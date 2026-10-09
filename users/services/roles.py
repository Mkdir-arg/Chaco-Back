"""Servicio de administración de Roles (Group + RolMeta + capacidades)."""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from core import rbac
from programas.models import AsignacionDispositivo
from users.models import Capacidad, RolMeta


class RolProtegidoError(Exception):
    """No se puede editar/eliminar/desactivar un rol protegido."""


def _set_capacidades(group, codigos, permitidas=None, programa=None):
    """Deja el rol con ``codigos``, **conservando** lo que el operador no podía tocar.

    G1b-06: el ``permissions.set()`` crudo reemplazaba el conjunto entero, y el POST de
    un admin de programa solo trae lo que su árbol le mostró. Resultado: el admin global
    agregaba ``ciudadano.ver`` a un rol de Becas y el admin de roles de Becas lo borraba
    sin enterarse, cambiando la descripción. Con ``permitidas`` (lo que ese operador sí
    puede tildar, de :func:`core.rbac.capacidades_delegables`) el conjunto final es
    ``(actuales − permitidas) ∪ seleccionadas``.

    ``permitidas=None`` es el admin global: él sí ve y decide todo el catálogo, así que
    lo que no mandó es lo que quiso sacar.

    ``programa`` es el del rol **después** de guardar: lo que no se puede asignar ahí
    (:func:`core.rbac.capacidades_fuera_del_programa`) se cae del conjunto final. Sin
    eso, mover «Operativo Becas» a Dispositivos le dejaba `becas.programa.administrar`
    y `becas.segmento.ver` —la fórmula de G1b-06 las trata como «lo que el operador no
    ve», y el admin global ni siquiera las mandó—: hoy no otorgan nada porque los gates
    evalúan con alcance, pero reintroducen el dato que ``users.0031`` acaba de limpiar y
    nadie lo vuelve a limpiar. Con ``programa=None`` (rol que no es de programa) no se
    filtra nada.
    """
    ct = ContentType.objects.get_for_model(Capacidad)
    finales = set(codigos)
    if permitidas is not None:
        finales |= {c for c in rbac.capacidades_de_grupo(group) if c not in permitidas}
    finales -= rbac.capacidades_fuera_del_programa(programa)
    codenames = [rbac.codename_de(c) for c in finales]
    perms = Permission.objects.filter(content_type=ct, codename__in=codenames)
    group.permissions.set(list(perms))


def _meta(group):
    meta, _ = RolMeta.objects.get_or_create(grupo=group)
    return meta


def asegurar_rol_sembrado(clave, nombre, defaults):
    """Rol que crea el arranque, identificado por su **clave estable** (OPS-06 fase 2).

    Devuelve ``(group, meta, recien_creado)``. Lo busca primero por ``RolMeta.clave``:
    así un rol renombrado desde el ABM sigue siendo el mismo y el arranque no crea un
    duplicado con el nombre canónico. Solo si ninguna fila tiene la clave cae al nombre
    —lo que pasa en una base nueva, o en una donde ``users.0030`` no pudo empatar porque
    el rol ya estaba renombrado— y en ese caso se la deja puesta, así que a partir del
    segundo arranque el nombre deja de importar.

    ``defaults`` se aplica **solo al crear** la ``RolMeta``: descripción, activo y
    protegido de un rol existente son del ABM (D-O06, Cambio 104).
    """
    meta = RolMeta.objects.filter(clave=clave).select_related("grupo").first()
    if meta is not None:
        return meta.grupo, meta, False
    group, grupo_creado = Group.objects.get_or_create(name=nombre)
    meta, _ = RolMeta.objects.get_or_create(grupo=group, defaults={**defaults, "clave": clave})
    if meta.clave is None:
        meta.clave = clave
        meta.save(update_fields=["clave"])
    return group, meta, grupo_creado


def _sincronizar_alcance_dispositivos(group, dispositivos):
    """Mantiene las asignaciones activas del rol sin borrar su historial."""

    ids = [dispositivo.pk for dispositivo in dispositivos]
    asignaciones = AsignacionDispositivo.objects.filter(rol=group)
    asignaciones.exclude(dispositivo_id__in=ids).update(activo=False)
    for dispositivo_id in ids:
        asignacion, _ = AsignacionDispositivo.objects.get_or_create(
            rol=group,
            dispositivo_id=dispositivo_id,
        )
        if not asignacion.activo:
            asignacion.activo = True
            asignacion.save(update_fields=["activo", "modificado"])


def _administra_el_sistema(group):
    """¿Este rol otorga alguna capacidad de administración **global**?

    La contracara de :func:`_programa_que_administra` para el check sin programa
    (G1b-07): desactivar un rol así deja de otorgar `usuario.administrar` /
    `rol.administrar`, igual que borrarlo.
    """
    return not set(rbac.CAPS_ADMINISTRACION).isdisjoint(rbac.capacidades_de_grupo(group))


def _programa_que_administra(group):
    """Programa que este rol administra hoy, o ``None``.

    Un rol "administra" un programa si es de categoría 'Programa', tiene
    ``programa`` y alguna capacidad de ``rbac.CAPS_ADMIN_PROGRAMA`` tildada. Se
    usa para el check scoped de "programa sin administrador" (RN-8)."""
    meta = getattr(group, "meta", None)
    if (
        meta
        and meta.categoria == rbac.CATEGORIA_PROGRAMA
        and meta.programa_id
        and not set(rbac.CAPS_ADMIN_PROGRAMA).isdisjoint(rbac.capacidades_de_grupo(group))
    ):
        return meta.programa
    return None


class RolesAdminService:
    @staticmethod
    @transaction.atomic
    def crear(form):
        # G1b-09 (ronda 3): crear un rol no puede dejar al sistema sin administradores,
        # así que acá el candado no está por el check sino por el **orden de los locks**.
        # `_set_capacidades` escribe `auth_group_permissions` y por la FK InnoDB pide un
        # lock sobre filas sueltas de `auth_permission`, en el orden en que recorre las
        # capacidades tildadas; el candado bloquea las suyas recorriendo el índice
        # `(content_type_id, codename)`. Las dos cosas a la vez cierran el ciclo contra
        # cualquiera de los otros seis caminos: sin esta línea, 11-14 deadlocks de 20
        # corridas en `mariadb:10.11` y 18-20 de 20 en `mysql:8.0` —`ERROR 1213`, que
        # ninguna vista atrapa, o sea 500— y 0 con ella (`CandadoSinDeadlockTests`).
        # Tomando el ancla primero, el `set()` arranca con esas filas ya suyas.
        rbac.tomar_candado_de_administracion()
        cd = form.cleaned_data
        group = Group.objects.create(name=cd["name"])
        RolMeta.objects.create(
            grupo=group,
            descripcion=cd.get("descripcion", ""),
            categoria=cd["categoria"],
            programa=cd.get("programa"),
            activo=True,
            protegido=False,
        )
        _set_capacidades(group, cd.get("capacidades", []), programa=cd.get("programa"))
        _sincronizar_alcance_dispositivos(group, cd.get("dispositivos_alcance", []))
        return group

    @staticmethod
    @transaction.atomic
    def actualizar(form, group):
        if _meta(group).protegido:
            raise RolProtegidoError("El rol está protegido y no puede editarse.")
        # G1b-09: el candado va antes de leer y de escribir; tomarlo recién en
        # `asegurar_admin_restante` serializa pero deja el check contando sobre la foto vieja.
        rbac.tomar_candado_de_administracion()
        # Programa que este rol administraba ANTES del cambio (puede quedar
        # huérfano si la edición le saca la capacidad de administración o le cambia el programa).
        programa_previo = _programa_que_administra(group)
        cd = form.cleaned_data
        group.name = cd["name"]
        group.save()
        meta = _meta(group)
        meta.descripcion = cd.get("descripcion", "")
        meta.categoria = cd["categoria"]
        meta.programa = cd.get("programa")
        meta.save()
        _set_capacidades(
            group,
            cd.get("capacidades", []),
            getattr(form, "capacidades_permitidas", None),
            programa=cd.get("programa"),
        )
        _sincronizar_alcance_dispositivos(group, cd.get("dispositivos_alcance", []))
        # Si la edición quitó usuario.administrar/rol.administrar y dejaría al
        # sistema sin admins, revierte la transacción.
        rbac.asegurar_admin_restante()
        if programa_previo is not None:
            rbac.asegurar_admin_restante(programa=programa_previo)
        return group

    @staticmethod
    @transaction.atomic
    def eliminar(group):
        if _meta(group).protegido:
            raise RolProtegidoError("El rol está protegido y no puede eliminarse.")
        # G1b-09: el candado va antes de leer y de escribir; tomarlo recién en
        # `asegurar_admin_restante` serializa pero deja el check contando sobre la foto vieja.
        rbac.tomar_candado_de_administracion()
        programa_previo = _programa_que_administra(group)
        # Al borrar el Group, Django desvincula a los usuarios (tabla intermedia)
        # y borra RolMeta por CASCADE.
        group.delete()
        rbac.asegurar_admin_restante()
        if programa_previo is not None:
            rbac.asegurar_admin_restante(programa=programa_previo)

    @staticmethod
    @transaction.atomic
    def toggle_activo(group):
        meta = _meta(group)
        if meta.protegido:
            raise RolProtegidoError("El rol está protegido y no puede desactivarse.")
        # G1b-09: el candado va antes de leer y de escribir; tomarlo recién en
        # `asegurar_admin_restante` serializa pero deja el check contando sobre la foto vieja.
        rbac.tomar_candado_de_administracion()
        # Capturar antes: si es un rol que administra un programa y se va a
        # desactivar, podría dejar ese programa sin administrador.
        programa_admin = _programa_que_administra(group)
        meta.activo = not meta.activo
        meta.save(update_fields=["activo"])
        # Desactivar un rol SÍ deja de otorgar sus capacidades (`rbac.puede` solo
        # mira roles activos), así que la desactivación vale lo mismo que borrarlo
        # a los efectos de quedarse sin administradores: se corren los dos checks,
        # el global y el del programa (G1b-07). Faltaba el global, y desactivar el
        # único rol no protegido con `usuario.administrar` dejaba el sistema sin
        # nadie que pudiera volver a tocar usuarios ni roles.
        if not meta.activo:
            # El check global solo si este rol es de los que otorgan administración:
            # desactivar un rol operativo no puede dejar al sistema sin admins, y
            # correrlo igual convertiría un sistema ya mal configurado (cero admins)
            # en uno donde tampoco se puede desactivar un rol cualquiera.
            if _administra_el_sistema(group):
                rbac.asegurar_admin_restante()
            if programa_admin is not None:
                rbac.asegurar_admin_restante(programa=programa_admin)
        return meta.activo

    @staticmethod
    def usuarios_afectados(group):
        """Cantidad de usuarios que tienen asignado el rol (para la confirmación)."""
        return group.user_set.count()
