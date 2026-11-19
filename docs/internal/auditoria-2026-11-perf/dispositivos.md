# Auditoría de performance y optimización 2026-11 · Dispositivos · Informe final (capítulo 3)

> Informe consolidado de la pasada 1 (12 revisores, 4 tajadas) con el resultado de la PoC de la pasada 2 para las dos fichas que la tenían pedida (candados y roles propios). SHA auditado `4140bb8073e271cf6ebccb1f08533d44553baf5a`. Capítulo 3 de la serie (Becas → Emergencia → Dispositivos). Los IDs finales son `D-<EJE>-NN`; la tabla de equivalencia contra los IDs de tajada está al final de la sección 2. Resoluciones del juez del 19-nov-2026 aplicadas. **Mediciones del banco: hechas el 19-nov-2026** (sección 8.d); `MEDIDO` es el estado de una ficha PERF/DAT con número del banco.

## 1. Resumen

- **Alcance:** módulo Dispositivos de `programas/` (legajo y detalle del dispositivo; estadías, plazas, ingreso y reservas; bitácora, equipo, constructor de formularios y `/media/`; edificios, inspecciones y API de campo de relevamientos). Python, templates, JS y la API de la app de campo. Quedan fuera `seed_*`, `diagnosticar_*` y los comandos de un solo uso. Las superficies de Emergencia que consumen Dispositivos son del capítulo 2 y se cruzan por ID.
- **Fichas:** 111 en la pasada 1, **93 tras fusionar** (12 fusiones que absorben 17 fichas, más 1 ficha INFO «verificado sin acción» pasada a Descartados). 93 fichas ≈ **318 h** con S=2, S-M=4, M=8, L=20 (totales contados de las fichas). Las olas 0 a 10 suman 264 h; las olas 11 y 12 (limpieza opcional, 22 fichas) suman 54 h.
- **Pasada 2 (PoC del juez):** las dos fichas que la tenían pedida están **CONFIRMADAS con test** (sección 8.0): el deadlock 1213 de candados (MEDIA, primera ola de concurrencia) y el atajo que otorga roles a uno mismo (MEDIA, Ola 0).

| Severidad | Fichas |
|---|---|
| CRÍTICA | 0 |
| ALTA | 5 |
| MEDIA | 38 |
| BAJA | 43 |
| INFO | 7 |
| **Total** | **93** |

| Eje | Fichas |
|---|---|
| SEG · Seguridad y RBAC | 7 |
| ERR · Errores y corrección | 14 |
| PERF · Rendimiento | 10 |
| DAT · Datos y operación | 1 |
| LIM · Código limpio y arquitectura | 51 |
| FE · Front (sin estética) | 10 |
| **Total** | **93** |

| Severidad × eje | SEG | ERR | PERF | DAT | LIM | FE |
|---|---|---|---|---|---|---|
| CRÍTICA | 0 | 0 | 0 | 0 | 0 | 0 |
| ALTA | 0 | 0 | 1 | 1 | 3 | 0 |
| MEDIA | 2 | 4 | 2 | 0 | 26 | 4 |
| BAJA | 5 | 8 | 3 | 0 | 21 | 6 |
| INFO | 0 | 2 | 4 | 0 | 1 | 0 |

**Las que importan:**

1. **D-LIM-01** (ALTA, hallado por 2 revisores): la vista reescribe la regla «quién ve al agente asignado» (D-LIM-01 absorbe D4-SEG-01: detalle reservado hasta el arreglo). Ola 0.
2. **D-SEG-01** (MEDIA, **CONFIRMADO con PoC**, Ola 0): detalle técnico reservado hasta el arreglo.
3. **D-SEG-02** (MEDIA, hallado por 2 revisores, Ola 0): detalle técnico reservado hasta el arreglo.
4. **D-ERR-01** (MEDIA, **CONFIRMADO con PoC**, hallado por 3 revisores, Ola 1): no hay orden global de candados; el ERROR 1213 se reprodujo en los dos caminos y llega como 500. No es Ola 0: InnoDB elige la víctima y el rollback no deja datos inconsistentes.
5. **D-LIM-02 y D-LIM-03** (ALTA): la transacción de negocio del ingreso y la edición del legajo están en la vista. Con D4-LIM-04, D3-LIM-06 y D1-LIM-06 forman la **regla transversal «lógica de dominio en vistas»** (R-1), la misma de Becas ola 7 y de E-LIM-01.
6. **D-ERR-02** (MEDIA, hallado por 4 revisores): un dispositivo cerrado sigue admitiendo cambios de plaza y reservas, y cerrar no mira estadías ni reservas. Es DECISIÓN CLIENTE con default aplicable.
7. **Rendimiento (medido el 19-nov-2026, sección 8.d):** **D-PERF-01** (ALTA, corta en ECOM: el historial profundo tarda ≈ 64 s y la página 1, ≈ 6,2 s) y **D-DAT-01** (ALTA: el detalle del dispositivo tarda ≈ 6,1 s por una consulta de `Estadia` en `type=ALL` sobre ≈ 121.000 filas) son las dos que suben. D-PERF-02 y D-PERF-03 quedan en MEDIA; D-PERF-04 y D-PERF-08 en BAJA; D-LIM-08 baja a INFO. D-PERF-05, D-PERF-06 y D-PERF-07 no se midieron por ruta. **No hay ninguna CRÍTICA.**

### Fusiones

Pedidas por el juez (se conserva una ficha; las demás quedan en «Origen» y en «Aporte del segundo revisor»). Todas se citan con «hallado por 2+ revisores = sube de peso»:

| Ficha final | Absorbe | Motivo |
|---|---|---|
| D-ERR-01 ← D2-ERR-01 | D2-DAT-01 + D3-DAT-01 | candados: no hay orden global (ingreso contra capacidad; corregir novedad contra cargarla). 3 revisores. PoC: 1213 en los dos caminos |
| D-ERR-02 ← D1-ERR-01 | D2-ERR-03 + D2-ERR-04 + D2-LIM-05 | dispositivo cerrado: la guarda no está en los servicios. 4 revisores |
| D-PERF-01 ← D1-PERF-01 | D1-ERR-04 | historial paginado: lee cada fuente completa hasta la página pedida. 2 revisores |
| D-LIM-01 ← D4-LIM-05 | D4-SEG-01 | regla de visibilidad del agente asignado; misma solución. ALTA se conserva |
| D-ERR-07 ← D3-ERR-02 | D3-LIM-07 | toggle de tipo no idempotente y estado de dominio escrito en la vista |
| D-LIM-13 ← D3-LIM-02 | D4-LIM-08 + D1-LIM-07 | traductor de errores del servicio al JSON/HTTP escrito varias veces (3 revisores; D1-LIM-07 hallada al consolidar) |
| D-LIM-08 ← D3-LIM-04 | D3-PERF-02 | pares usuario×rol sumables: mismo selector, sin tope en el alta |
| D-FE-05 ← D3-FE-03 | D4-FE-01 | mapeos tono → badge/ícono en templates |

Halladas al consolidar (mismo archivo o mismo problema, otro revisor):

| Ficha final | Absorbe | Motivo |
|---|---|---|
| D-SEG-02 ← D1-SEG-01 | D3-SEG-01 | el mismo hallazgo en dos pantallas; toma MEDIA |
| D-LIM-36 ← D3-LIM-11 | D1-LIM-16 + D4-LIM-06 | formateadores duplicados (plural, nombre de usuario, fecha, extensiones) |
| D-LIM-37 ← D2-LIM-13 | D4-LIM-13 | envoltorios identidad y constantes de capacidad copiados; vista que importa el mixin de otra vista |
| D-LIM-38 ← D2-LIM-12 | D3-LIM-16 | formato del nombre de plaza (`plaza_con_sector` ignorado). D3-LIM-16 **no cabía** en la ficha de tonos pedida por el juez |
| (sin ficha propia, a Descartados) | D1-LIM-15 | INFO «verificado sin acción»: la guardia de Emergencia no reimplementa el detalle del dispositivo |

Relaciones que NO se fusionaron (misma familia, otro archivo, otra causa o distinta migración; van cruzadas en las fichas): D-DAT-01 (índice del historial) con D-PERF-01; D-SEG-03, D-SEG-04 y D-SEG-05 con D-SEG-02 (alcance de datos personales, regla R-4); D-PERF-06 y D-PERF-07 con D-ERR-01 (mismas filas, otra medición); D-FE-07 con D-FE-03 (arranque del formulario del tipo); D-LIM-32 con D-LIM-37 (la misma importación del mixin en `reportes.py`).

### Cruces con otros capítulos

Buscados con grep en `becas.md` y `emergencia.md` (pedido 2 del juez):

| Ficha | Resultado del cruce |
|---|---|
| D-LIM-26 | **Existe en Becas: B-LIM-38** (ex B5-LIM-07, «El pegamento HTTP del constructor está copiado entre Becas y Dispositivos», Ola 12 de Becas). Arreglo único; el esfuerzo se cuenta una vez (el juez decide en qué ola). |
| D-ERR-06 | **No está en Becas.** El mismo patrón vive en `programas/views/diseno.py:287` (Becas). B-ERR-29 es otro defecto (`services/diseno.py:283`). **Resolución del juez:** la ficha D-ERR-06 cubre también `views/diseno.py:287` de Becas; hay nota cruzada en [becas.md](becas.md) (Ola 6) y no se abre ficha aparte. |
| D-PERF-03 | **No está ni en Becas ni en Emergencia.** Ficha propia, marcada transversal: `core/views/media.py` sirve adjuntos de los tres módulos. |
| D-SEG-01 | Cruce con #1114. Regla R-2. |
| D-FE-05 | **Existe en Emergencia: E-LIM-29**: la tabla severidad → tono/ícono y el `Aviso` copiados entre Emergencia y Dispositivos. Una sola tabla. |
| D-LIM-37 | E-LIM-27 (capacidad `dispositivo.admitir` redeclarada en siete módulos). |
| D-LIM-16 | E-LIM-19 (contrato Dispositivos ↔ Emergencia con helpers privados). |
| D-LIM-15 y D-LIM-17 | E-LIM-37 (regla de «cama libre» y mapa por sector escritos dos veces). |
| D-LIM-36 | E-LIM-25 (formateadores de texto copiados en cinco o más módulos). |
| D-ERR-01 | E-LIM-15 (orquestación de candados del ingreso copiada tres veces), E-PERF-09 y E-PERF-10 (aceptaciones simultáneas y validación de camas bajo candado). |
| D-LIM-13 | E-LIM-12, E-LIM-13, E-LIM-14 (traductores de errores) y B-LIM-65 (`responder_form`). |
| D-LIM-32 y D-LIM-12 | E-LIM-03 (compuerta 403/404 hecha dos veces) y E-LIM-01 (vistas que reescriben reglas del servicio). |
| D-LIM-18 | E-ERR-01 (identidad al confirmar con el DNI de un legajo existente, CONFIRMADO con PoC): misma ruta de código. |
| D-LIM-02, D-LIM-03, D-LIM-09, D-LIM-01, D-LIM-31, D-ERR-07 | Regla transversal R-1 «lógica de dominio en vistas»: Becas ola 7 (B-LIM-01 a B-LIM-06) y E-LIM-01. |

### Contradicciones entre fichas y resoluciones del juez

Se citan con los IDs de tajada (la tabla de equivalencia está al final de la sección 2).

1. **Orden global de candados dicho de tres maneras.** D2-ERR-01: plazas (por pk) y después dispositivo. D2-DAT-01: plaza, dispositivo y recién después sector («igual que las estadías en bitácora»). D3-DAT-01: entrada raíz, estadías y dispositivo, «compatible con egreso o cambio de plaza (estadía → dispositivo)». La «regla para no repetirlo» de D2-ERR-01 agrega un cuarto orden (estadía → plaza → reserva → ciudadano → dispositivo). Las cuatro son compatibles con **entrada de bitácora → estadías (pk) → plazas (pk) → reservas → ciudadano → dispositivo → sector**, pero ningún revisor verificó que ingreso, egreso, cambio de plaza y reserva tomen las estadías antes que las plazas en ese orden. Propuesta: fijar ese orden, probarlo con la PoC de dos hilos ya escrita y, mientras tanto, la alternativa común: reintentar la transacción entera ante 1213 con tope. Cruce con Emergencia (E-LIM-15): el orden debe ser el mismo en los dos módulos.
2. **Guarda «cerrado» contra «no ACTIVO».** D1-ERR-01 y D2-ERR-04 (ficha D-ERR-02) rechazan por estado `CERRADO`; D2-ERR-03 pide «no ACTIVO» para reservar. Hay estados intermedios que el cierre de Dispositivos no resuelve en ninguna ficha. Propuesta: una sola `dispositivo_operable(d)` con `CERRADO` rechazado en todo mutador y «no ACTIVO» solo donde ya se exige (bitácora, reservas); queda DECISIÓN CLIENTE con default.
3. **Destino de los helpers de formato.** D1-LIM-16 propone `programas/services/formato.py`; D3-LIM-11, `core/texto.py` y `core/archivos.py`; D4-LIM-06, `core/usuarios.py::nombre_visible`; Emergencia (E-LIM-25) tiene su propia propuesta. Propuesta: `core/texto.py` (plural y formatos), `core/archivos.py` (extensiones) y `core/usuarios.py` (nombre visible), un solo PR con Emergencia ola 7; `programas/services/formato.py` no se crea.
4. **Nombre del helper de visibilidad del agente asignado.** D4-LIM-05 propone `ve_la_asignacion_en_lote` y `agentes_visibles_para`; D4-SEG-01: detalle reservado hasta el arreglo. Propuesta: `ve_la_asignacion_en_lote` (queda dicho en D-LIM-01).
5. **Severidad de D-SEG-02.** D1-SEG-01 la dio MEDIA y D3-SEG-01 BAJA para el mismo hallazgo en dos pantallas, contra el mismo invariante (Cambio 271). La ficha fusionada toma MEDIA (D-SEG-02); el juez puede bajarla.
6. **D3-FE-01 propone `_ajax_js`; octubre descartó promoverlo.** El paso 2 usa un include que quizá solo exista en `programas/becas/` (descartado §8.1: no promover `_ajax_js`/`_modal_*` a `components/`). Resuelto: ver resolución 6 (data-ajax canónico, sin DECISIÓN CLIENTE).
7. **Numeración de olas de los revisores.** Los revisores de tajada usaron «Ola» con significados distintos (D1: 1/2/3; D2 y D3: 2/3/4 o «limpieza»; D3 corrección: «RBAC», «config», «constructor»; D4: 2/3). Aquí se reasignaron todas; el campo «Ola» de cada ficha es el de este informe.
8. **Volúmenes del banco.** D1 pide un dispositivo grande de 500 plazas con el 15 % de las estadías; D2, uno de 300 plazas con 20.000 egresadas y 300 activas; D4, 5.000 edificios y 50.000 inspecciones. No se contradicen si se siembran los tres a la vez (sección 8.c), pero hay que elegir el grande: 500 plazas, 10 sectores, 3 turnos y 20.000 estadías.

## 2. Índice

| ID | Título | Sev. | Estado | Esf. | Ola | Archivo |
|---|---|---|---|---|---|---|
| D-LIM-01 | La vista reescribe la regla de privacidad «quién ve al agente asignado» en lugar de usar el he… | ALTA | CONFIRMADO | S | 0 | `programas/views/dispositivos_relevamientos.py` |
| D-LIM-02 | Lógica de dominio y transacción de negocio en la vista del asistente de ingreso | ALTA | CONFIRMADO | S-M | 5 | `programas/views/dispositivos_ingreso.py` |
| D-LIM-03 | La edición del legajo (diff, contacto, traza y envío) se escribe en la vista | ALTA | CONFIRMADO | S-M | 5 | `programas/views/dispositivos_legajo.py` |
| D-SEG-01 | Un atajo permite otorgarse un rol propio | MEDIA | CONFIRMADO con test | S | 0 | Dispositivos · usuarios y agentes |
| D-SEG-02 | El historial muestra texto libre a quien no puede ver a la persona | MEDIA | CONFIRMADO | S | 0 | Dispositivos · historial |
| D-ERR-01 | Configurar capacidad toma dispositivo→plaza y el ingreso toma plaza→dispositivo: deadlock 1213 | MEDIA | CONFIRMADO con test | S-M | 1 | `programas/services/plazas.py` |
| D-ERR-02 | Cerrar un dispositivo no mira si tiene personas alojadas o reservas, y después del cierre se p… | MEDIA | CONFIRMADO | M | 3 | `programas/services/dispositivos.py` |
| D-ERR-03 | El ingreso retroactivo no tiene cota inferior: reescribe censo, historial y turnos viejos | MEDIA | CONFIRMADO | S | 3 | `programas/services/estadias.py` |
| D-ERR-04 | Una foto o un adjunto que llega después de «Revisado» se rechaza para siempre y la evidencia s… | MEDIA | PLAUSIBLE | S-M | 3 | `programas/services/inspecciones.py` |
| D-PERF-01 | El historial del detalle lee y arma en Python toda la auditoría anterior a la página pedida | ALTA | MEDIDO | M | 4 | `programas/selectors/auditoria_dispositivo.py` |
| D-PERF-02 | El censo del día lee el histórico entero de estadías del dispositivo | MEDIA | MEDIDO | S | 4 | `programas/services/ocupacion.py` |
| D-LIM-04 | El selector de auditoría decide la regla de privacidad del relevamiento y arma la presentación | MEDIA | CONFIRMADO | S-M | 2 | `programas/selectors/auditoria_dispositivo.py` |
| D-LIM-05 | El historial borra el id del ciudadano con una regex sobre un texto que escribe otro servicio | MEDIA | CONFIRMADO | S | 2 | `programas/selectors/auditoria_dispositivo.py` |
| D-LIM-06 | El enmascarado de la persona («Persona alojada») se resuelve en cinco lugares con dos redaccio… | MEDIA | CONFIRMADO | S | 2 | `programas/views/dispositivos_legajo.py` |
| D-LIM-07 | `puede_administrar_usuarios_dispositivos` es una regla paralela a `programas_administrables_us… | MEDIA | PLAUSIBLE | S | 2 | `services/equipo_dispositivo.py` |
| D-LIM-08 | La consulta «pares usuario×rol sumables» está escrita tres veces y el contrato `"u:r"` vive en… | INFO | MEDIDO | S-M | 4 | `services/equipo_dispositivo.py` |
| D-LIM-09 | La vista de P21 arma ~330 líneas de view-model y muta instancias del modelo con 18 atributos s… | MEDIA | CONFIRMADO | M | 5 | `programas/views/dispositivos_relevamientos.py` |
| D-LIM-10 | La vista del detalle arma a mano cada fila de estadías, y la regla «se puede mover» está tripl… | MEDIA | CONFIRMADO | S-M | 5 | `programas/views/dispositivos_legajo.py` |
| D-LIM-11 | La regla «puede dar de alta = `dispositivo.crear` + alcance de admin» está escrita en cuatro l… | MEDIA | CONFIRMADO | S | 5 | `programas/mixins_dispositivos.py` |
| D-LIM-12 | El gate del asistente reimplementa `puede_ingresar_persona`, que se declara «única fuente de l… | MEDIA | CONFIRMADO | S | 5 | `programas/views/dispositivos_ingreso.py` |
| D-LIM-13 | Tres vistas de Dispositivos reescriben `ajax_utils.errores_del_servicio`/`rechazar` | MEDIA | CONFIRMADO | S-M | 6 | `views/dispositivos_bitacora.py` |
| D-LIM-14 | El ciclo de vida de la estadía repite a mano su máquina de estados en cuatro servicios | MEDIA | CONFIRMADO | M | 7 | `programas/services/estadias.py` |
| D-LIM-15 | Tres definiciones de «plaza tomada» repartidas en cinco lugares | MEDIA | CONFIRMADO | S-M | 7 | `programas/services/estadias.py` |
| D-LIM-16 | La API que consumen Emergencia y `plazas.py` sigue siendo privada (inventario completo más all… | MEDIA | CONFIRMADO | S-M | 7 | `programas/services/reservas_derivacion.py` |
| D-LIM-17 | Dos constructores del mapa de plazas en paralelo (ingreso y «Sectores y plazas») | MEDIA | CONFIRMADO | M | 7 | `programas/services/ingreso.py` |
| D-LIM-18 | `ingreso.py` aloja la identidad de la persona (DNI, RENAPER, alta de legajo) que usa medio sis… | MEDIA | CONFIRMADO | S-M | 7 | `programas/services/ingreso.py` |
| D-LIM-19 | `sectores_plazas.py` es un presentador en `services/`: arma URLs, payload del modal y nombres… | MEDIA | CONFIRMADO | S-M | 7 | `programas/services/sectores_plazas.py` |
| D-LIM-20 | `estadias.py` supera las 1000 líneas mezclando cinco responsabilidades | MEDIA | CONFIRMADO | M | 7 | `programas/services/estadias.py` |
| D-LIM-21 | La máquina de estados del legajo está repartida en 7 servicios, 7 vistas y el template, que re… | MEDIA | CONFIRMADO | M | 8 | `programas/services/dispositivos.py` |
| D-LIM-22 | `infraestructura_del_dispositivo`: 240 líneas, tres modos y un dict de 16 claves implícitas | MEDIA | CONFIRMADO | S-M | 8 | `programas/services/detalle_dispositivo.py` |
| D-LIM-23 | Los códigos de acción de `TrazaDispositivo` son strings sueltos en seis módulos, sin `choices` | MEDIA | CONFIRMADO | S-M | 8 | `programas/models/__init__.py` |
| D-LIM-24 | `detalle_dispositivo.py` (893) junta dos dominios, y el de Infraestructura lo importa un selec… | MEDIA | CONFIRMADO | M | 8 | `programas/services/detalle_dispositivo.py` |
| D-LIM-25 | `views/dispositivos_legajo.py` tiene 1659 líneas y mezcla cuatro pantallas | MEDIA | CONFIRMADO | M | 8 | `programas/views/dispositivos_legajo.py` |
| D-LIM-26 | El constructor de formularios de Dispositivos es una copia de views/diseno.py (Becas) | MEDIA | CONFIRMADO | M | 8 | `views/dispositivos_formularios.py` |
| D-LIM-27 | `pantalla_bitacora` es una función de 318 líneas que mezcla todo | MEDIA | CONFIRMADO | M | 8 | `services/bitacora_pantalla.py` |
| D-LIM-28 | La regla de «vencido / por vencer» está escrita cinco veces, en Python y en SQL por separado | MEDIA | CONFIRMADO | S-M | 9 | `programas/models/__init__.py` |
| D-LIM-29 | Capas invertidas: los selectores importan de los servicios y un módulo existe solo para cortar… | MEDIA | CONFIRMADO | S-M | 9 | `programas/selectors/inspecciones.py` |
| D-LIM-30 | `services/inspecciones.py` pasa las 1.000 líneas y mezcla cinco responsabilidades | MEDIA | CONFIRMADO | M | 9 | `programas/services/inspecciones.py` |
| D-FE-01 | El cuerpo del modal de egreso está copiado entre el detalle (P4) y la estadía (P7) | MEDIA | CONFIRMADO | S | 10 | `programas/templates/programas/dispositivos/legajo/detail.html` |
| D-FE-02 | `tipo_detail.html` lleva 175 líneas de JS inline que reimplementan, y contradicen, el handler… | MEDIA | CONFIRMADO | S-M | 10 | `templates/programas/dispositivos/config/tipo_detail.html` |
| D-FE-03 | `nodo-formulario-tipo.js` duplica `nodo-formulario.js` (link público de Becas) con divergencias | MEDIA | CONFIRMADO | S-M | 10 | `static/custom/js/nodo-formulario-tipo.js` |
| D-FE-04 | Componente Alpine de ~55 líneas embebido en un atributo `x-data`, con nombres de acción duplic… | MEDIA | CONFIRMADO | S-M | 10 | `programas/templates/programas/dispositivos/sectores/sectores.html` |
| D-SEG-03 | El historial expone un dato personal del responsable | BAJA | CONFIRMADO | S | 2 | Dispositivos · historial |
| D-SEG-04 | El historial muestra datos de relevamientos fuera de alcance | BAJA | CONFIRMADO | S-M | 2 | Dispositivos · historial |
| D-SEG-05 | Una redacción por alcance se anula por otros caminos de lectura | BAJA | CONFIRMADO | S-M | 2 | Dispositivos · trayectoria |
| D-SEG-06 | La API de campo no limita las cargas de archivos | BAJA | CONFIRMADO | S | 2 | Dispositivos · API de campo |
| D-SEG-07 | Una regla de separación entre agente e institución puede romperse | BAJA | CONFIRMADO | S | 2 | Dispositivos · edificios |
| D-ERR-05 | La edición del legajo responde 500 si dos personas guardan el mismo código a la vez | BAJA | PLAUSIBLE | S | 1 | `programas/views/dispositivos_legajo.py` |
| D-ERR-06 | Borrar un grupo del formulario por tipo puede arrastrar en cascada un campo que se movió a ese… | BAJA | PLAUSIBLE | S | 3 | `programas/views/dispositivos_formularios.py` |
| D-ERR-07 | El toggle de tipo de dispositivo no es idempotente: un doble POST deja el estado como estaba | BAJA | CONFIRMADO | S | 3 | `programas/views/dispositivos_config.py` |
| D-ERR-08 | Un ingreso tipeado en el mismo minuto que un egreso previo se rechaza por los segundos | BAJA | CONFIRMADO | S | 3 | `programas/forms_ingreso.py` |
| D-ERR-09 | Los servicios no validan que el tipo de plaza sea admitido por el tipo de dispositivo | BAJA | PLAUSIBLE | S | 3 | `programas/services/estadias.py` |
| D-ERR-10 | `?tipo=` no numérico en el listado de instituciones da 500 | BAJA | CONFIRMADO | S | 3 | `programas/views/dispositivos_legajo.py` |
| D-ERR-11 | Con la sesión vencida, el formulario del tipo se reemplaza por la pantalla de login | BAJA | PLAUSIBLE | S | 3 | `programas/views/dispositivos_legajo.py` |
| D-ERR-12 | Entradas sin tope en el resultado de campo terminan en 500 en MariaDB estricto | BAJA | CONFIRMADO | S | 3 | `programas/api/serializers_inspecciones.py` |
| D-PERF-03 | `/media/` busca el adjunto de la bitácora y de los formularios del dispositivo por la ruta, en… | MEDIA | MEDIDO | S-M | 4 | `programas/models/__init__.py` |
| D-PERF-04 | P21 recorre el histórico entero de relevamientos unas 8 veces por carga, con un predicado de a… | BAJA | MEDIDO | S-M | 4 | `programas/views/dispositivos_relevamientos.py` |
| D-PERF-05 | Las alertas de reservas y préstamos vencidos no tienen tope: una por cada reserva olvidada, pa… | BAJA | PLAUSIBLE | S | 4 | `programas/services/alertas_dispositivos.py` |
| D-DAT-01 | Las trazas y la bitácora del historial no tienen índice que sirva al orden: cada detalle recor… | ALTA | MEDIDO | S-M | 4 | `programas/models/__init__.py` |
| D-LIM-31 | Las vistas reacomodan la salida del servicio y deciden la privacidad | BAJA | CONFIRMADO | S | 5 | `views/dispositivos_bitacora.py` |
| D-LIM-32 | Tres gates de sesión y permiso casi iguales, y `reportes` importa el mixin por la vista | BAJA | CONFIRMADO | S | 6 | `programas/mixins_dispositivos.py` |
| D-LIM-33 | El parseo de un id de GET está reescrito con cuatro reglas distintas (9 copias en el repo) | BAJA | CONFIRMADO | S | 6 | `programas/views/dispositivos_legajo.py` |
| D-LIM-34 | `UsuarioNoSumable` lleva un status HTTP: el servicio conoce el protocolo | BAJA | CONFIRMADO | S | 6 | `services/sumar_agente.py` |
| D-LIM-35 | `dispositivos_equipo.py` importa un helper privado de una vista de otra app y usa excepciones… | BAJA | CONFIRMADO | S | 6 | `views/dispositivos_equipo.py` |
| D-LIM-36 | Helpers de presentación copiados: `plural` ×3, `EXTENSIONES_IMAGEN` ×4, `_personas_prefetch`,… | BAJA | CONFIRMADO | S | 11 | `services/bitacora_detalle.py` |
| D-LIM-37 | Envoltorios identidad, constantes de capacidad y `_trazar` copiados entre módulos | BAJA | CONFIRMADO | S | 11 | `programas/services/ingreso.py` |
| D-LIM-38 | Formato del nombre de plaza y regla «asignación = cambio sin origen» repetidos pese a declarar… | BAJA | CONFIRMADO | S | 11 | `programas/services/nombre_plaza.py` |
| D-LIM-39 | `views/dispositivos_ingreso.py` (801 líneas): sesión, presentación y un preámbulo repetido en… | BAJA | CONFIRMADO | S-M | 11 | `programas/views/dispositivos_ingreso.py` |
| D-LIM-40 | `bitacora.py` repite validaciones: parseo de ids, turno en curso, dispositivo activo, nombre d… | BAJA | CONFIRMADO | S | 11 | `services/bitacora.py` |
| D-LIM-41 | Los cuatro mutadores del equipo repiten el mismo esqueleto | BAJA | CONFIRMADO | S | 11 | `services/equipo_dispositivo.py` |
| D-LIM-42 | `forms_bitacora` importa del servicio de pantalla y `bitacora.py` importa de un módulo de pres… | BAJA | CONFIRMADO | S | 11 | `services/bitacora_pantalla.py` |
| D-LIM-43 | El registro por momento de las respuestas del dispositivo está en tres lugares | BAJA | CONFIRMADO | S-M | 11 | `services/respuestas_dispositivo.py` |
| D-LIM-44 | `buscador_agentes.py` arma la fila dos veces | BAJA | CONFIRMADO | S | 11 | `services/buscador_agentes.py` |
| D-LIM-45 | Constantes de búsqueda redeclaradas y orden de turnos repetido | BAJA | CONFIRMADO | S | 11 | `selectors/personas_sugeridas.py` |
| D-LIM-46 | `forms_dispositivos.py` es un cajón de sastre de 861 líneas | BAJA | CONFIRMADO | S-M | 11 | `` |
| D-LIM-47 | Guardar una foto y guardar un adjunto repiten el mismo bloque y normalizan el UUID distinto | BAJA | CONFIRMADO | S | 11 | `programas/services/inspecciones.py` |
| D-LIM-48 | Alta y edición de edificio duplican la normalización y validación de código y nombre | BAJA | CONFIRMADO | S | 11 | `programas/services/edificios.py` |
| D-LIM-49 | `edificios_para_asignar` y `edificios_sin_relevar` (y la situación «vigentes») repiten la base… | BAJA | CONFIRMADO | S | 11 | `programas/services/inspecciones.py` |
| D-LIM-50 | La API de campo duplica las acciones `fotos` y `adjuntos` y arma su propio 400 legible | BAJA | CONFIRMADO | S | 11 | `programas/api/views_inspecciones.py` |
| D-LIM-51 | Presentación (íconos, tonos, notas, URLs) armada en servicios y en un selector | BAJA | CONFIRMADO | S-M | 11 | `programas/services/inspecciones.py` |
| D-FE-05 | Cadena if/elif tono → clase de badge copiada en 4 templates | BAJA | CONFIRMADO | S | 12 | `templates/programas/dispositivos/bitacora/entrada.html` |
| D-FE-06 | `legajo/form.html` lleva ~330 líneas de JS en cinco `<script>` inline | BAJA | CONFIRMADO | S-M | 12 | `programas/templates/programas/dispositivos/legajo/form.html` |
| D-FE-07 | Arranque del formulario dinámico del tipo copiado en dos templates | BAJA | CONFIRMADO | S | 12 | `programas/templates/programas/dispositivos/estadia/detalle.html` |
| D-FE-08 | `bitacora.html` lleva la lógica de Alpine inline y el objeto por defecto duplicado | BAJA | CONFIRMADO | S | 12 | `templates/programas/dispositivos/bitacora/bitacora.html` |
| D-FE-09 | El template de P21 tiene los «30 días» de la ventana de por vencer escritos a mano | BAJA | CONFIRMADO | S | 12 | `programas/templates/programas/dispositivos/relevamientos/list.html` |
| D-FE-10 | Validación del modal «Nuevo relevamiento» escrita como JS inline en un atributo | BAJA | CONFIRMADO | S | 12 | `programas/templates/programas/dispositivos/relevamientos/list.html` |
| D-ERR-13 | `nodo-formulario-tipo.js` vuelve a habilitar controles que el servidor renderizó deshabilitados | INFO | PLAUSIBLE | S | 3 | `static/custom/js/nodo-formulario-tipo.js` |
| D-ERR-14 | Fuera de AJAX, las acciones del Equipo muestran solo el primer error de validación | INFO | CONFIRMADO | S | 3 | `programas/views/dispositivos_equipo.py` |
| D-PERF-06 | `plaza_ocupada_despues_de` recorre todas las salidas históricas de la plaza dentro del `FOR UP… | INFO | PLAUSIBLE | S | 1 | `programas/services/movimientos.py` |
| D-PERF-07 | La fila del dispositivo serializa la operación: cada novedad de bitácora la toma con X y cada… | INFO | PLAUSIBLE | S | 1 | `programas/services/bitacora.py` |
| D-PERF-08 | El listado de Edificios calcula tres subconsultas y un GROUP BY sobre todo el alcance antes de… | BAJA | MEDIDO | S-M | 4 | `programas/selectors/edificios.py` |
| D-PERF-09 | El detalle arma el mapa completo de plazas solo para saber si hay alguna libre | INFO | MEDIDO | S | 4 | `programas/views/dispositivos_legajo.py` |
| D-PERF-10 | El informe de un relevamiento repite consultas de costo fijo (COUNT de fotos y alcance del coo… | INFO | MEDIDO | S | 4 | `programas/services/inspecciones.py` |

### Tabla de equivalencia con los IDs de tajada

| ID final | IDs de la pasada 1 |
|---|---|
| D-SEG-01 | D3-SEG-02 |
| D-SEG-02 | D1-SEG-01 + D3-SEG-01 |
| D-SEG-03 | D1-SEG-02 |
| D-SEG-04 | D1-SEG-03 |
| D-SEG-05 | D2-SEG-01 |
| D-SEG-06 | D4-SEG-02 |
| D-SEG-07 | D4-SEG-03 |
| D-ERR-01 | D2-ERR-01 + D2-DAT-01 + D3-DAT-01 |
| D-ERR-02 | D1-ERR-01 + D2-ERR-03 + D2-ERR-04 + D2-LIM-05 |
| D-ERR-03 | D2-ERR-02 |
| D-ERR-04 | D4-ERR-01 |
| D-ERR-05 | D1-ERR-03 |
| D-ERR-06 | D3-ERR-01 |
| D-ERR-07 | D3-ERR-02 + D3-LIM-07 |
| D-ERR-08 | D2-ERR-05 |
| D-ERR-09 | D2-ERR-06 |
| D-ERR-10 | D1-ERR-02 |
| D-ERR-11 | D1-ERR-05 |
| D-ERR-12 | D4-ERR-02 |
| D-ERR-13 | D3-ERR-03 |
| D-ERR-14 | D3-ERR-04 |
| D-PERF-01 | D1-PERF-01 + D1-ERR-04 |
| D-PERF-02 | D2-PERF-01 |
| D-PERF-03 | D3-PERF-01 |
| D-PERF-04 | D4-PERF-01 |
| D-PERF-05 | D1-PERF-02 |
| D-PERF-06 | D2-PERF-02 |
| D-PERF-07 | D2-PERF-03 |
| D-PERF-08 | D4-PERF-02 |
| D-PERF-09 | D1-PERF-03 |
| D-PERF-10 | D4-PERF-03 |
| D-DAT-01 | D1-DAT-01 |
| D-LIM-01 | D4-LIM-05 + D4-SEG-01 |
| D-LIM-02 | D2-LIM-03 |
| D-LIM-03 | D1-LIM-02 |
| D-LIM-04 | D1-LIM-11 |
| D-LIM-05 | D1-LIM-12 |
| D-LIM-06 | D1-LIM-05 |
| D-LIM-07 | D3-LIM-05 |
| D-LIM-08 | D3-LIM-04 + D3-PERF-02 |
| D-LIM-09 | D4-LIM-04 |
| D-LIM-10 | D1-LIM-06 |
| D-LIM-11 | D1-LIM-04 |
| D-LIM-12 | D2-LIM-09 |
| D-LIM-13 | D3-LIM-02 + D4-LIM-08 + D1-LIM-07 |
| D-LIM-14 | D2-LIM-02 |
| D-LIM-15 | D2-LIM-06 |
| D-LIM-16 | D2-LIM-04 |
| D-LIM-17 | D2-LIM-07 |
| D-LIM-18 | D2-LIM-10 |
| D-LIM-19 | D2-LIM-11 |
| D-LIM-20 | D2-LIM-01 |
| D-LIM-21 | D1-LIM-03 |
| D-LIM-22 | D1-LIM-10 |
| D-LIM-23 | D1-LIM-13 |
| D-LIM-24 | D1-LIM-09 |
| D-LIM-25 | D1-LIM-01 |
| D-LIM-26 | D3-LIM-01 |
| D-LIM-27 | D3-LIM-03 |
| D-LIM-28 | D4-LIM-03 |
| D-LIM-29 | D4-LIM-02 |
| D-LIM-30 | D4-LIM-01 |
| D-LIM-31 | D3-LIM-06 |
| D-LIM-32 | D1-LIM-14 |
| D-LIM-33 | D1-LIM-08 |
| D-LIM-34 | D3-LIM-09 |
| D-LIM-35 | D3-LIM-08 |
| D-LIM-36 | D3-LIM-11 + D1-LIM-16 + D4-LIM-06 |
| D-LIM-37 | D2-LIM-13 + D4-LIM-13 |
| D-LIM-38 | D2-LIM-12 + D3-LIM-16 |
| D-LIM-39 | D2-LIM-08 |
| D-LIM-40 | D3-LIM-12 |
| D-LIM-41 | D3-LIM-13 |
| D-LIM-42 | D3-LIM-10 |
| D-LIM-43 | D3-LIM-14 |
| D-LIM-44 | D3-LIM-15 |
| D-LIM-45 | D3-LIM-17 |
| D-LIM-46 | D3-LIM-18 |
| D-LIM-47 | D4-LIM-07 |
| D-LIM-48 | D4-LIM-09 |
| D-LIM-49 | D4-LIM-10 |
| D-LIM-50 | D4-LIM-11 |
| D-LIM-51 | D4-LIM-12 |
| D-FE-01 | D1-FE-01 |
| D-FE-02 | D3-FE-01 |
| D-FE-03 | D3-FE-02 |
| D-FE-04 | D2-FE-01 |
| D-FE-05 | D3-FE-03 + D4-FE-01 |
| D-FE-06 | D1-FE-02 |
| D-FE-07 | D2-FE-02 |
| D-FE-08 | D3-FE-04 |
| D-FE-09 | D4-FE-02 |
| D-FE-10 | D4-FE-03 |
| (Descartados) | D1-LIM-15 |

## 3. Plan por olas

Lo confirmado primero; después por tema y por archivo, para que los PRs no se pisen. Horas con S=2, S-M=4, M=8, L=20. Un issue por ola; las olas 11 y 12 son un backlog opcional con su propio subtotal. La Ola 0 es solo seguridad confirmada o con PoC; los candados (PoC confirmada, MEDIA) abren la primera ola de concurrencia, no la Ola 0.

| Ola | Nombre | Fichas | Horas |
|---|---|---|---|
| 0 | Seguridad confirmada (detalle reservado hasta el arreglo) | 3 | 6 |
| 1 | Concurrencia: orden de candados y carreras del legajo | 4 | 10 |
| 2 | Datos personales y alcance en historial, trayectoria y API de campo | 9 | 24 |
| 3 | Correcciones de borde: cierre, retroactivo, constructor y cargas tardías | 12 | 32 |
| 4 | Rendimiento medible: historial, censo, `/media/`, alta y edificios | 10 | 36 |
| 5 | De fondo: dominio de Dispositivos fuera de las vistas | 7 | 26 |
| 6 | De fondo: traductor único de errores, gates y parseo compartido | 5 | 12 |
| 7 | Estadías, plazas e ingreso: servicios, «plaza tomada» y mapa único | 7 | 40 |
| 8 | Legajo, historial, bitácora y constructor: estructura y tamaño | 7 | 48 |
| 9 | Edificios e inspecciones: capas, tamaño y regla de vencimiento | 3 | 16 |
| 10 | Front de prioridad media | 4 | 14 |
| 11 | Limpieza de código (opcional): helpers, constantes y tamaño | 16 | 40 |
| 12 | Limpieza de front (opcional): JS inline, mapeos de tono y arranques | 6 | 14 |
| | **Subtotal olas 0 a 10** | **71** | **264** |
| | **Subtotal olas 11 y 12 (opcional)** | **22** | **54** |
| | **Total** | **93** | **318** |

### Ola 0 · Seguridad confirmada (detalle reservado hasta el arreglo) (6 h, 3 fichas)

Tres fichas chicas con arreglo escrito, todas de datos personales o de roles: D-SEG-01 (PoC confirmada), la visibilidad del agente asignado (la ALTA del capítulo) y D-SEG-02. D-SEG-02 lleva DECISIÓN CLIENTE con default aplicable (sección 7). Detalle técnico reservado hasta el arreglo.

- **D-SEG-01** [MEDIA · S] Un atajo permite otorgarse un rol propio
- **D-LIM-01** [ALTA · S] La vista reescribe la regla de privacidad «quién ve al agente asignado» en lugar de usar el helper por lote que existe
- **D-SEG-02** [MEDIA · S] El historial muestra texto libre a quien no puede ver a la persona

### Ola 1 · Concurrencia: orden de candados y carreras del legajo (10 h, 4 fichas)

La primera ola de concurrencia. Se fija **un** orden global de candados (contradicción 1) y se prueba con la PoC de dos hilos (PoC reproducida; test en el PR que la arregla, con `DJANGO_SYNCDB_PROJECT_APPS=False`). Va primero el orden y la traducción del 1213; las dos fichas INFO de la fila del dispositivo se miden después (8.a).

- **D-ERR-01** [MEDIA · S-M] Configurar capacidad toma dispositivo→plaza y el ingreso toma plaza→dispositivo: deadlock 1213 (orden global adoptado: resolución 1 de la sección 1)
- **D-ERR-05** [BAJA · S] La edición del legajo responde 500 si dos personas guardan el mismo código a la vez
- **D-PERF-06** [INFO · S] `plaza_ocupada_despues_de` recorre todas las salidas históricas de la plaza dentro del `FOR UPDATE`
- **D-PERF-07** [INFO · S] La fila del dispositivo serializa la operación: cada novedad de bitácora la toma con X y cada ingreso, egreso o cambio necesita S por…

### Ola 2 · Datos personales y alcance en historial, trayectoria y API de campo (24 h, 9 fichas)

Datos personales y alcance en las pantallas que se leen sin `ciudadano.ver`: historial, trayectoria, formulario público de la API de campo. Un solo patrón de arreglo (redactar o no mostrar), un test parametrizado por usuario sin `ciudadano.ver` (regla R-4). Incluye las reglas de alcance escritas en varios lugares (enmascarado de la persona, y quién puede administrar usuarios de Dispositivos).

- **D-SEG-03** [BAJA · S] El historial expone un dato personal del responsable
- **D-SEG-04** [BAJA · S-M] El historial muestra datos de relevamientos fuera de alcance
- **D-SEG-05** [BAJA · S-M] Una redacción por alcance se anula por otros caminos de lectura
- **D-SEG-06** [BAJA · S] La API de campo no limita las cargas de archivos
- **D-SEG-07** [BAJA · S] Una regla de separación entre agente e institución puede romperse
- **D-LIM-04** [MEDIA · S-M] El selector de auditoría decide la regla de privacidad del relevamiento y arma la presentación
- **D-LIM-05** [MEDIA · S] El historial borra el id del ciudadano con una regex sobre un texto que escribe otro servicio
- **D-LIM-06** [MEDIA · S] El enmascarado de la persona («Persona alojada») se resuelve en cinco lugares con dos redacciones
- **D-LIM-07** [MEDIA · S] `puede_administrar_usuarios_dispositivos` es una regla paralela a `programas_administrables_usuarios`

### Ola 3 · Correcciones de borde: cierre, retroactivo, constructor y cargas tardías (32 h, 12 fichas)

Correcciones chicas de borde, cada una con su test. El cierre del dispositivo lleva DECISIÓN CLIENTE (default aplicable); la carga tardía de fotos tras «Revisado» también.

- **D-ERR-02** [MEDIA · M] Cerrar un dispositivo no mira si tiene personas alojadas o reservas, y después del cierre se puede seguir operando
- **D-ERR-03** [MEDIA · S] El ingreso retroactivo no tiene cota inferior: reescribe censo, historial y turnos viejos
- **D-ERR-04** [MEDIA · S-M] Una foto o un adjunto que llega después de «Revisado» se rechaza para siempre y la evidencia se pierde
- **D-ERR-06** [BAJA · S] Borrar un grupo del formulario por tipo puede arrastrar en cascada un campo que se movió a ese grupo al mismo tiempo (TOCTOU)
- **D-ERR-07** [BAJA · S] El toggle de tipo de dispositivo no es idempotente: un doble POST deja el estado como estaba
- **D-ERR-08** [BAJA · S] Un ingreso tipeado en el mismo minuto que un egreso previo se rechaza por los segundos
- **D-ERR-09** [BAJA · S] Los servicios no validan que el tipo de plaza sea admitido por el tipo de dispositivo
- **D-ERR-10** [BAJA · S] `?tipo=` no numérico en el listado de instituciones da 500
- **D-ERR-11** [BAJA · S] Con la sesión vencida, el formulario del tipo se reemplaza por la pantalla de login
- **D-ERR-12** [BAJA · S] Entradas sin tope en el resultado de campo terminan en 500 en MariaDB estricto
- **D-ERR-13** [INFO · S] `nodo-formulario-tipo.js` vuelve a habilitar controles que el servidor renderizó deshabilitados
- **D-ERR-14** [INFO · S] Fuera de AJAX, las acciones del Equipo muestran solo el primer error de validación

### Ola 4 · Rendimiento medible: historial, censo, `/media/`, alta y edificios (36 h, 10 fichas)

Medido en el banco el 19-nov-2026 (sección 8.d): **D-PERF-01 y D-DAT-01 son ALTA y van primero en esta ola**. Las rutas de Dispositivos ya están en el banco (#1220). El índice del historial y el arreglo del historial paginado van en el mismo PR (expand puro).

- **D-PERF-01** [ALTA · M] El historial del detalle lee y arma en Python toda la auditoría anterior a la página pedida
- **D-DAT-01** [ALTA · S-M] Las trazas y la bitácora del historial no tienen índice que sirva al orden: cada detalle recorre toda la historia del dispositivo
- **D-PERF-02** [MEDIA · S] El censo del día lee el histórico entero de estadías del dispositivo
- **D-PERF-03** [MEDIA · S-M] `/media/` busca el adjunto de la bitácora y de los formularios del dispositivo por la ruta, en columnas sin índice: un scan completo p…
- **D-LIM-08** [INFO · S-M] La consulta «pares usuario×rol sumables» está escrita tres veces y el contrato `"u:r"` vive en tres archivos
- **D-PERF-04** [BAJA · S-M] P21 recorre el histórico entero de relevamientos unas 8 veces por carga, con un predicado de alcance que no usa índice
- **D-PERF-05** [BAJA · S] Las alertas de reservas y préstamos vencidos no tienen tope: una por cada reserva olvidada, para siempre
- **D-PERF-08** [BAJA · S-M] El listado de Edificios calcula tres subconsultas y un GROUP BY sobre todo el alcance antes de recortar la página
- **D-PERF-09** [INFO · S] El detalle arma el mapa completo de plazas solo para saber si hay alguna libre
- **D-PERF-10** [INFO · S] El informe de un relevamiento repite consultas de costo fijo (COUNT de fotos y alcance del coordinador dos veces)

### Ola 5 · De fondo: dominio de Dispositivos fuera de las vistas (26 h, 7 fichas)

Regla de dominio escrita en la vista que ya tiene el servicio (regla R-1). Empieza por las dos ALTA. Se hace después de la Ola 0 porque D4-LIM-04 comparte líneas con la ficha del agente asignado.

- **D-LIM-02** [ALTA · S-M] Lógica de dominio y transacción de negocio en la vista del asistente de ingreso
- **D-LIM-03** [ALTA · S-M] La edición del legajo (diff, contacto, traza y envío) se escribe en la vista
- **D-LIM-09** [MEDIA · M] La vista de P21 arma ~330 líneas de view-model y muta instancias del modelo con 18 atributos sueltos
- **D-LIM-10** [MEDIA · S-M] La vista del detalle arma a mano cada fila de estadías, y la regla «se puede mover» está triplicada
- **D-LIM-31** [BAJA · S] Las vistas reacomodan la salida del servicio y deciden la privacidad
- **D-LIM-11** [MEDIA · S] La regla «puede dar de alta = `dispositivo.crear` + alcance de admin» está escrita en cuatro lugares
- **D-LIM-12** [MEDIA · S] El gate del asistente reimplementa `puede_ingresar_persona`, que se declara «única fuente de la regla»

### Ola 6 · De fondo: traductor único de errores, gates y parseo compartido (12 h, 5 fichas)

Un traductor único de errores por superficie y un solo gate de sesión y permiso. Se hace después de la Ola 5 para no mover dos veces las mismas vistas. Coordinada con Emergencia (E-LIM-12, E-LIM-13, E-LIM-14) y Becas (B-LIM-65).

- **D-LIM-13** [MEDIA · S-M] Tres vistas de Dispositivos reescriben `ajax_utils.errores_del_servicio`/`rechazar`
- **D-LIM-32** [BAJA · S] Tres gates de sesión y permiso casi iguales, y `reportes` importa el mixin por la vista
- **D-LIM-33** [BAJA · S] El parseo de un id de GET está reescrito con cuatro reglas distintas (9 copias en el repo)
- **D-LIM-34** [BAJA · S] `UsuarioNoSumable` lleva un status HTTP: el servicio conoce el protocolo
- **D-LIM-35** [BAJA · S] `dispositivos_equipo.py` importa un helper privado de una vista de otra app y usa excepciones como control de flujo

### Ola 7 · Estadías, plazas e ingreso: servicios, «plaza tomada» y mapa único (40 h, 7 fichas)

Los servicios de estadías, plazas e ingreso: una definición de «plaza tomada», un constructor del mapa de plazas, las API públicas que consume Emergencia. Coordinada con la fachada de Emergencia (E-LIM-19, E-LIM-37).

- **D-LIM-14** [MEDIA · M] El ciclo de vida de la estadía repite a mano su máquina de estados en cuatro servicios
- **D-LIM-15** [MEDIA · S-M] Tres definiciones de «plaza tomada» repartidas en cinco lugares
- **D-LIM-16** [MEDIA · S-M] La API que consumen Emergencia y `plazas.py` sigue siendo privada (inventario completo más allá de E-LIM-19)
- **D-LIM-17** [MEDIA · M] Dos constructores del mapa de plazas en paralelo (ingreso y «Sectores y plazas»)
- **D-LIM-18** [MEDIA · S-M] `ingreso.py` aloja la identidad de la persona (DNI, RENAPER, alta de legajo) que usa medio sistema
- **D-LIM-19** [MEDIA · S-M] `sectores_plazas.py` es un presentador en `services/`: arma URLs, payload del modal y nombres de funciones JS
- **D-LIM-20** [MEDIA · M] `estadias.py` supera las 1000 líneas mezclando cinco responsabilidades

### Ola 8 · Legajo, historial, bitácora y constructor: estructura y tamaño (48 h, 7 fichas)

Estructura y tamaño del legajo, del historial, de la bitácora y del constructor. El constructor de formularios (ficha del pegamento HTTP) comparte esfuerzo con B-LIM-38, Ola 12 de Becas.

- **D-LIM-21** [MEDIA · M] La máquina de estados del legajo está repartida en 7 servicios, 7 vistas y el template, que reescribe los orígenes
- **D-LIM-22** [MEDIA · S-M] `infraestructura_del_dispositivo`: 240 líneas, tres modos y un dict de 16 claves implícitas
- **D-LIM-23** [MEDIA · S-M] Los códigos de acción de `TrazaDispositivo` son strings sueltos en seis módulos, sin `choices`
- **D-LIM-24** [MEDIA · M] `detalle_dispositivo.py` (893) junta dos dominios, y el de Infraestructura lo importa un selector
- **D-LIM-25** [MEDIA · M] `views/dispositivos_legajo.py` tiene 1659 líneas y mezcla cuatro pantallas
- **D-LIM-26** [MEDIA · M] El constructor de formularios de Dispositivos es una copia de views/diseno.py (Becas)
- **D-LIM-27** [MEDIA · M] `pantalla_bitacora` es una función de 318 líneas que mezcla todo

### Ola 9 · Edificios e inspecciones: capas, tamaño y regla de vencimiento (16 h, 3 fichas)

Capas invertidas, tamaño de `services/inspecciones.py` y la regla de «vencido / por vencer» escrita cinco veces (con test de paridad Python/SQL).

- **D-LIM-28** [MEDIA · S-M] La regla de «vencido / por vencer» está escrita cinco veces, en Python y en SQL por separado
- **D-LIM-29** [MEDIA · S-M] Capas invertidas: los selectores importan de los servicios y un módulo existe solo para cortar el ciclo
- **D-LIM-30** [MEDIA · M] `services/inspecciones.py` pasa las 1.000 líneas y mezcla cinco responsabilidades

### Ola 10 · Front de prioridad media (14 h, 4 fichas)

Cuatro fichas de front de prioridad media: el cuerpo del modal de egreso copiado, el JS inline del tipo de dispositivo, la duplicación `nodo-formulario(-tipo).js` y el componente Alpine embebido en un atributo. No se tocan clases ni estructura visible sin pasar por el agente de diseño.

- **D-FE-01** [MEDIA · S] El cuerpo del modal de egreso está copiado entre el detalle (P4) y la estadía (P7)
- **D-FE-02** [MEDIA · S-M] `tipo_detail.html` lleva 175 líneas de JS inline que reimplementan, y contradicen, el handler `data-ajax` canónico
- **D-FE-03** [MEDIA · S-M] `nodo-formulario-tipo.js` duplica `nodo-formulario.js` (link público de Becas) con divergencias
- **D-FE-04** [MEDIA · S-M] Componente Alpine de ~55 líneas embebido en un atributo `x-data`, con nombres de acción duplicados entre Python y JS

### Ola 11 · Limpieza de código (opcional): helpers, constantes y tamaño (40 h, 16 fichas)

Backlog opcional: duplicaciones y constantes sin riesgo. Cada ficha es chica; lo que las cierra es el test de «un solo dueño» (regla R-9).

- **D-LIM-36** [BAJA · S] Helpers de presentación copiados: `plural` ×3, `EXTENSIONES_IMAGEN` ×4, `_personas_prefetch`, `_autor`, formato de fecha
- **D-LIM-37** [BAJA · S] Envoltorios identidad, constantes de capacidad y `_trazar` copiados entre módulos
- **D-LIM-38** [BAJA · S] Formato del nombre de plaza y regla «asignación = cambio sin origen» repetidos pese a declararse únicos
- **D-LIM-39** [BAJA · S-M] `views/dispositivos_ingreso.py` (801 líneas): sesión, presentación y un preámbulo repetido en cada handler
- **D-LIM-40** [BAJA · S] `bitacora.py` repite validaciones: parseo de ids, turno en curso, dispositivo activo, nombre de turno
- **D-LIM-41** [BAJA · S] Los cuatro mutadores del equipo repiten el mismo esqueleto
- **D-LIM-42** [BAJA · S] `forms_bitacora` importa del servicio de pantalla y `bitacora.py` importa de un módulo de presentación
- **D-LIM-43** [BAJA · S-M] El registro por momento de las respuestas del dispositivo está en tres lugares
- **D-LIM-44** [BAJA · S] `buscador_agentes.py` arma la fila dos veces
- **D-LIM-45** [BAJA · S] Constantes de búsqueda redeclaradas y orden de turnos repetido
- **D-LIM-46** [BAJA · S-M] `forms_dispositivos.py` es un cajón de sastre de 861 líneas
- **D-LIM-47** [BAJA · S] Guardar una foto y guardar un adjunto repiten el mismo bloque y normalizan el UUID distinto
- **D-LIM-48** [BAJA · S] Alta y edición de edificio duplican la normalización y validación de código y nombre
- **D-LIM-49** [BAJA · S] `edificios_para_asignar` y `edificios_sin_relevar` (y la situación «vigentes») repiten la base del filtro
- **D-LIM-50** [BAJA · S] La API de campo duplica las acciones `fotos` y `adjuntos` y arma su propio 400 legible
- **D-LIM-51** [BAJA · S-M] Presentación (íconos, tonos, notas, URLs) armada en servicios y en un selector

### Ola 12 · Limpieza de front (opcional): JS inline, mapeos de tono y arranques (14 h, 6 fichas)

Backlog opcional: JS inline chico, mapeos de tono y arranques de formularios sin riesgo.

- **D-FE-05** [BAJA · S] Cadena if/elif tono → clase de badge copiada en 4 templates
- **D-FE-06** [BAJA · S-M] `legajo/form.html` lleva ~330 líneas de JS en cinco `<script>` inline
- **D-FE-07** [BAJA · S] Arranque del formulario dinámico del tipo copiado en dos templates
- **D-FE-08** [BAJA · S] `bitacora.html` lleva la lógica de Alpine inline y el objeto por defecto duplicado
- **D-FE-09** [BAJA · S] El template de P21 tiene los «30 días» de la ventana de por vencer escritos a mano
- **D-FE-10** [BAJA · S] Validación del modal «Nuevo relevamiento» escrita como JS inline en un atributo

**Resoluciones del juez (19-nov-2026)**, una por contradicción:

1. **Orden global de candados: se adopta** el propuesto (**entrada de bitácora → estadías (pk) → plazas (pk) → reservas → ciudadano → dispositivo → sector**). El PR de D-ERR-01 tiene que **verificarlo contra ingreso, egreso, cambio de plaza y reserva** (que tomen las estadías antes que las plazas en ese orden) antes de tocar código, con la PoC de dos hilos; la alternativa común (reintentar ante 1213 con tope) queda como red de seguridad. El orden es el mismo que en Emergencia (E-LIM-15).
2. **CERRADO contra no ACTIVO: DECISIÓN CLIENTE**, default «cerrado»: una sola `dispositivo_operable(d)` que rechaza `CERRADO` en todo mutador, y «no ACTIVO» solo donde ya se exige (bitácora, reservas). Entra en la sección 7.
3. **Helpers de formato:** van a `core/texto.py` (y `core/archivos.py` para las extensiones) **si se usan fuera de `programas/`**; si no, a `programas/services/formato.py`. El PR lo decide con `grep` sobre los consumidores (`EXTENSIONES_IMAGEN` ya lo usa `notificaciones/services/paquete.py`, o sea `core/archivos.py`). Un solo PR con la Ola 7 de Emergencia.
4. **`ve_la_asignacion_en_lote`:** aprobado.
5. **Severidad de D-SEG-02: MEDIA**, como quedó.
6. **D3-FE-01 (D-FE-02) NO promueve `_ajax_js`** (descartado en octubre, §8.1): se usa el handler `data-ajax` canónico que ya cargan las pantallas de Dispositivos; si ese handler solo existiera en `programas/becas/`, se hace solo el paso 1.
7. **Numeración de olas:** la de este informe.
8. **Banco:** se siembra el volumen mayor: **500 plazas, 10 sectores, 3 turnos y 20.000 estadías** en el dispositivo grande (sección 8.c).

## 4. Reglas propuestas

Consolidadas: las reglas de las fichas que dicen lo mismo quedan en una sola fila. «Control mecánico» primero; skill, agente y `CLAUDE.md` solo donde ningún control lo ve. Ninguna aplica a toda sesión, así que ninguna va a `CLAUDE.md`.

| # | Tipo | Destino | Regla | Fichas |
|---|---|---|---|---|
| R-1 | control mecánico | `programas/tests/test_arquitectura.py` · ratchet con `ast` (**regla transversal «lógica de dominio en vistas»**) | Una clase de `programas/views/` o `programas/api/` no abre `transaction.atomic()`, no llama `select_for_update()` ni `.save()`/`.create()`/`.update()` sobre un modelo de dominio, y no decide una regla de privacidad: lo hace un servicio. Lista congelada de lo existente (D-LIM-02, D-LIM-03, D-LIM-09, D-LIM-01, D-LIM-31, D-ERR-07); el conjunto no puede crecer. Mensaje: «La vista orquesta, el servicio decide: mové esto a `services/`». No confundir con el ratchet de aristas vista → vista (RED-79), que octubre refutó. Misma regla que Becas ola 7 (B-LIM-01 a B-LIM-06) y E-LIM-01. | D-ERR-07, D-LIM-01, D-LIM-02, D-LIM-03, D-LIM-09, D-LIM-31 |
| R-2 | control mecánico | `users/tests/` o `programas/tests/test_roles_atajos.py` · ratchet | Todo atajo que otorga roles aplica la misma guarda que el ABM de usuarios (la guarda del ABM de usuarios, patrón de #1114). Un test recorre los servicios y vistas que otorgan grupos y exige que importen la guarda, con lista congelada; y un test de comportamiento por atajo, con mutación (quitar la guarda y ver el test rojo). | D-SEG-01 |
| R-3 | control mecánico | `programas/tests/test_orden_candados.py` + skill `.claude/skills/mysql-mariadb/` | Orden global de candados de Dispositivos y Emergencia: **entrada de bitácora → estadías (pk) → plazas (pk) → reservas → ciudadano → dispositivo → sector**. Todo servicio que toma dos o más lo hace con un helper único (`bloquear_en_orden(...)`). Test de concurrencia con dos hilos sobre los dos caminos de la PoC, etiquetado `concurrencia`, que corre solo contra MariaDB (job efímero) con `DJANGO_SYNCDB_PROJECT_APPS=False`. Skill: «una transacción que toma más de un candado los toma siempre en el orden del módulo; ante un 1213 se reintenta la transacción entera con tope, nunca se deja pasar un 500». | D-ERR-01, D-PERF-06, D-PERF-07 |
| R-4 | control mecánico | `programas/tests/test_privacidad_texto_libre.py` (invariante del Cambio 271 para texto libre) | Un usuario con `dispositivo.ver` y sin `ciudadano.ver` recorre las pantallas de un dispositivo con datos libres y personales sembrados con un centinela; el test falla si el centinela aparece. Se agrega una pantalla a la lista cada vez que se agrega una que muestra texto de otro. Regla: el texto libre y los datos de personas solo salen con `ciudadano.ver`. | D-SEG-02, D-SEG-03, D-SEG-04, D-SEG-05, D-LIM-04, D-LIM-05 |
| R-5 | control mecánico | `programas/tests/test_alcance_asignacion.py` · «un solo dueño» | «Quién ve al agente asignado» tiene un solo dueño (`ve_la_asignacion` / `ve_la_asignacion_en_lote` en `services/inspecciones.py`). El test busca `asignado_a`/`agente_asignado` en vistas, selectores y templates y falla si aparece fuera del dueño y de una lista congelada. Test funcional: reservado hasta el arreglo. | D-LIM-01 |
| R-6 | control mecánico | `programas/tests/test_arquitectura.py` · ratchet de traductores | Un `except (ValidationError, EstadoCambio, ...)` en `programas/views/` o `programas/api/` que arma una respuesta a mano se congela; las vistas nuevas usan el traductor único de la superficie (`respuestas.py` / `handle_exception`). Mensaje: «Traducí el error con el traductor de la superficie, no con un try/except propio». Los cuerpos de la API de campo (`detail`, `non_field_errors`) no cambian sin test de contrato y release coordinado con Chaco-mobile. Coordinado con E-LIM-12, E-LIM-13, E-LIM-14 y B-LIM-65. | D-LIM-13, D-LIM-34, D-LIM-35 |
| R-7 | control mecánico | `programas/tests/test_arquitectura.py` · ratchet de tamaño | Ningún archivo de `programas/` pasa de 1.000 líneas y ninguna función de 250, salvo una lista congelada que solo baja: `views/dispositivos_legajo.py` (1659), `services/estadias.py`, `services/inspecciones.py`, `services/detalle_dispositivo.py` (893) y `pantalla_bitacora` (318 líneas en una función). Mensaje: «Partí el módulo por responsabilidad antes de agregarle código». | D-LIM-20, D-LIM-24, D-LIM-25, D-LIM-27, D-LIM-30, D-LIM-39, D-LIM-46 |
| R-8 | control mecánico | `programas/tests/test_dispositivo_cerrado.py` · tabla de mutadores | Una tabla (`MUTADORES_DE_DISPOSITIVO`) lista cada función pública de `services/dispositivos.py`, `estadias.py` y `plazas.py` que escribe; un test parametrizado la ejecuta con un dispositivo `CERRADO` y exige `ValidationError` (y, para las que toman una plaza, sin 500 si la plaza se desactivó en paralelo). Otro test recorre las funciones públicas del módulo y falla si una que escribe no está en la tabla. La guarda vive en el servicio, no en la vista. | D-ERR-02, D-ERR-09 |
| R-9 | control mecánico | `programas/tests/test_un_solo_dueno.py` | Cada helper compartido tiene un solo dueño y una lista congelada de definiciones paralelas: `def plural(`, `def _nombre(`/`nombre_visible`, `EXTENSIONES_IMAGEN =`, `CAP_ADMITIR =`/`CAP_*`, `plaza_con_sector`, `MINIMO_CARACTERES`, parseo de ids de GET (`isascii() and isdecimal()`). El test falla si aparece una definición nueva fuera del dueño. Es la misma regla que E-LIM-25 y E-LIM-27 en Emergencia. | D-LIM-15, D-LIM-17, D-LIM-33, D-LIM-36, D-LIM-37, D-LIM-38, D-LIM-45 |
| R-10 | control mecánico | `scripts/design_audit.py` · regla nueva `BADGEIF` (ratchet) | En un parcial o template, una cadena `{% if <var> == '<MAYÚSCULAS>' %}badge-` o un `if/elif` que mapea un código de tono a una clase se marca: el tono se resuelve en Python (filtro `badge_tono`) y llega como variable. Una sola tabla de tonos para Emergencia y Dispositivos (E-LIM-29). Verificar que `tailwind.config` escanee `**/templatetags/*.py` y correr `npm run build:tailwind`. | D-FE-05 |
| R-11 | control mecánico | `scripts/design_audit.py` · regla de JS inline (ratchet) + test de contrato del front | Un `<script>` inline de más de 40 líneas o un componente Alpine de más de 15 líneas en un atributo `x-data` se marcan; el JS va a `static/custom/js/`. Dos archivos JS no implementan la misma lógica de condiciones: un solo módulo (`nodo-condiciones.js`) con las divergencias como opciones. No se promueven `_ajax_js`/`_modal_*` a `components/` (descartado en octubre). | D-FE-01, D-FE-02, D-FE-03, D-FE-04, D-FE-06, D-FE-07, D-FE-08, D-FE-10 |
| R-12 | control mecánico | `scripts/perf_budgets.json` + `programas/tests/test_presupuestos_dispositivos.py` (`--tag performance`) | Presupuestos de consultas y de bytes para las pantallas que la pasada 2 mida: `dispositivo_detalle`, `dispositivo_historial` (página profunda), `dispositivo_censo`, `dispositivos_alta`, `edificios_listado`, `relevamientos_p21`. El historial hidrata solo la página pedida; el alta no carga todo el padrón de pares usuario×rol; el censo del día no lee el histórico entero. Cada ficha PERF cierra con su entrada en el archivo. | D-PERF-01, D-PERF-02, D-PERF-04, D-PERF-08, D-PERF-09, D-PERF-10, D-DAT-01, D-LIM-08 |
| R-13 | skill | `.claude/skills/mysql-mariadb/` · sección «Índices en columnas de lookup por ruta» | «Toda vista que busca un archivo por su ruta (`/media/`) lo hace por una columna con índice (o un prefijo) o por un id en la URL; un `filter(archivo=...)` sobre una columna sin índice es un recorrido completo que crece con el histórico. Los índices solo de orden se piden con su EXPLAIN.» | D-PERF-03, D-DAT-01 |
| R-14 | skill | `.claude/skills/mysql-mariadb/` · sección «Transacciones y bloqueos» | «La validación que depende de filas se hace dentro de la operación que toma el candado (releer bajo el candado y decidir), y una operación sobre un estado es idempotente: recibe el estado deseado, no “invertir”.» Casos: borrar un grupo del constructor que arrastra un campo movido (D-ERR-06), el toggle de tipo (D-ERR-07), el 500 por código repetido a la vez en la edición del legajo (D-ERR-05). | D-ERR-03, D-ERR-04, D-ERR-05, D-ERR-06, D-ERR-07 |
| R-15 | skill | `.claude/skills/auditoria/rubricas/dispositivos.md` (rúbrica nueva) | Qué mirar la próxima vez en Dispositivos: orden de candados de las cuatro rutas de escritura (estadía, plaza, bitácora, reserva); guarda de dispositivo cerrado en cada mutador; texto libre y datos de personas en pantallas sin `ciudadano.ver`; visibilidad del agente asignado (Cambio 428); cargas tardías de la app de campo; `/media/` por tabla de adjuntos. | D-SEG-02, D-ERR-01, D-ERR-02, D-ERR-04, D-PERF-03, D-LIM-01 |

## 5. Descartados

Cruce con `docs/internal/auditoria-2026-10/README.md` (§0.4 y §8): lo que allí se descartó sin hechos nuevos queda descartado acá, con el motivo. Después, lo que los revisores miraron y salió limpio (para que la próxima auditoría no lo reabra).

| Propuesta o hallazgo | Por qué no | Qué se hace en su lugar |
|---|---|---|
| Pasar `ItemDiseno.padre` (y sus FK) a PROTECT para evitar el borrado en cascada del constructor (relacionado con D-ERR-06) | Octubre A8-01 / Cambio 58: contradice que el diseño sigue al catálogo (`README.md` §8.1). | Validar dentro de la operación que toma el candado (ficha D-ERR-06). |
| Un límite por IP o con `NUM_PROXIES` para la API de campo (D-SEG-06) | Octubre A2-01: el cliente cambia entre DEV (nginx) e ingreso de ECOM; NAT de las operadoras. | Un límite por usuario y por objeto padre; es lo que propone la ficha. |
| Globalizar `programa.configurar` para simplificar `puede_administrar_usuarios_dispositivos` (D-LIM-07) | Octubre A5-07 / SEC-07: Dispositivos la evalúa con programa. | Alinear con `programas_administrables_usuarios` sin tocar la capacidad. |
| Promover `_ajax_js`, `_modal_*`, `_field`, `_confirm_js` a `components/` (D-FE-02, D-FE-01) | Octubre A7: refactor que rompe consumidores; se declaran transversales. | Extraer el JS a `static/custom/js/` y usar el handler que ya cargan las pantallas de Dispositivos (contradicción 6 de la sección 1). |
| Ratchet «ninguna vista importa de otra vista» o `test_ninguna_vista_importa_de_otra_vista` (a propósito de D-LIM-32 y D-LIM-37) | Octubre RED-79: refutado; la regla es un ratchet de aristas existentes, no un absoluto. | La regla R-1 mide otra cosa (operaciones de dominio dentro de la vista), con lista congelada. |
| Índice «solo de orden» sin número (D-DAT-01) | Octubre §8.1: sin EXPLAIN baja a INFO. | Queda BAJA condicionada al EXPLAIN de la pasada 2; sin número, INFO. |
| Deduplicar «entregas idénticas en menos de 1 minuto» | Octubre A3-23: rechaza entregas legítimas del mismo día. | No aplica a Dispositivos; no se propone. |
| `D1-LIM-15` · «La guardia de Emergencia no reimplementa el detalle del dispositivo» | Verificado por el revisor de calidad de D1: la guardia usa `ocupacion.estado_de_plazas` y el mixin de alcance; lo que se duplica es el gate (D-LIM-32) y el parseo de ids (D-LIM-33). | Nada; sin ficha propia. |
| API de campo con N+1 o sin idempotencia (D4 perf) | Revisado sin hallazgo: la lista trae edificio y diseño con `select_related`, el detalle hace prefetch de fotos y la idempotencia por UUID usa `q_uuid_en_texto` contra columnas `char(36)`. | Nada. |

### D1 · corrección y seguridad

- **Alcance por vista.** Las vistas que reciben `pk` resuelven el alcance antes de leer nada:
  `DispositivoObjectPermissionMixin.get_object` (`mixins_dispositivos.py:110-116`) o
  `dispositivo_operable_o_404` (`:41-50`). Los hijos (estadía, plaza, sector, edificio) se filtran
  siempre por el dispositivo ya autorizado (`dispositivos_legajo.py:650, 980, 998, 1178-1185, 1384, 1503-1512`).
  Ajeno e inexistente dan el mismo 404. No hay IDOR por pk.
- **Alcance «territorial».** Dispositivos no tiene alcance territorial: el alcance fino es la
  membresía vigente del Equipo (`services/dispositivos.py:219-256`), y el alcance total sale de
  `programa.configurar` sobre DISPOSITIVOS (`:71-75`). `rbac.puede` empareja capacidad y programa del
  mismo rol (`core/rbac.py:_capacidades_activas_en_programa`), así que un rol de otro programa no
  concede nada. `dispositivo.ver_todos` amplía solo `dispositivo.ver` y `edificio.ver` (`:233-236`).
  El bug de precedencia de `CAPS_ADMIN_PROGRAMA` no aplica: este módulo no lo usa.
- **`DispositivoFormularioTipoView`** (`:362-403`): con `dispositivo`, el alcance es
  `dispositivos_en_alcance(editar)`; sin él, crear + alcance de admin. Bien.
- **XSS.** Los templates del legajo no tienen `|safe` ni `x-html`. El `x-data` interpola
  `persona_visible` con `escapejs` (`detail.html:20`). Los duplicados se dibujan con `textContent`
  (`form.html:424`).
- **Nombre y DNI de la persona alojada** en la solapa Estadías y en el historial se condicionan a
  `ciudadano.ver` (`dispositivos_legajo.py:447-457`, `detail.html:259-261`, `auditoria_dispositivo.py:209`).
  El id del ciudadano se saca de la traza `PLAZA_RESERVADA` (`:102, 186-188`).

### D1 · rendimiento

- `programas/services/detalle_dispositivo.py`
  - `indicadores_de_plazas` y `sectores_del_censo` (`:105-156`): salen del `Censo` de `ocupacion_de_plazas`
    (`programas/services/ocupacion.py:372-448`): 3 consultas agregadas por sector con `values().annotate()`,
    servidas por `Sector(dispositivo, activo)`, `Plaza(sector, estado)` y `Estadia(plaza, estado)`. No hay
    cálculo por plaza ni por sector en Python más allá de sumar conteos ya agregados.
  - `contar_alojadas` (`:159-162`): `COUNT` cubierto por `Estadia(dispositivo, estado)`.
  - `estadias_del_dispositivo` (`:205-242`): paginada de a 25, `select_related` + `only` de lo que dibuja la
    tabla; lo que leen `detail.html:254-340` y la vista (`dispositivos_legajo.py:446-469`;
    `ciudadano.apellido_nombre` usa solo `apellido` y `nombre`, cargados) no dispara cargas diferidas. El filtro
    «Todas» hace filesort sobre las estadías del dispositivo (≈100; miles en el peor caso): no amerita índice.
  - `infraestructura_del_dispositivo` (`:654-893`) y `registro_de_relevamientos` (`:607-651`): costo fijo,
    relevamientos paginados de a 10, fotos de la página en una consulta, grilla con tope de 60. El volumen de
    edificios e inspecciones es chico (unidades por dispositivo).
  - `alertas_del_dispositivo`: salvo D-PERF-05, cada regla es 1 o 2 consultas por índice;
    `plazas_fuera_de_servicio` ya agrega con tope.
  - Sin `Trunc*`, `__date` ni `CONVERT_TZ` en todo el alcance: las fechas se formatean en Python con
    `timezone.localtime` (`_fecha_legible`, `_fecha`, `_cuando`).
- `programas/selectors/auditoria_dispositivo.py`: aparte de D-PERF-01 y D-DAT-01, las cuatro lecturas tienen
  `select_related` de todo lo que leen los `evento_de_*` (incluidos `traza.inspeccion.criticidad`, `estado` y
  `asignado_a_id`, que viajan con `inspeccion__edificio`); `TrazaDispositivo.estado_*_legible` no consulta.
- `programas/views/dispositivos_legajo.py`: `DispositivoDetailView` (consultas fijas presupuestadas; los modales
  solo con su parámetro abierto), `EstadiaDetalleView` (movimientos y novedades paginados) y las acciones de
  estado (`_transicionar` bloquea por pk, sin función sobre columna en el `select_for_update`).
- `programas/services/dispositivos.py`: `puede_operar_dispositivo` se llama unas 7 veces por detalle, pero es un
  `exists()` por pk (o nada, para admin y `ver_todos`): constante. `buscar_posibles_duplicados` usa `iexact`
  (`LIKE` sin comodín inicial sobre `codigo` único) sobre 200 filas.
- `programas/mixins_dispositivos.py`: solo permisos; un `get_object_or_404` por pk.
- Templates `programas/templates/programas/dispositivos/legajo/**`: ningún `|length` sobre querysets (el único,
  `_infra_listado.html:35`, es sobre una lista ya recortada a 60), ningún acceso a relaciones en loops que no
  venga precargado, ningún contador calculado en el template.
- Listado (`DispositivoListView`, `dispositivos_legajo.py:166-231`): mirado solo para no duplicar. Paginado de a
  25, semáforo y censo por página en consultas fijas, `icontains` sobre 200 filas. Su auditoría va en D2.

### D1 · calidad

- **¿La guardia de Emergencia reusa `detalle_dispositivo` o lo reimplementa?** No lo reimplementa. La guardia
  (`views/emergencia_dispositivo.py`) no muestra alertas, indicadores ni historial del dispositivo: solo su nombre
  y el mapa de camas. Ese mapa sale de `selectors/emergencia_alojar.py:plazas_para_caso`, que llama a
  `ocupacion.estado_de_plazas`, la misma fuente que el censo del detalle. El alcance pasa por
  `mixins_dispositivos.dispositivo_operable_o_404`. Lo que sí se duplica es el **gate** (D-LIM-32) y el parseo de
  ids (D-LIM-33). Las reglas de dominio que la guardia escribe en la vista ya están en E-LIM-01.
- **Regla de 1000 líneas:** `views/dispositivos_legajo.py` (1659) la pasa: es D-LIM-25. `services/detalle_dispositivo.py`
  (893) pasa de 700 y junta dos dominios: D-LIM-24. `templates/.../legajo/detail.html` (705) pasa de 700, pero lo que
  sobra es el modal de egreso copiado (D-FE-01).
- **Ya registrados, no se repiten:** `CAP_ADMITIR` redeclarado (también `services/estadias.py:121`, del que importa
  la vista): E-LIM-27. `TONOS`/`ICONOS` de `alertas_dispositivos.py:74-75`, que `detalle_dispositivo.py:40,275-276`
  consume: E-LIM-29. Las reglas que `GuardiaView` y sus hijas reescriben en la vista: E-LIM-01. Los helpers
  `nombre_de`/`fecha_hora` de Emergencia: E-LIM-25. D-LIM-36 es el mismo patrón dentro de Dispositivos.

### D2 · rendimiento

- **Ocupación por dispositivo y por sector** (`ocupacion.py:372-448`): son tres consultas fijas que no leen el histórico. Las plazas se agregan con un LEFT JOIN acotado por `(dispositivo, activo)` y la FK de plaza. Las estadías activas van por `(plaza, estado)` con `estado='ACTIVA'`. Las reservas vigentes, por `(plaza, estado)` con `estado='VIGENTE'`, más un `NOT EXISTS` correlacionado por `plaza_id`. No hay cálculo en Python sobre todas las plazas ni N+1. Lo usan el listado de instituciones (`dispositivos_legajo.py:226`, solo los ids de la página), P5, el paso 2 del ingreso y Emergencia. El conteo crece con plazas y sectores, nunca con estadías ni movimientos.
- **`estado_de_plazas`** (`ocupacion.py:499-559`): dos consultas con `plaza_id IN (...)` sobre las plazas que se dibujan (las acota la capacidad), con los nombres en la misma consulta.
- **Censo** (`censo.py`): no tiene `Trunc*` ni `__date`. Los ingresos y egresos van por el índice `(dispositivo, momento)`. El reparto en Python es O(estadías del día × tramos), con un rango de un solo día en el único consumidor (`bitacora_pantalla.py:372`). Lo único que crece es la lectura de D-PERF-02.
- **Trayectoria** (`selectors/trayectoria.py`): la premisa «todas sus estadías sin índice» queda **refutada**. Usa el índice `(ciudadano, estado)` (`models/__init__.py:1278`), pagina de a 10 con COUNT, hace `select_related` de dispositivo, tipo, plaza, sector y motivo, y anota el alcance con `EXISTS`. `resumen_de_estadias` es un solo `aggregate` por el mismo índice.
- **Detalle de la estadía** (`selectors/estadia_detalle.py`): los movimientos van por `(estadia, momento)` con `select_related` de responsable, plazas y sectores (`movimientos.py:129` + `estadia_detalle.py:331`). Los turnos se leen una vez. Las otras estadías van por el índice de ciudadano, tope 5. Las novedades están paginadas. La tabla «Movimientos» pagina en Python una lista acotada por las operaciones de una estadía.
- **Capacidad** (`selectors/capacidad_dispositivo.py`, `views/dispositivos_capacidad.py`): son agregados de una consulta acotados por la capacidad instalada, con un POST por acción y cantidad constante de consultas. `codigos_del_sector` y `plazas_tomadas_del_sector` leen un solo sector.
- **«Sectores y plazas»** (`sectores_plazas.py`): consultas fijas. El tope de 200 por sector se aplica en Python sobre las plazas cargadas, que acota la capacidad y no la historia. Los inactivos solo se leen con `?inactivos=1`.
- **Ingreso, locks y transacciones** (`estadias.py`, `ingreso.py`, `views/dispositivos_ingreso.py`): la plaza se bloquea por pk sin JOIN, la persona por pk, `verificar_alojamiento_en_red` busca por el UNIQUE `clave_alojamiento` y `_exigir_intervalo_sin_alojamiento` usa el índice de ciudadano. `confirmar_ingreso` bloquea las plazas `order_by("pk")`. RENAPER se consulta en el paso 1, fuera de toda transacción (no hay `ATOMIC_REQUESTS`). Fuera de la configuración (D-ERR-01) no hay `select_for_update` sobre dispositivo ni sector en el camino del ingreso. `guardar_respuestas_ingreso` escribe archivos dentro de la transacción con la plaza tomada: es una sola plaza, así que no serializa a otros operadores.
- **REGEXP de `buscar_ciudadano_por_dni`:** ya registrado como E-PERF-01 / E-PERF-01. Sus consumidores en esta tajada son `ingreso.py:355` y `:366` (`_crear_legajo`, dentro del atomic de `confirmar_ingreso` pero **antes** de cualquier `FOR UPDATE`) y `views/dispositivos_ingreso.py:398` y `:437`. No aparece ningún consumidor nuevo que tome locks.
- **Templates** `estadia/**`, `ingreso/**` y `sectores/**`: no recorren querysets ni usan `|length` sobre querysets sin límite. Solo leen relaciones ya traídas (`resumen.plaza.sector` con `select_related`, `dispositivos_ingreso.py:658`).
- **Ya registrados, no repetidos:** E-PERF-09 (dos aceptaciones eligen las mismas camas), E-PERF-10 (N+1 acotado al reservar camas, `estadias.py:294-299`) y E-LIM-37 (la regla de cama libre en Python y en SQL).

### D3 · rendimiento

- **Pantalla del turno** (`services/bitacora_pantalla.py`, `views/dispositivos_bitacora.py`): costo constante en el volumen de la bitácora. Las lecturas de entradas van por `(dispositivo, fecha_operativa, turno)`, el índice de `EntradaBitacora` (`models/__init__.py:1949-1952`); `vigentes()` es un `LEFT JOIN` contra el `UNIQUE` de `version_anterior`; la página tiene tope (`TOPE_ENTRADAS + 1`, `COUNT` solo si se pasa); personas y adjuntos van por `Prefetch`, y el `only("id", "ciudadano_id")` sobre la M2M no abre el N+1 de la trampa 2 (el prefetch de una M2M empareja por la columna de la tabla intermedia). Las corregibles con `only(...)` leen solo campos cargados. Sin `Trunc*` ni `__date`: la fecha operativa se guarda en un `DateField`.
- **Detalle de la novedad** (`services/bitacora_detalle.py`): `versiones()` es `pk = raíz OR entrada_original_id = raíz`, los dos indexados; tres consultas fijas.
- **Doble envío** (`bitacora.py:429-445`): el filtro arranca por el prefijo del índice `(dispositivo, fecha_operativa, turno)`; el resto se evalúa sobre las filas de un turno-día.
- **Novedades automáticas** (`anotar_en_bitacora`, `anotar_novedad_automatica`): una consulta de turnos activos (`Turno` por `dispositivo`, cubierto por el `UNIQUE (dispositivo, nombre)`), sin lecturas por fila.
- **Turnos** (`crear_turno`, `editar_turno`): dispositivo X y después `Turno`; nadie toma un turno antes que el dispositivo.
- **Equipo** (`services/equipo_dispositivo.py`, `views/dispositivos_equipo.py`): las escrituras toman dispositivo → miembro; ninguna toca estadías ni plazas, así que no cruzan el orden de D-ERR-01. `equipo_del_dispositivo` es una consulta con `Exists` sobre el `UNIQUE (user_id, group_id)` de `auth_user_groups`. `crear_persona_y_sumar` crea el usuario antes de bloquear el dispositivo y el correo sale fuera de la transacción.
- **Sugerencias** (`selectors/agentes_sugeridos.py`, `equipo_sugeridas.py`, `personas_sugeridas.py`): `istartswith` (nunca `LIKE BINARY`), mínimo 3 caracteres y tope 10+1; `personas_sugeridas` parte el `OR` en dos consultas por columna, con medición citada.
- **Buscador y alta de agentes** (`buscador_agentes.py`, `agentes.py`, `sumar_agente.py`): tope `TOPE_RESULTADOS + 1`, asignables y personal con `IN` sobre los ids de la página. La búsqueda por correo (`email__iexact`) recorre `auth_user`, que Django no indexa: miles de filas, no se reporta sin medición. El alta de agente deja `agentes_asignables` fuera de la transacción.
- **Formularios por tipo** (`services/formularios_tipo.py`, `respuestas_dispositivo.py`, `selectors/formularios_tipo.py`, `views/dispositivos_formularios.py`, `dispositivos_config.py`): a lo sumo 8 formularios por tipo; `anotar_tiene_respuestas` usa `Exists` por FK indexada (el de `InspeccionEdificio.diseno`, anulable, toca la trampa 1 solo en teoría: 8 filas externas en una pantalla de configuración). `_guardar_respuestas` bloquea por `(dispositivo|estadia, diseno)`, el `UNIQUE` compuesto de cada modelo, en `READ COMMITTED`: sin gap locks. `formularios_de_los_tipos` hace una consulta por tipo del edificio (1–3). El editor delega en `programas.services.constructor` (fuera de la tajada).
- **Alertas** (`services/alertas_dispositivos.py`): consultas fijas por regla, solo desde el detalle de un dispositivo; `ReservaPlaza` tiene `Index(plaza, estado)`; sin `Trunc*`.
- **Horarios** (`services/horarios_dispositivo.py`): una lectura y, si cambió, `DELETE` + `bulk_create` dentro del candado del legajo.
- **Formularios Django** (`forms_bitacora.py`, `forms_dispositivos.py`): los `clean_*` hacen una consulta por pk; los selects de turnos y correcciones se arman con lo que la vista ya leyó.
- **Templates** `bitacora/**` y `config/**`: recorren listas ya armadas; el único `|length` es sobre una lista (`formularios`); `estado_tipo_dispositivo` no consulta.
- **Ya registrados, no repetidos:** D-PERF-07, D-ERR-01, D-PERF-02 y el REGEXP de `buscar_ciudadano_por_dni`.

### D4 · rendimiento

- **API de campo** (`api/views_inspecciones.py`, `api/serializers_inspecciones.py`): sin N+1. La lista trae edificio
  (`inspecciones_asignadas`) y diseno con select_related; `vencida` es propiedad y `formulario_version` no consulta.
  El detalle hace prefetch de fotos; `foto_vigente` es una lectura por objeto, no por fila. Sin paginación, acotado a
  lo que el agente tiene en curso.
- **Idempotencia por UUID** (`_admitir_carga`, `services/inspecciones.py:654-659`): `q_uuid_en_texto` compara igualdad
  contra las dos formas sin función sobre la columna; `uuid_cliente` es unique y está en char(36) (0093 y 0108). El
  predicado dentro del select_for_update usa índice.
- **Bloqueos** (`crear_inspeccion`, `reasignar_inspeccion`, `cancelar_inspeccion`, `marcar_revisado`,
  `desvincular_edificio`): bloquean por pk; las lecturas dentro del lock van por índice y sin llamadas externas.
- **Semáforo y última realizada** (`subconsulta_ultima_realizada`, `ultimas_inspecciones_por_edificio`,
  `semaforos_de_dispositivos`, `tiene_relevamiento_vencido`): consultas fijas por lote, servidas por
  Index(edificio, estado, realizada_en); la subconsulta escalar con LIMIT 1 en el SELECT evita el LIMIT dentro de IN.
- **Vencimiento de relevamientos:** no hay cron; «vencido» se deriva de `fecha_vencimiento` en cada lectura
  (`selectors/vencimiento_inspecciones.py`). Nada recorre la tabla de noche.
- **TruncDate / CONVERT_TZ / JSON:** ninguno en el alcance. Las fechas se formatean en Python (localtime, date_format);
  las respuestas del formulario se validan en Python sobre el dict de la app; no hay filtros por camino JSON.
- **Templates** de `edificios/` y `relevamientos/`: sin consultas en el template; la galería dibuja 24 con
  loading=lazy y pliega el resto.
- **Export** (`views/reportes.py` → `padron_dispositivos`): en memoria pero acotado al padrón de instituciones (cientos),
  con select_related del tipo; xlsx en write_only.
- **Ficha del edificio** (`ficha_de_edificio`): costo fijo, sectores con un Count filtrado, registro paginado (el
  registro vive en `services/detalle_dispositivo.py`, fuera de esta tajada).
- **D4-DAT:** sin hallazgos. Índices y FK de Edificio, InspeccionEdificio, FotoInspeccion, TrazaInspeccion y
  AdjuntoRespuestaRelevamiento cubren los caminos de lectura por lote; UUID ampliados a char(36).

## 6. Línea de base

Medida por lectura y, para las fichas PERF/DAT, en el banco MariaDB 10.11 del PR #1220 (sección 8.d); `perf_audit.py` no corrió.

- **Regla de 1.000 líneas:** la pasan `views/dispositivos_legajo.py` (1659 líneas, D-LIM-25), `services/estadias.py` (D-LIM-20) y `services/inspecciones.py` (D-LIM-30). Pasan de 700 o se acercan: `services/detalle_dispositivo.py` (893, D-LIM-24), `forms_dispositivos.py` (861, D-LIM-46), `views/dispositivos_ingreso.py` (801, D-LIM-39) y `templates/.../legajo/detail.html` (705). La función `pantalla_bitacora` tiene 318 líneas (D-LIM-27).
- **Sin N+1 en la API de campo** (`api/views_inspecciones.py`, `api/serializers_inspecciones.py`), el detalle de edificio ni el informe de relevamiento: lo confirmó el revisor de rendimiento de D4 leyendo el código.
- **`TruncDate`, `CONVERT_TZ` y filtros por camino JSON:** ninguno en el alcance de D4 (las fechas se formatean en Python); las demás tajadas no registran ninguno.
- **Volumen supuesto por los revisores** (el banco no lo tiene): 200 dispositivos, 10.000 plazas, 20.000 estadías, 100.000 movimientos, 200.000 registros de auditoría y bitácora, 100.000 ciudadanos; un centro grande de 300 a 500 plazas; 18 a 128 instituciones y, para el estrés, 5.000 edificios y 50.000 inspecciones (D4).
- **Presupuestos de consultas:** `DispositivoDetailView` tiene consultas fijas presupuestadas en SQLite (D1 perf); las fichas proponen sumar los del historial profundo, el censo, el alta y los edificios. La pasada 2 los lleva a `scripts/perf_budgets.json` (regla R-12).

## 7. Decisiones del cliente

Cada una lleva una propuesta por defecto aplicable: si no hay respuesta a tiempo, se implementa el default.

| Ficha | Decisión | Default propuesto |
|---|---|---|
| D-SEG-02 | ¿Qué ve de un texto libre sobre una persona quien no tiene permiso para verla? | Nada que no pueda ver de la persona. |
| D-ERR-02 | ¿Un dispositivo cerrado admite cambios operativos de plaza y reservas, y se puede cerrar con personas alojadas o reservas? | No a las dos: los mutadores rechazan por `CERRADO` y cerrar exige egresar y liberar antes. |
| D-ERR-02 (guarda) | ¿Los mutadores rechazan solo `CERRADO` o todo lo que no sea `ACTIVO`? (resolución 2 de la sección 1) | Solo `CERRADO` en todo mutador; «no ACTIVO» queda solo donde ya se exige (bitácora, reservas), con una única `dispositivo_operable(d)`. |
| D-ERR-03 | ¿Tope de días hacia atrás para el ingreso retroactivo? | Sin tope; solo la cota de existencia (no antes de crear la plaza ni el dispositivo). |
| D-SEG-05 | ¿La redacción por alcance de datos de otro dispositivo se aplica en todos los puntos de lectura? | Sí. |
| D-PERF-01 | Historial profundo: ¿límite de páginas o cursor? | Tope de 50 páginas (1.000 eventos) y mensaje «Hay más eventos: pedí el export»; el cursor por fuente queda como opción. |
| D-PERF-05 | Alertas de reservas y préstamos vencidos: ¿una por cada una o agrupadas? | Agrupar desde 3 vencidas, con el mismo tope y enlace que `plazas_fuera_de_servicio`. |
| D-ERR-04 | ¿La app puede subir fotos y adjuntos después de «Revisado»? | Sí, solo del agente que cerró el relevamiento, con una traza propia «llegó después de la revisión»; para cualquier otro sigue el 409. |
| D-SEG-06 | ¿Qué límite de cargas tiene la API de campo? | Por usuario y por objeto padre; nunca por IP. |
| D-SEG-07 | ¿Qué regla de separación entre agente e institución se valida y cuándo? | En todas las operaciones que la pueden romper. |
| D-LIM-38 | ¿Las alertas aceptan el formato canónico de nombre de plaza? | Sí (`plaza_con_sector`); si no, el helper recibe un parámetro. |
| D-LIM-36 | Si las cuatro listas de extensiones de imagen difieren, ¿cuál rige? | Conservar cada una con nombre propio; solo se unifican si ya coinciden. |
| D-FE-03 | ¿Unificar el criterio de recorte de espacios entre el formulario del tipo y el link público de Becas? | No en esta ola: se conserva cada conducta como opción explícita. |
| D-LIM-07 | ¿Qué regla rige para administrar usuarios de Dispositivos? | La del ABM de Usuarios. |
| D-LIM-50 | La API de campo duplica `fotos` y `adjuntos` y arma su propio 400 legible (contrato con Chaco-mobile). | No tocar el cuerpo; solo juntar el código. |
| D-LIM-08 | Alta de dispositivo: ¿se mantiene el buscador múltiple de responsables? | Sí, alimentado por sugerencias del servidor y con tope. |

## 8. Pasada 2 · qué medir y qué reproducir

### 8.0 Resultado de las PoC (ya ejecutadas por el juez)

| Ficha | Resultado | Severidad | Evidencia |
|---|---|---|---|
| D-ERR-01 (candados) | CONFIRMA | MEDIA, primera ola de concurrencia (no Ola 0) | PoC reproducida; test en el PR que la arregla: ERROR 1213 reproducido en MariaDB 10.11 con 2 hilos en los dos caminos (`ingresar_persona` contra `editar_plaza`; `corregir_entrada` contra `registrar_entrada`). Ninguna capa traduce el 1213 a otra cosa que un 500; InnoDB elige la víctima; el rollback no deja datos inconsistentes. **Para correrla hace falta `DJANGO_SYNCDB_PROJECT_APPS=False`** (con `True` el syncdb falla en MariaDB con el error 1005 por la FK de `users_profile`). |
| D-SEG-01 (roles propios) | CONFIRMA | MEDIA, Ola 0 | PoC reproducida; test en el PR que la arregla. Detalle técnico reservado hasta el arreglo. |

### 8.a Fichas PERF/DAT a medir en el banco

> **Estado: medido el 19-nov-2026** en el banco del PR #1220 (resultados en la sección 8.d). La tabla de abajo es el plan original; el resultado de cada ficha está en su línea «Medición en banco».

MariaDB 10.11, `read_timeout` 10 s, **sin** `DB_READ_TIMEOUT` propio (con los 10 s de producción). Sin número, una PERF ALTA baja a INFO. Resultado: D-PERF-01 pasó los 10 s (ALTA, corta), D-DAT-01 pasó 1 s (ALTA) y D-PERF-03 pasó 200 ms (MEDIA).

| Ficha | Sev. | Qué se mide (medición propuesta por el auditor) |
|---|---|---|
| D-PERF-01 · El historial del detalle lee y arma en Python toda la auditoría anter… | MEDIA | banco `scripts/perf_mysql/` (MariaDB 10.11, OPTIONS de producción) con la siembra de abajo: `python perfil_ruta.py "/dispositivos/<pk_grande>/?tab=historial&historial_page=1"` contra `...&historial_page=99999`; hoy la segunda escala con la historia, después las dos quedan iguales. |
| D-PERF-02 · El censo del día lee el histórico entero de estadías del dispositivo | MEDIA | en el banco `scripts/perf_mysql/` (MariaDB 10.11), con la siembra de abajo, correr `EXPLAIN ANALYZE` (o `ANALYZE FORMAT=JSON` en MariaDB) de la consulta. Antes: `key` = el índice de `dispositivo`, `rows` ≈ 20.000 y `r_rows` ≈ 20.000. Después: `type=range` sobre el índice nuevo y `rows` ≈ 400. Además, `perfil_ruta.py` sobre `/dispositivos/<pk>/bitacora/` antes y después. |
| D-LIM-08 · La consulta «pares usuario×rol sumables» está escrita tres veces y el… | MEDIA | en el banco, sembrar 1.000 usuarios con roles de Dispositivos y medir con `perfil_ruta.py` el `GET` del alta: tiempo de render y bytes. Se reporta solo si pasa de ~500 ms o ~1 MB. |
| D-PERF-03 · `/media/` busca el adjunto de la bitácora y de los formularios del di… | BAJA | en el banco MariaDB (3310), sembrar 50.000 `AdjuntoBitacora` y 200.000 `AdjuntoRespuestaRelevamiento`, y `ANALYZE FORMAT=JSON SELECT … FROM programas_adjuntobitacora WHERE archivo = '…'` antes (`ALL`, `rows` ≈ tabla) y después (`ref`, `rows` = 1). Medir además `perfil_ruta.py` sobre `/media/<ruta de un adjunto de relevamiento>` para ver los dos scans encadenados de `:299` y `:304`. |
| D-PERF-04 · P21 recorre el histórico entero de relevamientos unas 8 veces por car… | BAJA | banco MariaDB (3310) con 5.000 edificios y 50.000 inspecciones: EXPLAIN de la página «Completados» y del aggregate antes y después (type, rows, Using filesort) y tiempo total de P21 con `perfil_ruta.py`, para un coordinador no admin y para el admin. Si queda debajo de 100 ms a ese volumen, la ficha baja a INFO. |
| D-PERF-05 · Las alertas de reservas y préstamos vencidos no tienen tope: una por… | BAJA | sembrar 200 `ReservaPlaza` `VIGENTE` con `hasta` en el pasado sobre un dispositivo y abrir `/dispositivos/<pk>/`: hoy 200 bloques `role="status"`; después, uno. |
| D-DAT-01 · Las trazas y la bitácora del historial no tienen índice que sirva al… | BAJA | en el banco, con la siembra de abajo, `EXPLAIN` de las dos consultas (el SQL sale de `str(FeedAuditoria(d).fuentes[i][1][:20].query)`): hoy se espera `key` = índice de la FK, `rows` ≈ trazas del dispositivo, `Extra: Using where; Using filesort`; después `key` = índice nuevo, sin filesort en la traza y `Using index` en el `COUNT` de correcciones. Medir también `perfil_ruta.py "/dispositivos/<pk_grande>/"` (página 1, la de todos los días). |
| D-PERF-06 · `plaza_ocupada_despues_de` recorre todas las salidas históricas de la… | INFO | `EXPLAIN ANALYZE` en el banco con una plaza de 2.000 salidas sembradas y `momento` posterior a todas: `rows` antes ≈ 2.000, después ≈ 0. |
| D-PERF-07 · La fila del dispositivo serializa la operación: cada novedad de bitác… | INFO | con dos sesiones. S1 simula `registrar_entrada` con `SELECT id FROM programas_dispositivo WHERE id=D FOR UPDATE` y no cierra. S2 hace un `INSERT` en `programas_trazadispositivo` (o un ingreso real por la vista) con `dispositivo_id=D` y queda esperando hasta el `COMMIT` de S1. Ver `information_schema.INNODB_LOCK_WAITS`. |
| D-PERF-08 · El listado de Edificios calcula tres subconsultas y un GROUP BY sobre… | INFO | banco MariaDB (3310) con 5.000 edificios y 50.000 inspecciones: tiempo de la página 1 y de una profunda, sin filtro y con estado; EXPLAIN ANALYZE solo en el banco. Debajo de 100 ms, se descarta. |
| D-PERF-09 · El detalle arma el mapa completo de plazas solo para saber si hay alg… | INFO | `perfil_ruta.py "/dispositivos/<pk_grande>/"` con un dispositivo de 500 plazas y 300 estadías activas, comparando el tiempo propio de `plazas_para_ingresar` en el perfil contra el total de la vista. Si es menos del 5 % del request, se cierra sin cambio. |
| D-PERF-10 · El informe de un relevamiento repite consultas de costo fijo (COUNT d… | INFO | el test de presupuesto baja dos consultas. |

Volumen que pide cada ficha (se siembra una vez, ver 8.c):

| Ficha | Volumen y medición |
|---|---|
| D-PERF-01 | Dispositivo grande de 500 plazas con unas 20.000 trazas y 10.000 entradas de bitácora; `perfil_ruta.py` sobre `/dispositivos/<pk_grande>/` (página 1) y sobre `?tab=historial&historial_page=99999`; `EXPLAIN` de las dos consultas del historial antes y después del índice. |
| D-DAT-01 | Las mismas tablas; `EXPLAIN` de la «última traza» y del orden del historial, antes y después del índice. Sin número, INFO. |
| D-PERF-05 | 200 `ReservaPlaza` `VIGENTE` con `hasta` vencido en un dispositivo. |
| D-PERF-02 | Dispositivo grande con 3 turnos, 10 sectores y 500 plazas; **20.000 `Estadia` en total**: 500 activas en el grande (una por plaza, cada una con `clave_alojamiento`), unas 19.000 egresadas en el grande en 3 años y el resto repartido entre los dispositivos chicos; 100.000 ciudadanos. `EXPLAIN ANALYZE` / `ANALYZE FORMAT=JSON` del censo y `perfil_ruta.py` sobre `/dispositivos/<pk>/bitacora/`. |
| D-PERF-06 | 100.000 `MovimientoEstadia` y una plaza «caliente» con **2.000 salidas** (`plaza_origen`). Dos sesiones de `mysql`. |
| D-PERF-07 | Dos sesiones de `mysql`, sin volumen: cada novedad de bitácora toma el dispositivo con X y cada ingreso, con S. |
| D-PERF-03 | **50.000** `AdjuntoBitacora`, **20.000** `AdjuntoRespuestaAlta` y **200.000** `AdjuntoRespuestaRelevamiento`; `ANALYZE FORMAT=JSON` de las consultas por `archivo` de `core/views/media.py:227, 299, 304, 322`. |
| D-LIM-08 | **1.000 usuarios** con roles de Dispositivos y `perfil_ruta.py` sobre el alta (tiempo y bytes). |
| D-PERF-04 | **5.000 edificios y 50.000 inspecciones** (1 a 4 por edificio y año, sin purga) y 18 a 128 instituciones; P21 con las ocho pasadas por carga. |
| D-PERF-08 | Los mismos 5.000 edificios; el listado con las tres subconsultas y el `GROUP BY` antes de recortar la página. |
| D-PERF-10 | Un relevamiento con fotos y adjuntos: las consultas de costo fijo del informe (COUNT de fotos, alcance del coordinador). |

### 8.b Fichas ERR/SEG que necesitan PoC

Obligatorias (ALTA de corrección o seguridad): **ninguna ficha ERR/SEG es ALTA**. Las dos con PoC pedida están **ya ejecutadas y CONFIRMADAS** (8.0):

- **D-ERR-01** [MEDIA · CONFIRMADO con test] Configurar capacidad toma dispositivo→plaza y el ingreso toma plaza→dispositivo: deadlock 1213
- **D-SEG-01** [MEDIA · CONFIRMADO con test] Un atajo permite otorgarse un rol propio

Recomendadas (ERR/SEG con estado PLAUSIBLE, o con daño de datos si se confirma):

- **D-ERR-04** [MEDIA · PLAUSIBLE] Una foto o un adjunto que llega después de «Revisado» se rechaza para siempre y la evidencia se pierde
- **D-ERR-05** [BAJA · PLAUSIBLE] La edición del legajo responde 500 si dos personas guardan el mismo código a la vez
- **D-ERR-06** [BAJA · PLAUSIBLE] Borrar un grupo del formulario por tipo puede arrastrar en cascada un campo que se movió a ese grupo al mismo tiempo (TOCTOU)
- **D-ERR-09** [BAJA · PLAUSIBLE] Los servicios no validan que el tipo de plaza sea admitido por el tipo de dispositivo
- **D-ERR-11** [BAJA · PLAUSIBLE] Con la sesión vencida, el formulario del tipo se reemplaza por la pantalla de login
- **D-ERR-13** [INFO · PLAUSIBLE] `nodo-formulario-tipo.js` vuelve a habilitar controles que el servidor renderizó deshabilitados

Las ALTA del capítulo son de calidad (D-LIM-01, D-LIM-02, D-LIM-03) y se verifican con el test de regresión de la propia ficha (con mutación). Las ERR/SEG ya CONFIRMADAS por lectura llevan su test en «Tests a agregar».

### 8.c Qué le falta sembrar al banco (`scripts/perf_mysql/`)

Hoy el banco **no siembra Dispositivos**: ni `bench_mysql.py` ni los escenarios tienen rutas de `/dispositivos/`, y `seed_perf` no crea ni un dispositivo. **No** tocar `seed_perf` (lo usa el CI de performance): todo va en un único `scripts/perf_mysql/escenarios_dispositivos.py` con el volumen de la tabla de abajo. Las siembras se hacen una vez sobre la misma base de 100.000 ciudadanos (sección 8 de Emergencia comparte la base: coordinar los dos scripts).

| Siembra | Qué crear | Fichas |
|---|---|---|
| Dispositivos, sectores y plazas | 200 `Dispositivo` de un tipo con plazas (199 chicos de ≈ 50 plazas y 1 grande de **500 plazas, 10 sectores y 3 turnos**), ≈ 2 sectores por dispositivo y 10.000 `Plaza` repartidas; `Turno` en el grande. | D-PERF-01, D-PERF-02, D-PERF-06 |
| Estadías y movimientos | 20.000 `Estadia` en total: 500 activas en el grande (una por plaza) y unas 19.000 egresadas en el grande, repartidas en 3 años, y el resto en los dispositivos chicos, con `clave_alojamiento` `CIU-<id>`; 100.000 `MovimientoEstadia` (ingreso, egreso y algún cambio de plaza) con `dispositivo_id` y `momento` coherentes; una plaza «caliente» con 2.000 salidas. | D-ERR-01, D-PERF-02, D-PERF-06 |
| Ciudadanos | Los 100.000 de `seed_perf` como personas de las estadías. | D-PERF-01, D-PERF-02 |
| Auditoría y bitácora | 200.000 registros entre `TrazaDispositivo` (con unas 2.000 `EDITADO` con detalle JSON en el grande) y `EntradaBitacora` (unas 60.000 novedades, 3.000 con `version > 1`); en el grande, unas 20.000 trazas y 10.000 entradas. | D-DAT-01, D-PERF-01 |
| Reservas | ≈ 200 `ReservaPlaza` `VIGENTE` con `hasta` vencido sin liberar en un dispositivo. | D-PERF-05 |
| Adjuntos para `/media/` | 50.000 `AdjuntoBitacora`, 20.000 `AdjuntoRespuestaAlta` y 200.000 `AdjuntoRespuestaRelevamiento` con rutas distintas; `GET /media/` de cada tipo con el archivo del medio y con el último. | D-PERF-03 |
| Usuarios del alta | 1.000 usuarios con roles de Dispositivos (y los pares persona × rol del programa). | D-LIM-08 |
| Edificios e inspecciones | 5.000 `Edificio` vinculados a 18 a 128 instituciones, 50.000 `InspeccionEdificio` (1 a 4 por edificio y año, con fotos y `TrazaInspeccion`), con alcance de coordinador y de agente asignado para P21. | D-PERF-04, D-PERF-08, D-PERF-10 |
| Concurrencia (dos sesiones o dos hilos) | Los dos caminos de la PoC (PoC reproducida; test en el PR que la arregla) con `DJANGO_SYNCDB_PROJECT_APPS=False`; dos sesiones de `mysql` sobre `ingresar_persona`/`editar_plaza`, `corregir_entrada`/`registrar_entrada` y la fila del dispositivo (D2-PERF-03). Sin volumen. | D-ERR-01, D-PERF-07 |

Rutas a sumar a `_extra_targets()` de `bench_mysql.py` y a `scripts/perf_budgets.json`:

- `/dispositivos/<pk_grande>/` (detalle, página 1), `?tab=historial` (con `historial_page=99999`), `/dispositivos/<pk>/bitacora/` y el censo del día.
- `/dispositivos/nuevo/` (alta, con los 1.000 usuarios) y `dispositivos_alta`.
- `GET /media/` de adjuntos de bitácora, de alta y de relevamiento.
- Edificios: listado y ficha; relevamientos P21 (`/dispositivos/relevamientos/`) con un coordinador y con un agente; informe de un relevamiento.
- POST de un solo uso (base restaurable): `ingresar_persona`, `editar_plaza`, `corregir_entrada` y `registrar_entrada`, con dos hilos.

### 8.d Medición en banco

Banco local y sintético (MariaDB 10.11, `read_timeout` 10 s, OPTIONS de producción), sembrado por `scripts/perf_mysql/escenarios_dispositivos.py` (PR #1220). **Volumen:** 200 dispositivos; en la segunda medición, 120.304 estadías y 498.000 movimientos (el grande con 16,8 % de las estadías y 19,9 % de los movimientos), 140.000 trazas, 63.000 entradas de bitácora, 5.000 edificios, 50.000 inspecciones y adjuntos de 50.000 / 20.000 / 200.000. **Método:** frío = primer request; caliente = mediana de 3; `EXPLAIN` y `ANALYZE` sobre las consultas dominantes. Tras sembrar se corrió `ANALYZE TABLE` sobre las tablas grandes. **Ruido:** ±2x entre corridas del equipo. **Alcance:** banco local con datos sintéticos, no ECOM: ordena fichas y muestra el plan, no promete un tiempo en PRD. La segunda medición repartió la historia del dispositivo grande para descartar que D-DAT-01 fuera un artefacto de la siembra: no lo era.

| Ficha | Ruta | Caliente (ms) | Consultas | Severidad |
|---|---|---|---|---|
| D-PERF-01 | `/dispositivos/1/?tab=historial&historial_page=1` / `=99999` | 6.171 / 64.009 | 44 | MEDIA → **ALTA** (corta) |
| D-DAT-01 | `/dispositivos/1/` | 6.141 | 44 | BAJA → **ALTA** |
| D-PERF-02 | `/dispositivos/1/bitacora/` | 245 | 22 | MEDIA |
| D-PERF-03 | `/media/…` de bitácora y de relevamiento | 126 / 155 | 7 / 9 | BAJA → MEDIA |
| D-PERF-04 | `/dispositivos/relevamientos/` (P21) | 610 | 16 | BAJA |
| D-PERF-08 | `/dispositivos/edificios/` | 196-203 | 13-16 | INFO → BAJA |
| D-PERF-09, D-PERF-10 | detalle del grande; informe de relevamiento | 2.429 (ver D-DAT-01) / 49 | 44 / 12 | INFO |
| D-LIM-08 | `/dispositivos/nuevo/` con 1.000 usuarios | 449 | 10 | MEDIA → INFO |
| D-PERF-05, D-PERF-06, D-PERF-07 | alertas; salidas de una plaza; concurrencia | — | — | no medidas por ruta |

Otras rutas medidas, sin ficha: `/dispositivos/1/?tab=estadias` 4.165 ms (la misma consulta del historial), `/dispositivos/` 307 ms, padrón CSV 51 ms y XLSX 87 ms.

## 9. Fichas

Ordenadas por severidad y eje. Los IDs son los finales `D-<EJE>-NN`; el ID de la pasada 1 figura en cada ficha.

### D-LIM-01 · La vista reescribe la regla de privacidad «quién ve al agente asignado» en lugar de usar el helper por lote que existe
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** fusión de D4-LIM-05 + D4-SEG-01 · **Ola:** 0 · **Esfuerzo:** S
- **ID de la pasada 1:** D4-LIM-05 + D4-SEG-01 (**hallado por 2 revisores**)
- **Hallado por 2 revisores (sube de peso):** D4-LIM-05 (calidad: la vista reescribe la regla de privacidad «quién ve al agente asignado» en lugar de usar el helper) y D4-SEG-01: detalle reservado hasta el arreglo. Se arreglan con el mismo helper de alcance de asignación.
- **Parte del patrón «lógica de dominio en vistas»** (regla R-1). Se unifica en `ve_la_asignacion_en_lote(user, relevamientos) -> set[pk]` (contradicción 4 de la sección 1).
- **Ubicación:** `programas/views/dispositivos_relevamientos.py` y `programas/services/inspecciones.py` (helper por lote y regla canónica).
- **Escenario:** la regla de quién ve al agente asignado está reescrita en la vista, y la píldora y la columna no usan el helper del servicio. Si la regla cambia en el servicio, la vista queda con la vieja.
- **Causa raíz:** el helper por lote se agregó para la solapa Infraestructura y la vista de P21 no se migró.
- **Solución:** que la vista use un helper por lote junto a la regla canónica del servicio (que pasa a delegar en él), y que la píldora pida sus opciones al servicio. Mismo SQL, mismo resultado.
- **Tests a agregar:** un test que reemplaza la regla del servicio y verifica que la vista la consulta (rojo antes, verde después).
- **Verificación:** el test anterior, con mutación.
- **Regla para no repetirlo:** **skill** · `.claude/skills/seguridad-django/SKILL.md`, sección datos personales · «Una regla de visibilidad que tiene función en el servicio no se reescribe en la vista: si falta la versión por lote, se agrega al lado de la original y la original delega».

#### Aporte del segundo revisor (D4-SEG-01)
- **Detalle técnico:** Detalle técnico reservado hasta el arreglo; se agrega al informe con el PR que lo cierra.

---

### D-LIM-02 · Lógica de dominio y transacción de negocio en la vista del asistente de ingreso
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 5 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D2-LIM-03
- **Regla transversal «lógica de dominio en vistas» (R-1):** esta ficha es la más cara del grupo: la transacción de negocio (estadía + legajo + respuestas) vive en `views/dispositivos_ingreso.py:766`. Cruces: Becas ola 7 (B-LIM-01 a B-LIM-06) y Emergencia E-LIM-01.
- **Ubicación:** `programas/views/dispositivos_ingreso.py:766-791` (`_confirmar`: `transaction.atomic()` que compone `confirmar_ingreso` + `guardar_respuestas_ingreso`), `748-760` (enrutamiento de errores por las claves `"plaza"`/`"reserva"` del `ValidationError` del servicio), `601-626` (redacción del aviso de reservas a liberar)
- **Escenario:** la atomicidad «estadía + alta de legajo + respuestas del formulario de ingreso» es una regla de negocio (si el formulario falla, no hay ingreso) y hoy solo existe en la vista. Cualquier segundo camino de ingreso con formulario —Emergencia ya ingresa personas por `ingresar_persona` en `emergencia_confirmacion.py`— tiene que redescubrir y recomponer esa transacción. Además la vista decide «volver al paso plaza» según que el servicio haya puesto su error bajo la clave `"plaza"` o `"reserva"`: renombrar una clave en `estadias.py` (p. ej. `"reserva"` → `"reserva_id"`) cambia el flujo de pantalla sin que ningún test de servicio lo note.
- **Causa raíz:** el contrato entre servicio y vista es el diccionario de `ValidationError`, sin tipo; y la composición de dos servicios se resolvió donde estaba el formulario.
- **Solución:**
  1. `programas/services/ingreso.py::confirmar_ingreso_con_formulario(*, ..., formulario=None)` que hace el `transaction.atomic()` y llama a `confirmar_ingreso` y, si hay diseño, a `guardar_respuestas_ingreso`. La vista conserva solo `@archivos_atomicos` (es manejo de archivos del request) y llama a esa función.
  2. Excepción tipada `PlazaNoDisponible(ValidationError)` en `reglas_plaza` (D-LIM-20) lanzada por `bloquear_plaza`/`exigir_plaza_libre`/`bloquear_reserva_propia`, con los mismos `message_dict`; la vista hace `except PlazaNoDisponible` en lugar de inspeccionar claves.
  3. `_aviso_reserva_en_otro_dispositivo` y `_unir_con_y` → `ingreso.py`, junto a `reservas_en_otros_dispositivos`, que ya arma los datos.
- **Lo que NO hay que hacer:** mover `@archivos_atomicos` al servicio (depende de `request.FILES`); cambiar los mensajes que hoy ve el operador.
- **Tests a agregar:** `programas/tests/test_ingreso_servicio.py::ConfirmarConFormularioTests.test_falla_respuestas_deshace_estadia_y_legajo`; `...::PlazaNoDisponibleTests.test_reserva_ajena_es_plaza_no_disponible`.
- **Verificación:** los tests actuales de `IngresoConfirmarView` (rebote al paso plaza) verdes sin cambios.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` · «Un `transaction.atomic()` en `programas/views/` que encierra dos o más servicios es una transacción de negocio en la capa equivocada (ALTA en completa, `[MAJOR]` en pr). Una vista que ramifica por `error.message_dict` con claves del servicio necesita una excepción tipada».

---

### D-LIM-03 · La edición del legajo (diff, contacto, traza y envío) se escribe en la vista
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 5 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D1-LIM-02
- **Regla transversal «lógica de dominio en vistas» (R-1):** diff, contacto, traza y envío del legajo se escriben en `DispositivoUpdateView._guardar` y `DispositivoCreateView._guardar`. Cruces: Becas ola 7 (B-LIM-01 a B-LIM-06) y Emergencia E-LIM-01.
- **Ubicación:** `programas/views/dispositivos_legajo.py:699-724` (`DispositivoUpdateView._guardar`) y
  `:286-299` (`DispositivoCreateView._guardar`).
- **Escenario:** la edición es una operación de dominio completa y vive en la vista: bloquea la fila, vuelve a
  exigir que no esté `CERRADO`, arma el diff `{campo: {anterior, nuevo}}`, aplica `setattr`, sincroniza el
  contacto (Cambio 459), guarda con `update_fields`, reemplaza franjas, guarda el formulario del tipo, escribe la
  traza `EDITADO` y, si `POST["accion"] == "enviar_validacion"`, transiciona. Las transiciones de estado sí viven en
  `services/dispositivos.py:441-460`, y ahí `_sincronizar_contacto` (`:410-420`) hace un save y una traza parecidos
  con otra forma. Cualquier otro canal de edición (API, comando, app móvil) tendría que copiar estas 25 líneas o
  quedarse sin traza ni contacto sincronizado. El alta es más liviana, pero tiene el mismo defecto: cinco servicios
  orquestados y la rama `accion` leída del `request` dentro de la transacción.
- **Causa raíz:** el servicio del legajo se pensó para transiciones y la edición quedó en el `UpdateView`, que es
  donde Django la sugiere. CLAUDE.md lo prohíbe: «views/ orquestación HTTP, sin lógica de dominio».
- **Solución:** en `programas/services/dispositivos.py`:
  ```python
  def editar_dispositivo(dispositivo, usuario, datos: dict, *, franjas, formulario_tipo=None, enviar=False):
      with transaction.atomic():
          dispositivo = Dispositivo.objects.select_for_update().get(pk=dispositivo.pk)
          if dispositivo.estado == Dispositivo.Estado.CERRADO:
              raise PermissionDenied
          cambios = {c: {"anterior": getattr(dispositivo, c), "nuevo": v} for c, v in datos.items()}
          ...  # el mismo cuerpo de hoy, sin request
          return enviar_desde_formulario(dispositivo, usuario) if enviar else dispositivo
  def crear_dispositivo(form, usuario, *, responsables, franjas, formulario_tipo=None, enviar=False): ...
  ```
  La vista pasa `{c: form.cleaned_data[c] for c in form.changed_data}`, `enviar=request.POST.get("accion") ==
  "enviar_validacion"` y conserva `@archivos_atomicos` por fuera. `guardar_respuestas_alta` lo recibe el servicio
  como `formulario_tipo` (el objeto del form ya trae diseño, foto, respuestas y archivos). El texto de los mensajes
  y los `form_invalid` no cambian.
- **Lo que NO hay que hacer:** sacar la relectura de `CERRADO` bajo lock (`:703`) porque `get_object` ya lo
  revisó (`:695`): son dos momentos distintos y la segunda es la que cierra la carrera.
- **Tests a agregar:** `programas/tests/test_dispositivos_legajo.py::EditarDispositivoServicioTests.test_registra_diff_y_contacto`,
  `::test_cerrado_bajo_lock_rechaza`.
- **Verificación:** la suite de `test_dispositivos_legajo` y `test_dispositivos_formulario_alta` pasa sin cambios.
  El `patch("programas.views.dispositivos_legajo.registrar_alta_dispositivo")` de los tests pasa a apuntar al servicio.
- **Regla para no repetirlo:** **control mecánico** · `programas/tests/test_arquitectura.py` · ratchet: ninguna
  vista de `programas/views/` llama a `select_for_update()` ni arma un dict `{"anterior": ..., "nuevo": ...}`
  (`grep -n "select_for_update\|\"anterior\":" programas/views/` con conteo congelado; hoy: 1 y 1 en este archivo).

---

### D-SEG-01 · Un atajo permite otorgarse un rol propio
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (PoC reproducida; test en el PR que la arregla) · **Eje:** SEG · **Origen:** thermos-correccion · **Ola:** 0 · **Esfuerzo:** S
- **ID de la pasada 1:** D3-SEG-02
- **Escenario:** Un operador puede otorgarse un rol que su perfil no debería darle.
- **Detalle técnico:** Detalle técnico reservado hasta el arreglo; se agrega al informe con el PR que lo cierra.
- **Solución:** Reservada hasta el arreglo; propuesta por defecto: aplicar al atajo la misma guarda que el ABM de usuarios.
- **Tests a agregar:** Reservada hasta el arreglo.
- **Verificación:** Reservada hasta el arreglo.
- **Regla para no repetirlo:** **control mecánico + skill** · regla R-2 (sección 4): todo atajo que otorga roles aplica la misma guarda que el ABM de usuarios.

---

### D-SEG-02 · El historial muestra texto libre a quien no puede ver a la persona
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** SEG · **Origen:** fusión de D1-SEG-01 + D3-SEG-01 · **Ola:** 0 · **Esfuerzo:** S
- **ID de la pasada 1:** D1-SEG-01 + D3-SEG-01 (**hallado por 2 revisores**)
- **Escenario:** El historial muestra, a quien no ve a la persona, un texto libre que no debería ver.
- **Detalle técnico:** Detalle técnico reservado hasta el arreglo; se agrega al informe con el PR que lo cierra.
- **Solución:** Reservada hasta el arreglo; propuesta por defecto: DECISIÓN CLIENTE: mostrar solo lo que el usuario puede ver de la persona.
- **Tests a agregar:** Reservada hasta el arreglo.
- **Verificación:** Reservada hasta el arreglo.
- **Regla para no repetirlo:** **control mecánico** · regla R-4 (sección 4): el texto libre y los datos de personas solo salen con `ciudadano.ver`.

---

### D-ERR-01 · Configurar capacidad toma dispositivo→plaza y el ingreso toma plaza→dispositivo: deadlock 1213
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (PoC reproducida; test en el PR que la arregla: ERROR 1213 reproducido en MariaDB 10.11 con 2 hilos en los dos caminos, `ingresar_persona` contra `editar_plaza` y `corregir_entrada` contra `registrar_entrada`) · **Eje:** ERR · **Origen:** fusión de D2-ERR-01 + D2-DAT-01 + D3-DAT-01; (distinto del 1213 egreso↔confirmación aceptado; Cambio 290 no lo cubre) · **Ola:** 1 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D2-ERR-01 + D2-DAT-01 + D3-DAT-01 (**hallado por 3 revisores**)
- **Verificación de la pasada 2 (PoC, el juez):** CONFIRMADO con test, PoC reproducida; test en el PR que la arregla. El ERROR 1213 se reprodujo en MariaDB 10.11 con 2 hilos en **los dos caminos** (`ingresar_persona` contra `editar_plaza`; `corregir_entrada` contra `registrar_entrada`). Ninguna capa traduce el 1213: llega como 500. InnoDB elige la víctima y el rollback no deja datos inconsistentes. **Severidad MEDIA y primera ola de concurrencia, no Ola 0** (decisión del juez). Para correr la PoC hace falta `DJANGO_SYNCDB_PROJECT_APPS=False`: con `True` el syncdb falla en MariaDB con el error 1005 por la FK de `users_profile`.
- **Hallado por 3 revisores (sube de peso):** D2-ERR-01 (ingreso contra capacidad), D2-DAT-01 (la misma inversión, con `editar_sector` y la baja de plaza) y D3-DAT-01 (bitácora: corregir una novedad contra cargar una). Son tres caras de un mismo defecto: no hay un orden global de candados. Las tres soluciones difieren en el orden propuesto (contradicción 1 de la sección 1): hay que fijar **un** orden antes de tocar código, y la alternativa común a las tres es reintentar la transacción entera ante `OperationalError` 1213 con tope.
- **Cruce con Emergencia:** la orquestación de candados del ingreso está copiada tres veces (E-LIM-15) y dos aceptaciones simultáneas eligen las mismas camas (E-PERF-09, E-PERF-10): el orden global tiene que ser el mismo para Emergencia y Dispositivos, o el arreglo de uno reabre el deadlock del otro.
- **Ubicación:** `programas/services/plazas.py:187-193` (`_bloquear_dispositivo`), `:311`/`:336` (`editar_sector`), `:492-493` (`editar_plaza`), `:548-549` (`dar_de_baja_plaza`), `:576-577` (`reactivar_plaza`) contra `programas/services/estadias.py:465` (lock de plaza en `ingresar_persona`), `:502`/`:530` (INSERT de `Estadia`/`TrazaDispositivo` con FK al dispositivo), `:827`/`:858` (`reservar_plaza`), `:990`/`:1001` (`sacar_plaza_de_servicio`).
- **Escenario:** el operador A confirma un ingreso en la plaza P del dispositivo D (X sobre P; el INSERT de la estadía/traza pide S sobre D por la FK). A la vez el admin B edita P (X sobre D, después pide X sobre P). Ciclo → InnoDB aborta una con `ERROR 1213`; la vista de ingreso atrapa `ValidationError`, `Ciudadano.DoesNotExist` y `Plaza.DoesNotExist`, no `OperationalError` → 500.
- **Causa raíz:** `plazas.py` bloquea el dispositivo antes que la plaza, el orden inverso al de todos los caminos de `estadias.py` y a la convención escrita en `bitacora.py:199` («estadía y después dispositivo, por la FK»).
- **Solución:** en las cuatro funciones de `plazas.py`, bloquear primero la(s) plaza(s) ordenadas por pk y después `_bloquear_dispositivo`; el resto del cuerpo igual. Alternativa sin tocar el orden: capturar `OperationalError` 1213 en las vistas de ingreso/capacidad y devolver el mensaje de «reintentá» que ya usa el camino aceptado.
- **Lo que NO hay que hacer:** sacar el `select_for_update` del dispositivo en `plazas.py` (protege `puede_configurar_plazas` contra un cierre concurrente).
- **Tests a agregar:** `programas/tests/test_dispositivos_concurrencia.py::OrdenDeCandados.test_editar_plaza_e_ingreso_no_deadlock` (solo motor real, `skipUnless` MySQL/MariaDB, dos hilos).
- **Verificación:** test con dos conexiones en el banco MariaDB 3310; ninguna termina en 1213.
- **Regla para no repetirlo:** **skill** · `mysql-mariadb` (transacciones) · «Orden global de candados en Dispositivos: estadía → plaza → reserva → ciudadano → dispositivo. Un INSERT con FK al dispositivo cuenta como candado S sobre el dispositivo.»

#### Aporte del segundo revisor (D2-DAT-01: La configuración de plazas bloquea dispositivo → plaza y la operación plaza → dispositivo: deadlock (ERROR 1213) que llega como 500)
_Pasada 1: severidad BAJA · estado PLAUSIBLE (el orden invertido está CONFIRMADO por lectura; el deadlock pide concurrencia sobre la misma plaza o el mismo sector) · esfuerzo S-M._

- **Ubicación:** las que toman primero el dispositivo y después la plaza: `programas/services/plazas.py:492-493` (`editar_plaza`), `plazas.py:548-549` (`dar_de_baja_plaza`) y `plazas.py:311-336` (`editar_sector` con baja: dispositivo → sector → todas sus plazas). Las que toman primero la plaza y después, por FK, el dispositivo: `programas/services/estadias.py:465` y `:502` (`ingresar_persona`: `FOR UPDATE` de la plaza y luego el `INSERT` de `Estadia`, `MovimientoEstadia`, `TrazaDispositivo` y `EntradaBitacora`, todas con FK a `Dispositivo`), `estadias.py:686` y `:708-718` (`cambiar_plaza`), `:763` y `:775-785` (`asignar_plaza`), `:990` y `:1001` (`sacar_plaza_de_servicio`), y `:942` y `:955` (`liberar_reserva`).
- **Escenario:** T1, un operador, confirma un ingreso en la plaza P del dispositivo D: toma X sobre P (`_bloquear_plaza`). T2, un administrador, guarda «Editar plaza» sobre P: toma X sobre D (`_bloquear_dispositivo`) y espera P. T1 llega al `INSERT` de la estadía, y el chequeo de FK de InnoDB pide S sobre D, que tiene T2. InnoDB detecta el ciclo y aborta a uno con `ERROR 1213`. Ningún servicio lo traduce, así que el usuario ve un 500. Pasa lo mismo con «Sacar de servicio» contra «Editar plaza» sobre la misma plaza, y con un ingreso contra la baja del sector de esa plaza (`editar_sector` bloquea todas las plazas del sector **después** del dispositivo).
- **Causa raíz:** `programas/services/bitacora.py:190-200` ya documenta esta misma trampa («quien pida el dispositivo primero y la estadía después arma un ciclo») y la resuelve para las novedades: estadía → dispositivo. `plazas.py` no la sigue: pide el dispositivo antes que la plaza, al revés de la operación diaria, que toma la plaza y después el S implícito sobre el dispositivo por la FK.
- **Solución:** que todos los caminos que tocan una plaza la tomen **antes** que el dispositivo, igual que las estadías en bitácora. En `editar_plaza` y `dar_de_baja_plaza`: `select_for_update` de la plaza por pk primero (sin JOIN), después `_bloquear_dispositivo`, y recién entonces las comprobaciones de código único y de plaza tomada. Las dos comprobaciones quedan con ambas filas bloqueadas, así que la regla de unicidad del Cambio 430 se sostiene igual. En `editar_sector` con baja: bloquear las plazas del sector (`order_by("pk")`), después el dispositivo y después el sector. Las altas (`crear_sector`, `agregar_plazas`) no bloquean plazas y no cambian. Si el reorden no se acepta, la alternativa de la skill (§Transacciones y bloqueos) es reintentar la transacción entera ante `OperationalError` 1213, con tope de reintentos. La lógica y la UI no cambian.
- **Lo que NO hay que hacer:** sacar `_bloquear_dispositivo` de `editar_plaza`, porque sostiene el código único por sector frente a `agregar_plazas`. Y no meter `select_related("sector")` en el `FOR UPDATE` de la plaza: bloquearía el sector, como explican `estadias.py:321-324`.
- **Tests a agregar:** `programas/tests/test_dispositivos_concurrencia.py::OrdenConfiguracionTests.test_editar_plaza_y_ingreso_no_forman_ciclo` (dos hilos contra MariaDB, el mismo patrón del archivo) y `OrdenDeLosCandadosTests.test_editar_plaza_bloquea_plaza_antes_que_dispositivo` (secuencia de llamadas en SQLite).
- **Verificación:** con dos sesiones de `mysql` contra el banco. S1: `BEGIN; SELECT id FROM programas_plaza WHERE id=P FOR UPDATE;`. S2: `BEGIN; SELECT id FROM programas_dispositivo WHERE id=D FOR UPDATE; SELECT id FROM programas_plaza WHERE id=P FOR UPDATE;` (queda esperando). S1: un `INSERT INTO programas_trazadispositivo` con `dispositivo_id=D`, y una de las dos recibe `ERROR 1213`. Después del arreglo, S2 espera en la plaza sin tener el dispositivo y no hay ciclo. Correr `SHOW ENGINE INNODB STATUS` enseguida.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` §Transacciones y bloqueos · «Un `INSERT`/`UPDATE` en una tabla con FK pide un lock **compartido** sobre la fila padre. En Dispositivos el orden global es plaza → reserva → persona → estadía → **dispositivo**: un servicio que bloquee el dispositivo (`select_for_update`) antes que una plaza o una estadía arma un ciclo con cualquier ingreso, egreso o cambio que escriba una fila hija del dispositivo.»

#### Aporte del segundo revisor (D3-DAT-01: Corregir una novedad toma el dispositivo (S, por FK) antes que las estadías; cargar una novedad las toma al revés: deadlock (ERROR 1213) que llega como 500)
_Pasada 1: severidad BAJA · estado PLAUSIBLE (el orden invertido está CONFIRMADO por lectura; el deadlock pide dos operadores del mismo dispositivo, en el mismo turno, con una persona en común) · esfuerzo S._

- **Ubicación:** `programas/services/bitacora.py:734` (`corregir_entrada`: `FOR UPDATE` de la entrada raíz), `:813` → `:384` (`_guardar_adjuntos`: `INSERT` de `AdjuntoBitacora`, FK a `Dispositivo` ⇒ S sobre el dispositivo), `:830` (`INSERT` de la versión nueva, FK a `Dispositivo` ⇒ S) y `:833` → `:481` (`_vincular` → `entrada.personas.set`: `INSERT` en la tabla intermedia, FK a `Estadia` ⇒ S sobre cada estadía). Del otro lado, `registrar_entrada`: `:421-423` (X sobre las estadías, `order_by("pk")`) y `:426` (`_bloquear_dispositivo`: X sobre el dispositivo).
- **Escenario:** turno en curso del dispositivo D, la persona alojada con estadía E. T1, operador A, corrige una novedad que ya nombra a E y le suma un acta: toma X sobre la raíz, inserta el `AdjuntoBitacora` (InnoDB pide S sobre D para chequear la FK y lo retiene hasta el commit) y escribe el archivo al storage. T2, operador B, carga una novedad nueva sobre E: toma X sobre E (`:421`) y pide X sobre D (`:426`), que espera el S de T1. T1 llega a `_vincular` e inserta la fila (versión nueva, E) en la tabla intermedia: pide S sobre E, que tiene T2. Ciclo: InnoDB aborta a uno con `ERROR 1213`. Ninguna de las dos vistas lo traduce (`views/dispositivos_bitacora.py:220-225` solo atrapa `PermissionDenied` y `ValidationError`), así que el usuario ve un 500. Sin adjuntos nuevos el S sobre D aparece recién en `:830`, inmediatamente antes de `:833`: la ventana es de microsegundos; con adjuntos dura lo que tarda escribir hasta 10 archivos de 5 MB.
- **Causa raíz:** `bitacora.py:199-201` fija el orden global «estadía y después dispositivo» y `registrar_entrada` lo respeta, pero `corregir_entrada` no bloquea las estadías de la versión nueva: las toma recién al final, implícitamente, por la FK de la tabla intermedia, cuando ya retiene el S del dispositivo que dejó el primer `INSERT`. Un `INSERT` con FK pide un lock compartido sobre la fila padre aun en `READ COMMITTED`.
- **Solución:** en `corregir_entrada`, después del `FOR UPDATE` de la raíz (`:734`) y antes de `_guardar_adjuntos` (`:813`), bloquear las estadías que va a vincular la versión nueva, igual que `registrar_entrada`: `list(Estadia.objects.select_for_update().filter(pk__in=ids).order_by("pk").values_list("pk", flat=True))`, sin `select_related`. El cálculo de `estadias` (`:770-802`) son lecturas y ya está antes de `:813`: alcanza con insertar el bloqueo entre `:802` y `:803` con los ids de `estadias`. El orden queda raíz → estadías → dispositivo, compatible con `registrar_entrada` (que no toma entradas) y con egreso o cambio de plaza (estadía → dispositivo). La regla, los mensajes y la pantalla no cambian. Si no se acepta el reorden, la alternativa de la skill (§Transacciones y bloqueos) es reintentar la transacción entera ante `OperationalError` 1213, con tope de reintentos.
- **Lo que NO hay que hacer:** bloquear el dispositivo con `select_for_update` en `corregir_entrada` «para serializar todo»: pedido antes que las estadías arma el mismo ciclo con `registrar_entrada` en X/X, y pedido después suma la espera de D-PERF-07 a cada corrección. Tampoco meter `select_related("dispositivo")` en el `FOR UPDATE` de la raíz (`:732-733` explican por qué).
- **Tests a agregar:** `programas/tests/test_dispositivos_concurrencia.py::CarreraDeBitacoraTests.test_corregir_y_cargar_sobre_la_misma_persona_no_forman_ciclo` (dos hilos contra el motor real, el patrón de `_BaseCarrera`, con un `threading.Event` que frene a T1 después de `_guardar_adjuntos`); y en SQLite `programas/tests/test_dispositivos_bitacora.py::OrdenDeCandadosTests.test_corregir_bloquea_estadias_antes_de_insertar` (con `CaptureQueriesContext`: el `SELECT … FOR UPDATE` de `programas_estadia` antes del primer `INSERT`).
- **Verificación:** dos sesiones de `mysql` contra el banco MariaDB (3310). S1: `BEGIN; INSERT INTO programas_adjuntobitacora (dispositivo_id, …) VALUES (D, …);`. S2: `BEGIN; SELECT id FROM programas_estadia WHERE id=E FOR UPDATE; SELECT id FROM programas_dispositivo WHERE id=D FOR UPDATE;` (queda esperando). S1: `INSERT INTO programas_entradabitacora_personas (entradabitacora_id, estadia_id) VALUES (X, E);` y una de las dos recibe `ERROR 1213`. `SHOW ENGINE INNODB STATUS\G` enseguida. Después del arreglo, S1 pide E antes del primer `INSERT` y espera sin retener D: no hay ciclo.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` §Transacciones y bloqueos · «Un servicio que va a insertar filas que apuntan a una estadía (tabla intermedia incluida) bloquea esas estadías **antes** del primer `INSERT` con FK al dispositivo. Las FK también toman candados: el orden global en Dispositivos es estadía → dispositivo, y el `INSERT` de un hijo del dispositivo cuenta como tomar el dispositivo.»

---

### D-ERR-02 · Cerrar un dispositivo no mira si tiene personas alojadas o reservas, y después del cierre se puede seguir operando
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** fusión de D1-ERR-01 + D2-ERR-03 + D2-ERR-04 + D2-LIM-05 · **Ola:** 3 · **Esfuerzo:** M
- **ID de la pasada 1:** D1-ERR-01 + D2-ERR-03 + D2-ERR-04 + D2-LIM-05 (**hallado por 4 revisores**)
- **Hallado por 4 revisores (sube de peso):** D1-ERR-01 (cerrar no mira estadías ni reservas), D2-ERR-03 (se reserva en un dispositivo no activo y se cierra con abiertas), D2-ERR-04 (sacar o volver plaza a servicio ignora el cierre y da 500 si la plaza se desactiva en paralelo) y D2-LIM-05 (esas dos operaciones viven fuera de `plazas.py` y por eso no aplican la regla). Una sola causa: la regla «dispositivo cerrado» no está en el servicio sino en cada llamador. Hay que llevar la guarda a **cada mutador** (tabla de mutadores con test parametrizado, regla R-8).
- **DECISIÓN CLIENTE:** default = un dispositivo cerrado no admite cambios operativos de plaza ni reservas, y cerrar rechaza si hay `Estadia.activas()` o `ReservaPlaza` vigente. Contradicción 2 de la sección 1: «cerrado» (D1-ERR-01, D2-ERR-04) contra «no ACTIVO» (D2-ERR-03).
- **Ubicación:** `programas/services/dispositivos.py:553-562` (`cerrar_dispositivo`) y `:441-460` (`_transicionar`); `programas/services/estadias.py:798-835` (`reservar_plaza`), `:647-690` (`cambiar_plaza`), `:733` (`asignar_plaza`), `:967` (`sacar_plaza_de_servicio`); `programas/templates/programas/dispositivos/legajo/detail.html:77-79`; `programas/services/detalle_dispositivo.py:95`
- **Escenario:** un dispositivo ACTIVO con 12 estadías activas y 2 reservas vigentes se cierra desde
  «Más acciones → Cerrar». La confirmación dice «impide nuevas operaciones». Después del cierre:
  (a) las 12 estadías siguen `ACTIVA` en un dispositivo cerrado. Como hay un control de
  alojamiento en la red, esas personas no pueden ingresar en otro dispositivo hasta que alguien las
  egrese desde el cerrado. (b) Las reservas siguen tomando plazas que nunca se van a consumir
  (el ingreso exige ACTIVO, `estadias.py:454`). (c) Desde el mapa de plazas y el detalle se puede
  reservar, prestar, cambiar o asignar plaza y sacar plazas de servicio: ninguno de esos servicios
  mira `dispositivo.estado`. Solo el ingreso, los edificios (`edificios.py:73`) y la capacidad
  (`plazas.py:119, 137`) lo bloquean.
- **Causa raíz:** `_transicionar` solo valida los estados de origen. El cierre no tiene precondición
  sobre estadías ni reservas, y la regla «cerrado = sin operaciones» está escrita en el aviso y en la
  confirmación, pero no en los servicios de plaza y estadía.
- **Solución:** `DECISIÓN CLIENTE: por defecto, (1) `cerrar_dispositivo` rechaza con ValidationError
  («Egresá a las personas alojadas y liberá las reservas antes de cerrar.») si hay `Estadia.activas()`
  o `ReservaPlaza` vigente del dispositivo, dentro del mismo `select_for_update`; (2)
  `reservar_plaza`, `cambiar_plaza`, `asignar_plaza`, `sacar_plaza_de_servicio` y
  `volver_plaza_a_servicio` rechazan si el dispositivo está CERRADO, con el mismo patrón que
  `plazas.py:137`. El egreso queda permitido siempre.` Inactivar puede quedar como está (es temporal),
  pero conviene decidirlo en la misma consulta.
- **Lo que NO hay que hacer:** egresar o liberar en cascada dentro del cierre (es un dato clínico y
  administrativo que exige motivo y destino por persona), o bloquear también el egreso (dejaría a las
  personas sin salida).
- **Tests a agregar:** `programas/tests/test_dispositivos_legajo.py::CerrarDispositivo.test_no_cierra_con_estadias_activas`, `::test_no_cierra_con_reservas_vigentes`, `programas/tests/test_estadias.py::DispositivoCerrado.test_no_reserva_ni_cambia_plaza`, `::test_egreso_sigue_permitido`
- **Verificación:** con los tests, cerrando en la pantalla un dispositivo con personas alojadas y viendo el error en el toast.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/errores.md` · «Un estado terminal ("cerrado", "dado de baja") se hace cumplir en CADA servicio que muta hijos del objeto, no en el texto de la confirmación; y la transición a ese estado revisa qué hijos vivos deja colgados.»

#### Aporte del segundo revisor (D2-ERR-03: Se puede reservar plaza en un dispositivo no activo, y cerrarlo con estadías o reservas abiertas)
_Pasada 1: severidad BAJA · estado CONFIRMADO (lectura) · esfuerzo S._

- **Ubicación:** `programas/services/estadias.py:797-840` (`reservar_plaza`, sin chequeo de estado), `programas/services/sectores_plazas.py:156-159` (acción de reservar en P5); relacionado, fuera de la tajada: `programas/services/dispositivos.py:524` (`inactivar_dispositivo`) y `:553` (`cerrar_dispositivo`).
- **Escenario:** dispositivo SUSPENDIDO o CERRADO; un POST armado o una pestaña vieja crea una `ReservaPlaza` que toma la plaza. Al revés: se cierra un dispositivo con personas alojadas y reservas vigentes; quedan estadías abiertas en un dispositivo cerrado que el asistente (exige ACTIVO) ya no deja tocar.
- **Causa raíz:** `ingresar_persona` mira `dispositivo.estado` (`:454`) pero `reservar_plaza` no; las transiciones de estado del dispositivo no miran ocupación.
- **Solución:** en `reservar_plaza`, la misma guarda de estado que `ingresar_persona:454`. DECISIÓN CLIENTE para el cierre: propuesta por defecto, `cerrar_dispositivo` rechaza si hay estadías abiertas o reservas vigentes, con la cantidad en el mensaje.
- **Tests a agregar:** `programas/tests/test_estadias.py::Reserva.test_rechaza_dispositivo_no_activo`; `programas/tests/test_dispositivos.py::Cierre.test_rechaza_con_estadias_abiertas`.
- **Verificación:** tests con mutación.
- **Regla para no repetirlo:** **control mecánico** · test de contrato en `test_estadias.py` que recorre las funciones públicas de `estadias.py` que crean filas y exige que todas rechacen un dispositivo no ACTIVO.

#### Aporte del segundo revisor (D2-ERR-04: Sacar/volver plaza a servicio ignora el dispositivo cerrado y da 500 si la plaza se desactiva en paralelo)
_Pasada 1: severidad BAJA · estado CONFIRMADO (lectura) · esfuerzo S._

- **Ubicación:** `programas/services/estadias.py:966-1009` (`sacar_plaza_de_servicio`, `.get` en `:990`), `:1012-1041` (`volver_plaza_a_servicio`, `.get` en `:1025`); `programas/services/plazas.py:119-138` (`puede_configurar_plazas`, que sí rechaza CERRADO); `plazas.py:493` (mismo `.get`).
- **Escenario:** (a) dispositivo CERRADO: un POST armado saca la plaza de servicio e inserta traza; la UI lo esconde, el servicio lo acepta. (b) A abre la plaza, B la da de baja, A confirma: `Plaza.objects` (manager de activas) no la encuentra → `DoesNotExist` sin capturar → 500.
- **Causa raíz:** las dos funciones no reusan la regla de `puede_configurar_plazas` y bloquean con el manager filtrado sin traducir el «no existe».
- **Solución:** la guarda de estado de `plazas.py:119-120` al inicio de ambas; envolver el `.get` en `try/except Plaza.DoesNotExist` → `ValidationError("La plaza ya no está activa.")`. Igual en `plazas.py:493`.
- **Tests a agregar:** `programas/tests/test_estadias.py::FueraDeServicio.test_rechaza_dispositivo_cerrado`, `::test_plaza_dada_de_baja_devuelve_error_de_validacion`.
- **Verificación:** tests; la vista muestra un toast de error, no un 500.
- **Regla para no repetirlo:** **skill** · `seguridad-django` · «Lo que la UI esconde por estado, el servicio lo rechaza por estado.»

#### Aporte del segundo revisor (D2-LIM-05: «Sacar/volver a servicio» viven fuera del módulo de plazas y por eso no aplican la regla de dispositivo cerrado)
_Pasada 1: severidad MEDIA · estado CONFIRMADO (lectura) · esfuerzo S._

- **Ubicación:** `programas/services/estadias.py:966-1009` y `1012-1041` (solo `puede_operar_dispositivo(..., CAP_EDITAR)`); `programas/services/plazas.py:111-138` (`puede_configurar_plazas` y `_exigir_alcance` rechazan `CERRADO`); `programas/views/dispositivos_legajo.py:1303-1329` (las vistas no miran el estado)
- **Escenario:** dispositivo `CERRADO`. La pantalla no ofrece «Sacar de servicio» porque `puede_configurar_plazas` devuelve `False`, pero un POST armado a `PlazaFueraDeServicioView` llega a `sacar_plaza_de_servicio`, que solo verifica capacidad y alcance: la plaza del dispositivo cerrado cambia de estado y deja traza `PLAZA_FUERA_SERVICIO`. `editar_plaza`, `dar_de_baja_plaza` y `reactivar_plaza` (mismo `CAP_EDITAR`, mismo tipo de dato) sí lo rechazan con `DISPOSITIVO_CERRADO`.
- **Causa raíz:** el docstring de `sacar_plaza_de_servicio` (970-971) justifica vivir en `estadias` porque «la condición que la gobierna es la estadía»; pero la condición de estadía es una **consulta** (`plaza_tomada_por`), y la regla del recurso (cerrado, alcance de configuración) quedó en `plazas.py`. Al partirse, una de las dos mitades perdió una guarda.
- **Solución:** mover ambas funciones a `programas/services/plazas.py`, reemplazar el chequeo de capacidad por `_exigir_alcance(dispositivo, usuario)` (que agrega el rechazo de `CERRADO` con el mensaje existente) y seguir preguntando `plaza_tomada_por` (pública, D-LIM-16). Re-exportar desde `programas.services.estadias` una release. **DECISIÓN CLIENTE:** confirmar que un dispositivo cerrado no debe admitir cambios de estado operativo de plazas (propuesta por defecto: no, igual que editar/dar de baja).
- **Lo que NO hay que hacer:** agregar el chequeo de `CERRADO` solo en la vista: es justo la trampa «que la regla dependa de que la vista se acuerde» que el propio módulo documenta en `egresar_persona`.
- **Tests a agregar:** `programas/tests/test_plazas_servicio.py::DispositivoCerradoTests.test_sacar_de_servicio_rechaza_cerrado` y `test_volver_a_servicio_rechaza_cerrado`.
- **Verificación:** los dos tests en rojo antes del cambio (mutación) y verdes después.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` · «Toda escritura sobre `Plaza`/`Sector` pasa por `plazas._exigir_alcance`; un servicio que escribe una plaza con `puede_operar_dispositivo(..., CAP_EDITAR)` a secas es una guarda incompleta».

---

### D-ERR-03 · El ingreso retroactivo no tiene cota inferior: reescribe censo, historial y turnos viejos
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** nuevo · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** D2-ERR-02
- **Ubicación:** `programas/services/estadias.py:457-460` (solo valida «no futura»), `programas/forms_ingreso.py:106-112` (`IngresoConfirmarForm.fecha_ingreso`).
- **Escenario:** el operador tipea 2025 en lugar de 2026. La plaza y el dispositivo se crearon en 2026; `_exigir_plaza_libre_desde` no encuentra estadías previas y acepta. La estadía queda abierta desde 2025: el censo de 2025 la cuenta, la línea de tiempo muestra ocupación anterior a la existencia del dispositivo y la bitácora la cruza con turnos que no existían.
- **Causa raíz:** el servicio y el form validan contra «ahora» y contra otras estadías, nunca contra la vida de la plaza o del dispositivo.
- **Solución:** en `ingresar_persona`, rechazar `fecha_ingreso < max(plaza.creado, dispositivo.creado)` (o la fecha de activación si existe) con `ValidationError` del mismo estilo que el de «futura». DECISIÓN CLIENTE: si además se quiere un tope de días hacia atrás (propuesta por defecto: sin tope, solo la cota de existencia).
- **Lo que NO hay que hacer:** ponerlo solo en el form; la API y otros llamadores del servicio quedarían afuera.
- **Tests a agregar:** `programas/tests/test_estadias.py::IngresoRetroactivo.test_rechaza_fecha_anterior_a_la_plaza`.
- **Verificación:** test rojo sin la guarda (mutación), verde con ella.
- **Regla para no repetirlo:** **CLAUDE.md** · Convenciones de implementación · «Toda fecha retroactiva cargada a mano tiene cota inferior en el servicio (la creación del objeto que la contiene).»

---

### D-ERR-04 · Una foto o un adjunto que llega después de «Revisado» se rechaza para siempre y la evidencia se pierde
**Severidad:** MEDIA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** nuevo · **Ola:** 3 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D4-ERR-01
- **Ubicación:** `programas/services/inspecciones.py:673-676` (`_admitir_carga`: `inspeccion.revisado_en is not None` →
  `_conflicto_estado()`), `:483-490` (`puede_revisar` no mira si faltan cargas), `:461-480` (`marcar_revisado`);
  `programas/api/views_inspecciones.py:240-243` y `:277-280` (el contrato dice que la app sin conexión manda fotos y
  adjuntos **después** del resultado).
- **Escenario:** el agente cierra el relevamiento sin señal. Al recuperar conexión la app manda primero `resultado/`
  (queda `REALIZADA`) y después, de a una, las fotos y el archivo de un campo ARCHIVO obligatorio. Entre el resultado y la
  segunda foto el coordinador abre «Completados» y marca «Revisado» (la acción se ofrece apenas hay resultado). Desde ahí
  cada `POST fotos/` y `POST adjuntos/` pendiente devuelve 409 `ESTADO_NO_ADMITE`, que la app no reintenta. El informe
  queda con menos fotos de las que se sacaron y, si era un ARCHIVO obligatorio, con «Falta el archivo» para siempre
  (`formulario_del_relevamiento` → `faltantes`), sin forma de cargarlo: la galería es aditiva e inmutable.
- **Causa raíz:** la regla «revisado no admite cargas» se escribió pensando en cargas nuevas, pero el mismo flujo offline
  que el módulo soporta hace que las cargas **del mismo envío** lleguen después del resultado. Nada distingue «foto
  tardía del cierre» de «foto nueva sobre algo ya revisado», y la revisión no espera ni avisa.
- **Solución:** `DECISIÓN CLIENTE: aceptar, después de la revisión, las fotos y adjuntos del agente que cerró el
  relevamiento (`usuario.pk == inspeccion.realizada_por_id`), con una traza propia «llegó después de la revisión»; para
  cualquier otro sigue el 409.` En código: en `_admitir_carga`, cambiar la condición a
  `inspeccion.revisado_en is not None and usuario.pk != inspeccion.realizada_por_id`. Alternativa sin tocar la regla: en
  `informe_de_relevamiento` / P21, si el formulario tiene ARCHIVO obligatorios faltantes, `puede_revisar` devuelve
  `False` con el motivo «faltan archivos del territorial».
- **Lo que NO hay que hacer:** abrir las cargas a cualquier agente o a cualquier estado; quitar la inmutabilidad de
  `FotoInspeccion`.
- **Tests a agregar:** `programas/tests/test_api_inspecciones.py::EnvioTardio.test_foto_del_mismo_agente_despues_de_revisado`,
  `::test_otro_agente_despues_de_revisado_sigue_409`.
- **Verificación:** con los tests; en QA, cerrar desde la app en modo avión, revisar desde P21 y volver a dar señal.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/errores.md` · «En toda API con cola offline,
  cada estado terminal que se agregue del lado servidor se contrasta con el orden real de envío de la app: si lo que el
  contrato dice que llega "después" puede quedar rechazado por una acción humana intermedia, eso es pérdida de datos, no
  un conflicto.»

---

### D-PERF-01 · El historial del detalle lee y arma en Python toda la auditoría anterior a la página pedida
**Severidad:** ALTA · **Estado:** MEDIDO en banco · **Eje:** PERF · **Origen:** fusión de D1-PERF-01 + D1-ERR-04 · **Ola:** 4 · **Esfuerzo:** M
- **Medición en banco (19-nov-2026):** `/dispositivos/1/?tab=historial&historial_page=1` / `=99999`: 6.171 ms / 64.009 ms calientes en la segunda medición (frío 99.670 ms), 44 consultas; en la primera, 1.966 / 57.818 ms. La consulta de `Estadia` / `MovimientoEstadia` del historial tarda 19,7 s en `ANALYZE` y ≈ 60 s de SQL en el request (en la primera medición, 36,7 s en una sola consulta de `MovimientoEstadia`). **Sube a ALTA y corta en ECOM** (`read_timeout` 10 s): la página profunda no termina y la página 1 ya tarda ≈ 6,2 s porque lee y arma toda la auditoría anterior. No depende de la siembra.
- **ID de la pasada 1:** D1-PERF-01 + D1-ERR-04 (**hallado por 2 revisores**)
- **Hallado por 2 revisores (sube de peso):** D1-PERF-01 (rendimiento: el historial arma en Python toda la auditoría anterior a la página pedida) y D1-ERR-04 (corrección: pasar a una página profunda lee cada fuente completa). Es el mismo código; la solución es la misma (cursor por fuente o tope de páginas, DECISIÓN CLIENTE en el cuerpo). Va junto con el índice de D-DAT-01 (`TrazaDispositivo`/`EntradaBitacora`), que sirve al mismo orden.
- **Ubicación:** `programas/selectors/auditoria_dispositivo.py:370-382` (`FeedAuditoria.__getitem__`), alimentado
  por `programas/services/detalle_dispositivo.py:309` (`Paginator(feed, 20).get_page(pagina)`) desde
  `programas/views/dispositivos_legajo.py:438`.
- **Escenario:** para la página `p` del historial, `__getitem__` hace `consulta[:hasta]` con `hasta = p × 20`
  **en cada una de las cuatro fuentes**, hidrata cada fila como modelo con sus `select_related` (la de
  `MovimientoEstadia` encadena 6 JOINs: responsable, estadía→ciudadano, estadía→motivo, plaza origen→sector,
  plaza destino→sector), arma el dict de cada una (`evento_de_traza` hace `json.loads` del detalle de cada
  `EDITADO`), ordena todo en Python y devuelve 20. `get_page` convierte cualquier número fuera de rango en la
  última página, así que `?tab=historial&historial_page=99999` (o ir a la última) lee **la historia entera
  del dispositivo** (hasta 4 × total filas). Con el promedio supuesto (≈1.000 registros por dispositivo) es
  inocuo; con un parador que concentre el 10 % de la red (≈20.000 trazas + ≈5.000-15.000 movimientos +
  correcciones) la última página hidrata ≈25.000-35.000 modelos con JOINs en un request. Crece sin techo:
  ninguna de las cuatro tablas se purga.
- **Causa raíz:** el merge de cuatro fuentes ordenadas se resuelve trayendo filas **completas** desde el
  principio, en vez de decidir primero qué 20 claves caen en la página y recién después hidratar esas 20.
  El docstring del módulo (líneas 25-28) lo admite («como mucho p × tamaño filas de cada fuente»), y el
  presupuesto `dispositivos_auditoria` solo mide consultas (8 fijas), no filas.
- **Solución (mismo orden, mismo texto, mismas 20 líneas por página):** partir el corte en dos fases.
  1. Claves: por fuente, `consulta.values_list(<fecha>, "pk")[:hasta]` (sin `select_related`; con el índice de
     D-DAT-01 queda index-only), mezclar en Python por `(fecha, -fuente, pk)` como hoy y quedarse con las
     claves de `[desde:hasta]`.
  2. Hidratar: por fuente, `consulta.filter(pk__in=ids_de_esa_fuente)` con los `select_related` actuales
     (≤ 20 filas en total) y convertir con los mismos `evento_de_*`, reordenando por la clave de la fase 1.
  Son 4 consultas livianas + ≤ 4 de hidratación (las vacías se saltean): el presupuesto de 8 se mantiene o
  baja. Variante: la fase 1 como un solo `UNION ALL` de `(fecha, fuente, pk)` con `ORDER BY … LIMIT 20 OFFSET
  desde`; las columnas ya son homogéneas, que era la objeción del motivo del presupuesto al `UNION ALL` de
  filas completas.
- **Lo que NO hay que hacer:** recortar el historial a N páginas o cambiar el tamaño de página (cambia lo que
  el usuario ve: sería DECISIÓN CLIENTE); paginar cada fuente por separado con su propio OFFSET (rompe el
  orden global entre fuentes).
- **Tests a agregar:** `programas/tests/test_dispositivos_auditoria.py::AuditoriaPresupuestoTests.test_pagina_profunda_hidrata_solo_la_pagina`
  (con 3 páginas de cada fuente, `CaptureQueriesContext` sobre `feed[40:60]`: ninguna consulta con JOIN trae
  más de 20 filas, y el resultado es idéntico al de la implementación actual; el test existente
  `test_las_paginas_recorren_todo_una_sola_vez` cubre que no se pierdan ni repitan eventos).
- **Verificación:** banco `scripts/perf_mysql/` (MariaDB 10.11, OPTIONS de producción) con la siembra de
  abajo: `python perfil_ruta.py "/dispositivos/<pk_grande>/?tab=historial&historial_page=1"` contra
  `...&historial_page=99999`; hoy la segunda escala con la historia, después las dos quedan iguales.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` §Consultas · «Un feed que
  mezcla varias fuentes ordenadas se pagina en dos fases: primero las claves `(fecha, pk)` de cada fuente,
  sin JOINs, y después se hidratan solo las de la página. Traer `p × tamaño` filas completas por fuente hace
  que la última página cueste toda la historia.» Y en `scripts/perf_budgets.json` (`dispositivos_auditoria`)
  sumar al test la medición de filas de una página profunda, no solo el número de consultas.

#### Aporte del segundo revisor (D1-ERR-04: Pasar a una página profunda del historial lee el historial completo de cada fuente)
_Pasada 1: severidad BAJA · estado PLAUSIBLE · esfuerzo S-M._

- **Ubicación:** `programas/selectors/auditoria_dispositivo.py:370-382` (`FeedAuditoria.__getitem__`); `programas/services/detalle_dispositivo.py:309`
- **Escenario:** `?tab=historial&historial_page=999999` sobre un dispositivo con años de uso. `get_page`
  lleva a la última página, y `__getitem__` lee `consulta[:hasta]` con `hasta ≈ count`: las cuatro
  fuentes enteras, con `select_related`, que después se ordenan en Python. Con muchos miles de
  movimientos y trazas, el pedido se acerca al `read_timeout` de 10 s de ECOM y carga todo en memoria.
  Cualquiera con `dispositivo.ver` lo puede disparar.
- **Causa raíz:** el merge k-way con «primeras p×n filas por fuente» es correcto y barato para las
  primeras páginas, pero crece en forma lineal con la página y no tiene tope. El docstring
  (`:25-28`) lo asume.
- **Solución:** `DECISIÓN CLIENTE: por defecto, limitar la navegación del historial a las primeras N
  páginas (p. ej. 50 = 1000 eventos) y mostrar «Hay más eventos: pedí el export».` Otra opción sin
  cambiar el producto: paginar por cursor (`antes_de=<fecha,fuente,pk>`) filtrando cada fuente por
  `fecha <= cursor`, así cada página lee como mucho n filas por fuente.
- **Tests a agregar:** `programas/tests/test_detalle_dispositivo_perf.py::Historial.test_pagina_profunda_consultas_acotadas` (con `--tag performance`)
- **Verificación:** con el banco MySQL 40k (`scripts/perf_mysql/`), sembrando 20k movimientos en un dispositivo y midiendo la última página.
- **Regla para no repetirlo:** **control mecánico** · `scripts/perf_budgets.json` · presupuesto de filas leídas para la última página del historial, no solo de la primera.

---

### D-PERF-02 · El censo del día lee el histórico entero de estadías del dispositivo
**Severidad:** MEDIA · **Estado:** MEDIDO en banco · **Eje:** PERF · **Origen:** nuevo · **Ola:** 4 · **Esfuerzo:** S
- **Medición en banco (19-nov-2026):** `/dispositivos/1/bitacora/` (censo): 413 / 293 ms en la primera medición y 245 ms en la segunda, 22 consultas, SQL 109 ms. El censo de estadías recorre las 121.041 (`type=ALL`, 78 ms la consulta): hoy cuesta poco, pero escala con la historia. Se mantiene MEDIA.
- **ID de la pasada 1:** D2-PERF-01
- **Ubicación:** `programas/services/ocupacion.py:298-303` (`estadias_alojadas_entre`). Lo consumen `programas/services/censo.py:274` (`censo_por_dia`) y, por esa vía, `programas/services/bitacora_pantalla.py:372` (P10, «Bitácora del turno», en cada carga y para cualquier fecha desde `PISO_FECHA`). Índices de `Estadia`: `programas/models/__init__.py:1276-1281`.
- **Escenario:** el centro de 300 camas tiene 20.000 estadías egresadas y 300 activas. Cada vez que alguien abre P10, el censo del día ejecuta
  `SELECT fecha_ingreso, fecha_egreso FROM programas_estadia WHERE dispositivo_id = ? AND fecha_ingreso < ? AND (fecha_egreso IS NULL OR fecha_egreso >= ?)`.
  El único índice con `dispositivo_id` adelante es `(dispositivo, estado)`, y ninguna de las dos columnas de fecha del predicado está indexada. La base recorre por índice **todas** las estadías que el dispositivo tuvo en su vida (unas 20.000 entradas del índice secundario más 20.000 búsquedas por PK) para devolver unas 300 a 400 filas. Con el supuesto da decenas de ms. Pero crece con cada egreso y nada lo poda: en un parador con rotación diaria el histórico suma cientos de miles de filas por año, y la pantalla de cada turno paga ese recorrido.
- **Causa raíz:** el filtro que acota el resultado («egresó después del inicio del rango, o sigue adentro») cae sobre `fecha_egreso`, que no tiene índice. El de `(dispositivo, estado)` no sirve, porque el filtro no es por estado. El docstring del censo (`censo.py:68-74`) afirma «tres consultas fijas». Lo que es fijo es la cantidad de consultas, no las filas que lee cada una.
- **Solución:** sumar `models.Index(fields=["dispositivo", "fecha_egreso"])` a `Estadia.Meta.indexes`, con su migración (`AddIndex`: solo DDL, sin columna nueva, entra en el contrato de `check_migraciones.py`). Con ese índice el optimizador arma dos rangos, `(d, NULL)` para las activas y `(d, [desde, +inf))` para las egresadas en el rango, y lee solo lo que devuelve. La consulta y su resultado no cambian, así que la lógica queda igual.
- **Lo que NO hay que hacer:** indexar `(dispositivo, fecha_ingreso)`. `fecha_ingreso < hasta` también abarca todo el histórico. Tampoco reescribir el filtro como `estado=ACTIVA OR (estado=EGRESADA AND fecha_egreso >= desde)` sin el índice nuevo: la rama de las egresadas sigue recorriendo todas.
- **Tests a agregar:** `programas/tests/test_dispositivos_censo.py::CensoIndiceTests.test_estadia_tiene_indice_dispositivo_fecha_egreso`, un ratchet del índice como el de `IndiceDeLaDerivacionTests`. El presupuesto `dispositivos_censo` no cambia.
- **Verificación:** en el banco `scripts/perf_mysql/` (MariaDB 10.11), con la siembra de abajo, correr `EXPLAIN ANALYZE` (o `ANALYZE FORMAT=JSON` en MariaDB) de la consulta. Antes: `key` = el índice de `dispositivo`, `rows` ≈ 20.000 y `r_rows` ≈ 20.000. Después: `type=range` sobre el índice nuevo y `rows` ≈ 400. Además, `perfil_ruta.py` sobre `/dispositivos/<pk>/bitacora/` antes y después.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas activas · «Consultas "alojadas/vigentes en un rango" sobre una tabla histórica (`Estadia`, `ReservaPlaza`, `MovimientoEstadia`): el predicado que acota el resultado (`fecha_egreso >= desde`, `hasta >= momento`) tiene que estar en un índice detrás de la igualdad. Una cantidad fija de consultas no dice cuántas filas lee cada una.»

---

### D-LIM-04 · El selector de auditoría decide la regla de privacidad del relevamiento y arma la presentación
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 2 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D1-LIM-11
- **Ubicación:** `programas/selectors/auditoria_dispositivo.py:353-357`: `ve_asignacion = edificio_id in visibles
  or asignado_a_id == usuario_id`. `programas/services/detalle_dispositivo.py:639-646`: la misma regla («propios o
  coordinados») escrita otra vez para el registro fotográfico. Además, `auditoria_dispositivo.py:51-99` (títulos y
  tonos), `:182-302` (cuatro `evento_de_*` que arman frases) y `:209` (el enmascarado de la persona, ver D-LIM-06).
- **Escenario:** el comentario del propio selector (`:315-317`) dice «el selector no evalúa capacidades ni alcance,
  solo decide qué texto arma». Pero sí decide una regla de alcance: «el agente asignado ve su propia asignación».
  Si `inspecciones.ve_la_asignacion` cambia (por ejemplo, el coordinador deja de ver lo asignado a otro equipo), hay
  que encontrar y corregir dos copias que no la nombran. Una que quede vieja muestra el nombre del agente a la
  institución relevada.
- **Causa raíz:** el feed mezcla tres trabajos: leer (cuatro querysets), decidir quién ve qué y redactar. Por eso
  quedó en `selectors/` aunque dos tercios sean reglas y presentación.
- **Solución:** (1) un único `ve_asignacion(inspeccion, *, edificios_coordinados, usuario_id)` en
  `services/inspecciones.py`, usado por el feed y por `registro_de_relevamientos`. (2) El selector se queda con
  `FeedAuditoria` devolviendo `(fuente, fila)`, sin convertir. Los `evento_de_*`, `TITULOS_TRAZA` y `_TONOS_TRAZA`
  pasan a `services/historial_dispositivo.py`, que convierte **solo la página**. Hoy `__getitem__` (`:377-380`)
  convierte las `hasta` filas de cada fuente antes de ordenar, y para ordenar alcanza con la fecha de la fila
  (`creado_en`/`momento`/`creado`). El orden y el texto de cada línea no cambian.
- **Lo que NO hay que hacer:** pasarle `usuario` al selector para que llame a `puede()`: eso mete RBAC en la capa
  de lectura.
- **Tests a agregar:** `programas/tests/test_dispositivos_detalle.py::HistorialTests.test_agente_ve_su_asignacion_en_historial_y_registro`
  (las dos superficies, con el mismo usuario).
- **Verificación:** los presupuestos de consultas del detalle no cambian (`scripts/perf_budgets.json`, presupuesto
  de `dispositivos_detalle`). Probar con mutación: romper `ve_asignacion` tiene que poner rojas las dos superficies.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md`, tabla de helpers
  canónicos: «¿Quién ve el agente de un relevamiento en curso? → `inspecciones.ve_asignacion`. Un `asignado_a_id ==`
  fuera de ese módulo es duplicado».

---

### D-LIM-05 · El historial borra el id del ciudadano con una regex sobre un texto que escribe otro servicio
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** D1-LIM-12
- **Ubicación:** `programas/selectors/auditoria_dispositivo.py:102` (`_CIUDADANO_EN_TRAZA`) y `:186-188`. El que
  escribe es `programas/services/estadias.py:833` (`de_quien=f"ciudadano {ciudadano.pk}"`) y `:862-866`.
- **Escenario:** el mismo archivo dice, en `evento_de_inspeccion` (`:276-278`): «recortar depende del formato con
  el que se escribió y se rompe en silencio cuando ese formato cambia». Y dos funciones antes hace justo eso. Si
  `_crear_reserva` cambia el separador o el orden (por ejemplo, `"· persona 123"`), la regex deja de coincidir y el
  id de la persona aparece en el historial institucional sin que falle nada.
- **Causa raíz:** la traza guarda texto libre y el lector depende de su forma. Productor y consumidor viven en
  módulos distintos y no tienen contrato.
- **Solución:** sin tocar datos guardados: en `services/estadias.py`, al lado de `_crear_reserva`, una constante de
  formato y `detalle_de_reserva_sin_persona(detalle)`, que el selector importa. Un test de ida y vuelta escribe
  con el productor real y limpia con el consumidor. Las filas viejas siguen limpiándose igual.
- **Lo que NO hay que hacer:** dejar de escribir el id en la traza nueva sin migrar la lectura: las filas
  históricas lo traen y se seguirían mostrando.
- **Tests a agregar:** `programas/tests/test_dispositivos_detalle.py::HistorialTests.test_reserva_nunca_muestra_el_id_del_ciudadano`
  (con `reservar_plaza` real, no con una traza escrita a mano).
- **Verificación:** probar con mutación: cambiar el formato en `_crear_reserva` tiene que poner rojo el test.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md`: «Si un lector parsea
  el texto de una traza, el formato y el parser viven en el mismo módulo, con un test de ida y vuelta».

---

### D-LIM-06 · El enmascarado de la persona («Persona alojada») se resuelve en cinco lugares con dos redacciones
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** D1-LIM-05
- **Ubicación:** `programas/views/dispositivos_legajo.py:447-455`, `:589-591`, `:1109-1111` y `:1415` («La persona
  alojada»). `programas/selectors/auditoria_dispositivo.py:209`.
- **Escenario:** el enmascarado protege un dato personal: sin `ciudadano.ver`, el nombre no sale. Hoy son cinco
  ternarios independientes. En `:1110` se vuelve a llamar a `puede()` en lugar de usar el valor ya resuelto. Alguien
  que agregue una sexta superficie (el aviso de cambio de plaza, `:1655`) tiene que acordarse de copiarlo. Si se
  olvida, filtra el nombre a quien no lo puede ver. `persona_del_menu` (`:448-455`) además arma en la vista una frase
  con sector, código, fecha y número de estadía.
- **Causa raíz:** la regla de privacidad no tiene dueño. Se trata como un detalle de presentación de cada pantalla.
- **Solución:** en `services/estadias.py` (o `nombre_plaza.py`), `rotulo_de_persona(ciudadano, puede_ver, *,
  inicio_de_frase=False)` devuelve el nombre, «Persona alojada» o «La persona alojada». Al lado,
  `rotulo_del_menu(estadia, puede_ver)`. Las cinco llamadas pasan a usarlos, con el mismo texto que hoy.
- **Tests a agregar:** `programas/tests/test_dispositivos_detalle.py::RotuloPersonaTests.test_sin_ciudadano_ver_no_sale_el_nombre_en_ninguna_superficie`.
- **Verificación:** `grep -rn "Persona alojada" programas --include=*.py | grep -v tests` tiene que dar un solo lugar.
- **Regla para no repetirlo:** **control mecánico** · `test_arquitectura.py` · el literal `"Persona alojada"`
  aparece una sola vez fuera de tests.

---

### D-LIM-07 · `puede_administrar_usuarios_dispositivos` es una regla paralela a `programas_administrables_usuarios`
**Severidad:** MEDIA · **Estado:** PLAUSIBLE · **Eje:** LIM · **Origen:** nuevo · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** D3-LIM-05
- **No hacer:** globalizar `programa.configurar` (descartado en octubre, `README.md` §8.1: Dispositivos la evalúa con programa).
- **Ubicación:** `services/equipo_dispositivo.py:49-61`; canónico: `users/selectors/roles.py` (`programas_administrables_usuarios`).
- **Escenario:** el docstring dice «la misma definición» que el ABM de usuarios, pero usa `rbac.puede` y no `es_admin_global`. Un usuario que el ABM de Usuarios trata como admin global podría no ver la acción «crear agente» en el equipo, o al revés. No se probó con un rol real (por eso PLAUSIBLE).
- **Causa raíz:** se reescribió la condición en lugar de llamar al selector canónico.
- **Solución:** reemplazar el cuerpo por `return programa in programas_administrables_usuarios(user)` (o el equivalente con `exists()`). Antes, escribir un test que compare las dos funciones sobre los roles del seed. Si dan distinto, la diferencia la decide el PM: DECISIÓN CLIENTE, default = la del ABM de Usuarios. (Los códigos de capacidad literales ya están en E-LIM-27 y no se repiten acá.)
- **Lo que NO hay que hacer:** no globalizar `programa.configurar` (descartado en §8).
- **Tests a agregar:** un test parametrizado por rol del seed: `puede_administrar_usuarios_dispositivos(u, p) == (p in programas_administrables_usuarios(u))`.
- **Verificación:** el test pasa antes del cambio (y entonces la refactorización es segura) o falla y se escala.
- **Regla para no repetirlo:** CLAUDE.md · sección «Autorización» · «Una regla de "quién administra X" se pide al selector de `users/selectors/roles.py`; no se reescribe con `rbac.puede` en otro módulo.»

---

### D-LIM-08 · La consulta «pares usuario×rol sumables» está escrita tres veces y el contrato `"u:r"` vive en tres archivos
**Severidad:** INFO · **Estado:** MEDIDO en banco · **Eje:** LIM · **Origen:** fusión de D3-LIM-04 + D3-PERF-02 · **Ola:** 4 · **Esfuerzo:** S-M
- **Medición en banco (19-nov-2026):** `/dispositivos/nuevo/` con 1.000 usuarios: 483 / 449 ms, 10 consultas, SQL 110 ms. No pasa el umbral de 500 ms de la ficha: **baja a INFO** (el costo de rendimiento; la deduplicación de la consulta sigue siendo limpieza de código).
- **ID de la pasada 1:** D3-LIM-04 + D3-PERF-02 (**hallado por 2 revisores**)
- **Hallado por 2 revisores (sube de peso):** D3-LIM-04 (calidad: la consulta «pares usuario×rol sumables» escrita tres veces y el contrato `"u:r"` en tres archivos) y D3-PERF-02 (rendimiento: el alta de un dispositivo arma «Responsables» con todos los pares persona × rol del programa, sin tope). Mismo selector: se unifica y se acota a la vez. **Se mide en la pasada 2** (1.000 usuarios con roles de Dispositivos y `perfil_ruta.py` sobre el alta; secciones 8.a y 8.c).
- **Ubicación:** `services/equipo_dispositivo.py:109-120` (`_exigir_pares_sumables`), `:307-317` (`pares_persona_rol`), `selectors/equipo_sugeridas.py:33-45` (`consulta_de_pares`). Contrato `"<usuario>:<rol>"`: `services/equipo_dispositivo.py:333`, `selectors/equipo_sugeridas.py:65`, `forms_dispositivos.py:796`.
- **Escenario:** si se agrega un filtro (por ejemplo excluir usuarios inactivos o un rol nuevo), el selector que alimenta el buscador ofrece un par que el servicio después rechaza, o el servicio acepta uno que el buscador nunca muestra. Si alguien cambia el separador en un lugar, el form deja de parsear lo que manda el front.
- **Causa raíz:** no hay un selector dueño del «universo sumable» ni un par `codificar/decodificar` del valor.
- **Solución:** un selector único `pares_sumables(dispositivo)` en `selectors/equipo_sugeridas.py`, que usen el servicio (para validar) y el buscador (para listar). Agregar `codificar_par(u, r)` y `decodificar_par(texto)` junto a él, y que `clean_persona_rol` y el servicio los usen. Así `forms_dispositivos.py:787-814` deja de repetir las reglas del servicio: valida el formato y el servicio decide.
- **Lo que NO hay que hacer:** no cambiar el formato `"u:r"` (lo manda el front).
- **Tests a agregar:** un test que verifique que todo par que lista el buscador pasa `_exigir_pares_sumables`, y que uno fuera del universo no pasa.
- **Verificación:** `grep -n "split(\":\")" programas/` solo en `decodificar_par`.
- **Regla para no repetirlo:** skill · `.claude/skills/auditoria/rubricas/codigo-limpio.md` · «Un universo de selección que valida un servicio y lista un buscador sale de un único selector.»

#### Aporte del segundo revisor (D3-PERF-02: El alta de un dispositivo arma «Responsables» con todos los pares persona × rol del programa, sin tope)
_Pasada 1: severidad INFO · estado PLAUSIBLE · esfuerzo S-M._

- **Ubicación:** `programas/services/equipo_dispositivo.py:295-339` (`pares_persona_rol`, sin límite), consumido por `programas/forms.py:1126-1138` (`_agregar_responsables`: una opción por par y, por cada una, un diccionario de contacto embebido en el widget).
- **Escenario:** cada usuario con un rol activo de Dispositivos (el personal de todas las instituciones, no solo los admins) aporta una fila por rol. Con 200 instituciones × 5 personas son ~1.000 opciones con su JSON de contacto en cada `GET` y cada `POST` del alta. La consulta es una sola y liviana (`select_related("user", "user__profile", "group")`, sin N+1); lo que crece es el HTML y el render. El Equipo ya resolvió lo mismo con sugerencias acotadas (`selectors/equipo_sugeridas.py`, tope 10); el alta no.
- **Causa raíz:** el buscador del alta (Cambio 450) filtra en el navegador sobre la lista completa en vez de pedir sugerencias al servidor.
- **Solución (solo si la medición lo justifica):** que el campo «Responsables» del alta use el mismo selector de sugerencias que el Equipo (`consulta_de_pares`, sin dispositivo) y valide lo elegido con `_exigir_pares_sumables`, que ya mira solo los pares enviados. Si la pieza visual del buscador múltiple tiene que cambiar: `DECISIÓN CLIENTE: mantener el buscador múltiple actual alimentado por sugerencias del servidor`.
- **Tests a agregar:** `programas/tests/test_dispositivos_equipo.py::AltaResponsablesTests.test_alta_no_carga_todo_el_padron` (`assertNumQueries` y tamaño de `choices` acotado) y la entrada `dispositivos_alta` en `scripts/perf_budgets.json`.
- **Verificación:** en el banco, sembrar 1.000 usuarios con roles de Dispositivos y medir con `perfil_ruta.py` el `GET` del alta: tiempo de render y bytes. Se reporta solo si pasa de ~500 ms o ~1 MB.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas activas · «Un `<select>` o buscador que se llena con usuarios, personas o pares usuario × rol sale de un endpoint de sugerencias con tope, no de la lista completa embebida en el formulario.»

---

### D-LIM-09 · La vista de P21 arma ~330 líneas de view-model y muta instancias del modelo con 18 atributos sueltos
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 5 · **Esfuerzo:** M
- **ID de la pasada 1:** D4-LIM-04
- **Regla transversal «lógica de dominio en vistas» (R-1):** ~330 líneas de view-model y mutación de instancias con 18 atributos sueltos. Cruces: Becas ola 7 y Emergencia E-LIM-01. Va **después** de la ficha de Ola 0 (`ve_la_asignacion_en_lote`), porque comparte las líneas `:301-306` y `:348-356`.
- **Ubicación:** `programas/views/dispositivos_relevamientos.py:184-259` (tarjetas), `:269-390`
  (`get_context_data`, 120 líneas con una función anidada), `:392-423`, `:425-499` (`_preparar_fila`)
- **Escenario:** `_preparar_fila` cuelga de cada `InspeccionEdificio` `situacion`, `situacion_texto`,
  `con_acciones`, `vence_relativo`, `menu_id`, `menu_etiqueta`, `accion_visible`, `acciones_menu`, `url_informe`,
  `url_revisar`, `gestionable`, `motivo_reasignar`, `motivo_cancelar`, `url_reasignar`, `url_cancelar`, y el
  bucle de `:353-356` agrega `agente_visible`. En `:406-413` la solapa «Sin relevar» hace lo mismo sobre
  `Edificio` (`relevamiento_en_curso`, `asignado_a` como **texto**, `url_asignar`). El contrato con
  `relevamientos/list.html` y con `_tarjeta_de_relevamiento` es implícito: renombrar un atributo rompe el template
  sin error (Django devuelve vacío), y `_tarjeta_de_relevamiento` depende de que `_preparar_fila` haya corrido antes.
- **Causa raíz:** no existe una capa de presentación para P21; la vista hace de presenter. `CLAUDE.md` pide vistas
  que solo orquestan.
- **Solución:** `programas/services/listado_relevamientos.py` con un `@dataclass(frozen=True) FilaRelevamiento`
  (los 18 campos tipados + `tarjeta`) y `FilaEdificioSinRelevar`, construidos por `filas_de_relevamientos(user,
  relevamientos, hoy, en_alcance, vista, solapa)` y `filas_sin_relevar(...)`. La vista pagina, llama y pone en
  contexto. El template cambia `r.edificio.nombre` → `r.relevamiento.edificio.nombre` donde lea del modelo (o el
  dataclass expone `edificio`); HTML resultante idéntico (lo protegen los snapshots/tests de listado).
- **Lo que NO hay que hacer:** mover las mutaciones tal cual a un servicio: el problema es la forma implícita, no
  solo el archivo.
- **Tests a agregar:** `programas/tests/test_listado_relevamientos.py::FilaRelevamientoTests` (unitarios sin request,
  una fila por estado); los de `test_dispositivos_relevamientos_listado.py` quedan iguales.
- **Verificación:** HTML de P21 igual antes y después (diff de la respuesta en un test con datos fijos); presupuesto de
  queries de P21 sin cambios.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-auditor.md`, sección de capas · «Una vista que
  asigna atributos nuevos a instancias del modelo (`obj.algo = ...` sobre filas de un queryset) para el template es
  un presenter escondido: pedí un dataclass en `services/` o `selectors/`».

---

### D-LIM-10 · La vista del detalle arma a mano cada fila de estadías, y la regla «se puede mover» está triplicada
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 5 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D1-LIM-06
- **Regla transversal «lógica de dominio en vistas» (R-1):** la vista del detalle arma a mano cada fila de estadías y la regla «se puede mover» está triplicada.
- **Ubicación:** `programas/views/dispositivos_legajo.py:446-469` (bucle por estadía: rótulo, rótulo del menú,
  `url_ver`, `asigna_plaza`, `url_cambiar`, `motivo_cambiar`, `url_egresar`, `url_modal_egreso`). La regla «activa
  y (con plaza o el tipo maneja plazas)» aparece en `:461`, `:597` y `:1592-1596`.
- **Escenario:** P4 (fila y modal) y P7 deciden por separado si se ofrece «Cambiar/Asignar plaza». Las tres copias
  ya difieren: `:461` mira `estadia.activa`, `:597` lo mira 5 líneas antes (`:592`) y `:1594` lo combina con la
  capacidad en un solo `and`. Un cambio en la regla (por ejemplo, no asignar plaza a una estadía de Emergencia
  todavía en ingreso) obliga a tocar tres lugares. Además, `estadia.url_egresar` (`:468`) se calcula con `reverse`
  por fila, pero el template solo lo usa como bandera (`detail.html:277`): navega a `url_modal_egreso`.
- **Causa raíz:** el servicio `estadias_del_dispositivo` (`detalle_dispositivo.py:205-242`) ya decora cada estadía
  con `estado_texto` y `tono`, pero no con sus acciones. Las acciones dependen de permisos, así que se resolvieron
  en la vista.
- **Solución:** en `services/estadias.py`, `puede_mover(estadia, *, con_plazas) -> bool` (activa y (plaza o
  con_plazas)), usada en las tres. Y `acciones_de_estadia(estadia, dispositivo, *, puede_cambiar, puede_egresar,
  puede_ver, con_plazas, hay_libres) -> dict`, que devuelve las URLs y el motivo. La vista le pasa los permisos ya
  resueltos y queda en un `for` de una línea. `url_egresar` por fila se reemplaza por un booleano `egresable`, sin
  cambio visible.
- **Lo que NO hay que hacer:** llevar `puede_operar_dispositivo` adentro del servicio por fila: hoy cada permiso se
  resuelve una vez por pantalla y así tiene que seguir.
- **Tests a agregar:** `programas/tests/test_dispositivos_estadia_detalle.py::PuedeMoverTests` (las cuatro
  combinaciones de activa, plaza y con_plazas).
- **Verificación:** `test_dispositivos_detalle` y `test_dispositivos_estadia_detalle` pasan sin cambios, y el
  presupuesto de consultas del detalle queda igual.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md`, «Qué escalar»: «Una vista que recorre filas para
  colgarles URLs y motivos decide presentación por fila: eso es de un servicio de acciones».

---

### D-LIM-11 · La regla «puede dar de alta = `dispositivo.crear` + alcance de admin» está escrita en cuatro lugares
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 5 · **Esfuerzo:** S
- **ID de la pasada 1:** D1-LIM-04
- **Cruce con Emergencia:** la regla «puede dar de alta» de cuatro lugares incluye la capacidad redeclarada de E-LIM-27.
- **Ubicación:** `programas/mixins_dispositivos.py:100` (`DispositivoAltaPermissionMixin`, junto con la capacidad
  del mixin base), `programas/views/dispositivos_legajo.py:209-211` (botón del listado), `:389-391`
  (`DispositivoFormularioTipoView`) y `programas/services/dispositivos.py:387` (variante con `dispositivo.editar`
  para el envío desde el alta).
- **Escenario:** el docstring del mixin (`:84-97`) explica por qué el alta exige alcance total. Esa razón vive en un
  solo lugar, pero la regla se copió tres veces más con `and` a mano. Si se afloja o se endurece (por ejemplo,
  permitir el alta a un coordinador territorial), el listado ofrece un botón que da 403 o la sección del formulario
  del tipo responde 403 dentro de un alta permitida.
- **Causa raíz:** no hay una función con nombre para la regla, así que cada llamador la vuelve a armar.
- **Solución:** `puede_dar_de_alta_dispositivos(user)` en `services/dispositivos.py`, que devuelve
  `puede_en_programa_dispositivos(user, "dispositivo.crear") and puede_configurar_dispositivos(user)`. La usan el
  mixin, el listado y `DispositivoFormularioTipoView`. `puede_enviar_desde_formulario` llama a
  `puede_configurar_dispositivos` igual que hoy, pero con un comentario que remite al helper.
- **Tests a agregar:** `programas/tests/test_dispositivos_legajo.py::AltaTests.test_boton_mixin_y_seccion_coinciden`.
- **Verificación:** probar con mutación: invertir el helper tiene que poner rojos los tres gates.
- **Regla para no repetirlo:** **control mecánico** · `test_arquitectura.py` · ratchet: en `programas/views/`,
  `"dispositivo.crear"` aparece solo como `capacidad_requerida` (hoy hay dos usos inline).

---

### D-LIM-12 · El gate del asistente reimplementa `puede_ingresar_persona`, que se declara «única fuente de la regla»
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 5 · **Esfuerzo:** S
- **ID de la pasada 1:** D2-LIM-09
- **Cruce con Emergencia:** el gate del asistente reimplementa `puede_ingresar_persona`, igual que las vistas de la guardia reescriben reglas del servicio (E-LIM-01).
- **Ubicación:** `programas/views/dispositivos_ingreso.py:98-113` (`dispatch`: `puede_en_programa_dispositivos(ADMITIR)` + `dispositivo_operable_o_404(ADMITIR)` + `puede(CAP_VER_CIUDADANO)`); `programas/services/estadias.py:133-141` (docstring: «la vista del asistente la usa de gate»); `programas/views/dispositivos_ingreso.py:325-330` (docstring que afirma que el gate `puede_ingresar_persona` ya corrió)
- **Escenario:** hoy son equivalentes salvo el reparto 403/404. Si mañana `puede_ingresar_persona` suma una condición (p. ej. `dispositivo.estado == ACTIVO` o una capacidad nueva), el botón «Ingresar persona» del detalle se esconde pero el asistente sigue abierto por URL —la divergencia exacta que la función existe para evitar—, y dos docstrings afirman lo contrario de lo que hace el código.
- **Causa raíz:** el `dispatch` necesitaba distinguir 403 de 404 y se escribió a mano en lugar de componer.
- **Solución:** mantener el reparto 403/404 y terminar el `dispatch` con `if not puede_ingresar_persona(request.user, self.dispositivo): raise PermissionDenied`, eliminando la línea `puede(request.user, CAP_VER_CIUDADANO)` duplicada. Corregir el docstring de `_form_buscar`.
- **Lo que NO hay que hacer:** reemplazar todo el `dispatch` por `puede_ingresar_persona`: se perdería el 404 indistinguible para dispositivos ajenos.
- **Tests a agregar:** `programas/tests/test_ingreso_asistente.py::GateTests.test_gate_es_puede_ingresar_persona` (mock que la hace devolver `False` → 403).
- **Verificación:** mutación: cambiar `puede_ingresar_persona` a `False` debe poner rojo el test de la vista.
- **Regla para no repetirlo:** **skill** · `.claude/skills/seguridad-django/` · «Si existe `puede_<accion>()` documentada como fuente única, la vista que gatea esa acción la llama; reescribir sus capacidades en `dispatch` es divergencia latente».

---

### D-LIM-13 · Tres vistas de Dispositivos reescriben `ajax_utils.errores_del_servicio`/`rechazar`
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** fusión de D3-LIM-02 + D4-LIM-08 + D1-LIM-07 · **Ola:** 6 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D3-LIM-02 + D4-LIM-08 + D1-LIM-07 (**hallado por 3 revisores**)
- **Hallado por 3 revisores (sube de peso):** D3-LIM-02 (tres vistas del equipo y la bitácora reescriben `ajax_utils.errores_del_servicio`/`rechazar`), D4-LIM-08 (las cinco vistas POST de P21 repiten el mismo `try/except`, y una traduce distinto) y D1-LIM-07 (la traducción de errores del servicio al JSON del modal está escrita tres veces en el legajo, y `CambiarPlaza` usa un privado). Un solo traductor por superficie.
- **Cruce con otros capítulos:** el mismo defecto está en Emergencia (E-LIM-12, E-LIM-13, E-LIM-14) y en Becas (`responder_form`, B-LIM-65). El traductor tiene que vivir en `core/` (o `programas/respuestas.py`) y servir a los tres: una sola ficha de fondo coordinada, no tres.
- **Contrato de la app móvil:** el cuerpo de los errores de la API de campo (`detail`, `non_field_errors`) no se toca sin test de contrato y release coordinado con Chaco-mobile.
- **Ubicación:** `views/dispositivos_bitacora.py:163-198` (`_errores_del_servicio`, `_rechazar`, `_prohibido`); copias en `views/dispositivos_legajo.py:752` (`errores_por_campo`), `:1208-1235`, `:1475-1492`, y `views/dispositivos_relevamientos.py:619-640`. Canónico: `views/ajax_utils.py:45-75`. Además `_BitacoraPostView.post` (`dispositivos_bitacora.py:214-229`) repite el cascarón POST de `_EquipoAccionView.post` (`dispositivos_equipo.py`).
- **Escenario:** cuando cambia el contrato de error AJAX (por ejemplo `primerCampo` o el status 409), `ajax_utils` se actualiza y estas cuatro copias responden con el formato viejo. El modal muestra el error en otro lugar o no lo muestra.
- **Causa raíz:** `ajax_utils` es posterior a estas vistas, o no se descubrió. Nadie lo exige mecánicamente.
- **Solución:** borrar las copias e importar `errores_del_servicio`, `rechazar`, `ajax_errors` y `is_ajax` de `ajax_utils`. Si `_prohibido` difiere solo en el status, agregar `rechazar(..., estado=403)`. Extraer el cascarón POST (resolver dispositivo → exigir permiso → llamar al servicio → `ajax_redirect` o `rechazar`) a un mixin `ServicioPostMixin` en `ajax_utils`, que usen bitácora y equipo. Antes de borrar, comparar cada copia con la canónica: si alguna devuelve otro formato, esa diferencia se conserva como parámetro.
- **Lo que NO hay que hacer:** no promover nada a `components/`; no cambiar el JSON que lee `_ajax_js.html`.
- **Tests a agregar:** un test por vista que verifique que un `ValidationError` del servicio produce exactamente el mismo JSON (claves `errors`, `__all__`, status) antes y después.
- **Verificación:** `grep -rn "def _errores_del_servicio\|def _rechazar\|def errores_por_campo" programas/views` da 0.
- **Regla para no repetirlo:** control mecánico · `test_arquitectura.py` · «Ninguna vista define `_errores_del_servicio`, `_rechazar` ni `errores_por_campo`; se importan de `views/ajax_utils.py`.»

#### Aporte del segundo revisor (D4-LIM-08: Las vistas POST de P21 repiten el mismo try/except cinco veces y una traduce los errores distinto)
_Pasada 1: severidad BAJA · estado CONFIRMADO (lectura) · esfuerzo S._

- **Ubicación:** `programas/views/dispositivos_relevamientos.py:664-670`, `:691-704`, `:734-748`, `:764-770`, `:779-785`;
  divergencia en `:669`
- **Escenario:** cuatro vistas usan `_errores_del_servicio(error, form)` y `RelevamientoRevisarView` usa
  `{"__all__": error.messages}`: un `ValidationError` con clave de campo que sume `marcar_revisado` se aplanaría solo
  ahí. `RelevamientoAsignarView` y `DispositivoRelevamientoAsignarView` tienen el mismo bloque `crear_inspeccion(...)`
  palabra por palabra salvo `tipo`. La API ya resolvió esto con un `_ejecutar` (`api/views_inspecciones.py:121`).
- **Causa raíz:** cada vista se agregó copiando la anterior.
- **Solución:** en `_RelevamientoAccionView`, `_ejecutar(operacion, form=None, ok=...)` que corre la lambda y traduce
  `PermissionDenied` → `_prohibido` y `ValidationError` → `_rechazar(self._errores_del_servicio(error, form))`
  (con `form=None` cae en `__all__`, que es lo que hace Revisar hoy). Las dos de asignar comparten `_crear(edificio,
  datos, tipo)`.
- **Tests a agregar:** ninguno; los de acciones de P21 cubren los tres caminos.
- **Verificación:** suite de P21 igual.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-auditor.md` · «En una familia de vistas POST con
  base común, la traducción de excepciones del servicio vive en la base, una vez».

#### Aporte del segundo revisor (D1-LIM-07: La traducción de errores del servicio al JSON del modal está escrita tres veces, y `CambiarPlaza` usa privados de `EgresarView`)
_Pasada 1: severidad MEDIA · estado CONFIRMADO (lectura) · esfuerzo S._

- **Ubicación:** `programas/views/dispositivos_legajo.py:745-757` (`errores_por_campo`), `:1207-1225`
  (`_PlazaAccionView._errores_del_servicio`, la misma función con `alias`) y `:1474-1482` (wrapper de una línea).
  `_rechazar` está duplicado en `:1227-1234` y `:1484-1491`. `EstadiaCambiarPlazaView` llama a
  `EstadiaEgresarView._rechazar` y `_errores_del_servicio` (`:1639`, `:1652`), dos privados de otra clase. El cierre
  «si es AJAX `ajax_redirect`, si no `messages.success` + `redirect`» se repite en `:788-791`, `:1198-1201`,
  `:1417-1420` y `:1656-1659`.
- **Escenario:** el contrato JSON del arquetipo Modal (`{ok, errors}` con 400) lo define cada clase. Un cambio de
  contrato, como agregar `code` al error, se aplica en una y queda viejo en las otras dos. El acoplamiento
  `CambiarPlaza → EgresarView._rechazar` hace que refactorizar el egreso rompa el cambio de plaza.
- **Causa raíz:** el helper nació local en cada vista y nadie lo subió a `ajax_utils`.
- **Solución:** en `programas/views/ajax_utils.py`: `errores_por_campo(error, campos, alias=None)` (la versión con
  alias, que es la general), `rechazar_modal(request, errores, volver)` y `responder_exito(request, volver,
  mensaje)`. Las cuatro clases las usan, y se borran `_errores_del_servicio` y `_rechazar`. Las respuestas no
  cambian byte a byte.
- **Tests a agregar:** `programas/tests/test_ajax_utils.py::ErroresPorCampoTests` (alias, clave desconocida que va
  a `__all__`, error sin dict).
- **Verificación:** `test_dispositivos_plazas_acciones`, `test_dispositivos_egreso` y `test_dispositivos_legajo`
  pasan sin cambios.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md`, tabla de helpers canónicos: «Responder error u
  éxito a un modal `data-ajax` → `ajax_utils.rechazar_modal` / `responder_exito`».

---

### D-LIM-14 · El ciclo de vida de la estadía repite a mano su máquina de estados en cuatro servicios
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** (complementa E-LIM-15, que cubre solo la secuencia de candados del ingreso) · **Ola:** 7 · **Esfuerzo:** M
- **ID de la pasada 1:** D2-LIM-02
- **Ubicación:** `programas/services/estadias.py:457-460`, `571-574`, `677-680`, `757-760`, `814-816` (momento «no futuro» ×5); `567-569`, `687-689`, `764-766` (releer con `FOR UPDATE` + «ya está cerrada» ×3); `575-580`, `692-693`, `769-770` (momento ≥ último movimiento ×3); `520-536`, `620-639`, `710-728`, `777-793` (movimiento + bitácora + traza ×4); `646-729` vs `732-794` (`cambiar_plaza` y `asignar_plaza`, ~80 % del cuerpo idéntico)
- **Escenario:** la estadía tiene dos estados (`ACTIVA`, `EGRESADA`) y tres invariantes temporales (no futuro, no antes del ingreso, no antes del último movimiento), pero ninguna pieza los nombra: cada servicio los reescribe con su propio texto. Un cambio de regla —p. ej. tolerancia de reloj para «futuro», o un nuevo estado `SUSPENDIDA`— hay que hacerlo en cinco lugares y nada avisa si uno queda atrás. `cambiar_plaza` y `asignar_plaza` comparten permiso, momento, orden plaza→estadía, chequeo de activa, `ultimo_momento`, `_exigir_plaza_libre(momento=ahora)`, `_exigir_plaza_libre_desde`, `save(update_fields=["plaza", "modificado"])`, movimiento, bitácora y traza; difieren solo en la precondición de origen, la obligatoriedad del motivo, el tipo de movimiento y el texto.
- **Causa raíz:** el estado de la estadía es un `CharField` con chequeos sueltos; la tríada «registrar movimiento → anotar en bitácora → trazar» es un hecho de dominio único que nunca se extrajo. El docstring de `asignar_plaza` (736-742) rechaza *fusionar* las funciones públicas, y tiene razón, pero eso no impide compartir el núcleo.
- **Solución (preserva mensajes y orden de candados):**
  ```python
  def _momento_valido(momento, ahora, *, campo, que):           # «El {que} no puede ser futuro.»
  def _bloquear_estadia_activa(estadia) -> Estadia:             # select_for_update + "ya está cerrada"
  def _exigir_no_antes_del_ultimo(estadia, momento, *, campo, mensaje)
  def _registrar_hecho(estadia, usuario, *, tipo, momento, accion_traza, detalle, **mov) -> MovimientoEstadia
      # registrar_movimiento + anotar_en_bitacora + _trazar, en ese orden
  def _mover_a_plaza(estadia, plaza, usuario, *, momento, ahora) -> tuple[Estadia, Plaza, Plaza | None]
      # bloquear_plaza → _bloquear_estadia_activa → exigir libre ahora y desde → save(plaza)
  ```
  `cambiar_plaza` y `asignar_plaza` quedan como políticas de ~20 líneas: validan su precondición propia (origen distinto / origen vacío, motivo obligatorio / opcional, `maneja_plazas`) y llaman a `_mover_a_plaza` + `_registrar_hecho`. Los textos exactos se pasan como argumentos para no alterar ningún mensaje existente. Opcional en la misma ola: `Estadia.TRANSICIONES = {ACTIVA: {EGRESADA}}` y `Estadia.exigir_transicion(nuevo)` en el modelo.
- **Lo que NO hay que hacer:** unificar `cambiar_plaza` y `asignar_plaza` en una sola función pública con `origen=None` (lo que el docstring ya descartó); mover `_bloquear_estadia_activa` antes de `bloquear_plaza` (invierte el orden plaza→estadía y abre un deadlock).
- **Tests a agregar:** `programas/tests/test_estadias_ciclo.py::MomentoTests.test_mismo_mensaje_por_servicio` (parametrizado sobre los 5 servicios); los de orden de candados existentes deben seguir verdes sin tocarlos.
- **Verificación:** `OrdenDeLosCandadosTests` y `test_dispositivos_concurrencia` verdes; diff de mensajes = vacío (grep de los literales antes/después).
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` · «En `programas/services/estadias*`, toda transición de la estadía pasa por `_bloquear_estadia_activa` y todo hecho por `_registrar_hecho`; un `registrar_movimiento(` seguido de `anotar_en_bitacora(` escrito a mano fuera de ese helper es duplicado».

---

### D-LIM-15 · Tres definiciones de «plaza tomada» repartidas en cinco lugares
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** relacionado con E-LIM-37 (cama libre de Emergencia), distinto alcance · **Ola:** 7 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D2-LIM-06
- **Cruce con Emergencia:** la regla de «cama libre» y el armado del mapa por sector están escritos dos veces (E-LIM-37). Las tres definiciones de «plaza tomada» de esta ficha y D-LIM-17 (dos constructores del mapa) se resuelven con el mismo módulo que Emergencia.
- **Ubicación:** `programas/services/estadias.py:287-302` (`_plaza_tomada_por`: estadía activa o reserva `que_toman(momento)`); `programas/selectors/capacidad_dispositivo.py:61-70` (`plazas_tomadas_del_sector`: estadía activa o `estado=VIGENTE` escrito a mano, es decir `abiertas()`); `programas/services/plazas.py:552-554` (`dar_de_baja_plaza`: `_plaza_tomada_por` **o** `reserva_abierta_de`); `programas/services/plazas.py:519-530` (`motivo_para_no_dar_de_baja`, por el estado del mapa); `programas/services/sectores_plazas.py:358-378` (`_reservas_abiertas_por_plaza`, versión masiva de `reserva_abierta_de` con `order_by("-id")` para imitar «la más vieja»)
- **Escenario:** una reserva vencida sin liberar cuenta como «tomada» para dar de baja un sector o una plaza (`abiertas`), pero **no** para sacarla de servicio ni editarla (`que_toman`). Puede ser correcto, pero hoy nadie lo puede leer en un lugar: el criterio está implícito en qué helper eligió cada servicio, y `plazas_tomadas_del_sector` reescribe el filtro de `ReservaPlaza.objects.abiertas()` a mano (`estado=ReservaPlaza.Estado.VIGENTE`). El próximo servicio de configuración va a elegir uno al azar.
- **Causa raíz:** falta un módulo que nombre las dos preguntas distintas («¿alguien la toma desde ahora?» vs «¿queda algo sin resolver encima?») con versión unitaria y masiva.
- **Solución:** en `estadias/reglas_plaza.py` (o `programas/selectors/plazas_tomadas.py` si se prefiere lectura pura):
  ```python
  def tomada_desde_ahora(plaza, momento=None) -> str          # hoy _plaza_tomada_por
  def con_algo_sin_resolver(plaza) -> str                     # estadía activa o ReservaPlaza.objects.abiertas()
  def plazas_con_algo_sin_resolver(plazas_qs) -> set[int]     # masiva, la de sectores y de baja de sector
  ```
  `plazas_tomadas_del_sector` = `len(plazas_con_algo_sin_resolver(Plaza.objects.filter(sector=sector)))`; `dar_de_baja_plaza` usa `con_algo_sin_resolver`; `_reservas_abiertas_por_plaza` se apoya en `ReservaPlaza.objects.abiertas()` (ya lo hace) y documenta en un solo docstring la relación con `reserva_abierta_de`. Mensajes intactos.
- **Lo que NO hay que hacer:** unificar en una sola definición: cambiaría qué se puede sacar de servicio con una reserva vencida (comportamiento).
- **Tests a agregar:** `programas/tests/test_plazas_tomadas.py::CriteriosTests.test_reserva_vencida_bloquea_baja_pero_no_fuera_de_servicio` (fija el comportamiento actual).
- **Verificación:** `grep -rn "estado=ReservaPlaza.Estado.VIGENTE" programas/selectors programas/services` vacío fuera de `models`.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` · «"Tomada" tiene dos significados con nombre (`tomada_desde_ahora`, `con_algo_sin_resolver`); un filtro `estado=VIGENTE` o un `Estadia.objects.activas().filter(plaza…)` nuevo fuera de esos helpers es duplicado».

---

### D-LIM-16 · La API que consumen Emergencia y `plazas.py` sigue siendo privada (inventario completo más allá de E-LIM-19)
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** complementa E-LIM-19 · **Ola:** 7 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D2-LIM-04
- **Cruce con Emergencia:** el contrato Dispositivos ↔ Emergencia se apoya en helpers privados importados entre módulos (E-LIM-19). La API pública de `estadias.py`/`plazas.py` es la misma que pide Emergencia: una sola ficha de fachadas coordinada entre los dos capítulos.
- **Ubicación:** `programas/services/reservas_derivacion.py:76-91` importa `_crear_reserva`, `_exigir_desde_no_futuro`, `_exigir_plaza_libre`, `_reservas_abiertas_de` (además de los de E-LIM-19); `programas/services/emergencia_confirmacion.py:45-53` importa `_reservas_abiertas_de`; `programas/services/plazas.py:42` importa `_plaza_tomada_por` (Dispositivos→Dispositivos); `programas/services/estadias.py:478`, `893` repiten inline el candado de persona que `ingreso.py:309-312` llama `_bloquear_persona`
- **Escenario:** E-LIM-19 ya registra `_bloquear_plaza`, `_bloquear_persona`, `_como_uuid`. Quedan fuera de esa ficha cinco nombres privados que cruzan módulo: `_crear_reserva`, `_exigir_desde_no_futuro`, `_exigir_plaza_libre`, `_reservas_abiertas_de` y `_plaza_tomada_por`. El guion bajo le dice a quien edita `estadias.py` que puede cambiar firma o semántica libremente, pero `reservas_derivacion` y `plazas.py` dependen de ellas. Además el candado de persona existe tres veces (dos inline en `estadias.py` y el helper de `ingreso.py`), y el helper «oficial» vive en el módulo equivocado (el del asistente, no el de las reglas).
- **Causa raíz:** cuando Emergencia y C5 necesitaron las reglas se importaron tal cual, sin promoverlas.
- **Solución:** en `estadias/reglas_plaza.py` y `estadias/reservas.py` (D-LIM-20) exponer con nombre público `crear_reserva`, `exigir_desde_no_futuro`, `exigir_plaza_libre`, `plaza_tomada_por`, `bloquear_persona` (moviéndolo desde `ingreso.py`) y `reservas_abiertas_de_persona` (desde `ingreso._reservas_abiertas_de`). Dejar alias privados `_x = x` durante una release para no romper ramas abiertas, y reemplazar las dos líneas inline de `estadias.py:478,893` por `bloquear_persona(ciudadano)`. Declarar `__all__` en cada submódulo. Resolver junto con E-LIM-19 en el mismo PR.
- **Lo que NO hay que hacer:** «arreglarlo» copiando las funciones en `reservas_derivacion.py` (duplica las reglas de candado que E-LIM-15 ya marca como frágiles).
- **Tests a agregar:** `programas/tests/test_estadias_api_publica.py::SinImportsPrivadosTests.test_ningun_modulo_importa_privados_de_estadias_o_ingreso` (AST sobre `programas/**/*.py`).
- **Verificación:** `grep -rn "from programas.services.\(estadias\|ingreso\) import" programas | grep " _"` vacío (salvo tests).
- **Regla para no repetirlo:** **control mecánico** · regla nueva en `scripts/check_imports_privados.py` (o `ruff` `PLC2701` si se habilita `pylint` rules en `pyproject.toml`) · «import de un nombre `_privado` desde otro módulo de `programas/services` → error».

---

### D-LIM-17 · Dos constructores del mapa de plazas en paralelo (ingreso y «Sectores y plazas»)
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** el tope duplicado ya está en E-LIM-37; esto es el constructor · **Ola:** 7 · **Esfuerzo:** M
- **ID de la pasada 1:** D2-LIM-07
- **Cruce con Emergencia:** misma familia que E-LIM-37 (mapa de camas por sector). Se hace después de D-LIM-15 («plaza tomada») y con el mismo constructor.
- **Ubicación:** `programas/services/ingreso.py:129-181` (`plazas_para_ingresar`); `programas/services/sectores_plazas.py:335-355` y `381-473` (`_plazas_por_sector` + `sectores_con_plazas`); `programas/views/dispositivos_ingreso.py:493-505` (`tension()` vuelve a llamar `ocupacion_de_plazas` porque el mapa del ingreso «no comparte» cifras)
- **Escenario:** los dos hacen lo mismo con diferencias accidentales: leen los sectores activos (consulta propia cada uno), leen las plazas con `.only(...)` distinto (ingreso incluye `tipo`), llaman a `estado_de_plazas`, ordenan con `clave_natural` y cortan en 200. Pero ingreso ordena/cuenta `disponibles` sobre **todas** y corta al final, mientras P5 corta **antes** de derivar estados; ingreso filtra por `admite_tipo_de_plaza` en Python, P5 no. Un ajuste del mapa (p. ej. excluir plazas dadas de baja, o el orden natural) hay que hacerlo dos veces, y el paso 2 del asistente paga 3 consultas extra de `ocupacion_de_plazas` para la tensión.
- **Causa raíz:** el mapa nació en P6 y P5 lo reescribió para su modal en lugar de extraerlo.
- **Solución:** `programas/selectors/mapa_plazas.py::mapa_de_plazas(dispositivo, momento, *, puede_ver_personas, filtro_tipo=None) -> list[SectorDelMapa]` que devuelve sectores activos, plazas ordenadas (sin cortar), `EstadoPlaza` por plaza y el `OcupacionSector` correspondiente. `plazas_para_ingresar` y `sectores_con_plazas` pasan a ser adaptadores que agregan lo suyo (elegibles/propia; acciones/enlaces/modal) y aplican el tope en un solo punto. La tensión del paso 2 sale del `conteo` que ya trae el mapa.
- **Lo que NO hay que hacer:** hacer que el mapa de ingreso use el `Conteo` filtrado por tipo como si fuera el del dispositivo: la tensión del mockup es la del dispositivo entero (lo dice `dispositivos_ingreso.py:496-499`); conservar esa distinción explícita en el selector.
- **Tests a agregar:** `programas/tests/test_mapa_plazas.py::MapaTests.test_mismo_estado_en_ingreso_y_sectores`; presupuesto `dispositivos_ingreso_plaza` en `scripts/perf_budgets.json` (baja de consultas).
- **Verificación:** `--tag performance` con presupuestos iguales o menores; snapshots de P5/P6 sin cambios.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-auditor.md` · «Toda pantalla que dibuja plazas consume `selectors.mapa_plazas.mapa_de_plazas`; un `estado_de_plazas(` llamado desde un servicio de pantalla nuevo es un tercer constructor».

---

### D-LIM-18 · `ingreso.py` aloja la identidad de la persona (DNI, RENAPER, alta de legajo) que usa medio sistema
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 7 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D2-LIM-10
- **Cruce con Emergencia:** la identidad de la persona (DNI, RENAPER, alta de legajo) que aloja `ingreso.py` es la misma ruta que falla en E-ERR-01 (confirmar con el DNI de un legajo existente sin validar la identidad, CONFIRMADO con PoC). Si se mueve esa lógica, el test de E-ERR-01 es el de regresión.
- **Ubicación:** `programas/services/ingreso.py:61-83` (`buscar_ciudadano_por_dni`, «regla única de este DNI ya tiene persona»), `86-109` (`buscar_en_registro_de_personas`), `315-373` (`_alta_desde_registro`, `_alta_manual`, `alta_minima_de_persona`, `_crear_legajo`); consumidores: `programas/services/emergencia_alta.py:46`, `emergencia_recepcion.py:41`, `emergencia_confirmacion.py:46-53`, `forms_dispositivos.py:18`, `services/identidad.py:181` (import diferido dentro de función, señal de ciclo)
- **Escenario:** la regla de identidad del padrón vive en «datos y escritura del asistente de ingreso de Dispositivos». Emergencia, formularios y `identidad.py` la importan desde ahí; `identidad.py` necesita un import perezoso para no formar ciclo. Cualquier cambio del asistente (p. ej. al mapa del paso 2) toca un módulo del que depende la recepción de Emergencia.
- **Causa raíz:** se escribió para el asistente y se volvió canónica por uso.
- **Solución:** mover las cinco funciones a `programas/services/identidad.py` (ya existe y es el dueño natural) o a `legajos/services` si el PM prefiere el dominio Legajo; `ingreso.py` re-exporta una release. `alta_minima_de_persona` deja de ser un alias de `_alta_manual`: queda una sola función pública con ese nombre.
- **Lo que NO hay que hacer:** dejar copias en ambos lados «hasta migrar»: `buscar_ciudadano_por_dni` es explícitamente la regla única (Cambio 486).
- **Tests a agregar:** `programas/tests/test_identidad.py::BuscarPorDniTests.test_misma_respuesta_desde_ingreso_y_emergencia` (importa del re-export y del nuevo hogar, mismo objeto).
- **Verificación:** `identidad.py` sin import diferido; `python -c "import programas.services.identidad"` sin ciclo.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` · «Un helper canónico (tabla de helpers) vive en el módulo del concepto, no en el de su primer consumidor; un import diferido dentro de una función para evitar ciclo es síntoma».

---

### D-LIM-19 · `sectores_plazas.py` es un presentador en `services/`: arma URLs, payload del modal y nombres de funciones JS
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 7 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D2-LIM-11
- **Ubicación:** `programas/services/sectores_plazas.py:440-457` (`click = f"abrirReubicar({plaza.pk})"`, `f"abrirPlaza({plaza.pk})"`, `url = f"?editar_plaza=…"`), `188-223` (`reverse` de cuatro vistas), `279-300` (`datos_para_el_modal`, forma del `json_script`)
- **Escenario:** el módulo no escribe nada ni decide reglas (las delega a `ocupacion`/`plazas`), pero está en `services/` y emite código JavaScript como texto. Renombrar `abrirPlaza` en el componente Alpine de `sectores.html` rompe el mapa sin error en Python ni en tests de servicio; y un selector de lectura que llama `reverse` y arma `?editar_plaza=` mezcla routing con dominio.
- **Causa raíz:** «la vista no decide» se tradujo en mover la presentación a un servicio, en vez de a un selector/presentador.
- **Solución:** mover el módulo a `programas/selectors/sectores_plazas.py` (lectura pura) y reemplazar los strings JS por datos: cada celda lleva `{"modal": "plaza" | "reubicar" | "", "pk": …}` y el template decide `@click="abrir(celda)"`. `acciones_de_plaza`/`bloqueo_de_plaza` (reglas de qué acción admite una plaza) quedan en `services/plazas.py`. Mismo HTML resultante.
- **Lo que NO hay que hacer:** pasar la lógica de acciones al template (es la que hoy está bien testeada en Python).
- **Tests a agregar:** `programas/tests/test_sectores_plazas.py::CeldaTests.test_celda_no_contiene_javascript`.
- **Verificación:** snapshot del HTML de P5 idéntico.
- **Regla para no repetirlo:** **control mecánico** · `scripts/design_audit.py` regla nueva `PYJS` · «literal `f"…(` + identificador JS en `programas/services/*.py` o `selectors/*.py` → hallazgo: el servicio emite código de cliente».

---

### D-LIM-20 · `estadias.py` supera las 1000 líneas mezclando cinco responsabilidades
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 7 · **Esfuerzo:** M
- **ID de la pasada 1:** D2-LIM-01
- **Ubicación:** `programas/services/estadias.py:1-1041` (docstring 1-90; verificación en red 144-255; reglas de plaza 276-438; ciclo de la estadía 441-794; reservas 797-963; servicio de plaza 966-1041; presentación 147-159)
- **Escenario:** cualquier cambio en reservas, en el estado operativo de la plaza o en la verificación de red obliga a abrir y diffear el archivo que también contiene los cuatro servicios transaccionales más delicados del producto (ingreso/egreso/cambio/asignación). Emergencia, `plazas.py`, `sectores_plazas.py`, tres selectores y dos vistas importan de este único módulo, así que cada PR que lo toca tiene un radio de impacto de todo el carril.
- **Causa raíz:** el módulo creció por etapas (2 → 3 → C5 → Emergencia) agregando al final; nunca se cortó. Conviven: (a) la pregunta de red con su DTO (`VerificacionAlojamiento`, `AlojamientoEnLaRed`), (b) las reglas de plaza que Emergencia reusa, (c) el ciclo de vida de la estadía, (d) reservas/préstamos, (e) `sacar_plaza_de_servicio`/`volver_plaza_a_servicio`, que son **configuración de plaza** (piden `CAP_EDITAR`) y (f) una tabla de presentación (`ESTADOS_VISIBLES`/`estado_visible`) que solo leen selectores.
- **Solución:** convertir `programas/services/estadias.py` en paquete `programas/services/estadias/` con `__init__.py` que re-exporta exactamente los nombres públicos de hoy (ningún import externo cambia):
  - `alojamiento.py` (~150): `REFERENTE_FUERA_DE_ALCANCE`, `AlojamientoEnLaRed`, `VerificacionAlojamiento`, `verificar_alojamiento_en_red`, `_exigir_intervalo_sin_alojamiento`, `ALOJAMIENTO_SOLAPADO`.
  - `reglas_plaza.py` (~170): `bloquear_plaza`, `bloquear_reserva_propia`, `tomar_plaza`, `exigir_plaza_libre`, `exigir_plaza_libre_desde`, `plaza_tomada_por`, `reserva_abierta_de` y sus mensajes (ver D-LIM-16: aquí nacen con nombre público).
  - `ciclo.py` (~330 tras D-LIM-14): `ingresar_persona`, `egresar_persona`, `cambiar_plaza`, `asignar_plaza`.
  - `reservas.py` (~170): `reservar_plaza`, `crear_reserva`, `liberar_reserva`, `reserva_propia_vigente`, `_exigir_persona_sin_alojamiento_ni_reserva`.
  - `sacar_plaza_de_servicio` / `volver_plaza_a_servicio` → `programas/services/plazas.py` (ver D-ERR-02).
  - `ESTADOS_VISIBLES` / `estado_visible` → `programas/selectors/estadia_presentacion.py` (lo leen `estadia_detalle`, `trayectoria`, `detalle_dispositivo`).
  - Los docstrings largos («Por qué el bloqueo alcanza», «El orden de los candados») viajan con `reglas_plaza.py`, que es donde vive lo que explican.
- **Lo que NO hay que hacer:** partir por tamaño (`estadias_1.py`, `estadias_2.py`) o mover funciones sin el `__init__` de re-export: `emergencia_confirmacion`, `reservas_derivacion`, `dispositivos_legajo` y los tests importan desde `programas.services.estadias`. Tampoco reordenar los candados al mover (ver E-LIM-15; `OrdenDeLosCandadosTests` fija la secuencia).
- **Tests a agregar:** `programas/tests/test_estadias_api_publica.py::ApiPublicaTests.test_reexporta_los_nombres_de_hoy` (lista de nombres esperados en `programas.services.estadias.__all__`).
- **Verificación:** suite completa + `programas.tests.test_dispositivos_concurrencia` + `--tag performance` sin cambios; `wc -l` de cada módulo < 450.
- **Regla para no repetirlo:** **control mecánico** · `scripts/check_tamano_modulos.py` (nuevo, ratchet en CI) · falla si un `.py` de `programas/services|selectors|views` pasa de 1000 líneas o si uno que ya pasaba crece; lista de excepciones con fecha de vencimiento.

---

### D-LIM-21 · La máquina de estados del legajo está repartida en 7 servicios, 7 vistas y el template, que reescribe los orígenes
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 8 · **Esfuerzo:** M
- **ID de la pasada 1:** D1-LIM-03
- **Ubicación:** `programas/services/dispositivos.py:463-562` (siete funciones de 10-15 líneas que solo cambian
  `origenes`, `destino`, `accion` y dos flags). `programas/views/dispositivos_legajo.py:794-849`: siete subclases de
  `DispositivoActionView` que solo cambian capacidad, mensaje y servicio. `programas/templates/programas/dispositivos/legajo/detail.html:54,61,72,75,78,289`:
  el template decide qué transición ofrecer comparando `dispositivo.estado == 'ACTIVO'`, `'INACTIVO'`,
  `'RECHAZADO'`, `'CERRADO'`.
- **Escenario:** «Cerrar» se ofrece si `estado in (ACTIVO, INACTIVO, RECHAZADO)` (`detail.html:78`), que es una
  copia literal de `origenes` en `cerrar_dispositivo` (`dispositivos.py:559`). Si el PM decide que un `OBSERVADO`
  también se puede cerrar y se toca el servicio, el botón no aparece. Si se toca el template, el botón aparece y
  el servicio responde «La transición de estado solicitada no está permitida». Lo mismo pasa con Inactivar
  (`:72` contra `:530`), Reactivar (`:75` contra `:547`) e «Ingresar persona» (`:54`, `:289`). «Enviar a
  validación» sí está bien: usa `estados_desde_los_que_se_envia()` (`:370-378`), que es justamente la prueba de que
  el patrón correcto ya existe para uno solo de los siete.
- **Causa raíz:** no hay un modelo explícito de transiciones. Cada capa conoce los estados por su cuenta.
- **Solución (judo):** una tabla en `services/dispositivos.py`:
  ```python
  @dataclass(frozen=True)
  class Transicion:
      origenes: tuple; destino: str; traza: str; capacidad: str
      exige_datos: bool = False; exige_formulario: bool = False; motivo_obligatorio: str = ""
  TRANSICIONES = {"enviar_validacion": Transicion(...), "validar": ..., "observar": ..., "rechazar": ...,
                  "inactivar": ..., "reactivar": ..., "cerrar": ...}
  def transicionar(dispositivo, usuario, accion, motivo=None): ...   # el _transicionar de hoy + el chequeo de motivo
  def transiciones_disponibles(usuario, dispositivo) -> set[str]:     # estado en origenes y puede_operar(capacidad)
  ```
  Las siete funciones públicas quedan como alias de una línea, para no romper importadores. En la vista queda una
  sola `DispositivoTransicionView(accion=...)`, registrada en `dispositivos_urls.py` con `as_view(accion="cerrar",
  mensaje_exito=...)`, con los mismos nombres de URL. El detalle pasa `acciones = transiciones_disponibles(user,
  dispositivo)` y el template pregunta `{% if "cerrar" in acciones %}`. Así desaparecen las cinco comparaciones de
  estado del template y los flags `puede_validar`/`validacion_pendiente`. Los textos y la estética no cambian.
- **Lo que NO hay que hacer:** mover las comparaciones del template a variables de contexto `puede_cerrar = estado
  in (...)` en la vista: eso es mover la copia, no borrarla.
- **Tests a agregar:** `programas/tests/test_dispositivos_legajo.py::TransicionesTests.test_boton_y_servicio_usan_la_misma_tabla`
  (para cada estado, el conjunto que da `transiciones_disponibles` coincide con lo que el servicio acepta).
- **Verificación:** `test_dispositivos_cambio_407` y `test_dispositivos_legajo` pasan sin cambios. Además,
  `grep -c "dispositivo.estado ==" legajo/detail.html` tiene que dar 0.
- **Regla para no repetirlo:** **control mecánico** · `scripts/design_audit.py` (o un test de templates) · patrón
  `\.estado\s*(==|!=)\s*'[A-Z_]+'` en `programas/templates/programas/dispositivos/**`: «El template no decide
  transiciones: usá `acciones` de `transiciones_disponibles`», en modo ratchet.

---

### D-LIM-22 · `infraestructura_del_dispositivo`: 240 líneas, tres modos y un dict de 16 claves implícitas
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 8 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D1-LIM-10
- **Ubicación:** `programas/services/detalle_dispositivo.py:654-893`. `_respuesta_base` en `:524-544`.
- **Escenario:** una función hace cinco consultas, decide el modo (`vacio`, `listado` o `ficha`), arma filtros,
  chips, resumen, el bloque «sin edificio» y la URL de paginación, y devuelve un dict cuyas claves válidas dependen
  del modo. `_respuesta_base` existe solo para que el template no reviente con una clave ausente: es un *fallback*
  silencioso que tapa la invariante. Qué claves trae cada modo hay que leerlo en el docstring (`:663-672`). La
  elección del edificio pedido (`:735-744`) es un tercer parseo de id con reglas propias (ver D-LIM-33).
- **Causa raíz:** el modo creció por casos (Cambio 439) dentro de la misma función, en vez de modelarse.
- **Solución:** `_filas_de_edificios(...)` hace las consultas y el orden, y después `_vacio()`, `_listado(filas,
  estado, base)` y `_ficha(filas, pedido, usuario, pagina)`, cada uno con su `@dataclass(frozen=True)`
  (`InfraVacia`, `InfraListado`, `InfraFicha`, todas con `modo`). Los templates leen atributos con la misma
  sintaxis, así que `_infra_listado.html` y `_infra_ficha.html` no cambian. Se borra `_respuesta_base`. La única
  clave que leen los dos modos fuera de su parcial (`infraestructura.edificios` en `dispositivos_legajo.py:669`) pasa
  a ser una propiedad común.
- **Tests a agregar:** `programas/tests/test_dispositivos_fidelidad_fi.py::InfraModosTests.test_cada_modo_trae_solo_lo_suyo`.
- **Verificación:** las pruebas de fidelidad de infraestructura (`test_dispositivos_fidelidad_fi`) y el presupuesto
  de consultas del detalle no cambian.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md`, regla 5: «Un servicio que devuelve un dict con
  "modo" y claves que valen según el modo pide un tipo por modo; un `_respuesta_base` con vacíos es la señal».

---

### D-LIM-23 · Los códigos de acción de `TrazaDispositivo` son strings sueltos en seis módulos, sin `choices`
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 8 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D1-LIM-13
- **Ubicación:** `programas/models/__init__.py:812` (`accion = CharField(max_length=40)`, sin choices).
  Productores: `services/dispositivos.py:318,332,471,485,503,519,532,549,561`, `services/estadias.py:533,862`,
  `services/plazas.py:358` y `services/edificios.py:170`. Consumidor: `selectors/auditoria_dispositivo.py:48-99,184-189`.
  Lo mismo pasa con los estados en `services/dispositivos.py:38-46` (`TONOS_ESTADO` con claves `"BORRADOR"` y
  demás, en lugar de `Dispositivo.Estado`).
- **Escenario:** un typo en un productor (`"SECTOR_REACTIVADA"`) no falla: el historial muestra «Sector
  reactivada» por `_titulo_desconocido` (`:178-179`), sin tono. Nadie lo detecta. Para saber qué acciones existen
  hay que hacer grep en seis archivos.
- **Causa raíz:** la traza nació con dos acciones y creció sumando strings.
- **Solución:** `TrazaDispositivo.Accion(models.TextChoices)`, con las etiquetas de `TITULOS_TRAZA` como labels.
  Los productores usan `TrazaDispositivo.Accion.SECTOR_BAJA` y el selector arma `TITULOS_TRAZA` desde
  `Accion.labels`. Si no se quiere migración, una clase de constantes sin `choices` da lo mismo en el código. Si se
  ponen `choices`, la migración es un `AlterField` de estado sin SQL en MySQL/MariaDB y entra en el contrato de
  `check_migraciones.py`. `TONOS_ESTADO` pasa a usar `Dispositivo.Estado.X` como clave.
- **Tests a agregar:** `programas/tests/test_dispositivos_detalle.py::HistorialTests.test_toda_accion_tiene_titulo`
  (recorre `Accion` y exige una entrada en títulos).
- **Verificación:** `grep -rn "\"[A-Z_]\{5,\}\"" programas/services/dispositivos.py` no devuelve códigos de acción.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md`: «Un `CharField` de códigos que escriben varios módulos
  lleva `TextChoices` o constantes, no literales».

---

### D-LIM-24 · `detalle_dispositivo.py` (893) junta dos dominios, y el de Infraestructura lo importa un selector
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 8 · **Esfuerzo:** M
- **ID de la pasada 1:** D1-LIM-09
- **Ubicación:** `programas/services/detalle_dispositivo.py:322-893` (Infraestructura y el registro fotográfico del
  edificio, ~570 líneas) junto a `:58-319` (estadías, alertas e historial de P4). `programas/selectors/edificios.py:28-33`
  importa de este servicio `ESTADOS_EDILICIOS`, `aviso_de_vencimiento`, `estado_edilicio` y
  `registro_de_relevamientos`. `programas/views/dispositivos_edificios.py:25` importa `ESTADOS_EDILICIOS`. Las
  consultas de `:699-767` son ORM de lectura puro dentro de un servicio.
- **Escenario:** la ficha propia del edificio (#1168) depende del «detalle del dispositivo» para saber el estado de
  un edificio. La capa queda invertida (selector → servicio → selector), y cualquier cambio en la solapa P4 recompila
  el selector de edificios. Pasa de 700 líneas y cada nueva regla edilicia lo acerca a 1000.
- **Causa raíz:** la solapa Infraestructura se construyó dentro del módulo de P4. Cuando el edificio tuvo pantalla
  propia, se reusó por import en vez de mudar el código.
- **Solución:** partir en (a) `services/estado_edilicio.py` (`ESTADOS_EDILICIOS`, `clave_estado_edilicio`,
  `estado_edilicio`, `aviso_de_vencimiento`, `evento_de_relevamiento`, `registro_de_relevamientos`; ~200 líneas, sin
  dependencias de P4); (b) `services/infraestructura_dispositivo.py` (`infraestructura_del_dispositivo` y sus
  `_fila`/`_predio`/`_resumen`; ~350 líneas, ver D-LIM-22); (c) las dos consultas agregadas (edificios anotados y
  totales por edificio) a `selectors/capacidad_dispositivo.py`, que ya tiene `sectores_por_edificio`. Lo de P4
  queda en `detalle_dispositivo.py` con ~320 líneas. `selectors/edificios.py` importa de (a). Re-exportar en
  `detalle_dispositivo` mientras haya importadores.
- **Lo que NO hay que hacer:** moverlo todo a `selectors/edificios.py`: esas funciones redactan y deciden visibilidad,
  y el selector ya tiene demasiado.
- **Tests a agregar:** `programas/tests/test_arquitectura.py`: ningún `programas/selectors/*.py` importa de
  `programas.services.detalle_dispositivo`.
- **Verificación:** presupuestos de consultas del detalle y de la ficha del edificio sin cambios.
- **Regla para no repetirlo:** **control mecánico** · `test_arquitectura.py` · ratchet de imports
  `selectors → services` (hoy, al menos `edificios → detalle_dispositivo` y `edificios → dispositivos`).

---

### D-LIM-25 · `views/dispositivos_legajo.py` tiene 1659 líneas y mezcla cuatro pantallas
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 8 · **Esfuerzo:** M
- **ID de la pasada 1:** D1-LIM-01
- **Ubicación:** `programas/views/dispositivos_legajo.py:1-1659`. Legajo P2/P3/P4: `:166-857` (el `DetailView` solo
  ocupa `:406-684`, 278 líneas). Sectores P5 y acciones de plaza: `:860-1329`. Egreso: `:1332-1491`. Estadía P7 y
  cambio de plaza: `:1494-1659`. 125 líneas de imports (`:3-163`).
- **Escenario:** quien toca el modal de egreso carga en la cabeza el mapa de plazas, el alta del legajo y siete
  transiciones. Hay constantes que se usan 250 líneas antes de definirse: `FRAGMENTO_REUBICAR` se usa en `:882` y se
  define en `:1131`; `OPCION_REUBICAR` y `URL_DE_ACCION` también. Hay helpers compartidos entre las cuatro pantallas
  enterrados en el medio (`_entero` `:852`, `_estadia_del_dispositivo` `:1503`, `_form_de_cambio_de_plaza` `:1525`).
  `urls_plaza` arma URLs con un `reverse(..., args=[pk, 0]).replace("/plazas/0/", "/plazas/__pk__/")` (`:1031`),
  que depende de la forma literal de la ruta.
- **Causa raíz:** el archivo creció etapa por etapa del MVP v2 y nunca se partió. Ya hubo una partición parcial
  (`dispositivos_capacidad`, `dispositivos_ingreso`, `dispositivos_edificios`), pero estas cuatro pantallas
  quedaron juntas.
- **Solución:** partir sin cambiar comportamiento:
  - `views/dispositivos_legajo.py` (~700): listado, alta, edición, duplicados, sección del tipo, detalle y acciones.
    Baja más con D-LIM-03, D-LIM-21 y D-LIM-10.
  - `views/dispositivos_sectores.py` (~470): `DispositivoSectoresView`, `_PlazaAccionView` y sus cinco hijas,
    `PersonasSugeridasView`, `OPCION_REUBICAR`, `FRAGMENTO_REUBICAR` y `URL_DE_ACCION` (arriba del módulo).
  - `views/dispositivos_estadias.py` (~330): `DispositivoEstadiasView`, egreso, `EstadiaDetalleView`,
    `EstadiaCambiarPlazaView`, `url_volver_a_la_estadia` y `formulario_de_egreso`.
  - `programas/services/cambio_de_plaza.py` (o `estadias.py`): `_estadia_del_dispositivo`, `_sectores_para_cambio`
    y `_form_de_cambio_de_plaza`, que usan las tres pantallas. Si quedaran en una vista, el ratchet de dependencias
    entre vistas (`test_arquitectura.py`) subiría.

  `dispositivos_urls.py` importa de los tres módulos. Para `urls_plaza`, un patrón de URL con placeholder
  explícito (o `reverse` con `args=[pk, PLACEHOLDER]` documentado en el `urls`) en lugar del `replace`.
- **Lo que NO hay que hacer:** dejar `dispositivos_legajo.py` re-exportando todo para no tocar los tests. Los ~10
  `patch("programas.views.dispositivos_legajo.X")` (por ejemplo `plazas_para_ingresar`, `egresar_persona`,
  `guardar_respuestas_egreso`, `_sectores_para_cambio`, `ocupacion_de_plazas`) tienen que apuntar al módulo nuevo,
  o el patch reemplaza un nombre que nadie lee y el test pasa por el motivo equivocado.
- **Tests a agregar:** ninguno nuevo. Correr `test_dispositivos_*` con los patch corregidos.
- **Verificación:** `wc -l programas/views/dispositivos_*.py` sin archivos de más de 1000.
  `test_arquitectura.CapasTests` sin dependencias nuevas.
- **Regla para no repetirlo:** **control mecánico** · `test_arquitectura.py` · ratchet de tamaño: ningún
  `programas/views/*.py` crece si ya pasa de 1000, y ninguno nuevo cruza 1000.

---

### D-LIM-26 · El constructor de formularios de Dispositivos es una copia de views/diseno.py (Becas)
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 8 · **Esfuerzo:** M
- **ID de la pasada 1:** D3-LIM-01
- **Cruce con Becas (esfuerzo compartido):** el mismo pegamento HTTP del constructor está en Becas como B-LIM-38 (ex B5-LIM-07, `views/diseno.py` y `views/dispositivos_formularios.py`, `constructor_http.py`, `leer_movimiento`/`leer_condicion`; Ola 12 de Becas). **Un solo PR** resuelve los dos lados: las 8 h de esta ficha se cuentan una vez con B-LIM-38; el juez decide en qué ola vive.
- **Ubicación:** `views/dispositivos_formularios.py:54-316` (`_item`, `_json`, `_contexto`, `_respuesta`, `_mutar` y las vistas mover/grupo/texto/propio/item_editar/condicion/eliminar en 207-316) frente a `views/diseno.py:1-305` (las mismas vistas en 155-290).
- **Escenario:** se arregla un bug del constructor en Becas (validación de condición, orden al mover, respuesta JSON) y Dispositivos lo sigue teniendo, o al revés. Ya hay tres diferencias que nadie documentó: el resolver de diseño, `_en_ambos` y `permite_archivo=True`.
- **Causa raíz:** el constructor se clonó para Dispositivos en lugar de parametrizarlo. Las mutaciones ya viven en `services/diseno.py`; lo que se duplicó es la orquestación HTTP.
- **Solución:** un módulo `views/constructor_base.py` con una clase base (`ConstructorMutacionView`) que lleva `_item/_json/_contexto/_respuesta/_mutar` y las 7 vistas como subclases mínimas. Tres ganchos: `resolver_diseno(request, **kwargs)`, `alcance_extra` (`_en_ambos`) y `permite_archivo`. Becas y Dispositivos heredan y solo declaran los ganchos. Las URLs, los templates y el JSON de respuesta no cambian.
- **Lo que NO hay que hacer:** no fusionar las URLs ni los templates de los dos constructores; no tocar `services/diseno.py`; no meter `if programa == ...` en la base: los ganchos los resuelve cada subclase.
- **Tests a agregar:** un test parametrizado que pegue a las 7 mutaciones en los dos productos y compare el JSON con un snapshot tomado antes del cambio.
- **Verificación:** `manage.py test programas.tests` sobre los tests del constructor de Becas y de Dispositivos; diff del JSON igual a cero.
- **Regla para no repetirlo:** control mecánico · `programas/tests/test_arquitectura.py` · «Un detector de funciones homónimas con el mismo cuerpo AST entre `views/` de dos productos falla el build (techo = lo medido hoy).»

---

### D-LIM-27 · `pantalla_bitacora` es una función de 318 líneas que mezcla todo
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 8 · **Esfuerzo:** M
- **ID de la pasada 1:** D3-LIM-03
- **Ubicación:** `services/bitacora_pantalla.py:338-656`.
- **Escenario:** la función parsea la fecha, elige el turno, consulta vigentes, reemplazadas, corregibles (con dos ramas en 461-492), personas y turnos_config, y arma URLs con un `url_de` anidado y querystrings a mano (528-534). Encima arma tarjetas, títulos y notas. Cualquier cambio en una tarjeta obliga a leer las 318 líneas y a correr la pantalla entera para probarlo; no hay forma de testear la selección de turno sin la base.
- **Causa raíz:** la pantalla creció por agregado, sin cortes entre consulta, regla y presentación.
- **Solución:** partirla sin cambiar salida en (a) `_fecha_y_turno_pedidos(params, turnos)`, pura; (b) un selector `entradas_del_turno(dispositivo, turno, fecha)` que devuelva vigentes, reemplazadas y corregibles; (c) `_urls_de_bitacora(dispositivo, fecha, turno)` con `urlencode` en lugar de concatenar; (d) `_tarjetas(...)`, pura. `pantalla_bitacora` queda como orquestadora de menos de 60 líneas.
- **Lo que NO hay que hacer:** no cambiar las claves del dict que consume `bitacora.html` ni el número de consultas (mantener el presupuesto de queries).
- **Tests a agregar:** un snapshot del dict devuelto para 3 escenarios (turno en curso, por venir, cerrado) tomado antes del cambio, y tests unitarios de `_fecha_y_turno_pedidos`.
- **Verificación:** snapshot idéntico; `assertNumQueries` igual al actual.
- **Regla para no repetirlo:** control mecánico · ruff · «Activar `C901`/`PLR0915` (máx. 80 sentencias) en `programas/services/` con baseline; la función nueva no puede pasar el techo.»

---

### D-LIM-28 · La regla de «vencido / por vencer» está escrita cinco veces, en Python y en SQL por separado
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 9 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D4-LIM-03
- **Ubicación:**
  - `programas/models/__init__.py:2175-2179` (`InspeccionEdificio.vencida`, Python; la usa el serializer, campo `vencida`)
  - `programas/services/inspecciones.py:786-796` (`situacion_de`, Python, vencida + por vencer)
  - `programas/services/inspecciones.py:799-811` y `programas/selectors/vencimiento_inspecciones.py:13-14` (Q)
  - `programas/services/detalle_dispositivo.py:449-463` (`aviso_de_vencimiento`, ventana de por vencer otra vez)
  - `programas/views/dispositivos_relevamientos.py:133-143` (`_vence_relativo`, días relativos)
  - y el texto fijo «30 días» del template (D-FE-09)
- **Escenario:** si el Ministerio pide que el día del vencimiento ya cuente como vencido (hoy «el día del vencimiento
  todavía está vigente», `vencimiento_inspecciones.py:18`), hay que tocar `vencida()`, `situacion_de` y la `Q` a la
  vez. Si se olvida uno, la tarjeta «Vencidos» de P21 (SQL) y el badge de la fila (Python) muestran cosas distintas
  sobre el mismo relevamiento. Hoy coinciden; nada lo garantiza más que la memoria de quien edita.
- **Causa raíz:** no hay un dueño único del predicado: cada pantalla nueva (P21, semáforo, ficha del edificio,
  alertas, API) lo volvió a escribir en el idioma que necesitaba (Python o `Q`).
- **Solución:** un solo módulo (el selector de D-LIM-29) con las dos formas juntas y documentadas como par:
  `condicion_situacion(situacion, hoy) -> Q` y `situacion_de(inspeccion, hoy)` (Python), ambas usando
  `DIAS_POR_VENCER`. `InspeccionEdificio.vencida()` delega en `situacion_de(...) == VENCIDA`;
  `aviso_de_vencimiento` usa `DIAS_POR_VENCER` (ya lo hace) pero toma la comparación de ese módulo. Se mantienen
  los textos y tonos actuales.
- **Lo que NO hay que hacer:** registrar una `ReglaVencimiento` en `core/services/vencimientos.py`: el vencido no
  transiciona estado y `procesar_vencimientos` cambiaría el modelo de datos (sería una DECISIÓN CLIENTE).
- **Tests a agregar:** `programas/tests/test_inspecciones_situacion.py::SituacionParidadTests.test_python_y_sql_coinciden`
  — para hoy-1, hoy, hoy+30, hoy+31, compara `situacion_de(i)` contra el `filter(condicion_situacion(...))` de cada
  situación.
- **Verificación:** el test de paridad; mutación: cambiar `<` por `<=` en un solo lado y verlo rojo.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md`, tabla de helpers
  canónicos · fila nueva: «Situación de un relevamiento edilicio (vencido / por vencer / al día) · `situacion_de` y
  `condicion_situacion` (`programas/selectors/inspecciones.py`), siempre las dos juntas y con test de paridad».

---

### D-LIM-29 · Capas invertidas: los selectores importan de los servicios y un módulo existe solo para cortar el ciclo
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 9 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D4-LIM-02
- **Ubicación:** `programas/selectors/inspecciones.py:4`; `programas/selectors/edificios.py:28-45`;
  `programas/selectors/vencimiento_inspecciones.py:1-5`; imports diferidos en `programas/services/inspecciones.py:802`
  y `:1043` y en `programas/services/alertas_dispositivos.py:224`
- **Escenario:** `selectors/inspecciones.py` (14 líneas) importa `edificios_en_alcance` de
  `services/inspecciones.py`; el servicio necesita la condición de vencido, así que esa condición vive en un
  tercer módulo, `selectors/vencimiento_inspecciones.py`, cuyo docstring dice: «aquel importa del servicio de
  inspecciones, y el servicio lee estas funciones, así que juntos formarían un ciclo». Aun así hacen falta tres
  imports dentro de funciones. `selectors/edificios.py` importa de tres servicios (`detalle_dispositivo`,
  `dispositivos`, `inspecciones`).
- **Causa raíz:** las lecturas de alcance nacieron en el servicio (D-LIM-30), así que la dependencia apunta al
  revés de lo que dice `CLAUDE.md` (servicios leen de selectores, no al contrario).
- **Solución:** mover las lecturas a `selectors/inspecciones.py` (lista en D-LIM-30, paso 1), fusionar ahí
  `vencimiento_inspecciones.py` (dejarlo como re-export de una línea por compatibilidad) y reemplazar los imports
  diferidos por imports de módulo. `services/inspecciones.py` pasa a importar de `selectors/`; ningún selector
  importa de `services/inspecciones`.
- **Lo que NO hay que hacer:** seguir resolviendo cada ciclo nuevo con otro import diferido u otro módulo puente.
- **Tests a agregar:** el control de abajo.
- **Verificación:** `grep -n "^\s\+from programas" programas/services/inspecciones.py` sin resultados; el ratchet de
  abajo en verde.
- **Regla para no repetirlo:** **control mecánico** · `core/tests/test_capas_imports.py` (nuevo, mismo estilo que el
  ratchet de aristas de RED-79) · por AST: un módulo de `programas/selectors/` no importa de `programas.services`
  ni de `programas.views`. Allowlist con las aristas de hoy (`selectors/edificios.py`, `selectors/inspecciones.py`,
  `selectors/capacidad_dispositivo.py` si aplica…) que solo puede achicarse. Mensaje: «Un selector no lee de un
  servicio: mové la lectura al selector y que el servicio la importe».

---

### D-LIM-30 · `services/inspecciones.py` pasa las 1.000 líneas y mezcla cinco responsabilidades
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 9 · **Esfuerzo:** M
- **ID de la pasada 1:** D4-LIM-01
- **Ubicación:** `programas/services/inspecciones.py:1-1257` (1.257 líneas)
- **Escenario:** cualquier cambio al semáforo, al listado P21 o al informe abre el mismo archivo que las
  operaciones transaccionales del agente (`registrar_resultado`, `agregar_foto`). Los bloques ya están rotulados
  a mano: alcance (`:154-344`), comandos del coordinador (`:346-454`), comandos del agente (`:456-748`), listado y
  situación (`:750-908`), lecturas y semáforo (`:910-1059`), presentación del informe (`:1061-1257`).
- **Causa raíz:** el módulo creció por etapas del MVP (#699, #700, #701, #705, Cambios 275/422/423) y cada una
  sumó su sección al mismo archivo. Solo dos quintos son escritura; el resto son lecturas (que según `CLAUDE.md`
  van a `selectors/`) y armado de dicts para el template (íconos `fa-*`, tonos, notas, fechas ya formateadas).
- **Solución (sin cambiar lógica ni estética):** partir por la costura que ya está marcada, re-exportando desde
  `services/inspecciones.py` lo que importan los tests y la API para que nada se rompa en el paso 1:
  1. `selectors/inspecciones.py` ← alcance y lecturas: `_edificios_de`, `edificios_en_alcance`,
     `inspecciones_visibles`, `inspecciones_asignadas`, `inspecciones_del_agente`, `inspecciones_para_envio`,
     `_personal_de_edificios`, `personal_del_edificio`, `_candidatos_a_relevar`, `agentes_asignables*`,
     `edificios_para_asignar*`, `edificios_sin_relevar`, `inspecciones_en_curso_por_edificio`,
     `ultima_inspeccion`, `subconsulta_ultima_realizada`, `ultimas_inspecciones_por_edificio`,
     `inspecciones_de_dispositivo`, `edificios_con_asignacion_visible*`, `resumen_listado`, `filtrar_por_situacion`
     (este paso resuelve también D-LIM-29).
  2. `services/semaforo_edilicio.py` ← `Semaforo`, `SEMAFOROS`, `_GRAVEDAD`, `semaforo_de_*`,
     `semaforos_de_dispositivos`, `Situacion`, `situacion_de`, `DIAS_POR_VENCER`.
  3. `services/informe_relevamiento.py` ← `ve_la_asignacion`, `fotos_para_galeria`, `_indicadores_del_informe`,
     `_TONOS_*`, `informe_de_relevamiento`.
  4. Queda en `services/inspecciones.py` lo transaccional: excepciones, `crear/reasignar/cancelar_inspeccion`,
     `marcar_revisado`, `registrar_resultado`, `_admitir_carga`, `agregar_foto`, `agregar_adjunto_formulario`
     (~550 líneas).
- **Lo que NO hay que hacer:** mover y a la vez «mejorar» las consultas; el informe y el listado tienen
  presupuestos de queries (`--tag performance`). Primero se mueve, con re-exports; después se ajustan imports.
- **Tests a agregar:** ninguno nuevo; la suite `programas.tests.test_dispositivos_relevamientos*` y
  `test_inspecciones*` tienen que quedar idénticas.
- **Verificación:** `manage.py test programas` igual que la base; `wc -l` < 1000 en los cuatro módulos.
- **Regla para no repetirlo:** **control mecánico** · `core/tests/test_tamano_modulos.py` (nuevo) · ratchet: lista
  de archivos `.py` de `programas/{services,selectors,views}` con más de 1.000 líneas congelada al SHA de hoy;
  falla si aparece uno nuevo o si uno de la lista crece más de 50 líneas. Mensaje: «`<archivo>` pasa las 1.000
  líneas: partilo por responsabilidad antes de sumarle (rúbrica codigo-limpio, regla de las 1000)».

---

### D-FE-01 · El cuerpo del modal de egreso está copiado entre el detalle (P4) y la estadía (P7)
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** nuevo · **Ola:** 10 · **Esfuerzo:** S
- **ID de la pasada 1:** D1-FE-01
- **Ubicación:** `programas/templates/programas/dispositivos/legajo/detail.html:471-522` y
  `programas/templates/programas/dispositivos/estadia/detalle.html:184-236`. El modal hermano «Cambiar plaza» ya está
  extraído a `programas/dispositivos/_form_cambio_plaza.html` (`detail.html:460`, `estadia/detalle.html:172`).
- **Escenario:** los cinco campos de `EgresoForm` con sus `data-error`, el bloque del formulario del tipo y el aviso
  final están dos veces. El comentario de P7 (`:184`) lo admite: «mismo contrato que el de la solapa Estadías». Un
  campo nuevo en `EgresoForm`, o un `data-error` renombrado, se agrega en un modal y el otro pierde el error en su
  campo, que cae en `__all__` sin aviso.
- **Causa raíz:** cuando se extrajo `_form_cambio_plaza.html` no se hizo lo mismo con el egreso.
- **Solución:** `programas/dispositivos/_form_egreso.html` con el `<div class="px-6 py-6 …">` interno. Recibe
  `form_egreso`, `formulario_egreso` y, opcional, `resumen_ingreso` (la línea «Ingreso … · N días» que solo muestra
  P4). Cada pantalla conserva su envoltorio, su header y el `volver` oculto. El HTML que se renderiza es el mismo.
  Revisar `check_design_agent.py`: si el modal está fichado, la ficha va en el mismo diff.
- **Tests a agregar:** `programas/tests/test_dispositivos_egreso.py::ModalEgresoTests.test_p4_y_p7_tienen_los_mismos_data_error`.
- **Verificación:** `scripts/compile_templates.py --bloques` en 0 y `design_audit.py --ratchet` sin hallazgos nuevos.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-frontend.md`: «Un formulario que se dibuja en dos
  pantallas va en una parcial `_form_<accion>.html`; el modal (envoltorio y header) puede ser propio».

---

### D-FE-02 · `tipo_detail.html` lleva 175 líneas de JS inline que reimplementan, y contradicen, el handler `data-ajax` canónico
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** nuevo · **Ola:** 10 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D3-FE-01
- **Descartado de octubre (`README.md` §8.1, promover `_ajax_js`/`_modal_*` a `components/`):** esta ficha **no promueve `_ajax_js`**. El paso 2 usa el handler `data-ajax` canónico que ya cargan las pantallas de Dispositivos, sin moverlo a `components/` (resolución 6 de la sección 1). Si ese handler solo existiera en `programas/becas/`, se hace solo el paso 1.
- **Ubicación:** `templates/programas/dispositivos/config/tipo_detail.html:17-192`. Canónico: `templates/programas/becas/_ajax_js.html` (311 líneas).
- **Escenario:** el submit del modal de tipo no pone `aria-describedby` en los campos con error y bloquea el doble envío de forma más simple que el canónico. Cualquier arreglo de accesibilidad o de doble submit hecho en `_ajax_js` no llega a esta pantalla. Además trae su propio `getCookie` y su propio `showRequestError`.
- **Causa raíz:** la pantalla se escribió antes de que el handler fuera compartido, o lo copió y lo recortó.
- **Solución:** en dos pasos. (1) Mover el bloque tal cual a `static/custom/js/nodo-tipo-dispositivo.js`, sin cambiar conducta. (2) Reemplazar el submit propio por el handler `data-ajax` canónico que ya usan las pantallas de Dispositivos (sin promover nada a `components/`) y dejar en el archivo nuevo solo la apertura y el cierre del modal. El paso 2 cambia algo visible (los errores ganan `aria-describedby` y el foco va al primer campo), así que se valida con el agente de diseño.
- **Lo que NO hay que hacer:** no promover `_ajax_js` a components ni crear un ModernModal (descartado en §0.4).
- **Tests a agregar:** un test de template que verifique que `tipo_detail.html` no contiene `function getCookie` ni `addEventListener('submit'`.
- **Verificación:** `scripts/design_audit.py --ratchet` con 0 nuevos; prueba manual del alta y la edición de tipo con un error de validación.
- **Regla para no repetirlo:** control mecánico · `scripts/design_audit.py` · «Regla nueva: `<script>` inline de más de 40 líneas en un template del backoffice es un hallazgo; `function getCookie` fuera de los JS canónicos también.»

---

### D-FE-03 · `nodo-formulario-tipo.js` duplica `nodo-formulario.js` (link público de Becas) con divergencias
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** nuevo · **Ola:** 10 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D3-FE-02
- **Ubicación:** `static/custom/js/nodo-formulario-tipo.js:28-83` (`valorDe`, bucle `aplicar`) frente a `static/custom/js/nodo-formulario.js:37-96`.
- **Escenario:** una condición «mostrar si campo = X» se evalúa distinto en los dos productos. Dispositivos no hace trim y Becas sí, solo Becas excluye `.nodo-buscador__input`, y el fallback a `data-valor` es distinto. Un mismo diseño con un valor que trae espacios muestra la pregunta en Becas y la oculta en Dispositivos.
- **Causa raíz:** el evaluador de condiciones se copió en lugar de compartirse. La regla de negocio (cuándo se cumple una condición) quedó en dos lugares del front.
- **Solución:** extraer `valorDe` y `aplicar` a un módulo común (`nodo-condiciones.js`, función `aplicarCondiciones(raiz, opciones)`), que usen los dos archivos. Las tres divergencias pasan a ser opciones explícitas con el valor que hoy tiene cada uno, así no cambia nada. Unificar los valores (trim en los dos) es DECISIÓN CLIENTE: default = conservar cada conducta actual.
- **Lo que NO hay que hacer:** no cambiar en esta ola el criterio de trim de ninguno de los dos productos.
- **Tests a agregar:** si no hay harness JS, un test Django que renderice los dos formularios con un valor que lleva espacios y documente la conducta actual en un comentario.
- **Verificación:** prueba manual de una condición en el link público de Becas y en el formulario de ingreso de Dispositivos.
- **Regla para no repetirlo:** agente · `.claude/agents/chaco-design-system.md` · «La evaluación de condiciones de formularios dinámicos tiene un solo JS; no se escribe otro evaluador por producto.»

---

### D-FE-04 · Componente Alpine de ~55 líneas embebido en un atributo `x-data`, con nombres de acción duplicados entre Python y JS
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** (par de D-LIM-19) · **Ola:** 10 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D2-FE-01
- **Ubicación:** `programas/templates/programas/dispositivos/sectores/sectores.html:23-80` (estado, `fetch`, armado de fecha, `tituloPlaza()` con un diccionario `{reservar: …, prestar: …, fuera_servicio: …}`), `221-262` (`acciones.includes('reubicar' | 'ver_estadia' | …)`); `programas/services/sectores_plazas.py:92-108` (`ACCION_*` en Python)
- **Escenario:** el JS no se puede lintear, testear ni cachear; cada acción nueva exige tocar la constante Python, el diccionario de títulos JS y el `includes('…')` del menú, con strings sin vínculo entre sí. Un typo en `'fuera_servicio'` deja el botón invisible sin error.
- **Causa raíz:** el patrón «modal servidor + Alpine» de la golden se extendió inline en vez de en un módulo de `static/`.
- **Solución:** `static/custom/js/nodo-mapa-plazas.js` con `Alpine.data('mapaPlazas', (config) => ({…}))`; el template queda `x-data="mapaPlazas({{ config|json_script… }})"`. Los títulos del modal viajan del servidor en `datos_para_el_modal` (`"titulo"`), y los nombres de acción se exportan una vez (`ACCIONES` en `json_script`). Sin cambio visual.
- **Lo que NO hay que hacer:** moverlo a un `<script>` inline al pie (sigue sin lint y choca con CSP de `SecurityHeadersMiddleware` si se endurece).
- **Tests a agregar:** `programas/tests/test_sectores_plazas.py::ModalTests.test_payload_trae_titulo`; check de `scripts/design_audit.py` sobre la plantilla.
- **Verificación:** Playwright/receta de revisión visual sobre P5: menú, reservar, prestar, reubicar por AJAX y sin JS.
- **Regla para no repetirlo:** **control mecánico** · `scripts/design_audit.py` regla `XDATA-LARGO` · «atributo `x-data` con más de 15 líneas o que contiene `fetch(` → hallazgo: extraer a `Alpine.data` en `static/custom/js/`».

---

### D-SEG-03 · El historial expone un dato personal del responsable
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** SEG · **Origen:** nuevo · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** D1-SEG-02
- **Escenario:** El historial expone un dato personal del responsable que la ficha no muestra.
- **Detalle técnico:** Detalle técnico reservado hasta el arreglo; se agrega al informe con el PR que lo cierra.
- **Solución:** Reservada hasta el arreglo; propuesta por defecto: no mostrar el dato personal en el historial.
- **Tests a agregar:** Reservada hasta el arreglo.
- **Verificación:** Reservada hasta el arreglo.
- **Regla para no repetirlo:** **control mecánico** · regla R-4 (sección 4).

---

### D-SEG-04 · El historial muestra datos de relevamientos fuera de alcance
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** SEG · **Origen:** nuevo · **Ola:** 2 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D1-SEG-03
- **Escenario:** El historial muestra datos de un relevamiento a quien no tiene alcance sobre él.
- **Detalle técnico:** Detalle técnico reservado hasta el arreglo; se agrega al informe con el PR que lo cierra.
- **Solución:** Reservada hasta el arreglo; propuesta por defecto: aplicar al historial la misma regla de alcance que el detalle.
- **Tests a agregar:** Reservada hasta el arreglo.
- **Verificación:** Reservada hasta el arreglo.
- **Regla para no repetirlo:** **control mecánico** · regla R-4 (sección 4).

---

### D-SEG-05 · Una redacción por alcance se anula por otros caminos de lectura
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** SEG · **Origen:** decisión §4.11 · **Ola:** 2 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D2-SEG-01
- **Escenario:** Una redacción por alcance se anula por otros caminos de lectura.
- **Detalle técnico:** Detalle técnico reservado hasta el arreglo; se agrega al informe con el PR que lo cierra.
- **Solución:** Reservada hasta el arreglo; propuesta por defecto: DECISIÓN CLIENTE: aplicar la misma redacción por alcance en todos los puntos de lectura.
- **Tests a agregar:** Reservada hasta el arreglo.
- **Verificación:** Reservada hasta el arreglo.
- **Regla para no repetirlo:** **skill** · `seguridad-django` (datos personales) · «Una redacción por alcance se aplica en el selector, no en una pantalla.»

---

### D-SEG-06 · La API de campo no limita las cargas de archivos
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** SEG · **Origen:** nuevo · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** D4-SEG-02
- **Escenario:** La API de campo no limita la carga de archivos por usuario ni por relevamiento.
- **Detalle técnico:** Detalle técnico reservado hasta el arreglo; se agrega al informe con el PR que lo cierra.
- **Solución:** Reservada hasta el arreglo; propuesta por defecto: DECISIÓN CLIENTE: limitar las cargas por usuario y por objeto padre.
- **Tests a agregar:** Reservada hasta el arreglo.
- **Verificación:** Reservada hasta el arreglo.
- **Regla para no repetirlo:** **skill** · `.claude/skills/seguridad-django/` · «Todo endpoint de `/api/` que escribe un archivo declara un límite por usuario y por objeto padre.»

---

### D-SEG-07 · Una regla de separación entre agente e institución puede romperse
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** SEG · **Origen:** nuevo · **Ola:** 2 · **Esfuerzo:** S
- **ID de la pasada 1:** D4-SEG-03
- **Escenario:** Una regla de separación entre agente e institución puede romperse sin aviso.
- **Detalle técnico:** Detalle técnico reservado hasta el arreglo; se agrega al informe con el PR que lo cierra.
- **Solución:** Reservada hasta el arreglo; propuesta por defecto: DECISIÓN CLIENTE: validar la regla de separación en todas las operaciones que la pueden romper.
- **Tests a agregar:** Reservada hasta el arreglo.
- **Verificación:** Reservada hasta el arreglo.
- **Regla para no repetirlo:** **skill** · `.claude/skills/seguridad-django/` · «Una invariante entre dos agregados se verifica en todas las operaciones que la pueden romper.»

---

### D-ERR-05 · La edición del legajo responde 500 si dos personas guardan el mismo código a la vez
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** nuevo · **Ola:** 1 · **Esfuerzo:** S
- **ID de la pasada 1:** D1-ERR-03
- **Ubicación:** `programas/views/dispositivos_legajo.py:726-739` (`DispositivoUpdateView.form_valid`); comparar con `:310-314` (`DispositivoCreateView`)
- **Escenario:** dos ediciones concurrentes ponen el mismo `codigo`, que es `unique=True`
  (`models/__init__.py:590`). Las dos pasan `clean_codigo` y la segunda falla al guardar con
  `IntegrityError`. El alta lo captura y lo marca en el campo; la edición solo captura
  `ValidationError`, así que responde 500.
- **Causa raíz:** el manejo del choque de unicidad del alta no se copió a la edición.
- **Solución:** en `DispositivoUpdateView.form_valid`, agregar `except IntegrityError:
  form.add_error("codigo", "Ya existe un dispositivo con este código institucional."); return
  self.form_invalid(form)`, igual que el alta. `archivos_atomicos` ya revierte el archivo.
- **Tests a agregar:** `programas/tests/test_dispositivos_legajo.py::EdicionLegajo.test_codigo_duplicado_por_carrera_vuelve_al_form` (con `mock.patch` de `Dispositivo.save` que levanta `IntegrityError`)
- **Verificación:** con el test.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/errores.md` · «Si el alta captura `IntegrityError` de un campo único, la edición del mismo modelo también.»

---

### D-ERR-06 · Borrar un grupo del formulario por tipo puede arrastrar en cascada un campo que se movió a ese grupo al mismo tiempo (TOCTOU)
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** thermos-correccion · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** D3-ERR-01
- **Cruce con Becas:** el mismo patrón está en `programas/views/diseno.py:287` (Becas) y **no figura en `becas.md`** (B-ERR-29 es otro defecto, `services/diseno.py:283`). El arreglo es compartido con Becas; **Resolución del juez:** esta ficha cubre también la vista de Becas; la nota cruzada está en [becas.md](becas.md) (Ola 6) y no se abre ficha aparte del lado Becas.
- **No hacer:** pasar `ItemDiseno.padre` a PROTECT (descartado en octubre, A8-01 / Cambio 58, `README.md` §8.1). La solución es validar dentro de la operación que toma el candado.
- **Ubicación:**
- `programas/views/dispositivos_formularios.py:309-316` (`FormularioTipoItemEliminarView`).
- `programas/services/constructor.py:356-368` (`motivo_para_no_eliminar`).
- `constructor.py:228-252` (`mutar`, que toma `bloquear(diseno)`).
- `ItemDiseno.padre`, con `on_delete=CASCADE`.

El mismo patrón está en `programas/views/diseno.py:287` (Becas).

- **Escenario:**
1. Admin A pide borrar el grupo G, que está vacío. `motivo_para_no_eliminar` evalúa `item.hijos.exists()` antes del candado y le da False.
2. En ese momento, admin B mueve el campo C dentro de G, y `mutar` toma y libera el candado.
3. A entra a `mutar` y ejecuta `item.delete`.
4. Por el CASCADE se borra también C, sin aviso ni error.

- **Causa raíz:** la precondición se valida fuera de la sección crítica que protege la mutación.

- **Solución:** mover la validación dentro de la operación que se pasa a `mutar`. Esa función relee el ítem bajo el candado, recalcula `motivo_para_no_eliminar` y, si hay motivo, levanta `DisenoInvalido(motivo)`, que `mutar` ya traduce a un error JSON. El mensaje y la estética no cambian. Aplicar lo mismo en `views/diseno.py:287`.

- **Lo que NO hay que hacer:** cambiar `padre` a `PROTECT` en esta ola, porque es una migración y le cambia la semántica al constructor de Becas.

- **Tests a agregar:** un test de servicio que simule el cambio entre la validación y el borrado (mock o dos pasos) y verifique que el campo hijo sobrevive y que se devuelve el motivo.

- **Verificación:** los tests del constructor de Dispositivos y de Becas.

- **Regla para no repetirlo:** sumar a `.claude/skills/auditoria/rubricas/` (concurrencia): «Toda precondición de una mutación con candado se evalúa dentro de la operación protegida, nunca antes de tomar el candado».

---

### D-ERR-07 · El toggle de tipo de dispositivo no es idempotente: un doble POST deja el estado como estaba
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** fusión de D3-ERR-02 + D3-LIM-07; thermos-correccion · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** D3-ERR-02 + D3-LIM-07 (**hallado por 2 revisores**)
- **Hallado por 2 revisores (sube de peso):** D3-ERR-02 (el toggle de tipo no es idempotente: un doble POST deja el estado como estaba) y D3-LIM-07 (`TipoDispositivoToggleView` escribe el estado de dominio en la vista). Se arreglan a la vez: el servicio recibe el **estado deseado** (`activo=True/False`), no «invertir».
- **Parte del patrón «lógica de dominio en vistas»** (regla R-1).
- **Ubicación:** `programas/views/dispositivos_config.py:121-127` (`TipoDispositivoToggleView`, que hace `tipo.activo = not tipo.activo`).

- **Escenario:**
1. El admin confirma la desactivación con doble clic, o la red reenvía el POST.
2. El primer POST desactiva el tipo y el segundo lo reactiva.
3. La pantalla muestra el toast «desactivado» y el tipo sigue activo. Lo mismo pasa con dos admins en paralelo.

- **Causa raíz:** el POST no lleva el estado esperado. La vista invierte lo que lee, sin candado.

- **Solución:** mandar en el form de confirmación un campo oculto `activo=<estado destino>` y que la vista asigne ese valor (si ya está en ese estado, no hace nada y devuelve el mismo mensaje). Así no cambian ni el template visible ni el flujo de SweetAlert. La alternativa es `select_for_update` y comparar contra el estado esperado.

- **Lo que NO hay que hacer:** desactivar el botón solo por JS como única defensa.

- **Tests a agregar:** dos POST seguidos con `activo=0` dejan el tipo inactivo.

- **Verificación:** los tests de configuración de Dispositivos.

- **Regla para no repetirlo:** sumar a la rúbrica de corrección de `/auditoria`: «Los endpoints de alternar (toggle) reciben el estado destino, no invierten el estado leído».

#### Aporte del segundo revisor (D3-LIM-07: `TipoDispositivoToggleView` escribe estado de dominio en la vista)
_Pasada 1: severidad BAJA · estado CONFIRMADO (lectura) · esfuerzo S._

- **Ubicación:** `views/dispositivos_config.py:121-127`.
- **Escenario:** el toggle invierte `activo` sin estado destino. Dos pestañas que tocan «desactivar» dejan el tipo activo de nuevo, y no queda traza de quién lo cambió.
- **Causa raíz:** no existe `services/tipos_dispositivo.py`; la vista hace `obj.activo = not obj.activo; save()`.
- **Solución:** `cambiar_activo_tipo(tipo, activo: bool, usuario)` en un servicio, que la vista llame con el valor que manda el botón. Pasar el estado destino en el POST es un cambio de contrato menor (un hidden input) y no cambia la UI.
- **Lo que NO hay que hacer:** no agregar un modelo de auditoría nuevo para esto.
- **Tests a agregar:** dos POST «desactivar» seguidos dejan el tipo inactivo.
- **Verificación:** el test nuevo; prueba manual del toggle.
- **Regla para no repetirlo:** CLAUDE.md · «Patrón de capas» · «Una vista no hace `.save()` de un modelo de dominio: llama a un servicio.»

---

### D-ERR-08 · Un ingreso tipeado en el mismo minuto que un egreso previo se rechaza por los segundos
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** nuevo · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** D2-ERR-05
- **Ubicación:** `programas/forms_ingreso.py:106-112` contra `programas/forms_dispositivos.py:150-168` (`CambioPlazaForm.clean_momento`, que sí aplica `max(momento, ultimo)`); rechazo en `programas/services/estadias.py:384-402` y `:411-422`.
- **Escenario:** egreso registrado a las 14:30:41. El operador ingresa a alguien en esa plaza a las 14:30 tipeadas → el form da 14:30:00, anterior al egreso → «se superpone» / «plaza ocupada en el medio», aunque para el operador es el mismo minuto.
- **Causa raíz:** el form de ingreso trunca a minutos sin el ajuste que tiene el de cambio de plaza.
- **Solución:** en `IngresoConfirmarForm.clean_fecha_ingreso`, si la fecha cae en el mismo minuto que el último movimiento relevante, subirla a ese instante (patrón de `forms_dispositivos.py:150-168`).
- **Tests a agregar:** `programas/tests/test_ingreso.py::FechaIngreso.test_mismo_minuto_que_egreso_previo_se_acepta`.
- **Verificación:** test.
- **Regla para no repetirlo:** **agente** · `chaco-auditor` eje ERR · «Todo campo de fecha-hora a minuto que se compara contra momentos con segundos aplica el ajuste de `clean_momento`.»

---

### D-ERR-09 · Los servicios no validan que el tipo de plaza sea admitido por el tipo de dispositivo
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** nuevo · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** D2-ERR-06
- **Ubicación:** `programas/services/estadias.py:441-473` (`ingresar_persona`), `:646-695` (`cambiar_plaza`), `:732-794` (`asignar_plaza`), `:797-828` (`reservar_plaza`); `programas/services/ingreso.py:147` (filtro solo al armar las opciones).
- **Escenario:** si el tipo del dispositivo cambia, o una plaza quedó de un tipo que ya no admite, un POST con ese `plaza_id` aloja a la persona en una plaza que la UI nunca ofrecería.
- **Causa raíz:** `tipo.admite_tipo_de_plaza` se aplica al armar opciones, no en el servicio.
- **Solución:** en `_bloquear_plaza` (`estadias.py:313-336`), verificar `dispositivo.tipo.admite_tipo_de_plaza(plaza.tipo)` → `ValidationError`. Un solo punto cubre los cuatro caminos.
- **Tests a agregar:** `programas/tests/test_estadias.py::TipoDePlaza.test_rechaza_tipo_no_admitido`.
- **Verificación:** test con mutación.
- **Regla para no repetirlo:** **skill** · `seguridad-django` · «Un filtro de opciones en la UI siempre tiene su guarda en el servicio.»

---

### D-ERR-10 · `?tipo=` no numérico en el listado de instituciones da 500
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** nuevo · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** D1-ERR-02
- **Ubicación:** `programas/views/dispositivos_legajo.py:181-194` (`DispositivoListView._filtros` / `get_queryset`); `programas/services/reportes.py:42-43` (`filtrar_dispositivos`)
- **Escenario:** `GET /dispositivos/?tipo=abc` (un enlace viejo, un bot o un parámetro a mano).
  `filter(tipo_id="abc")` falla al preparar el valor («Field 'id' expected a number but got 'abc'»)
  con `ValueError` y responde 500. La exportación del padrón usa la misma función y tiene el mismo efecto.
- **Causa raíz:** el filtro pasa el GET crudo a un lookup sobre un entero. El módulo ya tiene `_entero`
  (`:852-857`) para esto, pero el listado no lo usa.
- **Solución:** en `_filtros`, `"tipo": _entero(self.request.GET.get("tipo", "")) or ""`. Lo mismo
  en la vista de exportación que arma esos filtros. Un tipo inválido se ignora, como ya pasa con un
  `estado` desconocido, que no da error.
- **Tests a agregar:** `programas/tests/test_dispositivos_legajo.py::ListadoFiltros.test_tipo_no_numerico_no_da_500`
- **Verificación:** con el test (200 y el listado sin filtrar por tipo).
- **Regla para no repetirlo:** **control mecánico** · `programas/tests/test_arquitectura.py` · test que busca `filter(<campo>_id=self.request.GET` o un `GET.get(...)` que llegue a un `*_id=` sin pasar por `_entero`/`int` validado (ratchet).

---

### D-ERR-11 · Con la sesión vencida, el formulario del tipo se reemplaza por la pantalla de login
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** nuevo · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** D1-ERR-05
- **Ubicación:** `programas/views/dispositivos_legajo.py:362-374` (`DispositivoFormularioTipoView`, solo `LoginRequiredMixin`); `programas/templates/programas/dispositivos/legajo/form.html:229-232`
- **Escenario:** la sesión vence con el alta abierta y el usuario cambia el tipo. El `fetch` sigue el
  302 de `LoginRequiredMixin` a `/login/`, que responde 200. `respuesta.ok` es verdadero y
  `seccion.innerHTML` recibe la página de login completa dentro del formulario (con su propio
  `<form>` y su CSRF anidados). Al guardar, el POST lleva campos del login mezclados y la sección
  del tipo se pierde sin aviso.
- **Causa raíz:** la vista no usa el contrato AJAX de sesión vencida (401 + `redirect`) que sí tienen
  `DispositivoProgramaPermissionMixin` y `ConfigurarDispositivosMixin` (`mixins_dispositivos.py:57-68`),
  y el JS no mira `respuesta.redirected`.
- **Solución:** en `form.html`, `if (!respuesta.ok || respuesta.redirected) throw new Error(...)`, lo
  que ya cae en el `catch` existente con su toast. Si además se quiere el redirect al login, en la vista
  devolver el mismo 401 JSON cuando `is_ajax(request)` y el usuario no está autenticado.
- **Tests a agregar:** `programas/tests/test_dispositivos_legajo.py::FormularioTipo.test_anonimo_ajax_no_devuelve_login_200` (si se toca la vista)
- **Verificación:** con el test, o en la pantalla borrando la cookie de sesión y cambiando el tipo.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-frontend.md` · «Un `fetch` que inyecta HTML con `innerHTML` comprueba `respuesta.ok && !respuesta.redirected`: un 302 al login llega como 200.»

---

### D-ERR-12 · Entradas sin tope en el resultado de campo terminan en 500 en MariaDB estricto
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** nuevo · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** D4-ERR-02
- **Ubicación:** `programas/api/serializers_inspecciones.py:106` (`observaciones` sin `max_length`), `:118-123`
  (`version_capturada` con `min_value=0` y sin `max_value`), `:107-117` (`respuestas` sin tope de claves);
  destino: `InspeccionEdificio.observaciones = TextField` (TEXT, 65.535 bytes), `RespuestasRelevamiento.version_capturada =
  PositiveIntegerField` (`integer UNSIGNED`, máx. 4.294.967.295), `RespuestasRelevamiento.observaciones_carga = TextField`
  que suma una línea por clave desconocida (`programas/services/respuestas_dispositivo.py:421-433`);
  `config/settings.py:393` (`sql_mode='STRICT_TRANS_TABLES'`). Mismo patrón en el backoffice:
  `programas/forms_dispositivos.py:344-348` (`indicaciones` sin `max_length` → `TextField`).
- **Escenario:** `POST /api/dispositivos/inspecciones/{id}/resultado/` con `observaciones` de 70 KB (dentro de
  `DATA_UPLOAD_MAX_MEMORY_SIZE = 5 MB`), o `version_capturada = 5000000000`, o `respuestas` con ~2.000 claves que el
  formulario no conoce (cada una agrega «La respuesta «…» ya no pertenece…» a `observaciones_carga`). El serializer lo
  acepta, `save()`/`create()` no pasa por `full_clean`, MariaDB contesta 1406 «Data too long» o 1264 «Out of range» y
  sale **500** (la transacción vuelve atrás, no queda dato corrupto). Si la cola de la app reintenta los 5xx, ese envío
  no sale nunca (eso último depende de `Chaco-mobile`). El modal de asignar del backoffice da el mismo 500 con
  indicaciones de más de 64 KB.
- **Causa raíz:** los límites de la columna no están en la frontera de entrada; el modo estricto convierte el desborde
  en excepción de base en vez de un 400 legible.
- **Solución:** sin cambiar el comportamiento normal: `observaciones = CharField(..., max_length=16000)` (16.000
  caracteres × 4 bytes utf8mb4 < 65.535); `version_capturada = IntegerField(..., max_value=2147483647)`; en
  `ResultadoInspeccionSerializer.validate_respuestas`, rechazar más de `settings.DATA_UPLOAD_MAX_NUMBER_FIELDS` (500)
  claves o claves de más de 60 caracteres (el largo de `AdjuntoRespuestaRelevamiento.clave`). En
  `AsignarRelevamientoForm.indicaciones`, `max_length=16000`. Los cuatro salen como 400 por `_respuesta_400` / el form.
- **Tests a agregar:** `programas/tests/test_api_inspecciones.py::Limites.test_observaciones_largas_400`,
  `::test_version_capturada_fuera_de_rango_400`, `::test_respuestas_con_demasiadas_claves_400`.
- **Verificación:** con los tests (400 con `detail`), y el caso de 70 KB contra el banco MariaDB del job ida y vuelta.
- **Regla para no repetirlo:** **control mecánico** · `programas/tests/test_arquitectura.py` · ratchet que recorre los
  `serializers.Serializer` de `programas/api/` y falla si un `CharField` sin `max_length` o un `IntegerField` sin
  `max_value` se escribe en un `TextField`/`PositiveIntegerField` (mensaje: «STRICT_TRANS_TABLES lo convierte en 500:
  poné el tope en el serializer»).

---

### D-PERF-03 · `/media/` busca el adjunto de la bitácora y de los formularios del dispositivo por la ruta, en columnas sin índice: un scan completo por cada archivo servido
**Severidad:** MEDIA · **Estado:** MEDIDO en banco · **Eje:** PERF · **Origen:** (el mismo patrón alcanza a todos los resolvers de `core/views/media.py`; si otra tajada lo registra para Becas o Legajos, consolidar en una sola ficha) · **Ola:** 4 · **Esfuerzo:** S-M
- **Medición en banco (19-nov-2026):** `/media/…bitacora/…` y `/media/…rel-…`: 361 / 459 ms frío, 126 / 155 ms caliente (7 / 9 consultas). La consulta por `archivo` no tiene índice: sobre `AdjuntoRespuestaRelevamiento` hace `type=ALL` en 198.660 filas (343-360 ms) y sobre la bitácora tarda 250-328 ms. **Sube a MEDIA** (primera medición; la segunda no la repitió).
- **ID de la pasada 1:** D3-PERF-01
- **Cruce con otros capítulos:** ni Becas ni Emergencia registran esta consulta. Es **transversal**: `core/views/media.py` sirve los adjuntos de los tres módulos (incluido `AdjuntoRespuestaRelevamiento`, de Becas). Ficha propia aquí; el índice o la ruta con id aplica a todos.
- **Ubicación:** modelos sin índice en `archivo`: `programas/models/__init__.py:1740` (`AdjuntoBitacora`), `:4969` (`AdjuntoRespuestaAlta`), `:5013` (`AdjuntoRespuestaIngreso`), `:5056` (`AdjuntoRespuestaEgreso`) y `:5113` (`AdjuntoRespuestaRelevamiento`). Consultas: `core/views/media.py:227` (`_adjunto_de_bitacora`), `:299` y `:304` (`_archivo_de_formulario_dispositivo`: un archivo del relevamiento recorre primero **toda** `AdjuntoRespuestaAlta` y después toda `AdjuntoRespuestaRelevamiento`, porque comparten prefijo) y `:321-322` (`_archivo_de_formulario_estadia`: un archivo de egreso recorre primero toda `AdjuntoRespuestaIngreso`).
- **Escenario:** el detalle de una novedad (`bitacora/entrada.html`) dibuja cada imagen adjunta como `<img>`, y la pantalla del turno lista hasta 50 entradas con sus adjuntos como enlaces. Cada imagen o descarga es un `GET /media/…` que corre `WHERE archivo = %s` sobre una `varchar(100)` sin índice: `type: ALL` sobre la tabla entera de adjuntos de **todos** los dispositivos. Las tablas crecen con el histórico y nunca se purgan (las entradas no se borran: `EntradaBitacora.delete` falla). Con decenas de miles de filas son decenas de milisegundos por imagen, multiplicados por las imágenes de la página; lejos todavía de los 10 s. La tabla que más crece es `AdjuntoRespuestaRelevamiento` (fotos de la app de campo), que además paga el scan previo de `AdjuntoRespuestaAlta`.
- **Causa raíz:** la autorización de `/media/` resuelve la fila dueña por la ruta guardada (`FileField`), y Django no indexa un `FileField`. Los modelos se diseñaron mirando sus lecturas por FK (todas indexadas) y no esta lectura por ruta.
- **Solución:** `models.Index(fields=["archivo"])` en los cinco modelos (migración expand, sin datos: un `AddIndex` por modelo, que en MariaDB 10.11 es un `ALTER TABLE … ADD INDEX` en línea). La consulta de `media.py` no cambia: el `archivo = %s` pasa a `ref`. Comportamiento y pantallas idénticos.
- **Lo que NO hay que hacer:** buscar por `archivo__endswith` o normalizar la ruta en el `WHERE` (anula el índice, trampa 5 de la rúbrica); ni reordenar los resolvers de `REGLAS` para adivinar la tabla (el orden por prefijo es contrato de `test_media_protegida.CoberturaDePrefijosTests`).
- **Tests a agregar:** `core/tests/test_media_protegida.py::IndicesDeRutaTests.test_todo_filefield_resuelto_por_ruta_tiene_indice` (recorre `REGLAS` y, para cada modelo consultado por `archivo=`, exige un índice cuyo primer campo sea ese).
- **Verificación:** en el banco MariaDB (3310), sembrar 50.000 `AdjuntoBitacora` y 200.000 `AdjuntoRespuestaRelevamiento`, y `ANALYZE FORMAT=JSON SELECT … FROM programas_adjuntobitacora WHERE archivo = '…'` antes (`ALL`, `rows` ≈ tabla) y después (`ref`, `rows` = 1). Medir además `perfil_ruta.py` sobre `/media/<ruta de un adjunto de relevamiento>` para ver los dos scans encadenados de `:299` y `:304`.
- **Regla para no repetirlo:** **control mecánico** · test en `core/tests/test_media_protegida.py` · «Todo modelo que un resolver de `core.views.media.REGLAS` consulta con `filter(<campo>=ruta)` tiene un `models.Index` cuyo primer campo es ese `FileField`. Mensaje: "`<Modelo>.<campo>` se resuelve por ruta en /media/ y no tiene índice: cada archivo servido recorre la tabla."»

---

### D-PERF-04 · P21 recorre el histórico entero de relevamientos unas 8 veces por carga, con un predicado de alcance que no usa índice
**Severidad:** BAJA · **Estado:** MEDIDO en banco · **Eje:** PERF · **Origen:** nuevo · **Ola:** 4 · **Esfuerzo:** S-M
- **Medición en banco (19-nov-2026):** P21 `/dispositivos/relevamientos/` admin / coordinador: 1.034 / 829 ms calientes en la primera medición (SQL 891 / 672 ms, `ALL` sobre 5.000 edificios con filesort) y 610 ms el admin en la segunda (SQL 327 ms) tras `ANALYZE TABLE`. Queda BAJA.
- **ID de la pasada 1:** D4-PERF-01
- **Ubicación:** `programas/views/dispositivos_relevamientos.py:275-352` (`RelevamientoListView.get_context_data`),
  `:520-523` (`_preparar_modales`); `programas/services/inspecciones.py:159-202` (`_edificios_de`,
  `edificios_en_alcance`, `inspecciones_visibles`), `:821-843` (`resumen_listado`);
  `programas/models/__init__.py:2161-2166` (índices de `InspeccionEdificio`).
- **Escenario:** un coordinador sin `programa.configurar` abre `/dispositivos/relevamientos/`. Sobre
  `inspecciones_visibles(user)` la pantalla arma el aggregate de `resumen_listado` (1), las cuatro páginas de solapa
  (4) y la píldora de agentes (1); aparte vuelve a componer `edificios_en_alcance` para `en_alcance` (1),
  `edificios_para_asignar` (2) y `gestionables` si hay modal. Cada consulta sobre relevamientos lleva el WHERE de
  `inspecciones_visibles`: edificio_id IN (vínculos WHERE dispositivo_id IN (Dispositivo WHERE pk IN (Miembro … AND
  EXISTS(auth_user_groups …) AND permiso …))) OR asignado_a_id = u OR edificio_id IN (el mismo árbol con
  dispositivos_operados). Bajo un OR, MariaDB y MySQL no convierten el IN en semi-join: materializan cada subconsulta
  y recorren toda `programas_inspeccionedificio`. Las páginas de solapa además filtran por `estado` y ordenan por
  `fecha_vencimiento`, `realizada_en`, `revisado_en` o `modificado`, y no hay índice que empiece por `estado` (los dos
  existentes empiezan por `edificio` y por `asignado_a`): para el admin (`InspeccionEdificio.objects.all()`) es
  type=ALL + Using filesort sobre todo lo realizado o cancelado para quedarse con 25. El costo de cada carga crece
  lineal con el histórico, que no se purga.
- **Causa raíz:** el alcance se expresa como subconsulta anidada y se recompone en cada queryset en vez de resolverse
  una vez por request; y la unión de tres caminos (`reduce(or_, caminos)`) saca al optimizador del camino indexado. Es
  el patrón «IN anidados» de la skill `mysql-mariadb` (trampa 4), con volumen chico.
- **Solución:** resolver el alcance una vez por request y reusarlo como lista de ids. En
  `RelevamientoListView.get_context_data`, `ids_alcance = list(edificios_en_alcance(user, CAP_ASIGNAR).values_list(...))`
  (cientos de ids como mucho), y que `inspecciones_visibles` acepte opcionalmente los ids ya resueltos de cada camino
  (o un helper que devuelva los tres conjuntos y arme `Q(edificio_id__in=ids) | Q(asignado_a=user)`). `en_alcance`,
  `asignaciones_visibles` y `gestionables` usan el mismo conjunto. Mismas filas, mismo orden, mismas reglas: no cambia
  lógica ni estética. Índices (estado, realizada_en) y afines solo si el banco los pide.
- **Lo que NO hay que hacer:** no partir `inspecciones_visibles` en tres consultas con UNION sin cuidar duplicados (un
  relevamiento propio y del alcance saldría dos veces); no cachear el alcance entre requests (cambia al tocar el Equipo
  o los roles y abriría lo que se quitó).
- **Tests a agregar:** `programas/tests/test_dispositivos_relevamientos_listado.py::RelevamientoListadoPresupuestoTests.test_alcance_se_resuelve_una_vez`
  (coordinador no admin, 2 y 200 relevamientos, mismo número de consultas).
- **Verificación:** banco MariaDB (3310) con 5.000 edificios y 50.000 inspecciones: EXPLAIN de la página «Completados»
  y del aggregate antes y después (type, rows, Using filesort) y tiempo total de P21 con `perfil_ruta.py`, para un
  coordinador no admin y para el admin. Si queda debajo de 100 ms a ese volumen, la ficha baja a INFO.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` §Consultas · «Un alcance que se usa
  en más de una consulta de la misma pantalla se resuelve una vez a lista de ids (values_list + list) y se pasa:
  componerlo en cada queryset repite el árbol de IN anidados y, unido con OR, saca al optimizador del índice.»

---

### D-PERF-05 · Las alertas de reservas y préstamos vencidos no tienen tope: una por cada reserva olvidada, para siempre
**Severidad:** BAJA · **Estado:** PLAUSIBLE (depende de cuántas reservas se dejan sin liberar en producción) · **Eje:** PERF · **Origen:** nuevo · **Ola:** 4 · **Esfuerzo:** S
- **Medición en banco (19-nov-2026):** no medida por ruta: con 200 reservas vencidas sembradas el conteo de bloques `role="status"` es una verificación de pantalla. Queda como está.
- **ID de la pasada 1:** D1-PERF-02
- **Ubicación:** `programas/services/alertas_dispositivos.py`, función `reservas_vencidas` (el
  `for reserva in reservas: yield Aviso(...)` sin límite), consumida por
  `programas/services/detalle_dispositivo.py:268-284` y dibujada en
  `programas/templates/programas/dispositivos/legajo/detail.html:96-98` (un `_alerta.html` por aviso, en el
  encabezado de todas las solapas).
- **Escenario:** una reserva o préstamo `VIGENTE` con `hasta` pasado no se cierra solo (no hay cron; solo
  `liberar_reserva` o el consumo al ingresar la pasan a `LIBERADA`/`CONSUMIDA`, `programas/services/estadias.py:512`
  y `:951`), y la plaza vuelve a poder reservarse porque `que_toman()` descarta las vencidas
  (`estadias.py:296`). Un dispositivo que presta plazas de 12/24 h y no registra la devolución suma una fila por
  préstamo: a dos por día, ≈700 al año. Cada una es un bloque de alerta completo arriba del detalle. La consulta
  en sí va por el índice `(plaza, estado)` y es barata; lo que crece es el HTML y el trabajo de template en cada
  apertura del detalle, y la pantalla queda enterrada bajo las alertas.
- **Causa raíz:** la regla emite una alerta por origen; la de plazas fuera de servicio, en el mismo archivo, ya
  resuelve el mismo problema con una sola alerta que nombra hasta `MAX_PLAZAS_NOMBRADAS` y dice «y N más».
- **Solución:** DECISIÓN CLIENTE: agrupar las vencidas en una sola alerta por tipo («N préstamos vencidos sin
  liberar: P-01 · Sector A, … y N más»), con el mismo patrón y tope que `plazas_fuera_de_servicio` y el mismo
  enlace al mapa. Propuesta por defecto: agrupar a partir de 3 vencidas; con 1 o 2, la alerta individual de hoy.
  Cambia el texto del encabezado, por eso no se aplica sin el visto bueno.
- **Lo que NO hay que hacer:** cortar la consulta con `[:N]` sin decirlo (esconde reservas abiertas que hay que
  liberar).
- **Tests a agregar:** `programas/tests/test_dispositivos_alertas.py::ReservasVencidasTests.test_muchas_vencidas_una_sola_alerta`
  (si el cliente lo aprueba).
- **Verificación:** sembrar 200 `ReservaPlaza` `VIGENTE` con `hasta` en el pasado sobre un dispositivo y abrir
  `/dispositivos/<pk>/`: hoy 200 bloques `role="status"`; después, uno.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas
  activas · «Las reglas de aviso (`core.services.vencimientos`) cuyo origen se acumula sin cierre automático
  emiten una alerta agregada con tope, no una por fila: el encabezado de una pantalla no es un listado
  paginado.»

---

### D-DAT-01 · Las trazas y la bitácora del historial no tienen índice que sirva al orden: cada detalle recorre toda la historia del dispositivo
**Severidad:** ALTA · **Estado:** MEDIDO en banco · **Eje:** DAT · **Origen:** nuevo · **Ola:** 4 · **Esfuerzo:** S-M
- **Medición en banco (19-nov-2026):** `/dispositivos/1/` (página 1): 3.807 / 2.429 ms en la primera medición y **6.141 ms** caliente en la segunda, 44 consultas. Con el dispositivo grande en el 16,8 % de `Estadia` y el 19,9 % de `MovimientoEstadia` (120.304 estadías y 498.000 movimientos en total) la consulta de `Estadia` sigue en `type=ALL` sobre 121.041 filas con `Using temporary; Using filesort` (3,1 s): sin índice útil, y crece con la historia total, no con la del dispositivo. **Sube a ALTA.** Lo que señala el EXPLAIN es la consulta de estadías y movimientos del detalle; el índice de trazas y bitácora que describe esta ficha va en la misma ola y se verifica con el mismo EXPLAIN.
- **ID de la pasada 1:** D1-DAT-01
- **Regla de octubre (`README.md` §8.1, índice «solo de orden» sin número):** sin el `EXPLAIN` de la pasada 2 esta ficha baja a INFO. Se mantiene BAJA solo porque va junto con D-PERF-01 (el arreglo del historial) y su costo es el de una migración *expand*.
- **Ubicación:** `programas/models/__init__.py:818-823` (`TrazaDispositivo.Meta`: sin `indexes`, solo el índice
  implícito de la FK `dispositivo_id`) y `programas/models/__init__.py:1949-1952` (`EntradaBitacora.Meta`: solo
  `(dispositivo, fecha_operativa, turno)`); consultas en `programas/selectors/auditoria_dispositivo.py:322-325`
  y `:343-345`, ejecutadas en **cada** carga del detalle (`dispositivos_legajo.py:438`: la solapa se arma
  aunque no esté abierta) y en `programas/services/alertas_dispositivos.py` (`sin_turnos`: `TrazaDispositivo`
  por `accion="VALIDADO"` ordenado por `-creado_en`).
- **Escenario:**
  - `TrazaDispositivo WHERE dispositivo_id=? AND accion NOT IN (4 ESTADIA_*) ORDER BY creado_en DESC, id DESC
    LIMIT 20` y su `COUNT`: con solo el índice de la FK, el motor lee **todas** las trazas del dispositivo
    (incluidas las `ESTADIA_*`, que se escriben una por movimiento y después se descartan), con lookup a la
    fila para leer `accion`, y hace filesort para el `LIMIT 20`. ≈1.000 filas de promedio; un parador grande,
    decenas de miles, en cada apertura del detalle.
  - `EntradaBitacora WHERE dispositivo_id=? AND version>1 ORDER BY creado DESC, id DESC` y su `COUNT`: el índice
    `(dispositivo, fecha_operativa, turno)` da el rango por dispositivo pero no tiene `version`, así que el
    `COUNT` de correcciones hace un lookup por **cada** novedad del dispositivo (la bitácora suma varias por
    turno, todos los días).
  - `MovimientoEstadia` sí tiene `(dispositivo, momento)` y `TrazaInspeccion` `(inspeccion, creado_en)`: esas dos
    fuentes no entran en la ficha.
- **Causa raíz:** los índices de esas tablas se pensaron para la pantalla del turno y el censo, no para el
  orden por fecha del historial (#699), que llegó después.
- **Solución:** una migración solo de esquema (expand, sin datos, reversible):
  `TrazaDispositivo.Meta.indexes = [models.Index(fields=["dispositivo", "creado_en"], name=...)]` (InnoDB
  agrega el `id` al final del secundario, así que sirve al `ORDER BY creado_en DESC, id DESC` con un recorrido
  hacia atrás, en MySQL 8 y en MariaDB 10.11), y en `EntradaBitacora` `models.Index(fields=["dispositivo",
  "version"], name=...)`, que deja el `COUNT` de correcciones index-only y el `SELECT` con filesort solo sobre
  las correcciones (pocas). `AddIndex` sobre 200.000 filas es `ALGORITHM=INPLACE, LOCK=NONE` en los dos motores:
  segundos, sin bloquear escrituras; `check_migraciones.py` no pide marcas para un `AddIndex`. No cambia
  comportamiento ni pantalla.
- **Lo que NO hay que hacer:** agregar el índice sin el `EXPLAIN` antes y después (cada índice cuesta escritura
  en tablas que se escriben en cada movimiento); declararlo descendente (`-creado_en`): MariaDB anterior a 10.8
  lo ignora y no hace falta.
- **Tests a agregar:** ninguno de comportamiento; `makemigrations --check` y el job `Migrate ida y vuelta` lo
  cubren.
- **Verificación:** en el banco, con la siembra de abajo, `EXPLAIN` de las dos consultas (el SQL sale de
  `str(FeedAuditoria(d).fuentes[i][1][:20].query)`): hoy se espera `key` = índice de la FK,
  `rows` ≈ trazas del dispositivo, `Extra: Using where; Using filesort`; después `key` = índice nuevo, sin
  filesort en la traza y `Using index` en el `COUNT` de correcciones. Medir también
  `perfil_ruta.py "/dispositivos/<pk_grande>/"` (página 1, la de todos los días).
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas
  activas · «Toda consulta nueva con `ORDER BY <fecha> DESC LIMIT` sobre una tabla de auditoría o bitácora
  (solo-aditiva) tiene un índice `(fk_de_filtro, fecha)`; una traza que se filtra por FK y se ordena por fecha
  sin él hace filesort sobre toda la historia del padre en cada pedido.»

---

### D-LIM-31 · Las vistas reacomodan la salida del servicio y deciden la privacidad
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 5 · **Esfuerzo:** S
- **ID de la pasada 1:** D3-LIM-06
- **Regla transversal «lógica de dominio en vistas» (R-1):** las vistas reacomodan la salida del servicio y deciden la privacidad. Cruces: Becas ola 7 y Emergencia E-LIM-01.
- **Ubicación:** `views/dispositivos_bitacora.py:94-116` (arma `corregibles_datos`/`turnos_datos` desde la salida de `pantalla_bitacora`), `:247` y `:277-284` (la regla de mostrar personas solo con `ciudadano.ver` vive en la vista), y las migas duplicadas en `:126-130` y `:154-159`.
- **Escenario:** otro canal (la API de la app de campo, un export) que consuma la bitácora tiene que repetir el gate de privacidad o se olvida de él.
- **Causa raíz:** el servicio de pantalla devuelve modelos y la vista termina de darles forma.
- **Solución:** que `pantalla_bitacora` reciba `puede_ver_personas` y devuelva ya `corregibles_datos`/`turnos_datos`; la vista solo calcula el booleano con `puede(user, "ciudadano.ver")` y lo pasa. Una función `_migas(dispositivo, actual)` para las dos listas.
- **Lo que NO hay que hacer:** no mover el chequeo RBAC al template.
- **Tests a agregar:** el contexto, con y sin `ciudadano.ver`, no incluye o incluye los nombres de las personas.
- **Verificación:** tests de la vista en verde; HTML idéntico.
- **Regla para no repetirlo:** skill · `rubricas/codigo-limpio.md` · «Una vista no transforma estructuras del servicio: si necesita otro formato, el servicio lo devuelve.»

---

### D-LIM-32 · Tres gates de sesión y permiso casi iguales, y `reportes` importa el mixin por la vista
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** relacionado con E-LIM-01 · **Ola:** 6 · **Esfuerzo:** S
- **ID de la pasada 1:** D1-LIM-14
- **Cruce con Emergencia:** la compuerta «403 sin la capacidad, 404 sin alcance» está implementada dos veces con mecánicas distintas (E-LIM-03). `GuardiaView` (Emergencia) hereda del mismo mixin que se arregle aquí.
- **Ubicación:** `programas/mixins_dispositivos.py:56-68` y `:124-136`: el 401 JSON de «Tu sesión venció» copiado,
  con mensajes 403 que ya difieren («No tenés permiso…» en `:72` y «No tiene permisos…» en `:140`).
  `programas/views/emergencia_dispositivo.py:79-94` (`GuardiaView.dispatch`) arma un tercer gate (autenticado →
  capacidad → `dispositivo_operable_o_404`) sin la respuesta AJAX del mixin. `programas/views/reportes.py:12` importa
  `DispositivoProgramaPermissionMixin` desde `views.dispositivos_legajo`. Eso obliga al re-export con `noqa`
  (`dispositivos_legajo.py:45-50`) y a la excepción del ratchet (`programas/tests/test_arquitectura.py:84`), aunque el
  mixin ya vive en `mixins_dispositivos.py` justamente para evitarlo (su docstring, `:1-8`).
- **Escenario:** un cambio en la respuesta de sesión vencida (por ejemplo, agregar `code`) se aplica en un mixin y
  no en el otro. La guardia, ante un POST AJAX sin capacidad, devuelve el HTML del 403 en vez del JSON.
- **Causa raíz:** cada mixin se escribió entero, sin un núcleo común.
- **Solución:** `_GateDispositivosMixin` con `_no_autenticado(request)` y `_prohibido(request, mensaje)`, del que
  heredan los dos mixins (mismos textos que hoy). `reportes.py` importa desde `programas.mixins_dispositivos`, y se
  borran la línea `("reportes", "dispositivos_legajo")` del ratchet y el re-export. `GuardiaView` puede heredar de
  `DispositivoProgramaPermissionMixin` con `capacidad_requerida = CAP_ADMITIR` y conservar su `preparar`.
- **Tests a agregar:** `programas/tests/test_arquitectura.py`: la excepción desaparece y el ratchet baja.
- **Verificación:** `test_arquitectura` en verde con una dependencia menos.
- **Regla para no repetirlo:** **control mecánico** · `test_arquitectura.py` · ya existe: bajar el contador.

---

### D-LIM-33 · El parseo de un id de GET está reescrito con cuatro reglas distintas (9 copias en el repo)
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 6 · **Esfuerzo:** S
- **ID de la pasada 1:** D1-LIM-08
- **Ubicación:** `programas/views/dispositivos_legajo.py:852-857` (`_entero`, ASCII + decimal) y `:587` (la misma
  regla inline, a 300 líneas del helper). `programas/services/detalle_dispositivo.py:172` (otra vez inline) y
  `:739-742` (`int()` con `try`, que acepta dígitos no ASCII y espacios). `programas/views/emergencia_dispositivo.py:139,395,410`
  (`isdecimal()` sin `isascii()`). La regla `isascii() and isdecimal()` está copiada en 9 archivos de `core` y
  `programas` (incluidos `forms.py`, `forms_dispositivos.py`, `dispositivos_capacidad.py`, `dispositivos_ingreso.py`
  y `dispositivos_relevamientos.py`).
- **Escenario:** el comentario de `:853-854` explica el bug que la regla evita: «un superíndice o un dígito arábigo
  pasan `isdigit()` y rompen `int()`». Tres de las copias no la cumplen igual. Hoy no da 500 porque `isdecimal()`
  rechaza superíndices e `int()` acepta los dígitos arábigos. Pero el contrato de «mismo 404 para todo id inválido»
  depende de qué copia se usó.
- **Causa raíz:** no hay un helper canónico en `core`.
- **Solución:** `core/http.py::entero_de_parametro(valor) -> int | None` (el cuerpo de `_entero`). Reemplazar las
  copias, empezando por las de este alcance. `normalizar_filtros` e `infraestructura_del_dispositivo` lo usan
  para `sector` y `edificio_id`.
- **Tests a agregar:** `core/tests/test_http.py::EnteroDeParametroTests` (superíndice, arábigo, espacios, vacío,
  `None`).
- **Verificación:** `grep -rn "isdecimal()" programas core --include=*.py | grep -v tests` da solo el helper.
- **Regla para no repetirlo:** **control mecánico** · `test_arquitectura.py` · ratchet sobre la cantidad de
  `.isdecimal()` fuera de `core/http.py` (hoy, 9 archivos más 3 en Emergencia).

---

### D-LIM-34 · `UsuarioNoSumable` lleva un status HTTP: el servicio conoce el protocolo
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 6 · **Esfuerzo:** S
- **ID de la pasada 1:** D3-LIM-09
- **Ubicación:** `services/sumar_agente.py:191-197` (atributo `estado` 403/409); el texto «Está inactivo…» repite `MOTIVO_AGENTE_INACTIVO` de `services/buscador_agentes.py:56`.
- **Escenario:** un caller que no es HTTP (comando, API móvil) recibe códigos de transporte, y el texto del motivo inactivo puede divergir entre el buscador y el alta.
- **Causa raíz:** atajo para que la vista no tenga que mapear motivos.
- **Solución:** la excepción lleva un `motivo` enumerado (`INACTIVO`, `SIN_PERMISO`, `YA_ES_MIEMBRO`); la vista mapea motivo → status en un dict. El texto sale de `MOTIVO_AGENTE_INACTIVO`.
- **Lo que NO hay que hacer:** no cambiar los status ni los textos que ve el usuario.
- **Tests a agregar:** por cada motivo, mismo status y mismo texto que hoy.
- **Verificación:** tests de la vista de sumar agente.
- **Regla para no repetirlo:** skill · `rubricas/codigo-limpio.md` · «Una excepción de servicio no lleva status HTTP.»

---

### D-LIM-35 · `dispositivos_equipo.py` importa un helper privado de una vista de otra app y usa excepciones como control de flujo
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 6 · **Esfuerzo:** S
- **ID de la pasada 1:** D3-LIM-08
- **Ubicación:** `views/dispositivos_equipo.py:31` (importa `_campo_en_colision` y `MENSAJES_COLISION` de `users/views/quick_create.py`); `:90`, `:124` (errores del form convertidos en `ValidationError`); `:76` (sin AJAX muestra solo `error.messages[0]`); `:88`, `:124` (`self.form` como estado mutable); `:155-170` (`_errores_del_alta` con mapeo de alias).
- **Escenario:** un refactor de `quick_create.py`, que hoy solo usan él mismo (`:390`) y esta vista (`:148`), rompe Dispositivos sin que el ratchet vista→vista de `test_arquitectura.py` lo vea, porque ese ratchet solo mira aristas dentro de `programas/views/`.
- **Causa raíz:** la detección de colisión de índice único es lógica de servicio que quedó en una vista.
- **Solución:** mover `_clave_rota`, `_campo_en_colision` y `MENSAJES_COLISION` a `users/services/colisiones.py` como API pública, e importarlos desde las dos vistas. En la vista de equipo, devolver `ajax_errors(form.errors)` directamente en lugar de lanzar y capturar un `ValidationError`.
- **Lo que NO hay que hacer:** no cambiar los textos de `MENSAJES_COLISION`.
- **Tests a agregar:** los tests actuales de colisión de quick_create, apuntados al módulo nuevo.
- **Verificación:** `grep -rn "from users.views" programas/` da 0.
- **Regla para no repetirlo:** control mecánico · `test_arquitectura.py` · «Extender el ratchet: ninguna vista importa de `<otra_app>.views`, y nadie importa un nombre que empiece con `_` de otro módulo.»

---

### D-LIM-36 · Helpers de presentación copiados: `plural` ×3, `EXTENSIONES_IMAGEN` ×4, `_personas_prefetch`, `_autor`, formato de fecha
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** fusión de D3-LIM-11 + D1-LIM-16 + D4-LIM-06 · **Ola:** 11 · **Esfuerzo:** S
- **ID de la pasada 1:** D3-LIM-11 + D1-LIM-16 + D4-LIM-06 (**hallado por 3 revisores**)
- **Hallado por 3 revisores (sube de peso):** D3-LIM-11 (`plural` ×3, `EXTENSIONES_IMAGEN` ×4, `_personas_prefetch`, `_autor`), D1-LIM-16 (formateadores de nombre, fecha y plural entre `detalle_dispositivo` y `auditoria_dispositivo`, con uno muerto) y D4-LIM-06 (seis copias de «nombre visible de un usuario», con tres textos de respaldo distintos). Una sola pasada por los formateadores.
- **Cruce con Emergencia:** formateadores de texto copiados en cinco o más módulos (E-LIM-25). El destino de los helpers difiere entre las tres soluciones (`programas/services/formato.py`, `core/texto.py`, `core/usuarios.py`): contradicción 3 de la sección 1; propuesta del juez en esa lista.
- **Ubicación:**
  - `plural`: `services/bitacora_detalle.py:36`, `services/emergencia_tablero.py:399`, `services/detalle_dispositivo.py:423`, más `'s' if n != 1` a mano en `services/alertas_dispositivos.py:168` y `:239`.
  - `EXTENSIONES_IMAGEN`: `notificaciones/services/paquete.py:72`, `selectors/revision.py:47`, `services/bitacora_detalle.py:25`, `services/respuestas.py:310` (lo usa `respuestas_dispositivo.py:275`).
  - `_personas_prefetch`: `bitacora_pantalla.py:175-181` es idéntico a `bitacora_detalle.py:65-71`.
  - `_autor`: `bitacora_pantalla.py:121` duplica `bitacora_detalle.py:28`.
  - Formato de fecha: `bitacora_pantalla.py:146` arma a mano lo que hace `_fecha_hora` de `bitacora_detalle`.
- **Escenario:** se agrega `.webp` o `.heic` a una lista y una pantalla muestra la miniatura mientras otra muestra un link de descarga del mismo archivo.
- **Causa raíz:** no hay un módulo de utilidades de presentación compartido en `programas`.
- **Solución (destino según la resolución 3 de la sección 1):** `core/archivos.py` con `EXTENSIONES_IMAGEN`/`es_imagen()` (ya la usa `notificaciones/`), y `plural()` y los formateadores en `core/texto.py` solo si algún consumidor está fuera de `programas/`; si no, en `programas/services/formato.py`. El resto importa de ahí. `bitacora_pantalla` importa `_personas_prefetch`, `_autor` y `_fecha_hora` de `bitacora_detalle` (renombrados sin guion bajo). Las 4 listas de extensiones se igualan solo si ya son iguales; si difieren, DECISIÓN CLIENTE (default = la unión no cambia nada visible solo si coinciden; si no, conservar cada una con nombre propio).
- **Lo que NO hay que hacer:** no cambiar ningún texto visible.
- **Tests a agregar:** `plural(1, "turno") == "1 turno"`, `plural(2, ...)`; `es_imagen` con mayúsculas.
- **Verificación:** `grep -rn "def plural\|EXTENSIONES_IMAGEN =" programas notificaciones` da 1 de cada uno.
- **Regla para no repetirlo:** skill · `rubricas/codigo-limpio.md` · «Antes de escribir un helper de texto o archivo, buscar en `core/`.»

#### Aporte del segundo revisor (D1-LIM-16: Formateadores duplicados entre `detalle_dispositivo` y `auditoria_dispositivo` (y uno muerto))
_Pasada 1: severidad BAJA · estado CONFIRMADO (lectura) · esfuerzo S._

- **Ubicación:** nombre de usuario: `selectors/auditoria_dispositivo.py:120-123` (`_quien`, «Sistema»),
  `services/detalle_dispositivo.py:330-333` (`_nombre`, «sin responsable») y `services/dispositivos.py:131-132`
  (`nombre_de_persona`). Fechas: `auditoria_dispositivo.py:126-127` (`_cuando`, **sin uso**),
  `detalle_dispositivo.py:245-250` (`_fecha_legible`) y `:336-337` (`_fecha`). Plurales:
  `detalle_dispositivo.py:340-343` (`_cantidad_de_fotos`, que reimplementa `_plural`) y `:423-424` (`_plural`).
- **Escenario:** tres maneras de nombrar a un usuario: `get_username()` en dos y `.username` en
  `detalle_dispositivo.py:333`, que ignora un `USERNAME_FIELD` propio. Y dos maneras de formatear la misma fecha
  en el mismo archivo.
- **Causa raíz:** cada módulo trae sus helpers privados.
- **Solución:** `programas/services/formato.py` con `nombre_de_usuario(u, vacio="Sistema")`, `fecha_legible(x)` y
  `plural(n, singular, plural)`. Los literales de vacío se pasan como argumento para conservar los textos. Borrar
  `_cuando`.
- **Tests a agregar:** `programas/tests/test_formato.py`.
- **Verificación:** `ruff` con F811/F841 no cubre funciones muertas. Usar `vulture programas/selectors/auditoria_dispositivo.py`
  o grep.
- **Regla para no repetirlo:** **skill** · `codigo-limpio.md`, tabla de helpers canónicos: «Nombre de usuario y fecha
  legible → `programas/services/formato.py`».

#### Aporte del segundo revisor (D4-LIM-06: Seis copias de «nombre visible de un usuario», con tres textos de respaldo distintos)
_Pasada 1: severidad BAJA · estado CONFIRMADO (lectura) · esfuerzo S._

- **Ubicación:** `programas/services/inspecciones.py:333-334` (`—`), `programas/services/detalle_dispositivo.py:330`,
  `programas/selectors/edificios.py:191-192` (`sin responsable`), `programas/views/dispositivos_relevamientos.py:146-147`
  (sin respaldo: `None` da `AttributeError`), y en templates `relevamientos/list.html:89` y `:230`
  (`get_full_name|default:username`)
- **Escenario:** el mismo agente aparece con `get_username()` en el informe y con `.username` en P21; si
  `USERNAME_FIELD` cambia, divergen. La versión de la vista no admite `None` y la usan `:356` y `:407`, protegidos
  hoy solo porque `asignado_a` no es nulo en la práctica.
- **Causa raíz:** no hay helper canónico; cada archivo escribió el suyo.
- **Solución:** `core/usuarios.py::nombre_visible(usuario, vacio="—")` (o en `users/`), y cada llamador pasa su
  respaldo actual (`vacio="sin responsable"` en el selector). En templates, exponer el nombre desde el dataclass de
  D-LIM-09 en vez del filtro `default`. Textos visibles iguales.
- **Tests a agregar:** `core/tests/test_usuarios.py::NombreVisibleTests` (con nombre, sin nombre, `None`).
- **Verificación:** `grep -rn "get_full_name() or" programas/` sin resultados en el alcance.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md`, tabla de helpers
  canónicos · fila: «Nombre visible de un usuario · `nombre_visible(usuario, vacio=…)`».

---

### D-LIM-37 · Envoltorios identidad, constantes de capacidad y `_trazar` copiados entre módulos
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** fusión de D2-LIM-13 + D4-LIM-13 · **Ola:** 11 · **Esfuerzo:** S
- **ID de la pasada 1:** D2-LIM-13 + D4-LIM-13 (**hallado por 2 revisores**)
- **Hallado por 2 revisores (sube de peso):** D2-LIM-13 (envoltorios identidad, constantes de capacidad y `_trazar` copiados entre módulos) y D4-LIM-13 (envoltorios identidad y una vista que importa el mixin desde otra vista). **Cruce con Emergencia:** la capacidad `"dispositivo.admitir"` redeclarada en siete módulos es E-LIM-27 (ex E-LIM-27): las `CAP_*` van a un solo módulo para Emergencia y Dispositivos. La importación del mixin desde `reportes.py` es la misma línea que cita la ficha de gates de sesión (D-LIM-32) (se corrige una vez).
- **Ubicación:** `programas/services/ingreso.py:50-58` (`maneja_plazas(d)` = `d.tipo.maneja_plazas`), `340-349` (`alta_minima_de_persona` = `_alta_manual`); `programas/forms_ingreso.py:19-23` (`GENERO_CHOICES` copia de `Ciudadano.Genero`, `legajos/models/base.py:21-24`, y la vista lo usa para rotular el género de una alta manual cargada con `Ciudadano.Genero`, `dispositivos_ingreso.py:256,270`); `CAP_EDITAR` en `estadias.py:124`, `plazas.py:48`, `edificios.py:38`, `bitacora.py:66`, `alertas_dispositivos.py:71`; `_trazar` sobre `TrazaDispositivo` en `estadias.py:258-273`, `plazas.py:96-108`, `edificios.py:64`; `_id_de` en `ocupacion.py:244-249` y `censo.py:236-241`
- **Escenario:** son copias hoy idénticas; un cambio en el catálogo de géneros o en la forma de la traza (p. ej. sumar `programa_id`) diverge en silencio. `ocupacion.Censo` (dataclass de conteos) comparte nombre con el módulo `censo` (que define `CensoDia`), lo que confunde al leer imports.
- **Causa raíz:** cada módulo nuevo copió lo que necesitaba del vecino.
- **Solución:** `programas/services/capacidades_dispositivos.py` con las `CAP_*` (o importarlas de `core.rbac` si el catálogo ya las expone); un único `trazar_dispositivo(...)` en `programas/services/trazas.py`; `GENERO_CHOICES = [("", "Seleccionar..."), *Ciudadano.Genero.choices]`; borrar `maneja_plazas` (llamar a la property) y renombrar `_alta_manual` a `alta_minima_de_persona`; `_id_de` a `programas/services/_ids.py`; renombrar `ocupacion.Censo` → `OcupacionRed` con alias.
- **Lo que NO hay que hacer:** borrar `alta_minima_de_persona` (es el nombre que usa Emergencia).
- **Tests a agregar:** `programas/tests/test_forms_ingreso.py::GeneroTests.test_choices_son_los_del_modelo`.
- **Verificación:** `grep -rn '^CAP_EDITAR = ' programas` → una línea.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/codigo-limpio.md` · fila nueva en «Helpers canónicos»: «Trazar en el legajo del dispositivo → `trazar_dispositivo`; capacidades del programa → `capacidades_dispositivos`».

#### Aporte del segundo revisor (D4-LIM-13: Envoltorios identidad y una vista que importa el mixin desde otra vista)
_Pasada 1: severidad BAJA · estado CONFIRMADO (lectura) · esfuerzo S._

- **Ubicación:** `programas/views/reportes.py:15-16` (`_respuesta` = `respuesta_reporte`), `:12` (importa
  `DispositivoProgramaPermissionMixin` de `views/dispositivos_legajo` mientras `views/dispositivos_edificios.py:11`
  lo importa de `programas/mixins_dispositivos`); `programas/selectors/edificios.py:73-76` (`ve_situaciones` =
  `puede_configurar_dispositivos`)
- **Escenario:** indirección sin semántica; la arista vista→vista suma al ratchet de RED-79 sin necesidad.
- **Solución:** llamar a `respuesta_reporte` directo; importar el mixin de `programas.mixins_dispositivos`.
  `ve_situaciones` puede quedar si se documenta como punto de decisión (hoy su docstring lo justifica a medias):
  default, dejarlo.
- **Tests a agregar:** ninguno.
- **Verificación:** el ratchet de aristas de RED-79 baja en una.
- **Regla para no repetirlo:** **control mecánico** · ratchet de RED-79 (ya existe) · sin cambios: esta ficha baja la cuenta.

---

### D-LIM-38 · Formato del nombre de plaza y regla «asignación = cambio sin origen» repetidos pese a declararse únicos
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** fusión de D2-LIM-12 + D3-LIM-16 · **Ola:** 11 · **Esfuerzo:** S
- **ID de la pasada 1:** D2-LIM-12 + D3-LIM-16 (**hallado por 2 revisores**)
- **Hallado por 2 revisores (sube de peso):** D2-LIM-12 (formato del nombre de plaza y regla «asignación = cambio sin origen» repetidos pese a declararse únicos) y D3-LIM-16 (`alertas_dispositivos` arma «Plaza X · Sector» a mano e ignora `plaza_con_sector`). Mismo helper (`services/nombre_plaza.py`) y mismo arreglo.
- **DECISIÓN CLIENTE (de D3-LIM-16):** default = las alertas usan `plaza_con_sector` y aceptan el formato canónico; si el PM quiere conservar el texto actual, el helper recibe un parámetro, no queda la copia.
- **Ubicación:** `programas/services/nombre_plaza.py:1-5` («Es el único lugar donde se arma») vs `programas/selectors/estadia_detalle.py:111-114` (`_plaza`: «Sector · código»), `351-353`, `371-374`; `programas/selectors/trayectoria.py:40-44` (`_ubicacion`, otra vez «Sector · código»); `programas/templates/programas/dispositivos/ingreso/paso_confirmar.html:44` (formato inline); regla de asignación en `estadia_detalle.py:154-157`, `169-170`, `209-210` (`tipo == CAMBIO_PLAZA and plaza_origen_id is None` ×3); docstring «cuatro consultas fijas» (`estadia_detalle.py:4-7`) vs «Tres consultas fijas» (`324`)
- **Escenario:** hay dos formatos vivos («01 (Pabellón A)» y «Pabellón A · 01») implementados en cuatro lugares; el módulo que se dice único no lo es. La noción «asignación de plaza» se infiere del par tipo/origen en tres funciones de presentación distintas, y `_detalle_del_movimiento` y `_fila_de_movimiento` son dos `switch` paralelos sobre el mismo tipo.
- **Causa raíz:** cada pantalla resolvió su rótulo; el concepto «asignación» no tiene nombre en el modelo.
- **Solución:** `nombre_plaza.ubicacion(plaza, sector_nombre=None) -> "Sector · código"` como segundo formato oficial (y corregir el docstring para decir que hay dos), usado por `estadia_detalle`, `trayectoria` y pasado ya armado a `paso_confirmar`; `MovimientoEstadia.es_asignacion` (property) en el modelo; una tabla `{tipo: (formato_detalle, formato_fila)}` en `estadia_detalle` en vez de dos cadenas `if/elif`. Corregir el docstring 3 vs 4.
- **Lo que NO hay que hacer:** unificar los dos formatos en uno: cambia textos visibles.
- **Tests a agregar:** `programas/tests/test_nombre_plaza.py::UbicacionTests.test_formato_sector_codigo`.
- **Verificación:** snapshots de P7 y trayectoria idénticos.
- **Regla para no repetirlo:** **control mecánico** · test ratchet `programas/tests/test_nombre_plaza.py::SinFormatoInlineTests` · «`f"{…sector.nombre} · {…codigo}"` fuera de `nombre_plaza.py` → falla».

#### Aporte del segundo revisor (D3-LIM-16: `alertas_dispositivos` arma «Plaza X · Sector» a mano e ignora `plaza_con_sector`)
_Pasada 1: severidad BAJA · estado CONFIRMADO (lectura) · esfuerzo S._

- **Ubicación:** `services/alertas_dispositivos.py:136` (`f"Plaza {reserva.plaza.codigo} · {reserva.plaza.sector.nombre}"`) y `:161` (`f"{codigo} · {sector} ({motivo})"`). Canónico: `services/nombre_plaza.py` (`plaza_con_sector`, cuyo docstring dice «el único lugar donde se arma; no se copia en cada servicio»).
- **Escenario:** cambia el formato canónico del nombre de plaza y las alertas siguen mostrando el viejo.
- **Causa raíz:** el helper canónico no se conocía cuando se escribieron las alertas.
- **Solución:** DECISIÓN CLIENTE: default = usar `plaza_con_sector` y aceptar el formato canónico en las alertas. Si el PM quiere conservar exactamente el texto actual, agregar un parámetro al helper en lugar de dejar la copia.
- **Lo que NO hay que hacer:** no tocar TONOS/ICONOS (E-LIM-29).
- **Tests a agregar:** el origen de la alerta coincide con `plaza_con_sector(plaza)`.
- **Verificación:** `grep -n "Plaza {" programas/services` da 0.
- **Regla para no repetirlo:** control mecánico · `design_audit`/test · «Un f-string con `plaza.codigo` y `sector.nombre` fuera de `nombre_plaza.py` es un hallazgo.»

---

### D-LIM-39 · `views/dispositivos_ingreso.py` (801 líneas): sesión, presentación y un preámbulo repetido en cada handler
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 11 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D2-LIM-08
- **Ubicación:** `programas/views/dispositivos_ingreso.py:117-184` (estado de sesión y huellas), `227-279` (`resumen_persona` con tres formas de persona), `539-545`, `571-577`, `686-692`, `705-711`, `744-745` (preámbulo `estado → _previo → resumen_persona → volver_al_inicio` y el mismo literal «La persona elegida ya no está en el Legajo Ciudadano…» ×5)
- **Escenario:** pasa las 700 líneas; un cambio de wording del aviso o de la regla de «persona vigente» hay que repetirlo en cinco handlers. La sesión del asistente (forma por dispositivo, migración de la forma vieja, huellas SHA-256) es un modelo de datos sin tipo que vive como métodos de la vista base.
- **Causa raíz:** template method ausente: cada `get`/`post` reimplementa la preparación.
- **Solución:** (a) `IngresoBaseView.preparar(request) -> tuple[estado, persona] | HttpResponse` que concentra el preámbulo y el literal en una constante `PERSONA_YA_NO_ESTA`; (b) `programas/views/ingreso_sesion.py::SesionAsistente` (dataclass + `cargar/guardar/limpiar/huella_persona/misma_persona`); (c) `resumen_persona` → `programas/selectors/ingreso_persona.py` (es una lectura: hace consulta a `Ciudadano` y arma presentación). Objetivo: la vista < 550 líneas.
- **Lo que NO hay que hacer:** guardar objetos de modelo en la sesión al tiparla (la forma JSON actual es la que soporta pestañas paralelas).
- **Tests a agregar:** `programas/tests/test_ingreso_sesion.py::SesionAsistenteTests.test_descarta_forma_vieja` y `test_huella_distingue_registro_de_manual`.
- **Verificación:** tests del asistente (pestañas paralelas, rebote a plaza) verdes sin tocarlos.
- **Regla para no repetirlo:** **control mecánico** · el mismo `scripts/check_tamano_modulos.py` de D-LIM-20 con umbral de aviso a 700 · «aviso (no falla) para vistas > 700 líneas».

---

### D-LIM-40 · `bitacora.py` repite validaciones: parseo de ids, turno en curso, dispositivo activo, nombre de turno
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 11 · **Esfuerzo:** S
- **ID de la pasada 1:** D3-LIM-12
- **Ubicación:** `services/bitacora.py:332-344` (`_ids_de_personas`) y `:674-685` (`_ids_a_quitar`), con el mismo `int(str().strip())`; `_exigir_turno_en_curso` (`:308-329`) repetido inline en `corregir_entrada` (`:746-754`); «Solo se carga la bitácora de un dispositivo activo» en `:408` y `:741`; chequeo de nombre vacío o duplicado en `crear_turno` (`:230-237`) y `editar_turno` (`:269-274`). `corregir_entrada` (`:698-834`) suma 136 líneas con tres modos de personas.
- **Escenario:** se corrige un mensaje o una regla de turno en curso y la otra copia sigue con la versión vieja: la corrección de una entrada acepta lo que la carga rechaza.
- **Causa raíz:** `corregir_entrada` se escribió copiando el camino de carga en lugar de llamarlo.
- **Solución:** `_parsear_ids(valores)` único; `corregir_entrada` llama a `_exigir_turno_en_curso` y a un `_exigir_dispositivo_activo`; `_validar_nombre_turno(dispositivo, nombre, excluir_pk=None)` para crear y editar. Los tres modos de personas pasan a `_personas_corregidas(entrada, datos)`.
- **Lo que NO hay que hacer:** no tocar el candado de `:426` (D-PERF-07) ni el caso de dispositivo cerrado por POST (ya registrado).
- **Tests a agregar:** `corregir_entrada` fuera de turno y con dispositivo inactivo devuelve el mismo error que la carga.
- **Verificación:** tests de bitácora en verde; `corregir_entrada` por debajo de 60 líneas.
- **Regla para no repetirlo:** skill · `rubricas/codigo-limpio.md` · «Un mensaje de error de dominio aparece una sola vez en el código.»

---

### D-LIM-41 · Los cuatro mutadores del equipo repiten el mismo esqueleto
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 11 · **Esfuerzo:** S
- **ID de la pasada 1:** D3-LIM-13
- **Ubicación:** `services/equipo_dispositivo.py:229-292` (`cambiar_rol`, `dar_de_baja`, `marcar_responsable`, `desmarcar_responsable`). Además hay 7 `from programas.models import …` dentro de funciones sin un ciclo que lo justifique (los modelos no importan servicios), y las lecturas `pares_persona_rol`/`equipo_del_dispositivo` viven en services en lugar de selectors. El bucle de username está en `:173-179`.
- **Escenario:** se agrega un quinto mutador y se olvida el `select_for_update` del miembro o el `_exigir_gestion`.
- **Causa raíz:** no se extrajo el patrón atomic → `_bloquear` → `_exigir_gestion` → `select_for_update(miembro)`.
- **Solución:** un context manager `_miembro_bloqueado(dispositivo, miembro_id, usuario)` que haga los cuatro pasos y entregue el miembro; cada mutador queda en 3-5 líneas. Subir los imports de modelos al encabezado (verificando con el detector de ciclos) y mover las dos lecturas a `selectors/equipo.py`.
- **Lo que NO hay que hacer:** no cambiar el orden de los locks.
- **Tests a agregar:** ninguno nuevo; los tests del equipo cubren los cuatro.
- **Verificación:** tests en verde; `CICLOS_CONOCIDOS` sin cambios.
- **Regla para no repetirlo:** skill · `rubricas/codigo-limpio.md` · «Un import de modelos dentro de una función lleva un comentario que nombra el ciclo que evita.»

---

### D-LIM-42 · `forms_bitacora` importa del servicio de pantalla y `bitacora.py` importa de un módulo de presentación
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 11 · **Esfuerzo:** S
- **ID de la pasada 1:** D3-LIM-10
- **Ubicación:** `forms_bitacora.py:13` (`TIPOS_MANUALES` desde `services/bitacora_pantalla.py`); `services/bitacora.py:58` (`plural` desde `services/bitacora_detalle.py`). También selectores que importan servicios: `selectors/agentes_sugeridos.py` → `services/buscador_agentes`, `selectors/equipo_sugeridas.py` → `services/dispositivos`/`inspecciones`.
- **Escenario:** el dominio y los forms dependen de la capa de pantalla. Un cambio de presentación arrastra el servicio de escritura y abre la puerta a un ciclo de imports como los que ya sostiene `test_arquitectura.py`.
- **Causa raíz:** las constantes de dominio se definieron donde se usaron primero.
- **Solución:** mover `TIPOS_MANUALES` a `services/bitacora.py` o junto al modelo, y `plural` a un helper de texto común (ver D-LIM-36). Los selectores que necesitan reglas de servicio reciben el dato ya calculado, o la regla baja a un selector.
- **Lo que NO hay que hacer:** no subir imports diferidos al encabezado sin correr el detector de ciclos.
- **Tests a agregar:** ninguno nuevo; el detector de ciclos sigue en verde.
- **Verificación:** `grep -n "bitacora_pantalla" programas/forms_bitacora.py` da 0.
- **Regla para no repetirlo:** control mecánico · `test_arquitectura.py` · «`forms*` y `services/*` no importan de módulos `*_pantalla`/`*_detalle`; `selectors/` no importa de `services/` (techo = lo medido hoy).»

---

### D-LIM-43 · El registro por momento de las respuestas del dispositivo está en tres lugares
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 11 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D3-LIM-14
- **Ubicación:** `services/respuestas_dispositivo.py:54-60` (`MODELOS_DE_RESPUESTAS`), `:171-224` (`guardar_respuestas_alta/ingreso/egreso`), `:367-370` (la tupla de `formularios_de_estadia`).
- **Escenario:** se agrega un momento nuevo (por ejemplo «traslado», que figura en la v2) y hay que tocar tres lugares; olvidar uno deja respuestas guardadas que la estadía no muestra.
- **Causa raíz:** el mapeo momento → (modelo, adjunto, dueño) no está en una sola estructura.
- **Solución:** un dict `MOMENTOS = {"alta": Momento(modelo, adjunto, dueño), ...}` y un único `guardar_respuestas(momento, ...)`; los tres wrappers quedan como alias de una línea para no tocar a los callers.
- **Lo que NO hay que hacer:** no renombrar los wrappers públicos en esta ola.
- **Tests a agregar:** guardar y leer para cada momento.
- **Verificación:** tests de respuestas en verde.
- **Regla para no repetirlo:** skill · `rubricas/codigo-limpio.md` · «Un enum de dominio con datos asociados se declara una vez, en un registro.»

---

### D-LIM-44 · `buscador_agentes.py` arma la fila dos veces
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 11 · **Esfuerzo:** S
- **ID de la pasada 1:** D3-LIM-15
- **Ubicación:** `services/buscador_agentes.py:126-140` (el bucle) y `:144-158` (`_fila_sumable`), con la extracción de perfil y DNI repetida.
- **Escenario:** se agrega un dato a la fila (por ejemplo el correo) y aparece en una rama sí y en la otra no.
- **Causa raíz:** el bucle se escribió antes que `_fila_sumable` y no se reemplazó.
- **Solución:** el bucle llama a `_fila_sumable` (o a una `_fila_base`) y agrega solo lo propio.
- **Lo que NO hay que hacer:** no cambiar las claves del JSON del buscador.
- **Tests a agregar:** snapshot del JSON del buscador para un usuario sumable y uno inactivo.
- **Verificación:** snapshot idéntico.
- **Regla para no repetirlo:** — (lo cubre la rúbrica general).

---

### D-LIM-45 · Constantes de búsqueda redeclaradas y orden de turnos repetido
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 11 · **Esfuerzo:** S
- **ID de la pasada 1:** D3-LIM-17
- **Ubicación:** `selectors/personas_sugeridas.py:19-20` (`MINIMO_CARACTERES = 3`, `MAXIMO_RESULTADOS = 10`) en lugar de `users.services.busqueda.MIN_CARACTERES`/`TOPE_RESULTADOS`. Orden `("orden", "hora_desde", "id")` en `services/bitacora.py:121`, `services/bitacora_pantalla.py:398-400` y `:525`, mientras `Turno.Meta.ordering` (`models/__init__.py:1700`) es `["dispositivo_id", "orden", "hora_desde"]`.
- **Escenario:** se sube el mínimo de búsqueda a 4 en Usuarios y el buscador de personas sigue en 3; el orden de turnos difiere entre la bitácora y otras pantallas que usan el `Meta`.
- **Causa raíz:** valores copiados en lugar de importados.
- **Solución:** importar las constantes de `users.services.busqueda`; una constante `ORDEN_TURNOS` en el modelo (o `Turno.objects.ordenados()`) usada en los tres lugares.
- **Lo que NO hay que hacer:** no cambiar `Meta.ordering` (cambiaría consultas en otras pantallas).
- **Tests a agregar:** ninguno.
- **Verificación:** `grep -rn "MINIMO_CARACTERES = \|\"orden\", \"hora_desde\", \"id\"" programas` da 0.
- **Regla para no repetirlo:** — (rúbrica general).

---

### D-LIM-46 · `forms_dispositivos.py` es un cajón de sastre de 861 líneas
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 11 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D3-LIM-18
- **Ubicación:** `forms_dispositivos.py` (861 líneas: egreso, plazas, relevamientos, sectores, edificios, equipo). `clean_persona_rol` (`:787-814`) tiene imports locales y vuelve a chequear reglas del servicio (ver D-LIM-08).
- **Escenario:** queda a 140 líneas del límite de 1.000; la próxima feature de Dispositivos lo pasa. `forms_bitacora.py` ya se separó por este mismo motivo.
- **Causa raíz:** un solo módulo de forms por producto.
- **Solución:** convertirlo en paquete `forms_dispositivos/` con un archivo por subdominio (`egreso.py`, `plazas.py`, `edificios.py`, `equipo.py`, `relevamientos.py`) y un `__init__.py` que reexporte los nombres actuales, para no tocar ningún import.
- **Lo que NO hay que hacer:** no cambiar nombres de clases ni campos.
- **Tests a agregar:** ninguno; la suite cubre los imports.
- **Verificación:** `manage.py check` y la suite de Dispositivos en verde; ningún archivo nuevo pasa de 300 líneas.
- **Regla para no repetirlo:** control mecánico · test · «Ningún `.py` de `programas/` pasa de 1.000 líneas (techo con baseline).»

---

### D-LIM-47 · Guardar una foto y guardar un adjunto repiten el mismo bloque y normalizan el UUID distinto
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 11 · **Esfuerzo:** S
- **ID de la pasada 1:** D4-LIM-07
- **Ubicación:** `programas/services/inspecciones.py:537-559` (`_guardar_foto`) y `:733-744`
  (`agregar_adjunto_formulario`); UUID: `:654`, `:697`, `:727`, `:734`
- **Escenario:** los dos hacen `full_clean(validate_unique=False)` → `atomic()` → `save()` → `IntegrityError` →
  `anotar_archivo_escrito` → `_conflicto_uuid_en_uso()` → `ya_existia = False`. `_como_uuid` corre dos veces en cada
  camino (`_admitir_carga` ya lo hace en `:654`) y, aun así, el adjunto guarda el `uuid_cliente` **crudo** (`:734`)
  mientras la foto guarda el normalizado (`:697-698`). Hoy da igual porque `full_clean` lo convierte; un cambio en el
  orden (guardar antes de validar) haría que solo uno de los dos se rompa.
- **Causa raíz:** el adjunto se copió de la foto (task A4) sin extraer la parte común.
- **Solución:** `_guardar_carga(instancia, archivo)` con el bloque compartido; `_admitir_carga` devuelve
  `(inspeccion, previa, uuid_normalizado)` y los dos llamadores usan ese valor. Sin cambio de comportamiento.
- **Tests a agregar:** los de idempotencia existentes alcanzan; sumar
  `test_inspecciones_api.py::AdjuntoTests.test_uuid_en_texto_queda_normalizado`.
- **Verificación:** suite de la API de campo igual.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-auditor.md` · «Dos funciones con el mismo
  try/except alrededor de `save()` y la misma limpieza de archivos son un helper que falta».

---

### D-LIM-48 · Alta y edición de edificio duplican la normalización y validación de código y nombre
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 11 · **Esfuerzo:** S
- **ID de la pasada 1:** D4-LIM-09
- **Ubicación:** `programas/services/edificios.py:101-107` y `:135-141`; acciones de traza como literales sueltos en
  `:114`, `:149`, `:170`, `:216`
- **Escenario:** una regla nueva para el código (largo mínimo, prefijo) hay que escribirla dos veces; si se escribe una,
  el alta la cumple y la edición no. Las acciones `"EDIFICIO_CREADO"`… son strings libres en un `CharField` sin
  choices (`TrazaDispositivo.accion`, `models/__init__.py:813`): un typo crea una acción nueva que el historial no
  reconoce.
- **Causa raíz:** copia entre funciones hermanas.
- **Solución:** `_datos_validados(codigo, datos, *, excepto=None) -> (codigo, campos)` que normaliza, exige y llama a
  `_exigir_codigo_libre`; constantes `ACCION_EDIFICIO_CREADO = "EDIFICIO_CREADO"` etc. en el módulo (sin migración:
  mismos valores).
- **Tests a agregar:** `programas/tests/test_edificios.py::EdicionTests.test_codigo_vacio_rechazado_al_editar` si no existe.
- **Verificación:** suite de edificios igual.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-auditor.md` · «`crear_x`/`editar_x` validan por un
  único helper; las acciones de traza son constantes, no literales».

---

### D-LIM-49 · `edificios_para_asignar` y `edificios_sin_relevar` (y la situación «vigentes») repiten la base del filtro
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 11 · **Esfuerzo:** S
- **ID de la pasada 1:** D4-LIM-10
- **Ubicación:** `programas/services/inspecciones.py:852-857` y `:884-889`; tercera forma de «vigente» en
  `programas/selectors/edificios.py:69-70` y `:95`; alias duplicados del through `_EdificioDispositivo`
  (`services/inspecciones.py:108`) y `_VINCULOS` (`selectors/edificios.py:66`)
- **Escenario:** «activo y con al menos una institución» se escribe con `pk__in=through.values(...)` en dos lugares y con
  `Exists(through...)` en otro. Si cambia la definición de edificio vigente (p. ej. excluir los que solo tienen
  instituciones cerradas), la sección Edificios y P21 dejan de coincidir.
- **Causa raíz:** las dos pantallas definieron «vigente» por su cuenta.
- **Solución:** `edificios_vigentes_en_alcance(user, capacidad)` en el selector (D-LIM-29), usado por las tres;
  un único alias del through. Mismo SQL en cada caso (se elige una forma y se miden los presupuestos).
- **Tests a agregar:** ninguno nuevo.
- **Verificación:** presupuestos de `dispositivos:relevamientos` y `dispositivos:edificios` sin cambios.
- **Regla para no repetirlo:** **skill** · `rubricas/codigo-limpio.md`, helpers canónicos · fila «Edificio vigente ·
  `edificios_vigentes_en_alcance`».

---

### D-LIM-50 · La API de campo duplica las acciones `fotos` y `adjuntos` y arma su propio 400 legible
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 11 · **Esfuerzo:** S
- **ID de la pasada 1:** D4-LIM-11
- **Ubicación:** `programas/api/views_inspecciones.py:246-265` y `:283-302`; `:99-111` (`_respuesta_400`) frente a
  `programas/api/serializers.py:38-51` (`rechazo_legible`)
- **Escenario:** las dos acciones son idénticas salvo serializer y operación (`get_object` → validar → `_ejecutar` →
  200/201 por `ya_existia`). El 400 de inspecciones agrega `detail` y `non_field_errors`; el de Becas
  (`rechazo_legible`) solo `non_field_errors`. La app (`becasApi.js`) lee los dos, pero hay dos contratos de error
  para la misma app que evolucionan por separado.
- **Causa raíz:** la API de inspecciones copió el molde de Becas sin extraer el helper.
- **Solución:** `_recibir_carga(request, entrada_cls, salida_cls, operacion)` para las dos acciones. Para el 400:
  mover `_respuesta_400` a `programas/api/errores.py` y documentarlo junto a `rechazo_legible`; **unificar el cuerpo
  es DECISIÓN CLIENTE** (contrato con `Chaco-mobile`): default, no tocar el cuerpo, solo juntar el código.
- **Lo que NO hay que hacer:** cambiar `detail`/`non_field_errors` sin el test de contrato y release coordinado de la app.
- **Tests a agregar:** ninguno; los de contrato de la API de campo cubren las dos acciones.
- **Verificación:** test de contrato igual.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-auditor.md` · «Dos `@action` de DRF con el mismo
  cuerpo salvo serializer y operación van por un helper».

---

### D-LIM-51 · Presentación (íconos, tonos, notas, URLs) armada en servicios y en un selector
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** LIM · **Origen:** nuevo · **Ola:** 11 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D4-LIM-12
- **Ubicación:** `programas/services/inspecciones.py:1149-1200` (`_TONOS_CON_COLOR`, `_indicadores_del_informe` con
  `fa-building`, `fa-calendar-check`…), `:1123-1146`; `programas/selectors/edificios.py:167-251` y `:254-329`
  (`reverse(...)`, `_url_asignar` con f-string de querystring en `:195-196`, rótulo de `Sector.Tipo` en `:297`)
- **Escenario:** `selectors/` es «consultas de lectura, sin lógica» y acá devuelve filas con URLs y textos para el
  template; el servicio transaccional conoce clases de Font Awesome. Un cambio de ícono o de ruta obliga a tocar la
  capa de dominio.
- **Causa raíz:** no hay módulo de presentación por pantalla (mismo origen que D-LIM-09).
- **Solución:** `services/informe_relevamiento.py` (D-LIM-30 paso 3) para el informe; `services/ficha_edificio.py`
  para `filas_del_listado`/`ficha_de_edificio`/`_base_de_fila`/`_instituciones_por_edificio`, dejando en
  `selectors/edificios.py` solo `edificios_visibles`, `filtrar_edificios`, `para_el_listado` y `localidades_visibles`.
  Salida idéntica.
- **Tests a agregar:** ninguno.
- **Verificación:** suite de la sección Edificios y del informe igual.
- **Regla para no repetirlo:** **control mecánico** · `core/tests/test_capas_imports.py` (el de D-LIM-29) · un módulo
  de `selectors/` no importa `django.urls.reverse`; allowlist decreciente.

---

### D-FE-05 · Cadena if/elif tono → clase de badge copiada en 4 templates
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** fusión de D3-FE-03 + D4-FE-01 · **Ola:** 12 · **Esfuerzo:** S
- **ID de la pasada 1:** D3-FE-03 + D4-FE-01 (**hallado por 2 revisores**)
- **Hallado por 2 revisores (sube de peso):** D3-FE-03 (la cadena `if/elif` tono → clase de badge copiada en 4 templates) y D4-FE-01 (el color de cada situación y de cada criticidad está en cuatro lugares, dos en templates). Misma mecánica: el tono se resuelve en Python y llega como variable.
- **Cruce con Emergencia:** la tabla severidad → tono/ícono y la serialización del `Aviso` están copiadas entre Emergencia y Dispositivos (E-LIM-29). El filtro `badge_tono` de esta ficha tiene que ser el mismo que adopte Emergencia: una sola tabla para los dos módulos.
- **Del pedido del juez (D-LIM-38 «si cabe»):** D-LIM-38 («Plaza X · Sector» armado a mano) no cabe en esta ficha (es el nombre de plaza, no el tono): quedó fusionado en D-LIM-38.
- **Ubicación:** `templates/programas/dispositivos/bitacora/entrada.html:11`, `templates/components/_entradas_bitacora.html:36` (además con una cadena de íconos), `templates/components/_turno_tarjeta.html:29`, `templates/components/_lista_tarjetas.html:33`. Prueba de que no hace falta: `tipo_list.html:161` usa `badge-{{ estado.tono }}`.
- **Escenario:** se agrega el tono `neutral` o `purple` y cae en `badge-gray` en tres templates y no en el cuarto.
- **Causa raíz:** la cadena existe para garantizar que Tailwind vea las clases completas en el build; la lista blanca se resolvió en cada template.
- **Solución:** un filtro `nodo_ui.badge_tono` (y `icono_tono`) que mapee tono → clase con default `badge-gray`. Las clases ya existen como literales en el filtro .py, que Tailwind tiene que escanear: verificar que `tailwind.config` incluya `**/templatetags/*.py`; si no, agregarlo y correr `npm run build:tailwind`. El HTML resultante es idéntico.
- **Lo que NO hay que hacer:** no usar `badge-{{ tono }}` sin lista blanca: un tono desconocido quedaría sin estilo.
- **Tests a agregar:** el filtro, por cada tono y uno desconocido.
- **Verificación:** HTML renderizado idéntico; los snapshots de Becas en verde (`_lista_tarjetas` es compartido).
- **Regla para no repetirlo:** control mecánico · `scripts/design_audit.py` · «`{% if x.tono == 'success' %}badge-success` es un hallazgo: usar `|badge_tono`.» Actualizar la ficha de `_lista_tarjetas`/`_turno_tarjeta` en `.claude/design/` (componentes canónicos).

#### Aporte del segundo revisor (D4-FE-01: El color de cada situación y de cada criticidad está en cuatro lugares, dos de ellos en templates)
_Pasada 1: severidad BAJA · estado CONFIRMADO (lectura) · esfuerzo S._

- **Ubicación:** situación: `programas/services/inspecciones.py:1153-1157` (`_TONOS_DE_SITUACION`),
  `programas/views/dispositivos_relevamientos.py:152-157` (`TONO_DE_SITUACION`),
  `programas/templates/programas/dispositivos/_relevamiento_situacion_badge.html:19-24`; criticidad:
  `programas/services/inspecciones.py:987-994` (`SEMAFOROS`) y
  `programas/templates/programas/dispositivos/_relevamiento_criticidad_badge.html:6-10`
- **Escenario:** el test (`test_dispositivos_relevamientos_listado.py:1001`) ata la vista con el badge, pero no al
  servicio: el informe usa `_TONOS_DE_SITUACION` y P21 el de la vista. Si se cambia el tono de «Por vencer» en uno, el
  informe y la fila del mismo relevamiento difieren. El badge de criticidad compara `'ALTA'`/`'MEDIA'`/`'BAJA'` en el
  template, que es la escala que los propios docstrings llaman «default a confirmar con el Ministerio».
- **Causa raíz:** el template decide el color en vez de recibirlo.
- **Solución:** un único `Situacion.TONOS` en el módulo de D-LIM-30 paso 2 (vista y servicio lo importan); los dos
  parciales reciben `tono` ya resuelto (`badge-{{ tono }}`), como hace `_galeria`/`Semaforo`. Para criticidad, el
  parcial recibe `semaforo` (`SEMAFOROS` ya tiene el tono). Clases resultantes idénticas.
- **Tests a agregar:** ampliar el test de `:1001` para que compare también contra el informe.
- **Verificación:** HTML de P21 y del informe igual.
- **Regla para no repetirlo:** **control mecánico** · `scripts/design_audit.py`, regla nueva `BADGEIF` (warning,
  ratchet) · patrón: `{% if <var> == '<MAYÚSCULAS>' %}badge-` en un parcial `_*badge*.html`. Mensaje: «El tono del
  badge se resuelve en Python y llega como variable; el template no mapea códigos a colores».

---

### D-FE-06 · `legajo/form.html` lleva ~330 líneas de JS en cinco `<script>` inline
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** nuevo · **Ola:** 12 · **Esfuerzo:** S-M
- **ID de la pasada 1:** D1-FE-02
- **Ubicación:** `programas/templates/programas/dispositivos/legajo/form.html:169-193` (resumen «Qué falta para
  validar»), `:197-250` (recarga del formulario del tipo por `fetch`), `:251-368` (formset de franjas horarias),
  `:369-400` (contacto desde el responsable) y `:401-~500` (anti-duplicado). Además, `detail.html:701-704`.
- **Escenario:** el JS se comunica por eventos globales (`formulario-tipo:faltantes`) y selectores de `id`
  (`id_codigo`, `id_tipo`) atados al `auto_id` de Django. No se puede cachear, no lo ve ningún linter de JS y
  no se puede reusar en otra pantalla con franjas (por ejemplo, la configuración de turnos). El patrón del repo
  para comportamiento reusable ya existe: `nodo-formulario-tipo.js`, `nodo-buscador.js` y `nodo-sugerencias.js`.
- **Causa raíz:** cada etapa del alta sumó su bloque al template.
- **Solución:** `static/custom/js/nodo-legajo-form.js`, que monta cada comportamiento por `data-*`
  (`data-requisito-campo`, `data-formulario-tipo`, `data-franjas`, …, que ya existen). Las franjas, si se reusan, van
  en un `nodo-franjas.js` aparte. Sin cambios de DOM ni de estilos. La URL del fetch sigue en `data-url`.
- **Tests a agregar:** ninguno de Python. Revisión visual con la receta Playwright de la memoria del proyecto
  (alta y edición con cambio de tipo).
- **Verificación:** `collectstatic` y el CSP (`SecurityHeadersMiddleware`): si la política apunta a sacar
  `unsafe-inline`, esto la acerca.
- **Regla para no repetirlo:** **control mecánico** · `scripts/design_audit.py` · regla nueva en modo ratchet:
  «`<script>` inline de más de 40 líneas en `programas/templates/**`. Movelo a `static/custom/js/nodo-*.js`».

---

### D-FE-07 · Arranque del formulario dinámico del tipo copiado en dos templates
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** nuevo · **Ola:** 12 · **Esfuerzo:** S
- **ID de la pasada 1:** D2-FE-02
- **Ubicación:** `programas/templates/programas/dispositivos/estadia/detalle.html:244-252`; `programas/templates/programas/dispositivos/ingreso/paso_confirmar.html:86-96` (mismos cuatro `<script src>` + `NodoFormularioTipo.montar(...)` inline)
- **Escenario:** sumar una dependencia al motor de formularios (p. ej. un quinto script) exige recordar cada pantalla que lo monta; la que se olvide falla solo en el navegador.
- **Causa raíz:** no hay include para el arranque del componente.
- **Solución:** `templates/components/_formulario_tipo_scripts.html` con parámetro `selector` (y el CSS de `nodo-buscador` en un include gemelo de `page_css`); las dos pantallas lo incluyen.
- **Tests a agregar:** ninguno nuevo; `scripts/compile_templates.py --bloques` en 0.
- **Verificación:** las dos pantallas montan el formulario (revisión visual).
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-frontend.md` · «El formulario dinámico del tipo se arranca con `components/_formulario_tipo_scripts.html`; no se copian sus `<script>`».

---

### D-FE-08 · `bitacora.html` lleva la lógica de Alpine inline y el objeto por defecto duplicado
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** nuevo · **Ola:** 12 · **Esfuerzo:** S
- **ID de la pasada 1:** D3-FE-04
- **Ubicación:** `templates/programas/dispositivos/bitacora/bitacora.html:7-31` (unas 25 líneas de JS dentro de `x-data`; el objeto `turnoForm` por defecto está en `:12` y otra vez en `:28`). La alerta `sin_turnos` está duplicada con solo el texto distinto en `:68-72`.
- **Escenario:** se agrega un campo al turno, se actualiza una copia del default y el modal arranca con un valor viejo después de cancelar.
- **Causa raíz:** el estado del modal se escribió inline.
- **Solución:** `Alpine.data("bitacoraTurnos", ...)` en `static/custom/js/nodo-bitacora.js` con una función `turnoVacio()`; el template queda en `x-data="bitacoraTurnos(...)"`. La alerta queda como un solo bloque con el texto elegido por una variable (`{% firstof %}` o `with`). El shell del modal es el del arquetipo y no se toca.
- **Lo que NO hay que hacer:** no cambiar el marcado del modal (es del arquetipo canónico).
- **Tests a agregar:** ninguno (sin harness JS); prueba manual crear → cancelar → crear.
- **Verificación:** `design_audit --ratchet` con 0 nuevos; `compile_templates.py --bloques` en 0.
- **Regla para no repetirlo:** agente · `.claude/agents/chaco-design-system.md` · «Un `x-data` de más de 10 líneas se mueve a `Alpine.data` en un JS estático.»

---

### D-FE-09 · El template de P21 tiene los «30 días» de la ventana de por vencer escritos a mano
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** nuevo · **Ola:** 12 · **Esfuerzo:** S
- **ID de la pasada 1:** D4-FE-02
- **Ubicación:** `programas/templates/programas/dispositivos/relevamientos/list.html:30-31` frente a
  `programas/services/inspecciones.py:755` (`DIAS_POR_VENCER = 30`)
- **Escenario:** si `DIAS_POR_VENCER` pasa a 15, las tarjetas cuentan con 15 y su nota sigue diciendo «en más de 30
  días» / «en los próximos 30 días»: el número y su explicación se contradicen en la misma tarjeta.
- **Causa raíz:** la constante no viaja al contexto.
- **Solución:** `context["dias_por_vencer"] = DIAS_POR_VENCER` y en el template
  `" en más de "|add:dias_por_vencer|add:" días"` (o la nota ya armada desde el presenter de D-LIM-09). Texto
  idéntico con el valor actual.
- **Tests a agregar:** `test_dispositivos_relevamientos_listado.py::ResumenTests.test_nota_usa_dias_por_vencer` con
  `override` de la constante.
- **Verificación:** el test anterior.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-frontend.md` · «Un número de negocio (días, topes,
  umbrales) que aparece en un texto del template llega por contexto desde su constante, nunca escrito a mano».

---

### D-FE-10 · Validación del modal «Nuevo relevamiento» escrita como JS inline en un atributo
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Eje:** FE · **Origen:** nuevo · **Ola:** 12 · **Esfuerzo:** S
- **ID de la pasada 1:** D4-FE-03
- **Ubicación:** `programas/templates/programas/dispositivos/relevamientos/list.html:181-182` y `:187-188`
- **Escenario:** `@submit="if (!$el.elements.asignar.value) { $event.preventDefault(); falta = true; $el.elements.asignar.focus(); }"`
  es lógica de validación en una cadena de atributo: no la cubre lint, no se reusa (el mismo patrón «select
  obligatorio con aviso propio» aparece en otros modales de dos pasos) y un cambio de `name` del campo la rompe en
  silencio.
- **Causa raíz:** falta un componente Alpine para «select obligatorio con aviso».
- **Solución:** mover a un `Alpine.data('elegirObligatorio', (campo) => ({ falta: false, enviar(e) {…} }))` en un
  JS estático existente del módulo (p. ej. `nodo-sugerencias.js` o uno nuevo `dispositivos-relevamientos.js`) y en el
  template `x-data="elegirObligatorio('asignar')" @submit="enviar($event)"`. Mismo comportamiento y mismo texto.
- **Lo que NO hay que hacer:** sacar `novalidate` y volver al aviso nativo (el comentario de `:180` explica por qué).
- **Tests a agregar:** ninguno de Python; verificación manual o Playwright si se retoma.
- **Verificación:** el modal sigue sin enviar con el select vacío y muestra «Elegí un edificio para continuar.».
- **Regla para no repetirlo:** **control mecánico** · `scripts/design_audit.py`, regla nueva `ALPINEIF` (warning,
  ratchet) · patrón: atributo `@\w+="[^"]*\bif\s*\(` en templates. Mensaje: «Lógica con `if` en un handler inline:
  movela a un `Alpine.data` en un JS estático».

---

### D-ERR-13 · `nodo-formulario-tipo.js` vuelve a habilitar controles que el servidor renderizó deshabilitados
**Severidad:** INFO · **Estado:** PLAUSIBLE · **Eje:** ERR · **Origen:** thermos-correccion · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** D3-ERR-03
- **Ubicación:** `static/custom/js/nodo-formulario-tipo.js:77`. Se usa desde `programas/templates/programas/dispositivos/legajo/_formulario_tipo.html` y desde las pantallas de ingreso, estadía y legajo.

- **Escenario:** al mostrar un ítem condicional, el script pone `disabled = false` en todos los controles del ítem, también en los que el servidor marcó `disabled` (por ejemplo, un campo de solo lectura). Esos controles pasan a ser editables y se envían en el POST. El servidor ignora los campos `disabled` del form de Django, así que el valor no se guarda. El daño es de UX: el usuario edita algo que después se pierde.

- **Solución:** marcar con `data-` los controles que el script deshabilitó y, al mostrar el ítem, habilitar solo esos.

- **Tests a agregar:** ninguno automatizado (no hay harness de JS). Verificación manual.

- **Regla para no repetirlo:** sumar a la ficha de componente JS en `.claude/design/`: «Mostrar u ocultar condicionalmente restaura solo el estado que el propio script cambió».

---

### D-ERR-14 · Fuera de AJAX, las acciones del Equipo muestran solo el primer error de validación
**Severidad:** INFO · **Estado:** CONFIRMADO (lectura) · **Eje:** ERR · **Origen:** thermos-correccion · **Ola:** 3 · **Esfuerzo:** S
- **ID de la pasada 1:** D3-ERR-04
- **Ubicación:** `programas/views/dispositivos_equipo.py:76` (`_EquipoAccionView.post`, que usa `error.messages[0]`).

- **Escenario:** si el servicio levanta un `ValidationError` con varios mensajes, el usuario sin JS ve solo el primero. La rama AJAX tiene el mismo comportamiento, así que no hay datos incorrectos: es un error informativo.

- **Solución:** unir los mensajes con `" "`, o mandar uno por `messages.error`.

- **Regla para no repetirlo:** ninguna nueva. Se cubre con la rúbrica de UX de errores.

---

### D-PERF-06 · `plaza_ocupada_despues_de` recorre todas las salidas históricas de la plaza dentro del `FOR UPDATE`
**Severidad:** INFO · **Estado:** PLAUSIBLE · **Eje:** PERF · **Origen:** nuevo · **Ola:** 1 · **Esfuerzo:** S
- **Medición en banco (19-nov-2026):** no medida por ruta: exige dos sesiones y una plaza con 2.000 salidas. Queda como está.
- **ID de la pasada 1:** D2-PERF-02
- **Ubicación:** `programas/services/movimientos.py:121`. Lo llama `programas/services/estadias.py:421` (`_exigir_plaza_libre_desde`) desde `ingresar_persona` (`:471`), `cambiar_plaza` (`:695`) y `asignar_plaza` (`:772`), siempre con la plaza ya bloqueada y solo en una carga retroactiva (`desde < ahora`).
- **Escenario:** `EXISTS(SELECT 1 FROM programas_movimientoestadia WHERE plaza_origen_id = ? AND momento > ?)`. El único índice que sirve es el implícito de la FK `plaza_origen_id`, de una columna. Si no hay coincidencia, que es el caso normal, lee todas las salidas que la plaza tuvo: unas 10 en promedio con el supuesto (100.000 movimientos sobre 10.000 plazas) y unas 365 por año en una cama de rotación diaria. Hoy son milisegundos, pero corren con la fila de la plaza tomada y crecen sin techo con la historia de la cama.
- **Causa raíz:** `momento` no está en el índice detrás de `plaza_origen_id`.
- **Solución (solo si la medición lo justifica):** `models.Index(fields=["plaza_origen", "momento"])` en `MovimientoEstadia`. InnoDB lo adoptaría como índice de la FK. Es inocuo, porque la tabla es solo de inserción (ningún `UPDATE` que revalide la FK), así que no reabre lo que cuidan `ReservaPlaza.Meta.indexes`.
- **Lo que NO hay que hacer:** volver a sumar la rama `OR plaza_destino_id = …`, que termina en `index_merge` (`movimientos.py:116-118`).
- **Tests a agregar:** ninguno hasta medir.
- **Verificación:** `EXPLAIN ANALYZE` en el banco con una plaza de 2.000 salidas sembradas y `momento` posterior a todas: `rows` antes ≈ 2.000, después ≈ 0.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/rendimiento.md` · la misma regla de D-PERF-02 (predicado de rango detrás de la igualdad), con énfasis en las lecturas que corren dentro de un `select_for_update`.

---

### D-PERF-07 · La fila del dispositivo serializa la operación: cada novedad de bitácora la toma con X y cada ingreso, egreso o cambio necesita S por FK
**Severidad:** INFO · **Estado:** PLAUSIBLE · **Eje:** PERF · **Origen:** posible duplicado con la tajada de bitácora (si allí se registró, queda la de allí) · **Ola:** 1 · **Esfuerzo:** S
- **Medición en banco (19-nov-2026):** no medida por ruta: es una prueba de concurrencia (dos sesiones). Queda como está.
- **ID de la pasada 1:** D2-PERF-03
- **Ubicación:** `programas/services/bitacora.py:426` (`registrar_entrada` → `_bloquear_dispositivo`), con la escritura de adjuntos al storage bajo ese candado en `bitacora.py:463` (`_guardar_adjuntos`). Del lado de esta tajada están los `INSERT` con FK a `Dispositivo` de `estadias.py:502`, `:520` (vía `movimientos.py:78`), `:528` y `:530`.
- **Escenario:** durante el turno, cada operador que carga una novedad toma X sobre la fila del dispositivo hasta el commit, incluida la escritura de hasta `MAX_ADJUNTOS_POR_ENTRADA` archivos. Mientras tanto, todo ingreso, egreso, cambio o asignación de plaza de ese dispositivo espera el S de la FK. No hay mecanismo que crezca: la espera dura lo que dura la escritura de los archivos, que hoy son milisegundos en disco local. Se volvería un problema con un storage remoto o archivos grandes.
- **Causa raíz:** se usa el candado del dispositivo para frenar el doble envío de la novedad (`bitacora.py:423-425`), y es la misma fila que los movimientos leen en modo compartido.
- **Solución (solo si la medición lo justifica):** escribir los adjuntos **antes** de tomar el candado (`archivos_atomicos` ya los borra si la transacción se deshace) y dejar bajo el candado solo el chequeo de duplicado y los `INSERT`. Es un cambio de la tajada de bitácora, no de esta.
- **Tests a agregar:** ninguno hasta medir.
- **Verificación:** con dos sesiones. S1 simula `registrar_entrada` con `SELECT id FROM programas_dispositivo WHERE id=D FOR UPDATE` y no cierra. S2 hace un `INSERT` en `programas_trazadispositivo` (o un ingreso real por la vista) con `dispositivo_id=D` y queda esperando hasta el `COMMIT` de S1. Ver `information_schema.INNODB_LOCK_WAITS`.
- **Regla para no repetirlo:** **skill** · `.claude/skills/mysql-mariadb/SKILL.md` §Transacciones y bloqueos · «Bajo un `select_for_update` sobre una fila que muchas transacciones leen por FK (dispositivo, programa) no se escribe al storage ni se llama a nada externo: primero los archivos, después el candado.»

---

### D-PERF-08 · El listado de Edificios calcula tres subconsultas y un GROUP BY sobre todo el alcance antes de recortar la página
**Severidad:** BAJA · **Estado:** MEDIDO en banco · **Eje:** PERF · **Origen:** nuevo · **Ola:** 4 · **Esfuerzo:** S-M
- **Medición en banco (19-nov-2026):** `/dispositivos/edificios/` / `?page=200` / `?estado=CRITICO` / `?estado=SIN_RELEVAR`: 203 / 199 / 196 / 36 ms en la segunda medición (13-16 consultas), ya con el filtro de verdad (la primera usaba `ACTIVO`, que no filtraba). `COUNT` de 5.000 filas con tres subconsultas, 250 ms la consulta. Pasa de INFO a BAJA por el número; no sube más.
- **ID de la pasada 1:** D4-PERF-02
- **Ubicación:** `programas/selectors/edificios.py:148-164` (`para_el_listado`), `:113-128` (`filtrar_edificios`,
  filtros `estado` y `compartido`); `programas/views/dispositivos_edificios.py:46-57`.
- **Escenario:** `/dispositivos/edificios/` pagina de a 25, pero la consulta de la página es SELECT …, (última
  realizada), COUNT(DISTINCT vínculos), EXISTS(vencido), (vence_el) FROM edificio LEFT JOIN vínculos … GROUP BY
  edificio.id ORDER BY nombre, id LIMIT 25 OFFSET n. Con GROUP BY por pk y ORDER BY nombre, el motor agrupa todo el
  alcance, evalúa las subconsultas de cada grupo y recién después ordena y recorta (la forma de la trampa 4 de la
  rúbrica). Con el filtro `estado`, la subconsulta de la última realizada (y la de su criticidad) va al WHERE y corre
  por cada edificio del alcance. Cada subconsulta usa Index(edificio, estado, realizada_en): N edificios × 3
  búsquedas por índice; con cientos de edificios, milisegundos.
- **Causa raíz:** las anotaciones que solo necesita la fila se calculan en la consulta que elige la página.
- **Solución (solo si el banco lo pide):** elegir la página con la consulta liviana (filtros + orden por nombre y pk +
  values_list del pk) y rehidratar esos 25 con `para_el_listado(Edificio.objects.filter(pk__in=ids))`, reordenando en
  Python con el orden de la página. Mismas filas y orden. El filtro por estado sigue en SQL.
- **Lo que NO hay que hacer:** no pasar el filtro de estado a Python (rompe la paginación); no agregar índices sin EXPLAIN.
- **Tests a agregar:** el presupuesto `dispositivos_edificios_listado` ya fija el número de consultas; el cambio suma
  una (la de ids) y exige actualizar `scripts/perf_budgets.json` con su motivo.
- **Verificación:** banco MariaDB (3310) con 5.000 edificios y 50.000 inspecciones: tiempo de la página 1 y de una
  profunda, sin filtro y con estado; EXPLAIN ANALYZE solo en el banco. Debajo de 100 ms, se descarta.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/rendimiento.md` §Trampas medidas ·
  agregar a la trampa 4: «Lo mismo con annotate(Count(...)) sobre una relación múltiple más subconsultas escalares:
  el GROUP BY obliga a calcular todo antes del LIMIT; elegir la página por pk y anotar después.»

---

### D-PERF-09 · El detalle arma el mapa completo de plazas solo para saber si hay alguna libre
**Severidad:** INFO · **Estado:** MEDIDO en banco · **Eje:** PERF · **Origen:** nuevo · **Ola:** 4 · **Esfuerzo:** S
- **Medición en banco (19-nov-2026):** detalle del dispositivo grande (500 plazas): 3.807 / 2.429 ms en la primera medición. El tiempo lo domina el historial y las estadías (D-DAT-01 y D-PERF-01), no el mapa de plazas. Se mantiene INFO.
- **ID de la pasada 1:** D1-PERF-03
- **Ubicación:** `programas/views/dispositivos_legajo.py:461-464`, que llama a `_mapa_de_ingreso()` (`:421-425`),
  que llama a `programas/services/ingreso.py:129` (`plazas_para_ingresar`).
- **Escenario:** a quien tiene `dispositivo.admitir`, con al menos una estadía activa en la página (la solapa por
  defecto, «Alojadas»), el detalle lee todos los sectores y plazas del dispositivo, deriva el estado de cada una
  (`estado_de_plazas`: estadías activas y reservas vigentes con el nombre de la persona), las ordena con
  `clave_natural` y arma los dicts del mapa del asistente, y usa solo `bool(plazas_elegibles)` para el texto
  «No hay plazas libres en el dispositivo.». Son 4 consultas fijas (ya presupuestadas en
  `dispositivos_detalle_sin_estadias`) y filas = plazas del dispositivo (≈50 de promedio, cientos en un parador
  grande). **No crece con el tiempo**, solo con el tamaño del dispositivo: por eso INFO.
- **Causa raíz:** se reutiliza la función del modal de cambio de plaza (que sí necesita el mapa) para una
  pregunta de sí o no.
- **Solución:** solo si la medición lo justifica: una función `hay_plaza_elegible(dispositivo)` en
  `programas/services/ingreso.py` que aplique la misma regla (tipo admitido, operativa, sin estadía activa ni
  reserva que cuente) con un `exists()`; el modal sigue usando `plazas_para_ingresar`. El texto y el
  comportamiento no cambian. Si mantener las dos reglas alineadas cuesta, no vale la pena.
- **Verificación (medición que falta):** `perfil_ruta.py "/dispositivos/<pk_grande>/"` con un dispositivo de 500
  plazas y 300 estadías activas, comparando el tiempo propio de `plazas_para_ingresar` en el perfil contra el
  total de la vista. Si es menos del 5 % del request, se cierra sin cambio.
- **Regla para no repetirlo:** **agente** · `.claude/agents/chaco-auditor.md` · «Una función que arma una
  estructura de pantalla no se llama para responder un booleano en otra: si solo hace falta saber si hay alguno,
  `exists()` con la misma regla.»

---

### D-PERF-10 · El informe de un relevamiento repite consultas de costo fijo (COUNT de fotos y alcance del coordinador dos veces)
**Severidad:** INFO · **Estado:** MEDIDO en banco · **Eje:** PERF · **Origen:** nuevo · **Ola:** 4 · **Esfuerzo:** S
- **Medición en banco (19-nov-2026):** informe de un relevamiento: 88 / 49 ms, 12 consultas. Se mantiene INFO.
- **ID de la pasada 1:** D4-PERF-03
- **Ubicación:** `programas/services/inspecciones.py:1221-1223` (`informe_de_relevamiento`: `fotos.count()` y la lista
  completa de fotos), `:1233` → `:490` (`puede_revisar` sin `edificios_gestionables`) y `:1223` → `:1092`
  (`ve_la_asignacion` → `edificios_con_asignacion_visible`).
- **Escenario:** «Ver informe» de un relevamiento realizado y sin revisar, abierto por un coordinador:
  `total_fotos = inspeccion.fotos.count()` y en la línea siguiente se traen todas las fotos (el docstring lo dice), así
  que el COUNT es len(fotos). Además `puede_revisar` y `ve_la_asignacion` corren cada uno
  `edificios_en_alcance(usuario, CAP_ASIGNAR).filter(pk=edificio_id)`, la misma pregunta con el mismo árbol de
  subconsultas. Dos consultas de más por informe; no crece con nada.
- **Causa raíz:** cada helper resuelve el alcance por su cuenta y el total se pide aparte de la lista.
- **Solución:** `total_fotos = len(fotos)`; resolver una vez
  `gestionables = edificios_con_asignacion_visible(usuario, [inspeccion.edificio_id])`, pasarlo a
  `puede_revisar(..., edificios_gestionables=gestionables)` y derivar la visibilidad de la asignación como asignado
  propio o edificio en `gestionables` (con la guarda de autenticado que ya tiene `ve_la_asignacion`). Mismo resultado.
- **Lo que NO hay que hacer:** no limitar la lista de fotos: el Cambio 423 decidió mandarlas todas.
- **Tests a agregar:** `programas/tests/test_dispositivos_informe_relevamiento.py::InformePresupuestoTests.test_costo_fijo`
  (assertNumQueries con 1 y 30 fotos, coordinador no admin).
- **Verificación:** el test de presupuesto baja dos consultas.
- **Regla para no repetirlo:** **skill** · `.claude/skills/auditoria/rubricas/rendimiento.md` §Búsquedas activas ·
  «.count() sobre un queryset que la misma función materializa entero: usar len().»

---
