# Skill `/auditoria` — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** una skill de proyecto con dos modos (`completa` y `pr`), un agente auditor y un hook que frena
`gh pr merge` sin auditoría aprobada para el SHA del PR.

**Architecture:** la skill es Markdown en `.claude/skills/auditoria/` (rúbricas adaptadas de Thermos +
piezas de Chaco). El modo B lanza dos `chaco-auditor` en paralelo y publica un comentario con un marcador;
`.claude/hooks/guardia_merge.py` (stdlib) lee ese marcador vía `gh pr view` antes de dejar pasar el merge.

**Tech Stack:** Markdown de skills/agentes de Claude Code · Python stdlib (hook) · Django `SimpleTestCase` (test
del hook) · `gh` CLI.

**Spec:** `docs/superpowers/specs/2026-10-23-skill-auditoria-design.md`

## Global Constraints

- Rama `feature/skill-auditoria`, worktree `.claude/worktrees/skill-auditoria`, PR contra `development`.
- Repo GitHub: `Mkdir-arg/Chaco-Back` (todo `gh` con `--repo Mkdir-arg/Chaco-Back`).
- Python de tests: `C:/Users/mkdir/Proyectos/Chaco/.venv312/Scripts/python.exe` (Py 3.12 + Dj 5.2, igual al CI);
  ruff con `C:/Users/mkdir/Proyectos/Chaco/.venv/Scripts/python.exe -m ruff`. En Git Bash: `export PYTHONIOENCODING=utf-8`.
- Tests: `PYTEST_RUNNING=1 DJANGO_SYNCDB_PROJECT_APPS=True DJANGO_SECRET_KEY=test-key <py312> manage.py test <módulo>`.
- Marcador del comentario, exacto: `<!-- auditoria-chaco veredicto=APPROVE|CHANGES_NEEDED sha=<40 hex minúsculas> -->`.
- Severidad modo B: `[BLOCKER]` / `[MAJOR]` / `[MINOR]`. Severidad modo A: `CRÍTICA|ALTA|MEDIA|BAJA|INFO`.
- Esfuerzo modo A: `S|S-M|M|L` → 2/4/8/20 h.
- La auditoría nunca edita código del producto; toda solución preserva lógica y estética o queda como
  `DECISIÓN CLIENTE: <propuesta por defecto>`.
- Rúbricas adaptadas citan origen `github.com/cursor/plugins` (thermos, commit `8b3326d`) y licencia MIT.
- Nunca `git stash` en este repo (sesiones concurrentes).

---

### Task 1: Hook `guardia_merge.py` con su test

**Files:**
- Create: `.claude/hooks/guardia_merge.py`
- Test: `core/tests/test_guardia_merge.py`

**Interfaces:**
- Produces: `extraer_merges(comando: str) -> list[Merge]`, `Merge(selector, repo, match_head)`,
  `evaluar(merge: Merge, pr: dict) -> str | None`, `consultar_pr(merge: Merge, cwd: str | None) -> dict`,
  `main(stdin: str, consultar=consultar_pr) -> tuple[int, str]`. `pr` es el JSON de
  `gh pr view --json number,url,baseRefName,headRefOid,comments`.

- [ ] **Step 1: Write the failing test** — `core/tests/test_guardia_merge.py`:

```python
"""El hook `guardia_merge` frena `gh pr merge` sin `/auditoria pr` aprobada para el head.

`.claude/` no viaja al release (export-ignore): el test se saltea en el snapshot de `main`
y corre en el CI de `development`, igual que los de `design_audit.py` en `test_gates_ci`.
`gh` se simula: el test no toca la red.
"""

import importlib.util
import json
import unittest
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parents[2]
HOOK = RAIZ / ".claude" / "hooks" / "guardia_merge.py"

HEAD = "a" * 40
VIEJO = "b" * 40


def _cargar():
    spec = importlib.util.spec_from_file_location("guardia_merge", HOOK)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _pr(comentarios=(), base="development", url="https://github.com/Mkdir-arg/Chaco-Back/pull/940"):
    return {
        "number": 940,
        "url": url,
        "baseRefName": base,
        "headRefOid": HEAD,
        "comments": [{"body": cuerpo} for cuerpo in comentarios],
    }


def _marca(veredicto, sha):
    return f"## Auditoría\n<!-- auditoria-chaco veredicto={veredicto} sha={sha} -->"


@unittest.skipUnless(HOOK.exists(), "hace falta .claude/hooks/guardia_merge.py (no viaja al release)")
class GuardiaMergeTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.guardia = _cargar()

    def _correr(self, comando, pr=None, error=None):
        llamadas = []

        def consultar(merge, cwd):
            llamadas.append(merge)
            if error:
                raise error
            return pr

        stdin = json.dumps({"tool_name": "Bash", "tool_input": {"command": comando}, "cwd": "."})
        codigo, mensaje = self.guardia.main(stdin, consultar=consultar)
        return codigo, mensaje, llamadas

    def test_comando_sin_merge_no_consulta_github(self):
        codigo, _, llamadas = self._correr("git status && gh pr view 940")
        self.assertEqual((codigo, llamadas), (0, []))

    def test_stdin_invalido_deja_pasar(self):
        self.assertEqual(self.guardia.main("no es json")[0], 0)
        self.assertEqual(self.guardia.main("[1, 2]")[0], 0)

    def test_sin_comentario_de_auditoria_frena(self):
        codigo, mensaje, _ = self._correr("gh pr merge 940 --merge", _pr())
        self.assertEqual(codigo, 2)
        self.assertIn("/auditoria pr 940", mensaje)

    def test_aprobado_para_un_sha_viejo_frena(self):
        codigo, _, _ = self._correr("gh pr merge 940 --merge", _pr([_marca("APPROVE", VIEJO)]))
        self.assertEqual(codigo, 2)

    def test_changes_needed_frena(self):
        codigo, mensaje, _ = self._correr("gh pr merge 940 --merge", _pr([_marca("CHANGES_NEEDED", HEAD)]))
        self.assertEqual(codigo, 2)
        self.assertIn("CHANGES_NEEDED", mensaje)

    def test_vale_el_ultimo_veredicto_sobre_el_head(self):
        aprobado_y_rechazado = _pr([_marca("APPROVE", HEAD), _marca("CHANGES_NEEDED", HEAD)])
        rechazado_y_aprobado = _pr([_marca("CHANGES_NEEDED", HEAD), _marca("APPROVE", HEAD)])
        self.assertEqual(self._correr("gh pr merge 940 --merge", aprobado_y_rechazado)[0], 2)
        self.assertEqual(self._correr("gh pr merge 940 --merge", rechazado_y_aprobado)[0], 0)

    def test_aprobado_para_el_head_deja_pasar(self):
        codigo, mensaje, _ = self._correr("gh pr merge 940 --merge", _pr([_marca("APPROVE", HEAD)]))
        self.assertEqual((codigo, mensaje), (0, ""))

    def test_match_head_commit_distinto_frena(self):
        comando = "gh pr merge 940 --merge --match-head-commit bbbbbbb"
        codigo, mensaje, _ = self._correr(comando, _pr([_marca("APPROVE", HEAD)]))
        self.assertEqual(codigo, 2)
        self.assertIn("match-head-commit", mensaje)

    def test_match_head_commit_corto_y_con_igual(self):
        comando = "gh pr merge 940 --merge --match-head-commit=AAAAAAA"
        self.assertEqual(self._correr(comando, _pr([_marca("APPROVE", HEAD)]))[0], 0)

    def test_otra_base_u_otro_repo_deja_pasar(self):
        self.assertEqual(self._correr("gh pr merge 940", _pr(base="main"))[0], 0)
        otro = _pr(url="https://github.com/Mkdir-arg/Chaco-mobile/pull/12")
        self.assertEqual(self._correr("gh pr merge 12", otro)[0], 0)

    def test_gh_caido_frena(self):
        codigo, mensaje, _ = self._correr("gh pr merge 940", error=RuntimeError("sin red"))
        self.assertEqual(codigo, 2)
        self.assertIn("sin red", mensaje)

    def test_extrae_selector_repo_y_sha_de_un_comando_compuesto(self):
        comando = (
            "cd x && gh pr merge 940 -R Mkdir-arg/Chaco-Back --squash "
            "--match-head-commit abc1234 --delete-branch; echo ok"
        )
        merges = self.guardia.extraer_merges(comando)
        self.assertEqual(len(merges), 1)
        merge = merges[0]
        self.assertEqual((merge.selector, merge.repo, merge.match_head), ("940", "Mkdir-arg/Chaco-Back", "abc1234"))

    def test_merge_sin_selector_usa_la_rama_actual(self):
        (merge,) = self.guardia.extraer_merges("gh pr merge --merge --delete-branch")
        self.assertIsNone(merge.selector)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_RUNNING=1 DJANGO_SYNCDB_PROJECT_APPS=True DJANGO_SECRET_KEY=test-key C:/Users/mkdir/Proyectos/Chaco/.venv312/Scripts/python.exe manage.py test core.tests.test_guardia_merge -v 2`
Expected: `skipped 'hace falta .claude/hooks/guardia_merge.py'` en todos (el hook no existe). Para ver
el rojo real, crear el hook vacío (`touch`) y correr de nuevo: `AttributeError: module 'guardia_merge' has no attribute 'main'`.

- [ ] **Step 3: Write the implementation** — `.claude/hooks/guardia_merge.py`:

```python
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
import subprocess
import sys
from dataclasses import dataclass

REPO = "mkdir-arg/chaco-back"
BASE = "development"
MARCADOR = re.compile(r"<!--\s*auditoria-chaco\s+veredicto=(APPROVE|CHANGES_NEEDED)\s+sha=([0-9a-f]{40})\s*-->")
_MERGE = re.compile(r"\bgh\s+pr\s+merge\b")
_SEPARADORES = re.compile(r"&&|\|\||[;|\n]")
_FLAGS_CON_VALOR = {
    "-R", "--repo", "--match-head-commit", "-t", "--subject", "-b", "--body",
    "-F", "--body-file", "-A", "--author-email",
}


@dataclass
class Merge:
    selector: str | None = None
    repo: str | None = None
    match_head: str | None = None


def extraer_merges(comando: str) -> list[Merge]:
    merges = []
    for tramo in _SEPARADORES.split(comando):
        encontrado = _MERGE.search(tramo)
        if not encontrado:
            continue
        resto = tramo[encontrado.end():]
        try:
            tokens = shlex.split(resto)
        except ValueError:
            tokens = resto.split()
        merge = Merge()
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token.startswith("--") and "=" in token:
                flag, valor = token.split("=", 1)
            elif token in _FLAGS_CON_VALOR:
                flag, valor = token, tokens[i + 1] if i + 1 < len(tokens) else ""
                i += 1
            elif token.startswith("-"):
                flag, valor = token, ""
            else:
                flag, valor = "", token
            if flag in ("-R", "--repo"):
                merge.repo = valor
            elif flag == "--match-head-commit":
                merge.match_head = valor.lower()
            elif not flag and merge.selector is None:
                merge.selector = valor
            i += 1
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
    if merge.match_head and not head.startswith(merge.match_head):
        return f"--match-head-commit {merge.match_head} no es el head actual del PR #{numero} ({head[:8]})."
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
    comando = ["gh", "pr", "view"]
    if merge.selector:
        comando.append(merge.selector)
    if merge.repo:
        comando += ["--repo", merge.repo]
    comando += ["--json", "number,url,baseRefName,headRefOid,comments"]
    resultado = subprocess.run(
        comando, cwd=cwd or None, capture_output=True, text=True, encoding="utf-8", timeout=20
    )
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
    for merge in extraer_merges(comando):
        try:
            pr = consultar(merge, datos.get("cwd"))
        except Exception as exc:  # gh caído, sin red, JSON roto: sin consulta no se mergea
            return 2, f"guardia_merge: no pude consultar el PR ({exc}). Sin consulta no se mergea."
        error = evaluar(merge, pr)
        if error:
            return 2, f"guardia_merge: {error}"
    return 0, ""


if __name__ == "__main__":
    codigo, mensaje = main(sys.stdin.buffer.read().decode("utf-8", "replace"))
    if mensaje:
        print(mensaje, file=sys.stderr)
    sys.exit(codigo)
```

- [ ] **Step 4: Run test to verify it passes**

Run: el comando del Step 2. Expected: `Ran 13 tests … OK`.

- [ ] **Step 5: Mutation check** — en `evaluar`, cambiar temporalmente `if sha == head:` por `if True:`;
correr el test: `test_aprobado_para_un_sha_viejo_frena` tiene que dar FAIL. Revertir y confirmar OK.

- [ ] **Step 6: Lint**

Run: `C:/Users/mkdir/Proyectos/Chaco/.venv/Scripts/python.exe -m ruff check .claude/hooks/guardia_merge.py core/tests/test_guardia_merge.py`
y `… -m ruff format --check` sobre los mismos. Expected: sin hallazgos (si `format --check` marca, correr `ruff format` sobre esos dos archivos).

- [ ] **Step 7: Commit**

```bash
git add .claude/hooks/guardia_merge.py core/tests/test_guardia_merge.py
git commit -m "feat(auditoria): hook guardia_merge frena gh pr merge sin auditoría aprobada para el head"
```

---

### Task 2: Registrar el hook en `.claude/settings.json`

**Files:**
- Modify: `.claude/settings.json` (agregar `PreToolUse` junto al `PostToolUse` existente)

**Interfaces:**
- Consumes: `.claude/hooks/guardia_merge.py` (Task 1).

El hook se invoca con un lanzador que resuelve la ruta con `CLAUDE_PROJECT_DIR` y **sale con 0 si el archivo no
existe**: con una ruta relativa, una sesión cuyo cwd sea un worktree viejo (sin el hook) haría que `python` muera
con código 2 «can't open file», y un `PreToolUse` con código 2 frena **todos** los comandos.

- [ ] **Step 1: Agregar el bloque** (clave `PreToolUse` dentro de `"hooks"`, antes de `PostToolUse`):

```json
"PreToolUse": [
  {
    "matcher": "Bash|PowerShell",
    "hooks": [
      {
        "type": "command",
        "command": "python",
        "args": [
          "-c",
          "import os,runpy;p=os.path.join(os.environ.get('CLAUDE_PROJECT_DIR','.'),'.claude','hooks','guardia_merge.py');os.path.isfile(p) and runpy.run_path(p,run_name='__main__')"
        ],
        "timeout": 30
      }
    ]
  }
],
```

Sin `statusMessage`: corre en cada comando de Bash/PowerShell y un mensaje fijo confundiría.
Si el control de permisos bloquea la edición (Self-Modification), dejar el bloque al usuario para pegar.

- [ ] **Step 2: Validar el JSON y el lanzador**

```bash
python -c "import json;json.load(open('.claude/settings.json',encoding='utf-8'));print('json ok')"
L="import os,runpy;p=os.path.join(os.environ.get('CLAUDE_PROJECT_DIR','.'),'.claude','hooks','guardia_merge.py');os.path.isfile(p) and runpy.run_path(p,run_name='__main__')"
echo '{"tool_name":"Bash","tool_input":{"command":"git status"},"cwd":"."}' | CLAUDE_PROJECT_DIR="$PWD" python -c "$L"; echo "exit=$?"        # → exit=0
echo '{"tool_name":"Bash","tool_input":{"command":"gh pr merge 1"},"cwd":"."}' | CLAUDE_PROJECT_DIR="/c/no/existe" python -c "$L"; echo "exit=$?"  # → exit=0 (sin hook, deja pasar)
echo '{"tool_name":"Bash","tool_input":{"command":"gh pr merge 940 --repo Mkdir-arg/Chaco-Back"},"cwd":"."}' | CLAUDE_PROJECT_DIR="$PWD" python -c "$L"; echo "exit=$?"  # → exit=2 si el #940 (ya mergeado, sin marcador) apunta a development
```

- [ ] **Step 3: Commit**

```bash
git add .claude/settings.json
git commit -m "feat(auditoria): registrar guardia_merge como PreToolUse de Bash y PowerShell"
```

---

### Task 3: Agente `chaco-auditor`, rúbricas y plantillas

**Files:**
- Create: `.claude/agents/chaco-auditor.md`
- Create: `.claude/skills/auditoria/rubricas/correccion-seguridad.md`
- Create: `.claude/skills/auditoria/rubricas/codigo-limpio.md`
- Create: `.claude/skills/auditoria/rubricas/rendimiento.md`
- Create: `.claude/skills/auditoria/plantillas/ficha.md`
- Create: `.claude/skills/auditoria/plantillas/comentario-pr.md`

**Interfaces:**
- Produces: rutas de rúbrica que el modo B y el modo A pasan en el prompt del agente; plantillas que la skill
  copia. El agente se lanza con `subagent_type: "chaco-auditor"`.

- [ ] **Step 1: `chaco-auditor.md`** — frontmatter `name: chaco-auditor`, `description` (auditor de solo lectura de
  Chaco; recibe rúbrica(s) y alcance —diff de un PR o un eje de la auditoría completa—; devuelve hallazgos con
  evidencia), `tools: Read, Grep, Glob, Bash`, `model: opus`. Cuerpo:
  - Lee **primero y entero** cada archivo de rúbrica que nombra el prompt (con Read; no son skills invocables).
  - Alcance: modo `pr` = solo código agregado o modificado en el diff, rastreando efectos en consumidores; modo
    `completa` = el eje y módulo indicados sobre el worktree del SHA auditado.
  - Nunca edita archivos del repo. Puede correr comandos de lectura, `git`, `manage.py check` y tests focalizados en
    el worktree que le indiquen, solo ante duda concreta. No repite lo que corre el CI (ver `.claude/skills/gates-ci/SKILL.md`).
  - Regla «sin cambiar lógica ni estética» (texto del Global Constraint).
  - No reportar sin investigar hasta el final (de Thermos «Critical Rules»): si puede verificar en el repo, verifica.
  - Calibrar severidad con honestidad (Thermos «Over-reporting»).
  - Salida: lista ordenada por severidad; cada ítem con `archivo:línea`, escenario concreto (datos/estado →
    resultado incorrecto), evidencia, solución, y en modo `completa` además los campos de `plantillas/ficha.md`.
    Si no hay hallazgos, decirlo explícito. No lanzar subagentes.

- [ ] **Step 2: `rubricas/correccion-seguridad.md`** — encabezado con origen (`thermo-nuclear-review`, MIT,
  `github.com/cursor/plugins` @ `8b3326d`). Secciones:
  1. *Prompt base* traducido de Thermos («audit extremely thoroughly for bugs, changes that break existing
     features, and security vulnerabilities»).
  2. *Romper funcionalidad*: rastrear efectos cruzados entre apps (`programas` ↔ `legajos` ↔ `core`), consumidores
     de services/selectors, la app móvil (API en `programas/api/`; tocar `serializers.py` o `definicion_formulario`
     exige test de contrato en el mismo diff).
  3. *Romper la experiencia de desarrollo* (Thermos devex): variables de entorno, secretos, puertos, scripts
     obligatorios, `requirements.txt`.
  4. *Fugas de alcance* (adaptación de «feature leak»): autorización por capacidad de `core/rbac.py`
     (`@requiere`, `puede`, `puede_alguna`, alcance por programa, `CAPS_ADMIN_*`), nunca por nombre de grupo;
     `PortalCiudadanoMiddleware` (solo `/static/` exento; `/media/` no); inscripción pública por token. Para el
     checklist completo leer `.claude/skills/seguridad-django/SKILL.md`.
  5. *Datos y migraciones*: copiar la lista de «lo que no ve ningún gate» de `.claude/agents/chaco-dev-reviewer.md`
     §Método 6 (RemoveIndex en uso, tabla grande `programas_formulario`, migración de datos por lotes,
     `atomic = False` idempotente con `core/migraciones.py`, `RunPython` ya aplicado) + expand/contract.
  6. *Trampas de producción (ECOM, MariaDB)*: remitir a `.claude/skills/mysql-mariadb/SKILL.md` §Trampas conocidas;
     nombrar las que más cobraron: UUID con guiones, `Trunc*`/`CONVERT_TZ`, `UniqueConstraint(condition=)`
     inexistente, `read_timeout` 10 s, llamadas externas dentro de `transaction.atomic()`.
  7. *Rotura intencional* y *sobre-reporte* (Thermos, traducidos).
  8. *Discusión del PR*: después de la auditoría propia, si hay hallazgos MAJOR+, leer comentarios del PR con
     `gh pr view N --repo Mkdir-arg/Chaco-Back --comments`; validar y atribuir lo que aporten.
  9. *Reglas críticas* (Thermos): no reportar con investigación a medias; frescura antes de leer el PR.

- [ ] **Step 3: `rubricas/codigo-limpio.md`** — origen `thermo-nuclear-code-quality-review` (MIT). Traducir y
  conservar: «code judo», las 7 reglas no negociables, preguntas primarias, qué escalar, remedios, tono. Cambios
  de calibración (sección «Calibración para Chaco», al principio):
  - Modo `pr`: **bloquea** (`[MAJOR]`, o `[BLOCKER]` si además rompe una regla de `CLAUDE.md`) solo lo que el PR
    empeora: archivo que cruza 1000 líneas, condiciones especiales en un flujo ajeno, helper duplicado existiendo el
    canónico, lógica en la capa equivocada. Reestructurar código preexistente = `[MINOR]` o «propuesta para la
    auditoría completa».
  - Modo `completa`: la ambición de Thermos aplica entera, pero cada propuesta lleva esfuerzo y no cambia
    comportamiento.
  - Capas de Chaco: `models/` datos · `selectors/` lectura sin negocio · `services/` negocio y escritura ·
    `views/` orquestación HTTP · `forms/` validación · `templates/` presentación. `programas` partido por producto.
  - Helpers canónicos a reusar (lista): `core/rbac.py` (`puede`, `requiere`), `core/migraciones.py`,
    `q_uuid_en_texto` (`programas/services/becas.py`), `window.toast()` (`nodo-toast.js`), SweetAlert2 para
    confirmaciones, `core.models.TimeStamped`.
  - Tipos: mypy solo sobre `[tool.mypy] files`; no exigir anotaciones fuera de ese alcance.
  - Front: solo calidad del JS/templates como código; nada visual (lo gobierna `chaco-design-system`).

- [ ] **Step 4: `rubricas/rendimiento.md`** — fuentes: `chaco-dev-reviewer.md` §Método 5 (copiar la lista de
  búsquedas activas: `list(` sobre querysets, `.count()` en loops, relaciones sin `select_related`/`prefetch_related`,
  `__date`/`icontains`/funciones sobre columnas calientes, `|length` sobre querysets, listados sin paginar, datos
  calculados en templates, tabs precargados) + trampas del ORM medidas en el banco:
  - `Exists(fk=OuterRef("pk"))` sobre FK casi toda NULL → scan por fila; resolver por lote con `IN` de ids.
  - `.only("pk")`/`.defer()` sobre un manager relacionado → N+1 (una consulta por fila para emparejar al padre).
  - `TruncDate` también sobre `DateField` emite `CONVERT_TZ` → NULL en ECOM; agrupar por la columna.
  - Paginar con `select_related` en la consulta paginada → MySQL arranca por la tabla chica y materializa todo:
    elegir la página con `only("pk")` y rehidratar por `pk__in`.
  - Función sobre columna en el `WHERE` anula el índice; con `select_for_update` arma cola y 500 (Cambio 91).
  - `read_timeout` 10 s: una consulta lenta es un 500. IN anidados y decodificar JSON en Python sobre miles de filas.
  - Cómo medir: `scripts/perf_audit.py` (SQLite, offline), presupuestos `scripts/perf_budgets.json` +
    `check_perf_budgets.py` (los mide el CI), `--tag performance`, `zeal` en la suite, banco MySQL
    `scripts/perf_mysql/README.md` para `EXPLAIN ANALYZE`. No pedir micro-optimizaciones sin medición.

- [ ] **Step 5: `plantillas/ficha.md`** — el bloque de la spec §«Formato de ficha», más: ID por eje
  (`SEG`, `ERR`, `PERF`, `LIM`, `DAT`, `FE`, `TST` + número), «Origen» si absorbe hallazgos de la auditoría previa,
  y debajo de «Regla para no repetirlo» la preferencia: control mecánico si se puede detectar con una herramienta;
  prosa solo para lo que ninguna herramienta ve, en la skill/agente del tema; `CLAUDE.md` solo si aplica a toda sesión.

- [ ] **Step 6: `plantillas/comentario-pr.md`**:

```markdown
## Auditoría · PR #<N> · `<sha corto>`

**Veredicto:** APPROVE | CHANGES NEEDED
**Alcance:** <n> archivos · rúbricas: corrección-seguridad, código limpio, rendimiento

### Hallazgos
- [BLOCKER|MAJOR|MINOR] `archivo:línea` — problema → escenario → solución (preserva lógica y estética).
(o «Sin hallazgos.»)

### MINOR para el próximo PR del carril
- …

### Regla propuesta (si un hallazgo repite un patrón)
- Tipo · destino · texto o chequeo.

Aprobado @ <sha completo>        ← solo si APPROVE

<!-- auditoria-chaco veredicto=<APPROVE|CHANGES_NEEDED> sha=<sha completo> -->
```

Variante re-sello: título `## Re-sello de auditoría · PR #<N> · <sha corto>`, una línea «El diff propio del PR es
idéntico al auditado en `<sha viejo>` (patch-id <id>); cambió solo la base.» (o «… salvo
`docs/internal/requerimientos.md`»), `Aprobado @ <sha>` y el marcador con `veredicto=APPROVE`.

- [ ] **Step 7: Verificar** — `C:/Users/mkdir/Proyectos/Chaco/.venv/Scripts/python.exe scripts/check_design_agent.py --changed` → OK
  (agentes nuevos no tocan el canónico de diseño). Cada ruta, función o script nombrado en los seis archivos existe:
  `git grep -n` o `ls` por cada uno.

- [ ] **Step 8: Commit**

```bash
git add .claude/agents/chaco-auditor.md .claude/skills/auditoria/rubricas .claude/skills/auditoria/plantillas
git commit -m "feat(auditoria): agente chaco-auditor, rúbricas adaptadas de Thermos y plantillas"
```

---

### Task 4: `SKILL.md`, `modo-pr.md`, `modo-completa.md`

**Files:**
- Create: `.claude/skills/auditoria/SKILL.md`
- Create: `.claude/skills/auditoria/modo-pr.md`
- Create: `.claude/skills/auditoria/modo-completa.md`

**Interfaces:**
- Consumes: agente `chaco-auditor`, rúbricas y plantillas (Task 3); marcador del hook (Task 1).

- [ ] **Step 1: `SKILL.md`** — frontmatter: `name: auditoria`; `description`: «Auditoría de código de Chaco en dos
  modos: `pr <N>` revisa el diff de un PR antes de mergearlo a development (reemplaza al revisor independiente y deja
  el «Aprobado @ SHA» que exige el hook guardia_merge) y `completa [módulo]` audita development entera y entrega un
  informe con solución y regla para no repetir cada error. Usala antes de cualquier merge a development, cuando
  pidan auditar, revisar si el código es limpio y óptimo, o buscar errores, rendimiento y mejoras sin cambiar lógica
  ni estética.» Cuerpo (≤ 90 líneas): qué modo según argumentos (sin argumentos → preguntar en texto, nunca
  AskUserQuestion); principios (sin cambiar lógica ni estética; nunca edita código; no repite el CI; severidad
  honesta); tabla de piezas (rúbricas, plantillas, agente, hook); costo de referencia; origen Thermos + MIT.

- [ ] **Step 2: `modo-pr.md`** — pasos 1-7 de la spec §«Modo B» con comandos exactos:

```bash
gh pr view <N> --repo Mkdir-arg/Chaco-Back --json number,baseRefName,headRefOid,headRefName,files,comments
git fetch origin development "pull/<N>/head:refs/remotes/origin/pr/<N>"
HEAD_SHA=<headRefOid>; MB=$(git merge-base origin/development "$HEAD_SHA")
git diff --stat "$MB" "$HEAD_SHA"; git diff "$MB" "$HEAD_SHA" > <scratchpad>/pr-<N>.diff
```

  Paso 0 (antes de lanzar agentes) = **re-sello**: si `comments` tiene un marcador `APPROVE` para un SHA `OLD`
  distinto del head:

```bash
MB_OLD=$(git merge-base origin/development "$OLD")
P_OLD=$(git diff "$MB_OLD" "$OLD" -- . ':(exclude)docs/internal/requerimientos.md' | git patch-id --stable | cut -d' ' -f1)
P_NEW=$(git diff "$MB" "$HEAD_SHA" -- . ':(exclude)docs/internal/requerimientos.md' | git patch-id --stable | cut -d' ' -f1)
```

  Iguales → publicar variante re-sello (con «salvo requerimientos.md» si ese archivo difiere) y terminar. Distintos
  → auditoría completa del modo B. Si `OLD` no está en el clon local: `git fetch origin "$OLD"`.
  Lanzamiento: dos `Agent(subagent_type="chaco-auditor")` en el **mismo mensaje**, prompts con: modo `pr`, ruta del
  diff, lista de archivos, rúbricas (1: `correccion-seguridad.md`; 2: `codigo-limpio.md` + `rendimiento.md`) y la
  línea «no repetir lo que corre el CI: leer `.claude/skills/gates-ci/SKILL.md`». Consolidación: deduplicar, pesar
  lo que encontraron los dos, el juez decide desacuerdos, severidad final. Veredicto y ciclo acelerado (APPROVE con
  solo MINOR → se mergea; MINOR al próximo PR del carril; excepción: MINOR que sea riesgo latente de datos/
  seguridad/arranque en PRD abre ronda). Publicar: escribir el comentario en `<scratchpad>/auditoria-pr-<N>.md` con
  `plantillas/comentario-pr.md` y `gh pr comment <N> --repo Mkdir-arg/Chaco-Back --body-file <archivo>`. Merge (si
  corresponde): `gh pr merge <N> --repo Mkdir-arg/Chaco-Back --merge --match-head-commit <HEAD_SHA>` — el hook lo
  verifica. Si el hook frena: leer el motivo; no hay bypass.

- [ ] **Step 3: `modo-completa.md`** — pasos 1-6 de la spec §«Modo A» con comandos:

```bash
git fetch origin development
SHA=$(git rev-parse origin/development)
git worktree add --detach <scratchpad>/auditoria-$SHA "$SHA"
# línea de base (desde la raíz del worktree; Python por los venv de la raíz del repo)
<py> -m ruff check . --statistics
git ls-files '*.py' '*.html' '*.js' | xargs wc -l | awk '$1>1000' | sort -rn
<py> scripts/perf_audit.py --output <scratchpad>/perf.json
<py> scripts/check_migraciones.py --todas
<py> scripts/design_audit.py --ratchet
```

  Ejes y prefijos de ID (tabla): seguridad y RBAC `SEG` · errores y corrección `ERR` · rendimiento y base `PERF` ·
  código limpio y arquitectura `LIM` · datos, migraciones y operación `DAT` · front (calidad, sin estética) `FE` ·
  tests y red de seguridad `TST`; qué rúbrica(s) lee cada uno. Pasada 1: hasta 7 `chaco-auditor` en un mensaje.
  Pasada 2: por cada CRÍTICA/ALTA sin prueba, un `Agent(model="sonnet")` escribe la PoC en
  `<worktree>/docs/internal/auditoria-AAAA-MM/poc/` y la corre → CONFIRMADO con test / REFUTADO. Cruce con la
  auditoría previa: leer `docs/internal/auditoria-2026-10/README.md` §0.4 y §8 (por offset, es grande) y no
  reintroducir lo refutado. Entregable: estructura de carpeta + README con secciones fijas (Resumen, Índice,
  Plan por olas con horas, **Reglas propuestas** —tabla tipo/destino/texto/fichas que la originan—, Descartados,
  SHA auditado). `.gitattributes`: agregar `docs/internal/auditoria-AAAA-MM/**/*.md text eol=lf` (lección del
  README duplicado del 07-oct). Entrega por PR de docs que pasa por el modo B. Nada se implementa sin aprobación.

- [ ] **Step 4: Verificar** — cada comando de los dos `modo-*.md` corre en seco en el worktree (los de `git` y
  los scripts con `--help`); `scripts/check_design_agent.py --changed` OK.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/auditoria/SKILL.md .claude/skills/auditoria/modo-pr.md .claude/skills/auditoria/modo-completa.md
git commit -m "feat(auditoria): skill /auditoria con modo pr (antes de mergear) y modo completa (informe)"
```

---

### Task 5: `CLAUDE.md`, requerimientos y PR

**Files:**
- Modify: `CLAUDE.md:335-342` (§Gates de CI)
- Modify: `docs/internal/requerimientos.md` (entrada nueva + fila del índice)

- [ ] **Step 1: `CLAUDE.md`** — después del párrafo que termina en «…en el mismo diff.», agregar:

```markdown
Antes de mergear un PR a `development` se corre `/auditoria pr <N>`: es la revisión independiente y deja el
«Aprobado @ SHA» que exige el hook `guardia_merge` (`.claude/hooks/`) para dejar pasar `gh pr merge`.
```

- [ ] **Step 2: Tests que leen `CLAUDE.md`**

Run: `PYTEST_RUNNING=1 DJANGO_SYNCDB_PROJECT_APPS=True DJANGO_SECRET_KEY=test-key C:/Users/mkdir/Proyectos/Chaco/.venv312/Scripts/python.exe manage.py test core.tests.test_gates_ci core.tests.test_motor_real core.tests.test_roundtrip_migraciones core.tests.test_un_solo_migrador core.tests.test_guardia_merge`
Expected: OK (los que necesitan motor real se saltean).

- [ ] **Step 3: Entrada de requerimientos** — consultar primero `scripts/requerimientos.py --tag metodo`; tomar el
  siguiente número libre de Cambio **en `origin/development` al momento de escribir** (`git fetch` antes); seguir la
  plantilla obligatoria del propio archivo (no copiar de memoria). Etiquetas `#metodo`. Contenido: pedido original
  (las frases del PM de esta sesión), alcance, decisiones (las 6 de la spec), archivos, validación, reversión
  (spec §Reversión). Fila nueva en el índice.

Run: `PYTHONIOENCODING=utf-8 C:/Users/mkdir/Proyectos/Chaco/.venv/Scripts/python.exe scripts/requerimientos.py --check` → OK.

- [ ] **Step 4: Commit, push y PR**

```bash
git add CLAUDE.md docs/internal/requerimientos.md docs/superpowers/plans/2026-10-23-skill-auditoria.md
git commit -m "docs: /auditoria en Gates de CI y Cambio <N> en requerimientos"
git push -u origin feature/skill-auditoria
gh pr create --repo Mkdir-arg/Chaco-Back --base development --title "Skill /auditoria: auditoría completa y control antes de mergear" --body-file <scratchpad>/pr-body.md
```

---

### Task 6: Prueba de punta a punta sobre el propio PR

- [ ] **Step 1: El hook frena sin auditoría** (sin mergear nada):

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"gh pr merge <N> --repo Mkdir-arg/Chaco-Back --merge"},"cwd":"."}' | python .claude/hooks/guardia_merge.py; echo "exit=$?"
```
Expected: `guardia_merge: Falta /auditoria pr <N> sobre <sha8> (sin auditoría)…` y `exit=2`.

- [ ] **Step 2: Correr `/auditoria pr <N>`** siguiendo `modo-pr.md` al pie de la letra. Anotar lo que el
  procedimiento no previó y corregirlo en el mismo PR (un commit), lo que obliga a re-auditar o re-sellar.

- [ ] **Step 3: El hook deja pasar con el APPROVE** — repetir el comando del Step 1 → `exit=0`. Probar el re-sello:
  `gh pr update-branch <N> --repo Mkdir-arg/Chaco-Back` (si está atrás) → Step 1 da `exit=2` → re-sello → `exit=0`.

- [ ] **Step 4: Memoria** — actualizar `feedback-metodologia-orquestacion-juez.md` y `feedback-ciclo-pr-acelerado.md`:
  el revisor independiente es `/auditoria pr` (desde 23-oct-2026) y el hook exige su marcador.

- [ ] **Step 5: Merge** — lo decide el usuario (o el juez con su autorización, CI verde, `--match-head-commit`).
