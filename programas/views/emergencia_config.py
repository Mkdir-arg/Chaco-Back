"""E7 · Configuración de la mesa de Emergencia: SLA y catálogo de kits.

La vista solo orquesta: los formularios validan la entrada y
`programas/services/configuracion_emergencia.py` guarda, vuelve a exigir la capacidad y
deja la traza.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views import View

from programas.forms_emergencia import PREFIJO_KITS, SLAEmergenciaForm, TipoKitFormSet
from programas.mixins_emergencia import EmergenciaPermissionMixin
from programas.services.configuracion_emergencia import catalogo_kits, guardar_configuracion, sla_vigente
from programas.services.emergencia_programa import CAP_SUPERVISAR

TEMPLATE = "programas/emergencia/configuracion.html"


class ConfiguracionEmergenciaView(EmergenciaPermissionMixin, View):
    capacidad_requerida = CAP_SUPERVISAR

    def _formularios(self, data=None):
        return (
            SLAEmergenciaForm(data, instance=sla_vigente()),
            TipoKitFormSet(data, queryset=catalogo_kits(), prefix=PREFIJO_KITS),
        )

    def _render(self, request, form, kits, status=200):
        return render(request, TEMPLATE, {"form": form, "kits": kits}, status=status)

    def get(self, request):
        return self._render(request, *self._formularios())

    def post(self, request):
        form, kits = self._formularios(request.POST)
        sla_valido, kits_validos = form.is_valid(), kits.is_valid()
        if not (sla_valido and kits_validos):
            # Un error del conjunto de kits (el formset llegó incompleto) no es de ningún
            # campo: se muestra arriba, en el bloque de errores del formulario.
            for error in kits.non_form_errors():
                form.add_error(None, error)
            return self._render(request, form, kits, status=400)
        try:
            guardar_configuracion(request.user, sla=form.campos_para_guardar(), kits=kits.cambios_para_guardar())
        except ValidationError as error:
            # Lo que el servicio rechaza y los formularios dejaron pasar (otro supervisor
            # cargó el mismo ítem entre el GET y el POST): se muestra arriba, sin guardar nada.
            form.add_error(None, error)
            return self._render(request, form, kits, status=400)
        messages.success(request, "Configuración de Emergencia guardada.")
        return redirect("emergencia:configuracion")
