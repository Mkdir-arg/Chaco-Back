"""Motor de condiciones del formulario (Cambio 58, RN-6 y RN-7).

Una condición se cuelga de un campo o de un grupo del diseño y decide si **se
muestra**. Es el único efecto (D11): oculto ⇒ no se exige aunque sea
obligatorio y lo respondido se descarta al enviar. Se evalúa en el navegador
mientras la persona completa y **otra vez acá, en el servidor**, que es la
autoridad. ``static/custom/js/nodo-condiciones.js`` es el espejo en JS: misma
semántica, mismos nombres de operador.

Forma de una condición::

    {"modo": "todas" | "alguna",
     "reglas": [{"fuente": "<clave del ítem>", "op": "<operador>", "valor": ...}, ...]}

La fuente es siempre otro ítem **anterior** del mismo formulario (RN-6); una
fuente vacía no cumple ningún operador salvo ``vacio`` / ``no_adjuntado``; un
ítem que quedó oculto por su propia condición cuenta como vacío para lo que
depende de él. Sin anidamiento.
"""

from __future__ import annotations

from datetime import date, datetime

from programas.models import TipoCampo

MODO_TODAS = "todas"
MODO_ALGUNA = "alguna"
MODOS = (MODO_TODAS, MODO_ALGUNA)

# Operadores por tipo de campo fuente (RN-7). ``vacio``/``completo`` valen para
# todo lo que recolecta un valor; los archivos tienen los suyos.
_COMUNES = {"vacio", "completo"}
OPERADORES_POR_TIPO = {
    TipoCampo.STRING: _COMUNES,
    TipoCampo.INT: _COMUNES | {"eq", "ne", "lt", "gt", "le", "ge"},
    TipoCampo.SELECTOR: _COMUNES | {"es", "no_es", "es_alguno"},
    TipoCampo.SELECTOR_MULTIPLE: _COMUNES | {"incluye", "no_incluye", "incluye_alguno"},
    TipoCampo.DATE: _COMUNES | {"edad_menor", "edad_mayor", "edad_igual", "edad_entre", "anterior", "posterior"},
    TipoCampo.ARCHIVO: {"adjuntado", "no_adjuntado"},
}

# Etiquetas para el editor de condiciones (misma clave que el operador).
ETIQUETAS_OPERADOR = {
    "vacio": "está vacío",
    "completo": "está completo",
    "eq": "es igual a",
    "ne": "es distinto de",
    "lt": "es menor a",
    "gt": "es mayor a",
    "le": "es menor o igual a",
    "ge": "es mayor o igual a",
    "es": "es",
    "no_es": "no es",
    "es_alguno": "es alguno de",
    "incluye": "incluye",
    "no_incluye": "no incluye",
    "incluye_alguno": "incluye alguno de",
    "edad_menor": "edad en años · menor a",
    "edad_mayor": "edad en años · mayor a",
    "edad_igual": "edad en años · igual a",
    "edad_entre": "edad en años · entre",
    "anterior": "es anterior a",
    "posterior": "es posterior a",
    "adjuntado": "fue adjuntado",
    "no_adjuntado": "no fue adjuntado",
}

# Los que no necesitan valor.
SIN_VALOR = {"vacio", "completo", "adjuntado", "no_adjuntado"}
# Los que esperan una lista de valores.
CON_LISTA = {"es_alguno", "incluye_alguno", "edad_entre"}


# ── Utilidades de valor ──────────────────────────────────────────────────────


def esta_vacio(valor):
    if valor is None:
        return True
    if isinstance(valor, str):
        return not valor.strip()
    if isinstance(valor, (list, tuple, set, dict)):
        return len(valor) == 0
    return False


def _fecha(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        texto = valor.strip()
        for formato in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(texto, formato).date()
            except ValueError:
                continue
    return None


def _numero(valor):
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return valor
    try:
        texto = str(valor).strip().replace(",", ".")
        return float(texto) if "." in texto else int(texto)
    except (TypeError, ValueError):
        return None


def edad_en_anios(fecha_nacimiento, hoy=None):
    """Años cumplidos a ``hoy`` (misma cuenta que ``es_menor``, RN-22)."""
    nacimiento = _fecha(fecha_nacimiento)
    if nacimiento is None:
        return None
    hoy = hoy or date.today()
    return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))


def _lista(valor):
    if valor is None:
        return []
    if isinstance(valor, (list, tuple, set)):
        return [str(v) for v in valor]
    return [str(valor)]


# ── Evaluación ───────────────────────────────────────────────────────────────


def evaluar_regla(regla, valor, hoy=None):
    """¿Se cumple ``regla`` para ``valor`` (lo respondido en la fuente)?"""
    op = regla.get("op")
    esperado = regla.get("valor")
    vacio = esta_vacio(valor)

    if op == "vacio":
        return vacio
    if op == "no_adjuntado":
        return vacio
    if vacio:
        # Fuente vacía: no cumple nada más (RN-6).
        return False
    if op in ("completo", "adjuntado"):
        return True

    if op == "es":
        return str(valor) == str(esperado)
    if op == "no_es":
        return str(valor) != str(esperado)
    if op == "es_alguno":
        return str(valor) in _lista(esperado)
    if op == "incluye":
        return str(esperado) in _lista(valor)
    if op == "no_incluye":
        return str(esperado) not in _lista(valor)
    if op == "incluye_alguno":
        return bool(set(_lista(valor)) & set(_lista(esperado)))

    if op in ("eq", "ne", "lt", "gt", "le", "ge"):
        a, b = _numero(valor), _numero(esperado)
        if a is None or b is None:
            return False
        return {"eq": a == b, "ne": a != b, "lt": a < b, "gt": a > b, "le": a <= b, "ge": a >= b}[op]

    if op in ("edad_menor", "edad_mayor", "edad_igual"):
        edad, limite = edad_en_anios(valor, hoy), _numero(esperado)
        if edad is None or limite is None:
            return False
        return {"edad_menor": edad < limite, "edad_mayor": edad > limite, "edad_igual": edad == limite}[op]
    if op == "edad_entre":
        edad = edad_en_anios(valor, hoy)
        rango = [_numero(v) for v in _lista(esperado)]
        if edad is None or len(rango) != 2 or None in rango:
            return False
        return min(rango) <= edad <= max(rango)
    if op in ("anterior", "posterior"):
        fecha, limite = _fecha(valor), _fecha(esperado)
        if fecha is None or limite is None:
            return False
        return fecha < limite if op == "anterior" else fecha > limite

    return False


def evaluar(condicion, respuestas, hoy=None):
    """¿El ítem con ``condicion`` se muestra, dadas las ``respuestas`` visibles?
    Sin condición (o sin reglas) siempre se muestra."""
    if not condicion:
        return True
    reglas = condicion.get("reglas") or []
    if not reglas:
        return True
    modo = condicion.get("modo") or MODO_TODAS
    resultados = (evaluar_regla(regla, respuestas.get(regla.get("fuente")), hoy) for regla in reglas)
    return all(resultados) if modo == MODO_TODAS else any(resultados)


def aplicar(items, respuestas, hoy=None):
    """Recorre los ítems del diseño en orden y decide qué se muestra.

    ``items``: lista ordenada de dicts con ``clave``, ``tipo`` (``grupo`` |
    ``campo`` | ``texto``), ``padre`` (clave del grupo o ``None``) y
    ``condicion``. ``respuestas``: ``{clave: valor}`` tal como llegaron.

    Devuelve ``(visibles, ocultos, respuestas_efectivas)``: los conjuntos de
    claves y las respuestas **sin** las de los ítems ocultos (lo que se guarda).
    Un ítem oculto cuenta como vacío para los que dependen de él; un hijo de
    un grupo oculto está oculto.
    """
    visibles, ocultos = set(), set()
    efectivas = {}
    for item in items:
        clave = item["clave"]
        padre = item.get("padre")
        if padre is not None and padre in ocultos:
            ocultos.add(clave)
            continue
        if evaluar(item.get("condicion"), efectivas, hoy):
            visibles.add(clave)
            if clave in respuestas and item.get("tipo") != "grupo":
                efectivas[clave] = respuestas[clave]
        else:
            ocultos.add(clave)
    return visibles, ocultos, efectivas


# ── Coherencia del diseño ────────────────────────────────────────────────────


def validar_condicion(condicion, item, anteriores):
    """Errores (lista de strings) de la condición de ``item`` dado el mapa de
    ítems ``anteriores`` (``clave → dict`` con ``tipo`` y ``tipo_campo``) que
    están antes en el orden. Vacío = coherente."""
    errores = []
    if not condicion:
        return errores
    modo = condicion.get("modo") or MODO_TODAS
    if modo not in MODOS:
        errores.append(f"Modo desconocido: {modo!r}.")
    reglas = condicion.get("reglas")
    if not isinstance(reglas, list):
        return errores + ["La condición no tiene reglas."]
    for numero, regla in enumerate(reglas, start=1):
        if not isinstance(regla, dict):
            errores.append(f"Regla {numero}: tiene un formato inválido.")
            continue
        fuente = regla.get("fuente")
        if not isinstance(fuente, str) or not isinstance(regla.get("op"), str):
            errores.append(f"Regla {numero}: la fuente y el operador tienen que ser textos.")
            continue
        if fuente == item.get("clave"):
            errores.append(f"Regla {numero}: un ítem no puede depender de sí mismo.")
            continue
        origen = anteriores.get(fuente)
        if origen is None:
            errores.append(f"Regla {numero}: la fuente «{fuente}» no existe o está después de este ítem.")
            continue
        if origen.get("tipo") != "campo":
            errores.append(f"Regla {numero}: la fuente «{fuente}» no es un campo.")
            continue
        op = regla.get("op")
        permitidos = OPERADORES_POR_TIPO.get(origen.get("tipo_campo"), set())
        if op not in permitidos:
            errores.append(f"Regla {numero}: el operador «{op}» no aplica a un campo {origen.get('tipo_campo')}.")
            continue
        if op not in SIN_VALOR and esta_vacio(regla.get("valor")):
            errores.append(f"Regla {numero}: el operador «{ETIQUETAS_OPERADOR.get(op, op)}» necesita un valor.")
        if op in CON_LISTA and not isinstance(regla.get("valor"), (list, tuple)):
            errores.append(f"Regla {numero}: «{ETIQUETAS_OPERADOR.get(op, op)}» espera una lista de valores.")
    return errores


def validar_coherencia(items):
    """Valida todas las condiciones de un diseño en orden. Devuelve
    ``{clave: [errores]}`` solo para los ítems con problemas. Como la fuente
    tiene que estar antes, un ciclo es imposible por construcción."""
    errores = {}
    anteriores = {}
    for item in items:
        problemas = validar_condicion(item.get("condicion"), item, anteriores)
        if problemas:
            errores[item["clave"]] = problemas
        anteriores[item["clave"]] = {"tipo": item.get("tipo"), "tipo_campo": item.get("tipo_campo")}
    return errores


def fuentes_disponibles(items, clave_item):
    """Los campos que pueden ser fuente de una condición de ``clave_item``: los
    campos anteriores en el orden (RN-6). Para el editor."""
    fuentes = []
    for item in items:
        if item["clave"] == clave_item:
            break
        if item.get("tipo") == "campo":
            fuentes.append(item)
    return fuentes
