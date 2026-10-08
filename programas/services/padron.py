"""Padrón de habilitados por Excel (RN-P14, #299; identidad desde el Cambio 57).

Uno por **convocatoria**: lo usan todos sus relevamientos, del link público y
de la app de campo. El operador sube un .xlsx de hasta seis columnas —
``documento, sexo, nombre, apellido, fecha de nacimiento, localidad`` — desde la
convocatoria. Acá viven el parser, la carga (reemplazo total, transaccional),
el chequeo ``esta_habilitado`` que consume el paso 1 del link **antes** de
consultar Base de Personas, la fila por DNI + sexo que alimenta la cascada de
identidad (``programas.services.identidad``) y el cruce automático que valida
los casos pendientes cuando llega un padrón con datos.

Las tres columnas de identidad y la localidad son opcionales por fila: una fila
con solo documento y sexo **habilita pero no valida** (RN-2). Los padrones de
dos columnas cargados antes del cambio siguen valiendo tal cual (RN-7).

Normalización en ambos sentidos: el DNI se reduce a dígitos y el sexo a F/M
(acepta "f", "Femenino", "MASCULINO", etc.), tanto al cargar el Excel como al
chequear lo tipeado en el paso 1. La localidad se cruza por nombre contra el
catálogo (``core.Localidad``) sin acentos ni mayúsculas; si no coincide queda
solo el texto y la carga lo reporta.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from io import BytesIO

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

# RED-48: la regla de DNI vive en `core/dni.py` —`legajos` y `portal` también la
# necesitan y no pueden importar `programas` sin cerrar un ciclo—. Se reexporta acá
# porque este módulo es su casa histórica y medio repo la importa de este nombre.
from core.dni import (  # noqa: F401
    LARGOS_DNI_VALIDOS,
    MENSAJE_DNI_INVALIDO,
    dni_valido,
    normalizar_dni,
)
from programas.models import Convocatoria, Formulario, PadronHabilitado, Relevamiento

# Tamaño máximo del Excel (los padrones reales son de cientos de filas).
PADRON_MAX_BYTES = 2 * 1024 * 1024

# Encabezados de la plantilla, en el orden de las columnas.
COLUMNAS = ("documento", "sexo", "nombre", "apellido", "fecha de nacimiento", "localidad")

_SEXOS = {
    "F": "F",
    "FEMENINO": "F",
    "MUJER": "F",
    "M": "M",
    "MASCULINO": "M",
    "HOMBRE": "M",
    "VARON": "M",
    "VARÓN": "M",
}

_ENCABEZADOS_DNI = {"DOCUMENTO", "DNI", "NRO DOCUMENTO", "NUMERO DE DOCUMENTO", "NÚMERO DE DOCUMENTO"}

_FORMATOS_FECHA = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%Y/%m/%d")

#: Piso de una fecha de nacimiento que se pueda creer (G1-12). Nadie vivo nació
#: antes, y es lo que separa una fecha de verdad del serial 0 de Excel, que
#: ``openpyxl`` convierte en 1899-12-30: esa fila entraba al padrón con esa fecha
#: y el cruce se la **escribía al legajo** de la persona.
FECHA_NACIMIENTO_MINIMA = date(1900, 1, 1)


def normalizar_sexo(valor):
    return _SEXOS.get(str(valor or "").strip().upper(), "")


def normalizar_texto(valor):
    """Nombre, apellido o localidad tal como vienen, sin espacios de más."""
    return re.sub(r"\s+", " ", str(valor or "")).strip()


def _creible(fecha, hoy=None):
    """``(fecha, invalida)`` después del control de rango (G1-12).

    Una fecha de nacimiento **futura** o anterior a 1900 no es una fecha que se
    pueda interpretar mal: es una fila mal cargada. Hasta acá entraba al padrón
    tal cual y el cruce la volcaba al legajo del ciudadano, donde la edad es una
    regla de negocio (RN-22, BEC-03). Se cuenta como fecha sin interpretar y la
    fila entra igual, sin fecha: lo que habilita a la persona es el documento.
    """
    if fecha is None:
        return None, True
    hoy = hoy or timezone.localdate()
    if fecha > hoy or fecha < FECHA_NACIMIENTO_MINIMA:
        return None, True
    return fecha, False


def _con_pivote(fecha, texto, formato, hoy):
    """El año de dos dígitos se interpreta hacia atrás, no hacia adelante.

    ``strptime`` con ``%y`` usa el pivote fijo de POSIX (69–99 → 19xx, 00–68 →
    20xx), así que ``05/06/30`` —una persona nacida en 1930— salía **2030**.
    Para una fecha de nacimiento no hay ambigüedad: la que está en el futuro es
    la del siglo anterior.
    """
    if "%y" not in formato or fecha <= hoy:
        return fecha
    try:
        return fecha.replace(year=fecha.year - 100)
    except ValueError:  # 29 de febrero de un año bisiesto que no lo es 100 antes
        return fecha.replace(year=fecha.year - 100, day=28)


def normalizar_fecha(valor, hoy=None):
    """Devuelve ``(fecha, invalida)``. ``invalida`` es True solo cuando había
    algo escrito que no se pudo interpretar; una celda vacía no es inválida.

    «No se pudo interpretar» incluye, desde G1-12, lo que se lee pero no se
    puede creer: una fecha futura o anterior a 1900.
    """
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None, False
    hoy = hoy or timezone.localdate()
    if isinstance(valor, datetime):
        return _creible(valor.date(), hoy)
    if isinstance(valor, date):
        return _creible(valor, hoy)
    if isinstance(valor, (int, float)):
        # Número de serie de Excel (fechas sin formato de celda).
        try:
            from openpyxl.utils.datetime import from_excel

            convertido = from_excel(valor)
        except (ValueError, TypeError, OverflowError):
            return None, True
        if isinstance(convertido, datetime):
            convertido = convertido.date()
        return _creible(convertido if isinstance(convertido, date) else None, hoy)
    texto = str(valor).strip()
    for formato in _FORMATOS_FECHA:
        try:
            leida = datetime.strptime(texto, formato).date()
        except ValueError:
            continue
        return _creible(_con_pivote(leida, texto, formato, hoy), hoy)
    return None, True


def clave_localidad(texto):
    """«Sáenz Peña» y «SAENZ PENA» son la misma localidad."""
    plano = unicodedata.normalize("NFD", str(texto or ""))
    plano = "".join(ch for ch in plano if unicodedata.category(ch) != "Mn")
    plano = re.sub(r"[^a-z0-9]+", " ", plano.lower())
    return plano.strip()


@dataclass
class ResumenPadron:
    """Lo que la carga informa al operador (y lo que devuelve el parser)."""

    validas: int = 0
    con_identidad: int = 0
    rechazadas: int = 0
    fechas_invalidas: int = 0
    localidades_no_reconocidas: list = field(default_factory=list)
    casos_validados: int = 0

    def mensaje(self):
        partes = [f"{self.validas} habilitado{'s' if self.validas != 1 else ''}"]
        partes.append(f"{self.con_identidad} con identidad completa")
        if self.rechazadas:
            partes.append(
                f"{self.rechazadas} fila{'s' if self.rechazadas != 1 else ''} ignorada{'s' if self.rechazadas != 1 else ''}"
            )
        if self.fechas_invalidas:
            partes.append(f"{self.fechas_invalidas} fecha{'s' if self.fechas_invalidas != 1 else ''} sin interpretar")
        if self.localidades_no_reconocidas:
            partes.append(f"{len(self.localidades_no_reconocidas)} localidad(es) no reconocida(s)")
        if self.casos_validados:
            partes.append(
                f"{self.casos_validados} caso{'s' if self.casos_validados != 1 else ''} pendiente{'s' if self.casos_validados != 1 else ''} validado{'s' if self.casos_validados != 1 else ''}"
            )
        return "Padrón cargado: " + " · ".join(partes) + "."


def parsear_padron(archivo):
    """Lee el Excel y devuelve ``(entradas, resumen)``.

    ``entradas``: lista de dicts ``{dni, sexo, nombre, apellido,
    fecha_nacimiento, localidad_texto}`` normalizados y sin duplicados (gana la
    primera aparición de cada DNI). ``resumen``: ``ResumenPadron`` con las filas
    rechazadas y las fechas que no se pudieron interpretar (se informan, no
    rompen la carga; la fila queda sin fecha).

    Levanta ``ValidationError`` si el archivo no es un .xlsx legible, pesa de
    más o no aporta ninguna fila válida.
    """
    nombre = getattr(archivo, "name", "") or ""
    if not nombre.lower().endswith(".xlsx"):
        raise ValidationError(
            "El padrón debe ser un archivo Excel (.xlsx) con las columnas: "
            "documento, sexo, nombre, apellido, fecha de nacimiento y localidad."
        )
    if getattr(archivo, "size", 0) > PADRON_MAX_BYTES:
        raise ValidationError("El padrón no puede superar los 2 MB.")

    from openpyxl import load_workbook

    try:
        libro = load_workbook(archivo, read_only=True, data_only=True)
    except Exception as exc:  # openpyxl levanta variantes según el archivo
        raise ValidationError("No se pudo leer el archivo: no es un Excel .xlsx válido.") from exc

    resumen = ResumenPadron()
    try:
        hoja = libro.active
        entradas = []
        vistos = set()
        for indice, fila in enumerate(hoja.iter_rows(min_col=1, max_col=len(COLUMNAS), values_only=True)):
            celdas = (tuple(fila) + (None,) * len(COLUMNAS))[: len(COLUMNAS)]
            crudo_dni, crudo_sexo, crudo_nombre, crudo_apellido, crudo_fecha, crudo_localidad = celdas
            dni = normalizar_dni(crudo_dni)
            sexo = normalizar_sexo(crudo_sexo)
            if not any(str(c or "").strip() for c in celdas):
                continue  # fila totalmente vacía
            if indice == 0 and not dni and str(crudo_dni or "").strip().upper() in _ENCABEZADOS_DNI:
                continue  # fila de encabezado
            if not sexo or not dni_valido(dni):
                resumen.rechazadas += 1
                continue
            if dni in vistos:
                resumen.rechazadas += 1
                continue
            fecha, invalida = normalizar_fecha(crudo_fecha)
            if invalida:
                resumen.fechas_invalidas += 1
            vistos.add(dni)
            entradas.append(
                {
                    "dni": dni,
                    "sexo": sexo,
                    "nombre": normalizar_texto(crudo_nombre),
                    "apellido": normalizar_texto(crudo_apellido),
                    "fecha_nacimiento": fecha,
                    "localidad_texto": normalizar_texto(crudo_localidad),
                }
            )
    finally:
        libro.close()

    if not entradas:
        raise ValidationError(
            "El padrón no tiene filas válidas. Se espera un .xlsx con documento y sexo (F/M) "
            "y, opcionalmente, nombre, apellido, fecha de nacimiento y localidad."
        )
    resumen.validas = len(entradas)
    resumen.con_identidad = sum(1 for e in entradas if e["nombre"] and e["apellido"])
    return entradas, resumen


def _convocatoria_de(objetivo):
    """La convocatoria dueña, venga ella misma o uno de sus relevamientos."""
    if isinstance(objetivo, Convocatoria):
        return objetivo
    convocatoria = getattr(objetivo, "convocatoria", None)
    if convocatoria is None:
        raise TypeError("Se espera una Convocatoria o un Relevamiento.")
    return convocatoria


def _es_relevamiento(objetivo):
    return not isinstance(objetivo, Convocatoria) and hasattr(objetivo, "convocatoria")


def padron_de(objetivo):
    """El padrón **efectivo** (Cambio 74): el propio del relevamiento si cargó
    uno; si no, el de su convocatoria. Para una convocatoria, el suyo (las
    filas de nivel convocatoria, sin las propias de sus relevamientos)."""
    if _es_relevamiento(objetivo):
        propio = objetivo.padron_propio.all()
        if propio.exists():
            return propio
        return _convocatoria_de(objetivo).padron.filter(relevamiento__isnull=True)
    return objetivo.padron.filter(relevamiento__isnull=True)


def origen_padron(relevamiento):
    """``"propio"`` | ``"convocatoria"`` | ``None`` — de dónde sale el padrón
    que rige a este relevamiento."""
    if relevamiento.padron_propio.exists():
        return "propio"
    if _convocatoria_de(relevamiento).padron.filter(relevamiento__isnull=True).exists():
        return "convocatoria"
    return None


def _entrada(item):
    """Acepta la tupla ``(dni, sexo)`` histórica o el dict de seis campos."""
    if isinstance(item, dict):
        return {
            "dni": normalizar_dni(item.get("dni")),
            "sexo": normalizar_sexo(item.get("sexo")),
            "nombre": normalizar_texto(item.get("nombre")),
            "apellido": normalizar_texto(item.get("apellido")),
            "fecha_nacimiento": item.get("fecha_nacimiento"),
            "localidad_texto": normalizar_texto(item.get("localidad_texto")),
        }
    dni, sexo = item
    return {
        "dni": normalizar_dni(dni),
        "sexo": normalizar_sexo(sexo),
        "nombre": "",
        "apellido": "",
        "fecha_nacimiento": None,
        "localidad_texto": "",
    }


def _indice_localidades():
    from core.models import Localidad

    indice = {}
    for localidad in Localidad.objects.only("id", "nombre").order_by("id"):
        indice.setdefault(clave_localidad(localidad.nombre), localidad)
    return indice


def _borrar_archivo_tras_commit(campo_archivo, nombre):
    """Borra del storage un Excel de padrón **después** del commit (DAT-05).

    Dos problemas, uno por punta. Al **reemplazar** el padrón nadie borraba el Excel
    anterior: cada recarga dejaba otro archivo con DNI, nombre y fecha de nacimiento
    de miles de personas en ``media/``, sin dueño y sin fecha de baja. Al **quitar**
    el padrón propio pasaba lo contrario: el archivo se borraba *dentro* de la
    transacción, así que un error posterior dejaba la fila apuntando a un archivo que
    ya no existía.

    `on_commit` resuelve las dos: el storage se toca solo si la base confirmó.
    """
    if not nombre:
        return
    storage = campo_archivo.storage
    transaction.on_commit(lambda: storage.delete(nombre))


@transaction.atomic
def cargar_padron(objetivo, archivo, entradas, usuario=None):
    """Reemplaza el padrón de ``objetivo`` por ``entradas`` (reemplazo total,
    no merge), guarda el Excel original para trazabilidad y **valida los casos
    pendientes** que ahora figuren con nombre y apellido (RN-5).

    Cambio 74: con una convocatoria, es el padrón que heredan sus
    relevamientos sin padrón propio; con un relevamiento, es el padrón propio
    de **ese** relevamiento y deja de heredar. Devuelve el ``ResumenPadron``.
    """
    convocatoria = _convocatoria_de(objetivo)
    relevamiento = objetivo if _es_relevamiento(objetivo) else None
    # BEC-15: el dueño del padrón se bloquea **antes** de borrar y volver a
    # insertar. La carga es un reemplazo total (DELETE + bulk_create) y sin
    # candado dos cargas en paralelo se intercalan: la segunda borra lo que la
    # primera estaba insertando y el padrón queda con filas de las dos tandas, o
    # con el `unique` de `(convocatoria, relevamiento, dni)` reventando en un 500
    # —en MySQL y MariaDB ese índice ni siquiera aplica cuando `relevamiento` es
    # NULL, así que el final normal es duplicados silenciosos—. Es el mismo
    # objeto sobre el que después se escribe `padron_archivo`.
    duenio_pk = (relevamiento or convocatoria).pk
    type(relevamiento or convocatoria).objects.select_for_update().filter(pk=duenio_pk).first()
    filas = [_entrada(item) for item in entradas]
    resumen = ResumenPadron(validas=len(filas))
    localidades = _indice_localidades() if any(f["localidad_texto"] for f in filas) else {}

    objetos = []
    for fila in filas:
        localidad = None
        if fila["localidad_texto"]:
            localidad = localidades.get(clave_localidad(fila["localidad_texto"]))
            if localidad is None and fila["localidad_texto"] not in resumen.localidades_no_reconocidas:
                resumen.localidades_no_reconocidas.append(fila["localidad_texto"])
        objetos.append(
            PadronHabilitado(
                convocatoria=convocatoria,
                relevamiento=relevamiento,
                dni=fila["dni"],
                sexo=fila["sexo"],
                nombre=fila["nombre"],
                apellido=fila["apellido"],
                fecha_nacimiento=fila["fecha_nacimiento"],
                localidad=localidad,
                localidad_texto=fila["localidad_texto"],
            )
        )
    resumen.con_identidad = sum(1 for o in objetos if o.tiene_identidad)

    if relevamiento is not None:
        relevamiento.padron_propio.all().delete()
    else:
        convocatoria.padron.filter(relevamiento__isnull=True).delete()
    PadronHabilitado.objects.bulk_create(objetos)
    if archivo is not None:
        # El parser ya consumió el stream: rebobinar antes de persistirlo.
        if hasattr(archivo, "seek"):
            archivo.seek(0)
        duenio = relevamiento or convocatoria
        anterior = duenio.padron_archivo.name
        duenio.padron_archivo = archivo
        duenio.save(update_fields=["padron_archivo", "modificado"])
        # DAT-05: el Excel que se acaba de reemplazar se va con el commit. Se compara
        # el nombre final —el storage puede haberle agregado un sufijo— para no
        # borrar el que se acaba de guardar si resultó ser el mismo.
        if anterior != duenio.padron_archivo.name:
            _borrar_archivo_tras_commit(duenio.padron_archivo, anterior)
    resumen.casos_validados = validar_casos_pendientes(objetivo, usuario)
    return resumen


@transaction.atomic
def quitar_padron_propio(relevamiento):
    """El relevamiento vuelve a heredar el padrón de la convocatoria: borra sus
    filas propias y su Excel. Devuelve cuántas filas tenía."""
    # BEC-15, la otra punta (RED-35): quitar también borra filas y escribe
    # `padron_archivo`, así que toma **el mismo** candado que `cargar_padron`.
    # Sin él, una carga simultánea sobre el mismo relevamiento se intercala y
    # queda el estado peor de todos: filas de la carga nueva con el Excel ya
    # borrado, o —al revés— el padrón propio vacío con el Excel puesto. Un
    # padrón propio vacío no retiene a nadie: `padron_de` cae al de la
    # convocatoria y, si no hay, el link queda abierto (RN-P14).
    Relevamiento.objects.select_for_update().filter(pk=relevamiento.pk).first()
    filas = relevamiento.padron_propio.count()
    relevamiento.padron_propio.all().delete()
    if relevamiento.padron_archivo:
        anterior = relevamiento.padron_archivo.name
        relevamiento.padron_archivo = None
        relevamiento.save(update_fields=["padron_archivo", "modificado"])
        # DAT-05: antes el `delete(save=False)` corría acá adentro, así que si el
        # `save` fallaba la fila quedaba apuntando a un archivo borrado.
        _borrar_archivo_tras_commit(relevamiento.padron_archivo, anterior)
    return filas


def esta_habilitado(objetivo, dni, sexo):
    """¿DNI+sexo pueden inscribirse? Se decide contra el padrón **efectivo**
    (el propio del relevamiento o el heredado); sin ninguno, el link es
    abierto (RN-P14)."""
    padron = padron_de(objetivo)
    if not padron.exists():
        return True
    return padron.filter(dni=normalizar_dni(dni), sexo=normalizar_sexo(sexo)).exists()


def fila_padron(objetivo, dni, sexo):
    """La fila del padrón **efectivo** para DNI + sexo, o ``None``."""
    dni, sexo = normalizar_dni(dni), normalizar_sexo(sexo)
    if not dni or not sexo:
        return None
    return padron_de(objetivo).filter(dni=dni, sexo=sexo).first()


def objetivo_con_identidad(relevamientos, dni, sexo):
    """Entre varios relevamientos, el primero cuyo padrón **efectivo** tiene a
    DNI + sexo con nombre y apellido; ``None`` si ninguno. Dos consultas como
    mucho (la app de campo puede tener varios relevamientos vigentes)."""
    dni, sexo = normalizar_dni(dni), normalizar_sexo(sexo)
    relevamientos = list(relevamientos)
    if not relevamientos or not dni or not sexo:
        return None
    con_propio = set(
        PadronHabilitado.objects.filter(relevamiento__in=relevamientos).values_list("relevamiento_id", flat=True)
    )
    filas = PadronHabilitado.objects.filter(dni=dni, sexo=sexo).con_identidad()
    propios = set(filas.filter(relevamiento__in=relevamientos).values_list("relevamiento_id", flat=True))
    heredables = set(
        filas.filter(
            relevamiento__isnull=True,
            convocatoria__in={r.convocatoria_id for r in relevamientos},
        ).values_list("convocatoria_id", flat=True)
    )
    for rel in relevamientos:
        if rel.pk in propios:
            return rel
        if rel.pk not in con_propio and rel.convocatoria_id in heredables:
            return rel
    return None


def datos_de_fila(fila):
    """Lo que la fila aporta a la identificación: mismo contrato que la Gran Base
    (nombre, apellido, fecha ISO) más la localidad para el legajo."""
    return {
        "nombre": fila.nombre,
        "apellido": fila.apellido,
        "fecha_nacimiento": fila.fecha_nacimiento.isoformat() if fila.fecha_nacimiento else "",
        "localidad_id": fila.localidad_id,
        "localidad_texto": fila.localidad_texto,
    }


def _identidad_del_caso(formulario):
    if formulario.ciudadano_id:
        return formulario.ciudadano.dni, formulario.ciudadano.genero
    datos = formulario.datos_identificacion if isinstance(formulario.datos_identificacion, dict) else {}
    return datos.get("dni", ""), datos.get("sexo") or datos.get("genero") or ""


def validar_casos_pendientes(objetivo, usuario=None):
    """Cruce automático (RN-5): los casos **sin validar** que figuran en el
    padrón efectivo con nombre y apellido pasan a validados por padrón.

    Cambio 74: al cargar el padrón de un relevamiento se cruzan solo sus
    casos; al cargar el de la convocatoria, los de sus relevamientos que lo
    heredan (los que tienen padrón propio no se tocan). Solo casos pendientes
    y no forzados; nunca desvalida. Completa en el ciudadano lo vacío (no pisa)
    y deja traza por caso. Devuelve cuántos validó.
    """
    from programas.services.becas import registrar_traza

    # El padrón entero en memoria (está acotado a 2 MB, cientos de filas): el
    # día que por fin llega un padrón con datos puede haber cientos de casos
    # pendientes acumulados, y una consulta por caso no escala.
    filas = {(fila.dni, fila.sexo): fila for fila in padron_de(objetivo).con_identidad().select_related("localidad")}
    if not filas:
        return 0
    # Sin las columnas JSON que el cruce no lee (``data``, ``respuestas``,
    # ``definicion``, ``datos_siis``): son unos 7 KB por caso, y el padrón de una
    # convocatoria cruza los pendientes de todos sus relevamientos. Con el
    # público de 20.000 casos eran 6.700 pendientes y 52 MB en una consulta
    # (1,2 s de SQL en el banco; contra la base de ECOM, más que su
    # ``read_timeout`` de 10 s); sin ellas, 180 ms. El ``save`` de abajo escribe
    # solo sus ``update_fields``, así que lo diferido no se toca.
    pendientes = (
        Formulario.objects.filter(
            validado_renaper=False,
            identidad_forzada=False,
        )
        .defer("data", "respuestas", "definicion", "datos_siis")
        .select_related("ciudadano")
    )
    if _es_relevamiento(objetivo):
        pendientes = pendientes.filter(relevamiento=objetivo)
    else:
        pendientes = pendientes.filter(relevamiento__convocatoria=objetivo).exclude(
            relevamiento__in=PadronHabilitado.objects.filter(relevamiento__convocatoria=objetivo).values(
                "relevamiento_id"
            )
        )

    validados = []
    for formulario in pendientes:
        dni, sexo = _identidad_del_caso(formulario)
        fila = filas.get((normalizar_dni(dni), normalizar_sexo(sexo)))
        if fila is None:
            continue
        cambios = [("Validación de identidad", "Pendiente", "Validada por padrón")]
        ciudadano = formulario.ciudadano
        if ciudadano is not None:
            actualizados = []
            for campo, valor in (
                ("nombre", fila.nombre),
                ("apellido", fila.apellido),
                ("fecha_nacimiento", fila.fecha_nacimiento),
                ("localidad", fila.localidad),
            ):
                if valor and not getattr(ciudadano, campo):
                    setattr(ciudadano, campo, valor)
                    actualizados.append(campo)
                    cambios.append((f"Ciudadano · {campo}", "", str(valor)))
            if actualizados:
                ciudadano.save(update_fields=[*actualizados, "modificado"])
        elif isinstance(formulario.datos_identificacion, dict):
            datos = dict(formulario.datos_identificacion)
            for campo, valor in (
                ("nombre", fila.nombre),
                ("apellido", fila.apellido),
                ("fecha_nacimiento", fila.fecha_nacimiento.isoformat() if fila.fecha_nacimiento else ""),
            ):
                if valor and not datos.get(campo):
                    datos[campo] = valor
            if fila.localidad_id and not datos.get("localidad_id"):
                datos["localidad_id"] = fila.localidad_id
            datos["origen"] = "padron"
            formulario.datos_identificacion = datos
        formulario.validado_renaper = True
        formulario.origen_validacion = Formulario.OrigenValidacion.PADRON
        # Lo que ``save()`` haría por su cuenta: ``modificado`` (auto_now) y el
        # DNI del titular recalculado. Los casos se escriben juntos al final.
        formulario.modificado = timezone.now()
        formulario.dni_titular = formulario._dni_titular_actual()
        validados.append(formulario)
        registrar_traza(formulario, usuario, cambios)
    if validados:
        # Un UPDATE por lote en vez de uno por caso: con 1.000 casos validados
        # eran 1.000 sentencias (1,4 s en el banco) dentro del request que sube
        # el padrón. El legajo (``ciudadano.save``) y la traza siguen por caso:
        # el primero dispara la señal que invalida su caché y la segunda vive en
        # ``registrar_traza``.
        Formulario.objects.bulk_update(
            validados,
            ["validado_renaper", "origen_validacion", "datos_identificacion", "modificado", "dni_titular"],
            batch_size=200,
        )
    return len(validados)


def plantilla_padron():
    """El .xlsx de ejemplo que se descarga desde la convocatoria: encabezados y
    dos filas —una completa, una con solo documento y sexo—."""
    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Padrón"
    hoja.append(list(COLUMNAS))
    hoja.append(["30123456", "F", "María Luján", "Gómez", "14/03/1991", "Resistencia"])
    hoja.append(["28111222", "M", "", "", "", ""])
    for columna, ancho in zip("ABCDEF", (14, 8, 22, 22, 20, 22)):
        hoja.column_dimensions[columna].width = ancho
    buffer = BytesIO()
    libro.save(buffer)
    return buffer.getvalue()
