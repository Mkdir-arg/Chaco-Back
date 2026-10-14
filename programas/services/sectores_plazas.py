"""Datos de la pantalla «Sectores y plazas» de un dispositivo (MVP v2, etapas 1 y 5 · P5).

La vista no cuenta ni decide estados: delega acá, y acá tampoco se deciden. El estado de
cada plaza (disponible, ocupada, reservada, prestada, fuera de servicio) y su tono los
deriva `programas.services.ocupacion.estado_de_plazas`, **el mismo** que usa el mapa del
asistente de ingreso: la misma plaza no puede verse distinta en las dos pantallas.

Los contadores del encabezado y de cada sector salen de `ocupacion.ocupacion_de_plazas`
(el `Conteo` del servicio), no de una cuenta propia de la pantalla.

Lo que se puede hacer con cada plaza
------------------------------------

P5 es donde se resuelven dos de las alertas de P4 —«préstamo o reserva vencida» y «plazas
fuera de servicio»—, así que cada plaza llega con **una** acción, la que su situación
admite, y el mapa la ofrece como enlace (`plaza.url`) al modal de la pantalla:

=====================================  ===================  ==========================
Situación de la plaza                  Acción               Capacidad
=====================================  ===================  ==========================
Fuera de servicio                      volver a servicio    ``dispositivo.editar``
Con una reserva o préstamo sin liberar liberar              ``dispositivo.admitir``
Ocupada                                sacar de servicio,   ``dispositivo.editar``
                                       **bloqueada**
Disponible                             sacar de servicio    ``dispositivo.editar``
=====================================  ===================  ==========================

«Con una reserva sin liberar» no es «reservada en el mapa»: la reserva vencida que nadie
liberó deja la plaza **Disponible** y sigue abierta (`estadias.reservas_abiertas`). Es
exactamente la que enciende la alerta de P4, y si la acción se decidiera por el estado del
mapa, esa alerta no se podría resolver desde acá. El estado dibujado sigue saliendo de
`estado_de_plazas` y de ningún otro lado; lo que se suma es un segundo hecho, no un
segundo estado.

La plaza ocupada **no esconde** la acción: la ofrece deshabilitada con su motivo, porque
`sacar_plaza_de_servicio` la rechaza y el operador tiene que saber por qué y qué hacer
(reubicar). Las capacidades las resuelve la vista y llegan acá como dos booleanos: el
servicio recibe hechos, no usuarios.

Costo
-----

**Consultas fijas, no una por sector** (lo que arrastraba el Cambio 272): las plazas de
todos los sectores salen en una sola consulta y el tope por sector se aplica en Python,
`estado_de_plazas` se llama **una vez** con todas las plazas dibujadas, y las reservas sin
resolver son otra consulta sola —y solo si quien mira las puede liberar—. Antes eran tres
por sector, así que un dispositivo con ocho pabellones costaba veinticuatro consultas
nada más que para dibujarse.
"""

from django.utils import timezone

from programas.models import Plaza, Sector
from programas.services.estadias import reserva_abierta_de, reservas_abiertas
from programas.services.ocupacion import (
    ESTADO_FUERA_SERVICIO,
    ESTADO_OCUPADA,
    LEYENDA_PLAZAS,
    estado_de_plazas,
    ocupacion_de_plazas,
)

# Tope por sector: el componente dibuja hasta 200 y avisa «Mostrando 200 de N»; la vista
# acota cada sector para no mandar un dispositivo entero en una sola grilla.
TOPE_PLAZAS_POR_SECTOR = 200

#: Las tres acciones de P5. Cada una tiene su servicio en `programas.services.estadias`.
ACCION_LIBERAR = "liberar"
ACCION_FUERA_SERVICIO = "fuera_servicio"
ACCION_VOLVER = "volver"

#: Por qué una plaza ocupada no se saca de servicio. Lo mismo que rechaza
#: `estadias.sacar_plaza_de_servicio`, dicho antes de intentarlo.
MOTIVO_PLAZA_OCUPADA = "Tiene una estadía activa: reubicá a la persona antes de sacarla de servicio."


def accion_de_plaza(estado, con_reserva_abierta):
    """La acción que admite una plaza, por su estado del mapa y su reserva sin resolver.

    Fuera de servicio gana: es la misma precedencia que dibuja `estado_de_plazas`, y una
    plaza fuera de servicio con una reserva abierta —que el servicio de estadías no deja
    escribir— se repone antes de nada.
    """

    if estado.estado == ESTADO_FUERA_SERVICIO:
        return ACCION_VOLVER
    if con_reserva_abierta:
        return ACCION_LIBERAR
    return ACCION_FUERA_SERVICIO


def bloqueo_de_plaza(estado, accion):
    """El motivo por el que la acción no va a proceder, o cadena vacía."""

    if accion == ACCION_FUERA_SERVICIO and estado.estado == ESTADO_OCUPADA:
        return MOTIVO_PLAZA_OCUPADA
    return ""


def _habilitada(accion, *, puede_liberar, puede_configurar_plazas):
    return puede_liberar if accion == ACCION_LIBERAR else puede_configurar_plazas


def plaza_para_accion(dispositivo, plaza_pk, *, puede_liberar=False, puede_configurar_plazas=False):
    """La plaza que pide `?plaza=<id>`, con su acción resuelta, o ``None``.

    ``None`` para la plaza inexistente, la de otra institución, la de un sector dado de
    baja —ninguna de las tres se dibuja en el mapa— y la que el usuario no puede
    gestionar: **el mismo resultado para las cuatro**, porque un mensaje distinto para la
    ajena sería un oráculo para enumerar los ids de las plazas de otras instituciones.

    El estado y la acción se vuelven a derivar acá con las mismas funciones que el mapa:
    el id viaja por la URL y entre el dibujo y el clic la plaza pudo cambiar de manos.
    """

    plaza = (
        Plaza.objects.filter(pk=plaza_pk, sector__dispositivo=dispositivo, sector__activo=True)
        .select_related("sector")
        .first()
    )
    if plaza is None:
        return None
    estado = estado_de_plazas([plaza])[plaza.pk]
    reserva = reserva_abierta_de(plaza)
    accion = accion_de_plaza(estado, reserva is not None)
    if not _habilitada(accion, puede_liberar=puede_liberar, puede_configurar_plazas=puede_configurar_plazas):
        return None
    return {
        "plaza": plaza,
        "estado": estado,
        "accion": accion,
        "bloqueo": bloqueo_de_plaza(estado, accion),
        "reserva": reserva,
    }


def _resumen(conteo):
    """Las cifras de un `Conteo` del servicio de ocupación, con las claves que lee la pantalla.

    `reservadas` es la cifra del servicio: reservas **y** préstamos vigentes.
    """

    return {
        "total": conteo.totales,
        "operativas": conteo.operativas,
        "fuera_servicio": conteo.fuera_de_servicio,
        "ocupadas": conteo.ocupadas,
        "reservadas": conteo.reservadas,
        "disponibles": conteo.disponibles,
    }


def _plaza_para_el_mapa(plaza, estado, url):
    """Un dict del mapa: estado y tono vienen del servicio, nunca del template ni de acá."""

    return {
        "codigo": plaza.codigo,
        "estado": estado.estado,
        "tono": estado.tono,
        "detalle": estado.detalle,
        "url": url,
    }


def _plazas_por_sector(sector_ids):
    """`{sector_id: [plazas]}` acotado al tope, en **una** consulta para todos los sectores.

    El recorte por sector va en Python y no en el SQL: un `LIMIT` por sector es una
    consulta por sector, que es el N+1 que esta pantalla arrastraba. Lo que se trae son
    las plazas cargadas del dispositivo, acotadas por la capacidad instalada real.
    """

    por_sector = {pk: [] for pk in sector_ids}
    plazas = (
        Plaza.objects.filter(sector_id__in=sector_ids)
        .only("id", "sector_id", "codigo", "estado", "motivo_fuera_servicio")
        .order_by("sector_id", "codigo")
    )
    for plaza in plazas:
        fila = por_sector[plaza.sector_id]
        if len(fila) < TOPE_PLAZAS_POR_SECTOR:
            fila.append(plaza)
    return por_sector


def _reservas_abiertas_por_plaza(plazas):
    """`{plaza_id: reserva_id}` de las reservas sin resolver. Una consulta.

    Se pregunta **siempre**, también para quien no puede liberar: la reserva no decide
    quién ve qué, decide qué acción admite la plaza. Si se saltara, una plaza reservada le
    ofrecería «sacar de servicio» a quien tiene `dispositivo.editar`, que es una acción
    que el servicio rechaza porque la plaza está tomada.

    El orden descendente hace que, si una plaza tuviera dos —que el bloqueo de la plaza
    impide—, quede la más vieja, la misma que `estadias.reserva_abierta_de` va a liberar.
    """

    if not plazas:
        return {}
    filas = reservas_abiertas([plaza.pk for plaza in plazas]).order_by("-id").values_list("plaza_id", "id")
    return dict(filas)


def sectores_con_plazas(dispositivo, *, puede_liberar=False, puede_configurar_plazas=False):
    """Todo lo que la pantalla dibuja: sectores activos con su mapa acotado y los totales.

    Las cifras del encabezado y de cada sector salen de `ocupacion.ocupacion_de_plazas` y
    los estados de las celdas de `ocupacion.estado_de_plazas`: las dos son el mismo
    servicio, así que el encabezado y el mapa no pueden decir cosas distintas.

    `puede_liberar` (`dispositivo.admitir`) y `puede_configurar_plazas`
    (`dispositivo.editar`) los resuelve la vista con alcance al dispositivo. Una plaza
    cuya acción el usuario no puede ejercer llega **sin** `url`: el mapa la dibuja
    informativa, que es lo que su contrato ya hacía.
    """

    # Un solo instante para las dos: la vigencia de una reserva es por tiempo, y con dos
    # `now()` distintos el encabezado y una celda podrían discrepar justo en su borde.
    momento = timezone.now()
    ocupacion = ocupacion_de_plazas(dispositivo, momento).de(dispositivo)
    sectores = {sector.pk: sector for sector in Sector.objects.filter(dispositivo=dispositivo, activo=True)}
    por_sector = _plazas_por_sector(list(sectores))

    dibujadas = [plaza for item in ocupacion.sectores for plaza in por_sector.get(item.sector_id, ())]
    # Una sola vez para todo el dispositivo, no una por sector: son dos consultas fijas.
    estados = estado_de_plazas(dibujadas, momento)
    reservas = _reservas_abiertas_por_plaza(dibujadas)

    armados = []
    for item in ocupacion.sectores:
        sector = sectores[item.sector_id]
        plazas = por_sector.get(item.sector_id, [])
        celdas = []
        for plaza in plazas:
            estado = estados[plaza.pk]
            accion = accion_de_plaza(estado, plaza.pk in reservas)
            habilitada = _habilitada(
                accion, puede_liberar=puede_liberar, puede_configurar_plazas=puede_configurar_plazas
            )
            celdas.append(_plaza_para_el_mapa(plaza, estado, f"?plaza={plaza.pk}" if habilitada else ""))
        armados.append(
            {
                "sector": sector,
                "resumen": _resumen(item.conteo),
                "difiere_de_lo_declarado": sector.capacidad != item.conteo.totales,
                "plazas": celdas,
            }
        )
    return {
        "sectores": armados,
        "totales": _resumen(ocupacion.conteo),
        "leyenda": LEYENDA_PLAZAS,
    }
