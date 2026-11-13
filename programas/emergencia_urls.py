from django.urls import path

from programas.views import emergencia as mesa
from programas.views import emergencia_config as config
from programas.views import emergencia_kits as kits
from programas.views import emergencia_tablero as tablero

app_name = "emergencia"

# Módulo Emergencia: la mesa (bandeja E2, ficha E3 y «Nuevo caso») y la configuración (E7).
# Las entregas de kits (E4, E5 y la recepción en el dispositivo) van abajo; el tablero (E1) es del supervisor. El segmento de E7 es
# `config/` y no `configuracion/` a propósito: el sidebar enciende el grupo «Configuración»
# con cualquier ruta que contenga esa palabra.
urlpatterns = [
    path("config/", config.ConfiguracionEmergenciaView.as_view(), name="configuracion"),
    path("tablero/", tablero.TableroView.as_view(), name="tablero"),
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
    # Entregas de kits (etapa 4): E4 (listado y asistente de tres pasos) y E5 (detalle).
    path("entregas/", kits.EntregasListView.as_view(), name="entregas"),
    path("entregas/nueva/", kits.NuevaEntregaDestinoView.as_view(), name="entrega_nueva"),
    path("entregas/nueva/<int:dispositivo>/", kits.NuevaEntregaItemsView.as_view(), name="entrega_nueva_items"),
    path(
        "entregas/nueva/<int:dispositivo>/confirmar/",
        kits.NuevaEntregaConfirmarView.as_view(),
        name="entrega_nueva_confirmar",
    ),
    path("entregas/<int:pk>/", kits.EntregaDetalleView.as_view(), name="entrega_detalle"),
    path("entregas/<int:pk>/en-camino/", kits.MarcarEnCaminoView.as_view(), name="entrega_en_camino"),
    path("entregas/<int:pk>/cancelar/", kits.CancelarEntregaView.as_view(), name="entrega_cancelar"),
    path("entregas/<int:pk>/observar/", kits.ObservarEntregaView.as_view(), name="entrega_observar"),
    # La recepción, dentro del dispositivo: la guardia con `emergencia.recibir_kit` en su Equipo.
    path("dispositivos/<int:dispositivo>/kits/", kits.KitsDelDispositivoView.as_view(), name="dispositivo_kits"),
    path(
        "dispositivos/<int:dispositivo>/kits/<int:pk>/recibir/",
        kits.RecibirKitView.as_view(),
        name="dispositivo_kit_recibir",
    ),
]
