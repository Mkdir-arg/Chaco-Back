import logging

from django.urls import reverse

from core.services.advanced_filters import AdvancedFilterEngine
from users.selectors import get_usuarios_queryset
from users.selectors.usuarios import usuarios_visibles_para
from users.users_filter_config import (
    FIELD_MAP as BENEFICIARIO_FILTER_MAP,
    FIELD_TYPES as BENEFICIARIO_FIELD_TYPES,
    NUM_OPS as BENEFICIARIO_NUM_OPS,
    TEXT_OPS as BENEFICIARIO_TEXT_OPS,
    get_filters_ui_config,
)

logger = logging.getLogger("django")

BENEFICIARIO_ADVANCED_FILTER = AdvancedFilterEngine(
    field_map=BENEFICIARIO_FILTER_MAP,
    field_types=BENEFICIARIO_FIELD_TYPES,
    allowed_ops={
        "text": BENEFICIARIO_TEXT_OPS,
        "number": BENEFICIARIO_NUM_OPS,
    },
)


class UsuariosService:
    @staticmethod
    def get_filtered_usuarios(request_or_get, operador=None):
        """Aplica filtros combinables sobre el listado de usuarios.

        Con ``operador`` se acota el listado al alcance del operador (admin de
        programa ve solo usuarios con algún rol de sus programas).
        """
        base_qs = (
            usuarios_visibles_para(operador)
            if operador is not None
            else get_usuarios_queryset()
        )
        return BENEFICIARIO_ADVANCED_FILTER.filter_queryset(base_qs, request_or_get)

    @staticmethod
    def get_usuarios_queryset():
        """Query optimizada para usuarios"""
        return get_usuarios_queryset()

    @staticmethod
    def get_usuarios_list_context():
        """Configuración para la lista de usuarios"""
        return {
            "table_headers": [
                {"title": "Nombre", "width": "12%"},
                {"title": "Apellido", "width": "20%"},
                {"title": "Username", "width": "10%"},
                {"title": "Email", "width": "8%"},
                {"title": "Roles", "width": "20%"},
            ],
            "table_fields": [
                {"name": "first_name"},
                {"name": "last_name"},
                {"name": "username"},
                {"name": "email"},
                {"name": "groups"},
            ],
            "table_actions": [
                {
                    "label": "Editar",
                    "url_name": "users:usuario_editar",
                    "type": "primary",
                    "class": "editar",
                },
                {
                    "label": "Activar/Desactivar",
                    "url_name": "users:usuario_toggle",
                    "type": "warning",
                    "class": "toggle",
                },
            ],
            "breadcrumb_items": [
                {"text": "Usuarios", "url": reverse("users:usuarios")},
                {"text": "Listar", "active": True},
            ],
            "reset_url": reverse("users:usuarios"),
            "add_url": reverse("users:usuario_crear"),
            "filters_mode": True,
            "filters_config": get_filters_ui_config(),
            "filters_action": reverse("users:usuarios"),
            "show_add_button": True,
        }
