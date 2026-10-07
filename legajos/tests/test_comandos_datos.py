"""Los dos comandos de datos de la Ola 3 PR 2: V2-NEW-05 y P-17 (G1c-08).

- `normalizar_uuid_legajos` vuelve a poner los UUID de Legajos en el formato que el ORM
  consulta en este motor, después de un restore. Sin él, una base restaurada desde un
  motor con el otro formato deja los pk donde el ORM no los busca: el detalle del legajo
  responde 404 y no hay ni un error en los logs.
- `listar_dni_no_normalizados` enumera las fichas que el PR frena —las cargadas con
  separadores y las numéricas de largo inválido— y sus gemelas normalizadas. Es de
  **solo lectura** a propósito: unir dos legajos mueve adjuntos, alertas, historial,
  inscripciones y casos de Becas, y cuál sobrevive no lo decide un script (P-17).
"""

from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.test import SimpleTestCase, TestCase, TransactionTestCase, tag

from legajos.management.commands import normalizar_uuid_legajos as comando_uuid
from legajos.management.commands.listar_dni_no_normalizados import COLUMNAS as COLUMNAS_LISTADO
from legajos.models import AlertaCiudadano, Ciudadano, LegajoAtencion

MOTOR_REAL = connection.vendor == "mysql"


def _correr_uuid(*args):
    salida = StringIO()
    call_command("normalizar_uuid_legajos", *args, stdout=salida)
    return salida.getvalue()


class NormalizarUuidLegajosTests(SimpleTestCase):
    databases = {"default"}

    def test_fuera_de_mysql_no_hace_nada_y_lo_dice(self):
        if MOTOR_REAL:
            self.skipTest("Este test describe el camino de SQLite.")

        self.assertIn("no hay nada que normalizar", _correr_uuid())

    def test_las_columnas_y_las_foreign_keys_son_las_de_la_migracion(self):
        """Si `legajos.0007` suma una columna UUID o una FK, el comando tiene que verla.

        El comando le pide el SQL y los nombres a la migración (`_normalizar_uuid`,
        `FK_ALERTA`, `FK_HISTORIAL`) en vez de copiarlos; lo que sí declara aparte es
        **qué** columnas mira, y eso es lo que se cruza acá.
        """
        import inspect

        migracion = comando_uuid.migracion()
        fuente = inspect.getsource(migracion)

        for tabla, columna in comando_uuid.COLUMNAS:
            with self.subTest(tabla=tabla, columna=columna):
                self.assertIn(tabla, fuente)
                self.assertIn(columna, fuente)
        self.assertEqual(
            {tabla: comando_uuid.nombre_por_defecto(tabla) for tabla, _ in comando_uuid.FOREIGN_KEYS},
            {
                "legajos_alertaciudadano": migracion.FK_ALERTA,
                "legajos_historialcontacto": migracion.FK_HISTORIAL,
            },
        )

    def test_el_sql_que_normaliza_es_el_de_la_migracion(self):
        """No hay una copia del `UPDATE`: el comando llama a la misma función."""
        self.assertIs(
            comando_uuid.migracion()._normalizar_uuid,
            __import__("importlib").import_module(comando_uuid.MIGRACION)._normalizar_uuid,
        )


@tag("mysql")
class NormalizarUuidLegajosMotorRealTests(TransactionTestCase):
    """El comando contra MariaDB/MySQL de verdad: lo corre el job «Motor real».

    Va sobre `TransactionTestCase` y no `TestCase` por dos motivos que se tocan: el
    comando abre un `schema_editor` para el DDL de las foreign keys —que adentro de la
    transacción de un `TestCase` tira `TransactionManagementError`— y el escenario que
    se reproduce es justamente el de un restore, donde las filas están commiteadas.
    """

    available_apps = None

    def setUp(self):
        if not MOTOR_REAL:
            self.skipTest("Necesita MySQL o MariaDB de verdad (DJANGO_TEST_MOTOR + DATABASE_*).")
        super().setUp()
        self.con_guiones = connection.features.has_native_uuid_field
        self.largo_viejo = 32 if self.con_guiones else 36

    def _estado_de_restore(self):
        """Un legajo con el pk en el formato equivocado y una alerta que lo referencia.

        Es lo que deja un restore de un dump del otro motor: el `UPDATE` sobre
        `legajos_legajoatencion.id` con las FK puestas muere con un 1451.
        """
        ciudadano = Ciudadano.objects.create(dni="30123456", nombre="A", apellido="B")
        legajo = LegajoAtencion.objects.create()
        alerta = AlertaCiudadano.objects.create(
            ciudadano=ciudadano,
            legajo=legajo,
            tipo=AlertaCiudadano.TipoAlerta.RIESGO_ALTO,
            prioridad=AlertaCiudadano.Prioridad.ALTA,
            mensaje="alerta del restore",
        )
        # El valor tal cual lo escribió el ORM en **este** motor, que es el que hay que
        # buscar para romperlo: con guiones en MariaDB 10.7+, hexadecimal en MySQL.
        guardado = str(legajo.pk) if self.con_guiones else legajo.pk.hex
        with connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            for tabla, columna in (
                ("legajos_legajoatencion", "id"),
                ("legajos_alertaciudadano", "legajo_id"),
            ):
                cursor.execute(
                    f"UPDATE {tabla} SET {columna} = {_al_formato_viejo(columna, self.con_guiones)} "
                    f"WHERE {columna} = %s",
                    [guardado],
                )
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        return legajo, alerta

    def test_el_pk_en_el_formato_viejo_vuelve_al_que_el_orm_consulta(self):
        """El BLOCKER de la ronda 1: con la alerta puesta, el `UPDATE` daba 1451."""
        legajo, alerta = self._estado_de_restore()
        self.assertFalse(LegajoAtencion.objects.filter(pk=legajo.pk).exists())

        salida = _correr_uuid("--aplicar")

        self.assertIn("fila(s) normalizadas", salida)
        self.assertTrue(LegajoAtencion.objects.filter(pk=legajo.pk).exists())
        self.assertEqual(AlertaCiudadano.objects.get(pk=alerta.pk).legajo_id, legajo.pk)

    def test_las_dos_foreign_keys_quedan_puestas(self):
        """Dejarlas caídas es peor que no haber normalizado."""
        self._estado_de_restore()

        _correr_uuid("--aplicar")

        with connection.cursor() as cursor:
            for tabla, columna in comando_uuid.FOREIGN_KEYS:
                with self.subTest(tabla=tabla):
                    self.assertIsNotNone(comando_uuid.fk_puesta(cursor, tabla, columna))

    def test_sin_aplicar_informa_y_no_escribe_nada(self):
        legajo, _ = self._estado_de_restore()

        salida = _correr_uuid()

        self.assertIn("Nada se escribió", salida)
        self.assertFalse(LegajoAtencion.objects.filter(pk=legajo.pk).exists())

    def test_correrlo_dos_veces_seguidas_deja_lo_mismo(self):
        """Es el paso 3 del runbook de restore: tiene que ser idempotente."""
        self._estado_de_restore()
        _correr_uuid("--aplicar")

        primera = _correr_uuid("--aplicar")
        segunda = _correr_uuid("--aplicar")

        self.assertIn("están en el formato correcto", primera)
        self.assertEqual(primera, segunda)

    def test_una_base_sana_informa_que_no_hay_nada_que_hacer(self):
        LegajoAtencion.objects.create()

        self.assertIn("están en el formato correcto", _correr_uuid())


def _al_formato_viejo(columna, con_guiones):
    """SQL que deja ``columna`` en el formato que **no** consulta el ORM de este motor.

    Es cómo se arma el estado de un restore cruzado: en MariaDB 10.7+ el formato bueno
    es el de 36 con guiones y el viejo es el hexadecimal de 32; en MySQL es al revés.
    """
    if con_guiones:
        return f"REPLACE({columna}, '-', '')"
    return (
        f"CONCAT(SUBSTRING({columna}, 1, 8), '-', SUBSTRING({columna}, 9, 4), '-', "
        f"SUBSTRING({columna}, 13, 4), '-', SUBSTRING({columna}, 17, 4), '-', "
        f"SUBSTRING({columna}, 21, 12))"
    )


class ListarDniNoNormalizadosTests(TestCase):
    def _correr(self, *args):
        salida = StringIO()
        call_command("listar_dni_no_normalizados", *args, stdout=salida)
        return salida.getvalue()

    def _con_dni(self, dni, nombre="Con", apellido="Puntos"):
        """Escribe la columna sin pasar por `save()`, que desde G1c-08 normaliza.

        Es la única forma de reproducir lo que ya está cargado en la base.
        """
        ciudadano = Ciudadano.objects.create(dni=f"9{Ciudadano.objects.count():07d}", nombre=nombre, apellido=apellido)
        Ciudadano.objects.filter(pk=ciudadano.pk).update(dni=dni)
        ciudadano.refresh_from_db()
        return ciudadano

    def test_sin_dni_problematicos_no_reporta_nada(self):
        Ciudadano.objects.create(dni="30123456", nombre="A", apellido="B")

        self.assertIn("Ningún DNI fuera de la regla única", self._correr())

    def test_lista_el_dni_con_separadores_y_marca_la_colision(self):
        self._con_dni("12.345.678")
        gemelo = Ciudadano.objects.create(dni="12345678", nombre="Sin", apellido="Puntos")

        salida = self._correr()

        self.assertIn("[separadores]", salida)
        self.assertIn(f"colisiona con el ciudadano {gemelo.pk}", salida)
        self.assertIn("1 con separadores", salida)

    def test_lista_tambien_los_numericos_de_largo_invalido(self):
        """La otra mitad: son justo los que este PR frena en el alta a SIIS.

        El barrido por `[^0-9]` no los veía, y son los que el PM necesita contar
        antes del deploy.
        """
        self._con_dni("123456", nombre="Corto")
        self._con_dni("1234567890", nombre="Largo")
        Ciudadano.objects.create(dni="30123456", nombre="Bien", apellido="Formado")

        salida = self._correr()

        self.assertEqual(salida.count("[largo]"), 2)
        self.assertIn("2 con un largo fuera de (7, 8)", salida)
        self.assertNotIn("Bien", salida)

    def test_un_dni_puede_estar_mal_por_los_dos_motivos(self):
        self._con_dni("1.234.56")

        self.assertIn("[separadores+largo]", self._correr())

    def test_la_salida_de_pantalla_enmascara_el_documento(self):
        """Es un listado para mirar: alcanza con reconocer la ficha y tener su id."""
        ciudadano = self._con_dni("12.345.678")

        salida = self._correr()

        self.assertNotIn("12.345.678", salida)
        self.assertIn("12******78", salida)
        self.assertIn(str(ciudadano.pk), salida)

    def test_el_csv_trae_las_columnas_declaradas_y_el_documento_entero(self):
        """El CSV es el insumo con el que el área cruza las fichas (P-17)."""
        self._con_dni("12.345.678")

        salida = self._correr("--csv")

        self.assertEqual(salida.splitlines()[0], ",".join(COLUMNAS_LISTADO))
        self.assertIn("12.345.678", salida)

    def test_el_comando_no_toca_nada(self):
        sucio = self._con_dni("12.345.678")

        self._correr()

        sucio.refresh_from_db()
        self.assertEqual(sucio.dni, "12.345.678")
