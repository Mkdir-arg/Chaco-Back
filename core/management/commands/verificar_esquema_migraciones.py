"""Guarda de coherencia entre `django_migrations` y el esquema real (OPS-01, RED-15).

**Solo lee.** Corre en el entrypoint antes del `migrate` y en el último paso del job
`Migrate ida y vuelta`. Lo que busca son las tres formas en que el registro de
migraciones y las tablas de verdad se separan:

1. **Filas sin archivo** (`applied - disk`). Es el estado de icore: el checkout quedó en
   `a9fc4ee`, donde las migraciones del constructor se llamaban `0057`-`0062`, y
   `development` las renumeró a `0060`-`0065`. Para Django son migraciones distintas: las
   nuevas no están aplicadas, así que las va a correr, y las tablas ya están.
2. **Tablas que una migración sin aplicar va a crear y ya existen.** El síntoma: `1050 Table already
   exists` en medio del deploy, con el esquema a medias porque en MySQL y MariaDB el DDL
   no es transaccional. El otro camino a lo mismo es restaurar un dump de producción
   sobre una base que tuvo más tablas: el dump trae un `DROP` por cada tabla **que él
   contiene**, y las que solo existían acá sobreviven mientras `django_migrations` vuelve
   al estado del dump.
3. **Tablas huérfanas** (el inverso, RED-15): existen en la base y ningún modelo del
   estado final las nombra. Es lo que deja un rollback que se cortó a mitad de camino.
   No frena el deploy —hay bases con tablas ajenas por motivos legítimos— salvo con
   `--estricto`, que es como lo corre el job de ida y vuelta, donde la base es efímera y
   no hay nada ajeno que valga.

La salida **nunca** es «corré `--fake`». `--fake` deja la tabla sin las columnas de los
`AddField` posteriores: cambia un deploy fallido por un error en runtime, meses después.
"""

from __future__ import annotations

import logging

from django.apps import apps as apps_vivas
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations import CreateModel

logger = logging.getLogger(__name__)

# Tablas que no son de ningún modelo y tienen que estar igual.
TABLAS_DEL_FRAMEWORK = {"django_migrations"}

AYUDA_FANTASMAS = (
    "Hay filas en django_migrations sin archivo en el código desplegado. Suele ser un "
    "checkout en la rama equivocada o una renumeración de migraciones. Se arregla "
    "renombrando esas filas (UPDATE django_migrations SET name=... — ver "
    "core/sql/2026-10-06_renombrar_migraciones_icore.sql), NUNCA con --fake ni borrando filas a ciegas."
)

AYUDA_COLISIONES = (
    "El migrate va a intentar crear tablas que ya existen y va a morir con «1050 Table "
    "already exists» dejando el esquema a medias. Si viene de un restore, hay que borrar "
    "esas tablas huérfanas antes de desplegar; si viene de una renumeración, hay que "
    "renombrar las filas de django_migrations. NUNCA --fake: deja la tabla sin las "
    "columnas de los AddField posteriores y rompe en runtime en vez de en el deploy."
)


def filas_sin_archivo(aplicadas, conocidas) -> list[tuple[str, str]]:
    """`applied - conocidas`: migraciones registradas que el código ya no tiene."""
    return sorted(set(aplicadas) - set(conocidas))


def claves_conocidas(loader) -> set:
    """Las claves que el código sí tiene: las de disco **más** las que un `replaces` cubre.

    Una migración *reemplazada* —por un squash— figura aplicada y no tiene archivo
    propio: es correcto y permanente. `django-health-check` es el caso vivo de este
    repo: su `db.0001_initial` declara `replaces = [("health_check_db", "0001_initial")]`,
    así que `django_migrations` guarda **dos** filas y en disco hay **un** archivo, bajo
    un tercer label (`db`, el del AppConfig).

    Sin esta unión, la guarda abortaría el arranque en icore, en testing y en PRD el día
    que se despliegue —lo midió el CI de este mismo PR—, y lo haría además con cualquier
    squash que el proyecto haga en el futuro.
    """
    reemplazadas = {
        clave for migracion in (getattr(loader, "replacements", None) or {}).values() for clave in migracion.replaces
    }
    return set(loader.disk_migrations) | reemplazadas


def migraciones_pendientes(loader) -> list:
    """Todas las migraciones del grafo que no figuran aplicadas, ordenadas.

    **No** se usa `MigrationExecutor.migration_plan`. Medido contra MariaDB 10.11: si
    el nodo hoja ya está aplicado, `migration_plan` entra en su rama de *backwards* y
    devuelve una lista **vacía**, aunque haya migraciones intermedias sin aplicar. Para
    esta guarda eso sería un falso OK justo en el caso raro. Lo que importa es más
    simple: cualquier migración sin aplicar cuya `CreateModel` ya tenga su tabla es un
    problema, esté donde esté en el grafo.
    """
    return [loader.graph.nodes[clave] for clave in sorted(loader.graph.nodes) if clave not in loader.applied_migrations]


def _db_table(app_label: str, operacion) -> str:
    opciones = getattr(operacion, "options", None) or {}
    return opciones.get("db_table") or f"{app_label}_{operacion.name.lower()}"


def colisiones_de_tablas(plan, tablas_existentes) -> list[tuple[str, str, str]]:
    """`(tabla, app, migración)` por cada `CreateModel` del plan cuya tabla ya está."""
    existentes = {nombre.lower() for nombre in tablas_existentes}
    encontradas = []
    for migracion in plan:
        for operacion in migracion.operations:
            if not isinstance(operacion, CreateModel):
                continue
            tabla = _db_table(migracion.app_label, operacion)
            if tabla.lower() in existentes:
                encontradas.append((tabla, migracion.app_label, migracion.name))
    return encontradas


def tablas_huerfanas(tablas_existentes, esperadas) -> list[str]:
    """Las que existen y no corresponden a ningún modelo del estado final."""
    conocidas = {nombre.lower() for nombre in esperadas} | TABLAS_DEL_FRAMEWORK
    return sorted(nombre for nombre in tablas_existentes if nombre.lower() not in conocidas)


def tablas_esperadas(loader=None) -> set[str]:
    """Las tablas del código de hoy más las del estado final de las migraciones.

    Las dos fuentes hacen falta. Los modelos vivos cubren las apps sin migraciones (las
    que el entrypoint arma con `--run-syncdb`) y las de terceros; el estado final de las
    migraciones cubre lo que el grafo deja creado aunque el modelo ya no esté en el
    código, que no es huérfano: es historia que todavía no se contrajo.
    """
    esperadas = {modelo._meta.db_table for modelo in apps_vivas.get_models(include_auto_created=True)}
    if loader is None:
        return esperadas
    try:
        estado = loader.project_state()
        esperadas |= {modelo._meta.db_table for modelo in estado.apps.get_models(include_auto_created=True)}
    except Exception:  # noqa: BLE001 — renderizar el estado histórico puede fallar; no es motivo de rojo
        logger.warning("no se pudo renderizar el estado final de las migraciones: se usan los modelos vivos")
    return esperadas


class Command(BaseCommand):
    help = "Verifica, sin escribir nada, que django_migrations y el esquema real se correspondan."

    def add_arguments(self, parser):
        parser.add_argument("--database", default=DEFAULT_DB_ALIAS, help="alias de la base (default: default)")
        parser.add_argument(
            "--estricto",
            action="store_true",
            help="las tablas huérfanas también frenan (lo usa el job «Migrate ida y vuelta»)",
        )

    def handle(self, *args, **opciones):
        conexion = connections[opciones["database"]]
        loader = MigrationLoader(conexion)

        problemas = []

        fantasmas = filas_sin_archivo(loader.applied_migrations, claves_conocidas(loader))
        if fantasmas:
            detalle = "\n".join(f"  - {app}.{nombre}" for app, nombre in fantasmas)
            problemas.append(f"{AYUDA_FANTASMAS}\nFilas sin archivo:\n{detalle}")

        tablas = set(conexion.introspection.table_names())

        pendientes = migraciones_pendientes(loader)
        colisiones = colisiones_de_tablas(pendientes, tablas)
        if colisiones:
            detalle = "\n".join(f"  - {tabla} (la crearía {app}.{nombre})" for tabla, app, nombre in colisiones)
            problemas.append(f"{AYUDA_COLISIONES}\nTablas que ya existen:\n{detalle}")

        huerfanas = tablas_huerfanas(tablas, tablas_esperadas(loader))
        if huerfanas:
            aviso = (
                "Tablas que existen y que ningún modelo del estado final nombra "
                "(restos de un rollback cortado, RED-15): " + ", ".join(huerfanas)
            )
            if opciones["estricto"]:
                problemas.append(aviso)
            else:
                self.stderr.write(self.style.WARNING(aviso))

        if problemas:
            raise CommandError("\n\n".join(problemas))

        self.stdout.write(
            self.style.SUCCESS(
                f"Esquema coherente: {len(loader.applied_migrations)} migraciones aplicadas, "
                f"{len(pendientes)} sin aplicar, {len(tablas)} tablas."
            )
        )
