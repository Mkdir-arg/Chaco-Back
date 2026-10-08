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
    un rol de alguno de los programas que administra, **y** no es una cuenta que
    lo excede (SEC-03): superusuario, admin global o admin de otro programa. Sin
    esa guarda alcanzaba con compartir un rol operativo para tomarle la cuenta.
    """
    if es_admin_global_usuarios(operador):
        return True
    # SEC-03: ningún alcance acotado llega a una cuenta que lo excede.
    if target.is_superuser or rbac.puede_alguna(target, rbac.CAPS_ADMINISTRACION):
        return False
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
    # Admin de OTRO programa (o de todos, con un rol global): compartir un rol
    # operativo no lo pone bajo el alcance de este operador.
    codenames_admin = [rbac.codename_de(c) for c in rbac.CAPS_ADMIN_PROGRAMA]
    if (
        target.groups.filter(meta__activo=True, permissions__codename__in=codenames_admin)
        .exclude(meta__programa__in=programas)
        .exists()
    ):
        return False
    return target.groups.filter(meta__programa__in=programas, meta__activo=True).exists()


def puede_gestionar_credenciales(operador, target):
    """¿El operador puede tocar usuario, correo y contraseña de ``target``, y activarlo?

    Para los roles alcanza con que el usuario tenga **un** rol del programa: el
    guardado es acotado y no pisa lo de afuera. Las credenciales y el estado de la
    cuenta, en cambio, son la cuenta entera, así que exigen que **todos** los roles
    del target estén dentro del alcance del operador (SEC-03, decisión D-03 de la
    auditoría oct-2026). El admin global no tiene restricción.
    """
    if operador is None or not getattr(target, "pk", None):
        return True
    if not puede_gestionar_usuario(operador, target):
        return False
    alcance = alcance_roles_ids_credenciales(operador)
    if alcance is None:  # admin global
        return True
    return not target.groups.exclude(pk__in=alcance).exists()


def alcance_roles_ids_credenciales(operador):
    """IDs de roles que **no** sacan al usuario del alcance del operador (SEC-03).

    Es el alcance de :func:`alcance_roles_ids` más los roles **desactivados** de
    los mismos programas. La diferencia es R0b-02: un rol inactivo no otorga nada
    *hoy*, pero alguien puede reactivarlo mañana, y entonces el usuario recupera
    un acceso con una clave que puso el admin de otro programa —el vector de
    G1b-01—. Así que un rol inactivo **de otro programa** sí saca del alcance.

    Lo que no cambia: un rol inactivo **del propio programa** del operador sigue
    estando bajo su alcance. Contarlo como ajeno (que es como se lee la propuesta
    literal de la ficha, «sacar el `exclude`») dejaba a un admin de Becas sin
    poder tocar las credenciales de su propio usuario por un rol de Becas que
    alguien desactivó.
    """
    if es_admin_global_usuarios(operador):
        return None
    if es_gestor_territorial(operador):
        from programas.services.autorizacion import grupos_territoriales_becas

        return set(grupos_territoriales_becas().values_list("id", flat=True))
    from django.contrib.auth.models import Group

    programas = programas_administrables_usuarios(operador)
    # Sin `meta__activo=True` y sin excluir Portal: acá no se pregunta qué puede
    # asignar, sino qué roles del target **no** lo exceden.
    return set(Group.objects.filter(meta__programa__in=programas).values_list("id", flat=True))


def _usuarios_con_token_de_app(usuarios):
    """IDs de los que tienen una sesión abierta en la app de campo.

    Una sola consulta por página: «Cerrar sesión de la app» solo se ofrece sobre
    quien de verdad tiene un token, para que el botón no aparezca en todas las
    filas del backoffice —donde no significa nada— (SEC-26).
    """
    from rest_framework.authtoken.models import Token

    return set(Token.objects.filter(user__in=[u.pk for u in usuarios]).values_list("user_id", flat=True))


def anotar_acciones_del_listado(operador, usuarios):
    """Marca ``gestionable``, ``credenciales_editables`` y ``tiene_token_app`` en cada fila.

    R0b-10: el servidor ya rechaza editar o activar a quien excede el alcance
    (SEC-03), pero la pantalla mostraba igual el lápiz y el interruptor sobre un
    superusuario o un multiprograma, y recién al apretarlos aparecía el aviso.

    Se calcula **en lote**: un puñado de consultas acotadas a los roles que la
    página ya trae, no una por fila. La autoridad sigue siendo la vista; esto
    solo evita ofrecer un botón que va a rebotar.
    """
    usuarios = list(usuarios)
    if not usuarios:
        return usuarios
    con_token = _usuarios_con_token_de_app(usuarios)
    for usuario in usuarios:
        usuario.tiene_token_app = usuario.pk in con_token
    if es_admin_global_usuarios(operador):
        for usuario in usuarios:
            usuario.gestionable = True
            usuario.credenciales_editables = True
        return usuarios

    from django.contrib.auth.models import Group

    # Los grupos salen del prefetch del listado: no agrega consultas.
    roles_por_usuario = {usuario.pk: {grupo.pk for grupo in usuario.groups.all()} for usuario in usuarios}
    ids_en_juego = set().union(*roles_por_usuario.values()) if roles_por_usuario else set()
    alcance_credenciales = alcance_roles_ids_credenciales(operador)

    if es_gestor_territorial(operador):
        from programas.models import AsignacionTerritorial
        from programas.services.autorizacion import (
            grupos_territoriales_becas,
            segmentos_para_gestion_territoriales,
        )

        territoriales = set(grupos_territoriales_becas().values_list("pk", flat=True))
        segmentos = set(segmentos_para_gestion_territoriales(operador).values_list("pk", flat=True))
        asignado = dict(
            AsignacionTerritorial.objects.filter(territorial__in=[u.pk for u in usuarios]).values_list(
                "territorial_id", "segmento_id"
            )
        )
        for usuario in usuarios:
            roles = roles_por_usuario[usuario.pk]
            usuario.gestionable = bool(
                not usuario.is_superuser and roles and roles <= territoriales and asignado.get(usuario.pk) in segmentos
            )
            usuario.credenciales_editables = usuario.gestionable and not (roles - alcance_credenciales)
        return usuarios

    programas = set(programas_administrables_usuarios(operador).values_list("pk", flat=True))
    codenames_globales = [rbac.codename_de(c) for c in rbac.CAPS_ADMINISTRACION]
    codenames_programa = [rbac.codename_de(c) for c in rbac.CAPS_ADMIN_PROGRAMA]
    activos = set(Group.objects.filter(pk__in=ids_en_juego, meta__activo=True).values_list("pk", flat=True))
    admin_global = set(
        Group.objects.filter(
            pk__in=ids_en_juego, meta__activo=True, permissions__codename__in=codenames_globales
        ).values_list("pk", flat=True)
    )
    admin_programa = dict(
        Group.objects.filter(
            pk__in=ids_en_juego, meta__activo=True, permissions__codename__in=codenames_programa
        ).values_list("pk", "meta__programa_id")
    )
    del_programa = dict(Group.objects.filter(pk__in=ids_en_juego).values_list("pk", "meta__programa_id"))

    for usuario in usuarios:
        roles = roles_por_usuario[usuario.pk]
        # Mismo orden de preguntas que `puede_gestionar_usuario`.
        excede = usuario.is_superuser or bool(roles & admin_global)
        # Un rol de administración **sin** programa (categoría Backoffice/Sistema)
        # también excede: es lo que hace el `exclude(meta__programa__in=…)` del
        # selector, donde el `NULL` no queda excluido.
        excede = excede or any(rol in admin_programa and admin_programa[rol] not in programas for rol in roles)
        en_alcance = any(rol in activos and del_programa.get(rol) in programas for rol in roles)
        usuario.gestionable = bool(not excede and en_alcance)
        usuario.credenciales_editables = usuario.gestionable and not (roles - alcance_credenciales)
    return usuarios
