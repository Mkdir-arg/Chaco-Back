from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views
from .views import programas as views_programas

app_name = "configuracion"

urlpatterns = [
    # Provincias
    path("provincias/", login_required(views.ProvinciaListView.as_view()), name="provincias"),
    path("provincias/crear/", login_required(views.ProvinciaCreateView.as_view()), name="provincia_crear"),
    path("provincias/<int:pk>/editar/", login_required(views.ProvinciaUpdateView.as_view()), name="provincia_editar"),
    path(
        "provincias/<int:pk>/eliminar/", login_required(views.ProvinciaDeleteView.as_view()), name="provincia_eliminar"
    ),
    # Municipios
    path("municipios/", login_required(views.MunicipioListView.as_view()), name="municipios"),
    path("municipios/crear/", login_required(views.MunicipioCreateView.as_view()), name="municipio_crear"),
    path("municipios/<int:pk>/editar/", login_required(views.MunicipioUpdateView.as_view()), name="municipio_editar"),
    path(
        "municipios/<int:pk>/eliminar/", login_required(views.MunicipioDeleteView.as_view()), name="municipio_eliminar"
    ),
    # Localidades
    path("localidades/", login_required(views.LocalidadListView.as_view()), name="localidades"),
    path("localidades/crear/", login_required(views.LocalidadCreateView.as_view()), name="localidad_crear"),
    path("localidades/<int:pk>/editar/", login_required(views.LocalidadUpdateView.as_view()), name="localidad_editar"),
    path(
        "localidades/<int:pk>/eliminar/", login_required(views.LocalidadDeleteView.as_view()), name="localidad_eliminar"
    ),
    # Secretarías y Subsecretarías
    path("secretarias/", login_required(views.SecretariaListView.as_view()), name="secretarias"),
    path("secretarias/crear/", login_required(views.SecretariaCreateView.as_view()), name="secretaria_crear"),
    path(
        "secretarias/<int:pk>/editar/", login_required(views.SecretariaUpdateView.as_view()), name="secretaria_editar"
    ),
    path(
        "secretarias/<int:pk>/eliminar/",
        login_required(views.SecretariaDeleteView.as_view()),
        name="secretaria_eliminar",
    ),
    path("subsecretarias/", login_required(views.SubsecretariaListView.as_view()), name="subsecretarias"),
    path("subsecretarias/crear/", login_required(views.SubsecretariaCreateView.as_view()), name="subsecretaria_crear"),
    path(
        "subsecretarias/<int:pk>/editar/",
        login_required(views.SubsecretariaUpdateView.as_view()),
        name="subsecretaria_editar",
    ),
    path(
        "subsecretarias/<int:pk>/eliminar/",
        login_required(views.SubsecretariaDeleteView.as_view()),
        name="subsecretaria_eliminar",
    ),
    # Programas — wizard de configuración
    path("programas/", views_programas.programa_list, name="programas"),
    path("programas/nuevo/paso1/", views_programas.programa_wizard_paso1, name="programa_wizard_paso1"),
    path("programas/nuevo/paso2/", views_programas.programa_wizard_paso2, name="programa_wizard_paso2"),
    path("programas/nuevo/paso3/", views_programas.programa_wizard_paso3, name="programa_wizard_paso3"),
    path("programas/nuevo/paso4/", views_programas.programa_wizard_paso4, name="programa_wizard_paso4"),
    path("programas/<int:pk>/editar/paso1/", views_programas.programa_editar_paso1, name="programa_editar_paso1"),
    path("programas/<int:pk>/editar/paso2/", views_programas.programa_editar_paso2, name="programa_editar_paso2"),
    path("programas/<int:pk>/editar/paso3/", views_programas.programa_editar_paso3, name="programa_editar_paso3"),
    path("programas/<int:pk>/editar/paso4/", views_programas.programa_editar_paso4, name="programa_editar_paso4"),
    path("programas/<int:pk>/estado/", views_programas.programa_cambiar_estado, name="programa_cambiar_estado"),
]
