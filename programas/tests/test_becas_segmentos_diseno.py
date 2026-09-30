"""Ajustes de diseño de las pantallas de Segmentos (PR W3-L-B, Cambio 96.x).

Cubre lo que se aplicó pantalla por pantalla:

- listado (``config/segmento_list.html`` + ``_segmentos_table.html``): encabezado
  común ``{% page_header %}`` sin tamaño en línea (TIT-13/14), alta con ``fa-plus``
  (TIT-18), tabla ``.nodo-*`` con acciones ``.nodo-icon-btn`` nombradas, sin el pie
  de paginación fijo en «1 de 1» (CMP-11) y sin ``focus:ring-brand`` (TWBUILD);
- detalle (``config/segmento_detail.html``): «Activar segmento» deja de ser rojo y
  confirma en tono de marca con «Sí, activar» (POP-13 / CMP-5 / POP-12), «Desactivar»
  confirma en rojo con la consecuencia, «Reanudar» usa ``fa-play`` (DC-5), el
  segmento pausado muestra su badge (CMP-10) y los cuatro modales son diálogos
  accesibles con ``x-becas-modal`` sin perder ningún campo (fila 80 del inventario);
- ``coordinador_asignar``: un solo aviso por acción en el POST clásico (ALR-8).
"""

from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.contrib.messages import get_messages
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.tests.js_harness import atributos_de
from programas.management.commands.seed_becas import ROL_ADMIN
from programas.models import AsignacionCoordinador, ProgramaSiis, Segmento

PLANTILLAS = (
    "programas/becas/config/segmento_list.html",
    "programas/becas/config/segmento_detail.html",
    "programas/becas/config/segmento_form.html",
    "programas/becas/config/_segmentos_table.html",
    "programas/becas/config/_subsegmentos_panel.html",
    "programas/becas/config/_requisitos_panel.html",
)


class SinHeroiconsTests(SimpleTestCase):
    """DC-6: en estas pantallas los íconos son Font Awesome, no SVG en línea."""

    def test_las_plantillas_del_pr_no_traen_svg(self):
        raiz = Path(settings.BASE_DIR) / "programas" / "templates"
        for ruta in PLANTILLAS:
            with self.subTest(ruta):
                self.assertNotIn("<svg", (raiz / ruta).read_text(encoding="utf-8"))


class _BaseSegmentos(TestCase):
    """Un programa con un segmento visible para un administrador de Becas."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_becas", stdout=StringIO())
        cls.admin = User.objects.create_user("admin_segmentos", password="x")
        cls.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        cls.programa = ProgramaSiis.objects.create(siis_programa_id=41, nombre="Becas de estudio")
        cls.segmento = Segmento.objects.create(
            nombre="Estudiantes terciarios",
            descripcion="Nivel superior no universitario",
            cupo_maximo=120,
            programa=cls.programa,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def _elementos(self, url):
        html = self.client.get(url).content.decode()
        return html, atributos_de(html)

    def _uno(self, elementos, predicado):
        encontrados = [attrs for _, attrs in elementos if predicado(attrs)]
        self.assertEqual(len(encontrados), 1, encontrados)
        return encontrados[0]


class SegmentoListEncabezadoTests(_BaseSegmentos):
    def setUp(self):
        super().setUp()
        self.html, self.elementos = self._elementos(reverse("becas:segmentos"))

    def test_titulo_usa_el_encabezado_comun_sin_tamano_en_linea(self):
        # TIT-13: el h1 salía con style="font-size:28px; letter-spacing:-0.5px".
        h1 = self._uno(self.elementos, lambda a: a.get("class", "").startswith("text-3xl font-extrabold"))
        self.assertNotIn("style", h1)
        self.assertIn(">Segmentos y subsegmentos</h1>", self.html)

    def test_el_contenedor_usa_el_ritmo_unico(self):
        # TIT-14: mb-8 + mb-6 → space-y-5, como el resto de las pantallas.
        self.assertTrue(any("space-y-5" in a.get("class", "").split() for _, a in self.elementos))
        self.assertNotIn('class="mb-8"', self.html)

    def test_alta_con_icono_de_font_awesome(self):
        # TIT-18: el botón traía el PlusIcon de Heroicons en SVG.
        self.assertIn('<i class="fas fa-plus" aria-hidden="true"></i> Nuevo segmento', self.html)

    def test_sin_utilidad_de_tailwind_fuera_del_build(self):
        # TWBUILD: focus:ring-brand no existe en el CSS compilado (el checkbox
        # quedaba sin anillo de foco). Ahora el control va por .nodo-checks.
        self.assertNotIn("focus:ring-brand", self.html)
        self.assertIn('class="nodo-checks"', self.html)


class SegmentoListModalesTests(_BaseSegmentos):
    def setUp(self):
        super().setUp()
        self.html, self.elementos = self._elementos(reverse("becas:segmentos"))

    def test_los_dos_modales_son_dialogos_con_la_directiva(self):
        for titulo_id, estado in (("modal-crear-titulo", "modalCrear"), ("modal-editar-titulo", "modalEditar")):
            panel = self._uno(self.elementos, lambda a, t=titulo_id: a.get("aria-labelledby") == t)
            self.assertEqual(panel.get("role"), "dialog")
            self.assertEqual(panel.get("aria-modal"), "true")
            self.assertIn("max-h-[90vh]", panel["class"].split())
            self.assertIn("flex-col", panel["class"].split())
            overlay = self._uno(self.elementos, lambda a, e=estado: a.get("x-becas-modal") == e)
            self.assertEqual(overlay.get("x-show"), estado)
        self.assertIn("custom/js/becas-modal.js", self.html)

    def test_los_formularios_conservan_sus_campos(self):
        nombres = {a.get("name") for tag, a in self.elementos if tag in ("input", "select", "textarea")}
        esperados = {
            "csrfmiddlewaretoken",
            "programa",
            "nombre",
            "descripcion",
            "cupo_maximo",
            "coordinador",
            "activo",
            "requiere_gps",
            "siis_jurid",
            "siis_id_fun_x_plan",
        }
        self.assertTrue(esperados <= nombres, esperados - nombres)
        crear = self._uno(self.elementos, lambda a: a.get("action") == reverse("becas:segmento_crear"))
        self.assertEqual(crear.get("method"), "post")
        self.assertIn("data-ajax", crear)


class SegmentosTablaTests(_BaseSegmentos):
    def test_sin_el_pie_de_paginacion_falso(self):
        # CMP-11: decía «1 de 1» con los dos botones deshabilitados siempre.
        html, _ = self._elementos(reverse("becas:segmentos"))
        self.assertNotIn("1 de 1", html)
        self.assertNotIn("Anterior", html)

    def test_encabezados_y_acciones_con_las_clases_del_sistema(self):
        html, elementos = self._elementos(reverse("becas:segmentos"))
        ths = [a for tag, a in elementos if tag == "th"]
        self.assertTrue(ths)
        for th in ths:
            self.assertIn("nodo-th", th.get("class", "").split())
        self.assertTrue(any("nodo-thead-row" in a.get("class", "").split() for _, a in elementos))
        acciones = [a for _, a in elementos if "nodo-icon-btn" in a.get("class", "").split()]
        self.assertEqual(len(acciones), 2, acciones)
        etiquetas = {a.get("aria-label") for a in acciones}
        self.assertEqual(
            etiquetas,
            {"Editar el segmento Estudiantes terciarios", "Ver el segmento Estudiantes terciarios"},
        )

    def test_el_segmento_pausado_muestra_su_badge(self):
        # CMP-10: un segmento pausado no se distinguía de uno activo.
        html, _ = self._elementos(reverse("becas:segmentos"))
        self.assertNotIn(">Pausado<", html)
        Segmento.objects.filter(pk=self.segmento.pk).update(pausado=True, pausa_motivo="Corte de presupuesto")
        html, _ = self._elementos(reverse("becas:segmentos"))
        self.assertIn(">Pausado<", html)

    def test_el_segmento_inactivo_no_se_marca_en_rojo(self):
        # DC-2: apagado no es un error → badge gris, no danger.
        Segmento.objects.filter(pk=self.segmento.pk).update(activo=False)
        html, _ = self._elementos(reverse("becas:segmentos"))
        self.assertIn('<span class="badge badge-gray badge-dot">Inactivo</span>', html)
        self.assertNotIn("badge-danger", html)


class SegmentoDetalleEstadoTests(_BaseSegmentos):
    def _boton_toggle(self):
        url = reverse("becas:segmento_toggle", args=[self.segmento.pk])
        _, elementos = self._elementos(reverse("becas:segmento_detalle", args=[self.segmento.pk]))
        return self._uno(elementos, lambda a: a.get("data-confirm-url") == url)

    def test_activar_no_es_rojo_y_confirma_en_tono_de_marca(self):
        # POP-13 / CMP-5 / POP-12: era btn-danger con fa-ban y confirmaba con «Sí».
        Segmento.objects.filter(pk=self.segmento.pk).update(activo=False)
        boton = self._boton_toggle()
        clases = boton["class"].split()
        self.assertIn("btn-brand", clases)
        self.assertNotIn("btn-danger", clases)
        self.assertEqual(boton.get("data-confirm-danger"), "false")
        self.assertEqual(boton.get("data-confirm-ok"), "Sí, activar")
        self.assertEqual(boton.get("data-confirm-title"), "¿Activar el segmento?")

    def test_activar_usa_el_icono_de_tilde_y_no_el_de_prohibido(self):
        Segmento.objects.filter(pk=self.segmento.pk).update(activo=False)
        html, _ = self._elementos(reverse("becas:segmento_detalle", args=[self.segmento.pk]))
        self.assertIn('<i class="fas fa-circle-check" aria-hidden="true"></i> Activar segmento', html)
        self.assertNotIn("fa-ban", html)

    def test_desactivar_sigue_en_rojo_y_dice_la_consecuencia(self):
        boton = self._boton_toggle()
        self.assertIn("btn-danger", boton["class"].split())
        self.assertEqual(boton.get("data-confirm-danger"), "true")
        self.assertEqual(boton.get("data-confirm-ok"), "Sí, desactivar")
        self.assertIn("deja de estar disponible para operar", boton.get("data-confirm-text", ""))
        self.assertIn(self.segmento.nombre, boton.get("data-confirm-text", ""))

    def test_reanudar_usa_el_icono_de_reproducir(self):
        # DC-5: «Reanudar» salía con el ícono de pausa.
        url = reverse("becas:segmento_detalle", args=[self.segmento.pk])
        html, _ = self._elementos(url)
        self.assertIn('<i class="fas fa-pause" aria-hidden="true"></i> Pausar segmento', html)
        Segmento.objects.filter(pk=self.segmento.pk).update(pausado=True, pausa_motivo="Sin fondos")
        html, _ = self._elementos(url)
        self.assertIn('<i class="fas fa-play" aria-hidden="true"></i> Reanudar segmento', html)

    def test_el_encabezado_marca_la_pausa_y_arma_las_migas(self):
        Segmento.objects.filter(pk=self.segmento.pk).update(pausado=True, pausa_motivo="Sin fondos")
        html, elementos = self._elementos(reverse("becas:segmento_detalle", args=[self.segmento.pk]))
        self.assertIn(">Pausado<", html)
        migas = self._uno(elementos, lambda a: a.get("aria-label") == "Migas")
        self.assertEqual(migas.get("class"), None)
        self.assertIn(">Programas</a>", html)
        self.assertIn(self.programa.nombre, html)
        volver = self._uno(elementos, lambda a: a.get("aria-label") == "Volver a segmentos")
        self.assertEqual(volver["href"], reverse("becas:segmentos"))


class SegmentoDetalleModalesTests(_BaseSegmentos):
    def setUp(self):
        super().setUp()
        self.html, self.elementos = self._elementos(reverse("becas:segmento_detalle", args=[self.segmento.pk]))

    def test_los_cuatro_modales_son_dialogos_con_la_directiva(self):
        modales = {
            "modal-sub-crear-titulo": "modalSub",
            "modal-sub-editar-titulo": "modalSubEdit",
            "modal-req-crear-titulo": "modalReq",
            "modal-req-editar-titulo": "modalReqEdit",
        }
        for titulo_id, estado in modales.items():
            panel = self._uno(self.elementos, lambda a, t=titulo_id: a.get("aria-labelledby") == t)
            self.assertEqual(panel.get("role"), "dialog")
            self.assertEqual(panel.get("aria-modal"), "true")
            self.assertIn("max-h-[90vh]", panel["class"].split())
            overlay = self._uno(self.elementos, lambda a, e=estado: a.get("x-becas-modal") == e)
            self.assertEqual(overlay.get("x-show"), estado)
        self.assertIn("custom/js/becas-modal.js", self.html)

    def test_el_modal_de_requisito_conserva_todos_sus_campos(self):
        # Fila 80 del inventario: el POST reemplaza el registro entero, así que un
        # control ausente se guardaría vacío.
        editar = self.html.split('id="form-req-editar"', 1)[1]
        for campo in (
            "texto",
            "tipo",
            "obligatorio",
            "orden",
            "opciones_texto",
            "presentacion",
            "canal",
            "destino_siis",
        ):
            self.assertIn(f'name="{campo}"', editar, campo)

    def test_el_modal_de_subsegmento_conserva_todos_sus_campos(self):
        crear = self._uno(
            self.elementos,
            lambda a: a.get("action") == reverse("becas:subsegmento_crear", args=[self.segmento.pk]),
        )
        self.assertIn("data-ajax", crear)
        nombres = {a.get("name") for tag, a in self.elementos if tag in ("input", "select", "textarea")}
        for campo in ("nombre", "descripcion", "referente", "cupo_maximo", "origin"):
            self.assertIn(campo, nombres, campo)


class CoordinadorAsignarAvisoTests(_BaseSegmentos):
    """ALR-8: el POST clásico deja un solo aviso, y no se traga ningún error."""

    def _asignar(self, datos):
        resp = self.client.post(
            reverse("becas:coordinador_asignar", args=[self.segmento.pk]),
            datos,
            follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        return [(m.level_tag, str(m)) for m in get_messages(resp.wsgi_request)]

    def test_un_solo_aviso_que_nombra_la_accion(self):
        avisos = self._asignar({"coordinador": ""})
        self.assertEqual(len(avisos), 1, avisos)
        nivel, texto = avisos[0]
        self.assertEqual(nivel, "error")
        self.assertTrue(texto.startswith("No se pudo asignar el coordinador."), texto)
        self.assertIn("requerido", texto)

    def test_los_errores_que_no_son_del_selector_dejan_de_perderse(self):
        # Antes solo se leían form.errors["coordinador"]: cualquier otro error
        # (de formulario o de otro campo) redirigía sin decir nada.
        def clean(self):
            self.add_error(None, "El segmento está pausado.")
            return self.cleaned_data

        with patch("programas.forms.AsignacionCoordinadorForm.clean", clean):
            avisos = self._asignar({"coordinador": self.admin.pk})
        self.assertEqual(len(avisos), 1, avisos)
        self.assertIn("El segmento está pausado.", avisos[0][1])
        self.assertFalse(AsignacionCoordinador.objects.filter(segmento=self.segmento).exists())
