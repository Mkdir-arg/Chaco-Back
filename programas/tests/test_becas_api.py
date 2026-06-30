"""Tests de la API REST de campo de Becas (#82)."""

from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APITestCase

from legajos.models import Ciudadano
from programas.management.commands.seed_becas import ROL_COORDINADOR, ROL_TERRITORIAL
from programas.models import (
    Convocatoria,
    Formulario,
    PreguntaGlobal,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    TipoCampo,
)


class _BaseApiTest(APITestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.seg = Segmento.objects.create(nombre="Seg", cupo_maximo=100, requiere_gps=True)
        self.conv = Convocatoria.objects.create(
            nombre="Conv", segmento=self.seg, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.terri = User.objects.create_user("terri", password="secret123")
        self.terri.groups.add(Group.objects.get(name=ROL_TERRITORIAL))
        self.terri2 = User.objects.create_user("terri2", password="secret123")
        self.terri2.groups.add(Group.objects.get(name=ROL_TERRITORIAL))

        self.rel = Relevamiento.objects.create(
            convocatoria=self.conv,
            territorial=self.terri,
            fecha_asignada=date(2026, 6, 1),
            zona="Centro",
        )
        self.rel_ajeno = Relevamiento.objects.create(
            convocatoria=self.conv,
            territorial=self.terri2,
            fecha_asignada=date(2026, 6, 1),
            zona="Otra",
        )

    def autenticar(self, user):
        from rest_framework.authtoken.models import Token

        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")


class TokenAuthTests(_BaseApiTest):
    def test_obtener_token_territorial(self):
        resp = self.client.post(
            reverse("becas_api:token"), {"username": "terri", "password": "secret123"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("token", resp.data)

    def test_token_denegado_sin_capacidad(self):
        coord = User.objects.create_user("coord", password="secret123")
        coord.groups.add(Group.objects.get(name=ROL_COORDINADOR))  # sin becas.campo
        resp = self.client.post(
            reverse("becas_api:token"), {"username": "coord", "password": "secret123"}, format="json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_sin_token_no_lista(self):
        resp = self.client.get(reverse("becas_api:relevamiento-list"))
        self.assertIn(resp.status_code, (401, 403))


class RelevamientoApiTests(_BaseApiTest):
    def test_lista_solo_propios(self):
        self.autenticar(self.terri)
        resp = self.client.get(reverse("becas_api:relevamiento-list"))
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in resp.data["results"]]
        self.assertIn(self.rel.id, ids)
        self.assertNotIn(self.rel_ajeno.id, ids)

    def test_detalle_incluye_definicion(self):
        PreguntaGlobal.objects.create(texto="Tenencia", tipo=TipoCampo.STRING, activo=True, orden=1)
        RequisitoNativo.objects.create(texto="Actividad", tipo=TipoCampo.STRING, segmento=self.seg, orden=1)
        self.autenticar(self.terri)
        resp = self.client.get(reverse("becas_api:relevamiento-detail", args=[self.rel.id]))
        self.assertEqual(resp.status_code, 200)
        definicion = resp.data["definicion_formulario"]
        self.assertTrue(definicion["requiere_gps"])
        self.assertTrue(any(g["texto"] == "Tenencia" for g in definicion["globales"]))
        self.assertTrue(any(r["texto"] == "Actividad" for r in definicion["requisitos"]))

    def test_no_accede_a_relevamiento_ajeno(self):
        self.autenticar(self.terri)
        resp = self.client.get(reverse("becas_api:relevamiento-detail", args=[self.rel_ajeno.id]))
        self.assertEqual(resp.status_code, 404)

    def test_iniciar_finalizar_reabrir(self):
        self.autenticar(self.terri)
        url_iniciar = reverse("becas_api:relevamiento-iniciar", args=[self.rel.id])
        self.assertEqual(self.client.post(url_iniciar).status_code, 200)
        self.rel.refresh_from_db()
        self.assertEqual(self.rel.estado, Relevamiento.Estado.EN_CURSO)

        url_finalizar = reverse("becas_api:relevamiento-finalizar", args=[self.rel.id])
        self.assertEqual(self.client.post(url_finalizar).status_code, 200)
        self.rel.refresh_from_db()
        self.assertEqual(self.rel.estado, Relevamiento.Estado.FINALIZADO)
        self.assertIsNotNone(self.rel.fecha_finalizado)

        url_reabrir = reverse("becas_api:relevamiento-reabrir", args=[self.rel.id])
        self.assertEqual(self.client.post(url_reabrir).status_code, 200)
        self.rel.refresh_from_db()
        self.assertEqual(self.rel.estado, Relevamiento.Estado.EN_CURSO)

    def test_iniciar_estado_invalido(self):
        self.rel.estado = Relevamiento.Estado.FINALIZADO
        self.rel.save()
        self.autenticar(self.terri)
        resp = self.client.post(reverse("becas_api:relevamiento-iniciar", args=[self.rel.id]))
        self.assertEqual(resp.status_code, 400)


class RenaperBecasApiTests(_BaseApiTest):
    def test_consultar_renaper_requiere_token(self):
        resp = self.client.post(
            reverse("becas_api:renaper-consultar"),
            {"dni": "40400400", "sexo": "M"},
            format="json",
        )
        self.assertIn(resp.status_code, (401, 403))

    @patch("programas.api.views.consultar_datos_renaper")
    def test_consultar_renaper_ok(self, mock_consultar):
        mock_consultar.return_value = {
            "success": True,
            "data": {
                "dni": "40400400",
                "nombre": "Juan",
                "apellido": "Perez",
                "fecha_nacimiento": "1990-01-02",
                "genero": "M",
            },
            "datos_api": {"raw": True},
        }
        self.autenticar(self.terri)
        resp = self.client.post(
            reverse("becas_api:renaper-consultar"),
            {"dni": "40400400", "sexo": "M"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["data"]["dni"], "40400400")
        self.assertEqual(resp.data["data"]["sexo"], "M")
        mock_consultar.assert_called_once_with("40400400", "M")

    @patch("programas.api.views.consultar_datos_renaper")
    def test_consultar_renaper_error_controlado(self, mock_consultar):
        mock_consultar.return_value = {"success": False, "error": "Servicio no disponible"}
        self.autenticar(self.terri)
        resp = self.client.post(
            reverse("becas_api:renaper-consultar"),
            {"dni": "40400400", "sexo": "F"},
            format="json",
        )
        self.assertEqual(resp.status_code, 502)
        self.assertFalse(resp.data["success"])
        self.assertEqual(resp.data["error"], "Servicio no disponible")

    def test_consultar_renaper_valida_dni_y_sexo(self):
        self.autenticar(self.terri)
        resp = self.client.post(
            reverse("becas_api:renaper-consultar"),
            {"dni": "40400400"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)


class FormularioSyncTests(_BaseApiTest):
    def test_crear_formulario_resuelve_ciudadano_nuevo(self):
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])
        resp = self.client.post(
            url,
            {
                "celular": "3624111222",
                "email_contacto": "x@y.com",
                "datos_identificacion": {"dni": "40400400", "nombre": "Juan", "apellido": "Pérez"},
                "data": {"globales": {}, "requisitos": {}},
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIsNotNone(resp.data["ciudadano"])
        self.assertIsNone(resp.data["datos_identificacion"])
        self.assertTrue(Ciudadano.objects.filter(dni="40400400").exists())

    def test_crear_formulario_escaneado_queda_validado_renaper(self):
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])
        resp = self.client.post(
            url,
            {
                "celular": "3624111222",
                "email_contacto": "x@y.com",
                "datos_identificacion": {
                    "dni": "41411411",
                    "nombre": "Maria",
                    "apellido": "Gomez",
                    "origen": "scan",
                },
                "data": {"globales": {}, "requisitos": {}},
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data["validado_renaper"])

    def test_crear_formulario_manual_no_queda_validado_renaper(self):
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])
        resp = self.client.post(
            url,
            {
                "celular": "3624111222",
                "email_contacto": "x@y.com",
                "validado_renaper": True,
                "datos_identificacion": {
                    "dni": "42422422",
                    "nombre": "Luis",
                    "apellido": "Rios",
                    "origen": "manual",
                },
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(resp.data["validado_renaper"])

    def test_crear_formulario_linkea_ciudadano_existente(self):
        existente = Ciudadano.objects.create(dni="50500500", nombre="Ana", apellido="López")
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])
        resp = self.client.post(
            url,
            {
                "celular": "3624111222",
                "email_contacto": "x@y.com",
                "datos_identificacion": {"dni": "50500500", "nombre": "OTRO", "apellido": "OTRO"},
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["ciudadano"], existente.id)
        existente.refresh_from_db()
        self.assertEqual(existente.nombre, "Ana")  # no se pisa

    def test_crear_formulario_sin_dni_falla(self):
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])
        resp = self.client.post(
            url, {"celular": "3624111222", "email_contacto": "x@y.com", "datos_identificacion": {}}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_listar_formularios_del_relevamiento(self):
        Formulario.objects.create(relevamiento=self.rel, celular="1", email_contacto="a@b.com")
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_actualizar_formulario(self):
        form = Formulario.objects.create(relevamiento=self.rel, celular="111", email_contacto="a@b.com")
        self.autenticar(self.terri)
        url = reverse("becas_api:formulario-detail", args=[form.id])
        resp = self.client.patch(url, {"celular": "999"}, format="json")
        self.assertEqual(resp.status_code, 200)
        form.refresh_from_db()
        self.assertEqual(form.celular, "999")
