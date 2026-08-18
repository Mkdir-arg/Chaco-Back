"""Datasets de solo lectura para los reportes transversales de Becas."""

from collections import Counter, defaultdict

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
    qs = (
        Relevamiento.objects.filter(convocatoria__in=convocatorias_visibles(user))
        .select_related("territorial", "convocatoria__segmento")
        .prefetch_related("formularios")
    )
    if segmento_id:
        qs = qs.filter(convocatoria__segmento_id=segmento_id)
    if territorial_id:
        qs = qs.filter(territorial_id=territorial_id)
    if desde:
        qs = qs.filter(fecha_hasta__gte=desde)
    if hasta:
        qs = qs.filter(fecha_asignada__lte=hasta)
    grupos = defaultdict(lambda: {"rels": [], "forms": []})
    for rel in qs:
        clave = (rel.territorial_id, rel.convocatoria.segmento_id)
        grupos[clave]["territorial"] = rel.territorial
        grupos[clave]["segmento"] = rel.convocatoria.segmento
        grupos[clave]["rels"].append(rel)
        grupos[clave]["forms"].extend(rel.formularios.all())
    filas = []
    hoy = timezone.localdate()
    for datos in grupos.values():
        rels, forms = datos["rels"], datos["forms"]
        estados = Counter(f.estado for f in forms)
        vencidos = sum(r.estado in ("ASIGNADO", "EN_CURSO") and r.fecha_hasta < hoy for r in rels)
        porcentaje = round(estados["APROBADO"] * 100 / len(forms), 1) if forms else 0
        usuario = datos["territorial"]
        filas.append(
            (
                usuario.get_full_name() or usuario.username,
                datos["segmento"].nombre,
                len(rels),
                sum(r.estado == "TERMINADO" for r in rels),
                vencidos,
                len(forms),
                estados["APROBADO"],
                estados["RECHAZADO"],
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
    if desde:
        qs = qs.filter(creado__date__gte=desde)
    if hasta:
        qs = qs.filter(creado__date__lte=hasta)
    ids = list(qs.values_list("pk", flat=True))
    ultima = ValidacionSIS.objects.filter(formulario_id=OuterRef("pk")).order_by("-creado", "-pk")
    con_ultima = qs.annotate(
        ultimo_siis=Subquery(ultima.values("estado")[:1]),
        ultimo_siis_id=Subquery(ultima.values("pk")[:1]),
    )
    total = qs.count()
    etapas = (
        ("Formularios enviados", total),
        ("Validados RENAPER", qs.filter(validado_renaper=True).count()),
        ("Aprobados", qs.filter(estado=Formulario.Estado.APROBADO).count()),
        ("Validación SIIS OK", con_ultima.filter(ultimo_siis=ValidacionSIS.Estado.OK).count()),
        ("Beneficiarios", qs.filter(estado=Formulario.Estado.APROBADO).count()),
        ("Lista de espera", ListaEspera.objects.filter(formulario_id__in=ids, promovido=False).count()),
        ("Rechazados", qs.filter(estado=Formulario.Estado.RECHAZADO).count()),
        ("Dados de baja", qs.filter(estado=Formulario.Estado.BAJA).count()),
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
        qs = qs.filter(fecha_aprobacion_reporte__date__gte=desde)
    if hasta:
        qs = qs.filter(fecha_aprobacion_reporte__date__lte=hasta)
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
