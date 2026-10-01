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
        # SEC-29: las listas de «qué podés hacer con tu cuenta» (ciudadano_items /
        # consulta_items) se fueron junto con el portal ciudadano: la home ya no
        # ofrece login ni registro.
    }


def get_portal_home_context():
    return cache.get_or_set("portal:home_ctx", _build_portal_home_context, 300)
