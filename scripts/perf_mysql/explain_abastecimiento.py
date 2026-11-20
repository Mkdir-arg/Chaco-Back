"""`EXPLAIN` de las lecturas de la solapa «Abastecimiento» de E8 (E-7b, RNF-009-10 y 11).

Lee la foto de situación (sin medirla: la mide ``explain_situacion.py``) y corre
``programas.selectors.emergencia_abastecimiento.lecturas_de_abastecimiento`` contra la base del
banco, captura **el SQL real** de A1-A5 (catálogo, recibido por dispositivo e ítem, en camino y
preparadas, personas alojadas y A5 si hace falta) y lo mide con ``_medicion.medir``: `EXPLAIN`,
filas leídas y tiempo.

Necesita ``SLAEmergencia.inicio_evento`` cargado y, para que la medición diga algo, un evento
anterior en la base. ``--sembrar`` (solo sobre la base descartable ``chaco_perf_ci``, una vez)
deja exactamente el banco con el que se midió el Cambio 510 y se justificó ``programas.0130``:
``inicio_evento`` hace 5 días, 30 ítems (dotación y reposición por persona, familia y lactante, y
sin regla), 50 dispositivos, 600 familias, 3.000 alojados y 300 egresados en el evento, **20.000
egresados de un evento anterior** (cada uno con su estadía egresada), **10.000 entregas recibidas
hace 30 días** y 2.000 de este evento (recibidas, con diferencias, preparadas, en camino y
canceladas), con tres líneas cada una. Las personas usan los DNI de prueba 90000001-90000099.
Receta: la del README (MariaDB 10.11 descartable y ``manage.py migrate``), después

    python scripts/perf_mysql/explain_abastecimiento.py --sembrar
    python scripts/perf_mysql/explain_abastecimiento.py [--repeticiones 20]

y, para el «antes» de un índice, ``manage.py migrate programas 0129`` y otra vez la segunda línea.
Los índices que el `EXPLAIN` pida van en una migración aparte.
"""

import argparse

from _bootstrap import cargar_django, exigir_base_descartable  # noqa: E402
from _medicion import medir  # noqa: E402

cargar_django()

from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402
from django.utils import timezone  # noqa: E402

from programas.selectors import emergencia_situacion as situacion  # noqa: E402
from programas.selectors.emergencia_abastecimiento import lecturas_de_abastecimiento  # noqa: E402
from programas.services.configuracion_emergencia import sla_vigente  # noqa: E402

PREFIJO = "B7-"
DNI_DE_PRUEBA = range(90_000_001, 90_000_100)


def _entregas(cuantas, prefijo, estado_de, momento_de, dispositivos, items, usuario):
    from programas.models import EntregaKit, LineaEntrega

    entregas = [
        EntregaKit(
            numero=f"{prefijo}-{n:07d}",
            dispositivo=dispositivos[n % len(dispositivos)],
            estado=estado_de(n),
            armada_por=usuario,
            despachada_en=momento_de(n),
            recibida_en=momento_de(n) if estado_de(n) in EntregaKit.ESTADOS_RECIBIDOS else None,
        )
        for n in range(cuantas)
    ]
    for desde in range(0, cuantas, 2000):
        lote = EntregaKit.objects.bulk_create(entregas[desde : desde + 2000])
        LineaEntrega.objects.bulk_create(
            [
                LineaEntrega(
                    entrega=entrega,
                    item=items[(k + j) % len(items)],
                    unidad="u",
                    cantidad_enviada=5,
                    cantidad_recibida=5 if entrega.recibida_en else None,
                )
                for k, entrega in enumerate(lote)
                for j in range(3)
            ]
        )


def sembrar():
    """El banco del Cambio 510 (ver el docstring del módulo). Una sola vez por base."""

    from datetime import timedelta
    from decimal import Decimal

    from django.contrib.auth import get_user_model

    from legajos.models import Ciudadano
    from programas.models import (
        Dispositivo,
        Estadia,
        GrupoFamiliar,
        IntegranteGrupo,
        Plaza,
        Sector,
        SLAEmergencia,
        TipoDispositivo,
        TipoKit,
    )

    exigir_base_descartable()
    if Dispositivo.objects.filter(codigo__startswith=PREFIJO).exists():
        raise SystemExit("El banco de Abastecimiento ya está sembrado en esta base.")
    ahora = timezone.now()
    sla = sla_vigente()
    SLAEmergencia.objects.filter(pk=sla.pk).update(inicio_evento=ahora - timedelta(days=5))
    usuario, _ = get_user_model().objects.get_or_create(username="bench_abastecimiento")
    tipo, _ = TipoDispositivo.objects.get_or_create(
        codigo="BENCH-E7B", defaults={"nombre": "Bench Abastecimiento", "tipos_plaza_admitidos": ["CAMA"]}
    )
    dispositivos = Dispositivo.objects.bulk_create(
        [Dispositivo(tipo=tipo, codigo=f"{PREFIJO}{n}", nombre=f"Bench {n}", estado="ACTIVO") for n in range(50)]
    )
    sectores = Sector.objects.bulk_create([Sector(dispositivo=d, nombre="G", capacidad=10) for d in dispositivos])
    Plaza.objects.bulk_create([Plaza(sector=s, codigo=f"C{k}") for s in sectores for k in range(10)])
    modos = (
        {"regla_modo": "DOTACION", "regla_cantidad": Decimal(1), "regla_por": "PERSONA"},
        {"regla_modo": "REPOSICION", "regla_cantidad": Decimal("0.5"), "regla_por": "PERSONA", "regla_cada_dias": 1},
        {"regla_modo": "REPOSICION", "regla_cantidad": Decimal(1), "regla_por": "FAMILIA", "regla_cada_dias": 3},
        {"regla_modo": "REPOSICION", "regla_cantidad": Decimal(1), "regla_por": "LACTANTE", "regla_cada_dias": 2},
        {},
    )
    items = TipoKit.objects.bulk_create(
        [TipoKit(nombre=f"Bench ítem {n}", unidad="u", orden=n, **modos[n % len(modos)]) for n in range(30)]
    )
    personas = [
        Ciudadano.objects.get_or_create(dni=str(dni), defaults={"nombre": "Bench", "apellido": "Abastecimiento"})[0]
        for dni in DNI_DE_PRUEBA
    ]
    grupos = GrupoFamiliar.objects.bulk_create(
        [
            GrupoFamiliar(
                responsable=personas[n % len(personas)],
                traslado="BOMBEROS",
                adultos_f=5,
                total_declarado=5,
                lactantes=n % 3,
            )
            for n in range(600)
        ]
    )
    activas = Estadia.objects.bulk_create(
        [
            Estadia(
                ciudadano=personas[n],
                dispositivo=dispositivos[n],
                fecha_ingreso=ahora - timedelta(days=4),
                clave_alojamiento=Estadia.clave_para(personas[n]),
            )
            for n in range(50)
        ]
    )
    egresadas = [
        Estadia(
            ciudadano=personas[n % len(personas)],
            dispositivo=dispositivos[n % 50],
            fecha_ingreso=ahora - timedelta(days=40),
            fecha_egreso=ahora - timedelta(days=30),
            estado="EGRESADA",
            clave_alojamiento=None,
        )
        for n in range(20000)
    ]
    for desde in range(0, len(egresadas), 2000):
        Estadia.objects.bulk_create(egresadas[desde : desde + 2000])
    viejos = [
        IntegranteGrupo(
            grupo=grupos[n % 600],
            orden=10000 + n,
            estadia=egresadas[n],
            ficha={"version": 1},
            confirmada_en=ahora - timedelta(days=40),
            egresado_en=ahora - timedelta(days=30),
        )
        for n in range(20000)
    ]
    for desde in range(0, len(viejos), 2000):
        IntegranteGrupo.objects.bulk_create(viejos[desde : desde + 2000])
    IntegranteGrupo.objects.bulk_create(
        [
            IntegranteGrupo(
                grupo=grupos[n % 600],
                orden=n,
                estadia=activas[n % 50],
                ficha={"version": 1},
                confirmada_en=ahora - timedelta(days=4),
                egresado_en=None if n < 3000 else ahora - timedelta(days=1),
            )
            for n in range(3300)
        ]
    )
    _entregas(
        10000,
        "BV",
        lambda n: "RECIBIDA",
        lambda n: ahora - timedelta(days=30, hours=n % 48),
        dispositivos,
        items,
        usuario,
    )
    estados = ("RECIBIDA", "RECIBIDA_CON_DIFERENCIAS", "PREPARADA", "EN_CAMINO", "CANCELADA")
    _entregas(
        2000, "BN", lambda n: estados[n % 5], lambda n: ahora - timedelta(hours=n % 96), dispositivos, items, usuario
    )
    print("Sembrado: 50 dispositivos, 30 ítems, 23.300 integrantes, 12.000 entregas (36.000 líneas).")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeticiones", type=int, default=20)
    parser.add_argument("--sembrar", action="store_true", help="siembra el banco del Cambio 510 y termina")
    args = parser.parse_args()

    if args.sembrar:
        sembrar()
        return
    exigir_base_descartable()  # sla_vigente() puede escribir el SLA de fábrica
    sla = sla_vigente()
    if sla.inicio_evento is None:
        raise SystemExit("Sin SLAEmergencia.inicio_evento la solapa no calcula: cargalo en el banco antes de medir.")
    foto = situacion.foto_de_situacion(sla, timezone.now())
    with CaptureQueriesContext(connection) as capturadas:
        lecturas = lecturas_de_abastecimiento(foto, sla.inicio_evento)
    consultas = [consulta["sql"] for consulta in capturadas.captured_queries]
    print(f"\n{connection.vendor} {'MariaDB' if connection.mysql_is_mariadb else 'MySQL'} {connection.mysql_version}")
    print(
        f"{len(consultas)} consultas · {len(lecturas.items)} ítems · {len(lecturas.recibido)} pares recibidos · "
        f"{len(lecturas.personas)} personas leídas · inicio del evento {sla.inicio_evento:%d/%m %H:%M}"
    )
    for numero, sql in enumerate(consultas, start=1):
        medir(f"A{numero} de la solapa", sql, args.repeticiones)


if __name__ == "__main__":
    main()
