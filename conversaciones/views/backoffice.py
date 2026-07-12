import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.rbac import requiere

from ..forms import (
    AsignarConversacionForm,
    ConfigurarColaForm,
    EvaluarConversacionForm,
    MensajeConversacionForm,
)
from ..models import Conversacion
from ..permisos import es_operador_restringido, puede_operar
from ..selectors import (
    get_configuracion_cola_contexto,
    get_conversacion_api_detalle,
    get_conversacion_detalle_queryset,
    get_conversaciones_queryset_para_lista,
    get_estadisticas_lista,
    get_estadisticas_tiempo_real,
    get_metricas_contexto,
    get_operadores_con_carga,
    get_todos_los_operadores,
)
from ..services import MetricasService
from ..services.chat import (
    asignar_conversacion_operador,
    configurar_operador_cola,
    crear_mensaje_operador,
    ejecutar_asignacion_automatica,
)
from ..services.chat import (
    cerrar_conversacion as cerrar_conversacion_service,
)
from ..services.chat import (
    evaluar_conversacion as evaluar_conversacion_service,
)


def _json_payload(request):
    try:
        return json.loads(request.body or "{}"), None
    except json.JSONDecodeError:
        return None, JsonResponse({"success": False, "error": "JSON inválido"})


def tiene_permiso_conversaciones(user):
    return puede_operar(user)


@login_required
@user_passes_test(tiene_permiso_conversaciones)
def lista_conversaciones(request):
    filtros = {
        "estado": request.GET.get("estado", ""),
        "operador": request.GET.get("operador", ""),
        "fecha_desde": request.GET.get("fecha_desde", ""),
        "fecha_hasta": request.GET.get("fecha_hasta", ""),
        "busqueda": request.GET.get("busqueda", ""),
        "tipo": request.GET.get("tipo", ""),
    }
    paginator = Paginator(get_conversaciones_queryset_para_lista(request.user, filtros), 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    querystring = request.GET.copy()
    querystring.pop("page", None)
    context = {
        "conversaciones": page_obj,
        "page_obj": page_obj,
        "filtros_qs": querystring.urlencode(),
        "es_operador_charla": es_operador_restringido(request.user),
        "operadores_con_carga": get_operadores_con_carga(),
        "todos_operadores": get_todos_los_operadores(),
        "filtros": filtros,
    }
    context.update(get_estadisticas_lista())
    return render(request, "conversaciones/lista.html", context)


@login_required
@user_passes_test(tiene_permiso_conversaciones)
def detalle_conversacion(request, conversacion_id):
    from ..models import HistorialAlertaConversacion, NuevaConversacionAlerta

    conversacion = get_object_or_404(get_conversacion_detalle_queryset(), id=conversacion_id)
    mensajes_qs = conversacion.mensajes.all()
    mensajes_qs.filter(remitente="ciudadano", leido=False).update(leido=True)
    # Al abrir la conversación se dan por vistas sus alertas: sin esto los
    # contadores del navbar (polled) crecían monótonamente para siempre.
    NuevaConversacionAlerta.objects.filter(
        conversacion=conversacion, operador=request.user, vista=False
    ).update(vista=True)
    HistorialAlertaConversacion.objects.filter(
        conversacion=conversacion, operador=request.user, vista=False
    ).update(vista=True, fecha_vista=timezone.now())
    return render(
        request,
        "conversaciones/detalle.html",
        {
            "conversacion": conversacion,
            "mensajes": mensajes_qs,
        },
    )


@login_required
@user_passes_test(tiene_permiso_conversaciones)
def asignar_conversacion(request, conversacion_id):
    conversacion = get_object_or_404(Conversacion, id=conversacion_id, estado="activa")
    if request.method == "POST":
        form = AsignarConversacionForm(request.POST)
        if form.is_valid():
            operador = request.user
            if form.cleaned_data.get("operador_id"):
                operador = get_object_or_404(get_todos_los_operadores(), id=form.cleaned_data["operador_id"])
            asignar_conversacion_operador(conversacion, operador, request.user)
            messages.success(
                request, f"Conversación asignada a {operador.get_full_name() or operador.username} exitosamente."
            )
    return redirect("conversaciones:lista")


@login_required
@user_passes_test(tiene_permiso_conversaciones)
def enviar_mensaje_operador(request, conversacion_id):
    if request.method != "POST":
        return JsonResponse({"success": False})

    payload, error_response = _json_payload(request)
    if error_response:
        return error_response

    form = MensajeConversacionForm(payload)
    if not form.is_valid() or not form.cleaned_data["mensaje"]:
        return JsonResponse({"success": False, "error": "Mensaje vacío"})

    conversacion = get_object_or_404(Conversacion, id=conversacion_id)
    try:
        mensaje = crear_mensaje_operador(conversacion, request.user, form.cleaned_data["mensaje"])
    except PermissionError as exc:
        return JsonResponse({"success": False, "error": str(exc)})

    return JsonResponse(
        {
            "success": True,
            "mensaje": {
                "id": mensaje.id,
                "contenido": mensaje.contenido,
                "fecha": mensaje.fecha_envio.strftime("%H:%M"),
            },
        }
    )


@login_required
@user_passes_test(tiene_permiso_conversaciones)
def cerrar_conversacion(request, conversacion_id):
    conversacion = get_object_or_404(Conversacion, id=conversacion_id)
    cerrar_conversacion_service(conversacion)
    messages.success(request, "Conversación cerrada exitosamente.")
    return redirect("conversaciones:lista")


@login_required
@user_passes_test(tiene_permiso_conversaciones)
def reasignar_conversacion(request, conversacion_id):
    conversacion = get_object_or_404(Conversacion, id=conversacion_id, estado="activa")
    if request.method == "POST":
        form = AsignarConversacionForm(request.POST)
        if form.is_valid() and form.cleaned_data.get("operador_id"):
            operador = get_object_or_404(get_todos_los_operadores(), id=form.cleaned_data["operador_id"])
            asignar_conversacion_operador(conversacion, operador, request.user)
            messages.success(
                request, f"Conversación reasignada a {operador.get_full_name() or operador.username} exitosamente."
            )
    return redirect("conversaciones:lista")


@login_required
@requiere("conversacion.metricas")
def metricas_conversaciones(request):
    return render(request, "conversaciones/metricas.html", get_metricas_contexto())


@login_required
@requiere("conversacion.configurar")
def configurar_cola(request):
    if request.method == "POST":
        form = ConfigurarColaForm(request.POST)
        if form.is_valid():
            cola = configurar_operador_cola(form.cleaned_data)
            messages.success(
                request,
                f"Configuración actualizada para {cola.operador.get_full_name() or cola.operador.username}",
            )
    return render(request, "conversaciones/configurar_cola.html", get_configuracion_cola_contexto())


@login_required
@user_passes_test(tiene_permiso_conversaciones)
def asignacion_automatica(request):
    try:
        asignadas, sin_operadores = ejecutar_asignacion_automatica()
        if asignadas > 0:
            messages.success(request, f"{asignadas} conversaciones asignadas automáticamente")
        if sin_operadores > 0:
            messages.warning(request, f"{sin_operadores} conversaciones no pudieron asignarse")
        if asignadas == 0 and sin_operadores == 0:
            messages.info(request, "No hay conversaciones sin asignar")
    except Exception:
        messages.error(request, "Error en la asignación automática")
    return redirect("conversaciones:lista")


@login_required
@user_passes_test(tiene_permiso_conversaciones)
def evaluar_conversacion(request, conversacion_id):
    conversacion = get_object_or_404(Conversacion, id=conversacion_id)
    if request.method == "POST":
        form = EvaluarConversacionForm(request.POST)
        if form.is_valid():
            evaluar_conversacion_service(conversacion, form.cleaned_data["satisfaccion"])
            return JsonResponse({"success": True})
    return JsonResponse({"success": False})


@login_required
@user_passes_test(tiene_permiso_conversaciones)
def api_metricas_tiempo_real(request):
    return JsonResponse(
        {
            "success": True,
            "metricas": MetricasService.calcular_metricas_globales(),
        }
    )


@login_required
@user_passes_test(tiene_permiso_conversaciones)
def api_conversacion_detalle(request, conversacion_id):
    try:
        conversacion = get_conversacion_api_detalle(conversacion_id)
        return JsonResponse(
            {
                "success": True,
                "conversacion": {
                    "id": conversacion.id,
                    "tipo": conversacion.get_tipo_display(),
                    "dni": conversacion.dni_ciudadano,
                    "sexo": conversacion.sexo_ciudadano,
                    "estado": conversacion.estado,
                    "estado_display": conversacion.get_estado_display(),
                    "operador": conversacion.operador_asignado.get_full_name()
                    if conversacion.operador_asignado
                    else None,
                    "fecha": conversacion.fecha_inicio.strftime("%d/%m/%Y %H:%M"),
                    "mensajes": conversacion.total_mensajes,
                    "no_leidos": conversacion.mensajes_no_leidos,
                },
            }
        )
    except Conversacion.DoesNotExist:
        return JsonResponse({"success": False, "error": "Conversación no encontrada"})


@login_required
@user_passes_test(tiene_permiso_conversaciones)
def api_estadisticas_tiempo_real(request):
    return JsonResponse(
        {
            "success": True,
            "estadisticas": get_estadisticas_tiempo_real(),
        }
    )
