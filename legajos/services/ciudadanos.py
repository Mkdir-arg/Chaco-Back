import re

from core.dni import dni_valido, normalizar_dni

from ..models import Ciudadano
from .consulta_renaper import consultar_datos_renaper


class RenaperLookupError(Exception):
    pass


class CiudadanosService:
    RENAPER_SESSION_KEY = "datos_renaper"
    RENAPER_RAW_SESSION_KEY = "datos_api_renaper"
    #: DNI cuya consulta a RENAPER volvió «fallecido» (D-C08).
    RENAPER_FALLECIDO_SESSION_KEY = "renaper_fallecido_dni"

    @staticmethod
    def extract_dni_from_cuit(cuit):
        """Los 8 dígitos del medio de un CUIT, si lo que sale es un DNI válido.

        RED-48: el largo lo decide `padron.dni_valido`, la única regla del repo, y
        no un `== 8` escrito acá. El DNI de 7 dígitos viaja en el CUIT con un cero
        adelante (`20-01234567-3`), así que se le sacan los ceros de la izquierda
        antes de medir: si no, el legajo nacía con un DNI que no cruza con el de
        Becas, que normaliza.
        """
        cuit_limpio = re.sub(r"[^0-9]", "", cuit or "")
        if len(cuit_limpio) != 11:
            return None
        dni = cuit_limpio[2:10].lstrip("0")
        return dni if dni_valido(dni) else None

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

    @classmethod
    def marcar_fallecido_en_renaper(cls, session, dni):
        """D-C08: deja anotado que la consulta de ``dni`` volvió «fallecido».

        La pantalla de error ofrece seguir por la carga manual. Hasta acá ese
        legajo nacía sin procedencia, indistinguible de uno tipeado a mano, y la
        única persona que sabía lo que RENAPER había contestado era la que estaba
        mirando la pantalla.
        """
        session[cls.RENAPER_FALLECIDO_SESSION_KEY] = normalizar_dni(dni)

    @classmethod
    def consumir_fallecido_en_renaper(cls, session, dni):
        """¿El alta manual de ``dni`` viene de un «fallecido»? Lo saca de la sesión.

        Se consume para que la marca no se le pegue al alta siguiente.
        """
        marcado = session.pop(cls.RENAPER_FALLECIDO_SESSION_KEY, None)
        return bool(marcado) and marcado == normalizar_dni(dni)

    @staticmethod
    def existe_con_dni(dni):
        """¿Hay ya un ciudadano con ese DNI, escrito como esté?

        G1c-08: `12.345.678` y `12345678` son la misma persona. La columna guarda
        lo que se cargó, y antes de este cambio se cargaba sin normalizar, así que
        el chequeo de duplicado tiene que mirar las dos formas. El `__contains`
        sobre los dígitos no alcanza —`1234567` está adentro de `12345678`—: se
        comparan los dígitos de los candidatos en Python, que son pocos.
        """
        dni = normalizar_dni(dni)
        if not dni:
            return False
        if Ciudadano.objects.filter(dni=dni).exists():
            return True
        # Solo las fichas cargadas con separadores pueden empatar normalizadas, y
        # todas contienen el DNI como subcadena de sus dígitos.
        candidatos = Ciudadano.objects.exclude(dni=dni).filter(dni__regex=r"[^0-9]").values_list("dni", flat=True)
        return any(normalizar_dni(candidato) == dni for candidato in candidatos)

    @staticmethod
    def invalidate_ciudadanos_cache():
        from dashboard.utils import invalidate_dashboard_cache

        invalidate_dashboard_cache()
