"""Solapa «Kits» de la página operativa del edificio: tabla de entregas y detalle con recepción (Cambio 568, PR 3).

Las entregas de **este** edificio y de **esta** institución, nada más: la lista sale de ``entregas_de`` (alcance por
edificio de quien mira) y se acota con ``edificio=`` **exacto**. Una entrega sin edificio (``edificio=NULL``, las
anteriores al Cambio 523) no aparece en ningún edificio: se ve desde Emergencia · Kits de la institución, con alcance
a toda ella (decisión del PM, 22/11/2026). La de otro edificio, la de otra institución del predio y la sin edificio
dan el mismo ``None`` (404 en la vista) que un id inexistente.

La recepción no se reescribe: el formulario del detalle publica a ``RecibirKitView`` (servicio ``recibir_entrega``),
que vuelve a esta solapa con el ``next`` del formulario.

Costo
-----

Constante. La lista: el ``COUNT`` de la página, la página de entregas (con el dispositivo y quien recibió) y las
líneas de todas con su ítem. El detalle: la entrega con sus líneas (2) y su posición entre las del edificio (1).
"""

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince

from programas.forms_emergencia_kits import RecepcionKitForm
from programas.models import EntregaKit
from programas.selectors import kits as selectores
from programas.services import kits as servicio

ENTREGAS_POR_PAGINA = 25


def entregas_del_edificio(dispositivo, edificio, usuario):
    """Las entregas de ``dispositivo`` a ``edificio``, de la más nueva a la más vieja. Queryset: 2 consultas al leerlo."""

    return selectores.entregas_de(dispositivo, usuario).filter(edificio=edificio).select_related("recibida_por")


def _hace(momento):
    """«hace 3 horas»: la unidad mayor del tiempo transcurrido."""

    if momento is None:
        return ""
    transcurrido = timesince(momento, timezone.now()).split(",")[0].replace("\xa0", " ")
    if transcurrido.startswith("0 "):
        return "hace un momento"
    return f"hace {transcurrido}"


def _diferencias(entrega, lineas):
    """Lo de la columna «Diferencia»: ``[{"texto", "clase"}]``, una por ítem que llegó distinto."""

    if entrega.estado in EntregaKit.ESTADOS_ABIERTOS:
        return [{"texto": "Se ve al recibir", "clase": "text-body-subtle"}]
    if entrega.estado not in EntregaKit.ESTADOS_RECIBIDOS:
        return [{"texto": "—", "clase": "text-body-subtle"}]
    diferencias = []
    for diferencia in selectores.diferencias_de(lineas):
        delta = diferencia["recibida"] - diferencia["enviada"]
        if delta < 0:
            texto = f"−{-delta} · falta{'n' if delta < -1 else ''} ({diferencia['nombre']})"
            diferencias.append({"texto": texto, "clase": "badge badge-danger"})
        else:
            diferencias.append({"texto": f"+{delta} · de más ({diferencia['nombre']})", "clase": "badge badge-warning"})
    return diferencias or [{"texto": "sin diferencia", "clase": "text-body-subtle"}]


def _fila(entrega, url_pagina):
    lineas = list(entrega.lineas.all())
    texto, tono = servicio.estado_visible_de_entrega(entrega)
    return {
        "entrega": entrega,
        "items": selectores.resumen_de_items(lineas),
        "estado_texto": texto,
        "estado_tono": tono,
        "enviada": _hace(entrega.despachada_en) or "Sin enviar",
        "recibida": _hace(entrega.recibida_en)
        or ("—" if entrega.estado == EntregaKit.Estado.CANCELADA else "Sin recibir"),
        "recibio": selectores.nombre_de(entrega.recibida_por),
        "diferencias": _diferencias(entrega, lineas),
        "recibe": entrega.abierta,
        "url": f"{url_pagina}?tab=kits&entrega={entrega.pk}",
    }


def _resumen(total, en_camino):
    entregas = "1 entrega" if total == 1 else f"{total} entregas"
    return f"{entregas} · {en_camino} en camino"


def contexto_de_la_lista(dispositivo, edificio, usuario, pagina, url_pagina, en_camino):
    """La tabla «Entregas a este edificio»: filas de la página pedida, su paginador y el resumen del encabezado."""

    paginador = Paginator(entregas_del_edificio(dispositivo, edificio, usuario), ENTREGAS_POR_PAGINA)
    pagina_actual = paginador.get_page(pagina)
    return {
        "modo": "lista",
        "filas": [_fila(entrega, url_pagina) for entrega in pagina_actual],
        "pagina": pagina_actual,
        "resumen": _resumen(paginador.count, en_camino),
    }


def contexto_del_detalle(dispositivo, edificio, usuario, entrega_pk, url_pagina):
    """El detalle de una entrega del edificio, o ``None`` (404): de otro edificio, de otra institución o sin edificio."""

    entregas = entregas_del_edificio(dispositivo, edificio, usuario)
    entrega = entregas.filter(pk=entrega_pk).first()
    if entrega is None:
        return None
    lineas = list(entrega.lineas.all())
    texto, tono = servicio.estado_visible_de_entrega(entrega)
    # Posición entre las del edificio, de la más nueva: las que se crearon después, más ella.
    posicion = entregas.aggregate(
        total=Count("pk"),
        mas_nuevas=Count("pk", filter=Q(creado__gt=entrega.creado) | Q(creado=entrega.creado, pk__gt=entrega.pk)),
    )
    desde = (
        f"En camino desde {_hace(entrega.despachada_en)}" if entrega.despachada_en else "Todavía sin marca de salida"
    )
    detalle = " · ".join(
        parte
        for parte in (
            desde if entrega.abierta else f"Recibida {_hace(entrega.recibida_en)}",
            f"Transporte: {entrega.transporte}" if entrega.transporte else "",
            f"destino {edificio.nombre} ({edificio.codigo})",
        )
        if parte
    )
    contexto = {
        "modo": "detalle",
        "entrega": entrega,
        "lineas": lineas,
        "estado_texto": texto,
        "estado_tono": tono,
        "detalle": detalle,
        "posicion": f"Entrega {posicion['mas_nuevas'] + 1} de {posicion['total']} de este edificio",
        "url_lista": f"{url_pagina}?tab=kits",
        "recibe": entrega.abierta,
    }
    if entrega.abierta:
        contexto["form"] = RecepcionKitForm(lineas=lineas)
        contexto["url_recibir"] = reverse("emergencia:dispositivo_kit_recibir", args=[dispositivo.pk, entrega.pk])
    else:
        contexto["remito"] = (
            [
                {
                    "url": entrega.remito.url,
                    "rotulo": "Remito",
                    "alt": f"Remito de la entrega {entrega.numero}",
                    "fecha": entrega.recibida_en,
                }
            ]
            if entrega.remito
            else []
        )
        contexto["recibio"] = selectores.nombre_de(entrega.recibida_por)
        contexto["recibida"] = selectores.fecha_hora(entrega.recibida_en)
    return contexto
