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

Estos dos helpers son el sobre único al que migran las vistas. La pieza y sus
tests son de la Ola R; **la migración es de la Ola 7**, app por app, empezando
por `programas/views/diseno.py` y `legajos/views/contactos_api.py`.
`core/tests/test_contrato_errores_ajax.py` congela lo que cada consumidor lee
hoy, para que la migración no se lleve puesto un front.

Forma del sobre, elegida **code-first** sobre la que ya devuelve el constructor
(`{"ok": False, "message": ..., "errores": [...]}`), que es la única de las cinco
que trae a la vez la bandera, el motivo legible y el detalle por campo:

    {"ok": False, "message": "<motivo para la persona>", "errores": [...]}
    {"ok": True, ...datos}

La clave del detalle es `errores` y no `errors` (así está escrita en
`diseno.py`): el idioma del repo es el español y cambiarla ahora sería
exactamente el renombre silencioso que la ficha vino a evitar.

**Migrar es sumar, no reemplazar.** El front instalado no se despliega junto con
el backend: la app de campo es una build en el teléfono del territorial
(`Chaco-mobile@a66c2d3`, `buildResponseError` lee `detail`, `error` y
`non_field_errors`) y una pantalla del backoffice puede quedar abierta mientras
sale la release. Por eso `error_json` y `ok_json` aceptan `heredadas=`: las
claves que **algún consumidor ya lee** viajan además de `ok`/`message`, con el
comentario que dice quién las lee. El sobre nuevo es el que se documenta y el
que leen los consumidores nuevos; las heredadas se van cuando se mide que nadie
las lee, no antes.

Hay una trampa de nombres que conviene no pisar: `errores` acá es una **lista de
strings** (y así la lee `becas-dashboard.js:188`), mientras que `errors` —en
`_ajax_js.html`, `users/_alta_rapida_modal.html` y `dispositivos/config/
tipo_detail.html`— es un **diccionario por campo** que el front vuelca en el
formulario. No son la misma clave con otro idioma: son dos contratos distintos.
"""

from django.http import JsonResponse

#: Clave con el motivo legible. La lee `nodo-constructor.js:133`.
CLAVE_MENSAJE = "message"
#: Clave con el detalle (lista de strings). Opcional. **No** es el `errors` por
#: campo que leen `_ajax_js.html` y `_alta_rapida_modal.html`.
CLAVE_ERRORES = "errores"
#: Las dos que pone el sobre y que `heredadas=` no puede pisar.
CLAVES_PROPIAS = frozenset({"ok", CLAVE_MENSAJE})


def _con_heredadas(cuerpo, heredadas):
    """Suma las claves que un consumidor ya lee, sin dejar que pisen el sobre."""
    if not heredadas:
        return cuerpo
    colisiones = CLAVES_PROPIAS & set(heredadas)
    if colisiones:
        raise TypeError(f"`heredadas` no puede redefinir {sorted(colisiones)}: las pone el sobre.")
    return {**cuerpo, **heredadas}


def error_json(mensaje, *, status=400, errores=None, heredadas=None):
    """Respuesta de error del backoffice: `{"ok": False, "message", "errores"}`.

    `errores` se omite cuando no hay detalle, para no obligar al front a
    distinguir «sin detalle» de «lista vacía».

    `heredadas` son claves adicionales que algún consumidor **ya lee** y que la
    migración conserva (`{"success": False, "error": mensaje}` en legajos). Van
    al final para que se lean como lo que son: compatibilidad, no contrato nuevo.
    """
    cuerpo = {"ok": False, CLAVE_MENSAJE: mensaje}
    if errores:
        cuerpo[CLAVE_ERRORES] = list(errores)
    return JsonResponse(_con_heredadas(cuerpo, heredadas), status=status)


def ok_json(*, heredadas=None, **datos):
    """Respuesta exitosa: `{"ok": True, ...datos}`.

    `ok` va primero y no se puede pisar con un kwarg: una vista que devuelva
    `ok=False` con status 200 es justo el caso que el front no sabe leer.
    """
    if "ok" in datos:
        raise TypeError("`ok` lo pone `ok_json`: para un error usá `error_json`.")
    return JsonResponse(_con_heredadas({"ok": True, **datos}, heredadas))
