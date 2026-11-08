# Componente · Chips de enlace (`components/_chips_enlace.html`)

**Clasificación:** Canónico reutilizable. Una fila de enlaces en píldora para cambiar de filtro o de registro sin
salir de la pantalla: cada chip recarga con la URL que armó la vista.
**Evidencia:** `templates/components/_chips_enlace.html`, `core/tests/test_nodo_ui_piezas.py`
(`ChipsEnlaceTest`), `programas/tests/test_dispositivos_infraestructura_tarjetas.py` (`ChipsTests`).
**Consumidor de referencia:** `programas/templates/programas/dispositivos/legajo/_infra_listado.html` (filtro por
estado) y `_infra_ficha.html` (cambiar de edificio), en la solapa Infraestructura de P4.

## Cuándo usarla

- Un filtro corto (hasta 5 opciones) del lado del servidor, o saltar entre hermanos de un mismo registro.
- **No** es `tabs.md` (alterna paneles de la misma página, sin recargar) ni un select: son enlaces reales.

## Invocación

```django
{% include "components/_chips_enlace.html" with nombre="Filtrar los edificios por estado" chips=infraestructura.filtros %}
{% include "components/_chips_enlace.html" with nombre="Otros edificios de esta institución" chips=infraestructura.chips aria_current="page" %}
```

| Parámetro | Efecto |
|---|---|
| `nombre` | Obligatorio. `aria-label` del `<nav>` |
| `chips` | Lista de dicts armada **en la vista**, en el orden en que se dibujan |
| `aria_current` | Opcional. Valor de `aria-current` del chip activo: `true` por defecto, `page` al cambiar de registro |

Cada chip: `texto` y `url` obligatorios; `activo` (resaltado y `aria-current`); `n` (conteo en badge, un 0 se
muestra); `tono` (`success`, `warning`, `danger`: punto del color del estado); `estado` (el estado en palabras,
solo lector de pantalla); `icono` (Font Awesome sin `fas`).

## Reglas

- La vista decide qué chip está activo y arma las URL con `reverse`; el template no compara nada.
- El color nunca es el único portador: el estado y el conteo viajan en texto.
- Los parámetros de otros filtros de la pantalla se conservan al armar la URL, en la vista.
- Autoescape siempre: ningún `|safe`.

## Prohibido

- Chips que cambian contenido sin recargar (eso es `tabs.md`).
- Más de 5 o 6 chips en una fila: pasa a un select o a un listado.
- Una URL externa o armada en el template.
