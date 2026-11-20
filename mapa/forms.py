from django import forms

from mapa.models import Punto


class PuntoForm(forms.ModelForm):
    """Alta de un punto: nombre, categoría y descripción en el modal; la posición sale del clic en el mapa."""

    class Meta:
        model = Punto
        fields = ["nombre", "categoria", "descripcion", "latitud", "longitud"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "nodo-field", "maxlength": 120, "autocomplete": "off"}),
            "categoria": forms.Select(attrs={"class": "nodo-field"}),
            "descripcion": forms.Textarea(attrs={"class": "nodo-field", "rows": 3, "maxlength": 500}),
            "latitud": forms.HiddenInput(),
            "longitud": forms.HiddenInput(),
        }
        help_texts = {"descripcion": "Opcional. Para qué está o quién lo usa."}

    def clean_nombre(self):
        return self.cleaned_data["nombre"].strip()


class PosicionForm(forms.ModelForm):
    """Mover un punto arrastrándolo: solo la posición."""

    class Meta:
        model = Punto
        fields = ["latitud", "longitud"]
