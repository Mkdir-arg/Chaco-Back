"""Modales del Equipo como pieza reutilizable (Cambio 564): ``legajo/_equipo_modales.html``.

1. La ficha sigue dibujando los cuatro títulos y sus botones, según el modal que abre la URL.
2. El contexto sale de funciones que cualquier vista puede llamar (``contexto_modal_*``).
3. El POST vuelve a la solapa Equipo, o al ``next`` si es de este sitio (nunca a un sitio ajeno).
"""

from django.urls import reverse

from programas.mixins_dispositivos_equipo import contexto_modal_alcance, contexto_modal_sumar_persona
from programas.models import MiembroEquipoDispositivo
from programas.tests.test_dispositivos_equipo_crear_persona_420 import AJAX
from programas.tests.test_equipo_selector_alcance import BaseSelector


class MarkupDeLosModalesTests(BaseSelector):
    def test_sumar_persona_dibuja_el_modal_de_sumar_y_el_de_crear(self):
        self._entrar(self.admin_programa)
        respuesta = self.client.get(self.url_sumar)

        self.assertTemplateUsed(respuesta, "programas/dispositivos/legajo/_equipo_modales.html")
        for texto in (
            "Sumar persona al Equipo",
            "Sumar al Equipo",
            "Crear persona",
            "Crear y sumar al Equipo",
            'x-becas-modal="modalEquipo"',
            'x-becas-modal="modalCrearPersona"',
            "modalEquipo=false; modalCrearPersona=true",
            "modal-equipo-titulo",
            "modal-crear-persona-titulo",
        ):
            self.assertContains(respuesta, texto)
        self.assertIsNone(respuesta.context["edificio_fijo"])
        self.assertNotContains(respuesta, 'name="next"')

    def test_agregar_persona_al_edificio_cambia_el_titulo_y_fija_el_edificio(self):
        self._entrar(self.admin_programa)
        respuesta = self.client.get(f"{self.url_detalle}?agregar_persona={self.ed1.pk}")

        self.assertContains(respuesta, "Agregar persona al edificio")
        self.assertContains(respuesta, "Crear y sumar al Equipo")
        self.assertNotContains(respuesta, "Sumar persona al Equipo")
        self.assertEqual(respuesta.context["edificio_fijo"], self.ed1)
        self.assertContains(respuesta, 'name="edificio_fijo"')

    def test_cambiar_alcance_dibuja_su_modal(self):
        fila = self._miembro(self.disp_a, self.ana, self.rol_ver)
        self._entrar(self.admin_programa)
        respuesta = self.client.get(f"{self.url_detalle}?tab=equipo&equipo=alcance&miembro={fila.pk}")

        for texto in ("Cambiar alcance", "Guardar alcance", 'x-becas-modal="modalAlcance"', "modal-alcance-titulo"):
            self.assertContains(respuesta, texto)
        self.assertNotContains(respuesta, "Sumar persona al Equipo")

    def test_sin_modal_abierto_no_hay_ninguno(self):
        self._entrar(self.admin_programa)
        respuesta = self.client.get(self.url_detalle + "?tab=equipo")

        for texto in ("modal-equipo-titulo", "modal-alcance-titulo", "modal-crear-persona-titulo"):
            self.assertNotContains(respuesta, texto)

    def test_el_responsable_comun_ve_el_pedido_al_administrador_y_no_el_boton_de_crear(self):
        self._entrar(self.responsable)
        respuesta = self.client.get(self.url_sumar)

        self.assertContains(respuesta, "Sumar persona al Equipo")
        self.assertNotContains(respuesta, "Crear y sumar al Equipo")
        self.assertIn("mensaje_pedir_alta", respuesta.context)


class ContextoReutilizableTests(BaseSelector):
    def test_el_contexto_de_sumar_no_necesita_una_vista(self):
        contexto = contexto_modal_sumar_persona(self.disp_a, self._fresco(self.admin_programa))

        self.assertTrue(contexto["puede_crear_persona"])
        self.assertIsNone(contexto["edificio_fijo"])
        self.assertIn("form_equipo", contexto)
        self.assertIn("form_crear_persona", contexto)
        self.assertEqual(contexto["url_equipo_sumar"], reverse("dispositivos:equipo_sumar", args=[self.disp_a.pk]))

    def test_con_edificio_fijo_viaja_en_los_formularios(self):
        contexto = contexto_modal_sumar_persona(self.disp_a, self._fresco(self.admin_programa), self.ed1)

        self.assertEqual(contexto["edificio_fijo"], self.ed1)
        self.assertEqual(contexto["form_equipo"].initial["edificio_fijo"], self.ed1.pk)
        self.assertEqual(contexto["form_crear_persona"].initial["edificio_fijo"], self.ed1.pk)

    def test_el_contexto_de_alcance_trae_la_fila_el_form_y_la_url(self):
        fila = self._miembro(self.disp_a, self.ana, self.rol_ver)
        contexto = contexto_modal_alcance(self.disp_a, self._fresco(self.admin_programa), fila)

        self.assertEqual(contexto["miembro_alcance"], fila)
        self.assertIn("form_alcance", contexto)
        self.assertEqual(
            contexto["url_equipo_alcance"], reverse("dispositivos:equipo_alcance", args=[self.disp_a.pk, fila.pk])
        )


class VueltaDelPostTests(BaseSelector):
    def _post(self, **extra):
        self._entrar(self.admin_programa)
        datos = {"persona_rol": f"{self.ana.pk}:{self.rol_admitir.pk}", "tipo_contratacion": "BECADO", **extra}
        return self.client.post(self.url_sumar_post, datos, headers=AJAX)

    def test_por_defecto_vuelve_a_la_solapa_equipo(self):
        respuesta = self._post()

        self.assertEqual(respuesta.json()["redirect"], self.url_detalle + "?tab=equipo")

    def test_un_next_de_este_sitio_se_respeta(self):
        destino = reverse("dispositivos:detalle", args=[self.disp_b.pk]) + "?tab=equipo"
        respuesta = self._post(next=destino)

        self.assertEqual(respuesta.json()["redirect"], destino)
        self.assertTrue(MiembroEquipoDispositivo.objects.filter(usuario=self.ana, dispositivo=self.disp_a).exists())

    def test_un_next_de_otro_sitio_se_ignora(self):
        for ajeno in ("https://evil.example.com/x", "//evil.example.com/x", "javascript:alert(1)"):
            with self.subTest(ajeno=ajeno):
                MiembroEquipoDispositivo.objects.filter(usuario=self.ana).delete()
                respuesta = self._post(next=ajeno)

                self.assertEqual(respuesta.json()["redirect"], self.url_detalle + "?tab=equipo")

    def test_el_next_del_contexto_viaja_en_los_tres_formularios(self):
        from django.template.loader import render_to_string

        contexto = contexto_modal_sumar_persona(self.disp_a, self._fresco(self.admin_programa))
        contexto.update(
            contexto_modal_alcance(
                self.disp_a, self._fresco(self.admin_programa), self._miembro(self.disp_a, self.ana, self.rol_ver)
            )
        )
        html = render_to_string(
            "programas/dispositivos/legajo/_equipo_modales.html", {**contexto, "next_url": "/vuelta/"}
        )

        self.assertEqual(html.count('<input type="hidden" name="next" value="/vuelta/">'), 3)
