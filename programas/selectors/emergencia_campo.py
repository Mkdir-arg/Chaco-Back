"""Lo que lee la app de campo del módulo Emergencia (etapa 1: el agente territorial).

Lo de la mesa —bandeja, semáforo, panel de derivar— está en ``programas.selectors.emergencia``.
"""

from core.selectors.geografia import localidades_operativas
from programas.models import CasoEmergencia

#: Cuántos envíos muestra «Mis envíos». La lista es para confirmar que lo de hoy llegó, no
#: un historial: sin tope crece con cada jornada del agente.
TOPE_MIS_CASOS = 50


def casos_relevados_por(usuario):
    """Los últimos casos que ``usuario`` relevó **en territorio**, del más nuevo al más viejo.

    Solo los de origen ``TERRITORIO``: ``relevado_por`` también es quien carga un caso desde
    la mesa o hace un ingreso directo, y esos no son envíos de la app del agente.

    Presupuesto: **1 consulta** (el grupo viene en el mismo ``SELECT``) y como mucho
    :data:`TOPE_MIS_CASOS` filas.
    """
    return (
        CasoEmergencia.objects.filter(relevado_por=usuario, origen=CasoEmergencia.Origen.TERRITORIO)
        .select_related("grupo")
        .only("numero", "estado", "creado", "grupo__total_declarado")
        .order_by("-creado", "-pk")[:TOPE_MIS_CASOS]
    )


def localidades_para_relevar():
    """``[{"id", "nombre"}]`` de las localidades que ofrece el Formulario 1 (RN-1.6).

    Son las de la provincia que opera el sistema (``core.selectors.localidades_operativas``,
    el mismo universo que ofrece el backoffice), por nombre. **Sin coordenadas**:
    ``core.Localidad`` no las tiene (hallazgo H4 del plan).

    Presupuesto: **1 consulta**, sin paginar: la app la guarda entera una vez por día.
    """
    return list(localidades_operativas().order_by("nombre", "pk").values("id", "nombre"))
