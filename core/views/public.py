# Create your views here.
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from core.rbac import requiere
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.dateparse import parse_datetime
from django.utils.timezone import localtime
from django.views.decorators.http import require_GET

from dashboard.utils import (
    contar_alertas_activas,
    contar_ciudadanos,
    contar_legajos,
    contar_seguimientos_hoy,
    contar_usuarios,
)

from ..selectors import get_localidades_values, get_municipios_values
from core.services.relevamientos_supabase import (
    fetch_adjuntos_counts,
    fetch_instituciones_list,
    fetch_relevamiento_detail,
    fetch_relevamientos,
    get_storage_signed_url,
    fetch_usernames_by_user_ids,
    fetch_username_by_user_id,
)


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
    qs = Subsecretaria.objects.filter(activo=True).order_by('nombre')
    if secretaria_id:
        qs = qs.filter(secretaria_id=secretaria_id)
    data = list(qs.values('id', 'nombre'))
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
        'total_ciudadanos': contar_ciudadanos(),
        'usuarios_activos': User.objects.filter(last_login__gte=hace_24h).count(),
        'registros_mes': InscripcionPrograma.objects.filter(fecha_inscripcion__gte=inicio_mes).count(),
        'actividad_hoy': contar_seguimientos_hoy(),
        'total_usuarios': contar_usuarios(),
        'total_legajos': legajo_stats['total'],
        'legajos_activos': legajo_stats['activos'],
        'seguimientos_hoy': contar_seguimientos_hoy(),
        'alertas_activas': contar_alertas_activas(),
    }

    # --- Mi trabajo de hoy ---
    derivaciones_pendientes = (
        DerivacionPrograma.objects.filter(estado='PENDIENTE')
        .select_related('ciudadano', 'programa_origen', 'programa_destino')
        .order_by('-creado')
    )
    context['derivaciones_pendientes_count'] = derivaciones_pendientes.count()
    context['derivaciones_pendientes'] = derivaciones_pendientes[:8]

    try:
        from conversaciones.models import Conversacion
        conversaciones_sin_asignar = (
            Conversacion.objects.filter(estado='pendiente', operador_asignado__isnull=True)
            .order_by('-fecha_inicio')
        )
        context['conversaciones_sin_asignar_count'] = conversaciones_sin_asignar.count()
        context['conversaciones_sin_asignar'] = conversaciones_sin_asignar[:8]
    except Exception:
        context['conversaciones_sin_asignar_count'] = 0
        context['conversaciones_sin_asignar'] = []

    # --- Inscripciones activas por programa (gráfico) ---
    context['programas_chart'] = [
        {
            'nombre': p.nombre,
            'color': p.color or '#3B82F6',
            'count': p.inscripciones_activas,
        }
        for p in Programa.objects.annotate(
            inscripciones_activas=Count(
                'inscripciones',
                filter=Q(inscripciones__estado__in=['ACTIVO', 'EN_SEGUIMIENTO']),
            )
        ).filter(inscripciones_activas__gt=0).order_by('-inscripciones_activas')[:10]
    ]

    return render(request, "inicio.html", context)


@login_required
@requiere("relevamiento.ver")
def relevamientos_view(request):
    """Vista de listado de relevamientos web."""
    query = (request.GET.get("q") or "").strip()
    institucion_id = (request.GET.get("institucion_id") or "").strip()
    result = fetch_relevamientos(limit=300, query=query, institucion_id=institucion_id or None)
    items = result.get("items", [])
    adjuntos_counts = fetch_adjuntos_counts([str(x.get("id")) for x in items if x.get("id")])
    instituciones = fetch_instituciones_list()
    usernames_by_user_id = fetch_usernames_by_user_ids([str(x.get("created_by")) for x in items if x.get("created_by")])

    for row in items:
        created_at = parse_datetime(row.get("created_at") or "")
        row["created_at_fmt"] = localtime(created_at).strftime("%d/%m/%Y %H:%M") if created_at else "-"

        nombre = (row.get("responsable_nombre") or "").strip()
        apellido = (row.get("responsable_apellido") or "").strip()
        full_name = f"{nombre} {apellido}".strip()
        row["responsable_full_name"] = full_name or "-"
        row["tiene_adjuntos"] = adjuntos_counts.get(str(row.get("id")), 0) > 0
        created_by = str(row.get("created_by") or "")
        row["usuario_relevamiento"] = (
            (row.get("usuario_username") or "").strip()
            or (usernames_by_user_id.get(created_by, "-") if created_by else "-")
        )
        if not row["usuario_relevamiento"] or row["usuario_relevamiento"] == "-":
            row["usuario_relevamiento"] = "sin_usuario"

    if not result.get("success"):
        messages.error(request, result.get("error") or "No se pudo cargar relevamientos")
    elif not (getattr(settings, "SUPABASE_URL", "") and (getattr(settings, "SUPABASE_ANON_KEY", "") or getattr(settings, "SUPABASE_KEY", ""))):
        messages.warning(request, "Supabase no esta configurado. Defini SUPABASE_URL y SUPABASE_ANON_KEY en .env")

    context = {
        "relevamientos": items,
        "q": query,
        "instituciones": instituciones,
        "institucion_id": institucion_id,
    }
    return render(request, "core/relevamientos.html", context)


@login_required
def relevamiento_detail_view(request, relevamiento_id):
    """Vista de detalle de un relevamiento."""
    result = fetch_relevamiento_detail(str(relevamiento_id))
    if not result.get("success"):
        messages.error(request, result.get("error") or "No se pudo cargar el detalle del relevamiento")
        return render(request, "core/relevamiento_detail.html", {"item": None, "adjuntos": [], "campos_extra": []})

    item = result.get("item") or {}
    relevado_at = parse_datetime(item.get("relevado_at") or "")
    created_at = parse_datetime(item.get("created_at") or "")
    updated_at = parse_datetime(item.get("updated_at") or "")
    last_synced_at = parse_datetime(item.get("last_synced_at") or "")
    item["relevado_at_fmt"] = localtime(relevado_at).strftime("%d/%m/%Y %H:%M") if relevado_at else "-"
    item["created_at_fmt"] = localtime(created_at).strftime("%d/%m/%Y %H:%M") if created_at else "-"
    item["updated_at_fmt"] = localtime(updated_at).strftime("%d/%m/%Y %H:%M") if updated_at else "-"
    item["last_synced_at_fmt"] = localtime(last_synced_at).strftime("%d/%m/%Y %H:%M") if last_synced_at else "-"
    item["last_synced_at_display"] = (
        item["last_synced_at_fmt"]
        if item["last_synced_at_fmt"] != "-"
        else (item["created_at_fmt"] if (item.get("sync_estado") == "SINCRONIZADO" and item["created_at_fmt"] != "-") else "Pendiente")
    )
    nombre = (item.get("responsable_nombre") or "").strip()
    apellido = (item.get("responsable_apellido") or "").strip()
    item["responsable_full_name"] = f"{nombre} {apellido}".strip() or "-"
    item["usuario_relevamiento"] = (
        (item.get("usuario_username") or "").strip()
        or fetch_username_by_user_id(item.get("created_by"))
    )
    if not item["usuario_relevamiento"] or item["usuario_relevamiento"] == "-":
        item["usuario_relevamiento"] = "sin_usuario"

    image_adjuntos = []
    file_adjuntos = []
    signature_attachment = None
    for adjunto in result.get("adjuntos", []):
        path = (adjunto.get("storage_path") or "").strip()
        bucket = (adjunto.get("storage_bucket") or "relevamientos").strip() or "relevamientos"
        signed_url = get_storage_signed_url(path, bucket=bucket) if path else ""
        mime_type = (adjunto.get("mime_type") or "").lower()
        tipo_archivo = (adjunto.get("tipo_archivo") or "").upper()
        categoria = (adjunto.get("categoria") or "").upper()
        is_image = tipo_archivo == "IMAGEN" or mime_type.startswith("image/")

        if not is_image and path:
            ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
            is_image = ext in {"jpg", "jpeg", "png", "webp", "gif", "bmp", "heic"}

        prepared = {
            **adjunto,
            "file_url": signed_url,
            "display_name": (adjunto.get("nombre_original") or path.split("/")[-1] or "archivo"),
        }
        if categoria == "FIRMA":
            if is_image and not signature_attachment:
                signature_attachment = prepared
            continue

        if is_image:
            image_adjuntos.append(prepared)
        else:
            file_adjuntos.append(prepared)

    signature_url = ""
    signature_name = ""
    if signature_attachment:
        signature_url = signature_attachment.get("file_url") or ""
        signature_name = signature_attachment.get("display_name") or "Firma"

    if not signature_url:
        firma_storage_path = (item.get("firma_storage_path") or "").strip()
        if firma_storage_path:
            signature_url = get_storage_signed_url(firma_storage_path, bucket="relevamientos")
            signature_name = signature_name or "Firma"

    context = {
        "item": item,
        "adjuntos": result.get("adjuntos", []),
        "image_adjuntos": image_adjuntos,
        "file_adjuntos": file_adjuntos,
        "campos_extra": result.get("campos_extra", []),
        "signature_url": signature_url,
        "signature_name": signature_name or "Firma",
        "has_signature_paths": bool(item.get("firma_paths")),
    }
    return render(request, "core/relevamiento_detail.html", context)


def error_500_view(request):
    return render(request, "500.html")
