from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from legajos.models import Ciudadano
from programas.models import Admision, InscripcionPrograma
from programas.services.dispositivos import dispositivos_visibles, puede_en_programa_dispositivos


class CiudadanoDispositivosView(LoginRequiredMixin, TemplateView):
    template_name = "legajos/solapas/dispositivos.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not puede_en_programa_dispositivos(self.request.user, "dispositivo.ver"):
            raise PermissionDenied
        ciudadano = get_object_or_404(Ciudadano, pk=self.kwargs["ciudadano_id"])
        inscripcion = get_object_or_404(
            InscripcionPrograma,
            pk=self.kwargs["inscripcion_id"],
            ciudadano=ciudadano,
            programa__tipo="DISPOSITIVOS",
            estado__in=[InscripcionPrograma.Estado.ACTIVO, InscripcionPrograma.Estado.EN_SEGUIMIENTO],
        )
        admisiones = (
            Admision.objects.filter(
                ciudadano=ciudadano,
                inscripcion_programa=inscripcion,
                dispositivo__in=dispositivos_visibles(self.request.user),
            )
            .select_related("dispositivo", "cama")
            .order_by("-fecha_ingreso")
        )
        if not admisiones.filter(estado=Admision.Estado.ALOJADO).exists():
            raise PermissionDenied
        context.update({"ciudadano": ciudadano, "admisiones": admisiones})
        return context
