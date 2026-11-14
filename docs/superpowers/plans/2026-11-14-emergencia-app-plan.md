# Emergencia en la app móvil/PWA (Chaco-mobile): plan

**Base:** `Mkdir-arg/Chaco-mobile`, rama `test` (versión 1.2.10, `2862274`). Los PRs van contra `test`, y en cada uno se sube la versión con `npm run version:subir`.

**Decisiones del usuario (14/11/2026):**
- La rama es `test`.
- El orden es M1 → M3 → M2.
- Se hace un cambio aditivo en Chaco-Back: `perfil` con `llegadas`/`kits`, y cada dispositivo con `admite`/`recibe_kits`.
- Se agrega `expo-image-manipulator` para convertir a JPEG en nativo.

## Cómo está armada la app (lo que se reusa)

**Un árbol por módulo.** `App.js` (`renderModulo`) monta `BecasApp` o `DispositivosApp` según `moduloActivo`, y con varios módulos muestra el selector. Dentro de cada módulo la navegación es estado local, con `Banner` y `SettingsPanel`.

**`services/modulos.js`.** Filtra los módulos contra `MODULOS=['becas','dispositivos']`. Hoy un usuario que solo tiene Emergencia queda sin módulos y el login lo rechaza con `SIN_MODULOS`.

**`services/becasApi.js`.** Maneja:
- la sesión y el token, sin refresh (un 401 invalida la sesión);
- `becasRequest`;
- `becasUploadFile`, que sube **un solo archivo**;
- los errores, con `status`, `payload`, `retryAfter` y `network`.

**`context/AuthContext.js`.** Escucha `subscribeSinModulo`, pero solo la de Dispositivos.

**Offline, con el molde de `dispositivosService.js`.**
- Una base propia en SQLite (OPFS en web) y una outbox con estados.
- Reintentos con backoff de hasta 8 intentos.
- `uuid_cliente` en cada envío.
- `clasificarError` decide por status y `code`.

**Formularios dinámicos del back.** Están en `definicionFormulario.js`, `CampoFormulario` y `GrupoFormulario`. Los Formularios 1 y 2 de Emergencia son fijos: se arman como pantallas propias que reusan `FormInput`, `FechaInput` y `CustomButton`.

**Fotos.** `imagePicker.js` y `webImages.comprimirImagen` solo achican cuando la foto pasa 1,5 MB o es HEIC. **No fuerzan JPEG.** El tope de 5 MB está en `MAX_ATTACHMENT_BYTES`.

**DNI y GPS.**
- `CameraModal` escanea PDF417.
- `parseDniCode` está dentro de `RelevamientoDetailScreen.js`: hay que extraerlo.
- `ubicacion.posicionActual` y `permisos` resuelven el GPS.

**Tests.**
- `node --test tests/*.test.cjs`, con `tests/helpers/mobile-runtime.cjs`.
- Pantallas con `react-test-renderer`.
- Playwright con `npm run test:web`.
- CI en `.github/workflows/pr-mobile.yml`: versión, tests, build, Playwright, Docker y `expo-doctor`.

**Del lado del back no hay que tocar nada para CORS.** Ya cubre `/api/`, PATCH, `Date` y `Retry-After`.

## Riesgos de diseño

1. **El 403 `SIN_MODULO` en Emergencia también significa «falta un permiso parcial»** (agente, kits o llegadas). Ante ese código hay que volver a pedir `/perfil/`, y solo si el perfil también da 403 se saca el módulo. `AuthContext` pasa a escuchar una señal común.
2. **Hoy la app no sabe, por dispositivo, si la persona admite o recibe kits.** Lo resuelve el cambio aditivo en el back.
3. **El 409 de M2/M3 no trae `code`:** se distingue por `estado_actual`. `UUID_EN_USO` sí trae `code`.
4. **Aceptar, rechazar, alojar y los cierres no son idempotentes.** Si un timeout termina en reintento y el servidor contesta 409, la app lo tiene que tratar como «se hizo».
5. **No hay que tocar las bases ni las outbox de Becas y Dispositivos.** Emergencia lleva su propia base `emergencia_offline.db` y su propia carpeta de adjuntos.

## PRs

**Chaco-Back (aditivo, previo a M3/M2):** `perfil` suma `llegadas` y `kits` (sin quitar `dispositivo`), y `mis-dispositivos` suma `admite` y `recibe_kits` por dispositivo. Lleva su test de contrato y la entrada en `requerimientos.md`.

**Chaco-mobile, contra `test`:**

1. **Módulo Emergencia visible solo con permisos.**
   - Archivos: `modulos.js`, `App.js`, el ícono en `ModuloSelectorScreen`, `AuthContext` con la señal común de `SIN_MODULO`, `navigation/EmergenciaApp.js` y `screens/EmergenciaInicioScreen.js`, con el perfil cacheado y accesos según `relevar`, `llegadas` y `kits`.
   - Tests: que un usuario con solo Emergencia entra, el orden con tres módulos, y que un 403 parcial no saca el módulo.
2. **Base compartida.**
   - `uploadMultipart` con varios archivos.
   - `utils/jpeg.js`: canvas en web y `expo-image-manipulator` en nativo.
   - `utils/dni.js`.
   - `consultarIdentidad` con la ruta como parámetro.
   - `services/emergenciaApi.js`.
3. **M1, ingreso de familias.** `emergenciaCola.js` (outbox y localidades), el Formulario 1, «Mis envíos» y el borrador.
4. **M3, kits.** Mis dispositivos, entregas pendientes y la recepción con remito JPEG y `cantidades[id]`. Va sin cola.
5. **M2, lectura y decisiones.** Buscar por DNI con manejo del 429, aceptar o rechazar, integrantes y el router de recarga por `estado_actual`.
6. **M2, ficha y camas.** La ficha del Formulario 2 (mínimo más secciones) y el mapa de camas.
7. **M2, cierres y sin derivación.** Alojar, cerrar con diferencia, cancelar, ingreso directo y «Avisar a la mesa».

## Preguntas que siguen abiertas (se aplica el valor por defecto mientras nadie diga otra cosa)

- **Branding:** el mismo «DATAÑACH» para todos los módulos.
- **«Mis envíos»:** muestra también los envíos locales con error, como Dispositivos.
- **M2 sin conexión:** la pantalla se bloquea con un aviso. No hay solo lectura cacheada.
- **Ficha:** se cargan el mínimo y las secciones 4 a 8, como pide el contrato.
- **Avisos de derivaciones nuevas:** alcanza con el contador de «mis dispositivos». No hay notificaciones.
