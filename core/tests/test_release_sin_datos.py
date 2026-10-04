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

        self.assertIn("Sin datos personales", flujo)
        self.assertIn("scripts/check_datos_personales.py", flujo)

    def test_el_guard_del_release_revisa_el_arbol_publicado(self):
        """RED-01: publish-main tiene que rechazar el release si se cuela un volcado."""
        flujo = (RAIZ / ".github/workflows/publish-main.yml").read_text(encoding="utf-8")

        self.assertIn("scripts/check_datos_personales.py --arbol", flujo)


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

    def test_con_techo_de_tamano_un_archivo_nuevo_grande_se_rechaza(self):
        carpeta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, carpeta, True)
        (carpeta / "padron.csv").write_text("x" * (600 * 1024), encoding="utf-8")

        errores = revisar(["padron.csv"], carpeta, con_techo_de_tamano=True)

        self.assertEqual(len(errores), 1)
        self.assertIn("techo", errores[0])

    def test_sin_techo_de_tamano_el_archivo_grande_pasa(self):
        """Sobre el árbol del release no corre el techo: hay grandes legítimos ya versionados."""
        carpeta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, carpeta, True)
        (carpeta / "vendor.js").write_text("x" * (600 * 1024), encoding="utf-8")

        self.assertEqual(revisar(["vendor.js"], carpeta, con_techo_de_tamano=False), [])
