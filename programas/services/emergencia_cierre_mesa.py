"""Cerrar desde la mesa una familia alojada y reabrir un caso cerrado (Cambio 588, decisiones 6 y 7 del replanteo).

Las dos son de la supervisión: exigen ``emergencia.cerrar_reabrir`` **con alcance sobre el programa EMERGENCIA**
(``puede_cerrar_y_reabrir``), que ni la guardia ni quien solo opera o supervisa tiene. La vista lo vuelve a decidir
y acá se vuelve a exigir: no se confía en que la pantalla se haya acordado.

Cerrar una familia alojada
--------------------------

Es el caso ``ALOJADO`` —con el ingreso completo o parcial, ``caso.ingreso_parcial``— cuya familia ya no está y la
guardia no registró el egreso: el caso quedaría abierto y las personas ocupando camas. **El motivo es obligatorio**
(200 caracteres) y queda en ``observacion_cierre`` con el motivo «Otro»; la traza es ``CERRADO_POR_LA_MESA``.

**Qué pasa con las estadías: se egresan en la misma transacción.** Es lo que ya hace el egreso de la guardia:
``estadias.egresar_persona`` cierra la estadía, suelta la cama y avisa a Emergencia con ``estadia_egresada``, y el
receptor (``emergencia_cierre.al_egresar_estadia``) marca ``egresado_en`` del integrante. Bloquear el cierre hasta que
la guardia egrese a cada uno dejaría la acción sin uso justo en el caso para el que existe. El egreso lleva el motivo
«Otro» del catálogo, el destino «Cierre del caso por la mesa de Emergencia» y ``verificar_alcance=False``: la mesa no
pertenece al Equipo del dispositivo y su autorización es la capacidad de este módulo.

El orden de los candados
------------------------

``estadía → caso``, **el de un egreso**, y no ``caso → estadía``: el receptor del egreso bloquea el caso *después* de la
estadía (``emergencia_alojar``, «por qué no forma un ciclo»), y si acá se tomara el caso primero y se esperara una
estadía, un egreso de la guardia a la vez —que tiene la estadía y espera el caso— cortaría a uno con ``ERROR 1213``. Se
leen sin candado las estadías abiertas de la familia, se toman las instituciones en compartido y las estadías por pk
(``dispositivos.bloquear_instituciones``, la fuente única de ese orden), recién entonces el caso, y se vuelve a mirar:
si el caso ya no está alojado o apareció una estadía que no se bloqueó, :class:`EstadoCambio` sin escribir nada.

Reabrir un caso cerrado
-----------------------

Vuelve **al estado anterior al cierre**: el que dejó la última traza que lo cerró (``estado_anterior``), sin columna
nueva. Un caso cerrado sin alojamiento vuelve a ``EN_GESTION`` con su dueño; uno cerrado estando alojado, a
``ALOJADO``. Se limpian ``cerrado_en`` —para que un cierre posterior marque la fecha de **ese** cierre, y la constraint
``caso_emergencia_cerrado_con_marca`` solo mira a los ``CERRADO``— y el motivo y la observación del cierre, que pasan
al detalle de la traza ``REABIERTO``. Lo que el cierre **hizo** no se deshace: los egresos de las estadías quedan.

**Una familia, un caso abierto (Cambio 579):** si la familia ya tiene **otro** caso abierto, reabrir se rechaza con
:class:`ReaperturaConOtroCasoAbierto`. La búsqueda es la de las altas (``caso_abierto_de_la_familia``) y corre con el
candado del numerador puesto (``serializar_altas``), que es el que serializa toda alta: orden **numerador → caso**.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from legajos.models import Ciudadano
from programas.models import CasoEmergencia, Estadia, GrupoFamiliar, IntegranteGrupo, MotivoEgreso, TrazaCaso
from programas.services.dispositivos import bloquear_instituciones
from programas.services.emergencia import EstadoCambio
from programas.services.emergencia_comun import _bloquear_caso, _cerrar, _trazar
from programas.services.emergencia_familia import caso_abierto_de_la_familia, serializar_altas
from programas.services.emergencia_programa import puede_cerrar_y_reabrir
from programas.services.estadias import egresar_persona

Estado = CasoEmergencia.Estado
Accion = TrazaCaso.Accion

SIN_PERMISO_DE_CERRAR_Y_REABRIR = (
    "Solo quien supervisa la mesa, con permiso para cerrar y reabrir casos, puede hacer esto."
)
MOTIVO_OBLIGATORIO = "Indicá por qué se cierra el caso desde la mesa."
MOTIVO_LARGO = "El motivo no puede tener más de 200 caracteres."
#: Qué motivo del catálogo de egresos lleva el egreso que hace la mesa (el primero activo) y a dónde dice que fue.
CODIGOS_MOTIVO_EGRESO = ("otro", "abandono")
DESTINO_DEL_EGRESO = "Cierre del caso por la mesa de Emergencia"
OBSERVACION_DEL_EGRESO = "Cierre del caso {numero} por la mesa de Emergencia."
SIN_MOTIVO_DE_EGRESO = (
    "El catálogo de motivos de egreso no tiene un motivo «Otro» activo: sin él no se pueden egresar las personas "
    "alojadas. Pedile a quien administra el sistema que lo reactive."
)
#: Los estados a los que un cierre de la mesa o del egreso deja volver. El resto no pasa por un cierre.
ESTADOS_AL_REABRIR = (Estado.EN_GESTION, Estado.ALOJADO)


class ReaperturaConOtroCasoAbierto(ValidationError):
    """Reabrir dejaría a la familia con **dos** casos abiertos (Cambio 579): se rechaza. ``caso`` es el otro."""

    def __init__(self, caso):
        self.caso = caso
        super().__init__(
            f"No se puede reabrir: la familia ya tiene otro caso abierto ({caso.numero}). "
            "Una familia tiene un solo caso abierto: seguí con ese, o cerralo primero."
        )


def puede_cerrar_alojado_por_la_mesa(caso):
    """¿Se ofrece «Cerrar: la familia ya no está» en la ficha? **Pura, sin consultas:** el caso está ``ALOJADO``."""

    return caso.estado == Estado.ALOJADO


def puede_reabrir_el_caso(caso):
    """¿Se ofrece «Reabrir» en la ficha? **Pura, sin consultas:** el caso está ``CERRADO``."""

    return caso.estado == Estado.CERRADO


def personas_egresadas(cantidad):
    """«1 persona egresada» / «N personas egresadas»: el único plural, para la traza y para el aviso."""

    return "1 persona egresada" if cantidad == 1 else f"{cantidad} personas egresadas"


def _exigir_supervision(usuario):
    if not puede_cerrar_y_reabrir(usuario):
        raise PermissionDenied(SIN_PERMISO_DE_CERRAR_Y_REABRIR)


def _motivo_limpio(motivo):
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError({"motivo": MOTIVO_OBLIGATORIO})
    if len(motivo) > 200:
        raise ValidationError({"motivo": MOTIVO_LARGO})
    return motivo


def _estadias_abiertas_de(grupo_id):
    """``{estadia_id: dispositivo_id}`` de los integrantes del grupo con la estadía abierta. Una consulta."""

    return dict(
        IntegranteGrupo.objects.filter(grupo_id=grupo_id, estadia__estado=Estadia.Estado.ACTIVA).values_list(
            "estadia_id", "estadia__dispositivo_id"
        )
    )


def _motivo_de_egreso():
    for codigo in CODIGOS_MOTIVO_EGRESO:
        motivo = MotivoEgreso.objects.filter(codigo=codigo, activo=True).first()
        if motivo is not None:
            return motivo
    raise ValidationError(SIN_MOTIVO_DE_EGRESO)


@transaction.atomic
def cerrar_alojado_por_la_mesa(caso, usuario, motivo):
    """Cierra un caso ``ALOJADO`` cuya familia ya no está, con motivo obligatorio (decisión 6).

    Egresa en la misma transacción a las personas que sigan con la estadía abierta (ver el docstring del módulo,
    «Qué pasa con las estadías»). El caso queda ``CERRADO`` con el motivo «Otro» y ``motivo`` como observación; la
    traza ``CERRADO_POR_LA_MESA`` va por supervisor y dice cuántas personas se egresaron. Un caso que ya no está
    ``ALOJADO`` —lo cerró otro, o la guardia sumó personas— es un :class:`EstadoCambio` y no se escribe nada.

    Devuelve el caso, con ``caso.estadias_egresadas``.
    """

    _exigir_supervision(usuario)
    motivo = _motivo_limpio(motivo)

    pk = getattr(caso, "pk", caso)
    grupo_id = CasoEmergencia.objects.values_list("grupo_id", flat=True).get(pk=pk)
    # El orden de un egreso (estadía → caso), no el del módulo: ver el docstring.
    previas = _estadias_abiertas_de(grupo_id)
    bloqueadas = []
    if previas:
        bloquear_instituciones(sorted(set(previas.values())))
        bloqueadas = list(Estadia.objects.select_for_update().filter(pk__in=previas).order_by("pk"))
    caso = _bloquear_caso(pk)
    if not puede_cerrar_alojado_por_la_mesa(caso):
        mensaje = (
            f"El caso {caso.numero} ya está cerrado. Recargá la ficha."
            if caso.estado == Estado.CERRADO
            else f"El caso {caso.numero} ya no está alojado. Recargá la ficha."
        )
        raise EstadoCambio(mensaje, estado_actual=caso.estado, caso=caso)
    if set(_estadias_abiertas_de(grupo_id)) - {estadia.pk for estadia in bloqueadas}:
        raise EstadoCambio(
            f"La familia del caso {caso.numero} cambió mientras tanto: la guardia registró un ingreso. Recargá la ficha.",
            estado_actual=caso.estado,
            caso=caso,
        )
    por_egresar = [estadia for estadia in bloqueadas if estadia.activa]
    motivo_egreso = _motivo_de_egreso() if por_egresar else None

    parcial = f"ingreso parcial, {caso.total_alojado} de {caso.grupo.total_declarado}" if caso.ingreso_parcial else ""
    _cerrar(caso, CasoEmergencia.MotivoCierre.OTRO, motivo)
    personas = personas_egresadas(len(por_egresar))
    _trazar(
        caso,
        usuario,
        Accion.CERRADO_POR_LA_MESA,
        estado_anterior=Estado.ALOJADO,
        detalle=f"Cerrado por la mesa{f' ({parcial})' if parcial else ''}: {motivo} · {personas}",
        por_supervisor=True,
    )
    # El caso ya está cerrado: el receptor del egreso marca a cada integrante y no vuelve a cerrarlo.
    for estadia in por_egresar:
        egresar_persona(
            estadia=estadia,
            usuario=usuario,
            motivo=OBSERVACION_DEL_EGRESO.format(numero=caso.numero),
            motivo_egreso=motivo_egreso,
            destino=DESTINO_DEL_EGRESO,
            verificar_alcance=False,
        )
    caso.estadias_egresadas = len(por_egresar)
    return caso


def _estado_antes_del_cierre(caso):
    """El estado en que estaba el caso cuando se cerró: lo dice la última traza que lo cerró. Una consulta.

    Los egresos que vienen después de un cierre de la mesa también dejan una traza con el caso ya ``CERRADO``, pero
    su ``estado_anterior`` es ``CERRADO``: no cuentan. Sin traza que lo diga (casos de antes de que la traza lo
    guardara) se deduce del cierre: ``TODOS_EGRESADOS`` viene de ``ALOJADO``; el resto, de la gestión.
    """

    traza = (
        TrazaCaso.objects.filter(caso_id=caso.pk, estado_nuevo=Estado.CERRADO)
        .exclude(estado_anterior=Estado.CERRADO)
        .order_by("-id")
        .first()
    )
    if traza is not None and traza.estado_anterior in ESTADOS_AL_REABRIR:
        anterior = traza.estado_anterior
    elif caso.motivo_cierre == CasoEmergencia.MotivoCierre.TODOS_EGRESADOS:
        anterior = Estado.ALOJADO
    else:
        anterior = Estado.EN_GESTION
    # «En gestión» es tener dueño: sin él, el caso vuelve a la bandeja.
    if anterior == Estado.EN_GESTION and caso.tomado_por_id is None:
        return Estado.NUEVO
    return anterior


def otro_caso_abierto_de_la_familia(caso):
    """El caso abierto, **distinto de** ``caso``, de la familia de ``caso``; o ``None``. Sin candados.

    La familia es el responsable más los integrantes que no egresaron (el criterio de las altas): para cada uno,
    ``caso_abierto_de_la_familia``. Quien decide algo con el resultado tiene que haber tomado antes
    ``serializar_altas``.
    """

    responsable_id = GrupoFamiliar.objects.values_list("responsable_id", flat=True).get(pk=caso.grupo_id)
    ciudadanos = {responsable_id}
    ciudadanos.update(
        IntegranteGrupo.objects.filter(
            grupo_id=caso.grupo_id, egresado_en__isnull=True, ciudadano__isnull=False
        ).values_list("ciudadano_id", flat=True)
    )
    for ciudadano in Ciudadano.objects.filter(pk__in=ciudadanos).order_by("pk"):
        otro = caso_abierto_de_la_familia(ciudadano)
        if otro is not None and otro.pk != caso.pk:
            return otro
    return None


@transaction.atomic
def reabrir_caso(caso, usuario):
    """Reabre un caso ``CERRADO``: vuelve al estado anterior al cierre y queda en el historial (decisión 7).

    **Rechaza** con :class:`ReaperturaConOtroCasoAbierto` si la familia ya tiene otro caso abierto: no puede
    haber dos. El candado del numerador se toma **antes** de mirarlo (el mismo de las altas) y después el del caso:
    orden numerador → caso. Un caso que ya no está cerrado —lo reabrió otro— es un :class:`EstadoCambio`.

    La traza ``REABIERTO`` lleva, en el detalle, lo que el cierre había dicho (motivo y observación), que se
    limpian de la fila. Devuelve el caso.
    """

    _exigir_supervision(usuario)
    pk = getattr(caso, "pk", caso)
    serializar_altas()
    caso = _bloquear_caso(pk)
    if not puede_reabrir_el_caso(caso):
        raise EstadoCambio(
            f"El caso {caso.numero} no está cerrado. Recargá la ficha.", estado_actual=caso.estado, caso=caso
        )
    otro = otro_caso_abierto_de_la_familia(caso)
    if otro is not None:
        raise ReaperturaConOtroCasoAbierto(otro)

    cierre = caso.get_motivo_cierre_display() if caso.motivo_cierre else "sin motivo registrado"
    if caso.observacion_cierre:
        cierre = f"{cierre} · {caso.observacion_cierre}"
    anterior = _estado_antes_del_cierre(caso)
    caso.estado = anterior
    caso.cerrado_en = None
    caso.motivo_cierre = ""
    caso.observacion_cierre = ""
    caso.save(update_fields=["estado", "cerrado_en", "motivo_cierre", "observacion_cierre", "modificado"])
    _trazar(
        caso,
        usuario,
        Accion.REABIERTO,
        estado_anterior=Estado.CERRADO,
        detalle=f"Reabierto, vuelve a «{caso.get_estado_display()}». Lo había cerrado: {cierre}",
        por_supervisor=True,
    )
    return caso
