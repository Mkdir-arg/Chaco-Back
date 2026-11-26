"""Formularios de las pantallas de stock (análisis 010, PR 5 y 6a: entregar, ingresar y traspasar).

Validan **la entrada** —que haya un número donde va un número, que el DNI tenga forma de DNI—; las reglas (permiso,
saldo, persona fallecida, institución activa, origen «Otro» con su detalle) las decide ``programas/services/stock.py``,
que es lo mismo que usa la app. ``agregar_errores_del_servicio`` lleva cada rechazo del servicio a su campo.

Las tres pantallas con tabla de cantidades comparten :class:`FormConTablaDeCantidades`: un campo ``cantidad_<id>`` por
insumo (``forms_cantidades``), la guarda de «un insumo pedido sin fila no se descarta en silencio» y el identificador del
envío. Copiarla en cada formulario es lo que pierde la guarda.
"""

import uuid

from django import forms

from legajos.models import Ciudadano
from programas.forms import INPUT_CLASS
from programas.forms_cantidades import campo_de, campo_de_cantidad, claves_sin_campo, numero
from programas.forms_emergencia import ErroresDelServicioMixin
from programas.models import OperacionStock
from programas.services.kits import CANTIDAD_MAXIMA
from programas.services.stock import (
    COMPROBANTE_MAXIMO,
    CONTADO_INVALIDO,
    DESTINO_INVALIDO,
    MOTIVO_INVALIDO,
    OBSERVACION_MAXIMA,
    ORIGEN_DETALLE_MAXIMO,
    SALDO_VISTO_INVALIDO,
)

CANTIDAD_INVALIDA = "Tiene que ser un número entero, cero o más."
FALTA_EL_IDENTIFICADOR = "Falta el identificador del envío: volvé a abrir la pantalla."
INSUMO_SIN_FILA = (
    "Algún insumo ya no está en el stock de este edificio. Volvé a cargar la pantalla y revisá las cantidades."
)
INSUMO_YA_NO_DISPONIBLE = (
    "Algún insumo se desactivó mientras cargabas. Volvé a cargar la pantalla y revisá las cantidades."
)
SIN_CANTIDADES = "Cargá la cantidad de al menos un insumo."


def _select():
    return forms.Select(attrs={"class": INPUT_CLASS})


class FormConTablaDeCantidades(ErroresDelServicioMixin, forms.Form):
    """Una cantidad por insumo (``insumos`` es ``[(TipoKit, en_stock)]``), el identificador del envío y lo propio de cada pantalla.

    Un campo de cantidad vacío es «de este insumo no va». ``uuid_cliente`` es el de la idempotencia (RN-010-18): se
    genera al abrir la pantalla y se conserva en los reintentos, así un doble clic no opera dos veces.
    """

    #: Los campos que viajan ocultos: no tienen dónde dibujar su error, y el del servicio sube a los errores generales.
    OCULTOS = ("uuid_cliente",)
    #: Lo que dice la guarda cuando llega una cantidad de un insumo que ya no tiene fila.
    TEXTO_SIN_FILA = INSUMO_SIN_FILA

    uuid_cliente = forms.UUIDField(
        error_messages={"required": FALTA_EL_IDENTIFICADOR, "invalid": FALTA_EL_IDENTIFICADOR},
        widget=forms.HiddenInput(),
    )

    def __init__(self, *args, insumos, **kwargs):
        super().__init__(*args, **kwargs)
        self.CAMPOS_ARRIBA = self.OCULTOS
        self.insumos = list(insumos)
        cantidades = {
            campo_de(item.pk): campo_de_cantidad(item, minimo=0, mensaje=CANTIDAD_INVALIDA)
            for item, _hay in self.insumos
        }
        # Las cantidades primero: es lo que se carga.
        self.fields = {**cantidades, **self.fields}
        if not self.is_bound:
            self.initial.setdefault("uuid_cliente", uuid.uuid4())

    def clean(self):
        limpio = super().clean()
        # Una cantidad de un insumo que no tiene fila (la vista arma las filas con lo de ahora, y en stock **más** los
        # insumos que llegan cargados) no se descarta en silencio: la operación saldría distinta de lo mostrado.
        if claves_sin_campo(self.data, self.fields):
            raise forms.ValidationError(self.TEXTO_SIN_FILA)
        if not self.errors and not self.lineas():
            raise forms.ValidationError(SIN_CANTIDADES)
        return limpio

    def _post_clean(self):
        """El error de un campo oculto no tiene dónde dibujarse: sube a los errores generales (``_form_errores``)."""

        super()._post_clean()
        for nombre in self.OCULTOS:
            for mensaje in self._errors.pop(nombre, []):
                self.add_error(None, mensaje)

    def filas(self):
        """Las filas de ``components/_tabla_cantidades.html``: el insumo, su unidad y lo que hay **ahora**."""

        return [
            {
                "campo": self[campo_de(item.pk)],
                "nombre": item.nombre,
                "unidad": item.unidad,
                "info": [{"texto": str(hay), "nota": ""}],
            }
            for item, hay in self.insumos
        ]

    def lineas(self):
        """``{item_id: cantidad}`` de lo que se mueve: solo las cantidades mayores que 0."""

        lineas = {}
        for item, _hay in self.insumos:
            cantidad = self.cleaned_data.get(campo_de(item.pk))
            if cantidad:
                lineas[item.pk] = cantidad
        return lineas

    def marcar_faltantes(self, faltantes):
        """Pone en la fila de cada insumo que no alcanzó cuánto pidió y cuánto hay **ahora** (``{item_id: (pedido, hay)}``)."""

        for item_id, (pedido, hay) in faltantes.items():
            campo = campo_de(item_id)
            if campo in self.fields:
                self.add_error(campo, f"Hay {hay} y pediste {pedido}.")


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
        widget=_select(),
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


class EntregaPersonaForm(FormConTablaDeCantidades):
    """La entrega: una cantidad por insumo **con saldo** en el edificio, una observación y el identificador del envío.

    La persona viaja en cuatro ocultos y el servicio la vuelve a resolver: lo que llega por acá no se cree.
    """

    OCULTOS = ("dni", "sexo", "nombre", "apellido", "uuid_cliente")

    dni = forms.CharField(required=False, widget=forms.HiddenInput())
    sexo = forms.CharField(required=False, widget=forms.HiddenInput())
    nombre = forms.CharField(required=False, widget=forms.HiddenInput())
    apellido = forms.CharField(required=False, widget=forms.HiddenInput())
    observacion = forms.CharField(
        label="Observación",
        required=False,
        max_length=OBSERVACION_MAXIMA,
        help_text="Opcional. Queda en el movimiento de stock; no pongas datos de salud.",
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
    )


class IngresoForm(FormConTablaDeCantidades):
    """El ingreso manual: de dónde viene, el detalle (obligatorio con «Otro»: lo decide el servicio), el comprobante
    de texto y una cantidad por insumo **activo** del catálogo."""

    TEXTO_SIN_FILA = INSUMO_YA_NO_DISPONIBLE

    origen = forms.ChoiceField(
        label="Origen",
        choices=[("", "Elegí…"), *OperacionStock.Origen.choices],
        error_messages={"required": "Elegí de dónde viene el stock."},
        widget=_select(),
    )
    origen_detalle = forms.CharField(
        label="Detalle del origen",
        required=False,
        max_length=ORIGEN_DETALLE_MAXIMO,
        help_text="Obligatorio si el origen es «Otro».",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    comprobante = forms.CharField(
        label="Comprobante",
        required=False,
        max_length=COMPROBANTE_MAXIMO,
        help_text="Opcional. Número o referencia del remito, la factura o la nota.",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )

    def campos_visibles(self):
        return [self["origen"], self["origen_detalle"], self["comprobante"]]


def valor_de_destino(dispositivo, edificio):
    """El valor del select de destino y del oculto: ``<id de la institución>:<id del edificio>``."""

    return f"{dispositivo.pk}:{edificio.pk}"


class DestinoForm(ErroresDelServicioMixin, forms.Form):
    """A dónde se traspasa: un par institución · edificio **de los que da** ``destinos_de_traspaso`` (el GET no escribe)."""

    destino = forms.ChoiceField(
        label="Destino",
        error_messages={"required": "Elegí a dónde van los insumos.", "invalid_choice": DESTINO_INVALIDO},
        widget=_select(),
    )

    def __init__(self, *args, destinos, **kwargs):
        super().__init__(*args, **kwargs)
        self.destinos = {
            valor_de_destino(dispositivo, edificio): (dispositivo, edificio) for dispositivo, edificio in destinos
        }
        self.fields["destino"].choices = [
            ("", "Elegí…"),
            *(
                (valor, f"{edificio.nombre} · {dispositivo.nombre}")
                for valor, (dispositivo, edificio) in self.destinos.items()
            ),
        ]

    def campos_visibles(self):
        return [self["destino"]]

    def elegido(self):
        """``(Dispositivo, Edificio)`` del destino elegido, o ``None`` si todavía no se eligió uno válido."""

        return self.destinos.get(self.cleaned_data.get("destino")) if self.is_valid() else None


class TraspasoForm(FormConTablaDeCantidades):
    """El traspaso: una cantidad por insumo **con saldo** en el origen, una observación y el destino, que viaja oculto.

    El servicio vuelve a validar el destino (alcance, estado, que sea otro lugar): lo que llega por acá no se cree.
    """

    OCULTOS = ("destino", "uuid_cliente")

    destino = forms.CharField(required=False, widget=forms.HiddenInput())
    observacion = forms.CharField(
        label="Observación",
        required=False,
        max_length=OBSERVACION_MAXIMA,
        help_text="Opcional. Queda en los dos movimientos del traspaso.",
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
    )

    def ids_de_destino(self):
        """``(id de la institución, id del edificio)`` del oculto; ``None`` en lo que no es un número."""

        izquierda, _dos_puntos, derecha = (self.cleaned_data.get("destino") or "").partition(":")
        return tuple(int(parte) if parte.isascii() and parte.isdecimal() else None for parte in (izquierda, derecha))


class AjusteForm(ErroresDelServicioMixin, forms.Form):
    """El ajuste por conteo de **un** insumo (RN-010-12): el motivo del catálogo, lo que se contó y el detalle.

    Viaja en ocultos el insumo, el ``saldo_visto`` —el que había al abrir el modal: si cambió, el servicio contesta
    ``SaldoCambio``— y el ``uuid_cliente``. Es un modal AJAX: los errores salen como ``{campo: [mensajes]}``
    (:meth:`errores`) y los de un oculto suben al error general. El servicio decide el resto (el detalle obligatorio,
    contar lo mismo que hay, un insumo desactivado hacia arriba).
    """

    CAMPOS_ARRIBA = ("item", "saldo_visto", "uuid_cliente")

    item = forms.IntegerField(widget=forms.HiddenInput())
    saldo_visto = forms.IntegerField(
        min_value=0,
        error_messages={"required": SALDO_VISTO_INVALIDO, "invalid": SALDO_VISTO_INVALIDO},
        widget=forms.HiddenInput(),
    )
    uuid_cliente = forms.UUIDField(
        error_messages={"required": FALTA_EL_IDENTIFICADOR, "invalid": FALTA_EL_IDENTIFICADOR},
        widget=forms.HiddenInput(),
    )
    motivo = forms.ChoiceField(
        label="Motivo",
        choices=[("", "Elegí…"), *OperacionStock.MotivoAjuste.choices],
        error_messages={"required": MOTIVO_INVALIDO, "invalid_choice": MOTIVO_INVALIDO},
        widget=_select(),
    )
    cantidad_contada = forms.IntegerField(
        label="Cantidad contada",
        min_value=0,
        max_value=CANTIDAD_MAXIMA,
        help_text="Lo que hay hoy en el edificio, contado. El sistema calcula la diferencia.",
        error_messages={
            "required": CONTADO_INVALIDO,
            "invalid": CONTADO_INVALIDO,
            "min_value": CONTADO_INVALIDO,
            "max_value": CONTADO_INVALIDO,
        },
        widget=numero(0),
    )
    detalle = forms.CharField(
        label="Detalle",
        required=False,
        max_length=OBSERVACION_MAXIMA,
        help_text="Obligatorio con «Otro» y con «Corrección de carga».",
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.setdefault("uuid_cliente", uuid.uuid4())

    def campos_visibles(self):
        return [self["motivo"], self["cantidad_contada"], self["detalle"]]

    def errores(self):
        """Los errores en la forma del modal: ``{campo: [mensajes]}``; los de un oculto, en ``__all__``."""

        resultado = {}
        for campo, mensajes in self.errors.items():
            destino = "__all__" if campo in self.CAMPOS_ARRIBA or campo not in self.fields else campo
            resultado.setdefault(destino, []).extend(mensajes)
        return resultado
