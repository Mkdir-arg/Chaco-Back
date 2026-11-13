"""Módulo Emergencia, PR 9-API: M3, la recepción de kits desde la app.

La guardia con ``emergencia.recibir_kit`` en su Equipo lista las entregas de su dispositivo y
confirma la recepción con la misma función que la pantalla web. Fija el 403/404 por alcance
(plan §2, C2), el 409 ``{detail, estado_actual}`` contra la web, la idempotencia por
``uuid_cliente`` y las claves exactas (``base_emergencia_api``).
"""

import uuid
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext

from core.validators import ADJUNTO_MAX_BYTES, MENSAJE_ADJUNTO_TAMANIO
from programas.api.serializers_emergencia import (
    MENSAJE_CANTIDADES_INVALIDAS,
    MENSAJE_SIN_CANTIDADES,
)
from programas.models import (
    EntradaBitacora,
    EntregaKit,
    LineaEntrega,
    TipoKit,
    TrazaEntrega,
)
from programas.selectors import kits as selectores_kits
from programas.services import kits as servicio_kits
from programas.services.emergencia import UuidEnUso
from programas.tests.base_emergencia_api import (
    ADMITIR,
    CLAVES_DIFERENCIA,
    CLAVES_ENTREGA,
    CLAVES_ESTADO_CAMBIO,
    CLAVES_FIJAS_DEL_400,
    CLAVES_LINEA_DE_ENTREGA,
    CLAVES_MI_DISPOSITIVO,
    CLAVES_RECEPCION,
    CLAVES_SIN_MODULO,
    CLAVES_UUID_EN_USO,
    PNG,
    SIN_MODULO,
    SIN_RECIBIR_KIT,
    URL_MIS_DISPOSITIVOS,
    BaseApiEmergencia,
)
from programas.tests.test_emergencia_base import RECIBIR_KIT
from programas.tests.test_emergencia_casos import JPEG

# ---------------------------------------------------------------------------
# M3 · Recepción de kits (PR 9-API)
# ---------------------------------------------------------------------------


class BaseApiKits(BaseApiEmergencia):
    """Lo de ``BaseApiEmergencia`` más dos dispositivos con su guardia de kits, catálogo y una entrega en camino."""

    def setUp(self):
        super().setUp()
        self.escuela = self._dispositivo("Escuela 12", camas=4)
        self.deposito = self._guardia("deposito", [RECIBIR_KIT], [self.club])
        self.deposito_escuela = self._guardia("deposito_escuela", [RECIBIR_KIT], [self.escuela])
        self.colchon = TipoKit.objects.create(nombre="Colchón", unidad="unidad", orden=1)
        self.alimentos = TipoKit.objects.create(nombre="Kit alimentario", unidad="kit", orden=2)
        self.entrega = self._entrega_en_camino(self.club, observacion="Entregar a la directora.")
        self.url_recibir = self._url_recibir(self.entrega)

    def _entrega_en_camino(self, dispositivo, **extra):
        entrega = servicio_kits.crear_entrega(
            self.operador, dispositivo, [(self.colchon, 10), (self.alimentos, 3)], **extra
        )
        return servicio_kits.marcar_en_camino(entrega, self.operador)

    def _url_entregas(self, dispositivo):
        return f"/api/emergencia/dispositivos/{dispositivo.pk}/entregas/"

    def _url_entrega(self, entrega):
        return f"/api/emergencia/entregas/{entrega.pk}/"

    def _url_recibir(self, entrega):
        return f"/api/emergencia/entregas/{entrega.pk}/recibir/"

    def _recepcion(self, colchones=10, kits=3, remito="jpeg", uuid_cliente=None, **extra):
        """El multipart de la app: ``cantidades[<id del ítem>]``, el remito y el identificador."""
        cuerpo = {
            "uuid_cliente": str(uuid_cliente or uuid.uuid4()),
            f"cantidades[{self.colchon.pk}]": colchones,
            f"cantidades[{self.alimentos.pk}]": kits,
            **extra,
        }
        if remito == "jpeg":
            cuerpo["remito"] = self._foto("remito.jpg")
        elif remito is not None:
            cuerpo["remito"] = remito
        return {clave: valor for clave, valor in cuerpo.items() if valor is not None}

    def _recibir(self, usuario=None, url=None, **cambios):
        return self._como(usuario or self.deposito).post(
            url or self.url_recibir, self._recepcion(**cambios), format="multipart"
        )

    def _foto_de(self, entrega):
        fila = EntregaKit.objects.filter(pk=entrega.pk).values().get()
        lineas = list(LineaEntrega.objects.filter(entrega=entrega).order_by("id").values())
        return fila, lineas, TrazaEntrega.objects.filter(entrega=entrega).count()


class AccesoAKitsTests(BaseApiKits):
    def _de_kits(self):
        return [self._url_entregas(self.club), self._url_entrega(self.entrega), self.url_recibir]

    def test_sin_token_es_401(self):
        for url in [URL_MIS_DISPOSITIVOS, *self._de_kits()]:
            for metodo in ("get", "post"):
                with self.subTest(url=url, metodo=metodo):
                    self.assertEqual(getattr(self._anonimo(), metodo)(url, {}, format="json").status_code, 401)

    def test_un_rol_de_becas_recibe_403_sin_modulo(self):
        """RU §6 n.° 3: ``becas.campo`` no abre nada de kits, exista o no la entrega."""
        cliente = self._como(self.territorial_becas)
        antes = self._foto_de(self.entrega)

        for url in (URL_MIS_DISPOSITIVOS, self._url_entregas(self.club), self._url_entrega(self.entrega)):
            with self.subTest(url=url):
                respuesta = cliente.get(url)
                self.assertEqual(respuesta.status_code, 403)
                self.assertEqual(sorted(respuesta.json()), CLAVES_SIN_MODULO)
                self.assertEqual(respuesta.json(), SIN_MODULO)
        respuesta = cliente.post(self.url_recibir, self._recepcion(), format="multipart")
        self.assertEqual((respuesta.status_code, respuesta.json()), (403, SIN_MODULO))
        self.assertEqual(self._foto_de(self.entrega), antes)

    def test_quien_abre_el_modulo_sin_recibir_kits_recibe_403(self):
        """La guardia que solo admite y el agente territorial abren el módulo, no la recepción de kits."""
        for usuario in (self.guardia, self.agente):
            cliente = self._como(usuario)
            for url in (self._url_entregas(self.club), self._url_entrega(self.entrega)):
                with self.subTest(usuario=usuario.username, url=url):
                    respuesta = cliente.get(url)
                    self.assertEqual(respuesta.status_code, 403)
                    self.assertEqual(respuesta.json(), SIN_RECIBIR_KIT)
            respuesta = cliente.post(self.url_recibir, self._recepcion(), format="multipart")
            self.assertEqual((respuesta.status_code, respuesta.json()), (403, SIN_RECIBIR_KIT))
        self.assertEqual(EntregaKit.objects.get(pk=self.entrega.pk).estado, EntregaKit.Estado.EN_CAMINO)

    def test_recibir_kit_en_a_no_abre_nada_de_b_y_contesta_404(self):
        """**Mutación de RN-4.8 por la API** (plan §2, C2). El depósito de la Escuela pide lo del Club.

        Visto en rojo: con ``entregas_al_alcance`` devolviendo todas las entregas (sin el
        ``dispositivo__in`` del alcance), el detalle contesta 200 con la entrega del Club y
        este test falla con «200 != 404». El POST lo sigue frenando el servicio, pero con el
        selector roto la vista lo traduce a 404 recién después de haber leído la entrega. El
        cuerpo del 404 es el de un id inexistente: no nombra al Club.
        """
        cliente = self._como(self.deposito_escuela)
        antes = self._foto_de(self.entrega)
        inexistente = cliente.get("/api/emergencia/entregas/999999/")
        self.assertEqual((inexistente.status_code, inexistente.json()), (404, {"detail": "No encontrado."}))

        for url in (self._url_entregas(self.club), self._url_entrega(self.entrega)):
            with self.subTest(url=url):
                respuesta = cliente.get(url)
                self.assertEqual(respuesta.status_code, 404)
                self.assertEqual(respuesta.json(), inexistente.json())
                self.assertNotIn("Club", respuesta.content.decode())
        respuesta = cliente.post(self.url_recibir, self._recepcion(), format="multipart")

        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(respuesta.json(), inexistente.json())
        self.assertEqual(self._foto_de(self.entrega), antes)
        self.assertFalse(EntregaKit.objects.get(pk=self.entrega.pk).remito)
        self.assertFalse(EntradaBitacora.objects.exists())

    def test_la_capacidad_sin_equipo_no_abre_nada(self):
        sin_equipo = self._guardia("sin_equipo", [RECIBIR_KIT])

        respuesta = self._como(sin_equipo).get(self._url_entrega(self.entrega))

        self.assertEqual((respuesta.status_code, respuesta.json()), (403, SIN_MODULO))

    def test_quien_opera_la_mesa_no_recibe_por_la_api(self):
        self.client.force_login(self.operador)

        respuesta = self.client.get(self._url_entrega(self.entrega))

        self.assertEqual((respuesta.status_code, respuesta.json()), (403, SIN_MODULO))


class MisDispositivosTests(BaseApiKits):
    def test_trae_id_nombre_y_entregas_pendientes(self):
        servicio_kits.crear_entrega(self.operador, self.club, [(self.colchon, 1)])

        respuesta = self._como(self.deposito).get(URL_MIS_DISPOSITIVOS)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([sorted(fila) for fila in respuesta.json()], [CLAVES_MI_DISPOSITIVO])
        # Solo recibe kits: lo de «Llegada de familias» viene en cero (PR 8).
        self.assertEqual(
            respuesta.json(),
            [
                {
                    "id": self.club.pk,
                    "nombre": "Club Sarmiento",
                    "entregas_pendientes": 2,
                    "plazas_libres": 0,
                    "derivaciones_pendientes": 0,
                }
            ],
        )

    def test_la_guardia_que_solo_admite_ve_su_dispositivo_con_cero_pendientes(self):
        respuesta = self._como(self.guardia).get(URL_MIS_DISPOSITIVOS)

        self.assertEqual(
            respuesta.json(),
            [
                {
                    "id": self.club.pk,
                    "nombre": "Club Sarmiento",
                    "entregas_pendientes": 0,
                    "plazas_libres": 4,
                    "derivaciones_pendientes": 0,
                }
            ],
        )

    def test_con_dos_dispositivos_vienen_los_dos_por_nombre(self):
        doble = self._sumar_rol(self.deposito, [RECIBIR_KIT], self.dispositivos, [self.escuela])
        self._entrega_en_camino(self.escuela)

        respuesta = self._como(doble).get(URL_MIS_DISPOSITIVOS)

        self.assertEqual(
            [(fila["nombre"], fila["entregas_pendientes"]) for fila in respuesta.json()],
            [("Club Sarmiento", 1), ("Escuela 12", 1)],
        )

    def test_el_agente_territorial_no_tiene_dispositivos(self):
        respuesta = self._como(self.agente).get(URL_MIS_DISPOSITIVOS)

        self.assertEqual((respuesta.status_code, respuesta.json()), (200, []))

    @tag("performance")
    def test_el_endpoint_no_crece_con_los_dispositivos(self):
        """Presupuesto de ``mis-dispositivos``: lo mismo con 1 dispositivo que con 30."""

        def consultas(usuario):
            cliente = self._como(usuario)
            cliente.get(URL_MIS_DISPOSITIVOS)
            with CaptureQueriesContext(connection) as capturadas:
                self.assertEqual(cliente.get(URL_MIS_DISPOSITIVOS).status_code, 200)
            return len(capturadas)

        # Con las dos capacidades y camas en los dos lados: así corren todas las consultas
        # de «Llegada de familias» (PR 8) en la medición chica y en la grande.
        con_uno = consultas(self._sumar_rol(self.deposito, [ADMITIR], self.dispositivos, [self.club]))
        muchos = [self._dispositivo(f"Sede {n:02d}", camas=2) for n in range(30)]
        de_todos = self._guardia("deposito_de_todos", [RECIBIR_KIT, ADMITIR], muchos)
        for dispositivo in muchos:
            self._entrega_en_camino(dispositivo)

        self.assertEqual(consultas(de_todos), con_uno)
        self.assertEqual(len(self._como(de_todos).get(URL_MIS_DISPOSITIVOS).json()), 30)

    @tag("performance")
    def test_el_selector_cuesta_dos_consultas(self):
        muchos = [self._dispositivo(f"Sede {n:02d}") for n in range(30)]
        de_todos = self._guardia("deposito_de_todos", [RECIBIR_KIT, ADMITIR], muchos)
        for dispositivo in muchos:
            self._entrega_en_camino(dispositivo)
        selectores_kits.mis_dispositivos(de_todos)  # memoiza el programa y las capacidades

        with self.assertNumQueries(2):
            filas = selectores_kits.mis_dispositivos(de_todos)
        self.assertEqual({fila["entregas_pendientes"] for fila in filas}, {1})


class EntregasDelDispositivoApiTests(BaseApiKits):
    def test_las_pendientes_traen_la_entrega_con_sus_lineas(self):
        respuesta = self._como(self.deposito).get(self._url_entregas(self.club), {"pendientes": "1"})

        self.assertEqual(respuesta.status_code, 200)
        (entrega,) = respuesta.json()
        self.assertEqual(sorted(entrega), CLAVES_ENTREGA)
        self.assertEqual([sorted(linea) for linea in entrega["lineas"]], [CLAVES_LINEA_DE_ENTREGA] * 2)
        self.assertEqual(
            entrega,
            {
                "id": self.entrega.pk,
                "numero": self.entrega.numero,
                "estado": "EN_CAMINO",
                "despachada_en": "2026-11-12T10:00:00-03:00",
                "recibida_en": None,
                "observacion_mesa": "Entregar a la directora.",
                "observacion_dispositivo": "",
                "lineas": [
                    {"item": self.colchon.pk, "nombre": "Colchón", "unidad": "unidad", "enviada": 10, "recibida": None},
                    {
                        "item": self.alimentos.pk,
                        "nombre": "Kit alimentario",
                        "unidad": "kit",
                        "enviada": 3,
                        "recibida": None,
                    },
                ],
            },
        )

    def test_pendientes_son_las_en_camino_y_las_preparadas_de_ese_dispositivo(self):
        preparada = servicio_kits.crear_entrega(self.operador, self.club, [(self.colchon, 1)])
        cancelada = servicio_kits.crear_entrega(self.operador, self.club, [(self.colchon, 1)])
        servicio_kits.cancelar_entrega(cancelada, self.operador, "Error de carga")
        self._entrega_en_camino(self.escuela)

        pendientes = self._como(self.deposito).get(self._url_entregas(self.club), {"pendientes": "1"}).json()
        todas = self._como(self.deposito).get(self._url_entregas(self.club)).json()

        self.assertEqual([e["numero"] for e in pendientes], [self.entrega.numero, preparada.numero])
        self.assertEqual([e["estado"] for e in pendientes], ["EN_CAMINO", "PREPARADA"])
        # Sin el filtro, todas las del dispositivo, de la más nueva a la más vieja.
        self.assertEqual([e["numero"] for e in todas], [cancelada.numero, preparada.numero, self.entrega.numero])

    def test_un_dispositivo_que_no_existe_o_que_no_es_suyo_es_404(self):
        cliente = self._como(self.deposito)

        for url in (self._url_entregas(self.escuela), "/api/emergencia/dispositivos/999999/entregas/"):
            with self.subTest(url=url):
                self.assertEqual(cliente.get(url).status_code, 404)

    def test_el_detalle_es_la_misma_forma_que_la_lista(self):
        cliente = self._como(self.deposito)

        detalle = cliente.get(self._url_entrega(self.entrega))
        (de_la_lista,) = cliente.get(self._url_entregas(self.club), {"pendientes": "1"}).json()

        self.assertEqual(detalle.status_code, 200)
        self.assertEqual(sorted(detalle.json()), CLAVES_ENTREGA)
        self.assertEqual(detalle.json(), de_la_lista)

    def test_la_lista_no_crece_con_las_entregas(self):
        cliente = self._como(self.deposito)
        url = self._url_entregas(self.club)
        cliente.get(url, {"pendientes": "1"})
        with CaptureQueriesContext(connection) as con_una:
            cliente.get(url, {"pendientes": "1"})
        for _ in range(12):
            self._entrega_en_camino(self.club)

        with self.assertNumQueries(len(con_una)):
            respuesta = cliente.get(url, {"pendientes": "1"})
        self.assertEqual(len(respuesta.json()), 13)


class RecibirEntregaApiTests(BaseApiKits):
    def test_recibir_sin_diferencias_devuelve_estado_y_diferencias_vacias(self):
        respuesta = self._recibir(observacion="Todo en orden.")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(sorted(respuesta.json()), CLAVES_RECEPCION)
        self.assertEqual(respuesta.json(), {"estado": "RECIBIDA", "diferencias": []})
        recibida = EntregaKit.objects.get(pk=self.entrega.pk)
        self.assertEqual((recibida.estado, recibida.recibida_por), (EntregaKit.Estado.RECIBIDA, self.deposito))
        self.assertEqual(recibida.observacion_dispositivo, "Todo en orden.")
        self.assertTrue(recibida.remito.name.startswith(f"emergencia/entregas/{recibida.carpeta_media}/"))

    def test_recibir_con_diferencias_las_lista_con_claves_exactas(self):
        respuesta = self._recibir(colchones=8, kits=4)

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["estado"], "RECIBIDA_CON_DIFERENCIAS")
        self.assertEqual([sorted(diferencia) for diferencia in cuerpo["diferencias"]], [CLAVES_DIFERENCIA] * 2)
        self.assertEqual(
            cuerpo["diferencias"],
            [
                {"item": self.colchon.pk, "enviada": 10, "recibida": 8},
                {"item": self.alimentos.pk, "enviada": 3, "recibida": 4},
            ],
        )

    def test_es_la_misma_funcion_que_la_recepcion_web(self):
        """RU-2: la API no reimplementa nada; llama a ``recibir_entrega`` con lo que tradujo."""
        with mock.patch(
            "programas.api.views_emergencia_kits.servicio_kits.recibir_entrega", wraps=servicio_kits.recibir_entrega
        ) as espia:
            envio = uuid.uuid4()
            self._recibir(colchones=8, uuid_cliente=envio, observacion="Faltaron dos.")

        (llamada,) = espia.call_args_list
        entrega, usuario, cantidades, remito = llamada.args
        self.assertEqual((entrega.pk, usuario), (self.entrega.pk, self.deposito))
        self.assertEqual(cantidades, {self.colchon.pk: 8, self.alimentos.pk: 3})
        self.assertEqual(remito.name, "remito.jpg")
        self.assertEqual(llamada.kwargs, {"observacion": "Faltaron dos.", "uuid_cliente": envio})

    def test_recibir_una_preparada_vale(self):
        preparada = servicio_kits.crear_entrega(self.operador, self.club, [(self.colchon, 2)])

        respuesta = self._como(self.deposito).post(
            self._url_recibir(preparada),
            {"uuid_cliente": str(uuid.uuid4()), f"cantidades[{self.colchon.pk}]": 2, "remito": self._foto("r.jpg")},
            format="multipart",
        )

        self.assertEqual((respuesta.status_code, respuesta.json()["estado"]), (200, "RECIBIDA"))

    def test_el_mismo_uuid_dos_veces_recibe_una_sola_vez(self):
        """RU-16 / RN-4.4: el reenvío devuelve lo mismo, sin validar ni reescribir."""
        envio = uuid.uuid4()
        primera = self._recibir(colchones=8, uuid_cliente=envio)
        antes = self._foto_de(self.entrega)

        # El reenvío llega sin remito y con otras cantidades: no se mira nada.
        segunda = self._recibir(colchones=1, kits=1, remito=None, uuid_cliente=envio)

        self.assertEqual((primera.status_code, segunda.status_code), (200, 200))
        self.assertEqual(segunda.json(), primera.json())
        self.assertEqual(self._foto_de(self.entrega), antes)

    def test_ya_recibida_con_otro_uuid_es_409_con_el_estado(self):
        self._recibir(colchones=8)
        antes = self._foto_de(self.entrega)

        respuesta = self._recibir(colchones=10)

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(sorted(respuesta.json()), CLAVES_ESTADO_CAMBIO)
        self.assertEqual(respuesta.json()["estado_actual"], "RECIBIDA_CON_DIFERENCIAS")
        self.assertIn("ya la recibió", respuesta.json()["detail"])
        self.assertEqual(self._foto_de(self.entrega), antes)

    def test_recibida_desde_el_backoffice_es_409_para_la_app(self):
        servicio_kits.recibir_entrega(
            self.entrega, self.deposito, {self.colchon.pk: 10, self.alimentos.pk: 3}, self._foto("remito.jpg")
        )

        respuesta = self._recibir()

        self.assertEqual((respuesta.status_code, respuesta.json()["estado_actual"]), (409, "RECIBIDA"))

    def test_cancelada_por_la_mesa_es_409_y_dice_cuando(self):
        self.reloj.avanzar(hours=5, minutes=2)
        servicio_kits.cancelar_entrega(self.entrega, self.operador, "El camión volvió")

        respuesta = self._recibir()

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(
            respuesta.json(),
            {
                "detail": f"Entrega {self.entrega.numero} cancelada por la mesa a las 15:02. Ya no se puede recibir.",
                "estado_actual": "CANCELADA",
            },
        )
        self.assertFalse(EntregaKit.objects.get(pk=self.entrega.pk).remito)

    def test_el_uuid_de_la_recepcion_de_otra_entrega_es_409_uuid_en_uso(self):
        envio = uuid.uuid4()
        self._recibir(uuid_cliente=envio)
        otra = self._entrega_en_camino(self.club)

        respuesta = self._recibir(url=self._url_recibir(otra), uuid_cliente=envio)

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(sorted(respuesta.json()), CLAVES_UUID_EN_USO)
        self.assertEqual(respuesta.json()["code"], "UUID_EN_USO")
        self.assertEqual(EntregaKit.objects.get(pk=otra.pk).estado, EntregaKit.Estado.EN_CAMINO)

    def test_el_409_de_la_recepcion_sale_por_tipo_aunque_cambie_el_texto(self):
        """``UuidEnUso`` también en la recepción: la vista no compara el mensaje (PR #1130).

        **Mutación vista en rojo:** con la vista comparando otra vez ``errores["uuid_cliente"]``
        contra ``[servicio_kits.UUID_EN_USO]``, un ``UuidEnUso`` con otro texto sale como 400
        ``VALIDACION``. Restaurada la captura por tipo, verde.
        """
        otro_texto = UuidEnUso("Ese identificador ya es de otra entrega.")

        with mock.patch.object(servicio_kits, "_exigir_uuid_libre", side_effect=otro_texto):
            respuesta = self._recibir(uuid_cliente=uuid.uuid4())

        self.assertEqual(respuesta.status_code, 409, respuesta.content)
        self.assertEqual(
            respuesta.json(), {"detail": "Ese identificador ya es de otra entrega.", "code": "UUID_EN_USO"}
        )
        self.assertEqual(EntregaKit.objects.get(pk=self.entrega.pk).estado, EntregaKit.Estado.EN_CAMINO)

    def _es_400_en(self, respuesta, campo, mensaje):
        self.assertEqual(respuesta.status_code, 400)
        cuerpo = respuesta.json()
        self.assertEqual(set(cuerpo), CLAVES_FIJAS_DEL_400 | {campo})
        self.assertEqual(cuerpo["code"], "VALIDACION")
        self.assertEqual(cuerpo[campo], [mensaje])
        self.assertEqual(cuerpo["detail"], mensaje)
        self.assertEqual(EntregaKit.objects.get(pk=self.entrega.pk).estado, EntregaKit.Estado.EN_CAMINO)

    def test_sin_remito_es_400_en_remito(self):
        self._es_400_en(self._recibir(remito=None), "remito", "Falta la foto del remito.")

    def test_un_png_es_400_en_remito(self):
        png = SimpleUploadedFile("remito.png", PNG, content_type="image/png")
        disfrazado = SimpleUploadedFile("remito.jpg", PNG, content_type="image/jpeg")

        for remito in (png, disfrazado):
            with self.subTest(remito=remito.name):
                self._es_400_en(self._recibir(remito=remito), "remito", servicio_kits.REMITO_NO_ES_JPEG)

    def test_un_remito_de_mas_de_5_mb_es_400(self):
        pasado = SimpleUploadedFile(
            "remito.jpg", JPEG + b"0" * (ADJUNTO_MAX_BYTES - len(JPEG) + 1), content_type="image/jpeg"
        )

        self._es_400_en(self._recibir(remito=pasado), "remito", MENSAJE_ADJUNTO_TAMANIO)

    def test_sin_uuid_cliente_es_400(self):
        cuerpo = self._recepcion()
        cuerpo.pop("uuid_cliente")

        respuesta = self._como(self.deposito).post(self.url_recibir, cuerpo, format="multipart")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("uuid_cliente", respuesta.json())
        self.assertEqual(respuesta.json()["code"], "VALIDACION")

    def test_sin_cantidades_es_400_en_cantidades(self):
        cuerpo = {"uuid_cliente": str(uuid.uuid4()), "remito": self._foto("remito.jpg")}

        respuesta = self._como(self.deposito).post(self.url_recibir, cuerpo, format="multipart")

        self._es_400_en(respuesta, "cantidades", MENSAJE_SIN_CANTIDADES)

    def test_falta_la_cantidad_de_un_item_es_400_y_dice_cual(self):
        respuesta = self._recibir(kits=None)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("Kit alimentario", respuesta.json()["cantidades"][0])
        self.assertEqual(EntregaKit.objects.get(pk=self.entrega.pk).estado, EntregaKit.Estado.EN_CAMINO)

    def test_una_cantidad_que_no_es_un_entero_cero_o_mas_es_400(self):
        for cantidad in ("-1", "ocho", "2.5"):
            with self.subTest(cantidad=cantidad):
                self._es_400_en(self._recibir(colchones=cantidad), "cantidades", MENSAJE_CANTIDADES_INVALIDAS)

    def test_una_cantidad_de_un_item_ajeno_es_400(self):
        ajeno = TipoKit.objects.create(nombre="Frazada", unidad="unidad")

        respuesta = self._recibir(**{f"cantidades[{ajeno.pk}]": 1})

        self._es_400_en(respuesta, "cantidades", servicio_kits.ITEM_AJENO)

    def test_deja_la_novedad_en_la_bitacora_del_dispositivo(self):
        from datetime import time

        from programas.services.bitacora import crear_turno

        editor = self._guardia("editor_club", ["dispositivo.editar"], [self.club])
        crear_turno(dispositivo=self.club, usuario=editor, nombre="Guardia", hora_desde=time(8), hora_hasta=time(8))

        self._recibir()

        entrada = EntradaBitacora.objects.get()
        self.assertEqual(entrada.texto, f"Kit recibido N.° {self.entrega.numero}")
        self.assertEqual(entrada.origen, EntradaBitacora.Origen.AUTOMATICA)
