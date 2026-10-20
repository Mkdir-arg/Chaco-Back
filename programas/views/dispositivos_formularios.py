"""Formularios por tipo de dispositivo (P17): alta, editor, mutaciones y baja.

Un tipo tiene a lo sumo un formulario por momento (``MomentoFormulario``). El
editor es el constructor de Becas —mismo motor, mismos parciales, mismo JS— con
otro dueño: las mutaciones corren por ``programas.services.constructor`` (candado,
coherencia de condiciones y versión) y acá solo se resuelve el acceso. Sin canal
app/link: todo ítem se pide en «ambos» y el control no se muestra.

Permisos: los de la configuración de tipos (``ConfigurarDispositivosMixin``). Un
tipo o un momento inexistentes responden 404.
"""

from __future__ import annotations

import json

from django.contrib import messages
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views import View

from core.http import error_json, ok_json
from programas.forms import (
    FormularioTipoNuevoForm,
    ItemCampoPropioForm,
    ItemEtiquetaForm,
    ItemGrupoForm,
    ItemTextoForm,
)
from programas.mixins_dispositivos import ConfigurarDispositivosMixin
from programas.models import CanalFormulario, DisenoFormulario, PresentacionCampo, TipoCampo, TipoDispositivo
from programas.services import constructor
from programas.services.diseno import items_ordenados
from programas.services.formularios_tipo import (
    DADO_DE_BAJA,
    SE_COMPLETA_EN,
    crear_formulario,
    eliminar_formulario,
    momentos_libres,
    reactivar_formulario,
)
from programas.validadores import validar_condicion_json
from programas.views.ajax_utils import ajax_errors

TARGET = "#constructor-items"
PARTIAL = "programas/becas/formulario/_constructor_items.html"
VACIO_TEXTO = "Este formulario todavía no tiene preguntas. Agregá un grupo para empezar."


# ── Acceso ───────────────────────────────────────────────────────────────────


def _formulario(pk, momento):
    """El formulario del momento para el tipo, o 404 si el tipo o el momento no existen."""
    return get_object_or_404(
        DisenoFormulario.objects.select_related("tipo_dispositivo"),
        tipo_dispositivo_id=pk,
        momento=momento,
    )


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


def _en_ambos(form):
    """El formulario de un tipo no se divide por canal: todo se pide en «ambos»,
    venga lo que venga en el POST."""
    if "canal" in form.cleaned_data:
        form.cleaned_data["canal"] = CanalFormulario.AMBOS
    return form.cleaned_data


# ── Datos para la pantalla ───────────────────────────────────────────────────


def _contexto(diseno, items=None):
    if items is None:
        items = items_ordenados(diseno)
    return {
        "tipo": diseno.tipo_dispositivo,
        "diseno": diseno,
        "items": items,
        "arbol": constructor.arbol(items),
        "datos": constructor.datos(diseno, items),
        "avisos": {},
        "vacio_texto": VACIO_TEXTO,
    }


def _respuesta(request, diseno, mensaje, items):
    ctx = _contexto(diseno, items)
    html = render_to_string(PARTIAL, ctx, request=request)
    return ok_json(target=TARGET, html=html, message=mensaje, datos=ctx["datos"], avisos=ctx["avisos"])


def _mutar(request, diseno, mensaje, operacion):
    try:
        items = constructor.mutar(diseno, request.user, operacion)
    except constructor.DisenoInvalido as exc:
        return error_json(exc.mensaje, errores=exc.errores)
    return _respuesta(request, diseno, mensaje, items)


# ── Alta y baja del formulario ───────────────────────────────────────────────


class FormularioTipoCrearView(ConfigurarDispositivosMixin, View):
    """«Nuevo formulario»: elige un momento libre, crea el formulario vacío y
    abre el editor."""

    http_method_names = ["post"]

    def post(self, request, pk):
        tipo = get_object_or_404(TipoDispositivo, pk=pk)
        ocupados = tipo.formularios.values_list("momento", flat=True)
        form = FormularioTipoNuevoForm(request.POST, momentos=momentos_libres(ocupados))
        if not form.is_valid():
            messages.error(request, "Elegí uno de los formularios que el tipo todavía no tiene.")
            return redirect("dispositivos:tipo_detalle", pk=tipo.pk)
        try:
            formulario = crear_formulario(tipo, form.cleaned_data["momento"], request.user)
        except DjangoValidationError as error:
            messages.error(request, " ".join(error.messages))
            return redirect("dispositivos:tipo_detalle", pk=tipo.pk)
        messages.success(request, f"Formulario «{formulario.get_momento_display()}» creado.")
        return redirect("dispositivos:formulario_editor", pk=tipo.pk, momento=formulario.momento)


class FormularioTipoEliminarView(ConfigurarDispositivosMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk, momento):
        formulario = _formulario(pk, momento)
        nombre = formulario.get_momento_display()
        try:
            resultado = eliminar_formulario(formulario)
        except DjangoValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            if resultado == DADO_DE_BAJA:
                messages.success(request, f"Formulario «{nombre}» dado de baja: ya tenía respuestas.")
            else:
                messages.success(request, f"Formulario «{nombre}» eliminado.")
        return redirect("dispositivos:tipo_detalle", pk=pk)


class FormularioTipoReactivarView(ConfigurarDispositivosMixin, View):
    """Vuelve a pedir un formulario dado de baja, con sus preguntas y su versión."""

    http_method_names = ["post"]

    def post(self, request, pk, momento):
        formulario = _formulario(pk, momento)
        reactivar_formulario(formulario)
        messages.success(request, f"Formulario «{formulario.get_momento_display()}» reactivado.")
        return redirect("dispositivos:tipo_detalle", pk=pk)


# ── Editor ───────────────────────────────────────────────────────────────────


class FormularioTipoEditorView(ConfigurarDispositivosMixin, View):
    """El constructor sobre el formulario de un momento del tipo."""

    def get(self, request, pk, momento):
        formulario = _formulario(pk, momento)
        ctx = _contexto(formulario)
        ctx.update(
            {
                "se_completa_en": SE_COMPLETA_EN.get(formulario.momento, ""),
                "canal_choices": CanalFormulario.choices,
                "tipo_choices": TipoCampo.choices,
                "presentacion_choices": PresentacionCampo.choices,
                "operadores": constructor.operadores(),
            }
        )
        return render(request, "programas/dispositivos/config/formulario_editor.html", ctx)


# ── Mutaciones ───────────────────────────────────────────────────────────────


class _MutacionView(ConfigurarDispositivosMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk, momento, clave=None):
        formulario = _formulario(pk, momento)
        return self.mutacion(request, formulario, clave)

    def mutacion(self, request, formulario, clave):  # pragma: no cover - abstracta
        raise NotImplementedError


class FormularioTipoMoverView(_MutacionView):
    """Drag & drop: ``{clave, padre, posicion}``."""

    def mutacion(self, request, formulario, clave):
        payload = _json(request)
        if payload is None or not payload.get("clave"):
            return error_json("Payload inválido.")
        item = _item(formulario, payload["clave"])
        clave_padre = payload.get("padre") or None
        try:
            posicion = int(payload.get("posicion", 0))
        except (TypeError, ValueError):
            return error_json("Posición inválida.")
        return _mutar(
            request,
            formulario,
            "Orden guardado.",
            lambda: constructor.mover(formulario, item, clave_padre, posicion),
        )


class FormularioTipoGrupoView(_MutacionView):
    def mutacion(self, request, formulario, clave):
        form = ItemGrupoForm(request.POST)
        if not form.is_valid():
            return ajax_errors(form)
        datos = _en_ambos(form)
        return _mutar(
            request,
            formulario,
            "Grupo agregado al final del formulario.",
            lambda: constructor.crear_grupo(formulario, datos),
        )


class FormularioTipoTextoView(_MutacionView):
    def mutacion(self, request, formulario, clave):
        form = ItemTextoForm(request.POST)
        padre = constructor.padre_para_nuevo(formulario, request.POST.get("padre") or "")
        if padre is None:
            form.add_error(None, "Elegí el grupo donde va el texto.")
        if not form.is_valid() or padre is None:
            return ajax_errors(form)
        datos = _en_ambos(form)
        return _mutar(request, formulario, "Texto agregado.", lambda: constructor.crear_texto(formulario, padre, datos))


class FormularioTipoPropioView(_MutacionView):
    def mutacion(self, request, formulario, clave):
        form = ItemCampoPropioForm(request.POST, permite_archivo=True)
        padre = constructor.padre_para_nuevo(formulario, request.POST.get("padre") or "")
        if padre is None:
            form.add_error(None, "Elegí el grupo donde va el campo.")
        if not form.is_valid() or padre is None:
            return ajax_errors(form)
        datos = _en_ambos(form)
        return _mutar(
            request,
            formulario,
            "Campo propio agregado.",
            lambda: constructor.crear_propio(formulario, padre, datos),
        )


class FormularioTipoItemEditarView(_MutacionView):
    def mutacion(self, request, formulario, clave):
        item = _item(formulario, clave)
        if item.es_grupo:
            form = ItemGrupoForm(request.POST)
        elif item.es_texto:
            form = ItemTextoForm(request.POST)
        elif item.es_propio:
            form = ItemCampoPropioForm(request.POST, permite_archivo=True)
        else:
            form = ItemEtiquetaForm(request.POST)
        if not form.is_valid():
            return ajax_errors(form)
        datos = _en_ambos(form)
        return _mutar(request, formulario, "Cambios guardados.", lambda: constructor.editar(item, datos))


class FormularioTipoCondicionView(_MutacionView):
    """``{condicion: null | {modo, reglas}}``, validada contra los ítems anteriores."""

    def mutacion(self, request, formulario, clave):
        item = _item(formulario, clave)
        payload = _json(request)
        if payload is None or "condicion" not in payload:
            return error_json("Payload inválido.")
        condicion = payload["condicion"]
        if condicion is not None and not isinstance(condicion, dict):
            return error_json("La condición tiene un formato inválido.")
        if condicion is not None and not (condicion.get("reglas") or []):
            condicion = None  # sin reglas = sin condición
        try:
            validar_condicion_json(condicion)
        except DjangoValidationError as error:
            return error_json(" ".join(error.messages))
        mensaje = "Condición guardada." if condicion else "Condición quitada: el ítem se muestra siempre."
        return _mutar(request, formulario, mensaje, lambda: constructor.poner_condicion(item, condicion))


class FormularioTipoItemEliminarView(_MutacionView):
    def mutacion(self, request, formulario, clave):
        item = _item(formulario, clave)
        motivo = constructor.motivo_para_no_eliminar(item)
        if motivo:
            return error_json(motivo)
        titulo = item.titulo or item.get_tipo_display()
        return _mutar(request, formulario, f"«{titulo}» eliminado.", item.delete)
