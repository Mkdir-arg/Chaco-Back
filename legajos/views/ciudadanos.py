from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView

from core.rbac import CapacidadRequeridaMixin

from ..forms import (
    CiudadanoConfirmarForm,
    CiudadanoManualForm,
    CiudadanoUpdateForm,
    ConsultaRenaperForm,
)
from ..models import Ciudadano
from ..selectors import (
    build_ciudadano_detail_context,
    get_ciudadanos_dashboard_metrics,
    get_ciudadanos_queryset,
)
from ..services import CiudadanosService


class CiudadanoListView(CapacidadRequeridaMixin, LoginRequiredMixin, ListView):
    capacidades_requeridas = "ciudadano.ver"
    model = Ciudadano
    template_name = "legajos/ciudadano_list.html"
    context_object_name = "ciudadanos"
    paginate_by = 20

    def get_queryset(self):
        return get_ciudadanos_queryset(self.request.GET.get("search", ""))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        total_ciudadanos = None
        if not self.request.GET.get("search"):
            total_ciudadanos = context["paginator"].count
        context["metricas"] = get_ciudadanos_dashboard_metrics(total_ciudadanos)
        return context


class CiudadanoDetailView(CapacidadRequeridaMixin, LoginRequiredMixin, DetailView):
    capacidades_requeridas = "ciudadano.ver"
    model = Ciudadano
    template_name = "legajos/ciudadano_detail.html"
    context_object_name = "ciudadano"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(build_ciudadano_detail_context(self.object, user=self.request.user))
        return context


class CiudadanoCreateView(CapacidadRequeridaMixin, LoginRequiredMixin, FormView):
    capacidades_requeridas = "ciudadano.crear"
    template_name = "legajos/ciudadano_renaper_form.html"
    form_class = ConsultaRenaperForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("renaper_error", False)
        return context

    def form_valid(self, form):
        dni = form.cleaned_data["dni"]
        sexo = form.cleaned_data["sexo"]

        if Ciudadano.objects.filter(dni=dni).exists():
            messages.error(self.request, f"Ya existe un ciudadano con DNI {dni}")
            return self.form_invalid(form)

        resultado = CiudadanosService.consultar_renaper(dni, sexo)

        if not resultado["success"]:
            context = self.get_context_data(form=form)
            context["renaper_error"] = True
            context["dni_consultado"] = dni
            context["sexo_consultado"] = sexo

            if resultado.get("fallecido"):
                context["error_message"] = "La persona consultada figura como fallecida en RENAPER"
            else:
                context["error_message"] = (
                    f"No se encontraron datos en RENAPER: {resultado.get('error', 'Error desconocido')}"
                )

            return self.render_to_response(context)

        CiudadanosService.store_renaper_data(self.request.session, resultado)
        return redirect("legajos:ciudadano_confirmar")


class CiudadanoManualView(CapacidadRequeridaMixin, LoginRequiredMixin, CreateView):
    capacidades_requeridas = "ciudadano.crear"
    model = Ciudadano
    form_class = CiudadanoManualForm
    template_name = "legajos/ciudadano_manual_form.html"
    success_url = reverse_lazy("legajos:ciudadanos")

    def get_initial(self):
        initial = super().get_initial()
        cuit = self.request.GET.get("cuit") or self.request.GET.get("dni")
        sexo = self.request.GET.get("sexo")

        if cuit:
            initial["dni"] = CiudadanosService.extract_dni_from_cuit(cuit) or "".join(filter(str.isdigit, cuit))
        if sexo:
            initial["genero"] = sexo
        return initial

    def form_valid(self, form):
        super().form_valid(form)
        CiudadanosService.invalidate_ciudadanos_cache()
        messages.success(
            self.request,
            f"Ciudadano {self.object.nombre} {self.object.apellido} creado exitosamente (carga manual)",
        )

        import time

        return redirect(f"{self.success_url}?t={int(time.time())}")


class CiudadanoConfirmarView(CapacidadRequeridaMixin, LoginRequiredMixin, CreateView):
    capacidades_requeridas = "ciudadano.crear"
    model = Ciudadano
    form_class = CiudadanoConfirmarForm
    template_name = "legajos/ciudadano_confirmar_form.html"
    success_url = reverse_lazy("legajos:ciudadanos")

    def dispatch(self, request, *args, **kwargs):
        if not CiudadanosService.get_renaper_data(request.session):
            messages.error(request, "No hay datos de RENAPER disponibles. Inicie el proceso nuevamente.")
            return redirect("legajos:ciudadano_nuevo")
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        datos = CiudadanosService.get_renaper_data(self.request.session)
        return {
            "dni": datos.get("dni"),
            "nombre": datos.get("nombre"),
            "apellido": datos.get("apellido"),
            "fecha_nacimiento": datos.get("fecha_nacimiento"),
            "genero": datos.get("genero"),
            "domicilio": datos.get("domicilio"),
            "provincia": datos.get("provincia"),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["datos_api"] = CiudadanosService.get_renaper_raw_data(self.request.session)
        return context

    def form_valid(self, form):
        super().form_valid(form)
        CiudadanosService.clear_renaper_data(self.request.session)
        CiudadanosService.invalidate_ciudadanos_cache()
        messages.success(
            self.request,
            f"Ciudadano {self.object.nombre} {self.object.apellido} creado exitosamente",
        )

        import time

        return redirect(f"{self.success_url}?t={int(time.time())}")


class CiudadanoUpdateView(CapacidadRequeridaMixin, LoginRequiredMixin, UpdateView):
    capacidades_requeridas = "ciudadano.editar"
    model = Ciudadano
    form_class = CiudadanoUpdateForm
    template_name = "legajos/ciudadano_edit_form.html"

    def _puede_ver_sensible(self):
        from core.rbac import puede

        return puede(self.request.user, "ciudadano.sensible")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["puede_ver_sensible"] = self._puede_ver_sensible()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["puede_ver_sensible"] = self._puede_ver_sensible()
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        CiudadanosService.invalidate_ciudadanos_cache()
        return response

    def get_success_url(self):
        return reverse_lazy("legajos:ciudadano_detalle", kwargs={"pk": self.object.pk})
