"""Lo que lee la mesa de Emergencia: semáforo del SLA, bandeja y panel de derivar.

Solo lectura: nada de acá escribe ni decide una transición (eso es
``programas.services.emergencia``). Cada función dice arriba cuántas consultas hace, y
``programas.tests.test_emergencia_casos`` fija ese número con ``assertNumQueries``: el
``read_timeout`` de la base es de 10 s y la bandeja se abre todo el día.

Tres reglas que cruzan todo el módulo:

* **Sin ``Trunc*``** sobre fechas (la base de ECOM no tiene tablas de zona horaria): los
  tiempos se restan en Python.
* **El semáforo no se guarda.** Sale de las marcas del caso, de los objetivos vigentes de
  ``SLAEmergencia`` y de un ``ahora`` que **llega por parámetro**: ``estado_sla`` no llama
  a ``now()``, así que el mismo caso contesta lo mismo en un test que en producción, y
  cambiar los objetivos en E7 mueve el semáforo de todos los casos abiertos.
* **Quién puede.** La bandeja, el conteo y el semáforo no miran permisos: los abre la
  vista, que ya exigió la capacidad. Las dos lecturas que salen del programa EMERGENCIA
  hacia Dispositivos —``dispositivos_para_derivar`` y ``responsables_alojados``— sí la
  exigen ellas mismas (``emergencia.operar`` o ``supervisar``, **no** ``dispositivo.ver``,
  RU-14), porque contestan sobre instituciones que quien pregunta no opera.
"""

import math
from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import PermissionDenied
from django.db.models import Case, Count, Exists, IntegerField, OuterRef, Q, Subquery, Value, When
from django.utils import timezone

from core.dni import DIGITOS_ASCII, dni_valido, normalizar_dni
from programas.models import CasoEmergencia, Derivacion, Dispositivo, Estadia, IntegranteGrupo, Plaza, TrazaCaso
from programas.services.emergencia_programa import puede_operar_la_mesa
from programas.services.ocupacion import ocupacion_de_plazas

Estado = CasoEmergencia.Estado

# ---------------------------------------------------------------------------
# Semáforo del SLA (RN-2.10)
# ---------------------------------------------------------------------------

SLA_EN_TERMINO = "EN_TERMINO"
SLA_POR_VENCER = "POR_VENCER"
SLA_FUERA = "FUERA"
ESTADOS_SLA = (SLA_EN_TERMINO, SLA_POR_VENCER, SLA_FUERA)

TRAMO_TOMAR = "tomar"
TRAMO_DERIVAR = "derivar"
TRAMO_ACEPTAR = "aceptar"
TRAMO_ALOJAR = "alojar"

#: Cada tramo: su nombre, la marca que lo **abre**, la que lo **cierra** y el campo de
#: ``SLAEmergencia`` con su objetivo. El orden es el del recorrido del caso. ``creado`` es
#: la hora del servidor al recibir el caso (RU-18): nunca la del teléfono.
TRAMOS = (
    (TRAMO_TOMAR, "creado", "tomado_en", "objetivo_tomar_min"),
    (TRAMO_DERIVAR, "tomado_en", "derivado_en", "objetivo_derivar_min"),
    (TRAMO_ACEPTAR, "derivado_en", "aceptado_en", "objetivo_aceptar_min"),
    (TRAMO_ALOJAR, "aceptado_en", "alojado_en", "objetivo_alojar_min"),
)

#: Los estados en los que el caso tiene un tramo corriendo. Alojado y cerrado no tienen SLA.
ESTADOS_CON_SLA = (Estado.NUEVO, Estado.EN_GESTION, Estado.DERIVADO, Estado.INGRESO_EN_CURSO)

#: Hasta cuántos minutos el tiempo se lee en minutos, y hasta cuántas horas en horas.
TOPE_EN_MINUTOS = 100
TOPE_EN_HORAS = 72


def texto_de_minutos(minutos):
    """Un lapso en minutos, legible cuando es grande: «42 min», «5 h», «3 d».

    Hasta 99 minutos va en minutos; desde 100 minutos y hasta 71 horas, en horas enteras;
    desde 72 horas, en días enteros. Siempre trunca: «48 h» es «por lo menos 48 horas».
    Una derivación que nadie aceptó en dos días se lee «48 h» y no «2880 min».
    """

    if minutos < TOPE_EN_MINUTOS:
        return f"{minutos} min"
    horas = minutos // 60
    if horas < TOPE_EN_HORAS:
        return f"{horas} h"
    return f"{horas // 24} d"


@dataclass(frozen=True)
class EstadoSLA:
    """Dónde está un caso respecto del objetivo de su tramo en curso.

    Es el contrato de la pieza ``components/_semaforo_sla.html``, que recibe
    ``estado``, ``minutos`` y ``tramo`` y no calcula nada:

    * ``estado`` — ``EN_TERMINO``, ``POR_VENCER`` o ``FUERA``.
    * ``minutos`` — en ``EN_TERMINO`` y ``POR_VENCER``, los que **faltan** para que venza
      el tramo (redondeados hacia arriba: «vence en 8 min» sigue siendo cierto durante
      todo ese minuto); en ``FUERA``, los que lleva **excedido** (hacia abajo).
    * ``tramo`` — ``tomar``, ``derivar``, ``aceptar`` o ``alojar``.

    Además trae ``objetivo_min`` y ``transcurridos_min`` del tramo, y ``texto_tiempo``:
    los mismos ``minutos`` en una forma que se puede leer cuando son muchos
    (:func:`texto_de_minutos`).

    Se desarma como la terna de siempre: ``estado, minutos, tramo = estado_sla(...)``.
    """

    estado: str
    minutos: int
    tramo: str
    objetivo_min: int
    transcurridos_min: int

    def __iter__(self):
        yield self.estado
        yield self.minutos
        yield self.tramo

    @property
    def texto_tiempo(self):
        return texto_de_minutos(self.minutos)

    @property
    def fuera(self):
        return self.estado == SLA_FUERA


def _tramo_en_curso(estado, marcas):
    """``(tramo, desde, campo_objetivo)`` del primer tramo que todavía no cerró, o ``None``.

    Las marcas se escriben una sola vez y no se borran (RN-2.9), así que el tramo en curso
    es el de la primera marca que falta, **esté en el estado que esté** el caso: uno que
    volvió a «En gestión» porque la derivación venció sigue en el tramo «aceptar», que
    corre desde la primera derivación. Eso es lo que hace que el SLA mida a la familia.
    """

    if estado not in ESTADOS_CON_SLA:
        return None
    for tramo, abre, cierra, campo_objetivo in TRAMOS:
        if marcas[cierra] is None:
            desde = marcas[abre]
            if desde is None:  # un caso al que le falta la marca anterior no tiene desde cuándo medir
                return None
            return tramo, desde, campo_objetivo
    return None


def _estado_sla_de(estado, marcas, sla, ahora):
    en_curso = _tramo_en_curso(estado, marcas)
    if en_curso is None:
        return None
    tramo, desde, campo_objetivo = en_curso
    objetivo_min = getattr(sla, campo_objetivo)
    objetivo_seg = objetivo_min * 60
    transcurrido_seg = max((ahora - desde).total_seconds(), 0)
    transcurridos_min = int(transcurrido_seg // 60)
    if transcurrido_seg > objetivo_seg:
        return EstadoSLA(
            SLA_FUERA, int((transcurrido_seg - objetivo_seg) // 60), tramo, objetivo_min, transcurridos_min
        )
    faltan = math.ceil((objetivo_seg - transcurrido_seg) / 60)
    # Entero contra entero: «pasó el 80 %» no depende de un redondeo de coma flotante.
    por_vencer = transcurrido_seg * 100 >= objetivo_seg * sla.umbral_por_vencer_pct
    return EstadoSLA(SLA_POR_VENCER if por_vencer else SLA_EN_TERMINO, faltan, tramo, objetivo_min, transcurridos_min)


def _marcas_de(caso):
    return {
        "creado": caso.creado,
        "tomado_en": caso.tomado_en,
        "derivado_en": caso.derivado_en,
        "aceptado_en": caso.aceptado_en,
        "alojado_en": caso.alojado_en,
    }


def estado_sla(caso, sla, ahora: datetime):
    """El semáforo del caso en ``ahora``: un :class:`EstadoSLA`, o ``None`` si no tiene SLA.

    **Sin consultas y sin reloj propio**: función pura de las marcas del caso, los
    objetivos de ``sla`` (un ``SLAEmergencia``) y ``ahora``.

    * Un caso alojado o cerrado devuelve ``None``: no hay tramo corriendo.
    * ``FUERA`` es haber **superado** el objetivo: justo en el minuto del objetivo todavía
      es ``POR_VENCER`` con 0 minutos.
    * ``POR_VENCER`` es haber llegado al ``sla.umbral_por_vencer_pct`` del objetivo (80 %
      de fábrica), incluido el instante exacto.
    """

    return _estado_sla_de(caso.estado, _marcas_de(caso), sla, ahora)


def ids_por_estado_sla(sla, ahora: datetime):
    """``{id del caso: EstadoSLA}`` de todos los casos con un tramo corriendo.

    **Una consulta**, sin JOIN y con siete columnas: los abiertos son cientos, no miles, y
    el semáforo se calcula en Python sobre ellos (02 §3). Es la base de la solapa «Fuera de
    SLA», del filtro por semáforo y del orden de la bandeja.
    """

    filas = CasoEmergencia.objects.filter(estado__in=ESTADOS_CON_SLA).values_list(
        "id", "estado", "creado", "tomado_en", "derivado_en", "aceptado_en", "alojado_en"
    )
    resultado = {}
    for pk, estado, creado, tomado_en, derivado_en, aceptado_en, alojado_en in filas:
        marcas = {
            "creado": creado,
            "tomado_en": tomado_en,
            "derivado_en": derivado_en,
            "aceptado_en": aceptado_en,
            "alojado_en": alojado_en,
        }
        semaforo = _estado_sla_de(estado, marcas, sla, ahora)
        if semaforo is not None:
            resultado[pk] = semaforo
    return resultado


def ids_fuera_de_sla(sla, ahora: datetime):
    """Los ids de los casos fuera de SLA, en **una consulta** (:func:`ids_por_estado_sla`)."""

    return [pk for pk, semaforo in ids_por_estado_sla(sla, ahora).items() if semaforo.fuera]


# ---------------------------------------------------------------------------
# Bandeja (E2)
# ---------------------------------------------------------------------------

SOLAPA_MIS_CASOS = "mis_casos"
SOLAPA_SIN_TOMAR = "sin_tomar"
SOLAPA_ESPERANDO_INSTITUCION = "esperando_institucion"
SOLAPA_ABIERTOS = "abiertos"
SOLAPA_NUEVOS = "nuevos"
SOLAPA_EN_GESTION = "en_gestion"
SOLAPA_DERIVADOS = "derivados"
SOLAPA_INGRESO_EN_CURSO = "ingreso_en_curso"
SOLAPA_FUERA_SLA = "fuera_sla"
SOLAPA_INGRESO_DIRECTO = "ingreso_directo"
SOLAPA_ALOJADOS = "alojados"
SOLAPA_CERRADOS = "cerrados"

#: Las solapas de E2. Las primeras cinco son los chips de la bandeja (Cambio 580), en el orden de la pantalla;
#: el resto sigue siendo válido porque lo usan los enlaces de los avisos (``?solapa=fuera_sla``, ``derivados``…).
SOLAPAS = (
    SOLAPA_MIS_CASOS,
    SOLAPA_SIN_TOMAR,
    SOLAPA_ESPERANDO_INSTITUCION,
    SOLAPA_ALOJADOS,
    SOLAPA_CERRADOS,
    SOLAPA_ABIERTOS,
    SOLAPA_NUEVOS,
    SOLAPA_EN_GESTION,
    SOLAPA_DERIVADOS,
    SOLAPA_INGRESO_EN_CURSO,
    SOLAPA_FUERA_SLA,
    SOLAPA_INGRESO_DIRECTO,
)

#: Los estados en los que un caso sin dueño espera que alguien de la mesa lo tome o lo siga: todos los abiertos
#: menos el alojado, que ya tiene a la familia adentro y se mira en «Alojados».
ESTADOS_SIN_TOMAR = (Estado.NUEVO, Estado.EN_GESTION, Estado.DERIVADO, Estado.INGRESO_EN_CURSO)

#: En manos de la institución: la derivación espera respuesta o ya fue aceptada y la familia está ingresando.
ESTADOS_ESPERANDO_INSTITUCION = (Estado.DERIVADO, Estado.INGRESO_EN_CURSO)

#: Qué filtra cada solapa que sale del estado o del origen. «Fuera de SLA» no está: no es
#: una condición de la base, se calcula.
_Q_DE_SOLAPA = {
    # Es ``CasoEmergencia.abierto`` en SQL: todo lo que no está cerrado (un alojado también: sigue abierto hasta que
    # egresa la familia). Una definición distinta hacía que la solapa y la propiedad se contradijeran (Cambio 580).
    SOLAPA_ABIERTOS: ~Q(estado=Estado.CERRADO),
    SOLAPA_SIN_TOMAR: Q(tomado_por__isnull=True, estado__in=ESTADOS_SIN_TOMAR),
    SOLAPA_ESPERANDO_INSTITUCION: Q(estado__in=ESTADOS_ESPERANDO_INSTITUCION),
    SOLAPA_NUEVOS: Q(estado=Estado.NUEVO),
    SOLAPA_EN_GESTION: Q(estado=Estado.EN_GESTION),
    SOLAPA_DERIVADOS: Q(estado=Estado.DERIVADO),
    SOLAPA_INGRESO_EN_CURSO: Q(estado=Estado.INGRESO_EN_CURSO),
    # Los que entraron sin pasar por la mesa y siguen abiertos.
    SOLAPA_INGRESO_DIRECTO: Q(origen=CasoEmergencia.Origen.DISPOSITIVO) & ~Q(estado=Estado.CERRADO),
    SOLAPA_ALOJADOS: Q(estado=Estado.ALOJADO),
    SOLAPA_CERRADOS: Q(estado=Estado.CERRADO),
}

#: El orden de la prioridad no es el alfabético de sus códigos.
_ORDEN_PRIORIDAD = Case(
    When(prioridad=CasoEmergencia.Prioridad.ALTA, then=Value(0)),
    When(prioridad=CasoEmergencia.Prioridad.MEDIA, then=Value(1)),
    default=Value(2),
    output_field=IntegerField(),
)

#: ``usuario`` es el id de quien mira: lo necesita la solapa «Mis casos» (los abiertos que tiene tomados).
FILTROS_DE_BANDEJA = (
    "solapa",
    "estado",
    "prioridad",
    "localidad",
    "tomado_por",
    "origen",
    "sla",
    "texto",
    "usuario",
)


def _q_de_solapa(solapa, usuario_id=None):
    """El filtro de la solapa. «Mis casos» depende de quien mira; sin usuario no hay casos suyos."""

    if solapa == SOLAPA_MIS_CASOS:
        if usuario_id is None:
            return Q(pk__in=[])
        return Q(tomado_por_id=usuario_id) & ~Q(estado=Estado.CERRADO)
    return _Q_DE_SOLAPA[solapa]


def _q_de_dni(dni):
    """El DNI (ya normalizado) del responsable o de cualquier integrante del grupo, en la misma consulta."""

    return Q(grupo__responsable__dni=dni) | Exists(
        IntegranteGrupo.objects.filter(ciudadano__dni=dni, grupo_id=OuterRef("grupo_id"))
    )


def _q_de_palabra(palabra):
    """Una palabra del buscador: n.° de caso, nombre, apellido o DNI del responsable, o de cualquier integrante."""

    q = (
        Q(numero__icontains=palabra)
        | Q(grupo__responsable__apellido__icontains=palabra)
        | Q(grupo__responsable__nombre__icontains=palabra)
    )
    dni = normalizar_dni(palabra)
    if dni:
        q |= _q_de_dni(dni)
    # Exists y no un JOIN: un caso con varios integrantes que coinciden no se repite ni hace falta DISTINCT.
    en_integrantes = Q(ciudadano__apellido__icontains=palabra) | Q(ciudadano__nombre__icontains=palabra)
    return q | Exists(IntegranteGrupo.objects.filter(en_integrantes, grupo_id=OuterRef("grupo_id")))


def _q_de_texto(texto):
    """N.° de caso, DNI, nombre o apellido del responsable o de un integrante (02 §3).

    El texto se parte en palabras y **cada una** tiene que aparecer en algún campo: «Juan Pérez»
    encuentra a la familia aunque el nombre y el apellido estén en columnas distintas (Cambio 533).

    Un DNI escrito con espacios («30 123 456») son varias palabras que no aparecen sueltas en ningún
    campo: si el texto entero es un DNI partido —solo dígitos y separadores— se suma con OR el DNI
    del responsable o de un integrante, en la misma consulta (Cambio 535).
    """

    texto = texto or ""
    palabras = texto.split()
    q = Q()
    for palabra in palabras:
        q &= _q_de_palabra(palabra)
    if len(palabras) > 1 and _es_dni_partido(texto):
        q |= _q_de_dni(normalizar_dni(texto))
    return q


#: Lo que puede separar los dígitos de un DNI escrito a mano.
_SEPARADORES_DE_DNI = frozenset(" .-")


def _es_dni_partido(texto):
    """¿``texto`` es un DNI con separadores? Solo dígitos, espacios, puntos y guiones, y un largo válido."""

    return all(ch in DIGITOS_ASCII or ch in _SEPARADORES_DE_DNI for ch in texto.strip()) and dni_valido(texto)


def bandeja(filtros=None, *, sla=None, ahora=None, semaforos=None):
    """El queryset de la bandeja E2, filtrado y ordenado, listo para paginar.

    ``filtros`` es un dict con cualquiera de estas claves (las vacías se ignoran):

    * ``solapa`` — una de :data:`SOLAPAS`.
    * ``estado``, ``prioridad``, ``origen`` — el código del ``TextChoices``.
    * ``localidad`` — id de ``core.Localidad``.
    * ``tomado_por`` — id de usuario («Míos» es el del que mira).
    * ``sla`` — ``EN_TERMINO``, ``POR_VENCER`` o ``FUERA``.
    * ``texto`` — N.° de caso, DNI, nombre o apellido del responsable o de un integrante, por palabras.
    * ``usuario`` — id de quien mira; lo exige la solapa ``mis_casos`` (sin él no devuelve nada).

    Con ``sla`` y ``ahora`` (el ``SLAEmergencia`` vigente y el instante) el orden es el de
    la pantalla: **fuera de SLA primero**, después por prioridad, después el más viejo.
    Sin ellos se ordena por prioridad y antigüedad. La solapa «Fuera de SLA» y el filtro
    ``sla`` los exigen (``ValueError`` si faltan): no se pueden contestar sin reloj.

    ``semaforos`` es lo que ya contestó :func:`ids_por_estado_sla` para ese ``sla`` y ese
    ``ahora``, si quien llama lo necesita también para otra cosa (E2 cuenta con él los
    «Fuera de SLA»); sin él, se calcula acá.

    **Presupuesto:** construir el queryset cuesta **0 o 1 consulta** (1 si llegaron
    ``sla`` y ``ahora`` sin ``semaforos``: la de :func:`ids_por_estado_sla`). Evaluarlo es **una** consulta
    por página, sin N+1 en la fila: trae el grupo, el responsable, la localidad y quien
    lo tomó con ``select_related``, y los avisos de la mesa como subconsultas de esa misma
    consulta (:func:`con_avisos_de_la_mesa`).
    """

    filtros = filtros or {}
    desconocidos = set(filtros) - set(FILTROS_DE_BANDEJA)
    if desconocidos:
        raise ValueError(f"Filtros que la bandeja no conoce: {', '.join(sorted(desconocidos))}.")

    casos = con_avisos_de_la_mesa(
        CasoEmergencia.objects.select_related("grupo__responsable", "localidad", "tomado_por"), ahora
    )
    solapa = filtros.get("solapa") or ""
    filtro_sla = filtros.get("sla") or ""
    if solapa and solapa not in SOLAPAS:
        raise ValueError(f"«{solapa}» no es una solapa de la bandeja.")
    if filtro_sla and filtro_sla not in ESTADOS_SLA:
        raise ValueError(f"«{filtro_sla}» no es un estado del semáforo.")
    con_reloj = sla is not None and ahora is not None
    if (solapa == SOLAPA_FUERA_SLA or filtro_sla) and not con_reloj:
        raise ValueError("El filtro por SLA necesita el SLA vigente y el instante (`sla` y `ahora`).")

    if solapa == SOLAPA_MIS_CASOS or solapa in _Q_DE_SOLAPA:
        casos = casos.filter(_q_de_solapa(solapa, filtros.get("usuario")))
    for campo in ("estado", "prioridad", "origen"):
        if filtros.get(campo):
            casos = casos.filter(**{campo: filtros[campo]})
    if filtros.get("localidad"):
        casos = casos.filter(localidad_id=filtros["localidad"])
    if filtros.get("tomado_por"):
        casos = casos.filter(tomado_por_id=filtros["tomado_por"])
    casos = casos.filter(_q_de_texto(filtros.get("texto")))

    orden = [_ORDEN_PRIORIDAD.asc(), "creado", "id"]
    if con_reloj:
        if semaforos is None:
            semaforos = ids_por_estado_sla(sla, ahora)
        fuera = [pk for pk, semaforo in semaforos.items() if semaforo.fuera]
        if solapa == SOLAPA_FUERA_SLA:
            casos = casos.filter(pk__in=fuera)
        if filtro_sla:
            casos = casos.filter(pk__in=[pk for pk, semaforo in semaforos.items() if semaforo.estado == filtro_sla])
        primero_los_fuera = Case(When(pk__in=fuera, then=Value(0)), default=Value(1), output_field=IntegerField())
        orden.insert(0, primero_los_fuera.asc())
    return casos.order_by(*orden)


def conteo_por_solapa(usuario_id=None):
    """Cuántos casos hay en cada solapa que sale del estado o del origen.

    ``usuario_id`` es quien mira, para «Mis casos» (sin él, 0).

    **Una consulta**, agregada (sin ``GROUP BY`` que después haya que sumar en Python y
    sin una consulta por solapa). Devuelve un dict con las claves de :data:`SOLAPAS`
    **menos** ``fuera_sla``, más ``total``.

    «Fuera de SLA» no sale de acá porque no es una condición de la base: es
    ``len(ids_fuera_de_sla(sla, ahora))``, una consulta más.
    """

    return CasoEmergencia.objects.aggregate(
        total=Count("id"),
        **{
            solapa: Count("id", filter=_q_de_solapa(solapa, usuario_id)) for solapa in (SOLAPA_MIS_CASOS, *_Q_DE_SOLAPA)
        },
    )


# ---------------------------------------------------------------------------
# Avisos de la mesa (las marcas que dependen de las etapas 3 y 4)
# ---------------------------------------------------------------------------


def ultima_traza_del_caso():
    """La subconsulta correlacionada de la última ``TrazaCaso`` del caso de la fila (``OuterRef("pk")``).

    La única definición de «la última traza»: la usan la bandeja, la ficha y el tablero E1.
    """

    return TrazaCaso.objects.filter(caso=OuterRef("pk")).order_by("-creado_en", "-id")


def rechazo_sin_nueva_accion(caso):
    """¿La última traza del caso sigue siendo el rechazo de la derivación (RN-3.13, HU-2.5)?

    ``caso`` trae ``ultima_accion`` (anotado con :func:`ultima_traza_del_caso`): la próxima
    acción de la mesa, cualquiera, deja otra traza y lo apaga. Lo leen la marca de E2/E3 y el
    aviso del tablero E1.
    """

    return caso.ultima_accion == TrazaCaso.Accion.DERIVACION_RECHAZADA


def con_avisos_de_la_mesa(casos, ahora=None):
    """``casos`` (un queryset de ``CasoEmergencia``) con lo que necesitan los avisos de la mesa.

    Suma a cada caso, como subconsultas correlacionadas **de la misma consulta** —no cuesta
    una consulta más, ni por fila ni por página—:

    * ``derivada_a`` — el nombre del dispositivo de la derivación vigente (pendiente o aceptada), que lee la
      columna «Qué falta» de la bandeja.
    * ``ultima_accion`` — la ``accion`` de la última ``TrazaCaso``. «Sin acción posterior»
      al rechazo o al vencimiento es que esa siga siendo la última.
    * ``ultima_traza_en`` — cuándo fue esa última traza: el último movimiento del caso, que
      lee el aviso «Aceptado sin movimiento» (:func:`horas_sin_movimiento`, Cambio 535).
    * ``rechazada_por``, ``rechazada_motivo`` y ``rechazada_observacion`` — el dispositivo,
      el motivo y la observación de la última derivación ``RECHAZADA`` (RN-3.13).
    * ``derivada_a_inactivo`` — la derivación ``PENDIENTE`` apunta a un dispositivo que dejó
      de estar ``ACTIVO`` (02 §9). Solo la pendiente: con la aceptada la familia ya llegó.
    * ``derivacion_vencida_sin_marcar`` — la derivación ``PENDIENTE`` ya pasó su ``vence_en`` (a ``ahora``,
      por defecto el reloj) y el cron todavía no la marcó: se puede aceptar igual (RN-3.3), pero la
      mesa tiene que ver que el plazo se cumplió (Cambio 533).

    Las subconsultas se evalúan sobre las filas de la página (50), y la cuenta del
    paginador no las arrastra porque nada las referencia.
    """

    ultima_traza = ultima_traza_del_caso()
    ultima_rechazada = Derivacion.objects.filter(caso=OuterRef("pk"), estado=Derivacion.Estado.RECHAZADA).order_by(
        "-respondida_en", "-id"
    )
    pendiente_a_inactivo = Derivacion.objects.filter(
        clave_vigente=OuterRef("pk"), estado=Derivacion.Estado.PENDIENTE
    ).exclude(dispositivo__estado=Dispositivo.Estado.ACTIVO)
    pendiente_vencida = Derivacion.objects.filter(
        clave_vigente=OuterRef("pk"), estado=Derivacion.Estado.PENDIENTE, vence_en__lt=ahora or timezone.now()
    )
    vigente = Derivacion.objects.filter(clave_vigente=OuterRef("pk"))
    return casos.annotate(
        derivada_a=Subquery(vigente.values("dispositivo__nombre")[:1]),
        ultima_accion=Subquery(ultima_traza.values("accion")[:1]),
        ultima_traza_en=Subquery(ultima_traza.values("creado_en")[:1]),
        rechazada_por=Subquery(ultima_rechazada.values("dispositivo__nombre")[:1]),
        rechazada_motivo=Subquery(ultima_rechazada.values("motivo")[:1]),
        rechazada_observacion=Subquery(ultima_rechazada.values("observacion")[:1]),
        derivada_a_inactivo=Exists(pendiente_a_inactivo),
        derivacion_vencida_sin_marcar=Exists(pendiente_vencida),
    )


def horas_sin_movimiento(caso, sla, ahora):
    """Horas enteras que lleva un ingreso aceptado sin movimiento, o ``None`` si no hay que avisar (Cambio 535).

    **Pura, sin consultas**: ``caso`` viene anotado por :func:`con_avisos_de_la_mesa` (``ultima_traza_en``).
    «Movimiento» es cualquier traza del caso —la aceptación, cada persona confirmada, un contacto
    de la mesa—: la misma «última traza» que la bandeja usa para los demás avisos. Solo en
    «Ingreso en curso», y solo desde ``sla.ingreso_sin_movimiento_h`` horas (0 lo apaga). No vence
    nada: el ingreso lo destraba quien supervisa la mesa, a mano.
    """

    limite_h = sla.ingreso_sin_movimiento_h
    desde = caso.ultima_traza_en
    if caso.estado != Estado.INGRESO_EN_CURSO or not limite_h or desde is None:
        return None
    horas = int((ahora - desde).total_seconds() // 3600)
    return horas if horas >= limite_h else None


# ---------------------------------------------------------------------------
# Panel «Derivar» (E3)
# ---------------------------------------------------------------------------

MARCA_ALCANZA = "ALCANZA"
MARCA_FALTAN = "FALTAN"
MARCA_SIN_PLAZAS = "SIN_PLAZAS"

RADIO_TIERRA_KM = 6371.0088

SIN_PERMISO_DE_MESA = "Solo quien trabaja en la mesa de Emergencia puede ver esto."


def dispositivo_elegible(dispositivo):
    """¿Se le puede derivar una familia? **La única definición** (RN-2.2, hallazgo H6).

    Institución ``ACTIVO`` cuyo tipo está activo, maneja plazas y admite camas. Si el PM
    decide «solo centros de evacuados» (decisión 5), el filtro por ``tipo.codigo`` se
    agrega acá y en ningún otro lado: el selector y ``derivar_caso`` preguntan por esta
    función.
    """

    tipo = dispositivo.tipo
    return (
        dispositivo.estado == Dispositivo.Estado.ACTIVO
        and tipo.activo
        and tipo.maneja_plazas
        and tipo.admite_tipo_de_plaza(Plaza.Tipo.CAMA)
    )


#: Lo que aloja una familia de Emergencia (RN-2.3): las camas. Un cupo o un turno libre no cuenta.
TIPOS_QUE_ALOJAN = (Plaza.Tipo.CAMA,)


def camas_de(dispositivos, momento=None):
    """El ``Censo`` de ``ocupacion_de_plazas`` contando **solo camas**. Las mismas 3 consultas en lote.

    Es la cuenta única de Emergencia: el panel «Derivar» (E3), la validación al derivar, la
    red del tablero (E1), sus avisos y la foto de situación (E8) la leen de acá.
    """

    return ocupacion_de_plazas(dispositivos, momento, tipos=TIPOS_QUE_ALOJAN)


def camas_libres_del_conteo(conteo):
    """Las camas libres de un ``Conteo`` de :func:`camas_de`, nunca negativas.

    No confundir con ``selectors.emergencia_alojar.camas_libres(dispositivo, momento)``, que
    devuelve las **plazas** libres de un dispositivo para elegir dónde alojar.
    """

    return max(conteo.disponibles or 0, 0)


def dispositivos_elegibles():
    """Los elegibles, con su tipo. Una consulta; lo que mira el JSON del tipo se filtra en Python."""

    candidatos = (
        Dispositivo.objects.filter(estado=Dispositivo.Estado.ACTIVO, tipo__activo=True)
        .select_related("tipo")
        .order_by("nombre", "id")
    )
    return [dispositivo for dispositivo in candidatos if dispositivo_elegible(dispositivo)]


def distancia_km(latitud_a, longitud_a, latitud_b, longitud_b):
    """Distancia en kilómetros entre dos puntos (haversine), o ``None`` si falta alguno.

    Se calcula en Python: son decenas de dispositivos, y así no hay función geográfica que
    tenga que existir igual en MySQL, MariaDB y SQLite.
    """

    if None in (latitud_a, longitud_a, latitud_b, longitud_b):
        return None
    lat_a, lon_a, lat_b, lon_b = (
        math.radians(float(valor)) for valor in (latitud_a, longitud_a, latitud_b, longitud_b)
    )
    seno_lat = math.sin((lat_b - lat_a) / 2)
    seno_lon = math.sin((lon_b - lon_a) / 2)
    a = seno_lat**2 + math.cos(lat_a) * math.cos(lat_b) * seno_lon**2
    return 2 * RADIO_TIERRA_KM * math.asin(min(1.0, math.sqrt(a)))


def marca_de_plazas(libres, pedidas):
    """``(marca, faltan)`` de ``libres`` camas para ``pedidas`` plazas (RN-2.5). Lo usa también el panel por edificio."""

    if libres <= 0:
        return MARCA_SIN_PLAZAS, max(pedidas, 0)
    if libres < pedidas:
        return MARCA_FALTAN, pedidas - libres
    return MARCA_ALCANZA, 0


def dispositivos_para_derivar(caso, usuario, *, plazas=None, momento=None):
    """Los dispositivos a los que la mesa puede derivar ``caso``, con plazas y distancia.

    Lo autoriza ``emergencia.operar`` (o ``supervisar``) en el programa EMERGENCIA, **no**
    ``dispositivo.ver`` (RU-14): sin eso, ``PermissionDenied``. Por eso devuelve de cada
    institución solo lo que hace falta para elegir y **nada de su operación interna**:

    ``{"id", "nombre", "localidad", "libres", "reservadas", "distancia_km", "marca", "faltan"}``

    * ``libres`` y ``reservadas`` son **camas** (RN-2.3), de :func:`camas_de`: la cuenta de
      ``ocupacion_de_plazas``, sin reimplementar, la misma que ve el tablero E1.
    * ``distancia_km`` es ``None`` —«distancia desconocida»— si el caso no tiene GPS o el
      dispositivo no tiene coordenadas. No hay centroide de localidad (hallazgo H4).
    * ``marca`` es ``ALCANZA``, ``FALTAN`` o ``SIN_PLAZAS`` contra ``plazas`` (por omisión,
      el ``total_declarado`` del grupo), y ``faltan`` cuántas plazas no hay.

    Orden: los que alcanzan primero, después los que no y al final los que no tienen
    plazas; dentro de cada grupo, el más cercano, con la distancia desconocida al final.

    **Presupuesto: 4 consultas fijas**, haya 5 dispositivos o 500: una por los elegibles
    con su tipo y las tres de ``ocupacion_de_plazas`` en lote. La autorización no suma
    con el usuario ya resuelto en la request (``rbac`` lo memoiza en el objeto).
    """

    if not puede_operar_la_mesa(usuario):
        raise PermissionDenied(SIN_PERMISO_DE_MESA)
    pedidas = caso.grupo.total_declarado if plazas is None else int(plazas)
    dispositivos = dispositivos_elegibles()
    censo = camas_de([dispositivo.pk for dispositivo in dispositivos], momento)

    filas = []
    for dispositivo in dispositivos:
        conteo = censo.de(dispositivo.pk).conteo
        libres = camas_libres_del_conteo(conteo)
        marca, faltan = marca_de_plazas(libres, pedidas)
        filas.append(
            {
                "id": dispositivo.pk,
                "nombre": dispositivo.nombre,
                "localidad": dispositivo.localidad,
                "libres": libres,
                "reservadas": conteo.reservadas,
                "distancia_km": distancia_km(caso.latitud, caso.longitud, dispositivo.latitud, dispositivo.longitud),
                "marca": marca,
                "faltan": faltan,
            }
        )

    orden_de_marca = {MARCA_ALCANZA: 0, MARCA_FALTAN: 1, MARCA_SIN_PLAZAS: 2}
    filas.sort(
        key=lambda fila: (
            orden_de_marca[fila["marca"]],
            fila["distancia_km"] is None,
            fila["distancia_km"] or 0.0,
            fila["nombre"],
            fila["id"],
        )
    )
    return filas


# ---------------------------------------------------------------------------
# Marcas de la ficha y de la fila
# ---------------------------------------------------------------------------


def posibles_duplicados_de(casos):
    """``{id del caso: [(id, numero) de otros casos abiertos con una persona en común]}``.

    RN-2.14: otro caso **abierto** cuyo responsable, o alguno de sus integrantes
    confirmados, es el responsable o un integrante confirmado de este. Es informativa: la
    mesa decide. Los casos sin coincidencias no aparecen en el dict.

    **Presupuesto: 3 consultas fijas** para toda la página de la bandeja: los integrantes
    confirmados de los casos pedidos, los casos abiertos con esos responsables y los
    integrantes de casos abiertos que son esas personas.
    """

    casos = list(casos)
    if not casos:
        return {}
    personas_de = {caso.pk: {caso.grupo.responsable_id} for caso in casos}
    caso_de_grupo = {caso.grupo_id: caso.pk for caso in casos}
    propios = IntegranteGrupo.objects.filter(grupo_id__in=caso_de_grupo, ciudadano__isnull=False).values_list(
        "grupo_id", "ciudadano_id"
    )
    for grupo_id, ciudadano_id in propios:
        personas_de[caso_de_grupo[grupo_id]].add(ciudadano_id)
    todas = set().union(*personas_de.values())

    # persona -> {(id, numero)} de los casos abiertos donde aparece
    casos_de_persona = {}
    abiertos = CasoEmergencia.objects.exclude(estado=Estado.CERRADO)
    for pk, numero, persona in abiertos.filter(grupo__responsable_id__in=todas).values_list(
        "id", "numero", "grupo__responsable_id"
    ):
        casos_de_persona.setdefault(persona, set()).add((pk, numero))
    integrantes = IntegranteGrupo.objects.filter(ciudadano_id__in=todas).exclude(grupo__caso__estado=Estado.CERRADO)
    for pk, numero, persona in integrantes.values_list("grupo__caso__id", "grupo__caso__numero", "ciudadano_id"):
        if pk is not None:
            casos_de_persona.setdefault(persona, set()).add((pk, numero))

    resultado = {}
    for caso in casos:
        otros = set()
        for persona in personas_de[caso.pk]:
            otros |= casos_de_persona.get(persona, set())
        otros = sorted(otro for otro in otros if otro[0] != caso.pk)
        if otros:
            resultado[caso.pk] = otros
    return resultado


def posibles_duplicados(caso):
    """Los ``(id, numero)`` de otros casos abiertos con una persona en común (RN-2.14).

    **3 consultas** (:func:`posibles_duplicados_de`). Lista vacía si no hay ninguno.
    """

    return posibles_duplicados_de([caso]).get(caso.pk, [])


@dataclass(frozen=True)
class ResponsableAlojado:
    """Dónde figura alojado hoy el responsable de un caso (RN-2.15)."""

    estadia_id: int
    dispositivo_id: int
    dispositivo: str
    desde: datetime


def responsables_alojados(casos, usuario):
    """``{id del caso: ResponsableAlojado}`` de los casos cuyo responsable tiene una estadía abierta.

    RN-2.15: no bloquea derivar, pero el dispositivo no le va a poder dar una cama hasta
    que lo egresen de donde está. Es la consulta de solo lectura equivalente a
    ``verificar_alojamiento_en_red``, que no sirve acá porque exige
    ``dispositivo.admitir`` —la mesa no la tiene— y recorta por el alcance del operador.
    La mesa ve todos los casos y deriva a cualquier institución (RU-10, RU-14), así que
    ve el nombre; por eso la exige ``emergencia.operar`` o ``supervisar``
    (``PermissionDenied``).

    **Presupuesto: 1 consulta** para toda la página, por la clave de alojamiento
    (``Estadia.clave_alojamiento``, única e indexada).
    """

    if not puede_operar_la_mesa(usuario):
        raise PermissionDenied(SIN_PERMISO_DE_MESA)
    casos = list(casos)
    if not casos:
        return {}
    casos_de_clave = {}
    for caso in casos:
        casos_de_clave.setdefault(Estadia.clave_para(caso.grupo.responsable_id), []).append(caso.pk)
    estadias = Estadia.objects.filter(clave_alojamiento__in=casos_de_clave).values_list(
        "clave_alojamiento", "id", "dispositivo_id", "dispositivo__nombre", "fecha_ingreso"
    )
    resultado = {}
    for clave, estadia_id, dispositivo_id, nombre, desde in estadias:
        alojado = ResponsableAlojado(estadia_id, dispositivo_id, nombre, desde)
        for caso_id in casos_de_clave[clave]:
            resultado[caso_id] = alojado
    return resultado


def responsable_alojado(caso, usuario):
    """El :class:`ResponsableAlojado` del caso, o ``None`` (RN-2.15). **1 consulta.**"""

    return responsables_alojados([caso], usuario).get(caso.pk)
