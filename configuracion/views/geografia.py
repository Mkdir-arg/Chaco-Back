from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from core.mixins import TimestampedSuccessUrlMixin
from core.models import Localidad, Municipio, Provincia
from core.rbac import CapacidadRequeridaMixin

from ..forms import LocalidadForm, MunicipioForm, ProvinciaForm


class _ConfigMixin(CapacidadRequeridaMixin):
    """Toda la configuración de geografía requiere config.administrar."""

    capacidades_requeridas = "config.administrar"


class ProvinciaListView(_ConfigMixin, LoginRequiredMixin, ListView):
    model = Provincia
    template_name = 'configuracion/provincia_list.html'
    context_object_name = 'provincias'
    paginate_by = 20


class ProvinciaCreateView(_ConfigMixin, LoginRequiredMixin, TimestampedSuccessUrlMixin, CreateView):
    model = Provincia
    form_class = ProvinciaForm
    template_name = 'configuracion/provincia_form.html'
    success_url = reverse_lazy('configuracion:provincias')

    def form_valid(self, form):
        super().form_valid(form)
        return self.redirect_with_timestamp()


class ProvinciaUpdateView(_ConfigMixin, LoginRequiredMixin, TimestampedSuccessUrlMixin, UpdateView):
    model = Provincia
    form_class = ProvinciaForm
    template_name = 'configuracion/provincia_form.html'
    success_url = reverse_lazy('configuracion:provincias')

    def form_valid(self, form):
        super().form_valid(form)
        return self.redirect_with_timestamp()


class ProvinciaDeleteView(_ConfigMixin, LoginRequiredMixin, DeleteView):
    model = Provincia
    template_name = 'configuracion/provincia_confirm_delete.html'
    success_url = reverse_lazy('configuracion:provincias')


class MunicipioListView(_ConfigMixin, LoginRequiredMixin, ListView):
    model = Municipio
    template_name = 'configuracion/municipio_list.html'
    context_object_name = 'municipios'
    paginate_by = 20


class MunicipioCreateView(_ConfigMixin, LoginRequiredMixin, TimestampedSuccessUrlMixin, CreateView):
    model = Municipio
    form_class = MunicipioForm
    template_name = 'configuracion/municipio_form.html'
    success_url = reverse_lazy('configuracion:municipios')

    def form_valid(self, form):
        super().form_valid(form)
        return self.redirect_with_timestamp()


class MunicipioUpdateView(_ConfigMixin, LoginRequiredMixin, TimestampedSuccessUrlMixin, UpdateView):
    model = Municipio
    form_class = MunicipioForm
    template_name = 'configuracion/municipio_form.html'
    success_url = reverse_lazy('configuracion:municipios')

    def form_valid(self, form):
        super().form_valid(form)
        return self.redirect_with_timestamp()


class MunicipioDeleteView(_ConfigMixin, LoginRequiredMixin, DeleteView):
    model = Municipio
    template_name = 'configuracion/municipio_confirm_delete.html'
    success_url = reverse_lazy('configuracion:municipios')


class LocalidadListView(_ConfigMixin, LoginRequiredMixin, ListView):
    model = Localidad
    template_name = 'configuracion/localidad_list.html'
    context_object_name = 'localidades'
    paginate_by = 20


class LocalidadCreateView(_ConfigMixin, LoginRequiredMixin, TimestampedSuccessUrlMixin, CreateView):
    model = Localidad
    form_class = LocalidadForm
    template_name = 'configuracion/localidad_form.html'
    success_url = reverse_lazy('configuracion:localidades')

    def form_valid(self, form):
        super().form_valid(form)
        return self.redirect_with_timestamp()


class LocalidadUpdateView(_ConfigMixin, LoginRequiredMixin, TimestampedSuccessUrlMixin, UpdateView):
    model = Localidad
    form_class = LocalidadForm
    template_name = 'configuracion/localidad_form.html'
    success_url = reverse_lazy('configuracion:localidades')

    def form_valid(self, form):
        super().form_valid(form)
        return self.redirect_with_timestamp()


class LocalidadDeleteView(_ConfigMixin, LoginRequiredMixin, DeleteView):
    model = Localidad
    template_name = 'configuracion/localidad_confirm_delete.html'
    success_url = reverse_lazy('configuracion:localidades')
