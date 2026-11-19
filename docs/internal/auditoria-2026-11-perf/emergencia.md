# Auditoría de performance y optimización 2026-11 · Emergencia · Informe final (capítulo 2)

> Informe consolidado de la pasada 1 (12 revisores, 4 tajadas) con el resultado de la PoC de la pasada 2 para las dos fichas obligatorias (ambas CONFIRMARON y subieron a ALTA; **las dos ya están resueltas**: E-SEG-01 en #1204, Cambio 496, y E-ERR-01 en #1205, Cambio 497). SHA auditado `4140bb8073e271cf6ebccb1f08533d44553baf5a`. Estados `CONFIRMADO (lectura)` o `PLAUSIBLE`: `CONFIRMADO con test` y `REFUTADO` los asigna la pasada 2. **Mediciones del banco: pendiente de medición** (sección 8.a). Nada se implementa sin aprobación del PM.

## 1. Resumen

- **Alcance:** módulo Emergencia de `programas/` (mesa y casos; alojar, recepción y cierre; tablero, avisos, kits y pantalla del dispositivo; API de campo). Tres revisores por tajada: corrección y seguridad, calidad de código, performance.
- **Fichas:** 101 en la pasada 1, **93 tras fusionar** (8 fusiones: 4 pedidas por el juez y 4 halladas al consolidar). Esfuerzo total propuesto: **312 h** (S=2, S-M=4, M=8, L=20), de las cuales E-SEG-01 y E-ERR-01 (S-M cada una) ya se entregaron; el seguimiento que dejaron esos PRs está en la sección 10.

| Severidad | Fichas |
|---|---|
| CRÍTICA | 0 |
| ALTA | 3 |
| MEDIA | 38 |
| BAJA | 45 |
| INFO | 7 |
| **Total** | **93** |

| Eje | Fichas |
|---|---|
| SEG · Seguridad y RBAC | 1 |
| ERR · Errores y corrección | 18 |
| PERF · Rendimiento | 15 |
| DAT · Datos y operación | 1 |
| LIM · Código limpio y arquitectura | 54 |
| FE · Front (sin estética) | 4 |
| **Total** | **93** |

| Severidad × eje | SEG | ERR | PERF | DAT | LIM | FE |
|---|---|---|---|---|---|---|
| CRÍTICA | 0 | 0 | 0 | 0 | 0 | 0 |
| ALTA | 1 | 1 | 0 | 0 | 1 | 0 |
| MEDIA | 0 | 2 | 5 | 0 | 30 | 1 |
| BAJA | 0 | 13 | 7 | 0 | 22 | 3 |
| INFO | 0 | 2 | 3 | 1 | 1 | 0 |

**Las que importan:**

1. **E-SEG-01** (ALTA, **CONFIRMADO con PoC; RESUELTO en #1204, Cambio 496**): el reenvío de «Ingresar igual» con el `uuid_cliente` de un caso propio devuelve a quien ya no opera ese dispositivo los integrantes (nombre, DNI, cama) de un caso ajeno, incluso los confirmados después de la baja. `avisar_a_la_mesa` repite el patrón. Viola RU-9. Ola 0.
2. **E-ERR-01** (ALTA, **CONFIRMADO con PoC; RESUELTO en #1205, Cambio 497**, con la excepción del responsable con identidad a revisar del Cambio 486): confirmar a un integrante con el DNI de un legajo existente, con otro nombre, aloja a esa otra persona, le crea el vínculo familiar y le escribe sexo y fecha de nacimiento en el legajo. Ola 0.
3. **E-LIM-01** (ALTA): las vistas de la guardia y de kits reescriben reglas de dominio que ya tiene el servicio; es el origen de la mayoría de las fichas de la Ola 4 y de dos divergencias de reglas (reposición, derivación pedida).
4. **E-PERF-01** y **E-PERF-02** (MEDIA, sin medir): el REGEXP de `buscar_ciudadano_por_dni` (hallado por 2 revisores, citado por otros 2) y el candado del numerador de casos tomado hasta el commit (hallado por 2 revisores) son los dos puntos donde una ráfaga de la app de campo se serializa contra el `read_timeout` de 10 s de ECOM. No hay ruta de Emergencia en el banco: sin medir quedan MEDIA.
5. **Idempotencia y pestaña vieja en la web** (E-ERR-02, E-ERR-05, E-ERR-06, E-ERR-07): la guarda `derivacion_vista` y el `uuid_cliente` existen en el servicio pero solo los manda la API; la web puede duplicar un caso, una entrega o actuar sobre un ingreso nuevo.
6. **E-ERR-03** (MEDIA): el cron de vencimientos corre una vez por día; ya está registrado como pendiente del PM antes de habilitar la mesa en PRD. Decisión de cliente.

No hay ninguna ficha CRÍTICA. Los PERF quedan todos en PLAUSIBLE (salvo el REGEXP, CONFIRMADO por lectura) hasta que la pasada 2 los mida (sección 8).

### Fusiones

Pedidas por el juez (se conserva una ficha y la otra queda en «Origen» y en «Aporte del segundo revisor»):

| Ficha final | Absorbe | Motivo |
|---|---|---|
| E-PERF-01 ← ~E1-PERF-02~ | ~E2-PERF-01~ | `buscar_ciudadano_por_dni` con REGEXP bajo candado; hallado por 2 revisores. E4 lo encontró también en `personas/consultar` y en `…/dispositivos/{id}/buscar/` (se suma al alcance de la ficha) |
| E-PERF-02 ← ~E1-PERF-01~ | ~E1-ERR-02~ | candado del numerador tomado hasta el commit, con las fotos (y en `ingreso_directo`, las plazas) adentro |
| E-PERF-06 ← ~E3-PERF-03~ | ~E3-ERR-07~ + segunda parte de ~E3-LIM-12~ | el tablero trae todas las entregas en camino con sus líneas para mostrar 20 (`emergencia_tablero.py:656-677`) |
| E-DAT-01 ← ~E1-DAT-01~ | ~E3-PERF-06~ | la «última traza» sin índice compuesto `(caso, creado_en, id)` |
| (sin ficha propia) | cantidad enorme de kits (`serializers_emergencia.py:334`) | E1-ERR-01 la cubre: la misma causa raíz que el `float()` de `_entero`; E4 la citó sin abrir ficha |

Halladas al consolidar (mismo archivo:línea y mismo problema):

| Ficha final | Absorbe | Motivo |
|---|---|---|
| E-LIM-27 ← ~E1-LIM-09~ | ~E2-LIM-10~ | `CAP_ADMITIR = "dispositivo.admitir"` redeclarada (6 copias en E1, 5 en E2, las mismas líneas) más los duplicados vecinos de la etapa 3 |
| E-LIM-13 ← ~E4-LIM-02~ | ~E4-LIM-03~ | nombres privados (`_respuesta_400`, `_VistaDeCampo`…) que cruzan módulos de `programas/api/`; misma regla de E4-LIM-03 = la de E4-LIM-02 y la misma salida (`programas/api/respuestas.py` + base pública) |
| E-PERF-12 ← ~E4-PERF-01~ | ~E4-LIM-15~ | `views_emergencia_kits.py:106-112`: `?pendientes=1` sin tope y con el tope en la vista; el tope pasa al selector (como `TOPE_MIS_CASOS` en M1). Severidad de la fusión: BAJA (la mayor) |
| E-LIM-44 ← ~E3-LIM-14~ | ~E4-LIM-09~ | `mis_dispositivos` (`selectors/kits.py:295`): E3 lo ve mal ubicado y E4 lo ve compuesto en la vista; se mueve y se completa en un solo selector de la guardia |

Relaciones que NO se fusionaron (misma familia, otro archivo o otra causa; van cruzadas en las fichas): E-ERR-05 / E-ERR-06 / E-ERR-07 (POST de la web sin identificador de envío, tres vistas distintas, un mismo patrón de arreglo); E-LIM-02 / E-LIM-01 / E-LIM-07 / E-LIM-32 (regla de dominio en la capa equivocada); E-LIM-30 / E-LIM-50 / E-LIM-52 (presentación dentro de `selectors/`); E-LIM-24 / E-LIM-18 / E-LIM-19 (privados importados entre módulos, tres módulos distintos); E-FE-01 / E-FE-04 (esqueleto de modal); E-LIM-54 / E-LIM-51 / E-LIM-53 (tamaño de archivos); E-LIM-09 / E-LIM-10 (misma vista `PlazasDelDispositivoView`, una regla de capacidad y otra de alcance); E-ERR-11 / E-ERR-18 (conversión de enteros a mano); E-PERF-07 / E-DAT-01 (índices nuevos: una sola migración, dos fichas); E-LIM-48 / E-LIM-52 (`selectors/emergencia_llegadas.py` vivo, no muerto: lo usa `views/emergencia_dispositivo.py:57`).

### Contradicciones entre fichas (propuesta de cada una; las cierra el PR de su ola)

1. **Dueño de `CAP_ADMITIR`.** E1-LIM-09 propone `services/dispositivos.py` (junto a `CAP_VER` y `CAP_CONFIGURAR`); E2-LIM-10 propone `estadias` o `emergencia_programa`. Además cuentan distinto las copias (siete módulos en E1, cinco en E2). La ficha fusionada E-LIM-27 conserva `services/dispositivos.py`; si el juez prefiere otro, es una línea.
2. **Umbral del ratchet de tamaño.** E1-LIM-16 propone 1.000 líneas para `services/emergencia*.py` y `selectors/emergencia*.py`; E3-LIM-13 y E4-LIM-14 proponen 700 (con `# TAMAÑO-OK`) para vistas y API. Ningún archivo del alcance pasa de 1.000 (el mayor: `services/emergencia.py`, 769). Propuesta: tope duro en 1.000, aviso en 700.
3. **Dónde va la siembra del banco.** E3 propone un `seed_perf_emergencia` o «una sección de `seed_perf`», lo que contradice `METODO.md` §4 (no se toca `seed_perf`: lo usa el CI de performance). E1 propone un paso `sembrar_emergencia` en `escalar_bench.py`; E2, `scripts/perf_mysql/escenarios_emergencia.py`. Propuesta: un único `escenarios_emergencia.py` (sección 8.c).
4. **Volumen a sembrar.** E1/E2/E3/E4 parten de 10.000 casos y 50.000 trazas; E3 pide además 100.000 casos y 500.000 trazas. Ciudadanos: 50.000-100.000 (E1) contra 500.000 (E2). Kits: 50 `TipoKit` y 5 líneas (E3) contra 10 ítems y 8 líneas (E4). La sección 8.c toma el mayor de cada uno, y las dos puntas para ciudadanos.
5. **Cómo se toma el total de entregas en camino.** E3-PERF-03 y E3-LIM-12 lo toman de `foto.entregas_en_camino` (2 consultas); E3-ERR-07 usa un `qs.count()` aparte (3 consultas). La ficha E-PERF-06 elige la foto.
6. **Forma del número provisorio.** E1-PERF-01: `"P" + uuid4().hex[:15]` y `numerar=False` en `ingreso_directo` y `avisar_a_la_mesa`; E1-ERR-02: `"tmp-" + uuid4().hex[:12]` y solo `crear_caso` (alternativa chica: sacar el segundo `full_clean` de adentro del candado). E-PERF-02 conserva el diseño de PERF-01 porque cubre también la etapa 3; la alternativa chica queda como paso previo.
7. **Convención de importación de fachadas.** E2-LIM-05 manda que todo caller externo importe desde la fachada (`emergencia_alojar`); E1-LIM-01 y E2-LIM-04 mandan que los módulos de etapas posteriores importen de `emergencia_comun` / `emergencia_ingreso_comun` y nunca de la fachada `emergencia`. Son dos convenciones de sentido opuesto según el módulo. Hay que fijar una antes de escribir el test de arquitectura (E-LIM-24, E-LIM-18).
8. **Severidad desigual para el mismo patrón.** E-LIM-01 (reglas de dominio en vistas) es ALTA; E-LIM-02 y E-LIM-07 (mismo patrón en la mesa) son MEDIA y E-LIM-32 BAJA. Se dejaron como las puso cada revisor; si el juez las iguala, el efecto es solo de orden.
9. **Solución de E-PERF-01.** E1 propone una columna indexada `dni_normalizado` (M); E2 propone no repetir el recorrido y sacarlo del candado (S) y deja la columna como paso M opcional «cuando se mida». No se contradicen: la ficha fusionada los ordena (primero S, después la columna), pero el esfuerzo de la ficha (M) cubre ambos.
10. **Ola propia de cada revisor.** Las olas que traían las fichas (Ola 1/2/3 en E3 y E4, «E3» en LIM, «a asignar» en E4) se descartaron y se reasignaron; E3 puso el cron (E-ERR-03) en su Ola 1 y E4 puso E-SEG-01 en su Ola 1: ambas quedan en las olas 3 y 0 de este informe.

## 2. Índice

| ID | Título | Sev. | Estado | Esf. | Ola | Archivo |
|---|---|---|---|---|---|---|
| E-SEG-01 | El reenvío de «Ingresar igual» devuelve los integrantes de un caso ajeno al dispositivo de la… | ALTA | RESUELTO (#1204) | S-M | 0 | `programas/api/views_emergencia_sin_derivacion.py` |
| E-ERR-01 | Confirmar con el DNI de un legajo existente no valida la identidad: aloja y escribe en el lega… | ALTA | RESUELTO (#1205) | S-M | 0 | `programas/services/emergencia_confirmacion.py` |
| E-LIM-01 | Las vistas de la guardia y de kits reescriben reglas de dominio que ya tiene el servicio | ALTA | CONFIRMADO | M | 4 | `programas/views/emergencia_kits.py` |
| E-ERR-02 | Cerrar con diferencia, cancelar el ingreso y «Familia alojada» desde la web no mandan `derivac… | MEDIA | CONFIRMADO | S-M | 1 | `programas/views/emergencia_dispositivo.py` |
| E-ERR-03 | Los vencimientos de Emergencia corren una vez por día: las derivaciones vencidas quedan pendie… | MEDIA | CONFIRMADO | S | 3 | `docker/cron/procesar_vencimientos.cron` |
| E-PERF-01 | El alta de un responsable nuevo recorre toda la tabla de ciudadanos con REGEXP, dos veces | MEDIA | CONFIRMADO | M | 2 | `programas/services/ingreso.py` |
| E-PERF-02 | El candado del numerador de casos queda tomado hasta el commit, con fotos y reservas adentro | MEDIA | PLAUSIBLE | M | 2 | `programas/services/emergencia_alta.py` |
| E-PERF-03 | El tablero recorre todo el histórico de casos en cada carga para quedarse con la ventana del d… | MEDIA | PLAUSIBLE | S-M | 2 | `programas/selectors/emergencia_tablero.py` |
| E-PERF-04 | La página de la bandeja ordena por expresiones y ordena el historial entero de la solapa | MEDIA | PLAUSIBLE | S-M | 2 | `programas/selectors/emergencia.py` |
| E-PERF-05 | E4 (listado de entregas) ordena y pagina todo el histórico sin índice, con `select_related` en… | MEDIA | PLAUSIBLE | S-M | 2 | `programas/selectors/kits.py` |
| E-LIM-02 | La vista de cancelar derivación busca la pendiente y decide el `EstadoCambio` fuera del candado | MEDIA | CONFIRMADO | S | 4 | `programas/views/emergencia.py` |
| E-LIM-03 | La compuerta «403 sin la capacidad, 404 sin alcance» está implementada dos veces con mecánicas… | MEDIA | CONFIRMADO | S-M | 4 | `programas/views/emergencia_dispositivo.py` |
| E-LIM-04 | Kits no tiene `acciones_de_entrega`: la vista decide qué transición se ofrece con el estado cr… | MEDIA | CONFIRMADO | S-M | 4 | `programas/views/emergencia_kits.py` |
| E-LIM-05 | El enrutamiento «estado del caso → pantalla» está repartido en tres métodos y uno se pisa solo | MEDIA | CONFIRMADO | S | 4 | `programas/views/emergencia_dispositivo.py` |
| E-LIM-06 | Dos definiciones de «ingreso directo»: el modelo mira `situacion` y el tablero infiere por `to… | MEDIA | CONFIRMADO | S-M | 4 | `programas/selectors/emergencia_tablero.py` |
| E-LIM-07 | La regla de plazas para derivar (RN-2.5) está escrita dos veces: en el panel y en `derivar_cas… | MEDIA | CONFIRMADO | S | 4 | `programas/selectors/emergencia.py` |
| E-LIM-08 | Reglas de dominio en `selectors/` y dependencia cruzada entre selectores y servicios | MEDIA | CONFIRMADO | S-M | 4 | `programas/selectors/emergencia.py` |
| E-LIM-09 | «¿Ve quién ocupa la cama?» lo decide cada vista, dos veces, con la capacidad redeclarada | MEDIA | CONFIRMADO | S | 4 | `programas/api/views_emergencia_llegadas.py` |
| E-LIM-10 | La guarda «el `?caso` tiene que estar derivado a este dispositivo» vive en la vista del mapa | MEDIA | CONFIRMADO | S | 4 | `programas/api/views_emergencia_llegadas.py` |
| E-LIM-11 | La tarjeta de la derivación se proyecta dos veces: serializer de la API y selector del backoff… | MEDIA | CONFIRMADO | S-M | 4 | `programas/api/serializers_emergencia.py` |
| E-LIM-12 | Cada endpoint repite a mano la traducción de errores: el protocolo `(resultado, respuesta)` de… | MEDIA | CONFIRMADO | M | 5 | `programas/api/views_emergencia.py` |
| E-LIM-13 | Cada superficie de la API de campo reescribe su traductor de errores, y Emergencia depende de… | MEDIA | CONFIRMADO | S-M | 5 | `programas/api/views_emergencia.py` |
| E-LIM-14 | La traducción de `EstadoCambio`/`ValidationError` está copiada nueve veces en dos archivos de… | MEDIA | CONFIRMADO | S-M | 5 | `views/emergencia_dispositivo.py` |
| E-LIM-15 | La orquestación de candados del ingreso está copiada tres veces | MEDIA | CONFIRMADO | M | 6 | `programas/services/emergencia_confirmacion.py` |
| E-LIM-16 | `alojar_familia` y `cerrar_con_diferencia` son dos copias del mismo cierre y cuentan distinto | MEDIA | CONFIRMADO | S-M | 6 | `programas/services/emergencia_cierre.py` |
| E-LIM-17 | Las transiciones de caso y de derivación se escriben a mano en cada servicio | MEDIA | CONFIRMADO | S-M | 6 | `` |
| E-LIM-18 | Seis módulos y una fachada para un único flujo, unidos por ~20 helpers con nombre privado | MEDIA | CONFIRMADO | M | 6 | `programas/services/emergencia_ingreso_comun.py` |
| E-LIM-19 | El contrato entre Dispositivos y Emergencia se apoya en helpers privados importados entre módu… | MEDIA | CONFIRMADO | S-M | 6 | `programas/services/reservas_derivacion.py` |
| E-LIM-20 | Los servicios devuelven datos colgando atributos sueltos en instancias de modelo | MEDIA | CONFIRMADO | M | 6 | `programas/services/emergencia_confirmacion.py` |
| E-LIM-21 | El mapa de Emergencia traduce el estado de una cama comparando rótulos de pantalla | MEDIA | CONFIRMADO | S-M | 6 | `programas/selectors/emergencia_alojar.py` |
| E-LIM-22 | El ejecutor «una transacción por fila, falla al final» lo promete `core` y lo implementa Emerg… | MEDIA | CONFIRMADO | S | 6 | `core/services/vencimientos.py` |
| E-LIM-23 | `EstadoCambio` vive en el módulo de la mesa y obliga a E3 y a kits a importar toda la etapa 2 | MEDIA | CONFIRMADO | S | 6 | `programas/services/emergencia.py` |
| E-LIM-24 | La fachada `services/emergencia.py` reexporta helpers privados y otros módulos los consumen co… | MEDIA | CONFIRMADO | S-M | 6 | `programas/services/emergencia.py` |
| E-LIM-25 | Formateadores de texto copiados en cinco o más módulos, con variantes que divergen | MEDIA | CONFIRMADO | S-M | 7 | `programas/services/emergencia_comun.py` |
| E-LIM-26 | Mensajes y topes de validación duplicados como literales entre forms y servicios, y un homónim… | MEDIA | CONFIRMADO | S | 7 | `services/emergencia.py` |
| E-LIM-27 | La capacidad `"dispositivo.admitir"` está redeclarada en siete módulos | MEDIA | CONFIRMADO | S | 7 | `programas/services/emergencia_programa.py` |
| E-LIM-28 | La regla «foto JPEG de la app, hasta 5 MB» está escrita dos veces, en dos capas | MEDIA | CONFIRMADO | S | 7 | `programas/api/serializers_emergencia.py` |
| E-LIM-29 | La tabla severidad→tono/ícono y la serialización del `Aviso` están copiadas en Emergencia y Di… | MEDIA | CONFIRMADO | S | 7 | `programas/services/avisos_emergencia.py` |
| E-LIM-30 | Tablas de presentación repartidas en servicio, *presenter* y vista | MEDIA | CONFIRMADO | S-M | 8 | `programas/services/emergencia.py` |
| E-LIM-31 | La foto del tablero cruza módulos como tuplas posicionales (`fila[3]`, `fila[5]`) y se desarma… | MEDIA | CONFIRMADO | S-M | 8 | `programas/selectors/emergencia_tablero.py` |
| E-FE-01 | El esqueleto del modal con formulario está copiado cinco veces en la ficha del caso | MEDIA | CONFIRMADO | M | 9 | `programas/templates/programas/emergencia/casos/detail.html` |
| E-ERR-04 | Con la cubeta de identidad agotada, la mesa no puede cargar un caso «con identidad a revisar» | BAJA | PLAUSIBLE | S | 0 | `programas/forms_emergencia.py` |
| E-ERR-05 | «Nuevo caso» de la mesa no es idempotente: un reenvío del POST crea un segundo caso con otro n… | BAJA | PLAUSIBLE | S | 1 | `programas/views/emergencia.py` |
| E-ERR-06 | Ingreso directo y «Agregar persona» desde el backoffice no tienen idempotencia del lado del se… | BAJA | PLAUSIBLE | S-M | 1 | `programas/views/emergencia_dispositivo.py` |
| E-ERR-07 | «Crear entrega» no es idempotente: un reenvío del paso 3 arma una segunda entrega (o una segun… | BAJA | PLAUSIBLE | S-M | 1 | `programas/views/emergencia_kits.py` |
| E-ERR-08 | El reintento idempotente de confirmar o agregar devuelve 409 si el caso ya cambió de estado | BAJA | PLAUSIBLE | S | 1 | `programas/services/emergencia_confirmacion.py` |
| E-ERR-09 | El reenvío de una recepción de kits sin `cantidades` da 400 en vez del 200 que promete el cont… | BAJA | CONFIRMADO | S | 1 | `programas/api/views_emergencia_kits.py` |
| E-ERR-10 | La cola reintenta para siempre un ingreso directo que ya se creó si el usuario perdió el dispo… | BAJA | PLAUSIBLE | S | 1 | `programas/api/views_emergencia_sin_derivacion.py` |
| E-ERR-11 | Un número de más de 308 dígitos en una cantidad del Formulario 1 tumba el alta con un 500 | BAJA | CONFIRMADO | S | 3 | `programas/services/emergencia_alta.py` |
| E-ERR-12 | «Familia alojada» acepta un sector dado de baja | BAJA | CONFIRMADO | S | 3 | `programas/services/emergencia_cierre.py` |
| E-ERR-13 | El ingreso directo, si pierde una cama en la carrera, pide «volver a tocar Aceptar» | BAJA | CONFIRMADO | S | 3 | `programas/services/emergencia_ingreso_comun.py` |
| E-ERR-14 | Si el UNIQUE de `uuid_cliente_recepcion` salta, la foto del remito queda huérfana en `media/` | BAJA | CONFIRMADO | S | 3 | `programas/services/kits.py` |
| E-ERR-15 | «Marcar en camino» acepta una hora de salida anterior al armado de la entrega | BAJA | CONFIRMADO | S | 3 | `programas/services/kits.py` |
| E-ERR-16 | «Casos por localidad» del tablero fusiona localidades homónimas de municipios distintos y su e… | BAJA | PLAUSIBLE | S | 3 | `programas/selectors/emergencia_tablero.py` |
| E-PERF-06 | El tablero trae todas las entregas en camino con todas sus líneas para mostrar 20 | BAJA | CONFIRMADO | S | 2 | `programas/selectors/emergencia_tablero.py` |
| E-PERF-07 | Derivaciones y entregas se filtran por `estado` sin un índice que empiece por `estado` | BAJA | PLAUSIBLE | S | 2 | `programas/selectors/emergencia_tablero.py` |
| E-PERF-08 | Tres consultas fijas de la bandeja recorren todos los casos en cada carga | BAJA | CONFIRMADO | S | 2 | `programas/selectors/emergencia.py` |
| E-PERF-09 | Dos aceptaciones simultáneas en el mismo dispositivo eligen las mismas camas y la segunda espe… | BAJA | CONFIRMADO | S-M | 2 | `programas/services/emergencia_recepcion.py` |
| E-PERF-10 | Reservar las camas de la familia valida cada cama con dos consultas propias mientras las tiene… | BAJA | CONFIRMADO | S | 2 | `programas/services/reservas_derivacion.py` |
| E-PERF-11 | «Familia en la puerta» busca en todos los casos no cerrados en vez de en los de la foto | BAJA | CONFIRMADO | S | 2 | `programas/services/avisos_emergencia.py` |
| E-PERF-12 | La lista de entregas pendientes de un dispositivo no tiene tope | BAJA | CONFIRMADO | S | 2 | `programas/api/views_emergencia_kits.py` |
| E-LIM-32 | «La derivación vigente del caso» se consulta con tres consultas escritas a mano | BAJA | CONFIRMADO | S | 4 | `programas/services/emergencia.py` |
| E-LIM-33 | La respuesta de la recepción de kits no pasa por el serializer que la documenta | BAJA | CONFIRMADO | S | 5 | `programas/api/views_emergencia_kits.py` |
| E-LIM-34 | Relectura del caso con ORM en las vistas y el mismo cuerpo «reservadas/faltantes/integrantes»… | BAJA | CONFIRMADO | S | 5 | `programas/api/views_emergencia_llegadas.py` |
| E-LIM-35 | Las vistas del backoffice importan del paquete de la API para filtrar el rechazo por DNI | BAJA | CONFIRMADO | S | 5 | `programas/views/emergencia.py` |
| E-LIM-36 | La fachada `emergencia_alojar` tiene dos rutas de importación, reexporta la ficha y conserva u… | BAJA | CONFIRMADO | S | 6 | `programas/services/emergencia_alojar.py` |
| E-LIM-37 | La regla de «cama libre» y el armado del mapa por sector están escritos dos veces | BAJA | PLAUSIBLE | S-M | 6 | `programas/selectors/emergencia_alojar.py` |
| E-LIM-38 | Las nueve acciones de la mesa repiten el mismo preludio de guardas | BAJA | CONFIRMADO | M | 6 | `programas/services/emergencia.py` |
| E-LIM-39 | El catálogo de necesidades del Formulario 1 tiene tres fuentes | BAJA | CONFIRMADO | S | 7 | `programas/services/emergencia_alta.py` |
| E-LIM-40 | `_marcas_de` está duplicada inline en `ids_por_estado_sla` | BAJA | CONFIRMADO | S | 7 | `programas/selectors/emergencia.py` |
| E-LIM-41 | `responsables_alojados` no pasa por el manager `Estadia.objects.de_la_red` | BAJA | CONFIRMADO | S | 7 | `programas/selectors/emergencia.py` |
| E-LIM-42 | `configuracion_emergencia` mezcla lecturas con escritura: `sla_vigente()` hace INSERT en cada… | BAJA | CONFIRMADO | S | 7 | `programas/services/configuracion_emergencia.py` |
| E-LIM-43 | Las siete reglas de aviso repiten el mismo esqueleto «tope 5 + Aviso + "y N más"» | BAJA | CONFIRMADO | S-M | 7 | `programas/services/avisos_emergencia.py` |
| E-LIM-44 | `selectors/kits.py` mezcla alcance de la guardia con lecturas de kits: autoriza dos veces y al… | BAJA | CONFIRMADO | S | 7 | `programas/selectors/kits.py` |
| E-LIM-45 | `acotar_relevado_en` reimplementa el recorte de reloj de `campo.acotar_capturado_en` y corre d… | BAJA | CONFIRMADO | S | 7 | `programas/services/emergencia_campo.py` |
| E-LIM-46 | La clase base del Formulario 1 conoce a su subclase (`pop("relevado_en", None)` + `relevado_en… | BAJA | CONFIRMADO | S | 7 | `programas/api/serializers_emergencia.py` |
| E-LIM-47 | Cuatro clases de permiso casi idénticas y el código `SIN_MODULO` redeclarado por superficie | BAJA | CONFIRMADO | S | 7 | `programas/api/views_emergencia.py` |
| E-LIM-48 | `selectors/emergencia_mesa.py` es un *presenter* que la guardia usa como bolsa de utilidades | BAJA | CONFIRMADO | S-M | 8 | `programas/selectors/emergencia_mesa.py` |
| E-LIM-49 | `forms_emergencia.py` mezcla la configuración E7 con los formularios de la mesa | BAJA | CONFIRMADO | S | 8 | `programas/forms_emergencia.py` |
| E-LIM-50 | El selector del tablero arma tarjetas de pantalla (íconos, tonos, URLs) y lee dos veces las en… | BAJA | CONFIRMADO | S-M | 8 | `programas/selectors/emergencia_tablero.py` |
| E-LIM-51 | `views/emergencia_dispositivo.py` pasa las 700 líneas, y el «sin derivación» que el PM quiere… | BAJA | CONFIRMADO | S | 8 | `programas/views/emergencia_dispositivo.py` |
| E-LIM-52 | `selectors/emergencia_llegadas.py` está vivo pero es presentación del backoffice alojada en `s… | BAJA | CONFIRMADO | M | 8 | `programas/selectors/emergencia_llegadas.py` |
| E-LIM-53 | `serializers_emergencia.py` (755 líneas) junta tres superficies que las vistas ya separaron | BAJA | CONFIRMADO | S | 8 | `programas/api/serializers_emergencia.py` |
| E-FE-02 | Los filtros de la bandeja se renderizan a mano mientras `FiltrosBandejaForm` declara las misma… | BAJA | CONFIRMADO | S-M | 9 | `programas/templates/programas/emergencia/casos/list.html` |
| E-FE-03 | «Llegaron N sobre M declaradas» se arma dos veces en la ficha, con dos fuentes | BAJA | CONFIRMADO | S | 9 | `programas/selectors/emergencia_mesa.py` |
| E-FE-04 | Los modales «Marcar en camino» y «Cancelar entrega» están escritos dos veces (listado y detall… | BAJA | CONFIRMADO | S | 9 | `programas/templates/programas/emergencia/kits/list.html` |
| E-ERR-17 | Un ingreso en curso que nadie cierra retiene las camas de la familia sin plazo | INFO | CONFIRMADO | M | 3 | `programas/services/reservas_derivacion.py` |
| E-ERR-18 | `kits._entero` levanta `ValueError` con «+-1» o «--1» (latente) | INFO | CONFIRMADO | S | 3 | `programas/services/kits.py` |
| E-PERF-13 | Ninguna ruta de Emergencia está en los presupuestos ni en el banco MySQL | INFO | CONFIRMADO | S-M | 2 | `scripts/perf_budgets.json` |
| E-PERF-14 | La ficha trae la traza completa, sin tope | INFO | CONFIRMADO | S | 2 | `programas/selectors/emergencia_mesa.py` |
| E-PERF-15 | La derivación aceptada nunca deja de ser ACEPTADA y las lecturas de la guardia arrastran todo… | INFO | CONFIRMADO | S | 2 | `programas/selectors/emergencia_alojar.py` |
| E-DAT-01 | Las subconsultas «última traza» y «última rechazada» no tienen índice compuesto, y el `Exists`… | INFO | PLAUSIBLE | S | 2 | `programas/selectors/emergencia.py` |
| E-LIM-54 | Tamaño: `services/emergencia.py` pasa las 700 líneas y otros tres archivos se acercan | INFO | CONFIRMADO | S | 8 | `programas/services/emergencia.py` |

## 3. Plan por olas

Lo urgente primero; después por tema y por archivo, para que los PRs no se pisen. Horas con S=2, S-M=4, M=8, L=20. Un issue por ola. Se ajustó la propuesta del juez: la Ola 0 junta las dos ALTA de datos personales con la casilla de identidad; la Ola 1 es la idempotencia desde la web; la Ola 2 es performance y va **después de medir**; la Ola 3 reúne las correcciones menores y el cron (DECISIÓN CLIENTE); la Ola 4 y la 5 son el trabajo de fondo (dominio fuera de las vistas y traductor único de errores), la Ola 6 ordena los servicios de la etapa 3, y las olas 7 a 9 son limpieza.

| Ola | Nombre | Fichas | Horas |
|---|---|---|---|
| 0 | Urgente: identidad y datos personales | 3 | 10 |
| 1 | Doble envío y pestaña vieja: idempotencia desde la web | 7 | 20 |
| 2 | Rendimiento medible: numerador, REGEXP, tablero e índices | 16 | 54 |
| 3 | Correcciones menores y operación de vencimientos | 9 | 24 |
| 4 | De fondo: reglas de dominio fuera de las vistas y los selectores | 12 | 40 |
| 5 | De fondo: traductor único de errores de la API y de las vistas | 6 | 22 |
| 6 | De fondo: servicios de alojar, cierre y mesa (candados, transiciones, helpers privados) | 13 | 62 |
| 7 | Limpieza: constantes, capacidades, formateadores y catálogos duplicados | 14 | 32 |
| 8 | Limpieza: presentación fuera de `selectors/` y tamaño de archivos | 9 | 32 |
| 9 | Limpieza: front de Emergencia | 4 | 16 |
| | **Total** | **93** | **312** |

### Ola 0 · Urgente: identidad y datos personales (10 h, 3 fichas)

Dos guardas chicas y una casilla. Las dos ALTA tenían PoC que las confirma (sección 8) y **ya están resueltas** (#1204 y #1205; lo que dejaron pendiente está en la sección 10). Queda E-ERR-04 y ese seguimiento. La casilla de identidad lleva propuesta por defecto aplicable (sección 7).

- **E-SEG-01** [ALTA · S-M] El reenvío de «Ingresar igual» devuelve los integrantes de un caso ajeno al dispositivo de la URL — **RESUELTO (#1204, Cambio 496)**
- **E-ERR-01** [ALTA · S-M] Confirmar con el DNI de un legajo existente no valida la identidad: aloja y escribe en el legajo de otra persona — **RESUELTO (#1205, Cambio 497)**
- **E-ERR-04** [BAJA · S] Con la cubeta de identidad agotada, la mesa no puede cargar un caso «con identidad a revisar»

### Ola 1 · Doble envío y pestaña vieja: idempotencia desde la web (20 h, 7 fichas)

Un solo patrón de arreglo: identificador de envío oculto en los formularios de la web (`uuid_cliente`, `derivacion_vista`) y «ya se hizo» antes que la guarda de estado. Se hacen juntas para escribir el helper una vez.

- **E-ERR-02** [MEDIA · S-M] Cerrar con diferencia, cancelar el ingreso y «Familia alojada» desde la web no mandan `derivacion_vista`: una pestaña vieja actúa sobr…
- **E-ERR-05** [BAJA · S] «Nuevo caso» de la mesa no es idempotente: un reenvío del POST crea un segundo caso con otro número
- **E-ERR-06** [BAJA · S-M] Ingreso directo y «Agregar persona» desde el backoffice no tienen idempotencia del lado del servidor
- **E-ERR-07** [BAJA · S-M] «Crear entrega» no es idempotente: un reenvío del paso 3 arma una segunda entrega (o una segunda reposición de la misma)
- **E-ERR-08** [BAJA · S] El reintento idempotente de confirmar o agregar devuelve 409 si el caso ya cambió de estado
- **E-ERR-09** [BAJA · S] El reenvío de una recepción de kits sin `cantidades` da 400 en vez del 200 que promete el contrato
- **E-ERR-10** [BAJA · S] La cola reintenta para siempre un ingreso directo que ya se creó si el usuario perdió el dispositivo

### Ola 2 · Rendimiento medible: numerador, REGEXP, tablero e índices (54 h, 16 fichas)

Se mide primero (sección 8.a) y se arregla después. Lo primero es dejar las rutas de Emergencia en el banco y en `perf_budgets.json`; sin eso ninguna de las otras tiene número. Los dos índices (`TrazaCaso`, `Derivacion`/`EntregaKit`) van en una sola migración (expand puro).

- **E-PERF-13** [INFO · S-M] Ninguna ruta de Emergencia está en los presupuestos ni en el banco MySQL
- **E-PERF-01** [MEDIA · M] El alta de un responsable nuevo recorre toda la tabla de ciudadanos con REGEXP, dos veces
- **E-PERF-02** [MEDIA · M] El candado del numerador de casos queda tomado hasta el commit, con fotos y reservas adentro
- **E-PERF-03** [MEDIA · S-M] El tablero recorre todo el histórico de casos en cada carga para quedarse con la ventana del día
- **E-PERF-04** [MEDIA · S-M] La página de la bandeja ordena por expresiones y ordena el historial entero de la solapa
- **E-PERF-05** [MEDIA · S-M] E4 (listado de entregas) ordena y pagina todo el histórico sin índice, con `select_related` en la consulta paginada
- **E-PERF-06** [BAJA · S] El tablero trae todas las entregas en camino con todas sus líneas para mostrar 20
- **E-PERF-07** [BAJA · S] Derivaciones y entregas se filtran por `estado` sin un índice que empiece por `estado`
- **E-PERF-08** [BAJA · S] Tres consultas fijas de la bandeja recorren todos los casos en cada carga
- **E-PERF-09** [BAJA · S-M] Dos aceptaciones simultáneas en el mismo dispositivo eligen las mismas camas y la segunda espera el candado para fallar siempre
- **E-PERF-10** [BAJA · S] Reservar las camas de la familia valida cada cama con dos consultas propias mientras las tiene todas tomadas
- **E-PERF-11** [BAJA · S] «Familia en la puerta» busca en todos los casos no cerrados en vez de en los de la foto
- **E-PERF-12** [BAJA · S] La lista de entregas pendientes de un dispositivo no tiene tope
- **E-PERF-14** [INFO · S] La ficha trae la traza completa, sin tope
- **E-PERF-15** [INFO · S] La derivación aceptada nunca deja de ser ACEPTADA y las lecturas de la guardia arrastran todo el histórico del dispositivo
- **E-DAT-01** [INFO · S] Las subconsultas «última traza» y «última rechazada» no tienen índice compuesto, y el `Exists` por `clave_vigente` no está medido

### Ola 3 · Correcciones menores y operación de vencimientos (24 h, 9 fichas)

Correcciones chicas de borde, cada una con su test. El cron de vencimientos ya está registrado como pendiente del PM; las demás no dependen de él.

- **E-ERR-03** [MEDIA · S] Los vencimientos de Emergencia corren una vez por día: las derivaciones vencidas quedan pendientes horas y las devoluciones por inacti…
- **E-ERR-11** [BAJA · S] Un número de más de 308 dígitos en una cantidad del Formulario 1 tumba el alta con un 500
- **E-ERR-12** [BAJA · S] «Familia alojada» acepta un sector dado de baja
- **E-ERR-13** [BAJA · S] El ingreso directo, si pierde una cama en la carrera, pide «volver a tocar Aceptar»
- **E-ERR-14** [BAJA · S] Si el UNIQUE de `uuid_cliente_recepcion` salta, la foto del remito queda huérfana en `media/`
- **E-ERR-15** [BAJA · S] «Marcar en camino» acepta una hora de salida anterior al armado de la entrega
- **E-ERR-16** [BAJA · S] «Casos por localidad» del tablero fusiona localidades homónimas de municipios distintos y su enlace filtra solo una
- **E-ERR-17** [INFO · M] Un ingreso en curso que nadie cierra retiene las camas de la familia sin plazo
- **E-ERR-18** [INFO · S] `kits._entero` levanta `ValueError` con «+-1» o «--1» (latente)

### Ola 4 · De fondo: reglas de dominio fuera de las vistas y los selectores (40 h, 12 fichas)

Regla de dominio escrita en la vista o en el selector que ya tiene el servicio. Empieza por la ALTA y por las que tienen divergencia real (`derivación pedida`, reposición, destino tras un cambio).

- **E-LIM-01** [ALTA · M] Las vistas de la guardia y de kits reescriben reglas de dominio que ya tiene el servicio
- **E-LIM-02** [MEDIA · S] La vista de cancelar derivación busca la pendiente y decide el `EstadoCambio` fuera del candado
- **E-LIM-03** [MEDIA · S-M] La compuerta «403 sin la capacidad, 404 sin alcance» está implementada dos veces con mecánicas distintas
- **E-LIM-04** [MEDIA · S-M] Kits no tiene `acciones_de_entrega`: la vista decide qué transición se ofrece con el estado crudo
- **E-LIM-05** [MEDIA · S] El enrutamiento «estado del caso → pantalla» está repartido en tres métodos y uno se pisa solo
- **E-LIM-06** [MEDIA · S-M] Dos definiciones de «ingreso directo»: el modelo mira `situacion` y el tablero infiere por `tomado_en == creado`
- **E-LIM-07** [MEDIA · S] La regla de plazas para derivar (RN-2.5) está escrita dos veces: en el panel y en `derivar_caso`
- **E-LIM-08** [MEDIA · S-M] Reglas de dominio en `selectors/` y dependencia cruzada entre selectores y servicios
- **E-LIM-09** [MEDIA · S] «¿Ve quién ocupa la cama?» lo decide cada vista, dos veces, con la capacidad redeclarada
- **E-LIM-10** [MEDIA · S] La guarda «el `?caso` tiene que estar derivado a este dispositivo» vive en la vista del mapa
- **E-LIM-11** [MEDIA · S-M] La tarjeta de la derivación se proyecta dos veces: serializer de la API y selector del backoffice
- **E-LIM-32** [BAJA · S] «La derivación vigente del caso» se consulta con tres consultas escritas a mano

### Ola 5 · De fondo: traductor único de errores de la API y de las vistas (22 h, 6 fichas)

Un módulo `programas/api/respuestas.py` y un `handle_exception` por superficie; las vistas de la web que repiten la escalera `try/except EstadoCambio` usan el mismo traductor. Se hace después de la Ola 4 para no mover dos veces las mismas vistas.

- **E-LIM-12** [MEDIA · M] Cada endpoint repite a mano la traducción de errores: el protocolo `(resultado, respuesta)` deja 23 ramas `if respuesta is not None`
- **E-LIM-13** [MEDIA · S-M] Cada superficie de la API de campo reescribe su traductor de errores, y Emergencia depende de un privado de Inspecciones
- **E-LIM-14** [MEDIA · S-M] La traducción de `EstadoCambio`/`ValidationError` está copiada nueve veces en dos archivos de vistas, con tres helpers locales duplica…
- **E-LIM-33** [BAJA · S] La respuesta de la recepción de kits no pasa por el serializer que la documenta
- **E-LIM-34** [BAJA · S] Relectura del caso con ORM en las vistas y el mismo cuerpo «reservadas/faltantes/integrantes» armado dos veces
- **E-LIM-35** [BAJA · S] Las vistas del backoffice importan del paquete de la API para filtrar el rechazo por DNI

### Ola 6 · De fondo: servicios de alojar, cierre y mesa (candados, transiciones, helpers privados) (62 h, 13 fichas)

Los seis módulos de la etapa 3 y la fachada de la mesa: orquestación de candados única, transiciones en un helper, resultados tipados en lugar de atributos colgados, helpers privados que pasan a públicos. Requiere definir primero la convención de fachadas (contradicción 7).

- **E-LIM-15** [MEDIA · M] La orquestación de candados del ingreso está copiada tres veces
- **E-LIM-16** [MEDIA · S-M] `alojar_familia` y `cerrar_con_diferencia` son dos copias del mismo cierre y cuentan distinto
- **E-LIM-17** [MEDIA · S-M] Las transiciones de caso y de derivación se escriben a mano en cada servicio
- **E-LIM-18** [MEDIA · M] Seis módulos y una fachada para un único flujo, unidos por ~20 helpers con nombre privado
- **E-LIM-19** [MEDIA · S-M] El contrato entre Dispositivos y Emergencia se apoya en helpers privados importados entre módulos
- **E-LIM-20** [MEDIA · M] Los servicios devuelven datos colgando atributos sueltos en instancias de modelo
- **E-LIM-21** [MEDIA · S-M] El mapa de Emergencia traduce el estado de una cama comparando rótulos de pantalla
- **E-LIM-22** [MEDIA · S] El ejecutor «una transacción por fila, falla al final» lo promete `core` y lo implementa Emergencia
- **E-LIM-23** [MEDIA · S] `EstadoCambio` vive en el módulo de la mesa y obliga a E3 y a kits a importar toda la etapa 2
- **E-LIM-24** [MEDIA · S-M] La fachada `services/emergencia.py` reexporta helpers privados y otros módulos los consumen como API
- **E-LIM-36** [BAJA · S] La fachada `emergencia_alojar` tiene dos rutas de importación, reexporta la ficha y conserva un envoltorio muerto
- **E-LIM-37** [BAJA · S-M] La regla de «cama libre» y el armado del mapa por sector están escritos dos veces
- **E-LIM-38** [BAJA · M] Las nueve acciones de la mesa repiten el mismo preludio de guardas

### Ola 7 · Limpieza: constantes, capacidades, formateadores y catálogos duplicados (32 h, 14 fichas)

Constantes, capacidades, formateadores y catálogos con un solo dueño. Cada ficha es chica; lo importante es el test de «un solo dueño» que las cierra.

- **E-LIM-25** [MEDIA · S-M] Formateadores de texto copiados en cinco o más módulos, con variantes que divergen
- **E-LIM-26** [MEDIA · S] Mensajes y topes de validación duplicados como literales entre forms y servicios, y un homónimo con dos textos
- **E-LIM-27** [MEDIA · S] La capacidad `"dispositivo.admitir"` está redeclarada en siete módulos
- **E-LIM-28** [MEDIA · S] La regla «foto JPEG de la app, hasta 5 MB» está escrita dos veces, en dos capas
- **E-LIM-29** [MEDIA · S] La tabla severidad→tono/ícono y la serialización del `Aviso` están copiadas en Emergencia y Dispositivos
- **E-LIM-39** [BAJA · S] El catálogo de necesidades del Formulario 1 tiene tres fuentes
- **E-LIM-40** [BAJA · S] `_marcas_de` está duplicada inline en `ids_por_estado_sla`
- **E-LIM-41** [BAJA · S] `responsables_alojados` no pasa por el manager `Estadia.objects.de_la_red`
- **E-LIM-42** [BAJA · S] `configuracion_emergencia` mezcla lecturas con escritura: `sla_vigente()` hace INSERT en cada GET y `catalogo_kits` es un selector en…
- **E-LIM-43** [BAJA · S-M] Las siete reglas de aviso repiten el mismo esqueleto «tope 5 + Aviso + "y N más"»
- **E-LIM-44** [BAJA · S] `selectors/kits.py` mezcla alcance de la guardia con lecturas de kits: autoriza dos veces y aloja `mis_dispositivos`
- **E-LIM-45** [BAJA · S] `acotar_relevado_en` reimplementa el recorte de reloj de `campo.acotar_capturado_en` y corre dentro de `validate_relevado_en`
- **E-LIM-46** [BAJA · S] La clase base del Formulario 1 conoce a su subclase (`pop("relevado_en", None)` + `relevado_en = None`)
- **E-LIM-47** [BAJA · S] Cuatro clases de permiso casi idénticas y el código `SIN_MODULO` redeclarado por superficie

### Ola 8 · Limpieza: presentación fuera de `selectors/` y tamaño de archivos (32 h, 9 fichas)

Presentación (rótulos, tonos, `reverse`) fuera de `selectors/`, y tamaño de archivos. La partición de `serializers_emergencia.py` en paquete va con la Ola 5.

- **E-LIM-30** [MEDIA · S-M] Tablas de presentación repartidas en servicio, *presenter* y vista
- **E-LIM-31** [MEDIA · S-M] La foto del tablero cruza módulos como tuplas posicionales (`fila[3]`, `fila[5]`) y se desarma a mano en 60 líneas
- **E-LIM-48** [BAJA · S-M] `selectors/emergencia_mesa.py` es un *presenter* que la guardia usa como bolsa de utilidades
- **E-LIM-49** [BAJA · S] `forms_emergencia.py` mezcla la configuración E7 con los formularios de la mesa
- **E-LIM-50** [BAJA · S-M] El selector del tablero arma tarjetas de pantalla (íconos, tonos, URLs) y lee dos veces las entregas en camino
- **E-LIM-51** [BAJA · S] `views/emergencia_dispositivo.py` pasa las 700 líneas, y el «sin derivación» que el PM quiere poder sacar sigue adentro
- **E-LIM-52** [BAJA · M] `selectors/emergencia_llegadas.py` está vivo pero es presentación del backoffice alojada en `selectors/`
- **E-LIM-53** [BAJA · S] `serializers_emergencia.py` (755 líneas) junta tres superficies que las vistas ya separaron
- **E-LIM-54** [INFO · S] Tamaño: `services/emergencia.py` pasa las 700 líneas y otros tres archivos se acercan

### Ola 9 · Limpieza: front de Emergencia (16 h, 4 fichas)

Esqueleto del modal y filtros de la bandeja. No se renombra `x-becas-modal` ni `programas/becas/_modal_*` en esta ola (decisión del juez); no se tocan clases ni estructura visibles para no romper los snapshots de Becas.

- **E-FE-01** [MEDIA · M] El esqueleto del modal con formulario está copiado cinco veces en la ficha del caso
- **E-FE-02** [BAJA · S-M] Los filtros de la bandeja se renderizan a mano mientras `FiltrosBandejaForm` declara las mismas opciones
- **E-FE-03** [BAJA · S] «Llegaron N sobre M declaradas» se arma dos veces en la ficha, con dos fuentes
- **E-FE-04** [BAJA · S] Los modales «Marcar en camino» y «Cancelar entrega» están escritos dos veces (listado y detalle) y dependen de parciales con nombre de…

## 4. Reglas propuestas

Consolidadas: las reglas de las fichas que dicen lo mismo quedan en una sola fila. «Control mecánico» primero; skill, agente y `CLAUDE.md` solo donde ningún control lo ve. Ninguna aplica a toda sesión, así que ninguna va a `CLAUDE.md`.

| # | Tipo | Destino | Regla | Fichas |
|---|---|---|---|---|
| R-1 | control mecánico | `programas/tests/test_arquitectura.py` (o `core/tests/`) · ratchet con `ast` | Un nombre con `_` inicial no se importa desde otro módulo de `programas/services` ni de `programas/api`. Lista congelada de lo existente; el conjunto no puede crecer. Alternativa: regla `PLC2701` de ruff con `per-file-ignores` congelado. Mensaje: «Importás un privado de otro módulo: hacelo público en su dueño o subilo a `programas/api/respuestas.py`». | E-LIM-13, E-LIM-18, E-LIM-19, E-LIM-24 |
| R-2 | control mecánico | `programas/tests/test_arquitectura.py` · «un solo dueño» | Un literal `"<modulo>.<accion>"` del `CATALOGO` de `core/rbac.py` se asigna a una constante en un solo módulo de `programas`; lo mismo para `CAP_ADMITIR`, `SIN_ALCANCE`, `TOPE_PLAZAS_POR_SECTOR` y los `code` de la API (`SIN_MODULO`), con el patrón de `test_la_constante_de_la_capacidad_publica_tiene_un_solo_dueno` (`:346`). | E-LIM-09, E-LIM-27, E-LIM-37, E-LIM-47 |
| R-3 | control mecánico | `programas/tests/test_arquitectura.py` / `test_capas.py` · capas | `programas/views/` no importa de `programas/api/`; los módulos de etapas posteriores no importan de la fachada `emergencia`; ningún `views/emergencia*.py` contiene `<Modelo>.objects.filter(` con `estado` ni `raise EstadoCambio`; ningún `programas/api/views_*.py` contiene `.objects.`; `def _errores_de` y `def _url(` solo existen en `emergencia_comun.py`. Excepciones congeladas. | E-LIM-01, E-LIM-02, E-LIM-14, E-LIM-23, E-LIM-34, E-LIM-35 |
| R-4 | control mecánico | `programas/tests/test_arquitectura.py` · ratchet de tamaño | Falla si un archivo de `services/emergencia*.py`, `selectors/emergencia*.py`, `views/emergencia*.py` o `programas/api/*.py` pasa de 1.000 líneas; aviso a las 700, sin `# TAMAÑO-OK: <motivo>`. (Umbral por decidir: contradicción 2.) | E-LIM-49, E-LIM-51, E-LIM-53, E-LIM-54 |
| R-5 | control mecánico | `programas/tests/test_arquitectura.py` · formato | `def (_)?(nombre_de|hora|fecha_hora|personas|camas|plazas)\(` solo puede existir en `programas/services/formato.py`; el test cruza `SEVERIDADES` con `TONOS` e `ICONOS` para que una severidad nueva sin tono ponga el CI en rojo. | E-LIM-25, E-LIM-29 |
| R-6 | control mecánico | `scripts/design_audit.py` · regla nueva `MODALSHELL` | Un template con más de una aparición de `role="dialog" aria-modal="true"` escrita a mano es hallazgo («usá `{% modal_form %}`»), en modo ratchet. | E-FE-01, E-FE-04 |
| R-7 | control mecánico | `core/tests/` · ratchet de REGEXP | Buscar en `programas/services/**` y `legajos/**` `__regex=` / `__iregex=` sin un filtro por índice (pk, FK o campo único) en la misma consulta; fallar con «REGEXP sin acotar: recorre la tabla entera. Indexá el valor normalizado.» | E-PERF-01 |
| R-8 | control mecánico | `scripts/check_perf_budgets.py` y `scripts/perf_budgets.json` | Fallar si un `app_name` de URLs del backoffice (p. ej. `emergencia`) no tiene al menos su listado en `perf_budgets.json`; y un test de patrón que falle si la consulta con `LIMIT` de un listado paginado lleva `JOIN` (`assert "JOIN" not in sql_de_la_pagina`). | E-PERF-05, E-PERF-13 |
| R-9 | control mecánico | `core/tests/test_cronjobs.py` · lectura de `docker/k8s/cronjobs.yaml` | Toda `ReglaVencimiento` con plazo en minutos (slug en `REGLAS_DE_MINUTOS`) tiene un CronJob con schedule `*/N` y N ≤ 5; si no, rojo. | E-ERR-03 |
| R-10 | control mecánico | test de regresión con mutación en cada ficha ERR/SEG | Cada arreglo lleva su test y se verifica quitando la guarda: el test tiene que ponerse rojo (mismo criterio que Becas). En SEG/ERR de identidad, el test usa un legajo existente con otro nombre. | E-SEG-01, E-ERR-01, E-ERR-04 |
| R-11 | skill | `.claude/skills/mysql-mariadb/SKILL.md` (transacciones, índices, trampas) | (a) Un contador con `select_for_update()` se toma al final de la transacción más externa; todo lo que corra después lo paga cada alta en cola contra el `read_timeout` de 10 s. (b) `buscar_ciudadano_por_dni` y `existe_con_dni` recorren `legajos_ciudadano` con REGEXP: se llaman fuera de todo candado y una vez por pedido; adentro del candado, solo el lookup exacto. (c) Un `filter(A | B | C)` usa índice solo si cada rama tiene uno. (d) Un índice `(a, b)` no sirve para `WHERE b = ?`: una vista global necesita el suyo que empiece por `estado`. (e) Una «última fila por padre» necesita el índice `(padre, fecha, id)`; un conteo por solapa va con índice que cubra todas las columnas de sus `filter=`. (f) «Primeras N + total» se cuenta con `COUNT` y se corta antes del `prefetch`. (g) Si se elige sin candado y se bloquea lo elegido con orden determinista, el perdedor reintenta una vez afuera de la transacción. | E-PERF-01, E-PERF-02, E-PERF-03, E-PERF-06, E-PERF-07, E-PERF-08, E-PERF-09, E-DAT-01 |
| R-12 | skill | `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas activas y §Trampas medidas | (a) Un `ORDER BY` por expresión (`Case/When`, `pk__in`) no lo sirve ningún índice: elegir los ids de la página primero. (b) `Subquery(… OuterRef … order_by(…)[:1])` en un listado: confirmar con EXPLAIN que el índice cubre filtro y orden. (c) Historial sin paginar: reportar la distribución por entidad antes de proponer un tope. (d) Un control «de a una fila» dentro de un bucle con las filas bloqueadas va en una consulta con `__in`. (e) Una regla del modelo (`q_*`) aplicada en un selector con ids candidatos se acota con `pk__in`. (f) Un índice `(padre, estado)` sobre un estado que no se cierra nunca no separa lo vivo de lo histórico. (g) `list(qs)` seguido de `[:n]` en Python: el recorte va en el queryset. (h) Todo listado de la API de campo lleva tope explícito en cada rama. | E-PERF-04, E-PERF-06, E-PERF-10, E-PERF-11, E-PERF-12, E-PERF-14, E-PERF-15, E-DAT-01 |
| R-13 | skill | `.claude/skills/seguridad-django/SKILL.md` (datos personales, API de campo, validación de entrada) | (a) Toda resolución de persona por DNI que escribe sobre el legajo o le abre una estadía compara nombre y apellido declarados con el legajo encontrado (patrón `DniRegistrado`): el DNI identifica, no autoriza a escribir. (b) La idempotencia por `uuid_cliente` es un atajo de lectura: el objeto que devuelve el reenvío pasa la misma guarda de alcance que un GET de ese objeto; si la respuesta trae datos de personas, la vista no puede apoyarse en que «el servicio ya acotó». (c) Cuando un tope de privacidad reemplaza un error para ocultar un dato, el reemplazo conserva el tipo del error. (d) Toda conversión numérica de entrada que pase por `float()` atrapa `OverflowError`; un parser de enteros a mano se prueba con signos repetidos. (e) Un selector que recibe `usuario` decide él mismo qué dato personal muestra; no recibe un booleano calculado por la vista. | E-SEG-01, E-ERR-01, E-ERR-04, E-ERR-11, E-ERR-18, E-LIM-09 |
| R-14 | skill | `.claude/skills/auditoria/rubricas/correccion-seguridad.md` (y la rúbrica de errores) | (a) Un POST de la web que crea una entidad con número correlativo o con efecto externo lleva identificador de envío oculto y lo pasa al servicio idempotente; la guardia JS de doble clic no cuenta. (b) Una guarda que compara contra «lo que la pantalla mostró» (`derivacion_vista`, `uuid_cliente`, un `version`) viaja como oculto desde todas las superficies que llaman al servicio. (c) En un servicio idempotente, «ya se hizo» va antes que la guarda de estado. (d) Todo id que llega del cliente y sale de una lista se valida con el mismo filtro que arma la lista. (e) Un helper compartido no fija textos de pantalla que nombran botones. (f) Toda reserva sin `hasta` necesita un camino de liberación o un docstring que no prometa vencimiento. (g) En una función con `@archivos_atomicos`, todo `save()` de un `FileField` dentro de `try/except` anota el archivo también en la rama del `except`. (h) Una fecha de hito tiene los dos límites. (i) Agrupar por un nombre no único pierde la identidad: el enlace de la fila no elige un id al azar. (j) Cada «idempotente: no se valida nada» del contrato se contrasta con lo que la vista valida antes del servicio, y el contrato declara qué códigos son terminales para la cola. | E-ERR-02, E-ERR-05, E-ERR-06, E-ERR-07, E-ERR-08, E-ERR-09, E-ERR-10, E-ERR-12, E-ERR-13, E-ERR-14, E-ERR-15, E-ERR-16, E-ERR-17 |
| R-15 | skill | `.claude/skills/auditoria/rubricas/codigo-limpio.md` (tabla de helpers canónicos y «Qué escalar») | Filas nuevas: (a) cargar un dispositivo con alcance → `dispositivo_operable_o_404` / mixin común; un `dispatch` propio que reimplementa 403/404 es duplicado; (b) traducir excepciones de dominio a HTTP en la API de campo → `handle_exception` de la vista base de la superficie; (c) foto que sube la app (JPEG, 5 MB) → `validar_jpeg_de_la_app`; (d) armado de pantalla (textos, tonos, URLs, stepper) → `programas/presentacion/`, nunca `selectors/`; (e) una vista que compara `.estado` para decidir qué botón mostrar pide `acciones_de_<x>()` al servicio; (f) si un selector clasifica algo para ofrecer o bloquear un botón, el servicio que decide consume esa misma función; (g) una regla de negocio que un servicio necesita no se define en `selectors/`; (h) un mensaje o tope que el servicio valida se importa en el form; (i) una tupla de `values_list` que sale de su módulo se convierte en dataclass; (j) un servicio que devuelve más que la fila devuelve un `Resultado*`; (k) dos servicios con el mismo estado final comparten un helper `_pasar_*`; (l) una función de «lectura» no hace `get_or_create`; (m) topes de listas en el selector; (n) `validate_<campo>` solo traduce forma; (o) una autorización se resuelve una vez, en la frontera; (p) un catálogo cerrado con rótulo es un `TextChoices`; (q) una condición que codifica un invariante de modelo se lee por un método del manager. | E-PERF-12, E-LIM-03, E-LIM-04, E-LIM-05, E-LIM-06, E-LIM-07, E-LIM-08, E-LIM-10, E-LIM-11, E-LIM-12, E-LIM-13, E-LIM-16, E-LIM-17, E-LIM-20, E-LIM-21, E-LIM-22, E-LIM-26, E-LIM-28, E-LIM-30, E-LIM-31, E-LIM-32, E-LIM-33, E-LIM-38, E-LIM-39, E-LIM-40, E-LIM-41, E-LIM-42, E-LIM-43, E-LIM-44, E-LIM-45, E-LIM-46, E-LIM-48, E-LIM-50, E-LIM-52 |
| R-16 | agente | `.claude/agents/chaco-frontend.md` | Un modal que aparece en más de una pantalla del mismo módulo va en un parcial `_modal_<accion>.html` desde el primer uso; si existe un Form para los parámetros de una pantalla, sus controles se renderizan desde el Form; en pantallas con presenter en Python, el template no redacta frases con datos: las imprime. | E-FE-01, E-FE-02, E-FE-03, E-FE-04 |
| R-17 | agente | `.claude/agents/chaco-auditor.md` | En `views/emergencia*.py`, un `raise EstadoCambio` o una consulta que decide si la acción procede es hallazgo: va al servicio. | E-LIM-02 |

## 5. Descartados

Lo que los revisores miraron y salió limpio (para que la próxima auditoría no lo reabra), más la decisión del juez sobre `selectors/emergencia_llegadas.py`.

- **`selectors/emergencia_llegadas.py` NO es código muerto** (decisión del juez, confirmada por E4): lo importa `programas/views/emergencia_dispositivo.py:57` (alias `pantalla`) y `programas/tests/test_emergencia_alojar.py:35`; sus 8 funciones públicas tienen consumidor. Lo que tiene es un problema de capa (E-LIM-52).
- **Kits y stock:** no hay duplicación, no existe ningún modelo de stock o depósito (RN-4.6, `services/kits.py:3-4`). Descartado (E3 calidad).
- **Sincronización por «cambios desde»:** no existe en la API de campo; no hay columna de fecha que indexar para eso (E4 perf).

### E1 · corrección y seguridad

- **Transiciones del caso:** cada servicio bloquea primero el caso (`_bloquear_caso`, sin JOIN) y decide con la
  fila bloqueada. No hay un camino de E1 que deje un estado imposible: derivar exige `EN_GESTION` y deja `DERIVADO`
  con una derivación `PENDIENTE`; cancelar y vencer exigen las dos cosas a la vez (`emergencia.py:594`, `:664-666`);
  cerrar exige `EN_GESTION` (un `DERIVADO` no se cierra); `CERRADO` es terminal (`_exigir_abierto`, `_exigir_estado`).
- **Doble derivación:** `clave_vigente` con `UniqueConstraint` **sin** `condition` (existe en MariaDB) y el
  `IntegrityError` se atrapa en un `atomic` anidado y se traduce a `EstadoCambio` (`emergencia.py:549-558`).
- **Doble «Tomar» / dos operadores:** el segundo espera el candado, lee el caso ya tomado y recibe
  `CasoTomadoPorOtro`; quien ya lo tiene tomado recibe el caso sin traza (`emergencia.py:326-331`).
- **Cron contra operador:** `vencer_derivacion` y `devolver_a_bandeja_por_inactividad` bloquean en el mismo orden y
  vuelven a mirar la condición sobre la fila bloqueada; devuelven `None` sin escribir.
- **RBAC:** todas las vistas heredan `MesaPermissionMixin` (`emergencia.operar` o `supervisar` con alcance al
  programa); `ReasignarCasoView` sube a `supervisar`. Cada servicio vuelve a exigir la capacidad y el «dueño o
  supervisor» sobre la fila bloqueada. Las dos lecturas que salen hacia Dispositivos
  (`dispositivos_para_derivar`, `responsables_alojados`) exigen la mesa ellas mismas. Nada autoriza por nombre de grupo.
- **Idempotencia de la app:** `uuid_cliente` único sobre columna anulable, búsqueda con `q_uuid_en_texto`, el
  `IntegrityError` del reenvío simultáneo vuelve el caso del primero; el mismo uuid de otro usuario es `UuidEnUso`.
- **XSS:** ningún `|safe`, `mark_safe`, `format_html` ni dato interpolado en JS/Alpine en los templates del
  alcance ni en las piezas que consumen (`_alerta`, `_linea_tiempo`, `_tarjeta_dispositivo_derivar`, `nodo_ui`);
  el toast pinta con `textContent` (`nodo-toast.js:148`).
- **Datos personales:** la traza y los logs no nombran a la familia (`_trazar`, `crear_caso` loguea `usuario.pk`
  y `origen`); el nombre del «DNI ya registrado» descuenta de la cubeta SEC-25 (`rechazo_para_mostrar`); las fotos
  se sirven por `core.views.media._adjunto_de_emergencia` solo a la mesa y a la guardia de la derivación vigente.
- **MariaDB:** sin `Trunc*` (el semáforo se calcula en Python), sin `UniqueConstraint` condicional, UUID con
  `q_uuid_en_texto`.

### E1 · rendimiento

- **Índices de los filtros de la mesa:** `estado` y `prioridad` → `(estado, prioridad)`; «Míos»/operador →
  `(tomado_por, estado)`; `localidad` → índice de la FK; `origen` solo se filtra junto con
  `estado <> CERRADO`. La bandeja no filtra por fechas ni por dispositivo. No falta índice para filtrar.
- `ids_por_estado_sla` (`selectors/emergencia.py:198`): una consulta por el índice de `estado`, acotada a
  los abiertos con SLA; semáforo en Python. No hay `Trunc*`, `__date` ni `CONVERT_TZ` en el alcance.
- `posibles_duplicados_de` y `responsables_alojados`: 3 + 1 consultas por página, por índices (FK
  `responsable`, FK `ciudadano`, UNIQUE `clave_alojamiento`). Sin N+1.
- `Paginator.count`: Django 5.2 saca del `COUNT` las anotaciones sin usar y el `select_related`.
- Panel «Derivar» (`dispositivos_para_derivar`): 4 consultas fijas, agregadas por sector; crece con las
  plazas de la red (≈ 10.000), no con los casos. Se mide con `emergencia_ficha` (E-PERF-13).
- `_caso_de_ese_envio` (`emergencia_alta.py:362`): `q_uuid_en_texto` compara por igualdad, sin función
  sobre la columna; usa el UNIQUE de `uuid_cliente` (`char(36)`, `0119`).
- Acciones POST: `_bloquear_caso` por pk, sin JOIN; dentro del candado de `derivar_caso` solo
  `ocupacion_de_plazas` de un dispositivo. Sin llamadas externas dentro de candados en el alcance.
- Polling: no hay.

### E1 · calidad

- **Tamaños.** Ningún archivo del alcance pasa las 1.000 líneas. Los que superan 700 o se acercan:
  `services/emergencia.py` 769, `selectors/emergencia.py` 668, `selectors/emergencia_mesa.py` 656 y
  `forms_emergencia.py` 631. Ver E-LIM-54: con LIM-01, LIM-02 y LIM-05 aplicadas,
  `services/emergencia.py` baja a unas 640 líneas sin partirlo.
- **`emergencia_comun` y `emergencia_ingreso_comun`.** La partición sigue la responsabilidad: `comun`
  tiene lo del caso (traza, permiso de la mesa, numerador, candado del caso) y `ingreso_comun` lo de
  la etapa 3 del dispositivo (alcance, candados de la derivación, reserva de camas). La segunda
  importa de la primera y no repite su lógica. Lo duplicado entre los dos son los formateadores de
  texto (LIM-06), y la frontera tiene una fuga: `ingreso_comun` importa `EstadoCambio` de la fachada
  `emergencia` (LIM-01).
- **`selectors/emergencia` y `selectors/emergencia_mesa`.** También van por responsabilidad: el
  primero hace las consultas que comparten la API y el tablero, y el segundo arma lo que dibujan E2
  y E3. Las consultas no están duplicadas. Hay tres problemas: `emergencia_mesa` es un *presenter*
  con nombre de selector y la guardia lo usa como bolsa de utilidades (LIM-11); la regla de
  elegibilidad y la de plazas viven en el selector y el servicio las repite (LIM-03, LIM-04); y la
  derivación vigente se lee con tres consultas escritas a mano (LIM-12).
- **Reuso de Dispositivos: bueno.** `ocupacion_de_plazas`, `alta_minima_de_persona`,
  `buscar_ciudadano_por_dni`, `Estadia.clave_para` y `puede_operar_dispositivo` se usan, no se
  reimplementan. `responsables_alojados` es una versión de solo lectura de
  `verificar_alojamiento_en_red`, con motivo documentado (permisos distintos). Su único desvío es
  que no pasa por el manager `de_la_red` (LIM-17).

### E2 · corrección y seguridad

- **Doble asignación de plaza.** Todo camino que escribe sobre una plaza la bloquea y vuelve a mirar con la fila tomada: `reservar_plazas_de_derivacion` (`reservas_derivacion.py:157-170`), `consumir_reserva_de_derivacion` (`:244-257`) y `_ingresar_en_cama_libre` (`emergencia_confirmacion.py:287-305`) terminan en `estadias.ingresar_persona`, que relee con `_bloquear_plaza` + `_exigir_plaza_libre` (`estadias.py:465-471`) y el `UNIQUE` de `clave_alojamiento`. La baja de sector bloquea todas sus plazas (`plazas.py:336`), así que no se cruza con la reserva.
- **Doble aceptación / aceptar y vencer a la vez.** Caso → derivación con `FOR UPDATE` y `_exigir_pendiente`; el `UNIQUE(clave_vigente)` sin condición sostiene «una vigente por caso» en MySQL y MariaDB.
- **Caso cerrado con estadía abierta.** La única transición a `CERRADO` desde la etapa 3 es `_cerrar_si_no_queda_nadie`, que exige ninguna estadía `ACTIVA`; `cancelar_ingreso` exige 0 confirmadas (`emergencia_cierre.py:294-298`), y la mesa solo cierra desde `EN_GESTION`/`NUEVO`. Con `read committed`, dos egresos simultáneos de los dos últimos integrantes cierran el caso en el segundo.
- **Reservas de derivación colgadas al cerrar.** `alojar_familia`, `cerrar_con_diferencia` y `cancelar_ingreso` las liberan con el caso y la derivación bloqueados; `liberar_reserva` corre en savepoint y el `except ValidationError: continue` no deja la transacción rota.
- **Alcance del operador.** Todos los servicios exigen `dispositivo.admitir` sobre el dispositivo **de la derivación** antes del primer candado (`_dispositivo_de`, `ingreso_sin_candado`); `puede_operar_dispositivo` no aplica `ver_todos` a `admitir` (`dispositivos.py:233-236`). Las API resuelven el recurso dentro de `dispositivos_en_alcance` y traducen a 404. Las reservas comunes de otro dispositivo se liberan sin alcance por la D2 (decisión registrada).
- **Idempotencia de aceptar/rechazar/cerrar/cancelar.** No son idempotentes por contrato (§13.3, §13.9): el reintento da 409 de estado y `derivacion_vista` (Cambio 477) evita actuar sobre una derivación nueva.
- **Ciclo egreso ↔ confirmación** (`ERROR 1213`): documentado y aceptado en el docstring de `emergencia_alojar` («La excepción conocida»); la transacción perdedora se deshace entera.

### E2 · rendimiento

- **«Buscar plaza libre en todos los dispositivos»**: no vive en esta tajada (la elección de dispositivo de la mesa está en `programas/selectors/emergencia.py`). Acá `camas_libres` y `plazas_para_caso` son de **un** dispositivo: 3 o 4 consultas fijas, `IN` sobre las camas del dispositivo contra `(plaza, estado)` de `Estadia` y de `ReservaPlaza`; no tocan el histórico de estadías. `resumen_de_llegadas` son 3 fijas con dos `NOT EXISTS` por el índice `(plaza, estado)`: con 5.000 plazas, unas 10.000 sondas de índice (milisegundos).
- **`select_for_update` mientras se calcula la ocupación**: la foto de camas se toma **sin** candado sobre plazas; las plazas se bloquean después, por pk, sin JOIN. El candado de caso y derivación sí cubre `camas_libres`, pero solo lo esperan pedidos sobre la misma familia. La colisión entre familias está en E-PERF-09.
- **Reservas vencidas recorridas en Python**: en el alcance solo se recorren las reservas abiertas **de una derivación** (FK indexada, hasta el tamaño de la familia) y las comunes **de una persona** (`(ciudadano, estado)`); la vigencia se evalúa en SQL (`vigentes` / `que_toman`), sin `Trunc*`.
- **Cierre que recorre todo el historial**: `_cerrar_si_no_queda_nadie` y `al_egresar_estadia` son 1 o 2 consultas por FK única o indexada (`grupo`, `estadia`); el receptor hace 1 sola consulta para los egresos que no son de Emergencia.
- **Orden de candados** caso, derivación, plazas (por pk), reservas, persona: respetado en recepción, confirmación, cierre y reservas de derivación; ningún `FOR UPDATE` con JOIN.
- **DAT (datos y migraciones)**: sin hallazgos en el alcance. Los índices `Plaza (sector, estado)`, `Estadia (plaza, estado)`, `ReservaPlaza (plaza, estado)` y la decisión documentada de **no** indexar `ReservaPlaza (derivacion, estado)` son coherentes con las consultas leídas.
- `puede_operar_dispositivo` se reevalúa 4 a 6 veces por confirmación (1 consulta cada una, sin memo): número fijo, no crece con el volumen; no se reporta.

### E3 · corrección y seguridad

- **Alcance de la guardia (SEG).** `RecepcionKitsMixin` (`emergencia_kits.py:530-549`) resuelve el dispositivo dentro de `dispositivos_en_alcance(user, CAP_RECIBIR_KIT)`; `RecibirKitView._entrega` filtra por ese dispositivo (404 la ajena); el servicio vuelve a exigir `puede_recibir` sobre la entrega. `GuardiaView` (`emergencia_dispositivo.py:78-91`) exige `dispositivo.admitir` y `dispositivo_operable_o_404`; derivaciones y casos se buscan siempre con `dispositivo=self.dispositivo` (`:132-139`, `:201-203`, `:261-268`). El remito en `core/views/media.py:267-283` pide mesa o `recibir_kit` sobre **ese** dispositivo. Sin fuga entre dispositivos.
- **RBAC.** Tablero y E7: `emergencia.supervisar` con alcance de programa (`EmergenciaPermissionMixin`); kits de la mesa: `puede_operar_la_mesa` en mixin **y** en servicio. Ningún chequeo por nombre de grupo.
- **Kits: stock negativo / entregas concurrentes.** No hay stock (RN-4.6). Recibir, cancelar, marcar en camino y observar bloquean la fila (`select_for_update`) y releen el estado: un doble POST de «Confirmar recepción» o la carrera cancelar/recibir termina en `EstadoCambioEntrega`, no en doble recepción. Cantidades acotadas a `CANTIDAD_MAXIMA`.
- **Vencimientos: idempotencia y carrera con el operador.** `vencer_derivacion` bloquea caso → derivación y revalida estado y `vence_en`; `devolver_a_bandeja_por_inactividad` bloquea el caso y revalida el límite de inactividad leyendo trazas después del candado; registrar un contacto deja `TrazaCaso` (`services/emergencia.py:462-472`). Registro de reglas y avisos idempotente por slug.
- **Fechas / zona horaria.** Ningún `Trunc*` ni `__date`: día operativo y filtro por fecha de E4 son rangos calculados en Python (`dia_operativo`, `rango_del_dia`) con `__gte/__lt`. El año del numerador K es el local.
- **Configuración.** Rangos por validadores del modelo (`objetivo ≥ 1`, vigencia ≥ 30, umbral 50–95, `inicio_evento` no futuro), regla de consumo completa o vacía (`TipoKit.clean`), guardado en una transacción con candados en orden de pk. Que dos supervisores simultáneos se pisen campos («gana el último») está documentado como decisión.
- **XSS.** Ningún `|safe`, `mark_safe`, `format_html` ni valor de usuario dentro de `<script>`/atributos JS en las vistas, servicios y templates del alcance; todo pasa por el autoescape.

### E3 · rendimiento

- **`Trunc*`/`__date`/`CONVERT_TZ`:** buscados activamente (`Trunc|__date|__year|__month|Extract`) en los 12 archivos Python del alcance y en los selectores que consumen (`emergencia_alojar.py`, `emergencia_llegadas.py`): no hay ninguno. «Hoy» es `dia_operativo()` en Python (`emergencia_tablero.py:97-108`) y el filtro de fecha de E4 es `rango_del_dia()` (`kits.py:80-85`), los dos con `__gte`/`__lt`.
- **Agregados del tablero:** `resumen`, `por_localidad`, `tiempos` y las 7 reglas de avisos trabajan sobre la foto en Python, con 0 consultas; mediana/p90 en Python sobre ~1.200 valores. No hay GROUP BY en SQL ni recorridos por caso.
- **Red de dispositivos del tablero:** `red_de_dispositivos` (`emergencia_tablero.py:290-317`) = 1 consulta de 200 dispositivos + 3 fijas de `ocupacion_de_plazas` en lote. `sin_plazas_con_derivacion_pendiente` solo suma 3 si hay una pendiente hacia un dispositivo no elegible.
- **Cron de vencimientos:** no hay `atomic` largo. Las dos reglas se registran con `transaccion_unica=False` y cada fila corre en su propia transacción con candado caso → derivación (`vencimientos_emergencia.py:66-94`, `emergencia.py:640-718`). `casos_sin_avance` es un `NOT EXISTS` correlacionado sobre ~cientos de `EN_GESTION` (índice `(estado, prioridad)` + FK de `TrazaCaso`). El costo por fila (2-5 consultas) está acotado por las filas vencidas, no por el histórico. La frecuencia diaria del cron ya está registrada como pendiente de decisión del PM (`docs/internal/requerimientos.md:55188-55200`): no se repite como hallazgo.
- **Avisos:** sin tabla ni estado, `TOPE_POR_REGLA = 5`, sin consultas con foto salvo E-PERF-11.
- **Configuración E7:** `sla_vigente()` = 1 `get_or_create`; `guardar_configuracion` bloquea los `TipoKit` en una sola consulta ordenada por pk. Hace un `exists` y una inserción de traza por ítem editado dentro de la transacción, acotado por el catálogo (~50): no hay mecanismo que crezca con el uso, así que no se reporta.
- **Kits, servicios:** `crear_entrega` valida antes de tomar el numerador y escribe las líneas con `bulk_create`; `recibir_entrega` bloquea solo la fila de la entrega, usa `bulk_update` y `q_uuid_en_texto` (igualdad sin función sobre la columna, usa el UNIQUE). No existe un modelo de stock ni de movimientos de kits: en ninguna pantalla hay sumas de stock (el foco «stock de kits» no aplica a este SHA).
- **Kits, detalle E5, pendientes del dispositivo y recepción:** 3 consultas fijas en el detalle; `entregas_pendientes_de` y `mis_dispositivos` usan el índice `(dispositivo, estado)`; `resumenes_de_destino` es fijo (5) y acotado a la página de 20 destinos (el `pk__in` sobre `MAX(id) GROUP BY dispositivo` corre sobre las entregas de esos 20, por el índice de la FK).
- **Pantalla del dispositivo (E6):** no hay N+1 por plaza, sector ni estadía. `llegadas_del_dispositivo` es 1 consulta con `select_related` y `Count` anotado, acotada al dispositivo por `(dispositivo, estado)`; `plazas_para_caso` = 4 fijas (camas con sector, `estado_de_plazas` en lote, derivación vigente) con tope de 200 plazas por sector; `integrantes_de` = 1 con `select_related("ciudadano", "estadia__plaza__sector")`; `fotos_del_caso` = 1. Los templates de `kits/**` y `dispositivo/**` no acceden a relaciones fuera de lo cargado ni usan `|length` sobre querysets.
- **Formularios:** `ItemsEntregaForm` recorre el catálogo (queryset evaluado una vez, ~50 filas); `FamiliaAlojadaForm` recibe los sectores del dispositivo. No hay `ModelChoiceField` sobre tablas grandes.

### E3 · calidad

- **Vencimientos: ¿reusa el registro de `procesar_vencimientos`?** Sí. `vencimientos_emergencia.py:143-164` registra
  dos `ReglaVencimiento` en `core.services.vencimientos` y las corre el mismo comando que las de Becas. No hay
  un segundo mecanismo. Lo que queda fuera de lugar es el ejecutor fila por fila (E-LIM-22).
- **Avisos vs. notificaciones:** no duplica el sistema de notificaciones (SES/SMTP/toast). Usa el registro
  `ReglaAviso` de core igual que `alertas_dispositivos.py`. Lo que está copiado es la tabla severidad→tono/ícono
  y la serialización del aviso (E-LIM-29), y las siete reglas repiten el mismo esqueleto (E-LIM-43).
- **Kits ↔ stock:** **no hay duplicación**. No existe ningún modelo de stock o depósito en `programas` ni en
  `core`. RN-4.6 lo excluye a propósito (`services/kits.py:3-4`, `models/__init__.py:6296`). Descartado.
- **Regla de 1000 líneas:** ningún archivo del alcance pasa de 1000. `views/emergencia_dispositivo.py` (726)
  pasa de 700 (E-LIM-51). `selectors/emergencia_tablero.py` (677) y `views/emergencia_kits.py` (626) se acercan.
- Ya registrados, no se repiten: `CAP_ADMITIR` redeclarado en `views/emergencia_dispositivo.py:63` (E-LIM-27).
  `nombre_de`/`fecha_hora`/`_nombre_de` en `selectors/kits.py:68-77` y `services/kits.py:138` (E-LIM-25).
  `_hora` importado como privado en `services/kits.py:70` (E-LIM-18/06). `CANTIDAD_RECIBIDA_INVALIDA` con dos
  textos en `forms_emergencia_kits.py:34` y `services/kits.py:108` (otro caso de E-LIM-26).

### E4 · corrección y seguridad

- **Alcance / IDOR por pk.** Cada ruta con id resuelve sobre un queryset ya acotado: dispositivo
  (`_VistaDeLlegadas._dispositivo`, `views_emergencia_llegadas.py:110-112`; `EntregasDelDispositivoView`,
  `views_emergencia_kits.py:107`), entrega (`_VistaDeKits._entrega`, `views_emergencia_kits.py:81-83` sobre
  `selectors/kits.py:247-259`), derivación (`views_emergencia_llegadas.py:114-116`) y caso
  (`ingreso_sin_candado`, `services/emergencia_ingreso_comun.py:116-124`, última derivación + `_exigir_alcance`).
  Lo ajeno da el mismo 404 que lo inexistente. El mapa con `?caso=` además compara
  `derivacion.dispositivo_id` (`views_emergencia_llegadas.py:520-522`). El servicio vuelve a exigir alcance.
  La única fuga de alcance encontrada es por `uuid_cliente`, no por pk (E-SEG-01).
- **Permisos.** Las cuatro clases (`views_emergencia.py:124-168`) usan solo capacidades vía
  `emergencia_programa` (nada por nombre de grupo). `CasosEmergenciaView` reemplaza `EmergenciaModuloPermission`
  por `EmergenciaRelevarPermission`, que es un subconjunto de `modulo_habilitado` (`emergencia_programa.py:136-148`):
  no abre de más. `permission_classes` corre antes que `throttle_classes` (DRF `initial()`), así que un 403 no
  consume cubeta.
- **Throttling.** `personas_campo` (120/h) y `emergencia_buscar` (300/h) existen en
  `config/settings.py:606,612`; ambas por usuario. El rechazo `DniRegistrado` descuenta de la misma cubeta en
  los tres extremos que crean casos (`views_emergencia.py:272-277`) y el `Throttled` sale como 429 con
  `Retry-After`.
- **Traducción de errores.** `_ejecutar` (`views_emergencia.py:262-279`) atrapa `UuidEnUso` y `DniRegistrado`
  **antes** que `ValidationError` (son subclases) y `EstadoCambioEntrega` hereda de `EstadoCambio`
  (`services/kits.py:120`): ningún rechazo del servicio conocido llega como 500. `_respuesta_400` aplana bien
  los errores de DRF (el `DictField` de cantidades devuelve un solo mensaje, `serializers_emergencia.py:312-318`).
- **UUID con/sin guiones.** Todas las búsquedas por `uuid_cliente` usan `q_uuid_en_texto`
  (`emergencia_alta.py:362`, `kits.py:453`); la comparación de la entrega bloqueada es entre objetos `UUID`
  (`kits.py:490`) y la de integrantes entre `str(UUID)` normalizados de los dos lados
  (`emergencia_confirmacion.py:367,535`). Las columnas son `char(36)` (`0119`, `0121`).
- **Entrada.** `latitud`/`longitud`/`precision_m` aceptan `nan`/`inf` en el `FloatField` de DRF, pero el
  servicio los rechaza (`emergencia_alta.py:248-263`: `nan` falla el rango, `inf` da `OverflowError` atrapado).
  Fotos: extensión + firma + 5 MB (`serializers_emergencia.py:46-57`) y el modelo revalida. Ids enormes en la URL
  o en `?caso=` no rompen: Django 5.2 devuelve vacío en lookups enteros fuera de rango.
  La cantidad enorme en `cantidades[<id>]` de la recepción (`serializers_emergencia.py:334`, `IntegerField`
  sin `max_value`) es la misma causa raíz que **E-ERR-11**: se cita ahí, no se repite.
- **Respuestas.** Ningún serializer de salida trae campos de más fuera del alcance: `CasoEmergenciaCreado` y
  `MiCaso` son mínimos; `DerivacionLlegada` (DNI, teléfono, observaciones) solo sale para derivaciones hacia un
  dispositivo del usuario; el ocupante de la cama solo con `ciudadano.ver` (igual que el backoffice,
  `views/emergencia_dispositivo.py:388`); la ficha de `integrante_de` saca `CLAVES_DE_ENVIO`.
- **`selectors/emergencia_llegadas.py` no está muerto.** La API no lo usa, pero las 8 funciones públicas tienen
  consumidor en el backoffice (`programas/views/emergencia_dispositivo.py:57`, alias `pantalla`) y en
  `programas/tests/test_emergencia_alojar.py:35`. Su ubicación ya está en E-LIM-52.

### E4 · rendimiento

- **Sincronización por «cambios desde»**: no existe. Ninguna ruta de `api_emergencia_urls.py` baja casos,
  llegadas, dispositivos o kits por fecha; la app sube (M1 y M2-6 se encolan) y lee por id o por
  dispositivo. No hay columna de fecha que indexar para esto.
- **Listados sin paginar** (son `APIView` sin paginador, a propósito por contrato): `casos/mios/` corta en
  50 (`selectors/emergencia_campo.py:11,27`, 1 consulta por la FK `relevado_por`; el orden por `creado` es
  un filesort de los casos de **un** agente, decenas a cientos); `localidades/` son las de la provincia
  (cientos, 1 consulta, la app la baja una vez por día); `mis-dispositivos/` como mucho los 200 de la red
  (4 + 3 consultas fijas; `resumen_de_llegadas` ya revisado en E2); `entregas/` sin `pendientes` corta en
  50; `…/plazas/` es un dispositivo (tope 200 por sector, 4 consultas fijas, E2); `…/integrantes/` es una
  familia (1 consulta).
- **Serializers con N+1**: ninguno. `DerivacionLlegadaSerializer` (5 `SerializerMethodField`) serializa
  **una** derivación y lo que lee viene del `select_related` de `buscar_por_dni`
  (`emergencia_recepcion.py:156`) o de `situacion`/`necesidades` (JSON de la misma fila); `nombre_de` no
  consulta (`selectors/emergencia_mesa.py:74-79`). `EntregaKitSerializer.lineas` va por
  `Prefetch(... select_related("item"))` (`selectors/kits.py:88-89`) en lista y detalle. `total_declarado`
  (`source="grupo.total_declarado"`) sale de un `select_related("grupo")` en `casos/mios/`, `_filas` y el
  aviso a la mesa; en el reenvío idempotente de `casos/` es 1 consulta más, fija. El CI ya lo cubre con
  `zeal` y con los `assertNumQueries` independientes de N de `test_emergencia_api_m1.py:513-530`,
  `test_emergencia_api_kits.py:344-422`, `test_emergencia_api_m2.py:240-289` y `test_emergencia_api_contrato.py:683-698`.
- **Fotos en base64**: no. Fotos y remito van como `FileField` multipart (`serializers_emergencia.py:153-166`,
  `:341-346`); `DATA_UPLOAD_MAX_MEMORY_SIZE` (5 MB) no cuenta archivos y por encima de
  `FILE_UPLOAD_MAX_MEMORY_SIZE` (2 MB) Django las vuelca a disco temporal, no a la base. Que el reenvío de la
  cola vuelva a subir las dos fotos antes de saber que el caso ya existe es costo de red, no de base; que se
  escriban con el numerador tomado es E-PERF-02.
- **Idempotencia por `uuid_cliente`**: `q_uuid_en_texto` compara por igualdad contra las dos formas, sin
  función sobre la columna (`core/db.py:43-46`): usa el `UNIQUE` (`char(36)` por `0119`/`0121`). La de
  `confirmar`/`agregar` mira el JSON de las filas de **una** familia.
- **Throttling**: solo `personas/consultar/` (`personas_campo`, 120/h) y `…/buscar/` (`emergencia_buscar`,
  300/h) tienen tope, por usuario, contra el cache (Redis en los ambientes servidos), no contra la base. Las
  escrituras no tienen tope: un throttle no aliviaría la contención, que es el candado único del numerador
  (E-PERF-02) y se resuelve ahí. DRF evalúa los permisos antes que el throttle, así que un 429 cuesta igual
  las 3 a 5 consultas fijas de alcance: no crece con el volumen; no se reporta.
- **Permisos por request**: `modulo_habilitado` + `admite_familias`/`recibe_kits` + el alcance de la vista +
  `_exigir_alcance` del servicio repiten `dispositivos_en_alcance(...).exists()` / `puede_operar_dispositivo`
  (ya anotado en E2, «Revisado sin hallazgo»): número fijo, subconsultas sobre el Equipo del usuario.
- **Búsquedas por id con alcance** (`_o_404`, `_derivacion`, `entregas_al_alcance`): `pk = X AND
  dispositivo_id IN (subconsulta del Equipo)`, por PK.
- **`Trunc*` / `CONVERT_TZ` / `__date`**: ninguno en el alcance. `selectors/emergencia_llegadas.py` es del
  backoffice (pantalla E6), formatea fechas en Python y solo consulta en `fotos_del_caso` (1 consulta por FK).
- **DAT**: sin hallazgos. Los `UUIDField` del alcance tienen su migración a `char(36)`
  (`0119_emergencia_casos.py:31`, `0121_emergencia_kits.py:30`); los índices `Derivacion (dispositivo, estado)`
  y `EntregaKit (dispositivo, estado)` cubren las lecturas de la API; `CasoEmergencia` no necesita
  `(relevado_por, origen, creado)` a este volumen.

## 6. Línea de base

Medida por lectura; `perf_audit.py` y `bench_mysql.py` no corrieron porque el banco no siembra Emergencia (sección 8.c).

- **Regla de 1.000 líneas:** ningún archivo del alcance la pasa. Pasan de 700 o se acercan: `services/emergencia.py` (769), `api/serializers_emergencia.py` (755), `views/emergencia_dispositivo.py` (726), `selectors/emergencia.py` (668), `selectors/emergencia_tablero.py` (677), `selectors/emergencia_mesa.py` (656), `forms_emergencia.py` (631), `views/emergencia_kits.py` (626). El mayor de la etapa 3 es `services/emergencia_confirmacion.py` (557); `services/estadias.py` (1.041) es contexto, fuera del alcance.
- **Presupuestos de consultas:** los fija `programas/tests/test_emergencia_mesa.py:1260-1302` con `assertNumQueries` sobre SQLite (bandeja con 500 casos abiertos, panel con 50 dispositivos) y los tests de la API (`test_emergencia_api_m1.py:513-530`, `test_emergencia_api_kits.py:344-422`, `test_emergencia_api_m2.py:240-289`, `test_emergencia_api_contrato.py:683-698`). Dicen cuántas consultas hay, no cuánto tarda cada una en MariaDB: **ninguna ruta de Emergencia está en `scripts/perf_budgets.json` ni en `scripts/perf_mysql/bench_mysql.py`** (E-PERF-13).
- **Sin N+1 en la bandeja, la ficha, el tablero, la pantalla del dispositivo ni la API** (los tres revisores de performance lo confirmaron leyendo; los serializers y los templates no tocan relaciones fuera de lo cargado).
- **Sin `Trunc*`, `__date` ni `CONVERT_TZ`** en ninguna de las cuatro tajadas: el día operativo y el semáforo se calculan en Python.
- **Volumen supuesto por los revisores** (el banco no lo tiene): 200 dispositivos, 10.000 plazas, 10.000 casos (≈ 1.000 abiertos en pico), 50.000 trazas, 15.000 derivaciones, 20.000 estadías, 30.000 reservas históricas, 40.000 integrantes; kits: ≈ 20.000 entregas con ≈ 100.000 líneas; `legajos_ciudadano` de 50.000 a 500.000 filas.

## 7. Decisiones del cliente

Cada una lleva una propuesta por defecto aplicable: si no hay respuesta a tiempo, se implementa el default.

| Ficha | Decisión | Default propuesto |
|---|---|---|
| E-ERR-01 | Qué pasa cuando el DNI del integrante coincide con un legajo pero nombre o apellido no. **Aplicado en #1205 (Cambio 497)**; el cliente confirma o corrige. | Rechazar con `ValidationError({"dni": …})`, con el mismo criterio de comparación que `DniRegistrado` de `emergencia_alta` (Cambio 486). Lo que la ficha no trae se sigue completando del legajo (contrato §13.8). |
| E-ERR-04 | Con la cubeta de consultas de personas agotada, ¿se ofrece igual la casilla «el DNI es correcto y es otra persona»? | Sí, sin el nombre de la persona registrada. Si el PM decide que sin cupo no se permite el alta marcada, la ficha pasa a REFUTADA. |
| E-ERR-03 | Frecuencia de los vencimientos de Emergencia y qué corre en el arranque del contenedor. **Ya es un pendiente del PM** en `requerimientos.md`. | CronJob propio cada 5 min con `--solo emergencia.derivacion` y otro con `--solo emergencia.caso_sin_avance`; excluir `emergencia.caso_sin_avance` del bootstrap. |
| E-ERR-07 | Cómo se evita el doble envío de «Crear entrega». | Deduplicar por envío con un `UUIDField` oculto y `cache.add` (sin migración); el reenvío redirige al detalle ya creado. |
| E-ERR-08 | El reintento de confirmar o agregar sobre un caso que ya cambió de estado. | Honrar el contrato: resolver primero la rama idempotente (200) y recién después exigir `INGRESO_EN_CURSO`. |
| E-ERR-15 | Hora de salida de una entrega anterior al armado. | Rechazarla: «La hora de salida no puede ser anterior al armado de la entrega.» |
| E-ERR-17 | Un ingreso en curso que nadie cierra retiene las camas sin plazo. | Mantener el comportamiento y corregir el docstring (quitar «vencimiento»). Un vencimiento de ingreso en curso es otro requerimiento. |
| E-LIM-05 | A qué pantalla vuelve la guardia después de cada cambio de estado. | ALOJADO → integrantes en todos los casos. |
| E-PERF-12 | La lista de pendientes de la app deja de ser «sin tope» (cambia el contrato §10). | Tope de 50, la más vieja primero. Nada de paginar con el `PageNumberPagination` por defecto (la app no lee `results`). |
| E-PERF-14 | Tope de la traza en la ficha del caso. | Mostrar las últimas 50 y un enlace a la traza completa; primero medir la distribución real por caso. |
| E-PERF-15 | Dejar de tratar como vigente la derivación aceptada. | No tocarlo: cambia el significado de `clave_vigente`; no se propone cambio. |
| E-FE-01 | (Decisión del juez, no del cliente) renombrar `x-becas-modal` y los parciales `becas/_modal_*` a un namespace neutro. | No renombrar en esta ola. |

## 8. Pasada 2 · qué medir y qué reproducir

### 8.0 Resultado de las PoC obligatorias (ya ejecutadas por el juez)

| Ficha | Resultado | Severidad | Evidencia |
|---|---|---|---|
| E-SEG-01 | CONFIRMA | MEDIA → **ALTA** | PoC reproducida; test en el PR que la arregla: tras sacar al usuario del equipo de A, el reenvío del mismo `uuid_cliente` a la URL de B responde 200 con los integrantes del caso de A (persona `Lopez, Ana`, DNI `<DNI de prueba 1>`, plaza), confirmados después de la baja. `avisar_a_la_mesa` repite el patrón con `CasoResumen`. No es CRÍTICA: exige el mismo usuario creador y acceso a otro dispositivo. |
| E-ERR-01 | CONFIRMA | MEDIA → **ALTA** | PoC reproducida; test en el PR que la arregla: `Ciudadano` «Persona Real» DNI <DNI de prueba 2>; confirmar a «Juan Benitez» con ese DNI vincula la fila a Persona Real, le abre la `Estadia`, crea el `VinculoFamiliar` y `_completar_legajo` escribe `genero='M'` y `fecha_nacimiento=2006-03-10` en el legajo ajeno. |

### 8.a Fichas PERF/DAT a medir en el banco

> **Estado: pendiente de medición.** Las mediciones del banco (siembra en `scripts/perf_mysql/` y rutas de `bench_mysql.py`) llegan en otro PR (`perf/banco-emergencia-dispositivos`). Hasta entonces esta sección es el plan de medición: ninguna ficha PERF cambia de severidad por número y este informe no trae ninguno.

MariaDB 10.11, `read_timeout` 10 s. Sin número, una PERF ALTA baja a INFO; las MEDIA quedan PLAUSIBLE hasta tener el número. Ninguna PERF de Emergencia es ALTA hoy, pero **dos suben a ALTA si la medición pasa el umbral**: E-PERF-02 (candado del numerador > 200 ms por alta) y E-PERF-01 (si en el padrón real el REGEXP pasa de ~0,5 s por recorrido bajo candado).

| Ficha | Sev. | Qué se mide (medición propuesta por el auditor) |
|---|---|---|
| E-PERF-01 · El alta de un responsable nuevo recorre toda la tabla de ciudadanos c… | MEDIA | banco MySQL (ya siembra `Ciudadano`, `scripts/perf_mysql/escalar_bench.py:162-172`): `EXPLAIN ANALYZE SELECT id, dni FROM legajos_ciudadano WHERE NOT (dni = '99999999') AND dni REGEXP '[^0-9]';` → esperado `type=ALL`, `rows≈N`. Ruta: `POST /emergencia/casos/nuevo/` con DNI inexistente (agregar a `_extra_targets()` de `bench_mysql.py` como `emergencia_caso_nuevo_dni_nuevo`, actor con rol de mesa). |
| E-PERF-02 · El candado del numerador de casos queda tomado hasta el commit, con f… | MEDIA | banco MySQL/MariaDB con dos conexiones: una corre `crear_caso` con dos fotos de 5 MB y se pausa después de numerar; medir cuánto espera la segunda. Durante 50 `POST /api/emergencia/casos/` concurrentes (script con `concurrent.futures` y `django.test.Client` con token de agente), leer `information_schema.INNODB_TRX` y `performance_schema.data_lock_waits` (MySQL) / `information_schema.INNODB_LOCK_WAITS` (MariaDB). Candado medido > 200 ms por alta ⇒ subir a ALTA. |
| E-PERF-03 · El tablero recorre todo el histórico de casos en cada carga para qued… | MEDIA | sembrar en `chaco_perf_ci` 10.000 y 100.000 `CasoEmergencia` (90 % `CERRADO` con `cerrado_en` en los últimos 6 meses, 1.000 abiertos repartidos en los estados, 5 `TrazaCaso` por caso, 0-2 `ContactoCaso`); `EXPLAIN` del SQL de `_casos_de_la_ventana` (imprimir `qs.query` armado igual que en la función) y mirar `type`/`rows` de `programas_casoemergencia` y las `DEPENDENT SUBQUERY`; después `scripts/perf_mysql/perfil_ruta.py` sobre `/emergencia/tablero/` con un supervisor (o agregar ese target a `bench_mysql.py`). Pas… |
| E-PERF-04 · La página de la bandeja ordena por expresiones y ordena el historial… | MEDIA | banco con la siembra de abajo. `EXPLAIN ANALYZE` de la SQL de `selectores.bandeja({"solapa": "cerrados"}, sla=sla, ahora=now, semaforos=s)[0:50]`, de la misma con `[4500:4550]` y con `{"texto": "gonz"}`. Señal: `Using temporary`, `rows` ≈ total de la solapa, o `DEPENDENT SUBQUERY` con `loops` ≫ 50. Rutas para `bench_mysql.py`: `emergencia:bandeja` con `?solapa=cerrados`, `?solapa=cerrados&page=90` y `?texto=gonz`. > 1 s ⇒ ALTA. |
| E-PERF-05 · E4 (listado de entregas) ordena y pagina todo el histórico sin índice… | MEDIA | sembrar 20.000 y 200.000 `EntregaKit` sobre 200 dispositivos (70 % `RECIBIDA`, 10 % `RECIBIDA_CON_DIFERENCIAS`, el resto abiertas/canceladas) con 5 líneas cada una; `EXPLAIN` de `str(listado_de_entregas({"solapa": "recibidas"})[:50].query)` (buscar `Using temporary; Using filesort` y `rows` cerca del total); `perfil_ruta.py` sobre `/emergencia/entregas/?solapa=recibidas` y `?solapa=recibidas&page=300`. |
| E-PERF-06 · El tablero trae todas las entregas en camino con todas sus líneas par… | BAJA | con 300 entregas `EN_CAMINO` sembradas, `CaptureQueriesContext` sobre `entregas_en_camino` y contar los ids del `IN`; no hace falta el banco. |
| E-PERF-07 · Derivaciones y entregas se filtran por `estado` sin un índice que emp… | BAJA | con la siembra de E-PERF-03/02, `EXPLAIN` de `Derivacion.objects.filter(estado="PENDIENTE").order_by("vence_en", "id")` y de `EntregaKit.objects.filter(Q(estado="EN_CAMINO") / q_entrega_sin_revisar())`: antes `type=ALL`, después `ref`/`range` sobre el índice nuevo. |
| E-PERF-08 · Tres consultas fijas de la bandeja recorren todos los casos en cada c… | BAJA | `EXPLAIN` en el banco: el agregado con `key=…estado_origen…` y `Extra: Using index`; las localidades sin `Using temporary`. |
| E-PERF-09 · Dos aceptaciones simultáneas en el mismo dispositivo eligen las misma… | BAJA | dos sesiones en el banco MariaDB: sembrar 1 dispositivo con 20 camas y 2 derivaciones PENDIENTE; S1 `BEGIN; SELECT id FROM programas_plaza WHERE id IN (<las 4 primeras de camas_libres>) ORDER BY id FOR UPDATE;` más un `INSERT` de reserva sobre la primera, sin commit; en paralelo, desde `manage.py shell`, `aceptar_derivacion(derivacion=B, usuario=...)` midiendo espera y resultado; `COMMIT` en S1: hoy debe dar `CAMAS_TOMADAS_MIENTRAS_ACEPTABA`, con el reintento, éxito con las camas siguientes. |
| E-PERF-10 · Reservar las camas de la familia valida cada cama con dos consultas p… | BAJA | entrada nueva en `scripts/perf_budgets.json` («emergencia_reservar_plazas_de_derivacion», lecturas fijas) y `assertNumQueries` con 1 y con 12 camas. |
| E-PERF-11 · «Familia en la puerta» busca en todos los casos no cerrados en vez de… | BAJA | `CaptureQueriesContext`; en el banco, `EXPLAIN` antes y después con 10.000 casos sembrados. |
| E-PERF-12 · La lista de entregas pendientes de un dispositivo no tiene tope | BAJA | sembrar 1 dispositivo con 500 `EntregaKit` `EN_CAMINO` de 8 líneas y medir `GET reverse("emergencia_api:dispositivo-entregas", args=[disp.pk]) + "?pendientes=1"` en `scripts/perf_mysql/bench_mysql.py` (actor: guardia con `emergencia.recibir_kit` en el Equipo); mirar el tamaño del JSON y el `EXPLAIN` del `SELECT` de `programas_entregakit` (`key` = el índice `(dispositivo, estado)`, `Using filesort` solo sobre esas filas). |
| E-PERF-13 · Ninguna ruta de Emergencia está en los presupuestos ni en el banco My… | INFO | — |
| E-PERF-14 · La ficha trae la traza completa, sin tope | INFO | en testing (lectura): `SELECT caso_id, COUNT(*) c FROM programas_trazacaso GROUP BY caso_id ORDER BY c DESC LIMIT 10;` |
| E-PERF-15 · La derivación aceptada nunca deja de ser ACEPTADA y las lecturas de l… | INFO | sembrar 1 dispositivo con 1.000 casos `ALOJADO`/`CERRADO` (derivación `ACEPTADA`, 4 integrantes con ciudadano) y 3 en `INGRESO_EN_CURSO`; `EXPLAIN` del SQL de las dos consultas (`str(qs.query)`): mirar `rows` sobre `programas_derivacion` y `Using temporary`; rutas al banco: `GET reverse("emergencia_api:dispositivo-buscar", args=[disp.pk]) + "?dni=<responsable de un caso alojado>"` y la pantalla E6 de llegadas (`programas/views/emergencia_dispositivo.py:173`). |
| E-DAT-01 · Las subconsultas «última traza» y «última rechazada» no tienen índice… | INFO | `EXPLAIN` de la consulta de página de E-PERF-04 con ≥ 50.000 trazas: las `DEPENDENT SUBQUERY` sobre `programas_trazacaso` sin `Using filesort`, y la de `programas_derivacion` por `clave_vigente` con `key=derivacion_clave_vigente_unica`, `rows=1`. |

### 8.b Fichas ERR/SEG que necesitan PoC

Obligatorias (ALTA de corrección o seguridad): ambas **ya ejecutadas, CONFIRMADAS y resueltas** (8.0; #1204 y #1205).

- **E-SEG-01** [ALTA · CONFIRMADO con test] El reenvío de «Ingresar igual» devuelve los integrantes de un caso ajeno al dispositivo de la URL
- **E-ERR-01** [ALTA · CONFIRMADO con test] Confirmar con el DNI de un legajo existente no valida la identidad: aloja y escribe en el legajo de otra persona

Recomendadas (ERR con estado PLAUSIBLE, o con daño de datos si se confirma):

- **E-ERR-04** [BAJA · PLAUSIBLE] Con la cubeta de identidad agotada, la mesa no puede cargar un caso «con identidad a revisar»
- **E-ERR-05** [BAJA · PLAUSIBLE] «Nuevo caso» de la mesa no es idempotente: un reenvío del POST crea un segundo caso con otro número
- **E-ERR-06** [BAJA · PLAUSIBLE] Ingreso directo y «Agregar persona» desde el backoffice no tienen idempotencia del lado del servidor
- **E-ERR-07** [BAJA · PLAUSIBLE] «Crear entrega» no es idempotente: un reenvío del paso 3 arma una segunda entrega (o una segunda reposición de la misma)
- **E-ERR-08** [BAJA · PLAUSIBLE] El reintento idempotente de confirmar o agregar devuelve 409 si el caso ya cambió de estado
- **E-ERR-10** [BAJA · PLAUSIBLE] La cola reintenta para siempre un ingreso directo que ya se creó si el usuario perdió el dispositivo
- **E-ERR-16** [BAJA · PLAUSIBLE] «Casos por localidad» del tablero fusiona localidades homónimas de municipios distintos y su enlace filtra solo una

Las ERR/SEG ya CONFIRMADAS por lectura llevan su test de regresión en la propia ficha («Tests a agregar», con mutación).

### 8.c Qué le falta sembrar al banco (`scripts/perf_mysql/`)

Hoy el banco no crea ni mide nada de Emergencia (`seed_emergencia` solo crea el programa y el SLA). **No** tocar `seed_perf` (lo usa el CI de performance): todo va en un único `scripts/perf_mysql/escenarios_emergencia.py` (contradicción 3), con volumen de la tabla de abajo. Las rutas de escritura son de un solo uso por base sembrada: iterar con `mysqldump` + restore, como la sonda de perf del CI efímero.

| Siembra | Qué crear | Fichas |
|---|---|---|
| Programas, usuarios y alcance | Programas EMERGENCIA y DISPOSITIVOS (`seed_datos_base`) + `SLAEmergencia`; 20 usuarios de la mesa (`emergencia.operar`) y 2 supervisores (uno es el actor `backoffice` de las rutas); un usuario de guardia con `dispositivo.admitir` y `emergencia.recibir_kit` en el Equipo de los dispositivos de prueba, con token de DRF; un administrador del programa Dispositivos (alcance total, para `mis-dispositivos`). | E-PERF-03, E-PERF-05, E-PERF-12, E-PERF-13 |
| Dispositivos y plazas | 200 dispositivos activos de un tipo que admita `CAMA`, 2 a 4 sectores (600 en total), 10.000 plazas cama; un centro grande de 300 camas en 6 sectores (el de las mediciones), 30 % con `Estadia` abierta. | E-PERF-09, E-PERF-10, E-PERF-15 |
| Casos y grupos | 10.000 `CasoEmergencia` (9.000 `CERRADO`/`ALOJADO`, 1.000 abiertos en `NUEVO`/`EN_GESTION`/`DERIVADO`/`INGRESO_EN_CURSO`, ≈ 30 % fuera de SLA, 5 % `origen=DISPOSITIVO`, 50 alojados en las últimas 24 h, ≈ 2 % con «en la puerta» en `situacion`) con `GrupoFamiliar` de 4 (40.000 `IntegranteGrupo`, la mitad con ciudadano, ≈ 10 % de responsables repetidos); variante de 100.000 casos para el tablero y la bandeja. 0-2 `ContactoCaso` (5.000) y 2.000 `AdjuntoCaso`. | E-PERF-03, E-PERF-04, E-PERF-08, E-PERF-11 |
| Trazas | 5 `TrazaCaso` por caso (50.000; 500.000 en la variante grande) y 20 casos alojados con 100 trazas cada uno. | E-DAT-01, E-PERF-03, E-PERF-04, E-PERF-14 |
| Derivaciones | 15.000 `Derivacion` (1 `ACEPTADA` por alojado, 1 `PENDIENTE` por `DERIVADO`, 200 `PENDIENTE` en total, el resto `RECHAZADA`/`VENCIDA`/`CANCELADA`); en el centro grande, 1.000 casos `ALOJADO`/`CERRADO` con derivación `ACEPTADA`, 10 `DERIVADO` con `PENDIENTE` y 3 en `INGRESO_EN_CURSO`. | E-PERF-07, E-PERF-09, E-PERF-15 |
| Histórico de Dispositivos | 20.000 `Estadia` (≈ 18.000 `EGRESADA` y 2.000 `ACTIVA`, el centro grande al 60 %) y ≈ 30.000 `ReservaPlaza` (mayoría `CONSUMIDA`/`LIBERADA`, ≈ 200 `VIGENTE` con `hasta` vencido sin liberar). | E-ERR-17, E-PERF-10 |
| Ciudadanos | Llevar `legajos_ciudadano` a 500.000 filas (DNI `10000000+i`) con 0,5 % a 1 % guardados con puntos tipo `12.345.678`; medir también con las 20.000 del banco, para tener las dos puntas. | E-PERF-01 |
| Kits | 50 `TipoKit` y un catálogo de 10 ítems; 20.000 `EntregaKit` (200.000 en la variante grande; 70 % `RECIBIDA`, 10 % con diferencias, 300 `EN_CAMINO`) con 5 `LineaEntrega` y 3 `TrazaEntrega` cada una; en el dispositivo grande, 500 `EN_CAMINO` de 8 líneas y 2.000 `RECIBIDA`. | E-PERF-05, E-PERF-06, E-PERF-07, E-PERF-12 |
| Concurrencia y fotos | 30 a 60 `POST /api/emergencia/casos/` concurrentes con dos fotos de 5 MB (`concurrent.futures` y `Client` con token de agente); lectura de `information_schema.INNODB_TRX` e `INNODB_LOCK_WAITS` durante la corrida; dos sesiones sobre el mismo caso para medir la espera de `confirmar_integrante` con REGEXP bajo candado. | E-PERF-01, E-PERF-02 |

Rutas a sumar a `_extra_targets()` de `bench_mysql.py` y a `scripts/perf_budgets.json`:

- `/emergencia/casos/` (bandeja, por solapa y página 2), `/emergencia/casos/<pk>/` (ficha), `emergencia_ficha` (panel «Derivar»), `POST /emergencia/casos/nuevo/` con DNI inexistente (actor con rol de mesa).
- `/emergencia/tablero/` (supervisor), `/emergencia/entregas/?solapa=recibidas`, `…&page=300` y `/emergencia/entregas/nueva/`.
- API como la guardia, por token: `emergencia_api:dispositivo-buscar` (con `?dni=` inexistente y con el de un alojado), `emergencia_api:dispositivo-plazas` (con `?caso=` de uno en `INGRESO_EN_CURSO`), `emergencia_api:mis-dispositivos`, `emergencia_api:dispositivo-entregas` con y sin `?pendientes=1`, `emergencia_api:entrega-detail` de una entrega con 8 líneas, `emergencia_api:caso-list`.
- POST de un solo uso (base restaurable): `emergencia_api:derivacion-aceptar` y `emergencia_api:caso-integrante-confirmar` con un DNI nuevo.

## 9. Fichas

Ordenadas por severidad y eje. Los IDs son los finales `E-<EJE>-NN`; el ID de la pasada 1 figura en cada ficha.

### E-SEG-01 · El reenvío de «Ingresar igual» devuelve los integrantes de un caso ajeno al dispositivo de la URL
**Severidad:** ALTA · **Estado:** RESUELTO (#1204, Cambio 496); CONFIRMADO con test (PoC reproducida; test en el PR que la arregla) · **Eje:** SEG · **Origen:** nuevo · **Ola:** 0 · **Esfuerzo:** S-M
- **Resuelto:** PR #1204 (merge `e224b9a8`, Cambio 496), 19-nov-2026, aprobado en `cbf75b98`. Seguimiento que dejó la auditoría de ese PR: sección 10.
- **ID de la pasada 1:** E4-SEG-01
- **Verificación de la pasada 2 (PoC, el juez):** CONFIRMADO con test, PoC reproducida; test en el PR que la arregla. Tras borrar su `MiembroEquipoDispositivo` de A, el reenvío del mismo `uuid_cliente` a la URL de B da **200** con los integrantes del caso de A, incluida la persona `{nombre: "Lopez, Ana", dni: "<DNI de prueba 1>"}` y su plaza, confirmados **después** de la baja (seguimiento en vivo). `avisar_a_la_mesa` repite el patrón (solo `CasoResumen`). Causas: `services/emergencia_sin_derivacion.py:94-99` (idempotencia antes del chequeo de dispositivo), `services/emergencia_alta.py:359-370` (`_caso_de_ese_envio` solo compara `relevado_por`) y `api/views_emergencia_sin_derivacion.py:~258` (`_filas` sin acotar).
- **Severidad (decisión del juez):** sube de MEDIA a **ALTA** porque la PoC confirma la fuga de datos personales. No es CRÍTICA: exige el mismo usuario creador y acceso a otro dispositivo; viola RU-9 del contrato.
- **Ubicación:** `programas/api/views_emergencia_sin_derivacion.py:244-266` (`IngresoDirectoView.post`, la
  relectura `_filas(caso.pk)` en :259), con la causa en `programas/services/emergencia_sin_derivacion.py:94-99`
  (`ingreso_directo`: idempotencia antes de cualquier relación caso↔dispositivo) y
  `programas/services/emergencia_alta.py:359-370` (`_caso_de_ese_envio`: solo mira `relevado_por`). Mismo
  patrón, con menos datos (solo `CasoResumen`), en `AvisarALaMesaView.post` (`:295-311`).
- **Escenario:** el usuario U fue guardia del dispositivo A e hizo un ingreso directo con `uuid_cliente = X`
  (o es agente territorial y además admite en algún lado, y X es el de un envío de M1). Después lo sacan del
  Equipo de A y queda admitiendo en B. `POST /api/emergencia/dispositivos/{B}/ingreso-directo/` con
  `uuid_cliente=X` y cualquier cuerpo que pase la forma del serializer → `_dispositivo(B)` pasa (admite en B) →
  `_exigir_alcance(U, B)` pasa → `_caso_de_ese_envio(X, U)` encuentra el caso de A (lo creó U) y lo devuelve con
  `ya_existia` → la vista responde **200** con `integrantes_de(caso)`: nombre, DNI, parentesco, cama de hoy,
  `confirmada_en`/`egresado_en` de cada persona, incluidas las que la guardia de A confirmó o agregó **después**
  de que U perdió el acceso. Repetible en el tiempo: es un seguimiento en vivo de un caso que el contrato
  (§2, RU-9) dice que tiene que ser 404 para quien no opera su dispositivo. Con un X de M1 (origen `TERRITORIO`)
  devuelve además, como si fuera un ingreso directo de B, un caso que la mesa derivó a cualquier lado.
- **Causa raíz:** la idempotencia se resuelve por «mismo usuario + mismo uuid» y corre **antes** de exigir que
  el caso encontrado sea un ingreso directo hacia **este** dispositivo; la vista confía en que el servicio ya
  acotó y relee el caso con `integrantes_de`, que por diseño «no exige capacidad: la vista lo exigió»
  (`selectors/emergencia_alojar.py:337-338`). Acá la vista no lo exigió.
- **Solución:** sin tocar el camino feliz ni la forma de la respuesta.
  1. En `ingreso_directo`, cuando `_caso_de_ese_envio` devuelve un caso: si `existente.origen != DISPOSITIVO`
     o su primera derivación (`_con_sus_reservas` ya la lee, `:64`) no es hacia `dispositivo`, levantar
     `UuidEnUso()` → 409 `UUID_EN_USO` («no es un reenvío de este envío»), que es lo que el contrato ya publica.
     Lo mismo en `avisar_a_la_mesa` comparando `situacion["en_la_puerta_de"]["dispositivo_id"]`.
  2. En `IngresoDirectoView.post`, solo para `caso.ya_existia`: armar `integrantes` únicamente si
     `servicio_alojar.ingreso_sin_candado(caso.pk, request.user)` pasa (alcance vigente sobre la última
     derivación); si levanta `PermissionDenied`, responder 200 con `caso`, `reservadas`, `faltantes` e
     `integrantes: []`. La cola de la app sigue recibiendo su 200 y no ve personas de un dispositivo ajeno.
- **Lo que NO hay que hacer:** no mover el chequeo de idempotencia después de `dispositivo_elegible`/`camas_libres`
  (rompe el reenvío «aunque ya no haya camas», que tiene test); no devolver 404 en el reenvío legítimo de un
  usuario que todavía opera el dispositivo (la cola quedaría trabada).
- **Tests a agregar:** `programas/tests/test_emergencia_api_m2.py::IngresoDirectoApiTest.test_reenvio_con_uuid_de_otro_dispositivo_no_devuelve_integrantes`,
  `::test_reenvio_con_uuid_de_un_envio_de_m1_es_uuid_en_uso`,
  `::test_reenvio_tras_perder_el_equipo_no_muestra_personas`,
  `programas/tests/test_emergencia_sin_derivacion.py::…::test_avisar_a_la_mesa_con_uuid_de_otro_dispositivo_es_uuid_en_uso`.
  Verificar por mutación: quitar la guarda y ver los tests en rojo.
- **Verificación:** los tests anteriores; `test_reenviar_el_mismo_envio_devuelve_el_mismo_caso_aunque_ya_no_haya_camas`
  sigue verde.
- **Regla para no repetirlo:** **skill** · `.claude/skills/seguridad-django/SKILL.md` (sección API de campo) ·
  «La idempotencia por `uuid_cliente` es un atajo de **lectura**: el objeto que devuelve el reenvío tiene que
  pasar la misma guarda de alcance que un GET de ese objeto (dispositivo de la URL, alcance vigente). Si la
  respuesta del reenvío trae datos de personas, la vista no puede apoyarse en que "el servicio ya acotó".»
  Y en `.claude/skills/auditoria/rubricas/` (seguridad): «Por cada `ya_existia`/`ya_estaba`, ¿qué alcance se
  exigió sobre el objeto **encontrado**, no sobre el de la URL?».

---

### E-ERR-01 · Confirmar con el DNI de un legajo existente no valida la identidad: aloja y escribe en el legajo de otra persona
**Severidad:** ALTA · **Estado:** RESUELTO (#1205, Cambio 497); CONFIRMADO con test (PoC reproducida; test en el PR que la arregla) · **Eje:** ERR · **Origen:** nuevo · **Ola:** 0 · **Esfuerzo:** S-M
- **Resuelto:** PR #1205 (merge `128a0cb3`, Cambio 497), 19-nov-2026, aprobado en `4b52bccc` y re-sellado en `b5b846f7`. Se rechaza con el criterio de `DniRegistrado` (`nombre_en_conflicto`, hecha pública), con una **excepción a revisar**: el responsable del grupo con identidad a revisar (Cambio 486) se confirma con lo que declaró el alta. Seguimiento: sección 10.
- **ID de la pasada 1:** E2-ERR-01
- **Verificación de la pasada 2 (PoC, el juez):** CONFIRMADO con test, PoC reproducida; test en el PR que la arregla. `Ciudadano` «Persona Real» con DNI <DNI de prueba 2>; confirmar al integrante «Juan Benitez» con ese DNI vincula `fila.ciudadano` a Persona Real, le abre la `Estadia`, crea el `VinculoFamiliar` y `_completar_legajo` escribe `genero="M"` y `fecha_nacimiento=2006-03-10` en el legajo ajeno (nombre y apellido no se pisan). Solución sugerida por el juez: control equivalente a `DniRegistrado` (Cambio 486 de Becas) antes de vincular.
- **Severidad (decisión del juez):** sube de MEDIA a **ALTA**: la PoC confirma que se aloja y se escribe en el legajo de otra persona.
- **Ubicación:** `programas/services/emergencia_confirmacion.py:383-384` (busca por DNI y completa la ficha con el legajo), `:407` (usa ese legajo sin más), `:428-430` (vínculo y `_completar_legajo`), `:106-125` (`_con_lo_del_legajo`), `:155-174` (`_completar_legajo`).
- **Escenario:** la guardia tipea mal un dígito del DNI del hijo («<DNI de prueba 2>» en vez de «<DNI de prueba 3>») y carga nombre «Juan Benítez». Ese DNI es el legajo de «Pedro Gómez». `confirmar_integrante` toma a Pedro Gómez sin comparar nombre/apellido: le abre una `Estadia` en la cama, crea `VinculoFamiliar` responsable→Pedro (`HIJO`, conviviente), y si el legajo de Pedro tenía vacíos sexo, nacimiento o teléfono, los llena con los de Juan. La ficha guardada dice «Juan Benítez» y la fila apunta a Pedro. Consecuencias: Pedro figura alojado en la red (cualquier ingreso real suyo en otro dispositivo da `AlojamientoEnLaRed`), Juan no existe en el sistema, y nada avisa.
- **Causa raíz:** la etapa 1 resolvió esto para el responsable (`emergencia_alta.crear_caso`: `DniRegistrado` si nombre/apellido no coinciden, o `identidad_en_conflicto` que marca el caso, Cambio 486); la confirmación de la etapa 3 resuelve la persona **solo por DNI** (`buscar_ciudadano_por_dni`) y trata los datos tipeados como relleno, nunca como control.
- **Solución:** `DECISIÓN CLIENTE: rechazar con ValidationError({"dni": …}) cuando la ficha trae nombre o apellido y no coinciden (normalizados) con el legajo encontrado, con el mismo criterio de comparación que usa crear_caso para DniRegistrado`. Implementación: en `confirmar_integrante`, después de `existente = buscar_ciudadano_por_dni(dni)` y **antes** de `_con_lo_del_legajo`, si `existente` y la ficha original trae `nombre`/`apellido`, comparar con la función de comparación de `emergencia_alta` (reutilizarla, no escribir otra). Lo que la ficha no trae sigue completándose del legajo como hoy (el contrato §13.8 dice «si la persona ya está en el legajo, alcanza con el DNI»).
- **Lo que NO hay que hacer:** pisar el legajo con los datos tipeados, ni dar de alta un segundo `Ciudadano` con el mismo DNI (`Ciudadano.dni` es único).
- **Tests a agregar:** `programas/tests/test_emergencia_alojar.py::ConfirmarIntegranteTests.test_dni_de_otro_legajo_con_otro_nombre_no_confirma`; `…::test_dni_existente_sin_nombre_completa_del_legajo` (regresión del camino actual).
- **Verificación:** el primer test rojo en el SHA auditado y verde con el arreglo; mutación: quitar la comparación y verlo rojo.
- **Regla para no repetirlo:** **skill** · `.claude/skills/seguridad-django/SKILL.md` (sección datos personales) · «Toda resolución de persona por DNI que **escribe** sobre el legajo o le abre una estadía compara nombre y apellido declarados con el legajo encontrado (patrón `DniRegistrado` de `emergencia_alta`); el DNI solo identifica, no autoriza a escribir.»

---

### E-LIM-01 · Las vistas de la guardia y de kits reescriben reglas de dominio que ya tiene el servicio
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — (relacionado con E-LIM-07 y E-LIM-32, mismo patrón en la mesa) · **Ola:** 4 · **Esfuerzo:** M
- **ID de la pasada 1:** E3-LIM-01
- **Ubicación:**
  - `programas/views/emergencia_kits.py:273-282` `_PasoConDestino._original`: «se repone una entrega del mismo
    dispositivo y `RECIBIDA_CON_DIFERENCIAS`». Es la misma regla que `programas/services/kits.py:280-292`
    `_validar_reposicion`, escrita otra vez con el ORM.
  - `programas/views/emergencia_dispositivo.py:136-150` `_derivacion_pedida`: define «derivación vigente para
    recibir» (`ESTADOS_VIGENTES` y caso en `DERIVADO`/`INGRESO_EN_CURSO`) dentro de la vista.
  - `programas/views/emergencia_dispositivo.py:261-273` `_IngresoView.preparar`: «el caso del ingreso es la
    última derivación hacia este dispositivo, `ACEPTADA`», con `order_by("-id")` escrito a mano.
  - `programas/views/emergencia_dispositivo.py:313` y `:544`: `max(total_declarado, len(integrantes))` es el
    «total efectivo» que alimenta `acciones_del_ingreso`. Está copiado en dos vistas y no vive en el selector
    que arma esos datos.
  - `programas/views/emergencia_dispositivo.py:429-443` (`_iniciales`: la persona 1 se precarga con el
    responsable) y `:553-556` (el sector se preselecciona con el `Counter` de las camas): son defaults del
    dominio, no orquestación HTTP.
- **Escenario:** si cambia la regla de reposición (por ejemplo, permitir reponer una entrega `RECIBIDA` con
  observación), hay que tocar el servicio **y** la vista. Si se toca solo el servicio, el paso 2 deja de
  precargar faltantes en silencio (`_original` devuelve `None`), y nadie ve un error. Lo mismo pasa con «total
  efectivo»: si una de las dos vistas cambia, «Familia alojada» se habilita en la lista de integrantes y la
  pantalla de alojar la rechaza, o al revés.
- **Causa raíz:** el docstring de los dos archivos promete «las vistas no tienen reglas» (`emergencia_kits.py:4`,
  `emergencia_dispositivo.py:7`), pero las búsquedas filtradas por estado se resolvieron en la vista porque no
  había un selector con ese nombre. Contradice el «Patrón de capas» de `CLAUDE.md` (views = orquestación, sin
  lógica de dominio).
- **Solución (preserva lógica):**
  - `selectors/kits.py`: `entrega_a_reponer(pk, dispositivo)` devuelve la entrega o `None` con el mismo filtro.
    `services/kits._validar_reposicion` pasa a usar ese predicado (`EntregaKit.q_reponible(dispositivo)` en el
    modelo) para que haya una sola definición.
  - `selectors/emergencia_alojar.py`: `derivacion_para_recibir(dispositivo, pk)` y
    `ultima_derivacion_hacia(dispositivo, caso_pk)` con los mismos `select_related`.
  - `selectores.integrantes_de(caso)` agrega `"total_efectivo"`. Las dos vistas leen esa clave. Mejor todavía:
    `servicio.acciones_del_ingreso(caso, datos)` calcula el total adentro.
  - `_iniciales` y la preselección de sector pasan a `selectors/emergencia_llegadas.py` (`iniciales_de_ficha`,
    `sector_sugerido`). Ese módulo ya es la «pantalla» de la guardia.
- **Lo que NO hay que hacer:** mover las consultas al servicio de escritura. Son lecturas y van a `selectors/`.
  Tampoco hay que perder el filtro por `self.dispositivo`: es la guarda de RU-9/C2 (otro dispositivo ⇒ 404).
- **Tests a agregar:** `programas/tests/test_emergencia_kits.py::ReposicionTest.test_vista_y_servicio_comparten_regla`
  (mutación: cambiar el estado en `q_reponible` pone en rojo la vista y el servicio a la vez).
  `programas/tests/test_emergencia_dispositivo_web.py::TotalEfectivoTest.test_integrantes_y_alojar_coinciden`
  (más integrantes agregados que declarados).
- **Verificación:** `grep -n "objects\." programas/views/emergencia_dispositivo.py programas/views/emergencia_kits.py`
  solo muestra `get_object_or_404` sobre selectores. Los tests de RU-9 siguen en verde.
- **Regla para no repetirlo:** **control mecánico** · test ratchet en `programas/tests/test_capas.py`: recorre
  con AST `programas/views/emergencia*.py` y falla si aparece `<Modelo>.objects.filter(` con `estado` o
  `estado__in` en los kwargs. Mensaje: «Filtro por estado en una vista: va en selectors/ o en un Q del modelo».

---

### E-ERR-02 · Cerrar con diferencia, cancelar el ingreso y «Familia alojada» desde la web no mandan `derivacion_vista`: una pestaña vieja actúa sobre un ingreso nuevo
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** Cambio 477 (la guarda existe, solo la usa la API) · **Ola:** 1 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E3-ERR-01
- **Ubicación:** `programas/views/emergencia_dispositivo.py:585` (`alojar_familia`), `:614` (`cerrar_con_diferencia`), `:638` (`cancelar_ingreso`), todas sin `derivacion_vista`; `:261-268` (`_IngresoView.preparar` resuelve la **última** derivación del caso hacia el dispositivo en cada request); templates `programas/templates/programas/emergencia/dispositivo/integrantes.html:131` y `:150`, `alojar.html:29` (ningún oculto con la derivación mostrada). La guarda está en `programas/services/emergencia_ingreso_comun.py:148-149` y la API la usa (`programas/api/serializers_emergencia.py:653-687`).
- **Escenario:** la guardia A tiene abierto «Integrantes» del caso 2026-C-000184 en dos pestañas (derivación D1, nadie confirmado). En la pestaña 1 cancela el ingreso: D1 → `RECHAZADA`, el caso vuelve a la mesa. La mesa vuelve a derivar al **mismo** dispositivo (D2) y otra guardia acepta: caso `INGRESO_EN_CURSO`, D2 `ACEPTADA`, camas reservadas. La guardia A, en la pestaña 2 (o reenviando el POST del modal), confirma «Cancelar ingreso»: `preparar` encuentra D2 `ACEPTADA` y el caso en curso, la vista llama a `cancelar_ingreso` sin `derivacion_vista`, `_abrir_ingreso` no compara nada y **cancela el ingreso nuevo con el motivo viejo**, libera las reservas de D2 y devuelve el caso a la mesa. Lo mismo con «Cerrar con diferencia» (deja `ALOJADO` parcial un ingreso que la pantalla no vio) y «Familia alojada».
- **Causa raíz:** el Cambio 477 resolvió el caso del reintento con un id de «la derivación que la pantalla mostraba», pero la pantalla web no lo guarda: la vista vuelve a resolver la derivación vigente en cada POST, que es justamente lo que la guarda tiene que comparar contra algo previo.
- **Solución:** sin tocar el servicio. Agregar `derivacion_vista = forms.IntegerField(widget=forms.HiddenInput, required=False)` a `DiferenciaForm`, `CancelarIngresoForm` y `FamiliaAlojadaForm` (`programas/forms_emergencia_dispositivo.py`), con `initial=self.derivacion.pk` al armarlos en `IntegrantesView.get` (`:369-372`) y `FamiliaAlojadaView._form` (`:547-554`); renderizar el oculto en los tres formularios; en los tres POST pasar `derivacion_vista=form.cleaned_data.pop("derivacion_vista")` al servicio. El `EstadoCambio` con `MENSAJE_OTRA_DERIVACION` ya lo traduce `traducir()` / el `except EstadoCambio` de cada vista. Estética igual (oculto).
- **Lo que NO hay que hacer:** pasar `derivacion_vista=self.derivacion.pk` desde la vista: `self.derivacion` se resuelve en el mismo request y siempre coincide con la bloqueada; no protege nada.
- **Tests a agregar:** `programas/tests/test_emergencia_dispositivo_web.py::CancelarIngresoWebTest.test_pestania_vieja_no_cancela_un_ingreso_nuevo`, `…::DiferenciaWebTest.test_pestania_vieja_no_cierra_otro_ingreso`, `…::FamiliaAlojadaWebTest.test_pestania_vieja_no_aloja_otro_ingreso`.
- **Verificación:** con D1 rechazada y D2 aceptada, POST con `derivacion_vista=D1` → redirect con el aviso «otra derivación», D2 sigue `ACEPTADA` y con sus reservas. Mutación: quitar el oculto → el test se pone rojo.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/correccion-seguridad.md` · «Una guarda de servicio que compara contra "lo que la pantalla mostró" (`derivacion_vista`, `uuid_cliente`, un `version`) tiene que viajar como oculto desde **todas** las superficies que llaman al servicio: la web, no solo la API. Buscar llamadas al servicio sin ese argumento.»

---

### E-ERR-03 · Los vencimientos de Emergencia corren una vez por día: las derivaciones vencidas quedan pendientes horas y las devoluciones por inactividad caen en masa a las 03:10 y en cada arranque
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** pendiente ya registrado (`docs/internal/requerimientos.md`, «Pendientes / a definir» punto 1) y Cambio 466 (`docs/internal/emergencia-manual.md:207-210`) · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** E3-ERR-02
- **Registro previo:** ya está como pendiente del PM en `docs/internal/requerimientos.md` (sección «Pendientes / a definir», punto 1: «Frecuencia del cron — decisión del PM antes de habilitar la mesa en PRD»). Esta ficha no lo descubre: lo mide y le deja el arreglo escrito. **DECISIÓN CLIENTE** (ver sección 7).
- **Ubicación:** `docker/cron/procesar_vencimientos.cron:31` (`10 3 * * *`), `docker/k8s/cronjobs.yaml:74` (mismo comando, una vez al día), `docker-compose.prod.yml:81` (`LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS=procesar_vencimientos` en el arranque); reglas en `programas/services/vencimientos_emergencia.py:143-161`.
- **Escenario:** a las 10:00 la mesa deriva con la vigencia mínima (30 min). A las 10:30 la derivación vence (RN-2.7), pero queda `PENDIENTE` y el caso `DERIVADO` hasta las 03:10 del día siguiente: la mesa no puede volver a derivar (el caso no está `EN_GESTION`) salvo cancelando a mano, y el tablero solo lo muestra como «venció hace 16 h y sigue pendiente» (`avisos_emergencia.py:150-152`). Al revés, `emergencia.caso_sin_avance` corre solo a las 03:10 y **en cada arranque del contenedor**: un deploy a media tarde devuelve a la bandeja, de golpe, todo caso `EN_GESTION` sin traza en los últimos 60 min, aunque el operador lo esté trabajando en ese momento sin haber dejado traza.
- **Causa raíz:** las reglas de Emergencia se registraron en el cron compartido con Becas, cuyo corte es diario; nadie agregó la corrida frecuente que la regla de negocio supone.
- **Solución:** sin tocar lógica: un CronJob/cron aparte cada 5 min con `procesar_vencimientos --solo emergencia.derivacion` y otro con `--solo emergencia.caso_sin_avance` (`concurrencyPolicy: Forbid`, `activeDeadlineSeconds` < 5 min). Las reglas ya son idempotentes y fila por fila (`_aplicar_una_por_una`), así que la frecuencia no cambia el resultado, solo el momento. Para el arranque: `DECISIÓN CLIENTE: excluir emergencia.caso_sin_avance del bootstrap` (p. ej. `procesar_vencimientos --excluir emergencia.caso_sin_avance` o el `--solo` de las de Becas) — por defecto, excluirla.
- **Lo que NO hay que hacer:** subir el cron diario entero a cada 5 min: arrastra las reglas de Becas (cierre de convocatorias) a un ritmo para el que no se pensaron.
- **Tests a agregar:** `core/tests/test_cronjobs.py::CronEmergenciaTest.test_hay_corrida_frecuente_de_las_reglas_de_emergencia` (parsea `docker/k8s/cronjobs.yaml` y exige un schedule ≤ 5 min con `--solo emergencia.`).
- **Verificación:** el test; en testing, derivar con 30 min y ver el caso en `EN_GESTION` con la traza «Derivación vencida» a los ≤ 35 min.
- **Regla para no repetirlo:** **control mecánico** · test de `docker/k8s/cronjobs.yaml` · «Toda `ReglaVencimiento` con plazo en minutos (slug en una lista `REGLAS_DE_MINUTOS`) tiene un CronJob con schedule `*/N` y N ≤ 5; si no, rojo.»

---

### E-PERF-01 · El alta de un responsable nuevo recorre toda la tabla de ciudadanos con REGEXP, dos veces
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** PERF · **Origen:** fusión de E-PERF-01; probablemente compartido con la tajada de Dispositivos (ingreso) y la etapa 3 (`emergencia_confirmacion.py:383`, `emergencia_recepcion.py:143`) · **Ola:** 2 · **Esfuerzo:** M
- **ID de la pasada 1:** E1-PERF-02 + E2-PERF-01 (**hallado por 2 revisores**)
- **Alcance ampliado (E4 y juez):** el mismo `buscar_ciudadano_por_dni` corre también en `POST …/personas/consultar/` (vía `identificar_en_legajo`, `programas/services/identidad.py:186`, cubeta `personas_campo` 120/h) y en `GET …/dispositivos/{id}/buscar/` (`emergencia_recepcion.py:143`, cubeta `emergencia_buscar` 300/h). Es el mismo REGEXP; la ficha queda con tres consumidores (alta de caso, confirmación bajo candado, consultas de la app). **Hallado por 2 revisores (E1 y E2) y citado por E3 y E4: sube de peso.** Ejecutar primero la mitad barata (S) de la solución de E2 (no repetir el recorrido y no correrlo con el caso tomado) y después, si la medición lo pide, la columna `dni_normalizado`.
- **Ubicación:** `programas/services/ingreso.py:79` (`Ciudadano.objects.exclude(dni=dni).filter(dni__regex=r"[^0-9]")`),
  llamado desde `programas/services/emergencia_alta.py:322` (`_responsable`) y otra vez desde
  `programas/services/ingreso.py:354` (`_crear_legajo`, vía `alta_minima_de_persona` → `_alta_manual`).
- **Escenario:** en una evacuación la mayoría de los responsables **no** tiene legajo. Cada alta de caso
  con DNI nuevo: (1) `filter(dni=…)` por el índice único → nada; (2) `dni REGEXP '[^0-9]'` sobre **toda**
  `legajos_ciudadano` (un REGEXP no usa índice: `type=ALL`), trae los que tienen separadores y los
  normaliza en Python; (3) `alta_minima_de_persona` repite (1)+(2) en `_crear_legajo` antes de insertar.
  Con 50.000–100.000 ciudadanos son 2 scans completos por alta (≈ 100–300 ms en total en MariaDB,
  estimado), dentro de la transacción de `crear_caso` y en el camino de la app de campo. Crece con
  **todos** los ciudadanos del sistema (Becas, Dispositivos, Emergencia), no con los casos. No llega a
  10 s con el volumen supuesto; sí suma CPU de la base en el pico, cuando 50 altas llegan a la vez.
- **Causa raíz:** la regla «el DNI escrito como esté en la base» se resuelve escaneando, porque no hay una
  columna con el DNI normalizado que se pueda indexar.
- **Solución (preserva lógica):** columna `Ciudadano.dni_normalizado` (`null=True`, `db_index=True`, expand
  puro), rellenada en lotes con `normalizar_dni(dni)` y mantenida en `save()`; `buscar_ciudadano_por_dni`
  pasa a `filter(dni=dni).first()` y, si no hay, `filter(dni_normalizado=dni).first()`: el mismo
  resultado, por índice. Mientras tanto (S): evitar el segundo scan, porque `_responsable` ya sabe que no
  hay persona y `_crear_legajo` solo necesita volver a buscar después de un `IntegrityError` (la carrera
  la cubre el UNIQUE de `dni`); toca `ingreso.py`, compartido con Dispositivos: correr sus tests.
- **Lo que NO hay que hacer:** acotar el REGEXP a formatos conocidos (`dni__in=["30.111.222", …]`): deja
  de encontrar legajos cargados con otros separadores y cambia la regla de identidad (Cambio 486).
- **Tests a agregar:** `programas/tests/test_ingreso.py::BuscarCiudadanoPorDniTest.test_dni_nuevo_no_recorre_la_tabla`
  (`CaptureQueriesContext`: ninguna consulta con `REGEXP`), más los casos existentes de DNI con puntos.
- **Verificación:** banco MySQL (ya siembra `Ciudadano`, `scripts/perf_mysql/escalar_bench.py:162-172`):
  `EXPLAIN ANALYZE SELECT id, dni FROM legajos_ciudadano WHERE NOT (dni = '99999999') AND dni REGEXP '[^0-9]';`
  → esperado `type=ALL`, `rows≈N`. Ruta: `POST /emergencia/casos/nuevo/` con DNI inexistente (agregar a
  `_extra_targets()` de `bench_mysql.py` como `emergencia_caso_nuevo_dni_nuevo`, actor con rol de mesa).
- **Regla para no repetirlo:** **control mecánico** · test ratchet en `core/tests/` · buscar en
  `programas/services/**` y `legajos/**` `__regex=`/`__iregex=` sin un filtro por índice (pk, FK o campo
  único) en la misma consulta, y fallar con «REGEXP sin acotar: recorre la tabla entera. Indexá el valor
  normalizado.»

#### Aporte del segundo revisor (E2-PERF-01: Confirmar a una persona nueva recorre dos veces la tabla entera de ciudadanos con el caso bloqueado)
_Pasada 1: severidad MEDIA · estado PLAUSIBLE · esfuerzo S._

- **Ubicación:** `programas/services/emergencia_confirmacion.py:383` (primera búsqueda) y `:407` → `_dar_de_alta` → `programas/services/ingreso.py:355` (`_crear_legajo`, segunda búsqueda; tercera en `:366` si choca el `IntegrityError`); el recorrido es `programas/services/ingreso.py:79-82`. También `programas/services/emergencia_recepcion.py:143` (búsqueda por DNI de la guardia, sin candado).
- **Escenario:** familia de 7 evacuada; 5 son chicos sin legajo. La guardia confirma persona por persona desde la app. Por cada DNI que no está exacto en la base, `buscar_ciudadano_por_dni` hace `SELECT id, dni FROM legajos_ciudadano WHERE NOT (dni = X) AND dni REGEXP "[^0-9]"`: recorre el índice entero de `dni` (la función sobre la columna anula la búsqueda por índice) y decodifica en Python lo que devuelve. `confirmar_integrante` lo hace **dos veces** por persona nueva (línea 383 y otra vez en `_crear_legajo:355`, microsegundos después), y las dos con `CasoEmergencia` y `Derivacion` tomados `FOR UPDATE` (`_abrir_ingreso`, línea 357). Con 7 personas: 10 recorridos completos de la tabla de ciudadanos por familia, más 1 por cada búsqueda por DNI en la puerta. Mientras dura, esperan la otra guardia que confirma a un integrante de la **misma** familia, el egreso de un familiar ya alojado (`al_egresar_estadia` pide el caso con la estadía y la plaza tomadas) y la mesa que cancela.
- **Causa raíz:** el respaldo para DNIs legacy con separadores es un recorrido O(ciudadanos) que su propio autor dejó documentado como aceptable **porque** «no es una ruta caliente ni toma ningún lock» (`legajos/services/ciudadanos.py:95-99`, misma regla). Emergencia lo usa en el camino caliente de la etapa 3 y dentro de la transacción con candados. Además, la segunda búsqueda es redundante: el alta nueva guarda el DNI normalizado (`legajos/forms/ciudadanos.py:149-167`, `clean_dni`), así que la carrera que `_crear_legajo` quiere cubrir solo puede traer una fila **exacta**; las fichas con separadores son legacy y ya se miraron en la línea 383.
- **Con qué crece:** filas de `legajos_ciudadano` (todo el padrón, no Emergencia). Consultas: 2 recorridos por persona nueva confirmada (3 con choque de DNI), 1 por búsqueda en la puerta. Filas: N ciudadanos por recorrido. A 20.000 es despreciable; a 500.000 o 1.000.000 se estima del orden de 0,3 a 1 s por recorrido (sin medir), 0,6 a 2 s con el caso tomado por persona.
- **Solución:** sin cambiar qué persona se encuentra:
  1. (S) No repetir el recorrido dentro de la misma transacción: `_crear_legajo` recibe `ya_buscado=False`; con `True` (lo pasa `alta_minima_de_persona` cuando la llama Emergencia después de su propia búsqueda) la relectura antes del `form.save()` y en el `IntegrityError` mira solo `Ciudadano.objects.filter(dni=dni).first()`: la fila que puede aparecer por carrera nace normalizada.
  2. (S) Hacer la búsqueda de la línea 383 **antes** de `_abrir_ingreso` (es lectura sin candado, como `_cama_del_dispositivo`); con el candado puesto, solo el lookup exacto (indexado) para la carrera. El recorrido deja de correr con el caso tomado.
  3. (M, opcional, cuando se mida) columna `dni_normalizado` indexada (expand con `null=True`, relleno en lotes), o cerrar las fichas de `listar_dni_no_normalizados` (P-17) y apagar el respaldo.
- **Lo que NO hay que hacer:** sacar el respaldo REGEXP sin más: deja de reconocer a la persona cargada como `12.345.678` y la parte en dos legajos (G1c-08). Ni meterle un `Length` o un regex con el largo interpolado: esquiva el ratchet de RED-48.
- **Tests a agregar:** `programas/tests/test_emergencia_alojar.py::ConfirmarIntegrantePresupuestoTests.test_persona_nueva_un_solo_recorrido_regexp` (con `CaptureQueriesContext`: una sola consulta con `REGEXP` por confirmación de persona nueva, y ninguna después del `SELECT … FOR UPDATE` del caso).
- **Verificación:** banco MariaDB: (a) sembrar 500.000 `Ciudadano` y medir `buscar_ciudadano_por_dni("99999999")` con `time.perf_counter` (mejor de 3); (b) `EXPLAIN SELECT id, dni FROM legajos_ciudadano WHERE NOT (dni = "99999999") AND dni REGEXP "[^0-9]"`: esperar `type=index`, `rows` del orden de N; (c) candado con dos sesiones: S1 `BEGIN; SELECT id FROM programas_casoemergencia WHERE id = <caso> FOR UPDATE;` y después el SELECT REGEXP dos veces; S2 `SELECT id FROM programas_casoemergencia WHERE id = <caso> FOR UPDATE;` midiendo la espera; (d) rutas nuevas en `scripts/perf_mysql/bench_mysql.py::_extra_targets`: `POST reverse("emergencia_api:caso-integrante-confirmar", args=[caso.pk, n])` con un DNI inexistente, y `GET reverse("emergencia_api:dispositivo-buscar", args=[disp.pk]) + "?dni=99999999"` (con la siembra de abajo).
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` §Trampas conocidas · «9. `buscar_ciudadano_por_dni` y `existe_con_dni` recorren `legajos_ciudadano` entera con `REGEXP` cuando el DNI exacto no está. Se llaman **fuera** de toda transacción con candado y una sola vez por pedido; adentro del candado, solo el lookup exacto por `dni`.» Y en `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas activas: «llamadas a `buscar_ciudadano_por_dni` después de un `select_for_update()` en el mismo camino».

---

### E-PERF-02 · El candado del numerador de casos queda tomado hasta el commit, con fotos y reservas adentro
**Severidad:** MEDIA · **Estado:** PLAUSIBLE · **Eje:** PERF · **Origen:** fusión de E-PERF-02 · **Ola:** 2 · **Esfuerzo:** M
- **ID de la pasada 1:** E1-PERF-01 + E1-ERR-02 (**hallado por 2 revisores**)
- **Fusión (juez):** absorbe E-PERF-02 (misma causa y mismas líneas: el candado del numerador toma `FOR UPDATE` en `emergencia_alta.py:504` y se suelta recién al commit, con las fotos y, en `ingreso_directo`, las plazas adentro). **Hallado por 2 revisores (E1 perf y E1 corrección) y citado por E4: sube de peso.** Se conserva el diseño de esta ficha (número provisorio + `asignar_numero` al final, con `numerar=False` para `ingreso_directo` y `avisar_a_la_mesa`).
- **Ubicación:** `programas/services/emergencia_alta.py:504` (`siguiente_numero` dentro de `crear_caso`,
  `@transaction.atomic` en `:402`), `:529-533` (fotos) y `:545` (traza) después del candado;
  `programas/services/emergencia_comun.py:51` (`select_for_update` del numerador);
  `programas/services/emergencia_sin_derivacion.py:106-152` (`ingreso_directo`) y `:174-195` (`avisar_a_la_mesa`).
- **Escenario:** pico de una inundación, 30–60 agentes de la app de campo mandan casos con dos fotos de
  hasta 5 MB (`ADJUNTO_MAX_BYTES`, `core/validators.py:28`). Cada `crear_caso` toma `FOR UPDATE` sobre
  **la única fila** `NumeradorEmergencia(serie="C", anio=2026)` y la suelta recién en el commit: entre
  medio guarda el caso, escribe las dos fotos en el storage (`FileSystemStorage`, el volumen del pod),
  vuelve a validarlas en `full_clean` y crea la traza. Todas las altas de la provincia —app, mesa e
  ingreso directo— se serializan detrás de esa fila. Con ~200 ms de candado por alta, la alta n.° 50
  espera ~10 s en el `SELECT … FOR UPDATE` y el cliente corta por `read_timeout` → `OperationalError` → 500
  (en la app, un 5xx que reintenta y vuelve a la cola). Peor en `ingreso_directo`: después de `crear_caso`
  la misma transacción bloquea el caso, crea la derivación y **bloquea plazas** en `_reservar_camas`
  (`emergencia_sin_derivacion.py:126-128`); si otra guardia tiene esas plazas tomadas aceptando una
  derivación, el numerador queda retenido mientras se espera esa otra transacción, y con él toda alta de caso.
- **Causa raíz:** el docstring del módulo (`programas/services/emergencia.py:45-46`) dice que el
  numerador «es una hoja… después de él solo hay altas», pero en `crear_caso` se toma **antes** de las
  escrituras de archivos y, cuando lo llama la etapa 3, antes de otros candados (caso, plazas). El
  candado dura lo que dura la transacción más externa, no lo que dura numerar.
- **Solución (preserva lógica):** numerar como **último paso de la transacción más externa**. El caso se
  inserta con un `numero` provisorio único que nadie llega a ver (p. ej. `"P" + uuid4().hex[:15]`, cabe en
  `max_length=16`; la fila no es visible para otras transacciones hasta el commit), se guardan fotos,
  traza y lo que agregue la etapa 3, y justo antes de salir un helper `asignar_numero(caso)` hace
  `siguiente_numero(...)` + `caso.save(update_fields=["numero"])`. `crear_caso` lo llama al final cuando
  es la transacción dueña; `ingreso_directo` y `avisar_a_la_mesa` le pasan `numerar=False` y lo llaman en
  su última línea. El número sigue siendo correlativo y sigue volviendo atrás con un rollback (hoy
  `PRIMERA_TRAZA` no cita el número; si una traza lo citara, va después de numerar). Ajustar el docstring
  del orden de candados.
- **Lo que NO hay que hacer:** numerar en una transacción aparte (`atomic` independiente u `on_commit`):
  deja huecos en la serie o expone casos sin número; ni volver a `MAX(numero)+1`.
- **Tests a agregar:** `programas/tests/test_emergencia_concurrencia.py::NumeradorTest.test_numerador_se_toma_al_final_de_la_transaccion`
  (con `CaptureQueriesContext`: el `SELECT … FOR UPDATE` del numerador es la última lectura antes del
  `UPDATE … numero`), y el mismo para `ingreso_directo`.
- **Verificación:** banco MySQL/MariaDB con dos conexiones: una corre `crear_caso` con dos fotos de 5 MB y
  se pausa después de numerar; medir cuánto espera la segunda. Durante 50 `POST /api/emergencia/casos/`
  concurrentes (script con `concurrent.futures` y `django.test.Client` con token de agente), leer
  `information_schema.INNODB_TRX` y `performance_schema.data_lock_waits` (MySQL) /
  `information_schema.INNODB_LOCK_WAITS` (MariaDB). Candado medido > 200 ms por alta ⇒ subir a ALTA.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` §Transacciones y bloqueos ·
  «Un contador con `select_for_update()` (numeradores, correlativos) se toma **al final** de la transacción
  más externa: todo lo que pase después de tomarlo —archivos, otros candados, llamadas— lo paga cada alta
  concurrente en cola. Si la función que numera la llama otra transacción, numerar va en la última línea
  de la de afuera.»

#### Aporte del segundo revisor (E1-ERR-02: El alta del caso retiene el candado del numerador mientras valida y escribe las fotos)
_Pasada 1: severidad MEDIA · estado PLAUSIBLE · esfuerzo S-M._

- **Ubicación:** `programas/services/emergencia_alta.py:503-545` (numera en la 504; fotos en 529-533; traza en 545;
  el commit es al salir de `crear_caso`) y `programas/services/emergencia_comun.py:64-69`
  (`siguiente_correlativo`: `select_for_update` sobre la fila del contador de la serie `C`).
- **Escenario:** después de un corte de señal, decenas de teléfonos vacían su cola de relevamientos a la vez, cada
  uno con dos fotos de hasta 5 MB, y la mesa carga casos en paralelo. Cada `crear_caso` toma el `FOR UPDATE` de la
  fila `(C, 2026)` en la línea 504 y lo suelta recién al commit, después de `adjunto.full_clean()` —que vuelve a
  correr `validar_foto` sobre cada imagen, ya validada en `_problemas_de_las_fotos` antes del candado— y de
  escribir los dos archivos en el storage. Todas las altas quedan en fila detrás de ese candado: si la cola
  acumulada supera los 10 s de `read_timeout` de la conexión con ECOM, las que esperan mueren con
  `OperationalError` (2013) → 500. La app reintenta (es idempotente por `uuid_cliente`), pero el reintento vuelve
  a la misma fila de espera, y la mesa ve el 500 en «Nuevo caso».
- **Causa raíz:** el numerador se pide **antes** de las escrituras lentas de la transacción en vez de ser lo
  último. El docstring de `emergencia.py:45-46` lo define como «hoja» del orden de candados, pero una hoja que se
  toma temprano igual serializa todo lo que viene después hasta el commit.
- **Solución:** pedir el número como **última** escritura de la transacción, sin cambiar qué número recibe cada
  caso ni el formato:
  1. crear `CasoEmergencia` con un `numero` provisional único que entre en `max_length=16`
     (p. ej. `f"tmp-{uuid4().hex[:12]}"`), guardar fotos y traza como hoy;
  2. al final, `caso.numero = siguiente_numero(NumeradorEmergencia.Serie.CASOS, ahora)` y
     `caso.save(update_fields=["numero", "modificado"])`.
  El candado pasa a durar un `UPDATE` del contador y un `UPDATE` del caso. Como todo sigue en la misma
  transacción, un rollback no deja huecos ni números provisionales a la vista. Alternativa más chica si se
  prefiere no tocar el orden: sacar la segunda validación de imagen de adentro del candado (ya la hizo
  `_problemas_de_las_fotos`), lo que acorta pero no resuelve.
  `DECISIÓN CLIENTE`: no aplica; es interno.
- **Lo que NO hay que hacer:** no volver a `MAX(numero) + 1` ni numerar fuera de la transacción: los números
  tienen que seguir siendo correlativos sin huecos y sin duplicados.
- **Tests a agregar:** `programas/tests/test_emergencia_alta.py::CrearCasoTests.test_numerar_es_la_ultima_escritura`
  (orden de llamadas con `mock`, como `OrdenDeLosCandadosEmergenciaTests`); en
  `programas/tests/test_emergencia_concurrencia.py`, una carrera de N altas con foto contra el motor real que
  mida el tiempo de espera del candado.
- **Verificación:** banco MySQL/MariaDB de `scripts/perf_mysql/` con `read_timeout=10`: 30 altas concurrentes con
  dos fotos cada una, sin `OperationalError`.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` (transacciones) · «Un
  `select_for_update` sobre una fila caliente (numeradores, contadores) se toma como **última** escritura de la
  transacción: todo lo que corre después de él —archivos, validaciones, otras filas— alarga la espera de los
  demás contra el `read_timeout` de 10 s de ECOM.»

---

### E-PERF-03 · El tablero recorre todo el histórico de casos en cada carga para quedarse con la ventana del día
**Severidad:** MEDIA · **Estado:** PLAUSIBLE · **Eje:** PERF · **Origen:** nuevo · **Ola:** 2 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E3-PERF-01
- **Ubicación:** `programas/selectors/emergencia_tablero.py:218` (`_casos_de_la_ventana`), con las subconsultas de 220-222 y `programas/selectors/emergencia.py:384` (`ultima_traza_del_caso`); la llama `programas/views/emergencia_tablero.py:35` en cada GET.
- **Escenario:** emergencia larga o varios eventos en el año: 10.000 casos, 9.000 cerrados hace más de 24 h, ~1.000 abiertos. Cada «Actualizar» del supervisor lee las 10.000 filas de `programas_casoemergencia` (con sus columnas JSON `situacion`/`necesidades`) para devolver ~1.000-1.200. Con el histórico creciendo (el módulo no purga ni archiva casos), el costo del tablero crece con todos los casos que existieron, no con los de la operación. El docstring del módulo (líneas 4-6) promete «nunca el histórico completo»: el resultado sí, el recorrido no.
- **Causa raíz:** el `WHERE` es `NOT (estado = "CERRADO") OR alojado_en >= %s OR cerrado_en >= %s`. Para usar índice en un `OR` el motor necesita un índice por cada rama (index_merge/sort_union); `alojado_en` y `cerrado_en` no tienen ninguno, así que el plan esperable es `type=ALL`. Además, por cada fila que pasa el filtro corren tres subconsultas correlacionadas: dos idénticas para la última traza (`accion` y `detalle`, líneas 220-221), cada una `WHERE caso_id = ? ORDER BY creado_en DESC, id DESC LIMIT 1` con filesort porque `TrazaCaso` solo tiene el índice de la FK, y un `EXISTS` sobre `ContactoCaso`. Con ~1.200 filas: ~3.600 subconsultas dependientes por carga.
- **Consultas/filas estimadas:** 1 consulta; ~10.000 filas leídas (crece lineal con los casos acumulados) + ~3.600 lecturas por índice de FK con filesort de ~5 trazas cada una (crece con los abiertos). Estimación sin medir: 0,1-0,5 s con 10.000 casos; el riesgo de 500 aparece recién con decenas de miles de casos acumulados o con un pico de abiertos alto. Por eso MEDIA y no ALTA.
- **Solución (preserva lógica y pantalla):** que el recorte lo haga un índice, sin cambiar qué casos entran. (1) Migración expand-only `AddIndex` en `CasoEmergencia`: `Index(fields=["cerrado_en"])` e `Index(fields=["alojado_en"])`; con las tres ramas indexadas (la de `estado` ya está en `(estado, prioridad)`) MariaDB/MySQL pueden resolver el `OR` con index_merge. (2) Si el `EXPLAIN` sigue en `ALL` (el `<>` sobre `estado` suele empujar al optimizador a no mezclar), plan B: elegir primero los ids con tres consultas indexadas (`estado__in=<estados abiertos>`, `alojado_en__gte`, `cerrado_en__gte`), unirlos en Python y correr la consulta actual con `pk__in=ids`. Son +2 consultas fijas: el presupuesto de `test_emergencia_tablero` se mueve en el mismo diff. (3) Opcional: `Index(fields=["caso", "creado_en", "id"])` en `TrazaCaso` (E-DAT-01).
- **Lo que NO hay que hacer:** cachear la foto del tablero (es «calculado al leer», RN-5.1, y el SLA se mide en minutos); acotar por `creado` (un caso abierto de hace días tiene que seguir entrando).
- **Tests a agregar:** `programas/tests/test_emergencia_tablero.py::TableroRendimientoTest.test_ventana_se_resuelve_por_indices` (con `CaptureQueriesContext`: la consulta de la ventana va por `pk__in` o por columnas indexadas), y la entrada de `/emergencia/tablero/` en `scripts/perf_budgets.json` (cierra en parte E-PERF-13).
- **Verificación / medición:** sembrar en `chaco_perf_ci` 10.000 y 100.000 `CasoEmergencia` (90 % `CERRADO` con `cerrado_en` en los últimos 6 meses, 1.000 abiertos repartidos en los estados, 5 `TrazaCaso` por caso, 0-2 `ContactoCaso`); `EXPLAIN` del SQL de `_casos_de_la_ventana` (imprimir `qs.query` armado igual que en la función) y mirar `type`/`rows` de `programas_casoemergencia` y las `DEPENDENT SUBQUERY`; después `scripts/perf_mysql/perfil_ruta.py` sobre `/emergencia/tablero/` con un supervisor (o agregar ese target a `bench_mysql.py`). Pasa a ALTA si con 100.000 casos la consulta supera 1 s.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` §Índices · «Un `filter(A | B | C)` usa índice solo si cada rama tiene uno; si una rama es un `<>` o una columna sin índice, el motor recorre la tabla entera aunque el resultado sea chico. Para "abiertos + recientes", indexá las columnas de fecha de la ventana o resolvé los ids por rama y uní en Python.»

---

### E-PERF-04 · La página de la bandeja ordena por expresiones y ordena el historial entero de la solapa
**Severidad:** MEDIA · **Estado:** PLAUSIBLE · **Eje:** PERF · **Origen:** trampa 4 de la rúbrica (paginar con `select_related`) · **Ola:** 2 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E1-PERF-03
- **Ubicación:** `programas/selectors/emergencia.py:317-319` (`select_related("grupo__responsable", "localidad", "tomado_por")`
  + cinco subconsultas correlacionadas de `con_avisos_de_la_mesa`, `:415-428`), `:341-352` (orden
  `CASE WHEN id IN (…fuera…)`, `CASE prioridad`, `creado`, `id`); `programas/views/emergencia.py:106-108`
  (`Paginator(…, 50).get_page(page)`).
- **Escenario:** solapa «Cerrados», o «Abiertos» con muchos `ALOJADO` (familias alojadas semanas), o un
  filtro de `estado`/`localidad`/`texto` sobre el historial. Con 10.000 casos, «Cerrados» son ≈ 9.000
  filas: el `ORDER BY` es una expresión (`CASE`) que ningún índice sirve, así que el motor lee las 9.000,
  las ordena (filesort) y recién ahí corta 50 —con `OFFSET` creciente al paginar—. Si el optimizador no
  arranca por `programas_casoemergencia` (con `texto`, el `OR` contra `legajos_ciudadano.apellido` lo
  puede llevar a otro orden de JOIN), el orden pasa a `Using temporary; Using filesort` sobre filas
  **anchas** (`Ciudadano` entero + los JSON `situacion`/`necesidades`) y las subconsultas del `SELECT` se
  evalúan para **todas** las filas antes del `LIMIT` (≈ 9.000 × 5 búsquedas por índice). El docstring de
  `con_avisos_de_la_mesa` (`:411-412`) da por hecho que corren sobre las 50: depende del plan. Estimado:
  decenas a pocos cientos de ms con 10.000 casos; crece lineal con el historial. No llega a 10 s con el
  volumen supuesto.
- **Causa raíz:** la página se elige sobre la consulta completa (JOINs + anotaciones) en vez de elegir
  primero los ids y rehidratar.
- **Solución (preserva lógica y orden):** paginar `bandeja(...).values_list("pk", flat=True)` —mismos
  filtros y mismo `order_by`, sin `select_related` ni anotaciones— y rehidratar la página con
  `con_avisos_de_la_mesa(CasoEmergencia.objects.select_related(...)).filter(pk__in=ids)`, reordenando en
  Python por la posición en `ids`. El `Paginator` sigue contando con el mismo `COUNT(*)`. Mismo resultado
  visible, una consulta fija más.
- **Lo que NO hay que hacer:** agregar un índice sobre `creado` creyendo que sirve al orden: el primer
  criterio es un `CASE`, no lo usa.
- **Tests a agregar:** `programas/tests/test_emergencia_mesa.py::BandejaRendimientoTest.test_pagina_se_elige_por_ids`
  (el orden de 120 casos con mezcla de SLA y prioridad es idéntico antes y después) y `CONSULTAS_E2` +1 en
  el mismo diff.
- **Verificación:** banco con la siembra de abajo. `EXPLAIN ANALYZE` de la SQL de
  `selectores.bandeja({"solapa": "cerrados"}, sla=sla, ahora=now, semaforos=s)[0:50]`, de la misma con
  `[4500:4550]` y con `{"texto": "gonz"}`. Señal: `Using temporary`, `rows` ≈ total de la solapa, o
  `DEPENDENT SUBQUERY` con `loops` ≫ 50. Rutas para `bench_mysql.py`: `emergencia:bandeja` con
  `?solapa=cerrados`, `?solapa=cerrados&page=90` y `?texto=gonz`. > 1 s ⇒ ALTA.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/rendimiento.md` §Trampas
  medidas, ítem 4 · agregar: «También cuando el `ORDER BY` es una expresión (`Case`/`When`, `pk__in` de una
  lista): ningún índice lo sirve y el motor ordena la solapa entera. Elegir los ids de la página primero, y
  no dar por hecho que las subconsultas del `SELECT` corren solo sobre la página: depende del plan.»

---

### E-PERF-05 · E4 (listado de entregas) ordena y pagina todo el histórico sin índice, con `select_related` en la consulta paginada
**Severidad:** MEDIA · **Estado:** PLAUSIBLE · **Eje:** PERF · **Origen:** nuevo · **Ola:** 2 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E3-PERF-02
- **Ubicación:** `programas/selectors/kits.py:109-124` (`listado_de_entregas`), paginado en `programas/views/emergencia_kits.py:173-175`; en la misma carga `programas/selectors/kits.py:130` (`conteos_de_solapas`) y `:141` (`destinos_con_entregas`).
- **Escenario:** 20.000 entregas acumuladas; la mesa abre E4 (cualquier solapa). La consulta de la página es `SELECT … FROM entregakit INNER JOIN dispositivo LEFT JOIN auth_user ×2 [WHERE estado …] ORDER BY creado DESC, id DESC LIMIT 50 OFFSET n`. Ningún índice sirve al `ORDER BY` (ni `creado` ni `estado` encabezan uno), así que el motor arma la unión completa, la ordena con filesort y recién ahí recorta: es la trampa 4 medida en Chaco («paginar con `select_related` en la consulta paginada»), con el agravante de que la `INNER JOIN` a `Dispositivo` (200 filas) invita a arrancar por la tabla chica. El filtro por fecha (`creado__gte/__lt`, línea 123) tampoco tiene índice. En la misma carga, `Paginator.count`, `conteos_de_solapas` y `destinos_con_entregas` recorren las 20.000 entregas (estas dos últimas probablemente por `(dispositivo, estado)` como índice cubriente, que es barato).
- **Causa raíz:** el listado crece con el histórico (las entregas no se archivan) y ni el orden ni la solapa por `estado` tienen índice.
- **Consultas/filas estimadas:** 5 consultas de la vista sobre `EntregaKit` (página, count, prefetch de líneas, conteos, destinos); la de la página lee y ordena ~20.000 filas unidas (lineal con las entregas) y las páginas profundas suman el `OFFSET`. Estimación sin medir: decenas a cientos de ms con 20.000; no llega a 10 s con el volumen supuesto, por eso MEDIA.
- **Solución (preserva lógica y pantalla):** (1) migración expand-only en `EntregaKit`: `Index(fields=["estado", "creado", "id"])` (solapa/estado + orden) e `Index(fields=["creado", "id"])` (sin solapa, y filtro por fecha). (2) En `listado_de_entregas`, separar elegir la página de hidratarla (patrón de la trampa 4): paginar el queryset ordenado con `only("pk")` y sin `select_related`, y rehidratar con `EntregaKit.objects.filter(pk__in=ids).select_related(...).prefetch_related(_lineas_ordenadas())` respetando el orden de `ids`. Mismo resultado y misma pantalla.
- **Lo que NO hay que hacer:** sacar el `select_related` sin rehidratar (vuelve el N+1 de dispositivo y usuarios, que zeal frena en el CI).
- **Tests a agregar:** `programas/tests/test_emergencia_kits.py::ListadoEntregasRendimientoTest.test_pagina_no_ordena_con_join` (la consulta con `LIMIT` no lleva `JOIN`) y la entrada `/emergencia/entregas/` en `scripts/perf_budgets.json`.
- **Verificación / medición:** sembrar 20.000 y 200.000 `EntregaKit` sobre 200 dispositivos (70 % `RECIBIDA`, 10 % `RECIBIDA_CON_DIFERENCIAS`, el resto abiertas/canceladas) con 5 líneas cada una; `EXPLAIN` de `str(listado_de_entregas({"solapa": "recibidas"})[:50].query)` (buscar `Using temporary; Using filesort` y `rows` cerca del total); `perfil_ruta.py` sobre `/emergencia/entregas/?solapa=recibidas` y `?solapa=recibidas&page=300`.
- **Regla para no repetirlo:** **control mecánico** · `scripts/perf_budgets.json` + test de rendimiento · toda ruta de listado de Emergencia entra al presupuesto, y un test de patrón falla si la consulta con `LIMIT` de un listado paginado lleva `JOIN` (`assert "JOIN" not in sql_de_la_pagina`).

---

### E-LIM-02 · La vista de cancelar derivación busca la pendiente y decide el `EstadoCambio` fuera del candado
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** thermos E1 · **Ola:** 4 · **Esfuerzo:** S
- **ID de la pasada 1:** E1-LIM-10
- **Ubicación:** `programas/views/emergencia.py:345-357` (`CancelarDerivacionView.ejecutar` llama a `mesa.derivacion_pendiente_de` y levanta `EstadoCambio` con mensaje propio). El servicio es `programas/services/emergencia.py:576` (`cancelar_derivacion(derivacion, …)`).
- **Escenario:** la API y cualquier otro caller tienen que repetir «buscar la pendiente del caso y, si no hay, 409» con su propio texto. Es lógica de dominio en la vista, contra RU-2 y el docstring del módulo («las vistas no tienen reglas del caso»). La lectura corre sin candado. El servicio vuelve a verificar, así que no hay bug, pero el mensaje de «ya no hay pendiente» depende de quién llame.
- **Causa raíz:** el servicio recibe una `Derivacion` y la pantalla tiene un `CasoEmergencia`. El puente quedó en la vista.
- **Solución:** sumar a `services/emergencia.py` la función `cancelar_derivacion_del_caso(caso, usuario, motivo)`, que valida el motivo, toma `_bloquear_caso` y después `Derivacion.objects.select_for_update().filter(clave_vigente=caso.pk, estado=PENDIENTE).first()`. Si no hay, levanta `EstadoCambio` con el mismo texto que hoy escribe la vista. Si hay, sigue el cuerpo actual de `cancelar_derivacion`, que se refactoriza a un `_cancelar(caso_bloqueado, derivacion_bloqueada, …)` compartido. El orden caso → derivación se mantiene. La vista queda en una línea más el aviso.
- **Lo que NO hay que hacer:** bloquear la derivación antes que el caso. Rompe el orden global documentado (`services/emergencia.py:27-50`).
- **Tests a agregar:** `programas/tests/test_emergencia_casos.py::CancelarDerivacionTests.test_sin_pendiente_es_estado_cambio_desde_el_servicio`. Sumar la secuencia nueva a `OrdenDeLosCandadosEmergenciaTests`.
- **Verificación:** esos tests, y la vista sin `raise EstadoCambio`.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-auditor.md` · «En `views/emergencia*.py`, un `raise EstadoCambio` o una consulta que decide si la acción procede es hallazgo: va al servicio».

---

### E-LIM-03 · La compuerta «403 sin la capacidad, 404 sin alcance» está implementada dos veces con mecánicas distintas
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 4 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E3-LIM-02
- **Ubicación:** `programas/views/emergencia_dispositivo.py:79-94` `GuardiaView.dispatch`
  (`puede_en_programa_dispositivos` + `dispositivo_operable_o_404`). `programas/views/emergencia_kits.py:524-545`
  `RecepcionKitsMixin.dispatch` (`dispositivos_en_alcance(...).filter(pk=...)` + `recibe_kits`).
- **Escenario:** las dos implementan el contrato C2 / Cambio 432, pero en orden inverso: la guardia decide 403
  antes de buscar y la de kits busca primero y después decide el 403. Si se agrega `DispositivoNoOperable`
  (estado del dispositivo) u otra condición en `dispositivo_operable_o_404`, la recepción de kits no la hereda.
  El resto de las vistas de Dispositivos (`dispositivos_bitacora.py:215`, `dispositivos_legajo.py:778`…) usa
  el helper canónico.
- **Causa raíz:** falta un mixin común «vista de un dispositivo con capacidad X». Cada etapa escribió su
  `dispatch`, y los dos repiten el `if not request.user.is_authenticated` que `LoginRequiredMixin` ya resuelve.
- **Solución:** un `DispositivoConCapacidadMixin(capacidad, kwarg_pk)` en `programas/mixins_dispositivos.py`:
  primero `puede_en_programa_dispositivos(user, capacidad)` (403) y después
  `dispositivo_operable_o_404(request, pk, capacidad, queryset)`. `GuardiaView` y `RecepcionKitsMixin` lo
  heredan con `capacidad = CAP_ADMITIR` o `CAP_RECIBIR_KIT`. Hay que confirmar que
  `puede_en_programa_dispositivos(user, CAP_RECIBIR_KIT)` equivale a `recibe_kits(user)`; si no, se agrega un
  hook `puede_entrar(user)` que por defecto llama a la primera función.
- **Lo que NO hay que hacer:** unificar en un 404 sin el 403 previo. RN-4.8 y la API (`SIN_MODULO`) distinguen
  los dos casos.
- **Tests a agregar:** `programas/tests/test_emergencia_kits.py::RecepcionAlcanceTest.test_dispositivo_no_operable_es_404`
  (hoy pasaría con otro motivo).
- **Verificación:** los tests de alcance existentes de E6 y de recepción siguen en verde. Mutación: quitar el
  403 del mixin pone en rojo los dos.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md`, tabla de
  helpers canónicos: agregar la fila «Cargar un dispositivo con alcance → `dispositivo_operable_o_404` / mixin
  común; un `dispatch` propio que reimplementa 403/404 es duplicado».

---

### E-LIM-04 · Kits no tiene `acciones_de_entrega`: la vista decide qué transición se ofrece con el estado crudo
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — (relacionado con E-LIM-17) · **Ola:** 4 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E3-LIM-03
- **Ubicación:** `programas/views/emergencia_kits.py:126-142` (menú de la fila), `:192-196` (estados que abren
  cada modal), `:436-437` (`puede_marcar_en_camino`, `puede_cancelar` del detalle). Las reglas de verdad están
  en `programas/services/kits.py:367` (`PREPARADA`) y `:394` (`ESTADOS_ABIERTOS`).
- **Escenario:** «Marcar en camino solo sobre `PREPARADA`» está escrito cuatro veces: tres en la vista y una en
  el servicio. Si la regla se amplía (por ejemplo, re-despachar una `EN_CAMINO` para corregir la hora), el
  menú, el modal por GET y el detalle se desalinean del servicio. Se ofrece una acción que termina en
  `EstadoCambioEntrega`, o se esconde una que vale. La guardia no tiene este problema:
  `servicio.acciones_del_ingreso` (`emergencia_dispositivo.py:312`) ya es el patrón correcto.
- **Causa raíz:** el servicio expone las transiciones pero no su disponibilidad.
- **Solución:** `services/kits.py`: `ACCIONES = {"en_camino": (Estado.PREPARADA,), "cancelar": EntregaKit.ESTADOS_ABIERTOS, "observar": EntregaKit.ESTADOS_RECIBIDOS}`
  y `acciones_de_entrega(entrega) -> dict[str, bool]`. `_exigir_estado(bloqueada, *ACCIONES["en_camino"], …)`
  lee la misma tabla. La vista usa `acciones["en_camino"]` en `_fila`, en el detalle y en `_modal`, que recibe
  `ACCIONES[...]` en lugar de la lista literal.
- **Tests a agregar:** `programas/tests/test_emergencia_kits.py::AccionesDeEntregaTest.test_tabla_coincide_con_transiciones`
  recorre cada estado y comprueba que la acción ofrecida no levanta `EstadoCambioEntrega`.
- **Verificación:** `grep -n "Estado.PREPARADA\|ESTADOS_ABIERTOS" programas/views/emergencia_kits.py` sin resultados.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md`, «Qué escalar»: «Una vista que compara `.estado`
  para decidir qué botón mostrar, cuando el servicio tiene la transición: pedir `acciones_de_<x>()` en el servicio».

---

### E-LIM-05 · El enrutamiento «estado del caso → pantalla» está repartido en tres métodos y uno se pisa solo
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 4 · **Esfuerzo:** S
- **ID de la pasada 1:** E3-LIM-04
- **Ubicación:** `programas/views/emergencia_dispositivo.py:205-208` (`despues_de_un_cambio`), `:275-282`
  (`ya_no`), `:287-300` (`traducir`). Las vistas que no usan `traducir` deciden su propio destino:
  `:497-499`, `:519-521`, `:586-588`.
- **Escenario:** en `traducir`, `destino` se calcula en `:294` y en `:295-296` se sobrescribe si el estado es
  `ALOJADO`. Para `IntegrantesView` (`estados` incluye `ALOJADO`) la segunda rama no hace nada. Para
  `_IngresoView` sí cambia el resultado. Ante el mismo `EstadoCambio(ALOJADO)`, `FichaIntegranteView._completar`
  manda a «Llegadas» (`:521`), `FichaIntegranteView.post` a «Integrantes» (`:499`) y `FamiliaAlojadaView` a
  «Llegadas» (`:588`). Hay tres respuestas distintas para el mismo estado nuevo. RU-20 pide «la pantalla que
  corresponde al estado nuevo».
- **Causa raíz:** no existe una función única `pantalla_para(estado, derivacion)`. Cada rama la recalcula.
- **Solución:** `_IngresoView.destino_para(estado_actual)` con una tabla explícita:
  `{INGRESO_EN_CURSO: integrantes, ALOJADO: integrantes, DERIVADO: llegadas?derivacion=…, *: llegadas}`.
  `ya_no`, `despues_de_un_cambio` y `traducir` la usan. Las tres vistas que hoy tienen su propio `try/except`
  pasan por `traducir` (ver E-LIM-14). Antes de unificar hay que fijar con tests el destino que tiene cada
  vista hoy, para no cambiar el comportamiento sin querer. Si el PM prefiere unificar los destinos:
  `DECISIÓN CLIENTE: ALOJADO → integrantes en todos los casos`.
- **Tests a agregar:** `programas/tests/test_emergencia_dispositivo_web.py::DestinoTrasCambioTest` parametrizado
  por vista × estado nuevo.
- **Verificación:** la tabla de destinos queda escrita una sola vez y los tests documentan cada fila.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md`: «Una variable que se asigna y en la línea
  siguiente se pisa con otro `if` es una tabla que falta».

---

### E-LIM-06 · Dos definiciones de «ingreso directo»: el modelo mira `situacion` y el tablero infiere por `tomado_en == creado`
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura); que diverjan en datos reales: PLAUSIBLE · **Eje:** LIM · **Origen:** nuevo · **Ola:** 4 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E3-LIM-06
- **Ubicación:** `programas/selectors/emergencia_tablero.py:147-155` (`FilaCaso.ingreso_directo`), usada en
  `:431` (tarjeta «ingresos directos») y `:613` (exclusión de tramos en tiempos).
  `programas/models/__init__.py:5921-5925` (`CasoEmergencia.es_ingreso_directo`). El docstring de
  `services/emergencia_sin_derivacion.py:200` dice: «la regla vive en el modelo».
- **Escenario:** el tablero cuenta «ingreso directo» con una marca de tiempo que depende de que
  `ingreso_directo()` guarde `tomado_en = creado` exacto. Una corrección de datos, un `restore` o un cambio que
  redondee `tomado_en` (o que lo setee con un segundo `now()`) hace que el tablero deje de contarlos, mientras
  la bandeja E2 (`emergencia_mesa.py:211`, `:493`) los sigue marcando. Además, «tiempos» empezaría a meter esos
  casos en los tramos tomar/derivar/aceptar con valor 0.
- **Causa raíz:** el tablero evita traer el JSON `situacion` por presupuesto de consultas. Para eso reinventó
  el predicado en lugar de llevarlo a SQL.
- **Solución:** en el modelo, `CasoEmergencia.q_ingreso_directo()` como hermano de `q_esperando_en_la_puerta`:
  `Q(origen=DISPOSITIVO) & ~Q(situacion__has_key=SITUACION_EN_LA_PUERTA)`. `has_key` anda en los tres motores.
  `_casos_de_la_ventana` lo anota (`ingreso_directo=ExpressionWrapper(Q(...), BooleanField())`) y `FilaCaso`
  lo recibe como campo. Se borra la propiedad inferida. Sigue siendo 1 consulta.
- **Lo que NO hay que hacer:** traer `situacion` en el `values_list` de cientos de casos (presupuesto de 7 consultas y read_timeout de ECOM).
- **Tests a agregar:** `programas/tests/test_emergencia_tablero.py::IngresoDirectoTest.test_coincide_con_el_modelo`
  con un caso directo cuyo `tomado_en` difiere de `creado` en 1 µs.
- **Verificación:** test anterior verde y `perf` del tablero sin cambios (`--tag performance`).
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md`: «Un predicado de dominio que el modelo ya
  define no se reinfiere desde columnas: si hace falta en SQL, se agrega `q_<predicado>()` al modelo».

---

### E-LIM-07 · La regla de plazas para derivar (RN-2.5) está escrita dos veces: en el panel y en `derivar_caso`
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** thermos E1 · **Ola:** 4 · **Esfuerzo:** S
- **ID de la pasada 1:** E1-LIM-03
- **Ubicación:** `programas/selectors/emergencia.py:491-496` (`_marca_de_plazas`) y `:531-533` (`libres = max(conteo.disponibles, 0)`). `programas/services/emergencia.py:534-538` repite lo mismo inline (`libres = max(...)`, `libres < 1` → sin plazas, `libres < plazas_pedidas` → `FaltanPlazas`).
- **Escenario:** si el PM pide que «sin plazas» se pueda derivar con confirmación, o que las reservadas cuenten distinto, hay que tocar dos lugares. Si se olvida uno, el panel ofrece «Derivar» y el servicio lo rechaza, o al revés. `acciones_posibles` existe para impedir exactamente ese desacople en los estados, pero no cubre las plazas.
- **Causa raíz:** el selector clasificó la marca para la pantalla y el servicio volvió a escribir la decisión en vez de consumir la clasificación.
- **Solución:** exponer en el selector (o en `emergencia_comun`) dos funciones puras: `plazas_libres(conteo) -> int` y `marca_de_plazas(libres, pedidas) -> (marca, faltan)`, que es la actual `_marca_de_plazas` pública. `derivar_caso` queda así:
  ```python
  libres = plazas_libres(ocupacion_de_plazas(dispositivo).de(dispositivo).conteo)
  marca, _ = marca_de_plazas(libres, plazas_pedidas)
  if marca == MARCA_SIN_PLAZAS: raise ValidationError({"dispositivo": SIN_PLAZAS})
  if marca == MARCA_FALTAN and not confirmar_faltantes: raise FaltanPlazas(libres=libres, pedidas=plazas_pedidas)
  ```
  Los mensajes y las excepciones son los mismos de hoy.
- **Tests a agregar:** `programas/tests/test_emergencia_casos.py::DerivarTests.test_panel_y_servicio_coinciden_en_la_marca` (parametrizado por libres 0, menor que pedidas y suficiente: el panel bloquea exactamente cuando el servicio rechaza).
- **Verificación:** ese test, más los de `FaltanPlazas` existentes.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` · «Si un selector clasifica algo para ofrecer o bloquear un botón, el servicio que decide la acción consume esa misma función; no reescribe la condición».

---

### E-LIM-08 · Reglas de dominio en `selectors/` y dependencia cruzada entre selectores y servicios
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** thermos E1 · **Ola:** 4 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E1-LIM-04
- **Ubicación:** `programas/selectors/emergencia.py:444-459` (`dispositivo_elegible`, «la única definición» de RN-2.2) consumida por `programas/services/emergencia.py:83,532` y por `emergencia_sin_derivacion`. `programas/selectors/emergencia.py:32-33` importa `services.emergencia_programa` y `services.ocupacion`. `programas/selectors/emergencia_mesa.py:27-39` importa `services.emergencia` (`acciones_posibles`, `ESTADOS_PARA_TOMAR`, tablas de presentación).
- **Escenario:** el servicio depende del selector para una regla de negocio y el *presenter* depende del servicio. Las capas de CLAUDE.md quedan en zigzag: services → selectors → services. Además, `selectors/emergencia.py` y `selectors/emergencia_mesa.py` levantan `PermissionDenied` (`:523`, `:646`) con un `SIN_PERMISO_DE_MESA` propio (ver LIM-08). Hay autorización repartida entre selector y servicio.
- **Causa raíz:** la regla nació donde primero se usó (el filtro del panel) y el servicio la importó de ahí.
- **Solución:** mover `dispositivo_elegible` a `programas/services/emergencia_comun.py`, o mejor a un método `Dispositivo.admite_derivacion_de_emergencia()` en el modelo. El selector la importa para filtrar `_dispositivos_elegibles` y el servicio deja de importar selectores. Reexportarla en `selectors.emergencia` por una release. Los dos `PermissionDenied` del selector se quedan: son el gate RU-14 documentado. Solo se unifica el mensaje (LIM-08).
- **Lo que NO hay que hacer:** pasar el filtro a SQL (`tipo.admite_tipo_de_plaza` lee JSON). Rompe la paridad MySQL/MariaDB/SQLite que el docstring defiende.
- **Tests a agregar:** `programas/tests/test_arquitectura.py::...::test_services_de_emergencia_no_importan_selectores` (con lista de excepciones vacía).
- **Verificación:** ese test, más los de `dispositivo_elegible` existentes.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md` · «Una regla de negocio que un servicio necesita no se define en `selectors/`; si el selector la usa para filtrar, la importa del servicio o del modelo».

---

### E-LIM-09 · «¿Ve quién ocupa la cama?» lo decide cada vista, dos veces, con la capacidad redeclarada
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** amplía E-LIM-27 (mismo patrón con `ciudadano.ver`) · **Ola:** 4 · **Esfuerzo:** S
- **ID de la pasada 1:** E4-LIM-04
- **Ubicación:** `programas/api/views_emergencia_llegadas.py:68`, `:525-527`; `programas/views/emergencia_dispositivo.py:64`,
  `:384-389`; `programas/services/estadias.py:130`; firma en `programas/selectors/emergencia_alojar.py:215`.
- **Escenario:** `plazas_para_caso(dispositivo, caso, usuario, *, puede_ver_personas=False)` recibe el **usuario** y
  además un booleano que cada llamador calcula con `rbac.puede(user, "ciudadano.ver")`. La API y el backoffice lo
  hacen igual hoy; un tercer llamador que olvide el kwarg muestra el mapa sin ocupantes en silencio, y uno que lo pase
  `True` sin chequear expone nombres. `CAP_VER_CIUDADANO = "ciudadano.ver"` está tres veces.
- **Causa raíz:** una decisión de autorización sobre datos personales quedó como parámetro opcional del selector en
  vez de resolverse donde ya está el usuario.
- **Solución:** que `plazas_para_caso` calcule `puede_ver_personas = rbac.puede(usuario, CAP_VER_CIUDADANO)` y retirar
  el kwarg (o dejarlo como override explícito solo para tests). Una sola constante, en `services/estadias.py` o en
  `core/rbac.py` si el catálogo expone códigos; las vistas la importan. Comportamiento idéntico.
- **Tests a agregar:** `programas/tests/test_emergencia_alojar.py::PlazasParaCasoTest.test_detalle_de_ocupante_solo_con_ciudadano_ver`
  (llamada sin kwarg, con y sin la capacidad).
- **Verificación:** `grep -rn 'CAP_VER_CIUDADANO = ' programas` = 1; `grep -n puede_ver_personas programas/api programas/views` vacío.
- **Regla para no repetirlo:** **skill** · `.claude/skills/seguridad-django/` · «Un selector que recibe `usuario` decide
  él mismo qué dato personal muestra: no recibir un booleano de permiso calculado por la vista.»

---

### E-LIM-10 · La guarda «el `?caso` tiene que estar derivado a este dispositivo» vive en la vista del mapa
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 4 · **Esfuerzo:** S
- **ID de la pasada 1:** E4-LIM-05
- **Ubicación:** `programas/api/views_emergencia_llegadas.py:513-528` (`PlazasDelDispositivoView.get`).
- **Escenario:** la vista parsea `?caso` (`isdecimal`, `int`), resuelve el ingreso con `self._ingreso` y compara
  `derivacion.dispositivo_id != dispositivo.pk` para dar 404. Es una regla de alcance de RU-9 (un caso de otro
  dispositivo no se nombra) escrita como `if` suelto en una vista HTTP, mientras `plazas_para_caso` ya «exige
  `dispositivo.admitir` sobre el dispositivo» (`selectors/emergencia_alojar.py:243`) pero no la pertenencia del caso.
  El backoffice llega a la misma garantía por otro camino (busca el caso filtrado por `self.dispositivo`), así que la
  regla tiene dos implementaciones distintas.
- **Causa raíz:** el selector acepta `(dispositivo, caso)` sin validar que se correspondan; cada vista lo compensa.
- **Solución:** mover el chequeo a una función del servicio ya dueña del concepto,
  `servicio_alojar.ingreso_en_dispositivo(caso_pk, dispositivo, usuario)` (envuelve `ingreso_sin_candado` + la
  comparación y lanza `PermissionDenied`), y usarla desde las dos vistas. El parseo de `?caso` puede ir a un
  `serializers.IntegerField(required=False, min_value=1)` de query (un `?caso=abc` sigue dando 404 si se mapea así).
- **Tests a agregar:** `programas/tests/test_emergencia_api_llegadas.py::PlazasTest.test_caso_de_otro_dispositivo_es_404` (ya
  debería existir; verificar por mutación: borrar el `if` y ver el test rojo).
- **Verificación:** la vista no compara `dispositivo_id`; tests de mapa en verde.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` · «Comparar ids de
  pertenencia (`x.dispositivo_id != y.pk`) en una vista es una regla de alcance fuera del servicio.»

---

### E-LIM-11 · La tarjeta de la derivación se proyecta dos veces: serializer de la API y selector del backoffice
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** relacionado con E-LIM-25 (formateadores) · **Ola:** 4 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E4-LIM-07
- **Ubicación:** `programas/api/serializers_emergencia.py:510-560` (`DerivacionLlegadaSerializer.get_vencida`,
  `get_derivada_por`, `get_necesidades`, `get_telefono`, `get_observaciones`); `programas/selectors/emergencia_llegadas.py:42-77`
  (`tarjeta_de_derivacion`).
- **Escenario:** las dos piezas calculan lo mismo desde la misma derivación: necesidades filtrando `NECESIDADES` por
  `caso.necesidades.get(clave)`, `caso.situacion.get("telefono", "")`, `caso.situacion.get("observaciones", "")`,
  `nombre_de(derivada_por)`, `derivacion_vencida(...)`. El backoffice pasa `ahora` fijo por request; el serializer usa
  `timezone.now()` por fila. Si `situacion` cambia de clave (p. ej. `telefono` pasa a `contacto.telefono`) hay que
  acordarse de dos lugares, y RU-1 (paridad app/web) depende de esa memoria.
- **Causa raíz:** no hay una proyección de datos planos de la derivación compartida; cada capa de presentación lee el
  JSON del caso por su cuenta.
- **Solución:** función pura en `selectors/emergencia_alojar.py` (que ya es «datos planos que comparte la API»):
  `datos_de_derivacion(derivacion, ahora) -> dict` con `necesidades` (claves), `telefono`, `observaciones`,
  `derivada_por`, `vencida`. `tarjeta_de_derivacion` la expande y suma rótulos/tonos; el serializer la usa vía
  `to_representation` o un `SerializerMethodField` único. Las claves del contrato no cambian.
- **Tests a agregar:** `programas/tests/test_emergencia_alojar.py::DatosDeDerivacionTest` (situación vacía, necesidades
  mixtas, vencida en el borde).
- **Verificación:** `grep -n 'situacion.get("telefono"' programas/` = 1 resultado (fuera de tests).
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` · «Paridad app/web
  (RU-1): lo que la API y el backoffice muestran del mismo objeto sale de una sola función de datos planos; el
  serializer y el selector de pantalla solo decoran.»

---

### E-LIM-12 · Cada endpoint repite a mano la traducción de errores: el protocolo `(resultado, respuesta)` deja 23 ramas `if respuesta is not None`
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 5 · **Esfuerzo:** M
- **ID de la pasada 1:** E4-LIM-01
- **Ubicación:** `programas/api/views_emergencia.py:248-279` (`_entrada`, `_ejecutar`), `:384-402`;
  `programas/api/views_emergencia_llegadas.py:118-141` (`_ingreso`, `_ingreso_para_leer`, `_caso_para_leer`),
  `:172-492` (todas las vistas); `views_emergencia_kits.py:158-174`; `views_emergencia_sin_derivacion.py:62-77`, `:113-128`.
- **Escenario:** el mapeo excepción de dominio → código del contrato (404/409/400/429) está centralizado en
  `_VistaDeCampo._ejecutar`, pero en forma de tupla `(resultado, respuesta)`. Cada vista tiene que desarmarla:
  `grep -c "respuesta is not None"` da 19 en `views_emergencia_llegadas.py`, 2 en `sin_derivacion`, 1 en `kits` y 1 en
  la base. Encima conviven **dos** formas de validar el cuerpo: `self._entrada(...)` (7 vistas) y el bloque manual
  `Serializer(data=…); if not is_valid(): return _respuesta_de_validacion(...)` (5 vistas: `views_emergencia.py:385`,
  `kits.py:160`, `sin_derivacion.py:64` y `:115`), porque `_entrada` devuelve `validated_data` y esas vistas necesitan
  el serializer (`datos_formulario1()`, `cantidades_por_item()`). Y hay **tres** variantes de la misma guarda de alcance
  por caso: `_ingreso` traduce `PermissionDenied`→`NotFound` a mano (`:125-128`, lo mismo que ya hace `_ejecutar`),
  `_ingreso_para_leer` lo envuelve en `_ejecutar`, y `_caso_para_leer` desarma la tupla de la anterior para quedarse con
  `[0]`. Un endpoint nuevo que olvide un `if respuesta is not None` devuelve `Response(Serializer(None))` con 200.
- **Causa raíz:** la traducción se diseñó como función que devuelve una respuesta en vez de usar el punto de extensión
  de DRF para eso (`APIView.handle_exception`), así que el control de flujo de error se propaga a mano por cada vista.
- **Solución (jugada de judo, sin cambiar contrato):**
  1. En `_VistaDeCampo`, sobreescribir `handle_exception(self, exc)` con la misma tabla que hoy tiene `_ejecutar`:
     `PermissionDenied` → `NotFound` (o la respuesta de `self.permiso_denegado`, atributo de clase que M1 setea a su 403),
     `EstadoCambio` → `_respuesta_409`, `UuidEnUso` → `_respuesta_uuid_en_uso`, `DniRegistrado` → descuento de cubeta +
     `Throttled` o `_respuesta_dni_registrado`, `ValidationError` de Django → `_respuesta_de_validacion(_errores(...))`;
     y `serializers.ValidationError` de DRF → `_respuesta_de_validacion(exc.detail)` (hoy lo hace `_entrada`). El resto,
     `super().handle_exception(exc)`.
  2. `_entrada(self, serializer_class)` pasa a devolver el **serializer validado** (`is_valid(raise_exception=True)`),
     con lo que desaparece el bloque manual de las 5 vistas.
  3. `_ingreso(request, pk, *estados)` queda una sola: llama a `ingreso_sin_candado` y deja que `PermissionDenied` /
     `EstadoCambio` suban. Se borran `_ingreso_para_leer` y `_caso_para_leer`.
  4. Cada vista queda lineal: `entrada = self._entrada(X)`; `resultado = servicio(...)`; `return Response(...)`.
  Se borran `_ejecutar`, el parámetro `sin_permiso` y ~70 líneas de ramas. Los cuerpos de 400/404/409/429 no cambian.
- **Lo que NO hay que hacer:** usar el `EXCEPTION_HANDLER` global de DRF en settings: cambiaría el 400 de Becas e
  Inspecciones. Tampoco convertir `EstadoCambio` en `APIException` dentro del servicio: el backoffice lo usa para
  redirigir (`views/emergencia_dispositivo.py`, RU-20).
- **Tests a agregar:** `programas/tests/test_emergencia_api_errores.py::TraduccionDeErroresTest` — un caso por
  excepción contra una vista de cada superficie (M1, M2, M3, M2-6), comparando el cuerpo byte a byte con el actual.
- **Verificación:** la suite de contrato `programas/tests/base_emergencia_api.py` y los tests de Emergencia en verde
  sin tocar expectativas; `grep -c "respuesta is not None" programas/api/views_emergencia*.py` = 0.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` (Helpers canónicos) ·
  «Traducir excepciones de dominio a HTTP en la API de campo: `handle_exception` de la vista base de la superficie.
  Una vista que desarma una tupla `(resultado, respuesta)` o hace `if not is_valid(): return …` es duplicado.»

---

### E-LIM-13 · Cada superficie de la API de campo reescribe su traductor de errores, y Emergencia depende de un privado de Inspecciones
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** fusión de E-LIM-13; relacionado con E-LIM-35 (dirección inversa del acople a `programas/api`) · **Ola:** 5 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E4-LIM-02 + E4-LIM-03
- **Ubicación:** `programas/api/views_emergencia.py:62` (`from programas.api.views_inspecciones import _respuesta_400`),
  `:176-186`, `:255-279`; `programas/api/views_inspecciones.py:99-139`; `programas/api/views.py:135-150` (`_error`,
  `_error_validacion` de Becas).
- **Escenario:** `views_inspecciones._ejecutar` (`:120-139`) y `views_emergencia._VistaDeCampo._ejecutar` tienen el
  mismo esqueleto (servicio → `PermissionDenied`→`NotFound`, `ValidationError`→400 con `detail` legible) y la misma
  expresión `error.message_dict if hasattr(error, "error_dict") else error.messages` (`views_inspecciones.py:139`,
  `views_emergencia.py:178`). El 400 «con `detail` legible y `code`» de Emergencia se arma importando un **privado**
  de Inspecciones y mutando su `.data`. Si Inspecciones cambia `_respuesta_400` (es suyo, con guion bajo), cambia el
  contrato de la app de Emergencia sin que nadie lo vea en el diff.
- **Causa raíz:** no existe un módulo compartido de respuestas de la API de campo; cada superficie nueva copió el
  patrón o lo tomó prestado de la anterior.
- **Solución:** crear `programas/api/respuestas.py` con nombres públicos: `respuesta_400(errores, code=None)`,
  `errores_de(django_validation_error)`, `respuesta_409(detail, **extra)`. `views_inspecciones` y `views_emergencia`
  importan de ahí; el cuerpo de cada superficie queda idéntico (Inspecciones sin `code`, Emergencia con
  `code: VALIDACION`). Con E-LIM-12 hecho, el `handle_exception` de cada superficie llama a estas funciones.
- **Lo que NO hay que hacer:** unificar también los `code` (`SIN_MODULO`, `VALIDACION`) de Becas: la app instalada los
  lee y Becas tiene sus propios textos por regex (`services/campo.py:78-86`).
- **Tests a agregar:** `programas/tests/test_api_respuestas.py::Respuesta400Test` (dict, lista, vacío, con y sin `code`).
- **Verificación:** `grep -rn "views_inspecciones import _" programas/` vacío; contratos de las tres superficies en verde.
- **Regla para no repetirlo:** **control mecánico** · ruff no lo cubre: test ratchet en `core/tests/` que falle si un
  módulo de `programas/api/` importa un nombre con `_` inicial de **otro** módulo de `programas/api/` (AST: `ImportFrom`
  con `module` en `programas.api.*` distinto del propio y algún `alias.name.startswith("_")`). Mensaje: «Importás un
  privado de otra superficie de la API: subilo a `programas/api/respuestas.py` o a la base de la superficie».

#### Aporte del segundo revisor (E4-LIM-03: Las bases de la API exportan su interfaz con nombres privados)
_Pasada 1: severidad BAJA · estado CONFIRMADO (lectura) · esfuerzo S._

- **Ubicación:** `programas/api/views_emergencia_llegadas.py:53-60`; `programas/api/views_emergencia_kits.py:24-31`;
  `programas/api/views_emergencia_sin_derivacion.py:20-28`.
- **Escenario:** `_VistaDeCampo`, `_VistaDeLlegadas`, `_respuesta_de_validacion`, `_creado_o_reenvio`, `_filas`, `_400`,
  `_SIN_TOKEN`, `_AJENO`, `_SIN_ADMITIR`, `_DNI_REGISTRADO` se importan entre módulos: el guion bajo ya no dice nada y
  nadie sabe qué se puede cambiar sin romper a otro archivo. El docstring de `views_emergencia.py:8-16` declara que es
  «la base que importan los otros», o sea, es API.
- **Solución:** `programas/api/emergencia_base.py` con los nombres públicos (la vista base, los permisos, las
  respuestas OpenAPI compartidas, `creado_o_reenvio`); `views_emergencia.py` queda solo con perfil/identidad/M1.
  Combina naturalmente con E-LIM-12 y E-LIM-13.
- **Verificación:** test ratchet de E-LIM-13 sin excepciones para Emergencia.
- **Regla para no repetirlo:** la de E-LIM-13.

---

### E-LIM-14 · La traducción de `EstadoCambio`/`ValidationError` está copiada nueve veces en dos archivos de vistas, con tres helpers locales duplicados
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — (mismo patrón que E-LIM-38 en la mesa) · **Ola:** 5 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E3-LIM-05
- **Ubicación:**
  - Escalera `try/except EstadoCambio/ValidationError`: `views/emergencia_dispositivo.py:213-220`, `:234-241`,
    `:488-502`, `:515-524`, `:584-591`, `:672-676`. `views/emergencia_kits.py:362-372`, `:481-488`, `:610-623`.
    `traducir` (`emergencia_dispositivo.py:287`) existe pero la usan solo 3 vistas.
  - Helpers copiados: `_errores_de` en `views/emergencia.py:75`, `views/emergencia_dispositivo.py:71` y
    `views/emergencia_kits.py:85`. `_url` (reverse + querystring) en `views/emergencia.py:63`,
    `views/emergencia_kits.py:77` y `GuardiaView.url` (`emergencia_dispositivo.py:101-104`). `_mensajes`
    (`emergencia_dispositivo.py:75`) frente a `" ".join(error.messages)` inline en `emergencia_kits.py:487`.
- **Escenario:** si mañana `EstadoCambio` tiene que mostrar también quién se adelantó (RU-20), hay nueve
  lugares que tocar y no hay ninguno canónico.
- **Causa raíz:** cada etapa armó su base de vistas. No hay un `views/emergencia_comun.py`.
- **Solución:** `programas/views/emergencia_comun.py` con `url_con_parametros`, `errores_en_una_linea(form)`,
  `mensajes_de(error)` y `ejecutar_servicio(request, accion, *, al_cambiar, al_rechazar, form=None)`. Esta
  última devuelve `(resultado, respuesta)` como `traducir`: con `form`, el `ValidationError` va a
  `form.agregar_errores_del_servicio` y si no, a `messages.error`. Las nueve escaleras pasan a una llamada. Los
  destinos los da E-LIM-05 (dispositivo) o el `_destino` actual (kits).
- **Lo que NO hay que hacer:** atrapar `PermissionDenied`. Hoy sube como 403 a propósito (docstring
  `emergencia_kits.py:8`).
- **Tests a agregar:** los existentes alcanzan. Se suma `programas/tests/test_emergencia_comun_vistas.py`
  para el helper aislado.
- **Verificación:** `grep -c "except EstadoCambio" programas/views/emergencia_*.py` cae de 9 a 0 (queda 1 en el helper).
- **Regla para no repetirlo:** **control mecánico** · test ratchet que cuenta `def _errores_de` y `def _url(` en
  `programas/views/` y falla si pasan de 0 fuera de `emergencia_comun.py`.

---

### E-LIM-15 · La orquestación de candados del ingreso está copiada tres veces
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 6 · **Esfuerzo:** M
- **ID de la pasada 1:** E2-LIM-01
- **Ubicación:**
  - `programas/services/emergencia_confirmacion.py:261-306` (`_ingresar_en_cama_libre`)
  - `programas/services/reservas_derivacion.py:241-286` (`consumir_reserva_de_derivacion`)
  - `programas/services/ingreso.py:213-251` (`confirmar_ingreso`, contexto). Es la versión canónica.
- **Escenario:** las tres funciones repiten la misma secuencia. (1) Leen `_reservas_abiertas_de(ciudadano)`.
  (2) Bloquean de una vez, ordenadas por pk, la plaza del ingreso más las plazas de las reservas que van a
  liberar (`list(Plaza.objects.select_for_update()…order_by("pk").values_list("pk", flat=True))`).
  (3) Liberan cada reserva con `liberar_reserva(…, verificar_alcance=False)` y la cláusula
  `except ValidationError: continue`. (4) Llaman a `_bloquear_persona`. (5) Vuelven a leer
  `_reservas_abiertas_de` y lanzan `RESERVA_NUEVA_DURANTE_EL_INGRESO`. (6) Terminan en `ingresar_persona`.
  Cualquier cambio en esa secuencia tiene que repetirse a mano en los tres lugares. Por ejemplo, la decisión
  D2 del Cambio 409, el orden plaza → reserva → persona o la excepción de `ERROR 1213` documentada en
  `emergencia_alojar.py:90-97`. Si una copia diverge, el resultado es un deadlock o una reserva que queda
  tomando plaza de alguien que ya está alojado, y ningún test lo cubre de forma transversal.
- **Causa raíz:** cuando Emergencia necesitó variantes (la reserva sobrante de la familia o la reasignación de
  la reserva de derivación), la secuencia se copió en vez de convertir `confirmar_ingreso` en un núcleo con
  puntos de extensión. Las tres copias se diferencian solo en **qué reservas extra se liberan** y en **qué se
  hace entre el bloqueo de la persona y el ingreso**.
- **Solución (jugada de judo):** dejar un único núcleo en `ingreso.py`, que es el módulo dueño de D2:
  ```python
  def ingresar_cerrando_reservas(*, ciudadano, dispositivo, usuario, plaza, propia=None,
                                 extra=(),            # [(reserva, motivo, verificar_alcance)]
                                 plazas_extra=(),     # pks que deben quedar bloqueados en el mismo lote
                                 antes_de_ingresar=None, fecha_ingreso=None):
      comunes = [r for r in _reservas_abiertas_de(ciudadano.pk) if propia is None or r.pk != propia.pk]
      a_liberar = [*extra, *((r, MOTIVO_RESERVA_CERRADA_POR_INGRESO, False) for r in comunes)]
      _bloquear_plazas_por_pk({plaza.pk if plaza else None, *plazas_extra, *(r.plaza_id for r, _, _ in a_liberar)} - {None})
      liberadas = {r.pk for r, motivo, alcance in a_liberar if _liberar_si_sigue(r, usuario, motivo, alcance)}
      _bloquear_persona(ciudadano)
      if any(propia is None or r.pk != propia.pk for r in _reservas_abiertas_de(ciudadano.pk)):
          raise ValidationError(RESERVA_NUEVA_DURANTE_EL_INGRESO)
      if antes_de_ingresar: propia = antes_de_ingresar() or propia
      return ingresar_persona(ciudadano=ciudadano, dispositivo=dispositivo, usuario=usuario,
                              plaza=plaza, fecha_ingreso=fecha_ingreso, reserva=propia), liberadas
  ```
  - `confirmar_ingreso` pasa a ser una llamada directa al núcleo.
  - `_ingresar_en_cama_libre` pasa `extra=[(sobrante, MOTIVO_RESERVA_SOBRANTE, True)]` y lee
    `reserva_liberada = sobrante.pk in liberadas`.
  - `consumir_reserva_de_derivacion` pasa `plazas_extra=[fila[0]]`, conserva el bloqueo de la reserva de
    derivación y su guarda del MAJOR 1 de #802 **antes** de llamar al núcleo, y mueve la reasignación de
    `ciudadano` a `antes_de_ingresar`. El orden de candados queda igual en los tres caminos.
  - `_bloquear_plazas_por_pk` y `_liberar_si_sigue` (el `try/except ValidationError: continue`) cubren
    también `liberar_reservas_de_derivacion` (`reservas_derivacion.py:321-337`), que repite el mismo patrón.
- **Lo que NO hay que hacer:** no mover el bloqueo de la reserva de derivación a **después** de la persona.
  El docstring de `reservas_derivacion.py:51-56` explica el deadlock que se forma al subir el lock compartido
  a exclusivo. Tampoco hay que unificar en una sola lectura `comunes` y la reserva sobrante, porque llevan
  alcance distinto (`verificar_alcance=True` en la sobrante).
- **Tests a agregar:** `programas/tests/test_ingreso_cerrando_reservas.py::NucleoIngresoTest.test_orden_de_candados_plaza_reserva_persona`
  (con `CaptureQueriesContext`: el `FOR UPDATE` de plazas va antes que el de reservas, y este antes que el de
  `legajos_ciudadano`), y `…::test_las_tres_entradas_cierran_las_comunes`. Además deben seguir en verde
  `test_emergencia_alojar`, `test_reservas_derivacion` y `test_ingreso`.
- **Verificación:** `grep -n "_bloquear_persona(" programas/services` devuelve una sola llamada fuera de
  `ingreso.py`, o ninguna. La suite de Dispositivos y la de Emergencia quedan en verde.
- **Regla para no repetirlo:** **control mecánico** · `programas/tests/test_arquitectura.py` · un test
  `test_bloquear_persona_tiene_un_solo_llamador` que recorra con `ast` los `programas/services/*.py` y falle
  si `_bloquear_persona` se llama fuera de `ingreso.py`. Mensaje: «La secuencia de ingreso con reservas vive
  en `ingreso.ingresar_cerrando_reservas`; no se copia.»

---

### E-LIM-16 · `alojar_familia` y `cerrar_con_diferencia` son dos copias del mismo cierre y cuentan distinto
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 6 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E2-LIM-02
- **Ubicación:** `programas/services/emergencia_cierre.py:127-180` y `:211-262`. Relacionado: `:292-298`
  (`cancelar_ingreso`).
- **Escenario:** las dos funciones ejecutan la misma secuencia: `_abrir_ingreso`, después
  `dispositivo = derivacion.dispositivo` y `grupo = caso.grupo`, contar confirmadas, preguntar
  `acciones_del_ingreso`, `liberar_reservas_de_derivacion`, `estado = ALOJADO`, `marcar("alojado_en")`,
  `total_alojado = confirmadas`, mezclar `situacion`, guardar los **mismos** `update_fields`,
  `_trazar`, `_anotar_en_bitacora`, `caso.reservas_liberadas = …` y `_cerrar_si_no_queda_nadie`. Sin
  embargo, calculan los insumos de la regla con **dos fórmulas distintas**:
  - `alojar_familia`: `confirmadas = _confirmadas(_filas_de(grupo))` y
    `total = max(grupo.total_declarado, len(filas))` (`:130-131`);
  - `cerrar_con_diferencia` y `cancelar_ingreso`: `IntegranteGrupo…filter(confirmada_en__isnull=False).count()`
    y `total = grupo.total_declarado` (`:214-215`, `:294-295`).

  Si alguna vez hay más filas que `total_declarado`, «alojar» y «diferencia» dejan de ser complementarios:
  la pantalla, que lee `acciones_del_ingreso`, ofrece un botón y el servicio lo rechaza.
- **Causa raíz:** el cierre se resolvió con una función por botón. No existe un «cierre a ALOJADO» con dos
  variantes de datos.
- **Solución:** un helper privado
  `_cerrar_a_alojado(ingreso, usuario, *, clave_situacion, situacion, motivo_liberar, accion, detalle, texto_bitacora)`
  con el cuerpo común, y una sola lectura de `confirmadas` y `total` para los tres cierres (ver E-LIM-18):
  `filas = _filas_de(grupo); confirmadas = _confirmadas(filas); total = max(grupo.total_declarado, len(filas))`.
  Las dos funciones públicas se quedan solo con su validación de entrada y sus textos.
  **Preserva la lógica:** antes de unificar la fórmula de `total`, hay que confirmar con un test que
  `len(filas) <= total_declarado` siempre se cumple (`_asegurar_filas` y `agregar_integrante` lo mantienen).
  Si el test no lo confirma, se pasa `total` como parámetro para conservar cada variante.
- **Lo que NO hay que hacer:** fusionar las dos funciones públicas en una con un flag `con_diferencia`. La API y
  la vista E6 las llaman por separado, y un modo booleano es justamente el espagueti que la rúbrica prohíbe.
- **Tests a agregar:** `programas/tests/test_emergencia_alojar.py::CierreTest.test_alojar_y_diferencia_son_complementarios`
  (recorre `confirmadas` de 0 a N y verifica que exactamente una de `alojar`, `diferencia` o `cancelar` es verdadera).
- **Verificación:** la suite `test_emergencia_alojar` queda en verde y `emergencia_cierre.py` baja unas 40 líneas.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` · «Dos servicios que
  terminan en el mismo estado con el mismo `update_fields` comparten un helper de transición; los insumos de una
  regla de botones (`acciones_*`) se calculan en un solo lugar.»

---

### E-LIM-17 · Las transiciones de caso y de derivación se escriben a mano en cada servicio
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 6 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E2-LIM-03
- **Ubicación:**
  - «Responder» la derivación: `emergencia_recepcion.py:253-256` (aceptar), `:318-323` (rechazar),
    `emergencia_cierre.py:303-307` (cancelar) y `emergencia_sin_derivacion.py:117-127` (nace ya respondida).
  - Transición del caso: `emergencia_recepcion.py:261-263`, `emergencia_cierre.py:60-63`, `:153-167` y
    `:228-241`, `emergencia_sin_derivacion.py:132-135`, `emergencia_ingreso_comun.py:303-304`.
- **Escenario:** cada acción repite `derivacion.estado = X; derivacion.respondida_por = usuario;
  derivacion.respondida_en = now; derivacion.save(update_fields=[…])` y
  `caso.estado = Y; caso.marcar(…); caso.save(update_fields=[…])`, con listas de `update_fields` escritas a
  mano. Si se agrega un campo a «responder», por ejemplo `respondida_desde`, hay que tocar cuatro servicios.
  Un `update_fields` incompleto no da error: el dato se pierde en silencio. `rechazar_derivacion` y
  `cancelar_ingreso` son además el mismo cierre («derivación RECHAZADA con motivo + `_devolver_a_la_mesa` +
  traza») con dos textos distintos.
- **Causa raíz:** el modelo no expone las transiciones. Ya existe `CasoEmergencia.marcar` para las marcas del
  SLA, pero no hay un equivalente para el cambio de estado.
- **Solución:**
  - `Derivacion.responder(self, estado, usuario, momento, *, motivo=None, observacion=None)`: asigna los campos
    y guarda con el `update_fields` que corresponde.
  - En `emergencia_ingreso_comun`, `_pasar_caso(caso, estado, *, marcas=(), momento, **campos)`: asigna,
    llama a `marcar` por cada marca y guarda `["estado", *marcas, *campos, "modificado"]`.
  - `_devolver_a_la_mesa` pasa a usar `_pasar_caso`.
  - `rechazar_derivacion` y `cancelar_ingreso` comparten `_rechazar_y_devolver(caso, derivacion, usuario, motivo, observacion, accion, detalle)`.

  Los estados, las marcas y los textos no cambian.
- **Lo que NO hay que hacer:** meter una librería de máquina de estados (django-fsm) ni validar las
  transiciones dentro del modelo. Las guardas de estado siguen en `_abrir_ingreso` y `_exigir_pendiente`, que
  ya leen con candado.
- **Tests a agregar:** `programas/tests/test_emergencia_alojar.py::TransicionesTest.test_responder_guarda_todos_los_campos`.
- **Verificación:** `grep -n "respondida_en = " programas/services/emergencia_*.py` sin resultados.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` · «Un cambio de
  estado que se repite en 2 o más servicios vive en un método del modelo o en un helper `_pasar_*`, con su
  `update_fields` en un solo lugar.»

---

### E-LIM-18 · Seis módulos y una fachada para un único flujo, unidos por ~20 helpers con nombre privado
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 6 · **Esfuerzo:** M
- **ID de la pasada 1:** E2-LIM-04
- **Ubicación:**
  - `programas/services/emergencia_ingreso_comun.py:13-305`, que exporta `_abrir_ingreso`, `_filas_de`,
    `_confirmadas`, `_anotar_en_bitacora`, `_reservar_camas`, `_resumen_de_reservas`, `_dia_y_mes`, `_camas`,
    `_devolver_a_la_mesa`, `_exigir_alcance`, `_dispositivo_de`, `_bloquear_derivacion` y `_por_que_ya_no`.
  - Los consumidores: `emergencia_recepcion.py:24-39` (13 privados), `emergencia_cierre.py:22-32`,
    `emergencia_confirmacion.py:37-44` y `emergencia_sin_derivacion.py:23-32`.
  - El contrato está en el docstring de la fachada, `emergencia_alojar.py:1-106`.
- **Escenario:** para entender «confirmar a una persona» hay que abrir `emergencia_alojar`, que tiene el
  contrato de candados (100 líneas de prosa), `emergencia_ingreso_comun`, que tiene la guarda y los candados,
  `emergencia_confirmacion`, `reservas_derivacion` e `ingreso`. El prefijo `_` no significa nada: los nombres
  «privados» de `ingreso_comun` son la API real entre hermanos, y nadie puede saber cuáles se pueden cambiar
  sin romper otro módulo. Las acciones sobre un ingreso abierto repiten el preámbulo
  `caso, derivacion = _abrir_ingreso(…); dispositivo = derivacion.dispositivo; grupo = caso.grupo;
  filas = _filas_de(grupo)` (`emergencia_cierre.py:127-130`, `:211-213`, `:292-293`;
  `emergencia_confirmacion.py:357-360`, `:529-532`).
- **Causa raíz:** el archivo se partió por **botón** (recepción, confirmación, cierre) y no por **concepto**.
  El concepto que comparten todos es «un ingreso abierto con candado», y ese concepto no tiene tipo propio.
- **Solución (jugada de judo):**
  1. `_abrir_ingreso` devuelve un `IngresoAbierto` (dataclass frozen con `caso`, `derivacion`, `dispositivo`
     y `grupo`, y `filas` y `confirmadas` como `cached_property`) con los métodos `trazar(accion, detalle)`,
     `anotar(texto, momento)` y `acciones()`, este último sobre `acciones_del_ingreso`. Así desaparecen el
     preámbulo repetido y la mitad de los imports privados.
  2. Pasar a nombres públicos del módulo (sin `_`) lo que `ingreso_comun` exporta a sus hermanos, y declararlo
     en `__all__`. Lo que queda con `_` es privado de verdad.
  3. Mover el contrato de candados del docstring de la fachada al de `emergencia_ingreso_comun`, que es donde
     vive el código que lo aplica. La fachada queda como un índice corto (ver E-LIM-36).

  No hay que volver a juntar los archivos: los tamaños son sanos. El problema es el pegamento entre ellos,
  no la partición.
- **Lo que NO hay que hacer:** juntar los seis módulos en un `emergencia_alojar.py` de ~1900 líneas. Eso
  rompe la regla de 1k y no simplifica nada.
- **Tests a agregar:** `programas/tests/test_arquitectura.py::EmergenciaAlojarTest.test_hermanos_no_importan_privados_de_ingreso_comun`.
- **Verificación:** con `ast`, ningún `ImportFrom` de `emergencia_ingreso_comun`
  con un nombre que empiece por `_`.
- **Regla para no repetirlo:** **control mecánico** · `programas/tests/test_arquitectura.py` · un ratchet
  `test_no_crecen_los_imports_de_privados_entre_modulos`: con `ast`, recorre `programas/services` y cuenta los
  `ImportFrom` cuyo nombre empieza por `_` y viene de otro módulo. El test falla si el conjunto crece respecto
  de una lista congelada (cubre también E-LIM-19).

---

### E-LIM-19 · El contrato entre Dispositivos y Emergencia se apoya en helpers privados importados entre módulos
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 6 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E2-LIM-06
- **Ubicación:**
  - `programas/services/reservas_derivacion.py:76-92`: `_bloquear_plaza`, `_crear_reserva`,
    `_exigir_desde_no_futuro` y `_exigir_plaza_libre` de `estadias`; `_bloquear_persona` y
    `_reservas_abiertas_de` de `ingreso`.
  - `programas/services/emergencia_confirmacion.py:24,32,46-53`: `_como_uuid` de `emergencia_alta`,
    `_claves_de_envio` de `emergencia_ficha`, y `_bloquear_persona` y `_reservas_abiertas_de` de `ingreso`.
  - `programas/services/emergencia_sin_derivacion.py:21`: `_caso_de_ese_envio` y `_como_uuid` de `emergencia`.
  - `emergencia_recepcion.py:23`, `emergencia_cierre.py:21` y `emergencia_ingreso_comun.py:27`: `_bloquear_caso`,
    `_trazar`, `_hora` y `_nombre_de` de `emergencia_comun`.
- **Escenario:** quien mantiene `estadias.py` lee `_exigir_plaza_libre` como privado y lo cambia pensando que
  solo lo usa su propio módulo. Ese cambio rompe la reserva de derivación de Emergencia, que es otro producto.
  `_como_uuid` entra por **dos rutas** en dos módulos hermanos (`emergencia_alta` en confirmación y
  `emergencia` en sin_derivacion). En el repo hay además tres definiciones: `emergencia_alta.py:372`,
  `kits.py:209` e `inspecciones.py:515`.
- **Causa raíz:** cuando Emergencia empezó a reutilizar el núcleo de Dispositivos (bien hecho), no se promovió a
  API pública lo que se reutilizaba.
- **Solución:**
  - En `estadias.py` e `ingreso.py`, renombrar a públicos los helpers que usa otro módulo
    (`bloquear_plaza`, `crear_reserva`, `exigir_plaza_libre`, `exigir_desde_no_futuro`, `bloquear_persona`,
    `reservas_abiertas_de`). Durante una release se deja el alias `_x = x` para no romper los parches de los
    tests.
  - Llevar `_como_uuid` a un único canónico (`core/uuid.py::como_uuid`, o el de `emergencia_alta`) e importarlo
    siempre desde ahí.
  - `emergencia_comun` ya funciona como API compartida, así que sus nombres pasan a públicos.

  Es un cambio solo de nombres: el comportamiento no cambia.
- **Lo que NO hay que hacer:** copiar los helpers dentro de `reservas_derivacion` para «no depender de privados».
  Eso duplicaría las reglas de plaza, que es lo que hoy está bien reutilizado.
- **Tests a agregar:** el ratchet de E-LIM-18.
- **Verificación:** `grep -rn "def _como_uuid" programas` devuelve 0 resultados (o 1 si el canónico queda con
  `_`), y el ratchet de privados queda en verde con la lista reducida.
- **Regla para no repetirlo:** **control mecánico** · `pyproject.toml` · activar la regla de ruff `PLC2701`
  (import-private-name, preview) con `per-file-ignores` congelado para lo existente. Si preview no es viable,
  usar el ratchet `ast` de E-LIM-18.

---

### E-LIM-20 · Los servicios devuelven datos colgando atributos sueltos en instancias de modelo
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 6 · **Esfuerzo:** M
- **ID de la pasada 1:** E2-LIM-07
- **Ubicación:**
  - `programas/services/emergencia_confirmacion.py:368-370`, `:467-469`, `:536` y `:556`
    (`ya_estaba`, `confirmadas`, `total_declarado`, `reserva_liberada`).
  - `programas/services/emergencia_cierre.py:178`, `:260` y `:316` (`caso.reservas_liberadas`).
  - `programas/services/emergencia_sin_derivacion.py:67` y `:151-152` (`ya_existia`, `reservadas`, `faltantes`).
- **Escenario:** el mismo módulo de etapa devuelve resultados con **dos convenciones**. `emergencia_recepcion`
  usa dataclasses tipadas (`ResultadoBusqueda` y `ResultadoAceptacion`, `:68-111`). El resto le cuelga atributos
  a un `IntegranteGrupo` o a un `CasoEmergencia`. Ningún tipo dice qué atributos trae cada camino:
  - el reenvío idempotente de `agregar_integrante` (`:536`) devuelve `ya_estaba` y `total_declarado`, pero no
    `confirmadas` ni `reserva_liberada`;
  - `confirmar_integrante` devuelve los cuatro.

  Un serializer que lee `integrante.confirmadas` en el camino de `agregar` da `AttributeError` solo en el
  reintento.
- **Causa raíz:** se reutiliza la fila del ORM como objeto de respuesta para no crear un tipo.
- **Solución:** crear `ResultadoConfirmacion(integrante, ya_estaba, confirmadas, total_declarado, reserva_liberada)`,
  `ResultadoCierre(caso, reservas_liberadas)` y `ResultadoIngresoDirecto(caso, ya_existia, reservadas, faltantes)`
  como dataclasses frozen, igual que en recepción. Los callers (`views/emergencia_dispositivo.py`,
  `api/views_emergencia_llegadas.py`, `api/views_emergencia_sin_derivacion.py`) leen `resultado.x` en vez de
  `instancia.x`. Durante la transición se pueden mantener los atributos colgados.
- **Lo que NO hay que hacer:** agregar esos campos como `@property` del modelo. Son datos de una respuesta, no
  del dominio.
- **Tests a agregar:** `programas/tests/test_emergencia_alojar.py::ContratoTest.test_agregar_reenviado_devuelve_el_mismo_tipo`.
- **Verificación:** `grep -n "\.ya_estaba = \|\.reservas_liberadas = \|\.ya_existia = " programas/services/emergencia_*.py`
  sin resultados.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` · «Un servicio que
  devuelve más que la fila devuelve un dataclass `Resultado*`; no se cuelgan atributos a instancias del ORM.»

---

### E-LIM-21 · El mapa de Emergencia traduce el estado de una cama comparando rótulos de pantalla
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 6 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E2-LIM-08
- **Ubicación:** `programas/selectors/emergencia_alojar.py:262-275`. Contexto: `programas/services/ocupacion.py:459-463`
  y `:477-496`.
- **Escenario:** `plazas_para_caso` decide el código del contrato de la app (`LIBRE`, `OCUPADA`,
  `FUERA_SERVICIO`) comparando `derivado.estado` con `ESTADO_FUERA_SERVICIO = "Fuera de serv."`,
  `ESTADO_OCUPADA = "Ocupada"` y `ESTADO_DISPONIBLE = "Disponible"`, que son **textos de leyenda**. Por ejemplo,
  si alguien cambia el rótulo a «Fuera de servicio» en la leyenda pero no en la constante, la cama no coincide
  con ninguna rama y cae en el `else`. La app la recibe como `RESERVADA` y no como `FUERA_SERVICIO`, sin ningún
  error. `EstadoPlaza.disponible` (`ocupacion.py:494-496`) también se define por igualdad de texto.
- **Causa raíz:** `EstadoPlaza` solo tiene el texto que se muestra. No tiene un código estable.
- **Solución:** agregar a `EstadoPlaza` un `codigo` (TextChoices `CodigoPlaza.DISPONIBLE/OCUPADA/RESERVADA/PRESTADA/FUERA_SERVICIO`)
  que `estado_de_plazas` llena junto con el texto, y hacer que el selector traduzca con un diccionario
  `{CodigoPlaza.X: PLAZA_X}` en vez de la cadena de `if`. La reserva de la familia queda como un caso aparte
  por `derivacion_id`. Los rótulos y los tonos no cambian.
- **Lo que NO hay que hacer:** reemplazar los rótulos por los códigos en las pantallas de Dispositivos. Eso es
  un cambio visual.
- **Tests a agregar:** `programas/tests/test_emergencia_alojar.py::MapaTest.test_cada_codigo_de_ocupacion_tiene_traduccion`
  (itera `CodigoPlaza` y verifica que ninguno cae en el default).
- **Verificación:** `grep -n "== ESTADO_" programas/selectors/emergencia_alojar.py` sin resultados.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` · «Ninguna rama de
  lógica compara un texto de pantalla: el estado viaja con un código (TextChoices) y el rótulo se deriva.»

---

### E-LIM-22 · El ejecutor «una transacción por fila, falla al final» lo promete `core` y lo implementa Emergencia
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 6 · **Esfuerzo:** S
- **ID de la pasada 1:** E3-LIM-07
- **Ubicación:** `core/services/vencimientos.py:54-60` (docstring de `transaccion_unica=False`: «`aplicar` abre
  una por fila… la regla levanta al final») frente a `programas/services/vencimientos_emergencia.py:54-94`
  (`VencimientoConFallas`, `_aplicar_una_por_una`). El comando (`core/management/commands/procesar_vencimientos.py:66-80`)
  depende de ese comportamiento.
- **Escenario:** la próxima regla con `transaccion_unica=False` (el docstring nombra a Legajos) tiene que
  copiar `_aplicar_una_por_una` o importar un privado de Emergencia. Si no lo hace, una fila fallida o no
  pone el cron en rojo o frena a las demás, y se rompe OPS-07.
- **Causa raíz:** el contrato quedó en core y la implementación en la primera app que lo necesitó.
- **Solución:** mover `VencimientoConFallas` y `aplicar_una_por_una(qs, transicion, que, logger)` a
  `core/services/vencimientos.py`. Una variante más simple: `ReglaVencimiento` acepta `transicion` (por fila) en
  lugar de `aplicar` cuando `transaccion_unica=False`, y el comando hace el recorrido. Emergencia queda con dos
  `ReglaVencimiento(..., transicion=servicio.vencer_derivacion)` y se borran unas 40 líneas.
- **Tests a agregar:** `core/tests/test_vencimientos.py::PorFilaTest.test_falla_una_y_sigue_y_termina_en_rojo`.
- **Verificación:** los tests de `vencimientos_emergencia` existentes, sin cambios de comportamiento.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md`: «Si un docstring de `core` describe un
  comportamiento que implementa una app, el helper va a `core`».

---

### E-LIM-23 · `EstadoCambio` vive en el módulo de la mesa y obliga a E3 y a kits a importar toda la etapa 2
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** thermos E1 · **Ola:** 6 · **Esfuerzo:** S
- **ID de la pasada 1:** E1-LIM-01
- **Ubicación:** `programas/services/emergencia.py:185` (`EstadoCambio`), `:204` (`CasoTomadoPorOtro`). Lo importan desde la fachada: `programas/services/emergencia_ingreso_comun.py:26`, `emergencia_confirmacion.py:23`, `emergencia_recepcion.py:22`, `kits.py:69`, `views/emergencia_dispositivo.py:61`, `views/emergencia_kits.py:55`.
- **Escenario:** `emergencia_ingreso_comun`, que según su docstring es la hoja compartida de la etapa 3, importa `programas.services.emergencia`. Ese módulo arrastra `emergencia_alta`, `selectors.emergencia`, `ocupacion`, `configuracion_emergencia` y `emergencia_programa`. Para levantar una excepción, la etapa 3 y kits dependen de todo el servicio de la mesa. El grafo que vigila `test_arquitectura` queda más denso de lo necesario, y cualquier import nuevo de `emergencia` hacia E3 cierra un ciclo.
- **Causa raíz:** cuando se extrajo `emergencia_comun` se movieron la traza, el numerador y el candado, pero no el contrato de error que comparten todos los caminos.
- **Solución:** mover `EstadoCambio` y `CasoTomadoPorOtro` a `programas/services/emergencia_comun.py`. Ya tiene `_nombre_de`, la única dependencia de `CasoTomadoPorOtro`. `emergencia.py` las sigue reexportando, así que quien las atrapa por `servicio.EstadoCambio` no cambia. Los seis importadores pasan a `from programas.services.emergencia_comun import EstadoCambio`. La jerarquía de clases, los mensajes y el 409 quedan iguales.
- **Lo que NO hay que hacer:** crear un `excepciones.py` nuevo para una sola clase. `comun` ya existe para esto.
- **Tests a agregar:** `programas/tests/test_arquitectura.py::...::test_la_etapa3_no_importa_el_servicio_de_la_mesa` (ningún `emergencia_{ingreso_comun,confirmacion,recepcion,cierre,sin_derivacion}` ni `kits` importa `programas.services.emergencia`).
- **Verificación:** ese test, más `manage.py test programas.tests.test_emergencia_casos programas.tests.test_arquitectura` en verde.
- **Regla para no repetirlo:** **control mecánico** · `programas/tests/test_arquitectura.py` · «los módulos `services/emergencia_*` de etapas posteriores importan de `emergencia_comun` / `emergencia_ingreso_comun`, nunca de la fachada `emergencia`».

---

### E-LIM-24 · La fachada `services/emergencia.py` reexporta helpers privados y otros módulos los consumen como API
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** thermos E1 · **Ola:** 6 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E1-LIM-02
- **Ubicación:** `programas/services/emergencia.py:88-112` (reexporta `_caso_de_ese_envio`, `_como_uuid`, `_bloquear_caso`, `_bloquear_numerador`, `_exigir_mesa`, `_hora`, `_nombre_de`, `_trazar` con `# noqa: F401`). Consumidores: `programas/services/emergencia_sin_derivacion.py:21` (`_caso_de_ese_envio`, `_como_uuid`, por la fachada), `programas/services/kits.py:69` (`siguiente_correlativo`, por la fachada), `programas/services/emergencia_ingreso_comun.py:27` (`_bloquear_caso`, `_hora` desde `comun`).
- **Escenario:** la idempotencia por `uuid_cliente` del ingreso directo depende de dos funciones con guion bajo que viven en `emergencia_alta` y se toman por un tercer módulo. Si alguien renombra o cambia `_como_uuid` creyéndola privada, rompe el ingreso sin derivación. Ruff no avisa, por el `noqa`. Una parte del muro de reexports existe solo para que los tests puedan parchear por la ruta vieja.
- **Causa raíz:** se partió el módulo en tres archivos sin decidir qué es API pública. La fachada lo tapó reexportando todo.
- **Solución:** (1) Renombrar a público lo que otro módulo consume: `caso_de_ese_envio`, `como_uuid`, `bloquear_caso`, `trazar`, `exigir_mesa`, dejando el alias privado por una release. (2) Cada consumidor importa del módulo dueño (`emergencia_alta`, `emergencia_comun`). (3) En `emergencia.py`, dejar en la fachada solo lo público que usan la API y las vistas (`crear_caso`, `NECESIDADES`, `UuidEnUso`, `MOTIVOS_DE_CIERRE_MANUAL`…) con un `__all__` explícito, y sacar los privados. (4) Los tests que parchean `programas.services.emergencia._x` pasan a parchear la ruta del dueño. Ningún comportamiento cambia.
- **Lo que NO hay que hacer:** sacar la fachada entera de una vez. La API (`api/views_emergencia.py:65`) y `vencimientos_emergencia.py:48` la usan legítimamente.
- **Tests a agregar:** `programas/tests/test_arquitectura.py::...::test_nadie_importa_privados_de_otro_modulo_de_emergencia` (regex `from programas\.services\.emergencia\w* import .*\b_[a-z]` fuera del propio paquete de tests).
- **Verificación:** ese test, más ruff sin `F401` silenciados en `services/emergencia.py`.
- **Regla para no repetirlo:** **control mecánico** · `test_arquitectura.py` · «un nombre con `_` no se importa desde otro módulo de `programas/services`; si hace falta afuera, es público y vive en su dueño».

---

### E-LIM-25 · Formateadores de texto copiados en cinco o más módulos, con variantes que divergen
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** thermos E1 · **Ola:** 7 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E1-LIM-06
- **Ubicación:** `_nombre_de` en `programas/services/emergencia_comun.py:82` (sin usuario devuelve `"nadie"`); `nombre_de` en `programas/selectors/emergencia_mesa.py:74` (sin usuario devuelve `""`); otras copias en `programas/selectors/kits.py:68`, `programas/services/kits.py:138` y `programas/selectors/estadia_detalle.py:105`. `_hora` en `emergencia_comun.py:90` y `emergencia_mesa.py:82`. `_fecha_hora` en `emergencia_mesa.py:86`, `selectors/estadia_detalle.py:101` y `services/bitacora_detalle.py:32`. `_personas` en `emergencia_mesa.py:97` y `services/emergencia_ingreso_comun.py:50`. `_plazas`/`_camas` en `emergencia_mesa.py:101` y `emergencia_ingreso_comun.py:54`. Además `selectors/emergencia_llegadas.py:18` importa el **privado** `_personas` de `emergencia_mesa`.
- **Escenario:** dos funciones casi homónimas responden distinto por el mismo usuario nulo («nadie» en la traza, vacío en la ficha). Quien cambie el formato de la hora en la ficha no lo cambia en la traza, y el mismo evento sale «14:05» en un lado y otra cosa en el otro.
- **Causa raíz:** no hay un módulo de formato compartido en `programas`. Cada archivo nuevo se trajo su copia.
- **Solución:** crear `programas/services/formato.py`, puro, con `nombre_de(usuario, *, vacio="")`, `hora(momento)`, `fecha_hora(momento)`, `dia_y_mes(momento)` y `cantidad(n, singular, plural)` (`cantidad(1,"persona","personas")` da «1 persona»). Cada sitio llama con su variante actual: la traza con `vacio="nadie"`, la ficha con el valor por omisión. Las salidas quedan idénticas byte a byte. Borrar las copias.
- **Lo que NO hay que hacer:** unificar «nadie» y «""» en un solo valor. Cambia el texto de la traza y de la ficha.
- **Tests a agregar:** `programas/tests/test_formato.py::FormatoTests` con los casos de borde (usuario sin nombre, `None`, 1 o N, medianoche local).
- **Verificación:** ese test, y `grep -rn "def _\?nombre_de\|def _hora\|def _fecha_hora\|def _personas" programas` devuelve solo `formato.py`.
- **Regla para no repetirlo:** **control mecánico** · `test_arquitectura.py` (patrón de `test_la_constante_..._tiene_un_solo_dueno`) · «`def (_)?(nombre_de|hora|fecha_hora|personas|camas|plazas)\(` solo puede existir en `programas/services/formato.py`».

---

### E-LIM-26 · Mensajes y topes de validación duplicados como literales entre forms y servicios, y un homónimo con dos textos
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** thermos E1 · **Ola:** 7 · **Esfuerzo:** S
- **ID de la pasada 1:** E1-LIM-08
- **Ubicación (form ↔ servicio):** «Pedí al menos una plaza.» `forms_emergencia.py:455` ↔ `services/emergencia.py:525`. «Indicá por qué se cancela la derivación.» `:456` ↔ `:588`. «El motivo no puede tener más de 200 caracteres.» y el tope `200`: `:496,500,502` ↔ `:589-590`, tres veces. «Elegí una prioridad: alta, media o baja.» `:452` ↔ `:430`. «Elegí a alguien que opere la mesa de Emergencia.» `:453` ↔ `:390`. «Elegí el motivo del cierre.» `:451` ↔ `:745`. «Indicá qué fuerza traslada.» `:388` ↔ `services/emergencia_alta.py:204`. Tope de dirección `240`: `forms_emergencia.py:362` ↔ `emergencia_alta.py:241-242`. **Homónimo:** `SIN_PERMISO_DE_MESA` vale «Solo quien trabaja en la mesa de Emergencia puede ver esto.» en `selectors/emergencia.py:441` y «No tenés permiso para operar la mesa de Emergencia.» en `services/emergencia_comun.py:20`.
- **Escenario:** si se sube el tope del motivo a 300 en el servicio, el form sigue cortando en 200 (y el `maxlength` del widget también), y la API acepta lo que la web rechaza. Quien importe `SIN_PERMISO_DE_MESA` recibe un texto u otro según el módulo.
- **Causa raíz:** la regla RU-2 (el servicio decide) se cumplió, pero el form duplicó los textos en vez de importarlos.
- **Solución:** el servicio exporta las constantes (`PEDI_UNA_PLAZA`, `MOTIVO_DE_CANCELACION`, `MOTIVO_CANCELACION_MAX = 200`, `DIRECCION_MAX = 240`, `ELEGI_LA_PRIORIDAD`, `ELEGI_UN_OPERADOR`, `ELEGI_EL_MOTIVO`, `TRASLADO_OTRO_FALTA`) y `forms_emergencia.py` las importa. Los textos no cambian. El del selector se renombra `SIN_PERMISO_DE_VER_LA_MESA`, con el mismo texto.
- **Tests a agregar:** `programas/tests/test_emergencia_casos.py::ContratoFormServicioTests.test_topes_del_form_son_los_del_servicio`.
- **Verificación:** `grep -n "200\b" programas/forms_emergencia.py` sin literales de tope. Ese test en verde.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md` · «Un mensaje o un tope que el servicio valida se importa en el form desde el servicio; el form no lo vuelve a escribir».

---

### E-LIM-27 · La capacidad `"dispositivo.admitir"` está redeclarada en siete módulos
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** fusión de E-LIM-27; thermos E1 · **Ola:** 7 · **Esfuerzo:** S
- **ID de la pasada 1:** E1-LIM-09 + E2-LIM-10
- **Fusión (juez):** absorbe E-LIM-27 (misma constante `CAP_ADMITIR` y más duplicados de la etapa 3: `SIN_ALCANCE`, `_exigir_alcance`, mensajes, coerción «instancia o pk»). El dueño de la constante queda como decisión del juez (ver «Contradicciones» de la sección 1).
- **Ubicación:** la del programa es `programas/services/emergencia_programa.py:25`. Hay copias en `programas/services/emergencia_alta.py:56` (en el alcance), `emergencia_ingreso_comun.py:34`, `selectors/emergencia_alojar.py:49`, `views/emergencia_dispositivo.py:63` y `services/estadias.py:121`.
- **Escenario:** si la capacidad se renombra en el `CATALOGO` de `core/rbac.py`, cada copia que se olvide niega en silencio: `puede_*` devuelve `False` y el ingreso directo da 403 sin error de import. Es el patrón que CLAUDE.md prohíbe («no inventar un permiso suelto»), aunque acá sea por copia.
- **Causa raíz:** cada módulo nuevo declaró la constante localmente para no importar de un vecino.
- **Solución:** dejar un solo dueño, `services/dispositivos.py` (donde viven `CAP_VER` y `CAP_CONFIGURAR`), con `CAP_ADMITIR`. Los demás lo importan. `emergencia_programa.CAP_ADMITIR` pasa a ser un reexport.
- **Tests a agregar:** `programas/tests/test_arquitectura.py::...::test_la_capacidad_admitir_tiene_un_solo_dueno`, con el mismo patrón que `test_la_constante_de_la_capacidad_publica_tiene_un_solo_dueno` (`:346`).
- **Verificación:** `grep -rn '= "dispositivo.admitir"' programas` devuelve una línea.
- **Regla para no repetirlo:** **control mecánico** · `test_arquitectura.py` · «un literal `"<modulo>.<accion>"` del CATALOGO se asigna a una constante en un solo módulo de `programas`».

#### Aporte del segundo revisor (E2-LIM-10: Constantes, guardas y validaciones de entrada duplicadas en los módulos de la etapa)
_Pasada 1: severidad BAJA · estado CONFIRMADO (lectura) · esfuerzo S._

- **Ubicación:**
  - `CAP_ADMITIR = "dispositivo.admitir"` está definido 5 veces: `emergencia_programa.py:25`,
    `emergencia_ingreso_comun.py:34`, `selectors/emergencia_alojar.py:49`, `emergencia_alta.py:56`,
    y `estadias.py:121`.
  - `SIN_ALCANCE` está definido 2 veces: `emergencia_ingreso_comun.py:36` y `selectors/emergencia_alojar.py:51`.
  - `_exigir_alcance` está definido 2 veces: `emergencia_ingreso_comun.py:63` y `selectors/emergencia_alojar.py:87`.
    La copia del selector no contempla `dispositivo=None`.
  - El texto «No tenés alcance para liberar plazas en este dispositivo.» está 2 veces:
    `reservas_derivacion.py:310` y `estadias.py:935`.
  - La validación «motivo de catálogo + "Otro" exige observación» está 2 veces: `emergencia_recepcion.py:306-310`
    y `emergencia_cierre.py:205-209`.
  - La coerción «instancia o pk» está escrita a mano 6 veces: `emergencia_confirmacion.py:187-197`,
    `emergencia_cierre.py:77-83`, `reservas_derivacion.py:144` y `:232`, y
    `emergencia_ingreso_comun.py:116` y `:148`.
  - `admite_familias` y `recibe_kits` tienen el mismo cuerpo salvo la capacidad: `emergencia_programa.py:97-125`.
  - La autorización vive en el selector, que importa `services.dispositivos` (`selectors/emergencia_alojar.py:38`, `:87-89`).
- **Escenario:** el cambio de un texto o de una capacidad hay que hacerlo en varios lugares. Las dos copias de
  `_exigir_alcance` ya divergen: una tolera `None` y la otra no.
- **Causa raíz:** cada módulo nuevo copió lo que necesitaba del anterior.
- **Solución:**
  - `CAP_ADMITIR` y `SIN_ALCANCE` se importan de `estadias` o de `emergencia_programa`, en un solo dueño.
  - El selector importa `exigir_alcance_admitir` de `emergencia_ingreso_comun`, o se mueve la guarda a la vista
    y la API. La primera opción es la que no cambia el comportamiento.
  - `reservas_derivacion` importa el mensaje desde `estadias`.
  - Crear `_validar_motivo(motivo, observacion, choices, mensaje_vacio)` en `emergencia_comun`.
  - Crear `pk_de(valor)` en `emergencia_comun`, que devuelve `int` o `None` sin lanzar excepciones.
  - Escribir `admite_familias`/`recibe_kits` como `_opera_con(usuario, cap)`.
- **Lo que NO hay que hacer:** sacar la guarda de alcance de `plazas_para_caso` y `llegadas_del_dispositivo` sin
  ponerla antes en la vista y la API. El docstring (`:10-13`) explica por qué se exige ahí.
- **Tests a agregar:** `programas/tests/test_arquitectura.py::EmergenciaAlojarTest.test_cap_admitir_tiene_un_solo_dueno`.
- **Verificación:** `grep -rn 'CAP_ADMITIR = ' programas` devuelve 1 resultado.
- **Regla para no repetirlo:** **control mecánico** · `programas/tests/test_arquitectura.py` · un test de «un solo
  dueño» para `CAP_ADMITIR`, `SIN_ALCANCE` y `TOPE_PLAZAS_POR_SECTOR`, con el patrón ya usado en `:336-346`.

---

### E-LIM-28 · La regla «foto JPEG de la app, hasta 5 MB» está escrita dos veces, en dos capas
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 7 · **Esfuerzo:** S
- **ID de la pasada 1:** E4-LIM-10
- **Ubicación:** `programas/api/serializers_emergencia.py:34-57` (`FOTO_EXTENSIONES_APP`, `validar_foto_de_la_app`);
  `programas/services/kits.py:87`, `:106`, `:408-418` (`REMITO_EXTENSIONES`, `validar_remito`).
- **Escenario:** las dos funciones hacen `Path(name).suffix` ∈ `(".jpg", ".jpeg")` + `firma_coincide` + tope
  `ADJUNTO_MAX_BYTES`. Para las fotos del caso la regla corre en el **serializer**; para el remito, en el **servicio**
  (y la docstring de `RecepcionKitEnvioSerializer` justifica lo contrario de lo que hace `CasoEmergenciaEnvioSerializer`).
  Si mañana la app empieza a mandar WEBP, hay que cambiar dos tuplas en dos capas.
- **Causa raíz:** no hay un validador canónico «JPEG de la app» en `core/validators.py`, al lado de `validar_foto`.
- **Solución:** `core.validators.validar_jpeg_de_la_app(archivo, mensaje_formato)` que lanza Django `ValidationError`
  con el mensaje recibido; `validar_remito` y `validar_foto_de_la_app` la llaman (el serializer convierte a error DRF
  como hoy). Mensajes y orden de chequeo idénticos.
- **Tests a agregar:** `core/tests/test_validators.py::ValidarJpegDeLaAppTest` (PNG renombrado, >5 MB, JPEG válido).
- **Verificación:** `grep -rn '(".jpg", ".jpeg")' programas core` = 1.
- **Regla para no repetirlo:** **skill** · tabla «Helpers canónicos» de `.claude/skills/auditoria/rubricas/codigo-limpio.md`:
  agregar fila «Foto que sube la app (JPEG, 5 MB) → `validar_jpeg_de_la_app` (`core/validators.py`)».

---

### E-LIM-29 · La tabla severidad→tono/ícono y la serialización del `Aviso` están copiadas en Emergencia y Dispositivos
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 7 · **Esfuerzo:** S
- **ID de la pasada 1:** E3-LIM-08
- **Ubicación:** `programas/services/avisos_emergencia.py:57-58` y `programas/services/alertas_dispositivos.py:74-75`
  (`TONOS`, `ICONOS` idénticos). `programas/services/avisos_emergencia.py:425-445` (`avisos_del_tablero`) y
  `programas/services/detalle_dispositivo.py:~270-280` (`"tono": TONOS[...]`, `"icono": ICONOS[...]`).
- **Escenario:** si se agrega una severidad a `core.services.vencimientos.SEVERIDADES` (el registro la valida),
  hay que acordarse de dos tablas en dos apps. Si no, el primer aviso de esa severidad tira `KeyError` en la
  pantalla. El comentario de `avisos_emergencia.py:56` («los mismos de Dispositivos») reconoce la copia.
- **Causa raíz:** la presentación de la severidad no tiene dueño, y cada consumidor del registro la redeclaró.
- **Solución:** `core/services/vencimientos.py`: `TONO_DE_SEVERIDAD`, `ICONO_DE_SEVERIDAD` y
  `Aviso.para_alerta() -> dict` (o `avisos_para_alerta(ambito, *args, **kwargs)`), al lado de `SEVERIDADES`.
  `avisos_del_tablero` y el bloque de `detalle_dispositivo` pasan a una llamada.
- **Tests a agregar:** `core/tests/test_vencimientos.py::SeveridadesTest.test_cada_severidad_tiene_tono_e_icono`.
- **Verificación:** `grep -rn "TONOS = {\"alta\"" programas/` sin resultados.
- **Regla para no repetirlo:** **control mecánico** · el test anterior cruza `SEVERIDADES` con las dos tablas,
  así que una severidad nueva sin tono pone el CI en rojo.

---

### E-LIM-30 · Tablas de presentación repartidas en servicio, *presenter* y vista
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** thermos E1 · **Ola:** 8 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E1-LIM-05
- **Ubicación:** `programas/services/emergencia.py:123-151` (`ESTADOS_VISIBLES_CASO` y `PRIORIDADES_VISIBLES` con tonos de badge, más `estado_visible_de_caso` y `prioridad_visible`). `programas/selectors/emergencia_mesa.py:269-280` (`SOLAPAS_POR_ESTADO` y `SOLAPAS_DE_ATENCION` con sus rótulos). `programas/views/emergencia.py:121-125` (rótulos del semáforo escritos en la vista). `programas/views/emergencia.py:194-208` (la vista arma el diccionario del modal «Derivar a…» con tono, textos y pregunta).
- **Escenario:** cambiar cómo se lee un estado o una solapa obliga a buscar en tres capas. El comentario de `services/emergencia.py:124` dice que la tabla «la leen la bandeja, la ficha y la app», pero `grep` la encuentra solo en `selectors/emergencia_mesa.py` y en tests: la API no la usa. El servicio, que según CLAUDE.md es «lógica de negocio y escritura», carga tonos de badge (`"brand"`, `"gray"`).
- **Causa raíz:** cada pieza de presentación se escribió en la primera capa que la necesitó, y no hay un módulo de rótulos de Emergencia.
- **Solución:** crear `programas/selectors/emergencia_rotulos.py`, puro y sin consultas, con `ESTADOS_VISIBLES_CASO`, `PRIORIDADES_VISIBLES`, `estado_visible_de_caso`, `prioridad_visible`, los rótulos de solapas y de semáforo y `ROTULO_DE_NECESIDAD` (LIM-07). `services/emergencia.py` los reexporta por una release. La vista pasa a leer `mesa.SEMAFOROS`, y la confirmación de derivar pasa a una función `mesa.confirmacion_de_derivar(elegido, plazas)` que la vista llama para sumarle el `DerivarCasoForm`. Textos y tonos idénticos. Corregir el comentario que nombra a la app.
- **Lo que NO hay que hacer:** pasar tonos y rótulos a los templates con `{% if estado == ... %}`. El patrón del repo es dato resuelto en Python.
- **Tests a agregar:** `programas/tests/test_emergencia_mesa.py::RotulosTests.test_toda_opcion_de_estado_y_prioridad_tiene_rotulo` (recorre `CasoEmergencia.Estado` y `Prioridad`).
- **Verificación:** snapshot o `assertContains` de E2 y E3 sin diferencias. Los presupuestos de consultas de `test_emergencia_mesa` no cambian.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md` · «En Emergencia los rótulos y tonos viven en `selectors/emergencia_rotulos.py`; un servicio no conoce tonos de badge y una vista no escribe tuplas de rótulos».

---

### E-LIM-31 · La foto del tablero cruza módulos como tuplas posicionales (`fila[3]`, `fila[5]`) y se desarma a mano en 60 líneas
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 8 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E3-LIM-09
- **Ubicación:** `programas/selectors/emergencia_tablero.py:166` (`Red.dispositivos`: tupla de 5),
  `:191-196` (`Foto.pendientes` de 6 y `entregas_sin_revisar` de 4, tipadas solo en comentarios),
  `:225-286` (18 columnas en `values_list` y otra vez en el desarmado). Las consumen
  `programas/services/avisos_emergencia.py:145` (`fila[5]`), `:300` y `:306` (`fila[3]`), `:147`, `:265` y
  `:308`, y `emergencia_tablero.py:170-180` y `:558`.
- **Escenario:** si se agrega una columna a `_derivaciones_pendientes` (por ejemplo, la localidad del
  dispositivo), `fila[5]` en otro archivo pasa a ser otro dato sin error de tipos. El aviso «por vencer»
  compararía contra un `str`, y en el mejor caso la pantalla tira un `AttributeError`. `FilaCaso` ya demuestra
  que el módulo sabe hacerlo bien con un dataclass. Las otras tres formas quedaron como tuplas.
- **Causa raíz:** optimización de `values_list` sin el paso de nombrar el resultado.
- **Solución:** dataclasses `FilaDispositivo`, `PendienteDerivacion` y `EntregaSinRevisar` (frozen, al lado de
  `FilaCaso`). En `_casos_de_la_ventana`, `.values(*CAMPOS)` con alias que coinciden con los campos
  (`localidad=F("localidad__nombre")`…) y `FilaCaso(**fila)`. Así desaparece el desarmado de 18 nombres
  (`:246-287`). Los consumidores pasan a `fila.vence_en` / `fila.dispositivo_id`. No cambia el número de consultas.
- **Tests a agregar:** los de presupuesto existentes (`test_emergencia_tablero`, `@tag("performance")`).
- **Verificación:** `grep -n "fila\[[0-9]\]" programas/services/avisos_emergencia.py` sin resultados.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md`, regla 5: «Una tupla de `values_list` que sale
  de la función que la armó se convierte en dataclass antes de cruzar el módulo».

---

### E-FE-01 · El esqueleto del modal con formulario está copiado cinco veces en la ficha del caso
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** thermos E1 · **Ola:** 9 · **Esfuerzo:** M
- **ID de la pasada 1:** E1-FE-01
- **Decisión del juez:** no renombrar `x-becas-modal` ni los parciales `programas/becas/_modal_*` en esta ola. La pieza nueva (`{% modal_form %}` o parcial del módulo) los sigue usando por dentro.
- **Ubicación:** `programas/templates/programas/emergencia/casos/detail.html:328-350` (derivar), `:352-369` (cerrar), `:371-388` (cancelar), `:390-406` (prioridad) y `:408-424` (reasignar). Cada uno repite el overlay `x-show`/`x-cloak`/`x-becas-modal`, el backdrop, el contenedor `role="dialog"`, `_modal_header`, el `<form>` con `csrf_token`, el cuerpo con scroll y `_modal_footer`. El mismo shell aparece en otros 26 templates del repo (`grep -rl x-becas-modal`), y Emergencia toma las piezas de `programas/becas/`.
- **Escenario:** un ajuste de accesibilidad del modal (foco inicial, `aria-describedby`) o del cierre con backdrop hay que hacerlo cinco veces en este archivo y 27 en el repo. El comentario de `:16` («los overlays fixed van fuera del space-y-5…») registra un bug que ya apareció por copiar mal el shell.
- **Causa raíz:** los partials cubren cabecera y pie, pero no el contenedor. El cuerpo del modal no se puede pasar a un `{% include %}`.
- **Solución:** un block tag en `nodo_ui`, del mismo estilo que `{% page_header %}…{% endpage_header %}` que ya existe, por ejemplo `{% modal_form abierto="modalCerrar" titulo=… icono=… tono=… action=… accion_texto=… %}…cuerpo…{% endmodal_form %}`. Tiene que emitir **exactamente** el HTML actual, clases incluidas, para no cambiar lo visual. Migrar primero los cinco de `detail.html`. Es una pieza canónica: el mismo diff actualiza su fila en `.claude/agents/chaco-design-system.md` y su ficha en `.claude/design/` (si no, falla `check_design_agent.py`). `DECISIÓN CLIENTE`: no aplica. **Decisión de diseño del juez:** el nombre de la pieza y si renombra `x-becas-modal` y los partials `programas/becas/_modal_*` a un namespace neutro (por defecto, no renombrar en esta ola).
- **Lo que NO hay que hacer:** retocar clases o estructura del modal «de paso». Rompe los snapshots de Becas (memoria: congelan el shell entero).
- **Tests a agregar:** `core/tests/test_nodo_ui.py::ModalFormTagTests.test_emite_el_mismo_html_que_el_shell_manual`.
- **Verificación:** `compile_templates.py --bloques` en 0, `design_audit.py --ratchet` sin hallazgos nuevos, y HTML de E3 sin diferencias contra HEAD.
- **Regla para no repetirlo:** **control mecánico** · `scripts/design_audit.py` · regla nueva `MODALSHELL`: un template con más de una aparición de `role="dialog" aria-modal="true"` escrita a mano es hallazgo («usá `{% modal_form %}`»), en modo ratchet.

---

### E-ERR-04 · Con la cubeta de identidad agotada, la mesa no puede cargar un caso «con identidad a revisar»
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** nuevo · **Ola:** 0 · **Esfuerzo:** S
- **ID de la pasada 1:** E1-ERR-04
- **Ubicación:** `programas/forms_emergencia.py:397-405` (`muestra_identidad_en_conflicto` solo se prende con un
  `DniRegistrado`); `programas/api/throttles.py:57-58` (`rechazo_para_mostrar` reemplaza el `DniRegistrado` por
  un `ValidationError` común cuando la cubeta está agotada); `programas/views/emergencia.py:160-162`.
- **Escenario:** una operadora de la mesa ya gastó la cubeta `personas_campo` de la hora (por ejemplo, con varios
  DNI que coincidían con otra persona). Llega un llamado de una familia cuyo responsable tiene un DNI registrado
  con otro nombre y la operadora sabe, por lo que le dicen, que es otra persona. El envío vuelve con «Ese DNI ya
  está registrado como otra persona, y llegaste al tope… Probá de nuevo más tarde.», pero el error ya no es un
  `DniRegistrado`, así que la casilla «El DNI es correcto y es otra persona: cargar con identidad a revisar» **no
  aparece**. Las únicas salidas son borrar nombre y apellido (el caso queda colgado de la persona equivocada, sin
  marca de revisión) o esperar hasta una hora con la familia sin caso.
- **Causa raíz:** la casilla se muestra por el **tipo** del error, y el reemplazo de SEC-25 cambia el tipo para no
  filtrar el nombre. Mostrar la casilla no filtra nada: no lleva el nombre de la persona registrada.
- **Solución:** que `rechazo_para_mostrar` devuelva, con la cubeta agotada, una subclase de `DniRegistrado` sin el
  nombre (o que `NuevoCasoMesaForm.agregar_errores_del_servicio` prenda la casilla también ante
  `MENSAJE_DNI_REGISTRADO_SIN_CUPO`). El texto del rechazo y lo que se descuenta de la cubeta quedan igual.
  `DECISIÓN CLIENTE: por defecto, mostrar la casilla también sin cupo` (si el PM decidió que sin cupo no se
  permite el alta marcada, es un REFUTADO y va a Descartados con ese motivo).
- **Lo que NO hay que hacer:** no devolver el nombre de la persona registrada cuando la cubeta está agotada.
- **Tests a agregar:** `programas/tests/test_emergencia_mesa.py::NuevoCasoViewTests.test_sin_cupo_igual_ofrece_identidad_a_revisar`.
- **Verificación:** con la cubeta agotada (`ConsultaPersonasThrottle` parchado), el re-render 400 incluye el campo
  `identidad_en_conflicto` y no incluye el apellido de la persona registrada.
- **Regla para no repetirlo:** **skill** · `.claude/skills/seguridad-django/SKILL.md` (datos personales) · «Cuando un
  tope de privacidad reemplaza un error para ocultar un dato, el reemplazo conserva el **tipo** del error (subclase
  sin el dato), así el flujo que depende del tipo sigue andando.»

---

### E-ERR-05 · «Nuevo caso» de la mesa no es idempotente: un reenvío del POST crea un segundo caso con otro número
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** nuevo · **Ola:** 1 · **Esfuerzo:** S
- **ID de la pasada 1:** E1-ERR-03
- **Ubicación:** `programas/views/emergencia.py:150-166` (`NuevoCasoView.post` llama a `crear_caso` sin
  `uuid_cliente`); `programas/forms_emergencia.py:431-444` (`datos_formulario1`, sin identificador de envío);
  `programas/services/emergencia_alta.py:459-463` (la idempotencia de RU-16 solo actúa con `uuid_cliente`).
- **Escenario:** quien atiende el teléfono carga una familia con fotos; el POST tarda (fotos + candado del
  numerador, ver E-PERF-02) y el navegador recibe un corte o la persona recarga y confirma «Reenviar formulario»
  desde la pantalla de error, o lo manda desde una segunda pestaña con la página atrás del historial. El primer
  POST ya había commiteado: el segundo crea **otro** `GrupoFamiliar` y otro `CasoEmergencia` (2026-C-000185 además
  de 2026-C-000184), los dos `EN_GESTION` y tomados por la misma persona. `nodo-submit-guard.js` frena el doble
  clic en la misma página, no el reenvío. Lo único que lo hace visible es el aviso informativo «Posible duplicado».
- **Causa raíz:** el alta tiene idempotencia por `uuid_cliente` (RU-16) pero solo la app la usa; el formulario
  del backoffice no genera identificador de envío.
- **Solución:** un `uuid_cliente = forms.UUIDField(widget=forms.HiddenInput, required=False)` en
  `NuevoCasoMesaForm`, con `initial=uuid4()` en el GET (y conservado en el re-render con errores), y en la vista
  `crear_caso(..., uuid_cliente=form.cleaned_data.get("uuid_cliente"))`. `crear_caso` ya devuelve el mismo caso
  (`ya_existia=True`) si el uuid es de ese usuario; la vista redirige a la ficha igual. Sin cambio visual: el campo
  es oculto. El mensaje de éxito puede quedar igual.
- **Lo que NO hay que hacer:** no deduplicar por DNI del responsable: dos familias distintas pueden declarar al
  mismo responsable y la decisión registrada (RN-2.14) es que el duplicado es informativo.
- **Tests a agregar:** `programas/tests/test_emergencia_mesa.py::NuevoCasoViewTests.test_reenvio_del_mismo_formulario_no_crea_otro_caso`.
- **Verificación:** dos POST con el mismo cuerpo → un solo `CasoEmergencia`, los dos responden 302 a la misma ficha.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/` (la de errores) · «Un POST del
  backoffice que **crea** una entidad con número correlativo o con efecto externo lleva identificador de envío
  oculto y lo pasa al servicio idempotente; la guardia JS de doble clic no cubre el reenvío del navegador.»

---

### E-ERR-06 · Ingreso directo y «Agregar persona» desde el backoffice no tienen idempotencia del lado del servidor
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** nuevo · **Ola:** 1 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E2-ERR-02
- **Ubicación:** `programas/views/emergencia_dispositivo.py:710` (`ingreso_directo` sin `uuid_cliente`), `:690` (`avisar_a_la_mesa` sin `uuid_cliente`), `:351` (`agregar_integrante` sin `uuid_cliente`); servicio `programas/services/emergencia_sin_derivacion.py:94-130` (sin `uuid_cliente` no hay ninguna deduplicación) y `programas/services/emergencia_confirmacion.py:533-545`.
- **Escenario:** dos guardias del mismo dispositivo (o la misma en dos pestañas) cargan «Ingresar igual» para la familia que está en la puerta. Cada POST crea un `CasoEmergencia` con su `Derivacion ACEPTADA` y **reserva camas** con `_reservar_camas`: la misma familia retiene el doble de camas hasta que alguien cancele uno de los dos ingresos. Lo mismo con «Agregar persona»: dos POST suman dos filas y `total_declarado` +2, y `alojar_familia` exige confirmar a una persona que no existe (hay que cerrar con diferencia). `nodo-submit-guard.js` evita el doble clic en una pestaña, no las otras dos vías.
- **Causa raíz:** la idempotencia del módulo cuelga de `uuid_cliente` (RU-16), que manda la app; la vista web no genera uno y `crear_caso` no deduplica por responsable con caso abierto.
- **Solución:** sin tocar la lógica del servicio: que los formularios web de «Ingresar igual», «Avisar a la mesa» y «Agregar persona» lleven un `uuid_cliente` oculto generado al renderizar (`uuid.uuid4()` en el `get`/contexto) y que la vista lo pase al servicio. Con eso el reenvío del mismo formulario devuelve el caso o la fila ya creados (`ya_existia` / `ya_estaba`), igual que en la app.
- **Lo que NO hay que hacer:** agregar un `UniqueConstraint` condicional por responsable «abierto» (no existe en MySQL/MariaDB) ni rechazar un segundo caso del mismo responsable (la mesa puede tener motivos y es otra decisión de negocio).
- **Tests a agregar:** `programas/tests/test_emergencia_dispositivo_web.py::IngresoDirectoWebTests.test_reenvio_del_mismo_formulario_no_duplica_caso_ni_reservas`; `…::AgregarIntegranteWebTests.test_reenvio_no_suma_otra_fila`.
- **Verificación:** dos POST con el mismo `uuid_cliente` → un caso, las mismas reservas; dos filas no aparecen.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/` (rúbrica de errores) · «Un servicio idempotente por `uuid_cliente` tiene que recibirlo desde **todas** sus vistas: la web lo genera en el formulario; un `uuid_cliente=None` en una vista que crea casos, reservas o filas es un hallazgo.»

---

### E-ERR-07 · «Crear entrega» no es idempotente: un reenvío del paso 3 arma una segunda entrega (o una segunda reposición de la misma)
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** nuevo · **Ola:** 1 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E3-ERR-03
- **Ubicación:** `programas/views/emergencia_kits.py:357-375` (`NuevaEntregaConfirmarView.post`), `programas/services/kits.py:295-342` (`crear_entrega` numera y crea sin identificador de envío); `_validar_reposicion` `kits.py:280-292` no mira si la original ya tiene reposiciones.
- **Escenario:** el POST de «Crear entrega» tarda (ECOM, numerador bloqueado por otra alta) y el operador recarga la página y acepta «reenviar el formulario», o el proxy reintenta: el segundo POST trae los mismos ocultos y crea `2026-K-000032` además de `…031`, con las mismas líneas, al mismo dispositivo. Con «Reponer», además, el botón sigue en E5 después de la primera reposición (`emergencia_kits.py:430-432` depende solo de `faltantes`), así que la misma diferencia se puede reponer dos veces. `nodo-submit-guard.js` cubre el doble clic, no la recarga ni el reintento.
- **Causa raíz:** el asistente no usa sesión (decisión explícita) y el servicio no tiene clave de envío; nada distingue «el mismo envío otra vez» de «otra entrega igual».
- **Solución:** `DECISIÓN CLIENTE: deduplicar por envío`. Sin migración: oculto `envio = UUIDField` en `ConfirmarEntregaForm` generado al mostrar el resumen; en la vista, antes de `crear_entrega`, `cache.add(f"kits:envio:{envio}", "en_curso", 3600)`; si ya existe, redirigir al detalle guardado (`cache.set(..., entrega.pk)` tras crear) con el mensaje de éxito. En producción el cache es Redis (compartido entre pods). Para reposiciones, como mínimo mostrar en E5 «ya repuesta por K-…» junto al botón (`reposiciones` ya está en el contexto).
- **Lo que NO hay que hacer:** un `UniqueConstraint` condicional sobre `(repone_a)` para impedir la segunda reposición: en MySQL/MariaDB no existe y en SQLite sí (el CI pasaría y la regla no estaría en prod).
- **Tests a agregar:** `programas/tests/test_emergencia_kits.py::NuevaEntregaWebTest.test_reenvio_del_mismo_envio_no_crea_otra`.
- **Verificación:** dos POST con el mismo `envio` → una entrega, el segundo redirige al detalle de la primera.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/correccion-seguridad.md` · «Un POST que crea una fila numerada (caso, entrega) necesita una clave de envío; sin ella, un reenvío del navegador duplica. La guardia JS no cuenta como idempotencia.»

---

### E-ERR-08 · El reintento idempotente de confirmar o agregar devuelve 409 si el caso ya cambió de estado
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** nuevo · **Ola:** 1 · **Esfuerzo:** S
- **ID de la pasada 1:** E2-ERR-03
- **Ubicación:** `programas/services/emergencia_confirmacion.py:357` (`_abrir_ingreso(..., INGRESO_EN_CURSO)`) antes de `:366-371` (respuesta idempotente por `uuid_cliente`); igual en `:529` antes de `:533-537`.
- **Escenario:** la guardia confirma a la última persona (201 que se pierde por la red); otra guardia toca «Familia alojada» (`ALOJADO`). La app reintenta con el mismo `uuid_cliente` y recibe **409** «La familia ya figura alojada», cuando el contrato §13.8 dice «el mismo `uuid_cliente` otra vez sobre la misma persona devuelve **200** con la misma fila». Lo mismo con «Agregar persona» si el ingreso se cerró entre medio.
- **Causa raíz:** la guarda de estado de `_abrir_ingreso` corre antes de mirar si el envío ya se aplicó.
- **Solución:** `DECISIÓN CLIENTE: honrar el contrato`. Abrir con `_abrir_ingreso(caso, usuario, Estado.INGRESO_EN_CURSO, Estado.ALOJADO, Estado.CERRADO)`, resolver primero la rama idempotente (fila confirmada con ese `uuid_cliente` → 200) y recién después exigir `INGRESO_EN_CURSO` con el mismo `EstadoCambio`/mensaje de `_por_que_ya_no`. Para agregar, igual con `uuid_cliente_alta`. No cambia ninguna escritura.
- **Tests a agregar:** `programas/tests/test_emergencia_alojar.py::ConfirmarIntegranteTests.test_reintento_con_mismo_uuid_tras_alojar_devuelve_la_fila`; `…::AgregarIntegranteTests.test_reintento_con_mismo_uuid_tras_cerrar_devuelve_la_fila`.
- **Verificación:** los dos tests; el 409 sigue para un `uuid_cliente` distinto.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/` · «En un servicio idempotente, la comprobación de "ya se hizo" va antes que la guarda de estado: si no, el reintento de un envío exitoso se ve como conflicto.»

---

### E-ERR-09 · El reenvío de una recepción de kits sin `cantidades` da 400 en vez del 200 que promete el contrato
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** nuevo · **Ola:** 1 · **Esfuerzo:** S
- **ID de la pasada 1:** E4-ERR-01
- **Ubicación:** `programas/api/views_emergencia_kits.py:159-162` (validación de forma antes del servicio) y
  `programas/api/serializers_emergencia.py:333-340` (`cantidades` obligatorio). Contrato:
  `docs/internal/contrato-app-emergencia.md:455-457` («No se vuelve a validar ni se escribe nada: no importa qué
  traiga el segundo cuerpo (ni siquiera hace falta el remito)»).
- **Escenario:** la primera recepción llegó al servidor y la respuesta se perdió. La app (o una versión futura
  que reintente solo con el identificador, como habilita el contrato) reenvía `uuid_cliente` sin
  `cantidades[...]` → el serializer corta con 400 `VALIDACION` «Indicá cuánto llegó de cada ítem…» y nunca llega
  a `recibir_entrega`, que sí habría contestado 200 por `uuid_cliente_recepcion` (`services/kits.py:490-492`).
  La guardia ve un error de validación sobre una entrega que ya quedó recibida. Hoy la app reenvía el mismo
  cuerpo, por eso es BAJA.
- **Causa raíz:** el contrato describe la idempotencia del servicio; la vista agrega un paso previo
  (forma del cuerpo) que en M1 el contrato sí declara («lo único que se mira antes es que se pueda leer») y en
  kits no.
- **Solución:** elegir una de las dos, sin cambiar la regla del servicio:
  (a) alinear el contrato §12 con el código: «Lo único que se mira antes es la forma: `uuid_cliente` UUID y
  `cantidades` enteros ≥ 0 (pueden ser las mismas del primer envío)», o
  (b) `cantidades = _CantidadesField(required=False, default=dict, …)` y dejar que `_validar_cantidades` del
  servicio diga «falta la cantidad de X» (mismo mensaje y clave `cantidades`) cuando no es reenvío.
  (a) es la de menor riesgo.
- **Tests a agregar:** `programas/tests/test_emergencia_api_kits.py::RecibirEntregaApiTest.test_reenvio_sin_cantidades`
  (fija el comportamiento elegido).
- **Verificación:** el test; `test_emergencia_api_contrato` sin cambios de claves.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/` (contratos de API) · «Cada
  "idempotente: no se valida nada" del contrato se contrasta con lo que la **vista** valida antes de llamar al
  servicio; el contrato tiene que listar esa validación previa.»

---

### E-ERR-10 · La cola reintenta para siempre un ingreso directo que ya se creó si el usuario perdió el dispositivo
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** nuevo · **Ola:** 1 · **Esfuerzo:** S
- **ID de la pasada 1:** E4-ERR-02
- **Ubicación:** `programas/api/views_emergencia_sin_derivacion.py:245` y `:296` (`self._dispositivo(...)`
  antes del servicio) sobre `views_emergencia_llegadas.py:110-112`; contrato §13.10
  (`contrato-app-emergencia.md:846-848`: «la cola reintenta con el mismo `uuid_cliente` hasta recibir 200 o 201»)
  y §2 (404 → «Recargar mis dispositivos»).
- **Escenario:** «Ingresar igual» se encola sin señal (es lo único de M2 que se encola). El primer envío sí
  llegó (o llega) y crea el caso; antes del reintento la mesa saca al usuario del Equipo, o le quitan el rol, o
  el dispositivo deja de estar en su alcance. Cada reintento con el mismo `uuid_cliente` contesta **404**
  (o 403 `SIN_MODULO` si ya no admite en ningún lado) aunque el caso exista: la vista corta antes de la
  idempotencia del servicio. La app no recibe nunca 200/201 y el ítem queda pendiente en la cola del teléfono
  sin forma de saber que la familia sí entró. Depende de que la app trate 404 como reintentable (no verificado
  en `Chaco-mobile`), por eso PLAUSIBLE.
- **Causa raíz:** el chequeo de alcance de la URL va antes que la búsqueda por `uuid_cliente`, y el contrato no
  define qué hace la cola con un 404/403 de un envío encolado.
- **Solución:** documentar en el contrato §13.10 que un 404/403 sobre un envío encolado es **terminal** (la cola
  lo saca y avisa «Ya no operás ese dispositivo; el caso puede haberse creado: consultá a la mesa»), igual que
  `UUID_EN_USO`. No cambiar el orden en el servidor: devolver el caso a quien ya no opera el dispositivo
  reabriría E-SEG-01.
- **Tests a agregar:** ninguno en el servidor (el comportamiento queda); en `Chaco-mobile`, el de la cola ante 404.
- **Verificación:** contrato actualizado y caso de QA en testing: encolar, sacar del Equipo, reconectar.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/` (contratos de API) · «Todo
  extremo que la app encola tiene que declarar en el contrato qué códigos son terminales para la cola (no solo
  200/201 y 409 `UUID_EN_USO`).»

---

### E-ERR-11 · Un número de más de 308 dígitos en una cantidad del Formulario 1 tumba el alta con un 500
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** nuevo · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** E1-ERR-01
- **Alcance ampliado (juez, a partir de E4):** cubre también la cantidad enorme en `cantidades[<id>]` de la recepción de kits (`programas/api/serializers_emergencia.py:334`, `IntegerField` sin `max_value`): es la misma causa raíz. Arreglo común: `max_value` donde la regla es del servicio no se pone en un solo borde; se atrapa `OverflowError` en el servicio y se acota el campo de la API de kits.
- **Ubicación:** `programas/services/emergencia_alta.py:146-160` (`_entero`, la comparación de la línea 151);
  entradas sin tope: `programas/forms_emergencia.py:237-245` (`_cantidad`, `IntegerField` sin `max_value`) y
  `programas/api/serializers_emergencia.py:64-65` (`_cantidad`, `IntegerField` sin `max_value`).
- **Escenario:** en «Nuevo caso» de la mesa (o en el envío M1 de la app) se manda `menores_f` = `1` seguido de 400
  ceros. El `IntegerField` del formulario lo convierte a `int` sin quejarse (no tiene tope y el número está por
  debajo del límite de 4300 dígitos de Python). En `_entero`, `int(valor) != float(valor)` evalúa
  `float(<int de 401 dígitos>)` → `OverflowError: int too large to convert to float`. `_entero` atrapa solo
  `TypeError` y `ValueError`, así que la excepción sube por `crear_caso` y `NuevoCasoView.post` (que atrapa
  solo `ValidationError`) → **500** en lugar del «Tiene que ser un número entero.» del campo.
- **Causa raíz:** la guarda de «es entero» usa `float()` sobre un `int` arbitrario, y el `except` no cubre
  `OverflowError`. El mismo módulo ya lo contempla para `precision_m` (`emergencia_alta.py:261`), no acá.
- **Solución:** en `_entero`, sumar `OverflowError` al `except (TypeError, ValueError)` de la línea 154. Con eso
  el número inválido cae en el mensaje de siempre. Ningún cambio de lógica para valores válidos: el tope real
  (`PositiveSmallIntegerField`, 32767) lo sigue diciendo `grupo.full_clean()`.
- **Lo que NO hay que hacer:** no poner `max_value=32767` solo en el formulario de la mesa: la regla es del
  servicio (RU-2) y la API entra por el mismo `_entero`.
- **Tests a agregar:** `programas/tests/test_emergencia_alta.py::ValidarFormulario1Tests.test_cantidad_gigante_es_error_de_campo`
  (`_validar_formulario1({"menores_f": 10**400, ...})` levanta `ValidationError` con la clave `menores_f`).
- **Verificación:** el test anterior en rojo sin el arreglo (OverflowError), en verde con él.
- **Regla para no repetirlo:** **skill** · `.claude/skills/seguridad-django/SKILL.md` (sección de validación de
  entrada) · «Toda conversión numérica de entrada del usuario que pase por `float()` atrapa `OverflowError`
  además de `ValueError`/`TypeError`: un `int` de Python no tiene tope y `float(int)` sí.»

---

### E-ERR-12 · «Familia alojada» acepta un sector dado de baja
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** nuevo · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** E2-ERR-04
- **Ubicación:** `programas/services/emergencia_cierre.py:74-86` (`_sector_del_dispositivo`), llamado en `:149`.
- **Escenario:** la app manda `sector` con el id de un sector inactivo del dispositivo (el serializer `programas/api/serializers_emergencia.py:671` acepta cualquier entero). `Sector.objects` no filtra `activo` (el modelo no tiene manager propio; `selectors/emergencia_alojar.sectores_del_dispositivo` filtra a mano), así que `caso.situacion["alojamiento"]` queda con un sector que no existe en el mapa.
- **Causa raíz:** el filtro de activo vive en el selector que arma las opciones y no en el servicio que valida.
- **Solución:** en `_sector_del_dispositivo`, `Sector.objects.filter(pk=…, dispositivo_id=…, activo=True)`; mismo mensaje «Elegí un sector de este dispositivo.».
- **Tests a agregar:** `programas/tests/test_emergencia_alojar.py::AlojarFamiliaTests.test_sector_dado_de_baja_es_error`.
- **Verificación:** el test.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/` · «Todo id que llega del cliente y debe salir de una lista de opciones se valida en el servicio con el mismo filtro que arma la lista.»

---

### E-ERR-13 · El ingreso directo, si pierde una cama en la carrera, pide «volver a tocar Aceptar»
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** nuevo · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** E2-ERR-05
- **Ubicación:** `programas/services/emergencia_ingreso_comun.py:38-40` y `:236-241` (`_reservar_camas` traduce todo choque de plaza a `CAMAS_TOMADAS_MIENTRAS_ACEPTABA`); usado por `programas/services/emergencia_sin_derivacion.py:128-130`.
- **Escenario:** «Ingresar igual» compite con otra guardia o con el mapa por una cama libre; el servicio falla con «Mientras aceptabas… Volvé a tocar «Aceptar»», pero en esa pantalla no hay botón «Aceptar» (el botón es «Crear el caso y seguir con las fichas»). La transacción se deshace entera, así que el dato está bien: lo que falla es la instrucción a la guardia (RU-20).
- **Causa raíz:** el mensaje del helper compartido quedó escrito para el único llamador original.
- **Solución:** que `_reservar_camas` reciba el mensaje (`mensaje=CAMAS_TOMADAS_MIENTRAS_ACEPTABA` por defecto) y que `ingreso_directo` pase uno propio («Mientras ingresabas, alguien tomó una de las camas. Volvé a enviar el formulario.»). Sin cambio de lógica.
- **Tests a agregar:** `programas/tests/test_emergencia_alojar.py::IngresoDirectoTests.test_cama_tomada_en_la_carrera_da_mensaje_del_ingreso_directo`.
- **Verificación:** el test (con `_exigir_plaza_libre` parchado para fallar).
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/` · «Un helper compartido no fija textos de pantalla que nombran botones: los recibe del llamador.»

---

### E-ERR-14 · Si el UNIQUE de `uuid_cliente_recepcion` salta, la foto del remito queda huérfana en `media/`
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** nuevo · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** E3-ERR-04
- **Ubicación:** `programas/services/kits.py:513-531` (`recibir_entrega`).
- **Escenario:** el mismo `uuid_cliente` llega a la vez para dos entregas distintas (app con un bug de reuso, o dos colas). En la segunda, `bloqueada.save()` corre `FileField.pre_save`, que **escribe** el JPEG en el storage, y después el `UPDATE` choca con el UNIQUE: el `except IntegrityError` levanta `UuidEnUso` **antes** de `anotar_archivo_escrito` (`:531`), así que `archivos_atomicos` no tiene nada que borrar. La foto del remito (documentación de la operación del dispositivo) queda en `emergencia/entregas/<carpeta>/` sin fila que la referencie.
- **Causa raíz:** el archivo se anota recién después de un `save` que puede fallar *después* de haber escrito el archivo.
- **Solución:** en el `except IntegrityError`, anotar antes de levantar: `anotar_archivo_escrito(bloqueada.remito, asignado=remito)` y después `raise UuidEnUso(UUID_EN_USO) from None`. `archivos_atomicos` lo borra al propagar. Sin cambio de comportamiento visible.
- **Tests a agregar:** `programas/tests/test_emergencia_kits.py::RecibirEntregaTest.test_uuid_en_uso_por_integrity_no_deja_el_remito` (mock del `save` interno que escribe y levanta `IntegrityError`; verifica que el storage no tiene el archivo).
- **Verificación:** el test; mutación: sacar la anotación del `except` → rojo.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/correccion-seguridad.md` · «En una función con `@archivos_atomicos`, todo `save()` de un FileField dentro de un `try/except` que traduce el error tiene que anotar el archivo también en la rama del `except`.»

---

### E-ERR-15 · «Marcar en camino» acepta una hora de salida anterior al armado de la entrega
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** nuevo · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** E3-ERR-05
- **Ubicación:** `programas/services/kits.py:362-369` (`marcar_en_camino` solo rechaza la hora futura); formulario `programas/forms_emergencia_kits.py:185-192`.
- **Escenario:** la mesa arma la entrega hoy 10:00 y al marcarla en camino tipea `2025-11-19T10:00` (año anterior) o `1900-01-01`: `despachada_en` queda antes de `creado`. El tablero (`emergencia_tablero.py:664-666`) muestra «hace 1 año» y la ordena primera entre las en camino; E5 muestra «En camino desde» anterior a «Armada por»; la traza queda «Salió a las …» sin fecha que delate el error.
- **Causa raíz:** la validación de `hora` mira solo el futuro, sin el límite inferior natural (el armado).
- **Solución:** `DECISIÓN CLIENTE: rechazar una salida anterior al armado`. Tras `_bloquear_entrega`, `if hora is not None and hora < bloqueada.creado: raise ValidationError({"hora": "La hora de salida no puede ser anterior al armado de la entrega."})`. La vista ya traduce `ValidationError` al aviso.
- **Tests a agregar:** `programas/tests/test_emergencia_kits.py::MarcarEnCaminoTest.test_hora_anterior_al_armado_se_rechaza`.
- **Verificación:** el test; la entrega queda `PREPARADA`.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/correccion-seguridad.md` · «Una fecha que carga el usuario para un hito tiene los dos límites: no futura y no anterior al hito previo del mismo registro.»

---

### E-ERR-16 · «Casos por localidad» del tablero fusiona localidades homónimas de municipios distintos y su enlace filtra solo una
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** nuevo · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** E3-ERR-06
- **Ubicación:** `programas/selectors/emergencia_tablero.py:547-549` (agrupa por nombre normalizado y pisa `localidad_id` con el último caso), `:566` (`?localidad=<un solo id>`).
- **Escenario:** `core.Localidad` es único por `(nombre, municipio)` (`core/models/base.py:88-90`), así que puede haber dos «Colonia Elisa» en municipios distintos. Los casos de ambas caen en **una** fila; los contadores suman las dos y el enlace «a la bandeja» filtra solo por el id del último caso leído, que muestra menos casos que los que la fila cuenta.
- **Causa raíz:** el cruce con los dispositivos (texto libre) obliga a agrupar por nombre, y la fila guarda un solo `localidad_id`.
- **Solución:** sin cambiar la agrupación por nombre: guardar el conjunto de ids (`actual.setdefault("ids", set()).add(caso.localidad_id)`) y armar el enlace solo si hay **un** id (`url = … if len(ids) == 1 else ""`); con varios, sin enlace (como las filas sin `core.Localidad`). Misma estética.
- **Tests a agregar:** `programas/tests/test_emergencia_tablero.py::PorLocalidadTest.test_homonimas_no_enlazan_a_una_sola`.
- **Verificación:** el test.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/correccion-seguridad.md` · «Agrupar por un nombre que no es único en el modelo pierde la identidad: el enlace de la fila no puede elegir un id al azar.»

---

### E-PERF-06 · El tablero trae todas las entregas en camino con todas sus líneas para mostrar 20
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** PERF · **Origen:** fusión de E-PERF-06 · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** E3-PERF-03 + E3-ERR-07
- **Fusión (juez):** absorbe E-PERF-06 y la segunda parte de E-LIM-50 (misma consulta: `entregas_en_camino` trae todas las `EN_CAMINO` con las líneas para dibujar 20). La solución elegida toma el total de `foto.entregas_en_camino` (2 consultas), no un `COUNT` aparte (ver «Contradicciones» de la sección 1).
- **Ubicación:** `programas/selectors/emergencia_tablero.py:656-677` (`entregas_en_camino`), llamada en `programas/views/emergencia_tablero.py:36`.
- **Escenario:** en un pico de distribución hay 300 entregas `EN_CAMINO` con 5-10 líneas. Cada carga del tablero materializa las 300 (`list(...)`, línea 656) y el `prefetch` trae sus ~3.000 líneas con el ítem, para dibujar `entregas[:tope]` (20, línea 663). El total (`len(entregas)`, línea 677) ya lo tiene la foto: `foto.entregas_en_camino`, contado en `_entregas()` (líneas 351-354).
- **Causa raíz:** el recorte a `TOPE_ENTREGAS` se hace en Python después del `prefetch`; y el filtro `estado = EN_CAMINO` no tiene índice que empiece por `estado` (E-PERF-07), así que además recorre `EntregaKit` entera.
- **Consultas/filas estimadas:** 2 consultas; las filas crecen con las entregas en camino × líneas por entrega. Con el volumen supuesto, cientos a pocos miles: sin riesgo de timeout, costo de memoria y red evitable.
- **Solución (preserva lógica y pantalla):** recortar en la base y tomar el total de la foto: `entregas = list(qs[:tope])` (el `prefetch` se aplica solo a esas 20) y `total = foto.entregas_en_camino` (pasándole la foto como a los demás selectores) o un `qs.count()` si se quiere mantener la firma. Mismo orden, mismas filas, mismo «y N más».
- **Tests a agregar:** `programas/tests/test_emergencia_tablero.py::EntregasEnCaminoTest.test_prefetch_solo_de_las_que_se_muestran` (con 30 en camino, el `IN` del prefetch lleva 20 ids).
- **Verificación / medición:** con 300 entregas `EN_CAMINO` sembradas, `CaptureQueriesContext` sobre `entregas_en_camino` y contar los ids del `IN`; no hace falta el banco.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas activas · agregar «`list(qs)` seguido de `[:n]` en Python: el recorte va en el queryset, antes del `prefetch_related`».

#### Aporte del segundo revisor (E3-ERR-07: El tablero trae todas las entregas en camino con sus líneas para listar 20)
_Pasada 1: severidad BAJA · estado CONFIRMADO (lectura) · esfuerzo S._

- **Ubicación:** `programas/selectors/emergencia_tablero.py:656-677` (`entregas_en_camino`).
- **Escenario:** en un evento grande con 300 entregas `EN_CAMINO` (la mesa marca y el dispositivo tarda en recibir), cada carga del tablero lee las 300 entregas y **todas** sus líneas con el ítem (`prefetch`) para dibujar 20 y contar el resto. Crece con el evento contra el `read_timeout` de 10 s de ECOM.
- **Causa raíz:** el total se calcula con `len()` sobre la lista completa en vez de un `COUNT`, y el `prefetch` se aplica antes del corte.
- **Solución:** `qs = EntregaKit.objects.filter(estado=EN_CAMINO)`; `total = qs.count()`; `entregas = list(qs.select_related("dispositivo").prefetch_related(...).order_by("despachada_en", "id")[:tope])`. 3 consultas en vez de 2, acotadas; mismo resultado. Ajustar el presupuesto del docstring y de `test_emergencia_tablero`.
- **Tests a agregar:** `programas/tests/test_emergencia_tablero.py::EntregasEnCaminoTest.test_presupuesto_no_crece_con_las_entregas` (`@tag("performance")`, 20 vs 300 entregas, mismas consultas y filas prefetcheadas ≤ 20).
- **Verificación:** el test de presupuesto.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/` · «Para "primeras N + total" se cuenta con `COUNT` y se corta antes del `prefetch`; nunca `len()` sobre la lista entera.»

---

### E-PERF-07 · Derivaciones y entregas se filtran por `estado` sin un índice que empiece por `estado`
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** PERF · **Origen:** nuevo · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** E3-PERF-04
- **Ubicación:** `programas/selectors/emergencia_tablero.py:322` (`_derivaciones_pendientes`), `:347` (`_entregas`, con el `NOT EXISTS` de `q_entrega_sin_revisar`, 336-337), `:657` (`entregas_en_camino`); `programas/services/vencimientos_emergencia.py:103` (`derivaciones_vencidas`, cron). Índices: `programas/models/__init__.py:6055-6058` y `:6383-6386`.
- **Escenario:** cada carga del tablero filtra `Derivacion` por `estado = PENDIENTE` y `EntregaKit` por estado dos veces. El único índice compuesto de cada tabla es `(dispositivo, estado)`, que no sirve para buscar por `estado` solo: recorrido completo de las 15.000 derivaciones y de las 20.000 entregas por carga (más un `NOT EXISTS` sobre `TrazaEntrega` por cada recibida con diferencias). El cron `emergencia.derivacion` hace lo mismo con `estado + vence_en`; hoy corre una vez por día, pero el pendiente registrado (`docs/internal/requerimientos.md:55197`, «Frecuencia del cron») es pasarlo a cada 5 minutos: ahí son 288 recorridos diarios de `Derivacion`.
- **Causa raíz:** los índices se diseñaron para la vista del dispositivo (`dispositivo = ? AND estado = ?`), no para las vistas globales de la mesa y del cron.
- **Consultas/filas estimadas:** 3 consultas del tablero + 1 del cron; ~15.000 + 2×20.000 filas leídas por carga, lineal con el histórico. Con el volumen supuesto son milisegundos: BAJA; sube si el histórico se multiplica.
- **Solución (preserva lógica):** migración expand-only con `AddIndex`: `Derivacion` `Index(fields=["estado", "vence_en"])` (sirve al tablero, que ordena por `vence_en`, y al cron); `EntregaKit` `Index(fields=["estado", "recibida_en"])` (`_entregas()` ordena por `recibida_en`). Si se hace E-PERF-05, su `(estado, creado, id)` ya cubre los filtros por estado y este solo suma el orden por `recibida_en`.
- **Lo que NO hay que hacer:** reordenar el índice existente `(dispositivo, estado)` a `(estado, dispositivo)`: lo usan la guardia (`llegadas_del_dispositivo`, `entregas_pendientes_de`) y sería un `RemoveIndex` que pide contract.
- **Tests a agregar:** ninguno de comportamiento; `makemigrations --check` y `check_migraciones.py` los corre el CI.
- **Verificación / medición:** con la siembra de E-PERF-03/02, `EXPLAIN` de `Derivacion.objects.filter(estado="PENDIENTE").order_by("vence_en", "id")` y de `EntregaKit.objects.filter(Q(estado="EN_CAMINO") | q_entrega_sin_revisar())`: antes `type=ALL`, después `ref`/`range` sobre el índice nuevo.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` §Índices · «Un índice `(a, b)` no sirve para `WHERE b = ?`. Si una vista global (mesa, tablero, cron) filtra por `estado` sin el primer campo, necesita su propio índice que empiece por `estado`.»

---

### E-PERF-08 · Tres consultas fijas de la bandeja recorren todos los casos en cada carga
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** PERF · **Origen:** nuevo · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** E1-PERF-04
- **Ubicación:** `programas/selectors/emergencia.py:366-370` (`conteo_por_solapa`: `aggregate` con 9
  `Count(filter=…)` sobre toda la tabla); `programas/selectors/emergencia_mesa.py:138`
  (`localidades_con_casos`: `Localidad JOIN casoemergencia … DISTINCT … ORDER BY nombre`);
  `programas/views/emergencia.py:110` y `:126`.
- **Escenario:** cada apertura de E2 y cada redirect de «Soltar» (`views/emergencia.py:285-286`) corren el
  agregado —que necesita `estado` **y** `origen` (solapa «Ingreso directo») y no tiene índice que los
  cubra → scan del índice clustered de 10.000 filas, con los JSON en la página— y las localidades, que
  unen cada caso con su localidad y deduplican (10.000 filas de JOIN para devolver ~70). Estimado: 10–30
  ms cada una con 10.000 casos; lineal con el historial. Sin riesgo de 500 con el volumen supuesto.
- **Causa raíz:** contar y listar sobre el historial completo sin un índice que cubra lo que se lee.
- **Solución (preserva lógica):** `models.Index(fields=["estado", "origen"])` en `CasoEmergencia`
  (`AddIndex`, expand): el agregado pasa a scan del índice secundario, que ya incluye `id`. Localidades:
  `Localidad.objects.filter(pk__in=CasoEmergencia.objects.values("localidad_id")).order_by("nombre")` →
  semi-join sobre el índice de la FK, sin traer filas de casos; mismo resultado.
- **Tests a agregar:** `programas/tests/test_emergencia_mesa.py::BandejaTest.test_localidades_con_casos_sin_duplicados`.
- **Verificación:** `EXPLAIN` en el banco: el agregado con `key=…estado_origen…` y `Extra: Using index`;
  las localidades sin `Using temporary`.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` §Índices · «Un conteo
  por solapa que corre en cada carga va con un índice que cubra **todas** las columnas de sus `filter=`:
  si falta una, es un scan de la tabla con sus JSON.»

---

### E-PERF-09 · Dos aceptaciones simultáneas en el mismo dispositivo eligen las mismas camas y la segunda espera el candado para fallar siempre
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** PERF · **Origen:** nuevo · **Ola:** 2 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E2-PERF-02
- **Ubicación:** `programas/services/emergencia_recepcion.py:248` y `:257` (`aceptar_derivacion`), `programas/services/emergencia_sin_derivacion.py:102` y `:128` (`ingreso_directo`), orden determinista en `programas/selectors/emergencia_alojar.py:138-142`, candado en `programas/services/reservas_derivacion.py:157`.
- **Escenario:** crecida, el Club recibe a la vez a la familia A (derivada) y a la B (llega sola). La guardia 1 toca «Aceptar» de A y la guardia 2 «Ingresar igual» de B con un segundo de diferencia. Las dos llaman a `camas_libres` **sin candado** y, en READ COMMITTED, ven la misma foto (las reservas de la otra todavía no están commiteadas); el orden es determinista (sector con más libres, código natural), así que las dos piden las **mismas** primeras N camas. La segunda queda en el `SELECT … FOR UPDATE` de la primera cama común hasta que la primera commitea (unas 4 consultas por cama, más filas, traza y bitácora: 0,1 a 0,5 s), y al despertar `_exigir_plaza_libre` encuentra la reserva: `CAMAS_TOMADAS_MIENTRAS_ACEPTABA`, rollback, y la guardia vuelve a tocar. Con k guardias concurrentes en el mismo centro, k-1 fallan en cada ronda.
- **Causa raíz:** elegir sin candado con un orden determinista hace que la colisión no sea mala suerte sino segura cuando hay concurrencia. El no reintento es deliberado y está bien fundado (`ROLLBACK TO SAVEPOINT` no suelta locks; docstring de `programas/services/emergencia_alojar.py:66-69`), pero no hay reintento **afuera** de la transacción.
- **Con qué crece:** con la concurrencia de operadores por dispositivo, no con el volumen de datos. La espera está acotada por la transacción ganadora (no llega a 10 s con los caminos actuales); el costo real es el fallo y el reintento manual.
- **Solución:** mantener la regla y las camas elegidas: desde la vista y la API (fuera del `@transaction.atomic`), **un** reintento automático cuando la excepción es exactamente `ValidationError({"plazas": CAMAS_TOMADAS_MIENTRAS_ACEPTABA})`; el segundo intento relee `camas_libres` con lo ya commiteado y elige con la misma regla. Es lo que hoy hace la guardia a mano. Alternativa sin tocar las vistas: un decorador `reintentar_si_camas_tomadas(veces=1)` por **encima** de `@transaction.atomic` en `aceptar_derivacion` e `ingreso_directo` (en `ingreso_directo`, después de la idempotencia por `uuid_cliente`, que ya lo cubre).
- **Lo que NO hay que hacer:** reintentar adentro de la misma transacción (rompe «todas las plazas de una vez, por pk»), ni `SKIP LOCKED` en la elección: cambia qué camas recibe la familia y deja de quedar junta en el sector con más libres.
- **Tests a agregar:** `programas/tests/test_emergencia_alojar.py::AceptarConcurrenteTests.test_reintenta_una_vez_si_le_tomaron_las_camas` (mock de `reservar_plazas_de_derivacion` que falla la primera vez con el error de plaza).
- **Verificación:** dos sesiones en el banco MariaDB: sembrar 1 dispositivo con 20 camas y 2 derivaciones PENDIENTE; S1 `BEGIN; SELECT id FROM programas_plaza WHERE id IN (<las 4 primeras de camas_libres>) ORDER BY id FOR UPDATE;` más un `INSERT` de reserva sobre la primera, sin commit; en paralelo, desde `manage.py shell`, `aceptar_derivacion(derivacion=B, usuario=...)` midiendo espera y resultado; `COMMIT` en S1: hoy debe dar `CAMAS_TOMADAS_MIENTRAS_ACEPTABA`, con el reintento, éxito con las camas siguientes.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` §Transacciones y bloqueos · «Si se elige sin candado y después se bloquea lo elegido, con un orden determinista dos pedidos concurrentes eligen lo mismo: el perdedor no reintenta adentro (los locks no se sueltan), pero sí una vez **afuera** de la transacción.»

---

### E-PERF-10 · Reservar las camas de la familia valida cada cama con dos consultas propias mientras las tiene todas tomadas
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** PERF · **Origen:** nuevo · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** E2-PERF-03
- **Ubicación:** `programas/services/reservas_derivacion.py:163-170` (bucle con `_exigir_plaza_libre`) y `:175-189` (`_crear_reserva` por cama); las consultas por cama en `programas/services/estadias.py:294` y `:296-299`.
- **Escenario:** aceptar una familia de 12 (o un ingreso directo de 12): con caso, derivación y las 12 plazas `FOR UPDATE`, el bucle hace 2 lecturas por cama (estadía activa con `EXISTS` y reserva que toma con `LIMIT 1`): 24, más 12 `INSERT` de reserva y 12 de traza. Todo bajo candado; las demás guardias que quieren cualquiera de esas camas esperan (agrava E-PERF-09).
- **Causa raíz:** se reutiliza el control de a una plaza (`_exigir_plaza_libre`) en un camino de varias.
- **Con qué crece:** con `plazas_pedidas` (tamaño de la familia, hasta unas 15), no con el histórico: cada consulta va por el índice `(plaza, estado)`. Estimado: 20 a 30 ms extra bajo candado. Por eso BAJA y no la MEDIA de la tabla de la rúbrica, que está pensada para listados.
- **Solución:** con las plazas ya bloqueadas, dos consultas para todas: `Estadia.objects.activas().filter(plaza_id__in=ids).values_list("plaza_id", flat=True)` y `ReservaPlaza.objects.que_toman(ahora).filter(plaza_id__in=ids).values_list("plaza_id", "tipo")`; después el mismo recorrido por `bloqueadas`, con los mismos mensajes y el mismo orden de chequeo (sector dado de baja, fuera de servicio, «ya tiene una estadía activa / un préstamo vigente / una reserva vigente»). Los `INSERT` quedan como están: la traza por cama es parte del contrato.
- **Tests a agregar:** `programas/tests/test_dispositivos_reservas_derivacion.py::PresupuestoTests.test_reservar_n_camas_lecturas_fijas` (mismas lecturas con 1 y con 12 camas, sin contar los `INSERT`).
- **Verificación:** entrada nueva en `scripts/perf_budgets.json` («emergencia_reservar_plazas_de_derivacion», lecturas fijas) y `assertNumQueries` con 1 y con 12 camas.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas activas · «Un control "de a una fila" (`_exigir_plaza_libre`, `_plaza_tomada_por`) llamado dentro de un bucle con las filas ya bloqueadas: va en una consulta con `__in`.»

---

### E-PERF-11 · «Familia en la puerta» busca en todos los casos no cerrados en vez de en los de la foto
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** PERF · **Origen:** nuevo · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** E3-PERF-05
- **Ubicación:** `programas/services/avisos_emergencia.py:347-352` (`familias_en_la_puerta`); el filtro es `CasoEmergencia.q_esperando_en_la_puerta()` (`programas/models/__init__.py:5877-5882`).
- **Escenario:** la foto ya trae los casos abiertos sin derivar (`sin_derivar`, línea 344; en pico, cientos). La consulta no se acota a esos ids: pide `NOT estado = CERRADO AND derivado_en IS NULL AND JSON_CONTAINS_PATH(situacion, …)` sobre toda la tabla y decodifica la columna JSON `situacion` de cada caso que pasa. Con el `<>`, el plan puede ir por el rango de `(estado, prioridad)` o recorrer la tabla. Es la segunda lectura del histórico de casos por carga del tablero (la primera es E-PERF-03).
- **Causa raíz:** el filtro se escribió como regla del modelo (reutilizable en E2/E3) y acá se aplica sin el alcance que ya se tiene.
- **Consultas/filas estimadas:** 1 consulta (solo si hay abiertos sin derivar, que en una emergencia es siempre); filas = casos no cerrados con `derivado_en` nulo, con JSON por fila. Con el volumen supuesto, chico.
- **Solución (preserva lógica):** agregar `.filter(pk__in=[caso.id for caso in sin_derivar])` antes del `.only(...)`: búsqueda por PK y mismo resultado (los candidatos ya se intersectan con `sin_derivar` en la línea 353).
- **Tests a agregar:** `programas/tests/test_emergencia_tablero.py::AvisosTest.test_en_la_puerta_se_acota_a_la_foto` (el SQL capturado lleva `id IN (...)`).
- **Verificación / medición:** `CaptureQueriesContext`; en el banco, `EXPLAIN` antes y después con 10.000 casos sembrados.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas activas · «Una regla del modelo (`q_*`) aplicada en un selector que ya tiene los ids candidatos se acota con `pk__in`: el filtro JSON corre solo sobre esas filas.»

---

### E-PERF-12 · La lista de entregas pendientes de un dispositivo no tiene tope
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** PERF · **Origen:** fusión de E-PERF-12 · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** E4-PERF-01 + E4-LIM-15
- **Ubicación:** `programas/api/views_emergencia_kits.py:108-109` (`?pendientes=1` sin recorte; la otra rama sí
  corta en `TOPE_ENTREGAS = 50`, `:39` y `:111`); `programas/selectors/kits.py:262-277` (`entregas_pendientes_de`,
  con `prefetch_related` de líneas e ítems); contrato §10 (`docs/internal/contrato-app-emergencia.md:392-393`,
  «sin tope»).
- **Escenario:** la mesa despacha entregas a un centro y nadie las recibe ni las cancela (se recibieron en
  papel, la guardia cambió, el centro cerró). `EN_CAMINO`/`PREPARADA` no vencen solas: solo salen por
  `recibir_entrega` o `cancelar_entrega` (`programas/services/kits.py:380`). Cada apertura de M3-1 trae
  **todas** las abiertas con **todas** sus líneas.
- **Con qué crece:** entregas abiertas sin cerrar del dispositivo × líneas por entrega. Consultas: fijas
  (2 + la del alcance; las líneas van por `Prefetch` con `select_related("item")`, sin N+1). Filas: con un
  uso normal, decenas; el índice `(dispositivo, estado)` de `EntregaKit` las encuentra sin recorrer las
  recibidas. No hay riesgo de 500 a la escala supuesta: por eso INFO. Es el único listado de la API sin
  tope cuyo tamaño no lo acota la realidad física (familia, camas del dispositivo, dispositivos de la red).
- **Causa raíz:** el recorte de 50 se puso solo en la rama histórica, porque «pendientes» se supuso
  chico; nada en el modelo lo garantiza.
- **Solución (solo si la medición lo pide; preserva lógica):** aplicar el mismo `TOPE_ENTREGAS` también a
  `?pendientes=1` (`entregas_pendientes_de(...)[:TOPE_ENTREGAS]` en la vista), manteniendo el orden de la
  más vieja a la más nueva. Cambia el contrato («sin tope» pasa a «hasta 50»): si hace falta ver más de 50
  pendientes, `DECISIÓN CLIENTE: tope de 50, con la más vieja primero`.
- **Lo que NO hay que hacer:** paginar con el `PageNumberPagination` por defecto de DRF (`PAGE_SIZE: 10`):
  la app de producción no lee `results` y se rompería el contrato.
- **Tests a agregar:** `programas/tests/test_emergencia_api_kits.py::EntregasDelDispositivoTest.test_pendientes_respeta_el_tope`.
- **Verificación:** sembrar 1 dispositivo con 500 `EntregaKit` `EN_CAMINO` de 8 líneas y medir
  `GET reverse("emergencia_api:dispositivo-entregas", args=[disp.pk]) + "?pendientes=1"` en
  `scripts/perf_mysql/bench_mysql.py` (actor: guardia con `emergencia.recibir_kit` en el Equipo); mirar el
  tamaño del JSON y el `EXPLAIN` del `SELECT` de `programas_entregakit` (`key` = el índice
  `(dispositivo, estado)`, `Using filesort` solo sobre esas filas).
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas
  activas · «Todo listado de la API de campo lleva tope explícito en **cada** rama; un “solo las
  pendientes” no es un tope si el estado no vence solo.»

#### Aporte del segundo revisor (E4-LIM-15: `?pendientes` se parsea a mano y el tope de la lista se aplica en la vista)
_Pasada 1: severidad BAJA · estado CONFIRMADO (lectura) · esfuerzo S._

- **Ubicación:** `programas/api/views_emergencia_kits.py:39`, `:106-112`.
- **Escenario:** `request.query_params.get("pendientes") in ("1", "true", "True")` es un parser de booleano propio
  (`"TRUE"`, `"yes"`, `"on"` dan la otra rama), y `TOPE_ENTREGAS` + el slicing `[:TOPE_ENTREGAS]` son de la consulta,
  no de HTTP (en M1 el tope análogo `TOPE_MIS_CASOS` sí vive en el selector, `selectors/emergencia_campo.py:11`).
- **Solución:** mover el tope a `selectores_kits.entregas_recientes_de(dispositivo)` como en M1; mantener la tupla de
  valores aceptados tal cual (cambiarla altera el contrato) pero en una constante con nombre junto al parámetro.
- **Verificación:** la vista no rebana querysets.
- **Regla para no repetirlo:** **skill** · rúbrica `codigo-limpio.md` · «Topes de listas en el selector, no en la vista.»

---

### E-LIM-32 · «La derivación vigente del caso» se consulta con tres consultas escritas a mano
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** thermos E1 · **Ola:** 4 · **Esfuerzo:** S
- **ID de la pasada 1:** E1-LIM-12
- **Ubicación:** `programas/services/emergencia.py:489` (`_mensaje_ya_derivado`), `programas/selectors/emergencia_mesa.py:502-509` (`derivacion_pendiente_de`) y `:512-515` (`_derivacion_vigente`), cada uno con `Derivacion.objects.filter(clave_vigente=caso.pk)…` y su propio `select_related`.
- **Escenario:** la convención «vigente = `clave_vigente` no nula» es un detalle de cómo se implementó el UNIQUE (RN-2.6). Si cambia, por ejemplo a una columna `vigente` booleana, hay que encontrar las tres copias.
- **Causa raíz:** no hay un manager con nombre de dominio para esta lectura, cuando `Estadia` sí tiene `de_la_red`.
- **Solución:** sumar al manager de `Derivacion` los métodos `vigente_de(caso)` (`filter(clave_vigente=getattr(caso,"pk",caso))`) y `pendiente_de(caso)`. Los tres sitios los usan con su `select_related` actual. Mismas consultas, mismo presupuesto.
- **Tests a agregar:** ninguno. Los presupuestos de `assertNumQueries` de E3 lo cubren.
- **Verificación:** `grep -rn "clave_vigente=" programas --include=*.py | grep -v models | grep -v tests` sin resultados.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md` · «Una condición que codifica un invariante de modelo (clave de vigencia, clave de alojamiento) se lee por un método del manager».

---

### E-LIM-33 · La respuesta de la recepción de kits no pasa por el serializer que la documenta
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 5 · **Esfuerzo:** S
- **ID de la pasada 1:** E4-LIM-06
- **Ubicación:** `programas/api/views_emergencia_kits.py:132`, `:175-182`; `programas/api/serializers_emergencia.py:354-368`.
- **Escenario:** el esquema publica `RecepcionKitRespuestaSerializer` (con `DiferenciaDeRecepcionSerializer`), pero la
  vista devuelve `Response(cuerpo)` con un dict armado a mano y proyecta `{item, enviada, recibida}` en un
  comprehension. Es la única respuesta de éxito del namespace que no se serializa: el esquema y la respuesta real pueden
  divergir sin que Spectacular lo note (el test de contrato de claves lo mitiga, por eso BAJA). La misma cadena
  `diferencias_de(lineas_de(recibida))` está en `programas/views/emergencia_kits.py:624`.
- **Solución:** `return Response(RecepcionKitRespuestaSerializer({"estado": recibida.estado, "diferencias": diferencias}).data)`:
  el serializer ya proyecta los tres campos y descarta el resto. Salida idéntica.
- **Verificación:** test de contrato de `entrega-recibir` en verde.
- **Regla para no repetirlo:** **skill** · rúbrica `codigo-limpio.md` · «Toda respuesta 2xx de la API de campo sale de
  `Serializer(...).data` del mismo serializer que declara `@extend_schema`.»

---

### E-LIM-34 · Relectura del caso con ORM en las vistas y el mismo cuerpo «reservadas/faltantes/integrantes» armado dos veces
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** los atributos `reservadas`, `faltantes`, `ya_existia`, `ya_estaba` son E-LIM-20 (no se repite) · **Ola:** 5 · **Esfuerzo:** S
- **ID de la pasada 1:** E4-LIM-08
- **Ubicación:** `programas/api/views_emergencia_llegadas.py:144-147` (`_filas`, con `CasoEmergencia.objects...get`),
  `:211-219`; `programas/api/views_emergencia_sin_derivacion.py:28` (importa `_filas`), `:77-84`, `:128`
  (la misma consulta inline); `programas/api/serializers_emergencia.py:590-595` (`AceptacionSerializer`) y `:747-751`
  (`IngresoDirectoSerializer`).
- **Escenario:** el módulo de vistas tiene una función que consulta el ORM (`_filas`), otra vista repite la consulta a
  mano, y `AceptarDerivacionView` / `IngresoDirectoView` arman el mismo dict `{caso, reservadas, faltantes, integrantes}`
  para dos serializers que difieren solo en `mensaje`.
- **Causa raíz:** la lectura posterior a la escritura no tiene dueño en `selectors/`.
- **Solución:** `selectores_alojar.caso_con_integrantes(caso_pk)` (las mismas 2 consultas) reemplaza `_filas` y la
  consulta inline; un helper `_cuerpo_de_reserva(resultado)` arma el dict; `IngresoDirectoSerializer` pasa a ser
  `AceptacionSerializer` sin `mensaje` (subclase o `fields` explícitos), conservando el nombre de componente de
  Spectacular si el contrato lo fija.
- **Tests a agregar:** ninguno nuevo; presupuestos de consultas existentes de M2-2 y M2-6 tienen que seguir iguales.
- **Verificación:** `grep -n "objects\." programas/api/views_emergencia*.py` sin resultados.
- **Regla para no repetirlo:** **control mecánico** · test ratchet: ningún `programas/api/views_*.py` contiene
  `.objects.` (AST `Attribute(attr="objects")`), con lista de excepciones congelada. Mensaje: «La vista de API no
  consulta el ORM: va a `selectors/`.»

---

### E-LIM-35 · Las vistas del backoffice importan del paquete de la API para filtrar el rechazo por DNI
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** thermos E1 · **Ola:** 5 · **Esfuerzo:** S
- **ID de la pasada 1:** E1-LIM-18
- **Ubicación:** `programas/views/emergencia.py:29` y `programas/views/emergencia_dispositivo.py:43` importan `rechazo_para_mostrar` de `programas/api/throttles.py:48`. El propio docstring dice que es «la mitad del backoffice».
- **Escenario:** el backoffice depende del paquete de la API para un control de privacidad (SEC-25). Quien reorganice `api/` puede mover o romper la protección del nombre en la web sin tocar ninguna vista.
- **Causa raíz:** el contador de consultas de identidad nació en la API y la mitad web se agregó al lado.
- **Solución:** mover `descontar_consulta_de_identidad` y `rechazo_para_mostrar` a `programas/services/identidad_cupo.py` (o junto a `services/identidad.py`). `api/throttles.py` los reexporta. Mismo comportamiento.
- **Tests a agregar:** `test_arquitectura.py::...::test_las_vistas_no_importan_de_api`.
- **Verificación:** ese test.
- **Regla para no repetirlo:** **control mecánico** · `test_arquitectura.py` · «`programas/views/` no importa de `programas/api/`».

---

### E-LIM-36 · La fachada `emergencia_alojar` tiene dos rutas de importación, reexporta la ficha y conserva un envoltorio muerto
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 6 · **Esfuerzo:** S
- **ID de la pasada 1:** E2-LIM-05
- **Ubicación:**
  - `programas/services/emergencia_alojar.py:108-194`.
  - Los callers que se la saltean: `programas/api/serializers_emergencia.py:32` y
    `programas/selectors/emergencia_llegadas.py:21`. Los dos importan `derivacion_vencida` de
    `emergencia_ingreso_comun`, aunque la fachada lo reexporta.
  - El envoltorio: `programas/services/emergencia_sin_derivacion.py:199-202`.
- **Escenario:**
  - La fachada declara «se importa y se parcha **donde vive**», pero 7 módulos importan desde la fachada y
    2 desde el submódulo, así que un `mock.patch` sobre una ruta no cubre a quien entró por la otra.
  - Reexporta 31 nombres de `emergencia_ficha` (`BOOLEANO`, `SECCION_*`, `ESQUEMA_FICHA`…), que no son de la
    etapa. `forms_emergencia_dispositivo.py:9` documenta que lee `emergencia_alojar.ESQUEMA_FICHA`.
  - `es_ingreso_directo(caso)` devuelve `caso.es_ingreso_directo` y nada más. Solo lo llaman
    `programas/tests/test_emergencia_sin_derivacion.py:65,172`.
  - `SITUACION_*` (`:192-194`) son alias de constantes del modelo «para quien las leía desde acá».
- **Causa raíz:** la fachada quedó de la época en que todo vivía en un solo archivo. Nunca se decidió si es
  la API pública o solo un índice.
- **Solución:** decidir que es **la** API pública de la etapa:
  - `serializers_emergencia` y `selectors/emergencia_llegadas` importan desde la fachada.
  - Quitar los reexportes de la ficha: `forms_emergencia_dispositivo` importa de `emergencia_ficha`.
  - Borrar `es_ingreso_directo`: los tests usan la propiedad del modelo.
  - Borrar los alias `SITUACION_*` cuando sus lectores pasen a `CasoEmergencia.SITUACION_*`
    (verificar con grep antes).

  No cambia comportamiento.
- **Lo que NO hay que hacer:** borrar la fachada entera. `apps.py` y 7 módulos dependen de ella, y es útil como
  índice de la etapa.
- **Tests a agregar:** ninguno nuevo. Hay que ajustar `test_emergencia_sin_derivacion.py:65,172` para que use
  `caso.es_ingreso_directo`.
- **Verificación:** `grep -rn "emergencia_ingreso_comun import" programas --include=*.py | grep -v services/emergencia_`
  sin resultados.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` · «Si un módulo es
  fachada, todo caller externo importa desde ella; una función que solo devuelve un atributo del modelo no se
  crea.»

---

### E-LIM-37 · La regla de «cama libre» y el armado del mapa por sector están escritos dos veces
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** LIM · **Origen:** nuevo · **Ola:** 6 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E2-LIM-09
- **Ubicación:**
  - `programas/selectors/emergencia_alojar.py:115-142` (`camas_libres`, en Python vía `estado_de_plazas`) contra
    `:166-185` (`resumen_de_llegadas`, en SQL a mano con `Exists`).
  - `programas/selectors/emergencia_alojar.py:215-304` (`plazas_para_caso`) contra
    `programas/services/ingreso.py:129-181` (`plazas_para_ingresar`).
  - `TOPE_PLAZAS_POR_SECTOR = 200` está definido tres veces: `selectors/emergencia_alojar.py:79`,
    `services/ingreso.py:44` y `services/sectores_plazas.py:89`.
- **Escenario:** el docstring de `resumen_de_llegadas` (`:152-156`) reconoce que es «la misma cuenta que
  `camas_libres`, hecha en la base». Si `estado_de_plazas` cambia su precedencia (por ejemplo, para considerar
  préstamos u otro tipo de reserva), el contador de «mis dispositivos» y la lista que usa `aceptar_derivacion`
  divergen: la app muestra «3 libres» y aceptar dice «Sin plazas». Los dos mapas por sector agrupan, ordenan
  con `clave_natural`, cortan en el tope y cuentan libres, cada uno con su propia forma de dict.
- **Causa raíz:** la cuenta en SQL se escribió para no pagar `estado_de_plazas` por cada dispositivo, pero no
  existe un queryset canónico de «cama libre» que puedan usar los dos.
- **Solución:** crear `Plaza.objects.camas_libres(momento)` en el manager, con los `exclude` de
  `resumen_de_llegadas`. `resumen_de_llegadas` lo agrupa, y `camas_libres` lo usa para el filtro y ordena en
  Python como hoy. El tope queda en una única constante en `ocupacion.py`.

  **Antes de tocar, hay que probar la equivalencia** con un test que compare las dos rutas sobre todos los
  estados de plaza. Por eso el estado es PLAUSIBLE.
- **Lo que NO hay que hacer:** unificar `plazas_para_caso` con `plazas_para_ingresar` en una sola función con
  flags. Los contratos de salida son distintos (app frente a template).
- **Tests a agregar:** `programas/tests/test_emergencia_alojar.py::CamasLibresTest.test_resumen_y_lista_cuentan_igual`.
- **Verificación:** el test nuevo queda en verde y se respetan los presupuestos de `assertNumQueries` vigentes.
- **Regla para no repetirlo:** **control mecánico** · `programas/tests/test_arquitectura.py` · un test
  `test_tope_plazas_por_sector_tiene_un_solo_dueno`, con el mismo patrón que
  `test_la_constante_de_la_capacidad_publica_tiene_un_solo_dueno`.

---

### E-LIM-38 · Las nueve acciones de la mesa repiten el mismo preludio de guardas
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** thermos E1 · **Ola:** 6 · **Esfuerzo:** M
- **ID de la pasada 1:** E1-LIM-13
- **Ubicación:** `programas/services/emergencia.py:325-340` (tomar), `:352-369` (soltar), `:428-446` (prioridad), `:458-479` (contacto), `:519-571` (derivar), `:585-617` (cancelar) y `:742-768` (cerrar). Todas hacen `_exigir_mesa` → `_bloquear_caso` → `_exigir_abierto`/`_exigir_estado` → `por_supervisor = _exigir_duenio_o_supervisor` → mutación → `_trazar(..., por_supervisor=por_supervisor)`.
- **Escenario:** el contrato de cuatro pasos del docstring (`:12-25`) se cumple por disciplina y no por estructura. Una acción nueva que olvide `_exigir_duenio_o_supervisor`, o que lo llame antes del candado, pasa la revisión si nadie la compara línea por línea.
- **Causa raíz:** el patrón se documentó, pero no se encapsuló.
- **Solución:** extraer un helper `_bloquear_para_actuar(caso, usuario, *estados, mensaje) -> (caso, por_supervisor)` que haga candado, estado y dueño o supervisor en ese orden. Las validaciones de entrada (motivo, prioridad, plazas) siguen **antes**, en cada función, como hoy. `tomar`, `reasignar` y los dos del cron quedan fuera porque tienen reglas propias. Son unas 40 líneas menos y el orden queda fijo en un lugar.
- **Lo que NO hay que hacer:** un decorador mágico que inyecte `caso`. Esconde que se devuelve la fila **bloqueada** y no la que llegó.
- **Tests a agregar:** los de `OrdenDeLosCandadosEmergenciaTests` siguen fijando la secuencia. Sumar `test_toda_accion_de_mesa_exige_duenio_despues_del_candado`.
- **Verificación:** la suite de `test_emergencia_casos` y `test_emergencia_concurrencia` sin cambios.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md` · «Si un docstring describe un protocolo de N pasos que cada función repite, el protocolo es una función».

---

### E-LIM-39 · El catálogo de necesidades del Formulario 1 tiene tres fuentes
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** thermos E1 · **Ola:** 7 · **Esfuerzo:** S
- **ID de la pasada 1:** E1-LIM-07
- **Ubicación:** `programas/services/emergencia_alta.py:59-61` (`NECESIDADES` y `NECESIDADES_CRITICAS`, solo claves). `programas/selectors/emergencia_mesa.py:52-57` (`ROTULO_DE_NECESIDAD`). `programas/forms_emergencia.py:346-349` (cuatro `BooleanField` con el rótulo repetido a mano).
- **Escenario:** agregar «oxígeno domiciliario» exige tocar tres archivos y el serializer. Si falta el rótulo, `ROTULO_DE_NECESIDAD[clave]` en `emergencia_mesa.py:371` y `emergencia_llegadas.py:68` lanza `KeyError` y la ficha da 500.
- **Causa raíz:** las claves se definieron como tupla de strings y no como `TextChoices` con su `label`.
- **Solución:** en `emergencia_alta`, `class Necesidad(models.TextChoices)` con las cuatro y sus rótulos actuales, más `NECESIDADES = tuple(Necesidad.values)` para no romper importadores y `NECESIDADES_CRITICAS` igual. `ROTULO_DE_NECESIDAD = dict(Necesidad.choices)`. El form genera los cuatro campos en un bucle sobre `Necesidad.choices`, con el mismo widget y el mismo orden.
- **Tests a agregar:** `programas/tests/test_emergencia_casos.py::NecesidadesTests.test_cada_necesidad_tiene_rotulo_y_campo`.
- **Verificación:** ese test, y el HTML de «Nuevo caso» sin diferencias.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md` · «Un catálogo cerrado con rótulo es un `TextChoices`; no una tupla de claves más un dict de rótulos más campos escritos a mano».

---

### E-LIM-40 · `_marcas_de` está duplicada inline en `ids_por_estado_sla`
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** thermos E1 · **Ola:** 7 · **Esfuerzo:** S
- **ID de la pasada 1:** E1-LIM-14
- **Ubicación:** `programas/selectors/emergencia.py:164-171` (`_marcas_de`) y `:198-209` (el mismo dict, armado a mano desde `values_list`). Los nombres de las marcas también están en `TRAMOS` (`:54-59`).
- **Escenario:** si se suma un tramo (por ejemplo «egresar»), hay que tocar `TRAMOS`, `_marcas_de`, el `values_list` y el desempaquetado. Si se olvida uno, `KeyError` en el semáforo de toda la bandeja.
- **Causa raíz:** la lista de marcas no está derivada de `TRAMOS`.
- **Solución:** `CAMPOS_DE_MARCA = tuple(dict.fromkeys(c for _, abre, cierra, _ in TRAMOS for c in (abre, cierra)))`. `_marcas_de` queda como `{c: getattr(caso, c) for c in CAMPOS_DE_MARCA}`. En `ids_por_estado_sla`: `values_list("id", "estado", *CAMPOS_DE_MARCA)` y `dict(zip(CAMPOS_DE_MARCA, resto))`. Sigue siendo una consulta.
- **Tests a agregar:** ninguno. Los del semáforo y el `assertNumQueries` existentes cubren el cambio.
- **Verificación:** la suite del semáforo en verde.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md` · «Si hay una tabla de configuración (`TRAMOS`), las listas de campos se derivan de ella».

---

### E-LIM-41 · `responsables_alojados` no pasa por el manager `Estadia.objects.de_la_red`
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** thermos E1 · **Ola:** 7 · **Esfuerzo:** S
- **ID de la pasada 1:** E1-LIM-17
- **Ubicación:** `programas/selectors/emergencia.py:654` (`Estadia.objects.filter(clave_alojamiento__in=…)`). El canónico es `programas/models/__init__.py:1122` (`de_la_red`), que usa `services/estadias.py:235`.
- **Escenario:** hoy los dos son equivalentes. Si `de_la_red` suma una condición (por ejemplo, excluir estadías anuladas), la mesa va a seguir viendo «Responsable alojado en X» por una estadía que Dispositivos ya no cuenta.
- **Causa raíz:** el manager no tiene una variante en lote, y el selector escribió el filtro a mano.
- **Solución:** sumar al manager `de_la_red_en_lote(claves)` (`filter(clave_alojamiento__in=claves)`), definir `de_la_red` sobre él y usarlo en el selector. Es una sola consulta, como hoy.
- **Tests a agregar:** ninguno. El presupuesto de una consulta de `responsables_alojados` cubre el cambio.
- **Verificación:** `grep -rn "clave_alojamiento__in" programas --include=*.py` solo en `models`.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md` · «Si un modelo tiene un método de manager con nombre de dominio, las lecturas en lote usan su variante en lote; no el filtro crudo».

---

### E-LIM-42 · `configuracion_emergencia` mezcla lecturas con escritura: `sla_vigente()` hace INSERT en cada GET y `catalogo_kits` es un selector en un servicio
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 7 · **Esfuerzo:** S
- **ID de la pasada 1:** E3-LIM-10
- **Ubicación:** `programas/services/configuracion_emergencia.py:131-138` (`get_or_create` en una función que
  el docstring llama «de lectura», usada por el tablero `views/emergencia_tablero.py:34`, la bandeja y el
  detalle). `:166-169` (`catalogo_kits`), importada como lectura por `views/emergencia_kits.py:53` y `:317-349`.
- **Escenario:** la primera carga del tablero sobre una base sin fila de SLA escribe dentro de un GET. Con dos
  pestañas en paralelo en MariaDB, el `get_or_create` sin `UNIQUE`-retry puede dar `IntegrityError` (PLAUSIBLE:
  depende de que `programa` sea unique en `SLAEmergencia`). Además, el fallback esconde la invariante «el seed
  crea el SLA», que `ProgramaEmergenciaInexistente` sí hace explícita para el programa.
- **Solución:** la fila de SLA la crea la migración o `seed_emergencia` junto al programa. `sla_vigente()`
  pasa a `selectors/emergencia.py` como `get()` y, si falta la fila, devuelve un `SLAEmergencia()` sin guardar
  con los defaults de fábrica (mismo resultado visible). `guardar_sla` conserva su `get_or_create`.
  `catalogo_kits` pasa a `selectors/kits.py`.
- **Tests a agregar:** `programas/tests/test_emergencia_tablero.py::SinSLATest.test_get_no_escribe` (assertNumQueries sin INSERT).
- **Verificación:** test anterior.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md`: «Una función que el código llama "de lectura"
  no hace `get_or_create`; si falta el dato, eso es un seed».

---

### E-LIM-43 · Las siete reglas de aviso repiten el mismo esqueleto «tope 5 + Aviso + "y N más"»
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 7 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E3-LIM-11
- **Ubicación:** `programas/services/avisos_emergencia.py:103-376`: siete funciones con el mismo bucle
  `for x in candidatos[:TOPE_POR_REGLA]: enlace, accion = _enlace(...); avisos.append(Aviso(..., fecha=None, ...))`
  seguido de `+ _y_mas(len(...) - TOPE_POR_REGLA, ...)`. Además, `_foto` está duplicada (`:96-97` y
  `selectors/emergencia_tablero.py:387-388`), y todas las funciones aceptan el modo `foto=None`
  (`:103`, `:136`… y `emergencia_tablero.py:408`, `:514`, `:592`), que solo usan los tests.
- **Escenario:** una regla nueva copia 35 líneas para cambiar 4 (candidatos, título, texto, URL del resto). Un
  cambio en el contrato del aviso (por ejemplo, `fecha` real) se repite 7 veces.
- **Solución (preserva salida):** un helper `_acotados(candidatos, usuario, armar, *, resto)` donde `armar(x)`
  devuelve `(titulo, texto, origen, url, accion)` y `resto` es un `Resto(singular, plural, url, accion)`. Cada
  regla queda en «filtrar candidatos + lambda». `foto` pasa a ser obligatoria y los tests llaman a
  `foto_del_tablero` explícitamente. Así se borran 11 ramas `None` y las dos `_foto`. Son unas 150 líneas menos.
- **Tests a agregar:** ninguno nuevo: los de `test_emergencia_tablero` comparan los textos de los avisos.
- **Verificación:** la suite de avisos en verde y la misma lista de avisos para los mismos datos.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md`: «Tres funciones con el mismo bucle y distinto
  texto piden un helper con una función de armado».

---

### E-LIM-44 · `selectors/kits.py` mezcla alcance de la guardia con lecturas de kits: autoriza dos veces y aloja `mis_dispositivos`
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** fusión de E-LIM-44 · **Ola:** 7 · **Esfuerzo:** S
- **ID de la pasada 1:** E3-LIM-14 + E4-LIM-09
- **Ubicación:** `programas/selectors/kits.py:270-271` (`entregas_pendientes_de` vuelve a correr
  `puede_operar_dispositivo`, que `RecepcionKitsMixin` ya resolvió en `views/emergencia_kits.py:539-545`).
  `:295-341` (`mis_dispositivos`: «dónde es de la guardia», con `CAP_ADMITIR` y `CAP_RECIBIR_KIT`, que no es
  una lectura de kits). La tabla de presupuestos del docstring (`:16-24`) nombra `detalle_de_entrega`, que no
  existe, y da 2 consultas para `mis_dispositivos` cuando su docstring (`:305`) dice 4.
- **Escenario:** cada carga de «Kits del dispositivo» paga la consulta de alcance dos veces. Quien busca «los
  dispositivos de la guardia» no lo encuentra en `selectors/dispositivos*` y lo reescribe. La tabla de
  presupuestos engaña al que la usa para revisar un PR.
- **Solución:** `entregas_pendientes_de(dispositivo)` sin el `usuario`: el alcance queda a cargo del llamador,
  como ya documenta `entregas_de` (`:280-285`). La API que lo usa pasa por `entregas_al_alcance`.
  `mis_dispositivos` se mueve a `selectors/emergencia_guardia.py` (o al módulo de alcance de Dispositivos).
  Hay que corregir la tabla del docstring.
- **Lo que NO hay que hacer:** quitar el chequeo sin confirmar que todos los llamadores (`grep entregas_pendientes_de`)
  ya filtran por alcance. Si la API lo llama con un dispositivo sin filtrar, el chequeo se queda.
- **Tests a agregar:** `programas/tests/test_emergencia_kits.py::PendientesTest.test_presupuesto_vista` (una consulta menos).
- **Verificación:** presupuesto de la vista de pendientes baja en 1.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md`: «La autorización se resuelve una vez, en la
  frontera (vista o API); un selector no la repite salvo que lo llame una frontera que no la hizo».

#### Aporte del segundo revisor (E4-LIM-09: «Mis dispositivos» se compone en la vista: merge de dos selectores con defaults a mano)
_Pasada 1: severidad BAJA · estado CONFIRMADO (lectura) · esfuerzo S._

- **Ubicación:** `programas/api/views_emergencia_kits.py:67-73`; `programas/selectors/kits.py:295`;
  `programas/selectors/emergencia_alojar.py:145`.
- **Escenario:** la vista filtra `donde_admite`, llama a `resumen_de_llegadas` y completa
  `{"plazas_libres": 0, "derivaciones_pendientes": 0}` por fila. La regla «0 donde solo recibe kits» (que el
  serializer documenta como contrato, `serializers_emergencia.py:249-254`) vive en la vista.
- **Solución:** `selectors.kits.mis_dispositivos_con_llegadas(usuario)` (o un parámetro en `mis_dispositivos`) que
  devuelva las filas completas; la vista queda en una línea. Mismas consultas.
- **Tests a agregar:** `programas/tests/test_kits.py::MisDispositivosTest.test_solo_kits_tiene_llegadas_en_cero`.
- **Verificación:** la vista no hace `.update` sobre filas.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` · «Un `for fila in
  filas: fila.update(...)` en una vista es composición de lectura: va al selector.»

---

### E-LIM-45 · `acotar_relevado_en` reimplementa el recorte de reloj de `campo.acotar_capturado_en` y corre dentro de `validate_relevado_en`
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 7 · **Esfuerzo:** S
- **ID de la pasada 1:** E4-LIM-11
- **Ubicación:** `programas/services/emergencia_campo.py:24-50`; `programas/services/campo.py:102-115`;
  `programas/api/serializers_emergencia.py:168-172`.
- **Escenario:** las dos funciones hacen `ahora = ahora or now(); if valor > ahora + ADELANTO_TOLERADO: return ahora`.
  La de Emergencia agrega un tope de 24 h que rechaza. Además, una regla de negocio que **muta** el dato (recorta a
  `ahora`) corre en `validate_*` del serializer, y el serializer depende de la clave interna del error
  (`error.message_dict["relevado_en"]`). `services/emergencia_campo.py` es un módulo de una sola función que solo
  llama el serializer; `crear_caso` no sabe que su `relevado_en` ya viene recortado.
- **Solución:** expresar `acotar_relevado_en` sobre `acotar_capturado_en` (`valor, _ = acotar_capturado_en(...)` después
  del chequeo de 24 h) y llamarla desde `crear_caso` cuando `origen == TERRITORIO` (o desde la vista pasando el valor),
  dejando al serializer solo el parseo ISO. El 400 sale igual por `ValidationError({"relevado_en": ...})` vía
  `_ejecutar`/`handle_exception`. Si se prefiere no tocar `crear_caso`, al menos reusar `acotar_capturado_en`.
- **Lo que NO hay que hacer:** sumar la observación K2 de Becas (`observacion_reloj_adelantado`): Emergencia no la tiene
  y sería un cambio de comportamiento.
- **Tests a agregar:** los de `programas/tests/test_emergencia_campo.py` (tolerancia, 1 día, >1 día) tienen que pasar sin
  cambios.
- **Verificación:** `ADELANTO_TOLERADO` comparado en un solo lugar.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` · «`validate_<campo>`
  solo traduce forma; una regla que cambia el valor o depende de `now()` va al servicio que crea el objeto.»

---

### E-LIM-46 · La clase base del Formulario 1 conoce a su subclase (`pop("relevado_en", None)` + `relevado_en = None`)
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 7 · **Esfuerzo:** S
- **ID de la pasada 1:** E4-LIM-12
- **Ubicación:** `programas/api/serializers_emergencia.py:174-185` (comentario en `:178`), `:736-744`.
- **Escenario:** `CasoEmergenciaEnvioSerializer.datos_formulario1` tiene un `pop` especial «el de la puerta no tiene
  `relevado_en`», y `IngresoDirectoEnvioSerializer` borra el campo heredado con `relevado_en = None`. La herencia está
  al revés: la base es M1 y la de la puerta le resta.
- **Solución:** `_Formulario1EnvioSerializer` (todo menos `relevado_en`, con `datos_formulario1` sin casos especiales);
  `CasoEmergenciaEnvioSerializer(_Formulario1EnvioSerializer)` suma `relevado_en` + `validate_relevado_en` y saca la clave
  en su `datos_formulario1`; `IngresoDirectoEnvioSerializer(_Formulario1EnvioSerializer)` solo pisa `direccion`. Los
  nombres de componente OpenAPI se mantienen.
- **Tests a agregar:** ninguno; el contrato de los tres extremos que crean casos tiene que quedar igual
  (`manage.py spectacular --fail-on-warn` sin diff del esquema).
- **Verificación:** no queda `relevado_en = None` ni `pop("relevado_en", None)`.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` · «Una subclase que
  anula un campo con `= None`, o una base con una rama para su hija, pide extraer la base común.»

---

### E-LIM-47 · Cuatro clases de permiso casi idénticas y el código `SIN_MODULO` redeclarado por superficie
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 7 · **Esfuerzo:** S
- **ID de la pasada 1:** E4-LIM-16
- **Ubicación:** `programas/api/views_emergencia.py:89`, `:124-168`; `programas/api/views_inspecciones.py:57`;
  `programas/api/views.py:162` (literal `"SIN_MODULO"`).
- **Escenario:** las cuatro clases son `message = {detail, code: SIN_MODULO}` + `return predicado(request.user)`; solo
  `EmergenciaRelevarPermission` chequea `user.is_authenticated` (las otras confían en el orden de `permission_classes`),
  una asimetría que nadie decidió. `CODIGO_SIN_MODULO` vive en dos módulos y como literal en un tercero, y es contrato
  con la app.
- **Solución:** `def _permiso_de_modulo(predicado, mensaje) -> type[BasePermission]` (o una base con `predicado` como
  atributo) que siempre exige autenticado; `CODIGO_SIN_MODULO` en `programas/api/respuestas.py` (E-LIM-13). Los cuerpos
  del 403 no cambian.
- **Verificación:** `grep -rn '"SIN_MODULO"' programas/api` = 1.
- **Regla para no repetirlo:** **skill** · rúbrica `codigo-limpio.md` · «Los `code` del contrato de la app viven en un solo módulo.»

---

### E-LIM-48 · `selectors/emergencia_mesa.py` es un *presenter* que la guardia usa como bolsa de utilidades
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** thermos E1 · **Ola:** 8 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E1-LIM-11
- **Ubicación:** `programas/selectors/emergencia_mesa.py:1-14` (el docstring dice «es de las dos pantallas del backoffice»). `programas/selectors/emergencia_llegadas.py:18` importa `ROTULO_DE_NECESIDAD`, `_personas`, `franjas_del_grupo` y `nombre_de`. `filas_de_integrantes` (`:425`) recibe la tabla de estados por parámetro para servir a la guardia (M2-3).
- **Escenario:** el módulo que se presenta como de E2 y E3 es dependencia de M2. Un cambio «solo de la bandeja» en `_personas` o `franjas_del_grupo` cambia la guardia, y el nombre no lo anticipa. Con 656 líneas, es el próximo candidato a cruzar las 1.000.
- **Causa raíz:** no hay un lugar para las piezas de armado compartidas entre la mesa y el dispositivo.
- **Solución:** con LIM-05 y LIM-06 aplicadas, los formateadores y rótulos salen de acá. Mover `franjas_del_grupo` y `filas_de_integrantes` a `programas/selectors/emergencia_rotulos.py` (o a `emergencia_grupo.py`) y dejar en `emergencia_mesa.py` solo E2 y E3. Reexportar por una release. El módulo baja a unas 500 líneas.
- **Tests a agregar:** ninguno nuevo. Los de `test_emergencia_mesa` y `test_emergencia_llegadas` cubren el contrato.
- **Verificación:** `emergencia_llegadas` no importa de `emergencia_mesa`.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md` · «Lo que comparten dos pantallas de Emergencia no vive en el módulo de una de ellas».

---

### E-LIM-49 · `forms_emergencia.py` mezcla la configuración E7 con los formularios de la mesa
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** thermos E1 · **Ola:** 8 · **Esfuerzo:** S
- **ID de la pasada 1:** E1-LIM-15
- **Ubicación:** `programas/forms_emergencia.py:46-229` (SLA, formset de kits y `_IdDeFila`) y `:232-631` (la mesa). En total, 631 líneas.
- **Escenario:** dos pantallas sin relación (E7 y E2/E3) comparten archivo, y el archivo se acerca a 700. Kits ya tiene su propia vista (`views/emergencia_kits.py`) y va a pedir más formularios.
- **Causa raíz:** el archivo se creó para E7 y la mesa se sumó abajo.
- **Solución:** mover las líneas 46-229 a `programas/forms_emergencia_config.py` y reexportarlas desde `forms_emergencia` por una release. `views/emergencia_config.py` importa del nuevo archivo.
- **Tests a agregar:** ninguno.
- **Verificación:** `manage.py check` y los tests de E7 en verde.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md` · «Un archivo de forms agrupa una pantalla o un flujo; uno de más de 600 líneas con dos pantallas se parte».

---

### E-LIM-50 · El selector del tablero arma tarjetas de pantalla (íconos, tonos, URLs) y lee dos veces las entregas en camino
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — (mismo patrón que E-LIM-08/05) · **Ola:** 8 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E3-LIM-12
- **Nota de consolidación (juez):** la segunda parte de esta ficha (`entregas_en_camino` lee todas las entregas para mostrar 20) pasa a E-PERF-06. Esta ficha conserva solo el armado de tarjetas de pantalla (íconos, tonos, `reverse`) dentro del selector.
- **Ubicación:** `programas/selectors/emergencia_tablero.py:408-502` (`resumen`: `icono`, `tono`, notas y
  pluralización con `_plural` `:399`), `:563-566` y `:674` (`reverse` en un selector). `:645-677`
  (`entregas_en_camino` trae **todas** las `EN_CAMINO` con `prefetch` de líneas para mostrar 20 y contar, y
  `_entregas()` `:340-357` ya las contó en la foto). `:659` reescribe el `Prefetch` de
  `selectors/kits.py:88-89` (`_lineas_ordenadas`).
- **Escenario:** con 200 entregas en camino, la vista carga 200 entregas y todas sus líneas para mostrar 20.
  El total sale de `len(entregas)`, que ya está en `foto.entregas_en_camino`. Un cambio de ícono o tono de una
  tarjeta obliga a tocar el selector y su presupuesto de consultas.
- **Solución:** `entregas_en_camino(ahora, tope)` hace `[:tope]` en el queryset (2 consultas, acotadas). La
  vista toma el total de `foto.entregas_en_camino`. El `Prefetch` usa `kits._lineas_ordenadas()` (público).
  `resumen` devuelve números y una vista o presenter (`views/emergencia_tablero.py`, o un
  `selectors/emergencia_tablero_pantalla.py` como `emergencia_llegadas`) arma las tarjetas. El selector baja
  de 677 a unas 520 líneas.
- **Tests a agregar:** `programas/tests/test_emergencia_tablero.py::EntregasEnCaminoTest.test_carga_solo_el_tope` (assertNumQueries + filas leídas).
- **Verificación:** presupuesto de la vista completa (16) sin cambios o menor.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md`: «`reverse()` o un nombre de ícono en `selectors/` es presentación fuera de lugar».

---

### E-LIM-51 · `views/emergencia_dispositivo.py` pasa las 700 líneas, y el «sin derivación» que el PM quiere poder sacar sigue adentro
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** — (complementa E-LIM-54) · **Ola:** 8 · **Esfuerzo:** S
- **ID de la pasada 1:** E3-LIM-13
- **Ubicación:** `programas/views/emergencia_dispositivo.py` (726 líneas). `:646-726` (`_Formulario1View`,
  `AvisarALaMesaView`, `IngresoDirectoView`). El comentario de `:647-648` dice que «se tiene que poder sacar sin
  tocar el resto», y el servicio ya está aparte (`services/emergencia_sin_derivacion.py`).
- **Escenario:** el archivo crece con cada paso del guion y quedan ~25 líneas para el umbral de 750 que pide
  partir. Sacar el ingreso directo (decisión 4 del PM) obliga hoy a editar el archivo central de la guardia.
- **Solución:** mover `:646-726` a `programas/views/emergencia_dispositivo_sin_derivacion.py` (espejo del
  servicio), importando `GuardiaView`. Si después de E-LIM-01/04/05 el archivo sigue arriba de 600 líneas,
  partir por paso: `..._llegadas.py` (paso 1) y `..._ingreso.py` (pasos 2 y 3). Las URLs no cambian.
- **Tests a agregar:** ninguno; los existentes cubren las rutas.
- **Verificación:** `wc -l programas/views/emergencia_dispositivo*.py`, todos por debajo de 600.
- **Regla para no repetirlo:** **control mecánico** · ratchet de tamaño (ya propuesto en E-LIM-54): falla si un
  `programas/views/*.py` nuevo o tocado pasa de 700 líneas sin `# TAMAÑO-OK: <motivo>`.

---

### E-LIM-52 · `selectors/emergencia_llegadas.py` está vivo pero es presentación del backoffice alojada en `selectors/`
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** el formateo `_dia_hora` es instancia de E-LIM-25 (no se repite) · **Ola:** 8 · **Esfuerzo:** M
- **ID de la pasada 1:** E4-LIM-13
- **Ubicación:** `programas/selectors/emergencia_llegadas.py:1-186`; único consumidor `programas/views/emergencia_dispositivo.py:57`.
- **Escenario:** el módulo arma textos («Familia Pérez», «Vence 12/03 14:20»), tonos de badge, contexto del stepper
  (`pasos`) y URLs (`url_de`) para templates: según `CLAUDE.md` («selectors/ consultas de lectura»), eso no es un
  selector. Importa un privado de otro módulo (`_personas` de `emergencia_mesa`, `:18`), y `filas_de_integrantes`
  (`:117-120`) es un envoltorio de una línea sobre `emergencia_mesa.filas_de_integrantes`. No es código muerto: la API
  no lo usa, pero la pantalla E6 sí, en 8 funciones.
- **Causa raíz:** el repo no tiene una capa nombrada para «armado de pantalla» y la mesa (`emergencia_mesa`) sentó el
  precedente de ponerla en `selectors/`.
- **Solución:** mover el módulo a `programas/presentacion/emergencia_llegadas.py` (o `views/_pantalla_emergencia.py`)
  sin cambiar funciones; `_personas` pasa a público en su dueño; `filas_de_integrantes` se reemplaza por la llamada
  directa con `estados=ESTADOS_DE_INTEGRANTE` en la vista. Hacerlo junto con `emergencia_mesa` para no dejar dos
  convenciones. Sin cambio visual.
- **Lo que NO hay que hacer:** borrarlo por «no lo usa la API»: rompe E6.
- **Verificación:** `grep -rn "selectors import emergencia_llegadas" programas` vacío; tests de E6 y snapshots en verde.
- **Regla para no repetirlo:** **CLAUDE.md** no (no aplica a toda sesión) → **skill** · rúbrica `codigo-limpio.md`,
  tabla de capas: agregar fila «armado de pantalla (textos, tonos, URLs, stepper) → `programas/presentacion/`, nunca
  `selectors/`».

---

### E-LIM-53 · `serializers_emergencia.py` (755 líneas) junta tres superficies que las vistas ya separaron
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 8 · **Esfuerzo:** S
- **ID de la pasada 1:** E4-LIM-14
- **Ubicación:** `programas/api/serializers_emergencia.py:1-755` (M1 `:72-228`, M3 `:231-375`, M2 `:378-755`).
- **Escenario:** pasa de 700 líneas y crece con cada PR de la app; las vistas están partidas por superficie
  (`views_emergencia`, `_kits`, `_llegadas`, `_sin_derivacion`) y los serializers no, así que sacar M2-6 (decisión 4 del
  PM: «se tiene que poder sacar sin tocar el resto», `views_emergencia_sin_derivacion.py:3-6`) exige editar este archivo
  (`IngresoDirectoEnvioSerializer`, `IngresoDirectoSerializer`, `AvisoALaMesaSerializer`, `:736-755`).
- **Solución:** paquete `programas/api/serializers_emergencia/` con `__init__.py` que reexporta todo (los imports
  actuales siguen andando), y módulos `base.py` (helpers `_texto/_cantidad/_aviso`, M1, perfil), `kits.py`,
  `llegadas.py`, `sin_derivacion.py`. Sin cambio de nombres ni de componentes OpenAPI.
- **Verificación:** `manage.py spectacular --fail-on-warn` sin diff; ningún módulo > 300 líneas.
- **Regla para no repetirlo:** **control mecánico** · test ratchet de tamaño: `programas/api/*.py` > 700 líneas falla
  salvo lista congelada (hoy `views.py`, 923). Mensaje: «Partí por superficie antes de seguir sumando.»

---

### E-FE-02 · Los filtros de la bandeja se renderizan a mano mientras `FiltrosBandejaForm` declara las mismas opciones
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** thermos E1 · **Ola:** 9 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E1-FE-02
- **Ubicación:** `programas/templates/programas/emergencia/casos/list.html:22-45` (cinco `<select>` con bucles de `<option>` y `selected` a mano). `programas/views/emergencia.py:119-128` pasa `estados`, `prioridades`, `semaforos` y `operadores` por separado. `programas/forms_emergencia.py:601-610` vuelve a declarar esas opciones en `FiltrosBandejaForm`, que la vista valida pero no renderiza.
- **Escenario:** hay tres fuentes por filtro (las opciones del form, la tupla de la vista y el bucle del template). Un filtro nuevo o una opción nueva hay que agregarlos en las tres. Si el template ofrece algo que el form no acepta, el filtro se ignora sin aviso («un valor que no es de la lista se ignora»).
- **Causa raíz:** `dynamic_list_filters.js` pide un `<form>` sin clase y controles con `aria-label`, y se resolvió escribiendo el HTML en vez de configurar los widgets.
- **Solución:** declarar en `FiltrosBandejaForm` los widgets con `attrs={"class": "nodo-field max-w-xs", "aria-label": …}` y las opciones vacías («Todos», «Todas», «Cualquiera») como primera choice. Cargar las opciones dinámicas (localidades, operadores, «Míos») en `__init__`. El template renderiza `{{ form.estado }}` y los demás. El HTML resultante tiene que ser idéntico: mismos `name`, clases, `aria-label` y orden de opciones. La vista deja de pasar las tuplas.
- **Lo que NO hay que hacer:** usar `components/_field.html` acá. Agrega label y wrapper, y cambia lo visual.
- **Tests a agregar:** `programas/tests/test_emergencia_mesa.py::BandejaFiltrosTests.test_html_de_filtros_sin_cambios` (`assertInHTML` de cada `<select>`).
- **Verificación:** ese test, y el presupuesto de consultas de E2 igual (operadores y localidades, una consulta cada uno, como hoy).
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-frontend.md` · «Si existe un Form para los parámetros de una pantalla, sus controles se renderizan desde el Form; no se reescriben `<option>` en el template».

---

### E-FE-03 · «Llegaron N sobre M declaradas» se arma dos veces en la ficha, con dos fuentes
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** thermos E1 · **Ola:** 9 · **Esfuerzo:** S
- **ID de la pasada 1:** E1-FE-03
- **Ubicación:** `programas/selectors/emergencia_mesa.py:187-194` (aviso de cabecera, con `grupo.total_declarado` y `grupo.suma_de_cantidades()`) y `programas/templates/programas/emergencia/casos/detail.html:163` (texto escrito en el template, con `integrantes.total` y `integrantes.declaradas`, que vienen de `selectors/emergencia_alojar.py:349-350`).
- **Escenario:** hoy los números coinciden (las dos fuentes terminan en `GrupoFamiliar`). Pero el texto está en Python y en el template a la vez: un cambio de redacción en uno deja la ficha diciendo lo mismo de dos formas.
- **Causa raíz:** el *presenter* arma el aviso y la sección de integrantes, y el template volvió a redactar la frase.
- **Solución:** el *presenter* agrega `integrantes["crecio_texto"]` con la frase actual del template, armada en Python, y el template imprime `{{ integrantes.crecio_texto }}`. El aviso de cabecera queda como está. El HTML no cambia y ninguno de los dos mensajes se borra (eso cambiaría lo visual).
- **Tests a agregar:** `programas/tests/test_emergencia_mesa.py::FichaTests.test_llegaron_mas_texto_unico`.
- **Verificación:** `assertContains` de E3 con un grupo crecido, sin diferencias.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-frontend.md` · «En pantallas con *presenter* en Python, el template no redacta frases con datos; las imprime».

---

### E-FE-04 · Los modales «Marcar en camino» y «Cancelar entrega» están escritos dos veces (listado y detalle) y dependen de parciales con nombre de Becas
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** misma familia que E-FE-01 (otro módulo) · **Ola:** 9 · **Esfuerzo:** S
- **ID de la pasada 1:** E3-FE-01
- **Ubicación:** `programas/templates/programas/emergencia/kits/list.html:98-137` y
  `programas/templates/programas/emergencia/kits/detail.html:172-208`: mismo esqueleto, mismo texto de alerta,
  mismos botones. Cambian el título (`· número`), la `action` y el oculto `volver`. Los dos incluyen
  `programas/becas/_modal_header.html`, `_modal_footer.html` y `custom/js/becas-modal.js` (`list.html:141`,
  `detail.html:212`).
- **Escenario:** el texto de advertencia de «Cancelar» («Una entrega cancelada no se reabre…») está en dos
  archivos. Si se corrige en uno, el listado y el detalle dicen cosas distintas sobre la misma acción.
- **Solución (sin cambio visual):** `kits/_modal_en_camino.html` y `kits/_modal_cancelar.html`, con
  `entrega`, `form`, `action`, `titulo` y `volver` (opcional) como parámetros. Listado y detalle los incluyen.
  El nombre `becas/` de los parciales y del JS de modal compartido se resuelve en E-FE-01 (mover a
  `components/`). Acá solo se cita.
- **Tests a agregar:** los snapshots o tests de render de kits que existan. `scripts/compile_templates.py --bloques` en 0.
- **Verificación:** `grep -c "Una entrega cancelada no se reabre" programas/templates -r` = 1.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-frontend.md`: «Un modal que aparece en más de
  una pantalla del mismo módulo va en un parcial `_modal_<accion>.html` del módulo desde el primer uso».

---

### E-ERR-17 · Un ingreso en curso que nadie cierra retiene las camas de la familia sin plazo
**Severidad:** INFO · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** nuevo · **Ola:** 3 · **Esfuerzo:** M
- **ID de la pasada 1:** E2-ERR-06
- **Ubicación:** `programas/services/reservas_derivacion.py:177-188` (reservas con `hasta=None`); `programas/services/emergencia.py:641-688` (`vencer_derivacion` solo vence `PENDIENTE`); `docs/internal/emergencia-manual.md:203` («Una `ACEPTADA` no vence»).
- **Escenario:** la guardia acepta (reserva 7 camas) y la familia nunca llega; nadie toca «Cancelar ingreso». Las 7 reservas quedan `VIGENTE` sin vencimiento y el caso en `INGRESO_EN_CURSO`: las camas no se ofrecen a otra derivación ni al ingreso directo. La mesa no puede cancelar una derivación aceptada (`cancelar_derivacion` exige `PENDIENTE`); solo se ve por la alerta genérica de SLA del tramo. El docstring de `liberar_reservas_de_derivacion` menciona «el vencimiento de la derivación» como llamador, pero ese camino no existe.
- **Causa raíz:** decisión registrada (la aceptada no vence) sin contrapartida para las reservas que cuelgan de ella.
- **Solución:** `DECISIÓN CLIENTE: mantener el comportamiento y corregir el docstring de liberar_reservas_de_derivacion (quitar «vencimiento»)`; si el PM quiere plazo, un vencimiento de ingreso en curso sin confirmadas que llame a `cancelar_ingreso` es otro requerimiento.
- **Tests a agregar:** — (documental).
- **Verificación:** lectura del docstring corregido.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/` · «Toda reserva sin `hasta` necesita un camino de liberación que no dependa de que alguien se acuerde; si es por decisión, que el docstring no prometa un vencimiento que no existe.»

---

### E-ERR-18 · `kits._entero` levanta `ValueError` con «+-1» o «--1» (latente)
**Severidad:** INFO · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** nuevo · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** E3-ERR-08
- **Ubicación:** `programas/services/kits.py:227-228`.
- **Escenario:** `"--1".strip().lstrip("+-")` es `"1"` → `isdecimal()` verdadero → `int("--1")` → `ValueError` sin atrapar → 500. Hoy no es alcanzable: la web (`IntegerField` de `ItemsEntregaForm`/`RecepcionKitForm`) y la API (`IntegerField` del serializer) entregan enteros. Lo sería para cualquier llamador nuevo que pase texto, que es lo que el docstring del helper promete aceptar.
- **Causa raíz:** el chequeo quita **todos** los signos y la conversión los recibe todos.
- **Solución:** `try: return int(valor.strip()) except ValueError: return None` dentro de la rama `str` (o `lstrip` de un solo signo: `re.fullmatch(r"[+-]?\d+", …)`). Mismo resultado para toda entrada válida.
- **Tests a agregar:** `programas/tests/test_emergencia_kits.py::EnteroTest.test_signos_repetidos_no_son_cantidad`.
- **Verificación:** `_entero("--1") is None`.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/correccion-seguridad.md` · «Un parser a mano de enteros se prueba con signos repetidos, espacios internos y dígitos Unicode; mejor `int()` dentro de `try`.»

---

### E-PERF-13 · Ninguna ruta de Emergencia está en los presupuestos ni en el banco MySQL
**Severidad:** INFO · **Estado:** CONFIRMADO (lectura) · **Eje:** PERF · **Origen:** nuevo · **Ola:** 2 · **Esfuerzo:** S-M
- **ID de la pasada 1:** E1-PERF-06
- **Ubicación:** `scripts/perf_budgets.json` y `scripts/perf_mysql/bench_mysql.py` (`_extra_targets`, `:29`):
  sin `emergencia`. Los conteos viven solo en `programas/tests/test_emergencia_mesa.py:1260-1302` (SQLite).
- **Escenario:** E-PERF-02 a -04 dependen del plan de MariaDB con volumen, que hoy nada mide; un cambio
  que agregue un JOIN o rompa el plan de la bandeja pasa el CI si no suma consultas.
- **Solución:** sembrar Emergencia en el banco («Siembra necesaria») y agregar a `bench_mysql.py`:
  `emergencia_bandeja`, `emergencia_bandeja_cerrados_p90` (`?solapa=cerrados&page=90`),
  `emergencia_bandeja_texto` (`?texto=gonz`), `emergencia_ficha` (caso `EN_GESTION` tomado por el actor,
  con panel de derivar y 200 dispositivos) y `emergencia_ficha_alojado` (100 trazas e integrantes); y las
  dos primeras a `perf_budgets.json` vía `perf_audit.py`.
- **Regla para no repetirlo:** **control mecánico** · `scripts/check_perf_budgets.py` · fallar si un
  `app_name` de URLs del backoffice (p. ej. `emergencia`) no tiene al menos su listado en `perf_budgets.json`.

---

### E-PERF-14 · La ficha trae la traza completa, sin tope
**Severidad:** INFO · **Estado:** CONFIRMADO (lectura) · **Eje:** PERF · **Origen:** nuevo · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** E1-PERF-05
- **Ubicación:** `programas/selectors/emergencia_mesa.py:413` (`_traza`) y `:401` (`_contactos`).
- **Escenario:** una familia alojada varias semanas acumula `FICHA_ACTUALIZADA` por cada edición de cada
  integrante, `INTEGRANTE_*`, `CONTACTO`…: 100–300 trazas en una sola consulta (sin N+1:
  `select_related("usuario")`), todas dibujadas en `_linea_tiempo.html`. Crece con la vida del caso, no con
  el volumen total; ms en la base, el costo real es el HTML.
- **Solución:** ninguna sin medición. Si la distribución real muestra colas largas, recortar es
  **DECISIÓN CLIENTE: mostrar las últimas 50 y un enlace a la traza completa**.
- **Verificación:** en testing (lectura): `SELECT caso_id, COUNT(*) c FROM programas_trazacaso GROUP BY caso_id ORDER BY c DESC LIMIT 10;`
- **Regla para no repetirlo:** **skill** · rúbrica de rendimiento · «Historial sin paginar: reportar la
  distribución por entidad antes de proponer un tope.»

---

### E-PERF-15 · La derivación aceptada nunca deja de ser ACEPTADA y las lecturas de la guardia arrastran todo el histórico del dispositivo
**Severidad:** INFO · **Estado:** CONFIRMADO (lectura) · **Eje:** PERF · **Origen:** nuevo · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** E2-PERF-04
- **Ubicación:** `programas/selectors/emergencia_alojar.py:450-463` (`llegadas_del_dispositivo`), `programas/services/emergencia_recepcion.py:147-161` (`buscar_por_dni`); índice en `programas/models/__init__.py:6055-6058` (`(dispositivo, estado)`); ningún cierre toca la derivación (`programas/services/emergencia_cierre.py:55-63`, `:152-167`, `:225-241`).
- **Escenario:** cada familia alojada deja su derivación `ACEPTADA` (con `clave_vigente`) para siempre. `llegadas_del_dispositivo` filtra `estado = ACEPTADA AND caso.estado = INGRESO_EN_CURSO`, y `buscar_por_dni` `estado IN (PENDIENTE, ACEPTADA)` con un `OR` entre responsable e integrantes y `DISTINCT`: el índice `(dispositivo, estado)` entrega todas las aceptadas históricas del dispositivo, y el filtro por el estado del caso (y, en la búsqueda, el `LEFT JOIN` a todos los integrantes) se resuelve fila por fila.
- **Con qué crece:** alojamientos históricos del dispositivo (por integrantes, en la búsqueda). Con el volumen supuesto, unos 50 por dispositivo de media y unos 1.000 en un centro grande tras varias emergencias: unas 4.000 filas unidas en `buscar_por_dni`, milisegundos. No hay riesgo de 500 a esa escala; queda como INFO con la medición que lo cerraría.
- **Solución (solo si la medición lo pide):** sin cambiar estados ni la regla de vigencia: en `buscar_por_dni`, partir el `OR` en dos consultas por índice (`caso__grupo__responsable=ciudadano` y `caso__grupo__integrantes__ciudadano=ciudadano`, cada una por su FK indexada) y unir los ids; en `llegadas_del_dispositivo`, que el plan arranque por `caso__estado__in=(DERIVADO, INGRESO_EN_CURSO)` con el índice `(estado, prioridad)` del caso. Que la derivación cambie de estado al cerrar el caso es `DECISIÓN CLIENTE: no tocarlo` (cambia el significado de `clave_vigente`) y no se propone.
- **Tests a agregar:** ninguno hasta medir.
- **Verificación:** sembrar 1 dispositivo con 1.000 casos `ALOJADO`/`CERRADO` (derivación `ACEPTADA`, 4 integrantes con ciudadano) y 3 en `INGRESO_EN_CURSO`; `EXPLAIN` del SQL de las dos consultas (`str(qs.query)`): mirar `rows` sobre `programas_derivacion` y `Using temporary`; rutas al banco: `GET reverse("emergencia_api:dispositivo-buscar", args=[disp.pk]) + "?dni=<responsable de un caso alojado>"` y la pantalla E6 de llegadas (`programas/views/emergencia_dispositivo.py:173`).
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas activas · «Un índice `(padre, estado)` sobre un estado que no se cierra nunca (`Derivacion.ACEPTADA`) no separa lo vivo de lo histórico: mirar si el filtro que recorta está en otra tabla.»

---

### E-DAT-01 · Las subconsultas «última traza» y «última rechazada» no tienen índice compuesto, y el `Exists` por `clave_vigente` no está medido
**Severidad:** INFO · **Estado:** PLAUSIBLE · **Eje:** DAT · **Origen:** fusión de E-DAT-01 · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** E1-DAT-01 + E3-PERF-06
- **Ubicación:** `programas/selectors/emergencia.py:384` (`TrazaCaso.filter(caso=OuterRef).order_by("-creado_en","-id")[:1]`),
  `:416-421` (`Derivacion` RECHAZADA por caso, ordenada por `respondida_en`, y el `Exists` por
  `clave_vigente`); `programas/models/__init__.py:6239-6244` (TrazaCaso sin `indexes`) y `:6055-6058`
  (Derivacion solo con `(dispositivo, estado)`); `programas/migrations/0119_emergencia_casos.py:816-822`.
- **Escenario:** por cada fila de la página (50) y en la ficha, la última traza sale del índice de la FK
  `caso_id` más un filesort de las trazas de ese caso (5 de media, 30–100 en familias alojadas semanas);
  igual la última rechazada, repetida en 3 subconsultas para 3 columnas. El cron de inactividad
  (`services/emergencia.py:709`, `creado_en__gte`) y el tablero E1 usan la misma forma. Crece con las
  trazas **por caso**, no con el total: no hay mecanismo de 500. El `Exists` por `clave_vigente` es la
  forma de la trampa 1 (columna casi toda NULL), pero el índice es **UNIQUE** y el optimizador lo trata
  como a lo sumo una fila por valor: no debería caer en scan; no está medido.
- **Causa raíz:** los índices se pensaron para los filtros de la bandeja (bien cubiertos), no para las
  subconsultas correlacionadas.
- **Solución:** solo si el EXPLAIN lo pide: `Index(fields=["caso", "creado_en", "id"])` en `TrazaCaso` e
  `Index(fields=["caso", "estado", "respondida_en"])` en `Derivacion` (expand, tablas chicas).
- **Verificación:** `EXPLAIN` de la consulta de página de E-PERF-04 con ≥ 50.000 trazas: las `DEPENDENT
  SUBQUERY` sobre `programas_trazacaso` sin `Using filesort`, y la de `programas_derivacion` por
  `clave_vigente` con `key=derivacion_clave_vigente_unica`, `rows=1`.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas
  activas · «`Subquery(… OuterRef … order_by(…)[:1])` en un listado: confirmar con EXPLAIN que el índice
  cubre el filtro **y** el orden de la subconsulta.»

#### Aporte del segundo revisor (E3-PERF-06: La «última traza» del caso se calcula con dos subconsultas iguales y un filesort por caso)
_Pasada 1: severidad INFO · estado PLAUSIBLE · esfuerzo S._

- **Ubicación:** `programas/selectors/emergencia.py:384` (`ultima_traza_del_caso`), usada dos veces en `programas/selectors/emergencia_tablero.py:220-221`; `TrazaCaso.Meta` sin `indexes` (`programas/models/__init__.py:6239-6244`).
- **Escenario:** por cada caso de la ventana (~1.200 en pico) el motor corre dos veces `SELECT … FROM trazacaso WHERE caso_id = ? ORDER BY creado_en DESC, id DESC LIMIT 1`, cada una con filesort de las trazas del caso (índice solo por `caso_id`). Crece con abiertos × trazas por caso.
- **Causa raíz:** sin índice `(caso, creado_en, id)` el `ORDER BY … LIMIT 1` no puede leer la última entrada del índice; y `accion` y `detalle` se piden por separado.
- **Solución (preserva lógica):** `AddIndex` en `TrazaCaso`: `Index(fields=["caso", "creado_en", "id"])` (expand-only; 50.000 filas, `ALTER` online). Opcional: anotar solo `ultima_traza_id` y leer `accion`/`detalle` con `TrazaCaso.objects.filter(pk__in=...)` (+1 consulta fija; hay que mover el presupuesto).
- **Tests a agregar:** ninguno de comportamiento.
- **Verificación / medición:** `EXPLAIN` de la consulta de la ventana con la siembra de E-PERF-03: las `DEPENDENT SUBQUERY` sobre `programas_trazacaso` pasan de `Using where; Using filesort` a usar el índice sin filesort. Sin esa medición queda INFO.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` §Índices · «Una "última fila por padre" (`filter(padre=OuterRef(...)).order_by("-fecha")[:1]`) necesita el índice `(padre, fecha, id)`; sin él es un filesort por fila del listado.»

---

### E-LIM-54 · Tamaño: `services/emergencia.py` pasa las 700 líneas y otros tres archivos se acercan
**Severidad:** INFO · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** thermos E1 · **Ola:** 8 · **Esfuerzo:** S
- **ID de la pasada 1:** E1-LIM-16
- **Ubicación:** `programas/services/emergencia.py` (769), `programas/selectors/emergencia.py` (668), `programas/selectors/emergencia_mesa.py` (656), `programas/forms_emergencia.py` (631).
- **Escenario:** ninguno cruza las 1.000. El servicio ya se partió una vez (`emergencia_alta`) por este motivo, y las etapas siguientes (kits, egreso) van a sumarle acciones.
- **Causa raíz:** el peso extra no es lógica de la mesa: son 72 líneas de docstring de módulo, unas 40 de reexports (LIM-02), unas 30 de tablas de presentación (LIM-05) y unas 55 de excepciones (LIM-01).
- **Solución:** no partir por partir. Aplicar LIM-01, LIM-02 y LIM-05 baja el servicio a unas 640 líneas, todas de reglas del caso. LIM-11 hace lo mismo con `emergencia_mesa` y LIM-15 con los forms. Si una acción nueva lo vuelve a llevar a más de 900, el corte natural es «vencimientos del sistema» (`:621-723`) a `emergencia_vencimientos.py`, junto a su único consumidor `vencimientos_emergencia.py`.
- **Tests a agregar:** —
- **Verificación:** `wc -l` después de las otras fichas.
- **Regla para no repetirlo:** **control mecánico** · `test_arquitectura.py` · un ratchet de líneas para `programas/services/emergencia*.py` y `programas/selectors/emergencia*.py` (falla por encima de 1.000).

---

---

## 10. Seguimiento de los PRs que resolvieron las dos ALTA

Lo que la revisión independiente dejó como MINOR en #1204 y #1205 y que va **en el próximo PR de Emergencia** (ninguno abre una fuga: son consistencia y texto). Es el único trabajo abierto de E-SEG-01 y E-ERR-01.

**De #1204 (E-SEG-01, Cambio 496)**

1. **Rama de carrera de `ingreso_directo` sin la guarda.** `programas/services/emergencia_sin_derivacion.py:132-133`: si `crear_caso` choca con el UNIQUE y devuelve el caso con `ya_existia`, no pasa por `_exigir_reenvio_de_este_ingreso`; dos POST simultáneos del mismo usuario con el mismo `uuid_cliente` a A y a B dan a B un 200 con el caso de A en vez de un 409. Sin fuga (mismo `relevado_por`, y la vista filtra `integrantes` con `ingreso_sin_candado`). Solución: que las dos ramas `ya_existia` pasen por un helper único que aplique la guarda y cuelgue las reservas.
2. **Usar el modelo.** `emergencia_sin_derivacion.py:85-87` y `:201-203` reescriben a mano reglas que viven en el modelo: usar `CasoEmergencia.es_ingreso_directo` y `caso.en_la_puerta`. Hoy un «Avisar a la mesa» que la mesa derivó a X, reenviado a `ingreso-directo` en X, pasa como reenvío de ingreso directo. Test: ese reenvío da 409.
3. **Texto del 409 `UUID_EN_USO`.** La descripción en OpenAPI (`programas/api/views_emergencia_sin_derivacion.py:52-54,116-118`) y en `docs/internal/contrato-app-emergencia.md:116,248,848-849` sigue diciendo solo «de otro usuario»: agregar «o de un envío a otro dispositivo, o de la otra acción de M2-6». Solo texto.

**De #1205 (E-ERR-01, Cambio 497)**

4. **«El legajo no se toca» es inexacto.** El docstring de `programas/services/emergencia_confirmacion.py:111` y la entrada del Cambio 497 lo afirman, pero en el camino de la excepción `_completar_legajo` completa sexo, nacimiento y teléfono **vacíos** del legajo del responsable, igual que antes. Corregir el texto; saltear `_completar_legajo` en ese camino es decisión de cliente.
5. **Fila `dni` del 400.** `docs/internal/contrato-app-emergencia.md:766` (`ConfirmarIntegranteView`) no lista el rechazo nuevo. Solo documentación.
6. **«O en otro integrante, se rechaza» no es exacto.** Otra fila con el DNI del responsable y el nombre declarado se acepta si la persona 1 todavía no se confirmó (después la frena `_ya_confirmada_en`). Ajustar el texto del Cambio 497.

**Regla propuesta por esas auditorías** (también en el README de la serie, «Reglas propuestas»): la idempotencia por `uuid_cliente` pasa la guarda de alcance en **todas** las ramas `ya_existia`, y toda resolución de persona por DNI que escribe compara nombre y apellido (`nombre_en_conflicto`).
