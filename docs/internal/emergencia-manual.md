# Módulo Emergencia — manual para QA y para quien opera

Qué es el módulo, cómo se habilita, qué pantalla hace qué y qué hay que probar. Es el manual **del backend tal como quedó**
(PRs 0 a 11, ramas `feat/emergencia-*`): ante una diferencia con el análisis funcional (rama `docs/emergencia-analisis`,
`docs/internal/emergencia/`), gana el código, y las correcciones al análisis están en las entradas del registro. El registro
de decisiones son los Cambios 457 a 469 de [`requerimientos.md`](requerimientos.md) (`scripts/requerimientos.py --tag
emergencia`); lo que pide y devuelve la app está en [`contrato-app-emergencia.md`](contrato-app-emergencia.md).

> **Estado (12/11/2026):** nada está mergeado a `development`. La app (PWA) del módulo **todavía no existe**: la API está lista y
> probada, pero las pantallas M1, M2 y M3 de `Chaco-mobile` están bloqueadas. Todo lo de la app se prueba hoy contra la API.

---

## 1. En una página

Ante una crecida, la mesa de operaciones del Ministerio necesita saber qué familias se evacuaron, dónde están, cuántas camas
quedan en cada centro y qué insumos salieron hacia cada uno. Emergencia tiene dos carriles:

| Carril | Empieza | Termina | Queda registrado |
|---|---|---|---|
| **Casos** (familias) | El agente territorial, desde la app (o la mesa, a mano) | El dispositivo que aloja a la familia | La familia, sus integrantes, el dispositivo y la cama de cada persona, con el tiempo de cada paso |
| **Kits** (insumos) | La mesa, desde el backoffice | El dispositivo que recibe | Qué salió, qué llegó y las diferencias |

Nada se duplica: la persona es el `Ciudadano` del legajo, la cama es una `Plaza` de Dispositivos, el alojamiento es una
`Estadia` (una por persona) y la reserva es una `ReservaPlaza`. Emergencia agrega el **caso** (el hilo que une todo eso en el
tiempo) y la **entrega de kits**.

```
 TERRITORIO              MESA (backoffice)                     DISPOSITIVO (backoffice o app)
 1 RELEVAR ──caso──▶ 2 TOMAR y DERIVAR ──derivación──▶ 3 ALOJAR
                       4 KITS: armar → en camino ─────────▶ 4 KITS: recibir → diferencias
                       5 SEGUIR: tablero del supervisor
```

---

## 2. Roles: qué tilda el PM

El programa **Emergencia** lo crea la migración (`programas.0117`) y el seed: no hay que darlo de alta. **No hay roles
sembrados** salvo el Administrador, que recibe `emergencia.operar`, `emergencia.supervisar` y `emergencia.recibir_kit`
(`users.0047`). Los demás los arma el PM en **Usuarios → Roles**. Se autoriza solo por capacidad; el nombre del rol es libre.

| Rol en la vida real | Programa del rol | Capacidades a tildar | Además |
|---|---|---|---|
| **Agente territorial** | Emergencia | `emergencia.relevar` (solapa «Emergencia») | Es una capacidad de campo: el usuario entra a la app, no al backoffice. |
| **Operador de mesa** | Emergencia | `emergencia.operar` | — |
| **Supervisor de mesa** | Emergencia | `emergencia.supervisar` (con o sin `operar`: supervisar ya incluye todo lo de operar) | — |
| **Guardia del dispositivo** | **Dispositivos** | `dispositivo.admitir` (llegadas), `emergencia.recibir_kit` (kits, solapa «Dispositivos» → «Emergencia en el dispositivo»), `dispositivo.egresar` (egresos), `dispositivo.ver` | **Tiene que integrar el Equipo del dispositivo** (detalle del dispositivo → Equipo) con ese rol. Sin Equipo la capacidad no alcanza a ningún dispositivo. |
| Administrador del programa Dispositivos | Dispositivos | (el que ya tiene) | Opera todos los dispositivos sin Equipo **si su rol tiene** `admitir` / `recibir_kit`. Sin ellas la app le abre el módulo pero no le ofrece pantallas (`perfil.dispositivo = false`). |

Reglas que conviene saber al armar roles:

- Las `emergencia.relevar/operar/supervisar` **solo se pueden tildar en un rol del programa Emergencia**, y
  `emergencia.recibir_kit` **solo en uno de Dispositivos** (el ABM no deja otra cosa).
- Para ver el legajo de una persona desde la ficha de un integrante hace falta además `ciudadano.ver`.
- Un usuario puede tener varios roles (un supervisor suele ser también operador; un guardia puede ser agente).
- El ciudadano del portal no llega a ninguna URL de Emergencia (lo frena el middleware del portal).

**Respuestas esperables:** sin la capacidad del módulo, **403**. Con la capacidad pero pidiendo por id algo de **otro**
dispositivo (una derivación, una entrega, una llegada), **404**, igual que un id que no existe (Cambio 432).

---

## 3. Pantallas del backoffice

| Pantalla | URL | Quién | Cómo se llega |
|---|---|---|---|
| **E1 · Tablero** | `/emergencia/tablero/` | supervisar | Sidebar → Programas → «Tablero de Emergencia» |
| **E2 · Bandeja de casos** | `/emergencia/casos/` | operar o supervisar | Sidebar → Programas → «Emergencia» |
| «Nuevo caso» (Formulario 1 de la mesa) | `/emergencia/casos/nuevo/` | operar o supervisar | Botón de E2 |
| **E3 · Ficha del caso** | `/emergencia/casos/<id>/` | operar o supervisar (actuar: quien lo tomó, o supervisar) | Fila de E2 |
| **E4 · Entregas de kits** | `/emergencia/entregas/` | operar o supervisar | Sidebar → Programas → «Entregas de kits» |
| Nueva entrega (3 pasos) | `/emergencia/entregas/nueva/` → `…/nueva/<dispositivo>/` → `…/confirmar/` | operar o supervisar | Botón de E4 |
| **E5 · Detalle de la entrega** | `/emergencia/entregas/<id>/` | operar o supervisar | Fila de E4 |
| **E6 · Emergencia · Llegadas** | `/dispositivos/<id>/emergencia/llegadas/` | `dispositivo.admitir` en el Equipo de ese dispositivo | Detalle del dispositivo → menú → «Emergencia · Llegadas» |
| E6 · Integrantes de la familia | `/dispositivos/<id>/emergencia/llegadas/casos/<caso>/` | ídem | Después de aceptar, o desde Llegadas |
| E6 · Ficha de una persona | `…/casos/<caso>/integrantes/<n>/` | ídem | Integrantes |
| E6 · Elegir cama | `…/casos/<caso>/integrantes/<n>/cama/` | ídem | Ficha (abre el mapa de plazas en modo emergencia) |
| E6 · Familia alojada / diferencia / cancelar | `…/casos/<caso>/alojar/`, `…/diferencia/`, `…/cancelar/` | ídem | Integrantes |
| E6 · Ingresar igual (sin derivación) | `/dispositivos/<id>/emergencia/llegadas/ingreso-directo/` | ídem | Llegadas, cuando el DNI no tiene derivación y hay camas |
| E6 · Avisar a la mesa | `/dispositivos/<id>/emergencia/llegadas/avisar/` | ídem | Llegadas, cuando el DNI no tiene derivación |
| **Kits del dispositivo** (recepción web) | `/emergencia/dispositivos/<id>/kits/` y `…/kits/<entrega>/recibir/` | `emergencia.recibir_kit` en el Equipo de ese dispositivo | Detalle del dispositivo → menú → «Emergencia · Kits» |
| **E7 · Configuración** | `/emergencia/config/` | supervisar | Sidebar → Programas → «Configuración de Emergencia» |

### E7 · Configuración (valores de fábrica)

| Campo | Fábrica | Regla |
|---|---|---|
| Nombre del evento | Emergencia | Se ve en el tablero y la bandeja |
| Objetivo para tomar / derivar / aceptar / alojar | 15 / 30 / 120 / 60 min | ≥ 1 |
| Vigencia de la derivación | 720 min | ≥ 30. Vale para las derivaciones **nuevas**; las ya creadas conservan su vencimiento |
| Minutos sin avance antes de devolver a la bandeja | 60 | 0 apaga la regla |
| Umbral «por vencer» | 80 % | Entre 50 y 95 |
| Catálogo de kits | vacío | Nombre único y unidad; se **desactiva**, no se borra |

Cada cambio deja traza por campo.

### Estados

| Caso | Significa |
|---|---|
| `NUEVO` | Entró y nadie lo tomó (tramo «tomar») |
| `EN_GESTION` | Un operador lo tiene (tramo «derivar») |
| `DERIVADO` | Hay una derivación pendiente (tramo «aceptar») |
| `INGRESO_EN_CURSO` | El dispositivo aceptó y está confirmando personas (tramo «alojar») |
| `ALOJADO` | Familia alojada (completa, o con diferencia y la marca de ingreso parcial) |
| `CERRADO` | Sin alojamiento (no requiere, sin contacto, asistido en domicilio, se alojó por su cuenta, otro) o «todos egresados» |

| Derivación | | Entrega de kit | |
|---|---|---|---|
| `PENDIENTE` | esperando al dispositivo | `PREPARADA` | armada |
| `ACEPTADA` | camas reservadas | `EN_CAMINO` | despachada |
| `RECHAZADA` | con motivo (sin plazas, no cumple perfil, no llegó, otro) | `RECIBIDA` | sin diferencias |
| `VENCIDA` | por el cron | `RECIBIDA_CON_DIFERENCIAS` | faltó o sobró algo |
| `CANCELADA` | por la mesa | `CANCELADA` | por la mesa, con motivo |

El **semáforo de SLA** (en término / por vencer / fuera) mide el tramo del estado actual contra su objetivo de E7, con texto
además del color. Los casos alojados y cerrados no tienen semáforo.

---

## 4. Flujo de punta a punta

### Etapa 1 · Relevar

- **Desde la app** (agente con `emergencia.relevar`): Formulario 1 en cuatro pasos (traslado y responsable, personas que ingresan
  juntas, quiénes necesitan asistencia, ubicación y fotos). Funciona sin señal: queda en cola y se envía al volver la conexión. El mismo envío dos veces crea **un**
  caso. Fotos JPEG de hasta 5 MB; sin dirección, se rechaza.
- **Desde la mesa** (E2 → «Nuevo caso»): el mismo formulario en una página con cuatro bloques.
- El servidor calcula el total declarado y la prioridad, numera el caso («2026-C-000031») y lo deja `NUEVO`, con origen
  Territorio o Mesa. El responsable queda dado de alta como `Ciudadano` si no existía.

### Etapa 2 · Tomar y derivar (E2, E3)

1. El operador **toma** el caso (si dos lo toman a la vez, gana uno y el otro recibe «Tomado por …»). Quien no lo tiene ve la
   ficha en solo lectura; el supervisor actúa sin tomarlo y la traza dice «por supervisor».
2. Registra **contactos** con la familia y puede **cambiar la prioridad**.
3. **Deriva**: el panel Derivar lista los dispositivos elegibles (activos y que admiten camas) con plazas libres y reservadas,
   distancia (o «desconocida» sin GPS) y la marca Alcanza / Faltan N / Sin plazas. A lo sumo una derivación vigente por caso.
   El caso pasa a `DERIVADO` y la derivación vence a los minutos de vigencia de E7.
4. Puede **cancelar** la derivación pendiente (con motivo), **soltar** el caso (el propio; el supervisor, cualquiera),
   **reasignarlo** (solo supervisar) o **cerrarlo sin alojamiento** con motivo.

### Etapa 3 · Alojar (E6 o app M2)

1. La guardia **busca por DNI** (de cualquier persona de la familia). Tres resultados: hay derivación a este dispositivo; la
   persona ya está alojada en la red; o «sin derivación vigente» — también cuando la derivación es para **otro** dispositivo, que
   no se nombra.
2. **Acepta** (reserva sola hasta las camas pedidas; menos es válido y se avisa; con 0 libres no se puede) o **rechaza** con
   motivo (el caso vuelve a la mesa con «Rechazado por X»). Una derivación ya vencida se puede aceptar mientras el cron no la
   marcó.
3. Por cada persona: **ficha mínima** (parentesco, DNI, nombre, apellido, sexo, fecha de nacimiento —vale aproximada—, las cinco
   preguntas de avisos críticos y adulto responsable si es menor de 16) y **cama** en el mapa de plazas (selección única). Se
   puede **agregar** una persona que no estaba declarada. Las secciones 4 a 8 de la ficha se completan después.
4. Con todas confirmadas, **«Familia alojada»** («N de N»): el caso queda `ALOJADO`. Si llegaron menos, **cerrar con diferencia**
   con motivo (quedó con familiares, no llegó al centro, derivado a salud, otro); las camas sobrantes se liberan. Si no se
   confirmó a nadie, **cancelar el ingreso** (vuelve a la mesa).
5. **Persona que no sabe su número de DNI:** no se le da cama; el ingreso se cierra con diferencia, motivo «Otro» y la
   observación. Quien perdió el documento pero sabe el número entra con «no tiene DNI físico».
6. **Familia sin derivación en la puerta:** «Ingresar igual» (ingreso directo, solo con camas libres; nace `INGRESO_EN_CURSO` y
   se marca en la bandeja) o «Avisar a la mesa» (crea un caso `NUEVO` con la marca «En la puerta de X»).
7. **Egreso:** cuando egresa (desde Dispositivos, como siempre) el último integrante alojado, el caso se cierra solo («Todos
   egresados»).

Aceptar, alojar y cerrar con diferencia dejan una novedad automática en la **bitácora del turno** del dispositivo. **Si no hay
turno vigente, no se escribe** (no es un error: la traza del caso queda igual).

Detrás de escena, las camas de la familia son reservas «de derivación» a nombre del responsable: **el ingreso normal de una
persona en Dispositivos no las libera** (excepción a la D2 del Cambio 409, ver Cambio 463), y en el mapa se ven como reservadas.

### Etapa 4 · Kits (E4, E5, recepción)

1. La mesa **arma** una entrega (destino activo, ítems activos del catálogo, cantidades > 0) → `PREPARADA`, numerada
   «2026-K-000031».
2. La **marca en camino** (transporte y hora de salida opcionales) o la **cancela** con motivo.
3. La guardia **recibe** (web o app): una cantidad ≥ 0 por línea y la **foto del remito** (JPEG, hasta 5 MB). Queda `RECIBIDA` o
   `RECIBIDA_CON_DIFERENCIAS` (también si llegó de más). Se puede recibir una `PREPARADA` (la traza lo dice). Con conexión
   obligatoria; el reintento con el mismo identificador no duplica.
4. En E5 la mesa ve enviado / recibido / diferencia, deja una **observación** (no cambia cantidades) y puede **reponer**: una
   entrega nueva precargada con lo que faltó.

No hay stock ni depósitos: las cantidades son las del remito.

### Etapa 5 · Seguir (E1)

El supervisor ve el hero con los números del día (el día operativo empieza a las **06:00** hora Argentina), las tarjetas, la red
de plazas, los tiempos por tramo, las entregas en camino y los **avisos**. Sin auto-refresh: «Actualizar» recarga.

---

## 5. Vencimientos

Los corre el comando de siempre, `python manage.py procesar_vencimientos`, junto con los de Becas. Dos reglas:

| Regla (`--solo`) | Qué hace | Se apaga |
|---|---|---|
| `emergencia.derivacion` | Una derivación `PENDIENTE` con el vencimiento pasado pasa a `VENCIDA`; el caso vuelve a `EN_GESTION` con el mismo operador y la marca «Derivación vencida · volver a derivar». Una `ACEPTADA` no vence. | — |
| `emergencia.caso_sin_avance` | Un caso `EN_GESTION` sin ninguna traza en los últimos «minutos sin avance» de E7 vuelve a `NUEVO`, sin dueño. | Con 0 en E7 |

Son idempotentes (una segunda corrida no toca nada), van caso por caso (si en el medio el dispositivo aceptó, la fila se saltea)
y `--dry-run` cuenta sin tocar.

> **Ojo al operar:** hoy el comando corre **una vez por día** (03:10) y al arrancar el contenedor. Para una emergencia real hay
> que programar una corrida frecuente (por ejemplo cada 5 minutos) de
> `procesar_vencimientos --solo emergencia.derivacion` y `--solo emergencia.caso_sin_avance`. Está como pendiente en el Cambio
> 461. Para QA, correrlo a mano.

---

## 6. Avisos

### En el tablero (E1)

Se calculan al abrir la pantalla; no se cierran a mano: desaparecen cuando su origen se resuelve. Cada uno enlaza al caso o a la
entrega (sin la capacidad de la mesa, se ve sin enlace). Cada regla muestra los más urgentes y resume el resto en «y N más».

| Aviso | Severidad | Se resuelve |
|---|---|---|
| Caso fuera de SLA | alta | Avanzando el caso (o subiendo el objetivo en E7) |
| Derivación rechazada sin nueva acción | alta | Derivando de nuevo o cerrando |
| Dispositivo sin plazas con derivación pendiente | alta | Cancelando la derivación o liberando plazas |
| Familia «en la puerta» de un dispositivo | alta | Tomando el caso y derivándolo |
| Derivación por vencer | media | Que el dispositivo responda, o cancelándola |
| Ingreso parcial sin revisar | media | Registrando un contacto con la familia **después** del alojamiento (E3) |
| Entrega con diferencias sin revisar | media | Escribiendo la observación de la mesa en E5 |

### En la bandeja y la ficha (E2, E3)

Marcas que se van con la siguiente acción sobre el caso: «Rechazado por X: motivo», «Derivación vencida · volver a derivar»,
«Dispositivo inactivo · volver a derivar», «Llegaron N sobre M declaradas» y «En la puerta de X».

---

## 7. La app (API)

El contrato completo es [`contrato-app-emergencia.md`](contrato-app-emergencia.md). En resumen:

- **Login** (el mismo de la app): `modulos` trae `"emergencia"` si el usuario tiene `emergencia.relevar` en el programa, o es de
  la guardia de algún dispositivo (`admitir` o `recibir_kit` con Equipo), o administra el programa Dispositivos. Las claves del
  login no cambian.
- **Perfil** (`/api/emergencia/perfil/`): `relevar` abre «Ingreso de familias» (M1); `dispositivo` abre «Llegada de familias» (M2)
  y «Recepción de kits» (M3).
- **M1**: consulta de personas propia de Emergencia, localidades, enviar una familia (multipart, idempotente por `uuid_cliente`,
  funciona encolado sin señal) y «Mis envíos».
- **M2**: todo lo de E6, con **conexión obligatoria** salvo el ingreso directo. Confirmar, agregar persona e ingreso directo son
  idempotentes; aceptar, rechazar, alojar y los cierres no: un reintento da 409 y la app recarga.
- **M3**: mis dispositivos, entregas de un dispositivo, detalle y recibir (idempotente, con conexión).
- **Errores:** sin módulo, 403 `SIN_MODULO`; recurso de otro dispositivo, 404; el estado cambió (otra guardia, la mesa, el cron),
  409 con `{detail, estado_actual}`.

La web y la app llaman a **las mismas funciones**: lo que se prueba en una vale para la otra, salvo la presentación.

---

## 8. Casos de prueba de alto nivel

Para que QA (PR 13) los convierta en casos por task (primera línea «Ambiente: testing»). Usar datos de prueba, nunca datos
reales de familias. Lo marcado **(motor real)** solo se puede verificar contra MySQL/MariaDB (testing o CI), no en SQLite.

### Habilitación y permisos

1. El programa Emergencia existe después del deploy, sin correr ningún comando.
2. El Administrador ve «Emergencia», «Entregas de kits», «Tablero de Emergencia» y «Configuración de Emergencia».
3. Un rol de Emergencia con solo `operar` ve la bandeja y las entregas, **no** el tablero ni E7 (403 por URL).
4. `emergencia.recibir_kit` no se puede tildar en un rol de Emergencia; `emergencia.operar` no se puede tildar en uno de Becas ni
   de Dispositivos.
5. Un usuario con roles de Becas o de relevamiento edilicio no abre ninguna URL de `/emergencia/` (403) ni recibe `"emergencia"`
   en el login.
6. Guardia del dispositivo A: abre Llegadas y Kits de A; con el id de B, 404; en la búsqueda por DNI de una familia derivada a B,
   «sin derivación vigente» sin nombrar B.
7. Guardia con la capacidad pero sin Equipo: no abre Llegadas de ningún dispositivo (403) y el perfil de la app da
   `dispositivo: false`.

### Etapa 1 · Relevar

8. Caso desde «Nuevo caso»: numerado, `NUEVO`, prioridad y total calculados, responsable con legajo.
9. Caso desde la API con fotos válidas; el mismo `uuid_cliente` dos veces crea uno solo.
10. Foto de más de 5 MB o que no es JPEG → 400; sin dirección → 400.
11. «Mis envíos» lista solo los del agente.
12. Posibles duplicados: otro caso abierto con una persona en común (responsable o integrante confirmado) se señala en la
    bandeja y en la ficha; un responsable que ya está alojado en la red, también.

### Etapa 2 · Tomar y derivar

13. Tomar: el caso pasa a `EN_GESTION`; otro operador ve solo lectura y «Tomado por …».
14. Dos operadores toman a la vez: gana uno **(motor real)**.
15. Soltar el propio; soltar el ajeno solo como supervisor; reasignar solo como supervisor (con traza «por supervisor»).
16. Contacto y cambio de prioridad solo con el caso tomado (o supervisor).
17. Derivar: el panel lista solo dispositivos activos que admiten camas; Alcanza / Faltan N / Sin plazas; segunda derivación
    vigente imposible.
18. Cancelar la derivación pendiente con motivo; cerrar sin alojamiento con cada motivo.
19. Semáforo: un caso que supera el objetivo de su tramo pasa a «por vencer» (al umbral) y a «fuera de SLA»; aparece en la
    solapa «Fuera de SLA».
20. Las ocho solapas cuentan bien y los filtros se combinan.
21. Segunda pestaña: actuar sobre un caso que otro ya cambió da el mensaje de «cambió de estado» y no pisa nada.

### Vencimientos

22. Con la vigencia en el mínimo (30 min) y la hora pasada, `procesar_vencimientos --solo emergencia.derivacion` deja la
    derivación `VENCIDA` y el caso `EN_GESTION` con la marca; una segunda corrida no hace nada.
23. Una derivación `ACEPTADA` nunca vence.
24. `--solo emergencia.caso_sin_avance` devuelve a «Nuevos» el caso abandonado; con 0 en E7 no hace nada.
25. Cambiar la vigencia en E7 no mueve el vencimiento de las derivaciones ya creadas.
26. Aceptar y vencer a la vez: gana uno **(motor real)**.

### Etapa 3 · Alojar (repetir en E6 y en la API)

27. Buscar por DNI del responsable y de un integrante confirmado; los tres resultados.
28. Aceptar con camas de sobra; con menos camas que las pedidas (aviso «Reservé N de M»); con 0 libres (no deja).
29. Rechazar con cada motivo; «Otro» exige observación; la mesa ve «Rechazado por X».
30. Confirmar a cada persona con la ficha mínima: cada faltante se informa; menor de 16 sin adulto responsable no confirma.
31. Elegir cama en el mapa: solo una; la reservada para la familia se puede elegir, la reservada ajena no.
32. Agregar una persona no declarada y confirmarla.
33. «Familia alojada» con N de N; con una sin confirmar no deja.
34. Cerrar con diferencia: el caso queda `ALOJADO` con «Llegaron N sobre M»; las camas sobrantes quedan libres en el mapa.
35. Persona sin número de DNI: no se confirma; se cierra con diferencia «Otro».
36. Cancelar un ingreso sin confirmados: el caso vuelve a la mesa y las camas se liberan; con un confirmado no deja.
37. Ingreso directo con camas libres (aparece en la solapa «Ingreso directo»); sin camas no deja; «Avisar a la mesa» crea un
    caso «En la puerta de X».
38. **Regresión de Dispositivos:** ingresar al responsable por el asistente normal de Dispositivos **no** libera las camas
    reservadas de su familia; una reserva común de otra persona sigue liberándose al ingresar (D2 del Cambio 409).
39. Egresar a todos los integrantes desde Dispositivos cierra el caso («Todos egresados»).
40. Bitácora: con turno vigente, aceptar, alojar y cerrar con diferencia dejan su novedad; sin turno, no, y el caso avanza igual.
41. Una guardia acepta desde el backoffice y otra desde la app a la vez: una recibe 409 y recarga **(motor real)**.
42. La guardia ve las fotos del caso; un usuario sin alcance no.

### Etapa 4 · Kits

43. Armar una entrega: destino inactivo no; ítem inactivo no; cantidad 0 no; ítem repetido no.
44. Marcar en camino; hora de salida futura no.
45. Cancelar con motivo; una recibida no se cancela.
46. Recibir sin diferencias → `RECIBIDA`; con faltantes o sobrantes → `RECIBIDA_CON_DIFERENCIAS`; sin remito o remito no JPEG o
    > 5 MB → error; recibir una `PREPARADA` deja la traza «sin marca de salida».
47. Reintento de la recepción con el mismo identificador: no duplica; con otro, 409 «ya la recibió …».
48. Observación de la mesa: no cambia cantidades; la traza guarda la anterior.
49. Reponer precarga las diferencias y solo vale para una recibida con diferencias del mismo dispositivo.
50. Guardia de A no recibe una entrega de B (404). La mesa cancela mientras la guardia recibe: gana uno **(motor real)**.

### Etapa 5 · Tablero y configuración

51. Solo supervisar abre E1 y E7.
52. Cada número del tablero contra un escenario armado a mano (incluido el corte del día a las 06:00).
53. Cada aviso aparece con su condición y desaparece al resolverla; «y N más» cuando hay muchos.
54. Programa sin datos: el tablero abre sin errores.
55. E7: vigencia < 30 y umbral fuera de 50-95 se rechazan; un tipo de kit se desactiva y deja de ofrecerse en una entrega nueva.

### Rendimiento

56. Con muchos casos abiertos (cientos), la bandeja, la ficha y el tablero responden sin demora visible (presupuestos fijados por
    test: E2 en 17 consultas, E3 en 18, E1 en 16).

---

## 9. Limitaciones conocidas

- **Plazas libres** (panel Derivar y tablero) cuenta todas las plazas del dispositivo, no solo las camas. Sin decidir.
- **Sin distancia sin GPS:** las localidades no tienen coordenadas.
- **Sin aviso automático a la familia:** el contacto se registra a mano.
- **Sin revisión visual en navegador** de ninguna pantalla nueva todavía.
- Con un id ajeno **y** un motivo inválido, cerrar con diferencia y rechazar dan 400 en vez de 404 (no muestran datos).
- La corrida frecuente de vencimientos no está programada (§5).
