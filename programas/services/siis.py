"""Cliente de compatibilidad SIIS para Becas."""

import logging

import requests
from django.conf import settings
from django.core.cache import cache

from core.integraciones import Cortacircuito, sesion_http
from core.performance.query_observability import instrument_external_call

logger = logging.getLogger(__name__)

#: Una sesión por módulo, con su pool (SIIS-09). Las llamadas se hacen contra
#: ``sesion`` y no contra ``requests`` para reutilizar la conexión TLS; es
#: también lo que los tests sustituyen.
sesion = sesion_http()

#: SIIS-09 · Con SIIS caído, cada clic en «Aprobar» o «Rechazar» se comía el
#: timeout de la consulta de compatibilidad antes de hacer nada. Tres fallas de
#: red seguidas la dejan sin consultar por un minuto: el veredicto queda en
#: ERROR —que no frena la aprobación desde el Cambio 81— sin retener el hilo.
#: **El alta no pasa por acá**: lo irreversible se decide caso por caso.
cortacircuito_consultas = Cortacircuito("siis.consulta")

#: Cuánto de una respuesta ilegible se guarda como constancia de lo que SIIS
#: contestó. Un error de un proxy puede ser una página HTML entera.
LARGO_CRUDO = 500
TOKEN_CACHE_KEY = "siis_api:access_token"  # nosec B105
PROGRAMAS_CACHE_KEY = "siis_api:programas:activos"
PROGRAMAS_TODOS_CACHE_KEY = "siis_api:programas:todos"
CATALOGO_CACHE_SECONDS = 300

ESTADO_ACTIVO = "ACTIVO"
ESTADO_INACTIVO = "INACTIVO"
ESTADO_DESCONOCIDO = "DESCONOCIDO"

# Alta de beneficiarios y catálogos maestros (manual M2M v4.2, septiembre 2026).
# Los catálogos cambian casi nunca: se cachean un día.
CATALOGO_CACHE_KEY = "siis_api:catalogo:{}"
CATALOGO_CACHE_LARGO = 24 * 60 * 60
CATALOGOS_MAESTROS = ("provincias", "localidades", "estados-civiles", "tipos-documento", "jurisdicciones")
TAB_INTERMEDIA_PATH = "/api/v1/auth/tab-intermedia"
# SIIS-02 · Qué pasó con el POST, visto desde la única pregunta que importa:
# «¿puede haber quedado un alta del otro lado?». El alta no tiene baja, así que
# un resultado ambiguo **no se reintenta**: se concilia con ECOM (D-S02).
#
#   OK          200/201: el alta está hecha.
#   NO_ENVIADO  el POST no salió o SIIS lo rechazó antes de procesarlo. Reintentable.
#   RECHAZADO   SIIS lo miró y dijo que no. Pide corregir datos, no reintentar.
#   INCIERTO    el POST pudo haber llegado y no sabemos qué pasó después.
RESULTADO_OK = "OK"
RESULTADO_NO_ENVIADO = "NO_ENVIADO"
RESULTADO_RECHAZADO = "RECHAZADO"
RESULTADO_INCIERTO = "INCIERTO"
CODIGO_INCIERTO = "RESULTADO_INCIERTO"
# El manual contesta 503 con este error cuando su base legacy está ocupada: el
# alta no se llegó a escribir, así que es el único 5xx que se reintenta (D-S02).
ERROR_BD_LEGACY = "ERROR_BD_LEGACY"
# Estados HTTP que no dicen nada sobre si el alta se procesó.
ESTADOS_AMBIGUOS = (408, 429)

# Campos informativos del programa que conservamos del contrato de ECOM. Se
# congelan en el segmento al vincularlo y son los que muestra el detalle.
CAMPOS_DETALLE_PROGRAMA = (
    "descripcion",
    "jurisdiccion_id",
    "controla_empleo_publico",
    "controla_horas_docentes",
    "controla_duplicidad_becas",
    "controla_smvm",
    "controla_edad_minima",
    "edad_minima",
)

# Valores del mapa ``validaciones`` que implican rechazo, con su texto para el
# operador. El resto de los valores del contrato son informativos o "sin
# incompatibilidad", así que no necesitan entrada acá.
MOTIVOS_RECHAZO = {
    "PROGRAMA_INACTIVO": "El programa no está vigente en SIIS.",
    "EDAD_INSUFICIENTE": "No alcanza la edad mínima exigida por el programa.",
    "INCOMPATIBLE_PLANTA": "Registra empleo público activo en la administración provincial.",
    "INCOMPATIBLE_EXCEDE_HORAS": "Supera el tope de horas cátedra docentes toleradas.",
    "BENEFICIO_ACTIVO_EXISTENTE": "Ya registra una beca o programa activo incompatible.",
    "SUSPENDIDO_TEMPORAL": "Registra una suspensión vigente en otro beneficio.",
}


MENSAJE_INCIERTO = (
    "SIIS no contestó y el alta pudo haber quedado registrada de su lado: no se reenvía hasta verificarlo."
)

# Errores de urllib3 que significan «la conexión no se abrió»: el POST no salió.
# Se miran por nombre y no por clase para no atarse a la versión de urllib3 que
# traiga requests.
ERRORES_SIN_CONEXION = {"NewConnectionError", "NameResolutionError", "ConnectTimeoutError"}


def crudo(valor, limite=LARGO_CRUDO):
    """Envuelve una respuesta que no es un objeto JSON, sin perderla.

    Antes se reemplazaba por ``{}`` y lo que SIIS había contestado desaparecía:
    quien después miraba la validación registrada no tenía forma de distinguir
    «SIIS no contestó» de «SIIS contestó una página de error del proxy». Queda
    bajo ``_crudo``, con el guion bajo adelante para que no se confunda con un
    campo del contrato, y recortado: un 502 de nginx son varios KB de HTML.
    """
    return {"_crudo": str(valor)[:limite]}


def _fallo(resultado, codigo, mensaje):
    """La forma que tiene un fallo sin respuesta HTTP."""
    return {
        "success": False,
        "resultado": resultado,
        "codigo": codigo,
        "reintentable": resultado == RESULTADO_NO_ENVIADO,
        "error": mensaje,
        "detalles": {},
        "data": {},
    }


def _no_llego_a_conectar(exc, visitados=None):
    """¿La conexión ni siquiera se abrió?

    ``requests`` envuelve el error de urllib3 (``ConnectionError(MaxRetryError(…,
    reason=NewConnectionError(…)))``), así que hay que recorrer la cadena: los
    argumentos, la causa, el contexto y el ``reason`` de urllib3.
    """
    visitados = visitados if visitados is not None else set()
    if exc is None or id(exc) in visitados:
        return False
    visitados.add(id(exc))
    if type(exc).__name__ in ERRORES_SIN_CONEXION:
        return True
    candidatos = [getattr(exc, "reason", None), getattr(exc, "__cause__", None), getattr(exc, "__context__", None)]
    candidatos.extend(arg for arg in getattr(exc, "args", ()) if isinstance(arg, BaseException))
    return any(_no_llego_a_conectar(candidato, visitados) for candidato in candidatos)


class SiisCatalogError(Exception):
    """Error seguro para mostrar al usuario al cargar catálogos de SIIS."""


class CatalogoSinCopiaLocal(SiisCatalogError):
    """No hay copia local del catálogo todavía: nadie la bajó.

    Es lo contrario de «SIIS no respondió»: no se tocó la red. Tiene su propia
    clase porque el arreglo también es otro —correr el comando o esperar al
    CronJob— y el mensaje que ve el coordinador no puede decirle que falló un
    servicio externo que nadie consultó.
    """


class _SiisConfigurationError(Exception):
    """No se pudo conseguir el token, y no fue por la red.

    Son dos cosas distintas que terminaban logueadas con el mismo texto —
    «Configuración SIIS incompleta»— y mandan a mirar lugares opuestos:

    * ``falta_configuracion=True``: la URL o las credenciales están vacías. Lo
      arregla una variable de entorno y el cliente corta **antes** de abrir la
      conexión.
    * ``falta_configuracion=False``: SIIS contestó, pero lo que contestó no
      sirve como token (un cuerpo que no es objeto, o sin ``access_token``).
      Las variables están bien; lo que falla es del otro lado.

    Lo que **no** cambia según el caso es el cortacircuito: tampoco cuenta como
    falla cuando SIIS contesta basura, porque contestar basura es contestar
    rápido y no hay espera que ahorrar (:class:`SiisMalConfiguradoTests`).
    """

    def __init__(self, mensaje, falta_configuracion=True):
        super().__init__(mensaje)
        self.falta_configuracion = falta_configuracion


class SiisAPIClient:
    def __init__(self):
        self.base_url = str(settings.SIIS_API_URL or "").strip().rstrip("/")
        self.client_id = str(settings.SIIS_API_CLIENT_ID or "").strip()
        self.client_secret = str(settings.SIIS_API_CLIENT_SECRET or "").strip()
        # SIIS-09 · Tres timeouts, no uno. ``timeout`` sigue siendo el del alta
        # porque es el que miran ``diagnosticar_siis`` y el cálculo del latido.
        self.timeout = (settings.SIIS_API_CONNECT_TIMEOUT, settings.SIIS_API_TIMEOUT)
        self.timeout_token = (settings.SIIS_API_CONNECT_TIMEOUT, settings.SIIS_API_TIMEOUT_TOKEN)
        self.timeout_consulta = (settings.SIIS_API_CONNECT_TIMEOUT, settings.SIIS_API_TIMEOUT_CONSULTA)

    def _token(self):
        token = cache.get(TOKEN_CACHE_KEY)
        if token:
            return token
        if not all((self.base_url, self.client_id, self.client_secret)):
            raise _SiisConfigurationError("Configuración SIIS incompleta.")
        response = instrument_external_call(
            "siis",
            sesion.post,
            f"{self.base_url}/api/v1/auth/token",
            json={"client_id": self.client_id, "client_secret": self.client_secret},
            timeout=self.timeout_token,
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            # Un cuerpo que no es objeto (``[]``, ``"OK"``) no tiene token ni
            # puede tenerlo: es configuración rota, no un error de red (SIIS-11).
            raise _SiisConfigurationError(
                "SIIS devolvió una respuesta de token que no es un objeto.", falta_configuracion=False
            )
        token = body.get("access_token")
        if not token:
            raise _SiisConfigurationError("SIIS no devolvió access_token.", falta_configuracion=False)
        ttl = max(int(body.get("expires_in") or 3600) - 60, 60)
        cache.set(TOKEN_CACHE_KEY, token, ttl)
        return token

    def _get(self, path):
        response = instrument_external_call(
            "siis",
            sesion.get,
            f"{self.base_url}{path}",
            headers={"Authorization": f"Bearer {self._token()}"},
            timeout=self.timeout_consulta,
        )
        if response.status_code == 401:
            cache.delete(TOKEN_CACHE_KEY)
        response.raise_for_status()
        return response.json()

    def _cargar_catalogo(self, path, mensaje_no_encontrado):
        try:
            return self._get(path)
        except _SiisConfigurationError as exc:
            # Mismo corte que en ``validar_compatibilidad``: una variable vacía y
            # un token que SIIS devolvió mal llevan a lugares distintos.
            if exc.falta_configuracion:
                logger.exception("Configuración incompleta al consultar un catálogo de SIIS")
                mensaje = "La integración con SIIS no está configurada. Contactá a Infraestructura."
            else:
                logger.exception("SIIS no devolvió un token usable al consultar un catálogo: %s", exc)
                mensaje = "SIIS no devolvió un token válido. Contactá a Infraestructura."
            raise SiisCatalogError(mensaje) from exc
        except requests.Timeout as exc:
            logger.exception("Timeout al consultar un catálogo de SIIS")
            raise SiisCatalogError("SIIS tardó demasiado en responder. Intentá nuevamente en unos minutos.") from exc
        except requests.ConnectionError as exc:
            logger.exception("Error de conexión al consultar un catálogo de SIIS")
            raise SiisCatalogError(
                "No se pudo conectar con SIIS. Verificá que el servicio esté disponible e intentá nuevamente."
            ) from exc
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            logger.exception("SIIS respondió HTTP %s al consultar un catálogo", status)
            if status in (401, 403):
                mensaje = "SIIS rechazó las credenciales configuradas. Contactá a Infraestructura."
            elif status == 404:
                mensaje = mensaje_no_encontrado
            elif status is not None and status >= 500:
                mensaje = "SIIS no está disponible temporalmente. Intentá nuevamente más tarde."
            else:
                mensaje = "SIIS rechazó la consulta del catálogo. Contactá a Infraestructura."
            raise SiisCatalogError(mensaje) from exc
        except (requests.RequestException, TypeError, ValueError) as exc:
            logger.exception("Respuesta inválida al consultar un catálogo de SIIS")
            raise SiisCatalogError(
                "SIIS devolvió una respuesta que la aplicación no pudo interpretar. Contactá a Infraestructura."
            ) from exc

    @staticmethod
    def _items(body, *keys):
        if isinstance(body, list):
            return body
        if not isinstance(body, dict):
            return []
        containers = (body, body.get("data"))
        for container in containers:
            if isinstance(container, list):
                return container
            if isinstance(container, dict):
                for key in keys:
                    if isinstance(container.get(key), list):
                        return container[key]
        return []

    @staticmethod
    def _normalizar_catalogo(items, id_keys):
        resultado = []
        for item in items:
            if not isinstance(item, dict):
                continue
            item_id = next((item.get(key) for key in id_keys if item.get(key) is not None), None)
            nombre = item.get("nombre") or item.get("descripcion") or item.get("denominacion")
            try:
                item_id = int(item_id)
            except (TypeError, ValueError):
                continue
            if not nombre:
                continue
            # Si ECOM dejara de informar ``estado``, asumirlo ACTIVO: preferimos
            # un catálogo completo antes que vaciar el select de golpe.
            programa = {
                "id": item_id,
                "nombre": str(nombre).strip(),
                "estado": str(item.get("estado") or ESTADO_ACTIVO).strip().upper(),
            }
            programa.update({campo: item[campo] for campo in CAMPOS_DETALLE_PROGRAMA if campo in item})
            resultado.append(programa)
        return resultado

    def _catalogo_programas(self, estado):
        body = self._cargar_catalogo(
            f"/api/v1/programas?estado={estado}",
            "SIIS no encontró el catálogo de programas. Es posible que ECOM haya cambiado la integración.",
        )
        return self._normalizar_catalogo(self._items(body, "programas", "results"), ("id", "id_programa"))

    def listar_programas(self):
        """Catálogo para elegir programa: solo los ACTIVOS.

        El filtro se le pide a SIIS *y* se vuelve a aplicar acá. Si el servicio
        ignorara el parámetro o cambiara su default, un programa dado de baja no
        tiene que llegar igual al select.
        """
        cached = cache.get(PROGRAMAS_CACHE_KEY)
        if cached is not None:
            return cached
        programas = [p for p in self._catalogo_programas(ESTADO_ACTIVO) if p["estado"] == ESTADO_ACTIVO]
        # Una lista vacía no se cachea (SIIS-06): es siempre una anomalía —SIIS no
        # tiene cero programas— y guardarla multiplica por los cinco minutos de la
        # caché el rato que el select queda vacío o que todo se ve dado de baja.
        if programas:
            cache.set(PROGRAMAS_CACHE_KEY, programas, CATALOGO_CACHE_SECONDS)
        return programas

    def listar_programas_todos(self):
        """Catálogo completo (ACTIVO + INACTIVO) para sincronizar estados.

        ``estado=ACTIVO`` no sirve para detectar una baja: el programa
        simplemente desaparece de la respuesta y no se distingue de una lista
        incompleta por un error del servicio.
        """
        cached = cache.get(PROGRAMAS_TODOS_CACHE_KEY)
        if cached is not None:
            return cached
        programas = self._catalogo_programas("TODOS")
        if programas:  # ver ``listar_programas``: el vacío no se cachea (SIIS-06)
            cache.set(PROGRAMAS_TODOS_CACHE_KEY, programas, CATALOGO_CACHE_SECONDS)
        return programas

    def validar_compatibilidad(self, dni, id_programa, fecha_nacimiento=None):
        """Prevalida elegibilidad de una persona contra un programa del SIIS.

        SIIS resuelve el veredicto **siempre con HTTP 200**: ``resultado`` viene
        en ``OK``/``RECHAZADO`` y ``apto`` lo acompaña. Un 4xx es un error de
        integración (payload inválido, credenciales), no un rechazo de negocio.
        """
        payload = {"dni": str(dni), "id_programa": int(id_programa)}
        if fecha_nacimiento:
            payload["fecha_nacimiento"] = str(fecha_nacimiento)
        if cortacircuito_consultas.abierto():
            # SIIS-09: ya falló tres veces seguidas. Esperar el timeout otra vez
            # no cambia el resultado y sí retiene el hilo del request.
            return {"success": False, "error": "No se pudo conectar con SIIS.", "data": {}, "cortado": True}
        try:
            response = instrument_external_call(
                "siis",
                sesion.post,
                f"{self.base_url}/api/v1/validaciones/compatibilidad",
                json=payload,
                headers={"Authorization": f"Bearer {self._token()}"},
                timeout=self.timeout_consulta,
            )
            try:
                body = response.json()
            except ValueError:
                body = {}
            if not isinstance(body, dict):
                # El cuerpo puede ser una lista o un string: sin esto, el primer
                # ``body.get`` era un ``AttributeError`` sin capturar, que en el
                # masivo cortaba la corrida y al rechazar un caso daba 500 (SIIS-11).
                # Lo que vino queda en ``_crudo``: es la constancia de qué contestó.
                body = crudo(body)
            cortacircuito_consultas.registrar_exito()
            if response.status_code == 401:
                cache.delete(TOKEN_CACHE_KEY)
            if response.status_code == 200 and body.get("resultado") in ("OK", "RECHAZADO"):
                return {"success": True, "compatible": bool(body.get("apto")), "data": body}
            if response.status_code >= 400:
                return {
                    "success": False,
                    "error": body.get("error") or body.get("detail") or f"SIIS respondió HTTP {response.status_code}.",
                    "data": body,
                }
            return {"success": False, "error": "SIIS devolvió una respuesta no reconocida.", "data": body}
        except _SiisConfigurationError as exc:
            # No se consiguió token y no fue por la red. Ninguno de los dos casos
            # cuenta como falla del cortacircuito: uno corta antes de abrir la
            # conexión y el otro contesta rápido, así que no hay espera que
            # ahorrar, y contarlos haría que el log dijera «SIIS falló 3 veces
            # seguidas» —que manda a mirar a ECOM—. Lo que sí cambia es a quién
            # manda a mirar el mensaje: una variable de entorno vacía la arregla
            # Infraestructura; un token que no sirve, SIIS.
            if exc.falta_configuracion:
                logger.exception("Configuración SIIS incompleta al validar compatibilidad")
            else:
                logger.exception("SIIS no devolvió un token usable al validar compatibilidad: %s", exc)
            return {"success": False, "error": "No se pudo conectar con SIIS.", "data": {}}
        except (requests.RequestException, TypeError, ValueError):
            logger.exception("Error técnico al validar compatibilidad en SIIS")
            cortacircuito_consultas.registrar_falla()
            return {"success": False, "error": "No se pudo conectar con SIIS.", "data": {}}

    # ------------------------------------------------------------------
    # Alta de beneficiarios (tabla intermedia) y catálogos maestros
    # ------------------------------------------------------------------
    @staticmethod
    def _normalizar_items(items):
        """Ítems con ``id`` entero y ``nombre``; conserva el resto de las claves
        (las localidades pueden traer su provincia, las funciones su programa)."""
        resultado = []
        for item in items:
            if not isinstance(item, dict):
                continue
            nombre = item.get("nombre") or item.get("descripcion") or item.get("denominacion")
            try:
                item_id = int(item.get("id"))
            except (TypeError, ValueError):
                continue
            if not nombre:
                continue
            normalizado = dict(item)
            normalizado["id"] = item_id
            normalizado["nombre"] = str(nombre).strip()
            resultado.append(normalizado)
        return resultado

    def catalogo(self, nombre):
        """Catálogo maestro (sección 2 del manual), cacheado un día.

        **Sale a la red**: no se llama desde un request de backoffice (ver
        :func:`catalogo_local`). Cada lectura exitosa deja además la copia en la
        base, que es de donde lee el request.
        """
        if nombre not in CATALOGOS_MAESTROS:
            raise ValueError(f"Catálogo SIIS desconocido: {nombre}")
        clave = CATALOGO_CACHE_KEY.format(nombre)
        cached = cache.get(clave)
        if cached is not None:
            return cached
        body = self._cargar_catalogo(
            f"/api/v1/auth/catalogos/{nombre}",
            f"SIIS no encontró el catálogo de {nombre.replace('-', ' ')}.",
        )
        items = self._normalizar_items(self._items(body, nombre, "items", "results"))
        cache.set(clave, items, CATALOGO_CACHE_LARGO)
        guardar_catalogo_local(nombre, items)
        return items

    def funciones_programa(self, id_programa):
        """Funciones/niveles de un programa: el ``id`` viaja en ``id_fun_x_plan``."""
        clave = CATALOGO_CACHE_KEY.format(f"funciones:{int(id_programa)}")
        cached = cache.get(clave)
        if cached is not None:
            return cached
        body = self._cargar_catalogo(
            f"/api/v1/auth/catalogos/funciones?id_programa={int(id_programa)}",
            "SIIS no encontró las funciones del programa.",
        )
        items = self._normalizar_items(self._items(body, "funciones", "items", "results"))
        cache.set(clave, items, CATALOGO_CACHE_LARGO)
        return items

    @staticmethod
    def _siis_id_de(body):
        """``ids_generados[0]`` o ``registros[0].id``: el manual muestra las dos."""
        if not isinstance(body, dict):
            return None
        ids = body.get("ids_generados")
        if isinstance(ids, list) and ids:
            try:
                return int(ids[0])
            except (TypeError, ValueError):
                pass
        registros = body.get("registros")
        if isinstance(registros, list) and registros and isinstance(registros[0], dict):
            try:
                return int(registros[0].get("id"))
            except (TypeError, ValueError):
                pass
        return None

    def cargar_beneficiario(self, payload):
        """Alta individual en la tabla intermedia (Modalidad A del manual).

        Nunca lanza. El resultado trae ``resultado`` (SIIS-02), que es lo que
        decide qué se puede volver a intentar:

        * ``OK`` — 200/201.
        * ``NO_ENVIADO`` — el POST no salió (DNS, conexión rechazada, timeout de
          conexión, token), o SIIS lo rechazó sin procesarlo (401, 503
          ``ERROR_BD_LEGACY``). Se reintenta solo.
        * ``RECHAZADO`` — SIIS lo miró y dijo que no (400 y el resto de los 4xx).
          Pide corregir datos.
        * ``INCIERTO`` — el POST pudo haber llegado (``ReadTimeout``, conexión
          cortada a mitad, 408/429, 500/502/504). **No se reintenta**: el alta no
          tiene baja. Se concilia con ECOM (``conciliar_envios_siis``).
        """
        resultado = self._intentar_alta(payload)
        if resultado.get("codigo") == "UNAUTHORIZED":
            # El token pudo haber vencido antes de lo que dijo ``expires_in``. El
            # 401 garantiza que el alta no se procesó, así que reintentar una vez
            # con un token nuevo no puede duplicar nada.
            cache.delete(TOKEN_CACHE_KEY)
            resultado = self._intentar_alta(payload)
        return resultado

    def _intentar_alta(self, payload):
        try:
            token = self._token()
        except (requests.RequestException, TypeError, ValueError, _SiisConfigurationError) as exc:
            # Sin ``logger.exception``: el traceback de requests arrastra el payload
            # con datos personales. El tipo de error alcanza para diagnosticar.
            logger.error("No se pudo obtener el token para el alta en SIIS (%s)", type(exc).__name__)
            return _fallo(RESULTADO_NO_ENVIADO, "ERROR_TECNICO", "No se pudo autenticar contra SIIS.")
        try:
            response = instrument_external_call(
                "siis",
                sesion.post,
                f"{self.base_url}{TAB_INTERMEDIA_PATH}",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
        except (TypeError, ValueError) as exc:
            # El payload no se pudo serializar: no salió nada a la red.
            logger.error("Error técnico al cargar un beneficiario en SIIS (%s)", type(exc).__name__)
            return _fallo(RESULTADO_NO_ENVIADO, "ERROR_TECNICO", "No se pudo armar la llamada a SIIS.")
        except requests.ConnectTimeout as exc:
            # Hereda de ConnectionError: su ``except`` va primero. La conexión no
            # llegó a abrirse, así que el alta no salió.
            logger.error("No se pudo conectar con SIIS (%s)", type(exc).__name__)
            return _fallo(RESULTADO_NO_ENVIADO, "ERROR_TECNICO", "No se pudo conectar con SIIS.")
        except requests.ConnectionError as exc:
            if _no_llego_a_conectar(exc):
                logger.error("No se pudo conectar con SIIS (%s)", type(exc).__name__)
                return _fallo(RESULTADO_NO_ENVIADO, "ERROR_TECNICO", "No se pudo conectar con SIIS.")
            # La conexión se abrió y se cortó: el POST pudo haber llegado.
            logger.error("Conexión con SIIS cortada durante el alta (%s)", type(exc).__name__)
            return _fallo(RESULTADO_INCIERTO, CODIGO_INCIERTO, MENSAJE_INCIERTO)
        except requests.RequestException as exc:
            # ReadTimeout, ChunkedEncodingError y cualquier otra: el servidor ya
            # tenía el pedido.
            logger.error("SIIS no completó la respuesta del alta (%s)", type(exc).__name__)
            return _fallo(RESULTADO_INCIERTO, CODIGO_INCIERTO, MENSAJE_INCIERTO)

        try:
            body = response.json()
        except ValueError:
            body = {}
        if not isinstance(body, dict):
            body = {"respuesta": body}
        if response.status_code == 401:
            cache.delete(TOKEN_CACHE_KEY)
        if response.status_code in (200, 201):
            return {
                "success": True,
                "resultado": RESULTADO_OK,
                "siis_id": self._siis_id_de(body),
                "codigo": "",
                "reintentable": False,
                "detalles": {},
                "data": body,
            }
        codigo = str(body.get("error") or "").strip().upper()
        resultado = self._resultado_http(response.status_code, codigo)
        if not codigo:
            codigo = {400: "DATOS_INVALIDOS", 401: "UNAUTHORIZED"}.get(response.status_code, "")
        if resultado == RESULTADO_INCIERTO:
            # El código que mandó SIIS queda en ``data``; el de la fila dice que
            # no sabemos qué pasó, que es lo que decide si se puede reintentar.
            codigo = CODIGO_INCIERTO
        elif not codigo:
            # 4xx sin código: no es un dato del beneficiario, es cómo está
            # configurada la integración (ruta, permisos, versión del contrato).
            codigo = "CONFIGURACION" if response.status_code < 500 else "ERROR_INTERNO"
        detalles = body.get("detalles") if isinstance(body.get("detalles"), dict) else {}
        return {
            "success": False,
            "resultado": resultado,
            "codigo": codigo,
            "reintentable": resultado == RESULTADO_NO_ENVIADO,
            "error": body.get("mensaje") or body.get("detail") or f"SIIS respondió HTTP {response.status_code}.",
            "detalles": detalles,
            "data": body,
        }

    @staticmethod
    def _resultado_http(status, codigo):
        if status == 401:
            return RESULTADO_NO_ENVIADO
        if status in ESTADOS_AMBIGUOS:
            return RESULTADO_INCIERTO
        if status >= 500:
            # D-S02: el 503 del legacy ocupado es el único 5xx que garantiza que
            # el alta no se escribió.
            return RESULTADO_NO_ENVIADO if codigo == ERROR_BD_LEGACY else RESULTADO_INCIERTO
        return RESULTADO_RECHAZADO


def validar_compatibilidad(dni, id_programa, fecha_nacimiento=None):
    return SiisAPIClient().validar_compatibilidad(dni, id_programa, fecha_nacimiento)


def listar_programas():
    return SiisAPIClient().listar_programas()


def listar_programas_todos():
    return SiisAPIClient().listar_programas_todos()


def cargar_beneficiario(payload):
    return SiisAPIClient().cargar_beneficiario(payload)


def catalogo(nombre):
    return SiisAPIClient().catalogo(nombre)


def funciones_programa(id_programa):
    return SiisAPIClient().funciones_programa(id_programa)


# ---------------------------------------------------------------------------
# Copia local de los catálogos maestros (SIIS-09, ronda 2)
# ---------------------------------------------------------------------------
def guardar_catalogo_local(nombre, items):
    """Deja en la base lo último que SIIS devolvió para ``nombre``.

    Un catálogo vacío **no se guarda**: es el mismo criterio de SIIS-06, donde
    una lista vacía resultó ser un error del servicio y no una baja real, y
    pisar la copia buena con ella dejaría a todos los casos sin poder resolver
    su localidad hasta la noche siguiente.
    """
    from programas.models import CatalogoSiisLocal

    if not items:
        return False
    CatalogoSiisLocal.objects.update_or_create(nombre=nombre, defaults={"items": list(items)})
    return True


def catalogo_local(nombre):
    """El catálogo maestro **sin salir a la red**: caché, y si no, la copia local.

    Es lo que usa el backoffice dentro de un request. La cadena de «Aprobar» ya
    ocupa los 55 s de presupuesto que deja nginx (``core.integraciones``), así
    que un GET de catálogo ahí no entra en ninguna cuenta: tiene que estar
    resuelto de antes. Lo deja resuelto cualquier corrida del masivo o de los
    comandos, y el CronJob de ``sincronizar_programas_siis`` todas las noches.

    Si no hay copia, lanza :class:`SiisCatalogError` diciendo cómo conseguirla.
    El alta queda como ERROR reintentable (nunca como un dato que falta): no es
    un problema del caso.
    """
    from programas.models import CatalogoSiisLocal

    if nombre not in CATALOGOS_MAESTROS:
        raise ValueError(f"Catálogo SIIS desconocido: {nombre}")
    cached = cache.get(CATALOGO_CACHE_KEY.format(nombre))
    if cached:
        return cached
    items = CatalogoSiisLocal.objects.filter(nombre=nombre).values_list("items", flat=True).first()
    if not items:
        raise CatalogoSinCopiaLocal(
            f"Todavía no hay una copia local del catálogo de {nombre.replace('-', ' ')} de SIIS. "
            "Se baja sola con la próxima corrida del proceso masivo o del CronJob nocturno "
            "(`sincronizar_programas_siis`); si corre, reintentá el envío después."
        )
    cache.set(CATALOGO_CACHE_KEY.format(nombre), items, CATALOGO_CACHE_LARGO)
    return items


def refrescar_catalogos_locales():
    """Vuelve a bajar los catálogos maestros y actualiza la copia local.

    La corre el CronJob nocturno. Devuelve ``(actualizados, fallados)``: no
    levanta nada, porque es un paso secundario de un comando que tiene otro
    trabajo principal y un catálogo que hoy no se pudo bajar no invalida la copia
    que ya había.
    """
    cliente = SiisAPIClient()
    actualizados, fallados = [], []
    for nombre in CATALOGOS_MAESTROS:
        cache.delete(CATALOGO_CACHE_KEY.format(nombre))
        try:
            items = cliente.catalogo(nombre)
        except SiisCatalogError as exc:
            fallados.append((nombre, str(exc)))
            continue
        if items:
            actualizados.append((nombre, len(items)))
        else:
            fallados.append((nombre, "SIIS devolvió un catálogo vacío."))
    return actualizados, fallados


def motivos_de_rechazo(validaciones):
    """Banderas incumplidas del mapa ``validaciones``, como ``[(bandera, texto)]``.

    SIIS informa el detalle por bandera y no un motivo redactado, así que el
    texto para el operador se arma acá. Las banderas que no rechazan (``VIGENTE``,
    ``SIN_INCOMPATIBILIDAD``, ``NUEVO_SOLICITANTE``…) simplemente no aparecen.
    """
    if not isinstance(validaciones, dict):
        return []
    return [(bandera, MOTIVOS_RECHAZO[valor]) for bandera, valor in validaciones.items() if valor in MOTIVOS_RECHAZO]
