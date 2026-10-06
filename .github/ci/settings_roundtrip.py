"""Settings del job `migration-roundtrip` (PR R-13, RED-17).

Vive fuera de `config/` a propósito. El job corre `manage.py` en **dos árboles** —el del
PR y el de la base del PR— y el de la base no tiene este archivo: entra por `PYTHONPATH`
apuntando a `.github/ci/` del árbol del PR, así que el mismo módulo sirve para los dos y
`config.settings` se resuelve en cada árbol por separado (`manage.py` pone su propio
directorio en `sys.path[0]`, antes que `PYTHONPATH`).

Lo único que cambia es el `read_timeout`/`write_timeout` de 10 s que `config/settings.py`
fija porque es el de ECOM (`CLAUDE.md` §Gotchas). Un `ALTER TABLE` sobre datos sembrados
lo pasa de largo, el cliente corta y el DDL sigue aplicándose del otro lado: la migración
queda a medias sin fila en `django_migrations`. Ese modo de falla es **real en producción**
y tiene su propia ficha (OPS-05); acá solo ensuciaría la medición de la ida y vuelta.

Cuando exista `DB_READ_TIMEOUT` como variable de entorno (OPS-05, PR R-15) este archivo
se borra y el job pasa a declarar los dos timeouts por `env:`.
"""

from config.settings import *  # noqa: F403
from config.settings import DATABASES

DATABASES["default"]["OPTIONS"].update({"read_timeout": 600, "write_timeout": 600})

# `CONN_MAX_AGE` de 60 s con una migración más larga que eso reconecta a mitad de camino
# y la conexión nueva nace sin el `init_command` (`STRICT_TRANS_TABLES`): el resto de la
# migración correría con un `sql_mode` distinto del de producción.
DATABASES["default"]["CONN_MAX_AGE"] = 0
