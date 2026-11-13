"""Lo que dibujan las pantallas de la mesa de Emergencia: la bandeja (E2) y la ficha (E3).

Solo lectura y solo armado: toma lo que contestan ``programas.selectors.emergencia`` (semáforo,
bandeja, panel de derivar, marcas) y lo deja en la forma que consumen los templates y las
piezas —listas de dicts con el texto y el tono ya resueltos—. Ninguna regla del caso vive
acá: quién puede qué lo decide ``programas.services.emergencia`` cuando la acción llega, y
estas funciones solo adelantan en pantalla lo que ese servicio va a contestar.

Va en un módulo aparte del selector del caso a propósito: aquel lo comparten la API de la
app y el tablero; esto es de las dos pantallas del backoffice.

Cada función dice cuántas consultas hace. ``programas.tests.test_emergencia_mesa`` fija el
total de E2 con 500 casos abiertos y el de E3 con 50 dispositivos.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from core import rbac
from core.models import Localidad
from programas.models import AdjuntoCaso, CasoEmergencia, ContactoCaso, Derivacion, GrupoFamiliar, TrazaCaso
from programas.selectors import emergencia as selectores
from programas.selectors import emergencia_alojar as selectores_alojar
from programas.services.emergencia import (
    ESTADOS_PARA_TOMAR,
    NECESIDADES,
    acciones_posibles,
    estado_visible_de_caso,
    prioridad_visible,
)
from programas.services.emergencia_programa import (
    CAP_EMERGENCIA_OPERAR,
    CAP_SUPERVISAR,
    programa_emergencia,
    puede_supervisar_la_mesa,
)

Estado = CasoEmergencia.Estado

#: Valor del filtro «Tomado por» que significa «los que tengo yo».
OPERADOR_MIOS = "mios"

#: Cuántos dispositivos muestra el panel «Derivar» de una vez. El resto se alcanza filtrando.
TOPE_DISPOSITIVOS = 20

#: RN-1.8: la fila avisa «Relevado 14:20 · enviado 16:05» cuando difieren más que esto.
DEMORA_DE_ENVIO_VISIBLE = timedelta(minutes=5)

ROTULO_DE_NECESIDAD = {
    "embarazo": "Embarazo",
    "electrodependiente": "Electrodependiente",
    "medicacion_critica": "Medicación crítica",
    "mascotas": "Mascotas",
}

MOTIVO_SIN_PLAZAS = "Sin plazas disponibles"

#: Las claves de ``CasoEmergencia.situacion`` que escribe la etapa 3. Se repiten acá —y no se
#: importan de ``services.emergencia_alojar``— porque ese servicio importa de la mesa lo que
#: comparte con ella, y traerlo desde un selector invertiría las capas.
#: ``test_emergencia_alojar_vistas`` fija que coincidan.
SITUACION_ALOJAMIENTO = "alojamiento"
SITUACION_DIFERENCIA = "diferencia"
SITUACION_EN_LA_PUERTA = "en_la_puerta_de"

#: Desde qué estados la ficha muestra a los integrantes: cuando el dispositivo ya aceptó.
ESTADOS_CON_INTEGRANTES = (Estado.INGRESO_EN_CURSO, Estado.ALOJADO, Estado.CERRADO)

ESTADO_DE_INTEGRANTE = {
    selectores_alojar.INTEGRANTE_SIN_CONFIRMAR: ("Sin confirmar", "gray"),
    selectores_alojar.INTEGRANTE_CONFIRMADA: ("Alojada", "success"),
    selectores_alojar.INTEGRANTE_EGRESADA: ("Egresó", "gray"),
}


def nombre_de(usuario):
    """Nombre y apellido de quien trabaja en la mesa; si no los cargó, su usuario."""

    if usuario is None:
        return ""
    return usuario.get_full_name().strip() or usuario.get_username()


def _hora(momento):
    return f"{timezone.localtime(momento):%H:%M}"


def _fecha_hora(momento):
    return f"{timezone.localtime(momento):%d/%m/%Y %H:%M}"


def _hace(desde, ahora):
    """«hace 12 min», con el mismo formato de lapso que el semáforo."""

    minutos = max(int((ahora - desde).total_seconds() // 60), 0)
    return f"hace {selectores.texto_de_minutos(minutos)}"


def _personas(total):
    return "1 persona" if total == 1 else f"{total} personas"


def _plazas(cantidad):
    return "1 plaza" if cantidad == 1 else f"{cantidad} plazas"


# ---------------------------------------------------------------------------
# Quiénes trabajan en la mesa
# ---------------------------------------------------------------------------


def operadores_de_la_mesa():
    """Usuarios activos que operan o supervisan la mesa, por orden alfabético. **1 consulta.**

    Por capacidad y con alcance (RU-6, RU-7): un rol activo del programa EMERGENCIA —o uno
    global— con ``emergencia.operar`` o ``emergencia.supervisar``. Es la lista que se
    **ofrece** al reasignar y al filtrar; quién puede recibir un caso lo vuelve a decidir
    ``reasignar_caso``. Los superusuarios no figuran: pueden, pero no son personal de la mesa.
    """

    programa = programa_emergencia()
    if programa is None:
        return User.objects.none()
    codenames = [rbac.codename_de(codigo) for codigo in (CAP_EMERGENCIA_OPERAR, CAP_SUPERVISAR)]
    return (
        User.objects.filter(is_active=True)
        .filter(
            Q(groups__meta__programa=programa) | Q(groups__meta__programa__isnull=True),
            groups__meta__activo=True,
            groups__permissions__codename__in=codenames,
        )
        .distinct()
        .order_by("first_name", "last_name", "username")
    )


def localidades_con_casos():
    """Las localidades que tienen algún caso: las opciones del filtro de E2. **1 consulta.**"""

    return Localidad.objects.filter(casos_emergencia__isnull=False).distinct().order_by("nombre")


# ---------------------------------------------------------------------------
# E2 · Bandeja
# ---------------------------------------------------------------------------


def _en_la_puerta(caso):
    """El nombre del dispositivo donde la familia espera (M2-6), o ``""``.

    «Avisar a la mesa» deja el dato en ``situacion`` para siempre; el aviso vale mientras la
    familia sigue esperando: el caso está abierto y la mesa todavía no lo derivó nunca.
    """

    en_la_puerta = (caso.situacion or {}).get(SITUACION_EN_LA_PUERTA)
    if not en_la_puerta or not caso.abierto or caso.derivado_en is not None:
        return ""
    return en_la_puerta.get("dispositivo") or "un dispositivo"


def avisos_de_la_mesa(caso):
    """Los avisos que dejan las etapas 3 y 4 sobre el caso: ``[{"texto", "tono", "detalle"}]``.

    Los mismos para la fila de E2 (``texto`` y ``tono``) y para la cabecera de E3 (que suma
    ``detalle``). Sin consultas: ``caso`` viene anotado por
    ``selectors.emergencia.con_avisos_de_la_mesa`` (la bandeja y :func:`casos_para_ficha`).

    * «Rechazado por X: motivo» y «Derivación vencida · volver a derivar» mientras esa sea
      la última traza del caso: la próxima acción, cualquiera, los saca (RN-3.13, HU-2.5).
    * «Dispositivo inactivo · volver a derivar» mientras la derivación pendiente apunte a
      un dispositivo que dejó de estar activo (02 §9).
    * «Llegaron 8 sobre 7 declaradas» cuando el dispositivo agregó personas (RN-3.8).
    """

    avisos = []
    if caso.ultima_accion == TrazaCaso.Accion.DERIVACION_RECHAZADA and caso.rechazada_por:
        motivo = (caso.rechazada_motivo or "sin motivo").lower()
        avisos.append(
            {
                "texto": f"Rechazado por {caso.rechazada_por}: {motivo}",
                "tono": "danger",
                "detalle": caso.rechazada_observacion
                or "El caso volvió a gestión: derivalo a otro dispositivo o cerralo.",
            }
        )
    elif caso.ultima_accion == TrazaCaso.Accion.DERIVACION_VENCIDA:
        avisos.append(
            {
                "texto": "Derivación vencida · volver a derivar",
                "tono": "warning",
                "detalle": "El dispositivo no respondió a tiempo y el caso volvió a gestión.",
            }
        )
    if caso.derivada_a_inactivo:
        avisos.append(
            {
                "texto": "Dispositivo inactivo · volver a derivar",
                "tono": "danger",
                "detalle": "El dispositivo al que se derivó dejó de estar activo. Cancelá la derivación y derivalo a otro.",
            }
        )
    declaradas = caso.grupo.suma_de_cantidades()
    if caso.grupo.total_declarado > declaradas:
        avisos.append(
            {
                "texto": f"Llegaron {caso.grupo.total_declarado} sobre {declaradas} declaradas",
                "tono": "info",
                "detalle": "El dispositivo agregó personas que no estaban en el relevamiento.",
            }
        )
    return avisos


def _marcas_de_fila(caso, duplicados, alojado):
    """Los avisos de la fila, en texto: ``[{"texto", "tono"}]``.

    «Ingreso parcial» y «En la puerta de X» salen de lo que dejó la etapa 3 en el propio caso
    (``total_alojado`` y ``situacion``); los de :func:`avisos_de_la_mesa`, de las
    subconsultas de la bandeja. Ninguno cuesta una consulta.
    """

    marcas = []
    en_la_puerta = _en_la_puerta(caso)
    if en_la_puerta:
        # «Avisar a la mesa» (M2-6): la familia espera en ese dispositivo a que la deriven.
        marcas.append({"texto": f"En la puerta de {en_la_puerta}", "tono": "warning"})
    elif caso.origen == CasoEmergencia.Origen.DISPOSITIVO and SITUACION_EN_LA_PUERTA not in (caso.situacion or {}):
        marcas.append({"texto": "Ingreso directo", "tono": "info"})
    marcas.extend({"texto": aviso["texto"], "tono": aviso["tono"]} for aviso in avisos_de_la_mesa(caso))
    if caso.ingreso_parcial:
        marcas.append(
            {"texto": f"Ingreso parcial · {caso.total_alojado} de {caso.grupo.total_declarado}", "tono": "warning"}
        )
    if duplicados:
        numeros = ", ".join(numero for _pk, numero in duplicados)
        marcas.append({"texto": f"Posible duplicado: caso {numeros}", "tono": "warning"})
    if alojado is not None:
        marcas.append({"texto": f"Responsable alojado en {alojado.dispositivo}", "tono": "warning"})
    if caso.ubicacion_aproximada:
        marcas.append({"texto": "Ubicación aproximada", "tono": "gray"})
    if abs(caso.creado - caso.relevado_en) > DEMORA_DE_ENVIO_VISIBLE:
        marcas.append({"texto": f"Relevado {_hora(caso.relevado_en)} · enviado {_hora(caso.creado)}", "tono": "gray"})
    return marcas


def filas_de_bandeja(casos, usuario, sla, ahora):
    """Una fila por caso de la página, con estado, prioridad, semáforo y marcas ya resueltos.

    ``casos`` es la página ya evaluada (lista), con lo que trae ``selectors.emergencia.bandeja``.

    **Presupuesto: 4 consultas fijas** para toda la página: las tres de
    ``posibles_duplicados_de`` y la de ``responsables_alojados``. El semáforo es una cuenta
    en Python sobre las marcas de cada fila.
    """

    casos = list(casos)
    duplicados = selectores.posibles_duplicados_de(casos)
    alojados = selectores.responsables_alojados(casos, usuario)
    filas = []
    for caso in casos:
        responsable = caso.grupo.responsable
        estado_texto, estado_tono = estado_visible_de_caso(caso)
        prioridad_texto, prioridad_tono = prioridad_visible(caso)
        filas.append(
            {
                "caso": caso,
                "familia": f"Familia {responsable.apellido}",
                "detalle": f"{_personas(caso.grupo.total_declarado)} · Caso {caso.numero}",
                "localidad": caso.localidad.nombre if caso.localidad_id else "",
                "estado_texto": estado_texto,
                "estado_tono": estado_tono,
                "prioridad_texto": prioridad_texto,
                "prioridad_tono": prioridad_tono,
                "tomado_por": nombre_de(caso.tomado_por) if caso.tomado_por_id else "",
                "sla": selectores.estado_sla(caso, sla, ahora),
                "marcas": _marcas_de_fila(caso, duplicados.get(caso.pk), alojados.get(caso.pk)),
                "puede_tomar": caso.estado in ESTADOS_PARA_TOMAR,
            }
        )
    return filas


#: Las solapas de E2, partidas en dos filas de chips: por estado del caso (de a seis, el
#: tope de la pieza) y las dos vistas que cruzan los estados.
SOLAPAS_POR_ESTADO = (
    (selectores.SOLAPA_ABIERTOS, "Abiertos"),
    (selectores.SOLAPA_NUEVOS, "Nuevos"),
    (selectores.SOLAPA_EN_GESTION, "En gestión"),
    (selectores.SOLAPA_DERIVADOS, "Derivados"),
    (selectores.SOLAPA_INGRESO_EN_CURSO, "Ingreso en curso"),
    (selectores.SOLAPA_CERRADOS, "Cerrados"),
)
SOLAPAS_DE_ATENCION = (
    (selectores.SOLAPA_FUERA_SLA, "Fuera de SLA"),
    (selectores.SOLAPA_INGRESO_DIRECTO, "Ingreso directo"),
)


def conteos_de_solapas(sla, ahora, *, semaforos=None):
    """``{solapa: cantidad}`` de las ocho solapas.

    ``semaforos`` es lo que contestó ``selectors.emergencia.ids_por_estado_sla(sla, ahora)``:
    E2 ya lo calculó para ordenar la bandeja y los «Fuera de SLA» se cuentan de ahí. **1
    consulta** (el agregado) con él; **2** sin él, que lo calcula.
    """

    if semaforos is None:
        semaforos = selectores.ids_por_estado_sla(sla, ahora)
    conteo = dict(selectores.conteo_por_solapa())
    conteo[selectores.SOLAPA_FUERA_SLA] = sum(1 for semaforo in semaforos.values() if semaforo.fuera)
    return conteo


# ---------------------------------------------------------------------------
# E3 · Ficha del caso
# ---------------------------------------------------------------------------


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
    return [
        {"etiqueta": "Responsable", "valor": responsable.apellido_nombre},
        {"etiqueta": "DNI", "valor": responsable.dni, "formato": "dni"},
        {"etiqueta": "Edad", "valor": f"{edad} años" if edad is not None else ""},
        {"etiqueta": "Teléfono de contacto", "valor": caso.situacion.get("telefono", "")},
        {"etiqueta": "Fuerza que traslada", "valor": traslado},
        {"etiqueta": "Dirección", "valor": caso.direccion},
        {"etiqueta": "Localidad", "valor": caso.localidad.nombre if caso.localidad_id else ""},
        {"etiqueta": "Origen", "valor": caso.get_origen_display()},
        {"etiqueta": "Relevado por", "valor": nombre_de(caso.relevado_por)},
        {"etiqueta": "Relevado", "valor": _fecha_hora(caso.relevado_en)},
        {"etiqueta": "Recibido", "valor": _fecha_hora(caso.creado)},
    ]


def _personas_del_grupo(caso):
    grupo = caso.grupo
    franjas = [
        {"franja": "Menores de 16", "femenino": grupo.menores_f, "masculino": grupo.menores_m, "total": grupo.menores},
        {
            "franja": "Adultos (16 a 59)",
            "femenino": grupo.adultos_f,
            "masculino": grupo.adultos_m,
            "total": grupo.adultos,
        },
        {"franja": "Mayores (60+)", "femenino": grupo.mayores_f, "masculino": grupo.mayores_m, "total": grupo.mayores},
    ]
    return {
        "franjas": franjas,
        "total_femenino": sum(fila["femenino"] for fila in franjas),
        "total_masculino": sum(fila["masculino"] for fila in franjas),
        "total": grupo.total_declarado,
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
    filas = []
    for integrante in datos["integrantes"]:
        texto, tono = ESTADO_DE_INTEGRANTE[integrante["estado"]]
        confirmada = integrante["estado"] != selectores_alojar.INTEGRANTE_SIN_CONFIRMAR
        ficha = ""
        if confirmada:
            ficha = "Ficha completa" if integrante["ficha_completa"] else "Ficha incompleta"
        filas.append(
            {
                "n": integrante["n"],
                "persona": integrante["persona"]["nombre"] if integrante["persona"] else f"Persona {integrante['n']}",
                "dni": integrante["persona"]["dni"] if integrante["persona"] else "",
                "parentesco": integrante["parentesco"],
                "cama": integrante["plaza"]["nombre"] if integrante["plaza"] else "",
                "estado_texto": texto,
                "estado_tono": tono,
                "ficha": ficha,
                "ficha_tono": "success" if integrante["ficha_completa"] else "warning",
            }
        )
    return {
        "filas": filas,
        "confirmadas": datos["confirmadas"],
        "total": datos["total_declarado"],
        "declaradas": datos["declaradas_al_relevar"],
        "crecio": datos["total_declarado"] > datos["declaradas_al_relevar"],
    }


def _alojamiento(caso):
    """Cómo viene (o terminó) el ingreso, con el dato real de la etapa 3. Sin consultas.

    ``{"directo", "en_la_puerta", "parcial", "parcial_titulo", "diferencia", "donde"}``:
    ingreso directo, aviso «en la puerta de X», ingreso parcial con su motivo, y la sección 4
    del Formulario 1 (sector, aula, tarjeta).
    """

    situacion = caso.situacion or {}
    diferencia = situacion.get(SITUACION_DIFERENCIA)
    parcial_titulo = ""
    if caso.ingreso_parcial:
        parcial_titulo = f"Ingreso parcial · {caso.total_alojado} de {caso.grupo.total_declarado} personas alojadas"
        if diferencia and diferencia.get("motivo_texto"):
            parcial_titulo = f"{parcial_titulo} · {diferencia['motivo_texto']}"
    return {
        "directo": caso.origen == CasoEmergencia.Origen.DISPOSITIVO and SITUACION_EN_LA_PUERTA not in situacion,
        "en_la_puerta": _en_la_puerta(caso),
        "parcial": caso.ingreso_parcial,
        "parcial_titulo": parcial_titulo,
        "diferencia": diferencia,
        "donde": situacion.get(SITUACION_ALOJAMIENTO),
    }


def derivacion_pendiente_de(caso):
    """La derivación ``PENDIENTE`` del caso, o ``None``: la que la mesa puede cancelar. **1 consulta.**"""

    return (
        Derivacion.objects.filter(clave_vigente=caso.pk, estado=Derivacion.Estado.PENDIENTE)
        .select_related("dispositivo")
        .first()
    )


def _derivacion_vigente(caso):
    """La derivación vigente tal como la muestra la ficha, o ``None``. **1 consulta.**"""

    derivacion = Derivacion.objects.filter(clave_vigente=caso.pk).select_related("dispositivo", "derivada_por").first()
    if derivacion is None:
        return None
    pendiente = derivacion.estado == Derivacion.Estado.PENDIENTE
    return {
        "dispositivo": derivacion.dispositivo.nombre,
        "localidad": derivacion.dispositivo.localidad,
        "plazas": _plazas(derivacion.plazas_pedidas),
        "derivada_por": nombre_de(derivacion.derivada_por),
        "derivada_en": _fecha_hora(derivacion.creado),
        "vence": _fecha_hora(derivacion.vence_en),
        "estado": "Esperando aceptación" if pendiente else derivacion.get_estado_display(),
        "pendiente": pendiente,
    }


def panel_de_derivar(caso, usuario, *, plazas=None, texto="", localidad="", url_de_accion=None):
    """El panel «Derivar» de E3: los dispositivos como los pide ``_tarjeta_dispositivo_derivar.html``.

    ``plazas`` es lo que la mesa quiere reservar (por omisión, el total declarado; nunca
    menos de 1). ``texto`` y ``localidad`` filtran la lista por nombre y por localidad del
    dispositivo. ``url_de_accion(dispositivo_id, plazas)`` arma el destino del botón «Derivar a …»;
    un dispositivo sin plazas va con el botón bloqueado y el motivo a la vista (RN-2.5).

    Devuelve ``{"plazas", "dispositivos", "total", "mostrados", "localidades", "filas"}``:
    ``dispositivos`` son a lo sumo :data:`TOPE_DISPOSITIVOS` tarjetas, en el orden del
    selector (alcanza primero, después por distancia); ``filas`` es lo que contestó el
    selector, sin recortar, indexado por id.

    **Presupuesto: 4 consultas**, las de ``dispositivos_para_derivar``, haya 5 o 500.
    """

    pedidas = caso.grupo.total_declarado if plazas is None else max(int(plazas), 1)
    filas = selectores.dispositivos_para_derivar(caso, usuario, plazas=pedidas)
    localidades = sorted({fila["localidad"] for fila in filas if fila["localidad"]})
    texto = (texto or "").strip().casefold()
    visibles = [
        fila
        for fila in filas
        if (not texto or texto in fila["nombre"].casefold()) and (not localidad or fila["localidad"] == localidad)
    ]
    tarjetas = []
    for fila in visibles[:TOPE_DISPOSITIVOS]:
        tarjeta = {**fila, "pk": fila["id"], "accion_texto": f"Derivar a {fila['nombre']}"}
        if fila["marca"] == selectores.MARCA_SIN_PLAZAS:
            tarjeta["accion_motivo"] = MOTIVO_SIN_PLAZAS
        elif url_de_accion is not None:
            tarjeta["accion_url"] = url_de_accion(fila["id"], pedidas)
        tarjetas.append(tarjeta)
    return {
        "plazas": pedidas,
        "dispositivos": tarjetas,
        "total": len(visibles),
        "mostrados": len(tarjetas),
        "localidades": localidades,
        "filas": {fila["id"]: fila for fila in filas},
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
        derivacion = _derivacion_vigente(caso)
    acciones = acciones_posibles(
        caso, usuario, es_supervisor=es_supervisor, derivacion_pendiente=bool(derivacion and derivacion["pendiente"])
    )

    tomado = ""
    if caso.tomado_por_id and caso.abierto:
        desde = f" {_hace(caso.tomado_en, ahora)}" if caso.tomado_en else ""
        tomado = "Lo tenés tomado vos." if acciones["es_duenio"] else f"Tomado por {nombre_de(caso.tomado_por)}{desde}."

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
        sin_panel = {"titulo": "Caso cerrado", "texto": "Un caso cerrado no se deriva ni se reabre."}
    else:
        sin_panel = {
            "titulo": "Lo deriva quien lo tiene tomado",
            "texto": "Solo quien lo tiene tomado, o quien supervisa la mesa, puede elegir el dispositivo.",
        }

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
        "personas": _personas_del_grupo(caso),
        "fotos": _fotos(caso),
        "contactos": _contactos(caso),
        "eventos": _traza(caso),
        "responsable_alojado": selectores.responsable_alojado(caso, usuario),
        "derivacion": derivacion,
        "motivo_cierre": caso.get_motivo_cierre_display() if caso.motivo_cierre else "",
        "integrantes": _integrantes(caso),
        "alojamiento": _alojamiento(caso),
        "avisos": avisos_de_la_mesa(caso),
    }
