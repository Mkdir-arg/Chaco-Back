from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.views.generic import TemplateView


class CiudadanoDispositivosView(LoginRequiredMixin, TemplateView):
    """Solapa de Dispositivos del legajo ciudadano: sin contenido hasta la E2.

    Listaba las admisiones del ciudadano con su cama y su fecha de ingreso, y esa
    lectura se fue con `Admision`. La reescribe la task 28 del MVP contra `Estadia`,
    que es la que vuelve a dar historial —y esta vez el completo, incluidas las
    estadías cerradas—.

    Mientras tanto responde 404. No es que falte terminarla: es que **no se llega**.
    `SolapasService` dejó de ofrecer la solapa para las inscripciones de Dispositivos,
    así que no hay link que la abra y el único acceso sería escribir la URL a mano.
    Dejarla renderizando con las guardas que quedaban —capacidad sobre el programa más
    inscripción vigente— habría aflojado el alcance: cualquiera con `dispositivo.ver`
    podía leer el nombre de un ciudadano probando identificadores, sin acotarse a los
    dispositivos que tiene asignados. La guarda vieja exigía además una admisión
    alojada **en un dispositivo visible para el usuario**, y esa parte no tiene cómo
    sostenerse sin `Admision`.
    """

    template_name = "legajos/solapas/dispositivos.html"

    def get(self, request, *args, **kwargs):
        raise Http404("La solapa de Dispositivos se repone en la task 28 del MVP.")
