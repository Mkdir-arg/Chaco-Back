"""Cliente de Base de Personas ("Gran Base") para el dominio Becas.

RENAPER permanece desacoplado en ``legajos.services.consulta_renaper``. Este
cliente usa credenciales propias, cachea el token y consulta solamente por DNI.
"""

import logging
import re
from datetime import datetime

import requests
from django.conf import settings
from django.core.cache import cache

from core.performance.query_observability import instrument_external_call

logger = logging.getLogger(__name__)

TOKEN_CACHE_KEY = "personas_api:token"  # nosec B105


def _texto(value):
    return str(value or "").strip()


def _normalizar_clave(value):
    return re.sub(r"[^a-z0-9]", "", _texto(value).lower())


def _aplanar(value, target=None):
    target = target if target is not None else {}
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                _aplanar(item, target)
            elif item not in (None, ""):
                target.setdefault(_normalizar_clave(key), item)
    elif isinstance(value, list):
        for item in value:
            _aplanar(item, target)
    return target


def _primero(flat, *keys):
    for key in keys:
        value = flat.get(_normalizar_clave(key))
        if value not in (None, ""):
            return value
    return ""


def fecha_iso(valor):
    """Normaliza la fecha de un proveedor a ``AAAA-MM-DD`` (o ``""`` si no se
    puede). Gran Base/RENAPER no garantizan formato: llegó ``15/03/2010`` y
    rompía RN-22 y el alta del ciudadano (revisión Cambio 40)."""
    if hasattr(valor, "isoformat"):
        return valor.isoformat()[:10]
    texto = _texto(valor).split("T")[0].split(" ")[0]
    if not texto:
        return ""
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            continue
    return ""


def normalizar_persona(payload, dni):
    """Tolera variantes de nombres hasta que se cierre el contrato definitivo."""
    data = payload.get("data") if isinstance(payload, dict) else payload
    flat = _aplanar(data)
    return {
        "dni": _texto(_primero(flat, "dni", "documento", "numero_documento", "nro_documento")) or dni,
        "apellido": _texto(_primero(flat, "apellido", "apellidos")),
        "nombre": _texto(_primero(flat, "nombre", "nombres")),
        "fecha_nacimiento": fecha_iso(_primero(flat, "fecha_nacimiento", "fechaNacimiento", "nacimiento")),
        "sexo": _texto(_primero(flat, "sexo", "genero")).upper(),
    }


class PersonasAPIClient:
    def __init__(self):
        self.base_url = _texto(settings.PERSONAS_API_URL).rstrip("/")
        self.client_id = _texto(settings.PERSONAS_API_CLIENT_ID)
        self.client_secret = _texto(settings.PERSONAS_API_CLIENT_SECRET)
        self.entidad_uuid = _texto(settings.PERSONAS_API_ENTIDAD_UUID)
        self.fuente_id = settings.PERSONAS_API_FUENTE_ID
        self.timeout = (settings.PERSONAS_API_CONNECT_TIMEOUT, settings.PERSONAS_API_TIMEOUT)

    def _configurada(self):
        return all((self.base_url, self.client_id, self.client_secret, self.entidad_uuid))

    def _token(self):
        token = cache.get(TOKEN_CACHE_KEY)
        if token:
            return token
        response = instrument_external_call(
            "personas",
            requests.post,
            f"{self.base_url}/aplicaciones/token/",
            json={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "entidad": self.entidad_uuid,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        body = response.json()
        token = (body.get("data") or {}).get("token") if isinstance(body, dict) else None
        if not token:
            raise ValueError("La API de Personas no devolvio un token.")
        # El proveedor informa 24 h; renovamos cinco minutos antes.
        cache.set(TOKEN_CACHE_KEY, token, 23 * 60 * 60 + 55 * 60)
        return token

    def consultar(self, dni, sexo):
        if not self._configurada():
            return {"success": False, "error": "Configuracion de Base de Personas incompleta."}
        try:
            response = instrument_external_call(
                "personas",
                requests.get,
                f"{self.base_url}/personas/consulta/",
                params={"dni": dni, "sexo": sexo, "fuente_id": self.fuente_id},
                headers={"Authorization": f"Bearer {self._token()}"},
                timeout=self.timeout,
            )
            if response.status_code == 401:
                cache.delete(TOKEN_CACHE_KEY)
            if response.status_code == 404:
                return {"success": False, "error": "El DNI no fue encontrado en Base de Personas."}
            response.raise_for_status()
            body = response.json()
            data = body.get("data") if isinstance(body, dict) else None
            codigo = data.get("codigo") if isinstance(data, dict) else None
            mensaje = _texto(data.get("mensaje")) if isinstance(data, dict) else ""
            if codigo == 12 or "NO SE ENCONTRO" in mensaje.upper():
                return {
                    "success": False,
                    "not_found": True,
                    "error": "El DNI no fue encontrado en Base de Personas.",
                }
            return {"success": True, "data": normalizar_persona(body, dni), "datos_api": body}
        except (requests.RequestException, ValueError, TypeError):
            logger.exception("Error al consultar Base de Personas")
            return {"success": False, "error": "No se pudo consultar Base de Personas."}


def consultar_persona(dni, sexo):
    dni = re.sub(r"\D", "", _texto(dni))
    if not dni:
        return {"success": False, "error": "El DNI es requerido."}
    sexo = _texto(sexo).upper()
    if sexo not in ("F", "M"):
        return {"success": False, "error": "El sexo debe ser F o M."}
    return PersonasAPIClient().consultar(dni, sexo)
