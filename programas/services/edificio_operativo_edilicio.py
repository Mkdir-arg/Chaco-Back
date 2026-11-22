"""Solapa «Estado edilicio» de la página operativa del edificio (Cambio 567, PR 5 del lote «el edificio como unidad operativa»).

Patrón lista → detalle, dentro de la misma solapa: ``?tab=edilicio`` muestra la tabla de relevamientos realizados del
edificio y ``?tab=edilicio&relevamiento=<id>`` abre el detalle de uno.

Autorización
------------

El relevamiento **cuelga del edificio** (lo ven todas las instituciones del predio), pero lo que muestra se abre solo
por :func:`programas.services.inspecciones.inspecciones_visibles` (Cambio 422 y 428): sin ese alcance la tabla queda
con el número y la fecha, y no hay detalle, ni observaciones, ni quién relevó, ni fotos. El detalle de un relevamiento
de **otro** edificio, de uno no realizado o de uno que el usuario no ve es el mismo ``None`` (404 en la vista) que un
id que no existe.

Costo
-----

Constante: COUNT y página de la tabla (2) más el censo de fotos y de visibilidad dentro de la misma consulta. El
detalle suma el relevamiento (1), sus fotos (1) y su posición entre los del edificio (1).
"""

from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import Truncator
from django.utils.timesince import timesince

from programas.models import FotoInspeccion, InspeccionEdificio
from programas.services.inspecciones import fotos_para_galeria, inspecciones_visibles

POR_PAGINA = 10
PARAM_PAGINA = "relevamientos_page"
PARAM_RELEVAMIENTO = "relevamiento"
_LARGO_OBSERVACION = 80

#: Rótulo corto y tono de cada criticidad: el del diseño (Baja, Media, Alta), no el largo del modelo.
_CRITICIDAD = {
    InspeccionEdificio.Criticidad.BAJA: ("Baja", "success"),
    InspeccionEdificio.Criticidad.MEDIA: ("Media", "warning"),
    InspeccionEdificio.Criticidad.ALTA: ("Alta", "danger"),
}


def numero_de_relevamiento(pk):
    return f"REL-{pk:04d}"


def _realizados(edificio):
    return InspeccionEdificio.objects.filter(edificio=edificio, estado=InspeccionEdificio.Estado.REALIZADA)


def _criticidad(valor):
    return _CRITICIDAD.get(valor) or (valor.title() if valor else "Sin criticidad", "gray")


def _nombre(usuario):
    if usuario is None:
        return "—"
    return usuario.get_full_name().strip() or usuario.get_username()


def _fecha(momento):
    return timezone.localtime(momento).strftime("%d/%m/%Y")


def _hace(momento):
    return f"hace {timesince(momento, depth=1)}"


def _plural(cantidad, singular, plural):
    return f"{cantidad} {singular if cantidad == 1 else plural}"


def _fila(inspeccion, *, marca):
    criticidad, tono = _criticidad(inspeccion.criticidad)
    abre = inspeccion.con_detalle
    return {
        "numero": numero_de_relevamiento(inspeccion.pk),
        "marca": marca,
        "fecha": _fecha(inspeccion.realizada_en),
        "hace": _hace(inspeccion.realizada_en),
        "con_detalle": abre,
        "relevo": _nombre(inspeccion.realizada_por) if abre else "",
        "criticidad": criticidad if abre else "",
        "tono": tono if abre else "",
        "observaciones": (
            Truncator((inspeccion.observaciones or "").strip()).chars(_LARGO_OBSERVACION) or "Sin observaciones"
            if abre
            else ""
        ),
        "fotos": (_plural(inspeccion.n_fotos, "foto", "fotos") if inspeccion.n_fotos else "Sin fotos") if abre else "",
        "url_detalle": "",
    }


def lista_de_relevamientos(user, edificio, pagina, url_pagina):
    """La tabla de la solapa: los relevamientos realizados del edificio, del más nuevo al más viejo.

    ``con_detalle`` es el alcance de inspección del usuario (una sola consulta, sin una por fila): sin él la fila no
    lleva criticidad, quién relevó, observaciones ni fotos, y no ofrece «Ver detalle».
    """

    consulta = (
        _realizados(edificio)
        .annotate(
            n_fotos=Count("fotos"),
            con_detalle=Exists(inspecciones_visibles(user).filter(pk=OuterRef("pk"))),
        )
        .select_related("realizada_por")
        .order_by("-realizada_en", "-pk")
    )
    pagina_actual = Paginator(consulta, POR_PAGINA).get_page(pagina)
    filas = []
    ultimo = len(pagina_actual.object_list) - 1
    for posicion, inspeccion in enumerate(pagina_actual):
        if pagina_actual.number == 1 and posicion == 0:
            marca = "Último"
        elif not pagina_actual.has_next() and posicion == ultimo and pagina_actual.paginator.count > 1:
            marca = "Primer relevamiento"
        else:
            marca = ""
        fila = _fila(inspeccion, marca=marca)
        if fila["con_detalle"]:
            volver = f"&{PARAM_PAGINA}={pagina_actual.number}" if pagina_actual.number > 1 else ""
            fila["url_detalle"] = f"{url_pagina}?tab=edilicio&{PARAM_RELEVAMIENTO}={inspeccion.pk}{volver}"
        filas.append(fila)
    total = pagina_actual.paginator.count
    return {
        "filas": filas,
        "pagina": pagina_actual,
        "total": total,
        "texto_total": _plural(total, "relevamiento", "relevamientos"),
        "hay_sin_detalle": any(not fila["con_detalle"] for fila in filas),
    }


def _id_valido(valor):
    texto = str(valor or "")
    return int(texto) if texto.isascii() and texto.isdecimal() and len(texto) < 10 else None


def relevamiento_del_edificio(user, edificio, relevamiento_pk):
    """El relevamiento realizado de **este** edificio que ``user`` puede abrir, o ``None`` (404 en la vista)."""

    pk = _id_valido(relevamiento_pk)
    if pk is None:
        return None
    return (
        _realizados(edificio)
        .filter(pk=pk, pk__in=inspecciones_visibles(user).values("pk"))
        .select_related("realizada_por")
        .first()
    )


def _posicion(edificio, inspeccion):
    """«el más nuevo de 4», «el más viejo de 4» o «el 2.º de 4»: una consulta."""

    medidas = _realizados(edificio).aggregate(
        total=Count("pk"),
        mas_nuevos=Count(
            "pk",
            filter=Q(realizada_en__gt=inspeccion.realizada_en)
            | Q(realizada_en=inspeccion.realizada_en, pk__gt=inspeccion.pk),
        ),
    )
    total, mas_nuevos = medidas["total"], medidas["mas_nuevos"]
    if total <= 1:
        return "el único relevamiento"
    if mas_nuevos == 0:
        return f"el más nuevo de {total}"
    if mas_nuevos == total - 1:
        return f"el más viejo de {total}"
    return f"el {mas_nuevos + 1}.º de {total}, del más nuevo al más viejo"


def detalle_de_relevamiento(edificio, inspeccion, url_pagina, *, dispositivo_pk, pagina=None):
    """Lo que dibuja el detalle: encabezado, datos, observaciones y las fotos de **ese** relevamiento."""

    # El relevamiento se leyó ya acotado a este edificio: se reusa, sin otra consulta para el nombre en el alt.
    inspeccion.edificio = edificio
    fotos = list(
        FotoInspeccion.objects.filter(inspeccion=inspeccion)
        .only("id", "inspeccion_id", "archivo", "descripcion", "creado")
        .order_by("creado", "pk")
    )
    criticidad, tono = _criticidad(inspeccion.criticidad)
    galeria = [
        {**foto, "fecha": inspeccion.realizada_en or foto["fecha"]} for foto in fotos_para_galeria(inspeccion, fotos)
    ]
    return {
        "numero": numero_de_relevamiento(inspeccion.pk),
        "subtitulo": f"{edificio.codigo} · {_fecha(inspeccion.realizada_en)} · {_posicion(edificio, inspeccion)}",
        "fecha": _fecha(inspeccion.realizada_en),
        "criticidad": criticidad,
        "tono": tono,
        "relevo": _nombre(inspeccion.realizada_por),
        "observaciones": (inspeccion.observaciones or "").strip(),
        "fotos": galeria,
        "total_fotos": len(galeria),
        "texto_fotos": f"{_plural(len(galeria), 'foto', 'fotos')} de este relevamiento",
        "url_volver": f"{url_pagina}?tab=edilicio" + (f"&{PARAM_PAGINA}={pagina}" if pagina and pagina > 1 else ""),
        "url_informe": reverse("dispositivos:relevamiento_informe", args=[inspeccion.pk])
        + f"?dispositivo={dispositivo_pk}",
    }


def contexto_edilicio(user, dispositivo, edificio, parametros, url_pagina):
    """El contexto de la solapa: la tabla, o el detalle si ``?relevamiento=`` pide uno (``None`` = 404 en la vista)."""

    pedido = parametros.get(PARAM_RELEVAMIENTO)
    if pedido:
        inspeccion = relevamiento_del_edificio(user, edificio, pedido)
        if inspeccion is None:
            return None
        return {
            "edilicio_detalle": detalle_de_relevamiento(
                edificio,
                inspeccion,
                url_pagina,
                dispositivo_pk=dispositivo.pk,
                pagina=_id_valido(parametros.get(PARAM_PAGINA)),
            )
        }
    return {
        "edilicio_lista": lista_de_relevamientos(user, edificio, parametros.get(PARAM_PAGINA), url_pagina),
    }
