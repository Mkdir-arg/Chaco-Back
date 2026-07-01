from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, ProtectedError
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from core.models import Secretaria, Subsecretaria
from core.rbac import CapacidadRequeridaMixin

from ..forms.secretaria import SecretariaForm, SubsecretariaForm

_CAPS = ["config.administrar"]
_REDIRECT = "/"


# ---------------------------------------------------------------------------
# Secretaría
# ---------------------------------------------------------------------------


class SecretariaListView(LoginRequiredMixin, CapacidadRequeridaMixin, ListView):
    model = Secretaria
    template_name = "configuracion/secretaria_list.html"
    context_object_name = "secretarias"
    capacidades_requeridas = _CAPS
    redirect_sin_permiso = _REDIRECT

    def get_queryset(self):
        qs = Secretaria.objects.annotate(cant_subsecretarias=Count("subsecretarias"))
        search = self.request.GET.get("search", "")
        if search:
            qs = qs.filter(nombre__icontains=search)
        return qs.order_by("nombre")

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
        secretarias = Secretaria.objects.annotate(cant_subsecretarias=Count("subsecretarias")).order_by("nombre")
        return render(
            self.request,
            "configuracion/secretaria_list.html",
            {
                "secretarias": secretarias,
                "search": "",
                "form": form,
                "abrir_modal_crear": True,
            },
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
        secretarias = Secretaria.objects.annotate(cant_subsecretarias=Count("subsecretarias")).order_by("nombre")
        return render(
            self.request,
            "configuracion/secretaria_list.html",
            {
                "secretarias": secretarias,
                "search": "",
                "form": form,
                "abrir_modal_pk": self.object.pk,
            },
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

    def get_queryset(self):
        qs = Subsecretaria.objects.select_related("secretaria").annotate(cant_programas=Count("programa"))
        secretaria_id = self.request.GET.get("secretaria")
        if secretaria_id:
            qs = qs.filter(secretaria_id=secretaria_id)
        return qs.order_by("secretaria__nombre", "nombre")

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
        subsecretarias = (
            Subsecretaria.objects.select_related("secretaria")
            .annotate(cant_programas=Count("programa"))
            .order_by("secretaria__nombre", "nombre")
        )
        return render(
            self.request,
            "configuracion/subsecretaria_list.html",
            {
                "subsecretarias": subsecretarias,
                "secretarias": Secretaria.objects.filter(activo=True).order_by("nombre"),
                "secretaria_filtro": "",
                "form": form,
                "abrir_modal_crear": True,
            },
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
        subsecretarias = (
            Subsecretaria.objects.select_related("secretaria")
            .annotate(cant_programas=Count("programa"))
            .order_by("secretaria__nombre", "nombre")
        )
        return render(
            self.request,
            "configuracion/subsecretaria_list.html",
            {
                "subsecretarias": subsecretarias,
                "secretarias": Secretaria.objects.filter(activo=True).order_by("nombre"),
                "secretaria_filtro": "",
                "form": form,
                "abrir_modal_pk": self.object.pk,
            },
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
