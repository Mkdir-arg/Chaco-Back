from django import template

register = template.Library()


@register.filter
def endswith(value, suffix):
    try:
        return str(value).lower().endswith(str(suffix).lower())
    except Exception:
        return False


@register.filter
def is_url(value):
    """
    Detecta si un string es una URL (comienza con /) o un nombre de vista
    Usage: {% if cancel_url|is_url %}{{ cancel_url }}{% else %}{% url cancel_url %}{% endif %}
    """
    try:
        return str(value).startswith("/")
    except AttributeError:
        return False


@register.filter
def getattr(obj, attr_name):
    """
    Obtiene un atributo de un objeto de forma segura, manejando relaciones
    Usage: {{ obj|getattr:"field_name" }}
    """
    import builtins

    try:
        value = builtins.getattr(obj, attr_name, None)
        if value is None:
            return ""

        # Manejar relaciones M2M haciendo join de sus elementos
        try:
            if hasattr(value, "all") and not isinstance(value, (str, bytes)):
                iterable = value.all()
                return ", ".join(str(v) for v in iterable)
        except Exception:
            # Si falla, caer al string por defecto
            pass

        return str(value)
    except (AttributeError, TypeError):
        return ""
