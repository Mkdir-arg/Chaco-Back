"""Lo que lee el tablero del supervisor de Emergencia (E1). Nada de acá escribe.

Todo se **calcula al leer** (RN-5.1): no hay tabla de métricas ni job. La ventana es la de
la operación del día —los casos abiertos (cientos) más los cerrados o alojados en las
últimas 24 h—, nunca el histórico completo.

Tres reglas que cruzan el módulo:

* **Sin ``Trunc*``** sobre un ``DateTimeField`` (RN-5.2): la base de ECOM no tiene tablas de
  zona horaria y Django lo traduce a ``CONVERT_TZ``, que ahí devuelve ``NULL``. «Hoy» es el
  **día operativo** —desde las 06:00 hora Argentina (hallazgo H8)— calculado en Python
  (:func:`dia_operativo`) y filtrado con ``__gte`` / ``__lt``; lo demás se agrupa en Python.
* **Puras respecto de ``ahora``.** Ninguna función llama a ``now()``: el instante llega por
  parámetro, así que un test con momentos fijos contesta lo mismo a cualquier hora.
* **Una sola foto.** Las cuatro funciones públicas comparten la lectura de casos, red y
  derivaciones (:func:`foto_del_tablero`). La vista la arma una vez y se la pasa a todas
  (y a los avisos de ``programas.services.avisos_emergencia``); sin ``foto``, cada función
  la arma sola, que es cómodo en un test y caro en una pantalla.

Presupuesto (lo fija ``programas.tests.test_emergencia_tablero`` con ``@tag("performance")``,
500 casos abiertos, 50 dispositivos y 200 entregas; el ``read_timeout`` de ECOM es de 10 s):

=================================  =========================================================
:func:`foto_del_tablero`           **7 fijas**: casos de la ventana (con la última traza y
                                   el contacto posterior al alojamiento como subconsultas),
                                   dispositivos elegibles, las tres de ``ocupacion_de_plazas``
                                   en lote, derivaciones pendientes y entregas (en camino y
                                   con diferencias sin revisar).
:func:`resumen` (con foto)         **0**.
:func:`por_localidad` (con foto)   **0**.
:func:`tiempos` (con foto)         **0**.
:func:`entregas_en_camino`         **2**: las primeras ``tope`` entregas con su dispositivo, y
                                   sus líneas. El total sale de la foto.
**Selectores del tablero**         **9** en total.
=================================  =========================================================
"""

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import NamedTuple
from zoneinfo import ZoneInfo

from django.db.models import BooleanField, Exists, ExpressionWrapper, OuterRef, Prefetch, Q, Subquery
from django.urls import reverse
from django.utils import timezone

from programas.models import CasoEmergencia, ContactoCaso, Derivacion, EntregaKit, LineaEntrega
from programas.selectors.emergencia import (
    SLA_FUERA,
    TRAMO_ALOJAR,
    TRAMOS,
    camas_de,
    camas_libres,
    dispositivos_elegibles,
    estado_sla,
    texto_de_minutos,
    ultima_traza_del_caso,
)
from programas.selectors.kits import q_entrega_sin_revisar, resumen_de_items
from programas.services.bitacora_detalle import plural

Estado = CasoEmergencia.Estado
Origen = CasoEmergencia.Origen

#: El día operativo empieza a las 06:00 hora Argentina (H8): un caso alojado a las 05:30 es
#: del día anterior. No sale de ``settings.TIME_ZONE`` a propósito: la regla es de la
#: operación de la provincia, no de cómo esté configurado el servidor.
DIA_OPERATIVO_DESDE = time(6, 0)
ZONA_OPERATIVA = ZoneInfo("America/Argentina/Buenos_Aires")

#: La ventana de lo «reciente» del tablero (RN-5.1, RN-5.3).
VENTANA = timedelta(hours=24)

#: Los estados que el tablero cuenta como «en gestión» (tarjeta 2).
ESTADOS_EN_GESTION = (Estado.EN_GESTION, Estado.DERIVADO, Estado.INGRESO_EN_CURSO)

#: Cuántas entregas en camino se listan; el resto se alcanza desde E4.
TOPE_ENTREGAS = 20

#: Percentil de la tabla de tiempos.
PERCENTIL = 90

SIN_LOCALIDAD = "Sin localidad"


# ---------------------------------------------------------------------------
# Día operativo (RN-5.2, H8)
# ---------------------------------------------------------------------------


def dia_operativo(ahora: datetime):
    """``[desde, hasta)`` del día operativo que contiene ``ahora``, en momentos con zona.

    Empieza a las :data:`DIA_OPERATIVO_DESDE` hora Argentina: antes de esa hora, ``ahora``
    pertenece al día operativo que empezó ayer. Se calcula en Python y se filtra con
    ``__gte`` / ``__lt``: nada de ``TruncDate`` (RN-5.2). Sin consultas.
    """

    local = ahora.astimezone(ZONA_OPERATIVA)
    fecha = local.date() if local.time() >= DIA_OPERATIVO_DESDE else local.date() - timedelta(days=1)
    desde = datetime.combine(fecha, DIA_OPERATIVO_DESDE, tzinfo=ZONA_OPERATIVA)
    return desde, desde + timedelta(days=1)


# ---------------------------------------------------------------------------
# La foto compartida
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FilaCaso:
    """Lo que el tablero lee de un caso: las marcas del SLA y poco más (sin JSON).

    ``ultima_accion`` y ``ultimo_detalle`` son los de su última ``TrazaCaso``;
    ``contacto_posterior``, si la mesa registró un contacto desde que se alojó, e
    ``ingreso_directo``, ``CasoEmergencia.es_ingreso_directo`` leído en SQL con su ``Q``.
    """

    id: int
    numero: str
    estado: str
    origen: str
    localidad_id: int | None
    localidad: str
    familia: str
    total_declarado: int
    total_alojado: int | None
    creado: datetime
    tomado_en: datetime | None
    derivado_en: datetime | None
    aceptado_en: datetime | None
    alojado_en: datetime | None
    cerrado_en: datetime | None
    ultima_accion: str | None = None
    ultimo_detalle: str | None = None
    contacto_posterior: bool = False
    ingreso_directo: bool = False

    @property
    def abierto(self):
        return self.estado != Estado.CERRADO

    @property
    def ingreso_parcial(self):
        return self.total_alojado is not None and self.total_alojado < self.total_declarado


class DispositivoDeLaRed(NamedTuple):
    """Un elegible con sus **camas** libres y reservadas (``selectors.emergencia.camas_de``)."""

    id: int
    nombre: str
    localidad: str
    libres: int
    reservadas: int


class DerivacionPendiente(NamedTuple):
    id: int
    caso_id: int
    numero: str
    dispositivo_id: int
    dispositivo: str
    vence_en: datetime


class EntregaSinRevisar(NamedTuple):
    id: int
    numero: str
    dispositivo: str
    recibida_en: datetime | None


@dataclass(frozen=True)
class Red:
    """Los dispositivos elegibles (RN-2.2) con sus camas, de ``ocupacion_de_plazas`` en lote."""

    dispositivos: tuple[DispositivoDeLaRed, ...]

    @property
    def libres(self):
        return sum(dispositivo.libres for dispositivo in self.dispositivos)

    @property
    def reservadas(self):
        return sum(dispositivo.reservadas for dispositivo in self.dispositivos)

    def libres_de(self, pk):
        for dispositivo in self.dispositivos:
            if dispositivo.id == pk:
                return dispositivo.libres
        return None


@dataclass(frozen=True)
class Foto:
    """Lo que leen juntas las funciones del tablero y los avisos, en :func:`foto_del_tablero`."""

    sla: object
    ahora: datetime
    casos: tuple
    red: Red
    #: Derivaciones ``PENDIENTE`` con caso y dispositivo.
    pendientes: tuple[DerivacionPendiente, ...]
    #: Entregas ``RECIBIDA_CON_DIFERENCIAS`` sin observación de la mesa.
    entregas_sin_revisar: tuple[EntregaSinRevisar, ...]
    #: Cuántas entregas están ``EN_CAMINO``.
    entregas_en_camino: int
    semaforos: dict = field(default_factory=dict)

    @property
    def abiertos(self):
        return [caso for caso in self.casos if caso.abierto]


def _casos_de_la_ventana(ahora):
    """Una consulta: los abiertos más los alojados o cerrados en las últimas 24 h, sin JSON.

    La última traza (acción y detalle, con ``selectors.emergencia.ultima_traza_del_caso``) y si
    hubo contacto después del alojamiento van como subconsultas correlacionadas sobre los
    índices de la FK del caso: son cientos de filas y así los avisos no suman una consulta cada uno.
    """

    limite = ahora - VENTANA
    ultima = ultima_traza_del_caso()
    contacto = ContactoCaso.objects.filter(caso=OuterRef("pk"), momento__gte=OuterRef("alojado_en"))
    filas = (
        CasoEmergencia.objects.filter(~Q(estado=Estado.CERRADO) | Q(alojado_en__gte=limite) | Q(cerrado_en__gte=limite))
        .annotate(
            ultima_accion=Subquery(ultima.values("accion")[:1]),
            ultimo_detalle=Subquery(ultima.values("detalle")[:1]),
            contacto_posterior=Exists(contacto),
            ingreso_directo=ExpressionWrapper(CasoEmergencia.q_ingreso_directo(), output_field=BooleanField()),
        )
        .order_by("creado", "id")
        .values_list(
            "id",
            "numero",
            "estado",
            "origen",
            "localidad_id",
            "localidad__nombre",
            "grupo__responsable__apellido",
            "grupo__total_declarado",
            "total_alojado",
            "creado",
            "tomado_en",
            "derivado_en",
            "aceptado_en",
            "alojado_en",
            "cerrado_en",
            "ultima_accion",
            "ultimo_detalle",
            "contacto_posterior",
            "ingreso_directo",
        )
    )
    return tuple(
        FilaCaso(
            id=pk,
            numero=numero,
            estado=estado,
            origen=origen,
            localidad_id=localidad_id,
            localidad=localidad or "",
            familia=f"Familia {apellido}",
            total_declarado=total_declarado,
            total_alojado=total_alojado,
            creado=creado,
            tomado_en=tomado_en,
            derivado_en=derivado_en,
            aceptado_en=aceptado_en,
            alojado_en=alojado_en,
            cerrado_en=cerrado_en,
            ultima_accion=ultima_accion,
            ultimo_detalle=ultimo_detalle,
            contacto_posterior=bool(contacto_posterior),
            ingreso_directo=bool(ingreso_directo),
        )
        for (
            pk,
            numero,
            estado,
            origen,
            localidad_id,
            localidad,
            apellido,
            total_declarado,
            total_alojado,
            creado,
            tomado_en,
            derivado_en,
            aceptado_en,
            alojado_en,
            cerrado_en,
            ultima_accion,
            ultimo_detalle,
            contacto_posterior,
            ingreso_directo,
        ) in filas
    )


def red_de_dispositivos(momento):
    """Los elegibles con sus **camas** libres y reservadas. **4 consultas fijas** (RN-5.7).

    Una por los elegibles con su tipo (``selectors.emergencia.dispositivos_elegibles``) y las
    tres de ``ocupacion_de_plazas`` en lote con ``camas_de``: la misma cuenta que ve el panel
    «Derivar» de E3, sin una consulta por dispositivo. Un cupo o un turno libre no suma (RN-2.3).
    """

    elegibles = dispositivos_elegibles()
    censo = camas_de([dispositivo.pk for dispositivo in elegibles], momento)
    filas = []
    for dispositivo in elegibles:
        conteo = censo.de(dispositivo.pk).conteo
        filas.append(
            DispositivoDeLaRed(
                id=dispositivo.pk,
                nombre=dispositivo.nombre,
                localidad=dispositivo.localidad,
                libres=camas_libres(conteo),
                reservadas=conteo.reservadas or 0,
            )
        )
    return Red(dispositivos=tuple(filas))


def _derivaciones_pendientes():
    return tuple(
        DerivacionPendiente(*fila)
        for fila in Derivacion.objects.filter(estado=Derivacion.Estado.PENDIENTE)
        .order_by("vence_en", "id")
        .values_list("id", "caso_id", "caso__numero", "dispositivo_id", "dispositivo__nombre", "vence_en")
    )


def _entregas():
    """Una consulta: las en camino y las recibidas con diferencias sin revisar (``kits.q_entrega_sin_revisar``).

    Devuelve ``(sin_revisar, en_camino)``: la lista de las sin revisar y cuántas van en camino.
    """

    filas = (
        EntregaKit.objects.filter(Q(estado=EntregaKit.Estado.EN_CAMINO) | q_entrega_sin_revisar())
        .order_by("recibida_en", "id")
        .values_list("id", "numero", "estado", "dispositivo__nombre", "recibida_en")
    )
    sin_revisar, en_camino = [], 0
    for pk, numero, estado, dispositivo, recibida_en in filas:
        if estado == EntregaKit.Estado.EN_CAMINO:
            en_camino += 1
        else:
            sin_revisar.append(EntregaSinRevisar(pk, numero, dispositivo, recibida_en))
    return tuple(sin_revisar), en_camino


def foto_del_tablero(sla, ahora):
    """Lo que comparten las funciones del tablero y sus avisos. **7 consultas fijas.**

    Casos de la ventana (1), red de dispositivos (4, :func:`red_de_dispositivos`),
    derivaciones pendientes (1) y entregas en camino o con diferencias sin revisar (1). El
    semáforo de cada caso abierto se calcula acá, en Python, con ``estado_sla`` (sin consultas).
    """

    casos = _casos_de_la_ventana(ahora)
    semaforos = {}
    for caso in casos:
        semaforo = estado_sla(caso, sla, ahora)
        if semaforo is not None:
            semaforos[caso.id] = semaforo
    sin_revisar, en_camino = _entregas()
    return Foto(
        sla=sla,
        ahora=ahora,
        casos=casos,
        red=red_de_dispositivos(ahora),
        pendientes=_derivaciones_pendientes(),
        entregas_sin_revisar=sin_revisar,
        entregas_en_camino=en_camino,
        semaforos=semaforos,
    )


def asegurar_foto(sla, ahora, foto):
    """``foto``, o una nueva si no vino (7 consultas). La usan también los avisos."""

    return foto if foto is not None else foto_del_tablero(sla, ahora)


def fuera_de_sla(foto):
    """``[(caso, EstadoSLA)]`` de los casos fuera de SLA, del más excedido al menos. Sin consultas."""

    fuera = [(caso, foto.semaforos[caso.id]) for caso in foto.casos if caso.id in foto.semaforos]
    fuera = [(caso, semaforo) for caso, semaforo in fuera if semaforo.estado == SLA_FUERA]
    return sorted(fuera, key=lambda par: (-par[1].minutos, par[0].id))


# ---------------------------------------------------------------------------
# Hero y seis indicadores (05 §3)
# ---------------------------------------------------------------------------


def resumen(sla, ahora, foto=None):
    """El hero y las seis tarjetas de E1, con sus notas ya escritas.

    Devuelve ``{"titulo", "hero": {...}, "tarjetas": [...], "hay_casos"}``. Cada tarjeta es un
    dict con ``etiqueta``, ``valor``, ``nota``, ``icono`` y ``tono``, lista para
    ``components/_stat_card.html``; el template no cuenta nada.

    **Presupuesto: 0 consultas** con ``foto``; 7 sin ella.
    """

    foto = asegurar_foto(sla, ahora, foto)
    desde, hasta = dia_operativo(ahora)
    abiertos = foto.abiertos
    nuevos = [caso for caso in abiertos if caso.estado == Estado.NUEVO]
    en_gestion = [caso for caso in abiertos if caso.estado in ESTADOS_EN_GESTION]
    derivados = sum(1 for caso in en_gestion if caso.estado == Estado.DERIVADO)
    ingresando = sum(1 for caso in en_gestion if caso.estado == Estado.INGRESO_EN_CURSO)
    fuera = fuera_de_sla(foto)
    por_tramo = {tramo: 0 for tramo, *_resto in TRAMOS}
    for _caso, semaforo in fuera:
        por_tramo[semaforo.tramo] += 1
    alojadas = [caso for caso in foto.casos if caso.alojado_en is not None and desde <= caso.alojado_en < hasta]
    personas = sum(caso.total_alojado or 0 for caso in alojadas)
    directos = sum(1 for caso in alojadas if caso.ingreso_directo)
    parciales = sum(1 for caso in alojadas if caso.ingreso_parcial)
    en_camino = foto.entregas_en_camino
    sin_revisar = len(foto.entregas_sin_revisar)
    libres, reservadas = foto.red.libres, foto.red.reservadas
    n_dispositivos = len(foto.red.dispositivos)

    if nuevos:
        minutos = max(int((ahora - min(caso.creado for caso in nuevos)).total_seconds() // 60), 0)
        nota_nuevos = f"el más viejo hace {texto_de_minutos(minutos)}"
    else:
        nota_nuevos = "ninguno esperando"

    tarjetas = [
        {
            "etiqueta": "Casos nuevos sin tomar",
            "valor": len(nuevos),
            "nota": nota_nuevos,
            "icono": "fa-inbox",
            "tono": "warning" if nuevos else "brand",
        },
        {
            "etiqueta": "En gestión",
            "valor": len(en_gestion),
            "nota": f"{plural(derivados, 'derivado', 'derivados')} · {ingresando} ingresando",
            "icono": "fa-people-arrows",
            "tono": "brand",
        },
        {
            "etiqueta": "Fuera de SLA",
            "valor": len(fuera),
            "nota": " · ".join(f"{tramo} {cantidad}" for tramo, cantidad in por_tramo.items()),
            "icono": "fa-triangle-exclamation",
            "tono": "danger" if fuera else "success",
        },
        {
            "etiqueta": "Familias alojadas hoy",
            "valor": len(alojadas),
            "nota": (
                f"{plural(personas, 'persona', 'personas')} · {plural(directos, 'ingreso directo', 'ingresos directos')}"
                f" · {plural(parciales, 'parcial', 'parciales')}"
            ),
            "icono": "fa-house-chimney-user",
            "tono": "success",
        },
        {
            "etiqueta": "Plazas libres en la red",
            "valor": libres,
            "nota": plural(reservadas, "reservada", "reservadas"),
            "icono": "fa-bed",
            "tono": "brand" if libres else "danger",
        },
        {
            "etiqueta": "Entregas en camino",
            "valor": en_camino,
            "nota": f"{sin_revisar} con diferencias sin revisar",
            "icono": "fa-truck",
            "tono": "warning" if sin_revisar else "brand",
        },
    ]
    return {
        "titulo": sla.nombre_evento,
        "hero": {
            "abiertos": len(abiertos),
            "fuera": len(fuera),
            "libres": libres,
            "dispositivos": n_dispositivos,
        },
        "tarjetas": tarjetas,
        "hay_casos": bool(foto.casos),
        "dia_operativo": (desde, hasta),
    }


# ---------------------------------------------------------------------------
# Casos por localidad
# ---------------------------------------------------------------------------


def _clave_de_nombre(nombre):
    return " ".join((nombre or "").split()).casefold()


def por_localidad(sla, ahora, foto=None):
    """Una fila por localidad: nuevos, en gestión, fuera de SLA, alojadas hoy y camas libres.

    Los casos se agrupan por ``localidad_id`` (``core.Localidad``), **nunca por el nombre**
    (RN-009-04): en Chaco hay nombres repetidos en municipios distintos, y cada fila enlaza a la
    bandeja E2 filtrada por esa sola localidad. Los casos sin localidad van a «Sin localidad».

    La localidad del dispositivo es texto libre, así que sus camas libres se suman a la fila de
    casos cuyo nombre coincide (sin mayúsculas ni espacios de más) **solo si es una sola**. Si
    no hay ninguna, o si el nombre es de dos localidades con casos, van a una fila propia por
    nombre, sin enlace: una localidad que solo tiene dispositivos aparece igual (es donde hay
    lugar) y las camas no se atribuyen a una homónima al azar.

    Orden: fuera de SLA, de más a menos; después nuevos; después el nombre.

    **Presupuesto: 0 consultas** con ``foto``; 7 sin ella.
    """

    foto = asegurar_foto(sla, ahora, foto)
    desde, hasta = dia_operativo(ahora)
    fuera = {caso.id for caso, _semaforo in fuera_de_sla(foto)}
    filas = {}

    def fila(clave, nombre, localidad_id=None):
        if clave not in filas:
            filas[clave] = {
                "localidad": nombre,
                "localidad_id": localidad_id,
                "nuevos": 0,
                "en_gestion": 0,
                "fuera_de_sla": 0,
                "alojadas_hoy": 0,
                "plazas_libres": 0,
            }
        return filas[clave]

    for caso in foto.casos:
        if caso.localidad_id:
            actual = fila(("localidad", caso.localidad_id), caso.localidad, caso.localidad_id)
        else:
            actual = fila(("sin_localidad",), SIN_LOCALIDAD)
        if caso.estado == Estado.NUEVO:
            actual["nuevos"] += 1
        elif caso.estado in ESTADOS_EN_GESTION:
            actual["en_gestion"] += 1
        if caso.id in fuera:
            actual["fuera_de_sla"] += 1
        if caso.alojado_en is not None and desde <= caso.alojado_en < hasta:
            actual["alojadas_hoy"] += 1

    por_nombre = {}
    for clave, actual in filas.items():
        if actual["localidad_id"]:
            por_nombre.setdefault(_clave_de_nombre(actual["localidad"]), []).append(clave)
    for dispositivo in foto.red.dispositivos:
        nombre = (dispositivo.localidad or "").strip()
        if not nombre:
            continue
        homonimas = por_nombre.get(_clave_de_nombre(nombre), [])
        if len(homonimas) == 1:
            actual = filas[homonimas[0]]
        else:
            actual = fila(("nombre", _clave_de_nombre(nombre)), nombre)
        actual["plazas_libres"] += dispositivo.libres

    url_bandeja = reverse("emergencia:bandeja")
    resultado = []
    for actual in filas.values():
        actual["url"] = f"{url_bandeja}?localidad={actual['localidad_id']}" if actual["localidad_id"] else ""
        resultado.append(actual)
    resultado.sort(
        key=lambda f: (-f["fuera_de_sla"], -f["nuevos"], f["localidad"] == SIN_LOCALIDAD, f["localidad"].casefold())
    )
    return resultado


# ---------------------------------------------------------------------------
# Tiempos por tramo (RN-5.3)
# ---------------------------------------------------------------------------


def _percentil(valores, percentil):
    """Percentil por rango más cercano sobre ``valores`` ordenados. ``None`` sin valores."""

    if not valores:
        return None
    rango = max(math.ceil(percentil / 100 * len(valores)), 1)
    return valores[rango - 1]


def _minutos(valor):
    return "—" if valor is None else texto_de_minutos(int(round(valor)))


def tiempos(sla, ahora, foto=None):
    """Por tramo: objetivo (E7), mediana, percentil 90 y cuántos fuera de objetivo.

    La muestra de cada tramo son los casos de la ventana con ese tramo **terminado en las
    últimas 24 h** (la marca que lo cierra cae en la ventana) más los que lo tienen **en
    curso** ahora (medido hasta ``ahora``): así un tramo trabado pesa aunque no haya
    terminado. Los ingresos directos no entran en tomar, derivar ni aceptar —la mesa no
    intervino y el servicio deja esos tramos en cero—, sí en alojar.

    Mediana y p90 en Python sobre los minutos (RN-5.3). Un tramo sin casos muestra «—»:
    sin divisiones por cero.

    **Presupuesto: 0 consultas** con ``foto``; 7 sin ella.
    """

    foto = asegurar_foto(sla, ahora, foto)
    limite = ahora - VENTANA
    muestras = {tramo: [] for tramo, *_resto in TRAMOS}
    for caso in foto.casos:
        en_curso = foto.semaforos.get(caso.id)
        for tramo, abre, cierra, _campo in TRAMOS:
            if caso.ingreso_directo and tramo != TRAMO_ALOJAR:
                continue
            desde, hasta = getattr(caso, abre), getattr(caso, cierra)
            if desde is None:
                continue
            if hasta is not None:
                if hasta >= limite:
                    muestras[tramo].append(max((hasta - desde).total_seconds(), 0) / 60)
            elif en_curso is not None and en_curso.tramo == tramo:
                muestras[tramo].append(max((ahora - desde).total_seconds(), 0) / 60)
    filas = []
    for tramo, _abre, _cierra, campo in TRAMOS:
        valores = sorted(muestras[tramo])
        objetivo = getattr(sla, campo)
        filas.append(
            {
                "tramo": tramo.capitalize(),
                "objetivo": texto_de_minutos(objetivo),
                "casos": len(valores),
                "mediana": _minutos(statistics.median(valores) if valores else None),
                "p90": _minutos(_percentil(valores, PERCENTIL)),
                "fuera_de_objetivo": sum(1 for valor in valores if valor > objetivo),
            }
        )
    return filas


# ---------------------------------------------------------------------------
# Entregas en camino
# ---------------------------------------------------------------------------


def entregas_en_camino(sla, ahora, foto=None, tope=TOPE_ENTREGAS):
    """Las entregas ``EN_CAMINO``, la que salió hace más primero: ``(filas, total)``.

    Cada fila: ``numero``, ``dispositivo``, ``desde`` (fecha y hora), ``hace`` («hace 3 h»),
    ``items`` (resumen de lo enviado) y ``url`` (E5). Se leen de la base solo las primeras
    ``tope``; el ``total`` (para el enlace a E4) es el de la foto, que ya las contó.

    **Presupuesto: 2 consultas** con ``foto``: las entregas con su dispositivo, y sus líneas con
    el ítem (``prefetch``). Sin N+1 por fila.
    """

    foto = asegurar_foto(sla, ahora, foto)
    entregas = (
        EntregaKit.objects.filter(estado=EntregaKit.Estado.EN_CAMINO)
        .select_related("dispositivo")
        .prefetch_related(Prefetch("lineas", queryset=LineaEntrega.objects.select_related("item").order_by("id")))
        .order_by("despachada_en", "id")[:tope]
    )
    filas = []
    for entrega in entregas:
        desde = entrega.despachada_en or entrega.creado
        minutos = max(int((ahora - desde).total_seconds() // 60), 0)
        lineas = list(entrega.lineas.all())
        filas.append(
            {
                "numero": entrega.numero,
                "dispositivo": entrega.dispositivo.nombre,
                "desde": f"{timezone.localtime(desde):%d/%m %H:%M}",
                "hace": f"hace {texto_de_minutos(minutos)}",
                "items": resumen_de_items(lineas),
                "url": reverse("emergencia:entrega_detalle", args=[entrega.pk]),
            }
        )
    return filas, foto.entregas_en_camino
