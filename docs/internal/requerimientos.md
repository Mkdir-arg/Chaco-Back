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
| `#gestion` | Tablero del Project, trazabilidad de issues y planes de prueba: qué se entregó y dónde figura |
| `#metodo` | Método de trabajo de los agentes: `AGENTS.md`, `QA.md`, `PM.md` y las convenciones que deben cumplir al crear issues |

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
| 8 | Incorporar programas | Becas / SIIS | `#siis` `#infra` | Cliente — DOCX | 07/08/2026 | 🟢 **Hecho — ECOM incorporó los cuatro programas al catálogo (27/08/2026)** | No desarrollada |
| 9 | Localidades como subsegmentos | Becas | `#convocatorias` `#datos` | Cliente — DOCX | 07/08/2026 | ⚪ **Se resolvió con el título de la convocatoria** | No desarrollada |
| 10 | Fecha desde/hasta del relevamiento | Becas · Mobile / API | `#relevamientos` `#mobile` `#api` | Cliente — DOCX | 07/08/2026 | 🟢 **Hecho** | `programas.0036` |
| 11 | Domicilio actual del ciudadano | Legajos | `#ui` `#datos` | Cliente — DOCX | 07/08/2026 | 🟢 **Hecho** | No |
| 12 | Desplegable de búsqueda de legajos | Legajos / Inicio | `#ui` | Cliente — DOCX | 07/08/2026 | 🟢 **Hecho** | No |
| 13 | Correo al crear usuario | Transversal / correo | `#correo` `#usuarios` `#infra` | Cliente — DOCX | 07/08/2026 | 🟢 **Hecho — SMTP de ECOM configurado en QA y producción (27/08/2026)** | No |
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
| 28 | Retirar el superusuario con credenciales en el código | Transversal / seguridad | `#infra` `#usuarios` `#sesion` | PM — surgió al revisar qué crea el bootstrap | 11/08/2026 | 🟢 **Hecho — contraseña del `admin` cambiada (27/08/2026)** | No |
| 29 | El bootstrap unificado en `seed_datos_base` | Transversal / infraestructura | `#infra` `#rbac` `#datos` | PM — vio que en el testing de ECOM faltaban roles de Becas | 11/08/2026 | 🟢 **Hecho** | No |
| 30 | La guía cubre el despliegue en Kubernetes desde cero | Transversal / infraestructura | `#infra` `#siis` | PM — pidió el repaso final de la guía para setear el sistema desde cero en Kubernetes | 11/08/2026 | 🟢 **Hecho** | No |
| 31 | La imagen autosuficiente para Kubernetes | Transversal / infraestructura | `#infra` `#relevamientos` `#ui` | PM — «que quede para levantarse en Kubernetes en todos los aspectos» | 11/08/2026 | 🟢 **Hecho — desplegado por ECOM (27/08/2026)** | No |
| 32 | Programas (SIIS) por encima de los segmentos | Becas / estructura | `#siis` `#convocatorias` `#requisitos` `#pausas` `#ui` | PM — pedido directo en sesión de trabajo | 13/08/2026 | 🟢 **Hecho** | `programas.0045` |
| 33 | Probar por qué SIIS no trae datos | Becas / SIIS | `#siis` `#infra` | PM — «quiero que pruebes la integración con SIIS, porque no me está trayendo datos» | 18/08/2026 | 🟢 **Hecho — credenciales cargadas; el catálogo trae datos (27/08/2026)** | No |
| 34 | Prevalidación SIIS al aprobar o rechazar formularios | Becas / revisión | `#siis` `#rbac` `#cupos` | Análisis #72 y revisión del PR #233 | 18/08/2026 | 🟢 **Hecho sobre el contrato vigente** | No |
| 35 | El login del backoffice muestra la contraseña con un botón ojo | Transversal / sesión | `#sesion` `#ui` | PM — mejora transversal aprobada el 14/08/2026, sin análisis | 14/08/2026 | 🟢 **Hecho** | No |
| 36 | El diseño de Dispositivos es todo lo contrario a lo que tiene que ser | Dispositivos | `#ui` | PM — pedido directo en sesión de trabajo | 19/08/2026 | 🟡 **Parcial — badges y solapas hechos; 4 hallazgos abiertos** | No |
| 37 | Credenciales por correo: clave provisoria al alta y recupero desde el login | Transversal / usuarios | `#usuarios` `#correo` `#sesion` `#infra` | PM — definiciones del 14/08/2026 (análisis #236) y credenciales SMTP entregadas el 20/08/2026 | 14/08/2026 | 🟡 **Parcial — SMTP configurado 27/08/2026; falta verificar el envío y aprobar los textos** | `users.0022` |
| 38 | Cerrar sesión da error 405 después de actualizar Django | Transversal / sesión | `#sesion` `#infra` `#ui` | PM — reportó el 405 al entrar a `/logout` | 20/08/2026 | 🟢 **Hecho** | No |
| 39 | En el login aparece el logo de Nodo en lugar del del Chaco | Transversal / marca | `#ui` `#sesion` `#infra` | PM — vio la marca del proveedor en la pantalla de acceso | 21/08/2026 | 🟢 **Hecho** | No |
| 40 | Corregir la redirección autenticada de `/dashboard/` | Transversal / ruteo | `#sesion` `#ui` | Hallazgo propio en la validación HTTP de #262 y la PR #284 | 20/08/2026 | 🟢 **Hecho** | No |
| 41 | Formulario público de autocompletado: relevamientos con link de inscripción | Becas · Portal | `#relevamientos` `#datos` `#rbac` `#correo` `#ui` | Programa de Becas, vía PM — sesión de análisis del 21/08/2026 (análisis #289) | 21/08/2026 | 🟢 **Hecho — mergeado (PR #306); Gran Base configurada 27/08/2026** | `programas.0049` + `programas.0050` + `users.0025` |
| 42 | El portal ciudadano quedó viejo: marca, textos y contenido de la home | Portal | `#ui` `#textos` | PM — «actualiza el diseño y los nombres de datanach.ecomdev.ar/portal/ ya que quedó viejo» | 26/08/2026 | 🟢 **Hecho** | No |
| 43 | Sacar el fondo animado del formulario de inscripción: shell propio «panel de marca» | Portal / inscripción pública | `#ui` `#relevamientos` | PM — «el fondo animado lo tendríamos que borrar»; eligió la Opción B de tres mockups | 26/08/2026 | 🟢 **Hecho** | No |
| 44 | Avisar por correo al ciudadano cuando se resuelve su formulario | Becas / revisión · Portal | `#correo` `#relevamientos` `#cupos` `#ui` `#infra` | PM — pedido directo en sesión de trabajo | 26/08/2026 | 🟡 **Implementado — activo con el SMTP de ECOM; falta verificar el envío real** | `programas.0053` |
| 45 | Documentar el Programa Becas al detalle: el sistema construido como evolución de la V1 | Becas · Documentación | `#textos` `#ui` `#relevamientos` | PM — «leer toda la documentación pública de Becas y actualizarla al detalle con lo que tenemos del proceso» | 26/08/2026 | 🟢 **Hecho — publicado en GitHub Pages** | No |
| 46 | La API de campo aceptaba cualquier archivo, de cualquier peso | Becas · Mobile / API | `#api` `#mobile` `#datos` | Hallazgo propio en la revisión del flujo público pedida por el PM | 26/08/2026 | 🟢 **Hecho — falta verificar contra la app antes de producción** | No |
| 47 | El tablero no reflejaba que el formulario público ya estaba entregado | Becas · Gestión | `#gestion` `#relevamientos` | PM — «las épicas y los task sobre el formulario público de los relevamientos de becas en qué estado están?» | 27/08/2026 | 🟡 **Parcial — tablero al día; plan de pruebas redactado sin publicar** | No |
| 48 | Analizar todo el diseño de Dispositivos, funcional y sobre todo front | Dispositivos | `#ui` `#datos` `#rbac` | PM — pedido directo en sesión de trabajo: «quiero analizar todo el diseño a nivel funcional y más que nada a diseño front del programa de dispositivos» | 26/08/2026 | 🟢 **Hecho — diagnóstico entregado; la remediación queda en #310-#323** | No requiere |
| 49 | Etiquetar en GitHub a qué programa pertenece cada tarea | Transversal / gestión | `#gestion` `#metodo` | PM — pedido directo en sesión de trabajo | 27/08/2026 | 🟢 **Hecho** | No |
| 50 | ECOM desbloqueó las dependencias externas: SMTP, Gran Base, SIIS y despliegue | Transversal · Becas / integraciones | `#infra` `#correo` `#siis` `#gestion` | PM — reporte punto por punto sobre la lista de pendientes de este archivo | 27/08/2026 | 🟡 **Parcial — ocho dependencias cerradas; falta el endpoint de salida de SIIS** | No requiere |
| 51 | El panel de marca del formulario de inscripción se estiraba con el formulario | Portal / inscripción pública | `#ui` `#relevamientos` | PM — «si el form es muy extenso se agranda y eso tendría que ser fijo… cuando escroleás el form eso está fijo y el form solo va para abajo» | 27/08/2026 | 🟢 **Hecho** | No requiere |
| 52 | El formulario público moría en un 403 de CSRF si el backoffice estaba abierto | Portal / inscripción pública | `#ui` `#sesion` `#relevamientos` | PM — reportó el 403 en producción sobre un link real: «el link es público, tiene que ser indistinto si es backoffice» | 27/08/2026 | 🟢 **Hecho** | No requiere |
| 53 | «Relevamiento» y «caso» son dos cosas y la UI usaba la misma palabra para las dos | Becas / textos · revisión | `#textos` `#ui` `#metodo` | PM — fijó el vocabulario en sesión de trabajo: «relevamiento = parametría con sus estados; casos = personas que completaron el formulario» | 27/08/2026 | 🟢 **Hecho** | No requiere |
| 54 | Un relevamiento en revisión no se podía volver a poner en curso | Becas / relevamientos | `#relevamientos` `#rbac` `#ui` `#convocatorias` | PM — «cuando está en estado En revisión no lo puedo pasar a En curso, como para abrirlo de nuevo» | 27/08/2026 | 🟢 **Hecho** | No requiere |
| 55 | Validar la identidad a mano cuando Base de Personas no puede validar | Becas / revisión | `#siis` `#rbac` `#ui` `#datos` | PM — «hoy en día no puedo validar; podemos agregar una funcionalidad para, aunque no valide, poder forzar la validación» | 27/08/2026 | 🟢 **Hecho** | `programas.0054` |
| 56 | Los selectores se pueden mostrar como buscador con píldoras | Becas · configuración → Portal | `#ui` `#relevamientos` `#datos` | PM — «cuando el campo es alguno de los dos tipo de selector, quiero poder configurar cuándo se ve como buscador con selector y el valor seleccionado se ve en píldora» | 28/08/2026 | 🟢 **Hecho** | `programas.0055` |
| 57 | Padrón de la convocatoria como fuente de identidad (Base de Personas apagada por configuración) | Becas · identificación | `#relevamientos` `#siis` `#datos` `#infra` | PM — «la Gran Base no está funcionando; vamos a agregar esos datos al Excel y autocompletar de ahí» | 28/08/2026 | 🟢 **Hecho — desarrollo de #327–#333 (28/08/2026); quedan las pruebas #334/#335** | `programas.0056` |
| 58 | Constructor de formularios por convocatoria: grupos, textos, condiciones y campos del legajo | Becas · configuración → Portal · App | `#relevamientos` `#ui` `#datos` `#rbac` | PM — «al configurar la convocatoria, Configurar formulario: el diseño y al lado cómo quedaría publicado; los requisitos son campos que se arrastran» | 28/08/2026 | 🟡 **Analizado — análisis #326 Definido, mockups entregados; tasks #336–#356 en Backlog (150 h)** | Pendiente (catálogo, diseño, caso) |
| 59 | El link público muestra el contacto del programa y «no disponible» distingue si todavía no abrió | Portal / inscripción pública | `#textos` `#ui` `#relevamientos` | PM — «cambiale los datos por consultasincentivojunvetud@gmail.com - Whatsapp 3625153720. Solo en caso de problemas técnicos» y «opción A que todavía no está abierto, opción B que está cerrado: que se vea un texto o el otro» | 31/08/2026 | 🟢 **Hecho** | No requiere |
| 60 | El contacto del programa sale del paso 1 del link público | Portal / inscripción pública | `#textos` `#ui` `#relevamientos` | PM — «en la página 1 tenemos consultasincentivojunvetud@gmail.com · WhatsApp 3625153720: eliminá esos datos; en la página 2 dejalos» | 03/09/2026 | 🟢 **Hecho** | No requiere |
| 61 | El mensaje de rechazo del paso 1 deja de mostrar el teléfono del organismo | Portal / inscripción pública | `#textos` `#ui` `#relevamientos` | PM — «también borrá ese mensaje», sobre la alerta roja «No podés inscribirte con ese documento. Si creés que es un error, comunicate con el programa al +54 362 430-0002» | 03/09/2026 | 🟢 **Hecho** | No requiere |
| 62 | El paso 1 vuelve a mostrar el pie, pero solo con la casilla | Portal / inscripción pública | `#textos` `#ui` `#relevamientos` | PM — «volvé a agregar en la primera página el mensaje donde estaba el correo y el número, pero solo agregá el correo» | 03/09/2026 | 🟢 **Hecho** | No requiere |
| 63 | El login tarda por el hash de la contraseña y el HTTP corre en un solo proceso | Transversal / login e infraestructura de ejecución | `#sesion` `#infra` | PM — en sesión: «noto que la carga de algunas pantallas tardan más de lo común, ejemplo el login» y «vamos con tema desarrollo y armá una rama para este cambio» | 03/09/2026 | 🟡 **Parcial — código listo en la rama `perf/login-argon2-gunicorn`; falta desplegar en icore-srv y que ECOM decida el modo gunicorn** | No requiere |
| 64 | Solapa «Dashboard» en el programa Becas: métricas, filtros y exportación | Becas / configuración del programa | `#ui` `#convocatorias` `#relevamientos` `#datos` | PM — en sesión: «vamos a armar un dashboard en el programa Becas… al lado de Requisitos del programa quiero agregar una solapa de dashboard, tiene que ser a nivel visual y poder exportar» | 05/09/2026 | 🟢 **Hecho — en producción de ECOM desde el 05/09/2026 (releases 43ffddf, 55d842e y fc740b8); falta QA formal #374 y la validación de las 86 h por el Ministerio** | No requiere |

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

🟢 **HECHO — 27/08/2026 · ECOM INCORPORÓ LOS CUATRO PROGRAMAS AL CATÁLOGO**

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

## Historial

**27/08/2026 — ECOM incorporó los programas al catálogo y la entrada quedó cerrada.** El PM
confirmó que los cuatro programas del pedido ya están en el catálogo de SIIS, así que el
semáforo pasa de 🟡 «depende de ECOM» a 🟢. La sección *Estado* de arriba —dos programas
vinculados al 11/08/2026— queda como foto de ese día y **ya no describe el catálogo actual**.
Del lado del Backoffice no hubo desarrollo, tal como preveían las decisiones tomadas: el
selector consume el catálogo, así que los programas nuevos aparecieron solos. Lo que resta es
operativo y no de código: **vincular a su programa los segmentos que hoy no lo tienen** —el
Cambio 32 lo volvió obligatorio en el alta, pero no fue retroactivo, y esos segmentos quedan
visibles con «—» en la columna Programa—. El desbloqueo completo está registrado en el
**Cambio 50**.

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

**27/08/2026 — el SMTP de ECOM quedó configurado en QA y en producción.** Con eso se cierra el
pendiente que mantenía esta entrada en 🟡 desde el 07/08/2026: la tabla de variables que le
pedía a Infra está cargada y el backend deja de ser el de consola. La casilla quedó en el
dominio **`gov.ar`**, que era la duda abierta del Cambio 37. Dos aclaraciones de alcance para
que el verde no se lea de más: el circuito de correo vigente es el del **Cambio 37** (clave
provisoria, no enlace temporal), y **configurado no es verificado** — que el envío real
funcione se comprueba corriendo `diagnosticar_correo` desde el servidor, y ese paso sigue
pendiente allá. Ver **Cambio 50**.

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

- ~~QA: ¿va a tomar `…/main:latest`? ¿Con qué URL?~~ **Respondido por DevOps de ECOM el 26/08/2026: no hay entorno de QA.** Son dos entornos, y `…/main:latest` es **producción**, con despliegue automático al publicarse la imagen (5 a 7 minutos). Ver `docs/internal/branching.md`.
- ¿Cómo quieren que manejemos `main`: la actualizamos en cada release nuestra, o solo cuando avisemos que hay una versión estable? Ahora cada push construye —y, sabiendo que `main` es producción, **cada push despliega**: la pregunta pasa a ser cuándo publicamos, no si construye.
- ¿Las variables de entorno de testing están cargadas (base, SIIS, correo)?
- Accesos a ArgoCD con usuario de dominio.
- El sync periódico de SIIS en Kubernetes sería un CronJob, o sea configuración: ¿lo definen ellos?

De nuestro lado:

- **La app móvil apunta al entorno viejo.** Si la URL nueva existe para que la APK conecte sin bloqueos, hay que cambiar la URL base en el repositorio de la app y regenerar el APK. Vive en otro repo (`Chaco-mobile`), así que no entra en este cambio.

## Reversión

Borrar `.gitlab-ci.yml`, su línea en `.gitattributes` y los dos nombres agregados al guard. Sin efecto sobre la aplicación: se vuelve al estado en que el release no lleva pipeline y las ramas espejadas se actualizan sin construir imagen.

## Historial

No aplica: entrada nueva.

**27/08/2026 — ECOM confirmó las variables de testing y desplegó el ambiente.** De la lista
*Para ECOM* se cierra una sola pregunta, la de si **las variables de entorno de testing están
cargadas** (base, SIIS y correo): lo están, y el ambiente quedó desplegado. **El resto de esa
lista sigue abierto** y este desbloqueo no lo toca — URL de QA, política de actualización de
`main`, accesos a ArgoCD con usuario de dominio y quién define el CronJob de sync de SIIS. De
nuestro lado también sigue en pie que **la app móvil apunta al entorno viejo**: cambiar la URL
base en `Chaco-mobile` y regenerar el APK. Ver **Cambio 50**.

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

🟢 **HECHO — 11/08/2026 · CONTRASEÑA DEL `admin` CAMBIADA EL 27/08/2026**

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

**27/08/2026 — la contraseña del `admin` quedó cambiada y la exposición está cerrada.** Era el
único pendiente que mantenía la entrada en 🟡: el superusuario salió del código el 11/08/2026,
pero el usuario ya creado seguía usando la credencial que había estado versionada, así que la
exposición real no se cerraba hasta hoy. ECOM confirmó el cambio y el semáforo pasa a 🟢.
Siguen abiertos los dos pendientes menores, que no son de seguridad: en un entorno local nuevo
el harness de E2E necesita crear el usuario a mano (receta no interactiva en `setup.md`), y
`RUN_CREAR_PROGRAMAS` de `docker-compose.prod.yml` sigue siendo configuración muerta que
conviene retirar. Ver **Cambio 50**.

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

**27/08/2026 — ECOM corrió el sembrado en testing.** Era el único pendiente de la entrada. Con
`seed_datos_base` ejecutado quedan creados los cinco grupos de Becas que faltaban en su
ambiente, que es el desfasaje que originó este cambio. Ver **Cambio 50**.

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

**27/08/2026 — ECOM desplegó el ambiente completo.** Con el despliegue hecho, el primer
pendiente queda resuelto por la vía de los hechos: la duda del entrypoint (completo vs.
`command` propio) ya está contestada en el ambiente real, y el Historial del Cambio 31 del
13/08/2026 documenta cómo — initContainer `bootstrap` en exit 0 y un solo deployment con
daphne. El segundo pendiente **no** se cierra con esto: del espejado de `.env.qa.example` no
hay confirmación explícita, y que su ambiente levante con las variables correctas no prueba que
el archivo de ejemplo haya viajado. Conviene verificarlo en la próxima pasada de
`/pushGitLabecom` en vez de asumirlo. Ver **Cambio 50**.

# Cambio 31 — La imagen autosuficiente para Kubernetes

🟢 **HECHO — 11/08/2026 · DESPLEGADO EL 27/08/2026**

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

**27/08/2026 — quedó desplegado, y el punto 3 de arriba caducó.** ECOM confirmó el despliegue
del ambiente completo, que era el pendiente que mantenía el semáforo en amarillo; la entrada
pasa a 🟢. Junto con eso hay que corregir el **punto 3 del bloque anterior**, que registró como
trampa que «el backend SMTP solo se activa con `ENVIRONMENT=prd`»: **ese criterio ya no rige**.
El Cambio 37 lo reescribió y hoy `config/settings.py` elige el backend **por la presencia de
`EMAIL_HOST`**, no por el `ENVIRONMENT`, con el motivo comentado en el propio archivo («qa usa
el mismo SMTP que prd, y el dev local sigue en consola sin configurar nada»). O sea que un QA
con SMTP cargado **manda correo real**, y lo único que lo distingue en la bandeja es el prefijo
`[QA]` del asunto (`EMAIL_ASUNTO_PREFIJO`). Ver **Cambio 50**.

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

## Historial

**27/08/2026 — la integración quedó verificada contra el servicio real, en su mitad de
lectura.** ECOM cargó las credenciales de SIIS y el sistema **trae el catálogo de programas y
valida personas** contra el servicio: los pasos 3 y 4 del diagnóstico dejan de ser teóricos y
no apareció ningún cambio de contrato en el catálogo, que era el riesgo que este pendiente
vigilaba. El segundo pendiente, las credenciales de **producción**, también se cierra: el
deploy de ECOM las incluyó.

Lo que **no** está resuelto es la otra mitad de la integración: **SIIS todavía no expone el
endpoint de salida** para informarle los beneficiarios confirmados con beca. Hoy
`programas/services/siis.py` es solo de lectura —`listar_programas`, `listar_programas_todos`
y `validar_compatibilidad`— y no hay método de escritura porque no hay contra qué escribir; sin
el contrato, implementarlo sería una apuesta. Queda registrado como pendiente 1 del **Cambio
50** y es lo que mantiene el análisis #72 en *En análisis*.

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

**26/08/2026 — el Cambio 48 reauditó el programa y corrigió uno de estos pendientes.**
La segunda auditoría (ver Cambio 48) verificó que **lo ejecutado acá sigue en pie** —badges
de estado y solapas Alpine reales— y confirmó que los cuatro pendientes seguían abiertos.
Sobre el **pendiente 3** cambia la salida: acá se propuso unificar los dos handlers de
confirmación tomando como modelo `becas/_confirm_js.html`, y **eso no corresponde**. Al
leerlo se comprobó que ese include está montado sobre `ModernModal`, que el agente canónico
clasifica como *Legacy solo mantenimiento*, mientras SweetAlert2 —lo que ya usa
Dispositivos— figura como *Canónico reutilizable, condicionado*. La salida correcta es
extraer un `dispositivos/_confirm_js.html` propio, no copiar Becas: copiarlo sería ir para
atrás. Los pendientes 1 y 3 quedan tomados por la task #321, el 2 por la #317, y el 4 sigue
fuera de alcance por requerir definición de producto (#179).

# Cambio 37 — Credenciales por correo: clave provisoria al alta y recupero desde el login

🟡 **PARCIAL — 20/08/2026 · el SMTP quedó configurado el 27/08/2026; falta verificar el envío y aprobar los textos**

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

**27/08/2026 — se cerraron dos de los cinco pendientes: el SMTP y el dominio.** ECOM configuró
el servidor de correo en **QA y en producción**, y el dominio de la casilla quedó definido en
**`gov.ar`**. Esa era la duda que esta entrada dejó abierta entre `gob.ar` y `gov.ar`, y se
resuelve sin tocar código: como los dos nombres resuelven a la misma IP, `EMAIL_HOST` era
indiferente y lo que faltaba definir era el usuario de autenticación y el remitente, que ahora
son `gov.ar`.

El semáforo **sigue en 🟡 a propósito**: que el SMTP esté configurado no es que el envío esté
verificado, y marcar esto en verde sería registrar como probado algo que nadie vio salir. Falta
correr `diagnosticar_correo` desde el servidor (task #245) y falta la **aprobación de los
textos (#244)**, que la firma el cliente y no la desbloquea Infra. Siguen abiertos también la
casilla de soporte y la dirección postal del pie, y el límite de intentos en el recupero. Ver
**Cambio 50**.

# Cambio 40 — Corregir la redirección autenticada de `/dashboard/`

🟢 **HECHO — 24/08/2026**

| | |
|---|---|
| **Programa / módulo** | Transversal / ruteo |
| **Etiquetas** | `#sesion` `#ui` |
| **Solicitante** | Hallazgo propio en la validación HTTP de #262 y la PR #284 |
| **Fecha del pedido** | 20/08/2026 |
| **Issue / épica** | #285 (padre #262, PR relacionada #284) |
| **Partes afectadas** | Backoffice |
| **Migración** | No requiere |

## Pedido original

«Corregir la redirección autenticada de `/dashboard/`: no debe terminar en `/`
(login), sino en `/inicio/`.» Del issue #285, que además pide eliminar la
resolución ambigua de `dashboard:inicio`, conservar `login_required` y agregar la
regresión.

## Alcance acordado

Entra: el destino del redirect de `/dashboard/`, su regresión automática y la
verificación de que la ruta deje de clasificarse como redirect al login.

Queda afuera: mover o renombrar `dashboard:inicio` —la vista del dashboard sigue
montada donde estaba— y cualquier cambio en la pantalla de inicio.

## Decisiones tomadas

- **El alias apunta al nombre explícito `core:inicio`, no a `dashboard:inicio`.**
  `dashboard.urls` está incluido en la raíz (`path("", include("dashboard.urls"))`)
  y su vista `inicio` vive en `path("", ...)`, así que `reverse("dashboard:inicio")`
  devolvía `/`: exactamente la misma URL que `users:login`. El redirect era correcto
  en la intención y equivocado en el destino.
- **No se toca el montaje de `dashboard.urls`.** Desambiguar moviendo esa app a un
  prefijo propio arrastraría todos sus endpoints de API, y no es lo que pide el
  issue: alcanza con que el alias nombre su destino sin ambigüedad.
- **El redirect sigue siendo temporal (302) y detrás de `login_required`.** La sonda
  `scripts/perf_http_probe.py` espera 302 en esa ruta.

## Implementación

Un usuario autenticado que entra a `/dashboard/` aterriza en `/inicio/` en un solo
salto. Un usuario anónimo sigue yendo al login con `?next=/dashboard/`.

## Archivos

- `core/urls.py` — `dashboard_redirect` redirige a `core:inicio`, con el comentario
  que explica por qué el nombre anterior era ambiguo.
- `core/tests/test_dashboard_redirect.py` — nuevo: regresión del destino y de la
  protección anónima.

## Base de datos

No requiere.

## Validación

- `manage.py test core.tests.test_dashboard_redirect core.tests.test_url_namespaces`
  → 8 tests OK.
- **La regresión se verificó en rojo**: contra el código anterior, 2 de los 3 casos
  nuevos fallan con `'/' != '/inicio/'`; el de protección anónima pasa en ambos
  lados, como corresponde.
- `manage.py check` → sin issues.
- `ruff check` y `ruff format --check` sobre los dos archivos → limpios.
- `scripts/design_audit.py --changed` → 0 errores, 0 warnings (no se tocó UI).
- Verificación HTTP sobre el stack local, sin seguir redirects: anónimo
  `/dashboard/` → 302 a `/?next=/dashboard/`; autenticado → 302 a `/inicio/` (antes
  era 302 a `/`). Siguiendo redirects bajó de 2 saltos a 1.

## Puesta en marcha en el servidor

No requiere: solo código.

## Pendientes / a definir

- **La sonda `scripts/perf_http_probe.py` no se corrió completa.** Su manifiesto
  necesita fixtures propias (`ciudadano_pk`, `conversacion_pk`, `relevamiento_pk`) y
  `seed_perf` exige una base llamada exactamente `chaco_perf_ci`, o sea otro stack.
  El criterio quedó cubierto de forma equivalente: `is_login_redirect()` marca todo
  302 cuyo `Location` tenga path `/`, y ahora el destino es `/inicio/`.
- **`dashboard:inicio` sigue reverseando a `/`.** Ya no lo usa nadie para redirigir,
  pero el nombre continúa siendo ambiguo para quien lo tome a futuro.

## Reversión

1. Revertir `core/urls.py`: una línea, el destino del redirect.
2. Borrar `core/tests/test_dashboard_redirect.py`.

No se pierden datos.

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

# Cambio 41 — Formulario público de autocompletado: relevamientos con link de inscripción

🟢 **HECHO — 24/08/2026 · mergeado a `development` el 25/08/2026 (PR #306, integra las fases 1 a 5) y espejado al GitLab de ECOM (testing y QA)**

| | |
|---|---|
| **Programa / módulo** | Becas · Portal |
| **Etiquetas** | `#relevamientos` `#datos` `#rbac` `#correo` `#ui` |
| **Solicitante** | Programa de Becas, a través del PM — pedido relevado y cerrado en sesión de análisis del 21/08/2026 (con adiciones del 22/08 y 24/08) |
| **Fecha del pedido** | 21/08/2026 |
| **Issue / épica** | Épica #69 · Análisis #289 · Tasks #290–#296 y #299 |
| **Partes afectadas** | Backoffice · Portal ciudadano (nueva superficie pública) · Servidor. **Mobile no se toca.** |
| **Migración** | `programas.0049` (tipo, token, correo, territorial nullable) + `programas.0050` (padrón) + `users.0025` (la capacidad al rol Administrador) |

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
- Tras el deploy **los roles del cliente no ven nada**: `seed_becas` sigue excluyendo `becas.relevamiento.publico` de los roles de Becas y encenderlos es tildarla en la pantalla de Roles, sin deploy. La excepción es el rol **`Administrador`**, que la recibe en `users.0025` (ver Historial del 25/08/2026). Probar el link end-to-end **en test, no en producción** (un envío de prueba aparecería en la bandeja de revisión del cliente).
- El correo de confirmación depende del **Cambio 37 / #245 (SMTP)**; hasta entonces crear los públicos con el toggle apagado.
- Sin cron nuevo: el cierre por vencimiento corre dentro del `procesar_vencimientos` existente.

## Pendientes / a definir

- **Configurar Base de Personas (Gran Base) en testing y QA**: `PERSONAS_API_CLIENT_ID`, `PERSONAS_API_CLIENT_SECRET` y `PERSONAS_API_ENTIDAD_UUID` están vacías en el deployment, así que el paso 1 nunca precarga y toda inscripción queda `origen=manual`. Las provee ECOM; se verificaron contra su API el 25/08/2026 (ver Historial). No requiere deploy de código, solo variables de entorno.
- **Ejecución de los 65 casos de QA** sobre testing (el merge y el despliegue se cerraron el 25/08/2026: PR #306 → `development` → release `main` → espejo a ECOM).
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
**25/08/2026 — Merge, despliegue y la capacidad para el rol `Administrador`.** Las cinco fases se
integraron en un solo merge a `development` (PR #306: CI 11/11 en verde, 889 tests OK) y se espejaron al
GitLab de ECOM (`test` → testing, `main` → QA). Dos cosas salieron de ahí:

- **Presupuesto de consultas del alta de relevamiento** (`carga_relevamiento` 21 → 24). La `CheckConstraint`
  nueva tipo↔territorial se valida en el `full_clean` del ModelForm y, dentro de la transacción del
  `TestCase`, Django 5.2 envuelve ese `SELECT` en un `atomic` (SAVEPOINT + SELECT + RELEASE = 3 consultas;
  1 en producción). De paso se quitó el `transaction.atomic()` que `RelevamientoForm.save` abría en **cada**
  alta, anidado con el que `Relevamiento.save` ya abre para numerar: ahora solo se abre cuando hay padrón
  que cargar, que es el caso donde relevamiento y habilitados tienen que ser todo-o-nada.
- **El rol `Administrador` recibe `becas.relevamiento.publico` por migración** (`users.0025`), por decisión
  del PM. El gate de RN-P13 dejaba la capacidad fuera de los seeds para encenderla desde la pantalla de
  Roles, pero ese rol es **protegido** y la pantalla rechaza su edición, así que para él no había camino
  manual: el único mecanismo que corre en cada deploy es una migración (el entrypoint ejecuta `migrate`, no
  los seeds). **Consecuencia asumida:** en producción los usuarios con rol Administrador van a ver la
  superficie del formulario público desde el próximo release; el gate sigue en pie para los roles de Becas
  del cliente, que se encienden a mano. Es coherente con `seed_rbac`, que ya le asigna al Administrador
  todas las capacidades del catálogo.

**25/08/2026 — Prueba en testing y comando de diagnóstico de integraciones.** Al probar el link en testing el
paso 1 aceptó el padrón y el captcha, pero el paso 2 mostró «No pudimos validar tus datos automáticamente». No era
un bug: con las credenciales de Base de Personas sin cargar, `PersonasAPIClient.consultar` corta **antes de salir a
la red**, devuelve error de configuración y el flujo sigue como `origen=manual`, exactamente como está diseñado. El
problema es que las tres causas posibles —credenciales ausentes, servicio que rechaza, o DNI que no está en la
fuente— se ven **idénticas** en pantalla y las dos primeras no dejan rastro en el log.

Se verificó contra la API de ECOM con las credenciales del organismo que la integración funciona: token OK y la
consulta de un DNI real devolvió apellido, nombre y fecha de nacimiento normalizada (el DNI que se probó primero
respondió `código 12 — NO SE ENCONTRO INFORMACION`, o sea que no está en la fuente 13; eso no es una falla).

Para no volver a diagnosticar a ciegas se agregó **`manage.py diagnosticar_integraciones`**: audita las variables de
todas las integraciones (Base de Personas, RENAPER, SIIS, correo, caché y base), prueba Gran Base de verdad con
`--dni`/`--sexo` diciendo si el formulario público precargaría, y con `--relevamiento`/`--token` audita por qué un
link acepta o no inscripciones —los cuatro motivos que comparten la pantalla «Formulario no disponible»— más si el
DNI está en el padrón o ya se inscribió. Nunca imprime secretos (informa presencia y largo) y devuelve código de
salida distinto de 0 si algo falla, para usarlo como gate de despliegue.

**26/08/2026 — El toggle de correo dejó de ser exclusivo del alta pública (Cambio 44).** Esta entrada decía que al
elegir tipo público «aparecen Cupo, Padrón y el toggle de correo», y `RelevamientoForm` lo removía junto con `tipo`
y `padron` cuando el usuario no tenía `becas.relevamiento.publico`. El Cambio 44 usa el mismo
`confirmar_por_email` para avisar cómo se resolvió un formulario —y eso pasa igual en los territoriales—, así que
el campo se ofrece ahora en los dos tipos y salió del `fieldset` condicionado; `tipo` y `padron` **siguen** gateados
por RN-P13. Lo que **no** cambió es la decisión de arriba: el comprobante de inscripción sigue siendo exclusivo del
flujo público y la API de campo no lo llama. También cambiaron la etiqueta y el `help_text` del campo
(`programas.0053`, solo metadatos), que hablaban únicamente del comprobante.

**25/08/2026 — Comprobante de inscripción con plantilla de marca.** El correo del comprobante salía en texto
plano; ahora va en las dos versiones —texto y HTML— como el resto de los correos del sistema, reusando el
encabezado y el pie compartidos (`user/email/_encabezado.html` y `_pie.html`). La plantilla está apuntada al
**ciudadano**, no al backoffice: el encabezado dice «Portal Ciudadano» (el include quedó parametrizado con
`encabezado_seccion`, default «Backoffice»), muestra el número de formulario con la misma frase que la pantalla
de comprobante, los datos de la inscripción (programa, documento, fecha y hora) y el teléfono del programa. El
envío pasó de `send_mail` a `EmailMultiAlternatives`; la vista le pasa protocolo y host para que el logo cargue
con URL absoluta, con `settings.DOMINIO` como respaldo. Sigue sin romper la inscripción si el SMTP falla.

**26/08/2026 — Revisión de seguridad de la superficie pública y endurecimiento.** El PM pidió auditar el link de
inscripción. Se revisó el código con tres lentes (abuso y enumeración, archivos y datos personales, configuración y
cabeceras) y se contrastó contra el entorno de testing en vivo. Se corrigió todo lo hallado **menos dos cosas que el
PM dejó fuera de alcance a propósito**: que una inscripción anónima cree un `Ciudadano` (y que eso saltee la
verificación RENAPER del registro del portal) y que el paso 2 muestre nombre, apellido y fecha de nacimiento de
cualquier documento. **Las dos siguen abiertas.**

Lo que se cerró:

- **Cadena de suministro.** El portal cargaba Alpine desde `unpkg` con versión **flotante** (`3.x.x`) en la misma
  página donde el ciudadano tipea su documento; el backoffice, otro Alpine desde `jsdelivr`, **SweetAlert2 en 17
  pantallas**, Chart.js, Bootstrap, AdminLTE, Font Awesome y la tipografía. Todo quedó autoalojado en
  `static/vendor/` con versión fija. La aplicación ya no carga **ningún** recurso de terceros salvo el reCAPTCHA, y
  un test recorre las plantillas y falla si alguien vuelve a pegar un CDN.
- **Anti-bot.** El desafío aritmético se resolvía leyendo la pregunta del HTML. Pasa a **reCAPTCHA v2 de Google**
  cuando hay claves (`RECAPTCHA_SITE_KEY`/`SECRET_KEY`); sin claves cae al desafío anterior para no romper un
  entorno sin credenciales. Si Google no responde, **rechaza**: una caída de red no puede abrir la puerta.
- **Fin del oráculo del paso 1.** Padrón, duplicado y documento no disponible daban tres mensajes distintos, así que
  barriendo documentos se reconstruía el padrón de habilitados (dato socioeconómico) y se sabía quién ya se había
  inscripto —incluidas las personas relevadas en campo—. Ahora es un solo mensaje y un solo cuerpo; hay un test que
  compara los dos renders byte a byte.
- **Rate limit.** La IP se tomaba de `X-Real-IP` sin verificar el origen: mandar la cabecera distinta en cada
  request anulaba el límite. Ahora las cabeceras solo se leen si el request viene de `TRUSTED_PROXY_NETS`, y la IP
  del cliente sale de recorrer `X-Forwarded-For` de derecha a izquierda descartando proxies conocidos (RFC 7239).
  **Cambia el contrato de la Fase 6**, que prefería `X-Real-IP`: con dos proxies encadenados esa preferencia hacía
  que todos los ciudadanos compartieran una única cubeta. Se sumó una cubeta **por documento** (sin IP, consumida
  después del captcha para que nadie pueda quemarle la cuota a un tercero) y un techo al **paso 2**, que escribe y
  recibe archivos y no tenía ninguno. Una caché caída ya no devuelve 500.
- **Archivos.** `/media/` quedó detrás de login donde lo sirve Django, y los adjuntos y el Excel del padrón pasan a
  nombres UUID (`programas.0051`), con una migración de datos que renombra lo ya subido (`programas.0052`): antes
  el primero que subía `dni.jpg` quedaba en una ruta que se adivina con un diccionario de cien entradas.
- **Cabeceras.** Middleware propio con CSP y `Permissions-Policy`. `frame-ancestors 'none'` es el reemplazo real del
  anti-clickjacking: el código manda `X-Frame-Options: DENY` pero **el ingress lo reescribe con `ALLOW-FROM`**, una
  directiva obsoleta que los navegadores ignoran —y al ignorarla la página quedaba embebible—.
- **Datos.** El documento ya no viaja en el traceback de Gran Base, el token del link se enmascara en el log de
  accesos, la ubicación GPS solo se guarda si el segmento la pide, y la identificación del paso 1 caduca a los 45
  minutos con un sello propio que se renueva (acortar la sesión entera hacía perder el paso 2 a medio llenar).
- `/api/schema|docs|redoc/` quedaron detrás de login.
- **Aviso de padrón abierto al crear un relevamiento público.** Volver el padrón obligatorio habría contradicho RN-P14 —que decidió que sin padrón el link es abierto—, así que en lugar de imponerlo se hace explícita la consecuencia en el momento de decidir: el alta muestra un aviso de que sin padrón cualquiera con el link se inscribe y ocupa cupo. Si el programa quiere volverlo obligatorio, es una validación más en el form.

**Una revisión adversarial del propio cambio encontró 21 defectos**, tres de ellos rotos de raíz: `collectstatic`
fallaba por los sourcemaps de las librerías autoalojadas —el contenedor no habría arrancado—, con las claves de
reCAPTCHA cargadas el paso 1 era imposible de completar porque el campo del form seguía siendo obligatorio, y el
CSP bloqueaba SweetAlert2 y Alpine en el backoffice. Los tres corregidos y verificados.

**Pendiente de infraestructura, no de código:** en la VM con nginx el `login_required` sobre `/media/` no aplica
—nginx sirve el directorio antes de llegar a Django— y, si la app móvil descarga adjuntos con token DRF, un
`login_required` la rompería. Definir con ECOM y con el equipo móvil antes de tocar esa topología. También hay que
pedirle a ECOM que **deje de reescribir `X-Frame-Options`** y que cargue `RECAPTCHA_*`.

**Decisión pendiente detectada:** los formularios **RECHAZADO/BAJA** cuentan como «ya inscripto» y bloquean la reinscripción por link (mismo criterio que la app de campo). Quedó así por omisión; confirmar con el programa si el rechazo debe liberar el DNI.



## Historial

**26/08/2026 — la regla «FALLECIDO corta» estaba escrita pero no se cumplía.** Se detectó
revisando el flujo público a pedido del PM.

`portal/views/inscripcion.py` corta el paso 1 con `resultado.get("fallecido")`, pero
`PersonasAPIClient.consultar` **nunca producía esa clave**: `normalizar_persona` devuelve
exactamente cinco campos —`dni`, `apellido`, `nombre`, `fecha_nacimiento`, `sexo`— y el
resto de la respuesta se descarta. La condición era código muerto, así que **el documento de
una persona fallecida pasaba el paso 1 y podía inscribirse**.

Los tests daban confianza falsa: mockeaban `consultar_persona` devolviendo
`{"success": False, "fallecido": True}`, una forma que el cliente real no produce. Verificaban
la vista, no la integración.

Se agregó la detección en `PersonasAPIClient.consultar`, por las mismas vías que el método ya
usa para el «no encontrado» (`data.mensaje`) más la clave `mensaf` que usa el cliente RENAPER
de este repo, una fecha de defunción o una marca booleana. Devuelve `{"success": False,
"fallecido": True}`, el mismo contrato que ya esperaba el consumidor. Se aceptan variantes
porque el contrato de Base de Personas sigue abierto (task #243).

Tres tests nuevos en `PersonasClientTests` lo ejercitan **con la forma real de la respuesta**,
no mockeando el servicio.

**Queda una limitación honesta:** si Base de Personas no informa el fallecimiento por ninguna
de esas vías, la regla sigue sin poder cumplirse. La diferencia es que ahora funciona en cuanto
el dato llegue, en vez de estar rota en silencio. Verificarlo contra el servicio real depende de
las credenciales, que siguen sin cargar en testing/QA.

**En el mismo commit, un arreglo colateral del test que prohíbe recursos de terceros**
(`portal/tests/test_seguridad_publica.SinRecursosDeTercerosTests`). Recorría **todo
`BASE_DIR`** buscando `.html`, así que fallaba por archivos que nadie sirve y que aparecen en
cualquier copia de trabajo: el `site/` que deja `mkdocs build`, los entornos virtuales
(`.venv-e2e` no estaba excluido) y repos clonados al lado del proyecto. Se descubrió porque
correr `mkdocs build` para validar la documentación rompía la suite del portal.

Ahora recorre **las plantillas que Django sirve** —los `DIRS` configurados más el
`templates/` de cada app, vía `get_app_template_dirs`—, que son 330 contra las 329 que compila
`compile_templates.py`, y **aborta si el recorrido queda vacío** para que no pueda pasar en
falso si algún día cambia la configuración de templates.

**27/08/2026 — Base de Personas (Gran Base) quedó configurada en testing y QA.** Era el primer
pendiente de la entrada: `PERSONAS_API_CLIENT_ID`, `PERSONAS_API_CLIENT_SECRET` y
`PERSONAS_API_ENTIDAD_UUID` estaban vacías en el deployment, así que el paso 1 nunca precargaba
y toda inscripción quedaba `origen=manual`. Con las credenciales cargadas el circuito se puede
probar de verdad, lo que convierte el pendiente de **los 65 casos de QA** en el trabajo que
sigue. También queda verificable el arreglo del bloque anterior de este historial, que dependía
de estas mismas credenciales para comprobarse contra el servicio real. Ver **Cambio 50**.

---

# Cambio 42 — El portal ciudadano quedó viejo: marca, textos y contenido de la home

🟢 **HECHO — 26/08/2026**

| | |
|---|---|
| **Programa / módulo** | Portal ciudadano |
| **Etiquetas** | `#ui` `#textos` |
| **Solicitante** | PM — pedido directo en sesión de trabajo, sobre la URL de testing de ECOM |
| **Fecha del pedido** | 26/08/2026 |
| **Issue / épica** | Sin issue |
| **Partes afectadas** | Portal ciudadano (home pública y shell) |
| **Migración** | No requiere |

## Pedido original

> «Actualiza el diseño y los nombres de https://datanach.ecomdev.ar/portal/ ya que quedó viejo.»

## Alcance acordado

- La **home pública** del portal (`/portal/`) y el **shell** que comparten todas sus páginas (header, footer, título del navegador).
- Marca, textos y contenido; el lenguaje visual (tokens, tarjetas, botones NODO, gradiente de marca) se conserva.
- **Afuera:** las páginas internas del perfil ciudadano (login, registro, mis programas, consultas, mis datos) y el flujo de inscripción pública: heredan el shell y no tenían textos viejos propios. También afuera los datos de contacto (ver Pendientes).

## Decisiones tomadas

- **La marca es DATAÑACH, sin sub-marca.** El portal decía «Portal Nande» / «Nande» en título, header y footer. Se pasó a «DATAÑACH · Portal Ciudadano · Gobierno del Chaco». La sub-marca «Ñandé» sigue **pendiente de decisión del cliente** (ver Cambio 39 y el rename de julio): no se usa hasta que se defina.
- **Chaco es provincia, no municipio.** Toda la home hablaba de «tu municipio», «Portal Municipal», «programas municipales», «consultas y reclamos municipales». Se reemplazó por «Gobierno del Chaco» / «programas sociales del Gobierno del Chaco». Se eligió «Gobierno del Chaco» y no el nombre del ministerio porque la documentación del cliente lo escribe de dos maneras distintas («Ministerio de Desarrollo de Chaco» y «Ministerio de Desarrollo Humano»); el logo cargado en el login es el del Gobierno del Chaco, así que es el nombre que no puede estar mal.
- **Se eliminó todo lo que no tenía una funcionalidad detrás.** La tarjeta «Instituciones / Red DATAÑACH» con los botones «Iniciar trámite» y «Consultar estado», el indicador «Instituciones DATAÑACH» (siempre 0) y la sección «Instituciones de la red» (la lista venía vacía por código: `"instituciones": []`) eran maquetas de un módulo que no existe y mandaban al login sin destino. Un portal público no puede prometer trámites que no se pueden hacer.
- **En su lugar, lo que el portal sí hace hoy:** una tarjeta «Consultas al programa» (conversaciones con el equipo, funcionalidad real) y el acceso rápido «Mis datos». Tres indicadores en vez de cuatro.
- **Franja «¿Recibiste un link de inscripción?» sin botón.** La inscripción pública (Cambio 41) entra por un link con token que distribuye el programa; no existe una URL genérica, así que la home solo orienta: «ingresá desde ese link».
- **El shell no cambió de estructura ni de assets** (es pieza «Canónico reutilizable» del inventario de diseño): solo textos y atributos. El año del copyright pasó a ser dinámico (`{% now "Y" %}`), que era «2024» fijo.
- **El divisor entre indicadores solo se dibuja en escritorio.** En móvil, con una columna, quedaba como una línea decorativa sin sentido (observación del revisor de diseño).

## Implementación

- Header: «DATAÑACH» con subtítulo «Portal Ciudadano · Gobierno del Chaco»; título del navegador «DATAÑACH — Portal Ciudadano».
- Hero: «Tus programas sociales, en un solo lugar», con accesos rápidos a Mis programas, Consultas y Mis datos.
- Tres indicadores: ciudadanos registrados, programas activos, personas acompañadas.
- Dos tarjetas: «Mi perfil ciudadano» y «Consultas al programa».
- Sección «Programas del Gobierno del Chaco» (misma lista dinámica de programas activos).
- Franja informativa sobre el link de inscripción; CTA final y bloque de ayuda como estaban.
- Footer: «DATAÑACH — Portal Ciudadano de los programas sociales del Gobierno del Chaco», copyright con año dinámico.
- **Datos de contacto confirmados por el PM el 26/08/2026:** teléfono **+54 362 430-0002** y correo **datanach@chaco.gob.ar**, reemplazando el 0800-222-1133 e info@chaco.gob.ar de la primera versión en header, footer, bloque de ayuda de la home y en las pantallas y correo de la inscripción pública (Cambio 41). Como ya no es una línea 0800, la etiqueta «Línea gratuita» pasó a «Teléfono».

## Archivos

`portal/templates/portal/base.html` · `portal/templates/portal/home.html` · `portal/selectors/public.py`

## Base de datos

No requiere.

## Validación

- `manage.py check` sin observaciones. `scripts/design_audit.py --changed`: **0 errores, 0 warnings**. `scripts/compile_templates.py`: 325 plantillas, 0 errores.
- Revisión con el agente `chaco-design-reviewer`: **aprobable**, sin hallazgos bloqueantes; se aplicó su única mejora (divisor de stats solo en `md+`). Tokens verificados uno a uno contra `chaco-tokens.css`; URLs nuevas verificadas contra `portal/urls.py`; el shell sin cambios estructurales.
- Búsqueda de restos: ninguna aparición de «Nande», «municip», «Instituciones», «trámite» ni «2024» en los tres archivos.
- Los tests del portal que renderizan bajo el test client no corren en este entorno (Python 3.14, error preexistente ya documentado en el Cambio 41); `test_package_exports` en verde.

## Puesta en marcha en el servidor

Solo el deploy. Sin variables, cron ni migración. La home se cachea 5 minutos (`portal:home_ctx`): tras desplegar, los textos del contexto (items de las tarjetas) pueden tardar hasta 5 minutos en actualizarse.

## Pendientes / a definir

- El horario de atención («Lunes a Viernes 9–17 hs») viene de la primera versión y no fue confirmado por el cliente.
- **Sub-marca «Ñandé»** y **logos definitivos**: siguen pendientes de decisión del cliente (ver Cambio 39). El portal usa `mini-logo.png`.
- Nombre exacto del ministerio para el pie de página, si el cliente lo prefiere sobre «Gobierno del Chaco».

## Reversión

Revertir el commit de los tres archivos. No hay datos ni migración involucrados.


---

# Cambio 43 — Sacar el fondo animado del formulario de inscripción: shell propio «panel de marca»

🟢 **HECHO — 26/08/2026**

| | |
|---|---|
| **Programa / módulo** | Portal ciudadano · inscripción pública de Becas (Cambio 41) |
| **Etiquetas** | `#ui` `#relevamientos` |
| **Solicitante** | PM — pedido directo en sesión de trabajo, mirando el link real en el testing de ECOM; eligió entre tres mockups |
| **Fecha del pedido** | 26/08/2026 |
| **Issue / épica** | Sin issue (cuelga funcionalmente del análisis #289) |
| **Partes afectadas** | Portal ciudadano (seis pantallas del flujo de inscripción) |
| **Migración** | No requiere |

## Pedido original

> «El fondo animado lo tendríamos que borrar. Proponeme 3 diseños, armá los mockups.» Y ante los tres: «Vamos con la opción B.»

## Alcance acordado

- Las **seis pantallas** del link de inscripción: paso 1, paso 2, comprobante, «ya estás inscripto», «no disponible» y «demasiados intentos».
- **Afuera:** la home del portal y sus efectos (siguen como en el Cambio 42: `portal-effects.js` se sigue cargando en la home; sacarlo de ahí es otra decisión), los correos de la inscripción y la lógica de los formularios.

## Decisiones tomadas

- **El fondo animado era herencia, no diseño del formulario.** Las pantallas de inscripción extendían `portal/base.html`, el shell de la home, que carga `portal-effects.js`: un canvas de 80 partículas animadas detrás de toda la página. En un trámite que la gente hace desde el celular eso es ruido, consumo de batería y una distracción sobre campos obligatorios.
- **Se resolvió con un shell propio, no con un `if` en el shell de la home.** `base_inscripcion.html` carga solo lo que el formulario necesita (Tailwind compilado, Manrope autoalojada, tokens, botones y campos NODO). Sin Alpine, sin FontAwesome, sin toasts, sin chat, sin efectos, sin animaciones de entrada. El único tercero que puede cargar es el reCAPTCHA de paso 1, y solo si está configurado. Motivo: desacopla el formulario de la home —que puede seguir evolucionando con sus efectos— y lo deja más liviano para una superficie pública anónima.
- **Se eligió la Opción B «panel de marca»** entre tres mockups (A «trámite limpio»: blanco liso y barra de progreso; C «banda de convocatoria»: banda rosa con vigencia y columna de ayuda). En escritorio, un panel lateral de 520 px con el gradiente de marca lleva la convocatoria, los tres pasos y la ayuda, y el formulario va sobre blanco a la derecha; en celular el panel se convierte en cabecera con stepper horizontal y el formulario debajo. Motivo del cliente: la marca acompaña sin competir con los campos, y los pasos quedan siempre visibles.
- **El flujo ahora se muestra como tres pasos**, no dos: Identificación · Formulario · Comprobante. El comprobante ya existía como pantalla; contarlo como paso hace que la persona sepa que el envío termina en algo que puede guardar.
- **El paso activo se resuelve con `data-paso-activo` y selectores CSS**, no con lógica de template: cada página declara su número en un bloque y el shell lo pinta. Motivo: los bloques de Django no son variables de contexto y no se pueden comparar en un `{% if %}` del padre; esta es la forma más simple que funciona sin JS.
- **Sin build de Tailwind disponible** (no hay `node_modules` en el entorno), el layout del panel vive en un `<style>` del shell con tokens `var(--…)`; las clases utilitarias usadas se verificaron una a una contra el CSS compilado.
- **`ya_inscripto.html` había desaparecido de `development`.** La plantilla existía (release `a72c2f2`) y la borró por error el commit `6e0a576` («docs(requerimientos): Cambio 40»), que solo debía tocar documentación. Desde entonces la vista la renderiza para quien ya está inscripto y la pantalla daba `TemplateDoesNotExist`. Se restauró en este cambio sobre el patrón nuevo. Es un bug de integración que salió a la luz al tocar el flujo completo; conviene revisar cómo se generó ese commit.
- **Accesibilidad del stepper (observación del revisor de diseño):** el paso activo no puede distinguirse solo por color. El stepper es un include (`_stepper.html`) que recibe `paso_activo` y marca el `<li>` activo con `aria-current="step"` y un texto solo para lectores de pantalla. Y el pie del panel de escritorio va sobre navy sólido, no sobre el gradiente: el texto chico blanco sobre el tramo rosa no alcanzaba el contraste mínimo.

## Implementación

- Escritorio: panel izquierdo con logo, «DATAÑACH · Portal Ciudadano · Gobierno del Chaco», etiqueta del programa y segmento, «Inscripción a {convocatoria}», la línea «Completá la inscripción en tres pasos. Solo necesitás tu DNI.», el stepper vertical (activo con círculo blanco y número en color de marca) y abajo la ayuda (+54 362 430-0002 · datanach@chaco.gob.ar) y el copyright con año dinámico. A la derecha, el formulario sobre blanco, con chip «Paso N de 3» y un título corto («Ingresá tus datos», «Completá tu formulario», «¡Inscripción enviada!»).
- Celular: el panel es la cabecera con stepper horizontal; el formulario debajo; la ayuda y el copyright pasan al pie.
- Las pantallas de resultado no muestran stepper y conservan icono, título y texto.
- Campos, ids, CSRF, `enctype`, captcha en sus dos modos, el script de geolocalización del paso 2 y el `extra_js` del reCAPTCHA quedaron intactos: solo cambió el contenedor.

## Archivos

`portal/templates/portal/inscripcion/base_inscripcion.html` (nuevo) · `_stepper.html` (nuevo) · `paso1.html` · `paso2.html` · `confirmacion.html` · `ya_inscripto.html` (nuevo) · `no_disponible.html` · `demasiados_intentos.html` · `.claude/agents/chaco-design-system.md` (fila «Shell de inscripción pública»).

## Base de datos

No requiere.

## Validación

- `manage.py check` sin observaciones · `scripts/design_audit.py --changed` **0 errores, 0 warnings** · `scripts/compile_templates.py` 328 plantillas, 0 errores · `scripts/check_design_agent.py --base development` OK (la pieza nueva quedó inventariada como «Canónico reutilizable»).
- Suite de inscripción (`test_inscripcion`, `test_inscripcion_envio`, `test_inscripcion_correo`): 42 tests, el único error es el de entorno (Python 3.14 renderizando bajo el test client), verificado idéntico sin los cambios.
- Revisión con `chaco-design-reviewer`: ver resultado en el PR.

## Puesta en marcha en el servidor

Solo el deploy. Sin variables, cron ni migración. La home **sigue** cargando `portal-effects.js`: si el cliente quiere sacarlo también de ahí, es un cambio de una línea en `portal/base.html` y se registra aparte.

## Pendientes / a definir

- Decidir si el fondo de partículas también se retira de la **home** (hay tres mockups de la home listos de esta misma sesión).
- Cuando exista un entorno con `node_modules`, mover el `<style>` del shell a clases del build de Tailwind si el equipo lo prefiere; funcionalmente es equivalente.

## Reversión

Revertir el commit: las seis páginas vuelven a extender `portal/base.html`. Conviene **conservar** `ya_inscripto.html` aunque se revierta el resto, porque sin él la pantalla de duplicado rompe.

---

# Cambio 44 — Avisar por correo al ciudadano cuando se resuelve su formulario

🟡 **IMPLEMENTADO — 26/08/2026 · activo desde el 27/08/2026 con el SMTP de ECOM; falta verificar el envío real**

| | |
|---|---|
| **Programa / módulo** | Becas · revisión de formularios y cupo · correo al Portal Ciudadano |
| **Etiquetas** | `#correo` `#relevamientos` `#cupos` `#ui` `#infra` |
| **Solicitante** | PM — pedido directo en sesión de trabajo, con las definiciones cerradas en la misma sesión al relevar el código |
| **Fecha del pedido** | 26/08/2026 |
| **Issue / épica** | Sin issue (cuelga funcionalmente del análisis #289 / Cambio 41) |
| **Partes afectadas** | Backoffice · Servidor. **Mobile no se toca.** |
| **Migración** | `programas.0053` — solo metadatos (`verbose_name` / `help_text`). Sin cambio de esquema. |

## Pedido original

> «En el programa Becas, cuando el ciudadano se inscribe le llega el comprobante de
> inscripción. Cuando el técnico valida el relevamiento en `/becas/revision/formulario/`
> lo puede aprobar o rechazar. Quiero que cuando pase eso se le envíe un mail avisando
> si fue aprobado o rechazado. Pero la aprobación o el rechazo no es la de SIIS, es la
> del caso en general.»

Definiciones agregadas en la misma sesión, al relevar el código:

> «Si queda en lista de espera se le notifica que entró pero está en lista de espera.»
> «Se le manda el motivo textual.» · «Ambas, sea por link o territorial.»
> «Lo respeta, y sumale eso al territorial también.» · «Sí, también cuando se pasa de
> lista a aprobado se avisa.»

## Alcance acordado

**Cuatro momentos de aviso**, no dos:

| Momento | Vista que lo dispara | Estado resultante |
|---|---|---|
| Aprobado con cupo | `formulario_aprobar` | `APROBADO` |
| Entró pero quedó en lista de espera | `formulario_aprobar` | sigue `ENVIADO` + entrada en `ListaEspera` |
| Rechazado | `formulario_rechazar` | `RECHAZADO` |
| Promovido de lista de espera a aprobado | `promover_lista_espera_view` | `APROBADO` |

- Aplica a **los dos tipos de relevamiento**: público por link y territorial de campo.
- **Respeta el toggle `confirmar_por_email`** del relevamiento, que pasa a estar
  disponible también en los territoriales (hasta este cambio solo se ofrecía en los públicos).
- El **motivo del rechazo se manda textual**, tal como lo escribió el técnico.

**Queda explícitamente afuera:** la baja de un beneficiario ya aprobado (`dar_de_baja`),
los cambios de estado hechos desde el admin de Django, el reenvío manual de un aviso y
cualquier aviso ligado a la validación SIIS.

## Decisiones tomadas

- **Cuatro correos y no dos, porque «Aprobar» tiene dos desenlaces.**
  `aprobar_o_poner_en_espera` devuelve `"aprobado"` o `"lista_espera"` según haya cupo, y
  `Formulario.Estado` no tiene un estado «en espera»: sin cupo el formulario **sigue en
  `ENVIADO`**. Mandar «fuiste aprobado» al apretar Aprobar le mentiría a quien cayó en
  lista de espera. Por eso el desenlace lo pasa la vista y no se deduce del estado.

- **El motivo del rechazo va textual, por decisión del cliente.** Se deja asentado el
  riesgo asumido: `motivo_rechazo` es hoy una nota interna del técnico, sin revisión de
  estilo ni destinatario ciudadano. Si el programa quiere despersonalizarlo más adelante,
  el cambio es de plantilla y no de flujo. En el HTML el motivo se escapa (test propio).

- **El aviso no distingue origen del formulario.** `email_contacto` es obligatorio en el
  modelo (`Bloque C — Contacto`) y viaja también en el serializer de la API móvil, así que
  un formulario cargado por el territorial tiene correo igual que uno del link.

- **El toggle se extiende a territorial en lugar de crear un campo nuevo.** Es el mismo
  hecho para el ciudadano —«este relevamiento notifica por correo»— y duplicarlo daría dos
  interruptores que hay que mantener sincronizados. Como el campo tiene `default=False`,
  **ningún relevamiento existente empieza a mandar correos**: es opt-in y no hay envío
  retroactivo. Esto **no reabre** la decisión del Cambio 41 «el comprobante es exclusivo
  del flujo público»: el comprobante sigue saliendo solo por link (la API de campo no lo
  llama); lo que se amplía es dónde se puede *configurar* el toggle.

- **El correo se manda desde la vista, después de que el servicio devuelve, nunca dentro
  de la transacción.** `aprobar_o_poner_en_espera` y `promover_lista_espera` son
  `@transaction.atomic`: si se enviara adentro y la transacción hiciera rollback, el correo
  ya salió y no se puede retractar.

- **El aviso nunca rompe la acción del técnico**, mismo criterio que el comprobante
  (Cambio 41): si SMTP falla se loguea y la aprobación o el rechazo quedan firmes. El
  blindaje cubre **también el armado** del mensaje, no solo el `send`: cuando la vista
  llama al servicio la resolución ya está commiteada, así que un error de plantilla daría
  un 500 sobre una acción ya hecha. Con el render adentro del `try`, el servicio devuelve
  `False` y la vista sigue.

- **No se toca `formulario_validar_sis`.** Es la prevalidación del Cambio 34 y no resuelve
  el caso; el pedido fue explícito en distinguirla. Hay un test que verifica que no avisa.

- **El estado del toggle se muestra en la tarjeta de información del relevamiento, no en la
  del link público.** Estaba dentro del bloque que solo se dibuja para los públicos: ahí un
  territorial con avisos activos no lo vería nunca. La redacción vieja («Confirmación por
  correo: activada») también quedó corta, porque ya no describe solo el comprobante.

## Implementación

- **Servicio nuevo** `programas/services/avisos_resolucion.py`, modelado sobre
  `enviar_confirmacion_inscripcion`: corta temprano si el relevamiento no notifica, si el
  formulario no tiene correo de contacto o si el desenlace no es uno de los cuatro; arma
  `EmailMultiAlternatives` con texto plano + HTML de marca y `contexto_pie()`; devuelve
  `True`/`False` y **nunca propaga**.
- **Plantillas** `programas/templates/programas/becas/email/resolucion_body.{txt,html}`:
  un par único con bloques condicionales por desenlace, reusando el encabezado y el pie de
  marca del portal. Asuntos: «Tu inscripción fue aprobada», «Tu inscripción quedó en lista
  de espera», «Novedades sobre tu inscripción» (rechazo) y de nuevo «Tu inscripción fue
  aprobada» para la promoción —para el ciudadano es el mismo hecho—, todos con
  «— {convocatoria}».
- **Tres puntos de llamada**, siempre después de que el servicio de dominio devolvió y
  fuera de su transacción: `formulario_aprobar` (con el `resultado` tal cual),
  `formulario_rechazar` (`"rechazado"` + motivo) y `promover_lista_espera_view`
  (`"promovido"`). Los tres pasan protocolo y host del request para que el logo del correo
  tenga URL absoluta.
- **Toggle en territoriales:** `RelevamientoForm.__init__` deja de remover
  `confirmar_por_email` cuando el usuario no tiene la capacidad de público; `tipo` y
  `padron` siguen gateados por RN-P13. En las tres pantallas de alta el control salió del
  `fieldset` condicionado por tipo y ahora se ve en los dos casos, con el `help_text` del
  modelo debajo.
- **Textos:** la etiqueta pasó a «Avisar por correo a la persona» y el `help_text` a
  «Avisa por correo cuando se resuelve el formulario: aprobado, en lista de espera o
  rechazado. En los relevamientos con link público, además manda el comprobante al
  inscribirse.»

## Archivos

`programas/services/avisos_resolucion.py` (nuevo) ·
`programas/templates/programas/becas/email/resolucion_body.{txt,html}` (nuevos) ·
`programas/views/revision.py` · `programas/views/cupo.py` · `programas/forms.py` ·
`programas/models/__init__.py` · `programas/migrations/0053_relevamiento_avisos_correo_textos.py` ·
`programas/templates/programas/becas/relevamientos/{convocatoria_detail,relevamiento_list,relevamiento_form,relevamiento_detail}.html` ·
`.claude/agents/chaco-design-system.md` (regla de `fieldset` condicionados en el bullet *Forms*) ·
tests: `programas/tests/test_avisos_resolucion.py` (nuevo), `programas/tests/test_becas_revision.py`,
`programas/tests/test_relevamiento_publico.py`.

## Base de datos

Sin cambio de esquema. `Relevamiento.confirmar_por_email` ya existe desde `programas.0049`
con `default=False`. `programas.0053` solo registra el cambio de `verbose_name` /
`help_text`, necesario para que `makemigrations --check` quede limpio. Segura sobre datos
existentes: no toca valores.

## Validación

- **34 tests propios**: 18 del servicio (`test_avisos_resolucion`, un caso por desenlace,
  motivo textual y escapado, toggle apagado en público y en territorial, territorial
  encendido, sin correo de contacto, desenlace desconocido, SMTP caído, marca y saludo) y
  16 de integración de las vistas (`test_becas_revision`): que cada vista llama al servicio
  con el desenlace correcto, que una aprobación bloqueada o un rechazo sin motivo no avisan,
  que `formulario_validar_sis` no avisa, que el territorial con el toggle encendido manda de
  verdad, y que ni un SMTP caído ni una plantilla rota voltean la aprobación, el rechazo o
  la promoción.
- Las pruebas de envío real llaman a la vista con `RequestFactory` en vez del test client:
  bajo Python 3.14 + Django 4.2 el client instrumenta el render y revienta en
  `Context.__copy__`, lo que alcanzaría también al `render_to_string` del correo. Es el
  mismo desvío que ya usaba `portal/tests/test_inscripcion_correo`.
- `manage.py check` sin observaciones · `makemigrations --check --dry-run` sin cambios ·
  `scripts/design_audit.py --changed` **0 errores** (1 WARN preexistente de `outline:none`
  en un `select` que este cambio no toca) · `scripts/compile_templates.py` 179 plantillas,
  0 errores · `scripts/requerimientos.py --check` OK.
- Suite `programas` completa: **525 tests, 1 falla + 119 errores antes del cambio y los
  mismos después**. Todos los errores son el bug de entorno de Python 3.14 renderizando bajo
  el test client; la única falla (`test_cachea_la_ausencia_del_programa`) es preexistente y
  de caché entre tests, ajena a este cambio.

## Puesta en marcha en el servidor

- Deploy estándar con migración (solo metadatos, riesgo nulo).
- **Depende del SMTP real**, que es el Cambio 37 / 13 y sigue pendiente de ECOM:
  `EMAIL_BACKEND` cae a consola mientras `EMAIL_HOST` esté vacío. Hasta entonces el código
  funciona y los tests pasan, pero **no se entrega nada**. Por eso la entrada queda 🟡 y no 🟢.
- Tras el deploy **nada cambia solo**: el toggle viene en `False` en todos los relevamientos
  existentes. Para empezar a notificar hay que activarlo relevamiento por relevamiento.

## Pendientes / a definir

- La **baja de un beneficiario aprobado** (`dar_de_baja`) no avisa. Quedó fuera de alcance;
  es el mismo hecho para el ciudadano y conviene definirlo.
- **Textos definitivos de los cuatro correos**: los aprueba el programa de Becas.
- Si el motivo del rechazo textual resulta inadecuado en producción, la salida es cambiar la
  plantilla, no el flujo.
- Nadie ve hoy si un aviso salió o falló: solo queda en el log del servidor. Si el programa
  necesita trazabilidad por formulario, es un desarrollo aparte.

## Reversión

Revertir el PR y retroceder la migración a `programas.0052`. No se pierden datos: no hay
columnas nuevas ni registros propios. Los relevamientos territoriales que hayan quedado con
el toggle en `True` conservan el valor; deja de tener efecto sobre los avisos de resolución
y vuelve a valer solo para el comprobante del link público.


## Historial

**26/08/2026, más tarde — la revisión posterior al merge destapó tres caminos que la
entrada original no contemplaba.** El spec enumeraba cuatro momentos de aviso, pero
`Formulario.estado` se escribe en **seis** puntos del código; los dos que faltaban y una
guarda ausente se resolvieron así:

- **La resolución de una carga duplicada NO avisa, y ahora está escrito en el código.**
  `formulario_resolver_duplicado` deja una de las dos cargas en `RECHAZADO`, pero las dos
  son de la **misma persona en el mismo relevamiento**: rechazar el duplicado es limpieza
  de datos, no la resolución de su inscripción. La carga que sobrevive queda `ENVIADO` y
  recibe el correo que corresponda cuando se resuelva de verdad. Avisar ahí le diría «no
  fue aprobada» a alguien cuyo trámite sigue abierto. Queda un comentario en las dos ramas
  y un test que lo fija, para que no se «corrija» más adelante.

- **El alta manual a lista de espera ahora sí avisa.** `agregar_lista_espera_view` metía a
  una persona en la lista sin correo, mientras que llegar ahí por «Aprobar sin cupo» sí
  avisaba. Para el ciudadano el desenlace es el mismo, así que manda el mismo aviso
  (`lista_espera`). Va afuera de la transacción y afuera del `try`, igual que los otros tres.

- **`formulario_rechazar` no tenía guarda de estado.** Iba directo de validar el motivo a
  escribir `RECHAZADO`, sin verificar que el formulario estuviera `ENVIADO` —a diferencia de
  la aprobación, que corta en `aprobar_o_poner_en_espera`—. Era **preexistente**, pero este
  cambio lo agravó: un doble clic mandaba **dos correos**, y un POST armado a mano podía
  rechazar a un beneficiario ya `APROBADO`, liberándole el cupo (que se cuenta en vivo) y
  avisándole que no fue aprobado. Se agregó la guarda simétrica a la de aprobar.

Tres tests nuevos en `ResolucionCoherenteTests` fijan las tres decisiones.

Lo que decía antes y sigue valiendo: los cuatro momentos de aviso originales y sus reglas no
cambiaron. Lo que cambió es que ahora los **seis** puntos que mueven el estado tienen una
decisión explícita: cuatro avisan, uno avisa desde ahora (lista de espera manual) y uno
deliberadamente no avisa (duplicados). La baja de un beneficiario sigue sin avisar y sigue
figurando como pendiente.

**27/08/2026 — el circuito dejó de estar inerte: ECOM configuró el SMTP.** Esta entrada se
cerró el 26/08 con los cuatro avisos implementados pero sin poder salir del servidor. Con el
SMTP cargado en **QA y producción** los correos se envían de verdad; en QA con el prefijo
`[QA]` en el asunto, que es lo único que los distingue en la bandeja del ciudadano (ver la
corrección del Historial del Cambio 31, porque el criterio del backend no es el `ENVIRONMENT`).

El semáforo **queda en 🟡**: nadie vio todavía llegar uno de estos avisos, así que falta correr
`diagnosticar_correo` desde el servidor y falta la aprobación de los **textos definitivos por
el programa de Becas**. Los otros pendientes no los toca este desbloqueo: la baja de un
beneficiario aprobado sigue sin avisar, y sigue sin haber trazabilidad de qué aviso salió o
falló más allá del log del servidor. Ver **Cambio 50**.

---

# Cambio 45 — Documentar el Programa Becas al detalle: el sistema construido como evolución de la V1

🟢 **HECHO — 26/08/2026 · publicado en `development` (2d075aa), desplegado a GitHub Pages**

| | |
|---|---|
| **Programa / módulo** | Becas · Documentación |
| **Etiquetas** | `#textos` `#ui` `#relevamientos` |
| **Solicitante** | PM — pedido directo en sesión de trabajo del 26/08/2026 |
| **Fecha del pedido** | 26/08/2026 |
| **Issue / épica** | sin issue |
| **Partes afectadas** | Documentación pública (GitHub Pages). **Sin cambios de código.** |
| **Migración** | No requiere |

## Pedido original

> «Quiero leer toda la documentación que tenemos pública de Becas y actualizarla al detalle
> con lo que tenemos del proceso: sumarle las funcionalidades de los email, el formulario
> público, la nueva jerarquía de programa/subsegmento y todo eso. Habría que leer el código
> completo de punta a punta y leer la documentación que tenemos de Becas y actualizarla al
> detalle. La idea es que esté bien detallada, con todas las reglas y todo eso, que no falte
> nada del detalle.»

Y al definir cómo convivirían los dos documentos: «convive, ya que es la evolución;
planteamos esto como evolución de la V1».

## Alcance acordado

- **Documento nuevo** `docs/client/funcionalidades/programa-becas-sistema.md` que describe el
  sistema construido, con sus reglas, procesos y controles.
- **El documento de junio se conserva** como registro histórico de la propuesta original de la
  Versión 001, con un aviso arriba que apunta al nuevo.
- Índice de funcionalidades y navegación de MkDocs actualizados con los dos.

**Afuera:** cambios de código, y la documentación de Dispositivos.

## Decisiones tomadas

- **Documento nuevo en vez de actualizar el de junio.** No era una desactualización de bordes:
  el de junio es una *propuesta* previa a construir —con «preguntas abiertas», «asunciones a
  confirmar» y «próximos pasos»— y lo pedido era una *descripción del sistema*. Son dos
  géneros distintos; pisarlo habría perdido la trazabilidad de qué se propuso en junio y en
  qué se convirtió. El PM eligió explícitamente la convivencia.

- **Relevamiento en paralelo por áreas antes de redactar.** El territorio son ~14.800 líneas de
  `programas` más la superficie del portal. Se dividió en seis relevamientos de solo lectura
  (jerarquía, RBAC, ciclo de vida, inscripción, revisión/cupos, integraciones), cada uno
  cruzando el código con este archivo por etiqueta, y **un solo redactor** sintetizó. Un solo
  escritor evita el conflicto de merge que trae que varias ramas toquen el mismo documento.

- **Sin referencias a código ni deuda interna.** El criterio de publicación del propio sitio
  pide «lenguaje orientado al cliente» y excluye «detalle interno (estado del código, impacto
  técnico, riesgos ni preguntas abiertas)». Las ~200 referencias `archivo:línea` del
  relevamiento fueron garantía de exactitud, no material publicable.

- **Las constantes numéricas de los controles anti-abuso no se publican.** Se dice que hay
  límite de intentos por conexión y por documento; no cuántos. Publicar los números le da el
  mapa a quien quiera evadirlos.

- **Sí se publican las dependencias de ECOM.** Catálogo SIIS vacío, credenciales de Base de
  Personas sin cargar y SMTP sin verificar, con qué queda inerte en cada caso. No es «riesgo
  interno»: es una dependencia que solo el cliente puede destrabar, y hasta hoy la
  conversación era nuestra.

## Implementación

El documento tiene 15 secciones: qué cambió respecto de la propuesta original · cómo se
organiza el programa (los cinco niveles) · quién hace qué (los cinco roles y su alcance) · qué
se le pregunta a la persona (los cuatro niveles de campos) · cómo se inscribe (los dos canales
paso a paso) · cómo se revisa y se resuelve · cupos y lista de espera · pausas y vencimientos ·
correos · integraciones · dependencias de ECOM · reportes y exportaciones · qué ve el ciudadano
en su legajo · estados de referencia · documentos relacionados.

## Archivos

`docs/client/funcionalidades/programa-becas-sistema.md` (nuevo, 440 líneas) ·
`docs/client/funcionalidades/programa-becas.md` (aviso de documento histórico) ·
`docs/client/funcionalidades/index.md` · `mkdocs.yml`

## Base de datos

No requiere.

## Validación

- `mkdocs build --strict` sin errores, dos corridas (antes y después de completar la cobertura).
- Enlaces internos verificados uno por uno.
- **Chequeo de cobertura contra los seis relevamientos**, que encontró huecos reales y frenó una
  primera publicación: faltaban los cinco reportes y las tres exportaciones, la solapa de Becas
  del legajo, la bandeja de identidades pendientes, el control de solapamiento de asignaciones
  de territorial, la validación de archivos, la tolerancia de reloj de la sincronización, cómo
  se asigna el alcance y la auditoría de cambios. Se incorporaron y se volvió a verificar.

## Puesta en marcha en el servidor

Ninguna. El workflow `docs-auto-deploy.yml` publica solo ante un push a `development` que toque
`docs/client/**` o `mkdocs.yml`.

## Pendientes / a definir

- **Las correcciones del doc de junio no se propagaron a `estimacion-programa-becas.md`**, que
  sigue reflejando el alcance estimado en junio.
- ~~El documento describe el Cambio 44 (avisos de resolución del caso) **como todavía
  inexistente**, porque al publicarse no estaba terminado.~~ **Resuelto el 26/08/2026**: la
  sección de correos se partió en «al ciudadano» (cinco) y «a los operadores» (dos), y se
  actualizaron además aprobar, rechazar y lista de espera, que ahora notifican. Se dejó
  asentado el caso que deliberadamente no avisa (resolución de cargas duplicadas).
- Las tres exclusiones deliberadas —constantes de los controles anti-abuso, catálogo de
  capacidades y deuda interna— se pueden revertir si el PM las quiere adentro.

## Reversión

Revertir el commit. El de junio vuelve a quedar sin el aviso y como única entrada del índice y
de la navegación. No se pierde nada: es documentación, sin código ni datos.


---

# Cambio 46 — La API de campo aceptaba cualquier archivo, de cualquier peso

🟢 **HECHO — 26/08/2026 · pendiente de verificar contra la app antes de producción**

| | |
|---|---|
| **Programa / módulo** | Becas · Mobile / API |
| **Etiquetas** | `#api` `#mobile` `#datos` |
| **Solicitante** | Hallazgo propio en la revisión del flujo público que pidió el PM |
| **Fecha del pedido** | 26/08/2026 |
| **Issue / épica** | sin issue |
| **Partes afectadas** | Servidor/API. **La app móvil no se toca, pero hay que verificarla.** |
| **Migración** | No requiere |

## Pedido original

> «¿Hay algún otro error más en todo este proceso del programa Becas? Me importa que los
> formularios públicos funcionen bien.» — y después: «resolvé los errores que encuentres».

## El problema

`AdjuntoFormularioSerializer` validaba **una sola cosa**: que viniera exactamente uno de
`pregunta_global` / `requisito_nativo`. Ni extensión ni tamaño. El portal público sí valida
—`.jpg/.jpeg/.png/.pdf`, 5 MB, en Python— así que las dos puertas de entrada al mismo modelo
tenían criterios opuestos.

Los límites globales de Django no cubrían el hueco, y es fácil creer que sí:
`DATA_UPLOAD_MAX_MEMORY_SIZE` **excluye los archivos** de su cuenta, y
`FILE_UPLOAD_MAX_MEMORY_SIZE` solo decide a partir de qué tamaño volcar a disco, no cuánto se
acepta. En los hechos **no había techo**.

Lo que lo vuelve serio: `/media/` lo sirve **nginx directo, sin pasar por Django** (pendiente
ya registrado en el Cambio 41), así que un `.html` o un `.svg` subido por la API se serviría y
se ejecutaría en el origen del sitio.

## Decisiones tomadas

- **Lista blanca, no lista negra.** El riesgo es contenido ejecutable o interpretable, y una
  lista negra siempre deja una extensión afuera.

- **La lista de la API es más amplia que la del portal, a propósito.** El portal recibe uploads
  **anónimos** y por eso su criterio es el más duro posible. Acá sube un **territorial
  autenticado desde un teléfono**, así que se suman los formatos que producen las cámaras
  (`.heic`, `.heif`, `.webp`): rechazar una captura legítima le rompe el trabajo de campo, y
  ese daño es peor que el que se está evitando. Lo que importa es que quede afuera `.html`,
  `.svg` y `.js`, y queda.

- **Mismo techo de 5 MB que el portal**, que es el límite ya documentado del producto.

- **No se tocó la app móvil.** Vive en otro repo y no se puede inspeccionar desde acá.

## Implementación

`validate_archivo` en `AdjuntoFormularioSerializer`, con las constantes
`ADJUNTO_EXTENSIONES` y `ADJUNTO_MAX_BYTES` al lado y el motivo de la divergencia con el
portal escrito en el código.

## Archivos

`programas/api/serializers.py` · `programas/tests/test_becas_api.py`

## Base de datos

No requiere.

## Validación

Cuatro tests nuevos en `AdjuntoValidacionTests` —**no existía ninguno para adjuntos en la
API**—: acepta una foto, acepta los formatos de cámara, rechaza `.html`/`.svg`/`.js` con 400,
y rechaza un archivo de más de 5 MB. Suite `programas.tests.test_becas_api` completa en verde.
`manage.py check` OK.

## Puesta en marcha en el servidor

Deploy estándar, sin migración.

**Antes de producción hay que verificar qué formato manda la app.** No hay ni un indicio en
este repo —ni tests de adjuntos, ni documentación del contrato— y la app vive en
`Chaco-mobile`. Si sube algo fuera de la lista, las capturas empiezan a rechazarse con 400 y
se corta el trabajo de campo. La lista se amplía en una línea.

## Pendientes / a definir

- Verificar el formato real contra la app móvil (arriba).
- La asimetría de fondo sigue: portal y API tienen dos listas y dos constantes. Unificarlas en
  un solo lugar es un refactor aparte; hoy la divergencia es deliberada y está explicada.
- Sigue sin resolverse que nginx sirva `/media/` sin autenticación (Cambio 41), que es lo que
  vuelve peligroso un adjunto ejecutable. Esto reduce el riesgo, no lo elimina.

### Revisados en la misma pasada y NO corregidos, con su motivo

La revisión del flujo público del 26/08 miró todo el circuito. Además de lo ya corregido
—`FALLECIDO` (Cambio 41) y estos adjuntos—, quedaron tres cosas sin tocar **a propósito**, para
que no se vuelvan a relevar de cero:

- **GPS sin validación geográfica en el servidor.** El segmento declara `requiere_gps` y ambos
  canales envían coordenadas, pero el servidor no las exige ni verifica que caigan en la
  localidad. No se resuelve escribiendo código: falta una **fuente oficial de polígonos de
  localidades**. Pendiente heredado del Cambio 19.

- **`RECHAZADO` y `BAJA` bloquean reinscribirse por link.** Cualquier formulario previo con el
  mismo documento en la convocatoria corta el paso 1, incluidos los ya rechazados o dados de
  baja. Quedó así **por omisión** al construir el Cambio 41 y nunca se confirmó con el
  programa. **Es una decisión de producto, no un defecto**: cambiarla sin que el programa la
  defina sería peor que dejarla registrada.

- **Los dos riesgos de privacidad del paso 1**, que el PM dejó fuera de alcance explícitamente
  en la revisión de seguridad del 26/08: (1) una inscripción anónima crea un `Ciudadano` sin
  pasar por la verificación de identidad del alta de cuenta del portal; (2) el paso 2 muestra
  nombre, apellido y fecha de nacimiento de cualquier documento que matchee, sin que quien
  completa el formulario sea necesariamente su dueño. No se revierten sin decisión del PM.

**Lo que sí se revisó y está correcto**, para no volver a auditarlo: el cierre del envío del
formulario público no tiene carreras —lock del relevamiento, idempotencia por `client_uuid`,
re-chequeo de estado, vigencia con pausa heredada, cupo, lock de la convocatoria para el
duplicado y re-verificación del padrón, todo **dentro** de la transacción y no solo en el paso
1—; el orden de validaciones del paso 1 consume el límite por documento **después** del
captcha, para que nadie pueda quemarle la cuota a un tercero rotando IP; y la respuesta de
Base de Personas solo expone nombre, apellido y fecha de nacimiento.

## Reversión

Revertir el commit. Los archivos ya subidos no se tocan.

---

# Cambio 47 — El tablero no reflejaba que el formulario público ya estaba entregado

🟡 **PARCIAL — 27/08/2026 · tablero al día; el plan de pruebas quedó redactado sin publicar**

| | |
|---|---|
| **Programa / módulo** | Becas · Gestión |
| **Etiquetas** | `#gestion` `#relevamientos` |
| **Solicitante** | PM — sesión de trabajo del 27/08/2026 |
| **Fecha del pedido** | 27/08/2026 |
| **Issue / épica** | Épica #69 · análisis #289 · tasks #290 a #296 y #299 |
| **Partes afectadas** | Ninguna del producto. Solo el Project #1 de GitHub, los issues y este documento |
| **Migración** | No requiere |

## Pedido original

> «Las épicas y los task sobre el formulario público de los relevamientos de becas ¿en qué
> estado están?» — y después, en orden: «a todos ponele iteración actual», «asignáme esas
> tareas a mi usuario Matías Fariña», «¿todas tienen los casos /qa:plan?», «armá el plan en
> la épica» y «documentá todo lo que se hizo».

## El problema

El **Cambio 41** (formulario público) estaba entregado desde el 25/08: PR #306 mergeada en
`development` y desplegada en testing, más los Cambios 43 y 44 encima. Pero en el Project #1
la épica, el análisis y las **8 tasks seguían en `Backlog` y abiertos**, sin responsable y sin
iteración.

No era un tablero abandonado —el resto del Project estaba mantenido: 84 items en Done y 24 en
In QA— sino **este cluster puntual desincronizado**. Un tablero que dice Backlog sobre trabajo
ya desplegado en testing hace invisible lo que falta de verdad, que era verificarlo.

## Alcance acordado

Entra: poner al día los campos del tablero de ese cluster y dejar escrito el plan de pruebas
de la épica. **No entra** ejecutar los casos, ni tocar código del producto, ni cerrar issues.

## Decisiones tomadas

- **«Solo lectura sobre el Project» cubre el `Status`, no los campos de metadata.** La regla de
  `PM.md` existe para que ningún asistente decida por su cuenta que algo avanzó de estado.
  Completar `Iteration` y `Assignees` cuando el PM lo pide explícitamente no toma esa decisión:
  es tipeo delegado y es reversible. Se escribieron esos campos y **no** se tocó ningún Status
  a mano.

- **No se tocó la configuración del campo de iteración.** Editar `iterationConfiguration` por
  API reemplaza la definición completa y rompe las asignaciones existentes. Se asignó la
  iteración item por item con `gh project item-edit`; la configuración quedó verificada intacta
  (1 activa + 6 completadas).

- **`Mkdir-arg` es el usuario del PM, no `matias-abate`.** Las dos cuentas empiezan con
  «Matías» y son personas distintas: `matias-abate` es Matías **Abate**. Se confirmó por el
  correo de git de la cuenta autenticada (`farinamatias00@gmail.com`) antes de asignar.

- **El gate del plan de pruebas se evalúa sobre las tasks abiertas.** `QA.md` pide que «todas
  las tasks de la épica» tengan casos, y su propia receta de cobertura filtra por
  `--state open`. Las **12 tasks abiertas** de la épica #69 tienen casos; las 6 cerradas que no
  (#73, #74, #75, #76, #77, #82) se entregaron antes de que el método de QA existiera. No se
  generaron casos retroactivos para ellas: se documentaron como cubiertas de forma indirecta
  por los end-to-end.

- **El plan se hizo sobre la épica entera, no solo sobre el formulario público.** Se advirtió
  que un plan de #69 arrastra 316 casos y nueve meses de módulo, y que un plan acotado al canal
  público sería más ejecutable; el PM eligió igual el de la épica. Queda registrado que la
  decisión fue consciente.

## Implementación

Lo que quedó hecho, en orden:

1. **Diagnóstico del cluster** — 10 items (épica #69, análisis #289, tasks #290 a #296 y #299),
   48 h estimadas, contrastados contra `development` y contra el índice de este archivo.

2. **Iteration 7 asignada a los 10 items.** Es la única iteración activa desde el 10/08/2026.

3. **Las 8 tasks asignadas a `Mkdir-arg`.** La automatización del Project reaccionó a la
   asignación y movió **7 de ellas a `In QA`**; **#299 quedó en `Backlog`**. Ese movimiento no
   lo hizo el asistente: fue la regla del Project, y quedó reportado al PM en el momento.

4. **Auditoría de cobertura QA de la épica #69** — 42 hijos, **316 casos** `TC-*` escritos,
   ninguno tildado.

5. **Plan de pruebas redactado** — estructura canónica de `QA.md`: alcance, actores y accesos,
   cobertura por las 36 tasks, **12 casos end-to-end nuevos** (`TC-E2E-01` a `TC-E2E-12`), datos
   de prueba, criterios de salida y fuera de alcance. Los end-to-end cubren las costuras que
   ninguna task prueba sola: la unicidad del ciudadano entre el canal de campo y el público
   (`TC-E2E-03`), el último cupo disputado entre ambos canales (`TC-E2E-04`), el lanzamiento por
   capacidad sin deploy (`TC-E2E-06`) y el vencimiento que cierra el link pero no la revisión
   (`TC-E2E-05`).

## Archivos

`docs/internal/requerimientos.md` (esta entrada y la etiqueta `#gestion` nueva en el
vocabulario). El cuerpo del plan de pruebas todavía **no está en el repositorio ni en GitHub**:
se le mostró al PM y quedó a la espera de su OK para publicarse como issue.

## Base de datos

No requiere.

## Validación

Sin código que validar. Cada escritura al Project se verificó releyendo
`gh project item-list` después de aplicarla: los 10 items con `Iteration 7`, las 8 tasks con
assignee, los Status resultantes y la configuración del campo de iteración intacta.
`scripts/requerimientos.py --check` sobre esta entrada.

## Puesta en marcha en el servidor

No requiere.

## Pendientes / a definir

1. **Publicar el `[PLAN DE PRUEBAS]` de la épica #69.** Está redactado y revisado; falta el OK
   del PM para crearlo como issue en Backlog con Tipo = Testing. Mientras no se publique, el
   trabajo de este cambio está a medias — de ahí el semáforo amarillo.
2. **#299 quedó en `Backlog` mientras las otras 7 pasaron a `In QA`.** Hay que emparejar el
   cluster; lo mueve el PM.
3. **El análisis #289 sigue en `Backlog`** aunque está Definido, sin preguntas abiertas y con
   sus 8 sub-issues ejecutados. Corresponde `Done`.
4. **La épica #69 quedó con iteración**, y es la única de las 7 épicas del tablero que la tiene.
   Se hizo porque el pedido fue «a todos»; falta decidir si se mantiene o se limpia por
   convención.
5. **Los 316 casos y los 12 end-to-end están sin ejecutar** (0 tildados). Es el trabajo real que
   el tablero desincronizado estaba ocultando.
6. **Los Cambios 42, 43, 44 y 45 no tienen issue en el Project.** Se entregaron como pedidos
   directos y solo viven en este archivo. Falta decidir si se crean issues retroactivos —como se
   hizo con el #234— o si se acepta explícitamente que no los tengan.
7. **El SMTP de ECOM (task #245) bloquea dos verificaciones:** el correo de confirmación del
   Cambio 41 (#296) y el aviso de resolución del Cambio 44.
8. **El análisis #72 (integración SIS) sigue En análisis**, bloqueado a la espera del contrato
   técnico. Mientras siga así, la épica #69 no se puede consolidar ni dar por probada.

## Reversión

Nada que revertir en el producto. En el Project: limpiar el campo `Iteration` de los 10 items y
quitar el assignee de las 8 tasks devuelve el tablero al estado previo, aunque los Status que
movió la automatización habría que corregirlos a mano. Revertir el commit deshace esta entrada y
la etiqueta `#gestion`.

## Historial

**27/08/2026 — el pendiente 7 quedó desbloqueado y el 8 tiene un motivo más preciso.** ECOM
configuró el SMTP en QA y producción, así que las dos verificaciones que la task **#245**
frenaba —el correo de confirmación del Cambio 41 (**#296**) y el aviso de resolución del Cambio
44— ya se pueden correr: deja de ser un bloqueo externo y pasa a ser trabajo propio, correr
`diagnosticar_correo` desde el servidor.

Sobre el pendiente 8: ECOM entregó la **lectura** de SIIS —el catálogo de programas y la
validación de personas ya funcionan contra el servicio real— pero **no el endpoint para
informarle los confirmados con beca**. El análisis **#72** sigue *En análisis* por eso, no por
falta de trabajo propio, y mientras no exista ese contrato la épica **#69** no se puede
consolidar ni dar por probada. Los otros siete pendientes siguen abiertos, incluido el que
mantiene la entrada en 🟡: publicar el `[PLAN DE PRUEBAS]` de la épica #69. Ver **Cambio 50**.

---

# Cambio 48 — Analizar todo el diseño de Dispositivos, funcional y sobre todo front

🟢 **HECHO — 26/08/2026** (el diagnóstico; la remediación queda planificada, no ejecutada)

| | |
|---|---|
| **Programa / módulo** | Dispositivos |
| **Etiquetas** | `#ui` `#datos` `#rbac` |
| **Solicitante** | PM — pedido directo en sesión de trabajo |
| **Fecha del pedido** | 26/08/2026 |
| **Issue / épica** | Épica #127 · análisis #309 · tasks #310 a #323 |
| **Partes afectadas** | Backoffice |
| **Migración** | No requiere (este cambio no toca código; la task #313 sí necesitará una) |

## Pedido original

«Quiero analizar todo el diseño a nivel funcional y más que nada a diseño front del
programa de dispositivos.» Y después, cerrado el diagnóstico: «generá las task en git,
asignalas a esta iteración y a mi usuario».

## Alcance acordado

**Diagnóstico, no remediación.** El PM eligió explícitamente las tres cosas que acotan
este cambio:

1. **Las 22 plantillas del programa Dispositivos y nada más** — 17 de
   `programas/templates/programas/dispositivos/` y 5 de
   `programas/templates/programas/admisiones/`. Quedaron afuera, por decisión del PM en la
   orquestación: reportes y exportes, el RBAC transversal, el sidebar, Becas, Merenderos y
   el portal ciudadano.
2. **Diagnóstico priorizado**, sin propuesta de rediseño ni wireframes.
3. **El informe en `docs/internal/`**, commiteado en su propia rama.

Después del diagnóstico se sumó, como segundo tramo del mismo pedido, la creación del
backlog en GitHub: análisis contenedor y 14 tasks, asignadas a la iteración activa y al PM.

## Decisiones tomadas

- **El diagnóstico se ejecutó en un worktree aparte, con una sesión paralela.** Se creó
  `C:\Users\mkdir\Proyectos\Chaco-wt-dispositivos` sobre la rama
  `docs/auditoria-diseno-dispositivos`. El motivo es el registrado en la memoria del
  proyecto sobre sesiones concurrentes: dos sesiones sobre el mismo checkout ya hicieron
  caer un commit en la rama equivocada. La auditoría es de solo lectura sobre el producto,
  así que el aislamiento no costó nada.

- **El PM orquestó antes de ejecutar.** No se largó el análisis en crudo: primero se
  clasificó la ruta (diseño, con el agente canónico como gate obligatorio), se identificó
  el programa y se relevó la superficie real —28 rutas, 22 plantillas, 4 módulos de
  vistas— para que el encargo tuviera blancos concretos. Recién con eso se lanzó.

- **Lo mecánico ya estaba limpio, y eso definió el foco.** `scripts/design_audit.py`
  sobre las dos carpetas da **0 errores y 0 warnings**. Igual que en el Cambio 36, el gate
  de cierre pasaba y el módulo seguía teniendo problemas: la conclusión es que el valor
  estaba en lo que el script no puede ver, y así se instruyó el análisis.

- **El diseño ya no era el problema; el circuito sí.** Los badges y las solapas reales del
  Cambio 36 resolvieron la queja visual original. Lo que quedó son agujeros de flujo, y por
  eso este cambio pesa más en lo funcional que en lo visual, al revés de lo que el pedido
  anticipaba.

- **Becas es vara de calidad, no molde visual.** Está por encima en paginación, permisos
  resueltos en la vista y reutilización de includes, y en eso se lo toma como referencia.
  Pero **en confirmaciones Dispositivos está mejor parado**: usa SweetAlert2, pieza
  canónica condicionada, mientras Becas sigue sobre `ModernModal`, clasificado *Legacy solo
  mantenimiento*. Se decide extraer un include propio del módulo y **no** copiar el de
  Becas —lo que corrige el pendiente 3 del Cambio 36, que proponía justamente copiarlo—.

- **Baja lógica, no borrado, para los campos de tipo de dispositivo.** El programa se rige
  por «historial permanente, sin borrar registros», y hoy el borrado o revienta con 500 o
  deja el histórico ilegible. La decisión aplica a la task #313.

- **Las 14 tasks cuelgan de un análisis nuevo, no del #128.** `AGENTS.md` no admite
  sub-issues sin análisis de origen. El #128 define el alcance original del programa
  (F-00/F-01/F-02, merenderos) y estas tasks nacen de una auditoría posterior: mezclarlas
  habría ensuciado la trazabilidad de las dos cosas. Se creó el análisis #309 colgando de
  la épica #127.

- **Iteración y assignees los cargó el PM.** `AGENTS.md` los reserva al PM humano; se
  hicieron por pedido explícito suyo en esta misma sesión. El **Status quedó en Backlog**
  en los 15 issues: no se movió ningún estado.

## Implementación

Lo que existe ahora y antes no:

- Un **informe de auditoría** de 28 hallazgos sobre las 22 plantillas, con el mapa de la
  superficie clasificado pieza por pieza —8 canónicas reutilizables, 7 legacy de
  mantenimiento y 7 duplicadas o conflictivas— y cada hallazgo con su `archivo:línea`,
  qué pasa hoy, impacto en el operador, propuesta concreta y esfuerzo.
- Un **análisis funcional en GitHub** (#309) que consolida el diagnóstico y deja
  registradas las decisiones de arriba, colgando de la épica #127.
- **14 tasks ejecutables** (#310 a #323), agrupando hallazgos que conviene resolver juntos,
  con criterios de aprobación, guía de interfaz y dependencias sugeridas entre ellas.
  Estimación total **89 h**, cargadas en el campo `EstimacionHoras`.

Los cinco hallazgos bloqueantes, que son el corazón del diagnóstico:

| | Hallazgo | Evidencia |
|---|---|---|
| **B1** | El F-00 es de escritura únicamente: se completa al admitir y al trasladar y ninguna pantalla lo muestra después. El indicador «Completitud F-00» acusa un problema que el operador no puede ni mirar ni corregir | `respuestas_f00`, `archivos_f00` y `origen_traslado` no aparecen en **ninguna** plantilla del repo; único lector: `services/indicadores.py:69` |
| **B2** | El traslado sin cama deja a la persona **alojada en el origen y en espera en el destino a la vez**, sin marca en ninguna de las dos pantallas. Único aviso: un toast de 7 segundos | `services/admisiones.py:204-212` no cierra el origen; recién lo hace `:248-249` al promover |
| **B3** | El parte diario **pisa el turno de otro operador** —observaciones y firma— y responde con el mismo mensaje de éxito que cuando lo crea | `services/registro_diario.py:58-67`; mensaje único en `views/admisiones.py:201` |
| **B4** | Eliminar un campo de tipo: **500** si tiene archivos, o historial huérfano si no | `views/dispositivos_config.py:219` sin captura; `models/__init__.py:877` es FK `PROTECT` |
| **B5** | El alta se bloquea **sin decir nada** cuando el código duplicado está fuera del alcance territorial. Le pasa siempre a quien tiene `dispositivo.crear` sin `dispositivo.ver` | `views/dispositivos_legajo.py:133-136` filtra las coincidencias pero no `codigo_duplicado`; `legajo/form.html:28` y `:64` |

Los cinco fueron **verificados contra el código** por el PM antes de crear las tasks, no
tomados por buenos del informe. En esa verificación apareció además un dato que abarata
B5: `views/dispositivos_legajo.py:132` ya calcula y devuelve `hay_coincidencias` **antes**
del filtro territorial —el backend ya expone la señal que falta y el template la ignora—.

## Archivos

- `docs/internal/auditoria-diseno-dispositivos-2026-08.md` — nuevo, el informe completo.
- `docs/internal/requerimientos.md` — esta entrada y el historial del Cambio 36.
- **Ningún archivo de código productivo fue modificado.**

## Base de datos

No requiere. La task #313 necesitará una migración cuando se ejecute (campo `activo` en
`CampoTipoDispositivo` para la baja lógica).

## Validación

- `scripts/design_audit.py` sobre `programas/templates/programas/dispositivos` y
  `programas/templates/programas/admisiones`: **0 errores, 0 warnings**.
- Los 5 hallazgos bloqueantes verificados uno por uno contra el código real: **los 5
  confirmados**, con la línea exacta.
- Los 15 issues verificados con `gh project item-list`: **Status Backlog**, Tipo, Prioridad,
  Módulo `programas/dispositivos`, `EstimacionHoras`, **Iteration 7** y assignee en los 15.
- `manage.py check` **no se corrió**: este cambio no toca código ni configuración de Django.
  Corresponde a cada task de remediación cuando se ejecute.

## Puesta en marcha en el servidor

No aplica. No hay nada que desplegar: es documentación y backlog.

## Pendientes / a definir

1. **Las 14 tasks están sin arrancar**, en Backlog e Iteration 7 (89 h estimadas). Por
   costo/beneficio conviene empezar por **#314** (bajo, desatasca un alta que hoy es un
   callejón sin salida) y **#312** (medio, es el mayor riesgo operativo: dos operadores
   pueden actuar sobre la misma persona sin saberlo). **#310** es el que más valor devuelve
   y el más caro, y arrastra a **#317**.

2. **Dos preguntas abiertas bloquean el arranque de sus tasks**, anotadas en el cuerpo de
   cada una:
   - **#310** — ¿la pantalla de detalle de admisión debe además **permitir completar** el
     F-00 después del ingreso, o es solo de lectura? Cambia el tamaño de la task.
   - **#311** — ¿cuántos días hacia atrás se habilitan para regularizar el parte diario?
     La auditoría propone 7 como valor de partida.

3. **Sin casos de QA.** Ninguna de las 14 tasks tiene su sección «Casos de prueba (QA)».
   Según `ESTADOS.md`, **sin casos de QA una task no es Ready**: hay que pasarles `/qa` antes
   de que el PM las mueva.

4. **La estimación de 89 h es propia, no del equipo.** Se derivó del esfuerzo bajo/medio/alto
   del informe y conviene contrastarla con quien vaya a tomar las tasks.

5. **Los cuatro pendientes del Cambio 36 siguen abiertos** y quedan absorbidos acá: el motor
   de modal AJAX y los dos handlers de confirmación en **#321**, las stat cards en **#317**,
   y la solapa embebida en el legajo **fuera de alcance** —es decisión de producto sobre
   `services/solapas.py`, vive en #179—.

6. **El pendiente del Cambio 23** —el orden de los campos de tipo de dispositivo, que quedó
   sin la regla de autonumerado sin repetidos— queda tomado por **#323**. Incluye verificar
   si hay órdenes repetidos ya cargados en producción, que habría que normalizar primero.

7. **El assignee se infirió.** Las 15 issues se asignaron a `Mkdir-arg` por ser la cuenta
   autenticada y dueña del Project; el otro Matías del repo es `matias-abate` (Matias
   Abate). Si no corresponde, se corrige con un `gh issue edit --add-assignee`.

## Reversión

Revertir los dos commits de documentación (`docs/auditoria-diseno-dispositivos`). Los
issues #309 a #323 **no se revierten con git**: si se descarta el plan hay que cerrarlos a
mano y sacar la fila `- [ ] #309` de la épica #127. No hay datos ni código involucrados.

## Historial

No aplica: entrada nueva.

---

# Cambio 49 — Etiquetar en GitHub a qué programa pertenece cada tarea

🟢 **HECHO — 27/08/2026**

| | |
|---|---|
| **Programa / módulo** | Transversal / gestión |
| **Etiquetas** | `#gestion` `#metodo` |
| **Solicitante** | PM — pedido directo en sesión de trabajo |
| **Fecha del pedido** | 27/08/2026 |
| **Issue / épica** | Sin issue — cambio de gestión sobre el Project #1 |
| **Partes afectadas** | Ninguna del producto: labels del repo en GitHub y método de los agentes |
| **Migración** | No requiere |

## Pedido original

«Quiero que en git en el project pongas una etiqueta nueva o busques una que ya tenemos
y agregues a qué programa pertenecen las tareas, ejemplo las que son de Becas y las que
son de Dispositivos, para diferenciar; tenemos transversales también.»

Y al cerrar el primer tramo: «documentá y sumá tanto al PM como a los otros agentes que
siempre que se cree una tarea se tiene que etiquetar».

## Alcance acordado

Entra: crear las etiquetas de programa, clasificar los 153 items del Project #1 y
documentar la convención en el método de los tres agentes.

Queda explícitamente afuera:

- Separar `merenderos` como cuarta etiqueta (ver Decisiones).
- Limpiar el campo `Modulo` del Project, que queda como eje paralelo y desprolijo.
- Tocar `Status` o cualquier otro campo del Project.

## Decisiones tomadas

- **Etiquetas de repo, no un campo nuevo del Project.** El PM pidió «una etiqueta», y
  además el label gana: se ve en el issue mismo, se filtra con `label:becas`, el Project
  puede agrupar por Labels, y los agentes Analista y QA pueden ponerlo en el mismo
  `gh issue create` sin un `item-edit` extra. Un campo single-select solo se ve dentro
  del Project.
- **Tres etiquetas, no cuatro: Merenderos va dentro de `dispositivos`.** La épica es
  literalmente «Dispositivos y Merenderos» (#127) y el presupuesto que lleva `/pm:horas`
  se computa por Becas/Dispositivos. Si alguna vez hace falta separarlo son 3 issues
  (#181, #182 y parte de #128).
- **El programa no es el módulo, y el campo `Modulo` no servía.** Ya existía `Modulo`
  (texto libre) en el Project, pero guarda el módulo **técnico** y está sucio: 41
  `programas`, 24 `users`, 19 vacíos, más `programas/dispositivos`, `apps/programas` y
  combinaciones tipo `scripts, legajos, configuracion`. Hay trabajo `transversal` que
  vive en `programas` y trabajo de `becas` que vive en `users`: el eje funcional y el
  técnico no coinciden, así que se agregó uno nuevo en vez de reciclar el viejo.
- **Los labels pasan a tener dos ejes independientes:** nivel (`epica`, `analisis`,
  `task`) y programa (`becas`, `dispositivos`, `transversal`). Todo issue lleva uno de
  cada uno; el programa se hereda hacia abajo de la épica al análisis y del análisis a
  sus sub-issues.
- **Cuatro clasificaciones ambiguas, resueltas y confirmadas por el PM:**
  1. Merenderos dentro de `dispositivos`.
  2. La app móvil va a `becas` (#242, #248, #249, #251): la app de campo solo sirve a
     territoriales de Becas, aunque #248 y #251 nazcan del análisis de credenciales.
  3. #79 (roles Admin/Territorial/Coordinador) va a `becas`: el trabajo es RBAC pero los
     roles son los de Becas.
  4. #273 y #278 (H-2, «duplicadas de Becas») van a `transversal`: son tareas de la
     iniciativa de performance, aunque midan consultas de Becas.
- **Se agregó `#metodo` al vocabulario cerrado de este archivo**, porque no había
  etiqueta para cambios en el método de los agentes y el mecanismo está previsto.

## Implementación

Tres labels creadas en `Mkdir-arg/Chaco-Back` y aplicadas a 152 de los 153 items del
Project:

| Label | Color | Issues | Alcance |
|---|---|---|---|
| `becas` | `#0e8a16` | 52 | Relevamiento territorial, convocatorias, segmentos, cupos, nivel Programa (SIIS), app de campo, formulario público, reportes de Becas |
| `dispositivos` | `#d93f0b` | 30 | Legajo institucional, tipos y campos F-00, camas, admisiones y traslados, parte diario F-01, merenderos y prestación alimentaria F-02 |
| `transversal` | `#6e7781` | 70 | RBAC, usuarios y roles, legajo ciudadano, portal, dashboard, performance y observabilidad, infra, CI y design system |

La convención quedó escrita en el método de los tres agentes: `AGENTS.md` la define
(sección «Etiqueta de programa») y es la fuente única; `QA.md` y `PM.md` la referencian
sin duplicarla. El Analista y QA **etiquetan al crear**; el PM Assistant **lee y
reporta**, y solo escribe si el PM humano se lo pide.

## Archivos

- `AGENTS.md` — sección «Etiqueta de programa», los dos ejes, el `gh issue create` con
  doble label, y la regla general de que ningún issue nace sin programa.
- `QA.md` — el `[PLAN DE PRUEBAS]` hereda la etiqueta de su épica; regla general.
- `PM.md` — el eje como fuente de datos, el chequeo 6 de `/pm:salud` con su comando de
  detección, el control cruzado en `/pm:horas` y la regla de «se lee, no se asigna».
- `docs/internal/requerimientos.md` — `#metodo` en el vocabulario, fila 49 y esta entrada.

No se tocó código del producto.

## Base de datos

No requiere.

## Validación

- Clasificación validada antes de escribir: 152 de 153 items, sin huecos, sin duplicados
  y sin números inexistentes.
- Verificación posterior contra GitHub, issue por issue: `becas` 52/52, `dispositivos`
  30/30, `transversal` 70/70; ninguno sin etiquetar y ninguno de más.
- El comando de detección que quedó documentado en `PM.md` se ejecutó y funciona.
- `manage.py check` y la auditoría de diseño no aplican: no se tocó código ni UI.

## Puesta en marcha en el servidor

No requiere.

## Pendientes / a definir

- **#163** quedó sin etiqueta: su título es literalmente «Task», sin tipo ni módulo, y
  está en `Done`. No hay con qué clasificarlo hasta que el PM diga qué era.
- **#161 «Notificaciones»** está abierto, sin etiqueta y **fuera del Project**. Lo
  detectó el comando de `/pm:salud` al probarlo. Hay issues del repo que no están en el
  tablero: conviene una pasada aparte.
- El campo `Modulo` del Project quedó como eje paralelo y desprolijo. Ahora que el
  programa vive en el label, `Modulo` debería quedar solo como módulo técnico o vaciarse.
  Es limpieza estructural del Project y la decide el PM.
- La convención vale de acá en adelante solo si los agentes la cumplen: el chequeo 6 de
  `/pm:salud` es el que lo detecta.

## Reversión

`gh label delete becas` (y `dispositivos`, `transversal`): borrar el label lo quita de
todos los issues, no hace falta desetiquetar uno por uno. Después revertir los bloques
agregados en `AGENTS.md`, `QA.md` y `PM.md`, y esta entrada con su fila del índice y la
etiqueta `#metodo`. No hay datos del sistema en juego ni migración que deshacer.

## Historial

No aplica: entrada nueva.

---

# Cambio 50 — ECOM desbloqueó las dependencias externas: SMTP, Gran Base, SIIS y despliegue

🟡 **PARCIAL — 27/08/2026 · ocho dependencias externas cerradas; falta el endpoint de salida de SIIS y verificar los envíos**

| | |
|---|---|
| **Programa / módulo** | Transversal · Becas / integraciones |
| **Etiquetas** | `#infra` `#correo` `#siis` `#gestion` |
| **Solicitante** | PM — reporte punto por punto, en sesión de trabajo, sobre la lista de pendientes de este archivo |
| **Fecha del pedido** | 27/08/2026 |
| **Issue / épica** | #245 (SMTP), #244 (textos), #296 (correo de confirmación), #72 (integración SIS) |
| **Partes afectadas** | Infra/ECOM · Backoffice · Portal · Servidor/API |
| **Migración** | No requiere |

## Pedido original

El PM informó, punto por punto sobre la lista de pendientes que salió de este archivo, qué
resolvió ECOM:

1. «ECOM ya configuró los SMTP en prd y qa».
2. «Ya se definió el dominio en `gov.ar`».
3. «Ya configuraron la Gran Base».
4. «Ya los incorporó» — los cuatro programas al catálogo de SIIS.
5. «Ya incorporó las credenciales de SIIS».
6. «Ya se corrió el set de datos» — `seed_datos_base` en testing.
7. «Ya desplegaron todo».
8. «Estamos integrados al momento de traer los programas, validar personas, pero por ahora no
   nos dieron el endpoint para enviarle los confirmados con becas».
9. «Ya cambiaron el `admin`».

## Alcance acordado

Esta entrada **no es un desarrollo**: es el registro del desbloqueo externo y de los semáforos
que mueve. Entra actualizar el estado de las entradas afectadas con su historial fechado, dejar
asentado lo que el desbloqueo **no** resuelve, y corregir un criterio que había quedado mal
registrado. Queda explícitamente afuera ejecutar las verificaciones que el desbloqueo recién
ahora hace posibles —`diagnosticar_correo`, los 65 casos de QA del formulario público—: eso es
trabajo propio y figura como pendiente, no como hecho.

## Decisiones tomadas

- **El dominio de la casilla de correo es `gov.ar`.** Cierra la duda del Cambio 37, donde Infra
  pedía `gov.ar` y las credenciales entregadas decían `gob.ar`. Como los dos nombres resuelven
  a la misma IP, `EMAIL_HOST` era indiferente: lo que faltaba definir era el usuario de
  autenticación y el remitente, que tienen que ser la misma dirección.
- **«SMTP configurado» no es «SMTP verificado».** Se movieron los semáforos que dependían de
  que ECOM entregara el servidor, pero no los que dependen de comprobar que un correo llega.
  Poner los Cambios 37 y 44 en verde hoy sería registrar como probado algo que nadie vio salir;
  siguen en 🟡 hasta que `diagnosticar_correo` corra desde el servidor.
- **La integración con SIIS quedó cerrada solo en su mitad de lectura**, y así se registra. El
  sistema trae el catálogo de programas y valida personas contra el servicio real, pero no hay
  cómo informarle los beneficiarios confirmados. No se va a escribir ese envío a ciegas: sin el
  contrato del endpoint, cualquier implementación es una apuesta que después habría que
  rehacer. Es el mismo criterio con el que el Cambio 8 se negó a cargar programas a mano.
- **Los cuatro programas del Cambio 8 aparecieron sin desarrollo de este lado**, como estaba
  previsto: el selector consume el catálogo. Lo que queda es operativo —vincular los segmentos
  viejos que no tienen programa—, no de código.
- **Se corrige un criterio mal registrado, no se borra.** El punto 3 del historial del Cambio 31
  (11/08/2026) decía que el backend SMTP solo se activa con `ENVIRONMENT=prd`. El Cambio 37
  cambió eso y nadie lo asentó. Se deja el texto viejo y se agrega la corrección fechada, como
  manda la regla de oro.

## Implementación

No hubo cambios de código: el sistema ya estaba preparado para las tres integraciones y lo que
faltaba era configuración del otro lado. El trabajo fue de registro:

- Pasaron a 🟢 los Cambios **8** (programas en el catálogo), **13** (SMTP), **28** (contraseña
  del `admin`) y **31** (despliegue).
- Siguen en 🟡, con el motivo acotado, los Cambios **37** y **44**: ya no los frena ECOM, los
  frena la verificación del envío y la aprobación de los textos.
- Recibieron historial sin cambiar de semáforo los Cambios **27**, **29**, **30**, **33**, **41**
  y **47**.

## Archivos

- `docs/internal/requerimientos.md` — esta entrada, su fila del índice y el historial fechado de
  los Cambios 8, 13, 27, 28, 29, 30, 31, 33, 37, 41, 44 y 47.

## Base de datos

No requiere migración.

## Validación

- `scripts/requerimientos.py --check` → OK, el índice y las entradas coinciden.
- **Verificado en el código, no asumido:** `config/settings.py` elige el backend de correo por
  la presencia de `EMAIL_HOST`, no por el `ENVIRONMENT`, así que el QA con SMTP cargado manda
  correo real, distinguible solo por el prefijo `[QA]` del asunto (`EMAIL_ASUNTO_PREFIJO`). Esto
  es lo que **corrige** el punto 3 del historial del Cambio 31.
- **Verificado en el código:** `programas/services/siis.py` expone únicamente
  `listar_programas`, `listar_programas_todos` y `validar_compatibilidad`. No hay método de
  escritura ni a medias, lo que confirma que el envío de confirmados está entero por hacer.
- Existen los dos comandos que cierran las verificaciones pendientes:
  `users/management/commands/diagnosticar_correo.py` y
  `programas/management/commands/diagnosticar_integraciones.py`.

## Puesta en marcha en el servidor

Nada de este lado. Lo que el desbloqueo habilita y conviene correr cuanto antes:

1. `manage.py diagnosticar_correo` en QA y en producción — es lo que cierra los Cambios 37 y 44
   y las verificaciones #245 y #296.
2. `manage.py diagnosticar_integraciones` para dejar asentada la respuesta real del catálogo de
   SIIS con las credenciales nuevas.

## Pendientes / a definir

1. **Endpoint de salida de SIIS: informar los beneficiarios confirmados con beca.** ECOM no lo
   entregó. Es la mitad faltante de la integración, lo que mantiene el análisis **#72** en *En
   análisis* y lo que impide consolidar la épica **#69**. Hasta que exista el contrato no hay
   nada que implementar.
2. **Verificar el envío real de correo** con `diagnosticar_correo` en QA y producción (task
   **#245**). Desbloquea los Cambios 37 y 44 y la verificación del correo de confirmación
   (**#296**).
3. **Aprobación de los textos (#244)**: los de credenciales y los cuatro avisos de resolución
   del Cambio 44. La firma es del cliente y del programa de Becas; el SMTP no la desbloquea.
4. **Vincular a su programa los segmentos existentes que no lo tienen** (Cambio 8 más el
   pendiente del Cambio 32). Con los cuatro programas ya en el catálogo es una pasada operativa.
5. **Ejecutar los 65 casos de QA del formulario público** (Cambio 41): con la Gran Base
   configurada el paso 1 precarga y el circuito se puede probar de verdad.
6. **Del Cambio 27 sigue abierto lo que este desbloqueo no toca**: URL de QA, política de
   actualización de `main`, accesos a ArgoCD, quién define el CronJob de sync de SIIS, y la app
   móvil apuntando al entorno viejo.
7. **Confirmar el espejado de `.env.qa.example`** (Cambio 30): el ambiente levanta, pero que su
   ambiente tenga las variables correctas no prueba que el archivo de ejemplo haya viajado.
8. **Cambiar también la contraseña del `admin` en testing y QA** si ECOM cambió solo la de
   producción. El Cambio 28 pedía las tres; el reporte dice «ya cambiaron el `admin`» sin
   distinguir ambiente.

## Reversión

No aplica: no hay código. Si alguno de los ocho puntos resultara no estar hecho, se corrige con
un historial nuevo en la entrada afectada, sin borrar este.

## Historial

No aplica: entrada nueva.
# Cambio 51 — El panel de marca del formulario de inscripción se estiraba con el formulario

🟢 **HECHO — 27/08/2026**

| | |
|---|---|
| **Programa / módulo** | Portal ciudadano · inscripción pública de Becas (shell del Cambio 43) |
| **Etiquetas** | `#ui` `#relevamientos` |
| **Solicitante** | PM — pedido directo en sesión de trabajo, mirando el link real de una convocatoria en producción |
| **Fecha del pedido** | 27/08/2026 |
| **Issue / épica** | Sin issue (ajuste estético del Cambio 43, que cuelga del análisis #289) |
| **Partes afectadas** | Portal ciudadano (las seis pantallas del flujo de inscripción, solo en escritorio) |
| **Migración** | No requiere |

## Pedido original

> «La sección cuadrada que engloba esto "¿Necesitás ayuda? +54 362 430-0002 · datanach@chaco.gob.ar
> © 2026 DATAÑACH — Gobierno del Chaco": si el form es muy extenso se agranda y eso tendría que ser
> fijo. En realidad todo el cuadrado que tiene a la izquierda, que engloba todo eso, tiene que ser
> fijo, y cuando escroleás el form eso está fijo y el form solo va para abajo.»

## Alcance acordado

- El panel izquierdo de escritorio (gradiente con marca, título de la convocatoria y stepper, más el
  pie navy con ayuda y copyright) queda fijo en la ventana; scrollea únicamente la columna del
  formulario.
- Aplica a las **seis pantallas** del link porque todas extienden el mismo shell: paso 1, paso 2,
  comprobante, «ya estás inscripto», «no disponible» y «demasiados intentos».
- **Afuera:** el celular (ahí el panel es cabecera y tiene que seguir scrolleando con la página), los
  campos y la lógica de los formularios, y el shell de la home del portal.

## Decisiones tomadas

- **El panel se fija con `position: fixed`, no envolviendo cabecera y pie en un contenedor sticky.**
  La alternativa —un `<div>` que envuelva `aside` + `footer` y sea `sticky` de 100vh— obligaba a
  poner el pie antes del `<main>` en el HTML, y en celular eso deja los links de ayuda en el orden de
  tabulación antes de los campos del formulario (WCAG 2.4.3). Con `fixed` el HTML no se toca: el
  cambio es solo CSS dentro del `@media (min-width: 1024px)`, y el celular queda idéntico a como
  estaba.
- **La columna izquierda del grid la sostiene el track explícito.** Al salir del flujo las dos piezas
  del panel, la primera columna queda vacía, pero `grid-template-columns: var(--di-panel-w) minmax(0,1fr)`
  la mantiene en 520px y el `<main>` sigue arrancando en el mismo lugar. No hubo que agregar padding
  al shell ni tocar la columna de contenido.
- **El ancho del panel pasó a ser una variable del shell (`--di-panel-w: 520px`).** Ahora el número
  aparece en tres lugares (el track del grid y el `width` de cabecera y pie): declararlo una sola vez
  evita que se desincronicen en el próximo ajuste.
- **La cabecera fija tiene scroll propio y aire abajo (`overflow-y: auto`, `padding-bottom: 136px`).**
  Medido: el pie mide 112px de alto en todos los anchos de escritorio (no llega a envolver ni a
  1024px) y el contenido del panel termina a 517px. Con eso, en ventanas de 650px de alto o más no
  hay scroll interno; en ventanas más bajas el contenido del panel sigue siendo alcanzable en vez de
  quedar tapado por el pie. Dentro de la cabecera no hay nada enfocable —marca, título y stepper son
  texto— así que el contenedor scrollable no puede atrapar el foco de teclado.

## Implementación

`portal/templates/portal/inscripcion/base_inscripcion.html`, solo el `<style>` del shell: la variable
`--di-panel-w` en `.di-shell` y, dentro del `@media (min-width: 1024px)`, `.di-panel-head` fija a
`top: 0` con `height: 100vh` y `.di-panel-foot` fija a `bottom: 0`, las dos con
`width: var(--di-panel-w)`. Ni el HTML, ni los bloques de Django, ni el include del stepper, ni el
CSS de celular cambiaron.

## Archivos

`portal/templates/portal/inscripcion/base_inscripcion.html` · `.claude/agents/chaco-design-system.md`
(fila «Shell de inscripción pública», que ahora describe el panel fijo).

## Base de datos

No requiere.

## Validación

- `manage.py check` sin observaciones · `scripts/design_audit.py --changed` **0 errores, 0 warnings** ·
  `scripts/compile_templates.py` 329 plantillas, 0 errores.
- Verificación visual con Playwright sobre el shell renderizado con un formulario de 30 campos: en
  1440×900, con la página scrolleada 1200px, la cabecera queda en `(0, 0, 520×900)` y el pie en
  `(0, 788, 520×112)` mientras el contenido se desplaza; sin scroll horizontal
  (`scrollWidth == innerWidth`) en 1024, 1100, 1280, 1440 y 1920px.
- En 390×844 (celular) la cabecera sigue `static` y el orden cabecera → contenido → pie no cambió.
- Con contenido corto (pantallas de resultado) la página mide exactamente una ventana: el panel se ve
  completo y no aparece hueco.

## Puesta en marcha en el servidor

Solo el deploy. Sin variables, cron ni migración. Es CSS embebido en el template: no requiere rebuild
de Tailwind ni `collectstatic`.

## Pendientes / a definir

- Si alguna vez se imprime el comprobante (hoy no hay botón de impresión), conviene agregar un
  `@media print` que devuelva el panel al flujo: un elemento `fixed` puede repetirse o recortarse en
  la impresión.

## Reversión

Quitar del `@media (min-width: 1024px)` las declaraciones `position/top/bottom/left/width/height/overflow-y`
de `.di-panel-head` y `.di-panel-foot` y devolverle a la cabecera `padding: 40px 48px`. El panel vuelve
a estirarse con el formulario; no hay datos ni contratos involucrados.

## Historial

No aplica: entrada nueva.

---
# Cambio 52 — El formulario público moría en un 403 de CSRF si el backoffice estaba abierto

🟢 **HECHO — 27/08/2026**

| | |
|---|---|
| **Programa / módulo** | Portal ciudadano · inscripción pública de Becas |
| **Etiquetas** | `#ui` `#sesion` `#relevamientos` |
| **Solicitante** | PM — reportó el 403 mirando un link real de convocatoria en producción |
| **Fecha del pedido** | 27/08/2026 |
| **Issue / épica** | Sin issue (cuelga del análisis #289, formulario público) |
| **Partes afectadas** | Portal ciudadano (los dos formularios del flujo público) · `CSRF_FAILURE_VIEW` de todo el portal |
| **Migración** | No requiere |

## Pedido original

> «¿Por qué da este error en prd? "Prohibido (403) — Verificación CSRF fallida. Petición abortada."»
> Y al confirmar el escenario: «Fue al tocar continuar del paso 1. Lo abrí en otra pantalla y levantó, si
> tenía las dos abiertas [fallaba]. El link es público, tiene que ser indistinto si es backoffice.»

## Alcance acordado

- Que el envío del formulario público no dependa de lo que pase en otra pestaña del mismo navegador.
- Que un CSRF fallido en el portal sea una pantalla de la que se pueda salir, no el 403 crudo de Django.
- **Afuera:** el 403 del backoffice (sigue con la pantalla de Django), y separar el dominio o las cookies
  del portal respecto del backoffice, que es decisión de infraestructura.

## Decisiones tomadas

- **La causa es la rotación de la cookie CSRF, no una falla de configuración.** Se descartaron a mano las
  dos causas típicas contra el link real de producción: el POST completo desde afuera pasa CSRF y llega al
  captcha (200), y el rechazo por `Referer` ausente prueba que Django se ve a sí mismo como HTTPS, o sea que
  `X-Forwarded-Proto` llega bien y no falta `DJANGO_CSRF_TRUSTED_ORIGINS`. Lo que rompe es que
  `django.contrib.auth.login` llama a `rotate_token()` (`contrib/auth/__init__.py`): el backoffice y el
  portal comparten `datanach.chaco.gob.ar`, así que iniciar sesión en el backoffice le cambia la cookie
  `csrftoken` a **todo** el navegador y el formulario público abierto en otra pestaña queda con un token que
  ya no vale.
- **Se resolvió refrescando el token, no eximiendo la vista de CSRF.** `@csrf_exempt` en un POST público que
  dispara consultas de identidad y crea inscripciones es una regresión de seguridad; el paso 2 además
  escribe. El shell pide el token vigente cuando la pestaña vuelve al frente y reemplaza el
  `csrfmiddlewaretoken` de los formularios. Endpoint nuevo `GET /portal/csrf/` (`csrf_token_vigente`), que
  devuelve el mismo token que ya viaja en el HTML y solo es legible desde el propio origen —no hay
  `django-cors-headers` en el proyecto, así que ningún sitio externo puede leerlo.
- **El refresco no intercepta el envío.** Se dispara en `visibilitychange`, `focus` y `pageshow` persistido
  (el botón «atrás» también restaura páginas con token viejo), con throttle de 30 s, y no toca el `submit`:
  así no puede demorar ni romper el envío, ni pelearse con el reCAPTCHA. Si el pedido falla, se manda el
  token original y el formulario funciona como antes.
- **La red de contención es una pantalla recuperable, no el 403 de Django.** `CSRF_FAILURE_VIEW`
  (`config.views.csrf_failure`) devuelve para las rutas `/portal/` la pantalla `portal/sesion_vencida.html`
  —el mismo shell de inscripción, con el botón «Volver a cargar el formulario»— y para el resto conserva la
  pantalla de Django tal cual estaba. Motivo: cualquiera que sea la causa (token viejo, cookies bloqueadas,
  `Origin`/`Referer` borrados por una extensión), un ciudadano tiene que poder seguir; y el backoffice es
  superficie con login, se toca aparte.
- **El destino del botón se sanea.** Se vuelve a `request.get_full_path()` solo si empieza con una barra y no
  con dos: `//otro-dominio` es una ruta válida para el navegador pero una URL absoluta dentro de un `href`, y
  ahí el 403 se volvía un redirect abierto. Hay test.
- **Queda registrado el efecto hermano, que no se toca acá:** el `logout()` del backoffice hace
  `session.flush()` y se lleva la identificación del paso 1 guardada en la sesión (la persona vuelve al paso
  1). El `login()` en cambio usa `cycle_key()` y **conserva** los datos. Separar de verdad las dos
  superficies pide dominio o cookies distintas, que es de ECOM.

## Implementación

- `portal/views/inscripcion.py`: `csrf_token_vigente` (`@require_GET`, `JsonResponse` con `Cache-Control: no-store`).
- `portal/urls.py`: `path("csrf/", …, name="csrf_token")`.
- `config/views.py`: `csrf_failure` + `_destino_seguro`; `config/settings.py`: `CSRF_FAILURE_VIEW`.
- `portal/templates/portal/sesion_vencida.html` (nueva) y el script inline del shell
  `portal/templates/portal/inscripcion/base_inscripcion.html`.

## Archivos

`portal/views/inscripcion.py` · `portal/urls.py` · `config/views.py` · `config/settings.py` ·
`portal/templates/portal/sesion_vencida.html` (nuevo) ·
`portal/templates/portal/inscripcion/base_inscripcion.html` ·
`portal/tests/test_csrf_publico.py` (nuevo) · `.claude/agents/chaco-design-system.md`.

## Base de datos

No requiere.

## Validación

- Diagnóstico contra producción antes de tocar código, sobre el link reportado: GET con `Set-Cookie:
  csrftoken` presente; POST con cookie y token de la misma visita → **200** (llega al captcha); token de una
  visita con cookie de otra → **403**; token sin cookie → **403**; cookie y token correctos sin `Origin` ni
  `Referer` → **403**. Dos GET seguidos devolvieron tokens distintos con su propio `Set-Cookie`, así que no
  hay HTML cacheado. Los POST de prueba usaron `dni=1` y murieron en el captcha: no crearon nada.
- `portal/tests/test_csrf_publico.py`: 7 tests, **OK** en un venv igual al CI (Python 3.12 + Django 5.2.17).
  Cubren el endpoint (200, `no-store`, 405 en POST, y que su token sirve para enviar), la pantalla del portal
  (403 + template + botón + ruta de vuelta), que fuera del portal no se usa esa pantalla, y el saneo del
  destino.
- Suites del portal en el mismo venv: `test_inscripcion`, `test_inscripcion_envio`, `test_inscripcion_correo`,
  `test_seguridad_publica`, `test_ciudadano_auth`, `test_package_exports` → **83 tests OK**.
- `manage.py check` sin observaciones · `scripts/design_audit.py --changed` **0 errores, 0 warnings** ·
  `scripts/compile_templates.py` 330 plantillas, 0 errores · `scripts/check_design_agent.py --base development` OK.
- Revisión visual de `sesion_vencida.html` renderizada: panel, botón de marca y pie correctos.

## Puesta en marcha en el servidor

Solo el deploy. Sin variables, cron ni migración. Conviene avisarle a ECOM que **`/portal/csrf/` no se puede
cachear** en el WAF que está adelante del dominio (hoy responde con `Cache-Control: no-store`).

## Pendientes / a definir

- Decidir con ECOM si el backoffice y el portal público van a seguir compartiendo dominio. Mientras lo
  compartan, un `logout()` en el backoffice le sigue borrando al mismo navegador la identificación del paso 1
  (vuelve al paso 1, sin 403).
- El 403 de CSRF del backoffice sigue mostrando la pantalla cruda de Django. Cambiarla implica que
  `403.html` (que extiende `includes/main.html`) renderice bien para un usuario anónimo; se evaluó y se dejó
  afuera de este cambio.

## Reversión

Quitar `CSRF_FAILURE_VIEW` de `config/settings.py` (vuelve la pantalla de Django), el script del shell y la
ruta `portal:csrf_token`. El formulario queda como estaba, con el 403 en el escenario de las dos pestañas.

## Historial

No aplica: entrada nueva.

---
# Cambio 53 — «Relevamiento» y «caso» son dos cosas y la UI usaba la misma palabra para las dos

🟢 **HECHO — 27/08/2026**

| | |
|---|---|
| **Programa / módulo** | Becas · backoffice (relevamientos, revisión, cupo) y solapa de Legajos |
| **Etiquetas** | `#textos` `#ui` `#metodo` |
| **Solicitante** | PM — pedido directo en sesión de trabajo, mientras se analizaban los estados |
| **Fecha del pedido** | 27/08/2026 |
| **Issue / épica** | Sin issue (cuelga del análisis de estados; ver Pendientes) |
| **Partes afectadas** | Nueve plantillas del backoffice y los mensajes de dos vistas |
| **Migración** | No requiere |

## Pedido original

> «Cuando yo hablo de relevamientos me refiero al formulario en sí, no a las personas que
> confirmaron un relevamiento. Dejemos claros esos dos conceptos: relevamientos = parametría,
> con sus estados; casos = personas que completaron el formulario de relevamientos, tanto
> público como por territorial.» Y ante el relevamiento de textos: «dale, renombrá.»

## Alcance acordado

- Los textos **visibles** del backoffice de Becas que dicen «formulario» hablando de la
  persona que completó el relevamiento pasan a decir **«caso»**.
- **Afuera:** el modelo, las rutas, los identificadores de Python y el contrato de la API de
  campo (la app móvil depende de esos nombres); el portal ciudadano; y «formulario público»,
  que nombra al *tipo de relevamiento* y por lo tanto ya usa la palabra en el sentido del PM.

## Decisiones tomadas

- **El vocabulario queda fijado así:** «relevamiento» es la parametría —la campaña con sus
  seis estados, territorial o pública—; «caso» es la persona que la completó, por link público
  o por territorial. En el código el caso sigue siendo el modelo `Formulario`.
- **La ambigüedad estaba dentro del producto, no solo en la conversación.** El tipo de
  relevamiento se mostraba como «Formulario público» (sentido parametría) y las pantallas de
  revisión decían «Revisión de formularios» y «formularios cargados» (sentido caso): la misma
  palabra con los dos significados en pantallas contiguas.
- **No se renombró el modelo `Formulario` a `Caso`.** Sería un refactor grande —migración,
  relaciones, serializers, la app de campo— sin beneficio funcional. Se documentó la
  traducción en el docstring del módulo de revisión y en el comentario del badge de estado,
  para que quien lea el código sepa que un `Formulario` es un caso.
- **Los mensajes al usuario se renombraron también**, no solo los títulos: un toast que dijera
  «Formulario aprobado» contra una pantalla titulada «Casos» reinstala la ambigüedad. Incluye
  los dos textos que se escriben en la traza del conflicto de duplicados, que se leen desde la
  pantalla del caso.
- **«Formulario N» pasó a «Caso N»** en el título del detalle, en la fila de la tabla y en el
  título del navegador; el número no cambió (sigue siendo el número dentro del relevamiento).

## Implementación

Textos renombrados: «Revisión de formularios» → «Revisión de casos»; la columna «Formulario» de
las tres tablas (detalle del relevamiento, revisión y cupo del segmento); «Caso N» en el detalle;
los vacíos «todavía no tiene casos cargados», «No hay casos pendientes», «Sin casos»; «Casos en
el Programa Becas» en la solapa del ciudadano; «Casos cuya identidad todavía requiere
validación»; los modales «Rechazar caso» y «¿Aprobar caso?»; y los mensajes «Caso aprobado»,
«Caso rechazado», «Caso actualizado», «Caso agregado a la lista de espera», «Quedan N caso(s) sin
revisar», «Solo se pueden rechazar casos pendientes de resolución», «El caso no tiene un
ciudadano vinculado».

## Archivos

`programas/templates/programas/becas/revision/personas_list.html` · `formulario_list.html` ·
`formulario_detalle.html` · `renaper_pendientes.html` ·
`programas/templates/programas/becas/relevamientos/relevamiento_detail.html` ·
`convocatoria_detail.html` · `programas/templates/programas/becas/cupo/segmento_detail.html` ·
`_resumen_ciudadano.html` · `_formulario_estado_badge.html` · `programas/views/revision.py` ·
`programas/views/cupo.py` · `programas/urls.py` · `programas/tests/test_becas_revision.py`.

## Base de datos

No requiere.

## Validación

- `manage.py check` sin observaciones · `scripts/design_audit.py --changed` **0 errores** (3 WARN
  de `outline:none` preexistentes, en líneas que este cambio no toca) ·
  `scripts/compile_templates.py` 330 plantillas, 0 errores.
- `programas.tests.test_becas_revision` + `legajos.tests`: **83 tests OK** en un venv igual al CI
  (Python 3.12 + Django 5.2.17). Un test asertaba el texto viejo del cartel de GPS
  («Este formulario no tiene coordenadas GPS registradas») y se actualizó al nuevo.
- Suites de Becas completas antes del ajuste del test: 181 tests, con esa única falla, ya corregida.

## Puesta en marcha en el servidor

Solo el deploy. Sin variables, cron ni migración.

## Pendientes / a definir

- El análisis de los estados del relevamiento sigue abierto y es el motivo por el que apareció
  este vocabulario: hoy **no existe la transición `EN_REVISION → EN_CURSO`** y el cron de
  vencimientos revierte cualquier reapertura que no venga con las fechas corridas. Quedan seis
  decisiones del PM antes de implementar «volver a campo» (capacidad, si se vuelve desde
  `TERMINADO`, qué pasa con la convocatoria cerrada, si la app puede seguir editando casos ya
  cargados durante la revisión, si la carga tardía sin señal tiene que poder entrar, y si un
  rechazo se puede deshacer).
- La documentación pública de `docs/client/` todavía usa «formulario» en el sentido de caso.
  Conviene alinearla en la próxima pasada de documentación, no en este cambio.

## Reversión

Revertir el commit: son textos, sin efecto sobre datos ni contratos.

## Historial

No aplica: entrada nueva.

---
# Cambio 54 — Un relevamiento en revisión no se podía volver a poner en curso

🟢 **HECHO — 27/08/2026**

| | |
|---|---|
| **Programa / módulo** | Becas · relevamientos y revisión (backoffice) |
| **Etiquetas** | `#relevamientos` `#rbac` `#ui` `#convocatorias` |
| **Solicitante** | PM — pedido directo en sesión de trabajo, con el análisis de estados a la vista |
| **Fecha del pedido** | 27/08/2026 |
| **Issue / épica** | Sin issue (cuelga del análisis #289; vocabulario en el Cambio 53) |
| **Partes afectadas** | Detalle del relevamiento, pantalla de revisión, regla de vencimiento |
| **Migración** | No requiere |

## Pedido original

> «Me di cuenta de que en los relevamientos, cuando está en estado En revisión, no lo puedo
> pasar a En curso, como para abrirlo de nuevo. Analizá todos los flujos de estados.» Y al
> definir el modelo: «para mí el que tiene `becas.relevamiento.editar` es el que puede pasar
> los estados, puede finalizarlo, puede pasarlo a un estado en curso, y en revisión se pasa
> solo con la fecha.»

## Alcance acordado

- Devolver a campo un relevamiento cerrado, desde `FINALIZADO` **y** desde `EN_REVISION`.
- `EN_REVISION` pasa a ser un estado **solo automático**: se llega por vencimiento de fecha.
- **Afuera:** deshacer una resolución de un caso, cerrar la edición de casos ya cargados durante
  la revisión, la ventana de sincronización tardía (`FINALIZANDO`) y la traza propia del
  relevamiento. Están en Pendientes.

## Decisiones tomadas

- **Todas las transiciones manuales son de `becas.relevamiento.editar`**, como lo definió el PM:
  finalizar y volver a campo. `becas.revision.editar` queda para el trabajo de revisión —resolver
  casos— más el cierre («Marcar terminado»), que no se movió de dueño en este cambio.
- **A `EN_REVISION` se llega solo por fecha.** Se eliminó el botón manual «Iniciar revisión» junto
  con su vista y su ruta (`revision_iniciar`): el único camino a ese estado es la regla
  `becas.relevamiento` de `procesar_vencimientos`. Así el estado significa una sola cosa —«la
  fecha cerró el campo y todavía no se terminó»— en vez de ser dos cosas según quién lo puso.
- **Consecuencia obligada: «Marcar terminado» ahora también sale de `FINALIZADO`.** Si a
  `EN_REVISION` solo se llega por vencimiento, un relevamiento cerrado a mano no habría podido
  terminarse hasta que venciera su fecha. Sigue exigiendo cero casos sin revisar. Revisar nunca
  dependió del estado, así que no se pierde nada por el camino.
- **Volver a campo exige fecha futura y convocatoria vigente. No es preferencia, es mecánica:**
  el cron devuelve a `EN_REVISION` todo lo abierto de una convocatoria vencida y todo `ASIGNADO`
  o `EN_CURSO` con `fecha_hasta` pasada. Sin esas dos condiciones la reapertura duraría hasta las
  03:10 y el problema volvería disfrazado de fantasma. Con la convocatoria cerrada o vencida se
  bloquea con un mensaje que dice qué hacer (extender su fecha de fin), porque reabrir la
  convocatoria es una decisión de programa, no de un relevamiento.
- **La fecha nueva es opcional cuando el período sigue vigente**, para no complicar el caso
  simple: un `FINALIZADO` que todavía está en fecha vuelve a campo con un clic, como antes.
- **La reapertura queda en el log de la aplicación** (`relevamiento_volver_a_campo`) con estado
  anterior, usuario y fecha nueva. El relevamiento no tiene traza propia como los casos y los
  dispositivos; hasta que exista, esto es lo que hay.
- **La API de campo no cambió.** Su `reabrir` sigue aceptando solo `FINALIZADO` y exigiendo estar
  dentro del período: es contrato con la app móvil y un vencido no pasaría igual.

## Implementación

- `programas/forms.py`: `VolverACampoForm` — `fecha_hasta` opcional, validada futura y dentro del
  período de la convocatoria.
- `programas/views/relevamientos.py`: `relevamiento_reabrir` reescrita como «volver a campo»
  (acepta `FINALIZADO` y `EN_REVISION`, valida convocatoria y fecha, limpia `fecha_finalizado`,
  actualiza `fecha_hasta`, loguea); el detalle pasa el form nuevo al contexto.
- `programas/views/revision.py`: se eliminó `relevamiento_iniciar_revision`;
  `relevamiento_terminar` acepta `ESTADOS_TERMINABLES` (`FINALIZADO`, `EN_REVISION`).
- `programas/urls.py`: se eliminó la ruta `revision_iniciar`.
- UI: tarjeta «Volver a campo» con la fecha en el detalle del relevamiento (con el texto que
  explica por qué se pide la fecha), y en la pantalla de revisión el botón «Volver a campo»
  —para quien tenga `becas.relevamiento.editar`— más «Marcar terminado» en los dos estados.

## Archivos

`programas/forms.py` · `programas/views/relevamientos.py` · `programas/views/revision.py` ·
`programas/urls.py` ·
`programas/templates/programas/becas/relevamientos/relevamiento_detail.html` ·
`programas/templates/programas/becas/revision/formulario_list.html` ·
`programas/tests/test_becas_relevamientos.py` · `programas/tests/test_becas_revision.py`.

## Base de datos

No requiere.

## Validación

- `programas.tests.test_becas_relevamientos` + `test_becas_revision` + `test_becas_vencimientos`
  + `test_becas_rbac`: **139 tests OK** en un venv igual al CI (Python 3.12 + Django 5.2.17).
- Tests nuevos: volver a campo desde `FINALIZADO` con período vigente y desde `EN_REVISION` con
  fecha nueva; rechazo sin fecha, con fecha pasada, con convocatoria cerrada y desde `TERMINADO`;
  y el que cierra el círculo: después de volver a campo, `relevamientos_de_convocatoria_vencida()`
  ya no lo incluye, o sea que el cron no lo revierte.
- Tests actualizados: el que afirmaba que reabrir rechazaba `EN_REVISION` (era el comportamiento
  que se vino a cambiar) y el de «iniciar revisión», reemplazado por terminar desde `FINALIZADO`.
- `manage.py check` sin observaciones · `scripts/design_audit.py --changed` **0 errores** (3 WARN
  de `outline:none` preexistentes) · `scripts/compile_templates.py` 330 plantillas, 0 errores.

## Puesta en marcha en el servidor

Solo el deploy. Sin variables, cron ni migración. El CronJob de `procesar_vencimientos` (03:10)
no cambia: sigue siendo el único que pone `EN_REVISION`.

## Pendientes / a definir

- **La app puede seguir editando casos ya cargados y subiéndoles adjuntos en cualquier estado**, y
  el permiso no caduca (valida la fecha de captura, que ya quedó fija). Decidir si se cierra a
  partir de `EN_REVISION`.
- **La carga tardía sin señal se pierde**: el cron cierra la entrada a las 03:10 y la app recibe
  409 aunque la captura sea de dentro del período. `FINALIZANDO (sync)` era el estado para esa
  ventana y nadie lo escribe. Definir con el equipo de la app móvil.
- **Un rechazo no se puede deshacer** y el rechazado tampoco puede reinscribirse por el link
  (la regla de duplicado cuenta `RECHAZADO` y `BAJA`, anotado en el código como decisión por
  omisión). Confirmar con el programa.
- **El relevamiento no tiene traza propia**: los cambios de estado solo quedan en el log.
- Decidir si «Marcar terminado» también pasa a `becas.relevamiento.editar`, por coherencia con
  «el que mueve los estados»; hoy quedó con `becas.revision.editar`.

## Reversión

Revertir el commit devuelve el botón «Iniciar revisión» con su ruta y vuelve a limitar la
reapertura a `FINALIZADO`. No hay datos ni contratos involucrados; la app móvil no se tocó.

## Historial

No aplica: entrada nueva.

---
# Cambio 55 — Validar la identidad a mano cuando Base de Personas no puede validar

🟢 **HECHO — 27/08/2026**

| | |
|---|---|
| **Programa / módulo** | Becas · revisión de casos (backoffice) |
| **Etiquetas** | `#siis` `#rbac` `#ui` `#datos` |
| **Solicitante** | PM — pedido directo en sesión de trabajo, mirando un caso real en producción |
| **Fecha del pedido** | 27/08/2026 |
| **Issue / épica** | Sin issue (cuelga de la revisión de Becas, #77) |
| **Partes afectadas** | Pantalla del caso en revisión · gate de aprobación |
| **Migración** | `programas.0054_identidad_forzada` |

## Pedido original

> «Primero la Validación de identidad: ¿contra qué valida hoy? Y segundo, hoy en día no puedo
> validar: ¿podemos agregar una funcionalidad para que, aunque no valide, poder forzar la
> validación?»

## Alcance acordado

- Poder marcar la identidad como validada **a mano**, con motivo obligatorio y traza, para
  desbloquear la resolución del caso.
- **Afuera:** cambiar la integración con Base de Personas, tocar el gate de SIIS (que es otro
  control y sigue igual) y diagnosticar por qué la fuente no responde en el ambiente del cliente.

## Decisiones tomadas

- **Qué valida hoy, para dejarlo escrito:** la «Validación de identidad» consulta **Base de
  Personas del Chaco («Gran Base»)**, no RENAPER. Es `programas/services/personas.py`
  (`consultar_persona`), con token OAuth *client_credentials* cacheado casi 24 h y una consulta
  `GET /personas/consulta/` por `dni` + `sexo` + `fuente_id`. El RENAPER real vive aparte, en
  `legajos/services/consulta_renaper.py`, y Becas no lo usa. El campo del modelo se llama
  `validado_renaper` por herencia del nombre viejo.
- **Qué hace cuando valida:** sobreescribe nombre, apellido, fecha de nacimiento y sexo del
  ciudadano con lo que devuelve la fuente, marca `validado_renaper=True` y registra cada cambio en
  la traza. Requiere ciudadano vinculado y sexo F o M cargado.
- **Por qué el pedido es urgente y no cosmético:** `motivo_bloqueo_aprobacion` exige identidad
  validada, así que un caso que la fuente no puede validar **no se puede aprobar ni resolver
  nunca**. Los motivos por los que hoy puede fallar son cuatro y cada uno tiene su mensaje:
  configuración incompleta, DNI no encontrado (404 o código 12), persona fallecida, o error
  técnico de la fuente.
- **La validación manual se guarda aparte de la real.** Se agregaron `identidad_forzada` y
  `identidad_forzada_motivo`: `validado_renaper` queda en `True` para desbloquear la aprobación,
  pero el dato nunca se lee como si lo hubiera devuelto la fuente. La pantalla muestra «Validada
  manualmente» sobre badge de advertencia con el motivo debajo, y el bloque de acciones de
  revisión lo repite antes de aprobar.
- **No inventa datos.** A diferencia de «Revalidar», la validación manual **no toca** nombre,
  apellido, fecha de nacimiento ni sexo: quedan los que cargó el territorial o la persona. Por eso
  el sexo **sigue editable** después de forzar (si la validación no vino de la fuente, no hay
  motivo para congelar el dato).
- **Motivo obligatorio de diez caracteres como mínimo**, en un Django Form (`ForzarIdentidadForm`)
  y validado también en el cliente. Es un control que se saltea: sin el motivo escrito no queda
  registro de por qué, y la traza es lo único que después explica la decisión.
- **La capacidad es `becas.programa.administrar`**, la misma que ya gobierna «Revalidar»
  (`CAP_REVALIDAR_RENAPER`). No se creó una capacidad nueva: la que existe ya está restringida al
  administrador de programa, que es el nivel que corresponde para saltear un control.
- **No se puede forzar dos veces** ni sobre un caso ya validado, y se exige ciudadano con DNI
  (el gate de aprobación lo pide igual).

## Implementación

- Modelo: `Formulario.identidad_forzada` y `Formulario.identidad_forzada_motivo`
  (migración `0054_identidad_forzada`).
- `programas/forms.py`: `ForzarIdentidadForm` (motivo, mínimo 10 caracteres).
- `programas/views/revision.py`: `formulario_forzar_identidad` — POST, capacidad, alcance,
  transacción, traza «Validación de identidad → Validada manualmente — {motivo}».
- `programas/urls.py`: `revision/formulario/<pk>/forzar-identidad/`.
- UI en `formulario_detalle.html`: tres estados en la celda de identidad (Validado / Validada
  manualmente / Pendiente), botón «Validar manualmente» junto a «Revalidar», modal con el motivo
  (mismo patrón que el de rechazo), aviso en el bloque de aprobación y el sexo editable tras la
  validación manual.

## Archivos

`programas/models/__init__.py` · `programas/migrations/0054_identidad_forzada.py` ·
`programas/forms.py` · `programas/views/revision.py` · `programas/urls.py` ·
`programas/templates/programas/becas/revision/formulario_detalle.html` ·
`programas/tests/test_becas_revision.py`.

## Base de datos

`programas.0054_identidad_forzada`: agrega `identidad_forzada` (booleano, default `False`) y
`identidad_forzada_motivo` (texto corto, vacío por defecto) a `Formulario`. Sin backfill: los casos
ya validados por la fuente quedan como estaban.

## Validación

- `programas.tests.test_becas_revision.ForzarIdentidadTests`: **8 tests OK** en un venv igual al CI
  (Python 3.12 + Django 5.2.17). Cubren que marca validado y deja traza, que no toca los datos de
  la persona, motivo corto y motivo ausente, sin ciudadano, doble forzado, solo POST, y que después
  de forzar la identidad deja de ser el motivo de bloqueo de la aprobación.
- Suites completas `test_becas_revision` + `test_becas_rbac` + `test_becas_api`: **125 tests OK**.
- `manage.py check` sin observaciones · `makemigrations --check` sin cambios pendientes ·
  `scripts/design_audit.py --changed` **0 errores** (3 WARN de `outline:none` preexistentes) ·
  `scripts/compile_templates.py` 330 plantillas, 0 errores.

## Puesta en marcha en el servidor

Deploy + `migrate`. Sin variables nuevas ni cron.

## Pendientes / a definir

- **Averiguar por qué la fuente no valida en el ambiente del cliente.** El mensaje exacto que
  muestra la pantalla dice cuál de los cuatro casos es; si es «Configuracion de Base de Personas
  incompleta», el arreglo real es que ECOM cargue `PERSONAS_API_URL`, `PERSONAS_API_CLIENT_ID`,
  `PERSONAS_API_CLIENT_SECRET`, `PERSONAS_API_ENTIDAD_UUID` y `PERSONAS_API_FUENTE_ID`. La
  validación manual es la salida de emergencia, no el arreglo.
- **Reporte de identidades validadas a mano.** Hoy el dato está en el caso y en la traza, pero no
  hay una vista que las liste; con volumen conviene tenerla para auditar.
- Definir si el aviso al ciudadano y el legajo tienen que mostrar de algún modo que la identidad no
  fue validada por la fuente.

## Reversión

Revertir el commit y la migración (`migrate programas 0053`). Los casos validados a mano quedan con
`validado_renaper=True` —siguen aprobables— pero se pierde la marca de que fue manual; el motivo y
el autor quedan igual en la traza, que es aditiva.

## Historial

No aplica: entrada nueva.

---

# Cambio 56 — Los selectores se pueden mostrar como buscador con píldoras

🟢 **HECHO — 28/08/2026**

| | |
|---|---|
| **Programa / módulo** | Becas · configuración de requisitos → Portal (inscripción pública) y API de campo |
| **Etiquetas** | `#ui` `#relevamientos` `#datos` |
| **Solicitante** | PM — pedido directo en sesión de trabajo |
| **Fecha del pedido** | 28/08/2026 |
| **Issue / épica** | Sin issue (cuelga de la configuración de Becas, #77) |
| **Partes afectadas** | Modales de requisito en programa/segmento/subsegmento · Requisitos generales · Paso 2 del link público · `definicion_formulario` |
| **Migración** | `programas.0055_presentacion_selector` |

## Pedido original

> «Vamos con un cambio de cómo se ven los campos del *Tipo de campo* de *Nuevo requisito*: cuando
> el campo es alguno de los dos tipo de selector, quiero poder configurar cuándo se ve como
> buscador con selector y el valor seleccionado se ve en píldora, o como se ve actualmente, como
> una lista y se puede seleccionar.»

Y al cerrar el alcance, en la misma sesión: «exacto, en el portal y en la api», «requisitos nativos
y requisitos generales de Becas, o sea en todos los requisitos que se pueden configurar en Becas»,
«sí, también aplica al de una selección».

## Alcance acordado

- Un ajuste nuevo por requisito, **Presentación**, con dos valores: `Lista de opciones` (lo de
  siempre) y `Buscador con píldoras`.
- Se ofrece en **los dos configuradores de Becas**: requisitos nativos (programa, segmento y
  subsegmento) y requisitos generales (preguntas globales).
- Aplica a **los dos tipos de selector**, el de una opción y el múltiple.
- Se ve en el **formulario público del portal** y viaja en la **definición que consume la app de
  campo**.
- **Afuera:** el control de la app móvil —la definición ya le llega, el widget lo implementa el
  equipo móvil en su repo— y los campos de tipos de dispositivo, que comparten `TipoCampo` pero
  son otra superficie y no se pidieron.

## Decisiones tomadas

- **Es presentación, no dato.** No cambia el valor guardado ni qué opciones son válidas: el mismo
  requisito con `LISTA` o con `BUSCADOR` acepta y guarda exactamente lo mismo. Por eso vive en un
  campo propio (`presentacion`) y no toca `opciones` ni `tipo`.
- **El `<select>` nativo no se reemplaza: se envuelve.** El control se monta encima del
  `<select data-buscador>` que sigue en el DOM y sigue siendo el que viaja en el POST. Así la
  validación del servidor (`ChoiceField` / `MultipleChoiceField` contra las opciones configuradas)
  queda intacta y **si el JS no corre, la persona ve el desplegable del navegador y el formulario
  se envía igual**. Es mejora progresiva, no un requisito para completar el trámite.
- **Sin librería de terceros.** El único `select2` del repo es el de Django admin y el backoffice
  no lo usa; el shell del portal público tampoco carga Alpine. El control es JS propio sin
  dependencias (`static/custom/js/nodo-buscador.js`), coherente con el autoalojado del Cambio 46:
  la superficie pública no le pide recursos a nadie.
- **El ajuste es opcional en el formulario.** El campo es `blank=True` y cae a `LISTA` si no viene.
  Sin eso, cualquier alta que no mandara el campo —un modal viejo, un POST programático, los
  propios tests— rompía con «este campo es obligatorio». Se detectó al correr la suite: el alta de
  requisitos dejó de funcionar y volvió a andar con el campo opcional.
- **Un tipo sin opciones normaliza a `LISTA` en silencio.** Guardar `BUSCADOR` sobre un texto o una
  fecha sería un dato que nadie lee; se corrige en el `clean` en vez de rechazar el alta.
- **Default `LISTA` para todo lo existente**, así el alta del campo no cambia el aspecto de ningún
  formulario ya configurado. Pasar algo a buscador es una decisión explícita.
- **El bloque nuevo aparece solo cuando el tipo es selector**, igual que el de *Opciones*: en los
  modales de edición con `x-show` de Alpine y en los de alta con el script de toggle.
- **Comparación tolerante al buscar:** sin acentos y sin mayúsculas, para que «educacion» encuentre
  «Educación».
- **Accesibilidad:** el `<label for>` apunta al `<select>`, que queda oculto, así que el input toma
  su texto como `aria-label`; `role="combobox"` con `aria-expanded`, la lista como `listbox`,
  navegación con flechas, Enter, Escape y Backspace, y ring de foco propio en el botón de quitar.

## Implementación

1. **Modelo** — `PresentacionCampo` (`LISTA` / `BUSCADOR`) y el campo `presentacion` en
   `PreguntaGlobal` y `RequisitoNativo`. Se agregó `TipoCampo.selectores()` para no repetir la
   tupla de los dos tipos con opciones en cuatro lugares.
2. **Configurador** — `_PresentacionMixin` en `programas/forms.py`, aplicado a
   `RequisitoNativoForm` y `PreguntaGlobalForm`: normaliza a `LISTA` si el tipo no es selector o si
   el valor no viene.
3. **Definición compartida** — `_campo_dict` en `programas/services/becas.py` expone
   `presentacion`. Es la misma estructura que sirve al portal y a la API de campo (RN-P12): no se
   creó una definición paralela.
4. **Portal** — `_field_para_campo` elige el widget: con `BUSCADOR`, `Select` / `SelectMultiple`
   con `data-buscador`; con `LISTA`, exactamente lo de antes (`Select` y `CheckboxSelectMultiple`).
5. **El control** — `nodo-buscador.js` y `nodo-buscador.css`, cargados solo en el paso 2 del link
   (nuevo bloque `extra_css` en el shell de inscripción).
6. **UI del backoffice** — el ajuste entra en los modales de alta y edición de los tres detalles
   (programa, segmento, subsegmento), en los dos modales de requisitos generales, y los paneles y
   la tabla pasan el valor actual al modal de edición.
7. **De paso:** el script que muestra u oculta los bloques dependientes del tipo estaba duplicado
   en dos templates y **faltaba en el detalle de programa** —ahí el bloque de *Opciones* se veía
   siempre, incluso en un campo de texto—. Ahora es un include único,
   `config/_tipo_selector_js.html`.

## Archivos

- `programas/models/__init__.py` — `PresentacionCampo`, `TipoCampo.selectores()`, el campo en los
  dos modelos.
- `programas/migrations/0055_presentacion_selector.py`
- `programas/forms.py` — `_PresentacionMixin`, el campo en los dos `Meta.fields`.
- `programas/services/becas.py` — `presentacion` en `_campo_dict`.
- `programas/views/configuracion.py` — `presentacion_choices` en los cinco contextos que pintan
  modales de requisito.
- `portal/forms/inscripcion.py` — `_es_buscador`, `_attrs_buscador` y la elección de widget.
- `static/custom/js/nodo-buscador.js` · `static/custom/css/nodo-buscador.css` — nuevos.
- `portal/templates/portal/inscripcion/base_inscripcion.html` — bloque `extra_css`.
- `portal/templates/portal/inscripcion/paso2.html` — carga del CSS y del JS.
- `programas/templates/programas/becas/config/` — `_tipo_selector_js.html` (nuevo),
  `programa_detail.html`, `segmento_detail.html`, `subsegmento_detail.html`, `pregunta_list.html`,
  `_requisitos_panel.html`, `_requisitos_programa_panel.html`, `_requisitos_propios_panel.html`,
  `_preguntas_table.html`.
- `programas/tests/test_presentacion_selector.py` (nuevo) · `portal/tests/test_inscripcion_envio.py`.

## Base de datos

`programas.0055_presentacion_selector`: agrega `presentacion` (varchar 20, default `LISTA`) a
`programas_preguntaglobal` y `programas_requisitonativo`. Aditiva, sin backfill: el default cubre
todo lo cargado.

## Validación

- `programas/tests/test_presentacion_selector.py` — 14 tests: default `LISTA`, las choices en los
  dos formularios, alta con `BUSCADOR` por pantalla y por formulario, normalización de los tipos
  sin opciones, y `definicion_formulario` exponiendo la presentación de globales y requisitos.
- `portal/tests/test_inscripcion_envio.py` — 10 tests nuevos: widget con y sin el enganche por
  tipo, que `LISTA` mantiene los checkboxes, que una definición sin la clave se lee como lista, que
  el buscador **no cambia qué valores son válidos**, y que el paso 2 carga el CSS y el JS.
- `manage.py check` sin observaciones · `makemigrations --check` sin cambios pendientes ·
  `scripts/compile_templates.py` 332 plantillas, 0 errores · `scripts/design_audit.py --changed`
  **0 errores** (2 WARN de `outline:none`: uno tiene su `box-shadow` de ring en la línea siguiente
  y el otro es el input, cuyo ring lo pinta el contenedor con `:focus-within`).

## Puesta en marcha en el servidor

Deploy + `migrate`. Sin variables nuevas ni cron. El CSS y el JS entran por `collectstatic`.

## Pendientes / a definir

- **El control de la app de campo.** La definición ya le manda `presentacion`; el widget en React
  Native lo tiene que implementar el equipo móvil en `Chaco-mobile`. Hasta entonces la app sigue
  mostrando su lista de siempre y no se rompe nada.
- **Los campos de tipos de dispositivo** comparten `TipoCampo` y quedaron sin el ajuste. Si se
  pide, es agregar el campo al modelo y el mixin a `CampoTipoDispositivoForm`.
- **Cuántas opciones justifican el buscador.** Hoy es una decisión manual por requisito; si se
  quiere, se puede pasar a automático a partir de N opciones.

## Reversión

Revertir el commit y la migración (`migrate programas 0054`). Los requisitos que estaban en
`BUSCADOR` vuelven a verse como lista: es solo presentación, no se pierde ningún dato de los
formularios ya completados.

## Historial

No aplica: entrada nueva.

---

# Cambio 57 — Padrón de la convocatoria como fuente de identidad

🟢 **HECHO — 28/08/2026** · Análisis #325 `Definido` · Desarrollo de #327–#333; pruebas #334 (automatizadas) y #335 (funcionales) en Backlog

| | |
|---|---|
| **Programa / módulo** | Becas · identificación de la persona (link público, app de campo, revisión) |
| **Etiquetas** | `#relevamientos` `#siis` `#datos` `#infra` |
| **Solicitante** | PM — sesión de análisis del 28/08/2026 |
| **Fecha del pedido** | 28/08/2026 |
| **Issue / épica** | #325 (épica #69) |
| **Partes afectadas** | Padrón (modelo y carga) · paso 1 y 2 del link · `consultar_persona_becas` · revisión · diagnóstico de integraciones |
| **Migración** | `programas.0056_padron_convocatoria_identidad` |

## Pedido original

> «Hoy en día en los formularios la validación de la persona le pega a la Gran Base, en base a eso te dice si el registro
> es validado o no, trae datos como nombre, apellido y fecha de nacimiento. Vamos a cambiar porque la Gran Base no está
> funcionando: vamos a agregar esos datos al Excel y vamos a autocompletar los datos de ahí y marcar válido o no. No borremos
> la integración a la Gran Base porque la idea es usarla después.»

## Alcance acordado

- El padrón pasa a ser **uno por convocatoria** (sirve a los dos canales) y trae identidad: `documento, sexo (F/M), nombre,
  apellido, fecha de nacimiento, localidad`.
- **Validado = figura en el Excel con nombre y apellido.** Fecha y localidad no condicionan.
- **Cascada** de identidad en el servidor: padrón → Base de Personas si `PERSONAS_API_ACTIVA` → manual. La Gran Base no se
  borra: se apaga por configuración y, cuando vuelve, **manda sobre el padrón** si difieren.
- Al subir un padrón con datos, los casos **sin validar** de la convocatoria se validan **automáticamente**, con traza.
- Datos precargados **completos** (se descartó enmascarar). Localidad cruzada por nombre contra el catálogo, con reporte de
  las que no coinciden.
- **Afuera:** base de personas local independiente del padrón (alternativa A2), borrar la integración, aplicar «fallecido»
  desde el padrón.

## Decisiones tomadas

- El Excel se consulta **siempre primero**, esté la Gran Base como esté: no es un plan B, es el primer paso. Con la Gran Base
  caída pero prendida, la persona del Excel ya quedó validada y el error solo cuesta la espera del timeout; la variable la
  saca, no cambia el resultado.
- El origen `padron` lo asigna **solo el servidor** tras verificar la fila en la tabla: la app no puede autovalidarse (mismo
  principio que hoy con `personas`/`scan`).
- Los ya validados nunca se desvalidan por un padrón nuevo; el cruce automático solo toca casos pendientes y sin forzar.
- «Revalidar» se deshabilita con la Gran Base apagada; se suma «Validar contra el padrón». El diagnóstico reporta
  «desactivada por configuración» como estado normal.
- RENAPER ≠ Gran Base: Becas usa la Gran Base; el campo se llama `validado_renaper` por herencia. RENAPER caído no afecta a Becas.

## Implementación

- **Padrón a la convocatoria** (#327): `PadronHabilitado.convocatoria` reemplaza a `relevamiento`;
  `Convocatoria.padron_archivo` reemplaza a `Relevamiento.padron_archivo`. El alta/reemplazo vive en la solapa
  Información general de la convocatoria (`convocatoria_padron`, POST, capacidad `becas.convocatoria.editar`,
  acotada a `convocatorias_visibles`), con plantilla descargable (`convocatoria_padron_plantilla`). El alta de
  relevamiento ya no tiene el campo; el detalle del relevamiento informa y linkea. La URL
  `relevamiento_padron` desaparece.
- **Seis columnas** (#328): `parsear_padron` devuelve `(entradas, ResumenPadron)` con dicts por fila; fecha en
  celda de Excel, serial o texto (`dd/mm/aaaa`, `aaaa-mm-dd`, …); una fecha ilegible se reporta y la fila queda sin
  fecha. La localidad se cruza por nombre normalizado (`clave_localidad`) contra `core.Localidad`; si no coincide
  queda `localidad_texto` y la carga la lista. `cargar_padron` acepta Convocatoria o Relevamiento y tuplas
  `(dni, sexo)` o dicts (compatibilidad con los llamadores del Cambio 41).
- **Cascada** (#329): `programas/services/identidad.py::identificar(convocatoria, dni, sexo)` → padrón (fila con
  nombre y apellido = `padron`) → `consultar_persona` solo si `settings.PERSONAS_API_ACTIVA` → `manual`. La Gran
  Base manda si difieren y devuelve `diferencias`; si falla, queda lo del padrón con `error`; `no_encontrado`
  distingue "no está en la fuente" de "la fuente falló". `fallecido` solo viene de la Gran Base.
- **Origen `padron`** (#330): el paso 1 del link usa `identificar`; `crear_formulario_publico` acepta `personas` y
  `padron` como validados y guarda `origen_validacion`. En la API, `_actualizar_validacion_identidad` verifica la
  fila en el servidor (RN-4): sin respaldo el caso queda `manual` y el `origen` del payload se corrige; con respaldo
  toma nombre, apellido, fecha y localidad del padrón. `consultar_persona_becas` mira el padrón de todas las
  convocatorias vigentes del territorial en una consulta (`convocatoria_con_identidad`) y consulta la Gran Base
  una sola vez; contrato de respuesta igual, más `origen`. Una validación manual (`identidad_forzada`) no la
  deshace un sync.
- **Cruce automático** (#331): `validar_casos_pendientes(convocatoria, usuario)` corre dentro de `cargar_padron`:
  solo casos `validado_renaper=False` sin `identidad_forzada`; completa en el ciudadano lo vacío (nombre, apellido,
  fecha, localidad), en los offline completa `datos_identificacion`; traza «Validación de identidad → Validada por
  padrón» por caso; el resumen de la carga informa cuántos.
- **Revisión** (#332): `Formulario.origen_validacion` (`personas` / `padron` / `scan` / `forzada`; vacío = sin
  validar) con backfill en la migración. Badges por fuente en `formulario_detalle.html`; «Validar contra el padrón»
  (`formulario_validar_padron`, misma capacidad que «Revalidar»); «Revalidar» deshabilitado con tooltip cuando la
  Gran Base está apagada y rechazado en el POST; al revalidar, el origen pasa a `personas`; al forzar, a `forzada`.
- **Diagnóstico y variables** (#333): `PERSONAS_API_ACTIVA` (default `True`) en `settings` y `.env.qa.example`;
  `diagnosticar_integraciones` la muestra y, en `False`, reporta la Gran Base como «desactivada por configuración»
  (OK, no falla) y el padrón con su conteo de identidades.

## Archivos

- `programas/models/__init__.py` — `Convocatoria.padron_archivo`, `PadronHabilitado` (convocatoria, identidad,
  `tiene_identidad`), `Formulario.OrigenValidacion` y `origen_validacion`.
- `programas/migrations/0056_padron_convocatoria_identidad.py` — escrita a mano: mueve las filas a la convocatoria,
  deduplica, cambia FK/índice/constraint, backfill de `origen_validacion`.
- `programas/services/padron.py` — reescrito: seis columnas, `ResumenPadron`, `fila_padron`, `datos_de_fila`,
  `convocatoria_con_identidad`, `validar_casos_pendientes`, `plantilla_padron`.
- `programas/services/identidad.py` — nuevo: `identificar`, `gran_base_activa`.
- `programas/services/inscripcion_publica.py`, `programas/services/becas.py` (localidad en
  `resolver_ciudadano_offline`), `portal/views/inscripcion.py`, `portal/templates/portal/inscripcion/paso2.html`.
- `programas/api/views.py` — `_actualizar_validacion_identidad`, `_convocatorias_para_identificar`,
  `consultar_persona_becas`.
- `programas/views/relevamientos.py` (`convocatoria_padron`, `convocatoria_padron_plantilla`, contexto del detalle),
  `programas/views/revision.py` (`formulario_validar_padron`, revalidar/forzar), `programas/urls.py`,
  `programas/forms.py` (sin `padron`).
- Templates: `convocatoria_detail.html` (bloque de padrón), `relevamiento_detail.html`, `relevamiento_form.html`,
  `relevamiento_list.html`, `revision/formulario_detalle.html`.
- `programas/management/commands/diagnosticar_integraciones.py`, `config/settings.py`, `.env.qa.example`.
- Tests: `programas/tests/test_padron.py` (reescrito), `programas/tests/test_padron_identidad.py` (nuevo),
  ajustes en `test_becas_api`, `test_diagnosticar_integraciones` y en los tests del portal (patch target
  `programas.services.identidad.consultar_persona`).

## Base de datos

`programas.0056`: `Convocatoria.padron_archivo`; en `PadronHabilitado` la FK `convocatoria` (con `RunPython` que
copia la convocatoria de cada relevamiento y deduplica por DNI), `nombre`, `apellido`, `fecha_nacimiento`,
`localidad` (FK a `core.Localidad`), `localidad_texto`, constraint `uniq_padron_dni_convocatoria` e índice
`programas_padron_conv_dni_idx`; se eliminan `PadronHabilitado.relevamiento` y `Relevamiento.padron_archivo`;
`Formulario.origen_validacion` con backfill (`forzada` si `identidad_forzada`, `personas` si estaba validado).

## Validación

- `programas/tests/test_padron.py` (reescrito, 27 tests): parser de seis columnas, fechas, localidad, habilitación
  compartida entre relevamientos de la convocatoria, alta/reemplazo desde la convocatoria, permisos, plantilla.
- `programas/tests/test_padron_identidad.py` (nuevo, 30 tests): cascada con y sin Gran Base, precedencia y
  diferencias, error vs no encontrado, fallecido; origen `padron` verificado en el servidor; cruce automático;
  revisión (validar contra padrón, revalidar apagado, orígenes); diagnóstico.
- Suites `test_becas_api`, `test_becas_revision`, `test_diagnosticar_integraciones`, `test_relevamiento_publico` y
  todo `portal`: sin fallos propios (los 12 errores restantes son el bug local `dicts` de Python 3.14 + Django 4.2).
- `manage.py check` sin observaciones · `makemigrations --check` sin cambios · `scripts/compile_templates.py` 331,
  0 errores · `scripts/design_audit.py --changed` 0 errores.

## Puesta en marcha en el servidor

Deploy + `migrate` + `PERSONAS_API_ACTIVA=false` en el ConfigMap de ECOM mientras la Gran Base no responda.

## Pendientes / a definir

- Confirmar con la app de campo si puede mandar el id del relevamiento al consultar identidad; si no, el servidor lo
  resuelve por los relevamientos vigentes del territorial.

## Reversión

Revertir el commit y `migrate programas 0055`. Se pierde el padrón por convocatoria (vuelve a ser por relevamiento,
sin identidad) y `origen_validacion`; `validado_renaper` se conserva, así que ningún caso deja de estar validado.

## Historial

No aplica: entrada nueva. Reabre parcialmente lo dejado fuera en el Cambio 41 («sin form-builder», «RENAPER como única
fuente»): la identidad pasa a tener dos fuentes.

---

# Cambio 58 — Constructor de formularios por convocatoria

🟡 **ANALIZADO — 28/08/2026** · Análisis #326 `Definido` · Mockups entregados · Tasks #336–#356 en Backlog, Iteration 7 (150 h)

| | |
|---|---|
| **Programa / módulo** | Becas · configuración de requisitos → convocatoria → link público y app de campo |
| **Etiquetas** | `#relevamientos` `#ui` `#datos` `#rbac` |
| **Solicitante** | PM — sesión de análisis del 28/08/2026 |
| **Fecha del pedido** | 28/08/2026 |
| **Issue / épica** | #326 (épica #69) · mockups https://claude.ai/code/artifact/84861117-5a64-433d-a2e1-aeaedea723c8 |
| **Partes afectadas** | Catálogo de requisitos · convocatoria (solapa nueva) · `definicion_formulario` · paso 2 del link · caso · revisión · API y app de campo |
| **Migración** | Pendiente: grupos y orígenes en el catálogo; diseño por convocatoria; `respuestas` + foto en el caso, caen columnas fijas |

## Pedido original

> «Me gustaría poder agregar textos como títulos, subtítulos, preguntas que dependen de respuestas de otras preguntas,
> configurar por ejemplo si se pide el Apoderado en base al campo fecha de nacimiento del legajo… el form se quedó corto.»
> Y después: «mantenemos los requisitos globales, de segmento y de subsegmento, pero al configurar la convocatoria hay algo
> que sea Configurar formulario: por un lado el formulario configurado y al lado cómo quedaría publicado; los requisitos
> configurados son campos que se van a arrastrar.» Y sobre los bloques fijos: «que esos bloques sean requisitos generales y
> que estén agrupados; un grupo llamado Datos personales que siempre haga referencia al legajo ciudadano.»

## Alcance acordado

Catálogo (generales · programa · segmento · subsegmento) = campos disponibles, por referencia. Diseño por convocatoria =
orden, grupos, textos y condiciones sobre el catálogo vivo, más campos propios. Bloques fijos → requisitos generales
protegidos vinculados al legajo (Datos personales, Contacto) y a una persona vinculada (Apoderado). Aplica al link
público y a la app de campo; el F-00 de Dispositivos queda afuera.

## Decisiones tomadas

Las catorce de la sesión, tabuladas en #326 (D1–D14): todos los requisitos se ven; campos propios de la convocatoria;
un caso viejo no muestra lo nuevo (foto por caso); referencia, no copia; bloques fijos protegidos y agrupados; drag &
drop real; admin del programa y coordinador del segmento arman el formulario; guardado en vivo; celular y correo
pueden ser opcionales; condición del apoderado configurable (default `edad < 18`); condiciones compuestas «todas /
alguna» sin anidar, único efecto mostrar/ocultar; fecha de nacimiento siempre obligatoria; texto plano y grupos
desplegados; «se pide en» (canal) por campo y grupo.

Reglas derivadas que cierran la consistencia: el catálogo es dueño de texto/tipo/opciones/presentación/obligatorio/
canal y el diseño de orden/grupo/condición/etiqueta; el diseño sigue al catálogo (auto-append, remove); la fuente de
una condición va antes y un drop que lo viole se rechaza con aviso; el servidor re-evalúa y descarta respuestas de
ítems ocultos; la identidad validada nunca se pisa al volcar al legajo; sin correo no se envían avisos; el GPS no es un
campo; la app vieja entra por un adaptador y el servidor arma su foto.

## Implementación

Pendiente. 21 tasks (#336–#356) en seis fases: catálogo → motor → constructor → portal y caso → app de campo → calidad e
integración. 150 h aprobadas por el PM (134 h en tasks + análisis, casos QA y reunión de definición).

## Archivos

Pendiente. Previstos: `programas/models/__init__.py`, `programas/services/diseno.py` y `condiciones.py` (nuevos),
`programas/services/becas.py`, `programas/views/diseno.py` (nuevo), templates de `config/`, `diseno/`, `revision/`,
`convocatoria_detail.html`, `portal/forms/inscripcion.py`, `portal/templates/portal/inscripcion/paso2.html`,
`programas/api/`, `static/vendor/sortablejs/`, `static/custom/js/nodo-condiciones.js`, repo `Chaco-mobile`.

## Base de datos

Pendiente. `GrupoRequisito`; `PreguntaGlobal` (grupo, origen, vinculo, protegido, canal); `RequisitoNativo.canal`;
`DisenoFormulario` + `ItemDiseno`; `Formulario.respuestas` + `definicion`, eliminación de `data`, `celular`,
`email_contacto`, `apoderado_*`. Migración destructiva viable solo sin carga real (confirmado 28/08/2026).

## Validación

Pendiente. Criterios en #326; casos QA por task; plan de pruebas de la épica al cierre.

## Puesta en marcha en el servidor

Por fase, a `test` de ECOM; `main` (producción) una sola vez al cierre, con la migración destructiva coordinada.

## Pendientes / a definir

- La app de campo la implementa el equipo móvil en su repo (#348); hasta entonces sigue con el formulario plano.

## Reversión

Por fase; la última (caso) es la única con migración destructiva.

## Historial

No aplica: entrada nueva. Es la fase 2 explícita de lo que el Cambio 41 dejó fuera («configurador de formularios
propio»). El Cambio 56 (presentación de selectores) queda absorbido como atributo del catálogo.

---

# Cambio 59 — El link público muestra el contacto del programa y «no disponible» distingue si todavía no abrió

🟢 **HECHO — 31/08/2026**

| | |
|---|---|
| **Programa / módulo** | Portal / inscripción pública (el link productivo es del programa Incentivo Juventud) |
| **Etiquetas** | `#textos` `#ui` `#relevamientos` |
| **Solicitante** | PM — pedido directo en sesión de trabajo, sobre el link productivo `/portal/inscripcion/f02de490-…/formulario/` |
| **Fecha del pedido** | 31/08/2026 |
| **Issue / épica** | Sin issue (ajuste de textos pedido en sesión) |
| **Partes afectadas** | Pie del shell de inscripción (todas las pantallas del link) · pantalla «Formulario no disponible» |
| **Migración** | No requiere |

## Pedido original

> «¿Necesitás ayuda? +54 362 430-0002 · datanach@chaco.gob.ar / © 2026 DATAÑACH — Gobierno del Chaco:
> cambiale los datos por consultasincentivojunvetud@gmail.com - Whatsapp 3625153720. Solo en caso de
> problemas técnicos.» Y sobre la pantalla de no disponible: «tenemos la opción A que todavía no está
> abierto y la opción B que está cerrado; quiero que en base a esas opciones se vea un texto o el otro».

## Alcance acordado

- El **pie del shell de inscripción** (visible en las seis pantallas del link) reemplaza teléfono, mail
  institucional y línea de copyright por: casilla de Gmail + WhatsApp 3625153720 + «Solo en caso de
  problemas técnicos.».
- La pantalla **«Formulario no disponible»** gana dos textos: **A** — «todavía no está abierto», con la
  fecha en que comienzan las inscripciones; **B** — «ya no admite inscripciones» (el texto que ya
  existía). La línea de contacto de esa pantalla también pasa a los datos nuevos.
- **Afuera:** el resto de las menciones del teléfono viejo (+54 362 430-0002): el mensaje de rechazo del
  paso 1 (`MENSAJE_RECHAZO`), «ya estás inscripto», «demasiados intentos», el comprobante y su correo,
  «sesión vencida», y el home y el pie del portal ciudadano. Quedan como pendiente a decidir.

## Decisiones tomadas

- **Matiza RN-P4 del Cambio 41** (pantalla única «sin motivo»): solo «todavía no abrió» gana texto
  propio, porque no revela nada sensible y le dice al ciudadano algo accionable (volvé tal fecha).
  Pausado, cupo lleno, vencido y cerrado **siguen compartiendo el genérico**: comunicar cupo o motivo de
  cierre sigue explícitamente fuera, como se decidió en el Cambio 41. `relevamiento_aun_no_abierto()`
  exige público + EN_CURSO + sin pausa + con cupo + `fecha_asignada` en el futuro; cualquier otra
  combinación cae al texto B.
- **El WhatsApp va como texto plano, sin deep-link `wa.me`**: `SinRecursosDeTercerosTests` prohíbe
  cualquier `href` `http(s)://` en plantillas servidas y no vale la pena agujerear esa red por un link de
  cortesía. El email sí es `mailto:` (no es http y pasa).
- **El contacto queda hardcodeado en el shell**, compartido por todos los links públicos. Hoy el único
  link vivo es el de Incentivo Juventud; si otro programa publica un link y necesita contacto propio, el
  paso siguiente es un campo por relevamiento (evolutivo, no pedido).
- **El email se transcribió tal cual lo pasó el cliente**, con «junvetud» (sic). Ver Pendientes.

## Implementación

- `portal/services/inscripcion.py` — `relevamiento_aun_no_abierto()`, al lado de
  `relevamiento_disponible()` que ya concentraba la disponibilidad (RN-P4).
- `portal/views/inscripcion.py` — `_no_disponible()` pasa `aun_no_abierto` al template.
- `portal/templates/portal/inscripcion/no_disponible.html` — las dos variantes; la A muestra
  `fecha_asignada` como `d/m/Y`.
- `portal/templates/portal/inscripcion/base_inscripcion.html` — el pie nuevo.

## Archivos

`portal/services/inscripcion.py` · `portal/views/inscripcion.py` ·
`portal/templates/portal/inscripcion/no_disponible.html` ·
`portal/templates/portal/inscripcion/base_inscripcion.html` · tests: `portal/tests/test_inscripcion.py`.

## Base de datos

No requiere.

## Validación

- Tests nuevos: el vencido muestra el texto B y no el A; un link con `fecha_asignada` futura muestra el A
  y no el B; un link pausado con fecha futura **no** califica como «aún no abierto» (RN-P4). Suite
  `portal.tests.test_inscripcion` 18/18 en verde (SQLite en memoria).
- `SinRecursosDeTercerosTests` en verde (el pie nuevo no introduce URLs externas).
- `manage.py check` OK · `design_audit.py --changed` 0 errores / 0 warnings · `compile_templates.py`
  331 plantillas, 0 errores.

## Puesta en marcha en el servidor

Deploy estándar sin migración. El servidor está sobre la rama `feature/constructor-formularios`.

## Pendientes / a definir

- Decidir si el teléfono +54 362 430-0002 que sigue en el resto de las superficies (mensaje de rechazo
  del paso 1, «ya estás inscripto», «demasiados intentos», comprobante y correo de confirmación, «sesión
  vencida», home y pie del portal) también se reemplaza, y por qué dato (es contacto del organismo, no
  del programa).

## Reversión

Revertir el commit; no hay migraciones ni datos involucrados.

## Historial

No aplica: entrada nueva. Matiza una decisión del Cambio 41 («Formulario no disponible» única para
vencido/pausado/cupo/cerrado, sin motivo): el caso «todavía no abrió» se separa por pedido del PM; el
resto sigue sin revelar motivo.

**31/08/2026 — El PM confirmó la casilla:** `consultasincentivojunvetud@gmail.com` es correcta tal
cual, no es un typo de «juventud».

**03/09/2026 — El pie ya no se ve en las seis pantallas:** el Cambio 60 lo saca del **paso 1**
(la pantalla que se abre con solo tener el link) y lo deja del paso 2 en adelante. El resto de lo
acordado acá sigue igual.

---

# Cambio 60 — El contacto del programa sale del paso 1 del link público

🟢 **HECHO — 03/09/2026**

| | |
|---|---|
| **Programa / módulo** | Portal / inscripción pública (link productivo de Incentivo Juventud) |
| **Etiquetas** | `#textos` `#ui` `#relevamientos` |
| **Solicitante** | PM — pedido directo en sesión de trabajo, sobre el link productivo `/portal/inscripcion/f02de490-…/` |
| **Fecha del pedido** | 03/09/2026 |
| **Issue / épica** | Sin issue (ajuste de textos pedido en sesión) |
| **Partes afectadas** | Pie del shell de inscripción · paso 1 del formulario público |
| **Migración** | No requiere |

## Pedido original

> «En la página 1 tenemos consultasincentivojunvetud@gmail.com · WhatsApp 3625153720. Eliminá esos
> datos; en la página 2 dejalos.»

## Alcance acordado

- El **paso 1** (identificación: DNI, sexo y captcha) deja de mostrar el pie con la casilla y el
  WhatsApp del programa. No queda un pie recortado: la franja entera desaparece de esa pantalla.
- El **paso 2** (formulario) lo sigue mostrando tal cual quedó en el Cambio 59.
- **Afuera:** las otras cuatro pantallas del link —confirmación, «formulario no disponible», «ya estás
  inscripto» y «demasiados intentos»— conservan el pie; el PM habló de la página 1 y la página 2, y no
  hay motivo para tocar el resto. La línea de contacto que el Cambio 59 puso **dentro** del cuerpo de
  «formulario no disponible» tampoco se toca.

## Decisiones tomadas

- **Se saca el pie completo, no solo el mail y el teléfono.** La segunda línea («Solo en caso de
  problemas técnicos.») es la aclaración de ese contacto: sola no dice nada. El pie del paso 1 tampoco
  vuelve a la línea de copyright que había antes del Cambio 59, porque eso sería reponer un texto que
  el PM ya había mandado sacar.
- **Se resuelve con un bloque de plantilla (`{% block pie %}`), no con un `if` sobre el paso.** El
  shell no sabe en qué paso está —cada pantalla es su propia plantilla—, y un condicional obligaría a
  inventar una variable de contexto en todas las vistas. Con el bloque, la pantalla que quiera ocultar
  el pie lo declara vacío en una línea y las demás no cambian.
- **El contacto sigue hardcodeado en el shell.** Vale lo decidido en el Cambio 59: si otro programa
  publica un link y necesita contacto propio, recién ahí se justifica un campo por relevamiento.
- **Queda un hueco de ~136 px al pie del panel de marca en escritorio.** Ese padding está para que el
  pie fijo no tape el stepper; sin pie es aire de más sobre el degradado, que no molesta. Se prefirió
  eso a duplicar el CSS del panel para el único caso del paso 1.

## Implementación

Al abrir el link público, la primera pantalla (identificación) ya no muestra ninguna franja de
contacto. Al pasar al formulario, el pie con la casilla y el WhatsApp aparece como hasta ahora, igual
que en el comprobante y en las pantallas de aviso.

## Archivos

`portal/templates/portal/inscripcion/base_inscripcion.html` (el pie pasa a `{% block pie %}`) ·
`portal/templates/portal/inscripcion/paso1.html` (lo declara vacío) · tests:
`portal/tests/test_inscripcion.py` (`PieDeContactoTests`).

## Base de datos

No requiere.

## Validación

- Tests nuevos (`PieDeContactoTests`): el paso 1 no contiene ni la casilla ni el número; el paso 2 sí.
  Suite `portal.tests.test_inscripcion` 20/20 en verde (SQLite en memoria). **Ojo:** en el venv local
  (Python 3.14 + Django 4.2) los dos casos caen en `_tolerar_render_local` —el bug conocido de
  `Context.__copy__`— y no llegan a afirmar nada; las afirmaciones corren de verdad en CI.
- Verificación local equivalente sin test client: se renderizaron las seis plantillas del link con
  `render_to_string`. Solo `paso1.html` sale sin `<footer>` y sin los dos datos; paso 2, confirmación,
  no disponible, ya inscripto y demasiados intentos los conservan.
- `manage.py check` OK · `compile_templates.py` 331 plantillas, 0 errores ·
  `design_audit.py --changed` 0 errores / 0 warnings.

## Puesta en marcha en el servidor

Deploy estándar sin migración. El servidor está sobre la rama `feature/constructor-formularios`.

## Pendientes / a definir

- Sigue abierto lo del Cambio 59: qué se hace con el teléfono +54 362 430-0002 que todavía aparece en
  el mensaje de rechazo del paso 1, «ya estás inscripto», «demasiados intentos», el comprobante y su
  correo, «sesión vencida», y el home y el pie del portal ciudadano.

## Reversión

Revertir el commit: el `{% block pie %}` vuelve a ser un `<footer>` fijo y el paso 1 lo muestra de
nuevo. No hay migraciones ni datos involucrados.

## Historial

No aplica: entrada nueva. Acota el alcance del Cambio 59 —que había puesto el pie en las seis
pantallas del link—; esa entrada queda con su nota de historial fechada.

**03/09/2026 — Media vuelta atrás, el mismo día:** el PM pidió que el pie **vuelva** al paso 1, pero
solo con la casilla. Lo que sigue en pie de esta entrada es que el **WhatsApp** no se muestra ahí; la
decisión de sacar la franja entera quedó sin efecto. Ver Cambio 62.

---

# Cambio 61 — El mensaje de rechazo del paso 1 deja de mostrar el teléfono del organismo

🟢 **HECHO — 03/09/2026**

| | |
|---|---|
| **Programa / módulo** | Portal / inscripción pública (link productivo de Incentivo Juventud) |
| **Etiquetas** | `#textos` `#ui` `#relevamientos` |
| **Solicitante** | PM — en la misma sesión del Cambio 60, con una captura de la alerta roja del paso 1 |
| **Fecha del pedido** | 03/09/2026 |
| **Issue / épica** | Sin issue (ajuste de textos pedido en sesión) |
| **Partes afectadas** | `MENSAJE_RECHAZO` del paso 1 del formulario público |
| **Migración** | No requiere |

## Pedido original

> «También borrá ese mensaje» — con una captura de la alerta roja del paso 1: «No podés inscribirte
> con ese documento. Si creés que es un error, comunicate con el programa al +54 362 430-0002.»

## Alcance acordado

- La alerta de rechazo del paso 1 pierde la segunda oración completa. Queda: **«No podés inscribirte
  con ese documento.»**
- **Afuera:** el mismo teléfono sigue en «ya estás inscripto», «demasiados intentos», el comprobante y
  su correo, «sesión vencida», y el home y el pie del portal ciudadano. El pedido fue sobre esta
  alerta; el resto sigue en el pendiente que abrió el Cambio 59.

## Decisiones tomadas

- **Se saca la oración de contacto, no la alerta entera.** «Borrá ese mensaje» se leyó sobre el dato de
  contacto —es el tema de toda la sesión (Cambios 59 y 60)— y no sobre el aviso: `MENSAJE_RECHAZO` es
  lo único que le dice al ciudadano que ese documento no pasa. Sin él, los cuatro caminos de rechazo
  del paso 1 dejarían el formulario en rojo sin texto, y la persona reintentaría sin saber por qué.
  **Queda pendiente de confirmación del PM** (ver Pendientes).
- **No se reemplaza por el contacto nuevo del programa** (la casilla y el WhatsApp del Cambio 59):
  sería contradecir el Cambio 60, que acaba de sacar ese contacto justamente del paso 1.
- **Sigue siendo un único mensaje para los cuatro rechazos** —fuera del padrón, ya inscripto,
  fallecido y padrón cambiado entre pasos—. Es la decisión de la revisión de seguridad del 26/08/2026:
  textos distintos convertían el formulario en un oráculo para reconstruir el padrón. Acortar el texto
  no toca esa propiedad, y `RechazosIndistinguiblesTests` la sigue cubriendo.

## Implementación

Cuando el paso 1 rechaza un documento, la alerta roja dice solo «No podés inscribirte con ese
documento.», sin teléfono ni invitación a comunicarse.

## Archivos

`portal/views/inscripcion.py` (constante `MENSAJE_RECHAZO`). Los tests que la verifican
—`portal/tests/test_seguridad_publica.py`, `portal/tests/test_correcciones_review_2.py`— importan la
constante, así que no hubo que tocarlos.

## Base de datos

No requiere.

## Validación

- `portal.tests.test_seguridad_publica` + `test_correcciones_review_2` + `test_inscripcion`: 69 tests,
  11 errores, **exactamente los mismos 11 con y sin el cambio** (baseline conocido del venv local:
  Python 3.14 + Django 4.2, `Context.__copy__`). Se corrió el baseline a propósito para compararlo.
- `manage.py check` OK. No tocó plantillas: no aplica `design_audit` ni `compile_templates`.

## Puesta en marcha en el servidor

Deploy estándar sin migración. El servidor está sobre la rama `feature/constructor-formularios`.

## Pendientes / a definir

- **Confirmar con el PM** si además hay que sacar la primera oración, es decir, dejar el rechazo sin
  ningún mensaje visible. Se preguntó al entregar el cambio; hasta la respuesta queda la oración corta.
- Sigue abierto el pendiente del Cambio 59 sobre las otras seis superficies donde aparece el
  +54 362 430-0002.

## Reversión

Revertir el commit: la constante vuelve a su texto largo con el teléfono.

## Historial

No aplica: entrada nueva. Cierra una parte del pendiente que dejó abierto el Cambio 59 (el teléfono
viejo en el mensaje de rechazo del paso 1) y acompaña al Cambio 60, del mismo pedido en sesión.

---

# Cambio 62 — El paso 1 vuelve a mostrar el pie, pero solo con la casilla

🟢 **HECHO — 03/09/2026**

| | |
|---|---|
| **Programa / módulo** | Portal / inscripción pública (link productivo de Incentivo Juventud) |
| **Etiquetas** | `#textos` `#ui` `#relevamientos` |
| **Solicitante** | PM — en la misma sesión, después de ver desplegado el Cambio 60 |
| **Fecha del pedido** | 03/09/2026 |
| **Issue / épica** | Sin issue (ajuste de textos pedido en sesión) |
| **Partes afectadas** | Pie del shell de inscripción · paso 1 del formulario público |
| **Migración** | No requiere |

## Pedido original

> «Volvé a agregar en la primera página el mensaje donde estaba el correo y el número, pero solo
> agregá el correo consultasincentivojunvetud@gmail.com.»

## Alcance acordado

- El **paso 1** vuelve a mostrar el pie completo —la casilla y la línea «Solo en caso de problemas
  técnicos.»— **sin el WhatsApp**.
- El **paso 2** y las otras cuatro pantallas del link siguen con la casilla **y** el WhatsApp, como
  quedó en el Cambio 59.
- **Afuera:** todo lo demás. En particular no se toca el mensaje de rechazo del Cambio 61, que sigue
  sin contacto.

## Decisiones tomadas

- **Se revierte el mecanismo del Cambio 60, no se le agrega otra capa.** Aquel bloque `pie` —que el
  paso 1 vaciaba entero— desaparece; en su lugar el pie es fijo otra vez y lo único opcional es el
  WhatsApp, en un bloque `pie_whatsapp` que el paso 1 declara vacío. Así el mail no queda escrito en
  dos plantillas: una sola línea del shell lo define para las seis pantallas.
- **La línea «Solo en caso de problemas técnicos.» vuelve también al paso 1.** Es la aclaración de la
  casilla; separarlas dejaría un contacto sin contexto, que es lo contrario de lo que pidió el Cambio 59.
- **Queda una diferencia real entre el paso 1 y el resto:** solo esa pantalla oculta el WhatsApp. No es
  un efecto colateral del mecanismo, es lo pedido; el test lo fija en las dos direcciones.

## Implementación

El pie del link vuelve a verse en las seis pantallas. En el paso 1 dice solo la casilla; del paso 2 en
adelante, casilla y WhatsApp.

## Archivos

`portal/templates/portal/inscripcion/base_inscripcion.html` (el pie vuelve a ser fijo; el WhatsApp
pasa a `{% block pie_whatsapp %}`) · `portal/templates/portal/inscripcion/paso1.html` (lo vacía) ·
tests: `portal/tests/test_inscripcion.py` (`PieDeContactoTests`).

## Base de datos

No requiere.

## Validación

- `PieDeContactoTests` actualizado: el paso 1 **contiene** la casilla y **no** el número; el paso 2
  tiene los dos. Suite `portal.tests.test_inscripcion` 20/20 en verde. Vale la misma advertencia del
  Cambio 60: en el venv local esos dos casos caen en `_tolerar_render_local` y afirman de verdad en CI.
- Verificación local equivalente con `render_to_string` sobre las seis plantillas: `paso1` sale con
  `<footer>` y con la casilla, sin el número; las otras cinco, con los dos datos.
- `manage.py check` OK · `compile_templates.py` 331 plantillas, 0 errores ·
  `design_audit.py --changed` 0 errores / 0 warnings.

## Puesta en marcha en el servidor

Deploy estándar sin migración.

## Pendientes / a definir

- Sigue abierto el pendiente del Cambio 59 sobre el +54 362 430-0002 en las otras superficies, y el del
  Cambio 61 sobre si el mensaje de rechazo del paso 1 tiene que desaparecer del todo.

## Reversión

Revertir el commit: el paso 1 vuelve a quedarse sin pie, como lo dejó el Cambio 60.

## Historial

No aplica: entrada nueva. Deja sin efecto la mitad del Cambio 60 —sacar el pie entero del paso 1— y
conserva la otra mitad: el WhatsApp sigue sin mostrarse ahí. El Cambio 60 queda con su nota fechada.

---

# Cambio 63 — El login tarda por el hash de la contraseña y el HTTP corre en un solo proceso

🟡 **PARCIAL — código listo el 03/09/2026 en la rama `perf/login-argon2-gunicorn`; falta desplegar en `icore-srv` y que ECOM decida si activa el modo gunicorn**

| | |
|---|---|
| **Programa / módulo** | Transversal — login e infraestructura de ejecución |
| **Etiquetas** | `#sesion` `#infra` |
| **Solicitante** | PM — en sesión: «quiero que analices la perfo del sistema, si se puede mejorar; noto que la carga de algunas pantallas tardan más de lo común, ejemplo el login», y después «vamos con tema desarrollo y armá una rama para este cambio» |
| **Fecha del pedido** | 03/09/2026 |
| **Issue / épica** | Sin issue. Antecedente: épica de performance #222 (relevamientos #219, #262, #264) |
| **Partes afectadas** | Backoffice (login) · Infra/ECOM (runtime HTTP de la imagen, compose de `icore-srv`) |
| **Migración** | No requiere |

## Pedido original

> «Quiero que analices la perfo del sistema, si se puede mejorar. Noto que la carga de algunas pantallas
> tardan más de lo común, ejemplo el login.» → punteo de mejoras de código → «Bien, vamos con tema
> desarrollo y armá una rama para este cambio.»

## Alcance acordado

Entra lo que el análisis ([analisis-performance-login-2026-09.md](analisis-performance-login-2026-09.md))
ubicó como las dos causas de mayor impacto y menor riesgo:

1. **El hash de la contraseña** (H-1): Argon2 en lugar del PBKDF2 por defecto.
2. **Un solo proceso Python para todo el HTTP** (H-2): la imagen gana el modo `APP_RUNTIME=gunicorn`
   y el compose de `icore-srv` lo adopta para el contenedor `web`.

**Queda afuera** (punteo entregado al PM, cada punto con su entrada cuando se haga): nginx con
`gzip_static` y HTTP/2 en `icore-srv` (H-4), timeouts más cortos hacia RENAPER/Personas/SIIS (H-6),
caché del contador de alertas del navbar (H-9), concatenación de las hojas de estilo (H-5), presupuesto
de CI para el POST de login, rotación real del log diario (H-8), middlewares async-capable (H-3, solo si
se sigue con Daphne para HTTP) y la fijación de sesión única en menos consultas (H-10).

## Decisiones tomadas

- **Argon2id primero; PBKDF2 se conserva detrás.** Medido en la máquina de desarrollo: verificar una
  contraseña con el PBKDF2 de Django 5.2 (1.000.000 de iteraciones, el que corre producción) cuesta
  **952 ms** de CPU; Argon2id con los parámetros por defecto de Django, **89 ms**. Ese segundo se paga
  con el GIL tomado, así que un login frenaba a los demás usuarios. PBKDF2 queda en la lista para leer
  los hashes ya guardados: Django los **re-hashea a Argon2 en el siguiente login exitoso**, sin
  migración ni reseteo de claves. **No se bajan las iteraciones de PBKDF2** como atajo: sería perder
  seguridad para ganar lo que Argon2 da sin perderla.
- **gunicorn con hilos (`gthread`), no gevent.** El código usa `mysqlclient` y `requests` bloqueantes;
  gevent exigiría monkey-patching y el parche de `config/gevent_patch.py` queda inactivo (solo se activa
  con `GUNICORN_WORKER_CLASS=gevent`). La documentación pública en `docs/client/architecture.md` decía
  `gunicorn -k gevent` para un modo que **el entrypoint nunca había implementado**: se corrige para que
  describa lo que la imagen hace.
- **Con gunicorn, `WEBSOCKETS_ENABLED` no se deduce: se declara.** Gunicorn no sirve websockets; deducir
  `True` mentiría en un despliegue sin Daphne y el navegador intentaría conectar a un `/ws/` que no
  existe. El entrypoint avisa al arrancar si la variable falta. En `icore-srv` se declara `True` porque
  el contenedor `websocket` (Daphne) sigue atendiendo `/ws/` y nginx ya lo enruta ahí.
- **Defaults 3 workers × 2 hilos, timeout 120 s, `max-requests` 1000 con jitter.** Tres procesos usan los
  4 vCPU de la VM dejando aire a MySQL y Redis. El timeout de 120 s es solo el techo a partir del cual
  gunicorn mataría un worker colgado: **el límite efectivo para el cliente lo pone nginx**, que corta a
  los 60 s (`proxy_read_timeout`), y la cadena RENAPER (10 s conexión + 20 s lectura) entra dentro de ese
  margen; con `gthread` una request larga tampoco mata al worker, porque el latido al maestro lo da el
  hilo principal, no el que atiende la request. El reciclado por cantidad de requests mantiene la memoria
  acotada bajo el límite del contenedor. Todo ajustable por variables `GUNICORN_*`.
- **`web` de `icore-srv` pasa a gunicorn en el compose del repo, con 900 MB sin swap.** El límite anterior
  (350 MB con 150 MB de swap permitido) hacía errática la latencia si el proceso paginaba; con tres
  workers de 150–200 MB hace falta subirlo. `websocket` sigue igual (Daphne, 300 MB).
- **Daphne sigue siendo el default de la imagen.** ECOM corre un solo Deployment con Daphne para HTTP y
  `/ws/` (Cambio 31, historial del 13/08/2026); si no cambia nada, su despliegue arranca exactamente
  igual. El modo gunicorn en Kubernetes exige dos Deployments (web con gunicorn, ws con Daphne), ingress
  enrutando `/ws/` y `WEBSOCKETS_ENABLED=True` en el web. Quedó documentado en `docker/k8s/README.md`,
  sección *HTTP en varios procesos*, junto con la alternativa sin cambios (más réplicas).
- **En ECOM se arranca subiendo réplicas, no con gunicorn; en `icore-srv`, gunicorn.** La forma de
  repartir la carga es **decisión nuestra, no de la plataforma**: DevOps aplica la configuración y aporta
  los datos del ambiente. En Kubernetes, más réplicas es un número en el manifiesto —no toca el ingress
  ni el enrutamiento del chat— y ya da un núcleo por réplica; gunicorn queda como segundo paso si las
  métricas lo piden. En `icore-srv` se elige gunicorn porque nginx **ya** separa `/ws/` hacia el
  contenedor `websocket` y no hay nada nuevo que enrutar. El pedido de datos a DevOps de ECOM, con el
  motivo de cada uno, está en
  [pedido-datos-prd-ecom-2026-09.md](pedido-datos-prd-ecom-2026-09.md).

## Implementación

- Las contraseñas nuevas y las que se cambian se guardan con Argon2id; las existentes siguen
  funcionando y se actualizan solas la primera vez que el usuario entra.
- La imagen acepta `APP_RUNTIME=gunicorn`: levanta `gunicorn config.wsgi:application` con
  `GUNICORN_WORKERS` × `GUNICORN_THREADS` (3 × 2), `GUNICORN_TIMEOUT` (120) y `GUNICORN_MAX_REQUESTS`
  (1000), después del mismo bootstrap de siempre. `runserver` y `daphne` no cambian.
- En `icore-srv`, `web` arranca con gunicorn y `WEBSOCKETS_ENABLED=True`; `websocket` y `nginx` siguen
  igual.
- Documentación alineada: `.env.qa.example`, `docker/k8s/README.md`, `docs/internal/processes.md`,
  `docs/client/architecture.md` (tabla de runtime y bloque de recursos) y la guía de la versión 001.

## Archivos

- `requirements.txt` (`argon2-cffi==25.1.0`)
- `config/settings.py` (`PASSWORD_HASHERS`)
- `users/tests/test_password_hashers.py` (nuevo)
- `docker-entrypoint.sh`
- `docker-compose.prod.yml`
- `.env.qa.example`
- `docker/k8s/README.md`
- `docs/internal/processes.md`
- `docs/client/architecture.md`
- `docs/client/versiones/version-001.md`
- `docs/internal/analisis-performance-login-2026-09.md` (el análisis de origen, nuevo)

## Base de datos

No requiere migración. La columna `auth_user.password` ya admite el formato de Argon2; el contenido se
actualiza fila a fila cuando cada usuario inicia sesión.

## Validación

- `manage.py check`: sin observaciones.
- `users.tests.test_password_hashers` (nuevo): **3/3 OK** — las contraseñas nuevas salen en Argon2, un
  hash PBKDF2 existente sigue autenticando y el POST de login lo migra a Argon2.
- `test_usuarios_abm` + `test_credenciales` + `test_password_reset` + `test_logout`: 57 tests, **10
  errores idénticos con y sin el cambio** (lista comparada con `diff`; baseline conocido del venv local:
  Python 3.14 + Django 4.2, `'super' object has no attribute 'dicts'`). La corrida pasó de 27,9 s a 8,0 s:
  los usuarios de prueba también se crean con Argon2.
- Medición del hash en la máquina de desarrollo (mediana de 5): PBKDF2 600k (venv, Django 4.2) 332 ms ·
  PBKDF2 1.000k (Django 5.2, producción) 952 ms · Argon2id 89 ms.
- `sh -n docker-entrypoint.sh` OK; `docker-compose.prod.yml` parseado y verificadas las variables nuevas;
  `ruff check` y `ruff format --check` OK; `mkdocs build --strict` OK.
- `pip-audit` sobre `argon2-cffi==25.1.0` y `argon2-cffi-bindings==26.1.0` (el gate de `pr-security.yml`):
  sin vulnerabilidades conocidas. `bandit` excluye `tests/`, así que las contraseñas literales del test
  nuevo no lo disparan.
- Revisión de `chaco-dev-reviewer` sobre el commit: **sin hallazgos bloqueantes ni importantes**, «listo
  para QA». Verificó con evidencia que nada del multiproceso se rompe: `CHANNEL_LAYERS`, caché, sesiones
  y throttle van por Redis en `prd`; la sesión única vive en la base; los hilos de `core/performance/*`
  solo arrancan por comando; `channels_redis` limpia su capa al cerrarse cada event loop de
  `async_to_sync`, así que bajo WSGI no acumula conexiones. Dos observaciones bajas sobre `nginx.conf`,
  preexistentes y fuera del diff, quedaron en Pendientes.
- No tocó plantillas ni estilos: no aplica `design_audit` ni `compile_templates`.
- **No se midió producción**: el acceso a `icore-srv` desde la sesión fue bloqueado por el clasificador
  de permisos. La confirmación queda para después del deploy (ver abajo).

## Puesta en marcha en el servidor

**`icore-srv`:** cambia `requirements.txt`, así que es rebuild: `git pull` de la rama → `docker compose -f
docker-compose.prod.yml up -d --build web websocket` → esperar `web` healthy → `docker restart
chaco-nginx-1`. No hace falta tocar `.env.production`: las variables nuevas van en el `environment:` del
compose. Verificar: en el log de `web` la línea `Iniciando gunicorn (3 workers x 2 hilos)`, `/health/`
200, que el chat en vivo siga conectando (indicador de WebSocket en el navbar), `docker stats` con `web`
por debajo de 900 MB, y en `logs/<fecha>/info.log` el `duration=` del `POST /` de un login real (antes
del cambio debería rondar el segundo; después, decenas de milisegundos más la ida a la base).

**ECOM:** nada obligatorio; el próximo espejo trae Argon2 y la imagen sigue arrancando con Daphne. Si
quieren repartir el HTTP, la receta está en `docker/k8s/README.md`.

## Pendientes / a definir

- Desplegar en `icore-srv` y confirmar con datos reales (`warning.log` de requests > 3 s antes/después,
  `docker stats`). Recién ahí la entrada pasa a 🟢.
- **Respuesta de DevOps de ECOM al pedido de datos del 03/09/2026**
  ([pedido-datos-prd-ecom-2026-09.md](pedido-datos-prd-ecom-2026-09.md)): réplicas y `resources`, nodo,
  runtime, ingress, Redis, motor de base y métricas. Con eso se les pasa la configuración concreta
  (réplicas y recursos) y se contrasta la línea de base contra la medición posterior al despliegue.
- Revisar el `maxmemory` de Redis **también en `icore-srv`**: hoy son 350 MB con `allkeys-lru`, y ahí
  viven las sesiones; si se llena, expulsa sesiones y desloguea usuarios sin causa aparente.
- El resto del punteo (ver *Alcance acordado*), cada uno con su propia entrada. El primero en la cola
  por relación ganancia/esfuerzo es nginx con `gzip_static` y HTTP/2 en `icore-srv`. En esa misma pasada
  sobre `nginx.conf`, dos observaciones de la revisión (preexistentes, no las introduce este cambio): el
  `keepalive 32` del upstream `web` no se aprovecha porque `proxy_set_header Connection
  $connection_upgrade` manda `close` en todo el HTTP normal (cada request abre una conexión nueva hacia
  gunicorn), y los timeouts de nginx (60 s) y gunicorn (120 s) conviene dejarlos alineados a propósito.

## Reversión

1. `APP_RUNTIME=daphne` en el `web` del compose (o revertir el commit): vuelve al proceso único. El
   `mem_limit` puede volver a 350m, aunque conviene dejarlo en 900m.
2. **Ojo con Argon2:** una vez desplegado, los usuarios que se hayan logueado tienen su hash en Argon2.
   Si se quita `argon2-cffi` o se saca `Argon2PasswordHasher` de `PASSWORD_HASHERS`, esos usuarios **no
   pueden entrar** hasta resetear la clave. Para volver a PBKDF2 como hasher principal, basta con poner
   PBKDF2 primero **dejando Argon2 en la lista**; Django re-hashea de vuelta en el siguiente login. No
   hay datos que se pierdan.

## Historial

No aplica: entrada nueva. Se apoya en el entrypoint del **Cambio 31** (modos `runserver`/`daphne` y
`bootstrap`) y en los relevamientos de la épica #222, cuyo dato de concurrencia (×3,6 con 8 clientes)
es lo que este cambio ataca.

**03/09/2026 — renumerada de 62 a 63.** Nació como «Cambio 62» en la rama
`perf/login-argon2-gunicorn` y así la nombran sus tres commits (`c1a9cbc`, `8a3129a`, `dc0f14f`). Al
traer `development` apareció otro Cambio 62 ya registrado en el tronco —el pie del paso 1 del link
público—, así que esta entrada tomó el número siguiente, que es el que vale. El texto no cambió.

**04/09/2026 — DevOps de ECOM respondió, y aparece una causa que no estaba en el análisis: el pod
tiene `limits.cpu: 500m`.** Medio núcleo por réplica, con `requests` de apenas `100m`, sobre nodos de
32 CPU. A ese techo, los ~950 ms de CPU que cuesta hoy verificar una contraseña se convierten en
**~1,9 s de reloj** por el frenado del planificador (50 ms de cada 100 ms), y con Daphne en proceso
único la capacidad total del sistema es **1 núcleo** (2 réplicas × 0,5). Es decir que en producción el
H-1 y el H-2 del análisis se potencian con un límite que nosotros no veíamos.

**Consecuencia para el plan: en ECOM el primer movimiento es subir `limits.cpu`, no las réplicas.**
Corrige el síntoma en cada request y no cuesta capacidad —los `limits` no reservan nada—, mientras que
sumar réplicas multiplica medios núcleos. La decisión anterior (réplicas antes que gunicorn) no cambia
para lo que venga después. Se detectaron además dos riesgos de configuración que no son de este cambio
pero sí de este ambiente: `limits.ephemeral-storage: 100Mi` con los logs escribiendo a la capa del
contenedor (riesgo de desalojo del pod, emparentado con el H-8) y Redis con `noeviction` sin `maxmemory`
confirmado (si no está fijado, el contenedor muere por memoria y caen todas las sesiones). El detalle,
los datos crudos y la configuración propuesta están en
[pedido-datos-prd-ecom-2026-09.md](pedido-datos-prd-ecom-2026-09.md).

---

# Cambio 64 — Solapa «Dashboard» en el programa Becas: métricas, filtros y exportación

🟡 **MERGEADO EN DEVELOPMENT — 05/09/2026** · Análisis #366 `Definido` · Tasks #367–#375 en Backlog, Iteration 7 (70 h) · Fases 1 a 6 mergeadas por el PR #376 (squash c59d995) con 27 tests en verde; faltan QA funcional (#374) y despliegue a test/producción de ECOM (#375) · Propuesta de 86 h a validación del Ministerio (Versión 002)

| | |
|---|---|
| **Programa / módulo** | Becas · configuración → detalle del programa (`/becas/config/programas/<pk>/`) |
| **Etiquetas** | `#ui` `#convocatorias` `#relevamientos` `#datos` |
| **Solicitante** | PM — en sesión: «vamos a armar un dashboard en el programa Becas… al lado de Requisitos del programa quiero agregar una solapa de dashboard, tiene que ser a nivel visual y poder exportar; vamos a analizar cuántas horas consume y armemos un mock up; la idea es que tenga métricas generales, puedan filtrar sus convocatorias, relevamientos y data de formularios enviados, también se debe exportar» |
| **Fecha del pedido** | 05/09/2026 |
| **Issue / épica** | Análisis #366 (épica #69) · tasks #367–#375 · mock up: https://claude.ai/code/artifact/672365a4-39ae-4ef9-895d-3664a99e77fb |
| **Partes afectadas** | Backoffice |
| **Migración** | No requiere (previsto: sin modelos nuevos) |

## Pedido original

> «Vamos a armar un dashboard en el programa Becas, en `/becas/config/programas/1/`, al lado de Requisitos del programa
> quiero agregar una solapa de dashboard. Tiene que ser a nivel visual y poder exportar. Vamos a analizar cuántas horas
> consume y armemos un mock up. La idea es que tenga métricas generales, puedan filtrar sus convocatorias, relevamientos
> y data de formularios enviados. También se debe exportar.»

## Alcance acordado

Propuesto en el mock up; queda a aprobación del PM:

- **Tercera solapa «Dashboard»** en `programa_detail.html`, a la derecha de «Requisitos del programa». Las otras dos
  solapas no cambian.
- **Una fila de filtros** que alcanza a todos los bloques y a la exportación: período (últimos 30 / 90 días, este año,
  todo, personalizado), segmento, convocatoria, relevamiento (dependiente de la convocatoria) y canal (territorial /
  link público).
- **Bloques:** seis indicadores (convocatorias activas, relevamientos en curso, formularios recibidos con variación
  contra el período anterior, aprobados y tasa, cupo ocupado, lista de espera); formularios recibidos por semana;
  estado de los formularios y canal de carga; avance por convocatoria (tabla con medidores de revisado y cupo);
  relevamientos por estado; embudo de revisión; producción por territorial; **respuestas de los formularios** por
  pregunta (selector, sí/no y selector múltiple); formularios por localidad.
- **Exportación:** cada gráfico tiene vista de tabla y CSV propio; botón general «Exportar» con planilla XLSX de una
  hoja por bloque, CSV de la tabla de convocatorias, CSV de respuestas, e imprimir / guardar PDF desde el navegador.
  Todo respeta los filtros aplicados.
- **Permisos:** `becas.reportes.ver` para ver la solapa y `becas.reportes.exportar` para exportar, con el alcance
  visible del usuario (admin del programa, coordinador, coordinador regional), igual que el módulo de reportes.

**Queda afuera:** PDF generado en el servidor (WeasyPrint u otro, sumaría una dependencia a la imagen de ECOM),
comparativas entre programas, un tablero para el portal ciudadano.

## Decisiones tomadas

- **Se reutiliza el módulo de reportes, no se crea uno paralelo.** `programas/services/reportes_becas.py` ya calcula
  avance por convocatoria, cupos, embudo y producción territorial, y `exportacion_reportes.py` ya escribe CSV/XLSX.
  El dashboard es una vista agregada por programa de esos mismos datos; solo se agregan la serie semanal, las
  localidades y las respuestas.
- **Chart.js 4.4.6 ya vendorizado** (`static/vendor/chartjs/`) con carga diferida como hace `templates/inicio.html`.
  Sin librerías nuevas.
- **Totales cacheados 5 minutos** por (programa, filtros, alcance del usuario), con leyenda «Datos al …» y botón
  «Actualizar ahora». Es la forma de que la solapa no cueste una consulta pesada por cada apertura.
- **El cupo se mide sobre el total aprobado histórico**, no sobre el período filtrado: el cupo es del segmento y no
  depende de la ventana de fechas. El mock up lo aclara en la tabla.
- **Un solo color por serie de magnitud; colores de estado solo donde significan estado** (aprobado / rechazado /
  baja). La paleta se validó para daltonismo con los tokens de Chaco (`#5059bc`, `#ff5a1f`, `#009966`, `#bf57c4`).
- **Respuestas de los formularios detrás de una lectura única.** Hoy salen de `Formulario.data`
  (`{"globales": {...}, "requisitos": {...}}`); con el Cambio 58 pasan a `respuestas` + `definicion`. Se implementa
  contra una función de lectura para no rehacer el bloque cuando entre el constructor.
- **«Avance por convocatoria» es una tabla, no un gráfico:** el usuario compara filas, y el canon del backoffice
  prefiere tabla densa a cards repetidas.

## Implementación

**Mergeado en `development` el 05/09/2026 (PR #376, squash c59d995). Fases 1 a 6 del diseño técnico
[2026-09-05-dashboard-becas-design.md](../plans/2026-09-05-dashboard-becas-design.md):**

- Servicio `programas/services/dashboard_becas.py`: `metricas()` con los ocho bloques y los seis indicadores, caché de
  5 minutos con huella de alcance, `preguntas_graficables()` / `distribuciones_respuestas()` en una sola pasada detrás
  de la lectura única `respuesta_de()`, y `bloques_exportacion()`.
- `DashboardBecasFiltroForm` en `forms_reportes.py` (período → fechas, limpieza dependiente RN-5/RN-6).
- Vistas `programa_dashboard_datos` (JSON) y `programa_dashboard_exportar` (XLSX de varias hojas / CSV por bloque) con
  permisos `becas.reportes.ver` / `becas.reportes.exportar` y programa visible; `respuesta_libro()` en
  `exportacion_reportes.py`.
- Solapa en `programa_detail.html` (solo con la capacidad, deep link `?tab=dash`), panel `_dashboard_panel.html` +
  `_dashboard_card.html`, JS `static/custom/js/becas-dashboard.js` con Chart.js diferido y colores desde tokens.
- 27 tests en `programas/tests/test_dashboard_becas.py`, en verde con Django 5.2 (venv 3.12 igual al CI). Revisión
  visual con servidor SQLite local + Playwright en 1440 y 390 px, sin errores de consola ni de red.

Pasada de legibilidad (05/09/2026, después del merge): la tarjeta «Estado de los formularios» se rearmó sin canvas
(barra apilada, una fila por estado con cantidad y porcentaje, corte por canal con medidores); el indicador de
formularios lleva un minigráfico de doce semanas; el alcance se muestra como chips; la cabecera de la solapa queda
en una fila; las tarjetas de barras fijan su alto según las filas y los números de las tablas usan dígitos tabulares.

Gotcha aprendido: las funciones de `autorizacion` reciben el `Programa` del RBAC, no el `ProgramaSiis`; pasarles el
ProgramaSiis vacía el alcance en silencio. El servicio las llama sin ese argumento y filtra por ProgramaSiis después.

Estimación entregada al PM el 05/09/2026, con el mismo criterio de horas que las 150 h del Cambio 58:

| N.º | Bloque | Qué incluye | Horas |
|---|---|---|---|
| 1 | Servicio de métricas | Agregados por programa con filtros: indicadores, serie semanal, estados, embudo, avance por convocatoria, territoriales, localidades. Reusa `reportes_becas` y las funciones de alcance. | 10 |
| 2 | Respuestas de los formularios | Catálogo de preguntas del programa (globales + requisitos) de tipo selector / sí-no / múltiple; distribución por opción sobre el JSON de respuestas; lectura única compatible con el Cambio 58. | 10 |
| 3 | Vista y endpoint | Solapa en `programa_detail`, form de filtros validado, endpoint JSON para recalcular con filtros, permisos y alcance. | 5 |
| 4 | Interfaz | Filtros, seis stat cards, siete gráficos Chart.js con tooltips, leyendas y vista de tabla, tabla de avance, estados vacíos, responsive, stat-card a CSS compartido, build de Tailwind, `design_audit` en 0. | 14 |
| 5 | Exportación | XLSX de varias hojas (extiende `exportacion_reportes`), CSV por bloque, impresión / PDF con CSS de impresión. | 6 |
| 6 | Performance | Caché de 5 minutos por filtros y alcance, índices si hacen falta, presupuesto de consultas en tests. | 4 |
| 7 | Tests automáticos | Servicio (conteos con fixtures), permisos y alcance por rol, exportaciones, presupuesto de consultas. | 8 |
| 8 | Análisis, QA y pruebas | Épica, análisis y tasks en GitHub; casos QA por task; plan de pruebas; pruebas manuales de los cinco roles. | 10 |
| 9 | Puesta en marcha | Deploy a `test` y a producción de ECOM, registro y ajustes después de QA. | 3 |
| | **Total técnico** | | **70** |

Variantes técnicas: sin el bloque de respuestas de formularios (si se prefiere esperar al Cambio 58) baja a **56 h**; con
PDF generado en el servidor sube unas **6 h** y agrega una dependencia a la imagen.

**Propuesta enviada al Ministerio (05/09/2026, mail del PM a Guido):** **86 h** para el desarrollo completo, o **70 h**
si el bloque de respuestas se posterga hasta terminar el constructor. La diferencia con el total técnico (16 h y 14 h)
es gestión, reuniones de definición y coordinación, que el PM sumó al presentar. Es la cifra que figura en
[docs/client/versiones/version-002.md](../client/versiones/version-002.md) como frente 7 de la Versión 002.

## Archivos

Nuevos: `programas/services/dashboard_becas.py`, `programas/views/dashboard_becas.py`,
`programas/templates/programas/becas/config/_dashboard_panel.html`, `_dashboard_card.html`,
`static/custom/js/becas-dashboard.js`, `programas/tests/test_dashboard_becas.py`,
`docs/plans/2026-09-05-dashboard-becas-design.md`. Modificados: `programas/forms_reportes.py`,
`programas/services/exportacion_reportes.py`, `programas/views/configuracion.py`, `programas/urls.py`,
`programas/templates/programas/becas/config/programa_detail.html`, `static/custom/css/tailwind.css` (build),
`.claude/agents/chaco-design-system.md` (inventario: fila del dashboard y deep link de tabs). No se movió el CSS
`.stat-card` de `inicio.html`: la stat card canónica es el patrón Tailwind de `convocatoria_detail.html`.

## Base de datos

No requiere: sin modelos ni migraciones. El presupuesto de consultas del servicio no crece con la cantidad de
formularios (test `test_presupuesto_de_consultas_no_crece_con_los_formularios`).

## Validación

Automática (05/09/2026): 27 tests en verde con Django 5.2 — conteos a mano, coherencia entre bloques (CA-3), alcance
del coordinador regional (CA-4), cupo insensible al período (RN-9), variación `None` sin período anterior (RN-8),
respuestas simple/múltiple con base y opción fuera de catálogo (RN-14/15), caché por alcance (RN-18), 403 sin
capacidad de ver y de exportar (CA-1, CA-6), XLSX con una hoja por bloque y fórmula neutralizada, CSV por bloque,
presupuesto de consultas. `manage.py check`, `design_audit --changed` 0/0, `compile_templates` 0,
`check_design_agent --changed` OK, ruff OK. Revisión visual en 1440 y 390 px sin errores.

Pendiente: QA funcional por rol (#374) y contraste de un mismo recorte contra el hub de reportes.

## Puesta en marcha en el servidor

05/09/2026: espejado al GitLab de ECOM con `/pushGitLabecom`, primero `test` (merge 1e37076, testing en datanach.ecomdev.ar)
y después `main` (release 43ffddf, producción, avance directo 17dc060..43ffddf). Sin migraciones ni variables nuevas; el mismo
push llevó el Cambio 63 (Argon2 + gunicorn opcional), que no se había espejado. La pasada de legibilidad (PR #377, squash ef284bc) se
desplegó el mismo día: release 55d842e a `test` (merge e7732b8) y a `main` (avance directo 43ffddf..55d842e), también sin
migraciones ni dependencias nuevas.

**Incidente en producción (05/09/2026, misma noche):** con 4.000 inscriptos la solapa quedaba vacía («Sin calcular
todavía», indicadores en guion, sin alerta). Causa más probable: la serie semanal usaba `TruncWeek` sobre un
`DateTimeField` con `USE_TZ`, que en MySQL se traduce a `CONVERT_TZ`; sin tablas de zona horaria en el servidor devuelve
NULL y Django corta con «Database returned an invalid datetime value» (SQLite y los tests no lo reproducen). Corrección
PR #378 (squash f866d05, release fc740b8): las semanas se agrupan en Python, y el JS muestra «Calculando…», cancela a
los 60 s y expone toda falla en la alerta inline con `console.error`. Espejado a `test` (merge dffce4d) y a `main`
(55d842e..fc740b8). Con el JS nuevo en producción el navegador mostró la causa real: el endpoint responde **500**. Contra un MySQL 8.0
local con 2.455 formularios sintéticos todo responde 200, así que depende de la forma de los datos reales. Segunda
corrección (PR #379): la lectura del JSON de respuestas y de las opciones de las preguntas tolera filas con `data` como
string, bolsas que no son dict, valores y opciones con forma `{valor, etiqueta}`; y el endpoint degrada por etapas: si
fallan las métricas responde 500 con la etapa y el tipo de error, si falla solo la pregunta devuelve el resto con `avisos`,
y en los dos casos el traceback completo va al log del servidor con `logger.exception`. Si vuelve a fallar, el mensaje
dirá la etapa y el tipo, y el log de ECOM tendrá el detalle. Sin pasos especiales: no hay migración ni variables nuevas. Flujo habitual a `test` y después `main` de ECOM.
El CI del PR quedó con los cinco checks que ya estaban rojos en `development` desde el 30/08/2026 (presupuesto de
`relevamiento_detalle`, ruff lint/format en archivos ajenos y las CVE de djangorestframework 3.16.1); el único propio,
Bandit por sha1 en la clave de caché, se corrigió antes de mergear.

## Pendientes / a definir

- Validación de Guido (Ministerio) del alcance y de las 86 h propuestas. El análisis y las tasks ya están creados en
  Backlog: si el Ministerio pide recortar, se ajustan antes de que el PM las mueva a Ready.
- Las tres asunciones del análisis #366 esperan confirmación: el nombre «Dashboard», si el bloque de respuestas entra
  en esta etapa o después del Cambio 58, y si se muestran todas las preguntas de opciones cerradas o una selección.
- Nombre de la solapa: «Dashboard» (como se pidió) o «Tablero».
- Si el bloque «Respuestas de los formularios» entra ahora o después del Cambio 58.
- Qué preguntas se muestran en «Respuestas»: todas las de tipo selector / sí-no / múltiple del programa, o una
  selección que haga el admin.

## Reversión

No aplica hasta implementar. La solapa se podrá ocultar quitando la capacidad, sin tocar datos.

## Historial

Entrada nueva. Antecedentes: el módulo de reportes de Becas (agosto de 2026: hub con cinco reportes y CSV/XLSX, que
este dashboard reutiliza) y el Cambio 58 (constructor de formularios, que cambia el origen de las respuestas).

---
