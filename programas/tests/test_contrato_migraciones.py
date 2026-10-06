"""RED-14, RED-19 y RED-57 · Contrato de las migraciones.

Tres modos de falla que hoy nadie ve, los tres con el mismo síntoma: el CI en verde
y la base de producción en un estado que no corresponde a ninguna release.

- **RED-14** — Django nunca deja un ``DEFAULT`` en la base para un ``AddField``: lo
  aplica durante el ``ALTER`` y lo quita. Con el esquema adelantado y el código viejo
  —el estado exacto después de un rollback de release— todo ``INSERT`` del ORM viejo
  omite la columna y MariaDB con ``STRICT_TRANS_TABLES`` lo rechaza: *«Field
  'dni_titular' doesn't have a default value»*. El alta de casos responde 500 y el
  backoffice de lectura sigue andando, así que el aviso llega por el territorial.
- **RED-19** — durante un rolling los pods viejos siguen atendiendo: una migración que
  borra o renombra una columna en la misma release da 500 intermitentes. Por eso un
  *contract* se declara (Anexo C de la auditoría).
- **RED-57** — 15 migraciones de datos informan ``OK`` al revertirse y dejan los datos
  a medias, porque su reversa es ``RunPython.noop`` (o una función vacía).

El motor de las tres reglas es ``scripts/check_migraciones.py``, que además corre como
gate en el job ``Migration Check`` sobre las migraciones **nuevas** del PR. Acá se lo
prueba de las dos maneras: contra casos sintéticos (que es donde se ve que la regla
distingue lo bueno de lo malo) y contra las migraciones reales del repo.
"""

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)
GATE = RAIZ / "scripts" / "check_migraciones.py"

_SPEC = importlib.util.spec_from_file_location("check_migraciones", GATE)
check_migraciones = importlib.util.module_from_spec(_SPEC)
# El `@dataclass` del script busca su propio módulo en `sys.modules` para resolver las
# anotaciones: sin registrarlo, el import revienta con un `AttributeError` opaco.
sys.modules["check_migraciones"] = check_migraciones
_SPEC.loader.exec_module(check_migraciones)

# Piso por app: se exige el contrato completo a las migraciones **posteriores** a estas,
# que son las que el repo tenía el 06/10/2026 cuando se escribió el gate. La deuda
# anterior no se reescribe (son migraciones aplicadas en producción); lo que importa es
# que ninguna nueva la agrande. Una app que no figure acá se revisa entera.
#
# ``programas`` apunta a la 0074 a propósito, no a la 0075: la 0075 (``EnvioSIIS``,
# Ola 1) es la primera migración que el contrato protege de verdad y tiene que estar
# adentro del conjunto medido.
DESDE = {
    "conversaciones": "0001",
    "core": "0002",
    "dashboard": "0001",
    "legajos": "0008",
    "programas": "0074",
    "users": "0026",
}


def _migraciones_del_repo():
    """``(app, nombre, ruta)`` de cada migración de una app del proyecto.

    Sale del disco y no de ``MigrationLoader``: la suite corre con
    ``DJANGO_SYNCDB_PROJECT_APPS=True``, que pone ``MIGRATION_MODULES = {app: None}``
    para armar el esquema desde los modelos, así que ``disk_migrations`` viene vacío.
    """
    for ruta in check_migraciones.todas_las_migraciones():
        yield ruta.parent.parent.name, ruta.stem, ruta


def _migraciones_nuevas():
    for app, nombre, ruta in _migraciones_del_repo():
        piso = DESDE.get(app)
        if piso is None or nombre.split("_")[0] > piso:
            yield app, nombre, ruta


class MotorDeReglasTests(SimpleTestCase):
    """Casos sintéticos: cada regla rechaza lo que tiene que rechazar y nada más."""

    def _reglas(self, codigo):
        return sorted(h.regla for h in check_migraciones.revisar_texto(codigo, "0999_prueba.py"))

    def test_una_columna_nueva_not_null_sin_default_de_base_no_pasa(self):
        codigo = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name="formulario",
            name="dni_titular",
            field=models.CharField(default="", max_length=20),
        ),
    ]
"""
        self.assertEqual(self._reglas(codigo), ["EXPAND"])

    def test_una_columna_nueva_nullable_pasa(self):
        codigo = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name="formulario",
            name="dni_titular",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
"""
        self.assertEqual(self._reglas(codigo), [])

    def test_una_columna_not_null_con_default_real_en_la_base_pasa(self):
        """Es la receta del Anexo C: el ``DEFAULT`` queda en la base, no en el ORM."""
        codigo = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name="formulario",
            name="dni_titular",
            field=models.CharField(default="", max_length=20),
        ),
        migrations.RunSQL(
            "ALTER TABLE programas_formulario ALTER COLUMN dni_titular SET DEFAULT ''",
            reverse_sql="ALTER TABLE programas_formulario ALTER COLUMN dni_titular DROP DEFAULT",
            state_operations=[],
        ),
    ]
"""
        self.assertEqual(self._reglas(codigo), [])

    def test_una_columna_not_null_con_db_default_pasa(self):
        """``db_default`` es la misma receta en una línea: Django 5 la escribe en el esquema.

        Sin esto, la única forma de declarar un `DEFAULT` que el checker viera era
        el `RunSQL`, y una migración que ya hacía lo correcto quedaba obligada a
        usar la marca de excepción, que dice lo contrario de lo que pasa.
        """
        codigo = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name="corridasiis",
            name="incompatibles",
            field=models.PositiveIntegerField(db_default=0, default=0),
        ),
    ]
"""
        self.assertEqual(self._reglas(codigo), [])

    def test_el_default_de_base_de_otra_columna_no_sirve(self):
        """Si el ``SET DEFAULT`` no nombra la columna nueva, no la cubre."""
        codigo = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name="formulario",
            name="dni_titular",
            field=models.CharField(default="", max_length=20),
        ),
        migrations.RunSQL(
            "ALTER TABLE programas_formulario ALTER COLUMN otra_cosa SET DEFAULT ''",
            reverse_sql="ALTER TABLE programas_formulario ALTER COLUMN otra_cosa DROP DEFAULT",
            state_operations=[],
        ),
    ]
"""
        self.assertEqual(self._reglas(codigo), ["EXPAND"])

    def test_la_marca_rollback_ok_habilita_la_columna_not_null(self):
        codigo = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        # ROLLBACK-OK: la tabla nace en esta misma release, ninguna release viva inserta.
        migrations.AddField(
            model_name="enviosiis",
            name="vigente",
            field=models.BooleanField(default=False),
        ),
    ]
"""
        self.assertEqual(self._reglas(codigo), [])

    def test_una_tabla_nueva_no_necesita_nada(self):
        """``CreateModel`` es *expand* puro: ningún código viejo inserta ahí."""
        codigo = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.CreateModel(
            name="AltaIntermediaSiis",
            fields=[("id", models.BigAutoField(primary_key=True)), ("dni", models.CharField(max_length=20))],
        ),
    ]
"""
        self.assertEqual(self._reglas(codigo), [])

    def test_un_contract_sin_declarar_no_pasa(self):
        codigo = """
from django.db import migrations

class Migration(migrations.Migration):
    operations = [
        migrations.RemoveField(model_name="segmento", name="siis_segmento_id"),
    ]
"""
        self.assertEqual(self._reglas(codigo), ["CONTRACT"])

    def test_un_contract_declarado_pasa(self):
        codigo = """
from django.db import migrations

class Migration(migrations.Migration):
    operations = [
        # CONTRACT: la columna dejó de leerse en la release 2026.09.30 (dos releases atrás).
        migrations.RemoveField(model_name="segmento", name="siis_segmento_id"),
    ]
"""
        self.assertEqual(self._reglas(codigo), [])

    def test_los_cuatro_tipos_de_contract_se_exigen(self):
        plantilla = """
from django.db import migrations

class Migration(migrations.Migration):
    operations = [
        migrations.{operacion},
    ]
"""
        for operacion in (
            'RemoveField(model_name="segmento", name="x")',
            'DeleteModel(name="Segmento")',
            'RenameField(model_name="segmento", old_name="x", new_name="y")',
            'RenameModel(old_name="Segmento", new_name="Tramo")',
        ):
            with self.subTest(operacion=operacion):
                self.assertEqual(self._reglas(plantilla.format(operacion=operacion)), ["CONTRACT"])

    def test_una_reversa_noop_sin_declarar_no_pasa(self):
        codigo = """
from django.db import migrations

def copiar(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    operations = [
        migrations.RunPython(copiar, migrations.RunPython.noop),
    ]
"""
        self.assertEqual(self._reglas(codigo), ["REVERSA"])

    def test_una_reversa_noop_declarada_pasa(self):
        codigo = """
from django.db import migrations

def copiar(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    operations = [
        # REVERSA-NOOP: al revertir, los segmentos quedan sin siis_segmento_id.
        migrations.RunPython(copiar, migrations.RunPython.noop),
    ]
"""
        self.assertEqual(self._reglas(codigo), [])

    def test_una_reversa_que_es_una_funcion_vacia_cuenta_como_noop(self):
        """El patrón de ``users/0007``: una función con solo docstring no revierte nada."""
        codigo = """
from django.db import migrations

def remapear(apps, schema_editor):
    pass

def noop_reverse(apps, schema_editor):
    \"\"\"No reversible.\"\"\"

class Migration(migrations.Migration):
    operations = [
        migrations.RunPython(remapear, noop_reverse),
    ]
"""
        self.assertEqual(self._reglas(codigo), ["REVERSA"])

    def test_una_reversa_de_verdad_pasa(self):
        codigo = """
from django.db import migrations

def copiar(apps, schema_editor):
    pass

def devolver(apps, schema_editor):
    Modelo = apps.get_model("programas", "Segmento")
    Modelo.objects.update(x=None)

class Migration(migrations.Migration):
    operations = [
        migrations.RunPython(copiar, devolver),
    ]
"""
        self.assertEqual(self._reglas(codigo), [])

    def test_un_runpython_sin_reversa_no_pasa(self):
        """Sin el segundo argumento la migración es irreversible **por omisión**."""
        codigo = """
from django.db import migrations

def copiar(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    operations = [
        migrations.RunPython(copiar),
    ]
"""
        self.assertEqual(self._reglas(codigo), ["REVERSA"])

    def test_un_runpython_irreversible_a_proposito_pasa(self):
        """``None`` explícito es una declaración: ``migrate`` se niega a revertir."""
        codigo = """
from django.db import migrations

def copiar(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    operations = [
        migrations.RunPython(copiar, None),
    ]
"""
        self.assertEqual(self._reglas(codigo), [])

    def test_un_runsql_sin_reverse_sql_no_pasa(self):
        codigo = """
from django.db import migrations

class Migration(migrations.Migration):
    operations = [
        migrations.RunSQL("UPDATE programas_formulario SET estado = 'ENVIADO'"),
    ]
"""
        self.assertEqual(self._reglas(codigo), ["REVERSA"])

    def test_el_hallazgo_dice_archivo_linea_y_que_hacer(self):
        codigo = """
from django.db import migrations

class Migration(migrations.Migration):
    operations = [
        migrations.RemoveField(model_name="segmento", name="x"),
    ]
"""
        hallazgo = check_migraciones.revisar_texto(codigo, "0999_prueba.py")[0]

        self.assertEqual(hallazgo.archivo, "0999_prueba.py")
        self.assertEqual(hallazgo.linea, 6)
        self.assertIn("# CONTRACT:", str(hallazgo))


class GateDeLineaDeComandosTests(SimpleTestCase):
    """El gate del CI: sale con 1 y nombra el archivo."""

    def _correr(self, contenido):
        with tempfile.TemporaryDirectory() as carpeta:
            archivo = Path(carpeta) / "0999_prueba.py"
            archivo.write_text(contenido, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(GATE), str(archivo)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                cwd=RAIZ,
            )

    def test_una_migracion_que_rompe_el_contrato_devuelve_1(self):
        corrida = self._correr(
            "from django.db import migrations, models\n\n"
            "class Migration(migrations.Migration):\n"
            "    operations = [\n"
            '        migrations.AddField(model_name="f", name="c", field=models.CharField(max_length=5)),\n'
            "    ]\n"
        )

        self.assertEqual(corrida.returncode, 1, corrida.stdout + corrida.stderr)
        self.assertIn("EXPAND", corrida.stdout)

    def test_una_migracion_sana_devuelve_0(self):
        corrida = self._correr(
            "from django.db import migrations, models\n\n"
            "class Migration(migrations.Migration):\n"
            "    operations = [\n"
            '        migrations.AddField(model_name="f", name="c", field=models.CharField(max_length=5, null=True)),\n'
            "    ]\n"
        )

        self.assertEqual(corrida.returncode, 0, corrida.stdout + corrida.stderr)


class MigracionesDelRepoTests(SimpleTestCase):
    """Las reglas, contra los archivos reales."""

    def test_columnas_nuevas_toleran_codigo_viejo(self):
        """RED-14. El piso es ``DESDE``: la deuda vieja no se reescribe, no crece."""
        hallazgos = [
            str(h)
            for _, _, ruta in _migraciones_nuevas()
            for h in check_migraciones.revisar_archivo(ruta)
            if h.regla == "EXPAND"
        ]

        self.assertEqual(hallazgos, [], "\n".join(hallazgos))

    def test_las_migraciones_nuevas_declaran_sus_contract(self):
        """RED-19. Un *contract* sin declarar es un 500 intermitente durante el rolling."""
        hallazgos = [
            str(h)
            for _, _, ruta in _migraciones_nuevas()
            for h in check_migraciones.revisar_archivo(ruta)
            if h.regla == "CONTRACT"
        ]

        self.assertEqual(hallazgos, [], "\n".join(hallazgos))

    def test_todas_las_migraciones_son_reversibles_o_lo_declaran(self):
        """RED-57. Esta sí es sobre **todas**: las 15 noop ya llevan su marca."""
        hallazgos = [
            str(h)
            for _, _, ruta in _migraciones_del_repo()
            for h in check_migraciones.revisar_archivo(ruta)
            if h.regla == "REVERSA"
        ]

        self.assertEqual(hallazgos, [], "\n".join(hallazgos))

    def test_el_piso_nombra_migraciones_que_existen(self):
        """Un piso con un número que ya no existe apagaría la regla sin que nadie lo vea."""
        numeros = {}
        for app, nombre, _ in _migraciones_del_repo():
            numeros.setdefault(app, set()).add(nombre.split("_")[0])

        for app, piso in DESDE.items():
            with self.subTest(app=app):
                self.assertIn(piso, numeros.get(app, set()))

    def test_la_0075_del_envio_siis_entra_en_el_conjunto_medido(self):
        """La primera migración que el contrato protege: si el piso sube, se pierde."""
        nuevas = {(app, nombre) for app, nombre, _ in _migraciones_nuevas()}

        self.assertIn(("programas", "0075_enviosiis_vigente"), nuevas)
