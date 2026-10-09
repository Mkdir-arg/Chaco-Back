from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from legajos.models import Ciudadano
from programas.models import InscripcionPrograma
from programas.services.dispositivos import puede_en_programa_dispositivos


class CiudadanoDispositivosView(LoginRequiredMixin, TemplateView):
    """Solapa de Dispositivos del legajo ciudadano, sin historial todavía.

    Listaba las admisiones del ciudadano con su cama y su fecha de ingreso. Esa
    lectura se fue con `Admision`; la reescribe la E2 del MVP contra `Estadia`,
    que es la que vuelve a dar historial. Hasta entonces la pantalla conserva su
    ruta y sus guardas —capacidad sobre el programa e inscripción vigente del
    ciudadano— y muestra el estado vacío, en vez de desaparecer y dejar el link
    del legajo en 404.
    """

    template_name = "legajos/solapas/dispositivos.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not puede_en_programa_dispositivos(self.request.user, "dispositivo.ver"):
            raise PermissionDenied
        ciudadano = get_object_or_404(Ciudadano, pk=self.kwargs["ciudadano_id"])
        get_object_or_404(
            InscripcionPrograma,
            pk=self.kwargs["inscripcion_id"],
            ciudadano=ciudadano,
            programa__tipo="DISPOSITIVOS",
            estado__in=[InscripcionPrograma.Estado.ACTIVO, InscripcionPrograma.Estado.EN_SEGUIMIENTO],
        )
        context["ciudadano"] = ciudadano
        return context
