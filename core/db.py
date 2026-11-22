"""Lo que comparten las consultas de todas las apps (RED-09, segunda parte).

La primera pieza es :func:`q_uuid_en_texto`, y vive acá por el mismo
motivo que ``core.dni``: la regla es del sistema, no de Becas. Siete de los nueve
``UUIDField`` del repo están fuera de ``programas`` (``legajos``, ``users``,
``core``) y el helper nació en ``programas/services/becas.py``: cualquiera de
esas apps tenía que importar el servicio de un dominio ajeno para buscar por su
propio UUID —y ``legajos.models`` no puede importar ``programas`` sin cerrar un
ciclo—. ``programas.services.becas`` lo reexporta: todo el código que ya lo
importaba de ahí sigue andando.

El ratchet que exige usarlo es ``core/tests/test_uuid_mariadb.py``.

La segunda es :func:`leer_con_bloqueo_compartido`: el candado compartido que el ORM no
tiene, con la sintaxis que entienden MySQL 8 y MariaDB.
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


def leer_con_bloqueo_compartido(modelo, pks, campo):
    """Lee ``campo`` de las filas ``pks`` con un candado **compartido**. Devuelve ``{pk: valor}``.

    ``select_for_update()`` es el único candado del ORM y es exclusivo: dos transacciones que
    solo necesitan que la fila no cambie mientras trabajan se esperarían entre sí. El
    compartido las deja pasar juntas y frena a quien quiera escribir la fila (un
    ``select_for_update()`` o un ``UPDATE``) hasta que todas terminen. Es lo que usan los
    caminos de Dispositivos que leen el estado de la institución antes de bloquear una plaza
    (ver ``programas.services.dispositivos.bloquear_institucion``).

    * MySQL 8 y MariaDB (los dos con ``vendor == "mysql"``): ``LOCK IN SHARE MODE``, la sintaxis
      que entienden los dos (``FOR SHARE`` no existe en MariaDB 10.11).
    * PostgreSQL: ``FOR SHARE``.
    * SQLite (la suite): sin candado, que no los tiene; la lectura igual se hace.

    Las filas se piden ordenadas por pk, así que varias se toman siempre en el mismo orden.
    Exige estar dentro de ``transaction.atomic()``, como ``select_for_update()``: fuera de una
    transacción el candado se soltaría al terminar la consulta. Los identificadores salen de
    ``_meta`` y los valores van como parámetros.
    """

    from django.db import connections, router
    from django.db.transaction import TransactionManagementError

    conexion = connections[router.db_for_write(modelo)]
    if not conexion.in_atomic_block:
        raise TransactionManagementError("leer_con_bloqueo_compartido exige estar dentro de transaction.atomic().")
    ids = sorted({pk for pk in pks if pk is not None})
    if not ids:
        return {}
    citar = conexion.ops.quote_name
    tabla = citar(modelo._meta.db_table)
    pk = citar(modelo._meta.pk.column)
    columna = citar(modelo._meta.get_field(campo).column)
    marcas = ", ".join(["%s"] * len(ids))
    # Los identificadores salen del modelo (nunca de la entrada) y van citados; los valores, por parámetro.
    sql = f"SELECT {pk}, {columna} FROM {tabla} WHERE {pk} IN ({marcas}) ORDER BY {pk}"  # nosec B608
    if conexion.vendor == "mysql":
        sql += " LOCK IN SHARE MODE"
    elif conexion.vendor == "postgresql":
        sql += " FOR SHARE"
    with conexion.cursor() as cursor:
        cursor.execute(sql, ids)
        return dict(cursor.fetchall())
