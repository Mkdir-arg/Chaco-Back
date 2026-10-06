# Revisión independiente — Detalle de cama (Dispositivos)

Agente `chaco-design-reviewer`, sesión aparte de la que escribió el template. Es la pantalla que falló en la línea
base: el agente anterior clonó la hermana del módulo y heredó su deuda entera.

**Dictamen: Aprobado** (un hallazgo menor, no bloqueante).

## Molde y marcadores
- Golden declarada `becas/cupo/segmento_detail.html` — figura en la tabla `## Arquetipos`: **sí**.
- **La deuda de la hermana no se heredó.** `dispositivos/legajo/detail.html` tiene `<style>[x-cloak]` local (L9),
  «← Volver» como link de texto (L13), `<h1>` propio (L17), `style="background:var(--bg-primary)"` (L44 y L57) y
  solapas **sin** `id`/`aria-controls`/`aria-labelledby` (L60-81). **Ninguno** aparece en `cama_detail.html`: usa
  `{% page_header %}` (L11), no tiene `<style>` ni `style=`, y cada tab/panel trae `id`, `aria-controls`,
  `:aria-selected`, `role="tabpanel"` y `aria-labelledby` (L35-54, 58, 95, 141).
- De la hermana se tomó solo dominio: `dispositivos:detalle`, `dispositivos:cama_editar`, el parcial
  `_cama_estado_badge.html` y el vocabulario (cama, dispositivo, admisión, parte diario).
- `--arquetipo detalle`: OK · `--ratchet`: 0 nuevos · `compile_templates.py`: 0 errores ·
  `check_design_agent.py --changed`: OK.

## Novedades
Ninguna. Todos los includes (`_stat_card`, `_estado_vacio`, `_paginacion`, `_cama_estado_badge`) se usan con su
contrato existente y sin parámetros nuevos.

## Hallazgos
1. *(moderado, no bloqueante)* **L142: `{{ partes|length }}`** sobre un queryset, para un texto informativo, cuando el
   contador ya existe como variable de vista (`n_partes`, usado en la solapa L53). Contradice la regla «sin `|length`
   sobre querysets» del método del revisor y la ficha `stat_card.md`. Corrección: `{{ n_partes }}`.
   **Ninguna regla P1 de `design_audit` lo atrapa** — y ninguna puede: es una regla de desarrollo, no de token visual.
   Lo cazó el revisor, que es su lugar en el sistema.
2. Sin otros hallazgos: badge antes de las acciones en el header (L13-18), stat cards con tono por significado
   (L24-28), avatares `bg-brand-soft text-fg-brand` sin gradiente (L112, D5), columna de acciones con `sr-only`
   (L104, L151) y **una sola** lista paginada por pantalla — evita la deuda de triple paginación que tiene la propia
   golden.

## Desarrollo front
`movimientos` paginado, `partes` con tope explícito `[:15]`; `select_related` descripto para las dos listas;
`puede_editar` resuelto en la vista con `puede_operar_dispositivo()` → `core.rbac.puede()` (mejor que la hermana, que
lo resuelve con un templatetag dentro del template). Al escribir la vista: `n_movimientos` tiene que ser
`movimientos.paginator.count`, no el conteo de la página actual.
