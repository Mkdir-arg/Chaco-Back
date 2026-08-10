"""Cliente de compatibilidad SIIS para Becas."""

import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)
TOKEN_CACHE_KEY = "siis_api:access_token"  # nosec B105
PROGRAMAS_CACHE_KEY = "siis_api:programas:activos"
PROGRAMAS_TODOS_CACHE_KEY = "siis_api:programas:todos"
CATALOGO_CACHE_SECONDS = 300

ESTADO_ACTIVO = "ACTIVO"
ESTADO_INACTIVO = "INACTIVO"
ESTADO_DESCONOCIDO = "DESCONOCIDO"

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


class SiisCatalogError(Exception):
    """Error seguro para mostrar al usuario al cargar catálogos de SIIS."""


class _SiisConfigurationError(Exception):
    pass


class SiisAPIClient:
    def __init__(self):
        self.base_url = str(settings.SIIS_API_URL or "").strip().rstrip("/")
        self.client_id = str(settings.SIIS_API_CLIENT_ID or "").strip()
        self.client_secret = str(settings.SIIS_API_CLIENT_SECRET or "").strip()
        self.timeout = (settings.SIIS_API_CONNECT_TIMEOUT, settings.SIIS_API_TIMEOUT)

    def _token(self):
        token = cache.get(TOKEN_CACHE_KEY)
        if token:
            return token
        if not all((self.base_url, self.client_id, self.client_secret)):
            raise _SiisConfigurationError("Configuración SIIS incompleta.")
        response = requests.post(
            f"{self.base_url}/api/v1/auth/token",
            json={"client_id": self.client_id, "client_secret": self.client_secret},
            timeout=self.timeout,
        )
        response.raise_for_status()
        body = response.json()
        token = body.get("access_token")
        if not token:
            raise _SiisConfigurationError("SIIS no devolvió access_token.")
        ttl = max(int(body.get("expires_in") or 3600) - 60, 60)
        cache.set(TOKEN_CACHE_KEY, token, ttl)
        return token

    def _get(self, path):
        response = requests.get(
            f"{self.base_url}{path}",
            headers={"Authorization": f"Bearer {self._token()}"},
            timeout=self.timeout,
        )
        if response.status_code == 401:
            cache.delete(TOKEN_CACHE_KEY)
        response.raise_for_status()
        return response.json()

    def _cargar_catalogo(self, path, mensaje_no_encontrado):
        try:
            return self._get(path)
        except _SiisConfigurationError as exc:
            logger.exception("Configuración incompleta al consultar un catálogo de SIIS")
            raise SiisCatalogError("La integración con SIIS no está configurada. Contactá a Infraestructura.") from exc
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
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/validaciones/compatibilidad",
                json=payload,
                headers={"Authorization": f"Bearer {self._token()}"},
                timeout=self.timeout,
            )
            try:
                body = response.json()
            except ValueError:
                body = {}
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
        except (requests.RequestException, TypeError, ValueError, _SiisConfigurationError):
            logger.exception("Error técnico al validar compatibilidad en SIIS")
            return {"success": False, "error": "No se pudo conectar con SIIS.", "data": {}}


def validar_compatibilidad(dni, id_programa, fecha_nacimiento=None):
    return SiisAPIClient().validar_compatibilidad(dni, id_programa, fecha_nacimiento)


def listar_programas():
    return SiisAPIClient().listar_programas()


def listar_programas_todos():
    return SiisAPIClient().listar_programas_todos()


def motivos_de_rechazo(validaciones):
    """Banderas incumplidas del mapa ``validaciones``, como ``[(bandera, texto)]``.

    SIIS informa el detalle por bandera y no un motivo redactado, así que el
    texto para el operador se arma acá. Las banderas que no rechazan (``VIGENTE``,
    ``SIN_INCOMPATIBILIDAD``, ``NUEVO_SOLICITANTE``…) simplemente no aparecen.
    """
    if not isinstance(validaciones, dict):
        return []
    return [(bandera, MOTIVOS_RECHAZO[valor]) for bandera, valor in validaciones.items() if valor in MOTIVOS_RECHAZO]
