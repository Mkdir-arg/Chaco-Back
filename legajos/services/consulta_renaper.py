import datetime
import logging
import random
import time
import unicodedata

import requests
import urllib3
from django.conf import settings
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError, RequestException
from urllib3.util.retry import Retry

from core.models import Provincia

# Suprimir warnings de SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

MOJIBAKE_MARKERS = ("Ã", "Â", "â€", "â€“", "â€”", "â€œ", "â€", "â€™")


def _clean_api_base(raw_url):
    if not raw_url:
        return ""
    # No quitar el slash final si la URL ya incluye el endpoint completo
    return str(raw_url).strip().strip('"').strip("'")


def _join_url(base_url, path):
    if not base_url:
        return ""
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _parse_positive_int(raw_value, default):
    try:
        value = int(raw_value)
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default


def _normalizar_sexo(sexo):
    raw = (sexo or "").strip()
    norm = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("utf-8").lower()
    mapping = {
        "m": "M",
        "masculino": "M",
        "hombre": "M",
        "f": "F",
        "femenino": "F",
        "mujer": "F",
        "x": "X",
        "no binario": "X",
        "nobinario": "X",
        "otro": "X",
    }
    return mapping.get(norm, raw.upper() if raw else "")


def _encode_mojibake_bytes(value):
    raw = bytearray()
    for char in value:
        for encoding in ("cp1252", "latin1"):
            try:
                raw.extend(char.encode(encoding))
                break
            except UnicodeError:
                continue
        else:
            return None
    return bytes(raw)


def reparar_texto_mojibake(value):
    if not isinstance(value, str) or not any(marker in value for marker in MOJIBAKE_MARKERS):
        return value

    raw_bytes = _encode_mojibake_bytes(value)
    if raw_bytes:
        try:
            repaired = raw_bytes.decode("utf-8")
        except UnicodeError:
            repaired = None
        if repaired and repaired != value:
            return repaired

    for encoding in ("latin1", "cp1252"):
        try:
            repaired = value.encode(encoding).decode("utf-8")
        except UnicodeError:
            continue
        if repaired and repaired != value:
            return repaired

    return value


def reparar_mojibake(value):
    if isinstance(value, dict):
        return {key: reparar_mojibake(item) for key, item in value.items()}
    if isinstance(value, list):
        return [reparar_mojibake(item) for item in value]
    if isinstance(value, tuple):
        return tuple(reparar_mojibake(item) for item in value)
    return reparar_texto_mojibake(value)


class APIClient:
    def __init__(self):
        self.username = settings.RENAPER_API_USERNAME
        self.password = settings.RENAPER_API_PASSWORD
        self.api_key = (getattr(settings, "RENAPER_API_KEY", "") or "").strip()
        self.api_key_header = (getattr(settings, "RENAPER_API_KEY_HEADER", "X-API-Key") or "X-API-Key").strip()
        self.api_key_prefix = (getattr(settings, "RENAPER_API_KEY_PREFIX", "") or "").strip()
        self.auth_mode = (getattr(settings, "RENAPER_AUTH_MODE", "auto") or "auto").strip().lower()
        self.http_method = (getattr(settings, "RENAPER_HTTP_METHOD", "auto") or "auto").strip().lower()

        self.api_base = _clean_api_base(settings.RENAPER_API_URL)
        self.login_url = self._build_login_url(self.api_base)
        self.consulta_url = self._build_consulta_url(self.api_base)

        connect_timeout = _parse_positive_int(getattr(settings, "RENAPER_CONNECT_TIMEOUT", 10), 10)
        read_timeout = _parse_positive_int(getattr(settings, "RENAPER_TIMEOUT", 20), 20)
        self.timeout = (connect_timeout, read_timeout)

        self.token = None
        self.token_expiration = None
        self.session = requests.Session()
        retry_count = _parse_positive_int(getattr(settings, "RENAPER_RETRIES", 0), 0)
        retries = Retry(
            total=retry_count,
            connect=retry_count,
            read=retry_count,
            backoff_factor=0.8,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "POST"]),
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _build_consulta_url(self, api_base):
        explicit_url = _clean_api_base(getattr(settings, "RENAPER_CONSULTA_URL", ""))
        if explicit_url:
            return explicit_url
        if not api_base:
            return ""
        base = api_base.rstrip("/")
        lower_base = base.lower()
        if lower_base.endswith("/api") and not self._use_api_key_mode():
            return _join_url(base, "consultarenaper")
        return base

    def _build_login_url(self, api_base):
        explicit_url = _clean_api_base(getattr(settings, "RENAPER_LOGIN_URL", ""))
        if explicit_url:
            return explicit_url
        if not api_base:
            return ""
        return _join_url(api_base, "auth/login")

    def _use_api_key_mode(self):
        if self.auth_mode == "api_key":
            return True
        if self.auth_mode == "credentials":
            return False
        return bool(self.api_key)

    def _resolve_http_method(self):
        if self.http_method in ("get", "post"):
            return self.http_method
        # En modo API key para SISOC priorizamos POST.
        return "post" if self._use_api_key_mode() else "get"

    def login(self):
        if self._use_api_key_mode():
            return

        try:
            response = self.session.post(
                self.login_url, json={"username": self.username, "password": self.password}, timeout=self.timeout
            )
        except ConnectionError:
            raise Exception("Error de conexion con el servicio.")
        except RequestException as e:
            raise Exception(f"No se pudo conectar al servicio de login: {str(e)}")

        if response.status_code != 200:
            raise Exception(f"Login fallido: {response.status_code} {response.text}")

        data = response.json()
        self.token = data.get("token")
        self.token_expiration = datetime.datetime.fromisoformat(data["expiration"].replace("Z", "+00:00"))

    def get_token(self):
        if self._use_api_key_mode():
            return None

        if not self.token or datetime.datetime.now(datetime.timezone.utc) >= self.token_expiration:
            self.login()
        return self.token

    def consultar_ciudadano(self, dni, sexo):
        headers = {"Content-Type": "application/json"}
        if self._use_api_key_mode():
            if not self.api_key:
                return {"success": False, "error": "Falta RENAPER_API_KEY para autenticar con API Key."}

            api_key_value = f"{self.api_key_prefix} {self.api_key}".strip()
            headers[self.api_key_header] = api_key_value
        else:
            try:
                token = self.get_token()
            except Exception:
                logger.exception("Error al obtener token RENAPER")
                return {"success": False, "error": "Error interno al obtener token"}
            headers["Authorization"] = f"bearer {token}"

        payload = {"dni": dni, "sexo": _normalizar_sexo(sexo)}
        method = self._resolve_http_method()

        try:
            if method == "post":
                response = self.session.post(
                    self.consulta_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                    verify=False,
                )
            else:
                response = self.session.get(
                    self.consulta_url,
                    headers=headers,
                    params=payload,
                    timeout=self.timeout,
                    verify=False,
                )
        except ConnectionError:
            return {"success": False, "error": "Error de conexion al servicio."}
        except RequestException:
            logger.exception("RequestException al conectar con RENAPER")
            return {
                "success": False,
                "error": "Error interno de conexion al servicio.",
            }

        if response.status_code != 200:
            try:
                error_data = response.json()
            except Exception:
                error_data = response.text[:500] if hasattr(response, "text") else "Sin contenido"
            return {
                "success": False,
                "error": f"Error HTTP {response.status_code}: Error en la respuesta del servicio.",
                "status_code": response.status_code,
                "raw_response": error_data,
            }

        try:
            data = response.json()
        except Exception:
            logger.exception("Respuesta RENAPER no es JSON valido")
            raw_text = response.text[:500] if hasattr(response, "text") else "No response text"
            return {
                "success": False,
                "error": "Error interno: respuesta no es JSON valido.",
                "raw_response": raw_text,
            }

        data = reparar_mojibake(data)

        if data.get("success", False):
            return {"success": True, "data": data["data"]}

        if data.get("isSuccess", False):
            return {"success": True, "data": data.get("result") or {}}

        if "isSuccess" in data:
            return {
                "success": False,
                "error": data.get("message") or "Respuesta de Renaper no indica exito.",
                "raw_response": data,
            }

        if not data.get("success", False):
            return {
                "success": False,
                "error": "Respuesta de Renaper no indica exito.",
                "raw_response": data,
            }

        return {"success": True, "data": data["data"]}


def normalizar(texto):
    if not texto:
        return ""
    texto = texto.lower().replace("_", " ")
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8")
    return texto.strip()


def consultar_datos_renaper(dni, sexo):
    if getattr(settings, "RENAPER_TEST_MODE", False):
        time.sleep(2)

        nombres = [
            "Juan Carlos",
            "Maria Elena",
            "Roberto",
            "Ana Sofia",
            "Carlos Alberto",
            "Lucia",
            "Fernando",
            "Valentina",
        ]
        apellidos = ["Perez", "Gonzalez", "Rodriguez", "Lopez", "Martinez", "Garcia", "Fernandez", "Morales"]
        calles = ["Av. Corrientes", "Av. Santa Fe", "Rivadavia", "San Martin", "Belgrano", "Mitre", "9 de Julio"]
        provincias = ["Buenos Aires", "Cordoba", "Santa Fe", "Mendoza", "Tucuman"]

        nombre_random = random.choice(nombres)
        apellido_random = random.choice(apellidos)
        calle_random = random.choice(calles)
        numero_random = random.randint(100, 9999)
        provincia_random = random.choice(provincias)
        anio_random = random.randint(1970, 2000)
        mes_random = random.randint(1, 12)
        dia_random = random.randint(1, 28)

        return {
            "success": True,
            "data": {
                "dni": dni,
                "nombre": nombre_random,
                "apellido": apellido_random,
                "fecha_nacimiento": f"{anio_random}-{mes_random:02d}-{dia_random:02d}",
                "genero": _normalizar_sexo(sexo),
                "domicilio": f"{calle_random} {numero_random}",
                "provincia": random.randint(1, 24),
            },
            "datos_api": {
                "nombres": nombre_random,
                "apellido": apellido_random,
                "fechaNacimiento": f"{anio_random}-{mes_random:02d}-{dia_random:02d}",
                "provincia": provincia_random,
                "calle": calle_random,
                "numero": str(numero_random),
            },
        }

    api_url = _clean_api_base(getattr(settings, "RENAPER_API_URL", None))
    api_key = (getattr(settings, "RENAPER_API_KEY", None) or "").strip()
    username = getattr(settings, "RENAPER_API_USERNAME", None)
    password = getattr(settings, "RENAPER_API_PASSWORD", None)

    if not api_url:
        return {
            "success": False,
            "error": "Configuracion RENAPER incompleta (URL).",
        }

    if not api_key and not (username and password):
        return {
            "success": False,
            "error": "Configuracion RENAPER incompleta (API key o usuario/password).",
        }

    try:
        client = APIClient()
        response = client.consultar_ciudadano(dni, sexo)

        if not response["success"]:
            return {
                "success": False,
                "error": response.get("error", "Error al consultar RENAPER"),
                "status_code": response.get("status_code"),
                "datos_api": response.get("raw_response"),
            }

        datos = response["data"]

        if datos.get("mensaf") == "FALLECIDO":
            return {"success": False, "fallecido": True}

        equivalencias_provincias = {
            "ciudad de buenos aires": "ciudad autonoma de buenos aires",
            "caba": "ciudad autonoma de buenos aires",
            "ciudad autonoma de buenos aires": "ciudad autonoma de buenos aires",
            "tierra del fuego": "tierra del fuego, antartida e islas del atlantico sur",
            "tierra del fuego antartida e islas del atlantico sur": "tierra del fuego, antartida e islas del atlantico sur",
        }

        provincia_api = datos.get("provincia", "")
        provincia_api_norm = normalizar(provincia_api)
        provincia_api_norm = equivalencias_provincias.get(provincia_api_norm, provincia_api_norm)

        provincia = None
        for prov in Provincia.objects.all():
            nombre_norm = normalizar(prov.nombre)
            if provincia_api_norm == nombre_norm:
                provincia = prov
                break

        genero = _normalizar_sexo(sexo)
        datos_mapeados = {
            "dni": dni,
            "nombre": datos.get("nombres"),
            "apellido": datos.get("apellido"),
            "fecha_nacimiento": datos.get("fechaNacimiento"),
            "genero": genero if genero in ("M", "F", "X") else "X",
            "domicilio": f"{datos.get('calle', '')} {datos.get('numero', '')} {datos.get('piso', '')} {datos.get('departamento', '')}".strip(),
            "provincia": provincia.pk if provincia else None,
        }

        return {"success": True, "data": datos_mapeados, "datos_api": datos}

    except Exception:
        logger.exception("Error inesperado en consultar_datos_renaper")
        return {
            "success": False,
            "error": "Error interno inesperado al consultar Renaper",
        }
