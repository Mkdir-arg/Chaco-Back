"""El panel «Derivar» de la mesa por edificio (Cambio 520): dónde hay camas y a qué distancia de la familia.

La mesa elige primero el **edificio** —el inmueble, que es donde están las camas— y después la
**institución** que lo ocupa: un edificio puede alojar a tres instituciones y una institución puede
ocupar más de un edificio. Las camas son las de ``selectors.emergencia.camas_de`` (la cuenta única de
Emergencia), repartidas por el edificio de cada sector, que viaja en la misma fila del censo.

La distancia se mide desde el **domicilio de la familia**, no desde el GPS de la toma:

1. el punto del domicilio que ubicó el backoffice (``domicilio_latitud``/``domicilio_longitud``);
2. en un caso cargado por la mesa antes del Cambio 520 (sin precisión de GPS), ``latitud``/``longitud``, que
   ahí guardaban el domicilio ubicado en el mapa;
3. el centroide de la localidad del caso (``core.UbicacionLocalidad``): aproximada;
4. el GPS del teléfono al relevar, solo si no hay nada de lo anterior.

Hasta cada edificio: sus coordenadas o, si no las tiene, el centroide de su localidad (aproximada). Una
coordenada fuera de la caja del Chaco (``services.situacion_emergencia.ubicacion_valida``) cuenta como que no está. Una
institución con camas en sectores sin edificio asignado (anteriores al Cambio 429) se muestra como su propio
grupo, ubicado con las coordenadas de la institución.

Edificios de ubicación reservada: los que ocupa una institución cuyo tipo es de ubicación reservada (Cambio
499). Siguen en el panel —la mesa tiene que poder derivar ahí— pero sin domicilio: solo el nombre, la
localidad y la distancia en línea recta, que se calcula en el servidor y nunca sale hacia Google.
"""

from collections import Counter
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db.models import Exists, OuterRef

from core.selectors.geografia import PROVINCIA_OPERATIVA, localidades_operativas
from core.services.ubicaciones_localidades import clave
from programas.models import CasoEmergencia, Dispositivo, Edificio
from programas.selectors.emergencia import (
    MARCA_ALCANZA,
    MARCA_FALTAN,
    MARCA_SIN_PLAZAS,
    SIN_PERMISO_DE_MESA,
    camas_de,
    camas_libres_del_conteo,
    dispositivos_elegibles,
    distancia_km,
    marca_de_plazas,
)
from programas.services.emergencia_programa import puede_operar_la_mesa
from programas.services.situacion_emergencia import ubicacion_valida

#: De dónde sale el punto de la familia.
ORIGEN_DOMICILIO = "domicilio"
ORIGEN_LOCALIDAD = "localidad"
ORIGEN_GPS = "gps"

#: El prefijo de la clave de un grupo del panel: un edificio, o los sectores sin edificio de una institución.
PREFIJO_EDIFICIO = "e"
PREFIJO_SIN_EDIFICIO = "d"

ORDEN_DE_MARCA = {MARCA_ALCANZA: 0, MARCA_FALTAN: 1, MARCA_SIN_PLAZAS: 2}


@dataclass(frozen=True)
class Punto:
    latitud: float
    longitud: float
    #: ``True`` si es el centroide de una localidad y no una dirección.
    aproximado: bool
    origen: str = ""


@dataclass(frozen=True)
class Centroides:
    """Los centroides de las localidades de la provincia, por id y por nombre. **1 consulta.**

    Por nombre solo entran los que no se repiten: ``Edificio.localidad`` y ``Dispositivo.localidad`` son
    texto, y un nombre que tienen dos localidades no dice cuál.
    """

    por_id: dict
    por_nombre: dict

    @classmethod
    def leer(cls):
        # Todas las localidades, con centroide o sin él: los homónimos se cuentan sobre todas, como en E8.
        filas = list(localidades_operativas().values_list("id", "nombre", "ubicacion__latitud", "ubicacion__longitud"))
        cuantas = Counter(clave(nombre) for _pk, nombre, _latitud, _longitud in filas)
        con_centroide = [fila for fila in filas if ubicacion_valida(fila[2], fila[3])]
        return cls(
            por_id={pk: (latitud, longitud) for pk, _nombre, latitud, longitud in con_centroide},
            por_nombre={
                clave(nombre): (latitud, longitud)
                for _pk, nombre, latitud, longitud in con_centroide
                if cuantas[clave(nombre)] == 1
            },
        )

    def de_localidad(self, localidad_id):
        punto = self.por_id.get(localidad_id)
        return Punto(*punto, aproximado=True, origen=ORIGEN_LOCALIDAD) if punto else None

    def de_nombre(self, nombre):
        punto = self.por_nombre.get(clave(nombre or ""))
        return Punto(*punto, aproximado=True, origen=ORIGEN_LOCALIDAD) if punto else None


def _par(latitud, longitud):
    """Un punto que sirve: las dos coordenadas y dentro de la caja del Chaco. Fuera, es un error de carga (E8)."""

    return ubicacion_valida(latitud, longitud)


def domicilio_ubicado(caso):
    """El punto del domicilio de la familia si ya está ubicado (pasos 1 y 2 del módulo), o ``None``. Sin consultas."""

    if _par(caso.domicilio_latitud, caso.domicilio_longitud):
        return Punto(caso.domicilio_latitud, caso.domicilio_longitud, aproximado=False, origen=ORIGEN_DOMICILIO)
    # Solo la mesa: un caso con origen «Ingreso directo» también puede venir de la app, con GPS sin precisión.
    de_la_mesa_antes_del_cambio = caso.origen == CasoEmergencia.Origen.MESA and caso.precision_m is None
    if de_la_mesa_antes_del_cambio and _par(caso.latitud, caso.longitud):
        return Punto(caso.latitud, caso.longitud, aproximado=False, origen=ORIGEN_DOMICILIO)
    return None


def punto_de_la_familia(caso, centroides):
    """Desde dónde se mide la distancia a los edificios (ver el docstring del módulo), o ``None``. Sin consultas."""

    ubicado = domicilio_ubicado(caso)
    if ubicado is not None:
        return ubicado
    centroide = centroides.de_localidad(caso.localidad_id)
    if centroide is not None:
        return centroide
    if _par(caso.latitud, caso.longitud):
        return Punto(caso.latitud, caso.longitud, aproximado=False, origen=ORIGEN_GPS)
    return None


def distancia_entre(origen, destino):
    """``{"km", "aproximada"}`` en línea recta, o ``None`` si falta alguno de los dos puntos."""

    if origen is None or destino is None:
        return None
    km = distancia_km(origen.latitud, origen.longitud, destino.latitud, destino.longitud)
    return {"km": km, "aproximada": origen.aproximado or destino.aproximado}


def texto_de_distancia(distancia):
    """Lo que dice la tarjeta: «a 3,1 km en línea recta», «≈ 12,0 km (por localidad)» o «distancia desconocida»."""

    if distancia is None:
        return "distancia desconocida"
    km = f"{distancia['km']:.1f}".replace(".", ",")
    if distancia["aproximada"]:
        return f"≈ {km} km (por localidad)"
    return f"a {km} km en línea recta"


def _edificios(ids):
    """Los edificios con camas, con la marca de reservado. **1 consulta** (con un ``EXISTS``)."""

    if not ids:
        return {}
    reservado = Dispositivo.objects.filter(edificios=OuterRef("pk"), tipo__ubicacion_reservada=True)
    edificios = (
        Edificio.objects.filter(pk__in=ids)
        .annotate(reservado=Exists(reservado))
        .only("id", "nombre", "calle", "numero", "localidad", "latitud", "longitud")
    )
    return {edificio.pk: edificio for edificio in edificios}


def _ubicacion_de_edificio(edificio, centroides):
    if _par(edificio.latitud, edificio.longitud):
        return Punto(edificio.latitud, edificio.longitud, aproximado=False)
    return centroides.de_nombre(edificio.localidad)


def _ubicacion_de_dispositivo(dispositivo, centroides):
    if _par(dispositivo.latitud, dispositivo.longitud):
        return Punto(dispositivo.latitud, dispositivo.longitud, aproximado=False)
    return centroides.de_nombre(dispositivo.localidad)


def clave_de_grupo(edificio_id, dispositivo_id):
    """``e12`` para el edificio 12; ``d34`` para los sectores sin edificio de la institución 34."""

    return f"{PREFIJO_EDIFICIO}{edificio_id}" if edificio_id is not None else f"{PREFIJO_SIN_EDIFICIO}{dispositivo_id}"


def edificios_para_derivar(caso, usuario, *, plazas=None, momento=None):
    """Los edificios con camas para derivar ``caso``, cada uno con sus instituciones. Ver el docstring del módulo.

    Lo autoriza ``emergencia.operar`` (o ``supervisar``), como ``dispositivos_para_derivar`` (RU-14): sin eso,
    ``PermissionDenied``. Cada grupo es un dict:

    ``{"clave", "edificio_id", "nombre", "ubicacion", "localidad", "reservado", "libres", "reservadas",
    "distancia", "distancia_texto", "destino", "marca", "faltan", "instituciones"}``

    * ``destino`` es hasta dónde se pide la distancia por calle: ``{"lat", "lng"}`` o ``{"direccion"}``, o
      ``None`` en un edificio de ubicación reservada o sin ubicación: esos nunca salen hacia Google.

    * ``libres`` y ``reservadas`` suman las camas de todas sus instituciones **en ese edificio**.
    * ``instituciones``: ``{"id", "nombre", "libres", "reservadas", "marca", "faltan"}`` con las camas de esa
      institución en ese edificio, la que más tiene primero.
    * ``marca`` es la de la mejor institución: se deriva a una sola, así que un edificio con 100 camas
      repartidas de a 10 no «alcanza» para una familia de 12.
    * ``ubicacion`` es el domicilio del edificio; en uno de ubicación reservada, solo la localidad.

    Orden: los que alcanzan primero, después los que no y al final los que no tienen camas; dentro de cada
    grupo, el más cercano, con la distancia desconocida al final.

    **Presupuesto: 6 consultas fijas**, haya 5 edificios o 500: los elegibles, las tres del censo, los
    edificios con su marca de reservado y los centroides de las localidades.
    """

    if not puede_operar_la_mesa(usuario):
        raise PermissionDenied(SIN_PERMISO_DE_MESA)
    pedidas = caso.grupo.total_declarado if plazas is None else int(plazas)
    dispositivos = dispositivos_elegibles()
    censo = camas_de([dispositivo.pk for dispositivo in dispositivos], momento)
    ocupaciones = {dispositivo.pk: censo.de(dispositivo.pk) for dispositivo in dispositivos}
    edificios = _edificios(
        {edificio_id for ocupacion in ocupaciones.values() for edificio_id in ocupacion.edificios() if edificio_id}
    )
    centroides = Centroides.leer()
    familia = punto_de_la_familia(caso, centroides)

    grupos = {}
    for dispositivo in dispositivos:
        ocupacion = ocupaciones[dispositivo.pk]
        for edificio_id in ocupacion.edificios():
            edificio = edificios.get(edificio_id) if edificio_id is not None else None
            if edificio_id is not None and edificio is None:
                continue
            llave = clave_de_grupo(edificio_id, dispositivo.pk)
            grupo = grupos.get(llave)
            if grupo is None:
                grupo = grupos[llave] = _grupo_nuevo(llave, edificio, dispositivo, familia, centroides)
            conteo = ocupacion.conteo_del_edificio(edificio_id)
            libres = camas_libres_del_conteo(conteo)
            marca, faltan = marca_de_plazas(libres, pedidas)
            grupo["instituciones"].append(
                {
                    "id": dispositivo.pk,
                    "nombre": dispositivo.nombre,
                    "libres": libres,
                    "reservadas": conteo.reservadas or 0,
                    "marca": marca,
                    "faltan": faltan,
                }
            )
            grupo["libres"] += libres
            grupo["reservadas"] += conteo.reservadas or 0

    for grupo in grupos.values():
        grupo["instituciones"].sort(key=lambda fila: (-fila["libres"], fila["nombre"], fila["id"]))
        mejor = grupo["instituciones"][0]["libres"] if grupo["instituciones"] else 0
        grupo["marca"], grupo["faltan"] = marca_de_plazas(mejor, pedidas)

    return sorted(
        grupos.values(),
        key=lambda grupo: (
            ORDEN_DE_MARCA[grupo["marca"]],
            grupo["distancia"] is None,
            grupo["distancia"]["km"] if grupo["distancia"] else 0.0,
            grupo["nombre"],
            grupo["clave"],
        ),
    )


def _destino_por_calle(reservado, destino, calle_y_numero, localidad):
    """Hasta dónde le pide Google la distancia por calle (fase 2), o ``None``. Nunca un edificio reservado.

    Las coordenadas si son exactas; si no, la dirección del edificio (Google la ubica mejor que el centroide
    de la localidad); y si tampoco hay calle, el centroide.
    """

    if reservado:
        return None
    if destino is not None and not destino.aproximado:
        return {"lat": float(destino.latitud), "lng": float(destino.longitud)}
    if calle_y_numero:
        partes = (calle_y_numero, localidad, PROVINCIA_OPERATIVA, "Argentina")
        return {"direccion": ", ".join(parte for parte in partes if parte)}
    if destino is not None:
        return {"lat": float(destino.latitud), "lng": float(destino.longitud)}
    return None


def _grupo_nuevo(llave, edificio, dispositivo, familia, centroides):
    if edificio is not None:
        reservado = edificio.reservado
        nombre = edificio.nombre
        localidad = edificio.localidad or ""
        calle_y_numero = " ".join(parte for parte in (edificio.calle, edificio.numero) if parte)
        domicilio = " · ".join(parte for parte in (calle_y_numero, localidad) if parte)
        destino = _ubicacion_de_edificio(edificio, centroides)
    else:
        reservado = dispositivo.tipo.ubicacion_reservada
        nombre = f"{dispositivo.nombre} (sin edificio asignado)"
        localidad = dispositivo.localidad or ""
        calle_y_numero = ""
        domicilio = localidad
        destino = _ubicacion_de_dispositivo(dispositivo, centroides)
    distancia = distancia_entre(familia, destino)
    return {
        "destino": _destino_por_calle(reservado, destino, calle_y_numero, localidad),
        "clave": llave,
        "edificio_id": edificio.pk if edificio is not None else None,
        "nombre": nombre,
        "ubicacion": localidad if reservado else domicilio,
        "localidad": localidad,
        "reservado": reservado,
        "libres": 0,
        "reservadas": 0,
        "distancia": distancia,
        "distancia_texto": texto_de_distancia(distancia),
        "marca": MARCA_SIN_PLAZAS,
        "faltan": 0,
        "instituciones": [],
    }
