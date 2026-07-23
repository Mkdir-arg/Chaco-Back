from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from programas.forms import CampoTipoDispositivoForm, TipoDispositivoForm
from programas.models import CampoTipoDispositivo, TipoDispositivo
from programas.services.dispositivos import puede_configurar_dispositivos


class ConfigurarDispositivosMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not puede_configurar_dispositivos(request.user):
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
    template_name = "programas/dispositivos/config/tipo_form.html"

    def get_success_url(self):
        messages.success(self.request, "Tipo de dispositivo actualizado.")
        return reverse("dispositivos:tipo_detalle", args=[self.object.pk])


class TipoDispositivoDetailView(ConfigurarDispositivosMixin, DetailView):
    model = TipoDispositivo
    template_name = "programas/dispositivos/config/tipo_detail.html"
    context_object_name = "tipo"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        secciones = {}
        for campo in self.object.campos_configurados.all():
            secciones.setdefault(campo.seccion, []).append(campo)
        context["secciones"] = list(secciones.items())
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
    template_name = "programas/dispositivos/config/campo_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tipo_dispositivo"] = self.object.tipo_dispositivo
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tipo"] = self.object.tipo_dispositivo
        return context

    def get_success_url(self):
        messages.success(self.request, "Campo actualizado.")
        return reverse("dispositivos:tipo_detalle", args=[self.object.tipo_dispositivo_id])


class CampoTipoDispositivoDeleteView(ConfigurarDispositivosMixin, View):
    def post(self, request, pk):
        campo = get_object_or_404(CampoTipoDispositivo, pk=pk)
        tipo_pk = campo.tipo_dispositivo_id
        campo.delete()
        messages.success(request, "Campo eliminado.")
        return redirect("dispositivos:tipo_detalle", pk=tipo_pk)
