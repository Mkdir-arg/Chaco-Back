"""El shell del backoffice depende de `conversaciones` por tres caminos (RED-13).

`conversaciones` es una app que hoy **no se usa** (decisión del 29-sep-2026) y que
G1-01 fase 2 va a apagar. La ficha de G1-01 la estimaba en 2 h y no nombraba ninguna de
estas tres dependencias:

1. **El shell.** `templates/includes/base.html` —que extiende *todo* el backoffice—
   resuelve cinco `{% url %}` de `conversaciones`. Desmontar `conversaciones.urls` sin
   tocarlo da `NoReverseMatch` en el render: **500 en todas las pantallas a la vez**,
   no en la de chat.
2. **El context processor.** `conversaciones.context_processors.user_groups` provee
   `user_groups_list`, `user_primary_group`, `user_is_superuser` y `websockets_enabled`,
   que no son de conversaciones y los usa el shell. Sacar esa línea de `settings.py` es
   **peor** que el 500: no rompe nada visible, pero `window.isSuperuser` pasa a `false`
   y los websockets quedan apagados sin aviso.
3. **`legajos.ready()`.** `legajos/signals/alertas.py` importa `conversaciones.models` a
   nivel de módulo. Sacar `"conversaciones"` de `INSTALLED_APPS` da `ImportError` en el
   arranque: la app no levanta en el deploy.

`ShellSinConversacionesTests.test_inicio_renderiza_sin_urls_de_conversaciones` es el
**criterio de «hecho»** de la fase 2: hoy está rojo (`expectedFailure`) y se pone verde
cuando el shell deje de depender de la app. Lo mismo
`IndependenciaTests.test_legajos_no_importa_conversaciones`.

Los otros tests de este módulo están en verde y fijan lo que la fase 2 no puede perder.
"""

import ast
import unittest
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from core.tests.urls_sin_conversaciones import urlpatterns as _urls_recortadas

RAIZ = Path(__file__).resolve().parents[2]

URLCONF_SIN_CONVERSACIONES = "core.tests.urls_sin_conversaciones"


@override_settings(ROOT_URLCONF=URLCONF_SIN_CONVERSACIONES)
class ShellSinConversacionesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="shell_backoffice",
            password="clave-de-prueba",
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_el_urlconf_recortado_no_tiene_las_rutas_de_conversaciones(self):
        """Control del andamio: si el filtro no sacara nada, el test de abajo
        pasaría por el motivo equivocado."""
        from config.urls import urlpatterns as completo

        self.assertEqual(len(completo) - len(_urls_recortadas), 2)
        with self.assertRaises(NoReverseMatch):
            reverse("conversaciones:lista")

    @unittest.expectedFailure
    def test_inicio_renderiza_sin_urls_de_conversaciones(self):
        """RED-13 — se invierte en G1-01 fase 2.

        Hoy levanta `NoReverseMatch` al renderizar `includes/base.html`. Cuando la
        fase 2 saque de ahí el bloque `window.conversacionesConfig` y los `<script>`
        a un include condicional, esto pasa a *unexpected success* y hay que sacarle
        el decorador.
        """
        respuesta = self.client.get(reverse("core:inicio"))

        self.assertEqual(respuesta.status_code, 200)

    def test_hoy_el_inicio_se_cae_y_el_motivo_es_el_reverse_del_shell(self):
        """El `expectedFailure` de arriba solo dice «falla». Esto dice **por qué**: si
        mañana fallara por otra cosa, el criterio de «hecho» de la fase 2 estaría
        midiendo un problema distinto.
        """
        with self.assertRaises(NoReverseMatch) as capturado:
            self.client.get(reverse("core:inicio"))

        self.assertIn("conversaciones", str(capturado.exception))


class ContextProcessorPrestadoTests(TestCase):
    """Las cuatro variables del shell que `conversaciones` provee y no son suyas.

    Este test está en **verde** y se pone rojo si alguien borra la línea del
    `settings.py` creyendo que limpia la app: ese es el modo de falla silencioso, el
    que no da 500 y deja `window.isSuperuser` en `false`.
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

    def test_el_context_processor_de_conversaciones_sigue_declarado(self):
        from django.conf import settings

        declarados = settings.TEMPLATES[0]["OPTIONS"]["context_processors"]

        self.assertIn("conversaciones.context_processors.user_groups", declarados)

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

    `legajos/apps.py::ready()` importa `legajos.signals`, que importa
    `legajos/signals/alertas.py`, que hace `from conversaciones.models import Mensaje`
    en el encabezado. Con la app fuera de `INSTALLED_APPS` eso es un `ImportError` en
    el arranque, no un error en una pantalla.

    La ficha pone este test en la Ola 7, junto con el movimiento de
    `alerta_mensaje_ciudadano` a `conversaciones/signals/`. Se adelanta acá, rojo y
    marcado, porque es la mitad de RED-13 que impide **arrancar** y la regla de la Ola R
    es que lo que las otras olas van a tocar tenga antes un test que se ponga rojo.
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

    def test_el_detector_ve_el_import_de_hoy(self):
        """Control del andamio del `expectedFailure` de abajo."""
        self.assertIn(
            "legajos/signals/alertas.py:4",
            self._imports_de_conversaciones_a_nivel_de_modulo(),
        )

    @unittest.expectedFailure
    def test_legajos_no_importa_conversaciones(self):
        """RED-13 — se invierte en G1-01 fase 2 (mover `alerta_mensaje_ciudadano`)."""
        self.assertEqual(self._imports_de_conversaciones_a_nivel_de_modulo(), [])
