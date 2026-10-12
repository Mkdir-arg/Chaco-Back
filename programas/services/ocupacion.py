"""Cálculo único de ocupación, disponibilidad y censo de plazas (MVP v2, etapa 1 · #687).

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
* ``ocupadas`` — las estadías activas con plaza. **Etapa 2.**
* ``reservadas`` — las reservas y los préstamos vigentes. **Etapa 2.**
* ``disponibles`` — ``operativas - ocupadas - reservadas``. **Etapa 2.**

Qué falta y de dónde viene
--------------------------

``ocupadas`` y ``reservadas`` **no se pueden calcular hoy**: salen de ``Estadia`` y de
``ReservaPlaza``, dos modelos que la **etapa 2** (ingreso y egreso) todavía no creó. Y
``disponibles`` se deriva de las dos, así que tampoco.

Esas tres claves valen ``None``, nunca ``0``. La distinción no es cosmética: ``0``
significa «no hay ninguna ocupada» y es una afirmación sobre el mundo; ``None`` significa
«este sistema todavía no lo sabe». Una pantalla que recibiera ``0`` mostraría un
dispositivo entero libre —y mandaría a alojar gente sobre plazas tomadas— sin que nada
fallara. Con ``None``:

* en Python, cualquier aritmética explota (``TypeError``) en vez de mentir;
* en un template, ``{{ conteo.ocupadas }}`` escribe ``None``, que se ve mal **a
  propósito**: una clave ausente se renderizaría como cadena vacía, indistinguible de un
  dato legítimo, y ese es justamente el fallo silencioso que se quiere evitar;
* :attr:`Conteo.pendientes` y :attr:`Conteo.completo` permiten preguntarlo sin adivinar.

La forma pública es la definitiva. Cuando la etapa 2 agregue ``Estadia`` y
``ReservaPlaza``, lo único que cambia es que esta función pase ``ocupadas=`` y
``reservadas=`` con un entero al construir cada :class:`Conteo`: ``operativas`` y
``disponibles`` son propiedades derivadas, así que se completan solas y **ninguna
pantalla cambia**.

Invariantes que el cálculo sostiene
-----------------------------------

* ``OcupacionDispositivo.conteo`` es **exactamente** la suma de sus ``sectores``: nadie
  puede mirar el desglose y el total y encontrar dos números distintos.
* Se cuentan **solo los sectores activos**, y por eso un sector dado de baja desaparece
  de todo el cálculo, total y desglose a la vez. La contracara es que dar de baja un
  sector con plazas vivas evaporaría capacidad en silencio: esa regla —que la baja falle
  si el sector tiene plazas— le toca al servicio de baja de sector, que todavía no
  existe.
* ``FUERA_SERVICIO`` y ocupada son mutuamente excluyentes por regla de negocio (sacar de
  servicio una plaza con estadía, reserva o préstamo vigente falla, y primero se
  reubica), así que cuando la etapa 2 complete ``ocupadas`` valdrá
  ``ocupadas <= operativas``.

Costo
-----

**Una consulta** —la agregación de plazas por sector, con ``Count(filter=...)``— más, a
lo sumo, la que evalúe el queryset de dispositivos que reciba. No crece con la cantidad
de sectores, de plazas ni de dispositivos: no hay un ``.count()`` por sector.

Acá no se agrupa por tiempo y por lo tanto **no hay ningún ``Trunc*``**: la base de ECOM
no tiene tablas de zona horaria, Django traduce ``Trunc*`` sobre un ``DateTimeField`` a
``CONVERT_TZ``, devuelve ``NULL`` y rompe solo en producción. Cuando la etapa 3 sume el
censo por turno sobre fechas, el agrupamiento va en Python (precedente:
``programas/services/dashboard_becas.py``).
"""

from dataclasses import dataclass

from django.db.models import Count, Q

from programas.models import Dispositivo, Plaza, Sector

#: Las claves que la etapa 1 no puede calcular, y de dónde van a salir.
PENDIENTES_DE_ETAPA_2 = ("ocupadas", "reservadas", "disponibles")


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
    #: ``None`` mientras ``Estadia`` no exista (etapa 2). Nunca ``0``: ver el módulo.
    ocupadas: int | None = None
    #: ``None`` mientras ``ReservaPlaza`` no exista (etapa 2). Nunca ``0``.
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

        return tuple(clave for clave in PENDIENTES_DE_ETAPA_2 if getattr(self, clave) is None)

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
    """Suma una colección de conteos; la colección vacía da un conteo en cero y pendiente."""

    total = Conteo()
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


def ocupacion_de_plazas(dispositivos) -> Censo:
    """Las cifras de plazas de ``dispositivos``, en una consulta.

    ``dispositivos`` puede ser un :class:`~programas.models.Dispositivo`, su id, o
    cualquier iterable de unos u otros (incluido un queryset, que entonces se evalúa).
    Los dispositivos sin sectores aparecen igual, en cero.

    **Lo que todavía no se puede calcular vale ``None``**: ``ocupadas`` y ``reservadas``
    salen de ``Estadia`` y ``ReservaPlaza``, que crea la etapa 2, y ``disponibles`` se
    deriva de ellas. La forma del resultado ya es la definitiva; ver el docstring del
    módulo.
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
