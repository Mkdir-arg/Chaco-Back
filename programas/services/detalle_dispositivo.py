"""Datos del detalle de un dispositivo (MVP v2, etapa 2 · #692 · P4).

La vista no cuenta ni decide estados: delega acá, y acá tampoco se deciden las cifras de
plazas. Las cifras y el porcentaje de la franja de indicadores y el desglose por sector salen del
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
from django.db.models import Count, Exists, F, OuterRef, Q, Subquery, Value
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.text import Truncator

from core.rbac import puede
from core.services.vencimientos import avisos
from programas.models import Dispositivo, Edificio, Estadia, FotoInspeccion, InspeccionEdificio, Sector
from programas.selectors.auditoria_dispositivo import auditoria_del_dispositivo
from programas.selectors.capacidad_dispositivo import instituciones_del_predio, sectores_por_edificio
from programas.selectors.vencimiento_inspecciones import tiene_relevamiento_vencido
from programas.services.alertas_dispositivos import AMBITO, ICONOS, TONOS
from programas.services.estadias import estado_visible
from programas.services.inspecciones import (
    DIAS_POR_VENCER,
    SEMAFOROS,
    SIN_EDIFICIO,
    SIN_RELEVAR,
    edificios_con_asignacion_visible,
    edificios_de_dispositivo_con_asignacion_visible,
    fotos_para_galeria,
    inspecciones_de_dispositivo,
    inspecciones_visibles,
    semaforo_de_inspeccion,
    semaforo_de_ultimas,
    subconsulta_ultima_realizada,
)
from programas.services.ocupacion import tension_de_ocupacion

POR_PAGINA_ESTADIAS = 25
POR_PAGINA_HISTORIAL = 20
POR_PAGINA_RELEVAMIENTOS = 10

#: Las solapas de P4, en el orden en que se dibujan. «Sectores y plazas» solo existe si el
#: tipo del dispositivo maneja plazas: en los demás, `?tab=sectores` no lleva a ninguna parte.
SOLAPAS = ("datos", "sectores", "estadias", "infraestructura", "equipo", "historial")
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
    Dispositivo.Estado.RECHAZADO: "Fue rechazado en la validación: no admite ingresos. Corregí los datos y volvé a enviarlo a validación.",
    Dispositivo.Estado.INACTIVO: "Está inactivo: no admite ingresos mientras siga así.",
    Dispositivo.Estado.CERRADO: "Está cerrado: el legajo se conserva, pero no admite ingresos ni otras operaciones.",
}


def aviso_sin_ingresos(dispositivo):
    """El texto de la alerta del encabezado, o vacío si el dispositivo está activo."""

    return _AVISO_SIN_INGRESOS.get(dispositivo.estado, "")


def indicadores_de_plazas(conteo, *, tipo=None):
    """Cifras y semáforo de la franja, derivados del mismo ``Conteo`` que el mapa."""

    tension = tension_de_ocupacion(conteo, tipo=tipo)

    return [
        {
            "etiqueta": "Ocupación",
            "valor": f"{tension.porcentaje} %" if tension.hay_cifra else "—",
            "icono": "fa-chart-simple",
            "tono": tension.tono,
            "nota": f"{tension.etiqueta} · {conteo.ocupadas} de {conteo.operativas} operativas"
            if tension.hay_cifra
            else "Sin plazas operativas o sin ocupación calculable",
        },
        {
            "etiqueta": "Plazas operativas",
            "valor": conteo.operativas,
            "icono": "fa-bed",
            "nota": f"{conteo.totales} cargadas · {conteo.fuera_de_servicio} fuera de servicio",
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


def estadias_del_dispositivo(dispositivo, *, estado=FILTRO_ALOJADAS, sector=None, pagina=1):
    """La página de estadías del dispositivo, lista para dibujar.

    Trae a la persona y a la plaza con su sector en la misma consulta y solo las columnas
    que la tabla muestra. A cada estadía de la página le deja ``estado_texto`` y ``tono`` (de
    la tabla única de `programas.services.estadias`), para que el template no decida nada.
    """

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


def eventos_de_historial(dispositivo, pagina=1, usuario=None):
    """La página de la auditoría del dispositivo como eventos de la línea de tiempo (más nuevo primero).

    Junta las cuatro trazas —legajo, estadías, correcciones de bitácora y relevamientos
    edilicios— en una sola lista (``programas.selectors.auditoria_dispositivo``).

    ``usuario`` decide si se nombra a las personas (``ciudadano.ver``) y si un relevamiento **sin realizar** nombra al
    agente. El detalle de esas trazas se escribió legible con el nombre adentro, así que la
    regla de `inspecciones.ve_la_asignacion` hay que volver a aplicarla acá; el alcance se
    resuelve en **una** consulta para toda la página.
    Sin usuario no se expone la identidad de las personas; la vista siempre pasa quién mira.
    """

    con_asignacion = edificios_de_dispositivo_con_asignacion_visible(usuario, dispositivo)
    usuario_id = usuario.pk if getattr(usuario, "is_authenticated", False) else None
    feed = auditoria_del_dispositivo(
        dispositivo,
        con_asignacion,
        usuario_id=usuario_id,
        puede_ver_personas=usuario is not None and puede(usuario, "ciudadano.ver"),
    )
    pagina_de_eventos = Paginator(feed, POR_PAGINA_HISTORIAL).get_page(pagina)
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


def _evento_de_relevamiento(inspeccion, fotos, *, ve_asignacion=False, enlace=""):
    """Una entrada de la línea de tiempo por relevamiento, con su tanda de fotos adentro.

    Lo que pasó va en el texto, no en el color. ``fotos`` y ``total_fotos`` son el opcional de
    `components/_linea_tiempo.html` que dibuja la galería dentro del evento, y ``enlace`` el
    que la convierte en el «Ver» del historial de relevamientos de P19.

    ``ve_asignacion`` lo decide `programas.services.inspecciones.ve_la_asignacion`: **la
    institución relevada no ve el nombre del agente** de un relevamiento en curso, solo que
    está en curso.
    """

    rotulos = ", ".join(list(dict.fromkeys(foto.descripcion for foto in fotos if foto.descripcion))[:8])
    galeria = {
        "pk": inspeccion.pk,
        # P19 rotula la tanda por el relevamiento; el informe conserva su contrato propio.
        "fotos": [
            {**foto, "fecha": inspeccion.realizada_en or foto["fecha"]}
            for foto in fotos_para_galeria(inspeccion, fotos)
        ],
        "total_fotos": inspeccion.n_fotos,
        "enlace": enlace,
        "enlace_texto": "Ver informe",
    }
    if inspeccion.estado != _REALIZADA:
        detalle = _cantidad_de_fotos(inspeccion.n_fotos).lower()
        agente = f" · asignado a {_nombre(inspeccion.asignado_a)}" if ve_asignacion else ""
        return {
            "cuando": f"en curso{agente}",
            "titulo": "Relevamiento en curso",
            "detalle": f"{detalle} · {rotulos}" if rotulos else detalle,
            **galeria,
        }
    semaforo = semaforo_de_inspeccion(inspeccion)
    evento = {
        "cuando": f"{_fecha(inspeccion.realizada_en)} · relevamiento · {_nombre(inspeccion.realizada_por)}",
        "titulo": _cantidad_de_fotos(inspeccion.n_fotos),
        "detalle": rotulos,
        "badge": semaforo.texto,
        "badge_tono": semaforo.tono,
        # Lo que el evento plegable de `_linea_tiempo` muestra al abrirse.
        "observaciones": (inspeccion.observaciones or "").strip(),
        **galeria,
    }
    if semaforo.tono in _TONOS_CON_COLOR:
        evento["tono"] = semaforo.tono
    if inspeccion.revisado_en is not None:
        evento["badge"] = "Revisado"
        evento["badge_tono"] = "success"
        evento["detalle"] = " · ".join(parte for parte in (rotulos, semaforo.texto) if parte)
        evento["cuando"] += (
            f" · revisado por {_nombre(inspeccion.revisado_por)} el {_fecha_legible(inspeccion.revisado_en)}"
        )
    return evento


#: Los estados del filtro de la solapa, en el orden en que se ofrecen y en el que se ordenan las
#: tarjetas (del más grave al mejor, «sin relevar» al final): clave, rótulo y criticidad de la última
#: realizada que la define (``None`` = ninguna realizada). El rótulo es el del semáforo
#: (`SEMAFOROS`): una sola redacción del estado para el filtro, la tarjeta y el badge de la solapa.
ESTADOS_EDILICIOS = (
    ("CRITICO", SEMAFOROS[InspeccionEdificio.Criticidad.ALTA].texto, InspeccionEdificio.Criticidad.ALTA),
    ("REGULAR", SEMAFOROS[InspeccionEdificio.Criticidad.MEDIA].texto, InspeccionEdificio.Criticidad.MEDIA),
    ("BUENO", SEMAFOROS[InspeccionEdificio.Criticidad.BAJA].texto, InspeccionEdificio.Criticidad.BAJA),
    ("SIN_RELEVAR", SEMAFOROS[SIN_RELEVAR].texto, None),
)
_CLAVES_ESTADO = {clave for clave, _texto, _criticidad in ESTADOS_EDILICIOS}
_ORDEN_ESTADO = {clave: orden for orden, (clave, _texto, _criticidad) in enumerate(ESTADOS_EDILICIOS)}
#: Cuántos sectores nombra la tarjeta antes de decir «y N más»; la ficha los lista todos.
_SECTORES_EN_TARJETA = 4
#: Largo de la observación en la tarjeta; el texto entero está en la ficha.
_LARGO_OBSERVACION = 140
#: Tarjetas que dibuja la grilla (las más graves primero; el filtro por estado muestra el resto) y chips de
#: edificio de la ficha (`chips_enlace.md`: hasta 6 en una fila; el resto queda detrás de «Los N edificios»).
_TOPE_TARJETAS = 60
_TOPE_CHIPS = 6


def _plural(cantidad, singular, plural):
    return f"{cantidad} {singular if cantidad == 1 else plural}"


def _clave_estado(ultima):
    """El estado del filtro de un edificio: sale de la criticidad de la última realizada."""

    if ultima is None:
        return "SIN_RELEVAR"
    for clave, _texto, criticidad in ESTADOS_EDILICIOS:
        if criticidad is not None and ultima.criticidad == criticidad:
            return clave
    return ""


def _aviso_de_vencimiento(vencido, vence_el, hoy):
    """«Vencido» o «Vence en N días» de un edificio, o ``None``.

    Vencido es la regla del selector compartido (relevamiento en curso con fecha pasada); «por vencer»
    usa la misma ventana que el listado de relevamientos (``DIAS_POR_VENCER``).
    """

    if vencido:
        return {"texto": "Vencido", "tono": "danger"}
    if vence_el is None:
        return None
    dias = (vence_el - hoy).days
    if dias > DIAS_POR_VENCER:
        return None
    return {"texto": "Vence hoy" if dias <= 0 else f"Vence en {_plural(dias, 'día', 'días')}", "tono": "warning"}


def _predio(otras, visibles):
    """Con quién comparte el inmueble, sin nombrar a quien el usuario no puede ver."""

    if otras <= 0:
        return "Solo esta institución"
    if otras == 1 and len(visibles) == 1:
        return f"Compartido con {visibles[0]['nombre']}"
    return f"Compartido con {_plural(otras, 'institución', 'instituciones')}"


def _sectores_en_texto(sectores):
    if not sectores:
        return "Todavía no hay sectores"
    nombres = [f"{sector['nombre']} ({sector['plazas']})" for sector in sectores[:_SECTORES_EN_TARJETA]]
    resto = len(sectores) - _SECTORES_EN_TARJETA
    if resto > 0:
        nombres.append(f"y {resto} más")
    return " · ".join(nombres)


def _resumen_del_listado(filas):
    """El encabezado del listado: cuántos edificios, el más grave si hay uno que lo merezca y las cuentas."""

    # `filas` ya viene del más grave al mejor: el primero es el más grave, y solo se nombra si
    # es crítico o regular (que «el más grave» sea «Bueno» no le sirve a nadie).
    peor = filas[0]
    mas_grave = peor if peor["estado"]["clave"] in ("CRITICO", "REGULAR") else None
    relevados = [fila for fila in filas if fila["estado"]["clave"] != "SIN_RELEVAR"]
    compartidos = sum(1 for fila in filas if fila["otras_instituciones"] > 0)
    sin_relevar = len(filas) - len(relevados)
    partes = []
    if compartidos:
        partes.append(
            "1 edificio es un predio compartido con otras instituciones"
            if compartidos == 1
            else f"{compartidos} edificios son predios compartidos con otras instituciones"
        )
    if sin_relevar:
        if partes:
            partes.append("1 todavía no se relevó" if sin_relevar == 1 else f"{sin_relevar} todavía no se relevaron")
        else:
            partes.append(
                "1 edificio todavía no se relevó"
                if sin_relevar == 1
                else f"{sin_relevar} edificios todavía no se relevaron"
            )
    return {
        "titulo": f"Funciona en {_plural(len(filas), 'edificio', 'edificios')}",
        "mas_grave": mas_grave,
        "todos_buenos": mas_grave is None
        and bool(relevados)
        and all(f["estado"]["clave"] == "BUENO" for f in relevados),
        # Las partes que aplican, en una frase: «A y B.» o «A.»; vacía si ninguna aplica.
        "cuentas": (" y ".join(partes) + ".") if partes else "",
    }


#: Lo que devuelve `infraestructura_del_dispositivo` en cualquier modo; cada modo pisa lo suyo.
_RESPUESTA_BASE = {
    "modo": "",
    "edificios": [],
    "n_edificios": 0,
    "semaforo": None,
    "listado": [],
    "n_sin_mostrar": 0,
    "filtros": [],
    "estado": "",
    "resumen": None,
    "chips": [],
    "eventos": [],
    "relevamientos": None,
    "viendo": None,
    "sin_edificio": None,
    "url_listado": "",
    "qs_paginacion": "",
}


def _fila_de_edificio(
    edificio, *, ultima, sectores, del_predio, total, dispositivo, base, hoy, con_ocupacion, puede_editar
):
    """Una fila de `infraestructura_del_dispositivo`: lo que la tarjeta y la ficha dibujan de un edificio.

    ``ultima`` trae ``con_detalle`` (alcance de inspección, Cambio 428): sin él la fila no lleva criticidad,
    observaciones, quién relevó ni conteos. Las URL las arma esta función con ``reverse``.
    """

    ve_detalle = ultima is None or ultima.con_detalle
    semaforo_estado = semaforo_de_inspeccion(ultima)
    otras = edificio.n_instituciones - 1
    realizados = total.get("realizados", 0)
    observaciones = (ultima.observaciones or "").strip() if ultima else ""
    if ultima is None:
        observacion = "Todavía no se relevó este edificio."
    elif ve_detalle:
        observacion = Truncator(observaciones).chars(_LARGO_OBSERVACION) or "Sin observaciones."
    else:
        observacion = ""
    return {
        "pk": edificio.pk,
        "sectores": sectores,
        "sectores_texto": _sectores_en_texto(sectores),
        "n_plazas": sum(sector["plazas"] for sector in sectores),
        "n_ocupadas": sum(sector["ocupadas"] for sector in sectores) if con_ocupacion else None,
        "codigo": edificio.codigo,
        "nombre": edificio.nombre,
        "domicilio": edificio.domicilio_completo,
        "latitud": edificio.latitud,
        "longitud": edificio.longitud,
        "instituciones": del_predio,
        # El estado de la tarjeta es el de la última realizada; «Vencido» y «Vence en N días» van aparte.
        "estado": {"clave": _clave_estado(ultima), "texto": semaforo_estado.texto, "tono": semaforo_estado.tono},
        "vencido": bool(edificio.vencido),
        "aviso": _aviso_de_vencimiento(edificio.vencido, edificio.vence_el, hoy),
        "ultima": ultima,
        "ve_detalle": ve_detalle,
        "relevo": _nombre(ultima.realizada_por) if ultima and ve_detalle else "",
        "fecha_texto": (
            f"Relevado el {_fecha(ultima.realizada_en)}" if ultima else f"Cargado el {_fecha(edificio.creado)}"
        ),
        "observacion": observacion,
        "otras_instituciones": otras,
        "n_instituciones": otras + 1,
        "predio": _predio(otras, [i for i in del_predio if i["pk"] != dispositivo.pk]),
        # Sin alcance no se cuenta lo que no se puede abrir: ni relevamientos ni fotos.
        "conteo": (
            f"{_plural(realizados, 'relevamiento', 'relevamientos')} · {_plural(total.get('fotos', 0), 'foto', 'fotos')}"
            if realizados
            else "Sin relevamientos"
        ),
        "con_conteo": ve_detalle,
        "url_ver": f"{base}&ver_edificio={edificio.pk}",
        "url_editar": f"{base}&edificio={edificio.pk}" if puede_editar else "",
        "url_desvincular": (
            reverse("dispositivos:edificio_desvincular", args=[dispositivo.pk, edificio.pk]) if puede_editar else ""
        ),
    }


def infraestructura_del_dispositivo(
    dispositivo, pagina=1, usuario=None, edificio_id=None, estado=None, ocupadas_por_sector=None, puede_editar=False
):
    """Lo que dibuja la solapa Infraestructura: tarjetas por edificio y, al abrir uno, su ficha (Cambio 439).

    El relevamiento **cuelga del edificio**: un predio compartido muestra los mismos en todas las
    instituciones que lo ocupan. Sin edificio cargado devuelve ``modo="vacio"`` y el semáforo
    «Sin edificio cargado», que no es lo mismo que un edificio sin relevar.

    ``modo`` es lo que la pantalla dibuja:

    - ``"vacio"``: ningún edificio.
    - ``"listado"``: dos o más edificios y ninguno abierto. ``edificios`` va del más grave al mejor (la
      última realizada manda; a igual estado, el que tiene un relevamiento vencido primero; «sin relevar» al
      final), ``listado`` es lo que deja el filtro ``estado`` (``CRITICO``, ``REGULAR``, ``BUENO``,
      ``SIN_RELEVAR``; otro valor no filtra), ``filtros`` los chips con su conteo y ``resumen`` el
      encabezado. El registro fotográfico no se pide.
    - ``"ficha"``: un edificio abierto (``viendo``), por ``edificio_id`` o porque es el único. Trae su registro
      paginado (``eventos``, ``relevamientos``) y los ``chips`` para pasar a otro edificio.

    Cada fila trae sus sectores activos con plazas y, si el llamador pasó ``ocupadas_por_sector``
    (``{sector_id: ocupadas}``, del censo que la pantalla ya calculó: la ocupación sale de las estadías,
    nunca se tipea), cuántas están ocupadas. ``sin_edificio`` junta los sectores que todavía no tienen edificio.

    Incluye coordenadas del edificio y las instituciones visibles del predio. No trae tenencia, servicios,
    habitaciones, plano ni vigencia: no son del MVP.

    ``puede_editar`` (``dispositivo.editar`` con alcance, lo resuelve la vista) es lo que agrega a cada fila
    ``url_editar`` y ``url_desvincular``; sin él van vacías y la tarjeta no ofrece esas acciones. Todas las URL de
    la solapa (``url_ver``, ``url_listado``, ``qs_paginacion``) las arma este servicio: el template no concatena.

    ``usuario`` decide **de quién** se muestra el relevamiento en curso: sin él —o con quien solo opera la
    institución— el evento dice «en curso» y nada más (`programas.services.inspecciones.ve_la_asignacion`).
    Cambio 428: la criticidad, las observaciones, quién relevó y las fotos son del informe; sin alcance de
    inspección (`ve_detalle` falso) queda el semáforo y la fecha.

    Costo fijo, sin importar cuántos edificios, relevamientos ni fotos: los edificios con su última realizada,
    el próximo vencimiento y la cantidad de instituciones (1), las instituciones visibles (1), las últimas con
    quien relevó (1), los sectores con sus plazas (1) y los totales por edificio (1). La ficha suma el ``COUNT``
    y la página del registro (2) y las fotos de la página (1); una más, no una por fila, solo si la página trae
    algún relevamiento en curso y el usuario podría coordinar el edificio. Sin edificio, una sola.
    """

    hoy = timezone.localdate()
    base = reverse("dispositivos:detalle", args=[dispositivo.pk]) + "?tab=infraestructura"
    edificios = list(
        Edificio.objects.filter(
            pk__in=Edificio.dispositivos.through.objects.filter(dispositivo=dispositivo).values("edificio_id")
        )
        .annotate(
            ultima_id=subconsulta_ultima_realizada(),
            n_instituciones=Count("dispositivos", distinct=True),
            vencido=tiene_relevamiento_vencido(),
            vence_el=Subquery(
                InspeccionEdificio.objects.filter(edificio=OuterRef("pk"), estado=InspeccionEdificio.Estado.ASIGNADA)
                .order_by("fecha_vencimiento", "pk")
                .values("fecha_vencimiento")[:1]
            ),
        )
        # El domicilio normalizado viaja en la MISMA consulta: leerlo
        # después desde el objeto sería una consulta por edificio, porque `only()` los deja
        # diferidos (el N+1 que este `only` está puesto para evitar, no para provocar).
        .only(
            "id",
            "codigo",
            "nombre",
            "calle",
            "numero",
            "piso_departamento",
            "localidad",
            "provincia",
            "codigo_postal",
            "latitud",
            "longitud",
            "creado",
        )
        .order_by("nombre", "pk")
    )
    if not edificios:
        return {**_RESPUESTA_BASE, "modo": "vacio", "semaforo": SEMAFOROS[SIN_EDIFICIO], "url_listado": base}

    pedido = None
    if len(edificios) == 1:
        pedido = edificios[0].pk
    else:
        try:
            pedido = int(edificio_id)
        except (TypeError, ValueError):
            pedido = None
        if pedido not in {edificio.pk for edificio in edificios}:
            pedido = None

    instituciones = instituciones_del_predio(usuario, [edificio.pk for edificio in edificios])
    # Cambio 428: la criticidad, las observaciones y quién relevó son del informe, que se abre solo
    # por `inspecciones_visibles`. Quien ve el dispositivo sin ese alcance recibe el semáforo y la
    # fecha, nada más. Va como `Exists` en la misma consulta de las últimas, sin una más; sin
    # usuario, todo como siempre.
    visibles = Exists(inspecciones_visibles(usuario).filter(pk=OuterRef("pk"))) if usuario is not None else Value(True)
    ultimas = (
        InspeccionEdificio.objects.select_related("realizada_por")
        .annotate(con_detalle=visibles)
        .in_bulk([edificio.ultima_id for edificio in edificios if edificio.ultima_id])
    )
    sectores_de, sectores_sin_edificio = sectores_por_edificio(dispositivo)
    # Los relevamientos realizados y las fotos de CADA edificio, en una sola consulta agrupada.
    totales = {
        fila["edificio_id"]: fila
        for fila in InspeccionEdificio.objects.filter(edificio_id__in=[edificio.pk for edificio in edificios])
        .values("edificio_id")
        .annotate(
            realizados=Count("pk", filter=Q(estado=_REALIZADA), distinct=True),
            fotos=Count("fotos", filter=~Q(estado=InspeccionEdificio.Estado.CANCELADA)),
        )
    }

    filas = [
        _fila_de_edificio(
            edificio,
            ultima=ultimas.get(edificio.ultima_id),
            sectores=[
                {
                    **sector,
                    "ocupadas": None if ocupadas_por_sector is None else ocupadas_por_sector.get(sector["pk"], 0),
                }
                for sector in sectores_de.get(edificio.pk, [])
            ],
            del_predio=instituciones.get(edificio.pk, []),
            total=totales.get(edificio.pk, {}),
            dispositivo=dispositivo,
            base=base,
            hoy=hoy,
            con_ocupacion=ocupadas_por_sector is not None,
            puede_editar=puede_editar,
        )
        for edificio in edificios
    ]
    filas.sort(
        key=lambda fila: (
            _ORDEN_ESTADO.get(fila["estado"]["clave"], len(_ORDEN_ESTADO)),
            0 if fila["vencido"] else 1,
            fila["nombre"].lower(),
            fila["pk"],
        )
    )
    semaforo = semaforo_de_ultimas(
        {fila["pk"]: fila["ultima"] for fila in filas},
        vencidos={edificio.pk for edificio in edificios if edificio.vencido},
    )
    # «Sin edificio» solo cuando no hay una ficha abierta entre varios: al abrir uno, la jerarquía es la de ese.
    sin_edificio = (
        {
            "sectores": sectores_sin_edificio,
            "n_plazas": sum(sector["plazas"] for sector in sectores_sin_edificio),
            "titulo": (
                "1 sector todavía no tiene edificio"
                if len(sectores_sin_edificio) == 1
                else f"{len(sectores_sin_edificio)} sectores todavía no tienen edificio"
            ),
            "texto": "; ".join(
                f"{sector['nombre']} · {_plural(sector['plazas'], 'plaza', 'plazas')}"
                for sector in sectores_sin_edificio
            )
            + ". Hasta asignarlos no figuran en ningún edificio.",
            # «Asignar edificio» abre la edición del primero; el resto se asigna de a uno, igual.
            "primero_pk": sectores_sin_edificio[0]["pk"],
            "url_asignar": reverse("dispositivos:sectores", args=[dispositivo.pk])
            + f"?sector={sectores_sin_edificio[0]['pk']}",
        }
        if sectores_sin_edificio and (pedido is None or len(filas) == 1)
        else None
    )

    if pedido is None:
        clave = estado if estado in _CLAVES_ESTADO else ""
        filtros = [{"texto": "Todos", "n": len(filas), "url": base, "activo": not clave}] + [
            {
                "texto": texto,
                "n": sum(1 for fila in filas if fila["estado"]["clave"] == codigo),
                "url": f"{base}&estado_edificio={codigo}",
                "activo": clave == codigo,
            }
            for codigo, texto, _criticidad in ESTADOS_EDILICIOS
        ]
        # La grilla tiene tope: del más grave al mejor, y el filtro por estado muestra el resto.
        elegidos = [fila for fila in filas if not clave or fila["estado"]["clave"] == clave]
        return {
            **_RESPUESTA_BASE,
            "modo": "listado",
            "edificios": filas,
            "n_edificios": len(filas),
            "semaforo": semaforo,
            "listado": elegidos[:_TOPE_TARJETAS],
            "n_sin_mostrar": max(len(elegidos) - _TOPE_TARJETAS, 0),
            "filtros": filtros,
            "estado": clave,
            "resumen": _resumen_del_listado(filas),
            "sin_edificio": sin_edificio,
            "url_listado": base,
        }

    viendo = next(fila for fila in filas if fila["pk"] == pedido)
    # «Los N edificios» vuelve al listado y es el primer chip; después, hasta `_TOPE_CHIPS` edificios (el abierto
    # siempre entra, aunque no esté entre los primeros). El resto se alcanza desde el listado.
    nombres = [fila for fila in filas if fila["pk"] != pedido][: _TOPE_CHIPS - 1]
    nombres.append(viendo)
    nombres.sort(key=filas.index)
    chips = [{"texto": f"Los {len(filas)} edificios", "url": base, "activo": False, "icono": "fa-arrow-left"}] + [
        {
            "texto": fila["nombre"],
            "url": fila["url_ver"],
            "activo": fila["pk"] == pedido,
            "tono": fila["estado"]["tono"],
            "estado": fila["estado"]["texto"],
        }
        for fila in nombres
    ]

    # Las canceladas no entran: no tienen resultado. La en curso va primero (todavía no tiene fecha).
    inspecciones = inspecciones_de_dispositivo(dispositivo).filter(edificio_id=pedido)
    if usuario is not None:
        # Cambio 422: el registro enlaza al informe y a las fotos, y los dos se abren solo por
        # `inspecciones_visibles`. Quien llega al detalle por leer todos los dispositivos
        # (`ver_todos`) sin operar ni coordinar la institución no ve los relevamientos.
        inspecciones = inspecciones.filter(pk__in=inspecciones_visibles(usuario).values("pk"))
    consulta = inspecciones.annotate(n_fotos=Count("fotos")).order_by(
        F("realizada_en").desc(nulls_first=True), "-creado", "-pk"
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

    # El alcance se resuelve para toda la página y solo si hay algo en curso que lo necesite:
    # preguntarlo por fila sería un N+1 proporcional a la página.
    en_curso = [inspeccion for inspeccion in relevamientos if inspeccion.estado != _REALIZADA]
    propios = {inspeccion.pk for inspeccion in en_curso if inspeccion.asignado_a_id == getattr(usuario, "pk", None)}
    coordinados = edificios_con_asignacion_visible(usuario, [i.edificio_id for i in en_curso]) if en_curso else set()
    eventos = [
        _evento_de_relevamiento(
            inspeccion,
            fotos_por_inspeccion.get(inspeccion.pk, []),
            ve_asignacion=inspeccion.pk in propios or inspeccion.edificio_id in coordinados,
            enlace=reverse("dispositivos:relevamiento_informe", args=[inspeccion.pk])
            + f"?dispositivo={dispositivo.pk}",
        )
        for inspeccion in relevamientos
    ]

    return {
        **_RESPUESTA_BASE,
        "modo": "ficha",
        # Al abrir uno, la jerarquía es la de ese; los otros solo aparecen como chips (`n_edificios` los cuenta).
        "edificios": [viendo],
        "n_edificios": len(filas),
        "semaforo": semaforo,
        "chips": chips if len(filas) > 1 else [],
        "eventos": eventos,
        "relevamientos": relevamientos,
        "viendo": viendo,
        "sin_edificio": sin_edificio,
        "url_listado": base,
        "qs_paginacion": f"tab=infraestructura&ver_edificio={pedido}",
    }
