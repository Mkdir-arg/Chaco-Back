"""Escala el banco a la forma de producción de **Emergencia** (auditoría de noviembre de 2026,
fichas E-PERF-01 a E-PERF-15 y E-DAT-01).

Crea, sobre lo que ya sembró ``seed_perf`` (programa y SLA de Emergencia incluidos):

* los actores: 20 usuarios de la mesa, 2 supervisores, un agente de campo y una guardia con
  token de DRF y Equipo en los dispositivos (la guardia y el administrador de Dispositivos son
  los mismos de ``escalar_dispositivos.py``);
* los 200 dispositivos ``BENCH-D-*`` (si ``escalar_dispositivos.py`` no corrió, los arma igual)
  y el **centro grande** ``BENCH-E-GRANDE``: 300 camas en 6 sectores, 30 % con estadía abierta;
* 10.000 casos (90 % cerrados o alojados, 10 % abiertos en NUEVO, EN_GESTION, DERIVADO e
  INGRESO_EN_CURSO; ≈ 30 % de los abiertos fuera de SLA; 5 % con origen DISPOSITIVO; 50
  alojados en las últimas 24 h) con su grupo de 4, 5 trazas, contactos y adjuntos; 15.000
  derivaciones (200 PENDIENTE); en el centro grande, 1.000 casos con derivación aceptada, 10
  derivados y 3 en ingreso;
* 20.000 entregas de kits con 5 líneas y 3 trazas cada una (300 EN_CAMINO), y en el centro
  grande 500 EN_CAMINO de 8 líneas y 2.000 RECIBIDA;
* el padrón de ciudadanos llevado a ``--ciudadanos`` filas (DNI ``10000000 + i``), con ≈ 0,7 %
  guardados con puntos, que es lo que obliga al ``REGEXP`` del alta (E-PERF-01).

**Idempotente**: cada bloque cuenta lo que ya hay con el prefijo del banco (``BENCH-C-``,
``BENCH-K-``) y crea solo lo que falta hasta el objetivo. **No borra nada.** Los volúmenes
se bajan o suben por argumento: la variante grande de las fichas E-PERF-03/04/05 es
``--casos 100000 --entregas 200000``.

Uso (raíz del repo, ``DATABASE_*`` apuntando al banco; ver README.md). Con
``DB_READ_TIMEOUT``/``DB_WRITE_TIMEOUT`` altos **solo para sembrar**:
    python scripts/perf_mysql/escalar_emergencia.py
"""

import argparse
import random
import time as reloj
from datetime import timedelta

from _bootstrap import cargar_django, exigir_base_descartable  # noqa: E402

cargar_django()
exigir_base_descartable()

import _siembra_comun as comun  # noqa: E402
from django.db import transaction  # noqa: E402

from core.models import Localidad  # noqa: E402
from programas.models import (  # noqa: E402
    AdjuntoCaso,
    CasoEmergencia,
    ContactoCaso,
    Derivacion,
    EntregaKit,
    Estadia,
    GrupoFamiliar,
    IntegranteGrupo,
    LineaEntrega,
    TipoKit,
    TrazaCaso,
    TrazaEntrega,
)

GRANDE = "BENCH-E-GRANDE"
PREFIJO_CASO = "BENCH-C-"
PREFIJO_ENTREGA = "BENCH-K-"

comun.sin_auto_now(TrazaCaso, "creado_en")
comun.sin_auto_now(TrazaEntrega, "creado_en")
comun.sin_auto_now(CasoEmergencia, "creado")
comun.sin_auto_now(EntregaKit, "creado")

E = CasoEmergencia.Estado


def paso(texto):
    print(f"[{reloj.strftime('%H:%M:%S')}] {texto}", flush=True)


# ---------------------------------------------------------------------------
# Actores y dispositivos
# ---------------------------------------------------------------------------
def sembrar_actores():
    roles = {clave: comun.asegurar_rol(clave) for clave in comun.ROLES}
    mesa = comun.asegurar_usuarios("bench_mesa", 20, roles["mesa"], token=False)
    supervisores = comun.asegurar_usuarios("bench_sup", 2, roles["supervisor"])
    agente = comun.asegurar_usuarios("bench_agente", 1, roles["agente"], token=True)[0]
    guardia = comun.asegurar_usuarios("bench_guardia", 1, roles["guardia"], token=True)[0]
    admin = comun.asegurar_usuarios("bench_admin_disp", 1, roles["admin_dispositivos"], token=True)[0]
    paso(
        f"actores: {len(mesa)} de mesa, {len(supervisores)} supervisores, agente, guardia, administrador de Dispositivos"
    )
    return roles, mesa, supervisores, agente, guardia, admin


def sembrar_dispositivos(args, roles, guardia):
    tipo = comun.asegurar_tipo()
    chicos = []
    for i in range(1, args.dispositivos):
        d, _ = comun.asegurar_dispositivo(
            f"BENCH-D-{i:04d}", f"BENCH Dispositivo {i:04d}", sectores=2, plazas_por_sector=25, turnos=1, tipo=tipo
        )
        chicos.append(d)
    grande, creado = comun.asegurar_dispositivo(
        GRANDE, "BENCH Centro de evacuados", sectores=6, plazas_por_sector=args.camas_grande // 6, turnos=1, tipo=tipo
    )
    comun.asegurar_equipo([grande.pk] + [d.pk for d in chicos], guardia, roles["guardia"], responsable=True)
    paso(f"dispositivos: {len(chicos)} chicos + {GRANDE} (pk {grande.pk}, {args.camas_grande} camas)")
    return grande, chicos


def sembrar_estadias_del_grande(args, grande, pool, guardia, rng):
    """El 30 % de las camas del centro grande con una estadía abierta (E-PERF-09, E-PERF-15)."""
    ya = Estadia.objects.filter(dispositivo=grande, estado="ACTIVA").count()
    quiero = int(args.camas_grande * 0.30) - ya
    if quiero <= 0:
        return
    con_activa = set(Estadia.objects.filter(estado="ACTIVA").values_list("ciudadano_id", flat=True))
    ocupadas = set(Estadia.objects.filter(dispositivo=grande, estado="ACTIVA").values_list("plaza_id", flat=True))
    libres = [p for p, _s in comun.plazas_de(grande.pk) if p not in ocupadas]
    candidatos = [c for c in reversed(pool) if c not in con_activa]
    ahora = comun.ahora()
    nuevas = []
    for plaza_id, ciudadano_id in zip(libres[:quiero], candidatos):
        nuevas.append(
            Estadia(
                ciudadano_id=ciudadano_id,
                dispositivo=grande,
                plaza_id=plaza_id,
                fecha_ingreso=ahora - timedelta(hours=rng.randint(1, 72)),
                estado="ACTIVA",
                clave_alojamiento=f"CIU-{ciudadano_id}",
                ingresada_por=guardia,
            )
        )
    comun.en_lotes(Estadia, nuevas)
    paso(f"estadías abiertas en {GRANDE}: +{len(nuevas)}")


# ---------------------------------------------------------------------------
# Casos
# ---------------------------------------------------------------------------
def _estados(cantidad, rng):
    """Los estados de ``cantidad`` casos nuevos: 10 % abiertos, 1/3 de los demás ALOJADO, 2/3 CERRADO."""
    abiertos = cantidad // 10
    reparto = {E.NUEVO: 0.30, E.EN_GESTION: 0.30, E.DERIVADO: 0.20, E.INGRESO_EN_CURSO: 0.20}
    estados = []
    for estado, parte in reparto.items():
        estados += [estado] * int(abiertos * parte)
    estados += [E.NUEVO] * (abiertos - len(estados))
    resto = cantidad - len(estados)
    estados += [E.ALOJADO] * (resto // 3) + [E.CERRADO] * (resto - resto // 3)
    rng.shuffle(estados)
    return estados


@transaction.atomic  # un corte a la mitad no deja casos sin grupo, derivación o trazas: el reintento rehace todo
def sembrar_casos(args, mesa, supervisores, agente, grande, chicos, pool, rng):
    ya = CasoEmergencia.objects.filter(numero__startswith=PREFIJO_CASO).count()
    faltan = args.casos - ya
    if faltan <= 0:
        paso(f"casos: {ya} (objetivo {args.casos}), nada que agregar")
        return
    ahora = comun.ahora()
    estados = _estados(faltan, rng)
    localidades = list(Localidad.objects.order_by("pk").values_list("pk", flat=True)[:300])
    operadores = list(mesa) + list(supervisores)
    dispositivos = [d.pk for d in chicos]
    nombres_disp = {d.pk: d.nombre for d in chicos}

    # Responsables: 10 % repetidos (la misma persona con más de un caso, E-PERF-01 y el aviso de duplicados).
    responsables, usados = [], []
    for n in range(faltan):
        if usados and rng.random() < 0.10:
            responsables.append(rng.choice(usados))
        else:
            r = pool[(ya + n) % len(pool)]
            usados.append(r)
            responsables.append(r)

    grupos = comun.en_lotes(
        GrupoFamiliar,
        [
            GrupoFamiliar(
                responsable_id=responsables[n],
                traslado="MUNICIPIO",
                adultos_f=2,
                menores_m=1,
                menores_f=1,
                total_declarado=4,
            )
            for n in range(faltan)
        ],
    )

    casos = []
    alojados_24h = 0
    for n, estado in enumerate(estados):
        i = ya + n
        abierto = estado not in (E.ALOJADO, E.CERRADO)
        if abierto:
            fuera_de_sla = rng.random() < 0.30
            relevado = ahora - (
                timedelta(days=rng.uniform(1, 5)) if fuera_de_sla else timedelta(minutes=rng.uniform(2, 10))
            )
        elif estado == E.ALOJADO:
            reciente = alojados_24h < args.alojados_24h
            alojados_24h += reciente
            relevado = ahora - (timedelta(hours=rng.uniform(2, 20)) if reciente else timedelta(days=rng.uniform(1, 30)))
        else:
            relevado = ahora - timedelta(days=rng.uniform(2, 180))
        origen = rng.choices(["TERRITORIO", "MESA", "DISPOSITIVO"], weights=[75, 20, 5])[0]
        operador = rng.choice(operadores)
        datos = {
            "numero": f"{PREFIJO_CASO}{i + 1:06d}",
            "grupo": grupos[n],
            "origen": origen,
            "estado": estado,
            "prioridad": rng.choice(["ALTA", "MEDIA", "BAJA"]),
            "localidad_id": rng.choice(localidades) if localidades else None,
            "direccion": f"Calle {i % 400} {100 + i % 900}, barrio Bench",
            "relevado_por": agente if origen == "TERRITORIO" else operador,
            "relevado_en": relevado,
            "creado": relevado,
        }
        if estado != E.NUEVO:
            datos["tomado_por"] = operador
            datos["tomado_en"] = relevado + timedelta(minutes=10)
        if estado in (E.DERIVADO, E.INGRESO_EN_CURSO, E.ALOJADO) or (estado == E.CERRADO and i % 2):
            datos["derivado_en"] = relevado + timedelta(minutes=30)
        if estado in (E.INGRESO_EN_CURSO, E.ALOJADO) or (estado == E.CERRADO and i % 2):
            datos["aceptado_en"] = relevado + timedelta(minutes=60)
        if estado == E.ALOJADO or (estado == E.CERRADO and i % 2):
            datos["alojado_en"] = relevado + timedelta(minutes=90)
            datos["total_alojado"] = 4
        if estado == E.CERRADO:
            datos["cerrado_en"] = min(relevado + timedelta(days=rng.uniform(1, 20)), ahora - timedelta(hours=1))
            datos["motivo_cierre"] = "TODOS_EGRESADOS" if i % 2 else "NO_REQUIERE"
        if estado in (E.NUEVO, E.EN_GESTION) and rng.random() < 0.05:
            disp_id = rng.choice(dispositivos)
            datos["situacion"] = {
                CasoEmergencia.SITUACION_EN_LA_PUERTA: {"dispositivo_id": disp_id, "dispositivo": nombres_disp[disp_id]}
            }
        casos.append(CasoEmergencia(**datos))
    comun.en_lotes(CasoEmergencia, casos)
    paso(
        f"casos: +{len(casos)} ({', '.join(f'{k}={estados.count(k)}' for k in (E.NUEVO, E.EN_GESTION, E.DERIVADO, E.INGRESO_EN_CURSO, E.ALOJADO, E.CERRADO))})"
    )

    sembrar_integrantes(casos, grupos, responsables, pool, ya, rng, args)
    sembrar_trazas(casos, mesa, args, rng, ahora)
    sembrar_derivaciones(args, casos, ya, grande, dispositivos, operadores, rng, ahora)
    sembrar_contactos_y_adjuntos(args, casos, mesa, operadores, rng, ahora)


def sembrar_integrantes(casos, grupos, responsables, pool, ya, rng, args):
    filas = []
    parentescos = ["JEFE", "CONYUGE", "HIJO", "HIJO"]
    for n, (caso, grupo) in enumerate(zip(casos, grupos)):
        # Los primeros 1.000 casos cerrados o alojados van al centro grande: los cuatro con persona.
        de_grande = (ya + n) < args.casos_grande
        con_persona = {0, 1, 2, 3} if de_grande else {0, rng.randint(1, 3)}
        usados = {responsables[n]}
        for orden in range(4):
            ciudadano_id = None
            if orden == 0:
                ciudadano_id = responsables[n]
            elif orden in con_persona:
                for _ in range(5):
                    candidato = rng.choice(pool)
                    if candidato not in usados:
                        usados.add(candidato)
                        ciudadano_id = candidato
                        break
            filas.append(
                IntegranteGrupo(grupo=grupo, orden=orden + 1, ciudadano_id=ciudadano_id, parentesco=parentescos[orden])
            )
    comun.en_lotes(IntegranteGrupo, filas)
    paso(f"integrantes: +{len(filas)}")


def sembrar_trazas(casos, mesa, args, rng, ahora):
    """5 trazas por caso y ``--trazas-largas`` alojados con 100."""
    acciones = ["CREADO", "TOMADO", "CONTACTO", "DERIVADO", "PRIORIDAD"]
    filas = []
    largos = [c for c in casos if c.estado == E.ALOJADO][: args.trazas_largas]
    for caso in casos:
        usuario = caso.tomado_por or caso.relevado_por
        cantidad = 100 if caso in largos else 5
        for k in range(cantidad):
            filas.append(
                TrazaCaso(
                    caso_id=caso.pk,
                    usuario=usuario,
                    creado_en=caso.relevado_en + timedelta(minutes=5 * k),
                    accion=acciones[k % len(acciones)] if k < 5 else "CONTACTO",
                    estado_anterior="",
                    estado_nuevo=caso.estado if k == 4 else "",
                )
            )
        if len(filas) >= 20000:
            comun.en_lotes(TrazaCaso, filas)
            filas = []
    comun.en_lotes(TrazaCaso, filas)
    paso(f"trazas de caso: total {TrazaCaso.objects.count()}")


def sembrar_derivaciones(args, casos, ya, grande, dispositivos, operadores, rng, ahora):
    """Una ACEPTADA por alojado (o cerrado con alojamiento), una PENDIENTE por derivado y las históricas.

    Los 1.000 primeros casos con aceptación, los 10 primeros derivados y los 3 primeros en ingreso
    son del centro grande. ``clave_vigente`` se escribe a mano: ``bulk_create`` no pasa por ``save()``.
    """
    filas = []
    aceptadas_grande = derivados_grande = ingresos_grande = 0
    operador = operadores[0]
    for caso in casos:
        con_alojamiento = caso.estado == E.ALOJADO or (caso.estado == E.CERRADO and caso.alojado_en is not None)
        base = {
            "caso_id": caso.pk,
            "plazas_pedidas": 4,
            "derivada_por": caso.tomado_por or operador,
            "vence_en": (caso.derivado_en or caso.relevado_en) + timedelta(hours=12),
        }
        if con_alojamiento:
            dispositivo = grande.pk if aceptadas_grande < args.casos_grande else rng.choice(dispositivos)
            aceptadas_grande += dispositivo == grande.pk
            filas.append(
                Derivacion(
                    **base,
                    dispositivo_id=dispositivo,
                    estado="ACEPTADA",
                    respondida_por=operador,
                    respondida_en=caso.aceptado_en,
                    clave_vigente=caso.pk,
                )
            )
        elif caso.estado == E.INGRESO_EN_CURSO:
            dispositivo = grande.pk if ingresos_grande < 3 else rng.choice(dispositivos)
            ingresos_grande += dispositivo == grande.pk
            filas.append(
                Derivacion(
                    **base,
                    dispositivo_id=dispositivo,
                    estado="ACEPTADA",
                    respondida_por=operador,
                    respondida_en=caso.aceptado_en,
                    clave_vigente=caso.pk,
                )
            )
        elif caso.estado == E.DERIVADO:
            dispositivo = grande.pk if derivados_grande < 10 else rng.choice(dispositivos)
            derivados_grande += dispositivo == grande.pk
            base["vence_en"] = comun.ahora() + timedelta(hours=rng.uniform(-3, 12))
            filas.append(Derivacion(**base, dispositivo_id=dispositivo, estado="PENDIENTE", clave_vigente=caso.pk))
    # Históricas (RECHAZADA, VENCIDA, CANCELADA): sin clave vigente, sobre casos cerrados o en gestión.
    objetivo_historicas = max(0, args.derivaciones * len(casos) // max(1, args.casos) - len(filas))
    candidatos = [c for c in casos if c.estado in (E.CERRADO, E.EN_GESTION, E.NUEVO)]
    for k in range(objetivo_historicas):
        caso = rng.choice(candidatos)
        filas.append(
            Derivacion(
                caso_id=caso.pk,
                dispositivo_id=rng.choice(dispositivos),
                estado=("RECHAZADA", "VENCIDA", "CANCELADA")[k % 3],
                plazas_pedidas=4,
                derivada_por=caso.tomado_por or operador,
                vence_en=caso.relevado_en + timedelta(hours=12),
                respondida_en=caso.relevado_en + timedelta(hours=1),
                clave_vigente=None,
            )
        )
    comun.en_lotes(Derivacion, filas)
    total = Derivacion.objects.count()
    paso(
        f"derivaciones: +{len(filas)} (total {total}; PENDIENTE {Derivacion.objects.filter(estado='PENDIENTE').count()})"
    )


def sembrar_contactos_y_adjuntos(args, casos, mesa, operadores, rng, ahora):
    proporcion = len(casos) / max(1, args.casos)
    n_contactos = int(args.contactos * proporcion)
    comun.en_lotes(
        ContactoCaso,
        [
            ContactoCaso(
                caso_id=rng.choice(casos).pk,
                canal=rng.choice(["LLAMADA", "WHATSAPP", "SMS", "PRESENCIAL"]),
                resultado=rng.choice(["ATENDIO", "NO_ATENDIO", "NUMERO_ERRONEO", "OTRO"]),
                por=rng.choice(operadores),
                momento=ahora - timedelta(hours=rng.randint(1, 24 * 90)),
            )
            for _ in range(n_contactos)
        ],
    )
    n_adjuntos = int(args.adjuntos * proporcion)
    elegidos = rng.sample(casos, min(len(casos), n_adjuntos))
    comun.en_lotes(
        AdjuntoCaso,
        [
            AdjuntoCaso(
                caso_id=c.pk,
                tipo="VIVIENDA" if k % 2 else "ACCESO",
                archivo=f"emergencia/casos/bench/{c.pk}-{k}.jpg",
                cargado_por=rng.choice(operadores),
            )
            for k, c in enumerate(elegidos)
        ],
    )
    paso(f"contactos +{n_contactos}, adjuntos +{len(elegidos)}")


# ---------------------------------------------------------------------------
# Kits
# ---------------------------------------------------------------------------
def sembrar_kits(args, mesa, guardia, grande, chicos, rng):
    ahora = comun.ahora()
    ya_tipos = TipoKit.objects.filter(nombre__startswith="BENCH ítem").count()
    TipoKit.objects.bulk_create(
        [TipoKit(nombre=f"BENCH ítem {i:02d}", unidad="un", orden=i) for i in range(ya_tipos, args.tipos_kit)]
    )
    items = list(TipoKit.objects.filter(nombre__startswith="BENCH ítem").order_by("pk").values_list("pk", flat=True))
    dispositivos = [d.pk for d in chicos]

    def armar(cantidad, dispositivo_de, estado_de, lineas, desde):
        entregas = []
        for n in range(cantidad):
            estado = estado_de(n)
            despachada = ahora - timedelta(hours=rng.uniform(2, 24 * 90))
            datos = {
                "numero": f"{PREFIJO_ENTREGA}{desde + n + 1:06d}",
                "dispositivo_id": dispositivo_de(n),
                "estado": estado,
                "armada_por": rng.choice(mesa),
                "creado": despachada - timedelta(hours=1),
            }
            if estado != "PREPARADA" and estado != "CANCELADA":
                datos["despachada_en"] = despachada
            if estado in ("RECIBIDA", "RECIBIDA_CON_DIFERENCIAS"):
                datos["recibida_en"] = despachada + timedelta(hours=3)
                datos["recibida_por"] = guardia
            if estado == "CANCELADA":
                datos["motivo_cancelacion"] = "Cancelada en el banco"
            entregas.append(EntregaKit(**datos))
        comun.en_lotes(EntregaKit, entregas)
        filas, trazas = [], []
        for e in entregas:
            for item in rng.sample(items, lineas):
                recibida = None
                if e.estado == "RECIBIDA":
                    recibida = 10
                elif e.estado == "RECIBIDA_CON_DIFERENCIAS":
                    recibida = 8
                filas.append(
                    LineaEntrega(
                        entrega_id=e.pk, item_id=item, unidad="un", cantidad_enviada=10, cantidad_recibida=recibida
                    )
                )
            for accion in ("ARMADA", "EN_CAMINO", "RECIBIDA")[:3]:
                trazas.append(
                    TrazaEntrega(
                        entrega_id=e.pk,
                        usuario=e.armada_por,
                        creado_en=e.creado + timedelta(hours=1 if accion == "EN_CAMINO" else 0),
                        accion=accion,
                    )
                )
            if len(filas) >= 20000:
                comun.en_lotes(LineaEntrega, filas)
                comun.en_lotes(TrazaEntrega, trazas)
                filas, trazas = [], []
        comun.en_lotes(LineaEntrega, filas)
        comun.en_lotes(TrazaEntrega, trazas)

    ya = EntregaKit.objects.filter(numero__startswith=PREFIJO_ENTREGA, dispositivo__in=dispositivos).count()
    faltan = args.entregas - ya
    if faltan > 0:
        en_camino = int(args.en_camino * faltan / max(1, args.entregas))

        def estado_general(n):
            if n < en_camino:
                return "EN_CAMINO"
            r = (n * 7919) % 1000 / 1000  # reparto determinista, sin depender del orden
            if r < 0.70:
                return "RECIBIDA"
            if r < 0.80:
                return "RECIBIDA_CON_DIFERENCIAS"
            return "PREPARADA" if r < 0.90 else "CANCELADA"

        armar(faltan, lambda n: dispositivos[n % len(dispositivos)], estado_general, 5, EntregaKit.objects.count())
        paso(f"entregas generales: +{faltan}")

    ya_grande = EntregaKit.objects.filter(dispositivo=grande).count()
    if ya_grande < args.entregas_grande_en_camino + args.entregas_grande_recibidas:
        armar(
            args.entregas_grande_en_camino,
            lambda n: grande.pk,
            lambda n: "EN_CAMINO",
            8,
            EntregaKit.objects.count(),
        )
        armar(
            args.entregas_grande_recibidas,
            lambda n: grande.pk,
            lambda n: "RECIBIDA",
            5,
            EntregaKit.objects.count(),
        )
        paso(
            f"entregas del {GRANDE}: +{args.entregas_grande_en_camino} EN_CAMINO, +{args.entregas_grande_recibidas} RECIBIDA"
        )


def reportar(grande):
    print("\n== Resumen del banco de Emergencia ==")
    print(f"centro grande: pk={grande.pk} codigo={GRANDE}")
    for modelo in (
        CasoEmergencia,
        IntegranteGrupo,
        Derivacion,
        TrazaCaso,
        ContactoCaso,
        AdjuntoCaso,
        EntregaKit,
        LineaEntrega,
    ):
        print(f"  {modelo.__name__:18} {modelo.objects.count()}")
    from legajos.models import Ciudadano

    print(f"  Ciudadano          {Ciudadano.objects.count()}")


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--dispositivos", type=int, default=200, help="chicos + 1 (como escalar_dispositivos.py)")
    p.add_argument("--camas-grande", type=int, default=300)
    p.add_argument("--ciudadanos", type=int, default=500_000)
    p.add_argument("--casos", type=int, default=10_000)
    p.add_argument("--casos-grande", type=int, default=1_000, help="con derivación aceptada en el centro grande")
    p.add_argument("--alojados-24h", type=int, default=50)
    p.add_argument("--derivaciones", type=int, default=15_000)
    p.add_argument("--trazas-largas", type=int, default=20)
    p.add_argument("--contactos", type=int, default=5_000)
    p.add_argument("--adjuntos", type=int, default=2_000)
    p.add_argument("--tipos-kit", type=int, default=50)
    p.add_argument("--entregas", type=int, default=20_000)
    p.add_argument("--en-camino", type=int, default=300)
    p.add_argument("--entregas-grande-en-camino", type=int, default=500)
    p.add_argument("--entregas-grande-recibidas", type=int, default=2_000)
    args = p.parse_args()
    rng = random.Random(11)

    roles, mesa, supervisores, agente, guardia, _admin = sembrar_actores()
    pool = comun.asegurar_ciudadanos(args.ciudadanos)
    grande, chicos = sembrar_dispositivos(args, roles, guardia)
    sembrar_estadias_del_grande(args, grande, pool, guardia, rng)
    sembrar_casos(args, mesa, supervisores, agente, grande, chicos, pool, rng)
    sembrar_kits(args, mesa, guardia, grande, chicos, rng)
    reportar(grande)


if __name__ == "__main__":
    main()
