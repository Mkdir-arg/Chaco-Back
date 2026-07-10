from django import forms
from django.contrib.auth.models import Group, User

from core import rbac


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


_INPUT_ABM = "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"


def _agregar_campo_segmento_territorial(form):
    """Suma el campo ``segmento_territorial`` (Becas) al form del ABM.

    Es obligatorio cuando el usuario tiene tildado un rol que otorga
    ``becas.campo`` (un territorial → un segmento). Se agrega en runtime para
    no importar ``programas`` al cargar el módulo.
    """
    from programas.models import Segmento
    from programas.services.autorizacion import grupos_territoriales_becas

    form.fields["segmento_territorial"] = forms.ModelChoiceField(
        queryset=Segmento.objects.filter(activo=True).order_by("nombre"),
        required=False,
        label="Segmento asignado (Becas)",
        empty_label="Seleccioná…",
        widget=forms.Select(attrs={"class": _INPUT_ABM, "id": "id_segmento_territorial"}),
        help_text="Define de qué segmento recibe relevamientos el territorial.",
    )
    form.grupos_territoriales_ids = [str(pk) for pk in grupos_territoriales_becas().values_list("id", flat=True)]


def _validar_segmento_territorial(form):
    """Regla del ABM: rol territorial tildado → segmento obligatorio.

    Sin rol territorial el campo se descarta (el servicio conserva la
    asignación existente solo si el usuario mantiene el rol por fuera del
    alcance del operador; si lo pierde, la borra).
    """
    cleaned = form.cleaned_data
    ids = set(getattr(form, "grupos_territoriales_ids", []))
    es_territorial = any(str(g.id) in ids for g in (cleaned.get("groups") or []))
    if es_territorial and not cleaned.get("segmento_territorial"):
        form.add_error(
            "segmento_territorial",
            "Seleccioná el segmento asignado: es obligatorio para el rol territorial.",
        )
    if not es_territorial:
        cleaned["segmento_territorial"] = None
    return cleaned


def _roles_asignables_queryset(operador=None):
    """Roles asignables a usuarios del backoffice: activos y NO de categoría Portal.

    El marcador ``Ciudadanos`` (identidad del portal) no es un rol de backoffice:
    asignárselo a un operador lo expulsaría al portal y rompería su sesión.

    Si ``operador`` es un **admin de programa** (no global), se acota a los roles
    de los programas que administra; un admin global (o sin operador) ve todos.
    """
    qs = Group.objects.filter(meta__activo=True).exclude(meta__categoria=rbac.CATEGORIA_PORTAL).order_by("name")
    if operador is None or operador.is_superuser or rbac.puede(operador, "usuario.administrar"):
        return qs
    from users.selectors.roles import programas_administrables

    return qs.filter(meta__programa__in=programas_administrables(operador))


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

    def __init__(self, *args, operador=None, **kwargs):
        args, kwargs = _normalize_groups_args(args, kwargs)
        super().__init__(*args, **kwargs)
        self.fields["groups"].queryset = _roles_asignables_queryset(operador)
        _agregar_campo_segmento_territorial(self)

    def clean(self):
        super().clean()
        return _validar_segmento_territorial(self)


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

    def __init__(self, *args, operador=None, **kwargs):
        args, kwargs = _normalize_groups_args(args, kwargs)
        super().__init__(*args, **kwargs)
        es_global = operador is None or operador.is_superuser or rbac.puede(operador, "usuario.administrar")
        asignables = _roles_asignables_queryset(operador)
        # Admin global: incluye los roles ya asignados (aunque estén inactivos)
        # para no perder asignaciones al editar. Admin de programa: NO se unen los
        # roles fuera de su alcance (no debe verlos ni tocarlos); igual se
        # preservan en el guardado scoped del servicio.
        if es_global and self.instance and self.instance.pk:
            asignables = (asignables | self.instance.groups.all()).distinct()
        self.fields["groups"].queryset = asignables
        self._original_password_hash = self.instance.password
        self.fields["password"].initial = ""
        _agregar_campo_segmento_territorial(self)
        if self.instance and self.instance.pk:
            asignacion = getattr(self.instance, "asignacion_territorial", None)
            if asignacion is not None:
                self.fields["segmento_territorial"].initial = asignacion.segmento_id

    def clean(self):
        super().clean()
        return _validar_segmento_territorial(self)
