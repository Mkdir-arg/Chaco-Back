#!/usr/bin/env python3
"""Verifica el contrato operativo del agente canónico de diseño.

Solo stdlib: el hook de Claude Code y el CI lo corren sin venv.

No define reglas de UI: valida que el inventario que vive en
``.claude/agents/chaco-design-system.md`` sea estructuralmente usable, que sus
fichas existan y que sus consumidores no vuelvan a introducir otra autoridad.

Lo que mira:

* **Inventario y arquetipos.** Las filas de ``## Inventario operativo inicial`` y
  de ``## Arquetipos`` (esta última la escribe el paso 4 de la Ola 6; mientras no
  exista no se exige). Las celdas se parten por ``|`` **sin escapar**: una fila
  que escribe ``\\|`` adentro de una celda ya no se descarta en silencio.
* **Evidencia.** Cada fila cita al menos una ruta del repo que existe. La ficha
  de la fila (``Ficha: `.claude/design/…` ``) también aporta evidencia, así que
  un contrato largo puede vivir en la ficha en vez de inflar la celda.
* **Regla del mismo diff.** Si el PR toca una pieza canónica, el mismo diff tiene
  que actualizar **el núcleo o la ficha de esa fila**. No la disparan el
  ``tailwind.css`` generado, los tests ni las vistas (siguen validándose como
  rutas que existen).
* **Límites del núcleo** (``--limites``): tamaño, largo de celda y cero historia.
  Quedan apagados por defecto hasta que el paso 4 reescriba el núcleo; el mismo
  PR que lo reescriba enciende la bandera en el CI.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_REPO = Path(__file__).resolve().parent.parent
AGENT_RELATIVE = Path(".claude/agents/chaco-design-system.md")
FICHAS_DIR = Path(".claude/design")
CONSUMER_FILES = (
    Path("AGENTS.md"),
    Path("CLAUDE.md"),
    Path(".claude/agents/chaco-frontend.md"),
    Path(".claude/agents/chaco-design-reviewer.md"),
)
AUTHORITY_FILES = CONSUMER_FILES + (
    Path("docs/design-kb/SKILL.md"),
    Path("docs/design-kb/readme.md"),
    Path("docs/design-kb/reference/README.md"),
    Path("docs/design-kb/reference/design-kb/IMPLEMENT_DESIGN_SYSTEM.md"),
    Path("docs/design-kb/reference/design-kb/design-constitution.md"),
    Path("scripts/design_audit.py"),
)
CLASSIFICATIONS = (
    "Canónico reutilizable",
    "Legacy solo mantenimiento",
    "Duplicado o conflictivo",
)
BANNED_AUTHORITY_CLAIMS = (
    "calcado del kit",
    "verdad visual",
    "canon: chaco-design-reviewer",
    "la fuente de verdad es `docs/design-kb`",
    "fix the code to match",
    "inviolable laws",
    "take precedence over personal",
)
EVIDENCE_PREFIXES = (
    "static/",
    "templates/",
    "portal/",
    "users/",
    "programas/",
    "core/",
    "legajos/",
    "configuracion/",
    "dashboard/",
    "conversaciones/",
    "docs/",
    ".claude/",
)
# Rutas que citan las filas pero NO disparan la regla del mismo diff.
# `tailwind.css` se regenera en cada build; los tests y las vistas se citan como
# contrato (y se validan como rutas que existen), pero tocarlos no cambia el
# contrato visual. Sin estas tres exclusiones la regla cubría 71 rutas y era el
# motor del changelog que hinchó el núcleo hasta 64 KB.
SIN_MISMO_DIFF = ("static/custom/css/tailwind.css",)
SIN_MISMO_DIFF_PARTES = ("/tests/", "/views/")

FICHA_RE = re.compile(r"Ficha: `(\.claude/design/[^`]+\.md)`")
NUCLEO_MAX_BYTES = 30_000
CELDA_MAX_CARACTERES = 450
# La historia va a `docs/internal/requerimientos.md`, nunca al agente: es lo que
# convirtió el núcleo en un changelog de filas de 4.000 caracteres.
HISTORIA_RE = re.compile(
    r"Cambio \d+|Ola \d+|\b(?:POP|TIT|CMP|ALR|DE|DP)-[A-Z]?\d+|\bW\d-"
    r"|\d{1,2}-(?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)-20\d\d"
)


def relative_path(path: str | Path) -> Path:
    return Path(path.replace("\\", "/"))


def read_text(repo: Path, relative: Path, errors: list[str]) -> str:
    target = repo / relative
    if not target.is_file():
        errors.append(f"missing required file: {relative.as_posix()}")
        return ""
    return target.read_text(encoding="utf-8")


def split_cells(line: str) -> list[str]:
    """Parte una fila de tabla Markdown en celdas.

    Un ``|`` separa celdas salvo que esté escapado (``\\|``) o adentro de un code
    span. Las dos formas aparecen en el inventario: filas que documentan filtros
    de Django (``` `user_groups_list|json_script:…` ```, ``` `|safe` ``,
    `` `|puede` ``) y una que documenta una expresión regular de JS (``(^|;)``).
    Partir a secas daba 4 o 5 trozos y la fila se descartaba **en silencio**:
    así se perdían tres filas y la evidencia canónica que declaran.
    """
    celdas: list[str] = []
    buffer: list[str] = []
    en_code_span = False
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if c == "\\" and i + 1 < n and line[i + 1] == "|":
            buffer.append("|")
            i += 2
            continue
        if c == "`":
            en_code_span = not en_code_span
        if c == "|" and not en_code_span:
            celdas.append("".join(buffer))
            buffer = []
        else:
            buffer.append(c)
        i += 1
    celdas.append("".join(buffer))
    return [celda.strip() for celda in celdas]


def table_rows(agent_text: str, heading: str, errors: list[str], *, required: bool) -> list[tuple[str, str, str]]:
    """Filas de 3 celdas de la tabla que sigue a ``heading``.

    Una fila mal formada es un error, no un descarte: el modo viejo
    (``continue``) escondía filas enteras del inventario.
    """
    rows: list[tuple[str, str, str]] = []
    inside = False
    for line in agent_text.splitlines():
        if line.startswith("## "):
            if line.strip() == heading:
                inside = True
                continue
            if inside:
                break
        if not inside:
            continue
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = split_cells(line.strip().strip("|"))
        if cells and cells[0] in {"Pieza", "Arquetipo"}:
            continue
        if len(cells) != 3:
            errors.append(f"malformed table row under '{heading}' ({len(cells)} cells): {cells[0][:60]}")
            continue
        classification = cells[1]
        if not classification.startswith(CLASSIFICATIONS):
            errors.append(f"invalid inventory classification for '{cells[0]}': {classification}")
            continue
        rows.append((cells[0], classification, cells[2]))
    if required and not rows:
        errors.append("missing inventory table rows")
    return rows


def inventory_rows(agent_text: str, errors: list[str]) -> list[tuple[str, str, str]]:
    return table_rows(agent_text, "## Inventario operativo inicial", errors, required=True)


def archetype_rows(agent_text: str, errors: list[str]) -> list[tuple[str, str, str]]:
    """Tabla ``## Arquetipos``. La escribe el paso 4 de la Ola 6: hasta entonces, vacía."""
    return table_rows(agent_text, "## Arquetipos", errors, required=False)


def evidence_paths(contract: str) -> list[Path]:
    paths: list[Path] = []
    for fragment in contract.split("`"):
        candidate = fragment.strip()
        if candidate.startswith(EVIDENCE_PREFIXES):
            paths.append(relative_path(candidate))
    return paths


def ficha_de(contract: str) -> Path | None:
    match = FICHA_RE.search(contract)
    return relative_path(match.group(1)) if match else None


def dispara_mismo_diff(evidence: Path) -> bool:
    ruta = evidence.as_posix()
    if ruta in SIN_MISMO_DIFF:
        return False
    return not any(parte in f"/{ruta}" for parte in SIN_MISMO_DIFF_PARTES)


def limites_del_nucleo(repo: Path, agent_text: str, rows: list[tuple[str, str, str]]) -> list[str]:
    """Núcleo corto, celdas cortas y sin historia (Ola 6, paso 4)."""
    errores: list[str] = []
    tamanio = len((repo / AGENT_RELATIVE).read_bytes())
    if tamanio > NUCLEO_MAX_BYTES:
        errores.append(f"core agent is too large: {tamanio} bytes (max {NUCLEO_MAX_BYTES})")
    for name, _classification, contract in rows:
        if len(contract) > CELDA_MAX_CARACTERES:
            errores.append(
                f"inventory contract cell too long for '{name}': {len(contract)} chars "
                f"(max {CELDA_MAX_CARACTERES}; el detalle va en la ficha)"
            )
    for historia in sorted(set(HISTORIA_RE.findall(agent_text))):
        errores.append(f"history reference in the core agent: {historia} (va en docs/internal/requerimientos.md)")
    return errores


def changed_from_git(repo: Path, base: str | None) -> list[Path]:
    command = ["git", "diff", "--name-only"]
    if base:
        command.append(f"{base}...HEAD")
    else:
        command.append("HEAD")
    result = subprocess.run(command, cwd=repo, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "could not read git diff")
    changes = [relative_path(line) for line in result.stdout.splitlines() if line.strip()]
    if not base:
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        changes.extend(relative_path(line) for line in untracked.stdout.splitlines() if line.strip())
    return changes


def validate(repo: Path, changed: list[Path] | None = None, *, limites: bool = False) -> list[str]:
    errors: list[str] = []
    agent_text = read_text(repo, AGENT_RELATIVE, errors)
    if not agent_text:
        return errors

    for required in CLASSIFICATIONS + ("Reconciliación obligatoria", "mismo PR"):
        if required not in agent_text:
            errors.append(f"agent is missing required contract text: {required}")

    rows = inventory_rows(agent_text, errors) + archetype_rows(agent_text, errors)
    # Pieza canónica → qué archivos satisfacen la regla del mismo diff: el núcleo
    # siempre, y la ficha de esa fila si la declara.
    guardianes: dict[Path, set[Path]] = {}
    fichas_citadas: set[Path] = set()
    for name, classification, contract in rows:
        ficha = ficha_de(contract)
        if ficha is not None:
            fichas_citadas.add(ficha)
            if not (repo / ficha).is_file():
                errors.append(f"inventory row '{name}' cites a ficha that does not exist: {ficha.as_posix()}")

        paths = evidence_paths(contract)
        if ficha is not None and (repo / ficha).is_file():
            # La evidencia declarada en la ficha vale como evidencia de la fila:
            # así el contrato largo baja a la ficha sin inflar la celda.
            paths += evidence_paths((repo / ficha).read_text(encoding="utf-8"))
        paths = [p for p in paths if p != ficha]
        if not paths:
            errors.append(f"inventory row has no code evidence: {name}")
            continue
        for evidence in paths:
            if not (repo / evidence).exists():
                errors.append(f"inventory evidence does not exist for '{name}': {evidence.as_posix()}")
            if classification.startswith("Canónico reutilizable") and dispara_mismo_diff(evidence):
                guardianes.setdefault(evidence, {AGENT_RELATIVE})
                if ficha is not None:
                    guardianes[evidence].add(ficha)

    huerfanas = (
        sorted(
            p.relative_to(repo).as_posix()
            for p in (repo / FICHAS_DIR).rglob("*.md")
            if relative_path(p.relative_to(repo).as_posix()) not in fichas_citadas
        )
        if (repo / FICHAS_DIR).is_dir()
        else []
    )
    for huerfana in huerfanas:
        errors.append(f"ficha in .claude/design is not cited by any inventory row: {huerfana}")

    for relative in CONSUMER_FILES:
        content = read_text(repo, relative, errors)
        if content and AGENT_RELATIVE.as_posix() not in content.replace("\\", "/"):
            errors.append(f"consumer does not reference canonical agent: {relative.as_posix()}")

    for relative in AUTHORITY_FILES + tuple(sorted(fichas_citadas)):
        content = read_text(repo, relative, errors)
        lowered = content.casefold()
        for banned in BANNED_AUTHORITY_CLAIMS:
            if banned.casefold() in lowered:
                errors.append(f"obsolete authority claim in {relative.as_posix()}: {banned}")

    if limites:
        errors.extend(limites_del_nucleo(repo, agent_text, rows))

    if changed is not None:
        changed_set = set(changed)
        sin_actualizar = sorted(
            evidence.as_posix()
            for evidence, aceptados in guardianes.items()
            if evidence in changed_set and not (aceptados & changed_set)
        )
        if sin_actualizar:
            formatted = ", ".join(sin_actualizar)
            errors.append(
                f"changed canonical UI evidence ({formatted}) must update "
                ".claude/agents/chaco-design-system.md (or its ficha in .claude/design/) in the same diff"
            )

    return errors


def hook_target() -> Path | None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return None
    tool_input = payload.get("tool_input") or {}
    tool_response = payload.get("tool_response") or {}
    file_path = tool_input.get("file_path") or tool_response.get("filePath")
    return Path(file_path) if file_path else None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--changed", action="store_true", help="validate the current working-tree diff")
    parser.add_argument("--base", help="compare HEAD against this base ref")
    parser.add_argument("--changed-file", action="append", default=[], help="explicit changed file; useful for tests")
    parser.add_argument("--hook", action="store_true", help="validate contract files after a Claude edit")
    parser.add_argument(
        "--limites",
        action="store_true",
        help="exigir los límites del núcleo (tamaño, celdas y cero historia); los enciende el paso 4 de la Ola 6",
    )
    args = parser.parse_args(argv)
    repo = args.repo.resolve()

    if args.hook:
        target = hook_target()
        if target is None:
            return 0
        try:
            relative = target.resolve().relative_to(repo)
        except ValueError:
            return 0
        es_ficha = FICHAS_DIR in relative.parents
        if not es_ficha and relative not in AUTHORITY_FILES and relative != AGENT_RELATIVE:
            return 0

    changed: list[Path] | None = None
    if args.changed_file:
        changed = [relative_path(path) for path in args.changed_file]
    elif args.changed or args.base:
        try:
            changed = changed_from_git(repo, args.base)
        except RuntimeError as exc:
            print(f"design-agent contract: ERROR\n- {exc}")
            return 1

    errors = validate(repo, changed, limites=args.limites)
    if errors:
        print("design-agent contract: ERROR")
        for error in errors:
            print(f"- {error}")
        return 1

    print("design-agent contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
