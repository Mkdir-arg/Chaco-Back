"""Corre comandos de arranque con un candado de base tomado (OPS-07, RED-19).

Django no toma ningún candado para `migrate` en MySQL/MariaDB. Dos procesos migrando a
la vez —el rolling de Kubernetes, o un `docker compose up` sobre un ambiente que todavía
está arrancando— se pisan: medido contra MariaDB 11.8, uno de los dos muere con 1050
desde base vacía y con 1060 desde base al día, y si se cruzan dentro de una migración de
varias operaciones el esquema queda a medias **sin** fila en `django_migrations`. De ahí
no se sale reintentando el deploy.

La regla sigue siendo la de RED-19 (`RUN_MIGRATIONS=false` en los Deployments y un Job
único que migra, `docker/k8s/README.md`). Esto es la red debajo de la regla: el ambiente
que todavía no la aplicó, y el cruce entre el `migrate` de un pod y el sembrado de otro,
que el Job por sí solo no cubre.

    python manage.py bootstrap_lock --comando "migrate --noinput" --comando seed_datos_base

`GET_LOCK` es un candado **de la conexión**: si el proceso muere, el servidor lo suelta
solo. Eso es exactamente lo que hace falta acá —un pod matado a mitad del bootstrap no
puede dejar bloqueado el deploy siguiente— y es lo que no da una fila de control en una
tabla.

**El candado y el `read_timeout` se tocan.** `SELECT GET_LOCK(nombre, espera)` es una
consulta que bloquea hasta `espera` segundos; con el `read_timeout` de 10 s de producción
el cliente se cae antes (error 2013) y el candado nunca llega a conseguirse. Por eso el
comando se niega a arrancar si la espera no entra holgada en el `read_timeout` de la
conexión: el entrypoint lo invoca con `DB_READ_TIMEOUT` levantado (OPS-05).

**El candado va en una conexión aparte, y no es un detalle.** Ser de la conexión
también significa que se suelta cuando *esa* conexión se cierra, y uno de los comandos
que corren adentro la cierra: `seed_datos_base` llama a `loaddata`, que termina con
`connections[alias].close()` —a propósito, es un workaround de Django para un bug viejo
de MySQL (#7572)—. Con el candado tomado sobre `connections["default"]`, ese `close()`
lo liberaba a mitad del sembrado y otro bootstrap podía entrar; medido con dos
arranques simultáneos sobre una base vacía. Por eso se abre una conexión dedicada que
**nadie más usa**: los comandos siguen trabajando sobre `default` y pueden cerrarla
todas las veces que quieran.
"""

import shlex

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

NOMBRE_POR_DEFECTO = "datanach_bootstrap"
ESPERA_POR_DEFECTO = 900
# Lo que se le deja al `read_timeout` por encima de la espera del candado. No es un
# número fino: alcanza con que la consulta que espera tenga margen para volver con un 0
# en vez de que el cliente corte la conexión.
MARGEN_SEGUNDOS = 5


class Command(BaseCommand):
    help = "Corre comandos de arranque (migrate, seeds) con un candado de base tomado, uno por vez."

    def add_arguments(self, parser):
        parser.add_argument(
            "--nombre",
            default=NOMBRE_POR_DEFECTO,
            help=f"Nombre del candado de MySQL/MariaDB (default: {NOMBRE_POR_DEFECTO}).",
        )
        parser.add_argument(
            "--espera",
            type=int,
            default=ESPERA_POR_DEFECTO,
            help=f"Segundos a esperar por el candado antes de abortar (default: {ESPERA_POR_DEFECTO}).",
        )
        parser.add_argument(
            "--comando",
            action="append",
            dest="comandos",
            default=[],
            metavar='"comando arg…"',
            help="Comando de gestión a correr con el candado tomado. Se puede repetir; corren en orden.",
        )

    def handle(self, *args, **options):
        comandos = [shlex.split(crudo) for crudo in options["comandos"] if crudo.strip()]
        if not comandos:
            self.stdout.write("bootstrap_lock: no hay comandos que correr; no se toma el candado.")
            return

        nombre = options["nombre"]
        if connections["default"].vendor != "mysql":
            self.stdout.write(
                f"AVISO: el motor «{connections['default'].vendor}» no tiene GET_LOCK; los comandos corren sin candado."
            )
            self._correr(comandos)
            return

        self._verificar_margen(options["espera"])
        # Conexión dedicada: ver el encabezado del módulo. `loaddata` cierra
        # `connections["default"]` al terminar y con el candado ahí se soltaba solo.
        candado = connections.create_connection("default")
        try:
            id_conexion = self._tomar_candado(candado, nombre, options["espera"])
            try:
                self._correr(comandos)
            finally:
                self._soltar_candado(candado, nombre, id_conexion)
        finally:
            candado.close()

    def _correr(self, comandos):
        for partes in comandos:
            self.stdout.write(f"Ejecutando python manage.py {' '.join(partes)}")
            call_command(*partes)

    # ── candado ────────────────────────────────────────────────────────────────

    def _tomar_candado(self, candado, nombre, espera):
        """Devuelve el `CONNECTION_ID` de la conexión dedicada que tomó el candado."""
        with candado.cursor() as cursor:
            cursor.execute("SELECT CONNECTION_ID()")
            id_conexion = (cursor.fetchone() or [None])[0]
            cursor.execute("SELECT GET_LOCK(%s, %s)", [nombre, espera])
            obtenido = (cursor.fetchone() or [None])[0]

        if obtenido != 1:
            raise CommandError(
                f"No se pudo tomar el candado «{nombre}» en {espera}s: hay otro proceso corriendo el "
                "bootstrap (otra réplica, el Job de migración o un deploy en curso). No se migró ni se "
                "sembró nada. Esperar a que termine y reintentar; si no termina nunca, mirar quién tiene "
                f"el candado con SELECT IS_USED_LOCK('{nombre}')."
            )
        self.stdout.write(f"Candado «{nombre}» tomado (conexión {id_conexion}).")
        return id_conexion

    def _soltar_candado(self, candado, nombre, id_conexion):
        """Suelta el candado y, si dejó de ser nuestro, dice **qué** pasó exactamente.

        Los dos casos anómalos no son el mismo y el aviso distingue: que lo tenga **otro**
        `CONNECTION_ID` significa que un segundo bootstrap entró mientras este corría; que
        no lo tenga nadie significa que la conexión dedicada se cayó y la exclusión mutua
        dejó de estar garantizada, sin evidencia de que alguien se haya metido.
        """
        with candado.cursor() as cursor:
            cursor.execute("SELECT IS_USED_LOCK(%s)", [nombre])
            duenio = (cursor.fetchone() or [None])[0]
            if duenio == id_conexion:
                cursor.execute("SELECT RELEASE_LOCK(%s)", [nombre])
                self.stdout.write(f"Candado «{nombre}» liberado.")
                return

        if duenio is None:
            self.stdout.write(
                f"AVISO: el candado «{nombre}» ya no estaba tomado al terminar: la conexión que lo "
                "sostenía se cayó durante el bootstrap. No hay señal de que otro proceso haya entrado, "
                "pero la exclusión mutua dejó de estar garantizada desde ese momento."
            )
            return
        self.stdout.write(
            f"AVISO: el candado «{nombre}» lo tiene otra conexión ({duenio}, no la {id_conexion}): "
            "otro bootstrap entró mientras este corría y los dos pudieron migrar o sembrar a la vez."
        )

    def _verificar_margen(self, espera):
        read_timeout = (connections["default"].settings_dict.get("OPTIONS") or {}).get("read_timeout")
        if read_timeout and espera + MARGEN_SEGUNDOS > read_timeout:
            raise CommandError(
                f"La espera del candado ({espera}s) no entra en el read_timeout de la conexión "
                f"({read_timeout}s): `SELECT GET_LOCK` bloquea y el cliente cortaría antes con un 2013, "
                "sin candado y sin migrar. Levantar MIGRATE_DB_READ_TIMEOUT (el entrypoint lo hace) o "
                "bajar --espera."
            )
