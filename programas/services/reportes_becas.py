"""Datasets de solo lectura para los reportes transversales de Becas."""

from collections import Counter
from datetime import datetime, time, timedelta

from django.db.models import Count, F, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from programas.models import Formulario, ListaEspera, Relevamiento, TracaFormulario, ValidacionSIS
from programas.services.autorizacion import (
    convocatorias_visibles,
    es_coordinador_regional_becas,
    segmentos_visibles,
    subsegmentos_visibles,
)
from programas.services.reportes import Reporte


def _formularios(user):
    return Formulario.objects.filter(relevamiento__convocatoria__in=convocatorias_visibles(user))


def _aware_start(fecha):
    return timezone.make_aware(datetime.combine(fecha, time.min), timezone.get_current_timezone())


def _filter_creado_rango(qs, desde=None, hasta=None):
    if desde:
        qs = qs.filter(creado__gte=_aware_start(desde))
    if hasta:
        qs = qs.filter(creado__lt=_aware_start(hasta + timedelta(days=1)))
    return qs


def reporte_cupos(user, *, segmento_id=None, solo_activos=False):
    segmentos = segmentos_visibles(user).select_related("programa")
    if segmento_id:
        segmentos = segmentos.filter(pk=segmento_id)
    convs = convocatorias_visibles(user)
    distribuido_por_segmento = dict(
        subsegmentos_visibles(user)
        .values("segmento_id")
        .annotate(total=Sum("cupo_maximo"))
        .values_list("segmento_id", "total")
    )
    ocupado_por_segmento = dict(
        _formularios(user)
        .filter(estado=Formulario.Estado.APROBADO)
        .values("relevamiento__convocatoria__segmento_id")
        .annotate(total=Count("pk"))
        .values_list("relevamiento__convocatoria__segmento_id", "total")
    )
    espera_por_segmento = dict(
        ListaEspera.objects.filter(formulario__relevamiento__convocatoria__in=convs, promovido=False)
        .values("segmento_id")
        .annotate(total=Count("pk"))
        .values_list("segmento_id", "total")
    )
    filas = []
    alcance_regional = es_coordinador_regional_becas(user)
    for segmento in segmentos:
        distribuido = distribuido_por_segmento.get(segmento.pk, 0)
        ocupado = ocupado_por_segmento.get(segmento.pk, 0)
        espera = espera_por_segmento.get(segmento.pk, 0)
        programa_estado = (segmento.programa.siis_programa_estado or "").upper() if segmento.programa_id else ""
        if programa_estado and programa_estado != "ACTIVO":
            estado = "Bloqueado por SIIS"
        elif segmento.pausa_efectiva:
            estado = "Pausado"
        else:
            estado = "Activo"
        if solo_activos and estado != "Activo":
            continue
        cupo_maximo = distribuido if alcance_regional else segmento.cupo_maximo
        filas.append(
            (
                segmento.nombre,
                cupo_maximo,
                distribuido,
                ocupado,
                max(cupo_maximo - ocupado, 0),
                espera,
                estado,
            )
        )
    return Reporte(
        ("Segmento", "Cupo máximo", "Distribuido", "Ocupado", "Disponible", "Lista de espera", "Estado"), tuple(filas)
    )


def reporte_avance(user, *, segmento_id=None, desde=None, hasta=None, estado=None):
    qs = (
        convocatorias_visibles(user)
        .select_related("segmento", "subsegmento")
        .annotate(
            rel_asignados=Count(
                "relevamientos", filter=Q(relevamientos__estado=Relevamiento.Estado.ASIGNADO), distinct=True
            ),
            rel_en_curso=Count(
                "relevamientos", filter=Q(relevamientos__estado=Relevamiento.Estado.EN_CURSO), distinct=True
            ),
            rel_finalizados=Count(
                "relevamientos", filter=Q(relevamientos__estado=Relevamiento.Estado.FINALIZADO), distinct=True
            ),
            rel_en_revision=Count(
                "relevamientos", filter=Q(relevamientos__estado=Relevamiento.Estado.EN_REVISION), distinct=True
            ),
            rel_terminados=Count(
                "relevamientos", filter=Q(relevamientos__estado=Relevamiento.Estado.TERMINADO), distinct=True
            ),
            form_total=Count("relevamientos__formularios", distinct=True),
            form_enviados=Count(
                "relevamientos__formularios",
                filter=Q(relevamientos__formularios__estado=Formulario.Estado.ENVIADO),
                distinct=True,
            ),
            form_aprobados=Count(
                "relevamientos__formularios",
                filter=Q(relevamientos__formularios__estado=Formulario.Estado.APROBADO),
                distinct=True,
            ),
            form_rechazados=Count(
                "relevamientos__formularios",
                filter=Q(relevamientos__formularios__estado=Formulario.Estado.RECHAZADO),
                distinct=True,
            ),
            form_baja=Count(
                "relevamientos__formularios",
                filter=Q(relevamientos__formularios__estado=Formulario.Estado.BAJA),
                distinct=True,
            ),
        )
    )
    if segmento_id:
        qs = qs.filter(segmento_id=segmento_id)
    if desde:
        qs = qs.filter(fecha_fin__gte=desde)
    if hasta:
        qs = qs.filter(fecha_inicio__lte=hasta)
    if estado == "activas":
        qs = qs.filter(activo=True)
    elif estado == "cerradas":
        qs = qs.filter(activo=False)
    filas = []
    for conv in qs:
        revisados = conv.form_aprobados + conv.form_rechazados + conv.form_baja
        porcentaje = round(revisados * 100 / conv.form_total, 1) if conv.form_total else 0
        estado_texto = (
            "Activa" if conv.activo else ("Cerrada por vencimiento" if conv.cerrada_automaticamente else "Cerrada")
        )
        filas.append(
            (
                conv.nombre,
                conv.segmento.nombre,
                conv.subsegmento.nombre if conv.subsegmento else "—",
                conv.fecha_inicio,
                conv.fecha_fin,
                estado_texto,
                conv.rel_asignados,
                conv.rel_en_curso,
                conv.rel_finalizados,
                conv.rel_en_revision,
                conv.rel_terminados,
                conv.form_enviados,
                conv.form_aprobados,
                conv.form_rechazados,
                conv.form_baja,
                f"{porcentaje}%",
                f"{conv.form_aprobados}/{conv.segmento.cupo_maximo}",
            )
        )
    return Reporte(
        (
            "Convocatoria",
            "Segmento",
            "Subsegmento",
            "Desde",
            "Hasta",
            "Estado",
            "Rel. asignados",
            "Rel. en curso",
            "Rel. finalizados",
            "Rel. en revisión",
            "Rel. terminados",
            "Form. enviados",
            "Form. aprobados",
            "Form. rechazados",
            "Form. baja",
            "% revisado",
            "Aprobados/cupo",
        ),
        tuple(filas),
    )


def reporte_produccion(user, *, segmento_id=None, territorial_id=None, desde=None, hasta=None):
    qs = Relevamiento.objects.filter(convocatoria__in=convocatorias_visibles(user))
    if segmento_id:
        qs = qs.filter(convocatoria__segmento_id=segmento_id)
    if territorial_id:
        qs = qs.filter(territorial_id=territorial_id)
    if desde:
        qs = qs.filter(fecha_hasta__gte=desde)
    if hasta:
        qs = qs.filter(fecha_asignada__lte=hasta)
    # Los relevamientos públicos no tienen territorial: no son "producción
    # territorial" y romperían el agrupado (revisión Cambio 40).
    qs = qs.filter(territorial__isnull=False)
    ahora = timezone.now()
    grupos = {}
    campos_grupo = (
        "territorial_id",
        "territorial__first_name",
        "territorial__last_name",
        "territorial__username",
        "convocatoria__segmento_id",
        "convocatoria__segmento__nombre",
    )
    rels = qs.values(*campos_grupo, "estado", "fecha_hasta").annotate(total=Count("pk"))
    for rel in rels:
        clave = (rel["territorial_id"], rel["convocatoria__segmento_id"])
        grupo = grupos.setdefault(
            clave,
            {
                "territorial__first_name": rel["territorial__first_name"],
                "territorial__last_name": rel["territorial__last_name"],
                "territorial__username": rel["territorial__username"],
                "convocatoria__segmento__nombre": rel["convocatoria__segmento__nombre"],
                "asignados": 0,
                "terminados": 0,
                "vencidos": 0,
                "formularios": 0,
                "aprobados": 0,
                "rechazados": 0,
            },
        )
        total = rel["total"]
        grupo["asignados"] += total
        if rel["estado"] == Relevamiento.Estado.TERMINADO:
            grupo["terminados"] += total
        if rel["estado"] in (Relevamiento.Estado.ASIGNADO, Relevamiento.Estado.EN_CURSO) and rel["fecha_hasta"] < ahora:
            grupo["vencidos"] += total

    forms = (
        Formulario.objects.filter(relevamiento__in=qs)
        .values(
            "relevamiento__territorial_id",
            "relevamiento__territorial__first_name",
            "relevamiento__territorial__last_name",
            "relevamiento__territorial__username",
            "relevamiento__convocatoria__segmento_id",
            "relevamiento__convocatoria__segmento__nombre",
            "estado",
        )
        .annotate(total=Count("pk"))
    )
    for form in forms:
        clave = (form["relevamiento__territorial_id"], form["relevamiento__convocatoria__segmento_id"])
        grupo = grupos.setdefault(
            clave,
            {
                "territorial__first_name": form["relevamiento__territorial__first_name"],
                "territorial__last_name": form["relevamiento__territorial__last_name"],
                "territorial__username": form["relevamiento__territorial__username"],
                "convocatoria__segmento__nombre": form["relevamiento__convocatoria__segmento__nombre"],
                "asignados": 0,
                "terminados": 0,
                "vencidos": 0,
                "formularios": 0,
                "aprobados": 0,
                "rechazados": 0,
            },
        )
        total = form["total"]
        grupo["formularios"] += total
        if form["estado"] == Formulario.Estado.APROBADO:
            grupo["aprobados"] += total
        elif form["estado"] == Formulario.Estado.RECHAZADO:
            grupo["rechazados"] += total

    filas = []
    for datos in grupos.values():
        formularios = datos["formularios"]
        aprobados = datos["aprobados"]
        porcentaje = round(aprobados * 100 / formularios, 1) if formularios else 0
        nombre = f"{datos['territorial__first_name']} {datos['territorial__last_name']}".strip()
        filas.append(
            (
                nombre or datos["territorial__username"],
                datos["convocatoria__segmento__nombre"],
                datos["asignados"],
                datos["terminados"],
                datos["vencidos"],
                formularios,
                aprobados,
                datos["rechazados"],
                f"{porcentaje}%",
            )
        )
    filas.sort(key=lambda fila: (-fila[5], fila[0]))
    return Reporte(
        (
            "Territorial",
            "Segmento",
            "Asignados",
            "Terminados",
            "Vencidos",
            "Formularios",
            "Aprobados",
            "Rechazados",
            "% aprobación",
        ),
        tuple(filas),
    )


def reporte_embudo(user, *, convocatoria_id=None, desde=None, hasta=None):
    qs = _formularios(user)
    if convocatoria_id:
        qs = qs.filter(relevamiento__convocatoria_id=convocatoria_id)
    qs = _filter_creado_rango(qs, desde, hasta)
    ultima = ValidacionSIS.objects.filter(formulario_id=OuterRef("pk")).order_by("-creado", "-pk")
    con_ultima = qs.annotate(
        ultimo_siis=Subquery(ultima.values("estado")[:1]),
        ultimo_siis_id=Subquery(ultima.values("pk")[:1]),
    )
    conteos = qs.aggregate(
        total=Count("pk"),
        renaper=Count("pk", filter=Q(validado_renaper=True)),
        aprobados=Count("pk", filter=Q(estado=Formulario.Estado.APROBADO)),
        rechazados=Count("pk", filter=Q(estado=Formulario.Estado.RECHAZADO)),
        baja=Count("pk", filter=Q(estado=Formulario.Estado.BAJA)),
    )
    total = conteos["total"] or 0
    aprobados = conteos["aprobados"] or 0
    etapas = (
        ("Formularios enviados", total),
        ("Validados RENAPER", conteos["renaper"] or 0),
        ("Aprobados", aprobados),
        ("Validación SIIS OK", con_ultima.filter(ultimo_siis=ValidacionSIS.Estado.OK).count()),
        ("Beneficiarios", aprobados),
        ("Lista de espera", qs.filter(lista_espera__promovido=False).distinct().count()),
        ("Rechazados", conteos["rechazados"] or 0),
        ("Dados de baja", conteos["baja"] or 0),
    )
    filas = [(etapa, cantidad, f"{round(cantidad * 100 / total, 1) if total else 0}%") for etapa, cantidad in etapas]
    motivos_backoffice = Counter(
        motivo or "Sin motivo informado"
        for motivo in qs.filter(estado=Formulario.Estado.RECHAZADO).values_list("motivo_rechazo", flat=True)
    )
    ultimas_rechazadas = con_ultima.filter(ultimo_siis=ValidacionSIS.Estado.RECHAZADO)
    validaciones = ValidacionSIS.objects.filter(pk__in=ultimas_rechazadas.values("ultimo_siis_id"))
    for motivo, cantidad in motivos_backoffice.items():
        filas.append(
            (f"Rechazo backoffice: {motivo}", cantidad, f"{round(cantidad * 100 / total, 1) if total else 0}%")
        )
    motivos_siis = Counter(
        validacion.motivo_amigable or validacion.codigo_motivo or "Sin motivo informado" for validacion in validaciones
    )
    for motivo, cantidad in motivos_siis.items():
        filas.append((f"Rechazo SIIS: {motivo}", cantidad, f"{round(cantidad * 100 / total, 1) if total else 0}%"))
    return Reporte(("Etapa / motivo", "Cantidad", "% sobre formularios"), tuple(filas))


def beneficiarios_queryset(user, *, segmento_id=None, convocatoria_id=None, desde=None, hasta=None):
    aprobacion = TracaFormulario.objects.filter(
        formulario_id=OuterRef("pk"), campo__iexact="estado", valor_nuevo__icontains="APROBADO"
    ).order_by("-created_at", "-pk")
    qs = (
        _formularios(user)
        .filter(estado=Formulario.Estado.APROBADO)
        .select_related("ciudadano", "relevamiento__convocatoria__segmento", "relevamiento__convocatoria__subsegmento")
        .annotate(fecha_aprobacion_reporte=Coalesce(Subquery(aprobacion.values("created_at")[:1]), F("modificado")))
        .order_by("-fecha_aprobacion_reporte", "pk")
    )
    if segmento_id:
        qs = qs.filter(relevamiento__convocatoria__segmento_id=segmento_id)
    if convocatoria_id:
        qs = qs.filter(relevamiento__convocatoria_id=convocatoria_id)
    if desde:
        qs = qs.filter(fecha_aprobacion_reporte__gte=_aware_start(desde))
    if hasta:
        qs = qs.filter(fecha_aprobacion_reporte__lt=_aware_start(hasta + timedelta(days=1)))
    return qs


def reporte_beneficiarios_desde_queryset(qs):
    filas = []
    for form in qs:
        datos = form.datos_identificacion or {}
        nombre = (
            form.ciudadano.nombre_completo
            if form.ciudadano_id
            else f"{datos.get('nombre', '')} {datos.get('apellido', '')}".strip()
        )
        dni = form.ciudadano.dni if form.ciudadano_id else datos.get("dni", "")
        conv = form.relevamiento.convocatoria
        filas.append(
            (
                nombre or "Sin identificar",
                dni,
                conv.segmento.nombre,
                conv.subsegmento.nombre if conv.subsegmento else "—",
                conv.nombre,
                form.relevamiento.zona,
                form.fecha_aprobacion_reporte,
            )
        )
    return Reporte(
        ("Nombre", "DNI", "Segmento", "Subsegmento", "Convocatoria", "Zona", "Fecha de aprobación"), tuple(filas)
    )


def reporte_beneficiarios(user, *, segmento_id=None, convocatoria_id=None, desde=None, hasta=None):
    return reporte_beneficiarios_desde_queryset(
        beneficiarios_queryset(
            user,
            segmento_id=segmento_id,
            convocatoria_id=convocatoria_id,
            desde=desde,
            hasta=hasta,
        )
    )
