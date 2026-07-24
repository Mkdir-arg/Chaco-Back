from django.urls import path

from programas.views import dispositivos_config as cfg
from programas.views import dispositivos_legajo as legajo

app_name = "dispositivos"

urlpatterns = [
    path("", legajo.DispositivoListView.as_view(), name="lista"),
    path("nuevo/", legajo.DispositivoCreateView.as_view(), name="crear"),
    path("buscar-duplicados/", legajo.DispositivoDuplicateSearchView.as_view(), name="buscar_duplicados"),
    path("<int:pk>/enviar-validacion/", legajo.DispositivoEnviarValidacionView.as_view(), name="enviar_validacion"),
    path("<int:pk>/validar/", legajo.DispositivoValidarView.as_view(), name="validar"),
    path("<int:pk>/observar/", legajo.DispositivoObservarView.as_view(), name="observar"),
    path("<int:pk>/rechazar/", legajo.DispositivoRechazarView.as_view(), name="rechazar"),
    path("<int:pk>/inactivar/", legajo.DispositivoInactivarView.as_view(), name="inactivar"),
    path("<int:pk>/cerrar/", legajo.DispositivoCerrarView.as_view(), name="cerrar"),
    path("<int:pk>/camas/agregar/", legajo.CamasCreateView.as_view(), name="camas_agregar"),
    path("camas/<int:pk>/editar/", legajo.CamaUpdateView.as_view(), name="cama_editar"),
    path("<int:pk>/", legajo.DispositivoDetailView.as_view(), name="detalle"),
    path("<int:pk>/editar/", legajo.DispositivoUpdateView.as_view(), name="editar"),
    path("config/", cfg.TipoDispositivoListView.as_view(), name="tipos"),
    path("config/nuevo/", cfg.TipoDispositivoCreateView.as_view(), name="tipo_crear"),
    path("config/<int:pk>/", cfg.TipoDispositivoDetailView.as_view(), name="tipo_detalle"),
    path("config/<int:pk>/editar/", cfg.TipoDispositivoUpdateView.as_view(), name="tipo_editar"),
    path("config/<int:pk>/toggle/", cfg.TipoDispositivoToggleView.as_view(), name="tipo_toggle"),
    path(
        "config/<int:tipo_pk>/campos/nuevo/",
        cfg.CampoTipoDispositivoCreateView.as_view(),
        name="campo_crear",
    ),
    path("config/campos/<int:pk>/editar/", cfg.CampoTipoDispositivoUpdateView.as_view(), name="campo_editar"),
    path("config/campos/<int:pk>/eliminar/", cfg.CampoTipoDispositivoDeleteView.as_view(), name="campo_eliminar"),
]
