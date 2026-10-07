"""La configuración de logging, armada por una función para poder probarla (OPS-03).

Hasta el Cambio 153, `config/settings.py` traía el diccionario `LOGGING` escrito a mano
con dos propiedades que nadie medía y que costaban caro en producción:

1. **`django.request` tenía `propagate: False` y handlers solo a archivo.** O sea: el
   traceback de cada 500 iba a `logs/<fecha>/error.log` y **a ningún lado más**. En
   Kubernetes (ECOM) ese directorio es efímero y `kubectl logs` solo muestra la línea
   `core.requests … status=500` del middleware: el traceback no existía para quien
   diagnosticaba. Sin eso, ningún otro hallazgo de la auditoría se puede diagnosticar en
   el ambiente donde pasa.
2. **Los archivos se escribían siempre y sin retención.** En icore `./logs` está montado
   desde el host y crece sin techo; en un filesystem de solo lectura, crear el directorio
   al importar settings es un arranque fallido.

Ahora: **stdout siempre** (es lo que recogen `docker compose logs` y `kubectl logs`) y
los archivos **solo si `LOG_TO_FILES=True`**, con purga de los días viejos.
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from pathlib import Path

# Las carpetas que crea `core.utils.DailyFileHandler`: una por día, `YYYY-MM-DD`.
CARPETA_DIARIA = re.compile(r"^\d{4}-\d{2}-\d{2}$")

ARCHIVOS = ("info_file", "error_file", "warning_file", "critical_file", "data_file")


def purgar_logs_viejos(log_dir: Path, retencion_dias: int) -> list[Path]:
    """Borra las carpetas diarias anteriores a la retención. Devuelve las borradas.

    Solo toca subdirectorios de `log_dir` cuyo nombre es una fecha `YYYY-MM-DD`: lo que
    escribió el propio `DailyFileHandler` y nada más. Cualquier otra cosa que haya en
    `logs/` se queda donde está.
    """
    import shutil

    if retencion_dias <= 0 or not log_dir.is_dir():
        return []

    # noqa DTZ011 deliberado: las carpetas diarias las nombra el handler con la
    # fecha del proceso, así que el corte tiene que usar esa misma fecha y no la
    # del `TIME_ZONE` de Django, o la rotación borraría un día de más o de menos.
    corte = date.today() - timedelta(days=retencion_dias)  # noqa: DTZ011
    borradas = []
    for hijo in sorted(log_dir.iterdir()):
        if not hijo.is_dir() or not CARPETA_DIARIA.match(hijo.name):
            continue
        try:
            dia = date.fromisoformat(hijo.name)
        except ValueError:  # pragma: no cover — lo filtra el regex
            continue
        if dia < corte:
            shutil.rmtree(hijo, ignore_errors=True)
            borradas.append(hijo)
    return borradas


def construir_logging(*, log_dir: Path, debug: bool, log_to_files: bool) -> dict:
    """El `LOGGING` de Django. `log_to_files=False` deja todo por stdout y nada en disco."""
    nivel = "DEBUG" if debug else "INFO"

    def archivo(nombre, nivel_handler, filtro, formatter="verbose"):
        return {
            "level": nivel_handler,
            "filters": [filtro],
            "class": "core.utils.DailyFileHandler",
            "filename": str(log_dir / nombre),
            "formatter": formatter,
        }

    handlers = {
        "console": {
            "level": "DEBUG" if debug else "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    }
    if log_to_files:
        handlers.update(
            {
                "info_file": archivo("info.log", "INFO", "info_only"),
                "error_file": archivo("error.log", "ERROR", "error_only"),
                "warning_file": archivo("warning.log", "WARNING", "warning_only"),
                "critical_file": archivo("critical.log", "CRITICAL", "critical_only"),
                "data_file": archivo("data.log", "INFO", "data_only", formatter="json_data"),
            }
        )

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "info_only": {"()": "django.utils.log.CallbackFilter", "callback": lambda r: r.levelno == logging.INFO},
            "error_only": {"()": "django.utils.log.CallbackFilter", "callback": lambda r: r.levelno == logging.ERROR},
            "warning_only": {
                "()": "django.utils.log.CallbackFilter",
                "callback": lambda r: r.levelno == logging.WARNING,
            },
            "critical_only": {
                "()": "django.utils.log.CallbackFilter",
                "callback": lambda r: r.levelno == logging.CRITICAL,
            },
            "data_only": {"()": "django.utils.log.CallbackFilter", "callback": lambda r: hasattr(r, "data")},
        },
        "formatters": {
            "verbose": {"format": "[{asctime}] {module} {levelname} {name}: {message}", "style": "{"},
            "simple": {"format": "[{asctime}] {levelname} {message}", "style": "{"},
            "json_data": {"()": "core.utils.JSONDataFormatter"},
        },
        "handlers": handlers,
        "root": {
            # El único lugar donde se decide a dónde van los registros. Todo lo demás
            # propaga hasta acá, así que agregar un destino se hace en un solo renglón.
            "handlers": ["console", *(nombre for nombre in ARCHIVOS if nombre in handlers)],
            "level": nivel,
        },
        "loggers": {
            "django": {"handlers": [], "level": nivel, "propagate": True},
            # OPS-03: sin handlers propios y propagando. Con `propagate: False` y los
            # handlers de archivo, el traceback de cada 500 no llegaba a stdout.
            "django.request": {"handlers": [], "level": "WARNING", "propagate": True},
            "core.requests": {"handlers": [], "level": "INFO", "propagate": True},
        },
    }
