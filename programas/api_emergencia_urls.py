"""URLs de la API de campo del módulo Emergencia (PR 5: base, perfil y M1; PR 9-API: M3, recepción de kits;
PR 8: M2, llegada de familias).

Namespace ``emergencia_api``. El login es el de la app de campo,
``/api/becas/auth/token/``: un solo token por usuario, y cada recurso con su permiso.
El contrato está en ``docs/internal/contrato-app-emergencia.md``.
"""

from django.urls import path

from programas.api.views_emergencia import (
    AceptarDerivacionView,
    AlojarFamiliaView,
    AvisarALaMesaView,
    BuscarFamiliaView,
    CancelarIngresoView,
    CasosEmergenciaView,
    CerrarConDiferenciaView,
    ConfirmarIntegranteView,
    ConsultarPersonaEmergenciaView,
    EntregaKitDetalleView,
    EntregasDelDispositivoView,
    IngresoDirectoView,
    IntegrantesView,
    IntegranteView,
    LocalidadesEmergenciaView,
    MisCasosEmergenciaView,
    MisDispositivosEmergenciaView,
    PerfilEmergenciaView,
    PlazasDelDispositivoView,
    RaizApiEmergencia,
    RechazarDerivacionView,
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
    # M2 · Llegada de familias (PR 8): la guardia con `dispositivo.admitir` en su Equipo.
    path("dispositivos/<int:dispositivo_id>/buscar/", BuscarFamiliaView.as_view(), name="dispositivo-buscar"),
    path("dispositivos/<int:dispositivo_id>/plazas/", PlazasDelDispositivoView.as_view(), name="dispositivo-plazas"),
    path("derivaciones/<int:pk>/aceptar/", AceptarDerivacionView.as_view(), name="derivacion-aceptar"),
    path("derivaciones/<int:pk>/rechazar/", RechazarDerivacionView.as_view(), name="derivacion-rechazar"),
    path("casos/<int:pk>/integrantes/", IntegrantesView.as_view(), name="caso-integrantes"),
    path("casos/<int:pk>/integrantes/<int:n>/", IntegranteView.as_view(), name="caso-integrante"),
    path(
        "casos/<int:pk>/integrantes/<int:n>/confirmar/",
        ConfirmarIntegranteView.as_view(),
        name="caso-integrante-confirmar",
    ),
    path("casos/<int:pk>/alojar/", AlojarFamiliaView.as_view(), name="caso-alojar"),
    path("casos/<int:pk>/cerrar-diferencia/", CerrarConDiferenciaView.as_view(), name="caso-cerrar-diferencia"),
    path("casos/<int:pk>/cancelar-ingreso/", CancelarIngresoView.as_view(), name="caso-cancelar-ingreso"),
    # Ingreso directo y aviso a la mesa (decisión 4 del PM): al final y en sus propias rutas, para poder sacarlos.
    path(
        "dispositivos/<int:dispositivo_id>/ingreso-directo/",
        IngresoDirectoView.as_view(),
        name="dispositivo-ingreso-directo",
    ),
    path("dispositivos/<int:dispositivo_id>/avisar-mesa/", AvisarALaMesaView.as_view(), name="dispositivo-avisar-mesa"),
]
