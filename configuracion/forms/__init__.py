"""Forms para la app de configuracion."""

from django import forms

from core.models import Localidad, Municipio, Provincia

from .programas import ProgramaPaso1Form, ProgramaPaso2Form, ProgramaPaso3Form, ProgramaPaso4Form  # noqa: F401
from .secretaria import SecretariaForm, SubsecretariaForm  # noqa: F401

_FIELD_CLASS = "nodo-field"


class ProvinciaForm(forms.ModelForm):
    class Meta:
        model = Provincia
        fields = ["nombre"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": _FIELD_CLASS, "placeholder": "Ej: Chaco"}),
        }


class MunicipioForm(forms.ModelForm):
    class Meta:
        model = Municipio
        fields = ["provincia", "nombre"]
        widgets = {
            "provincia": forms.Select(attrs={"class": _FIELD_CLASS}),
            "nombre": forms.TextInput(attrs={"class": _FIELD_CLASS, "placeholder": "Ej: Resistencia"}),
        }


class LocalidadForm(forms.ModelForm):
    class Meta:
        model = Localidad
        fields = ["municipio", "nombre"]
        widgets = {
            "municipio": forms.Select(attrs={"class": _FIELD_CLASS}),
            "nombre": forms.TextInput(attrs={"class": _FIELD_CLASS, "placeholder": "Ej: Barranqueras"}),
        }
