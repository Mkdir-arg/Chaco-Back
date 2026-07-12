from django.core.cache import cache

from legajos.models import Ciudadano
from programas.models import InscripcionPrograma, Programa


def _build_portal_home_context():
    # list(): el contexto va al cache y debe ser picklable (sin querysets lazy).
    programas = list(Programa.objects.filter(estado="ACTIVO").order_by("orden"))
    return {
        "programas": programas,
        "instituciones": [],
        "stats": {
            "ciudadanos": Ciudadano.objects.count(),
            "instituciones": 0,
            "programas": len(programas),
            "inscripciones_activas": InscripcionPrograma.objects.filter(
                estado__in=["ACTIVO", "EN_SEGUIMIENTO"]
            ).count(),
        },
        "ciudadano_items": [
            "Mis programas sociales e inscripciones",
            "Consultas y reclamos municipales",
            "Mis datos personales y contraseña",
        ],
        "institucion_items": [
            "Registro guiado paso a paso",
            "Seguimiento del estado del trámite",
            "Articulación con programas municipales",
            "Mesa de ayuda especializada",
        ],
    }


def get_portal_home_context():
    return cache.get_or_set("portal:home_ctx", _build_portal_home_context, 300)
