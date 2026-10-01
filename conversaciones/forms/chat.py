from django import forms

# `RenaperConsultaForm` e `IniciarConversacionForm` se eliminaron con las rutas
# públicas del chat: el segundo traía `datos_renaper = forms.JSONField()`, el
# nombre y apellido que el cliente anónimo quisiera para el legajo (G1-01 y
# G1-02, auditoría oct-2026).


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
