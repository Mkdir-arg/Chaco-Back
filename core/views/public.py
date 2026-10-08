# Create your views here.
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from dashboard.utils import (
    contar_alertas_activas,
    contar_ciudadanos,
    contar_legajos_atencion,
    contar_seguimientos_hoy,
    contar_usuarios,
)

from ..rbac import GRUPO_CIUDADANO_PORTAL, puede
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
@require_POST
def latido_de_sesion(request):
    """Avisa que el usuario sigue trabajando, aunque no haya pedido una pantalla.

    SEC-35. El contador del servidor
    (``core.middleware.ExpiracionPorInactividadMiddleware``) mide **pedidos**, y el
    del navegador mide actividad del usuario. Sin este latido, quien pasa veinte
    minutos tipeando un relevamiento largo —mouse y teclado todo el tiempo, ni un
    request— se encontraría con el login al guardar, y con el formulario perdido.
    ``idle-logout.js`` lo llama como mucho una vez por minuto y **solo** cuando
    hubo actividad real, que es la misma señal con la que decide no cerrar.

    No devuelve nada: el trabajo lo hizo el middleware al dejar pasar el request.
    """
    return JsonResponse({"ok": True})


@login_required
def inicio_view(request):
    """Vista para la página de inicio del sistema"""
    from datetime import timedelta

    from django.utils import timezone

    from programas.models import DerivacionPrograma, InscripcionPrograma

    User = get_user_model()
    ahora = timezone.now()
    hace_24h = ahora - timedelta(hours=24)
    inicio_mes = ahora.date().replace(day=1)
    # G2-04: la tarjeta dice «Legajos activos», así que cuenta `LegajoAtencion`.
    # `contar_legajos()` agrega `InscripcionPrograma` pese al nombre, y era lo que
    # hacía que el inicio y `/legajos/reportes/` se contradijeran en la misma sesión.
    legajo_stats = contar_legajos_atencion()
    seguimientos_hoy = contar_seguimientos_hoy()

    context = {
        # El título del encabezado canónico se arma acá: `{% page_header %}` toma
        # `titulo` como argumento con nombre y lo escapa (FE-22, el hero salió).
        "titulo_inicio": f"Hola, {request.user.get_short_name() or request.user.get_username()}",
        "total_ciudadanos": contar_ciudadanos(),
        # G2-04: es el último ingreso de las últimas 24 h, no «usuarios activos».
        # Los ciudadanos del portal quedan afuera: el grupo `Ciudadanos` es un
        # marcador de identidad del portal, no un rol del backoffice, y contarlos
        # infla un número que la home presenta como operación interna.
        "ingresos_24h": cache.get_or_set(
            "home:ingresos_backoffice_24h",
            lambda: User.objects.filter(last_login__gte=hace_24h).exclude(groups__name=GRUPO_CIUDADANO_PORTAL).count(),
            300,
        ),
        "registros_mes": cache.get_or_set(
            "home:inscripciones_mes",
            lambda: InscripcionPrograma.objects.filter(fecha_inscripcion__gte=inicio_mes).count(),
            300,
        ),
        "total_usuarios": contar_usuarios(),
        "total_legajos": legajo_stats["total"],
        "legajos_activos": legajo_stats["activos"],
        "seguimientos_hoy": seguimientos_hoy,
        "alertas_activas": contar_alertas_activas(),
    }
    # FE-22: las cuatro tarjetas pasan a `components/_stat_card.html`, que recibe el pie
    # como un texto ya armado. Los dos que concuerdan en número se arman acá —igual que
    # `titulo_inicio`—, porque el template no sabe concatenar sin volverse ilegible.
    context["pie_ciudadanos"] = (
        f"{context['registros_mes']} inscripci{'ón' if context['registros_mes'] == 1 else 'ones'} este mes"
    )
    context["pie_legajos"] = f"de {context['total_legajos']} legajos en total"
    context["pie_alertas"] = (
        f"{context['ingresos_24h']} ingreso{'' if context['ingresos_24h'] == 1 else 's'} "
        "al backoffice en las últimas 24 h"
    )

    # --- Mi trabajo de hoy ---
    # Los dos paneles nombran ciudadanos y DNIs: van detrás de la capacidad que
    # habilita la pantalla de la que salen (SEC-14, auditoría oct-2026). La home la
    # ve cualquier usuario autenticado del backoffice, así que sin capacidad el panel
    # directamente no se arma (el template lo esconde con el mismo `|puede`).
    context["derivaciones_pendientes_count"] = 0
    context["derivaciones_pendientes"] = []
    if puede(request.user, "ciudadano.ver"):
        derivaciones_pendientes = (
            DerivacionPrograma.objects.filter(estado="PENDIENTE")
            .select_related("ciudadano", "programa_origen", "programa_destino")
            .order_by("-creado")
        )
        context["derivaciones_pendientes_count"] = derivaciones_pendientes.count()
        context["derivaciones_pendientes"] = derivaciones_pendientes[:8]

    context["conversaciones_sin_asignar_count"] = 0
    context["conversaciones_sin_asignar"] = []
    if puede(request.user, "conversacion.operar"):
        try:
            from conversaciones.models import Conversacion
            from conversaciones.selectors import get_conversaciones_pendientes_count

            conversaciones_sin_asignar = Conversacion.objects.filter(
                estado="pendiente", operador_asignado__isnull=True
            ).order_by("-fecha_inicio")
            context["conversaciones_sin_asignar_count"] = get_conversaciones_pendientes_count(request.user)
            context["conversaciones_sin_asignar"] = conversaciones_sin_asignar[:8]
        except Exception:
            context["conversaciones_sin_asignar_count"] = 0
            context["conversaciones_sin_asignar"] = []

    # --- Inscripciones activas por programa (gráfico) ---
    # Era la única lectura pesada de la home sin cachear: agrega toda la tabla de
    # inscripciones en cada carga. Es un gráfico de volúmenes, no una bandeja de trabajo
    # ni un contador de pendientes, así que 5 minutos de retraso no cambian nada. Mismo
    # TTL que los contadores vecinos de esta vista.
    context["programas_chart"] = cache.get_or_set("home:programas_chart", _inscripciones_por_programa, 300)

    return render(request, "inicio.html", context)


def _inscripciones_por_programa():
    """Top 10 de programas por inscripciones vigentes, para el gráfico de la home."""
    from django.db.models import Count, Q

    from programas.models import Programa

    return [
        {
            "nombre": programa.nombre,
            "color": programa.color or "#3B82F6",
            "count": programa.inscripciones_activas,
        }
        for programa in Programa.objects.annotate(
            inscripciones_activas=Count(
                "inscripciones",
                filter=Q(inscripciones__estado__in=["ACTIVO", "EN_SEGUIMIENTO"]),
            )
        )
        .filter(inscripciones_activas__gt=0)
        .order_by("-inscripciones_activas")[:10]
    ]


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
