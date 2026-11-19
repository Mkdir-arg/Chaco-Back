"""Reglas e indicadores de la foto de situación de Emergencia (E8, análisis 009 §5).

Nada de acá consulta la base ni llama a ``now()``. El selector
``programas.selectors.emergencia_situacion`` solo lee (:func:`foto_de_situacion`); acá se decide
y se agrega, una sola vez, sobre lo leído:

* **Reglas puras** (reciben números): :func:`nivel_de_presion` (RN-009-06),
  :func:`horas_hasta_saturar` (RN-009-07), :func:`camas_cercanas` (RN-009-05: 25 km, ambigüedad
  contra todas las ``core.Localidad``), :func:`demanda_en_alza` (AE-3, aritmética entera) y
  :func:`presentar_perfil` (RN-009-11: salud solo provincial con filtro; «menos de 5»).
* **Indicadores** (reciben la foto, 0 consultas): :func:`resumen`, :func:`presion_por_localidad`,
  :func:`evolucion`, :func:`capacidad`, :func:`embudo`, :func:`perfil`, :func:`logistica` y
  :func:`puntos_del_mapa`. Las alertas están en ``programas.services.alertas_situacion_emergencia``.
"""

import statistics
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any, NamedTuple

from core.edad import edad_en_anios
from core.services.ubicaciones_localidades import LATITUD_CHACO, LONGITUD_CHACO, clave
from programas.models import CasoEmergencia, Derivacion, EntregaKit
from programas.selectors.emergencia import SLA_FUERA, TRAMOS, distancia_km
from programas.selectors.emergencia_situacion import HORAS_DEL_RITMO, VENTANA_7D
from programas.selectors.emergencia_tablero import ZONA_OPERATIVA, DispositivoDeLaRed, dia_operativo, percentil
from programas.services.emergencia_ficha import sin_dosis
from programas.services.ocupacion import (
    NIVEL_CRITICA,
    NIVEL_EXIGIDA,
    NIVEL_NORMAL,
    NIVEL_SIN_PLAZAS,
    Conteo,
    alojada_en,
    etiqueta_y_tono,
    tension_de_ocupacion,
)
from programas.services.ubicacion_reservada import separar_por_ubicacion_reservada

Estado = CasoEmergencia.Estado

# ---------------------------------------------------------------------------
# Presión por localidad (RN-009-06)
# ---------------------------------------------------------------------------

#: Una localidad sin personas esperando. Los otros tres niveles son los de la tensión de
#: ocupación (``services.ocupacion``): mismo vocabulario y mismos tonos (RNF-009-09).
NIVEL_SIN_DEMANDA = "sin_demanda"

#: Del más grave al menos: para ordenar filas y la lista «Localidades con más presión».
ORDEN_DE_PRESION = (NIVEL_CRITICA, NIVEL_EXIGIDA, NIVEL_NORMAL, NIVEL_SIN_DEMANDA)


class Presion(NamedTuple):
    """El nivel de presión de una localidad y su cociente (``None`` sin camas o sin demanda)."""

    nivel: str
    cociente: float | None

    @property
    def etiqueta(self) -> str:
        """La de la tensión del mismo nivel; «Sin demanda» es solo de la presión."""

        return "Sin demanda" if self.nivel == NIVEL_SIN_DEMANDA else etiqueta_y_tono(self.nivel)[0]

    @property
    def tono(self) -> str:
        """El de la tensión del mismo nivel; «Sin demanda» usa el de «Sin plazas»."""

        nivel = NIVEL_SIN_PLAZAS if self.nivel == NIVEL_SIN_DEMANDA else self.nivel
        return etiqueta_y_tono(nivel)[1]

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

    ``perfil`` es el de ``services.situacion_emergencia.perfil``:
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


# ---------------------------------------------------------------------------
# Indicadores de la foto (0 consultas): lo que muestran el Resumen y el Mapa
# ---------------------------------------------------------------------------

#: «Sin entrega recibida en 48 h» (B12, AE-6).
HORAS_SIN_ENTREGA = 48

#: Las cinco etapas del embudo, por la marca que las alcanza (RN-2.9: el embudo es monótono).
PASOS_DEL_EMBUDO = (
    ("relevados", "creado"),
    ("tomados", "tomado_en"),
    ("derivados", "derivado_en"),
    ("aceptados", "aceptado_en"),
    ("alojados", "alojado_en"),
)

SIN_LOCALIDAD = "Sin localidad"

#: Edades del perfil de alojados (B11): menores de 16, mayores de 60 o más.
EDAD_MENOR = 16
EDAD_MAYOR = 60


def _esperando(foto):
    return [caso for caso in foto.casos_filtrados if caso.esperando]


def _fuera_de_sla(foto, casos):
    return sum(1 for caso in casos if (semaforo := foto.semaforos.get(caso.id)) and semaforo.estado == SLA_FUERA)


def total_de_la_red(foto) -> Conteo:
    """El ``Conteo`` de camas de toda la red (B3, B9): incluye los de ubicación reservada."""

    return foto.red.total


def saturacion(foto):
    """Horas hasta saturar (B4, RN-009-07) con la red provincial; «—» si no hay casos."""

    libres = foto.red.libres
    if not foto.casos:
        return sin_datos_de_saturacion(libres, foto.ingresos_6h, foto.egresos_6h)
    return horas_hasta_saturar(libres, foto.ingresos_6h, foto.egresos_6h)


def resumen(foto):
    """Los cuatro indicadores (B1 a B4), en números. El texto lo escribe la pantalla (E-5).

    B1 y B2 siguen el filtro (por la localidad del caso); B3 y B4 son provinciales.
    """

    ahora = foto.ahora
    dia_desde, _hasta = dia_operativo(ahora)
    alojados = foto.alojados_filtrados
    ahora_alojadas = [persona for persona in alojados if persona.egresado_en is None]
    al_empezar_el_dia = sum(
        1
        for persona in alojados
        if persona.confirmada_en is not None and alojada_en(persona.confirmada_en, persona.egresado_en, dia_desde)
    )
    esperando = _esperando(foto)
    total = total_de_la_red(foto)
    return {
        "hay_casos": bool(foto.casos),
        "filtrado": foto.filtrado,
        "localidad_ignorada": foto.localidad_ignorada,
        "personas_alojadas": {
            "valor": len(ahora_alojadas),
            "dispositivos": len({persona.dispositivo_id for persona in ahora_alojadas}),
            "variacion_del_dia": len(ahora_alojadas) - al_empezar_el_dia,
            "desde": dia_desde,
        },
        "personas_esperando": {
            "valor": sum(caso.total_declarado for caso in esperando),
            "familias": len(esperando),
            "fuera_de_sla": _fuera_de_sla(foto, esperando),
        },
        "camas_libres": {
            "valor": foto.red.libres,
            "reservadas": foto.red.reservadas,
            "conteo": total,
            "tension": tension_de_ocupacion(total),
        },
        "saturacion": saturacion(foto),
    }


def _cercanas_de(foto, localidad_id, nombre):
    localidad = foto.localidades.get(localidad_id)
    latitud = localidad.latitud if localidad else None
    longitud = localidad.longitud if localidad else None
    return camas_cercanas(
        latitud, longitud, clave(localidad.nombre if localidad else nombre), foto.red.dispositivos, foto.ambiguos
    )


def presion_por_localidad(foto):
    """Una fila por localidad con demanda o con personas alojadas (B7, RN-009-04 a 06).

    Por ``localidad_id`` del caso, nunca por nombre. Cada fila: ``localidad_id``, ``localidad``,
    ``departamento``, ``con_ubicacion``, ``familias``, ``personas`` (esperando), ``fuera_de_sla``,
    ``alojadas`` (personas de esa localidad alojadas ahora), ``cercanas``
    (``services.situacion_emergencia.CamasCercanas``) y ``presion`` (``Presion``). Los casos sin
    localidad van a una fila «Sin localidad» sin cercanas ni presión.

    Orden: Crítica, Exigida, Normal, Sin demanda; dentro de cada nivel, el cociente más alto
    primero y las críticas «sin camas a 25 km» después de las que tienen cociente; después, más
    personas esperando.
    """

    filas = {}

    def fila(localidad_id, nombre):
        if localidad_id not in filas:
            localidad = foto.localidades.get(localidad_id)
            filas[localidad_id] = {
                "localidad_id": localidad_id,
                "localidad": nombre or (localidad.nombre if localidad else ""),
                "departamento": localidad.departamento if localidad else "",
                "con_ubicacion": bool(localidad and localidad.con_ubicacion),
                "familias": 0,
                "personas": 0,
                "fuera_de_sla": 0,
                "alojadas": 0,
            }
        return filas[localidad_id]

    for caso in _esperando(foto):
        actual = fila(caso.localidad_id, caso.localidad if caso.localidad_id else SIN_LOCALIDAD)
        actual["familias"] += 1
        actual["personas"] += caso.total_declarado
        if (semaforo := foto.semaforos.get(caso.id)) and semaforo.estado == SLA_FUERA:
            actual["fuera_de_sla"] += 1
    for persona in foto.alojados_filtrados:
        if persona.egresado_en is None:
            pk = persona.localidad_id
            fila(pk, persona.localidad if pk else SIN_LOCALIDAD)["alojadas"] += 1

    resultado = []
    for pk, actual in filas.items():
        if pk is None:
            actual["cercanas"], actual["presion"] = None, None
        else:
            actual["cercanas"] = _cercanas_de(foto, pk, actual["localidad"])
            actual["presion"] = nivel_de_presion(actual["personas"], actual["cercanas"].total)
        resultado.append(actual)

    def orden(actual):
        presion = actual["presion"]
        if presion is None:
            return (len(ORDEN_DE_PRESION), True, 0.0, -actual["personas"], "")
        return (
            ORDEN_DE_PRESION.index(presion.nivel),
            presion.cociente is None,
            -(presion.cociente or 0.0),
            -actual["personas"],
            actual["localidad"].casefold(),
        )

    resultado.sort(key=orden)
    return resultado


def evolucion(foto):
    """Por período de la ventana (B8): casos nuevos, familias alojadas, cerrados sin alojar y
    personas alojadas al cierre (o a ``ahora`` en el período en curso). Con el filtro de demanda.

    ``camas_operativas_hoy`` es la referencia rotulada: la capacidad no tiene historia (§4.1).
    """

    casos = foto.casos_filtrados
    alojados = foto.alojados_filtrados
    periodos = []
    for desde, hasta in foto.periodos:
        corte = min(hasta, foto.ahora)
        periodos.append(
            {
                "desde": desde,
                "hasta": hasta,
                "en_curso": hasta > foto.ahora,
                "casos_nuevos": sum(1 for caso in casos if desde <= caso.creado < hasta),
                "familias_alojadas": sum(
                    1 for caso in casos if caso.alojado_en is not None and desde <= caso.alojado_en < hasta
                ),
                "cerrados_sin_alojar": sum(
                    1
                    for caso in casos
                    if caso.alojado_en is None and caso.cerrado_en is not None and desde <= caso.cerrado_en < hasta
                ),
                "personas_alojadas_al_cierre": sum(
                    1
                    for persona in alojados
                    if persona.confirmada_en is not None
                    and alojada_en(persona.confirmada_en, persona.egresado_en, corte)
                ),
            }
        )
    return {
        "por_bloques": foto.filtros.ventana != VENTANA_7D,
        "periodos": periodos,
        "camas_operativas_hoy": total_de_la_red(foto).operativas,
    }


def _pendientes_por_dispositivo(foto):
    return Counter(d.dispositivo_id for d in foto.derivaciones if d.estado == Derivacion.Estado.PENDIENTE)


def _sin_ubicacion(dispositivos):
    return sum(1 for d in dispositivos if not ubicacion_valida(d.latitud, d.longitud))


class Tensionado(NamedTuple):
    """Un dispositivo publicable con su tensión **de su tipo** (B9 y AE-5)."""

    dispositivo: DispositivoDeLaRed
    tension: Any
    derivaciones_pendientes: int

    @property
    def exceso(self):
        """``porcentaje − umbral rojo`` del tipo: el orden de «más tensionados» (como Dispositivos)."""

        return self.tension.porcentaje - self.dispositivo.tipo.umbral_ocupacion_rojo


def tensionados(foto):
    """Los dispositivos publicables con cifra, del más al menos tensionado. Sin reservados (RN-009-13)."""

    pendientes = _pendientes_por_dispositivo(foto)
    publicables, _reservados = separar_por_ubicacion_reservada(foto.red.dispositivos)
    filas = [Tensionado(d, tension_de_ocupacion(d.conteo, tipo=d.tipo), pendientes.get(d.id, 0)) for d in publicables]
    filas = [fila for fila in filas if fila.tension.hay_cifra]
    filas.sort(key=lambda f: (-f.exceso, -f.tension.porcentaje, f.dispositivo.nombre, f.dispositivo.id))
    return filas


#: Cuántos «más tensionados» muestra B9.
TOPE_TENSIONADOS = 5


def capacidad(foto):
    """Capacidad de la red en camas (B9), siempre provincial (RN-009-12).

    ``total`` (``Conteo``) y ``tension`` (corte general 60/80) incluyen los dispositivos de
    ubicación reservada; ``mas_tensionados`` no los nombra.
    """

    total = total_de_la_red(foto)
    return {
        "total": total,
        "tension": tension_de_ocupacion(total),
        "libres": foto.red.libres,
        "reservadas": foto.red.reservadas,
        "fuera_de_servicio": total.fuera_de_servicio,
        "dispositivos": len(foto.red.dispositivos),
        "sin_ubicacion": _sin_ubicacion(foto.red.dispositivos),
        "mas_tensionados": tensionados(foto)[:TOPE_TENSIONADOS],
    }


def _mediana(valores):
    return statistics.median(valores) if valores else None


def embudo(foto):
    """El embudo de la cohorte (B10, RN-009-08): casos **creados en la ventana**, sin ingresos directos.

    ``pasos``: relevados, tomados, derivados, aceptados y alojados, cada uno con ``casos`` y la
    ``conversion`` (% sobre el paso anterior, ``None`` si el anterior es 0). ``tramos``: por
    tramo, cuántos casos de la cohorte lo completaron, mediana y p90 en minutos y el objetivo de
    E7. Salidas: cerrados sin alojar por motivo, derivaciones rechazadas (por motivo) y vencidas
    de la cohorte, e ingresos directos aparte. Con el filtro de demanda.
    """

    creados = [caso for caso in foto.casos_filtrados if foto.desde <= caso.creado < foto.ahora]
    cohorte = [caso for caso in creados if not caso.ingreso_directo]
    pasos, anterior = [], None
    for paso, marca in PASOS_DEL_EMBUDO:
        cantidad = sum(1 for caso in cohorte if getattr(caso, marca) is not None)
        conversion = int(round(cantidad * 100 / anterior)) if anterior else None
        pasos.append({"paso": paso, "casos": cantidad, "conversion": conversion})
        anterior = cantidad
    tramos = []
    for tramo, abre, cierra, campo in TRAMOS:
        valores = sorted(
            max((getattr(c, cierra) - getattr(c, abre)).total_seconds(), 0) / 60
            for c in cohorte
            if getattr(c, abre) is not None and getattr(c, cierra) is not None
        )
        tramos.append(
            {
                "tramo": tramo,
                "casos": len(valores),
                "mediana_min": _mediana(valores),
                "p90_min": percentil(valores),
                "objetivo_min": getattr(foto.sla, campo),
            }
        )
    ids = {caso.id for caso in cohorte}
    cerrados = Counter(
        CasoEmergencia.MotivoCierre(c.motivo_cierre).label
        if c.motivo_cierre in CasoEmergencia.MotivoCierre.values
        else "Otro"
        for c in cohorte
        if c.estado == Estado.CERRADO and c.alojado_en is None
    )
    rechazadas = Counter(
        d.motivo or "Otro" for d in foto.derivaciones if d.caso_id in ids and d.estado == Derivacion.Estado.RECHAZADA
    )
    return {
        "hay_casos": bool(cohorte),
        "pasos": pasos,
        "tramos": tramos,
        "cerrados_sin_alojar": {"total": sum(cerrados.values()), "por_motivo": dict(cerrados.most_common())},
        "rechazadas": {"total": sum(rechazadas.values()), "por_motivo": dict(rechazadas.most_common())},
        "vencidas": sum(1 for d in foto.derivaciones if d.caso_id in ids and d.estado == Derivacion.Estado.VENCIDA),
        "ingresos_directos": sum(1 for caso in creados if caso.ingreso_directo),
    }


def _contar_alojados(personas, ahora):
    hoy = ahora.astimezone(ZONA_OPERATIVA).date()
    conteo = defaultdict(int)
    for persona in personas:
        conteo["personas"] += 1
        edad = edad_en_anios(persona.fecha_nacimiento, hoy)
        if edad is None:
            conteo["edad_sin_dato"] += 1
        elif edad < EDAD_MENOR:
            conteo["menores"] += 1
        elif edad >= EDAD_MAYOR:
            conteo["mayores"] += 1
        avisos = persona.avisos_salud
        for clave_aviso in ("embarazo", "discapacidad", "electrodependiente", "medicacion_critica"):
            if avisos.get(clave_aviso) is True:
                conteo[clave_aviso] += 1
        if sin_dosis(avisos):
            conteo["sin_dosis"] += 1
    return conteo


def _contar_esperando(casos):
    conteo = defaultdict(int)
    for caso in casos:
        conteo["personas"] += caso.total_declarado
        conteo["familias"] += 1
        for clave_grupo in ("menores", "mayores", "lactantes", "dependientes", "mayores_dependientes"):
            conteo[clave_grupo] += getattr(caso, clave_grupo)
        for necesidad, clave_familias in (
            ("embarazo", "familias_embarazo"),
            ("electrodependiente", "familias_electrodependencia"),
            ("medicacion_critica", "familias_medicacion_critica"),
            ("mascotas", "familias_mascotas"),
        ):
            if caso.necesidades.get(necesidad):
                conteo[clave_familias] += 1
    return conteo


_CLAVES_DE_ALOJADOS = (
    "personas",
    "menores",
    "mayores",
    "edad_sin_dato",
    "embarazo",
    "discapacidad",
    "electrodependiente",
    "medicacion_critica",
    "sin_dosis",
)
_CLAVES_DE_ESPERANDO = (
    "personas",
    "familias",
    "menores",
    "mayores",
    "lactantes",
    "dependientes",
    "mayores_dependientes",
    "familias_embarazo",
    "familias_electrodependencia",
    "familias_medicacion_critica",
    "familias_mascotas",
)


def perfil(foto):
    """El perfil agregado (B11), **exacto**, con el filtro de demanda.

    ``{"alojados": {...}, "esperando": {...}}``. Alojados (Formulario 2): personas, menores de 16,
    mayores de 60, edad sin dato y, de ``avisos_salud``, embarazo, discapacidad,
    electrodependiente, medicación crítica y sin dosis (``emergencia_ficha.sin_dosis``). Esperando
    (Formulario 1, declarado): personas, familias, menores, mayores, lactantes, dependientes,
    mayores dependientes y familias con embarazo, electrodependencia, medicación crítica y
    mascotas. **Lo que se muestra** lo decide ``services.situacion_emergencia.presentar_perfil``
    (RN-009-11): este dict no va al template.
    """

    alojados = _contar_alojados([p for p in foto.alojados_filtrados if p.egresado_en is None], foto.ahora)
    esperando = _contar_esperando(_esperando(foto))
    return {
        "alojados": {clave_: alojados.get(clave_, 0) for clave_ in _CLAVES_DE_ALOJADOS},
        "esperando": {clave_: esperando.get(clave_, 0) for clave_ in _CLAVES_DE_ESPERANDO},
    }


def sin_dosis_provincial(foto):
    """Personas alojadas ahora con medicación crítica sin dosis, **sin filtro** (AE-7, RN-009-11)."""

    return sum(1 for persona in foto.alojados_ahora if sin_dosis(persona.avisos_salud))


def sin_entrega_reciente(foto):
    """Dispositivos con gente alojada y sin entrega recibida en 48 h (B12, AE-6), provincial.

    Cada fila: ``id``, ``nombre`` y ``localidad`` (vacíos si es de ubicación reservada),
    ``reservado``, ``personas``, ``ultima_recepcion`` y ``horas`` desde ella (``None`` si nunca).
    Primero los que nunca recibieron, después la recepción más vieja.
    """

    limite = foto.ahora - timedelta(hours=HORAS_SIN_ENTREGA)
    personas = Counter(p.dispositivo_id for p in foto.alojados_ahora)
    filas = []
    for dispositivo in foto.con_gente:
        ultima = dispositivo.ultima_recepcion
        if ultima is not None and ultima >= limite:
            continue
        filas.append(
            {
                "id": dispositivo.id,
                "nombre": "" if dispositivo.reservado else dispositivo.nombre,
                "localidad": "" if dispositivo.reservado else dispositivo.localidad,
                "reservado": dispositivo.reservado,
                "personas": personas.get(dispositivo.id, 0),
                "ultima_recepcion": ultima,
                "horas": None if ultima is None else int((foto.ahora - ultima).total_seconds() // 3600),
            }
        )
    filas.sort(key=lambda f: (f["ultima_recepcion"] is not None, f["ultima_recepcion"] or foto.ahora, f["id"]))
    return filas


def logistica(foto):
    """Logística de kits de la ventana (B12), provincial.

    Entregas despachadas en la ventana por estado; recibidas y con diferencias; en camino (todas,
    ahora); tránsito mediano en minutos de las recibidas; enviado y recibido por ítem; y los
    dispositivos con gente sin entrega recibida en 48 h.
    """

    Est = EntregaKit.Estado
    de_la_ventana = [e for e in foto.entregas if e.despachada_en is not None and e.despachada_en >= foto.desde]
    recibidas = [e for e in de_la_ventana if e.estado in EntregaKit.ESTADOS_RECIBIDOS]
    transitos = sorted(
        max((e.recibida_en - e.despachada_en).total_seconds(), 0) / 60 for e in recibidas if e.recibida_en is not None
    )
    return {
        "despachadas": len(de_la_ventana),
        "por_estado": dict(Counter(e.estado for e in de_la_ventana)),
        "recibidas": len(recibidas),
        "con_diferencias": sum(1 for e in recibidas if e.estado == Est.RECIBIDA_CON_DIFERENCIAS),
        "en_camino": sum(1 for e in foto.entregas if e.estado == Est.EN_CAMINO),
        "transito_mediano_min": _mediana(transitos),
        "por_item": list(foto.items_recibidos),
        "sin_entrega_48h": sin_entrega_reciente(foto),
    }


def puntos_del_mapa(foto):
    """Lo que viaja al mapa (B6): **centroides de localidad** y **dispositivos no reservados**.

    Nunca una coordenada de un caso (RNF-009-01) ni un dispositivo de ubicación reservada
    (RN-009-13): se filtran acá, no en el template. ``localidades``: las filas de presión con
    centroide (con el filtro de demanda). ``dispositivos``: los publicables con ubicación válida,
    con su nivel de tensión **de su tipo**. Y los contadores del pie: dispositivos sin ubicación,
    reservados y casos (familias esperando) de localidades sin ubicación o sin localidad.
    """

    localidades = []
    casos_sin_ubicacion = 0
    for fila in presion_por_localidad(foto):
        localidad = foto.localidades.get(fila["localidad_id"]) if fila["localidad_id"] else None
        if localidad is None or not localidad.con_ubicacion:
            casos_sin_ubicacion += fila["familias"]
            continue
        localidades.append(
            {
                "localidad_id": localidad.id,
                "nombre": fila["localidad"],
                "latitud": float(localidad.latitud),
                "longitud": float(localidad.longitud),
                "personas": fila["personas"],
                "familias": fila["familias"],
                "nivel": fila["presion"].nivel,
                "cociente": fila["presion"].cociente,
            }
        )
    publicables, reservados = separar_por_ubicacion_reservada(foto.red.dispositivos)
    dispositivos = []
    for d in publicables:
        if not ubicacion_valida(d.latitud, d.longitud):
            continue
        tension = tension_de_ocupacion(d.conteo, tipo=d.tipo)
        dispositivos.append(
            {
                "id": d.id,
                "nombre": d.nombre,
                "latitud": float(d.latitud),
                "longitud": float(d.longitud),
                "libres": d.libres,
                "nivel": tension.nivel,
                "porcentaje": tension.porcentaje,
            }
        )
    return {
        "localidades": localidades,
        "dispositivos": dispositivos,
        "dispositivos_sin_ubicacion": _sin_ubicacion(publicables),
        "dispositivos_reservados": len(reservados),
        "casos_sin_ubicacion": casos_sin_ubicacion,
    }
