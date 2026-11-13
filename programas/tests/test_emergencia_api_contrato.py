"""Módulo Emergencia, PR 5: la API de campo (base, login, perfil, identidad y localidades) y su esquema.

Lo que lee la app (`Chaco-mobile`) está fijado con **claves exactas** (las constantes
``CLAVES_*`` de ``base_emergencia_api``) y documentado en
``docs/internal/contrato-app-emergencia.md``. Cada superficie tiene su archivo: M1 en
``test_emergencia_api_m1``, M3 en ``test_emergencia_api_kits`` y M2 en los
``test_emergencia_api_m2*``. Este fija lo transversal:

* **H10 / RU-4** — una sola regla de acceso al módulo (``modulo_habilitado``): la usan el
  login (``"emergencia"`` en ``modulos``) y los permisos del namespace. Agente con
  ``emergencia.relevar``, guardia con ``dispositivo.admitir`` o ``emergencia.recibir_kit``
  **en el Equipo** de un dispositivo, o administrador del programa Dispositivos.
* **H11** — las claves del login no cambian (``CLAVES_LOGIN`` es el de Becas, importado);
  cambia un valor posible de ``modulos``, siempre al final.
* **RU §6 n.° 3, mitad API** — un rol de Becas no abre Emergencia y el agente de Emergencia
  no abre Becas. Son barridos del URLconf, no listas a mano.
* **H2** — la consulta de identidad de Emergencia es la de Becas, con permiso propio y la
  misma cubeta de throttle.
* **El esquema publicado** — cada extremo, sus claves y sus códigos (el 429 de la búsqueda
  por DNI incluido).
* **Presupuestos** — ``localidades`` no crece con las filas.

El test de mutación ``test_un_rol_de_becas_no_abre_el_modulo…`` se vio en rojo contra la
regla rota antes de quedar verde; el detalle está en su docstring.
"""

from unittest import mock

from django.contrib.auth.models import AnonymousUser, User
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.authtoken.models import Token

from core import rbac
from core.models import Localidad, Municipio, Provincia
from core.tests.test_api_schema_contrato import _generar_esquema_y_sus_avisos
from programas.api.views import ConsultaPersonasThrottle
from programas.models import (
    CasoEmergencia,
    MiembroEquipoDispositivo,
)
from programas.selectors.emergencia_campo import localidades_para_relevar
from programas.services.emergencia_programa import modulo_habilitado, roles_en_app
from programas.tests.base_emergencia_api import (
    ADMITIR,
    CLAVES_ACEPTACION,
    CLAVES_AVISO_A_LA_MESA,
    CLAVES_BUSQUEDA,
    CLAVES_CASO_CREADO,
    CLAVES_CIERRE_DE_INGRESO,
    CLAVES_CONFIRMACION,
    CLAVES_CONSULTA,
    CLAVES_ENTREGA,
    CLAVES_ESTADO_CAMBIO,
    CLAVES_FICHA_COMPLETADA,
    CLAVES_INGRESO_DIRECTO,
    CLAVES_INTEGRANTE_AGREGADO,
    CLAVES_INTEGRANTE_DETALLE,
    CLAVES_INTEGRANTES,
    CLAVES_LOCALIDAD,
    CLAVES_MAPA,
    CLAVES_MI_CASO,
    CLAVES_MI_DISPOSITIVO,
    CLAVES_PERFIL,
    CLAVES_RAIZ,
    CLAVES_RECEPCION,
    CLAVES_RECHAZO,
    CLAVES_SIN_MODULO,
    SIN_MODULO,
    SIN_RELEVAR,
    SOLO_DEL_AGENTE,
    URL_CASOS,
    URL_CONSULTAR,
    URL_LOCALIDADES,
    URL_MIOS,
    URL_MIS_DISPOSITIVOS,
    URL_PERFIL,
    URL_RAIZ,
    URLS_DE_KITS_DEL_BARRIDO,
    URLS_DE_LLEGADAS_DEL_BARRIDO,
    BaseApiEmergencia,
    urls_de_la_api_de_becas,
    urls_de_la_api_de_emergencia,
)
from programas.tests.test_becas_api_contrato import CLAVES_LOGIN
from programas.tests.test_emergencia_base import RECIBIR_KIT, RELEVAR
from users.models import Profile

Estado = CasoEmergencia.Estado
Prioridad = CasoEmergencia.Prioridad


# ---------------------------------------------------------------------------
# La regla única de acceso (H10)
# ---------------------------------------------------------------------------


class ModuloHabilitadoTests(BaseApiEmergencia):
    def test_el_agente_con_relevar_abre_el_modulo(self):
        self.assertTrue(modulo_habilitado(self.agente))
        self.assertEqual(roles_en_app(self.agente), {"relevar": True, "dispositivo": False})

    def test_la_guardia_con_admitir_en_su_equipo_abre_el_modulo(self):
        self.assertTrue(modulo_habilitado(self.guardia))
        self.assertEqual(roles_en_app(self.guardia), {"relevar": False, "dispositivo": True})

    def test_recibir_kit_en_el_equipo_tambien_lo_abre(self):
        deposito = self._guardia("deposito", [RECIBIR_KIT], [self.club])

        self.assertTrue(modulo_habilitado(deposito))
        self.assertEqual(roles_en_app(deposito), {"relevar": False, "dispositivo": True})

    def test_admitir_en_un_rol_sin_equipo_no_lo_abre(self):
        """La capacidad sin un dispositivo sobre el que ejercerla no es un acceso."""
        sin_equipo = self._guardia("sin_equipo", [ADMITIR, RECIBIR_KIT])

        self.assertFalse(modulo_habilitado(sin_equipo))
        self.assertEqual(roles_en_app(sin_equipo), {"relevar": False, "dispositivo": False})

    def test_una_fila_del_equipo_dada_de_baja_no_lo_abre(self):
        MiembroEquipoDispositivo.objects.filter(usuario=self.guardia).update(activo=False)

        self.assertFalse(modulo_habilitado(User.objects.get(pk=self.guardia.pk)))

    def test_el_admin_del_programa_dispositivos_lo_abre_sin_equipo(self):
        """H10: el login no cambia. Pero sin ``admitir`` ni ``recibir_kit`` no opera nada (PR 8).

        Los servicios de alojar y de kits le niegan todo (``puede_operar_dispositivo`` exige
        la capacidad aunque administre el programa): el perfil no le ofrece «Llegada de
        familias» ni «Recepción de kits» para que no le contesten 403 después.
        """
        admin = self._guardia("admin_disp", ["programa.configurar"])

        self.assertTrue(modulo_habilitado(admin))
        self.assertEqual(roles_en_app(admin), {"relevar": False, "dispositivo": False})

    def test_el_admin_del_programa_con_admitir_opera_todos_sin_equipo(self):
        for capacidad in (ADMITIR, RECIBIR_KIT):
            with self.subTest(capacidad=capacidad):
                admin = self._guardia(f"admin_{capacidad}", ["programa.configurar", capacidad])

                self.assertTrue(modulo_habilitado(admin))
                self.assertEqual(roles_en_app(admin), {"relevar": False, "dispositivo": True})

    def test_el_admin_de_otro_programa_no_lo_abre(self):
        admin_becas = self._usuario("admin_becas", ["programa.configurar"], programa=self.becas)

        self.assertFalse(modulo_habilitado(admin_becas))

    def test_quien_opera_la_mesa_no_abre_el_modulo_de_la_app(self):
        """La mesa trabaja en el backoffice: ``operar`` y ``supervisar`` no son accesos de la app."""
        for usuario in (self.operador, self.supervisor):
            with self.subTest(usuario=usuario.username):
                self.assertFalse(modulo_habilitado(usuario))

    def test_un_rol_de_becas_o_del_relevamiento_edilicio_no_lo_abre(self):
        edilicio = self._guardia("edilicio", ["inspeccion.relevar"], [self.club])

        for usuario in (self.territorial_becas, edilicio):
            with self.subTest(usuario=usuario.username):
                self.assertFalse(modulo_habilitado(usuario))
                self.assertEqual(roles_en_app(usuario), {"relevar": False, "dispositivo": False})

    def test_con_los_dos_roles_ve_los_dos_accesos(self):
        ambos = self._sumar_rol(self._usuario("ambos", [RELEVAR]), [ADMITIR], self.dispositivos, [self.club])

        self.assertEqual(roles_en_app(ambos), {"relevar": True, "dispositivo": True})

    def test_un_anonimo_no_lo_abre(self):
        self.assertFalse(modulo_habilitado(AnonymousUser()))
        self.assertFalse(modulo_habilitado(None))


# ---------------------------------------------------------------------------
# Login (RU-4, H11)
# ---------------------------------------------------------------------------


class LoginConEmergenciaTests(BaseApiEmergencia):
    def _modulos(self, username):
        respuesta = self._login(username)
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        # H11: las claves del cuerpo son las de siempre, las mismas que fija el contrato de Becas.
        self.assertEqual(sorted(respuesta.json()), sorted(CLAVES_LOGIN))
        return respuesta.json()["modulos"]

    def test_el_agente_solo_con_relevar_recibe_emergencia(self):
        self.assertEqual(self._modulos("agente"), ["emergencia"])

    def test_el_territorial_de_becas_sigue_recibiendo_solo_becas(self):
        self.assertEqual(self._modulos("terri_becas"), ["becas"])

    def test_becas_mas_relevar_trae_los_dos_con_emergencia_al_final(self):
        self._sumar_rol(self.territorial_becas, [RELEVAR], self.programa)

        self.assertEqual(self._modulos("terri_becas"), ["becas", "emergencia"])

    def test_el_agente_edilicio_con_relevar_trae_dispositivos_y_emergencia(self):
        self._sumar_rol(self.agente, ["inspeccion.relevar"], self.dispositivos)

        self.assertEqual(self._modulos("agente"), ["dispositivos", "emergencia"])

    def test_la_guardia_con_admitir_en_su_equipo_recibe_emergencia(self):
        self.assertEqual(self._modulos("guardia"), ["emergencia"])

    def test_el_admin_del_programa_dispositivos_recibe_emergencia(self):
        self._guardia("admin_disp", ["programa.configurar"])

        self.assertEqual(self._modulos("admin_disp"), ["emergencia"])

    def test_admitir_sin_equipo_no_saca_token(self):
        self._guardia("sin_equipo", [ADMITIR])

        respuesta = self._login("sin_equipo")

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json(), {"detail": "El usuario no tiene acceso a la app de campo."})
        self.assertFalse(Token.objects.filter(user__username="sin_equipo").exists())

    def test_quien_solo_opera_la_mesa_no_saca_token(self):
        self.assertEqual(self._login("ana").status_code, 403)

    def test_la_guardia_con_clave_provisoria_tiene_que_cambiarla_antes(self):
        """La guardia es un usuario de backoffice: el flag de la clave provisoria vale igual acá."""
        Profile.objects.update_or_create(user=self.guardia, defaults={"debe_cambiar_contrasena": True})

        respuesta = self._login("guardia")

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["codigo"], "debe_cambiar_contrasena")
        self.assertFalse(Token.objects.filter(user=self.guardia).exists())

    def test_la_guardia_no_es_un_usuario_solo_de_campo_y_el_agente_si(self):
        """``es_solo_campo`` decide el login web y cómo viaja la clave: sumar el módulo no lo mueve."""
        self.assertFalse(rbac.es_solo_campo(self.guardia))
        self.assertTrue(rbac.es_solo_campo(self.agente))


# ---------------------------------------------------------------------------
# Quién entra a qué (RU §6 n.° 3, mitad API)
# ---------------------------------------------------------------------------


class AccesoAlNamespaceTests(BaseApiEmergencia):
    def test_el_barrido_ve_las_rutas_del_namespace(self):
        """Sin esto, un barrido que devuelva vacío daría verde."""
        self.assertEqual(
            sorted(urls_de_la_api_de_emergencia()),
            sorted(
                [URL_RAIZ, URL_PERFIL, URL_CONSULTAR, URL_LOCALIDADES, URL_CASOS, URL_MIOS, URL_MIS_DISPOSITIVOS]
                + URLS_DE_KITS_DEL_BARRIDO
                + URLS_DE_LLEGADAS_DEL_BARRIDO
            ),
        )
        self.assertGreaterEqual(len(urls_de_la_api_de_becas()), 5)

    def test_sin_token_todo_el_namespace_es_401(self):
        for url in urls_de_la_api_de_emergencia():
            for metodo in ("get", "post"):
                with self.subTest(url=url, metodo=metodo):
                    respuesta = getattr(self._anonimo(), metodo)(url, {}, format="json")
                    self.assertEqual(respuesta.status_code, 401)

    def test_un_rol_de_becas_no_abre_el_modulo_ni_ninguna_ruta_del_namespace(self):
        """RU §6 n.° 3 (mitad API): ``becas.campo`` no abre Emergencia.

        **Mutación vista en rojo:** con ``modulo_habilitado`` aceptando además
        ``rbac.puede(user, "becas.campo")`` —«cualquier capacidad de campo abre el módulo»—
        este test falla en las dos mitades: la raíz, el perfil y las localidades contestan
        200 (y la consulta deja de dar 403), y el login devuelve ``["becas", "emergencia"]``.
        Restaurada la regla, verde.
        """
        cliente = self._como(self.territorial_becas)
        for url in urls_de_la_api_de_emergencia():
            esperado = SIN_RELEVAR if url in SOLO_DEL_AGENTE else SIN_MODULO
            for metodo in ("get", "post"):
                with self.subTest(url=url, metodo=metodo):
                    respuesta = getattr(cliente, metodo)(url, {}, format="json")
                    self.assertEqual(respuesta.status_code, 403)
                    self.assertEqual(sorted(respuesta.json()), CLAVES_SIN_MODULO)
                    self.assertEqual(respuesta.json(), esperado)
        self.assertEqual(CasoEmergencia.objects.count(), 0)

        respuesta = self._login("terri_becas")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["modulos"], ["becas"])

    def test_el_agente_de_emergencia_no_abre_ninguna_ruta_de_becas(self):
        """RU §6 n.° 3 al revés: ``emergencia.relevar`` no abre Becas, incluida su consulta de identidad.

        **Mutación vista en rojo:** con ``CampoBecasPermission`` aceptando además
        ``modulo_habilitado(user)`` —la forma «fácil» de resolver H2— la raíz, la agenda y
        ``personas/consultar`` de Becas dejan de contestar 403. Restaurada la regla, verde.
        """
        for usuario in (self.agente, self.guardia):
            cliente = self._como(usuario)
            for url in urls_de_la_api_de_becas():
                for metodo in ("get", "post"):
                    with self.subTest(usuario=usuario.username, url=url, metodo=metodo):
                        respuesta = getattr(cliente, metodo)(url, {"dni": "30111222", "sexo": "F"}, format="json")
                        self.assertEqual(respuesta.status_code, 403)
                        self.assertEqual(respuesta.json()["code"], "SIN_MODULO")

    def test_el_agente_de_emergencia_no_abre_el_relevamiento_edilicio(self):
        respuesta = self._como(self.agente).get(reverse("dispositivos_api:inspeccion-list"))

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["code"], "SIN_MODULO")

    def test_la_guardia_abre_el_modulo_pero_no_crea_casos_de_territorio(self):
        """Tabla de RU §4: crear desde territorio es del agente. La guardia entra por M2 (PR 8)."""
        cliente = self._como(self.guardia)

        for url in (URL_RAIZ, URL_PERFIL, URL_LOCALIDADES):
            with self.subTest(url=url):
                self.assertEqual(cliente.get(url).status_code, 200)
        envio = cliente.post(URL_CASOS, self._cuerpo(), format="multipart")
        mios = cliente.get(URL_MIOS)

        for respuesta in (envio, mios):
            self.assertEqual(respuesta.status_code, 403)
            self.assertEqual(respuesta.json(), SIN_RELEVAR)
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    def test_quien_opera_la_mesa_no_entra_con_su_sesion_del_backoffice(self):
        """El namespace admite sesión además de token, y la regla es la misma."""
        self.client.force_login(self.operador)

        respuesta = self.client.get(URL_PERFIL)

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json(), SIN_MODULO)


class RaizYPerfilTests(BaseApiEmergencia):
    def test_la_raiz_lista_las_rutas_del_namespace(self):
        respuesta = self._como(self.agente).get(URL_RAIZ)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(sorted(respuesta.json()), CLAVES_RAIZ)
        self.assertTrue(respuesta.json()["casos"].endswith(URL_CASOS))

    def test_el_perfil_dice_que_accesos_mostrar(self):
        ambos = self._sumar_rol(self._usuario("ambos", [RELEVAR]), [ADMITIR], self.dispositivos, [self.club])
        casos = (
            (self.agente, {"relevar": True, "dispositivo": False}),
            (self.guardia, {"relevar": False, "dispositivo": True}),
            (ambos, {"relevar": True, "dispositivo": True}),
        )

        for usuario, esperado in casos:
            with self.subTest(usuario=usuario.username):
                respuesta = self._como(usuario).get(URL_PERFIL)
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(sorted(respuesta.json()), CLAVES_PERFIL)
                self.assertEqual(respuesta.json(), esperado)


# ---------------------------------------------------------------------------
# Consulta de identidad (H2)
# ---------------------------------------------------------------------------


class ConsultaDePersonaTests(BaseApiEmergencia):
    PERSONA = {"success": True, "data": {"nombre": "Rosa", "apellido": "Benitez", "fecha_nacimiento": "1984-03-02"}}

    def setUp(self):
        super().setUp()
        parche = mock.patch("programas.services.identidad.consultar_persona", return_value=self.PERSONA)
        self.gran_base = parche.start()
        self.addCleanup(parche.stop)

    def _consultar(self, usuario, url=URL_CONSULTAR, **cuerpo):
        return self._como(usuario).post(url, {"dni": "30.111.222", "sexo": "f", **cuerpo}, format="json")

    def test_el_agente_y_la_guardia_consultan_con_el_contrato_de_becas(self):
        for usuario in (self.agente, self.guardia):
            with self.subTest(usuario=usuario.username):
                respuesta = self._consultar(usuario)

                self.assertEqual(respuesta.status_code, 200, respuesta.content)
                cuerpo = respuesta.json()
                self.assertEqual(sorted(cuerpo), CLAVES_CONSULTA)
                self.assertIs(cuerpo["success"], True)
                self.assertEqual(cuerpo["origen"], "personas")
                self.assertEqual(cuerpo["datos_api"], {})
                self.assertEqual(cuerpo["data"]["dni"], "30111222")
                self.assertEqual(cuerpo["data"]["sexo"], "F")
                self.assertEqual(cuerpo["data"]["nombre"], "Rosa")

    def test_la_respuesta_es_la_misma_que_da_becas(self):
        """Mismo servicio, mismo cuerpo: quien tiene los dos módulos ve lo mismo por las dos rutas."""
        ambos = self._sumar_rol(self.territorial_becas, [RELEVAR], self.programa)

        por_emergencia = self._consultar(ambos)
        por_becas = self._consultar(ambos, url=reverse("becas_api:personas-consultar"))

        self.assertEqual(por_becas.status_code, 200, por_becas.content)
        self.assertEqual(por_emergencia.json(), por_becas.json())

    def test_sin_dni_o_sin_sexo_es_el_400_de_siempre(self):
        respuesta = self._como(self.agente).post(URL_CONSULTAR, {"dni": "30111222"}, format="json")

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json(), {"success": False, "error": "DNI y sexo (F o M) son requeridos."})

    def test_la_persona_que_no_figura_es_404_y_la_fuente_caida_502(self):
        self.gran_base.return_value = {"success": False, "error": "No se encontró", "not_found": True}
        no_figura = self._consultar(self.agente)
        self.gran_base.return_value = {"success": False, "error": "Timeout"}
        caida = self._consultar(self.agente)

        self.assertEqual(no_figura.status_code, 404)
        self.assertEqual(sorted(no_figura.json()), ["error", "success"])
        self.assertEqual(caida.status_code, 502)
        self.assertEqual(caida.json(), {"success": False, "error": "Timeout"})

    def test_un_relevamiento_en_el_cuerpo_se_ignora(self):
        """Emergencia no tiene padrones: la clave de Becas no rompe ni cambia la respuesta."""
        respuesta = self._consultar(self.agente, relevamiento=999)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["origen"], "personas")

    @mock.patch.object(ConsultaPersonasThrottle, "get_rate", return_value="1/hour")
    def test_la_cubeta_es_la_misma_que_la_de_becas(self, _rate):
        """Un tope que se evade cambiando de módulo no es un tope (SEC-25)."""
        ambos = self._sumar_rol(self.territorial_becas, [RELEVAR], self.programa)

        primera = self._consultar(ambos, url=reverse("becas_api:personas-consultar"))
        segunda = self._consultar(ambos)

        self.assertEqual(primera.status_code, 200, primera.content)
        self.assertEqual(segunda.status_code, 429)
        self.assertIn("Retry-After", segunda)

    @mock.patch.object(ConsultaPersonasThrottle, "get_rate", return_value="1/hour")
    def test_la_cubeta_es_por_usuario(self, _rate):
        self.assertEqual(self._consultar(self.agente).status_code, 200)
        self.assertEqual(self._consultar(self.agente).status_code, 429)
        self.assertEqual(self._consultar(self.guardia).status_code, 200)

    @mock.patch.object(ConsultaPersonasThrottle, "get_rate", return_value="1/hour")
    def test_quien_no_tiene_el_modulo_no_gasta_la_cubeta(self, _rate):
        """El permiso corre antes que el throttle."""
        for _ in range(3):
            self.assertEqual(self._consultar(self.operador).status_code, 403)
        self.gran_base.assert_not_called()


# ---------------------------------------------------------------------------
# Localidades (RN-1.6, H4)
# ---------------------------------------------------------------------------


class LocalidadesTests(BaseApiEmergencia):
    def setUp(self):
        super().setUp()
        chaco = Provincia.objects.create(nombre="Chaco")
        self.municipio = Municipio.objects.create(nombre="San Fernando", provincia=chaco)
        self.resistencia = Localidad.objects.create(nombre="Resistencia", municipio=self.municipio)
        self.barranqueras = Localidad.objects.create(nombre="Barranqueras", municipio=self.municipio)
        corrientes = Provincia.objects.create(nombre="Corrientes")
        capital = Municipio.objects.create(nombre="Capital", provincia=corrientes)
        Localidad.objects.create(nombre="Corrientes", municipio=capital)

    def test_trae_id_y_nombre_de_la_provincia_operativa_por_nombre_y_sin_paginar(self):
        respuesta = self._como(self.agente).get(URL_LOCALIDADES)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.json(),
            [
                {"id": self.barranqueras.pk, "nombre": "Barranqueras"},
                {"id": self.resistencia.pk, "nombre": "Resistencia"},
            ],
        )
        for fila in respuesta.json():
            # H4: sin coordenadas. `core.Localidad` no las tiene.
            self.assertEqual(sorted(fila), CLAVES_LOCALIDAD)

    def test_la_guardia_tambien_las_lee(self):
        self.assertEqual(len(self._como(self.guardia).get(URL_LOCALIDADES).json()), 2)

    def test_el_id_que_devuelve_es_el_que_acepta_el_envio(self):
        respuesta = self._enviar(localidad=self.resistencia.pk)

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.assertEqual(CasoEmergencia.objects.get().localidad, self.resistencia)

    @tag("performance")
    def test_el_selector_cuesta_una_consulta(self):
        Localidad.objects.bulk_create(
            [Localidad(nombre=f"Paraje {n:03d}", municipio=self.municipio) for n in range(60)]
        )

        with self.assertNumQueries(1):
            filas = localidades_para_relevar()

        self.assertEqual(len(filas), 62)

    @tag("performance")
    def test_el_endpoint_no_crece_con_las_localidades(self):
        cliente = self._como(self.agente)
        cliente.get(URL_LOCALIDADES)  # deja memoizado el programa, que es una clave de proceso
        with CaptureQueriesContext(connection) as con_dos:
            cliente.get(URL_LOCALIDADES)
        Localidad.objects.bulk_create(
            [Localidad(nombre=f"Paraje {n:03d}", municipio=self.municipio) for n in range(60)]
        )

        with self.assertNumQueries(len(con_dos)):
            self.assertEqual(len(cliente.get(URL_LOCALIDADES).json()), 62)


# ---------------------------------------------------------------------------
# El esquema publicado
# ---------------------------------------------------------------------------


class EsquemaDeLaApiDeEmergenciaTests(BaseApiEmergencia):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.esquema, cls.errores, cls.warnings = _generar_esquema_y_sus_avisos()

    def _componente(self, operacion, codigo="200"):
        esquema = operacion["responses"][codigo]["content"]["application/json"]["schema"]
        ref = (esquema.get("items") or esquema)["$ref"].split("/")[-1]
        return self.esquema["components"]["schemas"][ref]

    def test_los_extremos_estan_publicados_sin_avisos(self):
        rutas = self.esquema["paths"]

        self.assertEqual(self.errores, [])
        self.assertEqual(self.warnings, [])
        esperados = {}
        for ruta, metodo in (
            (URL_PERFIL, "get"),
            (URL_CONSULTAR, "post"),
            (URL_LOCALIDADES, "get"),
            (URL_CASOS, "post"),
            (URL_MIOS, "get"),
            (URL_MIS_DISPOSITIVOS, "get"),
            ("/api/emergencia/dispositivos/{dispositivo_id}/entregas/", "get"),
            ("/api/emergencia/entregas/{id}/", "get"),
            ("/api/emergencia/entregas/{id}/recibir/", "post"),
            # M2 (PR 8)
            ("/api/emergencia/dispositivos/{dispositivo_id}/buscar/", "get"),
            ("/api/emergencia/dispositivos/{dispositivo_id}/plazas/", "get"),
            ("/api/emergencia/derivaciones/{id}/aceptar/", "post"),
            ("/api/emergencia/derivaciones/{id}/rechazar/", "post"),
            ("/api/emergencia/casos/{id}/integrantes/", "get"),
            ("/api/emergencia/casos/{id}/integrantes/", "post"),
            ("/api/emergencia/casos/{id}/integrantes/{n}/", "get"),
            ("/api/emergencia/casos/{id}/integrantes/{n}/", "patch"),
            ("/api/emergencia/casos/{id}/integrantes/{n}/confirmar/", "post"),
            ("/api/emergencia/casos/{id}/alojar/", "post"),
            ("/api/emergencia/casos/{id}/cerrar-diferencia/", "post"),
            ("/api/emergencia/casos/{id}/cancelar-ingreso/", "post"),
            ("/api/emergencia/dispositivos/{dispositivo_id}/ingreso-directo/", "post"),
            ("/api/emergencia/dispositivos/{dispositivo_id}/avisar-mesa/", "post"),
        ):
            esperados.setdefault(ruta, []).append(metodo)
        for ruta, metodos in esperados.items():
            with self.subTest(ruta=ruta):
                self.assertEqual(sorted(rutas[ruta]), sorted(metodos))
                for metodo in metodos:
                    self.assertIn("403", rutas[ruta][metodo]["responses"])

    def test_cada_respuesta_publica_las_claves_del_contrato(self):
        rutas = self.esquema["paths"]
        casos = (
            (rutas[URL_PERFIL]["get"], "200", CLAVES_PERFIL),
            (rutas[URL_LOCALIDADES]["get"], "200", CLAVES_LOCALIDAD),
            (rutas[URL_CASOS]["post"], "201", CLAVES_CASO_CREADO),
            (rutas[URL_CASOS]["post"], "200", CLAVES_CASO_CREADO),
            (rutas[URL_MIOS]["get"], "200", CLAVES_MI_CASO),
            (rutas[URL_CONSULTAR]["post"], "200", CLAVES_CONSULTA),
            (rutas[URL_MIS_DISPOSITIVOS]["get"], "200", CLAVES_MI_DISPOSITIVO),
            (rutas["/api/emergencia/dispositivos/{dispositivo_id}/entregas/"]["get"], "200", CLAVES_ENTREGA),
            (rutas["/api/emergencia/entregas/{id}/"]["get"], "200", CLAVES_ENTREGA),
            (rutas["/api/emergencia/entregas/{id}/recibir/"]["post"], "200", CLAVES_RECEPCION),
            (rutas["/api/emergencia/entregas/{id}/recibir/"]["post"], "409", CLAVES_ESTADO_CAMBIO),
            # M2 (PR 8)
            (rutas["/api/emergencia/dispositivos/{dispositivo_id}/buscar/"]["get"], "200", CLAVES_BUSQUEDA),
            (rutas["/api/emergencia/dispositivos/{dispositivo_id}/plazas/"]["get"], "200", CLAVES_MAPA),
            (rutas["/api/emergencia/derivaciones/{id}/aceptar/"]["post"], "200", CLAVES_ACEPTACION),
            (rutas["/api/emergencia/derivaciones/{id}/aceptar/"]["post"], "409", CLAVES_ESTADO_CAMBIO),
            (rutas["/api/emergencia/derivaciones/{id}/rechazar/"]["post"], "200", CLAVES_RECHAZO),
            (rutas["/api/emergencia/casos/{id}/integrantes/"]["get"], "200", CLAVES_INTEGRANTES),
            (rutas["/api/emergencia/casos/{id}/integrantes/"]["post"], "201", CLAVES_INTEGRANTE_AGREGADO),
            (rutas["/api/emergencia/casos/{id}/integrantes/{n}/"]["get"], "200", CLAVES_INTEGRANTE_DETALLE),
            (rutas["/api/emergencia/casos/{id}/integrantes/{n}/"]["patch"], "200", CLAVES_FICHA_COMPLETADA),
            (rutas["/api/emergencia/casos/{id}/integrantes/{n}/confirmar/"]["post"], "201", CLAVES_CONFIRMACION),
            (rutas["/api/emergencia/casos/{id}/integrantes/{n}/confirmar/"]["post"], "409", CLAVES_ESTADO_CAMBIO),
            (rutas["/api/emergencia/casos/{id}/alojar/"]["post"], "200", CLAVES_CIERRE_DE_INGRESO),
            (rutas["/api/emergencia/casos/{id}/cerrar-diferencia/"]["post"], "200", CLAVES_CIERRE_DE_INGRESO),
            (rutas["/api/emergencia/casos/{id}/cancelar-ingreso/"]["post"], "200", CLAVES_CIERRE_DE_INGRESO),
            (
                rutas["/api/emergencia/dispositivos/{dispositivo_id}/ingreso-directo/"]["post"],
                "201",
                CLAVES_INGRESO_DIRECTO,
            ),
            (
                rutas["/api/emergencia/dispositivos/{dispositivo_id}/avisar-mesa/"]["post"],
                "201",
                CLAVES_AVISO_A_LA_MESA,
            ),
        )
        for operacion, codigo, claves in casos:
            with self.subTest(operacion=operacion["operationId"], codigo=codigo):
                self.assertEqual(sorted(self._componente(operacion, codigo)["properties"]), claves)

    def test_las_dos_consultas_con_tope_publican_el_429(self):
        """La identidad (SEC-25) y la búsqueda por DNI (M2-1): la app sabe que pueden contestar 429."""
        rutas = self.esquema["paths"]

        for operacion in (
            rutas[URL_CONSULTAR]["post"],
            rutas["/api/emergencia/dispositivos/{dispositivo_id}/buscar/"]["get"],
        ):
            with self.subTest(operacion=operacion["operationId"]):
                self.assertIn("429", operacion["responses"])

    def test_el_envio_es_multipart_y_solo_exige_el_uuid(self):
        operacion = self.esquema["paths"][URL_CASOS]["post"]
        contenido = operacion["requestBody"]["content"]

        self.assertEqual(list(contenido), ["multipart/form-data"])
        cuerpo = self.esquema["components"]["schemas"][
            contenido["multipart/form-data"]["schema"]["$ref"].split("/")[-1]
        ]
        self.assertEqual(cuerpo["required"], ["uuid_cliente"])
        self.assertEqual(cuerpo["properties"]["uuid_cliente"]["format"], "uuid")
        self.assertEqual(cuerpo["properties"]["foto_vivienda"]["format"], "binary")
        self.assertEqual(cuerpo["properties"]["foto_acceso"]["format"], "binary")
        self.assertNotIn("total", cuerpo["properties"])
        self.assertNotIn("prioridad", cuerpo["properties"])

    def test_la_consulta_declara_el_mismo_cuerpo_que_la_de_becas(self):
        de_emergencia = self.esquema["paths"][URL_CONSULTAR]["post"]["requestBody"]["content"]["application/json"]
        de_becas = self.esquema["paths"]["/api/becas/personas/consultar/"]["post"]["requestBody"]["content"][
            "application/json"
        ]

        self.assertEqual(de_emergencia["schema"], de_becas["schema"])

    def test_el_estado_y_la_prioridad_del_caso_tienen_nombre_propio(self):
        """Sin nombre propio, Spectacular los llama con un hash que cambia al tocar cualquier `choices`."""
        componentes = self.esquema["components"]["schemas"]

        self.assertEqual(componentes["CasoEmergenciaEstadoEnum"]["enum"], list(Estado.values))
        self.assertEqual(componentes["CasoEmergenciaPrioridadEnum"]["enum"], list(Prioridad.values))
