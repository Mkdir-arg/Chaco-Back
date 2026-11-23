"""El caso abierto de una familia: **el** punto único que busca duplicados (Cambio 579).

Una familia tiene a lo sumo un caso de Emergencia abierto. Lo usan los tres caminos que
crean casos —``crear_caso`` (la mesa y el territorio), «Ingresar igual» y «Avisar a la mesa»— y
la búsqueda por DNI de la guardia, para que el criterio sea uno solo: el caso **no cerrado**
cuyo responsable, o cuyo integrante que no egresó, es esa persona.

Es casi una hoja de las dependencias: importa modelos y el candado del numerador de ``emergencia_comun``
(que no importa nada de esto), para que ``emergencia_alta`` pueda usarla sin ciclos.

La carrera de dos altas simultáneas de la misma familia se resuelve en ``crear_caso``: busca acá
**después** de tomar el candado del numerador de casos, que ya serializa toda alta. No se usa un
``UniqueConstraint`` condicional: no existe en MySQL ni en MariaDB (Django lo descarta en silencio y
SQLite sí lo crea, así que el test pasaría por el motivo equivocado).
"""

from django.utils import timezone

from core.dni import normalizar_dni
from programas.models import CasoEmergencia, Derivacion, GrupoFamiliar, IntegranteGrupo, NumeradorEmergencia
from programas.services.emergencia_comun import _bloquear_numerador

Estado = CasoEmergencia.Estado


def caso_abierto_de_la_familia(ciudadano):
    """El caso no cerrado de la familia de ``ciudadano`` (responsable o integrante), o ``None``.

    Si hubiera más de uno (casos de antes de esta regla), el más reciente. Un integrante que ya egresó no ata
    a la persona al caso. Sin candados: quien decide algo con el resultado tiene que haber tomado antes
    :func:`serializar_altas`.

    Corre **con el candado del numerador tomado**, así que son tres búsquedas por índice y sin ``DISTINCT``
    (grupos por ``responsable_id``, grupos por ``ciudadano_id`` del integrante y los casos con ``grupo_id__in``):
    un ``OR`` entre responsable e integrante recorre todos los casos no cerrados con cada alta de la provincia.
    """

    return _ultimo_caso(ciudadano, abierto=True)


def ultimo_caso_de_la_familia(ciudadano):
    """El caso más reciente de la familia de ``ciudadano``, **cerrado o no**, o ``None``.

    Solo para reconocer el reenvío de un envío que se sumó a un caso que después se cerró: lo que se decide con
    la familia es siempre :func:`caso_abierto_de_la_familia`.
    """

    return _ultimo_caso(ciudadano, abierto=False)


def _ultimo_caso(ciudadano, *, abierto):
    if ciudadano is None:
        return None
    grupos = set(GrupoFamiliar.objects.filter(responsable_id=ciudadano.pk).values_list("pk", flat=True))
    grupos.update(
        IntegranteGrupo.objects.filter(ciudadano_id=ciudadano.pk, egresado_en__isnull=True).values_list(
            "grupo_id", flat=True
        )
    )
    if not grupos:
        return None
    casos = CasoEmergencia.objects.filter(grupo_id__in=grupos).select_related("grupo__responsable")
    if abierto:
        casos = casos.exclude(estado=Estado.CERRADO)
    return casos.order_by("-id").first()


def serializar_altas(momento=None):
    """Toma el candado del numerador de casos **sin numerar**: quien llega después espera al commit del anterior.

    Es **el** candado del numerador (``_bloquear_numerador`` de ``emergencia_comun``, el que busca por nombre el
    arnés de concurrencia): devuelve la fila bloqueada para que ``siguiente_numero`` numere sobre ella
    (``numerador=``) sin volver a bloquear. Con él puesto, la lectura de :func:`caso_abierto_de_la_familia` ve lo
    que commiteó el alta que ganó (``READ COMMITTED``), y dos ingresos de la misma familia a la vez no abren dos
    casos. Tiene que correr dentro de una transacción.
    """

    anio = timezone.localtime(momento or timezone.now()).year
    NumeradorEmergencia.objects.get_or_create(serie=NumeradorEmergencia.Serie.CASOS, anio=anio)
    return _bloquear_numerador(NumeradorEmergencia.Serie.CASOS, anio)


def envio_sumado(caso, uuid_cliente, usuario):
    """La anotación del envío de ``usuario`` con ese ``uuid_cliente`` en ``caso``, o ``None``.

    Es el reenvío de un envío que no creó caso. La anotación es ``{"uuid", "usuario_id"}`` y, si el envío fue un
    ingreso directo, ``reservadas`` y ``faltantes``: lo que contestó, para contestar lo mismo al reenvío.
    """

    for envio in (caso.situacion or {}).get(CasoEmergencia.SITUACION_ENVIOS_SUMADOS) or []:
        if envio.get("uuid") == str(uuid_cliente) and envio.get("usuario_id") == usuario.pk:
            return envio
    return None


def envio_ya_sumado(caso, uuid_cliente, usuario):
    """¿Ese ``uuid_cliente`` ya se sumó a ``caso``, enviado por ``usuario``?"""

    return envio_sumado(caso, uuid_cliente, usuario) is not None


def anotar_envio_sumado(caso, uuid_cliente, usuario):
    """Anota en ``caso.situacion`` que ese envío se sumó a él, para que su reenvío no ejecute nada de nuevo.

    Relee ``situacion`` **con candado** y le agrega la anotación: ``caso`` se leyó antes, sin candado, y escribir
    el JSON entero desde esa lectura pisaría lo que la mesa o la guardia confirmaron en el medio
    (``identidad_revisada``, ``en_la_puerta_de``). El orden de candados es numerador y después caso, el de todo alta.
    Corre dentro de la transacción del envío: si esta vuelve atrás, la anotación también.
    """

    if uuid_cliente is None:
        return
    actual = CasoEmergencia.objects.select_for_update().filter(pk=caso.pk).values_list("situacion", flat=True).first()
    situacion = dict(actual or {})
    situacion[CasoEmergencia.SITUACION_ENVIOS_SUMADOS] = [
        *(situacion.get(CasoEmergencia.SITUACION_ENVIOS_SUMADOS) or []),
        {"uuid": str(uuid_cliente), "usuario_id": usuario.pk},
    ]
    caso.situacion = situacion
    caso.save(update_fields=["situacion", "modificado"])


def anotar_resultado_del_envio(caso, uuid_cliente, usuario):
    """Guarda en la anotación del envío lo que contestó (``caso.reservadas`` y ``caso.faltantes``).

    ``caso`` es el que devolvió el servicio, leído con candado, así que su ``situacion`` es la vigente.
    """

    envio = envio_sumado(caso, uuid_cliente, usuario) if uuid_cliente is not None else None
    if envio is None:
        return
    envio["reservadas"], envio["faltantes"] = caso.reservadas, caso.faltantes
    caso.save(update_fields=["situacion", "modificado"])


def caso_del_envio_sumado(dni, uuid_cliente, usuario):
    """El caso abierto de la familia de ``dni`` si ese ``uuid_cliente`` ya se sumó a él; si no, ``None``.

    Para los servicios que miran el reenvío **antes** de pedir camas (el ingreso directo): lo que contestó el
    primer envío no puede depender de si hoy quedan camas.
    """

    from programas.services.ingreso import buscar_ciudadano_por_dni

    if uuid_cliente is None:
        return None
    ciudadano = buscar_ciudadano_por_dni(normalizar_dni(dni or ""))
    caso = caso_abierto_de_la_familia(ciudadano)
    if caso is None:
        caso = ultimo_caso_de_la_familia(ciudadano)  # el caso se pudo cerrar entre el envío y su reenvío
    if caso is not None and envio_ya_sumado(caso, uuid_cliente, usuario):
        return caso
    return None


def ultima_derivacion(caso):
    """La última derivación del caso (la vigente, si la hay), con su dispositivo, o ``None``."""

    return Derivacion.objects.filter(caso_id=caso.pk).select_related("dispositivo").order_by("-id").first()


def nombra_la_institucion(derivacion, dispositivo):
    """¿Se le dice a quien opera ``dispositivo`` en qué institución está la familia? **La única decisión de eso.**

    Sí a la mesa (sin ``dispositivo``) y sí si la derivación es de **este** dispositivo. No hacia otra
    institución, esté pendiente o aceptada (decisión del PM, 23-nov-2026): quien no tiene alcance sobre ella no se
    entera, con solo el DNI, dónde está derivando, ingresando o alojada la familia (RU-9). Se le dice «otra
    institución» (``derivada_a_otra`` de :func:`resumen_del_caso_abierto`).
    """

    if derivacion is None or not derivacion.vigente:
        return False
    return dispositivo is None or derivacion.dispositivo_id == dispositivo.pk


def resumen_del_caso_abierto(caso, dispositivo=None):
    """Lo que la guardia puede ver de un caso abierto de la familia: nada más que esto.

    ``numero``, ``familia`` (el apellido del responsable), ``personas``, ``estado`` y, si
    :func:`nombra_la_institucion`, ``derivada_a`` (la institución) y ``derivada_en``; si la derivación vigente es de
    otra institución y no se nombra, ``derivada_a_otra`` es ``True``. Nada de la ficha, de los
    contactos ni de las fotos. ``en_este_dispositivo`` dice si el caso ya está derivado, o ingresado, acá.
    """

    derivacion = ultima_derivacion(caso)
    vigente = derivacion is not None and derivacion.vigente
    nombra = nombra_la_institucion(derivacion, dispositivo)
    return {
        "id": caso.pk,
        "numero": caso.numero,
        "familia": caso.grupo.responsable.apellido or "",
        "personas": caso.grupo.total_declarado,
        "estado": caso.estado,
        "estado_texto": caso.get_estado_display(),
        "derivada_a": derivacion.dispositivo.nombre if nombra else None,
        "derivada_en": derivacion.creado if nombra else None,
        "derivada_a_otra": vigente and not nombra,
        "en_este_dispositivo": bool(
            dispositivo is not None
            and derivacion is not None
            and derivacion.dispositivo_id == dispositivo.pk
            and (vigente or caso.estado == Estado.ALOJADO)
        ),
    }
