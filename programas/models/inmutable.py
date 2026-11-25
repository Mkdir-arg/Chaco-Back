"""Libro inmutable: el bloque solo-aditivo que repetían las trazas, escrito una vez (análisis 010, RN-010-05).

Un modelo que lo usa hereda de :class:`LibroInmutable` y queda así:

* ``QuerySet.update`` / ``delete`` / ``bulk_update`` y ``bulk_create(update_conflicts=True)`` levantan
  ``ValidationError``;
* ``save()`` sobre una fila que ya existe y ``delete()`` de instancia levantan ``ValidationError``; ``save()`` de
  una instancia nueva siempre es un INSERT (``force_insert``), así que un ``pk`` existente choca en vez de pisar.

Lo mal cargado se corrige con una fila nueva, nunca reescribiendo la historia. Por ahora lo usan solo las dos
tablas del stock; migrar las trazas viejas queda para la auditoría (MINOR 10 del Cambio 471).

``save()`` mira ``_state.adding`` y no ``pk``: una fila con ``pk`` asignado a mano pero todavía no guardada
tiene que poder insertarse, y una guardada no se reescribe.
"""

from django.core.exceptions import ValidationError
from django.db import models

MENSAJE_INMUTABLE = "Este registro es inmutable: se corrige con un registro nuevo."
MENSAJE_NO_SE_BORRA = "Este registro no se elimina."


class LibroInmutableQuerySet(models.QuerySet):
    """Sin vías masivas de mutación: ``update``, ``update_or_create``, ``delete``, ``bulk_update`` y
    ``bulk_create(update_conflicts=True)``."""

    def update(self, **kwargs):
        raise ValidationError(MENSAJE_INMUTABLE)

    def update_or_create(self, defaults=None, create_defaults=None, **kwargs):
        raise ValidationError(MENSAJE_INMUTABLE)

    def delete(self):
        raise ValidationError(MENSAJE_NO_SE_BORRA)

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError(MENSAJE_INMUTABLE)

    def bulk_create(self, objs, *args, update_conflicts=False, **kwargs):
        # `ON DUPLICATE KEY UPDATE` reescribiría una fila existente.
        if update_conflicts:
            raise ValidationError(MENSAJE_INMUTABLE)
        return super().bulk_create(objs, *args, update_conflicts=update_conflicts, **kwargs)


class LibroInmutableManager(models.Manager.from_queryset(LibroInmutableQuerySet)):
    """El Manager delega en el QuerySet: no repite sus bloqueos."""


class LibroInmutable(models.Model):
    """Mixin abstracto: una fila se inserta una vez y no cambia ni se borra."""

    objects = LibroInmutableManager()

    class Meta:
        abstract = True
        base_manager_name = "objects"
        default_manager_name = "objects"

    def save(self, *args, **kwargs):
        if not self._state.adding or kwargs.get("force_update") or kwargs.get("update_fields"):
            raise ValidationError(MENSAJE_INMUTABLE)
        # Con `pk` asignado a mano Django haría UPDATE primero: se fuerza el INSERT, que choca contra la fila vieja.
        kwargs["force_insert"] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(MENSAJE_NO_SE_BORRA)
