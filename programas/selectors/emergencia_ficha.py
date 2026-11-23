"""La ficha del caso (E3): lo que dibuja la pantalla de un caso de la mesa de Emergencia.

Solo lectura y solo armado, como ``selectors.emergencia_mesa`` para la bandeja (E2): toma lo que
contestan ``programas.selectors.emergencia`` y lo deja en la forma que consumen el template y las
piezas. Ninguna regla del caso vive acá: quién puede qué lo decide ``programas.services.emergencia``
cuando la acción llega, y estas funciones solo adelantan en pantalla lo que ese servicio va a contestar.

Lo que la ficha comparte con la bandeja (el paso que sigue, los avisos, los formateadores y las filas de
integrantes) está en ``emergencia_mesa``; esto es solo de la ficha. ``programas.tests.test_emergencia_mesa``
fija el total de consultas de E3 con 50 dispositivos.
"""

from core.coordenadas import url_domicilio_en_google_maps
from core.selectors.geografia import PROVINCIA_OPERATIVA
from programas.models import AdjuntoCaso, CasoEmergencia, ContactoCaso, Derivacion, GrupoFamiliar, TrazaCaso
from programas.selectors import emergencia as selectores
from programas.selectors import emergencia_alojar as selectores_alojar
from programas.selectors.emergencia_mesa import (
    ESTADOS_CON_INTEGRANTES,
    ROTULO_DE_NECESIDAD,
    _fecha_hora,
    _hace,
    _personas,
    _plazas,
    avisos_de_la_mesa,
    filas_de_integrantes,
    franjas_del_grupo,
    nombre_de,
    que_falta,
)
from programas.services.emergencia import (
    NECESIDADES,
    acciones_posibles,
    estado_visible_de_caso,
    prioridad_visible,
)
from programas.services.emergencia_cierre import puede_cancelar_ingreso_por_la_mesa
from programas.services.emergencia_cierre_mesa import puede_cerrar_alojado_por_la_mesa, puede_reabrir_el_caso
from programas.services.emergencia_ingreso_comun import derivacion_vencida
from programas.services.emergencia_programa import puede_cerrar_y_reabrir, puede_supervisar_la_mesa

Estado = CasoEmergencia.Estado


#: Las acciones de «Qué hacer ahora», de la más importante a la menos: el tono es el del botón.
_TONOS_DE_ACCION = ("brand", "secondary", "tertiary")


#: Lo que pregunta el diálogo de «Reabrir caso»: lo usan el botón de «Qué hacer ahora» y el menú «Más acciones».
CONFIRMAR_REABRIR = {
    "titulo": "¿Reabrir el caso?",
    "texto": (
        "Vuelve al estado en que estaba antes de cerrarse y queda anotado en la traza. "
        "Si la familia ya tiene otro caso abierto, no se puede reabrir."
    ),
    "ok": "Sí, reabrir",
}


def _accion_de_la_ficha(clave, texto, icono, tono, modal=""):
    """Un botón del bloque; ``modal`` es la variable Alpine del modal que abre, si abre uno."""

    return {"clave": clave, "texto": texto, "icono": icono, "tono": tono, "modal": modal}


def que_hacer_ahora(caso, puede, paso):
    """El bloque «Qué hacer ahora» de la ficha: el paso que sigue y los botones que quien mira puede usar.

    **Pura, sin consultas.** No decide nada nuevo: ``paso`` es :func:`que_falta` (la misma fuente que la columna
    «Qué falta» de la bandeja) y ``puede`` son los predicados que ya calculó la ficha —``acciones_posibles``, los de
    ``emergencia_cierre`` y ``emergencia_cierre_mesa`` (Cambio 588)—, así que **no ofrece lo que el servicio va a
    rechazar ni lo que pide una capacidad que quien mira no tiene**. Cada botón es una acción que la ficha ya trae
    (el menú «Más acciones» o el panel «Derivar»): acá se destaca la que corresponde al estado.

    Devuelve ``{"paso", "nota", "ayuda", "urgente", "acciones"}``; ``acciones`` va ordenada con las de tono ``brand``
    primero y cada una trae ``clave``, ``texto``, ``icono``, ``tono`` y ``modal`` (la variable Alpine del modal que
    abre, o ``""``). Sin acciones, el bloque solo informa.
    """

    acciones = []
    if puede["puede_tomar"]:
        acciones.append(_accion_de_la_ficha("tomar", "Tomar el caso", "fa-hand", "brand"))
    if puede["puede_derivar"]:
        acciones.append(_accion_de_la_ficha("derivar", "Elegir institución", "fa-share", "brand"))
    if puede["puede_cancelar_derivacion"]:
        tono = "brand" if paso["urgente"] else "secondary"
        acciones.append(
            _accion_de_la_ficha("cancelar_derivacion", "Cancelar derivación", "fa-ban", tono, "modalCancelar")
        )
    if puede["puede_cancelar_ingreso"]:
        acciones.append(
            _accion_de_la_ficha("cancelar_ingreso", "Cancelar ingreso", "fa-ban", "secondary", "modalCancelarIngreso")
        )
    if puede["puede_reabrir"]:
        acciones.append(_accion_de_la_ficha("reabrir", "Reabrir caso", "fa-lock-open", "brand"))
    if puede["puede_actuar"]:
        # «Contactar a la familia» es el paso de un ingreso parcial (urgente en un caso alojado); en los demás
        # estados es una acción de apoyo.
        tono = "brand" if caso.estado == Estado.ALOJADO and paso["urgente"] else "secondary"
        acciones.append(_accion_de_la_ficha("contacto", "Anotar un contacto", "fa-phone", tono))
    if puede["puede_cerrar"]:
        acciones.append(_accion_de_la_ficha("cerrar", "Cerrar sin alojamiento", "fa-lock", "tertiary", "modalCerrar"))
    if puede["puede_cerrar_alojado"]:
        acciones.append(
            _accion_de_la_ficha(
                "cerrar_alojado", "Cerrar: la familia ya no está", "fa-lock", "tertiary", "modalCerrarAlojado"
            )
        )
    acciones.sort(key=lambda accion: _TONOS_DE_ACCION.index(accion["tono"]))

    ayuda = ""
    if puede["puede_tomar"]:
        # Tomar habilita derivar y cerrar solo en un caso nuevo; en los demás es hacerse cargo.
        ayuda = "Nadie tomó este caso todavía. " + (
            "Tomalo para hablar con la familia, derivarla o cerrar el caso."
            if caso.estado == Estado.NUEVO
            else "Tomalo para hacerte cargo."
        )
    elif puede["solo_lectura"] and not acciones:
        # Con botones a la vista (la supervisión puede cerrar un caso ajeno) «le toca a otro» sería falso.
        ayuda = "Le toca a quien lo tiene tomado."
    return {
        "paso": paso["texto"],
        # En un caso cerrado la ficha ya muestra el motivo en su aviso: no se repite.
        "nota": "" if not caso.abierto else paso["nota"],
        "ayuda": ayuda,
        "urgente": paso["urgente"],
        "acciones": acciones,
    }


# ---------------------------------------------------------------------------
# E3 · Ficha del caso
# ---------------------------------------------------------------------------


#: Las solapas de la ficha, en el orden de la pantalla. La primera es la que abre si la URL no pide otra.
SOLAPAS_DE_LA_FICHA = ("familia", "personas", "contactos", "fotos", "historial")


def solapa_de_la_ficha(pedida):
    """La solapa que abre la ficha: la pedida con ``?tab=`` si existe, y si no, la primera. Sin consultas."""

    return pedida if pedida in SOLAPAS_DE_LA_FICHA else SOLAPAS_DE_LA_FICHA[0]


def casos_para_ficha():
    """El queryset del caso con lo que la ficha muestra de una: grupo, responsable, localidad y gente.

    Lleva los avisos de la mesa en la misma consulta (``selectors.emergencia.con_avisos_de_la_mesa``).
    """

    return selectores.con_avisos_de_la_mesa(
        CasoEmergencia.objects.select_related("grupo__responsable", "localidad", "tomado_por", "relevado_por")
    )


def _datos_del_relevamiento(caso):
    grupo = caso.grupo
    responsable = grupo.responsable
    traslado = grupo.get_traslado_display()
    if grupo.traslado == GrupoFamiliar.Traslado.OTRA and grupo.traslado_otro:
        traslado = f"Otra: {grupo.traslado_otro}"
    edad = responsable.edad
    localidad = caso.localidad.nombre if caso.localidad_id else ""
    return [
        {"etiqueta": "Responsable", "valor": responsable.apellido_nombre},
        {"etiqueta": "DNI", "valor": responsable.dni, "formato": "dni"},
        {"etiqueta": "Edad", "valor": f"{edad} años" if edad is not None else ""},
        {"etiqueta": "Teléfono de contacto", "valor": caso.situacion.get("telefono", "")},
        {"etiqueta": "Fuerza que traslada", "valor": traslado},
        {
            "etiqueta": "Dirección",
            "valor": caso.direccion,
            # La familia vive acá; la latitud y la longitud del caso son de dónde se lo tomó.
            "url_mapa": url_domicilio_en_google_maps(caso.direccion, localidad, PROVINCIA_OPERATIVA),
        },
        {"etiqueta": "Localidad", "valor": localidad},
        {"etiqueta": "Origen", "valor": caso.get_origen_display()},
        {"etiqueta": "Relevado por", "valor": nombre_de(caso.relevado_por)},
        {"etiqueta": "Relevado", "valor": _fecha_hora(caso.relevado_en)},
        {"etiqueta": "Recibido", "valor": _fecha_hora(caso.creado)},
    ]


def _personas_del_grupo(caso):
    grupo = caso.grupo
    franjas = franjas_del_grupo(grupo)
    return {
        "franjas": franjas,
        "total_femenino": sum(fila["femenino"] or 0 for fila in franjas),
        "total_masculino": sum(fila["masculino"] or 0 for fila in franjas),
        "total": grupo.total_declarado,
        "responsable_aparte": grupo.responsable_aparte,
        "asistencia": [
            {"etiqueta": "Personas con dependencia", "valor": grupo.dependientes},
            {"etiqueta": "Mayores dependientes", "valor": grupo.mayores_dependientes},
            {"etiqueta": "Lactantes", "valor": grupo.lactantes},
        ],
        "necesidades": [ROTULO_DE_NECESIDAD[clave] for clave in NECESIDADES if caso.necesidades.get(clave)],
    }


def _fotos(caso):
    """Las fotos del caso en el contrato de ``components/_galeria_fotos.html``. **1 consulta.**

    La URL es la de ``media/``, que sirve ``core.views.media`` detrás de login y solo a la mesa.
    """

    return [
        {
            "url": adjunto.archivo.url,
            "rotulo": adjunto.get_tipo_display(),
            "alt": f"{adjunto.get_tipo_display()} del caso {caso.numero}",
            "fecha": adjunto.creado,
        }
        for adjunto in AdjuntoCaso.objects.filter(caso=caso)
    ]


def _contactos(caso):
    """Los contactos con la familia, del más nuevo al más viejo. **1 consulta.**"""

    return [
        {
            "cuando": f"{_fecha_hora(contacto.momento)} · {nombre_de(contacto.por)}",
            "titulo": f"{contacto.get_canal_display()} · {contacto.get_resultado_display()}",
            "detalle": contacto.observacion,
        }
        for contacto in ContactoCaso.objects.filter(caso=caso).select_related("por")
    ]


def _traza(caso):
    """La traza del caso en el contrato de ``components/_linea_tiempo.html``. **1 consulta.**

    La más reciente arriba. «Por supervisor» va como etiqueta (RU-13): el detalle ya lo dice,
    y así se ve sin leer la línea entera.
    """

    eventos = []
    trazas = TrazaCaso.objects.filter(caso=caso).select_related("usuario").order_by("-creado_en", "-id")
    for traza in trazas:
        cuando = _fecha_hora(traza.creado_en)
        if traza.usuario_id:
            cuando = f"{cuando} · {nombre_de(traza.usuario)}"
        evento = {"cuando": cuando, "titulo": traza.accion_legible, "detalle": traza.detalle}
        if traza.por_supervisor:
            evento.update(badge="Por supervisor", badge_tono="info")
        eventos.append(evento)
    return eventos


def _integrantes(caso):
    """La sección «Integrantes» de E3, en solo lectura, o ``None`` si el dispositivo todavía no aceptó. **1 consulta.**

    Son las filas que la guardia va confirmando (etapa 3): quién es cada persona, en qué cama
    quedó y si su ficha está completa. La mesa solo mira: no hay acción sobre ellas.
    """

    if caso.estado not in ESTADOS_CON_INTEGRANTES:
        return None
    datos = selectores_alojar.integrantes_de(caso)
    if not datos["integrantes"]:
        return None
    return {
        "filas": filas_de_integrantes(datos),
        "confirmadas": datos["confirmadas"],
        "total": datos["total_declarado"],
        "declaradas": datos["declaradas_al_relevar"],
        "crecio": caso.grupo.llegaron_mas,
    }


def _alojamiento(caso):
    """Cómo viene (o terminó) el ingreso, con el dato real de la etapa 3. Sin consultas.

    ``{"directo", "en_la_puerta", "parcial", "parcial_titulo", "diferencia", "donde"}``:
    ingreso directo, aviso «en la puerta de X», ingreso parcial con su motivo, y la sección 4
    del Formulario 1 (sector, aula, tarjeta).
    """

    diferencia = caso.diferencia
    parcial_titulo = ""
    if caso.ingreso_parcial:
        parcial_titulo = f"Ingreso parcial · {caso.total_alojado} de {caso.grupo.total_declarado} personas alojadas"
        if diferencia and diferencia.get("motivo_texto"):
            parcial_titulo = f"{parcial_titulo} · {diferencia['motivo_texto']}"
    return {
        "directo": caso.es_ingreso_directo,
        "en_la_puerta": caso.esperando_en_la_puerta,
        "parcial": caso.ingreso_parcial,
        "parcial_titulo": parcial_titulo,
        "diferencia": diferencia,
        "donde": caso.alojamiento,
    }


def _derivacion_vigente(caso, ahora):
    """La derivación vigente tal como la muestra la ficha, o ``None``. **1 consulta.**"""

    derivacion = (
        Derivacion.objects.filter(clave_vigente=caso.pk)
        .select_related("dispositivo", "edificio", "derivada_por")
        .first()
    )
    if derivacion is None:
        return None
    pendiente = derivacion.estado == Derivacion.Estado.PENDIENTE
    return {
        "id": derivacion.pk,
        "dispositivo": derivacion.dispositivo.nombre,
        "edificio": derivacion.edificio.nombre if derivacion.edificio_id else "",
        "localidad": derivacion.dispositivo.localidad,
        "plazas": _plazas(derivacion.plazas_pedidas),
        "derivada_por": nombre_de(derivacion.derivada_por),
        "derivada_en": _fecha_hora(derivacion.creado),
        "vence": _fecha_hora(derivacion.vence_en),
        "estado": "Esperando aceptación" if pendiente else derivacion.get_estado_display(),
        "pendiente": pendiente,
        # Cambio 533: pasó el plazo y el proceso diario todavía no la marcó (RN-3.3: se acepta igual).
        "vencida": derivacion_vencida(derivacion, ahora),
    }


def ficha_de_caso(caso, usuario, sla, ahora):
    """Lo que muestra E3 de un caso, sin el panel de derivar (que depende de lo que pide la URL).

    ``caso`` viene de :func:`casos_para_ficha`.

    Qué puede hacer quien mira (``es_duenio``, ``puede_*``, ``solo_lectura``) no se decide
    acá: lo contesta ``services.emergencia.acciones_posibles`` con los mismos predicados que
    los guardas del servicio vuelven a evaluar sobre la fila bloqueada (RU-12, RU-13).

    **Presupuesto: 7 a 9 consultas**: fotos, contactos, traza, las tres de los duplicados y la
    del responsable alojado; si el caso está derivado o más adelante, la derivación; y desde
    que el dispositivo lo aceptó, los integrantes.
    """

    es_supervisor = puede_supervisar_la_mesa(usuario)
    estado_texto, estado_tono = estado_visible_de_caso(caso)
    prioridad_texto, prioridad_tono = prioridad_visible(caso)

    derivacion = None
    if caso.estado in (Estado.DERIVADO, Estado.INGRESO_EN_CURSO, Estado.ALOJADO):
        derivacion = _derivacion_vigente(caso, ahora)
    acciones = acciones_posibles(
        caso, usuario, es_supervisor=es_supervisor, derivacion_pendiente=bool(derivacion and derivacion["pendiente"])
    )

    tomado = ""
    if caso.tomado_por_id and caso.abierto:
        desde = f" {_hace(caso.tomado_en, ahora)}" if caso.tomado_en else ""
        tomado = "Lo tenés tomado vos." if acciones["es_duenio"] else f"Tomado por {nombre_de(caso.tomado_por)}{desde}."

    integrantes = _integrantes(caso)
    duplicados = selectores.posibles_duplicados(caso)
    duplicado = None
    if duplicados:
        primero_pk, primero_numero = duplicados[0]
        numeros = ", ".join(numero for _pk, numero in duplicados)
        duplicado = {
            "texto": (
                f"Hay otro caso abierto con una persona de esta familia: {numeros}. "
                "Si es la misma evacuación, cerrá uno de los dos con el motivo «Otro»."
            ),
            "pk": primero_pk,
            "accion": f"Abrir el caso {primero_numero}",
        }

    if caso.estado == Estado.NUEVO:
        sin_panel = {
            "titulo": "Primero hay que tomarlo",
            "texto": "El caso se deriva cuando alguien de la mesa lo toma.",
        }
    elif not caso.abierto:
        sin_panel = {
            "titulo": "Caso cerrado",
            "texto": "Un caso cerrado no se deriva. Quien tiene permiso para reabrir casos lo puede reabrir.",
        }
    else:
        sin_panel = {
            "titulo": "Lo deriva quien lo tiene tomado",
            "texto": "Solo quien lo tiene tomado, o quien supervisa la mesa, puede elegir el dispositivo.",
        }

    personas = _personas_del_grupo(caso)
    fotos = _fotos(caso)
    contactos = _contactos(caso)
    eventos = _traza(caso)
    alojamiento = _alojamiento(caso)
    puede_cancelar_ingreso = puede_cancelar_ingreso_por_la_mesa(
        caso, es_supervisor=es_supervisor, confirmadas=integrantes["confirmadas"] if integrantes else 0
    )
    supervision = _acciones_de_supervision(caso, usuario)

    return {
        "caso": caso,
        "titulo": f"Caso {caso.numero} · Familia {caso.grupo.responsable.apellido}",
        "duplicado": duplicado,
        "sin_panel": sin_panel,
        "bajada": f"{_personas(caso.grupo.total_declarado)} · {caso.direccion}",
        "estado_texto": estado_texto,
        "estado_tono": estado_tono,
        "prioridad_texto": prioridad_texto,
        "prioridad_tono": prioridad_tono,
        "sla": selectores.estado_sla(caso, sla, ahora),
        **acciones,
        "tomado": tomado,
        "datos": _datos_del_relevamiento(caso),
        "observaciones": caso.situacion.get("observaciones", ""),
        "personas": personas,
        "fotos": fotos,
        "contactos": contactos,
        "eventos": eventos,
        # El número de cada solapa: las listas ya están traídas, no cuesta una consulta.
        "conteos": {
            "personas": personas["total"],
            "contactos": len(contactos),
            "fotos": len(fotos),
            "historial": len(eventos),
        },
        "responsable_alojado": selectores.responsable_alojado(caso, usuario),
        "derivacion": derivacion,
        "motivo_cierre": caso.get_motivo_cierre_display() if caso.motivo_cierre else "",
        "integrantes": integrantes,
        "alojamiento": alojamiento,
        "avisos": avisos_de_la_mesa(caso, sla, ahora),
        # Cambio 535: quien supervisa destraba un ingreso aceptado sin nadie confirmado.
        "puede_cancelar_ingreso": puede_cancelar_ingreso,
        # Cambio 588: la supervisión corrige la mesa (capacidad propia).
        **supervision,
        "confirmar_reabrir": CONFIRMAR_REABRIR,
        # Cambio 589: el paso que sigue y los botones que corresponden, con los mismos predicados de arriba.
        "que_hacer": que_hacer_ahora(
            caso,
            {**acciones, **supervision, "puede_cancelar_ingreso": puede_cancelar_ingreso},
            que_falta(caso, sla, ahora),
        ),
    }


def _acciones_de_supervision(caso, usuario):
    """``puede_cerrar_alojado`` y ``puede_reabrir``: las dos de ``emergencia.cerrar_reabrir``. Sin consultas de datos."""

    puede = puede_cerrar_y_reabrir(usuario)
    return {
        "puede_cerrar_alojado": puede and puede_cerrar_alojado_por_la_mesa(caso),
        "puede_reabrir": puede and puede_reabrir_el_caso(caso),
    }
