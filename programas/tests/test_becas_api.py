"""Tests de la API REST de campo de Becas (#82)."""

from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
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
    Subsegmento,
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
            fecha_asignada=timezone.localdate(),
            zona="Centro",
        )
        self.rel_ajeno = Relevamiento.objects.create(
            convocatoria=self.conv,
            territorial=self.terri2,
            fecha_asignada=timezone.localdate(),
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
    def test_pausa_se_informa_y_bloquea_inicio(self):
        self.conv.pausado = True
        self.conv.pausa_motivo = "Operativo suspendido"
        self.conv.save(update_fields=["pausado", "pausa_motivo"])
        self.autenticar(self.terri)

        detalle = self.client.get(reverse("becas_api:relevamiento-detail", args=[self.rel.id]))
        inicio = self.client.post(reverse("becas_api:relevamiento-iniciar", args=[self.rel.id]), {}, format="json")

        self.assertTrue(detalle.data["pausado"])
        self.assertEqual(detalle.data["pausa_motivo"], "Operativo suspendido")
        self.assertEqual(inicio.status_code, 409)
        self.assertIn("Operativo suspendido", inicio.data["detail"])

    def test_lista_solo_propios(self):
        self.autenticar(self.terri)
        resp = self.client.get(reverse("becas_api:relevamiento-list"))
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in resp.data["results"]]
        self.assertIn(self.rel.id, ids)
        self.assertNotIn(self.rel_ajeno.id, ids)

    def test_lista_informa_la_localidad_asignada_sin_recibirla_del_mobile(self):
        localidad = Subsegmento.objects.create(
            segmento=self.seg,
            nombre="Localidad Norte",
            cupo_maximo=50,
        )
        self.conv.subsegmento = localidad
        self.conv.save(update_fields=["subsegmento", "modificado"])
        self.autenticar(self.terri)

        resp = self.client.get(reverse("becas_api:relevamiento-list"))

        self.assertEqual(resp.status_code, 200)
        propio = next(item for item in resp.data["results"] if item["id"] == self.rel.id)
        self.assertEqual(propio["localidad"], "Localidad Norte")

    def test_lista_incluye_relevamientos_vigentes_y_futuros(self):
        vencido = Relevamiento.objects.create(
            convocatoria=self.conv,
            territorial=self.terri,
            fecha_asignada=timezone.localdate() - timedelta(days=1),
            zona="Vencida",
        )
        futuro = Relevamiento.objects.create(
            convocatoria=self.conv,
            territorial=self.terri,
            fecha_asignada=timezone.localdate() + timedelta(days=1),
            zona="Futura",
        )
        self.autenticar(self.terri)

        resp = self.client.get(reverse("becas_api:relevamiento-list"))

        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in resp.data["results"]]
        self.assertIn(self.rel.id, ids)
        self.assertNotIn(vencido.id, ids)
        self.assertIn(futuro.id, ids)

        propio = next(item for item in resp.data["results"] if item["id"] == self.rel.id)
        self.assertIn("T", propio["fecha_asignada"])
        self.assertRegex(propio["fecha_asignada"], r"(Z|[+-]\d{2}:\d{2})$")

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

    def test_detalle_identifica_requisito_de_subsegmento_sin_depender_del_orden(self):
        subsegmento = Subsegmento.objects.create(
            segmento=self.seg,
            nombre="Sub",
            cupo_maximo=50,
        )
        self.conv.subsegmento = subsegmento
        self.conv.save(update_fields=["subsegmento", "modificado"])
        requisito_segmento = RequisitoNativo.objects.create(
            texto="Actividad",
            tipo=TipoCampo.STRING,
            segmento=self.seg,
            orden=1,
        )
        requisito_subsegmento = RequisitoNativo.objects.create(
            texto="Tipo de actividad",
            tipo=TipoCampo.STRING,
            segmento=self.seg,
            subsegmento=subsegmento,
            orden=1,
        )
        self.autenticar(self.terri)

        resp = self.client.get(reverse("becas_api:relevamiento-detail", args=[self.rel.id]))

        self.assertEqual(resp.status_code, 200)
        requisitos = {requisito["id"]: requisito for requisito in resp.data["definicion_formulario"]["requisitos"]}
        self.assertEqual(requisitos[requisito_segmento.id]["alcance"], "segmento")
        self.assertIsNone(requisitos[requisito_segmento.id]["subsegmento_id"])
        self.assertEqual(requisitos[requisito_subsegmento.id]["alcance"], "subsegmento")
        self.assertEqual(
            requisitos[requisito_subsegmento.id]["subsegmento_id"],
            subsegmento.id,
        )

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

    def test_no_permite_iniciar_relevamiento_fuera_de_fecha(self):
        self.rel.fecha_asignada = timezone.localdate() - timedelta(days=1)
        self.rel.fecha_hasta = self.rel.fecha_asignada
        self.rel.save(update_fields=["fecha_asignada", "fecha_hasta"])
        self.autenticar(self.terri)

        resp = self.client.post(reverse("becas_api:relevamiento-iniciar", args=[self.rel.id]))

        self.assertEqual(resp.status_code, 400)
        self.assertIn("período asignado", resp.data["detail"])

    def test_permite_sincronizar_dias_despues_un_inicio_capturado_en_fecha(self):
        capturado_en = timezone.now() - timedelta(days=3)
        self.rel.fecha_asignada = timezone.localdate(capturado_en)
        self.rel.save(update_fields=["fecha_asignada", "modificado"])
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-iniciar", args=[self.rel.id])

        primera = self.client.post(url, {"capturado_en": capturado_en.isoformat()}, format="json")
        segunda = self.client.post(url, {"capturado_en": capturado_en.isoformat()}, format="json")

        self.assertEqual(primera.status_code, 200)
        self.assertEqual(segunda.status_code, 200)
        self.rel.refresh_from_db()
        self.assertEqual(self.rel.estado, Relevamiento.Estado.EN_CURSO)


class PersonasBecasApiTests(_BaseApiTest):
    def test_consultar_persona_requiere_token(self):
        resp = self.client.post(
            reverse("becas_api:personas-consultar"),
            {"dni": "40400400", "sexo": "M"},
            format="json",
        )
        self.assertIn(resp.status_code, (401, 403))

    @patch("programas.services.identidad.consultar_persona")
    def test_consultar_persona_ok(self, mock_consultar):
        mock_consultar.return_value = {
            "success": True,
            "data": {
                "dni": "40400400",
                "nombre": "Juan",
                "apellido": "Perez",
                "fecha_nacimiento": "1990-01-02",
                "sexo": "M",
            },
            "datos_api": {"raw": True},
        }
        self.autenticar(self.terri)
        resp = self.client.post(
            reverse("becas_api:personas-consultar"),
            {"dni": "40400400", "sexo": "M"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["data"]["dni"], "40400400")
        self.assertEqual(resp.data["data"]["sexo"], "M")
        mock_consultar.assert_called_once_with("40400400", "M")

    @patch("programas.services.identidad.consultar_persona")
    def test_consultar_persona_error_controlado(self, mock_consultar):
        mock_consultar.return_value = {"success": False, "error": "Servicio no disponible"}
        self.autenticar(self.terri)
        resp = self.client.post(
            reverse("becas_api:personas-consultar"),
            {"dni": "40400400", "sexo": "F"},
            format="json",
        )
        self.assertEqual(resp.status_code, 502)
        self.assertFalse(resp.data["success"])
        self.assertEqual(resp.data["error"], "Servicio no disponible")

    @patch("programas.services.identidad.consultar_persona")
    def test_consultar_persona_no_encontrada_devuelve_404(self, mock_consultar):
        mock_consultar.return_value = {
            "success": False,
            "not_found": True,
            "error": "El DNI no fue encontrado en Base de Personas.",
        }
        self.autenticar(self.terri)
        resp = self.client.post(
            reverse("becas_api:personas-consultar"),
            {"dni": "48433496", "sexo": "M"},
            format="json",
        )
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(resp.data["success"])

    def test_consultar_persona_valida_dni(self):
        self.autenticar(self.terri)
        resp = self.client.post(
            reverse("becas_api:personas-consultar"),
            {},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)


class FormularioSyncTests(_BaseApiTest):
    def setUp(self):
        super().setUp()
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])

    def _payload_persona(self, fecha_nacimiento, **apoderado):
        return {
            "celular": "3624111222",
            "email_contacto": "x@y.com",
            "datos_identificacion": {
                "dni": "60600600",
                "nombre": "Persona",
                "apellido": "Prueba",
                "fecha_nacimiento": fecha_nacimiento.isoformat(),
            },
            **apoderado,
        }

    def test_cupo_cuenta_toda_persona_y_bloquea_nuevas_cargas(self):
        self.rel.cupo_maximo = 1
        self.rel.save(update_fields=["cupo_maximo", "modificado"])
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])

        primera = self.client.post(
            url,
            {
                "client_uuid": "11111111-1111-4111-8111-111111111111",
                "celular": "3624111222",
                "email_contacto": "x@y.com",
                "datos_identificacion": {"dni": "40111111", "nombre": "Uno", "apellido": "Cupo"},
            },
            format="json",
        )
        segunda = self.client.post(
            url,
            {
                "client_uuid": "22222222-2222-4222-8222-222222222222",
                "celular": "3624111222",
                "email_contacto": "x@y.com",
                "datos_identificacion": {"dni": "40222222", "nombre": "Dos", "apellido": "Cupo"},
            },
            format="json",
        )

        self.assertEqual(primera.status_code, 201)
        self.assertEqual(segunda.status_code, 409)
        self.assertEqual(segunda.data["code"], "CUPO_RELEVAMIENTO_COMPLETO")
        self.assertEqual(self.rel.formularios.count(), 1)

    def test_reintento_idempotente_no_falla_cuando_el_cupo_esta_completo(self):
        self.rel.cupo_maximo = 1
        self.rel.save(update_fields=["cupo_maximo", "modificado"])
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])
        payload = {
            "client_uuid": "33333333-3333-4333-8333-333333333333",
            "celular": "3624111222",
            "email_contacto": "x@y.com",
            "datos_identificacion": {"dni": "40333333", "nombre": "Tres", "apellido": "Cupo"},
        }

        primera = self.client.post(url, payload, format="json")
        reintento = self.client.post(url, payload, format="json")

        self.assertEqual(primera.status_code, 201)
        self.assertEqual(reintento.status_code, 200)
        self.assertEqual(primera.data["id"], reintento.data["id"])
        self.assertEqual(self.rel.formularios.count(), 1)

    def test_no_permite_cargar_persona_si_el_relevamiento_sigue_asignado(self):
        self.rel.estado = Relevamiento.Estado.ASIGNADO
        self.rel.save(update_fields=["estado", "modificado"])
        self.autenticar(self.terri)

        resp = self.client.post(
            reverse("becas_api:relevamiento-formularios", args=[self.rel.id]),
            {
                "celular": "3624111222",
                "email_contacto": "x@y.com",
                "datos_identificacion": {"dni": "40400400"},
                "data": {"globales": {}, "requisitos": {}},
            },
            format="json",
        )

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data["detail"], "Solo se pueden cargar personas en un relevamiento en curso.")

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

    def test_crear_formulario_validado_por_personas_queda_validado(self):
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])
        resp = self.client.post(
            url,
            {
                "celular": "3624111222",
                "email_contacto": "x@y.com",
                "datos_identificacion": {
                    "dni": "41422422",
                    "nombre": "Maria",
                    "apellido": "Gomez",
                    "origen": "personas",
                },
                "data": {"globales": {}, "requisitos": {}},
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data["validado_renaper"])

    def test_personas_sin_nombre_y_apellido_completos_no_valida(self):
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])
        resp = self.client.post(
            url,
            {
                "celular": "3624111222",
                "email_contacto": "x@y.com",
                "datos_identificacion": {
                    "dni": "41433433",
                    "nombre": "",
                    "apellido": "IBAÑEZ LUCAS SEBASTIAN",
                    "origen": "personas",
                },
                "data": {"globales": {}, "requisitos": {}},
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(resp.data["validado_renaper"])

    def test_correccion_manual_de_respuesta_incompleta_no_valida(self):
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])
        resp = self.client.post(
            url,
            {
                "celular": "3624111222",
                "email_contacto": "x@y.com",
                "datos_identificacion": {
                    "dni": "41444444",
                    "nombre": "Lucas Sebastian",
                    "apellido": "Ibañez",
                    "origen": "personas_incompleta",
                },
                "data": {"globales": {}, "requisitos": {}},
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(resp.data["validado_renaper"])

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

    def test_origen_desconocido_no_puede_autovalidarse(self):
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])
        resp = self.client.post(
            url,
            {
                "celular": "3624111222",
                "email_contacto": "x@y.com",
                "validado_renaper": True,
                "datos_identificacion": {
                    "dni": "43433433",
                    "nombre": "Luis",
                    "apellido": "Rios",
                    "origen": "otro",
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

    def test_menor_sin_apoderado_falla(self):
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])
        nacimiento = date(date.today().year - 10, 1, 1)

        resp = self.client.post(url, self._payload_persona(nacimiento), format="json")

        self.assertEqual(resp.status_code, 400)
        self.assertIn("apoderado_nombre", resp.data)
        self.assertIn("apoderado_apellido", resp.data)
        self.assertIn("apoderado_dni", resp.data)
        self.assertIn("apoderado_genero", resp.data)
        self.assertIn("apoderado_fecha_nacimiento", resp.data)

    def test_menor_con_apoderado_completo_se_acepta(self):
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])
        nacimiento = date(date.today().year - 10, 1, 1)
        payload = self._payload_persona(
            nacimiento,
            apoderado_nombre="Ana",
            apoderado_apellido="Pérez",
            apoderado_dni="27111222",
            apoderado_genero="F",
            apoderado_fecha_nacimiento="1985-05-10",
        )

        resp = self.client.post(url, payload, format="json")

        self.assertEqual(resp.status_code, 201)
        formulario = Formulario.objects.get(pk=resp.data["id"])
        self.assertIsNotNone(formulario.apoderado_ciudadano_id)
        self.assertEqual(formulario.apoderado_ciudadano.dni, "27111222")
        self.assertEqual(formulario.apoderado_ciudadano.genero, "F")

    def test_menor_vincula_apoderado_existente_sin_pisar_sus_datos(self):
        existente = Ciudadano.objects.create(
            dni="27111333",
            nombre="Nombre existente",
            apellido="Apellido existente",
            fecha_nacimiento=date(1980, 1, 1),
            genero="F",
        )
        self.autenticar(self.terri)
        nacimiento = date(date.today().year - 10, 1, 1)
        payload = self._payload_persona(
            nacimiento,
            apoderado_nombre="OTRO",
            apoderado_apellido="OTRO",
            apoderado_dni=existente.dni,
            apoderado_genero="F",
            apoderado_fecha_nacimiento="1985-05-10",
        )
        resp = self.client.post(
            reverse("becas_api:relevamiento-formularios", args=[self.rel.id]), payload, format="json"
        )
        self.assertEqual(resp.status_code, 201)
        formulario = Formulario.objects.get(pk=resp.data["id"])
        self.assertEqual(formulario.apoderado_ciudadano_id, existente.id)
        existente.refresh_from_db()
        self.assertEqual(existente.nombre, "Nombre existente")

    def test_mayor_sin_apoderado_se_acepta(self):
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])
        nacimiento = date(date.today().year - 20, 1, 1)

        resp = self.client.post(url, self._payload_persona(nacimiento), format="json")

        self.assertEqual(resp.status_code, 201)

    def test_listar_formularios_del_relevamiento(self):
        ciudadano = Ciudadano.objects.create(
            dni="12345678",
            nombre="Nombre",
            apellido="Visible",
            fecha_nacimiento=date(1990, 1, 1),
        )
        Formulario.objects.create(
            relevamiento=self.rel,
            ciudadano=ciudadano,
            celular="1",
            email_contacto="a@b.com",
        )
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        formulario = resp.data["results"][0]
        self.assertEqual(formulario["ciudadano_nombre"], "Nombre")
        self.assertEqual(formulario["ciudadano_apellido"], "Visible")

    def test_actualizar_formulario(self):
        form = Formulario.objects.create(relevamiento=self.rel, celular="111", email_contacto="a@b.com")
        self.autenticar(self.terri)
        url = reverse("becas_api:formulario-detail", args=[form.id])
        resp = self.client.patch(url, {"celular": "999"}, format="json")
        self.assertEqual(resp.status_code, 200)
        form.refresh_from_db()
        self.assertEqual(form.celular, "999")

    def test_no_permite_crear_formulario_fuera_de_fecha(self):
        self.rel.fecha_asignada = timezone.localdate() - timedelta(days=1)
        self.rel.fecha_hasta = self.rel.fecha_asignada
        self.rel.save(update_fields=["fecha_asignada", "fecha_hasta"])
        self.autenticar(self.terri)

        resp = self.client.post(
            reverse("becas_api:relevamiento-formularios", args=[self.rel.id]),
            {
                "celular": "3624111222",
                "email_contacto": "offline@demo.local",
                "datos_identificacion": {"dni": "40400400"},
                "data": {"globales": {}, "requisitos": {}},
            },
            format="json",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("fuera del período", resp.data["detail"])

    def test_permite_sincronizar_despues_una_captura_hecha_en_fecha(self):
        capturado_en = timezone.now() - timedelta(days=1)
        self.rel.fecha_asignada = timezone.localdate(capturado_en)
        self.rel.save(update_fields=["fecha_asignada"])
        client_uuid = uuid4()
        self.autenticar(self.terri)

        resp = self.client.post(
            reverse("becas_api:relevamiento-formularios", args=[self.rel.id]),
            {
                "client_uuid": str(client_uuid),
                "capturado_en": capturado_en.isoformat(),
                "celular": "3624111222",
                "email_contacto": "offline@demo.local",
                "datos_identificacion": {"dni": "40400400"},
                "data": {"globales": {}, "requisitos": {}},
            },
            format="json",
        )

        self.assertEqual(resp.status_code, 201)
        formulario = Formulario.objects.get(client_uuid=client_uuid)
        self.assertEqual(formulario.relevamiento, self.rel)
        self.assertEqual(timezone.localdate(formulario.capturado_en), timezone.localdate(self.rel.fecha_asignada))

    def test_reintento_con_mismo_uuid_no_duplica_formulario(self):
        client_uuid = uuid4()
        payload = {
            "client_uuid": str(client_uuid),
            "capturado_en": timezone.now().isoformat(),
            "celular": "3624111222",
            "email_contacto": "offline@demo.local",
            "datos_identificacion": {"dni": "40400400"},
            "data": {"globales": {}, "requisitos": {}},
        }
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])

        primera = self.client.post(url, payload, format="json")
        segunda = self.client.post(url, payload, format="json")

        self.assertEqual(primera.status_code, 201)
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(primera.data["id"], segunda.data["id"])
        self.assertEqual(Formulario.objects.filter(client_uuid=client_uuid).count(), 1)

    def test_conserva_segunda_carga_del_dni_como_conflicto_para_backoffice(self):
        payload = {
            "capturado_en": timezone.now().isoformat(),
            "celular": "3624111222",
            "email_contacto": "offline@demo.local",
            "datos_identificacion": {"dni": "40400400"},
            "data": {"globales": {}, "requisitos": {}},
        }
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])

        primera = self.client.post(url, {**payload, "client_uuid": str(uuid4())}, format="json")
        Formulario.objects.filter(pk=primera.data["id"]).update(estado=Formulario.Estado.RECHAZADO)
        segunda = self.client.post(url, {**payload, "client_uuid": str(uuid4())}, format="json")

        self.assertEqual(primera.status_code, 201)
        self.assertEqual(segunda.status_code, 201)
        conflicto = Formulario.objects.get(pk=segunda.data["id"])
        self.assertTrue(conflicto.conflicto_duplicado)
        self.assertFalse(conflicto.conflicto_resuelto)
        self.assertEqual(conflicto.duplicado_de_id, primera.data["id"])
        self.assertEqual(Formulario.objects.filter(relevamiento=self.rel).count(), 2)

    def test_permite_el_mismo_dni_en_otro_relevamiento(self):
        otro = Relevamiento.objects.create(
            convocatoria=self.conv,
            territorial=self.terri,
            fecha_asignada=timezone.localdate(),
            zona="Otra zona",
            estado=Relevamiento.Estado.EN_CURSO,
        )
        payload = {
            "capturado_en": timezone.now().isoformat(),
            "celular": "3624111222",
            "email_contacto": "offline@demo.local",
            "datos_identificacion": {"dni": "40400400"},
            "data": {"globales": {}, "requisitos": {}},
        }
        self.autenticar(self.terri)

        primera = self.client.post(
            reverse("becas_api:relevamiento-formularios", args=[self.rel.id]),
            {**payload, "client_uuid": str(uuid4())},
            format="json",
        )
        segunda = self.client.post(
            reverse("becas_api:relevamiento-formularios", args=[otro.id]),
            {**payload, "client_uuid": str(uuid4())},
            format="json",
        )

        self.assertEqual(primera.status_code, 201)
        self.assertEqual(segunda.status_code, 201)

    def test_consulta_dni_existente_no_expone_estado(self):
        ciudadano = Ciudadano.objects.create(dni="40400400", nombre="Juan", apellido="Perez")
        Formulario.objects.create(
            relevamiento=self.rel,
            ciudadano=ciudadano,
            estado=Formulario.Estado.RECHAZADO,
            celular="3624111222",
            email_contacto="offline@demo.local",
        )
        self.autenticar(self.terri)

        resp = self.client.get(
            reverse("becas_api:relevamiento-dni-existe", args=[self.rel.id]),
            {"dni": "40.400.400"},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, {"existe": True})

    def test_no_permite_actualizar_formulario_fuera_de_fecha(self):
        form = Formulario.objects.create(relevamiento=self.rel, celular="111", email_contacto="a@b.com")
        self.rel.fecha_asignada = timezone.localdate() - timedelta(days=1)
        self.rel.fecha_hasta = self.rel.fecha_asignada
        self.rel.save(update_fields=["fecha_asignada", "fecha_hasta"])
        self.autenticar(self.terri)

        resp = self.client.patch(
            reverse("becas_api:formulario-detail", args=[form.id]),
            {"celular": "999"},
            format="json",
        )

        self.assertEqual(resp.status_code, 400)
        form.refresh_from_db()
        self.assertEqual(form.celular, "111")


class AdjuntoValidacionTests(_BaseApiTest):
    """La API aceptaba cualquier archivo, de cualquier peso.

    ``/media/`` lo sirve nginx sin pasar por Django, asi que un ``.html`` o un
    ``.svg`` subido por ahi se ejecutaria en el origen del sitio.
    """

    def setUp(self):
        super().setUp()
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])
        self.formulario = Formulario.objects.create(
            relevamiento=self.rel,
            celular="3624111222",
            email_contacto="x@y.com",
        )
        self.pregunta = PreguntaGlobal.objects.create(texto="Foto del DNI", tipo=TipoCampo.ARCHIVO, orden=900)
        self.autenticar(self.terri)

    def _subir(self, archivo):
        return self.client.post(
            reverse("becas_api:formulario-adjuntos", args=[self.formulario.pk]),
            {"pregunta_global": self.pregunta.pk, "archivo": archivo},
            format="multipart",
        )

    def test_acepta_una_foto(self):
        resp = self._subir(SimpleUploadedFile("dni.jpg", b"datos", content_type="image/jpeg"))
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_acepta_los_formatos_de_camara_de_telefono(self):
        for nombre in ("dni.heic", "dni.webp", "dni.PNG"):
            with self.subTest(nombre=nombre):
                resp = self._subir(SimpleUploadedFile(nombre, b"datos"))
                self.assertEqual(resp.status_code, 201, resp.data)

    def test_rechaza_contenido_ejecutable(self):
        for nombre in ("payload.html", "payload.svg", "payload.js"):
            with self.subTest(nombre=nombre):
                resp = self._subir(SimpleUploadedFile(nombre, b"<script>alert(1)</script>"))
                self.assertEqual(resp.status_code, 400)
                self.assertIn("archivo", resp.data)

    def test_rechaza_un_archivo_de_mas_de_5_mb(self):
        grande = SimpleUploadedFile("dni.jpg", b"0" * (5 * 1024 * 1024 + 1), content_type="image/jpeg")
        resp = self._subir(grande)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("5 MB", str(resp.data))
