"""Dispositivos de ubicación reservada (RN-009-13, T9b del tablero de Dispositivos).

Un tipo con ``TipoDispositivo.ubicacion_reservada`` agrupa dispositivos de protección:
sus coordenadas **no llegan al template** y no se nombran en listados ordenados por
distancia o por tensión. **Siguen sumando** en los totales (camas libres, capacidad de la
red, alertas agregadas): esos bloques no muestran dónde quedan.

Es la definición única que usan los puntos del mapa, «más tensionados», las camas cercanas y
AE-5 de E8 (``services.situacion_emergencia`` y ``services.alertas_situacion_emergencia``) y,
cuando llegue, el tablero de Dispositivos.
El filtro se hace acá, en el servidor; nunca con CSS.

No se aplica al panel «Derivar» de la mesa (``selectors.emergencia.dispositivos_para_derivar``):
la mesa (``emergencia.operar``) es la que tiene que poder derivar una familia a un refugio
de protección, y el análisis 009 acepta que E4 se lo muestre.
"""

from django.db.models import Q


def q_sin_ubicacion_reservada(prefijo=""):
    """``Q`` que deja afuera los dispositivos cuyo tipo es de ubicación reservada.

    ``prefijo`` es el camino hasta el dispositivo desde el modelo que se filtra
    (``"dispositivo__"`` para una derivación, vacío para ``Dispositivo``).
    """

    return Q(**{f"{prefijo}tipo__ubicacion_reservada": False})


def separar_por_ubicacion_reservada(elementos, *, dispositivo=None):
    """``(publicables, reservados)`` en el orden de entrada. Sin consultas.

    ``elementos`` son dispositivos o filas que los contienen (la red de E8, por ejemplo, son
    ``selectors.emergencia_tablero.DispositivoDeLaRed``); ``dispositivo`` extrae de cada
    elemento lo que tiene el ``tipo`` (por omisión, el elemento mismo). Con el
    ``select_related("tipo")`` de la red no suma consultas. Los ``publicables`` se pueden
    dibujar y nombrar; los ``reservados`` solo se suman («N camas en dispositivos de
    ubicación reservada»), sin nombre ni orden.
    """

    extraer = dispositivo or (lambda elemento: elemento)
    publicables, reservados = [], []
    for elemento in elementos:
        (reservados if extraer(elemento).tipo.ubicacion_reservada else publicables).append(elemento)
    return publicables, reservados
