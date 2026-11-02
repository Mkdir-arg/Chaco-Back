"""Cambio 407 · a un usuario solo de campo la clave se le entrega por enlace, así que necesita correo.

Decisión del PM (30/10/2026): en el ABM (alta y edición) y en la importación por CSV, una clave tipeada para una
cuenta solo de campo sin correo se rechaza; con correo se entrega el enlace y se marca `debe_cambiar_contrasena`.
"""

import csv
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from programas.models import Programa
from users.forms import MENSAJE_CAMPO_SIN_CORREO
from users.models import Profile
from users.tests.test_credenciales_ola2_pr2 import EscenarioEdicionHaciaCampo, _rol, _SinCubetas, _user

TEXTO = "Para un usuario de campo hace falta un correo: la clave se entrega por enlace"
CLAVE_NUEVA = "Clave-Larguisima-2026"


class EdicionDeUsuarioDeCampoConClaveTests(EscenarioEdicionHaciaCampo, _SinCubetas):
    def _alta(self, username, email):
        return self.client.post(
            reverse("users:usuario_crear"),
            {
                "username": username,
                "email": email,
                "password": CLAVE_NUEVA,
                "groups": [str(self.rol_terr.pk)],
                "segmentos_territoriales": [str(self.segmento.pk)],
            },
        )

    def test_el_mensaje_es_el_decidido(self):
        self.assertEqual(MENSAJE_CAMPO_SIN_CORREO, TEXTO)

    def test_clave_tipeada_para_un_usuario_de_campo_sin_correo_se_rechaza_en_el_campo_correo(self):
        viejo = self._crear("viejo407", self.rol_terr)

        respuesta = self._editar(viejo, password=CLAVE_NUEVA)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["form"].errors["email"], [TEXTO])
        viejo.refresh_from_db()
        self.assertFalse(viejo.check_password(CLAVE_NUEVA))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_clave_tipeada_con_correo_manda_el_enlace_y_marca_el_cambio(self):
        usuario = self._crear("conmail407", self.rol_terr, email="c@x.test")

        respuesta = self._editar(usuario, password=CLAVE_NUEVA)

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/establecer-contrasena/", mail.outbox[-1].body)
        self.assertNotIn(CLAVE_NUEVA, mail.outbox[-1].body)
        usuario.refresh_from_db()
        self.assertFalse(usuario.check_password(CLAVE_NUEVA))
        self.assertTrue(Profile.objects.get(user=usuario).debe_cambiar_contrasena)

    def test_un_usuario_de_backoffice_sin_correo_puede_recibir_clave_tipeada(self):
        operador = self._crear("back407", self.rol_op)

        respuesta = self._editar(operador, password=CLAVE_NUEVA)

        self.assertEqual(respuesta.status_code, 302)

    def test_promover_a_backoffice_con_clave_tipeada_y_sin_correo_se_guarda_en_un_paso(self):
        """La rama de «clave tipeada» mira los roles con los que la cuenta queda, no los de antes."""
        viejo = self._crear("promo409", self.rol_terr)

        respuesta = self._editar(viejo, groups=[str(self.rol_op.pk)], password=CLAVE_NUEVA)

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(set(viejo.groups.all()), {self.rol_op})
        self.assertTrue(User.objects.get(pk=viejo.pk).check_password(CLAVE_NUEVA))

    def test_el_alta_de_campo_sin_correo_usa_el_mismo_texto(self):
        respuesta = self._alta("alta407", "")

        self.assertEqual(respuesta.context["form"].errors["email"], [TEXTO])
        self.assertFalse(User.objects.filter(username="alta407").exists())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_el_alta_de_campo_con_correo_manda_el_enlace_y_marca_el_cambio(self):
        self._alta("alta407b", "a@x.test")

        usuario = User.objects.get(username="alta407b")
        self.assertIn("/establecer-contrasena/", mail.outbox[-1].body)
        self.assertTrue(Profile.objects.get(user=usuario).debe_cambiar_contrasena)


class ImportCsvSoloCampoTests(TestCase):
    def setUp(self):
        becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.rol_terr = _rol("Terr", ["becas.campo"], becas)
        self.referencia = _user("referente407", self.rol_terr)
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _importar(self, filas):
        ruta = Path(self.tmp.name) / "u.csv"
        with ruta.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["Usuario", "Email", "Nombre completo", "Apellido", "Contraseña"])
            w.writeheader()
            w.writerows(filas)
        salida = StringIO()
        call_command(
            "import_users_from_csv",
            str(ruta),
            "--reference-user-id",
            str(self.referencia.pk),
            "--aplicar",
            stdout=salida,
        )
        return salida.getvalue()

    def _fila(self, usuario, email=""):
        return {
            "Usuario": usuario,
            "Email": email,
            "Nombre completo": "N",
            "Apellido": "A",
            "Contraseña": "Resistencia-2026-Chaco",
        }

    def test_la_fila_de_campo_sin_correo_se_rechaza_y_las_demas_siguen(self):
        salida = self._importar([self._fila("sinmail407"), self._fila("conmail407", "c@x.test")])

        self.assertFalse(User.objects.filter(username="sinmail407").exists())
        self.assertTrue(User.objects.filter(username="conmail407").exists())
        self.assertIn("sinmail407", salida)
        self.assertIn("usuario de campo", salida)

    def test_la_misma_fila_para_un_rol_de_backoffice_sin_correo_entra(self):
        rol_op = _rol("OpX", ["ciudadano.ver"])
        self.referencia.groups.set(Group.objects.filter(pk=rol_op.pk))

        self._importar([self._fila("back407")])

        self.assertTrue(User.objects.filter(username="back407").exists())

    def test_una_fila_de_campo_con_correo_ignora_la_clave_del_archivo_y_lo_informa(self):
        """Cambio 409 · D3: la clave se entrega por enlace; la del archivo no se usa."""
        salida = self._importar([self._fila("conmail409", "c409@x.test")])

        usuario = User.objects.get(username="conmail409")
        self.assertFalse(usuario.check_password("Resistencia-2026-Chaco"))
        self.assertFalse(usuario.has_usable_password())
        self.assertIn('pedir "Olvidé mi contraseña"', salida)
        self.assertIn("conmail409", salida)
        self.assertNotIn("Resistencia-2026-Chaco", salida)

    def test_la_misma_fila_de_backoffice_conserva_la_clave_del_archivo(self):
        rol_op = _rol("OpY", ["ciudadano.ver"])
        self.referencia.groups.set(Group.objects.filter(pk=rol_op.pk))

        salida = self._importar([self._fila("back409", "b409@x.test")])

        self.assertTrue(User.objects.get(username="back409").check_password("Resistencia-2026-Chaco"))
        self.assertNotIn("Olvidé mi contraseña", salida)
