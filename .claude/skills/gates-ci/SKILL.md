---
name: gates-ci
description: Qué corre el CI de Chaco en cada PR y en el release, qué bloquea el merge, qué no lo bloquea pero igual frena Publish main y el release gate, y cómo leer un rojo. Usala antes de abrir o mergear un PR, cuando un check sale rojo, al tocar contratos de API o el alcance de mypy, o antes de espejar a ECOM.
paths:
  - ".github/workflows/*.yml"
  - "security/excepciones.toml"
  - "requirements*.txt"
  - "scripts/check_*.py"
---

# Gates de CI

Movido desde `CLAUDE.md` (sección *Gates de CI*) para que cargue solo cuando hace falta. Las reglas que no pueden faltar nunca siguen en `CLAUDE.md`.

Los PRs van contra `development`. Estos checks **tienen que estar en verde** —y salen
rojos si no lo están—, pero hoy el merge no los exige todavía: el repo no tiene
protección de rama. Los dos rulesets que la encienden están versionados en
[`docs/internal/rulesets/`](docs/internal/rulesets.md) y **los aplica el dueño del
repo**; hasta entonces, no mergear en rojo es una regla del proceso, no un mecanismo.

- **Backend CI** — `manage.py check --deploy` (`Django System Check`),
  `makemigrations --check --dry-run` + `scripts/check_migraciones.py` sobre las
  migraciones nuevas del PR (`Migration Check`), `coverage run manage.py test --parallel 4`
  + `coverage combine` (`Tests & Coverage`, `fail_under = 79` con `branch = true` en
  `pyproject.toml`; `concurrency = ["multiprocessing"]` es lo que hace que la cobertura
  siga midiendo con la suite repartida en procesos) y `Contratos de API`:
  `manage.py spectacular --validate` más los módulos que congelan un contrato (esquema,
  app de campo, endpoints JSON del backoffice, servicios externos, forma de los JSON
  guardados, catálogo de capacidades). **Tocar `programas/api/serializers.py`,
  `definicion_formulario` o una clave que el front lee a mano obliga a actualizar el test
  de contrato en el mismo diff.**
- **Performance Guard** — tests `--tag performance` (presupuestos de queries en
  `scripts/perf_budgets.json`), comparación de duración y contrato MySQL/Redis efímero.
  Ahí viven también los dos jobs que corren contra el motor de verdad, **todavía no
  obligatorios**: `Motor real (<motor>)` (los tests `@tag("mysql")` contra
  `mariadb:10.11`, `mariadb:11` y `mysql:8.0`) y `Migrate ida y vuelta (<motor>)` (las
  migraciones del PR aplicadas, desaplicadas y vueltas a aplicar sobre datos sembrados,
  contra `mariadb:10.11` sin tablas de zona horaria y `mysql:8.0`). Los dos entran al
  ruleset cuando acumulen corridas.
- **Security** — `pip-audit` (`Pip Audit`), con las excepciones de
  `security/excepciones.toml`, que vencen.
- **Datos** — `Sin datos personales`: ningún volcado de personas entra al repo.
- **Code Quality** — `Ruff errores` (`ruff check . --select F`), `Ruff estilo` (E, W, I y `ruff format --check`, con
  la versión de `requirements-ci.txt`) y `Contratos del repo`: las condiciones de cierre de
  este archivo, corridas en el CI (sintaxis de todos los templates, `requerimientos.py --check`, `collectstatic` con el
  almacenamiento con manifest y el ratchet de `design_audit` contra `.design-audit-ratchet`).
- **Design Agent Contract** — `Validate inventory and authority`: contrato y límites del
  agente (`check_design_agent.py --limites`), `design_audit.py --ratchet` (0 hallazgos
  nuevos), `--goldens` (las pantallas de referencia en 0) y build de Tailwind sin diff.

Los dos últimos corren en **todos** los PRs: el filtro por rutas está adentro del job,
así que cuando el PR no toca Python o UI el check termina en verde sin hacer nada. Un
check con `paths:` en el trigger no puede ser obligatorio, porque no reporta nunca.

No bloquean el merge (`continue-on-error`): `Tipos (mypy)`, `Orden y paralelo`, Bandit y
dependency-review. **Pero un rojo que el merge deja pasar SÍ frena `Publish main`** (y el
`Release gate`): Bandit y dependency-review son `continue-on-error` a nivel job, su check
queda rojo y `main` no se publica —lo mismo con `Motor real` y `Migrate ida y vuelta`—;
mypy y `Orden y paralelo` lo llevan en el paso y su check queda verde. Así que se dejan en verde.

`Tipos (mypy)` (RED-76) corre **solo sobre el alcance declarado** en `files` de
`[tool.mypy]` (`pyproject.toml`); fuera de esa lista mypy no mira nada. El alcance crece
**un módulo por PR** y lo que entra, entra en verde: agregar una línea ahí obliga a anotar
ese módulo en el mismo diff, y lo estricto (`disallow_untyped_defs`) se declara para el
mismo conjunto. En local: `& $env:PY_VENV -m mypy` (se instala con
`pip install -r requirements-ci.txt`).

`Backend CI`, `Performance Guard` y `Datos` corren además en `push` a `development`,
para que un push directo deje un check rojo visible mientras no haya ruleset.

`Release gate` (`release-gate.yml`) no corre en los PRs: se dispara a mano con el SHA de
`main` que se va a espejar y verifica **ese release** —CI verde del PR que lo originó,
suite completa, migraciones sobre MariaDB, la imagen construida con su manifest de
estáticos y un smoke HTTP—. Es lo que `/pushGitLabecomTEST` corre antes de espejar y lo
que `/pushGitLabecomPRD` exige en verde. Y `publish-main.yml` no publica un release de un
commit que no venga de un PR con el CI en verde.

## «Pip Audit» rojo por una CVE nueva

Una advisory publicada hoy pone rojo `Pip Audit` en **todos** los PR abiertos, también en los
que no tocaron una dependencia: el problema no es del PR, y se resuelve en un PR propio que
saca los demás del rojo. Las reglas de las excepciones (cuatro claves, `vence_el` como fecha
TOML, retiro) están en la cabecera de [`security/excepciones.toml`](../../../security/excepciones.toml);
acá va el orden en que se decide.

1. **Leer la falla.** `gh run view <id> --log-failed --repo Mkdir-arg/Chaco-Back` filtrado por
   `CVE-`, `GHSA-` o `PYSEC-`, nunca el log entero.
2. **Identificar la advisory.** `gh api "/advisories?cve_id=<CVE>"`: da el GHSA, el módulo
   afectado y la versión corregida (o su ausencia).
3. **Comprobar si el módulo se carga.** Con `.venv312`, importar `daphne.server`,
   `daphne.http_protocol`, `daphne.ws_protocol` y `channels.layers` y listar `sys.modules`
   por el prefijo del paquete afectado. Mirar `sys.modules` tras importar solo mide lo que
   se carga al arrancar: revisar también el camino que activaría el módulo en ejecución (en
   el caso de DNS, `reactor.nameResolver`). Buscar también si el repo lo importa. Es la
   evidencia que va al motivo de la excepción. Si la excepción depende de que algo no se
   cargue, esa condición queda cubierta por un test en un proceso aislado, como
   `core/tests/test_twisted_dns.py`.
4. **Decidir.**
   - Hay versión **final** corregida: se sube el pin (si el paquete no está pineado, la
     toma sola la imagen).
   - No hay versión final corregida (solo un rc, o ninguna) y el módulo **no** se carga: excepción en
     `security/excepciones.toml` con `vence_el` y ticket.
   - El módulo **sí** se carga en la superficie servida (p. ej. `twisted.web` con daphne):
     decide el PM, y solo con una mitigación verificable, como la de nginx en
     CVE-2026-115877.
   - No existe la excepción sin vencimiento, y nunca se pinea un release candidate en la imagen.
5. **Validar.** `scripts/check_excepciones_seguridad.py` y después `pip-audit -r <archivo>`
   con las banderas de `--ignore-args`, para los tres `requirements*.txt`, tal como lo hace
   `pr-security.yml`.
6. **Retirar.** Cuando sale la versión final: `pip-audit` sin ningún `--ignore-vuln` y se
   borra toda entrada cuyo id ya no aparece, no solo las del mismo ticket.
