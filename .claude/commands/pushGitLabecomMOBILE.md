---
description: El espejo de la app móvil/PWA a ECOM se partió en dos (como el del back). Este comando explica cuál corresponde y no pushea nada.
allowed-tools: Bash(git rev-parse:*), Bash(git ls-remote:*), Bash(git fetch:*), Bash(git log:*)
---

**Este comando ya no espeja nada.** Empujaba `main` de la app a ECOM con la URL vieja del
repo. Desde el 22/10/2026 la app es una PWA y el flujo es PR → rama `test` de GitHub →
`ecom/test` (testing, `https://datanach-app.ecomdev.ar`); `main` de ECOM se trata como
**producción**. Por eso se partió en dos pasos, con una verificación humana en el medio,
igual que el del back (RED-23).

Explicale al usuario cuál le corresponde y terminá:

- **`/pushGitLabecomMOBILETEST`** — lleva `origin/test` de Chaco-mobile a `ecom/test`
  (repo `datanach-app`): construye la PWA de **testing**. No toca producción. Es el que
  casi siempre se quiere.
- **`/pushGitLabecomMOBILEPRD`** — lleva `origin/main` a `ecom/main`, que se trata como
  **producción**. Se corre **después** de que alguien probó testing, en otra sesión, y
  exige que el árbol sea idéntico al de `ecom/test` y una confirmación escribiendo
  `PRODUCCION`.

El procedimiento general está en `docs/internal/espejo-ecom.md`; el mecanismo de ramas, en
`docs/internal/branching.md`. El back se espeja con `/pushGitLabecomTEST` y
`/pushGitLabecomPRD`.

Si querés, mostrale el estado actual sin tocar nada: `git -C ../Chaco-mobile fetch origin`,
`git -C ../Chaco-mobile rev-parse origin/test origin/main` y
`git -C ../Chaco-mobile ls-remote --heads ecom`.
