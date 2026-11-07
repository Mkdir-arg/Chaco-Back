"""UI del Equipo de un dispositivo y responsables obligatorios en el alta (Cambio 411).

Cada guarda de la vista se verificó con mutación (romperla deja rojo el test que la cubre):

1. Cada POST del Equipo exige ``puede_gestionar_equipo`` (403) antes de mirar nada más.
2. La solapa la ve quien ve el dispositivo; los botones, solo quien gestiona.
3. El alta exige al menos un responsable y lo crea en la misma transacción.
4. El rol de agente de relevamiento no se ofrece ni se acepta.
"""

from django.contrib.auth.models import Group
from django.urls import reverse

from programas.models import Dispositivo, MiembroEquipoDispositivo
from programas.services.equipo_dispositivo import pares_persona_rol
from programas.tests.test_dispositivos_equipo_410 import BaseEquipo

CAPS_VER = ("dispositivo.ver",)
CAPS_ADMIN = ("dispositivo.ver", "dispositivo.crear", "dispositivo.editar", "programa.configurar")
AJAX = {"x-requested-with": "XMLHttpRequest"}


class BaseUI(BaseEquipo):
    def setUp(self):
        super().setUp()
        self.rol_ver = self._rol("Operador", CAPS_VER)
        self.rol_admin = self._rol("Admin", CAPS_ADMIN)
        self.rol_agente = self._rol("Agente", CAPS_VER, clave="dispositivos.agente_relevamiento")
        self.admin = self._usuario("admin", self.rol_admin)
        self.resp = self._usuario("resp", self.rol_ver)
        self.miembro = self._usuario("miembro", self.rol_ver)
        self.agente = self._usuario("agente", self.rol_agente)
        self.m_resp = self._miembro(self.disp_a, self.resp, self.rol_ver, responsable=True)
        self.m_otro = self._miembro(self.disp_a, self.miembro, self.rol_ver)
        self.url_detalle = reverse("dispositivos:detalle", args=[self.disp_a.pk])

    def _entrar(self, usuario):
        self.client.force_login(self._fresco(usuario))

    def _urls_post(self, dispositivo=None, miembro=None):
        d = (dispositivo or self.disp_a).pk
        m = (miembro or self.m_otro).pk
        return {
            "sumar": reverse("dispositivos:equipo_sumar", args=[d]),
            "baja": reverse("dispositivos:equipo_baja", args=[d, m]),
            "marcar": reverse("dispositivos:equipo_responsable", args=[d, m]),
            "quitar": reverse("dispositivos:equipo_quitar_responsable", args=[d, m]),
        }


class SolapaEquipoTests(BaseUI):
    def test_quien_ve_sin_gestionar_ve_la_lista_sin_botones(self):
        self._entrar(self.miembro)
        respuesta = self.client.get(self.url_detalle + "?tab=equipo")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'id="panel-equipo"')
        self.assertContains(respuesta, "resp")
        self.assertContains(respuesta, "Responsable")
        self.assertNotContains(respuesta, "Sumar persona")
        self.assertNotContains(respuesta, "/equipo/sumar/")
        self.assertNotContains(respuesta, "Dar de baja del Equipo")

    def test_el_responsable_ve_los_botones(self):
        self._entrar(self.resp)
        respuesta = self.client.get(self.url_detalle + "?tab=equipo")
        self.assertContains(respuesta, "Sumar persona")
        self.assertContains(respuesta, reverse("dispositivos:equipo_baja", args=[self.disp_a.pk, self.m_otro.pk]))

    def test_el_admin_ve_los_botones_y_las_opciones_no_incluyen_al_agente(self):
        self._entrar(self.admin)
        respuesta = self.client.get(self.url_detalle + "?tab=equipo")
        self.assertContains(respuesta, "Sumar persona")
        etiquetas = [par["etiqueta"] for par in pares_persona_rol(self.disp_a)]
        self.assertIn("admin — Admin", etiquetas)
        self.assertFalse([e for e in etiquetas if "Agente" in e])
        # Quien ya está en el Equipo con ese rol no se ofrece de nuevo.
        self.assertNotIn("miembro — Operador", etiquetas)

    def test_el_modal_de_sumar_se_abre_por_url_y_solo_para_quien_gestiona(self):
        self._entrar(self.admin)
        respuesta = self.client.get(self.url_detalle + "?tab=equipo&equipo=sumar")
        self.assertIn("form_equipo", respuesta.context)
        # Desde el Cambio 420 las opciones no viajan en la página: se piden por sugerencias (lo prueba el 420).
        self.assertContains(respuesta, "data-sugerencias-url")
        self.assertNotContains(respuesta, "admin — Admin")
        self.assertNotIn("form_equipo", self.client.get(self.url_detalle + "?tab=equipo").context)
        self._entrar(self.miembro)
        respuesta = self.client.get(self.url_detalle + "?tab=equipo&equipo=sumar")
        self.assertNotIn("form_equipo", respuesta.context)
        self.assertNotContains(respuesta, "modal-equipo-titulo")

    def test_el_equipo_de_otro_dispositivo_no_se_mezcla(self):
        self._miembro(self.disp_b, self.admin, self.rol_admin, responsable=True)
        self._entrar(self.admin)
        respuesta = self.client.get(self.url_detalle + "?tab=equipo")
        self.assertEqual(len(respuesta.context["equipo"]), 2)


class AccionesDelEquipoTests(BaseUI):
    def test_sin_gestion_cada_post_es_403_y_no_muta(self):
        # `miembro` ve el dispositivo (tiene `dispositivo.ver`) pero no lo gestiona.
        self._entrar(self.miembro)
        for nombre, url in self._urls_post().items():
            with self.subTest(nombre):
                datos = {"persona_rol": f"{self.admin.pk}:{self.rol_admin.pk}"} if nombre == "sumar" else {}
                self.assertEqual(self.client.post(url, datos).status_code, 403)
        self.assertEqual(MiembroEquipoDispositivo.objects.filter(dispositivo=self.disp_a).count(), 2)
        self.m_otro.refresh_from_db()
        self.assertTrue(self.m_otro.activo)
        self.assertFalse(self.m_otro.es_responsable)

    def test_un_responsable_de_otro_dispositivo_no_gestiona_este(self):
        self._miembro(self.disp_b, self.miembro, self.rol_ver, responsable=True)
        self._entrar(self.miembro)
        self.assertEqual(self.client.post(self._urls_post()["baja"]).status_code, 403)

    def test_el_403_ajax_es_json(self):
        self._entrar(self.miembro)
        respuesta = self.client.post(self._urls_post()["sumar"], {}, headers=AJAX)
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(respuesta.json()["ok"])

    def test_los_get_no_mutan(self):
        self._entrar(self.admin)
        for url in self._urls_post().values():
            self.assertEqual(self.client.get(url).status_code, 405)

    def test_el_responsable_suma_a_una_persona(self):
        self._entrar(self.resp)
        respuesta = self.client.post(
            self._urls_post()["sumar"], {"persona_rol": f"{self.admin.pk}:{self.rol_admin.pk}", "es_responsable": "on"}
        )
        self.assertRedirects(respuesta, self.url_detalle + "?tab=equipo")
        nuevo = MiembroEquipoDispositivo.objects.get(dispositivo=self.disp_a, usuario=self.admin)
        self.assertTrue(nuevo.activo)
        self.assertTrue(nuevo.es_responsable)

    def test_sumar_rechaza_al_agente_y_lo_dice_en_su_campo(self):
        self._entrar(self.admin)
        respuesta = self.client.post(
            self._urls_post()["sumar"],
            {"persona_rol": f"{self.agente.pk}:{self.rol_agente.pk}"},
            headers=AJAX,
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("persona_rol", respuesta.json()["errors"])
        self.assertFalse(MiembroEquipoDispositivo.objects.filter(usuario=self.agente).exists())

    def test_baja_y_marcar_desmarcar_responsable(self):
        self._entrar(self.resp)
        urls = self._urls_post()
        self.client.post(urls["marcar"])
        self.m_otro.refresh_from_db()
        self.assertTrue(self.m_otro.es_responsable)
        self.client.post(urls["quitar"])
        self.m_otro.refresh_from_db()
        self.assertFalse(self.m_otro.es_responsable)
        self.client.post(urls["baja"])
        self.m_otro.refresh_from_db()
        self.assertFalse(self.m_otro.activo)

    def test_no_se_deja_sin_responsables_y_el_error_es_texto_claro(self):
        self._entrar(self.admin)
        urls = self._urls_post(miembro=self.m_resp)
        respuesta = self.client.post(urls["baja"], follow=True)
        self.assertContains(respuesta, "no puede quedar sin responsables")
        self.m_resp.refresh_from_db()
        self.assertTrue(self.m_resp.activo)

    def test_la_fila_de_otro_dispositivo_es_404(self):
        ajena = self._miembro(self.disp_b, self.miembro, self.rol_ver)
        self._entrar(self.admin)
        url = reverse("dispositivos:equipo_baja", args=[self.disp_a.pk, ajena.pk])
        self.assertEqual(self.client.post(url).status_code, 404)
        ajena.refresh_from_db()
        self.assertTrue(ajena.activo)


class AltaConResponsablesTests(BaseUI):
    def _datos(self, **extra):
        base = {"codigo": "NUEVO-1", "tipo": self.tipo.pk, "nombre": "Nuevo"}
        base.update(extra)
        return base

    def test_la_pantalla_de_alta_ofrece_pares_persona_rol_sin_el_agente(self):
        self._entrar(self.admin)
        respuesta = self.client.get(reverse("dispositivos:crear"))
        self.assertContains(respuesta, "Responsables del dispositivo")
        self.assertContains(respuesta, "resp — Operador")
        self.assertNotContains(respuesta, "agente — Agente")

    def test_alta_sin_responsables_se_rechaza_y_no_crea_nada(self):
        self._entrar(self.admin)
        respuesta = self.client.post(reverse("dispositivos:crear"), self._datos())
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("responsables", respuesta.context["form"].errors)
        self.assertFalse(Dispositivo.objects.filter(codigo="NUEVO-1").exists())

    def test_alta_con_responsables_crea_las_filas_en_la_misma_transaccion(self):
        self._entrar(self.admin)
        respuesta = self.client.post(
            reverse("dispositivos:crear"),
            self._datos(responsables=[f"{self.resp.pk}:{self.rol_ver.pk}", f"{self.admin.pk}:{self.rol_admin.pk}"]),
        )
        self.assertEqual(respuesta.status_code, 302)
        nuevo = Dispositivo.objects.get(codigo="NUEVO-1")
        filas = MiembroEquipoDispositivo.objects.filter(dispositivo=nuevo)
        self.assertEqual(filas.count(), 2)
        self.assertTrue(all(f.es_responsable and f.activo for f in filas))

    def test_alta_con_el_rol_de_agente_se_rechaza(self):
        self._entrar(self.admin)
        respuesta = self.client.post(
            reverse("dispositivos:crear"), self._datos(responsables=[f"{self.agente.pk}:{self.rol_agente.pk}"])
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Dispositivo.objects.filter(codigo="NUEVO-1").exists())

    def test_alta_con_un_par_inexistente_se_rechaza(self):
        self._entrar(self.admin)
        otro = Group.objects.create(name="Suelto")
        respuesta = self.client.post(
            reverse("dispositivos:crear"), self._datos(responsables=[f"{self.resp.pk}:{otro.pk}"])
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Dispositivo.objects.filter(codigo="NUEVO-1").exists())

    def test_la_edicion_no_exige_responsables(self):
        self._entrar(self.admin)
        respuesta = self.client.get(reverse("dispositivos:editar", args=[self.disp_a.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("responsables", respuesta.context["form"].fields)
