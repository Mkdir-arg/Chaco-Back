"""Formularios de la inscripción pública de Becas (#293 paso 1, #294 paso 2)."""

from django import forms

from programas.services.padron import normalizar_dni
from programas.services.personas import fecha_iso
from programas.services.respuestas import aplicar, foto_definicion, legible, planos_de

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
        # Opcional a nivel form: con reCAPTCHA activo este campo no se renderiza
        # —el token viaja en `g-recaptcha-response`— y exigirlo dejaba el paso 1
        # imposible de completar. Quien valida de verdad es `captcha_valido()`
        # en la vista, antes que el form, en los dos modos.
        required=False,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "inputmode": "numeric", "autocomplete": "off"}),
    )

    def clean_dni(self):
        dni = normalizar_dni(self.cleaned_data["dni"])
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


def _es_buscador(campo):
    """¿El campo se configuró para elegir con buscador y píldoras? (Cambio 56).

    La presentación llega en la misma definición que consume la app. Un campo
    guardado antes del cambio no la trae: se lee como lista, que es como se veía.
    """
    return campo.get("presentacion") == "BUSCADOR"


# Atributos que enganchan el control de búsqueda con píldoras sobre el <select>
# nativo. El JS (static/custom/js/nodo-buscador.js) lo monta al cargar; si no
# corre, queda el desplegable del navegador y el formulario funciona igual.
def _attrs_buscador(placeholder):
    return {"class": INPUT_CLASS, "data-buscador": "1", "data-buscador-placeholder": placeholder}


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
        if _es_buscador(campo):
            widget = forms.Select(attrs=_attrs_buscador("Buscá una opción"))
        else:
            widget = forms.Select(attrs={"class": INPUT_CLASS})
        return forms.ChoiceField(label=etiqueta, required=requerido, choices=opciones, widget=widget)
    if tipo == "SELECTOR_MULTIPLE":
        opciones = [(o, o) for o in campo["opciones"]]
        if _es_buscador(campo):
            widget = forms.SelectMultiple(attrs=_attrs_buscador("Buscá y elegí una o varias"))
        else:
            widget = forms.CheckboxSelectMultiple()
        return forms.MultipleChoiceField(label=etiqueta, required=requerido, choices=opciones, widget=widget)
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
    """Paso 2 del link: el formulario **tal como lo diseñó la convocatoria**
    (Cambio 58, task #345).

    Se construye desde ``definicion_formulario(relevamiento)["items"]`` —la
    misma definición anidada que consume la app— y cada campo se nombra por su
    clave de ítem (``pg-<pk>``, ``rn-<pk>``, ``cp-…``). Lo que el paso 1 ya sabe
    del titular (DNI, sexo y, si la identidad se validó, nombre, apellido y
    fecha de nacimiento) no se vuelve a pedir: se muestra fijo y viaja igual en
    las respuestas. Las condiciones se evalúan en el navegador mientras se
    completa y **otra vez acá** (RN-6): un campo oculto no se exige y lo
    respondido para él se descarta.
    """

    # Geolocalización del navegador (best effort — asunción del análisis #289).
    gps_lat = forms.DecimalField(required=False, max_digits=9, decimal_places=6, widget=forms.HiddenInput)
    gps_lng = forms.DecimalField(required=False, max_digits=9, decimal_places=6, widget=forms.HiddenInput)

    def __init__(self, *args, definicion, identificacion, **kwargs):
        super().__init__(*args, **kwargs)
        self.definicion = definicion
        self.foto = foto_definicion(None, definicion)
        self.identificacion = identificacion
        # "personas" (Base de Personas) y "padron" (Cambio 57) traen la
        # identidad validada: no se le vuelve a pedir a la persona.
        self.es_manual = identificacion.get("origen") not in ("personas", "padron")
        self.fijas = {}  # clave → valor que ya sabemos del paso 1
        self.obligatorios = {}  # clave → bool (lo exige clean() si quedó visible)
        self._ocultos = set()
        self._campos = []  # [(clave, item)] de los que son fields
        self._grupos = []
        datos = identificacion.get("datos") or {}
        for grupo in self.foto["items"]:
            filas = []
            for item in grupo.get("items") or []:
                if item.get("tipo_item") != "campo":
                    filas.append(
                        {
                            "tipo": "texto",
                            "clave": item["clave"],
                            "texto": item.get("texto", ""),
                        }
                    )
                    continue
                filas.append(self._preparar_campo(item, datos))
            self._grupos.append(
                {
                    "clave": grupo["clave"],
                    "titulo": grupo.get("titulo", ""),
                    "subtitulo": grupo.get("subtitulo", ""),
                    "items": filas,
                }
            )

    # --- Construcción -----------------------------------------------------
    def _preparar_campo(self, item, datos):
        clave = item["clave"]
        origen = item.get("origen") or "pregunta"
        vinculo = item.get("vinculo") or ""
        fila = {
            "tipo": "campo",
            "clave": clave,
            "label": item.get("texto", ""),
            "obligatorio": bool(item.get("obligatorio")),
            "es_archivo": item.get("tipo") == "ARCHIVO",
            # Múltiple apilado (checkboxes): el template marca el contenedor
            # con .nodo-checks y el estilo vive en nodo-forms.css.
            "es_checks": item.get("tipo") == "SELECTOR_MULTIPLE" and not _es_buscador(item),
            "fijo": None,
            "fijo_texto": "",
            "bound": None,
        }
        valor_fijo = self._valor_fijo(origen, vinculo, datos)
        if valor_fijo:
            self.fijas[clave] = valor_fijo
            fila["fijo"] = valor_fijo
            fila["fijo_texto"] = legible(item, valor_fijo)
            return fila
        field = self._field_vinculado(origen, vinculo, item) or _field_para_campo(item)
        obligatorio = bool(item.get("obligatorio"))
        if origen == "legajo" and vinculo in ("nombre", "apellido", "dni", "fecha_nacimiento"):
            # La identidad del titular siempre se completa (D14 para la fecha).
            obligatorio = True
        field.required = False  # la obligatoriedad la decide clean(), con las condiciones ya aplicadas
        self.fields[clave] = field
        self.obligatorios[clave] = obligatorio
        self._campos.append((clave, item))
        fila["obligatorio"] = obligatorio
        fila["bound"] = self[clave]
        return fila

    def _valor_fijo(self, origen, vinculo, datos):
        """Lo que ya sabemos del titular por el paso 1 y no se vuelve a pedir."""
        if origen != "legajo":
            return None
        if vinculo == "dni":
            return self.identificacion.get("dni") or None
        if vinculo == "genero":
            return self.identificacion.get("sexo") or None
        if self.es_manual:
            return None
        if vinculo in ("nombre", "apellido"):
            return datos.get(vinculo) or None
        if vinculo == "fecha_nacimiento":
            return fecha_iso(datos.get("fecha_nacimiento")) or None
        return None

    def _field_vinculado(self, origen, vinculo, item):
        """Controles con validación propia para los campos del legajo y del
        apoderado; el resto sale de la definición como cualquier campo."""
        if origen == "pregunta":
            return None
        etiqueta = item.get("texto", "")
        if vinculo == "email":
            return forms.EmailField(
                label=etiqueta,
                widget=forms.EmailInput(attrs={"class": INPUT_CLASS, "placeholder": "nombre@correo.com"}),
            )
        if vinculo == "telefono":
            return forms.CharField(
                label=etiqueta,
                max_length=20,
                widget=forms.TextInput(
                    attrs={"class": INPUT_CLASS, "inputmode": "tel", "placeholder": "Ej. 3624123456"}
                ),
            )
        if vinculo == "dni":
            return forms.CharField(
                label=etiqueta,
                max_length=12,
                widget=forms.TextInput(attrs={"class": INPUT_CLASS, "inputmode": "numeric"}),
            )
        if vinculo == "genero":
            return forms.ChoiceField(
                label=etiqueta,
                choices=(("", "Elegí una opción"), ("F", "Femenino"), ("M", "Masculino")),
                widget=forms.Select(attrs={"class": INPUT_CLASS}),
            )
        if vinculo == "fecha_nacimiento":
            return forms.DateField(label=etiqueta, widget=forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}))
        return forms.CharField(label=etiqueta, max_length=120, widget=forms.TextInput(attrs={"class": INPUT_CLASS}))

    # --- Helpers que consume el template ----------------------------------
    def grupos(self):
        return self._grupos

    def planos(self):
        """Los ítems con sus condiciones para el motor del navegador."""
        return planos_de(self.foto)

    # --- Validación con las condiciones aplicadas (RN-6) ------------------
    @staticmethod
    def _serializar(valor):
        if valor in (None, "", []):
            return None
        if hasattr(valor, "name") and hasattr(valor, "size"):
            return valor.name  # archivo: el nombre; el archivo real va aparte
        if isinstance(valor, (list, tuple)):
            return list(valor)
        if hasattr(valor, "isoformat"):
            return valor.isoformat()
        return valor

    def _respuestas_de(self, cleaned):
        respuestas = dict(self.fijas)
        for clave, _item in self._campos:
            valor = self._serializar(cleaned.get(clave))
            if valor is not None:
                respuestas[clave] = valor
        return respuestas

    def clean(self):
        cleaned = super().clean()
        # El GPS es best effort y viaja en campos ocultos: uno malformado se
        # descarta entero, porque un error ahí no se puede ver ni corregir.
        if "gps_lat" in self.errors or "gps_lng" in self.errors:
            self.errors.pop("gps_lat", None)
            self.errors.pop("gps_lng", None)
            cleaned["gps_lat"] = cleaned["gps_lng"] = None
        _visibles, ocultos, _efectivas = aplicar(self.foto, self._respuestas_de(cleaned))
        self._ocultos = ocultos
        for clave, item in self._campos:
            if clave in ocultos:
                # Oculto: no se exige y lo que haya llegado se descarta (D11).
                cleaned[clave] = None
                self.errors.pop(clave, None)
                continue
            valor = cleaned.get(clave)
            if (item.get("vinculo") or "") == "dni" and valor:
                valor = normalizar_dni(valor)
                cleaned[clave] = valor
                if len(valor) not in (7, 8):
                    self.add_error(clave, "Ingresá un DNI válido de 7 u 8 dígitos.")
                    continue
            if self.obligatorios.get(clave) and valor in (None, "", []) and clave not in self.errors:
                self.add_error(clave, "Este dato es obligatorio.")
        return cleaned

    # --- Salidas hacia la ingesta -----------------------------------------
    def respuestas(self):
        """``{clave: valor}`` de lo visible y respondido, más lo que ya sabíamos
        del titular. Fechas en ISO; los ARCHIVO guardan el nombre."""
        respuestas = dict(self.fijas)
        for clave, _item in self._campos:
            if clave in self._ocultos:
                continue
            valor = self._serializar(self.cleaned_data.get(clave))
            if valor is not None:
                respuestas[clave] = valor
        return respuestas

    def archivos(self):
        """``[(clave, item, archivo)]`` de los ARCHIVO visibles con archivo."""
        subidos = []
        for clave, item in self._campos:
            if item.get("tipo") != "ARCHIVO" or clave in self._ocultos:
                continue
            archivo = self.cleaned_data.get(clave)
            if archivo:
                subidos.append((clave, item, archivo))
        return subidos
