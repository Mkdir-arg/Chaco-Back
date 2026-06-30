"""Forms para la app de configuracion."""

from django import forms

from core.models import Localidad, Municipio, Provincia

from .programas import ProgramaPaso1Form, ProgramaPaso2Form, ProgramaPaso3Form, ProgramaPaso4Form  # noqa: F401
from .secretaria import SecretariaForm, SubsecretariaForm  # noqa: F401


class ProvinciaForm(forms.ModelForm):
    class Meta:
        model = Provincia
        fields = ["nombre"]


class MunicipioForm(forms.ModelForm):
    class Meta:
        model = Municipio
        fields = ["provincia", "nombre"]


class LocalidadForm(forms.ModelForm):
    class Meta:
        model = Localidad
        fields = ["municipio", "nombre"]
