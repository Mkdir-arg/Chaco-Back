from django import forms
from django.contrib.auth.models import Group, User
from django.core.exceptions import ObjectDoesNotExist
from django.utils.text import slugify

from core import rbac
from core.dni import MENSAJE_DNI_INVALIDO, dni_valido, normalizar_dni


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


_INPUT_ABM = "nodo-field"


def _agregar_campos_perfil_usuario(form):
    # RED-48: el DNI del usuario de backoffice también es un DNI. Era la **novena**
    # regla del repo —6 a 8 dígitos, escrita como regex, que es por donde el ratchet de
    # `len()` no la veía— y pasa a la única (`core.dni.dni_valido`). Sigue siendo
    # opcional (`required=False`): el Cambio 5 permite usuarios sin DNI. La
    # normalización y la regla de largo viven en `_validar_dni_perfil_usuario`, que es
    # el único lugar que puede comparar con lo que la fila ya tiene guardado.
    form.fields["dni"] = forms.CharField(
        required=False,
        label="DNI",
        widget=forms.TextInput(attrs={"class": _INPUT_ABM, "placeholder": "Ingrese el DNI", "inputmode": "numeric"}),
    )
    form.fields["telefono"] = forms.CharField(
        required=False,
        max_length=30,
        label="Teléfono",
        widget=forms.TextInput(attrs={"class": _INPUT_ABM, "placeholder": "Ingrese el teléfono", "type": "tel"}),
    )
    form.fields["institucion"] = forms.CharField(
        required=False,
        max_length=255,
        label="Institución",
        widget=forms.TextInput(attrs={"class": _INPUT_ABM, "placeholder": "Ingrese la institución"}),
    )
    form.fields["observacion"] = forms.CharField(
        required=False,
        label="Observación",
        widget=forms.Textarea(attrs={"class": _INPUT_ABM, "placeholder": "Ingrese una observación", "rows": 3}),
    )

    if form.instance and form.instance.pk:
        perfil = getattr(form.instance, "profile", None)
        if perfil is not None:
            for campo in ("dni", "telefono", "institucion", "observacion"):
                form.fields[campo].initial = getattr(perfil, campo, "") or ""


def _dni_guardado_del_perfil(instancia):
    """El DNI que la fila ya tiene, o ``None`` si es un alta o no hay perfil.

    Se lee de la base y no de `instancia.profile`: la relación puede venir cacheada de
    antes de que el perfil existiera, y entonces el legacy no se reconocería.
    """
    from users.models import Profile

    if not (instancia and instancia.pk):
        return None
    return Profile.objects.filter(user=instancia).values_list("dni", flat=True).first()


def _validar_dni_perfil_usuario(form):
    """Normaliza el DNI del perfil, lo valida y comprueba que no esté repetido.

    **Normalizar es obligatorio, no cosmético** (RED-48, ronda 3): `Profile.dni` es un
    `CharField(max_length=8)`, así que guardar `12.345.678` crudo —diez caracteres—
    muere en MariaDB y MySQL con un `DataError (1406, "Data too long for column 'dni'")`,
    que es un **500**. En SQLite el `max_length` no se aplica y no se ve; lo mide
    `users/tests/test_dni_usuario_motor_real.py` contra los dos motores.

    La regla de largo se exige **solo si el DNI cambia o es un alta**, igual que en
    `CiudadanoForm.clean_dni`: exigirla siempre dejaba inmodificable a cualquier usuario
    con un DNI legacy de 6 dígitos —no se podía ni cambiarle el rol ni el correo—.
    """
    from users.models import Profile

    dni = normalizar_dni(form.cleaned_data.get("dni")) or None
    anterior = _dni_guardado_del_perfil(form.instance)
    if dni and not dni_valido(dni) and dni != anterior:
        form.add_error("dni", MENSAJE_DNI_INVALIDO)
    duplicado = Profile.objects.filter(dni=dni) if dni else Profile.objects.none()
    if form.instance and form.instance.pk:
        duplicado = duplicado.exclude(user=form.instance)
    if duplicado.exists():
        form.add_error("dni", "Ya existe un usuario registrado con este DNI.")
    form.cleaned_data["dni"] = dni


def _agregar_campo_segmento_territorial(form, operador=None):
    """Suma el campo ``segmento_territorial`` (Becas) al form del ABM.

    Es obligatorio cuando el usuario tiene tildado un rol que otorga
    ``becas.campo`` (un territorial → un segmento). Se agrega en runtime para
    no importar ``programas`` al cargar el módulo.
    """
    from programas.models import Segmento
    from programas.services.autorizacion import grupos_territoriales_becas
    from users.selectors.usuarios import es_gestor_territorial

    segmentos = Segmento.objects.filter(activo=True).order_by("nombre")
    # Solo se acota a quien gestiona territoriales de SUS segmentos; un admin de
    # programa elige entre todos los segmentos activos (los suyos son el programa
    # entero, y acotarlo por coordinación le dejaría el combo vacío).
    if operador is not None and es_gestor_territorial(operador):
        from programas.services.autorizacion import segmentos_para_gestion_territoriales

        segmentos = segmentos_para_gestion_territoriales(operador).filter(activo=True).order_by("nombre")
    form.fields["segmento_territorial"] = forms.ModelChoiceField(
        queryset=segmentos,
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


def _agregar_campos_jerarquia_becas(form):
    from programas.services.autorizacion import (
        grupos_referentes_becas,
        usuarios_coordinadores_becas,
    )

    form.fields["coordinador_referente"] = forms.ModelChoiceField(
        queryset=usuarios_coordinadores_becas(),
        required=False,
        label="Coordinador del Referente",
        empty_label="Seleccioná…",
        widget=forms.Select(attrs={"class": _INPUT_ABM}),
    )
    from users.presentation import etiqueta_usuario

    form.fields["coordinador_referente"].queryset = form.fields["coordinador_referente"].queryset.select_related(
        "profile"
    )
    form.fields["coordinador_referente"].label_from_instance = etiqueta_usuario
    form.grupos_referentes_ids = set(grupos_referentes_becas().values_list("id", flat=True))


def _validar_jerarquia_becas(form):
    cleaned = form.cleaned_data
    grupos = {g.id for g in (cleaned.get("groups") or [])}
    es_referente = bool(grupos & getattr(form, "grupos_referentes_ids", set()))
    if es_referente and not cleaned.get("coordinador_referente"):
        form.add_error("coordinador_referente", "Seleccioná el Coordinador del Referente.")
    if not es_referente:
        cleaned["coordinador_referente"] = None
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
    from users.selectors.usuarios import es_gestor_territorial

    if es_gestor_territorial(operador):
        from programas.services.autorizacion import grupos_territoriales_becas

        return qs.filter(pk__in=grupos_territoriales_becas())
    # Es el combo de Roles del ABM de Usuarios: lo acota quién administra los
    # USUARIOS del programa, no quién administra sus roles.
    from users.selectors.roles import programas_administrables_usuarios

    return qs.filter(meta__programa__in=programas_administrables_usuarios(operador))


_SIN_CATEGORIA = "Sin categoría"
_SIN_PROGRAMA = "Sin programa"


def _ambito_de(meta):
    """Solapa a la que pertenece un rol.

    Un rol de categoría ``Programa`` pertenece al ámbito de **su programa**; el
    resto, al de su categoría. Así "Becas" es una sola solapa: fusiona los roles
    del programa Becas con los de la categoría homónima (que existe por historia)
    y no queda un "Becas" adentro de otro "Programa".
    """
    categoria = getattr(meta, "categoria", "") or _SIN_CATEGORIA
    if categoria != rbac.CATEGORIA_PROGRAMA:
        return categoria
    return getattr(getattr(meta, "programa", None), "nombre", "") or _SIN_PROGRAMA


def _orden_de_ambitos(ambitos):
    """Categorías canónicas primero, después los programas alfabéticos, y los huérfanos al final."""
    canonicas = [c for c in rbac.CATEGORIAS_ROL if c != rbac.CATEGORIA_PROGRAMA]
    colas = (_SIN_CATEGORIA, _SIN_PROGRAMA)
    orden = [a for a in canonicas if a in ambitos]
    orden += sorted(a for a in ambitos if a not in canonicas and a not in colas)
    orden += [a for a in colas if a in ambitos]
    return orden


def _ids_unicos(labels):
    """``{label: id}`` con el slug del label, desambiguando choques (ej. "Ñachec"/"Nachec")."""
    ids, usados = {}, set()
    for label in labels:
        base = slugify(label) or "otros"
        candidato, n = base, 2
        while candidato in usados:
            candidato, n = f"{base}-{n}", n + 1
        usados.add(candidato)
        ids[label] = candidato
    return ids


class RolesPorAmbitoMixin:
    """Expone los roles asignables agrupados por ámbito para el panel del ABM.

    El campo sigue siendo ``groups`` (``ModelMultipleChoiceField``): el panel
    renderiza checkboxes ``name="groups"`` y la validación no cambia. El árbol se
    arma en el render (no en ``__init__``) para reflejar lo tildado en un POST
    inválido y no pagar la query cuando el form no se muestra.
    """

    def _roles_seleccionados_ids(self):
        """Ids (str) tildados: del POST si está bound, del initial si no."""
        valor = self["groups"].value() or []
        if not isinstance(valor, (list, tuple, set)):
            valor = [valor]
        return {str(getattr(v, "pk", v)) for v in valor}

    def roles_por_ambito(self):
        """``[{"id", "label", "total", "roles": [...]}]``, una solapa por ámbito.

        Un ámbito es una categoría de rol (Backoffice, Sistema, …) o un **programa**
        (Becas, Dispositivos, …). Los roles de categoría ``Programa`` se listan en la
        solapa de su programa, no en una solapa "Programa" con tarjetas adentro: así
        cada solapa es un nivel único y "Becas" no aparece dos veces (ver
        :func:`_ambito_de`). Cada solapa trae su lista plana de roles ordenada por
        nombre.
        """
        seleccionados = self._roles_seleccionados_ids()
        territoriales = set(getattr(self, "grupos_territoriales_ids", []))
        roles = self.fields["groups"].queryset.select_related("meta", "meta__programa")

        por_ambito = {}
        for grupo in sorted(roles, key=lambda g: g.name.lower()):
            meta = getattr(grupo, "meta", None)
            por_ambito.setdefault(_ambito_de(meta), []).append(
                {
                    "id": str(grupo.pk),
                    "input_id": f"rol-{grupo.pk}",
                    "nombre": grupo.name,
                    "descripcion": getattr(meta, "descripcion", "") or "",
                    "checked": str(grupo.pk) in seleccionados,
                    "inactivo": meta is not None and not meta.activo,
                    "territorial": str(grupo.pk) in territoriales,
                }
            )

        orden = _orden_de_ambitos(por_ambito)
        ids = _ids_unicos(orden)
        return [
            {
                "id": ids[ambito],
                "label": ambito,
                "total": len(por_ambito[ambito]),
                "roles": por_ambito[ambito],
            }
            for ambito in orden
        ]


class UserCreationForm(RolesPorAmbitoMixin, forms.ModelForm):
    # Con correo informado la clave la genera el sistema y viaja en el mensaje
    # (RN-C1 del análisis #236), así que este campo queda solo para el usuario sin
    # correo, que sigue recibiendo su clave por otra vía (RN-C3).
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "nodo-field",
                "placeholder": "Solo si el usuario no tiene correo",
            }
        ),
        label="Contraseña",
        required=False,
        help_text=(
            "Con correo informado no hace falta: el sistema genera una clave provisoria y se la envía al usuario."
        ),
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=_roles_asignables_queryset(),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                "class": "nodo-field",
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
                    "class": "nodo-field",
                    "placeholder": "Ingrese el nombre de usuario",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "nodo-field",
                    "placeholder": "Ingrese el email",
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "nodo-field",
                    "placeholder": "Ingrese el nombre",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "nodo-field",
                    "placeholder": "Ingrese el apellido",
                }
            ),
        }

    def __init__(self, *args, operador=None, **kwargs):
        args, kwargs = _normalize_groups_args(args, kwargs)
        super().__init__(*args, **kwargs)
        self.operador = operador
        self.fields["groups"].queryset = _roles_asignables_queryset(operador)
        _agregar_campos_perfil_usuario(self)
        _agregar_campo_segmento_territorial(self, operador)
        _agregar_campos_jerarquia_becas(self)

    def clean(self):
        super().clean()
        _validar_dni_perfil_usuario(self)
        _validar_segmento_territorial(self)
        # Sin correo no hay forma de entregarle una clave generada: la tiene que
        # poner el operador ací.
        if not self.cleaned_data.get("email") and not self.cleaned_data.get("password"):
            self.add_error(
                "password",
                "Sin correo informado, la contraseña es obligatoria: el sistema no puede enviársela.",
            )
        return _validar_jerarquia_becas(self)


class CustomUserChangeForm(RolesPorAmbitoMixin, forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "nodo-field",
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
                "class": "nodo-field",
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
                    "class": "nodo-field",
                    "placeholder": "Ingrese el nombre de usuario",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "nodo-field",
                    "placeholder": "Ingrese el email",
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "nodo-field",
                    "placeholder": "Ingrese el nombre",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "nodo-field",
                    "placeholder": "Ingrese el apellido",
                }
            ),
        }

    def __init__(self, *args, operador=None, **kwargs):
        args, kwargs = _normalize_groups_args(args, kwargs)
        super().__init__(*args, **kwargs)
        self.operador = operador
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
        # SEC-03: si el usuario tiene roles fuera del alcance del operador, sus
        # credenciales no se tocan desde acá (los roles en alcance sí). Deshabilitar
        # el campo hace que Django ignore lo que venga en el POST y use el valor
        # actual, así el bloqueo no depende de que el navegador respete el atributo.
        from users.selectors.usuarios import puede_gestionar_credenciales

        self.credenciales_editables = puede_gestionar_credenciales(operador, self.instance)
        if not self.credenciales_editables:
            aviso = "Solo lo puede cambiar quien administre todos los roles de este usuario."
            for nombre in ("username", "email", "password"):
                self.fields[nombre].disabled = True
                self.fields[nombre].help_text = aviso
        _agregar_campos_perfil_usuario(self)
        _agregar_campo_segmento_territorial(self, operador)
        _agregar_campos_jerarquia_becas(self)
        if self.instance and self.instance.pk:
            asignacion = getattr(self.instance, "asignacion_territorial", None)
            if asignacion is not None:
                self.fields["segmento_territorial"].initial = asignacion.segmento_id
            try:
                referente = self.instance.asignacion_referente
                self.fields["coordinador_referente"].initial = referente.coordinador_id
            except ObjectDoesNotExist:
                pass

    def clean(self):
        super().clean()
        _validar_dni_perfil_usuario(self)
        _validar_segmento_territorial(self)
        return _validar_jerarquia_becas(self)
