"""Formularios de la guardia del dispositivo en Emergencia (E6 · «Llegadas»).

Validan **la entrada** —que la opción sea de la lista, que el texto entre en el campo—. Las
reglas de la etapa (el mínimo de la ficha, quién puede, en qué estado, qué cama) las decide
``programas/services/emergencia_alojar.py``, que es lo mismo que llama la API de la app
(RU-2): lo que ese servicio rechace vuelve a su campo con ``agregar_errores_del_servicio``.

El Formulario 2 (la ficha individual) **no se define acá**: sus secciones y sus campos salen
de ``emergencia_alojar.ESQUEMA_FICHA``, y este módulo solo les pone rótulo, ayuda y control.
Un campo que se agregue al esquema y no tenga rótulo acá hace fallar el arranque del form:
es a propósito, para que el backoffice no quede atrás de la app.
"""

from django import forms

from core.widgets import SwitchInput
from legajos.models import Ciudadano
from programas.forms import INPUT_CLASS
from programas.forms_emergencia import NuevoCasoMesaForm
from programas.models import IntegranteGrupo, Sector
from programas.services import emergencia_alojar as servicio

ELEGI_EL_MOTIVO = "Elegí el motivo de la lista."

SI, NO = "si", "no"


def _texto(etiqueta, largo, ayuda="", **attrs):
    return forms.CharField(
        label=etiqueta,
        required=False,
        max_length=largo,
        help_text=ayuda,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, **attrs}),
    )


def _parrafo(etiqueta, largo, ayuda=""):
    return forms.CharField(
        label=etiqueta,
        required=False,
        max_length=largo,
        help_text=ayuda,
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 2}),
    )


def _opcion(etiqueta, opciones, vacio="Elegí una opción", ayuda=""):
    return forms.ChoiceField(
        label=etiqueta,
        required=False,
        choices=[("", vacio), *opciones],
        help_text=ayuda,
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )


def _si_no(etiqueta, ayuda=""):
    """Una pregunta de sí o no que **puede quedar sin responder**: el mínimo exige la respuesta."""

    return forms.TypedChoiceField(
        label=etiqueta,
        required=False,
        choices=[("", "Sin responder"), (SI, "Sí"), (NO, "No")],
        coerce=lambda valor: valor == SI,
        empty_value=None,
        help_text=ayuda,
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )


def _sin_datos(seccion):
    return forms.BooleanField(
        label="Sin datos para cargar",
        required=False,
        help_text=f"Marcalo si preguntaste y no hay nada que cargar en «{servicio.ROTULO_DE_SECCION[seccion]}».",
        widget=SwitchInput(),
    )


#: El control de cada campo de ``ESQUEMA_FICHA``. Las claves son las del esquema, una por una.
CONTROLES_DE_LA_FICHA = {
    "parentesco": lambda: _opcion("Parentesco con quien responde", IntegranteGrupo.Parentesco.choices),
    "parentesco_otro": lambda: _texto("Otro parentesco", 80, "Solo si elegiste «Otro»."),
    "dni": lambda: _texto(
        "DNI",
        12,
        "Sin número de DNI la persona no se confirma con cama: se cierra el ingreso con diferencia.",
        inputmode="numeric",
        autocomplete="off",
    ),
    "nombre": lambda: _texto("Nombre", 120, "Si la persona ya está en el legajo, alcanza con el DNI."),
    "apellido": lambda: _texto("Apellido", 120),
    "sexo": lambda: _opcion("Sexo", Ciudadano.Genero.choices),
    "fecha_nacimiento": lambda: forms.DateField(
        label="Fecha de nacimiento",
        required=False,
        help_text="Si no la sabe, cargá una aproximada y marcalo abajo.",
        widget=forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}, format="%Y-%m-%d"),
    ),
    "fecha_nacimiento_aproximada": lambda: forms.BooleanField(
        label="La fecha es aproximada", required=False, widget=SwitchInput()
    ),
    "telefono": lambda: _texto("Teléfono", 40, inputmode="tel"),
    "documento_extraviado": lambda: forms.BooleanField(
        label="Perdió el documento pero sabe el número", required=False, widget=SwitchInput()
    ),
    "embarazo": lambda: _si_no("¿Está embarazada?"),
    "discapacidad": lambda: _si_no("¿Tiene alguna discapacidad?"),
    "electrodependiente": lambda: _si_no("¿Es electrodependiente?"),
    "medicacion_critica": lambda: _si_no("¿Toma medicación crítica?"),
    "medicacion_critica_nombre": lambda: _texto("Qué medicación", 200, "Solo si toma medicación crítica."),
    "medicacion_critica_tiene_dosis": lambda: _si_no("¿Tiene dosis con ella?", "Solo si toma medicación crítica."),
    "alergias_graves": lambda: _si_no("¿Tiene alergias graves?"),
    "alergias_graves_detalle": lambda: _texto("A qué", 200),
    "nivel_educativo": lambda: _opcion("Nivel educativo", servicio.NivelEducativo.choices),
    "escuela": lambda: _texto("Escuela", 200),
    "asiste_escuela": lambda: _si_no("¿Asiste?"),
    "esquema_al_dia": lambda: _si_no("¿Tiene el esquema de vacunación al día?"),
    "vacunacion_observacion": lambda: _parrafo("Observación", 500),
    "obra_social": lambda: _texto("Obra social", 120),
    "enfermedades_cronicas": lambda: _parrafo("Enfermedades crónicas", 500),
    "medicacion_habitual": lambda: _parrafo("Medicación habitual", 500),
    "ocupacion": lambda: _texto("Ocupación", 200),
    "ingresos": lambda: _texto("Ingresos", 200),
    "observaciones": lambda: _parrafo("Observaciones", 1000),
    "mascotas": lambda: _si_no("¿Vino con mascotas?"),
    "adulto_responsable": lambda: _texto(
        "Adulto responsable",
        200,
        f"Obligatorio si es menor de {servicio.EDAD_SIN_ADULTO_RESPONSABLE} años: quién responde por la persona.",
    ),
}

#: Los campos que el mínimo exige siempre: llevan asterisco **sin** ``required`` —quien decide
#: es el servicio— como lo prevé ``components/_field.html`` (``marca_requerido``).
CAMPOS_DEL_MINIMO = (
    "parentesco",
    "dni",
    "sexo",
    "fecha_nacimiento",
    *servicio.PREGUNTAS_CRITICAS,
)


class FichaIntegranteForm(forms.Form):
    """El Formulario 2 de una persona (M2-4), con las ocho secciones de ``ESQUEMA_FICHA``.

    ``solo_opcionales=True`` es la ficha de una persona **ya confirmada**: quedan las
    secciones 4 a 8, que son las que ``completar_ficha`` deja cambiar.

    ``plaza`` es la cama elegida en el mapa: viaja oculta, y es lo que la pantalla mostró.
    """

    plaza = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)

    def __init__(self, *args, solo_opcionales=False, ficha=None, **kwargs):
        if ficha is not None:
            kwargs["initial"] = {**self._iniciales(ficha), **(kwargs.get("initial") or {})}
        super().__init__(*args, **kwargs)
        self.solo_opcionales = solo_opcionales
        self.secciones_del_form = servicio.SECCIONES_OPCIONALES if solo_opcionales else tuple(servicio.ESQUEMA_FICHA)
        if solo_opcionales:
            del self.fields["plaza"]
        for seccion in self.secciones_del_form:
            for campo in servicio.ESQUEMA_FICHA[seccion]:
                self.fields[campo] = CONTROLES_DE_LA_FICHA[campo]()
                if campo in CAMPOS_DEL_MINIMO:
                    self.fields[campo].marca_requerido = True
            if seccion in servicio.SECCIONES_OPCIONALES:
                self.fields[f"{seccion}_{servicio.SIN_DATOS}"] = _sin_datos(seccion)

    @staticmethod
    def _iniciales(ficha):
        """La ficha guardada como valores iniciales: los sí/no vuelven a «si» / «no»."""

        iniciales = {}
        for campo, valor in servicio.ficha_a_plano(ficha).items():
            control = CONTROLES_DE_LA_FICHA.get(campo)
            es_si_no = control is not None and isinstance(control(), forms.TypedChoiceField)
            iniciales[campo] = (SI if valor else NO) if es_si_no and isinstance(valor, bool) else valor
        return iniciales

    def secciones(self):
        """Las secciones para el template: ``[{codigo, numero, titulo, minimo, campos, sin_datos}]``."""

        armadas = []
        for numero, seccion in enumerate(servicio.ESQUEMA_FICHA, start=1):
            if seccion not in self.secciones_del_form:
                continue
            sin_datos = f"{seccion}_{servicio.SIN_DATOS}"
            armadas.append(
                {
                    "codigo": seccion,
                    "numero": numero,
                    "titulo": servicio.ROTULO_DE_SECCION[seccion],
                    "minimo": seccion in servicio.SECCIONES_MINIMAS,
                    "campos": [self[campo] for campo in servicio.ESQUEMA_FICHA[seccion]],
                    "sin_datos": self[sin_datos] if sin_datos in self.fields else None,
                }
            )
        return armadas

    def ficha(self):
        """La ficha anidada que recibe el servicio, con lo que se cargó en este formulario."""

        datos = {
            campo: (valor.isoformat() if hasattr(valor, "isoformat") else valor)
            for campo, valor in self.cleaned_data.items()
            if campo != "plaza" and valor not in (None, "")
        }
        ficha = servicio.ficha_desde_plano(datos)
        return {seccion: ficha[seccion] for seccion in self.secciones_del_form}

    def agregar_errores_del_servicio(self, error):
        """Lleva cada rechazo del servicio a su campo; lo que no es de un campo (la cama), arriba."""

        if not hasattr(error, "error_dict"):
            self.add_error(None, error)
            return
        for clave, errores in error.error_dict.items():
            self.add_error(clave if clave in self.fields and clave != "plaza" else None, errores)


class BuscarFamiliaForm(forms.Form):
    """M2-1: el DNI de cualquiera de la familia. Es un GET: no escribe nada."""

    dni = forms.CharField(
        label="DNI de alguien de la familia",
        max_length=12,
        help_text="El del responsable o el de una persona que ya confirmaste.",
        error_messages={"required": "Escribí un DNI para buscar."},
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "inputmode": "numeric", "autocomplete": "off"}),
    )


class _MotivoDelCatalogoForm(forms.Form):
    """Motivo de una lista más observación: la forma de las confirmaciones con motivo (RU-22)."""

    MOTIVOS = ()
    AYUDA_OBSERVACION = "Obligatoria si el motivo es «Otro»."

    motivo = forms.ChoiceField(
        label="Motivo",
        error_messages={"required": ELEGI_EL_MOTIVO, "invalid_choice": ELEGI_EL_MOTIVO},
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    observacion = forms.CharField(
        label="Observación",
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["motivo"].choices = [("", "Elegí el motivo"), *self.MOTIVOS]
        self.fields["observacion"].help_text = self.AYUDA_OBSERVACION


class RechazarDerivacionForm(_MotivoDelCatalogoForm):
    MOTIVOS = servicio.MotivoRechazo.choices


class DiferenciaForm(_MotivoDelCatalogoForm):
    MOTIVOS = servicio.MotivoDiferencia.choices
    AYUDA_OBSERVACION = "Obligatoria si el motivo es «Otro» (por ejemplo: no tiene número de documento)."


class CancelarIngresoForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo",
        max_length=200,
        help_text="Queda en la traza del caso y lo lee la mesa.",
        error_messages={
            "required": "Indicá por qué se cancela el ingreso.",
            "max_length": "El motivo no puede tener más de 200 caracteres.",
        },
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3, "maxlength": 200}),
    )


class FamiliaAlojadaForm(forms.Form):
    """La sección 4 del Formulario 1 (M2-5): dónde quedó la familia y la tarjeta."""

    sector = forms.ModelChoiceField(
        label="Sector o ala",
        queryset=Sector.objects.none(),
        required=False,
        empty_label="Sin indicar",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    aula = forms.CharField(
        label="Aula o dormitorio",
        required=False,
        max_length=80,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    tarjeta_entregada = forms.BooleanField(label="Tarjeta familiar entregada", required=False, widget=SwitchInput())
    tarjeta_numero = forms.CharField(
        label="Número de la tarjeta",
        required=False,
        max_length=40,
        help_text="Obligatorio si se entregó la tarjeta.",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    encargado = forms.CharField(
        label="Encargado que recibe",
        required=False,
        max_length=120,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )

    def __init__(self, *args, sectores, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sector"].queryset = sectores

    def agregar_errores_del_servicio(self, error):
        if not hasattr(error, "error_dict"):
            self.add_error(None, error)
            return
        for clave, errores in error.error_dict.items():
            self.add_error(clave if clave in self.fields else None, errores)


class Formulario1DispositivoForm(NuevoCasoMesaForm):
    """El Formulario 1 cargado en la puerta del dispositivo: ingreso directo y aviso a la mesa (M2-6).

    Es el de la mesa (PR 3) con **localidad y dirección opcionales**: la familia está acá, y
    sin esos datos el servicio pone los del dispositivo (RN-3.10).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo, ayuda in (
            ("direccion", "De dónde viene la familia. Si no la cargás, queda la del dispositivo."),
            ("localidad", "Si no la elegís, queda la del dispositivo."),
        ):
            self.fields[campo].required = False
            self.fields[campo].help_text = ayuda
        self.fields["localidad"].empty_label = "La del dispositivo"
