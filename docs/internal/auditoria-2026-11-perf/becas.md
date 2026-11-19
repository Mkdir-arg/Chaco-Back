# Auditoría de performance y optimización 2026-11 · Becas · Informe final (capítulo 1)

> Informe consolidado de la pasada 1 (18 revisores, 6 tajadas) y de la pasada 2 de los exports (banco). SHA auditado `4140bb8073e271cf6ebccb1f08533d44553baf5a`. Estados `CONFIRMADO (lectura)` o `PLAUSIBLE`: `CONFIRMADO con test` y `REFUTADO` los asigna la pasada 2. Resoluciones del juez del 19-nov-2026 aplicadas. Nada se implementa sin aprobación del PM.

## Resumen ejecutivo (para el PM)

1. **151 fichas activas, 624 h.** Ninguna crítica; 9 altas. Se integraron 2 fichas medidas en el banco y se descartó 1 por coincidir con octubre.
2. **Ola 0 (20 h):** el XSS del export ya está arreglado (#1202). Quedan las altas a SIIS que se saltean la lista «no enviar» (B-ERR-01) y el link anónimo que escribe en legajos (B-SEG-04).
3. **Riesgo operativo mayor:** cargar un padrón grande bloquea el link público más de 10 s y da error (B-PERF-01, Ola 1).
4. **Medido con 20.000 casos:** el Excel de respuestas tarda 18,7 s y el de beneficiarios 8 s. Hoy no cortan; con 8 h y 4 h bajan a ~7 s y ~3 s (Ola 4).
5. **De fondo (Ola 7, 72 h):** las reglas de aprobar casos y de estados del relevamiento viven en las pantallas. Unificar las reglas de estados entre backoffice y app (B-LIM-02) es **DECISIÓN CLIENTE** y un PR coordinado con Chaco-mobile, con los tests de contrato RED-11/RED-03 en el mismo diff.
6. **Propuesta:** issues para las olas 0-7 (262 h). Las olas 8-13 (362 h, limpieza) quedan como backlog opcional.
7. **19 preguntas al cliente** (§7), cada una con una propuesta por defecto que se aplica si no contesta.
8. **76 reglas para no repetir** (§4): 28 se vuelven chequeo automático y 48 van a las guías de revisión.

## 1. Resumen

- **Alcance:** módulo Becas de `programas/` (revisión y relevamientos, dashboard y reportes, integración SIIS, proceso masivo/cupo/padrón, configuración y constructor, app de campo y link público). Tres revisores por tajada: corrección y seguridad, calidad de código, performance.
- **Fichas:** 160 en la pasada 1, 150 tras fusionar (10 fusiones), **+2 de la pasada 2** (B-PERF-25, B-PERF-26, medidas en el banco) y **−1 descartada** por el cruce con octubre (B-PERF-16): **151 activas**. Esfuerzo total: **624 h** (S=2, S-M=4, M=8, L=20); olas 0-7: 262 h (71 fichas); olas 8-13: 362 h (80 fichas).

| Severidad | Fichas |
|---|---|
| CRÍTICA | 0 |
| ALTA | 9 |
| MEDIA | 73 |
| BAJA | 58 |
| INFO | 11 |
| **Total** | **151** |

| Eje | Fichas |
|---|---|
| SEG · Seguridad y RBAC | 4 |
| ERR · Errores y corrección | 30 |
| PERF · Rendimiento | 25 |
| DAT · Datos y operación | 2 |
| LIM · Código limpio y arquitectura | 73 |
| FE · Front (sin estética) | 17 |
| **Total** | **151** |

| Severidad × eje | SEG | ERR | PERF | DAT | LIM | FE |
|---|---|---|---|---|---|---|
| CRÍTICA | 0 | 0 | 0 | 0 | 0 | 0 |
| ALTA | 1 | 1 | 1 | 0 | 6 | 0 |
| MEDIA | 3 | 14 | 9 | 0 | 39 | 8 |
| BAJA | 0 | 15 | 5 | 1 | 28 | 9 |
| INFO | 0 | 0 | 10 | 1 | 0 | 0 |

**Las que importan:**

1. **B-SEG-01** (ALTA, **resuelto en #1202**, Cambio 494): XSS reflejado en `programas/views/dashboard_becas.py:148`; el 400 del export devuelve el valor del parámetro como HTML y la CSP permite `unsafe-inline`. Es el único caso del patrón en el repo; arreglo de una línea. Ola 0.
2. **B-ERR-01** (ALTA): `reenviar_siis_pendientes`, `enviar_casos_siis` y el vaciado de la tabla intermedia no aplican todas las reglas del masivo (lista «no enviar», materias, pausa); un alta doble en SIIS no tiene baja. Mitigante: comandos de operador con `--aplicar`. Ola 0.
3. **B-PERF-01** (ALTA, PLAUSIBLE hasta medir): cargar un padrón de 50.000 filas deja tomada la fila de la convocatoria 15-22 s y cada envío del link público espera más de 10 s y da 500. Hallado por dos revisores. Ola 1.
4. **Ola de fondo** (B-LIM-01, B-LIM-02, B-LIM-03, B-LIM-04, B-LIM-05, B-LIM-06): la resolución del caso y las transiciones de estado del relevamiento están escritas en las vistas y la máquina de estados está duplicada (backoffice y API con reglas divergentes). Es lo que explica la mayor parte de las 73 fichas LIM.
5. **Cifras que no coinciden entre pantallas** (B-LIM-15, B-LIM-14, B-ERR-20, B-ERR-05): el cupo ocupado se calcula en tres lugares y el embudo, el avance y el tablero cuentan con reglas distintas. Requieren decisión del cliente antes de tocar números.

No hay ninguna ficha CRÍTICA. Medido en el banco: el XLSX de respuestas (18,7 s) y el de beneficiarios (8 s) son los únicos exports lentos (B-PERF-25, B-PERF-26); los demás PERF de severidad MEDIA o mayor siguen PLAUSIBLE hasta la pasada 2 (sección 8).

### Fusiones

Pedidas por el juez (se conserva una ficha y la otra queda en «Origen» y en «Aporte del segundo revisor»):

| Ficha final | Absorbe | Motivo |
|---|---|---|
| B-PERF-01 ← B4-PERF-01 | B6-PERF-01 | el lock de la carga de padrón bloquea el link público (visto desde la carga y desde los consumidores) |
| B-ERR-01 ← B3-ERR-01 | B3-LIM-02 | tres vías de alta sin las reglas del masivo (escenario corregido con la matriz del juez) |
| B-LIM-02 ← B1-LIM-04 | B6-LIM-05 | máquina de estados del relevamiento duplicada en backoffice y API |
| B-LIM-15 ← B2-LIM-03 | B4-LIM-03 | cupo ocupado calculado en tres lugares |
| B-LIM-46 ← B1-LIM-08 | B2-LIM-09 | mismos helpers (`_aware_start`, rango por `creado`, `_pct`, `_lotes`) copiados entre revision, dashboard y reportes |

Halladas al consolidar (mismo archivo:línea y mismo problema):

| Ficha final | Absorbe | Motivo |
|---|---|---|
| B-ERR-09 ← B3-ERR-05 | B3-LIM-12 | `conciliar_envios_siis.py:155-248`: acepta el mismo envío dos veces y escribe sin el chequeo de estado previo que tiene `_cerrar` |
| B-ERR-10 ← B3-ERR-09 | B3-LIM-14 | `correr_alta_siis._sentencias` (`:113-140`): la segunda máquina de comillas trata como escapada la comilla que cierra |
| B-DAT-01 ← B3-DAT-01 | B3-LIM-13 | `correr_alta_siis.py:347`/`:362`: el conjunto de todos los pk de `EnvioSIIS` para identificar el caso de prueba |
| B-PERF-06 ← B3-PERF-01 | B4-ERR-03 | retención de hasta `--total` casos con sus JSON: `procesar_casos_siis.py:433` y `proceso_masivo.correr` (`:1098-1105`), el mismo patrón |
| B-LIM-71 ← B6-LIM-10 | B6-PERF-04 | `catalogo_geografico.py:57-59`: `par_coherente_en_catalogo` consulta en vivo; la misma solución (usar el catálogo cacheado) cierra la divergencia y la consulta |

Relaciones que NO se fusionaron (otro problema en el mismo archivo; van cruzadas en las fichas): B-FE-02/B-SEG-02 (guarda del sexo, plantilla vs vista), B-ERR-27/B-DAT-02 (`eliminacion.py`, hijo vivo vs COUNT bajo lock), B-PERF-19/B-PERF-06 (ids de todos los candidatos vs casos hidratados en `proceso_masivo.py:1098`), B-LIM-61 (`_lotes` y cierre de corrida, comparte `_lotes` con B-LIM-46), B-ERR-07/B-LIM-26 (drenaje de la tabla intermedia).

## 2. Índice

| ID | Título | Sev. | Estado | Esf. | Ola | Archivo |
|---|---|---|---|---|---|---|
| B-SEG-01 | El 400 del export del dashboard refleja el parámetro como HTML (XSS reflejado) | ALTA | RESUELTO (#1202) | S | 0 | `programas/views/dashboard_becas.py` |
| B-ERR-01 | Tres vías de alta a SIIS se saltean reglas que solo aplica el masivo (lista «no enviar», mater… | ALTA | CONFIRMADO | M | 0 | `programas/management/commands/reenviar_siis_pendientes.py` |
| B-PERF-01 | La carga del padrón deja tomada la convocatoria (o el relevamiento) 15-22 s y el link público… | ALTA | PLAUSIBLE | M | 1 | `programas/services/padron.py` |
| B-LIM-01 | Resolución del caso (aprobar, rechazar, duplicado, identidad, SIIS) escrita en vistas | ALTA | CONFIRMADO | L | 7 | `programas/views/revision.py` |
| B-LIM-02 | Máquina de estados de `Relevamiento` dispersa y con reglas divergentes (backoffice vs API) | ALTA | CONFIRMADO | L | 7 | `programas/views/relevamientos.py` |
| B-LIM-03 | Detalles de convocatoria y relevamiento arman el contexto y escriben estado en la vista | ALTA | CONFIRMADO | M | 7 | `programas/views/relevamientos.py` |
| B-LIM-04 | «Aprobar → informar a SIIS → avisar al ciudadano» está escrito tres veces, con orden y regla d… | ALTA | CONFIRMADO | M | 7 | `programas/services/proceso_masivo.py` |
| B-LIM-05 | Las reglas del catálogo y los reordenamientos escriben desde las vistas, no desde `services/` | ALTA | CONFIRMADO | M | 7 | `programas/views/configuracion.py` |
| B-LIM-06 | La API de campo tiene el dominio del alta y de la identidad escrito en la vista | ALTA | CONFIRMADO | M | 7 | `programas/api/views.py` |
| B-SEG-02 | Corregir el sexo desde un caso sin validar pisa la identidad de un legajo ya validado en otro… | MEDIA | CONFIRMADO | S | 0 | `programas/views/revision.py` |
| B-SEG-03 | El cupo del link público se agota con inscripciones basura y rechazar no lo libera | MEDIA | PLAUSIBLE | S-M | 0 | `programas/services/inscripcion_publica.py` |
| B-SEG-04 | El link anónimo crea legajos con identidad no verificada y escribe contacto en legajos reales | MEDIA | PLAUSIBLE | S-M | 0 | `programas/services/becas.py` |
| B-ERR-02 | «Revalidar con Base de Personas» guarda el sexo sin normalizar y da 500 con `FEMENINO`/`MASCUL… | MEDIA | CONFIRMADO | S | 5 | `programas/views/revision.py` |
| B-ERR-03 | Editar el contacto del caso reescribe la fila entera y puede revertir una aprobación, un recha… | MEDIA | PLAUSIBLE | S | 5 | `programas/views/revision.py` |
| B-ERR-04 | «Producción territorial» deja afuera los relevamientos que arrancan el último día del rango | MEDIA | CONFIRMADO | S | 4 | `programas/services/reportes_becas.py` |
| B-ERR-05 | La distribución de una pregunta del catálogo cuenta respuestas que una condición ocultó | MEDIA | PLAUSIBLE | M | 4 | `programas/services/dashboard_becas.py` |
| B-ERR-06 | El vaciado de la tabla intermedia registra el envío con el plan del programa, no el del payload | MEDIA | CONFIRMADO | S | 2 | `programas/services/siis_envio.py` |
| B-ERR-07 | `procesar_casos_siis` vacía TODA la tabla intermedia aunque se le pida una convocatoria, relev… | MEDIA | CONFIRMADO | S | 2 | `programas/management/commands/procesar_casos_siis.py` |
| B-ERR-08 | `correr_alta_siis` pierde toda la salida del hijo cuando corta por freno o error | MEDIA | CONFIRMADO | S | 2 | `programas/management/commands/correr_alta_siis.py` |
| B-ERR-09 | `conciliar_envios_siis` acepta el mismo envío dos veces con decisiones opuestas y actualiza si… | MEDIA | CONFIRMADO | S | 2 | `programas/management/commands/conciliar_envios_siis.py` |
| B-ERR-10 | `_sentencias` parte mal un literal que termina en barra invertida escapada | MEDIA | CONFIRMADO | S | 2 | `programas/management/commands/correr_alta_siis.py` |
| B-ERR-11 | Desde Cupo se encola y se aprueba un caso con conflicto de carga duplicada sin resolver | MEDIA | CONFIRMADO | S | 3 | `programas/services/cupo.py` |
| B-ERR-12 | Una caída de la conexión a la base deja la corrida masiva «en curso» sin motivo y el hilo muer… | MEDIA | PLAUSIBLE | S | 3 | `programas/services/proceso_masivo.py` |
| B-ERR-13 | La condición por defecto de un grupo del catálogo puede quedar detrás de su fuente y ocultar e… | MEDIA | CONFIRMADO | S-M | 6 | `programas/forms.py` |
| B-ERR-14 | Cambiar el tipo u opciones de una pregunta o requisito fuente de condiciones deja condiciones… | MEDIA | CONFIRMADO | M | 6 | `programas/forms.py` |
| B-ERR-15 | Los adjuntos que sincronizan después del cierre se rechazan si el caso no trae `capturado_en` | MEDIA | PLAUSIBLE | S | 1 | `programas/api/views.py` |
| B-PERF-02 | El CSV de lista de espera carga y decodifica los JSON pesados de cada caso | MEDIA | PLAUSIBLE | S | 5 | `programas/views/relevamientos.py` |
| B-PERF-03 | El embudo cuenta la lista de espera con un DISTINCT sobre las 37 columnas del caso, JSON inclu… | MEDIA | PLAUSIBLE | S | 4 | `programas/services/reportes_becas.py` |
| B-PERF-04 | Distribución de un campo propio condicionado: una fila y una corrida del motor de condiciones… | MEDIA | PLAUSIBLE | S-M | 4 | `programas/services/dashboard_becas.py` |
| B-PERF-05 | Export del dashboard: una pasada sobre todo el recorte por cada campo propio de todas las conv… | MEDIA | PLAUSIBLE | S | 4 | `programas/views/dashboard_becas.py` |
| B-PERF-06 | La corrida de `procesar_casos_siis` y el masivo de la pantalla retienen en memoria hasta `--to… | MEDIA | PLAUSIBLE | S-M | 3 | `programas/management/commands/procesar_casos_siis.py` |
| B-PERF-07 | `enviar_casos_siis` y `reenviar_siis_pendientes` eligen candidatos en una sola consulta sin ra… | MEDIA | PLAUSIBLE | S | 2 | `programas/management/commands/reenviar_siis_pendientes.py` |
| B-PERF-08 | Techo de rendimiento de la cola única del link público, nunca medido | MEDIA | PLAUSIBLE | S-M | 1 | `programas/services/inscripcion_publica.py` |
| B-LIM-07 | `views/revision.py` pasa de 1.000 líneas (1.385) y sigue creciendo | MEDIA | CONFIRMADO | M | 11 | `programas/views/revision.py` |
| B-LIM-08 | `views/relevamientos.py` pasa de 1.000 líneas (1.213) | MEDIA | CONFIRMADO | M | 11 | `programas/views/relevamientos.py` |
| B-LIM-09 | Resolución «persona del caso» (`ciudadano` o `datos_identificacion`) copiada ~15 veces | MEDIA | CONFIRMADO | S-M | 11 | `programas/views/relevamientos.py` |
| B-LIM-10 | Tres validadores de `next` con reglas distintas | MEDIA | CONFIRMADO | S | 11 | `programas/views/revision.py` |
| B-LIM-11 | `selectors/revision.py` construye formularios, evalúa permisos y duplica un contrato de 13 cla… | MEDIA | CONFIRMADO | S-M | 11 | `programas/selectors/revision.py` |
| B-LIM-12 | `services/solapas.py`: clase-namespace que mezcla lectura, escritura, presentación y lógica de… | MEDIA | CONFIRMADO | M | 11 | `programas/services/solapas.py` |
| B-LIM-13 | `dashboard_becas.py` concentra cinco servicios en 1.780 líneas y sigue creciendo | MEDIA | CONFIRMADO | L | 10 | `programas/services/dashboard_becas.py` |
| B-LIM-14 | Dos embudos de revisión calculan las «mismas» etapas con definiciones distintas | MEDIA | CONFIRMADO | M | 4 | `programas/services/dashboard_becas.py` |
| B-LIM-15 | El cupo ocupado y el distribuido se calculan en tres lugares con alcances distintos | MEDIA | CONFIRMADO | M | 4 | `programas/services/dashboard_becas.py` |
| B-LIM-16 | La fila «avance por convocatoria» se calcula dos veces (dashboard y reporte de avance) | MEDIA | CONFIRMADO | S-M | 10 | `programas/services/dashboard_becas.py` |
| B-LIM-17 | La lectura canónica de respuestas vive en el dashboard y la importa el envío a SIIS | MEDIA | CONFIRMADO | S-M | 10 | `programas/services/dashboard_becas.py` |
| B-LIM-18 | Política de autorización y de freno del dashboard escrita en la vista | MEDIA | CONFIRMADO | S-M | 10 | `programas/views/dashboard_becas.py` |
| B-LIM-19 | El registro de reportes está repartido en tres lugares y tiene un caso especial | MEDIA | CONFIRMADO | M | 10 | `programas/views/reportes_becas.py` |
| B-LIM-20 | `siis_envio.py` tiene 1.518 líneas y mezcla seis responsabilidades | MEDIA | CONFIRMADO | M | 8 | `programas/services/siis_envio.py` |
| B-LIM-21 | El bucle «lote → caso → freno → línea de avance → pausa» está copiado en tres comandos (y un c… | MEDIA | CONFIRMADO | S-M | 8 | `validar_casos_siis.py` |
| B-LIM-22 | Tres comandos de la integración no heredan `ComandoSiisBase` y reescriben sus guardas | MEDIA | CONFIRMADO | S | 8 | `correr_alta_siis.py` |
| B-LIM-23 | Las precondiciones de `correr_alta_siis` reimplementan con otra regla lo que lee `armar_payloa… | MEDIA | CONFIRMADO | S | 8 | `correr_alta_siis.py` |
| B-LIM-24 | `enviar_beneficiario_a_siis` y `guardar_en_tabla_intermedia` duplican el preámbulo, y el `Envi… | MEDIA | CONFIRMADO | S-M | 8 | `siis_envio.py` |
| B-LIM-25 | El resultado del cliente SIIS es un dict sin contrato, y el consumidor tiene una rama para moc… | MEDIA | CONFIRMADO | M | 8 | `siis.py` |
| B-LIM-26 | La política del drenaje de la tabla intermedia (cuándo frenar y qué hacer después) vive en `pr… | MEDIA | CONFIRMADO | S-M | 8 | `procesar_casos_siis.py` |
| B-LIM-27 | Cuatro comandos de alta que se solapan: `enviar_casos_siis` y `reenviar_siis_pendientes` son m… | MEDIA | CONFIRMADO | M | 8 | `procesar_casos_siis.py` |
| B-LIM-28 | `services/proceso_masivo.py` tiene 1.191 líneas y cuatro responsabilidades | MEDIA | CONFIRMADO | M | 9 | `programas/services/proceso_masivo.py` |
| B-LIM-29 | Normalización de DNI, sexo y fecha reescrita fuera de sus canónicas (y una contradice a la otr… | MEDIA | CONFIRMADO | S-M | 9 | `proceso_masivo.py` |
| B-LIM-30 | «Completar el legajo solo donde está vacío» está tres veces, y `alta_de_oficio` importa privad… | MEDIA | CONFIRMADO | S-M | 9 | `programas/services/padron.py` |
| B-LIM-31 | `completar_casos_renaper` lleva dominio dentro del comando y clona `sincronizar_desde_legacy` | MEDIA | CONFIRMADO | S-M | 9 | `programas/management/commands/completar_casos_renaper.py` |
| B-LIM-32 | La vista de Cupo arma el alcance y las tres consultas en `get_context_data` (115 líneas) | MEDIA | CONFIRMADO | S-M | 9 | `programas/views/cupo.py` |
| B-LIM-33 | `candidatos()` tiene 11 parámetros, 6 de ellos banderas que se combinan | MEDIA | CONFIRMADO | S-M | 9 | `programas/services/proceso_masivo.py` |
| B-LIM-34 | `views/configuracion.py` pasa las 1.000 líneas con cinco ABMs en un solo módulo | MEDIA | CONFIRMADO | M | 12 | `programas/views/configuracion.py` |
| B-LIM-35 | La misma regla de activación vive en el form **y** en la vista, con mensajes y defensas distin… | MEDIA | CONFIRMADO | S-M | 12 | `programas/forms.py` |
| B-LIM-36 | El «nivel» de un requisito (programa/segmento/subsegmento) se despacha con `if/elif` en ocho l… | MEDIA | CONFIRMADO | M | 12 | `programas/views/configuracion.py` |
| B-LIM-37 | Aristas vista→vista y nombres privados cruzando módulos que se pueden borrar hoy | MEDIA | CONFIRMADO | S | 12 | `programas/views/configuracion.py` |
| B-LIM-38 | El pegamento HTTP del constructor está copiado entre Becas y Dispositivos | MEDIA | CONFIRMADO | S-M | 12 | `programas/views/diseno.py` |
| B-LIM-39 | «El diseño sigue al catálogo» está escrito dos veces: `reconciliar` y `items_vigentes` | MEDIA | CONFIRMADO | M | 12 | `programas/services/diseno.py` |
| B-LIM-40 | `programas/forms.py` tiene 2.525 líneas y mezcla Becas, SIIS y Dispositivos | MEDIA | CONFIRMADO | L | 12 | `programas/forms.py` |
| B-LIM-41 | Dos caminos para crear un caso (app de campo y link público) con el mismo esqueleto y reglas q… | MEDIA | CONFIRMADO | L | 13 | `programas/api/views.py` |
| B-LIM-42 | «Qué origen acredita identidad» está escrito en seis lugares aunque existe la constante canóni… | MEDIA | CONFIRMADO | S | 13 | `programas/services/identidad.py` |
| B-LIM-43 | `FormularioSerializer.validate` hace el dominio del alta y le pasa resultados a la vista por `… | MEDIA | CONFIRMADO | M | 13 | `programas/api/serializers.py` |
| B-LIM-44 | Traducir respuestas a columnas fijas e identidad está escrito tres veces, con la misma regla d… | MEDIA | CONFIRMADO | S-M | 13 | `programas/api/serializers.py` |
| B-LIM-45 | `autorizacion.py` repite la precedencia de roles en cinco funciones, en dos órdenes distintos,… | MEDIA | CONFIRMADO | M | 13 | `programas/services/autorizacion.py` |
| B-FE-01 | Mapeos de estado → etiqueta/tono y decisiones de dominio escritos en templates | MEDIA | CONFIRMADO | S-M | 11 | `revision/_detalle/_siis_envio.html` |
| B-FE-02 | Regla de «sexo de solo lectura» divergente: el template ofrece editar y la vista siempre recha… | MEDIA | CONFIRMADO | S | 5 | `programas/templates/programas/becas/revision/_detalle/_identidad.html` |
| B-FE-03 | JS inline del detalle de revisión duplicado (toggles, selects dependientes, modales, guarda de… | MEDIA | CONFIRMADO | M | 11 | `revision/_detalle/_scripts.html` |
| B-FE-04 | Formulario «Nuevo relevamiento» triplicado con divergencias | MEDIA | CONFIRMADO | S-M | 11 | `relevamientos/convocatoria_detail.html` |
| B-FE-05 | Las etiquetas de canal y estado se reescriben en cinco lugares y la exportación dice otra cosa… | MEDIA | CONFIRMADO | S-M | 4 | `programas/models/__init__.py` |
| B-FE-06 | El editor de condiciones está copiado entero dentro de un atributo `x-data`, y ya divergió | MEDIA | CONFIRMADO | S-M | 12 | `programas/templates/programas/becas/config/pregunta_list.html` |
| B-FE-07 | La paridad Python↔JS cubre el motor de condiciones, pero no el filtro por canal, que tiene dos… | MEDIA | CONFIRMADO | S-M | 12 | `programas/services/diseno.py` |
| B-FE-08 | El modal de requisito está duplicado en cuatro pantallas y ya difiere entre ellas | MEDIA | CONFIRMADO | M | 12 | `programas/templates/programas/becas/config/segmento_detail.html` |
| B-ERR-16 | «Terminar revisión» cuenta los pendientes sin candado: una captura tardía puede quedar ENVIADA… | BAJA | PLAUSIBLE | S | 5 | `programas/views/revision.py` |
| B-ERR-17 | El filtro «fecha hasta» del listado de relevamientos excluye los que empiezan ese mismo día | BAJA | CONFIRMADO | S | 5 | `programas/views/relevamientos.py` |
| B-ERR-18 | Los filtros `segmento` y `territorial` del listado de relevamientos dan 500 con un valor no nu… | BAJA | CONFIRMADO | S | 5 | `programas/views/relevamientos.py` |
| B-ERR-19 | El CSV de beneficiarios rotula como «Fecha de aprobación» la última modificación del caso, en… | BAJA | CONFIRMADO | S | 5 | `programas/views/relevamientos.py` |
| B-ERR-20 | «Avance de convocatorias» cuenta con otras reglas de alcance que el resto de los reportes | BAJA | CONFIRMADO | S | 4 | `programas/services/reportes_becas.py` |
| B-ERR-21 | Una caída de Redis al leer el token deja el envío EN_PROCESO sin POST | BAJA | CONFIRMADO | S | 2 | `programas/services/siis.py` |
| B-ERR-22 | Un catálogo vacío de SIIS queda en cache 24 h | BAJA | CONFIRMADO | S | 2 | `programas/services/siis.py` |
| B-ERR-23 | `--ignorar-corrida` de `correr_alta_siis` no llega a los hijos y corta a mitad de camino | BAJA | CONFIRMADO | S | 2 | `programas/management/commands/correr_alta_siis.py` |
| B-ERR-24 | El cruce automático del padrón pisa validaciones y datos del legajo escritos mientras corre | BAJA | PLAUSIBLE | S | 3 | `programas/services/padron.py` |
| B-ERR-25 | El fallecimiento se busca en toda la respuesta de Base de Personas, no en el registro elegido | BAJA | PLAUSIBLE | S | 3 | `programas/services/personas.py` |
| B-ERR-26 | `completar_casos_renaper --aplicar` reescribe `data`/`respuestas`/`definicion` con una copia s… | BAJA | PLAUSIBLE | S | 3 | `programas/management/commands/completar_casos_renaper.py` |
| B-ERR-27 | La eliminación en cascada puede dejar vivo un hijo creado entre la lectura de ids y el bloqueo | BAJA | PLAUSIBLE | S | 6 | `programas/services/eliminacion.py` |
| B-ERR-28 | `reconciliar` e `items_vigentes` asumen que cada regla de condición es un dict | BAJA | PLAUSIBLE | S | 6 | `programas/services/diseno.py` |
| B-ERR-29 | `generar_por_defecto` no limpia `bajas_pendientes` y el siguiente `reconciliar` informa bajas… | BAJA | PLAUSIBLE | S | 6 | `programas/services/diseno.py` |
| B-ERR-30 | `datos_identificacion` que no es objeto JSON da 500 en vez de 400 | BAJA | CONFIRMADO | S | 1 | `programas/api/serializers.py` |
| B-PERF-09 | El detalle de convocatoria lista todos sus relevamientos sin paginar | BAJA | CONFIRMADO | S | 5 | `programas/views/relevamientos.py` |
| B-PERF-10 | El embudo agrupa los motivos en Python trayendo cada rechazo, y cada validación SIIS entera co… | BAJA | CONFIRMADO | S | 4 | `programas/services/reportes_becas.py` |
| B-PERF-11 | El catálogo de preguntas del dashboard se recalcula en cada request, con los ítems de todos lo… | BAJA | PLAUSIBLE | S | 4 | `programas/forms_reportes.py` |
| B-PERF-12 | `correr_alta_siis` vuelve a hidratar y armar el payload de todos los incompletos en cada tanda… | BAJA | CONFIRMADO | S-M | 2 | `programas/management/commands/correr_alta_siis.py` |
| B-PERF-13 | Borrar un requisito, una pregunta general o un subsegmento con documentos cargados trae a memo… | BAJA | CONFIRMADO | S | 6 | `programas/views/configuracion.py` |
| B-DAT-01 | `correr_alta_siis` identifica el caso de prueba por diferencia contra todos los pk de EnvioSII… | BAJA | CONFIRMADO | S | 2 | `programas/management/commands/correr_alta_siis.py` |
| B-LIM-46 | Helpers duplicados dentro de `programas` (paginación, hidratación, marcas, fechas, porcentajes… | BAJA | CONFIRMADO | S-M | 11 | `views/revision.py` |
| B-LIM-47 | La huella del alcance se calcula en dos lugares y cada entrada puede volver a resolver el alca… | BAJA | CONFIRMADO | S | 10 | `programas/services/dashboard_becas.py` |
| B-LIM-48 | Copia y pega dentro de `reporte_produccion` y `reporte_avance` | BAJA | CONFIRMADO | S | 10 | `programas/services/reportes_becas.py` |
| B-LIM-49 | Tres escritores del mismo CSV/XLSX en `exportacion_reportes.py` y artefacto de la conversión a… | BAJA | CONFIRMADO | S | 10 | `programas/services/exportacion_reportes.py` |
| B-LIM-50 | El contrato de `Datos` son dicts sueltos que tres consumidores leen por nombre | BAJA | CONFIRMADO | S-M | 10 | `programas/services/dashboard_becas.py` |
| B-LIM-51 | El form del dashboard resuelve el catálogo de dominio y arma JSON de presentación | BAJA | CONFIRMADO | S | 10 | `programas/forms_reportes.py` |
| B-LIM-52 | `armar_payload` (160 líneas) repite nueve veces «resolver → payload o faltante» | BAJA | CONFIRMADO | S-M | 8 | `siis_envio.py` |
| B-LIM-53 | El cliente repite la invalidación del token, el corte de configuración y la normalización de í… | BAJA | CONFIRMADO | S-M | 8 | `siis.py` |
| B-LIM-54 | La pausa del login convierte la excepción en un string y la vuelve a fabricar, con `requests.R… | BAJA | CONFIRMADO | S-M | 8 | `siis.py` |
| B-LIM-55 | `siis.py` (986 líneas, al borde del umbral) mezcla el cliente HTTP con la persistencia de catá… | BAJA | CONFIRMADO | S | 8 | `siis.py` |
| B-LIM-56 | `_localidades_csv_siis.py` es dominio escondido en `management/commands`, con `CommandError` y… | BAJA | CONFIRMADO | S | 8 | `programas/management/commands/_localidades_csv_siis.py` |
| B-LIM-57 | Alias históricos, imports perezosos sin motivo y códigos de error sin constante | BAJA | CONFIRMADO | S | 8 | `_base_siis.py` |
| B-LIM-58 | Las tres acciones de Cupo repiten el prólogo de autorización y no exigen POST | BAJA | CONFIRMADO | S | 9 | `programas/views/cupo.py` |
| B-LIM-59 | Los desenlaces de la aprobación viajan como strings sueltos en seis módulos | BAJA | CONFIRMADO | S | 9 | `programas/services/cupo.py` |
| B-LIM-60 | La aprobación con cupo está escrita tres veces en `cupo.py` | BAJA | CONFIRMADO | S | 9 | `programas/services/cupo.py` |
| B-LIM-61 | `correr()` repite cinco veces el cierre de la corrida y `_lotes` existe cinco veces en `progra… | BAJA | CONFIRMADO | S | 9 | `programas/services/proceso_masivo.py` |
| B-LIM-62 | Lanzar el masivo lee la planilla entera solo para saber si existe; tres formas de preguntar po… | BAJA | CONFIRMADO | S | 9 | `programas/views/proceso_masivo.py` |
| B-LIM-63 | Ciclo `proceso_masivo` ↔ `siis_envio` escondido con un import diferido | BAJA | CONFIRMADO | S | 9 | `programas/services/proceso_masivo.py` |
| B-LIM-64 | `inscribir_de_oficio` reimplementa dos veces el freno por errores seguidos | BAJA | CONFIRMADO | S | 9 | `programas/management/commands/inscribir_de_oficio.py` |
| B-LIM-65 | Cada vista bifurca AJAX/clásico a mano y `subsegmento_crear/editar` repiten el mismo bloque | BAJA | CONFIRMADO | S-M | 12 | `programas/views/configuracion.py` |
| B-LIM-66 | `forms_dinamicos`: el tipo de campo se compara contra cadenas sueltas en una cadena de `if` | BAJA | CONFIRMADO | S | 12 | `programas/forms_dinamicos.py` |
| B-LIM-67 | Dos modelos de borrado para la misma jerarquía de Becas | BAJA | CONFIRMADO | S-M | 12 | `programas/views/configuracion.py` |
| B-LIM-68 | `gestionar_pausa` resuelve el alcance con `isinstance` en la vista y arrastra un desfasaje de… | BAJA | CONFIRMADO | S | 12 | `programas/views/pausas.py` |
| B-LIM-69 | `programas/services/becas.py` es un cajón de sastre: definición, lookups por UUID, alcance, tr… | BAJA | CONFIRMADO | S-M | 13 | `programas/services/becas.py` |
| B-LIM-70 | Tres escrituras de «el caso que ocupa este DNI» y envoltorios que solo renombran | BAJA | CONFIRMADO | S | 13 | `programas/api/views.py` |
| B-LIM-71 | Coherencia Provincia-Localidad: el link valida contra la caché y la API contra la base viva | BAJA | CONFIRMADO | S | 13 | `programas/services/catalogo_geografico.py` |
| B-LIM-72 | El paso 2 del link arma las respuestas dos veces con el mismo bucle | BAJA | CONFIRMADO | S | 13 | `portal/forms/inscripcion.py` |
| B-LIM-73 | Las migas de Becas duplican la capacidad que pide cada vista de destino | BAJA | CONFIRMADO | S | 13 | `programas/templatetags/becas_extras.py` |
| B-FE-09 | 23 evaluaciones de `\|puede:"..."` en templates del alcance que repiten decisiones de la vista | BAJA | CONFIRMADO | S-M | 11 | `revision/_detalle/_acciones.html` |
| B-FE-10 | El JS reconstruye estructura partiendo textos compuestos por el servidor | BAJA | CONFIRMADO | S | 10 | `static/custom/js/becas-dashboard.js` |
| B-FE-11 | Porcentajes y umbrales de cupo recalculados en el JS | BAJA | CONFIRMADO | S | 10 | `static/custom/js/becas-dashboard.js` |
| B-FE-12 | La pantalla de Cupo reimplementa la confirmación canónica (tres funciones y un form oculto por… | BAJA | CONFIRMADO | S | 9 | `programas/templates/programas/becas/cupo/segmento_detail.html` |
| B-FE-13 | Las plantillas del aviso deciden el texto comparando literales, duplicado entre `.txt` y `.htm… | BAJA | CONFIRMADO | S | 9 | `programas/templates/programas/becas/email/resolucion_body.txt` |
| B-FE-14 | Dos lectores DOM→respuestas para el mismo motor, uno sin el caso del archivo ya guardado | BAJA | CONFIRMADO | S | 12 | `static/custom/js/nodo-formulario.js` |
| B-FE-15 | JS inline en templates de configuración y helpers reimplementados por archivo | BAJA | CONFIRMADO | S | 12 | `programas/templates/programas/becas/config/proceso_masivo.html` |
| B-FE-16 | `nodo-firma.js` observa todo el documento y recorre el DOM en cada mutación de cualquier página | BAJA | CONFIRMADO | S | 13 | `static/custom/js/nodo-firma.js` |
| B-FE-17 | `nodo-cascada-geo.js` depende del orden de carga de `nodo-formulario.js` y mide layout en cada… | BAJA | CONFIRMADO | S | 13 | `static/custom/js/nodo-cascada-geo.js` |
| B-PERF-14 | La tabla de casos del detalle de relevamiento pagina por OFFSET sobre filas anchas con join | INFO | PLAUSIBLE | S | 5 | `programas/views/relevamientos.py` |
| B-PERF-15 | Reportes transversales: el alcance viaja como IN anidados (2-3 niveles) y el banco solo lo mid… | INFO | PLAUSIBLE | S | 4 | `programas/services/reportes_becas.py` |
| B-PERF-17 | Beneficiarios: la fecha de aprobación sale de una subconsulta sobre TracaFormulario sin índice… | INFO | PLAUSIBLE | S | 4 | `programas/services/reportes_becas.py` |
| B-PERF-18 | El drenaje de la tabla intermedia y el listado de inciertos traen los JSON del caso para usar… | INFO | CONFIRMADO | S | 2 | `programas/services/siis_envio.py` |
| B-PERF-19 | La corrida masiva lee los ids de **todos** los candidatos aunque pida 100 | INFO | PLAUSIBLE | S | 3 | `programas/services/proceso_masivo.py` |
| B-PERF-20 | `get_cupo_stats` cuenta los aprobados del segmento con el `Segmento` tomado en cada aprobación… | INFO | PLAUSIBLE | S | 3 | `programas/services/cupo.py` |
| B-PERF-21 | `inscribir_de_oficio` resuelve el legajo y aprueba con el relevamiento público y la convocator… | INFO | PLAUSIBLE | S | 3 | `programas/services/alta_de_oficio.py` |
| B-PERF-22 | `completar_casos_renaper` arma un `IN` con todos los ids de casos para averiguar las convocato… | INFO | PLAUSIBLE | S | 3 | `programas/management/commands/completar_casos_renaper.py` |
| B-PERF-23 | Borrar una pregunta general bloquea y reescribe el diseño de cada convocatoria en una sola tra… | INFO | CONFIRMADO | S | 6 | `programas/services/diseno.py` |
| B-PERF-24 | Catálogo geográfico: estampida al vencer el caché y ~150 KB embebidos en cada GET del paso 2 | INFO | CONFIRMADO | S | 1 | `programas/services/catalogo_geografico.py` |
| B-PERF-25 | El XLSX de respuestas del dashboard tarda 18,7 s caliente / 27,8 s frío: el 75 % es openpyxl… | MEDIA | CONFIRMADO (medido) | M | 4 | `programas/services/exportacion_reportes.py` |
| B-PERF-26 | El XLSX de beneficiarios hidrata Formulario + 4 relaciones por cada aprobado para usar 7 valores | MEDIA | CONFIRMADO (medido) | S-M | 4 | `programas/services/reportes_becas.py` |
| B-DAT-02 | La baja lógica en cascada cuenta los casos con COUNT(*) mientras tiene tomada la fila de cada… | INFO | PLAUSIBLE | S | 6 | `programas/services/eliminacion.py` |

## 3. Plan por olas

Lo urgente primero; después por archivo, para que los PRs no se pisen. Horas con S=2, S-M=4, M=8, L=20. Un issue por ola.

| Ola | Nombre | Fichas | Horas |
|---|---|---|---|
| 0 | Urgente: seguridad y daño irreversible | 5 | 20 |
| 1 | Padrón y link público: lock, cola y app de campo | 5 | 18 |
| 2 | SIIS: correcciones y rendimiento de los comandos | 12 | 26 |
| 3 | Proceso masivo, cupo y alta de oficio | 10 | 22 |
| 4 | Dashboard y reportes: cifras y rendimiento | 15 | 60 |
| 5 | Revisión y relevamientos | 10 | 20 |
| 6 | Configuración, constructor y borrado en cascada | 8 | 24 |
| 7 | De fondo: servicio único de resolución del caso y de estados del relevamiento | 6 | 72 |
| 8 | Limpieza SIIS | 14 | 58 |
| 9 | Limpieza masivo, cupo y padrón | 15 | 46 |
| 10 | Limpieza dashboard y reportes | 12 | 56 |
| 11 | Limpieza revisión y relevamientos | 11 | 58 |
| 12 | Limpieza configuración y constructor | 16 | 86 |
| 13 | Limpieza app de campo y link público | 12 | 58 |
| | **Total** | **151** | **624** |

Olas 0-7 (corrección, rendimiento y fondo): **262 h**, 71 fichas. Olas 8-13 (limpieza, backlog opcional): **362 h**, 80 fichas.

### Ola 0 · Urgente: seguridad y daño irreversible (20 h, 5 fichas)

El XSS (B-SEG-01) ya está mergeado (#1202, Cambio 494). Las tres SEG de Becas pendientes de decisión (sección 7) llevan propuesta por defecto aplicable; si el cliente no contesta a tiempo, se implementa el default. Va primero y sin esperar al resto.

- **B-SEG-01** [ALTA · S] El 400 del export del dashboard refleja el parámetro como HTML (XSS reflejado)
- **B-ERR-01** [ALTA · M] Tres vías de alta a SIIS se saltean reglas que solo aplica el masivo (lista «no enviar», materias, pausa vigente)
- **B-SEG-02** [MEDIA · S] Corregir el sexo desde un caso sin validar pisa la identidad de un legajo ya validado en otro caso, aun fuera del alcan…
- **B-SEG-03** [MEDIA · S-M] El cupo del link público se agota con inscripciones basura y rechazar no lo libera
- **B-SEG-04** [MEDIA · S-M] El link anónimo crea legajos con identidad no verificada y escribe contacto en legajos reales

### Ola 1 · Padrón y link público: lock, cola y app de campo (18 h, 5 fichas)

Primero el corte de la transacción de `cargar_padron` (la medición decide el resto). Archivos: `services/padron.py`, `services/inscripcion_publica.py`, `api/views.py`, `services/catalogo_geografico.py`, `static/custom/js/nodo-*.js`.

- **B-PERF-01** [ALTA · M] La carga del padrón deja tomada la convocatoria (o el relevamiento) 15-22 s y el link público espera más de 10 s
- **B-ERR-15** [MEDIA · S] Los adjuntos que sincronizan después del cierre se rechazan si el caso no trae `capturado_en`
- **B-PERF-08** [MEDIA · S-M] Techo de rendimiento de la cola única del link público, nunca medido
- **B-ERR-30** [BAJA · S] `datos_identificacion` que no es objeto JSON da 500 en vez de 400
- **B-PERF-24** [INFO · S] Catálogo geográfico: estampida al vencer el caché y ~150 KB embebidos en cada GET del paso 2

### Ola 2 · SIIS: correcciones y rendimiento de los comandos (26 h, 12 fichas)

Un PR por comando. Archivos: `management/commands/{procesar,enviar,reenviar,correr_alta,conciliar}_siis*.py`, `services/siis.py`, `services/siis_envio.py`. Los ERR son S; el rendimiento se confirma en el banco antes de tocar.

- **B-ERR-06** [MEDIA · S] El vaciado de la tabla intermedia registra el envío con el plan del programa, no el del payload
- **B-ERR-07** [MEDIA · S] `procesar_casos_siis` vacía TODA la tabla intermedia aunque se le pida una convocatoria, relevamiento o segmento
- **B-ERR-08** [MEDIA · S] `correr_alta_siis` pierde toda la salida del hijo cuando corta por freno o error
- **B-ERR-09** [MEDIA · S] `conciliar_envios_siis` acepta el mismo envío dos veces con decisiones opuestas y actualiza sin mirar el estado
- **B-ERR-10** [MEDIA · S] `_sentencias` parte mal un literal que termina en barra invertida escapada
- **B-PERF-07** [MEDIA · S] `enviar_casos_siis` y `reenviar_siis_pendientes` eligen candidatos en una sola consulta sin rangos de pk (el patrón que…
- **B-ERR-21** [BAJA · S] Una caída de Redis al leer el token deja el envío EN_PROCESO sin POST
- **B-ERR-22** [BAJA · S] Un catálogo vacío de SIIS queda en cache 24 h
- **B-ERR-23** [BAJA · S] `--ignorar-corrida` de `correr_alta_siis` no llega a los hijos y corta a mitad de camino
- **B-PERF-12** [BAJA · S-M] `correr_alta_siis` vuelve a hidratar y armar el payload de todos los incompletos en cada tanda (costo cuadrático en tan…
- **B-DAT-01** [BAJA · S] `correr_alta_siis` identifica el caso de prueba por diferencia contra todos los pk de EnvioSIIS: puede mostrar el envío…
- **B-PERF-18** [INFO · S] El drenaje de la tabla intermedia y el listado de inciertos traen los JSON del caso para usar pk, DNI y programa

### Ola 3 · Proceso masivo, cupo y alta de oficio (22 h, 10 fichas)

Archivos: `services/proceso_masivo.py`, `views/cupo.py`, `services/cupo.py`, `services/alta_de_oficio.py`, `management/commands/{inscribir_de_oficio,completar_casos_renaper}.py`. B-PERF-06 toca también `procesar_casos_siis.py`: va después de la Ola 2.

- **B-ERR-11** [MEDIA · S] Desde Cupo se encola y se aprueba un caso con conflicto de carga duplicada sin resolver
- **B-ERR-12** [MEDIA · S] Una caída de la conexión a la base deja la corrida masiva «en curso» sin motivo y el hilo muere con la excepción
- **B-PERF-06** [MEDIA · S-M] La corrida de `procesar_casos_siis` y el masivo de la pantalla retienen en memoria hasta `--total` casos con sus JSON
- **B-ERR-24** [BAJA · S] El cruce automático del padrón pisa validaciones y datos del legajo escritos mientras corre
- **B-ERR-25** [BAJA · S] El fallecimiento se busca en toda la respuesta de Base de Personas, no en el registro elegido
- **B-ERR-26** [BAJA · S] `completar_casos_renaper --aplicar` reescribe `data`/`respuestas`/`definicion` con una copia sin candado
- **B-PERF-19** [INFO · S] La corrida masiva lee los ids de **todos** los candidatos aunque pida 100
- **B-PERF-20** [INFO · S] `get_cupo_stats` cuenta los aprobados del segmento con el `Segmento` tomado en cada aprobación, sin medición en MariaDB
- **B-PERF-21** [INFO · S] `inscribir_de_oficio` resuelve el legajo y aprueba con el relevamiento público y la convocatoria tomados, y recorre el…
- **B-PERF-22** [INFO · S] `completar_casos_renaper` arma un `IN` con todos los ids de casos para averiguar las convocatorias

### Ola 4 · Dashboard y reportes: cifras y rendimiento (60 h, 15 fichas)

Archivos: `services/dashboard_becas.py`, `services/reportes_becas.py`, `views/dashboard_becas.py`, `forms_reportes.py`, `becas-dashboard.js`. Las fichas con decisión del cliente cambian cifras en pantalla: van con el texto del cliente en el PR.

- **B-ERR-04** [MEDIA · S] «Producción territorial» deja afuera los relevamientos que arrancan el último día del rango
- **B-ERR-05** [MEDIA · M] La distribución de una pregunta del catálogo cuenta respuestas que una condición ocultó
- **B-PERF-03** [MEDIA · S] El embudo cuenta la lista de espera con un DISTINCT sobre las 37 columnas del caso, JSON incluidos
- **B-PERF-04** [MEDIA · S-M] Distribución de un campo propio condicionado: una fila y una corrida del motor de condiciones por caso cuando la condic…
- **B-PERF-05** [MEDIA · S] Export del dashboard: una pasada sobre todo el recorte por cada campo propio de todas las convocatorias del programa, a…
- **B-LIM-14** [MEDIA · M] Dos embudos de revisión calculan las «mismas» etapas con definiciones distintas
- **B-LIM-15** [MEDIA · M] El cupo ocupado y el distribuido se calculan en tres lugares con alcances distintos
- **B-FE-05** [MEDIA · S-M] Las etiquetas de canal y estado se reescriben en cinco lugares y la exportación dice otra cosa que la pantalla
- **B-ERR-20** [BAJA · S] «Avance de convocatorias» cuenta con otras reglas de alcance que el resto de los reportes
- **B-PERF-10** [BAJA · S] El embudo agrupa los motivos en Python trayendo cada rechazo, y cada validación SIIS entera con su JSON `respuesta`
- **B-PERF-11** [BAJA · S] El catálogo de preguntas del dashboard se recalcula en cada request, con los ítems de todos los diseños del programa
- **B-PERF-15** [INFO · S] Reportes transversales: el alcance viaja como IN anidados (2-3 niveles) y el banco solo lo mide como admin
- **B-PERF-17** [INFO · S] Beneficiarios: la fecha de aprobación sale de una subconsulta sobre TracaFormulario sin índice útil, y el banco siembra…
- **B-PERF-25** [MEDIA · M] El XLSX de respuestas del dashboard tarda 18,7 s caliente / 27,8 s frío: el 75 % es openpyxl escribiendo 700.000 celdas
- **B-PERF-26** [MEDIA · S-M] El XLSX de beneficiarios hidrata Formulario + 4 relaciones por cada aprobado para usar 7 valores

### Ola 5 · Revisión y relevamientos (20 h, 10 fichas)

Archivos: `views/revision.py`, `views/relevamientos.py`, `selectors/convocatorias.py`. Correcciones S independientes.

- **B-ERR-02** [MEDIA · S] «Revalidar con Base de Personas» guarda el sexo sin normalizar y da 500 con `FEMENINO`/`MASCULINO`
- **B-ERR-03** [MEDIA · S] Editar el contacto del caso reescribe la fila entera y puede revertir una aprobación, un rechazo o una validación concu…
- **B-PERF-02** [MEDIA · S] El CSV de lista de espera carga y decodifica los JSON pesados de cada caso
- **B-FE-02** [MEDIA · S] Regla de «sexo de solo lectura» divergente: el template ofrece editar y la vista siempre rechaza
- **B-ERR-16** [BAJA · S] «Terminar revisión» cuenta los pendientes sin candado: una captura tardía puede quedar ENVIADA dentro de un relevamient…
- **B-ERR-17** [BAJA · S] El filtro «fecha hasta» del listado de relevamientos excluye los que empiezan ese mismo día
- **B-ERR-18** [BAJA · S] Los filtros `segmento` y `territorial` del listado de relevamientos dan 500 con un valor no numérico
- **B-ERR-19** [BAJA · S] El CSV de beneficiarios rotula como «Fecha de aprobación» la última modificación del caso, en día UTC
- **B-PERF-09** [BAJA · S] El detalle de convocatoria lista todos sus relevamientos sin paginar
- **B-PERF-14** [INFO · S] La tabla de casos del detalle de relevamiento pagina por OFFSET sobre filas anchas con join

### Ola 6 · Configuración, constructor y borrado en cascada (24 h, 8 fichas)

Archivos: `services/eliminacion.py`, `views/configuracion.py`, `services/diseno.py`, `services/constructor.py`. Los ERR de condiciones (M) piden test con motor real.

- **B-ERR-13** [MEDIA · S-M] La condición por defecto de un grupo del catálogo puede quedar detrás de su fuente y ocultar el grupo para siempre
- **B-ERR-14** [MEDIA · M] Cambiar el tipo u opciones de una pregunta o requisito fuente de condiciones deja condiciones imposibles en diseños gua…
- **B-ERR-27** [BAJA · S] La eliminación en cascada puede dejar vivo un hijo creado entre la lectura de ids y el bloqueo
- **B-ERR-28** [BAJA · S] `reconciliar` e `items_vigentes` asumen que cada regla de condición es un dict
- **B-ERR-29** [BAJA · S] `generar_por_defecto` no limpia `bajas_pendientes` y el siguiente `reconciliar` informa bajas viejas
- **B-PERF-13** [BAJA · S] Borrar un requisito, una pregunta general o un subsegmento con documentos cargados trae a memoria TODOS los adjuntos so…
- **B-PERF-23** [INFO · S] Borrar una pregunta general bloquea y reescribe el diseño de cada convocatoria en una sola transacción
- **B-DAT-02** [INFO · S] La baja lógica en cascada cuenta los casos con COUNT(*) mientras tiene tomada la fila de cada relevamiento

**Nota cruzada con Dispositivos (D-ERR-06 / D3-ERR-01, TOCTOU del constructor):** la vista de eliminar ítem de `programas/views/diseno.py:287` tiene el mismo defecto que `views/dispositivos_formularios.py:309-316`. La ficha D-ERR-06 de [dispositivos.md](dispositivos.md) cubre las dos: el PR que mueve la validación dentro de la operación que toma el candado (`services/constructor.py`, `motivo_para_no_eliminar`/`mutar`) arregla las dos vistas y lleva el test de Becas. No se abre ficha aparte en este informe (B-ERR-29 es otro defecto, `services/diseno.py:283`).

### Ola 7 · De fondo: servicio único de resolución del caso y de estados del relevamiento (72 h, 6 fichas)

Ola de fondo: servicio único de resolución del caso y de estados del relevamiento. Orden sugerido: (1) máquina de estados del relevamiento (B-LIM-02); (2) resolución del caso (B-LIM-01); (3) «aprobar → SIIS → aviso» (B-LIM-04); (4) contexto de detalles (B-LIM-03); (5) dominio en la API de campo (B-LIM-06); (6) catálogo y reordenamientos (B-LIM-05). Va DESPUÉS de las Olas 3, 5 y 6 (tocan los mismos archivos) y ANTES de la limpieza 11-13. B-LIM-02 es **DECISIÓN CLIENTE** (§7): unificar las reglas de estado del relevamiento en backoffice, API y cron; si se aprueba, va en un PR coordinado con Chaco-mobile que actualiza los tests de contrato RED-11/RED-03 en el mismo diff.

- **B-LIM-01** [ALTA · L] Resolución del caso (aprobar, rechazar, duplicado, identidad, SIIS) escrita en vistas
- **B-LIM-02** [ALTA · L] Máquina de estados de `Relevamiento` dispersa y con reglas divergentes (backoffice vs API)
- **B-LIM-03** [ALTA · M] Detalles de convocatoria y relevamiento arman el contexto y escriben estado en la vista
- **B-LIM-04** [ALTA · M] «Aprobar → informar a SIIS → avisar al ciudadano» está escrito tres veces, con orden y regla de SIIS distintos
- **B-LIM-05** [ALTA · M] Las reglas del catálogo y los reordenamientos escriben desde las vistas, no desde `services/`
- **B-LIM-06** [ALTA · M] La API de campo tiene el dominio del alta y de la identidad escrito en la vista

### Ola 8 · Limpieza SIIS (58 h, 14 fichas)

Archivos: `services/siis_envio.py` (1.518 líneas), `services/siis.py`, `management/commands/_base_siis.py` y los comandos. Un PR por responsabilidad extraída.

- **B-LIM-20** [MEDIA · M] `siis_envio.py` tiene 1.518 líneas y mezcla seis responsabilidades
- **B-LIM-21** [MEDIA · S-M] El bucle «lote → caso → freno → línea de avance → pausa» está copiado en tres comandos (y un cuarto en el masivo)
- **B-LIM-22** [MEDIA · S] Tres comandos de la integración no heredan `ComandoSiisBase` y reescriben sus guardas
- **B-LIM-23** [MEDIA · S] Las precondiciones de `correr_alta_siis` reimplementan con otra regla lo que lee `armar_payload` y frenan circuitos que…
- **B-LIM-24** [MEDIA · S-M] `enviar_beneficiario_a_siis` y `guardar_en_tabla_intermedia` duplican el preámbulo, y el `EnvioSIIS` cerrado se arma a…
- **B-LIM-25** [MEDIA · M] El resultado del cliente SIIS es un dict sin contrato, y el consumidor tiene una rama para mocks
- **B-LIM-26** [MEDIA · S-M] La política del drenaje de la tabla intermedia (cuándo frenar y qué hacer después) vive en `procesar_casos_siis`, y su…
- **B-LIM-27** [MEDIA · M] Cuatro comandos de alta que se solapan: `enviar_casos_siis` y `reenviar_siis_pendientes` son modos de `procesar_casos_s…
- **B-LIM-52** [BAJA · S-M] `armar_payload` (160 líneas) repite nueve veces «resolver → payload o faltante»
- **B-LIM-53** [BAJA · S-M] El cliente repite la invalidación del token, el corte de configuración y la normalización de ítems
- **B-LIM-54** [BAJA · S-M] La pausa del login convierte la excepción en un string y la vuelve a fabricar, con `requests.Response` falsos
- **B-LIM-55** [BAJA · S] `siis.py` (986 líneas, al borde del umbral) mezcla el cliente HTTP con la persistencia de catálogos en la base
- **B-LIM-56** [BAJA · S] `_localidades_csv_siis.py` es dominio escondido en `management/commands`, con `CommandError` y una segunda copia de la…
- **B-LIM-57** [BAJA · S] Alias históricos, imports perezosos sin motivo y códigos de error sin constante

### Ola 9 · Limpieza masivo, cupo y padrón (46 h, 15 fichas)

Archivos: `services/proceso_masivo.py` (1.191 líneas), `services/cupo.py`, `views/cupo.py`, `services/alta_de_oficio.py`.

- **B-LIM-28** [MEDIA · M] `services/proceso_masivo.py` tiene 1.191 líneas y cuatro responsabilidades
- **B-LIM-29** [MEDIA · S-M] Normalización de DNI, sexo y fecha reescrita fuera de sus canónicas (y una contradice a la otra)
- **B-LIM-30** [MEDIA · S-M] «Completar el legajo solo donde está vacío» está tres veces, y `alta_de_oficio` importa privados de `becas`
- **B-LIM-31** [MEDIA · S-M] `completar_casos_renaper` lleva dominio dentro del comando y clona `sincronizar_desde_legacy`
- **B-LIM-32** [MEDIA · S-M] La vista de Cupo arma el alcance y las tres consultas en `get_context_data` (115 líneas)
- **B-LIM-33** [MEDIA · S-M] `candidatos()` tiene 11 parámetros, 6 de ellos banderas que se combinan
- **B-LIM-58** [BAJA · S] Las tres acciones de Cupo repiten el prólogo de autorización y no exigen POST
- **B-LIM-59** [BAJA · S] Los desenlaces de la aprobación viajan como strings sueltos en seis módulos
- **B-LIM-60** [BAJA · S] La aprobación con cupo está escrita tres veces en `cupo.py`
- **B-LIM-61** [BAJA · S] `correr()` repite cinco veces el cierre de la corrida y `_lotes` existe cinco veces en `programas`
- **B-LIM-62** [BAJA · S] Lanzar el masivo lee la planilla entera solo para saber si existe; tres formas de preguntar por una tabla
- **B-LIM-63** [BAJA · S] Ciclo `proceso_masivo` ↔ `siis_envio` escondido con un import diferido
- **B-LIM-64** [BAJA · S] `inscribir_de_oficio` reimplementa dos veces el freno por errores seguidos
- **B-FE-12** [BAJA · S] La pantalla de Cupo reimplementa la confirmación canónica (tres funciones y un form oculto por fila)
- **B-FE-13** [BAJA · S] Las plantillas del aviso deciden el texto comparando literales, duplicado entre `.txt` y `.html`

### Ola 10 · Limpieza dashboard y reportes (56 h, 12 fichas)

Archivos: `services/dashboard_becas.py` (1.780 líneas), `services/reportes_becas.py`, `services/exportacion_reportes.py`, `becas-dashboard.js`.

- **B-LIM-13** [MEDIA · L] `dashboard_becas.py` concentra cinco servicios en 1.780 líneas y sigue creciendo
- **B-LIM-16** [MEDIA · S-M] La fila «avance por convocatoria» se calcula dos veces (dashboard y reporte de avance)
- **B-LIM-17** [MEDIA · S-M] La lectura canónica de respuestas vive en el dashboard y la importa el envío a SIIS
- **B-LIM-18** [MEDIA · S-M] Política de autorización y de freno del dashboard escrita en la vista
- **B-LIM-19** [MEDIA · M] El registro de reportes está repartido en tres lugares y tiene un caso especial
- **B-LIM-47** [BAJA · S] La huella del alcance se calcula en dos lugares y cada entrada puede volver a resolver el alcance
- **B-LIM-48** [BAJA · S] Copia y pega dentro de `reporte_produccion` y `reporte_avance`
- **B-LIM-49** [BAJA · S] Tres escritores del mismo CSV/XLSX en `exportacion_reportes.py` y artefacto de la conversión a LF
- **B-LIM-50** [BAJA · S-M] El contrato de `Datos` son dicts sueltos que tres consumidores leen por nombre
- **B-LIM-51** [BAJA · S] El form del dashboard resuelve el catálogo de dominio y arma JSON de presentación
- **B-FE-10** [BAJA · S] El JS reconstruye estructura partiendo textos compuestos por el servidor
- **B-FE-11** [BAJA · S] Porcentajes y umbrales de cupo recalculados en el JS

### Ola 11 · Limpieza revisión y relevamientos (58 h, 11 fichas)

Archivos: `views/revision.py` (1.385 líneas), `views/relevamientos.py` (1.213), `selectors/revision.py`, `services/solapas.py`, templates de revisión. Después de la Ola 7: la extracción de la resolución achica `revision.py`. La ficha de helpers compartidos (B-LIM-46) toca también dashboard y reportes.

- **B-LIM-07** [MEDIA · M] `views/revision.py` pasa de 1.000 líneas (1.385) y sigue creciendo
- **B-LIM-08** [MEDIA · M] `views/relevamientos.py` pasa de 1.000 líneas (1.213)
- **B-LIM-09** [MEDIA · S-M] Resolución «persona del caso» (`ciudadano` o `datos_identificacion`) copiada ~15 veces
- **B-LIM-10** [MEDIA · S] Tres validadores de `next` con reglas distintas
- **B-LIM-11** [MEDIA · S-M] `selectors/revision.py` construye formularios, evalúa permisos y duplica un contrato de 13 claves
- **B-LIM-12** [MEDIA · M] `services/solapas.py`: clase-namespace que mezcla lectura, escritura, presentación y lógica de producto
- **B-FE-01** [MEDIA · S-M] Mapeos de estado → etiqueta/tono y decisiones de dominio escritos en templates
- **B-FE-03** [MEDIA · M] JS inline del detalle de revisión duplicado (toggles, selects dependientes, modales, guarda de doble envío)
- **B-FE-04** [MEDIA · S-M] Formulario «Nuevo relevamiento» triplicado con divergencias
- **B-LIM-46** [BAJA · S-M] Helpers duplicados dentro de `programas` (paginación, hidratación, marcas, fechas, porcentajes, lotes, URL base)
- **B-FE-09** [BAJA · S-M] 23 evaluaciones de `|puede:"..."` en templates del alcance que repiten decisiones de la vista

### Ola 12 · Limpieza configuración y constructor (86 h, 16 fichas)

Archivos: `views/configuracion.py` (1.351 líneas), `forms.py` (2.525), `forms_dinamicos.py`, JS del constructor. Después de la Ola 7.

- **B-LIM-34** [MEDIA · M] `views/configuracion.py` pasa las 1.000 líneas con cinco ABMs en un solo módulo
- **B-LIM-35** [MEDIA · S-M] La misma regla de activación vive en el form **y** en la vista, con mensajes y defensas distintas
- **B-LIM-36** [MEDIA · M] El «nivel» de un requisito (programa/segmento/subsegmento) se despacha con `if/elif` en ocho lugares
- **B-LIM-37** [MEDIA · S] Aristas vista→vista y nombres privados cruzando módulos que se pueden borrar hoy
- **B-LIM-38** [MEDIA · S-M] El pegamento HTTP del constructor está copiado entre Becas y Dispositivos
- **B-LIM-39** [MEDIA · M] «El diseño sigue al catálogo» está escrito dos veces: `reconciliar` y `items_vigentes`
- **B-LIM-40** [MEDIA · L] `programas/forms.py` tiene 2.525 líneas y mezcla Becas, SIIS y Dispositivos
- **B-FE-06** [MEDIA · S-M] El editor de condiciones está copiado entero dentro de un atributo `x-data`, y ya divergió
- **B-FE-07** [MEDIA · S-M] La paridad Python↔JS cubre el motor de condiciones, pero no el filtro por canal, que tiene dos copias JS
- **B-FE-08** [MEDIA · M] El modal de requisito está duplicado en cuatro pantallas y ya difiere entre ellas
- **B-LIM-65** [BAJA · S-M] Cada vista bifurca AJAX/clásico a mano y `subsegmento_crear/editar` repiten el mismo bloque
- **B-LIM-66** [BAJA · S] `forms_dinamicos`: el tipo de campo se compara contra cadenas sueltas en una cadena de `if`
- **B-LIM-67** [BAJA · S-M] Dos modelos de borrado para la misma jerarquía de Becas
- **B-LIM-68** [BAJA · S] `gestionar_pausa` resuelve el alcance con `isinstance` en la vista y arrastra un desfasaje de nombres
- **B-FE-14** [BAJA · S] Dos lectores DOM→respuestas para el mismo motor, uno sin el caso del archivo ya guardado
- **B-FE-15** [BAJA · S] JS inline en templates de configuración y helpers reimplementados por archivo

### Ola 13 · Limpieza app de campo y link público (58 h, 12 fichas)

Archivos: `api/views.py` (923 líneas), `api/serializers.py`, `services/autorizacion.py`, `services/becas.py`, `services/campo.py`, `nodo-firma.js`, `nodo-cascada-geo.js`. Después de la Ola 7.

- **B-LIM-41** [MEDIA · L] Dos caminos para crear un caso (app de campo y link público) con el mismo esqueleto y reglas que ya divergen
- **B-LIM-42** [MEDIA · S] «Qué origen acredita identidad» está escrito en seis lugares aunque existe la constante canónica
- **B-LIM-43** [MEDIA · M] `FormularioSerializer.validate` hace el dominio del alta y le pasa resultados a la vista por `self.context`
- **B-LIM-44** [MEDIA · S-M] Traducir respuestas a columnas fijas e identidad está escrito tres veces, con la misma regla de default copiada
- **B-LIM-45** [MEDIA · M] `autorizacion.py` repite la precedencia de roles en cinco funciones, en dos órdenes distintos, y mezcla cuatro responsa…
- **B-LIM-69** [BAJA · S-M] `programas/services/becas.py` es un cajón de sastre: definición, lookups por UUID, alcance, trazas y legajo
- **B-LIM-70** [BAJA · S] Tres escrituras de «el caso que ocupa este DNI» y envoltorios que solo renombran
- **B-LIM-71** [BAJA · S] Coherencia Provincia-Localidad: el link valida contra la caché y la API contra la base viva
- **B-LIM-72** [BAJA · S] El paso 2 del link arma las respuestas dos veces con el mismo bucle
- **B-LIM-73** [BAJA · S] Las migas de Becas duplican la capacidad que pide cada vista de destino
- **B-FE-16** [BAJA · S] `nodo-firma.js` observa todo el documento y recorre el DOM en cada mutación de cualquier página
- **B-FE-17** [BAJA · S] `nodo-cascada-geo.js` depende del orden de carga de `nodo-formulario.js` y mide layout en cada `change` de cualquier ca…

## 4. Reglas para no repetirlo (consolidadas)

Una fila por regla distinta: **76 reglas** (28 control mecánico, 39 skill, 9 checklist) para 151 fichas activas. «Ya existe»: **Sí** = la regla ya está en el repo; **Parcial** = existe el mecanismo o el archivo destino, falta la regla; **No** = nueva. Se verificó contra el SHA auditado: `test_arquitectura.py` (ratchets RED-79), `test_sql_portable.py`, `test_regla_dni.py`, ruff `E,F,W,I,DTZ011`, mypy sobre 3 archivos, `design_audit.py` (HEX solo en templates) y las skills `codigo-limpio.md`, `rendimiento.md`, `mysql-mariadb`, `seguridad-django`. En las reglas de una sola ficha el texto es el de la ficha.

| # | Tipo | Regla | Destino | Ya existe | Fichas |
|---|---|---|---|---|---|
| R01 | control mecánico | Ningún módulo de `programas/` pasa las 1.000 líneas; ratchet con lista congelada que solo baja | `core/tests/test_tamano_modulos.py` (nuevo) | Parcial: la regla está en `auditoria/rubricas/codigo-limpio.md` (regla 1); falta el test | B-LIM-07, B-LIM-08, B-LIM-13, B-LIM-20, B-LIM-28, B-LIM-34, B-LIM-40, B-LIM-55 |
| R02 | control mecánico | La escritura de dominio (`.save/.update/.delete`, `select_for_update`, `transaction.atomic`) en `views/**` y `api/**` solo puede bajar | `programas/tests/test_arquitectura.py` | Parcial: el archivo y el patrón de ratchet existen (RED-79) | B-LIM-01, B-LIM-05, B-LIM-06 |
| R03 | control mecánico | `relevamiento.estado =` solo se asigna en `services/relevamientos.py` | `programas/tests/test_arquitectura.py` | No | B-LIM-02 |
| R04 | control mecánico | Ciclos de import y aristas entre capas solo bajan (RED-79), extendido a servicio→vista y a lecturas canónicas fuera de su dueño | `programas/tests/test_arquitectura.py` (`CICLOS_CONOCIDOS`, `ARISTAS_CONOCIDAS`) | Sí (vista→vista y ciclos; el techo ya baja solo); falta la extensión | B-LIM-17, B-LIM-18, B-LIM-63 |
| R05 | control mecánico | No importar nombres privados (`_x`) de otro módulo | `pyproject.toml` ruff `PLC2701` | No | B-LIM-30, B-LIM-37, B-LIM-72 |
| R06 | control mecánico | Imports dentro de funciones solo con excepción declarada | `pyproject.toml` ruff `PLC0415` | No | B-LIM-57 |
| R07 | control mecánico | Un comando de management es un envoltorio del servicio: sin consultas ni escrituras de dominio propias | `programas/tests/test_arquitectura.py` | No | B-LIM-26, B-LIM-27, B-LIM-31, B-LIM-56 |
| R08 | control mecánico | Los comandos SIIS heredan las guardas (alcance, pausa, «no enviar», ensayo) de `ComandoSiisBase` y todas las vías las aplican | `programas/tests/test_base_siis.py` (nuevo) sobre `_base_siis.py` | Parcial: `ComandoSiisBase` existe; las guardas no | B-LIM-22, B-ERR-23 |
| R09 | control mecánico | Los servicios SIIS entran al alcance de mypy, un archivo por PR | `pyproject.toml` `[tool.mypy] files` | Parcial: mypy corre sobre 3 archivos | B-LIM-25 |
| R10 | control mecánico | Una respuesta de error que lleva texto de la request sale como `text/plain` o escapada | `core/tests/` (ratchet AST junto a RED-79) | No (el caso puntual se arregló en #1202) | B-SEG-01 |
| R11 | control mecánico | DNI, sexo y origen de identidad se normalizan solo con los helpers y constantes canónicos | `core/tests/test_regla_dni.py` extendido | Parcial: el test de la regla DNI existe | B-ERR-02, B-LIM-29, B-LIM-42 |
| R12 | control mecánico | Rangos de fecha en hora local; nada de `__date`/`Trunc*` sobre `DateTimeField` | `core/tests/test_sql_portable.py` extendido | Parcial: el test de SQL portable existe | B-ERR-04, B-ERR-17, B-ERR-19 |
| R13 | control mecánico | Exports y listados no leen los JSON pesados del caso (`data`, `definicion`, `respuesta`) si no los usan: `values()`/`only()` y presupuesto de consultas | `scripts/perf_budgets.json` + tests `--tag performance` | Parcial: hay presupuesto para `respuestas_por_persona` | B-PERF-02, B-PERF-03, B-PERF-18, B-PERF-26 |
| R14 | control mecánico | Todo export XLSX/CSV de volumen entra al banco con presupuesto de ms caliente | `scripts/perf_mysql/bench_mysql.py` + `scripts/perf_budgets.json` | Parcial: las rutas están en el banco; los presupuestos de exports del dashboard no | B-PERF-05, B-PERF-25 |
| R15 | control mecánico | Sección crítica mínima: dentro de `select_for_update` solo la lectura que garantiza la regla; se mide con N sesiones en el banco | banco `scripts/perf_mysql/` + `mysql-mariadb/SKILL.md` §Transacciones | Parcial: la skill tiene «transacciones cortas, externos fuera del lock»; falta la medición con N sesiones | B-PERF-01, B-PERF-08, B-PERF-20, B-PERF-21, B-DAT-02 |
| R16 | control mecánico | Comandos y corridas masivas iteran por lotes acotados y no retienen la lista entera de casos | test de presupuesto de memoria/consultas en `programas/tests/` | No | B-PERF-06, B-PERF-07, B-PERF-12, B-PERF-19 |
| R17 | control mecánico | Un `IN` con más de 1.000 literales se parte en lotes o pasa a subconsulta | `core/tests/test_sql_portable.py` o `mysql-mariadb/SKILL.md` §Consultas | No | B-PERF-22 |
| R18 | control mecánico | Colores hex solo en tokens: HEX también en Python (`services/`) | `scripts/design_audit.py` | Parcial: HEX solo mira templates | B-LIM-12 |
| R19 | control mecánico | Sin `<script>` inline con lógica en templates | `scripts/design_audit.py` (regla nueva SCRIPT-INLINE) | No | B-FE-03, B-FE-15 |
| R20 | control mecánico | `x-data` sin lógica larga en el atributo | `scripts/design_audit.py` (regla nueva XDATA) | No | B-FE-06 |
| R21 | control mecánico | Sin el modal legado `ModernModal` | `scripts/design_audit.py` | No | B-FE-12 |
| R22 | control mecánico | Los templates preguntan por capacidad con `|puede`, no por grupo ni por lista de capacidades a mano | `scripts/design_audit.py` | No | B-FE-09 |
| R23 | control mecánico | «Todo campo del catálogo que alimenta `condiciones` tiene test de “cambio con dependientes → rechazo”.» | test de contrato en `programas/tests` | No | B-ERR-14 |
| R24 | control mecánico | grep de `datos_identificacion.get(` / `datos_identificacion.` en `programas/views` y `templates` con ratchet a 0. | `test_arquitectura.py` | Parcial: el destino existe | B-LIM-09 |
| R25 | control mecánico | `url_has_allowed_host_and_scheme` solo aparece en el helper. | `test_arquitectura.py` | Parcial: el destino existe | B-LIM-10 |
| R26 | control mecánico | `programas/selectors/**` no importa de `programas.forms` ni llama a `puede(`. | `test_arquitectura.py` | Parcial: el destino existe | B-LIM-11 |
| R27 | control mecánico | Cada `TipoCampo` tiene su fábrica; uno sin fábrica hace fallar el test | `programas/tests/test_forms_dinamicos.py::FabricaTests.test_cada_tipo_tiene_fabrica` | No | B-LIM-66 |
| R28 | control mecánico | Cada miga pide la misma capacidad que la vista de destino | `programas/tests/test_becas_migas.py::MigasTests.test_cada_miga_pide_lo_mismo_que_su_vista` | No | B-LIM-73 |
| R29 | skill | Estados y mensajes del dominio son constantes, no strings sueltos | `auditoria/rubricas/codigo-limpio.md` | No | B-LIM-59, B-LIM-60 |
| R30 | skill | Tabla «Helpers canónicos»: agregar los helpers que hoy se copian (`_aware_start`, rango por `creado`, `_pct`, `_lotes`, parseo de `capturado_en`, lectura de respuestas, origen de identidad…) | `auditoria/rubricas/codigo-limpio.md` «Helpers canónicos» | Parcial: la tabla existe (rbac, `q_uuid_en_texto`, migraciones, toast…) | B-LIM-04, B-LIM-21, B-LIM-23, B-LIM-24, B-LIM-41, B-LIM-44, B-LIM-45, B-LIM-46, B-LIM-53, B-LIM-61, B-LIM-64, B-LIM-65, B-LIM-67, B-LIM-68, B-ERR-06 |
| R31 | skill | Una cifra = una función: pantalla, reporte y export la comparten | `auditoria/rubricas/codigo-limpio.md` | No | B-ERR-05, B-ERR-20, B-LIM-14, B-LIM-15, B-LIM-16, B-FE-11 |
| R32 | skill | Las lecturas de las vistas van a `selectors/` | `auditoria/rubricas/codigo-limpio.md` (capas) | No | B-LIM-03, B-LIM-32 |
| R33 | skill | Forms y serializers validan forma; el dominio va a `services/` | `auditoria/rubricas/codigo-limpio.md` (capas) | No | B-LIM-43, B-LIM-51 |
| R34 | skill | La repetición se declara como datos (tabla, `dataclass`) en vez de `if` repetidos | `auditoria/rubricas/codigo-limpio.md` | No | B-LIM-19, B-LIM-48, B-LIM-50, B-LIM-52 |
| R35 | skill | Dos implementaciones de la misma regla (Python/JS, link/app) comparten vectores de prueba | `auditoria/rubricas/codigo-limpio.md` (RED-38) | No | B-LIM-39, B-LIM-71, B-FE-07, B-FE-14 |
| R36 | skill | Leer-modificar-escribir: `UPDATE` condicional o lock antes de leer | `mysql-mariadb/SKILL.md` §Transacciones | Parcial: la sección existe sin este caso | B-ERR-03, B-ERR-09, B-ERR-24, B-ERR-26 |
| R37 | skill | Lo que depende de los hijos se decide con el padre tomado | `mysql-mariadb/SKILL.md` §Transacciones | Parcial: la sección existe (orden de candados) | B-ERR-16, B-ERR-27 |
| R38 | skill | JSON de entrada se lee con un helper que valida tipo (objeto) y da 400 | `seguridad-django/SKILL.md` | No | B-ERR-28, B-ERR-30 |
| R39 | skill | Caché de catálogo externo con anti-estampida (`cache.add`) y sin consulta en vivo | `rendimiento.md` «Trampas medidas» | No | B-ERR-22, B-PERF-24 |
| R40 | skill | Ninguna superficie anónima escribe en legajos sin identidad validada | `seguridad-django/SKILL.md` §2 | Parcial: §2 cubre superficies anónimas con token, no la escritura al legajo | B-SEG-02, B-SEG-04 |
| R41 | skill | El banco mide con cardinalidad real y con un actor no admin | `rendimiento.md` «Búsquedas activas» | No | B-PERF-15, B-PERF-17 |
| R42 | skill | Listados por página pk-first + hidratación (`listados.hidratar_pagina`) | `rendimiento.md` trampa 4 | Sí | B-PERF-09, B-PERF-14 |
| R43 | skill | Templates y JS deciden por flags y claves, no por strings de estado o etiquetas | `auditoria/rubricas/codigo-limpio.md` | No | B-FE-01, B-FE-02, B-FE-05, B-FE-13 |
| R44 | skill | Un modal o formulario repetido es un include | `.claude/agents/chaco-design-system.md` | No | B-FE-04, B-FE-08 |
| R45 | skill | «Todo recurso finito que se consume desde la superficie anónima (cupo, turnos) se puede agotar con captchas resueltos: definir qué estados lo liberan.» | `.claude/skills/seguridad-django/` (inscripción pública) | Parcial: el destino existe | B-SEG-03 |
| R46 | skill | «Código que corre fuera de un request (hilos, comandos largos) y captura `OperationalError` llama a `connection.close_if_unusable_or_obsolete()` antes de volver a usar la base: Django solo lo hace solo al principio y al final de… | `.claude/skills/mysql-mariadb/SKILL.md` | Parcial: el destino existe | B-ERR-12 |
| R47 | skill | «Un invariante entre filas (orden, pertenencia) se valida en el servicio, no en un solo form: toda escritura que mueva cualquiera de las filas pasa por la misma función.» | `.claude/skills/seguridad-django` (sección de invariantes) | Parcial: el destino existe | B-ERR-13 |
| R48 | skill | «Toda guarda temporal de la API de campo evalúa la hora de la captura (`capturado_en`, o `creado` como respaldo), nunca `now()`: la sincronización llega tarde por diseño y un 4xx es permanente en la app.» | `.claude/skills/auditoria/rubricas/` (ERR) | No | B-ERR-15 |
| R49 | skill | «Un GROUP BY sobre valores JSON solo es barato si la cardinalidad es chica: agrupar por un texto libre, una fecha o un número devuelve una fila por caso. Proyectar al dato que la regla necesita (presencia, rango) antes de agrupa… | `.claude/skills/mysql-mariadb/SKILL.md` §Consultas | Parcial: el destino existe | B-PERF-04 |
| R50 | skill | «una función de selección con más de tres banderas booleanas se parte en filtros con nombre». | `rubricas/codigo-limpio.md` regla 2 | Parcial: el destino existe | B-LIM-33 |
| R51 | skill | «Si una vista importa constantes de mensaje de un form (`from programas.forms import MSG_…`), la regla está duplicada: el dueño es un servicio y los dos lo llaman.» | `rubricas/codigo-limpio.md` | Parcial: el destino existe | B-LIM-35 |
| R52 | skill | «Un mismo string discriminador (`nivel`, `tipo`, `scope`) evaluado con `if/elif` en tres o más funciones es un modelo que falta: un objeto con los métodos, no más ramas.» | `rubricas/codigo-limpio.md` | Parcial: el destino existe | B-LIM-36 |
| R53 | skill | «Cuando una pieza tiene dos dueños (constructor de Becas y de Dispositivos), lo que no depende del dueño —incluido el parseo del payload— vive en el servicio compartido; cada vista pone solo acceso, URLs y contexto.» | `rubricas/codigo-limpio.md` | Parcial: el destino existe | B-LIM-38 |
| R54 | skill | «Todo id que llega por GET a un `filter(..._id=…)` pasa por `isdigit()` o por un form: un `ValueError` del ORM es un 500». | `.claude/skills/auditoria/rubricas/` | No | B-ERR-18 |
| R55 | skill | «Toda conclusión sobre una persona a partir de una respuesta externa se lee del registro atribuido a su DNI/sexo, nunca de un aplanado de la respuesta entera». | `.claude/skills/seguridad-django/SKILL.md` (datos personales) | Parcial: el destino existe | B-ERR-25 |
| R56 | skill | «`Counter(... for x in qs)` sobre filas del recorte: el conteo va en `values().annotate(Count)`». | `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas activas | Parcial: el destino existe | B-PERF-10 |
| R57 | skill | «Lo que se cachea por RN-17 incluye armar el form: un `__init__` que consulta corre también en los cache hits». | `.claude/skills/auditoria/rubricas/rendimiento.md` | Parcial: el destino existe | B-PERF-11 |
| R58 | skill | «No uses `ProtectedError.protected_objects` para contar: Django materializa todas las filas protegidas, con todas sus columnas y el `ordering` del modelo. Si el mensaje necesita un número, contalo antes con `values(fk).distinct(… | `.claude/skills/mysql-mariadb/SKILL.md` §Consultas | Parcial: el destino existe | B-PERF-13 |
| R59 | skill | «`set(Modelo.objects.values_list("pk"))` + `exclude(pk__in=...)` para encontrar lo que creó el paso anterior: usar el máximo pk previo y un filtro por autor; la diferencia de conjuntos crece con la tabla y se confunde con lo que… | `.claude/skills/auditoria/rubricas/rendimiento.md`, Búsquedas activas | Parcial: el destino existe | B-DAT-01 |
| R60 | skill | «Un parámetro opcional con `x or recalcular_x()` sobre un invariante de una vez por petición es un fallback silencioso: hacelo obligatorio». | `codigo-limpio.md` | Parcial: el destino existe | B-LIM-47 |
| R61 | skill | «Un segundo camino de salida (streaming, otra hoja) se escribe componiendo el primero, no copiándolo». | `codigo-limpio.md` | Parcial: el destino existe | B-LIM-49 |
| R62 | skill | «No fabricar objetos de una librería (`Response`, `HTTPError`) para reutilizar un `except`: un estado propio lleva su excepción propia.» | rúbrica `codigo-limpio.md` | Parcial: el destino existe | B-LIM-54 |
| R63 | skill | «vista que muta → `@require_POST`». | `.claude/skills/seguridad-django/` | Parcial: el destino existe | B-LIM-58 |
| R64 | skill | «chequear existencia por excepción de una lectura completa es un anti-patrón; usar el predicado». | `rubricas/codigo-limpio.md` | Parcial: el destino existe | B-LIM-62 |
| R65 | skill | «Un módulo de `services/` se nombra por el concepto que posee; `becas.py`/`utils.py` no reciben funciones nuevas». | `codigo-limpio.md` | Parcial: el destino existe | B-LIM-69 |
| R66 | skill | «Un `def _x(...): return y(...)` o `x = y` sin argumento ni transformación propia se borra en la revisión». | `codigo-limpio.md`, regla 4 | Parcial: el destino existe | B-LIM-70 |
| R67 | skill | «Señales `pre_delete`/`post_save` del catálogo que recorren diseños o convocatorias en un bucle: contar las consultas por fila afectada.» | `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas activas | Parcial: el destino existe | B-PERF-23 |
| R68 | checklist | Toda vía de aprobación o alta a SIIS reutiliza las guardas del masivo | `auditoria/rubricas/` (checklist de SIIS) | No | B-ERR-01, B-ERR-11 |
| R69 | checklist | todo paso que llame a SIIS dentro de un comando con filtros de alcance respeta esos filtros. Si no los respeta, lo dice en el ensayo con el número de casos. | checklist de revisión (`auditoria/rubricas/`) | No | B-ERR-07 |
| R70 | checklist | toda captura de salida de un subcomando se vuelca en `finally`. | checklist de revisión (`auditoria/rubricas/`) | No | B-ERR-08 |
| R71 | checklist | un solo tokenizador de SQL para los dos helpers. | checklist de revisión (`auditoria/rubricas/`) | No | B-ERR-10 |
| R72 | checklist | antes del POST, cualquier excepción es «no enviado». Después del POST, es «incierto». | checklist de revisión (`auditoria/rubricas/`) | No | B-ERR-21 |
| R73 | checklist | revisor · «Toda operación que reemplaza un agregado resetea su estado derivado.» | agente | No | B-ERR-29 |
| R74 | checklist | `.claude/agents/chaco-frontend.md` · «Si el JS necesita partes, el servidor manda una lista; nunca `split` sobre un texto armado en Python». | agente | No | B-FE-10 |
| R75 | checklist | `.claude/agents/chaco-frontend.md`: «Un `MutationObserver` sobre `document` filtra `addedNodes` por el selector propio; no recorre el documento entero por mutación». | agente | No | B-FE-16 |
| R76 | checklist | `.claude/agents/chaco-frontend.md`: «Un script que depende de que otro haya corrido escucha un evento nombrado (`nodo:*`) que ese otro emite; nunca el orden de los `<script>`». | agente | No | B-FE-17 |

## 5. Descartados

- **Refutados:** ninguno todavía. Los `REFUTADO` los agrega la pasada 2 con el motivo, para que nadie los reintroduzca.
- **Cruce con `auditoria-2026-10` (§0.4, §8 y `hallazgos/`): hecho el 19-nov.** Cambiaron 14 fichas: 1 pasa a descartada (B-PERF-16), 1 nueva cita y reabre un descarte de octubre con un hecho medido (B-PERF-25) y 12 actualizan «Origen» con el hallazgo abierto de octubre: B-SEG-04, B-PERF-02, B-PERF-03, B-PERF-18, B-PERF-06, B-FE-07, B-FE-14, B-LIM-43, B-PERF-13, B-SEG-03, B-LIM-70, B-PERF-14. Las demás coincidencias con §8 ya estaban tratadas en su ficha con el hecho nuevo (B-PERF-01 vs A4-04, B-PERF-18 vs A4-12, B-PERF-08 y B-PERF-20 vs PERF-12/contador, B-LIM-10 vs RS-R4-01).
- **Descartada por el cruce con octubre: B-PERF-16** (IN de más de 1.000 relevamientos convertido en tabla derivada en el dashboard). PERF-13 de octubre midió el mismo mecanismo (`relevamiento_id IN (2.001 ids)` → `<subquery2>` materializada, órdenes de magnitud debajo del `read_timeout`) y escribió «no abre ficha nueva» (`hallazgos/04-performance.md:522-527`). La ficha no trae medición nueva. Se reabre solo si el banco con 1.500 relevamientos (§8.c) muestra `dashboard_becas_datos` por encima del umbral. La ficha queda abajo, fuera de los totales.
- **Archivos sin uso (verificado en el SHA auditado):** `programas/templatetags/merenderos.py` (`racion`, `observacion`, `total`) **no tiene uso**: ningún template hace `{% load merenderos %}` y ningún `.py` lo importa; el servicio del circuito (`programas/services/merenderos.py`) ya no existe y el último cambio del archivo es `36e728f54` (circuito de merenderos). Fuera del alcance de Becas: candidato a borrar en el PR de limpieza que corresponda. `programas/selectors/emergencia_llegadas.py` **sí se usa** (`views/emergencia_dispositivo.py:57`); este informe no lo listaba como muerto, así que no hubo nada que corregir.
- **Revisado sin hallazgo** (los revisores de performance lo dejaron escrito para no repetirlo):
  - `RevisionPersonasListView`, `revision_formularios`, `RenaperPendientesListView`, `formulario_detalle` y `selectors/revision.py`: página por pk + hidratación, índices usables, `select_for_update` por pk; medidos en el banco.
  - `convocatoria_export_beneficiarios` y `convocatoria_export_relevamientos`: crecen con los casos pero sin evidencia de costo.
  - `RelevamientoListView`, `convocatorias_listado_qs`, `services/solapas.py`, `services/listados.py`: sin hallazgos de performance.
  - `proceso_masivo.procesar_caso/correr`, `avisos_resolucion`, `personas.py`, `vencimientos.py` (cron 03:10), `marca_de_oficio.py`, `cerrar_espera_colgada`: ninguna llamada a SIIS ni correo dentro de una transacción; orden de candados sin ciclo.
  - Listados de configuración, pausas, constructor, condiciones y formularios dinámicos, `forms.py` (parte Becas) y el JS del constructor: no leen casos o están acotados por el catálogo.
  - `autorizacion.py`, `becas_extras.py`, búsquedas por UUID (`q_uuid_en_texto`), `dni_en_convocatoria`, listados de la API (acotados por cupo), correo de confirmación sincrónico fuera del lock.
  - Notas INFO de la tajada SIIS sin ficha: docstring de `siis_sync.py:87-91` («solo escribe los que cambiaron»), el ensayo de `reenviar_siis_pendientes` imprime el DNI en consola, `procesar_casos_siis.py:271-273` compara con `str(dni)` en el ensayo (solo desvía el número del ensayo).
  - Rechazado por el juez como de seguridad: acciones de Cupo sin `@require_POST` (B-LIM-58): la escritura está dentro de `if request.method == "POST"`; queda BAJA.


#### B-PERF-16 (DESCARTADA) · Dashboard: con 1.000 relevamientos o más en el alcance, MariaDB vuelve a convertir el IN plano en una subconsulta
**Severidad:** INFO · **Estado:** DESCARTADO (cruce con octubre) · **Eje:** PERF · **Origen:** PERF-13 (oct.) · **Ola:** 4 · **Esfuerzo:** S
- **ID de la pasada 1:** B2-PERF-07
- **Ubicación:** `programas/services/dashboard_becas.py:281` (todos los relevamientos del recorte) y `:303-306`
  (`relevamiento_id__in=ids` en cada consulta del tablero).
- **Escenario:** programa con muchos relevamientos territoriales (el banco tiene 2.005; crecen con territoriales ×
  convocatorias). MariaDB 10.3+ reescribe un IN de `in_predicate_conversion_threshold` (1.000) literales o más como
  `IN (SELECT … FROM (VALUES …))`: el IN plano que el Cambio 64 eligió para evitar subconsultas vuelve a serlo, solo en
  ECOM. MySQL 8 no hace esa conversión, y en el banco el ProgramaSiis sintético agrupa un solo segmento, así que la lista
  nunca pasó de unas decenas.
- **Crece con:** relevamientos del alcance (SQL de ~12 KB repetido en las ~8 consultas del tablero).
- **Solución:** ninguna sin medir. Si `EXPLAIN` muestra un plan peor, filtrar por `relevamiento__convocatoria_id__in`
  (pocas convocatorias) cuando ningún filtro de relevamiento o canal lo impida.
- **Verificación:** banco MariaDB con 1.500 relevamientos en el programa del dashboard: `EXPLAIN` del agrupado
  (relevamiento_id, estado) de `metricas` con y sin `SET in_predicate_conversion_threshold=0`, y
  `bench_mysql.py --solo dashboard_becas_datos`.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` §Consultas · «MariaDB convierte un IN de
  1.000 literales o más en una tabla derivada: medirlo en MariaDB, no en MySQL 8».

## 6. Línea de base

Medido sobre el SHA auditado (solo lectura):

| Archivo | Líneas | Nota |
|---|---|---|
| `programas/forms.py` | 2.525 | mezcla Becas, SIIS y Dispositivos |
| `programas/services/dashboard_becas.py` | 1.780 | cinco servicios |
| `programas/services/siis_envio.py` | 1.518 | seis responsabilidades |
| `programas/views/revision.py` | 1.385 | crece desde octubre (1.331) |
| `programas/views/configuracion.py` | 1.351 | cinco ABMs |
| `programas/views/relevamientos.py` | 1.213 |  |
| `programas/services/proceso_masivo.py` | 1.191 | cuatro responsabilidades |
| `programas/services/siis.py` | 986 | al borde de las 1.000 |
| `programas/api/views.py` | 923 |  |

Siete archivos del alcance pasan las 1.000 líneas.

### Banco MariaDB 10.11 (`bench_mysql.py`, 20.000 casos, `read_timeout` 10 s)

Rutas de Becas por encima de 500 ms en caliente o de 1 s en frío (el resto queda debajo):

| Ruta | Frío | Caliente | SQL | Ficha |
|---|---|---|---|---|
| `dashboard_respuestas_xlsx` | 27.796 ms | **18.695 ms** | 2.310 ms | B-PERF-25 |
| `reporte_beneficiarios_xlsx` | 4.986 ms | **8.000 ms** | 1.985 ms | B-PERF-26 |
| `dashboard_becas_export_xlsx` | 4.075 ms | 197 ms | 3.297 ms | B-PERF-05 |
| `dashboard_becas_datos` | 1.718 ms | 78 ms | 1.140 ms | — |
| `dashboard_becas_export_csv_bloque` | 1.527 ms | 94 ms | 827 ms | B-PERF-05 |
| `reporte_embudo` | 709 ms | **636 ms** | 439 ms | B-PERF-03, B-PERF-10 |
| `dashboard_respuestas_csv` | error del banco | — | — | (≈3.030 ms en el log del server) |

- Ninguna ruta pasa los 10 s de `read_timeout` en SQL; las dos lentas cortan por CPU de escritura, no por base. Nginx (60 s) y gunicorn (120 s) no cortan hoy; el acantilado del XLSX de respuestas está en ~41.000 casos.
- **Nota de herramienta:** `bench_mysql.py` lee `.content` de un `StreamingHttpResponse` y falla con `AttributeError` en `dashboard_respuestas_csv`. Arreglo en el PR de sembrado: consumir `streaming_content`.
- `reporte_embudo` en caliente (636 ms) pasa el umbral de 500 ms, aunque el addendum resumía «todo < 1 s».
- El objetivo `revision_bandeja_estado_raro` responde 404 en el banco: la ruta del manifiesto está rota y no midió nada; corregirla en el mismo PR de sembrado.

## 7. Decisiones del cliente

Una línea por decisión: ficha · pregunta · propuesta por defecto (se aplica si el cliente no contesta).

- **B-SEG-02** · ¿Se bloquea cambiar el sexo si otro caso de la persona ya tiene identidad validada? · Sí: solo lectura.
- **B-SEG-03** · ¿Los casos rechazados dejan de ocupar cupo del link público? · Sí: excluir RECHAZADO del conteo, como los duplicados de SIIS-13.
- **B-SEG-04** · ¿Una inscripción anónima sin identidad validada puede crear legajos y escribir contacto antes de aprobarse? · No: legajo del apoderado y contacto recién al aprobar.
- **B-ERR-01** · ¿La lista «no enviar a SIIS» vale en toda vía (masivo, procesar, enviar, reenviar, vaciado y botón)? · Sí, en todas.
- **B-ERR-05** · ¿La distribución de una pregunta deja de contar respuestas que una condición ocultó? · Sí (lo prometió G2-01).
- **B-ERR-19** · ¿«Fecha de aprobación» en la planilla de beneficiarios es el día real de la aprobación? · Sí: día de la transición a APROBADO, hora local.
- **B-ERR-20** · ¿«Avance de convocatorias» cuenta con las mismas reglas que embudo y tablero? · Sí: alinear.
- **B-LIM-02** · ¿Se unifican las reglas de estado del relevamiento entre backoffice y app (finalizar desde `FINALIZANDO` en todos los canales; reabrir limpia siempre `cerrado_automaticamente_en`; reabrir exige el período actual)? · Sí, en un PR coordinado con Chaco-mobile y con los tests de contrato RED-11/RED-03 en el mismo diff.
- **B-LIM-04** · ¿Un segmento sin programa informa a SIIS al aprobar? · No informa (conducta actual).
- **B-LIM-14** · ¿El reporte de embudo cuenta las etapas igual que el tablero? · Sí: alinear (#366).
- **B-LIM-15** · ¿El «cupo ocupado» del tablero y del reporte es el del segmento entero, como en Cupo? · Sí: una sola función.
- **B-LIM-26** · ¿La corrida masiva de pantalla vacía también la tabla intermedia hacia SIIS? · No: se corrige el texto.
- **B-LIM-41** · ¿El antirreenvío del link público pasa a ser global, como en la app? · Sí (sin efecto práctico hoy).
- **B-LIM-45** · Con dos alcances (Referente y otro), ¿cuál manda? · Referente.
- **B-LIM-67** · ¿Subsegmentos y requisitos pasan a baja lógica? · No: borrado físico.
- **B-FE-05** · ¿El export del tablero usa las etiquetas de pantalla? · Sí.
- **B-FE-08** · ¿Al crear un segmento se muestra el destino SIIS, como al editarlo? · Sí, con `valida_siis`.
- **B-PERF-01** · Si al cargar un padrón falla el cruce, ¿el padrón queda cargado y el cruce se reintenta? · Sí: dos transacciones.
- **B-PERF-08** · Con el link saturado, ¿qué texto ve la persona? · El error genérico del paso 2.

Decisiones que tomó el juez (no van al cliente), 19-nov: B-LIM-58 queda BAJA y no es de seguridad; en B-LIM-29 el orden «alta y después aviso» figura como «DECISIÓN JUEZ»; **B-PERF-25 reabre A4-03 de octubre** (medido 12,2 → 2,9 s con el prototipo); **B-PERF-16 se descarta** (PERF-13 de octubre midió el mismo mecanismo); B-PERF-02, B-PERF-03, B-PERF-18 y B-PERF-26 se quedan en sus olas y citan PERF-11 de octubre (si PERF-11 se retoma, las absorbe). B-LIM-02 (unificar estados) y B-LIM-15 (cupo ocupado del dashboard) **son decisión del cliente** (§7).

## 8. Pasada 2 · qué medir y qué reproducir

### 8.a Fichas PERF/DAT a medir en el banco

MariaDB 10.11, `read_timeout` 10 s, banco de 20.000 casos (`scripts/perf_mysql/README.md`). Sin número, una PERF ALTA baja a INFO. Las MEDIA o mayores quedan PLAUSIBLE hasta tener el número.

| Ficha | Sev. | Qué se mide (medición propuesta por el auditor) |
|---|---|---|
| B-PERF-01 · La carga del padrón deja tomada la convocatoria (o el relevamiento) 1… | ALTA | base del banco con `escalar_bench.py --casos 20000` y el padrón de 50.000 filas del harness de PERF-04 (`test_a404_perfil`). Sesión 1: `cargar_padron(convocatoria_publica, …)` desde `manage.py shell`, cronometrado. Sesión 2 (cliente `mariadb`), en paralelo: `SET innodb_lock_wait_timeout=60; START TRANSACTION; SELECT id FROM programas_convocatoria WHERE id=<pk> FOR UPDATE;` y anotar cuánto espera; durante la espera,… |
| B-PERF-02 · El CSV de lista de espera carga y decodifica los JSON pesados de cada… | MEDIA | banco `scripts/perf_mysql/`: el seed no crea `ListaEspera`; sembrar 5.000 entradas activas sobre la convocatoria del relevamiento público (como `escenarios_borde.py` hace con los 400 `BAJA`) y sumar a `_extra_targets()` de `bench_mysql.py` la ruta `/becas/convocatorias/<conv>/export/lista-espera/`; medir frío/caliente antes y después y el pico de memoria con `tracemalloc`. Si con 5.000 entradas pasa de ~2 s o de ~20… |
| B-PERF-03 · El embudo cuenta la lista de espera con un DISTINCT sobre las 37 colu… | MEDIA | banco MariaDB: sembrar 5.000 `ListaEspera(promovido=False)` sobre casos del relevamiento público y correr `bench_mysql.py --solo reporte_embudo,reporte_embudo_xlsx` antes y después; `EXPLAIN ANALYZE` de la consulta (antes: `Using temporary` con la fila ancha). |
| B-PERF-04 · Distribución de un campo propio condicionado: una fila y una corrida… | MEDIA | banco MariaDB: diseño en la convocatoria del relevamiento público con un selector `cp-` condicionado a `edad_menor` sobre la fecha de nacimiento; `perfil_ruta.py "/becas/config/programas/<p>/dashboard/datos/?periodo=todo&pregunta=cp-…" 1` (filas que devuelve la consulta agrupada y segundos de Python en `condiciones.aplicar`), antes y después. |
| B-PERF-05 · Export del dashboard: una pasada sobre todo el recorte por cada campo… | MEDIA | banco: K convocatorias del mismo ProgramaSiis con diseño de 5 selectores `cp-` (sin casos) y `bench_mysql.py --solo dashboard_becas_export_xlsx` en frío: hoy consultas ≈ base + 12 + 5K y SQL ≈ K × 1 s; después, base + 12. |
| B-PERF-06 · La corrida de `procesar_casos_siis` y el masivo de la pantalla retien… | MEDIA | banco de 20.000 casos (`scripts/perf_mysql/README.md`, pasos 1-4). Correr el ensayo `manage.py procesar_casos_siis --total N --sin-filtro-materias` con N = 500, 2000 y 5000 y tomar el pico de memoria del proceso (PowerShell: `PeakWorkingSet64` de `Get-Process`, o `tracemalloc.get_traced_memory()` al final de `handle` en una copia local). Hoy crece lineal con N; después tiene que quedar plano en el tamaño de un lote. |
| B-PERF-07 · `enviar_casos_siis` y `reenviar_siis_pendientes` eligen candidatos en… | MEDIA | banco MariaDB 10.11 de 20.000 casos (README pasos 1-4), 9.000 marcados APROBADO sin envíos, contenedor reiniciado (buffer pool frío) y sin `DB_READ_TIMEOUT`. Cronometrar el ensayo de `reenviar_siis_pendientes` y de `enviar_casos_siis --sin-filtro-materias`. Además, imprimir el SQL de `_casos` y correr `ANALYZE FORMAT=JSON <sql>` con `docker exec chaco-mariadb-bench mariadb ... chaco_perf_ci`: mirar `r_rows` de `prog… |
| B-PERF-08 · Techo de rendimiento de la cola única del link público, nunca medido | MEDIA | script nuevo en `scripts/perf_mysql/` que lanza N hilos (N = 50, 200, 1000) con `crear_formulario_publico` sobre el mismo relevamiento con cupo libre; medir retención por envío (FOR UPDATE concedido → commit), p50/p99 de espera y cantidad de 2013 con read_timeout=10. Complementar con `performance_schema.events_transactions_history`. |
| B-PERF-09 · El detalle de convocatoria lista todos sus relevamientos sin paginar | BAJA | banco: `bench_mysql.py` con un target de `becas:convocatoria_detalle` sobre una convocatoria con 2.000 relevamientos territoriales (el actual, `convocatoria_publica_detalle`, mide la del público, que tiene uno) y `perfil_ruta.py /becas/convocatorias/<pk>/` para el tiempo de plantilla; entrada en `scripts/perf_budgets.json` para `becas:convocatoria_detalle`. |
| B-PERF-10 · El embudo agrupa los motivos en Python trayendo cada rechazo, y cada… | BAJA | banco: marcar 5.000 validaciones como RECHAZADO y `perfil_ruta.py /becas/reportes/embudo/ 1` (tiempo en `JSONField.from_db_value`), antes y después. |
| B-PERF-11 · El catálogo de preguntas del dashboard se recalcula en cada request,… | BAJA | `bench_mysql.py --solo dashboard_becas_datos` (ms en caliente y consultas) con 50 convocatorias con diseño de 60 ítems en el programa; entrada en `perf_budgets.json` de la ruta. |
| B-PERF-12 · `correr_alta_siis` vuelve a hidratar y armar el payload de todos los… | BAJA | banco de 20.000 casos, con un 35 % sin localidad que cruce (borrar sus LocalidadSiis y alias). Correr `correr_alta_siis --sin-insumos --destino tabla --aplicar --continuar --usuario bench` con el SIIS mockeado (parchear `validar_compatibilidad` en un settings de banco). Sumar por tanda «Candidatos pendientes» y «Descartados por datos incompletos» y el tiempo por tanda: hoy la suma de descartados es mucho mayor que l… |
| B-PERF-13 · Borrar un requisito, una pregunta general o un subsegmento con docume… | BAJA | banco `scripts/perf_mysql/` con 20k casos: sembrar un `AdjuntoFormulario` por caso para una pregunta general y medir `POST becas:pregunta_eliminar` antes y después. No es ruta de `bench_mysql.py`: va con `perfil_ruta.py` sobre el POST, o con un script de una vez que corra `PreguntaGlobal.delete()` dentro de un `atomic` con rollback y mida tiempo y pico de memoria. `EXPLAIN` del `COUNT(DISTINCT formulario_id) ... WHE… |
| B-DAT-01 · `correr_alta_siis` identifica el caso de prueba por diferencia contra… | BAJA | el test anterior; en el banco, `correr_alta_siis --aplicar --usuario bench` con un segundo proceso creando envíos, y comprobar qué caso muestra. |
| B-PERF-14 · La tabla de casos del detalle de relevamiento pagina por OFFSET sobre… | INFO | medir antes de tocar: sumar a `_extra_targets()` de `scripts/perf_mysql/bench_mysql.py` la ruta `reverse("becas:relevamiento_detalle", args=[rel.pk]) + "?formularios_page=400&tab=formularios"` y correr `EXPLAIN ANALYZE` de la consulta paginada (esperado hoy: ~20.000 filas leídas en `programas_formulario` y otras tantas en `legajos_ciudadano`). Si da < 100 ms en frío, se cierra sin cambio, como PERF-13. |
| B-PERF-15 · Reportes transversales: el alcance viaja como IN anidados (2-3 nivele… | INFO | banco MariaDB con un coordinador asignado al segmento del relevamiento público: `bench_mysql.py --solo reporte_cupos,reporte_embudo,reporte_beneficiarios` con ese actor, y `EXPLAIN` del agregado del embudo (buscar `DEPENDENT SUBQUERY` o materializaciones repetidas). |
| B-PERF-16 (descartada, §5; medir solo para reabrir) · Dashboard: con 1.000 relevamientos o más en el alcance, MariaDB vuelv… | INFO | banco MariaDB con 1.500 relevamientos en el programa del dashboard: `EXPLAIN` del agrupado (relevamiento_id, estado) de `metricas` con y sin `SET in_predicate_conversion_threshold=0`, y `bench_mysql.py --solo dashboard_becas_datos`. |
| B-PERF-17 · Beneficiarios: la fecha de aprobación sale de una subconsulta sobre T… | INFO | banco: sembrar 5-10 trazas por caso aprobado y `bench_mysql.py --solo reporte_beneficiarios,reporte_beneficiarios_xlsx` + `EXPLAIN ANALYZE` de la consulta angosta. |
| B-PERF-18 · El drenaje de la tabla intermedia y el listado de inciertos traen los… | INFO | con 5.000 filas en AltaIntermediaSIIS (`procesar_casos_siis --destino tabla --aplicar --total 5000`, en tandas), `ANALYZE FORMAT=JSON` de la consulta de una página y `SHOW SESSION STATUS LIKE 'Bytes_received'` antes y después de leer una página desde el shell. Reportar como MEDIA solo si una página pasa de unos 200 ms en frío. |
| B-PERF-19 · La corrida masiva lee los ids de **todos** los candidatos aunque pida… | INFO | banco (`chaco_perf_ci`, 20.000 casos, 22.000 DNI habilitados), desde `manage.py shell`: cronometrar `ids_de(candidatos(programa=p))` y `EXPLAIN ANALYZE` del primer y del último tramo (`str(candidatos(programa=p).filter(pk__gt=N).order_by("pk").values_list("pk", flat=True)[:2000].query)`). Si algún tramo pasa 2 s o el total pasa 10 s, sube a MEDIA. |
| B-PERF-20 · `get_cupo_stats` cuenta los aprobados del segmento con el `Segmento`… | INFO | banco, `EXPLAIN ANALYZE` del SQL de `get_cupo_stats(segmento_del_bench)` capturado con `scripts/perf_mysql/medir_consultas_borde.py` (agregar el escenario junto al de PERF-12); para el bloqueo, dos sesiones: una corre `aprobar_o_poner_en_espera` en bucle sobre 200 casos del segmento y la otra mide la espera de `SELECT id FROM programas_segmento WHERE id = X FOR UPDATE`. |
| B-PERF-21 · `inscribir_de_oficio` resuelve el legajo y aprueba con el relevamient… | INFO | banco, `inscribir_de_oficio --aplicar` con un CSV de 1.000 DNI del bench contra el relevamiento público, con `CaptureQueriesContext` + tiempo de la transacción por fila, y en paralelo `SELECT id FROM programas_relevamiento WHERE id = X FOR UPDATE` en bucle para registrar la espera máxima. Si pasa 500 ms, sube a BAJA. |
| B-PERF-22 · `completar_casos_renaper` arma un `IN` con todos los ids de casos par… | INFO | banco, `EXPLAIN ANALYZE` de las dos formas sobre 20.000 casos y tiempo de cada una. |
| B-PERF-23 · Borrar una pregunta general bloquea y reescribe el diseño de cada con… | INFO | banco `scripts/perf_mysql/`: tiempo de `PreguntaGlobal.delete()` en un `atomic` con rollback, con las convocatorias sembradas. Si queda por debajo de 1 s con el volumen real, se cierra sin cambio. |
| B-PERF-24 · Catálogo geográfico: estampida al vencer el caché y ~150 KB embebidos… | INFO | `medir_consultas_borde.py` sobre el GET del paso 2 con caché vacío vs. lleno; tamaño de respuesta con curl (size_download). |
| B-DAT-02 · La baja lógica en cascada cuenta los casos con COUNT(*) mientras tien… | INFO | banco `scripts/perf_mysql/`: `EXPLAIN ANALYZE SELECT COUNT(*) FROM programas_formulario WHERE relevamiento_id IN (<ids de la cascada>)`; se espera `Using index` y menos de 100 ms con 20k casos por relevamiento. |

### 8.b Fichas ERR/SEG que necesitan PoC

Obligatorias (ALTA o CRÍTICA de corrección o seguridad):

- **B-SEG-01** [ALTA] El 400 del export del dashboard refleja el parámetro como HTML (XSS reflejado)
- **B-ERR-01** [ALTA] Tres vías de alta a SIIS se saltean reglas que solo aplica el masivo (lista «no enviar», materias, pausa vigente)

Recomendadas (MEDIA con estado PLAUSIBLE, o con daño de datos si se confirma):

- **B-SEG-03** [MEDIA · PLAUSIBLE] El cupo del link público se agota con inscripciones basura y rechazar no lo libera
- **B-SEG-04** [MEDIA · PLAUSIBLE] El link anónimo crea legajos con identidad no verificada y escribe contacto en legajos reales
- **B-ERR-03** [MEDIA · PLAUSIBLE] Editar el contacto del caso reescribe la fila entera y puede revertir una aprobación, un rechazo o una validación concu…
- **B-ERR-05** [MEDIA · PLAUSIBLE] La distribución de una pregunta del catálogo cuenta respuestas que una condición ocultó
- **B-ERR-09** [MEDIA · CONFIRMADO] `conciliar_envios_siis` acepta el mismo envío dos veces con decisiones opuestas y actualiza sin mirar el estado
- **B-ERR-10** [MEDIA · CONFIRMADO] `_sentencias` parte mal un literal que termina en barra invertida escapada
- **B-ERR-12** [MEDIA · PLAUSIBLE] Una caída de la conexión a la base deja la corrida masiva «en curso» sin motivo y el hilo muere con la excepción
- **B-ERR-15** [MEDIA · PLAUSIBLE] Los adjuntos que sincronizan después del cierre se rechazan si el caso no trae `capturado_en`

Las ERR/SEG MEDIA ya CONFIRMADAS por lectura llevan su test de regresión en la propia ficha («Tests a agregar», con mutación).

### 8.c Qué le falta sembrar al banco (`scripts/perf_mysql/`)

Hoy el seed no crea ni mide lo siguiente; sin esto las fichas de 8.a no se pueden medir. **No** tocar `seed_perf` (lo usa el CI de performance): va en `escalar_bench.py`/`escenarios_borde.py`.

| Siembra | Qué crear | Fichas |
|---|---|---|
| `ListaEspera` | 5.000 entradas `promovido=False` sobre casos del relevamiento público; ruta nueva `/becas/convocatorias/<conv>/export/lista-espera/` en `_extra_targets()` | B-PERF-02, B-PERF-03 |
| Convocatoria con muchos relevamientos | 2.000 relevamientos territoriales en una convocatoria; target `becas:convocatoria_detalle` (hoy solo se mide la del público, con uno) y entrada en `perf_budgets.json` | B-PERF-09 |
| Detalle de relevamiento paginado hondo | ruta `becas:relevamiento_detalle` con `?formularios_page=400&tab=formularios` y `EXPLAIN ANALYZE` de la página | B-PERF-14 |
| Diseños con campos propios `cp-` | selector `cp-` condicionado a `edad_menor` (fecha de nacimiento) en la convocatoria pública; K convocatorias del mismo `ProgramaSiis` con 5 selectores `cp-`; 50 convocatorias con diseño de 60 ítems | B-PERF-04, B-PERF-05, B-PERF-11 |
| Validaciones SIIS RECHAZADO con JSON | 5.000 validaciones RECHAZADO con `respuesta` real | B-PERF-10 |
| Actor no admin | un coordinador asignado al segmento del relevamiento público (el banco mide solo como admin) y uno regional; reportes transversales con ese actor | B-PERF-15 |
| Muchos relevamientos en el programa | 1.500 relevamientos en el programa del dashboard (supera `in_predicate_conversion_threshold`) | B-PERF-16 (descartada; reabre si mide) |
| Varias trazas por caso | 5-10 `TracaFormulario` por caso aprobado | B-PERF-17 |
| Casos APROBADO sin envíos y datos SIIS | 9.000 APROBADO sin `EnvioSIIS`, contenedor con buffer pool frío y sin `DB_READ_TIMEOUT`; 35 % sin localidad que cruce (borrar `LocalidadSiis` y alias); DNI en `aprobados_materias` (22.000); SIIS mockeado (parchear `validar_compatibilidad` en el settings de banco) | B-PERF-07, B-PERF-12, B-PERF-19 |
| Tabla intermedia | 5.000 filas en `AltaIntermediaSIIS` (`procesar_casos_siis --destino tabla --aplicar --total 5000`, por tandas) | B-PERF-18 |
| Memoria de la corrida | ensayo de `procesar_casos_siis --total N` con N = 500, 2.000 y 5.000, medido con `tracemalloc` o `PeakWorkingSet64`; y una corrida masiva de 5.000 casos desde la pantalla | B-PERF-06 |
| Padrón grande y concurrencia | padrón de 50.000 filas (`escenarios_borde.py --padron 50000`) con 20.000 casos y ~6.700 pendientes de identidad; 20 POST concurrentes al paso 2 del link y sesión que pide `FOR UPDATE` de la convocatoria; lectura de `INNODB_TRX` y `INNODB_LOCK_WAITS` | B-PERF-01 |
| Cola del link público | script nuevo con N = 50, 200 y 1.000 hilos sobre `crear_formulario_publico` en un relevamiento con cupo libre (p50/p99 de espera, cantidad de 2013 con `read_timeout=10`) | B-PERF-08 |
| Catálogo geográfico | GET del paso 2 con caché vacío vs lleno; tamaño de respuesta (`size_download`); ~8.779 localidades | B-PERF-24, B-LIM-71 |
| Aprobación con cupo y alta de oficio | 200 casos del segmento aprobados en bucle con otra sesión pidiendo el `FOR UPDATE` del segmento; CSV de 1.000 DNI del banco para `inscribir_de_oficio --aplicar`; 20.000 casos para `completar_casos_renaper` | B-PERF-20, B-PERF-21, B-PERF-22 |
| Adjuntos y cascada de borrado | un `AdjuntoFormulario` por caso para una pregunta general (20.000 por relevamiento) y las convocatorias con ese diseño; `PreguntaGlobal.delete()` en un `atomic` con rollback | B-PERF-13, B-PERF-23, B-DAT-02 |

Rutas a sumar a `_extra_targets()` de `bench_mysql.py` y a `perf_budgets.json`: lista de espera (export), `becas:convocatoria_detalle` (2.000 relevamientos), `becas:relevamiento_detalle` página 400, reportes transversales como coordinador.

## 9. Fichas

Ordenadas por severidad y eje. Los IDs son los finales `B-<EJE>-NN`; el ID de la pasada 1 figura en cada ficha.

### B-SEG-01 · El 400 del export del dashboard refleja el parámetro como HTML (XSS reflejado)
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura; el mensaje se verificó con `.venv312`; el juez verificó que es el único caso del patrón en el repo) · **Eje:** SEG · **Origen:** nuevo (no está en la auditoría de octubre) · **Ola:** 0 · **Esfuerzo:** S
- **Resuelto:** PR #1202 (merge `b091e8de`, Cambio 494), 19-nov-2026, con test de mutación.
- **ID de la pasada 1:** B2-SEG-01
- **Verificación del juez:** CONFIRMADO por lectura. Es el único caso del patrón en el repo (`HttpResponseBadRequest` con el texto de error del form sin escapar). Va en la Ola 0.
- **Ubicación:** `programas/views/dashboard_becas.py:146-148` (`programa_dashboard_exportar`), con `_errores` en
  `programas/views/dashboard_becas.py:63-68`; los campos que reflejan el valor son `periodo` y `canal`, los dos
  `ChoiceField`, en `programas/forms_reportes.py:126` y `programas/forms_reportes.py:132`.
- **Escenario:** un usuario con `becas.reportes.exportar` abre un link como
  `/becas/config/programas/1/dashboard/export/csv/?periodo=<img src=x onerror=alert(document.domain)>`.
  `_programa_o_403` lo deja pasar, el form es inválido y la vista devuelve
  `HttpResponseBadRequest(" ".join(_errores(form)))`. Con `LANGUAGE_CODE = "es-ar"` el error de `ChoiceField` es
  `Escoja una opción válida. <img src=x onerror=alert(1)> no es una de las opciones disponibles.` (verificado), y
  `HttpResponseBadRequest` sale con `Content-Type: text/html; charset=utf-8` (verificado). El navegador renderiza la
  etiqueta y ejecuta el `onerror`: la CSP del sitio permite `'unsafe-inline'` en `script-src`
  (`config/middlewares/security_headers.py:38`), así que no lo frena. Es un GET de navegación de primer nivel: las
  cookies de sesión viajan aunque sean `SameSite=Lax`. El script corre en el origen del backoffice con la sesión de
  quien exporta datos personales, y puede leer cualquier pantalla o export del mismo origen y hacer POST con su token CSRF.
- **Causa raíz:** el texto de error del form, que Django arma interpolando el valor crudo recibido
  (`invalid_choice` con `%(value)s`), se devuelve sin escapar en una respuesta cuyo tipo por defecto es HTML. El endpoint
  hermano `programa_dashboard_datos` no tiene el problema porque contesta JSON (`JsonResponse`) y el JS lo pinta con
  `textContent` (`becas-dashboard.js:156-160`).
- **Solución:** que la respuesta 400 sea texto plano y no HTML. El cambio va en una sola línea y no toca la lógica ni
  el mensaje:
  `return HttpResponseBadRequest(" ".join(_errores(form)), content_type="text/plain; charset=utf-8")`.
  Por consistencia, las otras dos respuestas de error de esta vista (`:144` y `:166`, textos fijos) y el
  `HttpResponseServerError` de `:171` y `:215` pueden llevar el mismo `content_type`. Lo que ve el usuario no cambia:
  un navegador muestra ese 400 como texto plano igual.
- **Lo que NO hay que hacer:** no pasar a `escape()` solo el valor del `periodo` (mañana es otro `ChoiceField`); no
  reemplazar el mensaje por uno genérico (se pierde el detalle que hoy ayuda a diagnosticar), y no «arreglarlo»
  sacando `'unsafe-inline'` de la CSP en este PR (rompe las plantillas inline, ver el comentario de
  `security_headers.py:32`).
- **Tests a agregar:**
  `programas/tests/test_dashboard_exports.py::DashboardExportTests.test_400_con_filtro_invalido_es_texto_plano`
  (GET con `periodo=<script>x</script>` → 400, `Content-Type` empieza con `text/plain` y el cuerpo no se sirve como
  HTML). Verificarlo con mutación: sin el `content_type` el test tiene que quedar rojo.
- **Verificación:** el test de arriba, y el curl manual del escenario contra DEV: la respuesta trae
  `Content-Type: text/plain`.
- **Regla para no repetirlo:** **control mecánico** · `core/tests/` (ratchet AST junto a los de RED-79) · un test que
  recorra `programas/views/`, `legajos/views/`, `users/views/` y falle si encuentra
  `HttpResponseBadRequest(...)`/`HttpResponseServerError(...)`/`HttpResponse(...)` cuyo primer argumento no sea un
  literal de texto (`ast.Constant`) y que no declare `content_type=`. Mensaje: «Una respuesta de error que interpola
  datos (errores de form, parámetros) tiene que ir con `content_type="text/plain; charset=utf-8"` o por
  `JsonResponse`: el texto de un `ChoiceField` inválido trae el valor crudo». Además, una línea en
  `.claude/skills/seguridad-django/SKILL.md` (sección XSS): «Los errores de un form (`form.errors`) no están
  escapados: `invalid_choice` interpola el valor recibido. Nunca a una `HttpResponse*` con el tipo por defecto».

---

### B-ERR-01 · Tres vías de alta a SIIS se saltean reglas que solo aplica el masivo (lista «no enviar», materias, pausa vigente)
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** Thermos corrección · **Hallado por 2 revisores** (B3-ERR-01 + B3-LIM-02); origen de la absorbida: B3-LIM-02: extiende la lógica de SIIS-01 («séptima vía») y del Cambio 138 · **Ola:** 0 · **Esfuerzo:** M
- **ID de la pasada 1:** B3-ERR-01 + B3-LIM-02 (**hallado por 2 revisores**)
- **Nota de consolidación:** las dos soluciones difieren y hay que elegir. La de B3-ERR-01 filtra en los selectores con las funciones del masivo y descarta tocar `_reservar` (para no romper la vía manual, donde el operador decide caso por caso). La de B3-LIM-02 pone la invariante en `_reservar` y un selector base `casos_informables`. Lo decide la pregunta al cliente (sección 7): si el botón «Enviar a SIIS» de la pantalla también debe respetar la lista, va en `_reservar`; si no, selectores comunes + chequeo de `valida_siis` en el vaciado. En ambos casos la regla vale para reenviar, enviar y el vaciado, y el test de trinquete cubre todas las vías.
- **Ubicación:**
  - `programas/management/commands/reenviar_siis_pendientes.py:42-63`, en `_casos`. Filtra por último envío ERROR, envío vigente, oficio, `Q_PROGRAMA_VALIDA_SIIS` y agotados. No filtra por `excluidos`, por `habilitados` (materias) ni por `_sin_pausa_vigente`.
  - `programas/management/commands/enviar_casos_siis.py:135-179`, en `_casos`. Filtra materias, pero no `excluidos`, no pausa/bloqueo SIIS y no agotados.
  - `programas/services/siis_envio.py:1395-1472`, en `sincronizar_tabla_intermedia` (el «vaciado» de la tabla intermedia). Aplica `dnis_a_no_enviar` (1438-1443). No vuelve a mirar `valida_siis`, pausa, programa bloqueado ni materias del momento del envío.
  - La referencia correcta es `programas/services/proceso_masivo.py:687-697` en `candidatos()`: `_sin_pausa_vigente`, `insumos.habilitados` e `insumos.excluidos`.
- **Escenario:** el PM carga en `siis_enviar` a las personas que ya figuran en SIIS (p. ej. las ~3.729 del 23/09). El Cambio 138 dice que «el punto de la lista es que esa persona no llegue a SIIS» y el Cambio 90 que «cualquier camino que llegue a SIIS respeta la misma regla»; hoy solo la respeta el masivo (`proceso_masivo.candidatos`, `:687-697`). Un operador corre `reenviar_siis_pendientes --aplicar` tras una caída del legacy (el uso para el que se pensó), o `enviar_casos_siis --aplicar`, o un `procesar_casos_siis` que vacía la tabla intermedia, y un caso de esa lista sale igual (en reenviar, un ERROR técnico previo al Cambio 127; en enviar, un caso APROBADO). La API de SIIS no deduplica y el alta no tiene baja: queda un alta doble irreversible.
  **Matriz verificada por el juez en el SHA auditado** (lectura de `reenviar_siis_pendientes._casos`, `enviar_casos_siis._casos` y `siis_envio.sincronizar_tabla_intermedia`):

  | Vía | Lista «no enviar» | Filtro de materias | Pausa vigente | Otras reglas que no aplica |
  |---|---|---|---|---|
  | `reenviar_siis_pendientes` | no | no | no | solo filtra último envío ERROR, vigente, oficio, programa que valida y agotados |
  | `enviar_casos_siis` | no | sí (salvo `--sin-filtro-materias`) | no | tampoco agotados |
  | vaciado de la tabla intermedia (`sincronizar_tabla_intermedia`, `siis_envio.py:1395-1472`) | sí (`dnis_a_no_enviar`, `:1438`) | no | no | tampoco `valida_siis`, programa bloqueado ni el estado del momento del envío |
  | masivo (`proceso_masivo.candidatos`, referencia) | sí | sí | sí | — |

  Mitigante: son comandos que corre un operador, con ensayo por defecto y `--aplicar` explícito; el riesgo es de operación y no de un usuario final. Por eso no es CRÍTICA, pero el daño no tiene vuelta atrás.
- **Causa raíz:** cada comando arma su propio queryset de candidatos en lugar de reusar los filtros de `proceso_masivo.candidatos()`. Las reglas que se agregaron después (lista de exclusión, materias, pausa) se sumaron solo al masivo.
- **Solución (sin cambiar lógica ni estética):**
  1. En `reenviar_siis_pendientes._casos` y en `enviar_casos_siis._casos`, aplicar los mismos tres filtros que `candidatos()`: `exclude(ciudadano__dni__in=insumos.excluidos)`, `filter(ciudadano__dni__in=insumos.habilitados)` y `_sin_pausa_vigente(casos)`. `insumos` sale de la misma función que usa el masivo.
  2. En `sincronizar_tabla_intermedia`, antes de `_mandar_a_siis` (1452), repetir el chequeo de `programa.valida_siis` que ya hace `enviar_beneficiario_a_siis` en 1228.
  3. Mostrar en el ensayo cuántos casos quedaron afuera por cada regla, como ya hace el comando con los agotados.
- **Lo que NO hay que hacer:**
  - No meter el filtro en `_reservar`. Rompería la vía manual desde revisión y cupo, donde el operador decide caso por caso.
  - No copiar las listas a mano en cada comando. Hay que llamar a las mismas funciones del masivo.
- **Tests a agregar:**
  - Un caso APROBADO con último envío ERROR y DNI en `siis_enviar`: `reenviar_siis_pendientes --aplicar` no llama a `cargar_beneficiario` (mock).
  - Lo mismo con `enviar_casos_siis` y con un DNI sin materias aprobadas.
  - Una fila de tabla intermedia de un programa con `valida_siis=False`: el vaciado no la manda.
- **Verificación:** mutación. Sacar el `exclude` de `excluidos` en un comando tiene que poner rojo su test.
- **Regla para no repetirlo:** toda vía que termine en `cargar_beneficiario` toma sus candidatos de `proceso_masivo` (o de un helper común). Sumar un test de trinquete que recorra las vías de envío y verifique que cada una excluye un DNI de `siis_enviar`.

#### Aporte del segundo revisor (B3-LIM-02: «A quién se le puede dar el alta» está escrito en tres selectores y dos ya divergen: la lista de exclusión no frena a `enviar_casos_siis` ni a `reenviar_siis_pendientes`)
_Pasada 1: severidad ALTA · estado CONFIRMADO (lectura) · esfuerzo S-M._

- **Ubicación:** `programas/services/proceso_masivo.py:582-712` (`candidatos`), `programas/management/commands/enviar_casos_siis.py:135-179` (`_casos`), `programas/management/commands/reenviar_siis_pendientes.py:42-63` (`_casos`).
- **Escenario:** el PM carga un DNI en `siis_enviar` («a esta persona no la mandes», Cambio 138: «el punto de la lista es que esa persona no llegue a SIIS», `siis_envio.py:1405-1407`). Si alguien corre `enviar_casos_siis --aplicar` o `reenviar_siis_pendientes --aplicar`, ese caso sale igual: ninguno de los dos `_casos` llama a `dnis_a_no_enviar()`, y la puerta común (`_reservar`) tampoco la mira. Lo mismo pasa con otras reglas que solo tiene `candidatos`. `enviar_casos_siis` no excluye los casos con errores agotados (A2-15), los que tienen conflicto de carga sin resolver, los pausados (BEC-21) ni los ENVIADO en lista de espera. `reenviar` no aplica `aprobados_materias` (Cambio 90), y su docstring dice que «cualquier camino que llegue a SIIS respeta la misma regla» (`enviar_casos_siis.py:172-173`). El alta en SIIS no tiene baja.
- **Causa raíz:** las invariantes que tienen que valer para **cualquier** alta (envío vigente, alta de oficio, programa que valida, lista de exclusión) están copiadas en cada selector y no viven en la única puerta por la que pasan todas las vías. Cada regla nueva se agregó donde se necesitaba en ese momento: el Cambio 138 enumeró «los tres caminos» y dejó afuera estos dos.
- **Solución:** la jugada de judo es mover las invariantes a la puerta y sacarlas de los selectores:
  1. `siis_envio._reservar` (bajo el lock que ya toma): si `normalizar_dni(base["documento"])` está en `dnis_a_no_enviar()` (o en un `excluidos` que se le pasa ya leído, como hace `Insumos`), devuelve un `EnvioSIIS` cerrado `RECHAZADO` con `codigo_error="EXCLUIDO_POR_LISTA"` y sin `vigente`, el mismo patrón que `_cerrado_por_alta_de_oficio`. `sincronizar_tabla_intermedia` mantiene su conteo de `excluidas` sin tocar la fila.
  2. Un selector base `proceso_masivo.casos_informables(*, estados, insumos)` con lo común (`~Exists(vigente)`, `~alta_de_oficio_marcada()`, `Q_PROGRAMA_VALIDA_SIIS`, materias opcional, exclusión, agotados), sobre el que `candidatos` agrega sus reglas de aprobación y los dos comandos agregan su filtro de «último envío».
  `DECISIÓN CLIENTE: por defecto la lista de exclusión vale en toda vía masiva o automática (masivo, procesar, enviar, reenviar, drenaje); el botón «Enviar a SIIS» de la pantalla también la respeta y muestra el motivo en el toast.`
- **Lo que NO hay que hacer:** copiar el `exclude(ciudadano__dni__in=no_enviar)` a los dos `_casos`. Es el mismo error que causó esta ficha, y la sexta vía que aparezca lo vuelve a olvidar.
- **Tests a agregar:** `programas/tests/test_siis_enviar_exclusion.py::TodasLasViasTests.test_enviar_casos_siis_no_manda_un_excluido`, `…test_reenviar_siis_pendientes_no_manda_un_excluido`, `…test_reservar_cierra_un_excluido_sin_llamar_a_siis`. Verificar por mutación: si se borra el chequeo de `_reservar`, los tres quedan en rojo.
- **Verificación:** `cargar_beneficiario` sustituido con un mock que cuenta llamadas: 0 llamadas para un DNI excluido en las cinco vías.
- **Regla para no repetirlo:** **control mecánico** · `programas/tests/test_siis_vias.py` · test parametrizado sobre las vías de alta registradas en una tupla `VIAS_DE_ALTA`; un comando que importa `enviar_beneficiario_a_siis` y no está en la tupla hace fallar el test («vía de alta nueva sin la batería de invariantes»).

---

### B-PERF-01 · La carga del padrón deja tomada la convocatoria (o el relevamiento) 15-22 s y el link público espera más de 10 s
**Severidad:** ALTA · **Estado:** PLAUSIBLE (mecanismo verificado por lectura; sin medir: la pasada 2 lo mide en el banco) · **Eje:** PERF · **Origen:** nuevo. Es la combinación de BEC-15 (#621, 07-oct: `select_for_update` del dueño) con la duración que midió la resolución de PERF-04 (#632). No es A4-04 (§8.2): aquello hablaba de leer las filas del padrón, que con READ COMMITTED no bloquea; esto es la **fila de la convocatoria o del relevamiento**, que el link público pide con `FOR UPDATE`. · **Hallado por 2 revisores** (B4-PERF-01 + B6-PERF-01); origen de la absorbida: B6-PERF-01: mismo mecanismo que **B-PERF-01** (fusionar: B4 lo ve desde la carga, B6 desde los consumidores). Relacionado con BEC-15 (Cambio 172), PERF-04 (opción M) y A4-04. **No** es lo refutado en README §8.2 (A4-04, «poco probable con READ COMMITTED»): aquel análisis es sobre 917e583, anterior a BEC-15, y hablaba de lecturas planas del paso 1; acá son lecturas FOR UPDATE, que el nivel de aislamiento no relaja. · **Ola:** 1 · **Esfuerzo:** M
- **ID de la pasada 1:** B4-PERF-01 + B6-PERF-01 (**hallado por 2 revisores**)
- **Ubicación:** `programas/services/padron.py:400-472` (`cargar_padron`, `@transaction.atomic`): candado del dueño en
  `:421`, `bulk_create` del padrón en `:458`, `duenio.save(padron_archivo)` en `:465` y el cruce
  `validar_casos_pendientes` en `:471`, todo en la misma transacción. `quitar_padron_propio` `:475-501` (mismo patrón,
  más corto). Del otro lado: `programas/services/inscripcion_publica.py:114` (`Relevamiento … select_for_update`) y
  `:159` (`Convocatoria … select_for_update`) en el paso 2 del link; `programas/api/views.py:748` (alta de la app de
  campo, `Relevamiento … select_for_update`).
- **Escenario:** convocatoria del link público con 20.000 casos y 6.667 pendientes de identidad; un coordinador sube un
  padrón de 50.000 filas (`convocatoria_padron`, `programas/views/relevamientos.py:1110`) con el link abierto.
  `cargar_padron` toma `FOR UPDATE` sobre la convocatoria y lo sostiene hasta el commit: la resolución de PERF-04 midió
  esa transacción en **21,84 s** (legajos vacíos) y **14,96 s** (legajos cargados) en el banco MariaDB 10.11. Cada
  inscripción que llega en esa ventana toma el candado del relevamiento (`:114`), se queda esperando el de la
  convocatoria (`:159`) y a los 10 s la conexión muere por `read_timeout`: 500 en el paso 2. Mientras espera tiene
  tomado el relevamiento, así que las siguientes ya se encolan en `:114` (la cola del Cambio 91). Con padrón **propio**
  del relevamiento público (`relevamiento_padron`) el candado es directamente el del relevamiento; con padrón propio de
  un relevamiento territorial, el que espera es el alta de la app de campo (`api/views.py:748`), que reintenta por ser
  5xx. Efecto secundario: el cruce hace `bulk_update` de `legajos_ciudadano` cada 2.000 casos (`padron.py:640-645`) y
  esas filas quedan tomadas hasta el commit; un `ciudadano.save()` del revisor sobre uno de esos pendientes (validar
  identidad en la bandeja) espera lo mismo.
- **Causa raíz:** el reemplazo del padrón (lo que BEC-15 necesita serializar) y el cruce de casos (lo que crece con los
  casos) comparten una transacción. Sacar solo el `select_for_update` no alcanza: el `bulk_create` de
  `PadronHabilitado` (`:458`) chequea la FK hacia la convocatoria/relevamiento, InnoDB toma un **bloqueo compartido**
  sobre esa fila padre hasta el commit, y el `duenio.save` de `:465` la toma exclusiva. Cualquier `FOR UPDATE` del link
  sobre esa fila espera la transacción entera.
- **Solución:** dos transacciones, como ya dejó escrito PERF-04 en su «Opcional (M)»:
  1. `cargar_padron`: transacción corta con el candado del dueño (BEC-15 intacto) que solo hace `DELETE` + `bulk_create`
     + `padron_archivo` + `on_commit` del Excel viejo.
  2. Después del commit, `validar_casos_pendientes(objetivo, usuario)` en una transacción **por lote** de `LOTE_CASOS`
     (1.000): cada lote relee sus pendientes con
     `Formulario.objects.select_for_update().filter(pk__in=lote, validado_renaper=False, identidad_forzada=False).order_by("pk")`
     y escribe trazas, ciudadanos y formularios de ese lote. Toma filas de casos pendientes, que el link no toca, y dos
     cruces simultáneos no validan dos veces el mismo caso (el segundo relee `validado_renaper=True`). El
     `ResumenPadron` suma lo validado por lote: el mensaje al operador es el mismo.
  Lo único que cambia es el desenlace ante una falla a mitad del cruce: el padrón queda cargado y el cruce queda parcial
  y re-ejecutable (filtra `validado_renaper=False`), en vez de deshacerse todo. Si el PM quiere conservar la atomicidad
  total: `DECISIÓN CLIENTE: partir en dos transacciones (default)`; la alternativa es no cargar padrones con el link
  abierto, que es una regla operativa y no técnica.
- **Lo que NO hay que hacer:** sacar el `select_for_update` del dueño (vuelve BEC-15: padrón con filas de dos cargas);
  reemplazarlo por `GET_LOCK` sin partir la transacción (el bloqueo compartido de la FK del `bulk_create` sigue
  sosteniendo la fila hasta el commit); tocar el `read_timeout` (contrato con ECOM).
- **Tests a agregar:** `programas/tests/test_candados_concurrencia.py::PadronVsLinkPublicoTests.test_el_cruce_no_retiene_la_convocatoria`
  (`MotorRealMixin` + `TransactionTestCase`, como `CarreraDeCorridaMasivaTests`): hilo A corre `cargar_padron` con
  `validar_casos_pendientes` parcheado para dormir 3 s; hilo B pide `Convocatoria.objects.select_for_update().get(pk=…)`
  y tiene que obtenerlo en menos de 1 s. `programas/tests/test_padron_performance.py::ConsultasConstantesTests` y
  `MismosCasosEnElMismoOrdenTests` siguen en verde.
- **Verificación / medición en `scripts/perf_mysql/`:** base del banco con `escalar_bench.py --casos 20000` y el padrón
  de 50.000 filas del harness de PERF-04 (`test_a404_perfil`). Sesión 1: `cargar_padron(convocatoria_publica, …)` desde
  `manage.py shell`, cronometrado. Sesión 2 (cliente `mariadb`), en paralelo:
  `SET innodb_lock_wait_timeout=60; START TRANSACTION; SELECT id FROM programas_convocatoria WHERE id=<pk> FOR UPDATE;`
  y anotar cuánto espera; durante la espera, `SELECT * FROM information_schema.INNODB_LOCK_WAITS` (MariaDB) o
  `performance_schema.data_lock_waits` (MySQL). Hoy se espera la duración entera de `cargar_padron` (15-22 s); después
  del arreglo, solo la transacción 1 (estimado 1-4 s: `DELETE` + 25 `INSERT` de 2.000 filas), a confirmar con el mismo
  procedimiento.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` §Transacciones y bloqueos · «Las filas
  de `Relevamiento` y `Convocatoria` las bloquea el link público y la app de campo en cada alta. Una transacción de
  backoffice que las toque —con `select_for_update`, con un `UPDATE` o **con un INSERT en una tabla con FK hacia
  ellas**, que en InnoDB toma un bloqueo compartido sobre la fila padre hasta el commit— no puede incluir trabajo que
  crezca con los casos: partila y hacé el resto en lotes con su propio candado.» Y en
  `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas activas: «`@transaction.atomic` que inserta en una
  tabla con FK a `Relevamiento`/`Convocatoria` y después recorre casos.»

#### Aporte del segundo revisor (B6-PERF-01: La carga de padrón retiene el lock que necesita cada envío del link y cada alta de campo: espera >10 s → 500)
_Pasada 1: severidad ALTA · estado CONFIRMADO (lectura del orden de locks) · el tiempo de retención es el ya medido en PERF-04 (21,84 s / 14,96 s); la espera del lado del link es PLAUSIBLE hasta medir con 2 sesiones · esfuerzo M._

- **Ubicación:**
  - `programas/services/padron.py:421` — `cargar_padron` (atomic, :400) toma select_for_update del dueño (convocatoria o relevamiento con padrón propio) y lo retiene durante DELETE + bulk_create + `validar_casos_pendientes` (:471).
  - `programas/services/inscripcion_publica.py:114` — cada envío del link toma FOR UPDATE del Relevamiento; `:159` toma FOR UPDATE de la Convocatoria **mientras retiene** el del Relevamiento.
  - `programas/api/views.py:748` — alta de la app de campo: FOR UPDATE del Relevamiento (choca si el padrón es propio del relevamiento).
  - `programas/services/padron.py:486` — `quitar_padron_propio`: mismo patrón sobre el Relevamiento.
- **Escenario:** link público abierto, el operador reemplaza el padrón de la convocatoria (50k filas, 20k casos, ~6.700 pendientes). Durante 15–22 s la fila Convocatoria está tomada. El primer envío del paso 2 queda en `:159` con el Relevamiento tomado; los siguientes se encolan en `:114` detrás de él. Todo envío que espera más de 10 s muere por read_timeout (OperationalError 2013) → 500 a la persona, y su hilo del servidor sigue esperando hasta innodb_lock_wait_timeout (50 s) o hasta que se libera. Con padrón propio, también las altas de campo de ese relevamiento.
- **Crece con:** tamaño del padrón × casos pendientes (duración del lock) × envíos/s durante la ventana (cantidad de 500). Con 50k/20k: toda la ventana de 15–22 s es pérdida total de envíos.
- **Causa raíz:** BEC-15 serializa carga de padrón y envíos con el mismo lock de fila (correcto para RN-P14: un envío no puede validar contra un padrón a medio reemplazar), pero el lock cubre también el cruce `validar_casos_pendientes`, que es la parte cara y no necesita excluir envíos nuevos.
- **Solución (preserva la lógica):** partir `cargar_padron` en dos transacciones: (1) reemplazo del padrón bajo el lock del dueño (DELETE + bulk_create, segundos); (2) `validar_casos_pendientes` fuera de ese lock, en lotes con commit, idempotente (filtra por estado pendiente de origen). Un envío que entra entre (1) y (2) ya valida contra el padrón nuevo, que es lo que exige RN-P14. Es la opción M de PERF-04. **DECISIÓN CLIENTE** solo para el borde: si el cruce (2) falla, el padrón queda cargado y los pendientes se cruzan en el reintento (hoy se revierte todo). Propuesta por defecto: aceptar, con reintento manual desde la pantalla de padrón.
- **Lo que NO hay que hacer:** sacar el select_for_update del envío (reabre la carrera BEC-15); subir read_timeout (acuerdo con ECOM, y solo traslada el 500); correr el cruce en el hilo web con el lock tomado.
- **Tests a agregar:** MotorRealMixin/TransactionTestCase (patrón de `test_candados_concurrencia.py`): hilo A corre `cargar_padron` con un `validar_casos_pendientes` instrumentado que duerme; hilo B corre `crear_formulario_publico`; afirmar que B termina antes de que A termine el cruce y que B validó contra el padrón nuevo. Mutación: volver a poner el cruce dentro del lock → test rojo.
- **Verificación / medición:** banco `scripts/perf_mysql/` con `escenarios_borde.py --padron 50000`; sesión 1: `cargar_padron` (reemplazo); sesiones 2..N: POST al paso 2 del link en paralelo (N=20). Durante la carga leer `information_schema.INNODB_TRX`, `sys.innodb_lock_waits` y SHOW ENGINE INNODB STATUS; contar envíos con 2013 y su espera. Esperado hoy: espera ≈ duración del cruce (>10 s). Después del arreglo: espera ≤ duración del reemplazo.
- **Regla para no repetirlo:** skill · `.claude/skills/mysql-mariadb/SKILL.md` (sección locks) · «Un select_for_update sobre una fila que también toma un endpoint público (Relevamiento, Convocatoria) no se retiene durante un recálculo masivo: el lock cubre solo la escritura que la regla necesita atómica; el cruce va después, en lotes idempotentes. Medir con 2 sesiones en el banco antes de mergear.»

---

### B-LIM-01 · Resolución del caso (aprobar, rechazar, duplicado, identidad, SIIS) escrita en vistas
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo (RED-54 separó templates y selectores, no la escritura) · **Ola:** 7 · **Esfuerzo:** L
- **ID de la pasada 1:** B1-LIM-03
- **Ubicación:** `programas/views/revision.py:937-1017` (`formulario_aprobar`), `:1088-1171` (`formulario_rechazar`: `transaction.atomic` + `select_for_update` + estado + traza + `cerrar_espera_activa` + aviso), `:1020-1085` (`formulario_resolver_duplicado`, dos ramas simétricas `conservar_previo`/`conservar_actual`), `:1174-1238` (`formulario_revalidar_renaper`: mezcla Base de Personas en `Ciudadano`, parsea fechas), `:1241-1290`, `:1293-1348`, `:896-934` (`formulario_actualizar_genero`: save + traza sin `atomic`), `:798-852` (`formulario_datos_siis`: lock + merge), `:606-646` (POST del detalle).
- **Escenario:** optimizar el camino de aprobación (cantidad de consultas bajo el lock, contra el `read_timeout` de 10 s) exige tocar vistas HTTP que no tienen tests unitarios propios; la API y el cron no pueden reusar la regla («qué pasa al rechazar») y la reimplementan. Contradice CLAUDE.md «views/ orquestación HTTP, sin lógica de dominio».
- **Causa raíz:** cada acción nació como vista y nunca se extrajo; `services/` tiene las piezas (`cerrar_espera_activa`, `enviar_aviso_resolucion`, `motivo_bloqueo_aprobacion`) pero no el caso de uso que las orquesta.
- **Solución:** `programas/services/revision_caso.py` con un caso de uso por acción (`aprobar(formulario, usuario, base_url)`, `rechazar(...)`, `resolver_duplicado(..., decision)`, `revalidar_renaper(...)`, `validar_padron(...)`, `forzar_identidad(...)`, `actualizar_genero(...)`, `guardar_datos_siis(...)`) que devuelven un resultado tipado (`ResultadoAccion(ok, mensaje, nivel)`). La vista queda en: guarda de capacidad, `get_object_or_404`, llamar, `messages`, redirect. Mismas consultas, mismo orden, mismo lock: es mover cuerpo de función, no reescribirlo.
- **Lo que NO hay que hacer:** sacar el aviso o el `_informar_a_siis` fuera de la transacción si hoy está dentro (o al revés); agregar `atomic` a `actualizar_genero` en el mismo PR (es cambio de comportamiento: va aparte, con test); cambiar los textos de `messages`.
- **Tests a agregar:** tests de servicio por acción (estado final, traza creada, aviso disparado con mock) sin pasar por HTTP; los de vista existentes quedan como contrato.
- **Verificación:** suite `test_becas_revision*` en verde; `assertNumQueries` actuales sin recalibrar; mutación: invertir la condición de estado en `rechazar` y ver rojo el test de servicio.
- **Regla para no repetirlo:** control mecánico · `test_arquitectura.py` · ratchet: cantidad de `.save(`/`select_for_update`/`transaction.atomic` en `programas/views/**` solo puede bajar.

---

### B-LIM-02 · Máquina de estados de `Relevamiento` dispersa y con reglas divergentes (backoffice vs API)
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo; relacionado con BEC-09/BEC-10 (hallazgos/02-siis-becas.md) · **Hallado por 2 revisores** (B1-LIM-04 + B6-LIM-05); origen de la absorbida: B6-LIM-05: nuevo; RED-03 (la cobertura de estas ramas) · **Ola:** 7 · **Esfuerzo:** L
- **ID de la pasada 1:** B1-LIM-04 + B6-LIM-05 (**hallado por 2 revisores**)
- **Ubicación:** `programas/views/relevamientos.py:912-928` (finalizar), `:931-994` (reabrir), `:904-908` (`estados_revisables`); `programas/views/revision.py:1357-1385` (terminar, `ESTADOS_TERMINABLES`); `programas/api/views.py:655-660` (iniciar), `:679-693` (finalizar acepta `EN_CURSO|FINALIZANDO`), `:703-707` (reabrir: solo `FINALIZADO` y **no** limpia `cerrado_automaticamente_en`); `programas/services/vencimientos.py:37-156`; `services/campo.py:65-66, 158-171`; `services/eliminacion.py:36`; `services/dashboard_becas.py:82`; templates `relevamientos/relevamiento_detail.html:153,165,175`, `revision/formulario_list.html:11`.
- **Escenario:** el mismo relevamiento en `FINALIZANDO` se puede finalizar desde la app y no desde el backoffice; reabierto por API conserva la marca de cierre automático y el cron/listados lo tratan distinto que reabierto por backoffice. Cualquier optimización de listados por estado (índices, filtros) tiene que cazar diez definiciones de «abierto/cerrado».
- **Causa raíz:** no hay dueño de las transiciones: cada superficie compara strings de estado y escribe el campo.
- **Solución (DECISIÓN CLIENTE, §7; propuesta por defecto: se unifican las reglas):** un único `programas/services/relevamientos.py` con la tabla de transiciones (`TRANSICIONES = {accion: Transicion(desde, hacia, periodo, sella/limpia)}`) y las constantes `ESTADOS_ABIERTOS`, `ESTADOS_CERRADOS`, `ESTADOS_REVISABLES`; vista, API y cron llaman a lo mismo y la vista pasa flags al template (`puede_finalizar`, …). Reglas unificadas: (1) **finalizar** desde `{EN_CURSO, FINALIZANDO}` en todos los canales (hoy el backoffice no acepta `FINALIZANDO`); (2) **reabrir** limpia siempre `cerrado_automaticamente_en` (hoy la API no lo limpia); (3) **reabrir** mantiene la exigencia del período **actual** (no hay captura offline de una reapertura); (4) **terminar** sigue con `ESTADOS_TERMINABLES`. Códigos (`code`), `status` y textos de error no cambian. Consistente con la Ola 7: es el paso (1) de la ola. **Va en un PR coordinado con Chaco-mobile** (la app debe tolerar `FINALIZANDO → FINALIZADO` desde el backoffice y la limpieza de la marca de cierre) y con los tests de contrato RED-11/RED-03 en el mismo diff; sin esa coordinación no se mergea.
- **Lo que NO hay que hacer:** cambiar códigos o mensajes que lee la app; mergear sin coordinar con Chaco-mobile (la app debe tolerar `FINALIZANDO → FINALIZADO` desde el backoffice y la limpieza de la marca de cierre); tocar `vencimientos` y la vista en el mismo PR sin test del cron.
- **Tests a agregar:** matriz unificada (estado origen × acción × canal → resultado) contra el servicio; el test que hoy fijaría la divergencia API/backoffice pasa a fijar la matriz única; en el mismo PR se actualizan los tests de contrato de RED-11/RED-03 que cubren estas acciones.
- **Verificación:** `test_api_campo_relevamiento_formulario`, `test_becas_relevamientos`, tests de `vencimientos` en verde; grep de `estado ==` / `estado in` sobre `Relevamiento` en views/api/templates baja a 0.
- **Regla para no repetirlo:** control mecánico · `test_arquitectura.py` · ninguna asignación `relevamiento.estado =` fuera de `services/relevamientos.py` (ratchet con lista congelada).

#### Aporte del segundo revisor (B6-LIM-05: El ciclo de vida del relevamiento en la app es una máquina de estados ad hoc repartida en tres acciones y cinco reglas de «habilitado»)
_Pasada 1: severidad MEDIA · estado CONFIRMADO (lectura) · esfuerzo S-M._

- **Ubicación:** `programas/api/views.py:639-661` (`iniciar`), `:663-694` (`finalizar`), `:696-708` (`reabrir`); el
  bloque de parseo de `capturado_en` está copiado igual en `:644-652` y `:668-676`. Reglas de «se puede operar»:
  `_captura_habilitada` (`views.py:122-128`), `campo.evaluar_captura` (`campo.py:139-178`), `rel.habilitado_en(now)`
  inline (`views.py:701`), `inscripcion_publica.py:153`, `portal/services/inscripcion.py:77-84`
  (`relevamiento_disponible`). Pausa: `_respuesta_pausa` antes del lock (`views.py:727`) y otra vez dentro de
  `evaluar_captura` (`campo.py:153`).
- **Escenario:** `finalizar` acepta un `capturado_en` pasado con `_captura_habilitada` pero `reabrir` exige «ahora»;
  la gracia G1-04 está en `evaluar_captura` y además en un `if` de `finalizar` (`:680`). Agregar un estado
  (p. ej. `FINALIZANDO` ya obligó a tocar dos `if`) es editar tres métodos y recordar cuál regla de período usa cada
  uno.
- **Causa raíz:** cada ficha (G1-04, K1, K2) arregló la acción donde apareció el síntoma; `services/campo.py` tiene
  el modelo (`Decision`) pero solo lo usa el alta.
- **Solución (preserva lógica):** `programas/services/relevamiento_campo.py` con una tabla explícita
  ```python
  TRANSICIONES = {
      "iniciar":   Transicion(desde={ASIGNADO}, hacia=EN_CURSO, idempotente_en={EN_CURSO}, periodo="captura"),
      "finalizar": Transicion(desde={EN_CURSO, FINALIZANDO}, hacia=FINALIZADO,
                              idempotente_si=lambda r: r.estado in (FINALIZADO, EN_REVISION) and en_gracia(r),
                              periodo="captura", sella="fecha_finalizado"),
      "reabrir":   Transicion(desde={FINALIZADO}, hacia=EN_CURSO, periodo="ahora", limpia="fecha_finalizado"),
  }
  def transicionar(rel, accion, capturado_en) -> Decision: ...
  ```
  que devuelve el mismo `Decision` de `campo.py` (con `detalle`/`code`/`status` idénticos a los de hoy: los textos
  «Solo se puede iniciar un relevamiento asignado.», `RELEVAMIENTO_NO_ASIGNADO`, etc. pasan a la tabla). Las tres
  acciones del viewset quedan en tres líneas: `get_object` → `transicionar` → `Response`. El parseo de
  `capturado_en` va a un `CapturaSerializer` de un campo (mismo 400 `CAPTURADO_EN_INVALIDO`). `_captura_habilitada`
  pasa a `campo.py` junto a `evaluar_captura`.
- **Lo que NO hay que hacer:** «arreglar» de paso que `reabrir` use la regla de captura: hoy exige el período
  **actual** a propósito (no hay captura offline de una reapertura). La tabla tiene que reproducir exactamente lo de hoy.
- **Tests a agregar:** `programas/tests/test_relevamiento_campo.py::TransicionesTests` parametrizado por
  `(accion, estado, capturado_en, pausa) → (status, code)` con la matriz de RED-03.
- **Verificación:** `programas.tests.test_becas_api` y `programas.tests.test_app_de_campo` en verde; la matriz nueva
  igual a las respuestas HTTP actuales (se genera corriendo contra el código de hoy antes de mover).
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md`, «Qué escalar»: «una acción de API que cambia
  `estado` con `if` propios en vez de pasar por la tabla de transiciones del dominio».

---

### B-LIM-03 · Detalles de convocatoria y relevamiento arman el contexto y escriben estado en la vista
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 7 · **Esfuerzo:** M
- **ID de la pasada 1:** B1-LIM-05
- **Ubicación:** `programas/views/relevamientos.py:282-391` (`ConvocatoriaDetailView.get_context_data`, ~110 líneas: agregados, conteos de padrón, dos forms, motivo, permisos), `:866-909` (`RelevamientoDetailView.get_context_data`), `:245-270` (`motivo_sin_alta_de_relevamientos`, función pública en una vista que decide por `type(pausa).__name__`), `:467-487` y `:490-514` (toggle/reactivar escriben `activo`, `cerrada_automaticamente`, `cerrada_el`), `:768-813` (solapamiento en `RelevamientoCreateView.form_valid`), `:829-838` (`_aviso_cierre_automatico`), `:1018-1179` (padrón: el texto del resumen de sesión se arma en la vista).
- **Escenario:** el detalle de convocatoria es la pantalla que más agregados corre; para medir o reducir sus consultas hay que levantar la vista entera con request. La regla «por qué no da altas» depende del nombre de la clase Python: renombrar un modelo de pausa la rompe sin error.
- **Causa raíz:** mismo patrón que B-LIM-01 en el otro archivo; RED-54 solo hizo selectores para revisión.
- **Solución:** selector `contexto_convocatoria_detalle(convocatoria, user)` y `contexto_relevamiento_detalle(...)` en `programas/selectors/convocatorias.py` / `selectors/relevamientos.py` (mismas consultas, mismo orden); `motivo_sin_alta_de_relevamientos` a `services/convocatorias.py` con despacho por `isinstance`/atributo, no por `__name__`; toggle/reactivar y solapamiento a `services/convocatorias.py`. La vista solo llama y renderiza.
- **Lo que NO hay que hacer:** cambiar las claves del contexto (los templates las leen); juntar consultas «de paso» (va en la tajada PERF con su medición).
- **Tests a agregar:** test del selector con `assertNumQueries` igual al medido hoy; test de `motivo_sin_alta` por tipo de pausa.
- **Verificación:** presupuesto `becas_relevamiento_detalle` y `edicion_convocatoria` sin recalibrar; `test_becas_relevamientos` verde.
- **Regla para no repetirlo:** agente · `.claude/skills/auditoria/rubricas/codigo-limpio.md` · «un `get_context_data` de más de 30 líneas o que llama `.aggregate(`/`.count(` es hallazgo: va a un selector».

---

### B-LIM-04 · «Aprobar → informar a SIIS → avisar al ciudadano» está escrito tres veces, con orden y regla de SIIS distintos
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — (relacionado: RED-79 por el `_informar_a_siis` clonado para no importar vista→vista) · **Ola:** 7 · **Esfuerzo:** M
- **ID de la pasada 1:** B4-LIM-02
- **Ubicación:** `programas/services/proceso_masivo.py:827-907` (`procesar_caso`); `programas/views/revision.py:965-1016`
  (aprobar) + `:229-250` (`_informar_a_siis`); `programas/views/cupo.py:265-288` (promover) + `:54-72` (`_informar_a_siis`,
  segunda copia: su docstring lo admite, «mismo helper que en views/revision.py»).
- **Escenario:** el mismo desenlace de dominio («el caso quedó APROBADO, informalo a SIIS y avisá») tiene tres dueños:
  - el masivo **avisa antes** de informar a SIIS (`:860-865` antes de `:879`); revisión y cupo **informan antes** de avisar;
  - «¿este programa valida con SIIS?» se pregunta de tres formas: el masivo filtra por `Q_PROGRAMA_VALIDA_SIIS`
    (`proceso_masivo.py:406`), revisión usa `_programa_sin_siis`, cupo usa `programa is None or programa.valida_siis`
    (`views/cupo.py:278`) — con `programa is None` cupo **sí** intenta el alta y revisión no;
  - dos vistas contienen el flujo de dominio completo (validar, aprobar, decidir si se informa, informar, avisar), contra la
    regla de CLAUDE.md «views/ orquestación HTTP, sin lógica de dominio».
  Cualquier regla nueva del circuito (p. ej. la de alta de oficio del 07-nov) hay que recordarla en tres lugares.
- **Causa raíz:** el servicio `cupo` devuelve un string y deja al llamador decidir qué hacer con él; no hay un servicio
  que sea dueño del **post-aprobación**.
- **Solución (judo):** `programas/services/resolucion.py` con
  ```python
  @dataclass(frozen=True)
  class Desenlace:
      resultado: Resolucion            # ver B-LIM-59
      envio: EnvioSIIS | None
      aviso_enviado: bool
  def despues_de_aprobar(caso, usuario, resultado, *, catalogos, avisar=True, conexion=None, url=None) -> Desenlace:
      envio = informar_a_siis(caso, usuario, catalogos) if resultado.es_beneficiario and valida_siis(caso) else None
      aviso = enviar_aviso_resolucion(...) if avisar else False
      return Desenlace(resultado, envio, aviso)
  ```
  con **un** `valida_siis(caso)` (sale de `programa.valida_siis`, la misma columna que `Q_PROGRAMA_VALIDA_SIIS`) y **un**
  `informar_a_siis` (el de `revision.py`, que devuelve `(envio, nivel, texto)` sin escribir `messages`). Las dos vistas
  quedan en «llamar al servicio + traducir `Desenlace` a `messages`»; `procesar_caso` usa lo mismo para el tramo del
  alta. El orden aviso/alta se fija una vez: **DECISIÓN JUEZ: por defecto «alta y después aviso»** (el de las dos
  pantallas), que es lo que ve el ciudadano si el alta falla; el masivo pasa a ese orden.
  Lo de `programa is None`: preservar la conducta de cada vista hoy pasando el predicado explícito hasta que el PM
  confirme cuál vale (`DECISIÓN CLIENTE: un segmento sin programa no informa a SIIS`).
- **Lo que NO hay que hacer:** meter el alta o el correo **dentro** de `aprobar_o_poner_en_espera` (es
  `@transaction.atomic`: un rollback dejaría el correo enviado; está escrito en `avisos_resolucion.py:18-21`). El nuevo
  servicio va **afuera** de la transacción, igual que hoy.
- **Tests a agregar:** `programas/tests/test_resolucion.py::DespuesDeAprobarTests.test_los_tres_caminos_dan_el_mismo_desenlace`
  (subTest: revisión, promover, masivo con el mismo caso y SIIS mockeado) y `test_programa_sin_siis_no_informa`.
- **Verificación:** `grep -rn "def _informar_a_siis" programas/views` vacío; tests de revisión/cupo/masivo verdes.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` → tabla de helpers
  canónicos: «Después de aprobar un caso (alta SIIS + aviso) → `programas.services.resolucion.despues_de_aprobar`;
  una vista que llama a `enviar_beneficiario_a_siis` o `enviar_aviso_resolucion` directamente es duplicado».

---

### B-LIM-05 · Las reglas del catálogo y los reordenamientos escriben desde las vistas, no desde `services/`
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 7 · **Esfuerzo:** M
- **ID de la pasada 1:** B5-LIM-02
- **Ubicación:** `programas/views/configuracion.py:1038-1079` (`preguntas_reordenar`: renumera todo el catálogo y
  reasigna grupo), `:865-909` (`requisitos_reordenar`: candado + renumeración), `:1251-1291` (`pregunta_toggle_activo`:
  G1-09 y Cambio 418), `:1296-1330` (`pregunta_eliminar`), `:1085-1096` (`grupo_crear`: cálculo de `orden`),
  `:1117-1128` (`grupo_eliminar`: escribe `ItemDiseno.etiqueta` de **otro agregado**, los diseños), `:513-522`.
- **Escenario:** hoy la única forma de reordenar el catálogo, activar una pregunta o borrar un grupo con sus efectos
  sobre los diseños es un request HTTP. Un comando, un seed o la API no pueden reutilizar la regla sin copiarla (eso ya
  pasó: ver B-LIM-35), y los tests de la regla tienen que pasar por el cliente de Django.
- **Causa raíz:** contradice la regla escrita de `CLAUDE.md` («`views/` orquestación HTTP, sin lógica de dominio»; «el
  peso del dominio va en `services/`»). Las vistas validan el payload **y** deciden el estado nuevo **y** lo escriben.
- **Solución:** `programas/services/catalogo.py` con `reordenar_catalogo(grupos)`, `crear_grupo(datos)`,
  `eliminar_grupo(grupo) -> str | None` (motivo), `cambiar_activo(pregunta) -> str | None`,
  `motivo_para_no_eliminar(pregunta) -> str | None`; y `programas/services/requisitos.py` con
  `reordenar(ancla, ids)` que levanta `ListaDesactualizada` (→ 409). La vista queda en: parsear JSON, llamar, traducir
  la excepción o el motivo a `JsonResponse`/`messages`. Los textos de los mensajes se mudan tal cual (misma estética).
- **Lo que NO hay que hacer:** mover también el parseo del payload al servicio: el 400 «Payload inválido» es HTTP.
- **Tests a agregar:** `programas/tests/test_catalogo_servicio.py::ReordenarCatalogoTests.test_las_no_enviadas_quedan_detras`,
  `::CambiarActivoTests.test_destino_siis_repetido_devuelve_motivo`, `::EliminarGrupoTests.test_disenos_conservan_el_nombre`.
- **Verificación:** los tests actuales de las vistas (`test_becas_*`) siguen verdes sin tocarlos; los nuevos no usan
  `self.client`.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md`, sección de capas:
  «Una vista de `programas/views/` que hace `.update(`, `.save(` o `.delete(` sobre un modelo distinto del objeto de la
  URL, o que recorre una lista para renumerar, es lógica de dominio en la capa equivocada: va a `services/`.»

---

### B-LIM-06 · La API de campo tiene el dominio del alta y de la identidad escrito en la vista
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo; toca RED-79 (aristas entre vistas) y SEC-24 (lógica que hoy vive acá) · **Ola:** 7 · **Esfuerzo:** M
- **ID de la pasada 1:** B6-LIM-01
- **Ubicación:** `programas/api/views.py:84-128` (`_formulario_por_dni`, `_es_el_mismo_alta`, `_captura_habilitada`),
  `:301-330` (`_pisar_identidad_acreditada`), `:333-419` (`_actualizar_validacion_identidad`, 87 líneas de cascada
  de identidad con escritura), `:422-457` (`_completar_alta`), `:466-483` (`_relevamientos_para_identificar`),
  `:507-573` (`responder_consulta_de_persona`, importada por `programas/api/views_emergencia.py:61`),
  `:639-708` (máquina de estados de `iniciar`/`finalizar`/`reabrir`), `:710-802` (la transacción del alta entera:
  lock, idempotencia, cupo, duplicado, insert, completar).
- **Escenario:** de las 923 líneas del módulo, unas 450 son reglas de dominio y escrituras sin nada de HTTP. Los tests
  ya lo delatan: `programas/tests/test_becas_api.py:17` y `programas/tests/test_padron_identidad.py:19` importan el
  **privado** `_actualizar_validacion_identidad` desde la vista para probar una regla de identidad; y el módulo de
  Emergencia importa una función de la vista de Becas (`views_emergencia.py:61`) para compartir la consulta de
  identidad. Cualquier tercer canal que necesite «validar la identidad declarada por el cliente» o «completar un alta
  cortada» (el alta de oficio, `programas/services/alta_de_oficio.py`, ya es el tercero) tiene que importar de
  `programas.api.views` o copiar.
- **Causa raíz:** el alta nació como endpoint (#82) y cada ficha posterior (Cambio 57, 91, SEC-23/24, G1-04/05/16,
  K2/K4) agregó su regla donde ya estaba el código, no en `services/`. `services/campo.py` existe y se creó justo
  para esto (G1-04/05), pero solo se llevó la mitad.
- **Solución (preserva lógica y contrato):**
  1. `programas/services/alta_campo.py` (nuevo) recibe, sin cambiar una línea de cuerpo: `formulario_por_dni`,
     `es_el_mismo_alta`, `pisar_identidad_acreditada`, `actualizar_validacion_identidad`, `completar_alta`,
     `formulario_fresco`, y una función `registrar_alta(rel, validated_data, *, usuario, contexto) -> ResultadoAlta`
     con el bloque `transaction.atomic()` de `:746-792`. `ResultadoAlta` es un dataclass
     `(formulario, creado: bool, rechazo: Decision | None, colision_uuid: bool, cupo_lleno: bool)`. La vista solo
     traduce `ResultadoAlta` a `Response` con los **mismos** `detail`/`code`/`status` de hoy.
  2. `programas/services/identidad.py` gana `consulta_de_persona(datos, relevamientos, buscar_en_legajos) ->
     (status, cuerpo)`; `responder_consulta_de_persona` queda en un módulo de API compartido
     (`programas/api/consulta_persona.py`) que envuelve eso en `Response`. Las dos vistas (Becas y Emergencia)
     importan de ahí y desaparece la arista API-vista → API-vista.
  3. Las transiciones de relevamiento van a la ficha B-LIM-02.
  4. En `views.py` quedan reexportados con el nombre viejo los dos privados que importan los tests
     (`_actualizar_validacion_identidad = alta_campo.actualizar_validacion_identidad`) hasta que los tests se
     muden; en el mismo PR se mudan y se borra el reexport.
- **Lo que NO hay que hacer:** meter `transaction.atomic` alrededor de `completar_alta` «para que quede atómico»:
  va **después** del commit a propósito (Cambio 91, `read_timeout` de 10 s con el lock tomado). Tampoco pasar
  `serializer.save()` al servicio: el servicio recibe `validated_data` y crea con `Formulario.objects.create` vía
  el mismo `serializer.save(**extras)` que hoy — o se pasa el serializer como `guardar=callable`, para no cambiar
  qué campos se escriben.
- **Tests a agregar:** `programas/tests/test_alta_campo.py::AltaCampoServicioTests.test_reintento_con_alta_incompleta_completa`,
  `.test_colision_de_client_uuid_no_inserta`, `.test_cupo_lleno_no_inserta` (el servicio sin pasar por HTTP);
  `programas/tests/test_arquitectura.py::CapasTests` sumando la regla «`programas/api/` no importa de
  `programas/api/views`» como ratchet.
- **Verificación:** `manage.py test programas.tests.test_becas_api programas.tests.test_becas_api_contrato
  programas.tests.test_app_de_campo programas.tests.test_padron_identidad programas.tests.test_emergencia_api_contrato`
  en verde sin tocar aserciones; presupuesto `becas_api_alta` de `scripts/perf_budgets.json` igual (31/1); `wc -l
  programas/api/views.py` < 450.
- **Regla para no repetirlo:** **control mecánico** · `programas/tests/test_arquitectura.py` · ratchet AST: «ningún
  módulo de `programas/api/` y `*/views/` define funciones de módulo que llamen a `.save(`, `.objects.create(`,
  `select_for_update(` o `transaction.atomic`» con lista `CONOCIDAS` que solo baja; mensaje: «lógica de escritura en
  la vista: va a `services/` (CLAUDE.md, Patrón de capas)».

---

### B-SEG-02 · Corregir el sexo desde un caso sin validar pisa la identidad de un legajo ya validado en otro caso, aun fuera del alcance de quien lo hace
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** SEG · **Origen:** nuevo · **Ola:** 0 · **Esfuerzo:** S
- **ID de la pasada 1:** B1-SEG-01
- **Ubicación:** `programas/views/revision.py:906-924` (`formulario_actualizar_genero`).
- **Escenario:** la ciudadana DNI 30.111.222 tiene el caso A (segmento S1) validado por Base de Personas con sexo `F`, aprobado e informado a SIIS; se reinscribe en una convocatoria del segmento S2 y entra el caso B, todavía sin validar. El Coordinador de S2 (con `becas.revision.identidad`, sin alcance sobre S1) abre B: la guarda de `:906` solo mira `formulario.validado_renaper` **del caso B**, así que permite cambiar el sexo. `ciudadano.genero` es del legajo compartido: el caso A —fuera de su alcance— pasa a decir `M`, contradiciendo la fuente oficial con la que se validó, y el próximo reenvío a SIIS de A sale con ese sexo. La traza queda solo en B.
- **Causa raíz:** la regla «identidad validada ⇒ sexo de solo lectura» se evalúa por caso, pero el dato que protege vive en `Ciudadano`, compartido por todos los casos de la persona.
- **Solución:** `DECISIÓN CLIENTE: por defecto, el sexo es de solo lectura si **cualquier** caso del ciudadano tiene la identidad validada por una fuente (origen PERSONAS o PADRON)`. Implementación: en la guarda, además de `formulario.validado_renaper`, `Formulario.objects.filter(ciudadano_id=ciudadano.pk, validado_renaper=True).exclude(origen_validacion=Formulario.OrigenValidacion.FORZADA).exclude(pk=formulario.pk).exists()` (índice por `ciudadano_id`; una consulta solo en el POST). El mismo predicado en `contexto_identidad` para no dibujar el selector que va a contestar «solo lectura».
- **Lo que NO hay que hacer:** acotar la guarda al alcance del usuario (dejaría pisar el sexo validado de un caso que el usuario sí ve); copiar el sexo al `Formulario` (cambio de modelo, otra decisión).
- **Tests a agregar:** `programas/tests/test_revision_identidad.py::ActualizarGeneroTests.test_no_cambia_sexo_validado_en_otro_caso_del_ciudadano`.
- **Verificación:** el test; verificar por mutación (quitar el `exists()` → rojo).
- **Regla para no repetirlo:** **skill** · `.claude/skills/seguridad-django/SKILL.md` · «Un dato de `Ciudadano` (legajo transversal) que se edita desde un caso de programa se protege con las reglas de **todos** los casos de la persona, no solo con el del caso abierto: el alcance del caso no acota el efecto de escribir en el legajo».

---

### B-SEG-03 · El cupo del link público se agota con inscripciones basura y rechazar no lo libera
**Severidad:** MEDIA · **Estado:** PLAUSIBLE · **Eje:** SEG · **Origen:** Origen oct.: SIIS-13 (🟡 abierto: opción (a) en Cambio 174, opción (b) pendiente de D-S13); esta ficha es el mismo conteo de cupo con RECHAZADO; (no lo cubre ningún hallazgo de oct.) · **Ola:** 0 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B6-SEG-01
- **Ubicación:** `programas/services/inscripcion_publica.py:155` (`_insertar_formulario`), `portal/services/inscripcion.py:77-84` (`relevamiento_disponible` / `cupo_completo`)
- **Escenario:**
  1. Hay un relevamiento con link abierto, sin padrón y con `cupo_maximo` de N.
  2. Un atacante resuelve un captcha por inscripción. El bucket por IP es de 10 cada 10 min y se esquiva rotando IP.
  3. Envía DNIs aleatorios hasta llegar a N.
  4. El link pasa a «cupo completo» para los ciudadanos reales.
  5. El operador rechaza los casos basura, pero `rel.formularios.count()` los sigue contando.
- **Causa raíz:** el cupo cuenta todos los formularios, incluidos los RECHAZADO. Además, en un link sin padrón no hay nada que ate el DNI a una persona real antes de consumir cupo.
- **Solución:**
  - `DECISIÓN CLIENTE`. Propuesta por defecto: excluir del conteo los casos RECHAZADO, igual que la exclusión de SIIS-13 para duplicados.
  - El filtro va en `_insertar_formulario` y en `cupo_completo`, y los dos tienen que contar igual.
  - Opcional: una alerta al operador cuando el ritmo de inscripciones de un link supera X por hora.
- **Lo que NO hay que hacer:** borrar los casos basura para liberar cupo. Se pierde la traza y se rompe la auditoría.
- **Tests a agregar:** `programas/tests/test_inscripcion_publica.py::CupoTest.test_rechazado_no_consume_cupo`
- **Verificación:** test en verde. Con el cupo lleno y un caso rechazado, el link vuelve a aceptar una inscripción.
- **Regla para no repetirlo:** **skill** · `.claude/skills/seguridad-django/` (inscripción pública) · «Todo recurso finito que se consume desde la superficie anónima (cupo, turnos) se puede agotar con captchas resueltos: definir qué estados lo liberan.»

---

### B-SEG-04 · El link anónimo crea legajos con identidad no verificada y escribe contacto en legajos reales
**Severidad:** MEDIA · **Estado:** PLAUSIBLE · **Eje:** SEG · **Origen:** mismo vector que G1-01 (cerrado para conversaciones), por otra puerta. SIIS-08 solo cubre identidades validadas. cruce oct.: G1-01 (✅ #663, Cambio 198) cerró el vector solo apagando conversaciones; octubre no cubrió ni descartó el link público (`_completar_contacto`, `get_or_create` del apoderado). SIIS-08 (✅ opción mínima D-S08) deja sin decidir la parte de fondo (`Ciudadano.identidad_origen`) · **Ola:** 0 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B6-SEG-02
- **Ubicación:** `programas/services/becas.py` `resolver_ciudadano_offline` (~l.441-532) y `_completar_contacto` (~l.360), invocados desde `programas/services/inscripcion_publica.py:248` (`_completar_envio`)
- **Escenario (tres variantes):**
  1. **Titular manual sin padrón:** se crea un `Ciudadano` con un DNI y un nombre tipeados por un anónimo.
  2. **Apoderado:** se hace `get_or_create` con cualquier DNI y nombre. Puede ser el DNI de un tercero que todavía no tiene legajo, y su legajo nace con el nombre inventado.
  3. **Legajo existente:** si el ciudadano ya existe y su celular o email están vacíos, `_completar_contacto` le escribe el teléfono y el correo del atacante. Las comunicaciones posteriores llegan al atacante.
- **Causa raíz:** el alta de legajos desde el link reutiliza el camino offline del agente de campo, que es de confianza. No distingue el origen anónimo ni espera a que la identidad se valide.
- **Solución:**
  - `DECISIÓN CLIENTE`. Propuesta por defecto: para formularios de un relevamiento público con identidad no validada (sin padrón ni RENAPER), no correr `_completar_contacto` ni crear el legajo del apoderado en `_completar_envio`.
  - Diferir las dos cosas a la aprobación del caso, que ya pasa por un operador.
  - Los datos siguen guardados en `datos_identificacion`, así que no se pierde nada.
- **Lo que NO hay que hacer:** pisar el contacto existente con el más nuevo. Agrava el problema.
- **Tests a agregar:** `programas/tests/test_inscripcion_publica.py::LegajoAnonimoTest.test_link_publico_no_completa_contacto_de_legajo_existente`, `...test_link_publico_no_crea_legajo_de_apoderado`
- **Verificación:**
  - Los tests están en verde.
  - Una inscripción pública sobre el DNI de un legajo sin email deja el email vacío.
- **Regla para no repetirlo:** **skill** · `.claude/skills/seguridad-django/` · «Ningún dato tipeado en una superficie anónima escribe en un legajo (`Ciudadano`) existente ni crea uno ajeno sin validación de identidad o revisión humana.»

---

### B-ERR-02 · «Revalidar con Base de Personas» guarda el sexo sin normalizar y da 500 con `FEMENINO`/`MASCULINO`
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** nuevo; colateral de SIIS-10 (cerrado: normalizó la *comparación* por inicial, no el valor devuelto) · **Ola:** 5 · **Esfuerzo:** S
- **ID de la pasada 1:** B1-ERR-01
- **Ubicación:** `programas/views/revision.py:1204-1208` y `:1218-1227` (`formulario_revalidar_renaper`); origen del valor en `programas/services/personas.py:205` (`normalizar_persona` → `"sexo": _texto(...).upper()`).
- **Escenario:** caso con `ciudadano.genero = "F"`; Base de Personas responde el registro con `sexo: "FEMENINO"` (el docstring de `_inicial_de_sexo`, `personas.py:131`, documenta que el proveedor manda `F` **y** `FEMENINO`). `nuevos["genero"] = "FEMENINO"` ≠ `"F"` → `ciudadano.genero = "FEMENINO"` → `save(update_fields=["genero", …])` sobre `CharField(max_length=1)` (`legajos/models/base.py`, `genero`). Con `sql_mode='STRICT_TRANS_TABLES'` (`config/settings.py:393`) MariaDB/MySQL devuelve 1406 *Data too long* → `DataError` → **500**; el `atomic` revierte todo y la identidad nunca queda validada por este botón. En SQLite (tests) el largo no se controla: la suite pasa.
- **Causa raíz:** la vista toma el sexo crudo del proveedor; los otros consumidores del mismo dato lo filtran contra `Ciudadano.Genero.values` (`services/becas.py:454-456`, `services/campo.py:257-258`) o lo reducen a la inicial. Este no.
- **Solución:** en `formulario_revalidar_renaper`, normalizar antes de armar `nuevos`: `sexo = _inicial_de_sexo(datos.get("sexo") or datos.get("genero"))` (exponerlo como helper público en `services/personas.py`, p. ej. `inicial_de_sexo`) y usar `sexo or ciudadano.genero`. Mismo resultado para `F`/`M`; deja de romper con la forma larga. Alternativa equivalente: que `normalizar_persona` devuelva ya la inicial en `"sexo"` (revisar `api/views.py:361,402` y `services/emergencia_confirmacion.py:143,165`, que leen la misma clave y escriben `genero`).
- **Lo que NO hay que hacer:** truncar con `[:1]` sin validar (un código numérico del proveedor se guardaría como sexo); quitar el modo estricto.
- **Tests a agregar:** `programas/tests/test_revision_identidad.py::RevalidarPersonasTests.test_sexo_en_forma_larga_se_guarda_como_inicial` (mock de `consultar_persona` con `sexo="FEMENINO"`; afirmar `genero == "F"` y que un valor de más de 1 carácter nunca llega al `save`, p. ej. con un `assert len(ciudadano.genero) <= 1` o validando `full_clean`).
- **Verificación:** el test anterior; reproducir en el banco MySQL (`scripts/perf_mysql/`) con el mismo mock y ver 302 en vez de 500.
- **Regla para no repetirlo:** **control mecánico** · `core/tests/` · test que recorre los `save(update_fields=…)` sobre `Ciudadano.genero` en vistas/servicios y exige que el valor pase por `Ciudadano.Genero.values` (o, más simple, que los tests de identidad corran `ciudadano.full_clean()` tras el `save`, que sí controla `max_length` en SQLite).

---

### B-ERR-03 · Editar el contacto del caso reescribe la fila entera y puede revertir una aprobación, un rechazo o una validación concurrentes
**Severidad:** MEDIA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** nuevo; mismo modo de falla que SIIS-17 (cerrado para `datos_siis` en su propia vista) · **Ola:** 5 · **Esfuerzo:** S
- **ID de la pasada 1:** B1-ERR-02
- **Ubicación:** `programas/views/revision.py:559-573` (lectura del caso) y `:625-628` (`form.save()`); segunda ubicación de menor impacto: `programas/views/relevamientos.py:1207-1209` (`relevamiento_modificar_cupo`, `CupoRelevamientoForm.save()`).
- **Escenario:** el coordinador A guarda un celular nuevo en el caso 812 (POST a `formulario_detalle`). Entre la lectura de la fila (`:559`) y el `form.save()` (`:627`) —`respuestas_legibles`, validación del form— el proceso masivo o el revisor B aprueban el caso (`_escribir_estado`: `UPDATE … SET estado='APROBADO' WHERE estado='ENVIADO'`, y el alta a SIIS, que no tiene baja), o el cruce de padrón lo valida (`validado_renaper=True`), o otro usuario guarda `datos_siis`. `ModelForm.save()` llama a `instance.save()` **sin `update_fields`**: escribe las ~40 columnas con los valores leídos al principio → `estado='ENVIADO'`, `validado_renaper=False`, `datos_siis` viejo. Resultado: beneficiario informado a SIIS con el caso de nuevo pendiente, el cupo liberado (se puede aprobar a otro por encima del máximo) y la traza diciendo «APROBADO». Para el relevamiento: `form.save()` del cupo reescribe `estado`/`fecha_hasta`/`territorial` leídos antes (carrera con `relevamiento_finalizar`, `reabrir` o el cron de 03:10), y el `clean_cupo_maximo` cuenta sin el candado que sí toma la API de campo (`api/views.py:748`).
- **Causa raíz:** guardado de fila completa sobre una instancia leída sin candado, en una tabla que otros caminos actualizan por compare-and-set de columna.
- **Solución:** en `formulario_detalle`, dentro del `atomic` existente: `form.save(commit=False)` y `formulario.save(update_fields=[*[c for c, *_ in cambios_por_campo], "modificado"])` con los nombres de campo que cambiaron (las `editables` cuyo valor difiere; `Formulario.save` ya agrega `dni_titular` si hace falta). Mismo patrón en `relevamiento_modificar_cupo`: `rel.save(update_fields=["cupo_maximo", "modificado"])`, y si se quiere cerrar también el conteo, releer con `Relevamiento.objects.select_for_update()` dentro de un `atomic` antes de validar (mismo orden de candado que la API: relevamiento primero). No cambia lógica ni pantalla.
- **Lo que NO hay que hacer:** `select_for_update` del caso durante todo el request (incluye `respuestas_legibles` y, en otras vistas, HTTP a SIIS: §0.4); comparar `modificado` para «detectar» la carrera y rechazar la edición.
- **Tests a agregar:** `programas/tests/test_revision_edicion.py::EdicionContactoTests.test_guardar_contacto_no_pisa_estado_cambiado_en_paralelo` (cargar el caso, cambiar `estado` por `.update()` simulando la otra transacción —con `mock.patch` sobre `respuestas_legibles` que hace el `update`— y afirmar que tras el POST el estado sigue `APROBADO`); `…::test_cupo_relevamiento_no_pisa_estado`.
- **Verificación:** los tests anteriores (rojos hoy por la escritura de fila completa).
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/` (corrección) · «En `Formulario` y `Relevamiento`, que tienen transiciones por `UPDATE … WHERE estado=…`, ningún `form.save()`/`obj.save()` sin `update_fields` sobre una instancia leída antes en el request: se guarda solo lo que el form edita».

---

### B-ERR-04 · «Producción territorial» deja afuera los relevamientos que arrancan el último día del rango
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** nuevo · **Ola:** 4 · **Esfuerzo:** S
- **ID de la pasada 1:** B2-ERR-01
- **Ubicación:** `programas/services/reportes_becas.py:236-239` (`reporte_produccion`).
- **Escenario:** filtro `desde=2026-11-01&hasta=2026-11-19` (hasta = hoy, el uso normal). Un relevamiento asignado hoy
  a las 09:00 (`fecha_asignada` es `DateTimeField` y el form lo carga con `datetime-local`, `programas/forms.py:1923-1927`
  y `:2135-2136`) no sale en el reporte, ni en «Asignados» ni en sus formularios: `hasta` es un `date` y el filtro
  `fecha_asignada__lte=hasta` lo compara contra `2026-11-19 00:00`. El lado `desde` está bien
  (`fecha_hasta >= desde 00:00`). Además, cada filtro con `date` sobre un `DateTimeField` emite el
  `RuntimeWarning: received a naive datetime` de Django.
- **Causa raíz:** se pasa un `date` a un lookup de `DateTimeField`; Django lo convierte en medianoche **naive** del
  primer instante del día, no en el día entero. El mismo módulo ya tiene el patrón correcto, `_filter_creado_rango`
  (`reportes_becas.py:42-47`), que usa `_aware_start` y `< hasta + 1 día`.
- **Solución:** misma semántica de solapamiento [asignada, hasta] contra [desde, hasta], con límites aware:
  ```python
  if desde:
      qs = qs.filter(fecha_hasta__gte=_aware_start(desde))
  if hasta:
      qs = qs.filter(fecha_asignada__lt=_aware_start(hasta + timedelta(days=1)))
  ```
  No cambia columnas, orden ni estética del reporte.
- **Lo que NO hay que hacer:** no pasar a `fecha_asignada__date__lte=hasta`: `__date` sobre un `DateTimeField` con
  `USE_TZ` compila a `CONVERT_TZ`, que en ECOM devuelve NULL (no hay tablas de zona horaria) y el reporte quedaría vacío
  solo en producción.
- **Tests a agregar:**
  `programas/tests/test_reportes_becas.py::ReporteProduccionTests.test_hasta_incluye_relevamientos_asignados_ese_dia`
  (relevamiento con `fecha_asignada` = hoy 10:00 y `hasta` = hoy → aparece; con `hasta` = ayer → no aparece).
- **Verificación:** el test; `manage.py test programas.tests.test_reportes_becas -W error::RuntimeWarning` sin el
  warning de naive datetime.
- **Regla para no repetirlo:** **control mecánico** · test ratchet en `programas/tests/test_arquitectura.py` · AST que
  marque `filter(<campo DateTimeField>__lte|__lt|__gte|__gt=<nombre>)` cuando el nombre viene de un `DateField` de form
  (`desde`/`hasta`/`fecha_desde`/`fecha_hasta`) sin pasar por `_aware_start`; allowlist inicial con
  `programas/views/relevamientos.py:706-708`, que tiene el mismo patrón y está fuera de esta tajada. Mensaje: «Un `date`
  contra un `DateTimeField` es medianoche naive: usar `_aware_start(d)` y `< _aware_start(hasta + 1 día)`; nunca
  `__date`».

---

### B-ERR-05 · La distribución de una pregunta del catálogo cuenta respuestas que una condición ocultó
**Severidad:** MEDIA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** remanente de G2-01 (Ola 3 PR 8, #622), que cerró la mitad de las condiciones solo para los campos propios · **Ola:** 4 · **Esfuerzo:** M
- **ID de la pasada 1:** B2-ERR-02
- **Ubicación:** `programas/services/dashboard_becas.py:758-789` (las `Pregunta` del catálogo nacen con `plan=()`),
  `programas/services/dashboard_becas.py:1067-1081` (solo se evalúa la condición `if pregunta.plan`).
- **Escenario:** una convocatoria pone una pregunta general `pg-13` (selector Sí/No) dentro de un grupo condicionado
  («solo si tiene hijos = Sí»). Un caso responde «tiene hijos = No» pero la app o el contrato anterior dejan escrito
  `data.globales.13 = "Sí"` (`legacy_desde_respuestas`, `programas/services/respuestas.py:199-220`, copia a `data` lo que
  venga en `respuestas` sin pasar por el motor de condiciones). El dashboard cuenta ese «Sí» en la base y en la opción;
  el Excel por persona de la misma convocatoria lo saca (`dashboard_becas.py:1613-1616` borra de `data` las claves
  `ocultas`). Los dos números del mismo recorte no cierran.
- **Causa raíz:** el filtro por condición (`_la_condicion_la_oculta`) se armó para los `cp-` porque el plan sale del
  diseño de **una** convocatoria (`_preguntas_propias`); las preguntas del catálogo son del programa entero y pueden
  estar condicionadas distinto en cada diseño, así que nunca reciben plan.
- **Solución:** para una pregunta del catálogo que **en algún diseño en alcance** está condicionada (ella o su grupo),
  agrupar además por `relevamiento__convocatoria_id` y por las claves de su cierre transitivo **en ese diseño**, y
  evaluar la condición con el plan de esa convocatoria, igual que hoy con los `cp-` (una consulta por pregunta, una
  evaluación por combinación). Las que no están condicionadas en ningún diseño siguen por el camino actual sin costo
  extra. Mismo resultado visual; solo cambia el número cuando había respuestas ocultas.
  `DECISIÓN CLIENTE` solo si el PM prefiere no recalcular: por defecto, corregir (es lo que G2-01 prometió).
- **Lo que NO hay que hacer:** no leer la foto (`definicion`) por caso para evaluar la condición: es la consulta que el
  `read_timeout` de 10 s no tolera (G2-01, ronda 2).
- **Tests a agregar:**
  `programas/tests/test_dashboard_campos_propios.py::DistribucionCondicionesTests.test_pregunta_del_catalogo_oculta_no_cuenta`
  y `...test_misma_pregunta_condicionada_en_una_convocatoria_y_libre_en_otra`.
- **Verificación:** los dos tests; comprobar primero en testing si hay casos con respuesta guardada en una pregunta
  condicionada y oculta (si no los hay, la ficha baja a BAJA). La consulta va en el Escenario de la pasada 2.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/` (rúbrica de Becas) · «Toda cifra de
  respuestas tiene que aplicar el motor de condiciones a **todas** las claves, catálogo y propias. Si el dashboard y el
  Excel por persona del mismo recorte no dan lo mismo para una pregunta, es un bug».

---

### B-ERR-06 · El vaciado de la tabla intermedia registra el envío con el plan del programa, no el del payload
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** Thermos corrección · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** B3-ERR-02
- **Ubicación:** `programas/services/siis_envio.py:1452`. Hay que compararlo con 1253-1254 (`enviar_beneficiario_a_siis`) y con 1321 (`guardar_en_tabla_intermedia`).
- **Escenario:** la fila intermedia se guardó con un `id_plan_soc` que no es el `id_programa` del programa. Pasa con un plan por segmento, o cuando el programa cambió de plan entre el guardado y el vaciado. `_base_envio(formulario, ...)` toma el plan del programa, y `EnvioSIIS.save()` deriva `clave_persona_plan = "<doc>:<plan>"` de ese plan. Pasan dos cosas. Primero, la auditoría del envío dice un plan distinto del que se mandó. Segundo, el índice único de SIIS-05 mira la clave equivocada: o deja pasar un segundo alta persona+plan real por otra vía, o da un DUPLICADO_LOCAL falso con un envío legítimo.
- **Causa raíz:** el vaciado arma `base` sin el paso que las otras dos vías hacen después de armar el payload (`base["id_programa"] = payload["id_plan_soc"]`).
- **Solución:** antes de 1452, copiar lo de 1253-1254: tomar el payload de `payload_de(alta)` y, si trae `id_plan_soc`, pisar `base["id_programa"]` con ese valor. Es la misma línea de las otras dos vías.
- **Lo que NO hay que hacer:** no cambiar `_base_envio` para todas las vías. Las otras ya corrigen el plan después.
- **Tests a agregar:** una fila intermedia con `id_plan_soc` distinto del programa. Después del vaciado, `EnvioSIIS.clave_persona_plan` termina en el `id_plan_soc` de la fila.
- **Verificación:** mutación. Sacar la línea nueva pone el test en rojo.
- **Regla para no repetirlo:** el `EnvioSIIS` se registra siempre con el plan que viaja en el POST. Si hay más de una vía, sacar la armada de `base`+payload a un único helper.

---

### B-ERR-07 · `procesar_casos_siis` vacía TODA la tabla intermedia aunque se le pida una convocatoria, relevamiento o segmento
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** Thermos corrección · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** B3-ERR-03
- **Ubicación:** `programas/management/commands/procesar_casos_siis.py:134-208` (`_vaciar_tabla_intermedia`) y la llamada en 362. Los filtros `--convocatoria/--relevamiento/--segmento` de 365-374 solo aplican a los casos nuevos.
- **Escenario:** el operador corre `procesar_casos_siis --convocatoria 1 --aplicar --si` para soltar solo la Convocatoria 1 en PRD. En la tabla intermedia quedaron filas pendientes de otra convocatoria, por ejemplo los cursos que se dejaron afuera a propósito. El vaciado las manda igual, y el alta no tiene baja. `--si` saltea la confirmación, y la confirmación de 359 tampoco dice cuántas filas de afuera del filtro van a salir. El mismo vaciado ignora `--solo-completos` y el filtro de materias.
- **Causa raíz:** el vaciado se pensó como un paso previo global y nunca recibió los filtros del comando.
- **Solución:** pasarle a `_vaciar_tabla_intermedia` los mismos `convocatoria/relevamiento/segmento`, y filtrar las filas `AltaIntermediaSIIS` por `formulario__relevamiento__...` igual que en 365-374. Sin filtros, el comportamiento sigue como hoy. Sumar al ensayo el conteo de filas intermedias que saldrían.
- **Lo que NO hay que hacer:** no sacar el vaciado. Es lo que libera la tabla después de una caída.
- **Tests a agregar:** dos filas intermedias de convocatorias distintas. Con `--convocatoria A --aplicar`, solo se manda la de A (mock de `cargar_beneficiario`).
- **Verificación:** mutación sobre el filtro nuevo.
- **Regla para no repetirlo:** todo paso que llame a SIIS dentro de un comando con filtros de alcance respeta esos filtros. Si no los respeta, lo dice en el ensayo con el número de casos.

---

### B-ERR-08 · `correr_alta_siis` pierde toda la salida del hijo cuando corta por freno o error
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** Thermos corrección · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** B3-ERR-04
- **Ubicación:** `programas/management/commands/correr_alta_siis.py:207-213` (`_correr`). El corte del hijo está en `_base_siis.py:254-257` (`_cortado_por_fallas`, `SystemExit(1)`).
- **Escenario:** a mitad de una tanda de 500, `procesar_casos_siis` corta por el freno (3 inciertos seguidos). `_correr` redirige stdout/stderr del hijo a un `StringIO` y lo imprime solo cuando `call_command` vuelve. El `SystemExit` o el `CommandError` salen antes, así que se pierden el mensaje DETENIDO, la cuenta de cuántos salieron y la indicación de correr `conciliar_envios_siis`. Además, durante la tanda (minutos) no se ve ningún avance. El operador no sabe qué casos quedaron inciertos.
- **Causa raíz:** el buffer se vuelca después de la llamada y no en un `finally`.
- **Solución:** volcar el buffer en un `try/finally` alrededor del `call_command` y relanzar la excepción. Si se quiere ver el avance, pasar el `self.stdout` real en lugar de un `StringIO` para las tandas.
- **Lo que NO hay que hacer:** no tragar el `SystemExit`. La orquestación tiene que seguir cortando.
- **Tests a agregar:** un hijo simulado que escribe y después lanza `SystemExit(1)`. La salida de `correr_alta_siis` contiene lo que escribió el hijo y el código de salida sigue siendo 1.
- **Verificación:** correr el test con la versión actual (rojo) y con el `finally` (verde).
- **Regla para no repetirlo:** toda captura de salida de un subcomando se vuelca en `finally`.

---

### B-ERR-09 · `conciliar_envios_siis` acepta el mismo envío dos veces con decisiones opuestas y actualiza sin mirar el estado
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura); la carrera, PLAUSIBLE · **Eje:** ERR · **Origen:** Thermos corrección · **Hallado por 2 revisores** (B3-ERR-05 + B3-LIM-12); origen de la absorbida: B3-LIM-12: SIIS-02 (cerrado) · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** B3-ERR-05 + B3-LIM-12 (**hallado por 2 revisores**)
- **Ubicación:** `programas/management/commands/conciliar_envios_siis.py:193-220` (`_filas_del_csv`), `222-248` (`_aplicar`) y `155-189` (`_confirmar`/`_liberar`).
- **Escenario 1:** el CSV de ECOM trae el `envio_id` 812 dos veces, una con `confirmar` y otra con `liberar` (un copy-paste, o dos personas que completaron la misma planilla). `_aplicar` aplica las dos en orden y gana la última. El caso que SÍ está en SIIS queda liberado, y la próxima corrida lo vuelve a mandar, lo que da un alta doble.
- **Escenario 2:** dos conciliaciones a la vez, o una conciliación mientras corre un reintento. La validación del estado se hace al principio (232), pero el `UPDATE` de 155-189 filtra solo por `pk`. Entre la validación y el update, otro proceso pudo cambiar el envío.
- **Además:** `--usuario` es opcional, así que la traza de una decisión irreversible puede quedar sin autor.
- **Causa raíz:** no hay chequeo de duplicados en la entrada, y el update no es condicional al estado que se validó.
- **Solución:**
  1. En `_filas_del_csv`, rechazar el archivo entero si un `envio_id` aparece más de una vez, listando los ids.
  2. En `_confirmar`/`_liberar`, agregar al `filter(pk=...)` el estado esperado (`estado=INCIERTO` o EN_PROCESO vencido) y `vigente=True`, y contar las filas afectadas. Si es 0, avisar y no seguir con ese envío.
  3. Hacer obligatorio `--usuario` cuando va con `--aplicar`.
- **Lo que NO hay que hacer:** no resolver los duplicados por «gana la primera». Ante una contradicción, la decisión es humana.
- **Tests a agregar:** un CSV con un id duplicado y decisiones distintas da error sin tocar nada. Un envío que cambió de estado entre la validación y el update no se pisa.
- **Verificación:** mutación sobre el filtro de estado del update.
- **Regla para no repetirlo:** todo `UPDATE` que materializa una decisión validada antes filtra por el estado validado.

#### Aporte del segundo revisor (B3-LIM-12: La conciliación escribe las transiciones de `EnvioSIIS` desde el comando, sin el chequeo de estado previo que tiene `_cerrar`)
_Pasada 1: severidad MEDIA · estado CONFIRMADO (lectura; la carrera, PLAUSIBLE) · esfuerzo S._

- **Ubicación:** `conciliar_envios_siis.py:88-97` (selector de inciertos), `155-189` (`_confirmar`/`_liberar`), `232` (valida todo primero) y `241-247` (escribe después). Contra `siis_envio.py:1171-1197` (`_cerrar`: `filter(pk=…, estado=EN_PROCESO).update(...)`).
- **Escenario:** el invariante «`vigente` y `clave_persona_plan` se mueven juntos» está escrito dos veces: en `_cerrar` y en el comando. El comando valida todos los pk con `_envio()` y escribe en un segundo bucle con `filter(pk=envio.pk).update(...)`, **sin condición de estado**. Si entre la validación y la escritura el envío cambia (otra conciliación en paralelo, o un `EN_PROCESO` vencido cuyo proceso se destrabó y `_cerrar` lo dejó `ENVIADO`), `--liberar` lo pasa a `ERROR` con `vigente=None` y el caso vuelve a ser candidato con el alta hecha del otro lado. La ventana es chica (un `EN_PROCESO` tiene más de 5 minutos para entrar), por eso la carrera es PLAUSIBLE. El problema de capa está confirmado.
- **Causa raíz:** la máquina de estados del envío no tiene dueño único; el comando la reimplementa.
- **Solución:** `siis_envio.conciliar(envio, decision, *, siis_id=None, motivo="", usuario=None) -> bool` con `EnvioSIIS.objects.filter(pk=envio.pk, vigente=True).exclude(estado=ENVIADO).update(...)`, la traza dentro de la misma `atomic()` y `False` si no actualizó ninguna fila. El selector `_inciertos` pasa a `EnvioSIIS.objects.inciertos()` (manager), junto a `EnvioSIIS.incierto`, que ya define el mismo criterio por instancia. El comando queda con CSV, argumentos y log, e informa «#N cambió de estado, no se tocó».
- **Lo que NO hay que hacer:** envolver los dos bucles del comando en una sola transacción larga con `select_for_update`. Con `read_timeout = 10 s` en ECOM, un CSV de cientos de filas mata la conexión (§0.4).
- **Tests a agregar:** `programas/tests/test_conciliar_envios_siis.py::CarreraTests.test_liberar_no_pisa_un_envio_que_paso_a_enviado`.
- **Verificación:** `grep -n "EnvioSIIS.objects.filter(pk=" programas/management/commands/conciliar_envios_siis.py` vacío.
- **Regla para no repetirlo:** **skill** · rúbrica `codigo-limpio.md` · «Toda escritura de `EnvioSIIS.estado`/`vigente` va por `siis_envio` y condiciona el `UPDATE` al estado leído. En un comando es lógica de dominio en la capa equivocada.»

---

### B-ERR-10 · `_sentencias` parte mal un literal que termina en barra invertida escapada
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura); el impacto depende del contenido de los volcados (PLAUSIBLE) · **Eje:** ERR · **Origen:** Thermos corrección · **Hallado por 2 revisores** (B3-ERR-09 + B3-LIM-14); origen de la absorbida: B3-LIM-14: RED-01 (insumos fuera de la imagen) · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** B3-ERR-09 + B3-LIM-14 (**hallado por 2 revisores**)
- **Ubicación:** `programas/management/commands/correr_alta_siis.py:113-140`, con la condición `anterior == "\\"` en 125.
- **Escenario:** un insumo SQL trae `'C:\\'` o un valor que termina en `\\'`. `_sentencias` toma la comilla de cierre como escapada, sigue dentro del literal y parte mal en el próximo `;`. En autocommit, las sentencias anteriores ya se aplicaron y la siguiente da `ProgrammingError`, así que el insumo queda cargado a medias. `_sin_comentarios` sí cuenta las barras de a pares. Es PLAUSIBLE porque no se verificó que algún insumo real traiga ese patrón.
- **Solución:** contar las barras invertidas consecutivas antes de la comilla, como hace `_sin_comentarios`. La comilla está escapada solo si la cantidad es impar.
- **Tests a agregar:** `"INSERT ... VALUES ('a\\\\'); SELECT 1;"` se parte en 2 sentencias.
- **Verificación:** test.
- **Regla para no repetirlo:** un solo tokenizador de SQL para los dos helpers.

#### Aporte del segundo revisor (B3-LIM-14: Dos máquinas de estado de comillas distintas para partir los `.sql`; la segunda trata como escapada la comilla que cierra después de `\\`)
_Pasada 1: severidad MEDIA · estado PLAUSIBLE (depende del contenido de los volcados) · esfuerzo S._

- **Ubicación:** `correr_alta_siis.py:83-110` (`_sin_comentarios`: un `\` adentro de una cadena consume el par entero, bien) y `113-140` (`_sentencias`: decide el escape mirando solo `anterior != "\\"`).
- **Escenario:** un valor que termina en barra invertida se vuelca como `'C:\\datos\\'`: la comilla de cierre va precedida de `\` pero no está escapada. `_sentencias` la toma como escapada, sigue «dentro de la cadena» y se come los `;` siguientes: varias sentencias viajan pegadas en un `cur.execute` y MySQL devuelve error de sintaxis, o el `INSERT` carga de menos sin aviso si el driver acepta multi-statement. Los volcados del organismo (`DatosPersonas.sql`, con domicilios en texto libre) son el tipo de dato donde aparece. Además, un tokenizador de SQL de 60 líneas en un comando es lógica de insumos fuera de su módulo: `_insumos_siis.py` existe justamente para eso.
- **Causa raíz:** el mismo problema (comillas con escape) se resolvió dos veces con dos criterios.
- **Solución:** una sola función `sentencias_sql(texto)` en `_insumos_siis.py` con **un** recorrido: estado `comilla`, consumo del par `\x` dentro de cadenas, corte de `--` fuera de cadenas y corte en `;` fuera de cadenas. `correr_alta_siis` la importa. Comportamiento idéntico para todo `.sql` que hoy se parte bien.
- **Lo que NO hay que hacer:** pasar a `sqlparse` sin medirlo con los volcados reales (10 MB): cambia la dependencia de runtime y el tiempo del paso 2.
- **Tests a agregar:** `programas/tests/test_insumos_siis.py::SentenciasTests.test_barra_final_dentro_de_cadena`, `…test_punto_y_coma_en_comentario`, `…test_comilla_escapada`.
- **Verificación:** con `"INSERT INTO t VALUES ('a\\\\'); INSERT INTO t VALUES ('b');"` salen 2 sentencias (hoy sale 1).
- **Regla para no repetirlo:** **skill** · rúbrica `codigo-limpio.md` · «Un parser escrito a mano tiene un solo dueño y su batería de casos borde; dos recorridos del mismo texto con criterios distintos son un hallazgo.»

---

### B-ERR-11 · Desde Cupo se encola y se aprueba un caso con conflicto de carga duplicada sin resolver
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** — (misma regla que la guarda de `formulario_aprobar`; complementa BEC-02) · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** B4-ERR-01
- **Ubicación:** `programas/services/cupo.py:252-315` (`promover_lista_espera`: relee estado y `promovido` bajo
  candado, nunca el conflicto), `programas/services/cupo.py:406-449` (`agregar_a_lista_espera`, ídem);
  `programas/views/cupo.py:251-289` y `:292-322` (las vistas tampoco lo miran); `programas/views/cupo.py:154-156`
  (la solapa «Pendientes» lista ENVIADO con conflicto y ofrece «Agregar a lista de espera»). La regla existe en
  `programas/views/revision.py:359-362` (`_tiene_conflicto_duplicado_pendiente`) y se aplica en `:945-947` (aprobar) y
  `:1096-1098` (rechazar); el masivo excluye esos casos en `programas/services/proceso_masivo.py:683-685`.
- **Escenario:** el caso A queda en espera por cupo lleno; después sincroniza desde la app una segunda carga B de la
  misma persona y queda `cargas_en_conflicto` pendiente sobre A. Desde Cupo, «Promover» pasa A a `APROBADO` sin que
  nadie resuelva el duplicado (en la pantalla de revisión, «Aprobar» lo frena con «Primero debés resolver el conflicto
  de cargas duplicadas»). Peor: B aparece en «Pendientes» del cupo, se lo agrega a la espera y, con su validación SIIS
  hecha, también se promueve → dos casos `APROBADO` de la misma persona ocupando **dos** lugares del segmento (el alta
  en SIIS la frena `DUPLICADO_LOCAL`, el cupo no).
- **Causa raíz:** la regla «el conflicto de carga duplicada lo decide una persona antes de resolver» vive en la vista
  de revisión y en el selector del masivo, no en el servicio de cupo; los dos caminos de Cupo nunca la heredaron.
- **Solución:** mover el predicado `_tiene_conflicto_duplicado_pendiente` a `programas/services/cupo.py` (o a
  `services/becas.py`) e invocarlo **dentro** del candado en `promover_lista_espera` (después de releer el estado, antes
  de contar el cupo) y en `agregar_a_lista_espera` (junto al chequeo de espera activa), levantando
  `ValidationError("Primero debés resolver el conflicto de cargas duplicadas.")`. `revision.py` importa el mismo helper.
  No cambia ninguna regla: aplica en Cupo la que ya rige en revisión y en el masivo.
- **Lo que NO hay que hacer:** no filtrar solo la solapa «Pendientes» del template/vista: la mutación por URL directa
  (POST a `lista_espera_promover`) seguiría pasando.
- **Tests a agregar:** `programas/tests/test_becas_cupo.py::ConflictoDuplicadoEnCupoTests.test_promover_con_conflicto_pendiente_falla`,
  `.test_agregar_a_espera_con_conflicto_pendiente_falla`, `.test_resuelto_el_conflicto_promueve`.
- **Verificación:** mutación: quitar la llamada en `promover_lista_espera` y ver el test rojo.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/` (rúbrica de Becas) · «Toda transición a
  `APROBADO` o a lista de espera pasa por las mismas guardas de dominio que `formulario_aprobar` (conflicto de duplicado,
  espera activa, identidad); si una guarda vive en una vista, la próxima vía de aprobación no la hereda: va al servicio».

---

### B-ERR-12 · Una caída de la conexión a la base deja la corrida masiva «en curso» sin motivo y el hilo muere con la excepción
**Severidad:** MEDIA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** — (deriva de SIIS-03; el «Lost connection» por `read_timeout` está documentado en `proceso_masivo.py:717-724`) · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** B4-ERR-02
- **Ubicación:** `programas/services/proceso_masivo.py:1156-1164` (`except Exception` llama a `_guardar` sobre la misma
  conexión rota), `:1144-1155` (las otras dos ramas, ídem), `:1081-1086` (contrato «Nunca lanza»), `:1184-1189`
  (`trabajo()` solo tiene `finally`). Contraste: `programas/services/alta_de_oficio.py:309-311` +
  `programas/management/commands/inscribir_de_oficio.py:158-159`, que ante `OperationalError` hacen
  `close_old_connections()` antes de seguir.
- **Escenario:** con la base de ECOM ocupada, `ids_de(candidatos(...))` o cualquier consulta de la corrida muere con
  `OperationalError 2013 Lost connection`. Django marca `errors_occurred`, pero no reconecta solo: el `_guardar` del
  `except` sale por el mismo socket muerto y lanza `2006 MySQL server has gone away`. La excepción escapa de `correr`,
  el hilo la vuelca a stderr y la fila queda `EN_CURSO` con el latido viejo: la pantalla muestra «en curso» hasta 5
  minutos (`LATIDO_VENCIDO`), y la corrida siguiente la cierra como «Interrumpida: sin señal…». La causa real no queda
  en ningún lado que mire el coordinador.
- **Causa raíz:** fuera de un request nadie llama a `close_if_unusable_or_obsolete`; el hilo reutiliza la conexión que
  falló para informar la falla.
- **Solución:** al inicio de cada `except` de `correr`, `connection.close_if_unusable_or_obsolete()` (cierra solo si
  la conexión quedó inutilizable; la próxima consulta reconecta); y envolver el `_guardar` de las ramas de error en un
  `try/except` que haga `logger.exception(...)` si tampoco puede escribir, para que el hilo no muera con una excepción
  sin registrar. No cambia ningún desenlace: es el mismo `DETENIDA` con su mensaje, ahora escrito.
- **Lo que NO hay que hacer:** no envolver `correr` en un `transaction.atomic`: la corrida dura una hora y el
  diseño (`:1087-1089`) es confirmar por caso.
- **Tests a agregar:** `programas/tests/test_proceso_masivo.py::CorridaConexionCaidaTests.test_lost_connection_deja_la_corrida_detenida_con_motivo`
  (mock de `ids_de` que lanza `OperationalError` y de `connection.is_usable` → `False`; afirmar estado `DETENIDA` y
  mensaje con el error).
- **Verificación:** el test anterior; en el banco MySQL, matar la conexión de la corrida (`KILL <id>`) durante la
  selección y ver la fila `DETENIDA`.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` · «Código que corre fuera de un
  request (hilos, comandos largos) y captura `OperationalError` llama a `connection.close_if_unusable_or_obsolete()`
  antes de volver a usar la base: Django solo lo hace solo al principio y al final de cada request».

---

### B-ERR-13 · La condición por defecto de un grupo del catálogo puede quedar detrás de su fuente y ocultar el grupo para siempre
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** — (relacionado con BEC-04, resuelto; otro mecanismo) · **Ola:** 6 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B5-ERR-01
- **Ubicación:** `programas/forms.py:1365` (única validación de RN-6); `programas/views/configuracion.py:1038` (`preguntas_reordenar`) y `:1206` (`PreguntaGlobalUpdateView`, cambio de grupo) no revalidan; `programas/services/diseno.py:214` (`plan_por_defecto`) y `:133` (`_resolver_condicion`) la copian sin chequear orden.
- **Escenario:** el grupo Apoderado tiene `condicion_defecto` «edad < 18» sobre una pregunta del grupo Datos personales (validada al guardar el grupo). Un admin arrastra Apoderado por encima de Datos personales en el catálogo, o mueve la pregunta fuente al propio grupo Apoderado o a uno posterior. Nada lo rechaza. Toda convocatoria sin diseño guardado, y todo grupo nuevo que entra por `reconciliar`/`items_vigentes`, recibe la condición con la fuente después del grupo. `condiciones.aplicar` (`programas/services/condiciones.py:200`) y su espejo `static/custom/js/nodo-condiciones.js:132` evalúan en orden: la fuente todavía está vacía, el grupo queda oculto, sus obligatorios no se exigen y un menor se inscribe sin apoderado. En el constructor, `asegurar_coherencia` (`programas/services/constructor.py:217`) rechaza toda mutación y «Restablecer» (`programas/views/diseno.py:298`) devuelve 400 siempre.
- **Causa raíz:** el invariante «la fuente de la condición por defecto está en un grupo anterior» (RN-6) se valida solo en el formulario del grupo, no en las otras dos escrituras que cambian el orden o la pertenencia de la fuente.
- **Solución:** extraer la verificación de `validar_condicion_defecto` (`programas/services/diseno.py:192`) a una función que reciba el orden resultante y llamarla también en `preguntas_reordenar` (con el orden del payload, antes de guardar) y en `PreguntaGlobalForm.clean` cuando cambia `grupo`. Si rompe RN-6, responder 400 o error de form con el mismo texto que ya da el modal del grupo. No cambia la evaluación ni la estética.
- **Lo que NO hay que hacer:** no limpiar la condición en silencio al reordenar (pierde la regla de negocio); no relajar `aplicar` para evaluar fuentes posteriores (cambia la semántica en app y portal).
- **Tests a agregar:** reordenar grupos dejando el condicionado antes de su fuente → 400 y orden intacto; mover la pregunta fuente al grupo condicionado → error de form; `plan_por_defecto` de un catálogo válido no produce errores en `validar_coherencia`.
- **Verificación:** mutación: quitar la llamada nueva en `preguntas_reordenar` y ver el test rojo.
- **Regla para no repetirlo:** **skill** · `.claude/skills/seguridad-django` (sección de invariantes) · «Un invariante entre filas (orden, pertenencia) se valida en el servicio, no en un solo form: toda escritura que mueva cualquiera de las filas pasa por la misma función.»

---

### B-ERR-14 · Cambiar el tipo u opciones de una pregunta o requisito fuente de condiciones deja condiciones imposibles en diseños guardados
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** — (BEC-04 cubre canal, no tipo/opciones) · **Ola:** 6 · **Esfuerzo:** M
- **ID de la pasada 1:** B5-ERR-02
- **Ubicación:** `programas/forms.py:1395` (`PreguntaGlobalForm`) y `:1577` (`RequisitoNativoForm`, editable por Coordinador con `requisito.editar`); `programas/services/diseno.py:716` (`items_planos` lee `tipo_campo` del catálogo vivo); `programas/services/constructor.py:218` (`validar_coherencia` sin diff contra el estado previo).
- **Escenario:** un diseño tiene «mostrar si `situacion` es "Desocupado"». Alguien cambia `situacion` de SELECTOR a SELECTOR_MULTIPLE, saca la opción "Desocupado", o cambia una DATE con regla `edad_menor` a STRING. Nada mira los diseños ni las `condicion_defecto` que la usan. En portal y app el operador deja de aplicar (`es` compara contra `str(list)`; `edad_menor` sobre texto da None → falso) y el ítem queda oculto para siempre; ni `reconciliar` ni `items_vigentes` lo limpian. En el constructor, cualquier mutación de ese diseño devuelve 400 hasta que alguien quite la condición (solo los errores de canal pasan por `solo_lo_nuevo`).
- **Causa raíz:** el tipo y las opciones de una fuente se tratan como datos libres del catálogo, sin el chequeo de dependientes que sí tiene la baja (`registrar_baja_del_catalogo`, `programas/services/diseno.py:313`).
- **Solución:** en `clean()` de ambos forms, si cambia `tipo` u `opciones` y la clave es fuente de alguna regla en `ItemDiseno.condicion` de diseños no bloqueados o en `GrupoRequisito.condicion_defecto`, validar esas reglas con `condiciones.validar_condicion` contra el tipo/opciones nuevos y rechazar con la lista de convocatorias/grupos afectados. En `asegurar_coherencia`, aplicar `solo_lo_nuevo` también a los errores de `validar_coherencia` para que lo preexistente no bloquee ediciones ajenas.
- **Lo que NO hay que hacer:** no reescribir automáticamente las condiciones guardadas; no tocar las fotos de casos ya respondidos (D3).
- **Tests a agregar:** cambiar el tipo de una fuente usada → error con nombre de convocatoria; sacar una opción usada en `es` → error; diseño con condición rota preexistente → mover otro ítem no da 400.
- **Verificación:** mutación sobre el chequeo nuevo; repetir el escenario en el constructor.
- **Regla para no repetirlo:** **control mecánico** · test de contrato en `programas/tests` · «Todo campo del catálogo que alimenta `condiciones` tiene test de “cambio con dependientes → rechazo”.»

---

### B-ERR-15 · Los adjuntos que sincronizan después del cierre se rechazan si el caso no trae `capturado_en`
**Severidad:** MEDIA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** relacionado con G1-04 / G1-07 · **Ola:** 1 · **Esfuerzo:** S
- **ID de la pasada 1:** B6-ERR-01
- **Ubicación:** `programas/api/views.py:865` (`FormularioViewSet.adjuntos`), `programas/api/views.py:122-128` (`_captura_habilitada`)
- **Escenario:**
  1. Un agente carga un caso offline. Lo carga desde la app vieja o en línea, así que el caso queda sin `capturado_en`.
  2. Las fotos y documentos sincronizan después de `fecha_hasta`.
  3. `_captura_habilitada(rel, None)` evalúa `habilitado_en(now)` → 400 `FUERA_DE_PERIODO`.
  4. La app (Chaco-mobile@a66c2d3) trata cualquier 4xx como `FAILED_PERMANENT`.
  5. Resultado: el adjunto se pierde y `finalizar` queda bloqueado para siempre.
  - La asimetría: un caso que sí trae `capturado_en` acepta adjuntos sin límite de tiempo.
- **Causa raíz:** cuando `capturado_en` es `None`, el chequeo usa la hora actual. Debería usar la hora en que el caso se creó.
- **Solución:** en `adjuntos`, pasar `formulario.capturado_en or formulario.creado`. Así un caso creado dentro del período conserva su ventana. No cambia el contrato: mismo código y mismo mensaje para los casos que de verdad están fuera.
- **Lo que NO hay que hacer:** quitar el chequeo de período de `adjuntos`. Eso reabre la carga indefinida sobre relevamientos cerrados.
- **Tests a agregar:** `programas/tests/test_api_campo.py::AdjuntosFueraDePeriodoTest.test_adjunto_tardio_de_caso_sin_capturado_en_creado_en_periodo_se_acepta`
- **Verificación:** con el test de arriba en verde y `fecha_hasta` en el pasado, el POST de adjunto de un caso creado en período da 201.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/` (ERR) · «Toda guarda temporal de la API de campo evalúa la hora de la captura (`capturado_en`, o `creado` como respaldo), nunca `now()`: la sincronización llega tarde por diseño y un 4xx es permanente en la app.»

---

### B-PERF-02 · El CSV de lista de espera carga y decodifica los JSON pesados de cada caso
**Severidad:** MEDIA · **Estado:** PLAUSIBLE · **Eje:** PERF · **Origen:** Origen oct.: PERF-11 (abierto, ⏸️ diferido por el PM el 09-oct: la foto `definicion` en cada caso); (mismo patrón que el ya corregido en `convocatoria_export_beneficiarios`, comentario de `relevamientos.py:525-527`) · **Ola:** 5 · **Esfuerzo:** S
- **Relación con PERF-11 (octubre, ⏸️ diferida por el PM el 09-oct):** esta ficha se queda en su ola; si PERF-11 (la foto `definicion` en cada caso) se retoma, la absorbe.
- **ID de la pasada 1:** B1-PERF-01
- **Ubicación:** `programas/views/relevamientos.py:629-642` (`convocatoria_export_lista_espera`).
- **Escenario:** convocatoria con N entradas activas en `ListaEspera` (el cupo del segmento se llenó y los casos aprobables
  quedan en espera: con el link público de 20.000 casos y un cupo de pocos miles, N llega a miles). El export trae, por cada
  entrada, la fila **entera** de `Formulario` (solo difiere `formulario__data`): `definicion` (~5-7 KB, PERF-11),
  `respuestas`, `datos_siis` y `datos_identificacion`, más la fila entera de `Ciudadano` y de `Segmento`. Django hace un
  `json.loads` por cada JSONField de cada fila y el queryset se materializa entero (`for entrada in entradas`, sin
  `iterator()`): con 5.000 entradas son ~35 MB de JSON por la red y ~20.000 `json.loads`, todo vivo en memoria a la vez
  (el JSON parseado ocupa varias veces su texto en dicts de Python). El CSV escribe 5 columnas.
- **Causa raíz:** el `defer("formulario__data")` es anterior a que el caso cargara `definicion`, `respuestas` y
  `datos_siis`; el export hermano de beneficiarios ya se pasó a `values_list` por exactamente esto (907 ms -> 106 ms
  medidos sobre 4.827 filas, solo por `respuestas`).
- **Crece con:** entradas activas de lista de espera de la convocatoria. 1 consulta; por fila ~7-10 KB transferidos y 4
  `json.loads`.
- **Solución (misma salida, byte a byte):** proyectar con `values_list` solo lo que el CSV escribe e iterar por lotes:
  ```python
  filas = (
      sin_formularios_publicos_si_no_puede(ListaEspera.objects.filter(...), ..., prefijo="formulario__")
      .order_by("posicion")
      .values_list("posicion", "formulario__ciudadano_id", "formulario__ciudadano__nombre",
                   "formulario__ciudadano__apellido", "formulario__ciudadano__dni",
                   "formulario__datos_identificacion", "segmento__nombre", "fecha_ingreso")
  )
  for posicion, cid, nombre, apellido, dni, ident, segmento, fecha in filas.iterator(chunk_size=2000):
      ...
  ```
  `nombre_completo` es `f"{nombre} {apellido}"` (`legajos/models/base.py:265-267`): se arma igual en la vista.
- **Lo que NO hay que hacer:** pasarlo a `StreamingHttpResponse` sin tocar la proyección (lo caro es el JSON, no el buffer
  del CSV); sumar campos al `defer` de a uno (el próximo JSONField del modelo vuelve a entrar solo).
- **Tests a agregar:** `programas/tests/test_becas_revision.py::ExportListaEsperaTests.test_no_lee_los_json_del_caso`
  (`CaptureQueriesContext`: el SQL no contiene `definicion`, `respuestas` ni `datos_siis`) y
  `ExportListaEsperaTests.test_mismo_csv_con_y_sin_ciudadano` (fila con ciudadano y fila offline, contra el CSV actual).
- **Verificación:** banco `scripts/perf_mysql/`: el seed no crea `ListaEspera`; sembrar 5.000 entradas activas sobre la
  convocatoria del relevamiento público (como `escenarios_borde.py` hace con los 400 `BAJA`) y sumar a `_extra_targets()`
  de `bench_mysql.py` la ruta `/becas/convocatorias/<conv>/export/lista-espera/`; medir frío/caliente antes y después y
  el pico de memoria con `tracemalloc`. Si con 5.000 entradas pasa de ~2 s o de ~200 MB, sube a ALTA.
- **Regla para no repetirlo:** **control mecánico** · `programas/tests/` (ratchet) · un test que recorra las vistas de
  export de `programas/views/` (`*_export_*`, `reporte_exportar`) con `CaptureQueriesContext` y falle si algún `SELECT`
  sobre `programas_formulario` proyecta `definicion`, `respuestas`, `data` o `datos_siis` fuera de una lista explícita de
  exports que sí los usan; mensaje: «el export trae los JSON del caso: proyectá con values_list».

---

### B-PERF-03 · El embudo cuenta la lista de espera con un DISTINCT sobre las 37 columnas del caso, JSON incluidos
**Severidad:** MEDIA · **Estado:** PLAUSIBLE (mecanismo verificado por lectura; sin medir: la pasada 2 lo mide en el banco) · **Eje:** PERF · **Origen:** Origen oct.: PERF-11 (abierto, ⏸️ diferido por el PM el 09-oct); (el Cambio 92 midió el embudo en 146 ms, pero el banco no siembra `ListaEspera`) · **Ola:** 4 · **Esfuerzo:** S
- **Relación con PERF-11 (octubre, ⏸️ diferida por el PM el 09-oct):** esta ficha se queda en su ola; si PERF-11 (la foto `definicion` en cada caso) se retoma, la absorbe.
- **ID de la pasada 1:** B2-PERF-01
- **Ubicación:** `programas/services/reportes_becas.py:383` (`qs.filter(lista_espera__promovido=False).distinct().count()`); rutas `/becas/reportes/embudo/` y su export.
- **Escenario:** convocatoria con cupo lleno y miles de casos en lista de espera (p. ej. 5.000 de los 20.000) → la
  pantalla y el export del embudo ejecutan
  `SELECT COUNT(*) FROM (SELECT DISTINCT formulario.id, …, data, respuestas, definicion, datos_identificacion, datos_siis, … FROM programas_formulario JOIN programas_relevamiento JOIN programas_listaespera WHERE …) subquery`.
  En MariaDB un DISTINCT con columnas LONGTEXT (los JSON) va a una tabla temporal en disco (Aria) y obliga a leer
  las páginas externas de `definicion` (~5-7 KB por caso, PERF-11) de cada fila: ~13 KB por fila en espera
  movidos por una temporal, para devolver un número.
- **Evidencia:** SQL generado con `.venv312` (Django 5.2.17) sobre el mismo queryset:
  `SELECT COUNT(*) FROM (SELECT DISTINCT "programas_formulario"."id" AS "col1", … "data" AS "col31", "respuestas" AS "col32", "definicion" AS "col33", … "datos_siis" AS "col36", "created_by_id" AS "col37" FROM "programas_formulario" INNER JOIN "programas_relevamiento" … INNER JOIN "programas_listaespera" … WHERE (… "convocatoria_id" IN (SELECT U0."id" FROM "programas_convocatoria" U0 …) AND NOT "programas_listaespera"."promovido")) subquery`.
  `django/db/models/sql/query.py:511-534` (`get_aggregation`): con `distinct` la consulta interna conserva el SELECT
  por defecto (todas las columnas). `escalar_bench.py` no crea `ListaEspera` (grep sin resultados): los 146 ms del
  Cambio 92 se midieron con esta consulta vacía.
- **Crece con:** casos en lista de espera del recorte (filas de la temporal) × ancho de la fila (JSON).
- **Causa raíz:** `ListaEspera.formulario` es FK (un caso puede tener varias filas), así que el join necesita
  `distinct()`, y `.count()` sobre un queryset `distinct()` de modelo hace el DISTINCT de la fila entera.
- **Solución (mismo número):** contar ids, no filas:
  `qs.filter(lista_espera__promovido=False).values("pk").distinct().count()` (→ `SELECT COUNT(*) FROM (SELECT DISTINCT id …)`),
  o el patrón del dashboard (`dashboard_becas.py:595`):
  `ListaEspera.objects.filter(formulario__in=qs.values("pk"), promovido=False).values("formulario_id").distinct().count()`.
- **Lo que NO hay que hacer:** sacar el `distinct()` (duplica los casos con dos filas de espera no promovidas).
- **Tests a agregar:** `programas/tests/test_reportes_becas.py::EmbudoTests.test_lista_espera_no_hace_distinct_de_filas_anchas`
  (capturar las consultas de `reporte_embudo` y afirmar que ninguna tiene DISTINCT junto con `definicion`) y
  `…test_lista_espera_cuenta_una_vez_el_caso_con_dos_filas`.
- **Verificación:** banco MariaDB: sembrar 5.000 `ListaEspera(promovido=False)` sobre casos del relevamiento público y
  correr `bench_mysql.py --solo reporte_embudo,reporte_embudo_xlsx` antes y después; `EXPLAIN ANALYZE` de la consulta
  (antes: `Using temporary` con la fila ancha).
- **Regla para no repetirlo:** **control mecánico** · test en `programas/tests/` que recorre las rutas de reportes y
  dashboard capturando SQL y falla si una consulta tiene `SELECT DISTINCT` y alguna de `"definicion"`, `"respuestas"`,
  `"data"`, `"datos_siis"`, con el mensaje «`.distinct().count()` sobre un modelo ancho: contá `.values("pk").distinct()`».
  Y una línea en `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas activas: «`.distinct().count()` sobre `Formulario`».

---

### B-PERF-04 · Distribución de un campo propio condicionado: una fila y una corrida del motor de condiciones por caso cuando la condición mira un campo libre
**Severidad:** MEDIA · **Estado:** PLAUSIBLE · **Eje:** PERF · **Origen:** — · **Ola:** 4 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B2-PERF-02
- **Ubicación:** `programas/services/dashboard_becas.py:1067-1084` (GROUP BY por la respuesta **y** por cada fuente de
  la condición), `:1089-1100` (`_la_condicion_la_oculta`: `condiciones.aplicar` sobre el plan entero por fila),
  `:890-901` (`plan` = diseño completo); lo consumen `programa_dashboard_datos` (`views/dashboard_becas.py:110`) y el
  export (`:158`).
- **Escenario:** un selector propio («¿Quién es tu tutor?») visible solo si «Fecha de nacimiento → edad menor a 18»
  (operadores `edad_*` de DATE), o si «Nombre de la escuela está completo» (STRING solo admite vacío/completo), o con
  INT `gt/lt`. El docstring (`:1062-1066`) supone «una fila por combinación distinta (no una por caso)», pero con una
  fuente de alta cardinalidad (fechas, textos, números) el GROUP BY sobre los `JSON_EXTRACT` devuelve del orden de
  una fila por caso: hasta 20.000 filas, cada una con k+1 valores JSON decodificados en Python
  (`output_field=JSONField`) y un `condiciones.aplicar` que recorre los 40-80 ítems del diseño. Es el patrón del 500
  histórico (decodificar JSON en Python sobre miles de filas), que vuelve a entrar por las condiciones.
- **Evidencia:** lectura. `programas/services/condiciones.py:43-51` (`OPERADORES_POR_TIPO`: DATE, INT y STRING pueden ser
  fuente); `_claves_que_condicionan` (`dashboard_becas.py:827-851`) suma además las fuentes del grupo padre y,
  transitivamente, las de cada fuente. `escalar_bench.py` siembra preguntas generales (`--preguntas 12`), no campos
  propios condicionados: el banco no pasa por este camino.
- **Crece con:** casos del recorte × cardinalidad de las fuentes; el costo Python ≈ filas × ítems del plan.
- **Causa raíz:** cada fuente se agrupa por su **valor** aunque la regla solo necesite saber si está vacía, y la
  evaluación no se memoiza por combinación de fuentes (la visibilidad de la pregunta no depende de su propio valor:
  `validar_condicion` exige fuentes anteriores, sin ciclos).
- **Solución (mismo resultado):**
  1. Memoizar `_la_condicion_la_oculta` por la tupla de valores de las fuentes (clave `json.dumps(..., sort_keys=True)`):
     una evaluación por combinación de fuentes, no por par (respuesta, fuentes).
  2. Para una fuente cuyas reglas en el plan son solo `vacio`/`completo`, anotar su **presencia** (expresión SQL con
     la misma semántica que `condiciones.esta_vacio`) en vez del valor: esa fuente pasa a tener cardinalidad 2.
     DATE e INT con operadores de comparación siguen agrupando por valor.
- **Lo que NO hay que hacer:** evaluar caso por caso trayendo `respuestas` o la foto (el propio docstring lo descarta
  por el read_timeout), ni ignorar la condición (cambia la base de RN-15).
- **Tests a agregar:** `programas/tests/test_dashboard_becas.py::DistribucionCondicionadaTests.test_fuente_fecha_no_evalua_por_caso`
  (N casos con fechas distintas: `condiciones.aplicar` se llama como mucho una vez por combinación de fuentes, contado
  con `mock.patch`) y `…test_fuente_vacio_completo_da_la_misma_distribucion`.
- **Verificación:** banco MariaDB: diseño en la convocatoria del relevamiento público con un selector `cp-` condicionado
  a `edad_menor` sobre la fecha de nacimiento; `perfil_ruta.py "/becas/config/programas/<p>/dashboard/datos/?periodo=todo&pregunta=cp-…" 1`
  (filas que devuelve la consulta agrupada y segundos de Python en `condiciones.aplicar`), antes y después.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` §Consultas · «Un GROUP BY sobre valores
  JSON solo es barato si la cardinalidad es chica: agrupar por un texto libre, una fecha o un número devuelve una fila
  por caso. Proyectar al dato que la regla necesita (presencia, rango) antes de agrupar».

---

### B-PERF-05 · Export del dashboard: una pasada sobre todo el recorte por cada campo propio de todas las convocatorias del programa, aunque no estén en el recorte
**Severidad:** MEDIA · **Estado:** PLAUSIBLE · **Eje:** PERF · **Origen:** G1b-11 (resuelto con caché; esto queda en frío) · **Ola:** 4 · **Esfuerzo:** S
- **ID de la pasada 1:** B2-PERF-03
- **Ubicación:** `programas/views/dashboard_becas.py:156-160` (`distribuciones_cacheadas(..., catalogo=form.preguntas)`),
  `programas/services/dashboard_becas.py:1158-1161` y `:1060-1085` (una consulta `JSON_EXTRACT … GROUP BY` por pregunta),
  `:854-904` (`_preguntas_propias` suma los `cp-` de todas las convocatorias visibles del programa, sin mirar el recorte).
- **Escenario:** programa con 10 convocatorias históricas, cada una con 5 selectores propios; el usuario exporta el XLSX
  filtrando una convocatoria (o el CSV `bloque=respuestas`). Catálogo = 12 generales + 50 propios → 62 consultas, cada
  una recorre el recorte entero (`relevamiento_id IN (…)`) leyendo `respuestas`. G1b-11 midió 12 preguntas = 2,5 s de
  SQL con 20.000 casos en `mariadb:10.11` (~200 ms cada una): 62 son ~12 s en un request, y el número crece con cada
  convocatoria nueva. Las propias de las otras convocatorias devuelven siempre base 0 (la clave `cp-` + uuid4 es única
  por diseño, `dashboard_becas.py:863-865`): esas pasadas no aportan nada. Ninguna consulta pasa los 10 s sola; el
  riesgo es el request entero contra los 60 s de nginx a medida que se acumulan convocatorias.
- **Evidencia:** lectura; `escalar_bench.py` no siembra diseños con campos propios, así que `dashboard_becas_export_xlsx`
  del banco mide solo las 12 generales.
- **Crece con:** (convocatorias del programa con campos propios × selectores por diseño) × casos del recorte.
- **Causa raíz:** el catálogo no depende del recorte y cada pregunta se resuelve con un scan propio.
- **Solución (misma salida):** guardar en `Pregunta` la convocatoria del campo propio (`convocatoria_id`, de
  `item.diseno.convocatoria_id`); en `distribuciones_respuestas`, si esa convocatoria no está en
  `alcance.convocatoria_ids`, devolver `_armar_distribucion(pregunta, Counter(), 0)` sin consultar: es exactamente lo
  que sale hoy cuando la consulta no trae filas. Opcional y también idéntico: para la que sí está, acotar el queryset
  a los relevamientos de esa convocatoria (`alcance.relevamientos` ya trae `convocatoria_id`).
- **Lo que NO hay que hacer:** sacar esas preguntas del catálogo o del export (cambia lo que ve el usuario).
- **Tests a agregar:** `programas/tests/test_dashboard_becas.py::ExportacionTests.test_propios_de_otra_convocatoria_no_consultan`
  (`assertNumQueries` igual con 1 y con 5 convocatorias con propios fuera del recorte, y la hoja «Respuestas» idéntica).
- **Verificación:** banco: K convocatorias del mismo ProgramaSiis con diseño de 5 selectores `cp-` (sin casos) y
  `bench_mysql.py --solo dashboard_becas_export_xlsx` en frío: hoy consultas ≈ base + 12 + 5K y SQL ≈ K × 1 s; después,
  base + 12.
- **Regla para no repetirlo:** **control mecánico** · `scripts/perf_budgets.json` + `scripts/perf_audit.py::build_targets` ·
  sembrar en `seed_perf` al menos dos convocatorias con campos propios y presupuestar `dashboard_becas_export_xlsx`: si
  el conteo crece con convocatorias fuera del recorte, el presupuesto se rompe.

---

### B-PERF-06 · La corrida de `procesar_casos_siis` y el masivo de la pantalla retienen en memoria hasta `--total` casos con sus JSON
**Severidad:** MEDIA · **Estado:** PLAUSIBLE · **Eje:** PERF · **Origen:** relacionado con PERF-06/Cambio 106 (la consulta ya va por lotes; la retención en memoria no); Origen oct.: PERF-11 (abierto, ⏸️ diferido por el PM el 09-oct) para el peso del JSON retenido · **Hallado por 2 revisores** (B3-PERF-01 + B4-ERR-03); origen de la absorbida: B4-ERR-03: — (PERF-01 midió consultas, no memoria) · **Ola:** 3 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B3-PERF-01 + B4-ERR-03 (**hallado por 2 revisores**)
- **Ubicación:** `programas/management/commands/procesar_casos_siis.py:433` (`casos = list(proceso_masivo.hidratar_por_lotes(...))`), `:418-420` (`elegir_completos` devuelve los elegidos hidratados), opción `--total` sin máximo. Mismo patrón en `programas/services/proceso_masivo.py:1098-1105` (`correr`, hilo del pod web, tope `TOTAL_MAXIMO = 5000` en `views/proceso_masivo.py:33`): fuera de la tajada, citado para deduplicar.
- **Escenario:** un operador corre `procesar_casos_siis --aplicar --total 7000`. `hidratar_por_lotes` trae de a 200 (cada consulta entra en el read_timeout), pero el `list(...)` acumula los 7.000 Formulario con data, respuestas, definicion y datos_siis decodificados antes de procesar el primero. Es lo que documenta `correr_alta_siis.py:71-75`: con 7.434 de una el pod murió con exit 137 el 01/10/2026. El tope de 500 (`TANDA`) vive solo en el orquestador; el comando a mano no tiene ninguno. Pasa también en el ensayo: la rama sin `--solo-completos` hidrata todo antes del `if not aplicar` (`:433` contra `:458`).
- **Causa raíz:** el comando separa elegir de procesar con una lista de objetos completos; `--lote` parte el procesamiento, no la retención.
- **Con qué crece:** lineal con `--total`. Consultas: no cambian (N/200). RSS: unos 27 KB de JSON por caso, varias veces eso como dicts de Python; del orden de 0,5 a 1,5 GB con 5.000 a 7.000 casos.
- **Solución (mismo resultado):** quedarse con ids e hidratar por lote dentro del bucle, como ya hace `enviar_casos_siis.py:246`.
  - Rama sin `--solo-completos`: `ids = proceso_masivo.ids_de(consulta, limite=total)`; el resumen por estado sale de `values_list("estado", flat=True)` por tramos de ids; en el bucle, `lote = proceso_masivo.hidratar(lote_ids)`.
  - Rama `--solo-completos`: `elegir_completos` (o el comando) acumula `caso.pk` y se rehidrata por lote al procesar. El caso se relee segundos después; `_reservar` ya relee el estado bajo lock, así que el desenlace no cambia.
  - Los mensajes de log quedan iguales.
- **Lo que NO hay que hacer:** ponerle un máximo a `--total` (cambia el contrato y no arregla el masivo); diferir los JSON en `hidratar` (`armar_payload` los lee: se vuelve N+1).
- **Tests a agregar:** `programas/tests/test_circuito_siis_performance.py::ProcesarCasosSiisMemoriaTests.test_no_retiene_mas_de_un_lote_hidratado` (parchear `proceso_masivo.hidratar`, contar objetos vivos con weakref y afirmar que nunca hay más que `--lote`, con `--total 30 --lote 5`).
- **Verificación / medición en el banco:** banco de 20.000 casos (`scripts/perf_mysql/README.md`, pasos 1-4). Correr el ensayo `manage.py procesar_casos_siis --total N --sin-filtro-materias` con N = 500, 2000 y 5000 y tomar el pico de memoria del proceso (PowerShell: `PeakWorkingSet64` de `Get-Process`, o `tracemalloc.get_traced_memory()` al final de `handle` en una copia local). Hoy crece lineal con N; después tiene que quedar plano en el tamaño de un lote.
- **Regla para no repetirlo:** skill · `.claude/skills/auditoria/rubricas/rendimiento.md`, Búsquedas activas · «Una lista de modelos hidratados que se arma antes del bucle de procesamiento (`list(hidratar_por_lotes(...))`): el lote parte la consulta, no la memoria. En comandos por lotes se guardan ids y se hidrata por lote dentro del bucle (patrón de `enviar_casos_siis`).»

#### Aporte del segundo revisor (B4-ERR-03: La corrida masiva retiene en memoria hasta 5.000 casos completos, con sus JSON, durante toda la hora)
_Pasada 1: severidad MEDIA · estado PLAUSIBLE · esfuerzo S-M._

- **Ubicación:** `programas/services/proceso_masivo.py:1098-1101` (`casos, _ = elegir_completos(hidratar_por_lotes(...))`),
  `:789-804` (`elegidos.append(caso)` guarda el objeto entero), `:757-760` (`hidratar` sin `defer` en este camino:
  `definicion`, `data`, `respuestas`, `datos_siis`), `programas/views/proceso_masivo.py:33` (`TOTAL_MAXIMO = 5000`).
  El propio módulo mide la fila: «la foto del formulario son 27 KB por caso» (`:719`) y ~7 KB más de JSON (`:767-769`).
- **Escenario:** «Procesar» con 5.000. La selección termina con 5.000 `Formulario` hidratados y sus JSON ya
  deserializados a `dict` (varias veces el tamaño en bytes) vivos en la lista `casos` hasta que la corrida termina. El
  hilo corre **dentro del proceso web** (`lanzar` → `threading.Thread`), así que el pico de memoria es del pod que
  atiende requests: si pasa el límite del contenedor, el OOM mata el pod entero y la corrida con él (queda
  «interrumpida» y la pantalla cae para todos los usuarios de ese pod).
- **Causa raíz:** `elegir_completos` ya hidrata para decidir (necesita `armar_payload`) y devuelve los objetos en vez
  de los ids; la hidratación por lotes de PERF-01 acota la **lectura**, pero la lista de elegidos vuelve a juntarlo todo.
- **Solución:** que `correr` se quede con `[caso.pk for caso in casos]` (o que `elegir_completos` acepte un flag para
  devolver ids) y, en el bucle por `_lotes`, rehidrate cada grupo de `LOTE` con `hidratar(ids_del_grupo)`. Mismos casos,
  mismo orden, mismo procesamiento; el caso además llega con el estado del momento en que le toca (SIIS-04 ya relee bajo
  candado, así que no cambia ninguna decisión).
- **Lo que NO hay que hacer:** no diferir `definicion`/`data` en `hidratar` para este camino: `armar_payload` los lee
  y cada caso los volvería a pedir de a uno (`:741-747`).
- **Tests a agregar:** `programas/tests/test_proceso_masivo.py::CorridaMemoriaTests.test_correr_no_retiene_los_casos_elegidos`
  (mock de `hidratar` que cuenta llamadas: una por lote de proceso además de la selección; `procesar_caso` recibe casos
  del lote actual).
- **Verificación:** banco MySQL de 20.000 casos, corrida de 5.000 con `tracemalloc`/RSS antes y después: el pico deja de
  crecer con `total_pedido`.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/` (rendimiento) · «Un proceso largo que
  corre en un hilo del pod web guarda ids entre fases, no instancias de `Formulario`: cada una arrastra ~35 KB de JSON».

---

### B-PERF-07 · `enviar_casos_siis` y `reenviar_siis_pendientes` eligen candidatos en una sola consulta sin rangos de pk (el patrón que el Cambio 106 sacó de `ids_de`)
**Severidad:** MEDIA · **Estado:** PLAUSIBLE · **Eje:** PERF · **Origen:** — · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** B3-PERF-02
- **Ubicación:** `programas/management/commands/reenviar_siis_pendientes.py:315-336` (`_casos`: `select_related` de la cadena hasta programa, todas las columnas de `programas_formulario` con sus JSON, `list(casos[:limite])`); `programas/management/commands/enviar_casos_siis.py:135-179` (`_casos`: `values_list` sin rangos y `list(casos)` en :179).
- **Escenario:**
  - `reenviar_siis_pendientes` en el caso normal (pocos o ningún caso con último envío ERROR): `WHERE estado = APROBADO AND (subconsulta último envío) = ERROR AND NOT EXISTS(vigente) AND NOT EXISTS(traza) ... ORDER BY id LIMIT 200`. Como casi ninguna fila cumple, el motor recorre todos los APROBADO en orden de pk evaluando las subconsultas correlacionadas por fila, y lee cada fila entera con sus JSON (están en el SELECT). Con 9.000 a 20.000 aprobados son de 130 a 283 MB en una consulta: el síntoma que `proceso_masivo.ids_de` documenta (`proceso_masivo.py:717-724`, no entra en el read_timeout de 10 s, Lost connection). El comando muere justo después de una caída del legacy, que es cuando se lo usa.
  - `enviar_casos_siis`: trae solo pk, estado y programa_id, pero en una consulta sobre todos los candidatos, con dos subconsultas correlacionadas por fila, joins hasta programa y ciudadano, y un IN de unos 46.000 literales (`dnis_aprobados_materias`). El docstring mide 30 ms en el banco caliente; `ids_de` existe porque esa medición en caliente no predice ECOM. Riesgo menor (no lee JSON), mismo mecanismo.
- **Causa raíz:** los otros caminos de selección del circuito (`procesar_casos_siis`, `validar_casos_siis`, `correr_alta_siis`) pasan por `ids_de` (rangos de pk de 2.000) + `hidratar`; estos dos quedaron con la forma anterior.
- **Con qué crece:** casos del alcance (hasta 20.000 filas examinadas y 2 subconsultas por fila); en `reenviar`, además, con el tamaño de la fila.
- **Solución (mismo conjunto, mismo orden, mismo límite):**
  - `reenviar_siis_pendientes._casos`: `ids = proceso_masivo.ids_de(casos_sin_select_related, limite=limite)` y devolver `proceso_masivo.hidratar(ids)` (trae las mismas relaciones, ordenado por pk).
  - `enviar_casos_siis._casos`: el mismo queryset por `ids_de(casos, limite=options["limite"] or None)`; estado y programa_id del resumen por tramos de esos ids con `values_list`. El resto no cambia.
- **Lo que NO hay que hacer:** cambiar el IN de DNI por un JOIN contra `aprobados_materias` (otra intercalación: Illegal mix of collations, `proceso_masivo.py:112-114`); agregar `distinct()` (materializa).
- **Tests a agregar:** `programas/tests/test_circuito_siis_performance.py::SeleccionPorRangosTests.test_reenviar_no_lee_los_json_al_elegir` y `test_enviar_casos_elige_por_rangos_de_pk` (CaptureQueriesContext: toda consulta de selección sobre `programas_formulario` con subconsulta correlacionada lleva predicado de rango de id y LIMIT; ninguna trae `definicion`).
- **Verificación / medición en el banco:** banco MariaDB 10.11 de 20.000 casos (README pasos 1-4), 9.000 marcados APROBADO sin envíos, contenedor reiniciado (buffer pool frío) y sin `DB_READ_TIMEOUT`. Cronometrar el ensayo de `reenviar_siis_pendientes` y de `enviar_casos_siis --sin-filtro-materias`. Además, imprimir el SQL de `_casos` y correr `ANALYZE FORMAT=JSON <sql>` con `docker exec chaco-mariadb-bench mariadb ... chaco_perf_ci`: mirar `r_rows` de `programas_formulario` y `r_loops` de las subconsultas. Hoy: r_rows cerca de todos los APROBADO; después: 2.000 como máximo por consulta.
- **Regla para no repetirlo:** control mecánico · `programas/tests/test_circuito_siis_performance.py` · test que corre en ensayo cada comando derivado de `ComandoSiisBase` con 30 casos y falla si una consulta de selección sobre `programas_formulario` con subconsulta correlacionada no tiene rango de id y LIMIT, o si trae `definicion`. Mensaje: «La selección de candidatos de un comando SIIS va por `proceso_masivo.ids_de` + `hidratar` (Cambio 106).»

---

### B-PERF-08 · Techo de rendimiento de la cola única del link público, nunca medido
**Severidad:** MEDIA · **Estado:** PLAUSIBLE (mecanismo confirmado por lectura; tiempo de retención por envío sin medir) · **Eje:** PERF · **Origen:** Cambio 91 (`docs/internal/requerimientos.md:10326+`): la cola del lock único se aceptó como diseño y «adentro del lock quedó solo lo indexado», pero nunca se midió con N envíos concurrentes. No coincide con PERF-12 (mide solo el count). · **Ola:** 1 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B6-PERF-02
- **Ubicación:** `programas/services/inscripcion_publica.py:113-132` (atomic + FOR UPDATE del Relevamiento en :114), `:135-209` (`_insertar_formulario`: count :155, FOR UPDATE Convocatoria :159, `dni_en_convocatoria` :160, `esta_habilitado` :162, `Formulario.objects.create` :176); `programas/models/__init__.py:4164-4181` (`Formulario.save`: atomic anidado que vuelve a lockear el Relevamiento + Max(numero)).
- **Escenario:** pico de difusión del link. Todos los envíos del mismo relevamiento se serializan en una fila. Por envío, dentro del lock: ~8–10 idas y vueltas + INSERT con la foto `definicion` (6–27 KB de JSON). Si la retención es 20–30 ms, el techo es ~35–50 envíos/s por relevamiento; una ráfaga de 1.000 simultáneos deja a los últimos >10 s en cola → 2013 → 500, aunque cada consulta sea por índice.
- **Crece con:** envíos simultáneos por relevamiento (lineal en la espera del último) × latencia app↔base (cada ida y vuelta se paga con el lock tomado) × tamaño de la definición.
- **Causa raíz:** cupo y numeración exigen exclusión por relevamiento (correcto); lo que no está acotado es cuánto dura cada turno ni cuántos esperan.
- **Solución (preserva la lógica):** primero medir. Si el p99 de espera con la ráfaga objetivo pasa de ~5 s: (a) armar la foto `definicion` y el dict a insertar antes del atomic; (b) evitar el segundo lock + Max de `Formulario.save` cuando el llamador ya tiene el Relevamiento tomado (pasar el número calculado); (c) innodb_lock_wait_timeout de sesión por debajo de read_timeout en ese atomic, para devolver un error controlado (pedir reintento en unos segundos) en lugar de un 500 con el hilo colgado. Ninguna cambia la regla de cupo ni la numeración; el texto del error controlado es DECISIÓN CLIENTE (por defecto: el mensaje de error genérico del paso 2).
- **Lo que NO hay que hacer:** quitar el lock del Relevamiento (rompe cupo y numero único); contador de cupo desnormalizado sin lock; cola asíncrona sin acuerdo (cambia la experiencia).
- **Tests a agregar:** test con tag performance y presupuesto de consultas **dentro** de la sección crítica de `crear_formulario_publico` (entre el FOR UPDATE y el commit).
- **Verificación / medición:** script nuevo en `scripts/perf_mysql/` que lanza N hilos (N = 50, 200, 1000) con `crear_formulario_publico` sobre el mismo relevamiento con cupo libre; medir retención por envío (FOR UPDATE concedido → commit), p50/p99 de espera y cantidad de 2013 con read_timeout=10. Complementar con `performance_schema.events_transactions_history`.
- **Regla para no repetirlo:** control mecánico · test con tag performance en `programas/tests/` · «Presupuesto de consultas dentro de la sección crítica de `crear_formulario_publico` y del alta POST de la API; subirlo exige justificar en el PR la retención medida en el banco.»

---

### B-LIM-07 · `views/revision.py` pasa de 1.000 líneas (1.385) y sigue creciendo
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** RED tabla de fragilidad (g) #4 (1.331 líneas en oct; hoy 1.385) · **Ola:** 11 · **Esfuerzo:** M
- **ID de la pasada 1:** B1-LIM-01
- **Ubicación:** `programas/views/revision.py:1-1385`.
- **Escenario:** cualquier ajuste de perf en la bandeja (L365-553) obliga a abrir un archivo que mezcla bandejas, detalle, SIIS, resolución e identidad; el churn (34 en oct) lo vuelve el archivo con más conflictos del módulo. Un PR de perf sobre `_pagina_hidratada` choca con uno funcional sobre `formulario_aprobar`.
- **Causa raíz:** un único módulo de vistas por «pantalla de revisión» que fue absorbiendo cada acción nueva del caso.
- **Solución:** convertir en paquete `programas/views/revision/` con re-export en `__init__.py` (las URLs no cambian):
  - `bandejas.py`: `RevisionPersonasListView`, `RenaperPendientesListView`, `revision_formularios` y los helpers de paginación/marcas (L115-197, L365-553);
  - `caso.py`: `formulario_detalle` y helpers de origen/next (L279-341, L556-709);
  - `siis.py`: `formulario_validar_sis`, `formulario_enviar_siis`, `formulario_datos_siis`, vistas JSON de localidades/funciones (L712-893);
  - `resolucion.py`: aprobar, rechazar, resolver duplicado, reenviar aviso, `relevamiento_terminar` (L739-776, L937-1171, L1351-1385);
  - `identidad.py`: género, revalidar RENAPER, validar padrón, forzar identidad (L896-934, L1174-1348).
  Constantes (`MENSAJE_PROGRAMA_SIN_SIIS` L219, `ESTADOS_TERMINABLES` L1357) suben al módulo que las usa. Movimiento puro: ninguna línea de lógica cambia.
- **Lo que NO hay que hacer:** partir y a la vez cambiar lógica; renombrar nombres de URL; romper los `mock.patch("programas.views.revision.X")` de los tests (re-exportar o actualizar el target en el mismo diff).
- **Tests a agregar:** ninguno funcional; el contrato es la suite existente (`test_becas_revision*`, snapshots, `ConsultasDetalleTests`) en verde sin tocar valores.
- **Verificación:** `manage.py test programas.tests.test_becas_revision programas.tests.test_becas_revision_detalle_html programas.tests.test_becas_revision_listas`; `wc -l` de cada módulo nuevo < 400.
- **Regla para no repetirlo:** control mecánico · `programas/tests/test_arquitectura.py` · ratchet de tamaño: ningún `.py` de `programas/views/` supera 1.000 líneas salvo una lista congelada que solo puede achicarse.

---

### B-LIM-08 · `views/relevamientos.py` pasa de 1.000 líneas (1.213)
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** RED tabla de fragilidad (g) #4 (1.056 en oct) · **Ola:** 11 · **Esfuerzo:** M
- **ID de la pasada 1:** B1-LIM-02
- **Ubicación:** `programas/views/relevamientos.py:1-1213`.
- **Escenario:** convocatorias, exportes CSV, relevamientos, transiciones y padrón conviven; optimizar un export obliga a cargar 1.200 líneas de contexto y a reconciliar con cambios de padrón.
- **Causa raíz:** el módulo creció por agregado (+157 líneas desde oct) sin corte por responsabilidad.
- **Solución:** paquete `programas/views/relevamientos/` con re-export:
  - `convocatorias.py`: list/detail/create/update/toggle/reactivar (L127-514);
  - `exportes.py`: los tres CSV (L517-663), con el armado de filas bajado a `services/exportacion_reportes` (ver B-LIM-09);
  - `relevamientos.py`: list/create/detail (L669-909);
  - `transiciones.py`: finalizar/reabrir/reasignar/reprogramar/cupo (L912-1015, L1182-1213), delgadas sobre el servicio de B-LIM-02;
  - `padron.py`: L1018-1179.
  Los imports diferidos sin motivo (L1091-1093, L1156, L1172) suben a cabecera. `_convocatorias_qs` (L127-128), wrapper sin valor sobre `convocatorias_listado_qs`, se elimina.
- **Lo que NO hay que hacer:** cambiar el orden de las columnas CSV ni los encabezados; mover el texto de sesión del resumen de padrón a otro idioma/forma.
- **Tests a agregar:** ninguno funcional; si un import diferido protegía un ciclo, el `manage.py check` lo delata.
- **Verificación:** `manage.py test programas.tests.test_becas_relevamientos programas.tests.test_relevamiento_diseno`; `manage.py check`.
- **Regla para no repetirlo:** control mecánico · mismo ratchet de B-LIM-07.

---

### B-LIM-09 · Resolución «persona del caso» (`ciudadano` o `datos_identificacion`) copiada ~15 veces
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 11 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B1-LIM-06
- **Ubicación:** `programas/views/relevamientos.py:544-551` y `:642-650` (exportes CSV); templates `relevamientos/convocatoria_detail.html`, `relevamientos/relevamiento_detail.html:255-262` y `:278` (dos veces en la misma fila), `revision/formulario_list.html`, `revision/personas_list.html`, `revision/_detalle/_identidad.html:10-28`; servicios `avisos_resolucion.py:99`, `inscripcion_publica.py:289`, `reportes_becas.py:476`, `respuestas.py:241`; `api/views.py:117,446`.
- **Escenario:** el día que cambia la regla (p. ej. preferir el DNI validado del ciudadano) hay que editar 15 lugares, y el CSV y la pantalla ya pueden mostrar personas distintas para el mismo caso. Para optimizar los exportes (`only()` de columnas) hay que saber qué campos usa cada copia.
- **Causa raíz:** falta la propiedad canónica en el modelo `Formulario`.
- **Solución:** `Formulario.nombre_mostrado`, `dni_mostrado` (y lo que haga falta) como `@property` en `programas/models/__init__.py`, con la misma precedencia que hoy; reemplazar las copias una a una. En templates el reemplazo debe dar el mismo texto (snapshots lo garantizan).
- **Lo que NO hay que hacer:** unificar precedencias que hoy difieren entre copias sin listarlas antes (si alguna difiere, es un hallazgo aparte, no se arregla de paso); agregar consultas (la propiedad usa solo lo ya cargado).
- **Tests a agregar:** test de la propiedad (con ciudadano, sin ciudadano, sin datos).
- **Verificación:** snapshots del detalle intactos; CSV de convocatoria idéntico byte a byte sobre un fixture.
- **Regla para no repetirlo:** control mecánico · `test_arquitectura.py` · grep de `datos_identificacion.get(` / `datos_identificacion.` en `programas/views` y `templates` con ratchet a 0.

---

### B-LIM-10 · Tres validadores de `next` con reglas distintas
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo (no es el RS-R4-01 refutado: aquel era la duplicación de guardas) · **Ola:** 11 · **Esfuerzo:** S
- **ID de la pasada 1:** B1-LIM-07
- **Ubicación:** `programas/views/revision.py:279-297` (`_next_valido`: host + scheme + `require_https` + prefijo `/becas/`), `programas/views/relevamientos.py:188-201` (`_destino_seguro`: `require_https`), `:820-826` (`RelevamientoCreateView.get_success_url`: sin `require_https`).
- **Escenario:** el mismo `?next=` se acepta en una pantalla y se descarta en otra; quien agrega una vista nueva copia el más cercano, que puede ser el más laxo.
- **Causa raíz:** cada vista escribió su chequeo sobre `url_has_allowed_host_and_scheme`.
- **Solución:** un helper `next_seguro(request, valor, prefijo=None)` en `core/` (o `programas/views/_comun.py`) con `require_https=request.is_secure()`; las tres llaman a él pasando el prefijo cuando hoy lo exigen. Comportamiento idéntico salvo `get_success_url`, cuyo cambio a `require_https` se declara.
- **Lo que NO hay que hacer:** imponer el prefijo `/becas/` a las de relevamientos (cambia destinos válidos hoy).
- **Tests a agregar:** tabla de casos (`//evil`, `http://` en https, relativo válido) contra el helper.
- **Verificación:** tests de redirect existentes en verde.
- **Regla para no repetirlo:** control mecánico · `test_arquitectura.py` · `url_has_allowed_host_and_scheme` solo aparece en el helper.

---

### B-LIM-11 · `selectors/revision.py` construye formularios, evalúa permisos y duplica un contrato de 13 claves
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** RED-54 (cerrado; esto es lo que dejó) · **Ola:** 11 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B1-LIM-09
- **Ubicación:** `programas/selectors/revision.py:229-237` y `:289` (instancia `CiudadanoGeneroRevisionForm`, `ForzarIdentidadForm`, `DatosSiisForm`), `:278` y `:293` (`puede(user, CAP_REVISION_EDITAR)` dos veces), `:260-274` vs `:291-309` (`contexto_siis`: el retorno temprano repite a mano las 13 claves), `:49-115` (mapeo estado SIIS → etiqueta/tono), `:45` (`CAP_REVISION_EDITAR` redefinida para no importar de la vista).
- **Escenario:** agregar una clave a `contexto_siis` y olvidarla en el retorno temprano rompe el template solo para programas sin SIIS (camino poco probado); `ContextoDetalleTests` lo caza solo si cubre ese camino.
- **Causa raíz:** el selector absorbió todo lo que salió de la vista en RED-54, incluido lo que es form y permiso.
- **Solución:** el retorno temprano parte de un dict base común (`base = {...}; if sin_siis: return base`), sin listar las claves dos veces; el permiso se evalúa una vez y se pasa como argumento desde la vista (`puede_editar`), que ya lo calcula; la construcción de forms pasa a la vista o a un `forms_del_detalle(formulario, puede_editar)` en `forms/`. `CAP_REVISION_EDITAR` vive en un módulo de constantes de capacidades de Becas, importado por vista y selector.
- **Lo que NO hay que hacer:** cambiar claves ni valores del contexto; agregar consultas (15 por igualdad).
- **Tests a agregar:** `ContextoDetalleTests` para un programa sin SIIS (mismo set de claves).
- **Verificación:** `ConsultasDetalleTests`, `ContextoDetalleTests`, snapshots en verde.
- **Regla para no repetirlo:** control mecánico · `test_arquitectura.py` · `programas/selectors/**` no importa de `programas.forms` ni llama a `puede(`.

---

### B-LIM-12 · `services/solapas.py`: clase-namespace que mezcla lectura, escritura, presentación y lógica de producto
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** hallazgos/02-siis-becas.md:666 y :702 (abiertos, mencionan `solapas.py`) · **Ola:** 11 · **Esfuerzo:** M
- **ID de la pasada 1:** B1-LIM-10
- **Ubicación:** `programas/services/solapas.py`: `SolapasService` solo con `classmethod`; escritura en `cerrar_inscripcion` L172-187 y `crear_inscripcion_directa`; colores hex `#EF4444`, `#F97316`, `#F59E0B` e íconos; strings mágicos `"ACTIVO"`, `"EN_SEGUIMIENTO"`, `"PENDIENTE"`, `"CERRADO"` en L41, 97, 106, 117, 125, 142, 156, 176, 363, 367; `"Formulario": Formulario` (la clase) en el contexto L356; estado calculado dos veces en `_obtener_solapa_becas` L260-275; imports diferidos L174, 220-225, 261-262, 314-316, 361.
- **Escenario:** el legajo es transversal (lo abre cualquier rol); optimizar su solapa de Becas obliga a tocar un servicio genérico que además decide colores. Un estado renombrado en el modelo no rompe nada en ejecución: devuelve la solapa vacía.
- **Causa raíz:** un servicio de «solapas del legajo» al que cada producto le agregó su rama.
- **Solución:** funciones de módulo en vez de clase; las ramas de producto a `services/solapas_becas.py` / `solapas_dispositivos.py` registradas en un dict; estados desde los `TextChoices` del modelo; colores/íconos a un mapeo de presentación en el template o templatetag; escrituras (`cerrar_inscripcion`, `crear_inscripcion_directa`) a `services/inscripciones.py`; quitar la clase `Formulario` del contexto (pasar los choices que el template usa); imports a cabecera salvo ciclo comprobado.
- **Lo que NO hay que hacer:** cambiar los colores o íconos que se ven (se mueven, no se cambian); cambiar claves que lee el template del legajo.
- **Tests a agregar:** test de la solapa de Becas por estado (activo/seguimiento/pendiente/cerrado) contra el servicio.
- **Verificación:** tests de legajo en verde; render del legajo idéntico.
- **Regla para no repetirlo:** control mecánico · `design_audit.py` ya marca hex en templates; extender a `programas/services/**` (hex `#[0-9A-Fa-f]{6}` en servicios = hallazgo).

---

### B-LIM-13 · `dashboard_becas.py` concentra cinco servicios en 1.780 líneas y sigue creciendo
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — (RED-08 lo listaba con 1.253 líneas en oct-2026, `hallazgos/08-red-de-seguridad.md:2958`) · **Ola:** 10 · **Esfuerzo:** L
- **ID de la pasada 1:** B2-LIM-01
- **Ubicación:** `programas/services/dashboard_becas.py:1-1780`. Bloques: tipos `:102-216`; alcance `:247-312`; métricas `:314-641`; caché y huella `:644-731`; catálogo y distribuciones de respuestas `:734-1165`; bloques de exportación `:1168-1305`; export «respuestas por persona» `:1308-1780`.
- **Escenario:** el archivo pasó de 1.253 líneas (octubre) a 1.780 (+42 %) en ~19 commits desde septiembre. Cualquier cambio del export por persona (PERF-03, G2-01) obliga a abrir y revisar el mismo módulo que las métricas del tablero; `siis_envio.py` importa de acá (ver B-LIM-17). Cinco responsabilidades sin dependencia mutua real: el export por persona (`:1308-1780`, ~470 líneas) no usa `Filtros`, `Alcance` ni la caché.
- **Causa raíz:** cada pedido (Cambio 64, 65, G2-01, PERF-03, G1b-11/12) se resolvió agregando funciones al único módulo «del dashboard», sin un corte por responsabilidad.
- **Solución:** convertir en paquete `programas/services/dashboard_becas/` sin cambiar una línea de lógica:
  - `alcance.py` — `Filtros`, `Alcance`, `resolver_alcance`, `_formularios`, `_huella`, `_aware_start` (~200).
  - `metricas.py` — `Indicadores`, `Datos`, bloques `_serie_semanal`…`_texto_alcance`, `metricas` (~340).
  - `cache.py` — `_cache_get/_set/_delete`, `_clave`, `clave_cache`, `recalculo_permitido`, `metricas_cacheadas`, `distribucion_cacheada`, `distribuciones_cacheadas` (~150).
  - `distribuciones.py` — `Pregunta`, `Distribucion`, `preguntas_graficables`, `_preguntas_propias`, `_planos_del_diseno`, `_claves_que_condicionan`, `_ValorJson`, `_expresion_respuesta`, `distribuciones_respuestas` (~380).
  - `exportacion.py` — `_reporte_resumen`, `bloques_exportacion` (~140).
  - `respuestas_por_persona.py` — `COLUMNAS_FIJAS`, `_COLUMNAS_CASO`, `LOTE_RESPUESTAS`, `CONSULTAS_POR_LOTE`, `formulario_vigente`, `_claves_sin_columna`, `_filas_por_persona`, `_celdas_de_las_respuestas`, `respuestas_por_persona(_en_lotes)` (~480).
  - `__init__.py` re-exporta la API pública que hoy usan vistas, forms y `perf_budgets` (`Filtros`, `preguntas_graficables`, `resolver_alcance`, `metricas_cacheadas`, `distribucion_cacheada`, `distribuciones_cacheadas`, `bloques_exportacion`, `respuestas_por_persona_en_lotes`, `recalculo_permitido`, `clave_cache`, `RECALCULO_MINIMO`, `LOTE_RESPUESTAS`).
  - Los parsers de JSON (`_como_dict`, `_valores_de`, `_opciones_texto`, `respuesta_de`) salen del paquete (B-LIM-17).
- **Lo que NO hay que hacer:** confiar en el re-export para los `patch.object(svc, "LOTE_RESPUESTAS"|"RECALCULO_MINIMO"|"_filas_por_persona")` de `programas/tests/test_dashboard_becas.py:337,386,427,458,545` y el `patch("programas.services.dashboard_becas.metricas")` de `:768`: parchear el nombre re-exportado no cambia el que lee el submódulo. Hay que mover esos patches al submódulo en el mismo PR (por eso `_lotes` lee `LOTE_RESPUESTAS` en cada llamada, `:1467-1475`: que lo siga leyendo de `respuestas_por_persona`). Tampoco mezclar el split con cambios de lógica: un PR solo de movimiento.
- **Tests a agregar:** `programas/tests/test_arquitectura.py::CapasTests.test_servicios_no_pasan_de_mil_lineas` (ratchet con la lista actual de excepciones).
- **Verificación:** `git diff --stat` del PR = solo movimientos; suite `programas.tests.test_dashboard_becas` y `test_dashboard_campos_propios` en verde; `perf_budgets.json` sin cambios.
- **Regla para no repetirlo:** **control mecánico** · `programas/tests/test_arquitectura.py` · test que recorre `*/services/*.py` y `*/views/*.py` y falla si un archivo pasa de 1.000 líneas y no está en `EXCEPCIONES_1K = {ruta: techo_actual}`; el techo solo puede bajar.

---

### B-LIM-14 · Dos embudos de revisión calculan las «mismas» etapas con definiciones distintas
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 4 · **Esfuerzo:** M
- **ID de la pasada 1:** B2-LIM-02
- **Ubicación:** `programas/services/dashboard_becas.py:456-483` (`_siis_ok`, `_embudo`), `:576-595` (identidad y lista de espera en `metricas`); `programas/services/reportes_becas.py:351-402` (`reporte_embudo`).
- **Escenario:** mismo usuario, misma convocatoria, mismo período: la solapa Dashboard y el reporte «Embudo de revisión» muestran etapas homónimas con números distintos.
  - «Identidad validada» del dashboard = `validado_renaper OR identidad_forzada` (`:576`); «Validados RENAPER» del reporte = solo `validado_renaper` (`reportes_becas.py:370`). Con un caso de identidad forzada difieren en 1.
  - «Beneficiarios» se quitó del dashboard por ser el mismo número que «Aprobados» («inconsistencia 2 del análisis», `:472-473`) y sigue en el reporte (`reportes_becas.py:382`).
  - Lista de espera: `ListaEspera.objects.filter(formulario__in=…, promovido=False).count()` (`:595`) contra `qs.filter(lista_espera__promovido=False).distinct().count()` (`reportes_becas.py:383`): cuentan entradas una y formularios la otra.
  - El anti-join de «última validación SIIS» está escrito dos veces (`:460-468` y `reportes_becas.py:360-367`; el comentario de la segunda dice «igual que `_siis_ok`»).
- **Causa raíz:** el embudo es una regla de dominio y no tiene dueño: cada pantalla arma su consulta y sus etiquetas.
- **Solución:** extraer a `programas/services/embudo_becas.py` (o a la sección de métricas del paquete de B-LIM-13) un `ultimas_validaciones_siis(formularios)` que devuelva el queryset del anti-join (usado por `_siis_ok` y por los motivos SIIS del reporte) y un `conteos_embudo(formularios) -> dict` con `total, renaper, identidad, aprobados, rechazados, baja, lista_espera`. Cada pantalla conserva **su** lista de etapas y etiquetas leyendo de ese dict, de modo que hoy nada cambia de número. `DECISIÓN CLIENTE:` alinear el reporte con el dashboard (identidad = RENAPER o forzada, sin «Beneficiarios»); por defecto, alinear, porque el análisis #366 ya declaró la inconsistencia.
- **Lo que NO hay que hacer:** «unificar» copiando el `_embudo` del dashboard dentro del reporte: cambia números del reporte en silencio sin decisión.
- **Tests a agregar:** `programas/tests/test_embudo_becas.py::EmbudoTests.test_dashboard_y_reporte_cuentan_igual_las_etapas_comunes` (caso con identidad forzada y uno en lista de espera; afirma qué etapas coinciden y cuáles difieren a propósito).
- **Verificación:** el test anterior y `assertNumQueries` iguales a los de hoy en ambos caminos.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` (tabla de helpers canónicos) · fila nueva: «Embudo de Becas / última validación SIIS → `conteos_embudo`, `ultimas_validaciones_siis`; una cifra del embudo calculada a mano en otra pantalla es duplicado (MEDIA)».

---

### B-LIM-15 · El cupo ocupado y el distribuido se calculan en tres lugares con alcances distintos
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) — la diferencia de cifras para un coordinador regional es PLAUSIBLE · **Eje:** LIM · **Origen:** — · **Hallado por 2 revisores** (B2-LIM-03 + B4-LIM-03); origen de la absorbida: B4-LIM-03: — (vecino de RED-49, que es de nombres, no de cálculo) · **Ola:** 4 · **Esfuerzo:** M
- **ID de la pasada 1:** B2-LIM-03 + B4-LIM-03 (**hallado por 2 revisores**)
- **Ubicación:** `programas/services/dashboard_becas.py:369-398` (`_cupo`); `programas/services/reportes_becas.py:50-108` (`reporte_cupos`, en especial `:55-60` y `:66-72`); `programas/services/cupo.py:55-72` (`get_cupo_stats`).
- **Escenario:** el docstring de `_cupo` dice «como `reporte_cupos`» y el comentario de `reporte_cupos` (`:61-65`) dice que tiene que dar lo mismo que `get_cupo_stats`, que «mira el segmento entero». Pero:
  - distribuido del regional: `_cupo` suma `subsegmentos_a_cargo(user)` (`:377-384`) y `reporte_cupos` suma `subsegmentos_visibles(user)` (`:55-60`);
  - ocupado: `get_cupo_stats` cuenta todos los aprobados del segmento; `_cupo` y `reporte_cupos` solo los de `convocatorias_visibles(user)` (`:388`, `reportes_becas.py:29`).
  Para un usuario que no ve todas las convocatorias del segmento (o un regional con subsegmentos visibles ≠ a cargo), las tres cifras de «cupo ocupado» pueden diferir.
- **Causa raíz:** el cupo es una regla de dominio (BEC-05, D-B05) con dueño en `services/cupo.py`, pero los dos reportes la reimplementan con su propio alcance.
- **Solución:** agregar en `programas/services/cupo.py` un `ocupacion_por_segmento(segmento_ids, *, convocatorias=None) -> dict[int, int]` y `distribuido_por_segmento(subsegmentos_qs) -> dict[int, int]`; `_cupo` y `reporte_cupos` los llaman pasando **exactamente** el queryset que usan hoy (`subsegmentos_a_cargo` / `subsegmentos_visibles`, `convocatorias_visibles`), así no cambia ningún número. `DECISIÓN CLIENTE:` si el ocupado debe ser el del segmento entero (como `get_cupo_stats`); por defecto sí, que es lo que dice el comentario de `reporte_cupos`.
- **Lo que NO hay que hacer:** llamar `get_cupo_stats` por segmento en un bucle (N consultas) ni cambiar el alcance sin la decisión.
- **Tests a agregar:** `programas/tests/test_cupo.py::OcupacionTests.test_dashboard_reporte_y_stat_card_coinciden_para_admin` y `…_para_regional` (documenta la diferencia actual hasta la decisión).
- **Verificación:** los dos tests; presupuestos de consultas del dashboard y de `reportes/cupos/` sin cambios.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md`, tabla de helpers canónicos · «Cupo ocupado / distribuido → `programas/services/cupo.py`; contarlo con `Formulario.objects.filter(estado=APROBADO)` en otro módulo es duplicado (MEDIA)».

#### Aporte del segundo revisor (B4-LIM-03: «Cupo ocupado por segmento» se calcula en tres lugares con tres reglas de alcance)
_Pasada 1: severidad MEDIA · estado CONFIRMADO (lectura) la duplicación; PLAUSIBLE la divergencia de números · esfuerzo S-M._

- **Ubicación:** `programas/services/cupo.py:63-66` (`get_cupo_stats`, segmento entero);
  `programas/services/dashboard_becas.py:388-397` (`_cupo`, acotado a `convocatorias_visibles(user)`);
  `programas/services/reportes_becas.py:66-72` (`reporte_cupos`, `_formularios_del_alcance` sin RN-P13).
- **Escenario:** `reportes_becas.py:61-65` ya documenta que el ocupado es **capacidad** y no puede recortarse por
  visibilidad («este reporte decía 3/97 donde la stat card de Cupo y la aprobación dicen 10/90»). `dashboard_becas._cupo`
  sí lo recorta por `convocatorias_visibles(user)`: un usuario que no ve todas las convocatorias del segmento puede ver en
  el dashboard un ocupado menor que el de la pantalla de Cupo y el que usa la aprobación (PLAUSIBLE: depende del alcance
  del usuario). Tres consultas `Formulario … APROBADO … GROUP BY segmento` con el mismo propósito.
- **Causa raíz:** no hay un selector de capacidad; cada pantalla reescribió el `COUNT`.
- **Solución:** `programas/selectors/cupo.py::ocupados_por_segmento(segmento_ids) -> dict[int, int]` (una consulta
  agrupada, segmento entero, sin alcance: es capacidad). `get_cupo_stats` la usa para un id; `reporte_cupos` y
  `dashboard_becas._cupo` también. El **máximo** sigue siendo de cada pantalla (el regional suma subsegmentos), solo se
  unifica el ocupado. **DECISIÓN CLIENTE** (§7) si el dashboard debe cambiar su número (alinearlo con Cupo es lo coherente con
  D-22/RED-49; si el PM quiere el recorte, que quede como función con otro nombre).
- **Lo que NO hay que hacer:** «unificar» con `Segmento.cupo_disponible` (acepción distinta, RED-49).
- **Tests a agregar:** `programas/tests/test_cupo.py::OcupadoUnicoTests.test_dashboard_reporte_y_cupo_dicen_lo_mismo`.
- **Verificación:** `grep -rn "estado=Formulario.Estado.APROBADO" programas/services/{dashboard,reportes}_becas.py` sin
  agrupaciones por segmento propias.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md` helpers canónicos: «Cupo ocupado →
  `selectors.cupo.ocupados_por_segmento` (capacidad, sin alcance de visibilidad)».

---

### B-LIM-16 · La fila «avance por convocatoria» se calcula dos veces (dashboard y reporte de avance)
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 10 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B2-LIM-04
- **Ubicación:** `programas/services/dashboard_becas.py:401-404` (`_estado_convocatoria`), `:417-453` (`_tabla_convocatorias`); `programas/services/reportes_becas.py:111-227` (`reporte_avance`, en especial `:162-184`).
- **Escenario:** las dos funciones cuentan formularios por convocatoria y estado, calculan `revisados = aprobados + rechazados + bajas`, `% revisado` con un decimal y el texto «Activa / Cerrada por vencimiento / Cerrada»; el texto del estado está escrito dos veces (`:401-404` y `reportes_becas.py:182-184`) y la fórmula del porcentaje también (`:448` vía `_pct`, `reportes_becas.py:181` en línea). Un cambio de regla (por ejemplo, que BAJA no cuente como revisado) hay que hacerlo en dos lugares; olvidar uno deja la tabla del dashboard y el reporte con distinto «% revisado».
- **Causa raíz:** sin un helper de dominio «resumen de una convocatoria»; cada pantalla lo arma con sus columnas.
- **Solución:** mover `_estado_convocatoria` a un método/propiedad del modelo (`Convocatoria.estado_texto`) o a `services/convocatorias.py`, y un `resumen_formularios(conteo: Counter) -> dict` (recibidos, aprobados, rechazados, bajas, pendientes, revisado_pct) que usen `_tabla_convocatorias` y `reporte_avance`. Cada uno sigue con su consulta (el dashboard ya tiene el `Counter` del agrupado; el reporte arma el suyo de `contados`) y sus columnas/formatos actuales (`f"{porcentaje}%"` en el reporte).
- **Lo que NO hay que hacer:** hacer que el reporte use `metricas()` del dashboard: tiene otro recorte (filtros por fecha de convocatoria, no por `creado`) y otra caché.
- **Tests a agregar:** `programas/tests/test_reportes_becas.py::AvanceTests.test_revisado_y_estado_coinciden_con_dashboard`.
- **Verificación:** test anterior; HTML del reporte y CSV idénticos byte a byte sobre el fixture.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md` · «Estado y % revisado de una convocatoria → `Convocatoria.estado_texto` / `resumen_formularios`».

---

### B-LIM-17 · La lectura canónica de respuestas vive en el dashboard y la importa el envío a SIIS
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 10 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B2-LIM-05
- **Ubicación:** `programas/services/dashboard_becas.py:907-974` (`_como_dict`, `_opciones_texto`, `_valores_de`, `_ambito_y_pk`, `respuesta_de`), `:794-816` (`_planos_del_diseno`, «mismo contrato que `respuestas.planos_de`»); consumidor: `programas/services/siis_envio.py:20`, `:559`, `:574`.
- **Escenario:** `respuesta_de` se declara «**Única** lectura de la respuesta de un formulario» pero vive en un módulo de reportes de solo lectura. El camino de **escritura** a SIIS (`siis_envio`) depende del dashboard: cualquier refactor del dashboard (B-LIM-13) arrastra a SIIS, y un import circular futuro (dashboard → siis para mostrar algo) es directo. Los parsers tolerantes de JSON (`_como_dict`, `_valores_de`) son genéricos de `Formulario.data/respuestas`, no del tablero.
- **Causa raíz:** la función nació para el dashboard (G2-01) y SIIS la reutilizó desde donde estaba.
- **Solución:** mover `_como_dict` → `como_dict`, `_valores_de` → `valores_de`, `_opciones_texto` → `opciones_texto`, `_ambito_y_pk` y `respuesta_de` a `programas/services/respuestas.py` (que ya es dueño de `planos_de`, `campos_de`, `legible`); `dashboard_becas` y `siis_envio` importan de ahí. Mientras dure la transición, `dashboard_becas` re-exporta `respuesta_de` para no romper imports externos.
- **Lo que NO hay que hacer:** dejar dos copias «por las dudas»; tocar el comportamiento tolerante (doble codificado, `{valor, etiqueta}`): es lo que hace que filas viejas no rompan.
- **Tests a agregar:** `programas/tests/test_arquitectura.py::CapasTests.test_siis_no_importa_de_dashboard` (arista prohibida `services.siis_* → services.dashboard_becas`).
- **Verificación:** `grep -rn "dashboard_becas" programas/services/siis*.py` vacío; suites de SIIS y dashboard en verde.
- **Regla para no repetirlo:** **control mecánico** · `programas/tests/test_arquitectura.py` · lista de aristas prohibidas entre servicios: ningún servicio de escritura (`siis_*`, `becas`, `revision`) importa de un servicio de reportes (`dashboard_becas`, `reportes_becas`).

---

### B-LIM-18 · Política de autorización y de freno del dashboard escrita en la vista
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** arista `("configuracion", "dashboard_becas")` del ratchet RED-79 (`programas/tests/test_arquitectura.py:82`) · **Ola:** 10 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B2-LIM-06
- **Ubicación:** `programas/views/dashboard_becas.py:40-60` (`CAP_*`, `puede_ver_dashboard`, `puede_exportar_dashboard`, `_programa_o_403`), `:90-99` (freno de `?recalcular=1`); `programas/views/configuracion.py:326`; `programas/views/reportes_becas.py:46-52`, `:125-131` (mismas capacidades como literales).
- **Escenario:**
  - `configuracion` importa `puede_ver_dashboard/puede_exportar_dashboard` **de otra vista** (import local para esquivar el ciclo), y esa arista vista→vista está en la lista de excepciones del ratchet. Las mismas dos capacidades se evalúan además con literales en `ReportesPermissionMixin` y `ReporteBecasExportView`.
  - La vista decide la política de recálculo: llama `recalculo_permitido` y apaga `recalcular` (`:98-99`) antes de `metricas_cacheadas`. Otro llamador de `metricas_cacheadas(recalcular=True)` (un comando, la API) saltea el freno G1b-12 sin enterarse.
- **Causa raíz:** reglas de dominio (quién ve el tablero, cada cuánto se recalcula) escritas en la capa HTTP.
- **Solución:**
  - En `programas/services/autorizacion.py`: `CAP_REPORTES_VER`, `CAP_REPORTES_EXPORTAR`, `puede_reportes_becas(user, accion="ver"|"exportar")`. `views/dashboard_becas.py`, `views/reportes_becas.py` y `views/configuracion.py` lo importan de ahí; se borra la arista `("configuracion", "dashboard_becas")` del ratchet.
  - `metricas_cacheadas(..., recalcular)` aplica internamente `recalcular = recalcular and recalculo_permitido(programa, filtros, alcance.huella)`; la vista solo pasa el flag. `distribucion_cacheada` recibe el valor ya frenado (hoy lo recibe de la vista ya modificado: hay que devolverlo, p. ej. `metricas_cacheadas` → `(datos, desde_cache, recalculo_atendido)`).
- **Lo que NO hay que hacer:** mover `_programa_o_403` entero al servicio (lleva `get_object_or_404`/`PermissionDenied`, que son HTTP); solo el predicado.
- **Tests a agregar:** `programas/tests/test_dashboard_becas.py::FrenoRecalculoTests.test_metricas_cacheadas_frena_sin_pasar_por_la_vista`.
- **Verificación:** test anterior; `test_arquitectura` con una arista menos en `ARISTAS_CONOCIDAS`.
- **Regla para no repetirlo:** **control mecánico** · `programas/tests/test_arquitectura.py` · el ratchet de aristas vista→vista ya existe: bajar su techo en el mismo PR para que no vuelva.

---

### B-LIM-19 · El registro de reportes está repartido en tres lugares y tiene un caso especial
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 10 · **Esfuerzo:** M
- **ID de la pasada 1:** B2-LIM-07
- **Ubicación:** `programas/views/reportes_becas.py:17-43` (`REPORTES`), `:84-93` (`if codigo == "beneficiarios"`), `:94-96` (reconstruye el form en el `except`), `:97-120` (contexto); `programas/forms_reportes.py:62-88` (`parametros(codigo)`); `programas/templates/programas/becas/reportes/reporte.html:15-25` (`{% if codigo == 'cupos' or … %}` por campo).
- **Escenario:** agregar un reporte o un filtro obliga a tocar tres archivos con la misma lista de códigos: el diccionario de la vista, la cadena de `if` de `parametros` y la cadena de `{% if codigo == … %}` del template. Olvidar uno da un filtro que se muestra y se ignora, o que se aplica sin control visible. Además:
  - `beneficiarios` se resuelve con un `if` dentro del flujo genérico (paginado), y el export del mismo reporte va por el camino genérico;
  - `_filtros` usa `ValueError` como canal de errores del form y el `except` vuelve a construir el form (`:94-96`), lo que repite las consultas de `__init__` (segmentos, convocatorias, territoriales);
  - el contexto lleva claves que `reporte.html` no lee (`filtros_form`, `advanced`, `allow_or`, `reset_url`, `:102`, `:117-119`) y siete `filtro_*` copiados de `request.GET` (`:110-116`) en vez de los valores ya limpiados por el form.
- **Causa raíz:** el reporte no tiene una definición declarativa: qué filtros usa y si pagina están implícitos en código de tres capas.
- **Solución:** en `programas/services/reportes_becas.py`, una `@dataclass(frozen=True) class DefinicionReporte(titulo, descripcion, funcion, filtros: tuple[str, ...], queryset=None)` y `REPORTES = {...}` con `filtros=("segmento", "solo_activos")` para cupos, etc.; `beneficiarios` con `queryset=beneficiarios_queryset`. `ReporteBecasFiltroForm.parametros(campos)` genérico (mapea `segmento→segmento_id`, `convocatoria→convocatoria_id`, `territorial→territorial_id`, `estado→estado or None`). La vista: `if definicion.queryset: paginar` en vez de comparar el código; errores del form leídos de `form.errors` sin excepción. El template conserva **el mismo markup** de cada campo, cambiando solo la condición a `{% if 'segmento' in definicion.filtros %}`. Borrar las claves de contexto muertas.
- **Lo que NO hay que hacer:** pasar el template a `{{ form.as_p }}` o a un include genérico de filtros: cambia el HTML (estética) y rompe el ratchet de diseño.
- **Tests a agregar:** `programas/tests/test_reportes_becas.py::RegistroTests.test_cada_filtro_del_template_llega_a_la_funcion` (para cada código, cada filtro declarado aparece en el HTML y en los kwargs de la función).
- **Verificación:** HTML de los cinco reportes idéntico al de hoy sobre el fixture (snapshot); `compile_templates.py` en 0.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md` · «Un registro (reportes, solapas, exportes) se declara una vez como datos; un `if codigo == …` en la vista, el form o el template que repite el registro es espagueti (MEDIA)».

---

### B-LIM-20 · `siis_envio.py` tiene 1.518 líneas y mezcla seis responsabilidades
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 8 · **Esfuerzo:** M
- **ID de la pasada 1:** B3-LIM-01
- **Ubicación:** `programas/services/siis_envio.py:1-1518`. CUIL `81-230`, dirección `236-272`, catálogos/normalización `278-505`, payload `511-979`, ciclo de vida del envío `988-1357`, drenaje de la tabla intermedia `1360-1472`, texto del toast `1480-1518`.
- **Escenario:** cualquier cambio en el alta (una regla de CUIL, un campo del payload, un estado del envío) se hace en un archivo de 1.5k líneas donde conviven aritmética de módulo 11, regex de domicilios, un índice en memoria de catálogos, la máquina de estados de `EnvioSIIS` con `select_for_update` y los textos que ve el coordinador. El síntoma más claro está en `140-144`: `TEXTO_CUIL_TITULAR` se escribe como literal **porque `clave_nombre` se define 135 líneas más abajo**, y un test solo existe para fijar que los dos sigan coincidiendo. El orden del archivo ya condiciona el diseño.
- **Causa raíz:** el módulo nació como «armar el payload» y fue absorbiendo cada arreglo de SIIS-01/02/04/05/08/12/18, G1-08/10/11 y PERF-01 en el mismo lugar.
- **Solución (sin cambiar comportamiento):** partir en módulos hermanos y dejar `siis_envio.py` como dueño del ciclo de vida, que es donde se llama a `cargar_beneficiario` y `armar_payload`, los dos nombres que los tests sustituyen:
  - `services/siis_cuil.py`: `_verificador`, `calcular_cuil`, `PREFIJOS_CUIL`, `cuil_valido`, `evaluar_cuil_respondido`, `CUIL_*` (~110 líneas, puras).
  - `services/siis_catalogos.py`: `clave_nombre`, `_clave_sin_genero`, `CLAVES_PROVINCIA`, `provincia_de`, `Catalogos`, `CatalogoNoDisponible`, `CopiaDeCatalogoFaltante`, `CODIGO_SIN_COPIA_CATALOGO` (~240 líneas).
  - `services/siis_payload.py`: `parsear_direccion`, `normalizar_celular`, `respuestas_por_destino` y sus `_destinos_*`, `_apoderado`, `_chequear_identidad_acreditada`, `cuil_del_caso`/`_cuil_respondido`, `armar_payload` (~520 líneas).
  - `siis_envio.py` queda con `_base_envio`, `CasoYaInformado`, `CIERRE_POR_RESULTADO`, `_reservar`, `_cerrar`, `enviar_beneficiario_a_siis`, `_mandar_a_siis`, `guardar_en_tabla_intermedia`, `payload_de`, `sincronizar_tabla_intermedia` y `mensaje_envio` (~550 líneas), e **importa** `armar_payload`/`Catalogos`/`CatalogoNoDisponible` por nombre: `patch("…siis_envio.armar_payload")` sigue funcionando. También re-exporta lo que hoy importan 14 módulos de producción (`from programas.services.siis_envio import clave_nombre, Catalogos, …`), con `__all__`, para que la partición sea un PR sin cambios en los llamadores.
- **Lo que NO hay que hacer:** mover `enviar_beneficiario_a_siis`/`_mandar_a_siis` fuera de `siis_envio.py`. Las 46 sustituciones de `siis_envio.cargar_beneficiario` dejarían de interceptar y los tests mandarían el alta al cliente real.
- **Tests a agregar:** `programas/tests/test_siis_particion.py::ReexportsTests.test_nombres_publicos_siguen_en_siis_envio`, que importa cada nombre que hoy usa producción desde `siis_envio`.
- **Verificación:** suite completa de `programas` igual que antes. `wc -l` de cada módulo < 600.
- **Regla para no repetirlo:** **control mecánico** · `core/tests/test_tamano_modulos.py` (ratchet) · `for f in glob("*/services/*.py"): assert lineas(f) <= max(1000, BASE[f])`, con `BASE` congelado al SHA de hoy; un archivo solo puede bajar. Mensaje: «`<f>` pasa de 1000 líneas: partilo antes de sumar (rúbrica codigo-limpio §1)».

---

### B-LIM-21 · El bucle «lote → caso → freno → línea de avance → pausa» está copiado en tres comandos (y un cuarto en el masivo)
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** RED-53 (extrajo los flags y el freno, no el bucle) · **Ola:** 8 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B3-LIM-03
- **Ubicación:** `validar_casos_siis.py:283-309`, `enviar_casos_siis.py:242-276`, `procesar_casos_siis.py:466-503`. Variante sin lotes: `reenviar_siis_pendientes.py:96-117`. Cuarta copia: `proceso_masivo.py:1101-1140`.
- **Escenario:** las tres copias repiten `for numero, lote in self._lotes(...)`, `parcial`, `freno.registrar(...)`, `detenido = True; break`, la línea `lote n/N · … · s` y `if pausa and numero < total_lotes: time.sleep`. Ya hay diferencias de detalle (procesar hace una pausa extra de empalme con el drenaje, `467-469`; reenviar no tiene pausa ni lotes). La base existe precisamente para que «el día que cambie, cambie en los cuatro» (`_base_siis.py:241-248`), pero el bucle, que es donde se usa el freno, quedó afuera.
- **Causa raíz:** RED-53 extrajo piezas (flags, `_crear_freno`, `_resumen`) y no el esqueleto (template method).
- **Solución:** `ComandoSiisBase.correr_por_lotes(items, *, tamano, pausa, freno, procesar_uno, describir_lote, pausa_inicial=False) -> bool` (devuelve `detenido`). `procesar_uno(item)` devuelve el desenlace para el freno; `describir_lote(numero, total, lote, segundos)` arma la línea. Los tres `handle` quedan en selección + resumen. `reenviar` pasa a usarlo con `tamano=len(casos)` y su log por caso dentro de `procesar_uno`, sin cambiar la salida.
- **Lo que NO hay que hacer:** unificar con `proceso_masivo.correr` en el mismo paso. Ese bucle además late, mira la cancelación y escribe la corrida. Se puede converger después, cuando el bucle de los comandos sea uno.
- **Tests a agregar:** `programas/tests/test_base_siis.py::CorrerPorLotesTests.test_corta_en_el_caso_que_dispara_el_freno`, `…test_no_pausa_despues_del_ultimo_lote`. Los `FrenoConSiisCaidoTests` existentes son la caracterización.
- **Verificación:** `FrenoConSiisCaidoTests` y los tests de salida de los tres comandos en verde sin tocarlos.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md`, bajo «Helpers canónicos»: «Recorrer casos de SIIS por lotes con freno → `ComandoSiisBase.correr_por_lotes`. Un `for … in self._lotes(` con `freno.registrar` en un comando es duplicado.»

---

### B-LIM-22 · Tres comandos de la integración no heredan `ComandoSiisBase` y reescriben sus guardas
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** SIIS-03 (resuelto), RED-53 · **Ola:** 8 · **Esfuerzo:** S
- **ID de la pasada 1:** B3-LIM-04
- **Ubicación:** `correr_alta_siis.py:186-195, 199-201, 221-243`. `conciliar_envios_siis.py:84, 123-129, 250-251`. `sincronizar_programas_siis.py:44-70`. Contra `_base_siis.py:50-61, 175-209, 223-225, 261-274`.
- **Escenario:** la base dice «una guarda nueva se agrega en esta clase, y así nadie se entera tarde de que en un comando no existía» (`_base_siis.py:19-20`). Sin embargo, `correr_alta_siis` copia a mano el candado de corrida viva con `--ignorar-corrida`/`--motivo` (`231-240` ≈ `_base_siis.py:192-209`), el texto de ayuda de `--ignorar-corrida` (`189-193` = `AYUDA_IGNORAR_CORRIDA`), el chequeo de credenciales (`242-243` ≈ `272-274`) y `_log`. `conciliar_envios_siis` copia `_usuario` (= `_solicitante`) y `_log` (cuarta copia). `sincronizar_programas_siis` define otro `FALTA_MOTIVO` con el mismo nombre y otro texto. Consecuencia concreta: `correr_alta_siis` no corre `exigir_escritura_siis_permitida` (#569). En un ambiente no-PRD que apunta al SIIS productivo, ejecuta los pasos 2 a 5 (insumos `.sql`, RENAPER, `corregir_datos_siis`, todos escriben) y recién falla en el paso 6, cuando el hijo `procesar_casos_siis` levanta la guarda.
- **Causa raíz:** el criterio «hereda solo si habla con SIIS caso por caso» (`_base_siis.py:22`) mezcla dos cosas: el bucle (que estos no tienen) y las guardas (que sí necesitan).
- **Solución:** partir la base en `ComandoSiisGuardas(BaseCommand)` (flags sueltos, `exigir_sin_corrida_viva`, `exigir_escritura_siis_permitida`, `_exigir_credenciales`, `_solicitante`, `_log`) y `ComandoSiisBase(ComandoSiisGuardas)` (lotes, freno, resumen). Los tres comandos heredan de la primera. `correr_alta_siis._precondiciones` llama a `self.exigir_sin_corrida_viva(options)` y a `self.exigir_escritura_siis_permitida(options)` (esta última solo con `destino != tabla`, igual que `procesar_casos_siis.py:323-324`). Se borran `_responsable = _solicitante` (`_base_siis.py:270`) y los `_log`/`_usuario` duplicados.
- **Lo que NO hay que hacer:** que `correr_alta_siis` herede `ComandoSiisBase` completo. Sumaría `--lote`/`--max-errores` con otro default (`LOTE = 40` vs 50) y otro significado.
- **Tests a agregar:** `programas/tests/test_correr_alta_siis.py::GuardasTests.test_ambiente_no_prd_corta_en_el_paso_1_sin_cargar_insumos`.
- **Verificación:** con `escritura_siis_bloqueada()` en `True`, `correr_alta_siis --aplicar` termina en `CommandError` sin ejecutar ningún `.sql` (mock de `connection.cursor` con cero llamadas).
- **Regla para no repetirlo:** **control mecánico** · `programas/tests/test_base_siis.py::TodosHeredanLasGuardasTests` · AST de `programas/management/commands/*siis*.py`: toda clase `Command` debe ser subclase de `ComandoSiisGuardas`; mensaje: «comando SIIS sin la base de guardas (ver `_base_siis.py`)».

---

### B-LIM-23 · Las precondiciones de `correr_alta_siis` reimplementan con otra regla lo que lee `armar_payload` y frenan circuitos que sí saldrían
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** G1-08 / G1-10 (dónde vive el destino) · **Ola:** 8 · **Esfuerzo:** S
- **ID de la pasada 1:** B3-LIM-05
- **Ubicación:** `correr_alta_siis.py:60-68` (`DESTINOS`), `245-255` (solo `RequisitoNativo`), `217-219` y `265-273` (`_tiene_identificadores`). Contra `siis_envio.py:609-646` (`_destinos_del_catalogo` también lee `PreguntaGlobal`), `590-606` (destinos de la foto) y `943-973` (los ids salen de la corrección → el segmento → el programa).
- **Escenario:** (a) Si el organismo marca `loc_actual` en una **pregunta general** (`PreguntaGlobal.destino_siis`), `armar_payload` la resuelve bien, pero el paso 1 dice «Hay preguntas sin el destino SIIS marcado: loc_actual» y no arranca. (b) Si un programa no tiene `jurid`/`id_fun_x_plan` y sí los tiene cargados en su segmento, que es la prioridad del Cambio 82, el paso 1 lo lista como «sin identificadores (sus casos no van a salir)». Si es el único, corta con «Ningún programa tiene los identificadores», aunque los casos saldrían.
- **Causa raíz:** la lista de los 7 destinos y la regla de «programa listo» son una segunda copia del contrato del payload, escrita aparte y sin las reglas que el payload ganó después.
- **Solución:** exponer el contrato desde el dueño. En `siis_payload.py` (o en `siis_envio.py` hasta B-LIM-20): `DESTINOS_DEL_PAYLOAD = ("est_civil", "prov_actual", "loc_actual", "barrio_actual", "calle_altura", "prov_nacim", "loc_nacim")`, usado también por `armar_payload`; `destinos_marcados()` que une `PreguntaGlobal` y `RequisitoNativo` como `_destinos_del_catalogo`; `identificadores_resolubles(programa, segmentos)` con la misma cadena de `_primero_con_valor`. El comando solo los llama.
- **Lo que NO hay que hacer:** sumar `PreguntaGlobal` a mano en el comando. Sería una tercera copia.
- **Tests a agregar:** `programas/tests/test_correr_alta_siis.py::PrecondicionesTests.test_destino_en_pregunta_global_alcanza`, `…test_ids_en_el_segmento_alcanzan`.
- **Verificación:** los dos escenarios pasan `--solo-precondiciones` con «Está todo lo que hace falta para arrancar».
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` · «Una precondición que valida lo que otro módulo va a consumir tiene que llamar a ese módulo, no copiar su lista. Tuplas de claves del payload SIIS fuera de `siis_payload` son duplicado.»

---

### B-LIM-24 · `enviar_beneficiario_a_siis` y `guardar_en_tabla_intermedia` duplican el preámbulo, y el `EnvioSIIS` cerrado se arma a mano en seis lugares
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** SIIS-01/SIIS-04 (cerrados) · **Ola:** 8 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B3-LIM-06
- **Ubicación:** `siis_envio.py:1227-1254` vs `1303-1322` (preámbulo); `EnvioSIIS.objects.create(..., resuelto_en=timezone.now(), **base)` en `1096-1103`, `1128-1134`, `1162-1168`, `1244-1250`, `1314-1320`, `1324-1331`.
- **Escenario:** los dos caminos hacen, en el mismo orden: atajo por envío vigente, `_base_envio`, alta de oficio, `armar_payload` con `CatalogoNoDisponible → ERROR` y la corrección de `id_programa`/`id_funcion` desde el payload. Ya divergen en un punto: `enviar` relee el estado **bajo lock** en `_reservar` (SIIS-04), mientras `guardar_en_tabla_intermedia` mira `formulario.estado` sin lock (`1303`). El `INCOMPLETO` con `"DATOS_INCOMPLETOS"` se crea en dos lugares con literales repetidos.
- **Causa raíz:** el destino «tabla» (Cambio 108) se escribió copiando el camino «siis» en vez de factorizar lo común.
- **Solución:** dos piezas, sin tocar el orden de las operaciones:
  - `_envio_cerrado(base, estado, codigo, detalles, payload=None)`: la única fábrica de un `EnvioSIIS` ya resuelto, que reemplaza las seis copias.
  - `_preparar(formulario, solicitado_por, catalogos) -> EnvioSIIS | Preparado(payload, faltantes, base)` (dataclass): atajo vigente, oficio, payload, catálogo caído e ids. `enviar_beneficiario_a_siis` y `guardar_en_tabla_intermedia` quedan en 6-10 líneas cada una.
  La guarda sin lock de `guardar_en_tabla_intermedia` se conserva tal cual en este paso. Si se quiere alinear con SIIS-04, va en un PR propio porque cambia el comportamiento.
- **Lo que NO hay que hacer:** hacer que `guardar_en_tabla_intermedia` pase por `_reservar`: crearía un `EN_PROCESO` y un `vigente` que el destino tabla, a propósito, no deja.
- **Tests a agregar:** ninguno nuevo. Caracterizar con `test_siis_envio*.py` y `test_tabla_intermedia*.py` existentes antes y después.
- **Verificación:** `grep -c "EnvioSIIS.objects.create" programas/services/siis_envio.py` == 2 (la fábrica y la reserva `EN_PROCESO`).
- **Regla para no repetirlo:** **skill** · rúbrica `codigo-limpio.md` · «Un `EnvioSIIS` cerrado se crea solo con `_envio_cerrado`. Un `EnvioSIIS.objects.create(` nuevo en `siis_envio` es duplicado.»

---

### B-LIM-25 · El resultado del cliente SIIS es un dict sin contrato, y el consumidor tiene una rama para mocks
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** SIIS-02, SIIS-11 (cerrados) · **Ola:** 8 · **Esfuerzo:** M
- **ID de la pasada 1:** B3-LIM-08
- **Ubicación:** `siis.py:188-198` (`_fallo`), `555-621` (`validar_compatibilidad`: `success/compatible/error/data/cortado`), `736-814` (`_intentar_alta`: `success/resultado/codigo/reintentable/error/detalles/data/siis_id`). `siis_envio.py:1039-1048` (`_estado_final`: «Un cliente viejo (o un mock de test) sin `resultado`: se cae al criterio anterior»). `validacion_siis.py:43-52` (vuelve a envolver con `crudo` lo que `siis.py:582-587` ya envolvió).
- **Escenario:** el contrato SIIS-02 (OK / NO_ENVIADO / RECHAZADO / INCIERTO) es lo que decide si un alta irreversible se reintenta, y viaja como un dict con claves opcionales. `_estado_final` adivina el estado cuando falta `resultado`: producción carga una rama cuyo único cliente es un mock viejo. Si un mock nuevo omite `resultado` y pone `reintentable=True`, el test ve `ERROR` aunque el código real devolvería otra cosa, y pasa por el motivo equivocado. En el otro extremo, `validar_formulario_en_siis` no sabe si `data` ya viene normalizado y lo normaliza de nuevo.
- **Causa raíz:** no hay un tipo en la frontera cliente/servicio; cada capa se defiende de la otra.
- **Solución:** `@dataclass(frozen=True) class ResultadoAlta: resultado: str; codigo: str = ""; error: str = ""; detalles: dict; data: dict; siis_id: int | None = None` con `success`/`reintentable` como propiedades derivadas de `resultado`, y `ResultadoCompatibilidad(success, compatible, error, data, cortado)`. El cliente garantiza `data: dict`. Se borran la rama de fallback de `_estado_final` y el `crudo` de `validacion_siis.py`. Para no romper a `diagnosticar_siis`/`diagnosticar_integraciones`, que leen `resultado["success"]`, la dataclass expone `__getitem__`/`get` de compatibilidad durante una release.
- **Lo que NO hay que hacer:** borrar el fallback de `_estado_final` antes de actualizar los mocks: los tests que lo usan pasarían a `KeyError`. Primero los mocks devuelven `ResultadoAlta`, después se borra la rama.
- **Tests a agregar:** `programas/tests/test_siis_contrato.py::ResultadoAltaTests.test_reintentable_solo_si_no_enviado`, `…test_estado_final_exige_resultado`.
- **Verificación:** `grep -n "mock de test" programas/services/siis_envio.py` vacío; mypy limpio si se suma `siis.py` al alcance de `[tool.mypy] files`.
- **Regla para no repetirlo:** **control mecánico** · `pyproject.toml [tool.mypy] files += ["programas/services/siis.py", "programas/services/siis_envio.py"]` · el contrato tipado se rompe en CI si alguien vuelve a devolver un dict suelto.

---

### B-LIM-26 · La política del drenaje de la tabla intermedia (cuándo frenar y qué hacer después) vive en `procesar_casos_siis`, y su `handle` tiene 220 líneas
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura); la divergencia con el masivo, PLAUSIBLE · **Eje:** LIM · **Origen:** Cambio 108/138, Cambio 401 paso 9 · **Ola:** 8 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B3-LIM-17
- **Ubicación:** `procesar_casos_siis.py:134-208` (`_vaciar_tabla_intermedia`: lotes, tope, freno), `210-216` (`_envio_que_corta`), `238-254` (`_motivo_de_freno_del_drenaje`), `218-236` (`_que_hacer_tras_el_freno`), `316-537` (`handle`). Contra `siis_envio.py:1395-1472` (`sincronizar_tabla_intermedia`, cuya docstring dice «una corrida con destino SIIS vacía esto **antes** de seguir con los casos nuevos»).
- **Escenario:** la regla «el drenaje frena en el primer lote con algo que una persona tiene que mirar» y la de «qué envío corta el lote» están en el comando. `proceso_masivo.correr`, la corrida de la pantalla, no drena la tabla (`proceso_masivo.py:1094-1100`): la frase de la docstring del servicio vale solo para una de las dos corridas. Si es a propósito, no está escrito; si no lo es, es la misma divergencia de B-ERR-01 en otro eje. El `handle` mezcla precondiciones, confirmación interactiva, drenaje, selección, resumen y bucle.
- **Causa raíz:** el comando fue el primer y único cliente del drenaje y la política creció adentro de él.
- **Solución:** `siis_envio.drenar_tabla_intermedia(responsable, *, total, lote, pausa, al_lote) -> Drenaje(sigue: bool, mando: bool, cuenta: dict, motivo: str)` con `_envio_que_corta` y `_motivo_de_freno_del_drenaje` adentro. El comando conserva la impresión de cada lote (`al_lote`) y `_que_hacer_tras_el_freno` (son textos de consola). `handle` se parte en `_preparar` (guardas, credenciales, materias, confirmación), `_elegir_casos` (selección y descartes) y `_procesar` (bucle de B-LIM-21).
  `DECISIÓN CLIENTE: por defecto la corrida de la pantalla NO drena la tabla intermedia (comportamiento actual); se corrige la docstring de sincronizar_tabla_intermedia para que lo diga.`
- **Lo que NO hay que hacer:** llamar al drenaje desde `proceso_masivo.correr` sin decisión: cambia qué sale a SIIS desde la pantalla, y sale sin la confirmación escrita del Cambio 138.
- **Tests a agregar:** `programas/tests/test_tabla_intermedia.py::DrenajeTests.test_frena_en_el_primer_lote_con_rechazos` (llamando al servicio, sin el comando).
- **Verificación:** `handle` < 60 líneas; los tests del comando con destino SIIS siguen en verde.
- **Regla para no repetirlo:** **skill** · rúbrica `codigo-limpio.md` · «Un `handle()` de más de 80 líneas, o un `@staticmethod` de comando que decide sobre estados de `EnvioSIIS`, es lógica de dominio en la capa equivocada.»

---

### B-LIM-27 · Cuatro comandos de alta que se solapan: `enviar_casos_siis` y `reenviar_siis_pendientes` son modos de `procesar_casos_siis`, y `correr_alta_siis` es un orquestador sobre él
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** RED-53 (unificó flags, no comandos) · **Ola:** 8 · **Esfuerzo:** M
- **ID de la pasada 1:** B3-LIM-18
- **Ubicación:** `procesar_casos_siis.py` (con `--solo-enviar`, `106-109`), `enviar_casos_siis.py` (303 líneas), `reenviar_siis_pendientes.py` (117 líneas; `66-68` falsea `options` con `{**options, "aplicar": aplicar}` para el alias `--dry-run`), `correr_alta_siis.py` (536 líneas).
- **Escenario:** «informar el alta de los aprobados que faltan» se puede pedir de tres formas: `procesar_casos_siis --solo-enviar`, `enviar_casos_siis` y `reenviar_siis_pendientes`. Cada una tiene su selector (B-ERR-01), su bucle (B-LIM-21), su resumen y sus textos. Lo que agregan es ortogonal: `enviar` permite estados sensibles con `--si-entiendo` y `--reintentar-rechazados`; `reenviar` toma solo «último = ERROR» y excluye los agotados. El operador tiene que saber cuál de las tres respeta cada regla, y hoy la respuesta es distinta para cada una.
- **Causa raíz:** cada necesidad operativa nueva (reintento nocturno, estados sensibles, circuito completo) nació como un comando y no como un modo del mismo flujo.
- **Solución (preserva comportamiento y nombres):**
  1. Un servicio `proceso_masivo.informar_casos(casos, *, solicitante, catalogos, freno, exigir_aprobado, estados_permitidos, al_caso)` que es el «enviar caso por caso con freno» de los tres.
  2. Un selector por modo sobre la base común de B-ERR-01: `modo="pendientes"` (enviar), `modo="errores"` (reenviar), `modo="circuito"` (procesar).
  3. `enviar_casos_siis` y `reenviar_siis_pendientes` quedan como **envoltorios finos** (argumentos → modo → servicio → resumen), sin cambiar flags ni salida. Así no se rompen los procedimientos ni el CronJob, y un comando unificado se puede discutir después.
  4. `--dry-run` de reenviar: `parser.set_defaults` o un `aplicar` resuelto antes de las guardas, sin falsear el dict `options`.
- **Lo que NO hay que hacer:** borrar `enviar_casos_siis` o `reenviar_siis_pendientes`. Los nombran `docs/internal/procedimiento-alta-siis.md` y los procedimientos del PM; retirarlos es una decisión operativa, no de código.
- **Tests a agregar:** `programas/tests/test_siis_vias.py::MismoServicioTests.test_las_tres_vias_llaman_a_informar_casos`.
- **Verificación:** las tres vías comparten el selector base y `informar_casos`. `enviar_casos_siis.py` y `reenviar_siis_pendientes.py` quedan en menos de 120 líneas cada uno.
- **Regla para no repetirlo:** **skill** · rúbrica `codigo-limpio.md` · «Un comando de SIIS nuevo es un modo de los existentes, salvo justificación escrita en su docstring. Los comandos son envoltorios: argumentos → servicio → impresión.»

---

### B-LIM-28 · `services/proceso_masivo.py` tiene 1.191 líneas y cuatro responsabilidades
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 9 · **Esfuerzo:** M
- **ID de la pasada 1:** B4-LIM-01
- **Ubicación:** `programas/services/proceso_masivo.py:1-1191`.
- **Escenario:** el módulo mezcla (a) lectura de tablas de insumo externas por SQL crudo (`:68-203`, `:475-512`),
  (b) la consulta de candidatos —un selector— (`:219-258`, `:371-473`, `:514-775`), (c) el circuito por caso (`:261-369`,
  `:777-908`) y (d) la corrida en hilo con candado, latido y caché (`:911-1191`). Lo importan 8 comandos, la vista,
  `siis_envio` (con import diferido, ver B-LIM-63), `seed_perf` y `completar_casos_renaper` (este solo por `ids_de`).
  Es el archivo que más hallazgos acumuló en octubre (SIIS-03, SIIS-04, BEC-11, BEC-21, PERF-07, PERF-19…): cada
  arreglo agranda el mismo módulo.
- **Causa raíz:** el módulo nació como «lo compartido entre el comando y la pantalla» y fue absorbiendo cada capa nueva.
- **Solución:** partir sin cambiar una línea de lógica, dejando `proceso_masivo.py` como fachada que reexporta (todos los
  importadores siguen andando):
  | Módulo nuevo | Contenido | ~líneas |
  |---|---|---|
  | `programas/services/insumos_siis.py` | `TablaAprobadosMateriasFaltante`, `hay_aprobados_materias`, `dnis_aprobados_materias`, `_tabla_siis_enviar`, `dnis_a_no_enviar`, `dnis_crudos_a_no_enviar`, `Insumos` | 200 |
  | `programas/selectors/candidatos_siis.py` | `_Q_PAUSADO`, `_Q_SIIS_BLOQUEADO`, `Q_PROGRAMA_VALIDA_SIIS`, `casos_con_errores_agotados`, `_solo_los_aprobables`, `_sin_pausa_vigente`, `_por_incompatibilidad`, `candidatos`, `excluidos_por_pausa`, `conteos_de_la_pantalla` | 380 |
  | `programas/selectors/formularios_por_lotes.py` | `ids_de`, `hidratar`, `hidratar_por_lotes`, `JSON_DEL_CASO`, `SELECT_RELATED_CASOS` (genéricos, no son de SIIS) | 80 |
  | `programas/services/circuito_siis.py` | `FALLA_*`, `desenlace_de`, `Freno`, `Cuenta`, `CONTADORES`, `elegir_completos`, `procesar_caso` | 260 |
  | `programas/services/corrida_siis.py` | `_tomar_candado`, `CorridaEnCurso`, `exigir_sin_corrida_viva`, `registrar_corrida_ignorada`, `crear_corrida`, `correr`, `lanzar`, `clave_*`, `invalidar_conteos` | 290 |
- **Lo que NO hay que hacer:** mover y a la vez «mejorar» (B-LIM-33/12): primero el corte mecánico con la fachada, en un
  PR propio, para que el diff de lógica sea cero y revisable con `git diff --color-moved`.
- **Tests a agregar:** `programas/tests/test_proceso_masivo_fachada.py::FachadaTests.test_reexporta_la_api_publica`
  (lista de nombres que hoy importan comandos y vista).
- **Verificación:** suite de `programas` verde; `wc -l` de cada módulo < 400.
- **Regla para no repetirlo:** **control mecánico** · test ratchet `core/tests/test_tamano_archivos.py`: recorre
  `*/services`, `*/views`, `*/selectors`; falla si un archivo **nuevo** pasa de 1.000 líneas o si uno de la lista de
  deuda (con su tamaño de hoy como techo: `dashboard_becas.py` 1780, `proceso_masivo.py` 1191…) crece. Mensaje:
  «`<archivo>` pasó de N a M líneas: partilo antes de sumar (rúbrica codigo-limpio, regla 1)».

---

### B-LIM-29 · Normalización de DNI, sexo y fecha reescrita fuera de sus canónicas (y una contradice a la otra)
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura); PLAUSIBLE el impacto de «MUJER» · **Eje:** LIM · **Origen:** reaparición del patrón de RED-47/RED-48 (resueltos) en copias nuevas · **Ola:** 9 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B4-LIM-04
- **Ubicación:**
  - DNI: `proceso_masivo.py:91-92` (`_solo_digitos` con `\D`, no `core.dni.normalizar_dni`), variantes de ceros escritas
    dos veces `:124-131` y `:177-181`, y una tercera forma `:202`; `personas.py:117-125` (`_documento`) y `:344`.
  - Sexo: `padron.py:74-97` (`_SEXOS`: «MUJER»→F, «HOMBRE»/«VARÓN»→M) vs `personas.py:128-139` (`_inicial_de_sexo`: la
    inicial, así «MUJER»→**M** y «HOMBRE»→«») vs `personas.py:347-349`.
  - Fecha: `padron.py:138-170` (`normalizar_fecha`, con control de credibilidad G1-12) vs `personas.py:173-187`
    (`fecha_iso`, otros formatos y sin control), y `alta_de_oficio.py:353,407` usa la segunda para escribir
    `Ciudadano.fecha_nacimiento`.
- **Escenario:** (1) `_solo_digitos` no castea `float`/`Decimal`: si `SiisEnviar` —tabla que el PM crea a mano, tipo no
  garantizado— quedara `DECIMAL`/`DOUBLE`, `30123456.0` → `301234560` y la lista de exclusión no excluiría a nadie,
  exactamente el bug de RED-47 en una cuarta copia (PLAUSIBLE: la plantilla de `aprobados_materias` es `VARCHAR`).
  (2) si Base de Personas devolviera «MUJER», `_coincide` lo leería como M y rechazaría el registro de una mujer.
  (3) una fecha de Personas fuera de rango llega al legajo por `alta_de_oficio`, que el padrón ya no permite.
- **Causa raíz:** `core/dni.py` cubre «dígitos» y «largo válido» pero no «variantes con y sin ceros», así que cada lector
  de planillas se escribió la suya; sexo y fecha no tienen canónica fuera de `padron`.
- **Solución:** en `core/dni.py`: `dni_sin_ceros(valor) = normalizar_dni(valor).lstrip("0")` y
  `variantes_dni(valor) -> set[str]` (tal cual, sin ceros, `zfill(8)`); `proceso_masivo` usa las dos (borra
  `_solo_digitos` y los dos bucles) y `personas._documento = dni_sin_ceros`. Sexo: mover `normalizar_sexo` a `core/` (o
  importarlo de `padron`) y que `_inicial_de_sexo` sea `normalizar_sexo(v) or (inicial si es F/M)` — conserva «no objeta»
  y deja de invertir «MUJER». Fecha: `fecha_iso` delega en `padron.normalizar_fecha` para el rango.
- **Lo que NO hay que hacer:** cambiar `normalizar_dni` para que quite ceros (rompe el `IN` contra `Ciudadano.dni` que los
  guarda).
- **Tests a agregar:** `core/tests/test_regla_dni.py::VariantesTests.test_variantes_con_float_y_decimal`;
  `programas/tests/test_personas.py::SexoTests.test_mujer_es_f_en_las_dos_puertas`.
- **Verificación:** `grep -rn "zfill(8)\|lstrip(\"0\")" programas/services` solo en `core/dni.py`.
- **Regla para no repetirlo:** **control mecánico** · ampliar `core/tests/test_regla_dni.py`: falla si en código
  productivo aparece `re.sub(r"\D"` o `.zfill(8)` sobre una variable cuyo nombre matchea `NOMBRE_DNI` fuera de
  `core/dni.py` («usá `normalizar_dni`/`variantes_dni`»).

---

### B-LIM-30 · «Completar el legajo solo donde está vacío» está tres veces, y `alta_de_oficio` importa privados de `becas`
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 9 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B4-LIM-05
- **Ubicación:** `programas/services/padron.py:655-687` (dentro de `validar_casos_pendientes`, también la versión JSON
  `:674-687`); `programas/services/alta_de_oficio.py:394-418` (`_acreditar`); `programas/views/revision.py:1279`
  (`if valor and not getattr(ciudadano, campo)` en una vista). Privados cruzados: `alta_de_oficio.py:33-37`
  (`_anotar_identidad_acreditada`) y `completar_casos_renaper.py:79` (`respuestas._identidad_de`).
- **Escenario:** la regla de RN-5 «no pisar lo cargado» vive en tres implementaciones: el padrón completa
  `nombre/apellido/fecha_nacimiento/localidad`, la alta de oficio solo `fecha_nacimiento/nombre/apellido` (sin
  localidad) y la de revisión su propia lista. Un campo nuevo de identidad (p. ej. CUIL) se va a completar en una y no en
  las otras.
- **Causa raíz:** la identidad acreditada no tiene un servicio dueño de «volcarla al legajo».
- **Solución:** `programas/services/identidad.py::completar_ciudadano(ciudadano, datos) -> list[tuple[campo, valor]]`
  que **no guarda** (devuelve los campos tocados, para que el padrón siga haciendo `bulk_update` agrupado por campos y
  `_acreditar` haga `save(update_fields=…)`). Hacer públicos `anotar_identidad_acreditada` e `identidad_de` (renombrar,
  dejando alias privados una release) en vez de importarlos con guion bajo.
- **Lo que NO hay que hacer:** que el helper guarde: rompería el lote de PERF-04 en `validar_casos_pendientes`.
- **Tests a agregar:** `programas/tests/test_identidad.py::CompletarCiudadanoTests.test_no_pisa_y_devuelve_lo_tocado`.
- **Verificación:** `grep -rn "not getattr(ciudadano, campo)\|not ciudadano.nombre" programas` solo en `identidad.py`.
- **Regla para no repetirlo:** **control mecánico** · regla ruff `PLC2701` (import-private-name) en `pyproject.toml` con
  la lista de hoy como `per-file-ignores` a vaciar.

---

### B-LIM-31 · `completar_casos_renaper` lleva dominio dentro del comando y clona `sincronizar_desde_legacy`
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 9 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B4-LIM-06
- **Ubicación:** `programas/management/commands/completar_casos_renaper.py:259-274` (`_poner_foto`, idéntico a
  `programas/services/respuestas.py:265-273` salvo el `save`, y su docstring lo dice), `:276-328` (`_cruzar`), `:113-120`
  (`_norm`, tercera variante de «sin acentos» junto a `padron.clave_localidad:173-178` y `alta_de_oficio._sin_acentos:103-105`),
  `:76` (`ids_de` importado del módulo del circuito SIIS), `:139-141` (`_lotes`).
- **Escenario:** el cruce con RENAPER y la traducción de respuestas legacy son reglas de dominio dentro de una clase
  `BaseCommand` de 455 líneas: no se pueden reusar ni testear sin el comando, y un cambio en `sincronizar_desde_legacy`
  (p. ej. cómo se filtran las claves `cp-`) no llega acá.
- **Causa raíz:** `sincronizar_desde_legacy` mezcla calcular y guardar.
- **Solución (judo):** partir `sincronizar_desde_legacy` en `aplicar_respuestas_legacy(formulario, definicion) -> bool`
  (puro) + el `save` de siempre; `_poner_foto` pasa a dos líneas. Mover `_cruzar`, conversores y `_norm` a
  `programas/services/renaper_casos.py`; el comando queda en argumentos, lotes y log. `_norm`/`_sin_acentos`/`clave_localidad`
  → una `core.texto.sin_acentos(texto)` (cada uno conserva su post-proceso). `ids_de` desde el selector de B-LIM-28.
- **Tests a agregar:** `programas/tests/test_renaper_casos.py::CruzarTests` (los cuatro campos, `--pisar-existentes`).
- **Verificación:** el comando < 200 líneas; `grep -n "respuestas_desde_legacy" programas/management` vacío.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md` capas: «comandos de management: argumentos, lotes y
  log; la regla vive en `services/` (mismo criterio que las vistas)».

---

### B-LIM-32 · La vista de Cupo arma el alcance y las tres consultas en `get_context_data` (115 líneas)
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — (el contenido viene de SEC-21/SEC-22/PERF-02, resueltos) · **Ola:** 9 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B4-LIM-07
- **Ubicación:** `programas/views/cupo.py:109-223`.
- **Escenario:** la resolución de alcance (admin vs convocatorias visibles vs RN-P13, `:120-144`), las tres consultas y
  el `aggregate` de totales (`:146-205`) son reglas de autorización y lectura de dominio en la capa HTTP, contra «views/
  sin lógica de dominio». Lo mismo que la pantalla necesita lo va a necesitar un export o la API de la app, y hoy habría
  que copiarlo (como pasó con el cálculo de cupo, B-LIM-15).
- **Causa raíz:** el selector nunca se extrajo al arreglar SEC-21/PERF-02.
- **Solución:** `programas/selectors/cupo.py::tablero_cupo(segmento, usuario) -> TableroCupo` (dataclass con
  `beneficiarios_ids_qs`, `pendientes_ids_qs`, `lista_espera_qs`, `conteos`, `puede_editar`); la vista solo pagina
  (`_paginate`, `hidratar_pagina`) y arma el contexto. Mismas consultas, mismo orden.
- **Tests a agregar:** `programas/tests/test_cupo_selector.py::TableroCupoTests.test_regional_no_ve_subsegmentos_ajenos`
  (mover el caso de SEC-21 al selector) + el presupuesto de consultas que ya exista para `becas:cupo_segmento`.
- **Verificación:** `get_context_data` < 30 líneas; `perf_budgets.json` sin cambio.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-auditor.md`: «una vista con `Relevamiento.objects`/
  `Formulario.objects` + reglas de alcance es un selector sin extraer».

---

### B-LIM-33 · `candidatos()` tiene 11 parámetros, 6 de ellos banderas que se combinan
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 9 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B4-LIM-09
- **Ubicación:** `programas/services/proceso_masivo.py:582-711` (docstring de 45 líneas para explicar cómo interactúan
  `solo_enviar`, `filtrar_materias`, `destino`, `excluir_no_enviar`, `solo_incompatibles`, `sin_pausa`).
- **Escenario:** `sin_pausa=False` existe solo para `excluidos_por_pausa` (`:573`); `destino` acopla el selector al
  módulo de envío (`DESTINO_TABLA`); `solo_incompatibles` invierte un filtro del medio. Cada exclusión nueva (BEC-11,
  BEC-21, Cambio 138, alta de oficio) fue un `if` más en la misma función: es el patrón de «condición especial en flujo
  compartido» de la regla 2.
- **Causa raíz:** una sola función devuelve variantes de universo distintas según banderas.
- **Solución (judo):** `base_candidatos(programa=…, convocatoria=…, …)` con lo fijo (estado, sin envío vigente, sin marca de
  oficio, sin conflicto, aprobables) y exclusiones con nombre que se encadenan —`sin_pausa(qs)`, `con_veredicto(qs,
  incompatible=False)`, `solo_habilitados(qs, insumos)`, `sin_excluidos(qs, insumos)`, `sin_guardados_en_tabla(qs)`—;
  `candidatos()` queda como la composición por defecto (misma firma, para no tocar los ocho comandos de una), y
  `excluidos_por_pausa` compone sin `sin_pausa` en vez de pasar una bandera negada.
- **Lo que NO hay que hacer:** reordenar los filtros: el SQL de `_por_incompatibilidad` depende de que la subconsulta
  aparezca una sola vez (PERF-19); verificar con `str(qs.query)` antes/después.
- **Tests a agregar:** `programas/tests/test_candidatos_siis.py::ComposicionTests.test_sql_identico_a_candidatos`.
- **Verificación:** el SQL de `candidatos()` por defecto idéntico byte a byte al de hoy.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md` regla 2: «una función de selección con más de
  tres banderas booleanas se parte en filtros con nombre».

---

### B-LIM-34 · `views/configuracion.py` pasa las 1.000 líneas con cinco ABMs en un solo módulo
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 12 · **Esfuerzo:** M
- **ID de la pasada 1:** B5-LIM-01
- **Ubicación:** `programas/views/configuracion.py:1-1351` (programas SIIS 249-366, segmentos 369-524, subsegmentos
  527-678, coordinadores 681-711, requisitos 714-976, catálogo de preguntas y grupos 979-1330, JSON 1333-1351).
- **Escenario:** cualquier cambio de requisitos o del catálogo obliga a abrir 1.351 líneas donde conviven 16 constantes
  de capacidad, 11 helpers privados compartidos a medias y cinco entidades. Es el archivo de vistas más ancho de Becas y
  aparece en 2 de las 4 aristas vista→vista que todavía tolera `test_arquitectura.ARISTAS_CONOCIDAS`.
- **Causa raíz:** el módulo creció por agregación (#74 → Cambio 58 → 264 → 418 → 445) sin un corte por entidad, a
  diferencia de `services/` y del resto de `views/`, que ya están partidos por producto.
- **Solución:** paquete `programas/views/configuracion/` con un `__init__.py` que re-exporta los nombres públicos (así
  `programas/urls.py:5`, `from programas.views import configuracion as cfg`, y los 6 tests que lo importan no cambian):
  `_comun.py` (CAP_* y `_resumen_errores`, `_casos_con_adjunto`), `programas.py` (~120), `segmentos.py` (~180, incluye
  coordinadores), `subsegmentos.py` (~150), `requisitos.py` (~250, después de B-LIM-36 baja a ~150), `catalogo.py`
  (preguntas + grupos, ~350, después de B-LIM-05 baja a ~220). Mover sin tocar cuerpos; cada archivo < 400 líneas.
- **Lo que NO hay que hacer:** partir y además «limpiar» en el mismo PR: el corte tiene que ser un movimiento puro
  (diff de solo `git mv` + imports) para que la revisión sea mecánica; las reestructuras van en B-LIM-05/04.
- **Tests a agregar:** `programas/tests/test_arquitectura.py::TamanioModulosTests.test_ninguna_vista_pasa_1000_lineas`.
- **Verificación:** la suite de `programas` sin cambios en verde; `ruff check`; `manage.py check`.
- **Regla para no repetirlo:** **control mecánico** · `programas/tests/test_arquitectura.py` · ratchet de tamaño:
  `{ruta: líneas}` de los `.py` de `programas/` que hoy pasan 1.000; falla si aparece uno nuevo o si uno de la lista
  crece más de 50 líneas («`<ruta>` pasa las 1.000 líneas: partilo antes de sumarle»).

---

### B-LIM-35 · La misma regla de activación vive en el form **y** en la vista, con mensajes y defensas distintas
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** G1-09 (oct.) · **Ola:** 12 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B5-LIM-03
- **Ubicación:** «una pregunta activa por destino SIIS»: `programas/forms.py:1488-1501` y
  `programas/views/configuracion.py:1262-1277`. Par Provincia/Localidad: `programas/forms.py:1555-1571` y
  `programas/views/configuracion.py:1280-1287`. Constantes de mensaje exportadas del form a la vista:
  `programas/forms.py:1388-1392` → `configuracion.py:29-31`.
- **Escenario:** el comentario de la vista dice «el mensaje es el del form a propósito: es la misma regla, dicha igual»,
  pero no son iguales (el form: «Ya hay una pregunta activa que alimenta…»; la vista: «No se activó: ya hay una pregunta
  activa…»). Y la defensa ante un `destino_siis` fuera del enum existe solo en la vista (`_etiqueta_destino_siis`,
  `:1233-1246`); el form y `RequisitoNativoForm` hacen `PreguntaGlobal.DestinoSiis(destino).label` directo
  (`forms.py:1498`, `:1547`, `:1629`). La próxima regla que se agregue en un lado no va a estar en el otro.
- **Causa raíz:** la regla no tiene dueño en `services/`; el form es el lugar «natural» y la vista del botón no pasa por
  el form, así que se copió.
- **Solución:** en `programas/services/catalogo.py` (B-LIM-05): `motivo_no_activable(pregunta, *, activo, destino,
  depende_de) -> str | None` y `etiqueta_destino_siis(valor)` (la de la vista, mudada). `PreguntaGlobalForm.clean` y
  `_limpiar_activacion_catalogo` llaman a la función y hacen `add_error(campo, motivo)`; `pregunta_toggle_activo` hace
  `messages.error(motivo)`. Los `MSG_*` se mudan al servicio. Para no cambiar textos visibles, la función devuelve el
  núcleo del mensaje y cada llamador conserva su prefijo actual («No se activó: …»).
- **Tests a agregar:** `programas/tests/test_catalogo_servicio.py::MotivoNoActivableTests` (los tres casos), más
  `test_form_y_boton_usan_el_mismo_motivo` (mismo núcleo en los dos caminos).
- **Verificación:** `grep -n "DestinoSiis(destino).label" programas/` vacío.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md`: «Si una vista importa constantes de mensaje de
  un form (`from programas.forms import MSG_…`), la regla está duplicada: el dueño es un servicio y los dos lo llaman.»

---

### B-LIM-36 · El «nivel» de un requisito (programa/segmento/subsegmento) se despacha con `if/elif` en ocho lugares
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 12 · **Esfuerzo:** M
- **ID de la pasada 1:** B5-LIM-04
- **Ubicación:** `programas/views/configuracion.py:141-149` (`_requisitos_de_lista`), `:160-171`
  (`_puede_ordenar_requisitos`), `:174-215` (tres `_requisitos_*_ajax` casi iguales), `:757-761` (alcance en
  `requisito_crear`), `:778-791` (`_assert_scope_requisito`), `:811-818` y `:836-845` (cadenas de redirect y de panel
  AJAX según `request.POST["scope"]`), `:878-884` y `:905-909` (`requisitos_reordenar`). Una novena definición de «la
  lista» en `programas/forms.py:1644-1654` (`RequisitoNativoForm.hermanos_orden`).
- **Escenario:** «qué lista es», «quién la configura», «qué panel se repinta» y «a dónde se vuelve» son cuatro preguntas
  sobre el mismo concepto respondidas por separado. `_requisitos_de_lista("segmento")` filtra `segmento=…,
  subsegmento__isnull=True`; `hermanos_orden` filtra además `programa_id=…`: si un requisito de segmento llega a tener
  `programa_id` cargado, la pantalla lo muestra en la lista pero el form numera y controla el destino SIIS sobre otra.
  Sumar un cuarto nivel (o cambiar la regla de alcance de uno) toca ocho funciones.
- **Causa raíz:** falta el modelo del ancla; el nivel viaja como string (`nivel`, `scope`) y cada función lo vuelve a
  interpretar.
- **Solución (judo):** `programas/services/requisitos.py`:
  ```python
  @dataclass(frozen=True)
  class Ancla:
      nivel: Literal["programa", "segmento", "subsegmento"]
      objeto: ProgramaSiis | Segmento | Subsegmento
      @classmethod
      def de_requisito(cls, req) -> "Ancla": ...
      def lista(self) -> QuerySet[RequisitoNativo]: ...      # la única definición; la usa también el form
      def assert_alcance(self, user) -> None: ...            # hoy _assert_scope_requisito + ramas de reordenar
      def puede_ordenar(self, user) -> bool: ...
      def url_detalle(self) -> str: ...
  ```
  y en la vista un solo `_panel_ajax(request, ancla, message)` con un dict `nivel → (target, partial, nombre_ctx)`.
  `requisito_crear/editar/eliminar/reordenar` quedan en ~10 líneas cada uno. `hermanos_orden` pasa a `Ancla(...).lista()`.
- **Lo que NO hay que hacer:** resolver el ancla desde `request.POST["scope"]`: el ancla sale del requisito o de la URL;
  `scope` sigue eligiendo solo **qué panel** se repinta (la pantalla de requisitos filtrable usa `reqseg`).
- **Tests a agregar:** `programas/tests/test_requisitos_ancla.py::AnclaTests.test_lista_del_form_y_de_la_pantalla_coinciden`,
  `::test_alcance_por_nivel` (los tres niveles × admin / coordinador / coordinador regional).
- **Verificación:** `grep -c 'nivel == "programa"' programas/views/` = 0; tests de SEC-30 verdes.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md`: «Un mismo string discriminador (`nivel`, `tipo`,
  `scope`) evaluado con `if/elif` en tres o más funciones es un modelo que falta: un objeto con los métodos, no más ramas.»

---

### B-LIM-37 · Aristas vista→vista y nombres privados cruzando módulos que se pueden borrar hoy
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** RED-79 · **Ola:** 12 · **Esfuerzo:** S
- **ID de la pasada 1:** B5-LIM-06
- **Ubicación:** `programas/views/configuracion.py:1180` (`from programas.views.diseno import _operadores`),
  `programas/views/diseno.py:90-93` (alias de identidad `_operadores = constructor.operadores` y
  `DisenoInvalido = constructor.DisenoInvalido`, mantenidos «porque otros módulos los leen»),
  `programas/views/configuracion.py:322-323` (importa `puede_ver_dashboard`/`puede_exportar_dashboard` de
  `views/dashboard_becas`), `:984` (importa el privado `_preguntas_activas` de `services/diseno`),
  `programas/services/validacion_relevamiento.py:12` (importa el privado `_field_para_campo` de `forms_dinamicos`).
- **Escenario:** `test_arquitectura.ARISTAS_CONOCIDAS` (`programas/tests/test_arquitectura.py:82-87`) todavía lista
  `("configuracion", "dashboard_becas")` y `("configuracion", "diseno")`; las dos son imports de una función que no es de
  la vista importada. Los alias de `views/diseno.py` existen solo para sostener esa arista.
- **Causa raíz:** cuando `operadores` se mudó a `services/constructor` quedó el alias en vez de actualizar al consumidor;
  las funciones de permiso del dashboard nunca se mudaron a `services/autorizacion`.
- **Solución:** `configuracion.py` importa `operadores` de `programas.services.constructor`; borrar los dos alias de
  `views/diseno.py:90-93` (y usar `constructor.DisenoInvalido` en `_mutar`); mover `puede_ver_dashboard` y
  `puede_exportar_dashboard` a `programas/services/autorizacion.py` (re-exportados desde `dashboard_becas` si alguien más
  los toma); renombrar `_preguntas_activas` → `preguntas_activas` y `_field_para_campo` → `field_para_campo`. Bajar las
  dos aristas de `ARISTAS_CONOCIDAS` (de 4 a 2). Los imports dentro de funciones de `:322` y `:984` pasan arriba.
- **Tests a agregar:** el propio ratchet: `ARISTAS_CONOCIDAS` sin esas dos entradas.
- **Verificación:** `test_arquitectura` verde con el techo nuevo.
- **Regla para no repetirlo:** **control mecánico** · `programas/tests/test_arquitectura.py` · nuevo test: ningún
  `from programas.<…> import _<nombre>` entre módulos distintos de `programas/` (allowlist vacía al cerrar esta ficha).

---

### B-LIM-38 · El pegamento HTTP del constructor está copiado entre Becas y Dispositivos
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 12 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B5-LIM-07
- **Ubicación:** `programas/views/diseno.py:73-85` y `programas/views/dispositivos_formularios.py:63-75` (`_item`,
  `_json` idénticos; `_item` es además `constructor.item_por_clave`, `programas/services/constructor.py:39-48`);
  `diseno.py:109-123` y `dispositivos_formularios.py:103-117` (`_respuesta`, `_mutar`); parseo del arrastre
  `diseno.py:164-172` = `dispositivos_formularios.py:211-219`; parseo y normalización de la condición (RED-40)
  `diseno.py:257-272` = `dispositivos_formularios.py:293-304`, línea por línea. Y `programas/services/diseno.py:403-405`
  (`_siguiente_orden`) duplica `programas/services/constructor.py:258-260` (`siguiente_orden`) con otra consulta.
- **Escenario:** RED-40 (validar la forma de la condición antes de guardar) se tuvo que aplicar dos veces. El próximo
  arreglo del payload del constructor (por ejemplo, posición negativa o `padre` inexistente) se aplica en una de las dos
  pantallas y la otra queda abierta.
- **Causa raíz:** `services/constructor.py` se extrajo para «los dos dueños del diseño», pero solo con las operaciones; el
  parseo del payload —que es regla del constructor, no de Becas ni de Dispositivos— quedó en cada vista.
- **Solución:** en `services/constructor.py`: `leer_movimiento(payload) -> (clave, clave_padre, posicion)` y
  `leer_condicion(payload) -> dict | None`, que levantan `PayloadInvalido(mensaje)` con los textos actuales; las vistas
  hacen `except PayloadInvalido as e: return error_json(e.mensaje)`. Las vistas usan `constructor.item_por_clave` y un
  único `programas/views/constructor_http.py` (helper compartido como `ajax_utils`, agregado a `EXENTOS`) con
  `mutar_y_responder(request, diseno, mensaje, operacion, contexto)` donde `contexto` es el callable propio de cada
  pantalla. `services/diseno._siguiente_orden` se borra a favor de `constructor.siguiente_orden` (o al revés, dejando una).
- **Tests a agregar:** `programas/tests/test_constructor_payload.py::LeerCondicionTests` (null, sin reglas → None,
  operador desconocido) y `::LeerMovimientoTests`.
- **Verificación:** `grep -n "def _json\|def _item" programas/views/` vacío; los tests del constructor de Becas y de
  `dispositivos_formularios` verdes.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md`: «Cuando una pieza tiene dos dueños (constructor
  de Becas y de Dispositivos), lo que no depende del dueño —incluido el parseo del payload— vive en el servicio compartido;
  cada vista pone solo acceso, URLs y contexto.»

---

### B-LIM-39 · «El diseño sigue al catálogo» está escrito dos veces: `reconciliar` y `items_vigentes`
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 12 · **Esfuerzo:** M
- **ID de la pasada 1:** B5-LIM-08
- **Ubicación:** `programas/services/diseno.py:478-603` (`reconciliar`, persiste) y `:606-680` (`items_vigentes`, en
  memoria). Predicado «sobra»: `:513-515` y `:621-624`; alta de faltantes por pregunta y por requisito: `:529-554` y
  `:637-650`; condiciones con fuente ausente: `:573-579` y `:674-679`.
- **Escenario:** el constructor muestra (y avisa) lo que hace `reconciliar`; el portal y la app sirven lo que calcula
  `items_vigentes`. Si una regla cambia en uno solo —qué cuenta como «sobra», a qué grupo va un faltante, si una regla con
  fuente vacía se anula—, el operador ve en la vista previa un formulario distinto del que recibe la persona hasta que
  alguien vuelve a abrir el constructor. Ya difieren en algo deliberado (los grupos automáticos vacíos se borran en uno y
  se omiten al emitir en el otro), lo que hace difícil ver cuándo una diferencia nueva es un bug.
- **Causa raíz:** el diff contra el catálogo no está separado de su aplicación; cada función lo recalcula a su manera.
- **Solución (judo):** una función pura `_plan_reconciliacion(items, esperadas, esperados, preguntas) -> Plan` con
  `sobrantes`, `faltantes: list[(datos_grupo, campo)]` y `condiciones_rotas(claves_finales)`. `reconciliar` aplica el plan
  con escrituras (más los avisos y `bajas_pendientes`, que son solo suyos); `items_vigentes` lo proyecta en memoria. Sin
  cambio de comportamiento: los dos consumen el mismo diff.
- **Tests a agregar:** `programas/tests/test_diseno_reconciliacion.py::ParidadReconciliarVigentesTests.test_vigentes_igual_a_reconciliar_y_releer`
  (para un catálogo con altas, bajas y condiciones rotas: `claves(items_vigentes(d))` == `claves(items_ordenados(d))`
  después de `reconciliar(d)`, salvo grupos automáticos vacíos).
- **Verificación:** el test de paridad nuevo + los existentes de `reconciliar`/`items_vigentes` (24 citas en
  `programas/tests/`).
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md`: «Una regla que tiene versión que persiste y
  versión en memoria se escribe una vez como plan puro y dos aplicadores; si no, un test de paridad entre las dos.»

---

### B-LIM-40 · `programas/forms.py` tiene 2.525 líneas y mezcla Becas, SIIS y Dispositivos
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 12 · **Esfuerzo:** L
- **ID de la pasada 1:** B5-LIM-09
- **Ubicación:** `programas/forms.py:1-2525`. Bloques: base y widgets `:58-103`; SIIS `:104-450`
  (`ProgramaSiisCreateForm`, `ProgramaSiisIdentificadoresForm`, `DatosSiisForm`); estructura de Becas `:451-611`
  (+ `AsignacionCoordinadorForm` `:1656-1697`); mixins de catálogo `:612-706`; **Dispositivos v1** `:707-1324`
  (`TipoDispositivoForm`, franjas, `DispositivoForm`…, ~620 líneas); `BusquedaCiudadanoDNIForm` `:1325-1345`; catálogo
  `:1346-1655`; convocatorias y relevamientos `:1698-2112`; operación y revisión `:2113-2355` y `:2486-2525`; constructor
  `:2356-2485`.
- **Escenario:** 17 módulos importan de este archivo; ya existen `forms_dispositivos.py`, `forms_reportes.py`,
  `forms_emergencia*.py`… al lado, pero el v1 de Dispositivos sigue acá. Un cambio en el constructor de Becas abre un
  archivo donde dos tercios son de otros productos, y `forms.py:980` necesita un import diferido de `forms_dinamicos` para
  no entrar en ciclo.
- **Causa raíz:** el corte por producto de `CLAUDE.md` («en `programas` el dominio está partido por producto dentro de
  `services/` y `views/`») nunca llegó a los forms.
- **Solución:** paquete `programas/forms/` con `__init__.py` que re-exporta **todos** los nombres públicos actuales
  (`from programas.forms import X` sigue andando en los 17 consumidores):
  `base.py` (`INPUT_CLASS`, `CHECKBOX_CLASS`, `_text_widget`, `_id_siis_widget`, `_catalogo_choices`, ~60),
  `siis.py` (~350), `estructura.py` (segmento, subsegmento, coordinador, ~210), `catalogo.py` (mixins, grupo, pregunta,
  requisito, `MSG_*`, ~400), `dispositivos_v1.py` (`:707-1324`, ~620), `convocatorias.py` (~420), `revision.py` (~290),
  `constructor.py` (~130). Los `forms_*.py` hermanos quedan donde están (mover más es otro PR).
- **Lo que NO hay que hacer:** sacar `INPUT_CLASS` de `programas.forms` sin re-exportarlo ni actualizar las fichas: el
  agente canónico, `.claude/design/componentes/field.md:6,57,81,224`, `.claude/design/arquetipos/formulario.md:46` y
  `scripts/design_audit.py:649` citan `programas/forms.py` como evidencia; el mismo diff actualiza esas citas a
  `programas/forms/base.py` (si no, `check_design_agent.py` falla).
- **Tests a agregar:** `programas/tests/test_arquitectura.py::FormsReexportTests.test_nombres_publicos_de_programas_forms`
  (lista congelada de `dir(programas.forms)` públicos antes del corte).
- **Verificación:** suite completa verde; `check_design_agent.py --base origin/development`; `ruff`.
- **Regla para no repetirlo:** **control mecánico** · el ratchet de tamaño de B-LIM-34 cubre `forms*.py` también.

---

### B-LIM-41 · Dos caminos para crear un caso (app de campo y link público) con el mismo esqueleto y reglas que ya divergen
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo; relacionado con RED-05 y RED-10 (los dos caminos ya tienen tests y presupuestos por separado) · **Ola:** 13 · **Esfuerzo:** L
- **ID de la pasada 1:** B6-LIM-02
- **Ubicación:** app: `programas/api/views.py:746-802` + `_completar_alta` `:422-457`; link:
  `programas/services/inscripcion_publica.py:99-132` (`crear_formulario_publico`), `:135-209`
  (`_insertar_formulario`), `:212-249` (`_completar_envio`). Tercer camino fuera del alcance:
  `programas/services/alta_de_oficio.py:40,216`.
- **Escenario:** los dos hacen, en el mismo orden, *lock del relevamiento → idempotencia por `client_uuid` →
  disponibilidad → cupo → duplicado → insert → (fuera del lock, idempotente) completar → `resolver_ciudadano_offline`*.
  Lo que difiere está escrito distinto en cada lado y ya se separó:
  - **Idempotencia:** la app busca la clave en **toda** la base (`formulario_por_client_uuid_global`, K4, con
    chequeo de «mismo alta»); el link la busca **solo en el relevamiento** (`formulario_por_client_uuid(rel, …)`,
    `inscripcion_publica.py:122`). Hoy no muerde porque el link genera el UUID en el servidor, pero la regla K4 se
    escribió una vez y el otro camino no la heredó.
  - **Cupo:** `bloqueado.formularios.count() >= bloqueado.cupo_maximo` (`views.py:770`) y
    `rel.formularios.count() >= rel.cupo_maximo` (`inscripcion_publica.py:155`), mientras el modelo ya tiene
    `Relevamiento.cupo_completo` (`programas/models/__init__.py:3378`), que usa el portal fuera del lock
    (`portal/services/inscripcion.py:83`). Tres escrituras de la misma regla.
  - **Disponibilidad:** `campo.evaluar_captura` (app) frente a `rel.estado != EN_CURSO or not habilitado_en(now)`
    (`inscripcion_publica.py:153`) frente a `relevamiento_disponible` (`portal/services/inscripcion.py:77-84`).
  - **Identidad acreditada:** la app la recalcula en el servidor (`_actualizar_validacion_identidad`); el link la
    escribe inline en el `create` (`inscripcion_publica.py:165-208`, `validado_renaper=bool(es_validado and nombre
    and apellido)`), con su propia copia de «qué orígenes acreditan» (ver B-LIM-42).
  Una corrección futura en uno de los caminos (otra K4, otro Cambio 91) se va a hacer en uno solo, como ya pasó.
- **Causa raíz:** el link (#295) copió el patrón de la API («mismo patrón que la API de campo», dice su docstring
  `:9`) en vez de extraerlo; las reglas que vinieron después se aplicaron caso por caso.
- **Solución (preserva lógica):** jugada de judo — un único servicio de alta con política por canal.
  `programas/services/alta_caso.py`:
  ```python
  @dataclass(frozen=True)
  class PoliticaAlta:
      evaluar_disponibilidad: Callable[[Relevamiento, datetime | None], Decision]  # app: campo.evaluar_captura; link: _disponible_link
      chequear_duplicado: Callable[[Relevamiento, str], DuplicadoDecision]      # app: marca conflicto; link: lock convocatoria + raise
      chequear_padron: Callable[[Relevamiento, str, str], bool] | None          # link: esta_habilitado; app: None
      idempotencia_global: bool                                                 # app True (K4); link False (hoy)

  def reservar_alta(rel, *, client_uuid, dni, politica, insertar) -> ResultadoAlta: ...  # todo lo que va bajo el lock
  ```
  `insertar` es el callable propio de cada canal (`serializer.save(**extras)` o el `Formulario.objects.create` de
  `_insertar_formulario`), así los campos que escribe cada uno no cambian. El cupo pasa a una sola función
  `cupo_lleno_bajo_lock(rel)` (la cuenta fresca que hoy se escribe dos veces) junto a `Relevamiento.cupo_completo`.
  `completar_*` queda por canal (los adjuntos del link y la revisión G1-05 de la app son genuinamente distintos), pero
  los dos terminan en el mismo `resolver_ciudadano_offline`. La diferencia de idempotencia queda **explícita** en
  `idempotencia_global`; unificarla es `DECISIÓN CLIENTE: global también en el link` (sin efecto práctico hoy).
- **Lo que NO hay que hacer:** unificar las reglas de duplicado: la app **marca** (`conflicto_duplicado`) y el link
  **rechaza** por convocatoria (RN-P5). Son decisiones de producto distintas; lo que se unifica es el esqueleto, no
  la regla. Tampoco llevar `_completar_envio` adentro del lock.
- **Tests a agregar:** `programas/tests/test_alta_caso.py::PoliticasTests.test_app_y_link_comparten_el_orden_de_chequeos`
  (spy sobre la política, afirma el orden), `.test_cupo_lleno_igual_en_los_dos_canales`.
- **Verificación:** `portal.tests.test_inscripcion_envio`, `programas.tests.test_becas_api`,
  `programas.tests.test_candados_concurrencia` en verde; presupuestos `inscripcion_publica_paso2` (46/10) y
  `becas_api_alta` (31/1) sin subir.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md`, tabla de helpers
  canónicos: «Crear un caso (`Formulario`) → `programas.services.alta_caso.reservar_alta` con la política del canal;
  un `Formulario.objects.create` fuera de ahí es duplicado».

---

### B-LIM-42 · «Qué origen acredita identidad» está escrito en seis lugares aunque existe la constante canónica
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo; mismo patrón que RED-48 (una regla, varias implementaciones) · **Ola:** 13 · **Esfuerzo:** S
- **ID de la pasada 1:** B6-LIM-03
- **Ubicación:** canónica: `programas/services/identidad.py:30-35` (`ORIGEN_*`, `ORIGENES_ACREDITADOS`). Copias:
  `portal/forms/inscripcion.py:92` (`not in ("personas", "padron")`), `programas/services/inscripcion_publica.py:141-142`
  (`origen in ("personas", "padron")`), `programas/api/views.py:437` (`in ("padron", "personas")`),
  `programas/api/views.py:78-81` (`ORIGEN_VALIDACION_POR_FUENTE`), `:343` y `:350` (alias `scan/escaneo/dni_scan`,
  `personas/gran_base` sueltos en el `if`), `portal/views/inscripcion.py:217` (`"manual"` literal),
  `programas/services/becas.py:405` (la única que usa `ORIGENES_ACREDITADOS`).
- **Escenario:** sumar un origen acreditado (p. ej. un futuro «RENAPER directo», o promover `scan` como acreditado
  en el link) exige encontrar las seis copias; olvidarse una deja al link pidiendo de nuevo nombre y apellido
  (`es_manual`) mientras el caso queda validado, o al revés.
- **Causa raíz:** `ORIGENES_ACREDITADOS` llegó con SIIS-08, después de que el form, la ingesta y la API ya tenían su
  tupla literal; nadie las migró.
- **Solución:** en `identidad.py` agregar `ALIAS_ORIGEN = {"scan": ORIGEN_SCAN, "escaneo": ORIGEN_SCAN, "dni_scan":
  ORIGEN_SCAN, "gran_base": ORIGEN_PERSONAS}`, `normalizar_origen(valor) -> str` y `acredita(origen) -> bool`
  (`origen in ORIGENES_ACREDITADOS`). Reemplazar las seis copias por esas funciones/constantes; los valores
  persistidos (`"padron"`, `"personas"`, `"manual"`) no cambian.
- **Lo que NO hay que hacer:** meter `scan` en `ORIGENES_ACREDITADOS`: en la app acredita (D-24) pero
  `_anotar_identidad_acreditada` (SIIS-08) **no** debe compararlo contra el legajo. Son dos preguntas
  («¿queda validado?» y «¿es una fuente oficial?»): dos funciones, no una tupla.
- **Tests a agregar:** `programas/tests/test_padron_identidad.py::OrigenesTests.test_los_alias_se_normalizan`,
  `.test_ningun_modulo_escribe_la_tupla_de_origenes` (grep AST de la tupla literal fuera de `identidad.py`).
- **Verificación:** `grep -rn '"personas", "padron"\|"padron", "personas"' --include=*.py programas portal` → solo
  `identidad.py`.
- **Regla para no repetirlo:** **control mecánico** · test del punto anterior en `programas/tests/test_arquitectura.py`.

---

### B-LIM-43 · `FormularioSerializer.validate` hace el dominio del alta y le pasa resultados a la vista por `self.context`
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo; G1-05 (la regla), RED-11 (contrato); Origen oct.: RED-12 (abierto: contrato `definicion_formulario` de dos repos) · **Ola:** 13 · **Esfuerzo:** M
- **ID de la pasada 1:** B6-LIM-04
- **Ubicación:** `programas/api/serializers.py:230-354` (`validate`, 125 líneas): arma la foto
  (`:241-243`, `foto_definicion` → `definicion_formulario`, consultas al catálogo), corre el motor de condiciones
  (`:247`) y **otra vez** (`:319`), traduce respuestas a `data` y columnas fijas (`:249-259`), consulta `Ciudadano`
  (`:300-302`). Canal lateral: `self.context["reloj_adelantado"]` (`:238`) y `self.context["foto_definicion"]`
  (`:243`), que lee la vista (`views.py:738`, `:798`, `:801`). Tercera pasada del motor: `campo.revisar_carga`
  (`programas/services/campo.py:224`).
- **Escenario:** el contrato real entre serializer y vista es implícito: si alguien renombra la clave del contexto o
  valida sin `context={"relevamiento": …}` (como hace `FormularioSerializer(existente)` para responder), la vista
  recibe `None` y `_completar_alta` vuelve a pedir la definición entera (`sincronizar_desde_legacy` →
  `foto_definicion(relevamiento)`) **sin error**: más consultas y una foto distinta de la validada. Las condiciones
  se evalúan tres veces por alta con la misma foto y las mismas respuestas.
- **Causa raíz:** el serializer es el único lugar con `relevamiento` a mano antes del lock, así que se le fue
  sumando todo lo que «había que saber antes de guardar».
- **Solución (no cambia el contrato):** `programas/services/alta_campo.py` (o el de B-LIM-06) expone
  `preparar_alta(attrs, relevamiento, instancia=None) -> AltaPreparada` (dataclass: `attrs`, `foto`, `ocultos`,
  `reloj_adelantado`). `FormularioSerializer.validate` queda en: llamar a `preparar_alta`, traducir sus
  `ErrorDeAlta(campo, mensaje, legible: bool)` a `serializers.ValidationError` / `rechazo_legible` con **las mismas
  claves y textos de hoy**, guardar el resultado en `self.alta_preparada` (atributo tipado, no `context`). La vista
  lee `serializer.alta_preparada.foto` y `.reloj_adelantado`. `revisar_carga` recibe `ocultos` ya calculados
  (parámetro opcional; sin él calcula como hoy, para los otros llamadores).
- **Lo que NO hay que hacer:** cambiar la forma de los 400 (`{campo: [...]}` + `code: VALIDACION`, y
  `non_field_errors` en los de DNI/fecha): la app los parsea por regex (`becasApi.js`). Tampoco mover la validación a
  la vista: el esquema OpenAPI (RED-37) la toma del serializer.
- **Tests a agregar:** `programas/tests/test_alta_campo.py::PrepararAltaTests.test_una_sola_pasada_del_motor`
  (mock de `condiciones.aplicar`, `assert call_count == 1` por alta),
  `.test_serializer_sin_relevamiento_no_inventa_foto`.
- **Verificación:** `programas.tests.test_becas_api_contrato` (sin modificarlo) y `core.tests.test_api_schema_contrato`
  en verde; `becas_api_alta` igual o menor en `perf_budgets.json`.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md`, sección «Bordes»:
  «Un serializer valida forma; no consulta modelos ajenos ni escribe en `self.context` para que lo lea la vista. Lo
  que la vista necesita del `validate` viaja en un atributo tipado del serializer».

---

### B-LIM-44 · Traducir respuestas a columnas fijas e identidad está escrito tres veces, con la misma regla de default copiada
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 13 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B6-LIM-06
- **Ubicación:** columnas fijas desde `fijos`: `programas/api/serializers.py:253-258`, `programas/services/campo.py:290-294`
  (las dos con `None if columna.endswith("fecha_nacimiento") else ""`), `programas/services/inscripcion_publica.py:176-184`
  (la misma lista de siete columnas escrita a mano en el `create`, con `parse_date` propio para la fecha). Volcado de
  `IDENTIDAD` a respuestas por clave: `programas/services/respuestas.py:192-196`, `:228-231` y
  `programas/api/views.py:443-448` (el camino inverso, inline en la vista).
- **Escenario:** `COLUMNAS_FIJAS` es la fuente del mapeo, pero el *default* por columna y la conversión de fecha no
  están en ella: si se agrega una columna fija de fecha (`apoderado_*` ya tiene una), hay que acordarse de tres
  `endswith("fecha_nacimiento")`/`parse_date` distintos; en el link, una columna nueva en `COLUMNAS_FIJAS` **no** se
  escribe nunca, porque `_insertar_formulario` lista las siete a mano.
- **Causa raíz:** `legacy_desde_respuestas` devuelve un dict «flojo» (`fijos`) y cada llamador lo completa con su
  propia idea de vacío.
- **Solución:** en `respuestas.py`, `columnas_fijas_desde(fijos) -> dict[str, Any]` que devuelve **las siete** con su
  default (`None` para fechas, `""` el resto) y la fecha ya `parse_date`-ada; y `volcar_identidad(respuestas,
  definicion, identidad) -> dict` para el camino inverso. Los tres llamadores pasan a
  `Formulario.objects.create(..., **columnas_fijas_desde(fijos))`, `for columna, valor in
  columnas_fijas_desde(fijos).items(): ...` y `formulario.respuestas.update(volcar_identidad(...))`.
- **Lo que NO hay que hacer:** que el serializer deje de pasar cada valor por `self.fields[columna].run_validation`
  (`serializers.py:256`): ahí está la validación de largo y tipo de la columna; el helper solo unifica el default.
- **Tests a agregar:** `programas/tests/test_respuestas.py::ColumnasFijasTests.test_devuelve_todas_las_columnas_con_su_default`,
  `.test_una_columna_nueva_llega_al_link_y_a_la_app`.
- **Verificación:** `grep -n 'endswith("fecha_nacimiento")' -r programas` → 1 resultado (en `respuestas.py`).
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md`, tabla de helpers canónicos: «Columnas fijas del caso
  desde respuestas → `respuestas.columnas_fijas_desde`».

---

### B-LIM-45 · `autorizacion.py` repite la precedencia de roles en cinco funciones, en dos órdenes distintos, y mezcla cuatro responsabilidades
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) — la divergencia de orden; PLAUSIBLE su efecto (requiere un · **Eje:** LIM · **Origen:** nuevo; relacionado con RED-56 (falla cerrado) y SEC-30 · **Ola:** 13 · **Esfuerzo:** M
- **ID de la pasada 1:** B6-LIM-07
- **Ubicación:** `programas/services/autorizacion.py`: cadena admin → referente → regional → coordinador en
  `puede_gestionar_segmento` (`:212-224`), `segmentos_visibles` (`:268-276`), `aviso_sin_segmentos_becas`
  (`:291-317`), `segmentos_para_gestion_territoriales` (`:438-443`) y `_alcance_de_capacidades` (`:660-676`, la única
  que el propio módulo declara como «la precedencia»); en orden **regional primero**: `subsegmentos_visibles`
  (`:332`) y `convocatorias_visibles` (`:340`). El comentario `:634-637` documenta la inconsistencia en vez de
  resolverla. Cada `es_*_becas` vuelve a llamar a `es_admin_becas` (`:156`, `:163`, `:174`): una pregunta de alcance
  hace hasta 6-8 evaluaciones de `rbac.puede`. Responsabilidades mezcladas: alcance (`:39-415`), candidatos para
  combos (`:528-627`), choque de roles del ABM de usuarios (`:630-753`), territoriales en lote (`:438-508`).
  `get_segmentos_coordinador` y `coordinador_gestiona_segmento` viven en `becas.py:301-320` aunque solo los usa este
  módulo.
- **Escenario:** un usuario que quedó con Referente y Coordinador Regional (dato previo al Cambio 333, o un rol
  editado por el admin de Django) ve los segmentos como Referente y las convocatorias como Regional: abre una
  convocatoria y su relevamiento le da 403 (`_assert_alcance` combina las dos). Agregar un quinto alcance obliga a
  tocar siete funciones.
- **Causa raíz:** el alcance se modela como funciones booleanas sueltas (`es_referente`, `es_coordinador_regional`…)
  en vez de un valor; cada consumidor reconstruye la precedencia.
- **Solución (jugada de judo):** `alcance_becas(user, programa=None) -> Alcance | None` (enum con los cuatro valores
  que ya existen en `ALCANCE_*`), calculado **una vez** con la misma precedencia de `_alcance_de_capacidades`
  (evaluando las capacidades del usuario con `rbac.puede(..., programa=programa)`) y memoizado en el request como
  `programa_becas`. Las cinco funciones pasan a despachar por tabla:
  `SEGMENTOS_POR_ALCANCE = {ADMIN: lambda u: Segmento.objects.all(), REFERENTE: _segmentos_referente, ...}`.
  Partir el archivo en paquete `programas/services/autorizacion/` (`alcance.py`, `candidatos.py`,
  `roles_que_se_pisan.py`, `territoriales.py`) con `__init__.py` que reexporta todos los nombres públicos actuales:
  ningún import del repo cambia. Mudar los dos helpers de `becas.py` a `alcance.py` (con reexport en `becas.py`).
  **DECISIÓN CLIENTE:** para el usuario inválido con dos alcances, la precedencia única cambia lo que ve en
  `subsegmentos_visibles`/`convocatorias_visibles`; default propuesto: la de `_alcance_de_capacidades` (Referente
  gana), que es la que ya aplica `segmentos_visibles`.
- **Lo que NO hay que hacer:** globalizar `programa.configurar` ni tocar `CAPS_ADMIN_*` (README §8.1); no cambiar el
  fallo cerrado de `_programa_o_denegar` (RED-56) ni el `return False` sin programa de `puede_validar_identidad`.
- **Tests a agregar:** `programas/tests/test_becas_rbac.py::AlcanceUnicoTests.test_las_cinco_funciones_usan_la_misma_precedencia`
  (parametrizado por los cuatro alcances + combinación inválida), `.test_alcance_se_calcula_una_vez_por_request`
  (`assertNumQueries`). Verificar por mutación: invertir dos ramas de la tabla y ver el test rojo.
- **Verificación:** `manage.py test programas.tests.test_becas_rbac users` en verde; presupuestos de las bandejas de
  Becas en `perf_budgets.json` iguales o menores.
- **Regla para no repetirlo:** **skill** · `.claude/skills/seguridad-django/` (RBAC de Becas): «El alcance de Becas
  se pregunta con `alcance_becas(user)` y se despacha por tabla; no se encadenan `es_referente_becas`/
  `es_coordinador_regional_becas` en una función nueva».

---

### B-FE-01 · Mapeos de estado → etiqueta/tono y decisiones de dominio escritos en templates
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** nuevo (SIIS-17/18 tocan el mismo dato) · **Ola:** 11 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B1-FE-01
- **Ubicación:** `revision/_detalle/_siis_envio.html:13-25` (estado de `EnvioSIIS` → 6 ramas etiqueta/tono), `revision/_detalle/_siis_resultado.html:11-17` y `:95-101` (estado de `ValidacionSIS` → etiqueta, dos copias en el mismo archivo), `revision/_detalle/_identidad.html:77-125` (ramas por `origen_validacion` con literales `"padron"`/`"scan"`), `revision/_detalle/_conflicto_duplicado.html:17,23` (el template decide el valor `conservar_previo`/`conservar_actual`).
- **Escenario:** un estado nuevo de SIIS (p. ej. reintento) se muestra en blanco sin error; `selectors/revision.py:49-115` ya tiene un mapeo de tono para otra parte del mismo dato, así que hay dos tablas que pueden contradecirse.
- **Causa raíz:** la presentación de estados se escribió donde se usó.
- **Solución:** extender el mapeo existente de `selectors/revision.py` (o `get_<estado>_display` + un dict de tono junto a los choices) y pasar `etiqueta`/`tono` ya resueltos; el template solo pinta. Los literales de `origen_validacion` se comparan contra constantes expuestas en el contexto. Los valores de decisión del duplicado los provee la vista. Texto y clases resultantes idénticos (snapshots).
- **Lo que NO hay que hacer:** cambiar textos ni clases de los badges; agregar consultas.
- **Tests a agregar:** test del mapeo por cada estado del enum (incluido uno desconocido → etiqueta por defecto).
- **Verificación:** snapshots de `test_becas_revision_detalle_html.py` sin regenerar.
- **Regla para no repetirlo:** agente · `rubricas/codigo-limpio.md` · «un `{% if x.estado == '...' %}` con más de dos ramas en un template es un mapeo: va al selector».

---

### B-FE-02 · Regla de «sexo de solo lectura» divergente: el template ofrece editar y la vista siempre rechaza
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** nuevo · **Ola:** 5 · **Esfuerzo:** S
- **ID de la pasada 1:** B1-FE-02
- **Ubicación:** `programas/templates/programas/becas/revision/_detalle/_identidad.html:35` (solo lectura si `validado_renaper and not identidad_forzada and genero`) vs `programas/views/revision.py:906-908` (`formulario_actualizar_genero` rechaza si `validado_renaper and ciudadano.genero`, sin mirar `identidad_forzada`).
- **Escenario:** caso con identidad forzada y RENAPER validado con género cargado: el revisor ve el selector de sexo, lo cambia, envía, y recibe siempre «La identidad ya fue validada; el sexo es de solo lectura.». No hay forma de completar la acción que la pantalla ofrece.
- **Causa raíz:** la misma regla escrita dos veces, en capas distintas, y una cambió (al introducir `identidad_forzada`) sin la otra.
- **Solución:** una sola función `sexo_editable(formulario)` en el servicio de B-LIM-01 (o propiedad del modelo), usada por la vista para rechazar y por el selector para pasar `sexo_editable` al template. Qué regla gana (con o sin `identidad_forzada`) lo decide el PM; el arreglo mínimo es que ambas capas digan lo mismo.
- **Lo que NO hay que hacer:** «arreglar» solo el template ocultando el form sin decidir la regla; tocar el snapshot sin registrar el cambio.
- **Tests a agregar:** test con `identidad_forzada=True`, `validado_renaper=True`, `genero` cargado: lo que muestra el detalle coincide con lo que acepta el POST. Verificar por mutación.
- **Verificación:** el test nuevo; snapshots regenerados solo si cambia el caso forzado, con el diff revisado.
- **Regla para no repetirlo:** agente · `rubricas/codigo-limpio.md` · «una condición de permiso/editable que aparece en vista y template se calcula una vez y se pasa como flag».

---

### B-FE-03 · JS inline del detalle de revisión duplicado (toggles, selects dependientes, modales, guarda de doble envío)
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** nuevo · **Ola:** 11 · **Esfuerzo:** M
- **ID de la pasada 1:** B1-FE-03
- **Ubicación:** `revision/_detalle/_scripts.html` (258 líneas): toggles idénticos L23-31 y L48-57; `cargarLocalidades` L66-82 y `cargarFunciones` L98-114 (misma función); tres copias de `mostrar`/`ocultar`/`modalAccesible` más un visor de imagen con su propio Escape; guarda de doble envío `tomarEnvio` L157-169 repetida en `_conflicto_duplicado.html:30-80` (`enviando`, `form.dataset.enviando`, `ESPERA_CONFIRMAR_MS`) y en `config/proceso_masivo.html`; valores de template interpolados en JS (L64, L84-85, L94).
- **Escenario:** el bloque no se cachea (va en cada render del detalle, la pantalla más usada del revisor) y un arreglo en la guarda de doble envío hay que hacerlo en tres lugares; ya divergen en el tiempo de espera.
- **Causa raíz:** JS escrito por pantalla dentro del template, sin módulo estático del detalle.
- **Solución:** `static/custom/js/becas-revision.js` cargado con `defer`, configurado por `data-*` (URLs de localidades/funciones, ids de modal); una función `toggleSeccion`, una `cargarDependiente(select, url, destino)`, un `abrirModal/cerrarModal` local al archivo, y una guarda de doble envío compartida con `proceso_masivo` en el mismo archivo estático. El DOM no cambia; el snapshot cambia solo en el bloque `<script>` (regenerar y revisar que el único diff sea ese).
- **Lo que NO hay que hacer:** promover modales/confirmaciones a `components/` (descartado en §8); cambiar comportamiento visible ni tiempos.
- **Tests a agregar:** ninguno de Python; verificación manual o Playwright en testing (propuesta, no se corre sola).
- **Verificación:** `design_audit.py --ratchet` 0 nuevos; `compile_templates.py` 0; snapshots regenerados con diff limitado al `<script>`.
- **Regla para no repetirlo:** control mecánico · `design_audit.py` · bloque `<script>` inline de más de N líneas en templates de `programas/` = hallazgo con ratchet.

---

### B-FE-04 · Formulario «Nuevo relevamiento» triplicado con divergencias
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** nuevo · **Ola:** 11 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B1-FE-04
- **Ubicación:** `relevamientos/convocatoria_detail.html:263-371` (con `data-ajax`, placeholders `data-error`, convocatoria oculta), `relevamientos/relevamiento_list.html:153-247` (sin `data-ajax`, falta `data-error` en varios campos, alerta `sin_convocatorias`), `relevamientos/relevamiento_form.html:1-76` (tercera variante con `components/_field.html`; alerta `sin_convocatorias` repetida L18-25 vs `relevamiento_list.html:171-178`).
- **Escenario:** un campo nuevo del relevamiento (o el cambio de validación del solapamiento) hay que cargarlo tres veces; ya hoy un error de validación se muestra inline en una y no en otra.
- **Causa raíz:** el modal se copió a cada pantalla de origen.
- **Solución:** un parcial `relevamientos/_relevamiento_crear_campos.html` con parámetros (`ajax`, `convocatoria_fija`) que reproduzca byte a byte el markup de cada pantalla; la alerta `sin_convocatorias` a su propio parcial. Si alguna divergencia es un bug (falta de `data-error`), se corrige en un PR aparte, declarado.
- **Lo que NO hay que hacer:** cambiar clases o estructura visible; uniformar `data-ajax` sin decidirlo.
- **Tests a agregar:** test de render de las tres pantallas comparando el bloque del form antes/después.
- **Verificación:** `compile_templates.py --bloques` 0; `design_audit.py --ratchet` 0 nuevos.
- **Regla para no repetirlo:** agente · `.claude/agents/chaco-design-system.md` (ficha del módulo) · «el form de alta de relevamiento vive en un parcial; no se copia».

---

### B-FE-05 · Las etiquetas de canal y estado se reescriben en cinco lugares y la exportación dice otra cosa que la pantalla
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** — · **Ola:** 4 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B2-FE-01
- **Ubicación:** etiqueta del modelo `Relevamiento.Tipo.PUBLICO = "Formulario público"` (`programas/models/__init__.py:3128`) y `Formulario.Estado.ENVIADO = "Enviado"` (`:3923`). Reescrituras: `programas/services/dashboard_becas.py:553` y `:1393` («Link público»); `programas/templates/programas/becas/config/_dashboard_panel.html:112`; `static/custom/js/becas-dashboard.js:497-498` (`nombreEstado`, `nombreCanal`) y `:136` (compara contra la etiqueta **traducida** `'Formulario público'`). Sin reescribir: `_con_choices` (`dashboard_becas.py:626-627`) → `bloques_exportacion` (`:1201-1208`).
- **Escenario:** en pantalla, la tarjeta de estados dice «Pendientes de revisión» y «Canal: Link público»; el CSV/XLSX del mismo bloque dice «Enviado» y «Formulario público» (y la hoja «Resumen» del mismo libro dice «Pendientes de revisión», `:1190`). Si alguien cambia la etiqueta del choice, el `<select>` de relevamientos del JS (`:136`) deja de reconocer los públicos sin error: compara el texto de display.
- **Causa raíz:** la etiqueta de presentación del dominio no tiene un único dueño; el servidor manda el display del modelo y cada consumidor lo «corrige».
- **Solución:** el servicio manda la etiqueta final: `_con_choices(conteo, choices, etiquetas=ETIQUETAS_DASHBOARD)` con `ETIQUETAS_DASHBOARD = {"PUBLICO": "Link público", "ENVIADO": "Pendientes de revisión"}` en `dashboard_becas`, usado también por `_texto_alcance` y `_relevamientos_de`; `relevamientos_de` manda además `tipo_clave` (`"PUBLICO"`) y el JS compara contra la clave. El JS deja de reescribir (`nombreEstado`/`nombreCanal` → `f.etiqueta`) y el template toma la etiqueta de la misma constante. Así pantalla y export coinciden con lo que hoy muestra la pantalla. `DECISIÓN CLIENTE:` si el CSV debe pasar a «Link público»/«Pendientes de revisión» (por defecto sí: es lo que ve el usuario).
- **Lo que NO hay que hacer:** cambiar el `label` del choice en el modelo: es una migración de estado y cambia textos en todo el backoffice.
- **Tests a agregar:** `programas/tests/test_dashboard_becas.py::EtiquetasTests.test_export_y_json_usan_las_mismas_etiquetas`.
- **Verificación:** `grep -n "Formulario público\|'PUBLICO'\|'ENVIADO'" static/custom/js/becas-dashboard.js` vacío.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-frontend.md` · «El JS no compara contra textos de display ni renombra etiquetas del dominio: compara claves y pinta la etiqueta que manda el servidor».

---

### B-FE-06 · El editor de condiciones está copiado entero dentro de un atributo `x-data`, y ya divergió
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** — · **Ola:** 12 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B5-FE-01
- **Ubicación:** `programas/templates/programas/becas/config/pregunta_list.html:9-112` (~100 líneas de JS dentro del
  atributo `x-data`: `operadoresDe`, `etiquetaOp`, `necesitaValor`, `conLista`, `tipoInputR`, `grupoCondicionJson`) frente
  a `static/custom/js/nodo-constructor.js:589-645` (`operadoresDe`, `etiquetaOp`, `necesitaValor`, `conLista`,
  `tipoInput`, `guardarCondicion`).
- **Escenario:** las dos copias serializan la condición distinto. En el constructor, una regla sin valor se rechaza con
  «La regla N necesita un valor.» (`nodo-constructor.js:633-635`); en el editor de la condición por defecto del grupo,
  `grupoCondicionJson` saltea en silencio la regla vacía (`pregunta_list.html:75`) y no chequea el valor faltante: el
  operador guarda «edad <» sin número, el servidor lo rechaza con un mensaje genérico de `validar_condicion_defecto` y el
  modal no le marca la regla. El código en un atributo HTML no se puede testear con el harness de Node
  (`core/tests/js_harness`) ni lo ve ningún linter.
- **Causa raíz:** el editor nació en el constructor (Alpine en un `.js`) y la condición por defecto del grupo (#341) lo
  necesitó en otra pantalla; se copió en vez de extraerse.
- **Solución:** `static/custom/js/nodo-editor-condicion.js` con funciones puras sobre el vocabulario de `operadores()`:
  `operadoresDe(fuente, actual, vocab)`, `tipoInput(fuente, op, vocab)`, `serializar(reglas, modo, vocab) -> {condicion,
  error}`. El componente del constructor y el de `pregunta_list.html` delegan en él (el `x-data` de la página queda con
  estado y llamadas). `serializar` adopta la regla del constructor (rechaza la regla incompleta) para los dos, con el mismo
  texto de error que hoy muestra el constructor.
- **Lo que NO hay que hacer:** mover el `x-data` a `components/` o convertirlo en un componente global: es dominio Becas
  (§8.1). Tampoco duplicar el vocabulario de operadores en JS: sigue viniendo de `constructor.operadores()` por
  `json_script`.
- **Tests a agregar:** `programas/tests/js/editor_condicion.cjs` + `programas/tests/test_editor_condicion_js.py`
  (regla vacía, lista con edades, número) con `requiere_node`.
- **Verificación:** `grep -c "necesitaValor" programas/templates/` = 0.
- **Regla para no repetirlo:** **control mecánico** · `scripts/design_audit.py`: regla nueva `XDATA-LARGO`: un atributo
  `x-data` de más de 30 líneas o que define más de 5 métodos → «la lógica va a un `.js` de `static/custom/js/`; el
  `x-data` queda con estado y llamadas». Ratchet: no sube.

---

### B-FE-07 · La paridad Python↔JS cubre el motor de condiciones, pero no el filtro por canal, que tiene dos copias JS
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** #895 (paridad del motor); Origen oct.: RED-38 (abierto: tres motores de condiciones sin vectores compartidos) · **Ola:** 12 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B5-FE-02
- **Ubicación:** servidor: `programas/services/diseno.py:716-731` (`items_planos`, con exclusión en cascada del padre),
  `programas/services/condiciones.py:293-326` (`fuentes_fuera_del_canal`, BEC-04), `programas/models/__init__.py:4887-4891`
  (`se_pide_en`). Navegador: `static/custom/js/nodo-constructor.js:58-65` (`canalesServidos`) y `:440-445` (filtro de
  `renderPreview`), dos formas distintas de lo mismo en el mismo archivo; `:74-99` (`fuentesPara`, espejo de BEC-04).
  Red actual: `programas/tests/test_condiciones_paridad.py` + `programas/tests/js/paridad_condiciones.cjs` comparan solo
  `aplicar`.
- **Escenario:** las copias ya no coinciden en un borde: con `canal` vacío, el servidor excluye el ítem
  (`se_pide_en` → `"" in (AMBOS, canal)` es falso) y `renderPreview` también, pero `canalesServidos` lo trata como
  `'ambos'` (`it.canal || 'ambos'`), así que el editor ofrece como fuente un campo que el servidor después rechaza por
  BEC-04 al guardar. Hoy `canal_efectivo` casi nunca es vacío (los forms lo fuerzan a `AMBOS`), pero un restore o un
  `update()` lo deja así, y nada avisaría. El motor (`nodo-condiciones.js`) está bien cubierto: la tabla de #895 recorre
  todos los operadores y modos; las diferencias de coerción que quedan (`str(True)` vs `String(true)`, `int("1_000")`)
  no son alcanzables desde el DOM, donde todo valor es texto.
- **Causa raíz:** cuando se escribió la paridad se espejó el evaluador, no la preparación de su entrada; el filtro por
  canal se reescribió en cada lugar que lo necesitó.
- **Solución:** sumar a `nodo-condiciones.js` `itemsDelCanal(items, canal)` (espejo exacto de `items_planos`, con la
  semántica de `se_pide_en`) y `fuentesFueraDelCanal(itemsDelCanal, …)`; `renderPreview`, `canalesServidos` y
  `fuentesPara` pasan a usarlos (una sola copia JS). Extender `condiciones_paridad.json` con una columna `canal` por
  variante y que `paridad_condiciones.cjs` corra `aplicar(itemsDelCanal(items, canal), …)` contra
  `aplicar(items_planos(items, canal), …)`.
- **Tests a agregar:** casos nuevos en `programas/tests/condiciones_paridad.json` (padre solo-app con hijo «ambos»,
  canal vacío) y `programas/tests/test_condiciones_paridad.py::NavegadorTests.test_filtro_por_canal_igual_al_servidor`.
- **Verificación:** la paridad corre en CI con Node (ya lo hace para el motor).
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md`: «Toda función de `services/condiciones.py` o
  `services/diseno.items_planos` que tenga espejo en JS vive en `nodo-condiciones.js` y entra en la tabla de paridad; un
  espejo fuera de ese archivo es una copia sin red.»

---

### B-FE-08 · El modal de requisito está duplicado en cuatro pantallas y ya difiere entre ellas
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** — · **Ola:** 12 · **Esfuerzo:** M
- **ID de la pasada 1:** B5-FE-04
- **Ubicación:** alta y edición de requisito en `programas/templates/programas/becas/config/segmento_detail.html:601-724`,
  `subsegmento_detail.html:100-240`, `programa_detail.html:252-380` y `requisitos_segmento.html:65-210` (ocho modales).
  `'SELECTOR' || 'SELECTOR_MULTIPLE'` escrito a mano en 8 `x-show` (`segmento_detail.html:690,695`,
  `subsegmento_detail.html:208,213`, `programa_detail.html:347,352`, `requisitos_segmento.html:110,115,181,186`).
- **Escenario:** las copias ya no dicen lo mismo: el **alta** de `programa_detail` y `requisitos_segmento` pide «Este
  dato alimenta a SIIS como» (`programa_detail.html:297-305`, `requisitos_segmento.html:131-136`), pero el alta de
  `segmento_detail` y `subsegmento_detail` no lo trae (solo la edición, `segmento_detail.html:709-718`,
  `subsegmento_detail.html:227-236`): desde el segmento hay que crear y después editar para fijar el destino SIIS. El alta
  usa el `<select>` de Django + `_tipo_selector_js.html`; la edición, controles armados a mano + `x-show`: dos mecanismos
  para el mismo comportamiento en la misma pantalla. Y los tipos con opciones están escritos en JS en lugar de salir de
  `TipoCampo.selectores()`.
- **Causa raíz:** cada pantalla clonó el modal de la anterior; no hay un include de dominio para «form de requisito».
- **Solución:** `programas/templates/programas/becas/config/_requisito_modales.html` (include **de Becas**, no de
  `components/`) parametrizado con `prefijo`, `crear_url`, `scope`, `muestra_destino` y la variable Alpine de cada
  pantalla; mismo markup y clases que hoy (sin cambio visual). La lista de tipos con opciones llega por `json_script`
  desde `TipoCampo.selectores()`. La diferencia del destino SIIS en el alta queda como parámetro explícito.
  `DECISIÓN CLIENTE: por defecto, mostrar el destino SIIS también en el alta de segmento y subsegmento (con la misma
  condición `valida_siis` que ya usa la edición).`
- **Lo que NO hay que hacer:** promover el modal a `components/` ni crear un `x-nodo-modal` (refutado en §8.1).
- **Tests a agregar:** el snapshot de los detalles de Becas se regenera (`ACTUALIZAR_SNAPSHOTS_DETALLE=1`) y el diff debe
  ser solo de ids/orden; `programas/tests/test_requisitos_modales.py::test_las_cuatro_pantallas_usan_el_include`.
- **Verificación:** `design_audit.py --ratchet` 0 nuevos; `compile_templates.py --bloques` 0.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-frontend.md`: «Un modal de alta/edición del mismo
  modelo que aparece en dos pantallas se escribe una vez como include del dominio; la segunda pantalla lo incluye.»

---

### B-ERR-16 · «Terminar revisión» cuenta los pendientes sin candado: una captura tardía puede quedar ENVIADA dentro de un relevamiento TERMINADO
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** nuevo (relacionado con G1-04, gracia de sincronización) · **Ola:** 5 · **Esfuerzo:** S
- **ID de la pasada 1:** B1-ERR-03
- **Ubicación:** `programas/views/revision.py:1362-1384` (`relevamiento_terminar`).
- **Escenario:** relevamiento EN_REVISION dentro de las 24 h de gracia (`campo.ESTADOS_CON_GRACIA`, `campo.py:63-67`, que excluye TERMINADO a propósito: «sumar un caso cambiaría números ya informados»). El coordinador pulsa «Terminar»: la vista lee `rel.estado` y cuenta 0 pendientes **sin candado**; en ese momento la app sincroniza una captura atrasada: la API toma `select_for_update` sobre el relevamiento, ve EN_REVISION, inserta el caso ENVIADO y commitea; recién entonces el `UPDATE … estado='TERMINADO'` de la vista (que esperaba el candado de fila) se aplica. Queda un relevamiento TERMINADO con un caso sin revisar, que es justo lo que la vista y `campo` quieren impedir.
- **Causa raíz:** chequeo y escritura del estado en pasos separados, sin el candado de fila que usa la API de campo para la misma decisión.
- **Solución:** envolver el `POST` en `transaction.atomic()`, releer `rel = Relevamiento.objects.select_for_update().get(pk=rel.pk)` (mismo orden que la API: relevamiento primero; no hay HTTP adentro) y hacer la validación de estado y los dos conteos con esa fila tomada. Mismo mensaje y misma regla.
- **Lo que NO hay que hacer:** sumar el chequeo a la API (ya rechaza TERMINADO; el problema es la ventana).
- **Tests a agregar:** `programas/tests/test_revision_terminar.py::TerminarRelevamientoTests.test_toma_candado_del_relevamiento` (afirmar con `CaptureQueriesContext` que el `SELECT … FOR UPDATE` del relevamiento precede al conteo; en SQLite el candado es no-op, así que se prueba la forma).
- **Verificación:** el test; en el banco MySQL, dos conexiones (captura con el candado tomado + terminar) y ver que terminar espera y luego informa «Quedan 1 caso(s) sin revisar».
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/` · «Una transición de estado que depende de un conteo de hijos se decide con la fila padre tomada (`select_for_update`) si otro camino inserta hijos bajo ese mismo candado».

---

### B-ERR-17 · El filtro «fecha hasta» del listado de relevamientos excluye los que empiezan ese mismo día
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** nuevo (misma familia que DIS-01/BEC-18, no cubierto por su guardia: no hay `__date`) · **Ola:** 5 · **Esfuerzo:** S
- **ID de la pasada 1:** B1-ERR-04
- **Ubicación:** `programas/views/relevamientos.py:688-689` y `:705-708` (`RelevamientoListView.get_queryset`).
- **Escenario:** `fecha_asignada` y `fecha_hasta` son `DateTimeField` (`models/__init__.py:3187-3188`). Con `?fecha_hasta=2026-11-19`, `filter(fecha_asignada__lte=date(2026,11,19))` compila a `<= 2026-11-19 00:00` hora local (Django convierte la fecha a medianoche y avisa *naive datetime*): un relevamiento asignado el 19/11 a las 09:00 **no aparece** filtrando «hasta el 19/11». Además cada filtro con fecha deja un `RuntimeWarning` por request.
- **Causa raíz:** comparar un `date` contra un `DateTimeField` como límite superior inclusivo.
- **Solución:** usar el helper de `core/utils_fechas.py` (`inicio_del_dia_local` / `rango_periodo_local`): `fecha_hasta__gte=inicio_del_dia_local(fecha_desde)` y `fecha_asignada__lt=inicio_del_dia_local(fecha_hasta + timedelta(days=1))`. Sin `__date` ni `Trunc*` (seguro en ECOM).
- **Tests a agregar:** `programas/tests/test_relevamientos_list.py::FiltrosTests.test_fecha_hasta_incluye_el_dia`.
- **Verificación:** el test (rojo hoy).
- **Regla para no repetirlo:** **control mecánico** · `core/tests/test_sql_portable.py` · extender la guardia `ast` que ya resuelve el tipo del campo: un lookup `__lte`/`__lt`/`__gte`/`__gt` sobre un `DateTimeField` cuyo valor sale de `parse_date(...)` → error «compará contra `inicio_del_dia_local(...)`».

---

### B-ERR-18 · Los filtros `segmento` y `territorial` del listado de relevamientos dan 500 con un valor no numérico
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** nuevo · **Ola:** 5 · **Esfuerzo:** S
- **ID de la pasada 1:** B1-ERR-05
- **Ubicación:** `programas/views/relevamientos.py:686-687` y `:701-704`.
- **Escenario:** `GET /becas/relevamientos/?segmento=abc` (un link viejo, un parámetro pegado a mano, un escáner) → `filter(convocatoria__segmento_id="abc")` lanza `ValueError: Field 'id' expected a number` al armar la consulta → 500 y una alerta de error en el log. La bandeja hermana (`revision.py:466-471`) ya se cuida con `isdigit()`.
- **Causa raíz:** parámetros GET pasados crudos a un lookup de FK.
- **Solución:** mismo patrón que `RenaperPendientesListView`: aplicar el filtro solo si `segmento.isdigit()` / `territorial.isdigit()` (se ignora el valor inválido, como en la otra bandeja).
- **Tests a agregar:** `programas/tests/test_relevamientos_list.py::FiltrosTests.test_segmento_no_numerico_no_da_500`.
- **Verificación:** el test.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/` · «Todo id que llega por GET a un `filter(..._id=…)` pasa por `isdigit()` o por un form: un `ValueError` del ORM es un 500».

---

### B-ERR-19 · El CSV de beneficiarios rotula como «Fecha de aprobación» la última modificación del caso, en día UTC
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** nuevo (BEC-18 barrió `now().date()`, no este `strftime`) · **Ola:** 5 · **Esfuerzo:** S
- **ID de la pasada 1:** B1-ERR-06
- **Ubicación:** `programas/views/relevamientos.py:524` (encabezado) y `:541`, `:562` (`modificado.strftime("%d/%m/%Y")` en `convocatoria_export_beneficiarios`).
- **Escenario:** (a) un caso aprobado el 19/11 a las 22:30 ART tiene `modificado = 20/11 01:30 UTC`: el CSV dice «20/11/2026»; (b) cualquier escritura posterior (guardar contacto, `datos_siis`, revalidar identidad, el envío a SIIS) mueve `modificado`, y la «fecha de aprobación» del CSV pasa a ser esa. El CSV es el que se entrega con nombre y DNI de los aprobados.
- **Causa raíz:** se usa `modificado` como proxy de la aprobación y se formatea el `datetime` aware sin pasarlo a hora local.
- **Solución:** como mínimo, `timezone.localtime(modificado)` (o `core.utils_fechas.fecha_local`) antes del `strftime`: no cambia lógica. Para el valor: `DECISIÓN CLIENTE: por defecto, tomar la fecha de la traza de la transición a APROBADO` (`Subquery` sobre las trazas del caso con `campo="estado"` y `valor_nuevo="APROBADO"`, ordenadas por `-created_at`, `[:1]`, agregado al `values_list`; una sola consulta, sin N+1), o renombrar la columna a «Última modificación».
- **Tests a agregar:** `programas/tests/test_exports_convocatoria.py::BeneficiariosCsvTests.test_fecha_en_hora_local`.
- **Verificación:** el test con `modificado` a las 01:30 UTC.
- **Regla para no repetirlo:** **control mecánico** · `core/tests/test_sql_portable.py` (o test hermano) · `ast`: `.strftime(` sobre un atributo que resuelve a `DateTimeField` sin `localtime`/`fecha_local` en la misma expresión → error.

---

### B-ERR-20 · «Avance de convocatorias» cuenta con otras reglas de alcance que el resto de los reportes
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** nuevo (deriva de SEC-22/D-22) · **Ola:** 4 · **Esfuerzo:** S
- **ID de la pasada 1:** B2-ERR-03
- **Ubicación:** `programas/services/reportes_becas.py:162-174` y `:203` (`reporte_avance`).
- **Escenario:** (a) un usuario sin RN-P13 (`becas.relevamiento.publico`) mira «Avance» y «Embudo» de la misma
  convocatoria: «Form. aprobados» de Avance incluye los casos del link público
  (`Formulario.objects.filter(relevamiento__convocatoria_id__in=…)`, sin `sin_formularios_publicos_si_no_puede`),
  mientras «Aprobados» del Embudo (`_formularios(user)`, `:352`) y el tablero (`resolver_alcance`,
  `dashboard_becas.py:272-276`) los excluyen. Con 10 aprobados de los que 7 son públicos, Avance dice 10 y el Embudo 3.
  (b) Para un Coordinador Regional, «Aprobados/cupo» divide por `conv.segmento.cupo_maximo` (el cupo del segmento
  entero), mientras «Cupos por segmento» (`:94`) y el tablero (`_cupo`, `dashboard_becas.py:376-384`) le muestran lo
  distribuido en sus subsegmentos.
- **Causa raíz:** el conteo se separó de la consulta de relevamientos por performance (comentario de `:158-161`) y no
  heredó ni el filtro de RN-P13 ni la regla del cupo regional que usan los otros dos lugares.
- **Solución:** `DECISIÓN CLIENTE: por defecto, alinear Avance con el Embudo y el tablero`: aplicar
  `sin_formularios_publicos_si_no_puede(..., programa=programa_becas(user))` a la consulta de `contados`, y para el
  regional usar como denominador la suma de `cupo_maximo` de sus subsegmentos de ese segmento (la misma que
  `reporte_cupos`). Si el PM decide que Avance es **capacidad** como el cupo (D-22), dejar (a) como está y escribirlo en
  la descripción del reporte; (b) se corrige igual.
- **Tests a agregar:**
  `programas/tests/test_reportes_becas.py::ReporteAvanceTests.test_sin_rn_p13_no_cuenta_casos_publicos` y
  `...test_regional_ve_aprobados_sobre_cupo_distribuido`.
- **Verificación:** los dos tests; con el mismo usuario y recorte, «Form. aprobados» de Avance = «Aprobados» del Embudo.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/` (Becas) · «Una cifra nueva de casos
  en reportes o dashboard sale de `_formularios(user)` / `resolver_alcance`, no de `Formulario.objects` con un filtro
  armado a mano: así hereda RN-P13 y el alcance del regional».

---

### B-ERR-21 · Una caída de Redis al leer el token deja el envío EN_PROCESO sin POST
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** Thermos corrección · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** B3-ERR-06
- **Ubicación:** `programas/services/siis.py:738-743` (el `except` de `_intentar_alta`, que solo atrapa `RequestException, TypeError, ValueError, _SiisConfigurationError`) y `siis.py:398` (`cache.get` en `_token()`, sin `IGNORE_EXCEPTIONS`). El comentario de 956-957 reconoce que la lectura no está protegida.
- **Escenario:** en prd/qa la cache es Redis. Redis corta justo después de `_reservar`. `cache.get` lanza `ConnectionInterrupted`, que escapa de `_intentar_alta` aunque el docstring dice «Nunca lanza». `_cerrar` no corre y el envío queda EN_PROCESO sin que se haya mandado nada. A los 5 minutos pasa a incierto y necesita una conciliación manual con ECOM por un alta que nunca salió.
- **Causa raíz:** el `except` del token no cubre los errores de la cache.
- **Solución:** sumar al `except` de 738-743 los errores de la cache (o `Exception` acotado a la obtención del token) y devolver `RESULTADO_NO_ENVIADO`, igual que con un fallo de login. Es seguro porque todavía no salió ningún POST.
- **Lo que NO hay que hacer:** no ampliar el `except` alrededor del POST. Ahí un error sí es incierto.
- **Tests a agregar:** un mock de `cache.get` que lanza. El envío queda NO_ENVIADO/ERROR y no EN_PROCESO.
- **Verificación:** el test en rojo con el código actual.
- **Regla para no repetirlo:** antes del POST, cualquier excepción es «no enviado». Después del POST, es «incierto».

---

### B-ERR-22 · Un catálogo vacío de SIIS queda en cache 24 h
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** Thermos corrección · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** B3-ERR-07
- **Ubicación:** `programas/services/siis.py:664-665` (`catalogo`), `679-680` (`funciones_programa`) y `945-974` (`refrescar_catalogos_locales`, que invalida y después llama a `catalogo()`).
- **Escenario:** SIIS devuelve una lista vacía durante una ventana de mantenimiento. `catalogo()` hace `cache.set(clave, [], CATALOGO_CACHE_LARGO)`. El refresco nocturno lo deja así para todo el día. `Catalogos()` de los comandos y del masivo arma el payload con catálogos vacíos y el resultado son INCOMPLETO o RECHAZADO en serie. `listar_programas` (533-537) y `guardar_catalogo_local` (908) ya evitan cachear lo vacío. Estas dos no.
- **Solución:** cachear solo si `items` no está vacío, igual que en 533-537.
- **Lo que NO hay que hacer:** no bajar el TTL general.
- **Tests a agregar:** con un mock que devuelve `[]`, no queda clave en la cache.
- **Verificación:** test.
- **Regla para no repetirlo:** una respuesta vacía de un sistema externo no se cachea con TTL largo.

---

### B-ERR-23 · `--ignorar-corrida` de `correr_alta_siis` no llega a los hijos y corta a mitad de camino
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** Thermos corrección · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** B3-ERR-08
- **Ubicación:** `programas/management/commands/correr_alta_siis.py:186-195` y `231-240` (validación propia), `348-361` (`_verificacion`) y `410-426` (`_por_tandas`). `_base_siis.py:175-209` es `exigir_sin_corrida_viva`.
- **Escenario:** hay una corrida viva colgada y el operador usa `--ignorar-corrida --motivo ...`. La orquestación pasa su chequeo y ejecuta los pasos 2 a 5: insumos SQL, RENAPER y correcciones, que escriben datos. En el paso 6, el `procesar_casos_siis` hijo no recibe la bandera, `exigir_sin_corrida_viva` falla y la corrida termina a mitad de camino, con datos ya mutados.
- **Solución:** pasar `ignorar_corrida` y `motivo` en los `call_command` de 348-361 y 410-426.
- **Tests a agregar:** con una corrida viva y `--ignorar-corrida`, el hijo recibe la bandera (mock de `call_command`).
- **Verificación:** test.
- **Regla para no repetirlo:** las banderas de seguridad del orquestador se propagan a todos los hijos que las validan.

---

### B-ERR-24 · El cruce automático del padrón pisa validaciones y datos del legajo escritos mientras corre
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** — (mismo patrón que G3-06) · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** B4-ERR-04
- **Ubicación:** `programas/services/padron.py:596-603` (pendientes leídos sin candado, en el request que sube el
  Excel), `:702-708` (`UPDATE … WHERE pk IN` sin volver a filtrar `validado_renaper=False, identidad_forzada=False`),
  `:709-714` (`bulk_update` de `datos_identificacion` y `dni_titular` con la copia en memoria), `:642-645`
  (`bulk_update` de `Ciudadano` con los campos que estaban vacíos al leer).
- **Escenario:** un padrón de convocatoria con miles de pendientes tarda decenas de segundos. Mientras tanto un
  revisor revalida un caso con Base de Personas (`origen_validacion=PERSONAS`) o fuerza la identidad
  (`identidad_forzada=True`), o completa a mano el apellido del legajo. Al terminar el cruce, el `UPDATE` le reescribe
  `origen_validacion=PADRON`, el `bulk_update` repone el `datos_identificacion` leído antes y el legajo vuelve a tener
  el apellido del Excel. El docstring promete «nunca desvalida» y «no pisa».
- **Causa raíz:** el filtro de «pendiente» se evalúa al leer y no se repite al escribir; `bulk_update` no admite
  condición por fila.
- **Solución:** (1) agregar `validado_renaper=False, identidad_forzada=False` al `filter` del `UPDATE` de
  `solo_constantes` (`:708`); (2) antes del `bulk_update` de `con_json`, releer los pks que siguen pendientes
  (`Formulario.objects.filter(pk__in=…, validado_renaper=False, identidad_forzada=False).values_list("pk")`) y escribir
  solo esos; (3) para `Ciudadano`, la misma relectura de «campo todavía vacío» antes del `bulk_update` por grupo.
  Mismas sentencias en el caso normal; solo deja de escribir lo que cambió en el medio. Ajustar el conteo devuelto a lo
  efectivamente escrito.
- **Tests a agregar:** `programas/tests/test_padron.py::CruceConcurrenteTests.test_no_pisa_un_caso_validado_mientras_corria`,
  `.test_no_pisa_un_apellido_cargado_mientras_corria`.
- **Verificación:** los tests anteriores (mock que valida el caso entre la lectura y la escritura).
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` · «Una escritura masiva que decide por
  un estado leído (pendiente, vacío) repite esa condición en el `WHERE` del `UPDATE`; con `bulk_update`, se relee el
  subconjunto que todavía la cumple».

---

### B-ERR-25 · El fallecimiento se busca en toda la respuesta de Base de Personas, no en el registro elegido
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** residuo de SIIS-10 (el arreglo pasó `normalizar_persona` a `_plano`, `_informa_fallecido` quedó con `_aplanar`) · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** B4-ERR-05
- **Ubicación:** `programas/services/personas.py:209-231` (`_informa_fallecido(data)` usa `_aplanar`, primera aparición
  a cualquier profundidad gana), `:318-333` (se llama con `data` entero después de `elegir_registro`).
- **Escenario:** la fuente devuelve `data.personas` con dos registros (forma aceptada en `_registros`, `:111-113`): el
  de otro documento primero, con `fallecido: true`, y el de la persona consultada. `elegir_registro` elige bien el
  segundo, pero `_informa_fallecido` lee el `fallecido` del primero → `{"success": False, "fallecido": True}` y el paso 1
  del link corta a una persona viva (Cambio 41). Al revés, si el primero trae `fallecido: "N"`, el `setdefault` tapa la
  marca del registro elegido. Lo mismo con un `mensaje` anidado (p. ej. de un domicilio).
- **Causa raíz:** SIIS-10 dejó de aplanar el árbol para los datos de la persona, pero la detección de fallecimiento
  siguió leyendo el árbol entero.
- **Solución:** en `consultar`, conservar el registro de `elegir_registro` y evaluar
  `_informa_fallecido_en(registro)` con `_plano` (primer nivel del registro) **más** las marcas de sobre que hoy se
  aceptan en el primer nivel de `data` (`mensaje`, `mensaf`, `codigo`). Las variantes del contrato abierto (#243) siguen
  todas; solo cambia de qué registro se leen.
- **Tests a agregar:** `programas/tests/test_personas_service.py::FallecidoPorRegistroTests.test_fallecido_de_otro_registro_no_corta`,
  `.test_fallecido_del_registro_elegido_corta_aunque_otro_diga_no`.
- **Verificación:** los dos tests anteriores más `test_reconoce_las_variantes_de_fallecido_del_contrato_abierto` en verde.
- **Regla para no repetirlo:** **skill** · `.claude/skills/seguridad-django/SKILL.md` (datos personales) · «Toda
  conclusión sobre una persona a partir de una respuesta externa se lee del registro atribuido a su DNI/sexo, nunca de
  un aplanado de la respuesta entera».

---

### B-ERR-26 · `completar_casos_renaper --aplicar` reescribe `data`/`respuestas`/`definicion` con una copia sin candado
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** mismo patrón que G3-06 (`corregir_datos_siis`) · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** B4-ERR-06
- **Ubicación:** `programas/management/commands/completar_casos_renaper.py:388-416` (el lote se lee fuera de la
  transacción, se transforma en Python y `bulk_update(cambiados, CAMPOS_A_GUARDAR)` escribe los tres JSON enteros).
- **Escenario:** el comando corre sobre los ~7.500 casos de todas las convocatorias con la app en uso. Un revisor
  corrige «Completar datos para SIIS» o el contacto de un caso entre la lectura del lote y su `bulk_update`: el comando
  repone `data`/`respuestas` leídos antes y la corrección se pierde sin traza.
- **Causa raíz:** el `transaction.atomic()` envuelve solo la escritura; la lectura que decide qué escribir queda afuera
  y sin `select_for_update`.
- **Solución:** mover la lectura del lote dentro del `atomic` con
  `Formulario.objects.select_for_update().select_related(...).filter(pk__in=lote_ids)` cuando `--aplicar` (lotes de 50:
  el candado dura milisegundos, lejos del `read_timeout`). En seco queda igual.
- **Lo que NO hay que hacer:** no tomar el candado de toda la corrida ni de lotes grandes: cada lote es su transacción a
  propósito (`:28-32`).
- **Tests a agregar:** `programas/tests/test_completar_casos_renaper.py::LoteBajoCandadoTests.test_el_lote_se_lee_con_select_for_update`
  (con `candados_tomados` de RED-67).
- **Verificación:** el test anterior.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/` (datos y comandos) · «Un comando que
  reescribe columnas JSON enteras lee el lote dentro de la misma transacción y con `select_for_update`».

---

### B-ERR-27 · La eliminación en cascada puede dejar vivo un hijo creado entre la lectura de ids y el bloqueo
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** — · **Ola:** 6 · **Esfuerzo:** S
- **ID de la pasada 1:** B5-ERR-03
- **Ubicación:** `programas/services/eliminacion.py:120` (`_ids_de_cascada`, definida en `:77`, antes de los locks); relectura solo de relevamientos en `:124-129`.
- **Escenario:** un admin elimina un segmento mientras otro usuario crea una convocatoria o un subsegmento en ese segmento. Los ids se leyeron antes del `FOR UPDATE`; tras bloquear se relee solo la lista de relevamientos, no la de convocatorias ni subsegmentos. La convocatoria nueva queda viva bajo un segmento eliminado (huérfana en listados y selectores).
- **Causa raíz:** la ventana lectura→lock se cerró para relevamientos y no para los demás niveles intermedios.
- **Solución:** después de bloquear, releer bajo lock subsegmentos y convocatorias de `ids["segmentos"]` (igual que ya se hace con relevamientos) antes de contar casos y marcar. Mismo orden de locks.
- **Lo que NO hay que hacer:** no invertir el orden de locks (abre el deadlock documentado en `_ORDEN`).
- **Tests a agregar:** `TransactionTestCase` con dos hilos en MariaDB del banco: crear convocatoria durante la eliminación del segmento → queda eliminada o la creación falla.
- **Verificación:** banco MariaDB `scripts/perf_mysql/` con dos sesiones.
- **Regla para no repetirlo:** **CLAUDE.md** · Convenciones · «Si se resuelven ids antes del lock, se releen bajo lock todos los niveles que pueden recibir altas concurrentes.»

---

### B-ERR-28 · `reconciliar` e `items_vigentes` asumen que cada regla de condición es un dict
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** — · **Ola:** 6 · **Esfuerzo:** S
- **ID de la pasada 1:** B5-ERR-04
- **Ubicación:** `programas/services/diseno.py:582` y `:675` (`regla.get("fuente")` sin `isinstance`), frente a `:346` que sí lo chequea.
- **Escenario:** una condición guardada con una regla que no es dict (dato restaurado o escrito antes de `validar_condicion_json`) produce `AttributeError` y 500 al abrir el constructor o al servir la definición a la app.
- **Causa raíz:** defensa inconsistente sobre el mismo JSON en varios lugares.
- **Solución:** usar el mismo guard `isinstance(regla, dict)` que `:346`.
- **Lo que NO hay que hacer:** no envolver el bucle en un `except Exception`.
- **Tests a agregar:** diseño con regla `"x"` → `reconciliar` e `items_vigentes` no levantan.
- **Verificación:** test nuevo.
- **Regla para no repetirlo:** **agente** · revisor · «Un JSON persistido se lee con el mismo helper en todos lados.»

---

### B-ERR-29 · `generar_por_defecto` no limpia `bajas_pendientes` y el siguiente `reconciliar` informa bajas viejas
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** — · **Ola:** 6 · **Esfuerzo:** S
- **ID de la pasada 1:** B5-ERR-05
- **Ubicación:** `programas/services/diseno.py:283`.
- **Escenario:** el diseño acumuló bajas del catálogo y el usuario usa «Restablecer» (regenera desde el plan por defecto). Las bajas siguen guardadas y el próximo `reconciliar` muestra avisos de condiciones quitadas que ya no aplican al diseño nuevo.
- **Causa raíz:** el reemplazo total de ítems no resetea el estado derivado del diseño anterior.
- **Solución:** en `generar_por_defecto`, poner `bajas_pendientes=None` en la misma transacción (como `reconciliar` en `:595-597`).
- **Lo que NO hay que hacer:** no borrar las bajas en caminos que no reemplazan el diseño.
- **Tests a agregar:** diseño con bajas → restablecer → `bajas_pendientes is None`.
- **Verificación:** test nuevo.
- **Regla para no repetirlo:** **agente** · revisor · «Toda operación que reemplaza un agregado resetea su estado derivado.»

---

### B-ERR-30 · `datos_identificacion` que no es objeto JSON da 500 en vez de 400
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** — · **Ola:** 1 · **Esfuerzo:** S
- **ID de la pasada 1:** B6-ERR-02
- **Ubicación:** `programas/api/serializers.py:250`, `:261-263`, `:275` (`FormularioSerializer.validate`)
- **Escenario:**
  1. Llega un POST de formularios con `"datos_identificacion": "texto"` o con una lista.
  2. El merge `{**(attrs.get(...) or {}), **identidad}` lanza `TypeError`. O bien `datos.get("dni")` lanza `AttributeError`.
  3. Resultado: 500. La app reintenta los 5xx hasta 8 veces y nunca muestra un error legible.
- **Causa raíz:** el campo es un `JSONField` del modelo. Acepta cualquier JSON, y nadie valida su tipo antes de usarlo como dict.
- **Solución:** agregar `validate_datos_identificacion(self, value)` que rechace con `rechazo_legible` todo lo que no sea `dict` (400, misma forma que el resto). `None` sigue igual.
- **Tests a agregar:** `programas/tests/test_api_campo.py::FormularioSerializerTipoTest.test_datos_identificacion_no_dict_da_400`
- **Verificación:** test en verde. Un POST con una lista devuelve 400 con el código de validación.
- **Regla para no repetirlo:** **skill** · `.claude/skills/seguridad-django/` · «Un `JSONField` expuesto en un serializer valida su forma (dict/list) antes de indexarlo: si el tipo es otro, la respuesta es 500.»

---

### B-PERF-09 · El detalle de convocatoria lista todos sus relevamientos sin paginar
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** PERF · **Origen:** PERF-17 (abierta: la parte de Becas quedó «con FE-17», y FE-17 cerró en parcial sin tocar esta solapa) · **Ola:** 5 · **Esfuerzo:** S
- **ID de la pasada 1:** B1-PERF-02
- **Ubicación:** `programas/views/relevamientos.py:285-296` (`ConvocatoriaDetailView.get_context_data`,
  `relevamientos = list(relevamientos_qs)`), `:172-178` (`_relevamientos_ajax`, el mismo listado al crear desde el modal);
  plantilla `programas/templates/programas/becas/relevamientos/_relevamientos_tab_table.html:16-44`.
- **Escenario:** convocatoria con muchos relevamientos territoriales (una asignación por territorial y franja; el banco
  tiene 2.001 relevamientos). La solapa «Relevamientos» se arma entera en cada GET del detalle —aunque el usuario esté en
  «Información general» o «Beneficiarios»— y en cada alta por el modal: una fila por relevamiento con un `include` de
  `_estado_badge.html`. Además la lista entera de ids viaja como `relevamiento_id IN (...)` a las dos consultas de casos
  (`:294`, `:297`, `:309`); pasado el `in_predicate_conversion_threshold` (1.000) MariaDB la materializa como tabla
  derivada (lo describe la resolución de PERF-13).
- **Causa raíz:** el listado nació para pocas asignaciones por convocatoria; FE-17 dejó lista la pieza `_paginacion` con
  `param`/`extra_qs`, pero esta solapa no la usa.
- **Crece con:** relevamientos por convocatoria. 1 consulta, pero render O(N) filas e `IN` de N ids en las consultas de
  casos.
- **Solución:** paginar la solapa con `Paginator(relevamientos_qs, 25)` y `param="relevamientos_page"`,
  `extra_qs="tab=rel"` en `components/_paginacion.html` (mismo patrón que `beneficiarios_page`). Para `formularios_base`
  y `tiene_publicos`, sacar los ids con un `values_list("pk", "tipo")` angosto de los relevamientos visibles (o filtrar
  los casos por `relevamiento__convocatoria_id` con la exclusión de públicos solo cuando hace falta, como el cupo desde
  PERF-02). `_relevamientos_ajax` devuelve la página 1. Mismo orden (`-fecha_asignada`), mismas columnas.
- **Lo que NO hay que hacer:** cortar con `[:N]` sin paginador (esconde relevamientos sin decirlo).
- **Tests a agregar:** `programas/tests/test_convocatoria_detalle.py::RelevamientosPaginadosTests.test_la_solapa_corta_en_25_y_la_26_es_alcanzable`
  y `RelevamientosPaginadosTests.test_el_costo_no_crece_con_los_relevamientos` (`assertNumQueries` igual con 3 y con 30).
- **Verificación:** banco: `bench_mysql.py` con un target de `becas:convocatoria_detalle` sobre una convocatoria con
  2.000 relevamientos territoriales (el actual, `convocatoria_publica_detalle`, mide la del público, que tiene uno) y
  `perfil_ruta.py /becas/convocatorias/<pk>/` para el tiempo de plantilla; entrada en `scripts/perf_budgets.json` para
  `becas:convocatoria_detalle`.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas activas ·
  «`list(...)` de una relación inversa en un `DetailView`: si la relación crece con el uso (relevamientos por
  convocatoria, casos por relevamiento), va paginada con su propio `param`, aunque hoy sean pocos».

---

### B-PERF-10 · El embudo agrupa los motivos en Python trayendo cada rechazo, y cada validación SIIS entera con su JSON `respuesta`
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** PERF · **Origen:** — · **Ola:** 4 · **Esfuerzo:** S
- **ID de la pasada 1:** B2-PERF-04
- **Ubicación:** `programas/services/reportes_becas.py:388-391` (`values_list("motivo_rechazo")` de todos los rechazados +
  `Counter`), `:392-399` (itera instancias completas de `ValidacionSIS` para leer `motivo_amigable`/`codigo_motivo`).
- **Escenario:** convocatoria con miles de rechazos SIIS (p. ej. «BENEFICIO_EXISTENTE») → el reporte trae una instancia
  por validación con `respuesta` (JSONField, `json.loads` por fila), `motivo` (TEXT), `documento`, etc., para quedarse
  con `codigo_motivo`. Lo mismo con los rechazos de backoffice: una fila por caso rechazado en vez de una por motivo.
- **Evidencia:** `ValidacionSIS.motivo_amigable` (`programas/models/__init__.py`, después de `:4345`) depende solo de
  `codigo_motivo`; la consulta `ultimas` (anti-join) se evalúa dos veces (`:381` y `:392`).
- **Crece con:** casos rechazados del recorte. Ninguna consulta se acerca al timeout: es transferencia y Python, por eso BAJA.
- **Solución (mismo resultado):** `qs.filter(estado=RECHAZADO).values("motivo_rechazo").annotate(n=Count("pk"))` y
  `validaciones.values("codigo_motivo").annotate(n=Count("pk"))`, traduciendo cada código con la misma tabla de
  `motivo_amigable` (sacarla a una constante del modelo para no duplicarla); el «Sin motivo informado» se aplica sobre la
  clave agrupada sumando los vacíos, y las filas salen en el mismo orden que hoy.
- **Tests a agregar:** `programas/tests/test_reportes_becas.py::EmbudoTests.test_motivos_agrupados_en_sql` (mismas filas
  con motivos repetidos y vacíos; `assertNumQueries` fijo).
- **Verificación:** banco: marcar 5.000 validaciones como RECHAZADO y `perfil_ruta.py /becas/reportes/embudo/ 1` (tiempo
  en `JSONField.from_db_value`), antes y después.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas activas ·
  «`Counter(... for x in qs)` sobre filas del recorte: el conteo va en `values().annotate(Count)`».

---

### B-PERF-11 · El catálogo de preguntas del dashboard se recalcula en cada request, con los ítems de todos los diseños del programa
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** PERF · **Origen:** — · **Ola:** 4 · **Esfuerzo:** S
- **ID de la pasada 1:** B2-PERF-05
- **Ubicación:** `programas/forms_reportes.py:155` (`self.preguntas = preguntas_graficables(user, programa)` en el
  `__init__` del form), `programas/services/dashboard_becas.py:867-872` (`ItemDiseno` de todas las convocatorias visibles
  con `select_related("diseno__convocatoria")`: `condicion`/`propio` JSON y la fila entera de `Convocatoria`); lo llaman
  `programa_dashboard_datos`, `programa_dashboard_exportar` y el detalle del programa (`views/configuracion.py:331`).
- **Escenario:** cada cambio de filtro o de pregunta en la solapa, **también cuando las métricas salen de la caché**, lee
  todos los ítems de todos los diseños del programa (decenas de convocatorias × 40-80 ítems) y arma el plan. La caché de
  5 minutos (RN-17) cubre métricas y distribuciones, no el catálogo.
- **Crece con:** convocatorias históricas del programa × ítems por diseño (no con casos: por eso BAJA).
- **Solución (misma salida):** cachear `preguntas_graficables` con la política de las métricas (clave por programa y
  huella, sufijo `catalogo`, 5 min; queda a lo sumo 5 minutos atrás, como el resto de la solapa) o, más barato, leer solo
  las columnas que `_preguntas_propias` usa (`values`/`only` y el nombre de la convocatoria en vez de la fila entera).
- **Tests a agregar:** `programas/tests/test_dashboard_becas.py::CatalogoTests.test_segundo_request_no_relee_items`.
- **Verificación:** `bench_mysql.py --solo dashboard_becas_datos` (ms en caliente y consultas) con 50 convocatorias con
  diseño de 60 ítems en el programa; entrada en `perf_budgets.json` de la ruta.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/rendimiento.md` · «Lo que se cachea por RN-17
  incluye armar el form: un `__init__` que consulta corre también en los cache hits».

---

### B-PERF-12 · `correr_alta_siis` vuelve a hidratar y armar el payload de todos los incompletos en cada tanda (costo cuadrático en tandas)
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** PERF · **Origen:** — · **Ola:** 2 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B3-PERF-03
- **Ubicación:** `programas/management/commands/correr_alta_siis.py:386-431` (`_por_tandas`: cada vuelta corre `procesar_casos_siis --solo-completos --total 500`); `programas/management/commands/procesar_casos_siis.py:415-420` (`ids_de(consulta)` sin límite + `elegir_completos` desde el pk más bajo); `programas/services/proceso_masivo.py:777-804` (`elegir_completos` saltea los incompletos sin marcarlos).
- **Escenario:** relevamiento de 20.000 candidatos con una fracción p de incompletos (la localidad sin cruce llegó al 38 %, `siis_envio.py:328-331`). Un incompleto no deja EnvioSIIS, así que sigue siendo candidato; cada tanda arranca de nuevo desde el pk más bajo y vuelve a hidratar (fila entera, unos 27 KB) y a armar el payload de todos los incompletos que quedan antes de juntar 500 completos. Con p = 0,35: unos 13.000 completos, 26 tandas; la tanda k re-mira unos k x 270 incompletos, unos 94.000 armados de más en la corrida, más la última tanda que recorre los 7.000 para devolver 0. Con lo medido en PERF-01 (329 ms cada 200 candidatos) son unos 2,5 min de CPU y unos 2,5 GB releídos de `programas_formulario`. El log lo muestra: «Descartados por datos incompletos» crece de tanda en tanda con los mismos casos. Además, cada tanda relee 3 veces `aprobados_materias` (`procesar_casos_siis.py:344`, `:387` y dentro de `candidatos`).
- **Causa raíz:** la frontera de lo ya mirado no pasa de una tanda a la siguiente; el tope de 500 (puesto por memoria, `correr_alta_siis.py:71-75`) parte el envío pero no la selección.
- **Con qué crece:** cuadrático en tandas (completos / 500) por incompletos; lineal en el tamaño de fila. No toma locks ni bloquea requests, pero el barrido repetido de una tabla de 283 MB gasta buffer pool de la base compartida durante horas. Frente a las horas de llamadas a SIIS de la corrida es menos del 5 %: por eso BAJA.
- **Solución (mismo conjunto final de casos):** `procesar_casos_siis` acepta `--desde-pk N` (filtra `pk__gt=N` antes de `ids_de`) e informa el último pk mirado por `elegir_completos`; `_por_tandas` le pasa esa frontera a la tanda siguiente. Cuando una tanda con frontera devuelve 0, se hace una vuelta más desde 0 (la que hoy ya hace la última tanda), así un caso corregido durante la corrida sigue entrando. Los insumos se leen una vez por tanda reusando `proceso_masivo.Insumos`.
- **Lo que NO hay que hacer:** marcar a los incompletos con un EnvioSIIS INCOMPLETO para sacarlos de candidatos (rompe la regla «el descarte no toca el caso», `procesar_casos_siis.py:27-32`).
- **Tests a agregar:** `programas/tests/test_correr_alta_siis.py::TandasTests.test_cada_incompleto_se_arma_una_vez_mas_el_barrido_final` (TANDA parcheado a 2, 4 completos y 3 incompletos intercalados; contar llamadas a `armar_payload` por pk).
- **Verificación / medición en el banco:** banco de 20.000 casos, con un 35 % sin localidad que cruce (borrar sus LocalidadSiis y alias). Correr `correr_alta_siis --sin-insumos --destino tabla --aplicar --continuar --usuario bench` con el SIIS mockeado (parchear `validar_compatibilidad` en un settings de banco). Sumar por tanda «Candidatos pendientes» y «Descartados por datos incompletos» y el tiempo por tanda: hoy la suma de descartados es mucho mayor que los incompletos distintos; después, unas 2 veces los incompletos.
- **Regla para no repetirlo:** skill · `.claude/skills/auditoria/rubricas/rendimiento.md`, Búsquedas activas · «Un orquestador que llama N veces a un comando que recorre los candidatos desde el principio y saltea sin marcar paga un costo cuadrático en vueltas. Pasar la frontera (último pk mirado) entre vueltas y hacer un barrido final.»

---

### B-PERF-13 · Borrar un requisito, una pregunta general o un subsegmento con documentos cargados trae a memoria TODOS los adjuntos solo para contarlos
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) para el mecanismo; el tiempo con volumen real es PLAUSIBLE · **Eje:** PERF · **Origen:** efecto lateral de DAT-01 (FKs de `AdjuntoFormulario` a PROTECT); Origen oct.: DAT-01 sigue 🟡 (fase 1 en Cambio 168; punto 3 abierto) · **Ola:** 6 · **Esfuerzo:** S
- **ID de la pasada 1:** B5-PERF-01
- **Ubicación:** `programas/views/configuracion.py:1317` (`pregunta.delete()`), `:804` (`req.delete()`), `:671` (`sub.delete()`); el conteo sobre lo materializado en `_casos_con_adjunto` (`:625-632`) y `_motivo_subsegmento_protegido` (`:635-660`). FKs PROTECT en `programas/models/__init__.py:4224-4239`.
- **Escenario:** una pregunta general tipo ARCHIVO (p. ej. la foto del DNI) la sube cada caso de todas las convocatorias. Con 5 relevamientos de 20.000 casos hay ~100.000 filas en `programas_adjuntoformulario` con ese `pregunta_global_id`. El administrador aprieta Eliminar en Requisitos generales: el `Collector` de Django ejecuta `SELECT` de las 8 columnas `FROM programas_adjuntoformulario WHERE pregunta_global_id IN (X) ORDER BY creado DESC` (filesort de las 100k filas: `Meta.ordering = ["-creado"]`, sin índice que lo cubra), arma 100.000 instancias, las mete en un `set` dentro del `ProtectedError`, y la vista las recorre para contar `formulario_id` distintos. El resultado es el toast de siempre, correcto pero caro. Igual con un requisito del programa (lo heredan todas sus convocatorias) y con un subsegmento (cascada a sus requisitos y de ahí a sus adjuntos).
- **Causa raíz:** el `ProtectedError` se usa como consulta de conteo. En Django 5.2 `Collector.collect()` evalúa entero el queryset protegido y, como `AdjuntoFormulario` no tiene receptores de `pre/post_delete` ni relaciones entrantes, el `.only(*referenced_fields)` queda con un conjunto vacío y trae todas las columnas. Verificado con `manage.py shell` sobre el SHA (`.venv312`, Django 5.2.17): `referenced_fields: set()` y el SQL de 8 columnas con `ORDER BY creado DESC`. Crece con los casos que subieron ese documento, no con el catálogo.
- **Estimación:** 1 consulta de N filas (N = casos con ese adjunto; 20k por relevamiento) más N instancias en Python. Con 100k filas estrechas, del orden de 0,3 a 1 s de SQL y 1 a 3 s de CPU y memoria en el worker. No pasa sola el `read_timeout`, pero escala lineal en una acción interactiva.
- **Solución:** contar antes de borrar, con la misma regla y el mismo mensaje. En `pregunta_eliminar` y `requisito_eliminar`: `casos = AdjuntoFormulario.objects.filter(pregunta_global=pregunta).values("formulario_id").distinct().count()` (o `requisito_nativo=req`); si hay casos, el `messages.error` con el texto actual y `redirect`, sin llamar a `delete()`. En `subsegmento_eliminar`, el mismo conteo con `requisito_nativo__subsegmento=sub` más la existencia de convocatorias del subsegmento (incluidas las de baja lógica, con el manager sin filtro) para elegir el mismo texto de `_motivo_subsegmento_protegido`. El `try/except ProtectedError` queda como red para la carrera (un adjunto que entra entre el conteo y el borrado). Textos y comportamiento idénticos.
- **Lo que NO hay que hacer:** volver las FKs a CASCADE o SET_NULL (contradice DAT-01) ni cambiar el conteo por `.exists()` (el mensaje muestra el número de casos).
- **Tests a agregar:** `programas/tests/test_configuracion_borrado_protegido.py::BorradoConAdjuntosTests.test_conteo_constante_en_consultas` (mismo `assertNumQueries` con 2 y con 30 casos con adjunto, y el mismo mensaje que hoy).
- **Verificación:** banco `scripts/perf_mysql/` con 20k casos: sembrar un `AdjuntoFormulario` por caso para una pregunta general y medir `POST becas:pregunta_eliminar` antes y después. No es ruta de `bench_mysql.py`: va con `perfil_ruta.py` sobre el POST, o con un script de una vez que corra `PreguntaGlobal.delete()` dentro de un `atomic` con rollback y mida tiempo y pico de memoria. `EXPLAIN` del `COUNT(DISTINCT formulario_id) ... WHERE pregunta_global_id = X` tiene que usar el índice de la FK.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` §Consultas · «No uses `ProtectedError.protected_objects` para contar: Django materializa todas las filas protegidas, con todas sus columnas y el `ordering` del modelo. Si el mensaje necesita un número, contalo antes con `values(fk).distinct().count()` y dejá el `except ProtectedError` solo como red de la carrera.»

---

### B-DAT-01 · `correr_alta_siis` identifica el caso de prueba por diferencia contra todos los pk de EnvioSIIS: puede mostrar el envío de otro caso
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** DAT · **Origen:** — · **Hallado por 2 revisores** (B3-DAT-01 + B3-LIM-13); origen de la absorbida: B3-LIM-13: — · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** B3-DAT-01 + B3-LIM-13 (**hallado por 2 revisores**)
- **Ubicación:** `programas/management/commands/correr_alta_siis.py:347` (`antes = set(EnvioSIIS.objects.values_list("pk", flat=True))`) y `:362` (`exclude(pk__in=antes).order_by("-pk").first()`).
- **Escenario:** el paso de verificación humana se agregó después de que 4.139 personas entraron a SIIS con la localidad equivocada (`correr_alta_siis.py:5-8`). Mientras corre el caso de prueba, la pantalla sigue operando: un coordinador que aprueba o promueve desde Cupo crea otro EnvioSIIS. Si ese pk es mayor, el comando muestra ese envío como el caso de prueba, con su localidad, y la persona verifica en SIIS un caso que no es el de la corrida; si ese envío salió INCOMPLETO o ERROR, frena la corrida sin motivo. Además trae a memoria todos los pk de la tabla y los manda como NOT IN de miles de literales: barato, pero crece sin necesidad.
- **Causa raíz:** el comando no sabe qué caso eligió el hijo y lo deduce por diferencia global de conjuntos.
- **Con qué crece:** filas de EnvioSIIS (memoria y tamaño del SQL); la carrera, con la actividad concurrente de la pantalla.
- **Solución (mismo comportamiento visible):** antes de mandar, `tope = EnvioSIIS.objects.aggregate(m=Max("pk"))["m"] or 0`; después, `EnvioSIIS.objects.filter(pk__gt=tope, solicitado_por=<usuario del --usuario>)` (el hijo recibe el mismo `--usuario`); sin `--usuario`, `solicitado_por__isnull=True`. Si aparece más de uno, avisarlo en vez de elegir el último.
- **Lo que NO hay que hacer:** frenar la pantalla durante el circuito (cambia la operación: sería DECISIÓN CLIENTE y no hace falta).
- **Tests a agregar:** `programas/tests/test_correr_alta_siis.py::VerificacionTests.test_muestra_el_envio_de_la_corrida_aunque_la_pantalla_cree_otro` (crear un EnvioSIIS de otro usuario dentro del mock de `call_command`).
- **Verificación:** el test anterior; en el banco, `correr_alta_siis --aplicar --usuario bench` con un segundo proceso creando envíos, y comprobar qué caso muestra.
- **Regla para no repetirlo:** skill · `.claude/skills/auditoria/rubricas/rendimiento.md`, Búsquedas activas · «`set(Modelo.objects.values_list("pk"))` + `exclude(pk__in=...)` para encontrar lo que creó el paso anterior: usar el máximo pk previo y un filtro por autor; la diferencia de conjuntos crece con la tabla y se confunde con lo que crea otro camino.»

#### Aporte del segundo revisor (B3-LIM-13: `correr_alta_siis` orquesta comandos con argv en texto y para saber qué hicieron trae a memoria todos los pk de `EnvioSIIS`)
_Pasada 1: severidad BAJA · estado CONFIRMADO (lectura) · esfuerzo S._

- **Ubicación:** `correr_alta_siis.py:347` (`antes = set(EnvioSIIS.objects.values_list("pk", flat=True))`), `362`, `383-384` y `534` (`len(ids_de(candidatos()))` para contar), `386-431` (`_por_tandas` vuelve a lanzar `procesar_casos_siis` con argv en texto).
- **Escenario:** para encontrar el envío del caso de prueba se materializan **todos** los pk de `EnvioSIIS` (decenas de miles tras una corrida) y se hace una diferencia de conjuntos. Para contar pendientes se materializan todos los ids de candidatos tres veces por corrida. La comunicación con el hijo es por flags en texto (`"--total", str(...)`), así que un flag renombrado en `procesar_casos_siis` rompe el orquestador recién en tiempo de ejecución.
- **Causa raíz:** el orquestador trata a los comandos como cajas negras y reconstruye su resultado consultando la base.
- **Solución:** `antes = EnvioSIIS.objects.aggregate(m=Max("pk"))["m"] or 0` y `filter(pk__gt=antes)`. `proceso_masivo.candidatos(destino=…).count()` (sin `distinct`, ver `proceso_masivo.py:705-711`) en vez de `len(ids_de(...))`. Para la tanda, invocar `call_command("procesar_casos_siis", solo_completos=True, total=…, lote=…, …)` con kwargs: Django valida contra el parser del hijo y un nombre equivocado falla con `TypeError` en el acto.
- **Lo que NO hay que hacer:** quitar `TANDA`: protege la memoria del pod (exit 137 del 01/10).
- **Tests a agregar:** `programas/tests/test_correr_alta_siis.py::VerificacionTests.test_encuentra_el_envio_de_prueba_sin_listar_todos` (presupuesto de consultas con `assertNumQueries`).
- **Verificación:** el test anterior con un presupuesto fijo de consultas, independiente del tamaño de `EnvioSIIS`.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/` · «Nunca `set(Modelo.objects.values_list("pk"))` para un diff: `Max(pk)` + `pk__gt`.»

---

### B-LIM-46 · Helpers duplicados dentro de `programas` (paginación, hidratación, marcas, fechas, porcentajes, lotes, URL base)
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** hallazgos/04-performance.md:102 (mover `_pagina_hidratada` a selector compartido: hecho a medias) · **Hallado por 2 revisores** (B1-LIM-08 + B2-LIM-09); origen de la absorbida: B2-LIM-09: — · **Ola:** 11 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B1-LIM-08 + B2-LIM-09 (**hallado por 2 revisores**)
- **Ubicación:**
  - `views/revision.py:145-164` (`_pagina_hidratada`, `filter(pk__in).order_by(*orden)`) vs `services/listados.py` (`hidratar_en_orden`, `hidratar_pagina`); paginación manual en `:512-553`.
  - `views/revision.py:119-142` (`_marcar_carga_duplicada_pendiente`) y `:258-276` (`_marcar_en_espera_activa`): mismo esqueleto; «en espera activa» calculado una tercera vez en `services/solapas.py:334-336`.
  - `views/revision.py:115` `_aware_start` = `services/dashboard_becas.py:221` = `services/reportes_becas.py:38`.
  - `views/relevamientos.py:109,114` `_paginate`/`_querystring_without` = `views/cupo.py:81,90`.
  - `views/revision.py:167-169` `_puede_publico` = `views/relevamientos.py:121-124`.
  - `"https" if request.is_secure() else "http"` + `get_host()` en `views/revision.py:769,1014,1159` (5 en `programas`).
  - `views/revision.py:222-226` `_programa_sin_siis` duplica `selectors/revision.py:258-259`; `:359-362` `_tiene_conflicto_duplicado_pendiente` duplica `:578-587`.
- **Escenario:** dos estrategias de hidratación significan dos lugares para corregir el próximo problema de orden/estabilidad de página; una optimización hecha en `listados.py` no llega a revisión.
- **Causa raíz:** los helpers canónicos llegaron después que las copias y nadie migró las viejas.
- **Solución:** revisión usa `hidratar_en_orden` (verificar que el orden resultante sea idéntico: `hidratar_en_orden` ordena en Python por la lista de pks, `_pagina_hidratada` re-ordena en SQL; si los criterios de desempate difieren, se deja y se documenta por qué); un `_marcar_en_lote(objetos, ids_marcados, atributo)` para las dos marcas; `aware_start` a `core/fechas.py`; `_paginate`/`_querystring_without`/`_puede_publico` a un `programas/views/_comun.py`; `url_base(request)` a `core/`; las dos duplicaciones internas llaman a la que queda.
- **Lo que NO hay que hacer:** cambiar el número de consultas de la bandeja (`revision_bandejas` 15/16 con techo medido + 1).
- **Tests a agregar:** el de orden estable de la bandeja (misma página antes/después) si no existe.
- **Verificación:** `test_becas_revision_listas`, presupuestos `becas_revision*` sin recalibrar.
- **Regla para no repetirlo:** agente · `rubricas/codigo-limpio.md` · «antes de escribir un helper privado de paginación/fechas/URL, buscar en `services/listados.py`, `core/`; si existe, se usa».

#### Aporte del segundo revisor (B2-LIM-09: Helpers triviales copiados entre dashboard, reportes y form)
_Pasada 1: severidad BAJA · estado CONFIRMADO (lectura) · esfuerzo S._

- **Ubicación:**
  - `_aware_start`: `programas/services/dashboard_becas.py:221-222` y `programas/services/reportes_becas.py:38-39`.
  - Rango por `creado`: `dashboard_becas.py:307-310` y `reportes_becas.py:42-47`.
  - Porcentaje: `_pct` (`dashboard_becas.py:225-228`) y cinco copias en línea `round(x * 100 / total, 1) if total else 0` (`reportes_becas.py:181`, `:319`, `:387`, `:395`, `:401`).
  - Lotes: `_lotes` en `dashboard_becas.py:1467-1475` y `reportes_becas.py:453-461` (mismo nombre, firmas distintas).
  - Nombre visible del territorial: `dashboard_becas.py:501`, `:1392`; `reportes_becas.py:320`; `forms_reportes.py:227-229` (y fuera de B2, cinco copias más en `selectors/kits.py:73`, `services/dispositivos.py:132`…).
  - `_formularios` existe en los dos servicios con firmas y semánticas distintas (`dashboard_becas.py:301`, `reportes_becas.py:32`).
- **Escenario:** un cambio de criterio (p. ej. redondeo, o mostrar `username` cuando el nombre está vacío) se aplica en una copia y no en las otras; el reporte de producción y el dashboard muestran al mismo territorial con nombres distintos si uno cambia.
- **Causa raíz:** sin módulo de utilidades de reportes; cada archivo se escribió solo.
- **Solución:** `programas/services/reportes.py` (ya compartido) recibe `inicio_del_dia(fecha)`, `filtrar_creado(qs, desde, hasta)`, `pct(parte, total, decimales=1)`, `lotes(iterable, tamano)`; el nombre visible va a `core` (`nombre_visible(usuario)`) y se usa también con los campos de `values()` (`nombre_visible_de(first, last, username)`). Renombrar `_formularios` de `reportes_becas` a `_casos_visibles`.
- **Lo que NO hay que hacer:** cambiar el formato del porcentaje de los reportes (`"12.5%"` como texto) al del dashboard (float): es lo que ve el usuario.
- **Tests a agregar:** `programas/tests/test_reportes_utils.py::PctTests`.
- **Verificación:** `grep -n "\* 100 /" programas/services/reportes_becas.py` vacío.
- **Regla para no repetirlo:** **control mecánico** · `scripts/` (chequeo propuesto en el gate de lint) · patrón `get_full_name\(\)\.strip\(\) or` fuera de `core/` → «usá `nombre_visible`».

---

### B-LIM-47 · La huella del alcance se calcula en dos lugares y cada entrada puede volver a resolver el alcance
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 10 · **Esfuerzo:** S
- **ID de la pasada 1:** B2-LIM-08
- **Ubicación:** `programas/services/dashboard_becas.py:257-261` (huella dentro de `resolver_alcance`), `:671-686` (`_huella`, `_huella_alcance`), `:695-697` (`clave_cache`); `alcance = alcance or resolver_alcance(...)` en `:567`, `:721`, `:1056`, `:1121`, `:1150`.
- **Escenario:** `_huella_alcance` repite las cuatro consultas de las primeras líneas de `resolver_alcance` y su docstring advierte que **tienen** que dar el mismo texto o dos usuarios comparten caché. En producción nunca se llama: el único llamador sin `alcance` es el test (`programas/tests/test_dashboard_becas.py:506-512`). Los cinco `alcance or resolver_alcance` hacen que olvidar pasar `alcance` en una vista nueva resuelva el alcance dos veces en silencio (el comentario de `views/dashboard_becas.py:92-93` existe para evitar justo eso).
- **Causa raíz:** parámetro opcional que encubre un invariante («el alcance se resuelve una vez por petición»).
- **Solución:** `alcance` obligatorio en `metricas`, `metricas_cacheadas`, `distribuciones_respuestas`, `distribucion_cacheada`, `distribuciones_cacheadas` y `clave_cache`; borrar `_huella_alcance`. El test de `:506-512` pasa `svc.resolver_alcance(...)`.
- **Tests a agregar:** ninguno nuevo; ajustar los existentes.
- **Verificación:** `grep -n "_huella_alcance\|alcance or resolver_alcance" programas/` vacío; suite del dashboard en verde.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md` · «Un parámetro opcional con `x or recalcular_x()` sobre un invariante de una vez por petición es un fallback silencioso: hacelo obligatorio».

---

### B-LIM-48 · Copia y pega dentro de `reporte_produccion` y `reporte_avance`
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 10 · **Esfuerzo:** S
- **ID de la pasada 1:** B2-LIM-10
- **Ubicación:** `programas/services/reportes_becas.py:256-270` y `:293-307` (el mismo `setdefault` de 10 claves dos veces, con prefijos de campo distintos); `:115-145` (cinco `Count("relevamientos", filter=Q(..., estado=X), distinct=True)` idénticos salvo el estado) y `:178-179` (`setattr` sobre la instancia).
- **Escenario:** agregar un estado de relevamiento o una columna exige editar 2 o 5 bloques casi idénticos; olvidar uno deja un `KeyError` o una columna en 0.
- **Causa raíz:** sin factorizar el grupo ni generar las anotaciones.
- **Solución:** `def _grupo_vacio(first, last, username, segmento)` usado por los dos bucles; anotaciones generadas: `{f"rel_{nombre}": Count(..., filter=Q(relevamientos__eliminado_en__isnull=True, relevamientos__estado=estado), distinct=True) for nombre, estado in ESTADOS_AVANCE}`. Leer `conteo` como dict en vez de `setattr` sobre el modelo.
- **Lo que NO hay que hacer:** juntar las dos consultas de `reporte_avance` en una: el comentario `:158-161` mide por qué se separaron (225 ms).
- **Tests a agregar:** los existentes de `reportes_becas` alcanzan; agregar un snapshot de filas si no hay.
- **Verificación:** mismas filas y mismo `assertNumQueries`.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md` · «Bloques de anotación o de inicialización repetidos que solo cambian una constante se generan desde una tupla».

---

### B-LIM-49 · Tres escritores del mismo CSV/XLSX en `exportacion_reportes.py` y artefacto de la conversión a LF
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** RED-82 (la conversión dejó el archivo con una línea en blanco entre sentencias) · **Ola:** 10 · **Esfuerzo:** S
- **ID de la pasada 1:** B2-LIM-11
- **Ubicación:** `programas/services/exportacion_reportes.py:37-74` (`respuesta_libro`), `:88-108` (`_trozos_del_csv`), `:152-199` (`respuesta_reporte`); líneas en blanco intercaladas en `:29-74` y `:152-199`. Consumidor que valida tarde: `programas/views/reportes_becas.py:133-142`.
- **Escenario:** BOM, fila de alcance, línea en blanco y encabezados saneados se escriben en tres lugares: `respuesta_reporte(csv)` duplica `_trozos_del_csv` («el mismo CSV», dice su docstring) y `respuesta_reporte(xlsx)` duplica `respuesta_libro` con una sola hoja «Reporte». Un cambio de saneo (SEC-20, RED-70) se tiene que replicar tres veces. Además, `ReporteBecasExportView.get` arma el reporte completo (incluido el padrón de beneficiarios) y recién después `respuesta_reporte` devuelve 400 por formato inválido (`<str:formato>` en `programas/urls.py:26`).
- **Causa raíz:** el streaming (PERF-03) se agregó al lado de lo existente en vez de reemplazarlo.
- **Solución:** `respuesta_reporte(csv)` = `HttpResponse("".join(_trozos_del_csv(reporte, alcance)))` con los mismos headers; `respuesta_reporte(xlsx)` = `respuesta_libro([("Reporte", reporte)], nombre, alcance)`. Validar `formato in ("csv", "xlsx")` en la vista antes de calcular. Quitar las líneas en blanco intercaladas (cosmético, pero hoy oculta la estructura del archivo).
- **Lo que NO hay que hacer:** pasar todo a `StreamingHttpResponse` (tests y middlewares que leen `response.content`); cambiar el BOM.
- **Tests a agregar:** `programas/tests/test_exportacion_reportes.py::IgualdadTests.test_csv_en_memoria_y_streaming_son_identicos` (si no existe).
- **Verificación:** bytes de los CSV/XLSX de un fixture idénticos antes y después.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md` · «Un segundo camino de salida (streaming, otra hoja) se escribe componiendo el primero, no copiándolo».

---

### B-LIM-50 · El contrato de `Datos` son dicts sueltos que tres consumidores leen por nombre
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 10 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B2-LIM-12
- **Ubicación:** `programas/services/dashboard_becas.py:146-164` (`Datos` con `list`/`dict` sin forma), `:417-453` (16 claves de la fila de convocatoria), `:1198-1305` (`bloques_exportacion` las vuelve a listar a mano, `:1241-1260`); `static/custom/js/becas-dashboard.js:598-646`; fallbacks silenciosos `getattr(programa, "valida_siis", True)` (`:637`, `valida_siis` es propiedad de `ProgramaSiis`, `programas/models/__init__.py:2665`) y `getattr(conv.segmento, "nombre", "")` (`:435`).
- **Escenario:** renombrar `revisado_pct` en `_tabla_convocatorias` deja la columna del CSV con `KeyError` (500 en el export) y la del JS en `NaN %`; nada lo detecta salvo un test end-to-end. Los encabezados del bloque «convocatorias» (`:1223-1240`) y el orden de las claves (`:1242-1259`) son dos listas paralelas de 16 elementos.
- **Causa raíz:** sin tipo para las filas; la columna (clave + encabezado) no está definida una sola vez.
- **Solución:** `TypedDict` por fila (`FilaConvocatoria`, `FilaEstado`, `EtapaEmbudo`…) en el módulo de métricas, y para el export una tupla de columnas `COLUMNAS_CONVOCATORIA = (("nombre", "Convocatoria"), ("segmento", "Segmento"), …)` de la que salen encabezados y filas. Quitar los `getattr` defensivos donde el atributo existe siempre.
- **Lo que NO hay que hacer:** cambiar las claves del JSON (las lee el JS y el test de contrato de `07-front.md:644`).
- **Tests a agregar:** `programas/tests/test_dashboard_becas.py::ContratoTests.test_claves_de_fila_coinciden_con_columnas_de_export`.
- **Verificación:** test anterior; el CSV de «convocatorias» idéntico.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md` · «Encabezados y claves de una tabla exportable se declaran como una sola tupla de pares».

---

### B-LIM-51 · El form del dashboard resuelve el catálogo de dominio y arma JSON de presentación
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 10 · **Esfuerzo:** S
- **ID de la pasada 1:** B2-LIM-13
- **Ubicación:** `programas/forms_reportes.py:17` (importa del servicio), `:155` (`self.preguntas = preguntas_graficables(user, programa)` en `__init__`), `:217-233` (`relevamientos_de` arma el dict para el JS, con el nombre del territorial); construido en cada render del detalle del programa (`programas/views/configuracion.py:331`) y en cada petición de datos/export.
- **Escenario:** el catálogo (preguntas globales, requisitos, ítems de diseño de todas las convocatorias en alcance) se calcula al construir el form aunque la solapa no se abra (el comentario de `configuracion.py:322-324` dice que los números se piden recién al abrir, RNF-1). La vista de datos depende de que el form traiga `preguntas` para pasarlo como `catalogo=` (`views/dashboard_becas.py:111`, `:159`): el form es el transporte de un dato de dominio.
- **Causa raíz:** el form se usó como contenedor del estado de la petición.
- **Solución:** el form valida `pregunta` contra un catálogo que recibe por parámetro (`DashboardBecasFiltroForm(..., preguntas=...)`); la vista lo obtiene del servicio. `relevamientos_de` pasa al servicio (o a `selectors/`) como `opciones_relevamiento(qs, convocatoria)`. En `configuracion.py` el catálogo se sigue resolviendo porque el `<select>` de preguntas se renderiza en el servidor (`_dashboard_panel.html:219`): no cambia ni el HTML ni las consultas de hoy, solo quién las hace.
- **Lo que NO hay que hacer:** cargar las preguntas por AJAX: cambia la pantalla.
- **Tests a agregar:** ajustar los del form.
- **Verificación:** mismas consultas en `configuracion` y en `programa_dashboard_datos`.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md` · «Un form valida; no consulta catálogos de dominio en `__init__` ni arma JSON para el front».

---

### B-LIM-52 · `armar_payload` (160 líneas) repite nueve veces «resolver → payload o faltante»
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 8 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B3-LIM-07
- **Ubicación:** `siis_envio.py:818-979`, en particular `869-875`, `878-889`, `923-934` (seis bloques casi idénticos de `_resolver_catalogo`).
- **Escenario:** cada campo resuelto contra catálogo repite `x = _resolver_catalogo(...)`, `if x is not None: payload[k] = x`, `else: faltantes[k] = "…"`. Agregar un campo del manual es copiar un bloque más dentro de una función que ya no entra en pantalla.
- **Causa raíz:** no hay un modelo de «campo del payload»; el contrato del manual vive como secuencia de `if`.
- **Solución:** una tabla declarativa para los campos homogéneos, `CAMPOS_CATALOGO = (("est_civil", "estado_civil_id", None, MENSAJE), ("prov_actual", "provincia_id", None, …), ("loc_actual", "localidad_id", "prov_actual", …), …)`, recorrida por un `for` que pasa la provincia ya resuelta como dependencia. Persona, domicilio, programa y apoderado quedan explícitos: tienen reglas propias (Cambio 89, Cambio 82, SIIS-12) que una tabla escondería.
- **Lo que NO hay que hacer:** meter en la tabla la regla del domicilio sin altura ni la del barrio. Son decisiones del PM y tienen que leerse de corrido.
- **Tests a agregar:** ninguno; `ArmarPayloadTests` existentes son la caracterización.
- **Verificación:** payload y faltantes idénticos sobre los fixtures existentes.
- **Regla para no repetirlo:** **skill** · rúbrica `codigo-limpio.md` · «Tres o más bloques `if valor: payload[k]=… else: faltantes[k]=…` seguidos piden una tabla de campos.»

---

### B-LIM-53 · El cliente repite la invalidación del token, el corte de configuración y la normalización de ítems
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 8 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B3-LIM-09
- **Ubicación:** `cache.delete(TOKEN_CACHE_KEY)` ante 401 en `siis.py:430-431`, `589-590`, `732`, `781-782`. Corte `falta_configuracion` en `438-447` y `600-612`. `_normalizar_catalogo` `491-513` vs `_normalizar_items` `627-645` (mismo `nombre or descripcion or denominacion` y mismo `int(id)`).
- **Escenario:** cada llamada HTTP arma `instrument_external_call("siis", sesion.X, url, headers=Bearer, timeout=…)` y después invalida a mano en el 401. Un endpoint nuevo que olvide el `delete` deja el token vencido en caché hasta su TTL y cada request paga un 401 (es el mismo defecto que SIIS-14 encontró en RENAPER).
- **Causa raíz:** el cliente no tiene un método de request único; cada operación habla con `sesion` directamente.
- **Solución:** `SiisAPIClient._request(metodo, path, *, timeout, **kw)` que pide el token, instrumenta y ante un 401 invalida; `_get`, `validar_compatibilidad` y `_intentar_alta` lo usan. Los `except` siguen en cada operación porque mapean a mensajes distintos. `_id_y_nombre(item, id_keys=("id",))` compartido por los dos normalizadores. `sesion` sigue siendo atributo del módulo `siis` (60 sustituciones en tests).
- **Lo que NO hay que hacer:** que `_request` también capture excepciones. `cargar_beneficiario` necesita distinguir conexión no abierta de conexión cortada (SIIS-02), y un `except` genérico lo aplanaría.
- **Tests a agregar:** `programas/tests/test_siis_cliente.py::Token401Tests.test_todo_endpoint_invalida_el_token_ante_401` (parametrizado).
- **Verificación:** `grep -c "cache.delete(TOKEN_CACHE_KEY)" programas/services/siis.py` == 2 (`_request` y el reintento de `cargar_beneficiario`).
- **Regla para no repetirlo:** **skill** · rúbrica `codigo-limpio.md` · «Toda llamada a SIIS pasa por `SiisAPIClient._request`; un `sesion.get/post` fuera de él es duplicado.»

---

### B-LIM-54 · La pausa del login convierte la excepción en un string y la vuelve a fabricar, con `requests.Response` falsos
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** SIIS-09 (cerrado) · **Ola:** 8 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B3-LIM-10
- **Ubicación:** `siis.py:309-322` (`_motivo_de_pausa`), `371-387` (`_error_de_pausa`), `405-407`, `415-417`.
- **Escenario:** el hilo de login guarda en caché `"timeout"`, `"connect"`, `"http:503"`, `"config"`, `"red"` u `"otro"`. Quien espera reconstruye una excepción de `requests`, y en el caso HTTP arma un `requests.Response()` vacío con `status_code` puesto a mano, para que los `except` de `_cargar_catalogo`, `validar_compatibilidad` e `_intentar_alta` la traten «como siempre». Es un acoplamiento invisible: si alguien agrega un `except requests.HTTPError` que lee `exc.response.json()`, explota con la respuesta fabricada.
- **Causa raíz:** el estado «login en pausa» no tiene tipo propio; se disfraza de la falla original.
- **Solución:** una sola excepción `SiisLoginEnPausa(Exception)` con `.motivo`, levantada por `_token`, y una tabla `MENSAJE_POR_MOTIVO` que usan los tres handlers. Cada handler agrega un `except SiisLoginEnPausa as exc:` antes de los de `requests`, y en `cargar_beneficiario` se clasifica como `NO_ENVIADO` (el POST no salió). Los textos al usuario no cambian.
- **Lo que NO hay que hacer:** heredarla de `requests.ConnectionError` para «ahorrar» los `except`. Volvería a esconder la causa, y en `_intentar_alta` el orden de `except` decide entre `NO_ENVIADO` e `INCIERTO`.
- **Tests a agregar:** `programas/tests/test_siis_token.py::PausaTests.test_cada_motivo_da_el_mismo_mensaje_que_antes` (parametrizado por los 6 motivos).
- **Verificación:** `grep -n "requests.Response()" programas/services/siis.py` vacío.
- **Regla para no repetirlo:** **skill** · rúbrica `codigo-limpio.md` · «No fabricar objetos de una librería (`Response`, `HTTPError`) para reutilizar un `except`: un estado propio lleva su excepción propia.»

---

### B-LIM-55 · `siis.py` (986 líneas, al borde del umbral) mezcla el cliente HTTP con la persistencia de catálogos en la base
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** SIIS-09 ronda 2 (copia local) · **Ola:** 8 · **Esfuerzo:** S
- **ID de la pasada 1:** B3-LIM-11
- **Ubicación:** `siis.py:647-667` (`SiisAPIClient.catalogo` escribe en la base con `guardar_catalogo_local`, `666`), `849-889` (padrón geográfico con ORM), `895-974` (copia local y refresco), `977-986` (textos de rechazo). Importa modelos de forma perezosa en `872`, `906`, `927`.
- **Escenario:** el próximo cambio de la integración cruza las 1.000 líneas. Hoy el «cliente» ya tiene un efecto en la base que no se ve desde su firma: llamar a `catalogo()` reescribe `CatalogoSiisLocal`.
- **Causa raíz:** la copia local se agregó junto al cliente porque el cliente era quien la refrescaba.
- **Solución:** `services/siis_catalogos_locales.py` con `catalogo_geografico`, `_leer_padron_geografico`, `claves_padron_geografico`, `guardar_catalogo_local`, `catalogo_local`, `refrescar_catalogos_locales`, y re-export desde `siis.py`. `SiisAPIClient.catalogo` conserva el efecto (lo usa el masivo para mantener la copia al día, `catalogo_local` docstring `919-921`), pero lo recibe inyectado: `catalogo(nombre, al_leer=guardar_catalogo_local)`. Mismo comportamiento, dependencia explícita. `siis.py` baja a unas 840 líneas.
- **Lo que NO hay que hacer:** sacar `sesion` o `SiisAPIClient` de `siis.py`, porque los tests sustituyen `programas.services.siis.sesion` 60 veces.
- **Tests a agregar:** ninguno; `test_catalogo_local*.py` caracteriza.
- **Verificación:** `wc -l programas/services/siis.py` < 900, suite en verde.
- **Regla para no repetirlo:** **control mecánico** · el ratchet de B-LIM-20 con umbral de **aviso** en 900 líneas, para que el archivo se parta antes de cruzar.

---

### B-LIM-56 · `_localidades_csv_siis.py` es dominio escondido en `management/commands`, con `CommandError` y una segunda copia de la regla de cruce de localidades
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 8 · **Esfuerzo:** S
- **ID de la pasada 1:** B3-LIM-15
- **Ubicación:** `programas/management/commands/_localidades_csv_siis.py:111-120` (`claves_del_catalogo`, con ORM y «mismo criterio que `Catalogos._resolver_localidad`»), `138-170` (`armar_plan`), y los `CommandError` de `89`, `96`, `107`.
- **Escenario:** el módulo se define como «las piezas sin efectos» (`7-8`), pero consulta la base y levanta excepciones de comandos. Si la regla de resolución de `Catalogos._resolver_localidad` (`siis_envio.py:441-468`: alias por provincia → catálogo propio → API) cambia, el plan de carga sigue con la versión anterior y el organismo ve «no existe» para nombres que el alta sí resuelve.
- **Causa raíz:** el helper se extrajo del comando hacia el directorio del comando y no hacia `services/`.
- **Solución:** `services/siis_localidades.py` con `fila_sin_cruce`, `leer_csv_completado` (levanta `ValueError` y el comando la traduce a `CommandError`), `claves_del_catalogo` y `armar_plan`. La regla «¿esta clave cruza?» se expone como `Catalogos.clave_resoluble(clave)` en el módulo de catálogos y la usan las dos.
- **Lo que NO hay que hacer:** cambiar el criterio de `armar_plan` a la vez que se mueve. Primero mover, después alinear.
- **Tests a agregar:** `programas/tests/test_siis_localidades.py::PlanTests` (los que hoy entran por el comando, llamando a la función directo).
- **Verificación:** `grep -rn "CommandError" programas/services/` sin resultados nuevos.
- **Regla para no repetirlo:** **control mecánico** · `core/tests/test_capas.py` (o el ratchet de RED-79) · un archivo `management/commands/_*.py` que importe `django.db.models` o un modelo falla: «lógica de dominio en el directorio de comandos, va en `services/`».

---

### B-LIM-57 · Alias históricos, imports perezosos sin motivo y códigos de error sin constante
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 8 · **Esfuerzo:** S
- **ID de la pasada 1:** B3-LIM-16
- **Ubicación:**
  - Alias: `_base_siis.py:270` (`_responsable = _solicitante`), `siis_envio.py:375` (`_provincia_de = staticmethod(provincia_de)`), `siis_envio.py:518` (`_digitos = normalizar_dni`).
  - Envoltorios de módulo que instancian un cliente por llamada: `siis.py:829-892`.
  - Imports perezosos de `programas.models` cuando el módulo ya lo importa arriba: `siis_envio.py:414, 443, 618, 1301, 1426` (con `19`); `procesar_casos_siis.py:269` (con `62`).
  - `_lotes` duplicado: `_base_siis.py:279` y `proceso_masivo.py:1046`.
  - Literales de `codigo_error`: `"DUPLICADO_LOCAL"` en `siis_envio.py:1164` y `1495`, `"DATOS_INCOMPLETOS"` en `1098` y `1326`, `"ERROR_TECNICO"` en `1477` y `siis.py:743, 756, 761, 765`.
- **Escenario:** `mensaje_envio` decide el texto del toast comparando contra un literal que se escribió en otro lado. Si se renombra uno solo, el coordinador ve «SIIS no respondió» para un duplicado local, que manda a mirar a ECOM en vez de al caso. Los alias y los imports perezosos le hacen buscar al lector una razón que no existe (no hay ciclo de imports).
- **Causa raíz:** arreglos sucesivos que conservaron el nombre viejo «por las dudas».
- **Solución:** constantes `CODIGO_DUPLICADO_LOCAL`, `CODIGO_DATOS_INCOMPLETOS`, `CODIGO_ERROR_TECNICO` junto a `CODIGO_SIN_COPIA_CATALOGO`, o mejor como `EnvioSIIS.Codigo` (TextChoices sin migración, porque `codigo_error` es `CharField` libre). Borrar los alias y reemplazar los usos (dos llamadas a `_responsable`). Subir los imports al encabezado salvo `proceso_masivo` en `sincronizar_tabla_intermedia` (ese sí rompe un ciclo). Un solo `_lotes`. Los envoltorios de `siis.py` se conservan porque los usan vistas y tests, pero con una línea que diga por qué existen.
- **Lo que NO hay que hacer:** convertir `codigo_error` en `choices` con migración: hay códigos que vienen de SIIS y no se conocen de antemano.
- **Tests a agregar:** ninguno.
- **Verificación:** `grep -n '"DUPLICADO_LOCAL"\|"DATOS_INCOMPLETOS"' programas/services/siis_envio.py` con una sola aparición (la constante).
- **Regla para no repetirlo:** **control mecánico** · ruff `PLC0415` (`import-outside-toplevel`) activado en `pyproject.toml` para `programas/services/siis*.py`, con `# noqa: PLC0415 — ciclo con X` donde haga falta.

---

### B-LIM-58 · Las tres acciones de Cupo repiten el prólogo de autorización y no exigen POST
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 9 · **Esfuerzo:** S
- **ID de la pasada 1:** B4-LIM-08
- **Nota del juez:** NO es de seguridad. La escritura está dentro de `if request.method == "POST"` (`views/cupo.py:239`, `:265`, `:302`): un GET autorizado no muta nada y solo redirige. Queda BAJA (consistencia y prólogo repetido); no entra en la Ola 0.
- **Ubicación:** `programas/views/cupo.py:236-238`, `:261-264`, `:299-301`; `:239`, `:265`, `:302` (`if request.method == "POST"`).
- **Escenario:** `puede_alguna(..., [CAP_BENEFICIARIO_EDITAR], programa=programa_becas(...))` + `PermissionDenied` +
  `assert_alcance_formulario` copiado tres veces; un GET autorizado no hace nada y redirige, en vez de 405.
- **Solución:** `@login_required @require_POST @requiere(CAP_BENEFICIARIO_EDITAR)` (si `@requiere` ya evalúa con
  `programa_becas`, si no, un decorador local `_editar_beneficiarios`) y el `assert_alcance_formulario` como primera
  línea. **DECISIÓN JUEZ** el 405 en GET (hoy redirige con 302): si algún link hace GET, mantener el redirect.
- **Tests a agregar:** `programas/tests/test_cupo.py::AccionesCupoTests.test_get_no_muta`.
- **Regla para no repetirlo:** **skill** · `.claude/skills/seguridad-django/`: «vista que muta → `@require_POST`».

---

### B-LIM-59 · Los desenlaces de la aprobación viajan como strings sueltos en seis módulos
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 9 · **Esfuerzo:** S
- **ID de la pasada 1:** B4-LIM-10
- **Ubicación:** `programas/services/cupo.py:369,372,403` (devuelve `"aprobado"`/`"lista_espera"`);
  `proceso_masivo.py:857` (compara `"lista_espera"`), `:836` (devuelve `"tecnico"` al lado de `FALLA_TECNICA`, `:263`);
  `views/revision.py:977,1000`; `avisos_resolucion.py:41-44` y `alta_de_oficio.py:51` (constantes redefinidas);
  `templates/programas/becas/email/resolucion_body.*` (comparan literales).
- **Escenario:** un typo en cualquier comparación cae al `else` en silencio (en el correo, el `else` es el texto de
  **rechazo**).
- **Solución:** `class Resolucion(models.TextChoices)` en `programas/services/cupo.py` (`APROBADO`, `LISTA_ESPERA`,
  `RECHAZADO`, `PROMOVIDO`) — los valores no cambian, así que la traza y las plantillas siguen igual —; `avisos_resolucion`
  y `alta_de_oficio` la importan; `procesar_caso` devuelve `FALLA_TECNICA` en `:836`. En `procesar_caso` las dos llamadas
  a `enviar_aviso_resolucion` (`:860-861`, `:864-865`) quedan en una, antes de distinguir el desenlace.
- **Regla para no repetirlo:** **control mecánico** · test que hace `grep` de `== "aprobado"|== "lista_espera"` en
  `programas/services` y `programas/views` y falla.

---

### B-LIM-60 · La aprobación con cupo está escrita tres veces en `cupo.py`
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 9 · **Esfuerzo:** S
- **ID de la pasada 1:** B4-LIM-11
- **Ubicación:** `programas/services/cupo.py:294-313` (`promover_lista_espera`), `:357-372` (`aprobar_o_poner_en_espera`),
  `:389-403` (`aprobar_de_oficio`); mensajes literales repetidos `:296`≡`:397`, `:358`≡`:390`; `espera_activa` (`:91-93`)
  existe y `:339` y `:434` vuelven a escribir el mismo filtro.
- **Escenario:** «chequear cupo → CAS `ENVIADO→APROBADO` → traza» tres veces con variaciones (la promoción suma la traza de
  la fila, la de oficio la marca). Un cambio en la regla de cupo (p. ej. BEC-05 si se decide aplicar el subsegmento)
  se tiene que hacer en tres sitios.
- **Solución:** `_aprobar_con_cupo(formulario, segmento, user, *, sin_cupo, cambios_extra=())` que hace cupo + CAS +
  traza **después** de los candados; `sin_cupo` es `"error"` o `"espera"`. Los candados se quedan escritos en cada
  función pública.
- **Lo que NO hay que hacer:** meter el `select_for_update` en el helper: el contrato de RED-67 exige que lo pida la
  función que tiene que pedirlo (está escrito en `cupo.py:21-24`).
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md`: «mensaje de error literal repetido en el mismo
  módulo = constante o helper».

---

### B-LIM-61 · `correr()` repite cinco veces el cierre de la corrida y `_lotes` existe cinco veces en `programas`
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 9 · **Esfuerzo:** S
- **ID de la pasada 1:** B4-LIM-12
- **Ubicación:** `programas/services/proceso_masivo.py:1123-1163` (cinco `_guardar(..., estado=…, finalizada=timezone.now(),
  mensaje=…)`; tres `except` que solo cambian el mensaje); `_lotes` en `proceso_masivo.py:1046`,
  `completar_casos_renaper.py:139`, `_base_siis.py:279`, `dashboard_becas.py:1467`, `reportes_becas.py:453`.
- **Solución:** `_cerrar(corrida, cuenta, estado, mensaje="")` y los tres `except` en uno que arma el mensaje con un
  dict `{CatalogoNoDisponible: "No se pudo leer un catálogo de SIIS: {}", TablaAprobadosMateriasFaltante: "{}",
  Exception: "Error no previsto: {}"}` (mismo texto). `_lotes` → `itertools.batched` (Python 3.12, el del CI) o un
  `core.utils.lotes` donde haga falta la numeración.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md` helpers canónicos: «partir en lotes →
  `itertools.batched`».

---

### B-LIM-62 · Lanzar el masivo lee la planilla entera solo para saber si existe; tres formas de preguntar por una tabla
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** continuación de PERF-07 (resuelto en el GET, no en el POST) · **Ola:** 9 · **Esfuerzo:** S
- **ID de la pasada 1:** B4-LIM-13
- **Ubicación:** `programas/views/proceso_masivo.py:192` (`servicio.dnis_aprobados_materias()` dentro de un `try` para
  detectar la excepción); `proceso_masivo.py:103,152` (`introspection.table_names()`);
  `completar_casos_renaper.py:181-186` (`information_schema.tables`).
- **Escenario:** el POST trae los ~15.500 DNI a memoria y los tira; `hay_aprobados_materias()` existe para eso (PERF-07).
- **Solución:** `if not servicio.hay_aprobados_materias(): messages.error(request, str(servicio.TablaAprobadosMateriasFaltante()))`
  (mismo mensaje). Un `core.db.existe_tabla(nombre)` para los tres sitios.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md`: «chequear existencia por excepción de una lectura
  completa es un anti-patrón; usar el predicado».

---

### B-LIM-63 · Ciclo `proceso_masivo` ↔ `siis_envio` escondido con un import diferido
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** RED-79 (ciclos de import) · **Ola:** 9 · **Esfuerzo:** S
- **ID de la pasada 1:** B4-LIM-14
- **Ubicación:** `programas/services/proceso_masivo.py:34-42` importa `siis_envio`; `programas/services/siis_envio.py:1427`
  importa `proceso_masivo.dnis_a_no_enviar` dentro de la función.
- **Solución:** con el corte de B-LIM-28, `siis_envio` importa de `insumos_siis` (que no depende de nadie) arriba del
  módulo y el import diferido desaparece.
- **Regla para no repetirlo:** **control mecánico** · el ratchet de RED-79 cuenta también los imports diferidos entre
  `programas/services/*`.

---

### B-LIM-64 · `inscribir_de_oficio` reimplementa dos veces el freno por errores seguidos
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 9 · **Esfuerzo:** S
- **ID de la pasada 1:** B4-LIM-15
- **Ubicación:** `programas/management/commands/inscribir_de_oficio.py:124-135` y `:154-165`.
- **Escenario:** dos contadores a mano de «N errores técnicos seguidos» con resets distintos (en seco, una fila sin
  resultado resetea; aplicando, cualquiera sin `error_tecnico`), mientras `proceso_masivo.Freno` ya modela la racha.
- **Solución:** `Freno(max_errores=opciones["max_errores"])` y `freno.registrar(FALLA_TECNICA if r.error_tecnico else None)`
  en los dos bucles (conservar la regla de reset de cada uno, que coincide con la de `Freno`).
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md` helpers canónicos: «racha de errores → `Freno`».

---

### B-LIM-65 · Cada vista bifurca AJAX/clásico a mano y `subsegmento_crear/editar` repiten el mismo bloque
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 12 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B5-LIM-05
- **Ubicación:** 26 ramas `is_ajax(...)` en `programas/views/configuracion.py`; duplicado textual entre
  `subsegmento_crear` (`:529-569`) y `subsegmento_editar` (`:574-622`): mismo `IntegrityError` → `add_error` → AJAX o
  render, mismo armado del panel `#subs-panel` con `sum(s.cupo_maximo …)`. Contexto de choices repetido en cinco vistas:
  `:319-321`, `:505-507`, `:935-937`, `:970-972`, `:1157-1159` (y `programas/views/diseno.py:139-141`).
- **Escenario:** el cálculo de `subsegmentos_cupo_total` está en tres lugares (`:470`, `:552`, `:600`); si cambia (por
  ejemplo, excluir eliminados), uno queda viejo y el panel repintado por AJAX muestra otro total que el detalle.
- **Causa raíz:** no hay un helper que encapsule «form válido → respuesta ok según el canal / inválido → errores según el
  canal».
- **Solución:** en `programas/views/ajax_utils.py` (ya exento del ratchet): `responder_form(request, form, *, ok,
  plantilla, contexto)` donde `ok` es un callable que devuelve la respuesta de éxito; `_subsegmentos_panel_ajax(request,
  segmento, message)` único; `choices_de_campo()` en `programas/views/configuracion/_comun.py` que devuelve
  `{presentacion_choices, canal_choices, destino_siis_choices}` y se hace `ctx.update(...)`.
- **Tests a agregar:** ninguno nuevo: los de las vistas cubren los dos canales.
- **Verificación:** `grep -c "is_ajax(" programas/views/configuracion*` baja a menos de 10.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md`: «Tres vistas con el mismo `if is_ajax: … else:
  render(...)` alrededor de un form = usar `responder_form` de `ajax_utils`.»

---

### B-LIM-66 · `forms_dinamicos`: el tipo de campo se compara contra cadenas sueltas en una cadena de `if`
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 12 · **Esfuerzo:** S
- **ID de la pasada 1:** B5-LIM-10
- **Ubicación:** `programas/forms_dinamicos.py:204-252` (`_field_para_campo`: `"INT"`, `"SELECTOR"`,
  `"SELECTOR_MULTIPLE"`, `"DATE"`, `"FIRMA"`, `"ARCHIVO"`), `:213`, `:330`; el mismo módulo usa `TipoCampo.FIRMA` y
  `TipoCampo.con_adjunto()` en `:137-143`.
- **Escenario:** renombrar o agregar un tipo en `TipoCampo` no rompe nada en este archivo: el campo nuevo cae en el
  `CharField` por defecto en silencio.
- **Causa raíz:** fábrica escrita antes de que existieran los helpers de `TipoCampo`.
- **Solución:** `TipoCampo.X` en todas las comparaciones y un dict `_FABRICAS = {TipoCampo.INT: _field_int, …}` con el
  default explícito para `STRING`; mismo resultado para cada tipo.
- **Tests a agregar:** `programas/tests/test_forms_dinamicos.py::FabricaTests.test_cada_tipo_tiene_fabrica`
  (`set(TipoCampo.values) <= set(_FABRICAS) | {TipoCampo.STRING}`).
- **Verificación:** `grep -n '== "SELECTOR"' programas/forms_dinamicos.py` vacío.
- **Regla para no repetirlo:** **control mecánico** · test de arriba: un `TipoCampo` sin fábrica falla.

---

### B-LIM-67 · Dos modelos de borrado para la misma jerarquía de Becas
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** Cambio 489 (consecuencia registrada) · **Ola:** 12 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B5-LIM-11
- **Ubicación:** borrado físico con `ProtectedError` en `programas/views/configuracion.py:663-678`
  (`subsegmento_eliminar`) y `:794-819` (`requisito_eliminar`); borrado lógico en cascada en
  `programas/services/eliminacion.py:117-145`, que **también** marca subsegmentos (`:90`, `:106`). Parche de mensajes por
  la mezcla: `configuracion.py:635-660` (`_motivo_subsegmento_protegido`, rama «convocatoria eliminada»).
- **Escenario:** el mismo subsegmento se «elimina» de dos maneras según desde dónde: desde el segmento queda marcado y
  oculto; desde su panel se borra de la base o no se puede porque lo protege una convocatoria que ya nadie ve. Cada caso
  nuevo suma una rama más al traductor de `ProtectedError`.
- **Causa raíz:** el Cambio 489 introdujo la baja lógica de arriba hacia abajo y dejó afuera los ABMs de subsegmento y
  requisito, que siguen en la vista.
- **Solución:** mudar los dos borrados a `services/eliminacion.py` (`eliminar_subsegmento`, `eliminar_requisito`) que
  devuelven un motivo o levantan `EliminacionBloqueada`, conservando la semántica física de hoy.
  `DECISIÓN CLIENTE: por defecto, mantener el borrado físico de subsegmento y requisito (solo cambia de capa); pasarlos a
  baja lógica es una decisión de producto aparte.`
- **Tests a agregar:** `programas/tests/test_eliminacion_becas.py::SubsegmentoTests.test_protegido_por_convocatoria_eliminada_da_motivo`.
- **Verificación:** `configuracion.py` sin `except ProtectedError`.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md`: «Todo borrado de la estructura de Becas pasa por
  `services/eliminacion.py`; una vista con `except ProtectedError` es un borrado fuera de su dueño.»

---

### B-LIM-68 · `gestionar_pausa` resuelve el alcance con `isinstance` en la vista y arrastra un desfasaje de nombres
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — · **Ola:** 12 · **Esfuerzo:** S
- **ID de la pasada 1:** B5-LIM-12
- **Ubicación:** `programas/views/pausas.py:16-35` (`TIPOS` y `_segmento_de` con cinco `isinstance`), `:45-56`
  (reglas de alcance), `:71-75` (comentario que explica que `tipo` de la URL ≠ `model_name` salvo «programa» →
  «programasiis»).
- **Escenario:** sumar un pausable nuevo exige tocar el dict, la cadena de `isinstance` y recordar el desfasaje de
  `tipo_entidad`, en una vista. `services/eliminacion.py:84-99` resuelve la misma jerarquía por su cuenta.
- **Causa raíz:** el «segmento dueño de un objeto de Becas» no tiene una función en `services/autorizacion.py`.
- **Solución:** `autorizacion.segmento_de(objeto)` (la función actual, mudada) y `assert_puede_pausar(user, objeto)`;
  `TIPOS` pasa a `{tipo: (modelo, url_detalle)}` y el historial usa `modelo._meta.model_name` desde el dict, sin
  comentario explicativo.
- **Tests a agregar:** `programas/tests/test_pausas.py::AlcancePausaTests.test_segmento_de_cada_tipo`.
- **Verificación:** `views/pausas.py` sin `isinstance`.
- **Regla para no repetirlo:** **skill** · `.claude/skills/seguridad-django/`: «El alcance de un objeto (a qué segmento
  pertenece) se resuelve en `services/autorizacion.py`, nunca en la vista.»

---

### B-LIM-69 · `programas/services/becas.py` es un cajón de sastre: definición, lookups por UUID, alcance, trazas y legajo
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** RED-79 (el ciclo `becas ↔ diseno` sigue en `CICLOS_CONOCIDOS`) · **Ola:** 13 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B6-LIM-08
- **Ubicación:** `programas/services/becas.py` (532 líneas): definición del formulario `:29-248`; lookups idempotentes
  `:251-292`; alcance de coordinador `:301-320`; trazas `:323-357`; resolución del legajo `:360-532`
  (`resolver_ciudadano_offline`, `_anotar_identidad_acreditada`, `_completar_contacto`); reexport de
  `q_uuid_en_texto` `:13`. `programas/services/diseno.py:687` importa los privados `_alcance_requisito` y
  `_campo_dict`, que es el ciclo.
- **Escenario:** el nombre del módulo no dice nada de lo que hay adentro; `campo.py`, `respuestas.py`,
  `inscripcion_publica.py` y la API importan de `becas` cosas sin relación entre sí, y cada import diferido existe
  para esquivar el ciclo.
- **Solución:** sin cambiar cuerpos: `programas/services/definicion.py` (todo `:29-248` + `_alcance_requisito`, con
  los dos privados pasados a públicos — rompe el ciclo con `diseno`), `programas/services/legajo_del_caso.py`
  (`:360-532`), `trazas_de`/`registrar_traza` a `programas/services/trazas.py`, alcance a `autorizacion` (B-LIM-45).
  `becas.py` queda como fachada de reexports con un comentario de vencimiento, y el test de ciclos baja de 5 a 4.
- **Lo que NO hay que hacer:** borrar los reexports en el mismo PR (media docena de módulos y tests importan de
  `becas`): eso es un PR aparte, como dice el propio comentario de `:9-12`.
- **Tests a agregar:** ninguno nuevo; `programas/tests/test_arquitectura.py::ImportsTests.test_no_hay_ciclos_nuevos`
  con `becas ↔ diseno` fuera de `CICLOS_CONOCIDOS`.
- **Verificación:** suite de `programas` y `portal` en verde; el ratchet de ciclos rojo si alguien saca el ciclo de la
  lista sin moverlo (ya falla en las dos direcciones).
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md`: «Un módulo de `services/` se nombra por el concepto que
  posee; `becas.py`/`utils.py` no reciben funciones nuevas».

---

### B-LIM-70 · Tres escrituras de «el caso que ocupa este DNI» y envoltorios que solo renombran
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo; Origen oct.: SIIS-13 (🟡 abierto, D-S13: «el caso que ocupa este DNI») · **Ola:** 13 · **Esfuerzo:** S
- **ID de la pasada 1:** B6-LIM-09
- **Ubicación:** consulta doble `dni_titular` / `ciudadano__dni` (la optimización del Cambio 91) escrita en
  `programas/api/views.py:84-91` (`_formulario_por_dni`, por relevamiento), `programas/services/inscripcion_publica.py:62-69`
  (`caso_en_convocatoria`) y `:72-96` (`dni_en_convocatoria`). Envoltorios identidad: `views.py:94-95`
  (`_formulario_dni_existe`), `:101-103` (`_formulario_por_client_uuid` → `formulario_por_client_uuid_global`),
  `:131-132` (`_mensaje_pausa` → `campo.mensaje_pausa`), `portal/services/inscripcion.py:105`
  (`dni_ya_inscripto = dni_en_convocatoria`, importado además por
  `programas/management/commands/diagnosticar_integraciones.py:303`).
- **Escenario:** si mañana el DNI del legajo deja de corregirse por fuera (o se suma una tercera columna), la consulta
  doble se arregla en un lado y el chequeo de duplicados de la app y del link dejan de decir lo mismo. Los envoltorios
  obligan a seguir dos saltos para leer qué regla se aplica.
- **Solución:** `programas/services/casos.py` (o `alta_caso.py` de B-LIM-41) con
  `casos_con_dni(queryset, dni) -> Formulario | None` y `hay_caso_con_dni(queryset, dni) -> bool`, que reciben el
  queryset ya acotado (`relevamiento.formularios` o `_formularios_que_ocupan_el_dni(convocatoria)`). Borrar los cuatro
  envoltorios y llamar al canónico; `dni_ya_inscripto` se reemplaza por `dni_en_convocatoria` en el portal y en el
  comando.
- **Tests a agregar:** `programas/tests/test_casos.py::DniTests.test_encuentra_por_columna_y_por_legajo_corregido`
  (sobre los dos querysets).
- **Verificación:** `grep -rn 'ciudadano__dni=dni' programas portal` → solo el helper.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md`, regla 4: «Un `def _x(...): return y(...)` o `x = y` sin
  argumento ni transformación propia se borra en la revisión».

---

### B-LIM-71 · Coherencia Provincia-Localidad: el link valida contra la caché y la API contra la base viva
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura); la divergencia, solo dentro del TTL de 1 h tras un cambio en el ABM (PLAUSIBLE) · **Eje:** LIM · **Origen:** nuevo (Cambio 418) · **Hallado por 2 revisores** (B6-LIM-10 + B6-PERF-04); origen de la absorbida: B6-PERF-04: auditoría B6 · **Ola:** 13 · **Esfuerzo:** S
- **ID de la pasada 1:** B6-LIM-10 + B6-PERF-04 (**hallado por 2 revisores**)
- **Ubicación:** `programas/services/catalogo_geografico.py:51-54` (`localidad_pertenece`, caché de
  `catalogos_geograficos`, TTL `:20`) usada por `portal/forms/inscripcion.py:284`; `:57-59`
  (`par_coherente_en_catalogo`, consulta en vivo) usada por `programas/services/campo.py:649`.
- **Escenario:** el ABM agrega o renombra una localidad. Durante la hora siguiente la app de campo **recibió** las
  opciones de la caché (`definicion_formulario` → `catalogos_geograficos`), el territorial elige la localidad que el
  servidor le ofreció y la revisión la marca como «no es de la provincia» porque la base viva ya cambió; o al revés.
  Dos reglas para la misma pregunta, en dos canales.
- **Causa raíz:** la segunda función se agregó «para observar una carga por API» sin reutilizar la primera.
- **Solución:** `campo._observaciones_de_catalogo` usa `localidad_pertenece(provincia, localidad)` (la misma caché con
  la que se sirvieron las opciones) y se borra `par_coherente_en_catalogo`. Es solo una **observación** en la API
  (G1-05), no un rechazo, así que no hay riesgo para la cola offline. Ahorra además una consulta por campo de
  localidad en cada alta.
- **Lo que NO hay que hacer:** validar con la base viva también en el link: el `<select>` del navegador se llenó desde
  la caché (`nodo-cascada-geo.js`), y validar contra otra fuente vuelve a abrir la misma divergencia del otro lado.
- **Tests a agregar:** `programas/tests/test_app_de_campo.py::CatalogoGeoTests.test_la_observacion_usa_el_mismo_catalogo_que_se_sirvio`.
- **Verificación:** `grep -rn par_coherente_en_catalogo` → 0.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md`: «Lo que el servidor le sirvió al cliente como opciones
  es la misma fuente contra la que se valida su respuesta».

#### Aporte del segundo revisor (B6-PERF-04: par_coherente_en_catalogo consulta Localidad en vivo por nombre en cada captura sincronizada)
_Pasada 1: severidad INFO · estado CONFIRMADO (lectura) · esfuerzo S._

- **Ubicación:** `programas/services/catalogo_geografico.py:57-59`
- **Escenario:** cada alta de campo valida provincia/localidad con una consulta a Localidad por nombre de provincia y de localidad, sin usar el catálogo cacheado.
- **Crece con:** capturas sincronizadas (1 consulta por captura) sobre tabla fija (~8.779 filas) sin índice por nombre. No crece con el volumen de casos: INFO.
- **Causa raíz:** la validación no reutiliza el catálogo ya cacheado.
- **Solución:** resolver el par contra `catalogos_geograficos()`; mismo resultado, sin consulta.
- **Lo que NO hay que hacer:** agregar índice por nombre solo para esto.
- **Tests a agregar:** assertNumQueries del alta con caché caliente.
- **Verificación:** EXPLAIN con `medir_consultas_borde.py`; esperado type=ALL sobre ~8,8k filas, <5 ms.
- **Regla para no repetirlo:** — (caso puntual)

---

### B-LIM-72 · El paso 2 del link arma las respuestas dos veces con el mismo bucle
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 13 · **Esfuerzo:** S
- **ID de la pasada 1:** B6-LIM-11
- **Ubicación:** `portal/forms/inscripcion.py:234-241` (`_respuestas_de`, para el motor de condiciones en `clean`) y
  `:288-299` (`respuestas`, para la ingesta): el mismo bucle de `_serializar`/`valor_de_firma`, que solo difiere en
  saltear `_ocultos`. Además `:9-19` reexporta privados de `programas.forms_dinamicos` (`_field_para_campo`,
  `_validar_archivo`, `_attrs_buscador`, `_es_buscador`) con `noqa` «los importan los tests».
- **Escenario:** un cambio en cómo se serializa un valor (otra forma de firma, un tipo nuevo) se aplica en uno y no en
  el otro: el motor del servidor evalúa condiciones con un valor y la ingesta guarda otro.
- **Solución:** `respuestas(self, excluir=frozenset())` única; `clean` llama `self._respuestas(cleaned,
  excluir=frozenset())` y la salida `self._respuestas(self.cleaned_data, excluir=self._ocultos)`. Los tests que
  importan privados pasan a importarlos de `programas.forms_dinamicos` y se borra el reexport.
- **Tests a agregar:** `portal/tests/test_inscripcion_paso2.py::RespuestasTests.test_clean_y_salida_serializan_igual`.
- **Verificación:** `portal.tests` en verde.
- **Regla para no repetirlo:** **control mecánico** · `pyproject.toml` (ruff): activar `PLC2701` (import de nombre
  privado de otro módulo) con allowlist por archivo para lo existente.

---

### B-LIM-73 · Las migas de Becas duplican la capacidad que pide cada vista de destino
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 13 · **Esfuerzo:** S
- **ID de la pasada 1:** B6-LIM-12
- **Ubicación:** `programas/templatetags/becas_extras.py:68-72` (`_MIGA_CAP_*`), contra `capacidades_requeridas` de
  las vistas de destino (`programas/views/configuracion.py:251`, `:292`, `:371` y las de `views/relevamientos.py`).
- **Escenario:** el comentario `:64-67` lo dice: la miga ofrece el enlace solo si el usuario tiene la capacidad que
  pide la vista. Si una vista cambia su `capacidades_requeridas` (pasó con SEC-30), la miga sigue con la vieja y
  vuelve a mostrar un enlace que termina en 403 (o esconde uno válido). Nada lo detecta.
- **Solución:** derivar la capacidad de la vista: `resolve(reverse(url_name, args=…)).func.view_class
  .capacidades_requeridas` (memoizado por `url_name` en un `lru_cache` a nivel de módulo) y evaluar con el mismo
  `puede_alguna` que usa `CapacidadRequeridaMixin` (`core/rbac.py:1075`). Se borran las cinco constantes.
- **Tests a agregar:** `programas/tests/test_becas_migas.py::MigasTests.test_cada_miga_pide_lo_mismo_que_su_vista`
  (recorre los cinco `url_name`).
- **Verificación:** el test anterior; snapshots de detalle de Becas sin cambios (ojo: tocan el shell, regenerar solo
  si cambia el HTML, que no debería).
- **Regla para no repetirlo:** **control mecánico** · el test de arriba es el ratchet.

---

### B-FE-09 · 23 evaluaciones de `|puede:"..."` en templates del alcance que repiten decisiones de la vista
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** nuevo · **Ola:** 11 · **Esfuerzo:** S-M
- **ID de la pasada 1:** B1-FE-05
- **Ubicación:** templates de `revision/**` y `relevamientos/**`; ejemplo: `revision/_detalle/_acciones.html:1` y `revision/_detalle/_modales.html:1` (`formulario.estado == 'ENVIADO' and request.user|puede:"becas.revision.editar"`) cuando la vista ya calcula `puede_editar_caso`.
- **Escenario:** renombrar una capacidad del `CATALOGO` deja botones visibles que la vista rechaza (o al revés) sin error de template; cada evaluación además puede costar una consulta si la caché de permisos no está caliente.
- **Causa raíz:** el filtro `puede` es cómodo y se usó donde ya había flag.
- **Solución:** donde la vista ya calcula el flag, el template usa el flag; donde no, la vista lo calcula una vez (dict `permisos` en el contexto). Mismo HTML resultante.
- **Lo que NO hay que hacer:** quitar la guarda de la vista confiando en el template; cambiar visibilidad de ningún botón.
- **Tests a agregar:** test de visibilidad por rol para las acciones del detalle (si no existe).
- **Verificación:** snapshots intactos; `ConsultasDetalleTests` igual o menor.
- **Regla para no repetirlo:** control mecánico · `design_audit.py` · conteo de `|puede:` en `programas/templates/programas/becas/**` con ratchet.

---

### B-FE-10 · El JS reconstruye estructura partiendo textos compuestos por el servidor
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** — · **Ola:** 10 · **Esfuerzo:** S
- **ID de la pasada 1:** B2-FE-02
- **Ubicación:** `static/custom/js/becas-dashboard.js:303-316` (`pintarAlcance`: `String(alcance).split(' · ')`), `:136` (`rel.nombre.split(' · ')[0]`); productor: `programas/services/dashboard_becas.py:554` (`" · ".join(...)`).
- **Escenario:** una convocatoria o segmento llamado «Becas · Interior» se parte en dos chips («Becas» e «Interior») y el alcance muestra seis partes en vez de cinco. El servidor tiene las cinco partes separadas y las pega para que el cliente las vuelva a separar.
- **Causa raíz:** el JSON transporta el texto pensado para el encabezado del export (RN-16) en vez de la estructura.
- **Solución:** `Datos.alcance_partes: list[str]` (lo que hoy se une en `:554`), `alcance` sigue siendo el `" · ".join(alcance_partes)` para el export; el JS pinta `alcance_partes`. Para el relevamiento, mandar `nombre_corto` desde `relevamientos_de`.
- **Lo que NO hay que hacer:** cambiar el separador por otro carácter «que nadie use».
- **Tests a agregar:** `programas/tests/test_dashboard_becas.py::AlcanceTests.test_alcance_partes_con_separador_en_el_nombre`.
- **Verificación:** test anterior; `grep -n "split(' · ')" static/custom/js/becas-dashboard.js` vacío.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-frontend.md` · «Si el JS necesita partes, el servidor manda una lista; nunca `split` sobre un texto armado en Python».

---

### B-FE-11 · Porcentajes y umbrales de cupo recalculados en el JS
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** — · **Ola:** 10 · **Esfuerzo:** S
- **ID de la pasada 1:** B2-FE-03
- **Ubicación:** `static/custom/js/becas-dashboard.js:502-510`, `:525`, `:547` (porcentaje por estado y canal); `:258-263` y `:633-634` (umbrales 0,95 / 0,8 duplicados), `:263` y `:583` (mapa umbral→color duplicado); servidor: `programas/services/dashboard_becas.py:1201-1208` (el export calcula los mismos porcentajes con `_pct`), `:351-353` (`_con_choices` no los manda).
- **Escenario:** la pantalla redondea con `toLocaleString(maximumFractionDigits: 1)` sobre su propio cálculo y el CSV con `round(..., 1)` sobre otro; en los bordes (x,x5) pueden diferir en una décima. Cambiar el umbral de «cupo crítico» exige editar dos líneas del JS que no están juntas.
- **Causa raíz:** el servidor manda `pct` en embudo, localidades y respuestas, pero no en estados/canales; el JS completa lo que falta.
- **Solución:** `_con_choices` agrega `"pct": _pct(total, base)` (base = recibidos para estados y canales) y el JS lo pinta como hace con el embudo; `bloques_exportacion` lee `fila["pct"]`. En el JS, una sola `nivelCupo(ratio)` y un solo mapa `COLOR_NIVEL`, usados por el KPI y por `celdaMedidor`.
- **Lo que NO hay que hacer:** mover los colores al servidor.
- **Tests a agregar:** `programas/tests/test_dashboard_becas.py::MetricasTests.test_estados_y_canales_traen_pct`.
- **Verificación:** mismos números en pantalla y CSV sobre el fixture.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-frontend.md` · «Una cifra que también se exporta se calcula en el servicio; el JS solo la formatea».

---

### B-FE-12 · La pantalla de Cupo reimplementa la confirmación canónica (tres funciones y un form oculto por fila)
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** — · **Ola:** 9 · **Esfuerzo:** S
- **ID de la pasada 1:** B4-FE-01
- **Ubicación:** `programas/templates/programas/becas/cupo/segmento_detail.html:236-298` (`confirmarBaja`,
  `confirmarPromover`, `confirmarAgregarEspera`, casi idénticas) y los forms ocultos `:97-99`, `:155-157`, `:213-215`
  (uno por fila, cada uno con su `csrf_token`).
- **Escenario:** `programas/templates/programas/becas/_confirm_js.html` ya hace exactamente esto con `data-confirm-url`,
  `-title`, `-text`, `-ok`, `-danger` y además **bloquea el doble envío** (`confirmEnviado`), que la copia de Cupo no
  tiene (lo salvan los candados del servicio, no la pantalla).
- **Solución:** botones con `data-confirm-url="{% url … %}" data-confirm-title=… data-confirm-text=… data-confirm-ok=…
  data-confirm-danger=…` con los **mismos** textos de hoy (el nombre del ciudadano sigue yendo autoescapado en el
  atributo; ModernModal lo pinta con `textContent`), `{% include "programas/becas/_confirm_js.html" %}` y borrar el
  `<script>` y los forms ocultos. Mismo aspecto: ModernModal con los mismos parámetros.
- **Tests a agregar:** el snapshot de la pantalla de Cupo, si existe, se regenera; `compile_templates.py` en 0.
- **Verificación:** `design_audit.py --ratchet` 0 nuevos; si la pantalla tiene ficha en `.claude/design/`, actualizarla
  (`check_design_agent.py --base origin/development`).
- **Regla para no repetirlo:** **control mecánico** · `scripts/design_audit.py`: regla nueva «`ModernModal.show({type:
  'confirm'` dentro de un template que no es `_confirm_js.html` → usar `data-confirm-url`».

---

### B-FE-13 · Las plantillas del aviso deciden el texto comparando literales, duplicado entre `.txt` y `.html`
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** — · **Ola:** 9 · **Esfuerzo:** S
- **ID de la pasada 1:** B4-FE-02
- **Ubicación:** `programas/templates/programas/becas/email/resolucion_body.txt:3-7,12,15-18` y
  `resolucion_body.html:23,47,48,50,86,102-132`.
- **Escenario:** la misma ramificación de cuatro desenlaces está dos veces, con `resultado == "…"` literal y un `else`
  que pinta «no fue aprobada» para cualquier valor no previsto; agregar un desenlace es tocar seis `if` en dos archivos.
- **Solución:** que `enviar_aviso_resolucion` pase banderas ya resueltas (`es_aprobacion = resultado in {APROBADO,
  PROMOVIDO}`, `es_espera`, `es_rechazo`, `es_promocion`) y las plantillas usen `{% if es_espera %}`; el texto y el HTML
  no cambian. Test de paridad: cada clave de `ASUNTOS` renderiza `.txt` y `.html` sin caer en la rama de rechazo salvo
  `RECHAZADO`.
- **Tests a agregar:** `programas/tests/test_avisos_resolucion.py::PlantillasTests.test_cada_desenlace_tiene_su_rama`.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-frontend.md`: «una plantilla no compara strings de
  dominio: el contexto trae la bandera».

---

### B-FE-14 · Dos lectores DOM→respuestas para el mismo motor, uno sin el caso del archivo ya guardado
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** Origen oct.: RED-38 (abierto) · **Ola:** 12 · **Esfuerzo:** S
- **ID de la pasada 1:** B5-FE-03
- **Ubicación:** `static/custom/js/nodo-formulario.js:37-79` (link público, `portal/templates/portal/inscripcion/paso2.html`)
  y `static/custom/js/nodo-formulario-tipo.js:28-52` (Dispositivos, con la opción `archivoGuardado`). Servidor:
  `programas/forms_dinamicos.py:343-358` (`_respuestas_de`: un adjunto ya guardado cuenta como respondido).
- **Escenario:** hoy el link público no tiene adjuntos guardados, así que no se nota. Si `nodo-formulario.js` se usa en
  una pantalla con guardados (una reedición, una revisión), una condición «fue adjuntado» oculta y **deshabilita** el
  campo dependiente en el navegador mientras el servidor lo considera visible y obligatorio: la persona recibe «Este dato
  es obligatorio» sobre algo que no ve.
- **Causa raíz:** `nodo-formulario-tipo.js` generalizó el lector con opciones y el original quedó.
- **Solución:** reemplazar el cuerpo de `nodo-formulario.js` por `NodoFormularioTipo.montar(form, {archivoGuardado:
  false})` (o mover `valorDe` a `nodo-condiciones.js` como `NodoCondiciones.leerRespuestas(form, items, opciones)`), sin
  cambiar el comportamiento del link.
- **Tests a agregar:** `programas/tests/js/lector_respuestas.cjs` con jsdom mínimo, o caso en el harness existente.
- **Verificación:** un solo `querySelectorAll('input[type="checkbox"]')` de lectura de respuestas en `static/custom/js/`.
- **Regla para no repetirlo:** cubierta por la regla de B-FE-07 (todo espejo del motor vive en `nodo-condiciones.js`).

---

### B-FE-15 · JS inline en templates de configuración y helpers reimplementados por archivo
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** — · **Ola:** 12 · **Esfuerzo:** S
- **ID de la pasada 1:** B5-FE-05
- **Ubicación:** `programas/templates/programas/becas/config/proceso_masivo.html:190-294` (105 líneas: confirmación con
  `ModernModal`, guarda anti doble envío y relectura periódica); `pregunta_form.html:30-56` (tercera copia de
  `TIPOS_CON_OPCIONES`, junto a `_tipo_selector_js.html:13` y los `x-show` de B-FE-08); `csrfToken` reimplementado en
  `static/custom/js/nodo-constructor.js:23-27`, `nodo-catalogo-grupos.js`, `becas/_ajax_js.html` y `becas/_confirm_js.html`;
  `confirmar` propio en `nodo-constructor.js:334-352`.
- **Escenario:** la guarda de doble envío de POP-6 (ventana de 400 ms, foco en Cancelar) vive solo en el masivo; la
  próxima acción irreversible con confirmación la va a reescribir o no la va a tener. El JS en templates no pasa por
  ningún lint ni test.
- **Causa raíz:** cada pantalla resolvió su confirmación y su CSRF localmente.
- **Solución:** `static/custom/js/becas-confirmar-envio.js` con `interceptar(form, armarOpciones)` (el código actual,
  mudado), configurado por `data-` desde el template; el masivo conserva sus textos. Un `csrfToken()` único expuesto en
  `window` por el script base de Becas y consumido por los demás. `TIPOS_CON_OPCIONES` por `json_script`.
- **Tests a agregar:** ninguno obligatorio; los de POP-6 existentes sobre el masivo siguen verdes.
- **Verificación:** `proceso_masivo.html` sin bloque `<script>` de más de 10 líneas.
- **Regla para no repetirlo:** **control mecánico** · `scripts/design_audit.py`: regla `SCRIPT-INLINE-LARGO` (ratchet):
  un `<script>` sin `src` de más de 40 líneas en `templates/` → «movelo a `static/custom/js/` y configuralo con `data-`».

---

### B-FE-16 · `nodo-firma.js` observa todo el documento y recorre el DOM en cada mutación de cualquier página
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** nuevo · **Ola:** 13 · **Esfuerzo:** S
- **ID de la pasada 1:** B6-FE-01
- **Ubicación:** `static/custom/js/nodo-firma.js:110` (`new MutationObserver(...).observe(document.documentElement,
  { childList: true, subtree: true })`) que llama a `pintarFondos()` → `querySelectorAll('[data-firma-canvas]')`
  (`:91-104`) por cada lote de mutaciones.
- **Escenario:** en el paso 2 del link, `nodo-cascada-geo.js` vacía y llena el `<select>` de localidades (hasta 8779
  `<option>`) en cada cambio de provincia, y cada lote dispara el recorrido completo del documento aunque el formulario
  no tenga firma. El observer queda vivo también en todas las pantallas del backoffice que cargan el script.
- **Solución (mismo comportamiento):** filtrar los registros: solo correr `pintarFondos(nodo)` sobre los
  `addedNodes` que sean o contengan `[data-firma-canvas]`
  (`registros.forEach(r => r.addedNodes.forEach(n => n.nodeType === 1 && (n.matches('[data-firma-canvas]') ||
  n.querySelector('[data-firma-canvas]')) && pintarFondos(n)))`). `pintarFondos` ya acepta `raiz`.
- **Tests a agregar:** — (sin harness JS en el repo; ver memoria E2E). Verificación manual con Playwright en el paso 2.
- **Verificación:** DevTools → Performance al cambiar de provincia en el paso 2: sin llamadas a `pintarFondos` si no
  hay firma.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-frontend.md`: «Un `MutationObserver` sobre
  `document` filtra `addedNodes` por el selector propio; no recorre el documento entero por mutación».

---

### B-FE-17 · `nodo-cascada-geo.js` depende del orden de carga de `nodo-formulario.js` y mide layout en cada `change` de cualquier campo
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** nuevo · **Ola:** 13 · **Esfuerzo:** S
- **ID de la pasada 1:** B6-FE-02
- **Ubicación:** `static/custom/js/nodo-cascada-geo.js:88-90` (comentario: «Este script carga después, así que su
  listener corre después» — el contrato con `nodo-formulario.js` es el orden de los `<script>`), `:99-115` (listener de
  `change` sobre el documento que, para **cualquier** campo, recorre todos los selects de localidad y llama a
  `visible()` → `getClientRects()`, layout forzado), `:36-42` (`todas`: deduplica y ordena con `localeCompare` las
  ~8779 localidades en cada carga de página, se usen o no).
- **Escenario:** reordenar los `<script>` del template (o cargar `nodo-formulario.js` con `defer`) hace que la pasada
  inicial vea visible una Provincia que la condición va a ocultar y la Localidad arranca en el modo equivocado, sin
  error. Cada tecla que dispara `change` en un formulario largo fuerza layout por cada localidad.
- **Solución (mismo comportamiento):** `nodo-formulario.js` emite `document.dispatchEvent(new
  CustomEvent('nodo:condiciones-aplicadas'))` al terminar de aplicar condiciones (hoy no emite ningún evento); la
  cascada reevalúa el modo **solo** en ese evento y en el `change` de su Provincia, y deja de escuchar todos los
  `change`. `todas` pasa a calcularse perezosamente la primera vez que se necesita, con un `Intl.Collator('es')`
  reutilizado.
- **Tests a agregar:** — (sin harness JS); caso de QA manual: Provincia oculta por condición al cargar con errores.
- **Verificación:** Playwright en el paso 2 con un diseño que oculta la Provincia; cambiar el orden de los `<script>`
  no cambia el resultado.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-frontend.md`: «Un script que depende de que otro
  haya corrido escucha un evento nombrado (`nodo:*`) que ese otro emite; nunca el orden de los `<script>`».

---

### B-PERF-14 · La tabla de casos del detalle de relevamiento pagina por OFFSET sobre filas anchas con join
**Severidad:** INFO · **Estado:** PLAUSIBLE · **Eje:** PERF · **Origen:** relacionado con PERF-13 (oct., cerrada por medición en Cambio 192): misma trampa de OFFSET, pero en otra pantalla y sin la página pk-first, así que no se descarta · **Ola:** 5 · **Esfuerzo:** S
- **ID de la pasada 1:** B1-PERF-03
- **Ubicación:** `programas/views/relevamientos.py:894-901` (`RelevamientoDetailView`,
  `rel.formularios.select_related("ciudadano").defer(...)` + `_paginate`).
- **Escenario:** relevamiento público de 20.000 casos, solapa «Personas relevadas», `?formularios_page=400`. La consulta
  es `... LEFT JOIN legajos_ciudadano ... WHERE relevamiento_id = X ORDER BY numero LIMIT 50 OFFSET 19950`: con el
  `LEFT JOIN` el motor no reordena, recorre `uniq_formulario_numero_relevamiento` en orden pero **lee la fila completa del
  caso y hace el `eq_ref` a ciudadano por cada una de las 19.950 filas que descarta**. Es la única tabla de casos de esta
  tajada que no usa «pk primero, hidratar después» (`programas/services/listados.py`): `revision_formularios`, mismo
  relevamiento y mismo orden, elige la página con `only("pk")` (índice cubriente). El banco solo mide la página 1 de esta
  ruta (`relevamiento_publico_detalle`).
- **Causa raíz:** el patrón de `listados.py` se aplicó a revisión, convocatoria y cupo, no a esta solapa.
- **Crece con:** casos del relevamiento × profundidad de página: O(offset) filas anchas + O(offset) lookups a
  `legajos_ciudadano`. Estimado: decenas a pocos cientos de ms en la última página con 20.000 casos; lejos del
  `read_timeout`, por eso INFO.
- **Solución (misma página, mismo orden):**
  `PaginadorConConteo(Formulario.objects.filter(relevamiento=rel).order_by("numero").values_list("pk", flat=True), 50, total=<COUNT>)`
  e `hidratar_pagina(pagina, Formulario.objects.select_related("ciudadano").defer("data", "respuestas", "definicion", "datos_siis"))`.
  Por `Formulario.objects.filter(relevamiento=...)`, no `rel.formularios.only(...)` (trampa 2 de la rúbrica).
- **Tests a agregar:** `programas/tests/test_mediciones_banco_ola4.py::DetalleRelevamientoTests.test_la_pagina_se_elige_proyectando_solo_el_pk`
  (el SQL con `OFFSET` no lleva `JOIN` ni más columnas que `id`).
- **Verificación:** medir antes de tocar: sumar a `_extra_targets()` de `scripts/perf_mysql/bench_mysql.py` la ruta
  `reverse("becas:relevamiento_detalle", args=[rel.pk]) + "?formularios_page=400&tab=formularios"` y correr
  `EXPLAIN ANALYZE` de la consulta paginada (esperado hoy: ~20.000 filas leídas en `programas_formulario` y otras tantas
  en `legajos_ciudadano`). Si da < 100 ms en frío, se cierra sin cambio, como PERF-13.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` §Consultas · «Toda tabla paginada de
  `Formulario` elige la página con `values_list("pk")` y la hidrata con `programas.services.listados.hidratar_pagina`; un
  `Paginator` directo sobre un queryset con `select_related` paga el `OFFSET` en filas anchas.»

---

### B-PERF-15 · Reportes transversales: el alcance viaja como IN anidados (2-3 niveles) y el banco solo lo mide como admin
**Severidad:** INFO · **Estado:** PLAUSIBLE · **Eje:** PERF · **Origen:** — · **Ola:** 4 · **Esfuerzo:** S
- **ID de la pasada 1:** B2-PERF-06
- **Ubicación:** `programas/services/reportes_becas.py:29` (`relevamiento__convocatoria__in=convocatorias_visibles(user)`),
  `:35`, `:74`, `:231`, `:279` (`relevamiento__in=qs`); `programas/services/autorizacion.py:337-344` y `:257-276`.
- **Escenario:** para un coordinador, referente o regional, `convocatorias_visibles` es
  `segmento_id IN (SELECT … FROM segmento JOIN asignación … DISTINCT)` dentro de `convocatoria_id IN (…)` dentro del
  recorte de casos: el patrón del 500 histórico del dashboard, que `resolver_alcance` ya aplana a ids. El banco
  (`perf_admin`) solo pasa por la rama admin (`Segmento.objects.all()`) y se midió en MySQL 8 (Cambio 92), no en MariaDB.
- **Crece con:** casos del alcance (cupos, embudo, beneficiarios), con un plan que depende de cómo aplane el optimizador.
- **Solución (mismo alcance), solo si la medición lo justifica:** resolver al principio de cada reporte
  `conv_ids = list(convocatorias_visibles(user).values_list("pk", flat=True))` y filtrar por
  `relevamiento__convocatoria_id__in=conv_ids`, como `resolver_alcance`.
- **Verificación:** banco MariaDB con un coordinador asignado al segmento del relevamiento público:
  `bench_mysql.py --solo reporte_cupos,reporte_embudo,reporte_beneficiarios` con ese actor, y `EXPLAIN` del agregado del
  embudo (buscar `DEPENDENT SUBQUERY` o materializaciones repetidas).
- **Regla para no repetirlo:** **skill** · `scripts/perf_mysql/README.md` · «Medir también con un actor no admin: el alcance
  del admin es `Segmento.objects.all()` y esconde los IN anidados de los demás roles».

---

### B-PERF-17 · Beneficiarios: la fecha de aprobación sale de una subconsulta sobre TracaFormulario sin índice útil, y el banco siembra una sola traza por caso
**Severidad:** INFO · **Estado:** PLAUSIBLE · **Eje:** PERF · **Origen:** Cambio 92 (76 ms con 9.000 aprobados y 1 traza por caso) · **Ola:** 4 · **Esfuerzo:** S
- **ID de la pasada 1:** B2-PERF-08
- **Ubicación:** `programas/services/reportes_becas.py:406-419` (`Subquery` correlacionada con `campo__iexact` y
  `valor_nuevo__icontains`, `ORDER BY created_at DESC, id DESC LIMIT 1`, por cada aprobado, y el ORDER BY de la página
  sobre esa anotación); `TracaFormulario` solo tiene el índice de la FK (`programas/models/__init__.py:4274-4300`).
- **Escenario:** en producción cada caso junta varias trazas (PERF-04 midió 22.266 para 6.667 casos tras un padrón, más
  las ediciones de revisión): por cada aprobado el motor lee todas sus trazas por la FK, evalúa dos LIKE sobre TEXT y
  ordena; la página 1 de 25 y el export lo hacen para **todos** los aprobados del alcance.
- **Crece con:** aprobados × trazas por caso.
- **Solución:** ninguna sin medir; si escala, índice `(formulario, created_at, id)` en `TracaFormulario` (migración
  aditiva, sin cambio de lógica).
- **Verificación:** banco: sembrar 5-10 trazas por caso aprobado y `bench_mysql.py --solo reporte_beneficiarios,reporte_beneficiarios_xlsx`
  + `EXPLAIN ANALYZE` de la consulta angosta.
- **Regla para no repetirlo:** **skill** · `scripts/perf_mysql/README.md` · «El banco siembra la cardinalidad real de las
  tablas hijas (trazas, validaciones, lista de espera), no una fila por caso».

---

Revisado sin hallazgo: `programas/views/inicio_becas.py` (solo redirige), `programas/views/solapas_becas.py` (acotado a los
casos de un ciudadano), `programas/services/reportes.py`, `programas/services/exportacion_reportes.py` (CSV en streaming
correcto bajo ASGI; XLSX dentro del request ya cubierto por PERF-03), `static/custom/js/becas-dashboard.js` (carga diferida
al abrir la solapa, `AbortController` por filtro, tope de 60 s), templates `reportes/hub.html`, `reportes/reporte.html`
(beneficiarios paginado; el resto crece con convocatorias o territoriales, no con casos) y `config/_dashboard_panel.html`
(selectores perezosos).

---

### B-PERF-18 · El drenaje de la tabla intermedia y el listado de inciertos traen los JSON del caso para usar pk, DNI y programa
**Severidad:** INFO · **Estado:** CONFIRMADO (lectura) · **Eje:** PERF · **Origen:** Origen oct.: PERF-11 (abierto, ⏸️ diferido por el PM el 09-oct) · **Ola:** 2 · **Esfuerzo:** S
- **Relación con PERF-11 (octubre, ⏸️ diferida por el PM el 09-oct):** esta ficha se queda en su ola; si PERF-11 (la foto `definicion` en cada caso) se retoma, la absorbe.
- **ID de la pasada 1:** B3-PERF-04
- **Ubicación:** `programas/services/siis_envio.py:1382-1386` (`_pendientes_por_paginas`: `select_related("formulario__ciudadano", "formulario__relevamiento__convocatoria__segmento__programa")` sin defer); `programas/management/commands/conciliar_envios_siis.py:95` (`_inciertos` con `select_related("formulario")` para un listado que usa `formulario_id`).
- **Escenario:** `sincronizar_tabla_intermedia` manda el payload guardado del alta; del caso usa pk, `ciudadano.dni` y la cadena hasta programa. Igual lee por página 200 x unos 27 KB de data, respuestas, definicion, datos_siis y datos_identificacion (unos 5 MB por consulta). El comentario de `:1360-1364` resolvió el timeout paginando; la mayor parte de los bytes sigue viajando. El `--listar` de conciliar hace lo mismo por cada incierto.
- **Con qué crece:** filas pendientes de la tabla intermedia (hasta las 4.826 citadas en `:1362`) x tamaño de los JSON. Son lecturas acotadas por página y sin lock; no hay medición que muestre un problema: por eso INFO.
- **Solución (mismo resultado):** `.defer("formulario__data", "formulario__respuestas", "formulario__definicion", "formulario__datos_siis", "formulario__datos_identificacion")` en `_pendientes_por_paginas`, verificando antes que `_reservar` y `_base_envio` no abren esos campos (el POST recibe el payload hecho). En conciliar, sacar el `select_related("formulario")` de `_inciertos`; el `_envio` de `--confirmar`/`--liberar` queda igual.
- **Lo que NO hay que hacer:** diferirlos en `hidratar()` o en un manager por defecto (descartado en la auditoría de oct: cualquier lector en bucle se vuelve N+1).
- **Tests a agregar:** `programas/tests/test_circuito_siis_performance.py::DrenajeSinJsonTests.test_el_drenaje_no_lee_los_json_del_caso` (SQL capturado sin `definicion` y sin consultas extra por fila).
- **Verificación / medición en el banco:** con 5.000 filas en AltaIntermediaSIIS (`procesar_casos_siis --destino tabla --aplicar --total 5000`, en tandas), `ANALYZE FORMAT=JSON` de la consulta de una página y `SHOW SESSION STATUS LIKE 'Bytes_received'` antes y después de leer una página desde el shell. Reportar como MEDIA solo si una página pasa de unos 200 ms en frío.
- **Regla para no repetirlo:** skill · `.claude/skills/mysql-mariadb/SKILL.md`, Consultas · «Un `select_related` hacia Formulario desde otra tabla arrastra sus cinco JSON: si el camino no abre la foto ni las respuestas, `defer` explícito de esos campos en ese queryset (nunca en el manager).»

---

### B-PERF-19 · La corrida masiva lee los ids de **todos** los candidatos aunque pida 100
**Severidad:** INFO · **Estado:** PLAUSIBLE · **Eje:** PERF · **Origen:** nuevo (PERF-01 midió `elegir_completos`; esto es el paso anterior) · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** B4-PERF-02
- **Ubicación:** `programas/services/proceso_masivo.py:1098` (`ids_de(candidatos(programa=…))` sin `limite`),
  `:714-738` (`ids_de`), `:763-774` (`hidratar_por_lotes`), `:789-792` (`elegir_completos` corta en `total`).
- **Escenario:** corrida pedida por 100 casos con 20.000 candidatos: `ids_de` hace 20.000 / 2.000 = 10 consultas antes
  de mirar el primer caso, y cada una lleva el predicado entero de `candidatos` —subconsultas correlacionadas de
  `ultimo_envio`, `vigente`, alta de oficio, validación vigente, conflicto de carga y lista de espera, más el `IN` con
  los DNI de `aprobados_materias` (15.532 literales, ~188 KB de SQL según PERF-07)—. `elegir_completos` usa los
  primeros ~100-200. Crece lineal con los candidatos; el último tramo además recorre hasta el final de la tabla buscando
  el `LIMIT 2000` que no llega. Corre en el hilo del pod web con el mismo `read_timeout` de 10 s por consulta: si los
  candidatos quedan ralos en un rango de pk (muchos RECHAZADO/BORRADOR intercalados), un tramo escanea bastante más que
  2.000 filas.
- **Causa raíz:** `ids_de` devuelve una lista materializada; el límite real (`total_pedido` elegidos) recién lo conoce
  `elegir_completos`.
- **Solución:** variante perezosa `iter_ids_de(casos, pagina=PAGINA_IDS)` que hace `yield` por tramo, y que
  `hidratar_por_lotes` acepte un iterable de ids (lotes de `LOTE_LECTURA` a medida que llegan). `correr` pasa a
  `hidratar_por_lotes(iter_ids_de(candidatos(...)))`. Mismo orden por pk y mismos elegidos: solo se dejan de pedir tramos
  que nadie iba a mirar. `ids_de` sigue para los comandos que necesitan `len()`.
- **Tests a agregar:** `programas/tests/test_proceso_masivo.py::CorrerTests.test_una_corrida_chica_no_lee_todos_los_tramos`
  (`PAGINA_IDS` parcheado a 5, 30 candidatos, `total_pedido=3`: `CaptureQueriesContext` con a lo sumo 2 consultas de ids).
- **Verificación / medición:** banco (`chaco_perf_ci`, 20.000 casos, 22.000 DNI habilitados), desde `manage.py shell`:
  cronometrar `ids_de(candidatos(programa=p))` y `EXPLAIN ANALYZE` del primer y del último tramo
  (`str(candidatos(programa=p).filter(pk__gt=N).order_by("pk").values_list("pk", flat=True)[:2000].query)`). Si algún
  tramo pasa 2 s o el total pasa 10 s, sube a MEDIA.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas activas ·
  «Listas de ids materializadas enteras (`ids_de`, `list(values_list("pk"))`) cuando el consumidor corta antes: pedir
  por tramos perezosos.»

---

### B-PERF-20 · `get_cupo_stats` cuenta los aprobados del segmento con el `Segmento` tomado en cada aprobación, sin medición en MariaDB
**Severidad:** INFO · **Estado:** PLAUSIBLE · **Eje:** PERF · **Origen:** nuevo; PERF-02 decidió conservar `get_cupo_stats` para estos caminos y PERF-12 midió solo el `COUNT` del cupo del **link** · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** B4-PERF-03
- **Ubicación:** `programas/services/cupo.py:55-72` (`get_cupo_stats`), llamado bajo
  `Segmento.objects.select_for_update()` en `:294` (promover), `:364` (aprobar) y `:396` (de oficio); los candados en
  `:272`, `:333`, `:427`.
- **Escenario:** cada aprobación del segmento —bandeja de revisión, cada caso del proceso masivo, promoción desde Cupo,
  cada fila de `inscribir_de_oficio`— serializa sobre la fila del segmento durante
  `COUNT(*) … JOIN relevamiento JOIN convocatoria WHERE estado = "APROBADO" AND convocatoria.segmento_id = X`. Crece con
  los aprobados del segmento (8.932 en el banco). Con una corrida masiva en curso, el revisor que aprueba en la bandeja
  espera el conteo de cada caso del hilo. No hay número que diga si son 5 ms o 500 ms; por el índice
  `(relevamiento, estado)` se espera lo primero.
- **Causa raíz:** cupo dinámico por diseño (docstring del módulo); el costo del conteo bajo candado no se midió en el
  motor real.
- **Solución:** ninguna sin número. Si el `EXPLAIN ANALYZE` da más de 20 ms (el mismo umbral que PERF-12), contar sobre
  los ids de relevamiento del segmento (`Formulario.objects.filter(relevamiento_id__in=ids, estado=APROBADO).count()`,
  como la pantalla de cupo en PERF-02) para que use `(relevamiento, estado)` sin join. Mismo número, misma regla.
- **Lo que NO hay que hacer:** contador denormalizado (§8.1, descartado para el link por la misma razón).
- **Tests a agregar:** `programas/tests/test_mediciones_banco_ola4.py::CupoDelSegmentoTests.test_el_count_del_cupo_del_segmento_usa_el_indice`
  (captura del SQL, como `CupoDelLinkPublicoTests`).
- **Verificación / medición:** banco, `EXPLAIN ANALYZE` del SQL de `get_cupo_stats(segmento_del_bench)` capturado con
  `scripts/perf_mysql/medir_consultas_borde.py` (agregar el escenario junto al de PERF-12); para el bloqueo, dos
  sesiones: una corre `aprobar_o_poner_en_espera` en bucle sobre 200 casos del segmento y la otra mide la espera de
  `SELECT id FROM programas_segmento WHERE id = X FOR UPDATE`.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/rendimiento.md` §Trampas medidas ·
  «Toda consulta que corre con un `select_for_update` tomado tiene su `EXPLAIN ANALYZE` del banco anotado junto al
  código: con el candado, su tiempo lo paga cada request que espera.»

---

### B-PERF-21 · `inscribir_de_oficio` resuelve el legajo y aprueba con el relevamiento público y la convocatoria tomados, y recorre el CSV tres veces
**Severidad:** INFO · **Estado:** PLAUSIBLE · **Eje:** PERF · **Origen:** nuevo · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** B4-PERF-04
- **Ubicación:** `programas/services/alta_de_oficio.py:315-346` (`_escribir`: `select_for_update` de `Relevamiento`
  `:318` y de `Convocatoria` `:319`; adentro `resolver_ciudadano_offline` `:334`, `refresh_from_db` `:335` y
  `aprobar_de_oficio` `:345`, con candado de segmento + `get_cupo_stats`); prepasada `:232-261` (`necesidad_de_cupo` ->
  `estado_previo` por fila, 2-3 consultas) y otra vez `estado_previo` en `procesar` `:298`;
  `programas/management/commands/inscribir_de_oficio.py:77`, `:144`, `:156`.
- **Escenario:** CSV de 5.000 altas contra el relevamiento público con el link abierto. Prepasada: ~10-15 mil consultas
  antes de escribir nada. Después, por fila, una transacción con los dos candados que el link pide en cada envío, y
  adentro el `get_or_create` del ciudadano (con sus señales y los 4 `DEL` de Redis de PERF-16), la marca, el conteo del
  cupo del relevamiento (PERF-12) y el del segmento (B-PERF-20). Cada inscripción del link espera como mucho una fila
  (decenas de ms, estimado): no llega a 10 s, pero es justo lo que el Cambio 91 sacó del candado del link («los adjuntos
  y el legajo salen después de liberar», `inscripcion_publica.py:107-112`). El costo por fila crece con los casos de la
  convocatoria y del segmento.
- **Causa raíz:** `_escribir` copió el candado del link pero no el corte del Cambio 91 entre lo que el candado protege
  (idempotencia, cupo, duplicado, insert) y lo que no (legajo, aprobación).
- **Solución:** dentro del candado solo `formulario_por_client_uuid` + `dni_en_convocatoria` + cupo + `_crear`; commit;
  después `resolver_ciudadano_offline` y `aprobar_de_oficio` (que ya toma sus propios candados de segmento y caso y
  relee el estado). El `client_uuid` determinístico ya hace idempotente el reintento si se corta en el medio. Y que
  `necesidad_de_cupo` devuelva el `estado_previo` por DNI para que `procesar` no lo repita.
- **Tests a agregar:** `programas/tests/test_alta_de_oficio.py::CandadosTests.test_el_legajo_se_resuelve_fuera_del_candado_del_relevamiento`
  (contrato de presencia de RED-67, `core.tests.candados`).
- **Verificación / medición:** banco, `inscribir_de_oficio --aplicar` con un CSV de 1.000 DNI del bench contra el
  relevamiento público, con `CaptureQueriesContext` + tiempo de la transacción por fila, y en paralelo
  `SELECT id FROM programas_relevamiento WHERE id = X FOR UPDATE` en bucle para registrar la espera máxima. Si pasa
  500 ms, sube a BAJA.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` §Transacciones y bloqueos · «Quien
  toma el candado del relevamiento público fuera del link (comandos, altas administrativas) respeta el mismo corte del
  Cambio 91: adentro solo idempotencia, cupo, duplicado e insert.»

---

### B-PERF-22 · `completar_casos_renaper` arma un `IN` con todos los ids de casos para averiguar las convocatorias
**Severidad:** INFO · **Estado:** PLAUSIBLE · **Eje:** PERF · **Origen:** nuevo · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** B4-PERF-05
- **Ubicación:** `programas/management/commands/completar_casos_renaper.py:375-377`.
- **Escenario:** sin `--convocatoria`, `Formulario.objects.filter(pk__in=ids)` con los 20.000 ids (~140 KB de SQL) y
  join a `programas_relevamiento` para sacar `convocatoria_id`. MariaDB convierte un `IN` de más de 1.000 literales en
  tabla derivada (`in_predicate_conversion_threshold`, lo que ya anota `padron.py:67`); el plan no se midió. Crece con
  los casos. Comando manual, pero contra ECOM la consulta entra o no en los 10 s del `read_timeout`, el mismo síntoma que
  motivó `ids_de` en el mismo archivo (`:362-368`).
- **Causa raíz:** se reconstruye en Python un conjunto que la base da directo.
- **Solución:** `Convocatoria.objects.filter(pk__in=casos.values("relevamiento__convocatoria_id"))` sobre el mismo
  queryset `casos` (con `--limite`, partir `ids` en tramos de 1.000 y unir los sets). Mismas convocatorias.
- **Tests a agregar:** ninguno nuevo; la caracterización de RED-32 cubre el resultado.
- **Verificación / medición:** banco, `EXPLAIN ANALYZE` de las dos formas sobre 20.000 casos y tiempo de cada una.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` §Consultas · «Un `pk__in` con más
  de 1.000 literales es una tabla derivada en MariaDB: si los ids salieron de un queryset, pasale el queryset.»

---

### B-PERF-23 · Borrar una pregunta general bloquea y reescribe el diseño de cada convocatoria en una sola transacción
**Severidad:** INFO · **Estado:** CONFIRMADO (lectura) · **Eje:** PERF · **Origen:** ninguno · **Ola:** 6 · **Esfuerzo:** S
- **ID de la pasada 1:** B5-PERF-02
- **Ubicación:** `programas/services/diseno.py:333-359` (`registrar_baja_del_catalogo`, disparado en `pre_delete` por `programas/signals.py:134-141`).
- **Escenario:** una pregunta general está en el diseño de todas las convocatorias (un `ItemDiseno` por diseño). Al borrarla (sin adjuntos), dentro del `atomic` del borrado se hace por diseño: `SELECT ... FOR UPDATE` del `DisenoFormulario`, lectura de sus ítems con condición, `UPDATE` de `bajas_pendientes`, `UPDATE` de versión y `refresh_from_db`: unas 5 consultas por convocatoria, con los candados tomados hasta el COMMIT.
- **Causa raíz:** el trabajo va por diseño en un bucle. Crece con las convocatorias, no con los casos. Con 100 convocatorias son ~500 consultas y 100 filas de diseño bloqueadas durante el request. Frena el constructor de esas convocatorias mientras dura; el link y la app no toman el candado del diseño.
- **Solución (solo si la medición lo justifica):** traer de una vez los ítems con condición de todos los diseños afectados (`ItemDiseno.objects.filter(diseno_id__in=ids, condicion__isnull=False)`), bloquear los diseños con un único `select_for_update().filter(pk__in=ids).order_by("pk")` y agrupar en Python. Mismo resultado y mismo orden de locks.
- **Tests a agregar:** `programas/tests/test_diseno_bajas_catalogo.py::BajaEnMuchosDisenosTests.test_consultas_no_crecen_por_diseno` (2 contra 10 convocatorias).
- **Verificación:** banco `scripts/perf_mysql/`: tiempo de `PreguntaGlobal.delete()` en un `atomic` con rollback, con las convocatorias sembradas. Si queda por debajo de 1 s con el volumen real, se cierra sin cambio.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas activas · «Señales `pre_delete`/`post_save` del catálogo que recorren diseños o convocatorias en un bucle: contar las consultas por fila afectada.»

---

### B-PERF-24 · Catálogo geográfico: estampida al vencer el caché y ~150 KB embebidos en cada GET del paso 2
**Severidad:** INFO · **Estado:** CONFIRMADO (lectura) · **Eje:** PERF · **Origen:** auditoría B6 · **Ola:** 1 · **Esfuerzo:** S
- **ID de la pasada 1:** B6-PERF-03
- **Ubicación:** `programas/services/catalogo_geografico.py` (CATALOGO_TTL 1 h, sin candado de recálculo); `portal/views/inscripcion.py:246` (`definicion_formulario` en cada GET/POST del paso 2) → `paso2.html:40` (json_script del catálogo).
- **Escenario:** en el pico, al vencer la clave todos los workers recalculan a la vez (Provincia/Localidad, ~8.800 filas) y cada GET del paso 2 manda el catálogo entero.
- **Crece con:** nada que crezca con los datos (catálogo fijo); solo concurrencia en el instante de vencimiento. Por eso INFO.
- **Causa raíz:** caché sin protección de recálculo y catálogo embebido en vez de recurso cacheable.
- **Solución:** cache.add de una clave-candado para que un solo worker recalcule (o TTL largo + invalidación al editar). Opcional: servir el catálogo como JSON versionado con Cache-Control; mismo contenido, misma UI.
- **Lo que NO hay que hacer:** quitar el catálogo del front (lo usa la validación del cliente).
- **Tests a agregar:** si se agrega el candado, dos llamadas con caché vacío → una sola lectura.
- **Verificación:** `medir_consultas_borde.py` sobre el GET del paso 2 con caché vacío vs. lleno; tamaño de respuesta con curl (size_download).
- **Regla para no repetirlo:** skill · `.claude/skills/mysql-mariadb/SKILL.md` · «Caché de catálogos leídos en endpoints públicos: recálculo con cache.add como candado.»

---

### B-DAT-02 · La baja lógica en cascada cuenta los casos con COUNT(*) mientras tiene tomada la fila de cada relevamiento
**Severidad:** INFO · **Estado:** PLAUSIBLE (sin medir en MariaDB) · **Eje:** DAT · **Origen:** ninguno · **Ola:** 6 · **Esfuerzo:** S
- **ID de la pasada 1:** B5-DAT-01
- **Ubicación:** `programas/services/eliminacion.py:122-133` (`select_for_update` de los relevamientos de la cascada y después `Formulario.objects.filter(relevamiento_id__in=...).count()`).
- **Escenario:** eliminar un programa con 10 relevamientos de 20.000 casos. Con los relevamientos bloqueados se cuentan ~200.000 entradas de índice. Mientras dura, el `Formulario.save` del link público y del alta por API (que toma el lock del relevamiento al numerar) espera. Si el programa tiene casos, la respuesta es siempre «no se elimina».
- **Causa raíz:** el conteo exacto se hace bajo el candado y crece con los casos. Con los índices `(relevamiento, estado)` y `(relevamiento, creado)` debería resolverse con `Using index` en decenas de ms, lejos del `read_timeout`; sin medición no hay hallazgo, por eso es INFO.
- **Solución (solo si la medición lo pide):** un `exists()` previo fuera del lock (si ya hay casos no hace falta bloquear nada: el mensaje se arma con el `count()` sin `FOR UPDATE`) y, bajo el lock, solo el `exists()` que garantiza la regla. Mismo mensaje y misma regla.
- **Tests a agregar:** ninguno nuevo si la medición da menos de 100 ms.
- **Verificación:** banco `scripts/perf_mysql/`: `EXPLAIN ANALYZE SELECT COUNT(*) FROM programas_formulario WHERE relevamiento_id IN (<ids de la cascada>)`; se espera `Using index` y menos de 100 ms con 20k casos por relevamiento.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` §Transacciones y bloqueos · «Dentro de un `select_for_update()`, solo la lectura que garantiza la regla (`exists()`); los conteos para el mensaje van antes y sin candado.»

---

### B-PERF-25 · El XLSX de respuestas del dashboard tarda 18,7 s caliente / 27,8 s frío: el 75 % es openpyxl escribiendo 700.000 celdas
**Severidad:** MEDIA · **Estado:** CONFIRMADO (medido) · **Eje:** PERF · **Origen:** pasada 2, banco; cruce oct.: mismo export que PERF-03 (oct., `lxml` en Cambio 257) y que A4-03, que §8.1 de octubre descartó («reescribir el xlsx fila a fila ahorra ~37 MB y no mueve el tiempo»). **Hecho nuevo:** el tiempo medido es 75 % openpyxl escribiendo celdas y el prototipo lo baja 12,2 → 2,9 s; el juez lo reabre por eso (19-nov): B-PERF-25 reabre A4-03 de octubre, con el hecho medido (12,2 → 2,9 s) · **Ola:** 4 · **Esfuerzo:** M
- **ID de la pasada 1:** — (pasada 2, perfil de exports en el banco)
- **Ubicación:** `programas/services/exportacion_reportes.py:37-66` (`respuesta_libro`, `hoja.append([celda_segura(v) for v in fila])`), `core/exportacion.py:17` (`celda_segura`: regex sobre cada celda), `programas/services/dashboard_becas.py:1556` (`_filas_por_persona`, ~4,4 s con ~1-1,6 s de SQL).
- **Evidencia:** cProfile + tiempos sin profiler (PoC reproducida; el prototipo y sus números van al PR que la arregla): 20.003 × 35 celdas, 3,1 MB; escribir ya en memoria 11,5-16,8 s; `lxml_write_cell` 700.036 llamadas. SQL total ~2 s.
- **Crece con:** casos × columnas (preguntas). Acantilado contra los 60 s de nginx: ~41.000 casos (~36.000 en frío), ya estimado en Cambio documentado (requerimientos.md:33411). No corta hoy; ingress de ECOM sin dato (pedido-datos-prd-ecom-2026-09.md §4).
- **Solución (misma salida):** escritor propio de sheet XML con `zipfile` + `inlineStr` (sin dependencias nuevas). Prototipo del escritor: 12,2 s → 2,9 s, valores idénticos al releer con openpyxl. Más: `celda_segura` hace `search` antes de `sub` (~1 s). Total estimado 18,7 → ~7 s; acantilado → ~100.000 casos.
- **Tests a agregar:** contenido idéntico celda a celda (openpyxl load) entre el escritor viejo y el nuevo para el export de respuestas; tipos str/int/vacío; si se usa en otra planilla con datetime, fijar formato `yyyy-mm-dd h:mm:ss`.
- **Regla para no repetirlo:** control mecánico · `scripts/perf_mysql/bench_mysql.py` · todo export XLSX/CSV de volumen entra al banco con presupuesto de ms caliente.

---

### B-PERF-26 · El XLSX de beneficiarios hidrata Formulario + 4 relaciones por cada aprobado para usar 7 valores
**Severidad:** MEDIA · **Estado:** CONFIRMADO (medido) · **Eje:** PERF · **Origen:** pasada 2, banco · **Ola:** 4 · **Esfuerzo:** S-M
- **Relación con PERF-11 (octubre, ⏸️ diferida por el PM el 09-oct):** esta ficha se queda en su ola; si PERF-11 (la foto `definicion` en cada caso) se retoma, la absorbe.
- **ID de la pasada 1:** — (pasada 2, perfil de exports en el banco)
- **Ubicación:** `programas/services/reportes_becas.py:435` (`_hidratar_beneficiarios`, `in_bulk` + `select_related` de ciudadano, relevamiento, convocatoria, segmento, subsegmento), `:464-478`.
- **Evidencia:** 8.933 filas × 7 columnas; 5-11 s en el bench (mediana 8 s); cProfile: `in_bulk` 7,4 s, 1,27 M campos leídos, 53.598 instancias de modelo. Frío: armado 9,7 s (SQL 5,4 s).
- **Solución (misma salida):** `values(...)` con solo los campos usados + dict `{relevamiento_id: (zona, convocatoria, segmento, subsegmento)}` de una consulta chica; `nombre_completo` con la lógica de `legajos/models/base.py:265`. Estimado ~8 → ~3 s.
- **Tests a agregar:** las 8.933 filas idénticas, incluidos casos sin ciudadano (`datos_identificacion`).
- Relación: B-PERF-17 (subconsulta de fecha de aprobación) se mide junto.

---

