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

from django.contrib.auth.models import Permission, User
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
        "tab": "backoffice",
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
        "tab": "backoffice",
        "alcance": "programa",  # módulo "de programa": sus capacidades se evalúan con alcance
        "capacidades": [
            ("programa.ver", "Ver programas"),
            ("programa.operar", "Operar programas"),
            ("programa.configurar", "Configurar programas"),
        ],
    },
    {
        "modulo": "relevamientos",
        "label": "Relevamientos",
        "tab": "becas",
        "alcance": "programa",  # módulo "de programa": sus capacidades se evalúan con alcance
        "capacidades": [
            ("relevamiento.ver", "Ver relevamientos"),
            ("relevamiento.gestionar", "Gestionar relevamientos"),
        ],
    },
    {
        "modulo": "becas",
        "label": "Programa Becas",
        "tab": "becas",
        "alcance": "programa",  # módulo "de programa": sus capacidades se evalúan con alcance
        "capacidades": [
            ("becas.configurar", "Configurar Becas (segmentos, cupos, requisitos, preguntas, coordinadores)"),
            ("becas.relevamientos", "Gestionar relevamientos de Becas"),
            ("becas.revisar", "Revisar formularios de Becas (aprobar/rechazar)"),
            ("becas.campo", "Operar la app de campo de Becas (territorial)"),
        ],
    },
    {
        "modulo": "conversaciones",
        "label": "Conversaciones",
        "tab": "backoffice",
        "capacidades": [
            ("conversacion.operar", "Operar conversaciones"),
            ("conversacion.configurar", "Configurar conversaciones"),
            ("conversacion.metricas", "Ver métricas de conversaciones"),
        ],
    },
    {
        "modulo": "dashboard",
        "label": "Dashboard",
        "tab": "backoffice",
        "capacidades": [
            ("dashboard.ver", "Ver dashboard"),
        ],
    },
    {
        "modulo": "reportes",
        "label": "Reportes",
        "tab": "backoffice",
        "capacidades": [
            ("reporte.ver", "Ver reportes"),
        ],
    },
    {
        "modulo": "configuracion",
        "label": "Configuración (geografía)",
        "tab": "sistema",
        "capacidades": [
            ("config.ver", "Ver configuración"),
            ("config.administrar", "Administrar configuración"),
        ],
    },
    {
        "modulo": "instituciones",
        "label": "Instituciones",
        "tab": "institucion",
        "capacidades": [
            ("institucion.ver", "Ver instituciones"),
            ("institucion.administrar", "Administrar instituciones"),
        ],
    },
    {
        "modulo": "sistema",
        "label": "Sistema",
        "tab": "sistema",
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
CATEGORIA_NACHEC = "ÑACHEC"
CATEGORIA_BECAS = "Becas"
# Valor legacy: usado en datos históricos y tests. No aparece en el selector de UI.
CATEGORIA_PROGRAMA = "Programa"
CATEGORIAS_ROL = [
    CATEGORIA_BACKOFFICE,
    CATEGORIA_INSTITUCION,
    CATEGORIA_PORTAL,
    CATEGORIA_SISTEMA,
    CATEGORIA_NACHEC,
    CATEGORIA_BECAS,
]
CATEGORIAS_ROL_CHOICES = [(c, c) for c in CATEGORIAS_ROL]

# Metadatos de los tabs para el ABM de Roles (panel de capacidades).
TABS_CAPACIDADES = [
    {"id": "backoffice", "label": "Backoffice", "icon": "fa-table-columns"},
    {"id": "institucion", "label": "Institución", "icon": "fa-building-columns"},
    {"id": "portal", "label": "Portal", "icon": "fa-globe"},
    {"id": "sistema", "label": "Sistema", "icon": "fa-gear"},
    {"id": "nachec", "label": "ÑACHEC", "icon": "fa-seedling"},
    {"id": "becas", "label": "Becas", "icon": "fa-graduation-cap"},
]

# Capacidades que dan acceso de administración del propio RBAC (para auto-protección).
CAPS_ADMINISTRACION = ("usuario.administrar", "rol.administrar")

# Nombre del rol protegido y del marcador de identidad del portal.
ROL_ADMINISTRADOR = "Administrador"
GRUPO_CIUDADANO_PORTAL = "Ciudadanos"


class SinAdministradorError(Exception):
    """La operación dejaría al sistema sin ningún usuario que pueda administrar."""


class SinAdministradorProgramaError(SinAdministradorError):
    """La operación dejaría a un **programa** sin ningún administrador.

    Subclase de :class:`SinAdministradorError` para que los ``except`` ya
    existentes la sigan capturando.
    """


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


def codigos_de_programa():
    """Códigos de capacidad de los módulos "de programa" (``alcance == "programa"``).

    Estas son las únicas capacidades que se evalúan con alcance de Programa; el
    resto son globales y el parámetro ``programa`` las ignora (ver :func:`puede`).
    """
    return {
        codigo
        for modulo in CATALOGO
        if modulo.get("alcance") == "programa"
        for (codigo, _etiqueta) in modulo["capacidades"]
    }


def es_codigo_de_programa(codigo):
    """¿La capacidad ``codigo`` pertenece a un módulo "de programa"?"""
    return codigo in codigos_de_programa()


def capacidades_de_grupo(group):
    """Códigos de capacidad (``"ciudadano.ver"``...) que tiene tildados un rol."""
    codenames = set(group.permissions.values_list("codename", flat=True))
    return [c for c in codigos_de_capacidad() if codename_de(c) in codenames]


def arbol_capacidades(codigos_activos=(), solo_programa=False):
    """Catálogo agrupado por módulo, marcando las capacidades activas.

    Estructura lista para renderizar el árbol del ABM de Roles::

        [{"modulo", "label", "capacidades": [{"codigo", "label", "checked"}]}]

    Con ``solo_programa=True`` se limita a los módulos "de programa"
    (``alcance == "programa"``). El default es retrocompatible: devuelve el
    catálogo completo.
    """
    activos = set(codigos_activos)
    return [
        {
            "modulo": modulo["modulo"],
            "label": modulo["label"],
            "alcance": modulo.get("alcance"),
            "capacidades": [
                {"codigo": codigo, "label": etiqueta, "checked": codigo in activos}
                for (codigo, etiqueta) in modulo["capacidades"]
            ],
        }
        for modulo in CATALOGO
        if not solo_programa or modulo.get("alcance") == "programa"
    ]


def arbol_por_tabs(codigos_activos=(), solo_programa=False):
    """Catálogo agrupado por tab para el panel de capacidades del ABM de Roles.

    Devuelve la lista de tabs definida en :data:`TABS_CAPACIDADES`, cada una con
    los módulos que le corresponden y las capacidades marcadas según
    ``codigos_activos``. Los tabs vacíos se incluyen (permiten futura expansión).

    Con ``solo_programa=True`` solo incluye módulos con ``alcance == "programa"``.
    """
    activos = set(codigos_activos)
    tabs = {t["id"]: {"id": t["id"], "label": t["label"], "icon": t["icon"], "modulos": []} for t in TABS_CAPACIDADES}
    for modulo in CATALOGO:
        if solo_programa and modulo.get("alcance") != "programa":
            continue
        tab_id = modulo.get("tab", "backoffice")
        if tab_id not in tabs:
            continue
        tabs[tab_id]["modulos"].append({
            "modulo": modulo["modulo"],
            "label": modulo["label"],
            "capacidades": [
                {"codigo": codigo, "label": etiqueta, "checked": codigo in activos}
                for (codigo, etiqueta) in modulo["capacidades"]
            ],
        })
    return list(tabs.values())


# ---------------------------------------------------------------------------
# Núcleo de autorización
# ---------------------------------------------------------------------------
def _capacidades_activas(user):
    """Set de códigos de capacidad **efectivos** del usuario.

    Solo cuentan las capacidades otorgadas por roles **activos** (un rol
    desactivado deja de surtir efecto, aunque el usuario lo conserve asignado).
    El superusuario activo tiene todas; el inactivo, ninguna. Se cachea por
    request en el propio objeto ``user`` (una sola query por request).
    """
    cache = getattr(user, "_caps_activas_cache", None)
    if cache is not None:
        return cache
    if not getattr(user, "is_active", False):
        cache = frozenset()
    elif user.is_superuser:
        cache = frozenset(codigos_de_capacidad())
    else:
        codenames = set(
            Permission.objects.filter(
                group__user=user, group__meta__activo=True
            )
            .values_list("codename", flat=True)
            .distinct()
        )
        cache = frozenset(c for c in codigos_de_capacidad() if codename_de(c) in codenames)
    user._caps_activas_cache = cache
    return cache


def _capacidades_activas_en_programa(user, programa):
    """Set de códigos "de programa" efectivos del usuario **para un Programa**.

    Cuentan los roles **activos** del usuario cuyo ``RolMeta.programa`` es el
    programa indicado **o** es nulo (roles globales que igual tengan la
    capacidad — RN-3). Superusuario activo tiene todas; inactivo, ninguna. Se
    cachea por request y por programa en ``user._caps_programa_cache``.
    """
    programa_pk = getattr(programa, "pk", programa)
    cache = getattr(user, "_caps_programa_cache", None)
    if cache is None:
        cache = {}
        user._caps_programa_cache = cache
    if programa_pk in cache:
        return cache[programa_pk]

    de_programa = codigos_de_programa()
    if not getattr(user, "is_active", False):
        resultado = frozenset()
    elif user.is_superuser:
        resultado = frozenset(de_programa)
    else:
        codenames_programa = {codename_de(c) for c in de_programa}
        # IMPORTANTE: todas las condiciones sobre ``group`` van en un ÚNICO
        # ``filter`` para que apunten a la MISMA fila de Group (el rol que tiene
        # la capacidad debe ser, él mismo, del programa X o global y del usuario y
        # activo). Partirlo en dos ``filter`` crea joins separados y daría falsos
        # positivos (p. ej. una cap de otro programa "se cuela" porque un rol
        # global cualquiera la tiene).
        codenames = set(
            Permission.objects.filter(
                Q(group__meta__programa=programa_pk)
                | Q(group__meta__programa__isnull=True),
                group__user=user,
                group__meta__activo=True,
                codename__in=codenames_programa,
            )
            .values_list("codename", flat=True)
            .distinct()
        )
        resultado = frozenset(c for c in de_programa if codename_de(c) in codenames)
    cache[programa_pk] = resultado
    return resultado


def puede(user, codigo, programa=None):
    """¿El usuario tiene la capacidad ``codigo`` (p. ej. ``"ciudadano.ver"``)?

    Resuelve **solo por roles activos**: superusuario activo siempre pasa;
    usuario inactivo, anónimo o cuyo único rol está desactivado, nunca.

    ``programa`` (opcional) acota la evaluación cuando ``codigo`` es de un módulo
    "de programa": solo cuentan los roles con ``RolMeta.programa`` igual a ese
    programa (o globales que tengan la capacidad). **Retrocompatible:** con
    ``programa=None`` —y para capacidades globales, que ignoran el alcance— el
    resultado es idéntico al comportamiento histórico.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if programa is None or not es_codigo_de_programa(codigo):
        return codigo in _capacidades_activas(user)
    return codigo in _capacidades_activas_en_programa(user, programa)


def puede_alguna(user, codigos, programa=None):
    """¿Tiene al menos una de las capacidades indicadas? (con alcance opcional)."""
    return any(puede(user, c, programa=programa) for c in codigos)


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
            | Q(groups__meta__activo=True, groups__permissions__codename__in=codenames)
        )
        .distinct()
    )


def usuarios_que_administran_programa(programa, excluir_ids=()):
    """Usuarios **activos** que administran un programa concreto.

    Cuenta a quien tiene un rol **activo** con ``RolMeta.programa = programa`` y
    la capacidad ``programa.configurar``, más los **superusuarios** activos
    (acceso de emergencia, igual que el check global).
    """
    programa_pk = getattr(programa, "pk", programa)
    codename = codename_de("programa.configurar")
    return (
        User.objects.filter(is_active=True)
        .exclude(id__in=list(excluir_ids))
        .filter(
            Q(is_superuser=True)
            | Q(
                groups__meta__activo=True,
                groups__meta__programa=programa_pk,
                groups__permissions__codename=codename,
            )
        )
        .distinct()
    )


def asegurar_admin_restante(programa=None):
    """Lanza si una operación dejaría al sistema —o a un programa— sin administrador.

    Pensado para llamarse **dentro** de ``transaction.atomic`` tras aplicar un
    cambio (quitar rol, desactivar usuario, quitar capacidad de un rol, borrar
    rol): si dejaría sin admins, la excepción revierte la transacción.

    **Retrocompatible:** sin ``programa`` realiza el check **global** histórico.
    Con ``programa`` realiza el check acotado a ese programa (RN-8).
    """
    if programa is None:
        if not usuarios_que_administran().exists():
            raise SinAdministradorError(
                "La operación dejaría al sistema sin ningún usuario con permisos de "
                "administración. Asigná las capacidades a otro usuario antes de continuar."
            )
        return
    if not usuarios_que_administran_programa(programa).exists():
        raise SinAdministradorProgramaError(
            f"La operación dejaría al programa «{programa}» sin ningún administrador. "
            "Asigná un rol de administración de ese programa a otro usuario antes de continuar."
        )
