"""Configuración de la mesa de Emergencia (Cambio 578): «Insumos» y «Plazos de atención».

La pantalla única de configuración se partió en dos entradas del menú. La vista solo orquesta: los
formularios validan la entrada y `programas/services/configuracion_emergencia.py` guarda,
vuelve a exigir la capacidad y deja la traza. Las dos exigen `emergencia.supervisar`, como
la pantalla que reemplazan.
"""

from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from programas.forms_emergencia import InsumoForm, SLAEmergenciaForm
from programas.mixins_emergencia import EmergenciaPermissionMixin
from programas.models import TipoKit
from programas.selectors.emergencia_insumos import (
    ESTADOS,
    conteos_de_insumos,
    estado_valido,
    insumos_del_catalogo,
)
from programas.services.configuracion_emergencia import (
    cambiar_estado_tipo_kit,
    crear_tipo_kit,
    editar_tipo_kit,
    guardar_sla,
    insumo_usado_en_entregas,
    sla_vigente,
)
from programas.services.emergencia_programa import CAP_SUPERVISAR
from programas.services.pantalla_abastecimiento_emergencia import texto_de_consumo

TEMPLATE_INSUMOS = "programas/emergencia/insumos.html"
TEMPLATE_PLAZOS = "programas/emergencia/plazos.html"
INSUMOS_POR_PAGINA = 25


class PlazosEmergenciaView(EmergenciaPermissionMixin, View):
    """«Plazos de atención»: el SLA de la mesa y el nombre y el inicio del evento."""

    capacidad_requerida = CAP_SUPERVISAR

    def _render(self, request, form, status=200):
        return render(request, TEMPLATE_PLAZOS, {"form": form}, status=status)

    def get(self, request):
        return self._render(request, SLAEmergenciaForm(instance=sla_vigente()))

    def post(self, request):
        form = SLAEmergenciaForm(request.POST, instance=sla_vigente())
        if not form.is_valid():
            return self._render(request, form, status=400)
        try:
            guardar_sla(request.user, **form.campos_para_guardar())
        except ValidationError as error:
            # Lo que el servicio rechaza y el formulario dejó pasar: se muestra, sin guardar nada.
            form.add_error(None, error)
            return self._render(request, form, status=400)
        messages.success(request, "Plazos de atención guardados.")
        return redirect("emergencia:plazos")


def _url_insumos(estado, **parametros):
    """La lista en el chip ``estado``, con ``parametros`` extra (``nuevo``, ``editar``)."""
    consulta = {"estado": estado, **parametros}
    return f"{reverse('emergencia:insumos')}?{urlencode(consulta)}"


def _url_accion(nombre, pk, estado):
    """La URL de activar o desactivar un insumo, con el chip al que se vuelve."""
    return f"{reverse(nombre, args=[pk])}?{urlencode({'estado': estado})}"


class InsumosEmergenciaView(EmergenciaPermissionMixin, View):
    """«Insumos»: el catálogo de lo que la mesa puede enviar, con su alta y edición en un modal.

    El modal lo arma el servidor: ``?nuevo=1`` abre el alta y ``?editar=<id>`` la edición de ese
    insumo (la regla 1 —un insumo ya usado no cambia de nombre ni de unidad— decide qué campos
    quedan de solo lectura). Un guardado con errores vuelve con el modal abierto.
    """

    capacidad_requerida = CAP_SUPERVISAR

    def _contexto(self, request, estado, form=None, editando=None):
        conteos = conteos_de_insumos()
        pagina = Paginator(insumos_del_catalogo(estado), INSUMOS_POR_PAGINA).get_page(request.GET.get("page"))
        for insumo in pagina.object_list:
            insumo.consumo = texto_de_consumo(insumo)
            insumo.url_editar = _url_insumos(estado, editar=insumo.pk)
            insumo.url_desactivar = _url_accion("emergencia:insumo_desactivar", insumo.pk, estado)
            insumo.url_activar = _url_accion("emergencia:insumo_activar", insumo.pk, estado)
        chips = [
            {"texto": rotulo, "url": _url_insumos(clave), "activo": clave == estado, "n": conteos[clave]}
            for clave, rotulo in ESTADOS
        ]
        return {
            "page_obj": pagina,
            "insumos": pagina.object_list,
            "chips": chips,
            "estado": estado,
            "hay_insumos": conteos["todos"] > 0,
            "form": form,
            "abre_modal": form is not None,
            "editando": editando,
            "url_nuevo": _url_insumos(estado, nuevo=1),
            "url_lista": _url_insumos(estado),
        }

    def _form_de(self, tipo, data=None):
        if tipo is None:
            return InsumoForm(data)
        return InsumoForm(data, instance=tipo, en_uso=insumo_usado_en_entregas(tipo))

    def get(self, request):
        estado = estado_valido(request.GET.get("estado"))
        editando = (
            TipoKit.objects.filter(pk=request.GET["editar"]).first() if _es_id(request.GET.get("editar")) else None
        )
        form = None
        if editando is not None:
            form = self._form_de(editando)
        elif request.GET.get("nuevo"):
            form = self._form_de(None)
        return render(request, TEMPLATE_INSUMOS, self._contexto(request, estado, form, editando))

    def post(self, request):
        estado = estado_valido(request.POST.get("estado"))
        editando = None
        if request.POST.get("insumo"):
            if not _es_id(request.POST["insumo"]):
                raise Http404
            editando = TipoKit.objects.filter(pk=request.POST["insumo"]).first()
            if editando is None:
                raise Http404
        form = self._form_de(editando, request.POST)
        if form.is_valid():
            try:
                if editando is None:
                    insumo = crear_tipo_kit(request.user, **form.campos_para_guardar())
                else:
                    insumo = editar_tipo_kit(request.user, editando, **form.campos_para_guardar())
            except ValidationError as error:
                # Lo que el servicio rechaza y el formulario dejó pasar (otro supervisor cargó el
                # mismo nombre, o el insumo se usó entre el GET y el POST): se muestra, sin guardar.
                form.add_error(None, error)
            else:
                messages.success(request, f"Insumo «{insumo.nombre}» guardado.")
                if request.POST.get("continuar"):
                    return redirect(_url_insumos(estado, nuevo=1))
                return redirect(_url_insumos(estado))
        return render(request, TEMPLATE_INSUMOS, self._contexto(request, estado, form, editando), status=400)


def _es_id(valor):
    return bool(valor) and str(valor).isdigit() and len(str(valor)) < 10


class CambiarEstadoInsumoView(EmergenciaPermissionMixin, View):
    """Activa o desactiva un insumo (RN-4.7: no se borra). La confirmación es del botón de la lista."""

    capacidad_requerida = CAP_SUPERVISAR
    activo = True
    http_method_names = ["post"]

    def post(self, request, pk):
        insumo = TipoKit.objects.filter(pk=pk).first()
        if insumo is None:
            raise Http404
        cambiar_estado_tipo_kit(request.user, insumo, self.activo)
        if self.activo:
            messages.success(request, f"«{insumo.nombre}» se volvió a ofrecer en las entregas nuevas.")
        else:
            messages.success(request, f"«{insumo.nombre}» se desactivó: no se ofrece en las entregas nuevas.")
        return redirect(_url_insumos(estado_valido(request.GET.get("estado"))))
