import logging
from datetime import datetime, timedelta

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.html import escape
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from legajos.models import AlertaCiudadano, Ciudadano
from programas.models import DerivacionPrograma, InscripcionPrograma
from users.models import User

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def metricas_dashboard(request):
    """Obtiene metricas principales del dashboard (datos globales, cacheados 60 s)."""
    from django.core.cache import cache

    data = cache.get_or_set("dashboard:metricas_api", _calcular_metricas_dashboard, 60)
    return Response(data)


def _calcular_metricas_dashboard():
    total_ciudadanos = Ciudadano.objects.count()
    alertas_activas = AlertaCiudadano.objects.filter(activa=True).count()

    hoy = timezone.now().date()
    inscripciones = InscripcionPrograma.objects.aggregate(
        legajos_activos=Count("id", filter=Q(estado__in=["ACTIVO", "EN_SEGUIMIENTO"])),
        seguimientos_hoy=Count("id", filter=Q(fecha_inscripcion=hoy)),
        abiertos=Count("id", filter=Q(estado="ACTIVO")),
        seguimiento=Count("id", filter=Q(estado="EN_SEGUIMIENTO")),
        cerrados=Count("id", filter=Q(estado="CERRADO")),
    )

    hace_24h = timezone.now() - timedelta(hours=24)
    usuarios_activos = User.objects.filter(last_login__gte=hace_24h).count()

    return {
        "metricas": {
            "ciudadanos": total_ciudadanos,
            "legajos": inscripciones["legajos_activos"],
            "seguimientos": inscripciones["seguimientos_hoy"],
            "alertas": alertas_activas,
        },
        "estados_legajos": {
            "abiertos": inscripciones["abiertos"],
            "seguimiento": inscripciones["seguimiento"],
            "derivados": DerivacionPrograma.objects.filter(estado="PENDIENTE").count(),
            "cerrados": inscripciones["cerrados"],
        },
        "usuarios_conectados": usuarios_activos,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def buscar_ciudadanos(request):
    """Busqueda rapida de ciudadanos."""
    query = escape(request.GET.get("q", "").strip())

    if len(query) < 3:
        return Response({"results": []})

    try:
        # Filtros sargables: LIKE 'q%' usa índice; LIKE '%q%' fuerza full scan
        # del padrón por cada tecla del typeahead.
        if query.isdigit():
            filtro = Q(dni__startswith=query)
        else:
            filtro = Q(nombre__istartswith=query) | Q(apellido__istartswith=query)
        ciudadanos = Ciudadano.objects.only("id", "nombre", "apellido", "dni").filter(filtro)[:8]

        resultados = [{"id": c.id, "nombre": f"{c.apellido}, {c.nombre}", "dni": c.dni} for c in ciudadanos]
        return Response({"results": resultados})
    except Exception as e:
        logger.error(f"Error en busqueda de ciudadanos: {e}", exc_info=True)
        return Response({"results": [], "error": "Error en la busqueda"}, status=500)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def alertas_criticas(request):
    """Obtiene alertas criticas activas."""
    try:
        alertas = (
            AlertaCiudadano.objects.filter(activa=True, prioridad__in=["CRITICA", "ALTA"])
            .select_related("ciudadano")
            .order_by("-creado")[:5]
        )

        alertas_data = []
        for alerta in alertas:
            ciudadano_nombre = "Sin ciudadano"
            if getattr(alerta, "ciudadano", None):
                apellido = alerta.ciudadano.apellido or ""
                nombre = alerta.ciudadano.nombre or ""
                ciudadano_nombre = f"{apellido}, {nombre}".strip(", ").strip() or "Sin ciudadano"

            alertas_data.append(
                {
                    "id": alerta.id,
                    "ciudadano_id": alerta.ciudadano_id,
                    "ciudadano": ciudadano_nombre,
                    "tipo": alerta.get_tipo_display(),
                    "prioridad": alerta.prioridad,
                    "fecha": alerta.creado.strftime("%d/%m %H:%M"),
                    "mensaje": alerta.mensaje,
                }
            )

        return Response({"results": alertas_data})
    except Exception as e:
        logger.error(f"Error en alertas_criticas: {e}", exc_info=True)
        return Response({"results": []}, status=200)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def actividad_reciente(request):
    """Obtiene actividad reciente del sistema."""
    try:
        inscripciones = InscripcionPrograma.objects.select_related("ciudadano", "programa", "responsable").order_by(
            "-creado"
        )[:4]
        derivaciones = DerivacionPrograma.objects.select_related(
            "ciudadano", "programa_origen", "programa_destino", "derivado_por"
        ).order_by("-creado")[:3]
        alertas = AlertaCiudadano.objects.select_related("ciudadano").filter(activa=True).order_by("-creado")[:2]

        actividades = []

        for inscripcion in inscripciones:
            apellido = getattr(inscripcion.ciudadano, "apellido", "") or ""
            nombre = getattr(inscripcion.ciudadano, "nombre", "") or ""
            ciudadano_nombre = f"{apellido}, {nombre}".strip(", ").strip() or "Ciudadano"
            usuario = inscripcion.responsable.get_full_name() if inscripcion.responsable else "Sistema"

            actividades.append(
                {
                    "descripcion": f"Nueva inscripción en {inscripcion.programa.nombre} para {ciudadano_nombre}",
                    "usuario": usuario,
                    "tiempo": _tiempo_relativo(inscripcion.creado),
                    "timestamp": inscripcion.creado.isoformat(),
                    "tipo": "create",
                    "icono": "fas fa-plus",
                }
            )

        for derivacion in derivaciones:
            usuario = derivacion.derivado_por.get_full_name() if derivacion.derivado_por else "Sistema"
            destino = derivacion.programa_destino.nombre if derivacion.programa_destino else "Programa"

            actividades.append(
                {
                    "descripcion": f"Derivación a {destino}",
                    "usuario": usuario,
                    "tiempo": _tiempo_relativo(derivacion.creado),
                    "timestamp": derivacion.creado.isoformat(),
                    "tipo": "update",
                    "icono": "fas fa-check",
                }
            )

        for alerta in alertas:
            actividades.append(
                {
                    "descripcion": f"Alerta: {alerta.get_tipo_display()}",
                    "usuario": "Sistema",
                    "tiempo": _tiempo_relativo(alerta.creado),
                    "timestamp": alerta.creado.isoformat(),
                    "tipo": "alert",
                    "icono": "fas fa-exclamation-triangle",
                }
            )

        actividades.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        for item in actividades:
            item.pop("timestamp", None)

        return Response({"results": actividades[:8]})
    except Exception as e:
        logger.error(f"Error en actividad_reciente: {e}", exc_info=True)
        return Response({"results": []}, status=200)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def tendencias_datos(request):
    """Obtiene datos para grafico de tendencias."""
    periodo = request.GET.get("periodo", "30d")
    dias_map = {"7d": 7, "30d": 30, "90d": 90}
    dias = dias_map.get(periodo, 30)

    try:
        fecha_inicio = timezone.now().date() - timedelta(days=dias)

        from django.db.models.functions import TruncDate

        legajos_por_fecha = (
            InscripcionPrograma.objects.filter(fecha_inscripcion__gte=fecha_inicio)
            .annotate(fecha=TruncDate("fecha_inscripcion"))
            .values("fecha")
            .annotate(count=Count("id"))
            .order_by("fecha")
        )

        datos_dict = {item["fecha"]: item["count"] for item in legajos_por_fecha}

        datos = []
        labels = []
        for i in range(dias):
            fecha = fecha_inicio + timedelta(days=i)
            datos.append(datos_dict.get(fecha, 0))
            labels.append(fecha.strftime("%d/%m"))

        return Response({"labels": labels, "datos": datos})
    except Exception as e:
        logger.error(f"Error en tendencias: {e}", exc_info=True)
        return Response({"labels": [], "datos": []}, status=500)


def _tiempo_relativo(fecha):
    """Convierte fecha a tiempo relativo."""
    if isinstance(fecha, datetime):
        fecha = fecha.replace(tzinfo=None)
    elif hasattr(fecha, "date"):
        fecha = datetime.combine(fecha, datetime.min.time())

    ahora = datetime.now()
    diff = ahora - fecha

    if diff.days > 0:
        return f"Hace {diff.days} dia{'s' if diff.days > 1 else ''}"
    if diff.seconds > 3600:
        horas = diff.seconds // 3600
        return f"Hace {horas} hora{'s' if horas > 1 else ''}"
    if diff.seconds > 60:
        minutos = diff.seconds // 60
        return f"Hace {minutos} minuto{'s' if minutos > 1 else ''}"
    return "Hace unos segundos"
