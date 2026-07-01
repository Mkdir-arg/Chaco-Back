"""Vista de la solapa dinámica 'Becas' en el legajo del ciudadano (issue #80)."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from core.rbac import requiere
from legajos.models import Ciudadano
from programas.services.solapas import SolapasService

CAP = "ciudadano.ver"


@login_required
@requiere(CAP)
def becas_ciudadano_detalle(request, pk):
    ciudadano = get_object_or_404(Ciudadano, pk=pk)
    contexto = SolapasService.obtener_resumen_becas_ciudadano(ciudadano)
    contexto["ciudadano"] = ciudadano

    return render(request, "programas/becas/ciudadano_detalle.html", contexto)
