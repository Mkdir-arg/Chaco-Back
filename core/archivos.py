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
  haberle agregado un sufijo) y con el valor que se le **asignó** al campo, que
  es lo que decide si hubo escritura de verdad.

Si la operación termina bien, el registro se descarta sin tocar nada.

**Solo se borra lo que esta operación escribió.** Un campo de archivo también se
llena reusando un ``FieldFile`` que ya estaba guardado —el F-00 del origen de un
traslado, el adjunto de otra fila—, y ahí Django no toca el storage: las dos
filas pasan a nombrar el mismo archivo. Anotarlo haría que el rollback borre
documentación personal **preexistente** que la otra fila sigue nombrando, que es
peor que el huérfano que esto viene a evitar. El criterio está en
:func:`_lo_escribio_esta_operacion`.

**Alcance, dicho de frente:** esto deshace lo que escribió una operación que
**falló entera**. Una anidada que falle y cuyo error atrape la de afuera para
seguir adelante (un ``savepoint`` que vuelve atrás solo) no está cubierta: el
registro es uno solo, el de la más externa, y se limpia recién cuando esa
termina. Hoy ningún llamador hace eso; si alguno lo hiciera, el archivo de la
rama fallida quedaría registrado y se borraría de más.

Y la dirección inversa tampoco está cubierta: si la operación decorada **sale
bien**, el registro se descarta ahí mismo, así que un ``transaction.atomic``
**externo** que vuelva atrás después deja la fila sin existir y el archivo en
``media/``, huérfano. Por eso la operación decorada tiene que ser la transacción
entera —lo es en las tres de ``admisiones``— y no una pieza adentro de otra.
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


def _lo_escribio_esta_operacion(asignado):
    """¿Guardar ``asignado`` escribió bytes nuevos en el storage?

    ``FileField.pre_save`` es el único punto que lo toca, y llama a
    ``FieldFile.save()`` solo cuando el valor del campo está **sin commitear**:
    el ``UploadedFile`` del formulario, el ``File`` de un script. Un
    ``FieldFile`` que vino de la base (``_committed`` en ``True``) o un nombre
    suelto en ``str`` reusan el archivo que ya estaba y no escriben nada, así que
    no son de esta operación y no se anotan.
    """
    if asignado is None or isinstance(asignado, str):
        return False
    return not getattr(asignado, "_committed", False)


def anotar_archivo_escrito(fieldfile, *, asignado):
    """Anota un ``FieldFile`` recién guardado para borrarlo si la operación falla.

    ``fieldfile`` es el campo **ya guardado**, porque el nombre final lo pone el
    storage (puede haberle agregado un sufijo). ``asignado`` es lo que se le puso
    al campo antes de guardar, y es lo que decide si se anota: ver
    :func:`_lo_escribio_esta_operacion`.
    """
    escritos = _ESCRITOS.get()
    if escritos is None or not fieldfile or not _lo_escribio_esta_operacion(asignado):
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
