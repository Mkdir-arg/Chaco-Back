"""El hook `guardia_merge` frena `gh pr merge` sin `/auditoria pr` aprobada para el head.

`.claude/` no viaja al release (export-ignore): el test se saltea en el snapshot de `main`
y corre en el CI de `development`, igual que los de `design_audit.py` en `test_gates_ci`.
`gh` se simula: el test no toca la red.
"""

import importlib.util
import json
import sys
import unittest
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parents[2]
HOOK = RAIZ / ".claude" / "hooks" / "guardia_merge.py"

HEAD = "a" * 40
VIEJO = "b" * 40


def _cargar():
    spec = importlib.util.spec_from_file_location("guardia_merge", HOOK)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo  # @dataclass con `from __future__ import annotations` lo busca acá
    spec.loader.exec_module(modulo)
    return modulo


def _pr(comentarios=(), base="development", url="https://github.com/Mkdir-arg/Chaco-Back/pull/940"):
    return {
        "number": 940,
        "url": url,
        "baseRefName": base,
        "headRefOid": HEAD,
        "comments": [{"body": cuerpo} for cuerpo in comentarios],
    }


def _marca(veredicto, sha):
    return f"## Auditoría\n<!-- auditoria-chaco veredicto={veredicto} sha={sha} -->"


@unittest.skipUnless(HOOK.exists(), "hace falta .claude/hooks/guardia_merge.py (no viaja al release)")
class GuardiaMergeTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.guardia = _cargar()
        cls.addClassCleanup(sys.modules.pop, "guardia_merge", None)

    def _correr(self, comando, pr=None, error=None):
        llamadas = []

        def consultar(merge, cwd):
            llamadas.append(merge)
            if error:
                raise error
            return pr

        stdin = json.dumps({"tool_name": "Bash", "tool_input": {"command": comando}, "cwd": "."})
        codigo, mensaje = self.guardia.main(stdin, consultar=consultar)
        return codigo, mensaje, llamadas

    def test_comando_sin_merge_no_consulta_github(self):
        codigo, _, llamadas = self._correr("git status && gh pr view 940")
        self.assertEqual((codigo, llamadas), (0, []))

    def test_stdin_invalido_deja_pasar(self):
        self.assertEqual(self.guardia.main("no es json")[0], 0)
        self.assertEqual(self.guardia.main("[1, 2]")[0], 0)

    def test_sin_comentario_de_auditoria_frena(self):
        codigo, mensaje, _ = self._correr("gh pr merge 940 --merge", _pr())
        self.assertEqual(codigo, 2)
        self.assertIn("/auditoria pr 940", mensaje)

    def test_aprobado_para_un_sha_viejo_frena(self):
        codigo, _, _ = self._correr("gh pr merge 940 --merge", _pr([_marca("APPROVE", VIEJO)]))
        self.assertEqual(codigo, 2)

    def test_changes_needed_frena(self):
        codigo, mensaje, _ = self._correr("gh pr merge 940 --merge", _pr([_marca("CHANGES_NEEDED", HEAD)]))
        self.assertEqual(codigo, 2)
        self.assertIn("CHANGES_NEEDED", mensaje)

    def test_vale_el_ultimo_veredicto_sobre_el_head(self):
        aprobado_y_rechazado = _pr([_marca("APPROVE", HEAD), _marca("CHANGES_NEEDED", HEAD)])
        rechazado_y_aprobado = _pr([_marca("CHANGES_NEEDED", HEAD), _marca("APPROVE", HEAD)])
        self.assertEqual(self._correr("gh pr merge 940 --merge", aprobado_y_rechazado)[0], 2)
        self.assertEqual(self._correr("gh pr merge 940 --merge", rechazado_y_aprobado)[0], 0)

    def test_aprobado_para_el_head_deja_pasar(self):
        codigo, mensaje, _ = self._correr("gh pr merge 940 --merge", _pr([_marca("APPROVE", HEAD)]))
        self.assertEqual((codigo, mensaje), (0, ""))

    def test_match_head_commit_distinto_frena(self):
        comando = "gh pr merge 940 --merge --match-head-commit bbbbbbb"
        codigo, mensaje, _ = self._correr(comando, _pr([_marca("APPROVE", HEAD)]))
        self.assertEqual(codigo, 2)
        self.assertIn("match-head-commit", mensaje)

    def test_match_head_commit_corto_y_con_igual(self):
        comando = "gh pr merge 940 --merge --match-head-commit=AAAAAAA"
        self.assertEqual(self._correr(comando, _pr([_marca("APPROVE", HEAD)]))[0], 0)

    def test_otra_base_u_otro_repo_deja_pasar(self):
        self.assertEqual(self._correr("gh pr merge 940", _pr(base="main"))[0], 0)
        otro = _pr(url="https://github.com/Mkdir-arg/Chaco-mobile/pull/12")
        self.assertEqual(self._correr("gh pr merge 12", otro)[0], 0)

    def test_gh_caido_frena(self):
        codigo, mensaje, _ = self._correr("gh pr merge 940", error=RuntimeError("sin red"))
        self.assertEqual(codigo, 2)
        self.assertIn("sin red", mensaje)

    def test_extrae_selector_repo_y_sha_de_un_comando_compuesto(self):
        comando = (
            "cd x && gh pr merge 940 -R Mkdir-arg/Chaco-Back --squash "
            "--match-head-commit abc1234 --delete-branch; echo ok"
        )
        merges = self.guardia.extraer_merges(comando)
        self.assertEqual(len(merges), 1)
        merge = merges[0]
        self.assertEqual((merge.selector, merge.repo, merge.match_head), ("940", "Mkdir-arg/Chaco-Back", "abc1234"))

    def test_merge_sin_selector_usa_la_rama_actual(self):
        (merge,) = self.guardia.extraer_merges("gh pr merge --merge --delete-branch")
        self.assertIsNone(merge.selector)

    def test_mencionar_el_comando_sin_ejecutarlo_no_consulta_github(self):
        for comando in (
            'grep -n "gh pr merge" docs/internal/requerimientos.md',
            'git commit -m "docs: antes de gh pr merge se audita"',
            "echo gh pr merge 940",
        ):
            with self.subTest(comando=comando):
                codigo, _, llamadas = self._correr(comando)
                self.assertEqual((codigo, llamadas), (0, []))

    def test_reconoce_gh_exe_con_ruta_y_variables_de_entorno(self):
        for comando in (
            "gh.exe pr merge 940 --merge",
            '& "C:\\Program Files\\GitHub CLI\\gh.exe" pr merge 940 --merge',
            "GH_PROMPT_DISABLED=1 gh pr merge 940 --merge",
        ):
            with self.subTest(comando=comando):
                (merge,) = self.guardia.extraer_merges(comando)
                self.assertEqual(merge.selector, "940")

    def test_repo_pegado_al_flag(self):
        for comando in ("gh pr merge 940 -RMkdir-arg/Chaco-Back --merge", "gh pr merge 940 -R=Mkdir-arg/Chaco-Back"):
            with self.subTest(comando=comando):
                (merge,) = self.guardia.extraer_merges(comando)
                self.assertEqual(merge.repo, "Mkdir-arg/Chaco-Back")

    def test_comando_partido_en_varias_lineas(self):
        for corte in ("\\\n", "`\r\n"):
            with self.subTest(corte=repr(corte)):
                (merge,) = self.guardia.extraer_merges(f"gh pr merge 940 --merge {corte}  --match-head-commit abc1234")
                self.assertEqual((merge.selector, merge.match_head), ("940", "abc1234"))

    def test_selector_por_url_o_por_rama(self):
        url = "https://github.com/Mkdir-arg/Chaco-Back/pull/940"
        self.assertEqual(self.guardia.extraer_merges(f"gh pr merge {url} --merge")[0].selector, url)
        self.assertEqual(self.guardia.extraer_merges("gh pr merge feature/x --merge")[0].selector, "feature/x")

    def test_dos_merges_encadenados_se_evaluan_los_dos(self):
        aprobados = {"1": _pr([_marca("APPROVE", HEAD)]), "2": _pr()}
        llamadas = []

        def consultar(merge, cwd):
            llamadas.append(merge.selector)
            return aprobados[merge.selector]

        stdin = json.dumps({"tool_input": {"command": "gh pr merge 1 --merge && gh pr merge 2 --merge"}})
        codigo, _ = self.guardia.main(stdin, consultar=consultar)
        self.assertEqual((codigo, llamadas), (2, ["1", "2"]))

    def test_match_head_con_variable_avisa_que_no_se_expande(self):
        comando = 'gh pr merge 940 --merge --match-head-commit "$HEAD_SHA"'
        codigo, mensaje, _ = self._correr(comando, _pr([_marca("APPROVE", HEAD)]))
        self.assertEqual(codigo, 2)
        self.assertIn("no expande variables", mensaje)
