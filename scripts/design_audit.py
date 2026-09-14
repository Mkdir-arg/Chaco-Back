#!/usr/bin/env python3
"""Auditoría mecánica del sistema de diseño Chaco/NODO.

Chequeos mecánicos compartidos para cambios de UI. El inventario y las decisiones
operativas viven en `.claude/agents/chaco-design-system.md`, que se contrasta con
el frontend productivo antes de usar este script.

Uso:
    python scripts/design_audit.py [paths...]      # audita archivos o carpetas
    python scripts/design_audit.py --changed       # audita solo archivos modificados (git)
    python scripts/design_audit.py --hook          # modo hook de Claude Code (JSON por stdin)

Sin argumentos audita las superficies de UI del repo (templates/ + static/custom/css
+ templates de apps). Exit code 1 si hay violaciones ERROR; las WARN no cortan.

Reglas mecánicas complementarias del agente canónico de diseño:
  HEX        Cero hex hardcodeado (salvo #fff/#ffffff). Excluye chaco-tokens.css,
             los templates de correo (**/email/) y líneas con template tags
             dinámicos ({{ ... }}).
  FONT       Manrope única: Fredoka/Gellat/Geliat/Satoshi/Inter/Roboto/Montserrat.
  CONFIRM    window.confirm()/window.alert() prohibidos (SweetAlert2/DS Modal).
  SWALHEX    confirmButtonColor/cancelButtonColor prohibidos (usar buttonsStyling:false
             + customClass btn-nodo).
  GRADLEG    Gradientes legacy: FF0080/7928CA (NODO magenta) y 3B82F6/8B5CF6
             (azul→púrpura NODO) en templates/CSS.
  ICONHEX    fill=/stroke= con hex en SVG (color por token/currentColor).
  TWBUILD    Utilidad de Tailwind con variante (sm:/xl:/hover:...) o valor
             arbitrario ([82vh], [15px]) usada en un template pero ausente de
             static/custom/css/tailwind.css. El build está committeado: si se
             agrega una clase nueva hay que correr `npm run build:tailwind` y
             commitear el CSS, o la pantalla se ve mal sin ningún error.
  ZINDEX     z-index 9999 (escala del kit: topbar 20 · modal 50 · toast 80).
  OUTLINE    outline:none / outline-none (nunca sin reemplazo de ring).
  OPACITY    opacity como estado disabled (usar --bg-disabled/--text-disabled).
  DJCOMMENT  {# ... #} multilínea (se renderiza como texto; usar {% comment %}).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Superficies de UI auditadas por defecto
DEFAULT_TARGETS = [
    "templates",
    "static/custom/css",
    "core/templates",
    "dashboard/templates",
    "legajos/templates",
    "programas/templates",
    "portal/templates",
    "users/templates",
    "configuracion/templates",
    "conversaciones/templates",
    "tramites/templates",
]

# "email": los templates de correo (`**/templates/**/email/`) necesitan estilos
# inline y hex literal — ningún cliente de correo soporta CSS variables, y Outlook
# ni siquiera <style> confiable. Los colores igual salen del kit (--gradient-brand
# = #5059bc → #f98dff), pero escritos a mano: no hay forma de tokenizarlos.
# "vendor": librerías de terceros autoalojadas (Alpine, Font Awesome, vis-network,
# la tipografía). No son superficie de diseño propia y traen sus propios colores;
# se sirven desde el dominio para no depender de un CDN, no para editarlas.
EXCLUDE_PARTS = {".venv", "node_modules", ".git", "design-kb", "email", "vendor"}
# `tailwind.css` se genera desde templates/JS con `npm run build:tailwind`; sus
# valores internos pertenecen al framework y se revisan mediante el build, no
# mediante reglas pensadas para CSS escrito a mano.
EXCLUDE_FILES = {"chaco-tokens.css", "tailwind.css"}
UI_SUFFIXES = {".html", ".css", ".js"}

HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
ALLOWED_HEX = {"#fff", "#ffffff"}
DYNAMIC_RE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}")  # spans de template tags → dato del backend, se recortan del escaneo
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
        re.compile(r"window\.(confirm|alert)\s*\(|(?<![\w.])confirm\s*\("),
        "confirm()/alert() nativo prohibido — SweetAlert2 (backoffice) / DS Modal",
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


def changed_files() -> list[Path]:
    out = subprocess.run(["git", "diff", "--name-only", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout
    out += subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=REPO, capture_output=True, text=True
    ).stdout
    return [REPO / line for line in out.splitlines() if line.strip()]


# --- TWBUILD: utilidades de Tailwind que el build no tiene -------------------
# El build está committeado, así que una clase nueva no existe hasta que alguien
# corre `npm run build:tailwind`. El template compila, la auditoría pasa y la
# pantalla se ve mal en silencio (pasó con `xl:grid-cols-2` en el Cambio 58).
#
# Se verifican solo las que fallan así: las que llevan variante (`xl:`, `hover:`)
# o valor arbitrario (`max-h-[82vh]`). Una clase suelta sin variante puede venir
# del CSS legacy (Bootstrap/AdminLTE) o de un componente propio, y no se puede
# distinguir de una utilidad sin falsos positivos.

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
    limpias = set()
    # El CSS escapa lo que no es alfanumerico: `.xl\:top-6` es la clase
    # `xl:top-6`, y un hex seguido de espacio (coma, punto) es ese caracter.
    for cruda in re.findall(r"\.((?:[-a-zA-Z0-9_]|\\.|\\[0-9a-f]{1,6} ?)+)", css):
        sin_hex = re.sub(r"\\([0-9a-f]{1,6}) ?", lambda m: chr(int(m.group(1), 16)), cruda)
        limpias.add(sin_hex.replace("\\", ""))
    _CLASES_TW = limpias
    return limpias


def clases_sin_build(text: str) -> list[tuple[int, str]]:
    """``(línea, clase)`` de cada utilidad verificable que el build no declara."""
    compiladas = _clases_del_build()
    if not compiladas:
        return []
    faltantes, vistas = [], set()
    for m in CLASS_ATTR_RE.finditer(text):
        bloque = DYNAMIC_RE.sub(" ", m.group(1))
        for clase in bloque.split():
            verificable = clase.startswith(VARIANTES) or ("[" in clase and clase.endswith("]"))
            if not verificable or clase in vistas or not UTILIDAD_RE.match(clase):
                continue
            vistas.add(clase)
            if clase not in compiladas:
                faltantes.append((text[: m.start()].count(chr(10)) + 1, clase))
    return faltantes


def audit_file(path: Path) -> list[tuple[str, int, str, str, str]]:
    """Devuelve (severidad, línea, regla, mensaje, extracto)."""
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings

    lines = text.splitlines()
    is_template = path.suffix == ".html"

    for i, line in enumerate(lines, 1):
        # Pragma de excepción documentada: la línea se salta entera.
        # Uso: para valores canónicos sin token (ej. mapa badge-brand del kit).
        if "design-audit: allow" in line:
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
        for rule, sev, pat, msg in RULES:
            if pat.search(line):
                findings.append((sev, i, rule, msg, line.strip()[:100]))

    # {# ... #} multilínea (solo templates)
    if is_template:
        for m in DJCOMMENT_RE.finditer(text):
            ln = text[: m.start()].count("\n") + 1
            findings.append(
                ("ERROR", ln, "DJCOMMENT", "{# #} multilínea se renderiza como texto — usar {% comment %}", "")
            )

        for ln, clase in clases_sin_build(text):
            findings.append(
                (
                    "ERROR",
                    ln,
                    "TWBUILD",
                    f"«{clase}» no está en el CSS compilado — correr `npm run build:tailwind` y commitear",
                    "",
                )
            )

    return findings


def hook_mode() -> int:
    """PostToolUse hook de Claude Code: lee el JSON del evento por stdin.

    Exit 0 = sin violaciones (o archivo fuera de alcance). Exit 2 = hay ERRORs:
    stderr se devuelve al modelo para que corrija antes de seguir.
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
    errors = [f for f in audit_file(path) if f[0] == "ERROR"]
    if not errors:
        return 0
    sys.stderr.write(f"design_audit: {len(errors)} violación(es) del sistema de diseño en {path.name}:\n")
    for _, ln, rule, msg, extract in errors[:15]:
        sys.stderr.write(f"  {fp}:{ln}: [{rule}] {msg}\n")
        if extract:
            sys.stderr.write(f"      {extract}\n")
    if len(errors) > 15:
        sys.stderr.write(f'  ... y {len(errors) - 15} más (corré scripts/design_audit.py "{fp}")\n')
    sys.stderr.write(
        "Si las introdujo TU edición, corregilas según el inventario canónico y el código productivo. "
        "Si son preexistentes de una pantalla legacy que no estás migrando, no bloquean: mencionáselo al usuario y seguí.\n"
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

    if "--changed" in argv:
        targets = [p for p in changed_files() if p.exists()]
    elif argv:
        targets = [Path(a) if Path(a).is_absolute() else REPO / a for a in argv]
    else:
        targets = [REPO / t for t in DEFAULT_TARGETS if (REPO / t).exists()]

    errors = warns = 0
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
            else:
                warns += 1

    print(f"\n== design_audit: {errors} error(es), {warns} warning(s) ==")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
