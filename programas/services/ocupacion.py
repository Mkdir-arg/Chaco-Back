"""Cálculo único de ocupación, disponibilidad y censo de plazas (MVP v2, etapas 1 y 2 · #687, #689).

**Esta es la única fuente.** El mapa de plazas, el detalle del dispositivo, el censo y
los indicadores salen todos de :func:`ocupacion_de_plazas`; ninguno vuelve a contar por
su cuenta. Si cada pantalla deriva por su lado se desincronizan, que es exactamente lo
que el recorte de ``Plaza.estado`` evita en la base: la plaza guarda su estado
*operativo* —lo único que alguien decide— y todo lo demás se deriva acá.

Las cifras
----------

* ``totales`` — las plazas cargadas en los sectores activos.
* ``fuera_de_servicio`` — las que están en ``Plaza.Estado.FUERA_SERVICIO``.
* ``operativas`` — ``totales - fuera_de_servicio``.
* ``ocupadas`` — las plazas operativas con una estadía activa.
* ``reservadas`` — las plazas operativas sin estadía activa y con una reserva o un
  préstamo vigente.
* ``prestadas`` — el subconjunto de ``reservadas`` con préstamo vigente;
  ``reservadas_sin_prestamo`` es la diferencia. El agregado se conserva para P4.
* ``disponibles`` — ``operativas - ocupadas - reservadas``.

Cada plaza se cuenta **una sola vez**, en el estado que le resuelve
:func:`estado_de_plazas` con su precedencia —fuera de servicio, ocupada, reservada o
prestada, disponible—. Las dos cuentas filtran con los mismos querysets
(:func:`_estadias_que_ocupan` y :func:`_reservas_que_cuentan`), así que el encabezado y
las celdas del mapa no pueden decir cosas distintas.

Lo que se recibe y lo que se deriva (y qué significa ``None``)
--------------------------------------------------------------

La etapa 2 (#689) trajo ``Estadia`` y ``ReservaPlaza``, así que ``ocupadas`` y
``reservadas`` **ya se calculan** y ``disponibles`` sale sola de las dos. La forma
pública de la etapa 1 no cambió ni una letra: ``operativas`` y ``disponibles`` siempre
fueron propiedades derivadas, no campos, y por eso completar las cifras **no tocó
ninguna pantalla**.

Lo que **sí** se conserva es la distinción entre no saber y saber que no hay. Un
:class:`Conteo` armado a mano sin esas cifras —no el que devuelve este servicio, que las
llena siempre— las deja en ``None``, nunca en ``0``: ``0`` significa «no hay ninguna
ocupada» y es una afirmación sobre el mundo; ``None`` significa «este sistema todavía no
lo sabe». Una pantalla que recibiera ``0`` mostraría un dispositivo entero libre —y
mandaría a alojar gente sobre plazas tomadas— sin que nada fallara. Con ``None``:

* en Python, cualquier aritmética explota (``TypeError``) en vez de mentir;
* en un template, ``{{ conteo.ocupadas }}`` escribe ``None``, que se ve mal **a
  propósito**: una clave ausente se renderizaría como cadena vacía, indistinguible de un
  dato legítimo, y ese es justamente el fallo silencioso que se quiere evitar;
* :attr:`Conteo.pendientes` y :attr:`Conteo.completo` permiten preguntarlo sin adivinar.

Esa red sigue puesta para el que sume una cifra nueva mañana, y para el que sume un
:class:`Conteo` calculado con uno que no lo está: ``pendiente + lo que sea = pendiente``.

Invariantes que el cálculo sostiene
-----------------------------------

* ``OcupacionDispositivo.conteo`` es **exactamente** la suma de sus ``sectores``: nadie
  puede mirar el desglose y el total y encontrar dos números distintos.
* Se cuentan **solo los sectores activos**, y por eso un sector dado de baja desaparece
  de todo el cálculo, total y desglose a la vez. La contracara es que dar de baja un
  sector con plazas vivas evaporaría capacidad en silencio: esa regla —que la baja falle
  si el sector tiene plazas— le toca al servicio de baja de sector, que todavía no
  existe.
* ``FUERA_SERVICIO``, ocupada y reservada son mutuamente excluyentes **por regla de
  negocio, no por constraint**: sacar de servicio una plaza tomada falla y primero se
  reubica, y ni una estadía ni una reserva se dan sobre una plaza que ya tiene algo
  (`programas.services.estadias`, con la fila de la plaza bloqueada). Como el modelo no
  lo impide, el conteo **no confía en esa regla**: aplica la precedencia, y por
  construcción ``ocupadas + reservadas <= operativas`` y ``disponibles >= 0`` aunque
  alguien escriba por afuera. Una superposición así se ve en el mapa como el estado que
  gana, igual que en el encabezado.
* Todo el cálculo se hace sobre **un mismo instante** (``momento``): la vigencia de una
  reserva es por tiempo, y dos consultas con dos «ahora» distintos podrían discrepar.

Costo
-----

**Tres consultas** —las plazas por sector, las estadías activas por sector y las
reservas vigentes por sector (la exclusión de las plazas ocupadas va como subconsulta
``NOT EXISTS`` adentro de esa misma consulta)— más, a lo sumo, la que evalúe el queryset de dispositivos
que reciba. Son tres fijas: no crecen con la cantidad de sectores, de plazas ni de
dispositivos, y cada una devuelve una fila por sector.

Por qué tres y no una, que era el presupuesto de la etapa 1: meter las estadías en la
misma agregación significa encadenar ``sector → plaza → estadia`` en un solo ``LEFT
JOIN``, y Django pone el filtro del ``Count`` adentro de un ``CASE``, no en el ``ON``.
El motor materializaría una fila por **cada estadía histórica** de cada plaza —un
conjunto que crece para siempre, mientras que el de las plazas es fijo— para después
descartarlas casi todas. Tres consultas acotadas a lo vigente son ``O(sectores)``
siempre; una sola sería ``O(estadías de toda la vida)``.

Acá no se agrupa por tiempo y por lo tanto **no hay ningún ``Trunc*``**: la base de ECOM
no tiene tablas de zona horaria, Django traduce ``Trunc*`` sobre un ``DateTimeField`` a
``CONVERT_TZ``, devuelve ``NULL`` y rompe solo en producción. El censo por turno de la
etapa 3 (`programas.services.censo`) agrupa en Python.

Alojada en un instante
----------------------

El censo (#696) necesita la existencia en instantes pasados —al inicio y al fin de cada
turno—, que no es la foto de ahora. La regla vive acá y no allá, para que «alojada» se
decida en un solo lugar: :func:`alojada_en` (ingresó **antes** del instante y no egresó
antes de él) y :func:`estadias_alojadas_entre`, la consulta que trae las estadías
candidatas de un rango. Para el instante presente coincide con ``Estadia.objects.activas()``.
"""

from dataclasses import dataclass

from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone

from programas.models import Dispositivo, Estadia, Plaza, ReservaPlaza, Sector

#: Las cifras que no salen de las plazas: las dos que se reciben de los movimientos
#: (``Estadia`` y ``ReservaPlaza``) y la que se deriva de ellas.
CIFRAS_DE_MOVIMIENTOS = ("ocupadas", "reservadas", "disponibles")


def _sumar(uno, otro):
    """Suma dos cifras que pueden estar pendientes: pendiente + lo que sea = pendiente."""

    if uno is None or otro is None:
        return None
    return uno + otro


@dataclass(frozen=True)
class Conteo:
    """Las cifras de un ámbito —una plaza, un sector, un dispositivo o toda la red—.

    ``ocupadas`` y ``reservadas`` se reciben; ``operativas`` y ``disponibles`` se derivan
    y por eso no pueden quedar desalineadas con ellas. ``prestadas`` desglosa el agregado
    sin cambiar esa aritmética ni la completitud de las cifras originales.
    """

    totales: int = 0
    fuera_de_servicio: int = 0
    #: Plazas con estadía activa. ``None`` solo en un conteo armado a mano: ver el módulo.
    ocupadas: int | None = None
    #: Plazas con reserva o préstamo vigente. ``None`` solo en un conteo armado a mano.
    reservadas: int | None = None
    #: Desglose del agregado; un conteo manual sin desglose lo deja pendiente.
    prestadas: int | None = None

    @property
    def reservadas_sin_prestamo(self) -> int | None:
        if self.reservadas is None or self.prestadas is None:
            return None
        return self.reservadas - self.prestadas

    @property
    def operativas(self) -> int:
        return self.totales - self.fuera_de_servicio

    @property
    def disponibles(self) -> int | None:
        if self.ocupadas is None or self.reservadas is None:
            return None
        return self.operativas - self.ocupadas - self.reservadas

    @property
    def pendientes(self) -> tuple[str, ...]:
        """Qué claves todavía no se pueden calcular, en el orden del tablero."""

        return tuple(clave for clave in CIFRAS_DE_MOVIMIENTOS if getattr(self, clave) is None)

    @property
    def completo(self) -> bool:
        return not self.pendientes

    def __add__(self, otro):
        if not isinstance(otro, Conteo):
            return NotImplemented
        return Conteo(
            totales=self.totales + otro.totales,
            fuera_de_servicio=self.fuera_de_servicio + otro.fuera_de_servicio,
            ocupadas=_sumar(self.ocupadas, otro.ocupadas),
            reservadas=_sumar(self.reservadas, otro.reservadas),
            prestadas=_sumar(self.prestadas, otro.prestadas),
        )


def _sumar_conteos(conteos) -> Conteo:
    """Suma una colección de conteos. La colección vacía da todo en cero, nada pendiente.

    Cero y no pendiente porque la colección vacía es un ámbito **sin plazas** —un
    dispositivo sin sectores, o un censo al que no se le pidió ningún dispositivo—, y un
    ámbito sin plazas no tiene plazas tomadas. Eso se sabe; no es el caso de un
    :class:`Conteo` armado a mano al que le falta la cifra.
    """

    total = Conteo(ocupadas=0, reservadas=0, prestadas=0)
    for conteo in conteos:
        total = total + conteo
    return total


@dataclass(frozen=True)
class OcupacionSector:
    """Un sector activo con sus cifras.

    ``capacidad_declarada`` es la del legajo —el papel—, no la real: viaja acá para que
    la pantalla pueda contrastarla con ``conteo.totales`` sin una segunda consulta.
    """

    sector_id: int
    dispositivo_id: int
    nombre: str
    tipo: str
    capacidad_declarada: int
    conteo: Conteo


@dataclass(frozen=True)
class OcupacionDispositivo:
    """Un dispositivo con sus cifras y el desglose por sector.

    ``conteo`` es la suma exacta de ``sectores``; un dispositivo sin sectores, o con
    sectores sin plazas, llega igual con todo en cero.
    """

    dispositivo_id: int
    conteo: Conteo
    sectores: tuple[OcupacionSector, ...]


@dataclass(frozen=True)
class Censo:
    """El resultado de :func:`ocupacion_de_plazas` para los dispositivos pedidos."""

    por_dispositivo: dict[int, OcupacionDispositivo]
    #: La suma de todos los dispositivos pedidos: la franja de indicadores de la red.
    total: Conteo

    def de(self, dispositivo) -> OcupacionDispositivo:
        """El dispositivo pedido. Levanta ``KeyError`` si no estaba en la consulta.

        A propósito: devolver un cero para algo que nunca se consultó es la misma mentira
        que devolver un cero para algo que todavía no se puede calcular.
        """

        return self.por_dispositivo[_id_de(dispositivo)]


def _id_de(dispositivo) -> int:
    if isinstance(dispositivo, Dispositivo):
        if dispositivo.pk is None:
            raise ValueError("No se puede calcular la ocupación de un dispositivo sin guardar.")
        return dispositivo.pk
    return int(dispositivo)


def _ids_de(dispositivos) -> list[int]:
    """Acepta un dispositivo, un id, o cualquier iterable de unos u otros."""

    # `str` entra como escalar a propósito: una cadena es iterable, y sin esto un id que
    # llega de la URL como "3" se recorrería carácter por carácter.
    if isinstance(dispositivos, (Dispositivo, int, str)):
        candidatos = [dispositivos]
    else:
        candidatos = dispositivos
    ids: list[int] = []
    vistos: set[int] = set()
    for candidato in candidatos:
        pk = _id_de(candidato)
        if pk not in vistos:
            vistos.add(pk)
            ids.append(pk)
    return ids


def _por_sector(filas):
    """``{sector_id: cuántas}`` a partir de una agregación que ya viene agrupada."""

    return {fila["plaza__sector_id"]: fila["cuantas"] for fila in filas}


def alojada_en(fecha_ingreso, fecha_egreso, momento) -> bool:
    """Si una estadía con esas fechas tenía a la persona alojada en ``momento``.

    Ingresó **antes** del instante y no había egresado: ``fecha_ingreso < momento`` y
    (``fecha_egreso`` vacía o ``>= momento``). Es la frontera ``[inicio, fin)`` del censo
    vista desde la existencia: quien ingresa justo en el inicio de un turno es un ingreso
    de ese turno y no parte de su existencia inicial; quien egresa justo en el inicio
    estaba al empezar y es un egreso de ese turno.
    """

    return fecha_ingreso < momento and (fecha_egreso is None or fecha_egreso >= momento)


def estadias_alojadas_entre(dispositivo, desde, hasta):
    """``(fecha_ingreso, fecha_egreso)`` de las estadías alojadas en algún instante de ``[desde, hasta]``.

    Es el universo sobre el que :func:`alojada_en` se evalúa en Python para cualquier
    instante del rango: una consulta para todo el rango y no una por instante. Filtra
    solo por fechas, sin ``Trunc*``. ``dispositivo`` es la instancia o su id.
    """

    return (
        Estadia.objects.filter(dispositivo_id=getattr(dispositivo, "pk", dispositivo), fecha_ingreso__lt=hasta)
        .filter(Q(fecha_egreso__isnull=True) | Q(fecha_egreso__gte=desde))
        .order_by()
        .values_list("fecha_ingreso", "fecha_egreso")
    )


def _estadias_que_ocupan():
    """Las estadías que hacen «ocupada» a su plaza: activas, en una plaza que no está fuera de servicio.

    Fuera de servicio gana: es la primera regla de la precedencia de :func:`estado_de_plazas`.
    """

    return Estadia.objects.activas().exclude(plaza__estado=Plaza.Estado.FUERA_SERVICIO)


def _reservas_que_cuentan(momento):
    """Las reservas que hacen «reservada» o «prestada» a su plaza.

    Vigentes en ``momento``, en una plaza que no está fuera de servicio y **sin** una
    estadía activa: ocupada gana sobre reservada. Así una plaza ocupada y reservada a la
    vez —que el servicio de estadías no deja escribir, pero el modelo sí— se cuenta una
    sola vez, como ocupada, que es como la dibuja el mapa.
    """

    ocupada = Estadia.objects.activas().filter(plaza_id=OuterRef("plaza_id"))
    return (
        ReservaPlaza.objects.vigentes(momento)
        .exclude(plaza__estado=Plaza.Estado.FUERA_SERVICIO)
        .exclude(Exists(ocupada))
    )


def _ocupadas_por_sector(sector_ids):
    """Plazas ocupadas (:func:`_estadias_que_ocupan`), por sector. Una consulta, una fila por sector.

    Se filtra por los sectores que ya se conocen y no por el dispositivo: así el JOIN es
    ``estadia → plaza`` y no ``estadia → plaza → sector → dispositivo``.

    ``distinct`` sobre la plaza, no sobre la estadía: lo que se cuenta son plazas
    tomadas. Que dos estadías activas compartan plaza no puede pasar —lo impide el
    bloqueo de `programas.services.estadias`— pero si pasara, contarlas dos veces
    escondería el problema detrás de un número que cierra.
    """

    return _por_sector(
        _estadias_que_ocupan()
        .filter(plaza__sector_id__in=sector_ids)
        .values("plaza__sector_id")
        .annotate(cuantas=Count("plaza_id", distinct=True))
    )


def _reservadas_por_sector(sector_ids, momento):
    """Plazas reservadas o prestadas (:func:`_reservas_que_cuentan`), por sector.

    La vigencia la define `ReservaPlaza.objects.vigentes()` y no se repite acá: es por
    tiempo, sin cron que apague nada, y sin ningún ``Trunc*``.
    Devuelve ``{sector_id: (total_reservadas_o_prestadas, prestadas)}`` en la misma consulta.
    """

    return {
        fila["plaza__sector_id"]: (fila["cuantas"], fila["prestadas"])
        for fila in _reservas_que_cuentan(momento)
        .filter(plaza__sector_id__in=sector_ids)
        .values("plaza__sector_id")
        .annotate(
            cuantas=Count("plaza_id", distinct=True),
            prestadas=Count("plaza_id", filter=Q(tipo=ReservaPlaza.Tipo.PRESTAMO), distinct=True),
        )
    }


def ocupacion_de_plazas(dispositivos, momento=None) -> Censo:
    """Las cifras de plazas de ``dispositivos`` en ``momento`` (por defecto, ahora), en tres consultas fijas.

    ``dispositivos`` puede ser un :class:`~programas.models.Dispositivo`, su id, o
    cualquier iterable de unos u otros (incluido un queryset, que entonces se evalúa).
    Los dispositivos sin sectores aparecen igual, en cero.

    Devuelve las cinco cifras completas: las plazas dan ``totales`` y
    ``fuera_de_servicio``, las estadías activas dan ``ocupadas``, las reservas vigentes
    dan ``reservadas``, y ``operativas`` y ``disponibles`` se derivan. Ver el docstring
    del módulo para el porqué de cada consulta y de los ``None`` que siguen existiendo.
    """

    ids = _ids_de(dispositivos)
    momento = momento or timezone.now()
    sectores_por_dispositivo: dict[int, list[OcupacionSector]] = {pk: [] for pk in ids}

    if ids:
        filas = (
            Sector.objects.filter(dispositivo_id__in=ids, activo=True)
            .values("id", "dispositivo_id", "nombre", "tipo", "capacidad")
            # Un `Count` con `filter` por cada cifra sobre el **mismo** LEFT JOIN: el
            # motor recorre las plazas una vez y agrupa. Contar sector por sector sería
            # una consulta por sector, que es justo lo que los índices
            # `(dispositivo, activo)` y `(sector, estado)` están puestos para evitar.
            .annotate(
                plazas_totales=Count("plazas"),
                plazas_fuera_de_servicio=Count("plazas", filter=Q(plazas__estado=Plaza.Estado.FUERA_SERVICIO)),
            )
            # Explícito y no por `Meta.ordering`: este queryset agrupa, y el orden tiene
            # que salir de columnas que ya están en el `values()` para no encadenar un
            # JOIN de más hacia `Dispositivo`.
            .order_by("dispositivo_id", "nombre")
        )
        # Se materializa acá —y no se recorre perezosamente— porque las dos consultas de
        # movimientos necesitan los ids de los sectores antes de armar los conteos.
        filas = list(filas)
        sector_ids = [fila["id"] for fila in filas]
        ocupadas = _ocupadas_por_sector(sector_ids) if sector_ids else {}
        reservadas = _reservadas_por_sector(sector_ids, momento) if sector_ids else {}
        for fila in filas:
            sectores_por_dispositivo[fila["dispositivo_id"]].append(
                OcupacionSector(
                    sector_id=fila["id"],
                    dispositivo_id=fila["dispositivo_id"],
                    nombre=fila["nombre"],
                    tipo=fila["tipo"],
                    capacidad_declarada=fila["capacidad"],
                    conteo=Conteo(
                        totales=fila["plazas_totales"],
                        fuera_de_servicio=fila["plazas_fuera_de_servicio"],
                        # Cero y no `None`: acá sí se sabe. Un sector sin estadías no
                        # aparece en la agregación porque no tiene filas que agrupar, no
                        # porque falte el dato.
                        ocupadas=ocupadas.get(fila["id"], 0),
                        reservadas=reservadas.get(fila["id"], (0, 0))[0],
                        prestadas=reservadas.get(fila["id"], (0, 0))[1],
                    ),
                )
            )

    por_dispositivo = {
        pk: OcupacionDispositivo(
            dispositivo_id=pk,
            conteo=_sumar_conteos(sector.conteo for sector in sectores),
            sectores=tuple(sectores),
        )
        for pk, sectores in sectores_por_dispositivo.items()
    }

    return Censo(
        por_dispositivo=por_dispositivo,
        total=_sumar_conteos(ocupacion.conteo for ocupacion in por_dispositivo.values()),
    )


# ---------------------------------------------------------------------------------------
# El estado de cada plaza
# ---------------------------------------------------------------------------------------
#
# Misma fuente para todas las pantallas que dibujan plazas («Sectores y plazas» e ingreso):
# si cada una decidiera por su lado qué es «ocupada», la misma plaza saldría en dos estados
# distintos. El texto y el tono viajan juntos y la leyenda sale de la misma tabla.

ESTADO_DISPONIBLE = "Disponible"
ESTADO_OCUPADA = "Ocupada"
ESTADO_RESERVADA = "Reservada"
ESTADO_PRESTADA = "Prestada"
ESTADO_FUERA_SERVICIO = "Fuera de serv."

#: Estados del mapa con su tono (los de `components/_mapa_plazas.html`), en orden de leyenda.
LEYENDA_PLAZAS = [
    {"estado": ESTADO_DISPONIBLE, "tono": "success"},
    {"estado": ESTADO_OCUPADA, "tono": "info"},
    {"estado": ESTADO_RESERVADA, "tono": "warning"},
    {"estado": ESTADO_PRESTADA, "tono": "brand"},
    {"estado": ESTADO_FUERA_SERVICIO, "tono": "danger"},
]
_TONO_DE = {item["estado"]: item["tono"] for item in LEYENDA_PLAZAS}


@dataclass(frozen=True)
class EstadoPlaza:
    """Cómo se ve una plaza ahora mismo. `disponible` es lo único que habilita alojar en ella."""

    estado: str
    tono: str
    detalle: str = ""
    detalle_completo: str = ""

    @property
    def disponible(self) -> bool:
        return self.estado == ESTADO_DISPONIBLE


def estado_de_plazas(plazas, momento=None, *, puede_ver_personas=False) -> dict[int, EstadoPlaza]:
    """`{plaza_id: EstadoPlaza}` derivado de `Plaza.estado`, las estadías y las reservas.

    ``plazas`` son instancias de `Plaza` (hace falta `estado` y `motivo_fuera_servicio`).
    Dos consultas fijas, sin importar cuántas plazas: las estadías activas y las reservas
    vigentes de esas plazas. Precedencia: fuera de servicio, ocupada, prestada o reservada,
    disponible; las tres primeras son excluyentes por regla de negocio, no por constraint.
    Las consultas son las mismas que cuenta :func:`ocupacion_de_plazas`, así que la celda y
    el encabezado resuelven igual una plaza que tenga dos cosas a la vez.
    Los nombres viajan en esas mismas consultas, nunca una por plaza. La vista resuelve
    ``puede_ver_personas`` con ``ciudadano.ver``; por defecto no se exponen identidades.
    """

    plazas = list(plazas)
    ids = [plaza.pk for plaza in plazas]
    momento = momento or timezone.now()
    ocupadas = {
        pk: (apellido, nombre)
        for pk, apellido, nombre in _estadias_que_ocupan()
        .filter(plaza_id__in=ids)
        .values_list("plaza_id", "ciudadano__apellido", "ciudadano__nombre")
    }
    reservas = {
        pk: (tipo, apellido, nombre, hasta)
        for pk, tipo, apellido, nombre, hasta in _reservas_que_cuentan(momento)
        .filter(plaza_id__in=ids)
        .values_list("plaza_id", "tipo", "ciudadano__apellido", "ciudadano__nombre", "hasta")
    }

    derivados = {}
    for plaza in plazas:
        detalle = ""
        detalle_completo = ""
        if plaza.estado == Plaza.Estado.FUERA_SERVICIO:
            estado, detalle = ESTADO_FUERA_SERVICIO, plaza.motivo_fuera_servicio
        elif plaza.pk in ocupadas:
            estado = ESTADO_OCUPADA
            detalle = _nombre_en_plaza(*ocupadas[plaza.pk]) if puede_ver_personas else ""
        elif plaza.pk in reservas:
            tipo, apellido, nombre, hasta = reservas[plaza.pk]
            prestada = tipo == ReservaPlaza.Tipo.PRESTAMO
            estado = ESTADO_PRESTADA if prestada else ESTADO_RESERVADA
            persona = _nombre_en_plaza(apellido, nombre) if puede_ver_personas else ""
            vencimiento = f"hasta {timezone.localtime(hasta):%d/%m %H:%M}" if hasta else "sin vencimiento"
            detalle = f"{persona} · {vencimiento}" if persona else vencimiento
            vencimiento_completo = f"hasta {timezone.localtime(hasta):%d/%m/%Y %H:%M}" if hasta else "sin vencimiento"
            detalle_completo = f"{persona} · {vencimiento_completo}" if persona else vencimiento_completo
        else:
            estado = ESTADO_DISPONIBLE
        derivados[plaza.pk] = EstadoPlaza(
            estado=estado, tono=_TONO_DE[estado], detalle=detalle, detalle_completo=detalle_completo or detalle
        )
    return derivados


def _nombre_en_plaza(apellido, nombre):
    """Identidad abreviada del mapa, sin DNI ni otros datos del legajo."""

    inicial = nombre.strip()[:1]
    return f"{apellido}, {inicial}." if inicial else apellido


# ---------------------------------------------------------------------------------------
# Cómo se lee la ocupación en una fila de listado
# ---------------------------------------------------------------------------------------
#
# P2 (y P1) muestran la ocupación de cada institución como «ocupadas / operativas» con un
# badge de color. El umbral y el tono se deciden **acá**, una sola vez, y no en cada
# template: el mapeo de una cifra a un color es del dominio, no de la pantalla
# (`.claude/design/componentes/tabla.md`). El vocabulario —normal, exigida, crítica— es el
# del mockup, que nombra la situación y no el color.

#: Desde este porcentaje de plazas operativas ocupadas la fila se lee como crítica.
UMBRAL_CRITICA = 80
#: Desde este porcentaje, exigida. Por debajo, normal.
UMBRAL_EXIGIDA = 60

NIVEL_SIN_PLAZAS = "sin_plazas"
NIVEL_NORMAL = "normal"
NIVEL_EXIGIDA = "exigida"
NIVEL_CRITICA = "critica"

_TENSION = {
    NIVEL_SIN_PLAZAS: ("Sin plazas", "gray"),
    NIVEL_NORMAL: ("Normal", "success"),
    NIVEL_EXIGIDA: ("Exigida", "warning"),
    NIVEL_CRITICA: ("Crítica", "danger"),
}


@dataclass(frozen=True)
class Tension:
    """La ocupación de un ámbito tal como la dibuja una fila de listado.

    ``porcentaje`` es ``None`` cuando no hay nada sobre lo que calcularlo: sin plazas
    operativas no hay un 0 % que informar —no es que esté vacío, es que no tiene plazas—,
    y la fila dice «sin plazas» en vez de un número que invitaría a mandar gente ahí.
    """

    ocupadas: int | None
    operativas: int
    porcentaje: int | None
    nivel: str

    @property
    def texto(self) -> str:
        """Lo que va en la celda: «37 / 42», o el motivo por el que no hay cifra."""

        if self.porcentaje is None:
            return "sin plazas"
        return f"{self.ocupadas} / {self.operativas}"

    @property
    def etiqueta(self) -> str:
        """Cómo se nombra la situación («Crítica»), para el `aria-label` y las pantallas que no muestran el %."""

        return _TENSION[self.nivel][0]

    @property
    def tono(self) -> str:
        """Variante de badge de `nodo-badges.css` (`badge badge-{{ tono }}`)."""

        return _TENSION[self.nivel][1]

    @property
    def hay_cifra(self) -> bool:
        return self.porcentaje is not None


def tension_de_ocupacion(conteo: Conteo, *, tipo=None) -> Tension:
    """Cómo se lee el ``Conteo`` de un ámbito en una fila: cifras, porcentaje, nivel y tono.

    Sin plazas operativas —o sin saber cuántas están ocupadas, que es el ``None`` que el
    módulo se cuida de no confundir con cero— no hay porcentaje y el nivel es
    ``sin_plazas``: una institución recién cargada no es una institución vacía.

    P2 y P4 pasan el tipo para usar sus umbrales configurados. Sin tipo (por ejemplo,
    una cifra agregada de red) se conserva el corte general de 60/80.
    """

    operativas = conteo.operativas
    ocupadas = conteo.ocupadas
    if operativas <= 0 or ocupadas is None:
        return Tension(ocupadas=ocupadas, operativas=max(operativas, 0), porcentaje=None, nivel=NIVEL_SIN_PLAZAS)
    porcentaje = round(ocupadas * 100 / operativas)
    amarillo = tipo.umbral_ocupacion_amarillo if tipo is not None else UMBRAL_EXIGIDA
    rojo = tipo.umbral_ocupacion_rojo if tipo is not None else UMBRAL_CRITICA
    if porcentaje >= rojo:
        nivel = NIVEL_CRITICA
    elif porcentaje >= amarillo:
        nivel = NIVEL_EXIGIDA
    else:
        nivel = NIVEL_NORMAL
    return Tension(ocupadas=ocupadas, operativas=operativas, porcentaje=porcentaje, nivel=nivel)
