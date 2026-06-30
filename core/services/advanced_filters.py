"""Herramientas reutilizables para construir filtros avanzados en listados."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Iterable, Mapping, MutableMapping, Optional

from django.db.models import Q, QuerySet


class AdvancedFilterEngine:
    """Parsea filtros combinables enviados vía querystring y genera ``Q`` objects.

    La expectativa de formato coincide con la implementada originalmente en
    ``ComedorService.get_filtered_comedores``::

        {
          "logic": "AND" | "OR",
          "items": [
            {"field": str, "op": str, "value": Any, "empty_mode": str}
          ]
        }

    Donde la lógica combinada aplica ``OR`` entre filtros del mismo campo y el
    operador global (``AND`` por defecto) entre distintos campos.

    Args:
        field_map: Mapea el identificador expuesto a lookups de Django ORM.
        field_types: Define el tipo lógico de cada campo (por ejemplo ``text``,
            ``choice``, ``number`` o ``boolean``). Se usa para validar
            operadores y castear valores.
        allowed_ops: Opcional. Permite personalizar los operadores permitidos por
            tipo. Si no se provee se espera ``{"text": {...}, "number": {...}}``.
        field_casts: Funciones de casteo por campo; útiles cuando se requieren
            conversiones específicas (por ejemplo ``float`` para coordenadas).
        param_name: Nombre del parámetro GET que contiene el JSON de filtros.
    """

    def __init__(
        self,
        *,
        field_map: Mapping[str, str],
        field_types: Mapping[str, str],
        allowed_ops: Optional[Mapping[str, Iterable[str]]] = None,
        field_casts: Optional[Mapping[str, Callable[[Any], Any]]] = None,
        param_name: str = "filters",
    ) -> None:
        self.field_map = dict(field_map)
        self.field_types = dict(field_types)
        self.allowed_ops = {key: set(value) for key, value in (allowed_ops or {}).items()}
        self.field_casts = dict(field_casts or {})
        self.param_name = param_name

        missing_mappings = set(self.field_types) - set(self.field_map)
        if missing_mappings:
            raise ValueError(
                "AdvancedFilterEngine: field_types contiene claves sin mapeo: " + ", ".join(sorted(missing_mappings))
            )

    def filter_queryset(self, queryset: QuerySet, request_or_get: Any) -> QuerySet:
        """Devuelve ``queryset`` filtrado según los datos recibidos.

        Si no se logra construir un filtro válido retorna el queryset original
        sin modificaciones.
        """

        final_q = self.build_q(request_or_get)
        if final_q is None:
            return queryset
        return queryset.filter(final_q)

    def build_q(self, request_or_get: Any) -> Optional[Q]:
        """Construye el ``Q`` resultante a partir de los filtros recibidos."""

        raw_filters = self._extract_raw_filters(request_or_get)
        if not raw_filters:
            return None

        payload = self._load_payload(raw_filters)
        if not payload:
            return None

        items = payload.get("items") or []
        if not isinstance(items, list):
            return None

        groups: Dict[str, list[Q]] = {}
        for item in items:
            if not isinstance(item, MutableMapping):
                continue
            q_item = self._build_q_for_item(item)
            if q_item is None:
                continue
            field_name = item.get("field")
            if not field_name:
                continue
            groups.setdefault(field_name, []).append(q_item)

        if not groups:
            return None

        logic = str(payload.get("logic") or "AND").upper()
        use_or = logic == "OR"

        final_q: Optional[Q] = None
        for q_group in groups.values():
            if not q_group:
                continue
            group_q = q_group[0]
            for extra_q in q_group[1:]:
                group_q = group_q | extra_q

            if final_q is None:
                final_q = group_q
            else:
                final_q = (final_q | group_q) if use_or else (final_q & group_q)

        return final_q

    # --- Internal helpers -------------------------------------------------

    def _extract_raw_filters(self, request_or_get: Any) -> Any:
        """Obtiene el valor del parámetro configurado desde distintas fuentes."""

        params: Optional[Mapping[str, Any]] = None
        # ``HttpRequest`` expone ``GET`` cuya lectura puede fallar en tests.
        if hasattr(request_or_get, "GET"):
            try:
                params = request_or_get.GET
            except Exception:  # pragma: no cover - protección adicional
                params = None
        if params is None:
            if isinstance(request_or_get, Mapping):
                params = request_or_get
            else:
                params = None

        if not params:
            return None

        try:
            return params.get(self.param_name)
        except Exception:  # pragma: no cover - compatibilidad con QueryDict
            return None

    def _load_payload(self, raw_filters: Any) -> Optional[dict[str, Any]]:
        """Decodifica el JSON enviado en el parámetro de filtros."""

        if isinstance(raw_filters, (bytes, bytearray)):
            raw_filters = raw_filters.decode()

        if isinstance(raw_filters, str):
            raw_filters = raw_filters.strip()
            if not raw_filters:
                return None
            try:
                parsed = json.loads(raw_filters)
            except (json.JSONDecodeError, TypeError):
                return None
        elif isinstance(raw_filters, MutableMapping):
            parsed = dict(raw_filters)
        elif isinstance(raw_filters, Mapping):
            parsed = dict(raw_filters)
        else:
            return None

        if not isinstance(parsed, dict):
            return None
        return parsed

    def _build_q_for_item(self, item: MutableMapping[str, Any]) -> Optional[Q]:
        """Construye el ``Q`` para un filtro individual."""

        field = item.get("field")
        op = item.get("op")
        if not field or field not in self.field_map or not op:
            return None

        mapped_field = self.field_map[field]
        field_type = self.field_types.get(field)
        if not field_type:
            return None

        allowed_ops = self.allowed_ops.get(field_type)
        if allowed_ops is not None and op not in allowed_ops:
            return None

        if op == "empty":
            empty_mode = str(item.get("empty_mode") or "both").lower()
            null_q = Q(**{f"{mapped_field}__isnull": True})
            if field_type == "text":
                blank_q = Q(**{f"{mapped_field}__exact": ""})
                if empty_mode == "null":
                    return null_q
                if empty_mode == "blank":
                    return blank_q
                return null_q | blank_q
            return null_q

        value = item.get("value")
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None

        ok, casted = self._coerce_value(field, value, field_type)
        if not ok:
            return None

        lookup = None
        negate = False
        if field_type == "text":
            if op == "eq":
                lookup = f"{mapped_field}__iexact"
            elif op == "ne":
                lookup = f"{mapped_field}__iexact"
                negate = True
            elif op == "contains":
                lookup = f"{mapped_field}__icontains"
            elif op == "ncontains":
                lookup = f"{mapped_field}__icontains"
                negate = True
        elif field_type == "choice":
            if op == "eq":
                lookup = f"{mapped_field}__iexact"
            elif op == "ne":
                lookup = f"{mapped_field}__iexact"
                negate = True
        elif field_type == "number":
            if op == "eq":
                lookup = f"{mapped_field}__exact"
            elif op == "ne":
                lookup = f"{mapped_field}__exact"
                negate = True
            elif op == "gt":
                lookup = f"{mapped_field}__gt"
            elif op == "lt":
                lookup = f"{mapped_field}__lt"
        elif field_type == "boolean":
            if op == "eq":
                lookup = f"{mapped_field}__exact"
            elif op == "ne":
                lookup = f"{mapped_field}__exact"
                negate = True

        if not lookup:
            return None

        q_object = Q(**{lookup: casted})
        return ~q_object if negate else q_object

    def _coerce_value(self, field: str, value: Any, field_type: str) -> tuple[bool, Any]:
        """Intenta castear ``value`` según el tipo del campo."""

        if field in self.field_casts:
            try:
                return True, self.field_casts[field](value)
            except Exception:  # pragma: no cover - protección frente a errores
                return False, None

        if field_type == "number":
            try:
                return True, int(value)
            except (TypeError, ValueError):
                return False, None
        if field_type == "boolean":
            truthy = {True, 1, "1", "true", "t", "yes", "y"}
            falsy = {False, 0, "0", "false", "f", "no", "n"}

            if isinstance(value, str):
                value = value.strip().lower()

            if value in truthy:
                return True, True
            if value in falsy:
                return True, False
            return False, None

        return True, value


__all__ = ["AdvancedFilterEngine"]
