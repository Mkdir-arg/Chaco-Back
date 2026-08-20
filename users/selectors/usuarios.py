from django.contrib.auth.models import User

from core import rbac
from users.selectors.roles import programas_administrables_usuarios


def get_usuarios_queryset():
    # Solo se prefetchea lo que el listado consume (nombres de grupos); el
    # filtrado por groups__meta se hace en SQL y no necesita prefetch.
    return User.objects.select_related("profile").prefetch_related("groups").order_by("-id")


def es_gestor_territorial(user):
    """¿El operador está acotado a los territoriales de los segmentos que coordina?

    Es el alcance del Coordinador y del Referente de Becas. Un **administrador de
    programa** queda afuera aunque tenga ``becas.usuario.territorial``: su alcance
    es el programa entero, que ya incluye a esos territoriales. Sin esta guarda la
    rama territorial lo interceptaría y le devolvería 0 usuarios, porque un admin
    no coordina ningún segmento.
    """
    return rbac.puede(user, "becas.usuario.territorial") and not programas_administrables_usuarios(user).exists()


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
    if es_gestor_territorial(user):
        from django.contrib.auth.models import Group

        from programas.services.autorizacion import (
            grupos_territoriales_becas,
            segmentos_para_gestion_territoriales,
        )

        roles_territoriales = grupos_territoriales_becas()
        roles_no_territoriales = Group.objects.exclude(pk__in=roles_territoriales)
        visibles = (
            qs.filter(
                groups__in=roles_territoriales,
                asignacion_territorial__segmento__in=segmentos_para_gestion_territoriales(user),
            )
            .exclude(groups__in=roles_no_territoriales)
            .distinct()
        )
        return visibles
    programas = programas_administrables_usuarios(user)
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
    if es_gestor_territorial(user):
        from programas.services.autorizacion import grupos_territoriales_becas

        return set(grupos_territoriales_becas().values_list("id", flat=True))
    from users.forms import _roles_asignables_queryset

    return set(_roles_asignables_queryset(user).values_list("id", flat=True))


def puede_gestionar_usuario(operador, target):
    """¿El operador puede editar a ``target`` según su alcance?

    Admin global: siempre. Admin de programa: solo si el usuario tiene al menos
    un rol de alguno de los programas que administra.
    """
    if es_admin_global_usuarios(operador):
        return True
    if es_gestor_territorial(operador):
        from programas.services.autorizacion import (
            grupos_territoriales_becas,
            segmentos_para_gestion_territoriales,
        )

        roles = set(target.groups.values_list("pk", flat=True))
        roles_territoriales = set(grupos_territoriales_becas().values_list("pk", flat=True))
        es_solo_territorial = bool(roles) and roles.issubset(roles_territoriales)
        asignacion = getattr(target, "asignacion_territorial", None)
        permitido = bool(
            es_solo_territorial
            and asignacion
            and segmentos_para_gestion_territoriales(operador).filter(pk=asignacion.segmento_id).exists()
        )
        return permitido
    programas = set(programas_administrables_usuarios(operador).values_list("pk", flat=True))
    return target.groups.filter(meta__programa__in=programas, meta__activo=True).exists()
