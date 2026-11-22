# Componente · Índice de secciones de un modal (`components/_indice_secciones.html`)

**Clasificación:** Canónico reutilizable. Un índice de botones para moverse por las secciones de un modal largo, con
el panel ancho (`max-w-4xl`) del arquetipo Modal.
**Evidencia:** `templates/components/_indice_secciones.html`, `static/custom/js/nodo-indice-secciones.js`,
`core/tests/test_nodo_ui_piezas.py` (`IndiceSeccionesTest`), `core/tests/test_nodo_indice_secciones.py` (harness de
`node`) y `programas/tests/test_dispositivos_formulario_estadia.py` (`EgresoConIndiceDeSeccionesTests`).
**Consumidor de referencia:** «Registrar egreso» de Dispositivos cuando el formulario del tipo trae 2 o más grupos (con 1 las secciones van sin índice):
`programas/templates/programas/dispositivos/_form_egreso.html` (lo comparten P4, `legajo/detail.html`, y P7,
`estadia/detalle.html`).

## Cuándo usarla

- Un modal con **varias secciones largas** que se leen de corrido: la primera es fija y las demás vienen de un
  formulario armado por el constructor, así que no se sabe cuántas son.
- **No** es `tabs.md`: las solapas ocultan los paneles y un error de campo quedaría en uno que no se ve. Acá todas las
  secciones son un solo cuerpo que scrollea, y el índice solo lleva a cada una. Tampoco es `stepper.md` (pasos en
  orden, con validación por paso) ni `chips_enlace.md` (recarga la pantalla).
- Con menos de 2 secciones no se dibuja: el modal queda con el cuerpo y el ancho de siempre.

## Invocación

```django
<div class="px-6 py-6 overflow-y-auto min-h-0" data-indice-cuerpo>
  <div class="flex flex-col lg:flex-row gap-5 lg:gap-8">
    {% include "components/_indice_secciones.html" with nombre="Secciones del egreso" %}
    <div class="flex-1 min-w-0 space-y-5">
      <section id="…-0" tabindex="-1" aria-labelledby="…-0-titulo" data-indice-seccion data-indice-titulo="Título" class="space-y-5 focus:outline-none">
        <h3 id="…-0-titulo" class="text-sm font-bold text-heading">Título</h3>
        …
      </section>
    </div>
  </div>
</div>
```

| Parte | Contrato |
|---|---|
| `nombre` | Obligatorio. `aria-label` del `<nav>` |
| `data-indice-cuerpo` | El contenedor que scrollea (el cuerpo del modal); el JS lo busca con `closest` |
| `data-indice-seccion` + `data-indice-titulo` | Una por sección: la sección lleva `id`, `tabindex="-1"` (recibe el foco) y el título que el JS escribe en su entrada |
| `nodo-indice-secciones.js` | Cargarlo en `customJS`; al cargar monta todos los `[data-indice-secciones]`. `NodoIndiceSecciones.montar(nav)` lo monta a mano |

El panel del modal pasa de `max-w-[560px]` a `max-w-4xl` **con la misma condición** que dibuja el índice (la
pantalla la repite en la clase del panel; el cuerpo, en el `{% if %}` del parcial).

## Comportamiento

- Las entradas son `<button type="button">`: Tab llega, Enter o Espacio llevan a la sección (`scrollIntoView`, o
  inmediato con `prefers-reduced-motion`) y le dan el foco; el foco visible es `focus-visible:ring-2 focus-visible:ring-brand`.
- La sección que se lee queda con `aria-current="true"` y el estilo de activa (`bg-brand-soft text-fg-brand font-bold`);
  sigue al scroll del cuerpo y, al llegar al fondo, queda la última.
- Una sección `hidden` (por una condición del formulario) sale del índice; con menos de dos visibles el `<nav>` se
  oculta.
- Una sección con un campo en error (`aria-invalid="true"` o un `[data-error]` visible con texto) marca su entrada con el
  badge **«Revisar»**: el color nunca es el único portador. El error del 400 sigue apareciendo en su campo y el handler
  de `_ajax_js.html` le da el foco, que lleva el scroll a esa sección aunque no se viera.
- A partir de `lg` el índice va a la izquierda y fijo (`lg:sticky lg:top-0`); debajo de `lg` se apila arriba con las
  entradas en renglones que se parten (`flex-wrap`), sin scroll horizontal.
- Los títulos se escriben con `textContent`, nunca con `innerHTML`.

## Prohibido

- Un `<style>`, un `style=` o clases de paleta cruda: la pieza usa solo tokens y utilidades compiladas.
- Reescribir el índice a mano en una pantalla, o usar solapas (`role="tab"`) para lo que es una sola lectura de corrida.
- Entradas que son enlaces `<a>`: el shell les fuerza el color de marca y navegarían con el hash.

## Detalles de uso

- Clic en una entrada: queda activa al instante y el seguimiento del scroll no la pisa mientras dura el desplazamiento; la
  persona retoma el control con `wheel`, `touchmove`, `keydown` o `mousedown` en el cuerpo.
- Con el cuerpo arriba de todo, o sin alto (modal cerrado al montar), se marca la primera sección.
- Montar dos veces no duplica las entradas (`data-indice-montado`).
- Debajo de `lg` cada entrada mide al menos 44 px (`min-h-11`); desde `lg`, `lg:min-h-0`.
