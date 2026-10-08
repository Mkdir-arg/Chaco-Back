# Shells · qué extiende cada superficie

Las cuatro superficies tienen herencia y assets distintos. **No se mezclan.**

---

## 1. Backoffice — `templates/includes/base.html`

**Clasificación:** Canónico reutilizable.
**Evidencia:** `templates/includes/base.html`, `templates/includes/navbar.html`,
`templates/includes/sidebar/base.html`.
**Bloques:** `title`, `main-content`, `customJS`.

Se hereda; no se recrean el sidebar ni sus offsets.

- El sidebar es un **único panel responsivo**: overlay en móvil y fijo/colapsable en escritorio,
  con una sola inclusión de `templates/includes/sidebar/opciones.html`. Su control de cierre móvil
  queda fuera del panel y usa `x-show="sidebarOpen"` con `display: none` inicial, para no
  interceptar el botón de abrir cuando está fuera de pantalla.
- Tailwind se sirve desde `static/custom/css/tailwind.css`, generado por `npm run build:tailwind`
  con `tailwind.config.js`. **No** se usa el CDN de Play.
- La fuente de íconos se precarga con
  `<link rel="preload" as="font" type="font/woff2" crossorigin>` sobre `fa-solid-900.woff2` justo
  antes de la hoja de Font Awesome: sin eso el navegador la descubre recién al parsear
  `all.min.css` y, con `font-display:block`, los íconos tardan un round-trip extra en aparecer. El
  `crossorigin` es obligatorio aunque sea del mismo origen; si falta, la precarga no se reutiliza
  y la fuente se baja dos veces.
- El cierre de sesión del menú de usuario es un `<form method="post">` con `{% csrf_token %}`, no
  un enlace: `LogoutView` no acepta GET desde Django 5.0.
- Los grupos del usuario llegan al JS como
  `{{ user_groups_list|json_script:"user-groups-data" }}` + `window.userGroups = JSON.parse(...)`:
  los nombres de rol son texto libre y **nunca** se interpolan con `|safe` dentro de un `<script>`.
- El WebSocket `static/custom/js/conversaciones_lista_ws.js` se carga únicamente en la ruta
  `conversaciones:lista`; en esa ruta, `static/custom/js/conversaciones_tiempo_real_global.js` usa HTTP
  solo como fallback mientras el socket no esté abierto, y suspende o cancela el polling en
  pestañas ocultas.
- `static/custom/js/alertas_websocket.js` viaja **solo** con `puede_alertas_sensibles`, la variable que
  publica el context processor `conversaciones.context_processors.user_groups` a partir de
  `ciudadano.sensible`. Es un guard **único**: la campana del navbar —su única superficie, con el
  dropdown y el punto de estado— y `/ws/alertas/` piden la misma capacidad desde D-11, así que quien no
  la tiene no ve campana ni recibe el archivo. Un script de tiempo real que se carga sin mirar
  capacidades cobra 1 + 5 handshakes rechazados por página contra el único proceso ASGI y deja el
  indicador en «Desconectado»: ante un cierre con código `4403` el cliente **no reintenta**.
- El shell ya carga: el modal global de confirmaciones (`ModernModal`, `#modal-overlay`), los
  toasts, el `<template>` de los filtros dinámicos (`templates/components/list_filters.html`) y
  `static/custom/js/dynamic_list_filters.js`.
- **No carga ningún script que reescriba estilos de la página.** El shell no toca el tamaño ni el
  `display` de los controles: el área táctil de 44 px la dan `static/custom/css/nodo-buttons.css` y el
  `<style>` de `templates/includes/sidebar/base.html`, los dos detrás de `@media (pointer: coarse)`, así
  que con mouse cada control conserva el alto de su token (ítem del sidebar: 40 px).
- El `<html>` no lleva utilidad de fondo: el canvas sale de `--fondo-principal`.
- El shell carga `static/custom/js/nodo-submit-guard.js`: el segundo envío de un
  `<form method="post">` que no sea `data-ajax` queda cancelado, sus botones de envío pasan a
  `disabled` en el turno siguiente —deshabilitarlos durante el evento les borraría el `name`/`value`
  del POST— y el form queda `aria-busy="true"` hasta que se recargue o se vuelva con «atrás».
  Si el envío terminó **cancelado** —incluso por un listener delegado en `document` que la pantalla
  registre en `customJS`, que corre *después* de la guardia— la marca se suelta y no se deshabilita
  nada. Ninguna pantalla repite esa guardia. El shell publica además `window.alertasConfig`
  (`ciudadanoDetalleUrlTemplate`), que es de donde sale el destino de «Ver» en la alerta crítica:
  el JS no escribe rutas literales.
- El shell carga `static/custom/js/nodo-tabs.js`: flechas ← →, Home/End y `tabindex`
  itinerante sobre toda `[role="tablist"]` con `[role="tab"]`, en cualquier pantalla. Es
  **mejora progresiva** —activa la solapa disparando su propio `click()`, así que no toca el
  estado de Alpine ni nada visual, y sin el archivo las solapas siguen funcionando con el
  mouse—. Ninguna pantalla repite ese manejo de teclado.
- **Las rutas que consulta el JS del shell salen del template, no del `.js`.** La campana de
  alertas (`#alertas-campana`, en `templates/includes/navbar.html`) lleva `data-url-count` y
  `data-url-preview` resueltos con `{% url %}`, y `static/custom/js/alertas_websocket.js` las lee
  con `dataset`; sin el atributo no consulta nada. Un archivo de `static/` no pasa por el motor
  de templates, así que una ruta escrita a mano ahí no la revisa nadie hasta que devuelve 404 en
  producción (RED-42; el barrido vive en `core/tests/test_urls_del_front.py`). Lo mismo vale para
  el tema: la preferencia de modo oscuro se guarda **solo** en `localStorage` y no se postea a
  ninguna ruta (RED-75, D-RED-07 = A; candado en `users/tests/test_tema.py`).
- El backdrop del sidebar móvil es `bg-black/50`; el botón de menú y su separador se esconden en
  escritorio con `lg:hidden` y nada más, sin `!important` ni clases hook.
- El menú del avatar (`templates/includes/navbar.html`) tiene **dos** entradas: «Cambiar
  contraseña» (enlace a `users:cambiar_contrasena`) y «Cerrar sesión» (botón de un `<form>` POST,
  porque `LogoutView` ya no acepta GET). Es la única entrada del producto al cambio voluntario de
  clave: antes el flujo existía solo como `/password_change/` de `django.contrib.auth.urls`, sin
  plantilla ni link, y se retiró (SEC-26). El enlace usa utilidades (`text-heading
  hover:bg-secondary`) y no `style=`; el ancho del panel es `w-40`.
- El shell publica `window.idleLogoutConfig` y carga `static/custom/js/idle-logout.js`: aviso con
  cuenta regresiva y cierre por inactividad. Lleva `keepAliveUrl` (`{% url 'core:sesion_latido' %}`),
  que es lo que le traduce al servidor la actividad del usuario: el cierre de verdad lo decide
  `core.middleware.ExpiracionPorInactividadMiddleware`, que cuenta **pedidos**, y sin ese latido una
  pantalla larga que no pide nada —un relevamiento tipeado veinte minutos— terminaría en el login con
  el formulario perdido. El latido sale como mucho una vez por minuto y solo con actividad real.

---

## 2. Autenticación pública — `users/templates/user/base_public_auth.html`

**Clasificación:** Canónico reutilizable.
Superficie **sin sesión**, sin menú ni alertas internas, para credenciales. La extienden
`users/templates/user/establecer_contrasena.html`,
`users/templates/user/recuperar_contrasena.html`,
`users/templates/user/recuperar_contrasena_enviada.html`,
`users/templates/user/cambiar_contrasena_obligatorio.html` y
`users/templates/user/cambiar_contrasena.html`.

Contrato: clases `public-auth__title`, `__help`, `__field`, `__error`, `__button` y `__link`, con
`button.public-auth__link` para la misma apariencia cuando la acción tiene que ir por formulario.
La marca web usa `static/custom/chaco/login-logo.png` (330×120, logo del Gobierno del Chaco) y el
CSS compilado `static/custom/css/tailwind.css`. `static/custom/icore/nodo-logo.svg` es la marca de
ICore y **no** se usa en superficies del organismo. No reutiliza el shell del backoffice.

---

## 3. Portal ciudadano — `portal/templates/portal/base.html`

**Clasificación:** Canónico reutilizable.
Superficie separada del backoffice, consumidora de `static/custom/css/tailwind.css` compilado.

Contrato de marca: título del navegador «DATAÑACH — Portal Ciudadano», header «DATAÑACH» +
«Portal Ciudadano · Gobierno del Chaco», footer con la misma marca, copyright con año dinámico
(`{% now "Y" %}`) y **un solo dato de contacto: la casilla `datanach@chaco.gob.ar`** en header y
footer. El teléfono que figuraba antes era ficticio y se sacó de todas las superficies: no volver
a introducir un teléfono sin dato real confirmado por el PM. No se usa la sub-marca «Ñandé».

La home (`portal/templates/portal/home.html`) toma su contexto de
`portal.selectors.public.get_portal_home_context`, cacheado 5 minutos (`portal:home_ctx`).
**La home no ofrece login ni registro de ciudadano:** el portal ciudadano está apagado y
`portal/urls.py` ya no publica ninguna ruta `mi-perfil/*`, así que ningún template puede escribir
`{% url 'portal:ciudadano_…' %}` —revienta con `NoReverseMatch`—. La página se ordena alrededor
del único camino vivo: la inscripción llega por el link que envía el programa, sin cuenta ni
contraseña (hero + bloque «Se ingresa por link», franja de números, listado de programas activos
sin link por tarjeta, aviso «¿Recibiste un link de inscripción?» y cierre «Cómo inscribirte»
junto a la tarjeta de Ayuda). El contexto expone `programas` y `stats`; `ciudadano_items` y
`consulta_items` se dieron de baja con las tarjetas de perfil y consultas.

`portal/templates/portal/ciudadano/base_ciudadano.html` y las pantallas bajo
`portal/templates/portal/ciudadano/` quedan en el repo **sin ruta**: no son referencia para
pantallas nuevas, y volver a publicarlas exige arreglar antes el registro.

Ese shell comparte el cierre por inactividad del backoffice —misma `window.idleLogoutConfig`, mismo
`keepAliveUrl`— y su `logoutUrl` propia: la configuración se escribe igual en las dos superficies para
que el contador del servidor valga para las dos.

Las pantallas de inscripción pública **no** extienden este shell: usan el suyo, para no cargar
`static/custom/js/portal-effects.js`. Light-only.

---

## 4. Inscripción pública — `portal/templates/portal/inscripcion/base_inscripcion.html`

**Clasificación:** Canónico reutilizable.
Layout «Panel de marca»: grid `var(--di-panel-w) minmax(0,1fr)` desde 1024 px (el ancho del panel
se declara una sola vez en `.di-shell`: 520 px), con panel `var(--gradient-brand)` a la izquierda
y columna de contenido blanca a la derecha.

- **En escritorio el panel es fijo:** `.di-panel-head` va `position: fixed; top: 0; height: 100vh`
  y `.di-panel-foot` `position: fixed; bottom: 0`, las dos con `width: var(--di-panel-w)`. Por
  largo que sea el formulario solo scrollea la columna de contenido, y la primera columna del grid
  queda vacía porque sus dos piezas salen del flujo (la mantiene el track explícito).
- La cabecera lleva `overflow-y: auto` y `padding-bottom: 136px` —alto del pie (112 px) más aire—
  para que en ventanas muy bajas su contenido siga alcanzable.
- En celular el panel vuelve al flujo como cabecera compacta y el pie con ayuda y copyright se
  recoloca debajo del contenido (mismo HTML, solo `grid-template-areas` por media query).
- El pie del panel en escritorio va sobre `var(--bg-navy)` sólido (no sobre el gradiente) por el
  contraste del texto blanco; el cuerpo del panel conserva el gradiente.

**Bloques:** `title`, `panel_titulo` (etiqueta + `<h1>` + bajada, con fallback si no hay
convocatoria en contexto), `stepper` (vacío por defecto: cada página lo completa con
`{% include "portal/inscripcion/_stepper.html" with paso_activo=1 %}`, 1/2/3 según el paso; las
pantallas de resultado lo dejan vacío), `content` y `extra_js`.

`portal/templates/portal/inscripcion/_stepper.html` no distingue el paso activo solo por color: el
`<li>` correspondiente lleva `aria-current="step"` (con `data-step` conservado solo para el CSS del
círculo, vía `[aria-current="step"] .di-step__circle`) y un
`<span class="sr-only">Paso actual: </span>` antes del nombre del paso; `sr-only` sale de
`static/custom/css/tailwind.css`.

**No carga** `static/custom/js/portal-effects.js`, Alpine, Font Awesome, los toasts ni el modal de
`portal/templates/portal/base.html`; sin `animate-fadeInUp` ni `@keyframes`.

**Único JS propio del shell** (inline, sin dependencias): refresca el `csrfmiddlewaretoken` de los
formularios contra `{% url "portal:csrf_token" %}` cuando la pestaña vuelve al frente
(`visibilitychange`, `focus`, `pageshow` persistido), con throttle de 30 s y salida temprana si la
página no tiene formulario; el backoffice y el portal comparten dominio y el login rota la cookie
CSRF de todo el navegador. Si el pedido falla se manda el token original y el 403 cae en
`portal/templates/portal/sesion_vencida.html`, pantalla recuperable del `CSRF_FAILURE_VIEW`
(`config.views.csrf_failure`) que extiende este mismo shell con su `panel_titulo` y sin stepper.

**Analítica:** con `GTM_CONTAINER_ID` configurado el shell incluye `_gtm_head.html` (dataLayer
inicial con `pantalla`, `programa`, `convocatoria` y `convocatoria_id`, más el contenedor de Google
Tag Manager, primero en `<head>`) y `_gtm_body.html` (el `<noscript>` apenas abre `<body>`);
`portal/templates/portal/inscripcion/confirmacion.html` emite `inscripcion_enviada` en `extra_js`
una sola vez por envío. Sin la variable no se renderiza nada: se activa por entorno, nunca por template.

**Tokens consumidos:** `--gradient-brand`, `--bg-navy`, `--bg-white`, `--text-white`,
`--bg-secondary`, `--bg-brand-soft`/`--bg-brand-softer`, `--bg-brand-tint`, `--border-brand-subtle`,
`--bg-danger-soft`, `--border-danger-subtle`, `--text-fg-danger`, `--text-fg-brand`,
`--text-heading`, `--text-body`, `--text-body-subtle`, `--border-base`, `--font-size-*`,
`--font-weight-*`, `--radius-*`. Light-only.

Lo extienden `portal/templates/portal/inscripcion/paso1.html`,
`portal/templates/portal/inscripcion/paso2.html`,
`portal/templates/portal/inscripcion/confirmacion.html`,
`portal/templates/portal/inscripcion/ya_inscripto.html`,
`portal/templates/portal/inscripcion/no_disponible.html`,
`portal/templates/portal/inscripcion/demasiados_intentos.html` y
`portal/templates/portal/sesion_vencida.html`.

---

## 5. Legacy — el wrapper heredado (retirado)

**Clasificación:** histórico. El archivo **ya no existe**: FE-20 migró sus 17 consumidores —los 14
templates de Configuración (`*_form`, `*_confirm_delete` y los cuatro pasos del wizard) y las tres
páginas de error 403/404/500— al shell del backoffice y lo borró. La regla `[R:SHELLLEGACY]` de
`scripts/design_audit.py` queda como guarda: si alguien vuelve a escribir ese `{% extends %}`, falla.

Sus parciales `templates/components/alertas_eventos.html` y
`templates/components/widget_contactos.html` siguen vivos y pertenecen a ese mundo: no se incluyen
en pantallas nuevas (el segundo lo retira LEG-06).
