"""Stock en la app de campo, PR 7a (análisis 010, §10, §12 y §17): lectura, perfil y recepción con edificio.

Qué fija este archivo:

* Las claves exactas de cada respuesta (el contrato que lee Chaco-mobile) y ``Cache-Control: no-store``.
* 403 ``SIN_MODULO`` (no ve stock) y 403 ``SIN_PERMISO`` (ve el edificio, no tiene la capacidad de la consulta).
* 404 fuera de alcance **con el mismo cuerpo que lo inexistente**: ajeno, no vinculado, sin stock, alcance Edificios.
* Quien **solo** lleva stock abre el módulo (login con ``"emergencia"``, perfil ``stock: true``).
* La consulta de persona descuenta de la cubeta ``personas_campo``, no escribe y no nombra otras instituciones.
* ``puede`` de la lista (armado por conjuntos) coincide con los predicados del servicio.
* La recepción de una entrega sin edificio acepta ``edificio_id`` (y rechaza lo inválido con esa clave).

Mutaciones verificadas (romper la regla pone rojo el test que se nombra; ver el cuerpo del PR):

* sacar ``stock.ver`` de ``_lleva_stock_en_su_equipo`` (``modulo_habilitado``) →
  ``test_quien_solo_lleva_stock_abre_el_modulo``;
* sacar el ``q_edificios_en_alcance`` de ``dispositivos.pares_en_alcance`` →
  ``test_la_lista_solo_trae_lo_que_alcanza`` y ``test_con_alcance_edificios_la_lista_trae_solo_los_suyos``
  (el ``dispositivo_id__in`` de ese mismo filtro es redundante con ``q_edificios_en_alcance``: sacarlo solo no da
  rojo, y no es una fuga);
* sacar el chequeo de alcance de ``edificio_de_la_institucion`` (el que usa ``edificio_de_stock`` con ``stock.ver``) →
  ``test_404_fuera_de_alcance_es_igual_a_inexistente``;
* sacar el ``puede_entregar`` de ``PersonaDelStockView.get`` → ``test_la_persona_exige_poder_entregar``;
* ``EmergenciaModuloPermission`` con ``modulo_habilitado`` (suma stock) en vez de ``modulo_de_campo_habilitado`` →
  ``test_quien_solo_lleva_stock_no_consulta_identidades`` y el barrido
  ``test_quien_solo_lleva_stock_recibe_el_mismo_403_de_antes_en_toda_la_api_de_campo``.
"""

import shutil
import tempfile
from unittest import mock
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from legajos.models import Ciudadano
from programas.api.throttles import ConsultaPersonasThrottle
from programas.models import (
    Edificio,
    EntregaKit,
    LineaEntrega,
    MiembroEquipoDispositivo,
    MovimientoStock,
    OperacionStock,
)
from programas.services import stock as servicio
from programas.services.emergencia_programa import modulo_de_campo_habilitado, modulo_habilitado, roles_en_app
from programas.tests.base_emergencia_api import (
    CLAVES_ENTREGA,
    CLAVES_PERFIL,
    CLAVES_SIN_MODULO,
    SIN_MODULO,
    SIN_RELEVAR,
    SOLO_DEL_AGENTE,
    URL_CONSULTAR,
    URL_PERFIL,
    URLS_DE_STOCK_DEL_BARRIDO,
    urls_de_la_api_de_emergencia,
)
from programas.tests.base_stock import BaseEntrega
from programas.tests.test_emergencia_casos import JPEG

Alcance = MiembroEquipoDispositivo.Alcance

CLAVES_PAR = ["dispositivo", "edificio", "insumos_con_saldo", "puede"]
CLAVES_PUEDE = ["ajustar", "entregar", "ingresar"]
CLAVES_BREVE = ["id", "nombre"]
CLAVES_STOCK_EDIFICIO = ["dispositivo", "edificio", "insumos_activos", "puede", "saldos"]
CLAVES_SALDO = ["activo", "cantidad", "item_id", "nombre", "unidad"]
CLAVES_INSUMO_ACTIVO = ["item_id", "nombre", "unidad"]
CLAVES_PAGINA = ["resultados", "siguiente"]
CLAVES_MOVIMIENTO = [
    "cantidad",
    "creado_en",
    "detalle",
    "id",
    "item_id",
    "nombre",
    "saldo_posterior",
    "tipo",
    "unidad",
    "usuario",
]
CLAVES_DESTINO = ["dispositivo", "edificio"]
CLAVES_CONSULTA_PERSONA = ["historial", "persona"]
CLAVES_PERSONA = ["apellido", "dni", "nombre"]
CLAVES_HISTORIAL = ["creado_en", "institucion", "lineas"]
CLAVES_LINEA_HISTORIAL = ["cantidad", "nombre", "unidad"]


class BaseApiStock(BaseEntrega):
    """La institución con stock de ``BaseEntrega`` más lo de la app: token, login y URLs del namespace."""

    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        ajuste = override_settings(MEDIA_ROOT=self.media)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.ve = self._usuario_con("solo_ve", ("stock.ver",))

    def _como(self, usuario):
        token, _ = Token.objects.get_or_create(user=usuario)
        self.api.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        return self.api

    def _url(self, nombre, dispositivo=None, edificio=None):
        if nombre == "stock":
            return reverse("emergencia_api:stock")
        return reverse(
            f"emergencia_api:{nombre}",
            args=((dispositivo or self.disp).pk, (edificio or self.edificio).pk),
        )

    def _get(self, usuario, nombre, dispositivo=None, edificio=None, **parametros):
        return self._como(usuario).get(self._url(nombre, dispositivo, edificio), parametros)

    def _de_edificios(self, nombre, edificios, capacidades=("stock.ver",), dispositivo=None):
        """Un miembro con alcance **Edificios** sobre ``edificios``."""
        rol = self._rol(f"Rol {nombre}", ("dispositivo.ver", *capacidades))
        usuario = self._usuario(nombre, rol)
        miembro = MiembroEquipoDispositivo.objects.create(
            dispositivo=dispositivo or self.disp, usuario=usuario, rol=rol, alcance=Alcance.EDIFICIOS
        )
        miembro.edificios.set(edificios)
        return self._fresco(usuario)


# ---------------------------------------------------------------------------
# Quién entra (perfil y módulo)
# ---------------------------------------------------------------------------


class AccesoAlStockTests(BaseApiStock):
    def test_quien_solo_lleva_stock_abre_el_modulo(self):
        """``stock.ver`` en el Equipo de una institución con stock abre Emergencia aunque no tenga nada más.

        **Mutación vista en rojo:** sacar ``stock.ver`` de ``_lleva_stock_en_su_equipo`` deja a este usuario sin el
        módulo: el login no trae ``"emergencia"`` y todas las rutas contestan 403.
        **Mutación vista en rojo:** ``plazas`` sin ``modulo_de_campo_habilitado`` en ``roles_en_app``: el perfil dice
        ``plazas: true`` y ``edificios/`` contesta 403.
        """

        self.assertTrue(modulo_habilitado(self.ve))
        self.assertEqual(roles_en_app(self.ve)["stock"], True)
        self.assertFalse(roles_en_app(self.ve)["llegadas"])

        login = self.api.post(reverse("becas_api:token"), {"username": "solo_ve", "password": "x"}, format="json")
        self.assertEqual(login.status_code, 200)
        self.assertIn("emergencia", login.json()["modulos"])

        perfil = self._como(self.ve).get(reverse("emergencia_api:perfil"))
        self.assertEqual(perfil.status_code, 200)
        self.assertEqual(sorted(perfil.json()), CLAVES_PERFIL)
        self.assertIs(perfil.json()["stock"], True)
        # Plazas es de campo: tiene `dispositivo.ver`, pero esas rutas le dan 403, así que el perfil no se la ofrece.
        self.assertIs(perfil.json()["plazas"], False)
        self.assertEqual(self._como(self.ve).get(reverse("emergencia_api:edificios")).status_code, 403)
        self.assertEqual(self._get(self.ve, "stock").status_code, 200)

    def test_una_institucion_que_no_lleva_stock_no_abre_el_modulo(self):
        self.tipo.maneja_stock = False
        self.tipo.save()
        usuario = self._fresco(self.ve)

        self.assertFalse(modulo_habilitado(usuario))
        self.assertFalse(roles_en_app(usuario)["stock"])
        respuesta = self._get(usuario, "stock")
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(sorted(respuesta.json()), CLAVES_SIN_MODULO)

    def test_sin_stock_ver_no_hay_stock_aunque_el_modulo_este_abierto(self):
        """Abre Emergencia por otra capacidad, pero sin ``stock.ver`` el perfil dice ``stock: false`` y la API 403."""

        sin_ver = self._usuario_con("solo_entrega", ("stock.entregar", "emergencia.recibir_kit"))

        self.assertTrue(modulo_habilitado(sin_ver))
        self.assertFalse(roles_en_app(sin_ver)["stock"])
        for nombre in ("stock", "stock-edificio", "stock-movimientos", "stock-destinos-traspaso", "stock-persona"):
            with self.subTest(nombre):
                respuesta = self._get(sin_ver, nombre)
                self.assertEqual(respuesta.status_code, 403)
                self.assertEqual(respuesta.json()["code"], "SIN_MODULO")
                self.assertEqual(sorted(respuesta.json()), CLAVES_SIN_MODULO)

    def test_un_edificio_inactivo_no_cuenta_para_el_perfil_ni_la_lista(self):
        for edificio in (self.edificio, self.otro_edificio):
            edificio.activo = False
            edificio.save()
        usuario = self._fresco(self.ve)

        self.assertFalse(roles_en_app(usuario)["stock"])
        self.assertEqual(self._get(usuario, "stock").status_code, 403)

    def test_sin_token_es_401(self):
        self.api.credentials()
        for nombre in ("stock", "stock-edificio", "stock-movimientos", "stock-destinos-traspaso", "stock-persona"):
            with self.subTest(nombre):
                self.assertEqual(self.api.get(self._url(nombre)).status_code, 401)

    def test_quien_solo_lleva_stock_no_consulta_identidades(self):
        """``stock.ver`` abre el perfil y el stock, **no** la consulta de identidad: 403 ``SIN_MODULO`` como antes del PR.

        **Mutación vista en rojo:** con ``EmergenciaModuloPermission.has_permission`` llamando a ``modulo_habilitado``
        (el predicado que suma stock) en vez de ``modulo_de_campo_habilitado``, esta ruta contesta 200/404 con el
        legajo y el test falla; el barrido de abajo falla en todas las rutas de campo. Restaurada, verde.
        """

        self.assertTrue(modulo_habilitado(self.ve))
        self.assertFalse(modulo_de_campo_habilitado(self.ve))
        for datos in ({"dni": "30111222"}, {"dni": "30111222", "sexo": "F"}):
            with self.subTest(datos=datos):
                respuesta = self._como(self.ve).post(URL_CONSULTAR, datos, format="json")
                self.assertEqual(respuesta.status_code, 403)
                self.assertEqual(respuesta.json(), SIN_MODULO)

    def test_quien_solo_lleva_stock_recibe_el_mismo_403_de_antes_en_toda_la_api_de_campo(self):
        """Cada ruta del namespace salvo el perfil y el stock responde a ``stock.ver`` solo lo que antes del PR.

        Raíz, identidad, localidades, plazas, estadías, llegadas, kits y relevamiento: 403 con el cuerpo de siempre
        (``SIN_MODULO``; ``SIN_RELEVAR`` en las dos del agente).
        """

        propias_del_stock = {URL_PERFIL, *URLS_DE_STOCK_DEL_BARRIDO}
        cliente = self._como(self.ve)
        rutas = [url for url in urls_de_la_api_de_emergencia() if url not in propias_del_stock]
        self.assertGreater(len(rutas), 30)
        for url in rutas:
            esperado = SIN_RELEVAR if url in SOLO_DEL_AGENTE else SIN_MODULO
            for metodo in ("get", "post"):
                with self.subTest(url=url, metodo=metodo):
                    respuesta = getattr(cliente, metodo)(url, {}, format="json")
                    self.assertEqual(respuesta.status_code, 403)
                    self.assertEqual(respuesta.json(), esperado)


# ---------------------------------------------------------------------------
# GET stock/
# ---------------------------------------------------------------------------


class ListaDeStockTests(BaseApiStock):
    def test_claves_exactas_y_orden(self):
        self._sembrar(self.colchon, 5)
        self._sembrar(self.frazada, 2)

        respuesta = self._get(self.carga, "stock")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Cache-Control"], "no-store")
        filas = respuesta.json()
        self.assertEqual([f["edificio"]["nombre"] for f in filas], ["Edificio stock", "Otro edificio"])
        fila = filas[0]
        self.assertEqual(sorted(fila), CLAVES_PAR)
        self.assertEqual(sorted(fila["dispositivo"]), CLAVES_BREVE)
        self.assertEqual(sorted(fila["edificio"]), CLAVES_BREVE)
        self.assertEqual(sorted(fila["puede"]), CLAVES_PUEDE)
        self.assertEqual(fila["insumos_con_saldo"], 2)
        self.assertEqual(filas[1]["insumos_con_saldo"], 0)

    def test_un_insumo_en_cero_no_cuenta(self):
        self._sembrar(self.colchon, 5)
        self._sembrar(self.frazada, 0)

        self.assertEqual(self._get(self.carga, "stock").json()[0]["insumos_con_saldo"], 1)

    def test_la_lista_solo_trae_lo_que_alcanza(self):
        """**Mutación vista en rojo:** sin el filtro de alcance de ``_pares`` el usuario de A ve también el de B."""

        rol = self._rol("Stock de B", ("dispositivo.ver", "stock.ver"))
        de_b = self._miembro_con(rol, "de_b", dispositivo=self.disp_b)
        self.edificio_b.dispositivos.add(self.disp_b)

        de_a = [(f["dispositivo"]["id"], f["edificio"]["id"]) for f in self._get(self.ve, "stock").json()]
        de_la_b = [(f["dispositivo"]["id"], f["edificio"]["id"]) for f in self._get(de_b, "stock").json()]

        self.assertEqual(
            sorted(de_a), sorted([(self.disp.pk, self.edificio.pk), (self.disp.pk, self.otro_edificio.pk)])
        )
        self.assertEqual(de_la_b, [(self.disp_b.pk, self.edificio_b.pk)])

    def test_con_alcance_edificios_la_lista_trae_solo_los_suyos(self):
        de_uno = self._de_edificios("de_uno", [self.edificio])

        filas = self._get(de_uno, "stock").json()

        self.assertEqual([f["edificio"]["id"] for f in filas], [self.edificio.pk])

    def test_con_alcance_edificios_vacio_no_hay_stock(self):
        de_ninguno = self._de_edificios("de_ninguno", [])

        self.assertFalse(roles_en_app(de_ninguno)["stock"])
        self.assertEqual(self._get(de_ninguno, "stock").status_code, 403)

    def test_una_institucion_que_no_lleva_stock_no_aparece(self):
        """Un edificio vinculado a una institución cuyo tipo no lleva stock no se lista."""

        otro_tipo = type(self.tipo).objects.create(codigo="HOGAR", nombre="Hogar")
        disp_sin = type(self.disp).objects.create(
            tipo=otro_tipo, codigo="H-1", nombre="Disp H-1", estado=self.disp.estado
        )
        self.edificio_b.dispositivos.add(disp_sin)
        rol = self._rol("Stock en H", ("dispositivo.ver", "stock.ver"))
        usuario = self._miembro_con(rol, "en_hogar", dispositivo=disp_sin)
        self._miembro(self.disp, User.objects.get(pk=usuario.pk), rol)
        usuario = self._fresco(usuario)

        ids = {f["dispositivo"]["id"] for f in self._get(usuario, "stock").json()}

        self.assertEqual(ids, {self.disp.pk})

    def test_puede_de_la_lista_coincide_con_los_predicados_del_servicio(self):
        """Dos formas de calcular lo mismo (conjuntos y predicados) no pueden divergir, para ningún perfil."""

        perfiles = {
            "completo": self.guardia,
            "carga": self.carga,
            "ve": self.ve,
            "ingresa": self._usuario_con("solo_ingresa", ("stock.ver", "stock.ingresar")),
            "ajusta": self._usuario_con("solo_ajusta", ("stock.ver", "stock.ajustar")),
            "entrega_sin_ciudadano": self._usuario_con("sin_ciudadano", ("stock.ver", "stock.entregar")),
            "de_un_edificio": self._de_edificios(
                "de_un_edificio",
                [self.edificio],
                ("stock.ver", "stock.ingresar", "stock.entregar", "ciudadano.ver"),
            ),
        }
        for nombre, usuario in perfiles.items():
            for fila in self._get(usuario, "stock").json():
                with self.subTest(perfil=nombre, edificio=fila["edificio"]["id"]):
                    esperado = {
                        "entregar": servicio.puede_entregar(usuario, self.disp, fila["edificio"]["id"]),
                        "ingresar": servicio.puede_ingresar(usuario, self.disp, fila["edificio"]["id"]),
                        "ajustar": servicio.puede_ajustar(usuario, self.disp, fila["edificio"]["id"]),
                    }
                    self.assertEqual(fila["puede"], esperado)

    def test_el_costo_no_crece_con_los_insumos_ni_los_movimientos(self):
        self._sembrar(self.colchon, 5)
        self._get(self.carga, "stock")  # calienta cachés de ContentType/permisos
        pocas = self._consultas_de_la_lista()
        for i in range(5):
            self._sembrar(type(self.colchon).objects.create(nombre=f"Insumo {i}", unidad="u"), 3)
        self.assertEqual(self._consultas_de_la_lista(), pocas)

    def _consultas_de_la_lista(self):
        with CaptureQueriesContext(connection) as contexto:
            self._get(self.carga, "stock")
        return len(contexto)


# ---------------------------------------------------------------------------
# GET .../stock/
# ---------------------------------------------------------------------------


class StockDelEdificioTests(BaseApiStock):
    def test_claves_exactas_y_saldos(self):
        self._sembrar(self.colchon, 5)
        self._sembrar(self.viejo, 2)

        respuesta = self._get(self.carga, "stock-edificio")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Cache-Control"], "no-store")
        cuerpo = respuesta.json()
        self.assertEqual(sorted(cuerpo), CLAVES_STOCK_EDIFICIO)
        self.assertEqual(sorted(cuerpo["puede"]), CLAVES_PUEDE)
        self.assertEqual(sorted(cuerpo["saldos"][0]), CLAVES_SALDO)
        self.assertEqual(sorted(cuerpo["insumos_activos"][0]), CLAVES_INSUMO_ACTIVO)
        por_nombre = {s["nombre"]: s for s in cuerpo["saldos"]}
        self.assertEqual(por_nombre["Colchón stock"]["cantidad"], 5)
        self.assertIs(por_nombre["Colchón stock"]["activo"], True)
        self.assertEqual(por_nombre["Insumo viejo"]["cantidad"], 2)
        self.assertIs(por_nombre["Insumo viejo"]["activo"], False)
        nombres_activos = {i["nombre"] for i in cuerpo["insumos_activos"]}
        self.assertIn("Frazada stock", nombres_activos)
        self.assertNotIn("Insumo viejo", nombres_activos)

    def test_puede_dice_lo_que_el_usuario_hace_ahi(self):
        solo_ve = self._get(self.ve, "stock-edificio").json()["puede"]
        completo = self._get(self.guardia, "stock-edificio").json()["puede"]

        self.assertEqual(solo_ve, {"entregar": False, "ingresar": False, "ajustar": False})
        self.assertEqual(completo["entregar"], True)

    def test_404_fuera_de_alcance_es_igual_a_inexistente(self):
        """Ajeno, no vinculado, de institución sin stock, fuera de alcance y no existente: el mismo 404 y cuerpo.

        **Mutación vista en rojo:** sin el filtro de alcance de ``edificio_de_la_institucion`` el edificio fuera de alcance del
        usuario de un edificio contesta 200.
        """

        de_uno = self._de_edificios("de_uno", [self.edificio])
        rol = self._rol("Stock de B", ("dispositivo.ver", "stock.ver"))
        de_b = self._miembro_con(rol, "de_b", dispositivo=self.disp_b)
        inexistente = self.api.get(f"/api/emergencia/dispositivos/{self.disp.pk}/edificios/999999/stock/")  # sin token

        casos = {
            "inexistente": self._como(self.ve).get(
                f"/api/emergencia/dispositivos/{self.disp.pk}/edificios/999999/stock/"
            ),
            "dispositivo_inexistente": self._como(self.ve).get(
                f"/api/emergencia/dispositivos/999999/edificios/{self.edificio.pk}/stock/"
            ),
            "institucion_ajena": self._get(de_b, "stock-edificio"),
            "no_vinculado": self._get(self.ve, "stock-edificio", edificio=self.edificio_b),
            "fuera_del_alcance_edificios": self._get(de_uno, "stock-edificio", edificio=self.otro_edificio),
        }
        self.assertEqual(inexistente.status_code, 401)
        patron = casos["inexistente"]
        self.assertEqual(patron.status_code, 404)
        for nombre, respuesta in casos.items():
            with self.subTest(nombre):
                self.assertEqual(respuesta.status_code, 404)
                self.assertEqual(respuesta.json(), patron.json())
        # Las mismas respuestas para movimientos, destinos y persona.
        for ruta in ("stock-movimientos", "stock-destinos-traspaso", "stock-persona"):
            with self.subTest(ruta):
                ajena = self._get(de_b, ruta, dni="30111222")
                self.assertEqual(ajena.status_code, 404)
                self.assertEqual(ajena.json(), patron.json())

    def test_una_institucion_sin_stock_es_404_como_si_no_existiera(self):
        otro_tipo = type(self.tipo).objects.create(codigo="HOGAR", nombre="Hogar")
        sin_stock = type(self.disp).objects.create(
            tipo=otro_tipo, codigo="H-2", nombre="Disp H-2", estado=self.disp.estado
        )
        self.edificio.dispositivos.add(sin_stock)
        self._miembro(sin_stock, self.ve, self._rol("Ver en H", ("dispositivo.ver", "stock.ver")))
        usuario = self._fresco(self.ve)

        respuesta = self._get(usuario, "stock-edificio", dispositivo=sin_stock)
        inexistente = self._como(usuario).get(
            f"/api/emergencia/dispositivos/999999/edificios/{self.edificio.pk}/stock/"
        )

        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(respuesta.json(), inexistente.json())


# ---------------------------------------------------------------------------
# GET .../stock/movimientos/
# ---------------------------------------------------------------------------


class MovimientosTests(BaseApiStock):
    def _ingresar(self, cantidad=1, item=None):
        return servicio.ingresar_manual(
            self.carga,
            self.disp,
            self.edificio,
            {(item or self.colchon).pk: cantidad},
            origen=OperacionStock.Origen.DONACION,
            origen_detalle="Vecinos",
        )

    def test_claves_exactas_y_sin_datos_personales(self):
        self._sembrar(self.colchon, 10)
        self._entregar(lineas={self.colchon.pk: 2}, observacion="vive con su hijo, teléfono 3624000000")

        respuesta = self._get(self.carga, "stock-movimientos")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Cache-Control"], "no-store")
        cuerpo = respuesta.json()
        self.assertEqual(sorted(cuerpo), CLAVES_PAGINA)
        self.assertIsNone(cuerpo["siguiente"])
        fila = cuerpo["resultados"][0]
        self.assertEqual(sorted(fila), CLAVES_MOVIMIENTO)
        self.assertEqual(fila["cantidad"], -2)
        self.assertEqual(fila["saldo_posterior"], 8)
        texto = respuesta.content.decode()
        for dato in ("Paz", "Ana", "30111222", "3624000000"):
            self.assertNotIn(dato, texto)

    def test_del_mas_nuevo_al_mas_viejo_y_pagina_por_cursor(self):
        total = 53
        for _ in range(total):
            self._ingresar()

        primera = self._get(self.carga, "stock-movimientos").json()
        self.assertEqual(len(primera["resultados"]), 50)
        ids = [f["id"] for f in primera["resultados"]]
        self.assertEqual(ids, sorted(ids, reverse=True))
        self.assertEqual(primera["siguiente"], ids[-1])

        segunda = self._get(self.carga, "stock-movimientos", cursor=primera["siguiente"]).json()
        self.assertEqual(len(segunda["resultados"]), total - 50)
        self.assertIsNone(segunda["siguiente"])
        self.assertTrue(set(ids).isdisjoint(f["id"] for f in segunda["resultados"]))

    def test_filtra_por_tipo_e_insumo(self):
        self._sembrar(self.colchon, 10)
        self._ingresar(item=self.frazada)
        self._entregar(lineas={self.colchon.pk: 1})

        solo_entregas = self._get(self.carga, "stock-movimientos", tipo=MovimientoStock.Tipo.ENTREGA_PERSONA)
        solo_frazada = self._get(self.carga, "stock-movimientos", item=self.frazada.pk)

        self.assertEqual(
            {f["tipo"] for f in solo_entregas.json()["resultados"]}, {MovimientoStock.Tipo.ENTREGA_PERSONA}
        )
        self.assertEqual({f["item_id"] for f in solo_frazada.json()["resultados"]}, {self.frazada.pk})

    def test_un_parametro_invalido_es_400_validacion(self):
        for parametros in ({"tipo": "NO_EXISTE"}, {"item": "abc"}, {"cursor": "0"}, {"cursor": "x"}):
            with self.subTest(parametros):
                respuesta = self._get(self.carga, "stock-movimientos", **parametros)
                self.assertEqual(respuesta.status_code, 400)
                self.assertEqual(respuesta.json()["code"], "VALIDACION")

    def test_un_traspaso_no_nombra_la_otra_institucion(self):
        self._sembrar(self.colchon, 5)
        rol = self._rol("Traspasa", ("dispositivo.ver", "stock.ver", "stock.ingresar"))
        traspasa = self._miembro_con(rol, "traspasa")
        self._miembro(self.disp_b, traspasa, rol)
        traspasa = self._fresco(traspasa)
        servicio.traspasar(traspasa, self.disp, self.edificio, self.disp_b, self.edificio_b, {self.colchon.pk: 2})

        texto = self._get(self.carga, "stock-movimientos").content.decode()

        self.assertIn("Traspaso a otra institución", texto)
        self.assertNotIn(self.disp_b.nombre, texto)
        self.assertNotIn(self.edificio_b.nombre, texto)


# ---------------------------------------------------------------------------
# GET .../stock/destinos-traspaso/
# ---------------------------------------------------------------------------


class DestinosDeTraspasoTests(BaseApiStock):
    def test_claves_exactas_y_solo_lo_que_alcanza(self):
        respuesta = self._get(self.carga, "stock-destinos-traspaso")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Cache-Control"], "no-store")
        destinos = respuesta.json()
        self.assertTrue(destinos)
        self.assertEqual(sorted(destinos[0]), CLAVES_DESTINO)
        self.assertEqual(sorted(destinos[0]["edificio"]), CLAVES_BREVE)
        pares = {(d["dispositivo"]["id"], d["edificio"]["id"]) for d in destinos}
        self.assertIn((self.disp.pk, self.otro_edificio.pk), pares)
        self.assertNotIn((self.disp.pk, self.edificio.pk), pares)  # el origen no es destino
        self.assertNotIn((self.disp_b.pk, self.edificio_b.pk), pares)  # fuera de su alcance de stock.ingresar

    def test_sin_stock_ingresar_es_403_sin_permiso(self):
        respuesta = self._get(self.ve, "stock-destinos-traspaso")

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["code"], "SIN_PERMISO")
        self.assertEqual(respuesta.json()["detail"], servicio.SIN_PERMISO_DE_STOCK)


# ---------------------------------------------------------------------------
# GET .../stock/persona/
# ---------------------------------------------------------------------------


class PersonaDelStockTests(BaseApiStock):
    def test_con_legajo_claves_exactas_e_historial(self):
        self._sembrar(self.colchon, 10)
        self._entregar(lineas={self.colchon.pk: 2})

        respuesta = self._get(self.guardia, "stock-persona", dni="30111222")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Cache-Control"], "no-store")
        cuerpo = respuesta.json()
        self.assertEqual(sorted(cuerpo), CLAVES_CONSULTA_PERSONA)
        self.assertEqual(sorted(cuerpo["persona"]), CLAVES_PERSONA)
        self.assertEqual(cuerpo["persona"], {"dni": "30111222", "nombre": "Ana", "apellido": "Paz"})
        entrega = cuerpo["historial"][0]
        self.assertEqual(sorted(entrega), CLAVES_HISTORIAL)
        self.assertEqual(sorted(entrega["lineas"][0]), CLAVES_LINEA_HISTORIAL)
        self.assertEqual(entrega["lineas"][0]["cantidad"], 2)

    def test_el_historial_no_nombra_a_otras_instituciones(self):
        self._sembrar(self.colchon, 10, edificio=self.edificio_b, dispositivo=self.disp_b)
        otra = self._usuario_con("guardia_b", ("stock.ver", "stock.entregar", "ciudadano.ver"), dispositivo=self.disp_b)
        servicio.entregar_a_persona(otra, self.disp_b, self.edificio_b, "30111222", {self.colchon.pk: 1})

        respuesta = self._get(self.guardia, "stock-persona", dni="30111222")

        historial = respuesta.json()["historial"]
        self.assertEqual(len(historial), 1)
        self.assertEqual(historial[0]["institucion"], "Otra institución")
        self.assertNotIn(self.disp_b.nombre, respuesta.content.decode())

    def test_no_escribe_nada(self):
        """Un DNI sin legajo, con sexo, consulta al Registro y **no** da de alta el legajo (eso es del POST de 7b)."""

        antes = (Ciudadano.objects.count(), OperacionStock.objects.count(), MovimientoStock.objects.count())
        with mock.patch(self.CONSULTA_RENAPER, return_value=self.RENAPER_ENCUENTRA):
            respuesta = self._get(self.guardia, "stock-persona", dni="27555666", sexo="F")

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json()["persona"]["apellido"], "Ruiz")
        self.assertEqual(respuesta.json()["historial"], [])
        self.assertEqual(
            (Ciudadano.objects.count(), OperacionStock.objects.count(), MovimientoStock.objects.count()), antes
        )
        self.assertFalse(Ciudadano.objects.filter(dni="27555666").exists())

    def test_sin_datos_para_identificarla_es_200_con_persona_null(self):
        """Sin legajo y sin sexo no se consulta el padrón: la app pide nombre y apellido al entregar."""

        with mock.patch(self.CONSULTA_RENAPER) as registro:
            respuesta = self._get(self.guardia, "stock-persona", dni="27555666")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"persona": None, "historial": []})
        registro.assert_not_called()

    def test_la_persona_exige_poder_entregar(self):
        """403 ``SIN_PERMISO`` sin ``stock.entregar`` **o** sin ``ciudadano.ver``, y sin tocar el padrón.

        Lo frena la **vista** (``PersonaDelStockView.get``) antes de llamar al servicio: este test no prueba la guarda
        de ``services.stock.consultar_persona`` (esa es defensa en profundidad y la cubren los tests del servicio).

        **Mutación vista en rojo:** sacar el ``if not servicio.puede_entregar`` de la vista deja que el que solo ve el
        stock consulte el padrón por acá.
        """

        sin_ciudadano = self._usuario_con("sin_ciudadano", ("stock.ver", "stock.entregar"))
        for usuario in (self.ve, sin_ciudadano):
            with self.subTest(usuario.username), mock.patch(self.CONSULTA_RENAPER) as registro:
                respuesta = self._get(usuario, "stock-persona", dni="27555666", sexo="F")
                self.assertEqual(respuesta.status_code, 403)
                self.assertEqual(respuesta.json()["code"], "SIN_PERMISO")
                registro.assert_not_called()

    def test_los_400_de_validacion(self):
        sin_dni = self._get(self.guardia, "stock-persona")
        self.assertEqual(sin_dni.status_code, 400)
        self.assertEqual(sin_dni.json()["code"], "VALIDACION")
        with mock.patch(self.CONSULTA_RENAPER, return_value=self.RENAPER_FALLECIDA):
            fallecida = self._get(self.guardia, "stock-persona", dni="27555666", sexo="F")
        self.assertEqual(fallecida.status_code, 400)
        self.assertEqual(fallecida.json()["code"], "VALIDACION")

    @mock.patch.object(ConsultaPersonasThrottle, "get_rate", return_value="1/hour")
    def test_la_consulta_gasta_la_cubeta_personas_campo(self, _rate):
        primera = self._get(self.guardia, "stock-persona", dni="30111222")
        segunda = self._get(self.guardia, "stock-persona", dni="30111222")

        self.assertEqual(primera.status_code, 200)
        self.assertEqual(segunda.status_code, 429)
        self.assertIn("Retry-After", segunda)

    @mock.patch.object(ConsultaPersonasThrottle, "get_rate", return_value="1/hour")
    def test_sin_permiso_o_sin_dni_no_gasta_la_cubeta(self, _rate):
        for _ in range(3):
            self.assertEqual(self._get(self.ve, "stock-persona", dni="30111222").status_code, 403)
            self.assertEqual(self._get(self.guardia, "stock-persona").status_code, 400)
        self.assertEqual(self._get(self.guardia, "stock-persona", dni="30111222").status_code, 200)


# ---------------------------------------------------------------------------
# §10 y §12: entregas con edificio y recepción con ``edificio_id``
# ---------------------------------------------------------------------------


class RecepcionConEdificioTests(BaseApiStock):
    def setUp(self):
        super().setUp()
        self.recibe = self._usuario_con("recibe", ("emergencia.recibir_kit",))

    def _legada(self, dispositivo=None):
        """Una entrega anterior al Cambio 523: en camino y sin edificio."""

        entrega = EntregaKit.objects.create(
            numero=f"2026-K-{EntregaKit.objects.count() + 900:06d}",
            dispositivo=dispositivo or self.disp,
            edificio=None,
            estado=EntregaKit.Estado.EN_CAMINO,
            armada_por=self.carga,
        )
        for item, cantidad in ((self.colchon, 10), (self.frazada, 3)):
            LineaEntrega.objects.create(
                entrega=entrega, item=item, nombre=item.nombre, unidad=item.unidad, cantidad_enviada=cantidad
            )
        return entrega

    def _recibir(self, entrega, usuario=None, **extra):
        cuerpo = {
            "uuid_cliente": str(uuid4()),
            f"cantidades[{self.colchon.pk}]": 10,
            f"cantidades[{self.frazada.pk}]": 3,
            "remito": SimpleUploadedFile("remito.jpg", JPEG, content_type="image/jpeg"),
            **extra,
        }
        return self._como(usuario or self.recibe).post(
            f"/api/emergencia/entregas/{entrega.pk}/recibir/", cuerpo, format="multipart"
        )

    def test_la_entrega_sin_edificio_pide_elegir_y_lista_los_edificios(self):
        entrega = self._legada()

        detalle = self._como(self.recibe).get(f"/api/emergencia/entregas/{entrega.pk}/")
        lista = self._como(self.recibe).get(f"/api/emergencia/dispositivos/{self.disp.pk}/entregas/")

        self.assertEqual(detalle.status_code, 200)
        self.assertEqual(sorted(detalle.json()), CLAVES_ENTREGA)
        self.assertIs(detalle.json()["requiere_edificio"], True)
        self.assertEqual(
            sorted(e["id"] for e in detalle.json()["edificios"]), sorted([self.edificio.pk, self.otro_edificio.pk])
        )
        self.assertEqual(lista.json()[0]["edificios"], detalle.json()["edificios"])

    def test_una_entrega_con_edificio_no_pide_elegir(self):
        entrega = self._legada()
        entrega.edificio = self.edificio
        entrega.save()

        cuerpo = self._como(self.recibe).get(f"/api/emergencia/entregas/{entrega.pk}/").json()

        self.assertIs(cuerpo["requiere_edificio"], False)
        self.assertEqual(cuerpo["edificios"], [])

    def test_en_una_institucion_sin_stock_no_pide_elegir(self):
        self.tipo.maneja_stock = False
        self.tipo.save()
        entrega = self._legada()

        cuerpo = self._como(self._fresco(self.recibe)).get(f"/api/emergencia/entregas/{entrega.pk}/").json()

        self.assertIs(cuerpo["requiere_edificio"], False)
        self.assertEqual(cuerpo["edificios"], [])

    def test_con_alcance_edificios_la_entrega_sin_edificio_es_404(self):
        """La entrega sin edificio solo la alcanza quien tiene alcance Institución: con alcance Edificios, 404."""

        de_uno = self._de_edificios("recibe_uno", [self.edificio], capacidades=("emergencia.recibir_kit",))
        entrega = self._legada()

        cuerpo = self._como(de_uno).get(f"/api/emergencia/entregas/{entrega.pk}/")

        self.assertEqual(cuerpo.status_code, 404)

    def test_la_lista_no_crece_en_consultas_con_las_entregas_legadas(self):
        """El memo es por dispositivo: 1 entrega legada y 5 hacen las mismas consultas (``EntregaKitSerializer``).

        **Mutación vista en rojo:** sin el memo ``_memo_por_dispositivo`` cada entrega recalcula el edificio y las
        consultas crecen con la cantidad de entregas.
        """

        url = f"/api/emergencia/dispositivos/{self.disp.pk}/entregas/"
        self._legada()
        self._como(self.recibe).get(url)  # calienta cachés (permisos, contenttypes)
        with CaptureQueriesContext(connection) as una:
            self._como(self.recibe).get(url)
        for _ in range(4):
            self._legada()
        with CaptureQueriesContext(connection) as cinco:
            respuesta = self._como(self.recibe).get(url)

        self.assertEqual(len(respuesta.json()), 5)
        self.assertEqual(len(cinco), len(una))

    def test_recibir_con_edificio_id_suma_al_stock_de_ese_edificio(self):
        entrega = self._legada()

        respuesta = self._recibir(entrega, edificio_id=self.otro_edificio.pk)

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        entrega.refresh_from_db()
        self.assertEqual(entrega.edificio_id, self.otro_edificio.pk)
        self.assertEqual(self._cantidad(self.colchon, edificio=self.otro_edificio), 10)
        self.assertEqual(self._cantidad(self.colchon, edificio=self.edificio), 0)

    def test_sin_edificio_id_es_400_con_esa_clave(self):
        entrega = self._legada()

        respuesta = self._recibir(entrega)

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["code"], "VALIDACION")
        self.assertIn("edificio_id", respuesta.json())
        self.assertNotIn("edificio", respuesta.json())
        entrega.refresh_from_db()
        self.assertEqual(entrega.estado, EntregaKit.Estado.EN_CAMINO)

    def test_un_edificio_no_vinculado_es_400_con_esa_clave(self):
        entrega = self._legada()

        respuesta = self._recibir(entrega, edificio_id=self.edificio_b.pk)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("edificio_id", respuesta.json())
        self.assertFalse(Edificio.objects.filter(pk=self.edificio_b.pk, dispositivos=self.disp).exists())

    def test_el_reenvio_con_el_mismo_uuid_no_suma_dos_veces(self):
        entrega = self._legada()
        identificador = str(uuid4())

        primera = self._recibir(entrega, uuid_cliente=identificador, edificio_id=self.edificio.pk)
        segunda = self._recibir(entrega, uuid_cliente=identificador, edificio_id=self.edificio.pk)

        self.assertEqual((primera.status_code, segunda.status_code), (200, 200))
        self.assertEqual(self._cantidad(self.colchon), 10)
