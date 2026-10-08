"""SEC-26 · cierre de la sesión de la app de campo, **a pedido**.

`rest_framework.authtoken` emite un token sin vencimiento y
`Token.objects.get_or_create` devuelve siempre el mismo, así que un token
filtrado del teléfono (una copia de seguridad, un celular prestado, un
`adb backup`) sirve hasta que alguien lo borre. Borrarlo es esto.

**Por qué no lo hace sola la clave.** La primera versión colgaba la revocación de
un `post_save(User)`: cambiar la clave —por cualquiera de los cuatro caminos—
borraba el token. Contra la app instalada (`Chaco-mobile @ a66c2d3`) eso deja
varados los relevamientos que el teléfono todavía no sincronizó: ante un 401 la
app marca la operación `FAILED_PERMANENT` (`relevamientoService.js:1487`, `:1411`,
`:1563`) y no la reintenta nunca más, ni después de volver a loguearse. Un
territorial al que el admin le resetea la clave perdía el trabajo de la jornada
sin que nadie se entere. Así que el cambio de clave **ya no toca el token** —las
sesiones web sí se cierran, como siempre— y la revocación es una acción explícita
del ABM, para cuando el teléfono se perdió o la clave se filtró: ahí perder lo no
sincronizado es el mal menor y quien aprieta el botón lo decide avisado.

La revocación automática vuelve cuando haya un release de `Chaco-mobile` que
reintente o re-loguee ante un 401.
"""


def revocar_tokens_de_la_app(user):
    """Borra los tokens de la app de campo del usuario. Devuelve cuántos borró.

    Import tardío: `authtoken` es una app de DRF y este módulo lo importan vistas
    que se cargan temprano.
    """
    from rest_framework.authtoken.models import Token

    borrados, _ = Token.objects.filter(user=user).delete()
    return borrados
