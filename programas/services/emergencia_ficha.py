"""El Formulario 2 de Emergencia: la ficha individual de cada persona de la familia (etapa 3).

Esquema fijo y versionado (decisión 6 del PM): :data:`ESQUEMA_FICHA` es la única definición
y :func:`normalizar_ficha` la única puerta. Ver esa constante para el JSON exacto que
guarda ``IntegranteGrupo.ficha`` y que consumen la API y la app.

**Puro**: nada de acá consulta la base ni toma un candado. Lo usan la confirmación
(``emergencia_confirmacion``), el formulario del backoffice y la API, siempre a través de
``programas.services.emergencia_alojar``, que lo reexporta.
"""

from django.core.exceptions import ValidationError
from django.db import models

from core.dni import dni_valido, normalizar_dni
from core.edad import edad_en_anios, fecha_o_none
from legajos.models import Ciudadano
from programas.models import IntegranteGrupo

Parentesco = IntegranteGrupo.Parentesco

SIN_NUMERO_DE_DOCUMENTO = (
    "Sin un número de DNI válido no se puede confirmar a la persona con cama. "
    "Cerrá el ingreso con diferencia, motivo «Otro», y contá que no tiene número de documento."
)

#: Versión del esquema. Va **adentro** de la ficha (clave ``version``): una ficha guardada
#: con otra versión se lee con el esquema de esa versión, no con este.
FICHA_VERSION = 1

BOOLEANO = "booleano"

TEXTO = "texto"

FECHA = "fecha"

OPCION = "opcion"


class NivelEducativo(models.TextChoices):
    SIN_INSTRUCCION = "SIN_INSTRUCCION", "Sin instrucción"
    INICIAL = "INICIAL", "Inicial"
    PRIMARIO = "PRIMARIO", "Primario"
    SECUNDARIO = "SECUNDARIO", "Secundario"
    TERCIARIO = "TERCIARIO", "Terciario"
    UNIVERSITARIO = "UNIVERSITARIO", "Universitario"


SECCION_PARENTESCO = "parentesco"

SECCION_DATOS = "datos_personales"

SECCION_AVISOS = "avisos_salud"

SECCION_EDUCACION = "educacion"

SECCION_VACUNACION = "vacunacion"

SECCION_SALUD = "salud"

SECCION_TRABAJO = "trabajo"

SECCION_OBSERVACIONES = "observaciones"

#: **El Formulario 2.** Sección → campo → ``(tipo, parámetro)``. Las ocho secciones de 03 §3
#: (M2-4), en el orden de la pantalla. Es la única definición: de acá salen el validador, el
#: formulario del backoffice y —tal cual— el contrato de la API y de la app.
#:
#: Lo que guarda ``IntegranteGrupo.ficha`` es este JSON, con **solo las claves respondidas**
#: (una pregunta sin responder no figura; ``false`` es una respuesta)::
#:
#:     {
#:       "version": 1,
#:       "parentesco":       {"parentesco": "JEFE|CONYUGE|HIJO|OTRO", "parentesco_otro": "…"},
#:       "datos_personales": {"dni": "30111222", "nombre": "…", "apellido": "…",
#:                            "sexo": "M|F|X", "fecha_nacimiento": "AAAA-MM-DD",
#:                            "fecha_nacimiento_aproximada": false, "telefono": "…",
#:                            "documento_extraviado": false},
#:       "avisos_salud":     {"embarazo": false, "discapacidad": false,
#:                            "electrodependiente": false, "medicacion_critica": true,
#:                            "medicacion_critica_nombre": "…",
#:                            "medicacion_critica_tiene_dosis": true,
#:                            "alergias_graves": false, "alergias_graves_detalle": "…"},
#:       "educacion":        {"sin_datos": false, "nivel_educativo": "PRIMARIO", "escuela": "…",
#:                            "asiste_escuela": true},
#:       "vacunacion":       {"sin_datos": false, "esquema_al_dia": true,
#:                            "vacunacion_observacion": "…"},
#:       "salud":            {"sin_datos": false, "obra_social": "…",
#:                            "enfermedades_cronicas": "…", "medicacion_habitual": "…"},
#:       "trabajo":          {"sin_datos": false, "ocupacion": "…", "ingresos": "…"},
#:       "observaciones":    {"sin_datos": false, "observaciones": "…", "mascotas": false,
#:                            "adulto_responsable": "…"}
#:     }
#:
#: Las tres primeras secciones son el **mínimo** para confirmar (:func:`ficha_minima_valida`);
#: las otras cinco se pueden completar después (:func:`completar_ficha`) y llevan
#: ``sin_datos``: «pregunté y no hay nada que cargar», que cuenta como sección completa.
#: Los nombres de campo no se repiten entre secciones, así que la ficha se puede aplanar a
#: ``{campo: valor}`` y volver a armar (:func:`ficha_a_plano`, :func:`ficha_desde_plano`);
#: aplanado, ``sin_datos`` de la sección ``salud`` es ``salud_sin_datos``.
ESQUEMA_FICHA = {
    SECCION_PARENTESCO: {
        "parentesco": (OPCION, tuple(Parentesco.values)),
        "parentesco_otro": (TEXTO, 80),
    },
    SECCION_DATOS: {
        "dni": (TEXTO, 12),
        "nombre": (TEXTO, 120),
        "apellido": (TEXTO, 120),
        "sexo": (OPCION, tuple(Ciudadano.Genero.values)),
        "fecha_nacimiento": (FECHA, None),
        "fecha_nacimiento_aproximada": (BOOLEANO, None),
        "telefono": (TEXTO, 40),
        "documento_extraviado": (BOOLEANO, None),
    },
    SECCION_AVISOS: {
        "embarazo": (BOOLEANO, None),
        "discapacidad": (BOOLEANO, None),
        "electrodependiente": (BOOLEANO, None),
        "medicacion_critica": (BOOLEANO, None),
        "medicacion_critica_nombre": (TEXTO, 200),
        "medicacion_critica_tiene_dosis": (BOOLEANO, None),
        "alergias_graves": (BOOLEANO, None),
        "alergias_graves_detalle": (TEXTO, 200),
    },
    SECCION_EDUCACION: {
        "nivel_educativo": (OPCION, tuple(NivelEducativo.values)),
        "escuela": (TEXTO, 200),
        "asiste_escuela": (BOOLEANO, None),
    },
    SECCION_VACUNACION: {
        "esquema_al_dia": (BOOLEANO, None),
        "vacunacion_observacion": (TEXTO, 500),
    },
    SECCION_SALUD: {
        "obra_social": (TEXTO, 120),
        "enfermedades_cronicas": (TEXTO, 500),
        "medicacion_habitual": (TEXTO, 500),
    },
    SECCION_TRABAJO: {
        "ocupacion": (TEXTO, 200),
        "ingresos": (TEXTO, 200),
    },
    SECCION_OBSERVACIONES: {
        "observaciones": (TEXTO, 1000),
        "mascotas": (BOOLEANO, None),
        "adulto_responsable": (TEXTO, 200),
    },
}

#: Las tres secciones del mínimo y las cinco que se completan después, en orden.
SECCIONES_MINIMAS = (SECCION_PARENTESCO, SECCION_DATOS, SECCION_AVISOS)

SECCIONES_OPCIONALES = (
    SECCION_EDUCACION,
    SECCION_VACUNACION,
    SECCION_SALUD,
    SECCION_TRABAJO,
    SECCION_OBSERVACIONES,
)

SIN_DATOS = "sin_datos"

ROTULO_DE_SECCION = {
    SECCION_PARENTESCO: "Parentesco",
    SECCION_DATOS: "Datos personales",
    SECCION_AVISOS: "Avisos críticos de salud",
    SECCION_EDUCACION: "Educación",
    SECCION_VACUNACION: "Vacunación",
    SECCION_SALUD: "Salud y medicación",
    SECCION_TRABAJO: "Trabajo",
    SECCION_OBSERVACIONES: "Observaciones, mascotas y adulto responsable",
}

#: Las cinco preguntas de avisos críticos: las cinco tienen que estar **respondidas** (RN-3.6).
PREGUNTAS_CRITICAS = {
    "embarazo": "embarazo",
    "discapacidad": "discapacidad",
    "electrodependiente": "electrodependencia",
    "medicacion_critica": "medicación crítica",
    "alergias_graves": "alergias graves",
}

#: Desde qué edad una persona no necesita un adulto responsable en la ficha (03 §10).
EDAD_SIN_ADULTO_RESPONSABLE = 16

_VERDADERO = {"true", "1", "si", "sí", "on", "yes"}

_FALSO = {"false", "0", "no", "off"}


def _booleano(valor):
    """``True``, ``False`` o ``None`` («sin responder»). Lo que no se entiende es sin responder."""

    if isinstance(valor, bool):
        return valor
    if valor in (0, 1):
        return bool(valor)
    if isinstance(valor, str):
        texto = valor.strip().casefold()
        if texto in _VERDADERO:
            return True
        if texto in _FALSO:
            return False
    return None


def normalizar_ficha(ficha):
    """La ficha tal como se guarda: solo secciones y campos de :data:`ESQUEMA_FICHA`, tipados.

    Recibe el JSON anidado (con o sin ``version``); lo que no es del esquema se ignora, igual
    que ``crear_caso`` ignora las claves de más. Un texto vacío, un ``None`` o un booleano
    ilegible son «sin responder» y **no figuran** en lo que devuelve. Los textos van sin
    espacios exteriores; la fecha, en ISO (``AAAA-MM-DD``; acepta también ``dd/mm/aaaa``).

    Levanta ``ValidationError`` con los errores **por campo** (el nombre plano del campo) si
    un valor no es del tipo: una opción que no está en la lista, una fecha ilegible, un
    texto más largo que el tope. Es idempotente: normalizar una ficha normalizada no cambia nada.
    """

    ficha = ficha if isinstance(ficha, dict) else {}
    errores = {}
    limpia = {"version": FICHA_VERSION}
    for seccion, campos in ESQUEMA_FICHA.items():
        datos = ficha.get(seccion)
        datos = datos if isinstance(datos, dict) else {}
        armada = {}
        if seccion in SECCIONES_OPCIONALES and _booleano(datos.get(SIN_DATOS)):
            armada[SIN_DATOS] = True
        for campo, (tipo, parametro) in campos.items():
            valor = datos.get(campo)
            if tipo == BOOLEANO:
                valor = _booleano(valor)
                if valor is not None:
                    armada[campo] = valor
                continue
            if valor in (None, ""):
                continue
            if tipo == FECHA:
                fecha = fecha_o_none(valor)
                if fecha is None:
                    errores[campo] = "La fecha no es válida."
                else:
                    armada[campo] = fecha.isoformat()
                continue
            texto = str(valor).strip()
            if not texto:
                continue
            if tipo == OPCION:
                if texto not in parametro:
                    errores[campo] = "Elegí una opción de la lista."
                else:
                    armada[campo] = texto
            elif len(texto) > parametro:
                errores[campo] = f"No puede tener más de {parametro} caracteres."
            else:
                armada[campo] = texto
        limpia[seccion] = armada
    dni = limpia[SECCION_DATOS].get("dni")
    if dni:
        limpia[SECCION_DATOS]["dni"] = normalizar_dni(dni) or dni
    if errores:
        raise ValidationError(errores)
    return limpia


def ficha_minima_valida(ficha, *, hoy=None):
    """**El** validador del mínimo para confirmar a una persona con cama (RN-3.6, decisión 1 del PM).

    Devuelve la ficha normalizada, o levanta ``ValidationError`` con todo lo que falta, por
    campo. El mínimo:

    * **parentesco** (con ``parentesco_otro`` si es «Otro»);
    * **DNI** válido (número), **nombre** y **apellido**;
    * **sexo** y **fecha de nacimiento** (vale aproximada: ``fecha_nacimiento_aproximada``);
    * las **cinco preguntas** de avisos críticos **respondidas** —todas pueden ser «no»—; si
      hay medicación crítica, su nombre y si tiene dosis;
    * **adulto responsable** si la persona es menor de 16 años.

    Es una función pura: no consulta la base. ``confirmar_integrante`` le pasa la ficha ya
    completada con lo que el legajo sabe de la persona (nombre, sexo, nacimiento).
    ``hoy`` es para fijar la edad en un test.
    """

    ficha = normalizar_ficha(ficha)
    errores = {}
    parentesco, datos, avisos = (ficha[seccion] for seccion in SECCIONES_MINIMAS)

    if not parentesco.get("parentesco"):
        errores["parentesco"] = "Falta: parentesco con quien responde por la familia."
    elif parentesco["parentesco"] == Parentesco.OTRO and not parentesco.get("parentesco_otro"):
        errores["parentesco_otro"] = "Con el parentesco «Otro», indicá cuál."

    if not dni_valido(datos.get("dni")):
        errores["dni"] = SIN_NUMERO_DE_DOCUMENTO
    for campo, falta in (("nombre", "el nombre"), ("apellido", "el apellido"), ("sexo", "el sexo")):
        if not datos.get(campo):
            errores[campo] = f"Falta: {falta}."
    edad = None
    if not datos.get("fecha_nacimiento"):
        errores["fecha_nacimiento"] = "Falta: la fecha de nacimiento. Si no la sabe, cargá una aproximada y marcalo."
    else:
        edad = edad_en_anios(datos["fecha_nacimiento"], hoy)
        if edad is None or edad < 0:
            errores["fecha_nacimiento"] = "La fecha de nacimiento no puede ser futura."
            edad = None

    for campo, rotulo in PREGUNTAS_CRITICAS.items():
        if campo not in avisos:
            errores[campo] = f"Falta: avisos de salud · respondé sí o no a {rotulo}."
    if avisos.get("medicacion_critica"):
        if not avisos.get("medicacion_critica_nombre"):
            errores["medicacion_critica_nombre"] = "Falta: avisos de salud · qué medicación crítica toma."
        if "medicacion_critica_tiene_dosis" not in avisos:
            errores["medicacion_critica_tiene_dosis"] = "Falta: avisos de salud · si tiene dosis de la medicación."

    if edad is not None and edad < EDAD_SIN_ADULTO_RESPONSABLE:
        if not ficha[SECCION_OBSERVACIONES].get("adulto_responsable"):
            errores["adulto_responsable"] = (
                f"Es menor de {EDAD_SIN_ADULTO_RESPONSABLE} años: indicá el adulto responsable (sección 8)."
            )

    if errores:
        raise ValidationError(errores)
    return ficha


def secciones_incompletas(ficha):
    """Los rótulos de las secciones 4 a 8 que no tienen ni un dato ni «sin datos», en orden."""

    faltan = []
    for seccion in SECCIONES_OPCIONALES:
        datos = (ficha or {}).get(seccion) or {}
        if not datos.get(SIN_DATOS) and not any(campo != SIN_DATOS for campo in datos):
            faltan.append(ROTULO_DE_SECCION[seccion])
    return faltan


def ficha_esta_completa(ficha):
    """``ficha_completa`` (RN-3.6): cada sección tiene al menos un dato o está marcada «sin datos».

    Las tres del mínimo se dan por completas —sin ellas la persona no se confirma—; lo que
    decide son las secciones 4 a 8.
    """

    return not secciones_incompletas(ficha)


def ficha_desde_plano(datos):
    """Arma la ficha anidada desde ``{campo: valor}`` (un formulario). No valida: eso es de ``normalizar_ficha``."""

    datos = datos or {}
    ficha = {}
    for seccion, campos in ESQUEMA_FICHA.items():
        ficha[seccion] = {campo: datos[campo] for campo in campos if campo in datos}
        if seccion in SECCIONES_OPCIONALES and f"{seccion}_{SIN_DATOS}" in datos:
            ficha[seccion][SIN_DATOS] = datos[f"{seccion}_{SIN_DATOS}"]
    return ficha


def ficha_a_plano(ficha):
    """``{campo: valor}`` de una ficha guardada: los valores iniciales de un formulario."""

    plano = {}
    for seccion in ESQUEMA_FICHA:
        for campo, valor in ((ficha or {}).get(seccion) or {}).items():
            plano[f"{seccion}_{SIN_DATOS}" if campo == SIN_DATOS else campo] = valor
    return plano


#: Las dos claves que no son del Formulario 2 y viajan en la ficha: el identificador del
#: envío que **confirmó** a la persona y el del que **agregó** la fila (RU-16). No hay columna
#: para ellos en `IntegranteGrupo`, y sin migración es el único lugar donde caben.
CLAVES_DE_ENVIO = ("uuid_cliente", "uuid_cliente_alta")


def _claves_de_envio(ficha):
    return {clave: ficha[clave] for clave in CLAVES_DE_ENVIO if (ficha or {}).get(clave)}
