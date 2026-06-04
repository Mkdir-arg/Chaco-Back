from django import forms
from django.contrib.auth.models import Group, User


def _normalize_groups_data(data):
    """
    Permite aceptar tanto 'groups' como 'groups[]' cuando el formulario se envía desde JS.
    Algunos frontends serializan listas como 'field[]', lo que hacía que Django ignorara el campo.
    """
    if not data:
        return data

    try:
        has_groups_key = "groups" in data
    except TypeError:
        return data

    if has_groups_key or "groups[]" not in data:
        return data

    if hasattr(data, "getlist") and hasattr(data, "setlist"):
        mutable_data = data.copy()
        mutable_data.setlist("groups", mutable_data.getlist("groups[]"))
        try:
            del mutable_data["groups[]"]
        except KeyError:
            pass
        return mutable_data

    mutable_data = data.copy()
    raw_value = mutable_data.pop("groups[]", [])
    if isinstance(raw_value, (list, tuple)):
        values = list(raw_value)
    else:
        values = [raw_value]
    mutable_data["groups"] = values
    return mutable_data


def _normalize_groups_args(args, kwargs):
    if args:
        first = _normalize_groups_data(args[0])
        if first is not args[0]:
            args = (first, *args[1:])
    elif kwargs.get("data") is not None:
        kwargs["data"] = _normalize_groups_data(kwargs["data"])
    return args, kwargs


def _roles_asignables_queryset():
    """Roles asignables: solo los activos (un rol inactivo no es asignable)."""
    return Group.objects.filter(meta__activo=True).order_by("name")


class UserCreationForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                "placeholder": "Ingrese la contraseña",
            }
        ),
        label="Contraseña",
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=_roles_asignables_queryset(),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                "id": "id_groups",
                "size": "4",
            }
        ),
        label="Roles",
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "groups",
            "last_name",
            "first_name",
        ]
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                    "placeholder": "Ingrese el nombre de usuario",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                    "placeholder": "Ingrese el email",
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                    "placeholder": "Ingrese el nombre",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                    "placeholder": "Ingrese el apellido",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        args, kwargs = _normalize_groups_args(args, kwargs)
        super().__init__(*args, **kwargs)
        self.fields["groups"].queryset = _roles_asignables_queryset()


class CustomUserChangeForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                "placeholder": "Dejar en blanco para no cambiar",
            }
        ),
        label="Contraseña (dejar en blanco para no cambiarla)",
        required=False,
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=_roles_asignables_queryset(),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                "id": "id_groups_edit",
                "size": "4",
            }
        ),
        label="Roles",
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "groups",
            "last_name",
            "first_name",
        ]
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                    "placeholder": "Ingrese el nombre de usuario",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                    "placeholder": "Ingrese el email",
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                    "placeholder": "Ingrese el nombre",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                    "placeholder": "Ingrese el apellido",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        args, kwargs = _normalize_groups_args(args, kwargs)
        super().__init__(*args, **kwargs)
        # Incluye los roles ya asignados (aunque estén inactivos) + los activos,
        # para no perder asignaciones existentes al editar.
        asignables = _roles_asignables_queryset()
        if self.instance and self.instance.pk:
            asignables = (asignables | self.instance.groups.all()).distinct()
        self.fields["groups"].queryset = asignables
        self._original_password_hash = self.instance.password
        self.fields["password"].initial = ""
