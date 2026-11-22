"""Sección «Edificios» de Dispositivos (análisis #1164): el listado (#1167) y la ficha del edificio (#1168).

Solo lectura, salvo el enlace «Editar edificio» de la ficha (Cambio 555). La vista orquesta: qué edificios ve cada uno, los filtros y lo que dibuja cada fila
salen de `programas.selectors.edificios`. La acción de la fila, «Crear relevamiento», abre el modal
de asignar de Relevamientos (P21) y no tiene ruta propia.
"""

from django.shortcuts import get_object_or_404
from django.views.generic import ListView, TemplateView

from programas.mixins_dispositivos import DispositivoProgramaPermissionMixin
from programas.selectors.edificios import (
    COMPARTIDO_NO,
    COMPARTIDO_SI,
    SITUACION_TODOS,
    SITUACIONES,
    edificios_visibles,
    ficha_de_edificio,
    filas_del_listado,
    filtrar_edificios,
    localidades_visibles,
    para_el_listado,
    ve_situaciones,
)
from programas.services.detalle_dispositivo import ESTADOS_EDILICIOS
from programas.services.dispositivos import CAP_VER_EDIFICIOS

FILTROS = ("q", "localidad", "estado", "compartido", "situacion")


class EdificioListView(DispositivoProgramaPermissionMixin, ListView):
    """Listado paginado de edificios con filtros (RF1, RF2 del análisis #1164)."""

    capacidad_requerida = CAP_VER_EDIFICIOS
    template_name = "programas/dispositivos/edificios/list.html"
    paginate_by = 25
    context_object_name = "edificios"

    def _filtros(self):
        params = self.request.GET
        filtros = {nombre: (params.get(nombre) or "").strip() for nombre in FILTROS}
        if not ve_situaciones(self.request.user):
            filtros["situacion"] = ""
        return filtros

    def get_queryset(self):
        filtros = self._filtros()
        visibles = edificios_visibles(self.request.user, situacion=filtros["situacion"])
        return para_el_listado(
            filtrar_edificios(
                visibles,
                q=filtros["q"],
                localidad=filtros["localidad"],
                estado=filtros["estado"],
                compartido=filtros["compartido"],
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        filtros = self._filtros()
        situaciones = ve_situaciones(user)
        hay_filtros = any(filtros.values())
        filas = filas_del_listado(user, context["page_obj"].object_list)
        context.update(
            {
                "filas": filas,
                "filtros": filtros,
                "hay_filtros": hay_filtros,
                # Sin filtros y sin filas, para quien no es admin: no alcanza ningún edificio vigente.
                "vacio_por_alcance": not filas and not hay_filtros and not situaciones,
                "localidades": localidades_visibles(user, situacion=filtros["situacion"]),
                "estados": [(clave, texto) for clave, texto, _criticidad in ESTADOS_EDILICIOS],
                "opciones_compartido": [(COMPARTIDO_SI, "Compartido"), (COMPARTIDO_NO, "Una sola institución")],
                "ve_situaciones": situaciones,
                "situaciones": SITUACIONES if situaciones else (),
            }
        )
        return context


class EdificioDetailView(DispositivoProgramaPermissionMixin, TemplateView):
    """Ficha propia del edificio (RF3 del análisis #1164), en solo lectura; «Editar edificio» es un enlace al modal de Infraestructura.

    Se busca entre **todos** los que el usuario ve: para quien no es admin, `edificios_visibles` ignora la
    situación y deja solo los vigentes, así que un edificio fuera de alcance, huérfano o inactivo da 404
    (Cambio 432), igual que un id que no existe. El admin abre también los huérfanos y los inactivos.
    """

    capacidad_requerida = CAP_VER_EDIFICIOS
    template_name = "programas/dispositivos/edificios/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        edificio = get_object_or_404(
            para_el_listado(edificios_visibles(user, situacion=SITUACION_TODOS)), pk=self.kwargs["pk"]
        )
        context["ficha"] = ficha_de_edificio(user, edificio, pagina=self.request.GET.get("page") or 1)
        return context
