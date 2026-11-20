"""Lo que se dibuja en `/mapa/`: un punto por cosa ubicada, armado para `components/_mapa_capas.html`.

Cada capa sale de la regla de lectura de su propio módulo, no de `mapa.ver`: el mapa no abre nada que el usuario
no pudiera ver por otro lado.

- Dispositivos: `dispositivos_visibles`, sin los de ubicación reservada (RN-009-13), que solo se cuentan.
- Edificios: `edificios_visibles` (los vigentes).
- Casos de Emergencia: solo quien opera o supervisa la mesa, y solo los abiertos. Viaja el número, la prioridad,
  el estado y cuándo se relevó: nada de la persona (nombre, documento, dirección).
- Puntos: todos, para quien tiene `mapa.ver`. Se mueven y se borran con `mapa.editar`.

Las coordenadas viajan como float; un registro sin las dos no se dibuja y se cuenta aparte.
"""

from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince

from core import rbac
from mapa.models import Punto
from programas.models import CasoEmergencia
from programas.selectors.edificios import edificios_visibles
from programas.services.dispositivos import TONOS_ESTADO, dispositivos_visibles
from programas.services.emergencia_programa import puede_operar_la_mesa
from programas.services.ubicacion_reservada import q_sin_ubicacion_reservada

CAPA_DISPOSITIVOS = "dispositivo"
CAPA_EDIFICIOS = "edificio"
CAPA_EMERGENCIA = "emergencia"
CAPA_PUNTOS = "punto"

CAP_VER = "mapa.ver"
CAP_EDITAR = "mapa.editar"

ICONOS_CATEGORIA = {
    Punto.Categoria.SEDE: "fa-landmark",
    Punto.Categoria.EQUIPO: "fa-toolbox",
    Punto.Categoria.VEHICULO: "fa-truck",
    Punto.Categoria.OTRO: "fa-location-dot",
}
TONOS_PRIORIDAD = {
    CasoEmergencia.Prioridad.ALTA: "danger",
    CasoEmergencia.Prioridad.MEDIA: "warning",
    CasoEmergencia.Prioridad.BAJA: "info",
}

_CON_COORDENADAS = {"latitud__isnull": False, "longitud__isnull": False}


def puede_editar(user):
    return rbac.puede(user, CAP_EDITAR)


def _coordenadas(obj):
    return float(obj.latitud), float(obj.longitud)


def punto_de_dispositivo(dispositivo):
    lat, lng = _coordenadas(dispositivo)
    return {
        "id": f"dispositivo-{dispositivo.pk}",
        "capa": CAPA_DISPOSITIVOS,
        "lat": lat,
        "lng": lng,
        "etiqueta": dispositivo.nombre,
        "icono": "fa-house-user",
        "tono": "brand",
        "titulo": dispositivo.nombre,
        "subtitulo": dispositivo.tipo.nombre if dispositivo.tipo_id else "",
        "estado": {"texto": dispositivo.get_estado_display(), "tono": TONOS_ESTADO.get(dispositivo.estado, "gray")},
        "datos": [
            ["Plazas", str(dispositivo.camas_totales)],
            ["Domicilio", dispositivo.domicilio or "—"],
            ["Localidad", dispositivo.localidad or "—"],
        ],
        "url": reverse("dispositivos:detalle", args=[dispositivo.pk]),
        "url_texto": "Abrir legajo",
    }


def punto_de_edificio(edificio):
    lat, lng = _coordenadas(edificio)
    domicilio = " ".join(parte for parte in (edificio.calle, edificio.numero) if parte)
    return {
        "id": f"edificio-{edificio.pk}",
        "capa": CAPA_EDIFICIOS,
        "lat": lat,
        "lng": lng,
        "etiqueta": edificio.nombre,
        "icono": "fa-building",
        "tono": "success",
        "titulo": edificio.nombre,
        "subtitulo": edificio.codigo,
        "datos": [["Domicilio", domicilio or "—"], ["Localidad", edificio.localidad or "—"]],
        "url": reverse("dispositivos:edificio_detalle", args=[edificio.pk]),
        "url_texto": "Ver edificio",
    }


def punto_de_caso(caso, ahora):
    lat, lng = _coordenadas(caso)
    return {
        "id": f"caso-{caso.pk}",
        "capa": CAPA_EMERGENCIA,
        "lat": lat,
        "lng": lng,
        "etiqueta": caso.numero,
        "icono": "fa-triangle-exclamation",
        "tono": TONOS_PRIORIDAD.get(caso.prioridad, "gray"),
        "titulo": f"Caso {caso.numero}",
        "subtitulo": f"Prioridad {caso.get_prioridad_display().lower()}",
        "estado": {"texto": caso.get_estado_display(), "tono": TONOS_PRIORIDAD.get(caso.prioridad, "gray")},
        "datos": [["Relevado", f"hace {timesince(caso.relevado_en, ahora)}"]],
        "url": reverse("emergencia:caso_detalle", args=[caso.pk]),
        "url_texto": "Abrir ficha",
    }


def punto_de_punto(punto, *, editable):
    lat, lng = _coordenadas(punto)
    datos = []
    if punto.cargado_por_id:
        datos.append(["Cargado por", punto.cargado_por.get_full_name() or punto.cargado_por.get_username()])
    datos.append(["Actualizado", timezone.localtime(punto.modificado).strftime("%d/%m/%Y %H:%M")])
    resultado = {
        "id": f"punto-{punto.pk}",
        "capa": CAPA_PUNTOS,
        "grupo": punto.categoria,
        "lat": lat,
        "lng": lng,
        "etiqueta": punto.nombre,
        "icono": ICONOS_CATEGORIA.get(punto.categoria, "fa-location-dot"),
        "tono": "navy",
        "titulo": punto.nombre,
        "subtitulo": " · ".join(parte for parte in (punto.get_categoria_display(), punto.descripcion) if parte),
        "datos": datos,
    }
    if editable:
        resultado["movible"] = True
        resultado["acciones"] = [{"accion": "eliminar", "texto": "Eliminar", "icono": "fa-trash-can", "tono": "danger"}]
    return resultado


def capas_del_mapa(user):
    """Las capas que ``user`` puede ver, con sus puntos y lo que quedó afuera.

    Devuelve ``{"capas": [...], "puntos": [...], "editable": bool}``. Cada capa trae ``id``, ``nombre``,
    ``icono``, ``tono``, ``nota``, ``total`` y, si corresponde, ``fuera`` (texto de lo que no se dibuja).
    """

    capas, puntos = [], []
    editable = puede_editar(user)

    dispositivos = dispositivos_visibles(user)
    if dispositivos.exists():
        publicables = dispositivos.filter(q_sin_ubicacion_reservada())
        ubicados = list(publicables.filter(**_CON_COORDENADAS).select_related("tipo").order_by("nombre", "pk"))
        sin_ubicacion = publicables.exclude(**_CON_COORDENADAS).count()
        reservados = dispositivos.exclude(q_sin_ubicacion_reservada()).count()
        puntos += [punto_de_dispositivo(d) for d in ubicados]
        fuera = []
        if sin_ubicacion:
            fuera.append(f"{sin_ubicacion} sin ubicación")
        if reservados:
            fuera.append(f"{reservados} de ubicación reservada")
        capas.append(
            _capa(CAPA_DISPOSITIVOS, "Dispositivos", "fa-house-user", "brand", "Los que tenés a cargo", ubicados, fuera)
        )

    edificios = edificios_visibles(user)
    if edificios.exists():
        ubicados = list(edificios.filter(**_CON_COORDENADAS).order_by("nombre", "pk"))
        sin_ubicacion = edificios.exclude(**_CON_COORDENADAS).count()
        puntos += [punto_de_edificio(e) for e in ubicados]
        fuera = [f"{sin_ubicacion} sin ubicación"] if sin_ubicacion else []
        capas.append(_capa(CAPA_EDIFICIOS, "Edificios", "fa-building", "success", "Vigentes", ubicados, fuera))

    if puede_operar_la_mesa(user):
        abiertos = CasoEmergencia.objects.exclude(estado=CasoEmergencia.Estado.CERRADO)
        ubicados = list(
            abiertos.filter(**_CON_COORDENADAS)
            .only("pk", "numero", "prioridad", "estado", "latitud", "longitud", "relevado_en")
            .order_by("-relevado_en", "pk")
        )
        sin_ubicacion = abiertos.exclude(**_CON_COORDENADAS).count()
        ahora = timezone.now()
        puntos += [punto_de_caso(c, ahora) for c in ubicados]
        fuera = [f"{sin_ubicacion} sin ubicación"] if sin_ubicacion else []
        capas.append(
            _capa(
                CAPA_EMERGENCIA,
                "Casos de Emergencia",
                "fa-triangle-exclamation",
                "danger",
                "Abiertos, sin datos de la persona",
                ubicados,
                fuera,
            )
        )

    sueltos = list(Punto.objects.select_related("cargado_por"))
    puntos += [punto_de_punto(p, editable=editable) for p in sueltos]
    capas.append(_capa(CAPA_PUNTOS, "Puntos", "fa-map-pin", "navy", "Cargados en el mapa", sueltos, []))

    return {"capas": capas, "puntos": puntos, "editable": editable}


def _capa(capa_id, nombre, icono, tono, nota, ubicados, fuera):
    return {
        "id": capa_id,
        "nombre": nombre,
        "icono": icono,
        "tono": tono,
        "nota": nota,
        "total": len(ubicados),
        "fuera": " · ".join(fuera),
    }


def categorias():
    """Subfiltros de la capa Puntos: ``[(valor, texto, icono)]``."""

    return [(valor, texto, ICONOS_CATEGORIA[valor]) for valor, texto in Punto.Categoria.choices]
