from django.core.cache import cache

from legajos.models import Ciudadano
from programas.models import InscripcionPrograma, Programa


def _build_portal_home_context():
    # list(): el contexto va al cache y debe ser picklable (sin querysets lazy).
    programas = list(Programa.objects.filter(estado="ACTIVO").order_by("orden"))
    return {
        "programas": programas,
        "stats": {
            "ciudadanos": Ciudadano.objects.count(),
            "programas": len(programas),
            "inscripciones_activas": InscripcionPrograma.objects.filter(
                estado__in=["ACTIVO", "EN_SEGUIMIENTO"]
            ).count(),
        },
        "ciudadano_items": [
            "Mis programas sociales e inscripciones",
            "Consultas al equipo del programa",
            "Mis datos personales y contraseña",
        ],
        "consulta_items": [
            "Nueva consulta desde tu perfil",
            "Historial de tus conversaciones",
            "Respuesta del equipo del programa en tu cuenta",
        ],
    }


def get_portal_home_context():
    return cache.get_or_set("portal:home_ctx", _build_portal_home_context, 300)
