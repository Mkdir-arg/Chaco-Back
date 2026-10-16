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

from programas.services.dispositivos import (
    puede_configurar_dispositivos,
    puede_en_programa_dispositivos,
    puede_operar_dispositivo,
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


class DispositivoAltaPermissionMixin(DispositivoProgramaPermissionMixin):
    """El alta de una institución, acotada al alcance de admin del programa.

    `dispositivo.crear` sola no alcanza. Una institución recién creada **no tiene
    asignaciones**, así que el alcance fino de `puede_operar_dispositivo` no la incluye:
    quien la daba de alta sin alcance de admin guardaba el borrador y el redirect a su
    propio legajo le respondía 403, con la institución ya escrita y fuera de su vista. El
    alta queda para quien tiene alcance total sobre el programa —el mismo
    `puede_configurar_dispositivos` que resuelve `puede_operar_dispositivo`—, que es el
    único que puede después abrirla, asignarla y validarla.

    La capacidad la sigue exigiendo el mixin base; esto es el alcance, no una capacidad
    nueva: el catálogo de `core/rbac.py` no cambia.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not puede_configurar_dispositivos(request.user):
            if is_ajax(request):
                return JsonResponse(
                    {"ok": False, "message": "El alta de instituciones la hace quien administra el programa."},
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
