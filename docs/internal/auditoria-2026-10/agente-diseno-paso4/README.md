# Agente de diseño reescrito (Ola 6, paso 4) — archivos a aplicar sobre `.claude/`

**Esta carpeta es transitoria.** Contiene el núcleo reescrito del agente canónico de diseño, sus
fichas y los agentes consumidores, listos para moverse a `.claude/`. La sesión que los escribió **no
tiene permiso de escritura sobre `.claude/`**, así que el contenido se entrega acá, completo y
revisable en el diff, en vez de pegado en el cuerpo del PR (son ~90 KB: no entran).

## Cómo se aplica (un solo comando, desde la raíz del repo)

```bash
git rm -r --quiet .claude/design 2>/dev/null || true
mkdir -p .claude/design
cp -r docs/internal/auditoria-2026-10/agente-diseno-paso4/design/. .claude/design/
cp docs/internal/auditoria-2026-10/agente-diseno-paso4/agents/*.md .claude/agents/
git rm -r --quiet docs/internal/auditoria-2026-10/agente-diseno-paso4
git add .claude
```

Después:

```powershell
$env:PYTHONIOENCODING = "utf-8"
& .\.venv312\Scripts\python.exe scripts\check_design_agent.py --limites   # OK
& .\.venv312\Scripts\python.exe scripts\design_audit.py --goldens         # 0 hallazgos en 5 goldens
& .\.venv312\Scripts\python.exe scripts\test_design_audit.py              # 14 tests, sin skips
```

**Hasta que ese movimiento esté hecho, el check «Design Agent Contract» del PR sale en rojo**, y
tiene que salir: el mismo PR enciende `check_design_agent.py --limites` en el CI (el núcleo viejo
viola 58 límites) y hace que `design_audit.py --goldens` falle si el núcleo no declara la tabla
`## Arquetipos` (el núcleo viejo no la tiene). Las dos cosas pasan a verde con el `cp` de arriba.

## Qué hay acá

| Origen | Destino |
|---|---|
| `agents/chaco-design-system.md` | `.claude/agents/chaco-design-system.md` (núcleo, 25,5 KB) |
| `agents/chaco-frontend.md` | `.claude/agents/chaco-frontend.md` |
| `agents/chaco-design-reviewer.md` | `.claude/agents/chaco-design-reviewer.md` |
| `agents/chaco-dev-reviewer.md` | `.claude/agents/chaco-dev-reviewer.md` |
| `design/**` (21 fichas) | `.claude/design/**` |

Las fichas son 5 de arquetipo + 1 de arquetipos pendientes + 12 de componente + `shells.md` + 2 de
dominio. Cada una está citada por una fila del inventario o de la tabla *Arquetipos* del núcleo
(`check_design_agent.py` falla si queda una ficha huérfana o una fila citando una ficha que no
existe).
