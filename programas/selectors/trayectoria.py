"""Trayectoria de una persona en el programa Dispositivos (solapa del legajo, P16).

Lee de `Estadia` —la permanencia de la persona en cada dispositivo— y **no filtra por el
alcance de quien mira**: cualquiera del programa ve la trayectoria completa, abiertas y
cerradas, en cualquier institución de la red (decisión §4.11 de la propuesta v2). Lo que
limita lo que se ve adentro es la sensibilidad de cada sección, no el alcance.

Sensibilidad en el MVP
----------------------

Esta lectura solo trae datos de la estadía misma: institución, tipo, fechas, estado y
motivo de egreso **del catálogo** (`Estadia.motivo`). Las observaciones del egreso
(`Estadia.motivo_egreso`) son texto libre, pueden traer datos sensibles y **no** van acá.

Ninguno de esos datos es una sección sensible, porque las secciones sensibles son las
de la ficha de ingreso (salud, consumo, violencia), que todavía no se guardan contra la
estadía. **Cuando existan, no se agregan acá:** la ficha pasa por la sección bloqueada del
arquetipo Revisión, que decide `bloqueada` por capacidad en la vista y no manda los datos
al template. Que esta función no devuelva campos de la ficha es lo que garantiza que no
puedan filtrarse; el test de la solapa lo afirma.

Es una vista de lectura. El enlace al detalle exige `ciudadano.ver` y el mismo alcance
de `dispositivo.ver` que P7; se resuelve para toda la página, nunca por fila.
"""

from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Q
from django.urls import reverse
from django.utils import timezone

from core import rbac
from programas.models import Estadia
from programas.services.dispositivos import dispositivos_visibles
from programas.services.estadias import estado_visible

#: Estadías por página. La trayectoria de una persona crece sin techo; el tope es de la vista.
POR_PAGINA = 10


def _ubicacion(estadia):
    """«Pabellón A · A-02», o vacío si el tipo de dispositivo no maneja plaza identificable."""
    if estadia.plaza_id is None:
        return ""
    return f"{estadia.plaza.sector.nombre} · {estadia.plaza.codigo}"


def _fila(estadia):
    # Texto y tono salen de la tabla única de `programas.services.estadias`, la misma del detalle del dispositivo.
    estado, tono = estado_visible(estadia)
    fila = {
        "dispositivo": estadia.dispositivo.nombre,
        "tipo": estadia.dispositivo.tipo.nombre,
        "ubicacion": _ubicacion(estadia),
        "ingreso": estadia.fecha_ingreso,
        "egreso": estadia.fecha_egreso,
        "estado": estado,
        "tono": tono,
        "motivo": estadia.motivo.nombre if estadia.motivo_id else "",
    }
    if getattr(estadia, "puede_ver_detalle", False):
        fila["url_estadia"] = reverse("dispositivos:estadia_detalle", args=[estadia.dispositivo_id, estadia.pk])
    return fila


def _texto_hoy(estadia):
    """La frase de la alerta «Hoy»: dónde está alojada la persona y desde cuándo."""
    if estadia is None:
        return "sin estadía activa en la red."
    ubicacion = _ubicacion(estadia)
    donde = f"{estadia.dispositivo.nombre} ({ubicacion})" if ubicacion else estadia.dispositivo.nombre
    desde = timezone.localtime(estadia.fecha_ingreso).strftime("%d/%m/%Y")
    return f"alojada en {donde} desde el {desde}."


def trayectoria_de(ciudadano, pagina=None, *, usuario=None):
    """La trayectoria de `ciudadano`: página de filas, contadores y la estadía de hoy.

    Tres consultas, sin importar cuántas estadías tenga: el COUNT del paginador, la
    página con `dispositivo`, su tipo, la plaza y su sector ya traídos, y la estadía
    abierta. El alcance del detalle se anota con EXISTS en la lectura de la página,
    sin otra consulta por estadía. Los contadores salen del COUNT, no del recorte.
    """
    base = Estadia.objects.filter(ciudadano=ciudadano).select_related("dispositivo__tipo", "plaza__sector", "motivo")
    activa = base.activas().first()
    if usuario is not None and rbac.puede(usuario, "ciudadano.ver"):
        base = base.annotate(
            puede_ver_detalle=Exists(dispositivos_visibles(usuario).filter(pk=OuterRef("dispositivo_id")))
        )
    paginador = Paginator(base, POR_PAGINA)
    pagina_obj = paginador.get_page(pagina)
    filas = [_fila(e) for e in pagina_obj.object_list]
    # El `Page` solo lleva la paginación (número, contador, anterior/siguiente): se le
    # cambian las instancias por las filas ya recortadas, así que ni un
    # `{% for e in page_obj %}` puede tocar las observaciones del egreso, la clave de
    # alojamiento ni quién registró cada movimiento.
    pagina_obj.object_list = filas
    return {
        "page_obj": pagina_obj,
        "filas": filas,
        "n_estadias": paginador.count,
        "hay_activa": activa is not None,
        "hoy": _texto_hoy(activa),
    }


def resumen_de_estadias(ciudadano):
    """`(total, abiertas)` de la persona en **una** consulta: el contador y el subtítulo de la solapa."""
    datos = Estadia.objects.filter(ciudadano=ciudadano).aggregate(
        total=Count("pk"), abiertas=Count("pk", filter=Q(estado=Estadia.Estado.ACTIVA))
    )
    return datos["total"], datos["abiertas"]
