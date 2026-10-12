# Componente · Tarjeta de turno y entradas de bitácora (`components/_turno_tarjeta.html`, `components/_entradas_bitacora.html`)

**Clasificación:** Canónico reutilizable. Dos includes del registro diario de un dispositivo: la cabecera
de cada turno y la lista de anotaciones de un turno.
**Evidencia:** `templates/components/_turno_tarjeta.html`, `templates/components/_entradas_bitacora.html`,
`core/tests/test_nodo_ui_lote_c.py`.
**Consumidores de referencia:** ninguno todavía; lo usará la bitácora del turno (mockup P10).

## Invocación

```django
<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
  {% for turno in turnos %}{% include "components/_turno_tarjeta.html" with turno=turno %}{% endfor %}
</div>
{% include "components/_entradas_bitacora.html" with entradas=entradas_del_turno total=turno_abierto.entradas_total %}
```

La tarjeta va una por turno (la grilla es de la pantalla); las entradas van dentro de la card «Turno
Tarde · entradas», debajo de su encabezado.

| Parámetro | Efecto |
|---|---|
| `turno` | Dict armado por la vista: `nombre`, `estado`, y opcionales `horario`, `tono`, `detalle`, `activo`, `sin_abrir`, `acciones` (lista de `url`, `texto`, `variante`) |
| `entradas` | Lista de dicts (no queryset), de la más nueva a la más vieja: `hora`, `categoria`, y opcionales `tono`, `titulo`, `texto`, `autor`, `automatica`, `version` |
| `total` | Opcional: cantidad real de entradas si la vista mandó menos |

## Quién decide qué

- **El estado, la categoría y el tono los decide la vista.** El template solo traduce `tono` a la variante de
  badge: `success`, `info`, `warning`, `danger`, `brand`. Un tono desconocido, o ninguno, dibuja el badge neutro
  (`badge-gray`) y el ícono genérico; no se rompe. No hay reglas de dominio en el template.
- **El color no es el único portador.** El badge de la tarjeta lleva el texto del estado; el de cada entrada
  lleva el texto de la categoría y un ícono por tono (`fa-circle-check`, `fa-circle-info`,
  `fa-triangle-exclamation`, `fa-circle-exclamation`, `fa-flag`), todos `aria-hidden`.
- **El texto lo escribe un usuario:** se imprime con autoescape y `linebreaksbr` (respeta los saltos de línea,
  no deja pasar HTML). No hay `|safe` ni `{% autoescape off %}`.
- Las acciones de la tarjeta (`+ Novedad`, `Cerrar turno`) las arma la vista según capacidades: la pieza no
  decide quién puede qué y solo dibuja los enlaces que recibe. Son enlaces a una URL; lo que pida confirmación
  o motivo abre su modal desde la pantalla.

## Tope

Una bitácora crece sin techo: un turno largo tiene muchas entradas y un dispositivo tiene turnos todos los días.
**El recorte lo hace la vista**: manda las entradas más recientes del turno (por ejemplo las últimas 50) junto con
`total`, la cantidad real, y la lista completa pasa por paginación o por la pantalla del turno. Como red de
seguridad la pieza dibuja **hasta 100 entradas** y avisa «Mostrando N de M entradas». Un queryset sin acotar no
es contrato válido de esta pieza. Una lista vacía muestra el estado vacío canónico.

## Diferencias con el mockup

- La fila no usa la grilla `56px 110px 1fr` (valor arbitrario fuera de la lista blanca): son tres columnas en
  `flex` con `w-12`, `w-28` y el cuerpo `flex-1`.
- El turno activo marca el borde con `border-brand` y `aria-current`; no dibuja el anillo de 3 px, que no tiene
  utilidad en la lista blanca.
- El turno sin abrir no baja la opacidad (.65): usa fondo `bg-secondary`, para que el texto conserve el contraste.
- El badge de la entrada suma un ícono, que el mockup no dibuja.
- El 📎 de «adjunto» y el enlace «corregir» no son parte de la pieza (emoji fuera de Font Awesome; la corrección
  la define la pantalla). Las etiquetas extra como «Seguimiento abierto» tampoco.

## Prohibido

- Resolver estado, categoría o tono en el template, o mandar un queryset en `entradas`.
- `|safe` o autoescape apagado sobre el texto de una entrada.
- Mandar toda la bitácora de un turno sin recorte ni `total`.
- Usar solo el color para distinguir la categoría.
