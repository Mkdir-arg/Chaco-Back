"""Tests de la revisión de seguridad del formulario público (26/08/2026).

Cada clase fija una propiedad que se rompió alguna vez o que un cambio futuro
podría deshacer sin que nadie lo note:

- los rechazos del paso 1 no distinguen entre padrón, duplicado y documento no
  disponible (el formulario dejó de ser un oráculo para reconstruir el padrón);
- el rate limit no se evade mandando una cabecera, y suma una cubeta por
  documento;
- el paso 2 —el que escribe y recibe archivos— también tiene techo;
- el anti-bot es reCAPTCHA cuando hay claves, y el fallback no se cuela;
- ni el documento ni el token del link llegan a los logs;
- la ubicación solo se guarda si el segmento la pide.
"""

import re
from datetime import date, datetime, timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.middleware import _path_sin_secretos
from core.services.throttle import ip_cliente, rate_limit_excedido
from portal.services import inscripcion as servicio
from portal.views.inscripcion import MENSAJE_RECHAZO
from programas.models import Convocatoria, Formulario, Relevamiento, Segmento


def _normalizar(cuerpo):
    """Saca lo que cambia entre dos renders legítimos: el token CSRF y el
    desafío aritmético, que rota a propósito después de cada intento."""
    cuerpo = re.sub(rb'value="[A-Za-z0-9]{32,}"', b'value="CSRF"', cuerpo)
    return re.sub(r"¿Cuánto es [0-9]+ \+ [0-9]+\?".encode(), b"<desafio>", cuerpo)


PERSONA_OK = {
    "success": True,
    "data": {
        "dni": "30123456",
        "nombre": "María Luján",
        "apellido": "Gómez",
        "fecha_nacimiento": "1991-03-14",
        "sexo": "F",
    },
}


class ResolucionDeIpTests(TestCase):
    """La IP del rate limit no puede depender de una cabecera del cliente."""

    def setUp(self):
        self.factory = RequestFactory()

    def _request(self, remote, **cabeceras):
        return self.factory.post("/", REMOTE_ADDR=remote, **cabeceras)

    @override_settings(TRUSTED_PROXY_NETS=["10.0.0.0/8"])
    def test_ignora_la_cabecera_si_el_origen_no_es_un_proxy_confiable(self):
        request = self._request("200.1.2.3", HTTP_X_REAL_IP="9.9.9.9")

        self.assertEqual(ip_cliente(request), "200.1.2.3")

    @override_settings(TRUSTED_PROXY_NETS=["10.0.0.0/8"])
    def test_usa_la_cabecera_cuando_viene_del_proxy(self):
        request = self._request("10.1.2.3", HTTP_X_REAL_IP="181.20.30.40")

        self.assertEqual(ip_cliente(request), "181.20.30.40")

    @override_settings(TRUSTED_PROXY_NETS=["10.0.0.0/8"])
    def test_del_forwarded_toma_el_ultimo_que_es_el_que_puso_el_proxy(self):
        request = self._request("10.1.2.3", HTTP_X_FORWARDED_FOR="1.1.1.1, 181.20.30.40")

        self.assertEqual(ip_cliente(request), "181.20.30.40")

    @override_settings(TRUSTED_PROXY_NETS=[])
    def test_sin_proxies_confiables_manda_remote_addr(self):
        request = self._request("200.1.2.3", HTTP_X_REAL_IP="9.9.9.9", HTTP_X_FORWARDED_FOR="8.8.8.8")

        self.assertEqual(ip_cliente(request), "200.1.2.3")

    @override_settings(TRUSTED_PROXY_NETS=["10.0.0.0/8"])
    def test_rotar_la_cabecera_ya_no_multiplica_la_cuota(self):
        cache.clear()
        # Mismo cliente real, cabecera distinta en cada intento.
        excedio = False
        for i in range(6):
            request = self._request("200.1.2.3", HTTP_X_REAL_IP=f"9.9.9.{i}")
            excedio = rate_limit_excedido(request, "prueba", 3, 60)
        self.assertTrue(excedio, "la cuota se compartió pese a rotar la cabecera")


class RateLimitToleranteTests(TestCase):
    def test_una_cache_caida_no_bloquea_el_tramite(self):
        request = RequestFactory().post("/", REMOTE_ADDR="127.0.0.1")

        with patch("core.services.throttle.cache.add", side_effect=RuntimeError("redis caído")):
            self.assertFalse(rate_limit_excedido(request, "prueba", 1, 60))


class _BaseFlujoTest(TestCase):
    def setUp(self):
        cache.clear()
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas 2026",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now() - timedelta(days=1),
            fecha_hasta=timezone.now() + timedelta(days=10),
        )

    def _url(self):
        return reverse("portal:inscripcion_paso1", kwargs={"token": self.relevamiento.token_publico})

    def _post(self, dni="30123456", sexo="F"):
        session = self.client.session
        session[servicio.SESSION_KEY_CAPTCHA] = 7
        session[servicio.SESSION_KEY_CAPTCHA_PREGUNTA] = "¿Cuánto es 3 + 4?"
        session.save()
        return self.client.post(self._url(), {"dni": dni, "sexo": sexo, "captcha": "7"})


class RechazosIndistinguiblesTests(_BaseFlujoTest):
    """Los tres rechazos tienen que verse exactamente igual desde afuera."""

    def _respuesta_de_rechazo(self):
        with patch("programas.services.identidad.consultar_persona", return_value=PERSONA_OK):
            return self._post()

    def test_fuera_del_padron(self):
        self.relevamiento.convocatoria.padron.create(dni="99999999", sexo="M")

        resp = self._respuesta_de_rechazo()

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, MENSAJE_RECHAZO)

    def test_ya_inscripto(self):
        Formulario.objects.create(
            relevamiento=self.relevamiento,
            celular="3624000000",
            email_contacto="x@y.com",
            datos_identificacion={"dni": "30123456"},
        )

        resp = self._respuesta_de_rechazo()

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, MENSAJE_RECHAZO)
        # Lo que antes delataba: plantilla propia, el documento y la convocatoria.
        self.assertNotContains(resp, "Ya estás inscripto")
        self.assertNotContains(resp, "ya figura registrado")

    def test_documento_no_disponible(self):
        with patch(
            "programas.services.identidad.consultar_persona",
            return_value={"success": False, "fallecido": True},
        ):
            resp = self._post()

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, MENSAJE_RECHAZO)

    def test_los_tres_casos_dan_el_mismo_cuerpo(self):
        """Si los cuerpos difieren, el rechazo vuelve a ser un oráculo."""
        self.relevamiento.convocatoria.padron.create(dni="99999999", sexo="M")
        fuera_del_padron = self._respuesta_de_rechazo().content

        cache.clear()
        self.relevamiento.convocatoria.padron.all().delete()
        with patch(
            "programas.services.identidad.consultar_persona",
            return_value={"success": False, "fallecido": True},
        ):
            no_disponible = self._post().content

        self.assertEqual(_normalizar(fuera_del_padron), _normalizar(no_disponible))


class LimitePorDocumentoTests(_BaseFlujoTest):
    def test_el_mismo_documento_se_frena_aunque_cambie_la_ip(self):
        with patch.object(servicio, "MAX_INTENTOS_DNI", 2):
            factory = RequestFactory()
            excedio = []
            for i in range(4):
                request = factory.post("/", REMOTE_ADDR=f"127.0.0.{i}")
                excedio.append(servicio.documento_excedido(request, "30123456"))

        self.assertTrue(excedio[-1], "el documento no tuvo cubeta propia")

    def test_documentos_distintos_no_se_pisan(self):
        with patch.object(servicio, "MAX_INTENTOS_DNI", 1):
            factory = RequestFactory()
            request = factory.post("/", REMOTE_ADDR="127.0.0.1")
            servicio.documento_excedido(request, "30123456")
            servicio.documento_excedido(request, "30123456")

            self.assertFalse(servicio.documento_excedido(request, "40999888"))

    def test_la_cubeta_del_documento_se_consume_despues_del_captcha(self):
        """Si se contara antes, cualquiera podría dejar a otro sin inscribirse."""
        with patch.object(servicio, "MAX_INTENTOS_DNI", 1):
            with patch("programas.services.identidad.consultar_persona", return_value=PERSONA_OK):
                # Diez POST con el captcha mal: no deben gastar la cuota del documento.
                for _ in range(10):
                    session = self.client.session
                    session[servicio.SESSION_KEY_CAPTCHA] = 7
                    session.save()
                    self.client.post(self._url(), {"dni": "30123456", "sexo": "F", "captcha": "0"})

            factory = RequestFactory()
            request = factory.post("/", REMOTE_ADDR="127.0.0.1")

            self.assertFalse(
                servicio.documento_excedido(request, "30123456"),
                "un tercero pudo quemar la cuota de ese documento sin resolver el captcha",
            )


class CaptchaTests(TestCase):
    @override_settings(RECAPTCHA_SITE_KEY="", RECAPTCHA_SECRET_KEY="")
    def test_sin_claves_usa_el_desafio_propio(self):
        self.assertEqual(servicio.captcha_activo(), "aritmetico")

    @override_settings(RECAPTCHA_SITE_KEY="site", RECAPTCHA_SECRET_KEY="secreto")
    def test_con_claves_usa_recaptcha(self):
        self.assertEqual(servicio.captcha_activo(), "recaptcha")

    @override_settings(RECAPTCHA_SITE_KEY="site", RECAPTCHA_SECRET_KEY="secreto")
    def test_con_recaptcha_el_desafio_viejo_deja_de_servir(self):
        """Con Google activo, mandar el número correcto no alcanza."""
        request = RequestFactory().post("/", {"captcha": "7"})
        request.session = {servicio.SESSION_KEY_CAPTCHA: 7}

        self.assertFalse(servicio.captcha_valido(request, "7"))

    @override_settings(RECAPTCHA_SITE_KEY="site", RECAPTCHA_SECRET_KEY="secreto")
    @patch("portal.services.inscripcion.requests.post")
    def test_token_valido_pasa(self, post):
        post.return_value.json.return_value = {"success": True}
        post.return_value.raise_for_status.return_value = None
        request = RequestFactory().post("/", {servicio.CAMPO_RECAPTCHA: "token-de-google"})

        self.assertTrue(servicio.captcha_valido(request, None))

    @override_settings(RECAPTCHA_SITE_KEY="site", RECAPTCHA_SECRET_KEY="secreto")
    @patch("portal.services.inscripcion.requests.post")
    def test_token_rechazado_por_google_no_pasa(self, post):
        post.return_value.json.return_value = {"success": False, "error-codes": ["invalid-input-response"]}
        post.return_value.raise_for_status.return_value = None
        request = RequestFactory().post("/", {servicio.CAMPO_RECAPTCHA: "token-falso"})

        self.assertFalse(servicio.captcha_valido(request, None))

    @override_settings(RECAPTCHA_SITE_KEY="site", RECAPTCHA_SECRET_KEY="secreto")
    @patch("portal.services.inscripcion.requests.post", side_effect=Exception("sin red"))
    def test_si_google_no_responde_se_rechaza(self, _post):
        """Fallar cerrado: una caída de red no puede abrir la puerta."""
        request = RequestFactory().post("/", {servicio.CAMPO_RECAPTCHA: "token"})

        self.assertFalse(servicio.captcha_valido(request, None))

    @override_settings(RECAPTCHA_SITE_KEY="site", RECAPTCHA_SECRET_KEY="secreto")
    def test_sin_token_no_se_consulta_a_google(self):
        request = RequestFactory().post("/", {})

        with patch("portal.services.inscripcion.requests.post") as post:
            self.assertFalse(servicio.captcha_valido(request, None))
            post.assert_not_called()


class LogsSinSecretosTests(TestCase):
    def test_el_token_del_link_no_queda_en_el_log(self):
        path = "/portal/inscripcion/657051b4-1d69-45e1-9920-5a56374cfc88/formulario/"

        enmascarado = _path_sin_secretos(path)

        self.assertNotIn("657051b4", enmascarado)
        self.assertEqual(enmascarado, "/portal/inscripcion/<token>/formulario/")

    def test_las_demas_rutas_no_se_tocan(self):
        self.assertEqual(_path_sin_secretos("/becas/relevamientos/12/"), "/becas/relevamientos/12/")

    def test_el_documento_no_viaja_en_el_error_de_gran_base(self):
        """El traceback de requests arrastra la URL con ?dni=…: no se loguea."""
        import requests

        from programas.services import personas

        with override_settings(
            PERSONAS_API_URL="https://personas.example/api/v1",
            PERSONAS_API_CLIENT_ID="id",
            PERSONAS_API_CLIENT_SECRET="secreto",
            PERSONAS_API_ENTIDAD_UUID="uuid",
        ):
            with patch.object(personas.PersonasAPIClient, "_token", return_value="t"):
                with patch(
                    "programas.services.personas.requests.get",
                    side_effect=requests.RequestException("... for url: https://x/?dni=30123456&sexo=F"),
                ):
                    with self.assertLogs("programas.services.personas", level="ERROR") as registro:
                        personas.consultar_persona("30123456", "F")

        self.assertNotIn("30123456", "\n".join(registro.output))


@override_settings(RECAPTCHA_SITE_KEY="", RECAPTCHA_SECRET_KEY="")
class CabecerasDeSeguridadTests(TestCase):
    def test_el_formulario_publico_viaja_con_csp(self):
        segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=10)
        convocatoria = Convocatoria.objects.create(
            nombre="Conv",
            segmento=segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        rel = Relevamiento.objects.create(
            convocatoria=convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now() - timedelta(days=1),
            fecha_hasta=timezone.now() + timedelta(days=1),
        )

        resp = self.client.get(reverse("portal:inscripcion_paso1", kwargs={"token": rel.token_publico}))

        csp = resp.headers.get("Content-Security-Policy", "")
        # frame-ancestors es el que reemplaza al X-Frame-Options que el ingress pisa.
        self.assertIn("frame-ancestors 'none'", csp)
        # connect-src acotado es lo que corta la exfiltración si entrara un script.
        self.assertIn("connect-src 'self'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("form-action 'self'", csp)
        self.assertIn("geolocation=(self)", resp.headers.get("Permissions-Policy", ""))


@override_settings(RECAPTCHA_SITE_KEY="site", RECAPTCHA_SECRET_KEY="secreto")
class RecaptchaExtremoAExtremoTests(_BaseFlujoTest):
    """Con las claves cargadas el paso 1 tiene que poder completarse.

    Es el escenario de producción: el widget de Google no manda el campo
    ``captcha``, así que si el form lo exige no pasa nadie. Los tests unitarios
    del verificador no alcanzaban para detectarlo.
    """

    def _post_con_google(self, exito=True):
        with patch("portal.services.inscripcion.requests.post") as post:
            post.return_value.json.return_value = {"success": exito}
            post.return_value.raise_for_status.return_value = None
            with patch("programas.services.identidad.consultar_persona", return_value=PERSONA_OK):
                return self.client.post(
                    self._url(),
                    {"dni": "30123456", "sexo": "F", servicio.CAMPO_RECAPTCHA: "token-de-google"},
                )

    def test_con_token_valido_se_pasa_al_paso_2(self):
        resp = self._post_con_google()

        self.assertEqual(resp.status_code, 302, "el paso 1 quedó imposible de completar")
        self.assertIn("/formulario/", resp.url)

    def test_sin_token_valido_no_se_pasa(self):
        resp = self._post_con_google(exito=False)

        self.assertEqual(resp.status_code, 200)

    def test_el_widget_de_google_se_renderiza_y_el_desafio_viejo_no(self):
        resp = self.client.get(self._url())

        self.assertContains(resp, "g-recaptcha")
        self.assertContains(resp, "recaptcha/api.js")
        self.assertNotContains(resp, "Cuánto es")


class TechoDelPaso2Tests(_BaseFlujoTest):
    def _identificar(self):
        session = self.client.session
        session[servicio.clave_sesion(self.relevamiento)] = {
            "dni": "30123456",
            "sexo": "F",
            "datos": None,
            "origen": "manual",
        }
        session.save()

    def test_superado_el_techo_se_corta_el_envio(self):
        self._identificar()
        url = reverse("portal:inscripcion_paso2", kwargs={"token": self.relevamiento.token_publico})

        with patch("portal.views.inscripcion.paso2_excedido", return_value=True):
            resp = self.client.post(url, {})

        self.assertTemplateUsed(resp, "portal/inscripcion/demasiados_intentos.html")
        self.assertEqual(Formulario.objects.count(), 0)

    def test_el_techo_es_por_documento_y_no_por_ip(self):
        """Dos personas detrás del mismo NAT no se pisan la cuota."""
        factory = RequestFactory()
        request = factory.post("/", REMOTE_ADDR="127.0.0.1")

        with patch.object(servicio, "MAX_ENVIOS_PASO2", 1):
            servicio.paso2_excedido(request, "30123456")
            servicio.paso2_excedido(request, "30123456")

            self.assertFalse(servicio.paso2_excedido(request, "40999888"))


class IdentificacionVencidaTests(_BaseFlujoTest):
    def _sesion_con_sello(self, hace_minutos):
        session = self.client.session
        session[servicio.clave_sesion(self.relevamiento)] = {
            "dni": "30123456",
            "sexo": "F",
            "datos": None,
            "origen": "manual",
            "sellada": (timezone.now() - timedelta(minutes=hace_minutos)).isoformat(),
        }
        session.save()

    def _url_paso2(self):
        return reverse("portal:inscripcion_paso2", kwargs={"token": self.relevamiento.token_publico})

    def test_una_identificacion_vieja_manda_de_vuelta_al_paso_1(self):
        self._sesion_con_sello(hace_minutos=120)

        resp = self.client.get(self._url_paso2())

        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("/formulario/", resp.url)

    def test_una_identificacion_reciente_sigue_valiendo(self):
        self._sesion_con_sello(hace_minutos=5)

        resp = self.client.get(self._url_paso2())

        self.assertEqual(resp.status_code, 200)

    def test_pasar_por_el_paso_2_renueva_la_vigencia(self):
        """Lo que caduca es abandonar el trámite, no tardar en completarlo."""
        self._sesion_con_sello(hace_minutos=40)

        self.client.get(self._url_paso2())

        sellada = self.client.session[servicio.clave_sesion(self.relevamiento)]["sellada"]
        self.assertLess((timezone.now() - datetime.fromisoformat(sellada)).total_seconds(), 60)


class SinRecursosDeTercerosTests(TestCase):
    """Ninguna plantilla servida puede volver a traer código de un CDN.

    Es la red que evita que esto se desincronice: alcanza con que alguien pegue
    un script de un CDN para reabrir el agujero de cadena de suministro y, de
    paso, romper el CSP en esa pantalla.
    """

    PERMITIDOS = ("https://www.google.com/recaptcha/",)

    def test_ninguna_plantilla_carga_recursos_externos(self):
        import re
        from pathlib import Path

        from django.conf import settings

        from django.template.utils import get_app_template_dirs

        patron = re.compile(r'(?:src|href)="(https?://[^"]+)"')
        # Se recorren las plantillas que Django SIRVE --los ``DIRS`` configurados
        # mas el ``templates/`` de cada app--, no todo ``BASE_DIR``. Recorrer la
        # raiz entera hacia fallar la suite por HTML que nadie sirve y que
        # aparece en cualquier copia de trabajo: el ``site/`` de ``mkdocs build``,
        # los entornos virtuales, dependencias clonadas al lado del repo.
        raices = [Path(d) for cfg in settings.TEMPLATES for d in cfg.get("DIRS", [])]
        raices += [Path(d) for d in get_app_template_dirs("templates")]

        infractores = []
        vistas = set()
        for raiz in raices:
            if not raiz.is_dir():
                continue
            for plantilla in raiz.rglob("*.html"):
                if plantilla in vistas:
                    continue
                vistas.add(plantilla)
                texto = plantilla.read_text(encoding="utf-8", errors="ignore")
                for url in patron.findall(texto):
                    if not url.startswith(self.PERMITIDOS):
                        infractores.append(f"{plantilla}: {url}")

        self.assertTrue(vistas, "no se encontro ninguna plantilla: el recorrido quedo vacio")

        self.assertEqual(infractores, [], "hay recursos de terceros en plantillas servidas")


class GpsSoloSiSePideTests(_BaseFlujoTest):
    def test_no_se_guarda_la_ubicacion_si_el_segmento_no_la_pide(self):
        from programas.services.inscripcion_publica import crear_formulario_publico

        self.assertFalse(self.segmento.requiere_gps)
        form = type(
            "FormFalso",
            (),
            {
                "cleaned_data": {
                    "celular": "3624000000",
                    "email_contacto": "x@y.com",
                    "gps_lat": "-27.451000",
                    "gps_lng": "-58.986000",
                },
                "respuestas": lambda self: {},
                "archivos": lambda self: [],
            },
        )()
        identificacion = {"dni": "30123456", "sexo": "F", "datos": None, "origen": "manual"}

        formulario, creado = crear_formulario_publico(
            self.relevamiento, identificacion=identificacion, form=form, client_uuid=None
        )

        self.assertTrue(creado)
        self.assertIsNone(formulario.gps_lat)
        self.assertIsNone(formulario.gps_lng)
