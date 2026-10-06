# Revisión independiente — Listado de entregas (Merenderos)

Agente `chaco-design-reviewer`, sesión aparte de la que escribió el template (sin `Edit` en el frontmatter).

**Dictamen: Aprobado.**

## Molde y marcadores
- Golden declarada `becas/revision/personas_list.html` — figura en la tabla `## Arquetipos` del núcleo: **sí**.
- `--arquetipo listado`: OK · `--ratchet`: 0 nuevos · `compile_templates.py`: 199 / 0 errores ·
  `check_design_agent.py --changed`: OK.
- De la hermana (`merenderos/list.html`, legacy: `max-w-6xl`, `<h1>` a mano, tabla sin `nodo-th`/`nodo-td`) se tomó
  **solo dominio**: nombres de campo (`fecha`, `cantidad_kits`, `servicio`, `merendero.zona/barrio`), el patrón de
  filtro por rango `desde`/`hasta` y la ruta `merenderos:detalle`. Nada de estructura, clases ni JS.

## Novedades
Ninguna. El `{% include "programas/merenderos/_estado_badge.html" %}` es el esqueleto literal de la ficha con
`<modulo>` completado, no una pieza nueva.

## Hallazgos (ninguno bloqueante)
1. *(informativo)* La acción de fila abre el **merendero**, no la entrega, porque no existe `entrega_detalle` en
   `programas/merenderos_urls.py`. Decisión de dominio razonable; migrar el link si se agrega ese detalle.
2. *(a resolver en la vista)* El template usa `entrega.estado`, pero `EntregaMercaderia` solo tiene el booleano
   `anulada`. La vista tiene que exponer `.estado` sin abrir una consulta por fila.
3. *(dependencia sin crear)* Falta `programas/templates/programas/merenderos/_estado_badge.html`. Al crearlo hay que
   sumar su evidencia a la fila «Mapa de estados por módulo» del núcleo.
4. *(dependencia sin crear)* La URL `merenderos:entregas` todavía no existe — coherente con que en este ejercicio la
   vista y las URLs solo se describen.

## Desarrollo front
`select_related("merendero")` es obligatorio (cada fila toca `merendero.nombre/zona/barrio`); `paginate_by=25`
declarado; sin `|length` sobre querysets; la pantalla es solo GET, no aplica CSRF ni confirmación.
