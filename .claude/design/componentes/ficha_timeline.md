# Componentes · Línea de tiempo y sección de ficha

**Clasificación:** Canónico reutilizable.
**Evidencia:** `templates/components/_linea_tiempo.html`, `templates/components/_ficha_seccion.html`,
`templates/components/_ficha_avance.html` (interno), `static/custom/css/nodo-ficha.css`,
`core/tests/test_nodo_ui_piezas.py` (`LineaTiempoTest`, `FichaSeccionTest`).
**Consumidor de referencia:** `programas/templates/programas/dispositivos/estadia/revision_referencia.html`
(arquetipo Revisión, `arquetipos/revision.md`).

La bajada de esa golden muestra el DNI con el filtro de presentación `nodo_ui.dni`
(`12.345.678`); controles y búsquedas mantienen el valor original. Contrato del filtro
en `componentes/tabla.md`.

En `_ficha_seccion`, un campo con `formato: "dni"` presenta `valor` con ese mismo
filtro, independientemente de su etiqueta. El productor marca el campo; sin `formato`,
vacío o desconocido, conserva su representación y el HTML. La lista de campos no se modifica.
Lo verifica `FichaSeccionTest` en `core/tests/test_nodo_ui_piezas.py`.

## Línea de tiempo

```django
{% include "components/_linea_tiempo.html" with eventos=eventos %}
```

`eventos`: lista de dicts, ya ordenada por la vista. Cada uno: `cuando` (metadato ya formateado),
`titulo`, y opcionales `detalle`, `tono` (`warning`, `danger`, `success`; sin él, marca), `badge` +
`badge_tono` (`warning` por defecto). Sin eventos dibuja `_estado_vacio` (`vacio_titulo`, `vacio_texto`).
Riel de 2 px (`border-base`), punto de 10 px con borde tonal. El tono refuerza; lo que pasó va en el título.

En P7 (`programas/templates/programas/dispositivos/estadia/detalle.html`), `cuando` llega como
fecha · hora · turno · responsable. `programas/selectors/estadia_detalle.py` deriva el turno del
momento sobre los turnos activos cargados una vez; si no hay turno vigente, omite ese tramo.
El Historial de P4 conserva su metadato sin turno.

Ese mismo selector prepara el `persona` del encabezado, y lo nombra **«Apellido, Nombre»**
(`Ciudadano.apellido_nombre`): es el orden con el que la tabla desde la que se entró —la solapa
Estadías de P4— lo escribe en la celda, en el menú y en los modales, y el título tiene que decir
lo mismo que la fila. Contrato de la variable en `arquetipos/revision.md`.

En Infraestructura (P19), el evento revisado usa `badge="Revisado"` y `badge_tono="success"`;
conserva la criticidad en `detalle` y el tono del punto, y agrega revisor y fecha/hora a `cuando`.
El servicio carga `revisado_por` junto con la página de relevamientos.

**La lista llega acotada.** El componente dibuja todos los eventos que recibe y una estadía larga trae
cientos: **recortar es responsabilidad de la vista** (las últimas N, más un enlace «Ver todo» cuando
hay más). El componente no pagina. Cuando el feed es largo de verdad —la solapa Historial de
`programas/templates/programas/dispositivos/legajo/detail.html`, que junta en una sola lista la
auditoría de cuatro fuentes— la página la arma la vista y el control va **debajo**, con
`components/_paginacion.html`: la pieza sigue recibiendo solo los eventos de esa página.

**Enlace del evento (opcional).** Un evento puede traer `enlace` (URL interna, armada con `reverse`
en la vista o el servicio) y `enlace_texto` (por defecto «Ver»): se dibuja como un link al final de
la misma línea del texto, y su nombre accesible le suma el `cuando` del evento para que diez «Ver»
no se llamen igual. Es lo que convierte la línea de tiempo en el «historial» con acción por fila que
pide P19 (`programas/templates/programas/dispositivos/legajo/detail.html`, solapa Infraestructura →
«Ver informe»). Sin `enlace` el HTML del evento es el de siempre, carácter por carácter.

**Fotos dentro del evento (opcional).** Un evento puede traer `fotos` (lista de dicts con el
contrato de `components/_galeria_fotos.html`: `url`, `alt`, `rotulo`, `fecha`) y `total_fotos`
(la cantidad real si la vista recortó la tanda). La pieza dibuja la galería **dentro del `<li>`**,
debajo del texto, en un `div mt-3`: una sola `<ol>` con el riel continuo y cada tanda colgada de su
evento (P19, «Registro fotográfico»). Sin `fotos` —o con la lista vacía— el HTML del evento es el de
siempre, carácter por carácter. Consumidor: la solapa Infraestructura de
`programas/templates/programas/dispositivos/legajo/detail.html`.

## Límites actuales

- **No lleva otro contenido rico.** `detalle` sigue siendo una línea escapada, no un slot. Las fotos
  y el `enlace` son las únicas ranuras: otro contenido —una tabla, un formulario— **no se mete marcado en
  `detalle`** (si se desactiva el escape se abre un agujero con texto que carga un usuario); se
  resuelve con otro opcional acá, en una task propia, y hasta entonces va en una card aparte debajo
  de la línea de tiempo.
- El recorte de la tanda (tope 24 de la galería) y el de los eventos son de la vista.

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
| `campos` | Lista de `{etiqueta, valor, estado, formato}`; `estado`: vacío, `falta` (rojo) o `calculado` (gris); `formato: "dni"` opcional |
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
