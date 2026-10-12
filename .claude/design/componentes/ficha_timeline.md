# Componentes · Línea de tiempo y sección de ficha

**Clasificación:** Canónico reutilizable.
**Evidencia:** `templates/components/_linea_tiempo.html`, `templates/components/_ficha_seccion.html`,
`templates/components/_ficha_avance.html` (interno), `static/custom/css/nodo-ficha.css`,
`core/tests/test_nodo_ui_piezas.py` (`LineaTiempoTest`, `FichaSeccionTest`).
**Consumidor de referencia:** `programas/templates/programas/dispositivos/estadia/revision_referencia.html`
(arquetipo Revisión, `arquetipos/revision.md`).

## Línea de tiempo

```django
{% include "components/_linea_tiempo.html" with eventos=eventos %}
```

`eventos`: lista de dicts, ya ordenada por la vista. Cada uno: `cuando` (metadato ya formateado),
`titulo`, y opcionales `detalle`, `tono` (`warning`, `danger`, `success`; sin él, marca), `badge` +
`badge_tono` (`warning` por defecto). Sin eventos dibuja `_estado_vacio` (`vacio_titulo`, `vacio_texto`).
Riel de 2 px (`border-base`), punto de 10 px con borde tonal. El tono refuerza; lo que pasó va en el título.

**La lista llega acotada.** El componente dibuja todos los eventos que recibe y una estadía larga trae
cientos: **recortar es responsabilidad de la vista** (las últimas N, más un enlace «Ver todo» cuando
hay más). El componente no pagina.

**No lleva contenido rico.** Cada evento es texto: `detalle` es una línea, no un slot. Si un evento
necesita mostrar algo adentro —una grilla de fotos, una tabla—, **no se mete marcado en `detalle`**
(va escapado, y si se desactiva el escape se abre un agujero con texto que carga un usuario). Ese
caso todavía no tiene componente: se resuelve agregándole un slot de cuerpo acá, en una task propia,
y hasta entonces el contenido va en una card aparte debajo de la línea de tiempo.

## Sección de ficha

```django
{% include "components/_ficha_seccion.html" with codigo="salud" titulo="9 · Salud" avance=60 sensibilidad="Sensible · salud" sensibilidad_tono="warning" campos=campos %}
```

| Parámetro | Efecto |
|---|---|
| `codigo` | Obligatorio y único en la página: arma `ficha-<codigo>` (panel y `aria-controls`) |
| `titulo` | Obligatorio |
| `avance`, `avance_tono` | 0-100 o `None` (sin medidor); `brand` o `warning`. **Los decide la vista** |
| `sensibilidad`, `sensibilidad_tono` | Badge («Sensible · salud»), `warning` o `danger` |
| `completar_url` | Link «completar» junto al avance, con el título en `sr-only` |
| `abierta` | `False` la deja plegada al cargar; por defecto abierta |
| `campos` | Lista de `{etiqueta, valor, estado}`; `estado`: vacío, `falta` (rojo) o `calculado` (gris) |
| `vacio_texto` | Texto cuando no hay `campos` |
| `bloqueada`, `motivo`, `completa` | Sección rayada: sin campos, sin plegar; «La completa <completa>» |

Plegable con Alpine (`aria-expanded` + `aria-controls`). El medidor lleva `role="progressbar"` y el
porcentaje escrito. Las dos clases propias, `.nodo-ficha-bloqueada` (rayado) y `.nodo-ficha-medidor` (relleno, `style="--avance:N%"`), las carga el shell
desde `nodo-ficha.css`; ninguna pantalla las escribe a mano.

## Reglas

- **Bloquear no es ocultar.** Una sección que el rol no lee se muestra con avance y responsable; los
  datos nunca llegan al template (la vista no los pasa).
- La vista decide `bloqueada`, el avance y su tono; el componente no evalúa permisos ni umbrales.
- Va dentro de una card, apilada con `space-y-3`. Sin cards anidadas.

## Prohibido

- Armar la línea de tiempo o la sección a mano, o copiar el rayado.
- Emoji (🔒, 📎): el candado es `fa-lock` con `aria-hidden`.
- `<details>` o JS propio para plegar: lo hace Alpine, ya cargado por el shell.
