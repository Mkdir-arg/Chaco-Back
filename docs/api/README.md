# Colecciones Postman — APIs de Chaco

Colecciones [Postman](https://www.postman.com/) (formato v2.1) para probar las
APIs REST del repo a mano.

## Archivos

| Archivo | Contenido |
|---|---|
| `chaco.postman_environment.json` | Entorno compartido: `base_url`, `token` y demás variables. Importalo una vez y seleccionalo arriba a la derecha en Postman. |
| `becas-campo.postman_collection.json` | API de la app de campo de Becas (`/api/becas/`). Auth por token. |

> El resto de las APIs (`/api/legajos/`, `/api/core/`, `/api/users/`,
> `/api/conversaciones/`) se documentan como colecciones nuevas en esta misma
> carpeta, siguiendo las convenciones de abajo.

## Cómo usar

1. **Importá** el entorno y las colecciones en Postman (`Import` → arrastrá los `.json`).
2. Seleccioná el entorno **Chaco (local)** en el selector de entornos.
3. Ajustá `base_url` si no usás Docker local (default `http://localhost:8000`).
4. Corré primero el request de **login/token**: su script de test guarda el
   `token` en la variable de entorno automáticamente, y el resto de los requests
   lo toman del header de autenticación de la colección.

## Convenciones para agregar colecciones

- **Una colección por API** (`<area>.postman_collection.json`), con carpetas por
  recurso (p. ej. `Relevamientos`, `Formularios`).
- **Nunca hardcodear** host, tokens ni IDs: usar variables (`{{base_url}}`,
  `{{token}}`, `{{relevamiento_id}}`, …). Las variables compartidas van en el
  entorno; las propias de una colección, en sus *collection variables*.
- **Auth a nivel colección** cuando todos los requests comparten esquema
  (header `Authorization: Token {{token}}` para las APIs con DRF authtoken).
- El request de **login** debe guardar el token con un test script
  (`pm.environment.set("token", ...)`), así no hay que copiarlo a mano.
- Documentar cada request con su `description` (qué hace, qué capacidad exige,
  transiciones de estado válidas).

## Fuente de verdad

El contrato real es el código (`*/api/*.py`, `*/api_urls.py`) y el schema
OpenAPI que sirve drf-spectacular:

- Swagger UI: `{{base_url}}/api/docs/`
- ReDoc: `{{base_url}}/api/redoc/`
- Schema crudo: `{{base_url}}/api/schema/`

Si una colección y el código divergen, gana el código.
