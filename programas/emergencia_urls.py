from django.urls import path

from programas.views import emergencia as mesa
from programas.views import emergencia_config as config

app_name = "emergencia"

# Módulo Emergencia: la mesa (bandeja E2, ficha E3 y «Nuevo caso») y la configuración (E7).
# El tablero y las entregas de kits se suman en los PRs siguientes. El segmento de E7 es
# `config/` y no `configuracion/` a propósito: el sidebar enciende el grupo «Configuración»
# con cualquier ruta que contenga esa palabra.
urlpatterns = [
    path("config/", config.ConfiguracionEmergenciaView.as_view(), name="configuracion"),
    path("casos/", mesa.BandejaCasosView.as_view(), name="bandeja"),
    path("casos/nuevo/", mesa.NuevoCasoView.as_view(), name="caso_nuevo"),
    path("casos/<int:pk>/", mesa.CasoDetalleView.as_view(), name="caso_detalle"),
    path("casos/<int:pk>/tomar/", mesa.TomarCasoView.as_view(), name="caso_tomar"),
    path("casos/<int:pk>/soltar/", mesa.SoltarCasoView.as_view(), name="caso_soltar"),
    path("casos/<int:pk>/reasignar/", mesa.ReasignarCasoView.as_view(), name="caso_reasignar"),
    path("casos/<int:pk>/prioridad/", mesa.CambiarPrioridadView.as_view(), name="caso_prioridad"),
    path("casos/<int:pk>/contacto/", mesa.ContactoCasoView.as_view(), name="caso_contacto"),
    path("casos/<int:pk>/derivar/", mesa.DerivarCasoView.as_view(), name="caso_derivar"),
    path("casos/<int:pk>/cancelar-derivacion/", mesa.CancelarDerivacionView.as_view(), name="caso_cancelar_derivacion"),
    path("casos/<int:pk>/cerrar/", mesa.CerrarCasoView.as_view(), name="caso_cerrar"),
]
