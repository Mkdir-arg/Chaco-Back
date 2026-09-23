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

from programas.models import EnvioSIIS, Formulario, PreguntaGlobal
from programas.services.dashboard_becas import respuesta_de
from programas.services.siis import SiisCatalogError, cargar_beneficiario, catalogo

TDOC_DNI = 1
BARRIO_MINIMO = 4
LARGO_TEXTO = 50

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


def _digitos(valor):
    return re.sub(r"\D", "", str(valor or ""))


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


def _apoderado(formulario, faltantes):
    """Los 7 campos condicionales del manual (sección 4): solo para menores de 18."""
    if formulario.apoderado_ciudadano_id:
        a = formulario.apoderado_ciudadano
        dni, nombre, apellido, sexo, nacimiento = a.dni, a.nombre, a.apellido, a.genero, a.fecha_nacimiento
    else:
        dni, nombre, apellido = formulario.apoderado_dni, formulario.apoderado_nombre, formulario.apoderado_apellido
        sexo, nacimiento = formulario.apoderado_genero, formulario.apoderado_fecha_nacimiento
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
    celular = _digitos(formulario.celular)
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
        payload.update(_apoderado(formulario, faltantes))

    return payload, faltantes


# ---------------------------------------------------------------------------
# Servicio
# ---------------------------------------------------------------------------
def enviar_beneficiario_a_siis(formulario, solicitado_por, catalogos=None, exigir_aprobado=True):
    """Da de alta al beneficiario en SIIS y **siempre** deja un ``EnvioSIIS``.

    Idempotente: un caso ya ``ENVIADO`` no se vuelve a mandar (la API no
    deduplica). Nunca lanza por fallas de red ni de SIIS: eso queda registrado
    como ``ERROR`` reintentable. Sí lanza ``ValueError`` si el caso no está
    aprobado, porque eso es un error de programación del que llama.

    ``exigir_aprobado=False`` levanta esa guarda y **solo lo usa el comando de
    alta masiva** (``enviar_casos_siis``), que pide los estados por nombre. No
    es un atajo: informar un caso que nadie revisó, o que la provincia rechazó,
    lo registra como beneficiario en SIIS; la API no deduplica y desde acá no
    hay forma de darlo de baja. La revisión desde la pantalla siempre lo exige.
    """
    if exigir_aprobado and formulario.estado != Formulario.Estado.APROBADO:
        raise ValueError("Solo se informan a SIIS los casos aprobados.")
    vigente = formulario.envios_sis.filter(estado=EnvioSIIS.Estado.ENVIADO).order_by("-creado", "-pk").first()
    if vigente:
        return vigente

    programa = formulario.relevamiento.convocatoria.segmento.programa
    base = {
        "formulario": formulario,
        "id_programa": programa.siis_id_plan_soc_efectivo if programa else None,
        "id_funcion": programa.siis_funcion_id if programa else None,
        "documento": str(formulario.ciudadano.dni if formulario.ciudadano_id else "")[:20],
        "solicitado_por": solicitado_por,
    }
    try:
        payload, faltantes = armar_payload(formulario, catalogos=catalogos)
    except CatalogoNoDisponible as exc:
        return EnvioSIIS.objects.create(
            estado=EnvioSIIS.Estado.ERROR, codigo_error="ERROR_TECNICO", detalles={"catalogo": [str(exc)]}, **base
        )
    # El registro audita lo que se mandó de verdad: los ids pueden venir del
    # segmento o de la corrección del caso, no solo del programa (Cambio 82).
    base["id_programa"] = payload.get("id_plan_soc", base["id_programa"])
    base["id_funcion"] = payload.get("id_fun_x_plan", base["id_funcion"])
    if faltantes:
        return EnvioSIIS.objects.create(
            estado=EnvioSIIS.Estado.INCOMPLETO,
            codigo_error="DATOS_INCOMPLETOS",
            detalles=faltantes,
            payload=payload,
            **base,
        )

    resultado = cargar_beneficiario(payload)
    if resultado.get("success"):
        return EnvioSIIS.objects.create(
            estado=EnvioSIIS.Estado.ENVIADO,
            siis_id=resultado.get("siis_id"),
            payload=payload,
            respuesta=resultado.get("data") or {},
            **base,
        )
    estado = EnvioSIIS.Estado.ERROR if resultado.get("reintentable") else EnvioSIIS.Estado.RECHAZADO
    detalles = resultado.get("detalles") or {}
    if not detalles and resultado.get("error"):
        detalles = {"_": [str(resultado["error"])]}
    return EnvioSIIS.objects.create(
        estado=estado,
        codigo_error=str(resultado.get("codigo") or "")[:40],
        detalles=detalles,
        payload=payload,
        respuesta=resultado.get("data") or {},
        **base,
    )


def mensaje_envio(envio):
    """``(nivel, texto)`` para el toast de la vista; ``nivel`` es un método de ``messages``."""
    if envio.estado == EnvioSIIS.Estado.ENVIADO:
        sufijo = f" (ID {envio.siis_id})" if envio.siis_id else ""
        return "success", f"Informado a SIIS{sufijo}."
    if envio.estado == EnvioSIIS.Estado.INCOMPLETO:
        cantidad = len(envio.detalles or {})
        return "warning", f"El envío a SIIS quedó pendiente: faltan {cantidad} dato(s). Completalos desde el caso."
    if envio.estado == EnvioSIIS.Estado.RECHAZADO:
        return "warning", "SIIS rechazó el alta del beneficiario: revisá los datos señalados y reenviá."
    return "error", "SIIS no respondió correctamente; el envío quedó registrado para reintentar."
