# Componente · Tarjeta de edificio (`components/_tarjeta_edificio.html`)

**Clasificación:** Canónico reutilizable. Una tarjeta por edificio en el listado de Infraestructura de un
dispositivo: dice a qué edificio pertenece la institución, en qué estado está y si el predio es compartido.
**Evidencia:** `templates/components/_tarjeta_edificio.html`, `core/tests/test_nodo_ui_piezas.py`
(`TarjetaEdificioTest`), `programas/tests/test_dispositivos_infraestructura_tarjetas.py`.
**Consumidor de referencia:** `programas/templates/programas/dispositivos/legajo/_infra_listado.html` (P4, solapa
Infraestructura con 2 o más edificios). Solo usa clases y tokens que ya existen; las pocas utilidades nuevas
entraron al CSS compilado con `npm run build:tailwind`.

## Cuándo usarla

- Un listado de inmuebles donde cada uno tiene estado, último relevamiento y un destino propio (su ficha).
- **No** es una fila de tabla ni una `stat_card`: no compara columnas, presenta un edificio y lleva a su ficha.
- Con un solo edificio no se usa: se abre directo la ficha.

## Invocación

```django
<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
  {% include "components/_tarjeta_edificio.html" with edificio=edificio url_ver=url_ver url_editar=url_editar url_desvincular=url_desvincular only %}
</div>
```

| Parámetro | Efecto |
|---|---|
| `edificio` | Obligatorio. Dict armado **en la vista o el servicio**, nunca un modelo ni un queryset |
| `url_ver` | Obligatorio. La ficha del edificio: título, ítem «Ver» del ⋮ y pie |
| `url_editar` | Opcional. Sin ella no hay «Editar edificio» (se manda solo con `dispositivo.editar`) |
| `url_desvincular` | Opcional. Sin ella no hay «Desvincular»; confirma con `data-confirm-url` (ModernModal) |

Claves de `edificio`: `pk`, `nombre`, `codigo`, `domicilio`, `estado` (`texto`, `tono`), `aviso` (`texto`, `tono`
o `None`), `fecha_texto`, `observacion` (vacía = no se dibuja), `predio`, `sectores_texto`, `conteo`, `con_conteo`.

## Reglas

- **El estado, el tono, el aviso y el recorte por alcance los decide el servicio.** La tarjeta solo traduce `tono`
  a color. Sin alcance de inspección (`con_conteo` falso, `observacion` vacía) no cuenta relevamientos ni fotos y
  el enlace del pie dice «Ver ficha», sin prometer fotos.
- El estado y el aviso van siempre en texto (badge con punto); el color del ícono nunca es el único portador.
- El ⋮ usa `{% menu_fila %}` y lleva siempre «Ver», así que nunca queda vacío; el `id` del menú es
  `edificio-<pk>`, único dentro del listado.
- El «Vencido» (`danger`) y el «Vence en N días» (`warning`) son un badge aparte del estado: la criticidad de la
  última realizada no se pisa.
- Autoescape siempre: ningún `|safe`.

## Prohibido

- Calcular el estado, ordenar o contar dentro del template.
- Pasar un queryset o acceder a relaciones desde la tarjeta (N+1).
- Una acción de mutación que no confirme por `data-confirm-url`.
- Mostrar observaciones, relevó o conteos a quien no tiene alcance de inspección sobre el edificio.
