"""
Motor de autorización por **capacidades** (RBAC) del backoffice.

Pieza única de autorización del sistema. Una "capacidad" (`modulo.accion`,
p. ej. ``ciudadano.ver``) es un ``django.contrib.auth.Permission`` real, anclado
al modelo ``users.Capacidad`` y tildado sobre cada Rol (``Group``) mediante
``group.permissions``. La fachada ``puede()`` traduce el código de capacidad al
identificador nativo ``"<app_label>.<codename>"`` y delega en ``user.has_perm``,
reusando el cache por request, el bypass de superusuario y la resolución
usuario→grupos→permisos que ya provee Django.

Reglas:
- La autorización resuelve **solo** por capacidad, nunca por nombre de grupo.
- ``is_superuser`` (activo) tiene bypass total (lo da ``User.has_perm``).
- El grupo ``Ciudadanos`` es un **marcador de identidad** del portal, no una
  capacidad de backoffice (ver :func:`es_ciudadano_portal`).
"""
from functools import wraps

from django.contrib.auth.models import User
from django.db.models import Q

# App donde vive el modelo ancla ``Capacidad`` (define el app_label de los permisos).
APP_LABEL = "users"

# ---------------------------------------------------------------------------
# Catálogo curado de capacidades (fuente única: alimenta el seed, el árbol del
# ABM de Roles y el modelo ancla ``users.Capacidad``).
# Cada módulo: clave técnica, etiqueta visible y lista de (codigo, etiqueta).
# ---------------------------------------------------------------------------
CATALOGO = [
    {
        "modulo": "ciudadanos",
        "label": "Ciudadanos / Legajos",
        "capacidades": [
            ("ciudadano.ver", "Ver ciudadanos y legajos"),
            ("ciudadano.crear", "Crear ciudadanos"),
            ("ciudadano.editar", "Editar ciudadanos"),
            ("ciudadano.eliminar", "Eliminar ciudadanos"),
            ("ciudadano.sensible", "Ver datos sensibles"),
        ],
    },
    {
        "modulo": "programas",
        "label": "Programas",
        "capacidades": [
            ("programa.ver", "Ver programas"),
            ("programa.operar", "Operar programas"),
            ("programa.configurar", "Configurar programas"),
        ],
    },
    {
        "modulo": "relevamientos",
        "label": "Relevamientos",
        "capacidades": [
            ("relevamiento.ver", "Ver relevamientos"),
            ("relevamiento.gestionar", "Gestionar relevamientos"),
        ],
    },
    {
        "modulo": "conversaciones",
        "label": "Conversaciones",
        "capacidades": [
            ("conversacion.operar", "Operar conversaciones"),
            ("conversacion.configurar", "Configurar conversaciones"),
            ("conversacion.metricas", "Ver métricas de conversaciones"),
        ],
    },
    {
        "modulo": "dashboard",
        "label": "Dashboard",
        "capacidades": [
            ("dashboard.ver", "Ver dashboard"),
        ],
    },
    {
        "modulo": "reportes",
        "label": "Reportes",
        "capacidades": [
            ("reporte.ver", "Ver reportes"),
        ],
    },
    {
        "modulo": "configuracion",
        "label": "Configuración (geografía)",
        "capacidades": [
            ("config.ver", "Ver configuración"),
            ("config.administrar", "Administrar configuración"),
        ],
    },
    {
        "modulo": "instituciones",
        "label": "Instituciones",
        "capacidades": [
            ("institucion.ver", "Ver instituciones"),
            ("institucion.administrar", "Administrar instituciones"),
        ],
    },
    {
        "modulo": "sistema",
        "label": "Sistema",
        "capacidades": [
            ("usuario.administrar", "Administrar usuarios"),
            ("rol.administrar", "Administrar roles"),
        ],
    },
]

# Categorías válidas de un Rol (RolMeta.categoria).
CATEGORIA_BACKOFFICE = "Backoffice"
CATEGORIA_INSTITUCION = "Institución"
CATEGORIA_PORTAL = "Portal"
CATEGORIA_SISTEMA = "Sistema"
CATEGORIAS_ROL = [
    CATEGORIA_BACKOFFICE,
    CATEGORIA_INSTITUCION,
    CATEGORIA_PORTAL,
    CATEGORIA_SISTEMA,
]
CATEGORIAS_ROL_CHOICES = [(c, c) for c in CATEGORIAS_ROL]

# Capacidades que dan acceso de administración del propio RBAC (para auto-protección).
CAPS_ADMINISTRACION = ("usuario.administrar", "rol.administrar")

# Nombre del rol protegido y del marcador de identidad del portal.
ROL_ADMINISTRADOR = "Administrador"
GRUPO_CIUDADANO_PORTAL = "Ciudadanos"


class SinAdministradorError(Exception):
    """La operación dejaría al sistema sin ningún usuario que pueda administrar."""


# ---------------------------------------------------------------------------
# Catálogo: helpers de traducción código ↔ permiso Django
# ---------------------------------------------------------------------------
def codename_de(codigo):
    """``"ciudadano.ver"`` -> ``"ciudadano_ver"`` (codename Django)."""
    return codigo.replace(".", "_")


def perm_de(codigo):
    """``"ciudadano.ver"`` -> ``"users.ciudadano_ver"`` (identificador ``has_perm``)."""
    return f"{APP_LABEL}.{codename_de(codigo)}"


def todas_las_capacidades():
    """Lista plana ``[(codename, etiqueta), ...]`` para ``Capacidad.Meta.permissions``."""
    return [
        (codename_de(codigo), etiqueta)
        for modulo in CATALOGO
        for (codigo, etiqueta) in modulo["capacidades"]
    ]


def codigos_de_capacidad():
    """Lista de códigos de capacidad (``"ciudadano.ver"``...)."""
    return [
        codigo
        for modulo in CATALOGO
        for (codigo, _etiqueta) in modulo["capacidades"]
    ]


def capacidades_de_grupo(group):
    """Códigos de capacidad (``"ciudadano.ver"``...) que tiene tildados un rol."""
    codenames = set(group.permissions.values_list("codename", flat=True))
    return [c for c in codigos_de_capacidad() if codename_de(c) in codenames]


def arbol_capacidades(codigos_activos=()):
    """Catálogo agrupado por módulo, marcando las capacidades activas.

    Estructura lista para renderizar el árbol del ABM de Roles::

        [{"modulo", "label", "capacidades": [{"codigo", "label", "checked"}]}]
    """
    activos = set(codigos_activos)
    return [
        {
            "modulo": modulo["modulo"],
            "label": modulo["label"],
            "capacidades": [
                {"codigo": codigo, "label": etiqueta, "checked": codigo in activos}
                for (codigo, etiqueta) in modulo["capacidades"]
            ],
        }
        for modulo in CATALOGO
    ]


# ---------------------------------------------------------------------------
# Núcleo de autorización
# ---------------------------------------------------------------------------
def puede(user, codigo):
    """¿El usuario tiene la capacidad ``codigo`` (p. ej. ``"ciudadano.ver"``)?

    Delega en ``user.has_perm``: superusuario activo siempre pasa; usuario
    inactivo o anónimo nunca. El resultado se cachea por request en el propio
    ``has_perm`` de Django.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return user.has_perm(perm_de(codigo))


def puede_alguna(user, codigos):
    """¿Tiene al menos una de las capacidades indicadas?"""
    return any(puede(user, c) for c in codigos)


def es_ciudadano_portal(user):
    """¿El usuario es un ciudadano del portal? (marcador de identidad, no capacidad).

    Se cachea por request. El middleware del portal y ``ciudadano_required`` lo
    usan para separar identidad-de-portal de las capacidades del backoffice.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    cache = getattr(user, "_es_ciudadano_portal", None)
    if cache is None:
        cache = user.groups.filter(name=GRUPO_CIUDADANO_PORTAL).exists()
        user._es_ciudadano_portal = cache
    return cache


# ---------------------------------------------------------------------------
# Enforcement: decorador (FBV) y mixin (CBV)
# ---------------------------------------------------------------------------
def requiere(*codigos, redirect_to="core:inicio"):
    """Decorador para FBV: exige al menos una de las capacidades indicadas.

    No autenticado -> login. Autenticado sin capacidad -> redirect con mensaje.
    Reemplaza a ``core.decorators.group_required`` (por nombre de grupo).
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login

                return redirect_to_login(request.get_full_path())
            if puede_alguna(user, codigos):
                return view_func(request, *args, **kwargs)
            from django.contrib import messages
            from django.shortcuts import redirect

            messages.error(request, "No tiene permisos para acceder a esta sección.")
            return redirect(redirect_to)

        return _wrapped

    return decorator


class CapacidadRequeridaMixin:
    """Mixin para CBV: exige al menos una capacidad de ``capacidades_requeridas``.

    Reemplaza a ``core.mixins.GroupRequiredMixin`` y a ``AdminRequiredMixin``.
    Uso: ``capacidades_requeridas = "rol.administrar"`` (o lista de códigos).
    """

    capacidades_requeridas = []
    redirect_sin_permiso = "core:inicio"

    def get_capacidades_requeridas(self):
        caps = self.capacidades_requeridas
        return [caps] if isinstance(caps, str) else list(caps)

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(request.get_full_path())
        if puede_alguna(user, self.get_capacidades_requeridas()):
            return super().dispatch(request, *args, **kwargs)
        from django.contrib import messages
        from django.shortcuts import redirect

        messages.error(request, "No tiene permisos para acceder a esta sección.")
        return redirect(self.redirect_sin_permiso)


# ---------------------------------------------------------------------------
# Auto-protección: no dejar el sistema sin administradores
# ---------------------------------------------------------------------------
def usuarios_que_administran(excluir_ids=()):
    """Usuarios **activos** que pueden administrar usuarios o roles.

    Cuenta a quien tiene alguna capacidad de administración por rol (grupo) o
    por permiso directo, más los superusuarios (acceso de emergencia).
    """
    codenames = [codename_de(c) for c in CAPS_ADMINISTRACION]
    return (
        User.objects.filter(is_active=True)
        .exclude(id__in=list(excluir_ids))
        .filter(
            Q(is_superuser=True)
            | Q(groups__permissions__codename__in=codenames)
            | Q(user_permissions__codename__in=codenames)
        )
        .distinct()
    )


def asegurar_admin_restante():
    """Lanza :class:`SinAdministradorError` si ya no queda ningún administrador.

    Pensado para llamarse **dentro** de ``transaction.atomic`` tras aplicar un
    cambio (quitar rol, desactivar usuario, quitar capacidad de un rol, borrar
    rol): si dejaría al sistema sin admins, la excepción revierte la transacción.
    """
    if not usuarios_que_administran().exists():
        raise SinAdministradorError(
            "La operación dejaría al sistema sin ningún usuario con permisos de "
            "administración. Asigná las capacidades a otro usuario antes de continuar."
        )
