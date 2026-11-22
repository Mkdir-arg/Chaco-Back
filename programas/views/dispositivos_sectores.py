"""La pantalla «Sectores y plazas» de siempre (`/dispositivos/<id>/sectores/`)."""

from django.urls import reverse
from django.views.generic import DetailView

from programas.mixins_dispositivos import DispositivoObjectPermissionMixin
from programas.mixins_dispositivos_sectores import SectoresPlazasMixin
from programas.models import (
    Dispositivo,
)


class DispositivoSectoresView(SectoresPlazasMixin, DispositivoObjectPermissionMixin, DetailView):
    """La pantalla «Sectores y plazas» de siempre: sigue respondiendo (enlaces guardados, la app, los tests).

    Dibuja el mismo cuerpo que la solapa de la ficha. Los enlaces de adentro ya no llevan acá:
    las acciones vuelven a la solapa (`url_solapa_sectores`).
    """

    capacidad_requerida = "dispositivo.ver"
    model = Dispositivo
    template_name = "programas/dispositivos/sectores/sectores.html"
    context_object_name = "dispositivo"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dispositivo = self.object
        self._preparar_sectores_y_plazas(context, dispositivo)
        # Con el nombre de siempre para esta pantalla (no hay otro `sectores` que lo pise).
        context["sectores"] = context["sectores_mapa"]
        context["migas"] = [
            {"label": "Instituciones", "url": reverse("dispositivos:lista")},
            {"label": dispositivo.nombre, "url": reverse("dispositivos:detalle", args=[dispositivo.pk])},
            {"label": "Sectores y plazas", "url": ""},
        ]
        return context
