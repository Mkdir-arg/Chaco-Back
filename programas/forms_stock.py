"""Formularios de las pantallas de stock (análisis 010, PR 5: «Entregar a persona»).

Validan **la entrada** —que haya un número donde va un número, que el DNI tenga forma de DNI—; las reglas (permiso,
saldo, persona fallecida, institución activa) las decide ``programas/services/stock.py``, que es lo mismo que usa la
app. ``agregar_errores_del_servicio`` lleva cada rechazo del servicio a su campo.
"""

import uuid

from django import forms

from legajos.models import Ciudadano
from programas.forms import INPUT_CLASS
from programas.forms_emergencia import ErroresDelServicioMixin
from programas.services.kits import CANTIDAD_MAXIMA
from programas.services.stock import OBSERVACION_MAXIMA

#: Prefijo de los campos de cantidad: ``cantidad_<id del insumo>``.
PREFIJO_CANTIDAD = "cantidad_"
OCULTOS = ("dni", "sexo", "nombre", "apellido", "uuid_cliente")
CANTIDAD_ENTREGADA_INVALIDA = "Tiene que ser un número entero, cero o más."
FALTA_EL_IDENTIFICADOR = "Falta el identificador del envío: volvé a abrir la pantalla."


def _numero(minimo):
    return forms.NumberInput(attrs={"class": INPUT_CLASS, "min": minimo, "inputmode": "numeric"})


class PersonaForm(ErroresDelServicioMixin, forms.Form):
    """A quién se le entrega: DNI y, si hace falta, sexo (para consultar el Registro) o nombre y apellido (alta mínima).

    Es el GET de la pantalla: **no escribe nada**. Nombre y apellido solo se muestran cuando el servicio contestó
    ``PERSONA_SIN_DATOS`` (``pedir_nombre``).
    """

    dni = forms.CharField(
        label="DNI",
        max_length=15,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "inputmode": "numeric", "autocomplete": "off"}),
    )
    sexo = forms.ChoiceField(
        label="Sexo",
        required=False,
        choices=[("", "Elegí…"), *Ciudadano.Genero.choices],
        help_text="Solo hace falta si la persona todavía no tiene legajo: se usa para consultar el Registro de Personas.",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    nombre = forms.CharField(
        label="Nombre", required=False, max_length=120, widget=forms.TextInput(attrs={"class": INPUT_CLASS})
    )
    apellido = forms.CharField(
        label="Apellido", required=False, max_length=120, widget=forms.TextInput(attrs={"class": INPUT_CLASS})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pedir_nombre = False

    def campos_visibles(self):
        """Los campos que se dibujan: nombre y apellido solo si el Registro no la tiene."""

        nombres = ("dni", "sexo", "nombre", "apellido") if self.pedir_nombre else ("dni", "sexo")
        return [self[nombre] for nombre in nombres]


class EntregaPersonaForm(ErroresDelServicioMixin, forms.Form):
    """La entrega: una cantidad por insumo **con saldo** en el edificio, una observación y el identificador del envío.

    La persona viaja en cuatro ocultos y el servicio la vuelve a resolver: lo que llega por acá no se cree. Un campo
    de cantidad vacío es «no entrego de este insumo». ``uuid_cliente`` es el de la idempotencia (RN-010-18): se genera al
    abrir la pantalla y se conserva en los reintentos, así un doble clic no entrega dos veces.
    """

    dni = forms.CharField(required=False, widget=forms.HiddenInput())
    sexo = forms.CharField(required=False, widget=forms.HiddenInput())
    nombre = forms.CharField(required=False, widget=forms.HiddenInput())
    apellido = forms.CharField(required=False, widget=forms.HiddenInput())
    uuid_cliente = forms.UUIDField(
        error_messages={"required": FALTA_EL_IDENTIFICADOR, "invalid": FALTA_EL_IDENTIFICADOR},
        widget=forms.HiddenInput(),
    )
    observacion = forms.CharField(
        label="Observación",
        required=False,
        max_length=OBSERVACION_MAXIMA,
        help_text="Opcional. Queda en el movimiento de stock; no pongas datos de salud.",
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
    )

    def __init__(self, *args, saldos, **kwargs):
        super().__init__(*args, **kwargs)
        self.saldos = list(saldos)
        cantidades = {}
        for saldo in self.saldos:
            cantidades[f"{PREFIJO_CANTIDAD}{saldo.item_id}"] = forms.IntegerField(
                label=saldo.item.nombre,
                required=False,
                min_value=0,
                max_value=CANTIDAD_MAXIMA,
                error_messages={
                    "invalid": CANTIDAD_ENTREGADA_INVALIDA,
                    "min_value": CANTIDAD_ENTREGADA_INVALIDA,
                    "max_value": CANTIDAD_ENTREGADA_INVALIDA,
                },
                widget=_numero(0),
            )
        # Las cantidades primero: es lo que se carga.
        self.fields = {**cantidades, **self.fields}
        if not self.is_bound:
            self.initial.setdefault("uuid_cliente", uuid.uuid4())

    def _post_clean(self):
        """El error de un campo oculto no tiene dónde dibujarse: sube a los errores generales (``_form_errores``)."""

        super()._post_clean()
        for nombre in OCULTOS:
            for mensaje in self._errors.pop(nombre, []):
                self.add_error(None, mensaje)

    def filas(self):
        """Las filas de ``components/_tabla_cantidades.html``: el insumo, su unidad y el saldo **de ahora**."""

        return [
            {
                "campo": self[f"{PREFIJO_CANTIDAD}{saldo.item_id}"],
                "nombre": saldo.item.nombre,
                "unidad": saldo.item.unidad,
                "info": [{"texto": str(saldo.cantidad), "nota": ""}],
            }
            for saldo in self.saldos
        ]

    def lineas(self):
        """``{item_id: cantidad}`` de lo que se entrega: solo las cantidades mayores que 0."""

        lineas = {}
        for saldo in self.saldos:
            cantidad = self.cleaned_data.get(f"{PREFIJO_CANTIDAD}{saldo.item_id}")
            if cantidad:
                lineas[saldo.item_id] = cantidad
        return lineas

    def campo_de_cantidad(self, item_id):
        return f"{PREFIJO_CANTIDAD}{item_id}"

    def marcar_faltantes(self, faltantes):
        """Pone en la fila de cada insumo que no alcanzó cuánto pidió y cuánto hay **ahora** (``{item_id: (pedido, hay)}``)."""

        for item_id, (pedido, hay) in faltantes.items():
            campo = self.campo_de_cantidad(item_id)
            if campo in self.fields:
                self.add_error(campo, f"Hay {hay} y pediste {pedido}.")
