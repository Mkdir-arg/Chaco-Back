"""Proceso masivo a SIIS: pantalla no listada para lanzar el circuito en lote.

No figura en ningún menú ni link, pero lo que la protege es la capacidad
``becas.programa.proceso_masivo``, no el hecho de estar escondida: esconder un
botón que aprueba mil casos y los registra en un sistema provincial es
prolijidad, no seguridad.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.views.generic.detail import DetailView

from core.rbac import CapacidadRequeridaMixin, requiere
from programas.models import CorridaSiis, ProgramaSiis

# Alias: este módulo ya se llama proceso_masivo; sin él, dentro del archivo
# ``proceso_masivo`` sería ambiguo para quien lo lea.
from programas.services import proceso_masivo as servicio

CAP_PROCESO_MASIVO = "becas.programa.proceso_masivo"
TOTAL_MAXIMO = 5000


class ProcesoMasivoView(CapacidadRequeridaMixin, LoginRequiredMixin, DetailView):
    model = ProgramaSiis
    capacidades_requeridas = CAP_PROCESO_MASIVO
    template_name = "programas/becas/config/proceso_masivo.html"
    context_object_name = "programa"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["corrida"] = CorridaSiis.objects.filter(programa=self.object).order_by("-creado").first()
        ctx["en_curso"] = CorridaSiis.en_curso()
        ctx["pendientes"] = servicio.candidatos(programa=self.object).count()
        ctx["total_maximo"] = TOTAL_MAXIMO
        return ctx


@login_required
@requiere(CAP_PROCESO_MASIVO)
@require_POST
def proceso_masivo_lanzar(request, pk):
    """Crea la corrida y devuelve enseguida: el trabajo sigue en un hilo."""
    programa = get_object_or_404(ProgramaSiis, pk=pk)
    destino = redirect("becas:proceso_masivo", pk=programa.pk)

    if CorridaSiis.en_curso() is not None:
        messages.error(request, "Ya hay una corrida en curso. Esperá a que termine o frenala.")
        return destino

    try:
        total = int(request.POST.get("total_pedido") or 0)
    except ValueError:
        total = 0
    if not 1 <= total <= TOTAL_MAXIMO:
        messages.error(request, f"La cantidad tiene que estar entre 1 y {TOTAL_MAXIMO}.")
        return destino

    corrida = CorridaSiis.objects.create(programa=programa, solicitada_por=request.user, total_pedido=total)
    servicio.lanzar(corrida, responsable=request.user)
    messages.success(request, f"Corrida lanzada por {total} casos.")
    return destino


@login_required
@requiere(CAP_PROCESO_MASIVO)
@require_POST
def proceso_masivo_frenar(request, pk):
    """Pide el freno. **No** cambia el estado: eso lo hace el proceso.

    El estado final lo escribe quien está corriendo, al cerrar el lote en curso.
    Si lo marcara este request, la pantalla diría «cancelada» mientras el hilo
    sigue procesando los casos que le quedan del lote.
    """
    programa = get_object_or_404(ProgramaSiis, pk=pk)
    corrida = CorridaSiis.en_curso()
    if corrida is None:
        messages.info(request, "No hay ninguna corrida en curso.")
    else:
        CorridaSiis.objects.filter(pk=corrida.pk).update(cancelacion_pedida=True)
        messages.success(
            request,
            "Se pidió frenar. El proceso corta al terminar el lote en curso: puede tardar hasta 40 casos.",
        )
    return redirect("becas:proceso_masivo", pk=programa.pk)
