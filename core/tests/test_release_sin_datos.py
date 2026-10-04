"""Ningún volcado de personas vuelve al repo, al release ni a la imagen (RED-01).

El 04/10/2026 `scripts/DatosPersonas.sql` (respuesta de RENAPER de 10.321 personas,
con domicilio y menores incluidos), `scripts/Aprobados.sql` y `scripts/Localidades.sql`
estaban versionados en un repositorio **público**, viajaban a `main` y al GitLab de
ECOM, y entraban en la imagen de producción por el `COPY . .` del `Dockerfile`.

Este módulo es el «test permanente» de la ficha: fija las cuatro barreras que los
sacaron —`.gitignore`, `.gitattributes`, `.dockerignore` y el verificador compartido—
y se pone rojo si alguna se afloja o si aparece otro volcado. **No lee ni reproduce
ningún dato real**: el único volcado que construye es sintético, con DNI inventados.
"""

import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)

_SPEC = importlib.util.spec_from_file_location("check_datos_personales", RAIZ / "scripts" / "check_datos_personales.py")
check_datos_personales = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_datos_personales)
parece_volcado = check_datos_personales.parece_volcado
revisar = check_datos_personales.revisar

VOLCADOS_DEL_ORGANISMO = (
    "scripts/DatosPersonas.sql",
    "scripts/Aprobados.sql",
    "scripts/Localidades.sql",
)
PLANTILLA = "scripts/aprobados_materias_plantilla.sql"


def _git(*args):
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8")


@unittest.skipUnless(shutil.which("git") and (RAIZ / ".git").exists(), "hace falta el repositorio de git")
class ReleaseSinDatosTests(SimpleTestCase):
    """Las barreras que impiden que un volcado entre al repo o salga en el release."""

    def test_ningun_sql_versionado_tiene_volcado_de_personas(self):
        """El test que nombra la ficha RED-01: sobre los `.sql` que versiona git."""
        versionados = [linea for linea in _git("ls-files", "*.sql").stdout.splitlines() if linea.strip()]

        culpables = [ruta for ruta in versionados if parece_volcado(RAIZ / ruta)]

        self.assertEqual(culpables, [], f"hay volcados de personas versionados: {culpables}")

    def test_los_volcados_del_organismo_no_estan_versionados(self):
        versionados = set(linea for linea in _git("ls-files").stdout.splitlines() if linea.strip())

        presentes = [ruta for ruta in VOLCADOS_DEL_ORGANISMO if ruta in versionados]

        self.assertEqual(presentes, [], "los volcados del organismo volvieron al repo")

    def test_la_plantilla_sigue_versionada(self):
        """Sacar los volcados no puede llevarse el molde sin datos: es el insumo del operador."""
        versionados = set(linea for linea in _git("ls-files").stdout.splitlines() if linea.strip())

        self.assertIn(PLANTILLA, versionados)

    def test_gitignore_ignora_los_sql_de_scripts_menos_la_plantilla(self):
        for ruta in VOLCADOS_DEL_ORGANISMO:
            with self.subTest(ruta=ruta):
                self.assertEqual(_git("check-ignore", "-q", "--no-index", ruta).returncode, 0, f"{ruta} no se ignora")

        self.assertEqual(
            _git("check-ignore", "-q", "--no-index", PLANTILLA).returncode,
            1,
            "la plantilla sin datos no se tiene que ignorar",
        )

    def test_el_release_de_main_no_se_lleva_los_sql_del_organismo(self):
        """`export-ignore` en `.gitattributes`: es lo que mira `git archive` en publish-main."""
        for ruta in VOLCADOS_DEL_ORGANISMO:
            with self.subTest(ruta=ruta):
                salida = _git("check-attr", "export-ignore", "--", ruta).stdout
                self.assertIn("export-ignore: set", salida, f"{ruta} viajaría al release")

        self.assertIn("export-ignore: unset", _git("check-attr", "export-ignore", "--", PLANTILLA).stdout)

    def test_la_imagen_no_se_lleva_los_sql_de_scripts(self):
        """`.dockerignore`: sin esto el `COPY . .` del Dockerfile los mete en la imagen de PRD."""
        reglas = [
            linea.strip()
            for linea in (RAIZ / ".dockerignore").read_text(encoding="utf-8").splitlines()
            if linea.strip() and not linea.startswith("#")
        ]

        self.assertIn("scripts/*.sql", reglas)

    def test_el_gate_del_ci_se_llama_sin_datos_personales(self):
        flujo = (RAIZ / ".github/workflows/pr-datos.yml").read_text(encoding="utf-8")

        self.assertIn("name: Sin datos personales", flujo)
        self.assertIn("scripts/check_datos_personales.py", flujo)

    def test_el_gate_del_ci_corre_tambien_en_push_a_development(self):
        """Hasta RED-20, un push directo a `development` no dispara ningún otro check."""
        flujo = (RAIZ / ".github/workflows/pr-datos.yml").read_text(encoding="utf-8")

        disparadores = flujo[flujo.index("\non:") : flujo.index("\npermissions:")]

        self.assertIn("pull_request:", disparadores)
        self.assertIn("push:", disparadores)
        self.assertEqual(disparadores.count("- development"), 2)

    def test_el_guard_del_release_revisa_el_repo_antes_del_export_ignore_y_el_arbol_despues(self):
        """`git archive` ya aplicó `export-ignore`: mirar solo el release deja un hueco.

        Un `scripts/*.sql` forzado al índice queda fuera del release por el
        `export-ignore` y, aun así, visible en `development`. Lo que lo ve es el pase
        sobre los archivos versionados, y tiene que correr **antes** del `git archive`.
        """
        flujo = (RAIZ / ".github/workflows/publish-main.yml").read_text(encoding="utf-8")

        versionados = flujo.index("check_datos_personales.py --versionados")
        archivo = flujo.index("git archive HEAD")
        arbol = flujo.index("check_datos_personales.py --arbol")

        self.assertLess(versionados, archivo, "el repositorio se revisa antes de aplicar export-ignore")
        self.assertLess(archivo, arbol)

    def test_el_compose_de_produccion_documenta_el_volumen_de_insumos(self):
        """Montarlo es del PM, pero tiene que ser descubrible donde se lee el deploy."""
        compose = (RAIZ / "docker-compose.prod.yml").read_text(encoding="utf-8")

        self.assertIn("# - /srv/datos-siis:/datos-siis:ro", compose)
        self.assertIn("# - DATOS_SIIS_DIR=/datos-siis", compose)


class HeuristicaDeVolcadoTests(SimpleTestCase):
    """Qué distingue un volcado de una plantilla. Todo el material de acá es inventado."""

    def _escribir(self, nombre, contenido):
        carpeta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, carpeta, True)
        archivo = carpeta / nombre
        archivo.write_text(contenido, encoding="utf-8")
        return archivo

    def test_un_volcado_sintetico_de_personas_lo_detecta(self):
        filas = ",\n".join(f"('{30000000 + i}', 'Apellido{i}', 'Calle {i}')" for i in range(150))
        archivo = self._escribir(
            "volcado.sql",
            f"INSERT INTO `personas` (`dni`, `apellido`, `domicilio`) VALUES\n{filas};\n",
        )

        self.assertIsNotNone(parece_volcado(archivo))

    def test_un_volcado_en_formato_mysqldump_lo_detecta(self):
        """`mysqldump` por defecto no emite la lista de columnas: no hay `dni` que leer.

        Era el hueco más probable, porque es el formato que sale de exportar una tabla
        sin pensarlo. Se detecta por contenido: documentos y CUIL distintos.
        """
        filas = ",\n".join(f"('{30000000 + i}','20{30000000 + i}4','Gomez{i}','Calle {i} 100')" for i in range(5000))
        archivo = self._escribir("dump.sql", f"INSERT INTO `t` VALUES\n{filas};\n")

        motivo = parece_volcado(archivo)

        self.assertIsNotNone(motivo)
        self.assertIn("mysqldump", motivo)

    def test_un_mysqldump_con_extended_insert_en_una_sola_linea_lo_detecta(self):
        """`--extended-insert` es el default: las 5.000 tuplas van en UNA línea.

        Contando líneas que *son* una tupla daba 0 y el archivo pasaba entero. Y pesa
        184 KB, bien por debajo del techo de 512 KB, así que tampoco lo salvaba el
        tamaño: es el formato exacto que sale de `mysqldump` sin opciones.
        """
        filas = ",".join(f"('{30000000 + i}','20{30000000 + i}4','Gomez{i}','Calle {i} 100')" for i in range(5000))
        archivo = self._escribir("dump_extended.sql", f"INSERT INTO `t` VALUES {filas};\n")

        motivo = parece_volcado(archivo)

        self.assertLess(archivo.stat().st_size, check_datos_personales.TECHO_BYTES)
        self.assertIsNotNone(motivo)
        self.assertIn("mysqldump", motivo)

    def test_un_insert_en_una_linea_sin_documentos_no_es_un_volcado(self):
        """Contar separadores `),(` no puede volverse un detector de paréntesis."""
        filas = ",".join(f"({i}, 'etiqueta {i}')" for i in range(500))
        archivo = self._escribir("catalogo_una_linea.sql", f"INSERT INTO `catalogo` VALUES {filas};\n")

        self.assertIsNone(parece_volcado(archivo))

    def test_un_padron_en_csv_sin_sql_lo_detecta(self):
        """5.000 DNI en CSV pesan 60 KB: no hay techo de tamaño que los atrape."""
        filas = "\n".join(f"{30000000 + i},Apellido{i},Calle {i} 100" for i in range(5000))
        archivo = self._escribir("padron.csv", f"dni,apellido,domicilio\n{filas}\n")

        motivo = parece_volcado(archivo)

        self.assertIsNotNone(motivo)
        self.assertIn("padrón", motivo)

    def test_un_insert_sin_columnas_y_sin_documentos_no_es_un_volcado(self):
        """El contrapeso de la regla nueva: volumen sí, personas no."""
        filas = ",\n".join(f"({i}, 'etiqueta {i}')" for i in range(300))
        archivo = self._escribir("catalogo.sql", f"INSERT INTO `catalogo` VALUES\n{filas};\n")

        self.assertIsNone(parece_volcado(archivo))

    def test_un_csv_chico_de_catalogo_no_es_un_volcado(self):
        """`programas/data/siis_localidades.csv` y sus hermanos tienen que seguir pasando."""
        filas = "\n".join(f"{i},Localidad {i}" for i in range(500))
        archivo = self._escribir("localidades.csv", f"id,nombre\n{filas}\n")

        self.assertIsNone(parece_volcado(archivo))

    def test_la_plantilla_de_aprobados_no_es_un_volcado(self):
        """Tiene el INSERT con `dni` pero tres filas de ejemplo: es el molde, no los datos."""
        plantilla = RAIZ / PLANTILLA

        self.assertIsNone(parece_volcado(plantilla))

    def test_un_insert_corto_con_dni_no_es_un_volcado(self):
        archivo = self._escribir(
            "chico.sql",
            "INSERT INTO `t` (`dni`) VALUES\n('11111111'),\n('22222222');\n",
        )

        self.assertIsNone(parece_volcado(archivo))

    def test_un_sql_de_esquema_sin_datos_no_es_un_volcado(self):
        archivo = self._escribir("ddl.sql", "CREATE TABLE t (dni VARCHAR(20) PRIMARY KEY);\n")

        self.assertIsNone(parece_volcado(archivo))

    def test_un_archivo_nuevo_grande_se_rechaza(self):
        carpeta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, carpeta, True)
        (carpeta / "padron.bin").write_text("x" * (600 * 1024), encoding="utf-8")

        errores = revisar(["padron.bin"], carpeta)

        self.assertEqual(len(errores), 1)
        self.assertIn("techo", errores[0])

    def test_una_ruta_exenta_pasa_el_techo(self):
        carpeta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, carpeta, True)
        (carpeta / "package-lock.json").write_text("x" * (600 * 1024), encoding="utf-8")

        self.assertEqual(revisar(["package-lock.json"], carpeta), [])


class ExencionesDeTamanoTests(SimpleTestCase):
    """El techo de 512 KB es la red de respaldo: sus agujeros tienen que ser nominales."""

    def test_las_exenciones_son_rutas_exactas_sin_comodines(self):
        """Un glob (`docs/*`) convierte ese directorio en el escondite del próximo volcado."""
        con_comodin = [p for p in check_datos_personales.EXENTOS_TAMANO if any(c in p for c in "*?[")]

        self.assertEqual(con_comodin, [], "las exenciones del techo tienen que ser rutas exactas")

    def test_un_archivo_nuevo_grande_en_un_directorio_exento_no_queda_exento(self):
        """`core/fixtures/padron.json` de 1,7 MB tiene que caer, aunque el catálogo esté exento."""
        carpeta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, carpeta, True)
        (carpeta / "core" / "fixtures").mkdir(parents=True)
        (carpeta / "core" / "fixtures" / "padron.json").write_text("x" * (1700 * 1024), encoding="utf-8")

        errores = revisar(["core/fixtures/padron.json"], carpeta)

        self.assertEqual(len(errores), 1)
        self.assertIn("techo", errores[0])

    @unittest.skipUnless(shutil.which("git") and (RAIZ / ".git").exists(), "hace falta el repositorio de git")
    def test_la_lista_de_exenciones_cubre_todo_lo_grande_que_hay_hoy(self):
        """Si entra otro archivo grande legítimo, se agrega a mano y se revisa en el PR.

        Sin esto la lista se desactualiza en silencio y el primer PR que toque un
        archivo grande no exento se pone rojo sin que se entienda por qué.
        """
        grandes = [
            ruta
            for ruta in _git("ls-files").stdout.splitlines()
            if ruta.strip()
            and (RAIZ / ruta).is_file()
            and (RAIZ / ruta).stat().st_size > check_datos_personales.TECHO_BYTES
        ]

        sin_exencion = [ruta for ruta in grandes if ruta not in check_datos_personales.EXENTOS_TAMANO]

        self.assertEqual(sin_exencion, [], "hay archivos versionados sobre el techo que no están en EXENTOS_TAMANO")
