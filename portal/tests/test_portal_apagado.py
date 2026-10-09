"""SEC-29 (auditoría oct-2026) — el portal ciudadano queda apagado.

El registro del portal creaba una cuenta sobre cualquier legajo existente con
solo el DNI, y esa cuenta era la puerta de entrada de SEC-01 y SEC-09. El portal
no está en uso (decisión del PM, 29-sep-2026), así que se apagan las rutas
``mi-perfil/*``. Lo que **sí** sigue publicado es la inscripción pública por link,
que es la superficie que se usa en producción.
"""

import re
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import NoReverseMatch, Resolver404, resolve, reverse
from django.utils import timezone

from programas.models import Convocatoria, Relevamiento, Segmento

RUTAS_APAGADAS = [
    "/portal/mi-perfil/",
    "/portal/mi-perfil/login/",
    "/portal/mi-perfil/logout/",
    "/portal/mi-perfil/registro/",
    "/portal/mi-perfil/registro/verificar/",
    "/portal/mi-perfil/programas/",
    "/portal/mi-perfil/programas/1/",
    "/portal/mi-perfil/consultas/",
    "/portal/mi-perfil/consultas/nueva/",
    "/portal/mi-perfil/consultas/1/",
    "/portal/mi-perfil/consultas/1/enviar/",
    "/portal/mi-perfil/mis-datos/",
    "/portal/mi-perfil/mis-datos/cambio-email/",
    "/portal/mi-perfil/mis-datos/cambio-password/",
    "/portal/mi-perfil/password/reset/",
    "/portal/mi-perfil/password/reset/enviado/",
    "/portal/mi-perfil/password/reset/completado/",
]

NOMBRES_APAGADOS = [
    "ciudadano_mi_perfil",
    "ciudadano_login",
    "ciudadano_logout",
    "ciudadano_registro_step1",
    "ciudadano_registro_step2",
    "ciudadano_mis_programas",
    "ciudadano_programa_detalle",
    "ciudadano_mis_consultas",
    "ciudadano_nueva_consulta",
    "ciudadano_consulta_detalle",
    "ciudadano_enviar_mensaje",
    "ciudadano_mis_datos",
    "ciudadano_cambio_email",
    "ciudadano_confirmar_email",
    "ciudadano_cambio_password",
    "ciudadano_password_reset",
    "ciudadano_password_reset_done",
    "ciudadano_password_reset_confirm",
    "ciudadano_password_reset_complete",
]


class PortalApagadoTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_registro_no_existe(self):
        with self.assertRaises(Resolver404):
            resolve("/portal/mi-perfil/registro/")
        self.assertEqual(self.client.get("/portal/mi-perfil/registro/").status_code, 404)
        self.assertEqual(
            self.client.post("/portal/mi-perfil/registro/", {"dni": "30111222", "genero": "F"}).status_code,
            404,
        )

    def test_ninguna_ruta_de_mi_perfil_responde(self):
        for ruta in RUTAS_APAGADAS:
            with self.subTest(ruta=ruta):
                with self.assertRaises(Resolver404):
                    resolve(ruta)
                self.assertEqual(self.client.get(ruta).status_code, 404)

    def test_ningun_nombre_de_url_del_portal_ciudadano_resuelve(self):
        for nombre in NOMBRES_APAGADOS:
            with self.subTest(nombre=nombre):
                with self.assertRaises(NoReverseMatch):
                    reverse(f"portal:{nombre}")

    def test_home_del_portal_sigue_renderizando(self):
        respuesta = self.client.get(reverse("portal:home"))

        self.assertEqual(respuesta.status_code, 200)

    def test_csrf_publico_sigue(self):
        self.assertEqual(self.client.get(reverse("portal:csrf_token")).status_code, 200)


class InscripcionPublicaSigueTests(TestCase):
    """La inscripción pública por link es la superficie que se usa en producción."""

    def setUp(self):
        cache.clear()
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas 2026",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now() - timedelta(days=1),
            fecha_hasta=timezone.now() + timedelta(days=10),
        )

    def test_inscripcion_publica_sigue(self):
        url = reverse("portal:inscripcion_paso1", kwargs={"token": self.relevamiento.token_publico})

        self.assertEqual(resolve(url).url_name, "inscripcion_paso1")
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_los_tres_pasos_del_link_siguen_ruteando(self):
        token = self.relevamiento.token_publico
        for nombre, esperado in (
            ("inscripcion_paso1", "inscripcion_paso1"),
            ("inscripcion_paso2", "inscripcion_paso2"),
            ("inscripcion_confirmacion", "inscripcion_confirmacion"),
        ):
            with self.subTest(nombre=nombre):
                url = reverse(f"portal:{nombre}", kwargs={"token": token})
                self.assertEqual(resolve(url).url_name, esperado)


class MiddlewareCiudadanoTests(TestCase):
    """El middleware sigue separando portal de backoffice, pero manda a la home."""

    def setUp(self):
        cache.clear()
        self.grupo = Group.objects.create(name="Ciudadanos")
        self.ciudadano = User.objects.create_user(username="30111222", password="secret")  # nosec B106
        self.ciudadano.groups.add(self.grupo)

    def test_un_ciudadano_en_el_backoffice_va_a_la_home_del_portal(self):
        self.client.force_login(self.ciudadano)

        respuesta = self.client.get("/legajos/ciudadanos/")

        self.assertRedirects(respuesta, reverse("portal:home"), fetch_redirect_response=False)

    def test_un_ciudadano_puede_ver_la_home_del_portal_sin_rebotar(self):
        self.client.force_login(self.ciudadano)

        respuesta = self.client.get(reverse("portal:home"))

        self.assertEqual(respuesta.status_code, 200)


class DocumentacionDelPortalTests(SimpleTestCase):
    """R0-02 · la documentación no puede prometer una ruta del portal que no existe.

    `CLAUDE.md` y `docs/client/architecture.md` son los dos textos que describen el
    `PortalCiudadanoMiddleware`, y los dos siguieron diciendo que redirige a
    `portal:ciudadano_mi_perfil` después de que SEC-29 apagara las rutas `mi-perfil/*`.
    No es un bug de runtime, pero es la primera fuente que lee alguien —persona o
    agente— antes de tocar la separación backoffice/portal, y mandaba a una ruta que
    el `reverse` ya no resuelve.

    En vez de fijar el nombre correcto, que envejece igual, se afirma la propiedad:
    **todo `portal:<algo>` que esos dos textos nombren tiene que reversear.** Así la
    próxima ruta que se apague vuelve a poner esto en rojo.
    """

    #: Los dos documentos del hallazgo, relativos a la raíz del repo.
    DOCUMENTOS = ("CLAUDE.md", "docs/client/architecture.md")

    def test_las_rutas_del_portal_que_nombran_los_docs_existen(self):
        raiz = Path(settings.BASE_DIR)
        rotas = []
        for relativo in self.DOCUMENTOS:
            texto = (raiz / relativo).read_text(encoding="utf-8")
            for nombre in sorted(set(re.findall(r"portal:[a-z0-9_]+", texto))):
                try:
                    reverse(nombre)
                except NoReverseMatch:
                    rotas.append(f"{relativo} → {nombre}")

        self.assertEqual(rotas, [], f"Rutas del portal nombradas en la documentación y sin destino: {rotas}")

    def test_el_control_del_andamio(self):
        """Si el `reverse` de una ruta apagada no fallara, el test de arriba no mira nada."""
        with self.assertRaises(NoReverseMatch):
            reverse("portal:ciudadano_mi_perfil")
