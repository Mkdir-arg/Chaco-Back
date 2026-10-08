"""Tests de la API REST de campo de Becas (#82)."""

from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from legajos.models import Ciudadano
from programas.api.views import ConsultaPersonasThrottle, _actualizar_validacion_identidad
from programas.management.commands.seed_becas import ROL_COORDINADOR, ROL_TERRITORIAL
from programas.models import (
    AdjuntoFormulario,
    Convocatoria,
    Formulario,
    PreguntaGlobal,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    Subsegmento,
    TipoCampo,
)
from programas.services import campo as servicio_campo


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

    # RED-25 (auditoría oct-2026): hasta acá la capacidad `becas.campo` solo se
    # probaba en el **login** de la app. Los tres viewsets montan además
    # `SessionAuthentication`, así que una sesión de backoffice entra por la
    # misma puerta: borrar el `and puede(user, CAP)` de `CampoBecasPermission`
    # dejaba el oráculo de identidad RENAPER/Personas abierto a todo el
    # personal sin que fallara ningún test (mutación M11).

    def _coordinador(self):
        """Usuario de backoffice real, con rol y sin `becas.campo`."""
        coord = User.objects.create_user("coord", password="secret123")
        coord.groups.add(Group.objects.get(name=ROL_COORDINADOR))
        return coord

    def test_sesion_de_backoffice_sin_becas_campo_no_lista(self):
        self.client.force_login(self._coordinador())

        resp = self.client.get(reverse("becas_api:relevamiento-list"))

        self.assertEqual(resp.status_code, 403)

    @patch("programas.services.identidad.consultar_persona")
    def test_sesion_de_backoffice_sin_becas_campo_no_consulta_persona(self, mock_consultar):
        self.client.force_login(self._coordinador())

        resp = self.client.post(
            reverse("becas_api:personas-consultar"),
            {"dni": "40400400", "sexo": "M"},
            format="json",
        )

        self.assertEqual(resp.status_code, 403)
        mock_consultar.assert_not_called()

    def test_token_sin_capacidad_revocada_no_opera(self):
        """El Token no caduca al sacarle el rol al usuario: la capacidad se
        tiene que mirar en cada request, no solo al emitirlo."""
        self.autenticar(self.terri)
        self.assertEqual(self.client.get(reverse("becas_api:relevamiento-list")).status_code, 200)

        self.terri.groups.clear()

        resp = self.client.get(reverse("becas_api:relevamiento-list"))
        self.assertEqual(resp.status_code, 403)


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
        ids = [r["id"] for r in resp.data]
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
        propio = next(item for item in resp.data if item["id"] == self.rel.id)
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
        ids = [r["id"] for r in resp.data]
        self.assertIn(self.rel.id, ids)
        self.assertNotIn(vencido.id, ids)
        self.assertIn(futuro.id, ids)

        propio = next(item for item in resp.data if item["id"] == self.rel.id)
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

    # --- Particiones de estado de las tres transiciones de la app (RED-66) ----
    #
    # Las tres recorren el enum completo: un estado nuevo entra solo al recorrido
    # y hay que decidir explícitamente de qué lado cae. El camino feliz lo cubre
    # `test_iniciar_finalizar_reabrir`; lo que faltaba era el negativo, que es lo
    # que sostiene el contrato con la app móvil (Cambio 54: «su `reabrir` sigue
    # aceptando solo FINALIZADO») y la decisión «EN_REVISION no vuelve a campo
    # por la app».

    def _poner_estado(self, estado):
        Relevamiento.objects.filter(pk=self.rel.pk).update(estado=estado)
        self.rel.refresh_from_db()

    def test_no_reabre_un_relevamiento_que_no_este_finalizado(self):
        """RED-66: neutralizar la guarda de `reabrir` no rompía ningún test, y
        deja al territorial devolver a campo un relevamiento que el cron ya
        mandó a EN_REVISION (o uno TERMINADO, con reportes emitidos)."""
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-reabrir", args=[self.rel.id])

        for estado in Relevamiento.Estado:
            with self.subTest(estado=estado):
                self._poner_estado(estado)

                resp = self.client.post(url)

                self.rel.refresh_from_db()
                if estado == Relevamiento.Estado.FINALIZADO:
                    self.assertEqual(resp.status_code, 200)
                    self.assertEqual(self.rel.estado, Relevamiento.Estado.EN_CURSO)
                    self.assertIsNone(self.rel.fecha_finalizado)
                else:
                    self.assertEqual(resp.status_code, 400)
                    self.assertEqual(resp.data["detail"], "Solo se puede reabrir un relevamiento finalizado.")
                    self.assertEqual(self.rel.estado, estado)

    def test_iniciar_solo_sale_de_asignado_y_es_idempotente_en_curso(self):
        """RED-66: el mismo recorrido para `iniciar`. EN_CURSO devuelve 200 sin
        mover nada (la app reintenta el inicio tras un corte de red); el resto
        de los estados son 400."""
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-iniciar", args=[self.rel.id])

        for estado in Relevamiento.Estado:
            with self.subTest(estado=estado):
                self._poner_estado(estado)

                resp = self.client.post(url)

                self.rel.refresh_from_db()
                if estado == Relevamiento.Estado.ASIGNADO:
                    self.assertEqual(resp.status_code, 200)
                    self.assertEqual(self.rel.estado, Relevamiento.Estado.EN_CURSO)
                elif estado == Relevamiento.Estado.EN_CURSO:
                    self.assertEqual(resp.status_code, 200)
                    self.assertEqual(self.rel.estado, Relevamiento.Estado.EN_CURSO)
                else:
                    self.assertEqual(resp.status_code, 400)
                    self.assertEqual(resp.data["detail"], "Solo se puede iniciar un relevamiento asignado.")
                    self.assertEqual(self.rel.estado, estado)

    def test_finalizar_solo_sale_de_en_curso_o_finalizando(self):
        """RED-66: el mismo recorrido para `finalizar`. FINALIZANDO (la ventana
        de sincronización tardía) también cierra; ASIGNADO y TERMINADO no.

        G1-04 cambió una celda de esta tabla: un relevamiento **ya cerrado**
        (FINALIZADO o EN_REVISION) dentro de la gracia responde 200 sin tocar
        nada, en vez de 400. La cola offline sube primero las personas y después
        el «finalizar»; el 400 lo dejaba `FAILED_PERMANENT` en el teléfono y le
        mostraba un error al territorial por algo que ya estaba hecho.
        """
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-finalizar", args=[self.rel.id])
        cierran = {Relevamiento.Estado.EN_CURSO, Relevamiento.Estado.FINALIZANDO}
        # Idempotentes dentro de la gracia: ya están cerrados.
        ya_cerrados = {Relevamiento.Estado.FINALIZADO, Relevamiento.Estado.EN_REVISION}

        for estado in Relevamiento.Estado:
            with self.subTest(estado=estado):
                Relevamiento.objects.filter(pk=self.rel.pk).update(estado=estado, fecha_finalizado=None)
                self.rel.refresh_from_db()

                resp = self.client.post(url)

                self.rel.refresh_from_db()
                if estado in cierran:
                    self.assertEqual(resp.status_code, 200)
                    self.assertEqual(self.rel.estado, Relevamiento.Estado.FINALIZADO)
                    self.assertIsNotNone(self.rel.fecha_finalizado)
                elif estado in ya_cerrados:
                    self.assertEqual(resp.status_code, 200)
                    self.assertEqual(self.rel.estado, estado)
                    self.assertIsNone(self.rel.fecha_finalizado)
                else:
                    self.assertEqual(resp.status_code, 400)
                    self.assertEqual(resp.data["detail"], "El relevamiento no está en curso.")
                    self.assertEqual(self.rel.estado, estado)
                    self.assertIsNone(self.rel.fecha_finalizado)

    def test_finalizar_un_relevamiento_cerrado_hace_mucho_sigue_dando_400(self):
        """La idempotencia de arriba vale **dentro de la gracia**: pasadas las
        24 h del cierre, un `finalizar` sobre un relevamiento ya cerrado vuelve
        a ser lo que siempre fue, un error."""
        self.autenticar(self.terri)
        fin = timezone.now() - timedelta(days=4)
        Relevamiento.objects.filter(pk=self.rel.pk).update(
            estado=Relevamiento.Estado.EN_REVISION,
            fecha_asignada=timezone.now() - timedelta(days=5),
            fecha_hasta=fin,
        )

        resp = self.client.post(
            reverse("becas_api:relevamiento-finalizar", args=[self.rel.id]),
            {"capturado_en": (fin - timedelta(hours=1)).isoformat()},
            format="json",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["detail"], "El relevamiento no está en curso.")

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

    # RED-03 (auditoría oct-2026): las ramas de error de las transiciones no se
    # ejecutaban en ningún test. Un `capturado_en` malformado que pase de 400 a
    # 500 deja a la app en bucle de sincronización.
    #
    # El estado de origen de `iniciar`, `finalizar` y `reabrir` lo recorre
    # entero RED-66 (Cambio 120), acá arriba: esos tres `subTest` sobre todo el
    # enum subsumen los casos sueltos que este PR había escrito.

    def test_una_fecha_de_captura_invalida_da_400_en_iniciar_y_en_finalizar(self):
        """La app sincroniza con `capturado_en`; si manda basura, 400 con el
        campo señalado —nunca un 500 que la deje reintentando—."""
        self.autenticar(self.terri)

        for accion in ("iniciar", "finalizar"):
            for valor in ("ayer", "2026-13-45T99:99:99"):
                with self.subTest(accion=accion, capturado_en=valor):
                    resp = self.client.post(
                        reverse(f"becas_api:relevamiento-{accion}", args=[self.rel.id]),
                        {"capturado_en": valor},
                        format="json",
                    )

                    self.assertEqual(resp.status_code, 400, resp.data)
                    self.assertEqual(resp.data["capturado_en"], "La fecha de captura no es válida.")

        self.rel.refresh_from_db()
        self.assertEqual(self.rel.estado, Relevamiento.Estado.ASIGNADO)

    def test_dni_existe_sin_dni_da_400(self):
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-dni-existe", args=[self.rel.id])

        for params in ({}, {"dni": ""}, {"dni": "   "}, {"dni": "sin-numeros"}):
            with self.subTest(params=params):
                resp = self.client.get(url, params)

                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertEqual(resp.data["dni"], "El DNI es requerido.")


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

    # RED-37: la validación manual pasó a `ConsultaPersonaSerializer` (para que
    # el esquema publique el `requestBody`). Lo que sigue fija el contrato que
    # la app en producción ya usa: mismo cuerpo de error, y las mismas entradas
    # aceptadas (DNI con puntos, sexo en minúscula, `relevamiento` vacío).
    CUERPOS_RECHAZADOS = (
        {},
        {"dni": "40400400"},
        {"sexo": "M"},
        {"dni": "", "sexo": "M"},
        {"dni": "sin-digitos", "sexo": "M"},
        {"dni": "40400400", "sexo": "X"},
        {"dni": "40400400", "sexo": ""},
    )

    def test_consultar_persona_rechaza_con_el_cuerpo_de_siempre(self):
        self.autenticar(self.terri)

        for cuerpo in self.CUERPOS_RECHAZADOS:
            with self.subTest(cuerpo=cuerpo):
                resp = self.client.post(reverse("becas_api:personas-consultar"), cuerpo, format="json")

                self.assertEqual(resp.status_code, 400)
                self.assertEqual(
                    resp.data,
                    {"success": False, "error": "DNI y sexo (F o M) son requeridos."},
                )

    @patch("programas.services.identidad.consultar_persona")
    def test_consultar_persona_sigue_normalizando_dni_y_sexo(self, mock_consultar):
        mock_consultar.return_value = {
            "success": True,
            "data": {"dni": "40400400", "nombre": "Juan", "apellido": "Perez", "sexo": "M"},
            "datos_api": {},
        }
        self.autenticar(self.terri)

        resp = self.client.post(
            reverse("becas_api:personas-consultar"),
            # La app vieja manda el relevamiento vacío: siempre significó
            # "todos los vigentes del territorial", no un 400.
            {"dni": "40.400.400", "sexo": " m ", "relevamiento": ""},
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["data"]["dni"], "40400400")
        self.assertEqual(resp.data["data"]["sexo"], "M")
        mock_consultar.assert_called_once_with("40400400", "M")

    # `relevamiento` es el único campo cuyo trato cambió al pasar la validación
    # al serializer, así que queda fijado entero. Lo vacío siempre significó
    # «todos los vigentes del territorial» y se conserva; lo que no es un id
    # entero ahora da el 400 de siempre en vez de un 500 (`true` y `1.9` antes
    # colaban como id 1 por la coerción del ORM, y `"abc"` reventaba en
    # `filter(pk=...)`).
    #
    # La app no manda el campo: `Chaco-mobile/src/screens/RelevamientoDetailScreen.js`
    # tiene el único POST al endpoint y su cuerpo es `{dni, sexo}`. Si una
    # versión futura empieza a mandarlo, mandará el id entero.
    RELEVAMIENTOS_RECHAZADOS = (True, 1.9, "abc", [1])

    def test_consultar_persona_rechaza_un_relevamiento_que_no_es_un_id(self):
        self.autenticar(self.terri)

        for valor in self.RELEVAMIENTOS_RECHAZADOS:
            with self.subTest(relevamiento=valor):
                resp = self.client.post(
                    reverse("becas_api:personas-consultar"),
                    {"dni": "40400400", "sexo": "M", "relevamiento": valor},
                    format="json",
                )

                self.assertEqual(resp.status_code, 400)
                self.assertEqual(
                    resp.data,
                    {"success": False, "error": "DNI y sexo (F o M) son requeridos."},
                )

    @patch("programas.services.identidad.consultar_persona")
    def test_consultar_persona_acepta_el_relevamiento_vacio_o_ausente(self, mock_consultar):
        mock_consultar.return_value = {
            "success": True,
            "data": {"dni": "40400400", "nombre": "Juan", "apellido": "Perez", "sexo": "M"},
            "datos_api": {},
        }
        self.autenticar(self.terri)

        for valor in ({}, {"relevamiento": ""}, {"relevamiento": None}, {"relevamiento": self.rel.id}):
            with self.subTest(extra=valor):
                resp = self.client.post(
                    reverse("becas_api:personas-consultar"),
                    {"dni": "40400400", "sexo": "M", **valor},
                    format="json",
                )

                self.assertEqual(resp.status_code, 200)

    # SEC-04 (auditoría oct-2026): al retirar la consulta RENAPER anónima de
    # Legajos, el alias que la app usa en producción tiene que quedar intacto y
    # seguir exigiendo token. `personas/consultar/` ya lo cubre
    # `test_consultar_persona_requiere_token`, arriba.
    @patch("programas.services.identidad.consultar_persona")
    def test_alias_renaper_becas_sigue_autenticado(self, mock_consultar):
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
        url = reverse("becas_api:renaper-consultar")
        self.assertEqual(url, "/api/becas/renaper/consultar/")

        anonimo = self.client.post(url, {"dni": "40400400", "sexo": "M"}, format="json")
        self.assertIn(anonimo.status_code, (401, 403))

        self.autenticar(self.terri)
        resp = self.client.post(url, {"dni": "40400400", "sexo": "M"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["data"]["dni"], "40400400")
        # El alias no filtra el payload crudo del servicio externo.
        self.assertEqual(resp.data["datos_api"], {})


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

    @patch("programas.services.identidad.consultar_persona")
    def test_crear_formulario_validado_por_personas_queda_validado(self, mock_consultar):
        """SEC-24: sigue quedando validado, pero porque **el servidor** volvió a
        preguntar y la Gran Base contestó, no porque lo dijera el request."""
        mock_consultar.return_value = {
            "success": True,
            "data": {"dni": "41422422", "nombre": "Maria", "apellido": "Gomez", "fecha_nacimiento": "1990-01-02"},
        }
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])
        resp = self.client.post(
            url,
            {
                "celular": "3624111222",
                "email_contacto": "x@y.com",
                "datos_identificacion": {
                    "dni": "41422422",
                    "sexo": "F",
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
        mock_consultar.assert_called_once_with("41422422", "F")

    @patch("programas.services.identidad.consultar_persona")
    def test_personas_sin_nombre_y_apellido_completos_no_valida(self, mock_consultar):
        """La Gran Base solo acredita identidad cuando devuelve los **dos**
        componentes: el apellido entero en un campo y el nombre vacío es la
        respuesta que la fuente da para algunos documentos, y no alcanza."""
        mock_consultar.return_value = {
            "success": True,
            "data": {"dni": "41433433", "nombre": "", "apellido": "IBAÑEZ LUCAS SEBASTIAN"},
        }
        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])
        resp = self.client.post(
            url,
            {
                "celular": "3624111222",
                "email_contacto": "x@y.com",
                "datos_identificacion": {
                    "dni": "41433433",
                    "sexo": "M",
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
        formulario = resp.data[0]
        self.assertEqual(formulario["ciudadano_nombre"], "Nombre")
        self.assertEqual(formulario["ciudadano_apellido"], "Visible")

    def test_patch_formulario_405(self):
        """SEC-23 · el caso cargado no se edita por la API de campo.

        Hasta el Cambio 184 esto devolvía **200** y escribía: ``perform_update``
        no miraba el estado del caso, así que con el token se podía reescribir un
        caso ya resuelto. El sync legítimo solo crea (POST, idempotente por
        ``client_uuid``) y la app instalada no manda un solo PATCH.
        """
        form = Formulario.objects.create(relevamiento=self.rel, celular="111", email_contacto="a@b.com")
        self.autenticar(self.terri)
        url = reverse("becas_api:formulario-detail", args=[form.id])

        for metodo in (self.client.patch, self.client.put):
            with self.subTest(metodo=metodo.__name__):
                resp = metodo(url, {"celular": "999"}, format="json")

                self.assertEqual(resp.status_code, 405, resp.data)
                form.refresh_from_db()
                self.assertEqual(form.celular, "111")

        # El GET del mismo caso sigue andando: lo que se saca es la escritura.
        self.assertEqual(self.client.get(url).status_code, 200)

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

    def test_las_respuestas_y_el_legajo_se_resuelven_fuera_del_lock(self):
        """Con el lock del relevamiento tomado queda solo lo que el lock
        protege; las respuestas por clave y el legajo corren después del
        commit (Cambio 91): la profundidad de transacción al llamarlos es la
        de afuera de la vista."""
        from django.db import connection

        from programas.api import views as api_views
        from programas.services.becas import resolver_ciudadano_offline
        from programas.services.respuestas import sincronizar_desde_legacy

        profundidades = {}

        def espia(nombre, original):
            def _espia(*args, **kwargs):
                profundidades[nombre] = len(connection.savepoint_ids)
                return original(*args, **kwargs)

            return _espia

        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])
        afuera = len(connection.savepoint_ids)
        with (
            patch.object(
                api_views, "sincronizar_desde_legacy", side_effect=espia("respuestas", sincronizar_desde_legacy)
            ),
            patch.object(
                api_views, "resolver_ciudadano_offline", side_effect=espia("legajo", resolver_ciudadano_offline)
            ),
        ):
            resp = self.client.post(url, self._payload_persona(date(1990, 1, 1)), format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(profundidades, {"respuestas": afuera, "legajo": afuera})
        self.assertEqual(resp.data["ciudadano_dni"], "60600600")

    def test_un_reintento_tras_un_corte_completa_lo_que_falto(self):
        """El alta se cortó después del commit (antes de las respuestas y el
        legajo): el caso quedó insertado a medias. La app reintenta con el mismo
        client_uuid y ese reintento —200, idempotente— completa lo que faltó en
        vez de devolver el caso como estaba."""
        from programas.api import views as api_views

        self.autenticar(self.terri)
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.id])
        payload = {"client_uuid": str(uuid4()), **self._payload_persona(date(1990, 1, 1))}
        # El corte: el proceso murió después del commit y antes de completar
        # (las dos funciones nunca llegaron a correr).
        with (
            patch.object(api_views, "sincronizar_desde_legacy", return_value=None),
            patch.object(api_views, "resolver_ciudadano_offline", return_value=None),
        ):
            primera = self.client.post(url, payload, format="json")
        self.assertEqual(primera.status_code, 201)
        caso = Formulario.objects.get(client_uuid=payload["client_uuid"])
        self.assertIsNone(caso.ciudadano_id)
        self.assertFalse(caso.definicion)

        reintento = self.client.post(url, payload, format="json")

        self.assertEqual(reintento.status_code, 200)
        self.assertEqual(reintento.data["id"], caso.pk)
        self.assertEqual(reintento.data["ciudadano_dni"], "60600600")
        self.assertEqual(Formulario.objects.filter(client_uuid=payload["client_uuid"]).count(), 1)
        caso.refresh_from_db()
        self.assertEqual(caso.ciudadano.dni, "60600600")
        self.assertTrue(caso.definicion)
        self.assertIsNone(caso.datos_identificacion)
        # Un tercer envío ya no tiene nada que completar y devuelve lo mismo.
        self.assertEqual(self.client.post(url, payload, format="json").data, reintento.data)

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

    # SEC-23 borró `test_no_permite_actualizar_formulario_fuera_de_fecha`: el
    # PATCH ya no existe, así que su guard de período tampoco. Los otros cinco
    # endpoints de escritura lo siguen teniendo, y lo fija
    # `PeriodoEnTodosLosEndpointsTests`.

    # RED-26 (auditoría oct-2026): `FormularioViewSet.get_queryset` es el ÚNICO
    # filtro de alcance de `/api/becas/formularios/<id>/` (GET y
    # POST …/adjuntos/). Cambiarlo por `Formulario.objects.all()` —por ejemplo
    # «para que un supervisor vea los casos de su equipo»— deja todos los casos
    # de Becas (DNI, contacto, GPS, respuestas y adjuntos) visibles y
    # **editables** por cualquier territorial con token, y no falla ningún test
    # (mutación M14; la gemela de `RelevamientoViewSet` sí muere).

    def _formulario_ajeno(self):
        return Formulario.objects.create(
            relevamiento=self.rel_ajeno,
            celular="111",
            email_contacto="ajeno@demo.local",
        )

    def test_no_accede_a_formulario_ajeno(self):
        ajeno = self._formulario_ajeno()
        self.autenticar(self.terri)

        resp = self.client.get(reverse("becas_api:formulario-detail", args=[ajeno.pk]))

        self.assertEqual(resp.status_code, 404)

    def test_no_actualiza_formulario_ajeno(self):
        ajeno = self._formulario_ajeno()
        self.autenticar(self.terri)

        resp = self.client.patch(
            reverse("becas_api:formulario-detail", args=[ajeno.pk]),
            {"celular": "999"},
            format="json",
        )

        # 405 y no 404 desde SEC-23 (Cambio 184): sin `UpdateModelMixin` el
        # router no mapea el verbo, así que el método se rechaza antes de
        # resolver el objeto. Lo que importa sigue siendo lo de abajo: el caso
        # ajeno no cambió.
        self.assertEqual(resp.status_code, 405)
        ajeno.refresh_from_db()
        self.assertEqual(ajeno.celular, "111")

    def test_no_sube_adjunto_a_formulario_ajeno(self):
        ajeno = self._formulario_ajeno()
        pregunta = PreguntaGlobal.objects.create(texto="Foto del DNI", tipo=TipoCampo.ARCHIVO, orden=900)
        self.autenticar(self.terri)

        resp = self.client.post(
            reverse("becas_api:formulario-adjuntos", args=[ajeno.pk]),
            {"pregunta_global": pregunta.pk, "archivo": SimpleUploadedFile("dni.jpg", b"datos")},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 404)
        self.assertEqual(ajeno.adjuntos.count(), 0)

    def test_no_lista_los_adjuntos_de_un_formulario_ajeno(self):
        ajeno = self._formulario_ajeno()
        self.autenticar(self.terri)

        resp = self.client.get(reverse("becas_api:formulario-adjuntos", args=[ajeno.pk]))

        self.assertEqual(resp.status_code, 404)


class AdjuntoValidacionTests(_BaseApiTest):
    """La API aceptaba cualquier archivo, de cualquier peso.

    Un ``.html`` o un ``.svg`` subido por ahi se ejecuta en el origen del sitio
    al abrirlo. Desde SEC-09 ``/media/`` pasa por Django y exige sesion, pero eso
    acota quien lo abre, no que el archivo sea peligroso: la validacion de tipo
    sigue siendo la barrera.
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

    def test_lista_los_adjuntos_ya_subidos(self):
        """RED-03: el `GET …/adjuntos/` no se ejecutaba en ningún test y es lo
        que la app lee para no reenviar una foto que ya subió."""
        url = reverse("becas_api:formulario-adjuntos", args=[self.formulario.pk])
        vacio = self.client.get(url)
        self._subir(SimpleUploadedFile("dni.jpg", b"datos"))

        resp = self.client.get(url)

        self.assertEqual(vacio.status_code, 200)
        self.assertEqual(vacio.data, [])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["pregunta_global"], self.pregunta.pk)
        self.assertEqual(resp.data[0]["formulario"], self.formulario.pk)
        self.assertIsNone(resp.data[0]["requisito_nativo"])
        # La app abre esta URL para mostrar la foto ya sincronizada.
        self.assertTrue(resp.data[0]["archivo"].endswith(".jpg"), resp.data[0]["archivo"])

    def test_el_get_de_adjuntos_no_mira_la_pausa_ni_el_periodo(self):
        """Leer lo ya subido es seguro con el relevamiento pausado o vencido:
        es lo que evita que la app reenvíe. Se fija el comportamiento de hoy."""
        self._subir(SimpleUploadedFile("dni.jpg", b"datos"))
        self.conv.pausado = True
        self.conv.pausa_motivo = "Operativo suspendido"
        self.conv.save(update_fields=["pausado", "pausa_motivo"])

        resp = self.client.get(reverse("becas_api:formulario-adjuntos", args=[self.formulario.pk]))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)


class _CincoEndpointsTest(_BaseApiTest):
    """Los cinco endpoints de escritura que la app de campo usa en una jornada.

    RED-03: la pausa estaba probada en **uno** (`iniciar`) y el período en tres.
    Borrar el guard de cualquiera de los otros —o que `_respuesta_pausa` dejara
    de mirar la pausa heredada de la convocatoria— seguía dando la suite en
    verde, con el campo cargando sobre un programa pausado.

    Eran seis hasta el Cambio 184: el sexto era el ``PATCH`` del caso, que SEC-23
    retiró.
    """

    def setUp(self):
        super().setUp()
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])
        self.formulario = Formulario.objects.create(
            relevamiento=self.rel,
            celular="111",
            email_contacto="a@b.com",
        )
        self.pregunta = PreguntaGlobal.objects.create(texto="Foto del DNI", tipo=TipoCampo.ARCHIVO, orden=900)
        self.autenticar(self.terri)

    def _url_rel(self, accion):
        return reverse(f"becas_api:relevamiento-{accion}", args=[self.rel.pk])

    def _iniciar(self):
        return self.client.post(self._url_rel("iniciar"), {}, format="json")

    def _finalizar(self):
        return self.client.post(self._url_rel("finalizar"), {}, format="json")

    def _reabrir(self):
        return self.client.post(self._url_rel("reabrir"), {}, format="json")

    def _crear_caso(self):
        return self.client.post(
            self._url_rel("formularios"),
            {
                "client_uuid": str(uuid4()),
                "celular": "3624111222",
                "email_contacto": "x@y.com",
                "datos_identificacion": {"dni": "40400400", "nombre": "Juan", "apellido": "Perez"},
            },
            format="json",
        )

    def _subir_adjunto(self):
        return self.client.post(
            reverse("becas_api:formulario-adjuntos", args=[self.formulario.pk]),
            {"pregunta_global": self.pregunta.pk, "archivo": SimpleUploadedFile("dni.jpg", b"datos")},
            format="multipart",
        )

    def _endpoints(self):
        return [
            ("iniciar", self._iniciar),
            ("finalizar", self._finalizar),
            ("reabrir", self._reabrir),
            ("formularios POST", self._crear_caso),
            ("adjuntos POST", self._subir_adjunto),
        ]

    def _afirmar_que_nada_cambio(self):
        self.rel.refresh_from_db()
        self.formulario.refresh_from_db()
        self.assertEqual(self.rel.estado, Relevamiento.Estado.EN_CURSO)
        self.assertIsNone(self.rel.fecha_finalizado)
        self.assertEqual(self.formulario.celular, "111")
        self.assertEqual(Formulario.objects.count(), 1)
        self.assertEqual(AdjuntoFormulario.objects.count(), 0)


class PausaEnTodosLosEndpointsTests(_CincoEndpointsTest):
    """El contrato de la pausa, fijado tal cual (D-RED-10).

    Los cinco contestan ``409 {"detail", "pausado": true}``. Hasta el Cambio 184
    el contrato **no era uniforme**: el sexto endpoint, el PATCH del caso,
    contestaba ``400 {"detail": [...]}`` porque `perform_update` levantaba un
    `ValidationError` de DRF. SEC-23 retiró el PATCH, así que la excepción se
    fue con él y ya no hay un release de Chaco-mobile pendiente para unificarla.
    """

    #: El código **exacto** que contesta cada endpoint con el relevamiento
    #: pausado. Es el contrato que lee la app: una regresión que pase cualquiera
    #: de los 409 a 400 (o al revés) tiene que fallar acá.
    CODIGO_DE_PAUSA = {
        "iniciar": 409,
        "finalizar": 409,
        "reabrir": 409,
        "formularios POST": 409,
        "adjuntos POST": 409,
    }

    def setUp(self):
        super().setUp()
        self.conv.pausado = True
        self.conv.pausa_motivo = "Operativo suspendido"
        self.conv.save(update_fields=["pausado", "pausa_motivo"])

    def _afirmar_respuesta_de_pausa(self, nombre, resp, motivo):
        esperado = self.CODIGO_DE_PAUSA[nombre]
        self.assertEqual(resp.status_code, esperado, resp.data)
        self.assertIn(motivo, str(resp.data["detail"]))
        self.assertIs(resp.data["pausado"], True)
        self._afirmar_que_nada_cambio()

    def test_la_pausa_bloquea_y_no_escribe(self):
        for nombre, llamar in self._endpoints():
            with self.subTest(endpoint=nombre):
                resp = llamar()

                self._afirmar_respuesta_de_pausa(nombre, resp, "Operativo suspendido")

    def test_la_pausa_propia_del_relevamiento_tambien_bloquea(self):
        """La cadena es relevamiento → convocatoria → segmento/subsegmento →
        programa; acá se ejerce el primer eslabón, con el mismo código exacto
        por endpoint que la pausa heredada."""
        self.conv.pausado = False
        self.conv.save(update_fields=["pausado", "modificado"])
        self.rel.pausado = True
        self.rel.pausa_motivo = "Territorial de licencia"
        self.rel.save(update_fields=["pausado", "pausa_motivo", "modificado"])

        for nombre, llamar in self._endpoints():
            with self.subTest(endpoint=nombre):
                resp = llamar()

                self._afirmar_respuesta_de_pausa(nombre, resp, "Territorial de licencia")


class PeriodoEnTodosLosEndpointsTests(_CincoEndpointsTest):
    """Mismo barrido con la franja vencida y sin pausa: el período se miraba en
    tres de los endpoints (faltaban `finalizar`, `reabrir` y `adjuntos`).
    """

    def setUp(self):
        super().setUp()
        ayer = timezone.localdate() - timedelta(days=1)
        self.rel.fecha_asignada = ayer
        self.rel.fecha_hasta = ayer
        self.rel.save(update_fields=["fecha_asignada", "fecha_hasta", "modificado"])
        self.rel.refresh_from_db()

    def test_fuera_del_periodo_se_rechaza_y_no_escribe(self):
        for nombre, llamar in self._endpoints():
            with self.subTest(endpoint=nombre):
                resp = llamar()

                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertIn("período", str(resp.data["detail"]))
                self.assertNotIn("pausado", resp.data)
                self._afirmar_que_nada_cambio()


class AltaBajoElLockTests(_BaseApiTest):
    """RED-10: presupuesto de consultas del alta por la app de campo.

    El POST de un caso trabaja con `select_for_update` sobre el relevamiento,
    contra el `read_timeout` de 10 s de MySQL/MariaDB: cada consulta de más
    adentro del lock la pagan en cola todos los dispositivos que sincronizan
    (Cambio 91: 165 × 500; Cambio 93: el alta bajó de 32 a 10 consultas).
    Agregar una lectura por caso —reconstruir la definición adentro del lock,
    re-resolver identidad— deja el CI en verde y rompe en producción.

    El número es el **medido hoy** sobre SQLite, el motor del CI. Como cualquier
    presupuesto, solo puede bajar: subirlo exige justificarlo (RED-62).

    **29 → 30 (G1-05, RED-62).** La consulta de más es el `UPDATE` que deja la
    revisión de la carga: respuestas sin lo que las condiciones ocultaron y
    `observaciones_carga`. Tres cosas la hacen aceptable y hay que conservarlas:
    (1) corre **después del commit**, fuera del `select_for_update`, que es lo
    que este presupuesto protege; (2) es **condicional** —si no hay nada que
    descartar ni que observar no se escribe, y el caso de este test entra en el
    `UPDATE` porque el segmento de `_BaseApiTest` pide GPS y el payload no lo
    manda—; y (3) no escala con la cantidad de casos ni de campos, que es lo que
    fija el segundo test. La alternativa —no validar— es lo que dejaba entrar
    respuestas a preguntas que el formulario escondía y mandarlas a SIIS.
    """

    CONSULTAS_ALTA = 30

    def setUp(self):
        super().setUp()
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])
        self.autenticar(self.terri)

    def _payload(self):
        return {
            "client_uuid": str(uuid4()),
            "celular": "3624111222",
            "email_contacto": "x@y.com",
            "datos_identificacion": {
                "dni": "40400400",
                "nombre": "Juan",
                "apellido": "Perez",
                "fecha_nacimiento": "1990-01-02",
            },
            "data": {"globales": {}, "requisitos": {}},
        }

    def test_el_alta_no_crece_en_consultas(self):
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.pk])

        with self.assertNumQueries(self.CONSULTAS_ALTA):
            resp = self.client.post(url, self._payload(), format="json")

        self.assertEqual(resp.status_code, 201, resp.data)

    def test_el_alta_no_crece_con_mas_casos_ya_cargados(self):
        """El mismo presupuesto con el relevamiento ya poblado: así el número
        también fija que el alta **no escale** con la cantidad de casos. El
        control de duplicados por DNI son dos lecturas por índice; resolverlo
        recorriendo los casos en Python (una consulta por ciudadano) da el mismo
        total con el relevamiento vacío y explota en campo, que es donde el
        relevamiento tiene cientos."""
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.pk])
        for indice in range(5):
            Formulario.objects.create(
                relevamiento=self.rel,
                ciudadano=Ciudadano.objects.create(dni=f"3011111{indice}", nombre="Previo", apellido="Caso"),
                celular="111",
                email_contacto="a@b.com",
            )

        with self.assertNumQueries(self.CONSULTAS_ALTA):
            resp = self.client.post(url, self._payload(), format="json")

        self.assertEqual(resp.status_code, 201, resp.data)


class AdjuntoSobreCasoResueltoTests(_BaseApiTest):
    """SEC-23 · sobre un caso ya resuelto la documentación no se **reemplaza**.

    `POST …/adjuntos/` pisa el archivo del campo (G1-07), así que sobre un caso
    ya APROBADO un token de campo cambiaba la foto del DNI semanas después de la
    resolución y sin dejar rastro en la revisión. El alcance por territorial
    (`get_queryset`) no lo frenaba: es su propio caso.

    Lo que **no** se cierra es el campo vacío: el 409 deja la operación
    `FAILED_PERMANENT` en la cola del teléfono y con ella se traba el
    `finalizar_relevamiento` del relevamiento entero. Ese archivo entra y queda
    dicho en `observaciones_carga`.
    """

    def setUp(self):
        super().setUp()
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])
        self.formulario = Formulario.objects.create(
            relevamiento=self.rel,
            celular="111",
            email_contacto="a@b.com",
        )
        self.pregunta = PreguntaGlobal.objects.create(texto="Foto del DNI", tipo=TipoCampo.ARCHIVO, orden=900)
        self.autenticar(self.terri)

    def _subir(self, nombre="dni.jpg"):
        return self.client.post(
            reverse("becas_api:formulario-adjuntos", args=[self.formulario.pk]),
            {"pregunta_global": self.pregunta.pk, "archivo": SimpleUploadedFile(nombre, b"datos")},
            format="multipart",
        )

    def _resolver(self, estado):
        self.formulario.estado = estado
        self.formulario.save(update_fields=["estado", "modificado"])

    def test_adjunto_sobre_caso_enviado_entra(self):
        """El camino normal de la app: el caso recién sincronizado está ENVIADO
        y sus fotos suben detrás. Es lo que el 409 de abajo **no** puede
        romper."""
        resp = self._subir()

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(self.formulario.adjuntos.count(), 1)
        self.formulario.refresh_from_db()
        self.assertFalse(self.formulario.observaciones_carga)

    def test_el_reemplazo_sobre_un_caso_enviado_sigue_sin_observarse(self):
        """G1-07 sin cambios: mientras el caso está ENVIADO la segunda foto pisa
        a la primera, con 201 y sin nada que decirle al revisor."""
        primera = self._subir("movida.jpg")
        self.assertEqual(primera.status_code, 201, primera.data)

        resp = self._subir("buena.jpg")

        self.assertEqual(resp.status_code, 201, resp.data)
        adjunto = self.formulario.adjuntos.get()
        self.assertEqual(adjunto.pk, primera.data["id"])
        self.assertNotEqual(resp.data["archivo"], primera.data["archivo"])
        self.formulario.refresh_from_db()
        self.assertFalse(self.formulario.observaciones_carga)

    def test_adjunto_sobre_aprobado_409(self):
        """El reemplazo sobre un caso resuelto, en los tres estados que lo son."""
        for estado in (Formulario.Estado.APROBADO, Formulario.Estado.RECHAZADO, Formulario.Estado.BAJA):
            with self.subTest(estado=estado):
                self.formulario.adjuntos.all().delete()
                self._resolver(Formulario.Estado.ENVIADO)
                buena = self._subir("buena.jpg")
                self.assertEqual(buena.status_code, 201, buena.data)
                self._resolver(estado)

                resp = self._subir("otra.jpg")

                self.assertEqual(resp.status_code, 409, resp.data)
                self.assertEqual(resp.data["code"], "CASO_RESUELTO")
                adjunto = self.formulario.adjuntos.get()
                self.assertEqual(adjunto.pk, buena.data["id"])
                self.assertEqual(adjunto.archivo.name, buena.data["archivo"].split("/media/")[-1])

    def test_el_campo_vacio_de_un_caso_resuelto_recibe_el_archivo_observado(self):
        """No hay nada que reemplazar: el archivo entra y el revisor se entera
        por la carga. Rechazarlo cuesta el relevamiento entero —la app marca la
        operación `FAILED_PERMANENT` y `hasPendingFormularioOperations` le traba
        el `finalizar_relevamiento` para siempre— y se pierden **todos** los
        adjuntos pendientes del caso, no solo este."""
        for estado in (Formulario.Estado.APROBADO, Formulario.Estado.RECHAZADO, Formulario.Estado.BAJA):
            with self.subTest(estado=estado):
                self.formulario.adjuntos.all().delete()
                self.formulario.observaciones_carga = None
                self.formulario.save(update_fields=["observaciones_carga", "modificado"])
                self._resolver(estado)

                resp = self._subir()

                self.assertEqual(resp.status_code, 201, resp.data)
                self.assertEqual(self.formulario.adjuntos.count(), 1)
                self.formulario.refresh_from_db()
                observaciones = self.formulario.observaciones_carga or ""
                self.assertIn("Foto del DNI", observaciones)
                self.assertIn(self.formulario.get_estado_display(), observaciones)
                self.assertTrue(observaciones.startswith(servicio_campo.PREFIJO_ADJUNTO_TARDIO), observaciones)

    def test_la_observacion_del_archivo_tardio_no_se_repite(self):
        """La cola reintenta: la línea se escribe una sola vez."""
        self._resolver(Formulario.Estado.APROBADO)
        self.assertEqual(self._subir().status_code, 201)
        # Como la fila ya está, el reintento se lleva el 409; el que podría
        # duplicar la línea es el que vuelve a entrar porque el adjunto no quedó.
        self.formulario.adjuntos.all().delete()

        self.assertEqual(self._subir().status_code, 201)

        self.formulario.refresh_from_db()
        lineas = (self.formulario.observaciones_carga or "").splitlines()
        self.assertEqual(len(lineas), 1, lineas)

    def test_el_adjunto_del_caso_aprobado_no_se_puede_reemplazar(self):
        """La forma concreta del abuso: la foto buena ya está, el caso se
        aprobó, y el token la pisa por otra (`guardar_adjunto` **reemplaza**,
        G1-07)."""
        primera = self._subir("buena.jpg")
        self.assertEqual(primera.status_code, 201)
        self.formulario.estado = Formulario.Estado.APROBADO
        self.formulario.save(update_fields=["estado", "modificado"])

        resp = self._subir("otra.jpg")

        self.assertEqual(resp.status_code, 409, resp.data)
        adjunto = self.formulario.adjuntos.get()
        self.assertEqual(adjunto.pk, primera.data["id"])
        self.assertEqual(adjunto.archivo.name, primera.data["archivo"].split("/media/")[-1])

    def test_listar_los_adjuntos_de_un_caso_resuelto_sigue_andando(self):
        """Lo que se cierra es la escritura: el GET lo usa la app para saber qué
        subió y un 4xx ahí sí le cortaría la cola."""
        self.assertEqual(self._subir().status_code, 201)
        self.formulario.estado = Formulario.Estado.APROBADO
        self.formulario.save(update_fields=["estado", "modificado"])

        resp = self.client.get(reverse("becas_api:formulario-adjuntos", args=[self.formulario.pk]))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)


class IdentidadNoLaAcreditaElClienteTests(_BaseApiTest):
    """SEC-24 · con `origen: personas` la identidad se vuelve a resolver acá.

    Antes alcanzaba con que el request dijera `"origen": "personas"` y trajera
    un nombre y un apellido cualesquiera: el caso quedaba `validado_renaper=True`
    y `origen_validacion="personas"`, o sea acreditado por Base de Personas sin
    que nadie le hubiera preguntado nada a Base de Personas. El comentario de la
    vista ya decía «el cliente nunca puede autovalidarse» y era falso para esta
    rama (lo cumplía solo `padron`, Cambio 57 / RN-4).
    """

    def setUp(self):
        super().setUp()
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])
        self.autenticar(self.terri)

    def _alta(self, **identidad):
        datos = {"dni": "41422422", "sexo": "F", "origen": "personas"}
        datos.update(identidad)
        return self.client.post(
            reverse("becas_api:relevamiento-formularios", args=[self.rel.pk]),
            {
                "celular": "3624111222",
                "email_contacto": "x@y.com",
                "validado_renaper": True,  # lo que la app instalada manda en el alta
                "datos_identificacion": datos,
                "data": {"globales": {}, "requisitos": {}},
            },
            format="json",
        )

    @patch("programas.services.identidad.consultar_persona")
    def test_origen_personas_sin_respaldo_no_valida(self, mock_consultar):
        """La Gran Base no conoce ese documento: la identidad es la que la
        persona dijo, no una acreditada."""
        mock_consultar.return_value = {
            "success": False,
            "not_found": True,
            "error": "El DNI no fue encontrado en Base de Personas.",
        }

        resp = self._alta(nombre="Inventada", apellido="Totalmente")

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(resp.data["validado_renaper"])
        caso = Formulario.objects.get(pk=resp.data["id"])
        self.assertEqual(caso.origen_validacion, "")
        # La carga entra igual —es el camino de una carga manual— y es el
        # revisor el que decide (Cambio 55). Lo que no pasa es que el caso se
        # presente como acreditado por Base de Personas.
        self.assertEqual(caso.estado, Formulario.Estado.ENVIADO)

    @patch("programas.services.identidad.consultar_persona")
    def test_origen_personas_que_no_coincide_manda_la_fuente(self, mock_consultar):
        """La fuente contesta, pero con otros datos que los que viajaron en el
        request: lo que se guarda es lo que dijo la fuente."""
        mock_consultar.return_value = {
            "success": True,
            "data": {"dni": "41422422", "nombre": "Maria", "apellido": "Gomez", "fecha_nacimiento": "1990-01-02"},
        }

        resp = self._alta(nombre="Otra", apellido="Persona")

        self.assertEqual(resp.status_code, 201, resp.data)
        caso = Formulario.objects.get(pk=resp.data["id"])
        self.assertTrue(caso.validado_renaper)
        self.assertEqual(caso.origen_validacion, Formulario.OrigenValidacion.PERSONAS)
        self.assertEqual(caso.ciudadano.nombre, "Maria")
        self.assertEqual(caso.ciudadano.apellido, "Gomez")

    @patch("programas.services.identidad.consultar_persona")
    def test_con_la_gran_base_caida_la_identidad_queda_pendiente(self, mock_consultar):
        """No se puede verificar ⇒ no se acredita. Queda para la validación
        manual del revisor (Cambio 55), que es el camino previsto."""
        mock_consultar.return_value = {"success": False, "error": "No se pudo consultar Base de Personas."}

        resp = self._alta(nombre="Maria", apellido="Gomez")

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(resp.data["validado_renaper"])

    @patch("programas.services.identidad.consultar_persona")
    def test_el_documento_que_no_figura_queda_escrito_en_la_carga(self, mock_consultar):
        """La fuente **respondió** y el documento no está en ella: es un dato
        sobre la persona, y el revisor lo necesita para decidir si valida a mano
        (Cambio 55). El `logger.warning` lo ve el operador del servidor, no él."""
        mock_consultar.return_value = {
            "success": False,
            "not_found": True,
            "error": "El DNI no fue encontrado en Base de Personas.",
        }

        resp = self._alta(nombre="Inventada", apellido="Totalmente")

        self.assertEqual(resp.status_code, 201, resp.data)
        caso = Formulario.objects.get(pk=resp.data["id"])
        self.assertIn(servicio_campo.IDENTIDAD_NO_ENCONTRADA, (caso.observaciones_carga or "").splitlines())

    @patch("programas.services.identidad.consultar_persona")
    def test_la_fuente_que_no_respondio_queda_escrita_en_la_carga(self, mock_consultar):
        """La Gran Base caída no dice **nada** de la persona: el caso llega sin
        validar porque nadie pudo verificarlo, que no es lo mismo que «no
        figura». Sin la línea, los dos casos se ven iguales en la revisión."""
        mock_consultar.return_value = {"success": False, "error": "No se pudo consultar Base de Personas."}

        resp = self._alta(nombre="Maria", apellido="Gomez")

        self.assertEqual(resp.status_code, 201, resp.data)
        caso = Formulario.objects.get(pk=resp.data["id"])
        lineas = (caso.observaciones_carga or "").splitlines()
        self.assertIn(servicio_campo.IDENTIDAD_FUENTE_SIN_RESPUESTA, lineas)
        self.assertNotIn(servicio_campo.IDENTIDAD_NO_ENCONTRADA, lineas)

    @patch("programas.services.identidad.consultar_persona")
    def test_la_carga_acreditada_no_lleva_ninguna_de_las_dos_lineas(self, mock_consultar):
        """Y si un reintento del alta sí acredita, la línea que decía que no se
        pudo acreditar se va: dejarla ahí sería un reparo que ya no es cierto."""
        mock_consultar.return_value = {"success": False, "error": "No se pudo consultar Base de Personas."}
        caso = Formulario.objects.get(pk=self._alta(nombre="Maria", apellido="Gomez").data["id"])
        self.assertIn(servicio_campo.PREFIJO_IDENTIDAD_SIN_ACREDITAR, caso.observaciones_carga or "")
        mock_consultar.return_value = {
            "success": True,
            "data": {"dni": "41422422", "nombre": "Maria", "apellido": "Gomez", "fecha_nacimiento": "1990-01-02"},
        }

        _actualizar_validacion_identidad(caso, {"dni": "41422422", "sexo": "F", "origen": "personas"})

        caso.refresh_from_db()
        self.assertTrue(caso.validado_renaper)
        self.assertNotIn(servicio_campo.PREFIJO_IDENTIDAD_SIN_ACREDITAR, caso.observaciones_carga or "")

    def test_el_scan_del_dni_sigue_valiendo(self):
        """D-24: el escaneo del código de barras del documento físico cuenta
        como validación y **no** sale a la red."""
        with patch("programas.services.identidad.consultar_persona") as mock_consultar:
            resp = self._alta(origen="scan", nombre="Maria", apellido="Gomez")

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data["validado_renaper"])
        mock_consultar.assert_not_called()


class ConsultaDePersonasConThrottleTests(_BaseApiTest):
    """SEC-25 · `POST /api/becas/personas/consultar/` tiene tope por usuario.

    Devuelve nombre, apellido y fecha de nacimiento de cualquier DNI + sexo: sin
    tope, un token de campo recorre la Gran Base entera a dos consultas por
    documento (F y M).
    """

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)
        self.autenticar(self.terri)

    def _consultar(self, dni="40400400"):
        return self.client.post(
            reverse("becas_api:personas-consultar"),
            {"dni": dni, "sexo": "M"},
            format="json",
        )

    def test_la_tasa_configurada_es_la_de_d25(self):
        self.assertEqual(ConsultaPersonasThrottle().rate, "120/hour")

    @patch("programas.services.identidad.consultar_persona")
    @patch.object(ConsultaPersonasThrottle, "get_rate", return_value="2/hour")
    def test_pasado_el_tope_contesta_429(self, _rate, mock_consultar):
        mock_consultar.return_value = {"success": True, "data": {"nombre": "Juan", "apellido": "Perez"}}

        self.assertEqual(self._consultar("40400400").status_code, 200)
        self.assertEqual(self._consultar("40400401").status_code, 200)
        resp = self._consultar("40400402")

        self.assertEqual(resp.status_code, 429)
        # DRF manda `Retry-After`: la app lo ignora y cae a carga manual, pero
        # un cliente nuevo sabe cuánto esperar.
        self.assertIn("Retry-After", resp)

    @patch("programas.services.identidad.consultar_persona")
    @patch.object(ConsultaPersonasThrottle, "get_rate", return_value="1/hour")
    def test_la_cubeta_es_por_usuario_y_no_por_ip(self, _rate, mock_consultar):
        """Los territoriales salen por el NAT de la operadora móvil: una cubeta
        por IP le cerraría la consulta a una región entera por el uso de una
        sola persona."""
        mock_consultar.return_value = {"success": True, "data": {"nombre": "Juan", "apellido": "Perez"}}
        self.assertEqual(self._consultar().status_code, 200)
        self.assertEqual(self._consultar().status_code, 429)

        self.autenticar(self.terri2)

        self.assertEqual(self._consultar().status_code, 200)

    @patch.object(ConsultaPersonasThrottle, "get_rate", return_value="1/hour")
    def test_el_alias_renaper_comparte_la_misma_cubeta(self, _rate):
        """Las dos rutas son la misma vista: un tope que se evade cambiando de
        URL no es un tope."""
        with patch("programas.services.identidad.consultar_persona") as mock_consultar:
            mock_consultar.return_value = {"success": True, "data": {"nombre": "Juan", "apellido": "Perez"}}
            self.assertEqual(self._consultar().status_code, 200)

            resp = self.client.post(
                reverse("becas_api:renaper-consultar"),
                {"dni": "40400400", "sexo": "M"},
                format="json",
            )

        self.assertEqual(resp.status_code, 429)

    def test_un_anonimo_sigue_frenando_en_el_permiso_y_no_en_la_cubeta(self):
        """El permiso corre antes que el throttle: nadie puede gastarle la cuota
        a un territorial desde afuera, ni llenar la caché sin credenciales."""
        self.client.credentials()

        resp = self._consultar()

        self.assertIn(resp.status_code, (401, 403))
