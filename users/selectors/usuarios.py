from django.contrib.auth.models import User

from core import rbac
from users.selectors.roles import programas_administrables


def get_usuarios_queryset():
    return (
        User.objects.select_related("profile")
        .prefetch_related("groups", "groups__meta", "user_permissions")
        .order_by("-id")
    )


def es_admin_global_usuarios(user):
    """¿El operador gestiona **todos** los usuarios? (superusuario o ``usuario.administrar``).

    En el ABM de Usuarios el alcance global lo da ``usuario.administrar`` (no
    ``rol.administrar``, que es para el ABM de Roles).
    """
    if not getattr(user, "is_authenticated", False):
        return False
    return user.is_superuser or rbac.puede(user, "usuario.administrar")


def usuarios_visibles_para(user):
    """Usuarios que el operador puede ver, filtrados por alcance.

    Admin global: todos. Admin de programa: usuarios con al menos un rol cuyo
    ``RolMeta.programa`` esté entre los que administra.
    """
    qs = get_usuarios_queryset()
    if es_admin_global_usuarios(user):
        return qs
    programas = programas_administrables(user)
    return qs.filter(groups__meta__programa__in=programas, groups__meta__activo=True).distinct()


def alcance_roles_ids(user):
    """IDs de roles (Group) que el operador puede asignar/quitar.

    Devuelve ``None`` si es admin global (sin restricción: el guardado reemplaza
    todos los grupos como hoy). Para un admin de programa, el conjunto de roles
    **activos** de los programas que administra: solo esos se tocan al guardar,
    el resto del ``groups`` del usuario queda intacto.
    """
    if es_admin_global_usuarios(user):
        return None
    from users.forms import _roles_asignables_queryset

    return set(_roles_asignables_queryset(user).values_list("id", flat=True))


def puede_gestionar_usuario(operador, target):
    """¿El operador puede editar a ``target`` según su alcance?

    Admin global: siempre. Admin de programa: solo si el usuario tiene al menos
    un rol de alguno de los programas que administra.
    """
    if es_admin_global_usuarios(operador):
        return True
    programas = set(programas_administrables(operador).values_list("pk", flat=True))
    return target.groups.filter(meta__programa__in=programas, meta__activo=True).exists()
