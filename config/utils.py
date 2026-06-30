# DEPRECADO: Todas las utilidades fueron migradas a core.utils
# Este archivo se mantiene solo por compatibilidad con Django

import warnings

from core.utils import (  # noqa
    DailyFileHandler,
    convert_string_to_int,
    format_fecha_django,
    format_fecha_gestionar,
    format_serializer_errors,
)

warnings.warn(
    "config.utils está deprecado. Usá core.utils en su lugar",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "DailyFileHandler",
    "convert_string_to_int",
    "format_fecha_gestionar",
    "format_fecha_django",
    "format_serializer_errors",
]
