import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView

from core.rbac import CapacidadRequeridaMixin, puede, requiere

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
        metricas = get_ciudadanos_dashboard_metrics(total_ciudadanos)
        context["metricas"] = metricas
        # `_stat_card.html` recibe el valor **ya formateado**: el «%» lo ponía el template.
        # El dict de métricas está cacheado, así que la clave nueva va al contexto, no adentro.
        context["tasa_adherencia_texto"] = f"{metricas.get('tasa_adherencia', 0)}%"
        context["puede_crear"] = puede(self.request.user, "ciudadano.crear")
        return context


@login_required
@requiere("ciudadano.ver")
def ciudadanos_exportar_csv(request):
    """Exporta los ciudadanos visibles, respetando la búsqueda del listado."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="ciudadanos.csv"'
    response.write("\ufeff")

    writer = csv.writer(response)
    writer.writerow(["DNI", "Apellido", "Nombre", "Sexo", "Fecha de alta"])
    ciudadanos = get_ciudadanos_queryset(request.GET.get("search", ""))
    for ciudadano in ciudadanos.iterator():
        writer.writerow(
            [
                ciudadano.dni,
                ciudadano.apellido,
                ciudadano.nombre,
                ciudadano.get_genero_display(),
                ciudadano.creado.strftime("%d/%m/%Y") if ciudadano.creado else "",
            ]
        )
    return response


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

        # G1c-08: el DNI tipeado ya viene normalizado, pero en la base puede haber
        # personas cargadas antes con puntos (`87.654.321`). Un `filter(dni=dni)`
        # pelado no las ve y el alta crea la **segunda** ficha de la misma persona.
        # `listar_dni_no_normalizados` es el comando que los enumera para P-17.
        if CiudadanosService.existe_con_dni(dni):
            messages.error(self.request, f"Ya existe un ciudadano con DNI {dni}")
            return self.form_invalid(form)

        resultado = CiudadanosService.consultar_renaper(dni, sexo)

        if not resultado["success"]:
            context = self.get_context_data(form=form)
            context["renaper_error"] = True
            context["dni_consultado"] = dni
            context["sexo_consultado"] = sexo

            if resultado.get("fallecido"):
                # D-C08 (default): si desde acá se sigue por la carga manual, el
                # legajo nace con la procedencia que RENAPER informó. El dato viaja
                # por la sesión y no por la query string: así vale venga el link con
                # `?fallecido=1` o sin él.
                CiudadanosService.marcar_fallecido_en_renaper(self.request.session, dni)
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
        # D-C08 (default): la carga manual que viene de un «fallecido» de RENAPER
        # guarda esa procedencia. El flag lo deja el paso anterior en la sesión; si
        # el link trae `?fallecido=1` también vale, para cuando el template lo pase.
        de_fallecido = (
            CiudadanosService.consumir_fallecido_en_renaper(self.request.session, form.cleaned_data.get("dni"))
            or self.request.GET.get("fallecido") == "1"
        )
        if de_fallecido:
            form.instance.estado_renaper = Ciudadano.EstadoRenaper.FALLECIDO
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

    def _sin_datos_de_renaper(self, request):
        """La precondición del paso previo, o `None` si hay datos para confirmar.

        Vive en `get`/`post` y no en `dispatch` (RED-73): arriba de
        `super().dispatch()` corría **antes** que `CapacidadRequeridaMixin` y
        `LoginRequiredMixin`, así que un anónimo terminaba en el alta —no en el
        login— y estrenaba sesión solo para que le colgaran el `messages.error`.
        """
        if CiudadanosService.get_renaper_data(request.session):
            return None
        messages.error(request, "No hay datos de RENAPER disponibles. Inicie el proceso nuevamente.")
        return redirect("legajos:ciudadano_nuevo")

    def get(self, request, *args, **kwargs):
        return self._sin_datos_de_renaper(request) or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self._sin_datos_de_renaper(request) or super().post(request, *args, **kwargs)

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
        # G1c-08: el alta que confirma una consulta a RENAPER deja escrita su
        # procedencia. Sin esto, un legajo validado contra el registro civil y uno
        # tipeado a mano quedaban idénticos en la base.
        form.instance.estado_renaper = Ciudadano.EstadoRenaper.REGISTRADO
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

    def _puede_editar_dni(self):
        """G1c-08: el DNI de un legajo lo cambia quien administra la configuración.

        `config.administrar` es la capacidad que ya tiene el perfil que toca la
        parametría del sistema; no se inventa una nueva para esto.
        """
        from core.rbac import puede

        return puede(self.request.user, "config.administrar")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["puede_ver_sensible"] = self._puede_ver_sensible()
        kwargs["puede_editar_dni"] = self._puede_editar_dni()
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
