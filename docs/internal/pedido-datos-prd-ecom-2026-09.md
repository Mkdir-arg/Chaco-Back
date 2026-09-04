# Pedido de datos del ambiente productivo a DevOps de ECOM — 2026-09-03

Acompaña al **Cambio 63** del [archivo vivo de requerimientos](requerimientos.md) y al
[análisis de performance del login](analisis-performance-login-2026-09.md). Acá vive lo que se le pide
al equipo que administra el Kubernetes de producción, por qué se pide cada dato y qué se hace con la
respuesta.

## Por qué se pide

El Cambio 63 resuelve en la imagen las dos causas de latencia que encontró el análisis: el hash de la
contraseña (Argon2 en lugar de PBKDF2) y la posibilidad de servir el HTTP con varios procesos. La
primera llega sola con el build. La segunda **no se activa sola**: hay que decidir con qué forma se
reparte la carga y con qué recursos, y esa decisión necesita datos del ambiente real que no tenemos.

## Decisión tomada de nuestro lado (no se delega)

La arquitectura la definimos nosotros; DevOps aplica la configuración y aporta los datos del ambiente.

- **ECOM (Kubernetes): se arranca subiendo réplicas del Deployment actual**, sin cambiar el runtime.
  Motivo: es un número en el manifiesto, no toca el ingress ni el enrutamiento del chat, y ya da un
  núcleo por réplica. El modo `APP_RUNTIME=gunicorn` queda como segundo paso, solo si las métricas
  muestran que hace falta.
- **`icore-srv` (Docker Compose): gunicorn**, que es lo que ya quedó en el compose del repo. Motivo: ahí
  nginx ya separa `/ws/` hacia el contenedor `websocket`, así que no hay nada nuevo que enrutar.

Por eso el mensaje **no** les ofrece elegir entre las dos opciones: les anticipa el cambio, les pide los
datos y les avisa que después les pasamos la configuración concreta.

## Mensaje enviado

> Hola equipo,
>
> Les escribo para anticiparles dos cambios de performance que vienen en las próximas versiones de
> DATAÑACH y para pedirles algunos datos del ambiente productivo, así terminamos de definir la
> configuración con información completa.
>
> **Qué detectamos**
>
> Usuarios reportan que el login y algunas pantallas tardan más de lo normal, de forma intermitente.
> Analizamos el código y la configuración de despliegue y encontramos dos causas principales:
>
> 1. La verificación de la contraseña en el login cuesta cerca de 1 segundo de CPU por intento. Django
>    5.2 usa por defecto PBKDF2 con 1.000.000 de iteraciones, y ese segundo se ejecuta con el intérprete
>    bloqueado: mientras alguien se loguea, el resto de los usuarios del mismo proceso espera.
> 2. Todo el tráfico HTTP corre en un solo proceso Python (Daphne). Por el GIL de Python, eso significa
>    un solo núcleo para todos los usuarios, aunque el nodo tenga más. Medimos que con 8 usuarios
>    concurrentes los tiempos se multiplican por 3,5 aproximadamente.
>
> **Qué cambia en la imagen**
>
> - Contraseñas con Argon2 en lugar de PBKDF2. Baja la verificación de ~950 ms a ~90 ms. Es transparente
>   para ustedes: sin migración ni variables nuevas, y las contraseñas existentes siguen funcionando (se
>   actualizan solas la primera vez que cada usuario entra). Llega con el próximo build de la imagen.
> - La imagen incorpora un modo alternativo para servir el HTTP con varios procesos. El comportamiento
>   por defecto no cambia: si no se toca nada, el pod sigue arrancando con Daphne exactamente como hoy.
>
> Cómo repartir el HTTP en producción (más réplicas o el modo nuevo) lo vamos a definir de nuestro lado
> con los datos que les pedimos abajo, y después les pasamos la configuración concreta a aplicar:
> variables, réplicas y recursos.
>
> **Dos puntos para que revisen de su lado**
>
> - El límite de CPU del pod (`resources.limits.cpu`). Si es bajo, el hash de la contraseña se estrangula
>   y el login tarda más todavía.
> - HTTP/2 en el ingress. Cada pantalla del backoffice carga unos 40 archivos estáticos; con HTTP/1.1 eso
>   son varias tandas de ida y vuelta. Los estáticos ya salen comprimidos desde la app.
>
> **Información que necesitamos**
>
> 1. Réplicas actuales del Deployment y `resources` (requests y limits de CPU y memoria).
> 2. Cantidad de CPU y memoria del nodo o nodos donde corre.
> 3. Valor actual de `APP_RUNTIME` en el pod y si usan `command`/`args` propios o el entrypoint sin
>    argumentos.
> 4. Ingress: ¿HTTP/2 habilitado? ¿Compresión? ¿Cuáles son los timeouts hacia el pod (lectura y envío)?
> 5. Redis: versión, memoria asignada y política de `maxmemory`. Es importante porque ahí viven las
>    sesiones y la caché: con `allkeys-lru` y memoria llena, Redis expulsa sesiones y los usuarios quedan
>    deslogueados.
> 6. Base de datos: motor y versión (¿MySQL 8 o MariaDB?) y el `max_connections` configurado. Con varios
>    procesos web sube la cantidad de conexiones simultáneas.
> 7. Métricas de CPU y memoria del pod de los últimos días (7 si tienen esa retención, si no lo que haya)
>    y, si el ingress lo registra, el tiempo de respuesta del upstream, en particular para `POST /` y
>    `GET /inicio/`.
> 8. Si el pod tuvo reinicios (OOMKilled u otros) en las últimas semanas.
>
> **Próximos pasos**
>
> Validamos los dos cambios primero en nuestro ambiente de prueba, los espejamos a GitLab por el flujo
> habitual (test y luego main) y, con los datos de arriba, les mandamos la configuración definitiva para
> producción. Cualquier duda, quedamos a disposición.
>
> Saludos.

## Para qué sirve cada dato

| # | Dato | Para qué lo necesitamos |
|---|---|---|
| 1 | Réplicas y `resources` del Deployment | Es la variable que vamos a mover. Un `limits.cpu` bajo estrangula el hash del login, y el `limits.memory` define cuántos procesos entran si algún día pasamos a gunicorn (~150–200 MB por worker) |
| 2 | CPU y memoria del nodo | Techo real: no tiene sentido pedir réplicas que el nodo no sostiene |
| 3 | `APP_RUNTIME` y si usan `command`/`args` propios | Con comando propio el entrypoint **se saltea migraciones y sembrado** (Cambio 31): hay que saber si el bootstrap va por initContainer antes de tocar nada |
| 4 | HTTP/2, compresión y timeouts del ingress | El H-4 del análisis: ~40 archivos por pantalla. Y los timeouts del ingress son el límite efectivo para el usuario, por encima del de la app |
| 5 | Redis: versión, memoria y `maxmemory` | Ahí viven **sesiones y caché**. Con `allkeys-lru` y memoria llena, Redis expulsa sesiones: usuarios deslogueados sin causa aparente. Aplica igual a `icore-srv`, que hoy tiene `maxmemory 350mb` con esa política |
| 6 | Motor de base y `max_connections` | Su ambiente de testing corre **MariaDB**, no MySQL (Cambio 31, historial del 13/08/2026): por eso se pregunta en vez de afirmar. Con varios procesos web suben las conexiones simultáneas (`CONN_MAX_AGE=60`) |
| 7 | Métricas y tiempo de respuesta del upstream | Es la línea de base para comparar antes y después. Sin esto, la mejora del login no se puede demostrar del lado de producción |
| 8 | Reinicios del pod (OOMKilled) | Responde directo si el límite de memoria ya está pegando hoy |

## Qué se hace cuando lleguen las respuestas

1. Fijar el número de réplicas y los `resources` concretos, y pasárselos como configuración a aplicar.
2. Contrastar la línea de base (dato 7) con la medición posterior al despliegue de Argon2.
3. Si los datos 5 o 6 muestran un límite ajustado (Redis chico, `max_connections` bajo), tratarlo como
   pendiente propio antes de sumar procesos.
4. Registrar el resultado en el **Historial** del Cambio 63.

## Estado

**Enviado el 03/09/2026. Sin respuesta al momento de escribir esta nota.**
