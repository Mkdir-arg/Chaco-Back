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
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

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
