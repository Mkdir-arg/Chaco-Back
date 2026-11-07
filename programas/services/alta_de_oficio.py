"""Alta de oficio en una convocatoria de Becas (comando ``inscribir_de_oficio``).

Para personas que **ya son beneficiarias** y ya figuran en SIIS: el PM las da de
alta directamente desde un CSV, sin que pasen por el link público. Por cada una
se crea el caso (``Formulario``) en el relevamiento público indicado, se
crea/vincula el legajo ciudadano y el caso queda ``APROBADO`` de una vez.

Lo que **no** hace, a propósito: no consulta SIIS, no da de alta en SIIS y no
manda ningún correo. Sí consulta Personas (Gran Base) para acreditar la
identidad: sin identidad validada el caso queda ``ENVIADO`` para que lo revise
una persona (:func:`programas.services.cupo.aprobar_de_oficio` la exige).

**Idempotente.** El ``client_uuid`` de cada caso sale del token del relevamiento
y el DNI (``uuid5``), así que una corrida cortada se retoma sin duplicar: el
caso ya creado se encuentra por esa clave y solo se completa lo que faltó.

Cada fila va en su propia transacción: una que falla no corta el resto.
"""

from __future__ import annotations

import csv
import unicodedata
import uuid
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import InterfaceError, OperationalError, transaction
from django.utils import timezone

from core.dni import dni_valido, normalizar_dni
from programas.models import Convocatoria, Formulario, Relevamiento
from programas.services.becas import (
    _anotar_identidad_acreditada,
    formulario_por_client_uuid,
    resolver_ciudadano_offline,
)
from programas.services.cupo import aprobar_de_oficio, get_cupo_stats
from programas.services.identidad import ORIGEN_MANUAL, identificar
from programas.services.inscripcion_publica import caso_en_convocatoria, dni_en_convocatoria
from programas.services.marca_de_oficio import marcar
from programas.services.padron import normalizar_sexo, normalizar_texto
from programas.services.personas import fecha_iso
from programas.services.respuestas import foto_definicion

#: Espacio de nombres fijo de las claves idempotentes de las altas de oficio.
#: No cambiarlo: es lo que permite reconocer el caso de una corrida anterior.
NAMESPACE_ALTA_DE_OFICIO = uuid.UUID("5f0c6d1e-3b7a-4c52-9a1d-0e8f4b2c7a11")

# Resultados por fila.
APROBADO = "aprobado"
CREADO_SIN_VALIDAR = "creado_sin_validar"
YA_INSCRIPTO = "ya_inscripto"
YA_APROBADO = "ya_aprobado"
INVALIDO = "invalido"
DUPLICADO_ARCHIVO = "duplicado_archivo"
FALLECIDO = "fallecido"
ERROR = "error"

RESULTADOS = (
    APROBADO,
    CREADO_SIN_VALIDAR,
    YA_APROBADO,
    YA_INSCRIPTO,
    INVALIDO,
    DUPLICADO_ARCHIVO,
    FALLECIDO,
    ERROR,
)

_ALIAS_COLUMNAS = {
    "dni": "dni",
    "documento": "dni",
    "sexo": "sexo",
    "genero": "sexo",
    "apellido": "apellido",
    "apellidos": "apellido",
    "nombre": "nombres",
    "nombres": "nombres",
}


class ArchivoInvalido(Exception):
    """El CSV no se puede leer o le faltan columnas."""


@dataclass
class ResultadoFila:
    dni: str
    resultado: str
    numero: int | str = ""
    ciudadano_id: int | str = ""
    origen: str = ""
    detalle: str = ""
    #: Falla técnica de Personas: cuenta para el freno de la corrida.
    error_tecnico: bool = False
    #: Se hizo una consulta a Personas en esta fila (para la pausa).
    consulto_personas: bool = False
    #: La conexión a la base falló: la corrida cierra las conexiones viejas.
    error_bd: bool = False


def _sin_acentos(texto):
    plano = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return plano.strip().lower()


def leer_filas(ruta):
    """Lee el CSV y devuelve ``[{"linea", "dni", "sexo", "apellido", "nombres"}]`` crudos.

    Encabezados insensibles a mayúsculas y acentos, delimitador ``,`` o ``;``,
    utf-8 (con o sin BOM) y, si no decodifica, latin-1.
    """
    try:
        with open(ruta, "rb") as archivo:
            crudo = archivo.read()
    except OSError as error:
        raise ArchivoInvalido(f"No se pudo leer el archivo: {error}") from error
    try:
        texto = crudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = crudo.decode("latin-1")
    lineas = texto.splitlines()
    if not lineas:
        raise ArchivoInvalido("El archivo está vacío.")
    delimitador = ";" if lineas[0].count(";") > lineas[0].count(",") else ","
    lector = csv.reader(lineas, delimiter=delimitador)
    encabezado = next(lector, [])
    columnas = {}
    for posicion, nombre in enumerate(encabezado):
        destino = _ALIAS_COLUMNAS.get(_sin_acentos(nombre))
        if destino and destino not in columnas:
            columnas[destino] = posicion
    faltan = [c for c in ("dni", "sexo") if c not in columnas]
    if faltan:
        raise ArchivoInvalido(
            f"Faltan columnas obligatorias: {', '.join(faltan)} (esperadas: dni, sexo, apellido, nombres)."
        )
    filas = []
    for numero_linea, valores in enumerate(lector, start=2):
        if not any(str(v).strip() for v in valores):
            continue
        fila = {"linea": numero_linea}
        for destino in ("dni", "sexo", "apellido", "nombres"):
            posicion = columnas.get(destino)
            fila[destino] = valores[posicion] if posicion is not None and posicion < len(valores) else ""
        filas.append(fila)
    return filas


def preparar_filas(crudas):
    """Normaliza y marca cada fila: ``invalido`` o ``duplicado_archivo`` quedan
    en ``previo`` con su resultado; las demás van con ``previo=None``."""
    vistos = set()
    filas = []
    for cruda in crudas:
        dni = normalizar_dni(cruda["dni"])
        sexo = normalizar_sexo(cruda["sexo"])
        fila = {
            "linea": cruda["linea"],
            "dni": dni,
            "sexo": sexo,
            "apellido": normalizar_texto(cruda.get("apellido")),
            "nombres": normalizar_texto(cruda.get("nombres")),
            "previo": None,
        }
        if not dni_valido(dni):
            fila["previo"] = ResultadoFila(dni, INVALIDO, detalle=f"línea {fila['linea']}: DNI inválido")
        elif not sexo:
            fila["previo"] = ResultadoFila(dni, INVALIDO, detalle=f"línea {fila['linea']}: sexo inválido")
        elif dni in vistos:
            fila["previo"] = ResultadoFila(
                dni, DUPLICADO_ARCHIVO, detalle=f"línea {fila['linea']}: DNI repetido en el archivo"
            )
        else:
            vistos.add(dni)
        filas.append(fila)
    return filas


class AltaDeOficio:
    """Procesa filas contra un relevamiento público, con un usuario responsable."""

    def __init__(self, relevamiento, usuario):
        self.relevamiento = relevamiento
        self.convocatoria = relevamiento.convocatoria
        self.usuario = usuario
        self._foto = None

    def client_uuid(self, dni):
        return uuid.uuid5(NAMESPACE_ALTA_DE_OFICIO, f"{self.relevamiento.token_publico}:{dni}")

    def foto(self):
        if self._foto is None:
            self._foto = foto_definicion(self.relevamiento)
        return self._foto

    # -- lectura previa ------------------------------------------------------
    def estado_previo(self, dni):
        """``(resultado | None, existente)`` sin escribir nada.

        ``resultado`` es un ``ResultadoFila`` cuando no hay nada que hacer (ya
        inscripta por otra vía, o ya resuelta en una corrida anterior).
        ``existente`` es el caso de una corrida anterior (mismo ``client_uuid``).
        """
        existente = formulario_por_client_uuid(self.relevamiento, self.client_uuid(dni))
        if existente is None:
            if dni_en_convocatoria(self.convocatoria, dni):
                return ResultadoFila(dni, YA_INSCRIPTO, detalle=self._detalle_ya_inscripto(dni)), None
            return None, None
        return self._resultado_de_existente(dni, existente), existente

    def _detalle_ya_inscripto(self, dni, convocatoria=None):
        """Estado y número del caso que ya ocupa el DNI (misma regla que
        ``dni_en_convocatoria``: un RECHAZADO sin validar no cuenta)."""
        caso = caso_en_convocatoria(convocatoria or self.convocatoria, dni)
        if caso is None:
            return "el DNI ya figura en la convocatoria"
        return f"el DNI ya figura en la convocatoria: caso {caso.numero} del relevamiento {caso.relevamiento_id}, estado {caso.estado}"

    @staticmethod
    def _resultado_de_existente(dni, existente):
        if existente.estado == Formulario.Estado.ENVIADO:
            return None
        base = {"numero": existente.numero, "ciudadano_id": existente.ciudadano_id or ""}
        if existente.estado == Formulario.Estado.APROBADO:
            return ResultadoFila(dni, YA_APROBADO, detalle="aprobado en una corrida anterior", **base)
        return ResultadoFila(
            dni, YA_INSCRIPTO, detalle=f"caso de una corrida anterior en estado {existente.estado}", **base
        )

    def necesidad_de_cupo(self, filas):
        """Lugares que hacen falta: ``(del relevamiento, del segmento)``.

        Cuenta conservador: un caso nuevo ocupa uno en cada lado aunque después
        no valide; un caso de una corrida anterior todavía ``ENVIADO`` ocupa uno
        del segmento.
        """
        rel = seg = 0
        for fila in filas:
            if fila["previo"] is not None:
                continue
            previo, existente = self.estado_previo(fila["dni"])
            if previo is not None:
                continue
            if existente is None:
                rel += 1
            seg += 1
        return rel, seg

    def verificar_cupo(self, filas):
        """Devuelve ``None`` si entra, o el mensaje de por qué no."""
        necesita_rel, necesita_seg = self.necesidad_de_cupo(filas)
        libres_rel = Relevamiento.objects.get(pk=self.relevamiento.pk).cupos_libres_del_relevamiento
        libres_seg = get_cupo_stats(self.convocatoria.segmento)["cupo_disponible"]
        problemas = []
        if necesita_rel > libres_rel:
            problemas.append(f"el relevamiento tiene {libres_rel} lugares libres y hacen falta {necesita_rel}")
        if necesita_seg > libres_seg:
            problemas.append(f"el segmento tiene {libres_seg} lugares libres y hacen falta {necesita_seg}")
        return "; ".join(problemas) or None

    # -- escritura ---------------------------------------------------------
    def identidad_de(self, fila, existente=None):
        """Consulta la identidad solo si hace falta. Devuelve ``(identidad, resultado_corto)``."""
        dni = fila["dni"]
        if existente is not None and existente.validado_renaper:
            return None, None
        identidad = identificar(self.relevamiento, dni, fila["sexo"])
        if identidad["fallecido"]:
            return identidad, ResultadoFila(
                dni, FALLECIDO, consulto_personas=True, detalle="Personas informa fallecimiento"
            )
        if identidad["error"] and not identidad.get("no_encontrado"):
            return identidad, ResultadoFila(
                dni,
                ERROR,
                consulto_personas=True,
                error_tecnico=True,
                detalle=f"Personas no respondió: {identidad['error']}"[:300],
            )
        return identidad, None

    def consultar(self, fila):
        """Modo en seco: ``(resultado_previo | None, validaria | None)`` sin escribir."""
        previo, existente = self.estado_previo(fila["dni"])
        if previo is not None:
            return previo, None
        identidad, corto = self.identidad_de(fila, existente)
        if corto is not None:
            return corto, None
        return None, True if identidad is None else bool(identidad["validado"])

    def procesar(self, fila):
        """Una fila válida de :func:`preparar_filas`, en su propia transacción."""
        dni = fila["dni"]
        try:
            previo, existente = self.estado_previo(dni)
            if previo is not None:
                return previo
            identidad, corto = self.identidad_de(fila, existente)
            if corto is not None:
                return corto
            resultado = self._escribir(fila, identidad)
            resultado.consulto_personas = identidad is not None
            return resultado
        except ValidationError as error:
            return ResultadoFila(dni, ERROR, detalle="; ".join(error.messages)[:300])
        except (OperationalError, InterfaceError) as error:
            # Conexión caída o timeout de la base: es técnico, cuenta para el freno.
            return ResultadoFila(dni, ERROR, error_tecnico=True, error_bd=True, detalle=f"Base de datos: {error}"[:300])
        except Exception as error:  # una fila rota no corta las demás
            return ResultadoFila(dni, ERROR, detalle=f"{type(error).__name__}: {error}"[:300])

    def _escribir(self, fila, identidad):
        dni = fila["dni"]
        with transaction.atomic():
            rel = Relevamiento.objects.select_for_update().get(pk=self.relevamiento.pk)
            convocatoria = Convocatoria.objects.select_for_update().get(pk=rel.convocatoria_id)
            existente = formulario_por_client_uuid(rel, self.client_uuid(dni))
            if existente is None:
                if dni_en_convocatoria(convocatoria, dni):
                    return ResultadoFila(dni, YA_INSCRIPTO, detalle=self._detalle_ya_inscripto(dni, convocatoria))
                if rel.formularios.count() >= rel.cupo_maximo:
                    raise ValidationError("El relevamiento no tiene cupo para más casos.")
                formulario = self._crear(rel, fila, identidad)
            else:
                previo = self._resultado_de_existente(dni, existente)
                if previo is not None:
                    return previo
                formulario = existente
                if identidad is not None and identidad["validado"] and not formulario.validado_renaper:
                    self._acreditar(formulario, identidad)
            resolver_ciudadano_offline(formulario)
            formulario.refresh_from_db()
            base = {
                "numero": formulario.numero,
                "ciudadano_id": formulario.ciudadano_id or "",
                "origen": formulario.origen_validacion or ORIGEN_MANUAL,
            }
            if not formulario.validado_renaper:
                return ResultadoFila(
                    dni, CREADO_SIN_VALIDAR, detalle="identidad sin validar: queda ENVIADO para revisión", **base
                )
            aprobar_de_oficio(formulario, self.usuario)
            return ResultadoFila(dni, APROBADO, **base)

    def _crear(self, rel, fila, identidad):
        datos = (identidad or {}).get("datos") or {}
        validado = bool(identidad and identidad["validado"])
        if validado:
            nombre, apellido = datos.get("nombre", ""), datos.get("apellido", "")
            nacimiento = fecha_iso(datos.get("fecha_nacimiento")) or ""
            origen = identidad["origen"]
        else:
            nombre, apellido, nacimiento, origen = fila["nombres"], fila["apellido"], "", ORIGEN_MANUAL
        acredita = bool(validado and nombre and apellido)
        formulario = Formulario.objects.create(
            relevamiento=rel,
            data={},
            respuestas={},
            definicion=self.foto(),
            datos_identificacion={
                "dni": fila["dni"],
                "sexo": fila["sexo"],
                "nombre": nombre,
                "apellido": apellido,
                "fecha_nacimiento": nacimiento,
                "origen": origen if acredita else ORIGEN_MANUAL,
                "localidad_id": datos.get("localidad_id") if acredita else None,
            },
            client_uuid=self.client_uuid(fila["dni"]),
            capturado_en=timezone.now(),
            created_by=self.usuario,
            validado_renaper=acredita,
            origen_validacion=origen if acredita else "",
        )
        # La marca nace con el caso, validado o no: ningún camino lo informa a SIIS.
        marcar(formulario, self.usuario)
        return formulario

    @staticmethod
    def _acreditar(formulario, identidad):
        """Un caso de una corrida anterior que no validó y ahora sí: se acredita
        y se completa el legajo solo donde estaba vacío."""
        datos = identidad.get("datos") or {}
        if not (datos.get("nombre") and datos.get("apellido")):
            return
        formulario.validado_renaper = True
        formulario.origen_validacion = identidad["origen"]
        Formulario.objects.filter(pk=formulario.pk).update(
            validado_renaper=True, origen_validacion=identidad["origen"], modificado=timezone.now()
        )
        ciudadano = formulario.ciudadano
        if ciudadano is not None:
            # SIIS-08: si el legajo conserva los nombres del CSV y difieren de lo
            # acreditado, queda constancia (traza y ``datos_siis``).
            acreditada = {
                "nombre": datos["nombre"],
                "apellido": datos["apellido"],
                "fecha_nacimiento": datos.get("fecha_nacimiento") or "",
                "origen": identidad["origen"],
            }
            if _anotar_identidad_acreditada(formulario, ciudadano, acreditada):
                Formulario.objects.filter(pk=formulario.pk).update(datos_siis=formulario.datos_siis)
            completar = []
            nacimiento = fecha_iso(datos.get("fecha_nacimiento")) or None
            if nacimiento and not ciudadano.fecha_nacimiento:
                ciudadano.fecha_nacimiento = nacimiento
                completar.append("fecha_nacimiento")
            if not ciudadano.nombre:
                ciudadano.nombre = datos["nombre"]
                completar.append("nombre")
            if not ciudadano.apellido:
                ciudadano.apellido = datos["apellido"]
                completar.append("apellido")
            if completar:
                ciudadano.save(update_fields=[*completar, "modificado"])
