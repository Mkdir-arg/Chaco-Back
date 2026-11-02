"""Equipo de un dispositivo: las acciones de la solapa «Equipo» (Cambio 411).

Cada acción es un POST que re-verifica en el servidor: la vista exige ``puede_gestionar_equipo``
(admin de Dispositivos o responsable de **ese** dispositivo) antes de mirar nada más, y el
servicio (``equipo_dispositivo``) vuelve a exigirlo. El botón escondido no es una barrera.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View

from programas.forms_dispositivos import SumarMiembroEquipoForm
from programas.mixins_dispositivos import DispositivoProgramaPermissionMixin
from programas.models import Dispositivo, MiembroEquipoDispositivo
from programas.services import equipo_dispositivo as equipo
from programas.views.ajax_utils import ajax_redirect, errores_del_servicio, is_ajax


def url_solapa_equipo(dispositivo_pk):
    return f"{reverse('dispositivos:detalle', args=[dispositivo_pk])}?tab=equipo"


class _EquipoAccionView(DispositivoProgramaPermissionMixin, View):
    """Base: solo POST, con la compuerta de gestión antes de cualquier otra cosa."""

    capacidad_requerida = "dispositivo.ver"
    http_method_names = ["post"]
    mensaje_exito = ""

    def ejecutar(self, request, dispositivo, miembro):
        raise NotImplementedError

    #: El formulario del modal, si la acción lo tiene: dice a qué campo va cada error.
    form = None

    def post(self, request, pk, **kwargs):
        dispositivo = get_object_or_404(Dispositivo, pk=pk)
        if not equipo.puede_gestionar_equipo(request.user, dispositivo):
            if is_ajax(request):
                return JsonResponse(
                    {"ok": False, "message": "Solo el admin de Dispositivos o un responsable arma el Equipo."},
                    status=403,
                )
            raise PermissionDenied
        volver = url_solapa_equipo(dispositivo.pk)
        try:
            self.ejecutar(request, dispositivo, kwargs)
        except PermissionDenied:
            raise
        except ValidationError as error:
            if is_ajax(request):
                return JsonResponse({"ok": False, "errors": errores_del_servicio(error, self.form)}, status=400)
            messages.error(request, error.messages[0])
            return redirect(volver)
        if is_ajax(request):
            return ajax_redirect(request, volver, self.mensaje_exito)
        messages.success(request, self.mensaje_exito)
        return redirect(volver)


class EquipoSumarView(_EquipoAccionView):
    mensaje_exito = "Persona sumada al Equipo."

    def ejecutar(self, request, dispositivo, kwargs):
        form = self.form = SumarMiembroEquipoForm(request.POST, pares=equipo.pares_persona_rol(dispositivo))
        if not form.is_valid():
            raise ValidationError({campo: list(mensajes) for campo, mensajes in form.errors.items()})
        usuario, rol = form.cleaned_data["persona_rol"]
        equipo.sumar_miembro(
            actor=request.user,
            dispositivo=dispositivo,
            usuario=usuario,
            rol=rol,
            es_responsable=form.cleaned_data["es_responsable"],
        )


class _EquipoMiembroView(_EquipoAccionView):
    """Una acción sobre una fila del Equipo; la fila tiene que ser de **este** dispositivo."""

    def servicio(self, **kwargs):
        raise NotImplementedError

    def ejecutar(self, request, dispositivo, kwargs):
        miembro = get_object_or_404(MiembroEquipoDispositivo, pk=kwargs["miembro_pk"], dispositivo=dispositivo)
        self.servicio(actor=request.user, miembro=miembro)


class EquipoBajaView(_EquipoMiembroView):
    mensaje_exito = "Persona dada de baja del Equipo."
    servicio = staticmethod(equipo.dar_de_baja)


class EquipoMarcarResponsableView(_EquipoMiembroView):
    mensaje_exito = "Persona marcada como responsable."
    servicio = staticmethod(equipo.marcar_responsable)


class EquipoDesmarcarResponsableView(_EquipoMiembroView):
    mensaje_exito = "La persona dejó de ser responsable."
    servicio = staticmethod(equipo.desmarcar_responsable)
