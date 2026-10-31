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
fuera de servicio»—, así que cada plaza llega con las acciones que su situación admite
(`acciones`; casi siempre una) y el mapa la ofrece al modal de la pantalla: como botón sin
recarga (`plaza.click`) o, con `plaza.url` (`?plaza=<id>`), como enlace directo:

=====================================  ===================  ==========================
Situación de la plaza                  Acción               Capacidad
=====================================  ===================  ==========================
Fuera de servicio                      volver a servicio    ``dispositivo.editar``
Con una reserva o préstamo sin liberar liberar              ``dispositivo.admitir``
Ocupada                                reubicar a la        ``dispositivo.admitir``
                                       persona
Ocupada, sin ``dispositivo.admitir``   sacar de servicio,   ``dispositivo.editar``
                                       **bloqueada**
Disponible                             reservar, prestar    ``dispositivo.admitir``
                                       y sacar de servicio  ``dispositivo.editar``
=====================================  ===================  ==========================

De la plaza disponible se ofrece cada opción a quien puede ejercerla: reservar y prestar
(revierten lo que dejaron fuera los Cambios 287, 291 y 325) piden `admitir`, y sacar de
servicio pide `editar`. Reservar y prestar buscan a la persona por DNI en el padrón, así que
piden además `ciudadano.ver`, como el asistente de ingreso. La plaza ocupada se reubica con el
formulario del cambio de plaza, que necesita la estadía y el mapa de plazas libres: cargarlos
por plaza pasaría el presupuesto del mapa, así que ese modal se pide **al tocar la celda**
(`?plaza=<id>&fragmento=reubicar`) y la celda lleva `abrirReubicar(<id>)`.

«Con una reserva sin liberar» no es «reservada en el mapa»: la reserva vencida que nadie
liberó deja la plaza **Disponible** y sigue abierta (`ReservaPlaza.objects.abiertas()`). Es
exactamente la que enciende la alerta de P4, y si la acción se decidiera por el estado del
mapa, esa alerta no se podría resolver desde acá. El estado dibujado sigue saliendo de
`estado_de_plazas` y de ningún otro lado; lo que se suma es un segundo hecho, no un
segundo estado.

La plaza ocupada ofrece **reubicar** a quien puede admitir (Cambio 377, que revierte en
parte el 287): el modal mueve a la persona a otra plaza libre con `estadias.cambiar_plaza`.
A quien solo puede editar le sigue ofreciendo «sacar de servicio» deshabilitada con su
motivo, porque `sacar_plaza_de_servicio` la rechaza y tiene que saber por qué. Las capacidades las resuelve la vista y llegan acá como dos
booleanos: el servicio recibe hechos, no usuarios.

Costo
-----

**Consultas fijas, no una por sector** (lo que arrastraba el Cambio 272): las plazas de
todos los sectores salen en una sola consulta y el tope por sector se aplica en Python,
`estado_de_plazas` se llama **una vez** con todas las plazas dibujadas, y las reservas sin
resolver son otra consulta sola, la misma para cualquiera que mire. Antes eran tres
por sector, así que un dispositivo con ocho pabellones costaba veinticuatro consultas
nada más que para dibujarse.
"""

from django.utils import timezone

from programas.models import Plaza, ReservaPlaza, Sector
from programas.services.estadias import reserva_abierta_de
from programas.services.ocupacion import (
    ESTADO_FUERA_SERVICIO,
    ESTADO_OCUPADA,
    LEYENDA_PLAZAS,
    estado_de_plazas,
    ocupacion_de_plazas,
    tension_de_ocupacion,
)

# Tope por sector: el componente dibuja hasta 200 y avisa «Mostrando 200 de N»; la vista
# acota cada sector para no mandar un dispositivo entero en una sola grilla.
TOPE_PLAZAS_POR_SECTOR = 200

#: Las acciones de P5. Cada una tiene su servicio en `programas.services.estadias`.
ACCION_LIBERAR = "liberar"
ACCION_FUERA_SERVICIO = "fuera_servicio"
ACCION_VOLVER = "volver"
ACCION_REUBICAR = "reubicar"
ACCION_RESERVAR = "reservar"
ACCION_PRESTAR = "prestar"

#: El aviso del modal de una plaza ocupada cuando no hay a dónde mover a la persona.
MOTIVO_SIN_PLAZAS_LIBRES = "No hay plazas libres en el dispositivo para moverla."

#: Por qué una plaza ocupada no se saca de servicio. Lo mismo que rechaza
#: `estadias.sacar_plaza_de_servicio`, dicho antes de intentarlo.
MOTIVO_PLAZA_OCUPADA = "Tiene una estadía activa: reubicá a la persona antes de sacarla de servicio."


def acciones_de_plaza(
    estado, con_reserva_abierta, *, puede_admitir=False, puede_editar=False, puede_buscar_personas=False
):
    """Las acciones que admite una plaza y que quien mira puede ejercer, en el orden del modal.

    Fuera de servicio gana: es la misma precedencia que dibuja `estado_de_plazas`, y una
    plaza fuera de servicio con una reserva abierta —que el servicio de estadías no deja
    escribir— se repone antes de nada. Una reserva abierta se libera (`admitir`). La ocupada
    se reubica si quien mira puede admitir; si no, sigue siendo «sacar de servicio»,
    bloqueada con su motivo. La disponible ofrece reservar y prestar (`admitir`) y sacar de
    servicio (`editar`). Reservar y prestar buscan a la persona por DNI en el padrón, así que
    piden además `ciudadano.ver` (`puede_buscar_personas`), como el asistente de ingreso. Lista vacía: la plaza no es accionable para este usuario.
    """

    if estado.estado == ESTADO_FUERA_SERVICIO:
        return [ACCION_VOLVER] if puede_editar else []
    if con_reserva_abierta:
        return [ACCION_LIBERAR] if puede_admitir else []
    if estado.estado == ESTADO_OCUPADA:
        if puede_admitir:
            return [ACCION_REUBICAR]
        return [ACCION_FUERA_SERVICIO] if puede_editar else []
    acciones = [ACCION_RESERVAR, ACCION_PRESTAR] if puede_admitir and puede_buscar_personas else []
    if puede_editar:
        acciones.append(ACCION_FUERA_SERVICIO)
    return acciones


def bloqueo_de_plaza(estado, accion, hay_plazas_libres=True):
    """El motivo por el que la acción no va a proceder, o cadena vacía.

    `hay_plazas_libres` solo lo mira la reubicación y lo trae quien armó el formulario del
    cambio de plaza: saberlo cuesta el mapa de ingreso, que no se arma si la acción es otra.
    """

    if accion == ACCION_FUERA_SERVICIO and estado.estado == ESTADO_OCUPADA:
        return MOTIVO_PLAZA_OCUPADA
    if accion == ACCION_REUBICAR and not hay_plazas_libres:
        return MOTIVO_SIN_PLAZAS_LIBRES
    return ""


def plaza_para_accion(
    dispositivo, plaza_pk, *, puede_liberar=False, puede_configurar_plazas=False, puede_ver_personas=False
):
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
    # `puede_liberar` es `dispositivo.admitir`: liberar, reubicar, reservar y prestar.
    acciones = acciones_de_plaza(
        estado,
        reserva is not None,
        puede_admitir=puede_liberar,
        puede_editar=puede_configurar_plazas,
        puede_buscar_personas=puede_ver_personas,
    )
    if not acciones:
        return None
    return {
        "plaza": plaza,
        "estado": estado,
        # `accion` es la primera: la única salvo en la plaza disponible, que ofrece varias.
        "accion": acciones[0],
        "acciones": acciones,
        "bloqueo": bloqueo_de_plaza(estado, acciones[0]),
        "reserva": reserva,
    }


def datos_para_el_modal(plaza, estado, acciones, bloqueo=""):
    """Lo que el modal Alpine necesita de una plaza, serializable con `json_script`.

    Sale de lo que el mapa ya calculó: ni una consulta más por plaza. `detalle` es el de
    `estado_de_plazas`, así que respeta `ciudadano.ver` igual que la celda.
    """

    return {
        "codigo": plaza.codigo,
        "estado": estado.estado,
        "detalle": estado.detalle,
        "acciones": list(acciones),
        "bloqueo": bloqueo,
    }


def _resumen(conteo):
    """Las cifras de un `Conteo` del servicio de ocupación, con las claves que lee la pantalla.

    P5 separa las reservas de los préstamos; P4 conserva el agregado del servicio.
    """

    return {
        "total": conteo.totales,
        "operativas": conteo.operativas,
        "fuera_servicio": conteo.fuera_de_servicio,
        "ocupadas": conteo.ocupadas,
        "reservadas": conteo.reservadas_sin_prestamo,
        "prestadas": conteo.prestadas,
        "disponibles": conteo.disponibles,
        "porcentaje": tension_de_ocupacion(conteo).porcentaje,
    }


def _plaza_para_el_mapa(plaza, estado, url, click=""):
    """Un dict del mapa: estado y tono vienen del servicio, nunca del template ni de acá."""

    return {
        "codigo": plaza.codigo,
        "estado": estado.estado,
        "tono": estado.tono,
        "detalle": estado.detalle,
        "detalle_completo": estado.detalle_completo,
        "url": url,
        "click": click,
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
    filas = (
        ReservaPlaza.objects.abiertas()
        .filter(plaza_id__in=[plaza.pk for plaza in plazas])
        .order_by("-id")
        .values_list("plaza_id", "id")
    )
    return dict(filas)


def sectores_con_plazas(dispositivo, *, puede_liberar=False, puede_configurar_plazas=False, puede_ver_personas=False):
    """Todo lo que la pantalla dibuja: sectores activos con su mapa acotado y los totales.

    Las cifras del encabezado y de cada sector salen de `ocupacion.ocupacion_de_plazas` y
    los estados de las celdas de `ocupacion.estado_de_plazas`: las dos son el mismo
    servicio, así que el encabezado y el mapa no pueden decir cosas distintas.

    `puede_liberar` (`dispositivo.admitir`; también habilita reubicar) y `puede_configurar_plazas`
    (`dispositivo.editar`) los resuelve la vista con alcance al dispositivo. Una plaza
    cuya acción el usuario no puede ejercer llega sin `url`, salvo que pueda editar su
    identidad: en ese caso enlaza al modal de edición, sin liberar ni cambiar el estado.

    La que sí tiene acción trae `url` (`?plaza=<id>`, el enlace directo) y, si su modal se
    arma en el cliente, `click` (`abrirPlaza(<id>)`): el mapa dibuja un botón y no recarga.
    `plazas_modal` es `{id: datos}` de esas plazas, para el `json_script` de la página. La
    reubicación es un botón también (`abrirReubicar(<id>)`), pero su modal no viaja en la
    página: lo pide la pantalla al tocar, porque depende de la estadía.
    """

    # Un solo instante para las dos: la vigencia de una reserva es por tiempo, y con dos
    # `now()` distintos el encabezado y una celda podrían discrepar justo en su borde.
    momento = timezone.now()
    ocupacion = ocupacion_de_plazas(dispositivo, momento).de(dispositivo)
    sectores = {sector.pk: sector for sector in Sector.objects.filter(dispositivo=dispositivo, activo=True)}
    por_sector = _plazas_por_sector(list(sectores))

    dibujadas = [plaza for item in ocupacion.sectores for plaza in por_sector.get(item.sector_id, ())]
    # Una sola vez para todo el dispositivo, no una por sector: son dos consultas fijas.
    estados = estado_de_plazas(dibujadas, momento, puede_ver_personas=puede_ver_personas)
    reservas = _reservas_abiertas_por_plaza(dibujadas)

    armados = []
    plazas_modal = {}
    for item in ocupacion.sectores:
        sector = sectores[item.sector_id]
        plazas = por_sector.get(item.sector_id, [])
        celdas = []
        for plaza in plazas:
            estado = estados[plaza.pk]
            acciones = acciones_de_plaza(
                estado,
                plaza.pk in reservas,
                puede_admitir=puede_liberar,
                puede_editar=puede_configurar_plazas,
                puede_buscar_personas=puede_ver_personas,
            )
            url = f"?plaza={plaza.pk}" if acciones else ""
            click = ""
            if ACCION_REUBICAR in acciones:
                click = f"abrirReubicar({plaza.pk})"
            elif acciones:
                click = f"abrirPlaza({plaza.pk})"
                plazas_modal[plaza.pk] = datos_para_el_modal(
                    plaza, estado, acciones, bloqueo_de_plaza(estado, acciones[0])
                )
            if not url and puede_configurar_plazas:
                # Editar la identidad no libera la reserva ni exige dispositivo.admitir.
                url = f"?editar_plaza={plaza.pk}"
            celdas.append(_plaza_para_el_mapa(plaza, estado, url, click))
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
        "plazas_modal": plazas_modal,
    }
