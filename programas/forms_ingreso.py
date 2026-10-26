"""Formularios del asistente de ingreso de Dispositivos (MVP v2, etapa 2 · #690).

Módulo aparte y no `programas/forms.py`: el control de diseño trata ese archivo como
evidencia de la pieza canónica de campos (`INPUT_CLASS`), y estos forms solo la consumen.
"""

from django import forms
from django.utils import timezone

from core.dni import MENSAJE_DNI_INVALIDO, dni_valido, normalizar_dni
from legajos.models import Ciudadano
from programas.forms import INPUT_CLASS


class IngresoPersonaForm(forms.Form):
    """Paso 1 del asistente de ingreso: a quién se aloja (DNI y, si hace falta, sexo)."""

    GENERO_CHOICES = [("", "Seleccionar...")] + [
        ("M", "Masculino"),
        ("F", "Femenino"),
        ("X", "No binario"),
    ]

    dni = forms.CharField(
        label="DNI",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Ej.: 30123456", "inputmode": "numeric"}),
    )
    sexo = forms.ChoiceField(
        label="Sexo",
        required=False,
        choices=GENERO_CHOICES,
        help_text="Solo si la persona no está en el Legajo Ciudadano: el Registro de Personas lo pide.",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )

    def clean_dni(self):
        dni = normalizar_dni(self.cleaned_data.get("dni"))
        if not dni_valido(dni):
            raise forms.ValidationError(MENSAJE_DNI_INVALIDO)
        return dni


class IngresoAltaMinimaForm(forms.Form):
    """Alta mínima de la persona que no está en el legajo ni en el Registro de Personas.

    El DNI se muestra y no se edita: la vista lo toma de la sesión, nunca del POST.
    Los largos son los del modelo `Ciudadano`.
    """

    dni = forms.CharField(
        label="DNI",
        disabled=True,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "inputmode": "numeric"}),
    )
    nombre = forms.CharField(
        label="Nombre",
        max_length=Ciudadano._meta.get_field("nombre").max_length,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    apellido = forms.CharField(
        label="Apellido",
        max_length=Ciudadano._meta.get_field("apellido").max_length,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    fecha_nacimiento = forms.DateField(
        label="Fecha de nacimiento",
        required=False,
        widget=forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}, format="%Y-%m-%d"),
    )
    genero = forms.ChoiceField(
        label="Género",
        required=False,
        choices=[("", "Seleccionar..."), *Ciudadano.Genero.choices],
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )

    def __init__(self, *args, dni, sexo="", **kwargs):
        kwargs["initial"] = {"dni": dni, "genero": sexo}
        super().__init__(*args, **kwargs)

    def clean_fecha_nacimiento(self):
        fecha = self.cleaned_data.get("fecha_nacimiento")
        if fecha and fecha > timezone.localdate():
            raise forms.ValidationError("La fecha de nacimiento no puede ser futura.")
        return fecha


class IngresoConfirmarForm(forms.Form):
    """Paso final del asistente de ingreso: cuándo entró. Vacío es «ahora»."""

    fecha_ingreso = forms.DateTimeField(
        label="Fecha y hora de ingreso",
        required=False,
        help_text="Dejala vacía para registrar el ingreso en este momento. No puede ser futura.",
        widget=forms.DateTimeInput(attrs={"class": INPUT_CLASS, "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M"],
    )
