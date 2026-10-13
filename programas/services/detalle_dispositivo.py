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
la plaza, así que **no hay una consulta por fila**.
"""

from django.core.paginator import Paginator
from django.utils import timezone
from django.utils.formats import date_format

from programas.models import Dispositivo, Estadia, Sector
from programas.services.estadias import estado_visible

POR_PAGINA_ESTADIAS = 25
POR_PAGINA_HISTORIAL = 20

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


def eventos_de_historial(dispositivo, pagina=1):
    """La página del historial de validación como eventos de la línea de tiempo (más nuevo primero)."""

    trazas = dispositivo.trazas.select_related("usuario").order_by("-creado_en", "-id")
    pagina_de_trazas = Paginator(trazas, POR_PAGINA_HISTORIAL).get_page(pagina)
    eventos = []
    for traza in pagina_de_trazas:
        cuando = date_format(timezone.localtime(traza.creado_en), "d/m/Y H:i")
        detalle = f"{traza.estado_anterior_legible} → {traza.estado_nuevo_legible}"
        if traza.detalle_legible:
            detalle = f"{detalle} · {traza.detalle_legible}"
        eventos.append(
            {
                "cuando": f"{cuando} · {traza.usuario or 'Sistema'}",
                "titulo": traza.accion,
                "detalle": detalle,
            }
        )
    return pagina_de_trazas, eventos
