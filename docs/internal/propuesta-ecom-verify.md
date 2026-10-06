# Propuesta a ECOM: etapa `verify` y tag inmutable en el pipeline de DATAÑACH

**Estado:** redactada el 05/10/2026 (PR R-14, Cambio 128), ampliada el 06/10/2026 con los
puntos 4 y 5 (PR R-15, Cambio 153). **Falta enviarla**: la lleva el PM. Responde a la
pregunta abierta **H-12** de la auditoría de octubre 2026 y a las fichas **RED-22**,
**RED-16**, **OPS-03** y **OPS-04**.

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

**Nuestra mitad ya está hecha** (Cambio 153): desde el 06/10/2026, `publish-main.yml`
etiqueta cada release con `release-AAAA.MM.DD-<short>` sobre el commit de `main`, así que
«la release anterior» tiene nombre y SHA. Lo que falta es que la imagen de ellos también
los tenga: sin eso, el SHA sirve para reconstruir, no para volver en segundos.

### 3. Dump de la base antes de cada deploy de `main` (H-11)

Independiente de lo anterior y más urgente: hoy no hay respaldo tomado por el pipeline
antes de un deploy que puede traer migraciones. El runbook de rollback (Anexo D de
`processes.md`) lo supone.

### 4. Aviso: desde la próxima release, los tracebacks salen por stdout (OPS-03)

No requiere que ellos hagan nada; es un cambio nuestro que **cambia el volumen de los
logs de los pods** y conviene que lo sepan antes y no por una alerta de su stack.

Hasta ahora, el traceback de cada error 500 iba **solo** a `logs/<fecha>/error.log`
dentro del contenedor, que en Kubernetes es efímero: `kubectl logs` mostraba únicamente
la línea `core.requests … status=500`, sin la excepción. Diagnosticar cualquier incidente
en testing o en producción era imposible sin entrar al pod antes de que se reciclara.

Desde el Cambio 153, `django.request` propaga a la salida estándar. Concretamente:

- se agrega **una traza por cada 500 y por cada 4xx registrado**, no un log por request
  (el `core.requests … status=…` por request ya existía y no cambia);
- en un sistema sano eso es un puñado de líneas por día; durante un incidente, tantas
  como errores haya;
- los archivos en disco quedan **apagados por defecto** (`LOG_TO_FILES`), así que en sus
  pods no se escribe nada en el filesystem: antes sí, y nadie lo leía.

Si su stack de logs cobra por volumen o tiene un límite por pod, es el momento de
decirlo.

### 5. Aviso: `/health/ready/` existe; `/health/` no cambia (OPS-04)

Las sondas actuales apuntan a `/health/`, que sigue respondiendo exactamente igual: 200
sin tocar la base. **No hay que cambiar ningún manifiesto.**

Lo nuevo es `/health/ready/`, que sí consulta la base y el cache de sesiones y devuelve
**503** con un JSON `{"db": …, "cache": …}` cuando algo no responde. Sirve para
monitoreo externo y para verificar un deploy.

**No conviene usarla como `livenessProbe`**: con una sola base para todos los pods, una
base lenta los reiniciaría a todos a la vez. Como `readinessProbe` es decisión de ellos;
nuestra recomendación (D-O04) es dejarla solo para monitoreo.

## Si ECOM no lo acepta

El equivalente de nuestro lado ya está: `.github/workflows/release-gate.yml` (RED-23)
verifica el commit de `main` **antes** de que exista el espejo —CI verde del PR de
origen, suite completa, migraciones sobre MariaDB, imagen construida con su manifest y
smoke HTTP—, y `/pushGitLabecomPRD` exige verlo en verde. Es más tarde y es voluntario:
cubre el release, no un push que ECOM haga por su cuenta a `test` o `main`.
