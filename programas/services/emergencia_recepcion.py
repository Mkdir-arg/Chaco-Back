"""Etapa 3 de Emergencia, paso 1: la guardia busca a la familia por DNI y acepta o rechaza la derivación.

``buscar_por_dni`` (M2-1), ``aceptar_derivacion`` y ``rechazar_derivacion`` (M2-2). Se
importan desde ``programas.services.emergencia_alojar``, que tiene el contrato de la etapa
(alcance, orden de candados, traza y bitácora).
"""

from dataclasses import dataclass, field
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from core.dni import MENSAJE_DNI_INVALIDO, dni_valido, normalizar_dni
from programas.models import (
    CasoEmergencia,
    Derivacion,
)
from programas.selectors.emergencia_alojar import camas_libres
from programas.services.emergencia import EstadoCambio
from programas.services.emergencia_comun import _bloquear_caso, _hora, _nombre_de, _trazar
from programas.services.emergencia_ingreso_comun import (
    Accion,
    Estado,
    _anotar_en_bitacora,
    _asegurar_filas,
    _bloquear_derivacion,
    _camas,
    _devolver_a_la_mesa,
    _dia_y_mes,
    _dispositivo_de,
    _exigir_alcance,
    _por_que_ya_no,
    _reservar_camas,
    _resumen_de_reservas,
    mensaje_vencida,
)
from programas.services.estadias import verificar_alojamiento_en_red
from programas.services.ingreso import buscar_ciudadano_por_dni

# ---------------------------------------------------------------------------
# Resultados de la búsqueda por DNI (03 §7, `…/buscar/?dni=`)
# ---------------------------------------------------------------------------

BUSQUEDA_DERIVACION = "DERIVACION"

BUSQUEDA_SIN_DERIVACION = "SIN_DERIVACION"

BUSQUEDA_ALOJADA = "ALOJADA"

SIN_DERIVACION = "No hay una derivación para este DNI en tu dispositivo."


class MotivoRechazo(models.TextChoices):
    """Por qué el dispositivo rechaza una derivación (M2-2, RN-3.13)."""

    SIN_PLAZAS = "SIN_PLAZAS", "Sin plazas"
    NO_CUMPLE_PERFIL = "NO_CUMPLE_PERFIL", "No cumple perfil"
    NO_LLEGO = "NO_LLEGO", "No llegó"
    OTRO = "OTRO", "Otro"


SIN_PLAZAS_PARA_ACEPTAR = "Sin plazas · rechazá con motivo o liberá camas."


@dataclass(frozen=True)
class ResultadoBusqueda:
    """Lo que contesta :func:`buscar_por_dni` (03 §7).

    * ``resultado`` — ``DERIVACION``, ``SIN_DERIVACION`` o ``ALOJADA``.
    * ``plazas_libres`` — camas libres del dispositivo **ahora** (decide si se ofrece
      «Ingresar igual»).
    * ``derivacion`` / ``caso`` — solo con ``DERIVACION``: la derivación vigente hacia **este**
      dispositivo, con ``caso.grupo.responsable`` y ``derivada_por`` cargados.
    * ``alojada_aca`` — solo con ``ALOJADA``: si la estadía abierta es en este dispositivo.
    * ``alojada_en`` / ``alojada_desde`` — el nombre del dispositivo y desde cuándo, **solo si
      quien busca lo puede ver**; si no, vacío y ``None`` (RN-3.2, RU-9).
    * ``mensaje`` — el texto para la pantalla (RU-20). Nunca nombra un dispositivo que quien
      busca no opera.
    * ``dni`` — el DNI buscado, normalizado.
    """

    resultado: str
    dni: str
    plazas_libres: int = 0
    derivacion: Derivacion | None = None
    caso: CasoEmergencia | None = None
    alojada_aca: bool | None = None
    alojada_en: str = ""
    alojada_desde: datetime | None = None
    mensaje: str = ""


@dataclass(frozen=True)
class ResultadoAceptacion:
    """Lo que contesta :func:`aceptar_derivacion` (03 §7: ``{caso, reservadas, faltantes, integrantes}``).

    ``reservadas`` + ``faltantes`` = ``derivacion.plazas_pedidas``. ``reservas`` son las
    ``ReservaPlaza`` recién creadas, por pk de plaza; ``integrantes``, las filas de la familia
    por orden (N = ``total_declarado``). ``mensaje`` es «Reservé 5 de 7 · faltan 2 camas».
    """

    caso: CasoEmergencia
    derivacion: Derivacion
    reservadas: int
    faltantes: int
    reservas: list = field(default_factory=list)
    integrantes: list = field(default_factory=list)
    mensaje: str = ""


# ---------------------------------------------------------------------------
# Buscar (M2-1)
# ---------------------------------------------------------------------------


def buscar_por_dni(*, dispositivo, dni, usuario):
    """Busca a la familia por el DNI de cualquiera de sus personas (HU-3.1, RN-3.1, RN-3.2).

    Tres resultados (:class:`ResultadoBusqueda`):

    * ``DERIVACION`` — hay una derivación ``PENDIENTE`` o ``ACEPTADA`` **hacia este
      dispositivo** de un caso derivado o con ingreso en curso, cuyo responsable —o un
      integrante ya confirmado— tiene ese DNI. Gana sobre «alojada»: buscar de nuevo al
      responsable ya confirmado tiene que llevar a seguir con su familia.
    * ``ALOJADA`` — la persona tiene una estadía abierta en la red y no hay un ingreso que
      seguir. Dónde, solo si quien busca lo puede ver.
    * ``SIN_DERIVACION`` — todo lo demás, **incluida una derivación a otro dispositivo**: no
      se dice cuál ni que existe (RU-9, RU §6 n.° 2).

    Solo lectura, sin candados. Exige ``dispositivo.admitir`` sobre ``dispositivo``
    (``PermissionDenied``); un DNI que no es un DNI es ``ValidationError``.
    """

    _exigir_alcance(usuario, dispositivo)
    dni = normalizar_dni(dni)
    if not dni_valido(dni):
        raise ValidationError({"dni": MENSAJE_DNI_INVALIDO})

    libres = len(camas_libres(dispositivo))
    ciudadano = buscar_ciudadano_por_dni(dni)
    if ciudadano is None:
        return ResultadoBusqueda(BUSQUEDA_SIN_DERIVACION, dni, plazas_libres=libres, mensaje=SIN_DERIVACION)

    de_la_persona = Q(caso__grupo__responsable=ciudadano) | Q(caso__grupo__integrantes__ciudadano=ciudadano)
    derivacion = (
        Derivacion.objects.filter(
            de_la_persona,
            # La guarda de RU-9: solo lo derivado a **este** dispositivo. Es la única línea
            # que separa a la guardia de A de la familia que va a B.
            dispositivo=dispositivo,
            estado__in=Derivacion.ESTADOS_VIGENTES,
            caso__estado__in=(Estado.DERIVADO, Estado.INGRESO_EN_CURSO),
        )
        .select_related("caso__grupo__responsable", "caso__localidad", "derivada_por", "respondida_por")
        .distinct()
        .order_by("-id")
        .first()
    )
    if derivacion is not None:
        return ResultadoBusqueda(
            BUSQUEDA_DERIVACION, dni, plazas_libres=libres, derivacion=derivacion, caso=derivacion.caso
        )

    verificacion = verificar_alojamiento_en_red(ciudadano, usuario)
    if verificacion.alojada:
        aca = verificacion.dispositivo_id == dispositivo.pk
        if verificacion.dentro_del_alcance:
            mensaje = f"Alojada en {verificacion.dispositivo} desde el {_dia_y_mes(verificacion.desde)}."
        else:
            mensaje = "Alojada en otro dispositivo de la red."
        return ResultadoBusqueda(
            BUSQUEDA_ALOJADA,
            dni,
            plazas_libres=libres,
            alojada_aca=aca,
            alojada_en=verificacion.dispositivo if verificacion.dentro_del_alcance else "",
            alojada_desde=verificacion.desde if verificacion.dentro_del_alcance else None,
            mensaje=mensaje,
        )

    # RN-3.3: una derivación a este dispositivo que ya venció no se acepta, pero se cuenta por qué.
    vencida = (
        Derivacion.objects.filter(
            de_la_persona,
            dispositivo=dispositivo,
            estado=Derivacion.Estado.VENCIDA,
            caso__estado__in=(Estado.NUEVO, Estado.EN_GESTION),
        )
        .distinct()
        .order_by("-id")
        .first()
    )
    mensaje = mensaje_vencida(vencida) if vencida is not None else SIN_DERIVACION
    return ResultadoBusqueda(BUSQUEDA_SIN_DERIVACION, dni, plazas_libres=libres, mensaje=mensaje)


# ---------------------------------------------------------------------------
# Aceptar y rechazar (M2-2)
# ---------------------------------------------------------------------------


def _exigir_pendiente(caso, derivacion):
    if derivacion.estado == Derivacion.Estado.PENDIENTE and caso.estado == Estado.DERIVADO:
        return
    if derivacion.estado == Derivacion.Estado.ACEPTADA:
        quien = _nombre_de(derivacion.respondida_por) if derivacion.respondida_por_id else "otra persona de la guardia"
        cuando = f" a las {_hora(derivacion.respondida_en)}" if derivacion.respondida_en else ""
        mensaje = f"La derivación ya la aceptó {quien}{cuando}. Recargá la pantalla para seguir con el ingreso."
    else:
        mensaje = _por_que_ya_no(caso, derivacion)
    raise EstadoCambio(mensaje, estado_actual=caso.estado, caso=caso)


@transaction.atomic
def aceptar_derivacion(*, derivacion, usuario):
    """Acepta una derivación ``PENDIENTE``: reserva las camas y abre el ingreso (HU-3.2, RN-3.3, RN-3.4).

    * Vale aunque ``vence_en`` ya haya pasado, **mientras el cron no la haya marcado
      ``VENCIDA``** (RN-3.3): la familia está en la puerta. Quien tome primero el candado
      del caso —esta función o ``vencer_derivacion``— gana, y el otro ve el estado nuevo.
    * Elige sola las camas (``selectors.emergencia_alojar.camas_libres``: el sector con más
      libres primero, por código) y reserva **hasta** ``plazas_pedidas`` con
      ``reservas_derivacion.reservar_plazas_de_derivacion``, todo o nada. Menos camas que las pedidas es
      válido y se avisa («Reservé 5 de 7 · faltan 2 camas»); con **0 libres** no se acepta
      (``ValidationError``): se rechaza con motivo o se liberan camas.
    * El caso pasa a ``INGRESO_EN_CURSO`` con ``aceptado_en``; se crean las N filas de
      ``IntegranteGrupo`` (N = ``total_declarado``) que falten; queda la traza y la novedad
      ``GENERAL`` de la bitácora.

    Si una cama elegida se ocupó entre la foto y el candado, **no reintenta** (ver el orden
    de candados del módulo): ``ValidationError`` pidiendo volver a aceptar, y no queda nada.

    Levanta ``PermissionDenied`` sin ``dispositivo.admitir`` sobre el dispositivo de la
    derivación —antes de tomar ningún candado— y :class:`EstadoCambio` si ya no está
    pendiente (otra guardia la aceptó, venció, la mesa la canceló).

    Devuelve :class:`ResultadoAceptacion`.
    """

    dispositivo = _dispositivo_de(derivacion, usuario)
    caso = _bloquear_caso(derivacion.caso_id)
    derivacion = _bloquear_derivacion(derivacion.pk, caso, dispositivo)
    _exigir_pendiente(caso, derivacion)

    libres = camas_libres(dispositivo)
    if not libres:
        raise ValidationError({"plazas": SIN_PLAZAS_PARA_ACEPTAR})

    ahora = timezone.now()
    derivacion.estado = Derivacion.Estado.ACEPTADA
    derivacion.respondida_por = usuario
    derivacion.respondida_en = ahora
    derivacion.save(update_fields=["estado", "respondida_por", "respondida_en", "modificado"])
    reservas = _reservar_camas(
        derivacion=derivacion, plazas=libres[: derivacion.plazas_pedidas], usuario=usuario, momento=ahora
    )

    caso.estado = Estado.INGRESO_EN_CURSO
    caso.marcar("aceptado_en", ahora)
    caso.save(update_fields=["estado", "aceptado_en", "modificado"])
    integrantes = _asegurar_filas(caso.grupo)

    reservadas, pedidas = len(reservas), derivacion.plazas_pedidas
    faltantes = pedidas - reservadas
    resumen = _resumen_de_reservas(reservadas, pedidas)
    _trazar(
        caso,
        usuario,
        Accion.DERIVACION_ACEPTADA,
        estado_anterior=Estado.DERIVADO,
        detalle=f"Derivación aceptada por {dispositivo.nombre} · {resumen}",
    )
    _anotar_en_bitacora(
        dispositivo, usuario, f"Emergencia · derivación aceptada · caso N.° {caso.numero} · {resumen}", ahora
    )
    mensaje = f"Reservé {reservadas} de {pedidas}"
    mensaje = f"{mensaje} · faltan {_camas(faltantes)}" if faltantes else f"{mensaje} camas"
    return ResultadoAceptacion(
        caso=caso,
        derivacion=derivacion,
        reservadas=reservadas,
        faltantes=faltantes,
        reservas=reservas,
        integrantes=integrantes,
        mensaje=mensaje,
    )


@transaction.atomic
def rechazar_derivacion(*, derivacion, usuario, motivo, observacion=""):
    """Rechaza una derivación ``PENDIENTE`` con motivo (RN-3.13, RU-22).

    ``motivo`` es un código de :class:`MotivoRechazo`; con «Otro», ``observacion`` es
    obligatoria. La derivación queda ``RECHAZADA`` —suelta la vigencia: el caso se puede
    volver a derivar— y el caso vuelve a ``EN_GESTION`` **con el mismo operador**. La traza
    dice «Rechazado por X: sin plazas», que es lo que la mesa lee.

    ``PermissionDenied`` sin alcance sobre el dispositivo de la derivación;
    :class:`EstadoCambio` si ya no está pendiente. Devuelve la ``Derivacion``, con
    ``derivacion.caso`` como quedó.
    """

    observacion = (observacion or "").strip()
    if motivo not in MotivoRechazo.values:
        raise ValidationError({"motivo": "Elegí el motivo del rechazo."})
    if motivo == MotivoRechazo.OTRO and not observacion:
        raise ValidationError({"observacion": "Con el motivo «Otro», contá qué pasó."})

    dispositivo = _dispositivo_de(derivacion, usuario)
    caso = _bloquear_caso(derivacion.caso_id)
    derivacion = _bloquear_derivacion(derivacion.pk, caso, dispositivo)
    _exigir_pendiente(caso, derivacion)

    rotulo = MotivoRechazo(motivo).label
    derivacion.estado = Derivacion.Estado.RECHAZADA
    derivacion.motivo = rotulo
    derivacion.observacion = observacion
    derivacion.respondida_por = usuario
    derivacion.respondida_en = timezone.now()
    derivacion.save(update_fields=["estado", "motivo", "observacion", "respondida_por", "respondida_en", "modificado"])
    _devolver_a_la_mesa(caso)
    _trazar(
        caso,
        usuario,
        Accion.DERIVACION_RECHAZADA,
        estado_anterior=Estado.DERIVADO,
        detalle=f"Rechazado por {dispositivo.nombre}: {rotulo.lower()}" + (f" · {observacion}" if observacion else ""),
    )
    return derivacion
