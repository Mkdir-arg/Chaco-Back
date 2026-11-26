"""Autorización y reglas del legajo institucional de Dispositivos."""

import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from core import db as core_db
from core import rbac
from programas.services.programa_cache import clave_de, programa_por_codigo
from programas.urls_seguras import entero_de_parametro  # noqa: F401  (re-export: vive en el módulo neutral)

PROGRAMA_DISPOSITIVOS_CODIGO = "DISPOSITIVOS"
CAP_CONFIGURAR = "programa.configurar"
CAP_VER = "dispositivo.ver"
CAP_VER_TODOS = "dispositivo.ver_todos"
CAP_EDITAR = "dispositivo.editar"
#: La sección «Edificios» (#1164). Es de lectura: `ver_todos` la amplía como a `CAP_VER`.
CAP_VER_EDIFICIOS = "edificio.ver"
#: Stock de insumos por edificio (análisis 010). Solo ``stock.ver`` es de lectura; las otras tres operan.
CAP_STOCK_VER = "stock.ver"
CAP_STOCK_ENTREGAR = "stock.entregar"
CAP_STOCK_INGRESAR = "stock.ingresar"
CAP_STOCK_AJUSTAR = "stock.ajustar"
#: Las capacidades de lectura que `dispositivo.ver_todos` amplía a toda la red (RN-010-13: nunca las de operar).
_CAPS_LECTURA_RED = frozenset({CAP_VER, CAP_VER_EDIFICIOS, CAP_STOCK_VER})
# `CAP_ADMITIR` vivía acá para que `core.views.media` dejara al admisor bajar el F-00
# que él mismo había subido. Se fue con la admisión vieja (MVP v2, release A); la
# capacidad sigue en el catálogo y la repone la E2 con el ingreso contra `Estadia`.
#: Se conserva el nombre: la clave la deriva ``programa_cache.clave_de`` (RED-80).
_CACHE_KEY = clave_de(PROGRAMA_DISPOSITIVOS_CODIGO)
_CAMPOS_REQUERIDOS_VALIDACION = (
    "tipo",
    "codigo",
    "nombre",
    "categoria",
    "area_ministerio",
    "localidad",
    "domicilio",
    "responsable_nombre",
    "contacto_telefono",
)

# El mismo mapa para el encabezado y las filas del legajo institucional.
TONOS_ESTADO = {
    "BORRADOR": "white",
    "PENDIENTE_VALIDACION": "info",
    "ACTIVO": "success",
    "OBSERVADO": "warning",
    "RECHAZADO": "danger",
    "INACTIVO": "gray",
    "CERRADO": "gray",
}


def nombre_o(usuario, vacio="—"):
    """El nombre de `usuario`, o `vacio` si no hay (una asignación sin agente, un autor borrado)."""

    return vacio if usuario is None else nombre_de_persona(usuario)


def fecha_corta(momento):
    """«22/11/2026» en hora local: la fecha de un relevamiento o de una carga, sin la hora."""

    return timezone.localtime(momento).strftime("%d/%m/%Y")


def estado_de_dispositivo(dispositivo):
    return {"texto": dispositivo.get_estado_display(), "tono": TONOS_ESTADO.get(dispositivo.estado, "gray")}


def estado_de_tipo(tipo):
    return {"texto": "Activo" if tipo.activo else "Inactivo", "tono": "success" if tipo.activo else "gray"}


def normalizar_codigo_institucional(codigo):
    return " ".join(codigo.split()).upper()


def programa_dispositivos(user=None):
    """Obtiene el programa y lo memoiza durante la request.

    Fachada sobre :func:`programas.services.programa_cache.programa_por_codigo`: hasta
    RED-80 esta función era una copia de ``programa_becas`` con **otra** invalidación —de
    hecho, ninguna: nadie borraba ``programas:dispositivos``—.
    """
    return programa_por_codigo(PROGRAMA_DISPOSITIVOS_CODIGO, user=user)


def puede_configurar_dispositivos(user):
    """Exige la capacidad existente con alcance sobre DISPOSITIVOS."""

    programa = programa_dispositivos(user)
    return programa is not None and rbac.puede(user, CAP_CONFIGURAR, programa=programa)


def puede_en_programa_dispositivos(user, capacidad):
    """Evalúa una capacidad de Dispositivos con alcance al programa correcto."""

    programa = programa_dispositivos(user)
    return programa is not None and rbac.puede(user, capacidad, programa=programa)


def q_membresia_vigente(programa):
    """``Q`` sobre ``MiembroEquipoDispositivo``: la fila vale (Cambio 414).

    Vale la fila activa cuyo rol es del programa y está activo, y que la persona TODAVÍA tiene
    (si se le sacó el rol, la fila no cuenta). Es la única escritura de «membresía vigente»: la
    comparten ``membresias_vigentes``, los responsables activos y la solapa Equipo. La pertenencia
    al rol va con ``Exists`` para no multiplicar filas cuando se usa en un ``annotate``.
    """

    from django.contrib.auth import get_user_model

    tiene_el_rol = get_user_model().groups.through.objects.filter(
        user_id=OuterRef("usuario_id"), group_id=OuterRef("rol_id")
    )
    return Q(activo=True, rol__meta__activo=True, rol__meta__programa=programa) & Exists(tiene_el_rol)


def membresias_vigentes(user, programa):
    """Filas activas del Equipo (Cambio 410) de ``user`` que todavía valen (``q_membresia_vigente``).

    La usan el alcance y la gestión del Equipo.
    """

    from programas.models import MiembroEquipoDispositivo

    return MiembroEquipoDispositivo.objects.filter(q_membresia_vigente(programa), usuario=user)


def responsables_vigentes(dispositivo):
    """Responsables del Equipo de ``dispositivo`` cuya membresía todavía vale (``q_membresia_vigente``).

    La usan la gestión del Equipo (no dejarlo sin responsables) y el contacto del legajo (Cambio 459).
    """

    from programas.models import MiembroEquipoDispositivo

    return MiembroEquipoDispositivo.objects.filter(
        q_membresia_vigente(programa_dispositivos()), dispositivo=dispositivo, es_responsable=True
    )


# Contacto del legajo (Cambios 450 y 459). Vive acá y no en `equipo_dispositivo` porque las
# transiciones de este módulo lo sincronizan antes de exigir los datos: así el import va en
# un solo sentido (equipo_dispositivo → dispositivos) y no abre un ciclo.


def nombre_de_persona(usuario):
    return usuario.get_full_name().strip() or usuario.get_username()


def datos_de_contacto(usuario):
    """Responsable y contacto del legajo tomados de la persona (Cambios 450 y 459).

    Ni el alta ni la edición los piden a mano: salen del primer responsable (el elegido en el
    alta, después el del Equipo: ``contacto_del_equipo``). Sin perfil, documento y teléfono quedan vacíos.
    Cada valor pasa por la misma regla que el campo escrito a mano; el que no la cumple queda
    vacío (un teléfono inválido del perfil cuenta como «sin teléfono» y no traba la edición).
    """

    from programas.validacion_contacto import (
        normalizar_documento_responsable,
        normalizar_telefono,
        validar_nombre_responsable,
    )

    def _con_regla(regla, valor):
        valor = (valor or "").strip()
        if not valor:
            return ""
        try:
            return regla(valor)
        except ValidationError:
            return ""

    perfil = getattr(usuario, "profile", None)
    return {
        "responsable_nombre": _con_regla(validar_nombre_responsable, nombre_de_persona(usuario))[:200],
        "responsable_documento": _con_regla(normalizar_documento_responsable, getattr(perfil, "dni", None)),
        "contacto_telefono": _con_regla(normalizar_telefono, getattr(perfil, "telefono", None)),
        "contacto_email": (usuario.email or "").strip(),
    }


def responsable_de_contacto(dispositivo):
    """La persona de la que sale el contacto del legajo: el primer responsable vigente del Equipo.

    Vigente como en la solapa Equipo (``responsables_vigentes``): quien perdió el rol no cuenta.
    En el mismo orden que el buscador del alta (apellido, nombre, usuario), así el alta y la
    edición eligen a la misma persona. ``None`` si el legajo no tiene responsables vigentes (p. ej.
    los anteriores al Cambio 411): esos conservan el contacto escrito a mano.
    """
    if not dispositivo.pk:
        return None
    miembro = (
        responsables_vigentes(dispositivo)
        .select_related("usuario", "usuario__profile")
        .order_by("usuario__last_name", "usuario__first_name", "usuario__username", "pk")
        .first()
    )
    return miembro.usuario if miembro else None


def contacto_del_equipo(dispositivo, usuario=None):
    """El contacto que el legajo tiene que tener según su responsable, o ``None`` si no hay de quién tomarlo.

    Cada dato sale de la persona; el que su perfil no trae válido conserva el valor guardado en
    el legajo, así un contacto cargado antes no se borra al sincronizar (Cambio 459).
    """
    usuario = usuario or responsable_de_contacto(dispositivo)
    if usuario is None:
        return None
    return {campo: valor or getattr(dispositivo, campo) or "" for campo, valor in datos_de_contacto(usuario).items()}


def sincronizar_contacto(dispositivo):
    """Copia al legajo, sin guardar, el contacto de su responsable.

    Devuelve los cambios con la forma de la traza de edición, ``{campo: {"anterior", "nuevo"}}``.

    La llaman la edición y las transiciones que exigen los datos (enviar a validación y validar),
    así un cambio de perfil o de Equipo llega al legajo antes de chequearlo (Cambio 459).
    """
    contacto = contacto_del_equipo(dispositivo)
    if contacto is None:
        return {}
    cambios = {}
    for campo, nuevo in contacto.items():
        anterior = getattr(dispositivo, campo) or ""
        if nuevo != anterior:
            setattr(dispositivo, campo, nuevo)
            cambios[campo] = {"anterior": anterior, "nuevo": nuevo}
    return cambios


def _filtro_equipo(user, capacidad, programa):
    """Membresías vigentes del Equipo cuyo rol tiene ``capacidad``."""

    return membresias_vigentes(user, programa).filter(rol__permissions__codename=rbac.codename_de(capacidad))


def _del_equipo(user, capacidad, programa):
    """Dispositivos donde el usuario integra el Equipo con un rol que tiene ``capacidad``."""

    from programas.models import Dispositivo

    return Dispositivo.objects.filter(pk__in=_filtro_equipo(user, capacidad, programa).values("dispositivo_id"))


def _ve_todos(user, capacidad, programa):
    """``dispositivo.ver_todos`` da lectura total y **solo** lectura (:data:`_CAPS_LECTURA_RED`)."""

    return capacidad in _CAPS_LECTURA_RED and rbac.puede(user, CAP_VER_TODOS, programa=programa)


def puede_operar_dispositivo(user, dispositivo, capacidad):
    """Evalúa capacidad de Programa más el alcance fino del dispositivo.

    Los administradores del programa y los superusuarios conservan alcance total, y
    ``dispositivo.ver_todos`` da lectura de todo. El resto necesita ser parte del Equipo del
    dispositivo con un rol que tenga la capacidad.
    """

    if user is None or not getattr(user, "is_authenticated", False):
        return False

    programa = programa_dispositivos(user)
    if programa is None or not rbac.puede(user, capacidad, programa=programa):
        return False
    if puede_configurar_dispositivos(user) or _ve_todos(user, capacidad, programa):
        return True
    # Una sola consulta: el alcance se pregunta por pantalla.
    return _del_equipo(user, capacidad, programa).filter(pk=dispositivo.pk).exists()


def dispositivos_visibles(user):
    """Queryset de dispositivos que el usuario puede consultar dentro de su alcance."""

    return dispositivos_en_alcance(user, CAP_VER)


def localidades_visibles(user):
    """Las localidades distintas de los dispositivos que el usuario puede consultar, ordenadas.

    Es lo que ofrece el filtro «Localidad» del listado; `reportes.filtrar_dispositivos` las recibe para decidir
    si el valor pedido se filtra exacto o como texto libre.
    """

    return list(
        dispositivos_visibles(user)
        .exclude(localidad="")
        .order_by("localidad")
        .values_list("localidad", flat=True)
        .distinct()
    )


def dispositivos_en_alcance(user, capacidad):
    """Dispositivos sobre los que el usuario tiene ``capacidad``, con el alcance fino.

    La misma regla que :func:`puede_operar_dispositivo`, en forma de queryset: la
    capacidad en el programa, y después todo (admin del programa, o ``ver_todos`` para
    leer) o solo los dispositivos donde integra el Equipo con un rol que tiene esa
    capacidad.
    """

    from programas.models import Dispositivo

    programa = programa_dispositivos(user)
    if programa is None or not rbac.puede(user, capacidad, programa=programa):
        return Dispositivo.objects.none()
    if puede_configurar_dispositivos(user) or _ve_todos(user, capacidad, programa):
        return Dispositivo.objects.all()
    return _del_equipo(user, capacidad, programa)


def dispositivos_operados(user, capacidad):
    """Solo el alcance fino: los dispositivos donde integra el Equipo con un rol que tiene ``capacidad``.

    Lo mismo que :func:`dispositivos_en_alcance` **sin** la ampliación a todo del admin del
    programa ni de ``dispositivo.ver_todos``: es «la institución que opera», no «lo que puede
    leer». La usa el relevamiento edilicio (Cambio 422), que no se abre por ver todos los
    dispositivos.
    """

    from programas.models import Dispositivo

    programa = programa_dispositivos(user)
    if programa is None or not rbac.puede(user, capacidad, programa=programa):
        return Dispositivo.objects.none()
    return _del_equipo(user, capacidad, programa)


class AlcanceEdificios:
    """Lo que alguien alcanza **dentro** de una institución: todo, o solo ciertos edificios.

    ``todo`` es el alcance de siempre (toda la institución). Con ``todo=False``, ``edificios`` son los ids que
    sí alcanza; un conjunto vacío no alcanza nada (fail-closed): nunca equivale a «toda la institución».
    """

    __slots__ = ("todo", "edificios")

    def __init__(self, todo, edificios=()):
        self.todo = bool(todo)
        self.edificios = frozenset(edificios)

    def permite(self, edificio_id):
        """Si un objeto que cuelga de ``edificio_id`` (``None`` = sin edificio) entra en el alcance."""

        return self.todo or (edificio_id is not None and edificio_id in self.edificios)

    def filtrar(self, queryset, campo):
        """Acota ``queryset`` a los edificios alcanzados; ``campo`` es la ruta al id o a la FK del edificio."""

        if self.todo:
            return queryset
        return queryset.filter(**{f"{campo}__in": list(self.edificios)})

    def permite_todos(self, queryset, campo):
        """Si **cada** fila de ``queryset`` cuelga de un edificio alcanzado; ``campo`` es la ruta al id del edificio.

        Con ``todo`` no consulta. Es la forma de preguntar «¿todas estas plazas están en mi alcance?»: no con
        ``exclude(q_edificios_en_alcance(...))``, que con alcance total recibe un ``Q()`` vacío y no excluye nada
        (#1298). Una fila sin edificio no entra, como en :meth:`permite`.
        """

        if self.todo:
            return True
        return all(self.permite(edificio_id) for edificio_id in queryset.values_list(campo, flat=True))


ALCANCE_TODO = AlcanceEdificios(True)
ALCANCE_NADA = AlcanceEdificios(False)


def _es_alcance_institucion(alcance):
    """NULL (filas anteriores al campo) vale «Toda la institución»; cualquier otro valor distinto de ``EDIFICIOS``
    también, porque el campo solo admite esos dos."""

    from programas.models import MiembroEquipoDispositivo

    return alcance != MiembroEquipoDispositivo.Alcance.EDIFICIOS


def alcance_de_edificios(user, dispositivo, capacidad):
    """El **único dueño** de «qué edificios de ``dispositivo`` alcanza ``user`` con ``capacidad``» (Cambio 523).

    * Sin la capacidad en el programa, o sin ser del Equipo con un rol que la tenga: nada. (La institución
      sigue su camino por :func:`puede_operar_dispositivo`; acá solo se acota el interior.)
    * Admin del programa, superusuario y ``dispositivo.ver_todos`` (solo lectura): todo, sin cambios.
    * Del Equipo: si **alguna** de sus filas activas con un rol que tiene la capacidad es de la institución
      (o no tiene alcance cargado), todo. Si no, la **unión** de los edificios de esas filas que **siguen
      vinculados** a la institución; si no queda ninguno, nada. Jamás cae a «toda la institución».
    """

    from programas.models import Edificio

    if user is None or not getattr(user, "is_authenticated", False):
        return ALCANCE_NADA
    programa = programa_dispositivos(user)
    if programa is None or not rbac.puede(user, capacidad, programa=programa):
        return ALCANCE_NADA
    if puede_configurar_dispositivos(user) or _ve_todos(user, capacidad, programa):
        return ALCANCE_TODO
    filas = list(_filtro_equipo(user, capacidad, programa).filter(dispositivo=dispositivo).values_list("pk", "alcance"))
    if not filas:
        return ALCANCE_NADA
    if any(_es_alcance_institucion(alcance) for _pk, alcance in filas):
        return ALCANCE_TODO
    ids = Edificio.objects.filter(miembros_equipo__in=[pk for pk, _a in filas], dispositivos=dispositivo).values_list(
        "pk", flat=True
    )
    return AlcanceEdificios(False, ids)


def puede_operar_edificio(user, dispositivo, edificio_id, capacidad):
    """:func:`puede_operar_dispositivo` más el edificio: ``edificio_id`` (``None`` = sin edificio) tiene que estar alcanzado."""

    return puede_operar_dispositivo(user, dispositivo, capacidad) and alcance_de_edificios(
        user, dispositivo, capacidad
    ).permite(edificio_id)


def edificio_de_plaza(plaza):
    """El edificio del sector de ``plaza`` (un ``Plaza``, su id, o ``None``); ``None`` si no hay plaza o sector sin edificio."""

    from programas.models import Plaza

    if plaza is None:
        return None
    if isinstance(plaza, Plaza):
        return plaza.sector.edificio_id
    return Plaza.objects.filter(pk=plaza).values_list("sector__edificio_id", flat=True).first()


def puede_operar_plaza(user, dispositivo, plaza, capacidad):
    """:func:`puede_operar_dispositivo` más el edificio de la plaza (``None`` = sin plaza: solo alcance institución).

    Es el punto por el que pasan ingreso, egreso, cambio de plaza, reservas y las acciones sobre una plaza (RN4).
    Una plaza de un sector sin edificio, o ninguna plaza, no entra con alcance Edificios.
    """

    if not puede_operar_dispositivo(user, dispositivo, capacidad):
        return False
    alcance = alcance_de_edificios(user, dispositivo, capacidad)
    return alcance.todo or alcance.permite(edificio_de_plaza(plaza))


def puede_operar_institucion(user, dispositivo, capacidad):
    """:func:`puede_operar_dispositivo` **y** alcance sobre toda la institución (no solo ciertos edificios).

    Para lo que no cuelga de un edificio (el legajo, las entregas de kits, el ingreso directo de Emergencia):
    con alcance Edificios no se puede, fail-closed.
    """

    # `alcance_de_edificios` ya exige la capacidad y la membresía: «todo» implica `puede_operar_dispositivo`,
    # con una consulta menos.
    return alcance_de_edificios(user, dispositivo, capacidad).todo


def puede_editar_legajo(user, dispositivo, capacidad=CAP_EDITAR):
    """Editar el legajo de la institución (datos, horarios, contacto, estado) es de alcance **institución** (RN5).

    Con alcance Edificios la institución aparece en el listado pero no se edita.
    """

    return puede_operar_institucion(user, dispositivo, capacidad)


def dispositivos_de_institucion(user, capacidad):
    """:func:`puede_operar_institucion` en forma de queryset: las instituciones sobre las que ``user`` alcanza
    **toda la institución** con ``capacidad`` (admin del programa, o Equipo con alcance institución).

    Sirve para saber, en una consulta, en cuáles de varias instituciones puede editar el legajo (y con él sus
    edificios). Con alcance Edificios la institución no entra, fail-closed.
    """

    from programas.models import Dispositivo

    programa = programa_dispositivos(user)
    if programa is None or not rbac.puede(user, capacidad, programa=programa):
        return Dispositivo.objects.none()
    if puede_configurar_dispositivos(user) or _ve_todos(user, capacidad, programa):
        return Dispositivo.objects.all()
    return Dispositivo.objects.filter(
        pk__in=_filas_de_institucion(_filtro_equipo(user, capacidad, programa)).values("dispositivo_id")
    )


def _filas_de_institucion(filas):
    """Las filas del Equipo con alcance institución (o sin alcance cargado) de un queryset de ``_filtro_equipo``."""

    from programas.models import MiembroEquipoDispositivo

    return filas.exclude(alcance=MiembroEquipoDispositivo.Alcance.EDIFICIOS)


def miembros_del_edificio(dispositivo, edificio_id):
    """Las filas vigentes del Equipo de ``dispositivo`` que trabajan en ``edificio_id`` (Cambio 563).

    Vale la fila de alcance Institución (o sin alcance cargado) y la de alcance Edificios que incluye ese edificio.
    Los responsables van primero. Es la lectura inversa de :func:`alcance_de_edificios`: vive acá, con su dueño.
    """

    from programas.models import MiembroEquipoDispositivo

    en_este_edificio = MiembroEquipoDispositivo.edificios.through.objects.filter(edificio_id=edificio_id).values(
        "miembroequipodispositivo_id"
    )
    return list(
        MiembroEquipoDispositivo.objects.filter(dispositivo=dispositivo)
        .filter(q_membresia_vigente(programa_dispositivos()))
        .filter(~Q(alcance=MiembroEquipoDispositivo.Alcance.EDIFICIOS) | Q(pk__in=en_este_edificio))
        .select_related("usuario")
        .order_by("-es_responsable", "usuario__last_name", "usuario__first_name", "usuario__username", "pk")
    )


def contar_miembros_por_edificio(dispositivo, edificio_ids):
    """``{edificio_id: cantidad}`` de las filas vigentes del Equipo que trabajan en cada edificio (Cambio 570).

    La misma regla que :func:`miembros_del_edificio` leída de una vez para todos los edificios de una ficha: vale la
    fila de alcance Institución (o sin alcance cargado) en todos, y la de alcance Edificios en los que lista. Dos
    consultas fijas, sin importar cuántos edificios ni cuántos miembros.
    """

    from django.db.models import Count

    from programas.models import MiembroEquipoDispositivo

    ids = list(edificio_ids)
    if not ids:
        return {}
    vigentes = MiembroEquipoDispositivo.objects.filter(dispositivo=dispositivo).filter(
        q_membresia_vigente(programa_dispositivos())
    )
    de_toda_la_institucion = vigentes.filter(~Q(alcance=MiembroEquipoDispositivo.Alcance.EDIFICIOS)).count()
    por_edificio = {
        fila["edificio_id"]: fila["n"]
        for fila in MiembroEquipoDispositivo.edificios.through.objects.filter(
            edificio_id__in=ids,
            miembroequipodispositivo_id__in=vigentes.filter(alcance=MiembroEquipoDispositivo.Alcance.EDIFICIOS).values(
                "pk"
            ),
        )
        .values("edificio_id")
        .annotate(n=Count("pk"))
    }
    return {pk: de_toda_la_institucion + por_edificio.get(pk, 0) for pk in ids}


def q_edificios_en_alcance(user, capacidad, campo_dispositivo, campo_edificio):
    """La forma ``Q`` de :func:`alcance_de_edificios` para listas que cruzan instituciones.

    ``campo_dispositivo`` y ``campo_edificio`` son las rutas desde el modelo filtrado (p. ej.
    ``"dispositivo_id"`` y ``"sector__edificio_id"``). Es **solo** el acote por edificio: la institución
    la sigue resolviendo :func:`dispositivos_en_alcance`. Un objeto sin edificio no entra con alcance Edificios.

    **Solo para ``filter``.** Con alcance total (admin del programa, superusuario, ``ver_todos``) devuelve ``Q()``
    vacío, que en ``filter`` es «todo» pero en ``exclude`` o ``~`` no es «nada»: ``exclude(Q())`` no excluye
    ninguna fila (#1298). Para «¿todo esto está en mi alcance?» dentro de una institución, usar
    :meth:`AlcanceEdificios.permite_todos`.
    """

    from programas.models import MiembroEquipoDispositivo

    sin_nada = Q(pk__in=[])
    if user is None or not getattr(user, "is_authenticated", False):
        return sin_nada
    programa = programa_dispositivos(user)
    if programa is None or not rbac.puede(user, capacidad, programa=programa):
        return sin_nada
    if puede_configurar_dispositivos(user) or _ve_todos(user, capacidad, programa):
        return Q()
    # Todo en subconsultas: sin consultas extra respecto de la lista que se filtra. Las filas Edificios de una
    # institución que también tiene una fila Institución no restan: ya entra entera por la primera rama.
    filas = _filtro_equipo(user, capacidad, programa)
    completas = _filas_de_institucion(filas).values("dispositivo_id")
    limitadas = filas.filter(alcance=MiembroEquipoDispositivo.Alcance.EDIFICIOS).values("pk")
    de_sus_edificios = MiembroEquipoDispositivo.edificios.through.objects.filter(
        miembroequipodispositivo_id__in=limitadas,
        miembroequipodispositivo__dispositivo_id=OuterRef(campo_dispositivo),
        edificio_id=OuterRef(campo_edificio),
        edificio__dispositivos=OuterRef(campo_dispositivo),
    )
    return Q(**{f"{campo_dispositivo}__in": completas}) | Q(Exists(de_sus_edificios))


def pares_en_alcance(user, capacidad):
    """Los vínculos institución-edificio que ``user`` alcanza con ``capacidad``, como filas del vínculo.

    La única escritura de «institución en alcance **y** edificio en alcance» sobre el vínculo: la usan plazas
    (``dispositivo.ver``) y stock (``stock.ver``, sumando su filtro de tipo) y las que vengan.
    """

    from programas.models import Edificio

    return Edificio.dispositivos.through.objects.filter(
        dispositivo_id__in=dispositivos_en_alcance(user, capacidad).values("pk"),
    ).filter(q_edificios_en_alcance(user, capacidad, "dispositivo_id", "edificio_id"))


def _registrar_traza(dispositivo, usuario, accion, estado_anterior, estado_nuevo, detalle=""):
    from programas.models import TrazaDispositivo

    TrazaDispositivo.objects.registrar(
        dispositivo, usuario, accion, estado_anterior=estado_anterior, estado_nuevo=estado_nuevo, detalle=detalle
    )


def registrar_alta_dispositivo(dispositivo, usuario):
    _registrar_traza(
        dispositivo,
        usuario,
        "CREADO",
        "",
        dispositivo.estado,
    )


def registrar_edicion_dispositivo(dispositivo, usuario, cambios):
    """Conserva valores anterior/nuevo en la auditoría aditiva del legajo."""

    if not cambios:
        return
    _registrar_traza(
        dispositivo,
        usuario,
        "EDITADO",
        dispositivo.estado,
        dispositivo.estado,
        json.dumps(cambios, ensure_ascii=False, default=str),
    )


def buscar_posibles_duplicados(*, codigo="", nombre="", localidad=""):
    """Busca coincidencias blandas y determina si el código ya está tomado.

    El código es el único bloqueo duro. Nombre y localidad se informan para que
    quien carga decida si se trata de otra institución.
    """

    from programas.models import Dispositivo

    codigo_normalizado = normalizar_codigo_institucional(codigo)
    nombre = nombre.strip()
    localidad = localidad.strip()

    coincidencias = Q()
    if codigo_normalizado:
        coincidencias |= Q(codigo__iexact=codigo_normalizado)
    if nombre and localidad:
        coincidencias |= Q(nombre__iexact=nombre, localidad__iexact=localidad)

    queryset = Dispositivo.objects.none() if not coincidencias else Dispositivo.objects.filter(coincidencias)
    return {
        "codigo_duplicado": bool(codigo_normalizado and queryset.filter(codigo__iexact=codigo_normalizado).exists()),
        "dispositivos": queryset.select_related("tipo").order_by("nombre"),
    }


def campos_para_validacion():
    """Campos del circuito existente, también usados por el resumen del formulario."""
    return _CAMPOS_REQUERIDOS_VALIDACION


def estados_desde_los_que_se_envia():
    """Estados desde los que se (re)envía a validación: borrador, observado y rechazado.

    El rechazado se corrige y vuelve a enviarse (decisión del PM, 30/10/2026, Cambio 407).
    Una sola fuente para el servicio, el formulario y el botón del detalle.
    """
    from programas.models import Dispositivo

    return (Dispositivo.Estado.BORRADOR, Dispositivo.Estado.OBSERVADO, Dispositivo.Estado.RECHAZADO)


def puede_enviar_desde_formulario(usuario, dispositivo):
    """Una institución nueva todavía no tiene asignaciones: exige alcance total."""

    if dispositivo.estado not in estados_desde_los_que_se_envia():
        return False
    if not dispositivo.pk:
        return puede_configurar_dispositivos(usuario) and puede_en_programa_dispositivos(usuario, "dispositivo.editar")
    return puede_editar_legajo(usuario, dispositivo, "dispositivo.editar")


def enviar_desde_formulario(dispositivo, usuario):
    """El mismo permiso de P4 antes de ejecutar su transición, dentro del guardado atómico."""
    from django.core.exceptions import PermissionDenied

    if not puede_editar_legajo(usuario, dispositivo, "dispositivo.editar"):
        raise PermissionDenied
    return enviar_a_validacion(dispositivo, usuario)


def _exigir_campos_para_validacion(dispositivo):
    faltantes = [campo for campo in campos_para_validacion() if not getattr(dispositivo, campo)]
    if faltantes:
        # Con el nombre de cada campo como lo ve el operador: el aviso genérico lo dejaba buscando.
        nombres = [str(dispositivo._meta.get_field(campo).verbose_name) for campo in faltantes]
        raise ValidationError(
            "Completá los campos obligatorios antes de validar el dispositivo. Falta: " + ", ".join(nombres) + "."
        )


def _sincronizar_contacto(dispositivo, usuario):
    """Antes de exigir los datos, el contacto del legajo se pone al día con su responsable (Cambio 459).

    Si el perfil del responsable o el Equipo cambiaron después del último guardado, el chequeo ve
    lo vigente; lo que se copia queda en la traza como una edición más.
    """

    cambios = sincronizar_contacto(dispositivo)
    if cambios:
        dispositivo.save(update_fields=[*cambios, "modificado"])
        registrar_edicion_dispositivo(dispositivo, usuario, cambios)


def _exigir_formulario_del_tipo(dispositivo):
    """Los obligatorios visibles del formulario «Crear dispositivo» de su tipo (P17).

    Se exigen al **enviar** a validación, como los datos del legajo: el borrador los
    guarda incompletos. Contra el formulario vigente del tipo y lo ya guardado.
    """
    from programas.services.respuestas_dispositivo import faltantes_formulario_alta

    faltantes = faltantes_formulario_alta(dispositivo)
    if faltantes:
        raise ValidationError(
            "Completá las preguntas obligatorias del formulario del tipo antes de enviar a validación: "
            + ", ".join(faltantes)
            + ".",
            code="formulario_tipo_incompleto",
        )


def _transicionar(
    dispositivo,
    usuario,
    *,
    origenes,
    destino,
    accion,
    detalle="",
    exige_datos=False,
    exige_formulario=False,
    antes_de_cambiar=None,
):
    """`antes_de_cambiar(dispositivo)` corre con la fila bloqueada y el origen ya validado.

    Puede rechazar con `ValidationError` o devolver el texto que se suma al detalle de la traza.
    """
    from programas.models import Dispositivo

    with transaction.atomic():
        dispositivo = Dispositivo.objects.select_for_update().get(pk=dispositivo.pk)
        if dispositivo.estado not in origenes:
            raise ValidationError("La transición de estado solicitada no está permitida.")
        if exige_datos:
            _sincronizar_contacto(dispositivo, usuario)
            _exigir_campos_para_validacion(dispositivo)
        if exige_formulario:
            _exigir_formulario_del_tipo(dispositivo)

        if antes_de_cambiar is not None:
            extra = antes_de_cambiar(dispositivo)
            if extra:
                detalle = f"{detalle} · {extra}" if detalle else extra

        anterior = dispositivo.estado
        dispositivo.estado = destino
        dispositivo.save(update_fields=["estado", "modificado"])
        _registrar_traza(dispositivo, usuario, accion, anterior, destino, detalle)
        return dispositivo


def enviar_a_validacion(dispositivo, usuario):
    from programas.models import Dispositivo

    return _transicionar(
        dispositivo,
        usuario,
        origenes=estados_desde_los_que_se_envia(),
        destino=Dispositivo.Estado.PENDIENTE_VALIDACION,
        accion="ENVIADO_VALIDACION",
        exige_datos=True,
        exige_formulario=True,
    )


def validar_dispositivo(dispositivo, usuario):
    from programas.models import Dispositivo

    return _transicionar(
        dispositivo,
        usuario,
        origenes=(Dispositivo.Estado.PENDIENTE_VALIDACION,),
        destino=Dispositivo.Estado.ACTIVO,
        accion="VALIDADO",
        exige_datos=True,
    )


def observar_dispositivo(dispositivo, usuario, motivo):
    from programas.models import Dispositivo

    motivo = (motivo or "").strip()
    if not motivo:
        # Con el campo nombrado: así el modal de P4 lo pinta bajo «Motivo» en vez de
        # mandarlo a un aviso general. Sin JS, `error.messages[0]` sigue siendo el texto.
        raise ValidationError({"motivo": "Indicá el motivo de la observación."})
    return _transicionar(
        dispositivo,
        usuario,
        origenes=(Dispositivo.Estado.PENDIENTE_VALIDACION,),
        destino=Dispositivo.Estado.OBSERVADO,
        accion="OBSERVADO",
        detalle=motivo,
    )


def rechazar_dispositivo(dispositivo, usuario, motivo):
    from programas.models import Dispositivo

    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError({"motivo": "Indicá el motivo del rechazo."})
    return _transicionar(
        dispositivo,
        usuario,
        origenes=(Dispositivo.Estado.PENDIENTE_VALIDACION,),
        destino=Dispositivo.Estado.RECHAZADO,
        accion="RECHAZADO",
        detalle=motivo,
    )


def reactivar_dispositivo(dispositivo, usuario):
    """Un dispositivo inactivo vuelve a ACTIVO (decisión del PM, 02/11/2026, Cambio 409).

    Misma capacidad que inactivar (`dispositivo.editar`); queda en el historial como
    «REACTIVADO». El cerrado no vuelve: el cierre es definitivo.
    """
    from programas.models import Dispositivo

    return _transicionar(
        dispositivo,
        usuario,
        origenes=(Dispositivo.Estado.INACTIVO,),
        destino=Dispositivo.Estado.ACTIVO,
        accion="REACTIVADO",
    )


def bloquear_instituciones(ids):
    """Bloqueo **compartido** de las filas de estas instituciones, por pk. Devuelve ``{pk: estado}``.

    Es el primer candado de todo camino que toca plazas, reservas o estadías de una institución
    (pendiente del Cambio 536, cerrado en el Cambio 545). Esta función es la **fuente única** del orden
    de candados de Dispositivos; los demás módulos remiten acá en vez de repetirlo::

        institución → plaza (por pk) → reserva / estadía → persona

    Por qué primero la institución: «Inactivar» y «Cerrar» la toman en exclusivo
    (`_transicionar`) y después bloquean plazas y reservas; reservar, liberar, ingresar o cambiar
    de plaza bloquean la plaza y, al escribir la traza (`TrazaDispositivo` tiene una FK a la
    institución), InnoDB les pide un compartido sobre la misma fila. En el orden inverso las dos
    transacciones se esperaban en cruz y el motor cortaba una con `ERROR 1213`. Y el estado que
    se lee acá no puede cambiar hasta el commit: una reserva o un ingreso no se cuela en una
    institución que otro operador está cerrando.

    Compartido y no `select_for_update()`: dos ingresos en la misma institución no se esperan
    entre sí; solo esperan a quien la cambia de estado. Exige estar en una transacción (ver
    `core.db.leer_con_bloqueo_compartido`). Con varias instituciones —el ingreso que cierra las
    reservas de la persona en otros dispositivos— se toman todas de una vez, por pk.
    """
    from programas.models import Dispositivo

    return core_db.leer_con_bloqueo_compartido(Dispositivo, ids, "estado")


def bloquear_institucion(dispositivo):
    """`bloquear_instituciones` de una sola: devuelve su estado fresco, o ``None`` si no existe."""

    pk = getattr(dispositivo, "pk", dispositivo)
    return bloquear_instituciones([pk]).get(pk)


def exigir_institucion_en_estado(dispositivo, estados, accion):
    """Regla única de «qué se puede hacer según el estado de la institución» (Cambio 536).

    Lee el estado **fresco** de la base y con la fila tomada en compartido
    (`bloquear_institucion`): el objeto que llega puede ser anterior a que alguien la
    inactivara, y nadie la puede cerrar ni inactivar hasta que la acción termine. Va
    **antes** de bloquear la plaza. `estados` son los que permiten la acción; `accion`
    completa «No se puede …».
    """
    from programas.models import Dispositivo

    actual = bloquear_institucion(dispositivo)
    if actual not in estados:
        etiqueta = dict(Dispositivo.Estado.choices).get(actual, "inexistente").lower()
        raise ValidationError({"dispositivo": f"No se puede {accion}: el dispositivo está {etiqueta}."})


def estados_que_reservan():
    """Reservar y prestar una plaza: solo en una institución activa."""
    from programas.models import Dispositivo

    return (Dispositivo.Estado.ACTIVO,)


def estados_que_cambian_de_plaza():
    """Cambiar de plaza a quien ya está alojado: activa o inactiva, nunca cerrada."""
    from programas.models import Dispositivo

    return (Dispositivo.Estado.ACTIVO, Dispositivo.Estado.INACTIVO)
