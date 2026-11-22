"""Página operativa del edificio dentro de una institución (Cambio 563, PR 0 del lote «el edificio como unidad operativa»).

``dispositivos/<pk>/edificios/<edificio_pk>/?tab=<solapa>``. Es **otra pantalla** que la ficha global del módulo
Edificios (``EdificioDetailView``, Cambio 555), que queda como está. Acá la página vive siempre en el contexto de una
institución: ve ``dispositivo.ver`` con alcance sobre la institución y sobre **este** edificio; si no, 404, igual que
un id que no existe.

La vista orquesta; el armado de datos y las capacidades de cada acción están en
``programas.services.edificio_operativo``. Las acciones mantienen sus rutas por institución y reciben ``?edificio=``.
"""

from django.db.models import Q
from django.http import Http404
from django.views.generic import TemplateView

from core.rbac import puede
from programas.mixins_dispositivos import DispositivoProgramaPermissionMixin, dispositivo_operable_o_404
from programas.models import Dispositivo, Sector
from programas.services.detalle_dispositivo import estadias_del_dispositivo, normalizar_filtros, pildoras_de_estadias
from programas.services.dispositivos import CAP_VER, puede_operar_edificio
from programas.services.edificio_operativo import contexto_del_edificio, edificio_de_la_institucion
from programas.services.estadias import CAP_ADMITIR, CAP_EGRESAR, CAP_VER_CIUDADANO
from programas.services.ingreso import maneja_plazas, plazas_para_ingresar
from programas.views.dispositivos_legajo import contexto_modales_de_estadia, preparar_filas_de_estadias


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
        """Solapa Estadías (Cambio 566): las personas alojadas **de esta institución en este edificio**.

        La estadía no guarda el edificio: se deriva de su plaza (``plaza__sector__edificio_id``), el mismo criterio del
        contador de la solapa, así que una estadía sin plaza no tiene edificio y no aparece acá (queda en «Personas
        alojadas» de la institución). Las acciones son las de siempre, con el alcance sobre **este** edificio, y vuelven
        a esta solapa por ``next``.
        """

        request = self.request
        get = request.GET
        sectores = list(
            Sector.objects.filter(dispositivo=dispositivo, edificio_id=edificio.pk, activo=True)
            .order_by("nombre")
            .values("pk", "nombre")
        )
        estado, sector = normalizar_filtros(get.get("estado", ""), get.get("sector", ""), {s["pk"] for s in sectores})
        estadias = estadias_del_dispositivo(
            dispositivo,
            estado=estado,
            sector=sector,
            pagina=get.get("estadias_page"),
            q_alcance=Q(plaza__sector__edificio_id=edificio.pk),
        )
        puede_cambiar = puede_operar_edificio(user, dispositivo, edificio.pk, CAP_ADMITIR)
        puede_egresar = puede_operar_edificio(user, dispositivo, edificio.pk, CAP_EGRESAR)
        puede_ver_ciudadano = puede(user, CAP_VER_CIUDADANO)
        mapa = []

        def mapa_de_ingreso():
            if not mapa:
                mapa.append(plazas_para_ingresar(dispositivo, usuario=user))
            return mapa[0]

        preparar_filas_de_estadias(
            estadias,
            dispositivo=dispositivo,
            url_base=request.path,
            puede_ver_ciudadano=puede_ver_ciudadano,
            puede_cambiar=puede_cambiar,
            puede_egresar=puede_egresar,
            con_plazas=maneja_plazas(dispositivo),
            plazas_elegibles=lambda: mapa_de_ingreso()[1],
        )
        contexto = {
            "estadias": estadias,
            "puede_ver_ciudadano": puede_ver_ciudadano,
            "pildoras": pildoras_de_estadias(estado, sector, sectores),
            # La píldora es un <form method="get">: sin esto, filtrar perdería la solapa de la URL.
            "ocultos_estadias": [("tab", "estadias")],
            "hay_filtros_estadias": bool(estado or sector),
            # Los modales de cambio y de egreso vuelven a esta solapa, no a la ficha de la institución.
            "next_url": f"{request.path}?tab=estadias",
        }
        contexto.update(
            contexto_modales_de_estadia(
                request,
                dispositivo,
                puede_cambiar=puede_cambiar,
                puede_egresar=puede_egresar,
                puede_ver_ciudadano=puede_ver_ciudadano,
                mapa_de_ingreso=lambda: mapa_de_ingreso()[0],
            )
        )
        # El modal pedido por URL es de una estadía de ESTE edificio: la de otro, o la que no tiene plaza, da 404.
        abierta = contexto.get("estadia_egreso") or contexto.get("estadia_cambio")
        if abierta is not None and (abierta.plaza_id is None or abierta.plaza.sector.edificio_id != edificio.pk):
            raise Http404("Esa estadía no es de este edificio.")
        return contexto
