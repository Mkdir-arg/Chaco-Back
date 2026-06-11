"""Consultas de lectura para el ABM de Roles."""
from django.contrib.auth.models import Group
from django.db.models import Count

from core import rbac


def _capacidades_desde_prefetch(group):
    """Códigos de capacidad del rol usando los permisos ya prefetcheados."""
    codenames = {p.codename for p in group.permissions.all()}
    return [c for c in rbac.codigos_de_capacidad() if rbac.codename_de(c) in codenames]


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
