"""Quién recibe una entrega de insumos: la persona, por DNI (análisis 010, PR 2b, RN-010-09).

Se apoya en ``services/ingreso`` y **no duplica** su lógica: el legajo se busca con ``buscar_ciudadano_por_dni``, el
Registro de Personas con ``buscar_en_registro_de_personas`` y el alta es la del asistente de ingreso
(``alta_desde_registro`` y ``alta_minima_de_persona``), con el mismo formulario y la misma tolerancia a la carrera por
el DNI. El orden es el del ingreso: **legajo → Registro → alta mínima**.

Dos pasos separados a propósito:

* :func:`resolver_persona` **solo lee**: no escribe nada ni toma candados. Es lo que corre antes de la transacción de
  la entrega (la consulta al Registro es de red y no debe hacerse con filas bloqueadas) y lo que usa la pantalla para
  mostrar a quién se le entrega sin dar de alta a nadie.
* :func:`dar_de_alta` escribe, y corre **dentro** de la transacción de la entrega: si la entrega falla (saldo, estado),
  no queda un legajo huérfano.

Ninguna función de acá pide permiso: lo exige quien llama (``stock.entregar`` con ``ciudadano.ver``), porque lo que
devuelve es identidad.
"""

from typing import NamedTuple

from django.core.exceptions import ValidationError

from core.dni import MENSAJE_DNI_INVALIDO, dni_valido, normalizar_dni
from legajos.models import Ciudadano
from programas.selectors.kits import fecha_hora
from programas.services import ingreso

PERSONA_FALLECIDA = "La persona figura fallecida en el Registro de Personas: no se le puede entregar."
SEXO_INVALIDO = "Elegí un sexo de la lista."
FALTA_EL_SEXO = (
    "La persona no está en el legajo: indicá su sexo para consultar el Registro de Personas, "
    "o cargá su nombre y apellido."
)
FALTAN_NOMBRE_Y_APELLIDO = "El Registro de Personas no la tiene: cargá su nombre y apellido para darla de alta."

SEXOS = frozenset(Ciudadano.Genero.values)


class PersonaSinDatos(ValidationError):
    """No hay legajo ni datos del Registro con los que dar de alta a la persona (``PERSONA_SIN_DATOS``).

    ``pide_sexo`` es ``True`` cuando ni siquiera se pudo consultar el Registro (falta el sexo): la pantalla pide el
    sexo **o** el nombre y el apellido. Con ``False`` se consultó y no hubo datos: ``motivo`` dice por qué (no está,
    o el servicio no respondió) y faltan el nombre y el apellido.
    """

    def __init__(self, message, *, pide_sexo, motivo=""):
        super().__init__(message, code="PERSONA_SIN_DATOS")
        self.pide_sexo = pide_sexo
        self.motivo = motivo


class PersonaResuelta(NamedTuple):
    """A quién se le entrega. Exactamente uno de los tres orígenes viene cargado.

    ``ciudadano`` es un legajo que ya existe; ``datos_registro`` es lo que respondió el Registro (el legajo se da de
    alta con eso); ``datos_manual`` es el alta mínima con el nombre y el apellido que cargó quien entrega.
    """

    dni: str
    ciudadano: Ciudadano | None
    datos_registro: dict | None
    datos_manual: dict | None

    @property
    def origen(self):
        if self.ciudadano is not None:
            return "legajo"
        return "registro" if self.datos_registro is not None else "manual"

    @property
    def nombre(self):
        return self._dato("nombre")

    @property
    def apellido(self):
        return self._dato("apellido")

    def _dato(self, campo):
        if self.ciudadano is not None:
            return getattr(self.ciudadano, campo) or ""
        datos = self.datos_registro if self.datos_registro is not None else self.datos_manual
        return (datos.get(campo) or "").strip()


def _texto(valor):
    return (valor or "").strip()


def resolver_persona(dni, sexo="", nombre="", apellido=""):
    """La persona a la que se le entrega, **sin escribir nada** (RN-010-09). Devuelve :class:`PersonaResuelta`.

    1. **Legajo** por DNI (``buscar_ciudadano_por_dni``: encuentra también las fichas con separadores). Si el legajo
       figura fallecido, se rechaza.
    2. Sin legajo y con ``sexo``: **Registro de Personas**. Si figura fallecida, se rechaza. Si responde, esos datos.
    3. Sin Registro (no la tiene, o no respondió): el **alta mínima** con ``nombre`` y ``apellido``.

    Levanta ``ValidationError`` por campo (``dni`` inválido o fallecida, ``sexo`` fuera de la lista) o
    :class:`PersonaSinDatos` si no alcanza para identificarla. Con legajo no consulta al Registro ni mira el resto.
    """

    numero = normalizar_dni(dni)
    if not dni_valido(numero):
        raise ValidationError({"dni": MENSAJE_DNI_INVALIDO})
    sexo = _texto(sexo).upper()
    if sexo and sexo not in SEXOS:
        raise ValidationError({"sexo": SEXO_INVALIDO})
    ciudadano = ingreso.buscar_ciudadano_por_dni(numero)
    if ciudadano is not None:
        # DECISIÓN TOMADA POR DEFECTO: un legajo ya marcado fallecido se rechaza igual que si responde el Registro.
        if ciudadano.estado_renaper == Ciudadano.EstadoRenaper.FALLECIDO:
            raise ValidationError({"dni": PERSONA_FALLECIDA})
        return PersonaResuelta(numero, ciudadano, None, None)

    motivo = ""
    if sexo:
        datos, motivo, fallecido = ingreso.buscar_en_registro_de_personas(numero, sexo)
        if fallecido:
            raise ValidationError({"dni": PERSONA_FALLECIDA})
        if datos is not None:
            return PersonaResuelta(numero, None, datos, None)
    nombre, apellido = _texto(nombre), _texto(apellido)
    if not nombre or not apellido:
        raise PersonaSinDatos(FALTAN_NOMBRE_Y_APELLIDO if sexo else FALTA_EL_SEXO, pide_sexo=not sexo, motivo=motivo)
    return PersonaResuelta(numero, None, None, {"dni": numero, "nombre": nombre, "apellido": apellido, "genero": sexo})


def dar_de_alta(persona):
    """El legajo de ``persona``: el que ya tenía, o el que se da de alta ahora. **Escribe**: va en la transacción.

    Tolera la carrera por el DNI (si otro lo dio de alta mientras tanto, devuelve ese). Un dato que el formulario
    del legajo no acepta (un nombre de más de 120 caracteres, por ejemplo) se devuelve como error del campo ``nombre``.
    """

    if persona.ciudadano is not None:
        return persona.ciudadano
    try:
        if persona.datos_registro is not None:
            return ingreso.alta_desde_registro(persona.datos_registro)
        return ingreso.alta_minima_de_persona(persona.datos_manual)
    except ValidationError as error:
        raise ValidationError({"nombre": error.messages}) from error


def texto_de_la_persona(persona):
    """Lo que dice el aviso de la persona resuelta: quién es y de dónde salen sus datos (RN-010-09)."""

    if persona.origen == "legajo":
        return "Ya tiene legajo."
    if persona.origen == "registro":
        return "No tiene legajo: se da de alta con los datos del Registro de Personas al registrar la entrega."
    return "No está en el Registro de Personas: se da de alta con el nombre y el apellido que cargaste."


def filas_de_historial(historial):
    """Las filas de «Lo que recibió antes» (``selectors.stock.historial_de_persona``), ya en texto para el template.

    ``institucion`` ya viene resuelta por el selector: solo la propia se nombra, el resto es «Otra institución».
    """

    return [
        {
            "fecha": fecha_hora(entrega["creado_en"]),
            "institucion": entrega["institucion"],
            "propia": entrega["propia"],
            "lineas": [f"{linea['nombre']} · {linea['cantidad']} {linea['unidad']}" for linea in entrega["lineas"]],
        }
        for entrega in historial
    ]
