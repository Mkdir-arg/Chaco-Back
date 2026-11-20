"""Las reglas de consumo de la solapa «Abastecimiento» de E8 (análisis 009, §3.9, RN-009-15 a 21).

Nada de acá consulta la base ni llama a ``now()`` (RNF-009-12): las reglas reciben números y
``ahora``, y :func:`armar_abastecimiento` cruza en Python lo que leyó
``programas.selectors.emergencia_abastecimiento`` (A1-A5) con la foto de situación. Las alertas
AE-8 a AE-10 están en ``programas.services.alertas_situacion_emergencia`` y lo que se dibuja, en
``programas.services.pantalla_abastecimiento_emergencia``.

**Es una estimación, no un stock** (RNF-009-13): lo recibido se da por consumido a la tasa de la
regla desde la primera recepción del ítem en el dispositivo, sobre las personas, familias o
lactantes que de verdad estuvieron ahí. No sabe lo que llegó por fuera de la mesa ni lo que se perdió.

Reglas:

* **Unidades de hoy** (RN-009-16): personas alojadas en el dispositivo; familias con algún integrante
  alojado, contadas **enteras en su dispositivo principal** (el del integrante alojado de menor
  ``orden``), y sus lactantes **declarados**.
* **Necesario en 48 h** (RN-009-17): dotación = ``unidades × cantidad − recibido``; reposición =
  ``consumo diario × 2 − remanente``, con el remanente sobre las unidades-día reales desde la primera
  recepción. Nunca negativo y **redondeado hacia arriba** por dispositivo e ítem.
* **Faltan** (RN-009-18) = ``necesario − en camino − preparadas`` por dispositivo e ítem; la tabla
  por ítem los suma (lo preparado para uno no tapa el faltante de otro).
* **Sin cobertura 48 h** (RN-009-19): con gente y algún ítem con regla con faltan > 0.
* **Urgencia y orden** (RN-009-20): ver :func:`urgencia` y :func:`clave_de_orden`.
* **Salud** (RN-009-21): :func:`presentar_salud` decide qué se nombra.
"""

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import NamedTuple

from programas.models import Dispositivo, EntregaKit, TipoKit
from programas.selectors.emergencia_tablero import dia_operativo
from programas.services.emergencia_ficha import sin_dosis
from programas.services.ocupacion import NIVEL_CRITICA, NIVEL_EXIGIDA
from programas.services.situacion_emergencia import sin_dosis_provincial, sin_entrega_reciente

Modo = TipoKit.ModoRegla
Por = TipoKit.PorRegla

#: Para cuántas horas se estima lo que hay que mandar (§3.9).
HORAS_A_CUBRIR = 48
HORAS_DEL_DIA = 24

#: Estados de la cobertura de un ítem de reposición.
CUBRE = "cubre"
SIN_CUBRIR = "sin_cubrir"
#: Sin unidades que lo consuman (p. ej. un ítem por lactante en un dispositivo sin lactantes): «—».
SIN_CONSUMO = "sin_consumo"

#: En el orden de urgencia, un ítem nunca recibido es la menor cobertura posible (RN-009-20).
NUNCA = -math.inf


# ---------------------------------------------------------------------------
# Reglas puras
# ---------------------------------------------------------------------------


class Unidades(NamedTuple):
    """Las unidades de consumo de un dispositivo hoy (RN-009-16)."""

    personas: int = 0
    familias: int = 0
    lactantes: int = 0

    def de(self, por):
        return {Por.PERSONA: self.personas, Por.FAMILIA: self.familias, Por.LACTANTE: self.lactantes}.get(por, 0)


def redondear_hacia_arriba(valor: float) -> int:
    """El necesario se manda en unidades enteras: 2,67 kits son 3 (TC-1187-20).

    Se redondea primero a seis decimales: las unidades-día salen de segundos y un 20,000000000004
    no puede volverse 21.
    """

    return max(0, math.ceil(round(valor, 6)))


def principales(personas):
    """``{grupo_id: dispositivo_id}``: el dispositivo principal de cada familia (RN-009-16).

    El del integrante alojado de menor ``orden``; si ya no queda nadie alojado, el del integrante de
    menor ``orden`` de los leídos (para imputarle el consumo que hizo mientras estuvo).
    """

    elegido = {}
    for persona in personas:
        actual = elegido.get(persona.grupo_id)
        clave = (persona.egresado_en is not None, persona.orden)
        if actual is None or clave < actual[0]:
            elegido[persona.grupo_id] = (clave, persona.dispositivo_id)
    return {grupo: dispositivo for grupo, (_clave, dispositivo) in elegido.items()}


def unidades_de_hoy(personas) -> dict:
    """``{dispositivo_id: Unidades}`` de los dispositivos con alguien alojado ahora. Sin consultas."""

    alojadas = [persona for persona in personas if persona.egresado_en is None]
    cuantas = Counter(persona.dispositivo_id for persona in alojadas)
    lactantes_de = {persona.grupo_id: persona.lactantes for persona in alojadas}
    familias, lactantes = Counter(), Counter()
    for grupo, dispositivo in principales(alojadas).items():
        familias[dispositivo] += 1
        lactantes[dispositivo] += lactantes_de[grupo]
    return {
        dispositivo: Unidades(personas, familias[dispositivo], lactantes[dispositivo])
        for dispositivo, personas in cuantas.items()
    }


class Presencia(NamedTuple):
    """Un tramo ``[desde, hasta]`` en el que una persona o una familia estuvo en un dispositivo."""

    desde: datetime
    hasta: datetime
    peso: int = 1


def presencias(personas, ahora):
    """``{dispositivo_id: {"PERSONA": [...], "FAMILIA": [...], "LACTANTE": [...]}}``. Sin consultas.

    Cada persona, su estadía hasta su egreso o ``ahora``. Cada familia, en su dispositivo principal,
    desde el primer ingreso hasta el último egreso de sus integrantes **en ese dispositivo**; la de
    lactantes pesa lo que la familia declaró.
    """

    resultado = defaultdict(lambda: {Por.PERSONA: [], Por.FAMILIA: [], Por.LACTANTE: []})
    principal = principales(personas)
    familias = {}
    for persona in personas:
        hasta = persona.egresado_en or ahora
        resultado[persona.dispositivo_id][Por.PERSONA].append(Presencia(persona.ingreso, hasta))
        if principal[persona.grupo_id] != persona.dispositivo_id:
            continue
        desde_familia, hasta_familia, lactantes = familias.get(persona.grupo_id, (persona.ingreso, hasta, 0))
        familias[persona.grupo_id] = (
            min(desde_familia, persona.ingreso),
            max(hasta_familia, hasta),
            max(lactantes, persona.lactantes),
        )
    for grupo, (desde, hasta, lactantes) in familias.items():
        tramos = resultado[principal[grupo]]
        tramos[Por.FAMILIA].append(Presencia(desde, hasta))
        if lactantes:
            tramos[Por.LACTANTE].append(Presencia(desde, hasta, lactantes))
    return resultado


def unidades_dia(tramos, desde: datetime, ahora: datetime) -> float:
    """Las unidades-día de ``tramos`` recortados a ``[desde, ahora]`` (persona-días, familia-días…)."""

    total = 0.0
    for tramo in tramos:
        inicio, fin = max(tramo.desde, desde), min(tramo.hasta, ahora)
        if fin > inicio:
            total += tramo.peso * (fin - inicio).total_seconds() / 86400
    return total


def necesario_dotacion(unidades: int, cantidad, recibido: int) -> float:
    """Dotación: lo que falta para la gente de hoy. Lo recibido de más no se «devuelve» (TC-1187-23)."""

    return max(0.0, unidades * float(cantidad) - recibido)


def consumo_diario(unidades: int, cantidad, cada_dias: int) -> float:
    return unidades * float(cantidad) / cada_dias


def consumo_estimado(cantidad, cada_dias: int, unidades_dias: float) -> float:
    """Lo consumido desde la primera recepción: ``cantidad / cada_dias × unidades-día``."""

    return float(cantidad) / cada_dias * unidades_dias


def remanente(recibido: int, cantidad, cada_dias: int, unidades_dias: float) -> float:
    """Lo recibido que la regla todavía no da por consumido. Nunca negativo."""

    return max(0.0, recibido - consumo_estimado(cantidad, cada_dias, unidades_dias))


def necesario_reposicion(diario: float, remanente_: float, horas: int = HORAS_A_CUBRIR) -> float:
    """Reposición: el consumo de las próximas ``horas`` menos el remanente. Nunca negativo."""

    return max(0.0, diario * horas / HORAS_DEL_DIA - remanente_)


def faltan(necesario: int, en_camino: int, preparadas: int) -> int:
    """Lo que hay que mandar además de lo en camino y lo preparado (RN-009-18)."""

    return max(0, necesario - en_camino - preparadas)


class Cobertura(NamedTuple):
    """Hasta cuándo alcanza lo recibido **más lo en camino** de un ítem de reposición.

    ``horas`` es positiva si cubre (``hasta`` = ``ahora + horas``) y negativa si está sin cubrir
    desde hace ``-horas``; ``None`` sin consumo.
    """

    estado: str
    horas: float | None = None
    hasta: datetime | None = None


def cobertura(remanente_: float, diario: float, ahora: datetime, *, deficit: float = 0, en_camino: int = 0):
    """La cobertura de un ítem de reposición (RN-009-17), contando lo en camino (RN-009-20).

    Sin consumo diario no se calcula («—», TC-1187-24). Si lo recibido y lo en camino se acabaron,
    está sin cubrir desde hace ``déficit / consumo por hora``.
    """

    if diario <= 0:
        return Cobertura(SIN_CONSUMO)
    disponible = remanente_ + en_camino
    if disponible > 0:
        horas = disponible / diario * HORAS_DEL_DIA
        return Cobertura(CUBRE, horas, ahora + timedelta(hours=horas))
    return Cobertura(SIN_CUBRIR, -deficit / diario * HORAS_DEL_DIA)


def urgencia(nunca_recibio: bool, items) -> str:
    """Crítica o Exigida de un dispositivo sin cobertura 48 h (RN-009-20).

    **Crítica**: nunca recibió nada desde el inicio del evento; o alguno de los ítems que le faltan
    es una dotación, una reposición sin cubrir ahora aun contando lo en camino, o un ítem «por
    lactante» que nunca recibió con lactantes en el dispositivo (aunque tenga algo en camino: el texto
    de RN-009-20). **Exigida**: el resto (lo que le falta cubre algo, menos de 48 h). Solo miran los
    ítems con faltan > 0: lo preparado que tapa un ítem lo saca de la cuenta (§12: «… preparados»).
    """

    if nunca_recibio or any(item.critico for item in items if item.faltan):
        return NIVEL_CRITICA
    return NIVEL_EXIGIDA


def clave_de_orden(fila):
    """Crítica antes que Exigida; primero los que nunca recibieron; después la menor cobertura en
    horas de los ítems que faltan (nunca recibido = la menor, aun con algo en camino; dotación = 0 h;
    sin cubrir, negativa); a igual cobertura, más personas primero (RN-009-20)."""

    horas = [item.horas_para_ordenar for item in fila.items if item.faltan and item.horas_para_ordenar is not None]
    return (
        fila.urgencia != NIVEL_CRITICA,
        not fila.nunca_recibio,
        min(horas, default=math.inf),
        -fila.unidades.personas,
        fila.dispositivo.id,
    )


# ---------------------------------------------------------------------------
# Lo armado
# ---------------------------------------------------------------------------


class DispositivoDelAbastecimiento(NamedTuple):
    id: int
    nombre: str
    localidad: str
    reservado: bool
    #: ``Dispositivo.Estado``; vacío si no se pudo leer (no se ofrece «Preparar entrega»).
    estado: str

    @property
    def activo(self):
        return self.estado == Dispositivo.Estado.ACTIVO


#: Cómo se dice un dispositivo de ubicación reservada en la solapa (RN-009-13): sin nombre ni localidad.
RESERVADO = "Dispositivo de ubicación reservada"


def nombre_visible(dispositivo) -> str:
    """«Salón Parroquial · Charata», o :data:`RESERVADO` si es de ubicación reservada."""

    if dispositivo.reservado or not dispositivo.nombre:
        return RESERVADO
    return f"{dispositivo.nombre} · {dispositivo.localidad}" if dispositivo.localidad else dispositivo.nombre


class ItemDelDispositivo(NamedTuple):
    item: object
    necesario: int
    en_camino: int
    preparadas: int
    faltan: int
    nunca_recibido: bool
    #: ``None`` en dotación.
    cobertura: Cobertura | None
    #: Dotación con faltan, reposición sin cubrir ahora aun contando lo en camino, o un ítem por lactante nunca
    #: recibido con lactantes en el dispositivo (RN-009-20).
    critico: bool
    horas_para_ordenar: float | None


class FilaDispositivo(NamedTuple):
    dispositivo: DispositivoDelAbastecimiento
    unidades: Unidades
    ingresaron_hoy: int
    ultima_recepcion: datetime | None
    items: tuple
    urgencia: str = ""

    @property
    def nunca_recibio(self):
        return self.ultima_recepcion is None

    @property
    def sin_cobertura(self):
        return any(item.faltan for item in self.items)


class FilaItem(NamedTuple):
    item: object
    con_regla: bool
    necesario: int = 0
    en_camino: int = 0
    preparadas: int = 0
    faltan: int = 0


@dataclass(frozen=True)
class Salud:
    """La salud logística sin decidir qué se muestra (eso es :func:`presentar_salud`)."""

    sin_dosis: int
    #: ``((DispositivoDelAbastecimiento, personas sin dosis), ...)``
    sin_dosis_por_dispositivo: tuple
    #: ``((DispositivoDelAbastecimiento, lactantes declarados), ...)``, por nombre visible y después por id,
    #: nunca por conteo (RN-009-21 b).
    lactantes: tuple
    #: Los ítems con regla «por lactante» (sin ninguno no hay alerta de lactantes).
    items_de_lactantes: tuple


@dataclass(frozen=True)
class Abastecimiento:
    inicio_evento: datetime
    hay_reglas: bool
    con_gente: int
    sin_cobertura: int
    nunca_recibieron: int
    sin_entrega_48h: int
    personas_con_faltantes: int
    por_item: tuple
    #: Los sin cobertura 48 h, en el orden de :func:`clave_de_orden`.
    dispositivos: tuple
    salud: Salud
    items_con_regla: tuple

    @property
    def hay_alojados(self):
        return bool(self.con_gente)


def tiene_regla(item) -> bool:
    """Una regla completa (RN-009-15). Una a medias (cargada por fuera de E7) cuenta como «sin regla»:
    inventarle un consumo sería peor que no mostrarlo."""

    if not item.modo or item.cantidad is None or not item.por:
        return False
    return item.modo == Modo.DOTACION or bool(item.cada_dias)


def _item_del_dispositivo(item, unidades, tramos, recibido, en_camino, preparadas, ahora):
    cantidad_recibida = recibido.cantidad if recibido else 0
    u = unidades.de(item.por)
    if item.modo == Modo.DOTACION:
        necesario = redondear_hacia_arriba(necesario_dotacion(u, item.cantidad, cantidad_recibida))
        falta = faltan(necesario, en_camino, preparadas)
        horas = (NUNCA if recibido is None else 0.0) if falta else None
        return ItemDelDispositivo(
            item, necesario, en_camino, preparadas, falta, recibido is None, None, bool(falta), horas
        )

    diario = consumo_diario(u, item.cantidad, item.cada_dias)
    resto, deficit = 0.0, 0.0
    if recibido is not None:
        dias = unidades_dia(tramos[item.por], recibido.primera, ahora)
        consumido = consumo_estimado(item.cantidad, item.cada_dias, dias)
        resto = remanente(cantidad_recibida, item.cantidad, item.cada_dias, dias)
        deficit = max(0.0, consumido - cantidad_recibida)
    necesario = redondear_hacia_arriba(necesario_reposicion(diario, resto)) if u else 0
    cubre = cobertura(resto, diario, ahora, deficit=deficit, en_camino=en_camino)
    horas = None
    if cubre.estado != SIN_CONSUMO:
        horas = NUNCA if recibido is None else cubre.horas
    # RN-009-20: un ítem «por lactante» nunca recibido es Crítico aunque haya algo en camino.
    lactantes_sin_su_item = item.por == Por.LACTANTE and recibido is None and u > 0
    return ItemDelDispositivo(
        item,
        necesario,
        en_camino,
        preparadas,
        faltan(necesario, en_camino, preparadas),
        recibido is None,
        cubre,
        cubre.estado == SIN_CUBRIR or lactantes_sin_su_item,
        horas,
    )


def _dispositivos(ids, foto, lecturas):
    """``{id: DispositivoDelAbastecimiento}``: de la red de la foto, de A5 o, si no, de ``con_gente``."""

    resultado = {}
    for dispositivo in foto.red.dispositivos:
        resultado[dispositivo.id] = DispositivoDelAbastecimiento(
            dispositivo.id,
            dispositivo.nombre,
            dispositivo.localidad or "",
            bool(dispositivo.tipo.ubicacion_reservada),
            Dispositivo.Estado.ACTIVO,
        )
    for dispositivo in lecturas.fuera_de_la_red.values():
        resultado[dispositivo.id] = DispositivoDelAbastecimiento(
            dispositivo.id, dispositivo.nombre, dispositivo.localidad, dispositivo.reservado, dispositivo.estado
        )
    for dispositivo in foto.con_gente:
        resultado.setdefault(
            dispositivo.id,
            DispositivoDelAbastecimiento(
                dispositivo.id, dispositivo.nombre, dispositivo.localidad, dispositivo.reservado, ""
            ),
        )
    return {pk: resultado.get(pk) or DispositivoDelAbastecimiento(pk, "", "", True, "") for pk in ids}


def _por_nombre(par):
    """Las listas de salud van por nombre visible y después por id: nada del orden depende del conteo."""

    dispositivo, _cantidad = par
    return (nombre_visible(dispositivo).casefold(), dispositivo.id)


def _salud(total, sin, dispositivos, filas_por_id, items_de_lactantes):
    """B16: medicación crítica sin dosis por dispositivo (``sin``, de la foto: la misma lectura y la misma
    regla que AE-7) y lactantes sin el ítem de lactantes (nunca recibido o sin cubrir ahora aun contando
    lo en camino)."""

    # Nunca por conteo (RN-009-21 b): con 3 personas en 2 dispositivos, «el primero» diría quién tiene 2.
    por_dispositivo = tuple(sorted(((dispositivos[pk], n) for pk, n in sin.items()), key=_por_nombre))
    lactantes = []
    ids_de_lactantes = {item.id for item in items_de_lactantes}
    for fila in filas_por_id.values():
        if not fila.unidades.lactantes:
            continue
        sin_item = any(item.nunca_recibido or item.critico for item in fila.items if item.item.id in ids_de_lactantes)
        if sin_item:
            lactantes.append((fila.dispositivo, fila.unidades.lactantes))
    lactantes.sort(key=_por_nombre)
    return Salud(total, por_dispositivo, tuple(lactantes), tuple(items_de_lactantes))


def armar_abastecimiento(lecturas, foto, ahora: datetime) -> Abastecimiento:
    """Franja, tabla por ítem, dispositivos sin cobertura ordenados y salud. **0 consultas.**

    Todo provincial (los filtros de E8 no la acotan, RN-009-12). Solo los ítems activos (A1).
    """

    items_con_regla = tuple(item for item in lecturas.items if tiene_regla(item))
    unidades = unidades_de_hoy(lecturas.personas)
    tramos = presencias(lecturas.personas, ahora)
    sin = Counter(p.dispositivo_id for p in foto.alojados_ahora if p.dispositivo_id and sin_dosis(p.avisos_salud))
    dispositivos = _dispositivos(sorted(set(unidades) | set(sin)), foto, lecturas)
    ultima = {dispositivo.id: dispositivo.ultima_recepcion for dispositivo in foto.con_gente}
    inicio_del_dia, _fin = dia_operativo(ahora)
    hoy = Counter(p.dispositivo_id for p in lecturas.personas if p.egresado_en is None and p.ingreso >= inicio_del_dia)
    Est = EntregaKit.Estado

    filas = {}
    for pk, u in unidades.items():
        items = tuple(
            _item_del_dispositivo(
                item,
                u,
                tramos[pk],
                lecturas.recibido.get((pk, item.id)),
                lecturas.abiertas.get((pk, item.id, Est.EN_CAMINO), 0),
                lecturas.abiertas.get((pk, item.id, Est.PREPARADA), 0),
                ahora,
            )
            for item in items_con_regla
        )
        fila = FilaDispositivo(dispositivos[pk], u, hoy.get(pk, 0), ultima.get(pk), items)
        filas[pk] = fila._replace(urgencia=urgencia(fila.nunca_recibio, items) if fila.sin_cobertura else "")

    sin_cobertura = sorted((fila for fila in filas.values() if fila.sin_cobertura), key=clave_de_orden)
    por_item = []
    for n, item in enumerate(items_con_regla):
        de_cada = [fila.items[n] for fila in filas.values()]
        por_item.append(
            FilaItem(
                item,
                True,
                sum(i.necesario for i in de_cada),
                sum(i.en_camino for i in de_cada),
                sum(i.preparadas for i in de_cada),
                sum(i.faltan for i in de_cada),
            )
        )
    por_item.extend(FilaItem(item, False) for item in lecturas.items if not tiene_regla(item))

    items_de_lactantes = [item for item in items_con_regla if item.por == Por.LACTANTE]
    return Abastecimiento(
        inicio_evento=lecturas.inicio_evento,
        hay_reglas=bool(items_con_regla),
        con_gente=len(filas),
        sin_cobertura=len(sin_cobertura),
        nunca_recibieron=sum(1 for fila in filas.values() if fila.nunca_recibio),
        sin_entrega_48h=len(sin_entrega_reciente(foto)),
        personas_con_faltantes=sum(fila.unidades.personas for fila in sin_cobertura),
        por_item=tuple(por_item),
        dispositivos=tuple(sin_cobertura),
        salud=_salud(sin_dosis_provincial(foto), sin, dispositivos, filas, items_de_lactantes),
        items_con_regla=items_con_regla,
    )


# ---------------------------------------------------------------------------
# Qué se muestra de la salud (RN-009-21)
# ---------------------------------------------------------------------------

#: Desde cuántos lactantes un dispositivo se nombra con su número (RN-009-21 c).
MINIMO_LACTANTES_CON_NUMERO = 5


class SaludPresentada(NamedTuple):
    #: El total provincial exacto (AE-7 sin filtro) y en cuántos dispositivos.
    sin_dosis: int
    dispositivos: int
    #: ``False`` si el único dispositivo es de ubicación reservada: la línea no dice «en 1 dispositivo».
    decir_dispositivos: bool
    #: Los dispositivos nombrables, **sin número**, solo para quien opera la mesa y si el conteo no se deduce.
    nombres: tuple
    #: ``((dispositivo, lactantes o None), ...)``: el número solo desde 5; los reservados sin nombre.
    lactantes: tuple
    items_de_lactantes: tuple


def presentar_salud(salud: Salud, puede_operar: bool) -> SaludPresentada:
    """Qué de la salud logística se muestra según quién mira (RN-009-21). Sin consultas.

    (a) La línea agregada la ve todo el que ve E8. (b) Con ``operar`` o ``supervisar``, además los
    nombres sin número, salvo que el conteo se deduzca (un solo dispositivo, o tantas personas como
    dispositivos). (c) Lactantes: nombres para todos y el número solo desde 5. (d) Un dispositivo de
    ubicación reservada nunca se nombra; si es el único, la línea no dice «en 1 dispositivo».
    """

    por_dispositivo = salud.sin_dosis_por_dispositivo
    cantidad = len(por_dispositivo)
    deducible = cantidad <= 1 or salud.sin_dosis == cantidad
    nombres = ()
    if puede_operar and not deducible:
        nombres = tuple(dispositivo for dispositivo, _n in por_dispositivo if not dispositivo.reservado)
    solo_reservado = cantidad == 1 and por_dispositivo[0][0].reservado
    lactantes = tuple(
        (dispositivo, n if n >= MINIMO_LACTANTES_CON_NUMERO and not dispositivo.reservado else None)
        for dispositivo, n in salud.lactantes
    )
    return SaludPresentada(salud.sin_dosis, cantidad, not solo_reservado, nombres, lactantes, salud.items_de_lactantes)
