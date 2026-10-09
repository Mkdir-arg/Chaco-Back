"""Guarda de coherencia entre `django_migrations` y el esquema real (OPS-01, RED-15).

**Solo lee.** Corre en el entrypoint antes del `migrate` y en el último paso del job
`Migrate ida y vuelta`. Lo que busca son las tres formas en que el registro de
migraciones y las tablas de verdad se separan:

1. **Filas sin archivo** (`applied - disk`). Es el estado de icore: el checkout quedó en
   `a9fc4ee`, donde las migraciones del constructor se llamaban `0057`-`0062`, y
   `development` las renumeró a `0060`-`0065`. Para Django son migraciones distintas: las
   nuevas no están aplicadas, así que las va a correr, y las tablas ya están.

   **Pero una fila sin archivo casi nunca es eso.** Una base cualquiera de este proyecto
   tiene varias que son inertes y que no se van a limpiar nunca: `silk.0001`-`0008` si la
   base se migró con `DJANGO_DEBUG=True` y se arranca con `False` (`silk` entra a
   `INSTALLED_APPS` solo con `DEBUG`), las de `turnos` —app borrada—, las de `tramites`
   —que ya no tiene paquete de migraciones— y
   `programas.0046_formulario_fecha_aprobacion_formulario_fecha_rechazo`, borrada el
   18/08 con su número reusado. Abortar por cualquiera de ellas es dejar un ambiente que
   **no vuelve a arrancar nunca**, que es peor que el problema que la guarda busca.

   Así que frena **solo** la renumeración: una fila cuyo nombre, sin el número, también
   existe en disco con **otro** número y **sin aplicar**. Eso es exactamente «la misma
   migración registrada con otro nombre», o sea la que `migrate` va a volver a correr.
   El resto sale por aviso, con su motivo. Tiene un falso negativo conocido —una
   migración renumerada **y** renombrada— explicado en `clasificar_filas_sin_archivo`.
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
import re

from django.apps import apps as apps_vivas
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations import CreateModel

logger = logging.getLogger(__name__)

# Tablas que no son de ningún modelo y tienen que estar igual.
TABLAS_DEL_FRAMEWORK = {"django_migrations"}

# Tablas que carga el organismo con sus `.sql` (`programas/management/commands/_insumos_siis.py`,
# `INSUMOS`) y que se leen con SQL crudo: no tienen modelo y no son huérfanas. `seed_perf` crea
# `aprobados_materias` para el banco y el job «Migrate ida y vuelta», así que sin esto el chequeo
# estricto las marcaba como sobrantes. `core` no importa de `programas` (ratchet de capas, R-21):
# la lista se repite acá y `test_verificar_esquema_migraciones` la ata a `INSUMOS`.
TABLAS_EXTERNAS_DEL_ORGANISMO = {"aprobados_materias", "localidades_corregidas", "ciudadanos_renaper"}

# `0060_catalogo_grupos_origen_canal` → número y nombre. Lo que identifica a una
# migración renumerada es la segunda mitad.
NUMERADA = re.compile(r"^(\d+)_(.+)$")

AYUDA_RENUMERADAS = (
    "Hay migraciones registradas con un número y presentes en disco con otro, sin aplicar: "
    "el migrate las va a volver a correr sobre un esquema que ya las tiene y va a morir a "
    "mitad de camino. Suele ser un checkout en la rama equivocada. Se arregla renombrando "
    "esas filas (UPDATE django_migrations SET name=... — ver "
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
    propio: es correcto y permanente. El caso que lo descubrió fue `django-health-check`:
    su `db.0001_initial` declaraba `replaces = [("health_check_db", "0001_initial")]`, así
    que `django_migrations` guardaba **dos** filas y en disco había **un** archivo, bajo un
    tercer label (`db`, el del AppConfig). Sin esta unión, la guarda abortaba el arranque
    en icore, en testing y en PRD —lo midió el CI del PR R-15—.

    Ese paquete salió del proyecto en el Cambio 196 (OPS-13) y `core.0003` borró sus dos
    filas, así que hoy el repo no tiene ningún `replaces` vivo. La unión se queda: la
    próxima vez que alguien haga un squash, o instale una dependencia que traiga uno, el
    modo de falla es el mismo y el ambiente que lo sufre es producción.
    """
    reemplazadas = {
        clave for migracion in (getattr(loader, "replacements", None) or {}).values() for clave in migracion.replaces
    }
    return set(loader.disk_migrations) | reemplazadas


def claves_sin_aplicar(loader) -> list[tuple[str, str]]:
    """Las claves del grafo que no figuran aplicadas, ordenadas.

    **No** se usa `MigrationExecutor.migration_plan`. Medido contra MariaDB 10.11: si
    el nodo hoja ya está aplicado, `migration_plan` entra en su rama de *backwards* y
    devuelve una lista **vacía**, aunque haya migraciones intermedias sin aplicar. Para
    esta guarda eso sería un falso OK justo en el caso raro. Lo que importa es más
    simple: cualquier migración sin aplicar cuya `CreateModel` ya tenga su tabla es un
    problema, esté donde esté en el grafo.
    """
    return [clave for clave in sorted(loader.graph.nodes) if clave not in loader.applied_migrations]


def migraciones_pendientes(loader) -> list:
    """Las migraciones sin aplicar, en objetos."""
    return [loader.graph.nodes[clave] for clave in claves_sin_aplicar(loader)]


def _sufijo(nombre: str) -> str | None:
    """`0060_catalogo_grupos_origen_canal` → `catalogo_grupos_origen_canal`."""
    coincidencia = NUMERADA.match(nombre)
    return coincidencia.group(2) if coincidencia else None


def clasificar_filas_sin_archivo(fantasmas, loader) -> tuple[list, list]:
    """Parte las filas sin archivo en las que frenan el deploy y las que solo se avisan.

    Frena **una sola** situación: la fila registra una migración que en disco existe con
    otro número y **sin aplicar**. Ahí `migrate` la va a volver a correr sobre un esquema
    que ya la tiene. Es el estado de icore y es el único caso en que la fila, por sí
    sola, predice una rotura.

    Todo lo demás es ruido que ninguna base se va a sacar de encima: apps que este código
    no tiene (`turnos` borrada, `silk` fuera de `INSTALLED_APPS` sin `DEBUG`, `tramites`
    sin paquete de migraciones) y migraciones borradas sin reemplazo. Ahí `migrate` no
    tiene nada que correr por esa fila, así que se avisa y se sigue: abortar dejaría el
    ambiente sin arrancar **nunca más**, que es peor que el problema original.

    **Límite conocido (falso negativo), a propósito.** La renumeración se reconoce por el
    nombre sin el número, así que una migración renumerada **y renombrada** —cambió
    también la parte descriptiva— cae en «inerte» y la guarda deja arrancar. Si además es
    hoja y trae un `AddField`/`AddIndex`, el `migrate` se va a morir a mitad de camino con
    `1060 Duplicate column` o `1061 Duplicate key`, que es lo que esta guarda querría
    anticipar. No se cubre y es deliberado: adivinar que dos migraciones con nombres
    distintos son «la misma» pide comparar operaciones, y una heurística floja acá se
    paga en el arranque de producción, que es donde no se puede equivocar. El caso real
    del repo —icore— conserva el nombre; y la segunda barrera, la colisión de tablas,
    sigue cubriendo el `CreateModel` aunque el nombre cambie entero.

    Devuelve `(frenan, inertes)`: `frenan` como `((app, nombre), nombre_en_disco)`,
    `inertes` como `((app, nombre), motivo)`.
    """
    sin_aplicar_por_sufijo: dict[tuple[str, str], list[str]] = {}
    for app, nombre in claves_sin_aplicar(loader):
        sufijo = _sufijo(nombre)
        if sufijo:
            sin_aplicar_por_sufijo.setdefault((app, sufijo), []).append(nombre)

    frenan, inertes = [], []
    for app, nombre in fantasmas:
        if app not in loader.migrated_apps:
            inertes.append(((app, nombre), "este código no tiene migraciones para esa app"))
            continue
        sufijo = _sufijo(nombre)
        renumeradas = [n for n in sin_aplicar_por_sufijo.get((app, sufijo), []) if n != nombre] if sufijo else []
        if renumeradas:
            frenan.append(((app, nombre), renumeradas[0]))
        else:
            inertes.append(((app, nombre), "ninguna migración sin aplicar lleva ese mismo nombre"))
    return frenan, inertes


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
    conocidas = {nombre.lower() for nombre in esperadas} | TABLAS_DEL_FRAMEWORK | TABLAS_EXTERNAS_DEL_ORGANISMO
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
        parser.add_argument(
            "--solo-reporte",
            action="store_true",
            help=(
                "imprime todo lo que encuentra y termina en 0 aunque haya hallazgos. "
                "Es el modo para mirar un ambiente ajeno —testing o PRD de ECOM— antes de "
                "espejar o desplegar, sin que un código de salida distinto de 0 corte nada."
            ),
        )

    def handle(self, *args, **opciones):
        conexion = connections[opciones["database"]]
        loader = MigrationLoader(conexion)

        problemas = []

        fantasmas = filas_sin_archivo(loader.applied_migrations, claves_conocidas(loader))
        renumeradas, inertes = clasificar_filas_sin_archivo(fantasmas, loader)
        if renumeradas:
            detalle = "\n".join(
                f"  - {app}.{nombre} (en disco, sin aplicar: {app}.{en_disco})"
                for (app, nombre), en_disco in renumeradas
            )
            problemas.append(f"{AYUDA_RENUMERADAS}\nMigraciones registradas con otro número:\n{detalle}")
        for (app, nombre), motivo in inertes:
            # Aviso y no error: son filas que ninguna base se va a sacar de encima y que
            # no predicen ninguna rotura. Al log además del stderr, porque en el arranque
            # del contenedor el stderr se pierde entre el resto del bootstrap.
            aviso = f"fila sin archivo que no frena el deploy: {app}.{nombre} ({motivo})"
            logger.warning(aviso)
            self.stderr.write(self.style.WARNING(aviso))

        tablas = set(conexion.introspection.table_names())

        pendientes = migraciones_pendientes(loader)
        colisiones = colisiones_de_tablas(pendientes, tablas)
        if colisiones:
            detalle = "\n".join(f"  - {tabla} (la crearía {app}.{nombre})" for tabla, app, nombre in colisiones)
            problemas.append(f"{AYUDA_COLISIONES}\nTablas que ya existen:\n{detalle}")

        huerfanas = tablas_huerfanas(tablas, tablas_esperadas(loader))
        if huerfanas:
            aviso = (
                "Tablas que existen y que ningún modelo del estado final nombra. Puede ser "
                "una app que se retiró sin limpiar (p. ej. `silk_*`), un restore sobre una "
                "base que tenía más tablas, o una reversa que se cortó a mitad de camino "
                "(RED-15). No frena el deploy por sí sola: " + ", ".join(huerfanas)
            )
            if opciones["estricto"]:
                problemas.append(aviso)
            else:
                self.stderr.write(self.style.WARNING(aviso))

        resumen = (
            f"{len(loader.applied_migrations)} migraciones aplicadas, "
            f"{len(pendientes)} sin aplicar, {len(tablas)} tablas, "
            f"{len(inertes)} fila(s) sin archivo que no frenan."
        )

        if problemas and opciones["solo_reporte"]:
            # Modo de inspección: el hallazgo se imprime entero, pero el comando termina
            # en 0. Es lo que permite correrlo contra testing o PRD de ECOM —bases que no
            # son nuestras— sin que el código de salida corte el script de quien lo mire.
            self.stdout.write(self.style.ERROR("\n\n".join(problemas)))
            self.stdout.write(self.style.WARNING(f"Solo-reporte: hallazgos arriba, sin cortar. {resumen}"))
            return

        if problemas:
            raise CommandError("\n\n".join(problemas))

        self.stdout.write(self.style.SUCCESS(f"Esquema coherente: {resumen}"))
