"""Formularios de Emergencia.

Aparte de `programas/forms.py` a propósito (igual que `forms_dispositivos.py`): ese archivo
es evidencia del campo canónico (`INPUT_CLASS`), y un formulario nuevo que solo la consume
no mueve esa pieza.

E7 · Configuración: un ModelForm del SLA y un formset del catálogo de kits **sin borrado**
(RN-4.7). Los dos validan la entrada; lo que se guarda y la traza son del servicio
(`programas/services/configuracion_emergencia.py`).
"""

from django import forms

from core.widgets import SwitchInput
from programas.forms import INPUT_CLASS
from programas.models import SLAEmergencia, TipoKit
from programas.services.configuracion_emergencia import (
    CAMPOS_SLA,
    CAMPOS_TIPO_KIT,
    MENSAJE_NOMBRE_DUPLICADO,
    nombre_de_kit_en_uso,
    normalizar_nombre,
)

PREFIJO_KITS = "kits"
#: Tope de filas que un POST armado a mano puede pedir que se instancien.
MAXIMO_KITS = 200


def _minutos(minimo):
    return forms.NumberInput(attrs={"class": INPUT_CLASS, "min": minimo, "inputmode": "numeric"})


class SLAEmergenciaForm(forms.ModelForm):
    """Los ocho parámetros de la mesa. Los rangos son los validadores del modelo."""

    class Meta:
        model = SLAEmergencia
        fields = list(CAMPOS_SLA)
        widgets = {
            "nombre_evento": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "objetivo_tomar_min": _minutos(1),
            "objetivo_derivar_min": _minutos(1),
            "objetivo_aceptar_min": _minutos(1),
            "objetivo_alojar_min": _minutos(1),
            "vigencia_derivacion_min": _minutos(SLAEmergencia.VIGENCIA_MINIMA_MIN),
            "sin_avance_min": _minutos(0),
            "umbral_por_vencer_pct": forms.NumberInput(
                attrs={
                    "class": INPUT_CLASS,
                    "min": SLAEmergencia.UMBRAL_MINIMO_PCT,
                    "max": SLAEmergencia.UMBRAL_MAXIMO_PCT,
                    "inputmode": "numeric",
                }
            ),
        }

    def campos_del_evento(self):
        return [self["nombre_evento"]]

    def campos_de_objetivos(self):
        return [self[campo] for campo in CAMPOS_SLA if campo.startswith("objetivo_")]

    def campos_de_derivacion(self):
        return [self["vigencia_derivacion_min"], self["sin_avance_min"], self["umbral_por_vencer_pct"]]

    def campos_para_guardar(self):
        """Lo que recibe ``guardar_sla``: los campos del SLA ya validados."""
        return {campo: self.cleaned_data[campo] for campo in CAMPOS_SLA}


class TipoKitForm(forms.ModelForm):
    """Una fila del catálogo. La fila vacía del final es la de «agregar ítem»."""

    class Meta:
        model = TipoKit
        fields = list(CAMPOS_TIPO_KIT)
        widgets = {
            "nombre": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "unidad": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "kit, unidad, bidón…"}),
            "orden": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 0, "inputmode": "numeric"}),
            "activo": SwitchInput(),
        }

    def clean_nombre(self):
        nombre = normalizar_nombre(self.cleaned_data.get("nombre"))
        if nombre and nombre_de_kit_en_uso(nombre, excluir_pk=self.instance.pk):
            raise forms.ValidationError(MENSAJE_NOMBRE_DUPLICADO)
        return nombre

    def validate_unique(self):
        """El duplicado ya lo dijo ``clean_nombre``, sin distinguir mayúsculas: no se repite el error."""

    @property
    def es_nuevo(self):
        return self.instance.pk is None

    def campos_para_guardar(self):
        """Lo que recibe el servicio: los campos del ítem ya validados."""
        return {campo: self.cleaned_data[campo] for campo in CAMPOS_TIPO_KIT}


class _IdDeFila(forms.ModelChoiceField):
    """El ``id`` oculto de cada fila, resuelto contra el catálogo que el formset ya leyó.

    El campo de fábrica hace un ``queryset.get(pk=…)`` **por fila** al validar: con veinte
    ítems son veinte consultas para confirmar lo que el formset trajo en una.
    """

    def __init__(self, *args, buscar, **kwargs):
        super().__init__(*args, **kwargs)
        self._buscar = buscar

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            objeto = self._buscar(value)
        except (TypeError, ValueError, forms.ValidationError):
            objeto = None
        if objeto is None:
            raise forms.ValidationError(self.error_messages["invalid_choice"], code="invalid_choice")
        return objeto


class BaseTipoKitFormSet(forms.BaseModelFormSet):
    """Catálogo de kits: se edita y se agrega, **no se borra** (``can_delete=False``)."""

    def add_fields(self, form, index):
        super().add_fields(form, index)
        de_fabrica = form.fields[self._pk_field.name]
        form.fields[self._pk_field.name] = _IdDeFila(
            de_fabrica.queryset,
            buscar=self._fila_por_id,
            initial=de_fabrica.initial,
            required=False,
            widget=forms.HiddenInput,
        )

    def _fila_por_id(self, valor):
        """El ítem con ese id entre los que el formset ya trajo (el POST lo manda como texto)."""
        return self._existing_object(self.model._meta.pk.to_python(valor))

    def clean(self):
        super().clean()
        vistos = set()
        for form in self.forms:
            if form.errors or not form.has_changed() and form.es_nuevo:
                continue
            nombre = (form.cleaned_data.get("nombre") or "").casefold()
            if not nombre:
                continue
            if nombre in vistos:
                form.add_error("nombre", MENSAJE_NOMBRE_DUPLICADO)
            vistos.add(nombre)

    def validate_unique(self):
        """Los repetidos entre filas los marca ``clean`` en su fila, no como error del conjunto."""

    def filas_existentes(self):
        return [form for form in self.forms if not form.es_nuevo]

    def filas_nuevas(self):
        return [form for form in self.forms if form.es_nuevo]

    def cambios_para_guardar(self):
        """``[(tipo, campos)]`` para ``guardar_configuracion``: solo las filas que cambiaron.

        Una fila nueva sin tocar no es un ítem: es el lugar para agregar uno.
        """
        return [
            (None if form.es_nuevo else form.instance, form.campos_para_guardar())
            for form in self.forms
            if form.has_changed()
        ]


TipoKitFormSet = forms.modelformset_factory(
    TipoKit,
    form=TipoKitForm,
    formset=BaseTipoKitFormSet,
    extra=1,
    can_delete=False,
    max_num=MAXIMO_KITS,
    absolute_max=MAXIMO_KITS,
)
