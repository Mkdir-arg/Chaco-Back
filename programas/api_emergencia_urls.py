"""URLs de la API de campo del módulo Emergencia (PR 5: base, perfil y M1; PR 9-API: M3, recepción de kits;
PR 8: M2, llegada de familias).

Namespace ``emergencia_api``. El login es el de la app de campo,
``/api/becas/auth/token/``: un solo token por usuario, y cada recurso con su permiso.
El contrato está en ``docs/internal/contrato-app-emergencia.md``.
"""

from django.urls import path

from programas.api.views_emergencia import (
    CasosEmergenciaView,
    ConsultarPersonaEmergenciaView,
    LocalidadesEmergenciaView,
    MisCasosEmergenciaView,
    PerfilEmergenciaView,
    RaizApiEmergencia,
    SugerirPersonasEmergenciaView,
)
from programas.api.views_emergencia_estadias import (
    CambiarPlazaEstadiaView,
    EgresarEstadiaView,
    MotivosEgresoView,
    PlazasParaCambioView,
)
from programas.api.views_emergencia_kits import (
    EntregaKitDetalleView,
    EntregasDelDispositivoView,
    MisDispositivosEmergenciaView,
    RecibirEntregaKitView,
)
from programas.api.views_emergencia_llegadas import (
    AceptarDerivacionView,
    AlojarFamiliaView,
    BuscarFamiliaView,
    CancelarIngresoView,
    CerrarConDiferenciaView,
    ConfirmarIntegranteView,
    DerivacionDetalleView,
    DerivacionesPorRecibirView,
    IntegrantesView,
    IntegranteView,
    PlazasDelDispositivoView,
    QuitarIntegranteView,
    RechazarDerivacionView,
)
from programas.api.views_emergencia_plazas import (
    EdificiosDeLaAppView,
    EstadiasDelEdificioView,
    MapaDelEdificioView,
)
from programas.api.views_emergencia_plazas_acciones import (
    FueraDeServicioView,
    LiberarPlazaView,
    PrestarPlazaView,
    ReservarPlazaView,
    VolverAServicioView,
)
from programas.api.views_emergencia_sin_derivacion import AvisarALaMesaView, IngresoDirectoView

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
    path("personas/sugerir/", SugerirPersonasEmergenciaView.as_view(), name="personas-sugerir"),
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
    path(
        "dispositivos/<int:dispositivo_id>/derivaciones/",
        DerivacionesPorRecibirView.as_view(),
        name="dispositivo-derivaciones",
    ),
    path("dispositivos/<int:dispositivo_id>/plazas/", PlazasDelDispositivoView.as_view(), name="dispositivo-plazas"),
    path("derivaciones/<int:pk>/", DerivacionDetalleView.as_view(), name="derivacion-detalle"),
    path("derivaciones/<int:pk>/aceptar/", AceptarDerivacionView.as_view(), name="derivacion-aceptar"),
    path("derivaciones/<int:pk>/rechazar/", RechazarDerivacionView.as_view(), name="derivacion-rechazar"),
    path("casos/<int:pk>/integrantes/", IntegrantesView.as_view(), name="caso-integrantes"),
    path("casos/<int:pk>/integrantes/<int:n>/", IntegranteView.as_view(), name="caso-integrante"),
    path(
        "casos/<int:pk>/integrantes/<int:n>/confirmar/",
        ConfirmarIntegranteView.as_view(),
        name="caso-integrante-confirmar",
    ),
    path("casos/<int:pk>/integrantes/<int:n>/quitar/", QuitarIntegranteView.as_view(), name="caso-integrante-quitar"),
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
    # Egreso por persona y cambio de plaza (Cambio 597): cualquier dispositivo, con el alcance de la web.
    path("motivos-egreso/", MotivosEgresoView.as_view(), name="motivos-egreso"),
    path("estadias/<int:pk>/egresar/", EgresarEstadiaView.as_view(), name="estadia-egresar"),
    path("estadias/<int:pk>/plazas-para-cambio/", PlazasParaCambioView.as_view(), name="estadia-plazas-para-cambio"),
    path("estadias/<int:pk>/cambiar-plaza/", CambiarPlazaEstadiaView.as_view(), name="estadia-cambiar-plaza"),
    # Acciones de cama (Cambio 598): reservar, prestar, liberar, sacar de servicio y volver a servicio.
    path("plazas/<int:pk>/reservar/", ReservarPlazaView.as_view(), name="plaza-reservar"),
    path("plazas/<int:pk>/prestar/", PrestarPlazaView.as_view(), name="plaza-prestar"),
    path("plazas/<int:pk>/liberar/", LiberarPlazaView.as_view(), name="plaza-liberar"),
    path("plazas/<int:pk>/fuera-servicio/", FueraDeServicioView.as_view(), name="plaza-fuera-servicio"),
    path("plazas/<int:pk>/volver-servicio/", VolverAServicioView.as_view(), name="plaza-volver-servicio"),
    # Plazas y estadías (Cambio 596): lectura, para cualquier institución y edificio en el alcance de `dispositivo.ver`.
    path("edificios/", EdificiosDeLaAppView.as_view(), name="edificios"),
    path(
        "dispositivos/<int:dispositivo_id>/edificios/<int:edificio_id>/mapa/",
        MapaDelEdificioView.as_view(),
        name="edificio-mapa",
    ),
    path(
        "dispositivos/<int:dispositivo_id>/edificios/<int:edificio_id>/estadias/",
        EstadiasDelEdificioView.as_view(),
        name="edificio-estadias",
    ),
]
