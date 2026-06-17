from django import forms

from core.models import Secretaria, Subsecretaria


class SecretariaForm(forms.ModelForm):
    class Meta:
        model = Secretaria
        fields = ['nombre', 'descripcion', 'activo']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
        }


class SubsecretariaForm(forms.ModelForm):
    class Meta:
        model = Subsecretaria
        fields = ['secretaria', 'nombre', 'descripcion', 'activo']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
        }
