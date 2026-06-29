"""Consultas de lectura para el ABM de Roles."""
from django.contrib.auth.models import Group
from django.db.models import Count

from core import rbac
from programas.models import Programa


def _capacidades_desde_prefetch(group):
    """Códigos de capacidad del rol usando los permisos ya prefetcheados."""
    codenames = {p.codename for p in group.permissions.all()}
    return [c for c in rbac.codigos_de_capacidad() if rbac.codename_de(c) in codenames]


def es_admin_global(user):
    """¿El operador gestiona todo el RBAC, sin restricción de programa?

    Es el camino del Administrador global (o superusuario): ve y gestiona roles
    y usuarios de cualquier categoría/programa, igual que hoy.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    return rbac.puede(user, "rol.administrar") or rbac.puede(user, "usuario.administrar")


def programas_administrables(user):
    """Programas donde el operador es **administrador de programa**.

    Es decir, tiene un rol **activo** con ``RolMeta.programa = X`` y la capacidad
    ``programa.configurar`` tildada. Para un admin global/superusuario devuelve
    **todos** los programas.
    """
    if not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return Programa.objects.none()
    if es_admin_global(user):
        return Programa.objects.all()
    codename = rbac.codename_de("programa.configurar")
    return Programa.objects.filter(
        roles_meta__activo=True,
        roles_meta__grupo__user=user,
        roles_meta__grupo__permissions__codename=codename,
    ).distinct()


def puede_gestionar_rol(user, group):
    """¿El operador puede ver/editar este rol según su alcance?

    Admin global: siempre. Admin de programa: solo roles de categoría 'Programa'
    cuyo ``programa`` esté entre los que administra.
    """
    if es_admin_global(user):
        return True
    meta = getattr(group, "meta", None)
    _CATS_PROGRAMA = {rbac.CATEGORIA_PROGRAMA, rbac.CATEGORIA_NACHEC, rbac.CATEGORIA_BECAS}
    if not meta or meta.categoria not in _CATS_PROGRAMA or not meta.programa_id:
        return False
    return programas_administrables(user).filter(pk=meta.programa_id).exists()


def roles_visibles_para(user):
    """Roles agrupados para el ABM, **filtrados por el alcance del operador**.

    Devuelve ``{"categorias": [(categoria, [item, ...]), ...sin 'Programa'],
    "programas": [(Programa, [item, ...]), ...]}``. El admin global ve todo; el
    admin de programa ve solo la sub-sección de los programas que administra.

    Cada ``item``: ``{"group", "meta", "num_usuarios", "capacidades"}``.
    """
    global_ = es_admin_global(user)
    programas_ok = (
        None if global_
        else set(programas_administrables(user).values_list("pk", flat=True))
    )

    groups = (
        Group.objects.select_related("meta", "meta__programa")
        .prefetch_related("permissions")
        .annotate(num_usuarios=Count("user", distinct=True))
        .order_by("name")
    )

    cats = [c for c in rbac.CATEGORIAS_ROL if c != rbac.CATEGORIA_PROGRAMA]
    por_categoria = {cat: [] for cat in cats}
    sin_categoria = []
    por_programa = {}  # programa_pk -> (Programa, [items])

    for group in groups:
        meta = getattr(group, "meta", None)
        item = {
            "group": group,
            "meta": meta,
            "num_usuarios": group.num_usuarios,
            "capacidades": _capacidades_desde_prefetch(group),
        }
        categoria = meta.categoria if meta else None
        if categoria == rbac.CATEGORIA_PROGRAMA and meta and meta.programa_id:
            if not global_ and meta.programa_id not in programas_ok:
                continue  # rol de un programa que el operador no administra
            _prog, items = por_programa.setdefault(meta.programa_id, (meta.programa, []))
            items.append(item)
        else:
            if not global_:
                continue  # un admin de programa no ve roles globales
            (por_categoria.get(categoria, sin_categoria)).append(item)

    categorias = [(cat, por_categoria[cat]) for cat in cats if por_categoria[cat]]
    if global_ and sin_categoria:
        categorias.append(("Sin categoría", sin_categoria))
    programas = [
        por_programa[pk]
        for pk in sorted(por_programa, key=lambda k: por_programa[k][0].nombre)
    ]
    return {"categorias": categorias, "programas": programas}


def roles_por_categoria():
    """Roles agrupados por categoría, con meta, conteo de usuarios y capacidades.

    Devuelve ``[(categoria, [item, ...]), ...]`` en el orden de
    :data:`core.rbac.CATEGORIAS_ROL`, omitiendo las categorías vacías.
    """
    groups = (
        Group.objects.select_related("meta")
        .prefetch_related("permissions")
        .annotate(num_usuarios=Count("user", distinct=True))
        .order_by("name")
    )

    por_categoria = {cat: [] for cat in rbac.CATEGORIAS_ROL}
    sin_categoria = []
    for group in groups:
        meta = getattr(group, "meta", None)
        item = {
            "group": group,
            "meta": meta,
            "num_usuarios": group.num_usuarios,
            "capacidades": _capacidades_desde_prefetch(group),
        }
        categoria = meta.categoria if meta else None
        (por_categoria.get(categoria, sin_categoria)).append(item)

    resultado = [
        (categoria, por_categoria[categoria])
        for categoria in rbac.CATEGORIAS_ROL
        if por_categoria[categoria]
    ]
    if sin_categoria:
        resultado.append(("Sin categoría", sin_categoria))
    return resultado
