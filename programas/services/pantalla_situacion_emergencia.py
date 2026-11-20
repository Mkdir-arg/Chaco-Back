"""Lo que muestra E8 «Situación» (análisis 009, §12): los números de la foto, escritos para la pantalla.

Nada de acá consulta la base ni decide una regla: los números y los niveles salen de
``services.situacion_emergencia`` y las alertas de ``services.alertas_situacion_emergencia``, sobre la
foto de ``selectors.emergencia_situacion``. Acá solo se escriben (miles con punto, «≈», «—», el
signo de una variación), se arma la bajada del hero y se decide qué enlace viaja según quién mira:

* **No nominal** (RNF-009-01): solo localidades, dispositivos y totales. Un dispositivo de ubicación
  reservada no se nombra (RN-009-13).
* **Enlaces a la mesa solo con supervisar** (RN-009-13, RF-009-16): a la bandeja (E2) desde la tabla
  de presión y a E1. Sin ``supervisa``, las URL ni siquiera se calculan.
* **«Ver dispositivo»** solo para los dispositivos que el usuario abre por Dispositivos
  (``dispositivos_visibles``, §4.1): la vista los lee una vez y los pasa como ids.
* **Perfil con ``presentar_perfil``** (RN-009-11): con filtro, sin salud y con «menos de 5».
* **La capacidad dice «Red provincial»** siempre (RN-009-12).
* **Mapa** (E-6): solo centroides de localidad y dispositivos publicables (``puntos_del_mapa``); el
  payload de la pieza lleva lo justo para dibujar y buscar, y el panel de cada punto va en el HTML.
"""

from django.urls import reverse
from django.utils.formats import number_format

from programas.selectors.emergencia import texto_de_minutos
from programas.selectors.emergencia_situacion import VENTANA_7D
from programas.selectors.emergencia_tablero import ZONA_OPERATIVA
from programas.services.alertas_situacion_emergencia import HORAS_DE_SATURACION, alertas_de_situacion
from programas.services.ocupacion import (
    NIVEL_CRITICA,
    NIVEL_EXIGIDA,
    NIVEL_NORMAL,
    NIVEL_SIN_PLAZAS,
    UMBRAL_CRITICA,
    UMBRAL_EXIGIDA,
    etiqueta_y_tono,
)
from programas.services.situacion_emergencia import (
    HORAS_DEL_RITMO,
    NIVEL_SIN_DEMANDA,
    NO_SE_SATURA,
    PROYECCION,
    RADIO_CERCANAS_KM,
    SATURADA,
    Presion,
    capacidad,
    embudo,
    evolucion,
    logistica,
    perfil,
    presentar_perfil,
    presion_por_localidad,
    puntos_del_mapa,
    resumen,
)

#: El ícono de cada tono de tensión o presión: el de ``components/_barra_umbral.html`` (ficha
#: ``barra_umbral.md``), para que el badge de una tabla diga lo mismo que el de la barra.
ICONOS_DE_TONO = {
    "success": "fa-circle-check",
    "warning": "fa-triangle-exclamation",
    "danger": "fa-circle-exclamation",
    "gray": "fa-circle-minus",
}

#: Los tonos que admite ``components/_stat_card.html``; «Sin plazas» (gray) va con el de marca.
_TONOS_DE_TARJETA = {"success", "warning", "danger"}

#: Lo que dice el lector de pantalla cuando el p90 de un tramo supera su objetivo (en pantalla, negrita).
P90_SUPERA = " (supera el objetivo)"

#: Cuántos dispositivos «con gente y sin entrega recibida en 48 h» se listan; el total va aparte.
TOPE_SIN_ENTREGA = 10

DIAS = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")

RED_PROVINCIAL = "Red provincial"
SIN_DATO = "—"

ETIQUETAS_DE_PERFIL = {
    "alojados": (
        ("menores", "Menores de 16"),
        ("mayores", "Mayores de 60"),
        ("edad_sin_dato", "Edad sin dato"),
        ("embarazo", "Embarazo"),
        ("discapacidad", "Discapacidad"),
        ("electrodependiente", "Electrodependientes"),
        ("medicacion_critica", "Medicación crítica"),
        ("sin_dosis", "Medicación crítica sin dosis"),
    ),
    "esperando": (
        ("menores", "Menores"),
        ("mayores", "Mayores"),
        ("lactantes", "Lactantes"),
        ("dependientes", "Con dependencia"),
        ("mayores_dependientes", "Mayores dependientes"),
        ("familias_embarazo", "Familias con embarazo"),
        ("familias_electrodependencia", "Familias con electrodependencia"),
        ("familias_medicacion_critica", "Familias con medicación crítica"),
        ("familias_mascotas", "Familias con mascotas"),
    ),
}


# ---------------------------------------------------------------------------
# Cómo se escriben los números
# ---------------------------------------------------------------------------


def numero(valor):
    """Un entero con punto de miles («1.284»); ``None`` es «—»."""

    if valor is None:
        return SIN_DATO
    return number_format(int(valor), force_grouping=True)


def con_signo(valor):
    """Una variación: «+146», «−3», «0»."""

    valor = int(valor)
    if valor > 0:
        return f"+{numero(valor)}"
    if valor < 0:
        return f"−{numero(-valor)}"
    return "0"


def cociente(valor):
    """«3,2»: un decimal, con coma."""

    return number_format(valor, 1)


def minutos(valor):
    """Un lapso en minutos como lo escribe E1 («42 min», «5 h»); sin dato, «—»."""

    return SIN_DATO if valor is None else texto_de_minutos(int(valor))


def _plural(cantidad, singular, plural):
    return f"{numero(cantidad)} {singular if cantidad == 1 else plural}"


def badge(texto, tono):
    return {"texto": texto, "tono": tono, "icono": ICONOS_DE_TONO.get(tono, ICONOS_DE_TONO["gray"])}


def local(momento):
    return momento.astimezone(ZONA_OPERATIVA)


# ---------------------------------------------------------------------------
# Arriba de las solapas: hero, alcance y franja
# ---------------------------------------------------------------------------


def alcance(foto):
    """«Departamento San Fernando», «Resistencia · San Fernando» o «Toda la provincia», más la ventana."""

    filtros = foto.filtros
    if foto.filtrado and filtros.localidad_id and not foto.localidad_ignorada:
        localidad = foto.localidades.get(filtros.localidad_id)
        donde = localidad.nombre if localidad else ""
        if localidad and localidad.departamento:
            donde = f"{donde} · {localidad.departamento}"
    elif foto.filtrado:
        donde = f"Departamento {filtros.departamento}"
    else:
        donde = "Toda la provincia"
    ventana = "últimos 7 días" if filtros.ventana == VENTANA_7D else "últimas 72 h"
    return f"{donde} · {ventana}"


def bajada(numeros):
    """La frase del hero: alojadas, esperando y camas libres con la ocupación de la red."""

    alojadas = numeros["personas_alojadas"]
    esperando = numeros["personas_esperando"]
    camas = numeros["camas_libres"]
    tension = camas["tension"]
    ocupacion = f"{tension.porcentaje} % de ocupación" if tension.hay_cifra else "sin camas operativas"
    camas_texto = _plural(camas["valor"], "cama libre", "camas libres")
    if numeros["filtrado"]:
        camas_texto += " en la red provincial"
    return (
        f"{_plural(alojadas['valor'], 'persona alojada', 'personas alojadas')} en "
        f"{_plural(alojadas['dispositivos'], 'dispositivo', 'dispositivos')} · "
        f"{numero(esperando['valor'])} esperando lugar · {camas_texto} ({ocupacion})."
    )


def _tarjeta_saturacion(saturacion, provincial):
    etiqueta = "Horas hasta saturar"
    ritmo = (
        f"{con_signo(round(saturacion.ritmo_por_hora))} camas/h netas en las últimas {HORAS_DEL_RITMO} h"
        if saturacion.ingresos or saturacion.egresos
        else f"sin ingresos ni egresos en las últimas {HORAS_DEL_RITMO} h"
    )
    if saturacion.estado == PROYECCION:
        valor, sufijo = f"≈ {numero(saturacion.horas_redondeadas)}", " h"
        nota = f"{ritmo} · proyección al ritmo actual, no es un pronóstico"
        tono = "danger" if saturacion.horas < HORAS_DE_SATURACION else "warning"
    elif saturacion.estado == SATURADA:
        valor, sufijo, nota, tono = "0", " h", "Red saturada: no quedan camas libres", "danger"
    elif saturacion.estado == NO_SE_SATURA:
        valor, sufijo, nota, tono = SIN_DATO, "", f"No se satura al ritmo actual · {ritmo}", "success"
    else:
        valor, sufijo, nota, tono = SIN_DATO, "", "Todavía no hay casos", "brand"
    if provincial:
        nota = f"{RED_PROVINCIAL} · {nota}"
    return {
        "etiqueta": etiqueta,
        "valor": valor,
        "sufijo": sufijo,
        "nota": nota,
        "icono": "fa-hourglass-half",
        "tono": tono,
    }


def tarjetas(numeros):
    """La franja de cuatro indicadores (B1 a B4), lista para ``_stat_card`` ``variante="tablero"``."""

    alojadas = numeros["personas_alojadas"]
    esperando = numeros["personas_esperando"]
    camas = numeros["camas_libres"]
    tension = camas["tension"]
    hora_del_dia = f"{local(alojadas['desde']):%H:%M}"
    if tension.hay_cifra:
        nota_camas = f"{tension.porcentaje} % ocupada · {_plural(camas['reservadas'], 'reservada', 'reservadas')}"
    else:
        nota_camas = "sin camas operativas"
    if numeros["filtrado"]:
        nota_camas = f"{RED_PROVINCIAL} · {nota_camas}"
    return [
        {
            "etiqueta": "Personas alojadas",
            "valor": numero(alojadas["valor"]),
            "sufijo": "",
            "nota": (
                f"en {_plural(alojadas['dispositivos'], 'dispositivo', 'dispositivos')} · "
                f"{con_signo(alojadas['variacion_del_dia'])} desde las {hora_del_dia}"
            ),
            "icono": "fa-house-chimney-user",
            "tono": "brand",
        },
        {
            "etiqueta": "Personas esperando lugar",
            "valor": numero(esperando["valor"]),
            "sufijo": "",
            "nota": (
                f"{_plural(esperando['familias'], 'familia', 'familias')} · "
                f"{numero(esperando['fuera_de_sla'])} fuera de SLA"
            ),
            "icono": "fa-people-group",
            "tono": "warning" if esperando["valor"] else "brand",
        },
        {
            "etiqueta": "Camas libres en la red",
            "valor": numero(camas["valor"]),
            "sufijo": "",
            "nota": nota_camas,
            "icono": "fa-bed",
            "tono": tension.tono if tension.tono in _TONOS_DE_TARJETA else "brand",
        },
        _tarjeta_saturacion(numeros["saturacion"], numeros["filtrado"]),
    ]


def pildoras(foto):
    """Departamento, localidad (las del departamento elegido) y ventana, para ``_filtro_pildora``."""

    filtros = foto.filtros
    departamentos = sorted({loc.departamento for loc in foto.localidades.values() if loc.departamento})
    elegibles = [
        loc for loc in foto.localidades.values() if not filtros.departamento or loc.departamento == filtros.departamento
    ]
    elegibles.sort(key=lambda loc: (loc.nombre.casefold(), loc.departamento.casefold(), loc.id))
    nombres = [loc.nombre.casefold() for loc in elegibles]
    localidades = [
        (
            loc.id,
            f"{loc.nombre} ({loc.departamento or 'sin departamento'})"
            if nombres.count(loc.nombre.casefold()) > 1
            else loc.nombre,
        )
        for loc in elegibles
    ]
    return [
        {
            "nombre": "departamento",
            "etiqueta": "Departamento",
            "opciones": [(nombre, nombre) for nombre in departamentos],
            "valor": filtros.departamento,
        },
        {
            "nombre": "localidad",
            "etiqueta": "Localidad",
            "opciones": localidades,
            "valor": filtros.localidad_id or "",
            "todos": "Todas",
        },
        {
            "nombre": "ventana",
            "etiqueta": "Ventana",
            "opciones": [(VENTANA_7D, "7 días")],
            "valor": VENTANA_7D if filtros.ventana == VENTANA_7D else "",
            "todos": "72 h",
        },
    ]


# ---------------------------------------------------------------------------
# Solapa Resumen
# ---------------------------------------------------------------------------


#: Las alertas del Resumen que enlazan a otra parte de E8: regla → (clave de la URL, texto de la acción).
#: AE-6 lleva a la solapa que dice qué mandar (RN-009-22); ninguna enlaza a un caso.
ACCIONES_DE_ALERTA = {"AE-6": ("abastecimiento", "Ver el abastecimiento")}


def atencion(foto, *, supervisa, urls=None):
    """«Necesita atención»: las alertas recortadas y el contador.

    ``urls`` son las de destino de :data:`ACCIONES_DE_ALERTA` (la de Abastecimiento, con los filtros
    de la pantalla); una alerta sin URL no lleva acción.
    """

    resultado = alertas_de_situacion(foto)
    urls = urls or {}
    avisos = []
    for alerta in resultado["alertas"]:
        destino, accion = ACCIONES_DE_ALERTA.get(alerta["regla"], ("", ""))
        url = urls.get(destino, "") if destino else ""
        avisos.append(
            {
                "tono": alerta["tono"],
                "icono": alerta["icono"],
                "titulo": alerta["titulo"],
                "texto": alerta["texto"],
                "url": url,
                "accion": accion if url else "",
            }
        )
    total = resultado["total"]
    if not total:
        contador = "Ninguna alerta estratégica con estos filtros."
    elif total > len(avisos):
        contador = f"Mostrando {len(avisos)} de {total}. Primero las de prioridad alta."
    else:
        contador = f"{_plural(total, 'alerta', 'alertas')}, primero las de prioridad alta."
    return {
        "avisos": avisos,
        "resumen": contador,
        "url_avisos_operativos": reverse("emergencia:tablero") if supervisa else "",
    }


def _dato_de_presion(presion):
    """La cifra que acompaña al nivel: «3,2×», «sin camas a 25 km» o nada (Sin demanda)."""

    if presion.nivel == NIVEL_SIN_DEMANDA:
        return ""
    if presion.sin_camas_cercanas:
        return f"sin camas a {RADIO_CERCANAS_KM} km"
    return f"{cociente(presion.cociente)}×"


def _texto_de_presion(presion):
    if presion is None:
        return badge(SIN_DATO, "gray")
    dato = _dato_de_presion(presion)
    return badge(f"{presion.etiqueta} · {dato}" if dato else presion.etiqueta, presion.tono)


def tabla_de_presion(foto, *, supervisa, filas=None):
    """Las filas de «Presión por localidad» (B7) y la fila Total.

    Las localidades sin demanda (solo personas alojadas) van juntas en «Otras localidades (N)»; la
    fila «Sin localidad» va al final. El orden es el de ``presion_por_localidad`` (``filas``, si ya
    se calcularon).
    """

    url_bandeja = reverse("emergencia:bandeja") if supervisa else ""
    todas = presion_por_localidad(foto) if filas is None else filas
    filas, otras, sin_localidad = [], [], None
    for fila in todas:
        if fila["localidad_id"] is None:
            sin_localidad = fila
            continue
        if fila["presion"].nivel == NIVEL_SIN_DEMANDA:
            otras.append(fila)
            continue
        cercanas = fila["cercanas"]
        filas.append(
            {
                "localidad": fila["localidad"],
                "departamento": fila["departamento"] or SIN_DATO,
                "sin_ubicacion": not fila["con_ubicacion"],
                "url": f"{url_bandeja}?localidad={fila['localidad_id']}" if url_bandeja else "",
                "familias": numero(fila["familias"]),
                "personas": numero(fila["personas"]),
                "fuera_de_sla": numero(fila["fuera_de_sla"]),
                "alojadas": numero(fila["alojadas"]),
                "cercanas": numero(cercanas.total),
                "presion": _texto_de_presion(fila["presion"]),
            }
        )
    if otras:
        filas.append(
            {
                "localidad": f"Otras localidades ({numero(len(otras))})",
                "departamento": SIN_DATO,
                "sin_ubicacion": False,
                "url": "",
                "familias": "0",
                "personas": "0",
                "fuera_de_sla": "0",
                "alojadas": numero(sum(fila["alojadas"] for fila in otras)),
                "cercanas": SIN_DATO,
                "presion": _texto_de_presion(Presion(NIVEL_SIN_DEMANDA, None)),
            }
        )
    if sin_localidad is not None:
        filas.append(
            {
                "localidad": sin_localidad["localidad"],
                "departamento": SIN_DATO,
                "sin_ubicacion": False,
                "url": "",
                "familias": numero(sin_localidad["familias"]),
                "personas": numero(sin_localidad["personas"]),
                "fuera_de_sla": numero(sin_localidad["fuera_de_sla"]),
                "alojadas": numero(sin_localidad["alojadas"]),
                "cercanas": SIN_DATO,
                "presion": _texto_de_presion(None),
            }
        )
    total = {
        clave_: numero(sum(fila[clave_] for fila in todas))
        for clave_ in ("familias", "personas", "fuera_de_sla", "alojadas")
    }
    return {"filas": filas, "total": total, "hay_filas": bool(todas)}


def _etiqueta_de_periodo(desde, hasta, *, por_bloques, en_curso, ahora):
    inicio = local(desde)
    dia = f"{DIAS[inicio.weekday()]} {inicio:%d/%m}"
    if por_bloques:
        fin = local(hasta)
        etiqueta = f"{dia} {inicio:%H}–{fin:%H} h"
        eje = f"{inicio:%H} h"
    else:
        etiqueta, eje = dia, f"{inicio:%d/%m}"
    if en_curso:
        etiqueta = f"{etiqueta} (hasta {local(ahora):%H:%M})"
    return etiqueta, eje


def bloque_de_evolucion(foto):
    """La serie de ``_barras_pareadas`` (casos nuevos / familias alojadas) y las personas al cierre."""

    datos = evolucion(foto)
    periodos = []
    for periodo in datos["periodos"]:
        etiqueta, eje = _etiqueta_de_periodo(
            periodo["desde"],
            periodo["hasta"],
            por_bloques=datos["por_bloques"],
            en_curso=periodo["en_curso"],
            ahora=foto.ahora,
        )
        periodos.append(
            {
                "etiqueta": etiqueta,
                "eje": eje,
                "a": periodo["casos_nuevos"],
                "b": periodo["familias_alojadas"],
                "personas": numero(periodo["personas_alojadas_al_cierre"]),
            }
        )
    return {
        "periodos": periodos,
        "periodo": "Bloque de 6 h" if datos["por_bloques"] else "Día operativo",
        "titulo": "Evolución por bloques de 6 h" if datos["por_bloques"] else "Evolución por día operativo",
        "camas_operativas_hoy": numero(datos["camas_operativas_hoy"]),
    }


def bloque_de_capacidad(foto, *, dispositivos_visibles):
    """La barra provincial (60/80) y los cinco más tensionados con las marcas de su tipo (B9)."""

    datos = capacidad(foto)
    tension = datos["tension"]
    total = datos["total"]
    filas = []
    for fila in datos["mas_tensionados"]:
        dispositivo, t = fila.dispositivo, fila.tension
        tipo = dispositivo.tipo
        filas.append(
            {
                "nombre": dispositivo.nombre,
                "url": (
                    reverse("dispositivos:detalle", args=[dispositivo.id])
                    if dispositivo.id in dispositivos_visibles
                    else ""
                ),
                "tipo": f"{tipo.nombre} ({tipo.umbral_ocupacion_amarillo}/{tipo.umbral_ocupacion_rojo})",
                "localidad": dispositivo.localidad or SIN_DATO,
                "barra": {
                    "valor": t.ocupadas,
                    "maximo": t.operativas,
                    "porcentaje": t.porcentaje,
                    "tono": t.tono,
                    "etiqueta": t.etiqueta,
                    "umbral_exigida": tipo.umbral_ocupacion_amarillo,
                    "umbral_critica": tipo.umbral_ocupacion_rojo,
                    "texto": f"{numero(t.ocupadas)} / {numero(t.operativas)} · {t.porcentaje} %",
                    "nombre": f"Ocupación de {dispositivo.nombre}",
                },
                "derivaciones_pendientes": numero(fila.derivaciones_pendientes),
            }
        )
    return {
        "barra": {
            "valor": tension.ocupadas,
            "maximo": tension.operativas,
            "porcentaje": tension.porcentaje,
            "tono": tension.tono,
            "etiqueta": tension.etiqueta,
            "umbral_exigida": UMBRAL_EXIGIDA,
            "umbral_critica": UMBRAL_CRITICA,
        },
        "desglose": (
            f"Ocupadas {numero(total.ocupadas)} · reservadas {numero(datos['reservadas'])} · "
            f"libres {numero(datos['libres'])} de {numero(total.operativas)} operativas"
        ),
        "aparte": (
            f"{numero(datos['fuera_de_servicio'])} fuera de servicio · "
            f"{numero(datos['sin_ubicacion'])} sin ubicación · en {_plural(datos['dispositivos'], 'dispositivo', 'dispositivos')}"
        ),
        "mas_tensionados": filas,
    }


def bloque_de_embudo(foto):
    """El embudo de la cohorte (B10): pasos con su tramo, y las salidas del circuito en texto."""

    datos = embudo(foto)
    pasos = datos["pasos"]
    relevados = pasos[0]["casos"] if pasos else 0
    tramos = [None, *datos["tramos"]]
    filas = []
    for paso, tramo in zip(pasos, tramos, strict=False):
        fila = {
            "paso": paso["paso"].capitalize(),
            "casos": numero(paso["casos"]),
            "barra": {"valor": paso["casos"], "maximo": relevados, "texto": numero(paso["casos"])},
            "conversion": SIN_DATO if paso["conversion"] is None else f"{paso['conversion']} %",
            "tramo": "",
            "mediana": "",
            "p90": "",
            "objetivo": "",
            "p90_supera": False,
            "p90_nota": "",
        }
        if tramo is not None:
            supera = tramo["p90_min"] is not None and tramo["p90_min"] > tramo["objetivo_min"]
            fila.update(
                tramo=tramo["tramo"],
                mediana=minutos(tramo["mediana_min"]),
                p90=minutos(tramo["p90_min"]),
                objetivo=minutos(tramo["objetivo_min"]),
                p90_supera=supera,
                p90_nota=P90_SUPERA if supera else "",
            )
        filas.append(fila)

    def _detalle(por_motivo):
        return " · ".join(f"{motivo.lower()} {numero(cantidad)}" for motivo, cantidad in por_motivo.items())

    cerrados, rechazadas = datos["cerrados_sin_alojar"], datos["rechazadas"]
    salidas = [f"Cerrados sin alojar {numero(cerrados['total'])}"]
    if cerrados["total"]:
        salidas[0] += f" ({_detalle(cerrados['por_motivo'])})"
    texto_rechazadas = f"Derivaciones rechazadas {numero(rechazadas['total'])}"
    if rechazadas["total"]:
        texto_rechazadas += f" ({_detalle(rechazadas['por_motivo'])})"
    salidas.append(f"{texto_rechazadas}, vencidas {numero(datos['vencidas'])}")
    salidas.append(f"Ingresos directos {numero(datos['ingresos_directos'])} (fuera del embudo)")
    return {"hay_casos": datos["hay_casos"], "filas": filas, "salidas": salidas}


def bloque_de_perfil(foto):
    """El perfil (B11) tal como se puede mostrar: ``presentar_perfil`` decide salud y «menos de 5»."""

    presentado = presentar_perfil(perfil(foto), foto.filtrado)
    grupos = {}
    for grupo, etiquetas in ETIQUETAS_DE_PERFIL.items():
        cifras = presentado[grupo]
        items = []
        for clave_, etiqueta in etiquetas:
            cifra = cifras.get(clave_)
            if cifra is None:
                continue
            texto = cifra.texto if cifra.valor is None else numero(cifra.valor)
            if cifra.porcentaje is not None:
                texto = f"{texto} ({cifra.porcentaje} %)"
            items.append({"etiqueta": etiqueta, "texto": texto})
        grupos[grupo] = items
    alojados, esperando = presentado["alojados"], presentado["esperando"]
    return {
        "hay_datos": bool(alojados["personas"].valor or esperando["personas"].valor),
        "alojados_total": numero(alojados["personas"].valor),
        "esperando_total": numero(esperando["personas"].valor),
        "esperando_familias": numero(esperando["familias"].valor),
        "alojados": grupos["alojados"],
        "esperando": grupos["esperando"],
        "nota": presentado["nota"],
    }


def bloque_de_logistica(foto, *, dispositivos_visibles):
    """Logística de kits (B12): stat cards chicas, la tabla por ítem y los sin entrega en 48 h."""

    datos = logistica(foto)
    tarjetas_chicas = [
        {"etiqueta": "Despachadas", "valor": numero(datos["despachadas"]), "icono": "fa-truck-fast", "tono": "brand"},
        {
            "etiqueta": "Recibidas",
            "valor": numero(datos["recibidas"]),
            "nota": f"{numero(datos['con_diferencias'])} con diferencias",
            "icono": "fa-box",
            "tono": "warning" if datos["con_diferencias"] else "success",
        },
        {"etiqueta": "En camino", "valor": numero(datos["en_camino"]), "icono": "fa-truck", "tono": "brand"},
        {
            "etiqueta": "Tránsito mediano",
            "valor": minutos(datos["transito_mediano_min"]),
            "icono": "fa-clock",
            "tono": "brand",
        },
    ]
    items = [
        {
            "item": item.item,
            "enviado": numero(item.enviado),
            "recibido": numero(item.recibido),
            "diferencia": con_signo(item.diferencia),
        }
        for item in datos["por_item"]
    ]
    sin_entrega = []
    for fila in datos["sin_entrega_48h"][:TOPE_SIN_ENTREGA]:
        if fila["reservado"]:
            nombre, url = "Un dispositivo de ubicación reservada", ""
        else:
            nombre = f"{fila['nombre']} ({fila['localidad']})" if fila["localidad"] else fila["nombre"]
            url = reverse("dispositivos:detalle", args=[fila["id"]]) if fila["id"] in dispositivos_visibles else ""
        ultima = "nunca recibió" if fila["horas"] is None else f"última hace {numero(fila['horas'])} h"
        sin_entrega.append(
            {"nombre": nombre, "url": url, "detalle": f"{_plural(fila['personas'], 'persona', 'personas')}, {ultima}"}
        )
    total = len(datos["sin_entrega_48h"])
    return {
        "tarjetas": tarjetas_chicas,
        "items": items,
        "sin_entrega": sin_entrega,
        "sin_entrega_resumen": f"Mostrando {len(sin_entrega)} de {total}." if total > len(sin_entrega) else "",
    }


# ---------------------------------------------------------------------------
# Solapa Mapa (E-6)
# ---------------------------------------------------------------------------

#: Cuántas localidades lista «Localidades con más presión» (§3.6); el total va aparte.
TOPE_MAS_PRESION = 8

CAPA_LOCALIDADES = "localidades"
CAPA_DISPOSITIVOS = "dispositivos"

#: Los niveles de cada leyenda, del más grave al menos: el mismo vocabulario y los mismos tonos que la tabla.
_NIVELES_DE_PRESION = (NIVEL_CRITICA, NIVEL_EXIGIDA, NIVEL_NORMAL, NIVEL_SIN_DEMANDA)
_NIVELES_DE_TENSION = (NIVEL_CRITICA, NIVEL_EXIGIDA, NIVEL_NORMAL, NIVEL_SIN_PLAZAS)


def _id_localidad(pk):
    return f"loc-{pk}"


def _id_dispositivo(pk):
    return f"disp-{pk}"


def _km(distancia):
    return f"{number_format(distancia, 1)} km"


def _url_dispositivo(pk, dispositivos_visibles):
    return reverse("dispositivos:detalle", args=[pk]) if pk in dispositivos_visibles else ""


def _etiqueta_y_tono_de_presion(nivel):
    presion = Presion(nivel, None)
    return presion.etiqueta, presion.tono


def _leyenda(niveles, etiqueta_de):
    return [badge(*etiqueta_de(nivel)) for nivel in niveles]


def _texto_bandeja(familias):
    return "Ver el caso en la bandeja" if familias == 1 else f"Ver los {numero(familias)} casos en la bandeja"


def _panel_de_localidad(loc, *, url_bandeja, dispositivos_visibles):
    presion = Presion(loc["nivel"], loc["cociente"])
    cercanos = []
    for cercano in loc["cercanos"]:
        donde = "en la localidad, sin ubicación" if cercano["distancia_km"] is None else _km(cercano["distancia_km"])
        cercanos.append(
            {
                "nombre": cercano["nombre"],
                "url": _url_dispositivo(cercano["id"], dispositivos_visibles),
                "detalle": f"{donde} · {numero(cercano['libres'])} libres de {numero(cercano['operativas'])}",
            }
        )
    reservadas = loc["camas_reservadas"]
    url = ""
    if url_bandeja and loc["familias"]:
        url = f"{url_bandeja}?localidad={loc['localidad_id']}"
    return {
        "id": _id_localidad(loc["localidad_id"]),
        "titulo": loc["nombre"],
        "meta": f"Dpto. {loc['departamento']}" if loc["departamento"] else "",
        "badge": _texto_de_presion(presion),
        "datos": [
            ("Familias esperando", numero(loc["familias"])),
            ("Personas esperando", numero(loc["personas"])),
            ("Fuera de SLA", numero(loc["fuera_de_sla"])),
            ("Personas de la localidad ya alojadas", numero(loc["alojadas"])),
            (
                f"Camas libres a ≤ {RADIO_CERCANAS_KM} km",
                f"{numero(loc['camas_cercanas'])} en "
                f"{_plural(loc['dispositivos_cercanos'], 'dispositivo', 'dispositivos')}",
            ),
        ],
        "cercanos": cercanos,
        "reservadas": (
            f"Incluye {_plural(reservadas, 'cama', 'camas')} en dispositivos de ubicación reservada."
            if reservadas
            else ""
        ),
        "url": url,
        "url_texto": _texto_bandeja(loc["familias"]) if url else "",
    }


def _panel_de_dispositivo(d, *, dispositivos_visibles):
    etiqueta, tono = etiqueta_y_tono(d["nivel"])
    if d["porcentaje"] is None:
        ocupacion = "sin plazas"
    else:
        etiqueta = f"{etiqueta} · {d['porcentaje']} %"
        ocupacion = f"{numero(d['ocupadas'])} / {numero(d['operativas'])} camas"
    url = _url_dispositivo(d["id"], dispositivos_visibles)
    return {
        "id": _id_dispositivo(d["id"]),
        "titulo": d["nombre"],
        "meta": " · ".join(parte for parte in (d["tipo"], d["localidad"]) if parte),
        "badge": badge(etiqueta, tono),
        "datos": [
            ("Ocupación", ocupacion),
            ("Camas libres", numero(d["libres"])),
            ("Derivaciones pendientes", numero(d["derivaciones_pendientes"])),
        ],
        "url": url,
        "url_texto": "Ver dispositivo" if url else "",
    }


def _pie_del_mapa(puntos):
    partes = []
    if puntos["dispositivos_sin_ubicacion"]:
        partes.append(
            _plural(puntos["dispositivos_sin_ubicacion"], "dispositivo sin ubicación", "dispositivos sin ubicación")
        )
    if puntos["dispositivos_reservados"]:
        partes.append(f"{numero(puntos['dispositivos_reservados'])} con ubicación reservada")
    if puntos["casos_sin_ubicacion"]:
        partes.append(
            _plural(
                puntos["casos_sin_ubicacion"],
                "caso de localidades sin ubicación",
                "casos de localidades sin ubicación",
            )
        )
    return " · ".join(partes)


def bloque_del_mapa(foto, *, supervisa, dispositivos_visibles, filas=None):
    """La solapa Mapa (B6, RF-009-07): puntos de la pieza, capas con leyenda, paneles y la lista. Sin consultas.

    * ``puntos``: lo que serializa ``components/_mapa_capas.html``, ni un campo más. Localidades como
      círculo (tono de la presión, tamaño por personas esperando) y dispositivos como píldora (tono de la
      tensión de su tipo). Sin URL: el detalle es de la pantalla (``detalle=False``).
    * ``localidades`` / ``dispositivos``: el panel de cada punto, que el HTML trae oculto y la pantalla
      muestra con ``nodo-mapa-capas:seleccion``. La bandeja solo con ``supervisa``; «Ver dispositivo»
      solo si el usuario lo abre por Dispositivos.
    * ``lista``: las :data:`TOPE_MAS_PRESION` localidades del mapa con más presión, en el orden de la tabla.
    """

    datos = puntos_del_mapa(foto, filas)
    url_bandeja = reverse("emergencia:bandeja") if supervisa else ""
    puntos, localidades, dispositivos, con_demanda = [], [], [], []
    for loc in datos["localidades"]:
        presion = Presion(loc["nivel"], loc["cociente"])
        meta = f"Dpto. {loc['departamento']}" if loc["departamento"] else ""
        clave_ = _id_localidad(loc["localidad_id"])
        puntos.append(
            {
                "id": clave_,
                "capa": CAPA_LOCALIDADES,
                "lat": loc["latitud"],
                "lng": loc["longitud"],
                "etiqueta": loc["nombre"],
                "icono": "fa-people-group",
                "tono": presion.tono,
                "titulo": loc["nombre"],
                "subtitulo": meta,
                "forma": "circulo",
                "tamano": loc["tamano"],
            }
        )
        localidades.append(
            _panel_de_localidad(loc, url_bandeja=url_bandeja, dispositivos_visibles=dispositivos_visibles)
        )
        if presion.nivel != NIVEL_SIN_DEMANDA:
            con_demanda.append(
                {
                    "clave": clave_,
                    "nombre": loc["nombre"],
                    "meta": meta,
                    "dato": _dato_de_presion(presion),
                    "etiqueta": presion.etiqueta,
                    "tono": presion.tono,
                }
            )
    for d in datos["dispositivos"]:
        panel = _panel_de_dispositivo(d, dispositivos_visibles=dispositivos_visibles)
        puntos.append(
            {
                "id": panel["id"],
                "capa": CAPA_DISPOSITIVOS,
                "lat": d["latitud"],
                "lng": d["longitud"],
                "etiqueta": d["nombre"],
                "icono": "fa-bed",
                "tono": panel["badge"]["tono"],
                "titulo": d["nombre"],
                "subtitulo": panel["meta"],
            }
        )
        dispositivos.append(panel)
    lista = con_demanda[:TOPE_MAS_PRESION]
    return {
        "puntos": puntos,
        "hay_puntos": bool(puntos),
        "capas": [
            {
                "id": CAPA_LOCALIDADES,
                "nombre": "Localidades",
                "cantidad": numero(len(localidades)),
                "titulo": "Presión",
                "leyenda": _leyenda(_NIVELES_DE_PRESION, _etiqueta_y_tono_de_presion),
                "nota": "Un círculo por localidad, en su centro. Más grande, más personas esperando.",
            },
            {
                "id": CAPA_DISPOSITIVOS,
                "nombre": "Dispositivos",
                "cantidad": numero(len(dispositivos)),
                "titulo": "Ocupación",
                "leyenda": _leyenda(_NIVELES_DE_TENSION, etiqueta_y_tono),
                "nota": "Con los umbrales del tipo de cada dispositivo.",
            },
        ],
        "localidades": localidades,
        "dispositivos": dispositivos,
        "lista": lista,
        "lista_resumen": (
            f"Mostrando {len(lista)} de {numero(len(con_demanda))}." if len(con_demanda) > len(lista) else ""
        ),
        "pie": _pie_del_mapa(datos),
    }


def contexto_del_resumen(foto, *, supervisa, dispositivos_visibles, url_abastecimiento=""):
    """Todo lo que dibuja la pantalla menos los filtros y las URL de la vista. Sin consultas.

    ``url_abastecimiento`` es la de la solapa Abastecimiento con los filtros de la pantalla (la arma la vista).
    La tabla de presión y el mapa salen de las mismas filas (``presion_por_localidad``, una vez).
    """

    numeros = resumen(foto)
    filas = presion_por_localidad(foto)
    return {
        "titulo": foto.sla.nombre_evento,
        "eyebrow": "Programa Emergencia · Situación",
        "resumen": bajada(numeros),
        "hay_casos": numeros["hay_casos"],
        "filtrado": numeros["filtrado"],
        "localidad_ignorada": numeros["localidad_ignorada"],
        "alcance": alcance(foto),
        "tarjetas": tarjetas(numeros),
        "atencion": atencion(foto, supervisa=supervisa, urls={"abastecimiento": url_abastecimiento}),
        "presion": tabla_de_presion(foto, supervisa=supervisa, filas=filas),
        "mapa": bloque_del_mapa(foto, supervisa=supervisa, dispositivos_visibles=dispositivos_visibles, filas=filas),
        "evolucion": bloque_de_evolucion(foto),
        "capacidad": bloque_de_capacidad(foto, dispositivos_visibles=dispositivos_visibles),
        "embudo": bloque_de_embudo(foto),
        "perfil": bloque_de_perfil(foto),
        "logistica": bloque_de_logistica(foto, dispositivos_visibles=dispositivos_visibles),
        "radio_km": RADIO_CERCANAS_KM,
        "horas_del_ritmo": HORAS_DEL_RITMO,
    }
