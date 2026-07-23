from django.urls import path

from programas.views import dispositivos_config as cfg

app_name = "dispositivos"

urlpatterns = [
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
