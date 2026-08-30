"""Diseño del formulario por convocatoria (Cambio 58, RN-1..RN-3; tasks #339 y #340).

El diseño es un **orden sobre el catálogo vivo**: nunca falta un requisito del
catálogo ni sobra uno borrado. Una convocatoria sin diseño guardado se sirve
con el **plan por defecto** (los grupos del catálogo con sus preguntas y un
grupo por nivel de requisitos), sin escribir nada: el diseño se persiste la
primera vez que alguien abre el constructor. Desde ahí, cada vez que se sirve
se **reconcilia**: los requisitos nuevos aparecen al final de su grupo por
defecto, los borrados o desactivados salen, y las condiciones que los usaban se
eliminan con aviso.
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


def _requisitos_por_nivel(convocatoria):
    """``[(nivel, nombre, [RequisitoNativo])]`` en el orden programa → segmento
    → subsegmento, con la misma herencia que ``get_campos_formulario`` (RN-32)."""
    niveles = []
    segmento = convocatoria.segmento
    if segmento.programa_id:
        programa = segmento.programa
        niveles.append(("programa", programa.nombre, list(programa.requisitos.order_by("orden", "id"))))
    niveles.append(
        (
            "segmento",
            segmento.nombre,
            list(
                RequisitoNativo.objects.filter(segmento_id=segmento.pk, subsegmento__isnull=True).order_by(
                    "orden", "id"
                )
            ),
        )
    )
    if convocatoria.subsegmento_id:
        subsegmento = convocatoria.subsegmento
        niveles.append(("subsegmento", subsegmento.nombre, list(subsegmento.requisitos.order_by("orden", "id"))))
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


# ── Plan por defecto ─────────────────────────────────────────────────────────


def _item(diseno, tipo, clave, orden, padre=None, **campos):
    item = ItemDiseno(diseno=diseno, tipo=tipo, clave=clave, orden=orden, **campos)
    item.padre = padre
    return item


def plan_por_defecto(convocatoria, diseno=None):
    """Los ítems del formulario de hoy, **sin guardar**, en orden de pantalla:
    cada grupo seguido de sus campos. Es lo que se sirve cuando la convocatoria
    no tiene diseño y lo que se persiste al abrir el constructor por primera vez.
    """
    items = []
    orden = 0
    preguntas = _preguntas_activas()

    grupos = list(GrupoRequisito.objects.order_by("orden", "id"))
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

    for nivel, nombre, requisitos in _requisitos_por_nivel(convocatoria):
        if not requisitos:
            continue
        clave, plantilla = NIVELES[nivel]
        item_g = _item(diseno, GRUPO, clave, orden, etiqueta=plantilla.format(nombre=nombre))
        orden += 1
        items.append(item_g)
        for posicion, requisito in enumerate(requisitos):
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


def obtener_o_crear_diseno(convocatoria, usuario=None):
    """El diseño de la convocatoria, generado si no existía y reconciliado con
    el catálogo si ya estaba. Es lo que abre el constructor."""
    diseno, creado = DisenoFormulario.objects.get_or_create(convocatoria=convocatoria)
    if creado:
        generar_por_defecto(diseno)
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


def _grupo_para_pregunta(diseno, pregunta, grupos_por_clave, preguntas):
    """El ítem grupo donde cae un requisito general nuevo: el de su grupo del
    catálogo, creado si el diseño todavía no lo tenía."""
    if pregunta.grupo_id:
        clave = clave_grupo_catalogo(pregunta.grupo)
        etiqueta, subtitulo, canal, catalogo = "", pregunta.grupo.subtitulo, pregunta.grupo.canal, pregunta.grupo
        condicion = _resolver_condicion(pregunta.grupo.condicion_defecto, preguntas)
    else:
        clave, etiqueta, subtitulo, condicion, canal, catalogo = (
            CLAVE_GENERALES_SUELTAS,
            "Requisitos generales",
            "",
            None,
            CanalFormulario.AMBOS,
            None,
        )
    if clave not in grupos_por_clave:
        grupos_por_clave[clave] = ItemDiseno.objects.create(
            diseno=diseno,
            tipo=GRUPO,
            clave=clave,
            orden=_siguiente_orden(diseno, None),
            etiqueta=etiqueta,
            subtitulo=subtitulo,
            condicion=condicion,
            canal=canal,
            grupo_catalogo=catalogo,
        )
    return grupos_por_clave[clave]


def _grupo_para_nivel(diseno, nivel, nombre, grupos_por_clave):
    clave, plantilla = NIVELES[nivel]
    if clave not in grupos_por_clave:
        grupos_por_clave[clave] = ItemDiseno.objects.create(
            diseno=diseno,
            tipo=GRUPO,
            clave=clave,
            orden=_siguiente_orden(diseno, None),
            etiqueta=plantilla.format(nombre=nombre),
        )
    return grupos_por_clave[clave]


@transaction.atomic
def reconciliar(diseno, usuario=None):
    """El diseño sigue al catálogo (RN-1): agrega al final de su grupo por
    defecto lo que falte, quita lo que ya no exista o esté inactivo, y elimina
    las condiciones que apuntaban a lo quitado. Devuelve el detalle para avisar
    y sube la versión si cambió algo."""
    convocatoria = diseno.convocatoria
    items = list(diseno.items.select_related("pregunta", "requisito", "grupo_catalogo"))
    por_pregunta = {i.pregunta_id: i for i in items if i.pregunta_id}
    por_requisito = {i.requisito_id: i for i in items if i.requisito_id}
    grupos_por_clave = {i.clave: i for i in items if i.es_grupo}

    esperadas = {p.pk: p for p in _preguntas_activas()}
    esperados = {}
    for nivel, nombre, requisitos in _requisitos_por_nivel(convocatoria):
        for requisito in requisitos:
            esperados[requisito.pk] = (nivel, nombre, requisito)

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


def serializar(items, canal=None):
    """La estructura anidada de la definición v2: grupos con sus campos y textos,
    filtrada por canal. Un grupo sin hijos visibles no se emite (RN-3)."""
    grupos = []
    actual = None
    for item in items:
        if not item.se_pide_en(canal):
            if item.es_grupo:
                actual = None
            continue
        if item.es_grupo:
            actual = {
                "tipo": "grupo",
                "clave": item.clave,
                "titulo": item.titulo,
                "subtitulo": item.subtitulo,
                "condicion": item.condicion,
                "canal": item.canal_efectivo,
                "items": [],
            }
            grupos.append(actual)
            continue
        if actual is None:
            continue  # ítem suelto sin grupo: no se muestra
        if item.es_texto:
            actual["items"].append(
                {"tipo": "texto", "clave": item.clave, "texto": item.texto, "condicion": item.condicion}
            )
        else:
            datos = campo_dict(item)
            datos["tipo_item"] = "campo"
            actual["items"].append(datos)
    return [g for g in grupos if g["items"]]
