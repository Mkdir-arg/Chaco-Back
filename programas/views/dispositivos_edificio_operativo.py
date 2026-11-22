"""Página operativa del edificio dentro de una institución (Cambio 563, PR 0 del lote «el edificio como unidad operativa»).

``dispositivos/<pk>/edificios/<edificio_pk>/?tab=<solapa>``. Es **otra pantalla** que la ficha global del módulo
Edificios (``EdificioDetailView``, Cambio 555), que queda como está. Acá la página vive siempre en el contexto de una
institución: ve ``dispositivo.ver`` con alcance sobre la institución y sobre **este** edificio; si no, 404, igual que
un id que no existe.

La vista orquesta; el armado de datos y las capacidades de cada acción están en
``programas.services.edificio_operativo``. Las acciones mantienen sus rutas por institución y reciben ``?edificio=``.
"""

from django.http import Http404
from django.views.generic import TemplateView

from programas.mixins_dispositivos import DispositivoProgramaPermissionMixin, dispositivo_operable_o_404
from programas.models import Dispositivo
from programas.services.dispositivos import CAP_VER
from programas.services.edificio_operativo import contexto_del_edificio, edificio_de_la_institucion


class EdificioOperativoView(DispositivoProgramaPermissionMixin, TemplateView):
    capacidad_requerida = CAP_VER
    template_name = "programas/dispositivos/edificios/operativo.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        dispositivo = dispositivo_operable_o_404(
            self.request, self.kwargs["pk"], CAP_VER, queryset=Dispositivo.objects.select_related("tipo")
        )
        edificio = edificio_de_la_institucion(user, dispositivo, self.kwargs["edificio_pk"])
        if edificio is None:
            raise Http404("Ese edificio no es de esta institución o no está en tu alcance.")
        context.update(contexto_del_edificio(user, dispositivo, edificio, self.request.GET.get("tab", "")))
        return context
