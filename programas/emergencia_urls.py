from django.urls import path

from programas.views import emergencia as mesa
from programas.views import emergencia_config as config
from programas.views import emergencia_kits as kits
from programas.views import emergencia_situacion as situacion
from programas.views import emergencia_tablero as tablero

app_name = "emergencia"

# Módulo Emergencia: la mesa (bandeja E2, ficha E3 y «Nuevo caso») y la configuración, partida en
# «Insumos» y «Plazos de atención» (Cambio 578).
# Las entregas de kits (E4, E5 y la recepción en el dispositivo) van abajo; el tablero (E1) es del supervisor. El segmento de E7 es
# `config/` y no `configuracion/` a propósito: el sidebar enciende el grupo «Configuración»
# con cualquier ruta que contenga esa palabra.
urlpatterns = [
    # La pantalla única de antes: quien la tenga guardada llega a Insumos. El nombre se conserva.
    path("config/", config.ConfiguracionVieja.as_view(), name="configuracion"),
    path("config/insumos/", config.InsumosEmergenciaView.as_view(), name="insumos"),
    path(
        "config/insumos/<int:pk>/desactivar/",
        config.CambiarEstadoInsumoView.as_view(activo=False),
        name="insumo_desactivar",
    ),
    path(
        "config/insumos/<int:pk>/activar/",
        config.CambiarEstadoInsumoView.as_view(activo=True),
        name="insumo_activar",
    ),
    path("config/plazos/", config.PlazosEmergenciaView.as_view(), name="plazos"),
    path("tablero/", tablero.TableroView.as_view(), name="tablero"),
    # E8 «Situación» (análisis 009): el tablero estratégico, con `ver_situacion` o `supervisar`.
    path("situacion/", situacion.SituacionView.as_view(), name="situacion"),
    path("casos/", mesa.BandejaCasosView.as_view(), name="bandeja"),
    path("casos/nuevo/", mesa.NuevoCasoView.as_view(), name="caso_nuevo"),
    path("casos/personas-sugeridas/", mesa.PersonasSugeridasMesaView.as_view(), name="personas_sugeridas"),
    path("casos/<int:pk>/", mesa.CasoDetalleView.as_view(), name="caso_detalle"),
    path("casos/<int:pk>/tomar/", mesa.TomarCasoView.as_view(), name="caso_tomar"),
    path("casos/<int:pk>/soltar/", mesa.SoltarCasoView.as_view(), name="caso_soltar"),
    path("casos/<int:pk>/reasignar/", mesa.ReasignarCasoView.as_view(), name="caso_reasignar"),
    path("casos/<int:pk>/prioridad/", mesa.CambiarPrioridadView.as_view(), name="caso_prioridad"),
    path("casos/<int:pk>/contacto/", mesa.ContactoCasoView.as_view(), name="caso_contacto"),
    path("casos/<int:pk>/derivar/", mesa.DerivarCasoView.as_view(), name="caso_derivar"),
    path("casos/<int:pk>/ubicar-domicilio/", mesa.UbicarDomicilioView.as_view(), name="caso_ubicar_domicilio"),
    path("casos/<int:pk>/cancelar-derivacion/", mesa.CancelarDerivacionView.as_view(), name="caso_cancelar_derivacion"),
    path("casos/<int:pk>/cancelar-ingreso/", mesa.CancelarIngresoMesaView.as_view(), name="caso_cancelar_ingreso"),
    path("casos/<int:pk>/cerrar/", mesa.CerrarCasoView.as_view(), name="caso_cerrar"),
    # Entregas de kits (etapa 4): E4 (listado y «Nueva entrega» en una sola pantalla) y E5 (detalle).
    path("entregas/", kits.EntregasListView.as_view(), name="entregas"),
    path("entregas/nueva/", kits.NuevaEntregaView.as_view(), name="entrega_nueva"),
    # La URL del paso 2 del asistente viejo: redirige a la pantalla única (no rompe un enlace guardado).
    path("entregas/nueva/<int:dispositivo>/", kits.NuevaEntregaItemsView.as_view(), name="entrega_nueva_items"),
    path("entregas/<int:pk>/", kits.EntregaDetalleView.as_view(), name="entrega_detalle"),
    path(
        "entregas/<int:pk>/aceptar-diferencia/", kits.AceptarDiferenciaView.as_view(), name="entrega_aceptar_diferencia"
    ),
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
