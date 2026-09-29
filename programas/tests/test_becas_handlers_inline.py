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
from django.test import TestCase
from django.urls import reverse

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


class ReactivarConvocatoriaNombreTests(TestCase):
    """El pop-up de reactivar arma su ``html`` con el nombre escapado."""

    def setUp(self):
        self.admin = User.objects.create_superuser("admin-reactivar-xss", password="x")
        segmento = Segmento.objects.create(nombre="Seg R", cupo_maximo=100)
        hoy = date.today()
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

    def test_el_script_no_concatena_el_nombre_crudo_en_el_html(self):
        script = script_con(self._html(), "data-reactivar-url")
        self.assertNotRegex(script, r"\+\s*nombre\s*\+")  # el valor crudo de dataset
        self.assertIn("'&lt;'", script)

    @requiere_node
    def test_el_html_del_popup_muestra_el_nombre_como_texto(self):
        script = script_con(self._html(), "data-reactivar-url")

        log = correr_script(script, f"__click({{reactivarUrl: '/r/1/', nombre: {json.dumps(NOMBRE_CON_MARCADO)}}});")

        (popup,) = log["swal"]
        self.assertNotIn("<img", popup["html"])
        self.assertIn("&lt;img src=x onerror=&quot;window.__inyectado=1&quot;&gt;", popup["html"])
        self.assertIn("Está vencida. Elegí la nueva fecha de fin para reactivarla.", popup["html"])
        self.assertEqual(popup["title"], "Reactivar convocatoria")
        self.assertEqual(popup["input"], "date")
