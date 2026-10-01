import json
import logging

from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from ..forms import EvaluarConversacionForm
from ..models import Conversacion
from ..services.chat import (
    evaluar_conversacion as evaluar_conversacion_service,
)

logger = logging.getLogger(__name__)


def _json_payload(request):
    try:
        return json.loads(request.body or "{}"), None
    except json.JSONDecodeError:
        return None, JsonResponse({"success": False, "error": "JSON inválido"})


def _first_form_error(form, default_message):
    if form.errors:
        return next(iter(form.errors.values()))[0]
    return default_message


def evaluar_conversacion(request, conversacion_id):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Método no permitido"})

    payload, error_response = _json_payload(request)
    if error_response:
        return error_response

    evaluar_form = EvaluarConversacionForm({"satisfaccion": payload.get("satisfaccion")})
    if not evaluar_form.is_valid():
        return JsonResponse(
            {
                "success": False,
                "error": _first_form_error(evaluar_form, "Evaluación inválida"),
            }
        )

    conversacion = get_object_or_404(Conversacion, id=conversacion_id)
    evaluar_conversacion_service(conversacion, evaluar_form.cleaned_data["satisfaccion"])
    return JsonResponse({"success": True})
