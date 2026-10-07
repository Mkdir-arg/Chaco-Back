"""Los dos comandos de datos de la Ola 3 PR 2: V2-NEW-05 y P-17 (G1c-08).

- `normalizar_uuid_legajos` vuelve a poner los guiones a los UUID de Legajos después
  de un restore. Sin él, una base restaurada desde un motor sin UUID nativo deja los
  pk en hexadecimal mientras el ORM de MariaDB pregunta con guiones: el detalle del
  legajo responde 404 y no hay ni un error en los logs.
- `listar_dni_no_normalizados` enumera las fichas cargadas con puntos y sus gemelas
  normalizadas. Es de **solo lectura** a propósito: unir dos legajos mueve adjuntos,
  alertas, historial, inscripciones y casos de Becas, y cuál sobrevive no lo decide un
  script (P-17).
"""

from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.test import SimpleTestCase, TestCase, tag

from legajos.management.commands.normalizar_uuid_legajos import COLUMNAS, MIGRACION
from legajos.models import Ciudadano

MOTOR_REAL = connection.vendor == "mysql"


class NormalizarUuidLegajosTests(SimpleTestCase):
    databases = {"default"}

    def _correr(self, *args):
        salida = StringIO()
        call_command("normalizar_uuid_legajos", *args, stdout=salida)
        return salida.getvalue()

    def test_fuera_de_mysql_no_hace_nada_y_lo_dice(self):
        if MOTOR_REAL:
            self.skipTest("Este test describe el camino de SQLite.")

        self.assertIn("no hay nada que normalizar", self._correr())

    def test_las_columnas_son_las_mismas_que_amplia_la_migracion(self):
        """Si `legajos.0007` suma una columna UUID, el comando tiene que verla.

        Las dos listas se comparan por (tabla, columna): la migración además lleva la
        nulabilidad, que acá no hace falta porque el comando no toca el esquema.
        """
        import importlib

        migracion = importlib.import_module(MIGRACION)
        fuente = getattr(migracion, "COLUMNAS", None) or __import__("inspect").getsource(
            migracion.ampliar_uuid_legajos_mysql
        )
        if isinstance(fuente, str):
            # La versión anterior de la migración declara las columnas adentro de la
            # función: se comprueba que las cuatro estén nombradas ahí.
            for tabla, columna in COLUMNAS:
                with self.subTest(tabla=tabla):
                    self.assertIn(tabla, fuente)
                    self.assertIn(columna, fuente)
        else:
            self.assertEqual(sorted((t, c) for t, c, _ in fuente), sorted(COLUMNAS))


@tag("mysql")
class NormalizarUuidLegajosMotorRealTests(TestCase):
    """El comando contra MariaDB/MySQL de verdad: lo corre el job «Motor real»."""

    def setUp(self):
        if not MOTOR_REAL:
            self.skipTest("Necesita MySQL o MariaDB de verdad (DJANGO_TEST_MOTOR + DATABASE_*).")
        super().setUp()

    def _salida(self, *args):
        salida = StringIO()
        call_command("normalizar_uuid_legajos", *args, stdout=salida)
        return salida.getvalue()

    def test_una_base_sana_informa_que_no_hay_nada_que_hacer(self):
        salida = self._salida()

        if connection.features.has_native_uuid_field:
            self.assertIn("están con guiones", salida)
        else:
            self.assertIn("es el formato correcto", salida)

    def test_un_pk_en_hexadecimal_vuelve_a_tener_guiones(self):
        if not connection.features.has_native_uuid_field:
            self.skipTest("MySQL guarda el UUID en hexadecimal: no hay nada que normalizar.")
        from legajos.models import LegajoAtencion

        legajo = LegajoAtencion.objects.create(
            ciudadano=Ciudadano.objects.create(dni="30123456", nombre="A", apellido="B")
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE legajos_legajoatencion SET id = REPLACE(id, '-', '') WHERE id = %s", [str(legajo.pk)]
            )
        self.assertFalse(LegajoAtencion.objects.filter(pk=legajo.pk).exists())

        self._salida()

        self.assertTrue(LegajoAtencion.objects.filter(pk=legajo.pk).exists())

    def test_correrlo_dos_veces_seguidas_deja_lo_mismo(self):
        """Es el paso 3 del runbook de restore: tiene que ser idempotente."""
        primera = self._salida()
        segunda = self._salida()

        self.assertEqual(primera, segunda)


class ListarDniNoNormalizadosTests(TestCase):
    def _correr(self, *args):
        salida = StringIO()
        call_command("listar_dni_no_normalizados", *args, stdout=salida)
        return salida.getvalue()

    def test_sin_dni_sucios_no_reporta_nada(self):
        Ciudadano.objects.create(dni="30123456", nombre="A", apellido="B")

        self.assertIn("Ningún DNI con caracteres no numéricos", self._correr())

    def test_lista_el_dni_con_puntos_y_marca_la_colision(self):
        # `Ciudadano.save()` normaliza desde G1c-08: para reproducir lo que ya está
        # cargado en la base hay que escribir la columna sin pasar por el modelo.
        sucio = Ciudadano.objects.create(dni="12345678", nombre="Con", apellido="Puntos")
        Ciudadano.objects.filter(pk=sucio.pk).update(dni="12.345.678")
        gemelo = Ciudadano.objects.create(dni="12345678", nombre="Sin", apellido="Puntos")

        salida = self._correr()

        self.assertIn("12.345.678", salida)
        self.assertIn(f"colisiona con el ciudadano {gemelo.pk}", salida)
        self.assertIn("1 DNI sin normalizar, 1 con una ficha normalizada ya existente", salida)

    def test_el_comando_no_toca_nada(self):
        sucio = Ciudadano.objects.create(dni="12345678", nombre="Con", apellido="Puntos")
        Ciudadano.objects.filter(pk=sucio.pk).update(dni="12.345.678")

        self._correr()

        sucio.refresh_from_db()
        self.assertEqual(sucio.dni, "12.345.678")

    def test_el_csv_trae_las_columnas_declaradas(self):
        sucio = Ciudadano.objects.create(dni="12345678", nombre="Con", apellido="Puntos")
        Ciudadano.objects.filter(pk=sucio.pk).update(dni="12.345.678")

        salida = self._correr("--csv")

        self.assertEqual(
            salida.splitlines()[0],
            "id,dni_guardado,dni_normalizado,apellido,nombre,colisiona_con,largo_valido",
        )
