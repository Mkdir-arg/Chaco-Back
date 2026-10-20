"""Formularios armados desde un diseño del constructor (Cambio 58 y P17).

Un campo de la definición —la misma que consume la app de campo y el link público
(``definicion_formulario``) o la foto de un formulario de tipo de dispositivo— se
traduce a un field de Django **en un solo lugar**: lo usan el paso 2 de la inscripción
pública (``portal.forms.inscripcion``) y el formulario «Crear dispositivo» de P3. Vivía
en el portal; se mudó acá sin cambiar su comportamiento para que el backoffice lo use
sin importar del portal.
"""

from pathlib import Path

from django import forms

from core.validators import validar_firma
from programas.services.respuestas import aplicar, planos_de
from programas.services.respuestas_dispositivo import faltantes_de

INPUT_CLASS = "nodo-field w-full"

# Archivos del formulario público: upload anónimo, límites duros (análisis #289).
ARCHIVO_EXTENSIONES = (".jpg", ".jpeg", ".png", ".pdf")
ARCHIVO_MAX_BYTES = 5 * 1024 * 1024
AYUDA_ARCHIVO = "JPG, PNG o PDF, hasta 5 MB."


def _validar_archivo(archivo):
    nombre = (archivo.name or "").lower()
    if not nombre.endswith(ARCHIVO_EXTENSIONES):
        raise forms.ValidationError("Solo se aceptan archivos JPG, PNG o PDF.")
    if archivo.size > ARCHIVO_MAX_BYTES:
        raise forms.ValidationError("El archivo no puede superar los 5 MB.")
    # SIIS-16: la extensión la elige quien sube el archivo, y acá el upload es
    # **anónimo**. Sin mirar el contenido, un `.pdf` con HTML adentro quedaba en
    # `media/` y después lo abría un coordinador desde el backoffice. La firma
    # de los primeros bytes es del archivo, no de su nombre.
    validar_firma(archivo, Path(nombre).suffix, "El archivo no es un JPG, PNG o PDF válido.")


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


def serializar_valor(valor):
    """Un valor limpio del form, como se guarda en ``respuestas``: fechas en ISO y,
    de un archivo, el nombre (el archivo real va aparte)."""
    if valor in (None, "", []):
        return None
    if hasattr(valor, "name") and hasattr(valor, "size"):
        return valor.name
    if isinstance(valor, (list, tuple)):
        return list(valor)
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    return valor


class RespuestasDisenoForm(forms.Form):
    """Las preguntas de un formulario de tipo de dispositivo (P17), desde su foto.

    Mismo intérprete que el link público de Becas: cada campo se nombra por su clave,
    los textos se muestran en su grupo y las condiciones se evalúan en el navegador y
    **otra vez acá** (un campo oculto no se valida y lo que traiga se descarta).

    A diferencia del link, el tipo de cada valor se valida siempre pero **la
    obligatoriedad no**: el borrador se guarda incompleto y los obligatorios los exige
    «Enviar a validación» (:func:`faltantes_de`). ``guardadas`` son las respuestas ya
    guardadas (edición): precargan por clave y conservan el archivo que no se vuelve a
    subir.
    """

    def __init__(self, *args, foto, guardadas=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.foto = foto
        self.guardadas = dict(guardadas or {})
        self.obligatorios = {}
        self._campos = []  # [(clave, item)] de los que son fields
        self._grupos = []
        self._ocultos = set()
        for grupo in foto.get("items") or []:
            filas = []
            for item in grupo.get("items") or []:
                if item.get("tipo_item") != "campo":
                    filas.append({"tipo": "texto", "clave": item["clave"], "texto": item.get("texto", "")})
                    continue
                filas.append(self._preparar_campo(item))
            self._grupos.append(
                {
                    "clave": grupo["clave"],
                    "titulo": grupo.get("titulo", ""),
                    "subtitulo": grupo.get("subtitulo", ""),
                    "items": filas,
                }
            )

    def _preparar_campo(self, item):
        clave = item["clave"]
        field = _field_para_campo(item)
        obligatorio = bool(item.get("obligatorio"))
        es_archivo = item.get("tipo") == "ARCHIVO"
        field.required = False  # lo exige «Enviar a validación», con las condiciones aplicadas
        field.marca_requerido = obligatorio
        if es_archivo:
            field.help_text = AYUDA_ARCHIVO
        elif clave in self.guardadas:
            self.initial[clave] = self.guardadas[clave]
        self.fields[clave] = field
        self.obligatorios[clave] = obligatorio
        self._campos.append((clave, item))
        return {
            "tipo": "campo",
            "clave": clave,
            "obligatorio": obligatorio,
            "es_archivo": es_archivo,
            "es_checks": item.get("tipo") == "SELECTOR_MULTIPLE" and not _es_buscador(item),
            "archivo_guardado": self.guardadas.get(clave) if es_archivo else None,
            "bound": self[clave],
        }

    # --- Lo que consume el template ---------------------------------------
    def grupos(self):
        return self._grupos

    def planos(self):
        """Los ítems con sus condiciones para el motor del navegador."""
        return planos_de(self.foto)

    # --- Validación con las condiciones aplicadas (RN-6) -------------------
    def _respuestas_de(self, cleaned):
        respuestas = {}
        for clave, item in self._campos:
            valor = serializar_valor(cleaned.get(clave))
            if valor is None and item.get("tipo") == "ARCHIVO":
                # Sin archivo nuevo vale el que ya estaba: también para las condiciones.
                valor = self.guardadas.get(clave)
            if valor is not None:
                respuestas[clave] = valor
        return respuestas

    def clean(self):
        cleaned = super().clean()
        _visibles, ocultos, _efectivas = aplicar(self.foto, self._respuestas_de(cleaned))
        self._ocultos = ocultos
        for clave, _item in self._campos:
            if clave in ocultos:
                # Oculto: no se valida y lo que haya llegado se descarta (D11).
                cleaned[clave] = None
                self.errors.pop(clave, None)
        return cleaned

    # --- Salidas -----------------------------------------------------------
    def respuestas(self):
        """``{clave: valor}`` de lo visible y respondido. Fechas en ISO; un ARCHIVO
        guarda el nombre (el nuevo, o el que ya estaba si no se subió otro)."""
        respuestas = self._respuestas_de(self.cleaned_data)
        return {clave: valor for clave, valor in respuestas.items() if clave not in self._ocultos}

    def archivos(self):
        """``[(clave, archivo)]`` de los ARCHIVO visibles con un archivo nuevo."""
        subidos = []
        for clave, item in self._campos:
            if item.get("tipo") != "ARCHIVO" or clave in self._ocultos:
                continue
            archivo = self.cleaned_data.get(clave)
            if archivo:
                subidos.append((clave, archivo))
        return subidos

    def faltantes(self):
        """Los obligatorios visibles sin responder, con lo que el form tiene hoy: lo
        enviado si volvió del POST, lo guardado si no. Para el panel lateral."""
        if self.is_bound and hasattr(self, "cleaned_data"):
            respuestas = self.respuestas()
        else:
            respuestas = self.guardadas
        return faltantes_de(self.foto, respuestas)

    def marcar_faltantes(self):
        """Pinta «Este dato es obligatorio.» en cada obligatorio visible sin responder
        (cuando «Enviar a validación» se rechazó por el formulario)."""
        for campo in self.faltantes():
            if campo["clave"] in self.fields and not self.has_error(campo["clave"]):
                self.add_error(campo["clave"], "Este dato es obligatorio.")
