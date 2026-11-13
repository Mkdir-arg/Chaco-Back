"""Lo que dibujan las pantallas E6 del backoffice: «Emergencia · Llegadas» de un dispositivo.

Solo lectura y solo armado, como ``selectors.emergencia_mesa`` para la mesa: toma lo que
contestan ``selectors.emergencia_alojar`` (camas, integrantes, llegadas) y el servicio
(``buscar_por_dni``) y lo deja en la forma que consumen los templates y las piezas —dicts
con el texto y el tono ya resueltos—. Ninguna regla de la etapa vive acá.

Va aparte de ``emergencia_alojar`` a propósito: aquel lo comparte la API de la app y
devuelve datos planos; esto es del backoffice.

Quien llama es la vista, que ya exigió ``dispositivo.admitir`` con alcance.
"""

from django.utils import timezone

from programas.models import AdjuntoCaso
from programas.selectors import emergencia_alojar as alojar
from programas.selectors.emergencia_mesa import ROTULO_DE_NECESIDAD, _personas, nombre_de
from programas.selectors.emergencia_mesa import filas_de_integrantes as filas_de_integrantes_de_la_mesa
from programas.services.emergencia import NECESIDADES, prioridad_visible

#: Los tres pasos del guion de la guardia (03 §3). El estado del recorrido es el del caso,
#: no la sesión: cada paso es una pantalla que se abre por su URL.
PASOS = ("Buscar a la familia", "Integrantes y camas", "Familia alojada")


def _dia_hora(momento):
    return f"{timezone.localtime(momento):%d/%m %H:%M}"


def pasos(paso_actual, url_llegadas, url_integrantes=None):
    """El contexto de ``components/_stepper.html``: ``{"pasos", "paso_actual"}``."""

    urls = (url_llegadas, url_integrantes, None)
    return {
        "pasos": [{"etiqueta": etiqueta, "url": url} for etiqueta, url in zip(PASOS, urls, strict=True)],
        "paso_actual": paso_actual,
    }


def tarjeta_de_derivacion(derivacion, ahora):
    """La tarjeta de M2-2: la familia, cuántos son, la prioridad, quién derivó y cuándo vence.

    ``derivacion`` trae ``caso.grupo.responsable`` y ``derivada_por`` (así la devuelven
    ``buscar_por_dni`` y ``llegadas_del_dispositivo``). Sin consultas.
    """

    caso = derivacion.caso
    grupo = caso.grupo
    prioridad_texto, prioridad_tono = prioridad_visible(caso)
    pendiente = derivacion.estado == derivacion.Estado.PENDIENTE
    vencida = pendiente and derivacion.vence_en < ahora
    return {
        "derivacion": derivacion,
        "caso": caso,
        "pendiente": pendiente,
        "familia": f"Familia {grupo.responsable.apellido}",
        "responsable": grupo.responsable.apellido_nombre,
        "dni": grupo.responsable.dni,
        "personas": _personas(grupo.total_declarado),
        "plazas": derivacion.plazas_pedidas,
        "prioridad_texto": prioridad_texto,
        "prioridad_tono": prioridad_tono,
        "derivada_por": nombre_de(derivacion.derivada_por),
        "derivada_en": _dia_hora(derivacion.creado),
        "vence": _dia_hora(derivacion.vence_en),
        "vencida": vencida,
        "necesidades": [ROTULO_DE_NECESIDAD[clave] for clave in NECESIDADES if caso.necesidades.get(clave)],
        "franjas": [
            {"franja": "Menores de 16", "femenino": grupo.menores_f, "masculino": grupo.menores_m},
            {"franja": "Adultos (16 a 59)", "femenino": grupo.adultos_f, "masculino": grupo.adultos_m},
            {"franja": "Mayores (60+)", "femenino": grupo.mayores_f, "masculino": grupo.mayores_m},
        ],
        "asistencia": [
            {"etiqueta": "Personas con dependencia", "valor": grupo.dependientes},
            {"etiqueta": "Mayores dependientes", "valor": grupo.mayores_dependientes},
            {"etiqueta": "Lactantes", "valor": grupo.lactantes},
        ],
        "telefono": caso.situacion.get("telefono", ""),
        "observaciones": caso.situacion.get("observaciones", ""),
    }


def filas_de_llegadas(derivaciones, ahora, url_de):
    """Una fila por derivación de la lista de llegadas. ``url_de(derivacion)`` arma el destino. Sin consultas."""

    filas = []
    for derivacion in derivaciones:
        caso = derivacion.caso
        grupo = caso.grupo
        prioridad_texto, prioridad_tono = prioridad_visible(caso)
        pendiente = derivacion.estado == derivacion.Estado.PENDIENTE
        filas.append(
            {
                "familia": f"Familia {grupo.responsable.apellido}",
                "detalle": f"{_personas(grupo.total_declarado)} · Caso {caso.numero}",
                "prioridad_texto": prioridad_texto,
                "prioridad_tono": prioridad_tono,
                "cuando": (
                    f"Vence {_dia_hora(derivacion.vence_en)}"
                    if pendiente
                    else f"Aceptada {_dia_hora(derivacion.respondida_en or derivacion.creado)}"
                ),
                "vencida": pendiente and derivacion.vence_en < ahora,
                "confirmadas": derivacion.confirmadas,
                "total": grupo.total_declarado,
                "url": url_de(derivacion),
            }
        )
    return filas


#: Cómo lee la guardia cada fila de la familia: texto y tono del badge.
ESTADOS_DE_INTEGRANTE = {
    alojar.INTEGRANTE_SIN_CONFIRMAR: ("Sin confirmar", "gray"),
    alojar.INTEGRANTE_CONFIRMADA: ("Confirmada", "success"),
    alojar.INTEGRANTE_EGRESADA: ("Egresó", "gray"),
}


def filas_de_integrantes(datos, url_de=None):
    """Las filas de M2-3 desde lo que contesta ``integrantes_de``: las de la mesa, con la tabla de la guardia."""

    return filas_de_integrantes_de_la_mesa(datos, url_de, estados=ESTADOS_DE_INTEGRANTE)


def mapa_para_elegir(sectores, elegida, url_de):
    """Los sectores de ``plazas_para_caso`` en el contrato de ``components/_mapa_plazas.html``.

    Modo emergencia de la pieza, **sin tocarla** (ficha ``mapa_plazas.md``): la cama guardada
    para la familia lleva el texto «Reservada para esta familia», tono ``warning`` y es
    seleccionable; la reservada para otros, la ocupada y la fuera de servicio no llevan
    ``url``. ``url_de(plaza_id)`` arma el enlace de la que se puede elegir; a lo sumo una
    lleva ``seleccionada``.
    """

    armados = []
    for sector in sectores:
        plazas = []
        for plaza in sector["plazas"]:
            celda = {
                "codigo": plaza["codigo"],
                "estado": plaza["texto"],
                "tono": plaza["tono"],
                "detalle": plaza["detalle"],
                "seleccionada": plaza["id"] == elegida,
            }
            if plaza["elegible"]:
                celda["url"] = url_de(plaza["id"])
            plazas.append(celda)
        armados.append({**sector, "plazas": plazas})
    return armados


def cama_sugerida(sectores):
    """La primera cama guardada para la familia, en el orden del mapa; ``None`` si no queda ninguna."""

    for sector in sectores:
        for plaza in sector["plazas"]:
            if plaza["estado"] == alojar.PLAZA_RESERVADA_FAMILIA:
                return plaza["id"]
    return None


def cama_por_id(sectores, plaza_id):
    """El dict de la cama ``plaza_id`` dentro de lo que contestó ``plazas_para_caso``, o ``None``."""

    for sector in sectores:
        for plaza in sector["plazas"]:
            if plaza["id"] == plaza_id:
                return plaza
    return None


def fotos_del_caso(caso):
    """Las fotos del relevamiento en el contrato de ``components/_galeria_fotos.html``. **1 consulta.**

    La URL es la de ``media/``: ``core.views.media`` se la sirve a la guardia del dispositivo
    de la derivación vigente, y a nadie más fuera de la mesa (RU-17).
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
