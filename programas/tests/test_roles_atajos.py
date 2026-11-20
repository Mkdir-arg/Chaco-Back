"""Ratchet de la regla R-2: todo atajo que otorga roles aplica la guarda de autoasignación (#1114).

El ABM de Usuarios bloquea que alguien se cambie sus propios roles (`roles_propios_bloqueados`). Cualquier otro
camino que otorgue grupos desde `programas/services` o `programas/views` (`.groups.add(`/`.groups.set(`,
`.user_set.add(`/`.user_set.set(`, `groups.through.objects.create|bulk_create|get_or_create(`) es la misma puerta
por otro lado, y tiene que **llamar** a esa guarda (o la regla equivalente) en el servicio. Mencionarla en un
comentario o en un texto no cuenta: se exige una llamada real, medida por AST.

Si este test falla porque apareció un módulo nuevo: aplicá `roles_propios_bloqueados(operador, destinatario)` antes
de otorgar. No agregues el módulo a la allowlist sin explicar por qué el destinatario nunca puede ser el operador.
"""

import ast
import re
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parents[1]
CARPETAS = ("services", "views")
OTORGA_GRUPOS = re.compile(
    r"\.(?:groups|user_set)\.(?:add|set)\(|groups\.through\.objects\.(?:create|bulk_create|get_or_create)\("
)
GUARDA = "roles_propios_bloqueados"

#: Congelada: módulo (relativo a `programas/`) -> motivo. Hoy está vacía; solo puede achicarse.
ALLOWLIST_CONGELADA = {}


def llama_a_la_guarda(texto):
    """Si el código tiene una LLAMADA a la guarda (``guarda(...)`` o ``algo.guarda(...)``)."""

    for nodo in ast.walk(ast.parse(texto)):
        if isinstance(nodo, ast.Call):
            func = nodo.func
            nombre = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if nombre == GUARDA:
                return True
    return False


def otorga_grupos(texto):
    return bool(OTORGA_GRUPOS.search(texto))


def _modulos_que_otorgan_grupos():
    encontrados = {}
    for carpeta in CARPETAS:
        for ruta in sorted((RAIZ / carpeta).rglob("*.py")):
            texto = ruta.read_text(encoding="utf-8")
            if otorga_grupos(texto):
                encontrados[ruta.relative_to(RAIZ).as_posix()] = texto
    return encontrados


class RolesAtajosTests(SimpleTestCase):
    def test_todo_modulo_que_otorga_grupos_aplica_la_guarda_de_autoasignacion(self):
        modulos = _modulos_que_otorgan_grupos()
        self.assertTrue(modulos, "El escaneo no encontró ningún módulo: el patrón o las carpetas están mal.")
        sin_guarda = sorted(
            m for m, texto in modulos.items() if not llama_a_la_guarda(texto) and m not in ALLOWLIST_CONGELADA
        )
        self.assertEqual(
            sin_guarda,
            [],
            f"Estos módulos otorgan grupos sin llamar a `{GUARDA}` (regla R-2, patrón #1114): {sin_guarda}",
        )

    def test_la_allowlist_no_guarda_modulos_que_ya_no_existen_ni_ya_cumplen(self):
        modulos = _modulos_que_otorgan_grupos()
        for modulo in ALLOWLIST_CONGELADA:
            self.assertIn(modulo, modulos, f"{modulo} ya no otorga grupos: sacalo de la allowlist.")
            self.assertFalse(
                llama_a_la_guarda(modulos[modulo]), f"{modulo} ya aplica la guarda: sacalo de la allowlist."
            )

    def test_la_deteccion_exige_una_llamada_real_a_la_guarda(self):
        # Mutación: solo la nombran un comentario, un texto o un import; sin llamada no cuenta.
        solo_mencion = (
            "from users.selectors.usuarios import roles_propios_bloqueados\n"
            "# aplicar roles_propios_bloqueados antes de otorgar\n"
            "TEXTO = 'roles_propios_bloqueados'\n"
            "def f(u, g):\n    u.groups.add(g)\n"
        )
        self.assertFalse(llama_a_la_guarda(solo_mencion))
        self.assertTrue(llama_a_la_guarda("def f(o, u):\n    if roles_propios_bloqueados(o, u):\n        return\n"))
        self.assertTrue(
            llama_a_la_guarda("def f(o, u):\n    if selectores.roles_propios_bloqueados(o, u):\n        return\n")
        )

    def test_el_patron_detecta_cada_forma_de_otorgar_grupos(self):
        formas = (
            "u.groups.add(g)",
            "u.groups.set([g])",
            "g.user_set.add(u)",
            "g.user_set.set([u])",
            "User.groups.through.objects.create(user_id=1, group_id=2)",
            "User.groups.through.objects.bulk_create(filas)",
            "User.groups.through.objects.get_or_create(user_id=1, group_id=2)",
        )
        for forma in formas:
            self.assertTrue(otorga_grupos(forma), forma)
        self.assertFalse(otorga_grupos("u.groups.filter(pk=1).exists()"))
