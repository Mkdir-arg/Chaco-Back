"""Censo automático por turno y por día (MVP v2, etapa 3 · #696).

Existencia inicial, ingresos, egresos y existencia final de un dispositivo, **calculados**:
nadie tipea un número. Reemplaza a los contadores del parte diario, que se cargaban y el
turno siguiente pisaba.

De dónde sale cada cifra
------------------------

* **Existencia** (``inicial`` y ``alojadas_al_fin``): las personas alojadas en un
  instante, con la regla única de :func:`programas.services.ocupacion.alojada_en` —la
  misma fuente de las cifras del mapa y de los indicadores (regla 3 del plan: un solo
  origen)—. Acá no se vuelve a decidir qué es «estar alojada».
* **Ingresos y egresos**: los ``MovimientoEstadia`` de tipo ``INGRESO`` y ``EGRESO`` del
  dispositivo con ``momento`` en ``[inicio, fin)`` del tramo. Son los mismos que la
  bitácora y la línea de tiempo muestran, así que el número y la lista no discrepan.
  **Un cambio de sector o de plaza no cuenta**: la persona sigue en el dispositivo.
* ``final`` = ``inicial + ingresos − egresos``. Es aritmética, no una tercera lectura:
  el censo cierra por definición.

El invariante y qué manda si no se cumple
-----------------------------------------

Cada tramo se **verifica**: ``final`` tiene que ser igual a ``alojadas_al_fin``, que se
calcula por separado, desde las estadías. Con los datos que escriben los servicios de
`programas.services.estadias` **siempre** coincide, también con cargas retroactivas: el
ingreso y el egreso retroactivos graban la misma fecha en la estadía y en su movimiento
(``momento`` = ``fecha_ingreso``/``fecha_egreso``), y el cambio de plaza retroactivo no
mueve la existencia. Solo puede romperse con una escritura por afuera de los servicios
—una estadía cargada sin su movimiento, una fecha editada a mano—.

Si no coincide, **manda la existencia de las estadías** (``alojadas_al_fin``), que es lo
que muestran el mapa y los indicadores: el censo no puede contradecir al mapa. Pero no
se corrige en silencio: el tramo queda con ``cuadra = False`` y ``diferencia`` dice
cuántas personas faltan explicar, para que la pantalla lo muestre. Por eso cada tramo
toma su ``inicial`` de las estadías y **no** del ``final`` del tramo anterior: un
descuadre queda en el turno en el que pasó y no se arrastra al resto del día.

Turnos, huecos y el día operativo
---------------------------------

Los turnos y su fecha operativa salen de `programas.services.bitacora` (``turnos_del_dia``),
el único lugar que sabe que la Noche 22–06 del lunes es del lunes aunque sea martes 03:00.
El **día operativo** va del inicio de su primer turno al inicio del primer turno del día
siguiente: con Mañana 06–14, Tarde 14–22 y Noche 22–06, el lunes va del lunes 06:00 al
martes 06:00. Si los turnos dejan huecos (Mañana 08–12 y Tarde 14–20), cada hueco entra
como un tramo **sin turno** (``turno`` en ``None``): así los tramos de un día son
contiguos, uno empieza donde termina el anterior, la suma de los tramos es el día y un
día empieza donde terminó el anterior. Ningún movimiento queda fuera de todos los días.

**Sin turnos configurados**, el día es el de calendario en hora local, de 00:00 a 00:00,
en un solo tramo sin turno.

Los turnos que se usan son los **activos hoy**, igual que en la bitácora: si la
institución cambia sus horarios, el censo de un día viejo se recalcula con los nuevos.
Los movimientos guardan su ``momento``, no su turno, así que el número del día no cambia
—cambia cómo se reparte entre turnos—.

Hora local y nada de ``Trunc*``
-------------------------------

Las ventanas son instantes con zona armados en hora local (`Turno.ventana`, o la medianoche
local sin turnos). La base solo compara ``momento >= inicio AND momento < fin``; el
reparto por tramo es en Python. Ningún ``Trunc*`` ni ``__date`` sobre un ``DateTimeField``:
en ECOM la base no tiene tablas de zona horaria, Django lo traduce a ``CONVERT_TZ`` y
devuelve ``NULL`` solo en producción.

Costo
-----

**Tres consultas fijas** para cualquier cantidad de días, turnos, personas y movimientos:
los turnos activos (cero si se pasan ya leídos), las estadías alojadas en algún momento
del rango y los ingresos y egresos del rango. Presupuesto ``dispositivos_censo`` en
``scripts/perf_budgets.json``.
"""

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from programas.models import Dispositivo, MovimientoEstadia
from programas.services.bitacora import turno_vigente, turnos_activos, turnos_del_dia
from programas.services.ocupacion import alojada_en, estadias_alojadas_entre

#: Lo único que cambia la existencia del dispositivo. Los cambios de sector o de plaza no.
TIPOS_QUE_CUENTAN = (MovimientoEstadia.Tipo.INGRESO, MovimientoEstadia.Tipo.EGRESO)

#: Cómo se llama el tramo que no es un turno.
SIN_TURNO = "Sin turno"
DIA_COMPLETO = "Día completo"

CERRADO = "cerrado"
EN_CURSO = "en_curso"
POR_VENIR = "por_venir"


@dataclass(frozen=True)
class TramoCenso:
    """Un turno de un día —o un hueco entre turnos— con su censo.

    La ventana es ``[inicio, fin)``. ``turno`` es ``None`` en un hueco o en el día de un
    dispositivo sin turnos.
    """

    turno: object
    nombre: str
    inicio: datetime
    fin: datetime
    inicial: int
    ingresos: int
    egresos: int
    #: La existencia al fin del tramo según las estadías: la verificación independiente.
    alojadas_al_fin: int
    #: ``cerrado``, ``en_curso`` o ``por_venir`` respecto del momento en que se calculó.
    estado: str

    @property
    def final(self) -> int:
        return self.inicial + self.ingresos - self.egresos

    @property
    def cuadra(self) -> bool:
        return self.final == self.alojadas_al_fin

    @property
    def diferencia(self) -> int:
        """Lo que las estadías dicen de más (positivo) o de menos (negativo) que los movimientos."""

        return self.alojadas_al_fin - self.final

    @property
    def en_curso(self) -> bool:
        return self.estado == EN_CURSO


@dataclass(frozen=True)
class CensoDia:
    """El censo de una fecha operativa: sus tramos y el total del día."""

    dispositivo_id: int
    fecha_operativa: date
    tramos: tuple[TramoCenso, ...]
    #: ``False`` si el dispositivo no tiene turnos: el día es un solo tramo de 00:00 a 00:00.
    con_turnos: bool

    @property
    def inicio(self) -> datetime:
        return self.tramos[0].inicio

    @property
    def fin(self) -> datetime:
        return self.tramos[-1].fin

    @property
    def inicial(self) -> int:
        return self.tramos[0].inicial

    @property
    def ingresos(self) -> int:
        return sum(tramo.ingresos for tramo in self.tramos)

    @property
    def egresos(self) -> int:
        return sum(tramo.egresos for tramo in self.tramos)

    @property
    def final(self) -> int:
        return self.inicial + self.ingresos - self.egresos

    @property
    def alojadas_al_fin(self) -> int:
        return self.tramos[-1].alojadas_al_fin

    @property
    def cuadra(self) -> bool:
        """El día cierra contra las estadías y cada uno de sus tramos también."""

        return self.final == self.alojadas_al_fin and all(tramo.cuadra for tramo in self.tramos)

    @property
    def diferencia(self) -> int:
        return self.alojadas_al_fin - self.final

    @property
    def turnos(self) -> tuple[TramoCenso, ...]:
        """Solo los tramos que son un turno, sin los huecos."""

        return tuple(tramo for tramo in self.tramos if tramo.turno is not None)

    @property
    def tramo_en_curso(self) -> TramoCenso | None:
        return next((tramo for tramo in self.tramos if tramo.en_curso), None)

    def tramo_de(self, momento) -> TramoCenso | None:
        """El tramo que contiene ``momento``, o ``None`` si cae fuera del día."""

        return next((tramo for tramo in self.tramos if tramo.inicio <= momento < tramo.fin), None)


def _medianoche(fecha: date) -> datetime:
    """La medianoche **local** de la fecha: el borde del día sin turnos."""

    return timezone.make_aware(datetime.combine(fecha, time(0)), timezone.get_current_timezone())


def _ventanas_del_dia(fecha: date, turnos) -> list[tuple[object, str, datetime, datetime]]:
    """Los tramos contiguos del día operativo: ``(turno o None, nombre, inicio, fin)``."""

    if not turnos:
        return [(None, DIA_COMPLETO, _medianoche(fecha), _medianoche(fecha + timedelta(days=1)))]

    situados = turnos_del_dia(None, fecha, turnos=turnos)
    fin_del_dia = turnos_del_dia(None, fecha + timedelta(days=1), turnos=turnos)[0].inicio
    ventanas = []
    cursor = situados[0].inicio
    for situado in situados:
        if situado.inicio > cursor:
            ventanas.append((None, SIN_TURNO, cursor, situado.inicio))
        ventanas.append((situado.turno, situado.turno.nombre, situado.inicio, situado.fin))
        cursor = situado.fin
    if cursor < fin_del_dia:
        ventanas.append((None, SIN_TURNO, cursor, fin_del_dia))
    return ventanas


def _estado(inicio, fin, ahora) -> str:
    if fin <= ahora:
        return CERRADO
    if inicio <= ahora:
        return EN_CURSO
    return POR_VENIR


def _id_de(dispositivo) -> int:
    if isinstance(dispositivo, Dispositivo):
        if dispositivo.pk is None:
            raise ValueError("No se puede calcular el censo de un dispositivo sin guardar.")
        return dispositivo.pk
    return int(dispositivo)


def censo_por_dia(dispositivo, desde: date, hasta: date | None = None, *, turnos=None, ahora=None) -> list[CensoDia]:
    """El censo de cada fecha operativa de ``desde`` a ``hasta`` (inclusive), en orden.

    ``dispositivo`` es la instancia o su id. ``turnos`` es la lista de turnos activos ya
    leída (`bitacora.turnos_activos`); si no se pasa, se lee —una consulta—. ``ahora``
    solo decide qué tramo está ``en_curso`` (por omisión, el reloj).

    Tres consultas fijas para todo el rango, sin importar cuántos días, turnos,
    personas o movimientos: ver el docstring del módulo.
    """

    hasta = hasta or desde
    if hasta < desde:
        raise ValueError("El rango del censo termina antes de empezar.")
    pk = _id_de(dispositivo)
    if turnos is None:
        turnos = turnos_activos(pk)
    ahora = ahora or timezone.now()

    dias = []
    fecha = desde
    while fecha <= hasta:
        dias.append((fecha, _ventanas_del_dia(fecha, turnos)))
        fecha += timedelta(days=1)
    inicio_rango = dias[0][1][0][2]
    fin_rango = dias[-1][1][-1][3]

    # Las estadías que estuvieron alojadas en algún instante del rango: de acá salen la
    # existencia al inicio y al fin de cada tramo, evaluadas en Python con la regla de
    # `ocupacion`. Una consulta.
    estadias = list(estadias_alojadas_entre(pk, inicio_rango, fin_rango))

    # Los ingresos y egresos del rango, que se reparten por tramo en Python. Una consulta,
    # servida por el índice (dispositivo, momento).
    movimientos = list(
        MovimientoEstadia.objects.filter(
            dispositivo_id=pk,
            tipo__in=TIPOS_QUE_CUENTAN,
            momento__gte=inicio_rango,
            momento__lt=fin_rango,
        ).values_list("tipo", "momento")
    )

    # Los tramos de todo el rango son contiguos: el índice de un momento es su posición
    # entre los inicios. `bisect_right` deja el borde exacto en el tramo que empieza ahí.
    ventanas = [ventana for _, del_dia in dias for ventana in del_dia]
    inicios = [ventana[2] for ventana in ventanas]
    ingresos = [0] * len(ventanas)
    egresos = [0] * len(ventanas)
    for tipo, momento in movimientos:
        indice = bisect_right(inicios, momento) - 1
        if tipo == MovimientoEstadia.Tipo.INGRESO:
            ingresos[indice] += 1
        else:
            egresos[indice] += 1

    def alojadas(momento):
        return sum(1 for ingreso, egreso in estadias if alojada_en(ingreso, egreso, momento))

    # Los tramos son contiguos, así que la existencia al fin de uno es la del inicio del
    # siguiente: se evalúa una vez por borde y no dos (revisión de #832).
    censos = []
    indice = 0
    al_inicio = alojadas(inicio_rango)
    for fecha, del_dia in dias:
        tramos = []
        for turno, nombre, inicio, fin in del_dia:
            al_fin = alojadas(fin)
            tramos.append(
                TramoCenso(
                    turno=turno,
                    nombre=nombre,
                    inicio=inicio,
                    fin=fin,
                    inicial=al_inicio,
                    ingresos=ingresos[indice],
                    egresos=egresos[indice],
                    alojadas_al_fin=al_fin,
                    estado=_estado(inicio, fin, ahora),
                )
            )
            al_inicio = al_fin
            indice += 1
        censos.append(CensoDia(dispositivo_id=pk, fecha_operativa=fecha, tramos=tuple(tramos), con_turnos=bool(turnos)))
    return censos


def censo_del_dia(dispositivo, fecha_operativa: date, *, turnos=None, ahora=None) -> CensoDia:
    """El censo de una fecha operativa. Ver :func:`censo_por_dia`."""

    return censo_por_dia(dispositivo, fecha_operativa, turnos=turnos, ahora=ahora)[0]


def fecha_operativa_de(dispositivo, momento=None, *, turnos=None) -> date:
    """La fecha operativa del día de censo que contiene ``momento`` (por omisión, ahora).

    En un turno es la de `bitacora.turno_vigente`. En un hueco entre turnos, la del día
    cuya ventana lo contiene —un hueco antes del primer turno es del día anterior—. Sin
    turnos, la fecha local del momento.
    """

    momento = momento or timezone.now()
    if turnos is None:
        turnos = turnos_activos(_id_de(dispositivo))
    local = timezone.localtime(momento).date()
    if not turnos:
        return local
    vigente = turno_vigente(None, momento, turnos=turnos)
    if vigente is not None:
        return vigente.fecha_operativa
    for fecha in (local, local - timedelta(days=1)):
        ventanas = _ventanas_del_dia(fecha, turnos)
        if ventanas[0][2] <= momento < ventanas[-1][3]:
            return fecha
    return local  # inalcanzable: los días operativos son contiguos y cubren todo el tiempo


def censo_en_curso(dispositivo, *, ahora=None) -> CensoDia:
    """El censo del día operativo en curso: lo que muestra P10. Su ``tramo_en_curso`` es el turno de ahora."""

    ahora = ahora or timezone.now()
    turnos = turnos_activos(_id_de(dispositivo))
    return censo_del_dia(dispositivo, fecha_operativa_de(dispositivo, ahora, turnos=turnos), turnos=turnos, ahora=ahora)
