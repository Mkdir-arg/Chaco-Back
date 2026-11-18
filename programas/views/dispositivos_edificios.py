"""Sección «Edificios» de Dispositivos (análisis #1164): el listado de los edificios del alcance (#1167).

Solo lectura. La vista orquesta: qué edificios ve cada uno, los filtros y lo que dibuja cada fila
salen de `programas.selectors.edificios`. La acción de la fila, «Crear relevamiento», abre el modal
de asignar de Relevamientos (P21) y no tiene ruta propia.
"""

from django.views.generic import ListView

from programas.mixins_dispositivos import DispositivoProgramaPermissionMixin
from programas.selectors.edificios import (
    COMPARTIDO_NO,
    COMPARTIDO_SI,
    SITUACIONES,
    edificios_visibles,
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
