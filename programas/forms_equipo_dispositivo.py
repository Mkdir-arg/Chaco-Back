"""Formularios del Equipo de un dispositivo (Cambios 411, 420, 523, 556).

Salen de `forms_dispositivos.py` para que ese archivo no pase de las 1.000 líneas.
"""

from django import forms

from core.dni import MENSAJE_DNI_INVALIDO, dni_valido, normalizar_dni
from core.forms_sugerencias import attrs_sugerencias
from core.widgets import ChipsSelectMultiple, SwitchInput
from programas.forms import INPUT_CLASS
from programas.models import MiembroEquipoDispositivo

#: Lo que dice el buscador del Equipo cuando nadie coincide, según quien lo use (Cambio 420).
MENSAJE_EQUIPO_SIN_PERSONA = "No encontramos a nadie: tocá «Crear persona» para darla de alta."
MENSAJE_EQUIPO_PEDIR_ALTA = "¿No está? Pedile al administrador del programa que la dé de alta."


class _EdificiosField(forms.MultipleChoiceField):
    """Los ids de edificio elegidos. Qué edificios valen (vinculados, propios del responsable) lo decide el servicio."""

    def to_python(self, value):
        ids = []
        for crudo in super().to_python(value):
            if not (crudo.isascii() and crudo.isdecimal()):
                raise forms.ValidationError("Elegí edificios de la lista.", code="invalid_choice")
            ids.append(int(crudo))
        return ids

    def valid_value(self, value):
        return True


class _CamposAlcanceEquipo(forms.Form):
    """«Alcance» y «Edificios» del puesto (Cambio 523, PR 4), compartidos por sumar, crear y editar.

    El form solo **ofrece** lo que el servidor acepta (``opciones`` sale de ``equipo.opciones_de_alcance``) y no valida
    reglas: ``alcance`` acepta los valores del modelo aunque no se hayan ofrecido, y ``edificios`` cualquier id, para que
    el servicio (RN2, RN6) sea quien rechace y el error llegue al campo. Sin ``alcance`` en el POST, toda la institución.
    Con ``edificio_fijo`` (entrada «Agregar persona al edificio») no hay selector: viaja el edificio, oculto.
    """

    alcance = forms.ChoiceField(
        label="Alcance",
        required=False,
        choices=MiembroEquipoDispositivo._meta.get_field("alcance").choices,
        widget=forms.Select(attrs={"class": INPUT_CLASS, "x-model": "alcance"}),
        help_text="Qué parte de la institución opera la persona.",
    )
    edificios = _EdificiosField(
        label="Edificios",
        required=False,
        choices=(),
        widget=ChipsSelectMultiple,
        help_text="Elegí al menos un edificio.",
    )
    edificio_fijo = forms.IntegerField(required=False, widget=forms.HiddenInput())

    def _armar_alcance(self, opciones, edificio_fijo=False, miembro=None):
        self.edificio_fijo = edificio_fijo
        if edificio_fijo:
            del self.fields["alcance"], self.fields["edificios"]
            self.fields["edificio_fijo"].required = True
            return
        del self.fields["edificio_fijo"]
        opciones = opciones or {"alcances": [], "edificios": []}
        self.fields["alcance"].widget.choices = opciones["alcances"]
        self.fields["edificios"].choices = [(str(pk), nombre) for pk, nombre in opciones["edificios"]]
        if miembro is not None:
            primero = opciones["alcances"][0][0] if opciones["alcances"] else ""
            self.initial.setdefault("alcance", miembro.alcance or primero)
            self.initial.setdefault("edificios", [str(pk) for pk in miembro.edificios.values_list("pk", flat=True)])
        elif opciones["alcances"]:
            self.initial.setdefault("alcance", opciones["alcances"][0][0])

    def datos_de_alcance(self):
        """``{"alcance", "edificios"}`` para el servicio; con edificio fijo, es ese edificio."""

        if self.edificio_fijo:
            return {
                "alcance": MiembroEquipoDispositivo.Alcance.EDIFICIOS,
                "edificios": [self.cleaned_data["edificio_fijo"]],
            }
        return {
            "alcance": self.cleaned_data.get("alcance") or None,
            "edificios": self.cleaned_data.get("edificios") or [],
        }


class SumarMiembroEquipoForm(_CamposAlcanceEquipo):
    """«Sumar persona» al Equipo (Cambio 411): un buscador «Persona — Rol» y la marca de responsable.

    Desde el Cambio 420 la persona se busca con sugerencias (``nodo-sugerencias.js``): el campo visible
    es solo para teclear y el que viaja es ``persona_rol`` (``"<usuario_pk>:<rol_pk>"``, oculto), que el
    formulario valida contra lo que el servicio acepta (usuario activo, rol activo de Dispositivos que la
    persona tiene, sin el de agente de relevamiento y que todavía no está en el Equipo). El servicio
    vuelve a validar al guardar.
    """

    persona = forms.CharField(
        label="Persona y rol",
        required=False,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Escribí nombre o apellido"}),
    )
    persona_rol = forms.CharField(
        widget=forms.HiddenInput(),
        error_messages={"required": "Elegí a la persona y el rol de la lista de sugerencias."},
    )
    tipo_contratacion = forms.ChoiceField(
        label="Tipo de contratación",
        choices=[("", "Elegí el tipo de contratación"), *MiembroEquipoDispositivo.TipoContratacion.choices],
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
        error_messages={"required": "Elegí el tipo de contratación."},
    )
    es_responsable = forms.BooleanField(
        label="Es responsable del dispositivo",
        required=False,
        widget=SwitchInput(),
        help_text="Los responsables arman el Equipo del dispositivo.",
    )

    field_order = [
        "persona",
        "persona_rol",
        "tipo_contratacion",
        "alcance",
        "edificios",
        "edificio_fijo",
        "es_responsable",
    ]

    def __init__(
        self,
        *args,
        dispositivo=None,
        url_sugerencias=None,
        sin_resultados=None,
        opciones=None,
        edificio_fijo=False,
        **kwargs,
    ):
        """``url_sugerencias`` y ``sin_resultados`` (el aviso cuando nadie coincide) son solo presentación."""

        super().__init__(*args, **kwargs)
        self._armar_alcance(opciones, edificio_fijo)
        self.dispositivo = dispositivo
        campo = self.fields["persona"]
        campo.marca_requerido = True  # el campo visible no es `required` (viaja `persona_rol`), pero se pide
        campo.widget.attrs.update(attrs_sugerencias(url_sugerencias, sin_resultados))
        if url_sugerencias:
            campo.widget.attrs["data-sugerencias-destino"] = self["persona_rol"].auto_id

    def clean_persona_rol(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group
        from django.core.exceptions import ValidationError

        from programas.services import equipo_dispositivo as equipo

        invalido = forms.ValidationError("Esa persona y ese rol no se pueden sumar al Equipo.", code="invalid_choice")
        usuario_pk, _, rol_pk = self.cleaned_data["persona_rol"].partition(":")
        if not (usuario_pk.isascii() and usuario_pk.isdecimal() and rol_pk.isascii() and rol_pk.isdecimal()):
            raise invalido
        usuario = get_user_model().objects.filter(pk=int(usuario_pk)).first()
        rol = Group.objects.filter(pk=int(rol_pk)).first()
        if usuario is None or rol is None:
            raise invalido
        try:
            equipo.exigir_par_sumable(usuario, rol)
        except ValidationError:
            raise invalido from None
        if (
            self.dispositivo is not None
            and not self.edificio_fijo  # «Agregar persona al edificio» suma el edificio a quien ya está
            and MiembroEquipoDispositivo.objects.filter(
                dispositivo=self.dispositivo, usuario=usuario, rol=rol, activo=True
            ).exists()
        ):
            raise forms.ValidationError("Esa persona ya está en el Equipo con ese rol.")
        return usuario, rol


class CrearPersonaEquipoForm(_CamposAlcanceEquipo):
    """«Crear persona» desde el Equipo (Cambio 420): los cuatro datos y el rol con el que entra.

    ``roles`` es ``roles_para_crear_persona(actor)``: lo que el actor puede dar según la regla del ABM de
    Usuarios, acotado a Dispositivos y sin el rol de agente. No pide clave: llega por enlace al correo.
    El DNI, el correo y el resto de las reglas del alta las valida el formulario del ABM de Usuarios.
    """

    dni = forms.CharField(
        label="DNI",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "inputmode": "numeric", "placeholder": "Sin puntos"}),
    )
    first_name = forms.CharField(label="Nombre", max_length=150, widget=forms.TextInput(attrs={"class": INPUT_CLASS}))
    last_name = forms.CharField(label="Apellido", max_length=150, widget=forms.TextInput(attrs={"class": INPUT_CLASS}))
    email = forms.EmailField(
        label="Correo",
        widget=forms.EmailInput(attrs={"class": INPUT_CLASS}),
        help_text="La clave le llega a este correo, por un enlace para definirla.",
    )
    rol = forms.ModelChoiceField(
        label="Rol",
        queryset=None,
        empty_label="Elegí un rol",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
        error_messages={
            "required": "Elegí el rol con el que se suma.",
            "invalid_choice": "Ese rol no se puede dar al crear una persona.",
        },
    )
    tipo_contratacion = forms.ChoiceField(
        label="Tipo de contratación",
        choices=[("", "Elegí el tipo de contratación"), *MiembroEquipoDispositivo.TipoContratacion.choices],
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
        error_messages={"required": "Elegí el tipo de contratación."},
    )
    es_responsable = forms.BooleanField(
        label="Es responsable del dispositivo",
        required=False,
        widget=SwitchInput(),
        help_text="Los responsables arman el Equipo del dispositivo.",
    )

    field_order = [
        "dni",
        "first_name",
        "last_name",
        "email",
        "rol",
        "tipo_contratacion",
        "alcance",
        "edificios",
        "edificio_fijo",
        "es_responsable",
    ]

    def __init__(self, *args, roles, opciones=None, edificio_fijo=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rol"].queryset = roles
        self._armar_alcance(opciones, edificio_fijo)

    def clean_dni(self):
        dni = normalizar_dni(self.cleaned_data["dni"])
        if not dni_valido(dni):
            raise forms.ValidationError(MENSAJE_DNI_INVALIDO)
        return dni


class AlcanceMiembroEquipoForm(_CamposAlcanceEquipo):
    """«Cambiar alcance» de una persona del Equipo (Cambio 523, PR 4): el selector, con lo que tiene hoy."""

    def __init__(self, *args, opciones, miembro, **kwargs):
        super().__init__(*args, **kwargs)
        self._armar_alcance(opciones, False, miembro)
