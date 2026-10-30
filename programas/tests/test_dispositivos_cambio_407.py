"""Cambio 407 · QA local de Dispositivos del 30/10/2026.

1. **A-01** «Ingresar persona» se ofrece solo a quien el asistente deja entrar (`dispositivo.admitir`
   con alcance **y** `ciudadano.ver`), y el egreso/cambio de plaza no manda a quien no ve personas a una
   pantalla que le da 403.
2. **A-05** el formulario del tipo carga el buscador con píldoras.
3. **A-02** un dispositivo RECHAZADO se corrige y se vuelve a enviar a validación (INACTIVO no).
4. **C-S2** la clave provisoria del agente se cambia antes de usar la app: el login de token de campo
   responde 403 `debe_cambiar_contrasena` mientras la marca esté puesta, y el enlace la limpia.
"""

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core import rbac
from programas.models import Dispositivo, TrazaDispositivo
from programas.services.dispositivos import enviar_a_validacion
from programas.tests.test_dispositivos_crear_agente import BaseCrearAgente
from programas.tests.test_dispositivos_estadia_detalle import FORMATO, TODO, BaseDetalle
from programas.tests.test_dispositivos_legajo import area_de_prueba
from programas.views.dispositivos_legajo import url_solapa_estadias
from users.models import Profile

TEXTO_BOTON = "Ingresar persona"
MENSAJE_CLAVE = (
    "Tenés que cambiar la clave antes de usar la app. "
    "Usá el enlace que te llegó por correo o pedí uno nuevo desde «Olvidé mi contraseña»."
)


class _UnClientePorUsuario(BaseDetalle):
    """El backoffice admite una sola sesión por usuario: un segundo login invalida el primero."""

    def setUp(self):
        super().setUp()
        self._clientes = {}

    def _cliente(self, usuario=None):
        usuario = usuario or self.operador
        if usuario.pk not in self._clientes:
            self._clientes[usuario.pk] = super()._cliente(usuario)
        return self._clientes[usuario.pk]


class IngresarPersonaSoloConCiudadanoVerTests(_UnClientePorUsuario):
    def _detalle(self, usuario):
        return self._cliente(usuario).get(reverse("dispositivos:detalle", args=[self.cis.pk]), {"tab": "estadias"})

    def _sin(self, nombre, *quitar):
        capacidades = tuple(c for c in TODO if c not in quitar)
        return self._operador(nombre, self.cis, capacidades)

    def test_sin_ciudadano_ver_el_boton_no_se_ofrece_y_el_asistente_da_403(self):
        usuario = self._sin("Sin padron", "ciudadano.ver")

        respuesta = self._detalle(usuario)

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.context["puede_admitir"])
        self.assertNotContains(respuesta, TEXTO_BOTON)
        asistente = self._cliente(usuario).get(reverse("dispositivos:ingreso_persona", args=[self.cis.pk]))
        self.assertEqual(asistente.status_code, 403)

    def test_con_ciudadano_ver_el_boton_se_ofrece_y_el_asistente_abre(self):
        respuesta = self._detalle(self.operador)

        self.assertTrue(respuesta.context["puede_admitir"])
        self.assertContains(respuesta, TEXTO_BOTON)
        asistente = self._cliente().get(reverse("dispositivos:ingreso_persona", args=[self.cis.pk]))
        self.assertEqual(asistente.status_code, 200, asistente.headers.get("Location"))

    def test_sin_admitir_el_boton_tampoco_se_ofrece(self):
        usuario = self._sin("Sin admitir", "dispositivo.admitir")

        respuesta = self._detalle(usuario)

        self.assertFalse(respuesta.context["puede_admitir"])
        self.assertNotContains(respuesta, TEXTO_BOTON)

    def test_egresar_sin_ciudadano_ver_no_manda_a_un_403(self):
        usuario = self._sin("Egresa sin padron", "ciudadano.ver")
        datos = {
            "fecha_egreso": timezone.localtime().strftime(FORMATO),
            "motivo": self.alta.pk,
            "destino": "Domicilio",
            "observaciones": "",
            "volver": "estadia",
        }
        url = reverse("dispositivos:egresar", args=[self.cis.pk, self.estadia.pk])

        respuesta = self._cliente(usuario).post(url, datos, headers={"x-requested-with": "XMLHttpRequest"})

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json()["redirect"], url_solapa_estadias(self.cis.pk))


class BuscadorEnElFormularioDelTipoTests(_UnClientePorUsuario):
    def test_el_alta_y_la_edicion_cargan_el_buscador(self):
        admin = User.objects.create_superuser("admin407", password="x")
        self._clientes[admin.pk] = self._cliente(admin)
        for nombre, url in (
            ("alta", reverse("dispositivos:crear")),
            ("edicion", reverse("dispositivos:editar", args=[self.cis.pk])),
        ):
            with self.subTest(nombre):
                respuesta = self._cliente(admin).get(url)
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, "custom/css/nodo-buscador.css")
                self.assertContains(respuesta, "custom/js/nodo-buscador.js")
                self.assertContains(respuesta, "window.nodoBuscador.montar(seccion)")


def _completar(dispositivo):
    dispositivo.localidad = "Resistencia"
    dispositivo.domicilio = "Av. Sarmiento 100"
    dispositivo.responsable_nombre = "Laura Pérez"
    dispositivo.contacto_telefono = "3624000000"
    dispositivo.categoria = Dispositivo.Categoria.PUBLICO_ESTATAL
    dispositivo.area_ministerio = area_de_prueba()
    dispositivo.save()


class ReenvioDelRechazadoTests(_UnClientePorUsuario):
    def _rechazado(self, completo=True):
        if completo:
            _completar(self.cis)
        Dispositivo.objects.filter(pk=self.cis.pk).update(estado=Dispositivo.Estado.RECHAZADO)
        return Dispositivo.objects.get(pk=self.cis.pk)

    def test_el_servicio_reenvia_el_rechazado_y_deja_traza(self):
        dispositivo = self._rechazado()

        enviar_a_validacion(dispositivo, self.operador)

        dispositivo.refresh_from_db()
        self.assertEqual(dispositivo.estado, Dispositivo.Estado.PENDIENTE_VALIDACION)
        traza = TrazaDispositivo.objects.filter(dispositivo=dispositivo, accion="ENVIADO_VALIDACION").last()
        self.assertEqual(traza.estado_anterior, Dispositivo.Estado.RECHAZADO)
        self.assertEqual(traza.estado_nuevo, Dispositivo.Estado.PENDIENTE_VALIDACION)

    def test_el_rechazado_incompleto_no_se_reenvia(self):
        Dispositivo.objects.filter(pk=self.cis.pk).update(localidad="", domicilio="")
        dispositivo = self._rechazado(completo=False)

        with self.assertRaisesMessage(ValidationError, "Completá los campos obligatorios"):
            enviar_a_validacion(dispositivo, self.operador)

        dispositivo.refresh_from_db()
        self.assertEqual(dispositivo.estado, Dispositivo.Estado.RECHAZADO)

    def test_inactivo_y_cerrado_siguen_sin_reenvio(self):
        for estado in (Dispositivo.Estado.INACTIVO, Dispositivo.Estado.CERRADO, Dispositivo.Estado.ACTIVO):
            with self.subTest(estado):
                _completar(self.cis)
                Dispositivo.objects.filter(pk=self.cis.pk).update(estado=estado)
                with self.assertRaisesMessage(ValidationError, "no está permitida"):
                    enviar_a_validacion(Dispositivo.objects.get(pk=self.cis.pk), self.operador)

    def test_la_vista_reenvia_con_editar_y_da_403_sin_editar(self):
        self._rechazado()
        url = reverse("dispositivos:enviar_validacion", args=[self.cis.pk])
        sin_editar = self._operador("Sin editar", self.cis, tuple(c for c in TODO if c != "dispositivo.editar"))

        self.assertEqual(self._cliente(sin_editar).post(url).status_code, 403)
        self.assertEqual(Dispositivo.objects.get(pk=self.cis.pk).estado, Dispositivo.Estado.RECHAZADO)

        self._cliente().post(url)
        self.assertEqual(Dispositivo.objects.get(pk=self.cis.pk).estado, Dispositivo.Estado.PENDIENTE_VALIDACION)

    def test_el_detalle_ofrece_enviar_solo_al_rechazado_con_editar(self):
        self._rechazado()
        url = reverse("dispositivos:detalle", args=[self.cis.pk])

        respuesta = self._cliente().get(url)

        self.assertTrue(respuesta.context["puede_enviar_validacion"])
        self.assertContains(respuesta, reverse("dispositivos:enviar_validacion", args=[self.cis.pk]))
        sin_editar = self._operador("Sin editar", self.cis, tuple(c for c in TODO if c != "dispositivo.editar"))
        self.assertFalse(self._cliente(sin_editar).get(url).context["puede_enviar_validacion"])
        Dispositivo.objects.filter(pk=self.cis.pk).update(estado=Dispositivo.Estado.INACTIVO)
        self.assertFalse(self._cliente().get(url).context["puede_enviar_validacion"])


def _enlace_de_reseteo(usuario):
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    return reverse(
        "users:establecer_contrasena",
        kwargs={"uidb64": uid, "token": default_token_generator.make_token(usuario)},
    )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ClaveProvisoriaDelAgenteTests(BaseCrearAgente):
    """C-S2: el alta rápida ya entrega el enlace; el token de la app no se emite hasta usarlo."""

    def _crear_agente(self):
        respuesta = self._post()
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        return User.objects.get(pk=respuesta.json()["user"]["id"])

    def _token(self, usuario, clave="x"):
        return APIClient().post(reverse("becas_api:token"), {"username": usuario.username, "password": clave})

    def test_el_alta_del_agente_entrega_enlace_de_reseteo_y_no_clave(self):
        mail.outbox.clear()

        agente = self._crear_agente()

        self.assertTrue(rbac.es_solo_campo(agente))
        self.assertTrue(Profile.objects.get(user=agente).debe_cambiar_contrasena)
        cuerpo = mail.outbox[0].body
        self.assertIn("/establecer-contrasena/", cuerpo)
        self.assertNotIn("Contraseña provisoria", cuerpo)

    def test_con_la_marca_puesta_el_token_se_rechaza_con_403_y_codigo(self):
        agente = self._crear_agente()
        agente.set_password("Clave-Del-Correo-1")  # lo que tendría si le hubiera llegado una clave
        agente.save()

        respuesta = self._token(agente, "Clave-Del-Correo-1")

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json(), {"codigo": "debe_cambiar_contrasena", "detail": MENSAJE_CLAVE})
        self.assertFalse(Token.objects.filter(user=agente).exists())

    def test_con_clave_equivocada_no_se_revela_la_marca(self):
        agente = self._crear_agente()

        respuesta = self._token(agente, "no-es-la-clave")

        self.assertEqual(respuesta.status_code, 400)
        self.assertNotIn("codigo", respuesta.json())

    def test_el_enlace_limpia_la_marca_y_despues_el_token_se_emite(self):
        agente = self._crear_agente()
        cliente = Client()
        destino = cliente.get(_enlace_de_reseteo(agente))["Location"]

        respuesta = cliente.post(
            destino, {"new_password1": "Elegida-Por-Mi-2026", "new_password2": "Elegida-Por-Mi-2026"}
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Profile.objects.get(user=agente).debe_cambiar_contrasena)
        emitido = self._token(agente, "Elegida-Por-Mi-2026")
        self.assertEqual(emitido.status_code, 200, emitido.content)
        self.assertIn("dispositivos", emitido.json()["modulos"])
        self.assertTrue(Token.objects.filter(user=agente).exists())

    def test_olvide_mi_contrasena_tambien_libera_la_marca(self):
        """El mensaje de la app manda ahí: el correo de recupero apunta a la misma vista que limpia la marca."""
        agente = self._crear_agente()
        mail.outbox.clear()

        Client().post(reverse("users:recuperar_contrasena"), {"email": agente.email})

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/establecer-contrasena/", mail.outbox[0].body)
        enlace = next(linea.strip() for linea in mail.outbox[0].body.splitlines() if "/establecer-contrasena/" in linea)
        cliente = Client()
        destino = cliente.get(enlace[enlace.index("/establecer-contrasena/") :])["Location"]
        cliente.post(destino, {"new_password1": "Otra-Clave-2026-x", "new_password2": "Otra-Clave-2026-x"})
        self.assertFalse(Profile.objects.get(user=agente).debe_cambiar_contrasena)
        self.assertEqual(self._token(agente, "Otra-Clave-2026-x").status_code, 200)

    def test_el_usuario_sin_la_marca_entra_como_siempre(self):
        agente = self._crear_agente()
        Profile.objects.filter(user=agente).update(debe_cambiar_contrasena=False)
        agente.set_password("Clave-Propia-2026")
        agente.save()

        self.assertEqual(self._token(agente, "Clave-Propia-2026").status_code, 200)
