"""RED-51 · Las claves cacheadas de la home y **qué modelo mueve cada una**.

Antes de esto había dos funciones llamadas `invalidate_dashboard_cache` —una en
`dashboard/utils.py` con cinco claves, otra en `core/performance/cache_utils.py` con dos
y cableada por señales— y un receiver colgado del modelo equivocado: `stats_legajos` se
borraba al guardar un `LegajoAtencion`, pero esa clave la escribe `contar_legajos()`, que
agrega sobre `InscripcionPrograma`. Una inscripción nueva no refrescaba nada y la home
mostraba el número viejo hasta que expirara el TTL (300 s en producción, donde el cache
es Redis compartido); `alertas_activas` no la borraba nadie.

Los receivers que consumen esta tabla están en `dashboard/signals/cache.py`. La dirección
de la dependencia es una sola —`dashboard` usa la plomería de `core`, nunca al revés—,
que es lo que evita el ciclo de import que mide el ratchet de RED-79.

Lo que este módulo aporta es **una sola** tabla: clave → qué consulta la escribe → qué
modelo la invalida. Agregar un contador a la home es agregar una fila acá y nada más; y
la limpieza de OPS-10 ya no puede «deduplicar» dos funciones homónimas perdiendo claves,
porque hay una.

Por qué se invalida por modelo y no todo junto: un `save()` de `User` no cambia cuántos
ciudadanos hay, y borrar de más obliga a la home a recalcular lo que no cambió. El caso
medido está en PERF-16 (el cruce del padrón llegó a mandar 26.668 `DEL`).
"""

from django.utils import timezone

from core.performance.cache_utils import invalidar_tras_commit, invalidate_cache_keys

#: Cuántos `User` hay (`dashboard.utils.contar_usuarios`).
CLAVE_USUARIOS = "contar_usuarios"
#: Cuántos `Ciudadano` hay (`dashboard.utils.contar_ciudadanos`).
CLAVE_CIUDADANOS = "contar_ciudadanos"
#: Total y activos de **`InscripcionPrograma`**, pese al nombre
#: (`dashboard.utils.contar_legajos`). El nombre es histórico y se conserva: lo lee la
#: copia vieja del inicio (`dashboard.views.home.DashboardView`, RED-78).
CLAVE_STATS_LEGAJOS = "stats_legajos"
#: Total y activos de `LegajoAtencion` (`dashboard.utils.contar_legajos_atencion`), que
#: es lo que dice la tarjeta «Legajos activos» del inicio (G2-04).
CLAVE_STATS_LEGAJOS_ATENCION = "stats_legajos_atencion"
#: Alertas con `activa=True` (`dashboard.utils.contar_alertas_activas`), TTL 60 s.
CLAVE_ALERTAS = "alertas_activas"


def clave_seguimientos_hoy(dia=None):
    """Inscripciones del día **local** (`dashboard.utils.contar_seguimientos_hoy`).

    La clave lleva la fecha adentro, así que la de ayer caduca sola: lo que hay que
    invalidar al escribir es siempre la de hoy. El día es el local y no el de UTC por
    BEC-18 (entre las 21 y las 24 de Chaco, UTC ya es mañana y la clave se partía en dos).
    """
    return f"seguimientos_hoy_{dia or timezone.localdate()}"


#: `label_lower` del modelo → las claves que su escritura deja viejas.
#:
#: `programas.inscripcionprograma` mueve **dos**: el agregado de `contar_legajos()` y el
#: contador del día de `contar_seguimientos_hoy()`, que filtra por `fecha_inscripcion`.
#: `legajos.legajoatencion` mueve solo la suya: el `stats_legajos` que borraba era el
#: bug de esta ficha.
CLAVES_POR_MODELO = {
    "auth.user": (CLAVE_USUARIOS,),
    "legajos.ciudadano": (CLAVE_CIUDADANOS,),
    "legajos.alertaciudadano": (CLAVE_ALERTAS,),
    "legajos.legajoatencion": (CLAVE_STATS_LEGAJOS_ATENCION,),
    "programas.inscripcionprograma": (CLAVE_STATS_LEGAJOS, clave_seguimientos_hoy),
}


def claves_de(modelo):
    """Las claves que deja viejas una escritura sobre `modelo` (clase o `label_lower`)."""
    etiqueta = modelo if isinstance(modelo, str) else modelo._meta.label_lower
    return tuple(clave() if callable(clave) else clave for clave in CLAVES_POR_MODELO.get(etiqueta.lower(), ()))


def todas_las_claves():
    """Las de la tabla, con las dinámicas ya resueltas para hoy."""
    claves = []
    for modelo in CLAVES_POR_MODELO:
        claves.extend(claves_de(modelo))
    return tuple(dict.fromkeys(claves))


def invalidar_por_modelo(modelo):
    """Borra, tras el commit, solo lo que una escritura sobre `modelo` deja viejo."""
    invalidar_tras_commit(claves_de(modelo))


def invalidar_dashboard():
    """Borra **todos** los contadores de la home.

    La función única que reemplaza a las dos `invalidate_dashboard_cache`. La usa el ABM
    de ciudadanos (`CiudadanosService.invalidate_ciudadanos_cache`), que es escritura de
    pantalla y no de lote: ahí barrer de más no cuesta nada y evita razonar qué tocó cada
    alta. Lo que corre por fila usa :func:`invalidar_por_modelo`.

    Borra **en el acto**, no en `on_commit`, que es lo que hacía la función que reemplaza:
    la llaman las tres vistas de ciudadanos después de guardar, fuera de una transacción
    abierta, y diferirla cambiaría su semántica sin que ninguna medición lo pida.
    """
    invalidate_cache_keys(*todas_las_claves())
