"""Stock en la app de campo, PR 7b (análisis 010, §17): las cuatro escrituras.

Qué fija este archivo:

* Las claves exactas de cada respuesta y ``Cache-Control: no-store``.
* 201 la primera vez y 200 con ``ya_existia`` el reenvío, que **no mueve el saldo**; un reenvío con el cuerpo
  malformado es 400.
* Cada rechazo con su ``code``: 400 ``VALIDACION`` y ``PERSONA_SIN_DATOS``; 409 ``SALDO_INSUFICIENTE`` (con los
  saldos), ``SALDO_CAMBIO``, ``UUID_EN_USO`` y ``STOCK_NO_HABILITADO``.
* Permiso por acción sobre el par (403 ``SIN_PERMISO``), 404 fuera de alcance con el mismo cuerpo que lo inexistente.
* Nunca negativo por API, aun con dos uuid distintos; el libro queda coherente.
* 429 de la cubeta ``stock_escritura``.

Mutaciones verificadas (romper la regla pone rojo el test que se nombra; ver el cuerpo del PR):

* ``puede_ajustar`` con ``CAP_STOCK_INGRESAR`` en vez de ``CAP_STOCK_AJUSTAR`` →
  ``test_cada_accion_exige_su_capacidad`` (el que solo ingresa ajusta);
* sacar el ``if not self.puede`` de ``_EscrituraDeStockView.post`` **y** el ``_exigir`` del servicio →
  ``test_cada_accion_exige_su_capacidad`` (con uno solo en pie sigue verde: son dos barreras);
* ``_exigir_saldo`` sin efecto → ``test_nunca_negativo_dos_envios_del_ultimo_item`` (la base lo ataja con el CHECK);
* ``_par`` sin ``edificio_de_stock`` (solo vínculo con la institución) →
  ``test_alcance_edificios_solo_opera_en_los_suyos``.
"""

from unittest import mock
from uuid import uuid4

from django.urls import reverse

from programas.api.throttles import StockEscrituraThrottle
from programas.models import Dispositivo, MovimientoStock, OperacionStock
from programas.tests.base_emergencia_api import CLAVES_STOCK_MOVIMIENTO_OPERACION, CLAVES_STOCK_OPERACION
from programas.tests.base_stock import TODAS_LAS_DE_STOCK
from programas.tests.test_emergencia_api_stock_lectura import BaseApiStock


class BaseEscritura(BaseApiStock):
    def setUp(self):
        super().setUp()
        # Todas las capacidades de stock y ``ciudadano.ver``: el rol «completo» de la base no entrega.
        self.op = self._usuario_con("operador", (*TODAS_LAS_DE_STOCK, "ciudadano.ver"))

    def _post(self, usuario, nombre, cuerpo, dispositivo=None, edificio=None):
        return self._como(usuario).post(self._url(nombre, dispositivo, edificio), cuerpo, format="json")

    def _entrega(self, lineas=None, **extra):
        return {
            "uuid_cliente": str(uuid4()),
            "dni": "30111222",
            "lineas": lineas or [{"item_id": self.colchon.pk, "cantidad": 1}],
            **extra,
        }

    def _ingreso(self, lineas=None, **extra):
        return {
            "uuid_cliente": str(uuid4()),
            "lineas": lineas or [{"item_id": self.colchon.pk, "cantidad": 5}],
            "origen": "DONACION",
            **extra,
        }

    def _traspaso(self, **extra):
        return {
            "uuid_cliente": str(uuid4()),
            "destino_dispositivo_id": self.disp.pk,
            "destino_edificio_id": self.otro_edificio.pk,
            "lineas": [{"item_id": self.colchon.pk, "cantidad": 2}],
            **extra,
        }

    def _ajuste(self, **extra):
        return {
            "uuid_cliente": str(uuid4()),
            "item_id": self.colchon.pk,
            "cantidad_contada": 3,
            "saldo_visto": 10,
            "motivo": "CONTEO_PERIODICO",
            **extra,
        }


class RespuestasTests(BaseEscritura):
    def test_claves_exactas_de_las_cuatro_y_no_store(self):
        self._sembrar(self.colchon, 10)
        casos = [
            ("stock-entregar", self._entrega(), "ENTREGA_PERSONA", -1),
            ("stock-ingresar", self._ingreso(), "INGRESO_MANUAL", 5),
            ("stock-traspasar", self._traspaso(), "TRASPASO", -2),
            ("stock-ajustar", self._ajuste(saldo_visto=12, cantidad_contada=9), "AJUSTE", -3),
        ]
        for nombre, cuerpo, tipo, delta in casos:
            with self.subTest(nombre):
                respuesta = self._post(self.op, nombre, cuerpo)
                self.assertEqual(respuesta.status_code, 201, respuesta.content)
                datos = respuesta.json()
                self.assertEqual(sorted(datos), CLAVES_STOCK_OPERACION)
                self.assertEqual(datos["tipo"], tipo)
                self.assertFalse(datos["ya_existia"])
                self.assertEqual(datos["uuid_cliente"], cuerpo["uuid_cliente"])
                self.assertEqual(len(datos["movimientos"]), 1)
                self.assertEqual(sorted(datos["movimientos"][0]), CLAVES_STOCK_MOVIMIENTO_OPERACION)
                self.assertEqual(datos["movimientos"][0]["cantidad"], delta)
                self.assertEqual(respuesta["Cache-Control"], "no-store")
        self.assertLibroCoherente()

    def test_el_traspaso_no_nombra_el_otro_lado(self):
        self._sembrar(self.colchon, 10)
        datos = self._post(self.op, "stock-traspasar", self._traspaso()).json()
        self.assertEqual({m["cantidad"] for m in datos["movimientos"]}, {-2})
        self.assertEqual(self._cantidad(self.colchon, self.otro_edificio), 2)

    def test_la_entrega_no_devuelve_datos_de_la_persona(self):
        self._sembrar(self.colchon, 3)
        respuesta = self._post(self.op, "stock-entregar", self._entrega())
        self.assertNotIn("Ana", respuesta.content.decode())
        self.assertNotIn("30111222", respuesta.content.decode())

    def test_el_ingreso_con_otro_pide_detalle(self):
        sin_detalle = self._post(self.op, "stock-ingresar", self._ingreso(origen="OTRO"))
        self.assertEqual(sin_detalle.status_code, 400)
        self.assertIn("origen_detalle", sin_detalle.json())
        con_detalle = self._post(self.op, "stock-ingresar", self._ingreso(origen="OTRO", origen_detalle="Vecinos"))
        self.assertEqual(con_detalle.status_code, 201)


class IdempotenciaTests(BaseEscritura):
    def test_el_reenvio_da_200_y_no_mueve_el_saldo(self):
        self._sembrar(self.colchon, 10)
        casos = [  # el ajuste va primero: ``saldo_visto`` es el de la siembra
            ("stock-ajustar", self._ajuste(saldo_visto=10, cantidad_contada=4)),
            ("stock-entregar", self._entrega()),
            ("stock-ingresar", self._ingreso()),
            ("stock-traspasar", self._traspaso()),
        ]
        for nombre, cuerpo in casos:
            with self.subTest(nombre):
                primera = self._post(self.op, nombre, cuerpo)
                saldo = self._cantidad(self.colchon)
                operaciones = OperacionStock.objects.count()
                segunda = self._post(self.op, nombre, cuerpo)
                self.assertEqual((primera.status_code, segunda.status_code), (201, 200))
                self.assertTrue(segunda.json()["ya_existia"])
                self.assertEqual(segunda.json()["id"], primera.json()["id"])
                self.assertEqual(segunda.json()["movimientos"], primera.json()["movimientos"])
                self.assertEqual(self._cantidad(self.colchon), saldo)
                self.assertEqual(OperacionStock.objects.count(), operaciones)
        self.assertLibroCoherente()

    def test_un_reenvio_con_el_cuerpo_malformado_es_400(self):
        self._sembrar(self.colchon, 10)
        cuerpo = self._entrega()
        self.assertEqual(self._post(self.op, "stock-entregar", cuerpo).status_code, 201)
        saldo = self._cantidad(self.colchon)
        for malformado in ({**cuerpo, "lineas": "mucho"}, {**cuerpo, "lineas": []}, {**cuerpo, "lineas": [{"x": 1}]}):
            with self.subTest(lineas=malformado["lineas"]):
                respuesta = self._post(self.op, "stock-entregar", malformado)
                self.assertEqual(respuesta.status_code, 400)
                self.assertEqual(respuesta.json()["code"], "VALIDACION")
        sin_uuid = {k: v for k, v in cuerpo.items() if k != "uuid_cliente"}
        self.assertEqual(self._post(self.op, "stock-entregar", sin_uuid).status_code, 400)
        self.assertEqual(self._cantidad(self.colchon), saldo)

    def test_el_uuid_de_otro_usuario_o_de_otro_lugar_es_409_uuid_en_uso(self):
        self._sembrar(self.colchon, 10)
        cuerpo = self._ingreso()
        self.assertEqual(self._post(self.op, "stock-ingresar", cuerpo).status_code, 201)
        otro = self._usuario_con("otro_carga", ("stock.ver", "stock.ingresar"))
        for usuario, nombre, edificio in (
            (otro, "stock-ingresar", None),
            (self.op, "stock-ingresar", self.otro_edificio),
            (self.op, "stock-entregar", None),
        ):
            with self.subTest(usuario=usuario.username, nombre=nombre):
                envio = cuerpo if nombre == "stock-ingresar" else self._entrega(uuid_cliente=cuerpo["uuid_cliente"])
                respuesta = self._post(usuario, nombre, envio, edificio=edificio)
                self.assertEqual(respuesta.status_code, 409)
                self.assertEqual(respuesta.json()["code"], "UUID_EN_USO")
        self.assertEqual(self._cantidad(self.colchon), 15)


class RechazosTests(BaseEscritura):
    def test_saldo_insuficiente_trae_los_saldos(self):
        self._sembrar(self.colchon, 2)
        self._sembrar(self.frazada, 9)
        cuerpo = self._entrega(
            lineas=[{"item_id": self.colchon.pk, "cantidad": 5}, {"item_id": self.frazada.pk, "cantidad": 1}]
        )
        respuesta = self._post(self.op, "stock-entregar", cuerpo)
        self.assertEqual(respuesta.status_code, 409)
        datos = respuesta.json()
        self.assertEqual(datos["code"], "SALDO_INSUFICIENTE")
        self.assertEqual(
            {s["item_id"]: (s["cantidad"], s["alcanza"]) for s in datos["saldos"]},
            {self.colchon.pk: (2, False), self.frazada.pk: (9, True)},
        )
        self.assertEqual(sorted(datos["saldos"][0]), ["alcanza", "cantidad", "item_id", "nombre", "unidad"])
        self.assertEqual(self._cantidad(self.colchon), 2)
        self.assertEqual(self._cantidad(self.frazada), 9)

    def test_el_traspaso_sin_saldo_tambien_es_409(self):
        self._sembrar(self.colchon, 1)
        respuesta = self._post(self.op, "stock-traspasar", self._traspaso())
        self.assertEqual((respuesta.status_code, respuesta.json()["code"]), (409, "SALDO_INSUFICIENTE"))

    def test_saldo_cambio(self):
        self._sembrar(self.colchon, 7)
        respuesta = self._post(self.op, "stock-ajustar", self._ajuste(saldo_visto=10))
        self.assertEqual(respuesta.status_code, 409)
        datos = respuesta.json()
        self.assertEqual((datos["code"], datos["saldo_actual"], datos["saldo_visto"]), ("SALDO_CAMBIO", 7, 10))
        self.assertEqual(self._cantidad(self.colchon), 7)

    def test_stock_no_habilitado_con_la_institucion_inactiva(self):
        self._sembrar(self.colchon, 5)
        Dispositivo.objects.filter(pk=self.disp.pk).update(estado=Dispositivo.Estado.INACTIVO)
        for nombre, cuerpo in (("stock-ingresar", self._ingreso()), ("stock-entregar", self._entrega())):
            with self.subTest(nombre):
                respuesta = self._post(self.op, nombre, cuerpo)
                self.assertEqual((respuesta.status_code, respuesta.json()["code"]), (409, "STOCK_NO_HABILITADO"))
        self.assertEqual(self._cantidad(self.colchon), 5)

    def test_validacion_por_campo(self):
        self._sembrar(self.colchon, 5)
        casos = [
            ("stock-ingresar", self._ingreso(origen="REGALO"), "origen"),
            ("stock-ingresar", self._ingreso(lineas=[{"item_id": self.colchon.pk, "cantidad": 0}]), "lineas"),
            (
                "stock-ingresar",
                self._ingreso(lineas=[{"item_id": self.colchon.pk, "cantidad": 1}] * 2),
                "lineas",
            ),
            ("stock-entregar", self._entrega(dni="12"), "dni"),
            ("stock-traspasar", self._traspaso(destino_edificio_id=self.edificio_b.pk), "destino"),
            ("stock-ajustar", self._ajuste(item_id=999999), "item_id"),
            ("stock-ajustar", self._ajuste(motivo="OTRO"), "detalle"),
            ("stock-ajustar", self._ajuste(saldo_visto=5, cantidad_contada=5), "cantidad_contada"),
        ]
        for nombre, cuerpo, campo in casos:
            with self.subTest(nombre=nombre, campo=campo):
                respuesta = self._post(self.op, nombre, cuerpo)
                self.assertEqual(respuesta.status_code, 400, respuesta.content)
                self.assertEqual(respuesta.json()["code"], "VALIDACION")
                self.assertIn(campo, respuesta.json())
        self.assertEqual(self._cantidad(self.colchon), 5)

    def test_persona_sin_datos(self):
        self._sembrar(self.colchon, 5)
        for extra, pide_sexo in (({}, True), ({"sexo": "F"}, False)):
            with self.subTest(extra), mock.patch(self.CONSULTA_RENAPER, return_value=self.RENAPER_NO_ESTA):
                respuesta = self._post(self.op, "stock-entregar", self._entrega(dni="40999888", **extra))
                self.assertEqual(respuesta.status_code, 400)
                datos = respuesta.json()
                self.assertEqual(datos["code"], "PERSONA_SIN_DATOS")
                self.assertEqual(datos["pide_sexo"], pide_sexo)
                self.assertIn("motivo", datos)
        self.assertEqual(self._cantidad(self.colchon), 5)

    def test_entrega_a_una_persona_nueva_con_nombre_y_apellido(self):
        self._sembrar(self.colchon, 5)
        respuesta = self._post(
            self.op, "stock-entregar", self._entrega(dni="40999888", nombre="Luis", apellido="Gómez")
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.assertEqual(self._cantidad(self.colchon), 4)


class PermisosYAlcanceTests(BaseEscritura):
    def test_cada_accion_exige_su_capacidad(self):
        """Ve el edificio pero no tiene la capacidad de la acción: 403 ``SIN_PERMISO`` y no se mueve nada.

        **Mutación vista en rojo:** ``puede_ajustar`` con ``CAP_STOCK_INGRESAR`` deja ajustar a quien solo ingresa.
        """

        self._sembrar(self.colchon, 10)
        usuarios = {
            "stock-entregar": ("solo_ingresa", ("stock.ver", "stock.ingresar", "ciudadano.ver")),
            "stock-ingresar": ("solo_entrega", ("stock.ver", "stock.entregar", "ciudadano.ver")),
            "stock-traspasar": ("solo_ajusta", ("stock.ver", "stock.ajustar")),
            "stock-ajustar": ("solo_ingresa_2", ("stock.ver", "stock.ingresar")),
        }
        cuerpos = {
            "stock-entregar": self._entrega(),
            "stock-ingresar": self._ingreso(),
            "stock-traspasar": self._traspaso(),
            "stock-ajustar": self._ajuste(saldo_visto=10),
        }
        for nombre, (usuario, capacidades) in usuarios.items():
            with self.subTest(nombre):
                respuesta = self._post(self._usuario_con(usuario, capacidades), nombre, cuerpos[nombre])
                self.assertEqual(respuesta.status_code, 403)
                self.assertEqual(respuesta.json()["code"], "SIN_PERMISO")
        self.assertEqual(self._cantidad(self.colchon), 10)
        self.assertEqual(OperacionStock.objects.filter(tipo=OperacionStock.Tipo.AJUSTE).count(), 0)

    def test_entregar_exige_ciudadano_ver(self):
        self._sembrar(self.colchon, 3)
        sin_ciudadano = self._usuario_con("sin_ciudadano", ("stock.ver", "stock.entregar"))
        with mock.patch(self.CONSULTA_RENAPER) as registro:
            respuesta = self._post(sin_ciudadano, "stock-entregar", self._entrega(sexo="F"))
        self.assertEqual((respuesta.status_code, respuesta.json()["code"]), (403, "SIN_PERMISO"))
        registro.assert_not_called()

    def test_el_403_va_antes_que_el_400(self):
        respuesta = self._post(self.ve, "stock-ingresar", {})
        self.assertEqual(respuesta.status_code, 403)

    def test_sin_modulo_ni_stock_es_403_sin_modulo(self):
        ajeno = self._otro_usuario("sin_nada")
        respuesta = self._post(ajeno, "stock-ingresar", self._ingreso())
        self.assertEqual((respuesta.status_code, respuesta.json()["code"]), (403, "SIN_MODULO"))

    def test_alcance_edificios_solo_opera_en_los_suyos(self):
        self._sembrar(self.colchon, 5)
        usuario = self._de_edificios("de_un_edificio", [self.edificio], ("stock.ver", "stock.ingresar"))
        propio = self._post(usuario, "stock-ingresar", self._ingreso())
        ajeno = self._post(usuario, "stock-ingresar", self._ingreso(), edificio=self.otro_edificio)
        self.assertEqual(propio.status_code, 201)
        self.assertEqual(ajeno.status_code, 404)
        self.assertEqual(self._cantidad(self.colchon, self.otro_edificio), 0)

    def test_404_fuera_de_alcance_es_igual_a_inexistente(self):
        """Institución ajena, inexistente, edificio no vinculado o inexistente: el mismo 404, sin escribir.

        El alcance **Edificios** (que sí distingue ``edificio_de_stock``) lo cubre
        ``test_alcance_edificios_solo_opera_en_los_suyos``.
        """

        cuerpo = self._ingreso()
        inexistente = self._como(self.op).post(
            reverse("emergencia_api:stock-ingresar", args=(999999, 999999)), cuerpo, format="json"
        )
        self.assertEqual(inexistente.status_code, 404)
        for dispositivo, edificio in (
            (self.disp, self.edificio_b),
            (self.disp_b, self.edificio_b),
        ):
            with self.subTest(dispositivo=dispositivo.pk, edificio=edificio.pk):
                respuesta = self._post(self.op, "stock-ingresar", cuerpo, dispositivo, edificio)
                self.assertEqual(respuesta.status_code, 404)
                self.assertEqual(respuesta.json(), inexistente.json())
        self.assertEqual(self._post(self.op, "stock-ingresar", cuerpo).status_code, 201)
        self.assertEqual(OperacionStock.objects.count(), 1)


class NuncaNegativoTests(BaseEscritura):
    def test_nunca_negativo_dos_envios_del_ultimo_item(self):
        """Dos entregas del último insumo, con dos uuid distintos: la segunda es 409 y el saldo queda en 0.

        **Mutación vista en rojo:** ``_exigir_saldo`` sin efecto deja pasar la segunda (y la base la ataja con el CHECK).
        """

        self._sembrar(self.colchon, 1)
        primera = self._post(self.op, "stock-entregar", self._entrega())
        segunda = self._post(self.op, "stock-entregar", self._entrega())
        self.assertEqual(primera.status_code, 201)
        self.assertEqual((segunda.status_code, segunda.json()["code"]), (409, "SALDO_INSUFICIENTE"))
        self.assertEqual(self._cantidad(self.colchon), 0)
        self.assertEqual(MovimientoStock.objects.filter(item=self.colchon).count(), 2)  # la siembra y la entrega
        self.assertLibroCoherente()


class CubetaTests(BaseEscritura):
    @mock.patch.object(StockEscrituraThrottle, "get_rate", return_value="2/hour")
    def test_la_cubeta_de_escrituras_corta_con_429(self, _rate):
        self._sembrar(self.colchon, 5)
        estados = [self._post(self.op, "stock-ingresar", self._ingreso()).status_code for _ in range(3)]
        self.assertEqual(estados, [201, 201, 429])
        self.assertEqual(self._cantidad(self.colchon), 15)
        denegada = self._post(self.op, "stock-ingresar", self._ingreso())
        self.assertIn("Retry-After", denegada)

    @mock.patch.object(StockEscrituraThrottle, "get_rate", return_value="1/hour")
    def test_sin_modulo_no_gasta_la_cubeta(self, _rate):
        ajeno = self._otro_usuario("sin_nada_2")
        for _ in range(3):
            self.assertEqual(self._post(ajeno, "stock-ingresar", self._ingreso()).status_code, 403)
