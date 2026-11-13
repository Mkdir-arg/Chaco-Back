"""URLs de la API de campo del módulo Emergencia (PR 5: base, perfil y M1; PR 9-API: M3, recepción de kits).

Namespace ``emergencia_api``. El login es el de la app de campo,
``/api/becas/auth/token/``: un solo token por usuario, y cada recurso con su permiso.
El contrato está en ``docs/internal/contrato-app-emergencia.md``.
"""

from django.urls import path

from programas.api.views_emergencia import (
    CasosEmergenciaView,
    ConsultarPersonaEmergenciaView,
    EntregaKitDetalleView,
    EntregasDelDispositivoView,
    LocalidadesEmergenciaView,
    MisCasosEmergenciaView,
    MisDispositivosEmergenciaView,
    PerfilEmergenciaView,
    RaizApiEmergencia,
    RecibirEntregaKitView,
)

app_name = "emergencia_api"

#: Lo que lista la raíz: clave del índice → nombre de la ruta en este namespace.
INDICE = {
    "perfil": "perfil",
    "personas/consultar": "personas-consultar",
    "localidades": "localidades",
    "casos": "caso-list",
    "casos/mios": "caso-mios",
    "mis-dispositivos": "mis-dispositivos",
}

urlpatterns = [
    path("", RaizApiEmergencia.as_view(api_root_dict=INDICE), name="api-root"),
    path("perfil/", PerfilEmergenciaView.as_view(), name="perfil"),
    path("personas/consultar/", ConsultarPersonaEmergenciaView.as_view(), name="personas-consultar"),
    path("localidades/", LocalidadesEmergenciaView.as_view(), name="localidades"),
    path("casos/", CasosEmergenciaView.as_view(), name="caso-list"),
    path("casos/mios/", MisCasosEmergenciaView.as_view(), name="caso-mios"),
    # M3 · Recepción de kits: la guardia con `emergencia.recibir_kit` en su Equipo.
    path("mis-dispositivos/", MisDispositivosEmergenciaView.as_view(), name="mis-dispositivos"),
    path(
        "dispositivos/<int:dispositivo_id>/entregas/", EntregasDelDispositivoView.as_view(), name="dispositivo-entregas"
    ),
    path("entregas/<int:pk>/", EntregaKitDetalleView.as_view(), name="entrega-detail"),
    path("entregas/<int:pk>/recibir/", RecibirEntregaKitView.as_view(), name="entrega-recibir"),
]
