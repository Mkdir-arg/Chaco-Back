"""Formularios de Emergencia.

Aparte de `programas/forms.py` a propósito (igual que `forms_dispositivos.py`): ese archivo
es evidencia del campo canónico (`INPUT_CLASS`), y un formulario nuevo que solo la consume
no mueve esa pieza.

E7 · Configuración: un ModelForm del SLA y un formset del catálogo de kits **sin borrado**
(RN-4.7). Los dos validan la entrada; lo que se guarda y la traza son del servicio
(`programas/services/configuracion_emergencia.py`).

La mesa (abajo): el Formulario 1 de «Nuevo caso», los filtros de la bandeja (E2) y los
formularios chicos de la ficha del caso (E3). Validan **la entrada** —que haya un número
donde va un número, que la opción sea una de la lista—; las reglas del caso (total ≥ 1,
RN-1.3, quién puede y en qué estado) las decide `programas/services/emergencia.py`.
"""

from django import forms
from django.contrib.auth.models import User

from core.dni import MENSAJE_DNI_INVALIDO, dni_valido, normalizar_dni
from core.models import Localidad
from core.validators import validar_foto
from core.widgets import SwitchInput
from programas.forms import INPUT_CLASS
from programas.models import (
    AdjuntoCaso,
    CasoEmergencia,
    ContactoCaso,
    Dispositivo,
    GrupoFamiliar,
    SLAEmergencia,
    TipoKit,
)
from programas.selectors.emergencia import ESTADOS_SLA, SOLAPA_ABIERTOS, SOLAPAS
from programas.selectors.emergencia_mesa import OPERADOR_MIOS, nombre_de, operadores_de_la_mesa
from programas.services.configuracion_emergencia import (
    CAMPOS_SLA,
    CAMPOS_TIPO_KIT,
    MENSAJE_NOMBRE_DUPLICADO,
    nombre_de_kit_en_uso,
    normalizar_nombre,
)
from programas.services.emergencia import MOTIVOS_DE_CIERRE_MANUAL, NECESIDADES

PREFIJO_KITS = "kits"
#: Tope de filas que un POST armado a mano puede pedir que se instancien.
MAXIMO_KITS = 200
#: Tope de plazas que acepta el panel «Derivar»: el del campo `plazas_pedidas` (smallint).
PLAZAS_MAXIMAS = 32767


def _minutos(minimo):
    return forms.NumberInput(attrs={"class": INPUT_CLASS, "min": minimo, "inputmode": "numeric"})


class SLAEmergenciaForm(forms.ModelForm):
    """Los ocho parámetros de la mesa. Los rangos son los validadores del modelo."""

    class Meta:
        model = SLAEmergencia
        fields = list(CAMPOS_SLA)
        widgets = {
            "nombre_evento": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "objetivo_tomar_min": _minutos(1),
            "objetivo_derivar_min": _minutos(1),
            "objetivo_aceptar_min": _minutos(1),
            "objetivo_alojar_min": _minutos(1),
            "vigencia_derivacion_min": _minutos(SLAEmergencia.VIGENCIA_MINIMA_MIN),
            "sin_avance_min": _minutos(0),
            "umbral_por_vencer_pct": forms.NumberInput(
                attrs={
                    "class": INPUT_CLASS,
                    "min": SLAEmergencia.UMBRAL_MINIMO_PCT,
                    "max": SLAEmergencia.UMBRAL_MAXIMO_PCT,
                    "inputmode": "numeric",
                }
            ),
        }

    def campos_del_evento(self):
        return [self["nombre_evento"]]

    def campos_de_objetivos(self):
        return [self[campo] for campo in CAMPOS_SLA if campo.startswith("objetivo_")]

    def campos_de_derivacion(self):
        return [self["vigencia_derivacion_min"], self["sin_avance_min"], self["umbral_por_vencer_pct"]]

    def campos_para_guardar(self):
        """Lo que recibe ``guardar_sla``: los campos del SLA ya validados."""
        return {campo: self.cleaned_data[campo] for campo in CAMPOS_SLA}


class TipoKitForm(forms.ModelForm):
    """Una fila del catálogo. La fila vacía del final es la de «agregar ítem»."""

    class Meta:
        model = TipoKit
        fields = list(CAMPOS_TIPO_KIT)
        widgets = {
            "nombre": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "unidad": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "kit, unidad, bidón…"}),
            "orden": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 0, "inputmode": "numeric"}),
            "activo": SwitchInput(),
        }

    def clean_nombre(self):
        nombre = normalizar_nombre(self.cleaned_data.get("nombre"))
        if nombre and nombre_de_kit_en_uso(nombre, excluir_pk=self.instance.pk):
            raise forms.ValidationError(MENSAJE_NOMBRE_DUPLICADO)
        return nombre

    def validate_unique(self):
        """El duplicado ya lo dijo ``clean_nombre``, sin distinguir mayúsculas: no se repite el error."""

    @property
    def es_nuevo(self):
        return self.instance.pk is None

    def campos_para_guardar(self):
        """Lo que recibe el servicio: los campos del ítem ya validados."""
        return {campo: self.cleaned_data[campo] for campo in CAMPOS_TIPO_KIT}


class _IdDeFila(forms.ModelChoiceField):
    """El ``id`` oculto de cada fila, resuelto contra el catálogo que el formset ya leyó.

    El campo de fábrica hace un ``queryset.get(pk=…)`` **por fila** al validar: con veinte
    ítems son veinte consultas para confirmar lo que el formset trajo en una.
    """

    def __init__(self, *args, buscar, **kwargs):
        super().__init__(*args, **kwargs)
        self._buscar = buscar

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            objeto = self._buscar(value)
        except (TypeError, ValueError, forms.ValidationError):
            objeto = None
        if objeto is None:
            raise forms.ValidationError(self.error_messages["invalid_choice"], code="invalid_choice")
        return objeto


class BaseTipoKitFormSet(forms.BaseModelFormSet):
    """Catálogo de kits: se edita y se agrega, **no se borra** (``can_delete=False``)."""

    def add_fields(self, form, index):
        super().add_fields(form, index)
        de_fabrica = form.fields[self._pk_field.name]
        form.fields[self._pk_field.name] = _IdDeFila(
            de_fabrica.queryset,
            buscar=self._fila_por_id,
            initial=de_fabrica.initial,
            required=False,
            widget=forms.HiddenInput,
        )

    def _fila_por_id(self, valor):
        """El ítem con ese id entre los que el formset ya trajo (el POST lo manda como texto)."""
        return self._existing_object(self.model._meta.pk.to_python(valor))

    def clean(self):
        super().clean()
        vistos = set()
        for form in self.forms:
            if form.errors or not form.has_changed() and form.es_nuevo:
                continue
            nombre = (form.cleaned_data.get("nombre") or "").casefold()
            if not nombre:
                continue
            if nombre in vistos:
                form.add_error("nombre", MENSAJE_NOMBRE_DUPLICADO)
            vistos.add(nombre)

    def validate_unique(self):
        """Los repetidos entre filas los marca ``clean`` en su fila, no como error del conjunto."""

    def filas_existentes(self):
        return [form for form in self.forms if not form.es_nuevo]

    def filas_nuevas(self):
        return [form for form in self.forms if form.es_nuevo]

    def cambios_para_guardar(self):
        """``[(tipo, campos)]`` para ``guardar_configuracion``: solo las filas que cambiaron.

        Una fila nueva sin tocar no es un ítem: es el lugar para agregar uno.
        """
        return [
            (None if form.es_nuevo else form.instance, form.campos_para_guardar())
            for form in self.forms
            if form.has_changed()
        ]


TipoKitFormSet = forms.modelformset_factory(
    TipoKit,
    form=TipoKitForm,
    formset=BaseTipoKitFormSet,
    extra=1,
    can_delete=False,
    max_num=MAXIMO_KITS,
    absolute_max=MAXIMO_KITS,
)


# ---------------------------------------------------------------------------
# La mesa: «Nuevo caso» (Formulario 1), bandeja (E2) y ficha del caso (E3)
# ---------------------------------------------------------------------------


def _cantidad(etiqueta, ayuda=""):
    return forms.IntegerField(
        label=etiqueta,
        required=False,
        min_value=0,
        initial=0,
        help_text=ayuda,
        widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 0, "inputmode": "numeric"}),
    )


def _foto(etiqueta):
    return forms.FileField(
        label=etiqueta,
        required=False,
        validators=[validar_foto],
        widget=forms.ClearableFileInput(attrs={"class": INPUT_CLASS, "accept": ".jpg,.jpeg,.png"}),
    )


class ErroresDelServicioMixin:
    """Lleva cada rechazo de un servicio (``ValidationError``) a su campo; lo que no es de un campo, arriba.

    Los servicios de Emergencia validan las reglas y devuelven el error por clave; la vista
    no lo reinterpreta. ``CAMPOS_ARRIBA`` son claves que **son** campos del form pero cuyo
    error se lee mejor arriba (la cama de la ficha, que viaja oculta).
    """

    CAMPOS_ARRIBA = ()

    def agregar_errores_del_servicio(self, error):
        if not hasattr(error, "error_dict"):
            self.add_error(None, error)
            return
        for clave, errores in error.error_dict.items():
            self.add_error(clave if clave in self.fields and clave not in self.CAMPOS_ARRIBA else None, errores)


class NuevoCasoMesaForm(ErroresDelServicioMixin, forms.Form):
    """El Formulario 1 cargado desde la mesa (HU-1.4): lo que llega por teléfono.

    Los cuatro bloques son los cuatro pasos del formulario del agente (01 §4). No lleva GPS
    —quien atiende el teléfono no está en el lugar— y por eso acá la **localidad es
    obligatoria**: sin posición, es lo único que ubica a la familia además de la dirección.
    Lo que rechace ``crear_caso`` vuelve a su campo con :meth:`agregar_errores_del_servicio`.
    """

    traslado = forms.ChoiceField(
        label="Fuerza que traslada",
        choices=[("", "Elegí una opción"), *GrupoFamiliar.Traslado.choices],
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    traslado_otro = forms.CharField(
        label="Otra fuerza",
        required=False,
        max_length=120,
        help_text="Solo si elegiste «Otra».",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    dni = forms.CharField(
        label="DNI del responsable",
        max_length=12,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "inputmode": "numeric", "autocomplete": "off"}),
    )
    nombre = forms.CharField(
        label="Nombre",
        required=False,
        max_length=120,
        help_text="Solo si la persona todavía no está en el legajo.",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    apellido = forms.CharField(
        label="Apellido",
        required=False,
        max_length=120,
        help_text="Solo si la persona todavía no está en el legajo.",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    telefono = forms.CharField(
        label="Teléfono de contacto",
        required=False,
        max_length=40,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "inputmode": "tel"}),
    )

    menores_f = _cantidad("Menores de 16 · femenino")
    menores_m = _cantidad("Menores de 16 · masculino")
    adultos_f = _cantidad("Adultos (16 a 59) · femenino")
    adultos_m = _cantidad("Adultos (16 a 59) · masculino")
    mayores_f = _cantidad("Mayores (60+) · femenino")
    mayores_m = _cantidad("Mayores (60+) · masculino")

    dependientes = _cantidad("Personas con dependencia", "Movilidad reducida o discapacidad.")
    mayores_dependientes = _cantidad("Mayores dependientes")
    lactantes = _cantidad("Lactantes")
    embarazo = forms.BooleanField(label="Embarazo", required=False, widget=SwitchInput())
    electrodependiente = forms.BooleanField(label="Electrodependiente", required=False, widget=SwitchInput())
    medicacion_critica = forms.BooleanField(label="Medicación crítica", required=False, widget=SwitchInput())
    mascotas = forms.BooleanField(label="Mascotas", required=False, widget=SwitchInput())

    direccion = forms.CharField(
        label="Dirección",
        max_length=240,
        help_text="Calle y número, o una referencia («frente a la capilla»).",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    localidad = forms.ModelChoiceField(
        label="Localidad",
        queryset=Localidad.objects.order_by("nombre"),
        empty_label="Elegí una localidad",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    foto_vivienda = _foto("Foto de la vivienda")
    foto_acceso = _foto("Foto del acceso")
    observaciones = forms.CharField(
        label="Observaciones",
        required=False,
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
    )

    CAMPOS_DE_TRASLADO = ("traslado", "traslado_otro", "dni", "telefono", "nombre", "apellido")
    CAMPOS_DE_ASISTENCIA = ("dependientes", "mayores_dependientes", "lactantes")
    CAMPOS_DE_UBICACION = ("direccion", "localidad", "foto_vivienda", "foto_acceso")
    FOTOS = {"foto_vivienda": AdjuntoCaso.Tipo.VIVIENDA, "foto_acceso": AdjuntoCaso.Tipo.ACCESO}

    def clean_traslado_otro(self):
        otro = (self.cleaned_data.get("traslado_otro") or "").strip()
        if self.cleaned_data.get("traslado") == GrupoFamiliar.Traslado.OTRA and not otro:
            raise forms.ValidationError("Indicá qué fuerza traslada.")
        return otro

    def clean_dni(self):
        dni = normalizar_dni(self.cleaned_data.get("dni"))
        if not dni_valido(dni):
            raise forms.ValidationError(MENSAJE_DNI_INVALIDO)
        return dni

    def _campos(self, nombres):
        return [self[nombre] for nombre in nombres]

    def campos_de_traslado(self):
        return self._campos(self.CAMPOS_DE_TRASLADO)

    def campos_de_personas(self):
        return self._campos(GrupoFamiliar.CANTIDADES)

    def campos_de_asistencia(self):
        return self._campos(self.CAMPOS_DE_ASISTENCIA)

    def campos_de_necesidades(self):
        return self._campos(NECESIDADES)

    def campos_de_ubicacion(self):
        return self._campos(self.CAMPOS_DE_UBICACION)

    def campos_de_observaciones(self):
        return [self["observaciones"]]

    def datos_formulario1(self):
        """El dict que recibe ``crear_caso``, con las claves que documenta ese servicio."""

        datos = {
            campo: valor
            for campo, valor in self.cleaned_data.items()
            if campo not in self.FOTOS and valor not in (None, "")
        }
        datos["fotos"] = {
            tipo: self.cleaned_data[campo] for campo, tipo in self.FOTOS.items() if self.cleaned_data.get(campo)
        }
        return datos


# Lo que dice cada formulario chico de la ficha cuando llega algo que no puede ser. Van al
# aviso de la pantalla, así que dicen qué pasó y qué hacer (RU-20), no «Este campo es requerido».
CANAL_INVALIDO = "Elegí el canal del contacto de la lista."
RESULTADO_INVALIDO = "Elegí el resultado del contacto de la lista."
ELEGI_EL_MOTIVO = "Elegí el motivo del cierre."
ELEGI_LA_PRIORIDAD = "Elegí una prioridad: alta, media o baja."
ELEGI_UN_OPERADOR = "Elegí a alguien que opere la mesa de Emergencia."
ELEGI_UN_DISPOSITIVO = "Ese dispositivo ya no está en la lista. Recargá la ficha y elegí otro."
PEDI_UNA_PLAZA = "Pedí al menos una plaza."
MOTIVO_DE_CANCELACION = "Indicá por qué se cancela la derivación."


class ContactoCasoForm(forms.ModelForm):
    """Un contacto con la familia (RN-2.12): canal, resultado y observación."""

    class Meta:
        model = ContactoCaso
        fields = ["canal", "resultado", "observacion"]
        error_messages = {
            "canal": {"required": "Elegí por qué canal fue el contacto.", "invalid_choice": CANAL_INVALIDO},
            "resultado": {"required": "Elegí cómo resultó el contacto.", "invalid_choice": RESULTADO_INVALIDO},
        }
        widgets = {
            "canal": forms.Select(attrs={"class": INPUT_CLASS}),
            "resultado": forms.Select(attrs={"class": INPUT_CLASS}),
            "observacion": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 2}),
        }


class CierreCasoForm(forms.Form):
    """Cerrar sin alojamiento (E3-modal): el motivo sale de la lista y es obligatorio."""

    motivo = forms.ChoiceField(
        label="Motivo",
        choices=[("", "Elegí el motivo"), *[(motivo.value, motivo.label) for motivo in MOTIVOS_DE_CIERRE_MANUAL]],
        error_messages={"required": ELEGI_EL_MOTIVO, "invalid_choice": ELEGI_EL_MOTIVO},
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    observacion = forms.CharField(
        label="Observación",
        required=False,
        help_text="Obligatoria si el motivo es «Otro».",
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
    )


class CancelarDerivacionForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo",
        max_length=200,
        help_text="Queda en la traza del caso.",
        error_messages={
            "required": MOTIVO_DE_CANCELACION,
            "max_length": "El motivo no puede tener más de 200 caracteres.",
        },
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3, "maxlength": 200}),
    )


class PrioridadCasoForm(forms.Form):
    prioridad = forms.ChoiceField(
        label="Prioridad",
        choices=CasoEmergencia.Prioridad.choices,
        help_text="Solo cambia el orden de la bandeja.",
        error_messages={"required": ELEGI_LA_PRIORIDAD, "invalid_choice": ELEGI_LA_PRIORIDAD},
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )


class _OperadorField(forms.ModelChoiceField):
    def label_from_instance(self, usuario):
        return nombre_de(usuario)


class ReasignarCasoForm(forms.Form):
    """A quién pasa el caso. La lista es la de quienes trabajan en la mesa; ``reasignar_caso`` lo revalida."""

    operador = _OperadorField(
        label="Pasar el caso a",
        queryset=User.objects.none(),
        empty_label="Elegí una persona de la mesa",
        error_messages={"required": ELEGI_UN_OPERADOR, "invalid_choice": ELEGI_UN_OPERADOR},
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["operador"].queryset = operadores_de_la_mesa()


class DerivarCasoForm(forms.Form):
    """A qué dispositivo y cuántas plazas. ``confirmar_faltantes`` es el «sí» a derivar con menos (RN-2.5)."""

    dispositivo = forms.ModelChoiceField(
        queryset=Dispositivo.objects.select_related("tipo"),
        widget=forms.HiddenInput,
        error_messages={"required": ELEGI_UN_DISPOSITIVO, "invalid_choice": ELEGI_UN_DISPOSITIVO},
    )
    plazas = forms.IntegerField(
        label="Plazas a reservar",
        min_value=1,
        max_value=PLAZAS_MAXIMAS,
        error_messages={"required": PEDI_UNA_PLAZA, "invalid": PEDI_UNA_PLAZA, "min_value": PEDI_UNA_PLAZA},
        widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 1, "inputmode": "numeric"}),
    )
    confirmar_faltantes = forms.BooleanField(required=False, widget=forms.HiddenInput)


class PanelDerivarForm(forms.Form):
    """Lo que la ficha lee de la URL para armar el panel «Derivar». Es un GET: nada de esto escribe.

    ``derivar`` (el dispositivo que se eligió en una tarjeta) viaja en la misma URL pero no es
    un control del panel: va oculto solo para leerlo, y ``campos_visibles`` no lo incluye.
    """

    plazas = forms.IntegerField(
        label="Plazas a reservar",
        required=False,
        min_value=1,
        max_value=PLAZAS_MAXIMAS,
        widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 1, "inputmode": "numeric"}),
    )
    q = forms.CharField(
        label="Buscar dispositivo",
        required=False,
        max_length=80,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    localidad_dispositivo = forms.CharField(
        label="Localidad del dispositivo",
        required=False,
        max_length=120,
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    derivar = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)

    CAMPOS_VISIBLES = ("plazas", "q", "localidad_dispositivo")

    def valor(self, campo):
        """El valor limpio de ``campo``, o ``None`` si no vino o no era válido."""

        self.is_valid()
        return self.cleaned_data.get(campo) or None

    def ofrecer_localidades(self, localidades):
        self.fields["localidad_dispositivo"].widget.choices = [
            ("", "Todas"),
            *[(nombre, nombre) for nombre in localidades],
        ]

    def campos_visibles(self):
        return [self[campo] for campo in self.CAMPOS_VISIBLES]


class FiltrosBandejaForm(forms.Form):
    """Los filtros de E2. Un valor que no es de la lista se ignora: la bandeja no rebota por una URL vieja."""

    solapa = forms.ChoiceField(required=False, choices=[(solapa, solapa) for solapa in SOLAPAS])
    texto = forms.CharField(required=False, max_length=80)
    estado = forms.ChoiceField(required=False, choices=CasoEmergencia.Estado.choices)
    prioridad = forms.ChoiceField(required=False, choices=CasoEmergencia.Prioridad.choices)
    localidad = forms.IntegerField(required=False, min_value=1)
    operador = forms.CharField(required=False, max_length=12)
    sla = forms.ChoiceField(required=False, choices=[(estado, estado) for estado in ESTADOS_SLA])

    CAMPOS_DEL_SELECTOR = ("texto", "estado", "prioridad", "localidad", "sla")

    def limpios(self):
        """Los valores válidos que llegaron, sin los vacíos."""

        self.is_valid()
        return {campo: valor for campo, valor in self.cleaned_data.items() if valor not in (None, "")}

    def filtros(self, usuario):
        """El dict que recibe ``selectors.emergencia.bandeja``; por omisión, la solapa «Abiertos»."""

        limpios = self.limpios()
        filtros = {campo: limpios[campo] for campo in self.CAMPOS_DEL_SELECTOR if campo in limpios}
        filtros["solapa"] = limpios.get("solapa") or SOLAPA_ABIERTOS
        operador = limpios.get("operador", "")
        if operador == OPERADOR_MIOS:
            filtros["tomado_por"] = usuario.pk
        elif operador.isdecimal():
            filtros["tomado_por"] = int(operador)
        return filtros
