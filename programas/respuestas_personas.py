"""La respuesta HTTP de las sugerencias de personas del legajo, compartida por las pantallas que la usan.

Vive fuera de `programas/views/` porque la usan varias vistas (Dispositivos y la mesa de Emergencia) y una vista que le
pide un helper a otra vista es lo que mide el ratchet de `programas/tests/test_arquitectura.py`.
"""

from django.http import JsonResponse

from core.http_cache import sin_cache
from core.rbac import puede
from programas.selectors.personas_sugeridas import sugerir_personas
from programas.services.estadias import CAP_VER_CIUDADANO


def responder_personas_sugeridas(request):
    """JSON de ``sugerir_personas`` para ``?q=``, o 403 sin ``ciudadano.ver``. Sin caché ni registro de lo tecleado.

    El llamador ya validó **su** capacidad (la de la acción que el campo completa); acá solo se pide ver personas.
    """

    if not puede(request.user, CAP_VER_CIUDADANO):
        return JsonResponse({"ok": False, "message": "No tenés permiso para realizar esta acción."}, status=403)
    # Sin registrar lo tecleado: es un DNI o un apellido, dato personal.
    return sin_cache(JsonResponse(sugerir_personas(request.GET.get("q", ""))))
