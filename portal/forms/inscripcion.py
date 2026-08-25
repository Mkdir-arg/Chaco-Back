"""Formularios de la inscripción pública de Becas (#293 paso 1, #294 paso 2)."""

from django import forms
from django.utils.dateparse import parse_date

from programas.services.becas import es_menor
from programas.services.personas import fecha_iso

INPUT_CLASS = "nodo-field w-full"

# Archivos del formulario público: upload anónimo, límites duros (análisis #289).
ARCHIVO_EXTENSIONES = (".jpg", ".jpeg", ".png", ".pdf")
ARCHIVO_MAX_BYTES = 5 * 1024 * 1024


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


def _validar_archivo(archivo):
    nombre = (archivo.name or "").lower()
    if not nombre.endswith(ARCHIVO_EXTENSIONES):
        raise forms.ValidationError("Solo se aceptan archivos JPG, PNG o PDF.")
    if archivo.size > ARCHIVO_MAX_BYTES:
        raise forms.ValidationError("El archivo no puede superar los 5 MB.")


def _field_para_campo(campo):
    """Traduce un campo de ``definicion_formulario`` (la misma definición que
    consume la app, RN-P12) a un field de Django. Tipos: ``TipoCampo``."""
    etiqueta = campo["texto"]
    requerido = bool(campo["obligatorio"])
    tipo = campo["tipo"]
    if tipo == "INT":
        return forms.IntegerField(
            label=etiqueta,
            required=requerido,
            widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "inputmode": "numeric"}),
        )
    if tipo == "SELECTOR":
        opciones = [("", "Elegí una opción")] + [(o, o) for o in campo["opciones"]]
        return forms.ChoiceField(
            label=etiqueta, required=requerido, choices=opciones, widget=forms.Select(attrs={"class": INPUT_CLASS})
        )
    if tipo == "SELECTOR_MULTIPLE":
        opciones = [(o, o) for o in campo["opciones"]]
        return forms.MultipleChoiceField(
            label=etiqueta, required=requerido, choices=opciones, widget=forms.CheckboxSelectMultiple
        )
    if tipo == "DATE":
        return forms.DateField(
            label=etiqueta,
            required=requerido,
            widget=forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}),
        )
    if tipo == "ARCHIVO":
        return forms.FileField(
            label=etiqueta,
            required=requerido,
            validators=[_validar_archivo],
            widget=forms.ClearableFileInput(attrs={"class": INPUT_CLASS, "accept": ".jpg,.jpeg,.png,.pdf"}),
        )
    return forms.CharField(
        label=etiqueta, required=requerido, max_length=500, widget=forms.TextInput(attrs={"class": INPUT_CLASS})
    )


class InscripcionPaso2Form(forms.Form):
    """Paso 2 del link (#294): contacto + formulario dinámico + apoderado.

    Se construye desde ``definicion_formulario(relevamiento)`` — misma fuente
    que la app de campo, sin definiciones paralelas (RN-P12). Las preguntas
    globales entran como ``g_<pk>`` y los requisitos como ``r_<pk>``; un POST
    con ids ajenos a la definición se ignora (nunca llega a ``data``).
    """

    # Identidad manual (solo cuando el paso 1 no validó contra Gran Base).
    nombre = forms.CharField(
        label="Nombre", max_length=120, widget=forms.TextInput(attrs={"class": INPUT_CLASS})
    )
    apellido = forms.CharField(
        label="Apellido", max_length=120, widget=forms.TextInput(attrs={"class": INPUT_CLASS})
    )
    fecha_nacimiento = forms.DateField(
        label="Fecha de nacimiento",
        widget=forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}),
    )

    # Bloque C — contacto (obligatorio en el modelo).
    celular = forms.CharField(
        label="Celular",
        max_length=20,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "inputmode": "tel", "placeholder": "Ej. 3624123456"}),
    )
    email_contacto = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={"class": INPUT_CLASS, "placeholder": "nombre@correo.com"}),
    )

    # Bloque D — apoderado (obligatorio solo para menores, RN-22/RN-P9).
    apoderado_nombre = forms.CharField(
        label="Nombre del apoderado", max_length=120, required=False, widget=forms.TextInput(attrs={"class": INPUT_CLASS})
    )
    apoderado_apellido = forms.CharField(
        label="Apellido del apoderado", max_length=120, required=False, widget=forms.TextInput(attrs={"class": INPUT_CLASS})
    )
    apoderado_dni = forms.CharField(
        label="DNI del apoderado", max_length=12, required=False, widget=forms.TextInput(attrs={"class": INPUT_CLASS, "inputmode": "numeric"})
    )
    apoderado_genero = forms.ChoiceField(
        label="Sexo del apoderado",
        required=False,
        choices=(("", "Elegí una opción"), ("F", "Femenino"), ("M", "Masculino")),
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    apoderado_fecha_nacimiento = forms.DateField(
        label="Fecha de nacimiento del apoderado",
        required=False,
        widget=forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}),
    )

    # Geolocalización del navegador (best effort — asunción del análisis #289).
    gps_lat = forms.DecimalField(required=False, max_digits=9, decimal_places=6, widget=forms.HiddenInput)
    gps_lng = forms.DecimalField(required=False, max_digits=9, decimal_places=6, widget=forms.HiddenInput)

    def __init__(self, *args, definicion, identificacion, **kwargs):
        super().__init__(*args, **kwargs)
        self.definicion = definicion
        self.identificacion = identificacion
        self.es_manual = identificacion.get("origen") != "personas"
        if not self.es_manual:
            # La identidad ya vino validada del paso 1: no se pide ni se pisa.
            del self.fields["nombre"], self.fields["apellido"]
            datos = self.identificacion.get("datos") or {}
            if fecha_iso(datos.get("fecha_nacimiento")):
                del self.fields["fecha_nacimiento"]
            else:
                self.fields["fecha_nacimiento"].label = "No pudimos obtener tu fecha de nacimiento: completala"
        self._campos_dinamicos = []
        for prefijo, lista in (("g", definicion["globales"]), ("r", definicion["requisitos"])):
            for campo in lista:
                clave = f"{prefijo}_{campo['id']}"
                self.fields[clave] = _field_para_campo(campo)
                self._campos_dinamicos.append((clave, campo))

    # --- Helpers que consume el template ---------------------------------
    def campos_globales(self):
        return [self[clave] for clave, campo in self._campos_dinamicos if clave.startswith("g_")]

    def campos_requisitos(self):
        return [self[clave] for clave, campo in self._campos_dinamicos if clave.startswith("r_")]

    # --- RN-22: apoderado obligatorio para menores ------------------------
    def fecha_nacimiento_efectiva(self):
        if self.es_manual:
            return self.cleaned_data.get("fecha_nacimiento")
        if "fecha_nacimiento" in self.fields:
            return self.cleaned_data.get("fecha_nacimiento")
        datos = self.identificacion.get("datos") or {}
        return parse_date(fecha_iso(datos.get("fecha_nacimiento")) or "") or None

    def clean(self):
        cleaned = super().clean()
        dni_apoderado_original = cleaned.get("apoderado_dni")
        dni_apoderado = "".join(ch for ch in str(dni_apoderado_original or "") if ch.isdigit())
        if dni_apoderado_original and len(dni_apoderado) not in (7, 8):
            self.add_error("apoderado_dni", "Ingresa un DNI valido de 7 u 8 digitos.")
        cleaned["apoderado_dni"] = dni_apoderado
        if es_menor(self.fecha_nacimiento_efectiva()):
            campos = (
                "apoderado_nombre",
                "apoderado_apellido",
                "apoderado_dni",
                "apoderado_genero",
                "apoderado_fecha_nacimiento",
            )
            for campo in campos:
                if not cleaned.get(campo):
                    self.add_error(campo, "Este dato es obligatorio cuando la persona que se inscribe es menor de edad.")
        return cleaned

    # --- Salidas hacia la ingesta (#295) ----------------------------------
    def respuestas(self):
        """``Formulario.data`` con el mismo contrato que la app: claves por pk
        en string, bajo "globales" y "requisitos". Los ARCHIVO guardan el
        nombre; el archivo real viaja aparte como ``AdjuntoFormulario``."""
        data = {"globales": {}, "requisitos": {}}
        for clave, campo in self._campos_dinamicos:
            valor = self.cleaned_data.get(clave)
            if valor in (None, "", []):
                continue
            if campo["tipo"] == "ARCHIVO":
                valor = valor.name
            elif hasattr(valor, "isoformat"):
                valor = valor.isoformat()
            destino = "globales" if clave.startswith("g_") else "requisitos"
            data[destino][str(campo["id"])] = valor
        return data

    def archivos(self):
        """Lista de ``(alcance, id_campo, archivo)`` para crear los adjuntos."""
        subidos = []
        for clave, campo in self._campos_dinamicos:
            if campo["tipo"] != "ARCHIVO":
                continue
            archivo = self.cleaned_data.get(clave)
            if archivo:
                alcance = "global" if clave.startswith("g_") else "requisito"
                subidos.append((alcance, campo["id"], archivo))
        return subidos
