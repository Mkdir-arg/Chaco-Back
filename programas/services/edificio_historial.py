"""Solapa «Historial» de la página operativa del edificio (Cambio 571, PR 7 del lote «el edificio como unidad operativa»).

No hay una segunda fuente: es la **auditoría del dispositivo** (``programas.selectors.auditoria_dispositivo``, la misma
que la solapa Historial de la ficha de la institución) acotada a **este edificio y esta institución**. Entra lo que se
deriva del edificio (decisión del PM, 22/11/2026):

* las estadías (ingreso, egreso, cambio y asignación de plaza), por plaza → sector → edificio;
* las reservas de plaza y el alta, el cambio, la baja y el fuera de servicio de las plazas y sectores del edificio;
* las entregas de kits al edificio (solo con ``emergencia.recibir_kit`` sobre él, como la solapa Kits);
* los relevamientos edilicios del edificio;
* las correcciones de la bitácora de las novedades del edificio.

Lo que la traza de la institución no ata a un edificio (legajo, turnos, vínculos de edificios) queda en el historial de
la institución. Las **personas** se nombran solo con ``ciudadano.ver``; un relevamiento sin realizar nombra al agente
solo a quien ve la asignación. El predio compartido no filtra nada de la otra institución: todo se filtra por
``dispositivo`` además de por edificio.

Costo
-----

Constante en el volumen de eventos. La barra de solapas, que muestra el total con cualquier solapa abierta, paga **una**
consulta (:meth:`FeedAuditoria.total`, un ``UNION ALL``). Con la solapa abierta: el alcance de asignación (1), un
``COUNT`` y una lectura por fuente (10 como mucho) y los turnos del dispositivo (1), que sitúan cada evento en su turno
sin consultar por fila.
"""

from django.core.paginator import Paginator

from core.rbac import puede
from programas.selectors.auditoria_dispositivo import FUENTE_INSPECCION, auditoria_del_dispositivo
from programas.services.bitacora import turno_vigente, turnos_activos
from programas.services.detalle_dispositivo import POR_PAGINA_HISTORIAL, _fecha_legible
from programas.services.estadias import CAP_VER_CIUDADANO
from programas.services.inspecciones import edificios_de_dispositivo_con_asignacion_visible


def _feed(user, dispositivo, edificio, *, puede_kits, con_alcance):
    """El feed del edificio. ``con_alcance`` es lo que hace falta solo para dibujar los eventos, no para contarlos."""

    return auditoria_del_dispositivo(
        dispositivo,
        edificios_de_dispositivo_con_asignacion_visible(user, dispositivo) if con_alcance else frozenset(),
        usuario_id=user.pk if getattr(user, "is_authenticated", False) else None,
        puede_ver_personas=con_alcance and puede(user, CAP_VER_CIUDADANO),
        edificio=edificio,
        con_kits=puede_kits,
    )


def contar_eventos_del_edificio(user, dispositivo, edificio, *, puede_kits):
    """El contador de la solapa: una consulta, la misma cifra que muestra el pie de la lista."""

    return _feed(user, dispositivo, edificio, puede_kits=puede_kits, con_alcance=False).total()


def rotulo_del_turno(turno):
    """«Turno tarde»: cómo se nombra un turno en la página del edificio (encabezado e historial)."""

    return f"Turno {turno.nombre.lower()}"


def _turno(momento, turnos):
    situado = turno_vigente(None, momento, turnos=turnos)
    return rotulo_del_turno(situado.turno) if situado is not None else ""


def contexto_historial(user, dispositivo, edificio, pagina, *, puede_kits):
    """La página de eventos de la línea de tiempo y su paginador, listos para ``_linea_tiempo.html``."""

    feed = _feed(user, dispositivo, edificio, puede_kits=puede_kits, con_alcance=True)
    historial = Paginator(feed, POR_PAGINA_HISTORIAL).get_page(pagina)
    turnos = turnos_activos(dispositivo) if historial.paginator.count else []
    eventos = []
    for evento in historial:
        fecha = _fecha_legible(evento["fecha"])
        # El relevamiento lo hace el equipo territorial, que no trabaja en un turno de la institución.
        turno = "" if evento["fuente"] == FUENTE_INSPECCION else _turno(evento["fecha"], turnos)
        eventos.append(
            {
                "cuando": " · ".join(parte for parte in (fecha, turno, evento["quien"]) if parte),
                "titulo": evento["titulo"],
                "detalle": evento["detalle"],
                "tono": evento["tono"],
            }
        )
    return {"historial": historial, "eventos_historial": eventos}
