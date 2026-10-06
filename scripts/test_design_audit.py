"""Contrato de `design_audit.py` que se puede verificar sin Django.

Corre en el job «Design Agent Contract» con el Python pelado del runner (el
script es solo stdlib). Las reglas P1, el ratchet y los marcadores tienen su
batería completa en `core/tests/test_design_audit_estructura.py`, que corre en
Backend CI.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import design_audit


class DesignAuditGeneratedAssetsTests(unittest.TestCase):
    def test_no_audita_el_css_generado_por_tailwind(self) -> None:
        generated_css = Path(design_audit.REPO, "static", "custom", "css", "tailwind.css")

        self.assertEqual(list(design_audit.iter_files([generated_css])), [])

    def test_no_audita_la_documentacion(self) -> None:
        # `docs/` guarda anexos y la línea base del agente de diseño, que incluye
        # templates generados a propósito fuera de canon.
        doc = Path(design_audit.REPO, "docs", "internal")

        self.assertEqual(list(design_audit.iter_files([doc])), [])


class DecodificadorTests(unittest.TestCase):
    """FE-13: el parser de identificadores CSS."""

    def test_twbuild_reconoce_valores_arbitrarios_con_coma(self) -> None:
        """RS-R6-08: los dos TWBUILD falsos que bloqueaban el hook.

        Tailwind escapa la coma de un valor arbitrario como `\\2c ` (hex + un
        espacio terminador). Leído a secas, el nombre de la clase se cortaba ahí
        y la clase quedaba marcada como «falta en el build» aunque estuviera.
        """
        css = r".h-\[clamp\(1rem\2c 2rem\)\]{height:1rem}.xl\:grid-cols-\[minmax\(0\2c 1fr\)_auto\]{}"
        declaradas = design_audit.clases_css(css)

        self.assertIn("h-[clamp(1rem,2rem)]", declaradas)
        self.assertIn("xl:grid-cols-[minmax(0,1fr)_auto]", declaradas)

    def test_escapes_literales(self) -> None:
        self.assertIn("xl:top-6", design_audit.clases_css(r".xl\:top-6{top:1.5rem}"))
        self.assertIn("w-1/2", design_audit.clases_css(r".w-1\/2{width:50%}"))

    def test_los_dos_falsos_positivos_historicos_ya_no_aparecen(self) -> None:
        """Las dos clases reales del repo que TWBUILD reportaba mal (Cambio 95)."""
        declaradas = design_audit._clases_del_build()
        if declaradas is None:  # sin build committeado no hay nada que verificar
            self.skipTest("falta static/custom/css/tailwind.css")
        for clase in ("h-[clamp(12rem,calc(100dvh-31rem),28rem)]", "xl:grid-cols-[minmax(0,1fr)_auto]"):
            self.assertIn(clase, declaradas)


class RatchetTests(unittest.TestCase):
    RUTA = "legajos/templates/legajos/x.html"

    def test_no_reporta_la_deuda_preexistente(self) -> None:
        base = '<div class="bg-gray-200">viejo</div>'
        actual = base + '\n<p class="text-body">nuevo</p>'

        self.assertEqual(design_audit.nuevos(base, actual, self.RUTA), [])

    def test_reporta_lo_que_agrega_la_edicion(self) -> None:
        base = '<div class="bg-gray-200">viejo</div>'
        actual = base + '\n<p class="text-gray-900">nuevo</p>'

        hallazgos = design_audit.nuevos(base, actual, self.RUTA)

        self.assertEqual([f[2] for f in hallazgos], ["RAWPALETTE"])
        self.assertEqual(hallazgos[0][1], 2)

    # Un template real cuyos bytes UTF-8 incluyen 0x90, que en cp1252 **no existe**:
    # ahí es donde `git show` sin `encoding` explícito revienta. No alcanza con un
    # archivo "con tildes" (`á` es C3 A1 y cp1252 lo decodifica mal pero no falla).
    TEMPLATE_NO_CP1252 = "programas/templates/programas/merenderos/detail.html"
    BYTES_SIN_CP1252 = {0x81, 0x8D, 0x8F, 0x90, 0x9D}

    def _template_de_referencia(self) -> Path:
        ruta = design_audit.REPO / self.TEMPLATE_NO_CP1252
        if not ruta.exists():
            self.skipTest(f"falta {self.TEMPLATE_NO_CP1252}")
        crudo = ruta.read_bytes()
        # Si el archivo deja de tener uno de esos bytes, el test deja de probar nada:
        # mejor que falle acá y se elija otro de la lista que pasar en verde vacío.
        self.assertTrue(
            self.BYTES_SIN_CP1252 & set(crudo),
            f"{self.TEMPLATE_NO_CP1252} ya no tiene bytes indecodificables en cp1252: "
            "elegir otro template para este test",
        )
        return ruta

    def test_git_devuelve_el_contenido_aunque_no_se_pueda_decodificar_en_cp1252(self) -> None:
        """Sin `encoding` explícito, en Windows `git show` se decodifica en cp1252.

        El hilo lector de `subprocess` moría con `UnicodeDecodeError`, `stdout` volvía
        **vacío** y el ratchet daba por nueva toda la deuda vieja de ese archivo. En el
        CI (UTF-8) no se veía.
        """
        ruta = self._template_de_referencia()

        codigo, salida = design_audit._git(["show", f"HEAD:{self.TEMPLATE_NO_CP1252}"])

        self.assertEqual(codigo, 0)
        self.assertEqual(salida.replace("\r\n", "\n"), ruta.read_bytes().decode("utf-8").replace("\r\n", "\n"))

    def test_la_base_de_ese_template_no_vuelve_vacia(self) -> None:
        self._template_de_referencia()

        base = design_audit.contenido_en("HEAD", self.TEMPLATE_NO_CP1252)

        self.assertIsNotNone(base)
        self.assertNotEqual(base.strip(), "")
        # Y con la base entera, el ratchet no inventa hallazgos nuevos sobre sí misma.
        self.assertEqual(design_audit.nuevos(base, base, self.TEMPLATE_NO_CP1252), [])


class GoldensTests(unittest.TestCase):
    """La tabla `## Arquetipos` del núcleo es la fuente del gate.

    Hasta el paso 4 de la Ola 6 el modo era tolerante: sin tabla, `--goldens`
    salía verde sin verificar nada. Desde que el núcleo la declara, dejar de
    declararla (o declarar menos goldens que `design_audit.GOLDENS`) es un error.
    """

    def _nucleo(self, texto: str) -> Path:
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        p = Path(d) / "chaco-design-system.md"
        p.write_text(texto, encoding="utf-8")
        original = design_audit.AGENTE
        design_audit.AGENTE = p
        self.addCleanup(setattr, design_audit, "AGENTE", original)
        return p

    def test_nucleo_sin_tabla_de_arquetipos_falla(self) -> None:
        self._nucleo("# Agente\n\n## Inventario operativo inicial\n\n| a | b | c |\n")

        self.assertEqual(design_audit.goldens_declaradas(), [])
        self.assertEqual(design_audit.goldens_mode(), 1)

    def test_sin_nucleo_en_el_checkout_manda_la_lista_del_script(self) -> None:
        """El release excluye `.claude/`: ahí el gate se apoya en GOLDENS."""
        self._nucleo("x").unlink()

        self.assertIsNone(design_audit.goldens_declaradas())
        self.assertEqual(design_audit.goldens_mode(), 0)

    def test_golden_que_el_nucleo_dejo_de_declarar_falla(self) -> None:
        listado = dict(design_audit.GOLDENS)["listado"]
        self._nucleo(
            "## Arquetipos\n\n| Arquetipo | Clasificación | Golden |\n|---|---|---|\n"
            f"| Arquetipo · Listado | Canónico reutilizable | Golden `{listado}` |\n"
        )

        self.assertEqual(design_audit.goldens_declaradas(), [("listado", listado)])
        self.assertEqual(design_audit.goldens_mode(), 1)

    def test_las_goldens_declaradas_por_el_nucleo_estan_en_cero(self) -> None:
        if not design_audit.goldens_declaradas():
            self.skipTest("el núcleo todavía no declara la tabla `## Arquetipos`")

        self.assertEqual(design_audit.goldens_mode(), 0)


class CompileTemplatesTests(unittest.TestCase):
    def test_compile_templates_excluye_site_packages(self) -> None:
        """V5A-NEW-08: los venv del proyecto viven adentro del checkout."""
        fuente = Path(design_audit.REPO, "scripts", "compile_templates.py").read_text(encoding="utf-8")

        self.assertIn('"site-packages" not in', fuente)


class ArquetipoCliTests(unittest.TestCase):
    def test_golden_de_listado_cumple_sus_marcadores(self) -> None:
        golden = "programas/templates/programas/becas/revision/personas_list.html"
        if not (design_audit.REPO / golden).exists():
            self.skipTest("falta la golden de listado")

        self.assertEqual(design_audit.arquetipo_mode("listado", [golden]), 0)

    def test_marcador_faltante_corta(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "list.html"
            p.write_text('{% extends "includes/base.html" %}', encoding="utf-8")

            self.assertEqual(design_audit.arquetipo_mode("listado", [str(p)]), 1)


if __name__ == "__main__":
    unittest.main()
