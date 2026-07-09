from django import forms

from core.models import Secretaria, Subsecretaria

_FIELD_CLASS = "nodo-field"


class SecretariaForm(forms.ModelForm):
    class Meta:
        model = Secretaria
        fields = ["nombre", "descripcion", "activo"]
        widgets = {
            "nombre": forms.TextInput(
                attrs={"class": _FIELD_CLASS, "placeholder": "Ej: Secretaría de Desarrollo Social"}
            ),
            "descripcion": forms.Textarea(
                attrs={"class": _FIELD_CLASS, "rows": 3, "placeholder": "Descripción opcional"}
            ),
        }


class SubsecretariaForm(forms.ModelForm):
    class Meta:
        model = Subsecretaria
        fields = ["secretaria", "nombre", "descripcion", "activo"]
        widgets = {
            "secretaria": forms.Select(attrs={"class": _FIELD_CLASS}),
            "nombre": forms.TextInput(attrs={"class": _FIELD_CLASS, "placeholder": "Ej: Subsecretaría de Niñez"}),
            "descripcion": forms.Textarea(
                attrs={"class": _FIELD_CLASS, "rows": 3, "placeholder": "Descripción opcional"}
            ),
        }
