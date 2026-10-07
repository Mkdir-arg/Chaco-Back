"""Ola 5 · PR 5 — FE-18 y FE-19 en las pantallas de Usuarios y Roles.

Las dos fichas son el mismo error de lectura: el rojo del sistema significa *peligro*,
y acá se usaba para dos cosas que no lo son.

- **FE-18**: un usuario o un rol desactivado salía con `badge-danger`. Apagado no es un
  error (es el mismo criterio que ya fija `_pausable_estado_badge.html` para los
  segmentos de Becas): va en `badge-gray`.
- **FE-19**: el diálogo de confirmación pintaba el botón de confirmar con `btn-danger`
  **siempre**, así que «Activar usuario» —una acción constructiva— aparecía en rojo de
  borrado. El tono lo decide ahora la acción, no el handler.
"""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from core.tests.js_harness import correr_script, requiere_node, script_con

REPO = Path(settings.BASE_DIR)

USER_LIST = "users/templates/user/user_list.html"
ROL_LIST = "users/templates/rol/rol_list.html"
ROL_DETAIL = "users/templates/rol/rol_detail.html"


class InactivoEnGrisTests(SimpleTestCase):
    """FE-18: «Inactivo» es ausencia de actividad, no un error."""

    PANTALLAS = (USER_LIST, ROL_LIST, ROL_DETAIL)

    def test_el_badge_de_inactivo_es_gris(self):
        for ruta in self.PANTALLAS:
            with self.subTest(ruta=ruta):
                texto = (REPO / ruta).read_text(encoding="utf-8")
                self.assertTrue(
                    '<span class="badge badge-gray badge-dot">Inactivo</span>' in texto,
                    f"{ruta}: «Inactivo» tiene que ir en badge-gray",
                )

    def test_ninguna_pantalla_pinta_inactivo_de_rojo(self):
        for ruta in self.PANTALLAS:
            with self.subTest(ruta=ruta):
                texto = (REPO / ruta).read_text(encoding="utf-8")
                self.assertFalse(
                    'badge-danger badge-dot">Inactivo' in texto,
                    f"{ruta}: «Inactivo» no puede salir en badge-danger",
                )

    def test_activo_sigue_en_verde(self):
        for ruta in self.PANTALLAS:
            with self.subTest(ruta=ruta):
                texto = (REPO / ruta).read_text(encoding="utf-8")
                self.assertTrue('badge badge-success badge-dot">Activo' in texto, ruta)


@requiere_node
class ConfirmacionSegunLaAccionTests(SimpleTestCase):
    """FE-19: el rojo del botón de confirmar lo decide la acción, no el handler."""

    def _swal(self, ruta, marcador, llamada):
        script = script_con((REPO / ruta).read_text(encoding="utf-8"), marcador)
        log = correr_script(script, llamada)
        self.assertEqual(len(log["swal"]), 1, log)
        return log["swal"][0]

    def test_desactivar_usuario_confirma_en_rojo(self):
        opciones = self._swal(USER_LIST, "confirmarToggleUsuario", "confirmarToggleUsuario(1, 'juan', true);")
        self.assertEqual(opciones["title"], "Desactivar usuario")
        self.assertIn("btn-danger", opciones["customClass"]["confirmButton"])

    def test_activar_usuario_no_confirma_en_rojo(self):
        opciones = self._swal(USER_LIST, "confirmarToggleUsuario", "confirmarToggleUsuario(1, 'juan', false);")
        self.assertEqual(opciones["title"], "Activar usuario")
        self.assertNotIn("btn-danger", opciones["customClass"]["confirmButton"])
        self.assertIn("btn-brand", opciones["customClass"]["confirmButton"])

    def test_desactivar_rol_confirma_en_rojo(self):
        opciones = self._swal(ROL_LIST, "confirmarToggleRol", "confirmarToggleRol(1, 'Operador', true);")
        self.assertEqual(opciones["title"], "Desactivar rol")
        self.assertIn("btn-danger", opciones["customClass"]["confirmButton"])

    def test_activar_rol_no_confirma_en_rojo(self):
        opciones = self._swal(ROL_LIST, "confirmarToggleRol", "confirmarToggleRol(1, 'Operador', false);")
        self.assertEqual(opciones["title"], "Activar rol")
        self.assertNotIn("btn-danger", opciones["customClass"]["confirmButton"])
        self.assertIn("btn-brand", opciones["customClass"]["confirmButton"])

    def test_eliminar_rol_sigue_en_rojo(self):
        opciones = self._swal(ROL_LIST, "confirmarEliminarRol", "confirmarEliminarRol(1, 'Operador', 0);")
        self.assertIn("btn-danger", opciones["customClass"]["confirmButton"])

    def test_los_botones_del_dialogo_tienen_tamano(self):
        """Sin clase de tamaño, `.btn-nodo` queda con `padding-left: 0` (FE-06/FE-07)."""
        casos = (
            (USER_LIST, "confirmarToggleUsuario", "confirmarToggleUsuario(1, 'juan', true);"),
            (USER_LIST, "confirmarToggleUsuario", "confirmarToggleUsuario(1, 'juan', false);"),
            (ROL_LIST, "confirmarToggleRol", "confirmarToggleRol(1, 'Operador', true);"),
            (ROL_LIST, "confirmarEliminarRol", "confirmarEliminarRol(1, 'Operador', 2);"),
        )
        for ruta, marcador, llamada in casos:
            with self.subTest(llamada=llamada):
                clases = self._swal(ruta, marcador, llamada)["customClass"]
                for boton in ("confirmButton", "cancelButton"):
                    self.assertIn("btn-base", clases[boton], f"{llamada} · {boton}")
