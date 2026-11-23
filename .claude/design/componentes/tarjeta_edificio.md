# Componente · Tarjeta de edificio (`components/_tarjeta_edificio.html`)

**Clasificación:** Canónico reutilizable. Una tarjeta por edificio en la sección «Edificios · N» de la ficha de una
institución (Cambio 570): estado edilicio, ocupación, plazas disponibles, kits y equipo del edificio, y la puerta a su
página operativa (`dispositivos:edificio_operativo`).
**Evidencia:** `templates/components/_tarjeta_edificio.html`, `core/tests/test_nodo_ui_piezas.py`
(`TarjetaEdificioTest`), `programas/tests/test_dispositivos_infraestructura_tarjetas.py`.
**Consumidor de referencia:** `programas/templates/programas/dispositivos/legajo/detail.html` (sección «Edificios · N»,
en el cuerpo, fuera de las solapas). Solo usa clases y tokens que ya existen. Los botones «Vincular edificio» y
«Agregar edificio» los dibuja la sección, no la tarjeta. Los datos extra de la tarjeta (ocupación, disponibles, kits,
equipo, movimientos de hoy) los suma `programas/services/ficha_edificios.py` (`completar_tarjetas`) con costo constante en la
cantidad de edificios. La fila Kits nunca lleva un número suelto: dice «0 por recibir» o «N por recibir» (en camino y
preparadas juntas), igual que el badge de la solapa Kits de la página del edificio.

## Por qué no es `_lista_tarjetas`

`_lista_tarjetas.html` (`lista_tarjetas.md`) es la **alternativa móvil de una tabla**: va en `md:hidden`, repite las
mismas columnas y acciones de la fila y no agrega nada propio. Esta pieza es otra cosa: es la **vista principal en
todos los anchos** (no hay tabla de la que sea reemplazo), presenta un inmueble con su estado edilicio y su aviso de
vencimiento, la ocupación (`_barra_umbral`), una lista de datos (Disponibles, Kits, Equipo) y un pie con los
movimientos de hoy y el enlace «Abrir edificio». Por eso lleva su caja de ícono tonal y el pie, que la tarjeta móvil
no tiene ni debe tener. Comparten el contrato de fondo —un dict armado por la vista y `menu_fila` con las mismas claves
de ítem— y no se mezclan: una tabla densa con tarjetas móviles usa `_lista_tarjetas`; un listado de inmuebles que se
abre a una ficha usa ésta.

## Cuándo usarla

- Un listado de inmuebles donde cada uno tiene estado, ocupación y un destino propio (su página operativa).
- **No** es una fila de tabla ni una `stat_card`: no compara columnas, presenta un edificio y lo abre.
- Con un solo edificio también se usa: la ficha siempre muestra la sección.

## Invocación

```django
<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
  {% include "components/_tarjeta_edificio.html" with edificio=edificio url_ver=url_ver url_editar=url_editar url_desvincular=url_desvincular url_agregar_persona=url_agregar_persona only %}
</div>
```

| Parámetro | Efecto |
|---|---|
| `edificio` | Obligatorio. Dict armado **en la vista o el servicio**, nunca un modelo ni un queryset |
| `url_ver` | Obligatorio. La página del edificio: título, ítem «Abrir edificio» del ⋮ y pie. La arma el servicio (`edificio.url_abrir`) |
| `url_editar` | Opcional (vacía = sin «Editar edificio»). El servicio la manda solo con `dispositivo.editar`; con alcance Edificios no se ofrecen editar ni desvincular (`puede_editar_legajo`) |
| `url_desvincular` | Opcional (vacía = sin «Desvincular»); confirma con `data-confirm-url` (ModernModal) |
| `url_agregar_persona` | Opcional (vacía = sin «Agregar persona al edificio»). Abre el alta del Equipo con este edificio fijo; el servicio la manda solo donde el servidor acepta el alta (Cambio 556) |

Claves de `edificio`: `pk`, `nombre`, `codigo`, `domicilio`, `estado` (estado edilicio: `texto`, `tono`), `aviso`
(`texto`, `tono` o `None`), `predio_compartido`, `ocupacion` (`valor`, `maximo`, `porcentaje`, `tono`, `etiqueta`, `texto`,
`nombre`; `None` si el tipo no maneja plazas: sin barra ni «Disponibles»), `disponibles`, `kits` (`texto`, `clase`; `None`
si quien mira no recibe kits: sin fila), `equipo` (`texto`, `clase`) y `movimientos` (texto del pie). El servicio también
deja en la fila `url_abrir`, `url_editar`, `url_desvincular` y `url_agregar_persona`: el template del consumidor no
concatena URL.

## Reglas

- **El estado, el tono, el aviso, la ocupación y el recorte por alcance los decide el servicio.** La tarjeta solo
  traduce `tono` a color. La ocupación sale del mismo censo que los indicadores de la ficha: no hay otra cuenta de
  plazas. La barra va sin marcas de umbral (la leyenda es de la franja de indicadores).
- El estado y el aviso van siempre en texto (badge con punto); el color del ícono nunca es el único portador.
- El ⋮ usa `{% menu_fila %}` y lleva siempre «Abrir edificio», así que nunca queda vacío; el `id` del menú es
  `edificio-<pk>`, único dentro del listado.
- El «Vencido» (`danger`) y el «Vence en N días» (`warning`) son un badge aparte del estado: la criticidad de la
  última realizada no se pisa.
- Autoescape siempre: ningún `|safe`.
- La ficha arma las filas con `infraestructura_del_dispositivo(..., solo_tarjetas=True)`, que no lee las instituciones del predio ni los totales de relevamientos (la tarjeta no los dibuja; esas claves van vacías). Quien las necesite usa los otros modos del servicio, no la ficha (Cambio 572).

## Prohibido

- Calcular el estado, ordenar o contar dentro del template, o armar sus URL con `|add:`.
- Una grilla sin tope: el servicio entrega hasta 60 tarjetas (las más graves primero) y avisa con
  `n_sin_mostrar`; el filtro por estado muestra el resto.
- Pasar un queryset o acceder a relaciones desde la tarjeta (N+1).
- Una acción de mutación que no confirme por `data-confirm-url`.
- Mostrar kits a quien no puede recibirlos (`kits` es `None`) ni cifras de un edificio fuera de su alcance.
