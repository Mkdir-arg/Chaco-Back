"""Etapa 3 de Emergencia sin derivación: ingreso directo y aviso a la mesa (M2-6, RN-3.10).

«Ingresar igual» (``ingreso_directo``) —la decisión 4 del PM: va aparte para que se pueda
sacar sin tocar el resto— y «Avisar a la mesa» (``avisar_a_la_mesa``). Se importan desde
``programas.services.emergencia_alojar``.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.archivos import archivos_atomicos
from core.models import Localidad
from programas.models import (
    CasoEmergencia,
    Derivacion,
    ReservaPlaza,
)
from programas.selectors.emergencia import dispositivo_elegible
from programas.selectors.emergencia_alojar import camas_libres
from programas.services.emergencia import DISPOSITIVO_NO_ELEGIBLE, _caso_de_ese_envio, _como_uuid, crear_caso
from programas.services.emergencia_comun import _bloquear_caso, _trazar
from programas.services.emergencia_ingreso_comun import (
    Accion,
    Estado,
    Origen,
    _anotar_en_bitacora,
    _asegurar_filas,
    _exigir_alcance,
    _reservar_camas,
    _resumen_de_reservas,
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


def _con_sus_reservas(caso):
    """Le cuelga ``reservadas`` y ``faltantes`` a un caso que ya existía (el reenvío de un ingreso directo).

    Son las camas que el ingreso reservó **al crearse** —vigentes, consumidas o liberadas
    después— contra las que pidió: lo mismo que contestó el primer envío.
    """

    derivacion = Derivacion.objects.filter(caso_id=caso.pk).order_by("id").first()
    pedidas = derivacion.plazas_pedidas if derivacion is not None else 0
    reservadas = ReservaPlaza.objects.filter(derivacion=derivacion).count() if derivacion is not None else 0
    caso.reservadas, caso.faltantes = reservadas, max(pedidas - reservadas, 0)
    return caso


@archivos_atomicos
@transaction.atomic
def ingreso_directo(*, dispositivo, usuario, datos_formulario1, uuid_cliente=None):
    """«Ingresar igual»: la familia llegó sola y el dispositivo la recibe sin pasar por la mesa (HU-3.6, RN-3.10).

    Exige ``dispositivo.admitir`` sobre **ese** dispositivo, que sea elegible para alojar
    familias y que tenga **al menos una cama libre**. En una transacción:

    * crea el caso con ``crear_caso(origen=DISPOSITIVO)`` —misma validación del Formulario 1,
      con dirección y localidad opcionales—;
    * crea una ``Derivacion`` ``ACEPTADA`` hacia el propio dispositivo, para que todo lo que
      sigue (confirmar, alojar, diferencia, egreso) sea el mismo camino;
    * reserva camas para la familia **hasta donde alcance** y crea sus N filas;
    * deja el caso en ``INGRESO_EN_CURSO`` con ``tomado_en = derivado_en = aceptado_en =
      creado``: el tramo de la mesa vale 0 y el tablero lo separa como ingreso directo.

    **Idempotente** por ``uuid_cliente`` (RU-16; es lo único de la etapa que la app encola
    sin conexión): reenviarlo devuelve el mismo caso, con ``caso.ya_existia = True``, sin
    reservar de nuevo ni mirar si hoy hay camas.

    Devuelve el ``CasoEmergencia`` con ``ya_existia``, ``reservadas`` y ``faltantes``.
    """

    _exigir_alcance(usuario, dispositivo)
    uuid_cliente = _como_uuid(uuid_cliente)
    if uuid_cliente is not None:
        existente = _caso_de_ese_envio(uuid_cliente, usuario)
        if existente is not None:
            return _con_sus_reservas(existente)
    if not dispositivo_elegible(dispositivo):
        raise ValidationError({"dispositivo": DISPOSITIVO_NO_ELEGIBLE})
    libres = camas_libres(dispositivo)
    if not libres:
        raise ValidationError({"plazas": SIN_CAMAS_PARA_INGRESO_DIRECTO})

    caso = crear_caso(
        usuario=usuario,
        origen=Origen.DISPOSITIVO,
        datos_formulario1=_formulario1_en_el_dispositivo(datos_formulario1, dispositivo),
        uuid_cliente=uuid_cliente,
    )
    if caso.ya_existia:  # el mismo envío llegó dos veces a la vez: lo creó el otro
        return _con_sus_reservas(caso)
    caso = _bloquear_caso(caso)
    grupo = caso.grupo
    momento = caso.creado
    derivacion = Derivacion(
        caso=caso,
        dispositivo=dispositivo,
        estado=Derivacion.Estado.ACEPTADA,
        plazas_pedidas=grupo.total_declarado,
        vence_en=momento,
        derivada_por=usuario,
        respondida_por=usuario,
        respondida_en=momento,
    )
    derivacion.save()
    reservas = _reservar_camas(
        derivacion=derivacion, plazas=libres[: grupo.total_declarado], usuario=usuario, momento=momento
    )

    caso.estado = Estado.INGRESO_EN_CURSO
    for marca in ("tomado_en", "derivado_en", "aceptado_en"):
        caso.marcar(marca, momento)
    caso.save(update_fields=["estado", "tomado_en", "derivado_en", "aceptado_en", "modificado"])
    _asegurar_filas(grupo)

    reservadas = len(reservas)
    faltantes = grupo.total_declarado - reservadas
    resumen = _resumen_de_reservas(reservadas, grupo.total_declarado)
    _trazar(
        caso,
        usuario,
        Accion.INGRESO_DIRECTO,
        estado_anterior=Estado.NUEVO,
        detalle=f"Ingreso directo en {dispositivo.nombre}, sin pasar por la mesa · {resumen}",
    )
    _anotar_en_bitacora(
        dispositivo, usuario, f"Emergencia · ingreso directo · caso N.° {caso.numero} · {resumen}", timezone.now()
    )
    caso.ya_existia = False
    caso.reservadas, caso.faltantes = reservadas, faltantes
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
    Exige ``dispositivo.admitir`` sobre ese dispositivo. Idempotente por ``uuid_cliente``.

    Devuelve el ``CasoEmergencia`` con ``ya_existia``.
    """

    _exigir_alcance(usuario, dispositivo)
    caso = crear_caso(
        usuario=usuario,
        origen=Origen.DISPOSITIVO,
        datos_formulario1=_formulario1_en_el_dispositivo(datos_formulario1, dispositivo),
        uuid_cliente=uuid_cliente,
    )
    if caso.ya_existia:
        return caso
    caso = _bloquear_caso(caso)
    caso.situacion = {
        **caso.situacion,
        CasoEmergencia.SITUACION_EN_LA_PUERTA: {"dispositivo_id": dispositivo.pk, "dispositivo": dispositivo.nombre},
    }
    caso.save(update_fields=["situacion", "modificado"])
    _trazar(
        caso,
        usuario,
        Accion.AVISO_A_LA_MESA,
        estado_anterior=caso.estado,
        detalle=f"En la puerta de {dispositivo.nombre} · esperando derivación",
    )
    caso.ya_existia = False
    return caso


def es_ingreso_directo(caso):
    """¿El caso nació de «Ingresar igual»? Es ``CasoEmergencia.es_ingreso_directo``: la regla vive en el modelo."""

    return caso.es_ingreso_directo
