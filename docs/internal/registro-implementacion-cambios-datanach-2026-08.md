# Registro de implementación — Cambios DataÑach

**Estado:** En curso  
**Inicio:** 7 de agosto de 2026  
**Rama de trabajo:** `fixes-31-07`  
**Documento funcional relacionado:** `docs/internal/analisis-funcional-cambios-datanach-2026-08.md`

## Objetivo del registro

Registrar cada modificación realizada a partir del documento “Cambios en DataÑach”, incluyendo alcance, archivos, base de datos, validaciones y forma de reversión.

> Este archivo no reemplaza el historial de Git. Antes de desplegar se recomienda crear commits separados o claramente identificables. No debe ejecutarse una reversión de base de datos sin respaldo cuando ya existan datos cargados en los campos nuevos.

## Resumen

| Cambio | Estado | Parte | Migración |
|---|---|---|---|
| 1 — Recordarme | 🟢 **Hecho** | Backoffice / sesión | No |
| 2 — Limpieza de datos de prueba | 🟡 **Para limpieza en base de test** | Infraestructura / datos | No desarrollada |
| 3 — Becas → Programas en menú | 🟢 **Hecho** | Backoffice | No |
| 4 — Revisar tipos de usuarios | 🟢 **Hecho** | Backoffice / permisos | `programas.0038` + `users.0015` |
| 5 — Datos adicionales de usuario | 🟢 **Hecho** | Backoffice / modelo / API | `users.0012` |
| 6 — Usuarios y Roles dentro de Programas | 🟢 **Hecho mediante alta contextual** | Backoffice | No |
| 7 — Quitar categoría Becas | 🟢 **Hecho** | Backoffice / roles | No |
| 8 — Incorporar programas | 🟡 **Pertenece a ECOM** | ECOM / SIIS | No desarrollada |
| 9 — Localidades como subsegmentos | 🟡 **Se decidió ponerlo en el título de la convocatoria** | Backoffice / decisión funcional | No desarrollada |
| 10 — Fecha desde/hasta del relevamiento | 🟢 **Hecho** | Backoffice / Mobile / API | `programas.0036` |
| 11 — Domicilio actual del ciudadano | 🟢 **Hecho** | Backoffice | No |
| 12 — Desplegable de búsqueda de legajos | 🟢 **Hecho** | Backoffice | No |
| 13 — Correo al crear usuario | 🟡 **Implementado — pendiente SMTP ECOM** | Backoffice / correo | No |
| 14 — Sesión web única por usuario | 🟢 **Hecho** | Backoffice | `users.0013` |
| 15 — Administrador de programa y pausas | 🟢 **Hecho** | Backoffice / Mobile / API | `programas.0037` |
| 16 — Coordinador del segmento | 🟢 **Hecho** | Backoffice / permisos | `users.0014` |
| 17 — Referente | 🟢 **Hecho** | Backoffice / permisos / servidor | `programas.0038` + `users.0015` |
| 18 — Coordinador regional | 🟢 **Hecho** | Backoffice / Mobile / permisos / servidor | `programas.0038` + `users.0015` |
| 19 — Territorial | 🟡 **Parcialmente hecho — GPS pendiente** | Backoffice / Mobile / permisos / servidor | `programas.0040` |

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
- **Coordinador regional** es un perfil distinto, limitado a una Región formada por localidades.

## Impacto técnico

Se completó la matriz de roles, capacidades y filtros del servidor mediante los Cambios 17 y 18. No se duplicó el rol Administrador.

## Validación

La matriz se verificó junto con las pruebas de los Cambios 17 y 18.

## Reversión

La reversión funcional se encuentra detallada en los Cambios 17 y 18. Si se decidiera separar Coordinador general y Administrador, primero deberá definirse una matriz nueva para evitar permisos contradictorios.

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

🟢 **HECHO**

## Implementación

- Se creó el rol `Becas — Coordinador regional` y la entidad Región, compuesta por localidades/subsegmentos.
- Puede crear convocatorias y relevamientos solamente en su Región y ve sólo las convocatorias creadas por él que permanecen bajo su responsabilidad.
- Puede crear, editar, activar, desactivar y asignar solamente Territoriales propios; no administra roles ni pausa elementos.
- Puede recibir un relevamiento propio y operar por Mobile con las mismas validaciones de asignación.
- El Administrador dispone de una pantalla de Regiones y una acción explícita de reemplazo.
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

Por cada cambio siguiente agregar:

1. Número y título original.
2. Alcance acordado.
3. Implementación realizada.
4. Archivos modificados.
5. Migraciones o datos afectados.
6. Pruebas automáticas y manuales.
7. Procedimiento de reversión.
