# Mapa con Google Maps

Guía operativa para configurar Google Maps en Chaco: la API key, el Map ID, las variables de
entorno y los permisos. El contrato técnico de la pieza está en
`.claude/design/componentes/mapa_google.md`.

## Qué usa Google Maps

| Uso | Estado |
|---|---|
| Cargador común (`components/_google_maps.html` + `nodo-mapa.js`), CSP y capacidades | Fase 1 |
| Domicilio → coordenadas en los formularios (Dispositivo, Ciudadano, Emergencia) | Fase 2 |
| Mapa general `/mapa/`: capas de Dispositivos, Edificios y Emergencias + puntos sueltos | Fase 3 (hecha) |
| Lugar de la toma de Becas y enlace «Ver en el mapa» de Dispositivos | Fase 4 |

## 1. Crear la API key

1. En [Google Cloud console](https://console.cloud.google.com/), elegir o crear el proyecto del
   ambiente y asociarle una **cuenta de facturación** (sin facturación, la API no carga).
2. **APIs y servicios → Biblioteca**: habilitar **Maps JavaScript API** y **Geocoding API** (la
   segunda la usa el domicilio → coordenadas).
3. **APIs y servicios → Credenciales → Crear credenciales → Clave de API**.
4. Restringir la key (**obligatorio**, la key viaja en el HTML y cualquiera la puede leer):
   - **Restricciones de aplicaciones → Sitios web (referentes HTTP)**: el dominio de cada ambiente,
     por ejemplo `https://mi-entorno.ejemplo.ar/*`. En desarrollo, `http://localhost:8000/*`.
   - **Restricciones de API**: solo **Maps JavaScript API** y **Geocoding API**.
5. Una key por ambiente (dev, testing, producción). No se reutiliza la de producción en otro lado.

Referencia: [buenas prácticas de seguridad de API keys](https://developers.google.com/maps/api-security-best-practices).

## 2. Crear el Map ID y asignarle un estilo

Los marcadores del mapa son *Advanced Markers* y no cargan sin un Map ID.

1. **Google Maps Platform → Administración de mapas (Map management) → Crear ID de mapa**.
2. Tipo de mapa: **JavaScript**, rasterizado o vectorial (vectorial recomendado).
3. Para el estilo: **Estilos de mapa (Map styles) → Crear estilo**, ajustarlo (por ejemplo, menos
   puntos de interés para que se lean los marcadores) y **asociarlo al Map ID**. Los cambios de estilo
   se publican desde la consola, sin tocar el código.

Referencia: [estilos de mapa en la nube](https://developers.google.com/maps/documentation/javascript/cloud-customization).

## 3. Variables de entorno

| Variable | Valor | Si falta |
|---|---|---|
| `GOOGLE_MAPS_API_KEY` | La key del paso 1 | No se carga Google ni se abre la CSP; las pantallas muestran su estado vacío |
| `GOOGLE_MAPS_MAP_ID` | El Map ID del paso 2 | En `dev` se usa `DEMO_MAP_ID` (solo para probar). En `qa`/`prd`, `manage.py check --deploy` avisa con `core.W005` |

La key **nunca** se escribe en el código ni en un archivo del repo: va en el entorno del contenedor
o en el `.env` del servidor.

## 4. Seguridad de contenido (CSP)

Con `GOOGLE_MAPS_API_KEY` configurada, `SecurityHeadersMiddleware` suma los hosts que pide Google
(`GOOGLE_MAPS_SOURCES` en `config/middlewares/security_headers.py`, tomados de la política
*allowlist* de la [guía de CSP de Google](https://developers.google.com/maps/documentation/javascript/content-security-policy)).
Sin key no se agrega nada.

**Referente.** Django responde con `Referrer-Policy: same-origin`, y con esa política el navegador no le
manda `Referer` a Google, que entonces rechaza la key restringida por referente. Por eso `nodo-mapa.js`,
recién cuando la pantalla pide el mapa, pasa la política de **esa página** a
`strict-origin-when-cross-origin`: a Google le llega el origen del sitio (`https://mi-entorno.ejemplo.ar`),
nunca la ruta ni el legajo abierto. El resto del sitio no cambia.

## 5. Permisos

Dos capacidades en el módulo **Mapa** del ABM de Roles (pestaña General):

| Capacidad | Permite |
|---|---|
| `mapa.ver` | Ver `/mapa/` |
| `mapa.editar` | Agregar, mover y eliminar puntos del mapa |

La migración `users.0050` se las da al rol Administrador. Al resto de los roles se las asigna el PM.

## 6. La pantalla `/mapa/`

Ítem «Mapa» del menú, con `mapa.ver`. Cada capa se ve según la regla de lectura de su propio módulo:

| Capa | Quién la ve | Qué muestra |
|---|---|---|
| Dispositivos | quien ve dispositivos (su alcance de siempre) | los que tienen coordenadas; los de **ubicación reservada** no se dibujan nunca, solo se cuentan |
| Edificios | quien ve edificios | los vigentes con coordenadas; un edificio que ocupa algún dispositivo de ubicación reservada (aunque lo comparta) no se dibuja, solo se cuenta |
| Casos de Emergencia | quien opera o supervisa la mesa | los abiertos con coordenadas: número, prioridad, estado y hace cuánto se relevaron. **Nunca** nombre, documento ni dirección |
| Puntos | todos los que entran a `/mapa/` | lo cargado en el mapa (sedes, equipos, vehículos, otros) |

Lo que no tiene coordenadas se cuenta en la nota de su capa («no se ven: 3 sin ubicación»). Las coordenadas de
dispositivos, edificios y casos se editan en sus propios formularios; en el mapa solo se mueven los puntos.

Con `mapa.editar`: «Agregar punto» (tocar el mapa y completar nombre, categoría y descripción), arrastrar un punto
para moverlo y eliminarlo desde su detalle. La API que usa la pantalla:

| Método y ruta | Capacidad | |
|---|---|---|
| `GET /mapa/api/puntos/` | `mapa.ver` | lista de puntos |
| `POST /mapa/api/puntos/` | `mapa.editar` | alta (`nombre`, `categoria`, `descripcion`, `latitud`, `longitud`) |
| `PATCH /mapa/api/puntos/<id>/` | `mapa.editar` | mover (`latitud`, `longitud`, JSON o formulario) |
| `DELETE /mapa/api/puntos/<id>/` | `mapa.editar` | baja |

Responde JSON (también 401 y 403), exige el token CSRF y valida el rango de coordenadas. Los puntos también se
administran desde el admin de Django («Puntos del mapa»).

## 7. Costos

Google cobra por uso: cada carga de mapa y cada búsqueda de domicilio consumen cuota, con un crédito
mensual gratuito. Conviene configurar alertas de presupuesto en la cuenta de facturación del proyecto.
