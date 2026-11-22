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
from programas.mixins_dispositivos_estadias import contexto_modales_de_estadia, preparar_filas_de_estadias
from programas.models import Dispositivo
from programas.services.dispositivos import CAP_VER
from programas.services.edificio_operativo import (
    contexto_del_edificio,
    edificio_de_la_institucion,
    estadias_del_edificio,
    q_estadias_del_edificio,
)
from programas.services.ingreso import maneja_plazas


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
        # `?cambio=` y `?egreso=` abren su modal en la solapa Estadías, igual que en la ficha de la institución.
        tab = self.request.GET.get("tab", "")
        if not tab and ("cambio" in self.request.GET or "egreso" in self.request.GET):
            tab = "estadias"
        context.update(contexto_del_edificio(user, dispositivo, edificio, tab))
        # El panel se arma solo con la solapa abierta: la página no paga las consultas de las otras.
        if context["tab"] == "estadias":
            context.update(self._estadias_del_edificio(user, dispositivo, edificio))
        return context

    def _estadias_del_edificio(self, user, dispositivo, edificio):
        """Solapa Estadías (Cambio 566): lo HTTP. Los datos y las capacidades los arma ``estadias_del_edificio``.

        Las acciones son las de siempre y vuelven a esta solapa por ``next``. El modal pedido por URL
        (``?cambio=``/``?egreso=``) solo abre estadías de este edificio: otra, sin plaza o de otra institución da 404.
        """

        request = self.request
        get = request.GET
        datos = estadias_del_edificio(
            user, dispositivo, edificio, get.get("estado", ""), get.get("sector", ""), get.get("estadias_page")
        )
        estadias = datos["estadias"]
        mapa_de_ingreso = datos["mapa_de_ingreso"]
        preparar_filas_de_estadias(
            estadias,
            dispositivo=dispositivo,
            url_base=request.path,
            puede_ver_ciudadano=datos["puede_ver_ciudadano"],
            puede_cambiar=datos["puede_cambiar"],
            puede_egresar=datos["puede_egresar"],
            con_plazas=maneja_plazas(dispositivo),
            plazas_elegibles=lambda: mapa_de_ingreso()[1],
        )
        contexto = {
            "estadias": estadias,
            "puede_ver_ciudadano": datos["puede_ver_ciudadano"],
            "pildoras": datos["pildoras"],
            # La píldora es un <form method="get">: sin esto, filtrar perdería la solapa de la URL.
            "ocultos_estadias": [("tab", "estadias")],
            "hay_filtros_estadias": datos["hay_filtros"],
            # Los modales de cambio y de egreso vuelven a esta solapa, no a la ficha de la institución.
            "next_url": f"{request.path}?tab=estadias",
        }
        contexto.update(
            contexto_modales_de_estadia(
                request,
                dispositivo,
                puede_cambiar=datos["puede_cambiar"],
                puede_egresar=datos["puede_egresar"],
                puede_ver_ciudadano=datos["puede_ver_ciudadano"],
                mapa_de_ingreso=lambda: mapa_de_ingreso()[0],
                q_alcance=q_estadias_del_edificio(edificio),
            )
        )
        return contexto
