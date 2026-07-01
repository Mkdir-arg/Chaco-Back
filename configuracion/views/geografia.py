from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from core.mixins import TimestampedSuccessUrlMixin
from core.models import Localidad, Municipio, Provincia
from core.rbac import CapacidadRequeridaMixin

from ..forms import LocalidadForm, MunicipioForm, ProvinciaForm


class _ConfigMixin(CapacidadRequeridaMixin):
    """Toda la configuración de geografía requiere config.administrar."""

    capacidades_requeridas = "config.administrar"


# ---------------------------------------------------------------------------
# Provincia
# ---------------------------------------------------------------------------


class ProvinciaListView(_ConfigMixin, LoginRequiredMixin, ListView):
    model = Provincia
    template_name = "configuracion/provincia_list.html"
    context_object_name = "provincias"
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("form", ProvinciaForm())
        return context


class ProvinciaCreateView(_ConfigMixin, LoginRequiredMixin, TimestampedSuccessUrlMixin, CreateView):
    model = Provincia
    form_class = ProvinciaForm
    template_name = "configuracion/provincia_form.html"
    success_url = reverse_lazy("configuracion:provincias")

    def form_valid(self, form):
        super().form_valid(form)
        return self.redirect_with_timestamp()

    def form_invalid(self, form):
        provincias = Provincia.objects.all().order_by("nombre")
        return render(
            self.request,
            "configuracion/provincia_list.html",
            {
                "provincias": provincias,
                "form": form,
                "abrir_modal_crear": True,
            },
        )


class ProvinciaUpdateView(_ConfigMixin, LoginRequiredMixin, TimestampedSuccessUrlMixin, UpdateView):
    model = Provincia
    form_class = ProvinciaForm
    template_name = "configuracion/provincia_form.html"
    success_url = reverse_lazy("configuracion:provincias")

    def form_valid(self, form):
        super().form_valid(form)
        return self.redirect_with_timestamp()

    def form_invalid(self, form):
        provincias = Provincia.objects.all().order_by("nombre")
        return render(
            self.request,
            "configuracion/provincia_list.html",
            {
                "provincias": provincias,
                "form": form,
                "abrir_modal_pk": self.object.pk,
            },
        )


class ProvinciaDeleteView(_ConfigMixin, LoginRequiredMixin, DeleteView):
    model = Provincia
    template_name = "configuracion/provincia_confirm_delete.html"
    success_url = reverse_lazy("configuracion:provincias")


# ---------------------------------------------------------------------------
# Municipio
# ---------------------------------------------------------------------------


class MunicipioListView(_ConfigMixin, LoginRequiredMixin, ListView):
    model = Municipio
    template_name = "configuracion/municipio_list.html"
    context_object_name = "municipios"
    paginate_by = 20

    def get_queryset(self):
        return Municipio.objects.select_related("provincia").order_by("nombre")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("form", MunicipioForm())
        return context


class MunicipioCreateView(_ConfigMixin, LoginRequiredMixin, TimestampedSuccessUrlMixin, CreateView):
    model = Municipio
    form_class = MunicipioForm
    template_name = "configuracion/municipio_form.html"
    success_url = reverse_lazy("configuracion:municipios")

    def form_valid(self, form):
        super().form_valid(form)
        return self.redirect_with_timestamp()

    def form_invalid(self, form):
        municipios = Municipio.objects.select_related("provincia").order_by("nombre")
        return render(
            self.request,
            "configuracion/municipio_list.html",
            {
                "municipios": municipios,
                "form": form,
                "abrir_modal_crear": True,
            },
        )


class MunicipioUpdateView(_ConfigMixin, LoginRequiredMixin, TimestampedSuccessUrlMixin, UpdateView):
    model = Municipio
    form_class = MunicipioForm
    template_name = "configuracion/municipio_form.html"
    success_url = reverse_lazy("configuracion:municipios")

    def form_valid(self, form):
        super().form_valid(form)
        return self.redirect_with_timestamp()

    def form_invalid(self, form):
        municipios = Municipio.objects.select_related("provincia").order_by("nombre")
        return render(
            self.request,
            "configuracion/municipio_list.html",
            {
                "municipios": municipios,
                "form": form,
                "abrir_modal_pk": self.object.pk,
            },
        )


class MunicipioDeleteView(_ConfigMixin, LoginRequiredMixin, DeleteView):
    model = Municipio
    template_name = "configuracion/municipio_confirm_delete.html"
    success_url = reverse_lazy("configuracion:municipios")


# ---------------------------------------------------------------------------
# Localidad
# ---------------------------------------------------------------------------


class LocalidadListView(_ConfigMixin, LoginRequiredMixin, ListView):
    model = Localidad
    template_name = "configuracion/localidad_list.html"
    context_object_name = "localidades"
    paginate_by = 20

    def get_queryset(self):
        return Localidad.objects.select_related("municipio__provincia").order_by("nombre")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("form", LocalidadForm())
        return context


class LocalidadCreateView(_ConfigMixin, LoginRequiredMixin, TimestampedSuccessUrlMixin, CreateView):
    model = Localidad
    form_class = LocalidadForm
    template_name = "configuracion/localidad_form.html"
    success_url = reverse_lazy("configuracion:localidades")

    def form_valid(self, form):
        super().form_valid(form)
        return self.redirect_with_timestamp()

    def form_invalid(self, form):
        localidades = Localidad.objects.select_related("municipio__provincia").order_by("nombre")
        return render(
            self.request,
            "configuracion/localidad_list.html",
            {
                "localidades": localidades,
                "form": form,
                "abrir_modal_crear": True,
            },
        )


class LocalidadUpdateView(_ConfigMixin, LoginRequiredMixin, TimestampedSuccessUrlMixin, UpdateView):
    model = Localidad
    form_class = LocalidadForm
    template_name = "configuracion/localidad_form.html"
    success_url = reverse_lazy("configuracion:localidades")

    def form_valid(self, form):
        super().form_valid(form)
        return self.redirect_with_timestamp()

    def form_invalid(self, form):
        localidades = Localidad.objects.select_related("municipio__provincia").order_by("nombre")
        return render(
            self.request,
            "configuracion/localidad_list.html",
            {
                "localidades": localidades,
                "form": form,
                "abrir_modal_pk": self.object.pk,
            },
        )


class LocalidadDeleteView(_ConfigMixin, LoginRequiredMixin, DeleteView):
    model = Localidad
    template_name = "configuracion/localidad_confirm_delete.html"
    success_url = reverse_lazy("configuracion:localidades")
