# Ramas y publicación a main

## Modelo

`development` es la rama de trabajo. `main` es la rama de release generada por
`.github/workflows/publish-main.yml`.

El manifiesto de exclusiones vive en `.gitattributes`, mediante
`export-ignore`. El guard del workflow es la segunda defensa: rechaza un
release que incluya archivos de desarrollo o al que le falten archivos de
runtime requeridos.

## Checklist de cutover (una única vez)

1. Mergear esta rama a `development`. Ese merge trae el workflow a
   `development` y, por ser un push a esa rama, **dispara automáticamente la
   primera publicación** de `main`.
2. Verificar en la pestaña **Actions** que **Publish main** terminó OK y que el
   árbol de `main` quedó limpio. Para este primer run `main` todavía **no** debe
   estar protegida, o el bot no podrá pushear.
3. Cambiar la rama por defecto del repositorio a `development` y re-apuntar los
   PR abiertos.
4. Proteger `main` con un ruleset: restringir actualizaciones y bloquear force
   pushes, con bypass solo para la app GitHub Actions.
5. Verificar en el servidor que `git status` esté limpio antes del primer pull.

Nota: el disparo manual por `workflow_dispatch` (botón **Run workflow**) queda
disponible para republicar a mano; solo aparece una vez que `development` es la
rama por defecto.

## Reglas permanentes

- Un nuevo archivo de desarrollo requiere agregar `export-ignore` y el guard
  correspondiente si es crítico.
- Nunca pushear ni mergear a `main` a mano.
- Un hotfix se resuelve con un PR a `development` y luego se publica.
- Nunca reescribir la historia de `main`: el servidor usa `git pull --ff-only`.

El árbol de `main` queda limpio, pero su historia anterior conserva los
archivos de desarrollo. Esto es aceptado: limpiarla exigiría un force-push y
rompería el pull del servidor.

## Espejo al GitLab de ECOM y su CI/CD

`main` se espeja al GitLab de ECOM (remoto `ecom`, comando `/pushGitLabecom`).
Del otro lado **no** es un repo pasivo: tiene CI/CD propio.

- El pipeline vive en **`.gitlab-ci.yml`**, lo mantiene ECOM y nosotros llevamos
  una copia byte a byte igual para que **viaje en el release**. GitLab lee ese
  archivo del commit que recibe: si la rama no lo trae, **no se crea pipeline** y
  la rama se actualiza sin construir imagen. Eso es lo que pasó con el espejo del
  11/08/2026, hecho antes de incorporarlo.
- Qué hace: construye la imagen del `Dockerfile` de la raíz y la sube al registry
  on-prem de ECOM con **el nombre de la rama en la ruta** —
  `…/datanach/<rama>:latest`. Corre solo para `test` y `main`, así que son dos
  imágenes distintas. **ArgoCD** las despliega.
- Los entornos de ECOM son suyos y se despliegan solos: `test` alimenta
  **testing** (`https://datanach.ecomdev.ar/`) y `main` está previsto para **QA**.
  Nada que ver con `icore-srv`, que seguimos desplegando a mano.
- **La rama `test` de ECOM no es nuestra.** Tiene commits propios de su
  automatización (autor `argocd`, `[ci skip]`), así que está divergida de nuestra
  `main`: un push normal se rechaza y forzarlo les borraría esos commits y su
  copia del pipeline. Actualizarla se acuerda con ellos.
- Un cambio de **código fuente** se despliega solo. Un cambio de **configuración**
  —variables de entorno, secretos, un CronJob— lo hace su equipo de devops. Por
  eso el SMTP y la sincronización periódica de SIIS dependen de ellos en esos
  entornos.
- Los logs de los pods se ven en **ArgoCD**, con usuario de dominio y VPN.

El `.gitlab-ci.yml` y el `Dockerfile` de la raíz están en la lista de archivos
**requeridos** del guard de `publish-main.yml`: si un release sale sin ellos, el
workflow falla en lugar de publicar una rama que no construye nada.
