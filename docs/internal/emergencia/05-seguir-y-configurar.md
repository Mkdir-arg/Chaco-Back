# Emergencia · Etapa 5 — Seguir y configurar (tablero del supervisor y parámetros)

Reglas de rol: `00-reglas-de-usuario.md`. Depende de las etapas 2, 3 y 4 (lee lo que ellas
escriben). La configuración (E7) en cambio va **primera** en el orden de desarrollo
(README §8, PR 1), porque las otras etapas leen sus valores. Mockups: `E1` (tablero),
`E7` (configuración).

## 1. Objetivo

Que el supervisor vea en una pantalla si la emergencia está bajo control: cuántas familias
esperan, cuáles están fuera de tiempo, cuántas camas quedan, qué entregas están en camino y
qué pide acción ahora. Y que los parámetros que gobiernan las reglas (minutos objetivo,
vigencia, catálogo) se cambien sin tocar código.

## 2. Actores

| Rol | Pantalla | Capacidad |
|---|---|---|
| Supervisor de mesa | E1, E7 | `emergencia.supervisar` |

El operador no ve E1 (RU §4). Si el PM lo quiere para todos, es cambiar un decorador.

## 3. E1 · Tablero (arquetipo dashboard, golden del dashboard de Becas)

### Hero del programa

«Emergencia · Crecida del río» (nombre del evento, editable en E7) con tres números
grandes: **casos abiertos**, **fuera de SLA**, **plazas libres en N dispositivos**. Fecha y
hora de la última actualización; botón «Actualizar» (sin auto-refresh en esta etapa).

### Seis indicadores (`_stat_card` con `nota`)

| # | Título | Valor | Nota |
|---|---|---|---|
| 1 | Casos nuevos sin tomar | conteo `NUEVO` | «el más viejo hace 23 min» |
| 2 | En gestión | conteo `EN_GESTION` + `DERIVADO` + `INGRESO_EN_CURSO` | «12 derivados · 3 ingresando» |
| 3 | Fuera de SLA | conteo | desglose por tramo: «tomar 2 · derivar 4 · aceptar 1 · alojar 0» |
| 4 | Familias alojadas hoy | casos con `alojado_en` en el día operativo | «38 personas · 2 ingresos directos · 1 parcial» |
| 5 | Plazas libres en la red | suma sobre elegibles (RN-2.2) | «14 reservadas» |
| 6 | Entregas en camino | conteo `EN_CAMINO` | «2 con diferencias sin revisar» |

### Casos por localidad (tabla)

Localidad · Nuevos · En gestión · Fuera de SLA · Alojadas hoy · Plazas libres (de los
dispositivos de esa localidad). Orden: fuera de SLA desc. Click en la fila → E2 filtrada.

### Tiempos (tabla chica)

Por tramo: objetivo (E7) · mediana · percentil 90 · fuera de objetivo, calculados sobre los
casos **cerrados o avanzados en las últimas 24 h** (RN-5.3).

### Entregas en camino (lista)

N.° · dispositivo · desde cuándo · ítems resumen. Click → E5.

### Avisos que piden acción (lista con severidad)

Salen del registro de avisos de `core/services/vencimientos.py` (`ReglaAviso`, ámbito
`emergencia`), **se calculan al pedirlos y no tienen estado** (RN-5.4):

| Aviso | Condición | Severidad |
|---|---|---|
| Caso fuera de SLA | tramo actual > objetivo | alta |
| Derivación por vencer | `PENDIENTE` y `vence_en − now < 60 min` | media |
| Derivación rechazada sin nueva acción | última traza es rechazo | alta |
| Ingreso parcial sin revisar | `ALOJADO` parcial sin `observacion_mesa` | media |
| Entrega con diferencias sin revisar | `RECIBIDA_CON_DIFERENCIAS` sin `observacion_mesa` | media |
| Dispositivo sin plazas con derivación pendiente | plazas libres 0 y `PENDIENTE` hacia él | alta |
| Familia «en la puerta» de un dispositivo | caso `NUEVO` origen `DISPOSITIVO` | alta |

Cada aviso linkea a su pantalla (E3 o E5). Solapa «Mapa de la emergencia»: visible,
deshabilitada, con texto «Próxima etapa» (reservada; no se implementa).

## 4. E7 · Configuración (arquetipo formulario)

Una sola fila `SLAEmergencia` por programa (se crea en el seed con los defaults):

| Campo | Tipo | Default | Regla |
|---|---|---|---|
| Nombre del evento | texto | «Emergencia» | aparece en el hero de E1 y en el cabezal de E2 |
| Objetivo tomar (min) | entero ≥ 1 | 15 | RN-2.10 |
| Objetivo derivar (min) | entero ≥ 1 | 30 | |
| Objetivo aceptar (min) | entero ≥ 1 | 120 | |
| Objetivo alojar (min) | entero ≥ 1 | 60 | |
| Vigencia de la derivación (min) | entero ≥ 30 | 720 | RN-2.7; 0 no vale |
| Minutos sin avance antes de devolver a bandeja | entero ≥ 0 | 60 | RN-2.8; 0 apaga |
| Umbral «por vencer» (%) | 50 a 95 | 80 | RU-19 |

Debajo, **Catálogo de kits** (`TipoKit`): tabla editable inline (nombre, unidad, orden,
activo), «Agregar ítem». Sin borrar (RN-4.7).

Guardar deja `TrazaConfiguracion` (quién, cuándo, campo, antes, después): la mesa tiene que
poder explicar por qué un caso dejó de estar fuera de SLA.

## 5. Historias de usuario y criterios de aceptación

**HU-5.1** Como supervisor quiero ver en un vistazo qué está fuera de tiempo.
- Dado 3 casos con el tramo «derivar» vencido, cuando abro E1, entonces «Fuera de SLA»
  muestra 3 y la nota «derivar 3».
- Dado que subo el objetivo de derivar en E7, cuando vuelvo a E1, entonces el conteo baja
  sin reprocesar nada (se calcula al leer, RN-5.1).

**HU-5.2** Como supervisor quiero ver dónde falta lugar.
- Dado una localidad con 0 plazas libres y 2 casos nuevos, cuando abro E1, entonces la fila
  de esa localidad muestra 2 nuevos y 0 libres, y hay un aviso «Dispositivo sin plazas con
  derivación pendiente» si corresponde.

**HU-5.3** Como supervisor quiero que los avisos me lleven al lugar.
- Dado un aviso de entrega con diferencias, cuando lo toco, entonces abro E5 de esa
  entrega; cuando escribo la observación de la mesa, el aviso desaparece al volver.

**HU-5.4** Como supervisor quiero cambiar los tiempos sin pedirle a nadie.
- Dado E7, cuando guardo vigencia 480, entonces las derivaciones **nuevas** vencen a las
  8 h; las ya creadas conservan su `vence_en` (RN-5.5).

## 6. Reglas de negocio

- **RN-5.1** Todo el tablero se **calcula al leer**; no hay tabla de métricas ni job.
  Ventana: casos abiertos (cientos) + los cerrados o alojados en las últimas 24 h. Nunca
  recorre el histórico completo.
- **RN-5.2** Sin `TruncDate` / `TruncWeek` sobre `DateTimeField` (MariaDB en ECOM sin
  tablas de timezone → `CONVERT_TZ` devuelve `NULL`). «Hoy» se calcula como rango
  `[inicio_dia_operativo, fin)` en Python y se filtra con `__gte` / `__lt`. El día
  operativo empieza a las 06:00 hora Argentina (como el resto del sistema; verificar el
  helper existente en `programas/services/dashboard_becas.py`).
- **RN-5.3** Mediana y p90 de cada tramo: se traen las marcas de tiempo de los casos de
  la ventana (una consulta con `values_list`) y se calculan en Python. Un tramo sin
  casos muestra «—».
- **RN-5.4** Avisos = `ReglaAviso` registradas con `registrar_aviso`, ámbito
  `"emergencia"`, cada una con su `pendientes()` que devuelve `Aviso` con link. No tienen
  estado, no se cierran; desaparecen cuando la condición deja de cumplirse (doc del
  módulo de vencimientos). **Avisar nunca bloquea.**
- **RN-5.5** Cambiar la vigencia o los minutos sin avance afecta solo lo que se crea
  después; cambiar los objetivos del SLA afecta el semáforo de todos los casos abiertos
  (es un cálculo, RN-2.10), y la traza de configuración permite explicarlo.
- **RN-5.6** Presupuesto: E1 completa en ≤ 12 consultas y < 2 s con 500 casos abiertos,
  50 dispositivos y 200 entregas (test `--tag performance`; `read_timeout` de ECOM es
  10 s y el tablero no puede acercarse).
- **RN-5.7** Plazas libres de la red: una consulta agregada sobre `Plaza` `CAMA`
  `OPERATIVA` de dispositivos elegibles, restando `Estadia` abiertas y `ReservaPlaza`
  `VIGENTE` (`services/ocupacion.py` ya tiene la cuenta por dispositivo; agregar la
  variante por lote si no existe, **sin** N+1 por dispositivo).

## 7. Datos

| Tabla | Operación |
|---|---|
| `SLAEmergencia` | read (E1, E2, E3, cron) / update (E7) |
| `TipoKit` | CRUD sin delete (E7) |
| `TrazaConfiguracion` | insert en cada guardado de E7 |
| `CasoEmergencia`, `Derivacion`, `EntregaKit`, `Plaza`, `Estadia`, `ReservaPlaza` | read |

## 8. Servicios y selectores

- `selectors/emergencia_tablero.py`: `resumen(sla)`, `por_localidad()`,
  `tiempos(ventana)`, `entregas_en_camino()`; cada función una o dos consultas, documentado
  el presupuesto arriba de cada una.
- `services/avisos_emergencia.py`: las siete `ReglaAviso` de §3, registradas en
  `AppConfig.ready()` de `programas` (como las de Dispositivos).
- `services/configuracion_emergencia.py`: `guardar_sla(usuario, **campos)` con traza;
  `catalogo_kits(...)`.
- Vistas: `TableroView` (`@requiere("emergencia.supervisar")`), `ConfiguracionView`
  (ModelForm sobre `SLAEmergencia` + formset de `TipoKit`).

## 9. Casos borde

- Programa recién creado, sin casos → E1 con ceros y «Todavía no hay casos»; sin
  divisiones por cero en mediana / p90.
- Dos supervisores guardan E7 a la vez → gana el último; la traza tiene los dos.
- Cambia la hora del servidor (horario de verano no aplica en Argentina, pero el día
  operativo de 06:00 sí) → test con momentos fijos, no `now()` − N h
  (`proyecto-tests-dependientes-de-la-hora`).

## 10. Criterio de terminado

- [ ] Tests de selectores con datos sembrados: cada número del hero y de las seis
  tarjetas contra un escenario conocido (tabla de casos en el test).
- [ ] Test de cada `ReglaAviso` (aparece / desaparece).
- [ ] Test `--tag performance` de RN-5.6 con `assertNumQueries`.
- [ ] Test de RN-5.2: la consulta de «hoy» no contiene `CONVERT_TZ` (capturar SQL con
  `CaptureQueriesContext`).
- [ ] E1 clonada de la golden del dashboard; E7 de la golden de formulario; fichas nuevas
  para «lista de avisos con severidad» y «tabla de tiempos».
- [ ] Entrada en `requerimientos.md`; casos de QA.
