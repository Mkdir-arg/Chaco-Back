"""Equipo de un dispositivo: quién trabaja ahí, con qué rol y quién lo arma (Cambio 410).

Reglas (decisiones del PM, 02-nov-2026):

* El Equipo es por **persona** (``MiembroEquipoDispositivo``): el alcance fino de quien opera
  un dispositivo sin ser admin del programa.
* Hay **varios responsables** por dispositivo; si ya tenía alguno, no se lo deja sin ninguno.
* Arman el Equipo el admin de Dispositivos y los responsables **de ese** dispositivo.
* El rol tiene que ser de un rol del programa Dispositivos y la persona tiene que tenerlo.
* Quien además administra los usuarios del programa Dispositivos puede **crear a la persona** que no
  está (Cambio 420), con un rol que la regla del ABM de Usuarios le deje dar, y sumarla en la misma
  transacción.

Las escrituras toman ``select_for_update`` sobre el dispositivo: dos altas o bajas
simultáneas no pueden dejarlo sin responsables.
"""

from collections import namedtuple

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import BooleanField, Case, Prefetch, Value, When, prefetch_related_objects

from core import rbac
from programas.services.dispositivos import (
    membresias_vigentes,
    nombre_de_persona,
    programa_dispositivos,
    puede_configurar_dispositivos,
    q_membresia_vigente,
    responsables_vigentes,
)
from programas.services.inspecciones import CLAVE_ROL_AGENTE


def puede_gestionar_equipo(user, dispositivo):
    """Admin del programa Dispositivos o responsable activo de ese dispositivo."""

    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if puede_configurar_dispositivos(user):
        return True
    return (
        membresias_vigentes(user, programa_dispositivos(user))
        .filter(dispositivo=dispositivo, es_responsable=True)
        .exists()
    )


def puede_administrar_usuarios_dispositivos(user):
    """Superusuario, ``usuario.administrar`` o ``programa.usuario.administrar`` **acotado a Dispositivos**.

    Es el alcance del ABM de Usuarios (``programas_administrables_usuarios``): la misma definición que
    acota los roles que se pueden dar, así que quien pasa esta puerta no queda con el combo vacío por otra regla.
    """

    if user is None or not getattr(user, "is_authenticated", False) or not user.is_active:
        return False
    if rbac.puede(user, "usuario.administrar"):
        return True
    programa = programa_dispositivos(user)
    return programa is not None and rbac.puede(user, "programa.usuario.administrar", programa=programa)


def puede_crear_persona(user, dispositivo, gestiona=None):
    """«Crear persona» desde el Equipo: gestiona **este** Equipo y administra los usuarios de Dispositivos.

    ``gestiona`` es ``puede_gestionar_equipo`` si quien llama ya lo resolvió (``permisos_del_equipo``).
    """

    if gestiona is None:
        gestiona = puede_gestionar_equipo(user, dispositivo)
    return gestiona and puede_administrar_usuarios_dispositivos(user)


def roles_para_crear_persona(actor):
    """Roles con los que el ``actor`` puede dar de alta a una persona nueva en el Equipo.

    Parte de la regla del ABM de Usuarios (``roles_asignables``: no se da un rol con capacidades que el
    actor no puede asignar) y la acota al programa Dispositivos, sin el rol de agente de relevamiento.
    """

    from django.contrib.auth.models import Group

    from users.selectors.usuarios import roles_asignables

    programa = programa_dispositivos()
    if programa is None:
        return Group.objects.none()
    return roles_asignables(actor).filter(meta__programa=programa).exclude(meta__clave=CLAVE_ROL_AGENTE)


def _exigir_gestion(actor, dispositivo):
    if not puede_gestionar_equipo(actor, dispositivo):
        raise PermissionDenied("Solo el admin de Dispositivos o un responsable del dispositivo arma el Equipo.")


def _bloquear(dispositivo):
    from programas.models import Dispositivo

    return Dispositivo.objects.select_for_update().get(pk=dispositivo.pk)


def _exigir_pares_sumables(programa, pares):
    """Todos los ``(usuario, rol)`` son opciones de ``pares_persona_rol`` (Cambio 414).

    Es el único validador de quién se puede sumar al Equipo: usuario activo, rol activo del
    programa Dispositivos que la persona tiene y que no es el de agente de relevamiento. Mira solo
    las personas y roles elegidos, no todo el padrón.
    """

    pares = list(pares)
    if programa is None or not pares:
        raise ValidationError("Elegí personas y roles del listado.")
    validos = set(
        get_user_model()
        .groups.through.objects.filter(
            user__is_active=True,
            group__meta__activo=True,
            group__meta__programa=programa,
            user_id__in={usuario.pk for usuario, _ in pares},
            group_id__in={rol.pk for _, rol in pares},
        )
        .exclude(group__meta__clave=CLAVE_ROL_AGENTE)
        .values_list("user_id", "group_id")
    )
    if any((usuario.pk, rol.pk) not in validos for usuario, rol in pares):
        raise ValidationError("Elegí personas y roles del listado.")


def exigir_par_sumable(usuario, rol):
    """Falla con ``ValidationError`` si ``(usuario, rol)`` no es una opción de ``pares_persona_rol``."""

    _exigir_pares_sumables(programa_dispositivos(), [(usuario, rol)])


def _edificios_que_gestiona(actor, dispositivo):
    """Los edificios en los que ``actor`` arma el Equipo: ``None`` = toda la institución, o un conjunto de ids (RN6).

    Admin del programa y responsable con alcance Institución (o sin alcance cargado): todo. Responsable solo con
    alcance Edificios: la unión de los que siguen vinculados al dispositivo; si no queda ninguno, el conjunto vacío.
    """

    from programas.models import Edificio, MiembroEquipoDispositivo

    if puede_configurar_dispositivos(actor):
        return None
    filas = list(
        membresias_vigentes(actor, programa_dispositivos(actor))
        .filter(dispositivo=dispositivo, es_responsable=True)
        .values_list("pk", "alcance")
    )
    if any(alcance != MiembroEquipoDispositivo.Alcance.EDIFICIOS for _pk, alcance in filas):
        return None
    return set(
        Edificio.objects.filter(miembros_equipo__in=[pk for pk, _a in filas], dispositivos=dispositivo).values_list(
            "pk", flat=True
        )
    )


PermisosEquipo = namedtuple("PermisosEquipo", "gestiona propios")


def permisos_del_equipo(actor, dispositivo):
    """``(gestiona, propios)`` de ``actor`` sobre este Equipo, para resolverlos **una vez** por request.

    ``gestiona`` es ``puede_gestionar_equipo``; ``propios`` es ``_edificios_que_gestiona`` (``None`` = toda la
    institución) y solo se lee si gestiona: quien no arma el Equipo no necesita saber de qué edificios.
    """

    gestiona = puede_gestionar_equipo(actor, dispositivo)
    return PermisosEquipo(gestiona, _edificios_que_gestiona(actor, dispositivo) if gestiona else None)


def _exigir_alcance_valido(dispositivo, alcance, edificios):
    """``EDIFICIOS`` exige al menos un edificio vinculado a la institución (RN2); ``INSTITUCION`` no lleva ninguno."""

    from programas.models import Edificio, MiembroEquipoDispositivo

    if alcance != MiembroEquipoDispositivo.Alcance.EDIFICIOS:
        return []
    ids = {getattr(e, "pk", e) for e in edificios or ()}
    if not ids:
        raise ValidationError({"edificios": "Elegí al menos un edificio para el alcance «Edificios»."})
    vinculados = set(Edificio.objects.filter(pk__in=ids, dispositivos=dispositivo).values_list("pk", flat=True))
    if vinculados != ids:
        raise ValidationError({"edificios": "Todos los edificios tienen que estar vinculados a la institución."})
    return sorted(ids)


def _exigir_dentro_de_mis_edificios(actor, dispositivo, alcance, edificio_ids):
    """Un responsable con alcance Edificios solo suma miembros Edificios dentro de sus propios edificios (RN6)."""

    from programas.models import MiembroEquipoDispositivo

    propios = _edificios_que_gestiona(actor, dispositivo)
    if propios is None:
        return
    if alcance != MiembroEquipoDispositivo.Alcance.EDIFICIOS or not set(edificio_ids) <= propios:
        raise PermissionDenied("Con alcance por edificio solo se arma el Equipo de tus propios edificios.")


def _exigir_miembro_dentro_de_mis_edificios(actor, dispositivo, miembro):
    """Editar o dar de baja a alguien también queda dentro de los edificios del responsable (RN6)."""

    from programas.models import MiembroEquipoDispositivo

    if _edificios_que_gestiona(actor, dispositivo) is None:
        return
    ids = list(miembro.edificios.values_list("pk", flat=True))
    alcance = miembro.alcance or MiembroEquipoDispositivo.Alcance.INSTITUCION
    _exigir_dentro_de_mis_edificios(actor, dispositivo, alcance, ids)


def opciones_de_alcance(actor, dispositivo, permisos=None):
    """Lo que el modal del Equipo ofrece a ``actor``: ``{"alcances": [(valor, etiqueta)], "edificios": [(pk, nombre)]}``.

    Es solo presentación de lo que el servidor va a aceptar (RN6): el admin ofrece toda la institución y los edificios
    vinculados; el responsable con alcance Edificios, solo «Edificios» y los suyos. Sin edificios vinculados no se ofrece
    «Edificios» (no habría qué elegir). La autorización la sigue haciendo cada escritura. ``permisos`` es
    ``permisos_del_equipo`` si quien llama ya lo resolvió.
    """

    from programas.models import MiembroEquipoDispositivo

    Alcance = MiembroEquipoDispositivo.Alcance
    propios = permisos.propios if permisos is not None else _edificios_que_gestiona(actor, dispositivo)
    vinculados = dispositivo.edificios.order_by("nombre")
    if propios is not None:
        vinculados = vinculados.filter(pk__in=propios)
    edificios = list(vinculados.values_list("pk", "nombre"))
    if propios is not None:
        alcances = [(Alcance.EDIFICIOS.value, Alcance.EDIFICIOS.label)] if edificios else []
    elif edificios:
        alcances = list(Alcance.choices)
    else:
        alcances = [(Alcance.INSTITUCION.value, Alcance.INSTITUCION.label)]
    return {"alcances": alcances, "edificios": edificios}


def edificios_donde_agregar_persona(actor, dispositivo, permisos=None):
    """Dónde ofrece «Agregar persona al edificio»: ``None`` = en todos, o el conjunto de ids (vacío = en ninguno).

    La misma regla que valida ``_exigir_alta_en_edificio``: gestiona el Equipo, el dispositivo no está cerrado y,
    con alcance Edificios, solo en los propios (RN6). ``permisos`` es ``permisos_del_equipo`` si ya se resolvió.
    """

    from programas.models import Dispositivo

    if permisos is None:
        permisos = permisos_del_equipo(actor, dispositivo)
    if dispositivo.estado == Dispositivo.Estado.CERRADO or not permisos.gestiona:
        return set()
    return permisos.propios


def _exigir_alta_en_edificio(actor, dispositivo, edificio_id):
    """Cerrado, edificio ajeno o fuera de los edificios de ``actor``: falla. Con el dispositivo ya bloqueado."""

    from programas.models import Dispositivo, MiembroEquipoDispositivo

    Alcance = MiembroEquipoDispositivo.Alcance
    if dispositivo.estado == Dispositivo.Estado.CERRADO:
        raise ValidationError("El dispositivo está cerrado: no se suman personas a su Equipo.")
    _exigir_alcance_valido(dispositivo, Alcance.EDIFICIOS, [edificio_id])
    _exigir_dentro_de_mis_edificios(actor, dispositivo, Alcance.EDIFICIOS, [edificio_id])


RESULTADO_SUMADA = "sumada"
RESULTADO_AGREGADA = "agregada"
RESULTADO_YA_ALCANZA = "ya_alcanza"


def sumar_miembro_en_edificio(
    *, actor, dispositivo, usuario, rol, edificio_id, es_responsable=False, tipo_contratacion=None
):
    """«Agregar persona al edificio»: suma a ``usuario`` con alcance Edificios en ``edificio_id``.

    Devuelve ``(miembro, resultado)``. Si no estaba (o estaba de baja) entra con alcance Edificios y ese edificio. Si ya
    está activa con alcance Edificios, se le suma el edificio a su fila. Si ya tiene toda la institución (o el edificio
    ya estaba) no se cambia nada: ``RESULTADO_YA_ALCANZA``. Un responsable con alcance Edificios solo opera sus edificios.
    """

    from programas.models import MiembroEquipoDispositivo

    with transaction.atomic():
        dispositivo = _bloquear(dispositivo)
        _exigir_gestion(actor, dispositivo)
        _exigir_alta_en_edificio(actor, dispositivo, edificio_id)
        _exigir_pares_sumables(programa_dispositivos(), [(usuario, rol)])
        miembro = (
            MiembroEquipoDispositivo.objects.select_for_update()
            .filter(dispositivo=dispositivo, usuario=usuario, rol=rol, activo=True)
            .first()
        )
        if miembro is None:
            miembro = _sumar_miembro_bloqueado(
                actor=actor,
                dispositivo=dispositivo,
                usuario=usuario,
                rol=rol,
                es_responsable=es_responsable,
                tipo_contratacion=tipo_contratacion,
                alcance=MiembroEquipoDispositivo.Alcance.EDIFICIOS,
                edificio_ids=[edificio_id],
            )
            return miembro, RESULTADO_SUMADA
        if miembro.alcance != MiembroEquipoDispositivo.Alcance.EDIFICIOS:
            return miembro, RESULTADO_YA_ALCANZA
        _exigir_miembro_dentro_de_mis_edificios(actor, dispositivo, miembro)
        if miembro.edificios.filter(pk=edificio_id).exists():
            return miembro, RESULTADO_YA_ALCANZA
        miembro.edificios.add(edificio_id)
        return miembro, RESULTADO_AGREGADA


def cambiar_alcance(*, actor, miembro, alcance, edificios=()):
    """Cambia el alcance de una persona activa del Equipo: toda la institución o los ``edificios`` elegidos (RN2, RN6)."""

    from programas.models import MiembroEquipoDispositivo

    with transaction.atomic():
        dispositivo = _bloquear(miembro.dispositivo)
        _exigir_gestion(actor, dispositivo)
        miembro = MiembroEquipoDispositivo.objects.select_for_update().get(pk=miembro.pk)
        if not miembro.activo:
            raise ValidationError("La persona está de baja en el Equipo.")
        _exigir_miembro_dentro_de_mis_edificios(actor, dispositivo, miembro)
        alcance = alcance or MiembroEquipoDispositivo.Alcance.INSTITUCION
        edificio_ids = _exigir_alcance_valido(dispositivo, alcance, edificios)
        _exigir_dentro_de_mis_edificios(actor, dispositivo, alcance, edificio_ids)
        miembro.alcance = alcance
        miembro.save(update_fields=["alcance", "modificado"])
        miembro.edificios.set(edificio_ids)
        return miembro


MIEMBROS_SIN_EDIFICIOS = (
    "No se puede desvincular el edificio: dejaría sin ningún edificio a {personas}, que en el Equipo tiene{plural} "
    "alcance por edificio y no vería nada. Dalo{plural_lo} de baja del Equipo o cambiá su alcance antes de "
    "desvincularlo."
)


def soltar_edificio_del_equipo(dispositivo, edificio):
    """Quita ``edificio`` del alcance del Equipo antes de desvincularlo, o rechaza si alguien quedaría sin ninguno.

    Rechaza (``ValidationError`` con el nombre de las personas) si deja a alguien con membresía **vigente** y con alcance
    Edificios sin ningún edificio vigente: no vería nada (fail-closed, Cambio 523) y nadie se enteraría. Se mira por
    **persona**, como `alcance_de_edificios`: quien tiene otra fila vigente (`q_membresia_vigente`: activa, con rol
    activo del programa y todavía asignado) con toda la institución (o sin alcance cargado), o con otro edificio que sigue vinculado, no pierde nada. Si nadie queda ciego, le saca solo este
    edificio a cada fila que lo tenga (también a las de baja) y no toca nada más. Todo o nada: el rechazo ocurre
    antes de escribir.

    Lo llama `edificios.desvincular_edificio` ya con el bloqueo del dispositivo tomado, el mismo con el que
    arrancan `sumar_miembro` y `dar_de_baja`: una alta concurrente no puede meter este edificio en un alcance
    entre la lectura y el ``remove()``; si entra antes, esta lectura la ve; si entra después, el edificio ya no
    está vinculado y `sumar_miembro` la rechaza. Una consulta si el edificio no estaba en el alcance de nadie.
    """

    from programas.models import MiembroEquipoDispositivo

    Alcance = MiembroEquipoDispositivo.Alcance
    vigente = q_membresia_vigente(programa_dispositivos())
    filas = list(
        MiembroEquipoDispositivo.objects.filter(dispositivo=dispositivo, edificios=edificio)
        .annotate(vigente=Case(When(vigente, then=Value(True)), default=Value(False), output_field=BooleanField()))
        .values_list("pk", "usuario_id", "vigente", "alcance")
    )
    if not filas:
        return
    candidatos = {
        usuario_id for _pk, usuario_id, vigente_, alcance in filas if vigente_ and alcance == Alcance.EDIFICIOS
    }
    if candidatos:
        activas = list(
            MiembroEquipoDispositivo.objects.filter(
                vigente, dispositivo=dispositivo, usuario_id__in=candidatos
            ).values_list("pk", "usuario_id", "alcance")
        )
        con_todo = {usuario_id for _pk, usuario_id, alcance in activas if alcance != Alcance.EDIFICIOS}
        vigentes = dispositivo.edificios.exclude(pk=edificio.pk).values("pk")
        con_otro = set(
            MiembroEquipoDispositivo.edificios.through.objects.filter(
                miembroequipodispositivo_id__in=[pk for pk, _u, _a in activas], edificio_id__in=vigentes
            ).values_list("miembroequipodispositivo__usuario_id", flat=True)
        )
        ciegos = candidatos - con_todo - con_otro
        if ciegos:
            personas = get_user_model().objects.filter(pk__in=ciegos).order_by("last_name", "first_name", "username")
            nombres = [nombre_de_persona(persona) for persona in personas]
            plural = len(nombres) > 1
            raise ValidationError(
                {
                    "__all__": MIEMBROS_SIN_EDIFICIOS.format(
                        personas=", ".join(nombres), plural="n" if plural else "", plural_lo="s" if plural else ""
                    )
                }
            )
    MiembroEquipoDispositivo.edificios.through.objects.filter(
        miembroequipodispositivo_id__in=[pk for pk, *_ in filas], edificio_id=edificio.pk
    ).delete()


def _exigir_otro_responsable(dispositivo, miembro):
    """No dejar sin responsables a un dispositivo que tenía: queda al menos otro activo."""

    es_responsable_activo = miembro.activo and miembro.es_responsable
    if es_responsable_activo and not responsables_vigentes(dispositivo).exclude(pk=miembro.pk).exists():
        raise ValidationError("El dispositivo no puede quedar sin responsables: marcá a otra persona antes.")


def sumar_miembro(
    *,
    actor,
    dispositivo,
    usuario,
    rol,
    es_responsable=False,
    tipo_contratacion=None,
    alcance=None,
    edificios=(),
    edificio_fijo=None,
):
    """Suma a ``usuario`` con ``rol``; si la fila existía de baja, la reactiva.

    ``alcance`` (``INSTITUCION`` o ``EDIFICIOS``; ``None`` = toda la institución) y ``edificios`` (obligatorios con
    ``EDIFICIOS``, vinculados a la institución) son los del puesto. Un responsable con alcance Edificios solo suma
    miembros Edificios dentro de los suyos. ``edificio_fijo`` (el alta que nace en un edificio) exige además que se pueda
    sumar gente ahí: dispositivo abierto, edificio vinculado y propio de ``actor``.
    """

    with transaction.atomic():
        dispositivo = _bloquear(dispositivo)
        if edificio_fijo is not None:
            _exigir_alta_en_edificio(actor, dispositivo, edificio_fijo)
        edificio_ids = _exigir_compuertas_de_alta(actor, dispositivo, usuario, rol, alcance, edificios)
        return _sumar_miembro_bloqueado(
            actor=actor,
            dispositivo=dispositivo,
            usuario=usuario,
            rol=rol,
            es_responsable=es_responsable,
            tipo_contratacion=tipo_contratacion,
            alcance=alcance,
            edificio_ids=edificio_ids,
        )


def _exigir_compuertas_de_alta(actor, dispositivo, usuario, rol, alcance, edificios):
    """Gestión, par sumable y alcance (RN2, RN6) con el dispositivo bloqueado. Devuelve los ids de edificio validados."""

    _exigir_gestion(actor, dispositivo)
    _exigir_pares_sumables(programa_dispositivos(), [(usuario, rol)])
    edificio_ids = _exigir_alcance_valido(dispositivo, alcance, edificios)
    _exigir_dentro_de_mis_edificios(actor, dispositivo, alcance, edificio_ids)
    return edificio_ids


def _sumar_miembro_bloqueado(
    *, actor, dispositivo, usuario, rol, es_responsable, tipo_contratacion, alcance, edificio_ids
):
    """Escribe la fila: transacción abierta, dispositivo bloqueado y compuertas ya pasadas por quien llama."""

    from programas.models import MiembroEquipoDispositivo

    miembro, creado = MiembroEquipoDispositivo.objects.get_or_create(
        dispositivo=dispositivo,
        usuario=usuario,
        rol=rol,
        defaults={"es_responsable": es_responsable, "tipo_contratacion": tipo_contratacion, "alcance": alcance},
    )
    if not creado and miembro.activo:
        # Volver a sumar a alguien activo no le toca el puesto: si es de otro edificio, no es del responsable (RN6).
        _exigir_miembro_dentro_de_mis_edificios(actor, dispositivo, miembro)
    if creado or not miembro.activo:
        # Alta nueva o reactivación: el alcance que se elige ahora reemplaza al anterior.
        miembro.alcance = alcance
        miembro.edificios.set(edificio_ids)
    if not creado:
        estaba_de_baja = not miembro.activo
        miembro.activo = True
        # De baja vuelve como se pide; si ya estaba activa (dos altas a la vez) no se le saca la marca.
        miembro.es_responsable = es_responsable if estaba_de_baja else miembro.es_responsable or es_responsable
        if estaba_de_baja and tipo_contratacion:
            # Reactivar es un alta nueva del puesto: manda la contratación que se elige ahora.
            miembro.tipo_contratacion = tipo_contratacion
        miembro.save(update_fields=["activo", "es_responsable", "tipo_contratacion", "alcance", "modificado"])
    return miembro


def datos_de_alta_de_persona(*, actor, dni, nombre, apellido, correo, rol):
    """El ``UserCreationForm`` del ABM de Usuarios armado para el alta de una persona del Equipo.

    No hay una regla paralela: es el formulario del ABM, con los roles acotados a ``roles_para_crear_persona``
    (el rol elegido tiene que estar ahí) y el operador, que valida DNI, correo y que el rol no se pise.
    La clave la genera el sistema y llega por enlace al correo: no se pide ni se muestra una provisoria.
    El usuario se llama como el DNI (o ``<dni>-<n>`` si ese nombre ya lo tiene otra cuenta).
    """

    from django.http import QueryDict

    from users.forms import UserCreationForm

    username = str(dni)
    ocupado = get_user_model().objects.filter(username__iexact=username).exists()
    numero = 1
    while ocupado:
        numero += 1
        username = f"{dni}-{numero}"
        ocupado = get_user_model().objects.filter(username__iexact=username).exists()
    datos = QueryDict(mutable=True)
    datos.update({"username": username, "email": correo, "first_name": nombre, "last_name": apellido, "dni": dni})
    datos.setlist("groups", [str(rol.pk)])
    return UserCreationForm(data=datos, operador=actor, roles_acotados=roles_para_crear_persona(actor))


def crear_persona_y_sumar(
    *,
    actor,
    dispositivo,
    alta,
    rol,
    es_responsable=False,
    tipo_contratacion=None,
    alcance=None,
    edificios=(),
    edificio_fijo=None,
):
    """Crea el usuario de ``alta`` (``UserCreationForm`` válido) y lo suma al Equipo, **todo o nada**.

    Una sola transacción: si sumar al Equipo falla, no queda ni el usuario. La escritura del usuario es la
    de las altas rápidas (``UsuariosAdminService.create_user_from_form``). El correo con la clave no viaja
    acá: lo manda la vista cuando la transacción ya cerró. ``edificio_fijo`` («Crear persona» desde un edificio) se valida
    en ``sumar_miembro``, con el dispositivo bloqueado: cerrado, ajeno o fuera de los edificios de ``actor`` revierte
    también el usuario.
    """

    from users.selectors.usuarios import alcance_roles_ids
    from users.services.admin import UsuariosAdminService

    with transaction.atomic():
        if not puede_crear_persona(actor, dispositivo):
            raise PermissionDenied("Solo quien administra los usuarios de Dispositivos da de alta personas.")
        if not roles_para_crear_persona(actor).filter(pk=rol.pk).exists():
            raise ValidationError({"rol": "Ese rol no se puede dar al crear una persona."})
        usuario = UsuariosAdminService.create_user_from_form(alta, alcance_group_ids=alcance_roles_ids(actor))
        sumar_miembro(
            actor=actor,
            dispositivo=dispositivo,
            usuario=usuario,
            rol=rol,
            es_responsable=es_responsable,
            tipo_contratacion=tipo_contratacion,
            alcance=alcance,
            edificios=edificios,
            edificio_fijo=edificio_fijo,
        )
    return usuario


def sumar_responsables_al_crear(*, actor, dispositivo, pares):
    """Deja a ``pares`` (``[(usuario, rol)]``) como responsables de un dispositivo recién creado.

    Va dentro de la transacción del alta. Valida todo con ``_exigir_pares_sumables``, la misma definición que ofrece el
    formulario (``pares_persona_rol``) y escribe en una sola consulta, así que sumar a varios no
    cuesta más consultas por persona.
    """

    from programas.models import MiembroEquipoDispositivo

    with transaction.atomic():
        dispositivo = _bloquear(dispositivo)
        _exigir_gestion(actor, dispositivo)
        _exigir_pares_sumables(programa_dispositivos(), pares)
        MiembroEquipoDispositivo.objects.bulk_create(
            [
                MiembroEquipoDispositivo(dispositivo=dispositivo, usuario=usuario, rol=rol, es_responsable=True)
                for usuario, rol in dict.fromkeys(pares)
            ]
        )


def cambiar_rol(*, actor, miembro, rol_nuevo):
    """Pasa a la persona a otro rol del mismo dispositivo (conserva la marca de responsable)."""

    from programas.models import MiembroEquipoDispositivo

    with transaction.atomic():
        dispositivo = _bloquear(miembro.dispositivo)
        _exigir_gestion(actor, dispositivo)
        miembro = MiembroEquipoDispositivo.objects.select_for_update().get(pk=miembro.pk)
        _exigir_miembro_dentro_de_mis_edificios(actor, dispositivo, miembro)
        _exigir_pares_sumables(programa_dispositivos(), [(miembro.usuario, rol_nuevo)])
        if miembro.rol_id == rol_nuevo.pk:
            return miembro
        if MiembroEquipoDispositivo.objects.filter(
            dispositivo=dispositivo, usuario=miembro.usuario, rol=rol_nuevo
        ).exists():
            raise ValidationError("La persona ya está en el Equipo con ese rol.")
        miembro.rol = rol_nuevo
        miembro.save(update_fields=["rol", "modificado"])
        return miembro


def dar_de_baja(*, actor, miembro):
    from programas.models import MiembroEquipoDispositivo

    with transaction.atomic():
        dispositivo = _bloquear(miembro.dispositivo)
        _exigir_gestion(actor, dispositivo)
        miembro = MiembroEquipoDispositivo.objects.select_for_update().get(pk=miembro.pk)
        _exigir_miembro_dentro_de_mis_edificios(actor, dispositivo, miembro)
        if not miembro.activo:
            return miembro
        _exigir_otro_responsable(dispositivo, miembro)
        miembro.activo = False
        miembro.save(update_fields=["activo", "modificado"])
        return miembro


def marcar_responsable(*, actor, miembro):
    from programas.models import MiembroEquipoDispositivo

    with transaction.atomic():
        dispositivo = _bloquear(miembro.dispositivo)
        _exigir_gestion(actor, dispositivo)
        miembro = MiembroEquipoDispositivo.objects.select_for_update().get(pk=miembro.pk)
        _exigir_miembro_dentro_de_mis_edificios(actor, dispositivo, miembro)
        if not miembro.activo:
            raise ValidationError("La persona está de baja en el Equipo.")
        if not miembro.es_responsable:
            miembro.es_responsable = True
            miembro.save(update_fields=["es_responsable", "modificado"])
        return miembro


def desmarcar_responsable(*, actor, miembro):
    from programas.models import MiembroEquipoDispositivo

    with transaction.atomic():
        dispositivo = _bloquear(miembro.dispositivo)
        _exigir_gestion(actor, dispositivo)
        miembro = MiembroEquipoDispositivo.objects.select_for_update().get(pk=miembro.pk)
        _exigir_miembro_dentro_de_mis_edificios(actor, dispositivo, miembro)
        if not miembro.es_responsable:
            return miembro
        _exigir_otro_responsable(dispositivo, miembro)
        miembro.es_responsable = False
        miembro.save(update_fields=["es_responsable", "modificado"])
        return miembro


def pares_persona_rol(dispositivo=None):
    """Las opciones «Persona — Rol» que se pueden sumar al Equipo.

    Una por usuario activo × rol activo del programa Dispositivos que la persona **tiene**, sin
    el rol de agente de relevamiento (los agentes no integran el Equipo, decisión 5 del 410).
    Con ``dispositivo`` salen las que ya están activas ahí. Devuelve diccionarios
    ``{valor, usuario, rol, etiqueta}``; ``valor`` es ``"<usuario_pk>:<rol_pk>"``.
    """

    programa = programa_dispositivos()
    if programa is None:
        return []
    enlaces = (
        get_user_model()
        .groups.through.objects.filter(
            user__is_active=True,
            group__meta__activo=True,
            group__meta__programa=programa,
        )
        .exclude(group__meta__clave=CLAVE_ROL_AGENTE)
        .select_related("user", "user__profile", "group")
        .order_by("user__last_name", "user__first_name", "user__username", "group__name")
    )
    ocupadas = set()
    if dispositivo is not None:
        from programas.models import MiembroEquipoDispositivo

        ocupadas = set(
            MiembroEquipoDispositivo.objects.filter(dispositivo=dispositivo, activo=True).values_list(
                "usuario_id", "rol_id"
            )
        )
    pares = []
    for enlace in enlaces:
        if (enlace.user_id, enlace.group_id) in ocupadas:
            continue
        pares.append(
            {
                "valor": f"{enlace.user_id}:{enlace.group_id}",
                "usuario": enlace.user,
                "rol": enlace.group,
                "etiqueta": f"{nombre_de_persona(enlace.user)} — {enlace.group.name}",
            }
        )
    return pares


def equipo_del_dispositivo(dispositivo, permisos=None):
    """Los miembros activos del Equipo para la solapa, con ``vigente`` (el rol todavía vale) y su alcance en texto.

    «Vigente» es ``q_membresia_vigente``, la misma definición que usan el alcance y la gestión del Equipo, anotada
    sobre cada fila. Los edificios de todas las filas se leen con **un** ``prefetch`` (y ninguno si nadie tiene alcance Edificios), vengan 3 miembros o 300. Cada
    fila trae ``alcance_texto`` (solo los edificios que siguen vinculados) y, si se pasan los ``permisos`` de quien mira
    (``permisos_del_equipo``), ``puede_cambiar_alcance``: lo que el servidor le va a aceptar (RN6), para no ofrecer lo que
    rechaza. Sin ``permisos`` no se acota nada.
    """

    from programas.models import Edificio, MiembroEquipoDispositivo

    Alcance = MiembroEquipoDispositivo.Alcance
    vigente = Case(
        When(q_membresia_vigente(programa_dispositivos()), then=True),
        default=False,
        output_field=BooleanField(),
    )
    miembros = list(
        MiembroEquipoDispositivo.objects.filter(dispositivo=dispositivo, activo=True)
        .select_related("usuario", "rol__meta")
        .annotate(vigente=vigente)
        .order_by("-es_responsable", "usuario__last_name", "usuario__first_name", "usuario__username", "rol__name")
    )
    # Los edificios de todas las filas en una sola consulta (solo los que siguen vinculados), y ninguna si nadie
    # tiene alcance Edificios: el detalle de siempre cuesta lo mismo.
    con_edificios = [m for m in miembros if m.alcance == Alcance.EDIFICIOS]
    if con_edificios:
        prefetch_related_objects(
            con_edificios, Prefetch("edificios", queryset=Edificio.objects.filter(dispositivos=dispositivo))
        )
    gestiona, propios = permisos if permisos is not None else (True, None)
    for miembro in miembros:
        miembro.persona = nombre_de_persona(miembro.usuario)
        if miembro.alcance == Alcance.EDIFICIOS:
            vigentes = sorted(miembro.edificios.all(), key=lambda e: (e.nombre, e.pk))
            miembro.alcance_texto = ", ".join(e.nombre for e in vigentes) or "Sin edificios vigentes"
            miembro.puede_cambiar_alcance = gestiona and (propios is None or {e.pk for e in vigentes} <= propios)
        else:
            miembro.alcance_texto = Alcance.INSTITUCION.label
            miembro.puede_cambiar_alcance = gestiona and propios is None
    return miembros
