"""Filtros y tags de template del backoffice de Becas."""

import json

from django import template
from django.template.defaultfilters import date as fecha_local
from django.urls import reverse

from core import rbac
from programas.models import Convocatoria, ProgramaSiis, Relevamiento, Segmento, Subsegmento

register = template.Library()


@register.filter
def siis_info(programa):
    """Detalle de un ``ProgramaSiis``, como literal JSON para Alpine.

    Se emite sin ``mark_safe``: el autoescape convierte las comillas en
    ``&quot;`` dentro del atributo y el navegador las devuelve al parsear, así
    que la expresión ``@click="openInfo({...})"`` recibe un objeto válido.
    """
    datos = programa.siis_programa_datos or {}
    return json.dumps(
        {
            "id": programa.siis_programa_id,
            "nombre": datos.get("nombre") or programa.nombre,
            "descripcion": datos.get("descripcion") or "",
            "jurisdiccion": datos.get("jurisdiccion_id"),
            "estadoVinculado": datos.get("estado") or "",
            "estadoActual": programa.siis_programa_estado or "",
            "bloqueado": programa.siis_bloqueado,
            "motivo": programa.siis_motivo_bloqueo,
            "vinculado": fecha_local(programa.siis_vinculado_en, "d/m/Y H:i") or "",
            "verificado": fecha_local(programa.siis_verificado_en, "d/m/Y H:i") or "",
            "controles": [
                ("Empleo público", datos.get("controla_empleo_publico")),
                ("Horas cátedra docentes", datos.get("controla_horas_docentes")),
                ("Duplicidad de beneficios", datos.get("controla_duplicidad_becas")),
                ("Tope de SMVM", datos.get("controla_smvm")),
                ("Edad mínima", datos.get("controla_edad_minima")),
            ],
            "edadMinima": datos.get("edad_minima"),
        },
        ensure_ascii=False,
    )


@register.filter
def iniciales(value):
    """Iniciales de un nombre: 1ª letra del primer y último término (máx 2),
    en mayúscula. "María García" -> "MG"; "Carlos" -> "C"."""
    if not value:
        return ""
    partes = str(value).split()
    if not partes:
        return ""
    if len(partes) == 1:
        return partes[0][:1].upper()
    return (partes[0][:1] + partes[-1][:1]).upper()


# --- Migas de pan -------------------------------------------------------------
# Capacidad que pide cada vista de destino (``capacidades_requeridas`` en
# ``views/configuracion.py`` y ``views/relevamientos.py``). Sin ella la miga se
# muestra como texto: no se ofrece un enlace que va a terminar en 403. El alcance
# por objeto (segmento del coordinador, etc.) lo sigue resolviendo la vista.
_MIGA_CAP_PROGRAMA = "becas.segmento.ver"
_MIGA_CAP_SEGMENTO = "becas.segmento.ver"
_MIGA_CAP_SUBSEGMENTO = "becas.subsegmento.ver"
_MIGA_CAP_CONVOCATORIA = "becas.convocatoria.ver"
_MIGA_CAP_RELEVAMIENTO = "becas.relevamiento.ver"


def _cadena_becas(objeto):
    """``[(objeto, url_name, capacidad), …]`` de la raíz (programa) al ``objeto``.

    Solo recorre FKs (``relevamiento.convocatoria``, ``convocatoria.segmento`` y
    ``.subsegmento``, ``segmento.programa``): sin consultas si el objeto llega con
    esos ``select_related``; con una por relación no cargada si no.
    """
    if isinstance(objeto, Relevamiento):
        return _cadena_becas(objeto.convocatoria) + [(objeto, "becas:relevamiento_detalle", _MIGA_CAP_RELEVAMIENTO)]
    if isinstance(objeto, Convocatoria):
        cadena = _cadena_becas(objeto.segmento)
        if objeto.subsegmento_id:
            cadena.append((objeto.subsegmento, "becas:subsegmento_detalle", _MIGA_CAP_SUBSEGMENTO))
        return cadena + [(objeto, "becas:convocatoria_detalle", _MIGA_CAP_CONVOCATORIA)]
    if isinstance(objeto, Subsegmento):
        return _cadena_becas(objeto.segmento) + [(objeto, "becas:subsegmento_detalle", _MIGA_CAP_SUBSEGMENTO)]
    if isinstance(objeto, Segmento):
        # ``programa`` es nulo solo en segmentos históricos: la ruta arranca en el segmento.
        cadena = _cadena_becas(objeto.programa) if objeto.programa_id else []
        return cadena + [(objeto, "becas:segmento_detalle", _MIGA_CAP_SEGMENTO)]
    if isinstance(objeto, ProgramaSiis):
        return [(objeto, "becas:programa_detalle", _MIGA_CAP_PROGRAMA)]
    raise TypeError(f"becas_migas no sabe armar la ruta de {type(objeto).__name__}")


@register.simple_tag(takes_context=True)
def becas_migas(context, objeto, actual=None):
    """Migas de Becas para ``{% page_header migas=… %}``.

    Uso::

        {% becas_migas convocatoria as migas %}
        {% becas_migas segmento actual="Cupo y beneficiarios" as migas %}

    Arma ``Programas → Programa → Segmento → [Subsegmento] → Convocatoria →
    Relevamiento`` hasta ``objeto`` (``ProgramaSiis``, ``Segmento``,
    ``Subsegmento``, ``Convocatoria`` o ``Relevamiento``), con los nombres
    reales de cada objeto. La raíz es el listado «Programas», el mismo nombre
    que el menú. El último elemento es la página actual y va sin enlace; con
    ``actual`` se agrega un último elemento más (una pantalla que cuelga del
    objeto) y el objeto pasa a tener enlace.

    No consulta la base si ``objeto`` trae cargadas sus FKs hacia arriba (p. ej.
    una convocatoria con ``select_related("segmento__programa", "subsegmento")``)
    y las capacidades del usuario ya se evaluaron en la request.
    """
    request = context.get("request")
    user = getattr(request, "user", None)

    def enlace(url_name, capacidad, *args):
        return reverse(url_name, args=args) if rbac.puede(user, capacidad) else None

    migas = [{"label": "Programas", "url": enlace("becas:programas", _MIGA_CAP_PROGRAMA)}]
    migas += [
        {"label": obj.nombre, "url": enlace(url_name, capacidad, obj.pk)}
        for obj, url_name, capacidad in _cadena_becas(objeto)
    ]
    if actual:
        migas.append({"label": actual, "url": None})
    else:
        migas[-1]["url"] = None
    return migas
