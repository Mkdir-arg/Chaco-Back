"""APIs del dashboard: cada una pide la capacidad de lo que devuelve.

SEC-14 (auditoría oct-2026): alcanzaba con estar autenticado. `buscar-ciudadanos`
devolvía nombre y DNI del padrón por prefijo —hasta 20 por consulta más `has_more`,
suficiente para enumerarlo— y las alertas y la actividad reciente salían del alcance
global, sin pasar por `FiltrosUsuarioService`.

RED-37 punto 3 (Ola 7): las cinco eran `@api_view` sin serializer, así que
drf-spectacular las descartaba enteras («unable to guess serializer. Ignoring
view for now») y el esquema no publicaba ni la ruta. Ahora cada una declara su
respuesta con `inline_serializer`, que es el único mecanismo que no obliga a
inventar un `GenericAPIView` ni a mover la lógica. Los nombres de campo son
**los que ya devolvía la vista** —`results`, `has_more`, `labels`, `datos`…—: el
esquema documenta el contrato de RED-42, no uno nuevo.
`dashboard/tests/test_api_contrato.py::EsquemaContraElJsonRealTests` cruza las
dos mitades, así que un serializer que se despegue de la vista pone un test en
rojo.
"""

import logging
from datetime import datetime, timedelta

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.html import escape
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core.api_permissions import BackofficeAutenticado, RequiereCapacidad
from legajos.models import AlertaCiudadano, Ciudadano
from legajos.services.filtros_usuario import FiltrosUsuarioService
from programas.models import DerivacionPrograma, InscripcionPrograma
from users.models import User

logger = logging.getLogger(__name__)


def _contador(nombre, campos):
    """Un objeto anidado de puros enteros (los bloques de `metricas_dashboard`)."""
    return inline_serializer(name=nombre, fields={campo: serializers.IntegerField() for campo in campos})


@extend_schema(
    summary="Métricas del inicio del backoffice",
    description=(
        "Totales globales del sistema, cacheados 60 s. No se acotan al alcance del "
        "usuario: son conteos agregados, y la capacidad `dashboard.ver` es la que los habilita."
    ),
    responses={
        200: inline_serializer(
            name="MetricasDashboard",
            fields={
                "metricas": _contador("MetricasDashboardTotales", ["ciudadanos", "legajos", "seguimientos", "alertas"]),
                "estados_legajos": _contador(
                    "MetricasDashboardEstados", ["abiertos", "seguimiento", "derivados", "cerrados"]
                ),
                "usuarios_conectados": serializers.IntegerField(),
            },
        )
    },
)
@api_view(["GET"])
@permission_classes([BackofficeAutenticado, RequiereCapacidad("dashboard.ver")])
def metricas_dashboard(request):
    """Obtiene metricas principales del dashboard (datos globales, cacheados 60 s)."""
    from django.core.cache import cache

    data = cache.get_or_set("dashboard:metricas_api", _calcular_metricas_dashboard, 60)
    return Response(data)


def _calcular_metricas_dashboard():
    total_ciudadanos = Ciudadano.objects.count()
    alertas_activas = AlertaCiudadano.objects.filter(activa=True).count()

    # `localdate()`: `fecha_inscripcion` es un DateField en hora local, así que
    # con la fecha UTC el contador «de hoy» daba 0 entre las 21 y las 24 (BEC-18).
    hoy = timezone.localdate()
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


@extend_schema(
    summary="Búsqueda rápida de ciudadanos (typeahead del inicio)",
    description=(
        "Con menos de tres caracteres devuelve `results` vacío y **sin** `has_more`: "
        "es la rama corta de la vista, y el front la lee con la misma clave. "
        "`has_more` avisa que hay más de 20 coincidencias."
    ),
    parameters=[
        OpenApiParameter(
            "q",
            OpenApiTypes.STR,
            OpenApiParameter.QUERY,
            description="Prefijo de DNI (solo dígitos) o de nombre/apellido. Mínimo 3 caracteres.",
        )
    ],
    responses={
        200: inline_serializer(
            name="BusquedaCiudadanos",
            fields={
                "results": inline_serializer(
                    name="BusquedaCiudadanosItem",
                    many=True,
                    fields={
                        "id": serializers.IntegerField(),
                        "nombre": serializers.CharField(help_text="«Apellido, Nombre»"),
                        "dni": serializers.CharField(),
                    },
                ),
                "has_more": serializers.BooleanField(required=False),
            },
        ),
        500: inline_serializer(
            name="BusquedaCiudadanosError",
            fields={
                "results": serializers.ListField(child=serializers.DictField()),
                "error": serializers.CharField(),
            },
        ),
    },
)
@api_view(["GET"])
@permission_classes([BackofficeAutenticado, RequiereCapacidad("ciudadano.ver")])
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
        coincidencias = list(Ciudadano.objects.only("id", "nombre", "apellido", "dni").filter(filtro)[:21])
        hay_mas = len(coincidencias) > 20
        ciudadanos = coincidencias[:20]

        resultados = [{"id": c.id, "nombre": f"{c.apellido}, {c.nombre}", "dni": c.dni} for c in ciudadanos]
        return Response({"results": resultados, "has_more": hay_mas})
    except Exception as e:
        logger.error(f"Error en busqueda de ciudadanos: {e}", exc_info=True)
        return Response({"results": [], "error": "Error en la busqueda"}, status=500)


@extend_schema(
    summary="Alertas críticas y altas del alcance del usuario (hasta 5)",
    description=(
        "Si el cálculo falla, la vista responde **200** con `results` vacío a propósito: "
        "el panel del inicio se degrada en vez de romper la pantalla, y el traceback "
        "queda en el log del servidor."
    ),
    responses={
        200: inline_serializer(
            name="AlertasCriticas",
            fields={
                "results": inline_serializer(
                    name="AlertaCriticaItem",
                    many=True,
                    fields={
                        "id": serializers.IntegerField(),
                        "ciudadano_id": serializers.IntegerField(allow_null=True),
                        "ciudadano": serializers.CharField(help_text="«Apellido, Nombre» o «Sin ciudadano»"),
                        "tipo": serializers.CharField(help_text="Etiqueta legible del tipo de alerta"),
                        "prioridad": serializers.CharField(),
                        "fecha": serializers.CharField(help_text="`dd/mm HH:MM`, no ISO-8601"),
                        "mensaje": serializers.CharField(),
                    },
                )
            },
        )
    },
)
@api_view(["GET"])
@permission_classes([BackofficeAutenticado, RequiereCapacidad("ciudadano.sensible")])
def alertas_criticas(request):
    """Obtiene alertas criticas activas, acotadas al alcance del usuario."""
    try:
        alertas = (
            FiltrosUsuarioService.obtener_alertas_usuario(request.user)
            .filter(prioridad__in=["CRITICA", "ALTA"])
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


@extend_schema(
    summary="Feed de actividad reciente del inicio (hasta 8 eventos)",
    description=(
        "Mezcla inscripciones, derivaciones y alertas del alcance del usuario, ordenadas "
        "por fecha. El `timestamp` con el que se ordena **no sale** en la respuesta: la "
        "vista lo descarta después de ordenar. Un fallo devuelve 200 con `results` vacío."
    ),
    responses={
        200: inline_serializer(
            name="ActividadReciente",
            fields={
                "results": inline_serializer(
                    name="ActividadRecienteItem",
                    many=True,
                    fields={
                        "descripcion": serializers.CharField(),
                        "usuario": serializers.CharField(),
                        "tiempo": serializers.CharField(help_text="Texto relativo («Hace 2 horas»)"),
                        "tipo": serializers.ChoiceField(choices=["create", "update", "alert"]),
                        "icono": serializers.CharField(help_text="Clases de Font Awesome"),
                    },
                )
            },
        )
    },
)
@api_view(["GET"])
@permission_classes([BackofficeAutenticado, RequiereCapacidad("ciudadano.sensible")])
def actividad_reciente(request):
    """Actividad reciente del inicio, por tipo de evento y dentro del alcance.

    R0b-09: el feed listaba las últimas inscripciones y derivaciones **de todos
    los programas**, sin pasar por ningún alcance, y el tipo de la alerta —dato
    sensible— viajaba con ellas. Ahora todo sale acotado al alcance del usuario,
    el mismo que usa ``FiltrosUsuarioService`` para las alertas.

    La capacidad sigue siendo ``ciudadano.sensible``, la que el endpoint ya
    pedía: la rama de alertas es parte del feed, así que bajarla a
    ``ciudadano.ver`` abriría las inscripciones y derivaciones a roles que hoy
    no las ven —con ``config.administrar``, las de todo el sistema—. Ese cambio
    de alcance no entra en este PR (pendiente en la ficha G3-03).
    """
    try:
        inscripciones = FiltrosUsuarioService.acotar_a_programas_del_usuario(
            InscripcionPrograma.objects.select_related("ciudadano", "programa", "responsable"),
            request.user,
        ).order_by("-creado")[:4]
        derivaciones = FiltrosUsuarioService.acotar_a_programas_del_usuario(
            DerivacionPrograma.objects.select_related(
                "ciudadano", "programa_origen", "programa_destino", "derivado_por"
            ),
            request.user,
            campo="programa_destino_id",
        ).order_by("-creado")[:3]
        alertas = (
            FiltrosUsuarioService.obtener_alertas_usuario(request.user)
            .select_related("ciudadano")
            .order_by("-creado")[:2]
        )

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


@extend_schema(
    summary="Serie diaria de inscripciones para el gráfico del inicio",
    description=(
        "`labels` y `datos` tienen **siempre la misma longitud** y se emparejan por posición: "
        "Chart.js no las cruza por fecha. La serie termina hoy (hora local, no UTC)."
    ),
    parameters=[
        OpenApiParameter(
            "periodo",
            OpenApiTypes.STR,
            OpenApiParameter.QUERY,
            enum=["7d", "30d", "90d"],
            description="Cualquier otro valor cae a `30d`.",
        )
    ],
    responses={
        200: inline_serializer(
            name="TendenciasDashboard",
            fields={
                "labels": serializers.ListField(child=serializers.CharField(help_text="`dd/mm`")),
                "datos": serializers.ListField(child=serializers.IntegerField()),
            },
        )
    },
)
@api_view(["GET"])
@permission_classes([BackofficeAutenticado, RequiereCapacidad("dashboard.ver")])
def tendencias_datos(request):
    """Obtiene datos para grafico de tendencias."""
    periodo = request.GET.get("periodo", "30d")
    dias_map = {"7d": 7, "30d": 30, "90d": 90}
    dias = dias_map.get(periodo, 30)

    try:
        # G2-04: la serie termina **hoy**. Arrancaba en `hoy - dias` y recorría
        # `range(dias)`, así que el último punto era ayer y la actividad del día
        # en curso no aparecía nunca en el gráfico del inicio.
        #
        # `localdate()` y no `now().date()`: `fecha_inscripcion` es un DateField que
        # `auto_now_add` llena con `date.today()` —fecha local del proceso, que en
        # Linux es la de Argentina porque Django hace `os.environ["TZ"]` + `tzset()`—.
        # Con la fecha UTC, entre las 21 y las 24 de Argentina el último bucket quedaba
        # en «mañana» y salía siempre en cero. Es la corrección que propone BEC-18 para
        # este uso; el resto de los «hoy» UTC siguen abiertos en esa ficha.
        fecha_inicio = timezone.localdate() - timedelta(days=dias - 1)

        # ``fecha_inscripcion`` ya es un DateField: ``TruncDate`` no aportaba nada y
        # generaba ``DATE(CONVERT_TZ(...))``. Sin tablas de zona horaria —el MySQL de
        # ECOM no las tiene— CONVERT_TZ devuelve NULL, todo caía en un único bucket y el
        # gráfico salía en cero. Además la expresión no es indexable; agrupando por la
        # columna, la consulta se resuelve con el índice de la fecha.
        legajos_por_fecha = (
            InscripcionPrograma.objects.filter(fecha_inscripcion__gte=fecha_inicio)
            .values("fecha_inscripcion")
            .annotate(count=Count("id"))
            .order_by("fecha_inscripcion")
        )

        datos_dict = {item["fecha_inscripcion"]: item["count"] for item in legajos_por_fecha}

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
