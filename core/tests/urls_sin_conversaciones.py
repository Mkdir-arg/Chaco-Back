"""URLconf de prueba: `config.urls` **sin los dos includes de `conversaciones`** (RED-13).

Es el ambiente que va a existir el día que G1-01 fase 2 apague la app. Se arma
filtrando la lista real en vez de copiarla, para que una ruta nueva de `config/urls.py`
aparezca acá sola y el test no mida un URLconf congelado de 2026.

Lo usa `core/tests/test_shell_backoffice.py`.
"""

from config.urls import handler500  # noqa: F401
from config.urls import urlpatterns as _urlpatterns_completo

# Los dos `include()` de la app. `ws/conversaciones/` queda: no es de la app, es el 426
# que `config/urls.py` devuelve cuando el runtime no es ASGI.
PREFIJOS_DE_CONVERSACIONES = ("conversaciones/", "api/conversaciones/")

urlpatterns = [
    patron for patron in _urlpatterns_completo if str(getattr(patron, "pattern", "")) not in PREFIJOS_DE_CONVERSACIONES
]
