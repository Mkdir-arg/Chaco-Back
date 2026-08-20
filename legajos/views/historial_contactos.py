from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from ..forms import HistorialContactoForm
from ..models import LegajoAtencion
from ..models.contactos import HistorialContacto


@login_required
def historial_contactos_view(request, legajo_id):
    """Vista principal del historial de contactos"""
    legajo = get_object_or_404(LegajoAtencion, id=legajo_id)
    return render(request, "legajos/historial_contactos.html", {"legajo": legajo})


@login_required
def contactos_api(request, legajo_id):
    """API para obtener contactos del legajo"""
    legajo = get_object_or_404(LegajoAtencion, id=legajo_id)

    # Filtros
    search = request.GET.get("search", "")
    tipo = request.GET.get("tipo", "")
    estado = request.GET.get("estado", "")

    contactos = HistorialContacto.objects.filter(legajo=legajo)

    if search:
        contactos = contactos.filter(Q(motivo__icontains=search) | Q(resumen__icontains=search))

    if tipo:
        contactos = contactos.filter(tipo_contacto=tipo)

    if estado:
        contactos = contactos.filter(estado=estado)

    # El JS de historial_contactos.html espera la lista completa: limitamos a
    # los últimos 100 (pedimos 101 para saber si quedó historial afuera).
    contactos = list(contactos.select_related("profesional").order_by("-fecha_contacto")[:101])
    truncado = len(contactos) > 100
    contactos = contactos[:100]

    data = []
    for contacto in contactos:
        data.append(
            {
                "id": contacto.id,
                "fecha_contacto": contacto.fecha_contacto.isoformat(),
                "tipo_contacto": contacto.tipo_contacto,
                "tipo_contacto_display": contacto.get_tipo_contacto_display(),
                "estado": contacto.estado,
                "estado_display": contacto.get_estado_display(),
                "motivo": contacto.motivo,
                "resumen": contacto.resumen,
                "duracion_minutos": contacto.duracion_minutos,
                "duracion_formateada": contacto.duracion_formateada,
                "profesional": contacto.profesional.get_full_name(),
                "seguimiento_requerido": contacto.seguimiento_requerido,
                "fecha_proximo_contacto": contacto.fecha_proximo_contacto.isoformat()
                if contacto.fecha_proximo_contacto
                else None,
            }
        )

    return JsonResponse({"contactos": data, "truncado": truncado})


@login_required
@require_http_methods(["POST"])
def crear_contacto(request, legajo_id):
    """Crear nuevo contacto"""
    legajo = get_object_or_404(LegajoAtencion, id=legajo_id)

    form = HistorialContactoForm(request.POST, request.FILES)
    if form.is_valid():
        contacto = form.save(commit=False)
        contacto.legajo = legajo
        contacto.profesional = request.user
        contacto.save()

        return JsonResponse(
            {"success": True, "message": "Contacto registrado exitosamente", "contacto_id": contacto.id}
        )

    return JsonResponse({"success": False, "errors": form.errors})


@login_required
def detalle_contacto(request, contacto_id):
    """Obtener detalles de un contacto"""
    contacto = get_object_or_404(HistorialContacto, id=contacto_id)

    data = {
        "id": contacto.id,
        "fecha_contacto": contacto.fecha_contacto.isoformat(),
        "tipo_contacto": contacto.tipo_contacto,
        "tipo_contacto_display": contacto.get_tipo_contacto_display(),
        "estado": contacto.estado,
        "estado_display": contacto.get_estado_display(),
        "motivo": contacto.motivo,
        "resumen": contacto.resumen,
        "acuerdos": contacto.acuerdos,
        "proximos_pasos": contacto.proximos_pasos,
        "participantes": contacto.participantes,
        "ubicacion": contacto.ubicacion,
        "duracion_minutos": contacto.duracion_minutos,
        "duracion_formateada": contacto.duracion_formateada,
        "profesional": contacto.profesional.get_full_name(),
        "seguimiento_requerido": contacto.seguimiento_requerido,
        "fecha_proximo_contacto": contacto.fecha_proximo_contacto.isoformat()
        if contacto.fecha_proximo_contacto
        else None,
        "archivo_adjunto": contacto.archivo_adjunto.url if contacto.archivo_adjunto else None,
        "creado": contacto.creado.isoformat(),
    }

    return JsonResponse(data)


@login_required
@require_http_methods(["POST"])
def editar_contacto(request, contacto_id):
    """Editar contacto existente"""
    contacto = get_object_or_404(HistorialContacto, id=contacto_id)

    form = HistorialContactoForm(request.POST, request.FILES, instance=contacto)
    if form.is_valid():
        form.save()

        return JsonResponse({"success": True, "message": "Contacto actualizado exitosamente"})

    return JsonResponse({"success": False, "errors": form.errors})


@login_required
@require_http_methods(["POST"])
def eliminar_contacto(request, contacto_id):
    """Eliminar contacto"""
    contacto = get_object_or_404(HistorialContacto, id=contacto_id)
    contacto.delete()

    return JsonResponse({"success": True, "message": "Contacto eliminado exitosamente"})
