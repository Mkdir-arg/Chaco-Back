"""El contexto del detalle de un caso de Becas, en tres bloques (RED-54).

``formulario_detalle`` eran 155 líneas con complejidad ciclomática 26, fan-out 16
y ~36 claves de contexto que consume un template de 1.214 líneas. Las Olas 1, 2,
3 y 5 tocan esa vista (SIIS-01, SEC-21, BEC-09, FE-07) y el modo de falla que
mide la ficha es siempre el mismo: una clave que deja de ponerse se renderiza
como cadena vacía y la sección **desaparece de la pantalla sin 500 y sin ningún
test en rojo**.

Lo que cambia con esto no es el comportamiento —el contexto es el mismo, clave
por clave, y lo fija ``ContextoDetalleTests``— sino dónde se lee cada cosa:

- ``contexto_identidad``  — el mapa de la toma y lo que habilita revalidar;
- ``contexto_siis``       — los dos paneles de SIIS y lo que frena la aprobación;
- ``contexto_respuestas`` — lo que respondió la persona, con o sin foto.

Son **selectores**: leen y arman: no deciden ni escriben. Lo que sí decide
—aprobar, rechazar, enviar a SIIS— sigue en ``services/``.

Una nota de performance que no es cosmética: ``ConsultasDetalleTests`` fija el
presupuesto del detalle en **15 consultas por igualdad**, no como techo. Las
listas que arman estas funciones se materializan con ``list(...)`` a propósito
—los envíos y las validaciones se recorren más de una vez— y la del caso en
espera viaja en la consulta del propio caso (CMP-N1). Agregar un ``.filter()``
suelto acá es una consulta más en la pantalla más cara de Becas, la que dio 500
por timeout contra la base de ECOM.
"""

from pathlib import Path
from urllib.parse import urlencode

from core.rbac import puede
from programas.forms import CiudadanoGeneroRevisionForm, DatosSiisForm, ForzarIdentidadForm
from programas.models import Formulario, PreguntaGlobal, RequisitoNativo, TipoCampo
from programas.services.cupo import advertencia_aprobacion, motivo_bloqueo_aprobacion
from programas.services.identidad import gran_base_activa
from programas.services.padron import padron_de
from programas.services.respuestas import respuestas_legibles

#: Capacidades que leen los tres bloques. Repetidas acá y no importadas de
#: `views/revision.py` para no invertir la dependencia (las vistas importan
#: selectores, nunca al revés).
CAP_REVISION_EDITAR = "becas.revision.editar"
CAP_REVALIDAR_RENAPER = "becas.programa.administrar"

EXTENSIONES_IMAGEN = {".avif", ".gif", ".jpeg", ".jpg", ".png", ".webp"}

SIIS_CONTROLES = (
    ("vigencia_programa", "Vigencia del programa"),
    ("edad_minima", "Edad mínima"),
    ("empleo_publico", "Empleo público"),
    ("horas_docentes", "Horas docentes"),
    ("duplicidad_becas", "Otros beneficios o becas"),
)
SIIS_VALORES_FAVORABLES = {"VIGENTE", "CUMPLE_EDAD_MINIMA", "SIN_INCOMPATIBILIDAD"}
SIIS_VALORES_INFORMATIVOS = {"NO_EVALUADO_SIN_FECHA"}
SIIS_ETIQUETAS_VALOR = {
    "VIGENTE": "Programa vigente",
    "PROGRAMA_INACTIVO": "Programa inactivo",
    "CUMPLE_EDAD_MINIMA": "Cumple la edad mínima",
    "EDAD_INSUFICIENTE": "No cumple la edad mínima",
    "NO_EVALUADO_SIN_FECHA": "No evaluado: falta la fecha de nacimiento",
    "SIN_INCOMPATIBILIDAD": "Sin incompatibilidad",
    "INCOMPATIBLE_PLANTA": "Incompatible por empleo público",
    "INCOMPATIBLE_EXCEDE_HORAS": "Incompatible por exceso de horas docentes",
    "BENEFICIO_ACTIVO_EXISTENTE": "Tiene un beneficio activo incompatible",
    "SUSPENDIDO_TEMPORAL": "Tiene una suspensión temporal vigente",
}

#: Margen en grados alrededor del punto GPS para el recuadro del mapa embebido.
MARGEN_MAPA = 0.005


def detalle_validacion_siis(validacion):
    """Los controles de compatibilidad de una ``ValidacionSIS``, ya legibles.

    Devuelve ``None`` cuando no hay validación: el template usa eso para decidir
    si el panel existe.
    """
    if validacion is None:
        return None
    respuesta = validacion.respuesta if isinstance(validacion.respuesta, dict) else {}
    valores = respuesta.get("validaciones") if isinstance(respuesta.get("validaciones"), dict) else {}
    controles = []
    for clave, etiqueta in SIIS_CONTROLES:
        valor = str(valores.get(clave) or "").strip().upper()
        if not valor:
            continue
        if valor in SIIS_VALORES_FAVORABLES:
            tono = "success"
        elif valor in SIIS_VALORES_INFORMATIVOS:
            tono = "warning"
        else:
            tono = "danger"
        controles.append(
            {
                "etiqueta": etiqueta,
                "detalle": SIIS_ETIQUETAS_VALOR.get(valor, valor.replace("_", " ").capitalize()),
                "tono": tono,
            }
        )
    registrado = respuesta.get("persona_registrada_siis")
    if registrado is True:
        situacion = "Registrado en SIIS"
    elif registrado is False:
        situacion = "Nuevo solicitante"
    else:
        situacion = "No informado"
    return {
        "programa_nombre": respuesta.get("nombre_programa") or "",
        "programa_id": respuesta.get("id_programa") or validacion.id_programa,
        "situacion": situacion,
        "controles": controles,
    }


def detalles_envio_siis(envio):
    """``[(campo, mensaje)]`` del intento: SIIS devuelve una lista por campo y
    los faltantes locales una frase suelta."""
    if envio is None:
        return []
    detalles = envio.detalles if isinstance(envio.detalles, dict) else {}
    return [
        (campo, " ".join(str(m) for m in valor) if isinstance(valor, (list, tuple)) else str(valor))
        for campo, valor in detalles.items()
    ]


def respuestas_resueltas(formulario):
    """Arma listas legibles de respuestas (pregunta/requisito → valor).

    Los campos tipo ARCHIVO no traen el archivo en ``data`` (ahí la app de
    campo solo deja un placeholder tipo ``{"pendiente_upload": true}``): el
    archivo real se resuelve contra ``AdjuntoFormulario`` (#82).
    """
    data = formulario.data or {}
    globales = data.get("globales", {}) or {}
    requisitos = data.get("requisitos", {}) or {}

    pregunta_ids = [int(k) for k in globales.keys() if str(k).isdigit()]
    preguntas = {str(p.pk): p for p in PreguntaGlobal.objects.filter(pk__in=pregunta_ids)}
    req_ids = [int(k) for k in requisitos.keys() if str(k).isdigit()]
    requisitos_map = {str(r.pk): r for r in RequisitoNativo.objects.filter(pk__in=req_ids)}

    # Una sola lectura de adjuntos: eran dos consultas sobre la misma tabla y el mismo caso.
    adjuntos = list(formulario.adjuntos.all())
    adjuntos_pregunta = {a.pregunta_global_id: a for a in adjuntos if a.pregunta_global_id}
    adjuntos_requisito = {a.requisito_nativo_id: a for a in adjuntos if a.requisito_nativo_id}

    def _fila(campo_map, adjuntos_map, k, v):
        campo = campo_map.get(str(k))
        label = campo.texto if campo else f"Campo #{k}"
        es_archivo = campo is not None and campo.tipo == TipoCampo.ARCHIVO
        adjunto = adjuntos_map.get(int(k)) if es_archivo and str(k).isdigit() else None
        es_imagen = bool(adjunto and Path(adjunto.archivo.name or "").suffix.lower() in EXTENSIONES_IMAGEN)
        return {
            "label": label,
            "valor": v,
            "es_multiple": isinstance(v, list),
            "es_archivo": es_archivo,
            "adjunto": adjunto,
            "es_imagen": es_imagen,
            "es_subsegmento": bool(getattr(campo, "subsegmento_id", None)),
        }

    globales_list = [_fila(preguntas, adjuntos_pregunta, k, v) for k, v in globales.items()]
    requisitos_list = [_fila(requisitos_map, adjuntos_requisito, k, v) for k, v in requisitos.items()]
    requisitos_segmento = [item for item in requisitos_list if not item["es_subsegmento"]]
    requisitos_subsegmento = [item for item in requisitos_list if item["es_subsegmento"]]
    return globales_list, requisitos_segmento, requisitos_subsegmento


def sin_vinculados(bloques):
    """Los campos vinculados al legajo y al apoderado ya tienen su sección en
    el detalle (identidad, contacto, apoderado): en «Respuestas» quedan solo
    las preguntas y los textos. Un grupo que se queda sin nada no se muestra."""
    if bloques is None:
        return None
    filtrados = []
    for bloque in bloques:
        items = [
            i for i in bloque["items"] if i.get("tipo") != "campo" or not i.get("origen") or i["origen"] == "pregunta"
        ]
        if items:
            filtrados.append({**bloque, "items": items})
    return filtrados


def mapa_de_la_toma(formulario):
    """El recuadro de OpenStreetMap del punto donde se tomó la carga.

    ``None`` cuando el caso no trae GPS —el link público no lo pide— y entonces
    la sección de trazabilidad no dibuja el mapa.
    """
    if formulario.gps_lat is None or formulario.gps_lng is None:
        return None
    lat = float(formulario.gps_lat)
    lng = float(formulario.gps_lng)
    margen = MARGEN_MAPA
    return {
        "latitud": formulario.gps_lat,
        "longitud": formulario.gps_lng,
        "embed_url": "https://www.openstreetmap.org/export/embed.html?"
        + urlencode(
            {
                "bbox": (f"{lng - margen:.6f},{lat - margen:.6f},{lng + margen:.6f},{lat + margen:.6f}"),
                "layer": "mapnik",
                "marker": f"{lat:.6f},{lng:.6f}",
            }
        ),
        "open_url": "https://www.openstreetmap.org/?"
        + urlencode({"mlat": f"{lat:.6f}", "mlon": f"{lng:.6f}", "zoom": 16}),
    }


def contexto_identidad(formulario, user):
    """Sección «Identidad» y «Trazabilidad de la toma».

    Las tres claves de abajo deciden **qué acción se ofrece** cuando la identidad
    no está validada: con la Gran Base apagada «Revalidar» se deshabilita y se
    ofrece validar contra el padrón de la convocatoria (Cambio 57). Que una se
    caiga del contexto no da 500: deja el botón que corresponde sin dibujar.
    """
    return {
        "genero_form": CiudadanoGeneroRevisionForm(
            initial={"genero": formulario.ciudadano.genero if formulario.ciudadano else ""}
        ),
        "mapa": mapa_de_la_toma(formulario),
        "puede_revalidar_renaper": puede(user, CAP_REVALIDAR_RENAPER),
        "gran_base_activa": gran_base_activa(),
        "convocatoria_tiene_padron": padron_de(formulario.relevamiento).exists(),
        "forzar_identidad_form": ForzarIdentidadForm(),
    }


def contexto_siis(formulario, user):
    """Los dos paneles de SIIS y lo que condiciona la aprobación.

    SIIS-01: mientras haya un envío **vigente** la pantalla no ofrece reenviar.
    «Vigente» no es «el último»: puede haber un INCOMPLETO más nuevo que el
    EN_PROCESO que de verdad ocupa el caso, así que se busca sobre la lista ya
    traída y no con otra consulta.

    El alta del beneficiario solo tiene sentido en un caso aprobado: en
    cualquier otro estado las cuatro claves del envío salen vacías y el template
    no dibuja la sección.
    """
    validaciones_sis = list(formulario.validaciones_sis.select_related("solicitado_por"))
    validacion_sis = validaciones_sis[0] if validaciones_sis else None

    puede_enviar_siis = puede(user, CAP_REVISION_EDITAR)
    envios_sis = []
    envio_siis = None
    envio_siis_activo = None
    datos_siis_form = None
    if formulario.estado == Formulario.Estado.APROBADO:
        envios_sis = list(formulario.envios_sis.select_related("solicitado_por"))
        envio_siis = envios_sis[0] if envios_sis else None
        envio_siis_activo = next((envio for envio in envios_sis if envio.vigente), None)
        if puede_enviar_siis and envio_siis_activo is None:
            correcciones = formulario.datos_siis or {}
            datos_siis_form = DatosSiisForm(initial=correcciones, actuales=correcciones)

    return {
        "puede_validar_siis": puede(user, CAP_REVISION_EDITAR),
        "validacion_sis": validacion_sis,
        "detalle_siis": detalle_validacion_siis(validacion_sis),
        "historial_validaciones_sis": [
            {"validacion": validacion, "detalle": detalle_validacion_siis(validacion)}
            for validacion in validaciones_sis
        ],
        "motivo_bloqueo_aprobacion": motivo_bloqueo_aprobacion(formulario, validacion_sis),
        # Cambio 81: un rechazo o un error de SIIS ya no bloquean; se advierten.
        "advertencia_aprobacion": advertencia_aprobacion(formulario, validacion_sis),
        "envio_siis": envio_siis,
        "envio_siis_activo": envio_siis_activo,
        "historial_envios_sis": envios_sis,
        "datos_siis_form": datos_siis_form,
        "puede_enviar_siis": puede_enviar_siis,
        "detalles_envio_siis": detalles_envio_siis(envio_siis),
    }


def contexto_respuestas(formulario):
    """Lo que respondió la persona, en uno de los dos formatos que conviven.

    Cambio 58 (#347): un caso **con foto** del formulario se lee desde la foto y
    sale en un solo listado, en el orden en que se respondió; uno anterior a la
    foto sale en las tres listas históricas por alcance. Nunca los dos a la vez:
    el que no aplica viaja vacío.
    """
    bloques = sin_vinculados(respuestas_legibles(formulario))
    if bloques is None:
        globales_list, requisitos_segmento, requisitos_subsegmento = respuestas_resueltas(formulario)
    else:
        globales_list, requisitos_segmento, requisitos_subsegmento = [], [], []
    return {
        "bloques": bloques,
        "globales_list": globales_list,
        "requisitos_segmento": requisitos_segmento,
        "requisitos_subsegmento": requisitos_subsegmento,
    }
