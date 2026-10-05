"""Alta de beneficiarios aprobados en la tabla intermedia de SIIS.

Módulo puro: arma el payload de los 30 campos del manual M2M v4.2 a partir del
ciudadano, las respuestas del formulario marcadas con un ``destino_siis`` y las
correcciones del coordinador (``Formulario.datos_siis``). Lo que no se puede
resolver queda en ``faltantes`` y el envío no se hace; cada intento deja un
:class:`~programas.models.EnvioSIIS`.
"""

import re
import unicodedata
from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone

from programas.models import EnvioSIIS, Formulario, PreguntaGlobal
from programas.services.dashboard_becas import respuesta_de
from programas.services.padron import normalizar_dni
from programas.services.siis import (
    RESULTADO_INCIERTO,
    RESULTADO_NO_ENVIADO,
    RESULTADO_OK,
    RESULTADO_RECHAZADO,
    SiisCatalogError,
    cargar_beneficiario,
    catalogo,
)

TDOC_DNI = 1
BARRIO_MINIMO = 4
LARGO_TEXTO = 50
LARGO_CELULAR = 10

# Cambio 89: convención para el domicilio sin altura.
#
# SIIS exige un entero en ``nro_actual`` y el 38% de los casos relevados no lo
# tiene: la gente contestó «S/N», «0», «Planta Urbana» o directamente el nombre
# de la calle sin número. Sin esto, 2.405 personas no se pueden informar.
#
# Es una decisión del PM, tomada sabiendo el costo: cuando no hay altura **no
# viaja tampoco el nombre de la calle**, aunque el relevamiento lo tenga. Se
# eligió que los dos campos vayan juntos para que en SIIS quede claro que el
# domicilio es aproximado, en vez de una calle real con una altura inventada.
CALLE_SIN_NUMERO = "Planta urbana sin número"
ALTURA_SIN_NUMERO = 1
MAYORIA_DE_EDAD = 18
_PESOS_CUIL = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
_PALABRAS_DIRECCION = {"piso", "dpto", "depto", "dto", "departamento", "de", "y", "casa", "mz", "mza", "manzana"}
_FRASE_PISO_DPTO = r"\b(?:piso|dpto|depto|dto|departamento)\.?\s*([A-Za-z0-9]{1,3})\b"


class CatalogoNoDisponible(Exception):
    """SIIS no devolvió un catálogo: el envío se reintenta, no se corrige."""


# ---------------------------------------------------------------------------
# CUIL
# ---------------------------------------------------------------------------
def _verificador(prefijo, dni):
    base = f"{prefijo:02d}{dni}"
    suma = sum(int(c) * p for c, p in zip(base, _PESOS_CUIL))
    return 11 - (suma % 11)


def calcular_cuil(dni, sexo):
    """``(prefijo, dígito)`` con el algoritmo estándar de módulo 11.

    Prefijo 20 (M) / 27 (F). Si el verificador da 10, el prefijo pasa a 23 y el
    dígito es 9 (M) o 4 (F); si da 11, el dígito es 0.
    """
    dni = re.sub(r"\D", "", str(dni or "")).zfill(8)[-8:]
    es_mujer = str(sexo or "").upper() == "F"
    prefijo = 27 if es_mujer else 20
    digito = _verificador(prefijo, dni)
    if digito == 11:
        digito = 0
    elif digito == 10:
        prefijo = 23
        digito = 4 if es_mujer else 9
    return prefijo, digito


# ---------------------------------------------------------------------------
# Dirección
# ---------------------------------------------------------------------------
def parsear_direccion(texto):
    """Separa «Calle y altura (piso, dpto)» en ``calle``, ``nro``, ``piso`` y ``dpto``.

    El número es el último grupo de dígitos fuera de paréntesis; lo que hay
    entre paréntesis o después del número se interpreta como piso (dígitos) y
    departamento (una o dos letras). ``S/N`` deja ``nro`` en ``None``: SIIS exige
    un entero y no se inventa.
    """
    texto = " ".join(str(texto or "").split())
    extra = " ".join(re.findall(r"\(([^)]*)\)", texto))
    base = re.sub(r"\([^)]*\)", " ", texto)
    # «piso 3», «dpto A», «depto. 2B»: van al extra antes de buscar la altura,
    # si no el último número sería el piso y no la altura.
    frases = re.findall(_FRASE_PISO_DPTO, base, re.IGNORECASE)
    if frases:
        extra = f"{extra} {' '.join(frases)}".strip()
        base = re.sub(_FRASE_PISO_DPTO, " ", base, flags=re.IGNORECASE)
    sin_numero = re.search(r"\bS\s*/\s*N\b", base, re.IGNORECASE)
    if sin_numero:
        base = base[: sin_numero.start()]
    base = " ".join(base.split()).strip(" ,-")
    calle, nro = base, None
    if not sin_numero:
        m = re.match(r"^(?P<calle>.*?)(?:^|[\s,]+)(?P<nro>\d{1,6})(?P<cola>\D*)$", base)
        if m and m.group("calle").strip(" ,-"):
            calle = m.group("calle").strip(" ,-")
            nro = int(m.group("nro"))
            extra = f"{extra} {m.group('cola')}".strip()
    piso = dpto = None
    if extra:
        m_piso = re.search(r"\d{1,3}", extra)
        piso = int(m_piso.group()) if m_piso else None
        for token in re.split(r"[\s,;/.-]+", extra):
            if re.fullmatch(r"[A-Za-z]{1,2}", token) and token.lower() not in _PALABRAS_DIRECCION:
                dpto = token.upper()
                break
    return {"calle": calle[:LARGO_TEXTO], "nro": nro, "piso": piso, "dpto": dpto}


# ---------------------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------------------
def clave_nombre(texto):
    """Clave de comparación: sin acentos, sin «/a», minúsculas, un solo espacio."""
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().casefold()
    t = re.sub(r"/[ao]s?\b", "", t)
    # «Casada» y «Casado/a» tienen que coincidir: se neutraliza la última vocal de género.
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    return t


def _clave_sin_genero(clave):
    return re.sub(r"\b(\w+?)[ao]\b", r"\1", clave)


class Catalogos:
    """Resuelve nombres a ids de los catálogos maestros. ``cargar`` se inyecta en tests."""

    def __init__(self, cargar=catalogo):
        self._cargar = cargar
        self._cache = {}

    def _items(self, nombre):
        if nombre not in self._cache:
            try:
                self._cache[nombre] = list(self._cargar(nombre))
            except SiisCatalogError as exc:
                raise CatalogoNoDisponible(str(exc)) from exc
        return self._cache[nombre]

    @staticmethod
    def _provincia_de(item):
        for clave in ("id_provincia", "provincia_id", "provincia", "prov_id"):
            valor = item.get(clave)
            if isinstance(valor, dict):
                valor = valor.get("id")
            try:
                return int(valor)
            except (TypeError, ValueError):
                continue
        return None

    def _buscar(self, nombre_catalogo, texto, filtro=None, sin_genero=False):
        clave = clave_nombre(texto)
        if not clave:
            return None
        if sin_genero:
            clave = _clave_sin_genero(clave)
            candidatos = [
                i for i in self._items(nombre_catalogo) if _clave_sin_genero(clave_nombre(i["nombre"])) == clave
            ]
        else:
            candidatos = [i for i in self._items(nombre_catalogo) if clave_nombre(i["nombre"]) == clave]
        if filtro is not None:
            candidatos = [i for i in candidatos if filtro(i)]
        return candidatos[0]["id"] if len(candidatos) == 1 else None

    def provincia_id(self, nombre):
        """Cambio 85: primero el catálogo propio; la API queda de respaldo.

        El catálogo local es el que el organismo nos pasó y es el que manda: la
        API devolvía sin coincidencia nombres que sí están en su padrón.
        """
        from programas.models import ProvinciaSiis

        clave = clave_nombre(nombre)
        if not clave:
            return None
        propia = ProvinciaSiis.objects.filter(clave=clave).values_list("siis_id", flat=True)[:2]
        if len(propia) == 1:
            return propia[0]
        return self._buscar("provincias", nombre)

    def localidad_id(self, nombre, provincia_id=None):
        """Acotada a la provincia cuando se conoce; sin provincia, solo si el nombre es único.

        Orden (Cambio 85): equivalencia cargada → catálogo propio → API. La
        equivalencia va primero y gana incluso si el nombre existiera tal cual en
        el catálogo, porque es una decisión tomada a mano para ese texto.
        """
        from programas.models import AliasLocalidadSiis, LocalidadSiis

        clave = clave_nombre(nombre)
        if not clave:
            return None
        if provincia_id is not None:
            provincia_id = int(provincia_id)
            alias = (
                AliasLocalidadSiis.objects.filter(provincia__siis_id=provincia_id, clave=clave)
                .select_related("localidad")
                .first()
            )
            if alias is not None:
                # Sin destino es una decisión registrada: se revisó y no hay
                # equivalencia. Devolver ``None`` acá evita que la API invente una.
                return alias.localidad.siis_id if alias.localidad_id else None
            propias = LocalidadSiis.objects.filter(provincia__siis_id=provincia_id, clave=clave).values_list(
                "siis_id", flat=True
            )[:2]
            if len(propias) == 1:
                return propias[0]
            if len(propias) > 1:
                # Ambigua en el catálogo propio: que la resuelva una equivalencia,
                # no la API con otro criterio.
                return None
            return self._buscar("localidades", nombre, lambda i: self._provincia_de(i) in (None, provincia_id))
        propias = LocalidadSiis.objects.filter(clave=clave).values_list("siis_id", flat=True)[:2]
        if len(propias) == 1:
            return propias[0]
        return self._buscar("localidades", nombre)

    def estado_civil_id(self, nombre):
        """Contra la API, como provincias y localidades, pero acá los ids sí son los de SIIS.

        Se verificó el 01/10/2026 contra la tabla del manual M2M v4.2 (1 =
        Soltero/a, 2 = Casado/a, 5 = Conviviente), porque este es el mismo
        endpoint ``/catalogos/*`` que para localidades devuelve posiciones de
        lista en vez de ids. Lo que la API contesta acá coincide con el manual
        en los tres valores que el manual documenta, así que no hace falta un
        catálogo propio de respaldo.

        Lo que sí falta en SIIS es **Separado/a**: el relevamiento lo ofrece,
        no tiene equivalente en el catálogo y el caso queda sin poder enviarse
        (``est_civil`` es obligatorio). Son pocos y se destraban cargando la
        corrección a mano en ``datos_siis``.
        """
        return self._buscar("estados-civiles", nombre, sin_genero=True)

    def nombre_de(self, nombre_catalogo, item_id):
        for item in self._items(nombre_catalogo):
            if item["id"] == item_id:
                return item["nombre"]
        return ""


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------
def _texto_mayus(valor):
    return " ".join(str(valor or "").split()).upper()[:LARGO_TEXTO]


# Alias de la función canónica del padrón (RED-47): la copia propia convertía
# un DNI float o Decimal en un número con un 0 de más, y lo que viaja a SIIS es
# un alta sin baja.
_digitos = normalizar_dni


def normalizar_celular(valor):
    """El celular en los 10 dígitos que admite SIIS, o ``""`` si no se puede.

    SIIS lo guarda en una columna numérica de 10 dígitos: con el 54 o el 9
    adelante el SQL Server responde *Arithmetic overflow* y el alta vuelve como
    ``ERROR_BD_LEGACY`` (503), igual que una caída. Se sacan los prefijos que se
    reconocen sin adivinar (54, 9 de móvil, 0 de larga distancia). Si todavía
    sobra --un 15 intercalado, un dígito de más-- no viaja: es opcional, y un
    número adivinado es peor que ninguno.
    """
    digitos = _digitos(valor)
    for prefijo in ("54", "9", "0"):
        if len(digitos) > LARGO_CELULAR and digitos.startswith(prefijo):
            digitos = digitos[len(prefijo) :]
    return digitos if len(digitos) <= LARGO_CELULAR else ""


def _edad(fecha_nacimiento, hoy):
    return hoy.year - fecha_nacimiento.year - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))


def _con_valor(valor):
    return valor is not None and str(valor).strip() != ""


def _altura_valida(valor):
    """¿Es una altura de puerta de verdad?

    Un 0 no lo es: es «sin número» escrito con un dígito. ``_con_valor`` lo da
    por bueno --para el resto del payload el 0 sí es un valor legítimo-- y por
    eso «SAN MARTIN 0» salía con ``nro_actual: 0``, que SIIS recibe y guarda
    como una altura real. Acá se lo trata como falta de altura, igual que «S/N».
    """
    if not _con_valor(valor):
        return False
    try:
        return int(valor) > 0
    except (TypeError, ValueError):
        return False


def _primer_valor(formulario, clave):
    valores = [str(v).strip() for v in respuesta_de(formulario.data, clave) if str(v or "").strip()]
    return valores[0] if valores else None


def respuestas_por_destino(formulario):
    """``{destino: texto}`` con la primera respuesta no vacía de cada campo marcado.

    Se miran las preguntas generales activas y, además (Cambio 80), los
    requisitos nativos que alcanzan al formulario —los del programa, los del
    segmento y los del subsegmento de su convocatoria, la misma herencia que
    ``get_campos_formulario``—. Si una general y un requisito apuntan al mismo
    destino, manda el requisito: es el dato más específico de ese segmento.
    """
    from django.db.models import Q

    from programas.models import RequisitoNativo

    resultado = {}
    preguntas = PreguntaGlobal.objects.filter(activo=True).exclude(destino_siis="").values_list("pk", "destino_siis")
    for pk, destino in preguntas:
        valor = _primer_valor(formulario, f"global:{pk}")
        if valor is not None:
            resultado[destino] = valor

    convocatoria = formulario.relevamiento.convocatoria
    segmento = convocatoria.segmento
    alcance = Q(segmento_id=segmento.pk, subsegmento__isnull=True)
    if convocatoria.subsegmento_id:
        alcance |= Q(subsegmento_id=convocatoria.subsegmento_id)
    if segmento.programa_id:
        alcance |= Q(programa_id=segmento.programa_id)
    requisitos = (
        RequisitoNativo.objects.filter(alcance)
        .exclude(destino_siis="")
        .order_by("orden", "id")
        .values_list("pk", "destino_siis")
    )
    for pk, destino in requisitos:
        valor = _primer_valor(formulario, f"requisito:{pk}")
        if valor is not None:
            resultado[destino] = valor
    return resultado


def _apoderado(formulario, faltantes, correcciones=None):
    """Los 7 campos condicionales del manual (sección 4): solo para menores de 18.

    ``correcciones`` es el ``datos_siis`` del caso, igual que en el resto del
    payload: lo que el coordinador cargó a mano gana sobre lo que trae el
    legajo. Hasta el 30/09/2026 el apoderado era el único bloque que no las
    miraba, así que una fecha mal cargada no se podía corregir para SIIS sin
    tocar el legajo de la persona.
    """
    correcciones = correcciones or {}
    if formulario.apoderado_ciudadano_id:
        a = formulario.apoderado_ciudadano
        dni, nombre, apellido, sexo, nacimiento = a.dni, a.nombre, a.apellido, a.genero, a.fecha_nacimiento
    else:
        dni, nombre, apellido = formulario.apoderado_dni, formulario.apoderado_nombre, formulario.apoderado_apellido
        sexo, nacimiento = formulario.apoderado_genero, formulario.apoderado_fecha_nacimiento
    dni = _primero_con_valor(correcciones.get("dni_apoderado"), dni)
    nombre = _primero_con_valor(correcciones.get("nombre_apoderado"), nombre)
    apellido = _primero_con_valor(correcciones.get("apellido_apoderado"), apellido)
    sexo = _primero_con_valor(correcciones.get("sexo_apoderado"), sexo)
    nacimiento = _fecha_corregida(correcciones.get("fecha_nacim_apoderado")) or nacimiento
    datos = {}
    dni = _digitos(dni)
    if not dni:
        faltantes["dni_apoderado"] = "La persona es menor de 18 años y el caso no tiene apoderado con DNI."
        return datos
    datos["dni_apoderado"] = int(dni)
    if apellido:
        datos["apellido_apoderado"] = _texto_mayus(apellido)
    else:
        faltantes["apellido_apoderado"] = "Falta el apellido del apoderado."
    if nombre:
        datos["nombre_apoderado"] = _texto_mayus(nombre)
    else:
        faltantes["nombre_apoderado"] = "Falta el nombre del apoderado."
    sexo = str(sexo or "").upper()
    if sexo in ("F", "M"):
        datos["sexo_apoderado"] = sexo
        datos["cuil_pref_apoderado"], datos["cuil_dig_apoderado"] = calcular_cuil(dni, sexo)
    else:
        faltantes["sexo_apoderado"] = "El sexo del apoderado debe ser F o M."
    if nacimiento:
        datos["fecha_nacim_apoderado"] = nacimiento.isoformat()
    else:
        faltantes["fecha_nacim_apoderado"] = "Falta la fecha de nacimiento del apoderado."
    return datos


def _resolver_catalogo(correcciones, respuestas, campo, resolver):
    """Prioridad: corrección del coordinador → respuesta del relevamiento resuelta en el catálogo."""
    valor = correcciones.get(campo)
    if _con_valor(valor):
        return int(valor)
    if respuestas.get(campo):
        return resolver(respuestas[campo])
    return None


def _primero_con_valor(*valores):
    """El primero que no sea ``None`` ni cadena vacía. El 0 es un valor válido."""
    for valor in valores:
        if _con_valor(valor):
            return valor
    return None


def _fecha_corregida(valor):
    """La fecha de una corrección, que viaja como texto ISO en ``datos_siis``.

    Devuelve ``None`` si no hay valor o si no se puede leer: una corrección
    ilegible no puede pisar el dato del legajo en silencio.
    """
    if isinstance(valor, date):
        return valor
    if not _con_valor(valor):
        return None
    try:
        return date.fromisoformat(str(valor).strip()[:10])
    except ValueError:
        return None


def armar_payload(formulario, catalogos=None, hoy=None):
    """``(payload, faltantes)``: el payload solo se manda si ``faltantes`` está vacío.

    Lanza :class:`CatalogoNoDisponible` si SIIS no devuelve un catálogo (error
    técnico, reintentable), a diferencia de un dato que no matchea (faltante).
    Los nombres de campo son **exactamente** los del manual; no se inventan.
    """
    catalogos = catalogos or Catalogos()
    hoy = hoy or date.today()
    faltantes = {}
    payload = {"tdoc": TDOC_DNI}
    ciudadano = formulario.ciudadano if formulario.ciudadano_id else None
    segmento = formulario.relevamiento.convocatoria.segmento
    programa = segmento.programa
    respuestas = respuestas_por_destino(formulario)
    correcciones = formulario.datos_siis if isinstance(formulario.datos_siis, dict) else {}

    # --- Persona ---
    dni = _digitos(ciudadano.dni if ciudadano else "")
    if dni and len(dni) <= 10:
        payload["dni"] = int(dni)
    else:
        faltantes["dni"] = "El caso no tiene un ciudadano con DNI válido."
    if ciudadano and ciudadano.apellido:
        payload["apellido"] = _texto_mayus(ciudadano.apellido)
    else:
        faltantes["apellido"] = "Falta el apellido."
    if ciudadano and ciudadano.nombre:
        payload["nombre"] = _texto_mayus(ciudadano.nombre)
    else:
        faltantes["nombre"] = "Falta el nombre."
    sexo = str(ciudadano.genero if ciudadano else "").upper()
    if sexo in ("F", "M"):
        payload["sexo"] = sexo
        if dni:
            payload["cuil_pref"], payload["cuil_dig"] = calcular_cuil(dni, sexo)
    else:
        faltantes["sexo"] = "SIIS solo admite sexo F o M; corregilo en la sección de género del caso."
    nacimiento = ciudadano.fecha_nacimiento if ciudadano else None
    if nacimiento and nacimiento <= hoy:
        payload["fecha_nacim"] = nacimiento.isoformat()
    else:
        faltantes["fecha_nacim"] = "Falta la fecha de nacimiento o es futura."

    # --- Estado civil ---
    est_civil = _resolver_catalogo(correcciones, respuestas, "est_civil", catalogos.estado_civil_id)
    if est_civil is not None:
        payload["est_civil"] = est_civil
    else:
        faltantes["est_civil"] = (
            "No se pudo determinar el estado civil (sin pregunta marcada o sin coincidencia en el catálogo)."
        )

    # --- Domicilio actual ---
    prov_actual = _resolver_catalogo(correcciones, respuestas, "prov_actual", catalogos.provincia_id)
    if prov_actual is not None:
        payload["prov_actual"] = prov_actual
    else:
        faltantes["prov_actual"] = "No se pudo determinar la provincia del domicilio."
    loc_actual = _resolver_catalogo(
        correcciones, respuestas, "loc_actual", lambda nombre: catalogos.localidad_id(nombre, prov_actual)
    )
    if loc_actual is not None:
        payload["loc_actual"] = loc_actual
    else:
        faltantes["loc_actual"] = "La localidad no coincide con el catálogo de SIIS: elegila de la lista."

    barrio = correcciones.get("barrio_actual") or respuestas.get("barrio_actual") or ""
    barrio = " ".join(str(barrio).split())
    if barrio.isdigit():
        barrio = f"Barrio {barrio}"
    if len(barrio) >= BARRIO_MINIMO:
        payload["barrio_actual"] = barrio[:LARGO_TEXTO]
    else:
        faltantes["barrio_actual"] = "El barrio debe tener al menos 4 caracteres."

    direccion = parsear_direccion(respuestas.get("calle_altura", ""))
    calle = correcciones.get("calle_actual") or direccion["calle"]
    nro = correcciones.get("nro_actual", direccion["nro"])
    if not _altura_valida(nro) and not _con_valor(correcciones.get("calle_actual")):
        # Sin altura, el domicilio viaja como aproximado (Cambio 89). La
        # corrección del coordinador queda afuera de la regla: si alguien se
        # tomó el trabajo de escribir la calle a mano, esa gana.
        calle, nro = CALLE_SIN_NUMERO, ALTURA_SIN_NUMERO
    elif not _altura_valida(nro):
        nro = ALTURA_SIN_NUMERO
    if calle:
        payload["calle_actual"] = str(calle)[:LARGO_TEXTO]
    else:
        faltantes["calle_actual"] = "Falta la calle del domicilio."
    payload["nro_actual"] = int(nro)
    piso = correcciones.get("piso_actual", direccion["piso"])
    if _con_valor(piso):
        payload["piso_actual"] = int(piso)
    dpto = correcciones.get("dpto_actual", direccion["dpto"])
    if dpto:
        payload["dpto_actual"] = str(dpto).strip().upper()[:2]

    # --- Nacimiento ---
    prov_nacim = _resolver_catalogo(correcciones, respuestas, "prov_nacim", catalogos.provincia_id)
    if prov_nacim is not None:
        payload["prov_nacim"] = prov_nacim
    else:
        faltantes["prov_nacim"] = "Falta la provincia de nacimiento."
    loc_nacim = _resolver_catalogo(
        correcciones, respuestas, "loc_nacim", lambda nombre: catalogos.localidad_id(nombre, prov_nacim)
    )
    if loc_nacim is not None:
        payload["loc_nacim"] = loc_nacim
    else:
        faltantes["loc_nacim"] = "Falta la localidad de nacimiento."

    # --- Contacto (opcionales) ---
    celular = normalizar_celular(formulario.celular)
    if celular:
        payload["celular"] = int(celular)
    if formulario.email_contacto:
        payload["correo_electron"] = str(formulario.email_contacto).strip()[:LARGO_TEXTO]

    # --- Programa ---
    # Los tres ids salen del programa vinculado, pero la corrección del caso los
    # pisa: un programa mal configurado no puede dejar a la persona sin salida.
    for campo, valor_segmento, valor_programa, motivo in (
        (
            # El plan es uno solo por programa: no se carga por segmento. El
            # valor efectivo ya contempla el override del programa (Cambio 82).
            "id_plan_soc",
            None,
            programa.siis_id_plan_soc_efectivo if programa else None,
            "El segmento no tiene un programa SIIS configurado.",
        ),
        (
            "jurid",
            segmento.siis_jurid,
            programa.siis_jurid_efectivo if programa else None,
            "No hay jurisdicción: cargala en el segmento o en el programa.",
        ),
        (
            "id_fun_x_plan",
            segmento.siis_id_fun_x_plan,
            programa.siis_funcion_id if programa else None,
            "No hay función por plan: cargala en el segmento o configurala en el programa.",
        ),
    ):
        # Cambio 82: manda la corrección del caso; después lo cargado a mano en
        # el segmento; y recién al final lo que trae el programa vinculado.
        try:
            payload[campo] = int(_primero_con_valor(correcciones.get(campo), valor_segmento, valor_programa))
        except (TypeError, ValueError):
            faltantes[campo] = f"{motivo} También podés completarlo en «Completar datos para SIIS»."

    # --- Apoderado (condicional: menor de 18 a la fecha del envío) ---
    if nacimiento and _edad(nacimiento, hoy) < MAYORIA_DE_EDAD:
        payload.update(_apoderado(formulario, faltantes, correcciones))

    return payload, faltantes


# ---------------------------------------------------------------------------
# Servicio
# ---------------------------------------------------------------------------
# Los dos destinos posibles del alta. «tabla» no llama a la API: deja el payload
# en la tabla intermedia de este lado para revisarlo, o para que el organismo lo
# levante con un proceso propio.
DESTINO_SIIS = "siis"
DESTINO_TABLA = "tabla"
DESTINOS = (DESTINO_SIIS, DESTINO_TABLA)

# Las columnas de ``AltaIntermediaSIIS`` que son campos del payload. El orden es
# el del manual M2M; las fechas se guardan como ``date`` y vuelven en ISO.
CAMPOS_TABLA = (
    "tdoc", "dni", "cuil_pref", "cuil_dig", "apellido", "nombre", "sexo", "est_civil",
    "fecha_nacim", "prov_nacim", "loc_nacim", "celular", "correo_electron",
    "prov_actual", "loc_actual", "barrio_actual", "calle_actual", "nro_actual",
    "piso_actual", "dpto_actual", "id_plan_soc", "jurid", "id_fun_x_plan",
    "dni_apoderado", "cuil_pref_apoderado", "cuil_dig_apoderado", "apellido_apoderado",
    "nombre_apoderado", "sexo_apoderado", "fecha_nacim_apoderado",
)  # fmt: skip
CAMPOS_FECHA = ("fecha_nacim", "fecha_nacim_apoderado")


def _base_envio(formulario, solicitado_por):
    """Los datos de auditoría del ``EnvioSIIS``, sin el payload."""
    programa = formulario.relevamiento.convocatoria.segmento.programa
    return {
        "formulario": formulario,
        "id_programa": programa.siis_id_plan_soc_efectivo if programa else None,
        "id_funcion": programa.siis_funcion_id if programa else None,
        "documento": str(formulario.ciudadano.dni if formulario.ciudadano_id else "")[:20],
        "solicitado_por": solicitado_por,
    }


class CasoYaInformado(Exception):
    """El caso ya tiene un envío vigente: no hay nada que mandar.

    Lleva el ``EnvioSIIS`` que lo ocupa, para que quien llama lo muestre.
    """

    def __init__(self, envio):
        self.envio = envio
        super().__init__(f"El caso #{envio.formulario_id} ya tiene un envío vigente ({envio.estado}).")


# SIIS-02 · Cómo se cierra un intento según lo que contestó SIIS.
# ``vigente`` queda en True cuando el caso sigue ocupado: o hay alta, o no
# sabemos si la hay. ``None`` libera el caso para un reintento.
CIERRE_POR_RESULTADO = {
    RESULTADO_OK: (EnvioSIIS.Estado.ENVIADO, True),
    RESULTADO_NO_ENVIADO: (EnvioSIIS.Estado.ERROR, None),
    RESULTADO_RECHAZADO: (EnvioSIIS.Estado.RECHAZADO, None),
    RESULTADO_INCIERTO: (EnvioSIIS.Estado.INCIERTO, True),
}


def _estado_final(resultado):
    """``(estado, vigente)`` del cierre de un intento."""
    if resultado.get("success"):
        return CIERRE_POR_RESULTADO[RESULTADO_OK]
    clave = resultado.get("resultado")
    if clave in CIERRE_POR_RESULTADO:
        return CIERRE_POR_RESULTADO[clave]
    # Un cliente viejo (o un mock de test) sin ``resultado``: se cae al criterio
    # anterior, que es el conservador salvo para los reintentables declarados.
    return CIERRE_POR_RESULTADO[RESULTADO_NO_ENVIADO if resultado.get("reintentable") else RESULTADO_RECHAZADO]


def _estados_validos(exigir_aprobado, estados_permitidos):
    if estados_permitidos:
        return set(estados_permitidos)
    if exigir_aprobado:
        return {Formulario.Estado.APROBADO}
    return None


def _reservar(formulario, base, payload, faltantes, *, exigir_aprobado=True, estados_permitidos=None):
    """Toma el caso para este intento y devuelve el ``EnvioSIIS`` ``EN_PROCESO``.

    Es el corazón de SIIS-01. Dura milisegundos y **no hay ningún HTTP adentro**:
    con el ``read_timeout`` de 10 s de la base de ECOM, mantener el lock de una
    fila mientras se espera a SIIS (hasta 40 s) mata al segundo request.

    Tres capas, porque ninguna alcanza sola:

    1. ``select_for_update`` sobre la fila del **caso**: serializa a los dos
       candidatos y, de paso, relee el estado (SIIS-04: un caso que pasó a BAJA
       entre que se hidrató y su turno no se informa).
    2. la relectura de ``vigente`` ya con el lock tomado: en READ COMMITTED el
       segundo en entrar ve lo que el primero commiteó.
    3. el índice único, para lo que el lock no cubre (dos pods, un caso que
       cambió de fila, una corrida vieja).

    Lanza :class:`CasoYaInformado` si el caso está ocupado y ``ValueError`` si su
    estado no habilita el envío. Devuelve un ``EnvioSIIS`` ya cerrado
    (``INCOMPLETO`` / ``RECHAZADO`` por duplicado local) cuando no hay nada que
    mandar, o uno ``EN_PROCESO`` cuando sí.
    """
    validos = _estados_validos(exigir_aprobado, estados_permitidos)
    with transaction.atomic():
        estado = (
            Formulario.objects.select_for_update().filter(pk=formulario.pk).values_list("estado", flat=True).first()
        )
        if estado is None:
            raise ValueError("El caso ya no existe.")
        if validos is not None and estado not in validos:
            raise ValueError("Solo se informan a SIIS los casos aprobados.")
        vigente = EnvioSIIS.objects.filter(formulario_id=formulario.pk, vigente=True).first()
        if vigente is not None:
            raise CasoYaInformado(vigente)
        if faltantes:
            return EnvioSIIS.objects.create(
                estado=EnvioSIIS.Estado.INCOMPLETO,
                codigo_error="DATOS_INCOMPLETOS",
                detalles=faltantes,
                payload=payload,
                resuelto_en=timezone.now(),
                **base,
            )
        duplicado = _duplicado_local(formulario, base)
        if duplicado is not None:
            return duplicado
        try:
            # Savepoint propio: un IntegrityError envenena la transacción, y acá
            # adentro puede haber una externa (la vista que aprueba, por ejemplo).
            with transaction.atomic():
                return EnvioSIIS.objects.create(
                    estado=EnvioSIIS.Estado.EN_PROCESO, vigente=True, payload=payload, **base
                )
        except IntegrityError:
            otro = EnvioSIIS.objects.filter(formulario_id=formulario.pk, vigente=True).first()
            if otro is None:
                raise
            raise CasoYaInformado(otro) from None


def _duplicado_local(formulario, base):
    """SIIS-05: la misma persona y el mismo plan, informados desde otro caso.

    RN-P5 deduplica por convocatoria y la idempotencia del envío es por caso, así
    que dos casos distintos del mismo DNI en el mismo plan daban dos altas. Es un
    rechazo **local**: no se llama a SIIS (default D-S05, «una sola alta por
    persona y plan»).
    """
    documento, plan = base["documento"], base["id_programa"]
    if not documento or plan is None:
        return None
    otro = (
        EnvioSIIS.objects.filter(documento=documento, id_programa=plan, vigente=True)
        .exclude(formulario_id=formulario.pk)
        .values_list("formulario_id", flat=True)
        .first()
    )
    if otro is None:
        return None
    return EnvioSIIS.objects.create(
        estado=EnvioSIIS.Estado.RECHAZADO,
        codigo_error="DUPLICADO_LOCAL",
        detalles={"_": [f"Ya informado a SIIS en el caso #{otro} con el mismo documento y plan."]},
        resuelto_en=timezone.now(),
        **base,
    )


def _cerrar(envio, resultado):
    """Deja el intento en su estado final. Se cierra **una sola vez**.

    El ``UPDATE`` filtra por ``estado=EN_PROCESO``: si mientras el POST estaba en
    vuelo una conciliación tocó la fila (``conciliar_envios_siis``), no se pisa
    lo que decidió una persona con la respuesta de ECOM en la mano.
    """
    estado, vigente = _estado_final(resultado)
    detalles = resultado.get("detalles") or {}
    if not detalles and resultado.get("error"):
        detalles = {"_": [str(resultado["error"])]}
    EnvioSIIS.objects.filter(pk=envio.pk, estado=EnvioSIIS.Estado.EN_PROCESO).update(
        estado=estado,
        vigente=vigente,
        siis_id=resultado.get("siis_id"),
        codigo_error=str(resultado.get("codigo") or "")[:40],
        detalles=detalles,
        respuesta=resultado.get("data") or {},
        resuelto_en=timezone.now(),
    )
    envio.refresh_from_db()
    return envio


def enviar_beneficiario_a_siis(
    formulario, solicitado_por, catalogos=None, exigir_aprobado=True, estados_permitidos=None
):
    """Da de alta al beneficiario en SIIS y **siempre** deja un ``EnvioSIIS``.

    Idempotente de verdad (SIIS-01): mientras el caso tenga un envío vigente
    —``ENVIADO``, ``EN_PROCESO`` o ``INCIERTO``— no se vuelve a llamar a la API,
    que no deduplica ni permite dar de baja. Devuelve ese envío vigente.

    Nunca lanza por fallas de red ni de SIIS: eso queda registrado como ``ERROR``
    (reintentable) o ``INCIERTO`` (no reintentable, se concilia). Sí lanza
    ``ValueError`` si el caso no está en un estado que habilite el envío, porque
    eso es un error de programación del que llama.

    ``exigir_aprobado=False`` levanta esa guarda y **solo lo usa el comando de
    alta masiva** (``enviar_casos_siis``), que pide los estados por nombre; con
    ``estados_permitidos`` la relectura bajo lock exige que el estado siga dentro
    de los pedidos (SIIS-04). No es un atajo: informar un caso que nadie revisó,
    o que la provincia rechazó, lo registra como beneficiario en SIIS. La
    revisión desde la pantalla siempre exige APROBADO.

    **No llamarla dentro de una transacción**: el ``EN_PROCESO`` tiene que estar
    commiteado antes del POST para que el segundo candidato lo vea.
    """
    vigente = formulario.envios_sis.filter(vigente=True).first()
    if vigente is not None:
        # Atajo barato: evita armar el payload (6-8 consultas) de un caso que ya
        # está ocupado. La respuesta firme la da ``_reservar`` bajo el lock.
        return vigente

    base = _base_envio(formulario, solicitado_por)
    try:
        payload, faltantes = armar_payload(formulario, catalogos=catalogos)
    except CatalogoNoDisponible as exc:
        return EnvioSIIS.objects.create(
            estado=EnvioSIIS.Estado.ERROR,
            codigo_error="ERROR_TECNICO",
            detalles={"catalogo": [str(exc)]},
            resuelto_en=timezone.now(),
            **base,
        )
    # El registro audita lo que se mandó de verdad: los ids pueden venir del
    # segmento o de la corrección del caso, no solo del programa (Cambio 82).
    base["id_programa"] = payload.get("id_plan_soc", base["id_programa"])
    base["id_funcion"] = payload.get("id_fun_x_plan", base["id_funcion"])
    return _mandar_a_siis(
        formulario,
        payload,
        faltantes,
        base,
        exigir_aprobado=exigir_aprobado,
        estados_permitidos=estados_permitidos,
    )


def _mandar_a_siis(formulario, payload, faltantes, base, *, exigir_aprobado=True, estados_permitidos=None):
    """Reserva el caso, llama a la API y cierra el intento.

    Aparte porque la sincronización de la tabla intermedia manda un payload que
    ya estaba guardado, en vez de armarlo del caso, y la reserva y el registro
    del intento tienen que ser idénticos en los dos caminos (SIIS-01 y SIIS-04
    cubren también esa séptima vía).
    """
    try:
        envio = _reservar(
            formulario,
            base,
            payload,
            faltantes,
            exigir_aprobado=exigir_aprobado,
            estados_permitidos=estados_permitidos,
        )
    except CasoYaInformado as ocupado:
        return ocupado.envio
    if envio.estado != EnvioSIIS.Estado.EN_PROCESO:
        return envio
    # El HTTP va fuera de toda transacción: el ``EN_PROCESO`` ya está commiteado,
    # así que cualquier otro camino que entre mientras tanto lo ve y se retira.
    return _cerrar(envio, cargar_beneficiario(payload))


def guardar_en_tabla_intermedia(formulario, solicitado_por, catalogos=None, exigir_aprobado=True):
    """Deja el alta en la tabla intermedia de este lado. **No llama a SIIS.**

    Devuelve ``(alta, envio)``: el ``alta`` cuando se guardó, y el ``envio``
    cuando no se pudo --payload incompleto o catálogo caído-- con el mismo
    registro que dejaría un intento real, para que el caso aparezca en los
    resúmenes por el motivo correcto.

    Un caso ya informado a SIIS no se guarda: ya está del otro lado.
    """
    from programas.models import AltaIntermediaSIIS

    if exigir_aprobado and formulario.estado != Formulario.Estado.APROBADO:
        raise ValueError("Solo se informan a SIIS los casos aprobados.")
    if formulario.envios_sis.filter(vigente=True).exists():
        return None, None

    base = _base_envio(formulario, solicitado_por)
    try:
        payload, faltantes = armar_payload(formulario, catalogos=catalogos)
    except CatalogoNoDisponible as exc:
        return None, EnvioSIIS.objects.create(
            estado=EnvioSIIS.Estado.ERROR,
            codigo_error="ERROR_TECNICO",
            detalles={"catalogo": [str(exc)]},
            resuelto_en=timezone.now(),
            **base,
        )
    base["id_programa"] = payload.get("id_plan_soc", base["id_programa"])
    base["id_funcion"] = payload.get("id_fun_x_plan", base["id_funcion"])
    if faltantes:
        return None, EnvioSIIS.objects.create(
            estado=EnvioSIIS.Estado.INCOMPLETO,
            codigo_error="DATOS_INCOMPLETOS",
            detalles=faltantes,
            payload=payload,
            resuelto_en=timezone.now(),
            **base,
        )

    valores = {campo: payload.get(campo) for campo in CAMPOS_TABLA}
    for campo in CAMPOS_FECHA:
        valores[campo] = _fecha_corregida(valores[campo])
    for campo, valor in valores.items():
        if valor is None and campo in ("apellido", "nombre", "sexo", "celular", "correo_electron",
                                       "barrio_actual", "calle_actual", "dpto_actual",
                                       "apellido_apoderado", "nombre_apoderado", "sexo_apoderado"):  # fmt: skip
            valores[campo] = ""
    valores["sincronizado"] = False
    valores["sincronizado_en"] = None
    valores["envio"] = None
    valores["guardado_por"] = solicitado_por
    alta, _ = AltaIntermediaSIIS.objects.update_or_create(formulario=formulario, defaults=valores)
    return alta, None


def payload_de(alta):
    """El payload tal como se guardó, listo para mandar. Los vacíos no viajan."""
    payload = {}
    for campo in CAMPOS_TABLA:
        valor = getattr(alta, campo)
        if valor is None or valor == "":
            continue
        payload[campo] = valor.isoformat() if campo in CAMPOS_FECHA else valor
    return payload


def sincronizar_tabla_intermedia(solicitado_por, limite=None, al_terminar=None):
    """Manda a SIIS lo que quedó pendiente en la tabla intermedia local.

    Es lo que evita que un alta se quede guardada acá para siempre: una corrida
    con destino SIIS vacía esto **antes** de seguir con los casos nuevos.

    Se manda el payload **tal como se guardó**, no uno recalculado: es lo que se
    revisó. Si entre medio se corrigieron datos, hay que volver a guardarlo con
    ``--destino tabla`` para regenerarlo.

    Devuelve ``{"altas": n, "rechazadas": n, "errores": n, "no_aprobables": n}``.
    ``al_terminar`` se llama con cada ``(alta, envio)`` para informar el avance.

    El estado del caso se **relee bajo lock** antes de mandar (SIIS-04): una fila
    guardada hace días puede corresponder a un caso que desde entonces pasó a
    BAJA, y el payload guardado no lo sabe. Esos casos se cuentan aparte y la
    fila queda pendiente: que una persona decida si se regenera o se descarta.
    """
    from programas.models import AltaIntermediaSIIS

    cuenta = {"altas": 0, "rechazadas": 0, "errores": 0, "no_aprobables": 0}
    pendientes = (
        AltaIntermediaSIIS.objects.filter(sincronizado=False)
        .select_related("formulario__ciudadano", "formulario__relevamiento__convocatoria__segmento__programa")
        .order_by("pk")
    )
    if limite:
        pendientes = pendientes[:limite]
    for alta in list(pendientes):
        formulario = alta.formulario
        if formulario.envios_sis.filter(vigente=True).exists():
            # Alguien lo mandó por otro camino: la fila ya no tiene nada que hacer.
            alta.sincronizado = True
            alta.sincronizado_en = timezone.now()
            alta.save(update_fields=["sincronizado", "sincronizado_en", "modificado"])
            continue
        try:
            envio = _mandar_a_siis(formulario, payload_de(alta), {}, _base_envio(formulario, solicitado_por))
        except ValueError:
            cuenta["no_aprobables"] += 1
            continue
        if envio.estado == EnvioSIIS.Estado.ENVIADO:
            alta.sincronizado = True
            alta.sincronizado_en = timezone.now()
            alta.envio = envio
            alta.save(update_fields=["sincronizado", "sincronizado_en", "envio", "modificado"])
            cuenta["altas"] += 1
        elif envio.estado == EnvioSIIS.Estado.RECHAZADO:
            cuenta["rechazadas"] += 1
        else:
            cuenta["errores"] += 1
        if al_terminar is not None:
            al_terminar(alta, envio)
    return cuenta


def mensaje_envio(envio):
    """``(nivel, texto)`` para el toast de la vista; ``nivel`` es un método de ``messages``."""
    if envio.estado == EnvioSIIS.Estado.ENVIADO:
        sufijo = f" (ID {envio.siis_id})" if envio.siis_id else ""
        return "success", f"Informado a SIIS{sufijo}."
    if envio.estado == EnvioSIIS.Estado.EN_PROCESO and not envio.incierto:
        desde = timezone.localtime(envio.creado).strftime("%H:%M") if envio.creado else "recién"
        return "info", f"El alta ya se está informando a SIIS (desde {desde}). Recargá en un minuto."
    if envio.estado == EnvioSIIS.Estado.INCIERTO or envio.estado == EnvioSIIS.Estado.EN_PROCESO:
        return (
            "warning",
            "No sabemos si SIIS registró el alta: no se reenvía hasta verificarlo con SIIS.",
        )
    if envio.estado == EnvioSIIS.Estado.RECHAZADO and envio.codigo_error == "DUPLICADO_LOCAL":
        return (
            "warning",
            "Esta persona ya fue informada a SIIS en otro caso del mismo plan: no se vuelve a dar de alta.",
        )
    if envio.estado == EnvioSIIS.Estado.INCOMPLETO:
        cantidad = len(envio.detalles or {})
        return "warning", f"El envío a SIIS quedó pendiente: faltan {cantidad} dato(s). Completalos desde el caso."
    if envio.estado == EnvioSIIS.Estado.RECHAZADO:
        return "warning", "SIIS rechazó el alta del beneficiario: revisá los datos señalados y reenviá."
    return "error", "SIIS no respondió correctamente; el envío quedó registrado para reintentar."
