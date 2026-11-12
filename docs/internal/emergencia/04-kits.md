# Emergencia · Etapa 4 — Kits (la mesa envía insumos, el dispositivo confirma qué llegó)

Reglas de rol: `00-reglas-de-usuario.md`. Independiente de las etapas 1 a 3 (se puede
desarrollar en paralelo; solo necesita el programa y las capacidades de la etapa 0 /
README §8 PR 1). Mockups: `E4` (entregas + asistente), `E5` (detalle de entrega), `M3-1`
(recepción en la PWA), `M3-2` (confirmada).

## 1. Objetivo

Que la mesa sepa qué insumos salieron hacia cada centro y qué llegó de verdad, con la
diferencia a la vista, sin stock ni depósitos: **una entrega, una recepción**.

Resultado: `EntregaKit` `PREPARADA → EN_CAMINO → RECIBIDA | RECIBIDA_CON_DIFERENCIAS`,
con una `LineaEntrega` por ítem (enviado / recibido) y el remito adjunto.

## 2. Actores

| Rol | Superficie | Capacidad |
|---|---|---|
| Operador / supervisor de mesa | Backoffice E4, E5 | `emergencia.operar` |
| Operador del dispositivo | **PWA M3** (principal) y backoffice (misma pantalla dentro del dispositivo) | `emergencia.recibir_kit` evaluada con `puede_operar_dispositivo` (RU-8) |
| Supervisor | Catálogo en E7 | `emergencia.supervisar` |

## 3. Pantallas

### E4 · Entregas de kits (listado + asistente de 3 pasos)

- Listado: N.° de entrega · Dispositivo · Ítems (resumen «3 kits alimentarios, 10
  colchones…») · Estado (chip) · Armada por / cuándo · Recibida por / cuándo · marca
  **«Con diferencias»** resaltada. Filtros: estado, dispositivo, localidad, fecha. Solapas:
  Abiertas (preparadas + en camino) · Con diferencias · Recibidas · Canceladas.
- «Nueva entrega» abre el asistente:
  1. **Dispositivo destino**: buscador por nombre o localidad; la tarjeta muestra personas
     alojadas hoy, plazas ocupadas, última entrega (fecha y si tuvo diferencias).
  2. **Ítems y cantidades**: tabla del catálogo activo (`TipoKit`), cantidad entera > 0,
     unidad al lado; observación para el dispositivo (texto).
  3. **Confirmar**: resumen; «Crear entrega» → `PREPARADA`.
- Acciones por fila: «Marcar en camino» (modal opcional: transporte, hora de salida),
  «Cancelar» (motivo; solo `PREPARADA` o `EN_CAMINO`), «Abrir».

### E5 · Detalle de entrega (arquetipo detalle)

Cabecera: N.°, dispositivo, estado, armada por, en camino desde, recibida por / cuándo.
Tabla: Ítem · Enviado · Recibido · **Diferencia** (resaltada si ≠ 0). Observación de la
mesa, observación del dispositivo, foto del remito (modal), traza. Botón «Reponer»: abre
el asistente con el dispositivo y las diferencias precargadas como cantidades (HU-4.5).

### M3-1 · Recepción de kit (PWA)

Lista de entregas `EN_CAMINO` (y `PREPARADA`, por si llegó sin que la mesa la marcara)
para mi dispositivo. Al abrir una: tabla de ítems **precargada con lo enviado**; cada
cantidad editable; foto del remito (cámara, obligatoria); observación. Botón
**«Confirmar recepción»**.

### M3-2 · Recibida

«Recibida · 2 ítems con diferencia» (o «Recibida completa»). Lista con lo que difirió.
Botón «Volver a entregas».

## 4. Historias de usuario y criterios de aceptación

**HU-4.1** Como operador de mesa quiero armar una entrega en tres pasos.
- Dado un dispositivo `ACTIVO`, cuando completo ítems con cantidad > 0 y confirmo,
  entonces existe la entrega `PREPARADA` con sus líneas y la veo en Abiertas.
- Dado un ítem con cantidad 0 o vacía, cuando confirmo, entonces no avanza: «Sacá el
  ítem o poné una cantidad».

**HU-4.2** Como operador de mesa quiero marcar que salió.
- Dado `PREPARADA`, cuando marco en camino, entonces `EN_CAMINO`, `despachada_en` =
  ahora, y la PWA del dispositivo la lista.

**HU-4.3** Como operador del dispositivo quiero confirmar lo que llegó corrigiendo solo lo
distinto.
- Dado una entrega `EN_CAMINO` de 10 colchones y 3 kits, cuando confirmo sin tocar nada y
  con foto, entonces `RECIBIDA`, `cantidad_recibida` = enviada en cada línea.
- Dado que cambio colchones a 8, cuando confirmo, entonces `RECIBIDA_CON_DIFERENCIAS`, la
  línea muestra diferencia −2, y E4 la lista en «Con diferencias».
- Dado que no saqué la foto, cuando confirmo, entonces «Falta la foto del remito».
- Dado una entrega para otro dispositivo, cuando intento abrirla por id, entonces 403.

**HU-4.4** Como operador de mesa quiero ver qué faltó y por qué.
- Dado `RECIBIDA_CON_DIFERENCIAS`, cuando abro E5, entonces veo enviado / recibido /
  diferencia por ítem, la observación del dispositivo y el remito.

**HU-4.5** Como operador de mesa quiero reponer lo que faltó.
- Dado E5 con diferencias, cuando toco «Reponer», entonces el asistente arranca en el
  paso 2 con el mismo dispositivo y las diferencias como cantidades; la entrega nueva
  guarda `repone_a` = la anterior y E5 lo muestra en los dos sentidos.

**HU-4.6** Como supervisor quiero mantener el catálogo.
- Dado E7, cuando agrego «Agua 6 l» con unidad «bidón», entonces aparece en el paso 2
  del asistente. Cuando desactivo un ítem, deja de aparecer en entregas nuevas pero sigue
  en las viejas.

## 5. Transiciones

| Estado | Acción | Quién | Nuevo | Efectos |
|---|---|---|---|---|
| — | Crear | operar | `PREPARADA` | entrega + líneas (`cantidad_recibida = NULL`), traza |
| `PREPARADA` | Marcar en camino | operar | `EN_CAMINO` | `despachada_en`, transporte, traza |
| `PREPARADA` / `EN_CAMINO` | Cancelar (motivo) | operar | `CANCELADA` | traza |
| `PREPARADA` / `EN_CAMINO` | Recibir | recibir_kit (su dispositivo) | `RECIBIDA` o `RECIBIDA_CON_DIFERENCIAS` | `recibida_en`, `recibida_por`, cantidades, remito, bitácora `GENERAL` «Kit recibido N.° X», traza |
| `RECIBIDA*` | — | — | terminal | «Reponer» crea otra entrega |

Recibir una `PREPARADA` (la mesa no la marcó) es válido y deja traza «Recibida sin marca
de salida» (RN-4.3).

## 6. Reglas de negocio

- **RN-4.1** Una entrega tiene ≥ 1 línea; ítems del catálogo **activos** al crearla; un
  ítem una sola vez por entrega (unique `(entrega, item)`); cantidades enteras > 0.
- **RN-4.2** Destino: `Dispositivo.estado == ACTIVO` (cualquier tipo: un merendero
  también recibe kits).
- **RN-4.3** Recibir: `cantidad_recibida` entera ≥ 0 en **todas** las líneas (prellenada con
  la enviada), foto del remito obligatoria (JPEG, ≤ 5 MB), observación opcional. Estado
  final = `RECIBIDA_CON_DIFERENCIAS` si alguna línea tiene `recibida != enviada`.
- **RN-4.4** Recibir es idempotente por `uuid_cliente`; una entrega ya recibida devuelve
  409 con el estado (otra guardia la confirmó desde el backoffice).
- **RN-4.5** La recepción no se edita después de confirmada: una corrección es una
  observación de la mesa en E5 (campo `observacion_mesa`, con traza), nunca cambiar las
  cantidades.
- **RN-4.6** No hay stock: nada descuenta ni suma existencias. Las cantidades son texto
  de un remito. El tablero suma «entregas en camino» y «con diferencias», no unidades.
- **RN-4.7** `TipoKit`: nombre único, unidad (texto corto: «kit», «unidad», «bidón»),
  `activo`, `orden`. Se desactiva, no se borra (FK desde líneas).
- **RN-4.8** Alcance: la mesa ve todas las entregas; el dispositivo solo las suyas
  (`dispositivos_en_alcance(user, "emergencia.recibir_kit")`).
- **RN-4.9** Toda transición deja `TrazaEntrega` (mismo esquema que `TrazaCaso`, modelo
  aparte para no mezclar FKs).

## 7. Datos

| Tabla | Campos |
|---|---|
| `TipoKit` | nombre (unique), unidad, activo, orden |
| `EntregaKit` | numero, dispositivo, estado, armada_por, observacion_mesa, transporte, despachada_en, recibida_en, recibida_por, observacion_dispositivo, remito (adjunto detrás de login), repone_a (FK self, nullable), motivo_cancelacion, uuid_cliente_recepcion |
| `LineaEntrega` | entrega, item, cantidad_enviada, cantidad_recibida (nullable), unique (entrega, item) |
| `TrazaEntrega` | entrega, usuario, momento, estado_anterior, estado_nuevo, detalle |

`numero` = secuencia legible por año («2026-K-000031») generada en el servicio con
`select_for_update` sobre una fila contador, no `MAX()+1`.

## 8. Servicios y API

Servicios (`programas/services/kits.py`):

```
crear_entrega(usuario, dispositivo, lineas, observacion="", repone_a=None) -> EntregaKit
marcar_en_camino(entrega, usuario, transporte="", hora=None) -> EntregaKit
cancelar_entrega(entrega, usuario, motivo) -> EntregaKit
recibir_entrega(entrega, usuario, cantidades: dict[item_id, int], remito, observacion="", uuid_cliente=None) -> EntregaKit
observar_recepcion(entrega, usuario, texto) -> EntregaKit      # RN-4.5
```

API para la PWA:

| Método y ruta | Cuerpo | Respuesta |
|---|---|---|
| `GET /api/emergencia/dispositivos/{id}/entregas/?pendientes=1` | — | `[{id, numero, estado, despachada_en, lineas: [{item, nombre, unidad, enviada}]}]` |
| `GET …/entregas/{id}/` | — | detalle |
| `POST …/entregas/{id}/recibir/` (multipart) | `cantidades[item_id]`, `remito`, `observacion`, `uuid_cliente` | `{estado, diferencias: [{item, enviada, recibida}]}`; 409 si ya recibida |

## 9. PWA

1. `emergenciaService.js`: `entregasPendientes`, `recibirEntrega` (exige conexión, como
   RN-3.11: la foto y la confirmación van juntas; no se encola porque la mesa está
   esperando la respuesta y una recepción duplicada desde el backoffice daría 409).
2. Pantallas: `EntregasScreen` (M3-1 lista), `RecepcionKitScreen` (M3-1 detalle),
   `RecepcionConfirmadaScreen` (M3-2).
3. Reusar `imagePicker.js` + compresión para el remito.

## 10. Casos borde

- La mesa cancela mientras la guardia está cargando la recepción → al confirmar, 409
  «Entrega cancelada por la mesa a las 15:02».
- El catálogo cambia la unidad de un ítem → las líneas viejas guardan la unidad en el
  momento de crear la entrega (`unidad` copiada en `LineaEntrega`), para que E5 no cambie
  de significado.
- Llegó más de lo enviado → diferencia positiva, también cuenta como «con diferencias».
- Dispositivo pasa a `INACTIVO` con entregas abiertas → siguen visibles para la mesa con
  la marca; la guardia que todavía integra el equipo puede recibir.

## 11. Criterio de terminado

- [ ] Tests de servicio: RN-4.1, 4.3 (estado final según diferencias), 4.4
  (idempotencia + 409), 4.5, 4.8 (alcance), numeración concurrente.
- [ ] Test de mutación: usuario con `recibir_kit` en A no recibe una entrega de B.
- [ ] Contrato de API con claves exactas.
- [ ] E4 (listado + asistente) y E5 (detalle) clonadas de sus goldens; ficha nueva para
  la tabla enviado/recibido/diferencia.
- [ ] Entrada en `requerimientos.md`; casos de QA en PWA y backoffice.
