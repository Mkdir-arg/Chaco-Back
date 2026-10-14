"""Datos del detalle de un dispositivo (MVP v2, etapa 2 · #692 · P4).

La vista no cuenta ni decide estados: delega acá, y acá tampoco se deciden las cifras de
plazas. Las cuatro cifras de la franja de indicadores y el desglose por sector salen del
:class:`~programas.services.ocupacion.Censo` de ``ocupacion_de_plazas``, **la misma fuente**
que el mapa de «Sectores y plazas» y el asistente de ingreso: dos pantallas que derivan
por separado terminan mostrando el mismo dispositivo con dos ocupaciones distintas.

Lo único que se cuenta acá son **estadías** (las personas alojadas, para el rótulo de la
solapa), y es otra cosa que la ocupación: ``ocupadas`` cuenta plazas con estadía activa y
una estadía en un tipo sin plaza identificable no ocupa ninguna.

El texto y el tono del badge de cada estadía también se deciden acá, no en el template.

Costo
-----

Constante en el volumen: el ``Censo`` son tres consultas, el contador de estadías una, y
cada listado paginado dos (el ``COUNT`` y la página) con ``select_related`` de la persona y
la plaza, así que **no hay una consulta por fila**. Las alertas son una o dos consultas por
regla (``programas.services.alertas_dispositivos``) y el historial, un ``COUNT`` y una
lectura por cada una de sus cuatro fuentes (``programas.selectors.auditoria_dispositivo``).
"""

from collections import defaultdict

from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.utils import timezone
from django.utils.formats import date_format

from core.services.vencimientos import avisos
from programas.models import Dispositivo, Edificio, Estadia, FotoInspeccion, InspeccionEdificio, Sector
from programas.selectors.auditoria_dispositivo import auditoria_del_dispositivo
from programas.services.alertas_dispositivos import AMBITO, ICONOS, TONOS
from programas.services.estadias import estado_visible
from programas.services.inspecciones import (
    SEMAFOROS,
    SIN_EDIFICIO,
    inspecciones_de_dispositivo,
    semaforo_de_inspeccion,
    semaforo_de_ultimas,
    subconsulta_ultima_realizada,
)

POR_PAGINA_ESTADIAS = 25
POR_PAGINA_HISTORIAL = 20
POR_PAGINA_RELEVAMIENTOS = 10
#: El tope que dibuja `components/_galeria_fotos.html`: la tanda se recorta acá, no en la pieza.
FOTOS_POR_TANDA = 24

#: Las solapas de P4, en el orden en que se dibujan. «Sectores y plazas» solo existe si el
#: tipo del dispositivo maneja plazas: en los demás, `?tab=sectores` no lleva a ninguna parte.
SOLAPAS = ("datos", "sectores", "estadias", "infraestructura", "historial")
#: La que abre la pantalla, y a la que vuelven las acciones del encabezado.
SOLAPA_POR_DEFECTO = "estadias"


def normalizar_solapa(pedida, *, con_plazas):
    """Qué solapa abre la pantalla: la de `?tab=` si existe para **este** dispositivo.

    Lo ajeno cae en la de siempre. Sin esto, `?tab=sectores` en un tipo que no maneja
    plazas —o cualquier valor inventado— dejaba la tarjeta entera en blanco: Alpine
    guardaba el valor de la URL y ningún panel coincidía con él.
    """

    solapas = SOLAPAS if con_plazas else tuple(solapa for solapa in SOLAPAS if solapa != "sectores")
    return pedida if pedida in solapas else SOLAPA_POR_DEFECTO


#: Valores del filtro «Estado»: vacío = las alojadas (lo que se mira todo el día).
FILTRO_ALOJADAS = ""
FILTRO_EGRESADAS = Estadia.Estado.EGRESADA
FILTRO_TODAS = "TODAS"

_TIPOS_DE_SECTOR = dict(Sector.Tipo.choices)

#: Por qué el dispositivo no admite ingresos, según su estado. Activo no lleva aviso.
_AVISO_SIN_INGRESOS = {
    Dispositivo.Estado.BORRADOR: "Está en borrador: admite ingresos cuando se envíe a validación y se valide.",
    Dispositivo.Estado.PENDIENTE_VALIDACION: "Está pendiente de validación: admite ingresos cuando se valide.",
    Dispositivo.Estado.OBSERVADO: "Está observado: hay que corregir los datos y volver a enviarlo a validación.",
    Dispositivo.Estado.RECHAZADO: "Fue rechazado en la validación: no admite ingresos.",
    Dispositivo.Estado.INACTIVO: "Está inactivo: no admite ingresos mientras siga así.",
    Dispositivo.Estado.CERRADO: "Está cerrado: el legajo se conserva, pero no admite ingresos ni otras operaciones.",
}


def aviso_sin_ingresos(dispositivo):
    """El texto de la alerta del encabezado, o vacío si el dispositivo está activo."""

    return _AVISO_SIN_INGRESOS.get(dispositivo.estado, "")


def indicadores_de_plazas(conteo):
    """Las cuatro tarjetas de la franja, con las cifras del ``Conteo`` y nada más.

    ``conteo`` es el del dispositivo (``Censo.de(dispositivo).conteo``): acá solo se le
    da formato. No se suma, no se resta y no se saca ningún porcentaje.
    """

    return [
        {
            "etiqueta": "Plazas operativas",
            "valor": conteo.operativas,
            "icono": "fa-bed",
            "nota": f"{conteo.totales} cargadas · {conteo.fuera_de_servicio} fuera de servicio",
        },
        {
            "etiqueta": "Ocupadas",
            "valor": conteo.ocupadas,
            "icono": "fa-users",
            "nota": f"de {conteo.operativas} operativas",
        },
        {
            "etiqueta": "Reservadas o prestadas",
            "valor": conteo.reservadas,
            "icono": "fa-bookmark",
            "nota": "reservas y préstamos vigentes",
        },
        {
            "etiqueta": "Disponibles",
            "valor": conteo.disponibles,
            "icono": "fa-door-open",
            "nota": "operativas sin ocupar ni reservar",
        },
    ]


def sectores_del_censo(ocupacion):
    """Una fila por sector activo, con las cifras que ya trae el censo (``OcupacionDispositivo``)."""

    return [
        {
            "pk": sector.sector_id,
            "nombre": sector.nombre,
            "tipo": _TIPOS_DE_SECTOR.get(sector.tipo, sector.tipo),
            "totales": sector.conteo.totales,
            "ocupadas": sector.conteo.ocupadas,
            "reservadas": sector.conteo.reservadas,
            "disponibles": sector.conteo.disponibles,
            "fuera_de_servicio": sector.conteo.fuera_de_servicio,
        }
        for sector in ocupacion.sectores
    ]


def contar_alojadas(dispositivo):
    """Las personas alojadas hoy (estadías activas): el contador de la solapa. Una consulta."""

    return Estadia.objects.activas().filter(dispositivo=dispositivo).count()


def normalizar_filtros(estado, sector, sector_ids):
    """Lleva lo que llegó por la URL a valores que el servicio entiende; lo ajeno se descarta."""

    estado = estado if estado in (FILTRO_EGRESADAS, FILTRO_TODAS) else FILTRO_ALOJADAS
    texto = str(sector)
    # Solo dígitos ASCII: `isdigit()` acepta «²» (y `int()` lo rechaza con un 500) y `int()`
    # acepta dígitos de otros alfabetos, espacios y signos que una URL armada a mano puede traer.
    sector = int(texto) if texto.isascii() and texto.isdecimal() else None
    return estado, sector if sector in sector_ids else None


def pildoras_de_estadias(estado, sector, sectores):
    """Las píldoras de la fila de filtros, armadas acá porque el componente no decide nada.

    «Sector» solo aparece si el dispositivo tiene sectores: una píldora con «Todos» como única
    opción no filtra nada.
    """

    pildoras = [
        {
            "nombre": "estado",
            "etiqueta": "Estado",
            "todos": "Alojadas",
            "opciones": [(FILTRO_EGRESADAS, "Egresadas"), (FILTRO_TODAS, "Todas")],
            "valor": estado,
        },
    ]
    if sectores:
        pildoras.append(
            {
                "nombre": "sector",
                "etiqueta": "Sector",
                "todos": "Todos",
                "opciones": [(fila["pk"], fila["nombre"]) for fila in sectores],
                "valor": sector or "",
            }
        )
    return pildoras


def estadias_del_dispositivo(dispositivo, *, estado=FILTRO_ALOJADAS, sector=None, pagina=1, momento=None):
    """La página de estadías del dispositivo, lista para dibujar.

    Trae a la persona y a la plaza con su sector en la misma consulta y solo las columnas
    que la tabla muestra. A cada estadía de la página le deja ``estado_texto`` y ``tono`` (de
    la tabla única de `programas.services.estadias`) y ``dias_de_permanencia`` (hasta el
    egreso, o hasta ``momento`` si sigue alojada), para que el template no decida nada.
    """

    momento = momento or timezone.now()

    consulta = (
        Estadia.objects.filter(dispositivo=dispositivo)
        .select_related("ciudadano", "plaza__sector")
        .only(
            "id",
            "estado",
            "fecha_ingreso",
            "fecha_egreso",
            "ciudadano__id",
            "ciudadano__nombre",
            "ciudadano__apellido",
            "ciudadano__dni",
            "plaza__id",
            "plaza__codigo",
            "plaza__sector__id",
            "plaza__sector__nombre",
        )
        .order_by("-fecha_ingreso", "-id")
    )
    if estado == FILTRO_EGRESADAS:
        consulta = consulta.filter(estado=Estadia.Estado.EGRESADA)
    elif estado != FILTRO_TODAS:
        consulta = consulta.filter(estado=Estadia.Estado.ACTIVA)
    if sector:
        consulta = consulta.filter(plaza__sector_id=sector)
    pagina_de_estadias = Paginator(consulta, POR_PAGINA_ESTADIAS).get_page(pagina)
    # Recorrer el `Page` lo materializa en una lista, así que los atributos llegan al template.
    for estadia in pagina_de_estadias:
        estadia.estado_texto, estadia.tono = estado_visible(estadia)
        estadia.dias_de_permanencia = ((estadia.fecha_egreso or momento) - estadia.fecha_ingreso).days
    return pagina_de_estadias


def _fecha_legible(fecha):
    if fecha is None:
        return ""
    if hasattr(fecha, "hour"):
        return date_format(timezone.localtime(fecha), "d/m/Y H:i")
    return date_format(fecha, "d/m/Y")


def alertas_del_dispositivo(dispositivo, momento=None, usuario=None):
    """Las alertas vigentes del dispositivo, de la más severa a la menos, listas para `_alerta.html`.

    Salen del registro de reglas de aviso (``core.services.vencimientos``, ámbito
    ``dispositivos``): se derivan del dato en cada pedido y no bloquean nada. Cada una
    lleva severidad, origen, fecha y —si hay pantalla donde resolverla— su enlace.

    ``usuario`` es quien mira, y decide **solo el enlace**: las pantallas donde se
    resuelve una alerta tienen su propia capacidad, así que ofrecerle el link a quien va a
    rebotar con un 403 sería anunciarle una puerta cerrada. Qué alertas hay no depende de
    quién mira (ver `programas.services.alertas_dispositivos`). Sin usuario, las alertas
    que dependen de una capacidad llegan sin enlace.
    """

    alertas = []
    for aviso in avisos(AMBITO, dispositivo, momento or timezone.now(), usuario=usuario):
        fecha = _fecha_legible(aviso.fecha)
        pie = f"{aviso.origen} · desde el {fecha}" if fecha else aviso.origen
        alertas.append(
            {
                "regla": aviso.regla,
                "severidad": aviso.severidad,
                "tono": TONOS[aviso.severidad],
                "icono": ICONOS[aviso.severidad],
                "titulo": aviso.titulo,
                "texto": f"{aviso.texto} {pie}.",
                "origen": aviso.origen,
                "fecha": aviso.fecha,
                "enlace": aviso.enlace,
                "accion": aviso.accion,
            }
        )
    return alertas


def eventos_de_historial(dispositivo, pagina=1):
    """La página de la auditoría del dispositivo como eventos de la línea de tiempo (más nuevo primero).

    Junta las cuatro trazas —legajo, estadías, correcciones de bitácora y relevamientos
    edilicios— en una sola lista (``programas.selectors.auditoria_dispositivo``).
    """

    pagina_de_eventos = Paginator(auditoria_del_dispositivo(dispositivo), POR_PAGINA_HISTORIAL).get_page(pagina)
    eventos = [
        {
            "cuando": f"{_fecha_legible(evento['fecha'])} · {evento['quien']}",
            "titulo": evento["titulo"],
            "detalle": evento["detalle"],
            "tono": evento["tono"],
        }
        for evento in pagina_de_eventos
    ]
    return pagina_de_eventos, eventos


# --------------------------------------------------------------------------- #
# Solapa Infraestructura (P19 recortada · task 37) y su semáforo (task 40)
# --------------------------------------------------------------------------- #

_REALIZADA = InspeccionEdificio.Estado.REALIZADA
_TONOS_CON_COLOR = ("success", "warning", "danger")


def _nombre(usuario):
    if usuario is None:
        return "sin responsable"
    return usuario.get_full_name() or usuario.username


def _fecha(momento):
    return date_format(timezone.localtime(momento), "d/m/Y")


def _cantidad_de_fotos(cantidad):
    if not cantidad:
        return "Sin fotos"
    return f"{cantidad} foto{'s' if cantidad != 1 else ''}"


def _evento_de_relevamiento(inspeccion, fotos, con_edificio):
    """Una entrada de la línea de tiempo por relevamiento, con su tanda de fotos adentro.

    Lo que pasó va en el texto, no en el color. ``fotos`` y ``total_fotos`` son el opcional de
    `components/_linea_tiempo.html` que dibuja la galería dentro del evento.
    """

    edificio = f" · {inspeccion.edificio.nombre}" if con_edificio else ""
    rotulos = ", ".join(list(dict.fromkeys(foto.descripcion for foto in fotos if foto.descripcion))[:8])
    galeria = {"pk": inspeccion.pk, "fotos": _fotos_de_la_tanda(inspeccion, fotos), "total_fotos": inspeccion.n_fotos}
    if inspeccion.estado != _REALIZADA:
        detalle = _cantidad_de_fotos(inspeccion.n_fotos).lower()
        return {
            "cuando": f"en curso{edificio} · asignado a {_nombre(inspeccion.asignado_a)}",
            "titulo": "Relevamiento en curso",
            "detalle": f"{detalle} · {rotulos}" if rotulos else detalle,
            **galeria,
        }
    semaforo = semaforo_de_inspeccion(inspeccion)
    evento = {
        "cuando": f"{_fecha(inspeccion.realizada_en)} · relevamiento{edificio} · {_nombre(inspeccion.realizada_por)}",
        "titulo": _cantidad_de_fotos(inspeccion.n_fotos),
        "detalle": rotulos,
        "badge": semaforo.texto,
        "badge_tono": semaforo.tono,
        **galeria,
    }
    if semaforo.tono in _TONOS_CON_COLOR:
        evento["tono"] = semaforo.tono
    return evento


#: Formatos que se aceptan al cargar (Cambio 275) y que un navegador no dibuja en un `<img>`.
_SIN_VISTA_PREVIA = (".heic", ".heif")


def _fotos_de_la_tanda(inspeccion, fotos):
    """Los dicts que pide `_galeria_fotos.html`. La URL es la de `/media/`, que está detrás de login.

    Una HEIC o HEIF va sin URL: la pieza dibuja la celda gris con cámara en vez de una imagen rota.
    """

    fecha = _fecha(inspeccion.realizada_en or inspeccion.creado)
    galeria = []
    for numero, foto in enumerate(fotos[:FOTOS_POR_TANDA], start=1):
        rotulo = foto.descripcion or f"Foto {numero}"
        galeria.append(
            {
                "url": "" if foto.archivo.name.lower().endswith(_SIN_VISTA_PREVIA) else foto.archivo.url,
                "alt": f"{rotulo} · {inspeccion.edificio.nombre} · relevamiento del {fecha}",
                "rotulo": rotulo,
                "fecha": foto.creado,
            }
        )
    return galeria


def _indicadores_edilicios(semaforo, edificios, realizados, fotos):
    """La franja de la solapa: el semáforo y dos cifras, ya formateadas."""

    if len(edificios) > 1:
        nota_estado = f"el más grave de {len(edificios)} edificios"
    elif edificios[0]["ultima"] is not None:
        nota_estado = f"último relevamiento {_fecha(edificios[0]['ultima'].realizada_en)}"
    else:
        nota_estado = "ningún relevamiento realizado"
    return [
        {
            "etiqueta": "Estado edilicio",
            "valor": semaforo.texto,
            "icono": "fa-building",
            # La stat card chica no tiene gris: sin color, va con el de marca y el texto manda.
            "tono": semaforo.tono if semaforo.tono in _TONOS_CON_COLOR else "brand",
            "nota": nota_estado,
        },
        {
            "etiqueta": "Relevamientos realizados",
            "valor": realizados,
            "icono": "fa-clipboard-check",
            "tono": "brand",
            "nota": "cada uno queda en el registro",
        },
        {
            "etiqueta": "Fotos",
            "valor": fotos,
            "icono": "fa-camera",
            "tono": "brand",
            "nota": "cada relevamiento agrega su tanda",
        },
    ]


def infraestructura_del_dispositivo(dispositivo, pagina=1):
    """Lo que dibuja la solapa Infraestructura: criticidad, observaciones y registro fotográfico.

    El relevamiento **cuelga del edificio**: un predio compartido muestra los mismos en todas las
    instituciones que lo ocupan. Sin edificio cargado devuelve ``edificios`` vacío y el semáforo
    «Sin edificio cargado», que no es lo mismo que un edificio sin relevar.

    No trae tenencia, servicios, ubicación, habitaciones, plano ni vigencia: no son del MVP.

    Costo fijo, sin importar cuántos relevamientos ni cuántas fotos: los edificios con su última
    realizada y la cantidad de instituciones (1), esas últimas con quien relevó (1), los totales
    de la franja (1), el ``COUNT`` y la página del registro fotográfico (2) y las fotos de la
    página (1). Sin edificio, una sola.
    """

    edificios = list(
        Edificio.objects.filter(
            pk__in=Edificio.dispositivos.through.objects.filter(dispositivo=dispositivo).values("edificio_id")
        )
        .annotate(ultima_id=subconsulta_ultima_realizada(), n_instituciones=Count("dispositivos", distinct=True))
        .only("id", "codigo", "nombre")
        .order_by("nombre", "pk")
    )
    if not edificios:
        return {
            "edificios": [],
            "semaforo": SEMAFOROS[SIN_EDIFICIO],
            "indicadores": [],
            "eventos": [],
            "relevamientos": None,
        }

    ultimas = InspeccionEdificio.objects.select_related("realizada_por").in_bulk(
        [edificio.ultima_id for edificio in edificios if edificio.ultima_id]
    )
    filas = []
    for edificio in edificios:
        ultima = ultimas.get(edificio.ultima_id)
        filas.append(
            {
                "pk": edificio.pk,
                "codigo": edificio.codigo,
                "nombre": edificio.nombre,
                "semaforo": semaforo_de_inspeccion(ultima),
                "ultima": ultima,
                "relevo": _nombre(ultima.realizada_por) if ultima else "",
                "otras_instituciones": edificio.n_instituciones - 1,
            }
        )
    semaforo = semaforo_de_ultimas({fila["pk"]: fila["ultima"] for fila in filas})

    totales = InspeccionEdificio.objects.filter(edificio_id__in=[fila["pk"] for fila in filas]).aggregate(
        realizados=Count("pk", filter=Q(estado=_REALIZADA), distinct=True),
        fotos=Count("fotos", filter=~Q(estado=InspeccionEdificio.Estado.CANCELADA)),
    )

    # Las canceladas no entran: no tienen resultado. La en curso va primero (todavía no tiene fecha).
    consulta = (
        inspecciones_de_dispositivo(dispositivo)
        .annotate(n_fotos=Count("fotos"))
        .order_by(F("realizada_en").desc(nulls_first=True), "-creado", "-pk")
    )
    relevamientos = Paginator(consulta, POR_PAGINA_RELEVAMIENTOS).get_page(pagina)
    ids = [inspeccion.pk for inspeccion in relevamientos]
    fotos_por_inspeccion = defaultdict(list)
    if ids:
        for foto in (
            FotoInspeccion.objects.filter(inspeccion_id__in=ids)
            .only("id", "inspeccion_id", "archivo", "descripcion", "creado")
            .order_by("inspeccion_id", "creado", "pk")
        ):
            fotos_por_inspeccion[foto.inspeccion_id].append(foto)

    con_edificio = len(filas) > 1
    eventos = [
        _evento_de_relevamiento(inspeccion, fotos_por_inspeccion.get(inspeccion.pk, []), con_edificio)
        for inspeccion in relevamientos
    ]

    return {
        "edificios": filas,
        "semaforo": semaforo,
        "indicadores": _indicadores_edilicios(semaforo, filas, totales["realizados"], totales["fotos"]),
        "eventos": eventos,
        "relevamientos": relevamientos,
    }
