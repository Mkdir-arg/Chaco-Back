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

from core.integraciones import Cortacircuito, sesion_http
from core.performance.query_observability import instrument_external_call

logger = logging.getLogger(__name__)

TOKEN_CACHE_KEY = "personas_api:token"  # nosec B105

#: Una sesión por módulo, con su pool (SIIS-09).
sesion = sesion_http()

#: SIIS-09 · El tope del paso 1 del link público. Con la Gran Base caída, cada
#: inscripción retenía un hilo de daphne hasta agotar el timeout, una por una y
#: sin que el resultado cambiara: la identidad igual terminaba en ``manual``.
#: Tres fallas de red seguidas la dejan sin consultar por un minuto, y en ese
#: minuto el paso 1 resuelve por padrón o manual sin salir a la red.
cortacircuito = Cortacircuito("personas")


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


# ── Elegir el registro de la persona (SIIS-10) ────────────────────────────────

#: Mensajes del paso 1 cuando la respuesta no se puede atribuir a quien se
#: consultó. Los dos caen a ``manual``, que es el camino previsto del Cambio 57.
ERROR_AMBIGUA = "La respuesta de Base de Personas es ambigua."
ERROR_OTRO_DOCUMENTO = "La respuesta de Base de Personas no corresponde al documento consultado."

CLAVES_DNI = ("dni", "documento", "numero_documento", "nro_documento")
CLAVES_SEXO = ("sexo", "genero")


def _plano(registro):
    """Claves de **primer nivel** del registro, normalizadas.

    SIIS-10: antes se aplanaba el árbol entero con ``setdefault``, así que la
    primera aparición a cualquier profundidad ganaba y
    ``domicilio.localidad.nombre`` se leía como el nombre de la persona. Los
    objetos y listas anidados no son datos de la persona: son su domicilio, su
    localidad, su provincia.
    """
    if not isinstance(registro, dict):
        return {}
    return {
        _normalizar_clave(clave): valor
        for clave, valor in registro.items()
        if not isinstance(valor, (dict, list)) and valor not in (None, "")
    }


def _registros(data):
    """Los registros de persona de la respuesta, por ruta y sin bajar de nivel.

    El contrato de la fuente 13 sigue abierto (task #243), así que se aceptan
    las tres formas vistas: el propio ``data``, ``data.persona`` y
    ``data.personas``. Lo que **no** se hace es buscar las claves en cualquier
    rama del árbol.
    """
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    persona = data.get("persona")
    if isinstance(persona, dict):
        return [persona]
    personas = data.get("personas")
    if isinstance(personas, list):
        return [item for item in personas if isinstance(item, dict)]
    return [data]


def _coincide(registro, dni, sexo):
    """¿El registro es de la persona que se consultó?

    Lo que el registro **no trae** no objeta: la fuente puede no devolver el
    documento o el sexo. El sexo se compara por la inicial porque el proveedor
    manda tanto ``F`` como ``FEMENINO``.
    """
    plano = _plano(registro)
    documento = re.sub(r"\D", "", _texto(_primero(plano, *CLAVES_DNI)))
    if documento and dni and documento != dni:
        return False
    genero = _texto(_primero(plano, *CLAVES_SEXO))[:1].upper()
    return not (genero and sexo and genero != _texto(sexo)[:1].upper())


def elegir_registro(payload, dni, sexo=""):
    """``(registro, error)``: el único registro atribuible a ``(dni, sexo)``.

    Ninguno o más de uno es una respuesta que no se puede usar: se devuelve el
    error y el paso 1 resuelve por padrón o manual, como con la fuente caída.
    """
    data = payload.get("data") if isinstance(payload, dict) else payload
    registros = _registros(data)
    candidatos = [registro for registro in registros if _coincide(registro, dni, sexo)]
    if len(candidatos) == 1:
        return candidatos[0], ""
    if registros and not candidatos:
        return None, ERROR_OTRO_DOCUMENTO
    return None, ERROR_AMBIGUA


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


def normalizar_persona(payload, dni, sexo=""):
    """Tolera variantes de nombres hasta que se cierre el contrato definitivo.

    Acepta el sobre completo del proveedor o un registro ya elegido. Lee solo el
    primer nivel del registro (SIIS-10) y ``nombres`` antes que ``nombre``: la
    fuente usa ``nombre`` para el nombre completo «APELLIDO, Ana» en algunas
    ramas y ``nombres`` para el de pila, que es lo que la pantalla muestra.
    """
    registro, _ = elegir_registro(payload, dni, sexo)
    flat = _plano(registro if registro is not None else payload)
    return {
        "dni": _texto(_primero(flat, *CLAVES_DNI)) or dni,
        "apellido": _texto(_primero(flat, "apellido", "apellidos")),
        "nombre": _texto(_primero(flat, "nombres", "nombre")),
        "fecha_nacimiento": fecha_iso(_primero(flat, "fecha_nacimiento", "fechaNacimiento", "nacimiento")),
        "sexo": _texto(_primero(flat, *CLAVES_SEXO)).upper(),
    }


def _informa_fallecido(data):
    """``True`` si la respuesta marca a la persona como fallecida.

    Se mira por las mismas vias que el resto del contrato: el ``mensaje`` que ya
    se inspecciona para el "no encontrado", la clave ``mensaf`` que usa el
    cliente RENAPER de este repo, y una marca booleana o una fecha de
    defuncion si la fuente las expone. El contrato definitivo de Base de
    Personas sigue abierto (task #243), asi que se aceptan variantes en lugar
    de fijar una sola clave.
    """
    if not isinstance(data, dict):
        return False
    plano = _aplanar(data)
    if _texto(_primero(plano, "mensaf")).upper() == "FALLECIDO":
        return True
    if "FALLECID" in _texto(_primero(plano, "mensaje")).upper():
        return True
    if _primero(plano, "fecha_fallecimiento", "fechaFallecimiento", "fecha_defuncion"):
        return True
    marca = _primero(plano, "fallecido", "es_fallecido")
    if isinstance(marca, bool):
        return marca
    return _texto(marca).upper() in ("S", "SI", "TRUE", "1")


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
            sesion.post,
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
        if cortacircuito.abierto():
            # SIIS-09: tres fallas de red seguidas. Quien pregunta ya sabe qué
            # hacer con un "no se pudo consultar": seguir por padrón o manual.
            return {"success": False, "error": "No se pudo consultar Base de Personas.", "cortado": True}
        try:
            response = instrument_external_call(
                "personas",
                sesion.get,
                f"{self.base_url}/personas/consulta/",
                params={"dni": dni, "sexo": sexo, "fuente_id": self.fuente_id},
                headers={"Authorization": f"Bearer {self._token()}"},
                timeout=self.timeout,
            )
            # Contestó: el servicio está en pie. Lo que abre el cortacircuito es
            # **no poder hablarle**; un 404 o un 500 son respuestas, y cualquiera
            # de las dos resetea el contador acá (SIIS-09).
            cortacircuito.registrar_exito()
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
            _, error = elegir_registro(body, dni, sexo)
            if error:
                # SIIS-10: dos registros que no se pueden desempatar, o uno que
                # es de otro documento. Antes se mezclaban en una sola identidad
                # y se marcaba **validada**; hoy el paso 1 sigue por padrón o
                # manual, igual que con la fuente caída.
                logger.warning("Base de Personas devolvió una respuesta que no se puede atribuir: %s", error)
                return {"success": False, "error": error}
            if _informa_fallecido(data):
                # Mismo contrato que el cliente RENAPER
                # (``legajos/services/consulta_renaper.py``): quien consume la
                # respuesta corta con ``fallecido``. El paso 1 del formulario
                # publico ya lo esperaba, pero nada lo producia nunca, asi que
                # la regla "FALLECIDO corta" del Cambio 41 no se cumplia.
                return {"success": False, "fallecido": True}
            return {"success": True, "data": normalizar_persona(body, dni, sexo), "datos_api": body}
        except (requests.RequestException, ValueError, TypeError) as exc:
            # Sin `logger.exception`: el traceback de `requests` arrastra la URL
            # completa, y ahí viaja el documento consultado (?dni=...). Queda el
            # tipo de error, que es lo que sirve para diagnosticar.
            logger.error("Error al consultar Base de Personas (%s)", type(exc).__name__)
            cortacircuito.registrar_falla()
            return {"success": False, "error": "No se pudo consultar Base de Personas."}


def consultar_persona(dni, sexo):
    dni = re.sub(r"\D", "", _texto(dni))
    if not dni:
        return {"success": False, "error": "El DNI es requerido."}
    sexo = _texto(sexo).upper()
    if sexo not in ("F", "M"):
        return {"success": False, "error": "El sexo debe ser F o M."}
    return PersonasAPIClient().consultar(dni, sexo)
