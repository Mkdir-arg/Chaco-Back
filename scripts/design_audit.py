#!/usr/bin/env python3
"""Auditoría mecánica del sistema de diseño Chaco/NODO.

Solo stdlib: el hook de Claude Code y el CI lo corren sin venv.

Chequeos mecánicos compartidos para cambios de UI. El inventario y las decisiones
operativas viven en `.claude/agents/chaco-design-system.md`, que se contrasta con
el frontend productivo antes de usar este script.

Uso:
    python scripts/design_audit.py [paths...]      # audita archivos o carpetas
    python scripts/design_audit.py --changed       # audita solo archivos modificados (git)
    python scripts/design_audit.py --ratchet [--base REF]   # 0 hallazgos NUEVOS respecto de REF
    python scripts/design_audit.py --arquetipo listado ARCHIVO   # marcadores de un arquetipo
    python scripts/design_audit.py --goldens       # las goldens del agente, en 0
    python scripts/design_audit.py --hook          # modo hook de Claude Code (JSON por stdin)

Sin argumentos audita las superficies de UI del repo (templates/ + static/custom/css
+ templates de apps). Exit code 1 si hay violaciones ERROR; las WARN no cortan.

## Las tres severidades

  ERROR  Reglas duras de token/lint (hex, fuentes, confirm(), gradientes legacy...).
         Cortan en cualquier modo. Son pocas y el repo está en 0 desde hace tiempo.
  P1     Las 8 reglas estructurales de la Ola 6. El repo arrastra miles de hallazgos
         preexistentes, así que **no cortan en una corrida plana**: se informan como
         deuda. Cortan en `--ratchet` (y por lo tanto en el hook y en el CI) cuando
         el conteo de una regla **sube** en un archivo respecto de la base. La deuda
         de hoy queda congelada y solo puede bajar.
  WARN   Señales para evaluar con criterio. Nunca cortan.

Reglas ERROR (token/lint):
  HEX        Cero hex hardcodeado (salvo #fff/#ffffff). Excluye chaco-tokens.css,
             los templates de correo (**/email/) y líneas con template tags
             dinámicos ({{ ... }}).
  FONT       Manrope única: Fredoka/Gellat/Geliat/Satoshi/Inter/Roboto/Montserrat.
  CONFIRM    window.confirm()/alert()/prompt() nativos prohibidos (SweetAlert2/DS Modal).
  SWALHEX    confirmButtonColor/cancelButtonColor prohibidos (usar buttonsStyling:false
             + customClass btn-nodo).
  GRADLEG    Gradientes legacy: FF0080/7928CA (NODO magenta) y 3B82F6/8B5CF6
             (azul→púrpura NODO) en templates/CSS.
  ICONHEX    fill=/stroke= con hex en SVG (color por token/currentColor).
  ZINDEX     z-index 9999 (escala del kit: topbar 20 · modal 50 · toast 80).
  DJCOMMENT  {# ... #} multilínea (se renderiza como texto; usar {% comment %}).
  TWBUILD    Utilidad de Tailwind con variante (sm:/xl:/hover:...) o valor
             arbitrario ([82vh], [15px]) usada en un template pero ausente de
             static/custom/css/tailwind.css. El build está committeado: si se
             agrega una clase nueva hay que correr `npm run build:tailwind` y
             commitear el CSS, o la pantalla se ve mal sin ningún error.

Reglas P1 (estructura; ratchet):
  RAWPALETTE   Paleta cruda de Tailwind (bg-gray-200, text-red-500...) dentro de class="".
  INLINESTYLE  style="" con declaraciones (se permiten custom properties, valores
               dinámicos {{ }} y display:none).
  STYLEBLOCK   <style> fuera de los cuatro shells (incluye el [x-cloak] local).
  SHELLLEGACY  {% extends "includes/main.html" %} — shell legacy, no se extiende.
  PAGEHEADER   <h1> a mano en el backoffice en vez de {% page_header %}.
  TABLECANON   <th> sin nodo-th, o <thead style=...>.
  ICONARIA     Ícono Font Awesome <i class="fas ..."> sin aria-hidden="true".
  CLASSDEF     Clase usada que no existe en ningún CSS cargable. P1 si tiene forma
               de utilidad Tailwind (build viejo o utilidad inválida); WARN si no
               (Bootstrap/AdminLTE heredado, o hook sin prefijo js-).

Reglas WARN:
  OUTLINE    outline:none / outline-none (nunca sin reemplazo de ring).
  OPACITY    opacity como estado disabled (usar --bg-disabled/--text-disabled).
"""

from __future__ import annotations

import ast
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Superficies de UI auditadas por defecto
DEFAULT_TARGETS = [
    "templates",
    "static/custom/css",
    "static/custom/js",
    "core/templates",
    "dashboard/templates",
    "legajos/templates",
    "programas/templates",
    "portal/templates",
    "users/templates",
    "configuracion/templates",
    "conversaciones/templates",
]

# "email": los templates de correo (`**/templates/**/email/`) necesitan estilos
# inline y hex literal — ningún cliente de correo soporta CSS variables, y Outlook
# ni siquiera <style> confiable. Los colores igual salen del kit (--gradient-brand
# = #5059bc → #f98dff), pero escritos a mano: no hay forma de tokenizarlos.
# "vendor": librerías de terceros autoalojadas (Alpine, Font Awesome, vis-network,
# la tipografía). No son superficie de diseño propia y traen sus propios colores;
# se sirven desde el dominio para no depender de un CDN, no para editarlas.
# "docs": documentación, no producto. Ahí viven los anexos de la auditoría y la
# línea base del agente de diseño, que guarda templates generados a propósito
# fuera de canon: contarlos como deuda del repo sería medir el papel, no la app.
EXCLUDE_PARTS = {".venv", "node_modules", ".git", "design-kb", "docs", "email", "vendor"}
# `tailwind.css` se genera desde templates/JS con `npm run build:tailwind`; sus
# valores internos pertenecen al framework y se revisan mediante el build, no
# mediante reglas pensadas para CSS escrito a mano.
EXCLUDE_FILES = {"chaco-tokens.css", "tailwind.css"}
UI_SUFFIXES = {".html", ".css", ".js"}
COMMENT_PREFIXES = ("//", "/*", "*", "<!--", "{#")

HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
ALLOWED_HEX = {"#fff", "#ffffff"}
DYNAMIC_RE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}")  # spans de template tags → dato del backend, se recortan del escaneo
DYNAMIC_MULTI_RE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.S)
# var(--token, <fallback>) con un nivel de paréntesis anidado (ej. gradiente de fallback)
VAR_FALLBACK_RE = re.compile(r"var\((?:[^()]|\([^()]*\))*\)")

RULES: list[tuple[str, str, re.Pattern[str], str]] = [
    # (regla, severidad, patrón, mensaje)
    (
        "FONT",
        "ERROR",
        re.compile(
            r"fredoka|gellat|geliat|satoshi|font-family[^;]{0,60}\b(Inter|Roboto|Montserrat)\b|['\"]Montserrat['\"]",
            re.I,
        ),
        "Tipografía legacy — Manrope es la única (via --font-sans/--font-display)",
    ),
    (
        "CONFIRM",
        "ERROR",
        re.compile(r"window\.(confirm|alert|prompt)\s*\(|(?<![\w.$])(?<!function )(confirm|alert|prompt)\s*\("),
        "confirm()/alert()/prompt() nativo prohibido — SweetAlert2 (backoffice) / DS Modal",
    ),
    (
        "SWALHEX",
        "ERROR",
        re.compile(r"confirmButtonColor|cancelButtonColor"),
        "Color hex en SweetAlert — usar buttonsStyling:false + customClass btn-nodo",
    ),
    (
        "GRADLEG",
        "ERROR",
        re.compile(r"FF0080|7928CA|3B82F6|8B5CF6", re.I),
        "Gradiente/color legacy NODO — usar --gradient-brand / tokens",
    ),
    (
        "ICONHEX",
        "ERROR",
        re.compile(r"(fill|stroke)=[\"']#[0-9a-fA-F]{3,8}[\"']"),
        "Color hardcodeado en SVG — usar currentColor + token en el contenedor",
    ),
    (
        "ZINDEX",
        "ERROR",
        re.compile(r"z-index:\s*9999|z-\[9999\]"),
        "z-index 9999 — escala del kit: topbar 20 · modal 50 · toast 80",
    ),
    (
        "OUTLINE",
        "WARN",
        re.compile(r"outline:\s*none|outline-none"),
        "outline:none — verificar que haya ring de focus de reemplazo (--ring-brand)",
    ),
    (
        "OPACITY",
        "WARN",
        re.compile(r"disabled[^\n]{0,40}opacity|opacity[^\n]{0,40}disabled", re.I),
        "opacity como disabled — usar --bg-disabled + --text-disabled",
    ),
]

DJCOMMENT_RE = re.compile(r"\{#[^#]*?\n")  # apertura {# sin cierre en la misma línea

# Severidades que cortan en el ratchet (el resto es informativo).
SEVERIDADES_BLOQUEANTES = {"ERROR", "P1"}


def iter_files(paths: list[Path]):
    for p in paths:
        if p.is_file():
            # Mismo filtro que la rama de directorios y que el modo --hook: una
            # ruta explícita (--changed) no puede saltearse las exclusiones.
            if p.suffix in UI_SUFFIXES and p.name not in EXCLUDE_FILES and not (EXCLUDE_PARTS & set(p.parts)):
                yield p
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if (
                    f.is_file()
                    and f.suffix in UI_SUFFIXES
                    and f.name not in EXCLUDE_FILES
                    and not (EXCLUDE_PARTS & set(f.parts))
                ):
                    yield f


def rel_posix(path: Path) -> str:
    """Ruta del archivo relativa al repo, en formato posix (la que usa git)."""
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except (OSError, ValueError):
        return path.as_posix()


def changed_files() -> list[Path]:
    # Mismo motivo que en `_git`: sin `encoding` explícito, un nombre de archivo con
    # tilde rompe la lectura de `stdout` en Windows.
    comunes = {"cwd": REPO, "capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace"}
    out = subprocess.run(["git", "diff", "--name-only", "HEAD"], **comunes).stdout
    out += subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], **comunes).stdout
    return [REPO / line for line in out.splitlines() if line.strip()]


# --- Decodificador de clases declaradas en un CSS (FE-13) --------------------
# Un identificador CSS escapa todo lo que no sea alfanumérico: `.xl\:top-6` es la
# clase `xl:top-6` y `.w-1\/2` es `w-1/2`. Hay dos formas de escape y la
# diferencia importa:
#   * `\` + 1 a 6 dígitos hex = ese code point, y **consume un espacio opcional**
#     que sirve de terminador. Tailwind emite así la coma de un valor arbitrario:
#     `.h-\[clamp\(1rem\2c 2rem\)\]` es `h-[clamp(1rem,2rem)]`.
#   * `\` + cualquier otro carácter = ese carácter, literal.
# Con una expresión regular estas dos reglas se pisan (el espacio terminador se
# lee como parte del nombre o como su final) y la clase se trunca: así se
# inventaron los dos TWBUILD falsos que el hook reportaba como bloqueantes.
# Se recorre el prelude de cada regla (lo que está antes de `{`) para no leer
# puntos que viven dentro de declaraciones, strings o url().

_CSS_COMENTARIO_RE = re.compile(r"/\*.*?\*/", re.S)
_CSS_PRELUDE_RE = re.compile(r"([^{}]*)\{")
_HEX_RE = re.compile(r"[0-9a-fA-F]{1,6}")


def _ident_desde(sel: str, i: int) -> tuple[str, int]:
    """Lee un identificador CSS desde ``sel[i]``; devuelve (nombre, índice siguiente)."""
    nombre: list[str] = []
    n = len(sel)
    while i < n:
        c = sel[i]
        if c == "\\":
            m = _HEX_RE.match(sel, i + 1)
            if m:
                nombre.append(chr(int(m.group(0), 16)))
                i = m.end()
                # Un único espacio en blanco después del hex es el terminador del
                # escape, no parte del nombre.
                if i < n and sel[i] in " \t\n\r\f":
                    i += 1
            else:
                if i + 1 < n:
                    nombre.append(sel[i + 1])
                i += 2
        elif c.isalnum() or c in "-_" or ord(c) > 127:
            nombre.append(c)
            i += 1
        else:
            break
    return "".join(nombre), i


def clases_css(css: str) -> set[str]:
    """Las clases que declara un CSS, con los escapes ya resueltos."""
    css = _CSS_COMENTARIO_RE.sub("", css)
    encontradas: set[str] = set()
    for m in _CSS_PRELUDE_RE.finditer(css):
        sel = m.group(1)
        if sel.lstrip().startswith("@"):
            continue  # prelude de at-rule (@media, @supports): no declara clases
        i, n = 0, len(sel)
        while i < n:
            c = sel[i]
            if c == "." and i + 1 < n and (sel[i + 1].isalpha() or sel[i + 1] in "-_\\"):
                nombre, i = _ident_desde(sel, i + 1)
                if nombre:
                    encontradas.add(nombre)
            elif c == "[":
                # Selector de atributo: puede traer un punto adentro de la comilla.
                cierre = sel.find("]", i)
                i = cierre + 1 if cierre != -1 else n
            else:
                i += 1
    return encontradas


# --- TWBUILD: utilidades de Tailwind que el build no tiene -------------------
# El build está committeado, así que una clase nueva no existe hasta que alguien
# corre `npm run build:tailwind`. El template compila, la auditoría pasa y la
# pantalla se ve mal en silencio (pasó con `xl:grid-cols-2` en el Cambio 58).
#
# Se verifican solo las que fallan así: las que llevan variante (`xl:`, `hover:`)
# o valor arbitrario (`max-h-[82vh]`). El resto lo cubre CLASSDEF.

TAILWIND_CSS = REPO / "static" / "custom" / "css" / "tailwind.css"
# `class="..."` literal: `:class="..."` de Alpine lleva una expresión JS.
CLASS_ATTR_RE = re.compile(r'(?<![-:\w])class="([^"]*)"')
VARIANTES = (
    "sm:",
    "md:",
    "lg:",
    "xl:",
    "2xl:",
    "hover:",
    "focus:",
    "focus-visible:",
    "active:",
    "disabled:",
    "group-hover:",
    "peer-",
    "dark:",
    "print:",
)
# Solo utilidades: descarta lo que trae sintaxis de plantilla o comillas.
UTILIDAD_RE = re.compile(r"^-?[a-z0-9]+[-a-zA-Z0-9_:/\[\]().,%!.-]*$")
_CLASES_TW: set[str] | None = None
_CLASES_TW_LEIDO = False


def _clases_del_build() -> set[str] | None:
    """Las clases que declara `tailwind.css`, des-escapadas. ``None`` si falta."""
    global _CLASES_TW, _CLASES_TW_LEIDO
    if _CLASES_TW_LEIDO:
        return _CLASES_TW
    _CLASES_TW_LEIDO = True
    try:
        css = TAILWIND_CSS.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    _CLASES_TW = clases_css(css)
    return _CLASES_TW


def tokens_de_clase(text: str) -> list[tuple[int, str]]:
    """``(línea, token)`` de cada clase escrita a mano en un ``class="…"``.

    Los `{% %}` se recortan dejando sus ramas (un `{% if %}` entre clases no es
    una clase); el token que contenga un `{{ }}` se descarta entero, porque el
    nombre lo arma el backend y acá no se puede verificar.
    """
    out: list[tuple[int, str]] = []
    for m in CLASS_ATTR_RE.finditer(text):
        bloque = re.sub(r"\{\{.*?\}\}", "\x00", m.group(1), flags=re.S)
        bloque = re.sub(r"\{%.*?%\}", " ", bloque, flags=re.S)
        linea = text[: m.start()].count("\n") + 1
        for token in bloque.split():
            if "\x00" not in token:
                out.append((linea, token))
    return out


def clases_sin_build(text: str) -> list[tuple[int, str]]:
    """``(línea, clase)`` de cada utilidad verificable que el build no declara."""
    compiladas = _clases_del_build()
    if not compiladas:
        return []
    faltantes, vistas = [], set()
    for linea, clase in tokens_de_clase(text):
        verificable = clase.startswith(VARIANTES) or ("[" in clase and clase.endswith("]"))
        if not verificable or clase in vistas or not UTILIDAD_RE.match(clase):
            continue
        vistas.add(clase)
        if clase not in compiladas:
            faltantes.append((linea, clase))
    return faltantes


# --- CLASSDEF: clases que no existen en ningún CSS cargable (FE-13) ----------
# Universo declarado: el build de Tailwind, todos los CSS propios, los CSS de
# Font Awesome y SweetAlert2 (los únicos de `vendor` que aportan clases al
# markup propio), el `<style>` del propio template y los CSS que el template
# enlaza con `{% static '….css' %}` (ej. performance_dashboard.html, que carga
# bootstrap y adminlte por su cuenta).

CSS_BASE_GLOBS = (
    "static/custom/css/*.css",
    "static/vendor/fontawesome/**/*.css",
    "static/vendor/sweetalert2/**/*.css",
)
HOOKS_FILE = REPO / "scripts" / "design_audit_hooks.txt"
STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>(.*?)</style>", re.S | re.I)
STATIC_CSS_RE = re.compile(r"\{%\s*static\s+['\"]([^'\"]+\.css)['\"]\s*%\}")
EXTENDS_RE = re.compile(r"\{%\s*extends\s+['\"]([^'\"]+)['\"]\s*%\}")
# Vocabulario heredado de Bootstrap/AdminLTE y marcadores de JS muerto: la forma
# coincide con una raíz de Tailwind (`col-`, `w-`, `justify-`...) pero no son
# utilidades, son markup viejo que se va con FE-14, FE-20 y SEC-19. Van a WARN
# para que el ERROR de CLASSDEF signifique siempre lo mismo: bug visual del build.
LEGACY_NO_TAILWIND_RE = re.compile(
    r"^(?:col-(?:xs|sm|md|lg|xl)?-?\d+|row|container(?:-fluid)?|[wh]-(?:25|50|75|100)"
    r"|align-(?:items|self|content)-[a-z]+|justify-content-[a-z]+|float-[a-z]+(?:-[a-z]+)?"
    r"|list-(?:group|unstyled|inline)(?:-[a-z]+)*|text-(?:muted|dark|white-50)"
    r"|touch-friendly|scroll-indicator|animate-slide-in)$"
)
ALPINE_CLASS_ATTR_RE = re.compile(r'(?::class|x-bind:class)="([^"]*)"')
OBJETO_CLAVE_RE = re.compile(r"['\"]([^'\"]+)['\"]\s*:")
TERNARIO_RE = re.compile(r"\?\s*['\"]([^'\"]*)['\"]\s*:\s*['\"]([^'\"]*)['\"]")
CLASSLIST_RE = re.compile(r"classList\.(?:add|remove|toggle|replace)\(([^)]*)\)")
CLASSNAME_RE = re.compile(r"""className\s*=\s*['"]([^'"]*)['"]""")
STRING_RE = re.compile(r"""['"]([^'"]*)['"]""")

# Raíces de utilidad de Tailwind: un token con esta raíz y sin CSS es un bug
# visual (build viejo o utilidad inválida con esta config), no markup heredado.
RAICES_TAILWIND = {
    "bg",
    "text",
    "border",
    "divide",
    "ring",
    "placeholder",
    "outline",
    "m",
    "mt",
    "mr",
    "mb",
    "ml",
    "mx",
    "my",
    "p",
    "pt",
    "pr",
    "pb",
    "pl",
    "px",
    "py",
    "w",
    "h",
    "min",
    "max",
    "gap",
    "space",
    "inset",
    "top",
    "right",
    "bottom",
    "left",
    "z",
    "grid",
    "col",
    "row",
    "flex",
    "items",
    "justify",
    "self",
    "place",
    "order",
    "basis",
    "grow",
    "shrink",
    "rounded",
    "shadow",
    "opacity",
    "font",
    "leading",
    "tracking",
    "indent",
    "decoration",
    "underline",
    "align",
    "whitespace",
    "break",
    "overflow",
    "translate",
    "scale",
    "rotate",
    "skew",
    "origin",
    "transition",
    "duration",
    "ease",
    "delay",
    "animate",
    "from",
    "via",
    "to",
    "backdrop",
    "blur",
    "object",
    "aspect",
    "columns",
    "cursor",
    "select",
    "pointer",
    "list",
    "float",
    "clear",
    "fill",
    "stroke",
    "box",
    "caret",
    "accent",
    "scroll",
    "snap",
    "touch",
    "content",
}
_VARIANTE_RE = re.compile(r"^(?:[a-z0-9][a-z0-9-]*:)+")
_TOKEN_VALIDO_RE = re.compile(r"^[a-zA-Z0-9][-a-zA-Z0-9_:/\[\]().,%!]*$")

_UNIVERSO_BASE: set[str] | None = None
_HOOKS: tuple[str, ...] | None = None


def _hooks_permitidos() -> tuple[str, ...]:
    global _HOOKS
    if _HOOKS is None:
        patrones: list[str] = []
        try:
            for linea in HOOKS_FILE.read_text(encoding="utf-8").splitlines():
                linea = linea.strip()
                if linea and not linea.startswith("#"):
                    patrones.append(linea)
        except OSError:
            pass
        _HOOKS = tuple(patrones)
    return _HOOKS


def _universo_base() -> set[str]:
    """Clases declaradas por el CSS que carga todo el backoffice."""
    global _UNIVERSO_BASE
    if _UNIVERSO_BASE is None:
        universo: set[str] = set(_clases_del_build() or set())
        for patron in CSS_BASE_GLOBS:
            for css in sorted(REPO.glob(patron)):
                try:
                    universo |= clases_css(css.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    continue
        _UNIVERSO_BASE = universo
    return _UNIVERSO_BASE


_MAPA_TEMPLATES: dict[str, Path] | None = None
_CSS_HEREDADO: dict[str, set[str]] = {}


def _mapa_templates() -> dict[str, Path]:
    """Nombre de template (`includes/base.html`) → archivo, como lo resuelve el loader."""
    global _MAPA_TEMPLATES
    if _MAPA_TEMPLATES is None:
        mapa: dict[str, Path] = {}
        raices = [REPO / "templates"] + sorted(REPO.glob("*/templates"))
        for raiz in raices:
            if not raiz.is_dir():
                continue
            for f in raiz.rglob("*.html"):
                mapa.setdefault(f.relative_to(raiz).as_posix(), f)
        _MAPA_TEMPLATES = mapa
    return _MAPA_TEMPLATES


def _css_propio(text: str) -> set[str]:
    """Clases del `<style>` del template y de los CSS que enlaza con {% static %}."""
    extra: set[str] = set()
    for bloque in STYLE_BLOCK_RE.findall(text):
        extra |= clases_css(bloque)
    for ruta in STATIC_CSS_RE.findall(text):
        css = REPO / "static" / ruta.lstrip("/")
        try:
            extra |= clases_css(css.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return extra


def _universo_del_archivo(text: str) -> set[str]:
    """Universo base + el CSS propio + el de los shells que el template extiende.

    Lo heredado cuenta: `portal/base.html` define `.animate-fadeInUp` en su
    `<style>` y sus 17 hijos la usan sin declararla ellos.
    """
    extra = _css_propio(text)
    visitados: set[str] = set()
    actual = text
    for _ in range(5):  # cadena de herencia acotada: shells de 2 o 3 niveles
        m = EXTENDS_RE.search(actual)
        if not m or m.group(1) in visitados:
            break
        visitados.add(m.group(1))
        padre = _mapa_templates().get(m.group(1))
        if padre is None:
            break
        try:
            actual = padre.read_text(encoding="utf-8", errors="replace")
        except OSError:
            break
        # Los shells se repiten en cientos de hijos y enlazan todo el CSS propio:
        # sin cachear, cada template reparsea `static/custom/css/*.css` entero.
        if m.group(1) not in _CSS_HEREDADO:
            _CSS_HEREDADO[m.group(1)] = _css_propio(actual)
        extra |= _CSS_HEREDADO[m.group(1)]
    return _universo_base() | extra


def _es_utilidad_tailwind(token: str) -> bool:
    base = _VARIANTE_RE.sub("", token).lstrip("-").split("/")[0]
    if LEGACY_NO_TAILWIND_RE.match(base):
        return False
    raiz = base.split("-", 1)[0]
    return raiz in RAICES_TAILWIND and ("-" in base or "[" in base)


def tokens_de_clase_dinamicos(text: str) -> list[tuple[int, str]]:
    """Clases que aparecen en `:class` de Alpine y en manipulación de clases por JS."""
    out: list[tuple[int, str]] = []

    def linea_de(pos: int) -> int:
        return text[:pos].count("\n") + 1

    for m in ALPINE_CLASS_ATTR_RE.finditer(text):
        expr, linea = m.group(1), linea_de(m.start())
        for a, b in TERNARIO_RE.findall(expr):
            out += [(linea, t) for t in (a + " " + b).split()]
        for clave in OBJETO_CLAVE_RE.findall(expr):
            out += [(linea, t) for t in clave.split()]
    for m in CLASSLIST_RE.finditer(text):
        linea = linea_de(m.start())
        for arg in STRING_RE.findall(m.group(1)):
            out += [(linea, t) for t in arg.split()]
    for m in CLASSNAME_RE.finditer(text):
        out += [(linea_de(m.start()), t) for t in m.group(1).split()]
    return out


def clases_en_python(text: str) -> list[tuple[int, str]]:
    """``(línea, token)`` de cada cadena de un `.py` que puede ser una clase CSS.

    Buena parte de los campos del backoffice traen sus clases desde el widget del
    form, no desde el template: `programas/forms.py` (`INPUT_CLASS`), los widgets
    del wizard de programas, el input de archivo del legajo. Para el navegador es
    markup; para cualquier herramienta que solo mire `.html`, no existe.

    Se leen **todas** las cadenas literales con `ast`, no solo las que están bajo
    una clave ``"class"``: el patrón más común del repo es una constante de módulo
    (``_DISABLED = "text-sm … cursor-not-allowed"``) que después se referencia. Un
    nombre que no tenga forma de utilidad lo descarta quien llama.

    Con `ast` y no con una regex a propósito: el extractor de Tailwind sí es una
    regex sobre el texto crudo, y por eso un slice (`xs[desde:hasta]`) le parece
    una utilidad de valor arbitrario. Acá se ven cadenas literales y nada más.
    """
    try:
        arbol = ast.parse(text)
    except SyntaxError:
        return []
    out: list[tuple[int, str]] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            out += [(getattr(nodo, "lineno", 0), token) for token in nodo.value.split()]
    return out


def clases_sin_definicion(text: str, *, es_template: bool) -> list[tuple[int, str, bool]]:
    """``(línea, token, es_utilidad)`` de cada clase usada sin CSS que la declare."""
    universo = _universo_del_archivo(text) if es_template else _universo_base()
    hooks = _hooks_permitidos()
    crudos = (tokens_de_clase(text) if es_template else []) + tokens_de_clase_dinamicos(text)
    faltantes: list[tuple[int, str, bool]] = []
    vistos: set[str] = set()
    for linea, token in crudos:
        if token in vistos or token in universo or not _TOKEN_VALIDO_RE.match(token):
            continue
        vistos.add(token)
        if any(fnmatch.fnmatchcase(token, patron) for patron in hooks):
            continue
        faltantes.append((linea, token, _es_utilidad_tailwind(token)))
    return faltantes


# --- Reglas P1 (estructura; ratchet) ----------------------------------------

SHELLS = {
    "templates/includes/base.html",
    "templates/includes/main.html",
    "portal/templates/portal/base.html",
    "portal/templates/portal/inscripcion/base_inscripcion.html",
    "users/templates/user/base_public_auth.html",
}
RAWPALETTE_RE = re.compile(
    r"(?<![\w-])(?:[a-z0-9-]+:)*(?:bg|text|border|ring|divide|from|via|to|placeholder)"
    r"-(?:gray|slate|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky"
    r"|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}(?:/\d+)?\b"
)
INLINESTYLE_RE = re.compile(r'\sstyle="([^"]*)"')
CUSTOM_PROP_RE = re.compile(r"--[\w-]+\s*:[^;]*;?")
DISPLAY_NONE_RE = re.compile(r"display\s*:\s*none\s*;?", re.I)
STYLE_TAG_RE = re.compile(r"<style\b")
SHELLLEGACY_RE = re.compile(r"\{%\s*extends\s+[\"']includes/main\.html[\"']")
EXTIENDE_BASE_RE = re.compile(r"\{%\s*extends\s+[\"']includes/base\.html[\"']")
TH_SIN_CANON_RE = re.compile(r"<th\b(?![^>]*\bnodo-th\b)")
THEAD_STYLE_RE = re.compile(r"<thead[^>]*style=")
ICONARIA_RE = re.compile(r'<i\s+class="(?:fa[srb]?|fa-(?:solid|regular|brands))\s[^"]*"(?![^>]*aria-hidden)')


def _lineas_de(text: str, patron: re.Pattern[str]) -> list[int]:
    return [text[: m.start()].count("\n") + 1 for m in patron.finditer(text)]


def _p1_rawpalette(rel: str, text: str) -> list[tuple[int, str]]:
    out = []
    for m in CLASS_ATTR_RE.finditer(text):
        linea = text[: m.start()].count("\n") + 1
        for hallado in RAWPALETTE_RE.finditer(m.group(1)):
            out.append((linea, hallado.group(0)))
    return out


def _p1_inlinestyle(rel: str, text: str) -> list[tuple[int, str]]:
    out = []
    for m in INLINESTYLE_RE.finditer(text):
        valor = DYNAMIC_MULTI_RE.sub("", m.group(1))
        valor = CUSTOM_PROP_RE.sub("", valor)
        valor = DISPLAY_NONE_RE.sub("", valor)
        if valor.strip(" ;"):
            out.append((text[: m.start()].count("\n") + 1, m.group(0).strip()[:80]))
    return out


def _p1_styleblock(rel: str, text: str) -> list[tuple[int, str]]:
    if rel in SHELLS:
        return []
    return [(ln, "<style>") for ln in _lineas_de(text, STYLE_TAG_RE)]


def _p1_shelllegacy(rel: str, text: str) -> list[tuple[int, str]]:
    return [(ln, 'extends "includes/main.html"') for ln in _lineas_de(text, SHELLLEGACY_RE)]


def _p1_pageheader(rel: str, text: str) -> list[tuple[int, str]]:
    if rel.startswith("portal/"):
        return []
    if EXTIENDE_BASE_RE.search(text) and "<h1" in text and "{% page_header" not in text:
        linea = text[: text.index("<h1")].count("\n") + 1
        return [(linea, "<h1 a mano")]
    return []


def _p1_tablecanon(rel: str, text: str) -> list[tuple[int, str]]:
    if rel.startswith("portal/"):
        return []
    out = [(ln, "<th sin nodo-th") for ln in _lineas_de(text, TH_SIN_CANON_RE)]
    out += [(ln, "<thead style=") for ln in _lineas_de(text, THEAD_STYLE_RE)]
    return out


def _p1_iconaria(rel: str, text: str) -> list[tuple[int, str]]:
    return [(ln, "ícono sin aria-hidden") for ln in _lineas_de(text, ICONARIA_RE)]


# (regla, función, mensaje). El orden es el de la tabla del anexo §7.
P1_RULES: list[tuple[str, object, str]] = [
    ("RAWPALETTE", _p1_rawpalette, "Paleta cruda de Tailwind — usar el color semántico (bg-secondary, text-body…)"),
    ("INLINESTYLE", _p1_inlinestyle, "style= con declaraciones — usar utilidades o una custom property"),
    (
        "STYLEBLOCK",
        _p1_styleblock,
        "<style> en una pantalla — el CSS vive en static/custom/css y [x-cloak] ya es global",
    ),
    ("SHELLLEGACY", _p1_shelllegacy, "shell legacy includes/main.html — extender includes/base.html"),
    ("PAGEHEADER", _p1_pageheader, "<h1> a mano — el encabezado es {% page_header %}"),
    ("TABLECANON", _p1_tablecanon, "tabla fuera del canon — nodo-thead-row / nodo-th / nodo-td"),
    ("ICONARIA", _p1_iconaria, 'ícono Font Awesome sin aria-hidden="true"'),
]


def audit_file(path: Path) -> list[tuple[str, int, str, str, str]]:
    """Devuelve (severidad, línea, regla, mensaje, extracto)."""
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings

    lines = text.splitlines()
    is_template = path.suffix == ".html"
    rel = rel_posix(path)
    # Pragma de excepción documentada: la línea se salta entera.
    # Uso: para valores canónicos sin token (ej. mapa badge-brand del kit).
    exentas = {i for i, line in enumerate(lines, 1) if "design-audit: allow" in line}

    for i, line in enumerate(lines, 1):
        if i in exentas:
            continue
        # HEX crudo (regla especial: permite #fff, valores dinámicos del backend
        # ({{ ... }}/{% ... %} se recortan, no se salta la línea entera) y fallbacks
        # dentro de var(--token, #hex) — patrón token-first legítimo)
        scan = DYNAMIC_RE.sub("", line)
        scan = VAR_FALLBACK_RE.sub("var()", scan)
        for m in HEX_RE.finditer(scan):
            if m.group(0).lower() not in ALLOWED_HEX:
                findings.append(
                    ("ERROR", i, "HEX", "Hex hardcodeado — usar token semántico var(--...)", line.strip()[:100])
                )
                break  # un reporte por línea alcanza
        es_comentario = line.lstrip().startswith(COMMENT_PREFIXES)
        for rule, sev, pat, msg in RULES:
            if rule == "CONFIRM" and es_comentario:
                continue  # el comentario que menciona alert() no es una llamada
            if pat.search(line):
                findings.append((sev, i, rule, msg, line.strip()[:100]))

    # {# ... #} multilínea (solo templates)
    if is_template:
        for m in DJCOMMENT_RE.finditer(text):
            ln = text[: m.start()].count("\n") + 1
            if ln not in exentas:
                findings.append(
                    ("ERROR", ln, "DJCOMMENT", "{# #} multilínea se renderiza como texto — usar {% comment %}", "")
                )

        for ln, clase in clases_sin_build(text):
            if ln not in exentas:
                findings.append(
                    (
                        "ERROR",
                        ln,
                        "TWBUILD",
                        f"«{clase}» no está en el CSS compilado — correr `npm run build:tailwind` y commitear",
                        "",
                    )
                )

        for rule, fn, msg in P1_RULES:
            for ln, extracto in fn(rel, text):
                if ln not in exentas:
                    findings.append(("P1", ln, rule, msg, extracto))

    if is_template or rel.startswith("static/custom/js/"):
        for ln, token, es_utilidad in clases_sin_definicion(text, es_template=is_template):
            if ln in exentas:
                continue
            if es_utilidad:
                findings.append(
                    (
                        "P1",
                        ln,
                        "CLASSDEF",
                        f"«{token}» no existe en el build: utilidad inválida o CSS sin regenerar",
                        "",
                    )
                )
            else:
                findings.append(
                    (
                        "WARN",
                        ln,
                        "CLASSDEF",
                        f"«{token}» sin CSS: Bootstrap/AdminLTE heredado o hook sin prefijo js-",
                        "",
                    )
                )

    findings.sort(key=lambda f: (f[1], f[2]))
    return findings


# --- Ratchet ----------------------------------------------------------------


def _git(args: list[str]) -> tuple[int, str]:
    # `text=True` a secas decodifica con la codificación del sistema: en Windows es
    # cp1252 y cualquier template con una tilde reventaba el hilo lector de
    # `subprocess` con `UnicodeDecodeError`. `stdout` volvía vacío, la base del
    # ratchet quedaba sin contenido y TODA la deuda vieja de ese archivo se
    # reportaba como nueva (el CI, en UTF-8, no lo veía).
    r = subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )
    return r.returncode, r.stdout


def contenido_en(ref: str, rel: str) -> str | None:
    """El archivo tal como está en ``ref``. ``None`` si ahí no existía."""
    code, out = _git(["show", f"{ref}:{rel}"])
    return out if code == 0 else None


def nuevos(base_text: str | None, actual_text: str, rel: str) -> list[tuple[str, int, str, str, str]]:
    """Hallazgos bloqueantes del texto actual que la base no tenía.

    Compara **por conteo y por regla**: si una regla no subió, su deuda vieja no
    se reporta. De las que subieron se devuelven las líneas que no estaban en la
    base (y, si todas estaban, las últimas `delta`, porque igual hay más).
    """
    import tempfile

    def medir(texto: str) -> list[tuple[str, int, str, str, str]]:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d) / Path(rel).name
            tmp.write_text(texto, encoding="utf-8")
            crudos = audit_file(tmp)
        # `audit_file` deduce el alcance de la ruta; con el temporal hay que
        # recalcular las reglas sensibles a la ruta con el `rel` real.
        if tmp.suffix == ".html":
            crudos = [f for f in crudos if f[2] not in {r[0] for r in P1_RULES}]
            for rule, fn, msg in P1_RULES:
                for ln, extracto in fn(rel, texto):
                    crudos.append(("P1", ln, rule, msg, extracto))
        return [f for f in crudos if f[0] in SEVERIDADES_BLOQUEANTES]

    actuales = medir(actual_text)
    previos = medir(base_text) if base_text is not None else []

    por_regla_previa: dict[str, list[str]] = {}
    for sev, ln, rule, msg, extracto in previos:
        por_regla_previa.setdefault(rule, []).append(extracto)

    reportar: list[tuple[str, int, str, str, str]] = []
    por_regla_actual: dict[str, list[tuple[str, int, str, str, str]]] = {}
    for f in actuales:
        por_regla_actual.setdefault(f[2], []).append(f)

    for rule, hallazgos in por_regla_actual.items():
        delta = len(hallazgos) - len(por_regla_previa.get(rule, []))
        if delta <= 0:
            continue
        restantes = list(por_regla_previa.get(rule, []))
        sin_match = []
        for f in hallazgos:
            if f[4] in restantes:
                restantes.remove(f[4])
            else:
                sin_match.append(f)
        reportar.extend(sin_match[:delta] if len(sin_match) >= delta else hallazgos[-delta:])
    reportar.sort(key=lambda f: (f[1], f[2]))
    return reportar


def archivos_del_ratchet(base: str) -> list[str]:
    rutas: list[str] = []
    if base != "HEAD":
        _, out = _git(["diff", "--name-only", f"{base}...HEAD"])
        rutas += out.splitlines()
    _, out = _git(["diff", "--name-only", "HEAD"])
    rutas += out.splitlines()
    _, out = _git(["ls-files", "--others", "--exclude-standard"])
    rutas += out.splitlines()
    vistos, limpias = set(), []
    for r in rutas:
        r = r.strip()
        if not r or r in vistos:
            continue
        vistos.add(r)
        p = REPO / r
        if p.suffix in UI_SUFFIXES and p.name not in EXCLUDE_FILES and not (EXCLUDE_PARTS & set(Path(r).parts)):
            limpias.append(r)
    return sorted(limpias)


def ratchet_mode(base: str) -> int:
    rutas = archivos_del_ratchet(base)
    if not rutas:
        print(f"== design_audit --ratchet (base {base}): ningún archivo de UI cambiado ==")
        return 0
    total = 0
    for rel in rutas:
        actual_path = REPO / rel
        if not actual_path.exists():
            continue  # borrado: no puede sumar deuda
        try:
            actual = actual_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for sev, ln, rule, msg, extracto in nuevos(contenido_en(base, rel), actual, rel):
            print(f"{rel}:{ln}: [{sev}][{rule}] {msg}")
            if extracto:
                print(f"    {extracto}")
            total += 1
    print(f"\n== design_audit --ratchet (base {base}): {total} hallazgo(s) NUEVO(s) en {len(rutas)} archivo(s) ==")
    if total:
        print("La deuda preexistente no se cuenta: lo de arriba lo agregó este cambio y hay que corregirlo.")
    return 1 if total else 0


# --- Marcadores por arquetipo ------------------------------------------------
# Reemplazan al diff estructural con *similarity* que se descartó: una lista
# ordenada de marcadores que la golden tiene y la pantalla nueva tiene que
# reproducir, más lo que nunca puede aparecer. No miden parecido: miden que el
# esqueleto esté, en orden, y que no se haya colado el markup que se copia de
# las pantallas hermanas.

ARQUETIPOS: dict[str, dict[str, list]] = {
    "listado": {
        "marcadores": [
            (r'\{%\s*extends\s+"includes/base\.html"\s*%\}', False, "extiende el shell del backoffice"),
            (r"\{%\s*block\s+main-content\s*%\}", False, "bloque main-content"),
            (r'class="space-y-6"', False, "contenedor de página space-y-6"),
            (r"\{%\s*page_header\b", False, "{% page_header %}"),
            (r"\{%\s*endpage_header\s*%\}", False, "{% endpage_header %}"),
            (r"<form\b[^>]*\bdata-dynamic-list-filters\b", True, "form de filtros con data-dynamic-list-filters"),
            (r'class="bg-white rounded-xl border border-base shadow-sm overflow-hidden"', False, "card de lista"),
            (r'<table class="w-full border-collapse">', False, "tabla canónica"),
            (r'<tr class="nodo-thead-row">', False, "fila de encabezado nodo-thead-row"),
            (r'<th class="nodo-th', False, "th canónico"),
            (r'<td class="nodo-td', False, "td canónico"),
            (r"components/_paginacion\.html", True, "include de paginación"),
            (r"components/_estado_vacio\.html", False, "include de estado vacío"),
        ],
        "prohibidos": [
            (r"<h1\b", "encabezado a mano: el título es {% page_header %}"),
            (r"<style\b", "<style> local"),
            (r"page_obj\.has_(?:next|previous)", "paginación a mano: usar components/_paginacion.html"),
            (r"py-14 px-6 text-center", "estado vacío a mano: usar components/_estado_vacio.html"),
            (r"hover:bg-tertiary", "hover de fila fuera del canon: hover:bg-secondary"),
            (r"<thead[^>]*style=", "thead con style="),
        ],
    },
    "detalle": {
        "marcadores": [
            (r'\{%\s*extends\s+"includes/base\.html"\s*%\}', False, "extiende el shell del backoffice"),
            (r"\{%\s*block\s+main-content\s*%\}", False, "bloque main-content"),
            (r'class="space-y-5"', False, "contenedor de página space-y-5"),
            (r"\{%\s*page_header\b", False, "{% page_header %}"),
            (r"\{%\s*endpage_header\s*%\}", False, "{% endpage_header %}"),
            (r"components/_stat_card\.html", True, "franja de métricas con _stat_card"),
            (r'role="tablist"', False, 'contenedor de solapas con role="tablist"'),
            (r'aria-label="', False, "tablist con nombre accesible"),
            (r'role="tab"', False, 'solapa con role="tab"'),
            (r'aria-controls="', False, "solapa que apunta a su panel"),
            (r':aria-selected="', False, "estado seleccionado de la solapa"),
            (r'role="tabpanel"', False, 'panel con role="tabpanel"'),
            (r'aria-labelledby="', False, "panel que nombra a su solapa"),
        ],
        "prohibidos": [
            (r"<h1\b", "encabezado a mano: el título es {% page_header %}"),
            (r"<style\b", "<style> local"),
            (r"←\s*Volver", "«← Volver» de texto: va en page_header volver_url"),
            (r"<thead[^>]*style=", "thead con style="),
        ],
    },
    "formulario": {
        "marcadores": [
            (r'\{%\s*extends\s+"includes/base\.html"\s*%\}', False, "extiende el shell del backoffice"),
            (r"\{%\s*block\s+main-content\s*%\}", False, "bloque main-content"),
            (r'class="space-y-5"', False, "contenedor de página space-y-5"),
            (r"\{%\s*page_header\b", False, "{% page_header %}"),
            (r"volver_url=", False, "page_header con volver_url"),
            (r"\{%\s*endpage_header\s*%\}", False, "{% endpage_header %}"),
            (
                r'<form method="post"[^>]*class="bg-white rounded-xl border border-base shadow-sm p-6"',
                False,
                "surface del formulario",
            ),
            (r"\{%\s*csrf_token\s*%\}", False, "{% csrf_token %}"),
            (r"components/_form_errores\.html", False, "errores no de campo con components/_form_errores.html"),
            (r"_field\.html", False, "campos con el include _field.html"),
            (r"btn-nodo btn-tertiary btn-base", False, "acción secundaria del pie"),
            (r"btn-nodo btn-brand btn-base", False, "acción primaria del pie"),
        ],
        "prohibidos": [
            (r"<h1\b", "encabezado a mano: el título es {% page_header %}"),
            (r"<style\b", "<style> local"),
            (
                r"<label[^>]*class=\"block text-\[",
                "label con valor arbitrario: block text-sm font-medium text-heading mb-1",
            ),
            (r"←\s*Volver", "«← Volver» de texto: va en page_header volver_url"),
            (r"non_field_errors", "errores generales a mano: usar components/_form_errores.html"),
        ],
    },
    "modal": {
        "marcadores": [
            (r"x-becas-modal=", False, "x-becas-modal (foco, Tab atrapado, Escape, scroll)"),
            (r'class="fixed inset-0 z-50', False, "overlay a pantalla completa en z-50"),
            (r"bg-black/50", False, "backdrop canónico"),
            (r'role="dialog"', False, 'role="dialog"'),
            (r'aria-modal="true"', False, 'aria-modal="true"'),
            (r'aria-labelledby="', False, "diálogo que nombra su título"),
            (r"_modal_header\.html", False, "include del encabezado del modal"),
            (r'<form method="post"', False, "form POST adentro del diálogo"),
            (r"\{%\s*csrf_token\s*%\}", False, "{% csrf_token %}"),
            (r"_modal_footer\.html", False, "include del pie del modal"),
            (r"becas-modal\.js", False, "becas-modal.js cargado en customJS"),
        ],
        "prohibidos": [
            (r"<style\b", "<style> local"),
            (r"backdrop-filter\s*:", "backdrop con style=: usar la clase backdrop-blur-sm"),
            (r"Swal\.fire\(", "SweetAlert nuevo: la confirmación canónica es data-confirm-url → ModernModal"),
        ],
    },
}


def arquetipo_mode(nombre: str, rutas: list[str]) -> int:
    especificacion = ARQUETIPOS.get(nombre)
    if especificacion is None:
        print(f"arquetipo desconocido: {nombre} (hay {', '.join(sorted(ARQUETIPOS))})")
        return 1
    fallas = 0
    for ruta in rutas:
        path = Path(ruta) if Path(ruta).is_absolute() else REPO / ruta
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            print(f"{ruta}: no se puede leer")
            fallas += 1
            continue
        propias = 0
        posicion = 0
        for patron, opcional, descripcion in especificacion["marcadores"]:
            m = re.compile(patron).search(text, posicion)
            if m is None:
                if re.compile(patron).search(text):
                    print(f"{ruta}: [ARQUETIPO] fuera de orden — {descripcion}")
                    propias += 1
                elif not opcional:
                    print(f"{ruta}: [ARQUETIPO] falta el marcador — {descripcion}")
                    propias += 1
                continue
            posicion = m.end()
        for patron, motivo in especificacion["prohibidos"]:
            for ln in _lineas_de(text, re.compile(patron)):
                print(f"{ruta}:{ln}: [ARQUETIPO] prohibido — {motivo}")
                propias += 1
        print(f"{ruta}: arquetipo «{nombre}» — {'OK' if not propias else f'{propias} desvío(s)'}")
        fallas += propias
    return 1 if fallas else 0


# --- Goldens ----------------------------------------------------------------

AGENTE = REPO / ".claude" / "agents" / "chaco-design-system.md"
ARQUETIPO_FILA_RE = re.compile(r"^\|\s*Arquetipo\s*·\s*([^|]+?)\s*\|", re.I)
RUTA_BACKTICK_RE = re.compile(r"`([^`]+\.html)`")

# Las goldens saneadas por el paso 3 de la Ola 6 (anexo del agente, §3).
#
# La fuente de verdad es la tabla `## Arquetipos` del núcleo (la escribió el paso 4).
# Esta lista queda como **red del checkout sin `.claude/`** —el release lo excluye por
# `export-ignore`— y como segunda fuente que tiene que coincidir con el núcleo: si las
# dos se contradicen, o si el núcleo deja de declarar una golden que está acá, el gate
# lo reporta en vez de mirar para otro lado.
GOLDENS: list[tuple[str, str]] = [
    ("listado", "programas/templates/programas/becas/revision/personas_list.html"),
    ("detalle", "programas/templates/programas/becas/cupo/segmento_detail.html"),
    ("formulario", "programas/templates/programas/becas/config/segmento_form.html"),
    ("modal", "programas/templates/programas/becas/config/programa_list.html"),
]


def goldens_declaradas() -> list[tuple[str, str]] | None:
    """``(arquetipo, ruta de la golden)`` leídos de la tabla ``## Arquetipos``.

    ``None`` solo cuando **no hay núcleo que leer** (checkout sin ``.claude/``):
    ahí manda ``GOLDENS``. Si el núcleo existe pero no declara la tabla, devuelve
    una lista vacía y ``goldens_mode`` lo trata como error: el agente perdió su
    tabla de arquetipos.
    """
    try:
        texto = AGENTE.read_text(encoding="utf-8")
    except OSError:
        return None
    en_tabla = False
    filas: list[tuple[str, str]] = []
    for linea in texto.splitlines():
        if linea.startswith("## "):
            if linea.strip() == "## Arquetipos":
                en_tabla = True
                continue
            if en_tabla:
                break
        if not en_tabla:
            continue
        m = ARQUETIPO_FILA_RE.match(linea)
        if not m:
            continue
        nombre = m.group(1).strip().lower()
        celdas = re.split(r"(?<!\\)\|", linea.strip().strip("|"))
        contrato = celdas[-1] if celdas else ""
        ruta = RUTA_BACKTICK_RE.search(contrato)
        if ruta:
            filas.append((nombre, ruta.group(1)))
    return filas


def goldens_mode() -> int:
    nucleo = goldens_declaradas()
    fallas = 0
    if nucleo is None:
        # Checkout sin `.claude/` (el release lo excluye): no hay núcleo que leer.
        print("== design_audit --goldens: no hay núcleo en .claude/agents/: uso design_audit.GOLDENS ==")
        filas = GOLDENS
    elif not nucleo:
        print("[GOLDEN] el núcleo no declara la tabla `## Arquetipos`: sin ella no se sabe qué pantalla se clona")
        fallas += 1
        filas = GOLDENS
    else:
        filas = nucleo
        # Dos fuentes que pueden derivar: si el núcleo cambia una golden, este
        # script tiene que enterarse, porque es el que la deja en 0.
        declaradas = dict(nucleo)
        for nombre, ruta in nucleo:
            propia = dict(GOLDENS).get(nombre)
            if propia is not None and propia != ruta:
                print(f"[GOLDEN] el núcleo declara «{nombre}» en {ruta} y design_audit.GOLDENS en {propia}")
                fallas += 1
        for nombre, propia in GOLDENS:
            if nombre not in declaradas:
                print(f"[GOLDEN] design_audit.GOLDENS declara «{nombre}» en {propia} y el núcleo ya no lo declara")
                fallas += 1
    for nombre, ruta in filas:
        path = REPO / ruta
        if not path.exists():
            print(f"{ruta}: [GOLDEN] la golden del arquetipo «{nombre}» no existe")
            fallas += 1
            continue
        p1 = [f for f in audit_file(path) if f[0] in SEVERIDADES_BLOQUEANTES]
        for sev, ln, rule, msg, extracto in p1:
            print(f"{ruta}:{ln}: [GOLDEN][{rule}] {msg}")
        fallas += len(p1)
        if nombre in ARQUETIPOS:
            fallas += 0 if arquetipo_mode(nombre, [ruta]) == 0 else 1
    print(f"\n== design_audit --goldens: {fallas} hallazgo(s) en {len(filas)} golden(s) ==")
    return 1 if fallas else 0


# --- Hook --------------------------------------------------------------------


def hook_mode() -> int:
    """PostToolUse hook de Claude Code: lee el JSON del evento por stdin.

    Usa el ratchet contra `HEAD`, así que reporta **solo lo que agregó la
    edición**: la deuda previa del archivo no bloquea y no se menciona.

    Exit 0 = la edición no sumó hallazgos. Exit 2 = sí: stderr vuelve al modelo.
    """
    import json

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    fp = (payload.get("tool_input") or {}).get("file_path") or (payload.get("tool_response") or {}).get("filePath")
    if not fp:
        return 0
    path = Path(fp)
    # Fuera de alcance: fuera del repo, no-UI, kit de referencia, tokens
    try:
        in_repo = path.resolve().is_relative_to(REPO)
    except (OSError, ValueError):
        in_repo = False
    if (
        not in_repo
        or path.suffix not in UI_SUFFIXES
        or path.name in EXCLUDE_FILES
        or (EXCLUDE_PARTS & set(path.parts))
        or not path.exists()
    ):
        return 0
    rel = rel_posix(path)
    try:
        actual = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    errors = nuevos(contenido_en("HEAD", rel), actual, rel)
    if not errors:
        return 0
    sys.stderr.write(f"design_audit: tu edición agregó {len(errors)} hallazgo(s) de diseño en {path.name}:\n")
    for _, ln, rule, msg, extract in errors[:15]:
        sys.stderr.write(f"  {fp}:{ln}: [{rule}] {msg}\n")
        if extract:
            sys.stderr.write(f"      {extract}\n")
    if len(errors) > 15:
        sys.stderr.write(f"  ... y {len(errors) - 15} más (corré scripts/design_audit.py --ratchet)\n")
    sys.stderr.write(
        "Son hallazgos NUEVOS: la deuda preexistente del archivo ya se descontó. "
        "Corregilos según el inventario canónico y la golden del arquetipo.\n"
    )
    return 2


def main(argv: list[str]) -> int:
    # Consola Windows (cp1252) no soporta todos los caracteres de los extractos
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    if "--hook" in argv:
        return hook_mode()

    if "--goldens" in argv:
        return goldens_mode()

    if "--arquetipo" in argv:
        i = argv.index("--arquetipo")
        if len(argv) < i + 3:
            print("uso: design_audit.py --arquetipo {listado|detalle|formulario|modal} ARCHIVO [ARCHIVO...]")
            return 1
        return arquetipo_mode(argv[i + 1], argv[i + 2 :])

    if "--ratchet" in argv:
        base = "HEAD"
        if "--base" in argv:
            j = argv.index("--base")
            if len(argv) > j + 1:
                base = argv[j + 1]
        return ratchet_mode(base)

    if "--changed" in argv:
        targets = [p for p in changed_files() if p.exists()]
    elif argv:
        targets = [Path(a) if Path(a).is_absolute() else REPO / a for a in argv]
    else:
        targets = [REPO / t for t in DEFAULT_TARGETS if (REPO / t).exists()]

    errors = p1 = warns = 0
    for f in iter_files(targets):
        found = audit_file(f)
        if not found:
            continue
        rel = f.relative_to(REPO) if f.is_relative_to(REPO) else f
        for sev, ln, rule, msg, extract in found:
            print(f"{rel}:{ln}: [{sev}][{rule}] {msg}")
            if extract:
                print(f"    {extract}")
            if sev == "ERROR":
                errors += 1
            elif sev == "P1":
                p1 += 1
            else:
                warns += 1

    print(f"\n== design_audit: {errors} error(es), {p1} P1 (deuda), {warns} warning(s) ==")
    if p1:
        print("Los P1 son la deuda estructural del repo: no cortan acá, cortan si SUBEN (--ratchet).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
