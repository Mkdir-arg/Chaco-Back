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

Es una vista de lectura: no devuelve URLs ni capacidades de operación.
"""

from django.core.paginator import Paginator
from django.utils import timezone

from programas.models import Estadia

#: Estadías por página. La trayectoria de una persona crece sin techo; el tope es de la vista.
POR_PAGINA = 10

#: Tono del badge de cada estado. Lo decide la vista, no el template.
_TONO_ESTADO = {
    Estadia.Estado.ACTIVA: "info",
    Estadia.Estado.EGRESADA: "gray",
}


def _ubicacion(estadia):
    """«Pabellón A · A-02», o vacío si el tipo de dispositivo no maneja plaza identificable."""
    if estadia.plaza_id is None:
        return ""
    return f"{estadia.plaza.sector.nombre} · {estadia.plaza.codigo}"


def _fila(estadia):
    return {
        "dispositivo": estadia.dispositivo.nombre,
        "tipo": estadia.dispositivo.tipo.nombre,
        "ubicacion": _ubicacion(estadia),
        "ingreso": estadia.fecha_ingreso,
        "egreso": estadia.fecha_egreso,
        "estado": estadia.get_estado_display(),
        "tono": _TONO_ESTADO.get(estadia.estado, "gray"),
        "motivo": estadia.motivo.nombre if estadia.motivo_id else "",
    }


def _texto_hoy(estadia):
    """La frase de la alerta «Hoy»: dónde está alojada la persona y desde cuándo."""
    if estadia is None:
        return "sin estadía activa en la red."
    ubicacion = _ubicacion(estadia)
    donde = f"{estadia.dispositivo.nombre} ({ubicacion})" if ubicacion else estadia.dispositivo.nombre
    desde = timezone.localtime(estadia.fecha_ingreso).strftime("%d/%m/%Y")
    return f"alojada en {donde} desde el {desde}."


def trayectoria_de(ciudadano, pagina=None):
    """La trayectoria de `ciudadano`: página de filas, contadores y la estadía de hoy.

    Tres consultas, sin importar cuántas estadías tenga: el COUNT del paginador, la
    página con `dispositivo`, su tipo, la plaza y su sector ya traídos, y la estadía
    abierta. Los contadores salen del COUNT, no de `len()` sobre el recorte.
    """
    base = Estadia.objects.filter(ciudadano=ciudadano).select_related("dispositivo__tipo", "plaza__sector", "motivo")
    paginador = Paginator(base, POR_PAGINA)
    pagina_obj = paginador.get_page(pagina)
    activa = base.activas().first()
    return {
        "page_obj": pagina_obj,
        "filas": [_fila(e) for e in pagina_obj.object_list],
        "n_estadias": paginador.count,
        "hay_activa": activa is not None,
        "hoy": _texto_hoy(activa),
    }


def cantidad_de_estadias(ciudadano):
    """Cuántas estadías tiene la persona (abiertas y cerradas): el contador de la solapa."""
    return Estadia.objects.filter(ciudadano=ciudadano).count()
