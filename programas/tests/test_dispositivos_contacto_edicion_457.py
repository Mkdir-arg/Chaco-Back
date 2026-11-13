"""Edición de dispositivo: el contacto sale siempre del primer responsable del Equipo (Cambio 457).

El alta ya tomaba «Responsable y contacto» de la persona elegida (Cambio 450), pero la edición
seguía pidiendo los cuatro campos a mano y era el único lugar donde cargar un teléfono faltante.
Ahora, con un responsable en el Equipo, la edición no los pide: el legajo los toma de esa persona al
guardar y antes de enviar a validación o validar. Lo que el perfil no trae válido conserva el valor
guardado. Un legajo sin responsables (anterior al Cambio 411) sigue con los campos a mano.
"""

from django.core.exceptions import ValidationError
from django.urls import reverse

from programas.models import Dispositivo, TrazaDispositivo
from programas.services.dispositivos import enviar_a_validacion
from programas.tests.test_dispositivos_cambio_407 import _completar
from programas.tests.test_dispositivos_equipo_ui_411 import BaseUI
from users.models import Profile

CAMPOS = ("responsable_nombre", "responsable_documento", "contacto_telefono", "contacto_email")


class EdicionContactoDelEquipoTests(BaseUI):
    def setUp(self):
        super().setUp()
        # `resp` es el responsable de `disp_a` (BaseUI); `disp_b` no tiene Equipo.
        self.resp.first_name, self.resp.last_name, self.resp.email = "Rita", "Zapata", "rita@example.com"
        self.resp.save()
        self.url = reverse("dispositivos:editar", args=[self.disp_a.pk])

    def _datos(self, dispositivo, **extra):
        return {"codigo": dispositivo.codigo, "tipo": self.tipo.pk, "nombre": dispositivo.nombre, **extra}

    def test_con_responsable_la_edicion_no_pide_los_campos_y_muestra_el_contacto(self):
        Profile.objects.update_or_create(user=self.resp, defaults={"dni": "30111222", "telefono": "3624111222"})
        self._entrar(self.admin)
        respuesta = self.client.get(self.url)
        form = respuesta.context["form"]
        for campo in CAMPOS:
            self.assertNotIn(campo, form.fields)
        self.assertContains(respuesta, "Responsable y contacto")
        self.assertContains(respuesta, "Rita Zapata · 3624111222")
        # Como en el alta, documento y email no viajan a la página.
        self.assertNotContains(respuesta, "30111222")
        self.assertNotContains(respuesta, "rita@example.com")

    def test_sin_telefono_en_el_perfil_el_resumen_lo_pide_en_el_perfil(self):
        self._entrar(self.admin)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.context["form"].faltantes_responsable, ["telefono"])
        self.assertContains(respuesta, "Rita Zapata · sin teléfono en su perfil")
        self.assertContains(
            respuesta, "Teléfono del responsable: cargalo en el perfil de <span data-nombre-responsable>Rita Zapata"
        )

    def test_guardar_copia_el_contacto_del_responsable_y_lo_deja_en_la_traza(self):
        Profile.objects.update_or_create(user=self.resp, defaults={"dni": "30111222", "telefono": "3624111222"})
        self._entrar(self.admin)
        respuesta = self.client.post(self.url, self._datos(self.disp_a))
        self.assertEqual(respuesta.status_code, 302)
        self.disp_a.refresh_from_db()
        self.assertEqual(
            [getattr(self.disp_a, campo) for campo in CAMPOS],
            ["Rita Zapata", "30111222", "3624111222", "rita@example.com"],
        )
        traza = TrazaDispositivo.objects.filter(dispositivo=self.disp_a, accion="EDITADO").latest("pk")
        self.assertIn("3624111222", traza.detalle)

    def test_un_post_con_los_campos_viejos_no_los_pisa(self):
        Profile.objects.update_or_create(user=self.resp, defaults={"telefono": "3624111222"})
        self._entrar(self.admin)
        self.client.post(self.url, self._datos(self.disp_a, responsable_nombre="Otro", contacto_telefono="111"))
        self.disp_a.refresh_from_db()
        self.assertEqual((self.disp_a.responsable_nombre, self.disp_a.contacto_telefono), ("Rita Zapata", "3624111222"))

    def test_lo_que_el_perfil_no_trae_conserva_lo_guardado(self):
        """Mutación: si `contacto_del_equipo` copiara los vacíos, el teléfono cargado antes se perdería."""
        Dispositivo.objects.filter(pk=self.disp_a.pk).update(contacto_telefono="3624999888")
        self._entrar(self.admin)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.context["form"].faltantes_responsable, [])
        self.client.post(self.url, self._datos(self.disp_a))
        self.disp_a.refresh_from_db()
        self.assertEqual((self.disp_a.responsable_nombre, self.disp_a.contacto_telefono), ("Rita Zapata", "3624999888"))

    def test_toma_al_primer_responsable_en_el_orden_del_alta(self):
        self.admin.first_name, self.admin.last_name = "Ana", "Alvarez"
        self.admin.save()
        self._miembro(self.disp_a, self.admin, self.rol_admin, responsable=True)
        self._entrar(self.admin)
        self.client.post(self.url, self._datos(self.disp_a))
        self.disp_a.refresh_from_db()
        # Alvarez va antes que Zapata, como en las píldoras del alta.
        self.assertEqual(self.disp_a.responsable_nombre, "Ana Alvarez")

    def test_sin_responsables_la_edicion_sigue_con_los_campos_a_mano(self):
        self._entrar(self.admin)
        url = reverse("dispositivos:editar", args=[self.disp_b.pk])
        respuesta = self.client.get(url)
        for campo in CAMPOS:
            self.assertIn(campo, respuesta.context["form"].fields)
        self.assertEqual(respuesta.context["form"].faltantes_responsable, [])
        self.client.post(
            url, self._datos(self.disp_b, responsable_nombre="Laura Pérez", contacto_telefono="3624000000")
        )
        self.disp_b.refresh_from_db()
        self.assertEqual((self.disp_b.responsable_nombre, self.disp_b.contacto_telefono), ("Laura Pérez", "3624000000"))


class EnviarAValidacionSincronizaTests(BaseUI):
    """El caso de testing (dispositivo 14): el alta guardó el legajo sin teléfono porque el perfil no
    lo tenía; cargarlo después en el perfil alcanza para enviar a validación."""

    def setUp(self):
        super().setUp()
        self.resp.first_name, self.resp.last_name = "Rita", "Zapata"
        self.resp.save()
        _completar(self.disp_a)
        Dispositivo.objects.filter(pk=self.disp_a.pk).update(contacto_telefono="", estado=Dispositivo.Estado.BORRADOR)
        self.disp_a.refresh_from_db()

    def test_sin_telefono_en_el_perfil_no_se_envia(self):
        with self.assertRaisesMessage(ValidationError, "Teléfono"):
            enviar_a_validacion(self.disp_a, self._fresco(self.admin))

    def test_con_el_telefono_cargado_en_el_perfil_se_envia_y_lo_copia(self):
        Profile.objects.update_or_create(user=self.resp, defaults={"telefono": "3624111222"})
        enviado = enviar_a_validacion(self.disp_a, self._fresco(self.admin))
        self.assertEqual(enviado.estado, Dispositivo.Estado.PENDIENTE_VALIDACION)
        self.disp_a.refresh_from_db()
        self.assertEqual((self.disp_a.responsable_nombre, self.disp_a.contacto_telefono), ("Rita Zapata", "3624111222"))
