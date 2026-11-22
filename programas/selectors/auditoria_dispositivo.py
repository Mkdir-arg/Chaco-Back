"""Auditoría del dispositivo: qué pasó, quién lo hizo y cuándo (MVP v2, etapa 3 · #699).

La solapa «Historial» del detalle (P4) junta en **una sola lista**, de lo más nuevo a lo
más viejo, las cuatro trazas que hay en el programa:

1. ``TrazaDispositivo`` — el legajo institucional (alta, edición, validación y demás
   cambios de estado), las plazas (reservas, préstamos, fuera de servicio) y los turnos.
2. ``MovimientoEstadia`` — lo que le pasó a cada persona: ingreso, cambio de sector o de
   plaza, egreso. Es la fuente de las estadías: los servicios también escriben una
   ``TrazaDispositivo`` por cada uno (``ESTADIA_*``), pero esa se **omite** acá para que
   cada acción sea una sola línea. El movimiento dice más (la plaza de origen y de
   destino, la persona) y es el que lleva la fecha de cuándo pasó.
3. ``EntradaBitacora`` con ``version > 1`` — las **correcciones** de la bitácora. Las
   novedades en sí no entran: la bitácora ya es su propio registro, inmutable, y el
   historial se llenaría de partes del turno.
4. ``TrazaInspeccion`` — los relevamientos edilicios de los edificios que ocupa el
   dispositivo (asignar, reasignar, cancelar, resultado, fotos).

La solapa Historial de la página operativa del edificio (Cambio 571) lee **esta misma fuente** acotada a un edificio
(``edificio=`` de :class:`FeedAuditoria`) y suma una quinta, ``TrazaEntrega``: las entregas de kits a ese edificio.
Las trazas del dispositivo anteriores al Cambio 573 y sin edificio entran por lo que dicen, ver :func:`q_trazas_del_edificio`.

Los textos son de operador: ningún código de acción, nombre de campo crudo ni id de una
persona llega a la pantalla.

Costo
-----

Fijo: un ``COUNT`` y una lectura por fuente, ocho consultas (diez con los kits del edificio), sin importar cuántas
filas tenga cada una. Para la página ``p`` se leen como mucho ``p × tamaño`` filas de cada fuente
—ya ordenadas por la base— y se mezclan en Python; cada lectura trae lo que la línea
muestra con ``select_related``, así que no hay una consulta por fila.
"""

import json
import re

from django.core.exceptions import FieldDoesNotExist
from django.db.models import Exists, ExpressionWrapper, OuterRef, Q, TextField, Value
from django.db.models.functions import Concat
from django.utils import timezone
from django.utils.formats import date_format

from programas.models import (
    Dispositivo,
    EntradaBitacora,
    InspeccionEdificio,
    MovimientoEstadia,
    Plaza,
    Sector,
    TrazaDispositivo,
    TrazaEntrega,
    TrazaInspeccion,
)

#: Trazas del dispositivo que ya cuenta un `MovimientoEstadia`: se omiten para no duplicar.
ACCIONES_DE_ESTADIA = ("ESTADIA_INGRESO", "ESTADIA_EGRESO", "ESTADIA_CAMBIO_PLAZA", "ESTADIA_ASIGNACION_PLAZA")

#: Qué pasó, en idioma de operador, por cada acción de `TrazaDispositivo`.
TITULOS_TRAZA = {
    "CREADO": "Alta del dispositivo",
    "EDITADO": "Edición de los datos del dispositivo",
    "ENVIADO_VALIDACION": "Envío a validación",
    "VALIDADO": "Validación del dispositivo",
    "OBSERVADO": "Observación del dispositivo",
    "RECHAZADO": "Rechazo del dispositivo",
    "INACTIVADO": "Inactivación del dispositivo",
    "REACTIVADO": "Reactivación del dispositivo",
    "CERRADO": "Cierre del dispositivo",
    "PLAZA_RESERVADA": "Plaza reservada",
    "PLAZA_LIBERADA": "Reserva de plaza liberada",
    "PLAZA_FUERA_SERVICIO": "Plaza fuera de servicio",
    "PLAZA_EN_SERVICIO": "Plaza de nuevo en servicio",
    "TURNO_CREADO": "Alta de un turno",
    "TURNO_EDITADO": "Cambio en un turno",
    "SECTOR_CREADO": "Alta de un sector",
    "SECTOR_EDITADO": "Cambio en un sector",
    "SECTOR_BAJA": "Baja de un sector",
    "SECTOR_REACTIVADO": "Reactivación de un sector",
    "PLAZAS_AGREGADAS": "Alta de plazas",
    "PLAZA_EDITADA": "Cambio en una plaza",
    "PLAZA_BAJA": "Baja de una plaza",
    "PLAZA_REACTIVADA": "Reactivación de una plaza",
    "EDIFICIO_CREADO": "Alta de un edificio",
    "EDIFICIO_EDITADO": "Cambio en los datos del edificio",
    "EDIFICIO_VINCULADO": "Edificio vinculado al dispositivo",
    "EDIFICIO_DESVINCULADO": "Edificio desvinculado del dispositivo",
}

#: Las acciones que mueven el estado del legajo: el detalle es «antes → después».
_CAMBIOS_DE_ESTADO = frozenset(
    {"CREADO", "ENVIADO_VALIDACION", "VALIDADO", "OBSERVADO", "RECHAZADO", "INACTIVADO", "REACTIVADO", "CERRADO"}
)

_TONOS_TRAZA = {
    "VALIDADO": "success",
    "REACTIVADO": "success",
    "OBSERVADO": "warning",
    "RECHAZADO": "danger",
    "CERRADO": "danger",
    "PLAZA_FUERA_SERVICIO": "warning",
    # La baja de un sector saca plazas de la capacidad operativa: se lee como la de una plaza.
    "SECTOR_BAJA": "warning",
    "SECTOR_REACTIVADO": "success",
    "PLAZA_BAJA": "warning",
    "PLAZA_REACTIVADA": "success",
    "EDIFICIO_DESVINCULADO": "warning",
}

#: El id del ciudadano que `reservar_plaza` escribe en la traza: no va a la pantalla.
_CIUDADANO_EN_TRAZA = re.compile(r"\s·\s*ciudadano\s+\d+\s*$")


def _tono_de_inspeccion(traza):
    """El resultado de un relevamiento no es una buena noticia si salió crítico."""

    accion = TrazaInspeccion.Accion
    if traza.accion == accion.CANCELADA:
        return "warning"
    if traza.accion != accion.REALIZADA:
        return ""
    return "danger" if traza.inspeccion.criticidad == InspeccionEdificio.Criticidad.ALTA else "success"


# Fuentes, en el orden que desempata dos líneas del mismo instante.
_TRAZA, _MOVIMIENTO, _CORRECCION, _INSPECCION, _ENTREGA = range(5)
FUENTE_INSPECCION = _INSPECCION

#: Las trazas del dispositivo que hablan de un sector (el detalle trae «edificio <código>») o de una plaza (el
#: detalle trae «<código> (<sector>)»). Son las únicas que se pueden atar a un edificio sin un campo propio.
ACCIONES_DE_SECTOR = ("SECTOR_CREADO", "SECTOR_EDITADO", "SECTOR_BAJA", "SECTOR_REACTIVADO")
ACCIONES_DE_PLAZA = (
    "PLAZA_RESERVADA",
    "PLAZA_LIBERADA",
    "PLAZA_FUERA_SERVICIO",
    "PLAZA_EN_SERVICIO",
    "PLAZA_EDITADA",
    "PLAZA_BAJA",
    "PLAZA_REACTIVADA",
)
ACCION_DE_LOTE_DE_PLAZAS = "PLAZAS_AGREGADAS"


def q_trazas_del_edificio(edificio):
    """Las trazas del dispositivo que son de ``edificio``: alta, cambio y baja de sectores y plazas, y las reservas.

    Desde el Cambio 573 la traza guarda el edificio del sector en el momento del evento (``TrazaDispositivo.edificio``):
    ``Q(edificio=edificio)`` es exacto y sobrevive a que el sector se renombre, se mude o su nombre lo reuse otro.
    Las anteriores (``edificio`` NULL, sin backfill) se siguen derivando del detalle que escriben los servicios: un
    sector lo nombra por **código de edificio** (``… · edificio ED-A``, y ``(antes: ED-B)`` si se mudó), que es exacto
    y se lee siempre; una plaza o un lote de plazas por **nombre de sector**, contra los sectores de este edificio en el
    mismo dispositivo, dentro de la misma consulta. Esa derivación por nombre, solo para las trazas de plaza o de lote
    **anteriores al Cambio 573**, tiene estos límites:

    * un sector **renombrado** deja de coincidir con sus trazas de plaza viejas, que desaparecen del edificio;
    * un sector **mudado** a otro edificio se lleva consigo las trazas de plaza viejas que ya tenía (se leen por su
      nombre contra el edificio actual), no solo las duplica;
    * dos sectores del mismo dispositivo con el mismo nombre en edificios distintos (uno dado de baja libera el suyo)
      comparten sus trazas de plaza viejas: las de un nombre reusado se atribuyen al edificio que hoy lo tiene.
    """

    codigo = edificio.codigo
    de_sector = Q(accion__in=ACCIONES_DE_SECTOR) & (
        Q(detalle__endswith=f"edificio {codigo}")
        | Q(detalle__contains=f"edificio {codigo} (antes:")
        | Q(detalle__contains=f"(antes: {codigo})")
    )
    sectores = Sector.objects.filter(dispositivo_id=OuterRef("dispositivo_id"), edificio_id=edificio.pk).alias(
        texto=ExpressionWrapper(OuterRef("detalle"), output_field=TextField())
    )
    sin_edificio = Q(edificio__isnull=True)
    de_plaza = (
        sin_edificio
        & Q(accion__in=ACCIONES_DE_PLAZA)
        & Q(Exists(sectores.filter(texto__contains=Concat(Value("("), "nombre", Value(")")))))
    )
    de_lote = (
        sin_edificio
        & Q(accion=ACCION_DE_LOTE_DE_PLAZAS)
        & Q(Exists(sectores.filter(texto__startswith=Concat(Value("Sector "), "nombre", Value(" · ")))))
    )
    return Q(edificio=edificio) | de_sector | de_plaza | de_lote


def _quien(usuario):
    if usuario is None:
        return "Sistema"
    return usuario.get_full_name() or usuario.get_username()


def _cuando(momento):
    return date_format(timezone.localtime(momento), "d/m/Y H:i")


def _persona(estadia):
    ciudadano = estadia.ciudadano
    return f"{ciudadano.apellido}, {ciudadano.nombre}"


def _plaza(plaza):
    return f"plaza {plaza.codigo} ({plaza.sector.nombre})" if plaza is not None else "sin plaza"


def _mayuscula(texto):
    return texto[:1].upper() + texto[1:]


def _campo_legible(campo):
    try:
        return str(Dispositivo._meta.get_field(campo).verbose_name)
    except FieldDoesNotExist:
        return campo


def _valor_legible(valores, clave):
    """El guion es para el campo **vacío**, no para todo lo que Python considera falso.

    Comparar contra ``None`` y ``""`` y no con ``or``: un cupo que pasó de 0 a 10 o una
    casilla que se destildó son cambios reales, y con ``or`` el valor anterior se dibujaba
    como «—».
    """

    valor = valores.get(clave)
    return "—" if valor is None or valor == "" else valor


def _edicion_legible(detalle):
    """Los cambios de la edición con el nombre del campo como lo ve el operador."""

    try:
        cambios = json.loads(detalle)
    except (TypeError, json.JSONDecodeError):
        return detalle
    if not isinstance(cambios, dict):
        return detalle
    return " · ".join(
        f"{_campo_legible(campo)}: {_valor_legible(valores, 'anterior')} → {_valor_legible(valores, 'nuevo')}"
        for campo, valores in cambios.items()
        if isinstance(valores, dict)
    )


def _titulo_desconocido(accion):
    return accion.replace("_", " ").capitalize()


def evento_de_traza(traza):
    accion = traza.accion
    if accion == "EDITADO":
        detalle = _edicion_legible(traza.detalle)
    elif accion == "PLAZA_RESERVADA":
        # `reservar_plaza` escribe el id del ciudadano, no su nombre: se saca de la línea.
        detalle = _CIUDADANO_EN_TRAZA.sub("", traza.detalle)
    elif accion in _CAMBIOS_DE_ESTADO:
        if traza.estado_anterior:
            detalle = f"{traza.estado_anterior_legible} → {traza.estado_nuevo_legible}"
        else:
            detalle = f"Quedó en {traza.estado_nuevo_legible}"
        if traza.detalle:
            detalle = f"{detalle} · Motivo: {traza.detalle}"
    else:
        detalle = traza.detalle
    return {
        "fecha": traza.creado_en,
        "quien": _quien(traza.usuario),
        "titulo": TITULOS_TRAZA.get(accion) or _titulo_desconocido(accion),
        "detalle": detalle,
        "tono": _TONOS_TRAZA.get(accion, ""),
    }


def evento_de_movimiento(movimiento, *, puede_ver_personas=False):
    tipo = MovimientoEstadia.Tipo
    persona = _persona(movimiento.estadia) if puede_ver_personas else "Persona alojada"
    if movimiento.tipo == tipo.INGRESO:
        titulo = f"Ingreso de {persona}"
        detalle = _mayuscula(_plaza(movimiento.plaza_destino))
        tono = "success"
    elif movimiento.tipo in MovimientoEstadia.TIPOS_DE_CAMBIO_DE_PLAZA:
        que = "sector" if movimiento.tipo == tipo.CAMBIO_SECTOR else "plaza"
        if movimiento.plaza_origen_id is None:
            titulo = f"Asignación de plaza de {persona}"
            detalle = f"Se asignó la {_plaza(movimiento.plaza_destino)}"
        else:
            titulo = f"Cambio de {que} de {persona}"
            detalle = f"De {_plaza(movimiento.plaza_origen)} a {_plaza(movimiento.plaza_destino)}"
        # El motivo es texto libre que el operador escribió sobre la persona: sigue la misma
        # guarda que su nombre. Sin `ciudadano.ver` queda solo en `MovimientoEstadia` (D-SEG-02).
        if movimiento.motivo and puede_ver_personas:
            detalle = f"{detalle} · Motivo: {movimiento.motivo}"
        tono = ""
    elif movimiento.tipo == tipo.EGRESO:
        titulo = f"Egreso de {persona}"
        # El motivo del catálogo y no el texto del movimiento: sin motivo de catálogo, el
        # movimiento guarda las observaciones libres del egreso, que pueden traer datos
        # sensibles y no van al historial institucional (igual que la trayectoria, P16).
        motivo = movimiento.estadia.motivo
        origen = movimiento.plaza_origen
        detalle = f"Liberó la {_plaza(origen)}" if origen is not None else "Sin plaza asignada"
        if motivo is not None:
            detalle = f"{detalle} · Motivo: {motivo.nombre}"
        tono = ""
    else:
        titulo = f"{movimiento.get_tipo_display()} de {persona}"
        detalle = ""
        tono = ""
    return {
        "fecha": movimiento.momento,
        "quien": _quien(movimiento.responsable),
        "titulo": titulo,
        "detalle": detalle,
        "tono": tono,
    }


def evento_de_correccion(entrada):
    detalle = (
        f"{entrada.get_tipo_display()} del turno {entrada.turno.nombre} "
        f"del {entrada.fecha_operativa:%d/%m/%Y} · versión {entrada.version}"
    )
    if entrada.motivo_correccion:
        detalle = f"{detalle} · Motivo: {entrada.motivo_correccion}"
    return {
        "fecha": entrada.creado,
        "quien": _quien(entrada.responsable),
        "titulo": "Corrección de una novedad de la bitácora",
        "detalle": detalle,
        "tono": "",
    }


_TITULOS_ENTREGA = {
    TrazaEntrega.Accion.CREADA: "Entrega de kits armada",
    TrazaEntrega.Accion.EN_CAMINO: "Entrega de kits en camino",
    TrazaEntrega.Accion.RECIBIDA: "Entrega de kits recibida",
    TrazaEntrega.Accion.CANCELADA: "Entrega de kits cancelada",
    TrazaEntrega.Accion.OBSERVADA: "Observación sobre una entrega de kits",
}
_TONOS_ENTREGA = {TrazaEntrega.Accion.RECIBIDA: "success", TrazaEntrega.Accion.CANCELADA: "warning"}


def evento_de_entrega(traza):
    """Una línea por lo que le pasó a una entrega de kits: el número y lo que la traza escribió (ya legible)."""

    detalle = f"Entrega {traza.entrega.numero}"
    if traza.detalle:
        detalle = f"{detalle} · {traza.detalle}"
    return {
        "fecha": traza.creado_en,
        "quien": _quien(traza.usuario),
        "titulo": _TITULOS_ENTREGA.get(traza.accion) or traza.accion_legible,
        "detalle": detalle,
        "tono": _TONOS_ENTREGA.get(traza.accion, ""),
    }


#: Lo que la institución relevada lee en lugar del nombre mientras el relevamiento no se realizó.
EQUIPO_TERRITORIAL = "Equipo territorial"


def evento_de_inspeccion(traza, ve_asignacion=True):
    """Una línea del historial por cada movimiento del relevamiento edilicio.

    Con ``ve_asignacion`` en falso —quien solo opera la institución— y el relevamiento
    **sin realizar (en curso o cancelado)**, la línea no nombra a nadie: ni al agente asignado ni a quien
    ejecutó la acción. Es la misma regla que la solapa Infraestructura
    (`programas.services.inspecciones.ve_la_asignacion`), que acá hay que volver a aplicar
    porque el detalle de la traza se escribió legible **con el nombre adentro**. El texto se
    **rearma desde el modelo** en vez de recortar el guardado: recortar depende del formato
    con el que se escribió y se rompe en silencio cuando ese formato cambia.

    Una vez realizado, se ve todo: el resultado del relevamiento es auditable y la solapa ya
    muestra quién relevó.
    """

    inspeccion = traza.inspeccion
    if ve_asignacion or inspeccion.estado == inspeccion.Estado.REALIZADA:
        return {
            "fecha": traza.creado_en,
            "quien": _quien(traza.usuario),
            "titulo": traza.get_accion_display(),
            "detalle": traza.detalle,
            "tono": _tono_de_inspeccion(traza),
        }
    detalle = f"Edificio {inspeccion.edificio.nombre}"
    if traza.accion == TrazaInspeccion.Accion.ASIGNADA:
        detalle = f"{detalle} · vence el {date_format(inspeccion.fecha_vencimiento, 'd/m/Y')}"
    return {
        "fecha": traza.creado_en,
        "quien": EQUIPO_TERRITORIAL,
        "titulo": traza.get_accion_display(),
        "detalle": detalle,
        "tono": _tono_de_inspeccion(traza),
    }


class FeedAuditoria:
    """La auditoría del dispositivo como una secuencia que entiende `Paginator`.

    `count()` suma los `COUNT` de las cuatro fuentes y un corte ``[desde:hasta]`` lee, de
    cada una, las primeras ``hasta`` filas ya ordenadas, las mezcla por fecha y devuelve el
    tramo pedido. Cada elemento es un dict con ``fecha``, ``quien``, ``titulo``,
    ``detalle`` y ``tono``.

    ``edificios_en_alcance`` (Cambio 523) son los ids de los edificios que quien mira alcanza: ``None`` es toda la
    institución. Con un conjunto, el feed trae solo lo que cuelga de esos edificios —movimientos de estadía en sus
    plazas, correcciones de sus novedades, relevamientos de sus edificios— y **ninguna traza del dispositivo** (legajo, plazas,
    sectores, turnos, edificios): no lleva edificio. Un conjunto vacío no trae nada (fail-closed).

    ``edificio`` (Cambio 571) es el feed de **un** edificio de esta institución: lo mismo que con alcance Edificios sobre
    ese edificio, más las trazas de sectores y plazas que se le atan (:func:`q_trazas_del_edificio`) y, con
    ``con_kits``, sus entregas de kits. ``total()`` los cuenta en una sola consulta.
    """

    def __init__(
        self,
        dispositivo,
        edificios_con_asignacion=frozenset(),
        *,
        usuario_id=None,
        puede_ver_personas=False,
        edificios_en_alcance=None,
        edificio=None,
        con_kits=False,
    ):
        # Los edificios de los que quien mira puede ver de quién es el relevamiento. Lo
        # resuelve el servicio y llega como un conjunto de ids: el selector no evalúa
        # capacidades ni alcance, solo decide qué texto arma con lo que le dieron.
        visibles = frozenset(edificios_con_asignacion)
        if edificio is not None:
            edificios_en_alcance = [edificio.pk]
        limitado = edificios_en_alcance is not None
        ids = list(edificios_en_alcance or ())
        trazas = TrazaDispositivo.objects.filter(dispositivo=dispositivo).exclude(accion__in=ACCIONES_DE_ESTADIA)
        movimientos = MovimientoEstadia.objects.filter(dispositivo=dispositivo)
        correcciones = EntradaBitacora.objects.filter(dispositivo=dispositivo, version__gt=1)
        inspecciones = TrazaInspeccion.objects.filter(inspeccion__edificio__dispositivos=dispositivo)
        if limitado:
            trazas = trazas.filter(q_trazas_del_edificio(edificio)) if edificio is not None else trazas.none()
            # Por ids de plaza y no por el JOIN plaza → sector → edificio en un OR: el OR no usa índice y recorre toda la
            # tabla de movimientos. `todas` y no `objects`: entran también las plazas dadas de baja, como su historia.
            plazas = Plaza.todas.filter(sector__edificio_id__in=ids).values("pk")
            movimientos = movimientos.filter(Q(plaza_destino_id__in=plazas) | Q(plaza_origen_id__in=plazas))
            correcciones = correcciones.filter(edificio_id__in=ids)
            inspecciones = inspecciones.filter(inspeccion__edificio_id__in=ids)
        self.fuentes = (
            (
                _TRAZA,
                trazas.select_related("usuario").order_by("-creado_en", "-id"),
                evento_de_traza,
            ),
            (
                _MOVIMIENTO,
                movimientos.select_related(
                    "responsable",
                    "estadia__ciudadano",
                    "estadia__motivo",
                    "plaza_origen__sector",
                    "plaza_destino__sector",
                ).order_by("-momento", "-id"),
                lambda movimiento: evento_de_movimiento(movimiento, puede_ver_personas=puede_ver_personas),
            ),
            (
                _CORRECCION,
                correcciones.select_related("responsable", "turno").order_by("-creado", "-id"),
                evento_de_correccion,
            ),
            (
                _INSPECCION,
                inspecciones.select_related("usuario", "inspeccion__edificio").order_by("-creado_en", "-id"),
                lambda traza: evento_de_inspeccion(
                    traza,
                    traza.inspeccion.edificio_id in visibles
                    or (usuario_id is not None and traza.inspeccion.asignado_a_id == usuario_id),
                ),
            ),
        )
        if edificio is not None and con_kits:
            entregas = TrazaEntrega.objects.filter(entrega__dispositivo=dispositivo, entrega__edificio_id=edificio.pk)
            self.fuentes += (
                (
                    _ENTREGA,
                    entregas.select_related("usuario", "entrega").order_by("-creado_en", "-id"),
                    evento_de_entrega,
                ),
            )
        self._count = None

    def total(self):
        """Cuántos eventos hay, en **una** consulta (un ``UNION ALL`` de los ``id`` de cada fuente).

        Es el contador de la barra de solapas, que se dibuja con cualquier solapa abierta: ``count()`` son una consulta
        por fuente. Da lo mismo que ``count()``.
        """

        ids = [consulta.order_by().values("pk") for _fuente, consulta, _evento in self.fuentes]
        return ids[0].union(*ids[1:], all=True).count()

    def count(self):
        if self._count is None:
            self._count = sum(consulta.count() for _f, consulta, _e in self.fuentes)
        return self._count

    def __len__(self):
        return self.count()

    def __getitem__(self, corte):
        if not isinstance(corte, slice):
            raise TypeError("La auditoría se lee por tramos: feed[desde:hasta].")
        desde, hasta = corte.start or 0, corte.stop
        if hasta is None:
            hasta = self.count()
        filas = []
        for fuente, consulta, a_evento in self.fuentes:
            for fila in consulta[:hasta]:
                evento = {**a_evento(fila), "fuente": fuente}
                filas.append(((evento["fecha"], -fuente, fila.pk), evento))
        filas.sort(key=lambda par: par[0], reverse=True)
        return [evento for _clave, evento in filas[desde:hasta]]


def auditoria_del_dispositivo(
    dispositivo,
    edificios_con_asignacion=frozenset(),
    *,
    usuario_id=None,
    puede_ver_personas=False,
    edificios_en_alcance=None,
    edificio=None,
    con_kits=False,
):
    """El feed de auditoría del dispositivo, para paginar. Ver :class:`FeedAuditoria`."""

    return FeedAuditoria(
        dispositivo,
        edificios_con_asignacion,
        usuario_id=usuario_id,
        puede_ver_personas=puede_ver_personas,
        edificios_en_alcance=edificios_en_alcance,
        edificio=edificio,
        con_kits=con_kits,
    )
