"""Filtros validados para los reportes transversales de Becas."""

from django import forms
from django.contrib.auth.models import User

from programas.models import Convocatoria, Segmento
from programas.services.autorizacion import (
    convocatorias_visibles,
    segmentos_visibles,
    usuarios_territoriales_becas,
)


class ReporteBecasFiltroForm(forms.Form):
    segmento = forms.ModelChoiceField(queryset=Segmento.objects.none(), required=False)
    convocatoria = forms.ModelChoiceField(queryset=Convocatoria.objects.none(), required=False)
    territorial = forms.ModelChoiceField(queryset=User.objects.none(), required=False)
    desde = forms.DateField(required=False, input_formats=["%Y-%m-%d"])
    hasta = forms.DateField(required=False, input_formats=["%Y-%m-%d"])
    estado = forms.ChoiceField(
        required=False, choices=(("", "Todas"), ("activas", "Activas"), ("cerradas", "Cerradas"))
    )
    solo_activos = forms.BooleanField(required=False)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        convocatorias = convocatorias_visibles(user)
        self.fields["segmento"].queryset = segmentos_visibles(user)
        self.fields["convocatoria"].queryset = convocatorias
        self.fields["territorial"].queryset = (
            usuarios_territoriales_becas().filter(relevamientos_asignados__convocatoria__in=convocatorias).distinct()
        )

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get("desde"), datos.get("hasta")
        if desde and hasta and desde > hasta:
            raise forms.ValidationError("La fecha desde no puede ser posterior a la fecha hasta.")
        return datos

    def parametros(self, codigo):
        datos = self.cleaned_data
        comunes = {"desde": datos.get("desde"), "hasta": datos.get("hasta")}
        if codigo == "cupos":
            return {
                "segmento_id": getattr(datos.get("segmento"), "pk", None),
                "solo_activos": datos.get("solo_activos", False),
            }
        if codigo == "avance":
            return {
                **comunes,
                "segmento_id": getattr(datos.get("segmento"), "pk", None),
                "estado": datos.get("estado") or None,
            }
        if codigo == "produccion":
            return {
                **comunes,
                "segmento_id": getattr(datos.get("segmento"), "pk", None),
                "territorial_id": getattr(datos.get("territorial"), "pk", None),
            }
        if codigo == "embudo":
            return {**comunes, "convocatoria_id": getattr(datos.get("convocatoria"), "pk", None)}
        return {
            **comunes,
            "segmento_id": getattr(datos.get("segmento"), "pk", None),
            "convocatoria_id": getattr(datos.get("convocatoria"), "pk", None),
        }
