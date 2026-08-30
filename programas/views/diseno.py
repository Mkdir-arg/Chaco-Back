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
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.views import View
from django.views.decorators.http import require_POST

from core.rbac import CapacidadRequeridaMixin, requiere
from programas.forms import ItemCampoPropioForm, ItemEtiquetaForm, ItemGrupoForm, ItemTextoForm
from programas.models import CanalFormulario, ItemDiseno, PresentacionCampo, TipoCampo
from programas.services import condiciones as cond
from programas.services.autorizacion import convocatorias_visibles, puede_gestionar_segmento
from programas.services.diseno import (
    campo_dict,
    generar_por_defecto,
    items_ordenados,
    items_planos,
    nueva_clave,
    obtener_o_crear_diseno,
)
from programas.views.ajax_utils import ajax_errors

CAP_CONVOCATORIA_EDITAR = "becas.convocatoria.editar"
TARGET = "#constructor-items"
PARTIAL = "programas/becas/formulario/_constructor_items.html"

GRUPO = ItemDiseno.Tipo.GRUPO
CAMPO = ItemDiseno.Tipo.CAMPO
TEXTO = ItemDiseno.Tipo.TEXTO


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


def _diseno(request, pk):
    convocatoria = _convocatoria(request, pk)
    diseno, avisos = obtener_o_crear_diseno(convocatoria, request.user)
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


class DisenoInvalido(Exception):
    """Una mutación deja el diseño incoherente: se deshace y se explica."""

    def __init__(self, errores):
        super().__init__("Diseño inválido")
        self.errores = errores  # {clave: [mensajes]}


# ── Datos para la pantalla ───────────────────────────────────────────────────


def _datos(diseno, items):
    """Lo que consume la vista previa y los modales: cada ítem en orden con lo
    que el catálogo o el diseño saben de él. Es también el mapa de qué se puede
    hacer con cada ítem (`eliminable`, `canal_editable`...)."""
    hijos_por_padre = {}
    for item in items:
        if item.padre_id:
            hijos_por_padre[item.padre_id] = hijos_por_padre.get(item.padre_id, 0) + 1

    lista = []
    for item in items:
        dato = {
            "clave": item.clave,
            "tipo": item.tipo,
            "padre": item.padre.clave if item.padre_id else None,
            "titulo": item.titulo,
            "etiqueta": item.etiqueta,
            "subtitulo": item.subtitulo,
            "texto": item.texto,
            "condicion": item.condicion,
            "canal": item.canal_efectivo,
        }
        if item.es_grupo:
            dato.update(
                {
                    "catalogo": bool(item.grupo_catalogo_id),
                    "protegido": bool(item.grupo_catalogo_id and item.grupo_catalogo.protegido),
                    "hijos": hijos_por_padre.get(item.pk, 0),
                    "eliminable": hijos_por_padre.get(item.pk, 0) == 0,
                    "canal_editable": True,
                }
            )
        elif item.es_texto:
            dato.update({"eliminable": True, "canal_editable": True})
        else:
            campo = campo_dict(item)
            objeto = item.objeto_catalogo
            dato.update(
                {
                    "tipo_campo": campo["tipo"],
                    "opciones": campo.get("opciones") or [],
                    "presentacion": campo.get("presentacion") or PresentacionCampo.LISTA,
                    "obligatorio": bool(campo.get("obligatorio")),
                    "alcance": campo.get("alcance"),
                    "origen": campo.get("origen"),
                    "vinculo": campo.get("vinculo") or "",
                    "texto_catalogo": objeto.texto if objeto is not None else (item.propio or {}).get("texto", ""),
                    "protegido": bool(item.pregunta_id and item.pregunta.protegido),
                    "propio": item.es_propio,
                    "eliminable": item.es_propio,
                    "canal_editable": item.es_propio,
                }
            )
        item.ui = dato  # lo usa el parcial para los badges sin recalcular
        lista.append(dato)
    return {"version": diseno.version, "items": lista}


def _arbol(items):
    """``[(grupo, [hijos])]`` para el parcial; los sueltos (no debería haber)
    van bajo ``None``."""
    arbol = []
    indice = {}
    sueltos = []
    for item in items:
        if item.es_grupo:
            indice[item.pk] = []
            arbol.append((item, indice[item.pk]))
        elif item.padre_id in indice:
            indice[item.padre_id].append(item)
        else:
            sueltos.append(item)
    if sueltos:
        arbol.append((None, sueltos))
    return arbol


def _operadores():
    """Catálogo de operadores para el editor de condiciones (espejo de
    ``services.condiciones``)."""
    return {
        "por_tipo": {tipo: sorted(ops) for tipo, ops in cond.OPERADORES_POR_TIPO.items()},
        "etiquetas": cond.ETIQUETAS_OPERADOR,
        "sin_valor": sorted(cond.SIN_VALOR),
        "con_lista": sorted(cond.CON_LISTA),
    }


def _contexto(request, diseno, avisos=None, items=None):
    if items is None:
        items = items_ordenados(diseno)
    return {
        "convocatoria": diseno.convocatoria,
        "diseno": diseno,
        "items": items,
        "arbol": _arbol(items),
        "datos": _datos(diseno, items),
        "avisos": avisos or {},
    }


def _respuesta(request, diseno, mensaje, avisos=None, items=None):
    ctx = _contexto(request, diseno, avisos, items)
    html = render_to_string(PARTIAL, ctx, request=request)
    return JsonResponse(
        {"ok": True, "target": TARGET, "html": html, "message": mensaje, "datos": ctx["datos"], "avisos": ctx["avisos"]}
    )


def _mensaje(errores):
    partes = []
    for mensajes in errores.values():
        partes.extend(mensajes)
    return " ".join(partes) if partes else "El diseño quedó incoherente."


def _asegurar_coherencia(diseno):
    """Valida las condiciones sobre el diseño resultante y devuelve los ítems
    ya cargados (se reutilizan en la respuesta: una sola lectura)."""
    items = items_ordenados(diseno)
    errores = cond.validar_coherencia(items_planos(items))
    if errores:
        raise DisenoInvalido(errores)
    return items


def _mutar(request, diseno, mensaje, operacion):
    """Corre ``operacion`` dentro de una transacción, valida el diseño
    resultante y sube la versión; si no cierra, deshace todo y responde 400."""
    try:
        with transaction.atomic():
            operacion()
            items = _asegurar_coherencia(diseno)
            diseno.tocar(request.user)
    except DisenoInvalido as exc:
        return JsonResponse({"ok": False, "message": _mensaje(exc.errores), "errores": exc.errores}, status=400)
    return _respuesta(request, diseno, mensaje, items=items)


def _siguiente_orden(diseno, padre):
    ultimo = diseno.items.filter(padre=padre).order_by("-orden").values_list("orden", flat=True).first()
    return 0 if ultimo is None else ultimo + 1


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


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
def formulario_datos(request, pk):
    """Los datos del diseño (para refrescar la vista previa sin recargar)."""
    diseno, avisos = _diseno(request, pk)
    return JsonResponse({"ok": True, "datos": _datos(diseno, items_ordenados(diseno)), "avisos": avisos})


# ── Mutaciones ───────────────────────────────────────────────────────────────


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def formulario_mover(request, pk):
    """Drag & drop: ``{clave, padre, posicion}``. Los grupos se mueven en la
    raíz; campos y textos, dentro de un grupo. Si el movimiento deja una
    condición apuntando a una fuente posterior, se rechaza (RN-6)."""
    diseno, _ = _diseno(request, pk)
    payload = _json(request)
    if payload is None or not payload.get("clave"):
        return JsonResponse({"ok": False, "message": "Payload inválido."}, status=400)
    item = _item(diseno, payload["clave"])
    clave_padre = payload.get("padre") or None
    try:
        posicion = int(payload.get("posicion", 0))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "message": "Posición inválida."}, status=400)

    def operacion():
        if item.es_grupo:
            if clave_padre:
                raise DisenoInvalido({item.clave: ["Un grupo no puede ir dentro de otro grupo."]})
            hermanos = [g for g in diseno.items.filter(tipo=GRUPO).order_by("orden", "id") if g.pk != item.pk]
            item.padre = None
        else:
            if not clave_padre:
                raise DisenoInvalido({item.clave: ["Un campo o un texto tiene que estar dentro de un grupo."]})
            padre = _item(diseno, clave_padre)
            if not padre.es_grupo:
                raise DisenoInvalido({item.clave: ["Solo se puede soltar dentro de un grupo."]})
            item.padre = padre
            hermanos = [h for h in padre.hijos.order_by("orden", "id") if h.pk != item.pk]
        destino = max(0, min(posicion, len(hermanos)))
        hermanos.insert(destino, item)
        for orden, hermano in enumerate(hermanos):
            if hermano.pk == item.pk:
                item.orden = orden
                item.save(update_fields=["padre", "orden", "modificado"])
            elif hermano.orden != orden:
                ItemDiseno.objects.filter(pk=hermano.pk).update(orden=orden)

    return _mutar(request, diseno, "Orden guardado.", operacion)


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def formulario_grupo_crear(request, pk):
    diseno, _ = _diseno(request, pk)
    form = ItemGrupoForm(request.POST)
    if not form.is_valid():
        return ajax_errors(form)

    def operacion():
        ItemDiseno.objects.create(
            diseno=diseno,
            tipo=GRUPO,
            clave=nueva_clave("g"),
            orden=_siguiente_orden(diseno, None),
            etiqueta=form.cleaned_data["etiqueta"],
            subtitulo=form.cleaned_data["subtitulo"],
            canal=form.cleaned_data["canal"],
        )

    return _mutar(request, diseno, "Grupo agregado al final del formulario.", operacion)


def _padre_para_nuevo(diseno, request):
    clave_padre = request.POST.get("padre") or ""
    if not clave_padre:
        return None
    padre = diseno.items.filter(clave=clave_padre, tipo=GRUPO).first()
    return padre


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def formulario_texto_crear(request, pk):
    diseno, _ = _diseno(request, pk)
    form = ItemTextoForm(request.POST)
    padre = _padre_para_nuevo(diseno, request)
    if padre is None:
        form.add_error(None, "Elegí el grupo donde va el texto.")
    if not form.is_valid() or padre is None:
        return ajax_errors(form)

    def operacion():
        ItemDiseno.objects.create(
            diseno=diseno,
            tipo=TEXTO,
            clave=nueva_clave("t"),
            padre=padre,
            orden=_siguiente_orden(diseno, padre),
            texto=form.cleaned_data["texto"],
            canal=form.cleaned_data["canal"],
        )

    return _mutar(request, diseno, "Texto agregado.", operacion)


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def formulario_propio_crear(request, pk):
    diseno, _ = _diseno(request, pk)
    form = ItemCampoPropioForm(request.POST)
    padre = _padre_para_nuevo(diseno, request)
    if padre is None:
        form.add_error(None, "Elegí el grupo donde va el campo.")
    if not form.is_valid() or padre is None:
        return ajax_errors(form)

    def operacion():
        ItemDiseno.objects.create(
            diseno=diseno,
            tipo=CAMPO,
            clave=nueva_clave("cp"),
            padre=padre,
            orden=_siguiente_orden(diseno, padre),
            propio=form.cleaned_data["propio"],
            canal=form.cleaned_data["canal"],
        )

    return _mutar(request, diseno, "Campo propio agregado.", operacion)


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def formulario_item_editar(request, pk, clave):
    """Edita lo que el diseño es dueño de cada ítem (RN-2): grupo → título,
    subtítulo y canal; texto → texto y canal; campo propio → todo; campo del
    catálogo → solo la etiqueta."""
    diseno, _ = _diseno(request, pk)
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

    def operacion():
        datos = form.cleaned_data
        if item.es_grupo:
            item.etiqueta, item.subtitulo, item.canal = datos["etiqueta"], datos["subtitulo"], datos["canal"]
            item.save(update_fields=["etiqueta", "subtitulo", "canal", "modificado"])
        elif item.es_texto:
            item.texto, item.canal = datos["texto"], datos["canal"]
            item.save(update_fields=["texto", "canal", "modificado"])
        elif item.es_propio:
            item.propio, item.canal = datos["propio"], datos["canal"]
            item.save(update_fields=["propio", "canal", "modificado"])
        else:
            item.etiqueta = datos["etiqueta"]
            item.save(update_fields=["etiqueta", "modificado"])

    return _mutar(request, diseno, "Cambios guardados.", operacion)


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def formulario_condicion(request, pk, clave):
    """``{condicion: null | {modo, reglas}}``. Se valida contra los ítems
    anteriores (RN-6/RN-7) antes de guardar."""
    diseno, _ = _diseno(request, pk)
    item = _item(diseno, clave)
    payload = _json(request)
    if payload is None or "condicion" not in payload:
        return JsonResponse({"ok": False, "message": "Payload inválido."}, status=400)
    condicion = payload["condicion"]
    if condicion is not None and not isinstance(condicion, dict):
        return JsonResponse({"ok": False, "message": "La condición tiene un formato inválido."}, status=400)
    if condicion is not None and not (condicion.get("reglas") or []):
        condicion = None  # sin reglas = sin condición

    def operacion():
        item.condicion = condicion
        item.save(update_fields=["condicion", "modificado"])

    mensaje = "Condición guardada." if condicion else "Condición quitada: el ítem se muestra siempre."
    return _mutar(request, diseno, mensaje, operacion)


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def formulario_item_eliminar(request, pk, clave):
    """Se eliminan textos, campos propios y grupos vacíos. Los requisitos del
    catálogo no se eliminan del diseño (RN-1): se mueven o se desactivan en el
    catálogo."""
    diseno, _ = _diseno(request, pk)
    item = _item(diseno, clave)
    if item.es_campo and not item.es_propio:
        return JsonResponse(
            {
                "ok": False,
                "message": "Los requisitos del catálogo no se quitan del formulario: movelos de grupo o desactivalos en el catálogo.",
            },
            status=400,
        )
    if item.es_grupo and item.hijos.exists():
        return JsonResponse(
            {"ok": False, "message": "El grupo tiene ítems adentro: movelos antes de eliminarlo."}, status=400
        )

    titulo = item.titulo or item.get_tipo_display()

    def operacion():
        item.delete()

    return _mutar(request, diseno, f"«{titulo}» eliminado.", operacion)


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def formulario_restablecer(request, pk):
    """Vuelve al plan por defecto (grupos del catálogo + un grupo por nivel de
    requisitos). Borra textos, campos propios, condiciones y etiquetas."""
    diseno, _ = _diseno(request, pk)

    def operacion():
        generar_por_defecto(diseno)

    return _mutar(request, diseno, "Formulario restablecido al orden del catálogo.", operacion)
