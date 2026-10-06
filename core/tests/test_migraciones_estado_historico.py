"""RED-17 (2) · Las migraciones de datos se prueban con los modelos de su momento.

Cuatro archivos de tests ejercitaban la función de una migración pasándole
`django.apps.apps` —los modelos **vivos**—, así que una migración que usa un campo
agregado después de ella pasaba en verde. El repo ya pagó ese modo de falla: `0a785d75`
(26/08) arregló una `0052` que murió en el deploy con `padron_archivo` NULL.

Acá se fija lo que esos cuatro archivos no pueden fijar solos: que el estado histórico de
**toda** migración del repo se pueda construir, y que las funciones de datos que los
tests ejercitan sigan corriendo contra el registro de su momento y no contra el de hoy.
"""

import ast
import re
from pathlib import Path

from django.apps import apps as apps_vivas
from django.conf import settings
from django.db.migrations.loader import MigrationLoader
from django.test import SimpleTestCase, override_settings

from core.tests.historico import estado_historico

RAIZ = Path(settings.BASE_DIR)
APPS_DEL_PROYECTO = ("users", "core", "dashboard", "legajos", "conversaciones", "portal", "programas")
NOMBRE_DE_MIGRACION = re.compile(r"^\d{4}_.+$")

# Las migraciones de datos que el repo ejercita con tests propios. La tupla es
# `(app, migración, modelo que su función toca)`.
EJERCITADAS = (
    ("users", "0007_remapear_permisos_becas", "Capacidad"),
    ("users", "0025_administrador_relevamiento_publico", "Capacidad"),
    ("programas", "0012_crear_programas_dispositivos_merenderos", "Programa"),
    ("programas", "0063_sembrar_catalogo_protegido", "GrupoRequisito"),
)


def _migraciones_del_repo():
    for app in APPS_DEL_PROYECTO:
        carpeta = RAIZ / app / "migrations"
        for ruta in sorted(carpeta.glob("*.py")):
            if NOMBRE_DE_MIGRACION.match(ruta.stem):
                yield app, ruta.stem, ruta


def _modelos_que_nombra(ruta):
    """Los `(app, Modelo)` de cada `apps.get_model("app", "Modelo")` del archivo."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    nombrados = set()
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call) or not isinstance(nodo.func, ast.Attribute):
            continue
        if nodo.func.attr != "get_model" or len(nodo.args) != 2:
            continue
        if all(isinstance(arg, ast.Constant) and isinstance(arg.value, str) for arg in nodo.args):
            nombrados.add((nodo.args[0].value, nodo.args[1].value))
    return nombrados


class EstadoHistoricoTests(SimpleTestCase):
    def test_el_estado_historico_de_cada_migracion_del_repo_se_puede_construir(self):
        """Si el grafo se rompe, se rompe acá y no en el `migrate` de producción.

        `makemigrations --check` no lo ve: valida que no falten migraciones, no que las
        que hay compongan un estado.
        """
        with override_settings(MIGRATION_MODULES={}):
            loader = MigrationLoader(None, ignore_no_migrations=True)
            nodos = [clave for clave in loader.graph.nodes if clave[0] in {app for app, _, _ in EJERCITADAS}]

        self.assertTrue(nodos, "el loader no encontró ninguna migración del proyecto")
        for app, nombre in sorted(nodos):
            with self.subTest(migracion=f"{app}.{nombre}"):
                self.assertIsNotNone(estado_historico(app, nombre, al_final=True))

    def test_el_registro_historico_no_es_el_de_hoy(self):
        """Es la diferencia que hace útil al helper: si fueran lo mismo, no mediría nada."""
        historico = estado_historico("programas", "0012_crear_programas_dispositivos_merenderos")

        campos_de_entonces = {campo.name for campo in historico.get_model("programas", "Programa")._meta.get_fields()}
        campos_de_hoy = {campo.name for campo in apps_vivas.get_model("programas", "Programa")._meta.get_fields()}

        self.assertNotEqual(campos_de_entonces, campos_de_hoy)
        self.assertTrue(campos_de_hoy - campos_de_entonces, "el modelo de hoy tendría que tener campos nuevos")

    def test_cada_migracion_de_datos_con_test_propio_existe_en_su_estado(self):
        for app, migracion, modelo in EJERCITADAS:
            with self.subTest(migracion=f"{app}.{migracion}"):
                historico = estado_historico(app, migracion)

                self.assertIsNotNone(historico.get_model(app, modelo))

    def test_ninguna_migracion_usa_un_modelo_que_todavia_no_existia(self):
        """`apps.get_model("programas", "X")` con una `X` creada después revienta en el deploy.

        Hacia adelante, `migrate` desde cero recorre las migraciones **en orden**: una que
        nombra un modelo posterior pasa el CI de hoy —que arma el esquema desde los
        modelos y no ejecuta nada— y muere en el initContainer de producción. No hace
        falta base para verlo: es el estado histórico contra el texto del archivo.
        """
        for app, nombre, ruta in _migraciones_del_repo():
            nombrados = _modelos_que_nombra(ruta)
            if not nombrados:
                continue
            with self.subTest(migracion=f"{app}.{nombre}"):
                # `al_final=True`: una migración puede crear el modelo y usarlo después,
                # en el mismo archivo.
                historico = estado_historico(app, nombre, al_final=True)
                for etiqueta, modelo in sorted(nombrados):
                    with self.subTest(modelo=f"{etiqueta}.{modelo}"):
                        try:
                            historico.get_model(etiqueta, modelo)
                        except LookupError as error:  # pragma: no cover - el test es el mensaje
                            self.fail(f"{app}.{nombre} usa un modelo que no existía todavía: {error}")


class LosTestsDeMigracionUsanElRegistroHistoricoTests(SimpleTestCase):
    """Ratchet: los cuatro archivos que la ficha nombra no pueden volver a `apps` vivas.

    Es una lectura de texto a propósito. Lo que se degrada con el tiempo no es el
    comportamiento —los tests seguirían pasando— sino lo que miden: alcanza con que
    alguien escriba `migracion.funcion(apps, None)` de nuevo para que vuelva el agujero.
    """

    # Los dos de `users` corren con el registro histórico. Los dos de `programas` no
    # pueden: la suite arma el esquema desde los modelos de hoy
    # (`DJANGO_SYNCDB_PROJECT_APPS`), así que un modelo de entonces escribe un `INSERT`
    # sin las columnas agregadas después y la tabla de hoy las exige (`NOT NULL
    # constraint failed: programas_programa.umbral_disponibilidad_verde`). Eso no es un
    # defecto del test: es RED-14 visto desde adentro. Lo que sí se verifica para todas
    # es `test_ninguna_migracion_usa_un_modelo_que_todavia_no_existia`, que no toca base.
    CONVERTIDOS = (
        "users/tests/test_migracion_becas.py",
        "users/tests/test_migracion_administrador_publico.py",
    )
    CON_MOTIVO_ESCRITO = (
        "programas/tests/test_migracion_catalogo.py",
        "programas/tests/test_dispositivos_migrations.py",
    )

    def test_ninguno_le_pasa_el_registro_vivo_a_la_funcion_de_la_migracion(self):
        for archivo in self.CONVERTIDOS:
            with self.subTest(archivo=archivo):
                texto = (RAIZ / archivo).read_text(encoding="utf-8")

                self.assertIn("estado_historico", texto)
                self.assertNotIn("from django.apps import apps", texto)

    def test_los_que_siguen_con_el_registro_vivo_dicen_por_que(self):
        """Sin el motivo escrito, el próximo que lea la ficha lo «arregla» y vuelve el rojo."""
        for archivo in self.CON_MOTIVO_ESCRITO:
            with self.subTest(archivo=archivo):
                texto = (RAIZ / archivo).read_text(encoding="utf-8")

                self.assertIn("RED-17", texto)
                self.assertIn("umbral_disponibilidad_verde", texto)
