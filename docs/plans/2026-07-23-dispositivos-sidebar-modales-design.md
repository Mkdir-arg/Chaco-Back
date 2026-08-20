# Dispositivos: grupo propio y edición en modales

## Contexto

La configuración incorporada por la Task #174 aparece como `Dispositivos`
dentro del grupo `Administración` y sus formularios de edición navegan a una
página independiente. Durante la revisión se acordó separar el módulo de la
administración general y mantener el contexto del tipo mientras se edita.

## Diseño aprobado

- El sidebar incorpora un grupo propio `Dispositivos`, visible únicamente para
  usuarios con alcance de configuración sobre el programa Dispositivos.
- El grupo contiene el subítem `Configuración`, que conserva la ruta
  `/dispositivos/config/`.
- El grupo `Administración` deja de considerar y mostrar el acceso a
  Dispositivos.
- `Editar tipo` y `Editar campo` usan un modal accesible sobre la pantalla de
  detalle del tipo.
- Desde el detalle, el formulario se obtiene por AJAX y el modal se abre sin
  recargar la página ni cambiar la URL.
- Las URLs directas de edición siguen siendo navegables: renderizan el detalle
  correspondiente con el modal abierto.
- Los errores de validación se muestran dentro del modal.
- Al guardar correctamente se actualiza el detalle afectado y se cierra el
  modal, sin recarga.
- Cancelar, Escape o pulsar el fondo cierran el modal sin recarga. Si se llegó
  por una URL directa, la URL vuelve al detalle mediante History API.
- `Nuevo tipo` y `Agregar campo` permanecen como páginas completas.

## Enfoque técnico

Se repite el patrón AJAX existente en Becas:

- Las vistas detectan `X-Requested-With: XMLHttpRequest`.
- El GET AJAX devuelve el formulario renderizado para inyectarlo en el
  contenedor del modal.
- El POST AJAX devuelve el contrato `{ok, target, html, message}` de
  `programas/views/ajax_utils.py`; el cliente reemplaza el parcial del detalle.
- Los errores de validación vuelven como `{ok: false, errors}` con estado 400 y
  se muestran junto a cada campo.
- CSRF, permisos y errores de red se manejan explícitamente.

El render server-side y las URLs directas se conservan como fallback. Los
parciales de campos se comparten entre las altas en página y las ediciones en
modal, evitando duplicar validaciones o markup.

## Validación

- Tests de visibilidad y agrupación del sidebar.
- Tests GET/POST tradicional y AJAX de ambas URLs de edición, incluyendo
  errores y permisos.
- Compilación de templates y auditoría de diseño.
- Prueba real en navegador: apertura y guardado sin navegación, cierre, errores,
  URL directa, responsive y navegación del grupo Dispositivos.
