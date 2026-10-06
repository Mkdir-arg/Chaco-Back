"""RED-17 (b) · Editar una migración ya aplicada no puede cambiar su camino de ida.

`scripts/check_migraciones.py` (Cambio 135) mira solo las migraciones **agregadas**
(`git diff --diff-filter=A`), y lo deja escrito como límite conocido: «editar una
migración ya aplicada no tiene guard automático». No es un olvido: tocarlas hace falta a
veces —el propio Cambio 135 editó diecinueve para ponerles marcas y arreglarles la
reversa— y una regla «no se tocan» habría sido falsa.

El límite verdadero es **el SQL de ida no cambia**. Una fila de `django_migrations` dice
«esto ya corrió»: cualquier diferencia en la ida es esquema que en producción nunca va a
existir, y el CI, que migra desde cero, lo ve en verde.

Verificado contra el motor real en este PR (`mariadb:10.11.19`): subirle de 40 a 50 el
`max_length` de `clave_persona_plan` en `programas.0075` —una migración ya aplicada en
testing de ECOM— sale como un diff de `ALTER TABLE … varchar(40)` a `varchar(50)`;
agregarle un comentario a la misma línea sale en 0.
"""

import importlib.util
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)
GUION = RAIZ / "scripts" / "check_sqlmigrate.py"


def _cargar():
    spec = importlib.util.spec_from_file_location("check_sqlmigrate", GUION)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class LecturaDeRutasTests(SimpleTestCase):
    def setUp(self):
        self.guion = _cargar()

    def test_la_ruta_de_una_migracion_da_app_y_nombre(self):
        coincide = self.guion.RUTA_MIGRACION.match("programas/migrations/0075_enviosiis_vigente.py")

        self.assertIsNotNone(coincide)
        self.assertEqual(coincide.group("app"), "programas")
        self.assertEqual(coincide.group("nombre"), "0075_enviosiis_vigente")

    def test_el_init_y_los_archivos_sueltos_no_son_migraciones(self):
        for ruta in ("programas/migrations/__init__.py", "scripts/check_migraciones.py"):
            with self.subTest(ruta=ruta):
                self.assertIsNone(self.guion.RUTA_MIGRACION.match(ruta))


class NormalizacionTests(SimpleTestCase):
    def setUp(self):
        self.guion = _cargar()

    def test_el_diff_no_es_por_espacios_ni_lineas_en_blanco(self):
        """Reindentar el archivo no cambia el SQL: eso no puede poner el gate en rojo."""
        uno = "BEGIN;\n\nALTER TABLE `x` ADD COLUMN `y` varchar(40) NULL;   \nCOMMIT;"
        otro = "BEGIN;\nALTER TABLE `x` ADD COLUMN `y` varchar(40) NULL;\n\nCOMMIT;"

        self.assertEqual(self.guion.normalizar(uno), self.guion.normalizar(otro))


class ComparacionTests(SimpleTestCase):
    MIGRACION = [("programas", "0075_enviosiis_vigente", "programas/migrations/0075_enviosiis_vigente.py")]

    def setUp(self):
        self.guion = _cargar()

    def _comparar(self, antes, despues):
        return self.guion.comparar(
            self.MIGRACION,
            lambda lado, app, nombre: self.guion.normalizar(antes if lado == "base" else despues),
        )

    def test_una_edicion_que_no_toca_el_sql_pasa(self):
        """Es el caso del Cambio 135: marcas, comentarios y reversa."""
        sql = "ALTER TABLE `programas_enviosiis` ADD COLUMN `clave_persona_plan` varchar(40) NULL;"

        self.assertEqual(self._comparar(sql, sql), [])

    def test_cambiar_el_sql_de_ida_es_un_hallazgo_con_el_diff_adentro(self):
        hallazgos = self._comparar(
            "ALTER TABLE `programas_enviosiis` ADD COLUMN `clave_persona_plan` varchar(40) NULL;",
            "ALTER TABLE `programas_enviosiis` ADD COLUMN `clave_persona_plan` varchar(50) NULL;",
        )

        self.assertEqual(len(hallazgos), 1)
        self.assertIn("0075_enviosiis_vigente.py", hallazgos[0])
        self.assertIn("ya está aplicada en producción", hallazgos[0])
        self.assertIn(
            "-ALTER TABLE `programas_enviosiis` ADD COLUMN `clave_persona_plan` varchar(40) NULL;", hallazgos[0]
        )
        self.assertIn(
            "+ALTER TABLE `programas_enviosiis` ADD COLUMN `clave_persona_plan` varchar(50) NULL;", hallazgos[0]
        )

    def test_agregar_una_operacion_a_una_migracion_aplicada_tambien_sale(self):
        hallazgos = self._comparar(
            "ALTER TABLE `a` ADD COLUMN `x` varchar(40) NULL;",
            "ALTER TABLE `a` ADD COLUMN `x` varchar(40) NULL;\nALTER TABLE `a` DROP COLUMN `z`;",
        )

        self.assertEqual(len(hallazgos), 1)

    def test_sin_migraciones_editadas_no_hay_nada_que_comparar(self):
        self.assertEqual(self.guion.comparar([], lambda *_: []), [])


class LimitesDeclaradosTests(SimpleTestCase):
    def test_el_limite_de_los_runpython_esta_escrito_en_el_guion(self):
        """`sqlmigrate` imprime un `RunPython` como comentario: cambiarle el cuerpo no se ve.

        El límite es real y el gate no lo tapa. Que esté escrito es la diferencia entre un
        hueco conocido y uno que alguien descubre en producción.
        """
        self.assertIn("Límite conocido", GUION.read_text(encoding="utf-8"))
