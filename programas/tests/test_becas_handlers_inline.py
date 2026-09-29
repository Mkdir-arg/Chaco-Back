"""Datos del ciudadano fuera de los handlers inline (Cambio 95).

El nombre y el apellido los carga el ciudadano en la inscripción pública. Metidos
dentro de un ``onclick="fn('...')"`` el autoescape no alcanza: el navegador decodifica
``&#x27;`` a ``'`` antes de compilar el handler, así que un apellido con comilla rompe
el botón y uno armado a propósito se ejecuta como código. Los botones del cupo llevan
esos datos en atributos ``data-*`` y un listener delegado los lee de ``dataset``.
"""

import json
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.tests.js_harness import atributos_de, correr_script, requiere_node, script_con
from legajos.models import Ciudadano
from programas.models import Convocatoria, Formulario, ListaEspera, Relevamiento, Segmento

APELLIDO_CON_COMILLA = "O'Brien"
# Cierra el literal JS del handler viejo y encadena una expresión propia.
APELLIDO_QUE_CIERRA_EL_LITERAL = "x',window.__inyectado=1,'"
NOMBRE_CON_MARCADO = '<img src=x onerror="window.__inyectado=1">'


class CupoSegmentoHandlersInlineTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin-cupo-xss", password="x")
        self.segmento = Segmento.objects.create(nombre="Seg XSS", cupo_maximo=100)
        convocatoria = Convocatoria.objects.create(
            nombre="Conv XSS", segmento=self.segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        relevamiento = Relevamiento.objects.create(
            convocatoria=convocatoria,
            territorial=self.admin,
            fecha_asignada=date(2026, 6, 1),
            zona="A",
            estado=Relevamiento.Estado.FINALIZADO,
        )
        self.nombres = []
        for indice, apellido in enumerate((APELLIDO_CON_COMILLA, APELLIDO_QUE_CIERRA_EL_LITERAL)):
            ciudadano = Ciudadano.objects.create(
                dni=f"7070070{indice}", nombre="Ana", apellido=apellido, fecha_nacimiento=date(1990, 1, 1), genero="F"
            )
            self.nombres.append(f"Ana {apellido}")

            def formulario(estado, _ciudadano=ciudadano):
                return Formulario.objects.create(
                    relevamiento=relevamiento,
                    ciudadano=_ciudadano,
                    celular="1",
                    email_contacto="a@b.com",
                    estado=estado,
                )

            formulario(Formulario.Estado.APROBADO)  # pestaña Beneficiarios
            formulario(Formulario.Estado.ENVIADO)  # pestaña Pendientes de cupo
            en_espera = formulario(Formulario.Estado.APROBADO)  # pestaña Lista de espera
            ListaEspera.objects.create(formulario=en_espera, segmento=self.segmento, posicion=indice + 1)
            # El aprobado que está en espera también cae en Beneficiarios: no afecta a lo que se mide.

    def _html(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("becas:cupo_segmento", args=[self.segmento.pk]))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_ningun_handler_on_recibe_el_nombre_del_ciudadano(self):
        for tag, attrs in atributos_de(self._html()):
            for nombre_attr, valor in attrs.items():
                if not nombre_attr.startswith("on"):
                    continue
                for apellido in (APELLIDO_CON_COMILLA, APELLIDO_QUE_CIERRA_EL_LITERAL):
                    self.assertNotIn(apellido, valor, f"<{tag} {nombre_attr}> interpola el nombre del ciudadano")

    def test_las_tres_acciones_llevan_el_nombre_en_data_nombre(self):
        botones = [
            attrs for tag, attrs in atributos_de(self._html()) if tag == "button" and "data-cupo-accion" in attrs
        ]
        for accion in ("baja", "promover", "espera"):
            nombres = {attrs["data-nombre"] for attrs in botones if attrs["data-cupo-accion"] == accion}
            self.assertEqual(nombres, set(self.nombres), accion)
        self.assertTrue(all(attrs["data-pk"].isdigit() for attrs in botones))

    @requiere_node
    def test_el_listener_abre_la_misma_confirmacion_y_envia_el_mismo_form(self):
        script = script_con(self._html(), "data-cupo-accion")
        nombre = f"Ana {APELLIDO_QUE_CIERRA_EL_LITERAL}"

        log = correr_script(
            script,
            f"""
            __click({{cupoAccion: 'baja', pk: '11', nombre: {json.dumps(nombre)}}});
            __click({{cupoAccion: 'promover', pk: '22', nombre: {json.dumps(nombre)}}});
            __click({{cupoAccion: 'espera', pk: '33', nombre: {json.dumps(nombre)}}});
            __confirmar();
            """,
        )

        baja, promover, espera = log["modal"]
        self.assertEqual(baja["title"], "¿Dar de baja al beneficiario?")
        self.assertEqual(baja["message"], 'Se liberará 1 cupo en "Seg XSS". ¿Confirmar?')
        self.assertTrue(baja["danger"])
        self.assertEqual(promover["title"], f"¿Promover a {nombre} como beneficiario?")
        self.assertEqual(promover["confirmText"], "Promover")
        self.assertEqual(
            espera["message"],
            f'El formulario de "{nombre}" se agregará al final de la lista de espera de "Seg XSS".',
        )
        self.assertEqual(log["submits"], ["form-baja-11", "form-promover-22", "form-espera-33"])


def _form_de_reactivar(html):
    """Los elementos del ``<form data-reactivar-form>`` del modal, hasta su ``</form>``."""
    marca = html.find("data-reactivar-form")
    if marca == -1:
        raise AssertionError("La página no trae el <form data-reactivar-form> del modal de reactivar")
    inicio = html.rfind("<form", 0, marca)
    return atributos_de(html[inicio : html.index("</form>", marca)])


class ReactivarConvocatoriaNombreTests(TestCase):
    """El modal de reactivar recibe el nombre de la convocatoria como texto, nunca como marcado."""

    def setUp(self):
        self.admin = User.objects.create_superuser("admin-reactivar-xss", password="x")
        segmento = Segmento.objects.create(nombre="Seg R", cupo_maximo=100)
        hoy = timezone.localdate()
        Convocatoria.objects.create(
            nombre=NOMBRE_CON_MARCADO,
            segmento=segmento,
            fecha_inicio=hoy - timedelta(days=60),
            fecha_fin=hoy - timedelta(days=5),
            activo=False,
        )

    def _html(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("becas:convocatorias"))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_el_boton_lleva_el_nombre_en_data_nombre(self):
        botones = [attrs for _, attrs in atributos_de(self._html()) if "data-reactivar-url" in attrs]
        self.assertEqual([attrs["data-nombre"] for attrs in botones], [NOMBRE_CON_MARCADO])

    def test_el_nombre_no_llega_a_handlers_on_ni_a_atributos_alpine(self):
        html = self._html()
        self.assertNotIn(NOMBRE_CON_MARCADO, html)  # nunca como marcado crudo
        for tag, attrs in atributos_de(html):
            for nombre_attr, valor in attrs.items():
                if nombre_attr.startswith(("on", "x-", "@", ":")):
                    self.assertNotIn("<img", valor, f"<{tag} {nombre_attr}> interpola el nombre")

    def test_el_modal_pinta_el_nombre_con_x_text(self):
        html = self._html()
        marca = html.find("data-reactivar-modal")
        self.assertNotEqual(marca, -1, "La página no trae el modal de reactivar")
        modal = html[marca : html.index("</form>", marca)]
        self.assertNotIn("x-html", modal)
        self.assertIn(("p", "nombre"), [(tag, attrs.get("x-text")) for tag, attrs in atributos_de(modal)])

    @requiere_node
    def test_el_listener_abre_el_modal_con_el_nombre_como_texto(self):
        script = script_con(self._html(), "data-reactivar-url")
        url = "/becas/convocatorias/7/reactivar/"

        log = correr_script(
            script,
            f"""
            __log.eventos = [];
            window.CustomEvent = function (tipo, opciones) {{ this.type = tipo; this.detail = opciones.detail; }};
            window.dispatchEvent = function (evento) {{ __log.eventos.push(evento); }};
            __click({{reactivarUrl: {json.dumps(url)}, nombre: {json.dumps(NOMBRE_CON_MARCADO)}}});
            var modal = reactivarConvocatoria('2026-09-29');
            modal.$refs = {{fecha: {{focus: function () {{ __log.foco = 'fecha'; }}}}}};
            modal.$nextTick = function (fn) {{ fn(); }};
            modal.abrir(__log.eventos[0].detail);
            __log.estado = {{abierto: modal.abierto, url: modal.url, nombre: modal.nombre, fecha: modal.fecha}};
            """,
        )

        self.assertEqual([evento["type"] for evento in log["eventos"]], ["becas-reactivar"])
        self.assertEqual(log["swal"], [])
        # El nombre llega tal cual como dato: x-text lo pinta como textContent.
        self.assertEqual(
            log["estado"], {"abierto": True, "url": url, "nombre": NOMBRE_CON_MARCADO, "fecha": "2026-09-29"}
        )
        self.assertEqual(log["foco"], "fecha")


class ReactivarConvocatoriaModalTests(TestCase):
    """POP-3: «Reactivar» abre un modal propio con form POST, sin depender de SweetAlert2."""

    def setUp(self):
        self.admin = User.objects.create_superuser("admin-reactivar-modal", password="x")
        segmento = Segmento.objects.create(nombre="Seg M", cupo_maximo=100)
        self.hoy = timezone.localdate()
        self.conv = Convocatoria.objects.create(
            nombre="Convocatoria vencida",
            segmento=segmento,
            fecha_inicio=self.hoy - timedelta(days=60),
            fecha_fin=self.hoy - timedelta(days=5),
            activo=False,
        )

    def _html(self, client=None):
        client = client or self.client
        client.force_login(self.admin)
        response = client.get(reverse("becas:convocatorias"))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_el_modal_trae_un_form_post_con_csrf_y_fecha_fin(self):
        (tag, form), *campos = _form_de_reactivar(self._html())

        self.assertEqual(tag, "form")
        self.assertEqual(form["method"], "post")
        self.assertEqual(form[":action"], "url")
        inputs = {attrs.get("name"): attrs for tag, attrs in campos if tag == "input"}
        self.assertTrue(inputs["csrfmiddlewaretoken"]["value"])
        fecha = inputs["fecha_fin"]
        self.assertEqual(fecha["type"], "date")
        self.assertIn("required", fecha)
        self.assertEqual(fecha[":min"], "min")
        self.assertIn("nodo-field", fecha["class"].split())
        self.assertIn(("label", fecha["id"]), [(tag, attrs.get("for")) for tag, attrs in campos])

    def test_el_modal_es_un_dialogo_accesible_con_fecha_minima_hoy(self):
        html = self._html()
        marca = html.find("data-reactivar-modal")
        self.assertNotEqual(marca, -1, "La página no trae el modal de reactivar")
        # El modal global del base también es role=dialog: se busca dentro del de reactivar.
        (dialogo,) = [attrs for _, attrs in atributos_de(html[marca:]) if attrs.get("role") == "dialog"]
        self.assertEqual(dialogo["aria-modal"], "true")
        self.assertIn(f'id="{dialogo["aria-labelledby"]}"', html)
        (raiz,) = [attrs for _, attrs in atributos_de(html) if "@becas-reactivar.window" in attrs]
        self.assertEqual(raiz["x-data"], f"reactivarConvocatoria('{self.hoy.isoformat()}')")
        self.assertIn("@keydown.escape.window", raiz)

    def test_el_script_ya_no_depende_de_swal(self):
        script = script_con(self._html(), "data-reactivar-url")
        self.assertNotIn("Swal", script)

    def test_reactivar_con_el_form_del_modal_activa_la_convocatoria(self):
        cliente = Client(enforce_csrf_checks=True)
        html = self._html(cliente)
        (boton,) = [attrs for _, attrs in atributos_de(html) if "data-reactivar-url" in attrs]
        _, *campos = _form_de_reactivar(html)
        token = next(attrs["value"] for _, attrs in campos if attrs.get("name") == "csrfmiddlewaretoken")
        nueva = self.hoy + timedelta(days=30)

        response = cliente.post(
            boton["data-reactivar-url"], {"csrfmiddlewaretoken": token, "fecha_fin": nueva.isoformat()}
        )

        self.assertRedirects(response, reverse("becas:convocatorias"), fetch_redirect_response=False)
        self.conv.refresh_from_db()
        self.assertTrue(self.conv.activo)
        self.assertEqual(self.conv.fecha_fin, nueva)

    def test_el_servidor_rechaza_una_fecha_pasada_aunque_se_saltee_el_min_del_navegador(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("becas:convocatoria_reactivar", args=[self.conv.pk]),
            {"fecha_fin": (self.hoy - timedelta(days=1)).isoformat()},
            follow=True,
        )

        self.assertIn(
            "La nueva fecha de fin debe ser hoy o una fecha posterior.",
            [str(mensaje) for mensaje in response.context["messages"]],
        )
        self.conv.refresh_from_db()
        self.assertFalse(self.conv.activo)
