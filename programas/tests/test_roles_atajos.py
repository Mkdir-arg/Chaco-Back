"""Ratchet de la regla R-2: todo atajo que otorga roles aplica la guarda de autoasignación (#1114).

El ABM de Usuarios bloquea que alguien se cambie sus propios roles (`roles_propios_bloqueados`). Cualquier otro
camino que haga `groups.add(` / `groups.set(` desde `programas/services` o `programas/views` es la misma puerta
por otro lado, y tiene que aplicar esa guarda (o la regla equivalente) en el servicio.

Si este test falla porque apareció un módulo nuevo: aplicá `roles_propios_bloqueados(operador, destinatario)` antes
de otorgar. No agregues el módulo a la allowlist sin explicar por qué el destinatario nunca puede ser el operador.
"""

import re
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parents[1]
CARPETAS = ("services", "views")
OTORGA_GRUPOS = re.compile(r"\.groups\.(add|set)\(")
GUARDA = "roles_propios_bloqueados"

#: Congelada: módulo (relativo a `programas/`) -> motivo. Hoy está vacía; solo puede achicarse.
ALLOWLIST_CONGELADA = {}


def _modulos_que_otorgan_grupos():
    encontrados = {}
    for carpeta in CARPETAS:
        for ruta in sorted((RAIZ / carpeta).rglob("*.py")):
            texto = ruta.read_text(encoding="utf-8")
            if OTORGA_GRUPOS.search(texto):
                encontrados[ruta.relative_to(RAIZ).as_posix()] = texto
    return encontrados


class RolesAtajosTests(SimpleTestCase):
    def test_todo_modulo_que_otorga_grupos_aplica_la_guarda_de_autoasignacion(self):
        modulos = _modulos_que_otorgan_grupos()
        self.assertTrue(modulos, "El escaneo no encontró ningún módulo: el patrón o las carpetas están mal.")
        sin_guarda = sorted(m for m, texto in modulos.items() if GUARDA not in texto and m not in ALLOWLIST_CONGELADA)
        self.assertEqual(
            sin_guarda,
            [],
            f"Estos módulos otorgan grupos sin `{GUARDA}` (regla R-2, patrón #1114): {sin_guarda}",
        )

    def test_la_allowlist_no_guarda_modulos_que_ya_no_existen_ni_ya_cumplen(self):
        modulos = _modulos_que_otorgan_grupos()
        for modulo in ALLOWLIST_CONGELADA:
            self.assertIn(modulo, modulos, f"{modulo} ya no otorga grupos: sacalo de la allowlist.")
            self.assertNotIn(GUARDA, modulos[modulo], f"{modulo} ya aplica la guarda: sacalo de la allowlist.")
