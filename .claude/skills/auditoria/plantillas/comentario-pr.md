# Plantilla: comentario de la auditoría en el PR (modo `pr`)

Se escribe en un archivo del scratchpad y se publica con
`gh pr comment <N> --repo Mkdir-arg/Chaco-Back --body-file <archivo>`. La última línea —el
marcador— es la que lee el hook `guardia_merge`: sin ella, o con otro SHA, el merge no pasa.

## Auditoría

```markdown
## Auditoría · PR #<N> · `<sha corto>`

**Veredicto:** APPROVE | CHANGES NEEDED
**Alcance:** <n> archivos · rúbricas: corrección y seguridad, código limpio, rendimiento

### Hallazgos
- [BLOCKER|MAJOR|MINOR] `archivo:línea` — problema → escenario → solución (preserva lógica y estética).

(o «Sin hallazgos.»)

### MINOR para el próximo PR del carril
- …

### Regla propuesta
- <tipo> · <destino> · <texto o chequeo>   ← solo si un hallazgo repite un patrón ya registrado

Aprobado @ <sha completo>

<!-- auditoria-chaco veredicto=APPROVE sha=<sha completo> -->
```

- Con CHANGES NEEDED: sin la línea «Aprobado @», y el marcador con
  `veredicto=CHANGES_NEEDED` (guion bajo: es lo que lee el hook).
- Secciones vacías se omiten, salvo «Hallazgos».
- El SHA del marcador es el `headRefOid` completo (40 caracteres, minúsculas) que se auditó.

## Re-sello

Cuando el diff propio del PR no cambió y solo se movió la base:

```markdown
## Re-sello de auditoría · PR #<N> · `<sha corto nuevo>`

El diff propio del PR es idéntico al auditado en `<sha corto viejo>` (patch-id `<id corto>`):
cambió solo la base.

Aprobado @ <sha completo nuevo>

<!-- auditoria-chaco veredicto=APPROVE sha=<sha completo nuevo> -->
```

Si lo único que cambió del diff propio es `docs/internal/requerimientos.md` (renumeración del
Cambio), la segunda línea dice: «…idéntico al auditado en `<sha corto viejo>` salvo
`docs/internal/requerimientos.md`: cambió la base y la numeración del Cambio.»
