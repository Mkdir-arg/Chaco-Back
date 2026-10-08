"""Formularios de las campañas.

``CampanaForm`` es un ``forms.Form`` y no un ``ModelForm`` a propósito: los dos archivos no
se guardan tal cual, se **procesan** (el Excel se lee y se deduplica, el HTML se sanea) y
en la edición son opcionales —vacío quiere decir «dejar el que está»—, algo que el
``FileField`` de un ``ModelForm`` resuelve con el ``ClearableFileInput`` y su link al
archivo, que acá no corresponde. La escritura la hace ``services.campanas``.
"""

from django import forms
from django.conf import settings

from notificaciones.models import TOPE_DESTINATARIOS, Campana
from notificaciones.services import html as servicio_html
from notificaciones.services.lectura_excel import parsear_destinatarios

_FIELD_CLASS = "nodo-field"


def _tope():
    return f"{TOPE_DESTINATARIOS:,}".replace(",", ".")


class CampanaForm(forms.Form):
    nombre = forms.CharField(
        label="Nombre",
        max_length=Campana._meta.get_field("nombre").max_length,
        help_text="Para identificarla en el listado. No lo ve el destinatario.",
        widget=forms.TextInput(attrs={"class": _FIELD_CLASS, "placeholder": "Ej: Apertura convocatoria Becas 2027"}),
    )
    asunto = forms.CharField(
        label="Asunto",
        max_length=Campana._meta.get_field("asunto").max_length,
        widget=forms.TextInput(attrs={"class": _FIELD_CLASS}),
    )
    archivo_excel = forms.FileField(
        label="Lista de destinatarios (Excel)",
        widget=forms.FileInput(attrs={"class": _FIELD_CLASS, "accept": ".xlsx"}),
    )
    archivo_html = forms.FileField(
        label="Cuerpo del correo (HTML)",
        widget=forms.FileInput(attrs={"class": _FIELD_CLASS, "accept": ".html,.htm"}),
    )

    def __init__(self, *args, campana=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.campana = campana
        self.lectura = None
        self.datos_html = None
        prefijo = settings.EMAIL_ASUNTO_PREFIJO.strip()
        self.fields["asunto"].help_text = "Lo que lee la persona en su bandeja. Hasta 150 caracteres." + (
            f" En este ambiente se le antepone «{prefijo}»." if prefijo else ""
        )
        ayuda_excel = (
            f"Solo .xlsx, hasta 2 MB y hasta {_tope()} correos. Primera hoja, una dirección por fila en la "
            "columna con encabezado «email» (también vale «correo» o «mail»); sin encabezado se lee la "
            "columna A. Las direcciones inválidas y las repetidas se descartan y se listan en la previsualización."
        )
        ayuda_html = (
            "Solo .html, hasta 1 MB, en UTF-8. Las imágenes tienen que estar publicadas en una dirección "
            "https://: no se envían adjuntos. Se quitan scripts, formularios y contenido incrustado por seguridad."
        )
        if campana is not None:
            self.fields["archivo_excel"].required = False
            self.fields["archivo_html"].required = False
            ayuda_excel = (
                f"Actual: {campana.nombre_excel or 'lista cargada'}. Subí otro solo para reemplazarla. " + ayuda_excel
            )
            ayuda_html = (
                f"Actual: {campana.nombre_html or 'cuerpo cargado'}. Subí otro solo para reemplazarlo. " + ayuda_html
            )
        self.fields["archivo_excel"].help_text = ayuda_excel
        self.fields["archivo_html"].help_text = ayuda_html

    def clean_nombre(self):
        return self.cleaned_data["nombre"].strip()

    def clean_asunto(self):
        # Un salto de línea en el asunto es un header roto: Django lo rechaza al enviar.
        return " ".join(self.cleaned_data["asunto"].split())

    def clean_archivo_excel(self):
        archivo = self.cleaned_data.get("archivo_excel")
        if archivo:
            self.lectura = parsear_destinatarios(archivo)
        return archivo

    def clean_archivo_html(self):
        archivo = self.cleaned_data.get("archivo_html")
        if archivo:
            self.datos_html = servicio_html.procesar(archivo)
        return archivo


class PruebaForm(forms.Form):
    """El correo de destino de «Enviar prueba» (RF-007-18): una sola dirección, cualquier dominio."""

    email = forms.EmailField(
        label="Correo de destino",
        max_length=254,
        widget=forms.EmailInput(attrs={"class": _FIELD_CLASS, "autocomplete": "email"}),
    )

    def __init__(self, *args, **kwargs):
        # `auto_id` propio: el detalle muestra este form junto a otros campos con id de fábrica.
        kwargs.setdefault("auto_id", "id_prueba_%s")
        super().__init__(*args, **kwargs)

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()
