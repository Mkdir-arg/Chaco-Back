"""RED-58 · `legajos.0007` se puede correr dos veces seguidas.

MySQL y MariaDB no tienen DDL transaccional: una migración con `atomic = False` que se
corta deja el esquema en el estado al que llegó y **sin** fila en `django_migrations`, así
que el reintento vuelve a correr el archivo desde la primera línea.

El escenario medido (dos `DROP FOREIGN KEY` seguidos → `ERROR 1091`): el `MODIFY` del
medio espera el metadata lock de una tabla en uso más que el `read_timeout`, el cliente se
cae con un 2013, el `ALTER` **se aplica igual** en el servidor y el reintento muere en la
primera línea con un 1091 que no dice nada de lo que realmente pasó. OPS-05 sube el
`read_timeout` del `migrate` y hace el corte mucho menos probable; esto hace que, cuando
pase igual, el reintento funcione.

La migración ya está aplicada en los tres ambientes: el arreglo es **preventivo**, y lo
que de verdad se está fijando es la plantilla de `core/migraciones.py` para las próximas
`atomic = False` (ítem 6 del checklist del Anexo A).

Los casos de acá corren contra un `schema_editor` espía que simula `information_schema`,
porque lo que importa es **qué SQL decide mandar** según el estado que encuentra. La
corrida de verdad, dos veces seguidas contra el motor, está en
`core/tests/test_motor_real.py::MigracionReentranteTests` (`@tag("mysql")`).
"""

import importlib
import re

from django.test import SimpleTestCase

from core.migraciones import crear_fk_si_falta, modificar_columna, nombre_de_fk, quitar_fk_si_existe

#: El nombre del módulo empieza con un número, así que no se puede importar con `import`.
MIGRACION = "legajos.migrations.0007_ampliar_uuid_legajos"


class _Features:
    def __init__(self, nativo):
        self.has_native_uuid_field = nativo


class _Cursor:
    def __init__(self, conexion):
        self.conexion = conexion
        self.fila = None

    def __enter__(self):
        return self

    def __exit__(self, *excepcion):
        return False

    def execute(self, sql, parametros=None):
        parametros = list(parametros or [])
        self.conexion.consultas.append((" ".join(sql.split()), parametros))
        if "KEY_COLUMN_USAGE" in sql:
            self.fila = self.conexion.foreign_keys.get(tuple(parametros))
        elif "information_schema.COLUMNS" in sql:
            self.fila = self.conexion.columnas.get(tuple(parametros))
        else:  # pragma: no cover — la migración no consulta nada más
            self.fila = None

    def fetchone(self):
        return self.fila


class _Conexion:
    def __init__(self, nativo, foreign_keys, columnas):
        self.vendor = "mysql"
        self.alias = "default"
        self.features = _Features(nativo)
        self.consultas = []
        #: (tabla, columna) → (nombre,) | None
        self.foreign_keys = foreign_keys
        #: (tabla, columna) → (tipo,) | None
        self.columnas = columnas

    def cursor(self):
        return _Cursor(self)


DROP_FK = re.compile(r"ALTER TABLE (?P<tabla>\w+) DROP FOREIGN KEY (?P<nombre>\w+)", re.IGNORECASE)
ADD_FK = re.compile(
    r"ALTER TABLE (?P<tabla>\w+) ADD CONSTRAINT (?P<nombre>\w+) FOREIGN KEY \((?P<columna>\w+)\)", re.IGNORECASE
)
MODIFY = re.compile(r"ALTER TABLE (?P<tabla>\w+) MODIFY (?P<columna>\w+) (?P<tipo>\w+\(\d+\))", re.IGNORECASE)


class _SchemaEditorEspia:
    """Simula el esquema: registra el DDL **y actualiza** lo que `information_schema`
    contesta después. Sin eso, «correrla dos veces» no probaría nada: la segunda vuelta
    vería el mismo estado que la primera."""

    def __init__(self, *, nativo=True, foreign_keys=None, columnas=None):
        self.connection = _Conexion(nativo, dict(foreign_keys or {}), dict(columnas or {}))
        self.ejecutado = []

    def execute(self, sql, params=()):
        limpio = " ".join(sql.split())
        self.ejecutado.append(limpio)
        self._aplicar(limpio)

    def _aplicar(self, sql):
        coincide = DROP_FK.match(sql)
        if coincide:
            tabla, nombre = coincide.group("tabla"), coincide.group("nombre")
            for clave, valor in list(self.connection.foreign_keys.items()):
                if clave[0] == tabla and valor and valor[0] == nombre:
                    del self.connection.foreign_keys[clave]
            return
        coincide = ADD_FK.match(sql)
        if coincide:
            clave = (coincide.group("tabla"), coincide.group("columna"))
            self.connection.foreign_keys[clave] = (coincide.group("nombre"),)
            return
        coincide = MODIFY.match(sql)
        if coincide:
            clave = (coincide.group("tabla"), coincide.group("columna"))
            self.connection.columnas[clave] = (coincide.group("tipo"),)

    @property
    def ddl(self):
        return self.ejecutado

    def olvidar(self):
        """Vacía el registro de SQL, dejando el estado del esquema como quedó."""
        self.ejecutado = []


FK_ALERTA = ("legajos_alertaciudadano", "legajo_id")
FK_HISTORIAL = ("legajos_historialcontacto", "legajo_id")
COLUMNAS = (
    ("legajos_legajoatencion", "id"),
    ("legajos_alertaciudadano", "legajo_id"),
    ("legajos_historialcontacto", "legajo_id"),
    ("legajos_adjunto", "object_id"),
)


def _estado_sin_migrar():
    return {
        "foreign_keys": {
            FK_ALERTA: ("fk_alerta_real",),
            FK_HISTORIAL: ("fk_historial_real",),
        },
        "columnas": {clave: ("char(32)",) for clave in COLUMNAS},
    }


def _estado_ya_migrado():
    return {
        "foreign_keys": {
            FK_ALERTA: ("fk_alerta_real",),
            FK_HISTORIAL: ("fk_historial_real",),
        },
        "columnas": {clave: ("char(36)",) for clave in COLUMNAS},
    }


def _estado_a_medias():
    """Lo que deja un corte: las FK bajadas y solo algunas columnas ampliadas."""
    columnas = {clave: ("char(32)",) for clave in COLUMNAS}
    columnas[("legajos_legajoatencion", "id")] = ("char(36)",)
    return {"foreign_keys": {}, "columnas": columnas}


class AmpliarUuidReentranteTests(SimpleTestCase):
    def setUp(self):
        self.migracion = importlib.import_module(MIGRACION)

    def _correr(self, estado, nativo=True):
        espia = _SchemaEditorEspia(nativo=nativo, **estado)
        self.migracion.ampliar_uuid_legajos_mysql(None, espia)
        return espia

    def test_desde_cero_hace_el_trabajo_completo(self):
        espia = self._correr(_estado_sin_migrar())

        self.assertEqual(len([sql for sql in espia.ddl if "DROP FOREIGN KEY" in sql]), 2)
        self.assertEqual(len([sql for sql in espia.ddl if "MODIFY" in sql]), 4)
        self.assertEqual(len([sql for sql in espia.ddl if "ADD CONSTRAINT" in sql]), 2)

    def test_correrla_dos_veces_seguidas_no_manda_ningun_alter_la_segunda(self):
        """Era el bug: el segundo `DROP FOREIGN KEY` sobre una FK ya bajada da 1091."""
        espia = self._correr(_estado_sin_migrar())
        espia.olvidar()

        self.migracion.ampliar_uuid_legajos_mysql(None, espia)

        self.assertEqual([sql for sql in espia.ddl if sql.startswith("ALTER")], [])

    def test_sobre_una_base_ya_migrada_no_toca_nada(self):
        espia = self._correr(_estado_ya_migrado())

        self.assertEqual([sql for sql in espia.ddl if sql.startswith("ALTER")], [])

    def test_desde_un_corte_termina_lo_que_falta_y_nada_mas(self):
        espia = self._correr(_estado_a_medias())

        self.assertEqual([sql for sql in espia.ddl if "DROP FOREIGN KEY" in sql], [])
        self.assertEqual(len([sql for sql in espia.ddl if "MODIFY" in sql]), 3)
        self.assertEqual(len([sql for sql in espia.ddl if "ADD CONSTRAINT" in sql]), 2)

    def test_usa_el_nombre_real_de_la_fk_y_no_el_escrito_a_mano(self):
        """Una base restaurada de un dump viejo puede traer otro nombre."""
        espia = self._correr(_estado_sin_migrar())

        bajadas = [sql for sql in espia.ddl if "DROP FOREIGN KEY" in sql]
        self.assertTrue(any("fk_alerta_real" in sql for sql in bajadas))
        self.assertTrue(any("fk_historial_real" in sql for sql in bajadas))

    def test_si_la_fk_no_esta_la_recrea_con_el_nombre_de_django(self):
        espia = self._correr(_estado_a_medias())

        creadas = " ".join(sql for sql in espia.ddl if "ADD CONSTRAINT" in sql)
        self.assertIn(self.migracion.FK_ALERTA, creadas)
        self.assertIn(self.migracion.FK_HISTORIAL, creadas)

    def test_normaliza_los_uuid_aunque_el_modify_ya_estuviera_hecho(self):
        """Si el corte cayó entre el `ALTER` y el `UPDATE`, las filas quedaron a medias."""
        espia = self._correr(_estado_ya_migrado())

        self.assertEqual(len([sql for sql in espia.ddl if sql.startswith("UPDATE")]), 4)

    def test_sin_uuid_nativo_no_normaliza(self):
        """MySQL conserva el formato hex de 32: tocar las filas ahí sería romperlas."""
        espia = self._correr(_estado_sin_migrar(), nativo=False)

        self.assertEqual([sql for sql in espia.ddl if sql.startswith("UPDATE")], [])

    def test_en_otro_motor_no_hace_nada(self):
        espia = _SchemaEditorEspia(**_estado_sin_migrar())
        espia.connection.vendor = "sqlite"

        self.migracion.ampliar_uuid_legajos_mysql(None, espia)

        self.assertEqual(espia.ddl, [])


class PlantillaReentranteTests(SimpleTestCase):
    """`core/migraciones.py` es lo que van a usar las próximas `atomic = False`."""

    def test_nombre_de_fk_devuelve_none_cuando_no_hay(self):
        espia = _SchemaEditorEspia(foreign_keys={})

        self.assertIsNone(nombre_de_fk(espia, "una_tabla", "otra_id"))

    def test_quitar_fk_si_existe_no_toca_nada_si_no_esta(self):
        espia = _SchemaEditorEspia(foreign_keys={})

        self.assertIsNone(quitar_fk_si_existe(espia, "una_tabla", "otra_id"))
        self.assertEqual(espia.ddl, [])

    def test_crear_fk_si_falta_no_duplica(self):
        espia = _SchemaEditorEspia(foreign_keys={("una_tabla", "otra_id"): ("ya_esta",)})

        self.assertFalse(crear_fk_si_falta(espia, "una_tabla", "otra_id", "otra_tabla", "id", "nueva"))
        self.assertEqual(espia.ddl, [])

    def test_modificar_columna_compara_sin_mirar_mayusculas(self):
        espia = _SchemaEditorEspia(columnas={("una_tabla", "col"): ("CHAR(36)",)})

        self.assertFalse(modificar_columna(espia, "una_tabla", "col", "char(36)", "NOT NULL"))
        self.assertEqual(espia.ddl, [])

    def test_modificar_columna_altera_cuando_el_tipo_no_coincide(self):
        espia = _SchemaEditorEspia(columnas={("una_tabla", "col"): ("char(32)",)})

        self.assertTrue(modificar_columna(espia, "una_tabla", "col", "char(36)", "NOT NULL"))
        self.assertEqual(espia.ddl, ["ALTER TABLE una_tabla MODIFY col char(36) NOT NULL"])
