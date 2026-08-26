"""Cabeceras de seguridad que Django no emite por sí solo.

Nació de la revisión del 26/08/2026 sobre el formulario público. Dos motivos:

1. **No había `Content-Security-Policy`.** Es el control que limita el daño si
   alguna vez entra un script ajeno a la página donde el ciudadano tipea su
   documento: ``connect-src 'self'`` corta la exfiltración y ``script-src``
   impide cargar código de otro origen.
2. **El anti-clickjacking estaba roto en el despliegue.** Django manda
   ``X-Frame-Options: DENY``, pero el ingress lo reescribía con
   ``ALLOW-FROM …``, una directiva obsoleta que los navegadores modernos
   ignoran —y al ignorarla, la página quedaba embebible—. ``frame-ancestors``
   del CSP hace el mismo trabajo y no depende de esa cabecera.

Se escribió a mano en vez de sumar ``django-csp`` porque la política es una sola
y el repo ya tiene sus propios middlewares.

El único tercero permitido es el reCAPTCHA de Google, y solo porque el
formulario público lo necesita: el resto de las librerías se autoalojan en
``static/vendor/``.
"""

from django.conf import settings

RECAPTCHA_HOSTS = ("https://www.google.com", "https://www.gstatic.com")
# El detalle de un formulario de Becas embebe el mapa del lugar de la toma.
MAPA_HOSTS = ("https://www.openstreetmap.org",)

# 'unsafe-inline' y 'unsafe-eval' son necesarios hoy: las plantillas tienen
# scripts y estilos en línea, y Alpine evalúa expresiones con `new Function`.
# Aun así la política sirve: bloquea cargar código de otro origen y, sobre todo,
# mandarle datos a cualquiera que no seamos nosotros.
POLITICA_BASE = {
    "default-src": ["'self'"],
    "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'", *RECAPTCHA_HOSTS],
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:", "blob:", *MAPA_HOSTS],
    "font-src": ["'self'", "data:"],
    # Sin `ws:`/`wss:` pelados: esos esquemas sueltos habilitan CUALQUIER host y
    # dejaban abierta justo la vía de exfiltración que esta directiva cierra.
    # `'self'` ya cubre el WebSocket del mismo origen (CSP3).
    "connect-src": ["'self'"],
    "frame-src": ["'self'", *RECAPTCHA_HOSTS, *MAPA_HOSTS],
    "frame-ancestors": ["'none'"],
    "form-action": ["'self'"],
    "base-uri": ["'self'"],
    "object-src": ["'none'"],
}

PERMISSIONS_POLICY = "geolocation=(self), camera=(self), microphone=(), payment=(), usb=()"


def _politica():
    extra = getattr(settings, "CSP_EXTRA_SOURCES", {}) or {}
    partes = []
    for directiva, valores in POLITICA_BASE.items():
        completos = list(valores) + [v for v in extra.get(directiva, []) if v not in valores]
        partes.append(f"{directiva} {' '.join(completos)}" if completos else directiva)
    return "; ".join(partes)


class SecurityHeadersMiddleware:
    """Agrega CSP y Permissions-Policy, sin pisar lo que ya venga puesto."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.politica = _politica()
        self.solo_reportar = bool(getattr(settings, "CSP_REPORT_ONLY", False))

    def __call__(self, request):
        response = self.get_response(request)
        # El admin de Django y el navegador de la API traen su propio JS inline y
        # no son superficie pública: no vale la pena romperlos por esta política.
        if request.path.startswith(("/admin/", "/api/docs/", "/api/redoc/")):
            return response
        cabecera = "Content-Security-Policy-Report-Only" if self.solo_reportar else "Content-Security-Policy"
        response.setdefault(cabecera, self.politica)
        response.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        return response
