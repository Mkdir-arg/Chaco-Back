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
from django.test import override_settings, tag
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
    CLAVES_DERIVACION_DEL_INGRESO,
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
    CLAVES_SUGERENCIA,
    CLAVES_SUGERENCIAS,
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
    URL_SUGERIR,
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


def _accesos(relevar=False, llegadas=False, kits=False):
    """Lo que contesta ``roles_en_app``: ``dispositivo`` es siempre ``llegadas or kits``."""
    return {"relevar": relevar, "llegadas": llegadas, "kits": kits, "dispositivo": llegadas or kits}


# ---------------------------------------------------------------------------
# La regla única de acceso (H10)
# ---------------------------------------------------------------------------


class ModuloHabilitadoTests(BaseApiEmergencia):
    def test_el_agente_con_relevar_abre_el_modulo(self):
        self.assertTrue(modulo_habilitado(self.agente))
        self.assertEqual(roles_en_app(self.agente), _accesos(relevar=True))

    def test_la_guardia_con_admitir_en_su_equipo_abre_el_modulo(self):
        self.assertTrue(modulo_habilitado(self.guardia))
        self.assertEqual(roles_en_app(self.guardia), _accesos(llegadas=True))

    def test_recibir_kit_en_el_equipo_tambien_lo_abre(self):
        deposito = self._guardia("deposito", [RECIBIR_KIT], [self.club])

        self.assertTrue(modulo_habilitado(deposito))
        self.assertEqual(roles_en_app(deposito), _accesos(kits=True))

    def test_admitir_en_un_rol_sin_equipo_no_lo_abre(self):
        """La capacidad sin un dispositivo sobre el que ejercerla no es un acceso."""
        sin_equipo = self._guardia("sin_equipo", [ADMITIR, RECIBIR_KIT])

        self.assertFalse(modulo_habilitado(sin_equipo))
        self.assertEqual(roles_en_app(sin_equipo), _accesos())

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
        self.assertEqual(roles_en_app(admin), _accesos())

    def test_el_admin_del_programa_con_admitir_opera_todos_sin_equipo(self):
        for capacidad, esperado in ((ADMITIR, _accesos(llegadas=True)), (RECIBIR_KIT, _accesos(kits=True))):
            with self.subTest(capacidad=capacidad):
                admin = self._guardia(f"admin_{capacidad}", ["programa.configurar", capacidad])

                self.assertTrue(modulo_habilitado(admin))
                self.assertEqual(roles_en_app(admin), esperado)

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
                self.assertEqual(roles_en_app(usuario), _accesos())

    def test_con_los_dos_roles_ve_los_dos_accesos(self):
        ambos = self._sumar_rol(self._usuario("ambos", [RELEVAR]), [ADMITIR], self.dispositivos, [self.club])

        self.assertEqual(roles_en_app(ambos), _accesos(relevar=True, llegadas=True))

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
                [
                    URL_RAIZ,
                    URL_PERFIL,
                    URL_CONSULTAR,
                    URL_SUGERIR,
                    URL_LOCALIDADES,
                    URL_CASOS,
                    URL_MIOS,
                    URL_MIS_DISPOSITIVOS,
                ]
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
            (self.agente, _accesos(relevar=True)),
            (self.guardia, _accesos(llegadas=True)),
            (ambos, _accesos(relevar=True, llegadas=True)),
        )

        for usuario, esperado in casos:
            with self.subTest(usuario=usuario.username):
                respuesta = self._como(usuario).get(URL_PERFIL)
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(sorted(respuesta.json()), CLAVES_PERFIL)
                self.assertEqual(respuesta.json(), esperado)

    def test_el_perfil_separa_llegadas_de_kits(self):
        """M2 con ``llegadas``, M3 con ``kits``; ``dispositivo`` sigue siendo cualquiera de las dos (Cambio 475).

        Mutaciones vistas en rojo: ``llegadas`` o ``kits`` fijos en ``False``, o intercambiados
        (``admite_familias`` ↔ ``recibe_kits``), rompen las filas de un solo acceso.
        """
        casos = (
            ("solo_admite", [ADMITIR], [self.club], _accesos(llegadas=True)),
            ("solo_kits", [RECIBIR_KIT], [self.club], _accesos(kits=True)),
            ("admite_y_kits", [ADMITIR, RECIBIR_KIT], [self.club], _accesos(llegadas=True, kits=True)),
            # Abre el módulo (H10) sin ninguna de las dos: el único que ve todo en `false`.
            ("ninguno", ["programa.configurar"], [], _accesos()),
        )

        for nombre, capacidades, equipo, esperado in casos:
            with self.subTest(usuario=nombre):
                respuesta = self._como(self._guardia(nombre, capacidades, equipo)).get(URL_PERFIL)

                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(sorted(respuesta.json()), CLAVES_PERFIL)
                self.assertEqual(respuesta.json(), esperado)

    def test_llegadas_y_kits_miran_el_alcance_no_solo_la_capacidad(self):
        """Tildadas en un rol sin Equipo no abren nada, igual que ``dispositivo``."""
        sin_equipo = self._guardia("sin_equipo_perfil", [ADMITIR, RECIBIR_KIT])

        self.assertEqual(roles_en_app(sin_equipo), _accesos())


# ---------------------------------------------------------------------------
# Consulta de identidad (H2)
# ---------------------------------------------------------------------------


class _ConsultaDePersonaBase(BaseApiEmergencia):
    """Fixture y helpers de la consulta de persona, sin tests: los comparten las dos clases de abajo."""

    PERSONA = {"success": True, "data": {"nombre": "Rosa", "apellido": "Benitez", "fecha_nacimiento": "1984-03-02"}}

    def setUp(self):
        super().setUp()
        parche = mock.patch("programas.services.identidad.consultar_persona", return_value=self.PERSONA)
        self.gran_base = parche.start()
        self.addCleanup(parche.stop)

    def _consultar(self, usuario, url=URL_CONSULTAR, **cuerpo):
        return self._como(usuario).post(url, {"dni": "30.111.222", "sexo": "f", **cuerpo}, format="json")

    def _legajo(self, **campos):
        from core.models import Localidad
        from legajos.models import Ciudadano

        localidad = Localidad.objects.create(nombre="Resistencia")
        base = dict(
            dni="30111222",
            nombre="Rosa",
            apellido="Benitez",
            fecha_nacimiento="1984-03-02",
            genero="F",
            localidad=localidad,
        )
        return Ciudadano.objects.create(**{**base, **campos})

    def _gran_base_no_la_encuentra(self):
        self.gran_base.return_value = {"success": False, "error": "No se encontró", "not_found": True}


class ConsultaDePersonaTests(_ConsultaDePersonaBase):
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

    def test_sin_dni_es_el_400_de_siempre(self):
        for cuerpo in ({}, {"sexo": "F"}, {"dni": "", "sexo": "F"}, {"dni": "sin-digitos"}):
            with self.subTest(cuerpo=cuerpo):
                respuesta = self._como(self.agente).post(URL_CONSULTAR, cuerpo, format="json")

                self.assertEqual(respuesta.status_code, 400)
                self.assertEqual(respuesta.json(), {"success": False, "error": "DNI y sexo (F o M) son requeridos."})

    def test_un_sexo_presente_e_invalido_es_400(self):
        for sexo in ("X", "Z", "mujer"):
            with self.subTest(sexo=sexo):
                respuesta = self._como(self.agente).post(
                    URL_CONSULTAR, {"dni": "30111222", "sexo": sexo}, format="json"
                )

                self.assertEqual(respuesta.status_code, 400)
        self.gran_base.assert_not_called()

    def test_becas_sigue_exigiendo_el_sexo(self):
        ambos = self._sumar_rol(self.territorial_becas, [RELEVAR], self.programa)
        url = reverse("becas_api:personas-consultar")

        for cuerpo in ({"dni": "30111222"}, {"dni": "30111222", "sexo": ""}):
            with self.subTest(cuerpo=cuerpo):
                respuesta = self._como(ambos).post(url, cuerpo, format="json")

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

    def test_el_legajo_responde_si_base_de_personas_no_la_encuentra(self):
        legajo = self._legajo()
        self._gran_base_no_la_encuentra()

        respuesta = self._consultar(self.agente)

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(
            respuesta.json(),
            {
                "success": True,
                "origen": "legajo",
                "data": {
                    "nombre": "Rosa",
                    "apellido": "Benitez",
                    "fecha_nacimiento": "1984-03-02",
                    "localidad_id": legajo.localidad_id,
                    "localidad_texto": "Resistencia",
                    "dni": "30111222",
                    "sexo": "F",
                },
                "datos_api": {},
            },
        )

    def test_el_legajo_responde_si_base_de_personas_falla(self):
        self._legajo(fecha_nacimiento=None, localidad=None)
        self.gran_base.return_value = {"success": False, "error": "Timeout"}

        respuesta = self._consultar(self.agente)

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["origen"], "legajo")
        self.assertEqual(cuerpo["data"]["fecha_nacimiento"], "")
        self.assertIsNone(cuerpo["data"]["localidad_id"])
        self.assertEqual(cuerpo["data"]["localidad_texto"], "")

    def test_el_legajo_cargado_con_separadores_tambien_se_encuentra(self):
        legajo = self._legajo()
        # `save()` normaliza el DNI: el legajo viejo con puntos se simula con un UPDATE.
        type(legajo).objects.filter(pk=legajo.pk).update(dni="30.111.222")
        self._gran_base_no_la_encuentra()

        respuesta = self._consultar(self.agente)

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json()["origen"], "legajo")
        self.assertEqual(respuesta.json()["data"]["dni"], "30111222")

    def test_el_legajo_responde_si_base_de_personas_esta_apagada(self):
        self._legajo()

        with override_settings(PERSONAS_API_ACTIVA=False):
            respuesta = self._consultar(self.agente)

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json()["origen"], "legajo")
        self.gran_base.assert_not_called()

    def test_si_hay_legajo_responde_el_legajo_aunque_base_de_personas_la_encuentre(self):
        """Cambio 486: se muestra la persona de la que ``crear_caso`` va a colgar el caso."""
        self._legajo(nombre="Joaquin", apellido="FARIÑA")

        respuesta = self._consultar(self.agente)

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json()["origen"], "legajo")
        self.assertEqual(respuesta.json()["data"]["nombre"], "Joaquin")
        self.assertEqual(respuesta.json()["data"]["apellido"], "FARIÑA")

    def test_becas_con_legajo_sigue_respondiendo_lo_de_base_de_personas(self):
        self._legajo(nombre="Joaquin", apellido="FARIÑA")
        ambos = self._sumar_rol(self.territorial_becas, [RELEVAR], self.programa)

        respuesta = self._consultar(ambos, url=reverse("becas_api:personas-consultar"))

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json()["origen"], "personas")
        self.assertEqual(respuesta.json()["data"]["nombre"], "Rosa")

    def test_la_fallecida_no_cae_al_legajo(self):
        self._legajo()
        self.gran_base.return_value = {"success": False, "fallecido": True, "error": "Fallecida"}

        respuesta = self._consultar(self.agente)

        self.assertEqual(respuesta.status_code, 404)
        self.assertIs(respuesta.json()["fallecido"], True)

    def test_un_genero_distinto_en_el_legajo_igual_cuenta(self):
        """El DNI es único: el alta usaría ese legajo igual (Cambio 486)."""
        self._legajo(genero="M")
        self._gran_base_no_la_encuentra()

        respuesta = self._consultar(self.agente)

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json()["origen"], "legajo")

    def test_un_genero_vacio_en_el_legajo_se_acepta(self):
        self._legajo(genero="")
        self._gran_base_no_la_encuentra()

        respuesta = self._consultar(self.agente)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["origen"], "legajo")

    def test_un_legajo_inactivo_igual_cuenta(self):
        self._legajo(activo=False)
        self._gran_base_no_la_encuentra()

        respuesta = self._consultar(self.agente)

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json()["origen"], "legajo")

    def test_sin_legajo_la_falla_de_base_de_personas_sigue_siendo_502(self):
        self.gran_base.return_value = {"success": False, "error": "Timeout"}

        self.assertEqual(self._consultar(self.agente).status_code, 502)

    def test_becas_no_busca_en_el_legajo(self):
        self._legajo()
        self._gran_base_no_la_encuentra()
        ambos = self._sumar_rol(self.territorial_becas, [RELEVAR], self.programa)

        respuesta = self._consultar(ambos, url=reverse("becas_api:personas-consultar"))

        self.assertEqual(respuesta.status_code, 404)

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


class SugerirPersonasTests(_ConsultaDePersonaBase):
    """#1299 · sugerencias del legajo mientras se escribe el DNI: lo mismo que el paso 1 de Dispositivos."""

    def _sugerir(self, usuario, q):
        return self._como(usuario).get(URL_SUGERIR, {"q": q})

    def test_sugiere_por_prefijo_de_dni_solo_con_apellido_nombre_y_dni(self):
        self._legajo()
        self._legajo(dni="30999000", nombre="Otra", apellido="Distinta")

        respuesta = self._sugerir(self.agente, "30111")

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(
            respuesta.json(),
            {"resultados": [{"apellido": "Benitez", "nombre": "Rosa", "dni": "30111222"}], "hay_mas": False},
        )
        self.assertEqual(respuesta["Cache-Control"], "no-store")
        self.gran_base.assert_not_called()

    def test_acepta_el_dni_con_puntos(self):
        self._legajo()

        self.assertEqual(len(self._sugerir(self.agente, "30.1112").json()["resultados"]), 1)

    def test_con_menos_de_cinco_digitos_no_busca(self):
        self._legajo()

        for q in ("", "3", "30", "3011", "ab"):
            with self.subTest(q=q):
                respuesta = self._sugerir(self.agente, q)
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(respuesta.json(), {"resultados": [], "hay_mas": False})

    def test_letras_no_son_un_dni(self):
        self._legajo()

        self.assertEqual(self._sugerir(self.agente, "benitez").json()["resultados"], [])

    def test_exige_emergencia_relevar_incluso_con_el_modulo_abierto(self):
        self._legajo()

        self.assertEqual(self._sugerir(self.operador, "30111").status_code, 403)
        self.assertEqual(self._sugerir(self.territorial_becas, "30111").status_code, 403)
        self.assertEqual(self._sugerir(self.guardia, "30111").status_code, 403, "abre el módulo pero no relevá")
        self.assertEqual(self._sugerir(self.agente, "30111").status_code, 200)

    @mock.patch.object(ConsultaPersonasThrottle, "get_rate", return_value="1/hour")
    def test_sin_permiso_no_gasta_la_cubeta(self, _rate):
        self._legajo()

        self.assertEqual(self._sugerir(self.guardia, "30111").status_code, 403)
        self.assertEqual(self._sugerir(self.guardia, "30111").status_code, 403)
        self.assertEqual(self._sugerir(self.agente, "30111").status_code, 200)

    def test_sin_token_no_entra(self):
        from rest_framework.test import APIClient

        self.assertEqual(APIClient().get(URL_SUGERIR, {"q": "30111"}).status_code, 401)

    @mock.patch.object(ConsultaPersonasThrottle, "get_rate", return_value="1/hour")
    def test_comparte_la_cubeta_de_la_consulta_de_identidad(self, _rate):
        self._legajo()

        self.assertEqual(self._sugerir(self.agente, "30111").status_code, 200)
        self.assertEqual(self._sugerir(self.agente, "30111").status_code, 429)
        self.assertEqual(self._consultar(self.agente).status_code, 429)

    @mock.patch.object(ConsultaPersonasThrottle, "get_rate", return_value="1/hour")
    def test_lo_que_no_busca_no_descuenta_de_la_cubeta(self, _rate):
        for _ in range(3):
            self.assertEqual(self._sugerir(self.agente, "3011").status_code, 200)
        self.assertEqual(self._consultar(self.agente).status_code, 200)

    def test_el_esquema_publica_la_ruta_y_el_429(self):
        from drf_spectacular.generators import SchemaGenerator

        rutas = SchemaGenerator().get_schema(request=None, public=True)["paths"]

        self.assertIn("429", rutas[URL_SUGERIR]["get"]["responses"])
        self.assertEqual(rutas[URL_SUGERIR]["get"]["parameters"][0]["name"], "q")


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
            (URL_SUGERIR, "get"),
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
            (rutas[URL_SUGERIR]["get"], "200", CLAVES_SUGERENCIAS),
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
        resultados = self._componente(rutas[URL_SUGERIR]["get"])["properties"]["resultados"]["items"]["$ref"]
        item = self.esquema["components"]["schemas"][resultados.split("/")[-1]]
        self.assertEqual(sorted(item["properties"]), CLAVES_SUGERENCIA)

    def test_integrantes_publica_la_derivacion_y_los_cierres_la_aceptan_opcional(self):
        """Cambio 477: el `GET` dice qué derivación se mira y los tres cierres la reciben sin exigirla."""
        rutas = self.esquema["paths"]
        componentes = self.esquema["components"]["schemas"]

        integrantes = self._componente(rutas["/api/emergencia/casos/{id}/integrantes/"]["get"])
        propiedad = integrantes["properties"]["derivacion"]
        derivacion = componentes[(propiedad.get("allOf") or [propiedad])[0]["$ref"].split("/")[-1]]
        self.assertEqual(sorted(derivacion["properties"]), CLAVES_DERIVACION_DEL_INGRESO)
        self.assertIn("derivacion", integrantes["required"])
        for ruta in ("alojar", "cerrar-diferencia", "cancelar-ingreso"):
            with self.subTest(ruta=ruta):
                cuerpo = rutas[f"/api/emergencia/casos/{{id}}/{ruta}/"]["post"]["requestBody"]["content"]
                envio = componentes[cuerpo["application/json"]["schema"]["$ref"].split("/")[-1]]
                self.assertEqual(envio["properties"]["derivacion"]["type"], "integer")
                self.assertNotIn("derivacion", envio.get("required", []))

    def test_las_consultas_con_tope_publican_el_429(self):
        """La identidad (SEC-25), la búsqueda por DNI (M2-1) y los tres extremos que crean casos, cuyo rechazo
        «DNI ya registrado» descuenta de la cubeta de la identidad (Cambio 486): la app sabe que pueden contestar 429."""
        rutas = self.esquema["paths"]

        for operacion in (
            rutas[URL_CONSULTAR]["post"],
            rutas["/api/emergencia/dispositivos/{dispositivo_id}/buscar/"]["get"],
            rutas[URL_CASOS]["post"],
            rutas["/api/emergencia/dispositivos/{dispositivo_id}/ingreso-directo/"]["post"],
            rutas["/api/emergencia/dispositivos/{dispositivo_id}/avisar-mesa/"]["post"],
        ):
            with self.subTest(operacion=operacion["operationId"]):
                self.assertIn("429", operacion["responses"])

    def test_los_extremos_que_crean_casos_publican_persona_registrada(self):
        rutas = self.esquema["paths"]

        for operacion in (
            rutas[URL_CASOS]["post"],
            rutas["/api/emergencia/dispositivos/{dispositivo_id}/ingreso-directo/"]["post"],
            rutas["/api/emergencia/dispositivos/{dispositivo_id}/avisar-mesa/"]["post"],
        ):
            with self.subTest(operacion=operacion["operationId"]):
                self.assertIn("persona_registrada", operacion["responses"]["400"]["description"])

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

        # Desde el Cambio 522 el de Emergencia hereda el de Becas y solo suelta el `required: sexo`
        # (la puerta del dispositivo consulta solo con el DNI): el resto del cuerpo es idéntico.
        componentes = self.esquema["components"]["schemas"]
        schema_emergencia = componentes[de_emergencia["schema"]["$ref"].split("/")[-1]]
        schema_becas = componentes[de_becas["schema"]["$ref"].split("/")[-1]]
        self.assertEqual(schema_becas["required"], ["dni", "sexo"])
        self.assertEqual(schema_emergencia["required"], ["dni"])
        self.assertEqual(schema_emergencia["properties"].keys(), schema_becas["properties"].keys())

    def test_el_estado_y_la_prioridad_del_caso_tienen_nombre_propio(self):
        """Sin nombre propio, Spectacular los llama con un hash que cambia al tocar cualquier `choices`."""
        componentes = self.esquema["components"]["schemas"]

        self.assertEqual(componentes["CasoEmergenciaEstadoEnum"]["enum"], list(Estado.values))
        self.assertEqual(componentes["CasoEmergenciaPrioridadEnum"]["enum"], list(Prioridad.values))


class ConsultaDePersonaSinSexoTests(_ConsultaDePersonaBase):
    """La puerta del dispositivo sabe el DNI y no el sexo: sin sexo se busca solo en legajos."""

    def _sin_sexo(self, usuario, **cuerpo):
        return self._como(usuario).post(URL_CONSULTAR, {"dni": "30.111.222", **cuerpo}, format="json")

    def test_con_legajo_responde_el_legajo_sin_llamar_a_base_de_personas(self):
        legajo = self._legajo()

        for cuerpo in ({}, {"sexo": ""}, {"sexo": None}):
            with self.subTest(cuerpo=cuerpo):
                respuesta = self._sin_sexo(self.agente, **cuerpo)

                self.assertEqual(respuesta.status_code, 200, respuesta.content)
                self.assertEqual(
                    respuesta.json(),
                    {
                        "success": True,
                        "origen": "legajo",
                        "data": {
                            "nombre": "Rosa",
                            "apellido": "Benitez",
                            "fecha_nacimiento": "1984-03-02",
                            "localidad_id": legajo.localidad_id,
                            "localidad_texto": "Resistencia",
                            "dni": "30111222",
                            "sexo": "F",
                        },
                        "datos_api": {},
                    },
                )
        self.gran_base.assert_not_called()

    def test_el_sexo_del_legajo_solo_se_devuelve_si_mapea_limpio(self):
        legajo = self._legajo(genero="M")
        self.assertEqual(self._sin_sexo(self.guardia).json()["data"]["sexo"], "M")
        for genero in ("X", ""):
            with self.subTest(genero=genero):
                type(legajo).objects.filter(pk=legajo.pk).update(genero=genero)

                self.assertEqual(self._sin_sexo(self.guardia).json()["data"]["sexo"], "")

    def test_sin_legajo_es_404_no_en_legajo_sin_llamar_a_base_de_personas(self):
        respuesta = self._sin_sexo(self.agente)

        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(
            respuesta.json(),
            {"success": False, "no_en_legajo": True, "error": "No figura en los legajos de DATAÑACH."},
        )
        self.gran_base.assert_not_called()

    def test_con_sexo_el_comportamiento_no_cambia(self):
        self._legajo(nombre="Del legajo")

        respuesta = self._consultar(self.agente, sexo="M")

        self.assertEqual(respuesta.json()["origen"], "legajo")
        self.gran_base.assert_called_once()

    def test_con_otro_sexo_la_respuesta_trae_el_del_legajo(self):
        """#1301: el sexo de la consulta nunca pisa el del legajo."""
        self._legajo(genero="F")

        for pedido in ("M", "F", "m"):
            with self.subTest(pedido=pedido):
                respuesta = self._consultar(self.agente, sexo=pedido)

                self.assertEqual(respuesta.json()["origen"], "legajo")
                self.assertEqual(respuesta.json()["data"]["sexo"], "F")

    def test_con_sexo_y_legajo_sin_sexo_la_respuesta_trae_vacio(self):
        self._legajo(genero="X")

        respuesta = self._consultar(self.agente, sexo="M")

        self.assertEqual(respuesta.json()["origen"], "legajo")
        self.assertEqual(respuesta.json()["data"]["sexo"], "")
