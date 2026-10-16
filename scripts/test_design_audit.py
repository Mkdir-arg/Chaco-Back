"""Contrato de `design_audit.py` que se puede verificar sin Django.

Corre en el job «Design Agent Contract» con el Python pelado del runner (el
script es solo stdlib). Las reglas P1, el ratchet y los marcadores tienen su
batería completa en `core/tests/test_design_audit_estructura.py`, que corre en
Backend CI.
"""

from __future__ import annotations

import contextlib
import fnmatch
import io
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


class ParticionesTests(unittest.TestCase):
    """RED-54: el conjunto se mide contra el origen **antes** de partirse.

    El riesgo que cubren estos tests no es el PR que parte el archivo —ahí la
    base del PR todavía lo tiene entero— sino **el siguiente**: una vez que la
    partición está en `development`, la base trae el padre ya reducido y
    cualquier PR que toque un pedazo se lleva la deuda vieja como propia. Por
    eso `Particion.ref` es un SHA fijo y no la base del PR.
    """

    def _particion(self) -> tuple[design_audit.Particion, list[tuple[str, str]], str]:
        if not design_audit.PARTICIONES:
            self.skipTest("no hay particiones declaradas")
        particion = next(iter(design_audit.PARTICIONES.values()))
        if not design_audit._ref_disponible(particion.ref):
            self.skipTest(f"{particion.ref[:12]} no está en este clon")
        miembros = design_audit._miembros_de(particion)
        self.assertTrue(miembros, f"la partición de {particion.origen} no tiene archivos")
        archivos = [(rel, Path(design_audit.REPO, rel).read_text(encoding="utf-8")) for rel in miembros]
        origen_entero = design_audit.contenido_en(particion.ref, particion.origen)
        self.assertIsNotNone(origen_entero, f"{particion.origen} no existe en {particion.ref[:12]}")
        return particion, archivos, origen_entero

    def test_un_pr_posterior_a_la_particion_no_hereda_la_deuda(self) -> None:
        """El caso que falla si `ref` vuelve a ser la base del PR.

        Se mide el conjunto tal como está hoy en el árbol —que es lo que vería un
        PR posterior que toca un include— contra el archivo de origen entero: 0.
        """
        particion, archivos, origen_entero = self._particion()

        self.assertEqual(
            design_audit.nuevos_de_particion(origen_entero, particion.origen, archivos),
            [],
        )

    def test_medir_contra_el_padre_ya_partido_devolveria_la_deuda_vieja(self) -> None:
        """La mutación que demuestra que el SHA fijo hace falta."""
        particion, archivos, _ = self._particion()
        padre_partido = design_audit.contenido_en("HEAD", particion.origen)
        if padre_partido is None:
            self.skipTest(f"{particion.origen} ya no existe en HEAD")

        heredados = design_audit.nuevos_de_particion(padre_partido, particion.origen, archivos)

        self.assertTrue(
            heredados,
            "con el padre ya partido como base el conjunto tiene que heredar deuda: "
            "si esto da vacío, el test de arriba dejó de probar algo",
        )

    #: Un `style=` suelto: la regla INLINESTYLE ya tenía deuda en el archivo de
    #: origen (19 casos), que es justo donde el conteo por regla puede tapar algo.
    LINEA_NUEVA = '\n<p style="margin-top: 4px">nuevo</p>'

    def test_una_linea_nueva_en_un_pedazo_se_sigue_contando(self) -> None:
        """El conjunto no es una amnistía: lo que agrega el PR se reporta igual.

        Se mide contra el piso actual del conjunto (``archivos_en_la_base``), como la
        auditoría real: si el piso fuera solo el origen entero, un PR que baja deuda
        en un pedazo dejaría hueco y la línea nueva quedaría compensada.
        """
        particion, archivos, origen_entero = self._particion()
        tocado, texto = archivos[0]
        mutados = [(tocado, texto + self.LINEA_NUEVA)] + archivos[1:]

        hallazgos = design_audit.nuevos_de_particion(
            origen_entero, particion.origen, mutados, archivos_en_la_base=archivos
        )

        self.assertEqual([(f[0], f[3]) for f in hallazgos], [(tocado, "INLINESTYLE")])

    def test_el_conjunto_son_todos_los_archivos_y_no_solo_los_tocados(self) -> None:
        """Por qué los miembros salen de un `glob` y no de lo que el PR tocó.

        Con un solo pedazo en la mano, su conteo por regla no llega a superar al
        del archivo de 1.214 líneas y el hallazgo nuevo queda en delta ≤ 0: el
        ratchet se vuelve ciego justo sobre las reglas que ya tenían deuda.
        """
        particion, archivos, origen_entero = self._particion()
        self.assertGreater(len(archivos), 1)
        suelto, texto = archivos[0]

        solo_el_tocado = design_audit.nuevos_de_particion(
            origen_entero, particion.origen, [(suelto, texto + self.LINEA_NUEVA)]
        )

        self.assertEqual(solo_el_tocado, [])
        self.assertIn(suelto, design_audit._miembros_de(particion))

    def test_ref_inexistente_no_explota(self) -> None:
        """Clon *shallow*: `--ratchet` avisa y sigue, no revienta."""
        self.assertFalse(design_audit._ref_disponible("0" * 40))

    #: Un pedazo **más adentro** que el patrón de la partición.
    ANIDADO = "programas/templates/programas/becas/revision/_detalle/anidado/_x.html"

    @contextlib.contextmanager
    def _anidado_en_el_arbol(self):
        """El pedazo anidado, creado **en el árbol real** y borrado pase lo que pase.

        Tiene que vivir ahí: lo que se mide es `ratchet_mode` sobre este checkout, que
        descubre los archivos con `git` y `REPO.glob`. El borrado va en un `finally` y no
        en un `addCleanup` porque un Ctrl-C en el medio de la corrida no ejecuta los
        cleanups de `unittest` y dejaba el template suelto adentro de la partición.
        """
        ruta = Path(design_audit.REPO, self.ANIDADO)
        try:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text('<p style="margin-top: 4px">nuevo</p>\n', encoding="utf-8")
            yield self.ANIDADO
        finally:
            shutil.rmtree(ruta.parent, ignore_errors=True)

    def test_un_pedazo_anidado_no_se_queda_sin_auditar(self) -> None:
        """Los dos criterios de `glob` tienen que decidir igual.

        `fnmatch` deja que `*` cruce `/` y `Path.glob` no: el archivo entraba a la
        partición y no a sus miembros, así que no se medía ni como conjunto ni
        contra su propia base. Hoy no es miembro, y se audita suelto.
        """
        patron = next(p for p in design_audit.PARTICIONES if p.endswith("/_detalle/*.html"))
        particion = design_audit.PARTICIONES[patron]

        with self._anidado_en_el_arbol() as rel:
            self.assertTrue(fnmatch.fnmatch(rel, patron), "si esto deja de ser cierto, el test no prueba nada")
            self.assertIsNone(design_audit._particion_de(rel))
            self.assertNotIn(rel, design_audit._miembros_de(particion))

            salida = io.StringIO()
            with contextlib.redirect_stdout(salida):
                design_audit.ratchet_mode("HEAD")

        propios = [linea for linea in salida.getvalue().splitlines() if linea.startswith(f"{rel}:")]
        self.assertEqual(len(propios), 1, salida.getvalue())
        self.assertIn("INLINESTYLE", propios[0])

    def test_el_piso_baja_con_lo_que_la_base_ya_tiene_limpio(self) -> None:
        """Con `ref` fijo y nada más, el hueco que deja una limpieza queda para gastar.

        El origen traía dos `style=`; la base del PR ya tiene uno solo porque alguien
        limpió el otro. Volver a escribirlo es deuda nueva, aunque contra el origen el
        conteo no suba.
        """
        origen = '<p style="a">1</p>\n<p style="b">2</p>\n'
        base = [("a.html", '<p style="a">1</p>\n'), ("b.html", "<p>limpio</p>\n")]
        actual = [("a.html", '<p style="a">1</p>\n'), ("b.html", '<p style="c">3</p>\n')]

        self.assertEqual(design_audit.nuevos_de_particion(origen, "o.html", actual), [])
        con_piso_de_la_base = design_audit.nuevos_de_particion(origen, "o.html", actual, base)

        self.assertEqual([(f[0], f[3]) for f in con_piso_de_la_base], [("b.html", "INLINESTYLE")])

    #: Un origen con dos `style=`, sus dos pedazos y el include que llega después.
    ORIGEN_CON_DOS = '<p style="a">1</p>\n<p style="b">2</p>\n'
    PARTIDO = "<p>lo que quedó del padre</p>\n"

    def test_el_pr_que_parte_el_archivo_sigue_dando_cero(self) -> None:
        """En la base el único miembro presente es el origen entero: el piso no se mueve."""
        en_la_base = [("o.html", self.ORIGEN_CON_DOS), ("a.html", None), ("b.html", None)]
        actual = [("o.html", self.PARTIDO), ("a.html", '<p style="a">1</p>\n'), ("b.html", '<p style="b">2</p>\n')]

        piso = design_audit.piso_de_la_base(en_la_base)

        self.assertEqual(piso, [("o.html", self.ORIGEN_CON_DOS)])
        self.assertEqual(design_audit.nuevos_de_particion(self.ORIGEN_CON_DOS, "o.html", actual, piso), [])

    def test_un_include_nuevo_no_le_devuelve_el_piso_del_origen_a_sus_hermanos(self) -> None:
        """El escape del `min` era todo-o-nada, y ese era el agujero.

        La partición ya está en `development` y alguien limpió uno de los dos `style=`.
        Un PR posterior agrega un include nuevo a la carpeta —que en la base no existe— y
        de paso vuelve a escribir el `style=` que se había limpiado. Con el piso
        todo-o-nada, el miembro faltante devolvía el piso del origen (2) a **toda** la
        partición y el `style=` nuevo entraba gratis.
        """
        en_la_base = [
            ("o.html", self.PARTIDO),
            ("a.html", '<p style="a">1</p>\n'),
            ("b.html", "<p>limpio</p>\n"),
            ("c.html", None),  # el include que agrega este PR
        ]
        actual = [
            ("o.html", self.PARTIDO),
            ("a.html", '<p style="a">1</p>\n'),
            ("b.html", '<p style="c">3</p>\n'),  # el hueco, vuelto a gastar
            ("c.html", "<p>nuevo</p>\n"),
        ]

        hallazgos = design_audit.nuevos_de_particion(
            self.ORIGEN_CON_DOS, "o.html", actual, design_audit.piso_de_la_base(en_la_base)
        )

        self.assertEqual([(f[0], f[3]) for f in hallazgos], [("b.html", "INLINESTYLE")])
        # Y la mutación: con el piso todo-o-nada —el miembro que falta lo anula entero—
        # el mismo PR pasaba en 0. Si esto deja de ser cierto, el test de arriba no prueba nada.
        self.assertEqual(design_audit.nuevos_de_particion(self.ORIGEN_CON_DOS, "o.html", actual, None), [])

    def test_sin_ningun_miembro_en_la_base_el_piso_es_el_origen(self) -> None:
        self.assertIsNone(design_audit.piso_de_la_base([("a.html", None), ("b.html", None)]))

    def test_cada_particion_declara_cuando_se_retira(self) -> None:
        """Una excepción sin fecha de muerte se queda para siempre."""
        for patron, particion in design_audit.PARTICIONES.items():
            with self.subTest(particion=patron):
                self.assertTrue(particion.retiro.strip(), f"{patron} no dice cuándo se borra")


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
