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
