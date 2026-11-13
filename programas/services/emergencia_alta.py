"""El alta del caso de Emergencia: el Formulario 1 y :func:`crear_caso`.

Es la etapa 1 del módulo, separada de ``programas.services.emergencia`` para que ninguno
de los dos pase las mil líneas. Acá vive todo lo que corre **antes** de que el caso
exista: quién puede crear por cada origen, la idempotencia del envío (``uuid_cliente``),
la validación del Formulario 1 con los errores por campo, la prioridad sugerida, el
responsable por DNI (o su alta mínima) y las fotos. Lo que le pasa al caso después
—tomar, derivar, cerrar, vencer— sigue en ``emergencia.py``.

Las reglas de aquel módulo valen igual acá: la vista web, la API de la app y el ingreso
directo llaman a esta misma función (RU-2), y el orden de los candados es el que documenta
``programas.services.emergencia``. ``crear_caso`` no bloquea ningún caso —todavía no
hay—: su único candado es el del numerador, que es una hoja.

La dependencia va en un solo sentido: las piezas que comparte con la mesa (``_trazar``,
``_exigir_mesa``, ``siguiente_numero``) las toma de ``programas.services.emergencia_comun``,
nunca de ``emergencia``, y ``emergencia`` reexporta lo de acá: los imports de siempre
(``from programas.services.emergencia import crear_caso``) siguen andando.
"""

import uuid as _uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import File
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.archivos import anotar_archivo_escrito, archivos_atomicos
from core.db import q_uuid_en_texto
from core.dni import MENSAJE_DNI_INVALIDO, dni_valido, normalizar_dni
from core.models import Localidad
from core.validators import validar_foto
from legajos.models import Ciudadano
from programas.models import (
    AdjuntoCaso,
    CasoEmergencia,
    GrupoFamiliar,
    NumeradorEmergencia,
    TrazaCaso,
)
from programas.services.dispositivos import puede_en_programa_dispositivos
from programas.services.emergencia_comun import _exigir_mesa, _trazar, siguiente_numero
from programas.services.emergencia_programa import CAP_EMERGENCIA_RELEVAR, puede_en_programa_emergencia
from programas.services.ingreso import alta_minima_de_persona, buscar_ciudadano_por_dni

Estado = CasoEmergencia.Estado
Origen = CasoEmergencia.Origen
Prioridad = CasoEmergencia.Prioridad
Accion = TrazaCaso.Accion

#: El ingreso directo lo hace la guardia del dispositivo, con la capacidad de su programa.
CAP_ADMITIR = "dispositivo.admitir"

#: Los cuatro avisos del paso 3 del Formulario 1, en el orden de la pantalla.
NECESIDADES = ("embarazo", "electrodependiente", "medicacion_critica", "mascotas")
#: De esos, los que por sí solos hacen ALTA la prioridad sugerida (RN-1.4). Mascotas no.
NECESIDADES_CRITICAS = ("embarazo", "electrodependiente", "medicacion_critica")

PRIMERA_TRAZA = {
    Origen.TERRITORIO: "Relevado en territorio",
    Origen.MESA: "Cargado por la mesa",
    Origen.DISPOSITIVO: "Ingreso directo en el dispositivo",
}

SIN_PERMISO_DE_RELEVAR = "No tenés permiso para relevar familias en Emergencia."
SIN_PERMISO_DE_INGRESO_DIRECTO = "No tenés permiso para registrar un ingreso directo."
UUID_EN_USO = "Ese identificador de envío ya se usó en otro caso."
FOTO_NO_ES_UN_ARCHIVO = "Mandá la foto como archivo: no se aceptan rutas ni archivos ya guardados."


class UuidEnUso(ValidationError):
    """El ``uuid_cliente`` ya creó un caso de otro usuario: no es un reenvío.

    Es un ``ValidationError`` con la clave ``uuid_cliente`` —la mesa y quien ya lo atrapa como
    tal lo ven igual que antes—, pero con tipo propio para que la API lo convierta en 409 sin
    comparar el texto del mensaje.
    """

    def __init__(self, mensaje=None):
        super().__init__({"uuid_cliente": mensaje or UUID_EN_USO})


#: El tope de ``CasoEmergencia.precision_m`` (``PositiveIntegerField``) en MySQL y MariaDB.
PRECISION_MAXIMA_M = 2147483647


def prioridad_sugerida(*, menores, mayores, dependientes, mayores_dependientes, lactantes, necesidades):
    """La prioridad con la que nace el caso (RN-1.4). La mesa la puede cambiar después.

    * **ALTA** — algún lactante, algún mayor dependiente, o embarazo, electrodependencia o
      medicación crítica.
    * **MEDIA** — alguna persona con dependencia, algún menor o algún mayor.
    * **BAJA** — el resto.
    """

    if lactantes > 0 or mayores_dependientes > 0 or any(necesidades.get(clave) for clave in NECESIDADES_CRITICAS):
        return Prioridad.ALTA
    if dependientes > 0 or menores > 0 or mayores > 0:
        return Prioridad.MEDIA
    return Prioridad.BAJA


def _entero(datos, campo, errores):
    valor = datos.get(campo)
    if valor in (None, ""):
        return 0
    try:
        if isinstance(valor, bool) or int(valor) != float(valor):
            raise ValueError
        numero = int(valor)
    except (TypeError, ValueError):
        errores[campo] = "Tiene que ser un número entero."
        return 0
    if numero < 0:
        errores[campo] = "No puede ser negativo."
        return 0
    return numero


def _texto(datos, campo):
    return str(datos.get(campo) or "").strip()


def _problemas_de_las_fotos(fotos):
    """Los errores de las fotos, antes de numerar y de escribir nada.

    Solo entra un archivo **sin guardar**, el que llega en la subida: una ruta (``str``) o
    un archivo ya guardado (``_committed``) colgaría del caso un archivo que ya está en el
    disco y que ``validar_foto`` no mira. El ``full_clean`` del adjunto vuelve a validar
    al guardar.
    """

    problemas = []
    for tipo, archivo in fotos.items():
        rotulo = AdjuntoCaso.Tipo(tipo).label
        if not isinstance(archivo, File) or getattr(archivo, "_committed", False):
            problemas.append(f"{rotulo}: {FOTO_NO_ES_UN_ARCHIVO}")
            continue
        try:
            validar_foto(archivo)
        except ValidationError as error:
            problemas.extend(f"{rotulo}: {mensaje}" for mensaje in error.messages)
    return problemas


def _validar_formulario1(datos):
    """Las reglas del Formulario 1 que valen para cualquier origen. Devuelve los datos limpios.

    Levanta un ``ValidationError`` con los errores **por campo**, todos juntos: quien
    corrige un envío rechazado desde el teléfono no puede ir de a uno.
    """

    errores = {}
    limpio = {}

    limpio["traslado"] = _texto(datos, "traslado")
    limpio["traslado_otro"] = _texto(datos, "traslado_otro")
    if limpio["traslado"] not in GrupoFamiliar.Traslado.values:
        errores["traslado"] = "Elegí la fuerza que traslada."
    elif limpio["traslado"] == GrupoFamiliar.Traslado.OTRA and not limpio["traslado_otro"]:
        errores["traslado_otro"] = "Indicá qué fuerza traslada."
    elif limpio["traslado"] != GrupoFamiliar.Traslado.OTRA:
        limpio["traslado_otro"] = ""

    limpio["dni"] = normalizar_dni(datos.get("dni"))
    if not limpio["dni"]:
        errores["dni"] = MENSAJE_DNI_INVALIDO

    for campo in (*GrupoFamiliar.CANTIDADES, "dependientes", "mayores_dependientes", "lactantes"):
        limpio[campo] = _entero(datos, campo, errores)
    menores = limpio["menores_f"] + limpio["menores_m"]
    mayores = limpio["mayores_f"] + limpio["mayores_m"]
    # RN-1.2: el total es del servidor. Lo que mande el cliente como total ni se mira.
    total = sum(limpio[campo] for campo in GrupoFamiliar.CANTIDADES)
    limpio["total_declarado"] = total
    if not any(campo in errores for campo in GrupoFamiliar.CANTIDADES):
        if total < 1:
            errores["total"] = "Cargá al menos una persona."
        else:
            # RN-1.3
            if limpio["dependientes"] > total:
                errores.setdefault("dependientes", "No puede haber más personas con dependencia que personas.")
            if limpio["mayores_dependientes"] > mayores:
                errores.setdefault("mayores_dependientes", "No puede haber más mayores dependientes que mayores.")
            if limpio["lactantes"] > menores:
                errores.setdefault("lactantes", "No puede haber más lactantes que menores.")

    limpio["necesidades"] = {clave: bool(datos.get(clave)) for clave in NECESIDADES}

    # RN-1.12: sin GPS se puede enviar; sin dirección, no.
    limpio["direccion"] = _texto(datos, "direccion")
    if not limpio["direccion"]:
        errores["direccion"] = "Escribí la dirección o una referencia: es el mínimo para ubicar a la familia."
    elif len(limpio["direccion"]) > 240:
        errores["direccion"] = "La dirección no puede tener más de 240 caracteres."

    latitud, longitud = datos.get("latitud"), datos.get("longitud")
    limpio["latitud"] = limpio["longitud"] = limpio["precision_m"] = None
    if latitud not in (None, "") or longitud not in (None, ""):
        try:
            latitud, longitud = round(float(latitud), 6), round(float(longitud), 6)
            if not (-90 <= latitud <= 90 and -180 <= longitud <= 180):
                raise ValueError
        except (TypeError, ValueError):
            errores["latitud"] = "La posición del GPS no es válida."
        else:
            limpio["latitud"], limpio["longitud"] = latitud, longitud
            precision = datos.get("precision_m")
            if precision not in (None, ""):
                try:
                    limpio["precision_m"] = max(int(round(float(precision))), 0)
                    if limpio["precision_m"] > PRECISION_MAXIMA_M:
                        raise ValueError
                except (TypeError, ValueError, OverflowError):
                    limpio["precision_m"] = None
                    errores["precision_m"] = "La precisión del GPS no es válida."

    localidad = datos.get("localidad")
    limpio["localidad"] = None
    if localidad not in (None, ""):
        if isinstance(localidad, Localidad):
            limpio["localidad"] = localidad
        else:
            try:
                limpio["localidad"] = Localidad.objects.filter(pk=int(localidad)).first()
            except (TypeError, ValueError):
                limpio["localidad"] = None
            if limpio["localidad"] is None:
                errores["localidad"] = "Elegí una localidad de la lista."

    fotos = datos.get("fotos") or {}
    desconocidas = set(fotos) - set(AdjuntoCaso.Tipo.values)
    if desconocidas:
        errores["fotos"] = "Las fotos del caso son la de la vivienda y la del acceso."
    limpio["fotos"] = {tipo: archivo for tipo, archivo in fotos.items() if archivo}
    if "fotos" not in errores:
        problemas = _problemas_de_las_fotos(limpio["fotos"])
        if problemas:
            errores["fotos"] = problemas

    limpio["situacion"] = {}
    for clave in ("telefono", "observaciones"):
        if _texto(datos, clave):
            limpio["situacion"][clave] = _texto(datos, clave)
    if datos.get("documento_extraviado"):
        limpio["situacion"]["documento_extraviado"] = True

    if errores:
        raise ValidationError(errores)
    return limpio


def _responsable(datos, limpio):
    """El ``Ciudadano`` del responsable: el que ya está en el legajo, o su alta mínima (RN-1.5).

    El alta es la del asistente de ingreso de Dispositivos (``ingreso.alta_minima_de_persona``),
    no una copia. El sexo se infiere **solo** si la familia es de una persona; si no, queda
    sin dato y lo completa la ficha de la etapa 3. «Perdió el documento pero sabe el
    número» se guarda como ``dni_fisico = NO_TIENE`` en la persona que se da de alta acá
    (hallazgo H5); a quien ya tenía legajo no se le toca nada.
    """

    existente = buscar_ciudadano_por_dni(limpio["dni"])
    if existente is not None:
        return existente
    if not dni_valido(limpio["dni"]):
        raise ValidationError({"dni": MENSAJE_DNI_INVALIDO})
    nombre, apellido = _texto(datos, "nombre"), _texto(datos, "apellido")
    if not nombre or not apellido:
        raise ValidationError(
            {"nombre": "La persona no está en el legajo: cargá su nombre y su apellido para darla de alta."}
        )
    genero = ""
    if limpio["total_declarado"] == 1:
        femenino = limpio["menores_f"] + limpio["adultos_f"] + limpio["mayores_f"]
        genero = Ciudadano.Genero.FEMENINO if femenino == 1 else Ciudadano.Genero.MASCULINO
    fecha = datos.get("fecha_nacimiento")
    try:
        ciudadano = alta_minima_de_persona(
            {
                "dni": limpio["dni"],
                "nombre": nombre,
                "apellido": apellido,
                "fecha_nacimiento": fecha.isoformat() if hasattr(fecha, "isoformat") else (fecha or None),
                "genero": genero,
            }
        )
    except ValidationError as error:
        raise ValidationError({"nombre": error.messages}) from error
    if datos.get("documento_extraviado") and not ciudadano.dni_fisico:
        ciudadano.dni_fisico = Ciudadano.DniFisico.NO_TIENE
        ciudadano.save(update_fields=["dni_fisico", "modificado"])
    return ciudadano


def _caso_de_ese_envio(uuid_cliente, usuario):
    """El caso que ya creó ese ``uuid_cliente``, o ``None``. De otro usuario, :class:`UuidEnUso`."""

    existente = CasoEmergencia.objects.filter(q_uuid_en_texto("uuid_cliente", uuid_cliente)).first()
    if existente is None:
        return None
    if existente.relevado_por_id != usuario.pk:
        # El mismo identificador en manos de otro no es un reenvío: no se le devuelve un caso ajeno.
        raise UuidEnUso()
    existente.ya_existia = True
    return existente


def _como_uuid(valor):
    if valor in (None, ""):
        return None
    if isinstance(valor, _uuid.UUID):
        return valor
    try:
        return _uuid.UUID(str(valor))
    except (AttributeError, TypeError, ValueError):
        raise ValidationError({"uuid_cliente": "El identificador del envío no es válido."}) from None


def _exigir_puede_crear(usuario, origen):
    """Quién crea por cada origen (tabla de RU §4)."""

    if origen == Origen.TERRITORIO:
        if not puede_en_programa_emergencia(usuario, CAP_EMERGENCIA_RELEVAR):
            raise PermissionDenied(SIN_PERMISO_DE_RELEVAR)
    elif origen == Origen.MESA:
        _exigir_mesa(usuario)
    elif origen == Origen.DISPOSITIVO:
        # Acá solo se puede exigir la capacidad en el programa Dispositivos: esta función no
        # sabe en qué institución es el ingreso. El alcance sobre **ese** dispositivo lo
        # exige quien la llama (el ingreso directo de la etapa 3).
        if not puede_en_programa_dispositivos(usuario, CAP_ADMITIR):
            raise PermissionDenied(SIN_PERMISO_DE_INGRESO_DIRECTO)
    else:
        raise ValueError(f"«{origen}» no es un origen de caso.")


@archivos_atomicos
@transaction.atomic
def crear_caso(*, usuario, origen, datos_formulario1, uuid_cliente=None, relevado_en=None):
    """Crea un caso con su grupo familiar. **La única función que crea casos.**

    La usan la mesa («Nuevo caso»), la API de la app (M1) y el ingreso directo del
    dispositivo. Qué hace, en este orden:

    1. Exige la capacidad del origen: ``emergencia.relevar`` para ``TERRITORIO``,
       ``emergencia.operar`` (o ``supervisar``) para ``MESA`` y ``dispositivo.admitir`` en el
       programa Dispositivos para ``DISPOSITIVO``.
    2. **Idempotencia** (RU-16): si ``uuid_cliente`` ya creó un caso de este usuario, lo
       devuelve tal cual, con ``caso.ya_existia = True``, sin validar ni escribir nada. El
       mismo identificador usado por otro usuario es un :class:`UuidEnUso` (``ValidationError``).
    3. Valida el Formulario 1 (``ValidationError`` con los errores por campo): total ≥ 1,
       RN-1.3, dirección obligatoria (RN-1.12) y fotos: solo archivos subidos, sin guardar, que
       sean fotos de verdad.
    4. Calcula **en el servidor** ``total_declarado`` (RN-1.2) y la prioridad (RN-1.4).
    5. Resuelve el ``Ciudadano`` del responsable por DNI, o le da el alta mínima (RN-1.5).
    6. Numera con el contador de la serie ``C`` y da de alta grupo, caso, fotos y la
       primera traza.

    Cómo nace según el origen:

    * ``TERRITORIO`` — ``NUEVO``, sin tomar (RN-1.10).
    * ``MESA`` — ``EN_GESTION``, tomado por quien lo carga, con ``tomado_en`` (HU-1.4).
    * ``DISPOSITIVO`` — ``NUEVO`` y sin tomar: **esta función no crea la derivación
      implícita** del ingreso directo. La completa el servicio de la etapa 3 en la misma
      transacción (RN-3.10).

    ``datos_formulario1`` es un dict con:

    * ``traslado`` (código de ``GrupoFamiliar.Traslado``) y ``traslado_otro`` si es «Otra».
    * ``dni`` del responsable; ``nombre`` y ``apellido`` si no está en el legajo;
      opcionales ``fecha_nacimiento``, ``telefono`` y ``documento_extraviado``.
    * las seis cantidades (``menores_f``, ``menores_m``, ``adultos_f``, ``adultos_m``,
      ``mayores_f``, ``mayores_m``), ``dependientes``, ``mayores_dependientes``, ``lactantes``.
    * los avisos ``embarazo``, ``electrodependiente``, ``medicacion_critica``, ``mascotas``.
    * ``direccion`` (obligatoria); opcionales ``localidad`` (id o instancia de
      ``core.Localidad``), ``latitud``, ``longitud``, ``precision_m`` y ``observaciones``.
    * ``fotos``: opcional, ``{"VIVIENDA": archivo, "ACCESO": archivo}``.

    Cualquier otra clave se ignora, incluido un ``total`` o una ``prioridad`` que mande el
    cliente.

    ``relevado_en`` es la hora del teléfono al tocar «Enviar» (la única hora del cliente
    que se guarda, RU-18); sin ella, la del servidor.
    """

    if origen not in Origen.values:
        raise ValueError(f"«{origen}» no es un origen de caso.")
    _exigir_puede_crear(usuario, origen)

    uuid_cliente = _como_uuid(uuid_cliente)
    if uuid_cliente is not None:
        existente = _caso_de_ese_envio(uuid_cliente, usuario)
        if existente is not None:
            return existente

    limpio = _validar_formulario1(datos_formulario1)
    ahora = timezone.now()
    responsable = _responsable(datos_formulario1, limpio)
    prioridad = prioridad_sugerida(
        menores=limpio["menores_f"] + limpio["menores_m"],
        mayores=limpio["mayores_f"] + limpio["mayores_m"],
        dependientes=limpio["dependientes"],
        mayores_dependientes=limpio["mayores_dependientes"],
        lactantes=limpio["lactantes"],
        necesidades=limpio["necesidades"],
    )
    nace_tomado = origen == Origen.MESA

    try:
        # Anidada: si el UNIQUE de `uuid_cliente` salta —el mismo envío llegó dos veces a la
        # vez—, se deshacen el grupo y el número y la transacción de afuera sigue sana.
        with transaction.atomic():
            grupo = GrupoFamiliar(
                responsable=responsable,
                traslado=limpio["traslado"],
                traslado_otro=limpio["traslado_otro"],
                dependientes=limpio["dependientes"],
                mayores_dependientes=limpio["mayores_dependientes"],
                lactantes=limpio["lactantes"],
                total_declarado=limpio["total_declarado"],
                **{campo: limpio[campo] for campo in GrupoFamiliar.CANTIDADES},
            )
            grupo.full_clean()
            grupo.save()
            caso = CasoEmergencia(
                numero=siguiente_numero(NumeradorEmergencia.Serie.CASOS, ahora),
                grupo=grupo,
                origen=origen,
                estado=Estado.EN_GESTION if nace_tomado else Estado.NUEVO,
                prioridad=prioridad,
                localidad=limpio["localidad"],
                latitud=limpio["latitud"],
                longitud=limpio["longitud"],
                precision_m=limpio["precision_m"],
                direccion=limpio["direccion"],
                necesidades=limpio["necesidades"],
                situacion=limpio["situacion"],
                tomado_por=usuario if nace_tomado else None,
                tomado_en=ahora if nace_tomado else None,
                relevado_por=usuario,
                relevado_en=relevado_en or ahora,
                uuid_cliente=uuid_cliente,
            )
            caso.save()
    except IntegrityError:
        existente = _caso_de_ese_envio(uuid_cliente, usuario) if uuid_cliente is not None else None
        if existente is None:
            raise
        return existente

    for tipo, archivo in limpio["fotos"].items():
        adjunto = AdjuntoCaso(caso=caso, archivo=archivo, tipo=tipo, cargado_por=usuario)
        adjunto.full_clean()
        adjunto.save()
        anotar_archivo_escrito(adjunto.archivo, asignado=archivo)

    _trazar(caso, usuario, Accion.CREADO, estado_anterior="", detalle=PRIMERA_TRAZA[origen])
    caso.ya_existia = False
    return caso
