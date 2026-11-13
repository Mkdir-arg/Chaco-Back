# Componente · Tabla de conciliación y celda de diferencia (`components/_celda_diferencia.html`)

**Clasificación:** Canónico reutilizable. La tabla «enviado / recibido / diferencia» **no es una tabla
nueva**: es la tabla densa canónica (`tabla.md`) con una columna cuya celda dibuja esta pieza.
**Evidencia:** `templates/components/_celda_diferencia.html`, el filtro `menos` de
`core/templatetags/nodo_ui.py`, `core/tests/test_nodo_ui_emergencia.py` (`CeldaDiferenciaTest`).
**Consumidor previsto:** el detalle de una entrega de kits de Emergencia (ítem · enviado · recibido ·
diferencia).

## Invocación

```django
<div class="overflow-x-auto">
  <table class="w-full border-collapse">
    <thead>
      <tr class="nodo-thead-row">
        <th class="nodo-th">Ítem</th>
        <th class="nodo-th text-right">Enviado</th>
        <th class="nodo-th text-right">Recibido</th>
        <th class="nodo-th">Diferencia</th>
      </tr>
    </thead>
    <tbody>
      {% for linea in lineas %}
      <tr class="hover:bg-secondary">
        <td class="nodo-td text-heading font-medium">{{ linea.item }}</td>
        <td class="nodo-td text-right">{{ linea.cantidad_enviada }}</td>
        <td class="nodo-td text-right">{{ linea.cantidad_recibida|default_if_none:"—" }}</td>
        <td class="nodo-td">{% include "components/_celda_diferencia.html" with enviada=linea.cantidad_enviada recibida=linea.cantidad_recibida only %}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
```

La tabla va dentro de la card de la lista, con el contrato completo de `tabla.md`. La pieza es **el contenido
de la celda**: el `<td class="nodo-td">` lo escribe el consumidor.

| Parámetro | Efecto |
|---|---|
| `enviada` | Entero: la cantidad que salió |
| `recibida` | Entero: la cantidad que se recibió. `None` = todavía no se recibió |

## Qué dibuja

| Caso | Render | Texto |
|---|---|---|
| `recibida` menor que `enviada` | `badge badge-danger` | «−2 · faltan» («−1 · falta») |
| `recibida` mayor que `enviada` | `badge badge-warning` | «+1 · de más» |
| iguales | `text-body-subtle`, sin badge | «sin diferencia» |
| `recibida` es `None` | raya `aria-hidden` + `sr-only` | «—» («Todavía no recibida» para el lector de pantalla) |
| algún valor no es un entero | raya `aria-hidden` + `sr-only` | «—» («Sin dato») |

## Reglas

- **Lo único que hace la pieza es la resta** `recibida − enviada`, con el filtro `menos` (devuelve `None` si
  alguno de los dos no es un entero). Sumar, totalizar o decidir el estado de la entrega es del servicio.
- El signo y la palabra van siempre en texto: el color solo resalta la fila que difiere. Por eso «sin
  diferencia» no lleva badge: en una entrega completa no hay nada que resaltar.
- Un dato que falta se dibuja como raya, **nunca** como «sin diferencia».
- Lo que llegó de más también es una diferencia (`warning`): no se oculta ni se pinta como éxito.

## Prohibido

- Una tabla propia para la conciliación (clases de celda sueltas, colores por fila): es la tabla canónica.
- Pintar la fila entera de rojo, o usar solo el color del número para marcar la diferencia.
- Calcular la diferencia en el template del consumidor (`{% if a != b %}`) o repetir el badge a mano.
- Usar el filtro `menos` para aritmética de negocio: existe para presentar esta diferencia.
