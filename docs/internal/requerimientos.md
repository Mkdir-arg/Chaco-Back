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
| 26 | Subsegmento obligatorio para el Coordinador Regional | Becas / convocatorias | `#convocatorias` `#rbac` `#ui` | PM — surgió del análisis general de Becas del 11/08 | 11/08/2026 | 🟢 **Hecho** | No |
| 27 | El release lleva el pipeline de ECOM | Transversal / infraestructura | `#infra` `#mobile` | ECOM — mensaje al PM sobre el entorno nuevo con CI/CD | 11/08/2026 | 🟢 **Hecho** | No |
| 27.1 | Plantilla de variables y guía de configuración de entornos | Transversal / infraestructura | `#infra` `#correo` `#siis` | PM — para responderle a ECOM qué configurar sin entregar secretos | 11/08/2026 | 🟢 **Hecho** | No |
| 28 | Retirar el superusuario con credenciales en el código | Transversal / seguridad | `#infra` `#usuarios` `#sesion` | PM — surgió al revisar qué crea el bootstrap | 11/08/2026 | 🟡 **Hecho — falta cambiar la contraseña del `admin` ya creado** | No |
| 29 | El bootstrap unificado en `seed_datos_base` | Transversal / infraestructura | `#infra` `#rbac` `#datos` | PM — vio que en el testing de ECOM faltaban roles de Becas | 11/08/2026 | 🟢 **Hecho** | No |
| 30 | La guía cubre el despliegue en Kubernetes desde cero | Transversal / infraestructura | `#infra` `#siis` | PM — pidió el repaso final de la guía para setear el sistema desde cero en Kubernetes | 11/08/2026 | 🟢 **Hecho** | No |
| 31 | La imagen autosuficiente para Kubernetes | Transversal / infraestructura | `#infra` `#relevamientos` `#ui` | PM — «que quede para levantarse en Kubernetes en todos los aspectos» | 11/08/2026 | 🟡 **Hecho — pendiente de despliegue** | No |
| 32 | Programas (SIIS) por encima de los segmentos | Becas / estructura | `#siis` `#convocatorias` `#requisitos` `#pausas` `#ui` | PM — pedido directo en sesión de trabajo | 13/08/2026 | 🟢 **Hecho** | `programas.0045` |
| 33 | Probar por qué SIIS no trae datos | Becas / SIIS | `#siis` `#infra` | PM — «quiero que pruebes la integración con SIIS, porque no me está trayendo datos» | 18/08/2026 | 🟢 **Hecho — diagnóstico y comando de verificación** | No |
| 34 | Prevalidación SIIS al aprobar o rechazar formularios | Becas / revisión | `#siis` `#rbac` `#cupos` | Análisis #72 y revisión del PR #233 | 18/08/2026 | 🟢 **Hecho sobre el contrato vigente** | No |
| 35 | El login del backoffice muestra la contraseña con un botón ojo | Transversal / sesión | `#sesion` `#ui` | PM — mejora transversal aprobada el 14/08/2026, sin análisis | 14/08/2026 | 🟢 **Hecho** | No |
| 36 | El diseño de Dispositivos es todo lo contrario a lo que tiene que ser | Dispositivos | `#ui` | PM — pedido directo en sesión de trabajo | 19/08/2026 | 🟡 **Parcial — badges y solapas hechos; 4 hallazgos abiertos** | No |
| 37 | Credenciales por correo: clave provisoria al alta y recupero desde el login | Transversal / usuarios | `#usuarios` `#correo` `#sesion` `#infra` | PM — definiciones del 14/08/2026 (análisis #236) y credenciales SMTP entregadas el 20/08/2026 | 14/08/2026 | 🟡 **Parcial — implementado; falta envío real y aprobación de textos** | `users.0022` |
| 38 | Cerrar sesión da error 405 después de actualizar Django | Transversal / sesión | `#sesion` `#infra` `#ui` | PM — reportó el 405 al entrar a `/logout` | 20/08/2026 | 🟢 **Hecho** | No |
| 39 | En el login aparece el logo de Nodo en lugar del del Chaco | Transversal / marca | `#ui` `#sesion` `#infra` | PM — vio la marca del proveedor en la pantalla de acceso | 21/08/2026 | 🟢 **Hecho** | No |
| 40 | Formulario público de autocompletado: relevamientos con link de inscripción | Becas · Portal | `#relevamientos` `#datos` `#rbac` `#correo` `#ui` | Programa de Becas, vía PM — sesión de análisis del 21/08/2026 (análisis #289) | 21/08/2026 | 🟡 **Hecho — pendiente de merge y despliegue (PRs #301–#304)** | `programas.0049` + `programas.0050` |

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

## Historial

**20/08/2026 — el criterio «no se envían contraseñas en texto plano» quedó revertido.**
Esta entrada registró que la invitación llevaba un **enlace temporal** para
establecer la contraseña, y explícitamente que no viajaban claves en texto plano.
El cliente pidió lo contrario el 14/08/2026 (análisis #236): ahora el correo de alta
lleva el nombre de usuario y una **clave provisoria**. La mitigación acordada es que
el primer ingreso obliga a cambiarla, así que la clave enviada sirve una sola vez.
El detalle, el motivo y la implementación están en el **Cambio 37**, que también
reemplaza `users/services/invitations.py` por `users/services/correo.py` y cambia el
criterio de activación del SMTP. Lo demás de esta entrada sigue vigente: la tabla de
variables pedidas a ECOM y el comportamiento ante correo faltante o envío fallido.

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

🟢 **HECHO — 11/08/2026**

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

**Desplegado el 11/08/2026 en la release `96ca49b` (`development@7d946c5`).** No necesitó nada más que el deploy. Verificado: `/health/` y el login en 200 y el código horneado en el contenedor.

El primer intento de despliegue se cortó por una caída de VPN antes de aplicar el `git pull`; el servidor quedó intacto en la release anterior y se retomó desde ahí sin consecuencias.

Queda la verificación funcional: entrar con un Coordinador Regional, intentar crear una convocatoria sin subsegmento y confirmar que el formulario lo frena con el mensaje; después crearla con el subsegmento y confirmar que **aparece en su listado**, que es el síntoma que originó el cambio. Al 11/08 hay tres usuarios con ese rol en producción.

## Pendientes / a definir

- **El Referente y el Coordinador del segmento no se revisaron con esta lupa.** Su alcance es por segmento, así que el problema no se les aplica, pero nadie verificó si tienen un caso equivalente.
- Sigue abierto lo del Cambio 18 sobre nombres: el rol se llama Coordinador Regional y la UI de subsegmentos lo llama «Referente».

## Reversión

Revertir los seis archivos. Sin migración y sin datos que se pierdan: las convocatorias creadas con la regla activa tienen subsegmento, que es válido para el formulario anterior.

## Historial

No aplica: entrada nueva. Cierra el «Pendiente detectado» que había quedado anotado en el **Cambio 18**.

# Cambio 27 — El release lleva el pipeline de ECOM

🟢 **HECHO — 11/08/2026**

| | |
|---|---|
| **Programa / módulo** | Transversal — infraestructura y despliegue |
| **Etiquetas** | `#infra` `#mobile` |
| **Solicitante** | ECOM, por mensaje al PM sobre el entorno nuevo; el PM pidió incorporar el archivo |
| **Fecha del pedido** | 11/08/2026 |
| **Issue / épica** | Sin issue |
| **Partes afectadas** | Infra/ECOM |
| **Migración** | No requiere |

## Pedido original

ECOM informó que `https://datanach.ecomdev.ar/` es un entorno nuevo con CI/CD: al pushear a la rama `test` de su GitLab se despliega solo, sin coordinar con devops **mientras el cambio sea de código fuente y no de configuración**; los logs de los pods se ven en ArgoCD con usuario de dominio y VPN; el entorno es **testing, no QA**, y para armar QA piden que confirmemos si se puede usar la rama `main`; y la URL nueva está más expuesta a internet a propósito, **para que la app móvil pueda conectarse sin bloqueos**.

Sobre eso, el PM: «copiemos el `.gitlab-ci.yml`».

## Lo que se descubrió al revisar su GitLab

- Su repositorio tiene **dos ramas**: `main`, que actualizamos ese mismo día hasta `96ca49b`, y `test`, en `888c121` del **21/07/2026**, con autor **`argocd`** y mensaje `[ci skip]`.
- El pipeline construye la imagen del `Dockerfile` de la raíz y la sube al registry on-prem con **el nombre de la rama en la ruta** (`…/datanach/<rama>:latest`), y corre solo para `test` y `main`. Son dos imágenes distintas y las despliega ArgoCD.
- **`main` no traía `.gitlab-ci.yml`.** GitLab lee ese archivo del commit que recibe, así que el espejo del 11/08 actualizó la rama **sin construir ninguna imagen**. Queda por confirmar en su pestaña *Pipelines*, pero es lo que explica el mecanismo.
- **El entorno de testing corre código del 21 de julio**: la rama `test` no tiene `users.0020` ni `programas.0043`, o sea que le falta todo agosto —Coordinador Regional, vigencia de SIIS, permisos, y los cambios 25 y 26—. Es la razón por la que lo que se ve ahí no coincide con lo probado.
- El `Dockerfile` de la raíz **es idéntico al nuestro** salvo un BOM y el salto de línea final, así que su build usa la misma receta.

## Decisiones tomadas

- **Se copia el archivo tal cual, sin agregarle ni un comentario.** Motivo: el dueño del pipeline es ECOM. Cualquier agregado nuestro genera un diff espurio la próxima vez que ellos lo cambien y deja en duda cuál de las dos versiones manda. Se verificó que el blob quede idéntico al suyo (`a9541b9`).
- **Se fija `text eol=lf` en `.gitattributes`.** Motivo: al clonar su repo con `core.autocrlf=true` el archivo aparece con CRLF, pero eso es del checkout y no del contenido versionado. Sin fijarlo, la copia se guardaba con CRLF y el blob dejaba de coincidir con el suyo.
- **`.gitlab-ci.yml` y el `Dockerfile` de la raíz entran en la lista de archivos requeridos del guard.** Motivo: el modo de falla que acabamos de ver es silencioso —la rama se actualiza, no hay error en ninguna parte y no se construye nada—. Con el guard, un release sin esos archivos falla en vez de publicarse.
- **No se toca la rama `test` por ahora.** Motivo: tiene commits de su automatización que no están en nuestro historial, así que está divergida: un push normal se rechaza y forzarlo les borraría esos commits y su copia del pipeline, rompiendo el CI/CD que acaban de armar. Se acuerda con ellos quién la actualiza.

## Implementación

- El repositorio incorpora `.gitlab-ci.yml` en la raíz, idéntico al de ECOM, y por no estar excluido viaja en cada release.
- El guard del workflow verifica que ese archivo y el `Dockerfile` de la raíz estén presentes en el árbol publicado.
- `docs/internal/branching.md` documenta el mecanismo completo: qué construye el pipeline, qué rama alimenta cada entorno, por qué la rama `test` no es nuestra y qué diferencia hay entre un cambio de código y uno de configuración.

## Archivos

- `.gitlab-ci.yml`
- `.gitattributes`
- `.github/workflows/publish-main.yml`
- `docs/internal/branching.md`

## Base de datos

No requiere migración.

## Validación

- El blob de nuestro archivo coincide con el de ECOM (`a9541b9`), verificado con `git rev-parse` contra un clon superficial de su rama `test`.
- `git ls-files --eol` confirma `i/lf w/lf` con el atributo aplicado.
- `manage.py check` sin observaciones. No toca código de la aplicación.
- La verificación de fondo —que el pipeline efectivamente construya al recibir la rama— **solo se puede hacer con el próximo espejo**, mirando *Pipelines* en su GitLab.

## Puesta en marcha en el servidor

No aplica a `icore-srv`: nuestro despliegue sigue siendo manual y no usa este pipeline. El efecto es del lado de ECOM.

### Lo que pasó al espejar, el 11/08/2026

- **`main` quedó en `23c70da`** y, con el pipeline ya incluido, **disparó el primer build real**. Confirmado: antes las ramas se actualizaban sin construir nada.
- **Ese build falló, y no por el código.** Los jobs `#31692` (main) y `#31697` (test) murieron con `Cannot connect to the Docker daemon at tcp://docker:2375`: el servicio `docker:dind` no quedaba operativo. El build **no llegó a leer el `Dockerfile`**: el checkout y el login al registry salieron bien.

  **La causa era TLS, y la resolvió ECOM el mismo día** con una línea en el pipeline: `command: ["--tls=false"]` en el servicio dind (commit `0f3d3ae`, autor `matiasgon`). Las imágenes recientes de `docker:dind` habilitan TLS por defecto y escuchan en 2376, así que el daemon nunca quedaba disponible en el 2375 que busca `DOCKER_HOST`; la variable `DOCKER_TLS_CERTDIR: ""` por sí sola no alcanza.

  Vale dejar asentado el diagnóstico equivocado, para no repetirlo: se había atribuido al runner —`privileged` faltante, contenedores de servicio huérfanos y las dos etiquetas `docker:dind` / `docker:latest` resolviendo a la misma imagen local—. Esos síntomas estaban en el log y son reales, pero eran ruido: el `FATAL: No HOST or PORT found` del health check y las quejas de iptables aparecen igual cuando el problema es solo que el daemon escucha en otro puerto.
- **`test` quedó en `3e2e1ac`, sin forzar.** La rama estaba divergida y un push normal se rechaza, pero en vez de `--force` se hizo que nuestro contenido descienda del suyo: un commit de merge con el **árbol idéntico al de `main`** y padres `[23c70da, 888c121]`. Entra como avance directo y **conserva el commit de `argocd`**. El procedimiento quedó documentado en [branching.md](branching.md), incluido el rodeo del clon superficial —su servidor no puede servir ese commit por `fetch`, corta con HTTP 500—.
- **Con el arreglo del TLS el circuito quedó andando.** Verificado desde afuera: la ruta `/establecer-contrasena/<uid>/<token>/`, que se agregó el 07/08, responde en `datanach.ecomdev.ar`; con el código del 21 de julio habría dado 404. O sea que el pipeline construyó y ArgoCD desplegó.
- **Segundo espejo del día**, ya con el orden nuevo: `test` en `e681216` y `main` en `3b72e15`, que le llevan a ECOM la plantilla `.env.qa.example` (ver 27.1). El chequeo previo confirmó que su rama no tenía nada de contenido propio pendiente.
- **El comando `/pushGitLabecom` se rehízo con todo esto**: espeja `test` primero y `main` después, y arranca comprobando si `test` tiene commits de ellos que no tengamos —el paso que hoy evitó, a mano, revertirles el arreglo del pipeline—. Incluye el procedimiento sin reescritura, el rodeo del clon superficial y las fallas conocidas con su causa.

Antes se había verificado que sobrescribir `test` no habría perdido contenido de ellos —su `.gitlab-ci.yml` es el mismo blob que el nuestro y los otros cinco archivos que diferían eran restos de una estructura vieja de nuestro repo—, pero el camino sin reescritura era mejor y era posible.

## Pendientes / a definir

Para ECOM:

- QA: ¿va a tomar `…/main:latest`? ¿Con qué URL?
- ¿Cómo quieren que manejemos `main`: la actualizamos en cada release nuestra, o solo cuando avisemos que hay una versión estable? Ahora cada push construye.
- ¿Las variables de entorno de testing están cargadas (base, SIIS, correo)?
- Accesos a ArgoCD con usuario de dominio.
- El sync periódico de SIIS en Kubernetes sería un CronJob, o sea configuración: ¿lo definen ellos?

De nuestro lado:

- **La app móvil apunta al entorno viejo.** Si la URL nueva existe para que la APK conecte sin bloqueos, hay que cambiar la URL base en el repositorio de la app y regenerar el APK. Vive en otro repo (`Chaco-mobile`), así que no entra en este cambio.

## Reversión

Borrar `.gitlab-ci.yml`, su línea en `.gitattributes` y los dos nombres agregados al guard. Sin efecto sobre la aplicación: se vuelve al estado en que el release no lleva pipeline y las ramas espejadas se actualizan sin construir imagen.

## Historial

No aplica: entrada nueva.

## 27.1 Plantilla de variables y guía de configuración de entornos

🟢 **HECHO — 11/08/2026**

### Pedido original

Al montar ECOM sus entornos, el PM preguntó si había que pasarles las variables de entorno del servidor productivo. La respuesta fue que no —los valores no se comparten entre entornos— y el pedido derivó en dejar por escrito **qué** hay que configurar y **quién** provee cada valor.

### Decisiones tomadas

- **No se entregan los valores de producción, y esto queda escrito.** Motivos, en orden de gravedad: una `DJANGO_SECRET_KEY` compartida hace que una sesión firmada en un entorno valga en el otro; unas credenciales de base compartidas ponen los datos reales al alcance de una prueba; y ante una filtración no habría forma de saber de qué entorno salió.
- **Lo que se entrega es una plantilla, no un archivo lleno.** `.env.qa.example` no contiene ni un valor real y viaja en el release, así que ECOM la tiene en el repositorio espejado sin que nadie mande nada por chat.
- **Cada variable dice quién la provee.** Es la parte que faltaba: la lista de nombres ya existía en `.env.local.example`, pero no que las credenciales de **SIIS y Personas las emite ECOM** —el pedido va al revés de lo que parecía— ni que RENAPER puede quedar en modo de prueba para no bloquear un QA.
- **Se documentaron las dos causas típicas de «desplegué y no anda»**: el dominio ausente de `DJANGO_ALLOWED_HOSTS` / `DJANGO_CSRF_TRUSTED_ORIGINS`, que devuelve 400 en todo, y la base vacía sin sembrado, que deja el sistema sin roles ni programas y por lo tanto sin poder iniciar sesión.

### Implementación

- `.env.qa.example`: plantilla comentada por grupos —Django, URL del entorno, base, Redis, arranque, SIIS, Personas, RENAPER, correo, sesión, observabilidad—, con marca de obligatoriedad y de origen del valor.
- `processes.md` suma dos secciones: **Entornos**, con la tabla de los cuatro y quién despliega cada uno, y **Variables de entorno**, con la regla de no compartir valores, la tabla de quién provee qué y las dos trampas del entorno nuevo.
- **La guía pública de despliegue se rehízo** (`docs/client/versiones/version-001.md`, publicada en GitHub Pages). Estaba de julio y arrastraba **un error que impedía levantar el sistema**: su plantilla listaba solo las variables `MYSQL_*` —las del contenedor de base— y **omitía las `DATABASE_*`, que son las que lee la aplicación**. Quien la siguiera al pie levantaba MySQL y la app no podía conectarse, con los contenedores igualmente en *healthy*. Además le faltaban SIIS, Personas, correo, Redis, `DOMINIO` y el sembrado inicial; apuntaba al nombre viejo del repositorio; y listaba una sola tarea programada de las cuatro que existen.

  Ahora incluye el juego completo de variables con quién provee cada valor, la advertencia de que los dos bloques de base tienen que coincidir, las dos causas de «desplegué y no anda», las cuatro tareas programadas con qué pasa si no corren, los pasos de verificación y una nota sobre los ambientes de ECOM, que no se despliegan con esa guía.

### Archivos

- `.env.qa.example`
- `docs/internal/processes.md`
- `docs/client/versiones/version-001.md`

### Base de datos

No requiere migración.

### Validación

- `manage.py check` sin observaciones: no toca código.
- La plantilla se contrastó contra las variables que `config/settings.py` lee realmente, no contra el ejemplo anterior, y se verificó que ningún campo sensible quedara con valor.
- `mkdocs build --strict` sin advertencias, que es lo que corre el workflow que publica la página.

### Pendientes / a definir

- Los valores concretos siguen siendo de ECOM: credenciales de SIIS y Personas para sus entornos, el SMTP y las de RENAPER. La plantilla no los reemplaza, solo dice qué falta.
- **La tabla de alcance y las horas de la página pública siguen al 10/07/2026.** No se tocaron: son datos de PM y se actualizan con su propia información.

### Reversión

Borrar el archivo y las dos secciones de `processes.md`. Sin efecto sobre la aplicación.

### Historial

**11/08/2026, más tarde — la sección de despliegue de la guía pública se reescribió en tono técnico**, a pedido del PM («borrar el biri biri; técnico, claro y conciso»). Mismo contenido y mismos títulos —los nueve anclajes publicados se preservaron, verificado contra el build—, pero el cuerpo pasó de ~320 a ~180 líneas: fuera la prosa explicativa, los pasos como comandos con una línea de contexto, las advertencias largas comprimidas a bullets. No cambió ninguna decisión técnica; solo la redacción.

# Cambio 28 — Se retira el superusuario con credenciales escritas en el código

🟡 **HECHO — 11/08/2026 · FALTA CAMBIAR LA CONTRASEÑA DEL `admin` YA CREADO**

| | |
|---|---|
| **Programa / módulo** | Transversal — seguridad y despliegue |
| **Etiquetas** | `#infra` `#usuarios` `#sesion` |
| **Solicitante** | PM. Salió de preguntar qué usuarios crea el bootstrap al levantar un ambiente |
| **Fecha del pedido** | 11/08/2026 |
| **Issue / épica** | Sin issue |
| **Partes afectadas** | Backoffice · Infra/ECOM |
| **Migración** | No requiere |

## Pedido original

> «¿Podemos borrar el comando que crea el superadmin hardcodeado y poner en la documentación el comando que tienen que ejecutar para crearlo, a definición de ellos el nombre y usuario?»

## El problema

El comando `crear_superadmin` creaba el superusuario con **usuario y contraseña escritos en el código** (`admin` y una contraseña conocida del equipo). Servía para desarrollo local, pero **estaba en el default del bootstrap del entrypoint**, así que corría en cualquier ambiente donde la variable `LOCAL_BOOTSTRAP_COMMANDS` no estuviera definida — que es exactamente el caso de nuestro servidor productivo.

Tres agravantes:

- En producción **el usuario existe**: se creó por ese default.
- El **código está en el repositorio espejado a ECOM**, así que la contraseña viaja con él.
- El entorno de testing de ECOM está **deliberadamente más expuesto a internet** para que llegue la app móvil, así que ahí el mismo bootstrap habría dejado un superusuario con credencial pública alcanzable desde afuera.

## Decisiones tomadas

- **Se borra el comando en vez de parametrizarlo.** Motivo: cualquier variante que lo deje creando usuarios en el arranque vuelve a poner una credencial por defecto en un ambiente servido. Sin comando, la única forma es que alguien decida las credenciales.
- **La alternativa documentada es `createsuperuser`, el de Django.** Motivo: ya existe, es interactivo por defecto —así la contraseña no queda en el historial del shell— y acepta `DJANGO_SUPERUSER_*` con `--noinput` para los casos que necesitan script.
- **Se verificó que un superusuario creado así no queda incompleto.** El `Profile` —que usa la sesión única del Cambio 14— se crea solo con `get_or_create` en el login y en el middleware, así que no hace falta ningún paso extra.
- **Se corrigió el default del entrypoint**, que era `crear_superadmin seed_datos_base crear_programas`. Dejarlo apuntando a un comando borrado **habría dejado el contenedor sin arrancar** en el próximo deploy: el script corre con `set -eu`. Se comprobó además que `.env.production` del servidor no define `LOCAL_BOOTSTRAP_COMMANDS`, o sea que dependía de ese default.
- **El sembrado sigue creando roles y programas, y ningún usuario.** Se confirmó leyendo los tres comandos: `seed_rbac`, `crear_programas` y `seed_becas` solo tocan `Group` y `Programa`.

## Implementación

- Se eliminó `users/management/commands/crear_superadmin.py`.
- El default del bootstrap del entrypoint pasó a `seed_datos_base crear_programas`, y el de `docker-compose.yml` a `seed_rbac crear_programas`.
- Se retiró de `docker-compose.prod.yml` la bandera `RUN_CREAR_SUPERADMIN`, que además **no la leía nadie**: era configuración muerta.
- Las dos plantillas de variables aclaran que el bootstrap no crea usuarios y muestran el comando.
- La guía interna (`setup.md`, `processes.md`) y la **guía pública** documentan cómo crear el superusuario. En la pública es un paso propio, el 5, con la variante interactiva y la de script, la advertencia de elegir contraseña propia y la aclaración de que ese usuario es solo la puerta de entrada: los usuarios de trabajo se dan de alta desde el sistema.
- La sección **«Actualizar a una versión nueva»** de la guía pública avisa del cambio de comportamiento: un ambiente en marcha no se ve afectado, pero si se recrea la base hay que crear el usuario a mano, y **si el ambiente se sembró con una versión anterior tiene el `admin` con la contraseña conocida y hay que cambiarla** (con `changepassword` o desde el sistema). Es el lugar donde ECOM va a leerlo.

## Archivos

- `users/management/commands/crear_superadmin.py` (eliminado)
- `docker-entrypoint.sh`
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `.env.local.example`
- `.env.qa.example`
- `docs/internal/setup.md`
- `docs/internal/processes.md`
- `docs/client/versiones/version-001.md`

## Base de datos

No requiere migración. **Pero borrar el comando no cambia lo ya creado:** el usuario `admin` de producción sigue existiendo con su contraseña original.

## Validación

- `manage.py crear_superadmin` ya responde `Unknown command`.
- `manage.py check` sin observaciones y `mkdocs build --strict` sin advertencias.
- Se revisó que no quede ninguna referencia funcional al comando: las tres que restan son la prosa que explica por qué se retiró.
- Se verificó en el servidor que `.env.production` no define variables de bootstrap, de modo que el cambio de default es el que gobierna el próximo arranque.

## Puesta en marcha en el servidor

Sin acción en el deploy. **Lo que hay que hacer aparte y no es opcional: cambiarle la contraseña al `admin` de producción**, y avisarle a ECOM que haga lo mismo si algún ambiente suyo llegó a sembrarse con el comando viejo.

## Pendientes / a definir

- **Cambiar la contraseña del `admin` en producción.** Es lo único que cierra la exposición.
- **Avisar a ECOM**, por el mismo motivo, para testing y para QA cuando lo levanten.
- **El harness de E2E** entraba con ese usuario y contraseña en el Docker local. En un entorno local nuevo hay que crearlo a mano; la receta no interactiva quedó en `setup.md`.
- `RUN_CREAR_PROGRAMAS` de `docker-compose.prod.yml` **tampoco la lee nadie**. Se dejó por no mezclar, pero es configuración muerta y conviene retirarla.

## Reversión

Restaurar el archivo del comando y las líneas de bootstrap. No se recomienda: la reversión reintroduce la credencial en el código.

## Historial

No aplica: entrada nueva.

# Cambio 29 — El bootstrap unificado en `seed_datos_base`

🟢 **HECHO — 11/08/2026**

| | |
|---|---|
| **Programa / módulo** | Transversal — infraestructura y RBAC |
| **Etiquetas** | `#infra` `#rbac` `#datos` |
| **Solicitante** | PM. Vio en `datanach.ecomdev.ar/roles` que faltaban roles de Becas y preguntó si el ambiente se había levantado incompleto |
| **Fecha del pedido** | 11/08/2026 |
| **Issue / épica** | Sin issue |
| **Partes afectadas** | Backoffice · Infra/ECOM |
| **Migración** | No requiere |

## El síntoma

En el entorno de testing de ECOM la pantalla de Roles mostraba **tres de los cinco roles de Becas**: faltaban Coordinador Regional y Referente. El contador decía «3 de 12», mientras que nuestro productivo tiene 14 grupos — exactamente los dos que faltaban.

No era un arranque incompleto: era que **el sembrado de Becas no se estaba ejecutando en ese ambiente**, así que sus roles quedaron congelados en el estado en que se sembró la base, cuando Coordinador Regional (Cambio 18) y Referente (Cambio 17) todavía no existían.

## La causa

`seed_datos_base` es un **paraguas**: corre `seed_rbac` y `seed_becas`, crea los roles de menú y carga los catálogos base —sexo, día, mes y **localidades**— si las tablas están vacías. Es el default del bootstrap del entrypoint, y por eso nuestro productivo se mantiene al día sin que nadie corra nada.

Pero **las tres plantillas decían otra cosa**: `.env.local.example`, `.env.qa.example` y `docker-compose.yml` tenían `seed_rbac crear_programas`, sin `seed_becas`. Cualquier ambiente configurado siguiendo nuestra documentación quedaba con el desfasaje. Y `.env.qa.example` es el archivo que se le acababa de espejar a ECOM, así que el error se les estaba entregando servido.

## Decisiones tomadas

- **Los cuatro lugares dicen ahora `seed_datos_base crear_programas`.** Motivo: una sola forma de nombrar el sembrado. Tener el entrypoint diciendo una cosa y las plantillas otra es precisamente lo que produjo el desfasaje, y en silencio.
- **Se documentó que la lista no se recorta**, con el motivo: `seed_becas` **reemplaza** el conjunto de capacidades de cada rol, así que correrlo en cada arranque es lo que mantiene los roles alineados con el código. Recortarlo no rompe nada visible el primer día; el costo aparece meses después, cuando un rol nuevo no existe en un ambiente y nadie sabe por qué.
- **No se agrega `seed_becas` aparte.** Motivo: ya está adentro del paraguas, y listarlo dos veces invita a que alguien lo saque de un lado y lo deje en el otro.

## Beneficio lateral que decide el caso

`seed_datos_base` carga el catálogo de **localidades** si está vacío. Es la dependencia del selector Municipio/Localidad del Cambio 25: con esto, un ambiente nuevo la tiene sin intervención. Cierra el riesgo de puesta en marcha que esa entrada había dejado anotado.

## Implementación

- `.env.local.example`, `.env.qa.example` y `docker-compose.yml` pasaron a `seed_datos_base crear_programas`, con la explicación de qué incluye el paraguas.
- El docstring de `seed_datos_base` decía que `seed_becas` crea «3 roles de programa»: son cinco desde el Cambio 18. Corregido, con la advertencia de por qué correrlo en cada arranque.
- `processes.md` y la **guía pública** explican que la lista no se recorta y qué pasa si se recorta, con el caso de ECOM como ejemplo concreto.

## Archivos

- `.env.local.example`
- `.env.qa.example`
- `docker-compose.yml`
- `users/management/commands/seed_datos_base.py`
- `docs/internal/processes.md`
- `docs/client/versiones/version-001.md`

## Base de datos

No requiere migración. El sembrado es idempotente: crea lo que falta y actualiza capacidades, sin tocar usuarios ni datos.

## Validación

- `manage.py check` sin observaciones y `mkdocs build --strict` sin advertencias.
- Se verificó en el código que `seed_datos_base` llama a `seed_rbac` y `seed_becas` sin condición, y que `seed_becas` define los cinco roles.

## Puesta en marcha en el servidor

Sin acción en nuestro servidor: ya usaba el paraguas por el default del entrypoint. **En el entorno de ECOM hay que correr `seed_datos_base` (o `seed_becas`) una vez** para que aparezcan los dos roles que faltan; después, si su despliegue usa el bootstrap, se mantiene solo.

## Pendientes / a definir

- **Avisarle a ECOM** que corra el sembrado en testing, y que revise qué tiene configurado como bootstrap en Kubernetes: si lo recortaron, van a repetir el desfasaje.

## Reversión

Volver las tres líneas a `seed_rbac crear_programas`. No se recomienda: es reintroducir el desfasaje.

## Historial

No aplica: entrada nueva.

# Cambio 30 — La guía cubre el despliegue en Kubernetes desde cero

🟢 **HECHO — 11/08/2026**

| | |
|---|---|
| **Programa / módulo** | Transversal — infraestructura y despliegue |
| **Etiquetas** | `#infra` `#siis` |
| **Solicitante** | PM. Pidió el repaso final: si con lo publicado alguien puede setear el sistema desde cero en Kubernetes |
| **Fecha del pedido** | 11/08/2026 |
| **Issue / épica** | Sin issue |
| **Partes afectadas** | Infra/ECOM |
| **Migración** | No requiere |

## Pedido original

> «Último repaso: analizá si está todo bien armado como para setear el sistema desde cero con Kubernetes, si está todo bien explicado en la guía publicada y si no nos falta nada.»

## El análisis

La guía estaba completa **para la VM con Docker Compose**, pero el compose resuelve en silencio varias cosas que en Kubernetes hay que replicar a mano, y ninguna estaba escrita. Se revisó contra el código (`Dockerfile`, `docker-entrypoint.sh`, `docker-compose.prod.yml`, `config/settings_production.py`, `nginx.conf`), no contra memoria. Los ocho huecos:

1. **El entrypoint se saltea con `command`/`args`** (`exec "$@"` ante cualquier argumento): sin él no corren migraciones, estáticos ni sembrado, y el síntoma es silencioso. Es además la hipótesis más probable de los roles faltantes en el testing de ECOM (Cambio 29).
2. **Las variables del arranque tienen que ser variables de entorno reales del pod**: `RUN_*`, `LOCAL_BOOTSTRAP_COMMANDS`, `APP_RUNTIME` y `DJANGO_SETTINGS_MODULE` las lee el script o el proceso, no Django — un `.env.production` montado no alcanza para ellas.
3. **`DJANGO_SETTINGS_MODULE=config.settings_production` no estaba en la plantilla**, y es el modo endurecido: exige `ALLOWED_HOSTS` (falla al arrancar si falta), fuerza `DEBUG=False` y redirige a HTTPS.
4. **La redirección a HTTPS necesita `X-Forwarded-Proto: https` del ingress** (`SECURE_PROXY_SSL_HEADER` ya está en settings); sin ese encabezado, bucle de redirección infinito.
5. **`RUN_COLLECTSTATIC` no estaba en la plantilla** (el compose de producción lo setea aparte) y la imagen no trae servidor de estáticos: algo tiene que servir `/static/` y `/media/` — en la VM lo hace nginx desde un volumen compartido.
6. **`/media/` necesita almacenamiento persistente**: ahí viven los adjuntos que cargan los territoriales; sin volumen se pierden al reiniciar el pod.
7. **Websockets**: con `APP_RUNTIME=daphne` un solo proceso atiende HTTP y `/ws/`, pero el ingress tiene que dejar pasar `Upgrade`/`Connection`.
8. **Las tareas programadas son CronJob** en Kubernetes, y `sincronizar_programas_siis` nunca va en el arranque del pod (servicio externo).

Se verificó también desde afuera que el testing de ECOM **sí sirve los estáticos** (`/static/...css` responde 200), así que el punto 5 su plataforma ya lo resuelve; el punto 1 es el que les queda por confirmar en los logs del pod.

## Implementación

- La guía pública suma la sección **«Si el despliegue es en Kubernetes»** con los ocho puntos como checklist, incluido el diagnóstico por logs del punto 1 (qué líneas tienen que verse y cuál delata el salteo). La nota de ambientes automáticos apunta a esa sección.
- `.env.qa.example` incorpora `DJANGO_SETTINGS_MODULE` y `RUN_COLLECTSTATIC`, con la advertencia de que ese bloque va como variables reales del contenedor.
- `processes.md` suma la advertencia del entrypoint salteado, con el síntoma y el diagnóstico.

## Archivos

- `docs/client/versiones/version-001.md`
- `.env.qa.example`
- `docs/internal/processes.md`

## Base de datos

No requiere migración.

## Validación

- `mkdocs build --strict` sin advertencias (es lo que corre el workflow que publica).
- `scripts/requerimientos.py --check` en OK.
- La lista de diferencias se derivó leyendo los archivos reales del despliegue, y el punto de estáticos se contrastó contra el entorno vivo de ECOM.

## Puesta en marcha en el servidor

No aplica a `icore-srv`. Para ECOM es documentación: el único pedido activo que sale de acá es que **confirmen en los logs del pod si el entrypoint corre completo** (punto 1), porque de eso depende que migraciones y sembrado los haga el arranque o los tengan que orquestar ellos.

## Pendientes / a definir

- La confirmación de ECOM sobre cómo arranca su pod (entrypoint completo vs. `command` propio).
- Este release toca `.env.qa.example`, así que **conviene espejarlo a su GitLab** junto con el del Cambio 29, que tampoco se espejó todavía.

## Reversión

Revertir los tres archivos. Sin efecto sobre la aplicación.

## Historial

No aplica: entrada nueva. Completa la 27.1 (la guía) con lo específico de Kubernetes, y le da al Cambio 29 su hipótesis de causa raíz del lado de ECOM.

# Cambio 31 — La imagen autosuficiente para Kubernetes

🟡 **HECHO — 11/08/2026 · PENDIENTE DE DESPLIEGUE**

| | |
|---|---|
| **Programa / módulo** | Transversal — infraestructura y despliegue |
| **Etiquetas** | `#infra` `#relevamientos` `#ui` |
| **Solicitante** | PM: «hacé los cambios necesarios para que quede para levantarse en Kubernetes en todos los aspectos» |
| **Fecha del pedido** | 11/08/2026 |
| **Issue / épica** | Sin issue |
| **Partes afectadas** | Backoffice · Infra/ECOM |
| **Migración** | No requiere |

## Pedido original

El Cambio 30 documentó los huecos de Kubernetes; este los **resuelve en el código** para que la imagen no dependa de piezas externas que la plataforma tenga que inventar.

## Decisiones tomadas

- **Los estáticos los sirve la propia app (whitenoise), siempre.** Motivo: era el hueco más estructural — la imagen no traía servidor de estáticos y dependía del nginx de la VM. El middleware queda activo también en la VM porque es inerte ahí: nginx responde `/static/` antes de que la petición llegue a Django. Se eligió whitenoise por ser la solución estándar del ecosistema, sin proceso extra.
- **El storage de estáticos usa manifest también en `qa`, no solo en `prd`.** Motivo: estaba condicionado a `ENVIRONMENT == "prd"`, con lo cual un QA servía estáticos sin hash — distinto de producción justo en el ambiente que existe para parecerse a producción. Ahora `prd` y `qa` usan `CompressedManifestStaticFilesStorage` (manifest + precompresión).
- **`/media/` se sirve desde la app solo con `SERVE_MEDIA=True`.** Motivo: `django.views.static.serve` alcanza para la escala de QA pero no es un CDN; en la VM lo sirve nginx y el flag queda apagado. El límite queda explícito en vez de implícito.
- **`RUN_COLLECTSTATIC` pasa a valer `true` por defecto cuando `ENVIRONMENT` es `prd` o `qa`.** Motivo: sin el manifest cualquier template con `{% static %}` responde 500; que el default seguro dependa del tipo de ambiente elimina la variable que más fácil se olvida. En dev sigue apagado para no alargar cada arranque.
- **El entrypoint gana el modo one-shot `bootstrap`.** Motivo: si el manifiesto del pod define `command`/`args`, el entrypoint se saltea; con `args: ["bootstrap"]` un initContainer o Job corre migraciones + estáticos + sembrado y termina. Además, el aviso de «Comando personalizado detectado» ahora explica la consecuencia y la salida.
- **Se agregan manifiestos de referencia en `docker/k8s/`** (README, los cuatro CronJob, y el Deployment con initContainer y PVC de media). Motivo: viajan en el release —`docker/` no está excluido—, así que ECOM los tiene sin depender de la página. Son plantillas con `<IMAGEN>`/`<SECRET-ENV>`, no manifiestos listos: las decisiones de plataforma siguen siendo de ellos.

## Implementación

- `whitenoise==6.8.2` en requirements; middleware inmediatamente después de `SecurityMiddleware`; storage con manifest y precompresión en `prd`/`qa`.
- `SERVE_MEDIA` en settings y la ruta `/media/` en urls, activa solo con el flag.
- Entrypoint reestructurado: funciones primero, modo `bootstrap`, default de `collectstatic` por ambiente, aviso explicativo al saltearse.
- `docker/k8s/` con README, `cronjobs.yaml` y `bootstrap-initcontainer.yaml`.
- La plantilla y la guía pública actualizadas: los puntos de estáticos, media, bootstrap y CronJobs ahora dicen lo que la imagen hace sola y qué queda del lado de la plataforma.

## Archivos

- `requirements.txt`
- `config/settings.py`
- `config/urls.py`
- `docker-entrypoint.sh`
- `docker/k8s/README.md`
- `docker/k8s/cronjobs.yaml`
- `docker/k8s/bootstrap-initcontainer.yaml`
- `.env.qa.example`
- `docs/client/versiones/version-001.md`
- `docs/internal/processes.md`

## Base de datos

No requiere migración.

## Validación

- Sintaxis POSIX del entrypoint verificada (`sh -n`).
- `whitenoise==6.8.2` instalado en el venv y validados los imports del middleware y el storage.
- `manage.py check` sin observaciones con el middleware activo.
- Módulo de pruebas que renderiza el menú medido contra HEAD en un worktree: **2 errores antes y 2 después**, ambos el piso conocido de Python 3.14 — whitenoise no cambia el comportamiento de render.
- `mkdocs build --strict` sin advertencias y `scripts/requerimientos.py --check` en OK (ver commit).

## Puesta en marcha en el servidor

**Pendiente de despliegue en `icore-srv`** (rebuild de la imagen: cambia requirements). Sin migración y sin variables nuevas obligatorias: en la VM `SERVE_MEDIA` queda apagado y whitenoise es inerte detrás de nginx. Para ECOM, el efecto llega con el próximo espejo + build de su pipeline.

## Pendientes / a definir

- Desplegar en `icore-srv` y verificar que nginx siga sirviendo estáticos igual (no debería notarse nada).
- Espejar a ECOM: este release y los dos anteriores sin espejar.
- Si ECOM confirma que su pod usa `command` propio, indicarles el initContainer de `docker/k8s/bootstrap-initcontainer.yaml`.

## Reversión

Quitar whitenoise de requirements, middleware y storage; quitar `SERVE_MEDIA` de settings/urls; restaurar el entrypoint anterior y borrar `docker/k8s/`. Sin datos que se pierdan. La reversión reabre los huecos del Cambio 30.

## Historial

Entrada nueva; implementa lo que el **Cambio 30** había dejado documentado como responsabilidad de la plataforma.

**12/08/2026 — Prueba real de punta a punta en Kubernetes, desde cero.** A pedido del PM se levantó el sistema completo en un cluster k3d sobre `icore-srv` (aislado de producción: base propia efímera, puerto 8090, sin tocar los contenedores productivos). Imagen construida del release `6a5ea6c`. Resultado: **el circuito documentado funciona entero** — el entrypoint corrió migraciones + estáticos + sembrado + Daphne sin intervención, el pod quedó Ready por las probes de `/health/` en 102 s, y por el ingress respondieron 200 el health, el login y **un estático con hash servido por whitenoise sin nginx en el cluster**, que era la prueba central. El sembrado dejó 14 grupos (los **5 de Becas**, exactamente lo que le falta al testing de ECOM), **79 municipios y 778 localidades** cargados solos (la dependencia del Cambio 25), y **0 usuarios** — el superusuario se creó a mano con `createsuperuser --noinput`, como dice la guía (Cambio 28 verificado). Producción siguió sana durante toda la prueba (`/health/` 200, 5 GB libres).

Dos hallazgos operativos de la prueba, para quien la repita: `k3d image import` **falla en silencio** con Docker 29 (dice éxito y no importa nada; el modo `direct` falla con `content digest not found` por el store containerd) — la vía que funciona es `docker save --platform linux/amd64` + `docker cp` + `ctr -n k8s.io images import` en el nodo. Y la prueba corrió con `ENVIRONMENT=qa` **sin** `settings_production`, porque va por HTTP plano y el modo endurecido fuerza redirección a HTTPS y cookies seguras; con TLS real (el caso de ECOM) sí corresponde el módulo endurecido.

El cluster quedó corriendo para inspección manual (`http://10.5.6.209:8090` por VPN, usuario `admin-k8s`); se borra entero con `~/bin/k3d cluster delete datanach-test`.

**13/08/2026 — El testing de ECOM quedó corriendo sobre la nueva arquitectura.** Tras un día de idas y vueltas con su equipo (liveness matando el bootstrap → startupProbe; ingress apuntando al service viejo de nginx; `APP_RUNTIME` ausente que levantaba `runserver` — diagnosticado por las líneas de `autoreload` en su log), el ambiente quedó estable: **initContainer `bootstrap` en exit 0, un solo deployment con daphne** (en su caso en el puerto 8001, `APP_PORT` configurable, Service y probes alineados), sin nginx ni deployment de websocket, base sembrada completa. Confirmado por su log: `Bootstrap listo. Iniciando Daphne`. La arquitectura de este cambio quedó validada también en la plataforma de ECOM, no solo en nuestra prueba k3d. Diferencia conocida de su ambiente: **MariaDB** en lugar de MySQL 8 — sin impacto funcional; el warning `W036` (constraints condicionales de admisiones no creadas) aplica igual a MySQL 8, esas reglas las valida la capa de aplicación.

**11/08/2026, más tarde — re-revisión a pedido del PM («¿en teoría no hay ningún error?»).** Se releyeron los manifiestos y los claims de la documentación buscando errores, y aparecieron tres, corregidos en el momento:

1. **El ejemplo del initContainer tenía un hueco real:** con `command` propio en el contenedor web, el `collectstatic` del bootstrap escribía en el filesystem efímero del initContainer y los estáticos nunca llegaban al contenedor que sirve — whitenoise sin manifest responde 500 en toda pantalla. Se agregó el `emptyDir` de `/app/staticfiles` compartido entre ambos, con el motivo comentado.
2. **El comentario de horarios de `cronjobs.yaml` era impreciso:** decía «horarios en UTC-3 según el timezone del cluster», pero Kubernetes interpreta `schedule` en el timezone del controlador (UTC salvo configuración). Ahora indica `timeZone: America/Argentina/Buenos_Aires` (K8s ≥ 1.27) o correr los horarios tres horas.
3. **Trampa de correo sin documentar:** el backend SMTP solo se activa con `ENVIRONMENT=prd`; con `qa` el correo sale por la consola del pod aunque el SMTP esté configurado. Es deliberado del código (un QA no debe mandar mails reales), pero nadie lo decía: quedó anotado en la plantilla y en la guía, con la salida (correr el QA con `prd` si necesita probar invitaciones de punta a punta).

# Cambio 32 — Programas (SIIS) por encima de los segmentos

🟢 **HECHO — 13/08/2026**

| | |
|---|---|
| **Programa / módulo** | Becas — estructura del programa |
| **Etiquetas** | `#siis` `#convocatorias` `#requisitos` `#pausas` `#ui` |
| **Solicitante** | PM — pedido directo en sesión de trabajo, con demo el mismo día |
| **Fecha del pedido** | 13/08/2026 |
| **Issue / épica** | Sin issue |
| **Partes afectadas** | Backoffice · Servidor/API (formulario del territorial) · Infra (mismo cron del Cambio 22) |
| **Migración** | `programas.0045` |

## Pedido original

> «Hoy día tenemos Segmentos y subsegmentos, que segmentos lo traemos de SIIS. La idea ahora es que sea Programas (integración con SIIS) → Segmentos → Subsegmentos. Un programa puede tener N cantidad de segmentos los cuales nosotros le ponemos el nombre.»

Definiciones cerradas en la misma sesión: no puede existir un segmento sin programa (los datos actuales son de prueba); el nombre del programa se toma tal cual de SIIS como hoy hacía el segmento; el cupo se mantiene a nivel segmento; la pausa de un padre alcanza a todo lo de abajo como regla general; el coordinador sigue por segmento; y también hay requisitos a nivel programa.

## Alcance acordado

- Entidad nueva **Programa** (modelo `ProgramaSiis`; en la UI se llama «Programa»): es quien se vincula al catálogo de SIIS. El segmento pasa a ser local, con nombre puesto por el operador, N por programa.
- La vigencia SIIS del Cambio 22 sube un nivel: el bloqueo es del programa y cascadea a todos sus segmentos.
- Requisitos en cuatro niveles: generales, **de programa** (nuevo), de segmento y de subsegmento.
- Fuera de alcance: cupo a nivel programa (queda por segmento), coordinador a nivel programa (queda por segmento), mover un segmento de programa desde la UI.

## Decisiones tomadas

- **El modelo interno se llama `ProgramaSiis`**, no `Programa`: ya existe `Programa` para los programas del sistema (Becas, Dispositivos…). En la UI y en los textos es simplemente «Programa».
- **El segmento actual se partió en dos**: su identidad SIIS (id, foto congelada, estado corriente, fechas) se mudó a `ProgramaSiis`; el cuerpo local (nombre, descripción, cupo, GPS, activo) quedó en `Segmento`, que gana la FK `programa`.
- **La FK del segmento al programa queda `null=True` en la base pero obligatoria en los formularios.** Motivo: los segmentos históricos sin vínculo SIIS (datos de prueba) siguen operando sin bloquearse y sin migración destructiva; el alta nueva siempre exige programa. La depuración de esos registros de prueba es manual.
- **La unicidad se movió con la identidad**: antes un programa SIIS podía estar en un solo segmento (`uniq_segmento_siis_programa`); ahora es único por programa (`ProgramaSiis.siis_programa_id unique`) y el nombre del segmento es único dentro de su programa (`uniq_segmento_programa_nombre`), espejo del subsegmento.
- **La cadena de pausa gana un eslabón**: programa → segmento → subsegmento → convocatoria → relevamiento. El programa es pausable a mano (misma pantalla `gestionar_pausa`, tipo `programa`) y su `pausa_efectiva` respeta el criterio del Cambio 22: la pausa manual tiene precedencia y el bloqueo automático por SIIS nunca escribe el campo `pausado`.
- **El nombre del segmento dejó de autocompletarse desde SIIS**: ahora es obligatorio y libre (era el pedido central). El que toma el nombre del catálogo es el programa, congelado al vincular.
- **Los requisitos de programa los heredan todos sus segmentos** en el formulario del territorial (generales + programa + segmento + subsegmento). El autonumerado y la unicidad de orden **por lista** del Cambio 23 suman la lista del programa como un alcance más.
- **Capacidades reutilizadas**: las pantallas de Programas usan `becas.segmento.ver/crear` — quien administra la estructura de segmentos administra sus programas. No se crearon capacidades nuevas para no tocar el seed de roles.
- En la pantalla de revisión, los requisitos de programa se muestran junto a los del segmento (sin sección propia). Simplificación consciente para la demo.

## Implementación

- **Config de Becas gana la pantalla «Programas»** (`/becas/config/programas/`), primera entrada del menú del programa: listado con estado (Activo/Pausado + chip «SIIS inactivo»), franja de aviso por bajas de SIIS (la del Cambio 22, mudada acá), botón «!» con el detalle congelado, alta que es solo el selector del catálogo y detalle con dos pestañas: sus segmentos (con alta con programa fijo) y sus requisitos.
- El alta global de segmento (pantalla Segmentos) cambia el selector SIIS por un selector de Programa + campo Nombre obligatorio; la tabla suma la columna Programa y su chip SIIS ahora refleja el estado del programa.
- El detalle de segmento muestra el programa (solo lectura, con link) y los requisitos heredados del programa en su pestaña de requisitos; el detalle de subsegmento hereda programa + segmento.
- `sincronizar_programas_siis` actualiza ahora una fila por programa (antes, por segmento). Mismo cron (`docker/cron/sincronizar_programas_siis.cron`), sin cambios de infra.
- La validación SIS de revisión toma el `siis_programa_id` del programa del segmento.
- El selector de convocatorias del alta de relevamiento excluye las de programas pausados o no vigentes (antes miraba el estado en el segmento); los segmentos históricos sin programa no se excluyen.
- `seed_becas_demo_mobile` crea el programa demo («Chaco Joven» #34) y le cuelga los segmentos.

## Archivos

- `programas/models/__init__.py` — `ProgramaSiis`, `Segmento.programa`, `RequisitoNativo.programa`
- `programas/migrations/0045_programa_siis.py`
- `programas/forms.py` — `ProgramaSiisCreateForm`, `SegmentoForm`/`SegmentoCreateForm` sin SIIS, `RequisitoNativoForm` con ancla programa, exclusión en `RelevamientoForm`
- `programas/views/configuracion.py` — vistas de Programas, requisito de programa, ajustes de contexto
- `programas/views/pausas.py` — tipo `programa` en `gestionar_pausa`
- `programas/views/revision.py` — validación SIS por el programa del segmento
- `programas/services/siis_sync.py` + `programas/management/commands/sincronizar_programas_siis.py`
- `programas/services/becas.py` — herencia de requisitos de programa en el formulario
- `programas/services/autorizacion.py` — `requisitos_visibles` con el ancla programa
- `programas/templatetags/becas_extras.py` — `siis_info` sobre `ProgramaSiis`
- `programas/urls.py`, `programas/admin.py`
- Templates: `programa_list.html`, `programa_detail.html`, `_programas_table.html`, `_requisitos_programa_panel.html` (nuevos); `segmento_list.html`, `_segmentos_table.html`, `segmento_detail.html`, `_siis_programa_modal.html`, `requisito_form.html`, `_requisitos_page_table.html` (ajustados); `templates/includes/sidebar/opciones.html` (entrada Programas)
- `programas/management/commands/seed_becas_demo_mobile.py`
- Tests: `test_siis_vigencia_programa.py` (reescrito al nuevo nivel), `test_becas_config.py`, `test_becas_models.py`

## Base de datos

`programas.0045`: crea `ProgramaSiis`, agrega `Segmento.programa` y `RequisitoNativo.programa` (nulos), copia los datos —un programa por cada segmento vinculado, desde su foto congelada, y cuelga el segmento— y recién después borra los cinco campos `siis_*` del segmento y cambia las constraints. Es segura sobre datos existentes: la unicidad previa garantizaba a lo sumo un segmento por programa SIIS, y los segmentos sin vínculo quedan con programa nulo sin bloquearse.

## Validación

- `programas.tests.test_siis_vigencia_programa`: 22 pruebas del ciclo completo en el nivel nuevo — snapshot al vincular, doble vínculo rechazado, alta de segmento con nombre local y unicidad por programa, sincronización (baja, ausencia, idempotencia, dry-run, snapshot intacto), bloqueo en cascada hasta el relevamiento, pausa manual del programa cascadeando, precedencia de la pausa del segmento, segmento histórico sin programa que no se bloquea, y la salida de la convocatoria del selector por ambas vías.
- Suites de programas + usuarios/RBAC: 498 tests; los únicos fallos (110 errores de render + 1 falla de cache de Dispositivos) se verificaron **idénticos en `development`** corriendo la misma suite en un worktree limpio: son el baseline conocido de Python 3.14 + Django 4.2 (los tests de vista no renderizan en este entorno), no de este cambio.
- `manage.py check` sin errores; `makemigrations --check` sin cambios pendientes; `scripts/design_audit.py --changed` 0/0; `scripts/compile_templates.py` 306 OK / 0 errores.

## Puesta en marcha en el servidor

Nada nuevo: el cron del Cambio 22 sigue siendo el mismo comando. Aplicar la migración con respaldo previo, como siempre.

## Pendientes / a definir

- Depurar a mano los segmentos de prueba sin programa (quedan visibles con «—» en la columna Programa).
- La sección de revisión muestra los requisitos de programa dentro del bloque del segmento; si el cliente quiere verlos separados, es un ajuste de template.
- Los E2E de Playwright que pasen por el alta de segmento van a necesitar actualizar el flujo (ahora se elige programa y se escribe el nombre).

## Reversión

Antes de revertir, **respaldar la base**: la reversión de `programas.0045` elimina la tabla de programas y los campos `programa` de segmentos y requisitos — se pierde el vínculo SIIS de los segmentos (la migración de datos no tiene reversa automática) y los requisitos de programa quedan huérfanos de ancla. Pasos: revertir el código, correr `migrate programas 0044` y re-vincular los programas SIIS desde el alta de segmentos de la versión anterior.

## Historial

No aplica: entrada nueva. Sube de nivel lo implementado en el **Cambio 22** (vigencia SIIS) y le da al **Cambio 8** (incorporar programas de ECOM) la estructura que le faltaba: cuando los cuatro programas entren al catálogo, cada uno podrá tener N segmentos propios.

# Cambio 33 — Probar por qué SIIS no trae datos

🟢 **HECHO — 18/08/2026**

| | |
|---|---|
| **Programa / módulo** | Becas |
| **Etiquetas** | `#siis` `#infra` |
| **Solicitante** | PM — pedido directo en sesión de trabajo, con captura del select «Programa SIIS» vacío |
| **Fecha del pedido** | 18/08/2026 |
| **Issue / épica** | sin issue |
| **Partes afectadas** | Backoffice · Infra/ECOM |
| **Migración** | No requiere |

## Pedido original

«Quiero que pruebes la integración con SIIS, porque no me está trayendo datos.» El select **Programa SIIS** del alta de programa aparecía con la sola opción «Seleccioná un programa…».

## Alcance acordado

Entra: diagnosticar la causa y dejar una forma de verificar la integración en cualquier entorno. **No** entra cargar las credenciales —las emite ECOM y no están en el repo— ni cambiar el cliente de SIIS, que resultó estar bien.

## Decisiones tomadas

- **La causa no era el código.** Se probó el servicio de ECOM de punta a punta: `siisapi.ecomdev.ar` resuelve, y los cuatro endpoints del convenio responden `401` con cuerpo propio (`CREDENCIALES_INVALIDAS` / `Token inválido o vencido`). El servicio está arriba y el contrato no cambió. Lo que faltaba eran `SIIS_API_CLIENT_ID` y `SIIS_API_CLIENT_SECRET` en el entorno: sin ellas `SiisAPIClient._token()` corta **antes de salir a la red** y el formulario deja el select vacío. Era el pendiente que el Cambio 27.1 ya había anotado («cargar las credenciales de test en el gestor de claves y en el entorno»).
- **Se dejó un comando de diagnóstico en vez de un informe.** El síntoma —select vacío— tiene tres causas que se ven idénticas desde el backoffice: falta de configuración, rechazo del servicio, y catálogo que llega pero que el normalizador descarta por un cambio de contrato de ECOM. Sin una herramienta, cada vez que ECOM toque algo hay que rehacer la investigación a mano.
- **El comando recorre el camino real del cliente, no una copia.** Usa `SiisAPIClient` —incluidos `_items` y `_normalizar_catalogo`— para que lo que valida sea exactamente lo que corre en la aplicación. Un diagnóstico con su propio cliente HTTP podría dar verde con la app rota.
- **Descarta las cachés antes de probar.** El token se cachea 1 h y el catálogo 300 s: un diagnóstico que lea la caché puede dar verde con credenciales que ya no sirven. Con `--usar-cache` se puede pedir lo contrario, para ver qué está viendo la app en este momento.
- **Catálogo vacío es AVISO, no falla.** El entorno de test de ECOM puede no publicar programas y eso no es un problema de integración. La única falla de catálogo es que lleguen datos y el normalizador los tire: ahí el comando imprime las claves recibidas para compararlas contra las que el cliente espera.
- **Programa interpretado pero no vigente también es AVISO.** Se corrigió durante el desarrollo: la primera versión reportaba un programa `INACTIVO` como cambio de contrato. Un test lo detectó. El select vacío en ese caso es correcto y el motivo es la vigencia en SIIS.
- **Sale con código ≠ 0 si algo falla**, para poder usarlo como gate de despliegue o desde un CronJob.

## Implementación

`python manage.py diagnosticar_siis` informa, paso a paso y sin escribir nada:

1. **Configuración** — las tres variables (el secret solo por longitud, nunca su valor) y los timeouts. Avisa si `ENVIRONMENT=prd` pero la URL sigue apuntando al entorno de test de ECOM.
2. **Autenticación** — pide el token y, si falla, muestra el HTTP y el cuerpo textual de ECOM.
3. **Catálogo** — para `estado=ACTIVO` y `estado=TODOS`, cuántos items trajo la respuesta, cuántos interpretó la aplicación y cuántos llegan al select, con los programas listados.
4. **Compatibilidad** (opcional, con `--dni` y `--programa`) — la prevalidación, con los motivos de rechazo redactados.

## Archivos

- `programas/management/commands/diagnosticar_siis.py` (nuevo)
- `programas/tests/test_diagnosticar_siis.py` (nuevo)

## Base de datos

No requiere migración. El comando es de solo lectura y no toca la base.

## Validación

- `manage.py check` sin observaciones.
- `manage.py test programas.tests.test_diagnosticar_siis programas.tests.test_siis_service` → **17 tests OK**. Los seis nuevos cubren catálogo con datos, catálogo vacío, cambio de contrato, programa no vigente, token rechazado y falta de credenciales; los tres últimos verifican además el código de salida y que sin credenciales no se salga a la red.
- Contra el servicio real: los pasos 1 y 2 se ejercitaron de verdad —sin credenciales corta en el paso 1; con un secret inválido el paso 2 devuelve el `401 CREDENCIALES_INVALIDAS` de ECOM—. **Los pasos 3 y 4 solo están cubiertos por tests**: sin el secret válido no se pueden ejercitar contra el servicio.
- `scripts/design_audit.py --changed` → 0 errores, 0 warnings. No tocó UI.

## Puesta en marcha en el servidor

Nada propio: viaja en la imagen y se corre a mano cuando hace falta. Las variables las carga infra en el Secret del ambiente; los manifiestos de `docker/k8s/` las toman con `envFrom: secretRef`, así que una clave agregada al Secret llega al contenedor sin tocar YAML.

## Pendientes / a definir

- **Verificar los pasos 3 y 4 contra el servicio real** en cuanto el pod reinicie con las credenciales cargadas. Es lo único que puede destapar un cambio de contrato en el catálogo.
- Credenciales de **producción** de SIIS: siguen dependiendo del deploy prod de ECOM (pendiente heredado del Cambio 8 y de `docs/internal/temas/siis-api.md`).

## Reversión

Borrar los dos archivos nuevos. Sin efecto sobre la aplicación: nada del producto los importa.

# Cambio 34 — Prevalidación SIIS al aprobar o rechazar formularios

🟢 **Hecho sobre el contrato vigente**

| | |
|---|---|
| **Programa / módulo** | Becas / revisión |
| **Etiquetas** | `#siis` `#rbac` `#cupos` |
| **Solicitante** | Análisis #72 y revisión del PR #233 |
| **Fecha del pedido** | 18/08/2026 |
| **Migración** | No requiere |

## Pedido

Consultar SIIS de forma automática y síncrona cuando un Coordinador aprueba o rechaza un formulario, y permitir el reintento manual dentro de su segmento.

## Decisiones tomadas

- Cada acción consulta el programa SIIS del segmento y registra el intento, incluidos timeout y errores técnicos.
- La aprobación solo continúa con compatibilidad vigente para el DNI y programa actuales; después asigna cupo o lista de espera.
- El rechazo registra primero la consulta. Un error queda visible para reintento, pero no impide documentar la decisión local.
- El Coordinador valida SIIS mediante `becas.revision.editar` y conserva el alcance de sus segmentos. La revalidación de identidad sigue reservada a `becas.programa.administrar`.

## Alcance pendiente del contrato externo

La API vigente solo prevalida compatibilidad y no admite un parámetro que distinga aprobación de rechazo. La RN-25 del análisis #72 queda pendiente hasta que ECOM defina ese contrato; no se inventan campos fuera del manual.

## Archivos

- `programas/services/validacion_siis.py`, `programas/services/cupo.py`
- `programas/views/revision.py`
- `programas/templates/programas/becas/revision/formulario_detalle.html`
- `programas/tests/test_becas_revision.py`

## Historial

Entrada nueva. Implementa el disparo posible con el contrato vigente y explicita el límite externo de la RN-25.

## Historial

**18/08/2026, más tarde — la integración quedó verificada contra el servicio real y el comando se completó con lo que faltaba.** Infra cargó las credenciales en el Secret del ambiente y corrió el diagnóstico en el pod. Resultado: **autentica bien** (token de 297 caracteres) y **el catálogo responde HTTP 200 con cero programas**, tanto para `estado=ACTIVO` como para `estado=TODOS`.

Lo que eso cambia respecto de lo cerrado más arriba:

- **La causa registrada era correcta y quedó resuelta**: faltaban las credenciales. Con ellas, el cliente llega al servicio sin ningún error.
- **Pero el select sigue vacío**, y ahora por un motivo distinto: SIIS no publica programas para el cliente `datanach_test`. Eso vuelve a caer del lado del **Cambio 8** (que ECOM incorpore los programas al catálogo), que sigue pendiente de ellos. Deja de ser un problema de configuración nuestro.
- **El diagnóstico tenía un hueco que esta corrida destapó**: con la lista vacía informaba «0 items» sin mostrar el cuerpo, y «el catálogo está vacío» es indistinguible de «los programas vienen bajo una clave que `_items` no reconoce». Ahora, cuando no hay items, imprime el cuerpo recibido (recortado a 400 caracteres), sus claves de primer nivel y las que la aplicación busca. La respuesta pesaba 26 bytes, así que no cabía ningún programa; pero la conclusión no se podía sacar de la salida del comando, que es justamente para lo que existe.
- **Se agregó el backend de caché al paso 1**, con un aviso para un caso que se verificó corriendo el arranque: `config/settings_production` fija `ENVIRONMENT = "prd"` **después** de que `settings.py` evaluó los bloques que dependen de él, así que sin la variable de entorno `ENVIRONMENT` la caché queda local al proceso, el correo en backend de consola y los websockets en memoria, mientras `settings.ENVIRONMENT` informa `prd`. Para SIIS importa porque el endpoint de token tardó **7,6 segundos**: cacheado en Redis se paga una vez por hora, en memoria lo paga cada worker.

Nuevos tests: lista bajo clave desconocida, cuerpo recortado y claves de primer nivel en el catálogo vacío. Suite: **19 tests OK**. `manage.py check` limpio y `design_audit --changed` en 0/0.

Lo que decía antes y ya no vale: en *Pendientes* figuraba «verificar los pasos 3 y 4 contra el servicio real». El paso 3 quedó verificado. El **paso 4 (compatibilidad) sigue sin ejercitarse**: necesita un DNI real y un `id_programa` del catálogo, y el catálogo está vacío.

# Cambio 35 — El login del backoffice muestra la contraseña con un botón ojo

🟢 **HECHO — 19/08/2026**

| | |
|---|---|
| **Programa / módulo** | Transversal / sesión |
| **Etiquetas** | `#sesion` `#ui` |
| **Solicitante** | PM — mejora transversal sin análisis, aprobada por el PM el 14/08/2026 |
| **Fecha del pedido** | 14/08/2026 |
| **Issue / épica** | #250, dentro de la épica #252 |
| **Partes afectadas** | Backoffice |
| **Migración** | No requiere |

## Pedido original

«Botón "ojo" en el campo de contraseña del **login del backoffice** para alternar
entre oculto y visible», accesible (`aria-label`, operable por teclado) y siguiendo
el sistema de diseño.

## Alcance acordado

Entra el login del backoffice (`users/templates/user/login.html`). **Queda afuera**
el portal ciudadano: su login y sus pantallas de contraseña siguen sin toggle, y no
se tocaron porque el pedido acota la superficie al backoffice.

## Decisiones tomadas

- **El botón ya existía.** Al inspeccionar el código antes de desarrollar se encontró
  el toggle ya implementado en el login, con su ícono y su función `togglePassword()`.
  Lo que faltaba era exactamente lo que el pedido pide además del toggle: el estado
  accesible y el foco visible. El desarrollo se reencuadró sobre esa base en lugar de
  volver a escribir la funcionalidad.
- **El `aria-label` anuncia el estado, no la acción genérica.** Decía «Mostrar u
  ocultar contraseña» de forma fija, que no le dice al lector de pantalla en qué
  estado está el campo. Ahora alterna entre «Mostrar contraseña» y «Ocultar
  contraseña», y se sumó `aria-pressed` para que el botón se anuncie como conmutador.
- **El swap de ícono dejó de hacerse con `innerHTML`.** Antes se reescribía el `path`
  del SVG con dos strings duplicados dentro del JS. Ahora hay dos SVG en el markup y
  se conmuta cuál está oculto: se elimina la duplicación del `path` y el ícono no
  depende de inyectar markup en runtime.
- **`toggleAttribute` y no la propiedad `.hidden`.** `SVGElement` no expone la
  propiedad `hidden` (solo la expone `HTMLElement`), así que `svg.hidden = true`
  escribe una propiedad muerta y el ícono nunca cambia. Es un error que pasó los
  chequeos estáticos y solo apareció al probar en el navegador.
- **El `[hidden]` necesita ayuda del CSS en esta pantalla.** El login carga Tailwind
  por CDN, cuyo preflight declara `svg { display: block }`; siendo autor, le gana al
  `[hidden] { display: none }` del navegador. Por eso hay una regla explícita
  `.login-eye svg[hidden] { display: none }`.
- **El foco visible se define local a la pantalla.** El login no extiende
  `includes/base.html`: es un documento HTML propio y no recibe los estilos de foco
  del shell. El anillo se declaró en su `<style>` con `var(--ring-brand)`, igual que
  el `:focus` del campo de texto que ya estaba.
- **El campo no recuerda que estaba visible.** No se persiste el estado: el `type`
  lo renderiza el servidor siempre como `password`, así que cualquier recarga —un
  login fallido, por ejemplo— vuelve a ocultar la contraseña. Es la conducta buscada.
- **El foco se queda en el botón al alternar.** No se lo devuelve al campo, para que
  quien navega con teclado pueda mostrar y volver a ocultar sin volver a tabular.
- **Colateral:** el aviso de `messages` del login tenía tres colores hex escritos a
  mano (`#fffbeb`, `#fde68a`, `#92400e`). Se pasaron a los tokens `--bg-warning-soft`,
  `--border-warning-subtle` y `--text-fg-warning`, en espejo del bloque de error que
  ya usaba los tokens de `danger` diez líneas más abajo. Era el único ERROR que
  `design_audit.py` reportaba en el archivo y bloqueaba el cierre.

## Implementación

En el login del backoffice, el campo de contraseña tiene a la derecha un botón ojo.
Al activarlo, la contraseña se ve en texto plano y el ícono pasa a ojo tachado con el
color de marca; al activarlo de nuevo, vuelve a ocultarse. Funciona con mouse y con
teclado (Tab llega al botón, Enter y Espacio lo accionan) y muestra un anillo de foco
de marca cuando se lo alcanza por teclado. Un lector de pantalla lo anuncia como
botón conmutador y con la acción que corresponde al estado actual. El campo siempre
nace oculto: nada queda visible después de recargar.

## Archivos

- `users/templates/user/login.html` — clase `.login-eye` con `:focus-visible`, los dos
  SVG conmutables, `aria-pressed`/`aria-controls`/`aria-label` dinámico, el listener
  sin handler inline, y los tokens del aviso de `messages`.

## Base de datos

No requiere.

## Validación

- `manage.py check` → sin issues.
- `scripts/design_audit.py --changed` → **0 errores**, 2 WARN de `outline:none`, ambos
  justificados: cada uno tiene su `box-shadow: var(--ring-brand)` de reemplazo en el
  mismo bloque (`.login-input:focus` y `.login-eye:focus-visible`).
- `scripts/check_design_agent.py --changed` → `design-agent contract: OK`.
- `scripts/compile_templates.py` → 308 templates, 0 errores.
- **Prueba real en navegador (Chromium vía Playwright, login servido por el sistema
  levantado contra el MySQL local):** 22 verificaciones sobre los tres casos de QA del
  issue #250 —TC-250-01 toggle, TC-250-02 teclado y accesibilidad, TC-250-03 el default
  siempre oculto— todas en verde. Esta prueba es la que encontró el bug de
  `SVGElement.hidden`, que los chequeos estáticos no ven.

## Puesta en marcha en el servidor

No requiere: solo template. Alcanza el deploy.

## Pendientes / a definir

- El **portal ciudadano** no tiene el toggle en su login ni en sus pantallas de cambio
  y reseteo de contraseña (`portal/templates/portal/ciudadano/login.html`,
  `cambio_password.html`, `password_reset_confirm.html`, `registro_step2.html`). Quedó
  afuera por alcance; si se pide, conviene extraer el patrón a una pieza reutilizable
  en vez de repetir el bloque, y registrarla en el inventario del agente de diseño.
- El login carga **Tailwind por CDN** (`cdn.tailwindcss.com`) y su preflight compite
  con los estilos de la pantalla —este cambio necesitó una regla para sortearlo—.
  Sacarlo o reemplazarlo por el build del sistema es deuda anterior a este cambio.

## Reversión

Revertir el commit del template. No hay datos involucrados: el cambio es de
presentación y no persiste nada.

# Cambio 38 — Cerrar sesión da error 405 después de actualizar Django

🟢 **HECHO — 20/08/2026**

| | |
|---|---|
| **Programa / módulo** | Transversal / sesión |
| **Etiquetas** | `#sesion` `#infra` `#ui` |
| **Solicitante** | PM — reportó que `https://datanach.ecomdev.ar/logout` devuelve HTTP 405 |
| **Fecha del pedido** | 20/08/2026 |
| **Issue / épica** | sin issue |
| **Partes afectadas** | Backoffice |
| **Migración** | No requiere |

## Pedido original

«Cuando hago `https://datanach.ecomdev.ar/logout` me da HTTP ERROR 405.»

## Alcance acordado

Se corrige el cierre de sesión del backoffice. **Queda afuera** el portal ciudadano,
que no está afectado, y el resto del salto de versión de Django, que se revisó sin
encontrar más usos de APIs removidas.

## Decisiones tomadas

- **La causa es el salto a Django 5.** El commit `290e365` (PR #257, issue #256, para
  destrabar Pip Audit) subió **Django 4.2.30 → 5.2.17** el 18/08. Django 5.0 eliminó
  el soporte de GET en `LogoutView` —deprecado en 4.1— y la vista solo acepta POST.
  `users/urls.py` usa la vista de Django tal cual, así que entrar a `/logout` con el
  navegador devuelve 405. No es un problema de nginx ni del despliegue.
- **Se cierra sesión por formulario POST, no se le devuelve el GET a la vista.**
  Reponer el GET con una vista propia sería reintroducir a mano el agujero que Django
  cerró: con logout por GET, cualquier página de terceros con un
  `<img src="…/logout">` cierra la sesión del usuario sin que él haga nada.
- **Eran dos superficies, y la segunda es la más grave.** El ítem «Cerrar sesión» del
  menú de usuario, y el «Salir» de la pantalla de cambio de contraseña obligatorio.
  Esa pantalla retiene al usuario hasta que cambia la clave provisoria, y «Salir» es su
  única salida: con el 405, quien entraba con clave provisoria y no quería cambiarla
  quedaba sin forma de salir por la interfaz.
- **El cierre por inactividad nunca se rompió.** `static/custom/js/idle-logout.js` ya
  armaba un formulario POST con CSRF. Quedó el caso contrafáctico: el logout automático
  funcionaba y el manual no.
- **El portal ciudadano no estaba afectado.** Usa su propia `CiudadanoLogoutView` con
  únicamente `post()` y su template ya enviaba un formulario. Nunca aceptó GET.
- **Por qué no se detectó antes de desplegar:** el venv local sigue en **Django
  4.2.20** aunque `requirements.txt` declara 5.2.17 — se actualizó el archivo y no se
  reinstaló el entorno. `manage.py check` y los tests locales corren contra la versión
  vieja, donde el GET todavía funcionaba con un aviso de deprecación. Y el logout no
  tenía cobertura: la única referencia era `core/tests/test_url_namespaces.py`, que
  verifica que la URL resuelva, nunca que responda.
- **El resto del salto de versión se revisó.** No hay usos de `DEFAULT_FILE_STORAGE`,
  `STATICFILES_STORAGE`, `USE_L10N`, `index_together`, `NullBooleanField`,
  `make_random_password` ni los campos CI de Postgres. Los dos `timezone.utc` que
  aparecen son de la biblioteca estándar, no el alias de Django que se removió.
- **La actualización de Django no tiene entrada en este archivo.** El PR #257 se cerró
  sin registrarla, y este 405 es su consecuencia. Queda anotado como pendiente.

## Implementación

El cierre de sesión del backoffice se envía por POST con token CSRF, tanto desde el
menú de usuario como desde la pantalla de cambio de contraseña obligatorio. El usuario
no percibe ninguna diferencia: el ítem del menú se ve igual y sigue llevando al login.

## Archivos

- `templates/includes/navbar.html` — el ítem del menú pasa de enlace a formulario POST,
  conservando su apariencia y su comportamiento de hover.
- `users/templates/user/base_public_auth.html` — variante `button.public-auth__link`
  para que un botón de formulario se vea igual que el enlace, con foco visible.
- `users/templates/user/cambiar_contrasena_obligatorio.html` — «Salir» pasa a formulario.
- `users/tests/test_logout.py` — nuevo.
- `.claude/agents/chaco-design-system.md` — el shell del backoffice deja constancia de
  que el logout va por POST, y se inventaría el shell de autenticación pública.

## Base de datos

No requiere.

## Validación

- `users.tests.test_logout` → 3 pruebas en verde: el POST cierra la sesión y redirige al
  login, y ninguna de las dos pantallas ofrece el logout como enlace. Las dos últimas
  renderizan el template directamente en lugar de pedir la página con el cliente de
  pruebas, porque el entorno local corre Python 3.14 y ahí el cliente de pruebas de
  Django 4.2 no puede copiar el contexto de render.
- `manage.py check` → sin issues.
- `scripts/design_audit.py --changed` → 0 errores, 1 WARN de `outline:none` justificado
  (tiene su `box-shadow: var(--ring-brand)` en el mismo bloque).
- `scripts/check_design_agent.py --changed` → `design-agent contract: OK`.
- `scripts/compile_templates.py` → 318 templates, 0 errores.

## Puesta en marcha en el servidor

No requiere: solo templates. Alcanza el deploy.

## Pendientes / a definir

- **El venv local quedó en Django 4.2.20 contra 5.2.17 en producción.** Mientras no se
  reinstale, las validaciones locales corren contra otra versión que el servidor y
  pueden dejar pasar otra rotura como esta. Es el pendiente más importante de esta
  entrada.
- **La actualización de Django 4.2 → 5.2 no tiene entrada propia** en este archivo.
- El logout del portal ciudadano no tiene pruebas; funciona, pero por convención más
  que por contrato verificado.

## Reversión

Revertir el commit de los templates. No hay datos involucrados. Volver al enlace GET
solo tendría efecto si además se bajara Django a 4.2, y reintroduciría el problema de
seguridad descrito arriba.

# Cambio 39 — En el login aparece el logo de Nodo en lugar del del Chaco

🟢 **HECHO — 21/08/2026**

| | |
|---|---|
| **Programa / módulo** | Transversal / marca |
| **Etiquetas** | `#ui` `#sesion` `#infra` |
| **Solicitante** | PM — vio el logo «Nodo — Powered by ICore» en la pantalla de acceso |
| **Fecha del pedido** | 21/08/2026 |
| **Issue / épica** | sin issue |
| **Partes afectadas** | Backoffice |
| **Migración** | No requiere |

## Pedido original

«Quiero ver por qué aparece este ícono y no el de Chaco», con la captura del logo
«Nodo — Powered by ICore».

## Alcance acordado

Se corrige la marca del login y de las pantallas de credenciales, y se saca el asset de
ICore de la carpeta de Chaco. **Queda afuera** el resto del branding: sidebar, portal y
correos nunca estuvieron afectados.

## Decisiones tomadas

- **El archivo estaba mal archivado, no mal referenciado.**
  `static/custom/chaco/login-logo.svg` **era el logo de Nodo/ICore**, no el del Chaco:
  `#FD517D` para «Nodo», `#4C4C4C` para el ícono de nodos y `#6C757D` para «Powered by
  ICore». Entró el **24/06/2026** en el commit `8a5d412`, titulado «fijar branding
  Chaco». Vivió dos meses al lado de `login-logo.png` —que sí es el del Gobierno del
  Chaco— con un nombre que invitaba a confundirlos.
- **Lo puso en pantalla una optimización de peso.** El commit `1ce73b3` del 20/08
  («perf(inicio): diferir gráfico y aligerar login») cambió los dos templates de `.png`
  a `.svg` porque el SVG pesa 15 KB contra 194 KB. El objetivo era correcto; lo que
  faltó fue verificar que el archivo liviano fuera la misma imagen. Se eligió por
  nombre y por peso, nunca se abrió.
- **La causa real del peso era el tamaño, no el formato.** El PNG del Chaco era de
  **2212×805 px** y se renderiza a 38 px de alto en el login y 40 px en los correos:
  194 KB para mostrar 110×40. Se redimensionó a **330×120** (3× para pantallas de alta
  densidad) y quedó en **26 KB, un 87 % menos**. O sea que se conserva casi toda la
  ganancia de `1ce73b3` sin cambiar de logo: la diferencia con el SVG de ICore es de
  11 KB.
- **El máster en alta resolución no se perdió.** `app-logo.png` y `footer-logo.png` son
  byte a byte idénticos al PNG original (mismo SHA-256), así que la versión de 2212×805
  sigue disponible en el repositorio.
- **El asset de ICore se movió, no se borró.** Quedó en
  `static/custom/icore/nodo-logo.svg`, fuera de `custom/chaco/`, para que no vuelva a
  confundirse con la marca del organismo y sin destruir un archivo que puede hacer falta.
- **Había un test que fijaba el error como comportamiento esperado.**
  `LoginBrandAssetTests.test_login_web_usa_el_logo_svg_liviano` afirmaba `assertIn` del
  SVG **y** `assertNotIn` del PNG: cualquier corrección lo habría puesto en rojo. Se
  reescribió al revés —exige el PNG del Chaco y prohíbe cualquier referencia a
  `nodo-logo`— y ahora es el guardián de la regresión en lugar de su candado.
- **Ningún control mecánico podía detectarlo.** `design_audit.py` revisa hex, fuentes y
  tags; `check_design_agent.py` revisa que el inventario se actualice —y de hecho
  `1ce73b3` lo actualizó, dejando escrito que la marca era el SVG—. Ninguno abre una
  imagen para ver qué dice. Por eso el inventario ahora nombra el archivo correcto y
  aclara explícitamente que `nodo-logo.svg` es la marca del proveedor y no se usa en
  superficies del organismo.

## Implementación

El login del backoffice y las cuatro pantallas de credenciales fuera de sesión
—establecer contraseña, recuperar contraseña, aviso de envío y cambio obligatorio—
muestran el logo del Gobierno del Chaco. Se agregaron `width`/`height` a las etiquetas
para que el navegador reserve el espacio y la pantalla no salte al cargar.

## Archivos

- `static/custom/chaco/login-logo.png` — redimensionado de 2212×805 a 330×120 (194 KB → 26 KB).
- `static/custom/icore/nodo-logo.svg` — movido desde `static/custom/chaco/login-logo.svg`.
- `users/templates/user/login.html`, `users/templates/user/base_public_auth.html` — vuelven al PNG.
- `users/tests/test_credenciales.py` — el test invertido.
- `.claude/agents/chaco-design-system.md` — el inventario nombra el asset correcto.

## Base de datos

No requiere.

## Validación

- Se abrió el PNG redimensionado y se verificó a ojo que es el logo del Gobierno del
  Chaco y que sigue legible a ese tamaño.
- Render directo de `user/login.html` y `user/cambiar_contrasena_obligatorio.html`: las
  dos referencian `custom/chaco/login-logo.png`, ninguna menciona `nodo-logo`, y ninguna
  carga el CDN de Tailwind.
- `manage.py check` → sin issues.
- `scripts/design_audit.py --changed` → 0 errores, 3 WARN de `outline:none` justificados.
- `scripts/check_design_agent.py --changed` → `design-agent contract: OK`.
- `scripts/compile_templates.py` → 318 templates, 0 errores.
- `users.tests.test_logout` → 3 en verde. `LoginBrandAssetTests` no se puede ejecutar en
  el entorno local: pide la página con el cliente de pruebas y ahí choca con la
  incompatibilidad entre Python 3.14 y Django 4.2 del venv. Corre en CI, que usa 3.12.

## Puesta en marcha en el servidor

Alcanza el deploy. **Atención:** el release `57d17c3` —espejado al GitLab de ECOM el
21/08— lleva el logo de ICore. Hasta que se publique un release con esta corrección,
testing y QA muestran la marca del proveedor en la pantalla de acceso.

## Pendientes / a definir

- **Ningún control verifica el contenido de los assets de marca.** Si alguien vuelve a
  intercambiar dos imágenes por nombre, solo lo detecta una persona mirando la pantalla.
  El test nuevo cubre el caso de este archivo, no el general.
- `app-logo.png` y `footer-logo.png` siguen pesando 194 KB cada uno y son copias
  idénticas entre sí. Conviene revisar dónde se usan y a qué tamaño se renderizan.
- `docs/design-kb/reference/branding.py` apunta a `custom/branding/default/login-logo.svg`,
  una ruta que no existe en el repositorio.

## Reversión

Revertir el commit. El PNG vuelve a 194 KB y el SVG de ICore a `custom/chaco/`. No hay
datos involucrados.

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

# Cambio 36 — El diseño de Dispositivos es todo lo contrario a lo que tiene que ser

🟡 **PARCIAL — 19/08/2026**

| | |
|---|---|
| **Programa / módulo** | Dispositivos |
| **Etiquetas** | `#ui` |
| **Solicitante** | PM — pedido directo en sesión de trabajo: «tomá el agente de diseño y vé el programa Dispositivos, que el diseño es todo lo contrario a lo que tiene que ser» |
| **Fecha del pedido** | 19/08/2026 |
| **Issue / épica** | Sin issue |
| **Partes afectadas** | Backoffice |
| **Migración** | No requiere |

## Pedido original

«Quiero que tomes el agente de diseño y veas el programa Dispositivos ya que el
diseño es todo lo contrario a lo que tiene que ser.»

## Alcance acordado

El diagnóstico cubrió **todo** el programa: los 15 templates de
`programas/templates/programas/dispositivos/`, los 5 de `admisiones/` y la solapa
`legajos/templates/legajos/solapas/dispositivos.html`, contrastados contra el
frontend productivo de Becas —el módulo más maduro y la referencia de facto— y
contra `.claude/agents/chaco-design-system.md`.

De los seis hallazgos priorizados, el PM autorizó ejecutar **los dos primeros**:
badges de estado y solapas reales. Entran también los badges de estado de cama y
el contador de la lista de espera, porque son el mismo componente en las mismas
pantallas tocadas.

Queda **explícitamente afuera** de este cambio, con su motivo en *Pendientes*:
el motor de modal AJAX ad-hoc de la configuración, el restyle de las stat cards,
la unificación de los dos handlers de confirmación duplicados y la decisión sobre
si la solapa de Dispositivos debe embeberse en el legajo.

## Decisiones tomadas

- **El problema no era mecánico.** `scripts/design_audit.py` daba **0 errores y 0
  warnings** sobre todo el módulo antes de tocar nada: no había hex sueltos,
  fuentes legacy ni `confirm()` nativo. La divergencia era estructural —patrones
  de página, componentes y jerarquía—, que es justamente lo que la auditoría
  mecánica no puede ver. Se deja asentado porque explica por qué el módulo pasaba
  el gate de cierre y aun así se veía mal.

- **Las «solapas» del detalle eran anclas disfrazadas.** El `<nav>` imitaba la
  barra de tabs de Becas —con el ítem activo subrayado en `border-fg-brand`— pero
  eran `<a href="#id">` sin Alpine: las cinco secciones estaban **siempre**
  renderizadas y apiladas, y el indicador de «activo» nunca cambiaba al scrollear.
  Era un estado de foco falso y el mayor responsable de la sensación de desorden.
  Se convirtió en solapas Alpine reales (`x-data` / `x-show`) siguiendo
  `becas/relevamientos/convocatoria_detail.html`, que es el patrón canónico.

- **Los Indicadores operativos quedan fuera de las solapas, siempre visibles.**
  La sección nunca tuvo entrada en la barra de navegación: era contenido huérfano.
  Al pasar a solapas había que ubicarla en alguna, y esconder la salud operativa
  del dispositivo detrás de un clic habría sido una regresión. Se dejó como franja
  fija sobre las solapas, que es además la forma en que Becas trata sus métricas.

- **«Parte diario» sale de la barra de solapas.** Era un enlace a otra página
  metido entre tabs: dentro de un `role="tablist"` eso es semánticamente inválido
  y engaña al usuario, que espera cambiar de panel y termina navegando. Se movió a
  los botones de acción del encabezado, donde viven el resto de las acciones de
  página. Sigue disponible además desde la solapa de Admisiones, como antes.

- **Dispositivos no usaba el componente `badge` en ningún lado.** Cero apariciones
  en todo el módulo, contra más de 40 en Becas. El estado del dispositivo —que
  tiene **siete** valores posibles— se mostraba como texto plano sin color en el
  listado y en el detalle, y donde sí había badge estaba reimplementado a mano con
  `<span>` y clases sueltas. Un listado de siete estados sin código de color es el
  peor golpe a la escaneabilidad de toda la superficie, y por eso este fue el
  cambio de mayor relación impacto/esfuerzo.

- **El mapa de los siete estados se fijó así**, para que cada uno tenga lectura
  propia sin abusar del color de marca:

  | Estado | Variante | Por qué |
  |---|---|---|
  | `BORRADOR` | `badge-white` | Todavía no es un legajo real; el más liviano |
  | `PENDIENTE_VALIDACION` | `badge-info` | En vuelo, esperando a otro; mismo criterio que `EN_REVISION` en Becas |
  | `ACTIVO` | `badge-success` | Único estado plenamente operativo |
  | `OBSERVADO` | `badge-warning` | Requiere acción del solicitante |
  | `RECHAZADO` | `badge-danger` | Terminal negativo |
  | `INACTIVO` | `badge-gray` | No operativo, reversible |
  | `CERRADO` | `badge-gray` | No operativo, terminal |

  `INACTIVO` y `CERRADO` comparten variante a propósito: son los dos estados «no
  operativos» y la etiqueta de texto alcanza para distinguirlos. La alternativa era
  darle `badge-brand` a uno de los dos, y el rosa de marca atrae la vista, que es
  exactamente lo contrario de lo que se quiere para una fila muerta.

- **Se creó un parcial por entidad en vez de un filtro de template.** El mapa vive
  en `programas/templates/programas/dispositivos/_estado_badge.html` y
  `_cama_estado_badge.html`, calcado del patrón que ya usa
  `becas/relevamientos/_estado_badge.html`. Se prefirió el parcial al templatetag
  porque es el precedente del repo y porque mantiene el mapa de color donde se lee,
  no escondido en Python.

- **Los estados de cama entran en el mismo cambio.** Estaban en la tabla que ya se
  estaba tocando, también como texto plano, y son el mismo componente:
  `DISPONIBLE`→`badge-success`, `RESERVADA`→`badge-warning`, `OCUPADA`→`badge-info`,
  `FUERA_SERVICIO`→`badge-danger`. `OCUPADA` es `info` y no `warning` porque una
  cama ocupada es la operación normal, no una alerta.

- **La barra de solapas lleva `flex-wrap`**, que la de anclas no tenía. Con cinco
  ítems y contadores desbordaba en mobile sin ninguna señal de scroll.

## Implementación

En el **listado de dispositivos**, la columna Estado dejó de ser texto plano y
ahora muestra el badge de color correspondiente a cada uno de los siete estados.

En el **detalle del dispositivo**:

- El estado aparece como badge al lado del título, no como una línea de texto en
  mayúsculas sobre el nombre.
- La franja de Indicadores operativos quedó fija debajo del encabezado.
- El resto del contenido se agrupó en cuatro solapas reales —Datos, Camas,
  Admisiones, Historial— dentro de una sola tarjeta. Se muestra una por vez; Camas
  y Admisiones llevan su contador en un badge dentro de la propia solapa.
- «Parte diario» pasó a los botones del encabezado.
- La tabla de camas muestra el estado de cada cama como badge de color.
- El contador de la lista de espera y la marca «Reingreso» pasaron a badge.

En la **configuración de tipos de dispositivo**, los badges Activo/Inactivo de la
lista y del detalle, y la marca «Obligatorio» de cada campo, dejaron de ser spans
armados a mano y usan el componente del sistema. «Obligatorio» pasó de
`bg-info-soft` a `badge-brand`, que es lo que usa Becas para el mismo concepto en
sus preguntas.

No cambió ningún comportamiento, permiso, URL ni contrato de vista.

## Archivos

- `programas/templates/programas/dispositivos/_estado_badge.html` — **nuevo**
- `programas/templates/programas/dispositivos/_cama_estado_badge.html` — **nuevo**
- `programas/templates/programas/dispositivos/legajo/detail.html`
- `programas/templates/programas/dispositivos/legajo/list.html`
- `programas/templates/programas/dispositivos/config/tipo_list.html`
- `programas/templates/programas/dispositivos/config/_tipo_detail_content.html`

## Base de datos

No requiere.

## Validación

- `scripts/design_audit.py --changed` → **0 errores**. Los 2 warnings que reporta
  son `outline:none` en `users/templates/user/login.html`, ajenos a este cambio y
  preexistentes en el árbol de trabajo.
- `scripts/compile_templates.py` → **310 templates compilados, 0 errores**.
- `manage.py check` → **sin issues**.
- **Las suites de Dispositivos no se pudieron correr:** Docker estaba apagado y
  `manage.py test` falla al resolver el host `sedronar-mysql`. Quedan pendientes de
  ejecución `programas.tests.test_dispositivos_legajo`, `test_dispositivos_config`,
  `test_dispositivos_camas`, `test_admisiones` y `test_solapa_dispositivos`. El
  riesgo real es bajo —no se tocó Python ni contratos de contexto— pero
  `test_dispositivos_legajo` y `test_dispositivos_config` sí podrían assertear
  sobre texto del HTML del estado, que es justamente lo que cambió.
- Prueba en navegador: **pendiente**, por la misma razón.

## Puesta en marcha en el servidor

No requiere: son templates, entran con el deploy.

## Pendientes / a definir

Los cuatro hallazgos del diagnóstico que quedaron sin ejecutar, en el orden en que
conviene abordarlos:

1. **Motor de modal AJAX propio en la configuración.**
   `config/tipo_detail.html` implementa desde cero fetch, inyección, focus trap y
   submit AJAX. Los atributos `data-edit-url` / `data-edit-modal` **no existen en
   ningún otro archivo del repo**: es un cuarto patrón de modal que compite con
   `ModernModal`, con los modales Alpine de Becas y con el confirm de SweetAlert
   crudo. Su submit handler es una copia casi calcada de `becas/_ajax_js.html` y ya
   divergió del original —no soporta `data-reset`, no emite el evento equivalente a
   `becas-saved`, maneja un 401 que Becas no contempla—. Ojo con el antecedente:
   el plan del 23/07/2026
   ([`docs/plans/2026-07-23-dispositivos-sidebar-modales-design.md`](../plans/2026-07-23-dispositivos-sidebar-modales-design.md))
   aprobó «repetir el patrón AJAX existente en Becas»; se aprobó el comportamiento
   y se terminó implementando un motor paralelo. Tamaño mediano-grande: toca
   también `programas/views/dispositivos_config.py`.
2. **Stat cards achatadas.** Las ocho tarjetas del detalle usan
   `rounded-lg border-light` sin sombra ni ícono, contra
   `rounded-xl border-base shadow-sm` más ícono de color en Becas. Al repetirse
   ocho veces en la misma pantalla, el achatamiento se lee como sistema. Chico.
3. **Dos handlers de confirmación duplicados dentro del propio módulo.**
   `legajo/detail.html` y `config/tipo_detail.html` tienen cada uno su copia del
   `Swal.fire` para `data-confirm`, y ya divergieron: uno soporta
   `data-requires-motivo` y el otro no. Debería ser un include único, como
   `becas/_confirm_js.html`. Chico.
4. **La solapa de Dispositivos no se embebe en el legajo.**
   `programas/services/solapas.py` marca a Dispositivos como el **único** programa
   con `contenido_embebido: False`: al abrirla, el usuario sale por completo de la
   vista de legajo en vez de ver el contenido dentro de la solapa, como pasa con
   Becas. Es una decisión a nivel de servicio, no de template, y **requiere
   definición de producto** antes de tocarse.

Fuera de la lista, dos observaciones del diagnóstico que **no** son deuda de
Dispositivos y se registran para que no se le imputen:

- La carga de SweetAlert2 por CDN dentro de cada página la hacen 17 archivos de
  todo el sistema, pese a que `nodo-swal-theme.js` ya asume Swal global. Es una
  práctica extendida, no una divergencia del módulo.
- La convención del `<h1>` está partida en el propio canon: conviven
  `style="font-size:28px"` y `text-3xl font-extrabold`, y Becas usa las dos.
  Dispositivos las mezcla dentro de sí mismo, pero no inventó el problema.

## Reversión

`git revert` del commit. No hay datos involucrados: son seis templates, dos de
ellos nuevos. Revertir devuelve el detalle a secciones apiladas con anclas y los
estados a texto plano.

## Historial

No aplica: entrada nueva.

# Cambio 37 — Credenciales por correo: clave provisoria al alta y recupero desde el login

🟡 **PARCIAL — 20/08/2026 · el circuito está implementado; falta el envío real verificado contra el SMTP y la aprobación de los textos**

| | |
|---|---|
| **Programa / módulo** | Transversal / usuarios |
| **Etiquetas** | `#usuarios` `#correo` `#sesion` `#infra` |
| **Solicitante** | PM — definiciones del 14/08/2026 registradas en el análisis #236, y entrega de las credenciales SMTP en sesión de trabajo del 20/08/2026 |
| **Fecha del pedido** | 14/08/2026 |
| **Issue / épica** | Análisis #236 (épica #46) · tasks #244, #245, #246, #247 |
| **Partes afectadas** | Backoffice · Infra/ECOM |
| **Migración** | `users.0022` |

## Pedido original

Del análisis #236: «Círculo completo de credenciales por correo: (a) al **crear un
usuario**, que le llegue un correo con su nombre de usuario y una **clave
provisoria**; (b) que cualquier usuario pueda **restablecer su contraseña** desde
el login ("Olvidé mi contraseña") vía un enlace de un solo uso, incluidos los
territoriales desde la app.»

En la sesión del 20/08/2026 el PM entregó las credenciales del SMTP institucional
(`smtp.chaco.gob.ar:587`, STARTTLS, casilla `datanach@chaco.gob.ar`) y definió que
**el mismo servicio se usa en QA y en producción**. Las plantillas de los dos
correos llegaron diseñadas desde un proyecto de Claude Design (`Emails Chaco`).

## Alcance acordado

Entra el círculo completo: configuración del SMTP, las dos plantillas HTML de
correo, el alta con clave provisoria, el cambio obligatorio al primer ingreso y el
"¿Olvidaste tu contraseña?" del login del backoffice.

Queda **explícitamente afuera**:

- **El vencimiento de la clave provisoria.** El diseño original decía «Vence en 24
  horas»; el PM lo descartó porque no hay mecanismo de expiración de contraseñas en
  el sistema. Se borró la frase del correo en vez de dejar una promesa incumplida.
- El reset del portal ciudadano, que ya existía (fuera de alcance del #236).
- La task #248 (acceso al reset desde la app de territoriales), ya cerrada aparte.
- La casilla de soporte y la dirección postal del pie: a definir (ver *Pendientes*).

## Decisiones tomadas

- **La clave provisoria viaja en texto plano en el cuerpo del correo, revirtiendo
  el criterio del Cambio 13.** Ese cambio había registrado «no se envían
  contraseñas en texto plano» y por eso la invitación llevaba un enlace para
  establecer la contraseña. El cliente pidió explícitamente lo contrario el
  14/08/2026. La mitigación acordada es que la clave sirve **una sola vez en la
  práctica**: el middleware no deja usar ninguna pantalla hasta que la persona
  define una contraseña propia. El Cambio 13 conserva su texto y recibió su
  sección de historial.

- **El backend de correo lo decide `EMAIL_HOST`, no `ENVIRONMENT`.** Antes el SMTP
  se activaba solo con `ENVIRONMENT=prd`, así que en QA el correo salía por la
  consola del pod aunque estuviera configurado — la trampa que el Cambio 31 ya
  había dejado anotada. Con el criterio nuevo, QA y producción usan el mismo SMTP
  con solo cargar las variables, y el dev local sigue en consola sin configurar
  nada. Es la condición para que el PM pueda probar el circuito en QA.

- **El asunto se prefija con `[QA]` / `[DEV]` fuera de producción.** QA y producción
  comparten casilla remitente y plantilla, así que un correo de prueba y uno real
  llegan idénticos a la bandeja de un usuario real. El prefijo es lo único que los
  distingue. Sale de `EMAIL_ASUNTO_PREFIJO`, derivado de `ENVIRONMENT`.

- **`PASSWORD_RESET_TIMEOUT` fijado en 24 h.** No estaba seteado, así que Django
  usaba su default de 3 días. Los dos correos de recupero —el nuevo del backoffice
  y el del portal ciudadano, que ya existía— **prometían 24 horas por escrito**: la
  promesa era falsa desde antes de este cambio. Al setearlo se corrigen ambos.

- **`EMAIL_TIMEOUT` en 10 s.** El envío es sincrónico: no hay Celery en el repo, el
  correo sale dentro del request del alta de usuario. Sin timeout, un SMTP lento
  cuelga ese request hasta que corte el gateway.

- **El remitente tiene que ser la misma casilla que autentica.** `DEFAULT_FROM_EMAIL`
  usa `datanach@chaco.gob.ar`, igual que `EMAIL_HOST_USER`: la mayoría de los relays
  rechazan un `From` distinto del autenticado.

- **La pantalla de cambio obligatorio usa `SetPasswordForm`, no
  `PasswordChangeForm`.** La persona acaba de autenticarse con la clave provisoria;
  pedírsela otra vez no agrega seguridad y agrega fricción en el peor momento.

- **Al cambiar la clave hay que reescribir `backoffice_session_key`.** Django rota
  la sesión al cambiar la contraseña (`update_session_auth_hash`). Sin actualizar
  el Profile, `BackofficeSingleSessionMiddleware` lee la sesión nueva como
  «reemplazada» y expulsa al usuario en el request siguiente, justo después de
  haber definido su contraseña. Hay un test que cubre exactamente esto.

- **El chequeo del entorno es un comando propio, no `sendtestemail`.** El comando de
  Django solo prueba que «algo salga»: no valida que el remitente coincida con la
  casilla que autentica —la falla más probable y la más difícil de leer—, no arma las
  plantillas reales, y cuando falla no distingue entre DNS, egress cerrado al 587, TLS
  y credenciales rechazadas: las cuatro se ven como un error genérico.
  `diagnosticar_correo` recorre los cuatro pasos por separado, en el mismo estilo que
  `diagnosticar_siis`, y devuelve código distinto de 0 para poder usarse como gate de
  despliegue. El correo de prueba usa la plantilla real del alta, así que valida también
  el armado del mensaje y que el logo se sirva desde el static público.

- **Las dos altas del producto quedaron con el mismo criterio.** Además del ABM de
  usuarios existe el **alta rápida** de los modales de Becas
  (`usuario_alta_rapida`), que crea coordinadores, referentes y territoriales y
  **nunca enviaba ningún correo**: la clave la tipeaba el operador y la entregaba a
  mano. Ahora las dos pasan por `entregar_credenciales_provisorias`. Se unificó
  porque los territoriales —la población de RN-C6— se dan de alta justamente por
  ese camino.

- **El campo «Contraseña» del alta pasó a ser opcional.** Con la clave generada por
  el sistema, la que tipeaba el operador quedaba silenciosamente descartada: un
  campo obligatorio que no hacía nada. Ahora es opcional, con la ayuda que lo
  explica, y el formulario lo exige **solo cuando no hay correo** — el único caso en
  que el sistema no puede entregar la clave.

- **La marca de «debe cambiar la contraseña» se escribe sobre el `Profile` que el
  `User` trae cacheado, nunca con `update_or_create`.** La señal `save_user_profile`
  (post_save de `User`) re-guarda ese objeto cacheado en **cada** `user.save()`, así
  que un valor escrito por otra vía queda pisado por el estado viejo. El disparador
  más directo es `update_last_login`: al loguearse, Django guarda el usuario y con
  eso revierte la marca. Se detectó con un test que fallaba solo dentro del suite
  completo. Es una trampa general de este modelo, no solo de este cambio.

- **El gate vive en un middleware propio, después del de sesión única.** Ese
  middleware ya deja el `Profile` en la caché de relaciones del request, así que el
  chequeo no agrega consultas. Se excluye `/api/`: ahí la autenticación es por
  token de Mobile y el cambio de clave se resuelve en el navegador.

- **Los templates de correo quedan exceptuados de la regla HEX de la auditoría.**
  El HTML de correo necesita estilos inline y hex literal: ningún cliente de correo
  soporta CSS variables, y Outlook no respeta `<style>` de forma confiable. Los
  colores igual son los del kit (`--gradient-brand` = `#5059bc → #f98dff`), pero
  escritos a mano. Se excluyó el directorio `**/email/` en `scripts/design_audit.py`.

- **Se corrigió una inconsistencia previa de la auditoría.** `iter_files` aplicaba
  `EXCLUDE_PARTS` solo al recorrer directorios: una ruta de archivo explícita —que
  es como llega `--changed`— se saltaba las exclusiones. El modo `--hook` sí las
  aplicaba. Quedaron los tres caminos con el mismo filtro.

- **El logo del correo se sirve desde el static público del propio sitio**
  (`{{ protocol }}://{{ domain }}{% static ... %}`), no embebido por CID. Requiere
  que `/static/` sea accesible sin autenticación desde afuera, que es como ya está
  servido por nginx y WhiteNoise.

## Implementación

- **Alta de usuario:** el sistema genera una clave provisoria de 12 caracteres sin
  caracteres ambiguos (`0/O`, `1/l/I`), porque se lee de un correo y se tipea a
  mano. Se la asigna al usuario, marca el perfil como «debe cambiar la contraseña»
  y envía el correo con usuario, rol, dirección de acceso y la clave.
- **Primer ingreso:** hasta que la persona defina su contraseña, cualquier pantalla
  la devuelve a `/cambiar-contrasena/`. Solo queda disponible «Salir».
- **Si el envío falla o el usuario no tiene correo:** el usuario queda creado y el
  administrador ve la advertencia (RN-C3, comportamiento previo conservado). El
  aviso ahora indica que la persona puede entrar por «Olvidé mi contraseña», porque
  con el criterio nuevo la clave la conoce únicamente el correo que no salió.
- **Recupero:** el login tiene «¿Olvidaste tu contraseña?». El backend ya existía
  desde el Cambio 27; se le agregó la versión HTML del correo. La respuesta del
  formulario es neutra: un correo inexistente responde igual que uno existente.
- **Los dos correos** salen en multipart (texto + HTML), con encabezado de marca y
  pie compartidos.

## Archivos

- `config/settings.py` — backend por `EMAIL_HOST`, `EMAIL_TIMEOUT`,
  `EMAIL_ASUNTO_PREFIJO`, `EMAIL_SOPORTE`, `EMAIL_PIE_DIRECCION`,
  `PASSWORD_RESET_TIMEOUT`, middleware nuevo
- `.env.qa.example` — plantilla del bloque de correo, con la trampa del
  `ENVIRONMENT` reemplazada por el criterio nuevo
- `users/services/correo.py` — reemplaza a `users/services/invitations.py`
- `users/models/__init__.py` — `Profile.debe_cambiar_contrasena`
- `users/migrations/0022_profile_debe_cambiar_contrasena.py`
- `users/views/admin.py`, `users/views/auth.py`, `users/views/quick_create.py`,
  `users/views/__init__.py`
- `users/forms/__init__.py` — `password` opcional y exigido sin correo
- `users/templates/user/_alta_rapida_modal.html`
- `users/middleware.py` — `CambioContrasenaObligatorioMiddleware`
- `users/urls.py`
- `users/templates/user/email/` — `_encabezado.html`, `_pie.html`,
  `credenciales_usuario.{html,txt}`, `credenciales_usuario_asunto.txt`,
  `recupero_contrasena.{html,txt}`, `recupero_contrasena_asunto.txt`
  (los dos últimos vienen de `user/recuperar_contrasena_email.txt` y
  `user/recuperar_contrasena_asunto.txt`)
- `users/management/commands/diagnosticar_correo.py`
- `users/templates/user/cambiar_contrasena_obligatorio.html`
- `users/templates/user/login.html` — enlace de recupero
- `users/tests/test_credenciales.py` — reemplaza a `test_invitaciones.py`
- `scripts/design_audit.py` — exclusión de `**/email/` y filtro de `iter_files`
- `docs/client/funcionalidades/correos-credenciales.md` + índice y `mkdocs.yml`

## Base de datos

`users.0022` agrega `Profile.debe_cambiar_contrasena` (booleano, default `False`).
Segura sobre datos existentes: los perfiles ya creados quedan en `False`, es decir
sin cambio obligatorio, que es el comportamiento previo.

## Validación

- `manage.py check` sin errores.
- `scripts/compile_templates.py`: 318 templates compilados, 0 errores.
- `scripts/design_audit.py --changed`: 0 errores (2 warnings `OUTLINE`
  preexistentes en `login.html`, con su `--ring-brand` de reemplazo).
- `users.tests.test_credenciales` (9 pruebas nuevas, reemplazan a
  `test_invitaciones`) y `users.tests.test_password_reset`: **9/9 en verde** en el
  contenedor (Python 3.12). En el venv local (Python 3.14) 3 de ellas dan error por
  el bug conocido de `RequestContext.__copy__` con Django 4.2, que rompe cualquier
  test que renderice vía test client; por eso la verificación vale la del contenedor.
- Suite completa de `users` en el contenedor: **206 pruebas, 3 errores
  preexistentes** (`test_roles_abm`, `test_usuarios_roles_panel`:
  `IntegrityError` por `Programa` duplicado entre el seed y las fixtures).
  Se verificaron en un worktree limpio de HEAD: fallan igual sin estos cambios.
- `diagnosticar_correo` corrido desde el entorno de desarrollo: los pasos de
  configuración y de armado de los correos pasan, y el envío se verificó con backend en
  memoria. **El paso de conexión falla desde la red de desarrollo:** el 587 de
  `smtp.chaco.gob.ar` no responde ni con 25 s de espera, aunque el nombre resuelve
  (201.217.244.236). Es consistente con que el servidor solo acepte conexiones desde la
  red de la provincia, así que **el diagnóstico hay que correrlo desde el servidor**.
- **Sin verificar todavía:** el envío real contra `smtp.chaco.gob.ar`.

## Puesta en marcha en el servidor

1. Cargar en QA y en producción: `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`,
   `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_TIMEOUT`, `DEFAULT_FROM_EMAIL`
   (plantilla comentada en `.env.qa.example`; las credenciales no viven en el repo).
2. Verificar alcance de red a `smtp.chaco.gob.ar:587` desde el servidor.
3. `manage.py migrate` (trae `users.0022`).
4. `manage.py diagnosticar_correo` en cada ambiente — revisa variables, DNS,
   conexión autenticada y armado de los correos, y manda uno de prueba.
5. Alta de un usuario de prueba con casilla propia: confirmar que llega el correo,
   que la clave provisoria funciona y que el primer ingreso exige cambiarla.

## Pendientes / a definir

- **Casilla de soporte y dirección postal del pie.** El PM las dejó a definir. Salen
  de `EMAIL_SOPORTE` y `EMAIL_PIE_DIRECCION`: vacías, la línea no se renderiza, así
  que no queda un dato falso en el correo y no hace falta tocar código después.
- **Aprobación de los textos (#244).** Publicados en
  `docs/client/funcionalidades/correos-credenciales.md` para la firma del cliente.
- **Envío real (#245).** Pendiente de cargar las variables en QA y producción y de
  correr `diagnosticar_correo` desde el servidor.
- **Dominio de la casilla: `gob.ar` o `gov.ar`.** Infra pidió `gov.ar`; las credenciales
  que entregó el PM dicen `gob.ar`. Los dos nombres **resuelven a la misma IP**, así que
  `EMAIL_HOST` es indiferente: la duda afecta solo al usuario de autenticación y al
  remitente, que tienen que ser la misma dirección. Se resuelve corriendo
  `diagnosticar_correo` desde el servidor — si la casilla fuera la otra, el paso 2 corta
  con credenciales rechazadas.
- **Sin límite de intentos en el recupero.** No estaba en las reglas del #236: hoy
  se puede pedir el enlace tantas veces como se quiera. Queda anotado; no se
  implementó para no ampliar el alcance por decisión propia.

## Reversión

1. Revertir `users/urls.py`, `users/views/`, `users/middleware.py` y la línea del
   middleware en `config/settings.py`.
2. `manage.py migrate users 0021` (se pierde la marca de «debe cambiar la
   contraseña»: los usuarios pendientes quedan pudiendo operar con la provisoria).
3. Restaurar `users/services/invitations.py` y los templates de correo movidos.
4. La configuración SMTP puede quedar: con `EMAIL_HOST` vacío el sistema vuelve al
   backend de consola.

## Historial

No aplica: entrada nueva.

# Cómo continuar este registro

La estructura de cada entrada nueva está definida en **[Plantilla obligatoria de cada entrada](#plantilla-obligatoria-de-cada-entrada)**, al comienzo del archivo. El cierre de un desarrollo son cuatro pasos:

1. Agregar la entrada al final del archivo, con la plantilla completa.
2. Sumar su fila al **Índice**, con programa, **etiquetas**, solicitante, fecha y estado.
3. Si modificó algo ya registrado, agregar la sección **Historial** a la entrada afectada, sin borrar lo anterior.
4. Correr `scripts/requerimientos.py --check`: verifica que la entrada y el índice coincidan y que las etiquetas existan en el vocabulario. Tiene que dar OK.

La regla, el motivo de cada campo y la mitad de lectura —qué consultar **antes** de escribir código— están en **[Regla de oro](#regla-de-oro)** y en **[Cómo leerlo sin leerlo entero](#cómo-leerlo-sin-leerlo-entero)**.


---

# Cambio 40 — Formulario público de autocompletado: relevamientos con link de inscripción

🟡 **HECHO — 24/08/2026 — pendiente de merge y despliegue (PRs #301, #302, #303 y #304, apilados)**

| | |
|---|---|
| **Programa / módulo** | Becas · Portal |
| **Etiquetas** | `#relevamientos` `#datos` `#rbac` `#correo` `#ui` |
| **Solicitante** | Programa de Becas, a través del PM — pedido relevado y cerrado en sesión de análisis del 21/08/2026 (con adiciones del 22/08 y 24/08) |
| **Fecha del pedido** | 21/08/2026 |
| **Issue / épica** | Épica #69 · Análisis #289 · Tasks #290–#296 y #299 |
| **Partes afectadas** | Backoffice · Portal ciudadano (nueva superficie pública) · Servidor. **Mobile no se toca.** |
| **Migración** | `programas.0049` (tipo, token, correo, territorial nullable) + `programas.0050` (padrón) |

## Pedido original

> «Desde el programa de Becas quieren que un público objetivo se autocomplete: pasar un link con un formulario y que esa data llegue como si fuera desde la aplicación a un relevamiento. Mi idea era sumar en la configuración del relevamiento si es territorial o formulario público; en base a eso genera un relevamiento en la app o un link público.» Después: «siempre el primer paso antes de ingresar al form es poner número de documento y sexo […] valida si ya fue relevado […] después valida contra la Gran Base / RENAPER y te completa la información». Y el 24/08: «cuando se configura el relevamiento público la opción se valida con un Excel de dos columnas, documento y sexo, para dejar pasar o no al siguiente paso; esa validación la podemos configurar».

## Alcance acordado

- Nuevo **tipo de relevamiento**: territorial (exactamente como hoy) o **formulario público**, que genera un link con token y no tiene territorial ni zona.
- Flujo público en dos pasos: identificación (DNI + sexo, captcha) → formulario dinámico → comprobante. Lo enviado es un `Formulario` **ENVIADO** más, con su legajo ciudadano creado en el acto.
- **Padrón de habilitados** opcional por relevamiento (Excel documento/sexo) como lista blanca del paso 1.
- **Correo de confirmación configurable** por relevamiento.
- **Lanzamiento gateado por RBAC**: toda la superficie backoffice detrás de la capacidad `becas.relevamiento.publico`.
- **Afuera**: configurador de formularios propio, comunicar cupo o motivo de cierre, login del portal como requisito, avisos al backoffice por envío, editar el tipo de un relevamiento existente, pedir fecha de nacimiento en el paso 1.

## Decisiones tomadas

- **Sin form-builder: el público usa la misma definición dinámica que la app** (`definicion_formulario`: preguntas globales + requisitos heredados). Motivo: `Formulario.data` está keyed por pk de pregunta/requisito y la revisión renderiza contra eso; un form propio habría roto el «llega como si fuera de la app». Si hace falta acotar qué ve el público, el camino barato es un flag por pregunta (evolutivo aparte).
- **La ingesta no pasa por la API DRF** (exige token de territorial): una vista pública reutiliza los mismos servicios (`resolver_ciudadano_offline`, cupo bajo `select_for_update`, `client_uuid` idempotente). Para el backoffice el formulario es indistinguible: la bandeja de revisión, SIS, cupos y exportación **no se tocaron**.
- **Territorial pasa a nullable + constraint por tipo** en vez de un usuario sistema «Formulario público». Motivo: un usuario fantasma aparecería en filtros y reportes. Efecto colateral buscado: la API móvil filtra por territorial, así que los públicos desaparecen solos de la app (con test).
- **El público nace En curso y se cierra solo** al pasar `fecha_hasta`, reutilizando el registro de vencimientos (`becas.relevamiento_publico` → FINALIZADO). La pausa existente lo saca de servicio a mano. Sin operador que lo inicie no había alternativa.
- **Duplicado por convocatoria completa** (opción B del análisis), no por relevamiento: quien ya fue relevado en campo no puede volver a inscribirse por link. Se re-chequea dentro de la transacción del envío por si se coló otro entre paso 1 y envío.
- **Sin match en RENAPER/Gran Base se deja pasar igual**, con `validado_renaper=False` (mismo tratamiento que una carga manual del territorial); FALLECIDO corta. Decisión del cliente.
- **Los menores pueden inscribirse**; el paso 2 exige apoderado (RN-22, misma regla que la app; cumplir 18 hoy = mayor).
- **Solo datos básicos en la respuesta** (nombre, apellido, fecha de nacimiento): nunca domicilio. El paso 1 es un oráculo público y se acotó lo que revela. Se decidió **no** pedir fecha de nacimiento como control extra «por ahora»: quien sabe DNI y sexo de un tercero puede inscribirlo; la revisión humana es la mitigación.
- **Gateo por capacidad RBAC, no por variable de entorno.** Motivo: el pedido fue «que yo la configure y el cliente no la vea» en el mismo ambiente → per-usuario; encender es tildar la capacidad en Roles, sin deploy. El link en sí no se gatea (es público por diseño). El superusuario tiene bypass.
- **Padrón: Excel parseado al subir a una tabla indexada**, nunca leído por request; chequeo **antes** de RENAPER (ahorra consultas de no habilitados); normalización en ambos sentidos (dígitos; F/M sin mayúsculas); **reemplazo total, no merge**; el mensaje «no estás habilitado» revela pertenencia y se asumió como parte del requerimiento (la persona tiene que saber por qué no entra), acotado por captcha y rate limit.
- **Captcha aritmético autoalojado** en vez de reCAPTCHA/Turnstile o una dependencia nueva: los servicios externos exigirían salida a internet desde icore-srv y claves por ambiente. **Rate limiting sobre el cache de Django** (Redis en producción): cero infraestructura nueva.
- **GPS best-effort**: si la persona niega la geolocalización del navegador, el envío se acepta sin coordenadas (en campo el territorial la garantiza; desde la casa no tiene sentido bloquear).
- **El correo nunca rompe la inscripción**: cualquier falla de SMTP se loguea y el comprobante se muestra igual. Es exclusivo del flujo público (la API de campo no lo llama, con test).

## Implementación

- **Backoffice:** el modal de Nuevo relevamiento (listado, detalle de convocatoria y alta completa) tiene un selector de tipo visible solo con la capacidad; al elegir público se ocultan Territorial y Municipio/Localidad y aparecen Cupo, Padrón (archivo .xlsx) y el toggle de correo. El detalle muestra el link con botón copiar, la vigencia, el padrón cargado y la acción Cargar/Reemplazar padrón. Listados con badge de tipo; los públicos se ocultan a quien no tiene la capacidad y el POST con tipo público se rechaza server-side.
- **Portal** (`/inscripcion/<token>/`): paso 1 con DNI, sexo y verificación; en orden captcha → rate limit → padrón → duplicado → Gran Base. Pantallas: «Ya estás inscripto», «Formulario no disponible» (única para vencido/pausado/cupo/cerrado, sin motivo), 404 para token inválido, «No estás habilitado» inline. Paso 2 con datos validados en solo lectura (o carga manual sin match), contacto, preguntas y requisitos de la convocatoria con los seis tipos de campo, archivos JPG/PNG/PDF hasta 5 MB, apoderado y GPS. Comprobante con número de formulario y, si aplica, aviso del correo enviado (email enmascarado).
- **Ingesta:** `Formulario` ENVIADO con `datos_identificacion` en el contrato de la app, `validado_renaper` según origen, adjuntos como `AdjuntoFormulario`, legajo ciudadano creado o linkeado, `created_by` vacío.

## Archivos

`programas/models/__init__.py` · `programas/migrations/0049_*`, `0050_*` · `programas/forms.py` · `programas/views/relevamientos.py` · `programas/urls.py` · `programas/services/{vencimientos,padron,inscripcion_publica}.py` · `programas/api/views.py` · `programas/admin.py` · `programas/templates/programas/becas/relevamientos/*` · `core/rbac.py` · `portal/{urls,forms/inscripcion,services/inscripcion,views/inscripcion}.py` · `portal/templates/portal/inscripcion/*` · tests: `programas/tests/test_relevamiento_publico.py`, `test_padron.py`, `portal/tests/test_inscripcion*.py` · `docs/plans/2026-08-22-formulario-publico-becas-plan.md`.

## Base de datos

- `programas.0049`: `Relevamiento.tipo` (default TERRITORIAL), `token_publico` (UUID único, nulo en territoriales), `confirmar_por_email`, `territorial` nullable + `CheckConstraint` tipo↔territorial. **Segura sobre datos existentes**: todos los relevamientos previos quedan TERRITORIAL con su territorial intacto.
- `programas.0050`: `Relevamiento.padron_archivo` + tabla `PadronHabilitado` (relevamiento, dni, sexo; único por relevamiento+dni). Aditiva.

## Validación

- **~75 pruebas automáticas nuevas** en verde en local: modelo/constraint/API móvil/vistas gateadas (fase 1), cierre por vencimiento, parser y servicio del padrón, paso 1 completo (captcha, rate limit, padrón, duplicado por ambos campos, FALLECIDO, caído, privacidad de la respuesta), form dinámico (obligatorios, ids ajenos, archivos, RN-22 con borde de 18), ingesta (validado, linkeo sin duplicar, manual, idempotencia, cupo, duplicado colado, vencido), vista y correo (toggle on/off, SMTP caído, la API de campo no manda).
- Suites completas de Becas y Portal: solo los errores de entorno preexistentes (Python 3.14 renderizando plantillas), verificados contra `development` limpio en cada fase.
- `manage.py check` OK · `makemigrations --check` sin faltantes · `design_audit.py --changed` 0 errores / 0 warnings en las cuatro fases · `compile_templates.py` 324 plantillas, 0 errores · `check_design_agent.py` OK.
- **65 casos de QA** (`TC-290…299`) en los cuerpos de las tasks, a ejecutar por QA humano cuando los PRs mergeen.

## Puesta en marcha en el servidor

- Deploy estándar **con migración** (`manage.py migrate`; 0049 y 0050 son aditivas y de bajo riesgo).
- Tras el deploy **el cliente no ve nada**: ningún rol tiene `becas.relevamiento.publico`. Encender = asignarla desde la pantalla de Roles, sin deploy. Probar el link end-to-end **en test, no en producción** (un envío de prueba aparecería en la bandeja de revisión del cliente).
- El correo de confirmación depende del **Cambio 37 / #245 (SMTP)**; hasta entonces crear los públicos con el toggle apagado.
- Sin cron nuevo: el cierre por vencimiento corre dentro del `procesar_vencimientos` existente.

## Pendientes / a definir

- **Merge y despliegue** de los cuatro PRs apilados (#301 → #302 → #303 → #304) y ejecución de los 65 casos de QA.
- **Mockup desactualizado en dos detalles**: el modal del backoffice ya tiene el campo de padrón y «no estás habilitado» quedó como error inline del paso 1 (no pantalla propia).
- **Flag «visible en formulario público» por pregunta/requisito** si el programa necesita acotar el formulario del público (evolutivo aparte, ~4–6 h).
- Textos definitivos de pantallas y correo: se usaron los del mockup; los ajusta el programa cuando lo vea.
- El control extra de fecha de nacimiento en el paso 1 quedó descartado «por ahora»; retomarlo si aparece abuso.

## Reversión

Revertir los PRs en orden inverso (#304 → #301). Las migraciones se retroceden a `programas.0048`: antes de hacerlo con datos reales hay que **exportar los relevamientos públicos, sus padrones y los formularios ingresados por link** —el rollback elimina `tipo`, `token_publico`, `confirmar_por_email`, `padron_archivo` y la tabla `PadronHabilitado`, y los relevamientos sin territorial violarían la columna no nula—. Los formularios ya creados y sus legajos ciudadanos son datos comunes y se conservan.

## Historial

**24/08/2026 — Revisión de código de las cuatro fases (PR de correcciones, Fase 5).** Antes de mergear se revisó el diff completo y se corrigieron diez hallazgos; cinco eran errores 500 o salteos de reglas que los tests no cubrían:

- El reporte **Producción territorial** se caía con un solo relevamiento público (territorial nulo) → se excluyen del agrupado.
- El **rate limit** del paso 1 devolvía 500 en vez del mensaje (`add_error` sobre un form sin `cleaned_data`); un `except AttributeError` de los tests, puesto para tolerar el bug de render del entorno, lo tapaba → se corrigió el form y los tests ahora re-lanzan cualquier error que no sea ese bug conocido.
- **Pendientes RENAPER** generaba una opción `None` de territorial y rompía al filtrar → se excluyen públicos del selector y se validan los filtros GET.
- **Fecha de nacimiento no ISO** de Gran Base (`15/03/2010`) salteaba RN-22 (no exigía apoderado a un menor) y rompía el alta del ciudadano → `fecha_iso()` normaliza en `normalizar_persona`.
- El **gate RBAC** protegía listados y detalle pero no las vistas mutantes (finalizar, reabrir, reprogramar, cupo, pausa, revisión) → el chequeo vive ahora en `_assert_scope*` y en pausas.
- **Padrón**: los DNIs como float del Excel (`30123456.0`) quedaban con un cero de más y nadie matcheaba → cast numérico y rechazo de filas que no dan 7-8 dígitos. Y el padrón ahora **se re-verifica al enviar**, dentro de la transacción (un reemplazo entre paso 1 y envío ya no deja pasar).
- **Duplicado por convocatoria**: se lockea la convocatoria antes del chequeo (dos envíos simultáneos por relevamientos distintos podían pasar ambos) y RN-P5 quedó en una sola función compartida por portal e ingesta.
- Un relevamiento cambiado a público desde el admin quedaba **sin token** → se genera en `save()` siempre que falte.

**25/08/2026 - Fase 6 - segunda revision.** Se implementaron las correcciones de la segunda revision:

- El rate limit del paso 1 deja de confiar en el primer `X-Forwarded-For`: usa `X-Real-IP`, luego el ultimo forwarded, y el portal delega en el throttle central.
- El captcha del paso 1 se consume apenas valida correctamente, aun cuando despues el flujo vuelva con error.
- La idempotencia por `client_uuid` del formulario publico usa el helper tolerante a UUID texto/sin guiones compartido con la API.
- `formulario_revalidar_renaper` vuelve a pasar por `_assert_scope_formulario` antes de mutar datos del ciudadano.
- Si Gran Base valida identidad pero no entrega fecha normalizable, el paso 2 pide fecha de nacimiento y RN-22 vuelve a exigir apoderado para menores.
- El DNI del apoderado se normaliza y valida siempre que venga cargado, tambien en formularios de adultos.
- La creacion de relevamientos publicos con padron queda atomica: si falla la carga del padron no queda link abierto.
- Los listados de revision y pendientes RENAPER excluyen formularios publicos cuando el usuario no tiene `becas.relevamiento.publico`.
- Beneficiarios de convocatoria y su CSV aplican el mismo recorte de formularios publicos que los relevamientos visibles.
- El admin deja `tipo` como solo lectura al editar un relevamiento; la conversion territorial/publico queda bloqueada.
**Decisión pendiente detectada:** los formularios **RECHAZADO/BAJA** cuentan como «ya inscripto» y bloquean la reinscripción por link (mismo criterio que la app de campo). Quedó así por omisión; confirmar con el programa si el rechazo debe liberar el DNI.
