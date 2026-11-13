"""Etapa 3 de Emergencia: el dispositivo recibe a la familia y la aloja (03-alojar).

``DERIVADO → INGRESO_EN_CURSO → ALOJADO``: la guardia busca a la familia por DNI, acepta o
rechaza la derivación, confirma a cada persona con su ficha mínima y su cama, y cierra el
ingreso (N de N, o con diferencia). También el ingreso directo —la familia que llegó sola— y
el cierre del caso cuando egresa el último.

**Toda regla de la etapa vive acá.** La pantalla E6 del backoffice
(``programas.views.emergencia_dispositivo``) y la API de la app (PR 8) llaman a estas mismas
funciones (RU-1, RU-2): por eso ninguna recibe un ``request`` ni lee la sesión, todas toman
argumentos por nombre y devuelven la fila recién leída con lo que hace falta para armar la
respuesta. Lo que se lee —mapa de camas, filas de la familia, llegadas— está en
``programas.selectors.emergencia_alojar``.

Cómo está hecha cada función
----------------------------

1. **Alcance, antes de tocar nada** (RU-8, RU-9): ``puede_operar_dispositivo(usuario,
   dispositivo, "dispositivo.admitir")`` sobre el dispositivo **de la derivación**. Sin
   alcance, ``PermissionDenied`` y no se toma ni un candado: quien opera A no bloquea filas
   de una familia de B. La vista web lo traduce a 404 (plan C2) porque ya filtró antes; la
   API, igual.
2. Abre una transacción, **bloquea el caso y después la derivación** y decide con lo que lee
   de esas dos filas. Si ya no están como la acción necesita, :class:`EstadoCambio` (409):
   otra guardia, la mesa o el cron se adelantaron.
3. Deja ``TrazaCaso`` (RU-15) y, en aceptar, alojar y cerrar con diferencia, la novedad
   ``GENERAL`` automática de la bitácora del turno (RN-3.14). Sin turno vigente no se
   escribe y no es un error (plan R8): la traza del caso queda igual.

El orden de los candados
------------------------

El global del módulo (plan §8, R1)::

    caso → derivación → plazas (por pk) → reservas → persona

* El caso y la derivación los bloquea **este módulo**; ``estadias.py`` y
  ``reservas_derivacion.py`` no los bloquean ni los releen (contrato del PR 6). Sin JOIN, como
  en ``services.emergencia``.
* Las plazas, las reservas y la persona que ingresa los bloquean las funciones de
  ``estadias.py`` y ``reservas_derivacion.py``. Cuando una confirmación toca **dos** plazas —la cama libre que eligió la
  guardia y la de la reserva sobrante que devuelve—, acá se piden las dos de una vez
  ordenadas por pk, se libera la reserva y recién entonces se ingresa: plaza → reserva →
  persona, nunca al revés.
* El alta mínima de la persona va **antes** de las plazas: un ``INSERT`` no espera a nadie
  que tenga algo nuestro, y si choca con el mismo DNI dado de alta a la vez, espera con solo
  el caso y la derivación tomados.
* Lo último son las altas que cuelgan de la persona ya bloqueada: el ``VinculoFamiliar`` y la
  fila del integrante. El vínculo toma, por la FK, un lock **compartido** sobre la fila del
  responsable; no se le pide el exclusivo a propósito (un egreso del responsable en curso
  no tiene que esperar a esta transacción, ni al revés).
* ``aceptar_derivacion`` **no reintenta** si una cama elegida se ocupó entre la foto y el
  candado: ``ROLLBACK TO SAVEPOINT`` no suelta los locks de fila en InnoDB, y pedir un
  segundo juego de plazas con el primero todavía tomado rompería «todas de una vez, por
  pk». Falla con un mensaje claro y la guardia vuelve a tocar «Aceptar».

El egreso (RN-3.12) y por qué no forma un ciclo
-----------------------------------------------

``al_egresar_estadia`` recibe ``estadia_egresada`` **dentro** de la transacción de
``estadias.egresar_persona``, que llega con la fila de la estadía bloqueada y con locks
compartidos sobre la plaza que deja (el ``INSERT`` del movimiento la referencia). Su orden
es, entonces, *estadía → caso → integrante*: el revés del módulo, que va del caso hacia las
plazas. No forma un ciclo porque **ninguna función de este módulo espera, con el caso
tomado, algo que un egreso tenga**:

* ninguna bloquea una ``Estadia`` que ya existe (``ingresar_persona`` solo inserta);
* las plazas que piden ``aceptar``, ``cerrar_con_diferencia``, ``cancelar_ingreso`` y
  ``alojar_familia`` son las de reservas **vigentes** o camas libres, y una plaza con una
  estadía activa no tiene ni una cosa ni la otra;
* ``confirmar_integrante`` es la única que recibe una plaza de afuera, y por eso **mira sin
  candado si está ocupada antes de pedirla**: mientras el egreso no commitea, la cama se lee
  ocupada y la confirmación se rechaza sin esperar; cuando commiteó, ya no tiene locks.
* el receptor bloquea el caso **antes** de escribir al integrante, igual que
  ``completar_ficha``: los dos piden caso → integrante.

Para una estadía que no es de Emergencia el receptor hace **una** consulta y vuelve: está en
el camino de todos los egresos de Dispositivos.

La ficha individual (Formulario 2)
----------------------------------

Esquema fijo y versionado (decisión 6 del PM): :data:`ESQUEMA_FICHA` es la única definición
y :func:`normalizar_ficha` la única puerta. Ver esa constante para el JSON exacto que
guarda ``IntegranteGrupo.ficha`` y que consumen la API y la app.
"""

from dataclasses import dataclass, field
from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from core.archivos import archivos_atomicos
from core.dni import MENSAJE_DNI_INVALIDO, dni_valido, normalizar_dni
from core.edad import edad_en_anios, fecha_o_none
from core.models import Localidad
from legajos.models import Ciudadano
from legajos.models.contactos import TipoVinculo, VinculoFamiliar
from programas.models import (
    CasoEmergencia,
    Derivacion,
    Dispositivo,
    EntradaBitacora,
    Estadia,
    IntegranteGrupo,
    Plaza,
    ReservaPlaza,
    Sector,
    TrazaCaso,
)
from programas.selectors.emergencia import dispositivo_elegible
from programas.selectors.emergencia_alojar import camas_libres
from programas.senales import estadia_egresada
from programas.services.bitacora import anotar_novedad_automatica
from programas.services.dispositivos import puede_operar_dispositivo
from programas.services.emergencia import (
    DISPOSITIVO_NO_ELEGIBLE,
    EstadoCambio,
    _bloquear_caso,
    _caso_de_ese_envio,
    _como_uuid,
    _hora,
    _nombre_de,
    _trazar,
    crear_caso,
)
from programas.services.estadias import (
    AlojamientoEnLaRed,
    ingresar_persona,
    liberar_reserva,
    verificar_alojamiento_en_red,
)
from programas.services.ingreso import alta_minima_de_persona, buscar_ciudadano_por_dni
from programas.services.nombre_plaza import plaza_con_sector
from programas.services.reservas_derivacion import (
    consumir_reserva_de_derivacion,
    liberar_reservas_de_derivacion,
    reservar_plazas_de_derivacion,
)

Estado = CasoEmergencia.Estado
Origen = CasoEmergencia.Origen
Accion = TrazaCaso.Accion
Parentesco = IntegranteGrupo.Parentesco

CAP_ADMITIR = "dispositivo.admitir"

SIN_ALCANCE = "No formás parte del equipo de este dispositivo."

# ---------------------------------------------------------------------------
# Resultados de la búsqueda por DNI (03 §7, `…/buscar/?dni=`)
# ---------------------------------------------------------------------------

BUSQUEDA_DERIVACION = "DERIVACION"
BUSQUEDA_SIN_DERIVACION = "SIN_DERIVACION"
BUSQUEDA_ALOJADA = "ALOJADA"

SIN_DERIVACION = "No hay una derivación para este DNI en tu dispositivo."


class MotivoRechazo(models.TextChoices):
    """Por qué el dispositivo rechaza una derivación (M2-2, RN-3.13)."""

    SIN_PLAZAS = "SIN_PLAZAS", "Sin plazas"
    NO_CUMPLE_PERFIL = "NO_CUMPLE_PERFIL", "No cumple perfil"
    NO_LLEGO = "NO_LLEGO", "No llegó"
    OTRO = "OTRO", "Otro"


class MotivoDiferencia(models.TextChoices):
    """Por qué se alojaron menos personas que las declaradas (RN-3.9)."""

    QUEDO_CON_FAMILIARES = "QUEDO_CON_FAMILIARES", "Quedó con familiares"
    NO_LLEGO = "NO_LLEGO", "No llegó al centro"
    DERIVADO_A_SALUD = "DERIVADO_A_SALUD", "Derivado a salud"
    OTRO = "OTRO", "Otro"


SIN_PLAZAS_PARA_ACEPTAR = "Sin plazas · rechazá con motivo o liberá camas."
CAMAS_TOMADAS_MIENTRAS_ACEPTABA = (
    "Mientras aceptabas, alguien tomó una de las camas que se iban a reservar. Volvé a tocar «Aceptar»."
)
SIN_NUMERO_DE_DOCUMENTO = (
    "Sin un número de DNI válido no se puede confirmar a la persona con cama. "
    "Cerrá el ingreso con diferencia, motivo «Otro», y contá que no tiene número de documento."
)
SIN_CAMA_LIBRE = "Sin cama libre · liberá una o cerrá con diferencia."
ELEGI_UNA_CAMA = "Elegí una cama del mapa de este dispositivo."
MOTIVO_RESERVA_SOBRANTE = "Emergencia: la persona ingresó en otra cama."
MOTIVO_RESERVAS_AL_ALOJAR = "Emergencia: familia alojada, sobraron camas reservadas."
SIN_CAMAS_PARA_INGRESO_DIRECTO = (
    "No hay camas libres para ingresar a la familia. Liberá una cama o avisá a la mesa para que la derive a otro lado."
)

#: Dónde queda, dentro de ``CasoEmergencia.situacion``, lo que escribe esta etapa (sin migración).
SITUACION_ALOJAMIENTO = "alojamiento"  # sección 4 del Formulario 1 (M2-5)
SITUACION_DIFERENCIA = "diferencia"  # motivo del cierre con diferencia (RN-3.9)
SITUACION_EN_LA_PUERTA = "en_la_puerta_de"  # «Avisar a la mesa» (M2-6)


# ---------------------------------------------------------------------------
# Formulario 2: el esquema de la ficha individual
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Excepciones y resultados
# ---------------------------------------------------------------------------


def _dia_y_mes(momento):
    """«3/11», en hora local. A mano y no con ``%-d``, que no existe en Windows."""

    local = timezone.localtime(momento)
    return f"{local.day}/{local.month}"


class PersonaYaAlojada(ValidationError):
    """La persona que se quiso confirmar ya tiene una estadía abierta en la red (HU-3.3).

    Es un ``ValidationError`` (400) sobre el campo ``dni``. El mensaje nombra el otro
    dispositivo **solo si quien confirma lo puede ver** (``verificacion.dentro_del_alcance``):
    si no, dice que está alojada en otro dispositivo y a quién pedirle el egreso (RU-9).
    ``verificacion`` es la ``VerificacionAlojamiento`` de ``estadias``.
    """

    def __init__(self, ciudadano, verificacion):
        self.ciudadano = ciudadano
        self.verificacion = verificacion
        nombre = ciudadano.nombre_completo
        if verificacion.dentro_del_alcance:
            cuando = f" desde el {_dia_y_mes(verificacion.desde)}" if verificacion.desde else ""
            mensaje = (
                f"{nombre} figura alojado en {verificacion.dispositivo}{cuando}. "
                f"Pedí que lo egresen de {verificacion.dispositivo} o cerrá el ingreso con diferencia."
            )
        else:
            mensaje = (
                f"{nombre} figura alojado en otro dispositivo de la red. Pedí a la coordinación del "
                f"Programa Dispositivos que registre el egreso (clave {verificacion.clave}) "
                "o cerrá el ingreso con diferencia."
            )
        super().__init__({"dni": mensaje})


@dataclass(frozen=True)
class ResultadoBusqueda:
    """Lo que contesta :func:`buscar_por_dni` (03 §7).

    * ``resultado`` — ``DERIVACION``, ``SIN_DERIVACION`` o ``ALOJADA``.
    * ``plazas_libres`` — camas libres del dispositivo **ahora** (decide si se ofrece
      «Ingresar igual»).
    * ``derivacion`` / ``caso`` — solo con ``DERIVACION``: la derivación vigente hacia **este**
      dispositivo, con ``caso.grupo.responsable`` y ``derivada_por`` cargados.
    * ``alojada_aca`` — solo con ``ALOJADA``: si la estadía abierta es en este dispositivo.
    * ``alojada_en`` / ``alojada_desde`` — el nombre del dispositivo y desde cuándo, **solo si
      quien busca lo puede ver**; si no, vacío y ``None`` (RN-3.2, RU-9).
    * ``mensaje`` — el texto para la pantalla (RU-20). Nunca nombra un dispositivo que quien
      busca no opera.
    * ``dni`` — el DNI buscado, normalizado.
    """

    resultado: str
    dni: str
    plazas_libres: int = 0
    derivacion: Derivacion | None = None
    caso: CasoEmergencia | None = None
    alojada_aca: bool | None = None
    alojada_en: str = ""
    alojada_desde: datetime | None = None
    mensaje: str = ""


@dataclass(frozen=True)
class ResultadoAceptacion:
    """Lo que contesta :func:`aceptar_derivacion` (03 §7: ``{caso, reservadas, faltantes, integrantes}``).

    ``reservadas`` + ``faltantes`` = ``derivacion.plazas_pedidas``. ``reservas`` son las
    ``ReservaPlaza`` recién creadas, por pk de plaza; ``integrantes``, las filas de la familia
    por orden (N = ``total_declarado``). ``mensaje`` es «Reservé 5 de 7 · faltan 2 camas».
    """

    caso: CasoEmergencia
    derivacion: Derivacion
    reservadas: int
    faltantes: int
    reservas: list = field(default_factory=list)
    integrantes: list = field(default_factory=list)
    mensaje: str = ""


# ---------------------------------------------------------------------------
# Piezas internas
# ---------------------------------------------------------------------------


def _exigir_alcance(usuario, dispositivo):
    """RU-8: ``dispositivo.admitir`` sobre **este** dispositivo. Sin él, ``PermissionDenied``."""

    if dispositivo is None or not puede_operar_dispositivo(usuario, dispositivo, CAP_ADMITIR):
        raise PermissionDenied(SIN_ALCANCE)


def _dispositivo_de(derivacion, usuario):
    """El dispositivo de la derivación, con su tipo, **si quien pregunta lo opera**.

    Se lee sin candado: ``dispositivo_id`` no cambia nunca. Es la guarda de «`admitir` en A no
    toca una derivación de B aunque conozca el id»: corre antes del primer candado.
    """

    dispositivo = Dispositivo.objects.select_related("tipo").filter(pk=derivacion.dispositivo_id).first()
    _exigir_alcance(usuario, dispositivo)
    return dispositivo


def _bloquear_derivacion(pk, caso, dispositivo):
    """La derivación con ``FOR UPDATE``, recién leída. **Siempre después del caso**, sin JOIN.

    Le cuelga el caso bloqueado y el dispositivo ya leído: ``estadias`` los lee de ahí.
    """

    derivacion = Derivacion.objects.select_for_update().get(pk=pk)
    derivacion.caso = caso
    derivacion.dispositivo = dispositivo
    return derivacion


def _abrir_ingreso(caso, usuario, *estados):
    """Alcance, candados y estado de toda acción sobre un ingreso ya aceptado.

    1. Lee sin candado la **última** derivación del caso y exige alcance sobre su
       dispositivo. Sin derivación, o de otro dispositivo, ``PermissionDenied``: el mismo
       error, para no decir si el caso existe.
    2. Bloquea caso → derivación.
    3. Exige que la derivación siga ``ACEPTADA`` y el caso en uno de ``estados``; si no,
       :class:`EstadoCambio`. Quien llega acá opera el dispositivo al que el caso estuvo
       derivado, así que se le puede decir cómo quedó.

    Devuelve ``(caso, derivacion)`` bloqueados; ``derivacion.dispositivo`` trae su tipo.
    """

    pk = getattr(caso, "pk", caso)
    previa = Derivacion.objects.filter(caso_id=pk).select_related("dispositivo__tipo").order_by("-id").first()
    _exigir_alcance(usuario, previa.dispositivo if previa is not None else None)
    caso = _bloquear_caso(pk)
    derivacion = _bloquear_derivacion(previa.pk, caso, previa.dispositivo)
    if derivacion.estado != Derivacion.Estado.ACEPTADA or caso.estado not in estados:
        raise EstadoCambio(_por_que_ya_no(caso, derivacion), estado_actual=caso.estado, caso=caso)
    return caso, derivacion


def _por_que_ya_no(caso, derivacion):
    """Qué pasó con el ingreso y qué hacer (RU-20), para la pantalla que quedó vieja."""

    if caso.estado == Estado.ALOJADO:
        return f"La familia del caso {caso.numero} ya figura alojada. Recargá la pantalla."
    if caso.estado == Estado.CERRADO:
        return f"El caso {caso.numero} está cerrado. Recargá la pantalla."
    if caso.estado == Estado.INGRESO_EN_CURSO and derivacion.estado == Derivacion.Estado.ACEPTADA:
        return f"El ingreso del caso {caso.numero} ya está en curso. Recargá la pantalla."
    if derivacion.estado == Derivacion.Estado.VENCIDA:
        return (
            f"La derivación venció a las {_hora(derivacion.vence_en)}. Pedile a la mesa que vuelva a derivar "
            "o ingresala igual si tenés plazas."
        )
    if derivacion.estado == Derivacion.Estado.CANCELADA:
        return "La mesa canceló la derivación. Si la familia está en la puerta, avisale a la mesa."
    if derivacion.estado == Derivacion.Estado.RECHAZADA:
        return "La derivación ya fue rechazada o el ingreso se canceló. Buscá a la familia de nuevo."
    return f"El caso {caso.numero} ya no está para esto. Buscá a la familia de nuevo."


def _filas_de(grupo):
    """Las filas de la familia por orden, con persona y cama. **1 consulta.**"""

    return list(
        IntegranteGrupo.objects.filter(grupo_id=grupo.pk)
        .select_related("ciudadano", "estadia__plaza__sector")
        .order_by("orden")
    )


def _asegurar_filas(grupo):
    """Deja una fila de ``IntegranteGrupo`` por cada persona declarada (1 a N). Devuelve todas.

    Solo crea las que faltan: una familia que vuelve de un ingreso cancelado ya tiene las suyas.
    """

    existentes = set(IntegranteGrupo.objects.filter(grupo_id=grupo.pk).values_list("orden", flat=True))
    faltan = [orden for orden in range(1, grupo.total_declarado + 1) if orden not in existentes]
    if faltan:
        IntegranteGrupo.objects.bulk_create([IntegranteGrupo(grupo=grupo, orden=orden) for orden in faltan])
    return _filas_de(grupo)


#: Las dos claves que no son del Formulario 2 y viajan en la ficha: el identificador del
#: envío que **confirmó** a la persona y el del que **agregó** la fila (RU-16). No hay columna
#: para ellos en `IntegranteGrupo`, y sin migración es el único lugar donde caben.
CLAVES_DE_ENVIO = ("uuid_cliente", "uuid_cliente_alta")


def _claves_de_envio(ficha):
    return {clave: ficha[clave] for clave in CLAVES_DE_ENVIO if (ficha or {}).get(clave)}


def _confirmadas(filas):
    return sum(1 for fila in filas if fila.confirmada)


def _anotar_en_bitacora(dispositivo, usuario, texto, momento):
    """La novedad ``GENERAL`` automática del turno (RN-3.14). Sin turno no escribe: no es un error."""

    return anotar_novedad_automatica(
        dispositivo=dispositivo,
        tipo=EntradaBitacora.Tipo.GENERAL,
        texto=texto,
        momento=momento,
        usuario=usuario,
    )


def _devolver_a_la_mesa(caso):
    """El caso vuelve a quien lo tenía (``EN_GESTION``) o, si nadie lo tomó nunca, a la bandeja (``NUEVO``).

    Un ingreso directo no pasó por la mesa: no tiene ``tomado_por``, y un caso «en gestión»
    sin dueño no lo ve nadie.
    """

    caso.estado = Estado.EN_GESTION if caso.tomado_por_id else Estado.NUEVO
    caso.save(update_fields=["estado", "modificado"])
    return caso


def _cerrar_si_no_queda_nadie(caso, usuario, momento):
    """RN-3.12: un caso ``ALOJADO`` sin ningún integrante con estadía abierta pasa a ``CERRADO``.

    Se llama **con el caso bloqueado**. Devuelve si lo cerró. La cuenta mira la estadía y no
    ``egresado_en``: lo que decide es si alguien sigue adentro.
    """

    if caso.estado != Estado.ALOJADO:
        return False
    quedan = IntegranteGrupo.objects.filter(grupo_id=caso.grupo_id, estadia__estado=Estadia.Estado.ACTIVA).exists()
    if quedan:
        return False
    caso.estado = Estado.CERRADO
    caso.marcar("cerrado_en", momento)
    caso.motivo_cierre = CasoEmergencia.MotivoCierre.TODOS_EGRESADOS
    caso.save(update_fields=["estado", "cerrado_en", "motivo_cierre", "modificado"])
    _trazar(
        caso,
        usuario,
        Accion.CERRADO_POR_EGRESO,
        estado_anterior=Estado.ALOJADO,
        detalle="Cerrado: egresó la última persona de la familia",
    )
    return True


def _personas(cantidad):
    return "1 persona" if cantidad == 1 else f"{cantidad} personas"


def _camas(cantidad):
    return "1 cama" if cantidad == 1 else f"{cantidad} camas"


# ---------------------------------------------------------------------------
# Buscar (M2-1)
# ---------------------------------------------------------------------------


def buscar_por_dni(*, dispositivo, dni, usuario):
    """Busca a la familia por el DNI de cualquiera de sus personas (HU-3.1, RN-3.1, RN-3.2).

    Tres resultados (:class:`ResultadoBusqueda`):

    * ``DERIVACION`` — hay una derivación ``PENDIENTE`` o ``ACEPTADA`` **hacia este
      dispositivo** de un caso derivado o con ingreso en curso, cuyo responsable —o un
      integrante ya confirmado— tiene ese DNI. Gana sobre «alojada»: buscar de nuevo al
      responsable ya confirmado tiene que llevar a seguir con su familia.
    * ``ALOJADA`` — la persona tiene una estadía abierta en la red y no hay un ingreso que
      seguir. Dónde, solo si quien busca lo puede ver.
    * ``SIN_DERIVACION`` — todo lo demás, **incluida una derivación a otro dispositivo**: no
      se dice cuál ni que existe (RU-9, RU §6 n.° 2).

    Solo lectura, sin candados. Exige ``dispositivo.admitir`` sobre ``dispositivo``
    (``PermissionDenied``); un DNI que no es un DNI es ``ValidationError``.
    """

    _exigir_alcance(usuario, dispositivo)
    dni = normalizar_dni(dni)
    if not dni_valido(dni):
        raise ValidationError({"dni": MENSAJE_DNI_INVALIDO})

    libres = len(camas_libres(dispositivo))
    ciudadano = buscar_ciudadano_por_dni(dni)
    if ciudadano is None:
        return ResultadoBusqueda(BUSQUEDA_SIN_DERIVACION, dni, plazas_libres=libres, mensaje=SIN_DERIVACION)

    de_la_persona = Q(caso__grupo__responsable=ciudadano) | Q(caso__grupo__integrantes__ciudadano=ciudadano)
    derivacion = (
        Derivacion.objects.filter(
            de_la_persona,
            # La guarda de RU-9: solo lo derivado a **este** dispositivo. Es la única línea
            # que separa a la guardia de A de la familia que va a B.
            dispositivo=dispositivo,
            estado__in=Derivacion.ESTADOS_VIGENTES,
            caso__estado__in=(Estado.DERIVADO, Estado.INGRESO_EN_CURSO),
        )
        .select_related("caso__grupo__responsable", "caso__localidad", "derivada_por", "respondida_por")
        .distinct()
        .order_by("-id")
        .first()
    )
    if derivacion is not None:
        return ResultadoBusqueda(
            BUSQUEDA_DERIVACION, dni, plazas_libres=libres, derivacion=derivacion, caso=derivacion.caso
        )

    verificacion = verificar_alojamiento_en_red(ciudadano, usuario)
    if verificacion.alojada:
        aca = verificacion.dispositivo_id == dispositivo.pk
        if verificacion.dentro_del_alcance:
            mensaje = f"Alojada en {verificacion.dispositivo} desde el {_dia_y_mes(verificacion.desde)}."
        else:
            mensaje = "Alojada en otro dispositivo de la red."
        return ResultadoBusqueda(
            BUSQUEDA_ALOJADA,
            dni,
            plazas_libres=libres,
            alojada_aca=aca,
            alojada_en=verificacion.dispositivo if verificacion.dentro_del_alcance else "",
            alojada_desde=verificacion.desde if verificacion.dentro_del_alcance else None,
            mensaje=mensaje,
        )

    # RN-3.3: una derivación a este dispositivo que ya venció no se acepta, pero se cuenta por qué.
    vencida = (
        Derivacion.objects.filter(
            de_la_persona,
            dispositivo=dispositivo,
            estado=Derivacion.Estado.VENCIDA,
            caso__estado__in=(Estado.NUEVO, Estado.EN_GESTION),
        )
        .distinct()
        .order_by("-id")
        .first()
    )
    mensaje = SIN_DERIVACION
    if vencida is not None:
        mensaje = (
            f"La derivación venció a las {_hora(vencida.vence_en)}. Pedile a la mesa que vuelva a derivar "
            "o ingresala igual si tenés plazas."
        )
    return ResultadoBusqueda(BUSQUEDA_SIN_DERIVACION, dni, plazas_libres=libres, mensaje=mensaje)


# ---------------------------------------------------------------------------
# Aceptar y rechazar (M2-2)
# ---------------------------------------------------------------------------


def _exigir_pendiente(caso, derivacion):
    if derivacion.estado == Derivacion.Estado.PENDIENTE and caso.estado == Estado.DERIVADO:
        return
    if derivacion.estado == Derivacion.Estado.ACEPTADA:
        quien = _nombre_de(derivacion.respondida_por) if derivacion.respondida_por_id else "otra persona de la guardia"
        cuando = f" a las {_hora(derivacion.respondida_en)}" if derivacion.respondida_en else ""
        mensaje = f"La derivación ya la aceptó {quien}{cuando}. Recargá la pantalla para seguir con el ingreso."
    else:
        mensaje = _por_que_ya_no(caso, derivacion)
    raise EstadoCambio(mensaje, estado_actual=caso.estado, caso=caso)


@transaction.atomic
def aceptar_derivacion(*, derivacion, usuario):
    """Acepta una derivación ``PENDIENTE``: reserva las camas y abre el ingreso (HU-3.2, RN-3.3, RN-3.4).

    * Vale aunque ``vence_en`` ya haya pasado, **mientras el cron no la haya marcado
      ``VENCIDA``** (RN-3.3): la familia está en la puerta. Quien tome primero el candado
      del caso —esta función o ``vencer_derivacion``— gana, y el otro ve el estado nuevo.
    * Elige sola las camas (``selectors.emergencia_alojar.camas_libres``: el sector con más
      libres primero, por código) y reserva **hasta** ``plazas_pedidas`` con
      ``reservas_derivacion.reservar_plazas_de_derivacion``, todo o nada. Menos camas que las pedidas es
      válido y se avisa («Reservé 5 de 7 · faltan 2 camas»); con **0 libres** no se acepta
      (``ValidationError``): se rechaza con motivo o se liberan camas.
    * El caso pasa a ``INGRESO_EN_CURSO`` con ``aceptado_en``; se crean las N filas de
      ``IntegranteGrupo`` (N = ``total_declarado``) que falten; queda la traza y la novedad
      ``GENERAL`` de la bitácora.

    Si una cama elegida se ocupó entre la foto y el candado, **no reintenta** (ver el orden
    de candados del módulo): ``ValidationError`` pidiendo volver a aceptar, y no queda nada.

    Levanta ``PermissionDenied`` sin ``dispositivo.admitir`` sobre el dispositivo de la
    derivación —antes de tomar ningún candado— y :class:`EstadoCambio` si ya no está
    pendiente (otra guardia la aceptó, venció, la mesa la canceló).

    Devuelve :class:`ResultadoAceptacion`.
    """

    dispositivo = _dispositivo_de(derivacion, usuario)
    caso = _bloquear_caso(derivacion.caso_id)
    derivacion = _bloquear_derivacion(derivacion.pk, caso, dispositivo)
    _exigir_pendiente(caso, derivacion)

    libres = camas_libres(dispositivo)
    if not libres:
        raise ValidationError({"plazas": SIN_PLAZAS_PARA_ACEPTAR})

    ahora = timezone.now()
    derivacion.estado = Derivacion.Estado.ACEPTADA
    derivacion.respondida_por = usuario
    derivacion.respondida_en = ahora
    derivacion.save(update_fields=["estado", "respondida_por", "respondida_en", "modificado"])
    try:
        reservas = reservar_plazas_de_derivacion(
            derivacion=derivacion, plazas=libres[: derivacion.plazas_pedidas], usuario=usuario, momento=ahora
        )
    except ValidationError as error:
        if "plaza" in getattr(error, "error_dict", {}):
            raise ValidationError({"plazas": CAMAS_TOMADAS_MIENTRAS_ACEPTABA}) from error
        raise

    caso.estado = Estado.INGRESO_EN_CURSO
    caso.marcar("aceptado_en", ahora)
    caso.save(update_fields=["estado", "aceptado_en", "modificado"])
    integrantes = _asegurar_filas(caso.grupo)

    reservadas, pedidas = len(reservas), derivacion.plazas_pedidas
    faltantes = pedidas - reservadas
    resumen = f"{reservadas} de {_camas(pedidas)} reservadas"
    if faltantes:
        resumen = f"{resumen} · faltan {faltantes}"
    _trazar(
        caso,
        usuario,
        Accion.DERIVACION_ACEPTADA,
        estado_anterior=Estado.DERIVADO,
        detalle=f"Derivación aceptada por {dispositivo.nombre} · {resumen}",
    )
    _anotar_en_bitacora(
        dispositivo, usuario, f"Emergencia · derivación aceptada · caso N.° {caso.numero} · {resumen}", ahora
    )
    mensaje = f"Reservé {reservadas} de {pedidas}"
    mensaje = f"{mensaje} · faltan {_camas(faltantes)}" if faltantes else f"{mensaje} camas"
    return ResultadoAceptacion(
        caso=caso,
        derivacion=derivacion,
        reservadas=reservadas,
        faltantes=faltantes,
        reservas=reservas,
        integrantes=integrantes,
        mensaje=mensaje,
    )


@transaction.atomic
def rechazar_derivacion(*, derivacion, usuario, motivo, observacion=""):
    """Rechaza una derivación ``PENDIENTE`` con motivo (RN-3.13, RU-22).

    ``motivo`` es un código de :class:`MotivoRechazo`; con «Otro», ``observacion`` es
    obligatoria. La derivación queda ``RECHAZADA`` —suelta la vigencia: el caso se puede
    volver a derivar— y el caso vuelve a ``EN_GESTION`` **con el mismo operador**. La traza
    dice «Rechazado por X: sin plazas», que es lo que la mesa lee.

    ``PermissionDenied`` sin alcance sobre el dispositivo de la derivación;
    :class:`EstadoCambio` si ya no está pendiente. Devuelve la ``Derivacion``, con
    ``derivacion.caso`` como quedó.
    """

    observacion = (observacion or "").strip()
    if motivo not in MotivoRechazo.values:
        raise ValidationError({"motivo": "Elegí el motivo del rechazo."})
    if motivo == MotivoRechazo.OTRO and not observacion:
        raise ValidationError({"observacion": "Con el motivo «Otro», contá qué pasó."})

    dispositivo = _dispositivo_de(derivacion, usuario)
    caso = _bloquear_caso(derivacion.caso_id)
    derivacion = _bloquear_derivacion(derivacion.pk, caso, dispositivo)
    _exigir_pendiente(caso, derivacion)

    rotulo = MotivoRechazo(motivo).label
    derivacion.estado = Derivacion.Estado.RECHAZADA
    derivacion.motivo = rotulo
    derivacion.observacion = observacion
    derivacion.respondida_por = usuario
    derivacion.respondida_en = timezone.now()
    derivacion.save(update_fields=["estado", "motivo", "observacion", "respondida_por", "respondida_en", "modificado"])
    _devolver_a_la_mesa(caso)
    _trazar(
        caso,
        usuario,
        Accion.DERIVACION_RECHAZADA,
        estado_anterior=Estado.DERIVADO,
        detalle=f"Rechazado por {dispositivo.nombre}: {rotulo.lower()}" + (f" · {observacion}" if observacion else ""),
    )
    return derivacion


# ---------------------------------------------------------------------------
# Confirmar a una persona (M2-3, M2-4)
# ---------------------------------------------------------------------------

#: Parentesco de la ficha → tipo de vínculo del legajo, visto **desde el responsable**.
#: Quien figura como jefe/a de hogar y no es el responsable del caso queda como «Otro».
VINCULO_DE_PARENTESCO = {
    Parentesco.CONYUGE: TipoVinculo.PAREJA,
    Parentesco.HIJO: TipoVinculo.HIJO,
    Parentesco.OTRO: TipoVinculo.OTRO,
    Parentesco.JEFE: TipoVinculo.OTRO,
}


def _con_lo_del_legajo(ficha, ciudadano):
    """La ficha completada con lo que el legajo ya sabe: nombre, apellido, sexo y nacimiento.

    Solo llena lo que la guardia **no** cargó. Con la persona en el legajo, el DNI alcanza
    para identificarla: el mínimo no obliga a retipear lo que ya está.
    """

    if ciudadano is None:
        return ficha
    datos = ficha[SECCION_DATOS]
    del_legajo = {
        "nombre": ciudadano.nombre,
        "apellido": ciudadano.apellido,
        "sexo": ciudadano.genero,
        "fecha_nacimiento": ciudadano.fecha_nacimiento.isoformat() if ciudadano.fecha_nacimiento else "",
    }
    for campo, valor in del_legajo.items():
        if valor and not datos.get(campo):
            datos[campo] = valor
    return ficha


def _dar_de_alta(ficha):
    """El alta mínima del legajo, la misma del asistente de ingreso (``ingreso.alta_minima_de_persona``).

    «Perdió el documento pero sabe el número» queda como ``dni_fisico = NO_TIENE`` **solo en
    quien se da de alta acá** (hallazgo H5): a quien ya tenía legajo no se le toca.
    """

    datos = ficha[SECCION_DATOS]
    try:
        ciudadano = alta_minima_de_persona(
            {
                "dni": datos["dni"],
                "nombre": datos["nombre"],
                "apellido": datos["apellido"],
                "fecha_nacimiento": datos["fecha_nacimiento"],
                "genero": datos["sexo"],
                "telefono": datos.get("telefono", ""),
            }
        )
    except ValidationError as error:
        raise ValidationError({"nombre": error.messages}) from error
    if datos.get("documento_extraviado") and not ciudadano.dni_fisico:
        ciudadano.dni_fisico = Ciudadano.DniFisico.NO_TIENE
        ciudadano.save(update_fields=["dni_fisico", "modificado"])
    return ciudadano


def _completar_legajo(ciudadano, ficha):
    """Llena en el legajo el sexo, el nacimiento y el teléfono **que estaban vacíos**. Nunca pisa.

    El responsable se dio de alta en la etapa 1 sin sexo («lo completa la ficha de la etapa
    3»): acá se completa. Se llama con la persona ya bloqueada por el ingreso.
    """

    datos = ficha[SECCION_DATOS]
    campos = []
    if not ciudadano.genero and datos.get("sexo"):
        ciudadano.genero = datos["sexo"]
        campos.append("genero")
    if ciudadano.fecha_nacimiento is None and datos.get("fecha_nacimiento"):
        ciudadano.fecha_nacimiento = fecha_o_none(datos["fecha_nacimiento"])
        campos.append("fecha_nacimiento")
    if not ciudadano.telefono and datos.get("telefono"):
        ciudadano.telefono = datos["telefono"]
        campos.append("telefono")
    if campos:
        ciudadano.save(update_fields=[*campos, "modificado"])


def _cama_del_dispositivo(plaza, dispositivo, derivacion):
    """La cama elegida, **de este dispositivo**, con su sector. Sin candado.

    El mismo error para la que no existe y para la de otra institución, como
    ``estadias._bloquear_plaza``. Y los dos rechazos que se pueden dar sin esperar a nadie:
    fuera de servicio (03 §10) y ocupada. El de «ocupada» es además lo que impide el ciclo
    con un egreso en curso (ver el docstring del módulo): se mira **antes** de pedir el
    candado de la plaza.
    """

    pk = plaza.pk if isinstance(plaza, Plaza) else plaza
    cama = None
    if pk not in (None, ""):
        try:
            cama = (
                Plaza.objects.filter(pk=int(pk), sector__dispositivo_id=dispositivo.pk, tipo=Plaza.Tipo.CAMA)
                .select_related("sector")
                .first()
            )
        except (TypeError, ValueError):
            cama = None
    if cama is None:
        if pk in (None, "") and not _hay_cama_para_elegir(dispositivo, derivacion):
            # HU-3.5: la fila existe, pero no hay dónde alojar a la persona.
            raise ValidationError({"plaza": SIN_CAMA_LIBRE})
        raise ValidationError({"plaza": ELEGI_UNA_CAMA})
    nombre = plaza_con_sector(cama, cama.sector.nombre)
    if cama.estado == Plaza.Estado.FUERA_SERVICIO:
        raise ValidationError({"plaza": f"La cama {nombre} está fuera de servicio · elegí otra."})
    if not cama.sector.activo:
        raise ValidationError({"plaza": f"El sector de la cama {nombre} está dado de baja · elegí otra."})
    if Estadia.objects.activas().filter(plaza_id=cama.pk).exists():
        raise ValidationError({"plaza": f"La cama {nombre} ya está ocupada · elegí otra."})
    return cama


def _hay_cama_para_elegir(dispositivo, derivacion):
    """¿Queda alguna cama guardada para la familia, o alguna libre?"""

    return ReservaPlaza.objects.abiertas().filter(derivacion_id=derivacion.pk).exists() or bool(
        camas_libres(dispositivo)
    )


def _vincular_con_el_responsable(grupo, ciudadano, parentesco, caso):
    """El ``VinculoFamiliar`` entre el responsable y quien se confirma, según el parentesco (RN-3.7).

    Visto desde el responsable («su hijo/a es…»), marcado como conviviente. Si el vínculo ya
    existía en el legajo no se duplica ni se modifica.
    """

    VinculoFamiliar.objects.get_or_create(
        ciudadano_principal_id=grupo.responsable_id,
        ciudadano_vinculado=ciudadano,
        tipo_vinculo=VINCULO_DE_PARENTESCO[parentesco],
        defaults={"convive": True, "observaciones": f"Declarado al alojar · Emergencia caso N.° {caso.numero}"},
    )


def _ya_confirmada_en(filas, integrante, dni):
    """Si otra fila de la familia ya tiene a esa persona, el error que lo dice (03 §10)."""

    for otra in filas:
        if otra.pk == integrante.pk or not otra.ciudadano_id or normalizar_dni(otra.ciudadano.dni) != dni:
            continue
        nombre = otra.ciudadano.nombre_completo
        if otra.estadia_id and otra.estadia.plaza_id and otra.egresado_en is None:
            cama = plaza_con_sector(otra.estadia.plaza, otra.estadia.plaza.sector.nombre)
            return ValidationError({"dni": f"Ya confirmaste a {nombre} en la cama {cama}."})
        return ValidationError({"dni": f"Ya confirmaste a {nombre} en esta familia (persona {otra.orden})."})
    return None


def _error_de_cama(error, cama):
    """El rechazo de ``estadias`` sobre la plaza, dicho con el nombre de la cama y qué hacer."""

    detalle = getattr(error, "error_dict", {})
    if not ({"plaza", "reserva"} & set(detalle)):
        return error
    nombre = plaza_con_sector(cama, cama.sector.nombre)
    mensajes = " ".join(error.messages)
    return ValidationError({"plaza": f"Cama {nombre}: {mensajes} Recargá el mapa y elegí otra."})


@transaction.atomic
def confirmar_integrante(*, caso, orden, usuario, ficha, plaza, uuid_cliente=None):
    """Confirma a la persona ``orden`` de la familia con su ficha mínima y su cama (HU-3.3, RN-3.5 a 3.7).

    **Una sola transacción**: si cualquier paso falla —en particular el ingreso— no queda ni
    el legajo recién dado de alta, ni el vínculo familiar, ni la fila confirmada.

    1. Bloquea caso → derivación; el caso tiene que estar en ``INGRESO_EN_CURSO``.
    2. Valida el **mínimo** (:func:`ficha_minima_valida`), completando antes con lo que el
       legajo sabe si la persona ya existe. Sin número de DNI no se confirma (D-10): se
       cierra con diferencia.
    3. La misma persona dos veces en la familia es un error que dice dónde está.
    4. Resuelve el ``Ciudadano`` por DNI, o le da el alta mínima.
    5. La cama (``plaza``: instancia o id, del dispositivo de la derivación):

       * **reservada para esta familia** → ``reservas_derivacion.consumir_reserva_de_derivacion``: la
         reserva pasa a nombre de quien entra y queda ``CONSUMIDA``;
       * **libre, sin reserva** (la familia creció o la guardia cambió la cama) →
         ``estadias.ingresar_persona`` directo. Regla de la reserva sobrante: **la
         derivación nunca retiene más camas que personas faltan confirmar**. Si después de
         esta confirmación quedarían más reservas vigentes que personas sin confirmar, se
         libera **una** —la de la plaza con id más alto— en esta misma transacción, antes
         del ingreso. Si todavía hacen falta todas (reservó 5 de 7), no se libera ninguna;
       * reservada para otra persona, ocupada o fuera de servicio → ``ValidationError``
         sobre ``plaza`` diciendo cuál y que elija otra.

    6. Una persona con estadía abierta en la red → :class:`PersonaYaAlojada`.
    7. Crea el ``VinculoFamiliar`` con el responsable según el parentesco (si quien se
       confirma **es** el responsable, no), completa en el legajo lo que estaba vacío y
       guarda en la fila ``ciudadano``, ``estadia``, ``ficha``, ``ficha_completa`` y
       ``confirmada_en``. El ``INGRESO`` de la bitácora lo deja ``ingresar_persona``.

    ``uuid_cliente`` (opcional, RU-16) queda en la ficha: reenviar la misma confirmación
    devuelve la fila tal cual, con ``integrante.ya_estaba = True``. Una fila ya confirmada
    por otro envío es :class:`EstadoCambio` (otra guardia se adelantó: recargar).

    Devuelve el ``IntegranteGrupo`` con ``ya_estaba``, ``confirmadas``, ``total_declarado`` y
    ``reserva_liberada`` (si devolvió una cama sobrante) como atributos.
    """

    caso, derivacion = _abrir_ingreso(caso, usuario, Estado.INGRESO_EN_CURSO)
    dispositivo = derivacion.dispositivo
    grupo = caso.grupo
    filas = _filas_de(grupo)
    integrante = next((fila for fila in filas if fila.orden == orden), None)
    if integrante is None:
        raise ValidationError({"orden": "Esa persona no es de esta familia. Recargá la lista."})
    uuid_cliente = _como_uuid(uuid_cliente)

    if integrante.confirmada:
        if uuid_cliente is not None and integrante.ficha.get("uuid_cliente") == str(uuid_cliente):
            integrante.ya_estaba = True
            integrante.confirmadas, integrante.total_declarado = _confirmadas(filas), grupo.total_declarado
            integrante.reserva_liberada = False
            return integrante
        raise EstadoCambio(
            f"La persona {orden} ya fue confirmada. Recargá la lista.", estado_actual=caso.estado, caso=caso
        )

    ficha = normalizar_ficha(ficha)
    dni = ficha[SECCION_DATOS].get("dni")
    if not dni_valido(dni):
        raise ValidationError({"dni": SIN_NUMERO_DE_DOCUMENTO})
    repetida = _ya_confirmada_en(filas, integrante, dni)
    if repetida is not None:
        raise repetida
    existente = buscar_ciudadano_por_dni(dni)
    ficha = ficha_minima_valida(_con_lo_del_legajo(ficha, existente))
    cama = _cama_del_dispositivo(plaza, dispositivo, derivacion)

    # La reserva que toma esa cama, leída sin candado: decide el camino. `reservas_derivacion` la
    # vuelve a leer bloqueada, y si cambió en el medio falla con su propio error. Que sea de
    # **esta** derivación se mira acá: `consumir_reserva_de_derivacion` no recibe la derivación y
    # acepta la de cualquiera (`derivacion_id` no cambia nunca, así que leerlo sin candado alcanza).
    reserva = ReservaPlaza.objects.que_toman().filter(plaza_id=cama.pk).order_by("id").first()
    if reserva is not None and reserva.derivacion_id != derivacion.pk:
        raise ValidationError(
            {
                "plaza": f"La cama {plaza_con_sector(cama, cama.sector.nombre)} "
                "está reservada para otra persona · elegí otra."
            }
        )

    # El alta, antes de las plazas (ver el orden de candados del módulo).
    ciudadano = existente if existente is not None else _dar_de_alta(ficha)

    reserva_liberada = False
    try:
        if reserva is not None:
            estadia = consumir_reserva_de_derivacion(reserva=reserva, ciudadano=ciudadano, usuario=usuario)
        else:
            por_confirmar_despues = max(grupo.total_declarado - _confirmadas(filas) - 1, 0)
            vigentes = list(ReservaPlaza.objects.abiertas().filter(derivacion_id=derivacion.pk).order_by("plaza_id"))
            sobrante = vigentes[-1] if len(vigentes) > por_confirmar_despues else None
            if sobrante is not None:
                # Las dos plazas de una vez y por pk; después la reserva; la persona, al final.
                list(
                    Plaza.objects.select_for_update()
                    .filter(pk__in={cama.pk, sobrante.plaza_id})
                    .order_by("pk")
                    .values_list("pk", flat=True)
                )
                try:
                    liberar_reserva(reserva=sobrante, usuario=usuario, motivo=MOTIVO_RESERVA_SOBRANTE)
                    reserva_liberada = True
                except ValidationError:
                    pass  # la liberaron desde el mapa en el medio: ya no retiene nada
            estadia = ingresar_persona(ciudadano=ciudadano, dispositivo=dispositivo, usuario=usuario, plaza=cama)
    except AlojamientoEnLaRed as error:
        raise PersonaYaAlojada(ciudadano, error.verificacion) from error
    except ValidationError as error:
        raise _error_de_cama(error, cama) from error

    parentesco = ficha[SECCION_PARENTESCO]["parentesco"]
    if ciudadano.pk != grupo.responsable_id:
        _vincular_con_el_responsable(grupo, ciudadano, parentesco, caso)
    _completar_legajo(ciudadano, ficha)

    ficha.update(_claves_de_envio(integrante.ficha))
    if uuid_cliente is not None:
        ficha["uuid_cliente"] = str(uuid_cliente)
    ahora = timezone.now()
    integrante.ciudadano = ciudadano
    integrante.parentesco = parentesco
    integrante.parentesco_otro = ficha[SECCION_PARENTESCO].get("parentesco_otro", "")
    integrante.estadia = estadia
    integrante.ficha = ficha
    integrante.ficha_completa = ficha_esta_completa(ficha)
    integrante.confirmada_en = ahora
    integrante.save(
        update_fields=[
            "ciudadano",
            "parentesco",
            "parentesco_otro",
            "estadia",
            "ficha",
            "ficha_completa",
            "confirmada_en",
            "modificado",
        ]
    )

    confirmadas = _confirmadas(filas)  # la fila es la misma instancia que está en `filas`
    _trazar(
        caso,
        usuario,
        Accion.INTEGRANTE_CONFIRMADO,
        estado_anterior=caso.estado,
        detalle=(
            f"Persona {orden} confirmada · cama {plaza_con_sector(cama, cama.sector.nombre)} · "
            f"{confirmadas} de {grupo.total_declarado}"
        ),
    )
    integrante.ya_estaba = False
    integrante.confirmadas, integrante.total_declarado = confirmadas, grupo.total_declarado
    integrante.reserva_liberada = reserva_liberada
    return integrante


@transaction.atomic
def completar_ficha(*, caso, orden, usuario, ficha):
    """Completa las secciones 4 a 8 de una persona **ya confirmada** (M2-3, E6-integrantes).

    Vale con el ingreso en curso y con la familia ya alojada. ``ficha`` trae las secciones
    que se cargan (anidadas, como en :data:`ESQUEMA_FICHA`): cada sección **que viene**
    reemplaza a la guardada; las que no vienen, y las tres del mínimo —la identidad no se
    cambia después de confirmar—, quedan como estaban. Recalcula ``ficha_completa``.

    Un menor de 16 no puede quedar sin adulto responsable: se revalida el mínimo.

    Devuelve el ``IntegranteGrupo``.
    """

    caso, _derivacion = _abrir_ingreso(caso, usuario, Estado.INGRESO_EN_CURSO, Estado.ALOJADO)
    integrante = IntegranteGrupo.objects.filter(grupo_id=caso.grupo_id, orden=orden).first()
    if integrante is None:
        raise ValidationError({"orden": "Esa persona no es de esta familia. Recargá la lista."})
    if not integrante.confirmada:
        raise ValidationError({"orden": f"Primero confirmá a la persona {orden} con su cama."})

    ficha = ficha if isinstance(ficha, dict) else {}
    nueva = dict(integrante.ficha)
    for seccion in SECCIONES_OPCIONALES:
        if seccion in ficha:
            nueva[seccion] = ficha[seccion]
    nueva = ficha_minima_valida(nueva)
    nueva.update(_claves_de_envio(integrante.ficha))
    integrante.ficha = nueva
    integrante.ficha_completa = ficha_esta_completa(nueva)
    integrante.save(update_fields=["ficha", "ficha_completa", "modificado"])
    _trazar(
        caso,
        usuario,
        Accion.FICHA_ACTUALIZADA,
        estado_anterior=caso.estado,
        detalle=f"Ficha de la persona {orden} · {'completa' if integrante.ficha_completa else 'incompleta'}",
    )
    return integrante


@transaction.atomic
def agregar_integrante(*, caso, usuario, uuid_cliente=None):
    """Suma una persona que no estaba declarada (HU-3.5, RN-3.8).

    ``total_declarado`` crece en uno y aparece una fila nueva, sin confirmar. No reserva
    cama: al confirmarla se elige entre las libres, y si no hay ninguna la confirmación lo
    dice («Sin cama libre · liberá una o cerrá con diferencia»). La traza cuenta «N sobre M
    declaradas», con M lo que dijo el Formulario 1.

    ``uuid_cliente`` (opcional, RU-16) queda en la ficha de la fila nueva: reenviarlo
    devuelve esa misma fila, con ``integrante.ya_estaba = True``, sin sumar otra.

    Devuelve el ``IntegranteGrupo`` nuevo, con ``ya_estaba`` y ``total_declarado``.
    """

    caso, _derivacion = _abrir_ingreso(caso, usuario, Estado.INGRESO_EN_CURSO)
    grupo = caso.grupo
    uuid_cliente = _como_uuid(uuid_cliente)
    filas = _filas_de(grupo)
    if uuid_cliente is not None:
        for fila in filas:
            if fila.ficha.get("uuid_cliente_alta") == str(uuid_cliente):
                fila.ya_estaba, fila.total_declarado = True, grupo.total_declarado
                return fila

    grupo.total_declarado += 1
    grupo.save(update_fields=["total_declarado", "modificado"])
    integrante = IntegranteGrupo.objects.create(
        grupo=grupo,
        orden=max((fila.orden for fila in filas), default=0) + 1,
        ficha={"uuid_cliente_alta": str(uuid_cliente)} if uuid_cliente is not None else {},
    )
    _trazar(
        caso,
        usuario,
        Accion.INTEGRANTE_AGREGADO,
        estado_anterior=caso.estado,
        detalle=(
            f"Agregada persona por el dispositivo · {grupo.total_declarado} sobre "
            f"{grupo.suma_de_cantidades()} declaradas"
        ),
    )
    integrante.ya_estaba, integrante.total_declarado = False, grupo.total_declarado
    return integrante


# ---------------------------------------------------------------------------
# Cerrar el ingreso (M2-5, RN-3.9)
# ---------------------------------------------------------------------------


def _sector_del_dispositivo(sector, dispositivo):
    """``(id, nombre)`` del sector/ala elegido, que tiene que ser del dispositivo; ``(None, "")`` sin él."""

    if sector in (None, ""):
        return None, ""
    pk = sector.pk if isinstance(sector, Sector) else sector
    try:
        fila = Sector.objects.filter(pk=int(pk), dispositivo_id=dispositivo.pk).values_list("pk", "nombre").first()
    except (TypeError, ValueError):
        fila = None
    if fila is None:
        raise ValidationError({"sector": "Elegí un sector de este dispositivo."})
    return fila


@transaction.atomic
def alojar_familia(*, caso, usuario, sector=None, aula="", tarjeta_entregada=False, tarjeta_numero="", encargado=""):
    """«Familia alojada»: cierra el ingreso con **N de N** confirmadas (M2-5).

    Exige que **todas** las filas de la familia estén confirmadas; con una sola sin
    confirmar, ``ValidationError`` (lo que corresponde es confirmarla o cerrar con
    diferencia). Guarda la sección 4 del Formulario 1 en ``caso.situacion["alojamiento"]``::

        {"sector_id": 3, "sector": "Pabellón A", "aula": "Aula 3",
         "tarjeta_entregada": true, "tarjeta_numero": "0042", "encargado": "Ana López"}

    ``sector`` es un ``Sector`` del dispositivo o su id (opcional); con la tarjeta entregada,
    su número es obligatorio; ``encargado`` es quien recibe (por omisión, quien aloja).

    El caso pasa a ``ALOJADO`` con ``alojado_en`` y ``total_alojado``; las reservas de la
    derivación que hubieran sobrado se liberan (la mesa pudo pedir más camas que personas);
    queda la traza y la novedad ``GENERAL`` «familia alojada 7 de 7».

    Devuelve el ``CasoEmergencia``, con ``caso.reservas_liberadas``.
    """

    caso, derivacion = _abrir_ingreso(caso, usuario, Estado.INGRESO_EN_CURSO)
    dispositivo = derivacion.dispositivo
    grupo = caso.grupo
    filas = _filas_de(grupo)
    confirmadas = _confirmadas(filas)
    if confirmadas < grupo.total_declarado or confirmadas < len(filas) or not confirmadas:
        faltan = max(grupo.total_declarado, len(filas)) - confirmadas
        raise ValidationError(
            f"Falta confirmar a {_personas(faltan)}. Confirmalas, o cerrá el ingreso con diferencia si no llegaron."
        )

    aula = (aula or "").strip()
    tarjeta_numero = (tarjeta_numero or "").strip()
    encargado = (encargado or "").strip() or _nombre_de(usuario)
    errores = {}
    if len(aula) > 80:
        errores["aula"] = "No puede tener más de 80 caracteres."
    if tarjeta_entregada and not tarjeta_numero:
        errores["tarjeta_numero"] = "Indicá el número de la tarjeta familiar entregada."
    if len(tarjeta_numero) > 40:
        errores["tarjeta_numero"] = "No puede tener más de 40 caracteres."
    if len(encargado) > 120:
        errores["encargado"] = "No puede tener más de 120 caracteres."
    if errores:
        raise ValidationError(errores)
    sector_id, sector_nombre = _sector_del_dispositivo(sector, dispositivo)

    ahora = timezone.now()
    liberadas = liberar_reservas_de_derivacion(derivacion=derivacion, usuario=usuario, motivo=MOTIVO_RESERVAS_AL_ALOJAR)
    caso.estado = Estado.ALOJADO
    caso.marcar("alojado_en", ahora)
    caso.total_alojado = confirmadas
    caso.situacion = {
        **caso.situacion,
        SITUACION_ALOJAMIENTO: {
            "sector_id": sector_id,
            "sector": sector_nombre,
            "aula": aula,
            "tarjeta_entregada": bool(tarjeta_entregada),
            "tarjeta_numero": tarjeta_numero if tarjeta_entregada else "",
            "encargado": encargado,
        },
    }
    caso.save(update_fields=["estado", "alojado_en", "total_alojado", "situacion", "modificado"])
    donde = " · ".join(parte for parte in (sector_nombre, aula) if parte)
    resumen = f"{confirmadas} de {grupo.total_declarado}"
    _trazar(
        caso,
        usuario,
        Accion.ALOJADO,
        estado_anterior=Estado.INGRESO_EN_CURSO,
        detalle=f"Familia alojada en {dispositivo.nombre} · {resumen}" + (f" · {donde}" if donde else ""),
    )
    _anotar_en_bitacora(dispositivo, usuario, f"Emergencia · familia alojada {resumen} · caso N.° {caso.numero}", ahora)
    caso.reservas_liberadas = liberadas
    _cerrar_si_no_queda_nadie(caso, usuario, ahora)
    return caso


@transaction.atomic
def cerrar_con_diferencia(*, caso, usuario, motivo, observacion=""):
    """Cierra el ingreso con **menos personas que las declaradas** (HU-3.4, RN-3.9, RU-22).

    Requiere al menos una confirmada y un ``motivo`` de :class:`MotivoDiferencia`; con «Otro»
    (es el de «no tiene número de documento», D-10) la ``observacion`` es obligatoria. Con
    todas confirmadas no hay diferencia: se usa ``alojar_familia``.

    ``total_alojado`` = confirmadas; las reservas sobrantes de la derivación pasan a
    ``LIBERADA``; el caso queda ``ALOJADO`` —es el estado de «la familia está acá»— con la
    marca parcial (``caso.ingreso_parcial``). El motivo queda en la traza y en
    ``caso.situacion["diferencia"]``::

        {"motivo": "NO_LLEGO", "motivo_texto": "No llegó al centro", "observacion": "…",
         "confirmadas": 5, "declaradas": 7}

    Deja la novedad ``GENERAL`` de la bitácora con el motivo.

    Devuelve el ``CasoEmergencia``, con ``caso.reservas_liberadas``.
    """

    observacion = (observacion or "").strip()
    if motivo not in MotivoDiferencia.values:
        raise ValidationError({"motivo": "Elegí por qué llegaron menos personas."})
    if motivo == MotivoDiferencia.OTRO and not observacion:
        raise ValidationError({"observacion": "Con el motivo «Otro», contá qué pasó."})

    caso, derivacion = _abrir_ingreso(caso, usuario, Estado.INGRESO_EN_CURSO)
    dispositivo = derivacion.dispositivo
    grupo = caso.grupo
    confirmadas = IntegranteGrupo.objects.filter(grupo_id=grupo.pk, confirmada_en__isnull=False).count()
    if confirmadas < 1:
        raise ValidationError(
            "Todavía no confirmaste a nadie. Si la familia no llegó, cancelá el ingreso para devolverle el caso a la mesa."
        )
    if confirmadas >= grupo.total_declarado:
        raise ValidationError("Están todas las personas confirmadas: no hay diferencia. Usá «Familia alojada».")

    ahora = timezone.now()
    rotulo = MotivoDiferencia(motivo).label
    liberadas = liberar_reservas_de_derivacion(
        derivacion=derivacion, usuario=usuario, motivo=f"Emergencia: ingreso cerrado con diferencia ({rotulo.lower()})."
    )
    caso.estado = Estado.ALOJADO
    caso.marcar("alojado_en", ahora)
    caso.total_alojado = confirmadas
    caso.situacion = {
        **caso.situacion,
        SITUACION_DIFERENCIA: {
            "motivo": motivo,
            "motivo_texto": rotulo,
            "observacion": observacion,
            "confirmadas": confirmadas,
            "declaradas": grupo.total_declarado,
        },
    }
    caso.save(update_fields=["estado", "alojado_en", "total_alojado", "situacion", "modificado"])
    resumen = f"{confirmadas} de {grupo.total_declarado}"
    _trazar(
        caso,
        usuario,
        Accion.ALOJADO_CON_DIFERENCIA,
        estado_anterior=Estado.INGRESO_EN_CURSO,
        detalle=(
            f"Ingreso parcial en {dispositivo.nombre} · {resumen} · {rotulo}"
            + (f" · {observacion}" if observacion else "")
        ),
    )
    # La bitácora la lee quien tiene `dispositivo.ver`: va el motivo del catálogo, no la observación libre.
    _anotar_en_bitacora(
        dispositivo,
        usuario,
        f"Emergencia · ingreso cerrado con diferencia {resumen} · {rotulo.lower()} · caso N.° {caso.numero}",
        ahora,
    )
    caso.reservas_liberadas = liberadas
    _cerrar_si_no_queda_nadie(caso, usuario, ahora)
    return caso


@transaction.atomic
def cancelar_ingreso(*, caso, usuario, motivo):
    """Cancela un ingreso aceptado en el que **no se confirmó a nadie** (03 §5).

    ``motivo`` es un texto obligatorio (hasta 200 caracteres). Las reservas de la derivación
    se liberan, la derivación queda ``RECHAZADA`` con ese motivo y el caso vuelve a la mesa:
    a ``EN_GESTION`` con el mismo operador, o a la bandeja (``NUEVO``) si nadie lo había
    tomado —un ingreso directo—. Las filas de la familia quedan, sin confirmar.

    Con una sola persona confirmada no se cancela: se cierra con diferencia.

    Devuelve el ``CasoEmergencia``, con ``caso.reservas_liberadas``.
    """

    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError({"motivo": "Indicá por qué se cancela el ingreso."})
    if len(motivo) > 200:
        raise ValidationError({"motivo": "El motivo no puede tener más de 200 caracteres."})

    caso, derivacion = _abrir_ingreso(caso, usuario, Estado.INGRESO_EN_CURSO)
    dispositivo = derivacion.dispositivo
    if IntegranteGrupo.objects.filter(grupo_id=caso.grupo_id, confirmada_en__isnull=False).exists():
        raise ValidationError("Ya hay personas confirmadas con cama: cerrá el ingreso con diferencia.")

    liberadas = liberar_reservas_de_derivacion(
        derivacion=derivacion, usuario=usuario, motivo="Emergencia: ingreso cancelado."
    )
    derivacion.estado = Derivacion.Estado.RECHAZADA
    derivacion.motivo = motivo
    derivacion.respondida_por = usuario
    derivacion.respondida_en = timezone.now()
    derivacion.save(update_fields=["estado", "motivo", "respondida_por", "respondida_en", "modificado"])
    _devolver_a_la_mesa(caso)
    _trazar(
        caso,
        usuario,
        Accion.INGRESO_CANCELADO,
        estado_anterior=Estado.INGRESO_EN_CURSO,
        detalle=f"Ingreso cancelado por {dispositivo.nombre}: {motivo}",
    )
    caso.reservas_liberadas = liberadas
    return caso


# ---------------------------------------------------------------------------
# Sin derivación: ingreso directo y aviso a la mesa (M2-6)
# ---------------------------------------------------------------------------


def _formulario1_en_el_dispositivo(datos_formulario1, dispositivo):
    """El Formulario 1 con lo que se sabe por estar **en** el dispositivo (RN-3.10).

    La dirección y la localidad son opcionales acá: sin dirección va el domicilio del
    dispositivo (o «Se presentó en X»), y sin localidad la del dispositivo, **si** su texto
    coincide con exactamente una ``core.Localidad``.
    """

    datos = dict(datos_formulario1 or {})
    if not str(datos.get("direccion") or "").strip():
        datos["direccion"] = (dispositivo.domicilio or f"Se presentó en {dispositivo.nombre}")[:240]
    if datos.get("localidad") in (None, "") and dispositivo.localidad:
        candidatas = list(Localidad.objects.filter(nombre__iexact=dispositivo.localidad)[:2])
        if len(candidatas) == 1:
            datos["localidad"] = candidatas[0]
    return datos


def _con_sus_reservas(caso):
    """Le cuelga ``reservadas`` y ``faltantes`` a un caso que ya existía (el reenvío de un ingreso directo).

    Son las camas que el ingreso reservó **al crearse** —vigentes, consumidas o liberadas
    después— contra las que pidió: lo mismo que contestó el primer envío.
    """

    derivacion = Derivacion.objects.filter(caso_id=caso.pk).order_by("id").first()
    pedidas = derivacion.plazas_pedidas if derivacion is not None else 0
    reservadas = ReservaPlaza.objects.filter(derivacion=derivacion).count() if derivacion is not None else 0
    caso.reservadas, caso.faltantes = reservadas, max(pedidas - reservadas, 0)
    return caso


@archivos_atomicos
@transaction.atomic
def ingreso_directo(*, dispositivo, usuario, datos_formulario1, uuid_cliente=None):
    """«Ingresar igual»: la familia llegó sola y el dispositivo la recibe sin pasar por la mesa (HU-3.6, RN-3.10).

    Exige ``dispositivo.admitir`` sobre **ese** dispositivo, que sea elegible para alojar
    familias y que tenga **al menos una cama libre**. En una transacción:

    * crea el caso con ``crear_caso(origen=DISPOSITIVO)`` —misma validación del Formulario 1,
      con dirección y localidad opcionales—;
    * crea una ``Derivacion`` ``ACEPTADA`` hacia el propio dispositivo, para que todo lo que
      sigue (confirmar, alojar, diferencia, egreso) sea el mismo camino;
    * reserva camas para la familia **hasta donde alcance** y crea sus N filas;
    * deja el caso en ``INGRESO_EN_CURSO`` con ``tomado_en = derivado_en = aceptado_en =
      creado``: el tramo de la mesa vale 0 y el tablero lo separa como ingreso directo.

    **Idempotente** por ``uuid_cliente`` (RU-16; es lo único de la etapa que la app encola
    sin conexión): reenviarlo devuelve el mismo caso, con ``caso.ya_existia = True``, sin
    reservar de nuevo ni mirar si hoy hay camas.

    Devuelve el ``CasoEmergencia`` con ``ya_existia``, ``reservadas`` y ``faltantes``.
    """

    _exigir_alcance(usuario, dispositivo)
    uuid_cliente = _como_uuid(uuid_cliente)
    if uuid_cliente is not None:
        existente = _caso_de_ese_envio(uuid_cliente, usuario)
        if existente is not None:
            return _con_sus_reservas(existente)
    if not dispositivo_elegible(dispositivo):
        raise ValidationError({"dispositivo": DISPOSITIVO_NO_ELEGIBLE})
    libres = camas_libres(dispositivo)
    if not libres:
        raise ValidationError({"plazas": SIN_CAMAS_PARA_INGRESO_DIRECTO})

    caso = crear_caso(
        usuario=usuario,
        origen=Origen.DISPOSITIVO,
        datos_formulario1=_formulario1_en_el_dispositivo(datos_formulario1, dispositivo),
        uuid_cliente=uuid_cliente,
    )
    if caso.ya_existia:  # el mismo envío llegó dos veces a la vez: lo creó el otro
        return _con_sus_reservas(caso)
    caso = _bloquear_caso(caso)
    grupo = caso.grupo
    momento = caso.creado
    derivacion = Derivacion(
        caso=caso,
        dispositivo=dispositivo,
        estado=Derivacion.Estado.ACEPTADA,
        plazas_pedidas=grupo.total_declarado,
        vence_en=momento,
        derivada_por=usuario,
        respondida_por=usuario,
        respondida_en=momento,
    )
    derivacion.save()
    try:
        reservas = reservar_plazas_de_derivacion(
            derivacion=derivacion, plazas=libres[: grupo.total_declarado], usuario=usuario, momento=momento
        )
    except ValidationError as error:
        if "plaza" in getattr(error, "error_dict", {}):
            raise ValidationError({"plazas": CAMAS_TOMADAS_MIENTRAS_ACEPTABA}) from error
        raise

    caso.estado = Estado.INGRESO_EN_CURSO
    for marca in ("tomado_en", "derivado_en", "aceptado_en"):
        caso.marcar(marca, momento)
    caso.save(update_fields=["estado", "tomado_en", "derivado_en", "aceptado_en", "modificado"])
    _asegurar_filas(grupo)

    reservadas = len(reservas)
    faltantes = grupo.total_declarado - reservadas
    resumen = f"{reservadas} de {_camas(grupo.total_declarado)} reservadas"
    if faltantes:
        resumen = f"{resumen} · faltan {faltantes}"
    _trazar(
        caso,
        usuario,
        Accion.INGRESO_DIRECTO,
        estado_anterior=Estado.NUEVO,
        detalle=f"Ingreso directo en {dispositivo.nombre}, sin pasar por la mesa · {resumen}",
    )
    _anotar_en_bitacora(
        dispositivo, usuario, f"Emergencia · ingreso directo · caso N.° {caso.numero} · {resumen}", timezone.now()
    )
    caso.ya_existia = False
    caso.reservadas, caso.faltantes = reservadas, faltantes
    return caso


@archivos_atomicos
@transaction.atomic
def avisar_a_la_mesa(*, dispositivo, usuario, datos_formulario1, uuid_cliente=None):
    """«Avisar a la mesa»: la familia está en la puerta y no hay derivación (M2-6, 03 §10).

    Crea un caso ``NUEVO`` de origen ``DISPOSITIVO`` —la mesa lo ve en la bandeja y lo deriva
    a donde corresponda— con la marca «En la puerta de X» en
    ``caso.situacion["en_la_puerta_de"]``::

        {"dispositivo_id": 12, "dispositivo": "Club Sarmiento"}

    No reserva nada ni exige camas libres: es justo lo que se usa cuando no hay lugar.
    Exige ``dispositivo.admitir`` sobre ese dispositivo. Idempotente por ``uuid_cliente``.

    Devuelve el ``CasoEmergencia`` con ``ya_existia``.
    """

    _exigir_alcance(usuario, dispositivo)
    caso = crear_caso(
        usuario=usuario,
        origen=Origen.DISPOSITIVO,
        datos_formulario1=_formulario1_en_el_dispositivo(datos_formulario1, dispositivo),
        uuid_cliente=uuid_cliente,
    )
    if caso.ya_existia:
        return caso
    caso = _bloquear_caso(caso)
    caso.situacion = {
        **caso.situacion,
        SITUACION_EN_LA_PUERTA: {"dispositivo_id": dispositivo.pk, "dispositivo": dispositivo.nombre},
    }
    caso.save(update_fields=["situacion", "modificado"])
    _trazar(
        caso,
        usuario,
        Accion.AVISO_A_LA_MESA,
        estado_anterior=caso.estado,
        detalle=f"En la puerta de {dispositivo.nombre} · esperando derivación",
    )
    caso.ya_existia = False
    return caso


def es_ingreso_directo(caso):
    """¿El caso nació de «Ingresar igual»? Origen dispositivo y **no** un aviso a la mesa."""

    return caso.origen == Origen.DISPOSITIVO and SITUACION_EN_LA_PUERTA not in (caso.situacion or {})


# ---------------------------------------------------------------------------
# Egreso (RN-3.12)
# ---------------------------------------------------------------------------


def al_egresar_estadia(sender, estadia, usuario=None, **_kwargs):
    """Receptor de ``estadia_egresada``: marca al integrante y cierra el caso si no queda nadie.

    Corre **dentro de la transacción del egreso** (``estadias.egresar_persona``), con la fila
    de la estadía bloqueada: si falla, el egreso se deshace. Por eso es mínimo:

    * Para una estadía que **no es de Emergencia** —casi todas— hace **una** consulta y vuelve.
    * Para la de un integrante: bloquea el caso (**antes** de escribir al integrante, ver el
      docstring del módulo), le pone ``egresado_en`` y deja la traza. Si el caso está
      ``ALOJADO`` y ya no queda ningún integrante con estadía abierta, pasa a ``CERRADO`` con
      motivo «Todos egresados», ``cerrado_en`` y su traza.

    Un egreso con el ingreso todavía en curso solo marca al integrante: el caso lo cierra la
    guardia (alojar o diferencia), y ahí se vuelve a mirar si quedó alguien.
    """

    fila = IntegranteGrupo.objects.filter(estadia_id=estadia.pk).values_list("pk", "grupo_id", "orden").first()
    if fila is None:
        return
    integrante_pk, grupo_id, orden = fila
    caso = CasoEmergencia.objects.select_for_update().get(grupo_id=grupo_id)
    momento = estadia.fecha_egreso or timezone.now()
    IntegranteGrupo.objects.filter(pk=integrante_pk).update(egresado_en=momento, modificado=timezone.now())
    _trazar(
        caso,
        usuario,
        Accion.INTEGRANTE_EGRESADO,
        estado_anterior=caso.estado,
        detalle=f"Egresó la persona {orden} de la familia",
    )
    _cerrar_si_no_queda_nadie(caso, usuario, timezone.now())


def conectar_receptores():
    """Conecta el receptor del egreso. Lo llama ``ProgramasConfig.ready()``; es idempotente."""

    estadia_egresada.connect(al_egresar_estadia, dispatch_uid="programas.emergencia_alojar.al_egresar_estadia")
