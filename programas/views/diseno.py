"""Constructor del formulario de la convocatoria (Cambio 58, fase 3: tasks
#342, #343 y #344 del análisis #326).

Una pantalla a dos columnas: a la izquierda el diseño (grupos, campos y
textos, con drag & drop) y a la derecha la vista previa en vivo. **Cada
soltada y cada modal guardan al instante** (D8): toda mutación corre en una
transacción, valida la coherencia de las condiciones sobre el diseño resultante
(RN-6: la fuente siempre antes) y, si algo no cierra, se deshace entera y se
responde 400 con el motivo. La respuesta de éxito trae el parcial de la columna
izquierda ya renderizado más los datos que consume la vista previa.

Permisos: `becas.convocatoria.editar` (admin del programa y coordinador) sobre
una convocatoria visible cuyo segmento el usuario gestiona (D7).
"""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.views import View
from django.views.decorators.http import require_POST

from core.http import error_json, ok_json
from core.rbac import CapacidadRequeridaMixin, requiere
from programas.forms import ItemCampoPropioForm, ItemEtiquetaForm, ItemGrupoForm, ItemTextoForm
from programas.models import CanalFormulario, PresentacionCampo, TipoCampo
from programas.services import constructor
from programas.services.autorizacion import convocatorias_visibles, puede_gestionar_segmento
from programas.services.diseno import generar_por_defecto, items_ordenados, obtener_o_crear_diseno
from programas.validadores import validar_condicion_json
from programas.views.ajax_utils import ajax_errors

CAP_CONVOCATORIA_EDITAR = "becas.convocatoria.editar"
TARGET = "#constructor-items"
PARTIAL = "programas/becas/formulario/_constructor_items.html"

# ── Acceso ───────────────────────────────────────────────────────────────────


def _convocatoria(request, pk):
    """La convocatoria, solo si el usuario la ve y gestiona su segmento."""
    convocatoria = get_object_or_404(
        convocatorias_visibles(request.user).select_related("segmento__programa", "subsegmento"),
        pk=pk,
    )
    if not puede_gestionar_segmento(request.user, convocatoria.segmento):
        raise PermissionDenied
    return convocatoria


def _diseno(request, pk, reconciliar_con_catalogo=True):
    """El diseño de la convocatoria, con el control de acceso ya hecho.

    Los POST de mutación pasan ``reconciliar_con_catalogo=False`` (BEC-16):
    reconciliar **escribe**, y hacerlo en cada request metía una segunda
    escritura del diseño dentro de cada guardado. La sincronización con el
    catálogo se hace al abrir la pantalla, que es cuando el operador puede leer
    el aviso de qué entró y qué salió.
    """
    convocatoria = _convocatoria(request, pk)
    diseno, avisos = obtener_o_crear_diseno(
        convocatoria, request.user, reconciliar_con_catalogo=reconciliar_con_catalogo
    )
    return diseno, avisos


def _item(diseno, clave):
    return get_object_or_404(
        diseno.items.select_related("pregunta__grupo", "requisito", "grupo_catalogo", "padre"),
        clave=clave,
    )


def _json(request):
    try:
        datos = json.loads(request.body or b"{}")
    except ValueError:
        return None
    return datos if isinstance(datos, dict) else None


# ── Datos para la pantalla ───────────────────────────────────────────────────

# Viven en `programas.services.constructor`, que comparten los dos dueños del
# diseño; los nombres de acá quedan porque otros módulos los leen.
DisenoInvalido = constructor.DisenoInvalido
_operadores = constructor.operadores


def _contexto(request, diseno, avisos=None, items=None):
    if items is None:
        items = items_ordenados(diseno)
    return {
        "convocatoria": diseno.convocatoria,
        "diseno": diseno,
        "items": items,
        "arbol": constructor.arbol(items),
        "datos": constructor.datos(diseno, items),
        "avisos": avisos or {},
    }


def _respuesta(request, diseno, mensaje, avisos=None, items=None):
    ctx = _contexto(request, diseno, avisos, items)
    html = render_to_string(PARTIAL, ctx, request=request)
    return ok_json(target=TARGET, html=html, message=mensaje, datos=ctx["datos"], avisos=ctx["avisos"])


def _mutar(request, diseno, mensaje, operacion):
    """Corre ``operacion`` con el candado, la validación y la versión del
    constructor (`programas.services.constructor.mutar`); si no cierra, responde
    400 con el motivo."""
    try:
        items = constructor.mutar(diseno, request.user, operacion)
    except DisenoInvalido as exc:
        return error_json(exc.mensaje, errores=exc.errores)
    return _respuesta(request, diseno, mensaje, items=items)


# ── Pantalla ─────────────────────────────────────────────────────────────────


class ConvocatoriaFormularioView(CapacidadRequeridaMixin, LoginRequiredMixin, View):
    """«Configurar formulario» de la convocatoria (#342)."""

    capacidades_requeridas = CAP_CONVOCATORIA_EDITAR

    def get(self, request, pk):
        diseno, avisos = _diseno(request, pk)
        ctx = _contexto(request, diseno, avisos)
        ctx.update(
            {
                "canal_choices": CanalFormulario.choices,
                "tipo_choices": TipoCampo.choices,
                "presentacion_choices": PresentacionCampo.choices,
                "operadores": _operadores(),
                "form_grupo": ItemGrupoForm(),
                "form_texto": ItemTextoForm(),
                "form_propio": ItemCampoPropioForm(),
                "form_etiqueta": ItemEtiquetaForm(),
                "n_relevamientos": diseno.convocatoria.relevamientos.count(),
            }
        )
        return render(request, "programas/becas/formulario/convocatoria_formulario.html", ctx)


# ── Mutaciones ───────────────────────────────────────────────────────────────


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def formulario_mover(request, pk):
    """Drag & drop: ``{clave, padre, posicion}``. Los grupos se mueven en la
    raíz; campos y textos, dentro de un grupo. Si el movimiento deja una
    condición apuntando a una fuente posterior, se rechaza (RN-6)."""
    diseno, _ = _diseno(request, pk, reconciliar_con_catalogo=False)
    payload = _json(request)
    if payload is None or not payload.get("clave"):
        return error_json("Payload inválido.")
    item = _item(diseno, payload["clave"])
    clave_padre = payload.get("padre") or None
    try:
        posicion = int(payload.get("posicion", 0))
    except (TypeError, ValueError):
        return error_json("Posición inválida.")

    return _mutar(request, diseno, "Orden guardado.", lambda: constructor.mover(diseno, item, clave_padre, posicion))


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def formulario_grupo_crear(request, pk):
    diseno, _ = _diseno(request, pk, reconciliar_con_catalogo=False)
    form = ItemGrupoForm(request.POST)
    if not form.is_valid():
        return ajax_errors(form)

    return _mutar(
        request,
        diseno,
        "Grupo agregado al final del formulario.",
        lambda: constructor.crear_grupo(diseno, form.cleaned_data),
    )


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def formulario_texto_crear(request, pk):
    diseno, _ = _diseno(request, pk, reconciliar_con_catalogo=False)
    form = ItemTextoForm(request.POST)
    padre = constructor.padre_para_nuevo(diseno, request.POST.get("padre") or "")
    if padre is None:
        form.add_error(None, "Elegí el grupo donde va el texto.")
    if not form.is_valid() or padre is None:
        return ajax_errors(form)

    return _mutar(request, diseno, "Texto agregado.", lambda: constructor.crear_texto(diseno, padre, form.cleaned_data))


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def formulario_propio_crear(request, pk):
    diseno, _ = _diseno(request, pk, reconciliar_con_catalogo=False)
    form = ItemCampoPropioForm(request.POST)
    padre = constructor.padre_para_nuevo(diseno, request.POST.get("padre") or "")
    if padre is None:
        form.add_error(None, "Elegí el grupo donde va el campo.")
    if not form.is_valid() or padre is None:
        return ajax_errors(form)

    return _mutar(
        request, diseno, "Campo propio agregado.", lambda: constructor.crear_propio(diseno, padre, form.cleaned_data)
    )


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def formulario_item_editar(request, pk, clave):
    """Edita lo que el diseño es dueño de cada ítem (RN-2): grupo → título,
    subtítulo y canal; texto → texto y canal; campo propio → todo; campo del
    catálogo → solo la etiqueta."""
    diseno, _ = _diseno(request, pk, reconciliar_con_catalogo=False)
    item = _item(diseno, clave)
    if item.es_grupo:
        form = ItemGrupoForm(request.POST)
    elif item.es_texto:
        form = ItemTextoForm(request.POST)
    elif item.es_propio:
        form = ItemCampoPropioForm(request.POST)
    else:
        form = ItemEtiquetaForm(request.POST)
    if not form.is_valid():
        return ajax_errors(form)

    return _mutar(request, diseno, "Cambios guardados.", lambda: constructor.editar(item, form.cleaned_data))


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def formulario_condicion(request, pk, clave):
    """``{condicion: null | {modo, reglas}}``. Se valida contra los ítems
    anteriores (RN-6/RN-7) antes de guardar."""
    diseno, _ = _diseno(request, pk, reconciliar_con_catalogo=False)
    item = _item(diseno, clave)
    payload = _json(request)
    if payload is None or "condicion" not in payload:
        return error_json("Payload inválido.")
    condicion = payload["condicion"]
    if condicion is not None and not isinstance(condicion, dict):
        return error_json("La condición tiene un formato inválido.")
    if condicion is not None and not (condicion.get("reglas") or []):
        condicion = None  # sin reglas = sin condición
    # RED-40: la forma, antes de guardar. La coherencia contra el diseño la
    # valida `_mutar` después; lo que esto frena es lo que ni siquiera se puede
    # evaluar —un operador que el motor no conoce devuelve False y esconde el
    # ítem para siempre, sin error y sin log—.
    try:
        validar_condicion_json(condicion)
    except DjangoValidationError as error:
        return error_json(" ".join(error.messages))

    mensaje = "Condición guardada." if condicion else "Condición quitada: el ítem se muestra siempre."
    return _mutar(request, diseno, mensaje, lambda: constructor.poner_condicion(item, condicion))


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def formulario_item_eliminar(request, pk, clave):
    """Se eliminan textos, campos propios y grupos vacíos. Los requisitos del
    catálogo no se eliminan del diseño (RN-1): se mueven o se desactivan en el
    catálogo."""
    diseno, _ = _diseno(request, pk, reconciliar_con_catalogo=False)
    item = _item(diseno, clave)
    motivo = constructor.motivo_para_no_eliminar(item)
    if motivo:
        return error_json(motivo)

    titulo = item.titulo or item.get_tipo_display()
    return _mutar(request, diseno, f"«{titulo}» eliminado.", item.delete)


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def formulario_restablecer(request, pk):
    """Vuelve al plan por defecto (grupos del catálogo + un grupo por nivel de
    requisitos). Borra textos, campos propios, condiciones y etiquetas."""
    diseno, _ = _diseno(request, pk, reconciliar_con_catalogo=False)

    return _mutar(
        request, diseno, "Formulario restablecido al orden del catálogo.", lambda: generar_por_defecto(diseno)
    )
