from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import TemplateView

from core import rbac
from legajos.models import Ciudadano
from programas.selectors.trayectoria import trayectoria_de
from programas.services.dispositivos import CAP_VER, puede_en_programa_dispositivos


class CiudadanoDispositivosView(LoginRequiredMixin, TemplateView):
    """Solapa de Dispositivos del legajo ciudadano: la trayectoria completa de la persona.

    Lee de `Estadia` y muestra **todas** las estadías de la persona —abiertas y
    cerradas, de cualquier institución de la red—. Es de lectura: ni un botón operativo;
    para operar sobre una estadía hay que entrar al programa, donde sí manda el alcance.

    Qué la habilita
    ---------------

    Una sola cosa: **ser del programa**, que acá es tener `dispositivo.ver` con alcance
    al programa Dispositivos (un rol del programa o uno global que la tenga). Nunca el
    nombre de un grupo.

    Los tres candados que tenía quedaron afuera, cada uno por su razón:

    * *Exigir una admisión alojada.* La trayectoria existe aunque la persona ya no esté
      alojada: es justamente cuando más se consulta.
    * *Tirar `PermissionDenied` sin ella.* Una persona sin estadías es una trayectoria
      vacía, no un error: la pantalla lo dice con su estado vacío.
    * *Exigir la inscripción activa* (el `inscripcion_id` de la URL). La inscripción se
      cierra o se suspende, y la historia de la persona no se va con ella.

    Tampoco filtra por el alcance fino del dispositivo (`AsignacionDispositivo`): decisión
    §4.11 de la propuesta v2. Lo que limita es la sensibilidad de cada sección, y la
    trayectoria no trae ninguna (ver `programas.selectors.trayectoria`).
    """

    template_name = "legajos/solapas/dispositivos.html"

    def get(self, request, *args, **kwargs):
        if not puede_en_programa_dispositivos(request.user, CAP_VER):
            raise PermissionDenied
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ciudadano = get_object_or_404(Ciudadano, pk=self.kwargs["ciudadano_id"])
        context["ciudadano"] = ciudadano
        context.update(trayectoria_de(ciudadano, self.request.GET.get("estadias_page")))
        # El legajo pide `ciudadano.ver`: sin ella el enlace de vuelta rebotaría.
        if rbac.puede(self.request.user, "ciudadano.ver"):
            context["url_legajo"] = reverse("legajos:ciudadano_detalle", args=[ciudadano.pk])
        return context
