# Colecciones Postman — Chaco API

Colecciones de Postman v2.1 para documentar y probar todos los endpoints del sistema.
Una colección por módulo, sin variables de entorno.

## Módulos

| Archivo | Módulo | Endpoints | Descripción |
|---------|--------|-----------|-------------|
| [healthcheck.postman_collection.json](healthcheck.postman_collection.json) | Healthcheck | 1 | Monitoreo de salud del sistema |
| [core.postman_collection.json](core.postman_collection.json) | Core | ~25 | AJAX helpers, performance, API geográfica |
| [users.postman_collection.json](users.postman_collection.json) | Users | ~30 | Auth operadores, CRUD usuarios/roles, API DRF |
| [configuracion.postman_collection.json](configuracion.postman_collection.json) | Configuración | ~40 | Geografía, secretarías, programas (wizard 4 pasos) |
| [conversaciones.postman_collection.json](conversaciones.postman_collection.json) | Conversaciones | ~20 | Chat público, backoffice operadores, API alertas |
| [legajos.postman_collection.json](legajos.postman_collection.json) | Legajos | ~70 | Ciudadanos, archivos, alertas, NACHEC, API DRF |
| [portal.postman_collection.json](portal.postman_collection.json) | Portal Ciudadano | ~25 | Auth ciudadano, registro, perfil, consultas |
| [dashboard.postman_collection.json](dashboard.postman_collection.json) | Dashboard | 8 | Panel principal, APIs de métricas |

## Cómo importar

1. Abrir Postman → **Import**
2. Seleccionar uno o más archivos `.json` de esta carpeta
3. La colección aparece en el panel izquierdo lista para usar

## Autenticación

El sistema usa **autenticación por sesión Django** (cookies), no tokens Bearer.

### Para endpoints de backoffice (operadores)

1. Hacer GET a `http://localhost:8000/` para obtener la cookie `csrftoken`
2. Hacer POST al login con las credenciales y el `csrfmiddlewaretoken`
3. Copiar la cookie `sessionid` de la respuesta
4. Setearla en el header `Cookie: sessionid=<valor>` de los requests subsiguientes

Para requests POST/PATCH/DELETE a la API DRF, agregar también:
```
X-CSRFToken: <valor-de-la-cookie-csrftoken>
```

### Para endpoints del portal ciudadano

Misma mecánica pero usando `POST /portal/mi-perfil/login/` con DNI como username.

### Endpoints públicos (sin autenticación)

- `GET /health/` — healthcheck
- `GET /conversaciones/chat/` — pantalla de chat
- `POST /conversaciones/consultar-renaper/` — verificación RENAPER
- `POST /conversaciones/iniciar/` — iniciar conversación
- `GET|POST /portal/mi-perfil/login/` — login ciudadano
- `GET|POST /portal/mi-perfil/registro/` — registro paso 1 y 2

## Convenciones de los request bodies

| Tipo de endpoint | Content-Type | Body |
|-----------------|--------------|------|
| Vistas HTML (backoffice) | `application/x-www-form-urlencoded` | Incluye `csrfmiddlewaretoken` |
| API DRF (GET) | — | Sin body |
| API DRF (POST/PATCH) | `application/json` | JSON |
| Subida de archivos | `multipart/form-data` | Campo `archivo` tipo file |

## URL base

Todos los requests apuntan a `http://localhost:8000`. Para apuntar a otro entorno,
usar la función **Find & Replace** de Postman sobre la colección importada.
