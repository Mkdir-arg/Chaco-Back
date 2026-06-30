"""Vista de la solapa dinámica 'Becas' en el legajo del ciudadano (issue #80)."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from core.rbac import requiere
from legajos.models import Ciudadano
from programas.models import Formulario

CAP = "ciudadano.ver"


def _estado_relevante(formularios):
    """Determina el estado más relevante del ciudadano en Becas.

    Asume que formularios tiene prefetch_related("lista_espera") aplicado.
    """
    estados = {f.estado for f in formularios}
    # Usa el prefetch para evitar queries adicionales
    en_espera = any(
        any(not le.promovido for le in f.lista_espera.all())
        for f in formularios
    )
    if Formulario.Estado.APROBADO in estados:
        return "Beneficiario", "success"
    if en_espera:
        return "Lista de espera", "warning"
    if Formulario.Estado.RECHAZADO in estados:
        return "Rechazado", "danger"
    if Formulario.Estado.BAJA in estados:
        return "Dado de baja", "gray"
    return "Pendiente", "gray"


@login_required
@requiere(CAP)
def becas_ciudadano_detalle(request, pk):
    ciudadano = get_object_or_404(Ciudadano, pk=pk)
    formularios = list(
        Formulario.objects.filter(ciudadano=ciudadano)
        .select_related(
            "relevamiento__convocatoria__segmento",
            "relevamiento__convocatoria__subsegmento",
        )
        .prefetch_related("lista_espera")
        .order_by("-creado")
    )

    # Anotar cada formulario con en_espera_activa usando el prefetch (sin queries extra)
    for f in formularios:
        f.en_espera_activa = any(not le.promovido for le in f.lista_espera.all())

    estado_texto, estado_color = _estado_relevante(formularios) if formularios else ("—", "gray")

    # Stat cards basadas en formulario más reciente
    formulario_reciente = formularios[0] if formularios else None
    segmento_nombre = (
        formulario_reciente.relevamiento.convocatoria.segmento.nombre
        if formulario_reciente
        else "—"
    )
    fecha_envio = formulario_reciente.creado if formulario_reciente else None

    return render(
        request,
        "programas/becas/ciudadano_detalle.html",
        {
            "ciudadano": ciudadano,
            "formularios": formularios,
            "estado_texto": estado_texto,
            "estado_color": estado_color,
            "segmento_nombre": segmento_nombre,
            "fecha_envio": fecha_envio,
            "Formulario": Formulario,  # para acceder a Estado choices en template
        },
    )
