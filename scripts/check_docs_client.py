#!/usr/bin/env python
"""Gate de `docs/client/`: nada se publica en internet sin que alguien lo mire (RED-64).

`docs/client/` se construye con MkDocs y se publica en
https://mkdir-arg.github.io/Chaco-Back/ —un sitio **público**, `"public": true` según la
API de Pages— en cada push a `development` que toque esa carpeta. Entre el commit y la
URL pública pasa menos de un minuto y no hay nadie en el medio: `/pm:reporte`,
`/pm:minuta` y `/analisis:publicar` escriben ahí.

La mitad humana de la ficha es el `environment:` del job con *required reviewers*, que lo
configura el dueño del repo. Esta es la mitad mecánica, y corre **dos veces**: como paso
del workflow que publica (antes de construir) y como test de la suite
(`core/tests/test_docs_client_publicacion.py`), para que el hallazgo aparezca en el PR y
no recién cuando el dato ya está en internet.

    python scripts/check_docs_client.py              # lo que publica MkDocs → bloquea
    python scripts/check_docs_client.py --json       # la misma salida, para un test
    python scripts/check_docs_client.py --todo-docs  # `docs/` entero + los .md de la raíz

**Dos alcances, la misma regla.** El repositorio es público: un dato de una persona en
`docs/internal/` es tan legible en GitHub como uno en `docs/client/`. La diferencia es
que lo primero se lee navegando el repo y lo segundo sale además como página web. El
alcance estricto (el default) mira lo que MkDocs copia al sitio y **bloquea**; el
`--todo-docs` barre `docs/` entero y los `.md` de la raíz, y va **no bloqueante** en el
PR porque sobre esa superficie quedan falsos positivos que no se pueden sacar sin
aflojar la regla (los números, en los Cambios 207 y 209 de `requerimientos.md`).

**No solo `.md`.** MkDocs copia al sitio *todo* lo que haya en `docs_dir`, así que un
`.html` de mockup se publica igual que una página: se revisan todas las extensiones de
`EXTENSIONES_DE_TEXTO`. La regla del nav, en cambio, es solo para `.md`, que es lo único
que MkDocs pone en un menú.

Cinco reglas. Alcanza con que dispare una.

1. **Persona identificable.** Un documento (7 u 8 dígitos, con o sin puntos) en una línea
   que además nombra el documento —«DNI», «documento», `numeroDocumento`—, o un CUIL/CUIT
   bien formado en cualquier lado. El CUIL no necesita palabra cerca: el prefijo
   `20/23/24/27` más 9 dígitos ya lo identifica solo.

   La palabra no siempre está en la **misma** línea, y ahí es donde se publica un padrón
   entero sin que el gate diga nada: en una tabla o en un CSV la dice el **encabezado**
   (`| Apellido | Nombre | Documento |`, `apellido,nombre,dni`, `<th>Apellido</th>…`) y
   las filas de abajo ya no la repiten. Así que un documento también es hallazgo cuando a
   menos de `VENTANA_PADRON` líneas **arriba** hay un encabezado de padrón —una fila de
   etiquetas donde una nombra el documento y otra nombra a la persona—, o cuando viene
   entre paréntesis detrás de un nombre propio («Perez Ana (30111222) cobró la beca»), que
   es como se escribe un caso concreto en prosa.

   Lo que cuenta como **fila** es lo separado como una tabla: `|`, un tab, o celdas
   `<th>`/`<td>` de una misma `<tr>`, que es como se publica un padrón en un mockup. La
   coma y el punto y coma separan celdas **y** enumeran en prosa, así que ahí se pide que
   la línea no se delate como oración —que no termine en punto ni anuncie la lista con
   dos puntos— y que sus celdas no tengan verbo; si no, la prosa que *enumera* las
   columnas («el padrón trae apellido, nombre, documento y domicilio») convertía en
   hallazgo al primer número de siete dígitos del párrafo siguiente.

2. **Fecha de nacimiento rodeada de identidad.** Una fecha en una línea que la nombra
   («fecha de nacimiento», `fechaNacimiento`) con campos de identidad —apellido, nombres,
   CUIL, domicilio, documento— a menos de `VENTANA` líneas. Sola no dice nada; pegada a
   un nombre y un documento es la mitad de una identidad. Es lo que quedaba de la
   respuesta de RENAPER después de la primera pasada de saneamiento.

3. **Domicilio con calle y número.** Una calle con altura en la misma línea
   («Calle Falsa 123»), o un `calle:` con valor real y un `numero:` a menos de
   `VENTANA_DOMICILIO` líneas, que es la forma en que lo devuelven RENAPER y Personas.

4. **Secreto con valor.** Una clave que se llama `password`/`contraseña`/`secret`/`token`/
   `api_key` seguida de `:` o `=` y de un valor que **no** es un marcador de posición. Lo
   que se mira es el valor, no la clave.

5. **Archivo fuera del nav.** MkDocs construye **todo** `docs_dir`, esté o no en el menú:
   un `.md` suelto queda publicado y accesible por URL sin aparecer en ningún índice, que
   es la peor forma de publicar algo sin querer. Lo declarado a propósito va en el
   `not_in_nav` de `mkdocs.yml`, donde se ve.

**Los marcadores de posición no son hallazgos.** Un documento de dígitos repetidos
(`00000000`) o escrito sobre la secuencia `1234567…`, un CUIL con el cuerpo `12345678`,
la fecha `01/01/2000` y «Calle Falsa» son los valores con los que este repo escribe sus
ejemplos: reconocerlos es lo que deja al gate en 0 sin una lista de archivos perdonados.
Es una regla sobre el **valor**, auditable en una línea, no un escondite por ruta.

No hay archivo de excepciones, por el mismo motivo que `check_datos_personales.py` no
tiene globs: una lista de perdonados es un escondite. Un falso positivo se arregla
escribiendo el dato como marcador, no agregando la ruta a ningún lado.

Salida: una línea `::error file=…,line=…::` por hallazgo —GitHub la muestra sobre el
archivo en la pestaña del PR— y código 1. **Nunca imprime el valor que encontró**, solo
dice qué regla disparó: el log de Actions de un repo público también es público.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MKDOCS = RAIZ / "mkdocs.yml"

#: MkDocs copia al sitio todo lo que encuentra en `docs_dir`, no solo las páginas. Lo que
#: no es texto (una imagen, un PDF) no se revisa: para eso está `check_datos_personales`.
EXTENSIONES_DE_TEXTO = frozenset({".md", ".html", ".htm", ".json", ".csv", ".txt", ".yml", ".yaml"})

#: Un documento argentino: 7 u 8 dígitos, con los puntos de miles opcionales. El
#: `(?!\.?\d)` del final corta los números más largos (un CUIL, un id de trámite) sin
#: comerse el punto que cierra la oración, y los bordes de `\w`/`-` lo sacan del medio de
#: un UUID (`…-90719590f027`), que es de donde salían los falsos positivos más molestos.
#: No es una regla de validación —esa vive una sola vez, en `core.dni` (RED-48)—: acá se
#: buscan documentos **publicados**, igual que en `check_datos_personales.py`.
DOCUMENTO = re.compile(r"(?<![\w.-])(?:\d{1,2}\.\d{3}\.\d{3}|\d{7,8})(?!\.?\d)(?![A-Za-z_-])")  # regla-dni: ok
#: Lo que sigue al número y lo convierte en otra cosa: un tamaño, una duración, un conteo.
#: «`scripts/DatosPersonas.sql` (2.874.634 bytes … DNI, CUIL…)» era un hallazgo del gate.
UNIDAD = re.compile(
    r"(?i)^\s*(?:bytes?|kib|mib|gib|[kmg]b|ms|µs|us|seg(?:undos?)?|px|em|rem|pt|%"
    r"|l[íi]neas?|filas?|registros?|tuplas?|consultas?|queries|caracteres?|p[áa]ginas?"
    r"|personas?|archivos?|hallazgos?|horas?|h|LOC)\b"
)
#: La palabra que convierte a ese número en un documento de alguien. Se busca sobre la
#: línea con las mayúsculas separadas, así `numeroDocumento` cuenta igual que «documento»:
#: con `\b` a la izquierda, la `o` de `numero` tapaba la clave que más aparece en los JSON.
NOMBRA_DOCUMENTO = re.compile(r"(?i)\b(?:dni|d\.n\.i\.?|documento|nro\.?\s*doc)\b")
#: CUIL/CUIT: prefijo de persona o empresa + 8 dígitos + verificador. Se identifica solo.
CUIL = re.compile(r"(?<![\w.-])(?:20|23|24|27|30|33|34)[-\s]?\d{8}[-\s]?\d(?!\d)(?![A-Za-z])")

#: Lo que separa las celdas de una fila: una tabla markdown, un CSV, un TSV.
SEPARADOR_DE_CELDAS = re.compile(r"[|,;\t]")
#: De esos separadores, los que **solo** aparecen separando celdas. Un `|` o un tab no
#: tienen otro uso en una línea de documentación.
SEPARADOR_INEQUIVOCO = re.compile(r"[|\t]")
#: La coma y el punto y coma separan celdas **y** enumeran en prosa. Con ellos hay que
#: mirar la línea antes de llamarla fila.
SEPARADOR_AMBIGUO = re.compile(r"[,;]")
#: Lo que delata a la enumeración en prosa, y nunca aparece en una fila de CSV ni de
#: tabla: que la línea **termine en punto**, o que los dos puntos anuncien la lista antes
#: de la primera celda («Columnas: apellido, nombre, documento.»). Es la heurística
#: completa de la prosa; no se pide nada más sobre la forma de las celdas que el largo y
#: la ausencia de verbo.
FIN_DE_ORACION = re.compile(r"[.]['\"»)\]]*$")
#: Una fila de padrón no necesita tres columnas: `documento,apellido` ya nombra a una
#: persona y a su documento, que es exactamente lo que `_celdas_nombran_un_padron` exige.
#: Pedir tres perdía los padrones de dos columnas, que son los más fáciles de publicar.
MINIMO_DE_CELDAS_ENUMERADAS = 2
#: Una etiqueta de columna puede tener varias palabras —«apellido y nombre del titular»—;
#: lo que no tiene es largo de oración. No hay tope de palabras: con el verbo afuera y el
#: largo acotado, contar palabras solo perdía encabezados reales.
LARGO_MAXIMO_DE_ETIQUETA = 40
#: Los verbos con los que se escribe esa prosa. Una etiqueta de columna no tiene verbo.
VERBO_DE_PROSA = re.compile(
    r"(?i)\b(?:es|son|era|eran|fue|fueron|ser[áa]n?|est[áa]n?|hay|tiene|tienen|trae|traen"
    r"|lleva|llevan|incluye|incluyen|contiene|contienen|muestra|muestran|guarda|guardan"
    r"|viene|vienen|sale|salen|figura|figuran|aparece|aparecen|devuelve|devuelven"
    r"|publica|publican|usa|usan|pide|piden|necesita|necesitan|arma|arman|deja|dejan)\b"
)
#: Una celda de una tabla HTML. MkDocs copia los `.html` del sitio tal cual, y un padrón
#: escrito en `<table>` no tiene ni `|` ni coma: lo que nombra sus columnas es un `<th>`
#: (o un `<td>`, que es como terminan escritas la mitad de las tablas).
CELDA_HTML = re.compile(r"(?is)<(?P<tag>th|td)\b[^>]*>(?P<texto>.*?)</(?P=tag)>")
#: Solo las de encabezado, para cuando no hay `<tr>` que marque dónde termina la fila.
CELDA_TH = re.compile(r"(?is)<(?P<tag>th)\b[^>]*>(?P<texto>.*?)</(?P=tag)>")
#: Dónde empieza cada fila. El encabezado de un padrón son las celdas de **una misma**
#: fila: leídas todas juntas, una tabla clave-valor —«Documento rector» en una fila,
#: «Nombre del programa» en otra— se convertía en un encabezado de padrón.
SEPARADOR_DE_FILA_HTML = re.compile(r"(?i)<tr\b[^>]*>")
#: El adorno de adentro de la celda (`<span>`, `<a>`…), que no es parte de la etiqueta.
TAG_HTML = re.compile(r"(?s)<[^>]*>")
#: Guarda barata: sin esto, cada línea de cada archivo pagaría el escaneo de la ventana.
MARCA_DE_CELDA_HTML = re.compile(r"(?i)<t[hd]\b")
#: La etiqueta que nombra a la **persona**, que no es la que nombra al documento. Sin una
#: de estas, una enumeración de columnas técnicas no alcanza para llamar padrón a lo que
#: sigue: lo que convierte a una fila de números en un padrón es que arriba diga de quién
#: es cada columna.
NOMBRA_PERSONA = re.compile(
    r"(?i)\b(?:apellidos?|nombres?|cuil|cuit|domicilio|legajo|beneficiari[oa]s?|titular|ciudadan[oa]s?)\b"
)
#: Cuántas filas después del encabezado se miran. No se trata de marcar las mil filas de
#: un padrón —con una alcanza para frenar la publicación— sino de que ninguna tabla corta
#: pase por no repetir la palabra en cada fila.
VENTANA_PADRON = 5
#: «Perez Ana (30111222) cobró la beca»: el documento entre paréntesis detrás de un nombre
#: propio. No hay palabra que lo nombre ni encabezado arriba; lo que lo identifica es el
#: nombre pegado. Se piden **dos** palabras capitalizadas seguidas para que un «Cambio 207
#: (1234567)» o un «Ola 7 (…)» no entre: lo que se busca es un nombre y un apellido.
NOMBRE_PROPIO_CON_DOCUMENTO = re.compile(
    # regla-dni: ok — se busca un documento **publicado**, no se valida uno (igual que
    # `DOCUMENTO` acá arriba y que `check_datos_personales.py`): la regla de validación
    # vive una sola vez, en `core.dni` (RED-48).
    r"[A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑáéíóúüñ'’.-]*\s+[A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑáéíóúüñ'’.-]*\s*"  # regla-dni: ok
    r"[(\[]\s*(?P<doc>\d{1,2}\.\d{3}\.\d{3}|\d{7,8})\s*[)\]]"  # regla-dni: ok
)

#: Un documento que es obviamente inventado: todos los dígitos iguales, o escrito sobre la
#: secuencia `1234567…` (y su reverso), que es con lo que el repo escribe sus ejemplos.
DOCUMENTO_DE_RELLENO = re.compile(r"^(?:(\d)\1{6,7}|0?1234567\d?|0?7654321\d?)$")
#: Un CUIL de ejemplo: prefijo válido sobre un cuerpo que no es de nadie.
CUIL_DE_RELLENO = re.compile(r"^(?:20|23|24|27|30|33|34)(?:12345678|(\d)\1{7})\d$")

#: Una fecha **pegada** a la etiqueta que dice que es un nacimiento: `"fechaNacimiento":
#: "…"`, `<dt>Nacimiento</dt><dd>…`, `Fecha de nacimiento: …`. Entre la etiqueta y el
#: valor solo se admite puntuación o un par de tags: con un hueco libre, cualquier párrafo
#: que *hable* de fechas de nacimiento («una fecha de nacimiento ilegible (15/03/2010)»)
#: entraba como hallazgo, y un gate que marca la prosa se apaga el primer día.
NACIMIENTO_CON_FECHA = re.compile(
    r"(?i)(?:fecha\s*(?:de\s*)?nac\w*|nacimiento|f\.?\s*nac\.?|birth\s*date)"
    r"""(?:["'\]\s:=>|·,-]{0,8}|(?:</?[a-z]{1,4}>){1,3}\s*)"""
    r"(?P<fecha>\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|\d{1,2}-\d{1,2}-\d{4})(?![\d/-])"
)
#: La fecha con la que se escriben los ejemplos. Normalizada a `aaaa-mm-dd` para comparar.
FECHAS_DE_RELLENO = frozenset({"2000-01-01", "1900-01-01", "0001-01-01"})
#: Con qué tiene que estar rodeada una fecha para que sea la de una persona concreta.
CAMPO_DE_IDENTIDAD = re.compile(
    r"(?i)\b(?:dni|d\.n\.i\.?|documento|cuil|cuit|apellido|nombres?|domicilio|calle|legajo)\b"
)
#: Cuántas líneas cuentan como «cerca». Un bloque JSON de identidad entra entero.
VENTANA = 5
VENTANA_DOMICILIO = 3

#: Una calle con altura escrita en prosa: «Calle Montiel 2951», «Av. Sarmiento N.º 150».
#: Sin «ruta»: en este repo esa palabra es una URL («ninguna ruta da 500»), no una calle.
CALLE_CON_NUMERO = re.compile(
    r"(?i)\b(?:calle|avenida|av\.|pasaje|pje\.)\s+"
    r"(?P<nombre>[\wÁÉÍÓÚÜÑáéíóúüñ'.]+(?:\s+[\wÁÉÍÓÚÜÑáéíóúüñ'.]+){0,3}?)\s+"
    r"(?:n[.°º]?\s*)?\d{1,5}(?!\d)"
)
#: La forma en que lo devuelven RENAPER y Personas: la calle en una clave y la altura en
#: otra, un par de líneas más abajo.
VALOR_DE_CALLE = re.compile(
    r'(?i)[\'"]?\b(?:calle|domicilio|direcci[óo]n)[\'"]?\s*[:=]\s*[\'"]?(?P<valor>[^\'",\n]{3,60})'
)
VALOR_DE_ALTURA = re.compile(
    r"(?i)[\'\"]?\b(?:numero|número|nro\.?|altura)[\'\"]?\s*[:=]\s*[\'\"]?(?P<valor>\d{1,5})(?!\d)"
)
#: La calle con la que se escriben los ejemplos, y sus primas.
CALLE_DE_RELLENO = re.compile(r"(?i)\b(?:falsa|falso|ejemplo|example|prueba|placeholder|sin\s+dato|s/d|n/a)\b")

#: Clave que se llama como un secreto, su separador y el valor que le sigue. El
#: `(?!ar[íi]a)` saca «Secretaría» y `test_secretarias.py`, que no son un secreto sino la
#: mitad del organigrama del organismo.
SECRETO = re.compile(
    r"(?i)(?P<clave>[\w.-]*(?:password|passwd|contrase[nñ]a|secret(?!ar[íi]a)|token|api[_-]?key)[\w.-]*)"
    r"\s*[:=]\s*(?P<valor>\S+)"
)
#: `chaco-tokens.css:19` es una referencia a un archivo con su línea, no una clave.
CLAVE_ES_ARCHIVO = re.compile(r"(?i)\.(?:css|js|mjs|py|html?|md|ya?ml|json|txt|sql|png|svg|ts|tsx)$")
#: `var token = json.data.token;` es código, y `json.data` no es el secreto de nadie.
REFERENCIA_DE_CODIGO = re.compile(r"^[A-Za-z_$][\w$]*(?:\.[\w$]+)+[;,)]*$")
#: Un valor que se nombra a sí mismo como descartable. `DJANGO_SECRET_KEY=test-key` es la
#: clave del CI y está escrita en veinte lugares del repo a propósito.
#:
#: Las palabras van **sueltas**, no como subcadena: sin los bordes,
#: `SIIS_API_CLIENT_SECRET=AttestationKe9f3Qx` se perdonaba solo porque adentro de
#: «Attestation» hay un «test», y un secreto de verdad tiene todas las letras del
#: alfabeto. El borde es de letras y no `\b`, así `test123` y `ejemplo-1` —que sí son
#: marcadores— siguen entrando y «Attestation» no.
#:
#: El borde de la **derecha** sí admite las formas del propio marcador: sin ellas,
#: `TOKEN=testing123`, `tests`, `examples` y `fakes` eran hallazgos, que es marcar
#: exactamente lo que el repo escribe para no publicar un secreto. Las variantes van
#: declaradas una por una y no como un `[a-z]*` suelto, justamente para que «Attestation»
#: —`test` seguido de `ation`— siga sin eximir.
#:
#: Y el marcador tiene que **abrir el valor** (`^`, tras las comillas que lo envuelvan),
#: o abrir una de sus palabras si el valor entero está escrito a mano (ver
#: `_sabe_a_prueba`). Buscándolo en cualquier posición, un secreto de verdad que *termina*
#: en una de esas palabras —`SIIS_API_CLIENT_SECRET=k3yReal-testing`— se perdonaba solo,
#: que es el mismo agujero de «Attestation» por el otro lado.
SABE_A_PRUEBA = re.compile(
    r"""(?i)^["'`]*(?:tests?(?:ing)?|dummy|dummies|fakes?|ejemplos?|examples?|samples?"""
    r"|placeholders?|changeme|cambiame|no[-_]?real)(?![a-z])"
)
#: Un valor escrito a mano: palabras en minúscula unidas por guiones o puntos
#: (`ci-test-key-not-a-real-secret`, `mi_sample_valor`). Un secreto de verdad mezcla
#: mayúsculas y dígitos, así que `k3yReal-testing` no es esto.
PALABRAS_EN_MINUSCULA = re.compile(r"^[a-záéíóúüñ]+(?:[-_.][a-záéíóúüñ]+)*$")
SEPARADOR_DE_PALABRAS = re.compile(r"[-_.]")
#: Un valor que es un marcador de posición y no un secreto.
RELLENO = re.compile(r"^[<{$`*\[(\"']|^\.{3}|^…|^-+$|^_+$")
PALABRAS_DE_RELLENO = frozenset(
    {
        "none",
        "null",
        "n/a",
        "na",
        "placeholder",
        "ejemplo",
        "example",
        "valor",
        "value",
        "tu",
        "su",
        "xxx",
        "xxxx",
        "xxxxx",
        "cambiar",
        "change",
        "changeme",
        "opcional",
        "vacío",
        "vacio",
    }
)
#: Por debajo de esto no es un secreto, es prosa que quedó pegada al separador.
LARGO_MINIMO_DE_SECRETO = 6


def _cargar_mkdocs(ruta: Path = MKDOCS) -> dict:
    """`mkdocs.yml` trae `!!python/name:` (emoji, superfences): `safe_load` solo lo rechaza.

    PyYAML se importa acá y no arriba a propósito: `--todo-docs` no mira `mkdocs.yml`, así
    que el barrido amplio corre con el `python3` pelado del runner, sin instalar nada.
    """
    import yaml

    class Loader(yaml.SafeLoader):
        pass

    Loader.add_multi_constructor("tag:yaml.org,2002:python/name:", lambda *_: None)
    Loader.add_multi_constructor("!!python/name:", lambda *_: None)
    return yaml.load(ruta.read_text(encoding="utf-8"), Loader=Loader) or {}


def _paginas_del_nav(nav) -> set[str]:
    """Las rutas `.md` del `nav`, a cualquier profundidad."""
    encontradas: set[str] = set()
    if isinstance(nav, str):
        if nav.endswith(".md"):
            encontradas.add(nav.lstrip("/"))
    elif isinstance(nav, list):
        for entrada in nav:
            encontradas |= _paginas_del_nav(entrada)
    elif isinstance(nav, dict):
        for valor in nav.values():
            encontradas |= _paginas_del_nav(valor)
    return encontradas


def _patrones_fuera_del_nav(config: dict) -> list[str]:
    """`not_in_nav` es un bloque de patrones estilo `.gitignore`, uno por línea."""
    crudo = config.get("not_in_nav") or ""
    if isinstance(crudo, list):
        lineas = crudo
    else:
        lineas = str(crudo).splitlines()
    return [linea.strip().lstrip("/") for linea in lineas if linea.strip() and not linea.strip().startswith("#")]


def _declarado_fuera_del_nav(relativa: str, patrones: list[str]) -> bool:
    for patron in patrones:
        if patron.endswith("/"):
            if relativa.startswith(patron):
                return True
        elif relativa == patron or relativa.startswith(patron.rstrip("/") + "/"):
            return True
    return False


def _separar_camel(linea: str) -> str:
    """`numeroDocumento` → `numero Documento`, para que `\\b` vea la palabra de adentro."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-ZÁÉÍÓÚÑ])", " ", linea)


def _sabe_a_prueba(valor: str) -> bool:
    """Si el valor se nombra a sí mismo como descartable, en una de dos formas.

    Ninguna de las dos es «la palabra aparece en algún lado», que es lo que perdonaba a
    `k3yReal-testing`:

    1. El marcador **abre** el valor —`test-key`, `testing123`, `example-key`—, que es
       como se escribe un marcador de posición: anunciándose.
    2. El valor entero está **escrito a mano**: palabras en minúscula unidas por guiones,
       con una de ellas marcador (`ci-test-key-not-a-real-secret`, el `DJANGO_SECRET_KEY`
       del CI; `mi_sample_valor`). Un secreto de verdad mezcla mayúsculas y dígitos, así
       que `k3yReal-testing` no entra por acá: su primera palabra no es una palabra.
    """
    if SABE_A_PRUEBA.match(valor):
        return True
    if not PALABRAS_EN_MINUSCULA.match(valor):
        return False
    return any(SABE_A_PRUEBA.match(parte) for parte in SEPARADOR_DE_PALABRAS.split(valor))


def _es_relleno(valor: str) -> bool:
    if RELLENO.search(valor):
        return True
    limpio = valor.strip("`'\"*,.;:()[]{}<>")
    if len(limpio) < LARGO_MINIMO_DE_SECRETO:
        return True
    if REFERENCIA_DE_CODIGO.match(limpio) or _sabe_a_prueba(limpio):
        return True
    bajo = limpio.lower()
    return bajo in PALABRAS_DE_RELLENO or bajo.startswith("<") or bajo.endswith(">")


def _documentos(linea: str) -> list[str]:
    """Los documentos de la línea que no son un marcador ni un número con unidad."""
    encontrados = []
    for coincidencia in DOCUMENTO.finditer(linea):
        if UNIDAD.match(linea[coincidencia.end() :]):
            continue
        if not DOCUMENTO_DE_RELLENO.match(coincidencia.group().replace(".", "")):
            encontrados.append(coincidencia.group())
    return encontrados


def _cuiles(linea: str) -> list[str]:
    return [c.group() for c in CUIL.finditer(linea) if not CUIL_DE_RELLENO.match(re.sub(r"[-\s]", "", c.group()))]


def _fecha_normalizada(bruta: str) -> str:
    partes = re.split(r"[/-]", bruta)
    if len(partes[0]) == 4:
        anio, mes, dia = partes
    else:
        dia, mes, anio = partes
    return f"{anio}-{int(mes):02d}-{int(dia):02d}"


def _hay_identidad_cerca(lineas: list[str], indice: int, ventana: int, patron: re.Pattern) -> bool:
    desde = max(0, indice - ventana)
    hasta = min(len(lineas), indice + ventana + 1)
    return any(patron.search(_separar_camel(lineas[i])) for i in range(desde, hasta))


def _celdas(linea: str) -> list[str]:
    """Las celdas de una fila de tabla o de CSV, sin el adorno de markdown."""
    return [celda.strip().strip("`*\"'") for celda in SEPARADOR_DE_CELDAS.split(linea.strip().strip("|"))]


def _celdas_html(texto: str, patron: re.Pattern = CELDA_HTML) -> list[str]:
    """Las celdas `<th>`/`<td>` de `texto`, sin el adorno de adentro."""
    return [TAG_HTML.sub(" ", celda.group("texto")).strip() for celda in patron.finditer(texto)]


def _filas_de_celdas_html(texto: str) -> list[list[str]]:
    """Las celdas de cada `<tr>`, **por separado**.

    Un encabezado de padrón son las celdas de una misma fila. Leídas todas juntas, una
    tabla clave-valor —`<td>Documento rector</td>` en una fila y `<td>Nombre del
    programa</td>` en otra— calificaba como encabezado, y el primer número de siete
    dígitos que viniera abajo frenaba la publicación.

    El primer pedazo es la cola de la fila que empezó más arriba de la ventana: sigue
    siendo **una** fila, así que cuenta igual. Y si en la ventana no hay ningún `<tr>` no
    hay filas que separar: lo único que se sigue leyendo como encabezado es una corrida
    de `<th>` consecutivos, que es un encabezado escrito a mano.
    """
    partes = SEPARADOR_DE_FILA_HTML.split(texto)
    if len(partes) > 1:
        return [_celdas_html(parte) for parte in partes]
    return [_celdas_html(texto, CELDA_TH)]


def _celdas_nombran_un_padron(celdas: list[str]) -> bool:
    """Que **dos celdas distintas** nombren cosas distintas: una el documento y otra a
    la persona. Una sola («Documento») podría ser un título cualquiera; las dos juntas
    dicen de quién es cada columna, que es lo que le da sentido a los números de abajo.
    """
    celdas = [celda for celda in celdas if celda and len(celda) <= LARGO_MAXIMO_DE_ETIQUETA]
    if len(celdas) < 2:
        return False
    con_documento = {i for i, celda in enumerate(celdas) if NOMBRA_DOCUMENTO.search(_separar_camel(celda))}
    con_persona = {i for i, celda in enumerate(celdas) if NOMBRA_PERSONA.search(_separar_camel(celda))}
    return bool(con_documento) and bool(con_persona - con_documento)


def _parece_prosa_enumerativa(linea: str) -> bool:
    """Una oración que *enumera* columnas, no una fila que las tiene.

    Las dos marcas son de puntuación, y por eso son baratas y predecibles: una fila de
    CSV o de tabla **no termina en punto**, y no se anuncia con dos puntos antes de la
    primera celda. «Columnas: apellido, nombre, documento.» cumple las dos; `dni,apellido`
    ninguna. Mirar la forma de las celdas —cuántas palabras tenía cada una— era la
    heurística anterior, y perdía encabezados reales como
    `apellido y nombre del titular,documento,estado`.
    """
    limpia = linea.strip()
    if FIN_DE_ORACION.search(limpia):
        return True
    return ":" in SEPARADOR_AMBIGUO.split(limpia, maxsplit=1)[0]


def _parece_fila_de_tabla(linea: str) -> bool:
    """Si la línea está separada como una fila y no como una oración.

    Un `|` o un tab no tienen otro uso: alcanzan solos. La coma y el punto y coma también
    enumeran en prosa, así que ahí se pide que la línea no se delate como oración
    (`_parece_prosa_enumerativa`) y que sus celdas parezcan etiquetas: acotadas y **sin
    verbo**. No se cuentan palabras ni se piden tres columnas —`documento,apellido` es un
    padrón de dos columnas perfectamente publicable—.
    """
    if SEPARADOR_INEQUIVOCO.search(linea):
        return True
    if not SEPARADOR_AMBIGUO.search(linea) or _parece_prosa_enumerativa(linea):
        return False
    celdas = [celda for celda in _celdas(linea) if celda]
    if len(celdas) < MINIMO_DE_CELDAS_ENUMERADAS:
        return False
    return all(len(celda) <= LARGO_MAXIMO_DE_ETIQUETA and not VERBO_DE_PROSA.search(celda) for celda in celdas)


def _es_encabezado_de_padron(linea: str) -> bool:
    """Una fila de etiquetas que dice «lo que viene abajo son personas»."""
    return _parece_fila_de_tabla(linea) and _celdas_nombran_un_padron(_celdas(linea))


def _hay_encabezado_de_padron_arriba(lineas: list[str], indice: int) -> bool:
    """El encabezado va **antes** que sus filas: abajo no se mira.

    En HTML las celdas de un encabezado pueden venir repartidas en varias líneas (un
    `<th>` por línea), así que la ventana se mira entera —pero **fila por fila**, no toda
    junta: dos celdas de filas distintas no son un encabezado (`_filas_de_celdas_html`).
    """
    desde = max(0, indice - VENTANA_PADRON)
    if any(_es_encabezado_de_padron(lineas[i]) for i in range(desde, indice)):
        return True
    ventana = "\n".join(lineas[desde:indice])
    if not MARCA_DE_CELDA_HTML.search(ventana):
        return False
    return any(_celdas_nombran_un_padron(celdas) for celdas in _filas_de_celdas_html(ventana))


def _documento_pegado_a_un_nombre(linea: str) -> bool:
    nombrado = NOMBRE_PROPIO_CON_DOCUMENTO.search(linea)
    return bool(nombrado) and not DOCUMENTO_DE_RELLENO.match(nombrado.group("doc").replace(".", ""))


def _hay_altura_cerca(lineas: list[str], indice: int) -> bool:
    desde = max(0, indice - VENTANA_DOMICILIO)
    hasta = min(len(lineas), indice + VENTANA_DOMICILIO + 1)
    return any(VALOR_DE_ALTURA.search(lineas[i]) for i in range(desde, hasta))


def _revisar_contenido(relativa: str, texto: str) -> list[dict]:
    hallazgos = []
    lineas = texto.splitlines()
    # Las reglas miran **todas** las líneas, también las de adentro de un bloque de
    # código: el hallazgo real de esta ficha estaba justamente en un ```json.
    for indice, linea in enumerate(lineas):
        numero = indice + 1
        palabras = _separar_camel(linea)

        def anotar(regla: str, mensaje: str, _n: int = numero) -> None:
            hallazgos.append({"archivo": relativa, "linea": _n, "regla": regla, "mensaje": mensaje})

        if _documentos(linea):
            if NOMBRA_DOCUMENTO.search(palabras):
                anotar("persona", "un número de documento junto a la palabra que lo nombra")
            elif _hay_encabezado_de_padron_arriba(lineas, indice):
                anotar("persona", "un número de documento en una fila de padrón (la columna la nombra el encabezado)")
            elif _documento_pegado_a_un_nombre(linea):
                anotar("persona", "un número de documento pegado al nombre de una persona")
        if _cuiles(linea):
            anotar("persona", "algo con forma de CUIL/CUIT")

        nacimiento = NACIMIENTO_CON_FECHA.search(palabras)
        if (
            nacimiento
            and _fecha_normalizada(nacimiento.group("fecha")) not in FECHAS_DE_RELLENO
            and _hay_identidad_cerca(lineas, indice, VENTANA, CAMPO_DE_IDENTIDAD)
        ):
            anotar("persona", "una fecha de nacimiento rodeada de campos de identidad")

        calle = CALLE_CON_NUMERO.search(linea)
        if calle and not CALLE_DE_RELLENO.search(calle.group()):
            anotar("persona", "una calle con altura")
        else:
            clave = VALOR_DE_CALLE.search(linea)
            if clave and not CALLE_DE_RELLENO.search(clave.group("valor")) and _hay_altura_cerca(lineas, indice):
                anotar("persona", "un domicilio con calle y número")

        secreto = SECRETO.search(linea)
        if secreto and not CLAVE_ES_ARCHIVO.search(secreto.group("clave")) and not _es_relleno(secreto.group("valor")):
            anotar("secreto", "una clave de secreto con un valor que no es un marcador de posición")
    return hallazgos


def _archivos_de_texto(carpeta: Path):
    return sorted(ruta for ruta in carpeta.rglob("*") if ruta.is_file() and ruta.suffix.lower() in EXTENSIONES_DE_TEXTO)


def revisar(raiz: Path = RAIZ) -> list[dict]:
    """Los hallazgos de lo que MkDocs publica, ordenados por archivo y línea."""
    config = _cargar_mkdocs(raiz / "mkdocs.yml")
    carpeta = raiz / (config.get("docs_dir") or "docs/client")
    if not carpeta.is_dir():
        return [{"archivo": str(carpeta), "linea": 1, "regla": "nav", "mensaje": "docs_dir no existe"}]

    del_nav = _paginas_del_nav(config.get("nav"))
    fuera_del_nav = _patrones_fuera_del_nav(config)

    hallazgos: list[dict] = []
    for ruta in _archivos_de_texto(carpeta):
        relativa = ruta.relative_to(carpeta).as_posix()
        desde_la_raiz = ruta.relative_to(raiz).as_posix()
        # El nav solo lista `.md`: pedirle que declare un `.html` de assets no tiene dónde.
        if ruta.suffix.lower() == ".md" and relativa not in del_nav:
            if not _declarado_fuera_del_nav(relativa, fuera_del_nav):
                hallazgos.append(
                    {
                        "archivo": desde_la_raiz,
                        "linea": 1,
                        "regla": "nav",
                        "mensaje": "se publica pero no está en el nav de mkdocs.yml ni declarado en not_in_nav",
                    }
                )
        hallazgos += _revisar_contenido(desde_la_raiz, ruta.read_text(encoding="utf-8", errors="replace"))
    return sorted(hallazgos, key=lambda h: (h["archivo"], h["linea"], h["regla"]))


def revisar_todo(raiz: Path = RAIZ) -> list[dict]:
    """Las mismas reglas de contenido sobre `docs/` entero y los `.md` de la raíz.

    Sin la regla del nav, que solo tiene sentido sobre lo que construye MkDocs.
    """
    rutas = list(_archivos_de_texto(raiz / "docs")) + sorted(raiz.glob("*.md"))
    hallazgos: list[dict] = []
    for ruta in rutas:
        hallazgos += _revisar_contenido(
            ruta.relative_to(raiz).as_posix(), ruta.read_text(encoding="utf-8", errors="replace")
        )
    return sorted(hallazgos, key=lambda h: (h["archivo"], h["linea"], h["regla"]))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Gate de publicación de docs/client/ (RED-64).")
    parser.add_argument("--json", action="store_true", help="imprime los hallazgos como JSON")
    parser.add_argument(
        "--todo-docs",
        action="store_true",
        help="barre docs/ entero y los .md de la raíz, sin la regla del nav",
    )
    parser.add_argument("--raiz", default=str(RAIZ), help="raíz del repo (para los tests)")
    args = parser.parse_args(argv)

    raiz = Path(args.raiz)
    hallazgos = revisar_todo(raiz) if args.todo_docs else revisar(raiz)
    que = "docs/ + los .md de la raíz" if args.todo_docs else "docs/client/"
    if args.json:
        print(json.dumps(hallazgos, ensure_ascii=False, indent=2))
    else:
        for hallazgo in hallazgos:
            print(
                f"::error file={hallazgo['archivo']},line={hallazgo['linea']}::"
                f"[{hallazgo['regla']}] {hallazgo['mensaje']}"
            )
        total = len(hallazgos)
        print(f"{que}: {total} hallazgo(s)")
        if total:
            print(
                "Cómo se arregla: escribí el dato de la persona como marcador (documento "
                "12345678, CUIL 20-12345678-9, fecha 01/01/2000, «Calle Falsa 123»), el "
                "secreto como <valor>, o declará el archivo en el nav o en not_in_nav."
            )
    return 1 if hallazgos else 0


if __name__ == "__main__":
    sys.exit(main())
