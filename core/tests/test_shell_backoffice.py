"""El shell del backoffice ya no depende de `conversaciones` (RED-13 + G1-01 fase 2).

`conversaciones` es una app que no se usa (decisión del 29-sep-2026) y que G1-01 fase 2
apagó. La ficha la estimaba en 2 h y no nombraba ninguna de las tres dependencias que
este módulo fija, cada una con un modo de falla propio:

1. **El shell.** `templates/includes/base.html` —que extiende *todo* el backoffice—
   resolvía cinco `{% url %}` de `conversaciones`. Desmontar `conversaciones.urls` sin
   tocarlo daba `NoReverseMatch` en el render: **500 en todas las pantallas a la vez**,
   no en la de chat.
2. **El context processor.** `conversaciones.context_processors.user_groups` proveía
   `user_groups_list`, `user_primary_group`, `user_is_superuser` y `websockets_enabled`,
   que no son de conversaciones y los usa el shell. Sacar esa línea de `settings.py` era
   **peor** que el 500: no rompía nada visible, pero `window.isSuperuser` pasaba a
   `false` y los websockets quedaban apagados sin aviso. Se mudó a
   `core.context_processors.identidad_usuario`.
3. **`legajos.ready()`.** `legajos/signals/alertas.py` importaba `conversaciones.models`
   a nivel de módulo. Sacar `"conversaciones"` de `INSTALLED_APPS` era un `ImportError`
   en el arranque: la app no levantaba en el deploy. El receiver se mudó a
   `conversaciones/signals/alertas.py`.

Los tres tests entraron en la Ola R (#607, RED-13) rojos y marcados con
`@unittest.expectedFailure`; acá se invierten. El andamio que los acompañaba
—`core/tests/urls_sin_conversaciones.py`, que filtraba los dos `include()` para simular
el día de hoy— se borró: el URLconf real ya es ese.
"""

import ast
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

RAIZ = Path(__file__).resolve().parents[2]


class ShellSinConversacionesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="shell_backoffice",
            password="clave-de-prueba",
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_el_urlconf_real_no_tiene_las_rutas_de_conversaciones(self):
        """Control del andamio: si las rutas siguieran montadas, el test de abajo
        pasaría por el motivo equivocado."""
        from config.urls import urlpatterns

        prefijos = {str(getattr(patron, "pattern", "")) for patron in urlpatterns}

        self.assertNotIn("conversaciones/", prefijos)
        self.assertNotIn("api/conversaciones/", prefijos)
        with self.assertRaises(NoReverseMatch):
            reverse("conversaciones:lista")

    def test_inicio_renderiza_sin_urls_de_conversaciones(self):
        """RED-13 / criterio de «hecho» de G1-01 fase 2.

        Entró rojo en la Ola R: `includes/base.html` levantaba `NoReverseMatch` al
        resolver `window.conversacionesConfig`. Ese bloque y los cuatro `<script>` de
        chat ya no están en el shell.
        """
        respuesta = self.client.get(reverse("core:inicio"))

        self.assertEqual(respuesta.status_code, 200)

    def test_el_shell_no_nombra_ninguna_url_de_conversaciones(self):
        """La causa, no solo el efecto: el 200 de arriba no alcanza si mañana alguien
        vuelve a meter un `{% url 'conversaciones:…' %}` detrás de un `{% if %}` que
        hoy da falso."""
        shell = (RAIZ / "templates" / "includes" / "base.html").read_text(encoding="utf-8")

        self.assertNotIn("conversaciones:", shell)
        self.assertNotIn("conversaciones_api:", shell)


class IdentidadDelUsuarioTests(TestCase):
    """Las cuatro variables del shell que `conversaciones` prestaba y ya no presta.

    En la Ola R este bloque (`ContextProcessorPrestadoTests`) estaba en **verde** y
    afirmaba que la línea de `conversaciones` seguía en `settings.py`: era el modo de
    falla silencioso, el que no da 500 y deja `window.isSuperuser` en `false`. Ahora
    afirma lo mismo sobre el context processor de `core`, que es donde vive.
    """

    VARIABLES_PRESTADAS = (
        "user_groups_list",
        "user_primary_group",
        "user_is_superuser",
        "websockets_enabled",
    )

    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            username="shell_admin",
            password="clave-de-prueba",
            email="shell_admin@example.test",
        )

    def test_el_context_processor_es_el_de_core(self):
        from django.conf import settings

        declarados = settings.TEMPLATES[0]["OPTIONS"]["context_processors"]

        self.assertIn("core.context_processors.identidad_usuario", declarados)
        self.assertNotIn("conversaciones.context_processors.user_groups", declarados)

    def test_las_cuatro_variables_del_shell_llegan_al_contexto(self):
        self.client.force_login(self.admin)

        respuesta = self.client.get(reverse("core:inicio"))

        self.assertEqual(respuesta.status_code, 200)
        for variable in self.VARIABLES_PRESTADAS:
            with self.subTest(variable=variable):
                self.assertIn(variable, respuesta.context)

    def test_el_superusuario_llega_al_javascript_del_shell(self):
        """La consecuencia concreta: `window.isSuperuser` sale de `user_is_superuser`."""
        self.client.force_login(self.admin)

        cuerpo = self.client.get(reverse("core:inicio")).content.decode("utf-8")

        self.assertIn("window.isSuperuser = true;", cuerpo)


class IndependenciaTests(TestCase):
    """`legajos` no puede importar `conversaciones` a nivel de módulo.

    `legajos/apps.py::ready()` importa `legajos.signals`, que importaba
    `legajos/signals/alertas.py`, que hacía `from conversaciones.models import Mensaje`
    en el encabezado. Con la app fuera de `INSTALLED_APPS` eso es un `ImportError` en
    el arranque, no un error en una pantalla: es la mitad de RED-13 que impide
    **arrancar**.
    """

    @staticmethod
    def _imports_de_conversaciones_a_nivel_de_modulo():
        encontrados = []
        for archivo in (RAIZ / "legajos").rglob("*.py"):
            if "migrations" in archivo.parts:
                continue
            arbol = ast.parse(archivo.read_text(encoding="utf-8"), str(archivo))
            for nodo in arbol.body:  # solo el nivel de módulo: los diferidos no rompen el arranque
                if isinstance(nodo, ast.ImportFrom) and (nodo.module or "").startswith("conversaciones"):
                    encontrados.append(f"{archivo.relative_to(RAIZ).as_posix()}:{nodo.lineno}")
                elif isinstance(nodo, ast.Import):
                    encontrados += [
                        f"{archivo.relative_to(RAIZ).as_posix()}:{nodo.lineno}"
                        for alias in nodo.names
                        if alias.name.startswith("conversaciones")
                    ]
        return sorted(encontrados)

    def test_el_detector_sigue_viendo_un_import_plantado(self):
        """Control del andamio: sin esto, el test de abajo pasaría con un detector roto."""
        import ast as _ast

        arbol = _ast.parse("from conversaciones.models import Mensaje\n")
        self.assertTrue(
            any(isinstance(nodo, _ast.ImportFrom) and nodo.module.startswith("conversaciones") for nodo in arbol.body)
        )

    def test_legajos_no_importa_conversaciones(self):
        """RED-13 — invertido en G1-01 fase 2 (`alerta_mensaje_ciudadano` se mudó)."""
        self.assertEqual(self._imports_de_conversaciones_a_nivel_de_modulo(), [])

    def test_el_receiver_vive_en_conversaciones_y_sigue_conectado(self):
        """No desapareció: cambió de dueño, junto con el modelo que lo dispara.

        `Signal.disconnect` devuelve `True` solo si había algo que desconectar: es la
        forma pública de preguntar «¿este receiver está enganchado a este sender?».
        Se vuelve a conectar al salir, para no contaminar el resto de la suite.
        """
        from django.db.models.signals import post_save

        from conversaciones.models import Mensaje
        from conversaciones.signals.alertas import alerta_mensaje_ciudadano

        estaba_conectado = post_save.disconnect(alerta_mensaje_ciudadano, sender=Mensaje)
        if estaba_conectado:
            post_save.connect(alerta_mensaje_ciudadano, sender=Mensaje)

        self.assertTrue(estaba_conectado)
        self.assertEqual(alerta_mensaje_ciudadano.__module__, "conversaciones.signals.alertas")
