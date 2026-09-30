"""Detalle del caso de Becas: volver al origen, un aviso por acción y modales canónicos.

- TIT-9 / DE-3: el caso se abre desde varias pantallas y la flecha volvía siempre a los
  casos del relevamiento. Ahora respeta ``?next=``, pero solo si es una ruta interna de
  ``/becas/``: un ``next`` a otro host, a otro esquema o a otra parte del sistema se
  descarta y el volver cae en el destino de siempre.
- El origen viaja en los ``action`` de los POST del caso y en sus redirects, así que
  guardar algo no devuelve al usuario a una pantalla que no es la suya.
- ALR-16: «Aprobar» dejaba hasta tres avisos encimados; ahora sale uno, con el nivel del
  peor resultado.
- ALR-8: los errores del modal «Completar datos para SIIS» eran un aviso por campo.
- POP-10: los tres modales propios de la pantalla usan el markup canónico
  (``role="dialog"``, ``_modal_header`` / ``_modal_footer``) y becas-modal.js.
- DE-2: la pantalla va a ancho completo, sin máximo propio.
"""

from unittest.mock import patch
from urllib.parse import quote

from django.test import TestCase
from django.urls import reverse

from programas.models import EnvioSIIS, Formulario, ListaEspera, ValidacionSIS
from programas.tests.test_becas_revision import _BaseAprobacionTest, _BaseRevisionTest
from programas.views.revision import _aviso_unico, _next_valido


def _texto(html):
    return " ".join(html.split())


class VolverDelCasoTests(_BaseRevisionTest):
    """TIT-9 / DE-3. La flecha vuelve al origen, y solo si el origen es de /becas/."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.url = reverse("becas:formulario_detalle", args=[self.form_a.pk])
        self.casos_del_relevamiento = reverse("becas:revision_formularios", args=[self.rel_a.pk])

    def _contexto(self, next_=None):
        resp = self.client.get(self.url, {"next": next_} if next_ is not None else None)
        self.assertEqual(resp.status_code, 200)
        return resp

    def test_sin_next_vuelve_a_los_casos_del_relevamiento(self):
        resp = self._contexto()
        self.assertEqual(resp.context["volver_url"], self.casos_del_relevamiento)
        self.assertEqual(resp.context["volver_label"], "los casos del relevamiento")
        self.assertEqual(resp.context["next_qs"], "")

    def test_un_next_valido_se_respeta_y_se_anuncia(self):
        origen = reverse("becas:renaper_pendientes") + "?page=2"
        resp = self._contexto(origen)
        self.assertEqual(resp.context["volver_url"], origen)
        self.assertEqual(resp.context["volver_label"], "Pendientes de validación")
        self.assertEqual(resp.context["next_qs"], "?next=" + quote(origen, safe=""))
        html = resp.content.decode()
        self.assertIn('aria-label="Volver a Pendientes de validación"', html)
        self.assertIn(f'href="{origen.replace("?", "?")}"', html.replace("&amp;", "&"))

    def test_un_next_a_otro_host_se_descarta(self):
        for externo in (
            "https://malo.tld/becas/revision/",
            "//malo.tld/becas/revision/",
            r"/\malo.tld/becas/",
            "javascript:alert(1)",  # noqa: S105 — payload de prueba, no un secreto
        ):
            with self.subTest(externo=externo):
                resp = self._contexto(externo)
                self.assertEqual(resp.context["volver_url"], self.casos_del_relevamiento)
                self.assertEqual(resp.context["volver_label"], "los casos del relevamiento")
                self.assertEqual(resp.context["next_qs"], "")
                self.assertNotContains(resp, "malo.tld")

    def test_un_next_interno_fuera_de_becas_se_descarta(self):
        resp = self._contexto("/legajos/ciudadanos/")
        self.assertEqual(resp.context["volver_url"], self.casos_del_relevamiento)
        self.assertEqual(resp.context["next_qs"], "")

    def test_un_next_de_becas_que_no_enlaza_al_caso_se_descarta(self):
        """``/becas/reportes/`` es interno pero no es una pantalla de origen del caso."""
        resp = self._contexto(reverse("becas:reportes"))
        self.assertEqual(resp.context["volver_url"], self.casos_del_relevamiento)

    def test_las_migas_de_una_bandeja_arrancan_en_revision(self):
        resp = self._contexto(reverse("becas:renaper_pendientes"))
        labels = [m["label"] for m in resp.context["migas_origen"]]
        self.assertEqual(labels, ["Revisión", "Pendientes de validación", f"Caso {self.form_a.numero}"])
        self.assertIn("Pendientes de validación", _texto(resp.content.decode()))

    def test_sin_bandeja_las_migas_son_la_jerarquia_del_programa(self):
        resp = self._contexto()
        self.assertEqual(resp.context["migas_origen"], [])
        texto = _texto(resp.content.decode())
        # ``becas_migas relevamiento actual="Caso N"`` en la plantilla.
        self.assertIn("Programas", texto)
        self.assertIn(self.conv_a.nombre, texto)
        self.assertIn(f'aria-current="page" class="font-semibold text-body">Caso {self.form_a.numero}', texto)

    def test_el_origen_viaja_en_los_post_del_caso(self):
        origen = reverse("becas:revision")
        html = self._contexto(origen).content.decode()
        esperado = f"{reverse('becas:formulario_aprobar', args=[self.form_a.pk])}?next={quote(origen, safe='')}"
        self.assertIn(f'action="{esperado}"', html)

    def test_un_post_con_origen_redirige_conservandolo(self):
        origen = reverse("becas:revision")
        resp = self.client.post(
            self.url + "?next=" + quote(origen, safe=""),
            {"celular": "3624999999", "email_contacto": "a@b.com"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], self.url + "?next=" + quote(origen, safe=""))

    def test_un_post_con_origen_externo_redirige_sin_el(self):
        resp = self.client.post(
            self.url + "?next=" + quote("https://malo.tld/x", safe=""),
            {"celular": "3624999999", "email_contacto": "a@b.com"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], self.url)

    def test_el_ancho_ya_no_tiene_maximo_propio(self):
        self.assertNotContains(self._contexto(), "max-w-[1180px]")


class NextValidoTests(TestCase):
    """La validación de ``next``, sin pasar por la pantalla."""

    class _Req:
        def __init__(self, valor):
            self.GET = {"next": valor} if valor is not None else {}

        def get_host(self):
            return "testserver"

        def is_secure(self):
            return False

    def test_acepta_solo_rutas_internas_de_becas(self):
        casos = {
            "/becas/revision/": "/becas/revision/",
            "/becas/revision/?estado=ENVIADO": "/becas/revision/?estado=ENVIADO",
            "": "",
            None: "",
            "/legajos/": "",
            "//malo.tld/becas/": "",
            "https://malo.tld/becas/": "",
            "http://testserver/becas/revision/": "",  # absoluta: el prefijo exige ruta
            "javascript:alert(1)": "",  # noqa: S105 — payload de prueba
        }
        for valor, esperado in casos.items():
            with self.subTest(valor=valor):
                self.assertEqual(_next_valido(self._Req(valor)), esperado)


class UnAvisoPorAccionTests(_BaseAprobacionTest):
    """ALR-16: aprobar deja un solo mensaje, con el nivel del peor resultado."""

    def setUp(self):
        super().setUp()
        self.url = reverse("becas:formulario_aprobar", args=[self.form_a.pk])

    def _mensajes(self, resp):
        return [(m.level_tag, str(m)) for m in resp.context["messages"]]

    @patch("programas.views.revision.enviar_beneficiario_a_siis")
    def test_aprobar_con_todo_bien_deja_un_solo_aviso(self, enviar):
        enviar.return_value = EnvioSIIS.objects.create(
            formulario=self.form_a, estado=EnvioSIIS.Estado.ENVIADO, siis_id=99
        )

        resp = self.client.post(self.url, follow=True)

        mensajes = self._mensajes(resp)
        self.assertEqual(len(mensajes), 1, mensajes)
        nivel, texto = mensajes[0]
        self.assertEqual(nivel, "success")
        self.assertIn("Caso aprobado.", texto)
        self.assertIn("Informado a SIIS (ID 99).", texto)

    @patch("programas.views.revision.enviar_beneficiario_a_siis")
    def test_el_peor_resultado_manda_el_nivel(self, enviar):
        """Aprobado + SIIS que no valida + alta que se cae: un aviso, y es error."""
        enviar.side_effect = RuntimeError("SIIS caído")
        self.validacion.estado = ValidacionSIS.Estado.RECHAZADO
        self.validacion.motivo = "No alcanza la edad mínima."
        self.validacion.save(update_fields=["estado", "motivo"])
        self.validar_compatibilidad.return_value = {
            "success": True,
            "compatible": False,
            "motivo": "No alcanza la edad mínima.",
            "data": {"id_programa": 41, "validaciones": {}},
        }

        resp = self.client.post(self.url, follow=True)

        mensajes = self._mensajes(resp)
        self.assertEqual(len(mensajes), 1, mensajes)
        nivel, texto = mensajes[0]
        self.assertEqual(nivel, "error")
        self.assertIn("Caso aprobado.", texto)
        self.assertIn("no es compatible", texto)
        self.assertIn("No se pudo informar el beneficiario a SIIS", texto)

    def test_sin_cupo_tambien_es_un_solo_aviso(self):
        self.seg_a.cupo_maximo = 1
        self.seg_a.save(update_fields=["cupo_maximo"])
        Formulario.objects.create(
            relevamiento=self.rel_a,
            celular="3624300300",
            email_contacto="ocupa@b.com",
            estado=Formulario.Estado.APROBADO,
        )

        resp = self.client.post(self.url, follow=True)

        mensajes = self._mensajes(resp)
        self.assertEqual(len(mensajes), 1, mensajes)
        nivel, texto = mensajes[0]
        self.assertEqual(nivel, "warning")
        self.assertIn("se agregó a la lista de espera", texto)
        self.assertTrue(ListaEspera.objects.filter(formulario=self.form_a, promovido=False).exists())

    def test_el_aviso_unico_usa_el_peor_nivel_y_junta_los_textos(self):
        class _Req:
            pass

        with patch("programas.views.revision.messages") as messages:
            _aviso_unico(_Req(), [("success", "Uno."), ("", ""), ("warning", "Dos."), (None, None)])

        messages.warning.assert_called_once()
        self.assertEqual(messages.warning.call_args.args[1], "Uno. Dos.")


class ErroresDeDatosSiisTests(_BaseAprobacionTest):
    """ALR-8: un resumen, no un aviso flotante por campo."""

    def setUp(self):
        super().setUp()
        self.form_a.estado = Formulario.Estado.APROBADO
        self.form_a.save(update_fields=["estado"])
        self.url = reverse("becas:formulario_datos_siis", args=[self.form_a.pk])

    def test_los_errores_salen_en_un_solo_aviso(self):
        resp = self.client.post(self.url, {"cuit": "no-es-un-cuit", "id_plan_soc": "tampoco"}, follow=True)

        mensajes = [str(m) for m in resp.context["messages"]]
        self.assertEqual(len(mensajes), 1, mensajes)
        self.assertIn("No se guardaron los datos para SIIS. Revisá:", mensajes[0])


class ModalesDelCasoTests(_BaseRevisionTest):
    """POP-10: markup canónico y comportamiento accesible compartido."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def _html(self):
        return self.client.get(reverse("becas:formulario_detalle", args=[self.form_a.pk])).content.decode()

    def test_los_modales_propios_son_dialogos_nombrados(self):
        html = self._html()
        for overlay, titulo_id in (
            ("modal-rechazo-overlay", "modal-rechazo-title"),
            ("modal-forzar-overlay", "modal-forzar-title"),
        ):
            with self.subTest(overlay=overlay):
                self.assertIn(f'id="{overlay}"', html)
                self.assertIn(f'aria-labelledby="{titulo_id}"', html)
                self.assertIn(f'id="{titulo_id}"', html)
        # Los dos son diálogos modales con el alto máximo y el cuerpo scrolleable
        # del canon (el tercer role="dialog" de la página es el visor de imágenes,
        # que no es un modal de Becas).
        self.assertEqual(html.count('role="dialog" aria-modal="true"'), 3)
        self.assertEqual(html.count("max-h-[90vh] flex flex-col"), 2)
        self.assertEqual(html.count("overflow-y-auto min-h-0"), 2)

    def test_los_modales_traen_el_pie_y_la_cruz_canonicos(self):
        html = self._html()
        # `_modal_header` / `_modal_footer`: la X y el «Cancelar» los cierra becas-modal.js.
        self.assertGreaterEqual(html.count("data-becas-modal-cerrar"), 4)
        self.assertIn("Rechazar caso</button>", html)
        self.assertIn("Validar manualmente</button>", html)
        self.assertIn('form="form-rechazar"', html)
        self.assertNotIn("modal-rechazo-confirmar", html)
        self.assertNotIn("modal-forzar-cancelar", html)

    def test_se_carga_el_helper_de_modales(self):
        self.assertIn("custom/js/becas-modal.js", self._html())

    def test_un_caso_ya_resuelto_no_trae_el_modal_de_rechazo(self):
        """El modal está bajo la misma condición que #form-rechazar: sin el form no
        habría a quién apuntar con `form=`."""
        self.form_a.estado = Formulario.Estado.APROBADO
        self.form_a.save(update_fields=["estado"])

        html = self._html()

        # El id sigue nombrado en el JS de la pantalla: lo que no está es el markup.
        self.assertNotIn('id="modal-rechazo-overlay"', html)
        self.assertNotIn('id="form-rechazar"', html)


class EsperaEnLaBandejaTests(_BaseRevisionTest):
    """La bandeja del relevamiento deja lista la marca «Lista de espera» del estado."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_la_pagina_trae_en_espera_activa_sin_una_consulta_por_fila(self):
        ListaEspera.objects.create(formulario=self.form_a, segmento=self.seg_a, posicion=1)
        otro = Formulario.objects.create(relevamiento=self.rel_a, celular="3624700700", email_contacto="otro@b.com")

        resp = self.client.get(reverse("becas:revision_formularios", args=[self.rel_a.pk]))

        marcas = {f.pk: f.en_espera_activa for f in resp.context["formularios"]}
        self.assertEqual(marcas, {self.form_a.pk: True, otro.pk: False})

    def test_una_entrada_promovida_no_cuenta(self):
        ListaEspera.objects.create(formulario=self.form_a, segmento=self.seg_a, posicion=1, promovido=True)

        resp = self.client.get(reverse("becas:revision_formularios", args=[self.rel_a.pk]))

        marcas = {f.pk: f.en_espera_activa for f in resp.context["formularios"]}
        self.assertFalse(marcas[self.form_a.pk])
