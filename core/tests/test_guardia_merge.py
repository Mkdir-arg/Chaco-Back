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
