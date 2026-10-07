"""Un solo sobre para las respuestas JSON del backoffice (RED-39).

Al 04/10/2026 las vistas AJAX del backoffice devolvían el motivo del error en
**cinco** claves distintas —`error` (79 usos), `message` (38), `mensaje` (17),
`detail` (14) y `errors` (5)— y cada consumidor del front lee la suya con un
`||` que tapa la diferencia:

    var msg = data.message || 'No se pudo guardar. Recargá la página.';

Normalizar `programas/views/diseno.py` de `message` a `detail` —la convención de
DRF, que parece una mejora— deja al coordinador mirando «No se pudo guardar.
Recargá la página.» en vez del motivo real, sin un solo error en consola ni un
test en rojo.

Estos dos helpers son el sobre único al que migran las vistas. **La migración es
de la Ola 7**, app por app, empezando por `programas/views/diseno.py` y
`legajos/views/contactos_api.py`: acá solo queda la pieza, con su test. Hasta
entonces `core/tests/test_contrato_errores_ajax.py` congela lo que cada
consumidor lee hoy, para que la migración no se lleve puesto un front.

Forma del sobre, elegida **code-first** sobre la que ya devuelve el constructor
(`{"ok": False, "message": ..., "errores": [...]}`), que es la única de las cinco
que trae a la vez la bandera, el motivo legible y el detalle por campo:

    {"ok": False, "message": "<motivo para la persona>", "errores": [...]}
    {"ok": True, ...datos}

La clave del detalle es `errores` y no `errors` (así está escrita en
`diseno.py`): el idioma del repo es el español y cambiarla ahora sería
exactamente el renombre silencioso que la ficha vino a evitar.
"""

from django.http import JsonResponse

#: Clave con el motivo legible. La lee `nodo-constructor.js:133`.
CLAVE_MENSAJE = "message"
#: Clave con el detalle por campo (lista de strings). Opcional.
CLAVE_ERRORES = "errores"


def error_json(mensaje, *, status=400, errores=None):
    """Respuesta de error del backoffice: `{"ok": False, "message", "errores"}`.

    `errores` se omite cuando no hay detalle, para no obligar al front a
    distinguir «sin detalle» de «lista vacía».
    """
    cuerpo = {"ok": False, CLAVE_MENSAJE: mensaje}
    if errores:
        cuerpo[CLAVE_ERRORES] = list(errores)
    return JsonResponse(cuerpo, status=status)


def ok_json(**datos):
    """Respuesta exitosa: `{"ok": True, ...datos}`.

    `ok` va primero y no se puede pisar con un kwarg: una vista que devuelva
    `ok=False` con status 200 es justo el caso que el front no sabe leer.
    """
    if "ok" in datos:
        raise TypeError("`ok` lo pone `ok_json`: para un error usá `error_json`.")
    return JsonResponse({"ok": True, **datos})
