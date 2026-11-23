"""Formularios de Emergencia.

Aparte de `programas/forms.py` a propósito (igual que `forms_dispositivos.py`): ese archivo
es evidencia del campo canónico (`INPUT_CLASS`), y un formulario nuevo que solo la consume
no mueve esa pieza.

Configuración (Cambio 578): un ModelForm del SLA («Plazos de atención») y un ModelForm de un
insumo del catálogo de kits, que **nunca se borra** (RN-4.7). Los dos validan la entrada; lo que se guarda y la traza son del servicio
(`programas/services/configuracion_emergencia.py`).

La mesa (abajo): el Formulario 1 de «Nuevo caso», los filtros de la bandeja (E2) y los
formularios chicos de la ficha del caso (E3). Validan **la entrada** —que haya un número
donde va un número, que la opción sea una de la lista—; las reglas del caso (total ≥ 1,
RN-1.3, quién puede y en qué estado) las decide `programas/services/emergencia.py`.
"""

from django import forms
from django.contrib.auth.models import User

from core.coordenadas import VALIDADORES_LATITUD, VALIDADORES_LONGITUD, exigir_par
from core.dni import MENSAJE_DNI_INVALIDO, dni_valido, normalizar_dni
from core.forms_sugerencias import attrs_sugerencias
from core.selectors.geografia import localidades_operativas
from core.validators import validar_foto
from core.widgets import SwitchInput
from programas.forms import INPUT_CLASS
from programas.models import (
    AdjuntoCaso,
    CasoEmergencia,
    ContactoCaso,
    Dispositivo,
    Edificio,
    GrupoFamiliar,
    SLAEmergencia,
    TipoKit,
)
from programas.selectors.emergencia import ESTADOS_SLA, SOLAPA_ABIERTOS, SOLAPA_SIN_TOMAR, SOLAPAS
from programas.selectors.emergencia_mesa import OPERADOR_MIOS, nombre_de, operadores_de_la_mesa
from programas.services.configuracion_emergencia import (
    CAMPOS_SLA,
    MENSAJE_NOMBRE_DUPLICADO,
    nombre_de_kit_en_uso,
    normalizar_nombre,
)
from programas.services.emergencia import MOTIVOS_DE_CIERRE_MANUAL, NECESIDADES
from programas.services.emergencia_alta import CasoAbiertoDeLaFamilia, DniRegistrado

#: Tope de plazas que acepta el panel «Derivar»: el del campo `plazas_pedidas` (smallint).
PLAZAS_MAXIMAS = 32767


def _minutos(minimo):
    return forms.NumberInput(attrs={"class": INPUT_CLASS, "min": minimo, "inputmode": "numeric"})


class SLAEmergenciaForm(forms.ModelForm):
    """Los parámetros de la mesa y el inicio del evento (``CAMPOS_SLA``). Los rangos son los validadores del modelo."""

    class Meta:
        model = SLAEmergencia
        fields = list(CAMPOS_SLA)
        # Lo que lee quien configura, dicho como lo hace el sistema (selectors/emergencia.py y
        # services/emergencia.py): qué tramo mide cada plazo y a qué casos alcanza cada aviso.
        labels = {
            "nombre_evento": "Nombre del evento",
            "inicio_evento": "Inicio del evento",
            "objetivo_tomar_min": "Tomar el caso",
            "objetivo_derivar_min": "Derivarlo",
            "objetivo_aceptar_min": "Que la institución responda",
            "objetivo_alojar_min": "Alojar a la familia",
            "umbral_por_vencer_pct": "Avisar cuando falta poco (% del plazo)",
            "sin_avance_min": "Devolver el caso a la lista (minutos sin novedad)",
            "vigencia_derivacion_min": "La derivación vence a los (minutos)",
            "ingreso_sin_movimiento_h": "Avisar ingreso sin movimiento (horas)",
        }
        help_texts = {
            "nombre_evento": "Es el título de Situación y del Tablero.",
            "inicio_evento": (
                "Desde este momento se cuenta lo que recibió cada institución. "
                "Sin fecha, Situación no puede estimar qué falta."
            ),
            "objetivo_tomar_min": "Desde que llega hasta que alguien de la mesa lo toma.",
            "objetivo_derivar_min": "Desde que se toma hasta que se deriva a una institución.",
            "objetivo_aceptar_min": "Desde la derivación hasta que la institución la acepta.",
            "objetivo_alojar_min": "Desde que la institución acepta hasta que la familia queda alojada.",
            "umbral_por_vencer_pct": "Entre 50 y 95. El caso se marca por vencer al llegar a este porcentaje de su plazo.",
            "sin_avance_min": (
                "Si quien tomó el caso no hace nada en este tiempo, vuelve a la lista sin responsable. "
                "Vale para los casos abiertos. Con 0 no vuelve solo."
            ),
            "vigencia_derivacion_min": (
                "Si la institución no responde, la derivación vence y el caso vuelve a la mesa. "
                "Mínimo 30. Vale para las derivaciones nuevas."
            ),
            "ingreso_sin_movimiento_h": (
                "La institución aceptó y nadie confirmó a las personas: la mesa lo ve marcado. "
                "No vence nada. Con 0 no se avisa."
            ),
        }
        widgets = {
            "nombre_evento": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "objetivo_tomar_min": _minutos(1),
            "objetivo_derivar_min": _minutos(1),
            "objetivo_aceptar_min": _minutos(1),
            "objetivo_alojar_min": _minutos(1),
            "vigencia_derivacion_min": _minutos(SLAEmergencia.VIGENCIA_MINIMA_MIN),
            "sin_avance_min": _minutos(0),
            "ingreso_sin_movimiento_h": _minutos(0),
            "umbral_por_vencer_pct": forms.NumberInput(
                attrs={
                    "class": INPUT_CLASS,
                    "min": SLAEmergencia.UMBRAL_MINIMO_PCT,
                    "max": SLAEmergencia.UMBRAL_MAXIMO_PCT,
                    "inputmode": "numeric",
                }
            ),
            "inicio_evento": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"class": INPUT_CLASS, "type": "datetime-local"}
            ),
        }

    def campos_del_evento(self):
        return [self["nombre_evento"], self["inicio_evento"]]

    def campos_de_objetivos(self):
        return [self[campo] for campo in CAMPOS_SLA if campo.startswith("objetivo_")]

    def campos_de_avisos(self):
        return [
            self["umbral_por_vencer_pct"],
            self["sin_avance_min"],
            self["vigencia_derivacion_min"],
            self["ingreso_sin_movimiento_h"],
        ]

    def campos_para_guardar(self):
        """Lo que recibe ``guardar_sla``: los campos del SLA ya validados."""
        return {campo: self.cleaned_data[campo] for campo in CAMPOS_SLA}


CAMPOS_DE_INSUMO = ("nombre", "unidad", "regla_modo", "regla_cantidad", "regla_por", "regla_cada_dias")


class InsumoForm(forms.ModelForm):
    """Un insumo del catálogo: alta y edición en el mismo modal (Cambio 578).

    Sin formset ni fila vacía: cada guardado es un insumo. Activar y desactivar no pasa por
    acá (son sus propias acciones con confirmación) y el orden de las entregas es el del
    catálogo (``orden``, que acá no se toca).

    ``en_uso`` es la regla 1: con líneas de entrega, el nombre y la unidad se muestran de solo
    lectura. Un campo ``disabled`` ignora lo que llegue por POST y devuelve el valor guardado,
    así que el servicio nunca ve un cambio; además el servicio lo vuelve a exigir.
    """

    #: Cómo se llama cada modo de la regla para quien carga el insumo (los del modelo son los de la traza).
    OPCIONES_DE_CONSUMO = (
        (TipoKit.ModoRegla.SIN_REGLA, "No lo estimo"),
        (TipoKit.ModoRegla.DOTACION, "Se entrega una sola vez"),
        (TipoKit.ModoRegla.REPOSICION, "Se repone cada cierto tiempo"),
    )

    class Meta:
        model = TipoKit
        fields = list(CAMPOS_DE_INSUMO)
        widgets = {
            "nombre": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "unidad": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "regla_modo": forms.Select(attrs={"class": INPUT_CLASS}),
            "regla_cantidad": forms.NumberInput(
                attrs={
                    "class": INPUT_CLASS,
                    "min": "0.01",
                    "step": "0.01",
                    "inputmode": "decimal",
                    "placeholder": "Ej.: 3",
                }
            ),
            "regla_por": forms.Select(attrs={"class": INPUT_CLASS}),
            "regla_cada_dias": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 1, "inputmode": "numeric"}),
        }
        labels = {"regla_modo": "¿Cuánto hace falta?"}
        help_texts = {
            "nombre": "Como figura en el remito. No puede repetirse.",
            "unidad": "Por ejemplo: unidad, kit, bidón, paquete.",
            "regla_modo": (
                "Con esto la pantalla Situación estima qué le falta a cada institución. "
                "No es stock: el sistema no lleva inventario ni descuenta al enviar, y no cambia lo que se puede enviar."
            ),
        }

    def __init__(self, *args, en_uso=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.en_uso = en_uso
        self.fields["regla_modo"].choices = list(self.OPCIONES_DE_CONSUMO)
        if en_uso:
            for campo in ("nombre", "unidad"):
                self.fields[campo].disabled = True

    def campos_de_identidad(self):
        return [self["nombre"], self["unidad"]]

    def campos_de_consumo(self):
        return [self["regla_cantidad"], self["regla_por"], self["regla_cada_dias"]]

    def clean(self):
        """**Pasar** a «No lo estimo» vacía la regla sola: no obliga a borrar a mano cantidad, por y días.

        Solo cuando el modo cambió en este envío: una regla cargada (cantidad, por o días) con el
        modo que ya estaba en «No lo estimo» no se descarta en silencio, la rechaza el modelo. Después
        valida el modelo (RN-009-15): con dotación o reposición, lo que falta o sobra es error (una
        dotación con días se rechaza, no se borra en silencio: TC-1186-08).
        """
        datos = super().clean()
        if datos.get("regla_modo") == TipoKit.ModoRegla.SIN_REGLA and "regla_modo" in self.changed_data:
            datos["regla_cantidad"], datos["regla_por"], datos["regla_cada_dias"] = None, "", None
        return datos

    def clean_nombre(self):
        nombre = normalizar_nombre(self.cleaned_data.get("nombre"))
        if nombre and nombre_de_kit_en_uso(nombre, excluir_pk=self.instance.pk):
            raise forms.ValidationError(MENSAJE_NOMBRE_DUPLICADO)
        return nombre

    def validate_unique(self):
        """El duplicado ya lo dijo ``clean_nombre``, sin distinguir mayúsculas: no se repite el error."""

    def campos_para_guardar(self):
        """Lo que recibe el servicio: los campos del insumo ya validados."""
        return {campo: self.cleaned_data[campo] for campo in CAMPOS_DE_INSUMO}


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


#: Lo que dice el desplegable de «Nuevo caso» cuando el DNI no está en el legajo.
MENSAJE_SUGERENCIA_SIN_PERSONA_EN_NUEVO_CASO = "No está en el legajo: cargá su nombre y apellido abajo."

AYUDA_BUSCAR_DNI = (
    "Buscá en el legajo: escribí el DNI y elegí a la persona para completar su nombre y apellido. "
    "Si no está, cargalos a mano."
)
AYUDA_NOMBRE_DEL_RESPONSABLE = (
    "Solo si la persona todavía no está en el legajo. Si el DNI ya está registrado como otra persona, "
    "ver la casilla de abajo."
)
AYUDA_NOMBRE_CON_BUSCADOR = (
    "Se completan solos al elegir a la persona del legajo; cargalos a mano si no está. "
    "Si el DNI ya está registrado como otra persona, ver la casilla de abajo."
)


def aviso_identidad_a_revisar(caso):
    """El final del mensaje de éxito cuando el caso nació con identidad a revisar, o ``""``."""

    if caso.identidad_a_revisar is None:
        return ""
    return " Quedó con identidad a revisar: la mesa tiene que verificar quién es el responsable."


class _LocalidadConMunicipioField(forms.ModelChoiceField):
    """La localidad con su municipio entre paréntesis: el nombre solo se repite entre municipios."""

    def label_from_instance(self, localidad):
        return f"{localidad.nombre} ({localidad.municipio.nombre})"


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
        help_text=AYUDA_NOMBRE_DEL_RESPONSABLE,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    apellido = forms.CharField(
        label="Apellido",
        required=False,
        max_length=120,
        help_text=AYUDA_NOMBRE_DEL_RESPONSABLE,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    documento_extraviado = forms.BooleanField(
        label="Perdió el documento pero sabe el número",
        required=False,
        help_text="Queda anotado en la persona nueva del legajo. A quien ya tiene legajo no se le cambia nada.",
        widget=SwitchInput(),
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
    identidad_en_conflicto = forms.BooleanField(
        label="El DNI es correcto y es otra persona: cargar con identidad a revisar",
        required=False,
        help_text=(
            "El caso queda con la persona registrada, sin tocarla, y la mesa ve lo que cargaste para revisarlo. "
            "Si es esa persona, borrá nombre y apellido; si el DNI está mal, corregilo."
        ),
        widget=SwitchInput(),
    )

    forzar_nuevo = forms.BooleanField(
        label="Abrir un caso nuevo aunque la familia ya tiene uno abierto",
        required=False,
        help_text="Solo si de verdad es otra situación (p. ej. la familia se separó). Queda en el historial de los dos casos.",
        widget=SwitchInput(),
    )
    forzar_nuevo_motivo = forms.CharField(
        label="Motivo del caso nuevo",
        required=False,
        max_length=240,
        help_text="Obligatorio si abrís un caso nuevo.",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )

    direccion = forms.CharField(
        label="Dirección",
        max_length=240,
        help_text="Calle y número, o una referencia («frente a la capilla»).",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    localidad = _LocalidadConMunicipioField(
        label="Localidad (Municipio)",
        queryset=localidades_operativas(),
        empty_label="Elegí una localidad",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    # Cambio 493: el punto de la dirección, del Geocoder de Google o marcado en el mapa
    # (`components/_ubicacion_domicilio.html`). Sin JS o sin Google Maps, a mano. Desde el Cambio 520
    # llegan a ``crear_caso`` como el punto del **domicilio** (``domicilio_latitud``/``domicilio_longitud``),
    # no como el GPS: el backoffice no tiene GPS, y la distancia de «Derivar» se mide desde la casa.
    latitud = forms.DecimalField(
        label="Latitud",
        required=False,
        max_digits=9,
        decimal_places=6,
        validators=VALIDADORES_LATITUD,
        widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.000001"}),
    )
    longitud = forms.DecimalField(
        label="Longitud",
        required=False,
        max_digits=9,
        decimal_places=6,
        validators=VALIDADORES_LONGITUD,
        widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.000001"}),
    )
    foto_vivienda = _foto("Foto de la vivienda")
    foto_acceso = _foto("Foto del acceso")
    observaciones = forms.CharField(
        label="Observaciones",
        required=False,
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
    )

    CAMPOS_DE_TRASLADO = ("traslado", "traslado_otro", "dni", "telefono", "nombre", "apellido", "documento_extraviado")
    CAMPOS_DE_ASISTENCIA = ("dependientes", "mayores_dependientes", "lactantes")
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

    def clean(self):
        datos = super().clean()
        exigir_par(self)
        return datos

    def __init__(self, *args, url_sugerencias=None, **kwargs):
        """``url_sugerencias``: el endpoint que busca **solo en el legajo** mientras se escribe el DNI (Hallazgo 15).

        Solo presentación (``nodo-sugerencias.js``): al elegir a una persona se completan el DNI, el nombre y el
        apellido del legajo. Sin la URL, o sin JavaScript, el campo es el de siempre y ``crear_caso`` decide igual.
        """

        super().__init__(*args, **kwargs)
        if url_sugerencias:
            self.fields["dni"].help_text = AYUDA_BUSCAR_DNI
            self.fields["nombre"].help_text = self.fields["apellido"].help_text = AYUDA_NOMBRE_CON_BUSCADOR
            self.fields["dni"].widget.attrs.update(
                attrs_sugerencias(url_sugerencias, MENSAJE_SUGERENCIA_SIN_PERSONA_EN_NUEVO_CASO)
            )
            self.fields["dni"].widget.attrs["data-sugerencias-completa"] = (
                f"nombre:{self['nombre'].id_for_label},apellido:{self['apellido'].id_for_label}"
            )
        # La casilla solo aparece después del rechazo por DNI registrado, o si ya vino tildada.
        self.muestra_identidad_en_conflicto = bool(self.is_bound and self.data.get("identidad_en_conflicto"))
        # Lo mismo con «Abrir un caso nuevo»: aparece cuando la familia ya tiene un caso abierto (Cambio 579).
        self.muestra_caso_abierto = bool(self.is_bound and self.data.get("forzar_nuevo"))
        self.caso_abierto = None

    def agregar_errores_del_servicio(self, error):
        if isinstance(error, DniRegistrado):
            self.muestra_identidad_en_conflicto = True
        if isinstance(error, CasoAbiertoDeLaFamilia):
            self.muestra_caso_abierto = True
            self.caso_abierto = error.caso
        super().agregar_errores_del_servicio(error)

    def forzar_nuevo_motivo_de_la_mesa(self):
        """El motivo con el que la mesa abre un caso nuevo aunque la familia tenga uno, o ``None`` si no lo pide."""

        if not self.cleaned_data.get("forzar_nuevo"):
            return None
        return self.cleaned_data.get("forzar_nuevo_motivo") or ""

    def _campos(self, nombres):
        return [self[nombre] for nombre in nombres]

    def campos_de_traslado(self):
        campos = self._campos(self.CAMPOS_DE_TRASLADO)
        if self.muestra_identidad_en_conflicto:
            campos.append(self["identidad_en_conflicto"])
        if self.muestra_caso_abierto:
            campos.extend([self["forzar_nuevo"], self["forzar_nuevo_motivo"]])
        return campos

    def campos_de_personas(self):
        return self._campos(GrupoFamiliar.CANTIDADES)

    def campos_de_asistencia(self):
        return self._campos(self.CAMPOS_DE_ASISTENCIA)

    def campos_de_necesidades(self):
        return self._campos(NECESIDADES)

    def campos_de_fotos(self):
        return self._campos(self.FOTOS)

    def campos_de_observaciones(self):
        return [self["observaciones"]]

    def datos_formulario1(self):
        """El dict que recibe ``crear_caso``, con las claves que documenta ese servicio."""

        datos = {
            campo: valor
            for campo, valor in self.cleaned_data.items()
            if campo not in self.FOTOS
            and campo not in ("forzar_nuevo", "forzar_nuevo_motivo")
            and valor not in (None, "")
        }
        datos["fotos"] = {
            tipo: self.cleaned_data[campo] for campo, tipo in self.FOTOS.items() if self.cleaned_data.get(campo)
        }
        # Las cantidades de este formulario son los acompañantes: el responsable suma aparte.
        datos["responsable_aparte"] = True
        # El punto del mapa es el domicilio, no el GPS de un teléfono (Cambio 520).
        for campo in ("latitud", "longitud"):
            if campo in datos:
                datos[f"domicilio_{campo}"] = datos.pop(campo)
        return datos


# Lo que dice cada formulario chico de la ficha cuando llega algo que no puede ser. Van al
# aviso de la pantalla, así que dicen qué pasó y qué hacer (RU-20), no «Este campo es requerido».
CANAL_INVALIDO = "Elegí el canal del contacto de la lista."
RESULTADO_INVALIDO = "Elegí el resultado del contacto de la lista."
ELEGI_EL_MOTIVO = "Elegí el motivo del cierre."
ELEGI_LA_PRIORIDAD = "Elegí una prioridad: alta, media o baja."
ELEGI_UN_OPERADOR = "Elegí a alguien que opere la mesa de Emergencia."
ELEGI_UN_DISPOSITIVO = "Ese dispositivo ya no está en la lista. Recargá la ficha y elegí otro."
ELEGI_EL_EDIFICIO = "Ese edificio ya no está en la lista. Recargá la ficha y elegí otro."
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


class CancelarIngresoMesaForm(forms.Form):
    """«Cancelar ingreso» de la ficha: solo quien supervisa (Cambio 535). ``derivacion`` es la que vio la pantalla."""

    motivo = forms.CharField(
        label="Motivo",
        max_length=200,
        help_text="Queda en la traza del caso. El dispositivo ve que la mesa canceló el ingreso.",
        error_messages={
            "required": "Indicá por qué se cancela el ingreso.",
            "max_length": "El motivo no puede tener más de 200 caracteres.",
        },
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3, "maxlength": 200}),
    )
    derivacion = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)


class CerrarAlojadoMesaForm(forms.Form):
    """«Cerrar: la familia ya no está» de la ficha: solo con ``emergencia.cerrar_reabrir`` (Cambio 588)."""

    motivo = forms.CharField(
        label="Motivo",
        max_length=200,
        help_text="Queda en la traza del caso y como observación del cierre.",
        error_messages={
            "required": "Indicá por qué se cierra el caso desde la mesa.",
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
    """A qué institución, en qué edificio y cuántas plazas. ``confirmar_faltantes`` es el «sí» a derivar con menos (RN-2.5).

    ``edificio`` es opcional: una institución con camas en sectores sin edificio asignado se deriva sin él.
    Que la institución tenga camas en ese edificio lo valida ``derivar_caso`` (Cambio 520).
    """

    dispositivo = forms.ModelChoiceField(
        queryset=Dispositivo.objects.select_related("tipo"),
        widget=forms.HiddenInput,
        error_messages={"required": ELEGI_UN_DISPOSITIVO, "invalid_choice": ELEGI_UN_DISPOSITIVO},
    )
    edificio = forms.ModelChoiceField(
        queryset=Edificio.objects.all(),
        required=False,
        widget=forms.HiddenInput,
        error_messages={"invalid_choice": ELEGI_EL_EDIFICIO},
    )
    plazas = forms.IntegerField(
        label="Plazas a pedir",
        min_value=1,
        max_value=PLAZAS_MAXIMAS,
        error_messages={"required": PEDI_UNA_PLAZA, "invalid": PEDI_UNA_PLAZA, "min_value": PEDI_UNA_PLAZA},
        widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 1, "inputmode": "numeric"}),
    )
    confirmar_faltantes = forms.BooleanField(required=False, widget=forms.HiddenInput)


class UbicarDomicilioForm(forms.Form):
    """El punto del domicilio que el panel «Derivar» ubicó con Google (Cambio 520, fase 2). Lo manda el JS."""

    latitud = forms.DecimalField(max_digits=9, decimal_places=6, validators=VALIDADORES_LATITUD)
    longitud = forms.DecimalField(max_digits=9, decimal_places=6, validators=VALIDADORES_LONGITUD)


class PanelDerivarForm(forms.Form):
    """Lo que la ficha lee de la URL para armar el panel «Derivar». Es un GET: nada de esto escribe.

    ``grupo`` (el edificio elegido, ``e12``, o los sectores sin edificio de una institución, ``d34``) y
    ``derivar`` (la institución que se eligió adentro) viajan en la misma URL pero no son controles del
    panel: van ocultos solo para leerlos, y ``campos_visibles`` no los incluye.
    """

    plazas = forms.IntegerField(
        label="Plazas a pedir",
        required=False,
        min_value=1,
        max_value=PLAZAS_MAXIMAS,
        widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 1, "inputmode": "numeric"}),
    )
    q = forms.CharField(
        label="Buscar edificio o institución",
        required=False,
        max_length=80,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    localidad_dispositivo = forms.CharField(
        label="Localidad del edificio",
        required=False,
        max_length=120,
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    grupo = forms.RegexField(regex=r"^[ed][1-9][0-9]{0,9}$", required=False, widget=forms.HiddenInput)
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

    def solapa_explicita(self):
        """La solapa que vino en la URL, o ``""`` si es la implícita."""

        return self.limpios().get("solapa", "")

    def filtros(self, usuario):
        """El dict que recibe ``selectors.emergencia.bandeja``; por omisión, la solapa «Sin tomar»."""

        limpios = self.limpios()
        filtros = {campo: limpios[campo] for campo in self.CAMPOS_DEL_SELECTOR if campo in limpios}
        # Sin solapa en la URL se abre «Sin tomar», salvo que se esté buscando o filtrando por quién lo tiene: «Sin tomar»
        # nunca encuentra un caso con dueño, así que se filtra sobre «Abiertos» (que no es un chip). La solapa implícita
        # no se vuelve explícita al filtrar: el formulario no manda `solapa` si la URL no la traía.
        buscando = bool(limpios.get("texto") or limpios.get("operador"))
        filtros["solapa"] = limpios.get("solapa") or (SOLAPA_ABIERTOS if buscando else SOLAPA_SIN_TOMAR)
        filtros["usuario"] = usuario.pk
        operador = limpios.get("operador", "")
        if operador == OPERADOR_MIOS:
            filtros["tomado_por"] = usuario.pk
        elif operador.isdecimal():
            filtros["tomado_por"] = int(operador)
        return filtros
