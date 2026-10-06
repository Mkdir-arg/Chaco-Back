"""RED-14 (a) · Una columna que pasa a obligatoria por `AlterField` rompe igual el alta.

El gate estático del Cambio 135 mira `AddField` y no `AlterField`, y el motivo está
escrito en su entrada: sin el estado anterior no se distingue «esta columna pasa a
`NOT NULL` ahora» de un `AlterField` que solo cambia `choices` sobre una columna que ya
lo era —`programas.0075` es exactamente ese caso— y el gate gritaría siempre.

El estado anterior sí existe cuando las migraciones se **ejecutan**, que es lo que hace
el job `migration-roundtrip`: foto de `information_schema` con el esquema de la base,
foto después de las migraciones del PR, y la diferencia. Así se ven los tres casos con la
misma regla y sin falsos positivos:

* una columna nueva que nace `NOT NULL` sin `DEFAULT`;
* una columna que **era** `NULL` y el PR pasa a `NOT NULL`;
* una columna a la que el PR le **saca** el `DEFAULT` que tenía en la base.

Los tres dejan el mismo estado: con el esquema adelantado y el código viejo —lo que deja
un rollback de release— todo `INSERT` del ORM anterior omite la columna y MariaDB con
`STRICT_TRANS_TABLES` rechaza el alta entera (error 1364).

Medido contra `mariadb:10.11.19` en este PR: un `ALTER TABLE programas_formulario MODIFY
datos_identificacion longtext NOT NULL` sobre 200 filas sembradas sale como hallazgo acá
y `scripts/check_migraciones.py` no dice una palabra.
"""

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from core.management.commands.verificar_columnas_obligatorias import (
    _sin_default,
    columnas_declaradas,
    columnas_que_pasan_a_obligatorias,
)


def _columna(nulo=False, default=None, extra=""):
    return {"nulo": nulo, "default": default, "extra": extra}


class DefaultSegunElMotorTests(SimpleTestCase):
    """MariaDB devuelve la **cadena** ``NULL``; MySQL devuelve `NULL` de verdad."""

    def test_los_dos_motores_dicen_lo_mismo(self):
        for valor in (None, "NULL", "null", " NULL "):
            with self.subTest(valor=valor):
                self.assertTrue(_sin_default(valor))

    def test_un_default_de_verdad_no_se_confunde(self):
        for valor in ("'0'", "0", "''", "current_timestamp()"):
            with self.subTest(valor=valor):
                self.assertFalse(_sin_default(valor))


class ColumnasQuePasanAObligatoriasTests(SimpleTestCase):
    def test_una_columna_que_era_null_y_pasa_a_not_null_es_el_agujero_del_gate_estatico(self):
        base = {"programas_formulario": {"dni": _columna(nulo=True)}}
        actual = {"programas_formulario": {"dni": _columna(nulo=False)}}

        hallazgos = columnas_que_pasan_a_obligatorias(base, actual)

        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0][:2], ("programas_formulario", "dni"))
        self.assertIn("era NULL", hallazgos[0][2])

    def test_sacarle_el_default_a_una_columna_not_null_deja_el_mismo_agujero(self):
        base = {"programas_formulario": {"estado": _columna(default="'BORRADOR'")}}
        actual = {"programas_formulario": {"estado": _columna(default=None)}}

        hallazgos = columnas_que_pasan_a_obligatorias(base, actual)

        self.assertEqual(len(hallazgos), 1)
        self.assertIn("se lo saca", hallazgos[0][2])

    def test_una_columna_nueva_not_null_sin_default_en_una_tabla_que_ya_existia(self):
        base = {"programas_formulario": {"id": _columna(extra="auto_increment")}}
        actual = {
            "programas_formulario": {"id": _columna(extra="auto_increment"), "nueva": _columna()},
        }

        hallazgos = columnas_que_pasan_a_obligatorias(base, actual)

        self.assertEqual(len(hallazgos), 1)
        self.assertIn("es nueva", hallazgos[0][2])

    def test_una_tabla_entera_nueva_no_es_el_modo_de_falla(self):
        """El código viejo no conoce la tabla, así que no inserta en ella."""
        hallazgos = columnas_que_pasan_a_obligatorias({}, {"programas_nueva": {"x": _columna()}})

        self.assertEqual(hallazgos, [])

    def test_lo_que_ya_estaba_asi_no_se_reporta(self):
        """La deuda heredada no la trae este PR: el gate solo mira lo que cambia."""
        esquema = {"programas_formulario": {"dni": _columna()}}

        self.assertEqual(columnas_que_pasan_a_obligatorias(esquema, esquema), [])

    def test_una_columna_nullable_nueva_es_justo_lo_que_la_regla_pide(self):
        base = {"t": {}}
        actual = {"t": {"nueva": _columna(nulo=True)}}

        self.assertEqual(columnas_que_pasan_a_obligatorias(base, actual), [])

    def test_las_columnas_que_llena_el_motor_no_cuentan(self):
        """`auto_increment` y las generadas no van en el `INSERT` del ORM viejo tampoco."""
        base = {"t": {"id": _columna(nulo=True)}}
        actual = {"t": {"id": _columna(extra="auto_increment"), "calc": _columna(extra="stored generated")}}

        self.assertEqual(columnas_que_pasan_a_obligatorias(base, actual), [])

    def test_un_not_null_con_default_de_base_es_la_salida_que_la_regla_recomienda(self):
        """`RunSQL(… SET DEFAULT …, state_operations=[])`: el ORM viejo sigue insertando."""
        base = {"t": {"estado": _columna(nulo=True)}}
        actual = {"t": {"estado": _columna(default="'BORRADOR'")}}

        self.assertEqual(columnas_que_pasan_a_obligatorias(base, actual), [])


class MarcaDeSalidaTests(SimpleTestCase):
    def test_la_marca_declara_la_columna_que_nombra(self):
        texto = "# ROLLBACK-OK: «datos_identificacion» la llena el entrypoint antes de servir\n"

        self.assertIn("datos_identificacion", columnas_declaradas([texto]))

    def test_sin_marca_no_hay_nada_declarado(self):
        self.assertEqual(columnas_declaradas(["# CONTRACT: dejó de leerse en la release 1.2\n"]), set())


class ElComandoPideElMotorDeProduccionTests(SimpleTestCase):
    """Lee `information_schema`: en SQLite tiene que decirlo, no medir otra cosa."""

    databases = set()

    def test_en_sqlite_aborta_con_un_mensaje_que_explica_donde_corre(self):
        with self.assertRaises(CommandError) as capturado:
            call_command("verificar_columnas_obligatorias", "--guardar", "no-se-escribe.json")

        self.assertIn("migration-roundtrip", str(capturado.exception))
