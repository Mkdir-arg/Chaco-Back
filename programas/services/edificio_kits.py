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
from django.db.models import Case, Count, IntegerField, Q, When
from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince

from programas.forms_emergencia_kits import RecepcionKitForm
from programas.models import EntregaKit
from programas.selectors import kits as selectores
from programas.services import kits as servicio

ENTREGAS_POR_PAGINA = 25


def entregas_del_edificio(dispositivo, edificio, usuario):
    """Las entregas de ``dispositivo`` a ``edificio``, de la más nueva a la más vieja. Queryset: 2 consultas al leerlo.

    Es el orden base: la lista y la posición del detalle ponen primero las por recibir.
    """

    return selectores.entregas_de(dispositivo, usuario).filter(edificio=edificio).select_related("recibida_por")


def _hace(momento):
    """«hace 3 horas», «hace 7 días»: desde un día, los días corridos; antes, la unidad mayor (horas o minutos)."""

    if momento is None:
        return ""
    ahora = timezone.now()
    dias = (ahora - momento).days
    if dias >= 1:
        return f"hace {dias} día{'s' if dias > 1 else ''}"
    transcurrido = timesince(momento, ahora, depth=1).replace(" ", " ")
    return "hace un momento" if transcurrido.startswith("0 ") else f"hace {transcurrido}"


def _diferencia(entrega, lineas):
    """Los datos de la columna «Diferencia»; la celda la dibuja ``_celda_diferencia.html``, que decide el texto y el tono.

    ``modo``: ``abierta`` (todavía no se recibió), ``cancelada`` (no hay nada que comparar) o ``recibida``, con las
    líneas que llegaron distintas en ``items``.
    """

    if entrega.abierta:
        return {"modo": "abierta", "items": []}
    if entrega.estado not in EntregaKit.ESTADOS_RECIBIDOS:
        return {"modo": "cancelada", "items": []}
    return {"modo": "recibida", "items": selectores.diferencias_de(lineas)}


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
        "diferencia": _diferencia(entrega, lineas),
        "recibe": entrega.abierta,
        "url": servicio.url_de_kits_del_edificio(url_pagina, entrega),
    }


def _resumen(total, por_recibir):
    """«2 entregas · 0 por recibir»: el mismo «por recibir» (en camino o preparadas) de los contadores del edificio."""

    entregas = "1 entrega" if total == 1 else f"{total} entregas"
    return f"{entregas} · {por_recibir} por recibir"


def contexto_de_la_lista(dispositivo, edificio, usuario, pagina, url_pagina):
    """La tabla «Entregas a este edificio»: filas de la página pedida, su paginador y el resumen del encabezado.

    Van primero las por recibir (en camino o preparadas) y después el resto; en cada grupo, de la más nueva a la más vieja.
    """

    entregas = entregas_del_edificio(dispositivo, edificio, usuario)
    # El total y las «por recibir» en una sola consulta; el paginador no vuelve a contar.
    cuentas = entregas.aggregate(
        total=Count("pk"), por_recibir=Count("pk", filter=Q(estado__in=EntregaKit.ESTADOS_ABIERTOS))
    )
    # Las por recibir van primero (el ítem «Recibir kit (N)» lleva acá); dentro de cada grupo, de la más nueva a la más vieja.
    entregas = entregas.order_by(
        Case(When(estado__in=EntregaKit.ESTADOS_ABIERTOS, then=0), default=1, output_field=IntegerField()),
        "-creado",
        "-id",
    )
    paginador = Paginator(entregas, ENTREGAS_POR_PAGINA)
    paginador.__dict__["count"] = cuentas["total"]
    pagina_actual = paginador.get_page(pagina)
    return {
        "modo": "lista",
        "filas": [_fila(entrega, url_pagina) for entrega in pagina_actual],
        "pagina": pagina_actual,
        "resumen": _resumen(cuentas["total"], cuentas["por_recibir"]),
    }


def contexto_del_detalle(dispositivo, edificio, usuario, entrega_pk, url_pagina):
    """El detalle de una entrega del edificio, o ``None`` (404): de otro edificio, de otra institución o sin edificio."""

    entregas = entregas_del_edificio(dispositivo, edificio, usuario)
    entrega = entregas.filter(pk=entrega_pk).first()
    if entrega is None:
        return None
    lineas = list(entrega.lineas.all())
    texto, tono = servicio.estado_visible_de_entrega(entrega)
    # Posición con el mismo orden que la lista: las por recibir primero y, dentro de cada grupo, de la más nueva.
    # Si está abierta, antes van solo las abiertas más nuevas; si no, todas las abiertas y las cerradas más nuevas.
    abierta = Q(estado__in=EntregaKit.ESTADOS_ABIERTOS)
    mas_nueva = Q(creado__gt=entrega.creado) | Q(creado=entrega.creado, pk__gt=entrega.pk)
    antes = (abierta & mas_nueva) if entrega.abierta else (abierta | (~abierta & mas_nueva))
    posicion = entregas.aggregate(total=Count("pk"), antes=Count("pk", filter=antes))
    recibida = entrega.estado in EntregaKit.ESTADOS_RECIBIDOS
    if entrega.abierta:
        situacion = (
            f"En camino desde {_hace(entrega.despachada_en)}"
            if entrega.despachada_en
            else "Todavía sin marca de salida"
        )
    elif recibida:
        situacion = f"Recibida {_hace(entrega.recibida_en)}"
    else:
        situacion = texto
    detalle = " · ".join(
        parte
        for parte in (
            situacion,
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
        "posicion": f"Entrega {posicion['antes'] + 1} de {posicion['total']} de este edificio",
        "url_lista": servicio.url_de_kits_del_edificio(url_pagina),
        "recibe": entrega.abierta,
        "recibida_ok": recibida,
    }
    if entrega.abierta:
        contexto["form"] = RecepcionKitForm(lineas=lineas)
        contexto["suma_al_stock"] = servicio.suma_al_stock(dispositivo)
        contexto["url_recibir"] = reverse("emergencia:dispositivo_kit_recibir", args=[dispositivo.pk, entrega.pk])
    elif recibida:
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
