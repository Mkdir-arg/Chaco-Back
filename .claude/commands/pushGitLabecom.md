---
description: El espejo a ECOM se partió en dos (RED-23). Este comando explica cuál corresponde y no pushea nada.
allowed-tools: Bash(git rev-parse:*), Bash(git ls-remote:*), Bash(git fetch:*), Bash(git log:*)
---

**Este comando ya no espeja nada.** Empujaba `test` y `main` en la misma corrida, con una
sola confirmación: como el build de ECOM tarda 5 a 7 minutos, cuando llegaba al paso de
`main` —que **despliega producción automáticamente**— testing ni había terminado de
construir. El espejo se partió en dos pasos, con una verificación humana en el medio
(RED-23 de la auditoría oct-2026, Cambio 128).

Explicale al usuario cuál le corresponde y terminá:

- **`/pushGitLabecomTEST`** — lleva el release a `ecom/test`, que despliega **testing**.
  Corre antes el `release-gate` del release y no toca producción. Es el que casi siempre se
  quiere.
- **`/pushGitLabecomPRD`** — lleva a `ecom/main`, que **despliega producción**. Se corre
  **después** de que alguien haya probado testing, en otra sesión, y exige el SHA
  verificado, el `release-gate` en verde y una confirmación escribiendo `PRODUCCION`.

El procedimiento normativo está en `docs/internal/espejo-ecom.md`; el mecanismo de ramas, en
`docs/internal/branching.md`. La app móvil va aparte, con `/pushGitLabecomMOBILE`.

Si querés, mostrale el estado actual sin tocar nada: `git fetch origin main:main`,
`git rev-parse main` y `git ls-remote --heads ecom`.
