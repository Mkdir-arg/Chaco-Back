from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.shortcuts import render
from django.utils import timezone

from core.models import Municipio

from ..models.nachec import (
    CasoNachec,
    EvaluacionVulnerabilidad,
    PlanIntervencionNachec,
    PrestacionNachec,
    RelevamientoNachec,
    TareaNachec,
)


@login_required
def dashboard_nachec(request):
    """Dashboard integral del programa ÑACHEC"""
    periodo = request.GET.get("periodo", "semana")
    municipio_id = request.GET.get("municipio")

    hoy = timezone.now().date()
    if periodo == "dia":
        fecha_desde = hoy
    elif periodo == "semana":
        fecha_desde = hoy - timedelta(days=7)
    elif periodo == "mes":
        fecha_desde = hoy - timedelta(days=30)
    elif periodo == "trimestre":
        fecha_desde = hoy - timedelta(days=90)
    else:
        fecha_desde = hoy - timedelta(days=7)

    casos_qs = CasoNachec.objects.all()
    if municipio_id:
        casos_qs = casos_qs.filter(municipio=municipio_id)

    derivaciones_totales = casos_qs.count()
    derivaciones_nuevas = casos_qs.filter(creado__gte=fecha_desde).count()
    derivaciones_aceptadas = casos_qs.exclude(estado="RECHAZADO").count()
    derivaciones_pendientes = casos_qs.filter(estado="EN_REVISION").count()
    tasa_aceptacion = round((derivaciones_aceptadas / derivaciones_totales * 100) if derivaciones_totales > 0 else 0, 1)
    casos_incompletos = casos_qs.filter(
        Q(ciudadano_titular__dni__isnull=True) | Q(ciudadano_titular__telefono__isnull=True) | Q(direccion__isnull=True)
    ).count()

    relevamientos_completados = RelevamientoNachec.objects.filter(caso__in=casos_qs, completado=True).count()
    relevamientos_en_curso = casos_qs.filter(estado="EN_RELEVAMIENTO").count()
    relevamientos_sla_vencer = casos_qs.filter(
        estado__in=["ASIGNADO", "EN_RELEVAMIENTO"],
        sla_relevamiento__lte=hoy + timedelta(days=2),
        sla_relevamiento__gte=hoy,
    ).count()
    casos_sin_asignar = casos_qs.filter(estado="A_ASIGNAR").count()

    por_territorio = (
        casos_qs.values("municipio")
        .annotate(
            casos_total=Count("id"),
            relevamientos_completados=Count(
                "id",
                filter=Q(estado__in=["EVALUADO", "PLAN_DEFINIDO", "EN_EJECUCION", "EN_SEGUIMIENTO", "CERRADO"]),
            ),
        )
        .order_by("-casos_total")[:5]
    )
    for territorio in por_territorio:
        territorio["nombre"] = territorio["municipio"] or "Sin especificar"

    casos_evaluados = casos_qs.filter(estado__in=["PLAN_DEFINIDO", "EN_EJECUCION", "EN_SEGUIMIENTO", "CERRADO"]).count()
    casos_sin_evaluar = casos_qs.filter(estado="EVALUADO").count()

    evaluaciones = EvaluacionVulnerabilidad.objects.filter(caso__in=casos_qs)
    scoring_alto = evaluaciones.filter(categoria_final="ALTO").count()
    scoring_medio = evaluaciones.filter(categoria_final="MEDIO").count()
    scoring_bajo = evaluaciones.filter(categoria_final="BAJO").count()

    planes_activos = PlanIntervencionNachec.objects.filter(caso__in=casos_qs, vigente=True).count()
    planes_pendientes = casos_qs.filter(estado="PLAN_DEFINIDO").count()

    prestaciones_qs = PrestacionNachec.objects.filter(caso__in=casos_qs)
    prestaciones_programadas = prestaciones_qs.filter(estado="PROGRAMADA").count()
    prestaciones_en_proceso = prestaciones_qs.filter(estado__in=["EN_PROCESO", "EN_CURSO"]).count()
    prestaciones_entregadas = prestaciones_qs.filter(estado="ENTREGADA", fecha_entregada__gte=fecha_desde).count()
    prestaciones_vencidas = prestaciones_qs.filter(
        estado__in=["PROGRAMADA", "EN_PROCESO"],
        sla_hasta__lt=timezone.now(),
    ).count()

    prestaciones_con_sla = prestaciones_qs.filter(
        estado="ENTREGADA",
        sla_hasta__isnull=False,
        fecha_entregada__isnull=False,
    )
    cumplidas = sum(
        1
        for prestacion in prestaciones_con_sla
        if prestacion.fecha_entregada
        and prestacion.sla_hasta
        and timezone.make_aware(timezone.datetime.combine(prestacion.fecha_entregada, timezone.datetime.min.time()))
        <= prestacion.sla_hasta
    )
    cumplimiento_sla = round(
        (cumplidas / prestaciones_con_sla.count() * 100) if prestaciones_con_sla.count() > 0 else 0, 1
    )

    prestaciones_alimentaria = prestaciones_qs.filter(tipo="ALIMENTARIA").count()
    prestaciones_vivienda = prestaciones_qs.filter(tipo="VIVIENDA").count()
    prestaciones_salud = prestaciones_qs.filter(tipo="SALUD").count()
    prestaciones_educacion = prestaciones_qs.filter(tipo="EDUCACION").count()
    prestaciones_empleo = prestaciones_qs.filter(tipo="EMPLEO").count()
    prestaciones_emprendimiento = prestaciones_qs.filter(tipo="EMPRENDIMIENTO").count()

    casos_en_seguimiento = casos_qs.filter(estado="EN_SEGUIMIENTO").count()
    casos_cerrados = casos_qs.filter(estado="CERRADO", fecha_cierre__gte=fecha_desde).count()
    casos_reabiertos = (
        casos_qs.filter(
            historialestadocaso__estado_nuevo__in=["EN_SEGUIMIENTO", "EVALUADO", "PLAN_DEFINIDO"],
            historialestadocaso__estado_anterior="CERRADO",
            historialestadocaso__fecha__gte=fecha_desde,
        )
        .distinct()
        .count()
    )
    cierres_vencidos = TareaNachec.objects.filter(
        caso__in=casos_qs,
        tipo="OTRO",
        titulo__icontains="Cerrar caso",
        estado__in=["PENDIENTE", "EN_PROCESO"],
        fecha_vencimiento__lt=hoy,
    ).count()

    alertas_sla_vencido = TareaNachec.objects.filter(
        caso__in=casos_qs,
        estado__in=["PENDIENTE", "EN_PROCESO"],
        fecha_vencimiento__lt=hoy,
    ).count()
    casos_sin_relevamiento = casos_qs.filter(estado="ASIGNADO").count()
    cerrados_sin_evidencias = (
        casos_qs.filter(
            estado="CERRADO",
            prestacionnachec__estado="ENTREGADA",
        )
        .annotate(
            evidencias=Count("prestacionnachec__adjunto"),
        )
        .filter(evidencias=0)
        .distinct()
        .count()
    )

    familias_asistidas = casos_qs.filter(estado__in=["EN_EJECUCION", "EN_SEGUIMIENTO", "CERRADO"]).count()
    mejoras_vivienda = prestaciones_qs.filter(tipo="VIVIENDA", estado="ENTREGADA").count()
    capacitaciones = prestaciones_qs.filter(tipo__in=["EMPLEO", "EMPRENDIMIENTO"], estado="ENTREGADA").count()
    score_promedio = round(evaluaciones.aggregate(Avg("score_total"))["score_total__avg"] or 0, 1)

    municipios = Municipio.objects.all().order_by("nombre")

    metricas = {
        "derivaciones_totales": derivaciones_totales,
        "derivaciones_nuevas": derivaciones_nuevas,
        "derivaciones_aceptadas": derivaciones_aceptadas,
        "derivaciones_pendientes": derivaciones_pendientes,
        "tasa_aceptacion": tasa_aceptacion,
        "casos_incompletos": casos_incompletos,
        "por_territorio": por_territorio,
        "relevamientos_completados": relevamientos_completados,
        "relevamientos_en_curso": relevamientos_en_curso,
        "relevamientos_sla_vencer": relevamientos_sla_vencer,
        "casos_sin_asignar": casos_sin_asignar,
        "casos_evaluados": casos_evaluados,
        "casos_sin_evaluar": casos_sin_evaluar,
        "scoring_alto": scoring_alto,
        "scoring_medio": scoring_medio,
        "scoring_bajo": scoring_bajo,
        "planes_activos": planes_activos,
        "planes_pendientes": planes_pendientes,
        "prestaciones_programadas": prestaciones_programadas,
        "prestaciones_en_proceso": prestaciones_en_proceso,
        "prestaciones_entregadas": prestaciones_entregadas,
        "prestaciones_vencidas": prestaciones_vencidas,
        "cumplimiento_sla": cumplimiento_sla,
        "prestaciones_alimentaria": prestaciones_alimentaria,
        "prestaciones_vivienda": prestaciones_vivienda,
        "prestaciones_salud": prestaciones_salud,
        "prestaciones_educacion": prestaciones_educacion,
        "prestaciones_empleo": prestaciones_empleo,
        "prestaciones_emprendimiento": prestaciones_emprendimiento,
        "casos_en_seguimiento": casos_en_seguimiento,
        "casos_cerrados": casos_cerrados,
        "casos_reabiertos": casos_reabiertos,
        "cierres_vencidos": cierres_vencidos,
        "alertas_sla_vencido": alertas_sla_vencido,
        "casos_sin_relevamiento": casos_sin_relevamiento,
        "cerrados_sin_evidencias": cerrados_sin_evidencias,
        "familias_asistidas": familias_asistidas,
        "mejoras_vivienda": mejoras_vivienda,
        "capacitaciones": capacitaciones,
        "score_promedio": score_promedio,
    }

    return render(
        request,
        "legajos/nachec/dashboard.html",
        {
            "metricas": metricas,
            "municipios": municipios,
        },
    )
