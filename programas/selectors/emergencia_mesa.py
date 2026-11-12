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
from programas.services.emergencia import NECESIDADES, estado_visible_de_caso, prioridad_visible
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


def _marcas_de_fila(caso, duplicados, alojado):
    """Los avisos de la fila, en texto: ``[{"texto", "tono"}]``.

    Los que dependen de las etapas siguientes («Ingreso parcial», «En la puerta de X»,
    «Rechazado por X», «Derivación vencida») se suman acá cuando esas etapas existan.
    """

    marcas = []
    if caso.origen == CasoEmergencia.Origen.DISPOSITIVO:
        marcas.append({"texto": "Ingreso directo", "tono": "info"})
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
                "puede_tomar": caso.estado == Estado.NUEVO,
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


def conteos_de_solapas(sla, ahora):
    """``{solapa: cantidad}`` de las ocho solapas. **2 consultas**: el agregado y los fuera de SLA."""

    conteo = dict(selectores.conteo_por_solapa())
    conteo[selectores.SOLAPA_FUERA_SLA] = len(selectores.ids_fuera_de_sla(sla, ahora))
    return conteo


# ---------------------------------------------------------------------------
# E3 · Ficha del caso
# ---------------------------------------------------------------------------


def casos_para_ficha():
    """El queryset del caso con lo que la ficha muestra de una: grupo, responsable, localidad y gente."""

    return CasoEmergencia.objects.select_related("grupo__responsable", "localidad", "tomado_por", "relevado_por")


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

    Qué puede hacer quien mira se **adelanta** acá para no ofrecer un botón que el servicio
    va a rechazar (RU-12, RU-13): ``puede_actuar`` es «lo tengo tomado, o superviso», y es la
    misma pregunta que ``services.emergencia`` vuelve a hacer sobre la fila bloqueada.

    **Presupuesto: 7 u 8 consultas**: fotos, contactos, traza, las tres de los duplicados, la
    del responsable alojado y, si el caso está derivado o con ingreso en curso, la derivación.
    """

    es_duenio = caso.tomado_por_id is not None and caso.tomado_por_id == usuario.pk
    es_supervisor = puede_supervisar_la_mesa(usuario)
    puede_actuar = caso.abierto and (es_duenio or es_supervisor)
    estado_texto, estado_tono = estado_visible_de_caso(caso)
    prioridad_texto, prioridad_tono = prioridad_visible(caso)

    tomado = ""
    if caso.tomado_por_id and caso.abierto:
        desde = f" {_hace(caso.tomado_en, ahora)}" if caso.tomado_en else ""
        tomado = "Lo tenés tomado vos." if es_duenio else f"Tomado por {nombre_de(caso.tomado_por)}{desde}."

    derivacion = None
    if caso.estado in (Estado.DERIVADO, Estado.INGRESO_EN_CURSO, Estado.ALOJADO):
        derivacion = _derivacion_vigente(caso)

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
        "es_duenio": es_duenio,
        "es_supervisor": es_supervisor,
        "puede_actuar": puede_actuar,
        "puede_tomar": caso.estado == Estado.NUEVO,
        "puede_soltar": puede_actuar and caso.estado == Estado.EN_GESTION,
        "puede_derivar": puede_actuar and caso.estado == Estado.EN_GESTION,
        "puede_cerrar": puede_actuar and caso.estado == Estado.EN_GESTION,
        "puede_cancelar_derivacion": puede_actuar and bool(derivacion and derivacion["pendiente"]),
        "puede_reasignar": es_supervisor and caso.abierto,
        "tomado": tomado,
        # RU-12: quien no lo tiene tomado ni supervisa lo ve en solo lectura, y se le dice por qué.
        "solo_lectura": caso.abierto and not puede_actuar and caso.estado != Estado.NUEVO,
        "datos": _datos_del_relevamiento(caso),
        "observaciones": caso.situacion.get("observaciones", ""),
        "personas": _personas_del_grupo(caso),
        "fotos": _fotos(caso),
        "contactos": _contactos(caso),
        "eventos": _traza(caso),
        "responsable_alojado": selectores.responsable_alojado(caso, usuario),
        "derivacion": derivacion,
        "motivo_cierre": caso.get_motivo_cierre_display() if caso.motivo_cierre else "",
    }
