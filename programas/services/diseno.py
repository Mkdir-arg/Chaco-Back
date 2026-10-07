"""Diseño del formulario por convocatoria (Cambio 58, RN-1..RN-3; tasks #339 y #340).

El diseño es un **orden sobre el catálogo vivo**: nunca falta un requisito del
catálogo ni sobra uno borrado. Una convocatoria sin diseño guardado se sirve
con el **plan por defecto** (los grupos del catálogo con sus preguntas y un
grupo por nivel de requisitos), sin escribir nada: el diseño se persiste la
primera vez que alguien abre el constructor. Desde ahí, cada vez que se sirve
se **reconcilia**: los requisitos nuevos aparecen al final de su grupo por
defecto, los borrados o desactivados salen, y las condiciones que los usaban se
eliminan con aviso. El constructor la **persiste** (``reconciliar``); el portal
y la app la aplican **en memoria** (``items_vigentes``), así el formulario sigue
al catálogo aunque nadie vuelva a abrir el constructor.
"""

from __future__ import annotations

from uuid import uuid4

from django.db import models, transaction

from programas.models import (
    CanalFormulario,
    DisenoFormulario,
    GrupoRequisito,
    ItemDiseno,
    OrigenRequisito,
    PreguntaGlobal,
    RequisitoNativo,
)

GRUPO = ItemDiseno.Tipo.GRUPO
CAMPO = ItemDiseno.Tipo.CAMPO
TEXTO = ItemDiseno.Tipo.TEXTO

# Grupos por nivel de requisitos nativos (clave del ítem, título por defecto).
NIVELES = {
    "programa": ("g-programa", "Requisitos del programa {nombre}"),
    "segmento": ("g-segmento", "Requisitos del segmento {nombre}"),
    "subsegmento": ("g-subsegmento", "Requisitos del subsegmento {nombre}"),
}
CLAVE_GENERALES_SUELTAS = "g-generales"


# ── Claves ───────────────────────────────────────────────────────────────────


def clave_pregunta(pregunta):
    return f"pg-{pregunta.pk}"


def clave_requisito(requisito):
    return f"rn-{requisito.pk}"


def clave_grupo_catalogo(grupo):
    return f"g-{grupo.clave}"


def nueva_clave(prefijo):
    return f"{prefijo}-{uuid4().hex[:8]}"


# ── Catálogo esperado ────────────────────────────────────────────────────────


def catalogo_convocatoria(convocatoria):
    """Una sola lectura del catálogo para servir una definición: ``(preguntas,
    requisitos)`` —las preguntas generales activas con su grupo y los requisitos
    nativos que hereda la convocatoria (programa, segmento y subsegmento)—, cada
    lista por ``orden, id``. Son dos consultas; de acá se reparten en memoria el
    plan por defecto, la reconciliación (``items_vigentes``) y las listas
    planas, que antes volvían a la base cada una por su cuenta (Cambio 91: la
    definición se sirve en cada paso 2 del link y en cada detalle y alta de la
    app)."""
    from programas.services.becas import filtro_requisitos_convocatoria

    requisitos = list(
        RequisitoNativo.objects.filter(filtro_requisitos_convocatoria(convocatoria)).order_by("orden", "id")
    )
    return _preguntas_activas(), requisitos


def _requisitos_por_nivel(convocatoria, requisitos=None):
    """``[(nivel, nombre, [RequisitoNativo])]`` en el orden programa → segmento
    → subsegmento, con la misma herencia que ``get_campos_formulario`` (RN-32).

    Con ``requisitos`` (los de ``catalogo_convocatoria``, ya ordenados) se
    reparten por nivel en memoria; sin ellos, una consulta por nivel."""
    niveles = []
    segmento = convocatoria.segmento
    if segmento.programa_id:
        programa = segmento.programa
        if requisitos is None:
            del_programa = list(programa.requisitos.order_by("orden", "id"))
        else:
            del_programa = [r for r in requisitos if r.programa_id == programa.pk]
        niveles.append(("programa", programa.nombre, del_programa))
    if requisitos is None:
        del_segmento = list(
            RequisitoNativo.objects.filter(segmento_id=segmento.pk, subsegmento__isnull=True).order_by("orden", "id")
        )
    else:
        del_segmento = [r for r in requisitos if r.segmento_id == segmento.pk and r.subsegmento_id is None]
    niveles.append(("segmento", segmento.nombre, del_segmento))
    if convocatoria.subsegmento_id:
        subsegmento = convocatoria.subsegmento
        if requisitos is None:
            del_subsegmento = list(subsegmento.requisitos.order_by("orden", "id"))
        else:
            del_subsegmento = [r for r in requisitos if r.subsegmento_id == subsegmento.pk]
        niveles.append(("subsegmento", subsegmento.nombre, del_subsegmento))
    return niveles


def _preguntas_activas():
    return list(PreguntaGlobal.objects.filter(activo=True).select_related("grupo").order_by("orden", "id"))


def _fuentes_simbolicas(preguntas):
    """El catálogo no conoce los pk al sembrarse: la condición por defecto del
    Apoderado apunta a ``legajo:fecha_nacimiento``. Acá se traduce a la clave
    real del ítem (``pg-<pk>``)."""
    mapa = {}
    for pregunta in preguntas:
        if pregunta.origen == OrigenRequisito.LEGAJO:
            mapa[f"legajo:{pregunta.vinculo}"] = clave_pregunta(pregunta)
        elif pregunta.origen == OrigenRequisito.PERSONA_VINCULADA:
            mapa[f"apoderado:{pregunta.vinculo}"] = clave_pregunta(pregunta)
    return mapa


def _resolver_condicion(condicion, preguntas):
    """Copia de ``condicion`` con las fuentes simbólicas resueltas; las reglas
    cuya fuente no existe se descartan. Sin reglas, no hay condición."""
    if not condicion:
        return None
    mapa = _fuentes_simbolicas(preguntas)
    reglas = []
    for regla in condicion.get("reglas") or []:
        fuente = regla.get("fuente")
        if fuente in mapa:
            reglas.append({**regla, "fuente": mapa[fuente]})
        elif isinstance(fuente, str) and ":" in fuente:
            continue  # simbólica sin destino: se descarta
        else:
            reglas.append(dict(regla))
    if not reglas:
        return None
    return {"modo": condicion.get("modo") or "todas", "reglas": reglas}


# ── Condición por defecto de un grupo del catálogo ──────────────────────────


def _clave_catalogo(pregunta):
    """La clave con la que una condición por defecto nombra a una pregunta: la
    simbólica si es un campo vinculado (sobrevive a los pk de cada entorno,
    como en el seed), la del ítem (``pg-<pk>``) si es una pregunta común."""
    if pregunta.origen == OrigenRequisito.LEGAJO:
        return f"legajo:{pregunta.vinculo}"
    if pregunta.origen == OrigenRequisito.PERSONA_VINCULADA:
        return f"apoderado:{pregunta.vinculo}"
    return clave_pregunta(pregunta)


def fuentes_condicion_defecto(grupo=None, preguntas=None):
    """Los campos que la condición por defecto de ``grupo`` puede mirar: las
    preguntas activas de los grupos **anteriores** del catálogo (RN-6 por
    construcción: en el plan por defecto quedan antes que el grupo). Un grupo
    nuevo entra al final, así que puede mirar todo el catálogo agrupado; las
    preguntas sueltas caen en «Requisitos generales», después de los grupos,
    y por eso nunca son fuente. Mismo formato que el editor del constructor:
    ``{clave, titulo, tipo_campo, opciones}``."""
    fuentes = []
    for pregunta in preguntas if preguntas is not None else _preguntas_activas():
        if pregunta.grupo_id is None:
            continue
        if grupo is not None and grupo.pk and (pregunta.grupo.orden, pregunta.grupo_id) >= (grupo.orden, grupo.pk):
            continue
        fuentes.append(
            {
                "clave": _clave_catalogo(pregunta),
                "titulo": pregunta.texto,
                "tipo_campo": pregunta.tipo,
                "opciones": pregunta.opciones or [],
            }
        )
    return fuentes


def validar_condicion_defecto(condicion, grupo=None):
    """Errores (lista de strings) de una condición por defecto del catálogo:
    misma semántica que el motor, con las claves del catálogo como universo."""
    from programas.services import condiciones

    anteriores = {
        fuente["clave"]: {"tipo": "campo", "tipo_campo": fuente["tipo_campo"]}
        for fuente in fuentes_condicion_defecto(grupo)
    }
    item = {"clave": clave_grupo_catalogo(grupo) if grupo is not None and grupo.pk else "g-nuevo"}
    return condiciones.validar_condicion(condicion, item, anteriores)


# ── Plan por defecto ─────────────────────────────────────────────────────────


def _item(diseno, tipo, clave, orden, padre=None, **campos):
    item = ItemDiseno(diseno=diseno, tipo=tipo, clave=clave, orden=orden, **campos)
    item.padre = padre
    return item


def plan_por_defecto(convocatoria, diseno=None, catalogo=None):
    """Los ítems del formulario de hoy, **sin guardar**, en orden de pantalla:
    cada grupo seguido de sus campos. Es lo que se sirve cuando la convocatoria
    no tiene diseño y lo que se persiste al abrir el constructor por primera vez.

    ``catalogo`` (de ``catalogo_convocatoria``) evita volver a leer preguntas,
    grupos y requisitos: los grupos salen de las preguntas, que ya traen el
    suyo —un grupo sin preguntas activas no se muestra de todos modos (RN-3)—.
    """
    items = []
    orden = 0
    if catalogo is None:
        preguntas, requisitos = _preguntas_activas(), None
        grupos = list(GrupoRequisito.objects.order_by("orden", "id"))
    else:
        preguntas, requisitos = catalogo
        grupos = sorted({p.grupo_id: p.grupo for p in preguntas if p.grupo_id}.values(), key=lambda g: (g.orden, g.pk))
    por_grupo = {g.pk: [] for g in grupos}
    sueltas = []
    for pregunta in preguntas:
        (por_grupo.get(pregunta.grupo_id) if pregunta.grupo_id in por_grupo else sueltas).append(pregunta)

    for grupo in grupos:
        hijos = por_grupo[grupo.pk]
        if not hijos:
            continue  # RN-3: un grupo vacío no se muestra
        item_g = _item(
            diseno,
            GRUPO,
            clave_grupo_catalogo(grupo),
            orden,
            grupo_catalogo=grupo,
            subtitulo=grupo.subtitulo,
            condicion=_resolver_condicion(grupo.condicion_defecto, preguntas),
            canal=grupo.canal,
        )
        orden += 1
        items.append(item_g)
        for posicion, pregunta in enumerate(hijos):
            items.append(_item(diseno, CAMPO, clave_pregunta(pregunta), posicion, padre=item_g, pregunta=pregunta))

    if sueltas:
        item_g = _item(diseno, GRUPO, CLAVE_GENERALES_SUELTAS, orden, etiqueta="Requisitos generales")
        orden += 1
        items.append(item_g)
        for posicion, pregunta in enumerate(sueltas):
            items.append(_item(diseno, CAMPO, clave_pregunta(pregunta), posicion, padre=item_g, pregunta=pregunta))

    for nivel, nombre, del_nivel in _requisitos_por_nivel(convocatoria, requisitos):
        if not del_nivel:
            continue
        clave, plantilla = NIVELES[nivel]
        item_g = _item(diseno, GRUPO, clave, orden, etiqueta=plantilla.format(nombre=nombre))
        orden += 1
        items.append(item_g)
        for posicion, requisito in enumerate(del_nivel):
            items.append(_item(diseno, CAMPO, clave_requisito(requisito), posicion, padre=item_g, requisito=requisito))
    return items


# ── Persistencia ─────────────────────────────────────────────────────────────


@transaction.atomic
def generar_por_defecto(diseno):
    """Persiste el plan por defecto como diseño de la convocatoria."""
    diseno.items.all().delete()
    for item in plan_por_defecto(diseno.convocatoria, diseno):
        if item.padre is not None:
            item.padre_id = item.padre.pk
        item.save()
    return diseno


def bloquear(diseno):
    """Toma el candado de la fila del diseño (BEC-16).

    Un solo lugar para que el orden sea siempre el mismo —primero el diseño,
    después sus ítems— y para que se vea en el registro de `RED-67` quién lo pide.
    En SQLite `select_for_update()` es un no-op: lo que vale en los tres motores
    es que todo el que escribe el diseño pase por acá.
    """
    DisenoFormulario.objects.select_for_update().filter(pk=diseno.pk).first()
    return diseno


@transaction.atomic
def obtener_o_crear_diseno(convocatoria, usuario=None, reconciliar_con_catalogo=True):
    """El diseño de la convocatoria, generado si no existía y reconciliado con
    el catálogo si ya estaba. Es lo que abre el constructor.

    ``reconciliar_con_catalogo=False`` lo usan los POST de mutación (BEC-16): ahí
    el diseño no se sincroniza con el catálogo, porque reconciliar **escribe** y
    hacerlo en cada request convertía un guardado de orden en dos escrituras
    distintas compitiendo por las mismas claves. La reconciliación pasa a ocurrir
    donde tiene sentido: al abrir la pantalla.
    """
    diseno, creado = DisenoFormulario.objects.get_or_create(convocatoria=convocatoria)
    if creado:
        generar_por_defecto(bloquear(diseno))
        return diseno, {}
    if not reconciliar_con_catalogo:
        return diseno, {}
    return diseno, reconciliar(diseno, usuario)


def items_ordenados(diseno):
    """Los ítems guardados en orden de pantalla: grupos por orden, cada uno
    seguido de sus hijos por orden. Un ítem suelto (sin grupo) va al final."""
    todos = list(
        diseno.items.select_related("pregunta__grupo", "requisito", "grupo_catalogo", "padre").order_by("orden", "id")
    )
    grupos = [i for i in todos if i.es_grupo]
    hijos_de = {}
    sueltos = []
    for item in todos:
        if item.es_grupo:
            continue
        (hijos_de.setdefault(item.padre_id, []) if item.padre_id else sueltos).append(item)
    ordenados = []
    for grupo in grupos:
        ordenados.append(grupo)
        ordenados.extend(hijos_de.get(grupo.pk, []))
    ordenados.extend(sueltos)
    return ordenados


def _siguiente_orden(diseno, padre):
    ultimo = diseno.items.filter(padre=padre).aggregate(m=models.Max("orden"))["m"]
    return 0 if ultimo is None else ultimo + 1


def _catalogo_esperado(convocatoria, catalogo=None):
    """Lo que el catálogo dice que tiene que estar en el diseño (RN-1):
    ``(esperadas, esperados)`` como ``{pk: PreguntaGlobal}`` (activas) y
    ``{pk: (nivel, nombre, RequisitoNativo)}`` (herencia de la convocatoria).
    Con ``catalogo`` (de ``catalogo_convocatoria``) no vuelve a la base."""
    preguntas, requisitos = catalogo if catalogo is not None else (_preguntas_activas(), None)
    esperadas = {p.pk: p for p in preguntas}
    esperados = {}
    for nivel, nombre, del_nivel in _requisitos_por_nivel(convocatoria, requisitos):
        for requisito in del_nivel:
            esperados[requisito.pk] = (nivel, nombre, requisito)
    return esperadas, esperados


def _datos_grupo_para_pregunta(pregunta, preguntas):
    """Con qué nace el ítem grupo donde cae un requisito general: el de su
    grupo del catálogo (título del catálogo, condición por defecto resuelta) o
    «Requisitos generales» para una pregunta suelta."""
    if pregunta.grupo_id:
        grupo = pregunta.grupo
        return {
            "clave": clave_grupo_catalogo(grupo),
            "etiqueta": "",
            "subtitulo": grupo.subtitulo,
            "condicion": _resolver_condicion(grupo.condicion_defecto, preguntas),
            "canal": grupo.canal,
            "grupo_catalogo": grupo,
        }
    return {
        "clave": CLAVE_GENERALES_SUELTAS,
        "etiqueta": "Requisitos generales",
        "subtitulo": "",
        "condicion": None,
        "canal": CanalFormulario.AMBOS,
        "grupo_catalogo": None,
    }


def _datos_grupo_para_nivel(nivel, nombre):
    clave, plantilla = NIVELES[nivel]
    return {"clave": clave, "etiqueta": plantilla.format(nombre=nombre)}


def _grupo_para_pregunta(diseno, pregunta, grupos_por_clave, preguntas):
    """El ítem grupo donde cae un requisito general nuevo: el de su grupo del
    catálogo, creado si el diseño todavía no lo tenía."""
    datos = _datos_grupo_para_pregunta(pregunta, preguntas)
    if datos["clave"] not in grupos_por_clave:
        grupos_por_clave[datos["clave"]] = ItemDiseno.objects.create(
            diseno=diseno, tipo=GRUPO, orden=_siguiente_orden(diseno, None), **datos
        )
    return grupos_por_clave[datos["clave"]]


def _grupo_para_nivel(diseno, nivel, nombre, grupos_por_clave):
    datos = _datos_grupo_para_nivel(nivel, nombre)
    if datos["clave"] not in grupos_por_clave:
        grupos_por_clave[datos["clave"]] = ItemDiseno.objects.create(
            diseno=diseno, tipo=GRUPO, orden=_siguiente_orden(diseno, None), **datos
        )
    return grupos_por_clave[datos["clave"]]


@transaction.atomic
def reconciliar(diseno, usuario=None):
    """El diseño sigue al catálogo (RN-1): agrega al final de su grupo por
    defecto lo que falte, quita lo que ya no exista o esté inactivo, y elimina
    las condiciones que apuntaban a lo quitado. Devuelve el detalle para avisar
    y sube la versión si cambió algo.

    **Candado del diseño (BEC-16).** Escribe, así que no puede correr dos veces a
    la vez sobre el mismo diseño: dos operadores abriendo el constructor en el
    mismo momento creaban los ítems que faltaban los dos y el segundo moría con
    un `IntegrityError` de `uniq_item_diseno_clave` —un 500 en un GET—. Se
    serializa por la fila del `DisenoFormulario`, que es el mismo candado que
    toma `_mutar`.
    """
    bloquear(diseno)
    convocatoria = diseno.convocatoria
    items = list(diseno.items.select_related("pregunta", "requisito", "grupo_catalogo"))
    por_pregunta = {i.pregunta_id: i for i in items if i.pregunta_id}
    por_requisito = {i.requisito_id: i for i in items if i.requisito_id}
    grupos_por_clave = {i.clave: i for i in items if i.es_grupo}

    esperadas, esperados = _catalogo_esperado(convocatoria)

    quitados, agregados = [], []
    padres_vaciados = set()
    for item in items:
        sobra = (item.pregunta_id and item.pregunta_id not in esperadas) or (
            item.requisito_id and item.requisito_id not in esperados
        )
        if sobra:
            quitados.append((item.clave, item.titulo))
            if item.padre_id:
                padres_vaciados.add(item.padre_id)
            item.delete()

    for pk, pregunta in esperadas.items():
        if pk in por_pregunta:
            continue
        grupo = _grupo_para_pregunta(diseno, pregunta, grupos_por_clave, list(esperadas.values()))
        ItemDiseno.objects.create(
            diseno=diseno,
            tipo=CAMPO,
            clave=clave_pregunta(pregunta),
            padre=grupo,
            orden=_siguiente_orden(diseno, grupo),
            pregunta=pregunta,
        )
        agregados.append(pregunta.texto)
    for pk, (nivel, nombre, requisito) in esperados.items():
        if pk in por_requisito:
            continue
        grupo = _grupo_para_nivel(diseno, nivel, nombre, grupos_por_clave)
        ItemDiseno.objects.create(
            diseno=diseno,
            tipo=CAMPO,
            clave=clave_requisito(requisito),
            padre=grupo,
            orden=_siguiente_orden(diseno, grupo),
            requisito=requisito,
        )
        agregados.append(requisito.texto)

    # Un grupo automático —del catálogo o de nivel— que se quedó sin hijos
    # **porque el catálogo se los quitó en esta pasada** no se muestra (RN-3) y
    # tampoco se guarda: se borra y, si vuelve a hacer falta, lo recrean
    # ``_grupo_para_pregunta``/``_grupo_para_nivel``. Un grupo que el operador
    # vació a mano (movió sus campos a otro lado) se conserva con su condición y
    # su etiqueta: borrarlo perdería, por ejemplo, el «edad < 18» del Apoderado
    # sin aviso. Los grupos propios del operador se conservan siempre.
    automaticas = {clave for clave, _ in NIVELES.values()} | {CLAVE_GENERALES_SUELTAS}
    grupos_vacios = [
        g
        for g in diseno.items.filter(tipo=GRUPO, pk__in=padres_vaciados)
        .annotate(n_hijos=models.Count("hijos"))
        .filter(n_hijos=0)
        if g.grupo_catalogo_id or g.clave in automaticas
    ]
    for grupo in grupos_vacios:
        grupo.delete()

    # Una condición cuya fuente ya no está en el diseño (quitada acá, o borrada
    # del catálogo con CASCADE antes de llegar) se elimina con aviso.
    condiciones_quitadas = []
    claves_existentes = set(diseno.items.values_list("clave", flat=True))
    for item in diseno.items.filter(condicion__isnull=False):
        reglas = (item.condicion or {}).get("reglas") or []
        if any(regla.get("fuente") not in claves_existentes for regla in reglas):
            condiciones_quitadas.append(item.titulo)
            item.condicion = None
            item.save(update_fields=["condicion", "modificado"])

    if agregados or quitados or condiciones_quitadas or grupos_vacios:
        diseno.tocar(usuario)
    return {"agregados": agregados, "quitados": [t for _, t in quitados], "condiciones_quitadas": condiciones_quitadas}


def items_vigentes(diseno, catalogo=None):
    """Los ítems del diseño **como quedarían tras reconciliar**, sin escribir.

    Es lo que se sirve al portal y a la app: el diseño sigue al catálogo (RN-1)
    también entre visitas al constructor. Lo que el catálogo quitó o desactivó
    no se emite; lo que agregó entra al final de su grupo por defecto (creado
    en memoria si el diseño no lo tenía); una condición cuya fuente ya no está
    se ignora. Nada de esto se persiste: eso lo hace ``reconciliar`` cuando se
    abre el constructor, que además avisa. ``catalogo`` (de
    ``catalogo_convocatoria``) ahorra releer el catálogo.
    """
    esperadas, esperados = _catalogo_esperado(diseno.convocatoria, catalogo)
    preguntas = list(esperadas.values())
    vigentes = [
        item
        for item in items_ordenados(diseno)
        if not (
            (item.pregunta_id and item.pregunta_id not in esperadas)
            or (item.requisito_id and item.requisito_id not in esperados)
        )
    ]
    grupos_por_clave = {i.clave: i for i in vigentes if i.es_grupo}
    presentes_p = {i.pregunta_id for i in vigentes if i.pregunta_id}
    presentes_r = {i.requisito_id for i in vigentes if i.requisito_id}
    grupos_nuevos = []
    nuevos_por_grupo = {}

    def grupo_para(datos):
        if datos["clave"] not in grupos_por_clave:
            item_g = ItemDiseno(diseno=diseno, tipo=GRUPO, orden=len(grupos_por_clave), **datos)
            grupos_por_clave[datos["clave"]] = item_g
            grupos_nuevos.append(item_g)
        return grupos_por_clave[datos["clave"]]

    for pk, pregunta in esperadas.items():
        if pk in presentes_p:
            continue
        grupo = grupo_para(_datos_grupo_para_pregunta(pregunta, preguntas))
        nuevos_por_grupo.setdefault(grupo.clave, []).append(
            _item(diseno, CAMPO, clave_pregunta(pregunta), 0, padre=grupo, pregunta=pregunta)
        )
    for pk, (nivel, nombre, requisito) in esperados.items():
        if pk in presentes_r:
            continue
        grupo = grupo_para(_datos_grupo_para_nivel(nivel, nombre))
        nuevos_por_grupo.setdefault(grupo.clave, []).append(
            _item(diseno, CAMPO, clave_requisito(requisito), 0, padre=grupo, requisito=requisito)
        )

    # Orden de pantalla: cada grupo, sus hijos guardados y después los nuevos.
    hijos_de = {}
    for item in vigentes:
        if not item.es_grupo and item.padre_id:
            hijos_de.setdefault(item.padre_id, []).append(item)
    resultado = []
    for grupo in [i for i in vigentes if i.es_grupo] + grupos_nuevos:
        resultado.append(grupo)
        hijos = hijos_de.get(grupo.pk, []) if grupo.pk else []
        nuevos = nuevos_por_grupo.get(grupo.clave, [])
        for posicion, hijo in enumerate(nuevos, start=len(hijos)):
            hijo.orden = posicion
        resultado.extend(hijos)
        resultado.extend(nuevos)
    resultado.extend(i for i in vigentes if not i.es_grupo and not i.padre_id)

    # Una condición cuya fuente ya no está no se aplica (solo en memoria).
    claves = {i.clave for i in resultado}
    for item in resultado:
        reglas = (item.condicion or {}).get("reglas") or []
        if reglas and any(regla.get("fuente") not in claves for regla in reglas):
            item.condicion = None
    return resultado


# ── Serialización ────────────────────────────────────────────────────────────


def campo_dict(item):
    """La definición de un campo del diseño: la del catálogo (misma forma que
    ``definicion_formulario`` de siempre) con la etiqueta del diseño encima, o
    la del campo propio."""
    from programas.services.becas import _alcance_requisito, _campo_dict

    if item.pregunta_id:
        datos = _campo_dict(item.pregunta, "global")
    elif item.requisito_id:
        datos = _campo_dict(item.requisito, _alcance_requisito(item.requisito))
    else:
        propio = item.propio or {}
        datos = {
            "id": None,
            "texto": propio.get("texto", ""),
            "tipo": propio.get("tipo", ""),
            "opciones": propio.get("opciones") or [],
            "presentacion": propio.get("presentacion", "LISTA"),
            "obligatorio": bool(propio.get("obligatorio")),
            "orden": item.orden,
            "alcance": "propio",
            "subsegmento_id": None,
            "canal": item.canal,
            "origen": OrigenRequisito.PREGUNTA,
            "vinculo": "",
            "grupo": None,
        }
    datos["clave"] = item.clave
    datos["texto"] = item.titulo
    datos["condicion"] = item.condicion
    return datos


def items_planos(items, canal=None):
    """Lo que necesita el motor de condiciones: ``clave, tipo, padre, condicion,
    tipo_campo`` en orden, solo lo que se pide en ``canal``."""
    planos = []
    excluidos = set()
    for item in items:
        padre_clave = item.padre.clave if item.padre is not None else None
        if not item.se_pide_en(canal) or padre_clave in excluidos:
            excluidos.add(item.clave)
            continue
        plano = {"clave": item.clave, "tipo": item.tipo, "padre": padre_clave, "condicion": item.condicion}
        if item.es_campo:
            plano["tipo_campo"] = campo_dict(item)["tipo"]
        planos.append(plano)
    return planos


def _condicion_en_canal(condicion, claves_del_canal):
    """La condición, o ``None`` si alguna de sus fuentes no se pide en este canal.

    BEC-04: una regla cuya fuente no se pregunta en el canal servido **nunca** se
    cumple —la fuente llega vacía y ``evaluar_regla`` devuelve ``False``—, así que
    el ítem quedaba oculto para siempre y el servidor tampoco lo exigía. Es el
    mismo criterio que ya aplicaba ``items_vigentes`` cuando la fuente desaparecía
    del diseño: sin condición evaluable, el ítem se pide. Pedir de más es
    recuperable; no pedir nunca un requisito obligatorio, no.

    El constructor rechaza estos diseños al editarlos (``_asegurar_coherencia``),
    pero los que ya están guardados se siguen sirviendo y tienen que servirse bien.
    """
    reglas = (condicion or {}).get("reglas") or []
    if reglas and any(not isinstance(r, dict) or r.get("fuente") not in claves_del_canal for r in reglas):
        return None
    return condicion


def serializar(items, canal=None):
    """La estructura anidada de la definición v2: grupos con sus campos y textos,
    filtrada por canal. Un grupo sin hijos visibles no se emite (RN-3)."""
    claves_del_canal = {i.clave for i in items if i.se_pide_en(canal)}
    grupos = []
    actual = None
    for item in items:
        if not item.se_pide_en(canal):
            if item.es_grupo:
                actual = None
            continue
        condicion = _condicion_en_canal(item.condicion, claves_del_canal)
        if item.es_grupo:
            actual = {
                "tipo": "grupo",
                "clave": item.clave,
                "titulo": item.titulo,
                "subtitulo": item.subtitulo,
                "condicion": condicion,
                "canal": item.canal_efectivo,
                "items": [],
            }
            grupos.append(actual)
            continue
        if actual is None:
            continue  # ítem suelto sin grupo: no se muestra
        if item.es_texto:
            actual["items"].append({"tipo": "texto", "clave": item.clave, "texto": item.texto, "condicion": condicion})
        else:
            datos = campo_dict(item)
            datos["tipo_item"] = "campo"
            datos["condicion"] = condicion
            actual["items"].append(datos)
    return [g for g in grupos if g["items"]]
