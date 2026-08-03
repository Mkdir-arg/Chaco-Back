"""Cliente de compatibilidad SIIS para Becas."""

import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)
TOKEN_CACHE_KEY = "siis_api:access_token"  # nosec B105
PROGRAMAS_CACHE_KEY = "siis_api:programas:activos"
CATALOGO_CACHE_SECONDS = 300


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
            raise ValueError("Configuración SIIS incompleta.")
        response = requests.post(
            f"{self.base_url}/api/v1/auth/token",
            json={"client_id": self.client_id, "client_secret": self.client_secret},
            timeout=self.timeout,
        )
        response.raise_for_status()
        body = response.json()
        token = body.get("access_token")
        if not token:
            raise ValueError("SIIS no devolvió access_token.")
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
            if nombre:
                resultado.append({"id": item_id, "nombre": str(nombre).strip()})
        return resultado

    def listar_programas(self):
        cached = cache.get(PROGRAMAS_CACHE_KEY)
        if cached is not None:
            return cached
        body = self._get("/api/v1/programas?estado=ACTIVO")
        programas = self._normalizar_catalogo(self._items(body, "programas", "results"), ("id", "id_programa"))
        cache.set(PROGRAMAS_CACHE_KEY, programas, CATALOGO_CACHE_SECONDS)
        return programas

    def listar_segmentos(self, id_programa):
        id_programa = int(id_programa)
        key = f"siis_api:programa:{id_programa}:segmentos"
        cached = cache.get(key)
        if cached is not None:
            return cached
        body = self._get(f"/api/v1/programas/{id_programa}/segmentos")
        segmentos = self._normalizar_catalogo(self._items(body, "segmentos", "results"), ("id", "id_segmento"))
        cache.set(key, segmentos, CATALOGO_CACHE_SECONDS)
        return segmentos

    def validar_compatibilidad(self, documento, sexo, id_segmento):
        payload = {"documento": str(documento), "sexo": str(sexo).upper(), "id_segmento": int(id_segmento)}
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
            if response.status_code == 200 and body.get("resultado") == "OK":
                return {"success": True, "compatible": True, "data": body}
            if response.status_code == 400 and body.get("resultado") == "RECHAZADO":
                return {"success": True, "compatible": False, "data": body}
            if response.status_code >= 400:
                return {
                    "success": False,
                    "error": body.get("error") or body.get("detail") or f"SIIS respondió HTTP {response.status_code}.",
                    "data": body,
                }
            return {"success": False, "error": "SIIS devolvió una respuesta no reconocida.", "data": body}
        except (requests.RequestException, TypeError, ValueError):
            logger.exception("Error técnico al validar compatibilidad en SIIS")
            return {"success": False, "error": "No se pudo conectar con SIIS.", "data": {}}


def validar_compatibilidad(documento, sexo, id_segmento):
    return SiisAPIClient().validar_compatibilidad(documento, sexo, id_segmento)


def listar_programas():
    return SiisAPIClient().listar_programas()


def listar_segmentos(id_programa):
    return SiisAPIClient().listar_segmentos(id_programa)
