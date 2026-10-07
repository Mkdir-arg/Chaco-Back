from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count, ProtectedError
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from core.models import Secretaria, Subsecretaria
from core.rbac import CapacidadRequeridaMixin

from ..forms.secretaria import SecretariaForm, SubsecretariaForm

_CAPS = ["config.administrar"]
_REDIRECT = "/"
#: Mismo tamaño que las tres listas de Geografía (FE-04).
POR_PAGINA = 20


def _secretarias_qs():
    return Secretaria.objects.annotate(cant_subsecretarias=Count("subsecretarias")).order_by("nombre")


def _subsecretarias_qs():
    return (
        Subsecretaria.objects.select_related("secretaria")
        .annotate(cant_programas=Count("programa"))
        .order_by("secretaria__nombre", "nombre")
    )


def _contexto_lista(request, queryset, clave, form, *, destacado=None, **extra):
    """Contexto de una lista de Secretarías paginado igual que su `ListView` (FE-17).

    ``destacado`` es el registro cuyo modal de edición se va a abrir: se devuelve la
    página que lo contiene, porque si no el error de validación de una fila de la página
    2 vuelve a una página 1 donde esa fila no está y el modal no se renderiza nunca
    (mismo tratamiento que `views/geografia.py`, FE-04).
    """
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
# Secretaría
# ---------------------------------------------------------------------------


class SecretariaListView(LoginRequiredMixin, CapacidadRequeridaMixin, ListView):
    model = Secretaria
    template_name = "configuracion/secretaria_list.html"
    context_object_name = "secretarias"
    capacidades_requeridas = _CAPS
    redirect_sin_permiso = _REDIRECT
    paginate_by = POR_PAGINA

    def get_queryset(self):
        qs = _secretarias_qs()
        search = self.request.GET.get("search", "")
        if search:
            qs = qs.filter(nombre__icontains=search)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search"] = self.request.GET.get("search", "")
        context.setdefault("form", SecretariaForm())
        return context


class SecretariaCreateView(LoginRequiredMixin, CapacidadRequeridaMixin, CreateView):
    model = Secretaria
    form_class = SecretariaForm
    template_name = "configuracion/secretaria_form.html"
    success_url = reverse_lazy("configuracion:secretarias")
    capacidades_requeridas = _CAPS
    redirect_sin_permiso = _REDIRECT

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Secretaría "{self.object.nombre}" creada exitosamente.')
        return response

    def form_invalid(self, form):
        return render(
            self.request,
            "configuracion/secretaria_list.html",
            _contexto_lista(self.request, _secretarias_qs(), "secretarias", form, search="", abrir_modal_crear=True),
        )


class SecretariaUpdateView(LoginRequiredMixin, CapacidadRequeridaMixin, UpdateView):
    model = Secretaria
    form_class = SecretariaForm
    template_name = "configuracion/secretaria_form.html"
    success_url = reverse_lazy("configuracion:secretarias")
    capacidades_requeridas = _CAPS
    redirect_sin_permiso = _REDIRECT

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Secretaría "{self.object.nombre}" actualizada.')
        return response

    def form_invalid(self, form):
        return render(
            self.request,
            "configuracion/secretaria_list.html",
            _contexto_lista(
                self.request,
                _secretarias_qs(),
                "secretarias",
                form,
                destacado=self.object,
                search="",
                abrir_modal_pk=self.object.pk,
            ),
        )


class SecretariaDeleteView(LoginRequiredMixin, CapacidadRequeridaMixin, DeleteView):
    model = Secretaria
    template_name = "configuracion/secretaria_confirm_delete.html"
    success_url = reverse_lazy("configuracion:secretarias")
    capacidades_requeridas = _CAPS
    redirect_sin_permiso = _REDIRECT

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            nombre = self.object.nombre
            self.object.delete()
            messages.success(request, f'Secretaría "{nombre}" eliminada.')
            return redirect(self.success_url)
        except ProtectedError:
            messages.error(request, "No se puede eliminar esta secretaría porque tiene subsecretarías asociadas.")
            return redirect(self.success_url)


# ---------------------------------------------------------------------------
# Subsecretaría
# ---------------------------------------------------------------------------


class SubsecretariaListView(LoginRequiredMixin, CapacidadRequeridaMixin, ListView):
    model = Subsecretaria
    template_name = "configuracion/subsecretaria_list.html"
    context_object_name = "subsecretarias"
    capacidades_requeridas = _CAPS
    redirect_sin_permiso = _REDIRECT
    paginate_by = POR_PAGINA

    def get_queryset(self):
        qs = _subsecretarias_qs()
        secretaria_id = self.request.GET.get("secretaria")
        if secretaria_id:
            qs = qs.filter(secretaria_id=secretaria_id)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["secretarias"] = Secretaria.objects.filter(activo=True).order_by("nombre")
        context["secretaria_filtro"] = self.request.GET.get("secretaria", "")
        context.setdefault("form", SubsecretariaForm())
        return context


class SubsecretariaCreateView(LoginRequiredMixin, CapacidadRequeridaMixin, CreateView):
    model = Subsecretaria
    form_class = SubsecretariaForm
    template_name = "configuracion/subsecretaria_form.html"
    success_url = reverse_lazy("configuracion:subsecretarias")
    capacidades_requeridas = _CAPS
    redirect_sin_permiso = _REDIRECT

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Subsecretaría "{self.object.nombre}" creada exitosamente.')
        return response

    def form_invalid(self, form):
        return render(
            self.request,
            "configuracion/subsecretaria_list.html",
            _contexto_lista(
                self.request,
                _subsecretarias_qs(),
                "subsecretarias",
                form,
                secretarias=Secretaria.objects.filter(activo=True).order_by("nombre"),
                secretaria_filtro="",
                abrir_modal_crear=True,
            ),
        )


class SubsecretariaUpdateView(LoginRequiredMixin, CapacidadRequeridaMixin, UpdateView):
    model = Subsecretaria
    form_class = SubsecretariaForm
    template_name = "configuracion/subsecretaria_form.html"
    success_url = reverse_lazy("configuracion:subsecretarias")
    capacidades_requeridas = _CAPS
    redirect_sin_permiso = _REDIRECT

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Subsecretaría "{self.object.nombre}" actualizada.')
        return response

    def form_invalid(self, form):
        return render(
            self.request,
            "configuracion/subsecretaria_list.html",
            _contexto_lista(
                self.request,
                _subsecretarias_qs(),
                "subsecretarias",
                form,
                destacado=self.object,
                secretarias=Secretaria.objects.filter(activo=True).order_by("nombre"),
                secretaria_filtro="",
                abrir_modal_pk=self.object.pk,
            ),
        )


class SubsecretariaDeleteView(LoginRequiredMixin, CapacidadRequeridaMixin, DeleteView):
    model = Subsecretaria
    template_name = "configuracion/subsecretaria_confirm_delete.html"
    success_url = reverse_lazy("configuracion:subsecretarias")
    capacidades_requeridas = _CAPS
    redirect_sin_permiso = _REDIRECT

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            nombre = self.object.nombre
            self.object.delete()
            messages.success(request, f'Subsecretaría "{nombre}" eliminada.')
            return redirect(self.success_url)
        except ProtectedError:
            messages.error(request, "No se puede eliminar esta subsecretaría porque tiene programas asociados.")
            return redirect(self.success_url)
