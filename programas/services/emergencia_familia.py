"""El caso abierto de una familia: **el** punto único que busca duplicados (Cambio 579).

Una familia tiene a lo sumo un caso de Emergencia abierto. Lo usan los tres caminos que
crean casos —``crear_caso`` (la mesa y el territorio), «Ingresar igual» y «Avisar a la mesa»— y
la búsqueda por DNI de la guardia, para que el criterio sea uno solo: el caso **no cerrado**
cuyo responsable, o cuyo integrante ya confirmado, es esa persona.

Es una hoja de las dependencias: importa modelos y nada de los otros módulos de Emergencia, para
que ``emergencia_alta`` pueda usarla sin ciclos.

La carrera de dos altas simultáneas de la misma familia se resuelve en ``crear_caso``: busca acá
**después** de tomar el candado del numerador de casos, que ya serializa toda alta. No se usa un
``UniqueConstraint`` condicional: no existe en MySQL ni en MariaDB (Django lo descarta en silencio y
SQLite sí lo crea, así que el test pasaría por el motivo equivocado).
"""

from django.db.models import Q
from django.utils import timezone

from programas.models import CasoEmergencia, Derivacion, NumeradorEmergencia

Estado = CasoEmergencia.Estado


def caso_abierto_de_la_familia(ciudadano):
    """El caso no cerrado de la familia de ``ciudadano`` (responsable o integrante confirmado), o ``None``.

    Si hubiera más de uno (casos de antes de esta regla), el más reciente. Sin candados: quien decide
    algo con el resultado tiene que haber tomado antes :func:`serializar_altas`.
    """

    if ciudadano is None:
        return None
    return (
        CasoEmergencia.objects.exclude(estado=Estado.CERRADO)
        .filter(Q(grupo__responsable=ciudadano) | Q(grupo__integrantes__ciudadano=ciudadano))
        .select_related("grupo__responsable")
        .distinct()
        .order_by("-id")
        .first()
    )


def serializar_altas(momento=None):
    """Toma el candado del numerador de casos **sin numerar**: quien llega después espera al commit del anterior.

    Es el mismo candado que ``siguiente_numero`` vuelve a tomar al numerar. Con él puesto, la lectura de
    :func:`caso_abierto_de_la_familia` ve lo que commiteó el alta que ganó (``READ COMMITTED``), y dos
    ingresos de la misma familia a la vez no abren dos casos. Tiene que correr dentro de una transacción.
    """

    anio = timezone.localtime(momento or timezone.now()).year
    NumeradorEmergencia.objects.get_or_create(serie=NumeradorEmergencia.Serie.CASOS, anio=anio)
    return NumeradorEmergencia.objects.select_for_update().get(serie=NumeradorEmergencia.Serie.CASOS, anio=anio)


def ultima_derivacion(caso):
    """La última derivación del caso (la vigente, si la hay), con su dispositivo, o ``None``."""

    return Derivacion.objects.filter(caso_id=caso.pk).select_related("dispositivo").order_by("-id").first()


def resumen_del_caso_abierto(caso, dispositivo=None):
    """Lo que la guardia puede ver de un caso abierto de la familia: nada más que esto.

    ``numero``, ``familia`` (el apellido del responsable), ``personas``, ``estado`` y, si la mesa lo derivó,
    ``derivada_a`` (la institución) y ``derivada_en``. Nada de la ficha, de los contactos ni de las fotos.
    ``en_este_dispositivo`` dice si el caso ya está derivado, o ingresado, acá.
    """

    derivacion = ultima_derivacion(caso)
    vigente = derivacion is not None and derivacion.vigente
    derivada_a = derivacion.dispositivo.nombre if vigente else None
    return {
        "id": caso.pk,
        "numero": caso.numero,
        "familia": caso.grupo.responsable.apellido or "",
        "personas": caso.grupo.total_declarado,
        "estado": caso.estado,
        "estado_texto": caso.get_estado_display(),
        "derivada_a": derivada_a,
        "derivada_en": derivacion.creado if vigente else None,
        "en_este_dispositivo": bool(
            dispositivo is not None
            and derivacion is not None
            and derivacion.dispositivo_id == dispositivo.pk
            and (vigente or caso.estado == Estado.ALOJADO)
        ),
    }
