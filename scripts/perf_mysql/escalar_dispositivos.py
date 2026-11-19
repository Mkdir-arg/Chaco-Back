"""Escala el banco a la forma de producción de **Dispositivos** (auditoría de noviembre de 2026,
fichas D-PERF-01 a D-PERF-10, D-DAT-01 y D-LIM-08).

Crea, sobre lo que ya sembró ``seed_perf``:

* 200 dispositivos ``BENCH-D-*`` de un tipo que admite camas: 199 chicos (2 sectores × 25
  plazas, 1 turno) y ``BENCH-D-GRANDE`` (10 sectores, 500 plazas, 3 turnos);
* 20.000 estadías egresadas en tres años y 300 activas en el grande, más 1.000 activas
  repartidas en los chicos; 100.000 ``MovimientoEstadia`` y una plaza «caliente» con 2.000
  salidas;
* trazas y bitácora (140.000 + 60.000 filas, 2.000 trazas ``EDITADO`` con detalle y 5 % de
  novedades corregidas);
* 30.000 reservas, 200 de ellas ``VIGENTE`` con ``hasta`` vencido en ``BENCH-D-0001``;
* adjuntos para ``/media/`` (50.000 de bitácora, 20.000 del alta, 200.000 del relevamiento);
* 1.000 usuarios con rol de Dispositivos (el alta arma pares usuario × rol con todos);
* 5.000 edificios (vinculados a los primeros 128 dispositivos) y 50.000 inspecciones.

**Idempotente**: cada bloque cuenta lo que ya hay con el prefijo del banco (``BENCH``) y crea
solo lo que falta hasta el objetivo; correrlo dos veces no duplica. **No borra nada.** Todos los
volúmenes se pueden bajar por argumento (``--help``) para una corrida de prueba.

Uso (raíz del repo, ``DATABASE_*`` apuntando al banco; ver README.md). Primero
``seed_perf`` y el seed de datos base, y ``DB_READ_TIMEOUT``/``DB_WRITE_TIMEOUT`` altos
**solo para sembrar**:
    python scripts/perf_mysql/escalar_dispositivos.py
"""

import argparse
import json
import random
from datetime import timedelta
from pathlib import Path

from _bootstrap import cargar_django, exigir_base_descartable  # noqa: E402

cargar_django()
exigir_base_descartable()

import _siembra_comun as comun  # noqa: E402
from django.conf import settings  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.db import connection, transaction  # noqa: E402
from django.utils import timezone  # noqa: E402

from programas.models import (  # noqa: E402
    AdjuntoBitacora,
    AdjuntoRespuestaAlta,
    AdjuntoRespuestaRelevamiento,
    DisenoFormulario,
    Dispositivo,
    Edificio,
    EntradaBitacora,
    Estadia,
    FotoInspeccion,
    InspeccionEdificio,
    MovimientoEstadia,
    Plaza,
    ReservaPlaza,
    RespuestasAltaDispositivo,
    TrazaDispositivo,
    TrazaInspeccion,
    Turno,
)

comun.sin_auto_now(TrazaDispositivo, "creado_en")
comun.sin_auto_now(TrazaInspeccion, "creado_en")
comun.sin_auto_now(EntradaBitacora, "creado")

GRANDE = "BENCH-D-GRANDE"
PREFIJO_EDIFICIO = "BENCH-ED-"


paso = comun.paso


def archivo_de_prueba(ruta_relativa):
    """Un archivo diminuto de verdad bajo MEDIA_ROOT: ``/media/`` autoriza y llega a servirlo."""
    destino = Path(settings.MEDIA_ROOT) / ruta_relativa
    destino.parent.mkdir(parents=True, exist_ok=True)
    if not destino.exists():
        destino.write_bytes(b"%PDF-1.4 bench\n")


# ---------------------------------------------------------------------------
# Bloques
# ---------------------------------------------------------------------------
def sembrar_dispositivos(args):
    tipo = comun.asegurar_tipo()
    grande, _ = comun.asegurar_dispositivo(
        GRANDE, "BENCH Centro grande", sectores=10, plazas_por_sector=args.plazas_grande // 10, turnos=3, tipo=tipo
    )
    chicos = comun.asegurar_chicos(args.dispositivos, tipo)
    paso(f"dispositivos: {Dispositivo.objects.filter(codigo__startswith='BENCH-D-').count()} (grande {grande.pk})")
    return grande, chicos


def sembrar_actores(grande, chicos):
    roles, guardia, admin, coordinador = comun.asegurar_actores_de_dispositivos(grande, chicos)
    inspectores = comun.asegurar_usuarios("bench_inspector", 20, roles["operador"])
    paso(f"actores: guardia={guardia.username} admin={admin.username} coordinador={coordinador.username}")
    return roles, guardia, admin, coordinador, inspectores


def sembrar_estadias(args, grande, chicos, pool, guardia, rng):
    """Egresadas del grande, activas del grande y de los chicos; con su INGRESO y EGRESO."""
    ahora = comun.ahora()
    # Los primeros 1.300 ciudadanos del pool son de las activas (una activa por persona).
    reservados = pool[: args.activas + args.activas_chicos]
    resto = pool[len(reservados) :] or pool
    plazas_grande = comun.plazas_de(grande.pk)

    egresadas = Estadia.objects.filter(dispositivo=grande, estado="EGRESADA").count()
    faltan = max(0, args.estadias - egresadas)
    nuevas, movs = [], []
    for _ in range(faltan):
        plaza_id, _sector = rng.choice(plazas_grande)
        ingreso = comun.fecha_aleatoria(rng, ahora - timedelta(days=3 * 365), ahora - timedelta(days=2))
        egreso = min(ingreso + timedelta(hours=rng.randint(6, 24 * 30)), ahora - timedelta(hours=1))
        nuevas.append(
            Estadia(
                ciudadano_id=rng.choice(resto),
                dispositivo=grande,
                plaza_id=plaza_id,
                fecha_ingreso=ingreso,
                fecha_egreso=egreso,
                estado="EGRESADA",
                ingresada_por=guardia,
                egresada_por=guardia,
            )
        )
    comun.en_lotes(Estadia, nuevas)
    for e in nuevas:
        movs.append(_mov(e, "INGRESO", e.fecha_ingreso, guardia, plaza_destino_id=e.plaza_id))
        movs.append(_mov(e, "EGRESO", e.fecha_egreso, guardia, plaza_origen_id=e.plaza_id))
    paso(f"estadías egresadas del grande: +{len(nuevas)}")

    activas = []
    # Una activa por persona en toda la red (UNIQUE de la clave): se descartan las que ya la tienen.
    con_activa = set(Estadia.objects.filter(estado="ACTIVA").values_list("ciudadano_id", flat=True))
    sin_activa = [c for c in reservados if c not in con_activa]

    def _activas_de(dispositivo, plazas, cantidad):
        ocupadas = set(
            Estadia.objects.filter(dispositivo=dispositivo, estado="ACTIVA").values_list("plaza_id", flat=True)
        )
        libres = [p for p, _s in plazas if p not in ocupadas]
        rng.shuffle(libres)
        while cantidad > 0 and libres and sin_activa:
            ciudadano_id = sin_activa.pop(0)
            ingreso = ahora - timedelta(hours=rng.randint(1, 24 * 60))
            activas.append(
                Estadia(
                    ciudadano_id=ciudadano_id,
                    dispositivo=dispositivo,
                    plaza_id=libres.pop(),
                    fecha_ingreso=ingreso,
                    estado="ACTIVA",
                    clave_alojamiento=f"CIU-{ciudadano_id}",
                    ingresada_por=guardia,
                )
            )
            cantidad -= 1

    ya_grande = Estadia.objects.filter(dispositivo=grande, estado="ACTIVA").count()
    _activas_de(grande, plazas_grande, args.activas - ya_grande)
    ya_chicos = Estadia.objects.filter(dispositivo__in=[d.pk for d in chicos], estado="ACTIVA").count()
    falta_chicos = args.activas_chicos - ya_chicos
    por_dispositivo = -(-max(0, falta_chicos) // max(1, len(chicos)))
    for d in chicos:
        if falta_chicos <= 0:
            break
        antes = len(activas)
        _activas_de(d, comun.plazas_de(d.pk), min(por_dispositivo, falta_chicos))
        falta_chicos -= len(activas) - antes
    comun.en_lotes(Estadia, activas)
    for e in activas:
        movs.append(_mov(e, "INGRESO", e.fecha_ingreso, guardia, plaza_destino_id=e.plaza_id))
    comun.en_lotes(MovimientoEstadia, movs)
    paso(f"estadías activas: +{len(activas)}; movimientos de ingreso/egreso: +{len(movs)}")


def _mov(estadia, tipo, momento, usuario, *, plaza_origen_id=None, plaza_destino_id=None):
    return MovimientoEstadia(
        estadia=estadia,
        dispositivo_id=estadia.dispositivo_id,
        tipo=tipo,
        momento=momento,
        responsable=usuario,
        plaza_origen_id=plaza_origen_id,
        plaza_destino_id=plaza_destino_id if tipo == "INGRESO" else None,
    )


def _egresadas_de(d, cantidad, pool, guardia, rng, ahora):
    """Estadías EGRESADAS de un chico, con sus movimientos; la plaza de la estadía es la final del encadenado."""
    plazas = [p for p, _s in comun.plazas_de(d.pk)]
    nuevas, cadenas = [], []
    for _ in range(cantidad):
        ingreso = comun.fecha_aleatoria(rng, ahora - timedelta(days=3 * 365), ahora - timedelta(days=2))
        egreso = min(ingreso + timedelta(hours=rng.randint(6, 24 * 30)), ahora - timedelta(hours=1))
        inicial = rng.choice(plazas)
        pasos, actual = [], inicial
        for momento in sorted(comun.fecha_aleatoria(rng, ingreso, egreso) for _ in range(2)):
            destino = rng.choice([p for p in plazas if p != actual])
            pasos.append((momento, actual, destino))
            actual = destino
        cadenas.append((inicial, pasos))
        nuevas.append(
            Estadia(
                ciudadano_id=rng.choice(pool),
                dispositivo=d,
                plaza_id=actual,
                fecha_ingreso=ingreso,
                fecha_egreso=egreso,
                estado="EGRESADA",
                ingresada_por=guardia,
                egresada_por=guardia,
            )
        )
    comun.en_lotes(Estadia, nuevas)
    movs = []
    for e, (inicial, pasos) in zip(nuevas, cadenas):
        movs.append(_mov(e, "INGRESO", e.fecha_ingreso, guardia, plaza_destino_id=inicial))
        movs.append(_mov(e, "EGRESO", e.fecha_egreso, guardia, plaza_origen_id=e.plaza_id))
        for momento, origen, destino in pasos:
            movs.append(
                MovimientoEstadia(
                    estadia=e,
                    dispositivo=d,
                    tipo="CAMBIO_PLAZA",
                    momento=momento,
                    responsable=guardia,
                    plaza_origen_id=origen,
                    plaza_destino_id=destino,
                )
            )
    comun.en_lotes(MovimientoEstadia, movs)
    return len(nuevas)


def sembrar_egresadas_chicos(args, chicos, pool, guardia, rng):
    """Historia de los chicos: ``--egresadas-chicos`` por dispositivo, con INGRESO, EGRESO y dos cambios de plaza.

    Sin esto el centro grande concentraba el 95 % de las filas de ``Estadia`` y
    ``MovimientoEstadia`` y el optimizador elegía planes que en producción, con la historia
    repartida entre cientos de dispositivos, no elegiría. Así el grande queda en torno al 20 %.
    """
    ids = [d.pk for d in chicos]
    ya = Estadia.objects.filter(dispositivo_id__in=ids, estado="EGRESADA").count()
    por_dispositivo = max(0, args.egresadas_chicos * len(ids) - ya) // max(1, len(ids))
    if por_dispositivo <= 0:
        paso(f"egresadas de los chicos: {ya} (objetivo {args.egresadas_chicos} por dispositivo), nada que agregar")
        return
    ahora = comun.ahora()
    total = 0
    for d in chicos:
        with transaction.atomic():
            total += _egresadas_de(d, por_dispositivo, pool, guardia, rng, ahora)
    paso(f"egresadas de los chicos: +{total}")


ACCIONES_SIEMBRA = ("CREADO", "EDITADO", "VALIDADO")

ACCION_DE_MOVIMIENTO = {
    "INGRESO": "ESTADIA_INGRESO",
    "EGRESO": "ESTADIA_EGRESO",
    "CAMBIO_PLAZA": "ESTADIA_CAMBIO_PLAZA",
}


def sembrar_trazas_de_movimientos():
    """Una ``TrazaDispositivo`` ``ESTADIA_*`` por movimiento, como las deja el servicio real.

    Si la cuenta no coincide se borran las del banco con esas acciones (y las inventadas por una
    versión anterior de este script: ``CAMBIO_PLAZA`` y ``BITACORA``) y se rearman todas.
    """
    bench = Dispositivo.objects.filter(codigo__startswith="BENCH-D-")
    n_mov = MovimientoEstadia.objects.filter(dispositivo__in=bench).count()
    acciones = list(ACCION_DE_MOVIMIENTO.values())
    if TrazaDispositivo.objects.filter(dispositivo__in=bench, accion__in=acciones).count() == n_mov:
        paso(f"trazas de movimientos: {n_mov} (ya están)")
        return
    borrar = [*acciones, "CAMBIO_PLAZA", "BITACORA"]
    with connection.cursor() as c:
        c.execute(
            "DELETE t FROM programas_trazadispositivo t JOIN programas_dispositivo d ON d.id = t.dispositivo_id "
            "WHERE d.codigo LIKE 'BENCH-D-%%' AND t.accion IN (" + ", ".join(["%s"] * len(borrar)) + ")",
            borrar,
        )
    lote = []
    movimientos = MovimientoEstadia.objects.filter(dispositivo__in=bench).values_list(
        "dispositivo_id", "tipo", "momento", "responsable_id"
    )
    for dispositivo_id, tipo, momento, responsable_id in movimientos.iterator(chunk_size=20000):
        lote.append(
            TrazaDispositivo(
                dispositivo_id=dispositivo_id,
                usuario_id=responsable_id,
                creado_en=momento,
                accion=ACCION_DE_MOVIMIENTO[tipo],
            )
        )
        if len(lote) >= 20000:
            comun.en_lotes(TrazaDispositivo, lote)
            lote = []
    comun.en_lotes(TrazaDispositivo, lote)
    paso(f"trazas de movimientos: +{n_mov}")


def sembrar_cambios_de_plaza(args, grande, guardia, rng):
    """Hasta ``--movimientos`` del grande, con una plaza «caliente» de ``--salidas-caliente`` salidas."""
    total = MovimientoEstadia.objects.filter(dispositivo=grande).count()
    faltan = args.movimientos - total
    if faltan <= 0:
        paso(f"movimientos: {total} (objetivo {args.movimientos}), nada que agregar")
        return
    estadias = list(
        Estadia.objects.filter(dispositivo=grande).order_by("pk").values_list("pk", "fecha_ingreso", "fecha_egreso")
    )
    plazas = [p for p, _s in comun.plazas_de(grande.pk)]
    caliente = plazas[0]
    ya_caliente = MovimientoEstadia.objects.filter(plaza_origen_id=caliente, tipo="CAMBIO_PLAZA").count()
    nuevos = []
    ahora = comun.ahora()
    for n in range(faltan):
        estadia_id, ingreso, egreso = rng.choice(estadias)
        origen = caliente if n < max(0, args.salidas_caliente - ya_caliente) else rng.choice(plazas)
        destino = rng.choice(plazas)
        if destino == origen:
            destino = plazas[(plazas.index(origen) + 1) % len(plazas)]
        momento = comun.fecha_aleatoria(rng, ingreso, egreso or ahora)
        nuevos.append(
            MovimientoEstadia(
                estadia_id=estadia_id,
                dispositivo=grande,
                tipo="CAMBIO_PLAZA",
                momento=momento,
                responsable=guardia,
                plaza_origen_id=origen,
                plaza_destino_id=destino,
            )
        )
    comun.en_lotes(MovimientoEstadia, nuevos)
    paso(f"cambios de plaza: +{len(nuevos)} (plaza caliente {caliente})")


def sembrar_auditoria(args, grande, chicos, guardia, rng):
    """``TrazaDispositivo`` y ``EntradaBitacora`` (con correcciones), hasta el objetivo de cada dispositivo."""
    ahora = comun.ahora()
    acciones = ACCIONES_SIEMBRA

    def trazas(dispositivo_id, cantidad, editados):
        filas = []
        for i in range(cantidad):
            accion = "EDITADO" if i < editados else rng.choice(acciones)
            detalle = ""
            if accion == "EDITADO":
                detalle = json.dumps({"campos": {"nombre": ["A", "B"], "camas_totales": [10, 12]}, "i": i})
            filas.append(
                TrazaDispositivo(
                    dispositivo_id=dispositivo_id,
                    usuario=guardia,
                    creado_en=comun.fecha_aleatoria(rng, ahora - timedelta(days=3 * 365), ahora),
                    accion=accion,
                    estado_anterior="ACTIVO" if accion == "VALIDADO" else "",
                    estado_nuevo="ACTIVO" if accion == "VALIDADO" else "",
                    detalle=detalle,
                )
            )
        return filas

    def entradas(dispositivo_id, turno_ids, cantidad):
        filas = []
        for i in range(cantidad):
            momento = comun.fecha_aleatoria(rng, ahora - timedelta(days=3 * 365), ahora)
            filas.append(
                EntradaBitacora(
                    dispositivo_id=dispositivo_id,
                    turno_id=rng.choice(turno_ids),
                    fecha_operativa=timezone.localdate(momento),
                    momento=momento,
                    creado=momento,
                    responsable=guardia,
                    tipo="GENERAL",
                    texto=f"Novedad {i} del turno del banco: sin cambios relevantes.",
                )
            )
        return filas

    def correcciones(originales, porcentaje):
        filas = []
        for o in originales[: int(len(originales) * porcentaje)]:
            filas.append(
                EntradaBitacora(
                    dispositivo_id=o.dispositivo_id,
                    turno_id=o.turno_id,
                    fecha_operativa=o.fecha_operativa,
                    momento=o.momento + timedelta(minutes=5),
                    creado=o.momento + timedelta(minutes=5),
                    responsable_id=o.responsable_id,
                    tipo=o.tipo,
                    texto=o.texto + " (corregida)",
                    version=2,
                    entrada_original_id=o.pk,
                    version_anterior_id=o.pk,
                    motivo_correccion="Corrección del banco",
                )
            )
        return filas

    # Grande: 20.000 trazas (2.000 EDITADO) y 10.000 entradas. Chicos: el resto, repartido.
    ya = TrazaDispositivo.objects.filter(dispositivo=grande, accion__in=ACCIONES_SIEMBRA).count()
    comun.en_lotes(TrazaDispositivo, trazas(grande.pk, max(0, args.trazas_grande - ya), 2000 if ya == 0 else 0))
    turnos = list(Turno.objects.filter(dispositivo=grande).values_list("pk", flat=True))
    ya = EntradaBitacora.objects.filter(dispositivo=grande, version=1).count()
    originales = comun.en_lotes(EntradaBitacora, entradas(grande.pk, turnos, max(0, args.bitacora_grande - ya)))
    comun.en_lotes(EntradaBitacora, correcciones(originales, 0.05))
    paso("trazas y bitácora del grande listas")

    ids = [d.pk for d in chicos]
    ya_t = TrazaDispositivo.objects.filter(dispositivo__in=ids, accion__in=ACCIONES_SIEMBRA).count()
    ya_e = EntradaBitacora.objects.filter(dispositivo__in=ids, version=1).count()
    por_t = max(0, args.trazas_chicos - ya_t) // len(ids)
    por_e = max(0, args.bitacora_chicos - ya_e) // len(ids)
    turno_de = {}
    for turno_id, dispositivo_id in Turno.objects.filter(dispositivo__in=ids).values_list("pk", "dispositivo_id"):
        turno_de.setdefault(dispositivo_id, []).append(turno_id)
    lote_t, lote_e = [], []
    for dispositivo_id in ids:
        lote_t += trazas(dispositivo_id, por_t, 0)
        lote_e += entradas(dispositivo_id, turno_de[dispositivo_id], por_e)
        if len(lote_t) >= 20000:
            comun.en_lotes(TrazaDispositivo, lote_t)
            lote_t = []
        if len(lote_e) >= 10000:
            originales = comun.en_lotes(EntradaBitacora, lote_e)
            comun.en_lotes(EntradaBitacora, correcciones(originales, 0.05))
            lote_e = []
    comun.en_lotes(TrazaDispositivo, lote_t)
    originales = comun.en_lotes(EntradaBitacora, lote_e)
    comun.en_lotes(EntradaBitacora, correcciones(originales, 0.05))
    paso(
        f"trazas totales {TrazaDispositivo.objects.count()}, entradas de bitácora {EntradaBitacora.objects.count()}"
        f" (con versión > 1: {EntradaBitacora.objects.filter(version__gt=1).count()})"
    )


def sembrar_reservas(args, grande, chicos, pool, guardia, rng):
    ahora = comun.ahora()
    vigentes_ya = ReservaPlaza.objects.filter(
        plaza__sector__dispositivo__codigo="BENCH-D-0001", estado="VIGENTE", hasta__lt=ahora
    ).count()
    plazas0001 = [p for p, _s in comun.plazas_de(chicos[0].pk)]
    vigentes = [
        ReservaPlaza(
            plaza_id=plazas0001[i % len(plazas0001)],
            ciudadano_id=pool[-(i + 1)],
            tipo="RESERVA",
            estado="VIGENTE",
            desde=ahora - timedelta(days=10),
            hasta=ahora - timedelta(days=1),
            motivo="Reserva vencida del banco",
            creada_por=guardia,
        )
        for i in range(vigentes_ya, args.reservas_vencidas)
    ]
    comun.en_lotes(ReservaPlaza, vigentes)
    ya = (
        ReservaPlaza.objects.filter(plaza__sector__dispositivo__codigo__startswith="BENCH-D-")
        .exclude(estado="VIGENTE")
        .count()
    )
    todas = [
        p for p in Plaza.objects.filter(sector__dispositivo__codigo__startswith="BENCH-D-").values_list("pk", flat=True)
    ]
    cerradas = []
    for i in range(max(0, args.reservas - ya)):
        desde = comun.fecha_aleatoria(rng, ahora - timedelta(days=3 * 365), ahora - timedelta(days=3))
        cerradas.append(
            ReservaPlaza(
                plaza_id=rng.choice(todas),
                ciudadano_id=rng.choice(pool),
                tipo="PRESTAMO" if i % 5 == 0 else "RESERVA",
                estado="CONSUMIDA" if i % 2 else "LIBERADA",
                desde=desde,
                hasta=desde + timedelta(days=2),
                motivo="Reserva del banco",
                creada_por=guardia,
            )
        )
    comun.en_lotes(ReservaPlaza, cerradas)
    paso(f"reservas: +{len(vigentes)} vencidas vigentes, +{len(cerradas)} cerradas")


def sembrar_usuarios_alta(args, roles):
    usuarios = comun.asegurar_usuarios("bench_op", args.usuarios, roles["operador"], staff=True)
    paso(f"usuarios con rol de Dispositivos (alta): {len(usuarios)}")


def sembrar_edificios(args, chicos, grande, coordinador, rng):
    """Edificios e inspecciones. Cada edificio queda vinculado a uno de los primeros 128 dispositivos."""
    ahora = comun.ahora()
    ya = Edificio.objects.filter(codigo__startswith=PREFIJO_EDIFICIO).count()
    comun.en_lotes(
        Edificio,
        [
            Edificio(
                codigo=f"{PREFIJO_EDIFICIO}{i:05d}",
                nombre=f"BENCH Edificio {i:05d}",
                calle=f"Calle {i % 300}",
                numero=str(100 + i % 900),
                localidad=("Resistencia", "Barranqueras", "Fontana", "Sáenz Peña", "Charata")[i % 5],
            )
            for i in range(ya, args.edificios)
        ],
    )
    edificios = list(
        Edificio.objects.filter(codigo__startswith=PREFIJO_EDIFICIO).order_by("codigo").values_list("pk", flat=True)
    )
    destinos = [grande.pk] + [d.pk for d in chicos[:127]]
    through = Edificio.dispositivos.through
    vinculados = set(through.objects.filter(edificio_id__in=edificios).values_list("edificio_id", flat=True))
    comun.en_lotes(
        through,
        [
            through(edificio_id=e, dispositivo_id=destinos[i % len(destinos)])
            for i, e in enumerate(edificios)
            if e not in vinculados
        ],
    )
    paso(f"edificios: {len(edificios)}")

    inspectores = list(User.objects.filter(username__startswith="bench_inspector_").order_by("pk"))
    ya = InspeccionEdificio.objects.filter(edificio_id__in=edificios).count()
    faltan = args.inspecciones - ya
    nuevas = []
    hoy = timezone.localdate()
    for n in range(max(0, faltan)):
        edificio_id = edificios[(ya + n) % len(edificios)]
        inspector = inspectores[n % len(inspectores)]
        creada = comun.fecha_aleatoria(rng, ahora - timedelta(days=3 * 365), ahora - timedelta(days=1))
        r = rng.random()
        datos = {
            "edificio_id": edificio_id,
            "asignado_a": inspector,
            "creado_por": coordinador,
            "fecha_vencimiento": timezone.localdate(creada) + timedelta(days=30),
        }
        if r < 0.85:
            datos |= {
                "estado": "REALIZADA",
                "criticidad": ("BAJA", "MEDIA", "ALTA")[n % 3],
                "realizada_en": creada + timedelta(days=5),
                "realizada_por": inspector,
                "observaciones": "Relevamiento del banco.",
            }
        elif r < 0.93:
            datos |= {"estado": "ASIGNADA", "fecha_vencimiento": hoy + timedelta(days=rng.randint(-30, 30))}
        else:
            datos |= {"estado": "CANCELADA", "motivo_cancelacion": "Cancelada en el banco"}
        nuevas.append(InspeccionEdificio(**datos))
    inspecciones = comun.en_lotes(InspeccionEdificio, nuevas)
    # Las fechas de creación repartidas en tres años (auto_now_add no deja fijarlas en el insert).
    comun.en_lotes(
        TrazaInspeccion,
        [
            TrazaInspeccion(
                inspeccion_id=i.pk,
                usuario=coordinador,
                creado_en=i.realizada_en or ahora,
                accion="ASIGNADA",
                detalle="",
            )
            for i in inspecciones
        ],
    )
    paso(f"inspecciones: +{len(inspecciones)}")
    return edificios


def sembrar_adjuntos(args, grande, chicos, edificios, guardia, rng):
    ids = [grande.pk] + [d.pk for d in chicos]
    ya = AdjuntoBitacora.objects.filter(archivo__startswith="dispositivos/bitacora/bench/").count()
    comun.en_lotes(
        AdjuntoBitacora,
        [
            AdjuntoBitacora(
                dispositivo_id=ids[i % len(ids)],
                archivo=f"dispositivos/bitacora/bench/{i:06d}.pdf",
                nombre_original=f"acta-{i}.pdf",
                subido_por=guardia,
            )
            for i in range(ya, args.adjuntos_bitacora)
        ],
    )
    # El archivo del medio y el último existen de verdad: `/media/` autoriza y los sirve.
    for i in (args.adjuntos_bitacora // 2, args.adjuntos_bitacora - 1):
        archivo_de_prueba(f"dispositivos/bitacora/bench/{i:06d}.pdf")
    paso(
        f"adjuntos de bitácora: {AdjuntoBitacora.objects.filter(archivo__startswith='dispositivos/bitacora/bench/').count()}"
    )

    tipo = comun.asegurar_tipo()
    diseno, _ = DisenoFormulario.objects.get_or_create(tipo_dispositivo=tipo, momento="crear_dispositivo")
    todos = list(Dispositivo.objects.filter(codigo__startswith="BENCH-D-").order_by("pk").values_list("pk", flat=True))
    existentes = set(RespuestasAltaDispositivo.objects.filter(diseno=diseno).values_list("dispositivo_id", flat=True))
    comun.en_lotes(
        RespuestasAltaDispositivo,
        [RespuestasAltaDispositivo(diseno=diseno, dispositivo_id=d) for d in todos if d not in existentes],
    )
    respuestas = list(
        RespuestasAltaDispositivo.objects.filter(diseno=diseno).order_by("pk").values_list("pk", flat=True)
    )
    ya = AdjuntoRespuestaAlta.objects.filter(archivo__startswith="dispositivos/formularios/bench/").count()
    comun.en_lotes(
        AdjuntoRespuestaAlta,
        [
            AdjuntoRespuestaAlta(
                respuestas_id=respuestas[i % len(respuestas)],
                clave="adjunto",
                archivo=f"dispositivos/formularios/bench/{i:06d}.pdf",
            )
            for i in range(ya, args.adjuntos_alta)
        ],
    )
    archivo_de_prueba(f"dispositivos/formularios/bench/{args.adjuntos_alta - 1:06d}.pdf")
    paso(
        f"adjuntos del alta: {AdjuntoRespuestaAlta.objects.filter(archivo__startswith='dispositivos/formularios/bench/').count()}"
    )

    inspecciones = list(
        InspeccionEdificio.objects.filter(edificio_id__in=edificios).order_by("pk").values_list("pk", flat=True)
    )
    ya = AdjuntoRespuestaRelevamiento.objects.filter(archivo__startswith="dispositivos/formularios/bench/rel-").count()
    comun.en_lotes(
        AdjuntoRespuestaRelevamiento,
        [
            AdjuntoRespuestaRelevamiento(
                inspeccion_id=inspecciones[i % len(inspecciones)],
                clave=f"adjunto_{i % 4}",
                archivo=f"dispositivos/formularios/bench/rel-{i:06d}.pdf",
            )
            for i in range(ya, args.adjuntos_relevamiento)
        ],
        lote=5000,
    )
    for i in (args.adjuntos_relevamiento // 2, args.adjuntos_relevamiento - 1):
        archivo_de_prueba(f"dispositivos/formularios/bench/rel-{i:06d}.pdf")
    paso(
        f"adjuntos de relevamiento: {AdjuntoRespuestaRelevamiento.objects.filter(archivo__startswith='dispositivos/formularios/bench/rel-').count()}"
    )

    # El informe con fotos (D-PERF-10): una realizada con 8 fotos.
    realizada = InspeccionEdificio.objects.filter(edificio_id__in=edificios, estado="REALIZADA").order_by("pk").first()
    if realizada is not None and not FotoInspeccion.objects.filter(inspeccion=realizada).exists():
        comun.en_lotes(
            FotoInspeccion,
            [
                FotoInspeccion(
                    inspeccion=realizada,
                    archivo=f"dispositivos/inspecciones/bench/{realizada.pk}-{n}.jpg",
                    descripcion=f"Foto {n}",
                    cargada_por=realizada.asignado_a,
                )
                for n in range(8)
            ],
        )


def reportar(grande, edificios):
    """Los ids que ``bench_mysql.py`` busca solo; se imprimen para el que escribe el informe."""
    print("\n== Resumen del banco de Dispositivos ==")
    print(f"dispositivo grande: pk={grande.pk} codigo={GRANDE}")
    for modelo in (Dispositivo, Plaza, Estadia, MovimientoEstadia, TrazaDispositivo, EntradaBitacora, ReservaPlaza):
        print(f"  {modelo.__name__:22} {modelo.objects.count()}")
    print(f"  edificios BENCH        {len(edificios)}")
    print(f"  inspecciones           {InspeccionEdificio.objects.count()}")


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--dispositivos", type=int, default=200, help="total, contando el grande")
    p.add_argument("--plazas-grande", type=int, default=500)
    p.add_argument("--ciudadanos", type=int, default=100_000)
    p.add_argument("--estadias", type=int, default=20_000, help="egresadas del grande")
    p.add_argument("--activas", type=int, default=300, help="activas del grande")
    p.add_argument("--activas-chicos", type=int, default=1_000)
    p.add_argument("--egresadas-chicos", type=int, default=500, help="por cada dispositivo chico")
    p.add_argument(
        "--movimientos", type=int, default=100_000, help="movimientos del centro grande (los de los chicos van aparte)"
    )
    p.add_argument("--salidas-caliente", type=int, default=2_000)
    p.add_argument("--trazas-grande", type=int, default=20_000)
    p.add_argument("--trazas-chicos", type=int, default=120_000)
    p.add_argument("--bitacora-grande", type=int, default=10_000)
    p.add_argument("--bitacora-chicos", type=int, default=50_000)
    p.add_argument("--reservas", type=int, default=30_000)
    p.add_argument("--reservas-vencidas", type=int, default=200)
    p.add_argument("--usuarios", type=int, default=1_000)
    p.add_argument("--edificios", type=int, default=5_000)
    p.add_argument("--inspecciones", type=int, default=50_000)
    p.add_argument("--adjuntos-bitacora", type=int, default=50_000)
    p.add_argument("--adjuntos-alta", type=int, default=20_000)
    p.add_argument("--adjuntos-relevamiento", type=int, default=200_000)
    args = p.parse_args()
    rng = random.Random(7)

    grande, chicos = sembrar_dispositivos(args)
    roles, guardia, admin, coordinador, _inspectores = sembrar_actores(grande, chicos)
    pool = comun.asegurar_ciudadanos(args.ciudadanos)
    sembrar_estadias(args, grande, chicos, pool, guardia, rng)
    sembrar_egresadas_chicos(args, chicos, pool, guardia, rng)
    sembrar_cambios_de_plaza(args, grande, guardia, rng)
    sembrar_trazas_de_movimientos()
    sembrar_auditoria(args, grande, chicos, guardia, rng)
    sembrar_reservas(args, grande, chicos, pool, guardia, rng)
    sembrar_usuarios_alta(args, roles)
    edificios = sembrar_edificios(args, chicos, grande, coordinador, rng)
    sembrar_adjuntos(args, grande, chicos, edificios, guardia, rng)
    reportar(grande, edificios)


if __name__ == "__main__":
    main()
