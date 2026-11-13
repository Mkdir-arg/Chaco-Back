"""Lo que comparten los tests de la API de campo de Emergencia: el contrato y las bases.

Sin tests propios. Las constantes ``CLAVES_*`` son **el contrato** de lo que lee la app
(`Chaco-mobile`), documentado en ``docs/internal/contrato-app-emergencia.md``: agregar una clave
es seguro; renombrarla o sacarla es un release coordinado de la app, y este archivo se toca en el
mismo diff. Las usan ``test_emergencia_api_contrato`` (base, login, perfil y el esquema), ``…_m1``,
``…_kits`` y los ``…_m2*`` (llegada de familias).

* `BaseApiEmergencia` — la mesa de ``BaseCasos`` más la app: tokens, guardia con Equipo y
  media temporal.
* `BaseApiLlegadas` — lo anterior más dos dispositivos con su guardia y una familia de 7 por
  derivar (M2).
"""

import shutil
import tempfile
import uuid

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core import rbac
from core.tests.test_superficie_publica import rutas_concretas
from programas.api.views_emergencia import (
    MENSAJE_SIN_ADMITIR,
    MENSAJE_SIN_MODULO,
    MENSAJE_SIN_RECIBIR_KIT,
    MENSAJE_SIN_RELEVAR,
)
from programas.models import (
    CasoEmergencia,
    Derivacion,
    Estadia,
    IntegranteGrupo,
    MiembroEquipoDispositivo,
    ReservaPlaza,
    TrazaCaso,
)
from programas.services import emergencia as mesa
from programas.services import emergencia_alojar as servicio
from programas.tests.test_emergencia_alojar_base import GUARDIA, ficha_minima
from programas.tests.test_emergencia_base import _permiso
from programas.tests.test_emergencia_casos import JPEG, BaseCasos
from users.models import RolMeta

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
CLAVES_MI_DISPOSITIVO = ["derivaciones_pendientes", "entregas_pendientes", "id", "nombre", "plazas_libres"]
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
# M2 · Llegada de familias (PR 8). Los tests de cada ruta están en los `test_emergencia_api_m2*`.
CLAVES_CASO_RESUMEN = ["estado", "id", "numero", "prioridad", "total_declarado"]
CLAVES_INTEGRANTE = [
    "confirmada_en",
    "egresado_en",
    "estado",
    "ficha_completa",
    "n",
    "parentesco",
    "persona",
    "plaza",
]
CLAVES_PERSONA_DEL_INTEGRANTE = ["dni", "id", "nombre"]
CLAVES_PLAZA_DEL_INTEGRANTE = ["codigo", "id", "nombre"]
CLAVES_INTEGRANTE_DETALLE = sorted([*CLAVES_INTEGRANTE, "ficha", "secciones_incompletas"])
CLAVES_INTEGRANTES = [
    "caso",
    "con_ficha_incompleta",
    "confirmadas",
    "declaradas_al_relevar",
    "integrantes",
    "total_declarado",
]
CLAVES_BUSQUEDA = [
    "alojada_aca",
    "alojada_desde",
    "alojada_en",
    "derivacion",
    "dni",
    "mensaje",
    "plazas_libres",
    "resultado",
]
CLAVES_DERIVACION_LLEGADA = [
    "caso",
    "derivada_en",
    "derivada_por",
    "estado",
    "grupo",
    "id",
    "necesidades",
    "observaciones",
    "plazas_pedidas",
    "responsable",
    "telefono",
    "vence_en",
    "vencida",
]
CLAVES_RESPONSABLE = ["apellido", "dni", "nombre"]
CLAVES_GRUPO_DE_LA_DERIVACION = [
    "adultos_f",
    "adultos_m",
    "dependientes",
    "lactantes",
    "mayores_dependientes",
    "mayores_f",
    "mayores_m",
    "menores_f",
    "menores_m",
]
CLAVES_ACEPTACION = ["caso", "faltantes", "integrantes", "mensaje", "reservadas"]
CLAVES_RECHAZO = ["caso_estado"]
CLAVES_CONFIRMACION = ["confirmadas", "integrante", "reserva_liberada", "total_declarado"]
CLAVES_FICHA_COMPLETADA = ["ficha_completa", "secciones_incompletas"]
CLAVES_INTEGRANTE_AGREGADO = ["integrante", "total_declarado"]
CLAVES_CIERRE_DE_INGRESO = ["estado", "liberadas", "total_alojado"]
CLAVES_MAPA = ["caso", "sectores"]
CLAVES_SECTOR_CON_PLAZAS = ["libres", "plazas", "reservadas_familia", "sector", "total"]
CLAVES_SECTOR_DEL_MAPA = ["id", "nombre", "perfil"]
CLAVES_PLAZA_DEL_MAPA = ["codigo", "detalle", "elegible", "estado", "id", "nombre", "texto", "tono"]
CLAVES_INGRESO_DIRECTO = ["caso", "faltantes", "integrantes", "reservadas"]
CLAVES_AVISO_A_LA_MESA = ["caso"]
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

#: Las de M2 (PR 8) que llevan un id. Sus claves están arriba; los tests de cada ruta, en
#: los ``test_emergencia_api_m2*``.
URLS_DE_LLEGADAS_DEL_BARRIDO = [
    "/api/emergencia/casos/1/alojar/",
    "/api/emergencia/casos/1/cancelar-ingreso/",
    "/api/emergencia/casos/1/cerrar-diferencia/",
    "/api/emergencia/casos/1/integrantes/",
    "/api/emergencia/casos/1/integrantes/1/",
    "/api/emergencia/casos/1/integrantes/1/confirmar/",
    "/api/emergencia/derivaciones/1/aceptar/",
    "/api/emergencia/derivaciones/1/rechazar/",
    "/api/emergencia/dispositivos/1/avisar-mesa/",
    "/api/emergencia/dispositivos/1/buscar/",
    "/api/emergencia/dispositivos/1/ingreso-directo/",
    "/api/emergencia/dispositivos/1/plazas/",
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


SIN_ADMITIR = {"detail": MENSAJE_SIN_ADMITIR, "code": "SIN_MODULO"}
NO_ENCONTRADO = {"detail": "No encontrado."}


def _url(nombre, *args):
    return reverse(f"emergencia_api:{nombre}", args=args)


class BaseApiLlegadas(BaseApiEmergencia):
    """Lo de ``BaseApiEmergencia`` más dos dispositivos con su guardia y una familia de 7 por derivar."""

    def setUp(self):
        super().setUp()
        self.centro = self._dispositivo("Centro Norte", camas=9, localidad="Resistencia")
        self.escuela = self._dispositivo("Escuela 12", camas=5)
        self.guardia_centro = self._guardia("guardia_centro", list(GUARDIA), [self.centro])
        self.guardia_escuela = self._guardia("guardia_escuela", list(GUARDIA), [self.escuela])

    def _derivado(self, dispositivo=None, plazas=None, **datos):
        """Un caso de 7 personas tomado y derivado. Devuelve ``(caso, derivacion)``."""
        datos = {"menores_f": 2, "menores_m": 3, "dni": "30111222", "nombre": "Rosa", "apellido": "Benítez", **datos}
        caso = self._caso_tomado(**datos)
        derivacion = mesa.derivar_caso(
            caso, self.operador, dispositivo or self.centro, plazas or caso.grupo.total_declarado, True
        )
        return CasoEmergencia.objects.get(pk=caso.pk), derivacion

    def _aceptado(self, **kwargs):
        caso, derivacion = self._derivado(**kwargs)
        guardia = self.guardia_escuela if kwargs.get("dispositivo") == self.escuela else self.guardia_centro
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=guardia)
        return CasoEmergencia.objects.get(pk=caso.pk), Derivacion.objects.get(pk=derivacion.pk)

    def _reservas(self, derivacion):
        return list(
            ReservaPlaza.objects.filter(derivacion=derivacion, estado=ReservaPlaza.Estado.VIGENTE).order_by("plaza_id")
        )

    def _confirmar(self, caso, n, dni, plaza=None, uuid_cliente=None, usuario=None, **cambios):
        """La confirmación de la persona ``n`` por la API."""
        if plaza is None:
            plaza = self._reservas(Derivacion.objects.get(clave_vigente=caso.pk))[0].plaza
        cuerpo = {
            "uuid_cliente": str(uuid_cliente or uuid.uuid4()),
            "plaza_id": getattr(plaza, "pk", plaza),
            "ficha": ficha_minima(dni, **cambios),
        }
        return self._como(usuario or self.guardia_centro).post(
            _url("caso-integrante-confirmar", caso.pk, n), cuerpo, format="json"
        )

    def _confirmar_con_el_servicio(self, caso, n, dni):
        plaza = self._reservas(Derivacion.objects.get(clave_vigente=caso.pk))[0].plaza
        return servicio.confirmar_integrante(
            caso=caso, orden=n, usuario=self.guardia_centro, ficha=ficha_minima(dni), plaza=plaza
        )

    def _foto_del_caso(self, caso):
        """Todo lo que una acción podría escribir sobre el caso: para afirmar que no se escribió nada."""
        return (
            CasoEmergencia.objects.filter(pk=caso.pk).values().get(),
            list(Derivacion.objects.filter(caso=caso).order_by("id").values()),
            list(IntegranteGrupo.objects.filter(grupo_id=caso.grupo_id).order_by("orden").values()),
            TrazaCaso.objects.filter(caso=caso).count(),
            ReservaPlaza.objects.count(),
            Estadia.objects.count(),
        )
