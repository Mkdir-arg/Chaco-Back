from legajos.models import Ciudadano
from legajos.models_programas import InscripcionPrograma, Programa


def get_portal_home_context():
    return {
        "programas": Programa.objects.filter(estado='ACTIVO').order_by("orden"),
        "instituciones": [],
        "stats": {
            "ciudadanos": Ciudadano.objects.count(),
            "instituciones": 0,
            "programas": Programa.objects.filter(estado='ACTIVO').count(),
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
