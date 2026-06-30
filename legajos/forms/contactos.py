from datetime import datetime

from django import forms
from django.core.exceptions import ValidationError

from ..models.contactos import EstadoContacto, HistorialContacto, TipoContacto


class HistorialContactoForm(forms.ModelForm):
    class Meta:
        model = HistorialContacto
        fields = [
            "tipo_contacto",
            "fecha_contacto",
            "duracion_minutos",
            "estado",
            "motivo",
            "resumen",
            "acuerdos",
            "proximos_pasos",
            "participantes",
            "ubicacion",
            "seguimiento_requerido",
            "fecha_proximo_contacto",
            "archivo_adjunto",
        ]
        widgets = {
            "fecha_contacto": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "fecha_proximo_contacto": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "tipo_contacto": forms.Select(attrs={"class": "form-select"}),
            "estado": forms.Select(attrs={"class": "form-select"}),
            "duracion_minutos": forms.NumberInput(attrs={"class": "form-control", "min": "0", "max": "480"}),
            "motivo": forms.TextInput(attrs={"class": "form-control"}),
            "resumen": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "acuerdos": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "proximos_pasos": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "participantes": forms.TextInput(attrs={"class": "form-control"}),
            "ubicacion": forms.TextInput(attrs={"class": "form-control"}),
            "seguimiento_requerido": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "archivo_adjunto": forms.FileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Configurar choices
        self.fields["tipo_contacto"].choices = TipoContacto.choices
        self.fields["estado"].choices = EstadoContacto.choices

        # Labels personalizados
        self.fields["tipo_contacto"].label = "Tipo de Contacto"
        self.fields["fecha_contacto"].label = "Fecha y Hora"
        self.fields["duracion_minutos"].label = "Duración (minutos)"
        self.fields["motivo"].label = "Motivo del Contacto"
        self.fields["resumen"].label = "Resumen de la Conversación"
        self.fields["acuerdos"].label = "Acuerdos Alcanzados"
        self.fields["proximos_pasos"].label = "Próximos Pasos"
        self.fields["participantes"].label = "Otras Personas Presentes"
        self.fields["ubicacion"].label = "Ubicación del Encuentro"
        self.fields["seguimiento_requerido"].label = "Requiere Seguimiento"
        self.fields["fecha_proximo_contacto"].label = "Fecha Próximo Contacto"
        self.fields["archivo_adjunto"].label = "Archivo Adjunto"

        # Help texts
        self.fields["duracion_minutos"].help_text = "Para llamadas y reuniones"
        self.fields["participantes"].help_text = "Para visitas y reuniones"
        self.fields["ubicacion"].help_text = "Para encuentros presenciales"
        self.fields["archivo_adjunto"].help_text = "Grabación, foto o documento"

    def clean_fecha_contacto(self):
        fecha = self.cleaned_data["fecha_contacto"]
        if fecha > datetime.now():
            raise ValidationError("La fecha de contacto no puede ser futura")
        return fecha

    def clean_duracion_minutos(self):
        duracion = self.cleaned_data.get("duracion_minutos")
        tipo = self.cleaned_data.get("tipo_contacto")

        if tipo in ["LLAMADA", "REUNION", "VIDEO"] and not duracion:
            raise ValidationError("La duración es requerida para este tipo de contacto")

        if duracion and duracion > 480:  # 8 horas máximo
            raise ValidationError("La duración no puede exceder 8 horas")

        return duracion
