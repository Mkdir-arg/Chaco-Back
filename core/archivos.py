"""Archivos escritos adentro de una transacción (RED-35).

El storage no tiene transacción. Guardar un ``FileField`` escribe el archivo en
``media/`` en el acto, así que si la escritura que lo guardó vuelve atrás, la
fila desaparece y el archivo queda ahí **sin dueño y para siempre**: nadie lo
lista, nadie lo borra, y en este sistema esos archivos son documentación
personal (el F-00 de una admisión, el certificado de un requisito).

La otra punta —borrar del storage un archivo que la base todavía puede
devolver— ya la resuelve ``transaction.on_commit`` donde hace falta
(``padron._borrar_archivo_tras_commit``, ``legajos.services.contactos``). Esta
es la simétrica, y no tiene equivalente en Django: no existe un ``on_rollback``.

Se usa en dos partes:

- la operación que escribe se decora con :func:`archivos_atomicos`, **por
  afuera** de ``transaction.atomic`` —así, cuando el limpiador corre, la base ya
  volvió atrás—;
- el punto que guarda el archivo llama a :func:`anotar_archivo_escrito` con el
  ``FieldFile`` ya guardado (el nombre final lo pone el storage, que puede
  haberle agregado un sufijo).

Si la operación termina bien, el registro se descarta sin tocar nada.

**Alcance, dicho de frente:** esto deshace lo que escribió una operación que
**falló entera**. Una anidada que falle y cuyo error atrape la de afuera para
seguir adelante (un ``savepoint`` que vuelve atrás solo) no está cubierta: el
registro es uno solo, el de la más externa, y se limpia recién cuando esa
termina. Hoy ningún llamador hace eso; si alguno lo hiciera, el archivo de la
rama fallida quedaría registrado y se borraría de más.
"""

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

logger = logging.getLogger(__name__)

#: Los archivos que escribió la operación en curso, en este hilo o tarea.
#: ``None`` fuera de :func:`archivos_atomicos`: anotar ahí no hace nada, que es
#: lo correcto para un guardado suelto sin transacción propia.
_ESCRITOS = ContextVar("archivos_escritos", default=None)


def anotar_archivo_escrito(fieldfile):
    """Anota un ``FieldFile`` recién guardado para borrarlo si la operación falla."""
    escritos = _ESCRITOS.get()
    if escritos is None or not fieldfile:
        return
    escritos.append((fieldfile.storage, fieldfile.name))


@contextmanager
def _registro():
    """Cede el registro vigente. Lo crea solo la operación más externa."""
    heredado = _ESCRITOS.get()
    if heredado is not None:
        yield heredado, False
        return
    escritos = []
    token = _ESCRITOS.set(escritos)
    try:
        yield escritos, True
    finally:
        _ESCRITOS.reset(token)


def _borrar(escritos):
    """Best effort: un storage que no deja borrar no puede tapar el error real."""
    for storage, nombre in escritos:
        try:
            storage.delete(nombre)
        except Exception:  # permisos, volumen de media caído, archivo ya borrado…
            logger.exception("No se pudo borrar el archivo huérfano %s", nombre)


def archivos_atomicos(fn):
    """Los archivos que la operación escriba se borran si la operación falla.

    Va **arriba** de ``@transaction.atomic``::

        @archivos_atomicos
        @transaction.atomic
        def trasladar_admision(...):
            ...
    """

    @wraps(fn)
    def envoltorio(*args, **kwargs):
        with _registro() as (escritos, es_el_duenio):
            try:
                return fn(*args, **kwargs)
            except BaseException:
                if es_el_duenio:
                    _borrar(escritos)
                raise

    return envoltorio
