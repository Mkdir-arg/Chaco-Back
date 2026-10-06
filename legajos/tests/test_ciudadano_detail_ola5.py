"""El detalle del ciudadano después de la Ola 5 PR 2: FE-02, FE-09, FE-21 y LEG-03.

- **FE-02:** la página nunca cargó ``toastr``. Cada ``toastr.options = …`` tiraba
  ``toastr is not defined`` y cortaba el handler: «Subir archivos» no mandaba **ningún**
  POST. Los avisos ahora son ``window.toast``, el único sistema del repo.
- **FE-09:** los links a ``/legajos/<id>/`` apuntan a una ruta que no existe (no hay
  vista de detalle de ``LegajoAtencion``): quedan como texto.
- **FE-21:** los modales no cerraban con Escape ni atrapaban el foco. Se atan a
  ``becas-modal.js``, el helper canónico.
- **LEG-03 (D-L03 = B):** la solapa «Red Familiar» se retira: su API nunca estuvo
  montada (404 en cada carga) y, montada tal cual, listaba los vínculos de todos.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import Resolver404, resolve, reverse

from core.tests.js_harness import correr_script_pagina, requiere_node, script_con
from legajos.models import Ciudadano
from programas.models import Programa
from programas.services.solapas import SolapasService

RUTA_VINCULOS = "/api/legajos/contactos/vinculos-familiares/"


class DetalleCiudadanoBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin-ola5-legajos", password="x")
        cls.ciudadano = Ciudadano.objects.create(
            dni="27555666", nombre="Ana", apellido="Paz", fecha_nacimiento=date(1990, 1, 1), genero="F"
        )

    def setUp(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("legajos:ciudadano_detalle", args=[self.ciudadano.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.html = respuesta.content.decode()


class RedFamiliarRetiradaTests(DetalleCiudadanoBase):
    """LEG-03 · default D-L03 = B: la solapa y su API se retiran."""

    def test_solapa_red_familiar_no_se_ofrece(self):
        solapas = SolapasService.obtener_solapas_ciudadano(self.ciudadano)

        self.assertNotIn("red_familiar", [solapa["id"] for solapa in solapas])
        self.assertNotIn('id="tab-red_familiar"', self.html)
        self.assertNotIn('id="modalVinculo"', self.html)
        self.assertNotIn('id="total-vinculos"', self.html)

    def test_el_detalle_no_consulta_la_api_de_vinculos(self):
        """Era un 404 en cada carga del legajo."""
        self.assertNotIn(RUTA_VINCULOS, self.html)
        self.assertNotIn("cargarVinculos", self.html)
        self.assertNotIn("renderizarGrafoRed", self.html)
        with self.assertRaises(Resolver404):
            resolve(RUTA_VINCULOS)

    def test_el_router_de_vinculos_ya_no_existe(self):
        """Montarlo tal cual listaba los vínculos de todos los ciudadanos."""
        with self.assertRaises(ImportError):
            import legajos.urls.api_contactos  # noqa: F401
        with self.assertRaises(ImportError):
            from legajos.api_views.contactos import VinculoFamiliarViewSet  # noqa: F401


class AvisosConToastTests(DetalleCiudadanoBase):
    """FE-02 · ni `toastr` (que no se carga) ni `Swal.fire` para avisar."""

    def test_la_pagina_no_usa_toastr(self):
        self.assertNotIn("toastr", self.html)

    def test_los_avisos_usan_window_toast(self):
        self.assertIn("window.toast('error'", self.html)
        self.assertIn("window.toast('success'", self.html)

    @requiere_node
    def test_subir_archivos_manda_el_post(self):
        """Con `toastr` indefinido el handler moría antes del `fetch`."""
        script = script_con(self.html, "formArchivos")

        log = correr_script_pagina(
            script,
            # El `FormData` de node solo acepta un <form> real; el DOM del harness es un stub.
            "FormData = function () { return {get: function () { return null; }}; };\n"
            "window.toast = function (tipo, mensaje) { (__log.toasts = __log.toasts || []).push([tipo, mensaje]); };\n"
            "__disparar('#formArchivos', 'submit', {preventDefault: function () {}});\n",
        )

        self.assertTrue(
            any(f"/legajos/ciudadanos/{self.ciudadano.pk}/subir-archivos/" in url for url in log["fetches"]),
            log["fetches"],
        )
        self.assertTrue(log.get("toasts"), "no se mostró ningún aviso al terminar la subida")


class LinksDeLegajoTests(DetalleCiudadanoBase):
    """FE-09 · `/legajos/<id>/` no resuelve: no se linkea."""

    def test_el_detalle_no_arma_links_a_la_ruta_inexistente(self):
        # `/legajos/<id>/archivos/<n>/eliminar/` sí resuelve y se sigue armando así;
        # lo que no puede quedar es un `href` al detalle del legajo, que no existe.
        self.assertNotIn('href="/legajos/${', self.html)
        self.assertNotIn("`/legajos/${escaparHtml", self.html)

    def test_la_ruta_de_detalle_de_legajo_no_existe(self):
        with self.assertRaises(Resolver404):
            resolve("/legajos/11111111-1111-1111-1111-111111111111/")


class ModalesAccesiblesTests(DetalleCiudadanoBase):
    """FE-21 · Escape, foco atrapado y foco devuelto, con el helper canónico."""

    def test_el_detalle_carga_becas_modal(self):
        self.assertIn("becas-modal.js", self.html)
        self.assertIn("window.becasModal.bind", self.html)

    def test_los_botones_de_cierre_del_modal_declaran_el_marcador(self):
        self.assertIn("data-becas-modal-cerrar", self.html)


class AlertasDashboardLinkTests(TestCase):
    """FE-09 · el botón del dashboard de alertas iba a `/legajos/<uuid>/`."""

    def setUp(self):
        from legajos.models import AlertaCiudadano

        self.admin = User.objects.create_superuser("admin-ola5-alertas", password="x")
        self.ciudadano = Ciudadano.objects.create(dni="27555777", nombre="Juan", apellido="Soto")
        Programa.objects.get_or_create(
            codigo="DISPOSITIVOS", defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS}
        )
        AlertaCiudadano.objects.create(
            ciudadano=self.ciudadano,
            tipo="SIN_PLAN",
            prioridad="CRITICA",
            mensaje="Sin plan de trabajo",
            activa=True,
        )
        self.client.force_login(self.admin)

    def test_el_boton_apunta_al_detalle_del_ciudadano(self):
        respuesta = self.client.get(reverse("legajos:alertas_dashboard"))

        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        destino = reverse("legajos:ciudadano_detalle", args=[self.ciudadano.pk])
        self.assertIn(f'href="{destino}"', html)
        self.assertNotIn('href="/legajos/{', html)
        resolve(destino)
