"""Mensajes que las vistas de Legajos devuelven al cliente.

Vive aparte para que las vistas no tengan que importarse entre ellas solo por
una constante (RED-79: las aristas vista→vista no tienen ratchet).
"""

#: Lo único que ve el cliente cuando algo falla por dentro. Antes las APIs de
#: Legajos devolvían ``str(exc)`` con HTTP 200: el front lo mostraba como si
#: fuera un mensaje de negocio y, de paso, publicaba rutas y nombres de tabla
#: (SEC-10/A3-17, auditoría oct-2026). El detalle va al log con traza.
ERROR_GENERICO = "No se pudo completar la operación. Probá de nuevo."
