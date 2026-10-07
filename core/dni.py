"""La regla de DNI del sistema, escrita una sola vez (RED-48).

«DNI válido» estaba implementado **ocho** veces con **cuatro** reglas de largo: 7 u 8
en el padrón, los dos formularios del portal público, el serializer de la app, el
buscador de Dispositivos y la consulta a RENAPER de Legajos; exactamente 8 en
`extract_dni_from_cuit`; hasta 10 en el armado del alta a SIIS; y de 6 a 9 en el
registro del portal ciudadano. La diferencia no la veía nadie, porque las dos puntas
callan: el padrón **descarta la fila en silencio** (la suma a `rechazadas`) y
`siis_envio` mandaba a SIIS —que no tiene baja— lo que los formularios rechazaban.

Vive en `core/` y no en `programas/services/padron.py`, que es donde nació, porque
`legajos` y `portal` también tienen puertas de DNI y `legajos.models` no puede
importar `programas` sin cerrar un ciclo. `padron` la reexporta: todo el código que
ya importaba `normalizar_dni` de ahí sigue andando.

`core/tests/test_regla_dni.py` es el ratchet: recorre el código productivo y falla si
aparece una novena regla escrita a mano.
"""

from __future__ import annotations

from decimal import Decimal

#: Largos que el sistema acepta como DNI.
LARGOS_DNI_VALIDOS = (7, 8)

#: El texto exacto que ve la persona cuando el DNI no pasa. Lo comparten las puertas
#: para que el mismo rechazo no se explique de ocho maneras distintas.
MENSAJE_DNI_INVALIDO = "Ingresá un DNI válido de 7 u 8 dígitos, sin puntos."


def normalizar_dni(valor):
    """El DNI reducido a sus dígitos, venga como venga."""
    # openpyxl entrega floats (30123456.0) en Excels exportados desde CSV,
    # pandas o LibreOffice, y el driver de MySQL entrega Decimal cuando la
    # columna es DECIMAL (es el caso de ``ciudadanos_renaper``, que crea un
    # script externo); sin este cast el DNI queda con un 0 de más y no cruza
    # con nada (RED-47). Un NaN o un decimal con parte fraccionaria siguen
    # yendo por texto en vez de reventar.
    if isinstance(valor, (float, Decimal)):
        try:
            entero = int(valor)
        except (ValueError, ArithmeticError):
            entero = None
        if entero is not None and valor == entero:
            valor = entero
    return "".join(ch for ch in str(valor or "") if ch.isdigit())


def dni_valido(valor):
    """¿``valor`` es un DNI que el sistema acepta? Normaliza antes de medir.

    La **única** regla de largo del repo. Recibe lo que haya —texto con puntos,
    ``float`` de openpyxl, ``Decimal`` del driver de MySQL, ``None``— porque
    `normalizar_dni` ya sabe lidiar con todo eso.
    """
    return len(normalizar_dni(valor)) in LARGOS_DNI_VALIDOS
