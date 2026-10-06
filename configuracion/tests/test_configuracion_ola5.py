"""Configuración: paginación de Geografía, cascada del wizard y errores no de campo.

Las tres fichas del PR 3 de la Ola 5 de la auditoría integral de octubre de 2026:

* **FE-04** — `/configuracion/{provincias,municipios,localidades}/` pagina de a 20 y no
  dibuja ningún control: con 21 filas, la 21 es inalcanzable. Y cada `form_invalid`
  rearmaba el contexto a mano, sin `page_obj`, así que volver de un error de validación
  también perdía la paginación.
* **FE-05** — `programa_wizard_paso1.html` ponía su `<script>` en `{% block extra_js %}`,
  un bloque que ningún ancestro declara: Django lo descarta en silencio y la cascada
  Secretaría → Subsecretaría nunca llega al navegador.
* **FE-08** — los errores no de campo (`unique_together`, `clean()` de form) no se
  renderizaban en ninguna pantalla de Configuración salvo los pasos 2 y 3 del wizard: el
  formulario volvía igual, sin una sola explicación.
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from core import rbac
from core.models import Localidad, Municipio, Provincia, Secretaria, Subsecretaria
from users.models import Capacidad, RolMeta


def usuario_con(*codigos, username=None):
    """Usuario de backoffice con exactamente esas capacidades (ninguna = sin rol)."""
    usuario = User.objects.create_user(username or f"cfg-{'-'.join(codigos) or 'sin-rol'}", password="Clave-Seg-2026x")
    if not codigos:
        return usuario
    grupo, _ = Group.objects.get_or_create(name="Rol configuración " + "-".join(codigos))
    RolMeta.objects.get_or_create(grupo=grupo, defaults={"categoria": rbac.CATEGORIA_BACKOFFICE, "activo": True})
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    usuario.groups.add(grupo)
    return usuario


class GeografiaPaginacionTests(TestCase):
    """FE-04: las tres pantallas de Geografía dibujan su pie de paginación."""

    @classmethod
    def setUpTestData(cls):
        cls.provincia = Provincia.objects.create(nombre="Chaco")
        cls.municipio = Municipio.objects.create(nombre="Resistencia", provincia=cls.provincia)
        # 21 de cada una: una más que `paginate_by`, que es lo que vuelve inalcanzable
        # la última fila cuando no hay controles.
        for i in range(21):
            provincia = Provincia.objects.create(nombre=f"Provincia {i:02d}")
            municipio = Municipio.objects.create(nombre=f"Municipio {i:02d}", provincia=provincia)
            Localidad.objects.create(nombre=f"Localidad {i:02d}", municipio=municipio)

    def setUp(self):
        self.client.force_login(usuario_con("config.administrar", username="cfg-geo"))

    def test_la_pagina_1_ofrece_la_2(self):
        for ruta, texto in (
            ("configuracion:provincias", "22 provincias"),
            ("configuracion:municipios", "22 municipios"),
            ("configuracion:localidades", "21 localidades"),
        ):
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(reverse(ruta))

                self.assertContains(respuesta, 'href="?page=2"')
                self.assertContains(respuesta, 'aria-label="Página siguiente"')
                self.assertContains(respuesta, texto)

    def test_la_ultima_fila_es_alcanzable(self):
        respuesta = self.client.get(reverse("configuracion:localidades"), {"page": 2})

        self.assertContains(respuesta, "Localidad 20")
        self.assertContains(respuesta, 'aria-label="Página anterior"')

    def test_el_post_invalido_devuelve_la_lista_paginada(self):
        """Un alta inválida vuelve a la lista: tiene que volver paginada, no entera."""
        for ruta, datos, clave in (
            ("configuracion:provincia_crear", {"nombre": ""}, "provincias"),
            ("configuracion:municipio_crear", {"nombre": "", "provincia": self.provincia.pk}, "municipios"),
            ("configuracion:localidad_crear", {"nombre": "", "municipio": self.municipio.pk}, "localidades"),
        ):
            with self.subTest(ruta=ruta):
                respuesta = self.client.post(reverse(ruta), datos)

                self.assertEqual(respuesta.status_code, 200)
                self.assertIn("page_obj", respuesta.context)
                self.assertEqual(len(respuesta.context[clave]), 20)
                self.assertContains(respuesta, 'href="?page=2"')

    def test_el_error_de_edicion_abre_el_modal_de_la_fila_aunque_no_esté_en_la_página_1(self):
        """La fila editada queda fuera de la página 1: la vista tiene que traer su página."""
        ultima = Localidad.objects.order_by("nombre").last()

        respuesta = self.client.post(
            reverse("configuracion:localidad_editar", args=[ultima.pk]),
            {"nombre": "", "municipio": ultima.municipio_id},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, ultima.nombre)
        self.assertEqual(respuesta.context["abrir_modal_pk"], ultima.pk)

    def test_una_sola_pagina_no_dibuja_controles(self):
        Localidad.objects.exclude(pk=Localidad.objects.first().pk).delete()

        respuesta = self.client.get(reverse("configuracion:localidades"))

        self.assertNotContains(respuesta, "?page=")

    def test_sin_capacidad_no_entra(self):
        self.client.force_login(usuario_con(username="cfg-sin-rol"))

        self.assertNotEqual(self.client.get(reverse("configuracion:localidades")).status_code, 200)

    def test_anonimo_va_al_login(self):
        self.client.logout()

        respuesta = self.client.get(reverse("configuracion:localidades"))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("next=/configuracion/localidades/", respuesta.url)

    def test_superusuario_entra(self):
        self.client.force_login(User.objects.create_superuser("cfg-super", password="Clave-Seg-2026x"))

        self.assertContains(self.client.get(reverse("configuracion:localidades")), 'href="?page=2"')


class WizardCascadaTests(TestCase):
    """FE-05: el JS del paso 1 llega al navegador y la cascada se puede ejecutar."""

    @classmethod
    def setUpTestData(cls):
        cls.secretaria = Secretaria.objects.create(nombre="Desarrollo Social")
        Subsecretaria.objects.create(nombre="Niñez", secretaria=cls.secretaria)

    def setUp(self):
        self.client.force_login(usuario_con("programa.configurar", username="cfg-wizard"))

    def test_el_paso_1_incluye_el_script_de_la_cascada(self):
        html = self.client.get(reverse("configuracion:programa_wizard_paso1")).content.decode()

        self.assertIn(reverse("core:ajax_load_subsecretarias"), html)
        self.assertIn("subsecretariaSelect", html)

    def test_el_script_va_en_el_bloque_que_el_shell_declara(self):
        plantilla = "configuracion/templates/configuracion/programa_wizard_paso1.html"
        from pathlib import Path

        from django.conf import settings

        contenido = Path(settings.BASE_DIR, plantilla).read_text(encoding="utf-8")

        self.assertIn("{% block customJS %}", contenido)
        self.assertNotIn("{% block extra_js %}", contenido)

    def test_la_cascada_avisa_cuando_la_respuesta_no_es_ok(self):
        html = self.client.get(reverse("configuracion:programa_wizard_paso1")).content.decode()

        self.assertIn("if (!r.ok)", html)
        self.assertIn("window.toast('error'", html)

    def test_la_api_de_la_cascada_contesta_las_subsecretarias(self):
        respuesta = self.client.get(reverse("core:ajax_load_subsecretarias"), {"secretaria": self.secretaria.pk})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([s["nombre"] for s in respuesta.json()], ["Niñez"])


class ErroresNoDeCampoTests(TestCase):
    """FE-08: un duplicado de `unique_together` se ve en la pantalla."""

    @classmethod
    def setUpTestData(cls):
        cls.provincia = Provincia.objects.create(nombre="Chaco")
        cls.municipio = Municipio.objects.create(nombre="Resistencia", provincia=cls.provincia)
        cls.localidad = Localidad.objects.create(nombre="Barranqueras", municipio=cls.municipio)
        cls.secretaria = Secretaria.objects.create(nombre="Desarrollo Social")
        cls.subsecretaria = Subsecretaria.objects.create(nombre="Niñez", secretaria=cls.secretaria)

    def setUp(self):
        self.client.force_login(usuario_con("config.administrar", username="cfg-errores"))

    def test_localidad_duplicada_muestra_el_motivo(self):
        respuesta = self.client.post(
            reverse("configuracion:localidad_crear"),
            {"nombre": "Barranqueras", "municipio": self.municipio.pk},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["form"].non_field_errors())
        self.assertContains(respuesta, "Revisá el formulario")
        self.assertContains(respuesta, respuesta.context["form"].non_field_errors()[0])
        self.assertEqual(Localidad.objects.filter(nombre="Barranqueras").count(), 1)

    def test_municipio_duplicado_muestra_el_motivo(self):
        respuesta = self.client.post(
            reverse("configuracion:municipio_crear"),
            {"nombre": "Resistencia", "provincia": self.provincia.pk},
        )

        self.assertContains(respuesta, "Revisá el formulario")
        self.assertContains(respuesta, respuesta.context["form"].non_field_errors()[0])

    def test_subsecretaria_duplicada_muestra_el_motivo(self):
        respuesta = self.client.post(
            reverse("configuracion:subsecretaria_crear"),
            {"nombre": "Niñez", "secretaria": self.secretaria.pk, "activo": "on"},
        )

        self.assertContains(respuesta, "Revisá el formulario")
        self.assertContains(respuesta, respuesta.context["form"].non_field_errors()[0])

    def test_el_error_de_edicion_no_se_filtra_al_modal_de_alta(self):
        """El `form` del contexto es uno solo: el error tiene que salir una sola vez.

        Sin acotar el include del modal de alta, «Revisá el formulario» quedaba también
        dentro de «Nueva localidad»: oculto hasta que el usuario cerraba la edición y
        abría el alta, y ahí aparecía un error que no era de ese formulario.
        """
        otra = Localidad.objects.create(nombre="Fontana", municipio=self.municipio)

        respuesta = self.client.post(
            reverse("configuracion:localidad_editar", args=[otra.pk]),
            {"nombre": "Barranqueras", "municipio": self.municipio.pk},
        )

        html = respuesta.content.decode()
        self.assertEqual(respuesta.context["abrir_modal_pk"], otra.pk)
        self.assertEqual(html.count("Revisá el formulario"), 1)
        self.assertEqual(html.count(respuesta.context["form"].non_field_errors()[0]), 1)
        # El único bloque que lo trae es el modal de edición de esa fila.
        self.assertLess(html.index("Revisá el formulario"), html.index("titulo-crear-localidad"))

    def test_el_error_del_alta_sale_una_vez_y_en_el_modal_de_alta(self):
        respuesta = self.client.post(
            reverse("configuracion:localidad_crear"),
            {"nombre": "Barranqueras", "municipio": self.municipio.pk},
        )

        html = respuesta.content.decode()
        self.assertEqual(html.count("Revisá el formulario"), 1)
        self.assertGreater(html.index("Revisá el formulario"), html.index("titulo-crear-localidad"))

    def test_el_wizard_muestra_el_error_de_la_lista_de_espera_sin_cupo(self):
        """`ProgramaPaso3Form.clean()` es el único error no de campo vivo del wizard."""
        self.client.force_login(usuario_con("programa.configurar", username="cfg-wizard-errores"))
        sesion = self.client.session
        sesion["wizard_programa_nuevo"] = {
            "paso1": {
                "nombre": "P",
                "codigo": "P",
                "descripcion": "",
                "secretaria": self.secretaria.pk,
                "subsecretaria": self.subsecretaria.pk,
            },
            "paso2": {"naturaleza": "BECA"},
        }
        sesion.save()

        respuesta = self.client.post(
            reverse("configuracion:programa_wizard_paso3"),
            {"tiene_lista_espera": "on"},
        )

        self.assertContains(respuesta, "Revisá el formulario")
        self.assertContains(respuesta, "La lista de espera requiere que se configure un cupo máximo.")

    def test_las_pantallas_de_configuracion_usan_la_pieza_unica(self):
        """Nada de `{{ form.non_field_errors }}` suelto: la pieza es una sola."""
        from pathlib import Path

        from django.conf import settings

        base = Path(settings.BASE_DIR, "configuracion", "templates", "configuracion")
        sin_pieza = [
            archivo.name
            for archivo in sorted(base.glob("*.html"))
            if "non_field_errors" in archivo.read_text(encoding="utf-8")
            and "components/_form_errores.html" not in archivo.read_text(encoding="utf-8")
        ]

        self.assertEqual(sin_pieza, [])
