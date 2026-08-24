"""Formulario del paso 1 de la inscripción pública de Becas (#293)."""

from django import forms

INPUT_CLASS = "nodo-field w-full"


class InscripcionPaso1Form(forms.Form):
    dni = forms.CharField(
        label="Número de documento",
        max_length=12,
        widget=forms.TextInput(
            attrs={"class": INPUT_CLASS, "inputmode": "numeric", "placeholder": "Sin puntos, ej. 30123456"}
        ),
    )
    sexo = forms.ChoiceField(
        label="Sexo (como figura en tu DNI)",
        choices=(("", "Elegí una opción"), ("F", "Femenino"), ("M", "Masculino")),
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    captcha = forms.CharField(
        label="Verificación",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "inputmode": "numeric", "autocomplete": "off"}),
    )

    def clean_dni(self):
        dni = "".join(ch for ch in self.cleaned_data["dni"] if ch.isdigit())
        if len(dni) not in (7, 8):
            raise forms.ValidationError("Ingresá un DNI válido de 7 u 8 dígitos, sin puntos.")
        return dni

    def clean_sexo(self):
        sexo = self.cleaned_data["sexo"]
        if sexo not in ("F", "M"):
            raise forms.ValidationError("Seleccioná una opción.")
        return sexo
