"""Reglas puras de la foto de situación de Emergencia (E8, análisis 009 §5.2).

Nada de acá consulta la base ni llama a ``now()``: reciben números (o filas ya leídas) y
devuelven el resultado. El selector ``programas.selectors.emergencia_situacion`` solo lee y
agrega; la decisión de qué nivel tiene una localidad, cuándo se satura la red, qué camas
quedan cerca o qué del perfil se puede mostrar con un filtro se toma acá, una sola vez.

* :func:`nivel_de_presion` — RN-009-06.
* :func:`horas_hasta_saturar` — RN-009-07.
* :func:`camas_cercanas` — RN-009-05 (25 km, ambigüedad contra todas las ``core.Localidad``).
* :func:`demanda_en_alza` — la comparación de AE-3 (RN-009-09), con aritmética entera.
* :func:`presentar_perfil` — RN-009-11 (salud solo provincial con filtro; «menos de 5»).
"""

from typing import Any, NamedTuple

from core.services.ubicaciones_localidades import LATITUD_CHACO, LONGITUD_CHACO, clave
from programas.selectors.emergencia import distancia_km
from programas.services.ocupacion import (
    NIVEL_CRITICA,
    NIVEL_EXIGIDA,
    NIVEL_NORMAL,
    NIVEL_SIN_PLAZAS,
    Tension,
)
from programas.services.ubicacion_reservada import separar_por_ubicacion_reservada

# ---------------------------------------------------------------------------
# Presión por localidad (RN-009-06)
# ---------------------------------------------------------------------------

#: Una localidad sin personas esperando. Los otros tres niveles son los de la tensión de
#: ocupación (``services.ocupacion``): mismo vocabulario y mismos tonos (RNF-009-09).
NIVEL_SIN_DEMANDA = "sin_demanda"

_ETIQUETAS_DE_PRESION = {
    NIVEL_CRITICA: "Crítica",
    NIVEL_EXIGIDA: "Exigida",
    NIVEL_NORMAL: "Normal",
    NIVEL_SIN_DEMANDA: "Sin demanda",
}

#: Del más grave al menos: para ordenar filas y la lista «Localidades con más presión».
ORDEN_DE_PRESION = (NIVEL_CRITICA, NIVEL_EXIGIDA, NIVEL_NORMAL, NIVEL_SIN_DEMANDA)


class Presion(NamedTuple):
    """El nivel de presión de una localidad y su cociente (``None`` sin camas o sin demanda)."""

    nivel: str
    cociente: float | None

    @property
    def etiqueta(self) -> str:
        return _ETIQUETAS_DE_PRESION[self.nivel]

    @property
    def tono(self) -> str:
        """El tono de la tensión de ocupación del mismo nivel; «Sin demanda» usa el de «Sin plazas»."""

        nivel = NIVEL_SIN_PLAZAS if self.nivel == NIVEL_SIN_DEMANDA else self.nivel
        return Tension(ocupadas=None, operativas=0, porcentaje=None, nivel=nivel).tono

    @property
    def sin_camas_cercanas(self) -> bool:
        """Crítica sin cociente: hay gente esperando y ninguna cama a 25 km."""

        return self.nivel == NIVEL_CRITICA and self.cociente is None


def nivel_de_presion(esperando: int, camas_cercanas: int) -> Presion:
    """Personas esperando sobre camas libres cercanas (RN-009-06).

    * **Sin demanda**: 0 esperando.
    * **Crítica**: más esperando que camas (cociente > 1), o esperando y 0 camas cercanas.
    * **Exigida**: cociente ≥ 0,5. **Normal**: < 0,5.

    Las comparaciones son enteras (``2 × esperando ≥ camas``): el borde de 0,5 no depende de un
    redondeo de coma flotante. ``nivel_de_presion(12, 5)`` es Crítica (2,4×);
    ``nivel_de_presion(10, 10)``, Exigida.
    """

    esperando, camas = max(int(esperando), 0), max(int(camas_cercanas), 0)
    if esperando == 0:
        return Presion(NIVEL_SIN_DEMANDA, None)
    if camas == 0:
        return Presion(NIVEL_CRITICA, None)
    cociente = esperando / camas
    if esperando > camas:
        return Presion(NIVEL_CRITICA, cociente)
    if 2 * esperando >= camas:
        return Presion(NIVEL_EXIGIDA, cociente)
    return Presion(NIVEL_NORMAL, cociente)


# ---------------------------------------------------------------------------
# Horas hasta saturar (RN-009-07)
# ---------------------------------------------------------------------------

#: Las últimas horas sobre las que se mide el ritmo de ingresos y egresos en camas.
HORAS_DEL_RITMO = 6

SATURADA = "saturada"
NO_SE_SATURA = "no_se_satura"
PROYECCION = "proyeccion"
#: Sin casos en el programa: el indicador muestra «—» (análisis 009 §3.8 y §7).
SIN_DATOS = "sin_datos"


class Saturacion(NamedTuple):
    """Cuándo se llena la red al ritmo actual. ``horas`` solo en :data:`PROYECCION`.

    ``ritmo_por_hora`` es el neto (ingresos − egresos) / horas: positivo, la red se llena.
    """

    estado: str
    horas: float | None
    ritmo_por_hora: float
    ingresos: int
    egresos: int
    disponibles: int

    @property
    def horas_redondeadas(self) -> int | None:
        return None if self.horas is None else int(round(self.horas))


def horas_hasta_saturar(disponibles: int, ingresos: int, egresos: int, horas: int = HORAS_DEL_RITMO) -> Saturacion:
    """``disponibles / ritmo_neto``, con el ritmo de las últimas ``horas`` (RN-009-07).

    * Sin camas libres: **red saturada**.
    * Ritmo neto ≤ 0 (egresan tantas o más de las que ingresan): **no se satura al ritmo actual**.
    * Si no, la proyección en horas: ``horas_hasta_saturar(40, 12, 2, 6)`` son 24 h. Es una
      proyección al ritmo actual, no un pronóstico; la pantalla lo rotula.
    """

    disponibles, ingresos, egresos = max(int(disponibles), 0), int(ingresos), int(egresos)
    ritmo = (ingresos - egresos) / horas
    if disponibles == 0:
        return Saturacion(SATURADA, None, ritmo, ingresos, egresos, disponibles)
    if ingresos <= egresos:
        return Saturacion(NO_SE_SATURA, None, ritmo, ingresos, egresos, disponibles)
    return Saturacion(PROYECCION, disponibles * horas / (ingresos - egresos), ritmo, ingresos, egresos, disponibles)


def sin_datos_de_saturacion(disponibles: int, ingresos: int, egresos: int) -> Saturacion:
    """El indicador cuando el programa no tiene casos: «—», sin proyección ni alerta."""

    return Saturacion(SIN_DATOS, None, 0.0, int(ingresos), int(egresos), max(int(disponibles), 0))


# ---------------------------------------------------------------------------
# Camas libres cercanas (RN-009-05)
# ---------------------------------------------------------------------------

#: Radio de «camas cercanas» (pregunta 2 del análisis, resuelta por el PM).
RADIO_CERCANAS_KM = 25


def ubicacion_valida(latitud, longitud) -> bool:
    """¿Las coordenadas existen y caen en la caja del Chaco ± 0,5° de E-2 (análisis 009 §7)?

    Una coordenada fuera de la caja es un error de carga: el dispositivo cuenta como «sin ubicación».
    """

    if latitud is None or longitud is None:
        return False
    return LATITUD_CHACO[0] <= float(latitud) <= LATITUD_CHACO[1] and (
        LONGITUD_CHACO[0] <= float(longitud) <= LONGITUD_CHACO[1]
    )


class CamasCercanas(NamedTuple):
    """Las camas libres a ≤ 25 km de una localidad.

    ``total`` suma también las de los dispositivos de ubicación reservada (RN-009-05);
    ``reservadas`` es esa parte, para la línea «N camas en dispositivos de ubicación
    reservada». ``cercanos`` son ``(distancia_km, dispositivo)`` de los **publicables**, del
    más cercano al más lejano: un reservado nunca está ahí. ``distancia_km`` es ``None`` para
    uno sin coordenadas que cuenta por el nombre de su localidad (va al final).
    """

    total: int
    reservadas: int
    dispositivos: int
    cercanos: tuple[tuple[float | None, Any], ...]


def camas_cercanas(latitud, longitud, clave_de_nombre, red, ambiguos) -> CamasCercanas:
    """Camas libres cercanas de una localidad (RN-009-05). Sin consultas.

    * ``latitud`` / ``longitud``: el centroide de la localidad (``core.UbicacionLocalidad``), o
      ``None`` si no tiene.
    * ``clave_de_nombre``: el nombre de la localidad normalizado
      (``core.services.ubicaciones_localidades.clave``).
    * ``red``: los elegibles (``DispositivoDeLaRed``, con ``tipo``, coordenadas y ``libres``).
    * ``ambiguos``: las claves de nombre que son de **más de una** ``core.Localidad`` del Chaco.

    Un dispositivo con ubicación válida cuenta si está a ≤ :data:`RADIO_CERCANAS_KM` del
    centroide. Uno **sin** ubicación válida cuenta si la clave de su localidad (texto libre)
    coincide con ``clave_de_nombre`` y esa clave no está en ``ambiguos``; si es ambigua, no cuenta
    en ninguna. Una localidad sin centroide solo suma por nombre. Las cercanas **no son
    exclusivas**: la misma cama cuenta para todas las localidades que la tienen cerca.
    """

    elegidos = []
    for dispositivo in red:
        if ubicacion_valida(dispositivo.latitud, dispositivo.longitud):
            distancia = distancia_km(latitud, longitud, dispositivo.latitud, dispositivo.longitud)
            if distancia is not None and distancia <= RADIO_CERCANAS_KM:
                elegidos.append((distancia, dispositivo))
        else:
            nombre = clave(dispositivo.localidad)
            if nombre and nombre == clave_de_nombre and nombre not in ambiguos:
                elegidos.append((None, dispositivo))
    publicables, reservados = separar_por_ubicacion_reservada(elegidos, dispositivo=lambda par: par[1])
    publicables.sort(key=lambda par: (par[0] is None, par[0] or 0.0, par[1].nombre, par[1].id))
    reservadas = sum(dispositivo.libres for _distancia, dispositivo in reservados)
    return CamasCercanas(
        total=sum(dispositivo.libres for _distancia, dispositivo in publicables) + reservadas,
        reservadas=reservadas,
        dispositivos=len(elegidos),
        cercanos=tuple(publicables),
    )


# ---------------------------------------------------------------------------
# Demanda en alza (AE-3, RN-009-09)
# ---------------------------------------------------------------------------

#: Mínimo de casos en las últimas 24 h para que AE-3 hable (RN-009-09).
MINIMO_CASOS_EN_ALZA = 20


class Alza(NamedTuple):
    """La comparación de AE-3. ``porcentaje`` es ``None`` si el promedio anterior es 0."""

    alerta: bool
    actual: int
    promedio: float
    porcentaje: int | None


def demanda_en_alza(actual: int, anteriores) -> Alza:
    """Casos de las últimas 24 h contra el promedio de las tres 24 h anteriores (AE-3).

    Alerta si ``actual ≥ 20`` y ``actual ≥ 1,3 × promedio``; la comparación es entera
    (``10 × actual × 3 ≥ 13 × suma``), así que 26 contra un promedio de 20 alerta. Con promedio 0
    y al menos 20 casos también alerta, sin porcentaje («en las 72 h anteriores no hubo»).
    """

    anteriores = [int(valor) for valor in anteriores]
    suma, ventanas = sum(anteriores), len(anteriores)
    promedio = suma / ventanas if ventanas else 0.0
    alerta = actual >= MINIMO_CASOS_EN_ALZA and 10 * actual * ventanas >= 13 * suma
    porcentaje = None if suma == 0 else int(round((actual * ventanas / suma - 1) * 100))
    return Alza(alerta, int(actual), promedio, porcentaje)


# ---------------------------------------------------------------------------
# Perfil con filtro (RN-009-11)
# ---------------------------------------------------------------------------

#: Los indicadores de salud: con un filtro de localidad o departamento no se muestran.
SALUD_DE_ALOJADOS = ("embarazo", "discapacidad", "electrodependiente", "medicacion_critica", "sin_dosis")
SALUD_DE_ESPERANDO = (
    "dependientes",
    "mayores_dependientes",
    "familias_embarazo",
    "familias_electrodependencia",
    "familias_medicacion_critica",
)
#: Los no sensibles: con filtro se muestran, y de 1 a 4 dicen «menos de 5».
NO_SENSIBLES_DE_ALOJADOS = ("menores", "mayores", "edad_sin_dato")
NO_SENSIBLES_DE_ESPERANDO = ("menores", "mayores", "lactantes", "familias_mascotas")
#: Los conteos operativos: siempre exactos.
TOTALES_DE_ALOJADOS = ("personas",)
TOTALES_DE_ESPERANDO = ("personas", "familias")

MENOS_DE_5 = "menos de 5"
UMBRAL_SUPRESION = 5

#: Lo que dice el bloque con filtro (RN-009-11).
SALUD_SOLO_PROVINCIAL = "Los datos de salud se muestran solo para toda la provincia."

#: Sobre qué total se calcula el porcentaje de cada indicador (solo sin filtro).
_PORCENTAJE_SOBRE = {("alojados", "menores"): "personas", ("alojados", "mayores"): "personas"}


class Cifra(NamedTuple):
    """Un indicador del perfil tal como se puede mostrar.

    ``valor`` es ``None`` si se suprimió («menos de 5»): el número no viaja al template.
    ``porcentaje`` solo existe sin filtro.
    """

    valor: int | None
    texto: str
    porcentaje: int | None = None


def _cifra(valor, *, filtrado, total=None):
    valor = int(valor or 0)
    if filtrado and 0 < valor < UMBRAL_SUPRESION:
        return Cifra(None, MENOS_DE_5)
    porcentaje = None
    if not filtrado and total:
        porcentaje = int(round(valor * 100 / total))
    return Cifra(valor, str(valor), porcentaje)


def presentar_perfil(perfil, filtrado: bool):
    """Lo que el bloque «Perfil de las personas» puede mostrar (RN-009-11). Pura.

    ``perfil`` es el de ``selectors.emergencia_situacion.perfil``:
    ``{"alojados": {indicador: n}, "esperando": {indicador: n}}``. Devuelve un dict nuevo (no
    toca el recibido) con ``alojados`` y ``esperando`` como ``{indicador: Cifra}``, más
    ``filtrado``, ``salud_visible`` y ``nota``.

    * **Sin filtro**: todo exacto, con el porcentaje de menores y mayores alojados.
    * **Con filtro** de localidad o departamento: los indicadores de salud **no están** en el
      resultado (ni la clave), los no sensibles de 1 a 4 dicen «menos de 5» sin número, y no
      hay ningún porcentaje. Los totales (personas, familias) siguen exactos.
    """

    resultado: dict[str, Any] = {
        "filtrado": bool(filtrado),
        "salud_visible": not filtrado,
        "nota": SALUD_SOLO_PROVINCIAL if filtrado else "",
    }
    grupos = (
        ("alojados", TOTALES_DE_ALOJADOS, NO_SENSIBLES_DE_ALOJADOS, SALUD_DE_ALOJADOS),
        ("esperando", TOTALES_DE_ESPERANDO, NO_SENSIBLES_DE_ESPERANDO, SALUD_DE_ESPERANDO),
    )
    for grupo, totales, no_sensibles, salud in grupos:
        datos = perfil.get(grupo, {})
        cifras = {
            indicador: Cifra(int(datos.get(indicador, 0)), str(int(datos.get(indicador, 0)))) for indicador in totales
        }
        for indicador in no_sensibles:
            base = _PORCENTAJE_SOBRE.get((grupo, indicador))
            total = datos.get(base) if base else None
            cifras[indicador] = _cifra(datos.get(indicador, 0), filtrado=filtrado, total=total)
        if not filtrado:
            for indicador in salud:
                cifras[indicador] = _cifra(datos.get(indicador, 0), filtrado=False)
        resultado[grupo] = cifras
    return resultado
