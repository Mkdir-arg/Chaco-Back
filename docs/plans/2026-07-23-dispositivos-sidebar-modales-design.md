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
- Las URLs directas de edición siguen siendo navegables: renderizan el detalle
  correspondiente con el modal abierto.
- Los errores de validación se muestran dentro del modal.
- Al guardar correctamente se redirige al detalle del tipo.
- Cancelar, Escape o pulsar el fondo cierran el modal y vuelven a la URL del
  detalle.
- `Nuevo tipo` y `Agregar campo` permanecen como páginas completas.

## Enfoque técnico

Se reutiliza render server-side. Las vistas de edición entregan el mismo
contexto que la vista de detalle y agregan el formulario y el tipo de modal a
mostrar. Un parcial compartido dibuja cada formulario, tanto en su página de
alta como dentro del modal, evitando duplicar validaciones o markup.

No se agrega AJAX: mantiene el flujo Django existente, conserva el
comportamiento de las URLs directas y reduce estados de error en cliente.

## Validación

- Tests de visibilidad y agrupación del sidebar.
- Tests GET/POST de ambas URLs de edición, incluyendo errores.
- Compilación de templates y auditoría de diseño.
- Prueba real en navegador: apertura, cierre, errores, guardado, URL directa,
  responsive y navegación del grupo Dispositivos.
