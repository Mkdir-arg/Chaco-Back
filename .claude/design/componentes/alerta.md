# Componente · Alerta inline (`components/_alerta.html`)

**Clasificación:** Canónico reutilizable. Pieza única, variante única.
**Evidencia:** `templates/components/_alerta.html`, `core/tests/test_nodo_ui_piezas.py`.
**Consumidores de referencia:** `programas/templates/programas/becas/config/programa_list.html`
(nota informativa del modal), `programas/templates/programas/becas/config/programa_detail.html`,
`programas/templates/programas/becas/revision/formulario_detalle.html`.

## Invocación

```django
{% include "components/_alerta.html" with tono="warning" titulo="Sin padrón el link queda abierto" texto="Cualquier persona que lo reciba puede inscribirse y ocupar cupo." %}
```

| Parámetro | Efecto |
|---|---|
| `tono` | `warning` (por defecto), `danger`, `success`, `info` |
| `titulo` | Opcional, `strong text-heading` |
| `texto` | Opcional, `p text-body mt-1` |
| `role` | Por defecto `alert` en danger y warning, `status` en info y success. `role=""` no es válido: pasá el que corresponda |
| `icono` | Opcional. Nombre Font Awesome sin prefijo (`triangle-exclamation`). Se dibuja a la izquierda a 18 px (`text-lg`), con `aria-hidden="true"` y el color del tono. En `info` reemplaza al `circle-info` |
| `accion_url` + `accion_texto` | Opcionales y **van juntos**: link subrayado a la derecha dentro del bloque («Resolver», «Ver legajo»). Con solo uno de los dos no se dibuja el link y el render es el de siempre |

Render: `rounded-lg bg-{tono}-soft border border-{tono}-subtle p-4 text-sm`.

Con `icono` o con acción completa el bloque pasa a `flex items-start gap-3` (ícono · cuerpo `flex-1` · link
`shrink-0`); sin ellos el HTML es idéntico al anterior. El tono, el `role` y el escapado no cambian.

## Cuándo cada tono

- **danger:** la acción está bloqueada o algo falló.
- **warning:** advertencia que **no** impide seguir. Encabezado «Atención» y el botón de la
  acción **habilitado**: bloqueo y advertencia se distinguen por el encabezado y por si la acción
  está disponible, no por el color.
- **success:** confirmación persistente de un resultado (un envío que salió bien).
- **info:** nota explicativa dentro de un modal o de una card.

## Dónde va

- Debajo del encabezado de la página cuando condiciona toda la pantalla.
- Dentro de la card o del modal cuando explica ese bloque.
- El resultado de un proceso (por ejemplo, una carga de padrón) se muestra **fijo** con esta
  pieza dentro de su card, no solo como toast.

## Deuda conocida

El tono `info` no tiene par de tokens `bg`/`border` compilado: reusa la nota informativa canónica
con estilos en línea sobre `--bg-info-soft`, `--color-brand-200` y `--text-fg-info`, con ícono
`fa-circle-info`. Es deuda declarada en la pieza; **no se crean tokens nuevos** ni se copia ese
markup a mano: se usa el include.

## Prohibido

- Cajas de aviso escritas a mano con utilidades sueltas.
- Usar el color como único indicador (sin título ni texto).
- Un aviso efímero donde hace falta uno persistente: para avisos efímeros está `window.toast`.
