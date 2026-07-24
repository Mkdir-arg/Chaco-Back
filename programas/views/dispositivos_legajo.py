"""Vistas del legajo institucional de Dispositivos."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.utils import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from programas.forms import DispositivoForm
from programas.models import Dispositivo, TipoDispositivo
from programas.services.dispositivos import (
    buscar_posibles_duplicados,
    cerrar_dispositivo,
    dispositivos_visibles,
    enviar_a_validacion,
    inactivar_dispositivo,
    observar_dispositivo,
    puede_en_programa_dispositivos,
    puede_operar_dispositivo,
    rechazar_dispositivo,
    registrar_alta_dispositivo,
    registrar_edicion_dispositivo,
    validar_dispositivo,
)
from programas.views.ajax_utils import is_ajax


class DispositivoProgramaPermissionMixin(LoginRequiredMixin):
    capacidad_requerida = None

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
        if not puede_en_programa_dispositivos(request.user, self.capacidad_requerida):
            if is_ajax(request):
                return JsonResponse(
                    {"ok": False, "message": "No tenés permiso para realizar esta acción."},
                    status=403,
                )
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class DispositivoObjectPermissionMixin(DispositivoProgramaPermissionMixin):
    def get_object(self, queryset=None):
        dispositivo = super().get_object(queryset)
        if not puede_operar_dispositivo(self.request.user, dispositivo, self.capacidad_requerida):
            raise PermissionDenied
        return dispositivo


class DispositivoListView(DispositivoProgramaPermissionMixin, ListView):
    capacidad_requerida = "dispositivo.ver"
    model = Dispositivo
    template_name = "programas/dispositivos/legajo/list.html"
    context_object_name = "dispositivos"

    def get_queryset(self):
        queryset = dispositivos_visibles(self.request.user).select_related("tipo")
        tipo = self.request.GET.get("tipo")
        estado = self.request.GET.get("estado")
        localidad = self.request.GET.get("localidad", "").strip()
        if tipo:
            queryset = queryset.filter(tipo_id=tipo)
        if estado:
            queryset = queryset.filter(estado=estado)
        if localidad:
            queryset = queryset.filter(localidad__icontains=localidad)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["estados"] = Dispositivo.Estado.choices
        context["tipos"] = TipoDispositivo.objects.filter(activo=True).order_by("nombre")
        return context


class DispositivoCreateView(DispositivoProgramaPermissionMixin, CreateView):
    capacidad_requerida = "dispositivo.crear"
    model = Dispositivo
    form_class = DispositivoForm
    template_name = "programas/dispositivos/legajo/form.html"

    def form_valid(self, form):
        try:
            with transaction.atomic():
                self.object = form.save()
                registrar_alta_dispositivo(self.object, self.request.user)
        except IntegrityError:
            form.add_error("codigo", "Ya existe un dispositivo con este código institucional.")
            return self.form_invalid(form)
        messages.success(self.request, "Dispositivo creado como borrador.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("dispositivos:detalle", args=[self.object.pk])


class DispositivoDuplicateSearchView(DispositivoProgramaPermissionMixin, View):
    capacidad_requerida = "dispositivo.crear"

    def get(self, request):
        resultado = buscar_posibles_duplicados(
            codigo=request.GET.get("codigo", ""),
            nombre=request.GET.get("nombre", ""),
            localidad=request.GET.get("localidad", ""),
        )
        return JsonResponse(
            {
                "codigo_duplicado": resultado["codigo_duplicado"],
                "coincidencias": [
                    {
                        "codigo": dispositivo.codigo,
                        "nombre": dispositivo.nombre,
                        "localidad": dispositivo.localidad,
                        "estado": dispositivo.get_estado_display(),
                    }
                    for dispositivo in resultado["dispositivos"]
                ],
            }
        )


class DispositivoDetailView(DispositivoObjectPermissionMixin, DetailView):
    capacidad_requerida = "dispositivo.ver"
    model = Dispositivo
    template_name = "programas/dispositivos/legajo/detail.html"
    context_object_name = "dispositivo"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["trazas"] = self.object.trazas.select_related("usuario")
        return context


class DispositivoUpdateView(DispositivoObjectPermissionMixin, UpdateView):
    capacidad_requerida = "dispositivo.editar"
    model = Dispositivo
    form_class = DispositivoForm
    template_name = "programas/dispositivos/legajo/form.html"
    context_object_name = "dispositivo"

    def get_object(self, queryset=None):
        dispositivo = super().get_object(queryset)
        if dispositivo.estado == Dispositivo.Estado.CERRADO:
            raise PermissionDenied
        return dispositivo

    def form_valid(self, form):
        with transaction.atomic():
            dispositivo = Dispositivo.objects.select_for_update().get(pk=self.object.pk)
            if dispositivo.estado == Dispositivo.Estado.CERRADO:
                raise PermissionDenied
            cambios = {
                field: {"anterior": getattr(dispositivo, field), "nuevo": form.cleaned_data[field]}
                for field in form.changed_data
            }
            for field in form.changed_data:
                setattr(dispositivo, field, form.cleaned_data[field])
            if cambios:
                dispositivo.save(update_fields=[*form.changed_data, "modificado"])
                registrar_edicion_dispositivo(dispositivo, self.request.user, cambios)
            self.object = dispositivo
        messages.success(self.request, "Dispositivo actualizado.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("dispositivos:detalle", args=[self.object.pk])


class DispositivoActionView(DispositivoProgramaPermissionMixin, View):
    accion = None

    def ejecutar(self, dispositivo, request):
        raise NotImplementedError

    def post(self, request, pk):
        dispositivo = get_object_or_404(Dispositivo, pk=pk)
        if not puede_operar_dispositivo(request.user, dispositivo, self.capacidad_requerida):
            if is_ajax(request):
                return JsonResponse(
                    {"ok": False, "message": "No tenés permiso para realizar esta acción."},
                    status=403,
                )
            raise PermissionDenied
        try:
            self.ejecutar(dispositivo, request)
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            messages.success(request, self.mensaje_exito)
        return redirect("dispositivos:detalle", pk=dispositivo.pk)


class DispositivoEnviarValidacionView(DispositivoActionView):
    capacidad_requerida = "dispositivo.editar"
    mensaje_exito = "Dispositivo enviado a validación."

    def ejecutar(self, dispositivo, request):
        enviar_a_validacion(dispositivo, request.user)


class DispositivoValidarView(DispositivoActionView):
    capacidad_requerida = "dispositivo.validar"
    mensaje_exito = "Dispositivo validado y habilitado para admitir."

    def ejecutar(self, dispositivo, request):
        validar_dispositivo(dispositivo, request.user)


class DispositivoObservarView(DispositivoActionView):
    capacidad_requerida = "dispositivo.validar"
    mensaje_exito = "Dispositivo observado."

    def ejecutar(self, dispositivo, request):
        observar_dispositivo(dispositivo, request.user, request.POST.get("motivo"))


class DispositivoRechazarView(DispositivoActionView):
    capacidad_requerida = "dispositivo.validar"
    mensaje_exito = "Dispositivo rechazado."

    def ejecutar(self, dispositivo, request):
        rechazar_dispositivo(dispositivo, request.user, request.POST.get("motivo"))


class DispositivoInactivarView(DispositivoActionView):
    capacidad_requerida = "dispositivo.editar"
    mensaje_exito = "Dispositivo inactivado."

    def ejecutar(self, dispositivo, request):
        inactivar_dispositivo(dispositivo, request.user)


class DispositivoCerrarView(DispositivoActionView):
    capacidad_requerida = "dispositivo.editar"
    mensaje_exito = "Dispositivo cerrado."

    def ejecutar(self, dispositivo, request):
        cerrar_dispositivo(dispositivo, request.user)
