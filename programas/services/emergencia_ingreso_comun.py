"""Las piezas que comparten los caminos de la etapa 3 de Emergencia (alojar).

Alcance, candados del caso y de la derivación, el estado de un ingreso ya aceptado, las
filas de la familia, la reserva de camas, la bitácora del turno y **la** regla de qué se
puede hacer con un ingreso (:func:`acciones_del_ingreso`). Las usan la recepción, la
confirmación, el cierre y el ingreso sin derivación; las dependencias van en un solo
sentido: ninguno de esos módulos se importa desde acá (``programas.tests.test_arquitectura``).

El orden de los candados y el resto del contrato de la etapa están en el docstring de
``programas.services.emergencia_alojar``.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from programas.models import (
    CasoEmergencia,
    Derivacion,
    Dispositivo,
    EntradaBitacora,
    IntegranteGrupo,
    TrazaCaso,
)
from programas.services.bitacora import anotar_novedad_automatica
from programas.services.dispositivos import puede_operar_dispositivo, puede_operar_edificio, puede_operar_institucion
from programas.services.emergencia import EstadoCambio
from programas.services.emergencia_comun import _bloquear_caso, _hora
from programas.services.reservas_derivacion import reservar_plazas_de_derivacion

Estado = CasoEmergencia.Estado
Origen = CasoEmergencia.Origen
Accion = TrazaCaso.Accion

CAP_ADMITIR = "dispositivo.admitir"

SIN_ALCANCE = "No formás parte del equipo de este dispositivo."

CAMAS_TOMADAS_MIENTRAS_ACEPTABA = (
    "Mientras aceptabas, alguien tomó una de las camas que se iban a reservar. Volvé a tocar «Aceptar»."
)


def _dia_y_mes(momento):
    """«3/11», en hora local. A mano y no con ``%-d``, que no existe en Windows."""

    local = timezone.localtime(momento)
    return f"{local.day}/{local.month}"


def _personas(cantidad):
    return "1 persona" if cantidad == 1 else f"{cantidad} personas"


def _camas(cantidad):
    return "1 cama" if cantidad == 1 else f"{cantidad} camas"


# ---------------------------------------------------------------------------
# Alcance, candados y estado del ingreso
# ---------------------------------------------------------------------------


def _exigir_alcance(usuario, dispositivo, derivacion=None):
    """RU-8: ``dispositivo.admitir`` sobre **este** dispositivo. Sin él, ``PermissionDenied``.

    Con alcance Edificios (Cambio 523): si se conoce la ``derivacion``, tiene que ser de uno de sus edificios
    (``derivacion.edificio``; sin edificio no entra). Lo que no cuelga de una derivación tiene su propia regla:
    :func:`puede_ingresar_igual` y :func:`puede_avisar_a_la_mesa`.
    """

    if dispositivo is None:
        raise PermissionDenied(SIN_ALCANCE)
    if derivacion is not None:
        permitido = puede_operar_edificio(usuario, dispositivo, derivacion.edificio_id, CAP_ADMITIR)
    else:
        permitido = puede_operar_dispositivo(usuario, dispositivo, CAP_ADMITIR)
    if not permitido:
        raise PermissionDenied(SIN_ALCANCE)


def puede_ingresar_igual(usuario, dispositivo):
    """¿Puede hacer «Ingresar igual» (el ingreso directo) en ``dispositivo``? Sin mirar camas.

    Exige alcance sobre **toda la institución**: el ingreso directo no cuelga de una derivación a un
    edificio. La regla que aplican el servicio, la pantalla de Llegadas y la API (``buscar``).
    """

    return dispositivo is not None and puede_operar_institucion(usuario, dispositivo, CAP_ADMITIR)


def puede_avisar_a_la_mesa(usuario, dispositivo):
    """¿Puede «Avisar a la mesa» desde ``dispositivo``? Alcanza con admitir en él, con cualquier alcance.

    Con alcance Edificios también (relevamiento del 22/11/2026, hallazgo 4): el aviso no reserva
    nada ni toca un edificio, solo le pasa a la mesa la familia que está en la puerta.
    """

    return dispositivo is not None and puede_operar_dispositivo(usuario, dispositivo, CAP_ADMITIR)


def _dispositivo_de(derivacion, usuario):
    """El dispositivo de la derivación, con su tipo, **si quien pregunta lo opera**.

    Se lee sin candado: ``dispositivo_id`` no cambia nunca. Es la guarda de «`admitir` en A no
    toca una derivación de B aunque conozca el id»: corre antes del primer candado.
    """

    dispositivo = Dispositivo.objects.select_related("tipo").filter(pk=derivacion.dispositivo_id).first()
    _exigir_alcance(usuario, dispositivo, derivacion)
    return dispositivo


def _bloquear_derivacion(pk, caso, dispositivo):
    """La derivación con ``FOR UPDATE``, recién leída. **Siempre después del caso**, sin JOIN.

    Le cuelga el caso bloqueado y el dispositivo ya leído: ``estadias`` los lee de ahí.
    """

    derivacion = Derivacion.objects.select_for_update().get(pk=pk)
    derivacion.caso = caso
    derivacion.dispositivo = dispositivo
    return derivacion


#: El 409 de quien manda la derivación que vio y ya no es la del caso (Cambio 477).
MENSAJE_OTRA_DERIVACION = (
    "El ingreso del caso {numero} cambió: la derivación que viste ya no es la vigente. Recargá la pantalla."
)


def ingreso_sin_candado(caso, usuario, *estados):
    """El ingreso del caso **sin candado**: la guarda de quien lo lee y el paso 1 de quien lo toca.

    Lee la **última** derivación del caso —con el caso y su grupo, y el dispositivo con su
    tipo— y exige alcance sobre su dispositivo (RU-9). Sin derivación, o de otro dispositivo,
    ``PermissionDenied``: el mismo error, para no decir si el caso existe. Un caso que la
    guardia rechazó y la mesa derivó a otro lado deja de ser suyo.

    Con ``estados``, exige además que la derivación siga ``ACEPTADA`` y el caso en uno de
    ellos; si no, :class:`EstadoCambio` con :func:`_por_que_ya_no`. Sin ``estados``, solo el
    alcance: quien escribe vuelve a preguntar el estado con el candado puesto
    (:func:`_abrir_ingreso`).

    Devuelve ``(caso, derivacion)`` sin bloquear. **1 consulta** más las del alcance.
    """

    pk = getattr(caso, "pk", caso)
    derivacion = (
        Derivacion.objects.filter(caso_id=pk).select_related("caso__grupo", "dispositivo__tipo").order_by("-id").first()
    )
    _exigir_alcance(usuario, derivacion.dispositivo if derivacion is not None else None, derivacion)
    caso = derivacion.caso
    if estados and (derivacion.estado != Derivacion.Estado.ACEPTADA or caso.estado not in estados):
        raise EstadoCambio(_por_que_ya_no(caso, derivacion), estado_actual=caso.estado, caso=caso)
    return caso, derivacion


def _abrir_ingreso(caso, usuario, *estados, derivacion_vista=None):
    """Alcance, candados y estado de toda acción sobre un ingreso ya aceptado.

    1. :func:`ingreso_sin_candado` sin estados: la última derivación del caso y el alcance
       sobre su dispositivo, o ``PermissionDenied``.
    2. Bloquea caso → derivación.
    3. Con ``derivacion_vista`` (el id de la derivación que la pantalla mostraba), exige que sea
       la bloqueada; si no, :class:`EstadoCambio` con :data:`MENSAJE_OTRA_DERIVACION` (Cambio 477).
       Va **antes** del estado: si es la misma, el reintento de una acción que ya llegó sigue
       dando el 409 de estado y la app infiere que se hizo; si no, la acción iría contra un
       ingreso que la pantalla no vio (la mesa volvió a derivar y otra guardia aceptó).
    4. Exige que la derivación siga ``ACEPTADA`` y el caso en uno de ``estados``; si no,
       :class:`EstadoCambio`. Quien llega acá opera el dispositivo al que el caso estuvo
       derivado, así que se le puede decir cómo quedó.

    Devuelve ``(caso, derivacion)`` bloqueados; ``derivacion.dispositivo`` trae su tipo.
    """

    _caso, previa = ingreso_sin_candado(caso, usuario)
    caso = _bloquear_caso(previa.caso_id)
    derivacion = _bloquear_derivacion(previa.pk, caso, previa.dispositivo)
    if derivacion_vista is not None and getattr(derivacion_vista, "pk", derivacion_vista) != derivacion.pk:
        raise EstadoCambio(MENSAJE_OTRA_DERIVACION.format(numero=caso.numero), estado_actual=caso.estado, caso=caso)
    if derivacion.estado != Derivacion.Estado.ACEPTADA or caso.estado not in estados:
        raise EstadoCambio(_por_que_ya_no(caso, derivacion), estado_actual=caso.estado, caso=caso)
    return caso, derivacion


def _por_que_ya_no(caso, derivacion):
    """Qué pasó con el ingreso y qué hacer (RU-20), para la pantalla que quedó vieja."""

    if caso.estado == Estado.ALOJADO:
        return f"La familia del caso {caso.numero} ya figura alojada. Recargá la pantalla."
    if caso.estado == Estado.CERRADO:
        return f"El caso {caso.numero} está cerrado. Recargá la pantalla."
    if caso.estado == Estado.INGRESO_EN_CURSO and derivacion.estado == Derivacion.Estado.ACEPTADA:
        return f"El ingreso del caso {caso.numero} ya está en curso. Recargá la pantalla."
    if derivacion.estado == Derivacion.Estado.VENCIDA:
        return mensaje_vencida(derivacion)
    if derivacion.estado == Derivacion.Estado.CANCELADA:
        return "La mesa canceló la derivación. Si la familia está en la puerta, avisale a la mesa."
    if derivacion.estado == Derivacion.Estado.RECHAZADA:
        return "La derivación ya fue rechazada o el ingreso se canceló. Buscá a la familia de nuevo."
    return f"El caso {caso.numero} ya no está para esto. Buscá a la familia de nuevo."


def derivacion_vencida(derivacion, ahora=None):
    """¿Pendiente con ``vence_en`` pasado y todavía sin marcar? Se acepta igual (RN-3.3).

    **La** regla de «vencida» que muestran la API (M2-1) y la pantalla E6. El cron la marca
    ``VENCIDA`` después; hasta entonces la familia en la puerta entra.
    """

    ahora = ahora or timezone.now()
    return derivacion.estado == Derivacion.Estado.PENDIENTE and derivacion.vence_en < ahora


def mensaje_vencida(derivacion):
    """Por qué una derivación vencida no se acepta y qué hacer (RN-3.3, RU-20).

    Es el mismo texto en la búsqueda por DNI y en la pantalla que quedó vieja.
    """

    return (
        f"La derivación venció a las {_hora(derivacion.vence_en)}. Pedile a la mesa que vuelva a derivar "
        "o ingresala igual si tenés plazas."
    )


def mensaje_faltan_confirmar(faltan):
    """«Falta confirmar a 2 personas…»: por qué todavía no se puede «Familia alojada»."""

    return f"Falta confirmar a {_personas(faltan)}. Confirmalas, o cerrá el ingreso con diferencia si no llegaron."


def acciones_del_ingreso(*, estado, confirmadas, total):
    """Qué se puede hacer con un ingreso: **la** regla de los cierres y de «Agregar persona».

    Como ``services.emergencia.acciones_posibles`` para la mesa: la pantalla pregunta acá qué
    botones ofrecer, y cada servicio vuelve a preguntar lo mismo con lo que lee sobre el caso
    bloqueado. ``total`` son las personas de la familia (``total_declarado``, que crece con
    «Agregar persona»); ``confirmadas``, las que ya tienen cama. Devuelve::

        {"alojar": bool, "diferencia": bool, "cancelar": bool, "agregar": bool}

    * ``alojar`` — «Familia alojada»: N de N, con al menos una;
    * ``diferencia`` — al menos una confirmada y falta alguien;
    * ``cancelar`` — nadie confirmado todavía;
    * ``agregar`` — el ingreso sigue en curso.

    Todas exigen el ingreso en curso.
    """

    en_curso = estado == Estado.INGRESO_EN_CURSO
    return {
        "alojar": en_curso and 0 < confirmadas and confirmadas >= total,
        "diferencia": en_curso and 0 < confirmadas < total,
        "cancelar": en_curso and confirmadas == 0,
        "agregar": en_curso,
    }


def _reservar_camas(*, derivacion, plazas, usuario, momento):
    """``reservar_plazas_de_derivacion``, con el choque de una cama tomada dicho para la guardia.

    Si una cama elegida se ocupó entre la foto y el candado **no se reintenta** (ver el orden
    de candados en ``emergencia_alojar``): ``ValidationError`` pidiendo volver a tocar el botón.
    """

    try:
        return reservar_plazas_de_derivacion(derivacion=derivacion, plazas=plazas, usuario=usuario, momento=momento)
    except ValidationError as error:
        if "plaza" in getattr(error, "error_dict", {}):
            raise ValidationError({"plazas": CAMAS_TOMADAS_MIENTRAS_ACEPTABA}) from error
        raise


def _resumen_de_reservas(reservadas, pedidas):
    """«5 de 7 camas reservadas · faltan 2», para la traza y la bitácora."""

    resumen = f"{reservadas} de {_camas(pedidas)} reservadas"
    faltantes = pedidas - reservadas
    return f"{resumen} · faltan {faltantes}" if faltantes else resumen


# ---------------------------------------------------------------------------
# La familia, las camas y la bitácora
# ---------------------------------------------------------------------------


def _filas_de(grupo):
    """Las filas de la familia por orden, con persona y cama. **1 consulta.**"""

    return list(
        IntegranteGrupo.objects.filter(grupo_id=grupo.pk)
        .select_related("ciudadano", "estadia__plaza__sector")
        .order_by("orden")
    )


def _asegurar_filas(grupo):
    """Deja una fila de ``IntegranteGrupo`` por cada persona declarada (1 a N). Devuelve todas.

    Solo crea las que faltan: una familia que vuelve de un ingreso cancelado ya tiene las suyas. Cuenta filas, no
    números: «Quitar persona» deja un hueco en la numeración y ese hueco no es una persona más.
    """

    existentes = set(IntegranteGrupo.objects.filter(grupo_id=grupo.pk).values_list("orden", flat=True))
    cuantas, faltan, orden = max(grupo.total_declarado - len(existentes), 0), [], 0
    while len(faltan) < cuantas:
        orden += 1
        if orden not in existentes:
            faltan.append(orden)
    if faltan:
        IntegranteGrupo.objects.bulk_create([IntegranteGrupo(grupo=grupo, orden=orden) for orden in faltan])
    return _filas_de(grupo)


def _confirmadas(filas):
    return sum(1 for fila in filas if fila.confirmada)


def _anotar_en_bitacora(dispositivo, usuario, texto, momento, edificio_id=None):
    """La novedad ``GENERAL`` automática del turno (RN-3.14). Sin turno no escribe: no es un error."""

    return anotar_novedad_automatica(
        dispositivo=dispositivo,
        tipo=EntradaBitacora.Tipo.GENERAL,
        texto=texto,
        momento=momento,
        usuario=usuario,
        edificio_id=edificio_id,
    )


def _devolver_a_la_mesa(caso):
    """El caso vuelve a quien lo tenía (``EN_GESTION``) o, si nadie lo tomó nunca, a la bandeja (``NUEVO``).

    Un ingreso directo no pasó por la mesa: no tiene ``tomado_por``, y un caso «en gestión»
    sin dueño no lo ve nadie.
    """

    caso.estado = Estado.EN_GESTION if caso.tomado_por_id else Estado.NUEVO
    caso.save(update_fields=["estado", "modificado"])
    return caso
