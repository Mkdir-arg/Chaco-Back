# Componente · Hoja de impresión de un tablero (`nodo-impresion.css`)

**Clasificación:** Canónico reutilizable.
**Evidencia:** `static/custom/css/nodo-impresion.css`; primer consumidor, E8 «Situación» de Emergencia
(`programas/templates/programas/emergencia/situacion/situacion.html`).
**Arquetipo:** `arquetipos/dashboard.md`, sección *Impresión*: esta es la pieza que esa sección pedía construir con
el primer tablero que imprimiera.

## Cuándo

Un tablero de programa que se lleva a una reunión: el papel tiene que salir sin el shell y sin lo que solo sirve en
pantalla, con **todo** el panel Resumen aunque se esté mirando otra solapa. No es para imprimir un listado o un
detalle (eso queda para el navegador) ni para exportar (eso es un CSV o un PDF del servidor).

## Contrato

La pantalla carga la hoja en su bloque `page_css` (el shell **no** la carga):

```django
{% block page_css %}<link rel="stylesheet" href="{% static 'custom/css/nodo-impresion.css' %}">{% endblock %}
```

y marca sus partes con cuatro clases gancho:

| Clase | Efecto |
|---|---|
| `nodo-no-imprimir` | No sale en el papel: barra de filtros, barra de solapas, paneles que no se imprimen (mapa, abastecimiento), enlaces de trabajo |
| `nodo-solo-impresion` | Sale **solo** en el papel (oculto en pantalla): el subtítulo con los filtros aplicados, el pie «Documento de trabajo · … · impreso el …», la tabla completa que reemplaza a una paginada o al mapa |
| `nodo-impresion-panel` | El panel que se imprime siempre: le gana al `display:none` en línea de `x-show` y a `[x-cloak]` |
| `nodo-impresion-desplegar` | Un `<details>` que sale abierto y sin su `summary` («Cómo se calcula») |

Además, en `@media print` la hoja: pone A4 apaisada con margen de 12 mm; oculta el sidebar (`aside`), la barra
superior del shell, los elementos `fixed` (toasts, modales) y la acción del hero (`.nodo-hero__accion`); saca el
corrimiento del sidebar (`lg:pl-*`) y el padding de `main`; evita cortar un `section` entre hojas cuando entra en una,
y fuerza `print-color-adjust: exact` para que el hero, los badges y las barras no salgan en blanco.

El botón «Imprimir» de la pantalla es `btn-nodo btn-secondary btn-sm` con `@click="window.print()"` y `x-cloak` (sin
JS no se dibuja; Ctrl+P sigue andando). Va con la barra de filtros, así que no sale en el papel.

## Reglas

- **Ningún color ni medida visual nueva**: la hoja solo oculta, muestra y quita espacio del shell.
- El texto que sale solo en el papel lo arma la vista (alcance, fecha); el template no calcula.
- `::details-content` abre el `<details>` en Chrome ≥ 131 y Firefox ≥ 143; en navegadores más viejos «Cómo se
  calcula» sale plegado (límite conocido, como la tabla de `_barras_pareadas`, que la abre `nodo-tables.js`).
- Un mapa no se imprime (los mosaicos a medio cargar no son confiables): se oculta con `nodo-no-imprimir` y la tabla
  equivalente lo reemplaza.

## Prohibido

- Un `<style>` o `@media print` propio en la pantalla, o reusar `.no-print` de `responsive.css` (conflictivo) o el
  `dash-no-print` de Becas (local).
- Cargar la hoja desde el shell: solo la pantalla que imprime la pide.
- Usar `nodo-solo-impresion` para esconder datos de pantalla: lo que sale en papel también tiene que estar en
  pantalla (la tabla completa repite filas que la pantalla pagina, nada más).
