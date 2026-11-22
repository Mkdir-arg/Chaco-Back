"""Página operativa del edificio dentro de una institución (Cambio 563, PR 0 del lote «el edificio como unidad operativa»).

``dispositivos/<pk>/edificios/<edificio_pk>/?tab=<solapa>``. Es **otra pantalla** que la ficha global del módulo
Edificios (``EdificioDetailView``, Cambio 555), que queda como está. Acá la página vive siempre en el contexto de una
institución: ve ``dispositivo.ver`` con alcance sobre la institución y sobre **este** edificio; si no, 404, igual que
un id que no existe.

La vista orquesta; el armado de datos y las capacidades de cada acción están en
``programas.services.edificio_operativo``. Las acciones mantienen sus rutas por institución y reciben ``?edificio=``.

La solapa «Sectores y plazas» (Cambio 565) es el cuerpo de la pantalla de sectores con el edificio fijo
(``SectoresPlazasMixin.edificio_fijo``): se arma solo con la solapa abierta y sus acciones vuelven a ella.
"""

from django.http import Http404
from django.urls import reverse
from django.views.generic import DetailView

from programas.mixins_dispositivos import DispositivoObjectPermissionMixin
from programas.mixins_dispositivos_sectores import SectoresPlazasMixin
from programas.models import Dispositivo
from programas.services.dispositivos import CAP_VER
from programas.services.edificio_operativo import contexto_del_edificio, edificio_de_la_institucion
from programas.services.edificio_operativo_edilicio import contexto_edilicio


class EdificioOperativoView(SectoresPlazasMixin, DispositivoObjectPermissionMixin, DetailView):
    capacidad_requerida = CAP_VER
    model = Dispositivo
    template_name = "programas/dispositivos/edificios/operativo.html"
    context_object_name = "dispositivo"
    # Las celdas, los enlaces y los modales del mapa conservan la solapa (`?tab=sectores&plaza=…`).
    en_solapa = True
    param_editar_sector = "editar_sector"

    def get_queryset(self):
        return Dispositivo.objects.select_related("tipo")

    def get_object(self, queryset=None):
        """La institución y, con ella, el edificio: ajeno, desvinculado o fuera de alcance es 404 (también el fragmento)."""

        dispositivo = super().get_object(queryset)
        edificio = edificio_de_la_institucion(self.request.user, dispositivo, self.kwargs["edificio_pk"])
        if edificio is None:
            raise Http404("Ese edificio no es de esta institución o no está en tu alcance.")
        self.edificio_fijo = edificio
        return dispositivo

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dispositivo = self.object
        context.update(
            contexto_del_edificio(self.request.user, dispositivo, self.edificio_fijo, self.request.GET.get("tab", ""))
        )
        if context["sectores_cargados"]:
            self._preparar_sectores_y_plazas(context, dispositivo)
        # Estado edilicio (Cambio 567): se arma solo con la solapa abierta; con otra, su botón navega a `?tab=edilicio`.
        # La tabla de relevamientos, o el detalle de uno; uno ajeno o que no ve es 404.
        edificio = self.edificio_fijo
        url_pagina = reverse("dispositivos:edificio_operativo", args=[dispositivo.pk, edificio.pk])
        context["url_solapa_edilicio"] = f"{url_pagina}?tab=edilicio"
        context["edilicio_cargado"] = context["tab"] == "edilicio"
        if context["edilicio_cargado"]:
            edilicio = contexto_edilicio(self.request.user, dispositivo, edificio, self.request.GET, url_pagina)
            if edilicio is None:
                raise Http404("Ese relevamiento no es de este edificio o no está en tu alcance.")
            context.update(edilicio)
        return context
