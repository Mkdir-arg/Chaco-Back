# Propuesta a ECOM: etapa `verify` y tag inmutable en el pipeline de DATAÑACH

**Estado:** redactada el 05/10/2026 (PR R-14, Cambio 128). **Falta enviarla**: la lleva
el PM. Responde a la pregunta abierta **H-12** de la auditoría de octubre 2026 y a las
fichas **RED-22** y **RED-16**.

Este documento es **una propuesta**, no un cambio. `.gitlab-ci.yml` lo mantiene ECOM;
nuestra copia en el repo existe solo para que viaje en el release —sin ese archivo
GitLab no crea pipeline y la rama se actualiza sin construir imagen— y **tiene que
quedar byte a byte igual a la suya**. Por eso nada de lo de acá está aplicado en el
repositorio: si lo editáramos de nuestro lado, el próximo espejo les revertiría el
archivo.

## Qué pasa hoy

El pipeline tiene **una sola etapa**: `build`. Construye la imagen del `Dockerfile` de
la raíz y la publica como `…/datanach/<rama>:latest`. ArgoCD despliega esas imágenes:
`test` → testing, `main` → **producción, automáticamente, sin pase ni aprobación**, en 5
a 7 minutos.

Dos consecuencias medidas:

1. **Cero verificación antes de producción.** Cualquier regresión que no sea un error de
   sintaxis llega al organismo: un `TruncWeek` sobre un `DateTimeField` compila,
   construye, levanta y devuelve `NULL` **solo en MariaDB** (le pasó a este sistema:
   Cambio 125). El `docker build` no ejecuta una línea del código.
2. **No hay artefacto al que volver.** Como solo existe `:latest`, un rollback no tiene
   a qué apuntar: hay que reconstruir desde un commit anterior y esperar otro ciclo
   completo, con producción caída mientras tanto.

## Lo que se pide

### 1. Una etapa `verify` antes de `build`, con la misma regla de ramas

```yaml
stages:
  - verify
  - build

verify:
  stage: verify
  image: python:3.12-slim
  variables:
    DJANGO_SECRET_KEY: "ci-no-es-un-secreto-real"
    PYTEST_RUNNING: "1"
    DJANGO_SYNCDB_PROJECT_APPS: "True"
    DJANGO_DEBUG: "False"
    DJANGO_ALLOWED_HOSTS: "localhost"
    SIIS_API_URL: "https://siis.invalido.local"
  before_script:
    - apt-get update && apt-get install -y --no-install-recommends gcc default-libmysqlclient-dev pkg-config
    - pip install --no-cache-dir -r requirements.txt
  script:
    - python manage.py check --deploy
    - python manage.py makemigrations --check --dry-run
    - python manage.py test --verbosity=1
  rules:
    - if: '$CI_COMMIT_REF_NAME == "test" || $CI_COMMIT_REF_NAME == "main"'
      when: always
```

Notas para su equipo:

- **No necesita base de datos.** Con `PYTEST_RUNNING=1` la suite usa SQLite en memoria y
  `DJANGO_SYNCDB_PROJECT_APPS=True` crea las tablas desde los modelos.
- `SIIS_API_URL` tiene que estar definida aunque sea con un host ficticio: desde el
  Cambio 123 no tiene valor por defecto y `check --deploy` falla sin ella (es
  deliberado: sin esa variable, las altas se irían al SIIS de desarrollo).
- Costo estimado: 5 a 8 minutos por pipeline, una sola vez por push.
- Si la etapa falla, **no se construye la imagen** y el entorno queda en la versión
  anterior, que es exactamente el comportamiento que hoy no existe.

### 2. Un tag inmutable por commit, además de `:latest`

```yaml
    - DOCKER_BUILDKIT=1 docker build -t ${IMAGE_BASE}:latest -t ${IMAGE_BASE}:${CI_COMMIT_SHORT_SHA} .
    - docker push ${IMAGE_BASE}:latest
    - docker push ${IMAGE_BASE}:${CI_COMMIT_SHORT_SHA}
```

Con eso un rollback es apuntar ArgoCD a `…/datanach/main:${CI_COMMIT_SHORT_SHA}` de la
versión anterior: minutos en vez de un ciclo completo de build. No cambia nada del
deploy normal, que sigue mirando `:latest`.

### 3. Dump de la base antes de cada deploy de `main` (H-11)

Independiente de lo anterior y más urgente: hoy no hay respaldo tomado por el pipeline
antes de un deploy que puede traer migraciones. El runbook de rollback (Anexo D de
`processes.md`) lo supone.

## Si ECOM no lo acepta

El equivalente de nuestro lado ya está: `.github/workflows/release-gate.yml` (RED-23)
verifica el commit de `main` **antes** de que exista el espejo —CI verde del PR de
origen, suite completa, migraciones sobre MariaDB, imagen construida con su manifest y
smoke HTTP—, y `/pushGitLabecomPRD` exige verlo en verde. Es más tarde y es voluntario:
cubre el release, no un push que ECOM haga por su cuenta a `test` o `main`.
