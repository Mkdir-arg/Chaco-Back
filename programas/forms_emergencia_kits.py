"""Formularios de las entregas de kits de Emergencia (E4, E5 y la recepción en el dispositivo).

Aparte de `forms_emergencia.py` para que las dos etapas del módulo no se pisen al crecer.
Validan **la entrada** —que haya un número donde va un número, que la fecha sea una fecha—;
las reglas de la entrega (ítems activos, destino activo, quién puede y en qué estado, el
remito en JPEG) las decide `programas/services/kits.py`, que es lo mismo que usa la app.
"""

import uuid

from django import forms

from programas.forms import INPUT_CLASS
from programas.forms_emergencia import ErroresDelServicioMixin
from programas.models import Dispositivo, Edificio, EntregaKit
from programas.selectors.kits import SOLAPA_ABIERTAS, SOLAPAS, destinos_posibles
from programas.services.kits import (
    CANTIDAD_INVALIDA,
    CANTIDAD_MAXIMA,
    FALTA_EL_MOTIVO,
    FALTA_EL_MOTIVO_DE_LA_DIFERENCIA,
    FALTA_EL_REMITO,
    FALTA_LA_OBSERVACION,
    MOTIVO_DE_LA_DIFERENCIA_LARGO,
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
ELEGI_EL_EDIFICIO_DE_LA_ENTREGA = "Elegí el edificio al que va la entrega."
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


class _DestinoModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.nombre} · {obj.localidad}" if obj.localidad else obj.nombre


class DestinoEntregaForm(forms.Form):
    """A qué dispositivo va la entrega nueva. Es un GET: elegir un destino no escribe nada.

    Los destinos posibles son los de ``selectors.kits.destinos_posibles`` (RN-4.2): un valor que no es uno de ellos
    es un error del campo y la pantalla vuelve a pedirlo.
    """

    dispositivo = _DestinoModelChoiceField(
        label="Destino",
        queryset=Dispositivo.objects.none(),
        required=False,
        empty_label="Elegí el dispositivo",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
        error_messages={"invalid_choice": "Ese destino no está disponible. Elegí otro de la lista."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["dispositivo"].queryset = destinos_posibles()

    def destino(self):
        """El dispositivo elegido, o ``None`` si no eligió ninguno o el valor no sirve."""

        if not self.is_valid():
            return None
        return self.cleaned_data.get("dispositivo")


class ItemsEntregaForm(forms.Form):
    """Las cantidades de la entrega: una por cada ítem del catálogo activo (RN-4.1).

    Un campo `cantidad_<id>` por ítem. Vacío es «este ítem no va»; un cero no es una
    cantidad. ``repone_a`` viaja oculto cuando la entrega repone a otra (HU-4.5).
    """

    oculta_cantidades = False

    repone_a = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)
    #: Nace al abrir el paso 2 y viaja oculto hasta «Crear entrega»: reenviar el mismo armado (volver
    #: atrás en el navegador) devuelve la entrega ya creada en vez de otra (Cambio 535).
    uuid_cliente = forms.UUIDField(required=False, widget=forms.HiddenInput)

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

    def filas_de_cantidad(self, estimado):
        """``[{"item", "campo", "estimado"}]`` para la tabla: ``estimado`` es ``{item_id: ItemDelDispositivo}``."""

        return [
            {"item": item, "campo": self[_campo_de(item.pk)], "estimado": estimado.get(item.pk)}
            for item in self.catalogo
        ]

    def lineas(self, datos=None):
        """``[(TipoKit, cantidad)]`` de los ítems con cantidad: lo que recibe ``crear_entrega``."""

        datos = self.cleaned_data if datos is None else datos
        return [(item, datos[_campo_de(item.pk)]) for item in self.catalogo if datos.get(_campo_de(item.pk))]

    def cantidades_cargadas(self):
        """Los valores válidos de este envío como ``initial`` de otro form (para volver o confirmar)."""

        iniciales = {_campo_de(item.pk): cantidad for item, cantidad in self.lineas()}
        iniciales["repone_a"] = self.cleaned_data.get("repone_a")
        iniciales["uuid_cliente"] = self.cleaned_data.get("uuid_cliente") or uuid.uuid4()
        return iniciales

    @staticmethod
    def iniciales_de(faltantes, repone_a=None):
        """``initial`` a partir de ``[(TipoKit, cantidad)]``: la precarga de «Reponer»."""

        iniciales = {_campo_de(item.pk): cantidad for item, cantidad in faltantes}
        iniciales["repone_a"] = getattr(repone_a, "pk", repone_a)
        return iniciales

    @staticmethod
    def armado_nuevo(iniciales=None):
        """``iniciales`` con un ``uuid_cliente`` nuevo: el del armado que se abre (Cambio 535)."""

        return {**(iniciales or {}), "uuid_cliente": uuid.uuid4()}


class NuevaEntregaForm(ItemsEntregaForm):
    """La entrega nueva en una sola pantalla (Cambio 586): destino, cantidades, salida y nota.

    El destino viaja oculto (``dispositivo``) y la vista lo vuelve a validar contra los destinos posibles. Las
    cantidades son las del catálogo activo; ``salida`` dice si la entrega sale ya (se crea y se marca en camino en una
    sola operación) o queda preparada. **No guarda nada en la sesión**: se crea lo que este envío trae.
    """

    SALE_AHORA = "ahora"
    TODAVIA_NO = "despues"

    dispositivo = forms.IntegerField(required=True, min_value=1, widget=forms.HiddenInput)
    salida = forms.ChoiceField(
        label="¿Sale ahora?",
        choices=[
            (SALE_AHORA, "Sale ahora: queda en camino"),
            (TODAVIA_NO, "Todavía no sale: queda preparada"),
        ],
        initial=SALE_AHORA,
        help_text="Con «Todavía no sale» la marcás en camino después, desde el detalle de la entrega.",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    observacion = forms.CharField(
        label="Observación para el dispositivo",
        required=False,
        help_text="La ve quien recibe la entrega. Opcional.",
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
    )

    def __init__(self, *args, edificios=(), **kwargs):
        super().__init__(*args, **kwargs)
        # Cambio 523: un destino con más de un edificio exige elegir a cuál va la entrega; con uno solo queda
        # fijo y el campo no existe (lo resuelve ``crear_entrega``).
        edificios = list(edificios)
        if edificios:
            self.fields["edificio"] = forms.ModelChoiceField(
                label="Edificio de destino",
                queryset=Edificio.objects.filter(pk__in=[e.pk for e in edificios]).order_by("nombre"),
                empty_label="Elegí el edificio",
                widget=forms.Select(attrs={"class": INPUT_CLASS}),
                error_messages={
                    "required": ELEGI_EL_EDIFICIO_DE_LA_ENTREGA,
                    "invalid_choice": ELEGI_EL_EDIFICIO_DE_LA_ENTREGA,
                },
            )

    def campos_visibles(self):
        return [self[nombre] for nombre in ("edificio", "salida", "observacion") if nombre in self.fields]

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


class AceptarDiferenciaForm(forms.Form):
    """«Aceptar la diferencia» (Cambio 586): cierra la diferencia sin reponerla; el motivo es obligatorio."""

    _MAXIMO = EntregaKit._meta.get_field("cierre_diferencia_motivo").max_length

    motivo = forms.CharField(
        label="Motivo",
        max_length=_MAXIMO,
        help_text="Por qué no se repone lo que faltó. Queda en la traza de la entrega.",
        error_messages={
            "required": FALTA_EL_MOTIVO_DE_LA_DIFERENCIA,
            "max_length": MOTIVO_DE_LA_DIFERENCIA_LARGO.format(maximo=_MAXIMO),
        },
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
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

    Un campo `cantidad_<id del ítem>` por línea, **vacío** (Cambio 586): quien recibe cuenta lo que llegó y lo carga,
    aunque sea cero; no se confirma lo enviado por defecto. El remito en JPEG y de hasta 5 MB lo exige el servicio.
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
                label=linea.nombre_visible,
                min_value=0,
                max_value=CANTIDAD_MAXIMA,
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
