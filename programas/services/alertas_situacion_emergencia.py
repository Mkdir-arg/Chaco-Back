"""«Necesita atención» de E8: las alertas estratégicas AE-1 a AE-7 (RN-009-09).

Distintas de los siete avisos operativos de E1 (``services.avisos_emergencia``), que no se
mueven ni se repiten acá (RN-009-10). Igual que ellos:

* **Se calculan al leer y no tienen estado**: una alerta deja de aparecer cuando su dato deja de
  cumplir la condición. Son **puras** sobre la foto de ``selectors.emergencia_situacion``: no
  consultan la base ni llaman a ``now()``.
* **Nombran el dato, no enlazan a casos.** Nunca nombran personas; AE-5 nombra el dispositivo
  con su localidad, salvo los de ubicación reservada, que no entran (RN-009-13).
* **Tono e ícono** por severidad: los de ``services.avisos_emergencia`` (``TONOS``, ``ICONOS``).

=====  =====================================================  ========  =====================
Regla  Condición                                              Severidad Alcance con filtro
=====  =====================================================  ========  =====================
AE-1   horas hasta saturar < 12, red saturada o red en nivel  alta      provincial
       Crítica (≥ 80 %)
AE-2   localidades en presión Crítica con ≥ 10 personas       alta      demanda filtrada
       esperando (nombra hasta 3 y «y N más»)
AE-7   personas alojadas con medicación crítica sin dosis     alta      provincial
AE-5   dispositivo Crítica **de su tipo** con derivaciones    alta      provincial
       pendientes; una alerta por dispositivo
AE-3   casos de las últimas 24 h ≥ 20 y ≥ 1,3 × el promedio   media     demanda filtrada
       de las tres 24 h anteriores
AE-4   p90 de un tramo en 24 h > 2 × su objetivo, con ≥ 20    media     demanda filtrada
       casos en la muestra (la de ``tiempos()`` de E1)
AE-6   dispositivos con gente y sin entrega recibida en 48 h  media     provincial
=====  =====================================================  ========  =====================

**Orden** (decisión del PM): alta antes que media; dentro de cada severidad, primero las de la
red en orden de catálogo (AE-1, AE-2, AE-7; AE-3, AE-4, AE-6) y después las AE-5, entre sí por
``porcentaje − umbral rojo`` de su tipo (como B9). A lo sumo :data:`TOPE_ALERTAS`, con el total
para «Mostrando N de M». Con un filtro activo, las provinciales lo dicen: «en toda la provincia».
"""

from programas.selectors.emergencia import TRAMOS, texto_de_minutos
from programas.selectors.emergencia_situacion import (
    VENTANA_DE_ALZA,
    VENTANAS_ANTERIORES_DE_ALZA,
    presion_por_localidad,
    saturacion,
    sin_dosis_provincial,
    sin_entrega_reciente,
    tensionados,
    total_de_la_red,
)
from programas.selectors.emergencia_tablero import muestras_por_tramo, percentil
from programas.services.avisos_emergencia import ICONOS, TONOS
from programas.services.bitacora_detalle import plural
from programas.services.ocupacion import NIVEL_CRITICA, tension_de_ocupacion
from programas.services.situacion_emergencia import (
    HORAS_DEL_RITMO,
    PROYECCION,
    RADIO_CERCANAS_KM,
    SATURADA,
    demanda_en_alza,
)

#: Cuántas alertas muestra «Necesita atención» (RF-009-06).
TOPE_ALERTAS = 6

ALTA = "alta"
MEDIA = "media"

#: AE-1: horas hasta saturar por debajo de esto.
HORAS_DE_SATURACION = 12
#: AE-2: personas esperando mínimas de una localidad crítica, y cuántas nombra.
PERSONAS_LOCALIDAD_CRITICA = 10
LOCALIDADES_NOMBRADAS = 3
#: AE-4: el p90 tiene que superar este múltiplo del objetivo, con al menos estos casos.
MULTIPLO_TRAMO_TRABADO = 2
MINIMO_CASOS_TRAMO = 20

EN_TODA_LA_PROVINCIA = "en toda la provincia"

#: El orden de catálogo dentro de cada severidad; las AE-5 van después de las alta de la red.
ORDEN_DE_CATALOGO = ("AE-1", "AE-2", "AE-7", "AE-5", "AE-3", "AE-4", "AE-6")


def _alerta(regla, severidad, titulo, texto="", *, provincial=False, filtrado=False):
    if provincial and filtrado:
        titulo = f"{titulo}, {EN_TODA_LA_PROVINCIA}"
    return {
        "regla": regla,
        "severidad": severidad,
        "tono": TONOS[severidad],
        "icono": ICONOS[severidad],
        "titulo": titulo,
        "texto": texto,
        "provincial": provincial,
    }


def _lista(nombres):
    """«A», «A y B», «A, B y C»."""

    nombres = list(nombres)
    if len(nombres) <= 1:
        return "".join(nombres)
    return f"{', '.join(nombres[:-1])} y {nombres[-1]}"


# --- AE-1 · saturación --------------------------------------------------------------


def saturacion_de_la_red(foto):
    """AE-1, provincial: la red se satura en menos de 12 h, ya no tiene camas o está Crítica."""

    proyeccion = saturacion(foto)
    tension = tension_de_ocupacion(total_de_la_red(foto))
    if proyeccion.estado == SATURADA:
        titulo = "La red está saturada: no quedan camas libres"
    elif proyeccion.estado == PROYECCION and proyeccion.horas < HORAS_DE_SATURACION:
        titulo = f"La red se satura en ≈ {proyeccion.horas_redondeadas} h al ritmo actual"
    elif tension.nivel == NIVEL_CRITICA:
        titulo = f"La red está en nivel Crítica ({tension.porcentaje} % de ocupación)"
    else:
        return []
    texto = (
        f"En las últimas {HORAS_DEL_RITMO} h ingresaron {plural(proyeccion.ingresos, 'persona', 'personas')} "
        f"y egresaron {proyeccion.egresos}. Quedan {plural(foto.red.libres, 'cama libre', 'camas libres')}."
    )
    return [_alerta("AE-1", ALTA, titulo, texto, provincial=True, filtrado=foto.filtrado)]


# --- AE-2 · localidades críticas ----------------------------------------------------


def localidades_criticas(foto):
    """AE-2, sobre la demanda filtrada: presión Crítica con al menos 10 personas esperando."""

    criticas = [
        fila
        for fila in presion_por_localidad(foto)
        if fila["presion"] is not None
        and fila["presion"].nivel == NIVEL_CRITICA
        and fila["personas"] >= PERSONAS_LOCALIDAD_CRITICA
    ]
    if not criticas:
        return []
    nombradas = [fila["localidad"] for fila in criticas[:LOCALIDADES_NOMBRADAS]]
    resto = len(criticas) - len(nombradas)
    titulo = f"Presión crítica en {plural(len(criticas), 'localidad', 'localidades')}: {_lista(nombradas)}"
    if resto:
        titulo += f", y {resto} más"
    primera = criticas[0]
    camas = primera["cercanas"].total
    hay = f"hay {plural(camas, 'cama libre', 'camas libres')}" if camas else "no hay camas libres"
    texto = (
        f"{primera['localidad']}: {plural(primera['personas'], 'persona espera', 'personas esperan')} "
        f"y {hay} a menos de {RADIO_CERCANAS_KM} km."
    )
    return [_alerta("AE-2", ALTA, titulo, texto)]


# --- AE-7 · medicación crítica sin dosis --------------------------------------------


def medicacion_sin_dosis(foto):
    """AE-7, siempre provincial (RN-009-11): solo el número, sin nombres."""

    cantidad = sin_dosis_provincial(foto)
    if not cantidad:
        return []
    if cantidad == 1:
        titulo = "1 persona alojada con medicación crítica no tiene dosis"
    else:
        titulo = f"{cantidad} personas alojadas con medicación crítica no tienen dosis"
    return [_alerta("AE-7", ALTA, titulo, provincial=True, filtrado=foto.filtrado)]


# --- AE-5 · dispositivo crítico con derivaciones pendientes -------------------------


def dispositivos_criticos_con_pendientes(foto):
    """AE-5, provincial: una alerta por dispositivo Crítica **de su tipo** con derivaciones pendientes.

    Del más al menos tensionado (``porcentaje − umbral rojo``). Los de ubicación reservada no
    entran (``selectors.emergencia_situacion.tensionados`` ya los deja afuera).
    """

    alertas = []
    for fila in tensionados(foto):
        if fila.tension.nivel != NIVEL_CRITICA or not fila.derivaciones_pendientes:
            continue
        dispositivo = fila.dispositivo
        donde = f"{dispositivo.nombre} ({dispositivo.localidad})" if dispositivo.localidad else dispositivo.nombre
        if fila.tension.ocupadas >= fila.tension.operativas:
            estado = "está lleno"
        else:
            estado = f"está en nivel Crítica ({fila.tension.porcentaje} %)"
        pendientes = plural(fila.derivaciones_pendientes, "derivación pendiente", "derivaciones pendientes")
        alertas.append(
            _alerta("AE-5", ALTA, f"{donde} {estado} y tiene {pendientes}", provincial=True, filtrado=foto.filtrado)
        )
    return alertas


# --- AE-3 · demanda en alza ---------------------------------------------------------


def demanda_creciente(foto):
    """AE-3, sobre la demanda filtrada: las últimas 24 h contra el promedio de las tres anteriores."""

    ahora = foto.ahora
    creados = [caso.creado for caso in foto.casos_filtrados]

    def en(n):
        hasta = ahora - VENTANA_DE_ALZA * n
        desde = hasta - VENTANA_DE_ALZA
        return sum(1 for creado in creados if desde <= creado < hasta)

    alza = demanda_en_alza(en(0), [en(n) for n in range(1, VENTANAS_ANTERIORES_DE_ALZA + 1)])
    if not alza.alerta:
        return []
    if alza.porcentaje is None:
        horas = int(VENTANA_DE_ALZA.total_seconds() // 3600) * VENTANAS_ANTERIORES_DE_ALZA
        texto = f"{plural(alza.actual, 'caso nuevo', 'casos nuevos')} en las últimas 24 h; en las {horas} h anteriores no hubo."
    else:
        texto = (
            f"{plural(alza.actual, 'caso nuevo', 'casos nuevos')} en las últimas 24 h, {alza.porcentaje} % más que "
            "el promedio de las tres 24 h anteriores."
        )
    return [_alerta("AE-3", MEDIA, "Casos nuevos en alza", texto)]


# --- AE-4 · tramo trabado -----------------------------------------------------------


def tramos_trabados(foto):
    """AE-4, sobre la demanda filtrada: una alerta por tramo trabado, en el orden del recorrido.

    La muestra es la de ``tiempos()`` de E1 (``emergencia_tablero.muestras_por_tramo``): los
    casos que terminaron el tramo en las últimas 24 h más los que lo tienen en curso, medidos
    hasta ``ahora``, sin ingresos directos salvo en «alojar». El p90 y el mínimo de 20 casos
    salen de esa misma lista (decisión del PM): con menos, un solo caso lento la dispararía.
    """

    muestras = muestras_por_tramo(foto.casos_filtrados, foto.semaforos, foto.ahora)
    alertas = []
    for tramo, _abre, _cierra, campo in TRAMOS:
        valores = muestras[tramo]
        objetivo = getattr(foto.sla, campo)
        if len(valores) < MINIMO_CASOS_TRAMO:
            continue
        p90 = percentil(valores)
        if p90 <= MULTIPLO_TRAMO_TRABADO * objetivo:
            continue
        texto = (
            f"En las últimas 24 h, el 90 % de {len(valores)} casos tardó hasta {texto_de_minutos(int(p90))} "
            f"contra un objetivo de {texto_de_minutos(objetivo)}."
        )
        alertas.append(_alerta("AE-4", MEDIA, f"El tramo «{tramo}» está trabado", texto))
    return alertas


# --- AE-6 · sin entrega en 48 h -----------------------------------------------------


def dispositivos_sin_entrega(foto):
    """AE-6, provincial: dispositivos con gente y sin entrega recibida en 48 h (la cifra de B12)."""

    cantidad = len(sin_entrega_reciente(foto))
    if not cantidad:
        return []
    titulo = (
        f"{plural(cantidad, 'dispositivo', 'dispositivos')} con gente "
        f"{'no recibió' if cantidad == 1 else 'no recibieron'} ninguna entrega en las últimas 48 h"
    )
    return [_alerta("AE-6", MEDIA, titulo, provincial=True, filtrado=foto.filtrado)]


REGLAS = (
    saturacion_de_la_red,
    localidades_criticas,
    medicacion_sin_dosis,
    dispositivos_criticos_con_pendientes,
    demanda_creciente,
    tramos_trabados,
    dispositivos_sin_entrega,
)


def todas_las_alertas(foto):
    """Todas las alertas vigentes, en el orden de «Necesita atención». Sin consultas."""

    alertas = [alerta for regla in REGLAS for alerta in regla(foto)]
    return sorted(alertas, key=lambda a: (a["severidad"] != ALTA, ORDEN_DE_CATALOGO.index(a["regla"])))


def alertas_de_situacion(foto, tope=TOPE_ALERTAS):
    """``{"alertas": [...hasta tope], "total": M}`` para «Mostrando N de M» (RF-009-06). Sin consultas.

    Cada alerta: ``regla``, ``severidad``, ``tono``, ``icono``, ``titulo``, ``texto`` y
    ``provincial`` (las que no siguen el filtro). Listas para ``components/_alerta.html``.
    """

    alertas = todas_las_alertas(foto)
    return {"alertas": alertas[:tope], "total": len(alertas)}
