from django.urls import path

from programas.views import dispositivos_config as cfg
from programas.views import dispositivos_legajo as legajo
from programas.views import reportes

app_name = "dispositivos"

# Las rutas del circuito operativo —admisión, egreso, traslado, lista de espera,
# parte diario y camas— se fueron con los modelos que leían (`Cama`, `Admision`,
# `EsperaAdmision`, `RegistroDiario`). Las repone el MVP v2 con `Sector`/`Plaza`,
# `Estadia` y `Turno`; mientras tanto el legajo institucional del dispositivo y la
# configuración de tipos siguen en pie.
urlpatterns = [
    path("", legajo.DispositivoListView.as_view(), name="lista"),
    path("export/<str:reporte>/<str:formato>/", reportes.DispositivoExportView.as_view(), name="exportar"),
    path("nuevo/", legajo.DispositivoCreateView.as_view(), name="crear"),
    path("buscar-duplicados/", legajo.DispositivoDuplicateSearchView.as_view(), name="buscar_duplicados"),
    path("<int:pk>/enviar-validacion/", legajo.DispositivoEnviarValidacionView.as_view(), name="enviar_validacion"),
    path("<int:pk>/validar/", legajo.DispositivoValidarView.as_view(), name="validar"),
    path("<int:pk>/observar/", legajo.DispositivoObservarView.as_view(), name="observar"),
    path("<int:pk>/rechazar/", legajo.DispositivoRechazarView.as_view(), name="rechazar"),
    path("<int:pk>/inactivar/", legajo.DispositivoInactivarView.as_view(), name="inactivar"),
    path("<int:pk>/cerrar/", legajo.DispositivoCerrarView.as_view(), name="cerrar"),
    path("<int:pk>/", legajo.DispositivoDetailView.as_view(), name="detalle"),
    path("<int:pk>/editar/", legajo.DispositivoUpdateView.as_view(), name="editar"),
    path("config/", cfg.TipoDispositivoListView.as_view(), name="tipos"),
    path("config/nuevo/", cfg.TipoDispositivoCreateView.as_view(), name="tipo_crear"),
    path("config/<int:pk>/", cfg.TipoDispositivoDetailView.as_view(), name="tipo_detalle"),
    path("config/<int:pk>/editar/", cfg.TipoDispositivoUpdateView.as_view(), name="tipo_editar"),
    path("config/<int:pk>/toggle/", cfg.TipoDispositivoToggleView.as_view(), name="tipo_toggle"),
]
