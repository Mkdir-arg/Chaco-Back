"""Tests del paso 1 del formulario público de Becas (#293, análisis #289)."""

from datetime import date, timedelta
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from legajos.models import Ciudadano
from core.services.throttle import rate_limit_excedido
from portal.services import inscripcion as servicio


def _tolerar_render_local(exc):
    """Solo se tolera el bug conocido de ``Context.__copy__`` del test client con
    Python 3.14 + Django 4.2 (mensaje con ``dicts``). Cualquier otro
    ``AttributeError`` es un bug real y se re-lanza: uno de rate limit se
    escondió acá (revisión Cambio 40)."""
    if "dicts" not in str(exc):
        raise exc
from programas.models import Convocatoria, Formulario, Relevamiento, Segmento
from programas.services.padron import cargar_padron

DATOS_GRAN_BASE = {
    "success": True,
    "data": {
        "dni": "30123456",
        "nombre": "María Luján",
        "apellido": "Gómez",
        "fecha_nacimiento": "1991-03-14",
        "sexo": "F",
        "domicilio": "Av. Siempreviva 742",  # RN-P7: esto NUNCA debe viajar
    },
}


class _BaseInscripcionTest(TestCase):
    def setUp(self):
        cache.clear()
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas 2026",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = self._rel_publico()

    def _rel_publico(self, **extra):
        defaults = {
            "convocatoria": self.convocatoria,
            "tipo": Relevamiento.Tipo.PUBLICO,
            "fecha_asignada": timezone.now() - timedelta(days=1),
            "fecha_hasta": timezone.now() + timedelta(days=10),
        }
        defaults.update(extra)
        return Relevamiento.objects.create(**defaults)

    def _url(self, rel=None):
        rel = rel or self.relevamiento
        return reverse("portal:inscripcion_paso1", kwargs={"token": rel.token_publico})

    def _post_paso1(self, dni="30123456", sexo="F", captcha=None, rel=None):
        """Siembra el captcha en la sesión (evita el GET, que renderiza) y
        postea el paso 1 con la respuesta correcta salvo que se indique otra."""
        rel = rel or self.relevamiento
        session = self.client.session
        session[servicio.SESSION_KEY_CAPTCHA] = 7
        session[servicio.SESSION_KEY_CAPTCHA_PREGUNTA] = "¿Cuánto es 3 + 4?"
        session.save()
        return self.client.post(
            self._url(rel),
            {"dni": dni, "sexo": sexo, "captcha": captcha if captcha is not None else "7"},
        )


class ServiciosInscripcionTests(_BaseInscripcionTest):
    def test_disponibilidad(self):
        self.assertTrue(servicio.relevamiento_disponible(self.relevamiento))
        vencido = self._rel_publico(
            fecha_asignada=timezone.now() - timedelta(days=10), fecha_hasta=timezone.now() - timedelta(days=1)
        )
        self.assertFalse(servicio.relevamiento_disponible(vencido))
        pausado = self._rel_publico(pausado=True, pausa_motivo="x")
        self.assertFalse(servicio.relevamiento_disponible(pausado))
        lleno = self._rel_publico(cupo_maximo=1)
        Formulario.objects.create(
            relevamiento=lleno, celular="1", email_contacto="a@a.com", datos_identificacion={"dni": "1"}
        )
        self.assertFalse(servicio.relevamiento_disponible(lleno))
        finalizado = self._rel_publico()
        finalizado.estado = Relevamiento.Estado.FINALIZADO
        finalizado.save(update_fields=["estado"])
        self.assertFalse(servicio.relevamiento_disponible(finalizado))

    def test_duplicado_por_convocatoria_completa(self):
        territorial = User.objects.create_user("terr")
        rel_campo = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=territorial,
            fecha_asignada=date(2026, 6, 1),
            zona="Zona",
        )
        # Por identificación offline (formulario sin ciudadano resuelto).
        Formulario.objects.create(
            relevamiento=rel_campo, celular="1", email_contacto="a@a.com", datos_identificacion={"dni": "30123456"}
        )
        self.assertTrue(servicio.dni_ya_inscripto(self.convocatoria, "30123456"))
        # Por ciudadano resuelto.
        ciudadano = Ciudadano.objects.create(dni="28111222", nombre="A", apellido="B")
        Formulario.objects.create(relevamiento=rel_campo, celular="1", email_contacto="a@a.com", ciudadano=ciudadano)
        self.assertTrue(servicio.dni_ya_inscripto(self.convocatoria, "28111222"))
        # Otra convocatoria no bloquea (RN-P5 acota a la convocatoria).
        otra = Convocatoria.objects.create(
            nombre="Otra", segmento=self.segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.assertFalse(servicio.dni_ya_inscripto(otra, "30123456"))

    def test_rate_limit_por_ip(self):
        rf = RequestFactory()
        request = rf.post("/", REMOTE_ADDR="10.0.0.1")
        for _ in range(servicio.MAX_INTENTOS_IP):
            self.assertFalse(rate_limit_excedido(request, "inscripcion_paso1", servicio.MAX_INTENTOS_IP, servicio.VENTANA_SEGUNDOS))
        self.assertTrue(rate_limit_excedido(request, "inscripcion_paso1", servicio.MAX_INTENTOS_IP, servicio.VENTANA_SEGUNDOS))
        otra_ip = rf.post("/", REMOTE_ADDR="10.0.0.2")
        self.assertFalse(rate_limit_excedido(otra_ip, "inscripcion_paso1", servicio.MAX_INTENTOS_IP, servicio.VENTANA_SEGUNDOS))


class Paso1FlujoTests(_BaseInscripcionTest):
    def test_token_invalido_404(self):
        try:
            resp = self.client.get(reverse("portal:inscripcion_paso1", kwargs={"token": uuid4()}))
        except AttributeError as exc:
            _tolerar_render_local(exc)
            return
        self.assertEqual(resp.status_code, 404)

    @patch("portal.views.inscripcion.consultar_persona", return_value=DATOS_GRAN_BASE)
    def test_match_redirige_con_datos_basicos_en_sesion(self, mock_consulta):
        resp = self._post_paso1()
        self.assertRedirects(
            resp,
            reverse("portal:inscripcion_paso2", kwargs={"token": self.relevamiento.token_publico}),
            fetch_redirect_response=False,
        )
        mock_consulta.assert_called_once_with("30123456", "F")
        sesion = self.client.session[servicio.clave_sesion(self.relevamiento)]
        self.assertEqual(sesion["origen"], "personas")
        self.assertEqual(sesion["datos"]["nombre"], "María Luján")
        # RN-P7: solo datos básicos — el domicilio de Gran Base no viaja.
        self.assertNotIn("domicilio", sesion["datos"])

    @patch("portal.views.inscripcion.consultar_persona", return_value={"success": False, "not_found": True})
    def test_sin_match_avanza_como_manual(self, mock_consulta):
        resp = self._post_paso1()
        self.assertEqual(resp.status_code, 302)
        sesion = self.client.session[servicio.clave_sesion(self.relevamiento)]
        self.assertEqual(sesion["origen"], "manual")
        self.assertIsNone(sesion["datos"])

    @patch("portal.views.inscripcion.consultar_persona", return_value={"success": False, "fallecido": True})
    def test_fallecido_no_avanza(self, mock_consulta):
        try:
            self._post_paso1()
        except AttributeError as exc:
            _tolerar_render_local(exc)
        self.assertNotIn(servicio.clave_sesion(self.relevamiento), self.client.session)

    @patch("portal.views.inscripcion.consultar_persona")
    def test_captcha_incorrecto_no_consulta_identidad(self, mock_consulta):
        try:
            self._post_paso1(captcha="999")
        except AttributeError as exc:
            _tolerar_render_local(exc)
        mock_consulta.assert_not_called()
        self.assertNotIn(servicio.clave_sesion(self.relevamiento), self.client.session)

    @patch("portal.views.inscripcion.consultar_persona")
    def test_padron_bloquea_a_quien_no_figura_sin_consultar(self, mock_consulta):
        cargar_padron(self.relevamiento, None, [("28111222", "M")])
        try:
            self._post_paso1(dni="30123456", sexo="F")
        except AttributeError as exc:
            _tolerar_render_local(exc)
        mock_consulta.assert_not_called()
        self.assertNotIn(servicio.clave_sesion(self.relevamiento), self.client.session)

    @patch("portal.views.inscripcion.consultar_persona", return_value=DATOS_GRAN_BASE)
    def test_padron_deja_pasar_a_quien_figura_normalizado(self, mock_consulta):
        cargar_padron(self.relevamiento, None, [("30123456", "F")])
        resp = self._post_paso1(dni="30123456", sexo="F")
        self.assertEqual(resp.status_code, 302)
        mock_consulta.assert_called_once()

    @patch("portal.views.inscripcion.consultar_persona", return_value=DATOS_GRAN_BASE)
    def test_duplicado_en_convocatoria_no_avanza_ni_consulta(self, mock_consulta):
        Formulario.objects.create(
            relevamiento=self.relevamiento,
            celular="1",
            email_contacto="a@a.com",
            datos_identificacion={"dni": "30123456"},
        )
        try:
            self._post_paso1(dni="30123456", sexo="F")
        except AttributeError as exc:
            _tolerar_render_local(exc)
        mock_consulta.assert_not_called()
        self.assertNotIn(servicio.clave_sesion(self.relevamiento), self.client.session)

    @patch("portal.views.inscripcion.consultar_persona", return_value=DATOS_GRAN_BASE)
    def test_rate_limit_corta_sin_consultar(self, mock_consulta):
        with patch.object(servicio, "MAX_INTENTOS_IP", 0), patch(
            "portal.views.inscripcion.paso1_excedido", return_value=True
        ):
            try:
                self._post_paso1()
            except AttributeError as exc:
                _tolerar_render_local(exc)
        mock_consulta.assert_not_called()

    def test_paso2_sin_paso1_redirige(self):
        resp = self.client.get(reverse("portal:inscripcion_paso2", kwargs={"token": self.relevamiento.token_publico}))
        self.assertRedirects(resp, self._url(), fetch_redirect_response=False)

    def test_no_disponible_para_vencido(self):
        vencido = self._rel_publico(
            fecha_asignada=timezone.now() - timedelta(days=10), fecha_hasta=timezone.now() - timedelta(days=1)
        )
        try:
            resp = self.client.get(self._url(vencido))
        except AttributeError as exc:
            _tolerar_render_local(exc)
            return
        self.assertTemplateUsed(resp, "portal/inscripcion/no_disponible.html")
