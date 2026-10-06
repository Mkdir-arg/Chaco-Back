# Revisión independiente — Alta de tipo de prestación (Merenderos)

Agente `chaco-design-reviewer`, sesión aparte de la que escribió el template.

**Dictamen: Aprobado, sin cambios requeridos.**

## Molde y marcadores
- Golden declarada `becas/config/segmento_form.html` — figura en la tabla `## Arquetipos`: **sí**.
- `--arquetipo formulario`: OK · `--ratchet`: 0 nuevos · `compile_templates.py`: 199 / 0 errores ·
  `check_design_agent.py --changed`: OK.
- Las hermanas (`merenderos/entrega_form.html`, `solicitud_form.html`) se leyeron solo para confirmar que **no** se
  usaron de molde: tienen el campo escrito a mano, label `font-semibold`, botón sin la variante completa y `<h1>`
  propio con «← Volver» de texto — justo los antipatrones que la ficha prohíbe.

## El punto que la línea base falló
**L21: `{% for field in form %}{% include "programas/becas/_field.html" %}{% endfor %}`.** El campo se renderiza con el
parcial canónico **incluido**, no reimplementado en línea. En la línea base el agente copió ese markup a mano y lo
justificó («para no acoplar Merenderos a una ruta de Becas»); el núcleo nuevo declara el parcial **transversal** y el
agente lo incluyó sin dudar. Es el desvío que ninguna regla P1 atrapaba (la pantalla daba 0 P1 igual) y que la ficha
cerró.

## Novedades
Ninguna. El esqueleto es copia literal de la golden; cambia solo dominio (módulo, entidad, URL
`merenderos:tipos_prestacion`, textos). No hay `{% load rbac %}` porque no se usa `puede` — en la golden ese `load`
solo servía para el botón «Crear coordinador», que es de dominio y se omitió bien.

## Checklist de la ficha
`{% csrf_token %}` + `method="post"` (L13-14) · campos solo desde el form (L21) · pie Cancelar (`btn-tertiary btn-base`)
→ Guardar (`btn-brand btn-base`) en ese orden (L23-24) · título con `yesno` alta/edición y `volver_url` a la lista
(L7-9) · errores generales arriba con `role="alert"` (L16-19) · ícono con `aria-hidden` (L24). Ningún `<h1>` propio,
«← Volver» de texto, `class="nodo-field"` a mano, `<style>`, `style=`, paleta cruda ni SVG inline.

## Dominio
«tipo de prestación», «prestaciones mensuales», «merenderos»: vocabulario del perfil de Merenderos. Cero vocabulario de
Becas (convocatoria, segmento, cupo, beneficiario, relevamiento, SIIS).

## Hallazgo abierto para quien escriba el backend (fuera del template)
No existe el modelo `TipoPrestacion`: hoy el concepto vive como `TextChoices Servicio` dentro de `PrestacionDiaria`
(`programas/models/__init__.py:1077-1081`). Tampoco hay capacidad de configuración en el catálogo de Merenderos
(`core/rbac.py:71-84`, solo `merendero.ver/crear/editar/validar/entregar`). Las dos cosas son decisión de backend/PM.
