"""Registro genérico de reglas de vencimiento por fecha.

El comando ``procesar_vencimientos`` corre todas las reglas registradas: cierres
o cambios de estado que hay que aplicar cuando una fecha del dominio ya pasó
(ej. cerrar convocatorias vencidas, mandar sus relevamientos a revisión).

Cada regla declara:

- ``pendientes()`` → queryset de registros *vencidos y todavía por procesar* a
  hoy. Que el filtro incluya "todavía por procesar" es lo que hace al proceso
  **idempotente**: re-ejecutarlo no vuelve a tocar lo ya cerrado.
- ``aplicar(qs)`` → ejecuta el cambio sobre ese queryset y devuelve la cantidad
  de registros afectados.

Para sumar una entidad nueva (relevamiento, trámite, etc.), definí su regla en el
``services/vencimientos.py`` de la app y registrala con :func:`registrar`; el
``AppConfig.ready()`` de esa app se encarga de importar el módulo.

Reglas de aviso
---------------

El mismo registro guarda también **reglas que avisan y no aplican nada**
(:class:`ReglaAviso`, en :data:`AVISOS`): un préstamo de plaza vencido que nadie liberó,
un edificio que requiere intervención. Son la otra cara de un vencimiento —el dato pasó
su fecha o su umbral— cuando lo que corresponde no es cerrarlo solo sino que una persona
lo resuelva.

- ``pendientes(*args, **kwargs)`` → los :class:`Aviso` que hay que mostrar **ahora**. Se
  calculan del dato cada vez que se piden: un aviso no tiene estado, no se «cierra» a
  mano y no hay tabla que limpiar. Deja de aparecer en el momento en que su origen deja
  de cumplir la condición.
- ``severidad`` es de la regla, no de cada aviso, y ordena la lista (:data:`SEVERIDADES`).
- ``ambito`` agrupa las reglas de una pantalla o un módulo: quien muestra avisos pide los
  de su ámbito con :func:`avisos` y les pasa su objeto (p. ej. el dispositivo).

**Avisar nunca bloquea.** Ningún servicio consulta este registro para decidir si una
acción procede: lo leen las pantallas. ``procesar_vencimientos`` no las corre —no hay
nada que aplicar— y por eso viven en una lista aparte de :data:`REGLAS`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Callable, Iterable

from django.db.models import QuerySet


@dataclass(frozen=True)
class ReglaVencimiento:
    """Una regla de cierre/transición por fecha."""

    slug: str
    descripcion: str
    pendientes: Callable[[], QuerySet]
    aplicar: Callable[[QuerySet], int]


# Registro global. Se puebla al importar los módulos de reglas de cada app
# (vía sus AppConfig.ready()). El comando lo recorre en orden de registro.
REGLAS: list[ReglaVencimiento] = []


def registrar(regla: ReglaVencimiento) -> ReglaVencimiento:
    """Agrega ``regla`` al registro (idempotente por ``slug``: si ya existe una
    con el mismo slug la reemplaza, para no duplicar si el módulo se importa dos
    veces)."""
    global REGLAS
    REGLAS = [r for r in REGLAS if r.slug != regla.slug]
    REGLAS.append(regla)
    return regla


# --- Reglas de aviso -----------------------------------------------------------

#: De la más urgente a la menos. El orden de la tupla es el de la lista de avisos.
SEVERIDADES = ("alta", "media", "baja")


@dataclass(frozen=True)
class Aviso:
    """Algo que alguien tiene que resolver, derivado del dato que lo causa.

    ``origen`` nombra el registro que lo causa (la plaza, el edificio); ``enlace`` es dónde
    se resuelve, y ``accion`` el texto de ese enlace (vacíos si todavía no hay pantalla).
    ``fecha`` es desde cuándo pasa. ``regla`` y ``severidad`` los completa :func:`avisos`
    con los de la regla que lo produjo.
    """

    titulo: str
    texto: str
    origen: str
    fecha: date | datetime | None
    enlace: str = ""
    accion: str = ""
    regla: str = ""
    severidad: str = ""


@dataclass(frozen=True)
class ReglaAviso:
    """Una regla que avisa: no cierra ni cambia nada."""

    slug: str
    ambito: str
    descripcion: str
    severidad: str
    pendientes: Callable[..., Iterable[Aviso]]


AVISOS: list[ReglaAviso] = []


def registrar_aviso(regla: ReglaAviso) -> ReglaAviso:
    """Agrega ``regla`` a :data:`AVISOS`, idempotente por ``slug`` como :func:`registrar`."""

    global AVISOS
    if regla.severidad not in SEVERIDADES:
        raise ValueError(f"Severidad desconocida «{regla.severidad}»: tiene que ser una de {SEVERIDADES}.")
    AVISOS = [r for r in AVISOS if r.slug != regla.slug]
    AVISOS.append(regla)
    return regla


def avisos(ambito: str, *args, **kwargs) -> list[Aviso]:
    """Los avisos vigentes del ámbito, de la severidad más alta a la más baja.

    Corre cada regla del ámbito con los argumentos que recibe. Dentro de una severidad se
    respeta el orden de registro de las reglas y el que cada regla les da a sus avisos.
    """

    resultado = []
    for regla in [r for r in AVISOS if r.ambito == ambito]:
        for aviso in regla.pendientes(*args, **kwargs):
            resultado.append(replace(aviso, regla=regla.slug, severidad=regla.severidad))
    return sorted(resultado, key=lambda aviso: SEVERIDADES.index(aviso.severidad))
