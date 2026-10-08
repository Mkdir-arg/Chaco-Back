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
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import OrigenRequisito, Relevamiento, TipoCampo
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
    observaciones = []

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
