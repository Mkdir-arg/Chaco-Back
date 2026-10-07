# Espejo del release a ECOM, en dos pasos (RED-23)

Procedimiento normativo del espejo al GitLab de ECOM. Los comandos
`/pushGitLabecomTEST` y `/pushGitLabecomPRD` son la cara operativa de este documento;
el mecanismo de ramas, la divergencia de `test` y las fallas conocidas del push siguen
en [`branching.md`](branching.md), que no se duplica acá.

## Por qué está partido en dos

Hasta el Cambio 128, `/pushGitLabecom` empujaba `test` y `main` en **una sola corrida,
con una sola confirmación**. El build de ECOM tarda 5 a 7 minutos: cuando el comando
llegaba al paso de `main`, testing ni había terminado de construir. «`test` primero, se
verifica ahí, recién después `main`» era prosa que el procedimiento no implementaba, y
nada comprobaba que el commit espejado hubiera pasado el CI de GitHub ni que el `main`
local estuviera al día con `origin/main`.

Del otro lado no hay red: el pipeline de ECOM solo construye la imagen y **ArgoCD
despliega `main` en producción de forma automática, sin pase ni aprobación**
(RED-22; la propuesta para que eso cambie está en
[`propuesta-ecom-verify.md`](propuesta-ecom-verify.md)). Mientras ECOM no la acepte, lo
único que verifica un release antes del espejo es el `release-gate` de nuestro lado.

Los dos pasos son **dos sesiones distintas**, con una verificación humana en el medio.
No se encadenan.

## Paso 0 — Mirar el esquema del ambiente antes de espejar (OPS-01)

**Vale para los dos pasos y se hace antes de cada uno.** Un release se espeja contra una
base que ya existe y que puede no corresponderse con las migraciones que el release trae:
un restore encima, una renumeración, una reversa que se cortó. Eso no se ve desde acá y
el síntoma, cuando aparece, es el initContainer en CrashLoop con `1050 Table already
exists` y el esquema a medias —en MySQL y MariaDB el DDL no es transaccional—.

`manage.py verificar_esquema_migraciones --solo-reporte` **solo lee** (`SELECT` sobre
`django_migrations` e `information_schema`) y **termina siempre en 0**, así que se puede
correr contra un ambiente ajeno sin riesgo y sin cortar ningún script.

- **Testing de ECOM:** desde el pod `web-*`, con el código del release ya desplegado —o
  sea, después del paso 1 y antes del paso 2—:

  ```bash
  kubectl exec -it deploy/<web> -- python manage.py verificar_esquema_migraciones --solo-reporte
  ```

- **PRD de ECOM:** no tenemos acceso. Se le **pide a su equipo** que corra esa misma
  línea y mande la salida, junto con el dump previo (H-11). Es parte del paso 2.
- **icore-srv:** `docker compose -f docker-compose.prod.yml exec -T web python manage.py
  verificar_esquema_migraciones --solo-reporte`, antes del deploy.

Qué mirar en la salida:

| Lo que dice | Qué significa |
|---|---|
| `Esquema coherente: …` | Se puede seguir |
| `Migraciones registradas con otro número` | **Frena**: el `migrate` las va a volver a correr. Hay que renombrar esas filas antes (nunca `--fake`) |
| `Tablas que ya existen` | **Frena**: el `migrate` va a morir con `1050`. Viene de un restore o de una renumeración |
| `fila sin archivo que no frena el deploy` | Aviso. Son filas inertes (`silk`, `turnos`, `tramites`, migraciones borradas) que ninguna base se saca de encima |
| `Tablas que existen y que ningún modelo … nombra` | Aviso. Restos de una app retirada o de una reversa cortada; no rompe el deploy |

### Y mirar las dos variables de gevent (RED-45)

Desde el **Cambio 159**, `docker-entrypoint.sh` **aborta el arranque** si el entorno pide
workers gevent o eventlet. Es deliberado: el soporte de gevent de la imagen aplica
`config/gevent_patch.py`, que apaga `validate_thread_sharing` de Django y puede devolver
los datos de una persona en la respuesta de otra, sin error ni log (D-RED-08).

Pero si alguien en ECOM las puso alguna vez para probar contra los 504 del padrón, el
primer deploy con este release deja el pod en CrashLoop. **Se mira antes, no después:**

```bash
kubectl exec -it deploy/<web> -- sh -c 'echo "CMD_ARGS=[${GUNICORN_CMD_ARGS:-}] WORKER_CLASS=[${GUNICORN_WORKER_CLASS:-}]"'
```

| Lo que devuelve | Qué hacer |
|---|---|
| las dos vacías | Seguir. Es lo esperado: ningún manifiesto del repo las define |
| `GUNICORN_CMD_ARGS` con `gevent` o `eventlet` (en cualquier forma: `--worker-class`, `-k`, con o sin `=`) | **Frena**: sacarla del Deployment/ConfigMap antes de espejar |
| `GUNICORN_WORKER_CLASS=gevent` o `=eventlet` | **Frena**: ídem |
| cualquier otro valor (`sync`, `gthread`, `--timeout …`) | Arranca igual; el entrypoint deja un `AVISO` en el log y sigue |

Para **PRD** se le pide a ECOM esa misma línea junto con el `--solo-reporte`, en el paso 2.
En **icore-srv**: `docker compose -f docker-compose.prod.yml exec -T web env | grep GUNICORN`.

### Y confirmar que testing tiene Redis y declara `ENVIRONMENT` (OPS-12)

**Propuesta para el PM: esto hay que preguntárselo a ECOM antes de espejar este release.
No se supone nada del lado de ellos.**

Hasta el **Cambio 165**, `config/settings_production.py` reasignaba `ENVIRONMENT = "prd"`
después de que `settings.py` había derivado todo de la variable real. El efecto en testing
(`ENVIRONMENT=qa`) era que la app **decía** «prd» y corría con caché y channel layer
**locales al proceso**: el límite de intentos contaba por worker, una invalidación de
caché limpiaba uno de varios y los websockets no cruzaban entre pods. Testing no
reproducía lo que iba a pasar en producción, que es para lo que existe.

Desde este release, `qa` usa Redis igual que `prd`. Las dos preguntas para ECOM:

| Pregunta | Por qué importa |
|---|---|
| ¿El ambiente de testing tiene un Redis al que llega el pod, y `REDIS_HOST`/`REDIS_PORT` apuntan a él? | Es el cambio de comportamiento del release. ECOM ya provee Redis para los websockets; lo que hay que confirmar es que las variables están puestas en el Deployment de `web`, no solo en el de websockets |
| ¿Qué valen `ENVIRONMENT` y `DJANGO_SETTINGS_MODULE` en testing y en PRD? (es la pregunta abierta H-09) | Si `ENVIRONMENT` no está declarada, el ambiente queda con los defaults de desarrollo —caché local al proceso— en vez de con «prd» de regalo. Lo avisa `manage.py check --deploy` con `core.W002` |

Si testing **no** llega a un Redis, el release no se espeja hasta resolverlo: la app
arranca igual (`django_redis` no se conecta hasta el primer uso) pero cada pantalla que
lee caché responde error. Es un cambio de infraestructura del lado de ECOM, así que lo
pide el PM, no el espejo.

## Paso 1 — `/pushGitLabecomTEST`

Espeja el release a `ecom/test`, que despliega `https://datanach.ecomdev.ar/` (testing).

1. `git fetch origin main:main` y `git rev-parse main` → **ese SHA es el release**. El
   `main` local suele estar atrasado respecto del release publicado, y espejar un
   snapshot viejo es el error más fácil de cometer.
2. **Correr el `release-gate` para ese SHA y esperar a que termine en verde:**

   ```bash
   gh workflow run release-gate.yml --repo Mkdir-arg/Chaco-Back \
      --ref development -f sha=<sha-de-main>
   gh run list --repo Mkdir-arg/Chaco-Back --workflow=release-gate.yml --limit 1
   ```

   Verifica, sobre ese commit: CI verde del PR que lo originó, suite completa,
   migraciones sobre MariaDB, la imagen construida con su manifest de estáticos y un
   smoke HTTP con la imagen levantada. En rojo, **no se espeja**.
3. Revisar si `ecom/test` tiene commits de ellos (clon superficial; receta en
   `branching.md`). Si tocaron `.gitlab-ci.yml`, nuestra copia tiene que quedar byte a
   byte igual: se comparan blobs antes de seguir.
4. Mostrar los commits pendientes y el SHA, pedir confirmación, y recién ahí pushear
   `test` con el commit de alineación (sin `--force`).
5. Verificar con `git ls-remote ecom test` y avisar que el deploy de testing tarda 5 a
   7 minutos.
6. **Cerrar la sesión informando el SHA espejado.** Ese SHA es el insumo del paso 2.

## Paso 2 — `/pushGitLabecomPRD`

**Pushear `main` a ECOM es desplegar en producción.** No se corre a continuación del
paso 1: se corre cuando alguien verificó testing.

Recibe el **SHA verificado en testing** y, antes de tocar nada, comprueba:

1. **Que sea lo que se probó.** `git ls-remote ecom test` y `git rev-parse <sha>^{tree}`:
   el árbol del commit que hoy está en `ecom/test` tiene que ser **idéntico** al del SHA
   que se va a llevar a producción. Si no coincide, se probó otra cosa.
2. **Que el `release-gate` de ese SHA esté en verde** (`gh run list --workflow=release-gate.yml`),
   y que sea el del SHA, no el de otra corrida.
3. **Que alguien haya verificado testing**, con qué se probó y cuándo. Si la respuesta es
   «no lo miró nadie», el procedimiento termina acá.
4. **Que el esquema de PRD se haya mirado** (paso 0): la salida de
   `verificar_esquema_migraciones --solo-reporte` que mandó ECOM, sin «Migraciones
   registradas con otro número» ni «Tablas que ya existen». Si el release no trae
   migraciones nuevas esto es informativo; si las trae, es condición.
5. **Segunda confirmación escrita:** el operador tiene que escribir `PRODUCCION` —no
   «sí», no «dale»—. Recién con eso se pushea `main`.
6. Después del push, verificar `git ls-remote ecom main` y avisar que ArgoCD despliega
   solo, en 5 a 7 minutos, y que hay que mirar **Pipelines** del lado de ECOM.

Si el release trae migraciones, antes del paso 2 corresponde el runbook de rollback
(Anexo D de [`processes.md`](processes.md)) y el pedido del dump previo a ECOM.

## Lo que ninguno de los dos pasos hace

- No fuerza nunca (ni `--force`, ni `--force-with-lease`, ni borrar y recrear una rama).
- No toca `origin` (GitHub) ni ninguna rama que no sea `test` o `main` de ECOM.
- No edita `.gitlab-ci.yml`: es de ECOM y nuestra copia existe solo para que viaje en el
  release.
