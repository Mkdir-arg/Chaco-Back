"""Formularios de las entregas de kits de Emergencia (E4, E5 y la recepción en el dispositivo).

Aparte de `forms_emergencia.py` para que las dos etapas del módulo no se pisen al crecer.
Validan **la entrada** —que haya un número donde va un número, que la fecha sea una fecha—;
las reglas de la entrega (ítems activos, destino activo, quién puede y en qué estado, el
remito en JPEG) las decide `programas/services/kits.py`, que es lo mismo que usa la app.
"""

from django import forms

from programas.forms import INPUT_CLASS
from programas.forms_emergencia import ErroresDelServicioMixin
from programas.models import EntregaKit
from programas.selectors.kits import SOLAPA_ABIERTAS, SOLAPAS
from programas.services.kits import (
    CANTIDAD_INVALIDA,
    CANTIDAD_MAXIMA,
    FALTA_EL_MOTIVO,
    FALTA_EL_REMITO,
    FALTA_LA_OBSERVACION,
    MOTIVO_LARGO,
    MOTIVO_MAXIMO,
    SIN_LINEAS,
    TRANSPORTE_LARGO,
    TRANSPORTE_MAXIMO,
)

#: Prefijo de los campos de cantidad: `cantidad_<id del ítem>`.
PREFIJO_CANTIDAD = "cantidad_"
FORMATO_FECHA_HORA = "%Y-%m-%dT%H:%M"
ELEGI_UNA_HORA_VALIDA = "Indicá la fecha y la hora de salida, o dejala vacía para usar la de ahora."
CANTIDAD_RECIBIDA_REQUERIDA = "Indicá cuánto llegó, aunque sea cero."
ITEM_FUERA_DEL_CATALOGO = "Algún ítem ya no está en el catálogo activo. Volvé al paso anterior y revisá las cantidades."
CANTIDAD_RECIBIDA_INVALIDA = "Tiene que ser un número entero, cero o más."


def _numero(minimo):
    return forms.NumberInput(attrs={"class": INPUT_CLASS, "min": minimo, "inputmode": "numeric"})


def _campo_de(item_id):
    return f"{PREFIJO_CANTIDAD}{item_id}"


class FiltrosEntregasForm(forms.Form):
    """Los filtros de E4. Un valor que no es de la lista se ignora: el listado no rebota por una URL vieja."""

    solapa = forms.ChoiceField(required=False, choices=SOLAPAS)
    estado = forms.ChoiceField(required=False, choices=EntregaKit.Estado.choices)
    dispositivo = forms.IntegerField(required=False, min_value=1)
    localidad = forms.CharField(required=False, max_length=120)
    fecha = forms.DateField(required=False)

    CAMPOS_DEL_SELECTOR = ("estado", "dispositivo", "localidad", "fecha")

    def limpios(self):
        """Los valores válidos que llegaron, sin los vacíos."""

        self.is_valid()
        return {campo: valor for campo, valor in self.cleaned_data.items() if valor not in (None, "")}

    def filtros(self):
        """El dict que recibe ``selectors.kits.listado_de_entregas``; por omisión, la solapa «Abiertas»."""

        limpios = self.limpios()
        filtros = {campo: limpios[campo] for campo in self.CAMPOS_DEL_SELECTOR if campo in limpios}
        filtros["solapa"] = limpios.get("solapa") or SOLAPA_ABIERTAS
        return filtros


class BuscarDestinoForm(forms.Form):
    """El buscador del paso 1 del asistente. Es un GET: no escribe nada."""

    q = forms.CharField(required=False, max_length=80)

    def texto(self):
        self.is_valid()
        return self.cleaned_data.get("q") or ""


class ItemsEntregaForm(forms.Form):
    """Paso 2 del asistente: una cantidad por cada ítem del catálogo activo (RN-4.1).

    Un campo `cantidad_<id>` por ítem. Vacío es «este ítem no va»; un cero no es una
    cantidad. ``repone_a`` viaja oculto cuando la entrega repone a otra (HU-4.5).
    """

    oculta_cantidades = False

    repone_a = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)

    def __init__(self, *args, catalogo, **kwargs):
        super().__init__(*args, **kwargs)
        self.catalogo = list(catalogo)
        for item in self.catalogo:
            self.fields[_campo_de(item.pk)] = forms.IntegerField(
                label=item.nombre,
                required=False,
                min_value=1,
                max_value=CANTIDAD_MAXIMA,
                help_text=f"En {item.unidad}.",
                error_messages={
                    "invalid": CANTIDAD_INVALIDA,
                    "min_value": CANTIDAD_INVALIDA,
                    "max_value": CANTIDAD_INVALIDA,
                },
                widget=forms.HiddenInput if self.oculta_cantidades else _numero(1),
            )

    def clean(self):
        limpio = super().clean()
        # Una cantidad de un ítem que ya no está en el catálogo activo (se desactivó entre un
        # paso y el otro) no se descarta en silencio: la entrega saldría distinta de lo mostrado.
        if any(
            clave.startswith(PREFIJO_CANTIDAD) and clave not in self.fields and str(valor).strip()
            for clave, valor in self.data.items()
        ):
            raise forms.ValidationError(ITEM_FUERA_DEL_CATALOGO)
        # Si alguna cantidad ya falló, ese es el error: no se le suma «no hay ítems».
        if not self.errors and not self.lineas(limpio):
            raise forms.ValidationError(SIN_LINEAS)
        return limpio

    def campos_de_cantidad(self):
        return [self[_campo_de(item.pk)] for item in self.catalogo]

    def lineas(self, datos=None):
        """``[(TipoKit, cantidad)]`` de los ítems con cantidad: lo que recibe ``crear_entrega``."""

        datos = self.cleaned_data if datos is None else datos
        return [(item, datos[_campo_de(item.pk)]) for item in self.catalogo if datos.get(_campo_de(item.pk))]

    def cantidades_cargadas(self):
        """Los valores válidos de este envío como ``initial`` de otro form (para volver o confirmar)."""

        iniciales = {_campo_de(item.pk): cantidad for item, cantidad in self.lineas()}
        iniciales["repone_a"] = self.cleaned_data.get("repone_a")
        return iniciales

    @staticmethod
    def iniciales_de(faltantes, repone_a=None):
        """``initial`` a partir de ``[(TipoKit, cantidad)]``: la precarga de «Reponer»."""

        iniciales = {_campo_de(item.pk): cantidad for item, cantidad in faltantes}
        iniciales["repone_a"] = getattr(repone_a, "pk", repone_a)
        return iniciales


class ConfirmarEntregaForm(ItemsEntregaForm):
    """Paso 3: lo que el paso 2 mostró viaja oculto, y acá se suma la nota para el dispositivo.

    El asistente **no guarda nada en la sesión**: lo que se confirma es lo que esta pantalla
    trae en sus ocultos, que es lo que mostró en el resumen.
    """

    oculta_cantidades = True

    observacion = forms.CharField(
        label="Observación para el dispositivo",
        required=False,
        help_text="La ve quien recibe la entrega. Opcional.",
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
    )

    def campos_visibles(self):
        return [self["observacion"]]

    def agregar_errores_del_servicio(self, error):
        """Lo que rechace ``crear_entrega`` va arriba del formulario: ninguno es de un campo visible."""

        self.add_error(None, error.messages)


class EnCaminoForm(forms.Form):
    """Marcar en camino: transporte y hora de salida, los dos opcionales (HU-4.2)."""

    transporte = forms.CharField(
        label="Transporte",
        required=False,
        max_length=TRANSPORTE_MAXIMO,
        help_text="Quién la lleva, el vehículo o la patente. Opcional.",
        error_messages={"max_length": TRANSPORTE_LARGO},
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "maxlength": TRANSPORTE_MAXIMO}),
    )
    hora = forms.DateTimeField(
        label="Hora de salida",
        required=False,
        input_formats=[FORMATO_FECHA_HORA, "%Y-%m-%dT%H:%M:%S"],
        help_text="Si la dejás vacía se usa la de este momento.",
        error_messages={"invalid": ELEGI_UNA_HORA_VALIDA},
        widget=forms.DateTimeInput(attrs={"class": INPUT_CLASS, "type": "datetime-local"}, format=FORMATO_FECHA_HORA),
    )


class CancelarEntregaForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo",
        max_length=MOTIVO_MAXIMO,
        help_text="Queda en la traza de la entrega y lo ve el dispositivo si intenta recibirla.",
        error_messages={"required": FALTA_EL_MOTIVO, "max_length": MOTIVO_LARGO},
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3, "maxlength": MOTIVO_MAXIMO}),
    )


class ObservarEntregaForm(forms.Form):
    """RN-4.5: la única corrección después de la recepción es esta observación de la mesa."""

    texto = forms.CharField(
        label="Observación de la mesa",
        help_text="No cambia las cantidades recibidas. Queda en la traza.",
        error_messages={"required": FALTA_LA_OBSERVACION},
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
    )


class RecepcionKitForm(ErroresDelServicioMixin, forms.Form):
    """La recepción en el dispositivo: lo que llegó de cada ítem, el remito y una observación (HU-4.3).

    Un campo `cantidad_<id del ítem>` por línea, precargado con lo enviado: se corrige solo
    lo distinto. El remito en JPEG y de hasta 5 MB lo exige el servicio.
    """

    remito = forms.FileField(
        label="Foto del remito",
        help_text="En JPEG, de hasta 5 MB.",
        error_messages={"required": FALTA_EL_REMITO},
        widget=forms.ClearableFileInput(attrs={"class": INPUT_CLASS, "accept": ".jpg,.jpeg"}),
    )
    observacion = forms.CharField(
        label="Observación",
        required=False,
        help_text="Lo que la mesa tiene que saber de esta entrega. Opcional.",
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
    )

    def __init__(self, *args, lineas, **kwargs):
        super().__init__(*args, **kwargs)
        self.lineas = list(lineas)
        cantidades = {}
        for linea in self.lineas:
            cantidades[_campo_de(linea.item_id)] = forms.IntegerField(
                label=linea.item.nombre,
                min_value=0,
                max_value=CANTIDAD_MAXIMA,
                initial=linea.cantidad_enviada,
                help_text=f"Se enviaron {linea.cantidad_enviada} · en {linea.unidad}.",
                error_messages={
                    "required": CANTIDAD_RECIBIDA_REQUERIDA,
                    "invalid": CANTIDAD_RECIBIDA_INVALIDA,
                    "min_value": CANTIDAD_RECIBIDA_INVALIDA,
                    "max_value": CANTIDAD_RECIBIDA_INVALIDA,
                },
                widget=_numero(0),
            )
        # Las cantidades primero: es lo que la guardia revisa contra el remito.
        self.fields = {**cantidades, **self.fields}

    def campos_de_cantidad(self):
        return [self[_campo_de(linea.item_id)] for linea in self.lineas]

    def campos_del_remito(self):
        return [self["remito"], self["observacion"]]

    def cantidades(self):
        """``{item_id: cantidad}``: lo que recibe ``recibir_entrega``."""

        return {linea.item_id: self.cleaned_data[_campo_de(linea.item_id)] for linea in self.lineas}
