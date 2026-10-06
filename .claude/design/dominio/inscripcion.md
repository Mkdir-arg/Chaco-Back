# Dominio · Inscripción pública (formulario por diseño, paso 2)

**Clasificación:** Canónico reutilizable, dentro de su superficie. Es la única superficie pública
viva del portal: se llega por el link que envía el programa, sin cuenta ni contraseña.
**Evidencia:** `portal/templates/portal/inscripcion/paso2.html`,
`static/custom/js/nodo-formulario.js` sobre `static/custom/js/nodo-condiciones.js`,
`portal/templates/portal/inscripcion/base_inscripcion.html` (shell: ficha `shells.md`).

## Contrato del paso 2

El paso 2 **no tiene bloques fijos en el template**: recorre `form.grupos()` y por cada ítem rinde

- un `<section data-item="<clave>">` para el grupo, con `h2` en mayúsculas de 12 px y subtítulo
  `text-xs`;
- un `<p data-item>` para los párrafos;
- un par etiqueta + valor cuando el dato ya vino del paso 1;
- o `label` + control `nodo-field` para lo que se pide.

Contrato del JS: cada ítem lleva `data-item` con su clave y los ítems planos viajan en
`#formulario-items` (`json_script`). Al ocultar un ítem, el JS pone `hidden` en el contenedor y
`disabled` en sus controles, para que no viajen en el POST.

**Sin JavaScript el formulario se muestra completo y se envía igual:** el servidor vuelve a
evaluar las condiciones y es la autoridad. El espejo de condiciones del cliente es una comodidad,
nunca una validación.

Mantiene el shell de inscripción, el buscador con píldoras (`static/custom/js/nodo-buscador.js`)
para los selectores largos y los tokens del portal. Light-only.

## Reglas de la superficie

- Un solo `<h1>`, el del `panel_titulo` del shell.
- El stepper se completa por página con `paso_activo` 1, 2 o 3; las pantallas de resultado
  (`portal/templates/portal/inscripcion/confirmacion.html`,
  `portal/templates/portal/inscripcion/ya_inscripto.html`,
  `portal/templates/portal/inscripcion/no_disponible.html`,
  `portal/templates/portal/inscripcion/demasiados_intentos.html`) lo dejan vacío.
- No se cargan Alpine, Font Awesome, los toasts ni el modal del portal: los avisos de esta
  superficie se renderizan en el HTML.
- Nada de `{% url 'portal:ciudadano_…' %}`: esas rutas no existen y revientan con
  `NoReverseMatch`.
- El `csrfmiddlewaretoken` lo refresca el shell; no se agrega otro mecanismo.

## Prohibido

- Copiar el markup del backoffice (tabla densa, `page_header`, botones de ícono): es otra
  superficie, con otro shell y otros tokens.
- Un tercer script de terceros: el shell ya define cuáles entran y por variable de entorno.
- Validar en el cliente y confiar: la autoridad es el servidor.
