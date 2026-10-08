# Componente · Solapas (tabs) del backoffice

**Clasificación:** Canónico reutilizable.
**Evidencia (markup completo, con ARIA):**
`programas/templates/programas/becas/cupo/segmento_detail.html`.
**Secundarias:** `programas/templates/programas/becas/config/programa_detail.html` (carga diferida
y solapa condicionada por permiso) y
`programas/templates/programas/becas/relevamientos/convocatoria_detail.html` (deep link; ya
tiene ARIA desde FE-24).

Una acción que el servidor va a rechazar **no se dibuja**, viva en el panel que viva: en
`convocatoria_detail.html` los cuatro botones de export van bajo el mismo flag que decide la
solapa Reportes, aunque uno de ellos esté en el panel de Beneficiarios (Cambio 193, ronda 2).

No hay include ni tag: las solapas se clonan de la golden de detalle con su ARIA.

## Contrato

```django
<div class="space-y-5" x-data="{ tab: new URLSearchParams(window.location.search).get('tab') || 'uno' }">
  <div class="bg-white rounded-xl border border-base shadow-sm overflow-hidden">

    <div class="border-b border-base flex gap-1 px-2 flex-wrap" role="tablist" aria-label="Secciones del segmento">
      <button @click="tab='uno'" type="button" role="tab" id="tab-uno" aria-controls="panel-uno"
              :aria-selected="tab==='uno'"
              class="px-4 py-3 text-sm border-b-2 -mb-px transition flex items-center gap-1.5 whitespace-nowrap"
              :class="tab==='uno' ? 'text-fg-brand border-brand font-bold' : 'text-body-subtle border-transparent hover:text-body font-medium'">
        <i class="fas fa-users" aria-hidden="true"></i> Uno
        <span class="badge" :class="tab==='uno' ? 'badge-info' : 'badge-gray'">{{ n_uno }}</span>
      </button>
    </div>

    <div x-show="tab==='uno'" x-cloak role="tabpanel" id="panel-uno" aria-labelledby="tab-uno">…</div>
  </div>
</div>
```

- Las solapas van **dentro de una surface**, como primera fila.
- Barra: `border-b border-base flex gap-1 px-2 flex-wrap` con `role="tablist"` y `aria-label`.
- Ítem: `px-4 py-3 text-sm border-b-2 -mb-px transition flex items-center gap-1.5`; activo
  `text-fg-brand border-brand font-bold`; inactivo
  `text-body-subtle border-transparent hover:text-body font-medium`.
- Cada botón: `type="button"`, `role="tab"`, `id="tab-<x>"`, `aria-controls="panel-<x>"` y
  `:aria-selected`.
- Cada panel: `role="tabpanel"`, `id="panel-<x>"`, `aria-labelledby="tab-<x>"`, con `x-cloak`.
- Contadores: `badge` con variante **declarada** (`badge-info` en la activa, `badge-gray` en las
  demás), nunca utilidades de color sueltas.
- Deep link por querystring:
  `tab: new URLSearchParams(window.location.search).get('tab') || '<default>'` en el `x-data`.

## Teclado

Lo da `static/custom/js/nodo-tabs.js`, que el shell carga **una sola vez** para todo el
backoffice: ← → mueven el foco con vuelta circular, Home/End van a los extremos, y el
`tabindex` itinerante deja tabulable solo la solapa activa (Tab entra y sale de la barra en
un paso). Activa la solapa disparando su `click()`, así que no necesita saber nada del
estado de la pantalla; lee `aria-selected` para repartir el `tabindex` y un
`MutationObserver` lo recalcula cuando ese atributo cambia.

**Una pantalla no escribe su propio manejo de teclado.** Lo único que tiene que hacer es
declarar el ARIA del contrato de arriba.

## Reglas

- **Una barra de solapas solo contiene solapas.** Lo que abre **otra pantalla** va como acción
  del encabezado (`btn-nodo btn-secondary btn-sm`), no como una solapa con `ml-auto`.
- Solapa con carga diferida: su `@click` agrega `$dispatch('<evento>')` y el JS escucha ese
  evento en `window`.
- Solapa condicionada por permiso: el mismo `{% if %}` envuelve **el botón y el panel**.
- Si una solapa tiene listado paginado, ver la limitación de `components/_paginacion.html` en su
  ficha: una sola lista paginada por pantalla.

## Prohibido

- Solapas sin `tablist`/`tab`/`aria-controls`/`tabpanel`/`aria-labelledby`.
- `<a href="#…">` como solapa.
- Calcular el contenido de todas las solapas en la vista cuando el volumen puede crecer.
- Perder la solapa activa al paginar o exportar: viaja en la querystring.
- Un handler de `keydown` propio sobre la barra de solapas: ya está en el shell.
