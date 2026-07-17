# Ramas y publicación a main

## Modelo

`development` es la rama de trabajo. `main` es la rama de release generada por
`.github/workflows/publish-main.yml`.

El manifiesto de exclusiones vive en `.gitattributes`, mediante
`export-ignore`. El guard del workflow es la segunda defensa: rechaza un
release que incluya archivos de desarrollo o al que le falten archivos de
runtime requeridos.

## Checklist de cutover (una única vez)

1. Mergear esta rama a `development`.
2. Cambiar la rama por defecto del repositorio a `development`.
3. Re-apuntar los PR abiertos a `development`.
4. Ejecutar **Publish main** con `workflow_dispatch`; su primer commit deja
   `main` con el árbol de release limpio.
5. Proteger `main` con un ruleset: restringir actualizaciones y bloquear force
   pushes, con bypass solo para la app GitHub Actions.
6. Verificar en el servidor que `git status` esté limpio antes del primer pull.

## Reglas permanentes

- Un nuevo archivo de desarrollo requiere agregar `export-ignore` y el guard
  correspondiente si es crítico.
- Nunca pushear ni mergear a `main` a mano.
- Un hotfix se resuelve con un PR a `development` y luego se publica.
- Nunca reescribir la historia de `main`: el servidor usa `git pull --ff-only`.

El árbol de `main` queda limpio, pero su historia anterior conserva los
archivos de desarrollo. Esto es aceptado: limpiarla exigiría un force-push y
rompería el pull del servidor.
