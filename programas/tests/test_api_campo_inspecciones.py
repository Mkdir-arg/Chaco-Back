"""API de campo del relevamiento edilicio (MVP v2 de Dispositivos, tasks 38 y 39).

Lo que se fija acá, y por qué:

1. **Cada recurso con su permiso.** El login de la app (``/api/becas/auth/token/``) le da
   token al agente con ``inspeccion.relevar``, pero ese token no abre Becas; y el
   territorial de Becas no abre ``/api/dispositivos/``.
2. **Solo lo asignado, y lo ajeno es 404** con el mismo cuerpo que un id que no existe. El
   usuario que lo intenta tiene todo lo demás (todas las capacidades y alcance de admin).
3. **La vista no decide reglas**: criticidad, tipo y tamaño de la foto los rechaza el servicio.
4. **Idempotencia** para la app sin conexión: el mismo ``uuid_cliente`` dos veces deja un solo
   registro, en el resultado y en cada foto.
5. **Conflictos legibles**: cancelado, reasignado o ya realizado con otro envío → 409 con ``code``.
6. **El esquema publicado** documenta los tres extremos con sus tipos.
"""

import uuid
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import NotFound
from rest_framework.test import APIClient

from core.tests.test_api_schema_contrato import _generar_esquema_y_sus_avisos
from core.validators import ADJUNTO_MAX_BYTES
from programas.management.commands.seed_becas import ROL_TERRITORIAL
from programas.models import FotoInspeccion, InspeccionEdificio, TrazaInspeccion
from programas.services.inspecciones import (
    cancelar_inspeccion,
    crear_inspeccion,
    inspecciones_para_envio,
    reasignar_inspeccion,
)
from programas.tests.test_dispositivos_inspecciones import JPEG, TODAS_DE_DISPOSITIVOS, BaseInspecciones, _foto

Criticidad = InspeccionEdificio.Criticidad
Estado = InspeccionEdificio.Estado

CLAVES_LISTADO = ["edificio", "estado", "fecha_vencimiento", "id", "indicaciones", "vencida"]
CLAVES_DETALLE = sorted(
    [
        *CLAVES_LISTADO,
        "criticidad",
        "fotos",
        "motivo_cancelacion",
        "observaciones",
        "realizada_en",
        "uuid_resultado",
    ]
)
CLAVES_FOTO = ["creado", "descripcion", "id", "uuid_cliente"]
CLAVES_EDIFICIO = sorted(
    [
        "calle",
        "codigo",
        "codigo_postal",
        "id",
        "latitud",
        "localidad",
        "longitud",
        "nombre",
        "numero",
        "piso_departamento",
        "provincia",
    ]
)


def _lista():
    return reverse("dispositivos_api:inspeccion-list")


def _detalle(pk):
    return reverse("dispositivos_api:inspeccion-detail", args=[pk])


def _resultado(pk):
    return reverse("dispositivos_api:inspeccion-resultado", args=[pk])


def _fotos(pk):
    return reverse("dispositivos_api:inspeccion-fotos", args=[pk])


class BaseApiInspecciones(BaseInspecciones):
    def setUp(self):
        super().setUp()
        self.inspeccion = self._crear()
        # Todo menos ser el asignado: todas las capacidades y alcance de admin del programa.
        self.intruso = self._usuario("intruso", TODAS_DE_DISPOSITIVOS, [self.parador, self.geriatrico])
        self.api = APIClient()

    def _crear_en_cis(self, agente):
        """Otro edificio, con su propio coordinador: el del predio no tiene alcance ahí."""

        coordinador = self._usuario("coordinador_cis", ("inspeccion.asignar",), [self.cis])
        return crear_inspeccion(
            coordinador, edificio=self.edificio_cis, asignado_a=self._fresco(agente), fecha_vencimiento=self.vence
        )

    def _como(self, usuario):
        token, _ = Token.objects.get_or_create(user=usuario)
        self.api.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        return self.api

    def _enviar_resultado(self, usuario, pk, uuid_cliente=None, criticidad=Criticidad.MEDIA, **extra):
        cuerpo = {"criticidad": criticidad, "observaciones": "Humedad en el techo", **extra}
        if uuid_cliente is not False:
            cuerpo["uuid_cliente"] = str(uuid_cliente or uuid.uuid4())
        return self._como(usuario).post(_resultado(pk), cuerpo, format="json")

    def _enviar_foto(self, usuario, pk, uuid_cliente=None, archivo=None, **extra):
        cuerpo = {"archivo": archivo or _foto(), "descripcion": "Fachada", **extra}
        if uuid_cliente is not False:
            cuerpo["uuid_cliente"] = str(uuid_cliente or uuid.uuid4())
        return self._como(usuario).post(_fotos(pk), cuerpo, format="multipart")


class AutenticacionTests(BaseApiInspecciones):
    def test_sin_token_es_401(self):
        respuestas = (
            self.api.get(_lista()),
            self.api.get(_detalle(self.inspeccion.pk)),
            self.api.post(_resultado(self.inspeccion.pk), {}, format="json"),
            self.api.post(_fotos(self.inspeccion.pk), {}, format="multipart"),
        )
        self.assertEqual([r.status_code for r in respuestas], [401] * 4)

    def test_el_agente_saca_token_con_el_login_de_la_app(self):
        respuesta = self.api.post(reverse("becas_api:token"), {"username": "agente", "password": "x"}, format="json")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(set(respuesta.data), {"token", "user_id", "username"})

    def test_sin_inspeccion_relevar_no_saca_token_aunque_tenga_lo_demas_de_dispositivos(self):
        sin_relevar = tuple(c for c in TODAS_DE_DISPOSITIVOS if c != "inspeccion.relevar")
        self._usuario("sin_relevar", sin_relevar, [self.parador])

        respuesta = self.api.post(
            reverse("becas_api:token"), {"username": "sin_relevar", "password": "x"}, format="json"
        )

        self.assertEqual(respuesta.status_code, 403)

    def test_sin_inspeccion_relevar_es_403_aunque_tenga_todo_lo_demas(self):
        sin_relevar = tuple(c for c in TODAS_DE_DISPOSITIVOS if c != "inspeccion.relevar")
        usuario = self._usuario("sin_relevar", sin_relevar, [self.parador, self.geriatrico])

        respuestas = (
            self._como(usuario).get(_lista()),
            self._como(usuario).get(_detalle(self.inspeccion.pk)),
            self._enviar_resultado(usuario, self.inspeccion.pk),
            self._enviar_foto(usuario, self.inspeccion.pk),
        )

        self.assertEqual([r.status_code for r in respuestas], [403] * 4)
        self.assertEqual(respuestas[0].data["detail"], "El usuario no tiene acceso al relevamiento edilicio.")

    def test_el_territorial_de_becas_no_entra_al_relevamiento_edilicio(self):
        call_command("seed_becas", stdout=StringIO())
        territorial = User.objects.create_user("terri", password="x")
        territorial.groups.add(Group.objects.get(name=ROL_TERRITORIAL))

        self.assertEqual(self._como(territorial).get("/api/becas/relevamientos/").status_code, 200)
        self.assertEqual(self._como(territorial).get(_lista()).status_code, 403)

    def test_el_agente_no_entra_a_becas(self):
        call_command("seed_becas", stdout=StringIO())

        self.assertEqual(self._como(self.agente).get("/api/becas/relevamientos/").status_code, 403)
        self.assertEqual(self._como(self.agente).get(_lista()).status_code, 200)


class SoloLoAsignadoTests(BaseApiInspecciones):
    def test_el_listado_trae_solo_lo_suyo_en_curso(self):
        del_otro = self._crear_en_cis(self.otro_agente)

        mias = self._como(self.agente).get(_lista())
        del_otro_agente = self._como(self.otro_agente).get(_lista())
        del_intruso = self._como(self.intruso).get(_lista())

        self.assertEqual([i["id"] for i in mias.data], [self.inspeccion.pk])
        self.assertEqual([i["id"] for i in del_otro_agente.data], [del_otro.pk])
        self.assertEqual(del_intruso.data, [])

    def test_lo_realizado_sale_de_la_agenda_pero_el_detalle_sigue(self):
        self._enviar_resultado(self.agente, self.inspeccion.pk)

        self.assertEqual(self._como(self.agente).get(_lista()).data, [])
        self.assertEqual(self._como(self.agente).get(_detalle(self.inspeccion.pk)).data["estado"], Estado.REALIZADA)

    def test_lo_ajeno_es_404_igual_que_lo_que_no_existe(self):
        inexistente = self.inspeccion.pk + 1000
        for usuario in (self.otro_agente, self.intruso):
            with self.subTest(usuario=usuario.username):
                ajeno = (
                    self._como(usuario).get(_detalle(self.inspeccion.pk)),
                    self._enviar_resultado(usuario, self.inspeccion.pk),
                    self._enviar_foto(usuario, self.inspeccion.pk),
                )
                no_existe = (
                    self._como(usuario).get(_detalle(inexistente)),
                    self._enviar_resultado(usuario, inexistente),
                    self._enviar_foto(usuario, inexistente),
                )
                self.assertEqual([r.status_code for r in ajeno], [404] * 3)
                self.assertEqual([r.data for r in ajeno], [r.data for r in no_existe])
                self.assertEqual([r.json() for r in ajeno], [{"detail": str(NotFound.default_detail)}] * 3)

        self.inspeccion.refresh_from_db()
        self.assertEqual(self.inspeccion.estado, Estado.ASIGNADA)
        self.assertFalse(FotoInspeccion.objects.exists())

    def test_el_respaldo_del_servicio_da_el_mismo_404(self):
        """Si el servicio niega algo que la vista dejó pasar, sale el mismo cuerpo genérico."""

        no_existe = self._enviar_resultado(self.agente, self.inspeccion.pk + 1000)
        with patch("programas.api.views_inspecciones.registrar_resultado", side_effect=PermissionDenied("No es tuyo.")):
            negado = self._enviar_resultado(self.agente, self.inspeccion.pk)

        self.assertEqual(negado.status_code, 404)
        self.assertEqual(negado.json(), no_existe.json())
        self.assertEqual(negado.json(), {"detail": str(NotFound.default_detail)})

    def test_el_selector_de_envio_no_trae_lo_ajeno(self):
        """La primera de las dos capas: el servicio vuelve a mirar `asignado_a` igual."""

        self.assertEqual(list(inspecciones_para_envio(self._fresco(self.intruso))), [])
        self.assertEqual(list(inspecciones_para_envio(self._fresco(self.agente))), [self.inspeccion])


class ResultadoTests(BaseApiInspecciones):
    def test_el_agente_registra_el_resultado(self):
        envio = uuid.uuid4()

        respuesta = self._enviar_resultado(self.agente, self.inspeccion.pk, envio, Criticidad.ALTA)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(sorted(respuesta.data), CLAVES_DETALLE)
        self.assertEqual(respuesta.data["estado"], Estado.REALIZADA)
        self.inspeccion.refresh_from_db()
        self.assertEqual(self.inspeccion.criticidad, Criticidad.ALTA)
        self.assertEqual(self.inspeccion.observaciones, "Humedad en el techo")
        self.assertEqual(self.inspeccion.realizada_por, self.agente)
        self.assertEqual(self.inspeccion.uuid_resultado, envio)

    def test_criticidad_inventada_o_sin_uuid_es_400_legible(self):
        for respuesta in (
            self._enviar_resultado(self.agente, self.inspeccion.pk, criticidad="VERDE"),
            self._enviar_resultado(self.agente, self.inspeccion.pk, uuid_cliente=False),
        ):
            with self.subTest(cuerpo=respuesta.data):
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("detail", respuesta.data)
                self.assertIn("non_field_errors", respuesta.data)

        self.inspeccion.refresh_from_db()
        self.assertEqual(self.inspeccion.estado, Estado.ASIGNADA)


class FotoTests(BaseApiInspecciones):
    def test_el_agente_sube_una_foto(self):
        envio = uuid.uuid4()

        respuesta = self._enviar_foto(self.agente, self.inspeccion.pk, envio)

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(sorted(respuesta.data), CLAVES_FOTO)
        foto = FotoInspeccion.objects.get()
        self.assertEqual((foto.uuid_cliente, foto.descripcion, foto.cargada_por), (envio, "Fachada", self.agente))

    def test_la_foto_se_valida_en_el_servicio(self):
        casos = {
            "tipo no aceptado": _foto("informe.pdf", b"%PDF-1.4 algo"),
            "HTML renombrado": _foto("fachada.jpg", b"<html><script>alert(1)</script></html>"),
            "demasiado grande": _foto("grande.jpg", JPEG + b"0" * ADJUNTO_MAX_BYTES),
        }
        for caso, archivo in casos.items():
            with self.subTest(caso=caso):
                respuesta = self._enviar_foto(self.agente, self.inspeccion.pk, archivo=archivo)

                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("archivo", respuesta.data)
                self.assertTrue(respuesta.data["detail"])

        self.assertFalse(FotoInspeccion.objects.exists())

    def test_sin_archivo_o_sin_uuid_es_400(self):
        sin_uuid = self._enviar_foto(self.agente, self.inspeccion.pk, uuid_cliente=False)
        sin_archivo = self._como(self.agente).post(
            _fotos(self.inspeccion.pk), {"uuid_cliente": str(uuid.uuid4())}, format="multipart"
        )

        self.assertEqual((sin_uuid.status_code, sin_archivo.status_code), (400, 400))
        self.assertFalse(FotoInspeccion.objects.exists())

    def test_se_suben_fotos_despues_del_resultado(self):
        self._enviar_resultado(self.agente, self.inspeccion.pk)

        self.assertEqual(self._enviar_foto(self.agente, self.inspeccion.pk).status_code, 201)
        detalle = self._como(self.agente).get(_detalle(self.inspeccion.pk)).data
        self.assertEqual(len(detalle["fotos"]), 1)


class IdempotenciaTests(BaseApiInspecciones):
    def test_el_mismo_resultado_dos_veces_es_un_solo_registro(self):
        envio = uuid.uuid4()
        primera = self._enviar_resultado(self.agente, self.inspeccion.pk, envio, Criticidad.ALTA)
        self.inspeccion.refresh_from_db()
        realizada_en = self.inspeccion.realizada_en

        segunda = self._enviar_resultado(self.agente, self.inspeccion.pk, envio, Criticidad.BAJA)

        self.assertEqual((primera.status_code, segunda.status_code), (200, 200))
        self.assertEqual(primera.data, segunda.data)
        self.inspeccion.refresh_from_db()
        self.assertEqual((self.inspeccion.criticidad, self.inspeccion.realizada_en), (Criticidad.ALTA, realizada_en))

    def test_otro_resultado_sobre_uno_realizado_es_409(self):
        self._enviar_resultado(self.agente, self.inspeccion.pk)

        respuesta = self._enviar_resultado(self.agente, self.inspeccion.pk)

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual((respuesta.data["code"], respuesta.data["estado"]), ("YA_REALIZADA", Estado.REALIZADA))

    def test_la_misma_foto_dos_veces_es_una_sola(self):
        envio = uuid.uuid4()

        primera = self._enviar_foto(self.agente, self.inspeccion.pk, envio)
        segunda = self._enviar_foto(self.agente, self.inspeccion.pk, envio)

        self.assertEqual((primera.status_code, segunda.status_code), (201, 200))
        self.assertEqual(primera.data["id"], segunda.data["id"])
        self.assertEqual(FotoInspeccion.objects.count(), 1)

    def test_el_reenvio_de_una_foto_que_llego_no_choca_con_la_cancelacion(self):
        envio = uuid.uuid4()
        self._enviar_foto(self.agente, self.inspeccion.pk, envio)
        cancelar_inspeccion(self._fresco(self.coordinador), self.inspeccion, "Edificio clausurado")

        self.assertEqual(self._enviar_foto(self.agente, self.inspeccion.pk, envio).status_code, 200)
        self.assertEqual(FotoInspeccion.objects.count(), 1)

    def test_el_uuid_de_una_foto_del_agente_anterior_no_es_un_reenvio_del_nuevo(self):
        """El reenvío es del mismo agente: el nuevo no se queda con la foto del anterior."""

        envio = uuid.uuid4()
        self._enviar_foto(self.agente, self.inspeccion.pk, envio)
        reasignar_inspeccion(self._fresco(self.coordinador), self.inspeccion, self._fresco(self.otro_agente))

        respuesta = self._enviar_foto(self.otro_agente, self.inspeccion.pk, envio)

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.data["code"], "UUID_EN_USO")
        self.assertEqual(FotoInspeccion.objects.count(), 1)

    def test_el_mismo_uuid_en_otra_foto_es_409(self):
        envio = uuid.uuid4()
        otra = self._crear_en_cis(self.agente)
        self._enviar_foto(self.agente, self.inspeccion.pk, envio)

        respuesta = self._enviar_foto(self.agente, otra.pk, envio)

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.data["code"], "UUID_EN_USO")
        self.assertEqual(FotoInspeccion.objects.count(), 1)

    def _trazas(self, accion):
        return TrazaInspeccion.objects.filter(inspeccion=self.inspeccion, accion=accion).count()

    def test_el_reenvio_del_resultado_no_deja_una_segunda_traza(self):
        """La auditoría (#699) cuenta acciones, no llamadas: el reintento de la app no es una.

        La app sin señal reenvía hasta que le contestan; si cada reintento dejara su línea,
        el historial del dispositivo mostraría un relevamiento cerrado varias veces.
        """

        envio = uuid.uuid4()
        self._enviar_resultado(self.agente, self.inspeccion.pk, envio, Criticidad.ALTA)
        self.assertEqual(self._trazas(TrazaInspeccion.Accion.REALIZADA), 1)

        self.assertEqual(self._enviar_resultado(self.agente, self.inspeccion.pk, envio).status_code, 200)

        self.assertEqual(self._trazas(TrazaInspeccion.Accion.REALIZADA), 1)

    def test_el_reenvio_de_la_foto_no_deja_una_segunda_traza(self):
        envio = uuid.uuid4()
        self.assertEqual(self._enviar_foto(self.agente, self.inspeccion.pk, envio).status_code, 201)
        self.assertEqual(self._trazas(TrazaInspeccion.Accion.FOTO), 1)

        self.assertEqual(self._enviar_foto(self.agente, self.inspeccion.pk, envio).status_code, 200)

        self.assertEqual((self._trazas(TrazaInspeccion.Accion.FOTO), FotoInspeccion.objects.count()), (1, 1))


class ConflictoTests(BaseApiInspecciones):
    def test_cancelado_mientras_tanto_es_409_con_el_motivo(self):
        cancelar_inspeccion(self._fresco(self.coordinador), self.inspeccion, "Edificio clausurado")

        for respuesta in (
            self._enviar_resultado(self.agente, self.inspeccion.pk),
            self._enviar_foto(self.agente, self.inspeccion.pk),
        ):
            with self.subTest(url=respuesta.request["PATH_INFO"]):
                self.assertEqual(respuesta.status_code, 409)
                self.assertEqual((respuesta.data["code"], respuesta.data["estado"]), ("CANCELADA", Estado.CANCELADA))
                self.assertIn("Edificio clausurado", respuesta.data["detail"])

        self.assertFalse(FotoInspeccion.objects.exists())
        self.assertEqual(self._como(self.agente).get(_detalle(self.inspeccion.pk)).data["estado"], Estado.CANCELADA)

    def test_reasignado_mientras_tanto_es_409_para_quien_lo_tenia(self):
        reasignar_inspeccion(self._fresco(self.coordinador), self.inspeccion, self._fresco(self.otro_agente))

        for respuesta in (
            self._enviar_resultado(self.agente, self.inspeccion.pk),
            self._enviar_foto(self.agente, self.inspeccion.pk),
        ):
            with self.subTest(url=respuesta.request["PATH_INFO"]):
                self.assertEqual(respuesta.status_code, 409)
                self.assertEqual(respuesta.data["code"], "REASIGNADA")

        # Ya no es suyo: el detalle es 404, y el nuevo agente sí lo carga.
        self.assertEqual(self._como(self.agente).get(_detalle(self.inspeccion.pk)).status_code, 404)
        self.assertEqual(self._enviar_resultado(self.otro_agente, self.inspeccion.pk).status_code, 200)
        self.assertFalse(FotoInspeccion.objects.exists())

    def test_un_estado_que_todavia_no_existe_no_deja_cerrar_ni_subir_fotos(self):
        """Los estados son «defaults a confirmar con el Ministerio»: agregar uno no abre la puerta.

        Se fuerza por `update()` —ningún servicio escribe este valor— para que el día que
        exista «vencido» o cualquier otro, el agente no lo cierre como si estuviera en curso.
        """

        InspeccionEdificio.objects.filter(pk=self.inspeccion.pk).update(estado="VENCIDA")

        for respuesta in (
            self._enviar_resultado(self.agente, self.inspeccion.pk),
            self._enviar_foto(self.agente, self.inspeccion.pk),
        ):
            with self.subTest(url=respuesta.request["PATH_INFO"]):
                self.assertEqual(respuesta.status_code, 409)
                self.assertEqual((respuesta.data["code"], respuesta.data["estado"]), ("ESTADO_NO_ADMITE", "VENCIDA"))

        self.inspeccion.refresh_from_db()
        self.assertEqual(self.inspeccion.estado, "VENCIDA")
        self.assertFalse(FotoInspeccion.objects.exists())


class ContratoJsonTests(BaseApiInspecciones):
    """Las claves que lee la app. Agregar es seguro; renombrar o sacar es un release de la app."""

    def test_listado_y_detalle(self):
        listado = self._como(self.agente).get(_lista()).data
        detalle = self._como(self.agente).get(_detalle(self.inspeccion.pk)).data

        self.assertEqual(sorted(listado[0]), CLAVES_LISTADO)
        self.assertEqual(sorted(listado[0]["edificio"]), CLAVES_EDIFICIO)
        self.assertEqual(sorted(detalle), CLAVES_DETALLE)
        self.assertIs(detalle["vencida"], False)


class EsquemaTests(BaseApiInspecciones):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.esquema, _, cls.warnings = _generar_esquema_y_sus_avisos()

    def test_los_extremos_estan_publicados_sin_warnings(self):
        rutas = self.esquema["paths"]

        self.assertIn("get", rutas["/api/dispositivos/inspecciones/"])
        self.assertIn("get", rutas["/api/dispositivos/inspecciones/{id}/"])
        self.assertEqual(self.warnings, [])
        for ruta in ("resultado", "fotos"):
            with self.subTest(ruta=ruta):
                operacion = rutas[f"/api/dispositivos/inspecciones/{{id}}/{ruta}/"]["post"]
                self.assertIn("409", operacion["responses"])
                self.assertIn("404", operacion["responses"])

    def test_el_resultado_declara_su_cuerpo(self):
        operacion = self.esquema["paths"]["/api/dispositivos/inspecciones/{id}/resultado/"]["post"]
        ref = operacion["requestBody"]["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
        cuerpo = self.esquema["components"]["schemas"][ref]

        self.assertEqual(sorted(cuerpo["required"]), ["criticidad", "uuid_cliente"])
        self.assertEqual(cuerpo["properties"]["uuid_cliente"]["format"], "uuid")
        self.assertEqual(self.esquema["components"]["schemas"]["CriticidadEnum"]["enum"], ["BAJA", "MEDIA", "ALTA"])

    def test_la_foto_es_multipart(self):
        operacion = self.esquema["paths"]["/api/dispositivos/inspecciones/{id}/fotos/"]["post"]
        contenido = operacion["requestBody"]["content"]

        self.assertEqual(list(contenido), ["multipart/form-data"])
        ref = contenido["multipart/form-data"]["schema"]["$ref"].split("/")[-1]
        cuerpo = self.esquema["components"]["schemas"][ref]
        self.assertEqual(sorted(cuerpo["required"]), ["archivo", "uuid_cliente"])
        self.assertEqual(cuerpo["properties"]["archivo"]["format"], "binary")
        self.assertEqual(sorted(operacion["responses"])[:2], ["200", "201"])

    def test_el_estado_tiene_nombre_propio(self):
        self.assertEqual(
            self.esquema["components"]["schemas"]["InspeccionEstadoEnum"]["enum"],
            ["ASIGNADA", "REALIZADA", "CANCELADA"],
        )
