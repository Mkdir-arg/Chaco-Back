import re

from .consulta_renaper import consultar_datos_renaper


class RenaperLookupError(Exception):
    pass


class CiudadanosService:
    RENAPER_SESSION_KEY = "datos_renaper"
    RENAPER_RAW_SESSION_KEY = "datos_api_renaper"

    @staticmethod
    def extract_dni_from_cuit(cuit):
        cuit_limpio = re.sub(r"[^0-9]", "", cuit or "")
        if len(cuit_limpio) != 11:
            return None
        dni = cuit_limpio[2:10]
        return dni if len(dni) == 8 else None

    @staticmethod
    def consultar_renaper(dni, sexo):
        return consultar_datos_renaper(dni, sexo)

    @classmethod
    def store_renaper_data(cls, session, resultado):
        session[cls.RENAPER_SESSION_KEY] = resultado["data"]
        session[cls.RENAPER_RAW_SESSION_KEY] = resultado.get("datos_api", {})

    @classmethod
    def clear_renaper_data(cls, session):
        session.pop(cls.RENAPER_SESSION_KEY, None)
        session.pop(cls.RENAPER_RAW_SESSION_KEY, None)

    @classmethod
    def get_renaper_data(cls, session):
        return session.get(cls.RENAPER_SESSION_KEY, {})

    @classmethod
    def get_renaper_raw_data(cls, session):
        return session.get(cls.RENAPER_RAW_SESSION_KEY, {})

    @staticmethod
    def invalidate_ciudadanos_cache():
        from dashboard.utils import invalidate_dashboard_cache

        invalidate_dashboard_cache()
