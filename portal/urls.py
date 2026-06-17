from django.urls import path

from .views.public import (
    PortalHomeView,
)
from .views.ciudadano import (
    CiudadanoLoginView,
    CiudadanoLogoutView,
    CiudadanoPasswordResetCompleteView,
    CiudadanoPasswordResetConfirmView,
    CiudadanoPasswordResetDoneView,
    CiudadanoPasswordResetView,
    ciudadano_cambio_email,
    ciudadano_cambio_password,
    ciudadano_confirmar_email,
    ciudadano_consulta_detalle,
    ciudadano_enviar_mensaje,
    ciudadano_mi_perfil,
    ciudadano_mis_consultas,
    ciudadano_mis_datos,
    ciudadano_mis_programas,
    ciudadano_nueva_consulta,
    ciudadano_programa_detalle,
    RegistroStep1View,
    RegistroStep2View,
)

app_name = 'portal'

urlpatterns = [
    path('', PortalHomeView.as_view(), name='home'),
    # Portal ciudadano
    path('mi-perfil/login/', CiudadanoLoginView.as_view(), name='ciudadano_login'),
    path('mi-perfil/logout/', CiudadanoLogoutView.as_view(), name='ciudadano_logout'),
    path('mi-perfil/registro/', RegistroStep1View.as_view(), name='ciudadano_registro_step1'),
    path('mi-perfil/registro/verificar/', RegistroStep2View.as_view(), name='ciudadano_registro_step2'),
    path('mi-perfil/', ciudadano_mi_perfil, name='ciudadano_mi_perfil'),
    path('mi-perfil/programas/', ciudadano_mis_programas, name='ciudadano_mis_programas'),
    path('mi-perfil/programas/<int:pk>/', ciudadano_programa_detalle, name='ciudadano_programa_detalle'),
    path('mi-perfil/consultas/', ciudadano_mis_consultas, name='ciudadano_mis_consultas'),
    path('mi-perfil/consultas/nueva/', ciudadano_nueva_consulta, name='ciudadano_nueva_consulta'),
    path('mi-perfil/consultas/<int:pk>/', ciudadano_consulta_detalle, name='ciudadano_consulta_detalle'),
    path('mi-perfil/consultas/<int:pk>/enviar/', ciudadano_enviar_mensaje, name='ciudadano_enviar_mensaje'),
    path('mi-perfil/mis-datos/', ciudadano_mis_datos, name='ciudadano_mis_datos'),
    path('mi-perfil/mis-datos/cambio-email/', ciudadano_cambio_email, name='ciudadano_cambio_email'),
    path('mi-perfil/mis-datos/confirmar-email/<uuid:token>/', ciudadano_confirmar_email, name='ciudadano_confirmar_email'),
    path('mi-perfil/mis-datos/cambio-password/', ciudadano_cambio_password, name='ciudadano_cambio_password'),
    path('mi-perfil/password/reset/', CiudadanoPasswordResetView.as_view(), name='ciudadano_password_reset'),
    path('mi-perfil/password/reset/enviado/', CiudadanoPasswordResetDoneView.as_view(), name='ciudadano_password_reset_done'),
    path('mi-perfil/password/reset/<uidb64>/<token>/', CiudadanoPasswordResetConfirmView.as_view(), name='ciudadano_password_reset_confirm'),
    path('mi-perfil/password/reset/completado/', CiudadanoPasswordResetCompleteView.as_view(), name='ciudadano_password_reset_complete'),
]
