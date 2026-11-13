"""E6 · «Emergencia · Llegadas»: las rutas de la guardia del dispositivo (etapa 3 de Emergencia).

Cuelgan de ``/dispositivos/<pk>/emergencia/…`` y del namespace ``dispositivos``, no del de
``emergencia``: son pantallas **del dispositivo**, se abren con ``dispositivo.admitir`` y el
alcance del Equipo (RU-8), y contestan 404 sin alcance (plan C2). El namespace ``emergencia``
es el de la mesa, que se abre con las capacidades del programa EMERGENCIA.

Van en un módulo aparte para que sumar otra pantalla de Emergencia al dispositivo (la
recepción de kits) no toque esta lista. ``programas.dispositivos_urls`` las incluye.
"""

from django.urls import path

from programas.views import emergencia_dispositivo as llegadas

BASE = "<int:pk>/emergencia/llegadas/"
CASO = f"{BASE}casos/<int:caso_pk>/"

urlpatterns = [
    path(BASE, llegadas.LlegadasView.as_view(), name="emergencia_llegadas"),
    path(
        f"{BASE}derivaciones/<int:derivacion_pk>/aceptar/",
        llegadas.AceptarDerivacionView.as_view(),
        name="emergencia_aceptar",
    ),
    path(
        f"{BASE}derivaciones/<int:derivacion_pk>/rechazar/",
        llegadas.RechazarDerivacionView.as_view(),
        name="emergencia_rechazar",
    ),
    path(CASO, llegadas.IntegrantesView.as_view(), name="emergencia_integrantes"),
    path(f"{CASO}integrantes/agregar/", llegadas.AgregarIntegranteView.as_view(), name="emergencia_agregar"),
    path(f"{CASO}integrantes/<int:orden>/", llegadas.FichaIntegranteView.as_view(), name="emergencia_ficha"),
    path(f"{CASO}integrantes/<int:orden>/cama/", llegadas.ElegirCamaView.as_view(), name="emergencia_cama"),
    path(f"{CASO}alojar/", llegadas.FamiliaAlojadaView.as_view(), name="emergencia_alojar"),
    path(f"{CASO}diferencia/", llegadas.CerrarConDiferenciaView.as_view(), name="emergencia_diferencia"),
    path(f"{CASO}cancelar/", llegadas.CancelarIngresoView.as_view(), name="emergencia_cancelar"),
    path(f"{BASE}avisar/", llegadas.AvisarALaMesaView.as_view(), name="emergencia_avisar"),
    # Ingreso directo (decisión 4 del PM): al final y en su propia vista, para poder sacarlo solo.
    path(f"{BASE}ingreso-directo/", llegadas.IngresoDirectoView.as_view(), name="emergencia_ingreso_directo"),
]
