"""El ``Programa`` de un código, cacheado. Una sola pieza para los dos (RED-80).

Becas y Dispositivos resolvían su ``Programa`` con el mismo patrón escrito dos veces
—``autorizacion.programa_becas`` con la clave ``programas:becas``,
``dispositivos.programa_dispositivos`` con ``programas:dispositivos``— pero con guardas
e invalidación distintas: la de Becas la borraba ``seed_becas`` y fallaba *best-effort*
si el cache no respondía; la de Dispositivos **no la borraba nadie**.

Qué rompía eso sin que nadie se entere: durante 300 s todos los pods evalúan el alcance
contra un ``Programa`` que ya no es el que está en la base —un restore que recrea la
fila con otro pk, o el wizard de Configuración, que deja **cambiar el código** de un
programa en el paso 1—. Para Dispositivos eso es «nadie entra a Dispositivos» y se cura
solo; para Becas, ``_programa_o_denegar`` lo convierte en un 403 y falla cerrado
(RED-56). Las dos cosas son invisibles salvo que alguien esté mirando.

Acá hay una clave derivada del código y una invalidación que usan los dos, más la del
wizard: quien **escribe** un ``Programa`` es quien tiene que borrar su clave.
"""

import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

#: Vigencia de la entrada. Es el valor que tenían las dos claves por separado.
VIGENCIA = 300

#: Centinela del memo por request (distingue "no memoizado" de "memoizado como None").
_CACHE_MISS = object()


def clave_de(codigo):
    """``"BECAS"`` → ``"programas:becas"``. Las dos claves históricas salen de acá."""
    return f"programas:{codigo.lower()}"


def programa_por_codigo(codigo, user=None):
    """El ``Programa`` de ese código, o ``None`` si no está sembrado.

    Se consulta en casi todos los checks de autorización, así que se cachea 5 minutos.
    Solo se cachea **cuando existe**: guardar el ``None`` rompería los tests que siembran
    el programa después de la primera consulta, y en producción dejaría el sistema sin
    ese programa durante 300 s por una lectura hecha en el peor momento.

    Con ``user``, además memoiza en el propio objeto durante la request: una sola pantalla
    llegaba a pedir la misma clave siete veces, y en producción cada una es una ida y
    vuelta a Redis más el despickle del ``Programa``. El memo muere con la request, así
    que el ``cache.clear()`` de los tests y :func:`invalidar_programa` siguen surtiendo
    efecto.
    """
    from programas.models import Programa

    if user is not None:
        memo = getattr(user, "_programas_por_codigo", None)
        if memo is None:
            memo = {}
            user._programas_por_codigo = memo
        guardado = memo.get(codigo, _CACHE_MISS)
        if guardado is not _CACHE_MISS:
            return guardado

    clave = clave_de(codigo)
    programa = cache.get(clave)
    if programa is None:
        programa = Programa.objects.filter(codigo=codigo).first()
        if programa is not None:
            cache.set(clave, programa, VIGENCIA)
    if user is not None:
        user._programas_por_codigo[codigo] = programa
    return programa


def invalidar_programa(codigo):
    """Borra la clave cacheada de un programa. **No falla si el cache no responde.**

    La llaman los seeds, que corren en el **arranque del contenedor**, y el wizard de
    Configuración, que es la única pantalla que edita un ``Programa``. Desde OPS-12 los
    dos ambientes servidos usan Redis, así que un Redis inalcanzable hacía que el
    ``cache.delete`` incondicional terminara el bootstrap en exit 1
    (``ConnectionInterrupted``) y el pod quedara en CrashLoopBackOff: un cache caído
    pasaba a impedir el **arranque**, no solo a degradar el servicio.

    Que la invalidación sea *best-effort* es correcto y acotado: lo peor que queda es que
    otro proceso —uno que sí llegue al cache— siga viendo el ``Programa`` anterior hasta
    que venza su TTL. No se toca :func:`programa_por_codigo`: ahí un cache caído **sí**
    tiene que fallar fuerte, porque es un ambiente sirviendo tráfico con la
    infraestructura rota y taparlo sería esconder una caída real.

    Se atrapa ``Exception`` a propósito: el cliente de Redis traduce la falla a su propia
    jerarquía (``redis.exceptions.*``, que ``django_redis`` re-lanza) y acá no se quiere
    acoplar el seed a los tipos de un backend concreto.
    """
    clave = clave_de(codigo)
    try:
        cache.delete(clave)
    except Exception as excepcion:  # noqa: BLE001 — ver el docstring
        logger.warning(
            "No se pudo invalidar la clave %s en el cache (%s): el arranque sigue y la clave vence sola en %s s.",
            clave,
            type(excepcion).__name__,
            VIGENCIA,
        )
