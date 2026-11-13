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
from django.core.exceptions import ValidationError
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
from programas.api.serializers_emergencia import (
    MENSAJE_CANTIDADES_INVALIDAS,
    MENSAJE_FOTO_JPEG,
    MENSAJE_SIN_CANTIDADES,
)
from programas.api.views import ConsultaPersonasThrottle
from programas.api.views_emergencia import MENSAJE_SIN_MODULO, MENSAJE_SIN_RECIBIR_KIT, MENSAJE_SIN_RELEVAR
from programas.models import (
    AdjuntoCaso,
    CasoEmergencia,
    EntradaBitacora,
    EntregaKit,
    GrupoFamiliar,
    LineaEntrega,
    MiembroEquipoDispositivo,
    TipoKit,
    TrazaCaso,
    TrazaEntrega,
)
from programas.selectors import kits as selectores_kits
from programas.selectors.emergencia_campo import TOPE_MIS_CASOS, casos_relevados_por, localidades_para_relevar
from programas.services import emergencia as servicio
from programas.services import emergencia_alta
from programas.services import kits as servicio_kits
from programas.services.emergencia import UuidEnUso
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

CLAVES_RAIZ = ["casos", "casos/mios", "localidades", "mis-dispositivos", "perfil", "personas/consultar"]
CLAVES_PERFIL = ["dispositivo", "relevar"]
CLAVES_LOCALIDAD = ["id", "nombre"]
CLAVES_CASO_CREADO = ["id", "numero", "prioridad", "total_declarado"]
CLAVES_MI_CASO = ["creado_en", "estado", "numero", "total_declarado"]
CLAVES_CONSULTA = ["data", "datos_api", "origen", "success"]
CLAVES_SIN_MODULO = ["code", "detail"]
CLAVES_UUID_EN_USO = ["code", "detail"]
# M3 · Recepción de kits (PR 9-API).
CLAVES_MI_DISPOSITIVO = ["entregas_pendientes", "id", "nombre"]
CLAVES_ENTREGA = [
    "despachada_en",
    "estado",
    "id",
    "lineas",
    "numero",
    "observacion_dispositivo",
    "observacion_mesa",
    "recibida_en",
]
CLAVES_LINEA_DE_ENTREGA = ["enviada", "item", "nombre", "recibida", "unidad"]
CLAVES_RECEPCION = ["diferencias", "estado"]
CLAVES_DIFERENCIA = ["enviada", "item", "recibida"]
CLAVES_ESTADO_CAMBIO = ["detail", "estado_actual"]
#: El 400 trae además una clave por cada campo con error.
CLAVES_FIJAS_DEL_400 = {"code", "detail", "non_field_errors"}

SIN_MODULO = {"detail": MENSAJE_SIN_MODULO, "code": "SIN_MODULO"}
SIN_RELEVAR = {"detail": MENSAJE_SIN_RELEVAR, "code": "SIN_MODULO"}
SIN_RECIBIR_KIT = {"detail": MENSAJE_SIN_RECIBIR_KIT, "code": "SIN_MODULO"}

URL_RAIZ = "/api/emergencia/"
URL_PERFIL = "/api/emergencia/perfil/"
URL_CONSULTAR = "/api/emergencia/personas/consultar/"
URL_LOCALIDADES = "/api/emergencia/localidades/"
URL_CASOS = "/api/emergencia/casos/"
URL_MIOS = "/api/emergencia/casos/mios/"
URL_MIS_DISPOSITIVOS = "/api/emergencia/mis-dispositivos/"
#: Las de M3 que llevan un id: así las concreta el barrido del URLconf.
URLS_DE_KITS_DEL_BARRIDO = [
    "/api/emergencia/dispositivos/1/entregas/",
    "/api/emergencia/entregas/1/",
    "/api/emergencia/entregas/1/recibir/",
]

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
            sorted(
                [URL_RAIZ, URL_PERFIL, URL_CONSULTAR, URL_LOCALIDADES, URL_CASOS, URL_MIOS, URL_MIS_DISPOSITIVOS]
                + URLS_DE_KITS_DEL_BARRIDO
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

    def test_el_409_sale_por_tipo_aunque_cambie_el_texto_del_mensaje(self):
        """La vista atrapa ``UuidEnUso`` por tipo, no compara el texto (hallazgo MINOR del PR #1130).

        **Mutación vista en rojo:** con la vista comparando otra vez ``errores["uuid_cliente"]``
        contra ``[UUID_EN_USO]``, el mensaje cambiado sale como 400 ``VALIDACION``. Restaurada la
        captura por tipo, verde.
        """
        otro = self._usuario("otro_agente", [RELEVAR])
        identificador = uuid.uuid4()
        self._enviar(uuid_cliente=identificador)

        with mock.patch.object(emergencia_alta, "UUID_EN_USO", "Ese identificador ya lo usó otra persona."):
            respuesta = self._enviar(otro, uuid_cliente=identificador)

        self.assertEqual(respuesta.status_code, 409, respuesta.content)
        self.assertEqual(
            respuesta.json(), {"detail": "Ese identificador ya lo usó otra persona.", "code": "UUID_EN_USO"}
        )
        self.assertEqual(CasoEmergencia.objects.count(), 1)

    def test_el_uuid_en_uso_sigue_siendo_un_validation_error_con_su_clave(self):
        """La mesa y los tests que lo atrapan como ``ValidationError`` lo ven igual que antes."""
        error = servicio.UuidEnUso()

        self.assertIsInstance(error, ValidationError)
        self.assertEqual(error.message_dict, {"uuid_cliente": [servicio.UUID_EN_USO]})

    def test_el_reenvio_no_revalida_lo_que_el_serializer_ya_no_rechaza(self):
        """§6: el segundo cuerpo con reglas del Formulario 1 rotas igual devuelve el caso (200).

        Una cantidad negativa y un ``traslado_otro`` de más de 120 caracteres los rechazaría el
        servicio, que no llega a validarlos; antes los frenaba el serializer con un 400.
        """
        identificador = uuid.uuid4()
        primera = self._enviar(uuid_cliente=identificador)

        segunda = self._enviar(
            uuid_cliente=identificador, adultos_f=-1, traslado=GrupoFamiliar.Traslado.OTRA, traslado_otro="x" * 200
        )

        self.assertEqual(primera.status_code, 201, primera.content)
        self.assertEqual(segunda.status_code, 200, segunda.content)
        self.assertEqual(segunda.json(), primera.json())
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

    def test_traslado_otro_tiene_el_tope_del_modelo_y_no_uno_propio(self):
        """El largo de ``traslado_otro`` lo decide el modelo (120), igual que en la mesa.

        **Mutación vista en rojo:** con ``max_length=60`` de vuelta en el serializer, los 80
        caracteres dan 400 con el mensaje de DRF. Restaurado, verde.
        """
        respuesta = self._enviar(traslado=GrupoFamiliar.Traslado.OTRA, traslado_otro="G" * 80)

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.assertEqual(CasoEmergencia.objects.get().grupo.traslado_otro, "G" * 80)

        largo = self._enviar(traslado=GrupoFamiliar.Traslado.OTRA, traslado_otro="G" * 121)

        self.assertEqual(largo.status_code, 400, largo.content)
        cuerpo = largo.json()
        self.assertEqual(cuerpo["code"], "VALIDACION")
        self.assertEqual(set(cuerpo), CLAVES_FIJAS_DEL_400 | {"traslado_otro"})
        self.assertIn("120", cuerpo["traslado_otro"][0])
        self.assertEqual(CasoEmergencia.objects.count(), 1)

    def test_una_cantidad_negativa_la_rechaza_el_servicio_junto_con_los_demas_errores(self):
        """El signo lo valida ``crear_caso`` con su mensaje, en el mismo 400 que el resto.

        **Mutación vista en rojo:** con ``min_value=0`` de vuelta en ``_cantidad`` el 400 sale
        del serializer, con el mensaje de DRF y sin la clave ``direccion``. Restaurado, verde.
        """
        respuesta = self._enviar(adultos_f=-1, direccion="")

        self.assertEqual(respuesta.status_code, 400, respuesta.content)
        cuerpo = respuesta.json()
        self.assertEqual(set(cuerpo), CLAVES_FIJAS_DEL_400 | {"adultos_f", "direccion"})
        self.assertEqual(cuerpo["adultos_f"], ["No puede ser negativo."])
        self.assertEqual(
            cuerpo["direccion"], ["Escribí la dirección o una referencia: es el mínimo para ubicar a la familia."]
        )
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
        self.assertEqual(respuesta.json(), [{"id": self.club.pk, "nombre": "Club Sarmiento", "entregas_pendientes": 2}])

    def test_la_guardia_que_solo_admite_ve_su_dispositivo_con_cero_pendientes(self):
        respuesta = self._como(self.guardia).get(URL_MIS_DISPOSITIVOS)

        self.assertEqual(respuesta.json(), [{"id": self.club.pk, "nombre": "Club Sarmiento", "entregas_pendientes": 0}])

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

        con_uno = consultas(self.deposito)
        muchos = [self._dispositivo(f"Sede {n:02d}") for n in range(30)]
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
            "programas.api.views_emergencia.servicio_kits.recibir_entrega", wraps=servicio_kits.recibir_entrega
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
            (URL_MIS_DISPOSITIVOS, "get"),
            ("/api/emergencia/dispositivos/{dispositivo_id}/entregas/", "get"),
            ("/api/emergencia/entregas/{id}/", "get"),
            ("/api/emergencia/entregas/{id}/recibir/", "post"),
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
            (rutas[URL_MIS_DISPOSITIVOS]["get"], "200", CLAVES_MI_DISPOSITIVO),
            (rutas["/api/emergencia/dispositivos/{dispositivo_id}/entregas/"]["get"], "200", CLAVES_ENTREGA),
            (rutas["/api/emergencia/entregas/{id}/"]["get"], "200", CLAVES_ENTREGA),
            (rutas["/api/emergencia/entregas/{id}/recibir/"]["post"], "200", CLAVES_RECEPCION),
            (rutas["/api/emergencia/entregas/{id}/recibir/"]["post"], "409", CLAVES_ESTADO_CAMBIO),
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
