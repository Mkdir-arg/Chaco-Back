"""Avisos de la mesa de Emergencia (05 §3, RN-5.4): lo que el supervisor tiene que resolver ahora.

Son reglas de aviso del registro genérico de ``core.services.vencimientos``
(:class:`~core.services.vencimientos.ReglaAviso`), ámbito :data:`AMBITO`, como las alertas del
dispositivo (``programas.services.alertas_dispositivos``):

* **Se calculan al pedirlas y no tienen estado.** No hay tabla de avisos ni se cierran a mano:
  un aviso deja de aparecer en el momento en que su origen deja de cumplir la condición.
* **Avisar nunca bloquea.** Ningún servicio las consulta: las lee el tablero (E1).

=============================================  =========  =======================================
Regla                                          Severidad  Se resuelve
=============================================  =========  =======================================
Caso fuera de SLA                              alta       avanzando el caso (o subiendo el
                                                          objetivo en E7: es un cálculo)
Derivación rechazada sin nueva acción          alta       derivando de nuevo, o cerrando
Dispositivo sin plazas con derivación          alta       cancelando la derivación o liberando
pendiente                                                 plazas en el dispositivo
Familia «en la puerta» de un dispositivo       alta       tomando el caso y derivándolo
Derivación por vencer                          media      que el dispositivo responda, o
                                                          cancelándola
Ingreso parcial sin revisar                    media      registrando un contacto con la familia
                                                          después del ingreso (E3)
Entrega con diferencias sin revisar            media      escribiendo la observación de la mesa
                                                          en E5
=============================================  =========  =======================================

Firma de cada regla: ``pendientes(sla, ahora, usuario=None, foto=None)``. ``ahora`` llega por
parámetro (nada llama a ``now()``); ``foto`` es la de
``programas.selectors.emergencia_tablero.foto_del_tablero``, que la vista arma una vez para el
tablero y sus avisos. Con la foto, las siete reglas suman **a lo sumo 1 consulta**: la de
«en la puerta», solo si hay candidatos (lee ``situacion`` de esos casos para nombrar el
dispositivo).

**El enlace depende de quién mira.** Cada aviso lleva a la ficha del caso (E3) o al detalle
de la entrega (E5), que exigen operar o supervisar la mesa. Sin esa capacidad, el aviso
aparece igual pero **sin enlace**: avisar es de todos, resolver no.

**Acotados.** Cada regla nombra a lo sumo :data:`TOPE_POR_REGLA` casos o entregas, del más
urgente al menos, y resume el resto en un aviso «y N más» que lleva a la bandeja (E2) o al
listado de entregas (E4) filtrados.
"""

from django.urls import reverse

from core.services import vencimientos
from core.services.vencimientos import Aviso, ReglaAviso, registrar_aviso
from programas.models import CasoEmergencia, TrazaCaso
from programas.selectors import emergencia_tablero as tablero
from programas.selectors.emergencia import texto_de_minutos
from programas.services.emergencia_programa import puede_operar_la_mesa
from programas.services.ocupacion import ocupacion_de_plazas

AMBITO = "emergencia"

#: Cómo se dibuja cada severidad con la pieza `_alerta.html` (los mismos de Dispositivos).
TONOS = {"alta": "danger", "media": "warning", "baja": "info"}
ICONOS = {"alta": "triangle-exclamation", "media": "circle-exclamation", "baja": "circle-info"}

#: Cuántos casos o entregas nombra cada regla antes de resumir el resto.
TOPE_POR_REGLA = 5

#: «Derivación por vencer»: le quedan menos de estos minutos (05 §3).
POR_VENCER_MIN = 60

#: La clave de ``CasoEmergencia.situacion`` que escribe «Avisar a la mesa» (M2-6): vive en el modelo.
SITUACION_EN_LA_PUERTA = CasoEmergencia.SITUACION_EN_LA_PUERTA

Estado = CasoEmergencia.Estado
Accion = TrazaCaso.Accion


def _enlace(usuario, url, accion):
    """``(url, texto)`` solo para quien puede abrir E3/E5; al resto, el aviso sin enlace."""

    if usuario is None or not puede_operar_la_mesa(usuario):
        return "", ""
    return url, accion


def _url_caso(pk):
    return reverse("emergencia:caso_detalle", args=[pk])


def _url_entrega(pk):
    return reverse("emergencia:entrega_detalle", args=[pk])


def _y_mas(resto, usuario, *, singular, plural, url, accion):
    """El aviso que resume lo que no se nombró. Nada si no quedó resto."""

    if resto <= 0:
        return []
    enlace, texto = _enlace(usuario, url, accion)
    cuantos = f"{resto} {singular if resto == 1 else plural}"
    return [Aviso(titulo=f"Y {cuantos} más", texto="", origen=cuantos, fecha=None, enlace=enlace, accion=texto)]


def _foto(sla, ahora, foto):
    return foto if foto is not None else tablero.foto_del_tablero(sla, ahora)


# --- Caso fuera de SLA -----------------------------------------------------------------


def casos_fuera_de_sla(sla, ahora, usuario=None, foto=None):
    """El tramo en curso superó su objetivo. Del más excedido al menos. Sin consultas con foto."""

    fuera = tablero.fuera_de_sla(_foto(sla, ahora, foto))
    avisos = []
    for caso, semaforo in fuera[:TOPE_POR_REGLA]:
        enlace, accion = _enlace(usuario, _url_caso(caso.id), "Abrir el caso")
        avisos.append(
            Aviso(
                titulo=f"Caso {caso.numero} fuera de SLA",
                texto=(
                    f"{caso.familia}: el tramo «{semaforo.tramo}» lleva {texto_de_minutos(semaforo.minutos)} "
                    f"más que su objetivo de {texto_de_minutos(semaforo.objetivo_min)}."
                ),
                origen=f"Caso {caso.numero}",
                fecha=None,
                enlace=enlace,
                accion=accion,
            )
        )
    return avisos + _y_mas(
        len(fuera) - TOPE_POR_REGLA,
        usuario,
        singular="caso fuera de SLA",
        plural="casos fuera de SLA",
        url=f"{reverse('emergencia:bandeja')}?solapa=fuera_sla",
        accion="Ver en la bandeja",
    )


# --- Derivación por vencer -------------------------------------------------------------


def derivaciones_por_vencer(sla, ahora, usuario=None, foto=None):
    """``PENDIENTE`` con menos de :data:`POR_VENCER_MIN` minutos de vigencia. Sin consultas con foto.

    Una que ya pasó su vencimiento y sigue pendiente (el proceso de vencimientos todavía no
    corrió) también aparece: dice «venció hace…».
    """

    foto = _foto(sla, ahora, foto)
    limite = ahora.timestamp() + POR_VENCER_MIN * 60
    candidatas = [fila for fila in foto.pendientes if fila[5].timestamp() < limite]
    avisos = []
    for _pk, caso_id, numero, _dispositivo_id, dispositivo, vence_en in candidatas[:TOPE_POR_REGLA]:
        segundos = (vence_en - ahora).total_seconds()
        if segundos >= 0:
            cuando = f"vence en {texto_de_minutos(int(-(-segundos // 60)))}"
        else:
            cuando = f"venció hace {texto_de_minutos(int(-segundos // 60))} y sigue pendiente"
        enlace, accion = _enlace(usuario, _url_caso(caso_id), "Abrir el caso")
        avisos.append(
            Aviso(
                titulo=f"Derivación del caso {numero} por vencer",
                texto=f"{dispositivo} todavía no respondió: {cuando}.",
                origen=f"Caso {numero}",
                fecha=None,
                enlace=enlace,
                accion=accion,
            )
        )
    return avisos + _y_mas(
        len(candidatas) - TOPE_POR_REGLA,
        usuario,
        singular="derivación por vencer",
        plural="derivaciones por vencer",
        url=f"{reverse('emergencia:bandeja')}?solapa=derivados",
        accion="Ver en la bandeja",
    )


# --- Derivación rechazada sin nueva acción ---------------------------------------------


def rechazadas_sin_nueva_accion(sla, ahora, usuario=None, foto=None):
    """Casos abiertos cuya **última** traza es el rechazo de la derivación. Sin consultas con foto.

    Cualquier cosa que la mesa haga después (un contacto, derivar de nuevo, cerrar) deja otra
    traza y apaga el aviso.
    """

    casos = [caso for caso in _foto(sla, ahora, foto).abiertos if caso.ultima_accion == Accion.DERIVACION_RECHAZADA]
    avisos = []
    for caso in casos[:TOPE_POR_REGLA]:
        enlace, accion = _enlace(usuario, _url_caso(caso.id), "Derivar de nuevo")
        avisos.append(
            Aviso(
                titulo=f"Derivación del caso {caso.numero} rechazada",
                texto=f"{caso.familia}: {caso.ultimo_detalle or 'el dispositivo rechazó la derivación'}. Nadie volvió a actuar.",
                origen=f"Caso {caso.numero}",
                fecha=None,
                enlace=enlace,
                accion=accion,
            )
        )
    return avisos + _y_mas(
        len(casos) - TOPE_POR_REGLA,
        usuario,
        singular="derivación rechazada",
        plural="derivaciones rechazadas",
        url=f"{reverse('emergencia:bandeja')}?solapa=en_gestion",
        accion="Ver en la bandeja",
    )


# --- Ingreso parcial sin revisar -------------------------------------------------------


def ingresos_parciales_sin_revisar(sla, ahora, usuario=None, foto=None):
    """``ALOJADO`` con menos personas que las declaradas y sin contacto de la mesa después.

    El caso no tiene un campo de «revisado»: lo que dice que la mesa se ocupó es un
    ``ContactoCaso`` con ``momento`` desde el alojamiento (la mesa llamó a la familia por los
    que faltan). Sin consultas con foto: la foto ya trae ``contacto_posterior``.
    """

    pendientes = sorted(
        (
            caso
            for caso in _foto(sla, ahora, foto).abiertos
            if caso.estado == Estado.ALOJADO and caso.ingreso_parcial and not caso.contacto_posterior
        ),
        key=lambda caso: (caso.alojado_en, caso.id),
    )
    avisos = []
    for caso in pendientes[:TOPE_POR_REGLA]:
        enlace, accion = _enlace(usuario, _url_caso(caso.id), "Abrir el caso")
        avisos.append(
            Aviso(
                titulo=f"Ingreso parcial del caso {caso.numero} sin revisar",
                texto=(
                    f"{caso.familia}: se alojaron {caso.total_alojado} de {caso.total_declarado} personas. "
                    "Registrá el contacto con la familia por las que faltan."
                ),
                origen=f"Caso {caso.numero}",
                fecha=None,
                enlace=enlace,
                accion=accion,
            )
        )
    return avisos + _y_mas(
        len(pendientes) - TOPE_POR_REGLA,
        usuario,
        singular="ingreso parcial",
        plural="ingresos parciales",
        url=reverse("emergencia:bandeja"),
        accion="Ver en la bandeja",
    )


# --- Entrega con diferencias sin revisar -----------------------------------------------


def entregas_con_diferencias_sin_revisar(sla, ahora, usuario=None, foto=None):
    """Recibidas con diferencias sin la observación de la mesa (``tablero.q_entrega_sin_revisar``).

    Sin consultas con foto. Se apaga al escribir la observación en E5.
    """

    entregas = _foto(sla, ahora, foto).entregas_sin_revisar
    avisos = []
    for pk, numero, dispositivo, _recibida_en in entregas[:TOPE_POR_REGLA]:
        enlace, accion = _enlace(usuario, _url_entrega(pk), "Revisar la entrega")
        avisos.append(
            Aviso(
                titulo=f"Entrega {numero} con diferencias sin revisar",
                texto=f"{dispositivo} recibió algo distinto de lo enviado y la mesa todavía no dejó su observación.",
                origen=f"Entrega {numero}",
                fecha=None,
                enlace=enlace,
                accion=accion,
            )
        )
    return avisos + _y_mas(
        len(entregas) - TOPE_POR_REGLA,
        usuario,
        singular="entrega con diferencias",
        plural="entregas con diferencias",
        url=f"{reverse('emergencia:entregas')}?solapa=con_diferencias",
        accion="Ver las entregas",
    )


# --- Dispositivo sin plazas con derivación pendiente -----------------------------------


def sin_plazas_con_derivacion_pendiente(sla, ahora, usuario=None, foto=None):
    """Una derivación ``PENDIENTE`` hacia un dispositivo con 0 plazas libres.

    Derivar no reserva (las camas se reservan al aceptar), así que el dispositivo puede
    haberse llenado mientras tanto. Las plazas salen de la red de la foto; un dispositivo que
    ya no es elegible y tiene una pendiente se cuenta aparte con ``ocupacion_de_plazas`` (3
    consultas, solo en ese caso raro). Sin consultas con foto en el caso común.
    """

    foto = _foto(sla, ahora, foto)
    libres = {pk: foto.red.libres_de(pk) for pk in {fila[3] for fila in foto.pendientes}}
    afuera = [pk for pk, cantidad in libres.items() if cantidad is None]
    if afuera:
        censo = ocupacion_de_plazas(afuera, ahora)
        for pk in afuera:
            libres[pk] = max(censo.de(pk).conteo.disponibles or 0, 0)
    candidatas = [fila for fila in foto.pendientes if libres[fila[3]] == 0]
    avisos = []
    for _pk, caso_id, numero, _dispositivo_id, dispositivo, _vence_en in candidatas[:TOPE_POR_REGLA]:
        enlace, accion = _enlace(usuario, _url_caso(caso_id), "Abrir el caso")
        avisos.append(
            Aviso(
                titulo=f"{dispositivo} no tiene plazas libres",
                texto=f"Tiene pendiente la derivación del caso {numero}: no va a poder aceptarla así.",
                origen=f"Caso {numero}",
                fecha=None,
                enlace=enlace,
                accion=accion,
            )
        )
    return avisos + _y_mas(
        len(candidatas) - TOPE_POR_REGLA,
        usuario,
        singular="derivación hacia un dispositivo sin plazas",
        plural="derivaciones hacia dispositivos sin plazas",
        url=f"{reverse('emergencia:bandeja')}?solapa=derivados",
        accion="Ver en la bandeja",
    )


# --- Familia «en la puerta» de un dispositivo ------------------------------------------


def familias_en_la_puerta(sla, ahora, usuario=None, foto=None):
    """Casos ``NUEVO`` de origen ``DISPOSITIVO``: la guardia avisó que la familia espera ahí.

    **0 consultas** si en la foto no hay ninguno; 1 si hay (lee ``situacion`` solo de esos
    casos, para nombrar el dispositivo).
    """

    foto = _foto(sla, ahora, foto)
    candidatos = [
        caso
        for caso in foto.abiertos
        if caso.estado == Estado.NUEVO and caso.origen == CasoEmergencia.Origen.DISPOSITIVO
    ]
    if not candidatos:
        return []
    situaciones = dict(
        CasoEmergencia.objects.filter(pk__in=[caso.id for caso in candidatos[:TOPE_POR_REGLA]]).values_list(
            "id", "situacion"
        )
    )
    avisos = []
    for caso in candidatos[:TOPE_POR_REGLA]:
        donde = ((situaciones.get(caso.id) or {}).get(SITUACION_EN_LA_PUERTA) or {}).get(
            "dispositivo"
        ) or "un dispositivo"
        minutos = max(int((ahora - caso.creado).total_seconds() // 60), 0)
        enlace, accion = _enlace(usuario, _url_caso(caso.id), "Tomar el caso")
        avisos.append(
            Aviso(
                titulo=f"Familia en la puerta de {donde}",
                texto=f"{caso.familia} (caso {caso.numero}) espera hace {texto_de_minutos(minutos)} que la deriven.",
                origen=f"Caso {caso.numero}",
                fecha=None,
                enlace=enlace,
                accion=accion,
            )
        )
    return avisos + _y_mas(
        len(candidatos) - TOPE_POR_REGLA,
        usuario,
        singular="familia en la puerta",
        plural="familias en la puerta",
        url=f"{reverse('emergencia:bandeja')}?solapa=nuevos",
        accion="Ver en la bandeja",
    )


REGLAS = (
    (
        "emergencia.caso_fuera_de_sla",
        "Caso con el tramo en curso por encima de su objetivo.",
        "alta",
        casos_fuera_de_sla,
    ),
    (
        "emergencia.derivacion_rechazada",
        "Derivación rechazada y nadie volvió a actuar sobre el caso.",
        "alta",
        rechazadas_sin_nueva_accion,
    ),
    (
        "emergencia.sin_plazas_con_pendiente",
        "Dispositivo sin plazas libres con una derivación pendiente.",
        "alta",
        sin_plazas_con_derivacion_pendiente,
    ),
    (
        "emergencia.familia_en_la_puerta",
        "Familia que espera en la puerta de un dispositivo sin derivación.",
        "alta",
        familias_en_la_puerta,
    ),
    (
        "emergencia.derivacion_por_vencer",
        "Derivación pendiente con menos de una hora de vigencia.",
        "media",
        derivaciones_por_vencer,
    ),
    (
        "emergencia.ingreso_parcial",
        "Ingreso parcial sin contacto de la mesa con la familia.",
        "media",
        ingresos_parciales_sin_revisar,
    ),
    (
        "emergencia.entrega_con_diferencias",
        "Entrega recibida con diferencias sin observación de la mesa.",
        "media",
        entregas_con_diferencias_sin_revisar,
    ),
)


def avisos_del_tablero(sla, ahora, usuario=None, foto=None):
    """Los avisos vigentes, de la severidad más alta a la más baja, listos para `_alerta.html`.

    Cada uno: ``regla``, ``severidad``, ``tono``, ``icono``, ``titulo``, ``texto``, ``enlace`` y
    ``accion``. El template no decide la severidad ni cuenta (ficha `alerta.md`, «Lista de
    avisos con severidad»).
    """

    return [
        {
            "regla": aviso.regla,
            "severidad": aviso.severidad,
            "tono": TONOS[aviso.severidad],
            "icono": ICONOS[aviso.severidad],
            "titulo": aviso.titulo,
            "texto": aviso.texto,
            "enlace": aviso.enlace,
            "accion": aviso.accion,
        }
        for aviso in vencimientos.avisos(AMBITO, sla, ahora, usuario=usuario, foto=foto)
    ]


def registrar_reglas():
    for slug, descripcion, severidad, pendientes in REGLAS:
        registrar_aviso(
            ReglaAviso(slug=slug, ambito=AMBITO, descripcion=descripcion, severidad=severidad, pendientes=pendientes)
        )


registrar_reglas()
