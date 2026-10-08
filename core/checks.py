"""System checks propios del entorno (RED-61, SIIS-09).

``settings.py`` lee ~90 variables de entorno y la única validada era
``DJANGO_SECRET_KEY``. Las de acá son las que, mal puestas, no se notan:
una integración **sin baja** que apunta al ambiente equivocado responde 200 y
el caso queda «informado» sin que el organismo reciba nada; y unos timeouts
generosos de más no fallan nunca hasta que nginx corta el clic de «Aprobar»
con el alta ya en camino.

Corren con ``manage.py check --deploy`` (``deploy=True``): el CI, y la etapa
``verify`` del pipeline de ECOM cuando exista. **No** frenan el arranque del
contenedor; para eso habría que llamarlos desde el entrypoint.

El disparador de producción es ``DATANACH_ES_PRODUCCION``, una variable
explícita que ECOM setea únicamente en PRD, y no ``settings.ENVIRONMENT``: QA
—el testing de ECOM, que usa el SIIS de desarrollo legítimamente— e icore
también valen ``prd``.
"""

import os
from urllib.parse import urlparse

from django.conf import settings
from django.core.checks import Error, Tags, register
from django.core.checks import Warning as CheckWarning

from core.integraciones import PRESUPUESTO_SEGUNDOS, cadenas_fuera_de_presupuesto

#: Dominio del SIIS de **desarrollo** de ECOM.
DOMINIO_SIIS_DESARROLLO = "ecomdev.ar"

#: Variable que ECOM setea solo en producción.
VARIABLE_PRODUCCION = "DATANACH_ES_PRODUCCION"


def es_produccion():
    return os.environ.get(VARIABLE_PRODUCCION, "").strip() == "1"


def es_host_de_desarrollo(url):
    host = (urlparse(url).hostname or "").lower()
    return host == DOMINIO_SIIS_DESARROLLO or host.endswith(f".{DOMINIO_SIIS_DESARROLLO}")


@register(Tags.compatibility, deploy=True)
def entorno_de_integraciones(app_configs, **kwargs):
    """Las integraciones externas apuntan al ambiente que corresponde."""
    if settings.DEBUG:
        return []

    mensajes = []
    url = (getattr(settings, "SIIS_API_URL", "") or "").strip()
    if not url:
        mensajes.append(
            Error(
                "SIIS_API_URL está vacía: las altas de beneficiarios no van a ninguna parte.",
                hint=(
                    "Definí SIIS_API_URL en el entorno (ver .env.local.example). Ya no tiene default: "
                    "el que había apuntaba al SIIS de desarrollo, que responde 200 y deja el caso "
                    "como informado sin que el organismo reciba nada."
                ),
                id="core.E001",
            )
        )
    elif es_produccion() and es_host_de_desarrollo(url):
        mensajes.append(
            Error(
                f"SIIS_API_URL apunta al SIIS de desarrollo ({url}) con {VARIABLE_PRODUCCION}=1.",
                hint=(
                    "En producción SIIS_API_URL tiene que ser el host productivo del organismo. "
                    "La integración no tiene baja: un alta mandada al ambiente equivocado no se deshace."
                ),
                id="core.E002",
            )
        )

    if getattr(settings, "RENAPER_TEST_MODE", False):
        if es_produccion():
            # SIIS-20. El modo de prueba no es un stub inerte: inventa nombre,
            # apellido, fecha de nacimiento y domicilio al azar y los devuelve
            # con ``success=True``, cacheados 10 min por (dni, sexo). En PRD eso
            # es dar de alta ciudadanos con identidad inventada y **marcarlos
            # como validados**, que es lo que después habilita a aprobarlos.
            mensajes.append(
                Error(
                    f"RENAPER_TEST_MODE=True con {VARIABLE_PRODUCCION}=1: la identidad de los ciudadanos "
                    "se resolvería con datos inventados al azar y quedarían marcados como validados.",
                    hint=(
                        "Sacá RENAPER_TEST_MODE del entorno de producción. Es la escotilla para levantar "
                        "un ambiente sin credenciales del organismo (ver .env.qa.example), no una opción "
                        "de PRD."
                    ),
                    id="core.E004",
                )
            )
        else:
            mensajes.append(
                CheckWarning(
                    "RENAPER_TEST_MODE=True con DEBUG=False: la identidad se resuelve contra datos de prueba.",
                    hint="Sacá RENAPER_TEST_MODE del entorno salvo que sea un ambiente de pruebas a propósito.",
                    id="core.W001",
                )
            )

    # SIIS-21. Sin claves de Google el paso 1 del link público cae al desafío
    # aritmético propio, que un script resuelve leyendo la pregunta del HTML.
    # Además de no frenar automatización, es lo que obliga a que la cubeta por
    # documento cuente por IP (``portal.services.inscripcion.documento_excedido``)
    # y, con eso, a resignar parte de la defensa contra enumeración.
    #
    # SEC-37 / **D-37 = No**: el Cambio 71 no se reabre —el paso 2 sigue mostrando
    # el nombre y la fecha de nacimiento a partir de DNI + sexo— y la contrapartida
    # acordada es que en producción el captcha sea real. Por eso esto dejó de ser
    # un aviso (``core.W003``) y es un **error** desde el Cambio 185: lo que
    # sostiene la decisión no es una línea más en el log del deploy sino que
    # ``manage.py check --deploy`` se ponga rojo. Fuera de producción sigue sin
    # decir nada: dev, QA y los tests corren con el desafío aritmético a propósito.
    sin_recaptcha = not (
        (getattr(settings, "RECAPTCHA_SITE_KEY", "") or "").strip()
        and (getattr(settings, "RECAPTCHA_SECRET_KEY", "") or "").strip()
    )
    if es_produccion() and sin_recaptcha:
        mensajes.append(
            Error(
                f"Sin RECAPTCHA_SITE_KEY/RECAPTCHA_SECRET_KEY con {VARIABLE_PRODUCCION}=1: el link público "
                "queda con el desafío aritmético, que se resuelve leyendo la pregunta del HTML.",
                hint=(
                    "Cargá las claves de reCAPTCHA v2 en el entorno de producción (D-37). El desafío "
                    "aritmético es el respaldo para que un ambiente sin credenciales siga funcionando, "
                    "no una configuración de PRD: el paso 2 del link muestra nombre y fecha de nacimiento "
                    "a partir del DNI, y el captcha real es lo que lo protege de un barrido."
                ),
                id="core.E005",
            )
        )
    return mensajes


#: Ambientes servidos: los que tienen Redis y cuyo `ENVIRONMENT` es una declaración.
ENTORNOS_SERVIDOS = ("prd", "qa")


@register(Tags.compatibility, deploy=True)
def entorno_declarado(app_configs, **kwargs):
    """El módulo endurecido corre con el `ENVIRONMENT` declarado (OPS-12).

    Hasta el Cambio 165, ``settings_production`` reasignaba ``ENVIRONMENT = "prd"`` y
    tapaba el olvido: el ambiente decía «prd» y el cache era LocMem. Ahora no lo tapa,
    así que un ambiente servido sin la variable queda con los defaults de desarrollo
    —cache y channel layer locales al proceso— mientras sirve tráfico real con HSTS y
    cookies seguras. Eso no se ve mirando una pantalla: se ve acá.
    """
    if os.environ.get("DJANGO_SETTINGS_MODULE", "") != "config.settings_production":
        return []
    if settings.ENVIRONMENT in ENTORNOS_SERVIDOS:
        return []
    return [
        CheckWarning(
            f"ENVIRONMENT={settings.ENVIRONMENT!r} con config.settings_production: el módulo "
            "endurecido corriendo con la configuración de un ambiente de desarrollo.",
            hint=(
                "Declará ENVIRONMENT=prd o ENVIRONMENT=qa en el entorno del contenedor "
                "(ver .env.qa.example). Con un valor de desarrollo, el cache y el channel layer "
                "quedan locales al proceso: el throttle cuenta por worker, una invalidación limpia "
                "un worker de varios y los websockets no cruzan entre pods."
            ),
            id="core.W002",
        )
    ]


@register(Tags.security, deploy=True)
def media_x_accel_necesita_el_location_interno(app_configs, **kwargs):
    """``MEDIA_X_ACCEL=True`` exige un ``location internal`` en el servidor de adelante.

    Con la variable prendida, ``core.views.media`` autoriza y después devuelve una
    respuesta **vacía** con ``X-Accel-Redirect: /protected-media/<ruta>``, esperando que
    el servidor de adelante ponga los bytes. Si ese ``location`` no existe —el caso de
    ECOM mientras D-09/H-05 siga abierta— el usuario recibe un **200 de 0 bytes**, no un
    error: baja archivos vacíos y nadie se entera (seguimiento de #643).

    Django **no puede verificarlo**: el ingress es de otro equipo y no se consulta desde
    acá. Por eso es un aviso y no un error, y por eso solo habla cuando alguien prendió
    la variable, que es justo el momento en el que hace falta leerlo. El default
    (apagado) entrega los bytes desde Django y no dice nada. El paso operativo está en
    ``docker/k8s/README.md``.
    """
    if not getattr(settings, "MEDIA_X_ACCEL", False):
        return []
    return [
        CheckWarning(
            "MEDIA_X_ACCEL=True: las descargas de /media/ las entrega el servidor de adelante. "
            "Si no tiene el bloque `location /protected-media/ { internal; alias <MEDIA_ROOT>; }`, "
            "toda descarga responde 200 con 0 bytes, sin error.",
            hint=(
                "Confirmá con quien opera el ingress que ese `location internal` existe y apunta al "
                "mismo volumen que MEDIA_ROOT, y probalo bajando un archivo conocido (el `nginx.conf` "
                "del repo ya lo tiene; en ECOM es D-09/H-05). Si no está, dejá MEDIA_X_ACCEL sin "
                "definir: el default entrega los bytes desde Django."
            ),
            id="core.W004",
        )
    ]


@register(Tags.compatibility, deploy=True)
def presupuesto_de_llamadas_externas(app_configs, **kwargs):
    """La red de un request entra en los 60 s que aguanta nginx (SIIS-09).

    A diferencia del check de arriba, este corre también con ``DEBUG=True``: no
    mira el ambiente, mira la aritmética de los timeouts configurados contra las
    cadenas declaradas en ``core.integraciones.CADENAS``. Es lo que impide que
    «subile el timeout, que SIIS anda lento» vuelva a dejar «Aprobar» por encima
    del corte del gateway sin que nadie lo note hasta el 504.
    """
    return [
        Error(
            f"«{nombre}» puede tardar {segundos} s de red y el presupuesto es "
            f"{PRESUPUESTO_SEGUNDOS} s (nginx corta el request a los 60).",
            hint=(
                "Bajá los timeouts del entorno (SIIS_API_*, PERSONAS_API_*, RENAPER_*, "
                "EMAIL_TIMEOUT) o sacá una llamada de la cadena. La cadena declarada vive en "
                "core.integraciones.CADENAS: si el código cambió y ya no es esa, actualizala ahí."
            ),
            id="core.E003",
        )
        for nombre, segundos in cadenas_fuera_de_presupuesto()
    ]
