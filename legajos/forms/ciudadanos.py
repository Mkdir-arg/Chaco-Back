from django import forms

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
        dni = self.cleaned_data.get("dni")
        if dni:
            dni_limpio = "".join(filter(str.isdigit, dni))
            if len(dni_limpio) < 7 or len(dni_limpio) > 8:
                raise forms.ValidationError("El DNI debe tener entre 7 y 8 dígitos.")
            return dni_limpio
        return dni


class CiudadanoForm(forms.ModelForm):
    """Formulario para crear/editar ciudadanos con datos de RENAPER"""

    class Meta:
        model = Ciudadano
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


class CiudadanoConfirmarForm(CiudadanoForm):
    pass


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

    def __init__(self, *args, puede_ver_sensible=False, **kwargs):
        super().__init__(*args, **kwargs)
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
