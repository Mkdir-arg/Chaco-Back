"""Alta de dispositivo: el responsable y el contacto salen de la persona elegida (Cambio 448).

«Responsable y contacto» ya no se pide a mano en el alta: «Responsables del dispositivo» es un
buscador múltiple y el legajo copia nombre, documento, teléfono y email de la primera persona
elegida (en el orden del listado, que es el de las píldoras). La edición sigue mostrando los cuatro
campos para corregirlos.
"""

from django.urls import reverse

from programas.models import Dispositivo
from programas.tests.test_dispositivos_equipo_ui_411 import BaseUI
from users.models import Profile

CAMPOS = ("responsable_nombre", "responsable_documento", "contacto_telefono", "contacto_email")


class AltaContactoDelResponsableTests(BaseUI):
    def setUp(self):
        super().setUp()
        self.admin.first_name, self.admin.last_name, self.admin.email = "Ana", "Alvarez", "ana@example.com"
        self.admin.save()
        # El listado va por apellido: Alvarez antes que Zapata.
        self.resp.last_name = "Zapata"
        self.resp.save()
        Profile.objects.update_or_create(user=self.admin, defaults={"dni": "30111222", "telefono": "3624111222"})
        self.par_admin = f"{self.admin.pk}:{self.rol_admin.pk}"
        self.par_resp = f"{self.resp.pk}:{self.rol_ver.pk}"

    def _datos(self, **extra):
        return {"codigo": "NUEVO-448", "tipo": self.tipo.pk, "nombre": "Nuevo", **extra}

    def test_el_alta_no_pide_responsable_y_contacto_y_ofrece_un_buscador(self):
        self._entrar(self.admin)
        respuesta = self.client.get(reverse("dispositivos:crear"))
        form = respuesta.context["form"]
        for campo in CAMPOS:
            self.assertNotIn(campo, form.fields)
        self.assertNotContains(respuesta, "Responsable y contacto")
        self.assertContains(respuesta, 'data-buscador="1"')
        self.assertContains(respuesta, 'data-telefono="3624111222"')
        # El documento y el email de la persona no viajan a la página.
        self.assertNotContains(respuesta, "30111222")
        self.assertNotContains(respuesta, "ana@example.com")

    def test_el_alta_copia_el_contacto_de_la_primera_persona_del_listado(self):
        self._entrar(self.admin)
        # Se mandan en otro orden: manda el del listado (admin va antes que resp).
        respuesta = self.client.post(
            reverse("dispositivos:crear"), self._datos(responsables=[self.par_resp, self.par_admin])
        )
        self.assertEqual(respuesta.status_code, 302)
        nuevo = Dispositivo.objects.get(codigo="NUEVO-448")
        self.assertEqual(nuevo.responsable_nombre, "Ana Alvarez")
        self.assertEqual(nuevo.responsable_documento, "30111222")
        self.assertEqual(nuevo.contacto_telefono, "3624111222")
        self.assertEqual(nuevo.contacto_email, "ana@example.com")

    def test_sin_perfil_copia_el_nombre_y_deja_vacios_documento_y_telefono(self):
        self._entrar(self.admin)
        respuesta = self.client.post(reverse("dispositivos:crear"), self._datos(responsables=[self.par_resp]))
        self.assertEqual(respuesta.status_code, 302)
        nuevo = Dispositivo.objects.get(codigo="NUEVO-448")
        self.assertEqual(nuevo.responsable_nombre, "Zapata")
        self.assertEqual((nuevo.responsable_documento, nuevo.contacto_telefono), ("", ""))

    def test_el_perfil_pasa_por_las_reglas_del_legajo(self):
        """Mutación: sin las reglas en `datos_de_contacto`, «no tiene» se copia y la edición se traba."""
        self._entrar(self.admin)
        url = reverse("dispositivos:crear")
        Profile.objects.update_or_create(user=self.resp, defaults={"dni": "abc", "telefono": "no tiene"})
        form = self.client.post(url, {"codigo": "X", "responsables": [self.par_resp]}).context["form"]
        self.assertEqual(form.faltantes_responsable, ["telefono"])
        self.client.post(url, self._datos(responsables=[self.par_resp]))
        nuevo = Dispositivo.objects.get(codigo="NUEVO-448")
        self.assertEqual((nuevo.responsable_documento, nuevo.contacto_telefono), ("", ""))
        # Un teléfono válido con formato se guarda normalizado, como escrito a mano.
        Profile.objects.filter(user=self.admin).update(telefono="(0362) 15-411-1222")
        self.client.post(url, self._datos(codigo="NUEVO-448B", responsables=[self.par_admin]))
        self.assertEqual(Dispositivo.objects.get(codigo="NUEVO-448B").contacto_telefono, "0362154111222")

    def test_un_post_con_los_campos_viejos_no_los_pisa(self):
        self._entrar(self.admin)
        self.client.post(
            reverse("dispositivos:crear"),
            self._datos(responsables=[self.par_admin], responsable_nombre="Otro", contacto_telefono="111"),
        )
        nuevo = Dispositivo.objects.get(codigo="NUEVO-448")
        self.assertEqual((nuevo.responsable_nombre, nuevo.contacto_telefono), ("Ana Alvarez", "3624111222"))

    def test_el_resumen_de_validacion_pide_responsable_y_despues_su_telefono(self):
        self._entrar(self.admin)
        url = reverse("dispositivos:crear")
        self.assertEqual(self.client.get(url).context["form"].faltantes_responsable, ["ninguno"])
        # Vuelve con errores (sin nombre de dispositivo) para ver el resumen con lo elegido.
        sin_telefono = self.client.post(url, {"codigo": "X", "responsables": [self.par_resp]}).context["form"]
        self.assertEqual(sin_telefono.faltantes_responsable, ["telefono"])
        con_telefono = self.client.post(url, {"codigo": "X", "responsables": [self.par_admin]}).context["form"]
        self.assertEqual(con_telefono.faltantes_responsable, [])

    def test_la_edicion_sigue_mostrando_responsable_y_contacto(self):
        self._entrar(self.admin)
        respuesta = self.client.get(reverse("dispositivos:editar", args=[self.disp_a.pk]))
        for campo in CAMPOS:
            self.assertIn(campo, respuesta.context["form"].fields)
        self.assertContains(respuesta, "Responsable y contacto")
