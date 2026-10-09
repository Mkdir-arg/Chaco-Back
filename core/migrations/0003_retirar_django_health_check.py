"""OPS-13 · Se va `django-health-check`: su tabla y sus dos filas de `django_migrations`.

Las sondas del sistema son la app `healthcheck` de este repo (`/health/` y
`/health/ready/`). El paquete de terceros dejó de montar URLs en el Cambio 153 (OPS-04) y
desde este PR tampoco está en `INSTALLED_APPS` ni en `requirements.txt`.

**Por qué hace falta una migración para sacar un `pip install`.** La app tenía una
migración aplicada y una tabla en todos los ambientes donde ya corrió —icore, testing y
PRD—. Sacarla a secas deja:

* la tabla `health_check_db_testmodel` sin ningún modelo que la nombre (huérfana, RED-15);
* **dos** filas en `django_migrations` sin archivo en disco: `db.0001_initial` y
  `health_check_db.0001_initial`. Son dos porque el `app_label` del paquete cambió entre
  versiones y su `0001_initial` declara `replaces = [("health_check_db", "0001_initial")]`.

`verificar_esquema_migraciones` (OPS-01) no aborta por ninguna de las dos cosas —las filas
caen en «este código no tiene migraciones para esa app», que es aviso, y las huérfanas solo
frenan con `--estricto`—, pero deja dos avisos en **cada arranque de cada pod** y una tabla
que nadie sabe de dónde salió. El job «Migrate ida y vuelta», que sí corre `--estricto`
sobre una base sembrada desde el árbol base, la marcaría.

**Contract, no expand.** Lo que se borra dejó de leerse en el Cambio 153 (hace más de dos
releases): el backend `health_check.db` solo toca esa tabla cuando corre un *plugin* de
health check, y ninguna URL llega a uno desde entonces. Durante el rolling, la release
vieja tiene la app instalada y no la usa.

**Si hay rollback de release**, el código viejo vuelve con `health_check` en
`INSTALLED_APPS` y sin la fila: `migrate` corre su `CreateModel`, la tabla no está (la
borramos) y la vuelve a crear vacía. Se arregla solo y no hay dato que perder: esa tabla
solo guarda una fila transitoria que el propio check escribe y borra.

**Reversa real, no noop:** vuelven la tabla (vacía) y las dos filas. Lo único que no vuelve
es el `applied` original de esas filas —se graba la fecha de la reversa— y el contenido de
la tabla, que es transitorio por diseño.

`atomic = False`: MySQL y MariaDB no tienen DDL transaccional, así que un corte en el medio
—el `read_timeout` de 10 s de ECOM— dejaría el esquema donde llegó y sin fila en
`django_migrations`, y el reintento correría el archivo desde la primera línea (RED-58).
Los tres pasos se condicionan al estado real: `DROP TABLE` mira
`information_schema`/`introspection` y los `DELETE` filtran por la fila que buscan.
"""

from django.db import migrations

TABLA = "health_check_db_testmodel"

#: Las dos filas que el paquete dejó. `db` es el `app_label` del `AppConfig` actual;
#: `health_check_db` es el viejo, que su `replaces` cubre.
FILAS = (("db", "0001_initial"), ("health_check_db", "0001_initial"))

#: `TestModel`: `id` autoincremental y `title` varchar(128). Se escribe a mano porque al
#: revertir el paquete ya no está instalado y no hay modelo del que derivarla.
DDL_POR_MOTOR = {
    "mysql": (
        f"CREATE TABLE IF NOT EXISTS `{TABLA}` ("
        " `id` integer NOT NULL AUTO_INCREMENT PRIMARY KEY,"
        " `title` varchar(128) NOT NULL)"
    ),
    "sqlite": (
        f'CREATE TABLE IF NOT EXISTS "{TABLA}" ('
        ' "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,'
        ' "title" varchar(128) NOT NULL)'
    ),
}


def _existe_la_tabla(conexion, cursor) -> bool:
    return TABLA in conexion.introspection.table_names(cursor)


def retirar(apps, schema_editor):
    conexion = schema_editor.connection
    with conexion.cursor() as cursor:
        if _existe_la_tabla(conexion, cursor):
            cursor.execute(f"DROP TABLE {conexion.ops.quote_name(TABLA)}")
        for app, nombre in FILAS:
            cursor.execute("DELETE FROM django_migrations WHERE app = %s AND name = %s", [app, nombre])


def restituir(apps, schema_editor):
    conexion = schema_editor.connection
    ddl = DDL_POR_MOTOR.get(conexion.vendor)
    if ddl is None:  # pragma: no cover — solo mysql/mariadb y sqlite en este proyecto
        raise RuntimeError(f"no sé recrear {TABLA} en {conexion.vendor}: agregá su DDL en core/migrations/0003.")
    with conexion.cursor() as cursor:
        cursor.execute(ddl)
        for app, nombre in FILAS:
            # Se consulta y recién después se inserta: un `INSERT … SELECT … WHERE NOT
            # EXISTS` sin `FROM` es válido en SQLite y no en MySQL, y `FROM DUAL` es al
            # revés.
            cursor.execute("SELECT 1 FROM django_migrations WHERE app = %s AND name = %s", [app, nombre])
            if cursor.fetchone() is None:
                cursor.execute(
                    "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, CURRENT_TIMESTAMP)",
                    [app, nombre],
                )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("core", "0002_remove_turno"),
    ]

    operations = [
        # CONTRACT: `health_check_db_testmodel` dejó de leerse en el Cambio 153 (OPS-04,
        # 06-oct-2026), cuando se retiró `path("health/", include("health_check.urls"))`
        # y ninguna URL volvió a llegar a un plugin de health check. Van más de dos
        # releases desde entonces, así que ninguna release viva la toca.
        migrations.RunPython(retirar, restituir),
    ]
