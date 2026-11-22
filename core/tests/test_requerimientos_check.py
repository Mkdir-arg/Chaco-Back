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
        # El nombre va completo, como se escriben de verdad (`programas.0075_enviosiis_vigente`):
        # con el sufijo detrás de los cuatro dígitos. Un `programas.0999` pelado tapaba el
        # agujero de la regex, que no reconocía ningún nombre real.
        base = {
            "numero": str(requerimientos.PRIMER_CAMBIO_CON_REVERSION),
            "migracion": "`programas.0999_columna_nueva`",
            "base_de_datos": "Migración `programas.0999_columna_nueva`: agrega `columna_nueva` nullable.",
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

    def test_el_nombre_completo_de_la_migracion_se_reconoce(self):
        """Mutación: con la regex vieja (`\\b` después de los dígitos) esto pasaba en verde."""
        codigo, salida = self._documento(
            [
                self._entrada(
                    migracion="`programas.0076_backfill_dispositivos`",
                    base_de_datos="Agrega una columna nueva; el detalle está en el PR.",
                )
            ]
        )

        self.assertEqual(codigo, 1)
        self.assertIn("programas.0076", salida)

    def test_un_no_aplica_al_lado_de_la_migracion_no_exime_la_entrada(self):
        """La celda nombra una migración **y** dice «no aplica»: manda la migración."""
        codigo, salida = self._documento(
            [
                self._entrada(
                    migracion="`programas.0076_backfill` (el backfill no aplica a dispositivos)",
                    base_de_datos="Agrega una columna nueva, sin nombrar la migración.",
                    reversion="No aplica.",
                )
            ]
        )

        self.assertEqual(codigo, 1)
        self.assertIn("Base de datos", salida)
        self.assertIn("Reversión", salida)

    def test_la_base_de_datos_puede_nombrar_la_migracion_sin_el_sufijo(self):
        """`programas.0076` alcanza para la entrada de `programas.0076_backfill`."""
        codigo, salida = self._documento(
            [
                self._entrada(
                    migracion="`programas.0076_backfill`",
                    base_de_datos="Migración `programas.0076`: agrega `columna_nueva` nullable.",
                )
            ]
        )

        self.assertEqual(codigo, 0, salida)

    def test_una_celda_que_no_dice_ni_una_cosa_ni_la_otra_cae(self):
        """«Pendiente» no es ni una migración ni un «No requiere»: hay que decidirlo."""
        codigo, salida = self._documento([self._entrada(migracion="Pendiente de definir")])

        self.assertEqual(codigo, 1)
        self.assertIn("Migración", salida)

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
            CABECERA.format(filas=FILA.format(numero=numero, migracion="`programas.0999_columna_nueva`"))
            + f"# Cambio {numero} — Prueba\n\n🟢 **HECHO — 06/10/2026**\n\n"
            + "| | |\n|---|---|\n| **Migración** | `programas.0999_columna_nueva` |\n\n"
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


ARCHIVO_NUEVO = """# Cambio {numero} — Prueba {numero}

🟢 **HECHO — 22/11/2026**

| | |
|---|---|
| **Programa / módulo** | Transversal / método |
| **Etiquetas** | `#infra` |
| **Solicitante** | PM — pedido directo |
| **Fecha del pedido** | 22/11/2026 |
| **Migración** | {migracion} |

## Base de datos
{base_de_datos}

## Reversión
{reversion}
"""


class CarpetaDeCambiosTests(SimpleTestCase):
    """Desde el Cambio 549 cada entrada es un archivo `requerimientos/N.md`; el historial está congelado."""

    ULTIMO = requerimientos.ULTIMO_CAMBIO_HISTORICO

    def _registro(self, archivos=None, historial=None):
        """Arma historial + carpeta sintéticos. `archivos` es `{nombre: contenido}`."""
        raiz = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, raiz, True)
        carpeta = raiz / "requerimientos"
        carpeta.mkdir()
        for nombre, contenido in (archivos or {}).items():
            (carpeta / nombre).write_text(contenido, encoding="utf-8")

        historial = historial if historial is not None else [{"numero": "135", "migracion": "No requiere"}]
        filas = "\n".join(FILA.format(**e) for e in historial)
        cuerpo = "".join(
            ENTRADA.format(**{**e, "base_de_datos": "Nada.", "reversion": "No aplica."}) for e in historial
        )
        documento = raiz / "requerimientos.md"
        documento.write_text(CABECERA.format(filas=filas) + cuerpo, encoding="utf-8")
        return documento, carpeta

    def _nuevo(self, numero, **cambios):
        datos = {
            "numero": numero,
            "migracion": "No requiere",
            "base_de_datos": "Ningún cambio de esquema.",
            "reversion": "No aplica.",
        }
        datos.update(cambios)
        return ARCHIVO_NUEVO.format(**datos)

    def _check(self, archivos=None, historial=None):
        documento, carpeta = self._registro(archivos, historial)
        lineas, filas, entradas, vocabulario = requerimientos.leer_documento(documento, carpeta)
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = requerimientos.comando_check(filas, entradas, vocabulario, lineas)
        return codigo, salida.getvalue()

    def test_un_archivo_nuevo_valido_pasa_y_su_fila_sale_de_la_ficha(self):
        numero = str(self.ULTIMO + 1)
        documento, carpeta = self._registro({f"{numero}.md": self._nuevo(numero)})

        lineas, filas, entradas, vocabulario = requerimientos.leer_documento(documento, carpeta)
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = requerimientos.comando_check(filas, entradas, vocabulario, lineas)

        self.assertEqual(codigo, 0, salida.getvalue())
        fila = next(f for f in filas if f.numero == numero)
        self.assertEqual(fila.titulo, f"Prueba {numero}")
        self.assertEqual(fila.programa, "Transversal / método")
        self.assertEqual(fila.etiquetas, ["#infra"])
        self.assertEqual(fila.solicitante, "PM — pedido directo")
        self.assertEqual(fila.pedido, "22/11/2026")
        self.assertIn("HECHO", fila.estado)
        self.assertEqual(fila.migracion, "No requiere")

    def test_el_numero_del_archivo_tiene_que_ser_el_del_titulo(self):
        numero = self.ULTIMO + 1
        codigo, salida = self._check({f"{numero}.md": self._nuevo(str(numero + 1))})

        self.assertEqual(codigo, 1)
        self.assertIn(f"{numero}.md dice `# Cambio {numero + 1}`", salida)

    def test_dos_entradas_con_el_mismo_numero_fallan(self):
        codigo, salida = self._check(historial=[{"numero": "135", "migracion": "No requiere"}] * 2)

        self.assertEqual(codigo, 1)
        self.assertIn("El Cambio 135 tiene más de una entrada", salida)

    def test_una_fila_repetida_en_el_indice_falla(self):
        documento, carpeta = self._registro()
        fila = FILA.format(numero="135", migracion="No requiere")
        documento.write_text(documento.read_text(encoding="utf-8").replace(fila, f"{fila}\n{fila}"), encoding="utf-8")

        lineas, filas, entradas, vocabulario = requerimientos.leer_documento(documento, carpeta)
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = requerimientos.comando_check(filas, entradas, vocabulario, lineas)

        self.assertEqual(codigo, 1)
        self.assertIn("El Cambio 135 figura más de una vez en el índice", salida.getvalue())

    def test_un_archivo_nuevo_no_repite_un_numero_del_historial(self):
        codigo, salida = self._check({"135.md": self._nuevo("135")})

        self.assertEqual(codigo, 1)
        self.assertIn("El Cambio 135 tiene más de una entrada", salida)
        self.assertIn("pertenece al historial", salida)

    def test_un_nombre_con_slug_falla(self):
        numero = str(self.ULTIMO + 1)
        codigo, salida = self._check({f"{numero}-con-slug.md": self._nuevo(numero)})

        self.assertEqual(codigo, 1)
        self.assertIn("el nombre no es `N.md`", salida)

    def test_un_numero_del_rango_del_historial_falla_pero_un_subpedido_pasa(self):
        codigo, salida = self._check({"100.md": self._nuevo("100")})
        self.assertEqual(codigo, 1)
        self.assertIn("pertenece al historial", salida)

        codigo, salida = self._check({"135.1.md": self._nuevo("135.1")})
        self.assertEqual(codigo, 0, salida)

    def test_un_subpedido_sin_su_cambio_madre_falla(self):
        codigo, salida = self._check({"900.1.md": self._nuevo("900.1")})

        self.assertEqual(codigo, 1)
        self.assertIn("cuelga del Cambio 900, que no existe", salida)

    def test_un_cambio_nuevo_escrito_en_el_historial_falla_con_la_pista_de_la_carpeta(self):
        nuevo = str(self.ULTIMO + 1)
        codigo, salida = self._check(historial=[{"numero": nuevo, "migracion": "No requiere"}])

        self.assertEqual(codigo, 1)
        self.assertIn("congelado", salida)
        self.assertIn(f"docs/internal/requerimientos/{nuevo}.md", salida)

    def test_un_subpedido_dentro_de_un_archivo_falla(self):
        numero = str(self.ULTIMO + 1)
        contenido = self._nuevo(numero) + f"\n## {numero}.1 Otro pedido\n\n🟢 **HECHO — 22/11/2026**\n"
        codigo, salida = self._check({f"{numero}.md": contenido})

        self.assertEqual(codigo, 1)
        self.assertIn(f"{numero}.1", salida)
        self.assertIn("su propio archivo", salida)

    def test_la_migracion_sin_reversion_falla_tambien_en_un_archivo_nuevo(self):
        numero = str(self.ULTIMO + 1)
        contenido = self._nuevo(
            numero,
            migracion="`programas.0999_columna_nueva`",
            base_de_datos="Migración `programas.0999_columna_nueva`.",
            reversion="",
        )
        codigo, salida = self._check({f"{numero}.md": contenido})

        self.assertEqual(codigo, 1)
        self.assertIn("Reversión", salida)

    def test_una_etiqueta_fuera_del_vocabulario_falla(self):
        numero = str(self.ULTIMO + 1)
        contenido = self._nuevo(numero).replace("`#infra`", "`#inventada`")
        codigo, salida = self._check({f"{numero}.md": contenido})

        self.assertEqual(codigo, 1)
        self.assertIn("#inventada", salida)

    def test_un_archivo_sin_encabezado_falla(self):
        numero = str(self.ULTIMO + 1)
        codigo, salida = self._check({f"{numero}.md": "Sin título\n"})

        self.assertEqual(codigo, 1)
        self.assertIn("la primera línea no es `# Cambio N — Título`", salida)

    def test_buscar_informa_la_linea_relativa_al_archivo(self):
        numero = str(self.ULTIMO + 1)
        contenido = self._nuevo(numero) + "\nAguja única en la última línea\n"
        documento, carpeta = self._registro({f"{numero}.md": contenido})
        lineas, _filas, entradas, _vocabulario = requerimientos.leer_documento(documento, carpeta)
        esperada = contenido.splitlines().index("Aguja única en la última línea") + 1

        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = requerimientos.comando_buscar("aguja única", lineas, entradas)

        self.assertEqual(codigo, 0)
        self.assertIn(f"{numero}.md L{esperada}:", salida.getvalue())

    def test_una_carpeta_inexistente_no_rompe(self):
        documento, carpeta = self._registro()
        shutil.rmtree(carpeta)

        lineas, filas, entradas, vocabulario = requerimientos.leer_documento(documento, carpeta)
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = requerimientos.comando_check(filas, entradas, vocabulario, lineas)

        self.assertEqual(codigo, 0, salida.getvalue())

    def test_mayor_en_rutas_ignora_slugs_y_ceros_a_la_izquierda(self):
        rutas = [
            "docs/internal/requerimientos/549.md",
            "docs/internal/requerimientos/900-con-slug.md",
            "docs/internal/requerimientos/0950.md",
            "docs/internal/requerimientos/96.37.md",
            "docs/internal/requerimientos/notas.md",
        ]

        self.assertEqual(requerimientos.mayor_en_rutas(rutas), 549)
        self.assertEqual(requerimientos.mayor_en_rutas([]), 0)

    def test_un_nombre_con_ceros_a_la_izquierda_falla(self):
        numero = self.ULTIMO + 1
        codigo, salida = self._check({f"0{numero}.md": self._nuevo(str(numero))})

        self.assertEqual(codigo, 1)
        self.assertIn("el nombre no es `N.md`", salida)

    def test_un_segundo_cambio_dentro_del_archivo_falla_pero_en_un_bloque_de_codigo_no(self):
        numero = str(self.ULTIMO + 1)
        codigo, salida = self._check({f"{numero}.md": self._nuevo(numero) + "\n# Cambio 999 — Otro\n"})
        self.assertEqual(codigo, 1)
        self.assertIn("contiene otro `# Cambio`", salida)

        ejemplo = "\n```markdown\n# Cambio 9 — Título de ejemplo\n```\n"
        codigo, salida = self._check({f"{numero}.md": self._nuevo(numero) + ejemplo})
        self.assertEqual(codigo, 0, salida)

    def test_un_archivo_sin_semaforo_falla(self):
        numero = str(self.ULTIMO + 1)
        contenido = self._nuevo(numero).replace("🟢 **HECHO — 22/11/2026**\n", "")
        codigo, salida = self._check({f"{numero}.md": contenido})

        self.assertEqual(codigo, 1)
        self.assertIn(f"El Cambio {numero} tiene el estado vacío en la ficha", salida)

    def test_un_programa_vacio_falla(self):
        numero = str(self.ULTIMO + 1)
        contenido = self._nuevo(numero).replace("Transversal / método", "")
        codigo, salida = self._check({f"{numero}.md": contenido})

        self.assertEqual(codigo, 1)
        self.assertIn(f"El Cambio {numero} tiene el programa vacío en la ficha", salida)

    def test_sin_etiquetas_el_mensaje_dice_en_la_ficha(self):
        numero = str(self.ULTIMO + 1)
        contenido = self._nuevo(numero).replace("`#infra`", "")
        codigo, salida = self._check({f"{numero}.md": contenido})

        self.assertEqual(codigo, 1)
        self.assertIn(f"El Cambio {numero} no tiene etiquetas en la ficha", salida)

    def test_el_historial_no_admite_entradas_nuevas_aunque_lleven_un_numero_viejo(self):
        """Un `## N.M` con semáforo agregado al archivo congelado es una entrada nueva en el lugar equivocado."""
        documento, carpeta = self._registro()
        lineas, filas, entradas, _vocabulario = requerimientos.leer_documento(documento, carpeta)
        self.assertEqual(requerimientos.problemas_de_estructura(filas, entradas, lineas, congeladas=1), [])

        documento.write_text(
            documento.read_text(encoding="utf-8") + "\n## 135.37 Sub-pedido escrito donde no va\n\n🟢 **HECHO**\n",
            encoding="utf-8",
        )
        lineas, filas, entradas, _vocabulario = requerimientos.leer_documento(documento, carpeta)
        problemas = requerimientos.problemas_de_estructura(filas, entradas, lineas, congeladas=1)

        self.assertTrue(any("está congelado" in p and "N.md" in p for p in problemas), problemas)

    def test_un_historial_dentro_de_una_entrada_existente_sigue_pasando(self):
        documento, carpeta = self._registro()
        documento.write_text(
            documento.read_text(encoding="utf-8") + "\n## Historial\n\nSe corrigió algo el 22/11/2026.\n",
            encoding="utf-8",
        )
        lineas, filas, entradas, _vocabulario = requerimientos.leer_documento(documento, carpeta)

        self.assertEqual(requerimientos.problemas_de_estructura(filas, entradas, lineas, congeladas=1), [])

    def test_siguiente_sin_git_es_el_maximo_mas_uno(self):
        numero = self.ULTIMO + 3
        documento, carpeta = self._registro({f"{numero}.md": self._nuevo(str(numero))})
        _lineas, _filas, entradas, _vocabulario = requerimientos.leer_documento(documento, carpeta)

        self.assertEqual(requerimientos.siguiente_numero(entradas, con_remotas=False), numero + 1)
        _lineas, _filas, entradas, _vocabulario = requerimientos.leer_documento(*self._registro())
        self.assertEqual(requerimientos.siguiente_numero(entradas, con_remotas=False), self.ULTIMO + 1)


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
        archivos = [RAIZ / "docs" / "internal" / "requerimientos.md"]
        archivos += sorted((RAIZ / "docs" / "internal" / "requerimientos").glob("*.md"))

        for archivo in archivos:
            with self.subTest(archivo=archivo.name):
                self.assertFalse(archivo.read_bytes().startswith(b"\xef\xbb\xbf"))
