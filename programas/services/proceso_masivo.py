"""Circuito masivo de Becas: validar en SIIS, aprobar e informar el alta.

Es el mismo camino que los botones de la pantalla de revisión, caso por caso.
Vive acá —y no dentro del comando— porque lo usan dos disparadores: el comando
``procesar_casos_siis`` y la pantalla del proceso masivo. Una segunda
implementación se habría desincronizado con la primera regla que cambiara.
"""

import re
import threading
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Count, Exists, OuterRef, Q, Subquery
from django.utils import timezone

from programas.models import (
    AltaIntermediaSIIS,
    CorridaSiis,
    EnvioSIIS,
    Formulario,
    ProgramaSiis,
    ValidacionSIS,
)
from programas.services.avisos_resolucion import enviar_aviso_resolucion
from programas.services.cupo import CasoEnListaEspera, aprobar_o_poner_en_espera
from programas.services.siis_envio import (
    DESTINO_SIIS,
    DESTINO_TABLA,
    CatalogoNoDisponible,
    Catalogos,
    armar_payload,
    enviar_beneficiario_a_siis,
    guardar_en_tabla_intermedia,
)
from programas.services.validacion_siis import validar_formulario_en_siis

LOTE = 40
# Candidatos mirados entre latido y latido durante la selección. Armar el payload
# de uno son 6-8 consultas: con 7.496 candidatos la selección tarda entre 40 y
# 65 s, y antes no escribía una sola señal de vida en todo ese rato (SIIS-03).
LATIDO_CADA_MIRADOS = 100
MAX_ERRORES = 10
# Resultados **ambiguos** seguidos que detienen la corrida. El tope es más bajo
# que el de errores a propósito: un ERROR técnico no cuesta nada —el caso queda
# libre y se reintenta solo—, mientras que cada INCIERTO deja un caso **tomado**
# que solo se destraba preguntándole a ECOM si el alta llegó. Diez errores
# seguidos son diez reintentos; tres inciertos seguidos ya son tres
# conciliaciones a mano, y señal de que SIIS está contestando mal.
MAX_INCIERTOS = 3
# Casos que se traen de la base por vez al hidratar una lista de ids (abajo).
LOTE_LECTURA = 200
# Ids que se piden por consulta al recorrer la tabla por rangos de pk.
PAGINA_IDS = 2000
# Lo que el circuito lee de cada caso sin volver a la base: lo comparten
# ``candidatos`` y la hidratación por lotes.
SELECT_RELATED_CASOS = ("ciudadano", "relevamiento__convocatoria__segmento__programa", "apoderado_ciudadano")

# Cambio 90: a SIIS solo van los DNI que figuren en esta tabla. La carga el
# organismo desde su planilla, igual que ``ciudadanos_renaper``; una sola
# columna, ``dni``. Sin modelo Django a propósito: es un insumo externo, no un
# dato del sistema.
TABLA_APROBADOS_MATERIAS = "aprobados_materias"


class TablaAprobadosMateriasFaltante(Exception):
    """La tabla que decide quién va a SIIS no está cargada.

    Se corta a propósito en vez de seguir sin filtro: la tabla existe para decidir
    **quién no va**. Si faltara y el proceso mandara a todos igual, cometería
    exactamente el error que la tabla quiere evitar, y un alta en SIIS no se
    deshace desde acá.
    """

    def __init__(self):
        super().__init__(
            f"No existe la tabla `{TABLA_APROBADOS_MATERIAS}`. Cargala primero (una columna `dni`), "
            "o corré con --sin-filtro-materias si de verdad querés mandar a todos."
        )


def _solo_digitos(valor):
    return re.sub(r"\D", "", str(valor or ""))


def dnis_aprobados_materias():
    """DNI habilitados para ir a SIIS, en las dos formas en que pueden estar guardados.

    Devuelve un ``set`` con cada DNI tal cual (solo dígitos), sin ceros a la
    izquierda **y** rellenado a ocho, así el ``IN`` cruza tanto si
    ``Ciudadano.dni`` guarda «07654321» como «7654321». La planilla suele venir de Excel, que se come los ceros; la
    base puede tenerlos. Se lee a memoria y se cruza en SQL por valor, no con un
    JOIN: la tabla la crea un script aparte y puede quedar con otra
    intercalación, y ahí un JOIN falla con «Illegal mix of collations».
    """
    if TABLA_APROBADOS_MATERIAS not in connection.introspection.table_names():
        raise TablaAprobadosMateriasFaltante()
    dnis = set()
    with connection.cursor() as cur:
        # El nombre de la tabla es una constante del módulo, no una entrada
        # externa: no hay vector de inyección (Bandit B608).
        cur.execute(f"SELECT dni FROM `{TABLA_APROBADOS_MATERIAS}`")  # nosec B608
        for (dni,) in cur.fetchall():
            digitos = _solo_digitos(dni)
            if digitos:
                dnis.add(digitos)
                # Sin ceros a la izquierda, por si la base los guarda y la planilla
                # no; y rellenado a 8, por si es al reves (un DNI de 7 digitos que
                # la base guardo como «0» + 7). Ocho es el largo de un DNI actual.
                dnis.add(digitos.lstrip("0") or digitos)
                dnis.add(digitos.zfill(8))
    return dnis


# Contadores que viajan de ``Cuenta`` a ``CorridaSiis`` con el mismo nombre.
CONTADORES = (
    "mirados",
    "elegidos",
    "aprobados",
    "lista_espera",
    "incompatibles",
    "altas",
    "incompletos",
    "rechazados",
    "errores",
)

# Errores técnicos acumulados a partir de los cuales un caso deja de ser
# candidato automático (A2-15, punto 6 de SIIS-02). No es un castigo: un caso que
# falló cinco veces tiene un problema que ninguna corrida va a resolver sola, y
# cada reintento es una llamada a SIIS que le saca lugar a otro.
MAX_REINTENTOS = 5
# Tope del listado que se trae a memoria para excluirlos. Si hubiera más, es que
# SIIS está caído y el problema no son los casos.
TOPE_AGOTADOS = 5000


def casos_con_errores_agotados(tope=TOPE_AGOTADOS):
    """Ids de los casos con ``MAX_REINTENTOS`` o más envíos en ``ERROR``.

    Una sola consulta agrupada sobre ``programas_enviosiis`` (una tabla chica al
    lado de ``programas_formulario``) y la lista vuelve a memoria: un ``IN`` con
    una subconsulta correlacionada acá adentro es justo lo que no entra en el
    ``read_timeout`` de 10 s de la base de ECOM.

    Los que liberó ``conciliar_envios_siis`` **no cuentan**: son ``ERROR`` por
    cómo se guarda la decisión, no por un intento que falló. Si contaran, un caso
    con cuatro errores previos quedaría fuera para siempre justo después de que
    una persona confirmara con ECOM que hay que reenviarlo.
    """
    return list(
        EnvioSIIS.objects.filter(estado=EnvioSIIS.Estado.ERROR)
        .exclude(codigo_error=EnvioSIIS.LIBERADO)
        .values("formulario_id")
        .annotate(intentos=Count("id"))
        .filter(intentos__gte=MAX_REINTENTOS)
        .order_by("formulario_id")
        .values_list("formulario_id", flat=True)[:tope]
    )


# Desenlaces de un caso que cuentan como «SIIS no está sirviendo». Los devuelve
# ``procesar_caso`` y los interpreta :class:`Freno`.
FALLA_TECNICA = "tecnico"
FALLA_INCIERTA = "incierto"


def desenlace_de(envio):
    """Lo que un ``EnvioSIIS`` le dice al freno sobre el estado del servicio.

    Vive acá y no en cada comando porque la pregunta es una sola y la respuesta
    tiene que ser la misma en las cuatro vías (RED-53): un ``INCIERTO`` que
    acaba de intentarse es una falla —y de las caras—; uno que ya estaba, no,
    porque ahí no se llamó a SIIS.
    """
    if envio.estado == EnvioSIIS.Estado.ERROR:
        return FALLA_TECNICA
    if envio.estado == EnvioSIIS.Estado.INCIERTO and envio.recien_intentado:
        return FALLA_INCIERTA
    return None


@dataclass
class Freno:
    """Corta la corrida cuando SIIS deja de servir. Único para las tres vías.

    Lleva **dos rachas en paralelo**, no una:

    * ``tecnicos`` — el caso quedó libre y se reintenta solo. Diez seguidos
      significan «SIIS está caído»: no hay nada que ganar insistiendo.
    * ``inciertos`` — el POST pudo haber llegado y el caso queda **tomado**
      hasta que alguien le pregunte a ECOM. Son caros: el tope es más bajo.

    Una falla **no** resetea la racha de la otra: con SIIS devolviendo 500 y
    timeouts alternados, un solo contador que se pisa entre sí no llega nunca al
    tope y la corrida sigue golpeando un servicio caído (que es lo que pasaba
    cuando el INCIERTO contaba como «no es un error» y reseteaba el contador).
    Solo un desenlace sano —un alta hecha, un rechazo de datos, un caso que ya
    estaba tomado— vuelve las dos a cero.
    """

    max_errores: int = MAX_ERRORES
    max_inciertos: int = MAX_INCIERTOS
    tecnicos: int = 0
    inciertos: int = 0

    def registrar(self, desenlace):
        """Suma el desenlace y devuelve ``True`` si hay que cortar."""
        if desenlace == FALLA_TECNICA:
            self.tecnicos += 1
        elif desenlace == FALLA_INCIERTA:
            self.inciertos += 1
        else:
            self.tecnicos = 0
            self.inciertos = 0
        return self.corta

    @property
    def corta(self):
        return self.tecnicos >= self.max_errores or self.inciertos >= self.max_inciertos

    @property
    def motivo(self):
        """Qué contar en el mensaje de corte, en el orden en que importa.

        Lo lee el coordinador en la pantalla del proceso masivo y el operador en
        la consola, así que dice qué pasó y qué hacer, no el nombre del estado.
        """
        if self.inciertos >= self.max_inciertos:
            return (
                f"{self.inciertos} envíos seguidos sin saber si el alta llegó. SIIS contesta mal o no "
                "contesta, y cada uno de esos casos queda tomado: hay que preguntarle a ECOM si esas "
                "altas llegaron (`manage.py conciliar_envios_siis --listar`) antes de volver a correr"
            )
        return f"{self.tecnicos} errores técnicos seguidos. SIIS no está respondiendo o las credenciales no sirven"


@dataclass
class Cuenta:
    """Los desenlaces de una corrida. Se acumulan y se vuelcan a ``CorridaSiis``."""

    mirados: int = 0
    elegidos: int = 0
    aprobados: int = 0
    lista_espera: int = 0
    # SIIS contestó que la persona no es compatible con el programa. No se
    # aprueban ni se informan: los mira una persona (BEC-11).
    incompatibles: int = 0
    no_aprobable: int = 0
    # Ya los tiene otro camino (un envío EN_PROCESO o INCIERTO de antes) o ya se
    # informó a la misma persona en el mismo plan desde otro caso
    # (DUPLICADO_LOCAL). Ninguno de los dos es una falla de SIIS.
    ocupados: int = 0
    duplicados: int = 0
    # Intentos de **esta** corrida que quedaron sin saber si el alta llegó. Sí
    # son una falla de SIIS, y la más cara: cada uno pide una conciliación.
    inciertos: int = 0
    # Entró a la lista de espera entre la selección y su turno (el selector ya
    # los deja afuera). No viaja a ``CorridaSiis``: no hay columna para él.
    ya_en_espera: int = 0
    sin_datos: int = 0
    error_validacion: int = 0
    altas: int = 0
    incompletos: int = 0
    rechazados: int = 0
    errores: int = 0
    # Altas que quedaron en la tabla intermedia de este lado, sin ir a SIIS.
    guardadas: int = 0
    descartados: dict = field(default_factory=dict)


def _solo_los_aprobables(casos):
    """Saca los ``ENVIADO`` que la aprobación va a rechazar igual (BEC-21).

    ``motivo_bloqueo_aprobacion`` exige identidad validada y un ciudadano con DNI.
    Un caso sin eso entraba igual a la corrida: se le consultaba la
    compatibilidad a SIIS —hasta 40 s—, se intentaba aprobarlo, saltaba el
    ``ValidationError`` y se contaba como «no se pudo aprobar». Tres pasos para
    llegar a lo que se sabía desde la consulta.

    Solo aplica a los ``ENVIADO``: un ``APROBADO`` ya pasó por ese gate y lo que
    le falta es el alta, que no vuelve a mirar la identidad.
    """
    return casos.exclude(
        Q(estado=Formulario.Estado.ENVIADO)
        & (Q(validado_renaper=False) | Q(ciudadano__isnull=True) | Q(ciudadano__dni=""))
    )


def _sin_pausa_vigente(casos):
    """Saca los casos cuyo relevamiento, convocatoria, segmento o programa está pausado.

    Pausar frena la carga en campo y la operación de la pantalla, pero el masivo
    no la miraba: una convocatoria pausada seguía aprobando e informando altas en
    lote, que es lo contrario de lo que pausar quiere decir.

    Se comparan las columnas ``pausado`` de la cadena, que ya viene unida por los
    ``select_related``, y no ``pausa_efectiva``, que es una propiedad de Python.
    Queda afuera a propósito el bloqueo derivado del estado del programa en SIIS:
    hoy un catálogo vacío deja todos los programas en ``DESCONOCIDO`` (SIIS-06,
    abierto), y colgarle esto encima frenaría el masivo entero por un error de
    SIIS en vez de por una decisión de alguien.
    """
    return casos.exclude(
        Q(relevamiento__pausado=True)
        | Q(relevamiento__convocatoria__pausado=True)
        | Q(relevamiento__convocatoria__segmento__pausado=True)
        | Q(relevamiento__convocatoria__subsegmento__pausado=True)
        | Q(relevamiento__convocatoria__segmento__programa__pausado=True)
    )


def candidatos(
    *,
    programa=None,
    convocatoria=None,
    relevamiento=None,
    segmento=None,
    solo_enviar=False,
    filtrar_materias=True,
    destino=DESTINO_SIIS,
):
    """Casos que todavía no se informaron a SIIS.

    Los ``ENVIADO`` (pendientes de resolución) y los ya ``APROBADO`` sin alta,
    para que una corrida cortada se retome sola. Se saltean los que tienen un
    conflicto de carga duplicada sin resolver: eso lo decide una persona, igual
    que en la pantalla de revisión. También los ``ENVIADO`` que están en una
    lista de espera: se aprueban promoviéndolos desde Cupo (CMP-N1), así que
    consultarlos a SIIS y contarlos como pendientes no lleva a nada.

    Con ``filtrar_materias`` (el default) solo entran los DNI de
    ``aprobados_materias`` (Cambio 90). Si la tabla no existe, lanza
    ``TablaAprobadosMateriasFaltante`` en vez de devolver a todos.

    Con ``destino="tabla"`` se saltean además los que ya están guardados en la
    tabla intermedia sin sincronizar: guardarlos no deja ``EnvioSIIS``, así que
    sin esto volverían a salir como candidatos en cada vuelta y una corrida por
    tandas no terminaría nunca.

    Tampoco entran los casos con un envío **vigente** (SIIS-01): uno ya informado,
    uno con el POST en vuelo o uno de resultado incierto. Ni los que acumularon
    ``MAX_REINTENTOS`` errores técnicos: insistir con ellos gasta la corrida y
    tapa los que sí pueden salir (A2-15).

    Ni los que no se van a poder aprobar ni los que están pausados (BEC-21): ver
    :func:`_solo_los_aprobables` y :func:`_sin_pausa_vigente`.
    """
    ultimo = EnvioSIIS.objects.filter(formulario=OuterRef("pk")).order_by("-creado", "-id").values("estado")[:1]
    vigente = EnvioSIIS.objects.filter(formulario=OuterRef("pk"), vigente=True)
    casos = (
        Formulario.objects.select_related(*SELECT_RELATED_CASOS)
        .annotate(ultimo_envio=Subquery(ultimo))
        # «Todavía no informado» incluye a los que no tienen ningún envío, y eso
        # es NULL: un ``exclude`` los descartaría a todos, porque
        # ``NOT (NULL = 'ENVIADO')`` no es verdadero.
        #
        # El filtro por ``ultimo_envio`` se queda junto al de ``vigente`` a
        # propósito: durante el deploy puede haber filas ``ENVIADO`` escritas por
        # el código viejo, que nacen con ``vigente = NULL`` (expand/contract).
        .filter(Q(ultimo_envio__isnull=True) | ~Q(ultimo_envio=EnvioSIIS.Estado.ENVIADO))
        # NOT EXISTS contra el índice único ``(formulario, vigente)``: una
        # búsqueda exacta por caso, no el scan por fila de un ``Exists`` sobre
        # una FK casi siempre nula.
        .filter(~Exists(vigente))
        .order_by("pk")
    )
    agotados = casos_con_errores_agotados()
    if agotados:
        casos = casos.exclude(pk__in=agotados)
    estados = [Formulario.Estado.APROBADO]
    if not solo_enviar:
        estados.append(Formulario.Estado.ENVIADO)
    casos = casos.filter(estado__in=estados)
    if programa is not None:
        casos = casos.filter(relevamiento__convocatoria__segmento__programa=programa)
    if convocatoria is not None:
        casos = casos.filter(relevamiento__convocatoria_id=convocatoria)
    if relevamiento is not None:
        casos = casos.filter(relevamiento_id=relevamiento)
    if segmento is not None:
        casos = casos.filter(relevamiento__convocatoria__segmento_id=segmento)
    casos = casos.exclude(Q(conflicto_duplicado=True) & Q(conflicto_resuelto=False)).exclude(
        cargas_en_conflicto__conflicto_resuelto=False
    )
    casos = _sin_pausa_vigente(_solo_los_aprobables(casos))
    # Solo el ENVIADO: un APROBADO con una fila de espera colgando (datos previos
    # a la regla) igual tiene que informarse a SIIS.
    casos = casos.exclude(estado=Formulario.Estado.ENVIADO, lista_espera__promovido=False)
    if filtrar_materias:
        casos = casos.filter(ciudadano__dni__in=dnis_aprobados_materias())
    if destino == DESTINO_TABLA:
        # Con ``Exists`` sobre la clave foránea, que está indexada: un ``pk__in``
        # con miles de ids contra la base de ECOM no entra en su read_timeout.
        guardado = AltaIntermediaSIIS.objects.filter(formulario=OuterRef("pk"), sincronizado=False)
        casos = casos.exclude(Exists(guardado))
    # Sin ``distinct()``: nada acá multiplica filas (los ``select_related`` son
    # claves foráneas hacia adelante y el conflicto de carga se excluye con una
    # subconsulta), así que cada caso ya sale una sola vez. Con DISTINCT, en
    # cambio, MySQL materializaba los 20.000 candidatos enteros --con sus
    # columnas JSON-- en una tabla temporal antes de ordenar y cortar: 3,8 s
    # para un ``count()`` en el banco (la pantalla del proceso masivo) y de 2,9
    # a 4,4 s para ``[:1000]``; sin él, 0,1 s el ``count()``.
    return casos


def ids_de(casos, limite=None, pagina=PAGINA_IDS):
    """Solo los ids de ``casos`` (un queryset de :func:`candidatos`), en orden de pk.

    Se piden **por rangos de pk**, no de una sola vez. ``programas_formulario``
    pesa 283 MB —la foto del formulario son 27 KB por caso— y en InnoDB el índice
    primario *es* la tabla: un ``SELECT id ... ORDER BY id`` sin acotar recorre
    los 283 MB enteros y no entra en el ``read_timeout`` de 10 s de ECOM. El
    síntoma es engañoso, porque depende de cuánta I/O esté haciendo el servidor:
    el mismo comando entra si pasaron unos minutos desde el anterior y muere con
    «Lost connection» si se lanza enseguida. Con ``WHERE pk > N LIMIT pagina``
    cada consulta lee un trozo acotado y el tiempo deja de depender de eso.
    """
    recogidos = []
    ultimo = 0
    while True:
        falta = (limite - len(recogidos)) if limite else None
        if falta is not None and falta <= 0:
            break
        tramo = casos.filter(pk__gt=ultimo).order_by("pk").values_list("pk", flat=True)
        tramo = list(tramo[: min(pagina, falta) if falta else pagina])
        if not tramo:
            break
        recogidos.extend(tramo)
        ultimo = tramo[-1]
    return recogidos


def hidratar(ids):
    """Los casos completos de ``ids``, en orden de pk y con las relaciones que
    lee el circuito ya cargadas (las mismas que :func:`candidatos`)."""
    return list(Formulario.objects.select_related(*SELECT_RELATED_CASOS).filter(pk__in=ids).order_by("pk"))


def hidratar_por_lotes(ids, tamano=LOTE_LECTURA):
    """Recorre los casos de ``ids`` trayéndolos de a ``tamano``.

    Traerlos todos de una vez --``list(candidatos(...))``-- era pedirle a MySQL
    los 20.000 candidatos con ``data``, ``respuestas`` y ``definicion`` (unos
    7 KB por caso) en una sola consulta: 12,5 s de SQL en el banco, y contra la
    base de ECOM eso muere por ``read_timeout`` (10 s) antes de devolver nada.
    Una lista de ids vuelve en 100 ms y cada lote de 200 en 11 ms. Quien itera
    puede cortar cuando junta lo que necesita, sin haber leído el resto.
    """
    for inicio in range(0, len(ids), tamano):
        yield from hidratar(ids[inicio : inicio + tamano])


def elegir_completos(casos, catalogos, total, cuenta, *, al_mirar=None):
    """``(elegidos, descartados_por_campo)``: los que hoy saldrían sin faltantes.

    El total cuenta casos que se **mandan**, no casos que se miran: se recorre
    hasta juntarlos, salteando sin tocar a los que les falta un dato. Mandar uno
    incompleto no lo informa a SIIS pero igual lo deja aprobado y con una fila de
    error para revisar a mano.

    ``al_mirar`` se llama cada ``LATIDO_CADA_MIRADOS`` candidatos. Lo usa la
    corrida para latir: esto puede tardar más de un minuto y mientras tanto nadie
    sabía si seguía viva (SIIS-03).
    """
    elegidos, descartados = [], {}
    for caso in casos:
        if len(elegidos) >= total:
            break
        cuenta.mirados += 1
        if al_mirar is not None and cuenta.mirados % LATIDO_CADA_MIRADOS == 0:
            al_mirar()
        _, faltantes = armar_payload(caso, catalogos=catalogos)
        if faltantes:
            for campo in faltantes:
                descartados[campo] = descartados.get(campo, 0) + 1
            continue
        elegidos.append(caso)
        cuenta.elegidos += 1
    cuenta.descartados = descartados
    return elegidos, descartados


def procesar_caso(caso, responsable, catalogos, cuenta, *, avisar=False, solo_enviar=False, destino=DESTINO_SIIS):
    """Valida, aprueba e informa un caso. Devuelve ``"tecnico"`` si falló SIIS.

    Un caso que falla en un paso no avanza al siguiente y no interrumpe al resto.
    """
    if not solo_enviar:
        try:
            validacion = validar_formulario_en_siis(caso, responsable)
        except ValueError:
            # Sin programa SIIS o sin DNI: no hay consulta posible.
            cuenta.sin_datos += 1
            return None
        if validacion.estado == ValidacionSIS.Estado.ERROR:
            cuenta.error_validacion += 1
            return "tecnico"
        if validacion.estado == ValidacionSIS.Estado.RECHAZADO:
            # BEC-11 (D-B11): SIIS dice que la persona no es compatible con el
            # programa. En la pantalla del caso eso es una advertencia y la
            # decisión la toma el revisor (Cambio 81); acá no hay revisor, así
            # que el caso queda como está y lo mira alguien. No es una falla de
            # SIIS: el servicio contestó, y bien.
            cuenta.incompatibles += 1
            return None

        if caso.estado == Formulario.Estado.ENVIADO:
            try:
                resultado = aprobar_o_poner_en_espera(caso, responsable)
            except CasoEnListaEspera:
                cuenta.ya_en_espera += 1
                return None
            except ValidationError:
                # Falta algo que la aprobación exige (identidad, validación que
                # no corresponde al programa actual…).
                cuenta.no_aprobable += 1
                return None
            if resultado == "lista_espera":
                # Sin cupo no hay beneficiario que informar.
                cuenta.lista_espera += 1
                if avisar:
                    enviar_aviso_resolucion(caso, resultado)
                return None
            cuenta.aprobados += 1
            if avisar:
                enviar_aviso_resolucion(caso, resultado)

    try:
        if destino == DESTINO_TABLA:
            # El alta se guarda de este lado y no se llama a la API. El caso sigue
            # siendo candidato hasta que llegue a SIIS de verdad: la fila guardada
            # es una copia para revisar, no un alta hecha.
            alta, envio = guardar_en_tabla_intermedia(caso, responsable, catalogos=catalogos)
            if alta is not None:
                cuenta.guardadas += 1
                return None
            if envio is None:
                return None
        else:
            envio = enviar_beneficiario_a_siis(caso, responsable, catalogos=catalogos)
    except ValueError:
        # SIIS-04: el estado releído bajo lock ya no habilita el envío. El caso
        # cambió entre que se hidrató y su turno (una baja, un rechazo): no se
        # informa, y eso no es un error técnico.
        cuenta.no_aprobable += 1
        return None
    if envio.estado == EnvioSIIS.Estado.ENVIADO:
        cuenta.altas += 1
    elif envio.estado == EnvioSIIS.Estado.INCOMPLETO:
        cuenta.incompletos += 1
    elif desenlace_de(envio) == FALLA_INCIERTA:
        # Lo intentamos y no sabemos si llegó: es una falla de SIIS, y de las
        # caras. Que no cuente para el freno era dejar la corrida sin salida con
        # el servicio caído, porque 500, 502, 504 y ReadTimeout son INCIERTO.
        cuenta.inciertos += 1
        return FALLA_INCIERTA
    elif envio.estado in (EnvioSIIS.Estado.EN_PROCESO, EnvioSIIS.Estado.INCIERTO):
        # Lo tenía tomado otro camino desde antes: no se llamó a SIIS, así que no
        # dice nada sobre el estado del servicio.
        cuenta.ocupados += 1
    elif envio.estado == EnvioSIIS.Estado.RECHAZADO:
        if envio.codigo_error == "DUPLICADO_LOCAL":
            cuenta.duplicados += 1
        else:
            cuenta.rechazados += 1
    else:
        cuenta.errores += 1
        return FALLA_TECNICA
    return None


# ---------------------------------------------------------------------------
# Corrida
# ---------------------------------------------------------------------------
def _tomar_candado():
    """Bloquea la fila centinela hasta que cierre la transacción.

    La centinela es el ``ProgramaSiis`` de menor pk, y es global a propósito:
    ``CorridaSiis.en_curso()`` mira **todas** las corridas, no las de un
    programa, así que un candado por programa dejaría pasar dos lanzamientos
    sobre programas distintos. La fila siempre existe —se lanza desde un
    ``ProgramaSiis``— y el candado se suelta en el commit, que acá está a dos
    consultas de distancia.
    """
    return ProgramaSiis.objects.select_for_update().order_by("pk").values_list("pk", flat=True).first()


class CorridaEnCurso(Exception):
    """Hay una corrida viva y lo que se iba a hacer la pisaría.

    La levantan los comandos que hablan con SIIS caso por caso: el hilo del
    masivo y un comando a mano procesan los mismos casos, comparten el freno por
    errores seguidos —si SIIS se pone lento, ninguno de los dos corta a tiempo— y
    el alta no tiene baja.
    """

    def __init__(self, corrida):
        self.corrida = corrida
        desde = timezone.localtime(corrida.creado).strftime("%H:%M")
        super().__init__(
            f"Hay una corrida masiva en curso (#{corrida.pk}, {corrida.programa.nombre}, desde las {desde}). "
            "Correr esto en paralelo procesa los mismos casos y comparte el freno por errores seguidos. "
            "Esperá a que termine o frenala desde la pantalla del proceso masivo; "
            "si de verdad hace falta ahora, agregá --ignorar-corrida."
        )


def exigir_sin_corrida_viva():
    """Lanza :class:`CorridaEnCurso` si la pantalla está corriendo una (SIIS-03).

    Se pregunta **con el candado tomado**, el mismo que toma ``crear_corrida``:
    si no, un comando lanzado en el mismo segundo que la pantalla lee la tabla
    antes de que la corrida se commitee —la base corre en READ COMMITTED—, no ve
    nada y arranca igual.
    """
    with transaction.atomic():
        _tomar_candado()
        corrida = CorridaSiis.en_curso()
        if corrida is not None:
            raise CorridaEnCurso(corrida)


def _retirar_las_interrumpidas(nueva):
    """Cierra las ``EN_CURSO`` que ya no late nadie, en vez de dejarlas colgadas.

    Se llama con el candado tomado y después de comprobar que no hay ninguna
    viva: cualquier otra ``EN_CURSO`` que quede es, por definición, una que se
    quedó sin señal. Dejarlas abiertas era lo que mostraba dos corridas «en
    curso» a la vez y hacía imposible saber cuál era la de verdad.
    """
    for vieja in CorridaSiis.objects.filter(estado=CorridaSiis.Estado.EN_CURSO).exclude(pk=nueva.pk):
        desde = timezone.localtime(vieja.latido or vieja.creado).strftime("%H:%M")
        CorridaSiis.objects.filter(pk=vieja.pk).update(
            estado=CorridaSiis.Estado.DETENIDA,
            finalizada=timezone.now(),
            mensaje=f"Interrumpida: sin señal desde las {desde}; la reemplaza la corrida #{nueva.pk}.",
        )


def crear_corrida(*, programa, solicitada_por, total_pedido):
    """La corrida nueva, o ``None`` si ya había una viva.

    Entre preguntar ``en_curso()`` y crear la fila hay una ventana: con un
    segundo de latencia, dos pestañas —o dos personas— lanzaban dos corridas
    EN_CURSO a la vez y los dos hilos procesaban los mismos casos, aprobándolos
    e informándolos a SIIS por duplicado. Acá el chequeo pasa a hacerse con el
    candado ya tomado, así el segundo request lee la corrida del primero (la
    base corre en READ COMMITTED: al soltarse el candado, la lectura siguiente
    ve lo que el otro commiteó) y se va sin escribir nada.

    Devuelve ``None`` en vez de lanzar para no abortar la transacción: lo único
    que hay dentro es la lectura del candado, y un rollback acá no aporta nada.
    """
    with transaction.atomic():
        _tomar_candado()
        if CorridaSiis.en_curso() is not None:
            return None
        nueva = CorridaSiis.objects.create(programa=programa, solicitada_por=solicitada_por, total_pedido=total_pedido)
        _retirar_las_interrumpidas(nueva)
        return nueva


def _lotes(lista, tamano):
    for inicio in range(0, len(lista), tamano):
        yield lista[inicio : inicio + tamano]


def _latir(corrida):
    """Deja la señal de vida, y nada más.

    Un ``UPDATE`` de una columna: es lo más barato que se puede hacer por caso, y
    tiene que ser barato porque se hace por caso. No usa ``save()`` a propósito,
    igual que :func:`_guardar`: escribir el objeto en memoria pisaría
    ``cancelacion_pedida``, que lo marca otro request.
    """
    CorridaSiis.objects.filter(pk=corrida.pk).update(latido=timezone.now())


def _guardar(corrida, cuenta, **extra):
    """Vuelca los contadores y el latido. Cada lote deja su rastro en la base.

    Escribe **solo** los campos que toca. Un ``save()`` completo pisaría
    ``cancelacion_pedida`` con el valor que este proceso tiene en memoria, y
    quien apretó Frenar lo escribió desde otro request: el freno se perdería en
    el siguiente latido.
    """
    for campo in CONTADORES:
        setattr(corrida, campo, getattr(cuenta, campo))
    corrida.latido = timezone.now()
    for campo, valor in extra.items():
        setattr(corrida, campo, valor)
    corrida.save(update_fields=[*CONTADORES, "latido", *extra.keys(), "modificado"])


def correr(
    corrida, *, responsable=None, catalogos=None, lote=LOTE, max_errores=MAX_ERRORES, max_inciertos=MAX_INCIERTOS
):
    """Ejecuta la corrida y va escribiendo su avance. **Nunca lanza.**

    Todo desenlace —incluida una excepción que no previmos— queda escrito en la
    corrida. Corre en un hilo: si dejara escapar una excepción, nadie la vería y
    la pantalla quedaría con una corrida «en curso» para siempre.

    No hay una transacción que envuelva todo a propósito. Cada caso se confirma
    solo; eso es lo que permite cortar y retomar, y lo que evita el cuelgue de
    una transacción larga contra una base remota.
    """
    catalogos = catalogos or Catalogos()
    cuenta = Cuenta()
    responsable = responsable or corrida.solicitada_por
    try:
        # Antes de la primera consulta: la selección sola puede tardar más de un
        # minuto y hasta acá la corrida no había dado ninguna señal (SIIS-03).
        _latir(corrida)
        pendientes = hidratar_por_lotes(ids_de(candidatos(programa=corrida.programa)))
        casos, _ = elegir_completos(
            pendientes, catalogos, corrida.total_pedido, cuenta, al_mirar=lambda: _latir(corrida)
        )
        _guardar(corrida, cuenta)

        freno = Freno(max_errores=max_errores, max_inciertos=max_inciertos)
        for grupo in _lotes(casos, max(1, lote)):
            for caso in grupo:
                # El freno se mira por caso y no al final del lote: con SIIS
                # caído, esperar a los 40 del lote son 40 llamadas de más (y, si
                # son inciertas, 40 casos tomados).
                if freno.registrar(procesar_caso(caso, responsable, catalogos, cuenta)):
                    break
                # Lo mismo vale para el freno de la persona y para el latido: un
                # caso son hasta tres llamadas a SIIS, así que al final del lote
                # pueden haber pasado 26 minutos (SIIS-03).
                _latir(corrida)
                corrida.refresh_from_db(fields=["cancelacion_pedida", "estado"])
                if corrida.estado != CorridaSiis.Estado.EN_CURSO:
                    # Otra corrida nos dio por interrumpidos y nos reemplazó. El
                    # hilo se retira sin escribir: pisar el estado con el nuestro
                    # haría aparecer «terminada» a una corrida que ya no es.
                    return corrida
                if corrida.cancelacion_pedida:
                    _guardar(
                        corrida,
                        cuenta,
                        estado=CorridaSiis.Estado.CANCELADA,
                        finalizada=timezone.now(),
                        mensaje="La frenaron desde la pantalla. Lo procesado quedó firme.",
                    )
                    return corrida
            _guardar(corrida, cuenta)
            if freno.corta:
                _guardar(
                    corrida,
                    cuenta,
                    estado=CorridaSiis.Estado.DETENIDA,
                    finalizada=timezone.now(),
                    mensaje=f"Se detuvo tras {freno.motivo}. Lo hecho quedó; volvé a lanzarla cuando se recupere.",
                )
                return corrida

        _guardar(corrida, cuenta, estado=CorridaSiis.Estado.TERMINADA, finalizada=timezone.now())
        return corrida
    except CatalogoNoDisponible as exc:
        _guardar(
            corrida,
            cuenta,
            estado=CorridaSiis.Estado.DETENIDA,
            finalizada=timezone.now(),
            mensaje=f"No se pudo leer un catálogo de SIIS: {exc}",
        )
        return corrida
    except TablaAprobadosMateriasFaltante as exc:
        _guardar(corrida, cuenta, estado=CorridaSiis.Estado.DETENIDA, finalizada=timezone.now(), mensaje=str(exc))
        return corrida
    except Exception as exc:  # noqa: BLE001 - la corrida es el único lugar donde se puede informar
        _guardar(
            corrida,
            cuenta,
            estado=CorridaSiis.Estado.DETENIDA,
            finalizada=timezone.now(),
            mensaje=f"Error no previsto: {exc}",
        )
        return corrida


def _en_un_hilo(funcion):
    threading.Thread(target=funcion, daemon=True).start()


def lanzar(corrida, *, responsable=None, ejecutor=None):
    """Arranca la corrida sin hacer esperar al request.

    ``ejecutor`` se inyecta para poder correr sincrónico en los tests: con el
    hilo de verdad, las pruebas serían una carrera.
    """

    def trabajo():
        try:
            correr(corrida, responsable=responsable)
        finally:
            # Django abre una conexión por hilo; sin esto queda colgada.
            connection.close()

    (ejecutor or _en_un_hilo)(trabajo)
