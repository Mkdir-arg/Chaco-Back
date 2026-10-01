from django.urls import path

from .views.inscripcion import (
    csrf_token_vigente,
    inscripcion_confirmacion,
    inscripcion_paso1,
    inscripcion_paso2,
)
from .views.public import (
    PortalHomeView,
)

app_name = "portal"

# SEC-29 (auditoría oct-2026): el portal ciudadano está apagado. Su registro creaba
# una cuenta sobre cualquier legajo existente con solo el DNI, y esa cuenta era la
# puerta de entrada de SEC-01 y SEC-09. El portal no está en uso (decisión del PM,
# 29-sep-2026), así que las rutas ``mi-perfil/*`` no se publican. Las vistas y los
# templates siguen en el repo, sin ruta: si el portal vuelve, la vuelta tiene que
# arreglar antes el registro (RENAPER + verificación de sexo) y recién después
# reponer estas rutas.
urlpatterns = [
    path("", PortalHomeView.as_view(), name="home"),
    # Token CSRF vigente para los formularios públicos: el login del backoffice
    # rota la cookie del navegador y dejaba el formulario abierto con un token viejo.
    path("csrf/", csrf_token_vigente, name="csrf_token"),
    # Formulario público de Becas (#293) — superficie sin login, por token.
    path("inscripcion/<uuid:token>/", inscripcion_paso1, name="inscripcion_paso1"),
    path("inscripcion/<uuid:token>/formulario/", inscripcion_paso2, name="inscripcion_paso2"),
    path("inscripcion/<uuid:token>/confirmacion/", inscripcion_confirmacion, name="inscripcion_confirmacion"),
]
