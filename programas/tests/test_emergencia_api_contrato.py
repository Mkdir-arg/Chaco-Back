"""Módulo Emergencia, PR 5: la API de campo (base, login, perfil y M1) y su contrato.

Lo que lee la app (`Chaco-mobile`) está fijado acá con **claves exactas** (las constantes
``CLAVES_*``) y documentado en ``docs/internal/contrato-app-emergencia.md``: agregar una
clave es seguro; renombrarla o sacarla es un release coordinado de la app, y este archivo se
toca en el mismo diff.

Qué fija, regla por regla:

* **H10 / RU-4** — una sola regla de acceso al módulo (``modulo_habilitado``): la usan el
  login (``"emergencia"`` en ``modulos``) y los permisos del namespace. Agente con
  ``emergencia.relevar``, guardia con ``dispositivo.admitir`` o ``emergencia.recibir_kit``
  **en el Equipo** de un dispositivo, o administrador del programa Dispositivos.
* **H11** — las claves del login no cambian (``CLAVES_LOGIN`` es el de Becas, importado);
  cambia un valor posible de ``modulos``, siempre al final.
* **RU §6 n.° 3, mitad API** — un rol de Becas no abre Emergencia y el agente de Emergencia
  no abre Becas. Son barridos del URLconf, no listas a mano.
* **RU §6 n.° 5 / RN-1.8 / RU-16** — el mismo ``uuid_cliente`` dos veces crea **un** caso.
* **RN-1.2, 1.3, 1.9, 1.12 y RU-18** — total y prioridad del servidor, las validaciones del
  paso 3, fotos solo JPEG de hasta 5 MB, dirección obligatoria y la hora del teléfono.
* **H2** — la consulta de identidad de Emergencia es la de Becas, con permiso propio y la
  misma cubeta de throttle.
* **Presupuestos** — ``localidades`` y ``casos/mios`` no crecen con las filas.

Los dos tests de mutación (``test_un_rol_de_becas_no_abre_el_modulo…`` y
``test_el_mismo_uuid_cliente_dos_veces_crea_un_solo_caso``) se vieron en rojo contra la
regla rota antes de quedar verdes; el detalle está en el docstring de cada uno.
"""

import shutil
import tempfile
import uuid
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import AnonymousUser, Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import override_settings, tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core import rbac
from core.models import Localidad, Municipio, Provincia
from core.tests.test_api_schema_contrato import _generar_esquema_y_sus_avisos
from core.tests.test_superficie_publica import rutas_concretas
from core.validators import ADJUNTO_MAX_BYTES, MENSAJE_ADJUNTO_TAMANIO
from legajos.models import Ciudadano
from programas.api.serializers_emergencia import MENSAJE_FOTO_JPEG
from programas.api.views import ConsultaPersonasThrottle
from programas.api.views_emergencia import MENSAJE_SIN_MODULO, MENSAJE_SIN_RELEVAR
from programas.models import AdjuntoCaso, CasoEmergencia, GrupoFamiliar, MiembroEquipoDispositivo, TrazaCaso
from programas.selectors.emergencia_campo import TOPE_MIS_CASOS, casos_relevados_por, localidades_para_relevar
from programas.services import emergencia as servicio
from programas.services.emergencia_campo import RELEVADO_EN_FUTURO
from programas.services.emergencia_programa import modulo_habilitado, roles_en_app
from programas.tests.test_becas_api_contrato import CLAVES_LOGIN
from programas.tests.test_emergencia_base import OPERAR, RECIBIR_KIT, RELEVAR, _permiso
from programas.tests.test_emergencia_casos import JPEG, T0, BaseCasos
from users.models import Profile, RolMeta

Estado = CasoEmergencia.Estado
Origen = CasoEmergencia.Origen
Prioridad = CasoEmergencia.Prioridad

ADMITIR = "dispositivo.admitir"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64

# --- El contrato: claves exactas de cada respuesta ---------------------------------------

CLAVES_RAIZ = ["casos", "casos/mios", "localidades", "perfil", "personas/consultar"]
CLAVES_PERFIL = ["dispositivo", "relevar"]
CLAVES_LOCALIDAD = ["id", "nombre"]
CLAVES_CASO_CREADO = ["id", "numero", "prioridad", "total_declarado"]
CLAVES_MI_CASO = ["creado_en", "estado", "numero", "total_declarado"]
CLAVES_CONSULTA = ["data", "datos_api", "origen", "success"]
CLAVES_SIN_MODULO = ["code", "detail"]
CLAVES_UUID_EN_USO = ["code", "detail"]
#: El 400 trae además una clave por cada campo con error.
CLAVES_FIJAS_DEL_400 = {"code", "detail", "non_field_errors"}

SIN_MODULO = {"detail": MENSAJE_SIN_MODULO, "code": "SIN_MODULO"}
SIN_RELEVAR = {"detail": MENSAJE_SIN_RELEVAR, "code": "SIN_MODULO"}

URL_RAIZ = "/api/emergencia/"
URL_PERFIL = "/api/emergencia/perfil/"
URL_CONSULTAR = "/api/emergencia/personas/consultar/"
URL_LOCALIDADES = "/api/emergencia/localidades/"
URL_CASOS = "/api/emergencia/casos/"
URL_MIOS = "/api/emergencia/casos/mios/"

#: Las rutas que solo abre el agente; el resto las abre cualquiera con el módulo.
SOLO_DEL_AGENTE = {URL_CASOS, URL_MIOS}


def urls_de_la_api_de_emergencia():
    """Toda URL del namespace ``emergencia_api`` que existe hoy, sacada del URLconf."""
    return [url for nombre, url in rutas_concretas() if nombre.startswith("emergencia_api:")]


def urls_de_la_api_de_becas():
    """Toda URL de ``/api/becas/`` salvo el login, que es público por diseño."""
    return [url for nombre, url in rutas_concretas() if nombre.startswith("becas_api:") and nombre != "becas_api:token"]


class BaseApiEmergencia(BaseCasos):
    """La mesa de ``BaseCasos`` más lo de la app: tokens, guardia con Equipo y media temporal."""

    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        ajuste = override_settings(MEDIA_ROOT=self.media)
        ajuste.enable()
        self.addCleanup(ajuste.disable)

        self.api = APIClient()
        self.territorial_becas = self._usuario("terri_becas", ["becas.campo"], programa=self.becas)
        self.club = self._dispositivo("Club Sarmiento", camas=4)
        self.guardia = self._guardia("guardia", [ADMITIR], [self.club])

    def _sumar_rol(self, usuario, capacidades, programa, dispositivos=()):
        """Otro rol de ``programa`` para ``usuario``, y su lugar en el Equipo de ``dispositivos``."""
        rol = Group.objects.create(name=f"Rol {usuario.username} {Group.objects.count()}")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=programa, activo=True)
        rol.permissions.add(*[_permiso(codigo) for codigo in capacidades])
        usuario.groups.add(rol)
        for dispositivo in dispositivos:
            MiembroEquipoDispositivo.objects.create(dispositivo=dispositivo, usuario=usuario, rol=rol)
        return User.objects.get(pk=usuario.pk)

    def _guardia(self, nombre, capacidades, dispositivos=()):
        """Un usuario con un rol del programa DISPOSITIVOS, en el Equipo de ``dispositivos``."""
        usuario = User.objects.create_user(username=nombre, password="x")
        return self._sumar_rol(usuario, capacidades, self.dispositivos, dispositivos)

    def _como(self, usuario):
        token, _ = Token.objects.get_or_create(user=usuario)
        self.api.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        return self.api

    def _anonimo(self):
        self.api.credentials()
        return self.api

    def _login(self, username):
        return self._anonimo().post(reverse("becas_api:token"), {"username": username, "password": "x"}, format="json")

    def _foto(self, nombre="vivienda.jpg", contenido=JPEG, tipo="image/jpeg"):
        return SimpleUploadedFile(nombre, contenido, content_type=tipo)

    def _cuerpo(self, uuid_cliente=None, **cambios):
        """El Formulario 1 como lo manda la app: multipart, con su ``uuid_cliente``."""
        cuerpo = {"uuid_cliente": str(uuid_cliente or uuid.uuid4()), **self._datos()}
        cuerpo.update(cambios)
        return {clave: valor for clave, valor in cuerpo.items() if valor is not None}

    def _enviar(self, usuario=None, **cambios):
        return self._como(usuario or self.agente).post(URL_CASOS, self._cuerpo(**cambios), format="multipart")


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
        admin = self._guardia("admin_disp", ["programa.configurar"])

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
            sorted([URL_RAIZ, URL_PERFIL, URL_CONSULTAR, URL_LOCALIDADES, URL_CASOS, URL_MIOS]),
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
        este test falla dos veces: el login devuelve ``["becas", "emergencia"]`` y la raíz,
        el perfil, las localidades y la consulta contestan 200. Restaurada la regla, verde.
        """
        respuesta = self._login("terri_becas")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["modulos"], ["becas"])

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
# Enviar el Formulario 1 (M1)
# ---------------------------------------------------------------------------


class EnviarCasoTests(BaseApiEmergencia):
    def test_crea_el_caso_y_devuelve_las_cuatro_claves(self):
        respuesta = self._enviar(menores_f=2, mayores_m=1, telefono="3624111222", observaciones="Frente a la capilla")

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        caso = CasoEmergencia.objects.select_related("grupo").get()
        self.assertEqual(sorted(respuesta.json()), CLAVES_CASO_CREADO)
        self.assertEqual(
            respuesta.json(),
            {"id": caso.pk, "numero": caso.numero, "prioridad": "MEDIA", "total_declarado": 5},
        )
        # RN-1.10: nace NUEVO, sin tomar, de territorio, a nombre del agente.
        self.assertEqual(
            (caso.estado, caso.origen, caso.tomado_por, caso.relevado_por),
            (Estado.NUEVO, Origen.TERRITORIO, None, self.agente),
        )
        self.assertEqual(caso.situacion, {"telefono": "3624111222", "observaciones": "Frente a la capilla"})
        self.assertEqual(TrazaCaso.objects.get(caso=caso).detalle, "Relevado en territorio")

    def test_el_mismo_uuid_cliente_dos_veces_crea_un_solo_caso(self):
        """RU §6 n.° 5 / RN-1.8 / RU-16: el reenvío de la cola sin señal no duplica.

        **Mutación vista en rojo:** con la vista llamando a ``crear_caso`` sin el
        ``uuid_cliente`` —el envío deja de tener identidad— el segundo POST contesta 201 con
        otro ``numero`` y quedan dos casos. Restaurada la llamada, verde. (Romperlo en el
        servicio no alcanza para verlo rojo: sin la búsqueda previa, el ``UNIQUE`` de la
        columna devuelve igual el caso que ya estaba.)
        """
        identificador = uuid.uuid4()
        cuerpo = self._cuerpo(uuid_cliente=identificador, dni="30111222")

        primera = self._como(self.agente).post(URL_CASOS, dict(cuerpo), format="multipart")
        segunda = self._como(self.agente).post(URL_CASOS, dict(cuerpo), format="multipart")

        self.assertEqual(primera.status_code, 201, primera.content)
        self.assertEqual(segunda.status_code, 200, segunda.content)
        self.assertEqual(segunda.json(), primera.json())
        self.assertEqual(sorted(segunda.json()), CLAVES_CASO_CREADO)
        self.assertEqual(CasoEmergencia.objects.count(), 1)
        self.assertEqual(GrupoFamiliar.objects.count(), 1)
        self.assertEqual(TrazaCaso.objects.count(), 1)
        self.assertEqual(CasoEmergencia.objects.get().uuid_cliente, identificador)

    def test_el_reenvio_devuelve_el_caso_aunque_el_cuerpo_ya_no_valide(self):
        """El reintento no vuelve a validar: lo que se creó, se creó (paso 2 de ``crear_caso``)."""
        identificador = uuid.uuid4()
        primera = self._enviar(uuid_cliente=identificador)

        segunda = self._enviar(uuid_cliente=identificador, direccion="", adultos_f=0, adultos_m=0)

        self.assertEqual(segunda.status_code, 200, segunda.content)
        self.assertEqual(segunda.json(), primera.json())

    def test_el_uuid_de_otro_agente_es_409_y_no_devuelve_el_caso_ajeno(self):
        otro = self._usuario("otro_agente", [RELEVAR])
        identificador = uuid.uuid4()
        self._enviar(uuid_cliente=identificador)

        respuesta = self._enviar(otro, uuid_cliente=identificador)

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(sorted(respuesta.json()), CLAVES_UUID_EN_USO)
        self.assertEqual(respuesta.json(), {"detail": servicio.UUID_EN_USO, "code": "UUID_EN_USO"})
        self.assertEqual(CasoEmergencia.objects.count(), 1)

    def test_sin_uuid_cliente_es_400(self):
        cuerpo = self._cuerpo()
        del cuerpo["uuid_cliente"]

        respuesta = self._como(self.agente).post(URL_CASOS, cuerpo, format="multipart")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("uuid_cliente", respuesta.json())
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    def test_el_400_trae_code_detail_y_el_detalle_por_campo(self):
        respuesta = self._enviar(direccion="", traslado="")

        self.assertEqual(respuesta.status_code, 400)
        cuerpo = respuesta.json()
        self.assertEqual(set(cuerpo), CLAVES_FIJAS_DEL_400 | {"direccion", "traslado"})
        self.assertEqual(cuerpo["code"], "VALIDACION")
        self.assertEqual(cuerpo["traslado"], ["Elegí la fuerza que traslada."])
        self.assertIsInstance(cuerpo["detail"], str)
        self.assertIn(cuerpo["detail"], cuerpo["non_field_errors"])
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    def test_sin_direccion_no_se_envia_aunque_haya_gps(self):
        """RN-1.12: la dirección escrita es el mínimo."""
        respuesta = self._enviar(direccion="   ", latitud="-27.451", longitud="-58.986", precision_m="12")

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(
            respuesta.json()["direccion"],
            ["Escribí la dirección o una referencia: es el mínimo para ubicar a la familia."],
        )
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    def test_sin_gps_y_con_direccion_se_envia(self):
        respuesta = self._enviar()

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        caso = CasoEmergencia.objects.get()
        self.assertEqual((caso.latitud, caso.longitud, caso.precision_m), (None, None, None))

    def test_el_gps_se_guarda_con_su_precision(self):
        respuesta = self._enviar(latitud="-27.4512341", longitud="-58.9867891", precision_m="12.4")

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        caso = CasoEmergencia.objects.get()
        self.assertEqual((float(caso.latitud), float(caso.longitud), caso.precision_m), (-27.451234, -58.986789, 12))

    def test_las_validaciones_del_paso_3_las_hace_el_servidor(self):
        """RN-1.3: dependientes ≤ total, mayores dependientes ≤ mayores, lactantes ≤ menores."""
        casos = (
            ({"dependientes": 3}, "dependientes"),
            ({"mayores_dependientes": 1}, "mayores_dependientes"),
            ({"lactantes": 1}, "lactantes"),
        )
        for cambios, campo in casos:
            with self.subTest(campo=campo):
                respuesta = self._enviar(**cambios)
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn(campo, respuesta.json())
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    def test_sin_personas_no_se_envia(self):
        respuesta = self._enviar(adultos_f=0, adultos_m=0)

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["total"], ["Cargá al menos una persona."])

    def test_el_total_y_la_prioridad_que_manda_la_app_se_ignoran(self):
        """RN-1.2 y RN-1.4: los dos son del servidor."""
        respuesta = self._enviar(total=99, total_declarado=99, prioridad="ALTA", estado="CERRADO", numero="X")

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.assertEqual(respuesta.json()["total_declarado"], 2)
        self.assertEqual(respuesta.json()["prioridad"], "BAJA")
        caso = CasoEmergencia.objects.select_related("grupo").get()
        self.assertEqual((caso.grupo.total_declarado, caso.prioridad, caso.estado), (2, Prioridad.BAJA, Estado.NUEVO))

    def test_los_avisos_del_multipart_se_leen_como_booleanos(self):
        """En un formulario multipart `false` llega como texto: no puede valer como verdadero."""
        respuesta = self._enviar(embarazo="false", electrodependiente="0", medicacion_critica="", mascotas="true")

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        caso = CasoEmergencia.objects.get()
        self.assertEqual(
            caso.necesidades,
            {"embarazo": False, "electrodependiente": False, "medicacion_critica": False, "mascotas": True},
        )
        self.assertEqual(caso.prioridad, Prioridad.BAJA)

    def test_un_aviso_critico_hace_alta_la_prioridad(self):
        self.assertEqual(self._enviar(medicacion_critica="true").json()["prioridad"], "ALTA")

    def test_la_persona_que_no_esta_en_el_legajo_necesita_nombre_y_apellido(self):
        """RN-1.5: alta mínima del responsable."""
        sin_nombre = self._enviar(dni="30555666", nombre="", apellido="")
        con_nombre = self._enviar(dni="30555666", nombre="Rosa", apellido="Benítez")

        self.assertEqual(sin_nombre.status_code, 400)
        self.assertIn("nombre", sin_nombre.json())
        self.assertEqual(con_nombre.status_code, 201, con_nombre.content)
        self.assertEqual(Ciudadano.objects.get(dni="30555666").apellido, "Benítez")

    def test_tambien_acepta_json_cuando_no_hay_fotos(self):
        cuerpo = {"uuid_cliente": str(uuid.uuid4()), **self._datos(mascotas=True)}

        respuesta = self._como(self.agente).post(URL_CASOS, cuerpo, format="json")

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.assertTrue(CasoEmergencia.objects.get().necesidades["mascotas"])


class RelevadoEnTests(BaseApiEmergencia):
    """RU-18 / RN-1.8: ``relevado_en`` es la única hora del cliente que se guarda."""

    def _relevado_en(self, respuesta):
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        return CasoEmergencia.objects.get(pk=respuesta.json()["id"]).relevado_en

    def test_se_guarda_la_hora_del_telefono_y_creado_es_del_servidor(self):
        hace_dos_horas = T0 - timedelta(hours=2)

        respuesta = self._enviar(relevado_en=hace_dos_horas.isoformat())

        self.assertEqual(self._relevado_en(respuesta), hace_dos_horas)
        self.assertGreater(CasoEmergencia.objects.get().creado, hace_dos_horas)

    def test_un_envio_que_espero_dias_sin_senal_conserva_su_hora(self):
        hace_tres_dias = T0 - timedelta(days=3)

        self.assertEqual(self._relevado_en(self._enviar(relevado_en=hace_tres_dias.isoformat())), hace_tres_dias)

    def test_sin_relevado_en_vale_la_del_servidor(self):
        self.assertEqual(self._relevado_en(self._enviar()), T0)

    def test_dentro_de_la_tolerancia_queda_como_vino(self):
        adelantada = T0 + timedelta(minutes=3)

        self.assertEqual(self._relevado_en(self._enviar(relevado_en=adelantada.isoformat())), adelantada)

    def test_un_reloj_adelantado_unas_horas_se_recorta_a_la_hora_del_servidor(self):
        """Rechazarlo dejaría cada familia de ese teléfono en 400 hasta que le arreglen la hora."""
        adelantada = T0 + timedelta(hours=3)

        self.assertEqual(self._relevado_en(self._enviar(relevado_en=adelantada.isoformat())), T0)

    def test_una_fecha_de_mas_de_un_dia_en_el_futuro_se_rechaza(self):
        respuesta = self._enviar(relevado_en=(T0 + timedelta(days=2)).isoformat())

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["relevado_en"], [RELEVADO_EN_FUTURO])
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    def test_una_fecha_ilegible_se_rechaza(self):
        respuesta = self._enviar(relevado_en="ayer a la tarde")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("relevado_en", respuesta.json())


class FotosDelEnvioTests(BaseApiEmergencia):
    """RN-1.9: hasta dos fotos, JPEG, de hasta 5 MB."""

    def test_las_dos_fotos_quedan_en_el_caso_con_su_tipo(self):
        respuesta = self._enviar(foto_vivienda=self._foto(), foto_acceso=self._foto("acceso.jpeg"))

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        caso = CasoEmergencia.objects.get()
        adjuntos = list(AdjuntoCaso.objects.filter(caso=caso).order_by("tipo"))
        self.assertEqual([adjunto.tipo for adjunto in adjuntos], ["ACCESO", "VIVIENDA"])
        for adjunto in adjuntos:
            self.assertEqual(adjunto.cargado_por, self.agente)
            # RU-17: detrás de login, bajo la carpeta opaca del caso.
            self.assertTrue(adjunto.archivo.name.startswith(f"emergencia/casos/{caso.carpeta_media}/"))

    def test_la_respuesta_no_trae_las_fotos(self):
        """El archivo no vuelve: la app ya lo tiene y ``/media/`` va por sesión."""
        respuesta = self._enviar(foto_vivienda=self._foto())

        self.assertEqual(sorted(respuesta.json()), CLAVES_CASO_CREADO)

    def test_un_png_se_rechaza_aunque_el_modelo_lo_admita(self):
        respuesta = self._enviar(foto_vivienda=self._foto("vivienda.png", PNG, "image/png"))

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["foto_vivienda"], [MENSAJE_FOTO_JPEG])
        self.assertEqual(respuesta.json()["code"], "VALIDACION")
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    def test_un_png_renombrado_a_jpg_se_rechaza_por_la_firma(self):
        respuesta = self._enviar(foto_acceso=self._foto("acceso.jpg", PNG))

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["foto_acceso"], [MENSAJE_FOTO_JPEG])
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    def test_un_jpeg_de_mas_de_5_mb_se_rechaza(self):
        pesada = self._foto(contenido=JPEG + b"0" * ADJUNTO_MAX_BYTES)

        respuesta = self._enviar(foto_vivienda=pesada)

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["foto_vivienda"], [MENSAJE_ADJUNTO_TAMANIO])
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    def test_un_jpeg_en_el_limite_entra(self):
        justa = self._foto(contenido=JPEG + b"0" * (ADJUNTO_MAX_BYTES - len(JPEG)))

        self.assertEqual(self._enviar(foto_vivienda=justa).status_code, 201)

    def test_la_foto_rechazada_no_deja_caso_ni_gasta_numero(self):
        self._enviar(foto_vivienda=self._foto("vivienda.png", PNG, "image/png"))

        respuesta = self._enviar()

        self.assertEqual(respuesta.status_code, 201)
        self.assertTrue(respuesta.json()["numero"].endswith("-000001"))


# ---------------------------------------------------------------------------
# Mis envíos
# ---------------------------------------------------------------------------


class MisCasosTests(BaseApiEmergencia):
    def test_trae_solo_los_del_agente_del_mas_nuevo_al_mas_viejo(self):
        otro = self._usuario("otro_agente", [RELEVAR])
        primero = self._caso(adultos_f=3)
        self.reloj.avanzar(minutes=5)
        segundo = self._caso()
        self._caso(usuario=otro)

        respuesta = self._como(self.agente).get(URL_MIOS)

        self.assertEqual(respuesta.status_code, 200)
        filas = respuesta.json()
        self.assertEqual([fila["numero"] for fila in filas], [segundo.numero, primero.numero])
        for fila in filas:
            self.assertEqual(sorted(fila), CLAVES_MI_CASO)
        self.assertEqual(filas[1]["total_declarado"], 4)
        self.assertEqual(filas[1]["estado"], "NUEVO")
        self.assertEqual(self._como(otro).get(URL_MIOS).json()[0]["numero"][-1], "3")

    def test_el_estado_sigue_al_caso(self):
        caso = self._caso()
        servicio.tomar_caso(caso, self.operador)

        self.assertEqual(self._como(self.agente).get(URL_MIOS).json()[0]["estado"], "EN_GESTION")

    def test_lo_que_el_mismo_usuario_cargo_desde_la_mesa_no_es_un_envio(self):
        """``relevado_por`` también es quien carga en la mesa: «Mis envíos» son los de territorio."""
        doble = self._sumar_rol(self.agente, [OPERAR], self.programa)
        self._caso(origen=Origen.MESA, usuario=doble)
        de_territorio = self._caso(usuario=doble)

        filas = self._como(doble).get(URL_MIOS).json()

        self.assertEqual([fila["numero"] for fila in filas], [de_territorio.numero])

    def test_sin_envios_es_una_lista_vacia(self):
        self.assertEqual(self._como(self.agente).get(URL_MIOS).json(), [])

    @tag("performance")
    def test_trae_como_mucho_cincuenta_en_una_consulta(self):
        for _ in range(TOPE_MIS_CASOS + 3):
            self._caso()

        with self.assertNumQueries(1):
            casos = list(casos_relevados_por(self.agente))
            totales = [caso.grupo.total_declarado for caso in casos]

        self.assertEqual(len(casos), TOPE_MIS_CASOS)
        self.assertEqual(totales, [2] * TOPE_MIS_CASOS)

    @tag("performance")
    def test_el_endpoint_no_crece_con_los_casos(self):
        cliente = self._como(self.agente)
        self._caso()
        cliente.get(URL_MIOS)  # deja memoizado el programa, que es una clave de proceso
        with CaptureQueriesContext(connection) as con_uno:
            cliente.get(URL_MIOS)
        for _ in range(12):
            self._caso()

        with self.assertNumQueries(len(con_uno)):
            self.assertEqual(len(cliente.get(URL_MIOS).json()), 13)


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
        for ruta, metodo in (
            (URL_PERFIL, "get"),
            (URL_CONSULTAR, "post"),
            (URL_LOCALIDADES, "get"),
            (URL_CASOS, "post"),
            (URL_MIOS, "get"),
        ):
            with self.subTest(ruta=ruta):
                self.assertEqual(list(rutas[ruta]), [metodo])
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
        )
        for operacion, codigo, claves in casos:
            with self.subTest(operacion=operacion["operationId"], codigo=codigo):
                self.assertEqual(sorted(self._componente(operacion, codigo)["properties"]), claves)

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
