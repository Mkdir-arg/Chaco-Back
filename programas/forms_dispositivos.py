"""Formularios de la operación de Dispositivos (MVP v2).

Aparte de `programas/forms.py` a propósito: ese archivo es evidencia del campo canónico
(`INPUT_CLASS`), y un formulario nuevo que solo la consume no mueve esa pieza.
"""

from django import forms
from django.utils import timezone

from core.widgets import SwitchInput
from programas.forms import INPUT_CLASS
from programas.models import MotivoEgreso


class EgresoForm(forms.Form):
    """Egreso de una persona del dispositivo (P9 del mockup · #691).

    La regla de fondo —fecha no futura ni anterior al ingreso, motivo vigente— la sostiene
    `programas.services.estadias.egresar_persona`, que relee la estadía con la fila
    bloqueada. Acá se repite lo que el operador puede corregir sin salir del modal.
    """

    fecha_egreso = forms.DateTimeField(
        label="Fecha y hora",
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"],
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"class": INPUT_CLASS, "type": "datetime-local"}),
        help_text="No puede ser anterior al ingreso.",
    )
    motivo = forms.ModelChoiceField(
        label="Motivo",
        queryset=MotivoEgreso.objects.none(),
        empty_label="Elegí un motivo",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
        error_messages={"required": "Elegí el motivo del egreso."},
    )
    destino = forms.CharField(
        label="Destino",
        max_length=200,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Domicilio de familiar, otro dispositivo…"}),
        error_messages={"required": "Indicá a dónde va la persona."},
    )
    observaciones = forms.CharField(
        label="Observaciones",
        required=False,
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3, "placeholder": "Opcional"}),
    )
    pertenencias_devueltas = forms.BooleanField(
        label="Pertenencias devueltas y firmadas",
        required=False,
        widget=SwitchInput,
    )

    def __init__(self, *args, estadia=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.estadia = estadia
        self.fields["motivo"].queryset = MotivoEgreso.objects.filter(activo=True)
        if not self.is_bound:
            self.fields["fecha_egreso"].initial = timezone.localtime().replace(second=0, microsecond=0)

    def clean_fecha_egreso(self):
        fecha = self.cleaned_data["fecha_egreso"]
        if fecha > timezone.now():
            raise forms.ValidationError("El egreso no puede ser futuro.")
        if self.estadia is not None and fecha < self.estadia.fecha_ingreso:
            raise forms.ValidationError("El egreso no puede ser anterior al ingreso.")
        return fecha
