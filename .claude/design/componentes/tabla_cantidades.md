# Componente · Tabla de cantidades (`components/_tabla_cantidades.html`)

**Clasificación:** Canónico reutilizable. Pieza única: una fila por ítem con su control de cantidad.
**Evidencia:** `templates/components/_tabla_cantidades.html`, `programas/templates/programas/emergencia/kits/nueva.html`
(consumidor), `programas/templates/programas/dispositivos/stock/entregar.html` (consumidor, `rotulo_item="Insumo"`, columna
«En stock»), `core/tests/test_nodo_ui_piezas.py` (`TablaCantidadesTest`).

Va **dentro del `<form>` del consumidor**, que pone la card, el csrf y el pie. No pagina ni calcula.

## Invocación

```django
{% include "components/_tabla_cantidades.html" with filas=filas columnas_info=columnas_info rotulo_cantidad="Cantidad a enviar" caption="Ítems de la entrega" only %}
```

| Parámetro | Efecto |
|---|---|
| `filas` | Armadas por la **vista**: `campo` (BoundField de la cantidad), `nombre`, `unidad`, `info` = `[{texto, nota}]` |
| `columnas_info` | Rótulos de las columnas informativas, en el mismo orden que `info` (vacía o ausente: sin columnas) |
| `rotulo_cantidad` | Rótulo de la última columna, la del control |
| `rotulo_item` | Opcional: rótulo de la primera columna (por defecto «Ítem»; el stock usa «Insumo») |
| `caption` | Texto para el lector de pantalla (`sr-only`) |

## Reglas

- El control sale de `campo_control` (ARIA desde el servidor): el `<label for>` es el nombre, la unidad vive en
  `<auto_id>-ayuda` (la nombra `aria-describedby`) y el error por fila en `<auto_id>-error` con `data-error`.
- Un `texto` vacío en una celda de `info` dibuja «—»; la `nota` va debajo en `text-xs text-body-subtle`.
- Sin `filas` no dibuja nada. Lleva su propio `overflow-x-auto`.
- Los campos se arman con `programas/forms_cantidades.py` (`campo_de_cantidad`, con `help_text="En <unidad>."`, que
  es lo que llena `<auto_id>-ayuda`) y su guarda: un insumo pedido que ya no tiene fila no se descarta en silencio. En
  stock las filas son los insumos con saldo **más** los que llegan cargados en el POST («Hay 0 y pediste N»).

## Prohibido

- Calcular en el template.
- Poner card o paginación adentro.
- Un `<table>` copiado a mano para una lista con cantidades.
