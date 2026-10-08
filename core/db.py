"""Lo que comparten las consultas de todas las apps (RED-09, segunda parte).

Hoy vive acá una sola pieza, :func:`q_uuid_en_texto`, y vive acá por el mismo
motivo que ``core.dni``: la regla es del sistema, no de Becas. Siete de los nueve
``UUIDField`` del repo están fuera de ``programas`` (``legajos``, ``users``,
``core``) y el helper nació en ``programas/services/becas.py``: cualquiera de
esas apps tenía que importar el servicio de un dominio ajeno para buscar por su
propio UUID —y ``legajos.models`` no puede importar ``programas`` sin cerrar un
ciclo—. ``programas.services.becas`` lo reexporta: todo el código que ya lo
importaba de ahí sigue andando.

El ratchet que exige usarlo es ``core/tests/test_uuid_mariadb.py``.
"""

from __future__ import annotations

import uuid

from django.db.models import CharField, F, Q, Value
from django.db.models.lookups import Exact


def q_uuid_en_texto(campo, valor):
    """Filtro por un ``UUIDField`` guardado como texto en cualquiera de sus dos formas.

    En MySQL la columna es ``char`` y conviven filas en hex de 32 (MySQL, SQLite)
    y con guiones (MariaDB 10.7+, que Django trata como UUID nativo; o una base
    restaurada de un motor al otro). El lookup ``campo=valor`` del ORM manda una
    sola de las dos, según el motor, y no encuentra la otra. Se compara por
    igualdad contra las dos como texto plano, sin funciones sobre la columna,
    para que el índice siga sirviendo.

    ``valor`` puede ser un ``uuid.UUID`` o su texto en cualquiera de las dos
    formas (R0-07). Lo que no es un UUID —``None``, un texto cualquiera, un
    número— no revienta con un ``AttributeError`` adentro de una vista: devuelve
    un ``Q`` que no trae nada, que es la respuesta correcta a «buscá este token»
    cuando el token no puede existir.
    """
    try:
        normalizado = valor if isinstance(valor, uuid.UUID) else uuid.UUID(str(valor))
    except (AttributeError, TypeError, ValueError):
        return Q(pk__in=[])
    columna = F(campo)
    return Q(Exact(columna, Value(normalizado.hex, output_field=CharField()))) | Q(
        Exact(columna, Value(str(normalizado), output_field=CharField()))
    )
