"""Formularios de la bitácora del turno (P10).

Salieron de `programas/forms_dispositivos.py` sin cambios, para que ese archivo no pase de las
1000 líneas.
"""

from django import forms

from core.validators import ACCEPT_ADJUNTO
from core.widgets import ChipsSelectMultiple, SwitchInput
from programas.forms import INPUT_CLASS
from programas.models import EntradaBitacora, Turno
from programas.services.bitacora_pantalla import TIPOS_MANUALES

# --------------------------------------------------------------------------- #
# Bitácora del turno (P10 · #697)
# --------------------------------------------------------------------------- #
#
# Los formularios solo traducen lo que llega del modal. Las reglas —turno en curso,
# personas alojadas en ese momento, tope de adjuntos, superposición de turnos— viven en
# `programas.services.bitacora`, y la vista muestra su error tal cual.

_FORMATOS_MOMENTO = ["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"]


class AdjuntosInput(forms.FileInput):
    """Un `<input type="file" multiple>`."""

    allow_multiple_selected = True


class AdjuntosField(forms.FileField):
    """Varios archivos en un campo. Devuelve la lista tal cual llegó.

    Cada archivo y el tope por novedad los valida `bitacora._guardar_adjuntos` —con los
    heredados de la versión que se corrige—, antes de escribir el primero: acá no se
    repite la regla.
    """

    def clean(self, data, initial=None):
        if isinstance(data, (list, tuple)):
            return [archivo for archivo in data if archivo]
        return [data] if data else []


class _IdsField(forms.MultipleChoiceField):
    """Ids marcados en el modal (casillas «Quitar» armadas por Alpine, que escriben el nombre en el POST).

    Devuelve una lista de enteros y rechaza lo no numérico. No se validan contra opciones: son de la
    novedad que se elige en el mismo modal, y `bitacora.corregir_entrada` exige que lo sean. El widget
    solo fija el nombre del campo en el POST: nunca se dibuja.
    """

    def to_python(self, value):
        try:
            return [int(str(valor).strip()) for valor in super().to_python(value)]
        except ValueError:
            raise forms.ValidationError("Alguno de los elementos a quitar no es válido.", code="invalid") from None

    def valid_value(self, value):
        return True


class _PersonasYAdjuntosForm(forms.Form):
    """Las personas y los adjuntos que comparten el alta y la corrección de una novedad."""

    etiqueta_personas = ""
    etiqueta_adjuntos = ""
    ayuda_adjuntos = ""

    personas = forms.MultipleChoiceField(required=False, choices=(), widget=ChipsSelectMultiple)
    adjuntos = AdjuntosField(
        required=False,
        widget=AdjuntosInput(attrs={"class": INPUT_CLASS, "accept": ACCEPT_ADJUNTO}),
    )

    def __init__(self, *args, personas=(), max_adjuntos=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["personas"].label = self.etiqueta_personas
        self.fields["personas"].choices = [(str(pk), etiqueta) for pk, etiqueta in personas]
        self.fields["adjuntos"].label = self.etiqueta_adjuntos
        if max_adjuntos:
            self.fields["adjuntos"].help_text = self.ayuda_adjuntos.format(max=max_adjuntos)


class NovedadForm(_PersonasYAdjuntosForm):
    """Cargar una novedad del turno en curso (`bitacora.registrar_entrada`)."""

    tipo = forms.ChoiceField(
        label="Tipo",
        choices=(),
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
        error_messages={"required": "Elegí el tipo de novedad."},
    )
    momento = forms.DateTimeField(
        label="Cuándo pasó",
        required=False,
        input_formats=_FORMATOS_MOMENTO,
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"class": INPUT_CLASS, "type": "datetime-local"}),
        help_text="Vacío = ahora. Puede ser más temprano, dentro del turno en curso.",
    )
    texto = forms.CharField(
        label="Qué pasó",
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 4}),
        error_messages={"required": "Contá qué pasó."},
    )
    etiqueta_personas = "Personas involucradas"
    etiqueta_adjuntos = "Adjuntos"
    ayuda_adjuntos = "Hasta {max} archivos: PDF, imágenes o documentos de 5 MB."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipo"].choices = [("", "Elegí el tipo"), *TIPOS_MANUALES]


class CorreccionForm(_PersonasYAdjuntosForm):
    """Corregir una novedad del turno en curso: agrega una versión (`bitacora.corregir_entrada`)."""

    # Un entero con un `<select>`: las opciones las arma la vista con las novedades del turno
    # en curso, sin una consulta (ni un `__str__` por fila) para dibujarlas; al recibir, solo
    # se exige que sea de este dispositivo. Que sea del turno en curso lo decide el servicio.
    entrada = forms.IntegerField(
        label="Novedad a corregir",
        widget=forms.Select(
            attrs={"class": INPUT_CLASS, "x-model": "correccion.entrada", "@change": "elegirCorreccion()"}
        ),
        error_messages={
            "required": "Elegí la novedad que querés corregir.",
            "invalid": "Elegí la novedad que querés corregir.",
        },
    )
    tipo = forms.ChoiceField(
        label="Tipo",
        choices=(),
        widget=forms.Select(attrs={"class": INPUT_CLASS, "x-model": "correccion.tipo"}),
        error_messages={"required": "Elegí el tipo de novedad."},
    )
    texto = forms.CharField(
        label="Texto corregido",
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 4, "x-model": "correccion.texto"}),
        error_messages={"required": "La novedad necesita un texto."},
    )
    motivo = forms.CharField(
        label="Motivo de la corrección",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Opcional"}),
    )
    # Se puede sumar (los mismos campos y validación que el alta) y quitar lo cargado por error:
    # la versión nueva no lo lleva, la anterior lo conserva.
    quitar_adjuntos = _IdsField(required=False, widget=forms.MultipleHiddenInput)
    quitar_personas = _IdsField(required=False, widget=forms.MultipleHiddenInput)
    etiqueta_personas = "Sumar personas involucradas"
    etiqueta_adjuntos = "Sumar adjuntos"
    ayuda_adjuntos = "Hasta {max} archivos por novedad, contando los que ya tiene: PDF, imágenes o documentos de 5 MB."

    def __init__(self, *args, dispositivo=None, corregibles=(), **kwargs):
        # Los dos modales conviven en la página: sin prefijo de id repetirían `id_texto`, etc.
        kwargs.setdefault("auto_id", "id_corr_%s")
        super().__init__(*args, **kwargs)
        self.dispositivo = dispositivo
        self.fields["tipo"].choices = [("", "Elegí el tipo"), *TIPOS_MANUALES]
        self.fields["entrada"].widget.choices = [("", "Elegí la novedad"), *corregibles]

    def clean_entrada(self):
        entrada = EntradaBitacora.objects.filter(pk=self.cleaned_data["entrada"], dispositivo=self.dispositivo).first()
        if entrada is None:
            raise forms.ValidationError("Esa novedad no es de este dispositivo.")
        return entrada


class TurnoForm(forms.Form):
    """Alta o edición de un turno (`bitacora.crear_turno` / `editar_turno`).

    Sin `turno` es un alta; con `turno`, la edición de ese. Un turno no se borra: se da de
    baja con «Activo».
    """

    # Como `CorreccionForm.entrada`: las opciones salen de la vista y al recibir solo se
    # exige que el turno sea de este dispositivo.
    turno = forms.IntegerField(
        label="Turno",
        required=False,
        widget=forms.Select(attrs={"class": INPUT_CLASS, "x-model": "turnoForm.turno", "@change": "elegirTurno()"}),
        error_messages={"invalid": "Ese turno no es de este dispositivo."},
    )
    nombre = forms.CharField(
        label="Nombre",
        max_length=60,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Mañana", "x-model": "turnoForm.nombre"}),
        error_messages={"required": "El turno necesita un nombre."},
    )
    hora_desde = forms.TimeField(
        label="Desde",
        widget=forms.TimeInput(
            format="%H:%M", attrs={"class": INPUT_CLASS, "type": "time", "x-model": "turnoForm.desde"}
        ),
        error_messages={"required": "Indicá a qué hora empieza."},
    )
    hora_hasta = forms.TimeField(
        label="Hasta",
        widget=forms.TimeInput(
            format="%H:%M", attrs={"class": INPUT_CLASS, "type": "time", "x-model": "turnoForm.hasta"}
        ),
        help_text="Si termina más temprano que su inicio, cruza la medianoche (22:00 a 06:00).",
        error_messages={"required": "Indicá a qué hora termina."},
    )
    orden = forms.IntegerField(
        label="Orden",
        min_value=0,
        max_value=32767,
        initial=0,
        required=False,
        widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "x-model": "turnoForm.orden"}),
    )
    activo = forms.BooleanField(
        label="Activo",
        required=False,
        # Tildado de fábrica: el alta de un turno es, por abrumadora mayoría, un turno que
        # empieza a regir. Lo pide el render sin JS —Alpine lo pisa al elegir un turno de la
        # lista—, y desde que `crear_turno` honra el interruptor un alta sin el campo crearía
        # un turno dado de baja sin que nadie lo haya pedido.
        initial=True,
        widget=SwitchInput(attrs={"x-model": "turnoForm.activo"}),
    )

    def __init__(self, *args, dispositivo=None, turnos=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.dispositivo = dispositivo
        self.fields["turno"].widget.choices = [("", "Nuevo turno"), *turnos]

    def clean_turno(self):
        pk = self.cleaned_data["turno"]
        if pk is None:
            return None
        turno = Turno.objects.filter(pk=pk, dispositivo=self.dispositivo).first()
        if turno is None:
            raise forms.ValidationError("Ese turno no es de este dispositivo.")
        return turno
