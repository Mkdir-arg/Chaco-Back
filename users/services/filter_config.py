"""Configuración para filtros combinables de usuarios."""

from typing import Any, Dict

# --- Backend -----------------------------------------------------------------

FIELD_MAP: Dict[str, str] = {
    "username": "username",
    "email": "email",
    "first_name": "first_name",
    "last_name": "last_name",
    "rol": "groups__name",
}

FIELD_TYPES: Dict[str, str] = {
    key: "text"
    for key in [
        "username",
        "email",
        "first_name",
        "last_name",
        "rol",
    ]
}

TEXT_OPS = ["contains", "ncontains", "eq", "ne", "empty"]
NUM_OPS = ["eq", "ne", "gt", "lt", "empty"]

# --- Frontend ----------------------------------------------------------------

FILTER_FIELDS = [
    {"name": "first_name", "label": "Nombre", "type": "text"},
    {"name": "last_name", "label": "Apellido", "type": "text"},
    {"name": "username", "label": "Usuario", "type": "text"},
    {"name": "email", "label": "Email", "type": "text"},
    {"name": "rol", "label": "Rol", "type": "text"},
]


def get_filters_ui_config() -> Dict[str, Any]:
    """Configuración serializable para la UI de filtros avanzados."""

    return {
        "fields": FILTER_FIELDS,
        "operators": {
            "text": list(TEXT_OPS),
            "number": list(NUM_OPS),
        },
        "defaultOperators": {
            "text": "contains",
            "number": "eq",
        },
    }


__all__ = [
    "FIELD_MAP",
    "FIELD_TYPES",
    "TEXT_OPS",
    "NUM_OPS",
    "FILTER_FIELDS",
    "get_filters_ui_config",
]
