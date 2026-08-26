#!/usr/bin/env python3
"""Verifica el contrato operativo del agente canónico de diseño.

No define reglas de UI: valida que el inventario que vive en
``.claude/agents/chaco-design-system.md`` sea estructuralmente usable y que sus
consumidores no vuelvan a introducir otra autoridad.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

DEFAULT_REPO = Path(__file__).resolve().parent.parent
AGENT_RELATIVE = Path(".claude/agents/chaco-design-system.md")
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
EVIDENCE_PREFIXES = ("static/", "templates/", "portal/", "users/", "programas/", "docs/", ".claude/")


def relative_path(path: str | Path) -> Path:
    return Path(path.replace("\\", "/"))


def read_text(repo: Path, relative: Path, errors: list[str]) -> str:
    target = repo / relative
    if not target.is_file():
        errors.append(f"missing required file: {relative.as_posix()}")
        return ""
    return target.read_text(encoding="utf-8")


def inventory_rows(agent_text: str, errors: list[str]) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    in_inventory = False
    for line in agent_text.splitlines():
        if line.startswith("## "):
            if line.strip() == "## Inventario operativo inicial":
                in_inventory = True
                continue
            if in_inventory:
                break
        if not in_inventory:
            continue
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 3 or cells[0] == "Pieza":
            continue
        classification = cells[1]
        if not classification.startswith(CLASSIFICATIONS):
            errors.append(f"invalid inventory classification for '{cells[0]}': {classification}")
            continue
        rows.append((cells[0], classification, cells[2]))
    if not rows:
        errors.append("missing inventory table rows")
    return rows


def evidence_paths(contract: str) -> list[Path]:
    paths: list[Path] = []
    for fragment in contract.split("`"):
        candidate = fragment.strip()
        if candidate.startswith(EVIDENCE_PREFIXES):
            paths.append(relative_path(candidate))
    return paths


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


def validate(repo: Path, changed: list[Path] | None = None) -> list[str]:
    errors: list[str] = []
    agent_text = read_text(repo, AGENT_RELATIVE, errors)
    if not agent_text:
        return errors

    for required in CLASSIFICATIONS + ("Reconciliación obligatoria", "mismo PR"):
        if required not in agent_text:
            errors.append(f"agent is missing required contract text: {required}")

    rows = inventory_rows(agent_text, errors)
    canonical_evidence: set[Path] = set()
    for name, classification, contract in rows:
        paths = evidence_paths(contract)
        if not paths:
            errors.append(f"inventory row has no code evidence: {name}")
            continue
        for evidence in paths:
            if not (repo / evidence).exists():
                errors.append(f"inventory evidence does not exist for '{name}': {evidence.as_posix()}")
            if classification.startswith("Canónico reutilizable"):
                canonical_evidence.add(evidence)

    for relative in CONSUMER_FILES:
        content = read_text(repo, relative, errors)
        if content and AGENT_RELATIVE.as_posix() not in content.replace("\\", "/"):
            errors.append(f"consumer does not reference canonical agent: {relative.as_posix()}")

    for relative in AUTHORITY_FILES:
        content = read_text(repo, relative, errors)
        lowered = content.casefold()
        for banned in BANNED_AUTHORITY_CLAIMS:
            if banned.casefold() in lowered:
                errors.append(f"obsolete authority claim in {relative.as_posix()}: {banned}")

    if changed is not None:
        changed_set = set(changed)
        changed_canonical = sorted(path for path in canonical_evidence if path in changed_set)
        if changed_canonical and AGENT_RELATIVE not in changed_set:
            formatted = ", ".join(path.as_posix() for path in changed_canonical)
            errors.append(
                f"changed canonical UI evidence ({formatted}) must update .claude/agents/chaco-design-system.md in the same diff"
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
        if relative not in AUTHORITY_FILES and relative != AGENT_RELATIVE:
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

    errors = validate(repo, changed)
    if errors:
        print("design-agent contract: ERROR")
        for error in errors:
            print(f"- {error}")
        return 1

    print("design-agent contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
