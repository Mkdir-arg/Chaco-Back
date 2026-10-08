"""Lo que la app de campo manda al servidor: cuándo se acepta y qué se revisa
(G1-04 y G1-05, auditoría oct-2026).

Dos reglas, con el **mismo criterio**: la captura ya existe —la hizo un
territorial parado delante de una persona— y tirarla es perder trabajo de campo
sin dejar rastro. Así que se acepta y se marca, y solo se rechaza lo imposible.

**G1-04 · gracia de sincronización.** El teléfono guarda las cargas en una cola
offline y las sube cuando vuelve la señal. Si en el medio el cron de las 03:10
pasó el relevamiento a ``EN_REVISION``, el alta daba 409; y la app clasifica un
409 que no sea de pausa como ``FAILED_PERMANENT``
(``relevamientoService.js``), así que las capturas quedaban en el teléfono para
siempre y el backoffice nunca se enteraba de que existían. Ahora entran, dentro
de una ventana de gracia, marcadas como ``sincronizado_tarde``.

**G1-05 · lo que el servidor valida.** El link público pasa las respuestas por
el motor de condiciones y por la validación de cada campo; la API de campo no
validaba nada: un cliente con token podía crear un caso sin las obligatorias,
con opciones inexistentes o con respuestas a preguntas que el motor había
escondido —que después viajan a SIIS—. Acá se descarta lo oculto (D11, el mismo
efecto que en el link) y lo demás queda escrito en ``observaciones_carga``, que
la revisión muestra.

**G1-07 · los adjuntos.** El archivo de un campo ``ARCHIVO`` no viaja en el alta:
llega después, en un ``POST …/adjuntos/`` por campo. Ese endpoint no miraba nada:
un reintento de la cola offline creaba una fila más —y la revisión se quedaba con
la **más vieja**, así que el territorial veía su foto corregida ignorada— y el
campo al que se adjuntaba podía no existir en el formulario del relevamiento.
Acá hay un archivo por campo de archivo del caso, y la referencia se rechaza
**solo** cuando nunca pudo ser de esta convocatoria; la que quedó vieja entre la
captura y la sincronización entra observada, con el mismo criterio que G1-05.

**G1-16 · con qué versión se capturó.** La foto de la definición se guarda al
**sincronizar**, que puede ser días después de la captura. Si alguien editó el
formulario en el medio, el caso queda interpretado con un diseño que la persona
nunca vio. El servidor acepta —opcionalmente— la versión que el teléfono tenía
delante y, si no coincide con la que terminó guardando, lo deja observado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import AdjuntoFormulario, OrigenRequisito, Relevamiento, TipoCampo
from programas.services.respuestas import aplicar, campos_de, fecha_de_referencia

#: Lo que el legajo acepta como sexo: F, M y X (no binario).
GENEROS_DEL_LEGAJO = set(Ciudadano.Genero.values)

# D-G04 (README §2 de la auditoría): 24 h desde el cierre del período del
# relevamiento. G1 sugería 72 h y V6, 24; se aplica el default registrado.
GRACIA_SINCRONIZACION = timedelta(hours=24)

# Un relevamiento ya cerrado todavía acepta lo que se capturó en fecha, mientras
# dure la gracia. ``TERMINADO`` no: ahí los reportes ya salieron y sumar un caso
# cambiaría números ya informados.
ESTADOS_CON_GRACIA = (
    Relevamiento.Estado.FINALIZANDO,
    Relevamiento.Estado.FINALIZADO,
    Relevamiento.Estado.EN_REVISION,
)

# Tolerancia de reloj del teléfono hacia adelante (ya estaba en la vista).
ADELANTO_TOLERADO = timedelta(minutes=5)

FUERA_DE_PERIODO = "La captura se realizó fuera del período asignado."
NO_EN_CURSO = "Solo se pueden cargar personas en un relevamiento en curso."
GRACIA_VENCIDA = (
    "El relevamiento cerró hace más de 24 horas y ya no acepta cargas sincronizadas tarde. "
    "Avisá al coordinador para que las cargue desde el backoffice."
)


@dataclass(frozen=True)
class Decision:
    """Qué hacer con una captura que llega: aceptarla (y si llega tarde) o
    rechazarla con un cuerpo y un código."""

    acepta: bool
    tardia: bool = False
    detalle: str = ""
    status: int = 400

    @property
    def rechaza(self):
        return not self.acepta


def evaluar_captura(relevamiento, capturado_en, ahora=None):
    """¿Se acepta este alta y llega tarde? (G1-04)

    ``capturado_en`` es el momento en que el territorial cargó a la persona en
    el teléfono; ``None`` cuando la app no lo manda (carga en línea, app vieja),
    y ahí vale la regla de siempre: el relevamiento tiene que estar en curso y
    en fecha **ahora**.
    """
    ahora = ahora or timezone.now()

    if capturado_en is None:
        if relevamiento.estado != Relevamiento.Estado.EN_CURSO:
            return Decision(acepta=False, detalle=NO_EN_CURSO, status=409)
        if not relevamiento.habilitado_en(ahora):
            return Decision(acepta=False, detalle=FUERA_DE_PERIODO, status=400)
        return Decision(acepta=True)

    # Una captura del futuro no es una sincronización tardía: o el reloj del
    # teléfono está mal o el cuerpo viene armado a mano.
    if capturado_en > ahora + ADELANTO_TOLERADO:
        return Decision(acepta=False, detalle=FUERA_DE_PERIODO, status=400)
    if not relevamiento.habilitado_en(capturado_en):
        # Incluye la pausa: un relevamiento pausado no habilita ninguna fecha.
        return Decision(acepta=False, detalle=FUERA_DE_PERIODO, status=400)

    if relevamiento.estado == Relevamiento.Estado.EN_CURSO:
        return Decision(acepta=True)
    if relevamiento.estado not in ESTADOS_CON_GRACIA:
        # ASIGNADO (todavía no arrancó) y TERMINADO (ya se informó).
        return Decision(acepta=False, detalle=NO_EN_CURSO, status=409)
    if en_gracia(relevamiento, ahora):
        return Decision(acepta=True, tardia=True)
    return Decision(acepta=False, detalle=GRACIA_VENCIDA, status=409)


def en_gracia(relevamiento, ahora=None):
    """¿Estamos dentro de las 24 h posteriores al cierre del período?"""
    ahora = ahora or timezone.now()
    return bool(relevamiento.fecha_hasta and ahora <= relevamiento.fecha_hasta + GRACIA_SINCRONIZACION)


# ── G1-05 · revisión de lo que llegó ─────────────────────────────────────────


@dataclass
class Revision:
    """Lo que quedó de la carga después de pasarla por el servidor."""

    respuestas: dict
    observaciones: list = field(default_factory=list)

    @property
    def texto(self):
        return "\n".join(self.observaciones)


def revisar_carga(formulario, relevamiento=None, identidad=None):
    """Aplica al caso las mismas reglas que el link público (G1-05).

    Devuelve una :class:`Revision` con las respuestas **efectivas** —sin las de
    los ítems que el motor de condiciones escondió (D11)— y la lista de
    observaciones. **No rechaza nada:** lo imposible (un DNI que no es un DNI)
    lo frena antes el serializer, con un 400. Acá lo que hay son capturas
    legítimas con algo incompleto, y perderlas sería peor que registrarlas con
    la observación a la vista del revisor.

    ``identidad`` es el ``datos_identificacion`` que mandó la app: se lee acá
    porque ``resolver_ciudadano_offline`` lo borra al vincular el legajo.
    """
    definicion = formulario.definicion or {}
    respuestas = dict(formulario.respuestas or {})
    # G1-07: lo que dejó una subida posterior no lo sabe esta función y se
    # reescribe entero, así que se arrastra.
    observaciones = _observaciones_de_adjuntos(formulario)

    observaciones.extend(_observacion_de_version(formulario, definicion))

    _visibles, ocultos, _efectivas = aplicar(definicion, respuestas, hoy=fecha_de_referencia(formulario))
    # Se quitan **solo** las ocultas y no se reemplaza el diccionario por
    # ``efectivas``: una clave que la foto no tenga (un diseño que cambió
    # debajo) no se pierde por el camino.
    efectivas = {clave: valor for clave, valor in respuestas.items() if clave not in ocultos}

    for clave in sorted(set(respuestas) - set(efectivas)):
        observaciones.append(f"Se descartó la respuesta a «{_etiqueta(definicion, clave)}»: no correspondía pedirla.")

    for campo in campos_de(definicion):
        clave = campo.get("clave")
        if clave in ocultos:
            continue
        valor = efectivas.get(clave)
        if _vacio(valor):
            if campo.get("obligatorio") and _se_responde_en_el_alta(campo):
                observaciones.append(f"Falta la respuesta obligatoria «{campo.get('texto') or clave}».")
            continue
        observaciones.extend(_problemas_de_valor(campo, valor))

    sexo = str((identidad or {}).get("sexo") or (identidad or {}).get("genero") or "").strip().upper()
    if sexo and sexo not in GENEROS_DEL_LEGAJO:
        # `resolver_ciudadano_offline` lo descarta en silencio al crear el
        # legajo: la persona queda sin sexo y nadie sabe por qué. El legajo
        # acepta F, M y X (no binario); lo que se observa es lo que no es
        # ninguno de los tres, no «lo que no es F ni M».
        observaciones.append(f"El sexo de la persona llegó como «{sexo}» y no es un valor conocido: quedó sin cargar.")

    if _requiere_gps(relevamiento or formulario.relevamiento) and (
        formulario.gps_lat is None or formulario.gps_lng is None
    ):
        observaciones.append("El segmento pide ubicación GPS y la carga llegó sin coordenadas.")

    return Revision(respuestas=efectivas, observaciones=observaciones)


def aplicar_revision(formulario, revision):
    """Guarda lo que dejó :func:`revisar_carga`: las respuestas efectivas, el
    ``data`` del contrato anterior recalculado desde ellas y las observaciones.

    Devuelve ``True`` si escribió algo (para no pagar un UPDATE de más en la
    enorme mayoría de las cargas, que no tienen nada que observar)."""
    from programas.services.respuestas import legacy_desde_respuestas

    campos = ["modificado"]
    if revision.respuestas != (formulario.respuestas or {}):
        formulario.respuestas = revision.respuestas
        # ``data`` es el espejo del contrato anterior: si una respuesta se
        # descartó por oculta, tiene que irse de los dos lados o
        # ``respuestas_por_destino`` la seguiría mandando a SIIS.
        data, _fijos = legacy_desde_respuestas(revision.respuestas, formulario.definicion or {})
        formulario.data = data
        campos.extend(["respuestas", "data"])
    texto = revision.texto
    if texto != (formulario.observaciones_carga or ""):
        formulario.observaciones_carga = texto or None
        campos.append("observaciones_carga")
    if len(campos) == 1:
        return False
    formulario.save(update_fields=campos)
    return True


def _observacion_de_version(formulario, definicion):
    """G1-16 · ¿el teléfono capturó con otra versión del formulario?

    ``version_capturada`` es **opcional**: la app instalada
    (``Chaco-mobile@a66c2d3``) no la manda y ahí no hay nada que comparar, que es
    el caso de la enorme mayoría de las cargas. Cuando viene y difiere de la
    versión de la foto que el caso terminó guardando, el diseño cambió entre la
    captura y la sincronización: lo que el revisor ve en la pantalla no es
    exactamente lo que la persona tuvo delante.

    **No se reconstruye la foto de la versión vieja**, que es la otra opción que
    plantea la ficha: el diseño guarda un contador (``DisenoFormulario.version``)
    y no un historial, así que esa foto no existe en ningún lado. Se marca, que
    es lo que la ficha deja como alternativa.
    """
    capturada = formulario.version_capturada
    guardada = (definicion or {}).get("version")
    if capturada is None or guardada is None or capturada == guardada:
        return []
    return [
        f"La carga se hizo con la versión {capturada} del formulario y se guardó con la versión "
        f"{guardada}: el diseño cambió entre la captura y la sincronización."
    ]


# ── G1-07 · adjuntos de la app ───────────────────────────────────────────────

#: Los tres veredictos de :func:`pertenencia_del_adjunto`.
ADJUNTO_DEL_FORMULARIO = "del_formulario"
ADJUNTO_YA_NO_SE_PIDE = "ya_no_se_pide"
ADJUNTO_AJENO = "ajeno"

MENSAJE_ADJUNTO_AJENO = (
    "Ese campo no es un campo de archivo del formulario de este relevamiento, así que el archivo no se guardó."
)

# La línea que ve el revisor cuando el archivo entró pero su campo ya no está en
# el formulario. El prefijo es lo que la reconoce en ``observaciones_carga``
# (ver ``_observaciones_de_adjuntos``), así que los dos se mueven juntos.
PREFIJO_ADJUNTO_OBSERVADO = "Llegó el archivo de «"
ADJUNTO_OBSERVADO = (
    PREFIJO_ADJUNTO_OBSERVADO + "{campo}», un campo que el formulario de este relevamiento ya no pide: "
    "el archivo se guardó, pero no aparece entre las respuestas."
)


def definicion_del_caso(formulario, relevamiento=None):
    """La foto con la que se interpreta el caso.

    La que guardó al sincronizar (D3) y, mientras todavía no la tenga, la
    definición vigente de su relevamiento. El segundo camino no es teórico: el
    alta guarda la foto en ``_completar_alta`` y un caso creado por otra vía
    (backoffice, fixture) puede no tenerla nunca.
    """
    if formulario.definicion:
        return formulario.definicion
    from programas.services.becas import definicion_formulario

    return definicion_formulario(relevamiento or formulario.relevamiento)


def claves_de_archivo(definicion):
    """Las claves (``pg-<pk>`` / ``rn-<pk>`` / ``cp-…``) de los campos ``ARCHIVO``.

    Salen de la estructura anidada (``items``) y, si la definición las trae, de
    las listas planas ``globales``/``requisitos``. La foto que guarda el caso
    (``foto_definicion``) tiene solo ``items``; la definición vigente que sirve
    la API trae las dos.
    """
    definicion = definicion or {}
    claves = {campo.get("clave") for campo in campos_de(definicion) if campo.get("tipo") == TipoCampo.ARCHIVO}
    for lista, prefijo in (("globales", "pg"), ("requisitos", "rn")):
        for campo in definicion.get(lista) or []:
            if isinstance(campo, dict) and campo.get("tipo") == TipoCampo.ARCHIVO and campo.get("id") is not None:
                claves.add(f"{prefijo}-{campo['id']}")
    return claves


def pertenencia_del_adjunto(formulario, pregunta_global=None, requisito_nativo=None):
    """¿De dónde salió la referencia con la que llega este archivo? (G1-07)

    Tres respuestas, porque dos no alcanzaban. El teléfono baja la definición,
    captura offline y sincroniza días después; en el medio el PM puede desactivar
    un campo, sacarlo del diseño o cambiarle el canal. Con un solo «no» el
    servidor devolvía 400 por ese campo, y un 400 no es reintentable para la app
    (``relevamientoService.js:1486``): ``syncRemoteBecasFormulario`` corta el
    bucle de subidas en el primero que falla, la operación queda
    ``FAILED_PERMANENT`` y **los documentos que venían después, que el servidor
    sí aceptaba, no se suben nunca**. El reintento manual muere en el mismo
    lugar.

    * ``ADJUNTO_DEL_FORMULARIO`` — la clave está en la foto del caso o en la
      definición vigente del relevamiento. Vale primero la foto; si ahí no está,
      se mira la definición vigente, que incluye la **lista plana** que es lo
      único que lee la app instalada (``Chaco-mobile@a66c2d3``:
      ``mapDjangoRelevamientoDetail`` arma ``campos_definicion`` con
      ``globales``/``requisitos``, no con ``items``, y sube cada archivo con el
      ``id`` de esa lista). Las dos no coinciden siempre: un grupo del diseño
      acotado a otro canal saca sus campos de ``items`` pero no de la lista
      plana. La segunda mirada solo se paga cuando la primera no alcanzó.
    * ``ADJUNTO_YA_NO_SE_PIDE`` — es un campo ``ARCHIVO`` que **pudo** ser de
      esta convocatoria (una pregunta general, que aplica a todas; o un requisito
      de su herencia) y hoy no aparece en el formulario: se desactivó, salió del
      diseño o le cambiaron el canal. La captura ya existe, así que el archivo
      entra y queda observado para el revisor, igual que G1-05.
    * ``ADJUNTO_AJENO`` — lo que **nunca** pudo ser de esta convocatoria: el
      requisito de otro segmento, o un campo que no pide ningún archivo. Ese sí
      se rechaza: el documento no es de este caso, o no tiene dónde colgarse.
    """
    referencia = pregunta_global if pregunta_global is not None else requisito_nativo
    if referencia is None or getattr(referencia, "tipo", None) != TipoCampo.ARCHIVO:
        return ADJUNTO_AJENO
    clave = f"pg-{referencia.pk}" if pregunta_global is not None else f"rn-{referencia.pk}"
    if clave in claves_de_archivo(definicion_del_caso(formulario)):
        return ADJUNTO_DEL_FORMULARIO
    if formulario.definicion:
        # Sin foto, ``definicion_del_caso`` ya fue la definición vigente entera.
        from programas.services.becas import definicion_formulario

        if clave in claves_de_archivo(definicion_formulario(formulario.relevamiento)):
            return ADJUNTO_DEL_FORMULARIO
    if requisito_nativo is not None and not _requisito_de_la_convocatoria(formulario, requisito_nativo):
        return ADJUNTO_AJENO
    # Una ``PreguntaGlobal`` es del catálogo general —aplica a todas las
    # convocatorias—, así que siempre pudo estar en esta.
    return ADJUNTO_YA_NO_SE_PIDE


def _requisito_de_la_convocatoria(formulario, requisito):
    """¿Este requisito nativo pertenece a la herencia de la convocatoria del caso?

    Se pregunta con el **mismo** ``Q`` que arma la definición (RN-32) y no con
    una copia en memoria de la regla: que un requisito «sea de otro segmento» es
    exactamente lo contrario de que la definición lo sirva, y dos escrituras de
    la misma regla se separan. Es una consulta por el índice, y solo en el camino
    en el que la clave no estaba en ninguna de las dos definiciones.
    """
    from programas.models import RequisitoNativo
    from programas.services.becas import filtro_requisitos_convocatoria

    convocatoria = formulario.relevamiento.convocatoria
    return RequisitoNativo.objects.filter(filtro_requisitos_convocatoria(convocatoria), pk=requisito.pk).exists()


def observar_adjunto(formulario, referencia):
    """Deja en ``observaciones_carga`` que entró un archivo de un campo que el
    formulario ya no pide, sin repetir la línea cuando la cola reintenta.

    Es la contracara de aceptar: el documento se guarda, pero
    ``_adjuntos_por_clave`` lo indexa por una clave que la definición del caso no
    tiene, así que la pantalla de revisión no lo muestra. Sin esta línea el
    revisor ve el campo *faltante* y no se entera de que el archivo llegó.

    Devuelve ``True`` si escribió.
    """
    linea = ADJUNTO_OBSERVADO.format(campo=getattr(referencia, "texto", "") or "un campo del formulario")
    lineas = (formulario.observaciones_carga or "").splitlines()
    if linea in lineas:
        return False
    lineas.append(linea)
    formulario.observaciones_carga = "\n".join(lineas)
    formulario.save(update_fields=["observaciones_carga", "modificado"])
    return True


def _observaciones_de_adjuntos(formulario):
    """Las líneas de G1-07 que el caso ya tiene guardadas.

    ``aplicar_revision`` reescribe ``observaciones_carga`` entero, y el reintento
    del alta vuelve a pasar por ahí mientras el caso siga incompleto
    (``_alta_incompleta``), que puede ser después de una subida. Se conservan
    para que la observación del adjunto no desaparezca sin que nadie la lea.
    """
    return [
        linea
        for linea in (formulario.observaciones_carga or "").splitlines()
        if linea.startswith(PREFIJO_ADJUNTO_OBSERVADO)
    ]


def guardar_adjunto(formulario, *, archivo, pregunta_global=None, requisito_nativo=None):
    """Un archivo por campo de archivo del caso (G1-07).

    Si el campo ya tenía uno, se **reemplaza**: el reintento de la cola offline
    no deja dos filas, y el territorial que vuelve a sacar la foto porque la
    primera salió movida ve la segunda. El archivo viejo se borra del
    almacenamiento con ``transaction.on_commit``, nunca antes: si la transacción
    se cae, el adjunto que sigue valiendo es el que todavía está en ``media/``.

    El ``select_for_update`` bloquea la fila que el campo **ya tenía**, así que
    dos reintentos de la cola sobre un adjunto existente se ordenan uno detrás
    del otro. Lo que no evita es que dos subidas simultáneas del mismo campo
    *sin* fila previa creen una cada una: con ``READ COMMITTED`` una lectura que
    no encuentra nada no toma gap lock, y no hay restricción única en la base
    **a propósito**, porque producción ya tiene filas duplicadas de antes y una
    restricción no se podría crear sobre ellas. O sea que puede haber dos filas
    del mismo campo; con duplicados —los viejos y los de esa carrera— se opera
    sobre el más nuevo, que es también el que ``_adjuntos_por_clave`` le muestra
    al revisor.

    Si el campo ya no está en el formulario del relevamiento (G1-07, el diseño
    cambió entre la captura y la sincronización), el archivo entra igual y la
    observación queda escrita dentro de la misma transacción: un adjunto que la
    revisión no muestra sin la línea que lo explica es peor que no tenerlo.
    """
    with transaction.atomic():
        existente = (
            formulario.adjuntos.select_for_update()
            .filter(pregunta_global=pregunta_global, requisito_nativo=requisito_nativo)
            .order_by("-creado", "-pk")
            .first()
        )
        if existente is None:
            adjunto = AdjuntoFormulario.objects.create(
                formulario=formulario,
                pregunta_global=pregunta_global,
                requisito_nativo=requisito_nativo,
                archivo=archivo,
            )
        else:
            anterior = existente.archivo.name
            almacenamiento = existente.archivo.storage
            existente.archivo = archivo
            existente.save(update_fields=["archivo", "modificado"])
            if anterior and anterior != existente.archivo.name:
                transaction.on_commit(lambda: almacenamiento.delete(anterior))
            adjunto = existente
        if (
            pertenencia_del_adjunto(formulario, pregunta_global=pregunta_global, requisito_nativo=requisito_nativo)
            == ADJUNTO_YA_NO_SE_PIDE
        ):
            observar_adjunto(formulario, pregunta_global or requisito_nativo)
        return adjunto


def _requiere_gps(relevamiento):
    convocatoria = getattr(relevamiento, "convocatoria", None)
    segmento = getattr(convocatoria, "segmento", None)
    return bool(getattr(segmento, "requiere_gps", False))


def _vacio(valor):
    return valor in (None, "", [], {})


def _se_responde_en_el_alta(campo):
    """¿Este campo obligatorio tiene que venir **en el POST del alta**?

    Dos no, y las dos exclusiones son code-first:

    * **`ARCHIVO`:** su respuesta no viaja en el alta sino en los
      ``POST …/adjuntos/`` que la app manda después (``becasUploadFile`` en
      ``relevamientoService.js``). Exigirlo acá marcaría «falta» en el 100 % de
      las cargas. Lo que faltara de verdad es G1-07, que mira los adjuntos.
    * **Apoderado (`PERSONA_VINCULADA`):** el catálogo los tiene obligatorios
      desde el **Cambio 67**, que los pide a toda persona… **en el link**; ahí
      mismo está escrito que «la app de campo mantiene, por ahora, la regla de
      menores» hasta que Mobile la cambie. En el canal app la obligatoriedad la
      decide RN-22 en el serializer, y observarla acá contradiría esa decisión
      con cinco líneas en cada caso de un adulto.
    """
    if campo.get("tipo") == TipoCampo.ARCHIVO:
        return False
    return campo.get("origen") != OrigenRequisito.PERSONA_VINCULADA


def _etiqueta(definicion, clave):
    for campo in campos_de(definicion):
        if campo.get("clave") == clave:
            return campo.get("texto") or clave
    return clave


def _problemas_de_valor(campo, valor):
    """Observaciones de un valor respondido: tipo y opciones del catálogo."""
    tipo = campo.get("tipo")
    etiqueta = campo.get("texto") or campo.get("clave")
    opciones = campo.get("opciones") or []

    if tipo == TipoCampo.INT and not _es_entero(valor):
        return [f"«{etiqueta}» esperaba un número y llegó «{valor}»."]
    if tipo == TipoCampo.SELECTOR and opciones and str(valor) not in [str(o) for o in opciones]:
        return [f"«{etiqueta}» llegó con una opción que no está en el formulario: «{valor}»."]
    if tipo == TipoCampo.SELECTOR_MULTIPLE and opciones:
        elegidas = valor if isinstance(valor, (list, tuple)) else [valor]
        validas = [str(o) for o in opciones]
        fuera = [str(v) for v in elegidas if str(v) not in validas]
        if fuera:
            return [f"«{etiqueta}» llegó con opciones que no están en el formulario: {', '.join(fuera)}."]
    if (campo.get("vinculo") or "") == "genero" and campo.get("origen") == OrigenRequisito.LEGAJO:
        if str(valor).upper() not in ("F", "M"):
            return [f"«{etiqueta}» tiene que ser F o M y llegó «{valor}»."]
    return []


def _es_entero(valor):
    try:
        int(str(valor).strip())
    except (TypeError, ValueError):
        return False
    return True
