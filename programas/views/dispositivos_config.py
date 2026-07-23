from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from programas.forms import CampoTipoDispositivoForm, TipoDispositivoForm
from programas.models import CampoTipoDispositivo, TipoDispositivo
from programas.services.dispositivos import puede_configurar_dispositivos
from programas.views.ajax_utils import ajax_errors, ajax_ok, is_ajax


def _agrupar_campos_por_seccion(tipo):
    secciones = {}
    for campo in tipo.campos_configurados.all():
        secciones.setdefault(campo.seccion, []).append(campo)
    return list(secciones.items())


def _detalle_ajax(request, tipo, message):
    tipo.refresh_from_db()
    return ajax_ok(
        request,
        target="#dispositivos-detail-content",
        partial="programas/dispositivos/config/_tipo_detail_content.html",
        context={
            "tipo": tipo,
            "secciones": _agrupar_campos_por_seccion(tipo),
        },
        message=message,
    )


def _modal_ajax(request, context):
    html = render_to_string(
        "programas/dispositivos/config/_edit_modal.html",
        context,
        request=request,
    )
    return JsonResponse({"ok": True, "html": html})


class ConfigurarDispositivosMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            if is_ajax(request):
                login_response = self.handle_no_permission()
                return JsonResponse(
                    {
                        "ok": False,
                        "message": "Tu sesión venció. Volvé a iniciar sesión.",
                        "redirect": login_response.url,
                    },
                    status=401,
                )
            return self.handle_no_permission()
        if not puede_configurar_dispositivos(request.user):
            if is_ajax(request):
                return JsonResponse(
                    {"ok": False, "message": "No tiene permisos para realizar esta acción."},
                    status=403,
                )
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class TipoDispositivoListView(ConfigurarDispositivosMixin, ListView):
    model = TipoDispositivo
    template_name = "programas/dispositivos/config/tipo_list.html"
    context_object_name = "tipos"

    def get_queryset(self):
        return super().get_queryset().annotate(cantidad_campos=Count("campos_configurados"))


class TipoDispositivoCreateView(ConfigurarDispositivosMixin, CreateView):
    model = TipoDispositivo
    form_class = TipoDispositivoForm
    template_name = "programas/dispositivos/config/tipo_form.html"

    def get_success_url(self):
        messages.success(self.request, "Tipo de dispositivo creado.")
        return reverse("dispositivos:tipo_detalle", args=[self.object.pk])


class TipoDispositivoUpdateView(ConfigurarDispositivosMixin, UpdateView):
    model = TipoDispositivo
    form_class = TipoDispositivoForm
    template_name = "programas/dispositivos/config/tipo_detail.html"
    context_object_name = "tipo"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["secciones"] = _agrupar_campos_por_seccion(self.object)
        context["modal_edicion"] = "tipo"
        context["modal_action"] = reverse("dispositivos:tipo_editar", args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        if is_ajax(request):
            return _modal_ajax(request, context)
        return self.render_to_response(context)

    def form_valid(self, form):
        self.object = form.save()
        if is_ajax(self.request):
            return _detalle_ajax(self.request, self.object, "Tipo de dispositivo actualizado.")
        messages.success(self.request, "Tipo de dispositivo actualizado.")
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        if is_ajax(self.request):
            return ajax_errors(form)
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("dispositivos:tipo_detalle", args=[self.object.pk])


class TipoDispositivoDetailView(ConfigurarDispositivosMixin, DetailView):
    model = TipoDispositivo
    template_name = "programas/dispositivos/config/tipo_detail.html"
    context_object_name = "tipo"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["secciones"] = _agrupar_campos_por_seccion(self.object)
        return context


class TipoDispositivoToggleView(ConfigurarDispositivosMixin, View):
    def post(self, request, pk):
        tipo = get_object_or_404(TipoDispositivo, pk=pk)
        tipo.activo = not tipo.activo
        tipo.save(update_fields=["activo", "modificado"])
        messages.success(request, f"{tipo.nombre} quedó {'activo' if tipo.activo else 'inactivo'}.")
        return redirect("dispositivos:tipo_detalle", pk=tipo.pk)


class CampoTipoDispositivoCreateView(ConfigurarDispositivosMixin, CreateView):
    model = CampoTipoDispositivo
    form_class = CampoTipoDispositivoForm
    template_name = "programas/dispositivos/config/campo_form.html"

    def get_tipo_dispositivo(self):
        if not hasattr(self, "_tipo_dispositivo"):
            self._tipo_dispositivo = get_object_or_404(TipoDispositivo, pk=self.kwargs["tipo_pk"])
        return self._tipo_dispositivo

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tipo_dispositivo"] = self.get_tipo_dispositivo()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tipo"] = self.get_tipo_dispositivo()
        return context

    def get_success_url(self):
        messages.success(self.request, "Campo agregado.")
        return reverse("dispositivos:tipo_detalle", args=[self.get_tipo_dispositivo().pk])


class CampoTipoDispositivoUpdateView(ConfigurarDispositivosMixin, UpdateView):
    model = CampoTipoDispositivo
    form_class = CampoTipoDispositivoForm
    template_name = "programas/dispositivos/config/tipo_detail.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tipo_dispositivo"] = self.object.tipo_dispositivo
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tipo = self.object.tipo_dispositivo
        context["tipo"] = tipo
        context["secciones"] = _agrupar_campos_por_seccion(tipo)
        context["modal_edicion"] = "campo"
        context["modal_action"] = reverse("dispositivos:campo_editar", args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        if is_ajax(request):
            return _modal_ajax(request, context)
        return self.render_to_response(context)

    def form_valid(self, form):
        self.object = form.save()
        tipo = self.object.tipo_dispositivo
        if is_ajax(self.request):
            return _detalle_ajax(self.request, tipo, "Campo actualizado.")
        messages.success(self.request, "Campo actualizado.")
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        if is_ajax(self.request):
            return ajax_errors(form)
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("dispositivos:tipo_detalle", args=[self.object.tipo_dispositivo_id])


class CampoTipoDispositivoDeleteView(ConfigurarDispositivosMixin, View):
    def post(self, request, pk):
        campo = get_object_or_404(CampoTipoDispositivo, pk=pk)
        tipo_pk = campo.tipo_dispositivo_id
        campo.delete()
        messages.success(request, "Campo eliminado.")
        return redirect("dispositivos:tipo_detalle", pk=tipo_pk)
