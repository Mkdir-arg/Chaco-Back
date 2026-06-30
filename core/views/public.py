# Create your views here.
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from dashboard.utils import (
    contar_alertas_activas,
    contar_ciudadanos,
    contar_legajos,
    contar_seguimientos_hoy,
    contar_usuarios,
)

from ..selectors import get_localidades_values, get_municipios_values


@login_required
@require_GET
def load_municipios(request):
    """Carga municipios filtrados por provincia."""
    provincia_id = request.GET.get("provincia_id")
    return JsonResponse(get_municipios_values(provincia_id), safe=False)


@login_required
@require_GET
def load_localidad(request):
    """Carga localidades filtradas por municipio."""
    municipio_id = request.GET.get("municipio_id")
    return JsonResponse(get_localidades_values(municipio_id), safe=False)


@login_required
@require_GET
def load_subsecretarias(request):
    """Carga subsecretarías activas filtradas por secretaría."""
    from ..models import Subsecretaria

    secretaria_id = request.GET.get("secretaria")
    qs = Subsecretaria.objects.filter(activo=True).order_by("nombre")
    if secretaria_id:
        qs = qs.filter(secretaria_id=secretaria_id)
    data = list(qs.values("id", "nombre"))
    return JsonResponse(data, safe=False)


@login_required
def inicio_view(request):
    """Vista para la página de inicio del sistema"""
    from datetime import timedelta

    from django.db.models import Count, Q
    from django.utils import timezone

    from programas.models import DerivacionPrograma, InscripcionPrograma, Programa

    User = get_user_model()
    ahora = timezone.now()
    hace_24h = ahora - timedelta(hours=24)
    inicio_mes = ahora.date().replace(day=1)
    legajo_stats = contar_legajos()

    context = {
        "total_ciudadanos": contar_ciudadanos(),
        "usuarios_activos": User.objects.filter(last_login__gte=hace_24h).count(),
        "registros_mes": InscripcionPrograma.objects.filter(fecha_inscripcion__gte=inicio_mes).count(),
        "actividad_hoy": contar_seguimientos_hoy(),
        "total_usuarios": contar_usuarios(),
        "total_legajos": legajo_stats["total"],
        "legajos_activos": legajo_stats["activos"],
        "seguimientos_hoy": contar_seguimientos_hoy(),
        "alertas_activas": contar_alertas_activas(),
    }

    # --- Mi trabajo de hoy ---
    derivaciones_pendientes = (
        DerivacionPrograma.objects.filter(estado="PENDIENTE")
        .select_related("ciudadano", "programa_origen", "programa_destino")
        .order_by("-creado")
    )
    context["derivaciones_pendientes_count"] = derivaciones_pendientes.count()
    context["derivaciones_pendientes"] = derivaciones_pendientes[:8]

    try:
        from conversaciones.models import Conversacion

        conversaciones_sin_asignar = Conversacion.objects.filter(
            estado="pendiente", operador_asignado__isnull=True
        ).order_by("-fecha_inicio")
        context["conversaciones_sin_asignar_count"] = conversaciones_sin_asignar.count()
        context["conversaciones_sin_asignar"] = conversaciones_sin_asignar[:8]
    except Exception:
        context["conversaciones_sin_asignar_count"] = 0
        context["conversaciones_sin_asignar"] = []

    # --- Inscripciones activas por programa (gráfico) ---
    context["programas_chart"] = [
        {
            "nombre": p.nombre,
            "color": p.color or "#3B82F6",
            "count": p.inscripciones_activas,
        }
        for p in Programa.objects.annotate(
            inscripciones_activas=Count(
                "inscripciones",
                filter=Q(inscripciones__estado__in=["ACTIVO", "EN_SEGUIMIENTO"]),
            )
        )
        .filter(inscripciones_activas__gt=0)
        .order_by("-inscripciones_activas")[:10]
    ]

    return render(request, "inicio.html", context)


@login_required
def relevamientos_view(request):
    """Compatibilidad para el relevamiento legacy: usar el modulo Becas actual."""
    return redirect("becas:relevamientos")


@login_required
def relevamiento_detail_view(request, relevamiento_id):
    """Compatibilidad para enlaces legacy de relevamientos."""
    return redirect("becas:relevamientos")


def error_500_view(request):
    return render(request, "500.html")
