from django.db.models import OuterRef, Subquery

from programas.models import InscripcionPrograma


def get_linked_inscripcion_for_legajo(legajo):
    return (
        InscripcionPrograma.objects.select_related("ciudadano", "programa", "responsable")
        .filter(legajo_id=legajo.id)
        .order_by("-fecha_inscripcion")
        .first()
    )


def get_legajo_ids_for_ciudadano(ciudadano):
    return InscripcionPrograma.objects.filter(
        ciudadano=ciudadano,
        legajo_id__isnull=False,
    ).values_list("legajo_id", flat=True)


def get_legajos_queryset_for_ciudadano(ciudadano, base_queryset=None):
    if base_queryset is None:
        from ..models import LegajoAtencion

        base_queryset = LegajoAtencion.objects.all()

    return base_queryset.filter(id__in=get_legajo_ids_for_ciudadano(ciudadano))


def get_legajo_ids_for_programas(programa_ids):
    return InscripcionPrograma.objects.filter(
        programa_id__in=programa_ids,
        legajo_id__isnull=False,
    ).values_list("legajo_id", flat=True).distinct()


def get_programa_ids_for_legajo_ids(legajo_ids):
    return InscripcionPrograma.objects.filter(
        legajo_id__in=legajo_ids,
    ).values_list("programa_id", flat=True).distinct()


def annotate_legajo_link_data(queryset):
    inscripciones = InscripcionPrograma.objects.filter(legajo_id=OuterRef("pk")).order_by(
        "-fecha_inscripcion"
    )
    return queryset.annotate(
        linked_ciudadano_id=Subquery(inscripciones.values("ciudadano_id")[:1]),
        linked_ciudadano_nombre=Subquery(inscripciones.values("ciudadano__nombre")[:1]),
        linked_ciudadano_apellido=Subquery(inscripciones.values("ciudadano__apellido")[:1]),
        linked_ciudadano_dni=Subquery(inscripciones.values("ciudadano__dni")[:1]),
        linked_programa_nombre=Subquery(inscripciones.values("programa__nombre")[:1]),
    )


def get_active_legajo_for_ciudadano(ciudadano):
    from ..models import LegajoAtencion

    return get_legajos_queryset_for_ciudadano(
        ciudadano,
        base_queryset=LegajoAtencion.objects.filter(
            estado__in=[
                LegajoAtencion.Estado.ABIERTO,
                LegajoAtencion.Estado.EN_SEGUIMIENTO,
            ]
        ),
    ).order_by("-fecha_admision").first()
