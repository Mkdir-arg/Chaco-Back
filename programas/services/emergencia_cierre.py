"""Etapa 3 de Emergencia, paso 3: cerrar el ingreso, y el cierre del caso cuando egresa el último.

``alojar_familia`` (N de N, M2-5), ``cerrar_con_diferencia`` (RN-3.9), ``cancelar_ingreso``
(03 §5), ``cancelar_ingreso_por_la_mesa`` (Cambio 535) y el receptor de ``estadia_egresada`` (RN-3.12). Se importan desde
``programas.services.emergencia_alojar``, que tiene el contrato de la etapa y explica por
qué el egreso no forma un ciclo de candados con este módulo.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from programas.models import (
    CasoEmergencia,
    Derivacion,
    Estadia,
    IntegranteGrupo,
    Sector,
)
from programas.senales import estadia_egresada
from programas.services.emergencia import EstadoCambio
from programas.services.emergencia_comun import _bloquear_caso, _nombre_de, _trazar
from programas.services.emergencia_ingreso_comun import (
    Accion,
    Estado,
    _abrir_ingreso,
    _anotar_en_bitacora,
    _confirmadas,
    _devolver_a_la_mesa,
    _filas_de,
    acciones_del_ingreso,
    mensaje_faltan_confirmar,
)
from programas.services.emergencia_programa import puede_supervisar_la_mesa
from programas.services.reservas_derivacion import liberar_reservas_de_derivacion


class MotivoDiferencia(models.TextChoices):
    """Por qué se alojaron menos personas que las declaradas (RN-3.9)."""

    QUEDO_CON_FAMILIARES = "QUEDO_CON_FAMILIARES", "Quedó con familiares"
    NO_LLEGO = "NO_LLEGO", "No llegó al centro"
    DERIVADO_A_SALUD = "DERIVADO_A_SALUD", "Derivado a salud"
    OTRO = "OTRO", "Otro"


MOTIVO_RESERVAS_AL_ALOJAR = "Emergencia: familia alojada, sobraron camas reservadas."


def _cerrar_si_no_queda_nadie(caso, usuario, momento):
    """RN-3.12: un caso ``ALOJADO`` sin ningún integrante con estadía abierta pasa a ``CERRADO``.

    Se llama **con el caso bloqueado**. Devuelve si lo cerró. La cuenta mira la estadía y no
    ``egresado_en``: lo que decide es si alguien sigue adentro.
    """

    if caso.estado != Estado.ALOJADO:
        return False
    quedan = IntegranteGrupo.objects.filter(grupo_id=caso.grupo_id, estadia__estado=Estadia.Estado.ACTIVA).exists()
    if quedan:
        return False
    caso.estado = Estado.CERRADO
    caso.marcar("cerrado_en", momento)
    caso.motivo_cierre = CasoEmergencia.MotivoCierre.TODOS_EGRESADOS
    caso.save(update_fields=["estado", "cerrado_en", "motivo_cierre", "modificado"])
    _trazar(
        caso,
        usuario,
        Accion.CERRADO_POR_EGRESO,
        estado_anterior=Estado.ALOJADO,
        detalle="Cerrado: egresó la última persona de la familia",
    )
    return True


def _sector_del_dispositivo(sector, dispositivo):
    """``(id, nombre)`` del sector/ala elegido, que tiene que ser del dispositivo; ``(None, "")`` sin él."""

    if sector in (None, ""):
        return None, ""
    pk = sector.pk if isinstance(sector, Sector) else sector
    try:
        fila = Sector.objects.filter(pk=int(pk), dispositivo_id=dispositivo.pk).values_list("pk", "nombre").first()
    except (TypeError, ValueError):
        fila = None
    if fila is None:
        raise ValidationError({"sector": "Elegí un sector de este dispositivo."})
    return fila


# ---------------------------------------------------------------------------
# Cerrar el ingreso (M2-5, RN-3.9)
# ---------------------------------------------------------------------------


@transaction.atomic
def alojar_familia(
    *,
    caso,
    usuario,
    sector=None,
    aula="",
    tarjeta_entregada=False,
    tarjeta_numero="",
    encargado=None,
    derivacion_vista=None,
):
    """«Familia alojada»: cierra el ingreso con **N de N** confirmadas (M2-5).

    Exige que **todas** las filas de la familia estén confirmadas; con una sola sin
    confirmar, ``ValidationError`` (lo que corresponde es confirmarla o cerrar con
    diferencia). Guarda la sección 4 del Formulario 1 en ``caso.situacion["alojamiento"]``::

        {"sector_id": 3, "sector": "Pabellón A", "aula": "Aula 3",
         "tarjeta_entregada": true, "tarjeta_numero": "0042", "encargado": "Ana López",
         "encargado_id": 12}

    ``sector`` es un ``Sector`` del dispositivo o su id (opcional); con la tarjeta entregada,
    su número es obligatorio. Quien recibe es **siempre** ``usuario`` (el que aloja): se guarda su
    id (``encargado_id``) y su nombre (``encargado``, para mostrarlo). El parámetro ``encargado``
    sigue aceptándose por la app vieja, pero se ignora.
    ``derivacion_vista``: el id de la derivación que mostraba la pantalla; si ya no es la del
    caso, :class:`EstadoCambio` sin escribir nada (``_abrir_ingreso``, Cambio 477).

    El caso pasa a ``ALOJADO`` con ``alojado_en`` y ``total_alojado``; las reservas de la
    derivación que hubieran sobrado se liberan (la mesa pudo pedir más camas que personas);
    queda la traza y la novedad ``GENERAL`` «familia alojada 7 de 7».

    Devuelve el ``CasoEmergencia``, con ``caso.reservas_liberadas``.
    """

    caso, derivacion = _abrir_ingreso(caso, usuario, Estado.INGRESO_EN_CURSO, derivacion_vista=derivacion_vista)
    dispositivo = derivacion.dispositivo
    grupo = caso.grupo
    filas = _filas_de(grupo)
    confirmadas, total = _confirmadas(filas), max(grupo.total_declarado, len(filas))
    if not acciones_del_ingreso(estado=caso.estado, confirmadas=confirmadas, total=total)["alojar"]:
        raise ValidationError(mensaje_faltan_confirmar(total - confirmadas))

    aula = (aula or "").strip()
    tarjeta_numero = (tarjeta_numero or "").strip()
    encargado = _nombre_de(usuario)
    errores = {}
    if len(aula) > 80:
        errores["aula"] = "No puede tener más de 80 caracteres."
    if tarjeta_entregada and not tarjeta_numero:
        errores["tarjeta_numero"] = "Indicá el número de la tarjeta familiar entregada."
    if len(tarjeta_numero) > 40:
        errores["tarjeta_numero"] = "No puede tener más de 40 caracteres."
    if errores:
        raise ValidationError(errores)
    sector_id, sector_nombre = _sector_del_dispositivo(sector, dispositivo)

    ahora = timezone.now()
    liberadas = liberar_reservas_de_derivacion(derivacion=derivacion, usuario=usuario, motivo=MOTIVO_RESERVAS_AL_ALOJAR)
    caso.estado = Estado.ALOJADO
    caso.marcar("alojado_en", ahora)
    caso.total_alojado = confirmadas
    caso.situacion = {
        **caso.situacion,
        CasoEmergencia.SITUACION_ALOJAMIENTO: {
            "sector_id": sector_id,
            "sector": sector_nombre,
            "aula": aula,
            "tarjeta_entregada": bool(tarjeta_entregada),
            "tarjeta_numero": tarjeta_numero if tarjeta_entregada else "",
            "encargado": encargado,
            "encargado_id": getattr(usuario, "pk", None),
        },
    }
    caso.save(update_fields=["estado", "alojado_en", "total_alojado", "situacion", "modificado"])
    donde = " · ".join(parte for parte in (sector_nombre, aula) if parte)
    resumen = f"{confirmadas} de {grupo.total_declarado}"
    _trazar(
        caso,
        usuario,
        Accion.ALOJADO,
        estado_anterior=Estado.INGRESO_EN_CURSO,
        detalle=f"Familia alojada en {dispositivo.nombre} · {resumen}" + (f" · {donde}" if donde else ""),
    )
    _anotar_en_bitacora(
        dispositivo,
        usuario,
        f"Emergencia · familia alojada {resumen} · caso N.° {caso.numero}",
        ahora,
        derivacion.edificio_id,
    )
    caso.reservas_liberadas = liberadas
    _cerrar_si_no_queda_nadie(caso, usuario, ahora)
    return caso


@transaction.atomic
def cerrar_con_diferencia(*, caso, usuario, motivo, observacion="", derivacion_vista=None):
    """Cierra el ingreso con **menos personas que las declaradas** (HU-3.4, RN-3.9, RU-22).

    Requiere al menos una confirmada y un ``motivo`` de :class:`MotivoDiferencia`; con «Otro»
    (es el de «no tiene número de documento», D-10) la ``observacion`` es obligatoria. Con
    todas confirmadas no hay diferencia: se usa ``alojar_familia``.

    ``total_alojado`` = confirmadas; las reservas sobrantes de la derivación pasan a
    ``LIBERADA``; el caso queda ``ALOJADO`` —es el estado de «la familia está acá»— con la
    marca parcial (``caso.ingreso_parcial``). El motivo queda en la traza y en
    ``caso.situacion["diferencia"]``::

        {"motivo": "NO_LLEGO", "motivo_texto": "No llegó al centro", "observacion": "…",
         "confirmadas": 5, "declaradas": 7}

    Deja la novedad ``GENERAL`` de la bitácora con el motivo. ``derivacion_vista``, como en
    :func:`alojar_familia`.

    Devuelve el ``CasoEmergencia``, con ``caso.reservas_liberadas``.
    """

    observacion = (observacion or "").strip()
    if motivo not in MotivoDiferencia.values:
        raise ValidationError({"motivo": "Elegí por qué llegaron menos personas."})
    if motivo == MotivoDiferencia.OTRO and not observacion:
        raise ValidationError({"observacion": "Con el motivo «Otro», contá qué pasó."})

    caso, derivacion = _abrir_ingreso(caso, usuario, Estado.INGRESO_EN_CURSO, derivacion_vista=derivacion_vista)
    dispositivo = derivacion.dispositivo
    grupo = caso.grupo
    confirmadas = IntegranteGrupo.objects.filter(grupo_id=grupo.pk, confirmada_en__isnull=False).count()
    if not acciones_del_ingreso(estado=caso.estado, confirmadas=confirmadas, total=grupo.total_declarado)["diferencia"]:
        if confirmadas < 1:
            raise ValidationError(
                "Todavía no confirmaste a nadie. Si la familia no llegó, cancelá el ingreso para devolverle el caso "
                "a la mesa."
            )
        raise ValidationError("Están todas las personas confirmadas: no hay diferencia. Usá «Familia alojada».")

    ahora = timezone.now()
    rotulo = MotivoDiferencia(motivo).label
    liberadas = liberar_reservas_de_derivacion(
        derivacion=derivacion, usuario=usuario, motivo=f"Emergencia: ingreso cerrado con diferencia ({rotulo.lower()})."
    )
    caso.estado = Estado.ALOJADO
    caso.marcar("alojado_en", ahora)
    caso.total_alojado = confirmadas
    caso.situacion = {
        **caso.situacion,
        CasoEmergencia.SITUACION_DIFERENCIA: {
            "motivo": motivo,
            "motivo_texto": rotulo,
            "observacion": observacion,
            "confirmadas": confirmadas,
            "declaradas": grupo.total_declarado,
        },
    }
    caso.save(update_fields=["estado", "alojado_en", "total_alojado", "situacion", "modificado"])
    resumen = f"{confirmadas} de {grupo.total_declarado}"
    _trazar(
        caso,
        usuario,
        Accion.ALOJADO_CON_DIFERENCIA,
        estado_anterior=Estado.INGRESO_EN_CURSO,
        detalle=(
            f"Ingreso parcial en {dispositivo.nombre} · {resumen} · {rotulo}"
            + (f" · {observacion}" if observacion else "")
        ),
    )
    # La bitácora la lee quien tiene `dispositivo.ver`: va el motivo del catálogo, no la observación libre.
    _anotar_en_bitacora(
        dispositivo,
        usuario,
        f"Emergencia · ingreso cerrado con diferencia {resumen} · {rotulo.lower()} · caso N.° {caso.numero}",
        ahora,
        derivacion.edificio_id,
    )
    caso.reservas_liberadas = liberadas
    _cerrar_si_no_queda_nadie(caso, usuario, ahora)
    return caso


@transaction.atomic
def cancelar_ingreso(*, caso, usuario, motivo, derivacion_vista=None):
    """Cancela un ingreso aceptado en el que **no se confirmó a nadie** (03 §5).

    ``motivo`` es un texto obligatorio (hasta 200 caracteres). Las reservas de la derivación
    se liberan, la derivación queda ``RECHAZADA`` con ese motivo y el caso vuelve a la mesa:
    a ``EN_GESTION`` con el mismo operador, o a la bandeja (``NUEVO``) si nadie lo había
    tomado —un ingreso directo—. Las filas de la familia quedan, sin confirmar.

    Con una sola persona confirmada no se cancela: se cierra con diferencia.

    ``derivacion_vista`` es el id de la derivación que mostraba la pantalla. Cancelar no es
    idempotente y actúa sobre la **última** derivación: sin él, el reintento de un cancelar que
    ya llegó, después de que la mesa volviera a derivar al mismo dispositivo y otra guardia
    aceptara, cancelaría ese ingreso nuevo con el motivo viejo. Con él, :class:`EstadoCambio`
    si ya no es la del caso; si es la misma y el cancelar ya llegó, el 409 de estado
    (``EN_GESTION``/``NUEVO``) de siempre (Cambio 477).

    Devuelve el ``CasoEmergencia``, con ``caso.reservas_liberadas``.
    """

    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError({"motivo": "Indicá por qué se cancela el ingreso."})
    if len(motivo) > 200:
        raise ValidationError({"motivo": "El motivo no puede tener más de 200 caracteres."})

    caso, derivacion = _abrir_ingreso(caso, usuario, Estado.INGRESO_EN_CURSO, derivacion_vista=derivacion_vista)
    dispositivo = derivacion.dispositivo
    confirmadas = IntegranteGrupo.objects.filter(grupo_id=caso.grupo_id, confirmada_en__isnull=False).count()
    if not acciones_del_ingreso(estado=caso.estado, confirmadas=confirmadas, total=caso.grupo.total_declarado)[
        "cancelar"
    ]:
        raise ValidationError("Ya hay personas confirmadas con cama: cerrá el ingreso con diferencia.")

    liberadas = liberar_reservas_de_derivacion(
        derivacion=derivacion, usuario=usuario, motivo="Emergencia: ingreso cancelado."
    )
    derivacion.estado = Derivacion.Estado.RECHAZADA
    derivacion.motivo = motivo
    derivacion.respondida_por = usuario
    derivacion.respondida_en = timezone.now()
    derivacion.save(update_fields=["estado", "motivo", "respondida_por", "respondida_en", "modificado"])
    _devolver_a_la_mesa(caso)
    _trazar(
        caso,
        usuario,
        Accion.INGRESO_CANCELADO,
        estado_anterior=Estado.INGRESO_EN_CURSO,
        detalle=f"Ingreso cancelado por {dispositivo.nombre}: {motivo}",
    )
    caso.reservas_liberadas = liberadas
    return caso


SIN_PERMISO_DE_CANCELAR_INGRESO = "Solo quien supervisa la mesa puede cancelar un ingreso en curso."
INGRESO_CON_CONFIRMADAS = (
    "Ya hay personas confirmadas con cama: el ingreso no se cancela desde la mesa. "
    "Pedile al dispositivo que lo cierre con diferencia."
)
MOTIVO_RESERVAS_CANCELADO_POR_LA_MESA = "Emergencia: la mesa canceló el ingreso."


def puede_cancelar_ingreso_por_la_mesa(caso, *, es_supervisor, confirmadas):
    """¿Se ofrece «Cancelar ingreso» en la ficha de la mesa? **Pura, sin consultas** (Cambio 535).

    La misma regla que vuelve a exigir :func:`cancelar_ingreso_por_la_mesa` sobre las filas bloqueadas:
    quien supervisa, caso en ingreso y nadie confirmado (``acciones_del_ingreso(...)["cancelar"]``).
    """

    return (
        bool(es_supervisor) and acciones_del_ingreso(estado=caso.estado, confirmadas=confirmadas, total=0)["cancelar"]
    )


@transaction.atomic
def cancelar_ingreso_por_la_mesa(*, caso, usuario, motivo, derivacion_vista=None):
    """La mesa destraba un ingreso aceptado que no avanza: **solo quien supervisa**, con motivo (Cambio 535).

    Un caso en «Ingreso en curso» no vence (la derivación ``ACEPTADA`` no tiene plazo) y, si la
    guardia no confirma a nadie ni lo cancela, queda tomando camas para siempre. Esto es la salida
    de la mesa, con las mismas reglas que ``cancelar_ingreso`` de la guardia:

    * **sin ninguna persona confirmada**: con una sola ya hay alguien adentro y el ingreso se cierra
      con diferencia, que es de la guardia (``ValidationError``);
    * libera las reservas vigentes de la derivación (sin alcance sobre el dispositivo: no es una
      decisión sobre esas camas sino la consecuencia de que el ingreso terminó);
    * la derivación queda ``CANCELADA`` con el motivo —la guardia que abra la familia lee «La mesa
      canceló la derivación»— y el caso vuelve a quien lo tenía o a la bandeja;
    * traza ``INGRESO_CANCELADO`` por supervisor, con el motivo, y una novedad en la bitácora del
      turno del dispositivo **sin** el motivo libre (la lee quien tiene ``dispositivo.ver``).

    No hay vencimiento automático: lo decide una persona. ``derivacion_vista`` es la derivación que
    mostró la ficha; si ya no es la vigente, :class:`EstadoCambio` (Cambio 477).

    Candados: caso → derivación → plazas → reservas, el orden global de Emergencia.
    Devuelve el caso, con ``caso.reservas_liberadas``.
    """

    if not puede_supervisar_la_mesa(usuario):
        raise PermissionDenied(SIN_PERMISO_DE_CANCELAR_INGRESO)
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError({"motivo": "Indicá por qué se cancela el ingreso."})
    if len(motivo) > 200:
        raise ValidationError({"motivo": "El motivo no puede tener más de 200 caracteres."})

    caso = _bloquear_caso(caso)
    pk_vigente = (
        Derivacion.objects.filter(clave_vigente=caso.pk, estado=Derivacion.Estado.ACEPTADA)
        .values_list("pk", flat=True)
        .first()
    )
    derivacion = Derivacion.objects.select_for_update().filter(pk=pk_vigente).first() if pk_vigente else None
    if derivacion_vista not in (None, "") and (
        derivacion is None or int(getattr(derivacion_vista, "pk", derivacion_vista)) != derivacion.pk
    ):
        raise EstadoCambio(
            f"El ingreso del caso {caso.numero} cambió. Recargá la ficha.", estado_actual=caso.estado, caso=caso
        )
    if derivacion is None or derivacion.estado != Derivacion.Estado.ACEPTADA or caso.estado != Estado.INGRESO_EN_CURSO:
        raise EstadoCambio(
            f"El caso {caso.numero} ya no tiene un ingreso en curso. Recargá la ficha.",
            estado_actual=caso.estado,
            caso=caso,
        )
    confirmadas = IntegranteGrupo.objects.filter(grupo_id=caso.grupo_id, confirmada_en__isnull=False).count()
    if not puede_cancelar_ingreso_por_la_mesa(caso, es_supervisor=True, confirmadas=confirmadas):
        raise ValidationError(INGRESO_CON_CONFIRMADAS)

    dispositivo = derivacion.dispositivo
    liberadas = liberar_reservas_de_derivacion(
        derivacion=derivacion, usuario=usuario, motivo=MOTIVO_RESERVAS_CANCELADO_POR_LA_MESA, verificar_alcance=False
    )
    ahora = timezone.now()
    derivacion.estado = Derivacion.Estado.CANCELADA
    derivacion.motivo = motivo
    derivacion.respondida_por = usuario
    derivacion.respondida_en = ahora
    derivacion.save(update_fields=["estado", "motivo", "respondida_por", "respondida_en", "modificado"])
    _devolver_a_la_mesa(caso)
    _trazar(
        caso,
        usuario,
        Accion.INGRESO_CANCELADO,
        estado_anterior=Estado.INGRESO_EN_CURSO,
        detalle=f"Ingreso en {dispositivo.nombre} cancelado por la mesa: {motivo}",
        por_supervisor=True,
    )
    _anotar_en_bitacora(
        dispositivo,
        usuario,
        f"Emergencia · la mesa canceló el ingreso del caso N.° {caso.numero} · camas liberadas: {liberadas}",
        ahora,
        derivacion.edificio_id,
    )
    caso.reservas_liberadas = liberadas
    return caso


# ---------------------------------------------------------------------------
# Egreso (RN-3.12)
# ---------------------------------------------------------------------------


def al_egresar_estadia(sender, estadia, usuario=None, **_kwargs):
    """Receptor de ``estadia_egresada``: marca al integrante y cierra el caso si no queda nadie.

    Corre **dentro de la transacción del egreso** (``estadias.egresar_persona``), con la fila
    de la estadía bloqueada: si falla, el egreso se deshace. Por eso es mínimo:

    * Para una estadía que **no es de Emergencia** —casi todas— hace **una** consulta y vuelve.
    * Para la de un integrante: bloquea el caso (**antes** de escribir al integrante, ver el
      docstring del módulo), le pone ``egresado_en`` y deja la traza. Si el caso está
      ``ALOJADO`` y ya no queda ningún integrante con estadía abierta, pasa a ``CERRADO`` con
      motivo «Todos egresados», ``cerrado_en`` y su traza.

    Un egreso con el ingreso todavía en curso solo marca al integrante: el caso lo cierra la
    guardia (alojar o diferencia), y ahí se vuelve a mirar si quedó alguien.
    """

    fila = IntegranteGrupo.objects.filter(estadia_id=estadia.pk).values_list("pk", "grupo_id", "orden").first()
    if fila is None:
        return
    integrante_pk, grupo_id, orden = fila
    caso = CasoEmergencia.objects.select_for_update().get(grupo_id=grupo_id)
    momento = estadia.fecha_egreso or timezone.now()
    IntegranteGrupo.objects.filter(pk=integrante_pk).update(egresado_en=momento, modificado=timezone.now())
    _trazar(
        caso,
        usuario,
        Accion.INTEGRANTE_EGRESADO,
        estado_anterior=caso.estado,
        detalle=f"Egresó la persona {orden} de la familia",
    )
    _cerrar_si_no_queda_nadie(caso, usuario, timezone.now())


def conectar_receptores():
    """Conecta el receptor del egreso. Lo llama ``ProgramasConfig.ready()``; es idempotente."""

    estadia_egresada.connect(al_egresar_estadia, dispatch_uid="programas.emergencia_alojar.al_egresar_estadia")
