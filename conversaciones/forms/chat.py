from django import forms

from ..models import Conversacion


class RenaperConsultaForm(forms.Form):
    dni = forms.CharField(max_length=8)
    sexo = forms.CharField(max_length=1)

    def clean_dni(self):
        return self.cleaned_data["dni"].strip()

    def clean_sexo(self):
        return self.cleaned_data["sexo"].strip().upper()


class IniciarConversacionForm(forms.Form):
    tipo = forms.ChoiceField(choices=Conversacion.TIPO_CHOICES, required=False)
    dni = forms.CharField(max_length=8, required=False)
    sexo = forms.CharField(max_length=1, required=False)
    datos_renaper = forms.JSONField(required=False)
    prioridad = forms.ChoiceField(choices=Conversacion.PRIORIDAD_CHOICES, required=False)

    def clean_tipo(self):
        return (self.cleaned_data.get("tipo") or "anonima").strip()

    def clean_dni(self):
        return (self.cleaned_data.get("dni") or "").strip()

    def clean_sexo(self):
        return (self.cleaned_data.get("sexo") or "").strip().upper()

    def clean_prioridad(self):
        return (self.cleaned_data.get("prioridad") or "normal").strip()


class MensajeConversacionForm(forms.Form):
    mensaje = forms.CharField()

    def clean_mensaje(self):
        return self.cleaned_data["mensaje"].strip()


class AsignarConversacionForm(forms.Form):
    operador_id = forms.IntegerField(required=False)


class ConfigurarColaForm(forms.Form):
    operador_id = forms.IntegerField(required=True)
    max_conversaciones = forms.IntegerField(min_value=1, required=False)
    activo = forms.BooleanField(required=False)

    def clean_max_conversaciones(self):
        return self.cleaned_data.get("max_conversaciones") or 5


class EvaluarConversacionForm(forms.Form):
    satisfaccion = forms.IntegerField(min_value=1, max_value=5)
