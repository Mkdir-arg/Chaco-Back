"""Etapa 3 de Emergencia sin derivación: ingreso directo y aviso a la mesa (M2-6, RN-3.10).

«Ingresar igual» (``ingreso_directo``) —la decisión 4 del PM: va aparte para que se pueda
sacar sin tocar el resto— y «Avisar a la mesa» (``avisar_a_la_mesa``). Se importan desde
``programas.services.emergencia_alojar``.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from core.archivos import archivos_atomicos
from core.dni import normalizar_dni
from core.models import Localidad
from programas.models import (
    CasoEmergencia,
    Derivacion,
    ReservaPlaza,
)
from programas.selectors.emergencia import dispositivo_elegible
from programas.selectors.emergencia_alojar import camas_libres
from programas.services.emergencia import (
    DISPOSITIVO_NO_ELEGIBLE,
    EstadoCambio,
    UuidEnUso,
    _caso_de_ese_envio,
    _como_uuid,
    crear_caso,
)
from programas.services.emergencia_alta import CasoAbiertoDeLaFamilia
from programas.services.emergencia_comun import _bloquear_caso, _trazar
from programas.services.emergencia_familia import (
    anotar_resultado_del_envio,
    caso_abierto_de_la_familia,
    caso_del_envio_sumado,
    envio_sumado,
)
from programas.services.emergencia_ingreso_comun import (
    SIN_ALCANCE,
    Accion,
    Estado,
    Origen,
    _anotar_en_bitacora,
    _asegurar_filas,
    _filas_de,
    _reservar_camas,
    _resumen_de_reservas,
    cancelar_derivacion_por_llegada,
    marcar_en_la_puerta,
    mensaje_otro_edificio,
    puede_avisar_a_la_mesa,
    puede_ingresar_igual,
)


class CasoAbiertoEnOtraInstitucion(CasoAbiertoDeLaFamilia):
    """El caso de la familia está en manos de otra institución.

    Ni al ingresar ni al avisar se manda «a avisar a la mesa»: con el ingreso o el alojamiento en marcha en otra
    institución no hay nada que avisar y el propio sistema lo rechaza. Quien la levanta puede pasar su texto
    (``mensaje``), como hace el aviso.
    """

    def __init__(self, caso, dispositivo=None, mensaje=None):
        super().__init__(
            caso,
            dispositivo,
            mensaje=mensaje
            or (
                f"La familia ya tiene el caso {caso.numero} en curso en otra institución: no se la puede ingresar acá."
            ),
        )


SIN_CASO_ABIERTO = "La familia ya no tiene un caso abierto. Buscala de nuevo."
CASO_YA_CERRADO = "El caso {numero} de la familia se cerró mientras tanto. Buscala de nuevo."
YA_ALOJADA_NADA_QUE_AVISAR = "La familia ya está alojada en este dispositivo: no hay nada que avisar a la mesa."
A_RECIBIR_NO_SE_INGRESA_IGUAL = (
    "La derivación a este dispositivo está por recibir: aceptala en vez de ingresar a la familia igual."
)

SIN_CAMAS_PARA_INGRESO_DIRECTO = (
    "No hay camas libres para ingresar a la familia. Liberá una cama o avisá a la mesa para que la derive a otro lado."
)


def _formulario1_en_el_dispositivo(datos_formulario1, dispositivo):
    """El Formulario 1 con lo que se sabe por estar **en** el dispositivo (RN-3.10).

    La dirección y la localidad son opcionales acá: sin dirección va el domicilio del
    dispositivo (o «Se presentó en X»), y sin localidad la del dispositivo, **si** su texto
    coincide con exactamente una ``core.Localidad``.
    """

    datos = dict(datos_formulario1 or {})
    if not str(datos.get("direccion") or "").strip():
        datos["direccion"] = (dispositivo.domicilio or f"Se presentó en {dispositivo.nombre}")[:240]
    if datos.get("localidad") in (None, "") and dispositivo.localidad:
        candidatas = list(Localidad.objects.filter(nombre__iexact=dispositivo.localidad)[:2])
        if len(candidatas) == 1:
            datos["localidad"] = candidatas[0]
    return datos


def _camas_de_un_edificio(libres, cuantas):
    """``(edificio_id, camas)``: hasta ``cuantas`` camas de ``libres``, **todas del mismo edificio**.

    El edificio con más camas libres; a igualdad, el de la primera cama de ``libres`` (que ya viene
    ordenada por sector). Las camas sin edificio cuentan como un grupo más, con ``edificio_id``
    ``None``. Así el ingreso directo nace con su edificio y la guardia de ese edificio lo sigue
    (relevamiento del 22/11/2026, hallazgo 18); si no alcanza, faltan, como al aceptar una derivación.
    """

    por_edificio = {}
    for cama in libres:
        por_edificio.setdefault(cama.sector.edificio_id, []).append(cama)
    edificio_id, camas = max(por_edificio.items(), key=lambda par: len(par[1]))
    return edificio_id, camas[:cuantas]


def _con_sus_reservas(caso):
    """Le cuelga ``reservadas`` y ``faltantes`` a un caso **creado** por un ingreso directo (su reenvío).

    Son las camas que el ingreso reservó **al crearse** —vigentes, consumidas o liberadas
    después— contra las que pidió: lo mismo que contestó el primer envío. No sirve para un envío que se sumó a un
    caso que ya existía: ese guarda lo que contestó en su anotación (:func:`_con_lo_que_contesto`).
    """

    derivacion = Derivacion.objects.filter(caso_id=caso.pk).order_by("-id").first()
    pedidas = derivacion.plazas_pedidas if derivacion is not None else 0
    reservadas = ReservaPlaza.objects.filter(derivacion=derivacion).count() if derivacion is not None else 0
    caso.reservadas, caso.faltantes = reservadas, max(pedidas - reservadas, 0)
    return caso


def _con_lo_que_contesto(caso, uuid_cliente, usuario):
    """El reenvío de un envío que se sumó a un caso existente contesta lo mismo que el primero.

    ``reservadas`` y ``faltantes`` salen de la anotación del envío (:func:`anotar_resultado_del_envio`): contarlas
    de nuevo da otra cosa si el caso cambió. Sin ellas (anotación de antes), se cuentan.
    """

    envio = envio_sumado(caso, uuid_cliente, usuario)
    if envio is not None and "reservadas" in envio:
        caso.reservadas, caso.faltantes = envio["reservadas"], envio["faltantes"]
        return caso
    return _con_sus_reservas(caso)


def _exigir_reenvio_de_este_ingreso(caso, dispositivo):
    """El caso hallado por ``uuid_cliente`` tiene que ser un ingreso directo hacia **este** dispositivo.

    La idempotencia es un atajo de lectura: el mismo ``uuid_cliente`` puesto en la URL de otro
    dispositivo (o de un envío de M1) no es un reenvío de este envío. Si no, ``UuidEnUso``
    (409), sin devolver nada del caso.
    """

    primera = Derivacion.objects.filter(caso_id=caso.pk).order_by("id").first()
    if caso.origen != Origen.DISPOSITIVO or primera is None or primera.dispositivo_id != dispositivo.pk:
        raise UuidEnUso()


def _ultima_derivacion_bloqueada(caso):
    """La última derivación del caso con ``FOR UPDATE``. Se pide **después** del caso, sin JOIN."""

    return Derivacion.objects.select_for_update().filter(caso_id=caso.pk).order_by("-id").first()


def _abrir_el_ingreso(*, caso, dispositivo, usuario, libres, momento, detalle):
    """Deja el caso con el ingreso en curso en ``dispositivo``: derivación aceptada, camas y filas (RN-3.10).

    Es lo que sigue de crear el caso en «Ingresar igual», y lo que hace el ingreso sobre un caso que la familia
    ya tenía (Cambio 579). El caso viene bloqueado. Las marcas del SLA se escriben solo si todavía no tienen
    valor: un caso que ya pasó por la mesa conserva las suyas.
    """

    grupo = caso.grupo
    estado_anterior = caso.estado
    edificio_id, camas = _camas_de_un_edificio(libres, grupo.total_declarado)
    derivacion = Derivacion(
        caso=caso,
        dispositivo=dispositivo,
        edificio_id=edificio_id,
        estado=Derivacion.Estado.ACEPTADA,
        plazas_pedidas=grupo.total_declarado,
        vence_en=momento,
        derivada_por=usuario,
        respondida_por=usuario,
        respondida_en=momento,
    )
    derivacion.save()
    reservas = _reservar_camas(derivacion=derivacion, plazas=camas, usuario=usuario, momento=momento)

    caso.estado = Estado.INGRESO_EN_CURSO
    for marca in ("tomado_en", "derivado_en", "aceptado_en"):
        caso.marcar(marca, momento)
    campos = ["estado", "tomado_en", "derivado_en", "aceptado_en", "modificado"]
    if CasoEmergencia.SITUACION_EN_LA_PUERTA_TRAS_DERIVAR in caso.situacion:
        caso.situacion = {
            clave: valor
            for clave, valor in caso.situacion.items()
            if clave != CasoEmergencia.SITUACION_EN_LA_PUERTA_TRAS_DERIVAR
        }
        campos.append("situacion")
    caso.save(update_fields=campos)
    _asegurar_filas(grupo)

    reservadas = len(reservas)
    faltantes = grupo.total_declarado - reservadas
    resumen = _resumen_de_reservas(reservadas, grupo.total_declarado)
    _trazar(
        caso,
        usuario,
        Accion.INGRESO_DIRECTO,
        estado_anterior=estado_anterior,
        detalle=f"{detalle} · {resumen}",
    )
    _anotar_en_bitacora(
        dispositivo,
        usuario,
        f"Emergencia · ingreso directo · caso N.° {caso.numero} · {resumen}",
        timezone.now(),
        edificio_id,
    )
    caso.ya_existia = False
    caso.reservadas, caso.faltantes = reservadas, faltantes
    return caso


@archivos_atomicos
@transaction.atomic
def ingreso_directo(*, dispositivo, usuario, datos_formulario1, uuid_cliente=None):
    """«Ingresar igual»: la familia llegó sola y el dispositivo la recibe sin pasar por la mesa (HU-3.6, RN-3.10).

    Exige ``dispositivo.admitir`` sobre **toda la institución** (:func:`puede_ingresar_igual`), que sea elegible para alojar
    familias y que tenga **al menos una cama libre**. En una transacción:

    * crea el caso con ``crear_caso(origen=DISPOSITIVO)`` —misma validación del Formulario 1,
      con dirección y localidad opcionales—;
    * crea una ``Derivacion`` ``ACEPTADA`` hacia el propio dispositivo, para que todo lo que
      sigue (confirmar, alojar, diferencia, egreso) sea el mismo camino;
    * reserva camas para la familia **hasta donde alcance**, todas de un mismo edificio —el que
      tiene más libres—, que queda como el edificio de la derivación, y crea sus N filas;
    * deja el caso en ``INGRESO_EN_CURSO`` con ``tomado_en = derivado_en = aceptado_en =
      creado``: el tramo de la mesa vale 0 y el tablero lo separa como ingreso directo.

    **Una familia, un caso abierto** (Cambio 579): si la familia ya tiene un caso abierto no se crea otro; el
    ingreso se suma a ese caso (:func:`_ingresar_en_el_caso_abierto`).

    **Idempotente** por ``uuid_cliente`` (RU-16; es lo único de la etapa que la app encola
    sin conexión): reenviarlo devuelve el mismo caso, con ``caso.ya_existia = True``, sin
    reservar de nuevo ni mirar si hoy hay camas.

    Devuelve el ``CasoEmergencia`` con ``ya_existia``, ``familia_ya_tenia_caso``, ``reservadas`` y ``faltantes``.
    """

    if not puede_ingresar_igual(usuario, dispositivo):
        raise PermissionDenied(SIN_ALCANCE)
    uuid_cliente = _como_uuid(uuid_cliente)
    if uuid_cliente is not None:
        existente = _caso_de_ese_envio(uuid_cliente, usuario)
        if existente is not None:
            _exigir_reenvio_de_este_ingreso(existente, dispositivo)
            return _con_sus_reservas(existente)
        # El envío que se sumó a un caso que ya existía no dejó un caso con su ``uuid_cliente``: se reconoce por
        # la anotación del caso y se contesta antes de mirar las camas, como el primer envío.
        sumado = caso_del_envio_sumado(datos_formulario1.get("dni"), uuid_cliente, usuario)
        if sumado is not None:
            sumado.ya_existia = True
            sumado.familia_ya_tenia_caso = True
            return _con_lo_que_contesto(sumado, uuid_cliente, usuario)
    if not dispositivo_elegible(dispositivo):
        raise ValidationError({"dispositivo": DISPOSITIVO_NO_ELEGIBLE})
    libres = camas_libres(dispositivo, usuario=usuario)
    if not libres:
        raise ValidationError({"plazas": SIN_CAMAS_PARA_INGRESO_DIRECTO})

    caso = crear_caso(
        usuario=usuario,
        origen=Origen.DISPOSITIVO,
        datos_formulario1=_formulario1_en_el_dispositivo(datos_formulario1, dispositivo),
        uuid_cliente=uuid_cliente,
        devolver_existente=True,
    )
    if caso.ya_existia:  # el mismo envío llegó dos veces a la vez, o se sumó a un caso que se cerró después
        if caso.familia_ya_tenia_caso:
            return _con_lo_que_contesto(caso, uuid_cliente, usuario)
        return _con_sus_reservas(caso)
    if caso.familia_ya_tenia_caso:
        caso = _ingresar_en_el_caso_abierto(caso, dispositivo, usuario, personas=caso.personas_declaradas_ahora)
        anotar_resultado_del_envio(caso, uuid_cliente, usuario)
        return caso
    caso = _bloquear_caso(caso)
    caso = _abrir_el_ingreso(
        caso=caso,
        dispositivo=dispositivo,
        usuario=usuario,
        libres=libres,
        momento=caso.creado,
        detalle=f"Ingreso directo en {dispositivo.nombre}, sin pasar por la mesa",
    )
    caso.familia_ya_tenia_caso = False  # ``_bloquear_caso`` volvió a leer el caso: no trae las marcas del alta
    return caso


def _caso_abierto_del_dni(dni):
    """El caso abierto de la familia de ``dni``. **La guardia pasa el DNI, nunca el id del caso**: un id armado a
    mano le dejaría sumarse a —y cancelar la derivación de— un caso que no es el de la familia que tiene delante.
    """

    from programas.services.ingreso import buscar_ciudadano_por_dni

    ciudadano = buscar_ciudadano_por_dni(normalizar_dni(dni or ""))
    caso = caso_abierto_de_la_familia(ciudadano)
    if caso is None:
        raise ValidationError({"dni": SIN_CASO_ABIERTO})
    return caso


@transaction.atomic
def ingresar_con_caso_abierto(*, dispositivo, usuario, dni):
    """«Ingresar con este caso»: la guardia ingresa a la familia sobre el caso que ya tenía abierto (Cambio 579).

    Es la salida del modal «Esta familia ya tiene un caso abierto»: no hace falta cargar el Formulario 1 de
    nuevo. Mismas reglas de alcance que «Ingresar igual» (toda la institución y camas libres). El caso se
    resuelve por el ``dni`` del responsable o de un integrante. Ver :func:`_ingresar_en_el_caso_abierto` por lo
    que pasa según el estado del caso.
    """

    if not puede_ingresar_igual(usuario, dispositivo):
        raise PermissionDenied(SIN_ALCANCE)
    if not dispositivo_elegible(dispositivo):
        raise ValidationError({"dispositivo": DISPOSITIVO_NO_ELEGIBLE})
    return _ingresar_en_el_caso_abierto(_caso_abierto_del_dni(dni), dispositivo, usuario, personas=0)


def _ingresar_en_el_caso_abierto(caso, dispositivo, usuario, *, personas):
    """El ingreso de la familia sobre su caso abierto, según cómo esté. Bloquea el caso y su última derivación.

    * ``NUEVO`` / ``EN_GESTION`` — el caso pasa a ser un ingreso en ``dispositivo``: derivación aceptada, camas
      y filas, como «Ingresar igual» pero sin abrir otro caso. Pide camas libres.
    * ``DERIVADO`` — con la derivación pendiente a **otra** institución, se cancela (se liberan las camas que
      hubiera, queda en el historial y la mesa lo ve) y sigue como el anterior. Si la pendiente es a este
      dispositivo, se acepta en vez de ingresar igual.
    * ``INGRESO_EN_CURSO`` — en este dispositivo, no hay nada que hacer: sigue con ese ingreso. En otra
      institución, no se toca el ingreso de nadie: :class:`CasoAbiertoEnOtraInstitucion`.
    * ``ALOJADO`` — en este dispositivo, las personas que llegan después se suman al caso (decisión 8,
      :func:`_sumar_personas_al_alojado`); en otro, :class:`CasoAbiertoEnOtraInstitucion`.

    ``personas`` son las declaradas ahora por quien llegó (0 si no se sabe).
    """

    caso = _bloquear_caso(caso)
    derivacion = _ultima_derivacion_bloqueada(caso)
    if caso.estado == Estado.CERRADO:
        raise EstadoCambio(CASO_YA_CERRADO.format(numero=caso.numero), estado_actual=caso.estado, caso=caso)
    en_este = derivacion is not None and derivacion.dispositivo_id == dispositivo.pk
    caso.familia_ya_tenia_caso = True

    if caso.estado == Estado.INGRESO_EN_CURSO:
        if en_este and derivacion.estado == Derivacion.Estado.ACEPTADA:
            caso.ya_existia = False
            return _con_sus_reservas(caso)
        raise CasoAbiertoEnOtraInstitucion(caso, dispositivo)
    if caso.estado == Estado.ALOJADO:
        if en_este:
            return _sumar_personas_al_alojado(caso, dispositivo, usuario, personas)
        raise CasoAbiertoEnOtraInstitucion(caso, dispositivo)

    libres = camas_libres(dispositivo, usuario=usuario)
    if not libres:
        raise ValidationError({"plazas": SIN_CAMAS_PARA_INGRESO_DIRECTO})
    if caso.estado == Estado.DERIVADO:
        if derivacion is None or derivacion.estado != Derivacion.Estado.PENDIENTE:
            raise EstadoCambio(
                f"El caso {caso.numero} cambió mientras tanto. Buscá a la familia de nuevo.",
                estado_actual=caso.estado,
                caso=caso,
            )
        if en_este:
            raise ValidationError({"dni": A_RECIBIR_NO_SE_INGRESA_IGUAL})
        cancelar_derivacion_por_llegada(
            caso=caso, derivacion=derivacion, dispositivo=dispositivo, usuario=usuario, en_la_puerta=False
        )
    return _abrir_el_ingreso(
        caso=caso,
        dispositivo=dispositivo,
        usuario=usuario,
        libres=libres,
        momento=timezone.now(),
        detalle=f"Ingreso en {dispositivo.nombre}: la familia ya tenía este caso abierto",
    )


def _sumar_personas_al_alojado(caso, dispositivo, usuario, personas):
    """Decisión 8: las personas que llegan después se suman al caso ya alojado, sin abrir otro.

    El ingreso vuelve a estar en curso (la derivación sigue aceptada) para que la guardia confirme a quienes
    faltan con su ficha y su cama. Se suman las personas declaradas ahora que no cubren las filas que ya
    estaban sin confirmar; sin cantidad (el modal), una, si no quedaba nadie por confirmar. Las marcas de
    «ingreso parcial» y de la diferencia se limpian: el cierre las vuelve a escribir.
    """

    grupo = caso.grupo
    pendientes = sum(1 for fila in _filas_de(grupo) if not fila.confirmada)
    sumar = max(personas - pendientes, 0) if personas else 0
    if pendientes + sumar == 0:
        sumar = 1
    if sumar:
        grupo.total_declarado += sumar
        grupo.save(update_fields=["total_declarado", "modificado"])
        _asegurar_filas(grupo)
    caso.estado = Estado.INGRESO_EN_CURSO
    caso.total_alojado = None
    caso.situacion = {clave: valor for clave, valor in caso.situacion.items() if clave != "diferencia"}
    caso.save(update_fields=["estado", "total_alojado", "situacion", "modificado"])
    detalle = (
        f"Llegaron más personas de la familia a {dispositivo.nombre}: se suman a este caso "
        f"({sumar} nueva{'s' if sumar != 1 else ''}, {pendientes} sin confirmar) · el ingreso vuelve a estar en curso"
    )
    _trazar(caso, usuario, Accion.PERSONAS_SUMADAS, estado_anterior=Estado.ALOJADO, detalle=detalle)
    _anotar_en_bitacora(
        dispositivo,
        usuario,
        f"Emergencia · personas sumadas a la familia alojada · caso N.° {caso.numero}",
        timezone.now(),
    )
    caso.ya_existia = False
    # No se reservó nada para ellas: las camas se piden al confirmarlas. Todas las sumadas faltan.
    caso.reservadas, caso.faltantes = 0, sumar
    return caso


@archivos_atomicos
@transaction.atomic
def avisar_a_la_mesa(*, dispositivo, usuario, datos_formulario1, uuid_cliente=None):
    """«Avisar a la mesa»: la familia está en la puerta y no hay derivación (M2-6, 03 §10).

    Crea un caso ``NUEVO`` de origen ``DISPOSITIVO`` —la mesa lo ve en la bandeja y lo deriva
    a donde corresponda— con la marca «En la puerta de X» en
    ``caso.situacion["en_la_puerta_de"]``::

        {"dispositivo_id": 12, "dispositivo": "Club Sarmiento"}

    No reserva nada ni exige camas libres: es justo lo que se usa cuando no hay lugar.
    Exige ``dispositivo.admitir`` sobre ese dispositivo, con cualquier alcance —también Edificios—
    (:func:`puede_avisar_a_la_mesa`). Idempotente por ``uuid_cliente``.

    **Una familia, un caso abierto** (Cambio 579): si la familia ya tiene un caso abierto no se crea otro; el
    aviso se suma a ese caso (:func:`_avisar_sobre_el_caso_abierto`).

    Devuelve el ``CasoEmergencia`` con ``ya_existia`` y ``familia_ya_tenia_caso``.
    """

    if not puede_avisar_a_la_mesa(usuario, dispositivo):
        raise PermissionDenied(SIN_ALCANCE)
    caso = crear_caso(
        usuario=usuario,
        origen=Origen.DISPOSITIVO,
        datos_formulario1=_formulario1_en_el_dispositivo(datos_formulario1, dispositivo),
        uuid_cliente=uuid_cliente,
        devolver_existente=True,
    )
    if caso.ya_existia:
        if caso.familia_ya_tenia_caso:  # el reenvío de un aviso que se sumó a un caso que ya existía
            return caso
        puerta = (caso.situacion or {}).get(CasoEmergencia.SITUACION_EN_LA_PUERTA) or {}
        if caso.origen != Origen.DISPOSITIVO or puerta.get("dispositivo_id") != dispositivo.pk:
            raise UuidEnUso()
        return caso
    if caso.familia_ya_tenia_caso:
        return _avisar_sobre_el_caso_abierto(caso, dispositivo, usuario)
    caso = _bloquear_caso(caso)
    marcar_en_la_puerta(caso, dispositivo)
    _trazar(
        caso,
        usuario,
        Accion.AVISO_A_LA_MESA,
        estado_anterior=caso.estado,
        detalle=f"En la puerta de {dispositivo.nombre} · esperando derivación",
    )
    caso.ya_existia = False  # ``_bloquear_caso`` volvió a leer el caso: no trae las marcas del alta
    caso.familia_ya_tenia_caso = False
    return caso


@transaction.atomic
def avisar_con_caso_abierto(*, dispositivo, usuario, dni):
    """«Avisar a la mesa» desde el modal «Esta familia ya tiene un caso abierto»: sin cargar el Formulario 1."""

    if not puede_avisar_a_la_mesa(usuario, dispositivo):
        raise PermissionDenied(SIN_ALCANCE)
    return _avisar_sobre_el_caso_abierto(_caso_abierto_del_dni(dni), dispositivo, usuario)


def _avisar_sobre_el_caso_abierto(caso, dispositivo, usuario):
    """El aviso de la puerta, sumado al caso que la familia ya tenía. **Nunca crea un caso.**

    Con la derivación pendiente a otra institución, la cancela (:func:`cancelar_derivacion_por_llegada`): la
    familia está acá. Si la derivación o el ingreso son de **este** dispositivo, no se avisa a la mesa: la
    guardia tiene que seguir con esa derivación.
    """

    caso = _bloquear_caso(caso)
    derivacion = _ultima_derivacion_bloqueada(caso)
    if caso.estado == Estado.CERRADO:
        raise EstadoCambio(CASO_YA_CERRADO.format(numero=caso.numero), estado_actual=caso.estado, caso=caso)
    en_este = derivacion is not None and derivacion.dispositivo_id == dispositivo.pk
    # La misma regla que ofrece la búsqueda (``_con_caso_abierto``): con el ingreso o el alojamiento ya en
    # marcha no hay nada que avisar. En otra institución se dice que la familia está en curso; acá, qué sigue.
    if caso.estado in (Estado.INGRESO_EN_CURSO, Estado.ALOJADO) and not en_este:
        raise CasoAbiertoEnOtraInstitucion(
            caso,
            dispositivo,
            mensaje=(
                f"La familia ya tiene el caso {caso.numero} en curso en otra institución: no hay nada que avisar "
                "a la mesa."
            ),
        )
    if en_este and caso.estado == Estado.ALOJADO:
        raise ValidationError({"dni": YA_ALOJADA_NADA_QUE_AVISAR})
    if en_este and caso.estado in (Estado.DERIVADO, Estado.INGRESO_EN_CURSO):
        raise ValidationError(mensaje_otro_edificio(derivacion))

    estado_anterior = caso.estado
    if caso.estado == Estado.DERIVADO and derivacion is not None and derivacion.estado == Derivacion.Estado.PENDIENTE:
        cancelar_derivacion_por_llegada(
            caso=caso, derivacion=derivacion, dispositivo=dispositivo, usuario=usuario, en_la_puerta=True
        )
    else:
        marcar_en_la_puerta(caso, dispositivo)
    _trazar(
        caso,
        usuario,
        Accion.AVISO_A_LA_MESA,
        estado_anterior=estado_anterior,
        detalle=f"En la puerta de {dispositivo.nombre} · la familia ya tenía este caso: el aviso se suma a él",
    )
    caso.ya_existia = False
    caso.familia_ya_tenia_caso = True
    return caso


def es_ingreso_directo(caso):
    """¿El caso nació de «Ingresar igual»? Es ``CasoEmergencia.es_ingreso_directo``: la regla vive en el modelo."""

    return caso.es_ingreso_directo
