"""Hook PreToolUse: frena `gh pr merge` hacia `development` sin `/auditoria pr` aprobada para el head.

Lee por stdin el JSON del hook (Bash o PowerShell). Sale con 0 si deja pasar; con 2 y el motivo
en stderr si frena. Solo librería estándar: corre con el `python` global, como los hooks de
`design_audit.py`. Es una guarda del proceso, no de seguridad: un merge desde la web de GitHub o
por `gh api` no pasa por acá.
"""

from __future__ import annotations

import json
import re
import shlex
import sys

REPO = "mkdir-arg/chaco-back"
BASE = "development"
MARCADOR = re.compile(r"<!--\s*auditoria-chaco\s+veredicto=(APPROVE|CHANGES_NEEDED)\s+sha=([0-9a-f]{40})\s*-->")
# Solo en posición de comando: nombrarlo en un `grep` o en un `git commit -m` no consulta GitHub.
_GH = r"""(?:"(?:[^"]*[\\/])?gh(?:\.exe)?"|'(?:[^']*[\\/])?gh(?:\.exe)?'|(?:[^\s"']*[\\/])?gh(?:\.exe)?)"""
_PALABRAS = r"(?:(?:if|then|elif|else|do|while|until|time|!)\s+)*"
_MERGE = re.compile(rf"^\s*{_PALABRAS}(?:\w+=\S*\s+)*{_GH}\s+pr\s+merge\b", re.IGNORECASE)
# `&` también es fin de comando (fondo en bash, llamada en PowerShell); `{ } ( )` abren y cierran bloques.
_SEPARADORES = ";|&\n{}()"
_CORTE_SIN_COMILLAS = re.compile(f"[{re.escape(_SEPARADORES)}]")
_ANTES_DE_COMENTARIO = " \t\n;&|"  # `#` después de esto abre un comentario; en `${#x}` no
# Cuerpos de texto que no son comandos: here-string de PowerShell y heredoc de bash (queda la línea que lo abre).
# Sin su línea de cierre no se tocan: un `<<` dentro de un string no borra lo que sigue.
_HERE_STRING = re.compile(r"@(['\"])[ \t]*\r?\n.*?^\1@", re.S | re.M)
_HEREDOC = re.compile(r"((?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_]\w*)\2[^\n]*\n).*?^\t*\3\r?$", re.S | re.M)
_CONTINUACION = re.compile(r"[\\`]\r?\n")
_REDIRECCION = re.compile(r"(?:\d*|\*)(?:>>?|<)")
_FLAGS_CON_VALOR = {
    "-R",
    "--repo",
    "--match-head-commit",
    "-t",
    "--subject",
    "-b",
    "--body",
    "-F",
    "--body-file",
    "-A",
    "--author-email",
}


class Merge:  # clase simple y no @dataclass: el hook corre en cada Bash y `dataclasses` tarda en importar
    def __init__(self, selector: str | None = None, repo: str | None = None, match_head: str | None = None):
        self.selector, self.repo, self.match_head = selector, repo, match_head


def _tramos(comando: str, escape: str) -> list[str]:
    """Corta en los separadores que están fuera de comillas: lo citado sigue siendo un argumento.

    Si al final queda una comilla abierta, el lector perdió la cuenta y suma el corte sin comillas:
    ante la duda ve un merge de más, nunca uno de menos (falla cerrado, como la consulta a GitHub).
    """
    texto = _CONTINUACION.sub(" ", _HEREDOC.sub(r"\1", _HERE_STRING.sub(r"\1\1", comando)))
    tramos, actual, comilla, previo, i = [], [], None, "\n", 0
    while i < len(texto):
        caracter = texto[i]
        if caracter == escape and comilla != "'" and i + 1 < len(texto):  # el siguiente no corta ni cierra
            actual.append(texto[i : i + 2])
            previo = texto[i + 1]
            i += 2
            continue
        if comilla:
            comilla = None if caracter == comilla else comilla
        elif caracter in "'\"":
            comilla = caracter
        elif caracter == "#" and previo in _ANTES_DE_COMENTARIO:  # comentario hasta el fin de la línea
            fin = texto.find("\n", i)
            i = len(texto) if fin == -1 else fin
            continue
        elif caracter in _SEPARADORES:
            tramos.append("".join(actual))
            actual, previo = [], caracter
            i += 1
            continue
        actual.append(caracter)
        previo = caracter
        i += 1
    tramos.append("".join(actual))
    if comilla:
        tramos += _CORTE_SIN_COMILLAS.split(texto)
    return tramos


def extraer_merges(comando: str, escape: str = "\\") -> list[Merge]:
    """`escape` es `\\` en bash y el backtick en PowerShell."""
    merges, vistos = [], set()
    for tramo in _tramos(comando, escape):
        encontrado = _MERGE.search(tramo)
        if not encontrado:
            continue
        resto = tramo[encontrado.end() :]
        try:
            tokens = shlex.split(resto)
        except ValueError:
            tokens = resto.split()
        merge = Merge()
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if _REDIRECCION.match(token):  # `2>`, `> salida.txt`, `2>/dev/null`: ni selector ni flag
                i += 2 if _REDIRECCION.fullmatch(token) else 1
                continue
            if token.startswith("--") and "=" in token:
                flag, valor = token.split("=", 1)
            elif token in _FLAGS_CON_VALOR:
                flag, valor = token, tokens[i + 1] if i + 1 < len(tokens) else ""
                i += 1
            elif token[:2] in _FLAGS_CON_VALOR:  # corto con el valor pegado: -RMkdir-arg/Chaco-Back, -R=…
                flag, valor = token[:2], token[2:].removeprefix("=")
            elif token.startswith("-"):
                flag, valor = token, ""
            else:
                flag, valor = "", token
            if flag in ("-R", "--repo"):
                merge.repo = valor
            elif flag == "--match-head-commit":
                merge.match_head = valor
            elif not flag and merge.selector is None:
                merge.selector = valor
            i += 1
        clave = (merge.selector, merge.repo, merge.match_head)
        if clave not in vistos:  # el corte sin comillas puede repetir uno: se consulta una vez
            vistos.add(clave)
            merges.append(merge)
    return merges


def _repo_de_url(url: str) -> str:
    partes = url.split("github.com/", 1)[-1].split("/")
    return "/".join(partes[:2]).lower()


def evaluar(merge: Merge, pr: dict) -> str | None:
    if _repo_de_url(pr.get("url", "")) != REPO or pr.get("baseRefName") != BASE:
        return None
    head = pr["headRefOid"].lower()
    numero = pr.get("number")
    if merge.match_head and not head.startswith(merge.match_head.lower()):
        motivo = f"--match-head-commit {merge.match_head} no es el head actual del PR #{numero} ({head[:8]})."
        if merge.match_head.startswith("$"):
            motivo += " El hook no expande variables: escribí el SHA literal."
        return motivo
    veredicto = None
    for comentario in pr.get("comments") or []:
        for valor, sha in MARCADOR.findall(comentario.get("body") or ""):
            if sha == head:
                veredicto = valor
    if veredicto == "APPROVE":
        return None
    estado = veredicto or "sin auditoría"
    return f"Falta /auditoria pr {numero} sobre {head[:8]} ({estado}). Auditá o re-sellá antes de mergear."


def consultar_pr(merge: Merge, cwd: str | None) -> dict:
    import subprocess  # solo un merge lo necesita: no se paga en cada Bash

    comando = ["gh", "pr", "view"]
    if merge.selector:
        comando.append(merge.selector)
    if merge.repo:
        comando += ["--repo", merge.repo]
    comando += ["--json", "number,url,baseRefName,headRefOid,comments"]
    resultado = subprocess.run(comando, cwd=cwd or None, capture_output=True, text=True, encoding="utf-8", timeout=20)
    if resultado.returncode != 0:
        raise RuntimeError(resultado.stderr.strip() or f"gh salió con {resultado.returncode}")
    return json.loads(resultado.stdout)


def main(stdin: str, consultar=consultar_pr) -> tuple[int, str]:
    try:
        datos = json.loads(stdin)
    except ValueError:
        return 0, ""
    if not isinstance(datos, dict):
        return 0, ""
    comando = (datos.get("tool_input") or {}).get("command") or ""
    escape = "`" if datos.get("tool_name") == "PowerShell" else "\\"
    for merge in extraer_merges(comando, escape):
        try:
            pr = consultar(merge, datos.get("cwd"))
        except Exception as exc:  # gh caído, sin red, JSON roto: sin consulta no se mergea
            return 2, f"guardia_merge: no pude consultar el PR ({exc}). Sin consulta no se mergea."
        error = evaluar(merge, pr)
        if error:
            return 2, f"guardia_merge: {error}"
    return 0, ""


if __name__ == "__main__":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # en Windows sale en cp1252: «auditor�a»
    codigo, mensaje = main(sys.stdin.buffer.read().decode("utf-8", "replace"))
    if mensaje:
        print(mensaje, file=sys.stderr)
    sys.exit(codigo)
