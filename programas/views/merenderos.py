"""Vistas del backoffice del programa Merenderos."""

from calendar import monthrange
from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView

from programas.forms import EntregaMercaderiaForm, SolicitudMerenderoForm
from programas.models import Merendero, PrestacionDiaria, PrestacionMensual, SolicitudMerendero
from programas.services.merenderos import (
    aprobar_solicitud,
    guardar_prestacion,
    reenviar_solicitud,
    registrar_entrega,
    resolver_solicitud,
)


def _programa_merenderos():
    from programas.models import Programa

    return Programa.objects.filter(codigo=Programa.TipoPrograma.MERENDEROS).first()


def _puede_en_merenderos(user, capacidad):
    from core.rbac import puede

    programa = _programa_merenderos()
    return programa is not None and puede(user, capacidad, programa=programa)


class MerenderosPermissionMixin(LoginRequiredMixin):
    capacidad_requerida = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not _puede_en_merenderos(request.user, self.capacidad_requerida):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class MerenderoListView(MerenderosPermissionMixin, ListView):
    capacidad_requerida = "merendero.ver"
    model = Merendero
    context_object_name = "merenderos"
    template_name = "programas/merenderos/list.html"

    def get_queryset(self):
        queryset = Merendero.objects.all()
        estado = self.request.GET.get("estado")
        termino = self.request.GET.get("q", "").strip()
        if estado:
            queryset = queryset.filter(estado=estado)
        if termino:
            queryset = queryset.filter(nombre__icontains=termino)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["estados"] = Merendero.Estado.choices
        return context


class SolicitudMerenderoCreateView(MerenderosPermissionMixin, CreateView):
    capacidad_requerida = "merendero.crear"
    model = SolicitudMerendero
    form_class = SolicitudMerenderoForm
    template_name = "programas/merenderos/solicitud_form.html"

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.estado = SolicitudMerendero.Estado.EN_REVISION
        self.object.save()
        messages.success(self.request, "Solicitud enviada a revisión.")
        return redirect("merenderos:solicitudes")


class SolicitudMerenderoListView(MerenderosPermissionMixin, ListView):
    capacidad_requerida = "merendero.ver"
    model = SolicitudMerendero
    context_object_name = "solicitudes"
    template_name = "programas/merenderos/solicitudes.html"


class SolicitudMerenderoResolverView(MerenderosPermissionMixin, View):
    capacidad_requerida = "merendero.validar"

    def post(self, request, pk, accion):
        solicitud = get_object_or_404(SolicitudMerendero, pk=pk)
        try:
            if accion == "reenviar":
                reenviar_solicitud(solicitud)
                messages.success(request, "Solicitud reenviada a revisión.")
                return redirect("merenderos:solicitudes")
            if accion == "aprobar":
                merendero = aprobar_solicitud(solicitud, request.user)
                messages.success(request, f"Solicitud aprobada. Se creó {merendero.nombre}.")
                return redirect("merenderos:detalle", pk=merendero.pk)
            estados = {
                "observar": SolicitudMerendero.Estado.OBSERVADA,
                "rechazar": SolicitudMerendero.Estado.RECHAZADA,
            }
            if accion not in estados:
                return HttpResponseBadRequest("Acción inválida.")
            resolver_solicitud(
                solicitud,
                estado=estados[accion],
                observaciones=request.POST.get("motivo", ""),
                usuario=request.user,
            )
            messages.success(request, "Solicitud actualizada.")
        except ValidationError as error:
            messages.error(request, error.messages[0])
        return redirect("merenderos:solicitudes")


class MerenderoDetailView(MerenderosPermissionMixin, DetailView):
    capacidad_requerida = "merendero.ver"
    model = Merendero
    context_object_name = "merendero"
    template_name = "programas/merenderos/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entregas"] = self.object.entregas_mercaderia.filter(anulada=False)
        context["puede_entregar"] = _puede_en_merenderos(self.request.user, "merendero.entregar")
        context["puede_editar"] = _puede_en_merenderos(self.request.user, "merendero.editar")
        return context


class EntregaMercaderiaCreateView(MerenderosPermissionMixin, CreateView):
    capacidad_requerida = "merendero.entregar"
    model = Merendero
    form_class = EntregaMercaderiaForm
    template_name = "programas/merenderos/entrega_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.merendero = get_object_or_404(Merendero, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            registrar_entrega(self.merendero, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, "Entrega registrada.")
        return redirect("merenderos:detalle", pk=self.merendero.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["merendero"] = self.merendero
        return context


class MerenderoEstadoView(MerenderosPermissionMixin, View):
    capacidad_requerida = "merendero.editar"

    def post(self, request, pk, estado):
        merendero = get_object_or_404(Merendero, pk=pk)
        destinos = {"suspender": Merendero.Estado.SUSPENDIDO, "cerrar": Merendero.Estado.CERRADO}
        if estado not in destinos:
            return HttpResponseBadRequest("Acción inválida.")
        merendero.estado = destinos[estado]
        merendero.save(update_fields=["estado", "modificado"])
        messages.success(request, "Estado del merendero actualizado.")
        return redirect("merenderos:detalle", pk=merendero.pk)


class PrestacionMensualView(MerenderosPermissionMixin, View):
    capacidad_requerida = "merendero.entregar"
    template_name = "programas/merenderos/prestacion_mensual.html"

    def _contexto(self, request, merendero, anio, mes):
        if not 1 <= mes <= 12:
            raise ValidationError("Mes inválido.")
        ultimo_dia = monthrange(anio, mes)[1]
        prestacion = PrestacionMensual.objects.filter(merendero=merendero, anio=anio, mes=mes).first()
        valores = {}
        observaciones = {}
        if prestacion:
            valores = {(linea.dia, linea.servicio): linea.raciones for linea in prestacion.lineas_diarias.all()}
            observaciones = prestacion.observaciones_por_dia
        return {
            "merendero": merendero,
            "anio": anio,
            "mes": mes,
            "dias": range(1, ultimo_dia + 1),
            "servicios": PrestacionDiaria.Servicio.choices,
            "valores": valores,
            "observaciones": observaciones,
            "prestacion": prestacion,
        }

    def get(self, request, pk):
        merendero = get_object_or_404(Merendero, pk=pk)
        hoy = date.today()
        try:
            contexto = self._contexto(
                request, merendero, int(request.GET.get("anio", hoy.year)), int(request.GET.get("mes", hoy.month))
            )
        except (TypeError, ValueError, ValidationError):
            return HttpResponseBadRequest("Mes o año inválido.")
        from django.shortcuts import render

        return render(request, self.template_name, contexto)

    def post(self, request, pk):
        merendero = get_object_or_404(Merendero, pk=pk)
        try:
            anio, mes = int(request.POST["anio"]), int(request.POST["mes"])
            ultimo_dia = monthrange(anio, mes)[1]
            raciones, observaciones = {}, {}
            for dia in range(1, ultimo_dia + 1):
                raciones[dia] = {}
                for servicio, _etiqueta in PrestacionDiaria.Servicio.choices:
                    valor = request.POST.get(f"raciones-{dia}-{servicio}", "0")
                    raciones[dia][servicio] = int(valor or 0)
                observaciones[dia] = request.POST.get(f"observacion-{dia}", "")
            guardar_prestacion(
                merendero, anio=anio, mes=mes, raciones=raciones, observaciones=observaciones, usuario=request.user
            )
        except (KeyError, TypeError, ValueError, ValidationError) as error:
            messages.error(
                request,
                error.messages[0] if isinstance(error, ValidationError) else "Los datos de prestación son inválidos.",
            )
            return redirect(
                f"{reverse('merenderos:prestacion', args=[merendero.pk])}?anio={request.POST.get('anio', '')}&mes={request.POST.get('mes', '')}"
            )
        messages.success(request, "Prestación mensual guardada.")
        return redirect(f"{reverse('merenderos:prestacion', args=[merendero.pk])}?anio={anio}&mes={mes}")
