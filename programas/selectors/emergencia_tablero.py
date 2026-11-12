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
:func:`foto_del_tablero`           **7 fijas**: casos de la ventana, dispositivos elegibles,
                                   las tres de ``ocupacion_de_plazas`` en lote, derivaciones
                                   pendientes y entregas con diferencias sin revisar.
:func:`resumen` (con foto)         **1**: el conteo de entregas en camino.
:func:`por_localidad` (con foto)   **0**.
:func:`tiempos` (con foto)         **0**.
:func:`entregas_en_camino`         **2**: las entregas con su dispositivo y sus líneas.
**Selectores del tablero**         **10** en total.
=================================  =========================================================
"""

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Exists, OuterRef, Q
from django.urls import reverse
from django.utils import timezone

from programas.models import CasoEmergencia, Derivacion, Dispositivo, EntregaKit, TrazaEntrega
from programas.selectors.emergencia import (
    SLA_FUERA,
    TRAMO_ALOJAR,
    TRAMOS,
    dispositivo_elegible,
    estado_sla,
    texto_de_minutos,
)
from programas.selectors.kits import resumen_de_items
from programas.services.ocupacion import ocupacion_de_plazas

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
    """Lo que el tablero lee de un caso: las marcas del SLA y poco más (sin JSON)."""

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

    @property
    def abierto(self):
        return self.estado != Estado.CERRADO

    @property
    def ingreso_directo(self):
        """«Ingresar igual» sin pasar por la mesa: el servicio deja ``tomado_en = creado``.

        Un aviso a la mesa («en la puerta») también es de origen dispositivo, pero lo toma un
        operador después: su ``tomado_en`` es otro. Así se distingue sin leer ``situacion``.
        """

        return self.origen == Origen.DISPOSITIVO and self.tomado_en is not None and self.tomado_en == self.creado

    @property
    def ingreso_parcial(self):
        return self.total_alojado is not None and self.total_alojado < self.total_declarado


@dataclass(frozen=True)
class Red:
    """Los dispositivos elegibles (RN-2.2) con sus plazas, de ``ocupacion_de_plazas`` en lote."""

    dispositivos: tuple  # ((id, nombre, localidad, libres, reservadas), ...)

    @property
    def libres(self):
        return sum(libres for _pk, _nombre, _localidad, libres, _reservadas in self.dispositivos)

    @property
    def reservadas(self):
        return sum(reservadas for *_resto, reservadas in self.dispositivos)

    def libres_de(self, pk):
        for dispositivo_id, _nombre, _localidad, libres, _reservadas in self.dispositivos:
            if dispositivo_id == pk:
                return libres
        return None


@dataclass(frozen=True)
class Foto:
    """Lo que leen juntas las funciones del tablero y los avisos, en :func:`foto_del_tablero`."""

    sla: object
    ahora: datetime
    casos: tuple
    red: Red
    #: Derivaciones ``PENDIENTE`` con caso y dispositivo: ``(id, caso_id, numero, dispositivo_id,
    #: dispositivo, vence_en)``.
    pendientes: tuple
    #: Entregas ``RECIBIDA_CON_DIFERENCIAS`` sin observación de la mesa: ``(id, numero, dispositivo,
    #: recibida_en)``.
    entregas_sin_revisar: tuple
    semaforos: dict = field(default_factory=dict)

    @property
    def abiertos(self):
        return [caso for caso in self.casos if caso.abierto]


def _casos_de_la_ventana(ahora):
    """Una consulta: los abiertos más los alojados o cerrados en las últimas 24 h, sin JSON."""

    limite = ahora - VENTANA
    filas = (
        CasoEmergencia.objects.filter(
            ~Q(estado=Estado.CERRADO) | Q(alojado_en__gte=limite) | Q(cerrado_en__gte=limite)
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
        ) in filas
    )


def red_de_dispositivos(momento):
    """Los elegibles con sus plazas libres y reservadas. **4 consultas fijas** (RN-5.7).

    Una por los candidatos con su tipo (lo que mira el JSON del tipo se filtra en Python con
    ``dispositivo_elegible``, la única definición) y las tres de ``ocupacion_de_plazas`` en
    lote: la misma cuenta que ve el panel «Derivar» de E3, sin una consulta por dispositivo.
    """

    candidatos = (
        Dispositivo.objects.filter(estado=Dispositivo.Estado.ACTIVO, tipo__activo=True)
        .select_related("tipo")
        .order_by("nombre", "id")
    )
    elegibles = [dispositivo for dispositivo in candidatos if dispositivo_elegible(dispositivo)]
    censo = ocupacion_de_plazas([dispositivo.pk for dispositivo in elegibles], momento)
    filas = []
    for dispositivo in elegibles:
        conteo = censo.de(dispositivo.pk).conteo
        filas.append(
            (dispositivo.pk, dispositivo.nombre, dispositivo.localidad, max(conteo.disponibles or 0, 0), conteo.reservadas or 0)
        )
    return Red(dispositivos=tuple(filas))


def _derivaciones_pendientes():
    return tuple(
        Derivacion.objects.filter(estado=Derivacion.Estado.PENDIENTE)
        .order_by("vence_en", "id")
        .values_list("id", "caso_id", "caso__numero", "dispositivo_id", "dispositivo__nombre", "vence_en")
    )


def q_entrega_sin_revisar():
    """Recibida con diferencias y sin la observación de la mesa **posterior a la recepción**.

    No alcanza con mirar ``observacion_mesa``: el campo nace con la nota que la mesa le deja al
    dispositivo al armar la entrega. Lo que dice «la mesa la revisó» es la traza ``OBSERVADA``,
    que solo se escribe sobre una entrega ya recibida (``kits.observar_recepcion``).
    """

    observada = TrazaEntrega.objects.filter(entrega=OuterRef("pk"), accion=TrazaEntrega.Accion.OBSERVADA)
    return Q(estado=EntregaKit.Estado.RECIBIDA_CON_DIFERENCIAS) & ~Q(Exists(observada))


def _entregas_sin_revisar():
    return tuple(
        EntregaKit.objects.filter(q_entrega_sin_revisar())
        .order_by("recibida_en", "id")
        .values_list("id", "numero", "dispositivo__nombre", "recibida_en")
    )


def foto_del_tablero(sla, ahora):
    """Lo que comparten las funciones del tablero y sus avisos. **7 consultas fijas.**

    Casos de la ventana (1), red de dispositivos (4, :func:`red_de_dispositivos`),
    derivaciones pendientes (1) y entregas con diferencias sin revisar (1). El semáforo de
    cada caso abierto se calcula acá, en Python, con ``estado_sla`` (sin consultas).
    """

    casos = _casos_de_la_ventana(ahora)
    semaforos = {}
    for caso in casos:
        semaforo = estado_sla(caso, sla, ahora)
        if semaforo is not None:
            semaforos[caso.id] = semaforo
    return Foto(
        sla=sla,
        ahora=ahora,
        casos=casos,
        red=red_de_dispositivos(ahora),
        pendientes=_derivaciones_pendientes(),
        entregas_sin_revisar=_entregas_sin_revisar(),
        semaforos=semaforos,
    )


def _foto(sla, ahora, foto):
    return foto if foto is not None else foto_del_tablero(sla, ahora)


def fuera_de_sla(foto):
    """``[(caso, EstadoSLA)]`` de los casos fuera de SLA, del más excedido al menos. Sin consultas."""

    fuera = [(caso, foto.semaforos[caso.id]) for caso in foto.casos if caso.id in foto.semaforos]
    fuera = [(caso, semaforo) for caso, semaforo in fuera if semaforo.estado == SLA_FUERA]
    return sorted(fuera, key=lambda par: (-par[1].minutos, par[0].id))


def _plural(cantidad, singular, plural=None):
    return f"{cantidad} {singular if cantidad == 1 else (plural or singular + 's')}"


# ---------------------------------------------------------------------------
# Hero y seis indicadores (05 §3)
# ---------------------------------------------------------------------------


def resumen(sla, ahora, foto=None):
    """El hero y las seis tarjetas de E1, con sus notas ya escritas.

    Devuelve ``{"titulo", "hero": {...}, "tarjetas": [...], "hay_casos"}``. Cada tarjeta es un
    dict con ``etiqueta``, ``valor``, ``nota``, ``icono`` y ``tono``, lista para
    ``components/_stat_card.html``; el template no cuenta nada.

    **Presupuesto: 1 consulta** con ``foto`` (el conteo de entregas en camino); **8** sin ella.
    """

    foto = _foto(sla, ahora, foto)
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
    en_camino = EntregaKit.objects.filter(estado=EntregaKit.Estado.EN_CAMINO).count()
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
            "nota": f"{_plural(derivados, 'derivado')} · {ingresando} ingresando",
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
                f"{_plural(personas, 'persona')} · {_plural(directos, 'ingreso directo', 'ingresos directos')}"
                f" · {_plural(parciales, 'parcial', 'parciales')}"
            ),
            "icono": "fa-house-chimney-user",
            "tono": "success",
        },
        {
            "etiqueta": "Plazas libres en la red",
            "valor": libres,
            "nota": _plural(reservadas, "reservada"),
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


def _clave_de_localidad(nombre):
    return " ".join((nombre or "").split()).casefold()


def por_localidad(sla, ahora, foto=None):
    """Una fila por localidad: nuevos, en gestión, fuera de SLA, alojadas hoy y plazas libres.

    La localidad del caso es ``core.Localidad`` y la del dispositivo es texto libre: se cruzan
    por el nombre, sin mayúsculas ni espacios de más. Una localidad que solo tiene
    dispositivos aparece igual (es donde hay lugar). ``url`` es la bandeja E2 filtrada por
    esa localidad, o vacía si la fila no corresponde a una ``core.Localidad`` con casos.

    Orden: fuera de SLA, de más a menos; después nuevos; después el nombre.

    **Presupuesto: 0 consultas** con ``foto``; 7 sin ella.
    """

    foto = _foto(sla, ahora, foto)
    desde, hasta = dia_operativo(ahora)
    fuera = {caso.id for caso, _semaforo in fuera_de_sla(foto)}
    filas = {}

    def fila(clave, nombre):
        if clave not in filas:
            filas[clave] = {
                "localidad": nombre,
                "localidad_id": None,
                "nuevos": 0,
                "en_gestion": 0,
                "fuera_de_sla": 0,
                "alojadas_hoy": 0,
                "plazas_libres": 0,
            }
        return filas[clave]

    for caso in foto.casos:
        nombre = caso.localidad or SIN_LOCALIDAD
        actual = fila(_clave_de_localidad(caso.localidad) if caso.localidad_id else None, nombre)
        if caso.localidad_id:
            actual["localidad_id"] = caso.localidad_id
        if caso.estado == Estado.NUEVO:
            actual["nuevos"] += 1
        elif caso.estado in ESTADOS_EN_GESTION:
            actual["en_gestion"] += 1
        if caso.id in fuera:
            actual["fuera_de_sla"] += 1
        if caso.alojado_en is not None and desde <= caso.alojado_en < hasta:
            actual["alojadas_hoy"] += 1
    for _pk, _nombre, localidad, libres, _reservadas in foto.red.dispositivos:
        if not (localidad or "").strip():
            continue
        fila(_clave_de_localidad(localidad), localidad.strip())["plazas_libres"] += libres

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

    foto = _foto(sla, ahora, foto)
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


def entregas_en_camino(ahora, tope=TOPE_ENTREGAS):
    """Las entregas ``EN_CAMINO``, la que salió hace más primero: ``(filas, total)``.

    Cada fila: ``numero``, ``dispositivo``, ``desde`` (fecha y hora), ``hace`` («hace 3 h»),
    ``items`` (resumen de lo enviado) y ``url`` (E5). Se listan las primeras ``tope``; el
    total sirve para el enlace a E4.

    **Presupuesto: 2 consultas**: las entregas con su dispositivo, y sus líneas con el ítem
    (``prefetch``). Sin N+1 por fila.
    """

    entregas = list(
        EntregaKit.objects.filter(estado=EntregaKit.Estado.EN_CAMINO)
        .select_related("dispositivo")
        .prefetch_related("lineas__item")
        .order_by("despachada_en", "id")
    )
    filas = []
    for entrega in entregas[:tope]:
        desde = entrega.despachada_en or entrega.creado
        minutos = max(int((ahora - desde).total_seconds() // 60), 0)
        lineas = sorted(entrega.lineas.all(), key=lambda linea: linea.id)
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
    return filas, len(entregas)

