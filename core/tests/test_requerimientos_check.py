"""RED-84 · `requerimientos.py --check` mira la sección «Reversión».

La plantilla obligatoria de `docs/internal/requerimientos.md` pide `**Migración**`,
`## Base de datos` y `## Reversión` desde siempre, y el `--check` —que es gate del CI
(job «Contratos del repo», RED-24)— solo verificaba que el índice y las entradas
coincidieran. Una entrada con migración y la sección de reversión vacía pasaba en verde,
y el día del rollback el operador no tiene qué leer: es exactamente el agujero que el
runbook D.4 (RED-60) viene a tapar del otro lado.

El piso es `PRIMER_CAMBIO_CON_REVERSION`: el histórico no se reescribe.
"""

import contextlib
import importlib.util
import io
import shutil
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)
SCRIPT = RAIZ / "scripts" / "requerimientos.py"

_SPEC = importlib.util.spec_from_file_location("requerimientos", SCRIPT)
requerimientos = importlib.util.module_from_spec(_SPEC)
sys.modules["requerimientos"] = requerimientos
_SPEC.loader.exec_module(requerimientos)

CABECERA = """# Requerimientos — archivo vivo

### Etiquetas

| Etiqueta | Qué cubre |
|---|---|
| `#infra` | Infraestructura |

## Índice

| N.º | Requerimiento | Programa / módulo | Etiquetas | Solicitante | Pedido | Estado | Migración |
|---|---|---|---|---|---|---|---|
{filas}

**Notas**

"""

FILA = "| {numero} | Prueba {numero} | Transversal | `#infra` | PM | 06/10/2026 | 🟢 **Hecho** | {migracion} |"

ENTRADA = """# Cambio {numero} — Prueba {numero}

🟢 **HECHO — 06/10/2026**

| | |
|---|---|
| **Programa / módulo** | Transversal |
| **Etiquetas** | `#infra` |
| **Solicitante** | PM |
| **Fecha del pedido** | 06/10/2026 |
| **Migración** | {migracion} |

## Base de datos
{base_de_datos}

## Reversión
{reversion}

"""


class ReversionEnElCheckTests(SimpleTestCase):
    def _documento(self, entradas):
        """Arma un `requerimientos.md` sintético y devuelve `(codigo, salida)` de `--check`."""
        carpeta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, carpeta, True)
        archivo = carpeta / "requerimientos.md"

        filas = "\n".join(FILA.format(numero=e["numero"], migracion=e["migracion"]) for e in entradas)
        cuerpo = "".join(ENTRADA.format(**e) for e in entradas)
        archivo.write_text(CABECERA.format(filas=filas) + cuerpo, encoding="utf-8")

        lineas, filas_leidas, entradas_leidas, vocabulario = requerimientos.leer_documento(archivo)
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = requerimientos.comando_check(filas_leidas, entradas_leidas, vocabulario, lineas)
        return codigo, salida.getvalue()

    def _entrada(self, **cambios):
        base = {
            "numero": str(requerimientos.PRIMER_CAMBIO_CON_REVERSION),
            "migracion": "`programas.0999`",
            "base_de_datos": "Migración `programas.0999`: agrega `columna_nueva` nullable.",
            "reversion": ("1. `migrate programas 0998`.\n2. Se pierde lo cargado en `columna_nueva` desde el deploy."),
        }
        base.update(cambios)
        return base

    def test_una_entrada_con_migracion_y_reversion_completa_pasa(self):
        codigo, salida = self._documento([self._entrada()])

        self.assertEqual(codigo, 0, salida)

    def test_una_entrada_con_migracion_y_reversion_vacia_no_pasa(self):
        codigo, salida = self._documento([self._entrada(reversion="")])

        self.assertEqual(codigo, 1)
        self.assertIn("Reversión", salida)

    def test_una_reversion_de_una_sola_linea_no_alcanza(self):
        """«No aplica» debajo de una migración es justo lo que el runbook no quiere leer."""
        codigo, salida = self._documento([self._entrada(reversion="No aplica.")])

        self.assertEqual(codigo, 1)
        self.assertIn("Reversión", salida)

    def test_la_base_de_datos_tiene_que_nombrar_la_migracion(self):
        codigo, salida = self._documento(
            [self._entrada(base_de_datos="Agrega una columna nueva, sin detalle de la migración.")]
        )

        self.assertEqual(codigo, 1)
        self.assertIn("Base de datos", salida)

    def test_una_entrada_sin_migracion_no_necesita_reversion(self):
        codigo, salida = self._documento(
            [
                self._entrada(
                    migracion="No requiere",
                    base_de_datos="Ningún cambio de esquema.",
                    reversion="No aplica.",
                )
            ]
        )

        self.assertEqual(codigo, 0, salida)

    def test_el_historico_no_se_reescribe(self):
        """Una entrada anterior al piso con la sección vacía sigue pasando."""
        viejo = str(requerimientos.PRIMER_CAMBIO_CON_REVERSION - 1)
        codigo, salida = self._documento([self._entrada(numero=viejo, reversion="")])

        self.assertEqual(codigo, 0, salida)

    def test_la_seccion_que_falta_del_todo_tambien_cae(self):
        carpeta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, carpeta, True)
        archivo = carpeta / "requerimientos.md"
        numero = requerimientos.PRIMER_CAMBIO_CON_REVERSION
        archivo.write_text(
            CABECERA.format(filas=FILA.format(numero=numero, migracion="`programas.0999`"))
            + f"# Cambio {numero} — Prueba\n\n🟢 **HECHO — 06/10/2026**\n\n"
            + "| | |\n|---|---|\n| **Migración** | `programas.0999` |\n\n"
            + "## Implementación\nCualquier cosa.\n",
            encoding="utf-8",
        )

        lineas, filas, entradas, vocabulario = requerimientos.leer_documento(archivo)
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = requerimientos.comando_check(filas, entradas, vocabulario, lineas)

        self.assertEqual(codigo, 1)
        self.assertIn("Reversión", salida.getvalue())
        self.assertIn("Base de datos", salida.getvalue())


class ArchivoRealTests(SimpleTestCase):
    """El archivo del repo pasa su propio gate (es el que corre en el CI)."""

    def test_el_check_del_repo_esta_en_ok(self):
        lineas, filas, entradas, vocabulario = requerimientos.leer_documento()
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = requerimientos.comando_check(filas, entradas, vocabulario, lineas)

        self.assertEqual(codigo, 0, salida.getvalue())

    def test_el_archivo_no_empieza_con_bom(self):
        """Un BOM al principio rompe el parseo del índice y nadie lo ve hasta el CI."""
        crudo = (RAIZ / "docs" / "internal" / "requerimientos.md").read_bytes()

        self.assertFalse(crudo.startswith(b"\xef\xbb\xbf"))
