"""Credenciales — Ola 2, PR 2 (G2-03 y SEC-26, con D-26 = link de reseteo).

PoC invertidas de `docs/internal/auditoria-2026-10/poc/test_repro_usuarios.py`
(`G2CambioClaveSinClaveActualTests`, `G1b03y04TokenCampoTests`) más lo que la ficha
SEC-26 pide por su cuenta: límite de intentos, el include de `django.contrib.auth.urls`
que ya no está, y el token de la app que deja de valer cuando cambia la clave.
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import Resolver404, resolve, reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core import rbac
from programas.models import Programa, Segmento
from users.models import Capacidad, Profile, RolMeta

CLAVE = "Clave-Segura-2026"


def _perm(codigo):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct)


def _rol(nombre, caps, programa=None):
    grupo = Group.objects.create(name=nombre)
    RolMeta.objects.create(
        grupo=grupo,
        categoria=rbac.CATEGORIA_PROGRAMA if programa else "Sistema",
        programa=programa,
        activo=True,
    )
    for codigo in caps:
        grupo.permissions.add(_perm(codigo))
    return grupo


def _user(username, *grupos, password=CLAVE):
    usuario = User.objects.create_user(username, password=password, email=f"{username}@x.test")
    for grupo in grupos:
        usuario.groups.add(grupo)
    return usuario


class _SinCubetas(TestCase):
    """Las cubetas del rate limit viven en la caché del proceso: una por test."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)


# --------------------------------------------------------------------------- #
# G2-03 — la pantalla de cambio obligatorio no es un cambio de clave para todos
# --------------------------------------------------------------------------- #
class G2CambioClaveSinClaveActualTests(_SinCubetas):
    def setUp(self):
        super().setUp()
        self.usuario = _user("victima", _rol("OpX", ["ciudadano.ver"]), password="Original-2026")
        self.obligatorio = reverse("users:cambiar_contrasena_obligatorio")
        self.voluntario = reverse("users:cambiar_contrasena")

    def test_una_sesion_sin_clave_provisoria_no_cambia_la_clave_sin_la_actual(self):
        """La PoC invertida: un `fetch` silencioso tomaba la cuenta para siempre."""
        self.client.force_login(self.usuario)

        respuesta = self.client.post(
            self.obligatorio,
            {"new_password1": "Tomada-Por-Xss-99", "new_password2": "Tomada-Por-Xss-99"},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], self.voluntario)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("Original-2026"))

    def test_con_la_clave_provisoria_la_pantalla_sigue_andando(self):
        Profile.objects.filter(user=self.usuario).update(debe_cambiar_contrasena=True)
        self.client.force_login(User.objects.get(pk=self.usuario.pk))

        respuesta = self.client.post(
            self.obligatorio,
            {"new_password1": "Nueva-clave-segura-2026", "new_password2": "Nueva-clave-segura-2026"},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("Nueva-clave-segura-2026"))
        self.assertFalse(Profile.objects.get(user=self.usuario).debe_cambiar_contrasena)

    def test_el_cambio_voluntario_exige_la_clave_actual(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.post(
            self.voluntario,
            {
                "old_password": "la-que-no-es",
                "new_password1": "Nueva-clave-segura-2026",
                "new_password2": "Nueva-clave-segura-2026",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("old_password", respuesta.context["form"].errors)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("Original-2026"))

    def test_el_cambio_voluntario_con_la_clave_actual_funciona_y_no_pierde_la_sesion(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.post(
            self.voluntario,
            {
                "old_password": "Original-2026",
                "new_password1": "Nueva-clave-segura-2026",
                "new_password2": "Nueva-clave-segura-2026",
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("Nueva-clave-segura-2026"))
        self.assertEqual(self.client.get(reverse("core:inicio")).status_code, 200)

    def test_un_anonimo_no_entra_a_ninguna_de_las_dos(self):
        for url in (self.obligatorio, self.voluntario):
            respuesta = self.client.get(url)
            self.assertEqual(respuesta.status_code, 302)
            self.assertIn(reverse("users:login"), respuesta["Location"])

    def test_un_usuario_sin_rol_si_puede_cambiar_su_propia_clave(self):
        pelado = _user("pelado", password="Original-2026")
        self.client.force_login(pelado)

        self.assertEqual(self.client.get(self.voluntario).status_code, 200)

    def test_el_superusuario_tambien_pasa_por_la_clave_actual(self):
        jefe = User.objects.create_superuser("jefe", "jefe@x.test", "Original-2026")
        self.client.force_login(jefe)

        respuesta = self.client.post(
            self.voluntario,
            {
                "old_password": "la-que-no-es",
                "new_password1": "Nueva-clave-segura-2026",
                "new_password2": "Nueva-clave-segura-2026",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        jefe.refresh_from_db()
        self.assertTrue(jefe.check_password("Original-2026"))


# --------------------------------------------------------------------------- #
# SEC-26 — el segundo juego de rutas de autenticación ya no existe
# --------------------------------------------------------------------------- #
class SinRutasDeAuthDeDjangoTests(TestCase):
    def test_las_rutas_de_django_contrib_auth_urls_no_resuelven(self):
        """`/password_change/` no renderizaba nada (no hay plantilla), pero el POST
        cambiaba la clave y redirigía: sin clave actual y sin límite de intentos."""
        for ruta in ("/password_reset/", "/password_reset/done/", "/reset/done/", "/password_change/"):
            with self.subTest(ruta=ruta):
                with self.assertRaises(Resolver404):
                    resolve(ruta)

    def test_los_flujos_propios_siguen_resolviendo(self):
        for nombre in (
            "users:login",
            "users:logout",
            "users:recuperar_contrasena",
            "users:cambiar_contrasena",
            "users:cambiar_contrasena_obligatorio",
        ):
            with self.subTest(nombre=nombre):
                self.assertTrue(resolve(reverse(nombre)))


# --------------------------------------------------------------------------- #
# SEC-26 — límite de intentos en el login y en el recupero
# --------------------------------------------------------------------------- #
class LimiteDeIntentosTests(_SinCubetas):
    def setUp(self):
        super().setUp()
        self.usuario = _user("operador", _rol("OpX", ["ciudadano.ver"]), password="Original-2026")

    def _fallar(self, veces, username="operador", ip="203.0.113.9"):
        for _ in range(veces):
            self.client.post(reverse("users:login"), {"username": username, "password": "no-es"}, REMOTE_ADDR=ip)

    def test_despues_de_diez_intentos_fallidos_quien_no_sabe_la_clave_queda_frenado(self):
        self._fallar(10)

        respuesta = self.client.post(reverse("users:login"), {"username": "operador", "password": "tampoco"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["form"].non_field_errors().as_data()[0].code, "demasiados_intentos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_la_cubeta_es_por_usuario_y_no_frena_a_los_demas(self):
        otro = _user("companiera", _rol("OpY", ["ciudadano.ver"]), password="Original-2026")

        self._fallar(10)
        respuesta = self.client.post(reverse("users:login"), {"username": otro.username, "password": "Original-2026"})

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_entrar_bien_no_gasta_cuota(self):
        """Una oficina entera sale por la misma IP: si el acierto consumiera ficha,
        el límite se lo comería el tráfico normal."""
        for _ in range(12):
            self.client.post(reverse("users:login"), {"username": "operador", "password": "Original-2026"})
            self.client.logout()

        respuesta = self.client.post(reverse("users:login"), {"username": "operador", "password": "Original-2026"})
        self.assertEqual(respuesta.status_code, 302)

    def test_la_cubeta_por_usuario_no_deja_afuera_al_dueno_de_la_cuenta(self):
        """Bloqueo de cuenta por tercero (ronda 2). La cubeta por usuario no mira la
        IP —si no, rotar de proxy devolvía la cuota—, y por eso mismo la llena
        **cualquiera** tipeando el usuario de otro. Diez POST desde un locutorio
        dejaban diez minutos afuera a quien quisieran. Ahora se consulta recién
        después de autenticar: con la clave correcta se entra siempre."""
        self._fallar(10)

        respuesta = self.client.post(
            reverse("users:login"),
            {"username": "operador", "password": "Original-2026"},
            REMOTE_ADDR="198.51.100.7",
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_el_recupero_deja_de_mandar_correos_al_pasarse_del_limite(self):
        url = reverse("users:recuperar_contrasena")
        for _ in range(5):
            self.client.post(url, {"email": self.usuario.email})
        self.assertEqual(len(mail.outbox), 5)

        respuesta = self.client.post(url, {"email": self.usuario.email})

        self.assertEqual(respuesta.status_code, 302)  # la pantalla no cambia: no revela nada
        self.assertEqual(len(mail.outbox), 5)


# --------------------------------------------------------------------------- #
# SEC-26 + D-26 — el token de la app y la clave del territorial
# --------------------------------------------------------------------------- #
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class TokenDeCampoYClaveDelTerritorialTests(_SinCubetas):
    def setUp(self):
        super().setUp()
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.rol_terr = _rol("Terr", ["becas.campo"], self.becas)
        self.territorial = _user("terri", self.rol_terr)
        self.api = APIClient()

    def _token(self, password=CLAVE):
        return self.api.post(reverse("becas_api:token"), {"username": "terri", "password": password})

    def test_cambiar_la_clave_no_cierra_la_sesion_de_la_app(self):
        """Ronda 2: la revocación automática dejaba varados los relevamientos.

        Contra la app instalada (`Chaco-mobile @ a66c2d3`) un 401 no es
        «reintentá»: `relevamientoService.js:1487` marca la operación
        `FAILED_PERMANENT` y `:1411`/`:1563` no la vuelven a tomar nunca, ni
        después de re-loguearse. Un territorial al que le resetean la clave perdía
        lo que el teléfono todavía no había subido, sin que nadie se entere. El
        token se borra ahora solo cuando alguien lo pide (ver
        `CerrarSesionDeLaAppTests`)."""
        clave = self._token().data["token"]
        self.api.credentials(HTTP_AUTHORIZATION=f"Token {clave}")
        self.assertEqual(self.api.get("/api/becas/relevamientos/").status_code, 200)

        self.territorial.set_password("Nueva-Clave-2026")
        self.territorial.save()

        self.assertEqual(self.api.get("/api/becas/relevamientos/").status_code, 200)
        self.assertTrue(Token.objects.filter(user=self.territorial).exists())

    def test_la_app_instalada_sigue_entrando_con_la_clave_nueva(self):
        """Contrato con `Chaco-mobile` a66c2d3: el login de la app manda
        `{username, password}` a `/api/becas/auth/token/` y espera `token`,
        `user_id` y `username`. Nada de eso cambia."""
        self.territorial.set_password("Nueva-Clave-2026")
        self.territorial.save()

        respuesta = self._token("Nueva-Clave-2026")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(set(respuesta.data), {"token", "user_id", "username"})

    def test_el_login_de_la_app_frena_tras_diez_intentos_fallidos(self):
        for _ in range(9):
            self._token("no-es")

        respuesta = self._token("tampoco")

        self.assertEqual(respuesta.status_code, 429)
        self.assertIn("Demasiados intentos", respuesta.data["detail"])

    def test_la_cubeta_del_token_no_deja_afuera_al_dueno_de_la_cuenta(self):
        """Mismo bloqueo por tercero que en el login web: con la clave correcta se
        entra siempre, porque la cubeta por usuario la llena cualquiera."""
        for _ in range(10):
            self._token("no-es")

        respuesta = self._token()

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("token", respuesta.data)

    def test_un_username_gigante_no_arma_una_clave_de_cache_gigante(self):
        """El usuario tipeado entraba entero en la clave de la caché: un POST con
        400 caracteres escribía una clave de 400 caracteres en Redis por intento.
        Se recorta a 150, que es el largo de `auth_user.username`."""
        largo = "x" * 400
        self.api.post(reverse("becas_api:token"), {"username": largo, "password": "no-es"})

        self.assertIsNotNone(cache.get("throttle:token_campo:" + "x" * 150))
        self.assertIsNone(cache.get("throttle:token_campo:" + largo))

    def test_la_cubeta_del_token_no_mira_la_ip(self):
        """Los territoriales salen por el NAT del operador móvil: una cubeta por IP
        le cerraría la app a una región entera."""
        otro = _user("terri2", self.rol_terr)
        for _ in range(10):
            self._token("no-es")

        respuesta = self.api.post(reverse("becas_api:token"), {"username": otro.username, "password": CLAVE})

        self.assertEqual(respuesta.status_code, 200)

    def test_el_alta_del_territorial_manda_un_link_y_no_una_clave_en_claro(self):
        """D-26 = (b). Al territorial el backoffice nunca le va a pedir que cambie la
        clave —el login web lo rechaza y la API no mira el flag—, así que la clave
        provisoria del correo le quedaba vigente para siempre."""
        from users.services.correo import ENTREGA_LINK, entregar_credenciales_provisorias

        peticion = self.client.request().wsgi_request

        modalidad = entregar_credenciales_provisorias(self.territorial, peticion)

        self.assertEqual(modalidad, ENTREGA_LINK)
        cuerpo = mail.outbox[0].body
        self.assertIn("/establecer-contrasena/", cuerpo)
        self.assertNotIn("Contraseña provisoria", cuerpo)
        self.assertNotIn("primer ingreso", cuerpo)

    def test_el_alta_de_un_usuario_de_backoffice_sigue_llevando_la_clave(self):
        from users.services.correo import ENTREGA_CLAVE, entregar_credenciales_provisorias

        operador = _user("operador", _rol("OpX", ["ciudadano.ver"]))
        peticion = self.client.request().wsgi_request

        modalidad = entregar_credenciales_provisorias(operador, peticion)

        self.assertEqual(modalidad, ENTREGA_CLAVE)
        cuerpo = mail.outbox[0].body
        self.assertIn("Contraseña provisoria", cuerpo)
        self.assertNotIn("/establecer-contrasena/", cuerpo)

    def test_el_link_limpia_la_marca_de_clave_provisoria(self):
        Profile.objects.filter(user=self.territorial).update(debe_cambiar_contrasena=True)

        url = reverse(
            "users:establecer_contrasena",
            kwargs={
                "uidb64": urlsafe_base64_encode(force_bytes(self.territorial.pk)),
                "token": default_token_generator.make_token(self.territorial),
            },
        )
        # La vista canjea el token por una URL con el token en sesión y recién ahí acepta el POST.
        destino = self.client.get(url)["Location"]
        respuesta = self.client.post(
            destino,
            {"new_password1": "Elegida-Por-Mi-2026", "new_password2": "Elegida-Por-Mi-2026"},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Profile.objects.get(user=self.territorial).debe_cambiar_contrasena)
        self.territorial.refresh_from_db()
        self.assertTrue(self.territorial.check_password("Elegida-Por-Mi-2026"))

    def test_el_territorial_sigue_sin_poder_entrar_al_backoffice(self):
        respuesta = self.client.post(reverse("users:login"), {"username": "terri", "password": CLAVE})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["form"].non_field_errors().as_data()[0].code, "territorial_mobile_only")

    def test_un_territorial_con_otra_capacidad_no_es_solo_campo(self):
        """El combo que decide D-26 es el mismo que el del login: si además tiene
        algo de backoffice, el circuito de la clave provisoria sí le aplica."""
        mixto = _user("mixto", self.rol_terr, _rol("OpX", ["ciudadano.ver"]))

        self.assertFalse(rbac.es_solo_campo(mixto))
        self.assertTrue(rbac.es_solo_campo(self.territorial))

    def test_el_alta_rapida_de_un_territorial_avisa_que_mando_el_link(self):
        from io import StringIO

        from django.core.management import call_command

        from programas.management.commands.seed_becas import ROL_TERRITORIAL

        call_command("seed_becas", stdout=StringIO())
        segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=5)
        admin = _user(
            "adm-becas",
            _rol(
                "AdmBecas",
                ["becas.programa.administrar", "programa.usuario.administrar"],
                self.becas,
            ),
        )
        self.assertTrue(Group.objects.filter(name=ROL_TERRITORIAL).exists())
        self.client.force_login(admin)

        respuesta = self.client.post(
            reverse("users:usuario_alta_rapida"),
            {
                "tipo": "territorial",
                "segmento_id": str(segmento.pk),
                "username": "terri-nuevo",
                "email": "terri-nuevo@x.test",
                "password": "",
                "first_name": "Terri",
                "last_name": "Nuevo",
            },
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertTrue(respuesta.json()["ok"], respuesta.json())
        self.assertIn("enlace para definir la contraseña", respuesta.json()["message"])


# --------------------------------------------------------------------------- #
# SEC-26 — «Cerrar sesión de la app»: la revocación, ahora explícita
# --------------------------------------------------------------------------- #
class CerrarSesionDeLaAppTests(_SinCubetas):
    def setUp(self):
        super().setUp()
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.disp = Programa.objects.create(codigo="DISPOSITIVOS", nombre="Dispositivos")
        self.rol_terr = _rol("Terr", ["becas.campo"], self.becas)
        self.territorial = _user("terri", self.rol_terr)
        Token.objects.create(user=self.territorial)
        self.adm_becas = _user("adm-becas", _rol("AdmBecas", ["programa.usuario.administrar"], self.becas))
        self.adm_disp = _user("adm-disp", _rol("AdmDisp", ["programa.usuario.administrar"], self.disp))
        self.url = reverse("users:usuario_cerrar_sesion_app", args=[self.territorial.pk])

    def test_la_accion_explicita_si_borra_el_token(self):
        self.client.force_login(self.adm_becas)

        respuesta = self.client.post(self.url)

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Token.objects.filter(user=self.territorial).exists())

    def test_un_admin_de_otro_programa_recibe_403_y_el_token_sigue_vivo(self):
        """El alcance es el de las credenciales (R0b-02/R0b-10): borrar el token es
        sobre la cuenta entera, no sobre los roles de un programa."""
        self.client.force_login(self.adm_disp)

        respuesta = self.client.post(self.url)

        self.assertEqual(respuesta.status_code, 403)
        self.assertTrue(Token.objects.filter(user=self.territorial).exists())

    def test_sin_capacidad_y_anonimo_no_cierran_nada(self):
        pelado = _user("pelado", _rol("OpX", ["ciudadano.ver"]))
        self.client.force_login(pelado)
        self.assertEqual(self.client.post(self.url).status_code, 302)

        self.client.logout()
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.assertTrue(Token.objects.filter(user=self.territorial).exists())

    def test_no_se_cierra_por_GET(self):
        self.client.force_login(self.adm_becas)

        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertTrue(Token.objects.filter(user=self.territorial).exists())

    def test_el_boton_aparece_solo_sobre_quien_tiene_sesion_en_la_app(self):
        sin_app = _user("terri-sin-app", self.rol_terr)
        self.client.force_login(self.adm_becas)

        respuesta = self.client.get(reverse("users:usuarios"))

        self.assertContains(respuesta, self.url)
        self.assertNotContains(respuesta, reverse("users:usuario_cerrar_sesion_app", args=[sin_app.pk]))

    def test_el_aviso_del_modal_dice_que_se_pierde_lo_no_sincronizado(self):
        self.client.force_login(self.adm_becas)

        respuesta = self.client.get(reverse("users:usuarios"))

        self.assertContains(respuesta, "no haya sincronizado van a quedar trabados en la app")


# --------------------------------------------------------------------------- #
# SEC-26 — techo por IP: lo que corta el password-spray
# --------------------------------------------------------------------------- #
@override_settings(
    AUTH_FALLIDOS_MAX_POR_IP=5,
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class TechoPorIpTests(_SinCubetas):
    """La cubeta por usuario no ve un barrido: cambia de usuario en cada intento y
    ninguna llega a 10. Lo que lo ve es el techo por IP, que acá se baja a 5 con el
    setting —que existe justamente para poder moverlo por entorno—."""

    ATACANTE = "203.0.113.9"

    def setUp(self):
        super().setUp()
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.rol_terr = _rol("Terr", ["becas.campo"], self.becas)
        self.territorial = _user("terri", self.rol_terr)
        self.operador = _user("operador", _rol("OpX", ["ciudadano.ver"]), password="Original-2026")
        self.api = APIClient()

    def test_el_login_web_corta_un_barrido_de_usuarios_distintos(self):
        for i in range(5):
            self.client.post(
                reverse("users:login"),
                {"username": f"victima-{i}", "password": "no-es"},
                REMOTE_ADDR=self.ATACANTE,
            )

        respuesta = self.client.post(
            reverse("users:login"),
            {"username": "operador", "password": "Original-2026"},
            REMOTE_ADDR=self.ATACANTE,
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["form"].non_field_errors().as_data()[0].code, "demasiados_intentos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_el_token_de_la_app_corta_un_barrido_de_usuarios_distintos(self):
        for i in range(5):
            self.api.post(
                reverse("becas_api:token"),
                {"username": f"victima-{i}", "password": "no-es"},
                REMOTE_ADDR=self.ATACANTE,
            )

        respuesta = self.api.post(
            reverse("becas_api:token"),
            {"username": "terri", "password": CLAVE},
            REMOTE_ADDR=self.ATACANTE,
        )

        self.assertEqual(respuesta.status_code, 429)
        self.assertIn("Demasiados intentos", respuesta.data["detail"])

    def test_el_techo_es_por_ip_y_no_toca_a_los_de_al_lado(self):
        """El argumento del NAT móvil se respeta por lo holgado del default (300),
        no por dejar la puerta sin techo: desde otra IP no cambia nada."""
        for i in range(5):
            self.api.post(
                reverse("becas_api:token"),
                {"username": f"victima-{i}", "password": "no-es"},
                REMOTE_ADDR=self.ATACANTE,
            )

        respuesta = self.api.post(
            reverse("becas_api:token"),
            {"username": "terri", "password": CLAVE},
            REMOTE_ADDR="198.51.100.7",
        )

        self.assertEqual(respuesta.status_code, 200)


# --------------------------------------------------------------------------- #
# G1b-08 + D-26 — cómo le llega la clave a un usuario de campo
# --------------------------------------------------------------------------- #
class AltaDeUsuarioDeCampoTests(_SinCubetas):
    def setUp(self):
        super().setUp()
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.rol_terr = _rol("Terr", ["becas.campo"], self.becas)
        self.rol_op = _rol("OpX", ["ciudadano.ver"])
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=5)
        self.root = _user("root-global", _rol("Admins", ["usuario.administrar"]))
        self.client.force_login(self.root)

    def _alta(self, **extra):
        datos = {
            "username": "nuevo",
            "email": "",
            "password": "Clave-Larguisima-2026",
            "first_name": "",
            "last_name": "",
            "groups": [str(self.rol_terr.pk)],
            "segmento_territorial": str(self.segmento.pk),
        }
        datos.update(extra)
        return self.client.post(reverse("users:usuario_crear"), datos)

    def test_el_alta_de_un_usuario_de_campo_sin_correo_se_rechaza(self):
        """D-26 (b): la clave se le entrega con un link de reseteo, y el link viaja
        por correo. Sin correo quedaba la que tipeó el operador —que la conoce— y
        vigente para siempre, porque a él el backoffice nunca le pide cambiarla:
        el login web lo rechaza y la API no mira `debe_cambiar_contrasena`."""
        respuesta = self._alta()

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("email", respuesta.context["form"].errors)
        self.assertFalse(User.objects.filter(username="nuevo").exists())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_con_correo_el_alta_de_campo_anda_y_manda_el_link(self):
        respuesta = self._alta(email="nuevo@x.test")

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(User.objects.filter(username="nuevo").exists())
        self.assertIn("/establecer-contrasena/", mail.outbox[0].body)

    def test_un_usuario_de_backoffice_sin_correo_sigue_pudiendo_darse_de_alta(self):
        """Para él la otra vía existe: la clave la tipea el operador y el primer
        ingreso se la hace cambiar (G1b-08). Nada de esto cambió."""
        respuesta = self._alta(groups=[str(self.rol_op.pk)])

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(User.objects.filter(username="nuevo").exists())

    def test_un_usuario_mixto_no_es_de_campo_y_no_necesita_correo(self):
        respuesta = self._alta(groups=[str(self.rol_terr.pk), str(self.rol_op.pk)])

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(User.objects.filter(username="nuevo").exists())

    def test_sin_correo_y_sin_clave_sigue_fallando_por_la_clave(self):
        respuesta = self._alta(groups=[str(self.rol_op.pk)], password="")

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("password", respuesta.context["form"].errors)


class EdicionHaciaUsuarioDeCampoTests(_SinCubetas):
    """La otra pantalla por la que se llegaba al estado que D-26 (b) cerró.

    El alta ya exige correo al usuario de campo, pero la edición no miraba nada: se
    daba de alta un **mixto** sin correo (legítimo) y después se le destildaba el rol
    que no era de campo. La cuenta quedaba solo-campo, sin correo y con la clave que
    tipeó el operador, vigente para siempre.
    """

    def setUp(self):
        super().setUp()
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.rol_terr = _rol("Terr", ["becas.campo"], self.becas)
        self.rol_op = _rol("OpX", ["ciudadano.ver"])
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=5)
        self.root = _user("root-global", _rol("Admins", ["usuario.administrar"]))
        self.client.force_login(self.root)

    def _crear(self, username, *grupos, email=""):
        usuario = User.objects.create_user(username, password=CLAVE)
        usuario.email = email
        usuario.save(update_fields=["email"])
        usuario.groups.set(grupos)
        return usuario

    def _editar(self, usuario, **extra):
        datos = {
            "username": usuario.username,
            "email": usuario.email,
            "password": "",
            "first_name": usuario.first_name,
            "last_name": usuario.last_name,
            "groups": [str(g.pk) for g in usuario.groups.all()],
            "segmento_territorial": str(self.segmento.pk),
        }
        datos.update(extra)
        return self.client.post(reverse("users:usuario_editar", args=[usuario.pk]), datos)

    def test_sacarle_el_rol_de_backoffice_a_un_mixto_sin_correo_se_rechaza(self):
        mixto = self._crear("mixto", self.rol_terr, self.rol_op)

        respuesta = self._editar(mixto, groups=[str(self.rol_terr.pk)])

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("email", respuesta.context["form"].errors)
        self.assertEqual(set(mixto.groups.all()), {self.rol_terr, self.rol_op})

    def test_la_misma_edicion_con_correo_pasa(self):
        mixto = self._crear("mixto2", self.rol_terr, self.rol_op)

        respuesta = self._editar(mixto, groups=[str(self.rol_terr.pk)], email="mixto2@x.test")

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(set(mixto.groups.all()), {self.rol_terr})

    def test_un_territorial_sin_correo_que_ya_existia_se_sigue_pudiendo_editar(self):
        """Los que se crearon antes de este cambio no quedan congelados: lo que se
        rechaza es *llegar* a solo-campo sin correo, no estar ahí."""
        viejo = self._crear("viejo", self.rol_terr)

        respuesta = self._editar(viejo, first_name="Juana")

        self.assertEqual(respuesta.status_code, 302)
        viejo.refresh_from_db()
        self.assertEqual(viejo.first_name, "Juana")

    def test_editar_un_usuario_de_backoffice_sin_correo_no_pide_clave(self):
        """La regla de la clave es del alta: en la edición el campo vacío significa
        «no la cambies» y la cuenta ya tiene una."""
        operador = self._crear("solo-backoffice", self.rol_op)

        respuesta = self._editar(operador, first_name="Ana")

        self.assertEqual(respuesta.status_code, 302)
        operador.refresh_from_db()
        self.assertEqual(operador.first_name, "Ana")
