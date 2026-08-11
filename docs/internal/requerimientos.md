# Requerimientos — archivo vivo

**Qué es:** el registro único y permanente de todo lo que se desarrolla en este sistema. Un desarrollo no está terminado hasta que tiene su entrada acá.  
**Alcance:** todos los programas y módulos — Becas/Programas, Dispositivos y Merenderos, Legajos, Portal, Conversaciones y transversales.  
**Inicio del registro:** 7 de agosto de 2026. Nació como registro de los cambios pedidos para DataÑach y se generalizó a todo el sistema; por eso las entradas se titulan «Cambio N».  
**Documentos relacionados:** [analisis-funcional-cambios-datanach-2026-08.md](analisis-funcional-cambios-datanach-2026-08.md) (análisis del pedido original) · [cambios-datanach-pedidos-y-definiciones-pendientes-2026-08.md](cambios-datanach-pedidos-y-definiciones-pendientes-2026-08.md) (definiciones abiertas).

> Este archivo no reemplaza el historial de Git ni los Issues de GitHub: es la versión legible de **qué se pidió, quién lo pidió, qué se decidió y cómo se revierte**. No debe ejecutarse una reversión de base de datos sin respaldo cuando ya existan datos cargados en los campos nuevos.

## Cómo leerlo sin leerlo entero

Este archivo crece con cada requerimiento, así que **nunca se lee completo**. Se consulta por índice y etiquetas, y solo después se abre la entrada que interesa. La herramienta es [`scripts/requerimientos.py`](../../scripts/requerimientos.py), que lee este mismo archivo y no necesita Django ni base de datos:

```powershell
& .\.venv\Scripts\python.exe scripts\requerimientos.py                    # índice compacto: N, título, programa, estado, etiquetas
& .\.venv\Scripts\python.exe scripts\requerimientos.py --tag rbac         # solo los requerimientos de ese tema
& .\.venv\Scripts\python.exe scripts\requerimientos.py --buscar "cupo"    # texto dentro de las entradas, devuelve en qué requerimiento está
& .\.venv\Scripts\python.exe scripts\requerimientos.py --ver 24           # una sola entrada, completa
& .\.venv\Scripts\python.exe scripts\requerimientos.py --check            # el índice y las entradas coinciden
```

El equivalente manual, si no se puede correr el script, es leer la **cabecera y el índice** —las primeras ~150 líneas— y después abrir únicamente el rango de líneas de la entrada buscada (`--ver` imprime ese rango). Lo que no se hace nunca es cargar el archivo entero para encontrar un dato.

### Consulta obligatoria al iniciar un requerimiento

**Antes de escribir código, se consulta este archivo.** No es opcional y es la otra mitad de la regla de oro: se lee al empezar y se escribe al cerrar.

1. Filtrar por la etiqueta y el programa del tema que se va a tocar.
2. Leer las entradas que aparezcan, prestando atención a **Decisiones tomadas**, **Pendientes** e **Historial**.
3. Recién entonces diseñar. Si lo que se va a hacer contradice una decisión registrada, se dice antes de implementar, no después.

El motivo está en este mismo archivo: el Cambio 24 existe porque el 20 se cerró sin ver su efecto completo sobre el alcance, y el Cambio 18 se rehizo entero después de haberse eliminado. Las dos cosas se habrían evitado leyendo primero.

### Etiquetas

Vocabulario **cerrado**: no se inventan etiquetas al escribir una entrada. Si hace falta una nueva, se agrega primero a esta tabla y se explica en una línea. Cada requerimiento lleva entre 2 y 5, y viven en la columna *Etiquetas* del índice, que es su única fuente.

| Etiqueta | Qué agrupa |
|---|---|
| `#rbac` | Roles, capacidades, alcance y quién ve qué |
| `#usuarios` | ABM de usuarios, altas, perfiles y datos personales |
| `#sesion` | Login, duración y unicidad de la sesión |
| `#ui` | Pantallas, textos visibles, navegación y menú |
| `#datos` | Modelo de datos, campos nuevos y limpieza de registros |
| `#relevamientos` | Relevamientos: fechas, estados, operación de campo |
| `#convocatorias` | Convocatorias, segmentos y subsegmentos |
| `#requisitos` | Requisitos y preguntas de los segmentos |
| `#pausas` | Pausas operativas y bloqueos heredados |
| `#cupos` | Cupos y límites de carga |
| `#gps` | Geolocalización y validación territorial |
| `#siis` | Integración con SIIS / catálogo de ECOM |
| `#correo` | Envío de correo y notificaciones por mail |
| `#textos` | Correcciones de texto y codificación |
| `#mobile` | Impacta la APK de territoriales |
| `#api` | Impacta el servidor/API consumido por Mobile |
| `#infra` | Requiere algo del ambiente: cron, SMTP, despliegue, ECOM |

## Regla de oro

**Se lee al iniciar cualquier requerimiento y se escribe al terminarlo.** Las dos mitades son obligatorias: la de lectura está arriba, en *Consulta obligatoria al iniciar un requerimiento*.

**Al terminar cualquier desarrollo, antes de darlo por cerrado, se agrega su entrada a este archivo.** Sin excepciones, y siempre en este mismo documento: no se abren archivos nuevos por mes, por programa ni por pedido.

- **Nada se reescribe.** Si un desarrollo posterior cambia algo ya registrado, la entrada original se conserva y se le suma una sección de historial fechada, que deja visible qué decía antes y por qué cambió. Los Cambios 18 y 20 son los ejemplos a seguir.
- **También se registra lo que se decidió no hacer**, con el motivo (ver Cambios 2 y 9). Un pedido descartado sin registro vuelve a discutirse a los tres meses.
- **Numeración corrida y sin reutilizar:** el requerimiento nuevo toma el número siguiente al último del índice, aunque sea de otro programa.
- **Sub-pedidos:** un pedido que amplía un requerimiento ya cerrado se escribe dentro de su entrada como `## 6.1 Título`, **con su propio semáforo debajo del título**, y va al índice como fila propia. Ese semáforo es lo que lo distingue de una subsección interna numerada —como el `## 15.1` del Cambio 15, que es una parte del mismo pedido y no lleva estado propio—; es la marca que usa `scripts/requerimientos.py` para reconocerlo.
- Toda entrada nueva se suma **también** a la tabla del índice, con sus etiquetas.
- Si falta un dato de contexto —quién lo pidió, cuándo, con qué issue—, se escribe «sin registrar» en vez de omitir el campo. La ausencia tiene que ser visible.

### Cuándo se aplica

- **Es condición de cierre**, al mismo nivel que `manage.py check` y —si el trabajo tocó UI— que `scripts/design_audit.py --changed` y `scripts/compile_templates.py`. Mientras falte la entrada, el desarrollo no está terminado.
- Vale para **todo**: funcionalidades nuevas, ajustes chicos, correcciones de bugs, cambios de permisos, integraciones y decisiones de no implementar.
- **Se consulta al abrir el trabajo y se escribe al cerrarlo.** La consulta es por índice y etiquetas, nunca leyendo el archivo completo: el procedimiento está en *Cómo leerlo sin leerlo entero*. Esto no reemplaza al `code-first` de `CLAUDE.md` —el código sigue siendo la fuente de verdad de qué hace hoy el sistema—; este archivo aporta lo que el código no dice: **qué se decidió y por qué**.
- `CLAUDE.md` solo apunta a este archivo: la definición de la regla, la plantilla y el índice viven **únicamente acá**, para que no existan dos versiones que se contradigan.

### Deuda abierta del registro

Los requerimientos **20 y 22** no tienen **solicitante ni fecha de pedido** registrados en su origen. Figuran como «sin registrar» en el índice; se completan cuando se confirme quién los pidió. Ese hueco es lo que esta regla viene a cerrar: de acá en adelante ningún requerimiento se cierra sin esos dos datos.

El 21 y el 23 se pidieron en sesión de trabajo y ya tienen su origen asentado; el 24 se detectó internamente.

## Plantilla obligatoria de cada entrada

```markdown
# Cambio N — Título en las palabras del pedido

🟢 **HECHO — DD/MM/AAAA**   (o 🟡 PARCIAL · 🔴 PENDIENTE · ⚪ NO SE IMPLEMENTA)

| | |
|---|---|
| **Programa / módulo** | Becas · Dispositivos · Legajos · Portal · Conversaciones · Transversal |
| **Etiquetas** | 2 a 5 del vocabulario cerrado, iguales a las de su fila del índice |
| **Solicitante** | Quién lo pidió y por qué vía: reunión, documento, mail, issue |
| **Fecha del pedido** | DD/MM/AAAA |
| **Issue / épica** | #NN, o «sin issue» |
| **Partes afectadas** | Backoffice · Mobile · Servidor/API · Infra/ECOM |
| **Migración** | `app.NNNN`, o «No requiere» |

## Pedido original
Textual, o lo más cerca posible de las palabras del solicitante.

## Alcance acordado
Qué entra y qué queda explícitamente afuera.

## Decisiones tomadas
Cada definición funcional o técnica con su motivo. Es la sección que más se
consulta después: acá va el «por qué» que no se deduce leyendo el código.

## Implementación
Qué hace el sistema ahora, en lenguaje funcional.

## Archivos

## Base de datos
Migración, columnas nuevas y si es segura sobre datos existentes.

## Validación
Pruebas automáticas y manuales con su resultado, `manage.py check` y —si tocó
UI— `scripts/design_audit.py --changed` y `scripts/compile_templates.py`.

## Puesta en marcha en el servidor
Solo si necesita algo más que el deploy: cron, variables, comando manual.

## Pendientes / a definir
Lo que quedó abierto, para que no se pierda.

## Reversión
Pasos en orden y qué datos se pierden al revertir.

## Historial
Solo si la entrada cambió después de haberse cerrado: qué decía antes, qué la
cambió y cuándo.
```

Los campos que no apliquen se escriben como «No requiere» o «No aplica»; no se borran.

## Índice

| N.º | Requerimiento | Programa / módulo | Etiquetas | Solicitante | Pedido | Estado | Migración |
|---|---|---|---|---|---|---|---|
| 1 | Recordarme | Transversal / sesión | `#sesion` `#usuarios` | Cliente — DOCX «Cambios en DataÑach» | 07/08/2026 | 🟢 **Hecho** | No |
| 2 | Limpieza de datos de prueba | Transversal / datos | `#datos` `#infra` | Cliente — DOCX | 07/08/2026 | ⚪ **No por código — limpieza en base de test** | No desarrollada |
| 3 | Becas → Programas en menú | Becas | `#ui` | Cliente — DOCX | 07/08/2026 | 🟢 **Hecho** | No |
| 4 | Revisar tipos de usuarios | Becas / permisos | `#rbac` `#usuarios` | Cliente — DOCX | 07/08/2026 | 🟢 **Hecho** | `programas.0038`, `programas.0041`, `programas.0044`, `users.0015`, `users.0016` y `users.0018` |
| 5 | Datos adicionales de usuario | Transversal / usuarios | `#usuarios` `#datos` `#api` | Cliente — DOCX | 07/08/2026 | 🟢 **Hecho** | `users.0012` |
| 6 | Usuarios y Roles dentro de Programas | Becas | `#usuarios` `#ui` `#rbac` | Cliente — DOCX | 07/08/2026 | 🟢 **Hecho mediante alta contextual** | No |
| 6.1 | Alta rápida del Referente del subsegmento | Becas / subsegmentos | `#usuarios` `#rbac` `#ui` `#convocatorias` | PM — pedido directo en sesión de trabajo | 11/08/2026 | 🟢 **Hecho** | No |
| 7 | Quitar categoría Becas | Becas / roles | `#rbac` `#ui` | Cliente — DOCX | 07/08/2026 | 🟢 **Hecho** | No |
| 8 | Incorporar programas | Becas / SIIS | `#siis` `#infra` | Cliente — DOCX | 07/08/2026 | 🟡 **Pertenece a ECOM** | No desarrollada |
| 9 | Localidades como subsegmentos | Becas | `#convocatorias` `#datos` | Cliente — DOCX | 07/08/2026 | ⚪ **Se resolvió con el título de la convocatoria** | No desarrollada |
| 10 | Fecha desde/hasta del relevamiento | Becas · Mobile / API | `#relevamientos` `#mobile` `#api` | Cliente — DOCX | 07/08/2026 | 🟢 **Hecho** | `programas.0036` |
| 11 | Domicilio actual del ciudadano | Legajos | `#ui` `#datos` | Cliente — DOCX | 07/08/2026 | 🟢 **Hecho** | No |
| 12 | Desplegable de búsqueda de legajos | Legajos / Inicio | `#ui` | Cliente — DOCX | 07/08/2026 | 🟢 **Hecho** | No |
| 13 | Correo al crear usuario | Transversal / correo | `#correo` `#usuarios` `#infra` | Cliente — DOCX | 07/08/2026 | 🟡 **Implementado — pendiente SMTP ECOM** | No |
| 14 | Sesión web única por usuario | Transversal / sesión | `#sesion` | Cliente — DOCX | 07/08/2026 | 🟢 **Hecho** | `users.0013` |
| 15 | Administrador de programa y pausas | Becas · Mobile / API | `#rbac` `#pausas` `#mobile` `#api` | Cliente — DOCX | 07/08/2026 | 🟢 **Hecho** | `programas.0037` |
| 16 | Coordinador del segmento | Becas / permisos | `#rbac` `#usuarios` | Cliente — DOCX | 07/08/2026 | 🟢 **Hecho** | `users.0014` |
| 17 | Referente | Becas / permisos | `#rbac` `#usuarios` | Cliente — DOCX | 07/08/2026 | 🟢 **Hecho** | `programas.0038` + `users.0015` |
| 18 | Coordinador regional | Becas / permisos | `#rbac` `#convocatorias` `#relevamientos` `#usuarios` | Cliente — DOCX | 07/08/2026 | 🟢 **Rehecho con alcance de subsegmento** | `programas.0044` + `users.0018` |
| 19 | Territorial | Becas · Mobile / API | `#rbac` `#mobile` `#cupos` `#gps` `#api` | Cliente — DOCX | 07/08/2026 | 🟡 **Parcial — GPS pendiente** | `programas.0040` |
| 20 | Separar la administración de Usuarios y de Roles por programa | Transversal / permisos | `#rbac` `#usuarios` | Pedido posterior — origen sin registrar | sin registrar | 🟢 **Hecho** | `users.0019` |
| 21 | Textos con caracteres rotos | Transversal / textos | `#textos` `#ui` | PM — pedido directo en sesión de trabajo | 11/08/2026 | 🟢 **Hecho** | No |
| 22 | Vigencia del programa SIIS en los segmentos | Becas / integración | `#siis` `#pausas` `#convocatorias` `#infra` | Pedido posterior — origen sin registrar | sin registrar | 🟢 **Hecho** | `programas.0043` |
| 23 | Orden de los requisitos: autonumerado y sin repetidos | Becas / requisitos | `#requisitos` `#ui` | PM — pedido directo en sesión de trabajo | 11/08/2026 | 🟢 **Hecho** | No |
| 24 | Alcance sobre Usuarios y Roles solo por capacidades transversales | Transversal / permisos | `#rbac` `#usuarios` `#ui` | PM — lo detectó revisando el rol Becas — Administrador | 11/08/2026 | 🟢 **Hecho** | `users.0020` |
| 25 | Zona del relevamiento elegida del catálogo de localidades | Becas / relevamientos | `#relevamientos` `#ui` `#datos` | PM — pedido directo en sesión de trabajo | 11/08/2026 | 🟢 **Hecho** | No |
| 26 | Subsegmento obligatorio para el Coordinador Regional | Becas / convocatorias | `#convocatorias` `#rbac` `#ui` | PM — surgió del análisis general de Becas del 11/08 | 11/08/2026 | 🟡 **Hecho — pendiente de despliegue** | No |

**Notas del índice**

- Los requerimientos 1 a 19 son la normalización del documento «Cambios en DataÑach (1).docx», enviado por el cliente el 7 de agosto de 2026, en su orden de aparición. Los puntos 7 y 8 separan dos pedidos que el DOCX trae en un mismo párrafo.
- Del 20 en adelante son pedidos posteriores a ese documento. Los requerimientos 20 y 22 **no tienen solicitante ni fecha de pedido registrados en su origen**; quedan como «sin registrar» hasta confirmarlos. Ese hueco es exactamente lo que la regla de oro viene a cerrar.
- El requerimiento 22 se apoya en el 8 (Incorporar programas), que es la integración con el catálogo de ECOM. El 24 completa y corrige el criterio del 20.
- Las entradas 1 a 24 son anteriores a la plantilla: su programa, solicitante, fecha y etiquetas viven en esta tabla y no repetidos en cada entrada. **Las nuevas llevan la plantilla completa**, con las mismas etiquetas en la entrada y en el índice.
- Las etiquetas se asignaron leyendo cada entrada, no por su título. `scripts/requerimientos.py --check` verifica que ninguna quede fuera del vocabulario y que no falte ni sobre ninguna fila.

---

# Cambio 1 — Hacer funcionar “Recordarme”

## Implementación

- Se agregó `remember` al formulario de autenticación.
- Con “Recordarme” marcado, la sesión utiliza `SESSION_COOKIE_AGE`, actualmente 24 horas.
- Sin marcarlo, la sesión vence al cerrar el navegador.
- Si un usuario autenticado entra nuevamente al login o a `/`, se lo redirige a Inicio.
- Se conserva el cierre por inactividad configurado en el sistema.

## Archivos

- `users/forms/auth.py`
- `users/views/auth.py`
- `users/templates/user/login.html`
- `users/tests/test_usuarios_abm.py`

## Validación

```powershell
docker compose run --rm --no-deps app python manage.py test `
  users.tests.test_usuarios_abm.LoginRouteTests `
  users.tests.test_usuarios_abm.LoginUsuarioInactivoTests --keepdb
```

**Resultado:** 8 pruebas aprobadas.

También se verificó manualmente con Edge:

- La cookie persistente muestra vencimiento a 24 horas.
- Al cerrar y reabrir Edge, la sesión continúa activa.
- `http://localhost:8000` redirige al usuario autenticado hacia Inicio.

## Reversión

No requiere cambios de base de datos.

Para volver al comportamiento anterior se deben retirar conjuntamente:

1. El campo `remember` de `UsuariosAuthenticationForm`.
2. El método `form_valid()` y `redirect_authenticated_user` de `UsuariosLoginView`.
3. La vinculación del checkbox con `form.remember` en el template.
4. Las pruebas agregadas para este comportamiento.

---

# Cambio 2 — Limpieza de datos de prueba

## Decisión

No se implementó una eliminación desde código. Quedó marcado como **“Para limpieza en base de test”**.

## Responsabilidad

- El cliente debe identificar los registros de prueba.
- Infraestructura o el responsable autorizado debe respaldar y limpiar la base de test.
- No debe ejecutarse en producción usando como criterio únicamente nombres o datos inferidos.

## Reversión

No aplica todavía porque no se modificaron ni eliminaron datos.

---

# Cambio 3 — Renombrar Becas como Programas en el menú lateral

## Alcance acordado

El pedido se acotó a la etiqueta visible del menú izquierdo.

## Implementación

- `Becas` se muestra como `Programas` en el menú expandido.
- El título y texto accesible del menú colapsado también muestran `Programas`.
- No se cambiaron rutas `/becas/`, permisos `becas.*`, nombres de modelos, API ni APK.

## Archivos

- `templates/includes/sidebar/opciones.html`
- `users/tests/test_menu_rbac.py`

## Validación

```powershell
docker compose run --rm --no-deps app python manage.py test `
  users.tests.test_menu_rbac.MenuRestringidoTests --keepdb
```

**Resultado:** 4 pruebas aprobadas.

## Reversión

No requiere cambios de base de datos. Reemplazar solamente las tres etiquetas visibles `Programas` por `Becas` en el bloque del módulo del sidebar y retirar la prueba específica del nombre.

---

# Cambio 4 — Revisar tipos de usuarios

🟢 **HECHO**

## Decisión funcional

- **Coordinador general del programa** y **Administrador del programa** son dos nombres para el mismo perfil.
- Se conserva el rol técnico existente `Becas — Administrador`; no se crea un rol duplicado.
- **Coordinador del segmento** continúa siendo un perfil distinto, con alcance limitado a sus segmentos.
- **Territorial** continúa siendo el perfil exclusivo de Mobile.
- **Referente** depende de un Coordinador del segmento y administra Territoriales dentro del alcance heredado.
- El perfil **Coordinador regional** fue retirado por decisión funcional y luego repuesto con otro anclaje: ya no depende de una Región (que no existe más) sino del **subsegmento** que tiene a cargo. Ver Cambio 18.

## Impacto técnico

La matriz vigente queda formada por Administrador, Coordinador del segmento, Coordinador regional, Referente y Territorial. No se duplicó el rol Administrador.

## Validación

La matriz se verificó junto con las pruebas del Cambio 17 y las de la reposición del Cambio 18.

## Reversión

La reversión funcional del Referente se encuentra detallada en el Cambio 17. Si se decidiera separar Coordinador general y Administrador, primero deberá definirse una matriz nueva para evitar permisos contradictorios.

---

# Cambio 5 — Agregar datos al usuario

## Implementación

Se agregaron al perfil del usuario:

- DNI.
- Teléfono.
- Institución.
- Observación.

Los cuatro campos:

- Aparecen en alta y edición.
- Son opcionales por decisión actual.
- Se exponen en el serializer del perfil.

Reglas del DNI:

- Entre 6 y 8 números.
- No puede repetirse entre usuarios.
- Se almacena como `NULL` cuando no se informa, permitiendo múltiples usuarios sin DNI.

También se agregaron asteriscos visuales a los campos actualmente obligatorios:

- Nombre de usuario.
- Contraseña durante el alta.
- Segmento asignado cuando el usuario posee rol Territorial; este último ya estaba indicado.

## Archivos

- `users/models/__init__.py`
- `users/forms/__init__.py`
- `users/services/admin.py`
- `users/serializers/__init__.py`
- `users/templates/user/user_form.html`
- `users/tests/test_user_admin_services.py`
- `users/migrations/0012_profile_datos_personales.py`

## Base de datos

Migración agregada y aplicada localmente:

```text
users.0012_profile_datos_personales
```

Columnas nuevas en `users_profile`:

| Columna | Tipo funcional | Nulos/vacíos | Restricción |
|---|---|---|---|
| `dni` | Texto, máximo 8 | Sí | Único cuando está informado |
| `telefono` | Texto, máximo 30 | Vacío permitido | — |
| `institucion` | Texto, máximo 255 | Vacío permitido | — |
| `observacion` | Texto largo | Vacío permitido | — |

## Validación

```powershell
docker compose run --rm --no-deps app python manage.py makemigrations --check --dry-run
docker compose run --rm --no-deps app python manage.py test `
  users.tests.test_user_admin_services.UsuariosAdminServiceTests --keepdb
docker compose exec app python manage.py check
```

**Resultados:**

- No se detectaron migraciones faltantes.
- 4 pruebas específicas de alta, edición y DNI aprobadas.
- `manage.py check` sin errores propios del cambio.

**Observación de pruebas preexistente:** La clase completa de asignación territorial presenta contaminación del caché del Programa Becas entre casos y la suite amplia de roles intenta duplicar el Programa `DISPOSITIVOS` en la base reutilizada. Los casos específicos de este cambio aprobaron; esos problemas no fueron corregidos dentro de este alcance.

## Reversión

### Antes de tener datos reales

Se puede retroceder la migración:

```powershell
docker compose exec app python manage.py migrate users 0011_dispositivos_alcance_rbac
```

Después deben revertirse conjuntamente modelo, formulario, servicio, serializer, template y pruebas.

### Después de tener datos reales

No ejecutar el rollback directamente: eliminar la migración borra DNI, teléfono, institución y observación de todos los usuarios.

Procedimiento seguro:

1. Exportar las cuatro columnas asociadas a cada usuario.
2. Verificar el respaldo.
3. Recién entonces retroceder la migración.
4. Revertir el código relacionado.

---

# Cambio 6 — Usuarios y Roles dentro de Programas

🟢 **HECHO**

## Implementación

- Se agregó un botón de alta rápida junto a los selectores de usuario de las pantallas de Programas que lo requieren.
- El botón abre un modal con los campos necesarios para crear el usuario sin abandonar el flujo actual.
- Al finalizar, el usuario nuevo queda seleccionado o disponible para su asignación inmediata.
- El modal y las opciones de rol respetan las capacidades y el alcance del operador: no se permite crear roles ni usuarios superiores mediante una petición manual.
- Se conservaron los ABM generales existentes para evitar duplicar datos y lógica.

## Archivos principales

- `users/templates/user/_alta_rapida_modal.html`
- `users/views/quick_create.py`
- `users/services/invitations.py`
- `users/forms/__init__.py`
- `users/services/admin.py`
- `users/urls.py`
- Templates y formularios de Segmentos, Subsegmentos y Relevamientos que incorporan el selector contextual.

## Reversión

Retirar los botones y la inclusión del modal en las pantallas de Programas, eliminar la ruta de alta rápida y volver a exigir que los usuarios se creen previamente desde el ABM general. No requiere borrar usuarios ya creados: continúan siendo usuarios normales del sistema.

## 6.1 Alta rápida del Referente del subsegmento

🟢 **HECHO — 11/08/2026**

| | |
|---|---|
| **Programa / módulo** | Becas — configuración de subsegmentos |
| **Etiquetas** | `#usuarios` `#rbac` `#ui` `#convocatorias` |
| **Solicitante** | PM, pedido directo en sesión de trabajo |
| **Fecha del pedido** | 11/08/2026 |
| **Issue / épica** | Sin issue |
| **Partes afectadas** | Backoffice |
| **Migración** | No requiere |

### Pedido original

«en el pop up Nuevo subsegmento https://relevamiento-deshum.ecomdev.ar/becas/config/segmentos/1/ abajo del Referente asignado, crea un boton como el Crear coordinador pero que sea uno para creal el Referente»

### Alcance acordado

- Entra el botón en el modal **Nuevo subsegmento**, debajo del selector *Referente asignado*, con el mismo aspecto y comportamiento que el de **Crear coordinador** que ya existe en la misma pantalla.
- Queda afuera el modal **Editar subsegmento**: tiene su propio selector de referente y el atajo requeriría tocarlo (ver *Pendientes*).
- Queda afuera cambiar **quién puede ser referente**: el universo elegible sigue siendo el definido en el Cambio 18.

### Decisiones tomadas

- **El botón da de alta un Coordinador Regional, no un rol nuevo llamado «Referente».** Motivo: *Referente asignado* es la etiqueta que la pantalla del subsegmento le pone al Coordinador Regional a cargo (Cambio 18). El rol `Becas — Referente` es otro perfil, el del Cambio 17, que depende de un Coordinador del segmento. Crear ese otro rol habría dado un usuario con permisos equivocados y que además no aparecería en el selector.
- **Se reutilizó el modal de alta rápida existente en lugar de hacer uno propio.** Motivo: el mecanismo del Cambio 6 ya resuelve crear-y-dejar-seleccionado; un modal nuevo habría duplicado los campos, la validación y la verificación de permisos.
- **El tipo se llama `referente` en la interfaz y se traduce al rol Coordinador Regional en el servidor.** Motivo: el operador lee «Referente» en la pantalla y el nombre técnico del rol no debe filtrarse a la UI. La traducción está en un solo lugar y comentada, porque los dos nombres coexisten y se confunden con facilidad.
- **Los dos tipos de alta de backoffice quedaron unificados en una tabla.** Motivo: coordinador y referente comparten exactamente la misma guarda y el mismo camino sin segmento. Tenerlos como ramas separadas invitaba a que una se actualizara sin la otra.
- **La capacidad se verifica dos veces: una para mostrar el botón y otra en el servidor.** Motivo: ocultar un botón no es un control de acceso y el endpoint es alcanzable a mano. Un Coordinador que lo invoque recibe 403.
- **El referente nuevo no recibe segmento ni subsegmento durante el alta.** Motivo: el vínculo lo establece el guardado del subsegmento. Asignarlo también en el alta habría creado un segundo camino para la misma relación, con el riesgo de que quedaran discrepantes.

### Implementación

- El modal Nuevo subsegmento muestra el botón **Crear referente** debajo del selector *Referente asignado*.
- Abre el mismo modal de alta rápida que usa **Crear coordinador**. Al confirmar, el usuario creado se incorpora al selector y queda elegido; el subsegmento se guarda con ese referente.
- El usuario nuevo queda con el rol **Becas — Coordinador Regional**, el único perfil que el sistema admite como referente de un subsegmento.
- El botón solo lo ve quien administra el programa. Para el resto, la pantalla queda exactamente como estaba.

### Archivos

- `programas/templates/programas/becas/config/segmento_detail.html`
- `users/views/quick_create.py`
- `users/tests/test_coordinador_usuarios.py`

### Base de datos

**No requiere migración.** No se agregaron campos: el vínculo subsegmento → referente ya existe desde `programas.0044` (Cambio 18).

### Validación

- Dos pruebas nuevas: el Administrador crea el referente desde el modal —queda con el rol Coordinador Regional, aparece entre los referentes elegibles y vuelve en la respuesta sin segmento— y un Coordinador que invoca el mismo alta recibe 403 sin que el usuario se cree.
- `manage.py check` sin observaciones. `scripts/design_audit.py --changed`: 0 errores. `scripts/compile_templates.py`: 301 plantillas, 0 errores.
- Las dos pruebas de vista que ya fallaban en `users.tests.test_coordinador_usuarios` siguen fallando por la incompatibilidad de entorno descrita en el Cambio 24, no por este cambio: revientan al copiar el contexto de la plantilla, en un flujo que este requerimiento no toca.

### Puesta en marcha en el servidor

No requiere nada además del deploy. **Todavía no desplegado.**

### Pendientes / a definir

- El modal **Editar subsegmento** no tiene el atajo. Su selector de referente está escrito a mano con Alpine y sin identificador propio, así que engancharlo pide darle un `id`. Es un cambio chico si se decide unificarlo.
- Pendiente la prueba manual en el ambiente de test: crear un referente desde el modal y confirmar que queda seleccionado y se guarda junto con el subsegmento.

### Reversión

Quitar el botón del modal Nuevo subsegmento y el tipo `referente` del alta rápida. No hay migración que deshacer ni datos que se pierdan: los usuarios ya creados continúan siendo Coordinadores Regionales y se administran desde el ABM de Usuarios.

### Historial

No aplica: entrada nueva.

---

# Cambio 7 — Quitar Becas como categoría seleccionable de rol

## Implementación

- Se eliminó `Becas` de las opciones del campo Categoría en alta y edición de roles.
- Para administradores de programa, la única categoría disponible es `Programa` y queda seleccionada por defecto.
- Se mantuvo `CATEGORIA_BECAS` como valor técnico legacy para poder identificar y consultar registros antiguos si aparecieran en otra base.
- No se alteraron capacidades `becas.*`, programa Becas, usuarios, API ni APK.

Estado local revisado antes del cambio:

- 3 roles con categoría `Programa`.
- 0 roles con categoría `Becas`.

## Archivos

- `users/forms/roles.py`
- `users/tests/test_roles_abm.py`

## Validación

```powershell
docker compose run --rm --no-deps app python manage.py test `
  users.tests.test_roles_abm.RolCategoriaFormTests.test_categoria_programa_en_selector_global `
  users.tests.test_roles_abm.RolAlcanceTests.test_form_admin_programa_incluye_categoria_programa `
  users.tests.test_roles_abm.RolAlcanceTests.test_form_admin_programa_guarda_en_su_programa `
  --keepdb
```

**Resultado:** 3 pruebas específicas aprobadas.

## Reversión

No requiere migración de base de datos.

Para volver a mostrar `Becas`:

1. Retirar el filtro que excluye `CATEGORIA_BECAS` en `RolForm.__init__()`.
2. Volver a incluir `Becas` en las opciones restringidas del administrador de programa.
3. Restaurar el valor inicial anterior si se desea.
4. Ajustar las pruebas del selector.

---

# Cambio 8 — Incorporar programas al catálogo de SIIS

🟡 **NO SE DESARROLLA DE ESTE LADO — DEPENDE DE ECOM**

> Entrada escrita el 11/08/2026 para cerrar un hueco del registro: el requerimiento figuraba en el índice desde el principio, pero nunca tuvo entrada propia.

## Pedido original

Incorporar **MAMÁ ÑACHEC, FUTURO JÓVEN, SEGMENTO FE y MI CASA ÑACHEC** al selector de Programa SIIS del alta de segmentos. El DOCX agrega la aclaración «Ya se le escribió el email a ECOM».

## Decisiones tomadas

- **No hay desarrollo posible en el Backoffice.** El selector no tiene una lista propia: consume el catálogo que publica SIIS. Un programa que no está en ese catálogo no se puede ofrecer sin inventar datos que después no validarían contra el servicio.
- Por eso el pedido quedó como **gestión con ECOM**, no como tarea de software. La vía es el correo que el cliente ya envió.
- Se descartó cargar los cuatro programas a mano como paso provisorio: habrían quedado sin `siis_programa_id` real y las prevalidaciones de ciudadanos los habrían rechazado, con un error difícil de interpretar para el operador.

## Estado

Al 11/08/2026 el catálogo real de SIIS tiene vinculados dos programas —`#34 Chaco Joven` y `#15 Chaco Olímpico ley 7353`— y ninguno de los cuatro pedidos. Verificado contra producción durante el Cambio 22.

## Relación con otros requerimientos

El Cambio 22 (vigencia del programa SIIS) se apoya en esta integración: cuando los cuatro programas entren al catálogo, quedan automáticamente cubiertos por la detección de bajas y el bloqueo del segmento, sin trabajo adicional.

## Archivos

No aplica: no hubo cambios de código.

## Base de datos

No requiere migración.

## Pendientes

Que ECOM incorpore los cuatro programas al catálogo de SIIS. Cuando eso ocurra, el único trabajo de este lado es vincular cada segmento a su programa desde el alta; el resto ya funciona.

## Reversión

No aplica.

---

# Cambio 9 — Localidades en lugar de subsegmentos

⚪ **NO SE IMPLEMENTA EL CAMBIO ESTRUCTURAL — RESUELTO POR OTRA VÍA**

> Entrada escrita el 11/08/2026 para cerrar un hueco del registro: el requerimiento figuraba en el índice desde el principio, pero nunca tuvo entrada propia.

## Pedido original

Permitir trabajar con las localidades de Chaco en lugar de los subsegmentos actuales. La captura del DOCX corresponde a la pantalla «Nuevo subsegmento», donde hoy se elige un Segmento SIIS y no una localidad.

## Decisiones tomadas

- **Se descartó reemplazar el subsegmento por una localidad.** El subsegmento es la unidad que atraviesa todo el modelo: de él dependen convocatorias, relevamientos, cupos y —desde el Cambio 18— el alcance del Coordinador Regional. Cambiar su naturaleza obligaba a rediseñar esas cuatro cosas a la vez.
- **Decisión provisoria vigente:** la localidad se identifica **en el título de la convocatoria**. Resuelve la necesidad operativa —saber de qué localidad es cada convocatoria— sin tocar el modelo.
- Es una decisión de forma, no de fondo: no habilita filtrar, agrupar ni cupear por localidad, porque el dato no es estructurado.

## Si se retoma el cambio estructural

Antes de implementarlo hay que definir:

1. La **fuente oficial** del catálogo de localidades de Chaco, y quién la mantiene.
2. La **relación** entre localidad, segmento y programa: si una localidad puede pertenecer a más de un segmento, y qué pasa con los subsegmentos ya creados.
3. Si los **cupos** pasan a ser por localidad, y cómo se migran los cupos por relevamiento que hoy existen.
4. Qué ocurre con el **alcance del Coordinador Regional**, que hoy se ancla al subsegmento (Cambio 18). Es la dependencia que este pedido no tenía cuando se escribió.

## Archivos

No aplica: no hubo cambios de código.

## Base de datos

No requiere migración. Es justamente el motivo por el que se eligió esta salida.

## Reversión

No aplica. Si se quiere dejar de usar la localidad en el título, se editan los títulos de las convocatorias.

## Nota del 11/08/2026 — parte de la pregunta 1 quedó respondida

El **Cambio 25** empezó a usar el catálogo de `/configuracion/localidades/` como fuente de la zona de un relevamiento. Eso contesta la pregunta de cuál es el catálogo disponible —es el nacional que comparte el domicilio de los ciudadanos, con 778 localidades de Chaco— pero **no** cambia la decisión de esta entrada: el subsegmento sigue siendo la unidad estructural y la localidad se sigue anotando en el título de la convocatoria. Lo que falta definir sigue siendo quién mantiene ese catálogo y los tres puntos que siguen.

---

# Cambio 10 — Fecha desde/hasta del relevamiento

## Implementación

- Se agregó `fecha_hasta` y la fecha técnica existente pasó a mostrarse como **Fecha desde**.
- Los relevamientos existentes se conservan como operativos de un solo día: la migración copia su fecha anterior en `fecha_hasta`.
- Backoffice permite crear y reprogramar un relevamiento con ambas fechas, muestra el período y detecta asignaciones superpuestas.
- Las dos fechas deben estar dentro del inicio y fin de la convocatoria; Fecha hasta no puede ser anterior a Fecha desde.
- La API entrega ambas fechas y permite iniciar, cargar, sincronizar, finalizar o reabrir solamente dentro del período.
- Mobile muestra la vigencia completa, incluye el relevamiento en cada día de su período y habilita la operación durante cualquiera de esos días.
- Un relevamiento finalizado anticipadamente permanece cerrado aunque todavía esté dentro de su vigencia.

## Archivos principales

- `programas/models/__init__.py`
- `programas/forms.py`
- `programas/views/relevamientos.py`
- `programas/api/serializers.py`
- `programas/api/views.py`
- `programas/templates/programas/becas/relevamientos/`
- `programas/migrations/0036_relevamiento_fecha_hasta.py`
- `mobile/src/services/relevamientoService.js`
- `mobile/src/screens/HomeScreen.js`
- `mobile/src/screens/RelevamientosScreen.js`
- `mobile/src/screens/RelevamientoDetailScreen.js`

## Validación

- Migración aplicada correctamente en el entorno local.
- `manage.py check`: sin errores.
- `makemigrations --check --dry-run`: sin migraciones faltantes.
- 65 pruebas de modelos y API de relevamientos aprobadas.
- Exportación Android de Expo completada correctamente.

La suite amplia del Backoffice conserva fallas preexistentes relacionadas con permisos y datos reutilizados. Además, algunos casos antiguos todavía envían únicamente `fecha_asignada`; deben actualizarse para incluir `fecha_hasta`. Esto no afectó las pruebas del modelo/API ni la compilación Mobile.

## Reversión

La migración puede retrocederse a `programas.0035_numeracion_contextual_becas`. Antes de hacerlo en un ambiente con datos reales se debe exportar `fecha_hasta`, porque el rollback elimina esa columna y pierde los períodos de varios días.

# Cambio 11 — Domicilio actual del ciudadano

## Alcance acordado

Se reutiliza el domicilio existente del ciudadano y se cambia únicamente su denominación visible en Backoffice. No se crea un segundo domicilio ni un historial.

## Implementación

- Alta manual: el campo se muestra como **Domicilio actual**.
- Confirmación de datos provenientes de RENAPER: se muestra como **Domicilio actual**.
- Edición: se muestra como **Domicilio actual**.
- Detalle del ciudadano: se muestra como **Domicilio actual**.
- El campo conserva su carácter opcional.

## Archivos

- `legajos/forms/ciudadanos.py`
- `legajos/templates/legajos/ciudadano_confirmar_form.html`
- `legajos/templates/legajos/ciudadano_detail.html`
- `legajos/tests/test_ciudadanos_admision.py`

## Validación

- Prueba específica de formularios aprobada.
- `manage.py check` sin errores.
- No requiere migración ni modifica datos existentes.

## Reversión

Restaurar la etiqueta visible **Domicilio** en el formulario y en los templates indicados. No hay cambios de base de datos que revertir.

# Cambio 12 — Desplegable de búsqueda de legajos

## Problema

La API devolvía resultados, pero el desplegable del buscador de Inicio estaba dentro de una tarjeta con `overflow: hidden`. Al abrirse hacia abajo podía quedar recortado según navegador, resolución o nivel de zoom.

## Implementación

- La tarjeta del buscador permite que el desplegable sobresalga.
- Se agregó un nivel visual superior para que los resultados aparezcan por encima de “Mi trabajo de hoy”.
- No se modificó la búsqueda ni la API.
- El desplegable muestra hasta 20 coincidencias; si existen más, informa que se deben escribir más caracteres para precisar la búsqueda.

## Archivos

- `templates/inicio.html`

## Validación

- `manage.py check` sin errores.
- La API encontró correctamente el ciudadano local `Ejemplo Mac, María`, DNI `31538703`.
- El registro de ejemplo se creó sólo en la base local de desarrollo.

## Reversión

Retirar la clase `search-card` y restaurar el nivel visual anterior de `.search-results`. No requiere migración.

# Cambio 13 — Correo al crear un usuario

## Implementación

- Al finalizar el alta se envía una invitación al correo informado.
- El mensaje incluye el nombre de usuario y un enlace temporal para establecer una contraseña.
- No se envían contraseñas en texto plano.
- El enlace deja de ser válido al utilizarlo y cambiar la contraseña.
- Si falta el correo o falla el envío, el usuario permanece creado y el administrador recibe una advertencia.
- En desarrollo se utiliza el backend de consola; test y producción requieren SMTP de ECOM.

## Archivos

- `users/services/invitations.py`
- `users/views/admin.py`
- `users/urls.py`
- `users/templates/user/establecer_contrasena.html`
- `users/tests/test_invitaciones.py`
- `config/settings.py`

## Configuración requerida a ECOM

Para que el correo funcione fuera del entorno local necesitamos que Infra/ECOM:

1. Proporcione y configure un servidor de correo saliente (SMTP) para DataÑach.
2. Informe el servidor, puerto, usuario y contraseña.
3. Confirme si la conexión utiliza TLS.
4. Defina la dirección remitente visible, por ejemplo `no-responder@chaco.gob.ar`.
5. Autorice al servidor de DataÑach a conectarse y enviar desde esa dirección.
6. Configure estos valores tanto en test como en producción:

| Variable | Qué debe contener |
|---|---|
| `EMAIL_HOST` | Dirección del servidor de correo |
| `EMAIL_PORT` | Puerto de conexión, normalmente 587 |
| `EMAIL_HOST_USER` | Usuario autorizado para enviar |
| `EMAIL_HOST_PASSWORD` | Contraseña o credencial del servicio |
| `EMAIL_USE_TLS` | `True` si utiliza conexión segura TLS |
| `DEFAULT_FROM_EMAIL` | Nombre y correo remitente visible |

### Prueba que debe realizar Infra

1. Crear un usuario de prueba con una casilla a la que tengan acceso.
2. Confirmar que llega el correo “Tu usuario de DATAÑACH fue creado”.
3. Abrir el enlace recibido y establecer una contraseña.
4. Iniciar sesión con esa nueva contraseña.
5. Revisar los registros del servidor si el Backoffice informa que no pudo enviar el mensaje.

> El desarrollo ya está preparado. Sin esta configuración SMTP el usuario se crea, pero el correo no puede salir del servidor.

## Validación

- 2 pruebas aprobadas: contenido seguro del correo y establecimiento de contraseña mediante el enlace.
- `manage.py check` sin errores.
- No se detectaron migraciones pendientes.

## Reversión

Retirar el envío desde `UserCreateView`, la ruta y template para establecer contraseña, el servicio de invitaciones y la configuración SMTP agregada. No requiere rollback de base de datos.

# Cambio 14 — Impedir sesiones simultáneas del mismo usuario

## Alcance acordado

- Se aplica únicamente al Backoffice web.
- Mobile queda fuera de alcance: no se modifican ni invalidan sus tokens y no se afectan relevamientos pendientes de sincronización.
- Ante un segundo ingreso, la sesión web más nueva reemplaza a la anterior.

## Implementación

- Se registra en el perfil la clave de la sesión web vigente.
- Cada nuevo login establece su sesión como la única válida.
- En la siguiente navegación de una sesión reemplazada, se cierra esa sesión, se redirige al login y se muestra el aviso correspondiente.
- Una sesión creada antes del despliegue se conserva y registra automáticamente si todavía no existe otra sesión vigente.
- La comparación se realiza contra la base de datos para funcionar aunque producción utilice caché de sesiones o varios procesos.

## Archivos

- `users/models/__init__.py`
- `users/views/auth.py`
- `users/middleware.py`
- `users/migrations/0013_profile_backoffice_session_key.py`
- `users/templates/user/login.html`
- `users/tests/test_usuarios_abm.py`
- `config/settings.py`

## Validación

- 5 pruebas de login aprobadas, incluida la simulación de dos navegadores con el mismo usuario.
- Se comprobó que la primera sesión es cerrada y que la segunda continúa activa.
- `manage.py check` sin errores.
- `makemigrations --check --dry-run` no detectó cambios pendientes.

## Reversión

Retirar el middleware, el registro de la sesión en `UsuariosLoginView`, la prueba asociada y revertir la migración `users.0013` de forma controlada. Mobile no requiere reversión porque no fue modificado.

# Cambio 15 — Rol Administrador del programa

## 15.1 Usuarios y roles

- Se verificó que el alcance existente limita al administrador a los usuarios y roles de sus programas.
- No puede administrar roles globales ni pertenecientes a otro programa.
- La incorporación efectiva de los cuatro programas continúa dependiendo de la carga de ECOM indicada en el Cambio 8.

## 15.2 Pausas operativas

Se tomó como asunción funcional **Sector = Convocatoria**. El Administrador del programa puede pausar y reanudar:

- Convocatorias.
- Segmentos.
- Subsegmentos.
- Relevamientos.

Cada movimiento exige un motivo y registra permanentemente qué elemento fue afectado, si se pausó o reanudó, quién realizó la acción, fecha y hora. El estado actual conserva además el motivo y responsable de la pausa vigente.

Una pausa superior se hereda: un relevamiento queda bloqueado si está pausado él mismo, su convocatoria, su segmento o su subsegmento. No se eliminan formularios ni se altera el estado de trabajo que tenía antes de la pausa.

En Mobile se informa “Pausado” y el motivo. Mientras esté pausado no se permite iniciar, cargar personas, adjuntar archivos, finalizar ni reabrir el relevamiento.

Si una persona fue capturada sin conexión o antes de que la tablet recibiera la pausa, el formulario y sus adjuntos permanecen guardados en SQLite. El rechazo por pausa no elimina la operación ni consume el límite de reintentos: queda pendiente y Mobile vuelve a intentar la sincronización cada cinco minutos hasta que el relevamiento sea reanudado.

## Archivos principales

- `programas/models/__init__.py`
- `programas/services/pausas.py`
- `programas/views/pausas.py`
- `programas/api/serializers.py`
- `programas/api/views.py`
- `programas/forms.py`
- `programas/migrations/0037_pausas_operativas.py`
- Templates de detalle de convocatoria, segmento, subsegmento y relevamiento.
- `mobile/src/services/relevamientoService.js`
- `mobile/src/screens/RelevamientosScreen.js`
- `mobile/src/screens/RelevamientoDetailScreen.js`

## Validación

- Pruebas de modelo, herencia de pausa, historial, reanudación y motivo obligatorio.
- Prueba API para comprobar que Mobile recibe la pausa y no puede iniciar el relevamiento.
- La cola offline conserva indefinidamente las cargas rechazadas por una pausa temporal.
- Compilación iOS de Expo completada correctamente.
- `manage.py check` sin errores y sin migraciones pendientes.

## Reversión

Retirar las acciones y bloqueos de pausa, los campos expuestos a Mobile y revertir controladamente `programas.0037`. La reversión elimina el historial de auditoría, por lo que requiere respaldo previo.

# Cambio 16 — Coordinador del segmento

## Implementación

- Se incorporó una capacidad específica para administrar Territoriales sin otorgar administración general de usuarios o roles.
- El Coordinador puede ingresar al listado, alta y edición de usuarios.
- Solo ve y administra usuarios con rol Territorial asignados a segmentos que coordina.
- En el formulario solamente puede seleccionar el rol Territorial y sus segmentos activos.
- El servidor rechaza roles o segmentos ajenos aunque se altere manualmente el formulario.
- El ABM de roles continúa oculto y devuelve acceso denegado ante una URL directa.
- La pausa continúa reservada al Administrador del programa.
- Se verificó el alcance existente sobre convocatorias, relevamientos, formularios, revisión y cupos.
- Las exportaciones continúan reservadas al Administrador.
- En los formularios donde se selecciona un Coordinador o Territorial se agregó **Crear usuario**.
- El alta rápida abre un modal con los datos personales y de acceso, fuerza el rol correspondiente y selecciona automáticamente al usuario creado.
- Al crear un Territorial también se lo asigna inmediatamente al segmento de la convocatoria o relevamiento.
- Solo el Administrador puede crear Coordinadores; Administradores y Coordinadores con alcance pueden crear Territoriales.

## Archivos principales

- `core/rbac.py`
- `programas/management/commands/seed_becas.py`
- `users/forms/__init__.py`
- `users/selectors/usuarios.py`
- `users/views/admin.py`
- `users/views/quick_create.py`
- `users/templates/user/_alta_rapida_modal.html`
- `templates/includes/sidebar/opciones.html`
- `users/migrations/0014_coordinador_gestiona_territoriales.py`
- `users/tests/test_coordinador_usuarios.py`

## Validación

- Pruebas aprobadas para opciones permitidas, alta normal y rápida, rechazo de segmento ajeno, selección/asignación automática, visibilidad acotada y bloqueo del ABM de roles.
- `manage.py check` sin errores.
- No se detectaron migraciones pendientes.

## Reversión

Retirar la capacidad `becas.usuario.territorial`, los alcances especiales del ABM, los cambios de menú y revertir `users.0014` de forma controlada.

# Cambio 17 — Referente

🟢 **HECHO**

## Implementación

- Se creó el rol `Becas — Referente` y una asignación explícita Referente → Coordinador del segmento.
- Hereda los segmentos del Coordinador y puede crear, editar, activar, desactivar y consultar solamente Territoriales de ese alcance.
- Puede consultar convocatorias, relevamientos, formularios y avances dentro del alcance heredado.
- No puede administrar roles, crear o modificar convocatorias/relevamientos ni pausar elementos.
- Los filtros se validan en el servidor. Al cambiar de Coordinador pierde el alcance anterior sin borrar datos históricos.

## Archivos principales

- `core/rbac.py`
- `programas/models/__init__.py`
- `programas/services/autorizacion.py`
- `programas/management/commands/seed_becas.py`
- `users/forms/__init__.py`
- `users/services/admin.py`
- `users/selectors/usuarios.py`
- `programas/tests/test_referente_regional.py`
- `programas/migrations/0038_asignacionterritorial_coordinador_regional_and_more.py`
- `users/migrations/0015_alter_capacidad_options.py`

## Reversión

Antes de revertir, respaldar la base. Quitar el rol Referente de los usuarios o reasignarlos, restaurar la configuración anterior de capacidades y filtros y, recién después de retirar el código que usa la relación, revertir `programas.0038` y `users.0015`. Revertir `programas.0038` elimina las asignaciones Referente → Coordinador.

# Cambio 18 — Coordinador regional

🟢 **REHECHO CON ALCANCE DE SUBSEGMENTO — 11/08/2026**

## Decisión vigente

El rol vuelve, pero **anclado al subsegmento** en lugar de a una Región. Las Regiones se eliminaron el 10/08 y no se recuperan: no vuelven la entidad Región, su pantalla, las asignaciones regionales ni la transferencia de responsabilidad. Lo que se repone es el perfil, con el subsegmento como unidad de alcance.

### Cómo se asigna

- El subsegmento gana un campo **Referente asignado**, disponible en el alta y en la edición.
- El selector solo ofrece usuarios con el rol `Becas — Coordinador Regional`.
- Es **uno solo por subsegmento**: elegir otro reemplaza al anterior. Un mismo Coordinador Regional sí puede tener varios subsegmentos a cargo, incluso de segmentos distintos.
- En el alta, junto al selector hay un botón **Crear referente** que da de alta el usuario con este rol sin salir de la pantalla (ver 6.1).

### Qué puede hacer

- Crear y editar **convocatorias** y **relevamientos** de sus subsegmentos.
- Crear y administrar **Territoriales** del segmento que los contiene.
- Ver el segmento únicamente como contexto.

### Qué no puede hacer

- Configurar el segmento: no tiene `becas.segmento.editar` ni `becas.requisito.*`, así que **Información general** y **Requisitos del segmento** le quedan cerrados por permisos, no solo ocultos en pantalla. Esas dos solapas directamente no se le muestran y entra a Subsegmentos.
- Ver los subsegmentos de sus pares. Si un segmento tiene tres subsegmentos con tres referentes distintos, cada uno ve solamente el suyo, tanto en el listado como al entrar por URL directa.
- Operar convocatorias a nivel segmento (las que no tienen subsegmento): quedan fuera de su alcance.

### Implementación

- Capacidad `becas.coordinador_regional` y rol `Becas — Coordinador Regional`, sembrado por `seed_becas` (aparece solo al desplegar, sin pasos manuales).
- El alcance se resuelve en `programas/services/autorizacion.py`. Como el resto de las pantallas ya filtraba por `subsegmentos_visibles` y `convocatorias_visibles`, acotar esos dos querysets propagó el alcance a convocatorias, relevamientos y revisión sin tocar cada vista.
- Se agregó `puede_operar_subsegmento`, que valida contra el subsegmento concreto y no contra el segmento padre. Sin eso, el rol podía abrir por URL el subsegmento de un par del mismo segmento; se aplica en el detalle, la edición y la eliminación.
- La **Revisión de formularios quedó deliberadamente fuera**: el rol crea relevamientos pero todavía no ve los formularios que salen de ellos. Sumarle `becas.revision.ver` es un cambio menor si se decide incluirlo.

### Validación

- 15 pruebas específicas aprobadas en `programas/tests/test_coordinador_regional.py`, incluidas la de aislamiento entre pares del mismo segmento y la de que el rol no se ofrezca como coordinador de segmento.
- `manage.py check` sin errores y sin migraciones pendientes.

### Corrección del 11/08 — el selector de Subsegmento ofrecía todos

**Pedido:** un Coordinador Regional que entra a **Becas → Convocatorias → Nueva convocatoria** ve correctamente su Segmento, pero el desplegable **Subsegmento** le lista todos los subsegmentos creados en ese segmento. Debe ofrecerle únicamente el que tiene asignado.

**Origen:** el desplegable no se arma con el queryset del formulario. `ConvocatoriaForm` ya recibía `subsegmentos_permitidos=subsegmentos_visibles(user)`, y por eso al guardar se rechazaba un subsegmento ajeno; pero las opciones visibles se cargan por AJAX contra `becas:segmento_subsegmentos_json`, que devolvía todos los subsegmentos del segmento sin mirar quién consultaba. La pantalla ofrecía opciones que el backend después no aceptaba.

**Corrección:** el endpoint pasó a filtrar por `subsegmentos_visibles(request.user)` —la misma función que ya usaba el formulario— y a buscar el segmento dentro de `segmentos_visibles(request.user)`, de modo que un segmento fuera de alcance responde 404 en lugar de exponer su contenido. Cubre las dos entradas del formulario, la pantalla Nueva convocatoria y el modal del listado, porque ambas consumen ese mismo endpoint. No requiere migración ni cambios de permisos.

**Archivos:** `programas/views/configuracion.py` y `programas/tests/test_coordinador_regional.py`.

**Validación:** dos pruebas nuevas —el referente ve únicamente su subsegmento aunque comparta segmento con un par, y un segmento fuera de alcance levanta `Http404`— más las 13 anteriores. `manage.py check` sin errores.

**Reversión:** revertir el filtrado en `segmento_subsegmentos_json` y retirar las dos pruebas. Se vuelve al comportamiento anterior sin tocar la base.

**Puesta en marcha:** desplegado el 11/08/2026 en la release `e5477a2`, junto con el Cambio 24. No requiere nada más que el deploy.

**Pendiente detectado:** el campo Subsegmento sigue siendo opcional para este rol. Si el Coordinador Regional crea una convocatoria sin subsegmento, queda a nivel segmento y `convocatorias_visibles` la deja fuera de su alcance, con lo cual desaparece de su listado apenas la guarda. Se resuelve exigiendo el subsegmento cuando quien crea es Coordinador Regional; queda a definición.

> **Resuelto el 11/08/2026 por el [Cambio 26](#cambio-26--el-subsegmento-es-obligatorio-para-el-coordinador-regional)**, con la definición que este párrafo proponía: se exige el subsegmento en vez de ampliarle la visibilidad.

## Historial: eliminación del 10/08/2026

Se había eliminado completamente el módulo: el rol `Becas — Coordinador regional`, la entidad Región, su pantalla, las asignaciones regionales, la transferencia de responsabilidad y los filtros regionales.

Se conservaron los datos y comportamientos ajenos a ese punto: Referente, Coordinador, Territorial, convocatorias, relevamientos y cupos.

## Archivos principales de la reposición

- `core/rbac.py` (capacidad `becas.coordinador_regional`)
- `programas/models/__init__.py` (`Subsegmento.referente`)
- `programas/services/autorizacion.py`
- `programas/management/commands/seed_becas.py`
- `programas/forms.py`
- `programas/views/configuracion.py`
- `programas/templates/programas/becas/config/segmento_detail.html`
- `programas/templates/programas/becas/config/_subsegmentos_panel.html`
- `programas/tests/test_coordinador_regional.py`
- `programas/migrations/0044_subsegmento_referente.py`
- `users/migrations/0018_alter_capacidad_options.py`

## Reversión de la reposición

Antes de revertir, respaldar la base. Desasignar los referentes de los subsegmentos (o aceptar perder esa asignación), quitar el rol a los usuarios que lo tengan, retirar el código que usa `Subsegmento.referente` y recién después revertir `programas.0044` y `users.0018`. Revertir `programas.0044` elimina la columna `referente` y con ella todas las asignaciones.

## Archivos retirados o modificados en la eliminación del 10/08

- `programas/templates/programas/becas/config/regiones.html` (retirado)
- `programas/services/regiones.py` (retirado)
- `programas/models/__init__.py`
- `programas/forms.py`
- `programas/views/configuracion.py`
- `programas/views/relevamientos.py`
- `programas/services/autorizacion.py`
- `programas/management/commands/seed_becas.py`
- `programas/admin.py`
- `programas/urls.py`
- `users/forms/__init__.py`
- `users/services/admin.py`
- `users/selectors/usuarios.py`
- `users/templates/user/user_form.html`
- `core/rbac.py`
- `templates/includes/sidebar/opciones.html`
- `programas/migrations/0041_remove_region_localidades_and_more.py`
- `users/migrations/0016_alter_capacidad_options.py`

## Reversión de esta eliminación

Para recuperar el módulo no alcanza con revertir una sola migración: primero debe restaurarse el código retirado y luego revertirse `users.0016` y `programas.0041`, o recuperarse el commit anterior completo. Si alguna de esas migraciones fue aplicada, realizar respaldo antes porque `programas.0041` elimina tablas y relaciones regionales.

## Implementación anterior retirada

## Implementación

- Se creó el rol `Becas — Coordinador regional` y la entidad Región, compuesta por localidades/subsegmentos.
- Puede crear convocatorias y relevamientos solamente en su Región y ve sólo las convocatorias creadas por él que permanecen bajo su responsabilidad.
- Puede crear, editar, activar, desactivar y asignar solamente Territoriales propios; no administra roles ni pausa elementos.
- Puede recibir un relevamiento propio y operar por Mobile con las mismas validaciones de asignación.
- El Administrador dispone de una pantalla de Regiones y una acción explícita de reemplazo.
- El selector de localidades de Regiones se unificó con la experiencia visual del Backoffice: permite buscar, seleccionar varias opciones, seleccionar las visibles, limpiar y muestra la cantidad elegida sin exigir `Ctrl`/`Cmd`.
- La edición de una Región se realiza en un modal sobre el listado, con los datos y localidades actuales precargados; la URL de edición se conserva como respaldo y reabre el mismo modal.
- El reemplazo transfiere Región, convocatorias vigentes y Territoriales, preserva el creador original y todos los datos, y registra origen, destino, ejecutor, fecha y cantidades transferidas en una auditoría inmutable.

## Archivos principales

- `programas/models/__init__.py`
- `programas/forms.py`
- `programas/services/autorizacion.py`
- `programas/services/regiones.py`
- `programas/views/configuracion.py`
- `programas/views/relevamientos.py`
- `programas/views/revision.py`
- `programas/templates/programas/becas/config/regiones.html`
- `users/forms/__init__.py`
- `users/services/admin.py`
- `users/selectors/usuarios.py`
- `programas/migrations/0038_asignacionterritorial_coordinador_regional_and_more.py`
- `programas/migrations/0039_transferenciaregional.py`
- `programas/tests/test_referente_regional.py`

## Validación

- 100 pruebas aprobadas sobre roles, alcance, usuarios, pausas, API Mobile y transferencias.
- `manage.py check` sin errores y sin migraciones pendientes.

## Reversión

Respaldar la base antes de intervenir. Primero desasignar o migrar los usuarios Regionales y restaurar capacidades/filtros anteriores. Luego retirar el código dependiente y revertir, en este orden, `programas.0039`, `programas.0038` y `users.0015`. Revertir `0039` elimina el historial de transferencias; revertir `0038` elimina Regiones, asignaciones y los campos de creador/responsable, por lo que el respaldo es obligatorio.

# Cambio 19 — Territorial

🟡 **PARCIALMENTE HECHO — CONTROL GPS PENDIENTE**

## Implementación

- El usuario que tiene exclusivamente el rol/capacidad Territorial ya no puede iniciar sesión en el Backoffice.
- El rechazo ocurre en el servidor y muestra que debe utilizar la aplicación móvil; no depende de ocultar opciones del menú.
- El acceso por token de Mobile se mantiene habilitado.
- La API entrega la localidad desde el subsegmento de la convocatoria asignada.
- Mobile muestra **Localidad asignada** y no permite seleccionar ni enviar otra localidad.
- La API continúa comprobando que el relevamiento pertenezca al Territorial autenticado; cada formulario queda vinculado en el servidor a ese relevamiento y su localidad.

## Cupo por relevamiento implementado

- Cada relevamiento posee un cupo configurable, con valor inicial de 100 para compatibilidad con los existentes.
- Todo usuario con permiso para crear relevamientos puede establecerlo o modificarlo desde Backoffice.
- Se muestran personas utilizadas, cupo máximo y estado completo.
- Toda persona relevada ocupa un lugar, sin importar si está pendiente, aprobada o rechazada.
- Mobile contabiliza también los formularios guardados offline y bloquea el botón de nueva persona al alcanzar el límite.
- La API bloquea cargas excedentes con `CUPO_RELEVAMIENTO_COMPLETO` y conserva la idempotencia de reintentos.
- El cupo puede aumentarse, pero no reducirse por debajo de las personas ya cargadas.

## Definición GPS confirmada y pendiente técnico

- Cada captura debe controlarse por GPS y verificarse contra la localidad asignada.
- Mobile ya captura y envía coordenadas, pero el servidor todavía debe hacerlas obligatorias y comprobar su pertenencia geográfica.
- Se necesita una fuente oficial de límites/polígonos de localidades para completar esa validación.

## Archivos principales

- `users/forms/auth.py`
- `users/tests/test_usuarios_abm.py`
- `programas/api/serializers.py`
- `programas/api/views.py`
- `programas/forms.py`
- `programas/models/__init__.py`
- `programas/views/relevamientos.py`
- `programas/templates/programas/becas/relevamientos/relevamiento_detail.html`
- `programas/migrations/0040_relevamiento_cupo_maximo.py`
- `programas/tests/test_becas_api.py`
- `programas/tests/test_becas_relevamientos.py`
- `mobile/src/services/relevamientoService.js`
- `mobile/src/screens/RelevamientoDetailScreen.js`

## Validación

- 46 pruebas de login y API aprobadas.
- Prueba específica aprobada para verificar que la localidad asignada sea informada por el servidor.
- Pruebas específicas aprobadas para aumento de cupo, rechazo de reducción inválida, bloqueo de cargas excedentes e idempotencia de sincronización.

## Reversión del cupo

Respaldar la base, retirar primero las referencias a `cupo_maximo` de Backoffice, API y Mobile y revertir luego `programas.0040`. La reversión elimina únicamente el cupo propio del relevamiento; no elimina formularios existentes.

# Cambio 20 — Separar la administración de Usuarios y de Roles por programa

🟢 **HECHO**

## Pedido original

La capacidad **Configurar programas** (`programa.configurar`) daba, con un solo tilde, acceso a Usuarios **y** a Roles. Se pidió dividirla en dos: una para usuarios y otra para roles, funcionando de la misma manera —asignada a un usuario de un programa, le permite gestionar los usuarios de su programa y los roles de sus programas— pero pudiendo otorgar una sin la otra.

## Alcance acordado

- Dos capacidades nuevas, ambas acotadas al programa del rol que las lleva.
- Se otorgan por separado: se puede dar la gestión de usuarios sin la de roles, y a la inversa.
- `programa.configurar` conserva únicamente su función original, el asistente de configuración de programas, y deja de conferir alcance sobre Usuarios y Roles.
- Ningún rol existente pierde lo que venía haciendo.

## Implementación

- Se agregaron al catálogo **Administrar los usuarios de su programa** (`programa.usuario.administrar`) y **Administrar los roles de su programa** (`programa.rol.administrar`), dentro del módulo Programas.
- El alcance quedó definido en dos conjuntos separados, uno por cada módulo. La capacidad paraguas del programa Becas (`becas.programa.administrar`) integra ambos, de modo que el Administrador de Becas conserva la gestión de usuarios y suma la de roles de su programa. **(Modificado — ver Historial.)**
- Las capacidades que abren cada módulo se derivan de esos mismos conjuntos, para que la puerta de entrada y el alcance no puedan quedar desalineados. Esa desalineación era la causa de que un usuario pudiera entrar a Usuarios y no ver a nadie.
- El selector de programas administrables pasó a ser parametrizable, con una variante por módulo. Los doce puntos del código que lo consumían se repartieron según qué resuelven: usuarios, roles o la unión de ambos.
- El desplegable de Roles dentro del ABM de Usuarios se acota por la capacidad de **usuarios**, no por la de roles: allí se asignan roles a una persona, no se administran.
- El menú lateral muestra Usuarios y Roles de forma independiente, según la capacidad correspondiente.
- La verificación de “no dejar un programa sin administrador” usa la unión de ambas capacidades, para que quitar una no bloquee la edición.

## Archivos principales

- `core/rbac.py`
- `users/selectors/roles.py`
- `users/selectors/usuarios.py`
- `users/forms/__init__.py`
- `users/forms/roles.py`
- `users/views/admin.py`
- `users/views/roles.py`
- `users/services/roles.py`
- `templates/includes/sidebar/opciones.html`
- `users/migrations/0019_separar_admin_programa_usuarios_roles.py`
- `users/tests/test_usuarios_abm.py`
- `users/tests/test_roles_abm.py`
- `users/tests/test_rbac.py`

## Migración y datos

`users.0019_separar_admin_programa_usuarios_roles` incorpora las dos capacidades al catálogo y **otorga ambas a todo rol que ya tuviera `programa.configurar`**, de modo que nadie pierde acceso al desplegar. A esos roles se les conserva `programa.configurar`, porque sigue habilitando el asistente de programas.

## Validación

- 191 pruebas de `users` ejecutadas, sin fallas y sin errores nuevos respecto de la medición previa al cambio (188 pruebas con el mismo piso de errores de entorno).
- Tres pruebas nuevas: alcance de usuarios y de roles independientes entre sí, y menú lateral con una sola capacidad, con la otra y con ambas.
- Se actualizó una prueba previa que asumía que una sola capacidad abría las dos secciones; su cambio confirma la separación.
- `manage.py check` sin observaciones y sin migraciones pendientes.
- Auditoría de diseño y compilación de plantillas sin errores.

## Reversión

Respaldar la base y revertir `users.0019`, que elimina las dos capacidades del catálogo junto con sus permisos. Antes de revertir hay que confirmar que los roles afectados conserven `programa.configurar`: al volver atrás, esa capacidad vuelve a ser la única que otorga alcance sobre Usuarios y Roles, y un rol al que se le hubiese quitado en el ínterin quedaría sin acceso a ambos módulos.

Esta reversión quedó además condicionada por el Cambio 24: hoy hay que revertir primero ese cambio, porque de lo contrario quitar la `0019` deja al Administrador de Becas sin ninguna de las capacidades que le dan alcance.

## Historial

**11/08/2026 — El criterio de esta entrada fue modificado por el [Cambio 24](#cambio-24--el-alcance-sobre-usuarios-y-roles-solo-por-capacidades-transversales).**

Lo que decía antes: el alcance sobre los dos módulos lo integraba también la capacidad paraguas del programa Becas (`becas.programa.administrar`), de modo que el Administrador de Becas lo recibía por esa vía.

Qué lo cambió: al revisar el rol se vio que las tres capacidades de programa estaban destildadas y el usuario igual veía la sección Administración. Que la paraguas confiriera ese alcance hacía imposible quitarle los dos módulos al Administrador de Becas sin vaciarle el rol, y obligaba a que cada programa nuevo tuviera su propia capacidad paraguas para poder delegar la gestión. Desde el Cambio 24 el alcance lo dan **solo** las dos capacidades transversales, y la paraguas quedó acotada a su dominio.

También se corrigieron entonces 19 pruebas que este cambio había dejado en rojo: construían el administrador de programa otorgando `programa.configurar`, que esta misma entrada dejó de tratar como tal, y sus preparaciones nunca se actualizaron.

# Cambio 21 — Textos con caracteres rotos en todo el sistema

🟢 **HECHO**

## Pedido original

> «Buscá todas las palabras que se rompieron como estas: `Despu`+`Ã`+`©`+`s` y arreglalas en todo el sistema.»

Pedido posterior al documento “Cambios en DataÑach”; no corresponde a ninguno de sus 19 puntos.

## Origen del problema

Texto escrito en UTF-8 y vuelto a leer como cp1252/latin-1. Cada carácter acentuado quedó convertido en dos o tres caracteres visibles:

| Debía verse | Se veía como |
|---|---|
| `é` | `Ã`+`©` |
| `ó` | `Ã`+`³` |
| `í` | `Ã`+`­` |
| `—` (guion largo) | `â`+`€`+`”` |
| `·` (separador) | `Â`+`·` |

> Los ejemplos de esta sección escriben los caracteres dañados **separados uno por uno a propósito**. Si se escribieran pegados, cualquier revisión de codificación —incluida la de este mismo cambio— los “corregiría” y la explicación quedaría sin sentido. Ya ocurrió una vez durante la implementación.

## Alcance acordado

- Se revisaron todos los archivos versionados del repositorio.
- Se corrigió únicamente el texto dañado. No se modificó lógica, comportamiento ni datos.
- Quedaron fuera de alcance el `static/admin/` vendorizado de Django y el texto dañado a propósito del reparador de RENAPER (ver “Exclusiones deliberadas”).
- Quedó fuera de alcance la base de datos. Si existieran registros cargados con el mismo defecto, requieren una corrección de datos aparte de este cambio.

## Método de detección

No se buscó una lista de patrones conocidos, que siempre deja casos afuera. Se detectó por reversión: todo grupo de caracteres que, recodificado a cp1252 —con latin-1 de reserva— y releído como UTF-8, produzca un texto válido y distinto, es texto dañado. Una `ñ` o una `Ñ` correctas no superan esa prueba y quedan intactas.

Gracias a eso se descartaron falsos positivos en `config/settings.py`, `templates/inicio.html`, `users/templates/user/login.html`, el menú lateral y las fixtures de localidades: sus coincidencias eran la `Ñ` de DATAÑACH y nombres propios correctamente escritos.

## Correcciones realizadas

56 correcciones en 4 archivos:

| Archivo | Correcciones | Qué contenía |
|---|---|---|
| `programas/templates/programas/becas/config/segmento_list.html` | 13 | Único texto visible al usuario: el aviso “Después de guardar…”, las etiquetas “Descripción” (dos veces) y “Cupo máximo”, el título “Becas · Segmentos” y 7 comentarios internos |
| `users/tests/test_rbac.py` | 17 | Comentarios y docstrings |
| `users/tests/test_usuarios_abm.py` | 15 | Comentarios y docstrings |
| `users/tests/test_roles_abm.py` | 11 | Comentarios, docstrings y el nombre del programa de prueba “Vacío” |

**Caso especial:** en `users/tests/test_roles_abm.py` un guion largo había perdido además su tercer carácter (quedó `â`+`€` seguido de una comilla común en lugar de la comilla tipográfica), por lo que no admitía reversión automática: la secuencia ya no era reversible. Se corrigió a mano como `—`, igual que los docstrings equivalentes de los puntos 65 y 67.

## Exclusiones deliberadas

`legajos/services/consulta_renaper.py` y `legajos/tests/test_consulta_renaper_encoding.py` conservan caracteres dañados **a propósito**: son la lista de marcadores y los casos de prueba del reparador de respuestas de RENAPER, que llegan con este mismo defecto desde el organismo. Corregirlos habría desactivado esa reparación.

Cualquier revisión futura de codificación debe respetar esas dos excepciones. Este documento no necesita ser excluido: sus ejemplos están escritos carácter por carácter justamente para no ser confundidos con texto a corregir.

## Archivos

- `programas/templates/programas/becas/config/segmento_list.html`
- `users/tests/test_rbac.py`
- `users/tests/test_roles_abm.py`
- `users/tests/test_usuarios_abm.py`

## Base de datos

No requiere migración y no modifica datos existentes.

## Validación

- `scripts/design_audit.py --changed`: 0 errores.
- `scripts/compile_templates.py`: 301 plantillas compiladas, 0 errores.
- `manage.py check`: sin errores.
- Barrido final sobre todo el repositorio: no queda texto dañado, salvo las 6 líneas intencionales de RENAPER.
- Equivalencia de los tres archivos de prueba: su árbol de sintaxis, con las cadenas normalizadas, es idéntico al anterior. Es decir que no cambió ninguna instrucción; la única variación está en docstrings y en el par de literales “Vacío” que se crea y se verifica dentro del mismo caso.

**Observación sobre la suite:** no se utilizó el conteo de pruebas fallidas como criterio de aceptación, porque con `PYTEST_RUNNING=1` la suite no es determinista: dos corridas idénticas del estado anterior arrojaron 30 y 16 fallas. Por eso la verificación se hizo comparando el árbol de sintaxis, que sí es concluyente para un cambio que sólo toca texto.

## Reversión

No requiere base de datos. Alcanza con restaurar los cuatro archivos al commit anterior.

El template no debe revertirse parcialmente: el título, las dos etiquetas y el aviso del modal tienen que quedar todos en la misma codificación.

## Puesta en marcha en el servidor

Desplegado el 11/08/2026 en la release `e5477a2`. Solo el template llega al release: los tres archivos de prueba también viajan, pero el texto corregido que ve el operador es el de `segmento_list.html`.

## Recomendación pendiente

Incorporar esta detección a `scripts/design_audit.py`, que ya es la fuente única de los chequeos mecánicos y se ejecuta automáticamente después de cada edición. Así el defecto no podría volver a entrar sin aviso. No se implementó dentro de este alcance.

---

# Cambio 22 — Vigencia del programa SIIS en los segmentos

🟢 **HECHO**

## Pedido original

> «La integración de SIIS para traer el segmento, es decir el programa para SIIS, quiero que me traiga los activos.» Y luego: «quiero que avise si pasó a inactivo, hay que bloquearlo y tienen que mostrar una alerta que informe del cambio de SIIS», más un botón informativo con el detalle del programa.

Pedido posterior al documento “Cambios en DataÑach”. Se apoya en el Cambio 8 (Incorporar programas), que es la integración con el catálogo de ECOM.

## Situación previa

El catálogo ya se pedía con `?estado=ACTIVO`, pero nada verificaba la respuesta: si SIIS ignoraba el parámetro o cambiaba su valor por defecto, los programas dados de baja entraban igual al selector. Y sobre todo, un programa **ya vinculado** que después dejaba de estar vigente no generaba ningún aviso: se descubría recién cuando una prevalidación devolvía `PROGRAMA_INACTIVO`.

## Implementación

### El catálogo del selector

Se mantiene el pedido con `?estado=ACTIVO` y además **se vuelve a filtrar por estado sobre la respuesta**, para no depender de que el servicio respete el parámetro. Si SIIS dejara de informar el campo `estado`, no se filtra: es preferible un catálogo completo a un selector vacío que impida dar de alta segmentos.

### La detección de bajas

Necesita el catálogo completo (`?estado=TODOS`), no el filtrado. Con `ACTIVO`, un programa dado de baja simplemente desaparece de la respuesta y no se distingue de una lista incompleta por una falla del servicio. Son dos consumos distintos del mismo endpoint, con propósitos distintos.

### Lo que se guarda en el segmento

- El **detalle del programa se congela al vincularlo** (nombre, descripción, jurisdicción, los cinco controles de elegibilidad y la edad mínima). Esa foto es la referencia contra la que se compara después, y no se pisa al sincronizar.
- Aparte se guarda el **estado corriente** y la fecha de última verificación.

### El bloqueo

Un programa `INACTIVO` —o que dejó de figurar en el catálogo— bloquea el segmento a través de `pausa_efectiva`, el mismo mecanismo de la pausa manual, que ya cascadea a subsegmento, convocatoria, relevamiento, backoffice y app de campo.

**No se toca el campo `pausado`**: es una acción manual con autor y trazabilidad propia. Si el proceso automático lo escribiera, alguien podría “reanudar” un segmento cuyo programa SIIS sigue inactivo. La pausa manual conserva su precedencia y su motivo.

Con el segmento bloqueado no se pueden cargar ni editar relevamientos, y la convocatoria desaparece del selector.

### El aviso

- Franja de advertencia en el listado de segmentos y en el detalle, indicando qué programa cambió y desde cuándo.
- Chip **“SIIS inactivo”** en la columna Estado de la tabla, separado del Activo/Inactivo local: son dos dimensiones distintas y no deben mezclarse.
- Botón **“!”** que abre el detalle del programa tal como estaba al vincularlo, con su estado actual al lado para que el cambio quede a la vista. Es solo informativo.

## Puesta en marcha en el servidor

La actualización de estados la hace `python manage.py sincronizar_programas_siis` (idempotente, con `--dry-run`). **Requiere una entrada de cron**, sin la cual la baja no se detecta sola: snippet versionado en `docker/cron/sincronizar_programas_siis.cron`.

No debe agregarse a `LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS`: el `docker-entrypoint.sh` corre con `set -eu` y sin tolerancia a fallos, y el comando termina con error si SIIS no responde, así que una caída de ECOM dejaría el contenedor `web` sin arrancar.

## Archivos

- `programas/services/siis.py`
- `programas/services/siis_sync.py`
- `programas/models/__init__.py`
- `programas/forms.py`
- `programas/views/configuracion.py`
- `programas/templatetags/becas_extras.py`
- `programas/management/commands/sincronizar_programas_siis.py`
- `programas/templates/programas/becas/config/_segmentos_table.html`
- `programas/templates/programas/becas/config/segmento_list.html`
- `programas/templates/programas/becas/config/segmento_detail.html`
- `programas/templates/programas/becas/config/_siis_programa_modal.html`
- `docker/cron/sincronizar_programas_siis.cron`
- `programas/tests/test_siis_service.py`
- `programas/tests/test_siis_vigencia_programa.py`
- `programas/migrations/0043_siis_programa_detalle.py`

## Base de datos

`programas.0043` agrega cuatro campos a `Segmento`, todos aditivos y con valor por defecto vacío: el detalle congelado, el estado actual, la fecha de vinculación y la de última verificación. Un segmento sin estado no queda bloqueado, así que la migración es segura sobre datos existentes.

## Validación

- 35 pruebas aprobadas entre el cliente de SIIS y el ciclo de vigencia, incluidos el descarte de inactivos, el catálogo completo para detectar bajas, la propagación del bloqueo hasta el relevamiento y la precedencia de la pausa manual.
- `manage.py check` sin errores y sin migraciones pendientes.
- `scripts/design_audit.py --changed` y `scripts/compile_templates.py`: 0 errores.
- Verificado en producción contra el SIIS real: los dos programas vinculados (`#34 Chaco Joven` y `#15 Chaco Olímpico ley 7353`) figuran ACTIVOS, por lo que ningún segmento quedó bloqueado.

**Observación:** las pruebas de vista no cubren la franja, el chip ni el modal. La suite no puede ejercitar vistas en este entorno por una incompatibilidad de Python 3.14 con Django 4.2 al copiar el contexto de plantilla, ajena a este cambio. Se compensó con una prueba directa del filtro que alimenta el modal.

## Reversión

Antes de revertir, respaldar la base. Retirar la entrada de cron, quitar el código que usa los campos nuevos y recién después revertir `programas.0043`, que elimina el detalle congelado y el estado de todos los segmentos. No afecta el vínculo con el programa (`siis_programa_id`), que es anterior a este cambio.

# Cambio 23 — Orden de los requisitos: autonumerado y sin repetidos

🟢 **HECHO — 11/08/2026**

| | |
|---|---|
| **Programa / módulo** | Becas — configuración de requisitos |
| **Solicitante** | PM, pedido directo en sesión de trabajo |
| **Fecha del pedido** | 11/08/2026 |
| **Issue / épica** | Sin issue |
| **Partes afectadas** | Backoffice |
| **Migración** | No requiere |

## Pedido original

«Tanto en los Requisitos del segmento, como del subsegmento, como los generales, el valor orden se puede ingresar pero si no se ingresa se autonumera. Sumale la validación de que no puede haber los mismos valores, es decir no podés tener 2 iguales en el mismo orden.»

## Alcance acordado

- Las tres pantallas se comportan igual: el orden es opcional y, si queda vacío, se asigna el siguiente disponible.
- Dos requisitos no pueden compartir el mismo orden dentro de su alcance.
- Queda afuera el orden de los **campos de tipos de dispositivo**, que tiene la misma forma pero pertenece a otro módulo y no estaba en el pedido.

## Decisiones tomadas

- **La unicidad es por lista, no global.** Se controla entre los requisitos propios del segmento, entre los de cada subsegmento y entre las preguntas generales, por separado. Motivo: son tres listas distintas dentro del formulario que completa el territorial, y un requisito propio del subsegmento no compite por posición con uno heredado del segmento. Un subsegmento puede tener su orden 1 aunque el segmento ya tenga el suyo.
- **Vacío significa «el siguiente», no «reordenar todo».** Se toma el orden más alto de esa lista y se le suma uno. Motivo: es el cambio mínimo y no toca los órdenes ya asignados a otros requisitos.
- **Al editar, el requisito no se compara consigo mismo.** Motivo: guardar un requisito sin tocarle el orden nunca debe fallar.
- **La validación es del formulario y no una restricción de la base.** Motivo: los datos existentes ya tienen órdenes repetidos —las preguntas generales creadas con el formulario anterior quedaron todas en cero—, así que una restricción de unicidad no habría podido aplicarse sobre esa tabla. Se asume la consecuencia descrita en Base de datos.
- **Las dos reglas viven en un único lugar compartido por los tres formularios.** Motivo: evitar que la numeración de una pantalla evolucione distinto de las otras, que es exactamente lo que había pasado antes: los requisitos ya autonumeraban y los generales no.
- **Se agregó el espacio del mensaje de error debajo del campo.** Motivo: sin ese espacio, el envío por AJAX descartaba el detalle del error y solo mostraba el aviso genérico «Revisá los datos del formulario», dejando al operador sin saber qué corregir.

## Implementación

- El orden dejó de ser obligatorio en los tres formularios. El campo muestra *Automático* como leyenda mientras está vacío.
- El mensaje de error nombra el número ocupado y el alcance: *«Ya hay otro requisito con el orden 3 en este segmento. Elegí un número libre.»*
- Se corrigió el alta de requisitos generales, que enviaba el orden fijo en cero. Ese valor impedía que la numeración automática se activara alguna vez.

## Archivos

- `programas/forms.py`
- `programas/templates/programas/becas/config/pregunta_list.html`
- `programas/templates/programas/becas/config/requisitos_segmento.html`
- `programas/templates/programas/becas/config/segmento_detail.html`
- `programas/templates/programas/becas/config/subsegmento_detail.html`
- `programas/tests/test_becas_config.py`

## Base de datos

**No requiere migración.** Consecuencia a tener presente: un requisito que ya venía con orden repetido no se puede guardar desde el formulario hasta darle un número libre. El mensaje indica cuál está ocupado.

## Validación

- Once pruebas nuevas: numeración correlativa con el campo vacío, numeración a partir del orden más alto cargado a mano, rechazo de repetidos en segmento y en subsegmento, independencia entre ambos alcances, edición conservando el orden propio y edición hacia un orden ocupado.
- Suite de `programas` sin fallas nuevas respecto de la medición previa al cambio.
- `manage.py check` sin observaciones. `scripts/design_audit.py` sobre las cuatro plantillas: 0 errores. `scripts/compile_templates.py`: 301 plantillas, 0 errores.
- Las pruebas de rechazo de repetidos se escribieron sobre el formulario y no sobre la respuesta de la vista, por la limitación de entorno descrita en el Cambio 24.

## Puesta en marcha en el servidor

Desplegado el 11/08/2026 junto con el Cambio 20, en la release `451817d`. Verificado que quedó horneado en el contenedor.

## Pendientes / a definir

- El orden de los **campos de tipos de dispositivo** tiene la misma forma y quedó sin la regla. Aplicarle la misma implementación es un cambio de dos líneas si se decide unificarlo.
- Los requisitos y preguntas que ya tienen orden repetido en producción siguen así hasta que alguien los edite. Si se quiere una base sin repetidos —y con ello la opción de una restricción real en la base— hay que normalizarlos primero.

## Reversión

Revertir los seis archivos. No se pierden datos: los órdenes ya asignados quedan como estén y el formulario anterior los acepta sin validación. No hay migración que deshacer.

## Historial

No aplica: entrada nueva.

# Cambio 24 — El alcance sobre Usuarios y Roles, solo por capacidades transversales

🟢 **HECHO — 11/08/2026**

| | |
|---|---|
| **Programa / módulo** | Transversal — permisos (RBAC) |
| **Solicitante** | PM. Lo detectó revisando el rol «Becas — Administrador» y definió el criterio general en la misma sesión |
| **Fecha del pedido** | 11/08/2026 |
| **Issue / épica** | Sin issue |
| **Partes afectadas** | Backoffice |
| **Migración** | `users.0020` |

## Pedido original

El PM observó que el rol **Becas — Administrador** tenía sin tildar las tres capacidades de programa —Configurar programas, Administrar los usuarios de su programa y Administrar los roles de su programa— y sin embargo el usuario veía la sección **Administración** con Usuarios y Roles. Preguntó por qué.

La causa era que la capacidad paraguas del programa (`becas.programa.administrar`) también otorgaba ese alcance. Sobre eso definió el criterio:

> «Lo que haría para todos los programas de acá en adelante es otorgando el rol *Administrar los usuarios de su programa* y *Administrar los roles de su programa*: podés gestionar sus roles y sus usuarios, y con eso nos evitamos tener capacidades como `becas.programa.administrar`.»

## Alcance acordado

- Las dos capacidades transversales pasan a ser la **única** fuente del alcance sobre ambos módulos, para todos los programas.
- La capacidad paraguas de Becas **se conserva**: solo deja de conferir el alcance transversal.
- Ningún rol existente pierde lo que venía haciendo.
- Queda explícitamente afuera la capacidad del Coordinador para crear territoriales (`becas.usuario.territorial`).

## Decisiones tomadas

- **La paraguas de Becas no se elimina, solo pierde su doble función.** Motivo: gatea ocho puntos del dominio Becas —reportes, revalidación con RENAPER, pausas y el alta de coordinadores—, así que borrarla era desarmar el programa. Lo que se corrigió es que una misma capacidad hiciera dos trabajos distintos: dominio del programa y alcance transversal del RBAC. Ahora **paraguas = dominio; `programa.*.administrar` = RBAC**.
- **Se descartó destildarle la paraguas al rol** como alternativa sin tocar código. Motivo: le habría sacado mucho más que el menú, y el control de «no dejar un programa sin administrador» cuenta esa misma capacidad, con lo que el programa podía quedarse sin administrador.
- **`becas.usuario.territorial` no se toca**, aunque sea un nombre de Becas dentro de una constante transversal. Motivo: no es «administra el programa» sino «los territoriales de mis segmentos», y no existe hoy una capacidad genérica que modele ese alcance. Hacerlo convertía un cambio de dos archivos en un rediseño. Es prolijidad, no funcionamiento.
- **La migración de traspaso va en la misma release que el código, y no es opcional.** Motivo: el riesgo silencioso descrito en Base de datos.
- **La vuelta atrás de la migración es deliberadamente neutra: no borra capacidades.** Motivo: no hay forma de distinguir si un rol las tiene por esta migración, por la `0019` o porque alguien las tildó a mano; borrarlas revocaría un acceso legítimo. Al revertir el código la paraguas recupera su doble función y las capacidades repartidas quedan redundantes pero inofensivas.
- **El menú lateral pasó a derivar de las mismas constantes que usan las vistas.** Motivo: era el único lugar del sistema donde las capacidades estaban enumeradas a mano —seis por condición, cuatro condiciones—, y esa duplicación es la que generó la consulta que originó este cambio. Con la derivación, el menú y la puerta de entrada no pueden quedar desalineados.
- **El sembrado de Becas otorga las dos capacidades explícitamente.** Motivo: `asegurar_roles_becas` **reemplaza** el conjunto de capacidades del rol, así que una corrida del sembrado habría borrado lo que la migración acababa de otorgar, y cualquier entorno nuevo habría nacido con el Administrador sin acceso a los dos módulos. Se derivan de la constante para que no puedan desincronizarse.

## Implementación

- Los dos conjuntos de alcance quedaron con una sola capacidad cada uno. Es el cambio completo de comportamiento: todo lo demás del sistema los lee, no los redefine.
- El menú lateral muestra Administración, Usuarios y Roles según los mismos conjuntos que abren cada módulo.
- En la pantalla del rol las dos capacidades quedan **tildadas y a la vista**: lo que antes era implícito ahora se ve.

## Archivos

- `core/rbac.py`
- `core/templatetags/rbac.py`
- `templates/includes/sidebar/opciones.html`
- `programas/management/commands/seed_becas.py`
- `users/migrations/0020_alcance_abm_solo_capacidades_transversales.py`
- `users/tests/test_rbac.py`
- `users/tests/test_usuarios_abm.py`
- `users/tests/test_roles_abm.py`
- `programas/tests/test_becas_rbac.py`
- `programas/tests/test_dispositivos_config.py`

## Base de datos

`users.0020_alcance_abm_solo_capacidades_transversales` otorga las dos capacidades transversales a todo rol que tuviera la paraguas de Becas, de modo que nadie pierde acceso al desplegar. **No agrega capacidades al catálogo ni modifica tablas:** solo reparte permisos existentes, así que es segura sobre datos existentes.

**Por qué no es opcional.** Sin el traspaso, el Administrador de Becas no solo perdía los dos módulos. El alcance territorial está definido **por exclusión** —tiene la capacidad de crear territoriales y no administra ningún programa—, así que el Administrador habría quedado clasificado como gestor territorial, y ese alcance son «los territoriales de los segmentos que coordina», que para un administrador son ninguno. El resultado no habría sido un aviso de permisos sino un listado de Usuarios **vacío**: se ve el menú, se entra sin error y no aparece nadie. Una lista vacía se reporta como pérdida de datos; un aviso de permisos se diagnostica en segundos.

## Validación

- Cinco pruebas nuevas que fijan el criterio: la paraguas sola no otorga alcance, no muestra la sección Administración y no cuenta como administrador del programa; las dos transversales sí; y cada módulo se otorga por separado.
- Una prueba nueva que protege el sembrado: verifica que el rol Administrador reciba las dos capacidades, para que el reemplazo del conjunto no vuelva a dejarlo sin acceso.
- **Se encontraron 19 pruebas que el Cambio 20 había dejado en rojo** y nunca se actualizaron: construían el administrador de programa otorgando `programa.configurar`, que ese mismo cambio dejó de tratar como tal. Se corrigieron los siete puntos de preparación involucrados, cada uno con la capacidad que la prueba realmente necesita. Medido contra el estado previo: de 139 pruebas en rojo se pasó a **124**, con **16 recuperadas y ninguna rota**.
- `manage.py check` sin observaciones. `scripts/design_audit.py` sobre el menú lateral: 0 errores y 0 advertencias. `scripts/compile_templates.py`: 301 plantillas, 0 errores.

## Puesta en marcha en el servidor

**Desplegado el 11/08/2026 en la release `e5477a2` (`development@c55fd5f`)**, sin backup de base por pedido del PM: la migración es un `RunPython` que solo reparte permisos ya existentes entre grupos, no toca esquema ni datos de negocio, y su vuelta atrás es no-op.

La migración la aplicó el entrypoint al arrancar el contenedor, antes de atender pedidos, así que no hubo ventana en la que un rol quedara sin alcance. Verificado en el servidor: `users.0020` en `[X]`, `web` y `websocket` healthy, nginx reiniciado después de recrearlos, `/health/` y el login en 200, y las constantes nuevas horneadas en el contenedor (`CAPS_ADMIN_PROGRAMA_USUARIOS` con una sola capacidad y el sidebar derivando de los filtros).

**Queda la verificación funcional por rol:** entrar con un usuario real de cada rol de Becas —Administrador, Coordinador, Coordinador Regional y Referente— y confirmar que Usuarios y Roles listen lo que corresponde a cada uno. **El síntoma a buscar es la lista vacía, no el aviso de permisos.**

## Pendientes / a definir

- **Verificación funcional por rol en el servidor**, según el punto anterior. Es lo único que el despliegue no cubre: la migración quedó aplicada, pero que cada rol vea a quien debe se comprueba entrando.
- **`becas.usuario.territorial` sigue nombrada dentro de una constante transversal**, como capacidad que abre el módulo de Usuarios. No afecta el funcionamiento; queda para cuando se modele el alcance del Coordinador con una capacidad genérica.
- **El entorno local de pruebas no sirve como red de seguridad completa.** Corre Python 3.14, incompatible con el cliente de pruebas de Django 4.2: falla con `AttributeError: 'super' object has no attribute 'dicts'` en cualquier prueba que renderice una plantilla, y de ahí sale la mayor parte de las 124 en rojo, todas anteriores a este cambio. Tres de las 19 corregidas siguen figurando en rojo por esa causa, pero ya superan el control de acceso y fallan recién al renderizar. Se arregla volviendo el entorno a **Python 3.12**, el stack documentado en `CLAUDE.md`; hasta entonces conviene validar los formularios sobre el formulario mismo y no sobre la respuesta de la vista. Receta del entorno sin Docker en [venv-setup.md](venv-setup.md).

## Reversión

Revertir los archivos de código y el sembrado. La migración `users.0020` se puede revertir sin efecto: su vuelta atrás no borra nada, por el motivo explicado en Decisiones tomadas. Al revertir el código la paraguas recupera su doble función, de modo que las capacidades repartidas quedan redundantes pero inofensivas. No se pierden datos.

## Historial

No aplica: entrada nueva. Modifica el criterio del **Cambio 20**, cuyo historial quedó registrado en esa entrada.

# Cambio 25 — La zona del relevamiento se elige del catálogo de localidades

🟢 **HECHO — 11/08/2026**

| | |
|---|---|
| **Programa / módulo** | Becas — relevamientos |
| **Etiquetas** | `#relevamientos` `#ui` `#datos` |
| **Solicitante** | PM, pedido directo en sesión de trabajo |
| **Fecha del pedido** | 11/08/2026 |
| **Issue / épica** | Sin issue |
| **Partes afectadas** | Backoffice |
| **Migración** | No requiere |

## Pedido original

> «En Nuevo relevamiento, el campo Zona / Localidad tiene que tomar el valor de `/configuracion/localidades/`.» Y al definir la forma: «no hace falta hacer migración, y que sea un selector filtrado con 2 campos Municipios y Localidades, siempre filtrando por Chaco».

## Alcance acordado

- El campo deja de escribirse a mano y pasa a elegirse con **dos selectores encadenados**: Municipio filtra, Localidad es el valor.
- Los dos se acotan a **Chaco**; el catálogo es nacional.
- **Sin migración**: `zona` sigue siendo texto en el modelo.
- Queda afuera la zona de los **merenderos**, que es otro modelo con un campo homónimo.

## Decisiones tomadas

- **El catálogo es nacional y hubo que acotarlo.** `/configuracion/localidades/` tiene **8779 localidades en 2109 municipios** de todo el país —lo comparte el domicilio de los ciudadanos—, de las cuales **778 son de Chaco, en 79 municipios**. Ofrecer el catálogo entero habría dejado elegir una localidad de Buenos Aires para un relevamiento de Chaco.
- **El recorte se resuelve por nombre de provincia, no por id.** Motivo: el id depende de cómo se cargó el catálogo en cada ambiente, y un id fijo en el código se rompe en el próximo. Vive en un solo lugar (`PROVINCIA_OPERATIVA`), que es lo único a tocar si algún día el sistema atendiera más de una provincia.
- **Se guarda el nombre de la localidad; el municipio solo filtra y no se persiste.** Motivo: es lo pedido —el valor es la localidad— y es lo que permite no migrar. Consecuencia asumida abajo, en Base de datos.
- **El selector de Localidad se renderiza vacío y se llena por AJAX.** Motivo: mandar las 778 opciones en cada carga del listado y del detalle de convocatoria es peso muerto en dos pantallas que ya son pesadas. Cuando el formulario vuelve con errores sí se repueblan las del municipio elegido, o el operador perdería lo que había seleccionado.
- **La validación no usa las opciones renderizadas sino el catálogo completo de Chaco**, más el cruce de que la localidad pertenezca al municipio elegido. Motivo: el select vacío es comodidad de carga, no un control; un POST armado a mano tiene que chocar contra el servidor igual.
- **Se reusó el endpoint del domicilio del ciudadano** (`/ajax/load-localidades/`) en lugar de escribir uno nuevo. Motivo: hace exactamente esto y ya está probado; el municipio que recibe ya viene acotado desde el formulario.
- **No se tocó el rótulo «Zona» de los listados ni el texto que viaja a Mobile.** Motivo: `zona` sigue siendo el mismo string; la APK instalada no se entera del cambio.

## Implementación

- El modal **Nuevo relevamiento** —el del detalle de convocatoria y el del listado— y el alta de página completa muestran **Municipio** y **Localidad** en lugar del campo de texto.
- Al elegir un municipio se cargan sus localidades; mientras no haya municipio, el segundo selector dice «Elegí primero el municipio».
- Si el municipio no tiene localidades cargadas, el selector lo dice en lugar de quedar mudo.
- Guardar deja en el relevamiento el **nombre de la localidad**, que es lo que siguen mostrando el listado, el detalle, la exportación y la app de campo.

## Archivos

- `core/selectors/geografia.py`
- `core/selectors/__init__.py`
- `programas/forms.py`
- `programas/templates/programas/becas/relevamientos/_cascada_localidad.html`
- `programas/templates/programas/becas/relevamientos/convocatoria_detail.html`
- `programas/templates/programas/becas/relevamientos/relevamiento_list.html`
- `programas/templates/programas/becas/relevamientos/relevamiento_form.html`
- `programas/tests/test_becas_relevamientos.py`

## Base de datos

**No requiere migración**, que es lo pedido. Dos consecuencias asumidas:

1. **Los nombres de localidad se repiten dentro de Chaco** —hay 5 «San Antonio» y 5 «El Palmar» en municipios distintos—, así que dos relevamientos de localidades diferentes pueden quedar con el mismo texto. Para el trabajo de campo alcanza; para reportar por localidad haría falta guardar la relación, que es lo que se descartó al no migrar.
2. **Los relevamientos ya cargados conservan su texto anterior** (en producción son dos: `Resistencia` y `Test`). No molesta porque **la zona solo se define al crear**: no existe edición de relevamiento —reprogramar toca fechas y reasignar toca territorial—, así que ningún selector tiene que reabrir un valor viejo.

## Validación

- Seis pruebas nuevas: el selector de municipios excluye otra provincia; se guarda el nombre de la localidad; se rechaza una localidad que no es del municipio elegido; se rechaza una de otra provincia; la zona sigue siendo obligatoria; y el select llega vacío pero se repuebla al volver con errores.
- Se actualizaron las once altas de las pruebas existentes, que mandaban la zona como texto libre.
- Módulo `test_becas_relevamientos` medido contra el estado previo en un worktree en HEAD: **12 errores antes y 12 después**, todos del entorno (Python 3.14 renderizando plantillas, ver Cambio 24). Ninguna prueba nueva o modificada falla.
- `manage.py check` sin observaciones y `makemigrations --check` sin cambios detectados, que confirma que no hubo migración. `scripts/design_audit.py --changed`: 0 errores (1 WARN preexistente de `outline:none` en un select que no se tocó). `scripts/compile_templates.py`: 302 plantillas, 0 errores.

## Puesta en marcha en el servidor

**Desplegado el 11/08/2026 en la release `8df9985` (`development@cfa5250`).** No necesitó nada más que el deploy: sin migración, sin cron y sin variables.

El riesgo a verificar era que el ambiente tuviera cargado el catálogo con la provincia escrita `Chaco` —si estuviera vacío o con otro nombre, el selector de municipios aparece vacío y no se puede crear un relevamiento—. Verificado contra producción llamando a los selectores desplegados: **79 municipios y 778 localidades**. `/health/` y el login en 200, nginx reiniciado después de recrear `web` y `websocket`.

Ese chequeo hay que repetirlo en cualquier ambiente nuevo, porque el catálogo se carga con `load_initial_data` y no viaja con el deploy.

## Pendientes / a definir

- **La palabra «zona» quedó con dos sentidos.** El campo ahora es una localidad, pero la columna de los listados y el campo que viaja a Mobile se siguen llamando «Zona». Renombrarlos es cosmético y arrastra la APK, así que se dejó.
- **La API le manda a Mobile dos localidades distintas**: `zona` (esta, donde trabaja el territorial) y `localidad` (el nombre del subsegmento, del Cambio 19). No se pisan, pero conviene decidir cuál mostrar cuando se toque la app.
- **Si más adelante se quiere reportar por localidad**, hay que guardar la relación y no el texto. Es la misma decisión que el Cambio 9 dejó abierta.
- **No hay pantalla de edición de la zona.** Si alguna vez se agrega, el formulario tiene que resolver el texto guardado hacia los dos selectores, y ahí sí molesta la ambigüedad de los nombres repetidos.

## Reversión

Revertir los archivos listados. No hay migración que deshacer ni datos que se pierdan: los relevamientos creados con el selector quedan con un texto de zona perfectamente válido para el formulario anterior.

## Historial

No aplica: entrada nueva. Se relaciona con el **Cambio 9**, que había dejado abierta la fuente oficial del catálogo de localidades, y con el **Cambio 19**, que expone la localidad del subsegmento a Mobile.

# Cambio 26 — El subsegmento es obligatorio para el Coordinador Regional

🟡 **HECHO — 11/08/2026 · PENDIENTE DE DESPLIEGUE**

| | |
|---|---|
| **Programa / módulo** | Becas — convocatorias |
| **Etiquetas** | `#convocatorias` `#rbac` `#ui` |
| **Solicitante** | PM. Salió del análisis general de Becas pedido el 11/08/2026; el pendiente estaba anotado desde el Cambio 18 |
| **Fecha del pedido** | 11/08/2026 |
| **Issue / épica** | Sin issue |
| **Partes afectadas** | Backoffice |
| **Migración** | No requiere |

## Pedido original

> «Perfecto el error detectado, vamos con el cambio: si sos Becas — Coordinador Regional, el campo Subsegmento [es obligatorio].»

## El problema

El alcance del Coordinador Regional se define **por subsegmento**: `convocatorias_visibles` le devuelve solo las de los subsegmentos que tiene a cargo. Pero el campo Subsegmento era opcional para todos, y el rol tiene `becas.convocatoria.crear`.

La secuencia era: creaba una convocatoria sin subsegmento, el sistema la guardaba sin quejarse, redirigía al listado **y la convocatoria no estaba ahí**. Quedaba a nivel segmento, es decir fuera de su propio alcance. No se perdía —un Administrador la ve, porque su alcance es el segmento— pero para quien la creó desaparecía, que es la forma más confusa posible de fallar.

## Alcance acordado

- El subsegmento pasa a ser obligatorio **solo** cuando quien opera es Coordinador Regional.
- Para el resto de los roles sigue siendo opcional: una convocatoria a nivel segmento es legítima y el Administrador la ve igual.
- Queda afuera arreglar las convocatorias sin subsegmento que ya existan.

## Decisiones tomadas

- **Se exige el dato en vez de ampliarle la visibilidad.** La alternativa era que `convocatorias_visibles` le mostrara también las del segmento que contiene su subsegmento. Se descartó: le haría ver las convocatorias de sus pares del mismo segmento, que es exactamente lo que el rol separa (ver Cambio 18, «no puede operar el subsegmento de un par»).
- **La obligatoriedad depende del operador, no del formulario.** El form recibe ahora `operador`, igual que `RelevamientoForm`, y decide con `es_coordinador_regional_becas`. Motivo: es la misma función que define el alcance, así que la regla y el alcance no pueden quedar desalineados.
- **El mensaje explica la consecuencia, no la regla.** Dice «una convocatoria a nivel segmento queda fuera de tu alcance y no la verías en tu listado» en lugar de «este campo es obligatorio». Motivo: el operador no tiene por qué saber cómo está modelado su alcance, pero sí necesita entender por qué se lo piden.
- **El asterisco se dibuja según `field.required`** en las tres pantallas, en vez de escribirlo a mano. Motivo: si mañana la regla cambia, no quedan asteriscos mintiendo.

## Implementación

- Al Coordinador Regional el campo Subsegmento le aparece con asterisco y no puede guardar sin elegirlo, en las tres entradas: el modal del listado, el modal del detalle y la pantalla completa de alta/edición.
- Los otros roles no ven ningún cambio.
- Combinado con la corrección del endpoint del 11/08 (Cambio 18), el desplegable solo le ofrece sus propios subsegmentos: ahora está obligado a elegir y solo puede elegir lo suyo.

## Archivos

- `programas/forms.py`
- `programas/views/relevamientos.py`
- `programas/templates/programas/becas/relevamientos/convocatoria_list.html`
- `programas/templates/programas/becas/relevamientos/convocatoria_detail.html`
- `programas/templates/programas/becas/relevamientos/convocatoria_form.html`
- `programas/tests/test_coordinador_regional.py`

## Base de datos

No requiere migración.

**Convocatorias ya existentes sin subsegmento:** no se tocan. En producción hay una (la del segmento «Chaco Olímpico ley 7353», que no tiene subsegmentos), creada por un Administrador y visible para él, así que no hay nada que reparar hoy. Si en algún momento aparece una creada por un Regional, un Administrador puede editarla y asignarle el subsegmento.

## Validación

- Cinco pruebas nuevas: el Regional no puede crear sin subsegmento y el error nombra la consecuencia; con su subsegmento crea y la convocatoria le queda visible; no puede usar el subsegmento de un par; para el Administrador el campo sigue siendo opcional; y `required` solo se activa para el Regional, que es de lo que depende el asterisco del template.
- Módulo `test_coordinador_regional` completo: **20 pruebas, todas en verde.** Son de formulario y no de vista, por la limitación de entorno del Cambio 24.
- `manage.py check` sin observaciones y sin migraciones detectadas. `scripts/design_audit.py --changed`: 0 errores (1 WARN preexistente de `outline:none` en un select que no se tocó). `scripts/compile_templates.py`: 302 plantillas, 0 errores.

## Puesta en marcha en el servidor

Pendiente de despliegue. No necesita nada más que el deploy.

Para verificarlo después: entrar con un Coordinador Regional, intentar crear una convocatoria sin subsegmento y confirmar que el formulario lo frena con el mensaje; después crearla con el subsegmento y confirmar que **aparece en su listado**, que es el síntoma que originó el cambio.

## Pendientes / a definir

- **El Referente y el Coordinador del segmento no se revisaron con esta lupa.** Su alcance es por segmento, así que el problema no se les aplica, pero nadie verificó si tienen un caso equivalente.
- Sigue abierto lo del Cambio 18 sobre nombres: el rol se llama Coordinador Regional y la UI de subsegmentos lo llama «Referente».

## Reversión

Revertir los seis archivos. Sin migración y sin datos que se pierdan: las convocatorias creadas con la regla activa tienen subsegmento, que es válido para el formulario anterior.

## Historial

No aplica: entrada nueva. Cierra el «Pendiente detectado» que había quedado anotado en el **Cambio 18**.

# Verificaciones generales pendientes antes de desplegar

- Ejecutar la suite relevante sin una base de test reutilizada contaminada.
- Verificar en la base de test que no existan roles con categoría `Becas`.
- Aplicar `users.0012_profile_datos_personales` primero en test.
- Aplicar `users.0013_profile_backoffice_session_key` en test.
- Aplicar `programas.0037_pausas_operativas` en test.
- Aplicar `users.0014_coordinador_gestiona_territoriales` en test y ejecutar `seed_becas`.
- Probar alta y edición de usuarios con y sin DNI.
- Confirmar que los administradores de programa conservan su alcance.
- Probar login recordado en el dominio real de test.
- Crear commits identificables antes de continuar con un despliegue.

# Cómo continuar este registro

La estructura de cada entrada nueva está definida en **[Plantilla obligatoria de cada entrada](#plantilla-obligatoria-de-cada-entrada)**, al comienzo del archivo. El cierre de un desarrollo son cuatro pasos:

1. Agregar la entrada al final del archivo, con la plantilla completa.
2. Sumar su fila al **Índice**, con programa, **etiquetas**, solicitante, fecha y estado.
3. Si modificó algo ya registrado, agregar la sección **Historial** a la entrada afectada, sin borrar lo anterior.
4. Correr `scripts/requerimientos.py --check`: verifica que la entrada y el índice coincidan y que las etiquetas existan en el vocabulario. Tiene que dar OK.

La regla, el motivo de cada campo y la mitad de lectura —qué consultar **antes** de escribir código— están en **[Regla de oro](#regla-de-oro)** y en **[Cómo leerlo sin leerlo entero](#cómo-leerlo-sin-leerlo-entero)**.
