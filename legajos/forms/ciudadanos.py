from django import forms

from core.dni import MENSAJE_DNI_INVALIDO, dni_valido, normalizar_dni

from ..models import Ciudadano

_FLOWBITE_INPUT_CSS = (
    "block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 "
    "text-sm text-gray-900 shadow-sm transition-colors "
    "focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
)
_FLOWBITE_READONLY_CSS = (
    "block w-full rounded-lg border border-gray-200 bg-gray-100 p-2.5 "
    "text-sm text-gray-500 shadow-sm cursor-not-allowed"
)
_FLOWBITE_TEXTAREA_CSS = (
    "block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 "
    "text-sm text-gray-900 shadow-sm transition-colors "
    "focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
)
_FLOWBITE_FILE_CSS = (
    "block w-full text-sm text-gray-700 file:mr-4 file:rounded-lg file:border-0 "
    "file:bg-blue-600 file:px-4 file:py-2.5 file:font-medium file:text-white "
    "hover:file:bg-blue-700"
)


class ConsultaRenaperForm(forms.Form):
    """Formulario para consultar datos en RENAPER"""

    GENERO_CHOICES = [
        ("", "Seleccionar..."),
        ("M", "Masculino"),
        ("F", "Femenino"),
        ("X", "No binario"),
    ]

    dni = forms.CharField(
        max_length=8,
        label="DNI",
        widget=forms.TextInput(
            attrs={
                "class": _FLOWBITE_INPUT_CSS,
                "placeholder": "Ingrese el DNI (ej: 12345678)",
            }
        ),
    )

    sexo = forms.ChoiceField(
        choices=GENERO_CHOICES,
        label="Sexo",
        widget=forms.Select(
            attrs={
                "class": _FLOWBITE_INPUT_CSS,
            }
        ),
    )

    def clean_dni(self):
        # RED-48: la regla de largo es la única del repo (`core.dni.dni_valido`).
        dni = normalizar_dni(self.cleaned_data.get("dni"))
        if not dni_valido(dni):
            raise forms.ValidationError(MENSAJE_DNI_INVALIDO)
        return dni


class CiudadanoForm(forms.ModelForm):
    """Formulario para crear/editar ciudadanos con datos de RENAPER"""

    class Meta:
        model = Ciudadano
        labels = {"domicilio": "Domicilio actual"}
        fields = [
            "dni",
            "nombre",
            "apellido",
            "fecha_nacimiento",
            "genero",
            "telefono",
            "email",
            "domicilio",
            "provincia",
            "municipio",
            "localidad",
        ]
        widgets = {
            "dni": forms.TextInput(
                attrs={
                    "class": _FLOWBITE_READONLY_CSS,
                    "readonly": True,
                }
            ),
            "nombre": forms.TextInput(
                attrs={
                    "class": _FLOWBITE_INPUT_CSS,
                }
            ),
            "apellido": forms.TextInput(
                attrs={
                    "class": _FLOWBITE_INPUT_CSS,
                }
            ),
            "fecha_nacimiento": forms.DateInput(
                attrs={
                    "class": _FLOWBITE_INPUT_CSS,
                    "type": "date",
                }
            ),
            "genero": forms.Select(
                attrs={
                    "class": _FLOWBITE_INPUT_CSS,
                }
            ),
            "telefono": forms.TextInput(
                attrs={
                    "class": _FLOWBITE_INPUT_CSS,
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": _FLOWBITE_INPUT_CSS,
                }
            ),
            "domicilio": forms.TextInput(
                attrs={
                    "class": _FLOWBITE_INPUT_CSS,
                }
            ),
            "provincia": forms.Select(
                attrs={
                    "class": _FLOWBITE_INPUT_CSS,
                }
            ),
            "municipio": forms.Select(
                attrs={
                    "class": _FLOWBITE_INPUT_CSS,
                }
            ),
            "localidad": forms.Select(
                attrs={
                    "class": _FLOWBITE_INPUT_CSS,
                }
            ),
        }

    def clean_dni(self):
        """G1c-08: el DNI del legajo entra normalizado y con la regla del repo.

        El widget tenía `readonly` y nada más —una propiedad del HTML, no una
        validación—, así que `12.345.678` entraba tal cual por la carga manual y
        creaba una **segunda** persona junto a `12345678`. Becas normaliza, así que
        nunca la encontraba: la misma persona quedaba partida en dos legajos.

        La regla de largo es `core.dni.dni_valido`, la única del repo (RED-48), y se
        aplica **solo cuando el DNI es nuevo o cambió**. En una edición que no lo
        toca, exigirla dejaba inmodificable a cualquier ficha con un DNI legacy de 6,
        9 o 10 dígitos: el error colgaba de un campo `disabled`, no se veía dónde, y
        no se guardaba nada —ni el teléfono—. Corregir esos DNI es un trabajo aparte
        (`manage.py listar_dni_no_normalizados`, P-17) y lo hace quien puede editarlo.
        """
        dni = normalizar_dni(self.cleaned_data.get("dni"))
        if not dni_valido(dni) and dni != normalizar_dni(getattr(self.instance, "dni", "")):
            raise forms.ValidationError(MENSAJE_DNI_INVALIDO)
        return dni


class CiudadanoManualForm(CiudadanoForm):
    class Meta(CiudadanoForm.Meta):
        widgets = {
            **CiudadanoForm.Meta.widgets,
            "dni": forms.TextInput(
                attrs={
                    "class": _FLOWBITE_INPUT_CSS,
                    "placeholder": "Ingrese el DNI",
                }
            ),
        }


#: Lo que RENAPER respondió y el operador **confirma**, no edita (G1c-08). Django
#: ignora lo que llegue en el POST para un campo `disabled` y usa el `initial`, que
#: en esta pantalla sale de la sesión: el `dni=99999999, nombre=Inventado` que la
#: PoC mandaba a mano deja de poder entrar. El domicilio, el teléfono y el email no
#: están acá a propósito: son los datos que el operador sí completa o corrige.
CAMPOS_CONFIRMADOS_DE_RENAPER = ("dni", "nombre", "apellido", "fecha_nacimiento")


class CiudadanoConfirmarForm(CiudadanoForm):
    """Confirmación del alta con datos de RENAPER.

    Los cuatro campos de identidad llegan de la consulta y quedan bloqueados: la
    pantalla dice «confirmar», y hasta acá un POST armado a mano guardaba cualquier
    cosa con la procedencia de RENAPER puesta.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre in CAMPOS_CONFIRMADOS_DE_RENAPER:
            campo = self.fields[nombre]
            # Se bloquea lo que RENAPER **respondió**. Si un campo volvió vacío no
            # hay nada que confirmar y el operador lo completa: bloquearlo también
            # dejaría la pantalla sin salida (RED-41 midió respuestas reales con el
            # nombre en `None`).
            if self.get_initial_for_field(campo, nombre) in (None, ""):
                continue
            campo.disabled = True
            campo.widget.attrs["class"] = _FLOWBITE_READONLY_CSS


_UPDATE_CSS = _FLOWBITE_INPUT_CSS


class CiudadanoUpdateForm(CiudadanoForm):
    """Formulario de edición ampliado — incluye campos de perfil social."""

    _FIELD_CSS = _UPDATE_CSS

    class Meta(CiudadanoForm.Meta):
        fields = CiudadanoForm.Meta.fields + [
            "foto",
            "tipo_vivienda",
            "tenencia_vivienda",
            "condiciones_vivienda",
            "situacion_laboral",
            "ingreso_estimado",
            "obra_social",
            "nivel_educativo",
            "dni_fisico",
            "estado_renaper",
            "observaciones",
        ]
        widgets = {
            **CiudadanoForm.Meta.widgets,
            "foto": forms.ClearableFileInput(
                attrs={
                    "class": _FLOWBITE_FILE_CSS,
                    "accept": "image/*",
                }
            ),
            "tipo_vivienda": forms.Select(attrs={"class": _UPDATE_CSS}),
            "tenencia_vivienda": forms.Select(attrs={"class": _UPDATE_CSS}),
            "condiciones_vivienda": forms.Textarea(attrs={"class": _FLOWBITE_TEXTAREA_CSS, "rows": 3}),
            "situacion_laboral": forms.Select(attrs={"class": _UPDATE_CSS}),
            "ingreso_estimado": forms.Select(attrs={"class": _UPDATE_CSS}),
            "obra_social": forms.TextInput(attrs={"class": _UPDATE_CSS}),
            "nivel_educativo": forms.Select(attrs={"class": _UPDATE_CSS}),
            "dni_fisico": forms.Select(attrs={"class": _UPDATE_CSS}),
            "estado_renaper": forms.Select(attrs={"class": _UPDATE_CSS}),
            "observaciones": forms.Textarea(attrs={"class": _FLOWBITE_TEXTAREA_CSS, "rows": 4}),
        }

    def __init__(self, *args, puede_ver_sensible=False, puede_editar_dni=False, **kwargs):
        super().__init__(*args, **kwargs)
        # G1c-08. Dos campos que la edición dejaba cambiar a cualquiera con
        # `ciudadano.editar`:
        #
        # * **`dni`**: es la identidad de la persona en los tres módulos. Cambiarlo
        #   en un titular con un caso APROBADO cambia lo que se reintenta contra
        #   SIIS, y el DNI viejo queda ocupado en la convocatoria (DAT-03). Queda
        #   para quien administra la configuración; el resto corrige por el alta.
        # * **`estado_renaper`**: es la **procedencia** del dato, no un dato del
        #   legajo. Lo pone el alta según de dónde vino la identidad; a mano
        #   cualquiera marcaba «REGISTRADO» una carga manual.
        #
        # Van `disabled` y no fuera de `fields`: el template los renderiza por
        # nombre, y Django ignora lo que llegue en el POST para un campo disabled.
        if not puede_editar_dni:
            self.fields["dni"].disabled = True
            self.fields["dni"].widget.attrs["class"] = _FLOWBITE_READONLY_CSS
        self.fields["estado_renaper"].disabled = True
        self.fields["estado_renaper"].widget.attrs["class"] = _FLOWBITE_READONLY_CSS
        if puede_ver_sensible:
            from ..models import Ciudadano as _C

            self.fields["cobertura_medica"] = forms.CharField(
                max_length=200,
                required=False,
                label="Cobertura médica",
                widget=forms.TextInput(attrs={"class": self._FIELD_CSS}),
            )
            self.fields["medicacion_habitual"] = forms.CharField(
                required=False,
                label="Medicación habitual",
                widget=forms.Textarea(attrs={"class": _FLOWBITE_TEXTAREA_CSS, "rows": 3}),
            )
            self.fields["estado_migratorio"] = forms.ChoiceField(
                choices=[("", "---------")] + list(_C.EstadoMigratorio.choices),
                required=False,
                label="Estado migratorio",
                widget=forms.Select(attrs={"class": self._FIELD_CSS}),
            )
            if self.instance and self.instance.pk:
                self.fields["cobertura_medica"].initial = self.instance.cobertura_medica
                self.fields["medicacion_habitual"].initial = self.instance.medicacion_habitual
                self.fields["estado_migratorio"].initial = self.instance.estado_migratorio

    def clean_foto(self):
        foto = self.cleaned_data.get("foto")
        if foto and hasattr(foto, "size") and foto.size > 5 * 1024 * 1024:
            raise forms.ValidationError("La foto no puede superar los 5 MB.")
        return foto

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Guardar campos sensibles si están presentes
        if "cobertura_medica" in self.cleaned_data:
            instance.cobertura_medica = self.cleaned_data["cobertura_medica"]
        if "medicacion_habitual" in self.cleaned_data:
            instance.medicacion_habitual = self.cleaned_data["medicacion_habitual"]
        if "estado_migratorio" in self.cleaned_data:
            instance.estado_migratorio = self.cleaned_data["estado_migratorio"]
        if commit:
            instance.save()
        return instance
