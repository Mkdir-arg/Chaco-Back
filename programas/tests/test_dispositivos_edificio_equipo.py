"""Solapa «Equipo» de la página del edificio y proceso «Sumar persona» (Cambio 569, PR 4 del lote «el edificio como unidad operativa»).

1. Quién aparece: toda la institución y este edificio. Quien opera solo otro edificio de la institución, o es de otra
   institución del mismo predio, no aparece.
2. «Sumar persona» abre «Agregar persona al edificio» con ESTE edificio fijo; el POST no acepta uno ajeno.
3. Cada acción (sumar, cambiar alcance, baja, responsable) solo con la capacidad que la gobierna, y vuelve a la solapa.
4. El resultado: la fila aparece y el aviso (toast) lleva el texto del diseño.
5. El costo no crece con la cantidad de miembros.
6. ``destino_seguro``: el único validador de ``next``.
"""

import json
import re

from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection
from django.test import RequestFactory, SimpleTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from programas.models import MiembroEquipoDispositivo
from programas.services.dispositivos import miembros_del_edificio
from programas.tests.test_dispositivos_equipo_crear_persona_420 import AJAX
from programas.tests.test_equipo_selector_alcance import BaseSelector
from programas.views.ajax_utils import con_parametro, destino_seguro

Alcance = MiembroEquipoDispositivo.Alcance
PRESUPUESTOS = settings.BASE_DIR / "scripts" / "perf_budgets.json"
CLAVE_PRESUPUESTO = "dispositivos_edificio_operativo_equipo"


class BaseEquipoEdificio(BaseSelector):
    def setUp(self):
        super().setUp()
        self.url = reverse("dispositivos:edificio_operativo", args=[self.disp_a.pk, self.ed1.pk])
        self.url_equipo = f"{self.url}?tab=equipo"
        # Gente con nombre y apellido para distinguirla en la tabla.
        self.en_inst = self._persona("ines", "Ines", "Quiroga", Alcance.INSTITUCION)
        self.en_ed1 = self._persona("elsa", "Elsa", "Duarte", Alcance.EDIFICIOS, [self.ed1])
        self.en_ed2 = self._persona("eva", "Eva", "Navarro", Alcance.EDIFICIOS, [self.ed2])
        self.en_ambos = self._persona("ema", "Ema", "Paz", Alcance.EDIFICIOS, [self.ed1, self.ed2])

    def _persona(self, username, nombre, apellido, alcance, edificios=()):
        usuario = self._usuario(username, self.rol_ver)
        User.objects.filter(pk=usuario.pk).update(first_name=nombre, last_name=apellido)
        fila = self._miembro(self.disp_a, usuario, self.rol_ver)
        fila.alcance = alcance
        fila.save(update_fields=["alcance"])
        fila.edificios.set(edificios)
        return usuario

    def _entrar(self, usuario=None):
        super()._entrar(usuario or self.admin_programa)

    def _get(self, usuario=None, **params):
        self._entrar(usuario)
        return self.client.get(self.url, params)

    def _filas(self, respuesta):
        return [m.persona for m in respuesta.context["equipo"]]


class QuienApareceTests(BaseEquipoEdificio):
    def test_aparecen_toda_la_institucion_y_este_edificio(self):
        filas = self._filas(self._get(tab="equipo"))

        for apellido in ("Quiroga", "Duarte", "Paz"):
            self.assertTrue(any(apellido in fila for fila in filas), f"{apellido} debería estar")

    def test_quien_opera_solo_otro_edificio_de_la_institucion_no_aparece(self):
        respuesta = self._get(tab="equipo")

        self.assertFalse(any("Navarro" in fila for fila in self._filas(respuesta)))
        self.assertNotContains(respuesta, "Navarro")

    def test_alguien_de_otra_institucion_del_mismo_predio_no_aparece(self):
        self.ed1.dispositivos.add(self.disp_b)
        ajeno = self._usuario("ajeno", self.rol_ver)
        User.objects.filter(pk=ajeno.pk).update(first_name="Ana", last_name="Ajenez")
        self._miembro(self.disp_b, ajeno, self.rol_ver)

        respuesta = self._get(tab="equipo")

        self.assertNotContains(respuesta, "Ajenez")
        self.assertFalse(any("Ajenez" in fila for fila in self._filas(respuesta)))

    def test_el_alcance_dice_este_edificio_solo_si_es_el_unico(self):
        por_persona = {m.usuario_id: m.alcance_texto for m in self._get(tab="equipo").context["equipo"]}

        self.assertEqual(por_persona[self.en_ed1.pk], "Este edificio")
        self.assertEqual(por_persona[self.en_inst.pk], "Toda la institución")
        self.assertIn(self.ed1.nombre, por_persona[self.en_ambos.pk])
        self.assertIn(self.ed2.nombre, por_persona[self.en_ambos.pk])

    def test_los_rotulos_son_los_del_modelo(self):
        MiembroEquipoDispositivo.objects.filter(usuario=self.en_ed1).update(tipo_contratacion="BECADO")
        respuesta = self._get(tab="equipo")

        self.assertContains(
            respuesta, MiembroEquipoDispositivo(tipo_contratacion="BECADO").get_tipo_contratacion_display()
        )
        for rotulo in ("Persona", "Rol", "Contratación", "Alcance", "Responsable"):
            self.assertContains(respuesta, f">{rotulo}</th>")

    def test_el_contador_de_la_solapa_cuenta_las_mismas_filas(self):
        respuesta = self._get(tab="equipo")

        self.assertEqual(respuesta.context["contadores"]["equipo"], len(respuesta.context["equipo"]))


class SumarPersonaTests(BaseEquipoEdificio):
    def test_el_boton_abre_el_modal_con_este_edificio_fijo(self):
        respuesta = self._get(tab="equipo")

        self.assertContains(respuesta, "Sumar persona")
        self.assertContains(respuesta, f"{self.url}?tab=equipo&amp;equipo=sumar")
        abierto = self._get(tab="equipo", equipo="sumar")
        self.assertEqual(abierto.context["edificio_fijo"], self.ed1)
        self.assertContains(abierto, "Agregar persona al edificio")
        self.assertContains(abierto, "Sumar al Equipo")
        self.assertContains(abierto, "Crear persona")
        self.assertContains(abierto, "Crear y sumar al Equipo")
        self.assertContains(abierto, f'name="edificio_fijo" value="{self.ed1.pk}"')
        # Los dos POST (sumar y crear) vuelven a esta solapa.
        self.assertContains(abierto, f'name="next" value="{self.url_equipo}"', count=2)

    def test_sin_modal_pedido_no_se_arma_ninguno(self):
        respuesta = self._get(tab="equipo")

        for texto in ("modal-equipo-titulo", "modal-alcance-titulo", "modal-crear-persona-titulo"):
            self.assertNotContains(respuesta, texto)

    def test_sumar_fija_este_edificio_y_la_fila_aparece_con_el_aviso_del_diseno(self):
        self._entrar()
        # El POST que arma el modal: la persona y el rol del buscador, el edificio fijo y el `next` de la solapa.
        respuesta = self.client.post(
            self.url_sumar_post,
            {
                "persona_rol": f"{self.ana.pk}:{self.rol_admitir.pk}",
                "tipo_contratacion": "BECADO",
                "edificio_fijo": self.ed1.pk,
                "next": self.url_equipo,
            },
            headers=AJAX,
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json()["redirect"], f"{self.url_equipo}&nuevo={self._fila_de_ana().pk}")

        fila = self._fila_de_ana()
        self.assertEqual((fila.alcance, self._ids(fila)), (Alcance.EDIFICIOS, {self.ed1.pk}))
        pagina = self.client.get(self.url_equipo)
        self.assertContains(pagina, "Gomez")
        self.assertContains(pagina, f"Ana Gomez se sumó al Equipo de {self.ed1.nombre} como {self.rol_admitir.name}.")

    def test_la_fila_recien_sumada_sale_resaltada_y_las_demas_no(self):
        self._entrar()
        respuesta = self.client.post(
            self.url_sumar_post,
            {
                "persona_rol": f"{self.ana.pk}:{self.rol_admitir.pk}",
                "tipo_contratacion": "BECADO",
                "edificio_fijo": self.ed1.pk,
                "next": self.url_equipo,
            },
            headers=AJAX,
        )
        nueva = self._fila_de_ana()
        self.assertEqual(respuesta.json()["redirect"], f"{self.url_equipo}&nuevo={nueva.pk}")

        pagina = self.client.get(respuesta.json()["redirect"])

        self.assertEqual(pagina.context["miembro_nuevo"], nueva.pk)
        resaltada = 'class="hover:bg-secondary transition bg-success-soft"'
        self.assertContains(pagina, resaltada, count=1)
        self.assertNotContains(self.client.get(self.url_equipo), resaltada)

    def test_si_ya_alcanzaba_no_se_resalta_nada(self):
        self._entrar()
        datos = {
            "persona_rol": f"{self.ana.pk}:{self.rol_admitir.pk}",
            "tipo_contratacion": "BECADO",
            "edificio_fijo": self.ed1.pk,
            "next": self.url_equipo,
        }
        self.client.post(self.url_sumar_post, datos, headers=AJAX)
        otra_vez = self.client.post(self.url_sumar_post, datos, headers=AJAX)

        self.assertEqual(otra_vez.json()["redirect"], self.url_equipo)

    def test_crear_persona_en_el_edificio_avisa_con_el_texto_de_sumar_y_conserva_las_credenciales(self):
        self._entrar()
        respuesta = self.client.post(
            self.url_crear, self._datos(edificio_fijo=self.ed1.pk, next=self.url_equipo), headers=AJAX
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.content)

        pagina = self.client.get(respuesta.json()["redirect"])

        self.assertContains(
            pagina, f"Lucía Ferreyra se sumó al Equipo de {self.ed1.nombre} como {self.rol_admitir.name}."
        )
        self.assertContains(pagina, "correo")

    def test_el_modal_nombra_el_edificio_con_su_codigo_y_pide_la_persona(self):
        abierto = self._get(tab="equipo", equipo="sumar")

        self.assertContains(abierto, f"{self.ed1.nombre} ({self.ed1.codigo})")
        self.assertTrue(abierto.context["form_equipo"].fields["persona"].marca_requerido)

    def test_un_edificio_de_otra_institucion_no_se_acepta_por_post(self):
        self._entrar()
        respuesta = self.client.post(
            self.url_sumar_post,
            {
                "persona_rol": f"{self.ana.pk}:{self.rol_admitir.pk}",
                "tipo_contratacion": "BECADO",
                "edificio_fijo": self.ed_ajeno.pk,
                "next": self.url_equipo,
            },
            headers=AJAX,
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(MiembroEquipoDispositivo.objects.filter(usuario=self.ana).exists())

    def test_crear_persona_desde_el_edificio_la_deja_en_este_edificio(self):
        self._entrar()
        respuesta = self.client.post(
            self.url_crear, self._datos(edificio_fijo=self.ed1.pk, next=self.url_equipo), headers=AJAX
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json()["redirect"], self.url_equipo)
        fila = MiembroEquipoDispositivo.objects.get(usuario=User.objects.get(email="lucia@example.com"))
        self.assertEqual((fila.alcance, self._ids(fila)), (Alcance.EDIFICIOS, {self.ed1.pk}))

    def test_quien_no_gestiona_el_equipo_no_ve_el_boton_ni_las_acciones(self):
        simple = self._persona("simple", "Sara", "Simple", Alcance.INSTITUCION)
        respuesta = self._get(simple, tab="equipo", equipo="sumar")

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "Sumar persona")
        self.assertNotContains(respuesta, "Dar de baja")
        self.assertNotContains(respuesta, "modal-equipo-titulo")
        self.assertContains(respuesta, "Quiroga")

    def test_un_dispositivo_cerrado_no_ofrece_sumar(self):
        self.disp_a.estado = self.disp_a.Estado.CERRADO
        self.disp_a.save(update_fields=["estado"])
        respuesta = self._get(tab="equipo", equipo="sumar")

        self.assertNotContains(respuesta, "modal-equipo-titulo")
        self.assertFalse(respuesta.context["puede_sumar_persona"])

    def test_el_responsable_de_otro_edificio_no_puede_sumar_en_este(self):
        # Responsable con alcance Edificios {ED-2}: no ve ED-1 (404), así que tampoco suma ahí.
        resp_ed2 = self._usuario("resp_ed2", self.rol_ver)
        fila = self._miembro(self.disp_a, resp_ed2, self.rol_ver, responsable=True)
        fila.alcance = Alcance.EDIFICIOS
        fila.save(update_fields=["alcance"])
        fila.edificios.set([self.ed2])

        self.assertEqual(self._get(resp_ed2).status_code, 404)

    def test_el_responsable_de_este_edificio_suma_y_solo_aca(self):
        respuesta = self._get(self.resp_ed, tab="equipo", equipo="sumar")

        self.assertEqual(respuesta.context["edificio_fijo"], self.ed1)
        self.assertContains(respuesta, "Agregar persona al edificio")


class AccionesDeFilaTests(BaseEquipoEdificio):
    def _fila(self, usuario):
        return MiembroEquipoDispositivo.objects.get(dispositivo=self.disp_a, usuario=usuario)

    def test_las_acciones_con_confirmacion_vuelven_a_esta_solapa(self):
        fila = self._fila(self.en_ed1)
        respuesta = self._get(tab="equipo")

        baja = reverse("dispositivos:equipo_baja", args=[self.disp_a.pk, fila.pk])
        responsable = reverse("dispositivos:equipo_responsable", args=[self.disp_a.pk, fila.pk])
        for ruta in (baja, responsable):
            self.assertContains(respuesta, f'data-confirm-url="{ruta}?next=', html=False)
        for texto in ("Cambiar alcance", "Marcar como responsable", "Dar de baja"):
            self.assertContains(respuesta, texto)

        self._entrar()
        enviado = self.client.post(f"{baja}?next={self.url_equipo.replace('?', '%3F').replace('=', '%3D')}")
        self.assertRedirects(enviado, self.url_equipo, fetch_redirect_response=False)
        self.assertFalse(self._fila(self.en_ed1).activo)

    def test_marcar_responsable_vuelve_al_edificio(self):
        fila = self._fila(self.en_ed1)
        self._entrar()
        url = reverse("dispositivos:equipo_responsable", args=[self.disp_a.pk, fila.pk])

        enviado = self.client.post(url, {"next": self.url_equipo})

        self.assertRedirects(enviado, self.url_equipo, fetch_redirect_response=False)
        self.assertTrue(self._fila(self.en_ed1).es_responsable)

    def test_un_next_ajeno_vuelve_a_la_ficha_de_siempre(self):
        fila = self._fila(self.en_ed1)
        self._entrar()
        url = reverse("dispositivos:equipo_responsable", args=[self.disp_a.pk, fila.pk])

        enviado = self.client.post(f"{url}?next=https://malo.example/x")

        self.assertRedirects(
            enviado,
            f"{reverse('dispositivos:detalle', args=[self.disp_a.pk])}?tab=equipo",
            fetch_redirect_response=False,
        )

    def test_cambiar_alcance_abre_su_modal_por_url_y_vuelve_al_edificio(self):
        fila = self._fila(self.en_inst)
        abierto = self._get(tab="equipo", equipo="alcance", miembro=fila.pk)

        self.assertContains(abierto, "Guardar alcance")
        self.assertContains(abierto, f'name="next" value="{self.url_equipo}"')
        self.assertEqual(abierto.context["miembro_alcance"], fila)

    def test_un_miembro_que_no_es_de_este_edificio_no_abre_su_modal(self):
        fila = self._fila(self.en_ed2)
        abierto = self._get(tab="equipo", equipo="alcance", miembro=fila.pk)

        self.assertNotContains(abierto, "modal-alcance-titulo")

    def test_el_responsable_acotado_ve_deshabilitado_el_alcance_de_toda_la_institucion(self):
        respuesta = self._get(self.resp_ed, tab="equipo")

        self.assertContains(respuesta, "Solo en tus propios edificios")


class SoloConSuSolapaTests(BaseEquipoEdificio):
    def test_con_otra_solapa_no_se_arma_el_panel_y_el_boton_navega(self):
        respuesta = self._get(tab="estadias")

        self.assertFalse(respuesta.context["equipo_cargado"])
        self.assertNotIn("permisos_equipo", respuesta.context)
        for texto in ("Sumar persona", "Dar de baja", "Quiroga"):
            self.assertNotContains(respuesta, texto)
        self.assertContains(respuesta, "window.location.href=")
        self.assertEqual(respuesta.context["url_solapa_equipo"], self.url_equipo)
        self.assertContains(respuesta, 'id="tab-equipo" aria-controls="panel-equipo" data-solapa-navega')

    def test_el_contador_y_la_franja_siguen_con_cualquier_solapa(self):
        respuesta = self._get(tab="estadias")

        self.assertEqual(
            respuesta.context["contadores"]["equipo"], len(miembros_del_edificio(self.disp_a, self.ed1.pk))
        )
        self.assertGreater(respuesta.context["contadores"]["equipo"], 0)
        self.assertTrue(respuesta.context["equipo_en_turno"]["nombres"])
        self.assertContains(respuesta, "Equipo en turno")

    def test_un_modal_pedido_con_otra_solapa_no_se_abre(self):
        respuesta = self._get(tab="estadias", equipo="sumar")

        self.assertNotContains(respuesta, "modal-equipo-titulo")

    def test_con_su_solapa_abierta_el_panel_va_armado_y_el_boton_no_navega(self):
        respuesta = self._get(tab="equipo")

        self.assertTrue(respuesta.context["equipo_cargado"])
        boton = re.search(r'<button[^>]*id="tab-equipo"[^>]*>', respuesta.content.decode())
        self.assertIsNotNone(boton)
        self.assertNotIn("data-solapa-navega", boton.group(0))


class PresupuestoDelEquipoTests(BaseEquipoEdificio):
    def _medir(self, url):
        self._entrar()
        self.client.get(url)  # calienta sesión y caché
        with CaptureQueriesContext(connection) as consultas:
            self.assertEqual(self.client.get(url).status_code, 200)
        return len(consultas)

    def test_la_solapa_no_cuesta_mas_con_mas_miembros_y_entra_en_su_techo(self):
        antes = self._medir(self.url_equipo)
        for numero in range(8):
            self._persona(f"mas{numero}", f"Mas{numero}", "Gente", Alcance.EDIFICIOS, [self.ed1, self.ed2])
        despues = self._medir(self.url_equipo)

        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]
        self.assertEqual(antes, despues)
        self.assertLessEqual(despues, techo["consultas_fijas"])

    def test_la_pagina_con_otra_solapa_no_paga_lo_del_panel(self):
        # El techo de la página (`dispositivos_edificio_operativo`) no incluye lo propio del Equipo.
        con_otra = self._medir(f"{self.url}?tab=historial")
        con_equipo = self._medir(self.url_equipo)

        self.assertLess(con_otra, con_equipo)


class ConParametroTests(SimpleTestCase):
    def test_agrega_y_reemplaza_sin_tocar_el_resto(self):
        self.assertEqual(con_parametro("/a/?tab=equipo", "nuevo", 7), "/a/?tab=equipo&nuevo=7")
        self.assertEqual(con_parametro("/a/?nuevo=1&tab=equipo", "nuevo", 7), "/a/?tab=equipo&nuevo=7")
        self.assertEqual(con_parametro("/a/", "nuevo", 7), "/a/?nuevo=7")


class DestinoSeguroTests(SimpleTestCase):
    def _pedido(self, metodo="post", **datos):
        fabrica = RequestFactory()
        return getattr(fabrica, metodo)("/x/", datos)

    def test_un_next_propio_se_respeta(self):
        self.assertEqual(destino_seguro(self._pedido(next="/a/b/?c=1"), "/def/"), "/a/b/?c=1")

    def test_sin_next_o_ajeno_vuelve_al_defecto(self):
        self.assertEqual(destino_seguro(self._pedido(), "/def/"), "/def/")
        for malo in ("https://malo.example/x", "//malo.example/x", "javascript:alert(1)"):
            with self.subTest(malo=malo):
                self.assertEqual(destino_seguro(self._pedido(next=malo), "/def/"), "/def/")

    def test_por_defecto_lee_solo_el_post(self):
        pedido = RequestFactory().post("/x/?next=/a/", {})

        self.assertEqual(destino_seguro(pedido, "/def/"), "/def/")
        self.assertEqual(destino_seguro(pedido, "/def/", desde=("POST", "GET")), "/a/")

    def test_el_post_gana_sobre_la_url(self):
        pedido = RequestFactory().post("/x/?next=/de-la-url/", {"next": "/del-form/"})

        self.assertEqual(destino_seguro(pedido, "/def/", desde=("POST", "GET")), "/del-form/")

    def test_el_prefijo_acota_la_ruta(self):
        pedido = self._pedido("get", next="/portal/x/")

        self.assertEqual(destino_seguro(pedido, "", desde=("GET",), prefijo="/becas/"), "")
        pedido = self._pedido("get", next="/becas/x/")
        self.assertEqual(destino_seguro(pedido, "", desde=("GET",), prefijo="/becas/"), "/becas/x/")
