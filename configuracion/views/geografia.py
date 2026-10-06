from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from core.mixins import TimestampedSuccessUrlMixin
from core.models import Localidad, Municipio, Provincia
from core.rbac import CapacidadRequeridaMixin

from ..forms import LocalidadForm, MunicipioForm, ProvinciaForm

POR_PAGINA = 20


class _ConfigMixin(CapacidadRequeridaMixin):
    """Toda la configuración de geografía requiere config.administrar."""

    capacidades_requeridas = "config.administrar"


def _queryset(modelo):
    """El mismo orden y los mismos `select_related` para el listado y para los errores.

    Antes cada `form_invalid` rearmaba el queryset a mano: el listado de provincias salía
    por `id` y el reintento tras un error por `nombre`, y ninguno de los tres volvía
    paginado (FE-04).
    """
    if modelo is Provincia:
        return Provincia.objects.order_by("nombre")
    if modelo is Municipio:
        return Municipio.objects.select_related("provincia").order_by("nombre")
    return Localidad.objects.select_related("municipio__provincia").order_by("nombre")


def _contexto_lista(request, modelo, clave, form, *, destacado=None, **extra):
    """Contexto de una lista de geografía, paginado igual que su `ListView`.

    ``destacado`` es el registro cuyo modal de edición se va a abrir: la página que se
    devuelve es la que lo contiene, porque si no el error de validación de la fila 21
    volvía a una página 1 donde esa fila no está y el modal no se renderizaba nunca.
    """
    queryset = _queryset(modelo)
    paginator = Paginator(queryset, POR_PAGINA)
    numero = request.GET.get("page")
    if numero is None and destacado is not None:
        pks = list(queryset.values_list("pk", flat=True))
        if destacado.pk in pks:
            numero = pks.index(destacado.pk) // POR_PAGINA + 1
    page_obj = paginator.get_page(numero)
    return {
        clave: page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "form": form,
        **extra,
    }


# ---------------------------------------------------------------------------
# Provincia
# ---------------------------------------------------------------------------


class ProvinciaListView(_ConfigMixin, LoginRequiredMixin, ListView):
    model = Provincia
    template_name = "configuracion/provincia_list.html"
    context_object_name = "provincias"
    paginate_by = POR_PAGINA

    def get_queryset(self):
        return _queryset(Provincia)

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
        return render(
            self.request,
            "configuracion/provincia_list.html",
            _contexto_lista(self.request, Provincia, "provincias", form, abrir_modal_crear=True),
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
        return render(
            self.request,
            "configuracion/provincia_list.html",
            _contexto_lista(
                self.request,
                Provincia,
                "provincias",
                form,
                destacado=self.object,
                abrir_modal_pk=self.object.pk,
            ),
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
    paginate_by = POR_PAGINA

    def get_queryset(self):
        return _queryset(Municipio)

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
        return render(
            self.request,
            "configuracion/municipio_list.html",
            _contexto_lista(self.request, Municipio, "municipios", form, abrir_modal_crear=True),
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
        return render(
            self.request,
            "configuracion/municipio_list.html",
            _contexto_lista(
                self.request,
                Municipio,
                "municipios",
                form,
                destacado=self.object,
                abrir_modal_pk=self.object.pk,
            ),
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
    paginate_by = POR_PAGINA

    def get_queryset(self):
        return _queryset(Localidad)

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
        return render(
            self.request,
            "configuracion/localidad_list.html",
            _contexto_lista(self.request, Localidad, "localidades", form, abrir_modal_crear=True),
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
        return render(
            self.request,
            "configuracion/localidad_list.html",
            _contexto_lista(
                self.request,
                Localidad,
                "localidades",
                form,
                destacado=self.object,
                abrir_modal_pk=self.object.pk,
            ),
        )


class LocalidadDeleteView(_ConfigMixin, LoginRequiredMixin, DeleteView):
    model = Localidad
    template_name = "configuracion/localidad_confirm_delete.html"
    success_url = reverse_lazy("configuracion:localidades")
