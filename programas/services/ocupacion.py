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
* ``ocupadas`` — las plazas con una estadía activa.
* ``reservadas`` — las plazas con una reserva o un préstamo vigente.
* ``disponibles`` — ``operativas - ocupadas - reservadas``.

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
  (`programas.services.estadias`, con la fila de la plaza bloqueada). De ahí sale
  ``ocupadas + reservadas <= operativas``, y por lo tanto ``disponibles >= 0``. Es una
  invariante del servicio de escritura: si alguien escribe por afuera, acá se va a ver
  —un ``disponibles`` negativo—, que es exactamente lo que se quiere que pase.

Costo
-----

**Tres consultas** —las plazas por sector, las estadías activas por sector y las
reservas vigentes por sector— más, a lo sumo, la que evalúe el queryset de dispositivos
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
``CONVERT_TZ``, devuelve ``NULL`` y rompe solo en producción. Cuando la etapa 3 sume el
censo por turno sobre fechas, el agrupamiento va en Python (precedente:
``programas/services/dashboard_becas.py``).
"""

from dataclasses import dataclass

from django.db.models import Count, Q

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
    y por eso no pueden quedar desalineadas con ellas.
    """

    totales: int = 0
    fuera_de_servicio: int = 0
    #: Plazas con estadía activa. ``None`` solo en un conteo armado a mano: ver el módulo.
    ocupadas: int | None = None
    #: Plazas con reserva o préstamo vigente. ``None`` solo en un conteo armado a mano.
    reservadas: int | None = None

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
        )


def _sumar_conteos(conteos) -> Conteo:
    """Suma una colección de conteos. La colección vacía da todo en cero, nada pendiente.

    Cero y no pendiente porque la colección vacía es un ámbito **sin plazas** —un
    dispositivo sin sectores, o un censo al que no se le pidió ningún dispositivo—, y un
    ámbito sin plazas no tiene plazas tomadas. Eso se sabe; no es el caso de un
    :class:`Conteo` armado a mano al que le falta la cifra.
    """

    total = Conteo(ocupadas=0, reservadas=0)
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


def _ocupadas_por_sector(sector_ids):
    """Plazas con estadía activa, por sector. Una consulta, una fila por sector.

    Se filtra por los sectores que ya se conocen y no por el dispositivo: así el JOIN es
    ``estadia → plaza`` y no ``estadia → plaza → sector → dispositivo``.

    ``distinct`` sobre la plaza, no sobre la estadía: lo que se cuenta son plazas
    tomadas. Que dos estadías activas compartan plaza no puede pasar —lo impide el
    bloqueo de `programas.services.estadias`— pero si pasara, contarlas dos veces
    escondería el problema detrás de un número que cierra.
    """

    return _por_sector(
        Estadia.objects.filter(estado=Estadia.Estado.ACTIVA, plaza__sector_id__in=sector_ids)
        .values("plaza__sector_id")
        .annotate(cuantas=Count("plaza_id", distinct=True))
    )


def _reservadas_por_sector(sector_ids):
    """Plazas con reserva o préstamo vigente, por sector.

    La vigencia la define `ReservaPlaza.objects.vigentes()` y no se repite acá: es por
    tiempo, sin cron que apague nada, y sin ningún ``Trunc*``.
    """

    return _por_sector(
        ReservaPlaza.objects.vigentes()
        .filter(plaza__sector_id__in=sector_ids)
        .values("plaza__sector_id")
        .annotate(cuantas=Count("plaza_id", distinct=True))
    )


def ocupacion_de_plazas(dispositivos) -> Censo:
    """Las cifras de plazas de ``dispositivos``, en tres consultas fijas.

    ``dispositivos`` puede ser un :class:`~programas.models.Dispositivo`, su id, o
    cualquier iterable de unos u otros (incluido un queryset, que entonces se evalúa).
    Los dispositivos sin sectores aparecen igual, en cero.

    Devuelve las cinco cifras completas: las plazas dan ``totales`` y
    ``fuera_de_servicio``, las estadías activas dan ``ocupadas``, las reservas vigentes
    dan ``reservadas``, y ``operativas`` y ``disponibles`` se derivan. Ver el docstring
    del módulo para el porqué de cada consulta y de los ``None`` que siguen existiendo.
    """

    ids = _ids_de(dispositivos)
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
        reservadas = _reservadas_por_sector(sector_ids) if sector_ids else {}
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
                        reservadas=reservadas.get(fila["id"], 0),
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
