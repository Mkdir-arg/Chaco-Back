"""Mutaciones del constructor de formularios, compartidas por sus dos dueños.

El constructor (Cambio 58) edita un ``DisenoFormulario`` sea de una convocatoria de
Becas o de un tipo de dispositivo (P17). Lo que no depende de quién es el dueño
vive acá —el candado, la validación de coherencia, la versión y cada operación
sobre los ítems—, y cada pantalla pone solo su acceso y sus URLs
(``programas.views.diseno`` y ``programas.views.dispositivos_formularios``): una
vista no importa de otra (``programas.tests.test_arquitectura``).

**Cada mutación corre en una transacción** (D8): toma el candado del diseño,
valida las condiciones sobre el diseño resultante (RN-6: la fuente siempre antes)
y, si algo no cierra, se deshace entera y levanta :class:`DisenoInvalido` con el
motivo ya redactado para el operador.
"""

from __future__ import annotations

from django.db import transaction
from django.http import Http404

from programas.models import CanalFormulario, ItemDiseno, PresentacionCampo
from programas.services import condiciones as cond
from programas.services.diseno import bloquear, campo_dict, items_ordenados, items_planos, nueva_clave

GRUPO = ItemDiseno.Tipo.GRUPO
CAMPO = ItemDiseno.Tipo.CAMPO
TEXTO = ItemDiseno.Tipo.TEXTO


class DisenoInvalido(Exception):
    """Una mutación deja el diseño incoherente: se deshace y se explica."""

    def __init__(self, errores):
        super().__init__("Diseño inválido")
        self.errores = errores  # {clave: [mensajes]}
        self.mensaje = ""


def item_por_clave(diseno, clave):
    """El ítem del diseño con esa clave, o 404 (mismo trato que la URL)."""
    item = (
        diseno.items.select_related("pregunta__grupo", "requisito", "grupo_catalogo", "padre")
        .filter(clave=clave)
        .first()
    )
    if item is None:
        raise Http404("Ítem inexistente.")
    return item


# ── Datos para la pantalla ───────────────────────────────────────────────────


def datos(diseno, items):
    """Lo que consume la vista previa y los modales: cada ítem en orden con lo
    que el catálogo o el diseño saben de él. Es también el mapa de qué se puede
    hacer con cada ítem (`eliminable`, `canal_editable`...)."""
    hijos_por_padre = {}
    for item in items:
        if item.padre_id:
            hijos_por_padre[item.padre_id] = hijos_por_padre.get(item.padre_id, 0) + 1

    lista = []
    for item in items:
        dato = {
            "clave": item.clave,
            "tipo": item.tipo,
            "padre": item.padre.clave if item.padre_id else None,
            "titulo": item.titulo,
            "etiqueta": item.etiqueta,
            "subtitulo": item.subtitulo,
            "texto": item.texto,
            "condicion": item.condicion,
            "canal": item.canal_efectivo,
        }
        if item.es_grupo:
            dato.update(
                {
                    "catalogo": bool(item.grupo_catalogo_id),
                    "protegido": bool(item.grupo_catalogo_id and item.grupo_catalogo.protegido),
                    "hijos": hijos_por_padre.get(item.pk, 0),
                    "eliminable": hijos_por_padre.get(item.pk, 0) == 0,
                    "canal_editable": True,
                }
            )
        elif item.es_texto:
            dato.update({"eliminable": True, "canal_editable": True})
        else:
            campo = campo_dict(item)
            objeto = item.objeto_catalogo
            dato.update(
                {
                    "tipo_campo": campo["tipo"],
                    "opciones": campo.get("opciones") or [],
                    "presentacion": campo.get("presentacion") or PresentacionCampo.LISTA,
                    "obligatorio": bool(campo.get("obligatorio")),
                    "alcance": campo.get("alcance"),
                    "origen": campo.get("origen"),
                    "vinculo": campo.get("vinculo") or "",
                    "texto_catalogo": objeto.texto if objeto is not None else (item.propio or {}).get("texto", ""),
                    "protegido": bool(item.pregunta_id and item.pregunta.protegido),
                    "propio": item.es_propio,
                    "eliminable": item.es_propio,
                    "canal_editable": item.es_propio,
                }
            )
        item.ui = dato  # lo usa el parcial para los badges sin recalcular
        lista.append(dato)
    return {"version": diseno.version, "items": lista}


def arbol(items):
    """``[(grupo, [hijos])]`` para el parcial; los sueltos (no debería haber)
    van bajo ``None``."""
    resultado = []
    indice = {}
    sueltos = []
    for item in items:
        if item.es_grupo:
            indice[item.pk] = []
            resultado.append((item, indice[item.pk]))
        elif item.padre_id in indice:
            indice[item.padre_id].append(item)
        else:
            sueltos.append(item)
    if sueltos:
        resultado.append((None, sueltos))
    return resultado


def operadores():
    """Catálogo de operadores para el editor de condiciones (espejo de
    ``services.condiciones``). Lo alimenta también el editor de grupos del
    catálogo (``pregunta_list.html``).

    ``por_tipo`` es lo que se **ofrece** y ``aceptados`` lo que el servidor valida
    (``OPERADORES_POR_TIPO``): la diferencia (``OPERADORES_NO_OFRECIDOS``, #341) se
    muestra solo en la regla guardada que ya la usa."""
    return {
        "por_tipo": {
            tipo: sorted(ops - cond.OPERADORES_NO_OFRECIDOS.get(tipo, set()))
            for tipo, ops in cond.OPERADORES_POR_TIPO.items()
        },
        "aceptados": {tipo: sorted(ops) for tipo, ops in cond.OPERADORES_POR_TIPO.items()},
        "etiquetas": cond.ETIQUETAS_OPERADOR,
        "sin_valor": sorted(cond.SIN_VALOR),
        "con_lista": sorted(cond.CON_LISTA),
    }


def mensaje_errores(errores, titulos=None):
    """El motivo del rechazo para el operador: con el nombre de los ítems, no
    sus claves («Fecha de nacimiento», no «pg-9»)."""
    titulos = titulos or {}
    partes = []
    for clave, mensajes in errores.items():
        for mensaje in mensajes:
            for otra, titulo in titulos.items():
                mensaje = mensaje.replace(f"«{otra}»", f"«{titulo}»")
            partes.append(f"{titulos.get(clave, clave)}: {mensaje}")
    return " ".join(partes) if partes else "El diseño quedó incoherente."


# ── Coherencia ───────────────────────────────────────────────────────────────

#: Los canales que se sirven de verdad, con el nombre que entiende el operador.
#: ``AMBOS`` no se valida aparte: es la unión de estos dos.
CANALES_SERVIDOS = (
    (CanalFormulario.APP, "la app de campo"),
    (CanalFormulario.LINK, "el link público"),
)


def errores_por_canal(items):
    """``{clave: [errores]}`` de las condiciones imposibles en algún canal (BEC-04).

    Mirado entero el diseño puede estar bien —la fuente existe y está antes— y aun
    así dejar un ítem imposible en uno de los dos canales, porque ahí su fuente no
    se pregunta. Se junta todo en un solo mapa para poder **comparar** dos estados
    del diseño, que es lo que necesita `mutar`.
    """
    errores = {}
    for canal, etiqueta in CANALES_SERVIDOS:
        for clave, mensajes in cond.fuentes_fuera_del_canal(items_planos(items, canal), etiqueta).items():
            errores.setdefault(clave, []).extend(mensajes)
    return errores


def solo_lo_nuevo(errores, previos):
    """Los errores que **no** estaban antes de la mutación.

    Un diseño guardado antes de BEC-04 puede traer una condición imposible desde
    siempre. Rechazar toda mutación por eso dejaría el formulario congelado —no se
    podría ni renombrar un grupo— hasta que alguien borre la condición ofensora, y
    el operador no tendría por qué saber cuál es. Mientras tanto la pantalla se
    sirve bien igual: `serializar` anula esa condición. Así que se bloquea lo que
    esta edición **agrega**, no lo que encontró.
    """
    nuevos = {}
    for clave, mensajes in errores.items():
        faltantes = [m for m in mensajes if m not in previos.get(clave, [])]
        if faltantes:
            nuevos[clave] = faltantes
    return nuevos


def asegurar_coherencia(diseno, errores_previos=None):
    """Valida las condiciones sobre el diseño resultante y devuelve los ítems
    ya cargados (se reutilizan en la respuesta: una sola lectura).

    ``errores_previos`` es la foto por canal de **antes** de la mutación: con ella,
    los incumplimientos de BEC-04 que ya venían de antes no bloquean la edición
    (ver `solo_lo_nuevo`). Sin ella se exige el diseño entero coherente, que es lo
    que corresponde cuando no hay un «antes» con el que comparar.
    """
    items = items_ordenados(diseno)
    errores = cond.validar_coherencia(items_planos(items))
    if errores:
        raise DisenoInvalido(errores)
    por_canal = errores_por_canal(items)
    if errores_previos is not None:
        por_canal = solo_lo_nuevo(por_canal, errores_previos)
    if por_canal:
        raise DisenoInvalido(por_canal)
    return items


def mutar(diseno, usuario, operacion):
    """Corre ``operacion`` dentro de una transacción, valida el diseño
    resultante y sube la versión. Devuelve los ítems ya ordenados; si no cierra,
    deshace todo y levanta :class:`DisenoInvalido` con ``mensaje`` redactado.

    **Candado del diseño (BEC-16).** La fila del `DisenoFormulario` se bloquea
    antes de tocar nada: dos operadores guardando a la vez leían cada uno el
    diseño anterior y el segundo dejaba, por ejemplo, la fuente de una condición
    después de su destino —RN-6 rota— sin que ninguna de las dos validaciones se
    diera cuenta, porque cada una vio un diseño coherente.
    """
    try:
        with transaction.atomic():
            bloquear(diseno)
            # La foto de BEC-04 **antes** de tocar nada, con el candado ya tomado:
            # lo que esta edición no rompió no es asunto de esta edición.
            errores_previos = errores_por_canal(items_ordenados(diseno))
            operacion()
            items = asegurar_coherencia(diseno, errores_previos)
            diseno.tocar(usuario)
    except DisenoInvalido as exc:
        titulos = {i.clave: i.titulo or i.get_tipo_display() for i in items_ordenados(diseno)}
        exc.mensaje = mensaje_errores(exc.errores, titulos)
        raise
    return items


# ── Operaciones (corren adentro de `mutar`) ──────────────────────────────────


def siguiente_orden(diseno, padre):
    ultimo = diseno.items.filter(padre=padre).order_by("-orden").values_list("orden", flat=True).first()
    return 0 if ultimo is None else ultimo + 1


def mover(diseno, item, clave_padre, posicion):
    """Drag & drop. Los grupos se mueven en la raíz; campos y textos, dentro de
    un grupo. Si el movimiento deja una condición apuntando a una fuente
    posterior, lo rechaza `mutar` (RN-6)."""
    if item.es_grupo:
        if clave_padre:
            raise DisenoInvalido({item.clave: ["Un grupo no puede ir dentro de otro grupo."]})
        hermanos = [g for g in diseno.items.filter(tipo=GRUPO).order_by("orden", "id") if g.pk != item.pk]
        item.padre = None
    else:
        if not clave_padre:
            raise DisenoInvalido({item.clave: ["Un campo o un texto tiene que estar dentro de un grupo."]})
        padre = item_por_clave(diseno, clave_padre)
        if not padre.es_grupo:
            raise DisenoInvalido({item.clave: ["Solo se puede soltar dentro de un grupo."]})
        item.padre = padre
        hermanos = [h for h in padre.hijos.order_by("orden", "id") if h.pk != item.pk]
    destino = max(0, min(posicion, len(hermanos)))
    hermanos.insert(destino, item)
    for orden, hermano in enumerate(hermanos):
        if hermano.pk == item.pk:
            item.orden = orden
            item.save(update_fields=["padre", "orden", "modificado"])
        elif hermano.orden != orden:
            ItemDiseno.objects.filter(pk=hermano.pk).update(orden=orden)


def padre_para_nuevo(diseno, clave_padre):
    """El grupo donde va un texto o un campo nuevo, o ``None``."""
    if not clave_padre:
        return None
    return diseno.items.filter(clave=clave_padre, tipo=GRUPO).first()


def crear_grupo(diseno, datos_form):
    ItemDiseno.objects.create(
        diseno=diseno,
        tipo=GRUPO,
        clave=nueva_clave("g"),
        orden=siguiente_orden(diseno, None),
        etiqueta=datos_form["etiqueta"],
        subtitulo=datos_form["subtitulo"],
        canal=datos_form["canal"],
    )


def crear_texto(diseno, padre, datos_form):
    ItemDiseno.objects.create(
        diseno=diseno,
        tipo=TEXTO,
        clave=nueva_clave("t"),
        padre=padre,
        orden=siguiente_orden(diseno, padre),
        texto=datos_form["texto"],
        canal=datos_form["canal"],
    )


def crear_propio(diseno, padre, datos_form):
    ItemDiseno.objects.create(
        diseno=diseno,
        tipo=CAMPO,
        clave=nueva_clave("cp"),
        padre=padre,
        orden=siguiente_orden(diseno, padre),
        propio=datos_form["propio"],
        canal=datos_form["canal"],
    )


def editar(item, datos_form):
    """Lo que el diseño es dueño de cada ítem (RN-2): grupo → título, subtítulo
    y canal; texto → texto y canal; campo propio → todo; campo del catálogo →
    solo la etiqueta."""
    if item.es_grupo:
        item.etiqueta, item.subtitulo, item.canal = datos_form["etiqueta"], datos_form["subtitulo"], datos_form["canal"]
        item.save(update_fields=["etiqueta", "subtitulo", "canal", "modificado"])
    elif item.es_texto:
        item.texto, item.canal = datos_form["texto"], datos_form["canal"]
        item.save(update_fields=["texto", "canal", "modificado"])
    elif item.es_propio:
        item.propio, item.canal = datos_form["propio"], datos_form["canal"]
        item.save(update_fields=["propio", "canal", "modificado"])
    else:
        item.etiqueta = datos_form["etiqueta"]
        item.save(update_fields=["etiqueta", "modificado"])


def poner_condicion(item, condicion):
    item.condicion = condicion
    item.save(update_fields=["condicion", "modificado"])


def motivo_para_no_eliminar(item):
    """Por qué un ítem no se puede eliminar del diseño, o ``""``.

    Se eliminan textos, campos propios y grupos vacíos. Los requisitos del
    catálogo no se eliminan del diseño (RN-1): se mueven o se desactivan en el
    catálogo."""
    if item.es_campo and not item.es_propio:
        return (
            "Los requisitos del catálogo no se quitan del formulario: movelos de grupo o desactivalos en el catálogo."
        )
    if item.es_grupo and item.hijos.exists():
        return "El grupo tiene ítems adentro: movelos antes de eliminarlo."
    return ""
