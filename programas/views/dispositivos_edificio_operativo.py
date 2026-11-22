"""Página operativa del edificio dentro de una institución (Cambio 563, PR 0 del lote «el edificio como unidad operativa»).

``dispositivos/<pk>/edificios/<edificio_pk>/?tab=<solapa>``. Es **otra pantalla** que la ficha global del módulo
Edificios (``EdificioDetailView``, Cambio 555), que queda como está. Acá la página vive siempre en el contexto de una
institución: ve ``dispositivo.ver`` con alcance sobre la institución y sobre **este** edificio; si no, 404, igual que
un id que no existe.

La vista orquesta; el armado de datos y las capacidades de cada acción están en
``programas.services.edificio_operativo``. Las acciones mantienen sus rutas por institución y reciben ``?edificio=``.
"""

from django.contrib import messages
from django.http import Http404
from django.views.generic import TemplateView

from programas.mixins_dispositivos import DispositivoProgramaPermissionMixin, _entero, dispositivo_operable_o_404
from programas.mixins_dispositivos_equipo import contexto_modal_alcance, contexto_modal_sumar_persona
from programas.models import Dispositivo
from programas.services.dispositivos import CAP_VER
from programas.services.edificio_operativo import contexto_del_edificio, edificio_de_la_institucion


def modales_del_equipo(request, dispositivo, edificio, contexto):
    """Abre «Agregar persona al edificio» o «Cambiar alcance» si la URL lo pide (``?equipo=sumar|alcance``).

    Igual que en la ficha de la institución: los formularios (con sus consultas) se arman solo con un modal abierto.
    Se ofrece solo lo que el servidor va a aceptar; si no, un aviso y la página de siempre. El edificio del alta es
    **este**, siempre: no viaja por la URL.
    """

    pedido = request.GET.get("equipo")
    if not contexto["equipo_cargado"] or pedido not in ("sumar", "alcance"):
        return
    permisos = contexto["permisos_equipo"]
    if not permisos.gestiona:
        return
    if pedido == "sumar":
        if contexto["puede_sumar_persona"]:
            contexto.update(contexto_modal_sumar_persona(dispositivo, request.user, edificio, permisos))
        else:
            messages.warning(request, "No se pueden agregar personas a este edificio.")
        return
    pk = _entero(request.GET.get("miembro"))
    miembro = next((m for m in contexto["equipo"] if m.pk == pk), None)
    if miembro is None or not miembro.puede_cambiar_alcance:
        messages.warning(request, "No se puede cambiar el alcance de esa persona.")
        return
    contexto.update(contexto_modal_alcance(dispositivo, request.user, miembro, permisos))


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
        modales_del_equipo(self.request, dispositivo, edificio, context)
        # La fila que el alta acaba de dejar (`?nuevo=<id>`) sale resaltada.
        context["miembro_nuevo"] = _entero(self.request.GET.get("nuevo"))
        return context
