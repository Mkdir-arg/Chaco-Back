"""Lo que dibuja la bandeja de la mesa de Emergencia (E2) y lo que ella comparte con la ficha del caso (E3).

Solo lectura y solo armado: toma lo que contestan ``programas.selectors.emergencia`` (semáforo,
bandeja, panel de derivar, marcas) y lo deja en la forma que consumen los templates y las
piezas —listas de dicts con el texto y el tono ya resueltos—. Ninguna regla del caso vive
acá: quién puede qué lo decide ``programas.services.emergencia`` cuando la acción llega, y
estas funciones solo adelantan en pantalla lo que ese servicio va a contestar.

Va en un módulo aparte del selector del caso a propósito: aquel lo comparten la API de la
app y el tablero; esto es de las pantallas del backoffice. La ficha del caso (E3) vive en
``programas.selectors.emergencia_ficha``; acá quedó lo que comparte con la bandeja (``que_falta``,
los avisos, los formateadores) y el panel «Derivar».

Cada función dice cuántas consultas hace. ``programas.tests.test_emergencia_mesa`` fija el
total de E2 con 500 casos abiertos y el de E3 con 50 dispositivos.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from core import rbac
from core.models import Localidad
from programas.models import CasoEmergencia, Derivacion, TrazaCaso
from programas.selectors import emergencia as selectores
from programas.selectors import emergencia_alojar as selectores_alojar
from programas.selectors import emergencia_derivar as selectores_derivar
from programas.services.emergencia import (
    estado_visible_de_caso,
    prioridad_visible,
    puede_tomar_el_caso,
)
from programas.services.emergencia_programa import (
    CAP_EMERGENCIA_OPERAR,
    CAP_SUPERVISAR,
    programa_emergencia,
)
from programas.services.identidad import texto_comparable

Estado = CasoEmergencia.Estado

#: Valor del filtro «Tomado por» que significa «los que tengo yo».
OPERADOR_MIOS = "mios"

#: Cuántos edificios muestra el panel «Derivar» de una vez. El resto se alcanza filtrando.
TOPE_DISPOSITIVOS = 20
#: A cuántos edificios de la lista se les pide la distancia por calle a Google (se cobra por par).
TOPE_POR_CALLE = 10

#: RN-1.8: la fila avisa «Relevado 14:20 · enviado 16:05» cuando difieren más que esto.
DEMORA_DE_ENVIO_VISIBLE = timedelta(minutes=5)

ROTULO_DE_NECESIDAD = {
    "embarazo": "Embarazo",
    "electrodependiente": "Electrodependiente",
    "medicacion_critica": "Medicación crítica",
    "mascotas": "Mascotas",
}

MOTIVO_SIN_PLAZAS = "Sin plazas disponibles"

#: Desde qué estados la ficha muestra a los integrantes: cuando el dispositivo ya aceptó.
ESTADOS_CON_INTEGRANTES = (Estado.INGRESO_EN_CURSO, Estado.ALOJADO, Estado.CERRADO)

#: Cómo lee la mesa cada fila de la familia: texto y tono del badge. La guardia tiene su
#: tabla (``emergencia_llegadas.ESTADOS_DE_INTEGRANTE``): para ella la persona está
#: «Confirmada»; para la mesa, «Alojada».
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


def avisos_de_la_mesa(caso, sla, ahora):
    """Los avisos que dejan las etapas 3 y 4 sobre el caso: ``[{"texto", "tono", "detalle"}]``.

    Los mismos para la fila de E2 (``texto`` y ``tono``) y para la cabecera de E3 (que suma
    ``detalle``). Sin consultas: ``caso`` viene anotado por
    ``selectors.emergencia.con_avisos_de_la_mesa`` (la bandeja y ``emergencia_ficha.casos_para_ficha``).

    * «Rechazado por X: motivo» y «Derivación vencida · volver a derivar» mientras esa sea
      la última traza del caso: la próxima acción, cualquiera, los saca (RN-3.13, HU-2.5).
    * «Dispositivo inactivo · volver a derivar» mientras la derivación pendiente apunte a
      un dispositivo que dejó de estar activo (02 §9).
    * «Derivación vencida sin marcar» mientras la pendiente pasó su plazo y el cron no la marcó (RN-3.3).
    * «Llegaron 8 sobre 7 declaradas» cuando el dispositivo agregó personas (``GrupoFamiliar.llegaron_mas``, RN-3.8).
    * «Identidad a revisar» mientras la mesa no la revisó (``CasoEmergencia.identidad_pendiente``, Cambio 486): sale del
      JSON ``situacion`` del propio caso y del responsable ya traído, sin consultas.
    * «Aceptado sin movimiento hace N h» cuando el ingreso en curso no se movió en el plazo de E7
      (``selectors.emergencia.horas_sin_movimiento``, Cambio 535).
    """

    avisos = []
    declarada = caso.identidad_pendiente
    if declarada is not None:
        responsable = caso.grupo.responsable
        avisos.append(
            {
                "texto": "Identidad a revisar",
                "tono": "warning",
                "detalle": (
                    "Quien cargó el caso sostuvo que el DNI es de otra persona: declaró "
                    f"«{declarada.get('apellido', '')}, {declarada.get('nombre', '')}» y el legajo dice "
                    f"«{responsable.apellido}, {responsable.nombre}». Verificá quién es el responsable; "
                    "si es otra persona, corregí el legajo."
                ),
            }
        )
    if selectores.rechazo_sin_nueva_accion(caso) and caso.rechazada_por:
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
    if caso.derivacion_vencida_sin_marcar:
        avisos.append(
            {
                "texto": "Derivación vencida sin marcar",
                "tono": "warning",
                "detalle": (
                    "Pasó el plazo y el dispositivo todavía puede aceptarla: se marca como vencida en el próximo "
                    "proceso diario. Si la familia no llegó, cancelá la derivación y derivala de nuevo."
                ),
            }
        )
    horas = selectores.horas_sin_movimiento(caso, sla, ahora)
    if horas is not None:
        avisos.append(
            {
                "texto": f"Aceptado sin movimiento hace {horas} h",
                "tono": "warning",
                "detalle": (
                    "Nadie confirmó personas ni dejó novedades en el caso desde entonces. Contactá a la guardia; si "
                    "la familia no va a llegar y no hay nadie confirmado, quien supervisa la mesa puede cancelar el "
                    "ingreso y liberar las camas."
                ),
            }
        )
    if caso.grupo.llegaron_mas:
        avisos.append(
            {
                "texto": f"Llegaron {caso.grupo.total_declarado} sobre {caso.grupo.suma_de_cantidades()} declaradas",
                "tono": "info",
                "detalle": "El dispositivo agregó personas que no estaban en el relevamiento.",
            }
        )
    return avisos


def _marcas_de_fila(caso, duplicados, alojado, sla, ahora):
    """Los avisos de la fila, en texto: ``[{"texto", "tono"}]``.

    «Ingreso parcial» y «En la puerta de X» salen de lo que dejó la etapa 3 en el propio caso
    (``total_alojado`` y ``situacion``); los de :func:`avisos_de_la_mesa`, de las
    subconsultas de la bandeja. Ninguno cuesta una consulta.
    """

    marcas = []
    en_la_puerta = caso.esperando_en_la_puerta
    if en_la_puerta:
        # «Avisar a la mesa» (M2-6): la familia espera en ese dispositivo a que la deriven.
        marcas.append({"texto": f"En la puerta de {en_la_puerta}", "tono": "warning"})
    elif caso.es_ingreso_directo:
        marcas.append({"texto": "Ingreso directo", "tono": "info"})
    marcas.extend({"texto": aviso["texto"], "tono": aviso["tono"]} for aviso in avisos_de_la_mesa(caso, sla, ahora))
    if caso.ingreso_parcial:
        marcas.append(
            {"texto": f"Ingreso parcial · {caso.total_alojado} de {caso.grupo.total_declarado}", "tono": "warning"}
        )
    if duplicados:
        numeros = ", ".join(numero for _pk, numero in duplicados)
        marcas.append({"texto": f"Posible duplicado: caso {numeros}", "tono": "warning"})
    # RN-2.15 avisa que el responsable sigue alojado en otra institución antes de derivar; en un caso
    # ya alojado esa estadía es la del propio caso y la marca engaña (Cambio 533).
    if alojado is not None and caso.estado != Estado.ALOJADO:
        marcas.append({"texto": f"Responsable alojado en {alojado.dispositivo}", "tono": "warning"})
    if caso.ubicacion_aproximada:
        marcas.append({"texto": "Ubicación aproximada", "tono": "gray"})
    if abs(caso.creado - caso.relevado_en) > DEMORA_DE_ENVIO_VISIBLE:
        marcas.append({"texto": f"Relevado {_hora(caso.relevado_en)} · enviado {_hora(caso.creado)}", "tono": "gray"})
    return marcas


def que_falta(caso, sla, ahora):
    """El próximo paso de un caso para la columna «Qué falta» de la bandeja: ``{"texto", "nota", "urgente"}``.

    **Pura, sin consultas**: sale de las marcas del propio caso y de lo que anota
    ``selectors.emergencia.con_avisos_de_la_mesa`` (``derivada_a``, ``ultima_accion``, ``rechazada_*``…). No decide
    nada ni cambia ningún estado: dice qué sigue según el estado del caso (y de su derivación). ``texto`` es el
    paso; ``nota`` (puede ir vacía) dice por qué, y ``urgente`` la marca como algo que la mesa tiene que mirar.

    * Nuevo: «Tomarlo» (nota si lo devolvió la inactividad o la familia espera en la puerta).
    * En gestión: «Derivarlo a una institución»; «a otra» si la rechazó; «de nuevo» si venció.
    * Derivado: «Esperar que X lo acepte»; «Confirmar con X» si pasó el plazo; «a otra» si X está inactiva.
    * Ingreso en curso: «Esperar que X confirme a las personas»; «Contactar a X» si no se movió en horas.
    * Alojado: «Nada: se cierra cuando egrese la familia»; «Contactar a la familia» si el ingreso fue parcial.
    * Cerrado: «Nada: el caso está cerrado» y el motivo.
    """

    estado = caso.estado
    institucion = caso.derivada_a or "la institución"
    texto, nota, urgente = "", "", False
    if estado == Estado.NUEVO:
        texto = "Tomarlo"
        if caso.ultima_accion == TrazaCaso.Accion.DEVUELTO_POR_INACTIVIDAD:
            nota, urgente = "Volvió a la bandeja: nadie lo movió a tiempo", True
        elif caso.esperando_en_la_puerta:
            nota, urgente = f"La familia espera en la puerta de {caso.esperando_en_la_puerta}", True
    elif estado == Estado.EN_GESTION:
        if selectores.rechazo_sin_nueva_accion(caso) and caso.rechazada_por:
            texto = "Derivarlo a otra institución"
            motivo = (caso.rechazada_motivo or "sin motivo").lower()
            nota, urgente = f"{caso.rechazada_por} no lo aceptó: {motivo}", True
        elif caso.ultima_accion == TrazaCaso.Accion.DERIVACION_VENCIDA:
            texto = "Derivarlo de nuevo"
            nota, urgente = "La institución no respondió a tiempo", True
        else:
            texto = "Derivarlo a una institución"
            if caso.esperando_en_la_puerta:
                nota, urgente = f"La familia espera en la puerta de {caso.esperando_en_la_puerta}", True
    elif estado == Estado.DERIVADO:
        if caso.derivada_a_inactivo:
            texto = "Cancelar la derivación y derivarlo a otra institución"
            nota, urgente = f"{institucion} dejó de estar activa", True
        elif caso.derivacion_vencida_sin_marcar:
            texto = f"Confirmar con {institucion} si lo acepta"
            nota, urgente = "Pasó el plazo para responder", True
        else:
            texto = f"Esperar que {institucion} lo acepte"
    elif estado == Estado.INGRESO_EN_CURSO:
        horas = selectores.horas_sin_movimiento(caso, sla, ahora)
        if horas is not None:
            texto = f"Contactar a {institucion}"
            nota, urgente = f"Aceptado y sin movimiento hace {horas} h", True
        else:
            texto = f"Esperar que {institucion} confirme a las personas"
            if caso.es_ingreso_directo:
                nota = "Ingresó directo, sin pasar por la mesa"
    elif estado == Estado.ALOJADO:
        if caso.ingreso_parcial:
            faltan = caso.grupo.total_declarado - caso.total_alojado
            texto = "Contactar a la familia"
            nota, urgente = (
                f"{'Falta' if faltan == 1 else 'Faltan'} {_personas(faltan)} de las {caso.grupo.total_declarado} declaradas",
                True,
            )
        else:
            texto = "Nada: se cierra cuando egrese la familia"
    else:
        texto = "Nada: el caso está cerrado"
        nota = caso.get_motivo_cierre_display() if caso.motivo_cierre else ""
    return {"texto": texto, "nota": nota, "urgente": urgente}


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
                "que_falta": que_falta(caso, sla, ahora),
                "marcas": _marcas_de_fila(caso, duplicados.get(caso.pk), alojados.get(caso.pk), sla, ahora),
                "puede_tomar": puede_tomar_el_caso(caso),
            }
        )
    return filas


#: Los seis chips de la bandeja, en una sola fila y en el orden de la pantalla (Cambio 580). «Sin tomar» y
#: «Esperando a la institución» se cruzan a propósito: un ingreso directo sin dueño está en las dos.
SOLAPAS_DE_LA_BANDEJA = (
    (selectores.SOLAPA_MIS_CASOS, "Mis casos"),
    (selectores.SOLAPA_SIN_TOMAR, "Sin tomar"),
    (selectores.SOLAPA_ESPERANDO_INSTITUCION, "Esperando a la institución"),
    (selectores.SOLAPA_ALOJADOS, "Alojados"),
    (selectores.SOLAPA_ABIERTOS, "Todos los abiertos"),
    (selectores.SOLAPA_CERRADOS, "Cerrados"),
)


def conteos_de_solapas(sla, ahora, *, semaforos=None, usuario_id=None):
    """``{solapa: cantidad}`` de todas las solapas (``usuario_id`` es quien mira, para «Mis casos»).

    ``semaforos`` es lo que contestó ``selectors.emergencia.ids_por_estado_sla(sla, ahora)``:
    E2 ya lo calculó para ordenar la bandeja y los «Fuera de SLA» se cuentan de ahí. **1
    consulta** (el agregado) con él; **2** sin él, que lo calcula.
    """

    if semaforos is None:
        semaforos = selectores.ids_por_estado_sla(sla, ahora)
    conteo = dict(selectores.conteo_por_solapa(usuario_id))
    conteo[selectores.SOLAPA_FUERA_SLA] = sum(1 for semaforo in semaforos.values() if semaforo.fuera)
    return conteo


def franjas_del_grupo(grupo):
    """Las filas de «Personas que ingresan juntas», con la del responsable si va aparte.

    La del responsable no tiene sexo (``None``): el Formulario 1 no lo pide para él.
    """

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
    if grupo.responsable_aparte:
        franjas.append({"franja": "Responsable", "femenino": None, "masculino": None, "total": 1})
    return franjas


def _rotulo_de_integrante(integrante):
    """«Pérez, Juan» confirmada; la persona 1 sin confirmar, con el nombre del responsable; si no, «Persona N»."""

    if integrante["persona"]:
        return integrante["persona"]["nombre"]
    if integrante.get("responsable"):
        return f"{integrante['responsable']['nombre']} (responsable)"
    return f"Persona {integrante['n']}"


def filas_de_integrantes(datos, url_de=None, estados=ESTADO_DE_INTEGRANTE):
    """Las filas de la familia desde lo que contesta ``integrantes_de``, con texto y tono. Sin consultas.

    La comparten la ficha de la mesa (E3, en solo lectura) y la guardia (M2-3), cada una con
    su tabla de ``estados``. ``url_de(n)`` arma el destino de la ficha de la persona; sin él,
    la fila no lleva ``url``.
    """

    filas = []
    for integrante in datos["integrantes"]:
        texto, tono = estados[integrante["estado"]]
        confirmada = integrante["estado"] != selectores_alojar.INTEGRANTE_SIN_CONFIRMAR
        filas.append(
            {
                **integrante,
                "rotulo": _rotulo_de_integrante(integrante),
                "estado_texto": texto,
                "estado_tono": tono,
                "confirmada": confirmada,
                "ficha_texto": ("Ficha completa" if integrante["ficha_completa"] else "Ficha incompleta")
                if confirmada
                else "",
                "ficha_tono": "success" if integrante["ficha_completa"] else "warning",
                "accion": ("Completar ficha" if not integrante["ficha_completa"] else "Ver ficha")
                if confirmada
                else "Confirmar",
                "url": url_de(integrante["n"]) if url_de is not None else "",
            }
        )
    return filas


def derivacion_pendiente_de(caso):
    """La derivación ``PENDIENTE`` del caso, o ``None``: la que la mesa puede cancelar. **1 consulta.**"""

    return (
        Derivacion.objects.filter(clave_vigente=caso.pk, estado=Derivacion.Estado.PENDIENTE)
        .select_related("dispositivo")
        .first()
    )


def panel_de_derivar(
    caso, usuario, *, plazas=None, texto="", localidad="", grupo=None, url_de_grupo=None, url_de_accion=None
):
    """El panel «Derivar» de E3 por edificio (Cambio 520), como lo pide ``_tarjeta_dispositivo_derivar.html``.

    Dos pasos en la misma pantalla: la lista de **edificios** con sus camas libres y su distancia a la
    familia; con ``grupo`` (la clave de un edificio de la lista), las **instituciones** de ese edificio con
    sus camas ahí, cada una con su botón «Derivar a …».

    ``plazas`` es lo que la mesa quiere pedir (por omisión, el total declarado; nunca menos de 1).
    ``texto`` busca en el nombre y el domicilio del edificio y en el nombre de sus instituciones;
    ``localidad`` filtra por la del edificio. ``url_de_grupo(clave)`` arma el botón de un edificio y
    ``url_de_accion(clave, dispositivo_id, plazas)`` el de una institución. Un edificio o una institución
    sin camas va con el botón bloqueado y el motivo a la vista (RN-2.5).

    Devuelve ``{"plazas", "edificios", "total", "mostrados", "localidades", "grupo", "grupos"}``:
    ``edificios`` son a lo sumo :data:`TOPE_DISPOSITIVOS` tarjetas, en el orden del selector (alcanza
    primero, después por distancia); ``grupo`` es el edificio elegido con sus tarjetas de institución, o
    ``None``; ``grupos`` es todo lo que contestó el selector, sin recortar, por clave.

    **Presupuesto: 6 consultas**, las de ``edificios_para_derivar``, haya 5 edificios o 500.
    """

    pedidas = caso.grupo.total_declarado if plazas is None else max(int(plazas), 1)
    todos = selectores_derivar.edificios_para_derivar(caso, usuario, plazas=pedidas)
    localidades = sorted({fila["localidad"] for fila in todos if fila["localidad"]})
    texto = texto_comparable(texto)
    visibles = [fila for fila in todos if _coincide(fila, texto) and (not localidad or fila["localidad"] == localidad)]
    tarjetas = []
    for fila in visibles[:TOPE_DISPOSITIVOS]:
        cuantas = len(fila["instituciones"])
        tarjeta = {
            **fila,
            "pk": fila["clave"],
            "localidad": fila["ubicacion"],
            "accion_texto": f"Ver {'la institución' if cuantas == 1 else f'las {cuantas} instituciones'}",
        }
        if fila["marca"] == selectores.MARCA_SIN_PLAZAS:
            tarjeta["accion_motivo"] = MOTIVO_SIN_PLAZAS
        elif url_de_grupo is not None:
            tarjeta["accion_url"] = url_de_grupo(fila["clave"])
        tarjetas.append(tarjeta)

    grupos = {fila["clave"]: fila for fila in todos}
    elegido = grupos.get(grupo) if grupo else None
    if elegido is not None:
        instituciones = []
        for institucion in elegido["instituciones"]:
            tarjeta = {
                **institucion,
                "pk": f"{elegido['clave']}-{institucion['id']}",
                "localidad": elegido["nombre"],
                "distancia_texto": elegido["distancia_texto"],
                "accion_texto": f"Derivar a {institucion['nombre']}",
            }
            if institucion["marca"] == selectores.MARCA_SIN_PLAZAS:
                tarjeta["accion_motivo"] = MOTIVO_SIN_PLAZAS
            elif url_de_accion is not None:
                tarjeta["accion_url"] = url_de_accion(elegido["clave"], institucion["id"], pedidas)
            instituciones.append(tarjeta)
        elegido = {**elegido, "tarjetas": instituciones}
    return {
        "plazas": pedidas,
        "edificios": tarjetas,
        "distancias": _distancias_por_calle(caso, tarjetas) if elegido is None else None,
        "total": len(visibles),
        "mostrados": len(tarjetas),
        "localidades": localidades,
        "grupo": elegido,
        "grupos": grupos,
    }


def _distancias_por_calle(caso, tarjetas):
    """Lo que necesita ``nodo-derivar-distancias.js`` para pedir la distancia por calle (Cambio 520, fase 2).

    ``origen`` es el domicilio ya ubicado o ``None`` (el JS lo ubica con ``direccion`` y lo guarda);
    ``destinos``, los primeros :data:`TOPE_POR_CALLE` edificios de la lista con punto o dirección
    (``{"clave", "lat", "lng"}`` o ``{"clave", "direccion"}``), sin los de ubicación reservada. ``None`` si no hay a quién medir. Sin consultas.
    """

    destinos = [
        {"clave": tarjeta["clave"], **tarjeta["destino"]} for tarjeta in tarjetas if tarjeta["destino"] is not None
    ][:TOPE_POR_CALLE]
    if not destinos:
        return None
    ubicado = selectores_derivar.domicilio_ubicado(caso)
    localidad = caso.localidad.nombre if caso.localidad_id else ""
    direccion = selectores_derivar.direccion_para_google(caso.direccion, localidad)
    return {
        "origen": {"lat": float(ubicado.latitud), "lng": float(ubicado.longitud)} if ubicado else None,
        "direccion": direccion,
        "destinos": destinos,
    }


def _coincide(fila, texto):
    if not texto:
        return True
    nombres = [fila["nombre"], fila["ubicacion"], *(institucion["nombre"] for institucion in fila["instituciones"])]
    # Sin acentos ni mayúsculas, como el resto de las búsquedas por nombre (Cambio 533).
    return any(texto in texto_comparable(nombre) for nombre in nombres)
