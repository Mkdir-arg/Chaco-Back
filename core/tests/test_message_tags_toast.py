"""Los mensajes de Django llegan a ``nodo-toast`` con un tag que entiende.

``base.html`` y ``portal/base.html`` imprimen cada mensaje como
``<div class="dj-message" data-tags="{{ message.tags }}">`` y ``nodo-toast.js``
(``resolveType``) elige la variante buscando ``success``/``warning``/``error``.
``MESSAGE_TAGS`` traducía los niveles a clases Tailwind (``bg-green-500 …``) y
todo toast salía como «Información».
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.messages.storage.base import Message
from django.shortcuts import render
from django.test import TestCase, override_settings
from django.urls import include, path

NIVELES = [
    (messages.DEBUG, "info"),
    (messages.INFO, "info"),
    (messages.SUCCESS, "success"),
    (messages.WARNING, "warning"),
    (messages.ERROR, "error"),
]


def _vista_con_mensajes(template):
    def vista(request):
        messages.success(request, "Guardado OK")
        messages.warning(request, "Revisar esto")
        messages.error(request, "Falló aquello")
        return render(request, template)

    return vista


urlpatterns = [
    path("__msgs__/backoffice/", _vista_con_mensajes("includes/base.html")),
    path("__msgs__/portal/", _vista_con_mensajes("portal/base.html")),
    path("", include("config.urls")),
]


class MessageTagsTests(TestCase):
    def test_cada_nivel_lleva_el_tag_de_nodo_toast(self):
        for nivel, tag in NIVELES:
            with self.subTest(nivel=nivel):
                self.assertEqual(Message(nivel, "x").tags, tag)

    def test_extra_tags_se_suman_al_nivel(self):
        self.assertEqual(Message(messages.WARNING, "x", extra_tags="algo").tags, "algo warning")


@override_settings(ROOT_URLCONF=__name__)
class MessageTagsRenderTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("root_msgs", "r@x.com", "x"))

    def _tags_renderizados(self, url):
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        return re.findall(r'class="dj-message" data-tags="([^"]*)">([^<]*)<', html)

    def test_backoffice_imprime_tags_que_resolveType_entiende(self):
        self.assertEqual(
            self._tags_renderizados("/__msgs__/backoffice/"),
            [("success", "Guardado OK"), ("warning", "Revisar esto"), ("error", "Falló aquello")],
        )

    def test_portal_imprime_tags_que_resolveType_entiende(self):
        self.assertEqual(
            self._tags_renderizados("/__msgs__/portal/"),
            [("success", "Guardado OK"), ("warning", "Revisar esto"), ("error", "Falló aquello")],
        )


NODO_TOAST = Path(settings.BASE_DIR) / "static" / "custom" / "js" / "nodo-toast.js"


class ResolveTypeNodeTests(TestCase):
    """Corre el ``resolveType`` real de ``nodo-toast.js`` en node sobre los tags
    que produce ``MESSAGE_TAGS``. Sin node en la máquina se saltea."""

    def test_resolve_type_devuelve_la_variante_de_cada_nivel(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node no está instalado")
        fuente = NODO_TOAST.read_text(encoding="utf-8")
        aliases = re.search(r"var ALIASES = \{.*?\n    \};", fuente, re.S).group(0)
        resolve = re.search(r"function resolveType\(raw\) \{.*?\n    \}", fuente, re.S).group(0)
        tags = [Message(nivel, "x").tags for nivel, _ in NIVELES]
        script = f"{aliases}\n{resolve}\nconsole.log(JSON.stringify({json.dumps(tags)}.map(resolveType)));"
        salida = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(salida), [tag for _, tag in NIVELES])
