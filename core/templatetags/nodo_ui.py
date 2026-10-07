"""Piezas de estructura de página del backoffice (sistema de diseño NODO).

Encabezado de página::

    {% load nodo_ui %}
    {% page_header titulo=obj.nombre volver_url=url_padre volver_label="convocatorias" migas=migas %}
      {% bajada %}{{ obj.segmento.nombre }}{% if obj.subsegmento %} · {{ obj.subsegmento.nombre }}{% endif %}{% endbajada %}
      <span class="badge badge-success badge-dot">Activa</span>
      <a href="…" class="btn-nodo btn-brand btn-sm">Editar</a>
    {% endpage_header %}

Renderiza ``templates/components/_page_header.html``: título ``h1``, bajada,
botón volver circular con ``aria-label="Volver a {volver_label}"``, migas de
pan (solo con tres niveles o más) y, a la derecha, el cuerpo del bloque
(badges y acciones).

Escape:

- ``titulo`` y ``bajada=`` se escapan siempre. La única forma de pasar HTML
  por ``bajada=`` es marcarlo explícitamente desde la plantilla
  (``bajada=texto|safe``); este módulo nunca marca como seguro un valor
  recibido por argumento.
- ``{% bajada %}…{% endbajada %}`` (tiene precedencia sobre ``bajada=``) es un
  fragmento de la propia plantilla: cada variable de adentro pasa por el
  autoescape como en cualquier otro lugar, así que un enlace escrito en la
  plantilla sale como HTML y un nombre cargado por un usuario sale escapado.
  Se reconoce solo como hijo directo del bloque, no dentro de un ``{% if %}``.
- El cuerpo del bloque (acciones) es plantilla, con el mismo autoescape.

``migas`` es una lista de ``{"label": str, "url": str | None}`` ordenada de la
raíz a la página actual (p. ej. la que arma ``becas_migas``). El último
elemento es la página actual y se muestra sin enlace. Con menos de tres
elementos no se muestran: en pantallas de uno o dos niveles alcanza el volver.

Filtros activos::

    {% if request.GET|hay_filtros:"page,tab" %}…{% endif %}

``hay_filtros`` es ``True`` si algún parámetro que no esté en la lista de
excluidos (separada por comas; por defecto ``page``) trae un valor no vacío.
Sirve para que el estado vacío (``components/_estado_vacio.html``) distinga
«no hay nada» de «los filtros no traen nada».

Querystring sin algunas claves::

    {{ request.GET|sin_parametros:"beneficiarios_page"|sin_parametros:"tab=beneficiarios" }}

``sin_parametros`` devuelve el querystring codificado (sin ``?``) de un
``QueryDict`` —o de otro querystring ya codificado, así se encadena— sacando
las claves que se le pasan. Lo usa ``components/_paginacion.html`` para armar
el enlace de la página siguiente cuando la pantalla pagina con un parámetro
propio (``param``/``extra_qs``): sin esto el enlace salía con el parámetro de
página repetido.
"""

import re

from django import template
from django.http import QueryDict
from django.template.base import NodeList, token_kwargs

register = template.Library()

TEMPLATE_PAGE_HEADER = "components/_page_header.html"
EXCLUIDOS_HAY_FILTROS = "page"
MIGAS_MINIMO = 3
ARGUMENTOS = ("titulo", "bajada", "volver_url", "volver_label", "migas")


def _o_vacio(renderizado):
    """El fragmento renderizado tal cual, o ``""`` si es solo espacio."""
    return renderizado if renderizado.strip() else ""


class BajadaNode(template.Node):
    """``{% bajada %}…{% endbajada %}``: fuera de ``page_header`` renderiza tal cual."""

    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        return self.nodelist.render(context)


class PageHeaderNode(template.Node):
    def __init__(self, kwargs, acciones, bajada):
        self.kwargs = kwargs
        self.acciones = acciones
        self.bajada = bajada

    def render(self, context):
        valores = {nombre: valor.resolve(context) for nombre, valor in self.kwargs.items()}
        migas = list(valores.get("migas") or [])
        if len(migas) < MIGAS_MINIMO:
            migas = []
        # ``NodeList.render`` ya devuelve ``SafeString`` (cada variable pasó por el
        # autoescape); se descarta si queda solo espacio, sin ``strip()``, que lo
        # convertiría en ``str`` y lo haría escapar de nuevo.
        bajada = _o_vacio(self.bajada.render(context)) if self.bajada is not None else valores.get("bajada")
        plantilla = context.template.engine.get_template(TEMPLATE_PAGE_HEADER)
        with context.push(
            titulo=valores.get("titulo"),
            bajada=bajada,
            volver_url=valores.get("volver_url"),
            volver_label=valores.get("volver_label"),
            migas=migas,
            acciones=_o_vacio(self.acciones.render(context)),
        ):
            return plantilla.render(context)


@register.tag("bajada")
def do_bajada(parser, token):
    nodelist = parser.parse(("endbajada",))
    parser.delete_first_token()
    return BajadaNode(nodelist)


@register.tag("page_header")
def do_page_header(parser, token):
    bits = token.split_contents()
    nombre_tag = bits[0]
    restantes = bits[1:]
    kwargs = token_kwargs(restantes, parser)
    if restantes:
        raise template.TemplateSyntaxError(
            f"'{nombre_tag}' solo acepta argumentos con nombre ({', '.join(ARGUMENTOS)}); sobra: {restantes[0]!r}"
        )
    desconocidos = set(kwargs) - set(ARGUMENTOS)
    if desconocidos:
        raise template.TemplateSyntaxError(f"'{nombre_tag}' no acepta: {', '.join(sorted(desconocidos))}")
    if "titulo" not in kwargs:
        raise template.TemplateSyntaxError(f"'{nombre_tag}' requiere titulo=")

    cuerpo = parser.parse(("endpage_header",))
    parser.delete_first_token()

    bajada = None
    acciones = NodeList()
    for nodo in cuerpo:
        if isinstance(nodo, BajadaNode):
            if bajada is not None:
                raise template.TemplateSyntaxError(f"'{nombre_tag}' admite un solo {{% bajada %}}")
            bajada = nodo.nodelist
        else:
            acciones.append(nodo)
    return PageHeaderNode(kwargs, acciones, bajada)


@register.filter
def hay_filtros(parametros, excluidos=EXCLUIDOS_HAY_FILTROS):
    """``True`` si algún parámetro no excluido trae un valor no vacío.

    ``parametros`` es un ``QueryDict`` (``request.GET``) o un ``dict``;
    ``excluidos`` es una lista separada por comas (paginación, solapa…).
    """
    if not parametros:
        return False
    fuera = {nombre.strip() for nombre in str(excluidos or "").split(",") if nombre.strip()}
    for clave in parametros:
        if clave in fuera:
            continue
        if hasattr(parametros, "getlist"):
            valores = parametros.getlist(clave)
        else:
            valor = parametros[clave]
            valores = valor if isinstance(valor, (list, tuple)) else [valor]
        if any(str(valor).strip() for valor in valores if valor is not None):
            return True
    return False


SEPARADOR_CLAVES = re.compile(r"[,&]")


@register.filter
def sin_parametros(parametros, excluidos=""):
    """Querystring de ``parametros`` sin las claves de ``excluidos``.

    ``parametros`` es un ``QueryDict`` (``request.GET``) o un querystring ya
    codificado —así el filtro se encadena consigo mismo—. ``excluidos`` es una
    lista de claves separadas por comas o por ``&``; de un par ``clave=valor``
    se usa solo la clave, para poder pasarle el mismo ``extra_qs`` que viaja en
    el enlace.

    Devuelve el querystring **sin** ``?`` y **sin** escapar: lo escapa la
    plantilla (o el ``{% firstof %}`` que lo recibe).
    """
    if not parametros:
        return ""
    if not hasattr(parametros, "getlist"):
        parametros = QueryDict(str(parametros))
    fuera = {
        trozo.split("=", 1)[0].strip()
        for trozo in SEPARADOR_CLAVES.split(str(excluidos or ""))
        if trozo.split("=", 1)[0].strip()
    }
    if not fuera:
        return parametros.urlencode()
    restantes = parametros.copy()
    for clave in fuera:
        restantes.pop(clave, None)
    return restantes.urlencode()
