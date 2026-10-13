"""Mixins de permisos de Dispositivos, compartidos por varias vistas.

Viven **fuera de `programas/views/`** a propósito: los usan `dispositivos_legajo`,
`dispositivos_relevamientos` y `reportes`, y una vista que le pide un helper a otra
vista es justo lo que mide el ratchet de `programas/tests/test_arquitectura.py`
(`CapasTests.test_no_crecen_las_dependencias_entre_vistas`). `dispositivos_legajo`
los re-exporta para no romper los imports que ya existen.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse

from programas.services.dispositivos import puede_en_programa_dispositivos, puede_operar_dispositivo
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
