# Análisis funcional — Cambios solicitados para DataÑach

**Estado:** Borrador en análisis  
**Fecha:** 7 de agosto de 2026  
**Origen:** Documento “Cambios en DataÑach” enviado por el cliente  
**Criterio de organización:** Los puntos conservan el orden del documento original. En cada uno se indica la parte del sistema responsable.

**Registro técnico de implementación y reversión:** `docs/internal/registro-implementacion-cambios-datanach-2026-08.md`

> Este documento es un borrador interno de análisis. Las definiciones pendientes deben resolverse antes de crear las tareas definitivas. La fuente de verdad final debe quedar en los Issues de GitHub.

## Referencias de componentes

| Identificación | Parte del sistema |
|---|---|
| **Backoffice** | Portal web de administración y consulta. |
| **Mobile** | APK utilizada por territoriales/relevadores. |
| **Servidor/API** | Reglas que deben controlarse centralmente y servicios consumidos por Backoffice y Mobile. |
| **Infraestructura/ECOM** | Ejecución en ambientes, base de datos, correo, despliegues y configuración operativa. |

## Capturas revisadas

Se revisaron las siete imágenes incrustadas en el DOCX y se asociaron de la siguiente manera:

| Captura | Punto relacionado | Información aportada |
|---|---|---|
| Menú lateral con “Becas” | Cambio 3 | Identifica el texto visible que debe pasar a “Programas”. |
| Pantalla “Nuevo usuario” | Cambio 5 | Confirma que faltan DNI, teléfono, institución y observación. |
| Selector “Programa SIIS” | Cambio 8 | Confirma que los cuatro programas no están en el catálogo externo y requieren gestión con ECOM/SIIS. |
| Pantalla “Nuevo subsegmento” | Cambio 9 | Confirma que hoy se selecciona un Segmento SIIS y no una localidad. |
| Pantalla “Nuevo relevamiento” | Cambio 10 | Confirma una sola Fecha asignada y una Zona/Localidad de texto libre. |
| Pantalla “Crear Ciudadano” | Cambio 11 | Confirma que Domicilio ya existe; el pedido es principalmente identificarlo como actual. |
| Buscador de Inicio con DNI 31538703 | Cambio 12 | Ubica el bug en el buscador rápido del Dashboard y aporta un caso para reproducir. |

---

# Cambios pedidos

Los cambios 1 a 19 siguen estrictamente el orden de aparición del DOCX original.

## Cambio 1 — Revisar “Recordarme” porque no funciona — 🟢 **HECHO**

**Parte:** Backoffice + Servidor/API.

**Resolución:** “Recordarme” conserva la sesión durante 24 horas; sin marcarlo, la sesión vence al cerrar el navegador. Un usuario ya autenticado es redirigido desde el login hacia Inicio.

**Estado actual:** El login muestra la opción “Recordarme”, pero no se observa una implementación que cambie la duración de la sesión según la selección.

**Cambio requerido:**

- Si se selecciona “Recordarme”, mantener la sesión durante el período que se defina.
- Si no se selecciona, finalizar la sesión al cerrar el navegador o al vencer el tiempo de inactividad.
- Aplicar el mismo comportamiento en test y producción.

**Pendiente de definición:** Duración de la sesión recordada.

## Cambio 2 — Quitar usuarios y datos de prueba — 🟡 **PARA LIMPIEZA EN BASE DE TEST**

Incluye datos de prueba de:

- Usuarios.
- Segmentos.
- Subsegmentos.
- Convocatorias.
- Relevamientos.
- Revisión.

**Parte:** Servidor/datos + Infraestructura/ECOM. Desarrollo puede preparar el procedimiento.

**Cambio requerido:**

- Identificar exactamente los registros de prueba.
- Revisar sus relaciones antes de eliminarlos.
- Preparar un comando o procedimiento controlado si la limpieza es compleja.
- Realizar una copia de seguridad.
- Ejecutar primero en test y validar el resultado antes de producción.

**Fuera del alcance directo del equipo:** Ejecutar una eliminación destructiva en producción sin autorización, respaldo y participación de Infraestructura.

**Pendiente de definición:** Listado de registros considerados de prueba.

## Cambio 3 — Quitar la palabra “Becas” y reemplazarla por “Programas” — 🟢 **HECHO**

**Parte acordada:** Backoffice.

**Resolución:** Se cambió únicamente la etiqueta visible **Becas** del menú lateral por **Programas**, incluyendo el texto accesible del menú colapsado. No se modificaron rutas, permisos, pantallas internas, API ni APK.

**Estado actual:** El portal, la API y la APK contienen textos y referencias al módulo Becas. También existe el concepto genérico de Programa.

**Evidencia de la captura:** La imagen señala específicamente la opción **Becas** del menú lateral del Backoffice. Por lo tanto, el pedido confirmado por la captura es, como mínimo, renombrar ese acceso visible a **Programas**. La imagen no demuestra por sí sola que deban renombrarse rutas, tablas o permisos técnicos.

**Cambio requerido:**

- Cambiar menú, títulos, etiquetas y mensajes visibles del Backoffice.
- Cambiar los textos visibles de la APK.
- Cambiar los mensajes públicos de la API cuando corresponda.
- Mantener inicialmente los códigos técnicos internos `becas.*` si renombrarlos implica romper permisos, rutas o migraciones existentes.

**Pendiente de definición:** Confirmar si se solicita sólo un cambio de nombre visible o si cada programa tendrá un circuito independiente.

## Cambio 4 — Revisar los tipos de usuarios de esta etapa — 🟢 **HECHO**

El documento enumera:

1. Coordinador general del programa.
2. Coordinador regional.
3. Referente.
4. Territorial.

**Parte:** Backoffice + Servidor/API. Territorial también impacta Mobile.

**Estado actual:** Existen los roles Administrador, Coordinador y Territorial para el módulo actual. No se identificaron equivalentes completos para Referente y Coordinador regional.

**Cambio requerido:**

- Definir la jerarquía entre los cuatro roles.
- Definir cómo se relacionan con programas, segmentos, localidades y otros usuarios.
- Asignar capacidades y restricciones verificables.
- Aplicar el alcance en las consultas y operaciones del servidor, no sólo ocultando opciones en pantalla.

**Definición acordada:** “Coordinador general del programa” y “Administrador del programa” representan el mismo rol. Se conserva el rol técnico existente **Administrador del programa**, con las facultades detalladas en el Cambio 15. “Coordinador del segmento” continúa siendo un rol diferente y limitado a sus segmentos, según el Cambio 16.

**Jerarquía resultante:**

1. Administrador del programa / Coordinador general del programa: mismo perfil, alcance completo dentro del programa.
2. Coordinador del segmento: perfil existente con alcance por segmento.
3. Referente: depende de un Coordinador del segmento y hereda su alcance, según el Cambio 17.
4. Coordinador regional: administra su Región y sus convocatorias/Territoriales, según el Cambio 18.
5. Territorial: perfil exclusivo de Mobile, con las reglas del Cambio 19.

**Resolución:** Los roles Referente y Coordinador regional fueron definidos e implementados en los Cambios 17 y 18. La jerarquía queda completa.

## Cambio 5 — Agregar datos al crear usuarios — 🟢 **HECHO**

Datos solicitados:

- DNI.
- Teléfono.
- Institución.
- Observación.

**Parte:** Backoffice + Servidor/API.

**Resolución:** Se agregaron DNI, teléfono, institución y observación al alta y edición. Por ahora son opcionales. El DNI admite entre 6 y 8 números y no puede repetirse. Los campos obligatorios actuales muestran un asterisco.

**Estado actual:** El alta administra nombre, apellido, usuario, correo, contraseña, roles y asignación territorial, pero no todos los datos solicitados.

**Evidencia de la captura:** La pantalla **Nuevo usuario** actualmente muestra Nombre de usuario, Email, Nombre, Apellido y Contraseña. Los cuatro datos pedidos no aparecen en el bloque visible. La modificación corresponde a esta misma pantalla, no a un alta separada.

**Cambio requerido:**

- Incorporar los campos al perfil del usuario.
- Mostrarlos en alta, edición y detalle.
- Validar formato y eventual unicidad del DNI.
- Definir si Institución utiliza el catálogo existente o es texto libre.

**Pendiente de definición:** Obligatoriedad de cada campo y tratamiento de usuarios existentes.

## Cambio 6 — Poner Usuarios y Roles dentro de Becas (Programas) — 🟢 **HECHO**

**Parte:** Backoffice.

**Solución aplicada:** La gestión contextual de usuarios se incorporó dentro de las pantallas de Programas mediante modales de alta rápida. Cuando una convocatoria, segmento, subsegmento o relevamiento requiere seleccionar un usuario, el operador autorizado puede crearlo sin abandonar la pantalla y dejarlo seleccionado o asignado inmediatamente.

**Cambio requerido:**

- Se reutilizan las validaciones y servicios del ABM existente.
- El modal muestra solamente los campos y roles permitidos para el operador.
- El usuario creado queda disponible y puede asignarse directamente al elemento en edición.
- Los permisos se validan en el servidor; ocultar el botón no es la única protección.
- El ABM general de Roles permanece disponible solamente para quienes tienen permiso para administrarlo.

**Definición adoptada:** El pedido se resuelve con alta contextual por modal, sin duplicar los ABM ni crear pantallas independientes por programa.

## Cambio 7 — En Editar rol, quitar la categoría “Becas” y dejar solamente “Programa” — 🟢 **HECHO**

**Parte:** Backoffice + Servidor/datos.

**Resolución:** Se retiró `Becas` de las categorías seleccionables en el alta y edición de roles, tanto para administradores globales como para administradores de programa. Los roles del módulo continúan usando categoría `Programa`, programa asociado `Becas` y capacidades técnicas `becas.*`. No se modificaron permisos, API ni APK.

**Estado actual:** Conviven referencias de categoría Becas y Programa. Los roles actuales del módulo se crean asociados a la categoría Programa.

**Cambio requerido:**

- Quitar Becas de las opciones visibles de categoría.
- Migrar a Programa los roles antiguos que todavía utilicen Becas.
- Verificar que los usuarios no pierdan permisos durante la migración.

## Cambio 8 — Incorporar programas — 🟡 **PERTENECE A ECOM**

Programas solicitados, en el orden del documento:

1. Mamá Ñachec.
2. Futuro Joven.
3. Segmento FE.
4. Mi Casa Ñachec.

El documento aclara que ya se envió un correo a ECOM.

**Parte:** Backoffice + Servidor/datos + Infraestructura/ECOM. Impacta Mobile si la APK debe distinguir programas.

**Estado actual:** Existe un catálogo genérico de programas y una instancia técnica de Becas.

**Evidencia de la captura:** En **Nuevo segmento**, el campo obligatorio **Programa SIIS** despliega programas provenientes del catálogo de SIIS. Los cuatro programas solicitados no aparecen. La anotación de la captura indica: “Estos programas ya no están. Escribir nosotros, lo creamos nosotros”. Junto con la aclaración de que ya se escribió a ECOM, esto muestra una dependencia externa: primero ECOM/SIIS debe dar de alta o exponer esos programas; después DataÑach podrá seleccionarlos.

**Cambio requerido:**

- Crear los cuatro programas con código, nombre, descripción y estado.
- Solicitar o confirmar su creación en SIIS por parte de ECOM.
- Asociar los identificadores de SIIS devueltos.
- Definir administradores y roles iniciales.
- Determinar si cada programa tendrá configuración, segmentos, convocatorias y relevamientos propios.
- Mostrar el programa correspondiente en la APK cuando existan relevamientos de más de uno.

**Responsabilidad propuesta:**

- **ECOM/SIIS:** crear o publicar los cuatro programas en el catálogo externo.
- **Backoffice/Servidor:** consumir el catálogo actualizado y vincular cada programa externo con su configuración local.
- **Mobile:** sólo requiere cambio si el relevamiento debe mostrar o permitir distinguir el programa.

**No recomendado:** Escribir los cuatro nombres únicamente dentro del selector del frontend, porque quedarían sin un identificador válido de SIIS y podrían desaparecer o duplicarse al sincronizar el catálogo.

**Pendiente de definición:** Códigos, identificadores SIIS y grado de independencia funcional entre programas.

## Cambio 9 — Quitar los subsegmentos actuales y permitir agregar localidades de Chaco — 🟡 **SE DECIDIÓ PONERLO EN EL TÍTULO DE LA CONVOCATORIA**

**Parte:** Backoffice + Mobile + Servidor/datos + Infraestructura/ECOM.

**Decisión actual:** Por ahora, la localidad se identificará en el título de la convocatoria. No se implementará todavía una modificación estructural de subsegmentos ni un catálogo de localidades. El análisis técnico siguiente se conserva como antecedente si esta decisión cambia.

**Estado actual:** Ya existe el ABM de subsegmentos asociados a segmentos. El modelo no establece que un subsegmento sea necesariamente una localidad oficial.

**Evidencia de la captura:** La pantalla **Nuevo subsegmento** no permite escribir libremente su nombre. Obliga a seleccionar un **Segmento SIIS**, copia su nombre e ID y solicita además Descripción y Cupo máximo. Esto confirma que el flujo actual no está diseñado para elegir localidades. Habrá que reemplazar o adaptar ese selector, y no solamente limpiar registros existentes.

**Cambio requerido en Backoffice:**

- Permitir administrar las localidades/subsegmentos.
- Asociarlas al segmento y programa correspondientes.
- Evitar duplicados.
- Evaluar si se utiliza un catálogo oficial en lugar de nombres libres.
- Sustituir el selector actual de Segmento SIIS por un catálogo de localidades o por el mecanismo que confirme ECOM.
- Revisar si el Cupo máximo debe continuar perteneciendo al subsegmento/localidad.

**Cambio requerido en Mobile:**

- Mostrar la localidad asignada al relevamiento.
- Permitir trabajar solamente con las localidades recibidas como asignadas.

**Cambio requerido en Servidor/API:**

- Validar la asignación en cada operación.
- Entregar a la APK solamente relevamientos y localidades autorizadas.

**Tarea de Infraestructura/datos:**

- Respaldar y retirar los subsegmentos de prueba confirmados.
- Cargar el catálogo inicial acordado.
- No eliminar subsegmentos que tengan información real vinculada sin definir una migración.

**Pendiente de definición:** Si “subsegmento” seguirá siendo el nombre técnico, cuál es la fuente oficial de localidades, si una localidad puede pertenecer a más de un segmento o programa y si conserva un cupo propio.

## Cambio 10 — Fecha del relevamiento desde/hasta, incluso un solo día

🟢 **HECHO**

**Parte:** Backoffice + Mobile + Servidor/API.

**Estado implementado:** Cada relevamiento posee Fecha desde y Fecha hasta. El Backoffice, la API y Mobile trabajan con el período completo.

**Evidencia de la captura:** La ventana **Nuevo relevamiento** contiene Convocatoria, Territorial asignado, Zona/Localidad y una única **Fecha asignada**. La captura confirma que el pedido apunta a reemplazar o ampliar esta fecha única con **Fecha desde** y **Fecha hasta**. También muestra que Zona/Localidad es actualmente un campo de texto, no una localidad seleccionada de un catálogo.

**Cambio requerido en Backoffice:**

- Permitir definir fecha desde y fecha hasta para cada relevamiento, si ése es el alcance confirmado.
- Permitir que ambas sean iguales.
- Impedir que la fecha hasta sea anterior a la fecha desde.
- Validar que el período esté dentro de la convocatoria.
- Reemplazar Zona/Localidad de texto libre por la localidad/subsegmento asignada cuando se defina el nuevo catálogo.

**Cambio requerido en Mobile:**

- Mostrar el período completo.
- Permitir iniciar y cargar personas cualquier día dentro del período.
- Bloquear nuevas cargas fuera del período.
- Adaptar el trabajo sin conexión al nuevo rango de fechas.

**Cambio requerido en Servidor/API:**

- Entregar ambas fechas.
- Validar cada inicio, carga, sincronización y finalización contra el período.

**Definición aplicada:** El relevamiento puede continuar en curso durante varios días y finalizarse anticipadamente. Fuera del período no admite nuevas cargas ni sincronizaciones. Ambas fechas deben estar dentro de la convocatoria.

## Cambio 11 — En la creación del ciudadano, poner domicilio actual

🟢 **HECHO**

**Parte:** Backoffice. También Mobile si debe capturarse durante el relevamiento.

**Estado actual:** El ciudadano ya tiene domicilio, provincia, municipio y localidad.

**Evidencia de la captura:** La pantalla **Crear Ciudadano** ya muestra un campo **Domicilio** dentro de Información de contacto. Por lo tanto, la captura no pide crear un campo nuevo: el cambio mínimo respaldado por la evidencia es renombrarlo como **Domicilio actual**. Sólo sería necesario modificar el modelo si el cliente también quiere distinguir domicilio actual de domicilio anterior o legal.

**Cambio implementado:**

- Se reutiliza el campo existente, sin migración ni pérdida de datos.
- La etiqueta se muestra como “Domicilio actual” en alta, confirmación, edición y detalle del ciudadano en Backoffice.
- Conserva su obligatoriedad actual: es opcional.
- No se crea historial de domicilios ni se modifica Mobile dentro de este cambio.

## Cambio 12 — Bug al buscar un legajo

🟢 **HECHO**

**Parte:** Backoffice + Servidor/API.

**Problema confirmado:** La búsqueda encontraba ciudadanos, pero la tarjeta contenedora usaba `overflow: hidden`; el desplegable podía quedar recortado al abrirse hacia abajo, especialmente según navegador, resolución o zoom.

**Evidencia de la captura:** El error señalado corresponde al buscador rápido de la pantalla **Inicio**, debajo de los indicadores, y no necesariamente al listado general de legajos. En el ejemplo se escribe el DNI **31538703** y no se muestra ningún resultado visible. El código confirma que ese cuadro consulta la API de búsqueda del Dashboard y que debería buscar ciudadanos por DNI, nombre o apellido.

**Cambio implementado:**

- La tarjeta del buscador permite mostrar el desplegable fuera de sus límites.
- El listado queda por encima de las secciones siguientes.
- No se modifica la consulta ni la API porque el defecto estaba en la presentación.
- Se agregó localmente un ciudadano de ejemplo con DNI 31538703 para la prueba visual.

## Cambio 13 — Notificar por correo que se creó un usuario

🟡 **IMPLEMENTADO — PENDIENTE CONFIGURACIÓN SMTP DE ECOM**

La notificación debe enviarse a la persona registrada.

**Parte:** Backoffice + Servidor/API + Infraestructura/ECOM.

**Estado implementado:** Al crear un usuario con correo informado se envía una invitación con su nombre de usuario y un enlace temporal para establecer una contraseña. La contraseña cargada por el administrador nunca se incluye en el mensaje.

**Cambio requerido en Backoffice/Servidor:**

- Enviar un correo al finalizar el alta.
- Informar nombre de usuario, enlace de acceso y un mecanismo seguro para establecer la contraseña.
- No enviar una contraseña permanente en texto plano.
- Informar al administrador si el envío falló.

**Tarea de Infraestructura:**

- Configurar servidor de correo, remitente y credenciales en test y producción.
- Verificar entrega y registro de errores.

**Definición aplicada:** Un fallo de correo no revierte la creación del usuario; el administrador recibe una advertencia. En desarrollo el mensaje se imprime en los logs. ECOM debe configurar SMTP y remitente para test y producción.

## Cambio 14 — Impedir que el mismo usuario esté abierto al mismo tiempo en diferentes lugares

🟢 **HECHO**

**Parte:** Backoffice.

**Definición aplicada:**

- Cada usuario puede conservar una sola sesión activa en el Backoffice.
- Un nuevo ingreso web reemplaza al anterior.
- Cuando se vuelve a navegar desde la sesión anterior, se cierra y se informa que fue reemplazada.
- Las sesiones abiertas antes del despliegue se adoptan como válidas hasta que exista un nuevo ingreso.

**Fuera de alcance acordado:** Mobile. Sus tokens y relevamientos pendientes de sincronización no se modifican ni se invalidan con esta regla.

---

# Cambio 15 — Rol Administrador del programa

🟢 **HECHO**

## 15.1 Crea usuarios y roles

**Parte:** Backoffice + Servidor/API.

**Estado verificado:** El administrador de programa administra únicamente usuarios y roles dentro de sus programas autorizados. Los cuatro programas dependen de la carga/configuración indicada en el Cambio 8, responsabilidad de ECOM.

**Reglas conservadas:**

- Conservar el alcance por programa.
- Impedir que administre usuarios o roles de otros programas.
- Adaptar el comportamiento a los cuatro programas solicitados.

## 15.2 Puede pausar cualquier sector, segmento, subsegmento y relevamiento

El documento aclara: “Creo que ya lo hace, pero chequeo”.

**Parte:** Backoffice + Servidor/API.

**Asunción aplicada:** “Sector” equivale a **Convocatoria**.

**Implementación realizada:**

- El Administrador del programa puede pausar y reanudar convocatorias, segmentos, subsegmentos y relevamientos.
- Cada acción exige un motivo y registra elemento, acción, usuario, fecha y hora.
- El historial se conserva al reanudar y no se sobrescribe.
- Pausar un nivel superior bloquea operativamente los relevamientos dependientes sin borrar ni cambiar sus estados previos.
- El Backoffice y Mobile muestran el estado pausado y su motivo.
- Mobile no permite iniciar, cargar personas, adjuntar, finalizar ni reabrir mientras la pausa esté vigente.

**A confirmar con el cliente:** La equivalencia “Sector = Convocatoria”.

---

# Cambio 16 — Coordinador del segmento

🟢 **HECHO**

## 16.1 No puede detener ni pausar el segmento

**Parte:** Backoffice + Servidor/API.

**Cambio requerido:**

- Ocultar las acciones no autorizadas.
- Rechazar igualmente la operación desde el servidor si se intenta invocar directamente.

**Estado verificado:** Las acciones de pausa están reservadas al Administrador del programa. El Coordinador no ve la acción y el servidor rechaza el acceso directo.

## 16.2 Crea usuarios, pero no puede crear roles

**Parte:** Backoffice + Servidor/API.

**Definición aplicada:** El Coordinador puede crear y editar únicamente usuarios Territoriales asignados a uno de sus segmentos activos.

**Cambio requerido:**

- Permitir crear solamente los tipos de usuario autorizados dentro de su segmento.
- Impedir alta, edición o eliminación de roles.
- Impedir asignar permisos superiores a los propios.

**Restricciones implementadas:** No puede ingresar al ABM de roles, asignar roles diferentes de Territorial, elegir segmentos ajenos, administrar coordinadores ni otorgar permisos.

**Alta contextual:** En cada selector de Coordinador o Territorial se puede abrir un modal de creación. El sistema asigna el rol correcto, vincula al Territorial con el segmento correspondiente y deja al usuario nuevo seleccionado en el formulario original. Solo el Administrador puede usarlo para crear Coordinadores.

## 16.3 Sólo puede consultar datos de su segmento

**Parte:** Backoffice + Servidor/API.

**Estado actual:** Ya existe una asignación de coordinadores a segmentos y filtros de autorización por segmento.

**Cambio requerido:**

- Reutilizar y ampliar el alcance existente.
- Aplicarlo a convocatorias, relevamientos, territoriales, formularios, revisión, cupos y reportes.
- Verificar que exportaciones y accesos directos respeten el mismo filtro.

**Estado verificado:** Convocatorias, relevamientos, territoriales, formularios, revisión y cupos utilizan el alcance por segmentos asignados. Las exportaciones permanecen reservadas al Administrador del programa y el acceso directo del Coordinador es rechazado.

---

# Cambio 17 — Referente

🟢 **HECHO**

El documento lo describe como “mano derecha del coordinador del programa”.

## 17.1 No puede detener ni pausar el segmento

**Parte:** Backoffice + Servidor/API.

**Cambio requerido:** Ocultar y rechazar las operaciones de pausa o detención.

## 17.2 Crea usuarios, pero no roles

**Parte:** Backoffice + Servidor/API.

**Cambio requerido:**

- Permitir alta de usuarios dentro de su alcance.
- Impedir administrar roles.
- Impedir asignar usuarios o permisos fuera de su alcance.

**Definición:** Puede crear y administrar solamente usuarios Territoriales dentro de los segmentos heredados.

## 17.3 Sólo puede consultar datos de sus coordinadores generales y territoriales

**Parte:** Backoffice + Servidor/API.

**Estado actual:** No existe una relación jerárquica equivalente para el rol Referente.

**Cambio requerido:**

- Crear la relación entre Referente y los usuarios bajo su responsabilidad.
- Filtrar usuarios, convocatorias, relevamientos, formularios y reportes según esa relación.

**Definición:** Su alcance se obtiene del Coordinador del segmento asignado y comprende sus Territoriales y datos operativos.

## Definición aplicada

- El Referente depende de un Coordinador del segmento.
- Hereda los segmentos activos de ese Coordinador.
- Puede crear, editar, activar y desactivar Territoriales de esos segmentos.
- Puede consultar usuarios Territoriales, convocatorias, relevamientos, formularios, avances y cupos del alcance heredado.
- No crea roles, convocatorias ni relevamientos y no puede pausar elementos.
- Al cambiar de Coordinador pierde el alcance anterior, sin eliminar información histórica.

## Consultas resueltas para implementar

1. ¿El Referente pertenece a un programa completo, a un segmento o a un Coordinador específico?
2. ¿Un Referente puede estar relacionado con más de un Coordinador o segmento?
3. ¿Quién asigna y desasigna los Referentes: el Administrador del programa o el Coordinador?
4. ¿Qué significa “sus coordinadores generales” dentro de los roles reales del sistema?
5. ¿Puede crear solamente Territoriales o también Coordinadores y otros Referentes?
6. Además de crear usuarios, ¿puede editarlos, desactivarlos, restablecerles el acceso o reasignarlos?
7. ¿Puede consultar datos de los Coordinadores o solamente los datos operativos de sus Territoriales?
8. ¿Qué pantallas debe poder consultar: usuarios, convocatorias, relevamientos, formularios, revisión, cupos, beneficiarios y reportes?
9. ¿Debe poder crear o modificar convocatorias y relevamientos, o su acceso operativo se limita a usuarios y consulta?
10. Si un Territorial cambia de segmento o Coordinador, ¿deja automáticamente de estar visible para el Referente anterior?

**Implementación:** Se agregaron el rol `Becas — Referente`, su capacidad identificadora y la relación explícita Referente → Coordinador. Los filtros se ejecutan en el servidor.

---

# Cambio 18 — Coordinador regional

⚫ **RETIRADO POR DECISIÓN FUNCIONAL — 10/08/2026**

> El pedido original se conserva debajo como trazabilidad del DOCX, pero ya no forma parte del alcance implementado. Se eliminaron el rol Coordinador regional, la entidad Región, la pantalla de configuración, las asignaciones, transferencias y filtros regionales. Permanecen sin cambios Administrador, Coordinador del segmento, Referente y Territorial.

## 18.1 Sólo ve datos de la convocatoria que creó

**Parte:** Backoffice + Servidor/API.

**Estado actual:** El coordinador actual se limita por segmento; no por autoría de la convocatoria.

**Cambio requerido:**

- Registrar el creador de la convocatoria.
- Filtrar convocatorias y datos derivados por autoría, si se confirma esa regla.
- Definir qué ocurre cuando otra persona reemplaza al coordinador.

**Definición:** Ve solamente las convocatorias creadas por él que continúan bajo su responsabilidad.

## 18.2 Selecciona las localidades donde el territorial tomará datos

**Parte:** Backoffice + Mobile + Servidor/API.

**Cambio requerido en Backoffice:**

- Permitir seleccionar uno o más territoriales.
- Asignarles localidades/subsegmentos y relevamientos.
- Mostrar las asignaciones vigentes.

**Cambio requerido en Mobile:**

- Mostrar únicamente los relevamientos y localidades asignados.
- Impedir seleccionar una localidad diferente.

**Cambio requerido en Servidor/API:**

- Validar que territorial, localidad y relevamiento coincidan en cada formulario enviado.

## 18.3 Puede cargar datos

**Parte:** Backoffice o Mobile + Servidor/API.

**Definición:** Puede gestionar desde Backoffice y también operar por Mobile cuando recibe un relevamiento propio.

## 18.4 Crea solamente usuarios territoriales y no crea roles

**Parte:** Backoffice + Servidor/API.

**Cambio requerido:**

- Permitir crear usuarios sólo con rol Territorial.
- Asignarlos automáticamente a su región o alcance.
- Impedir acceso al ABM de roles.
- Impedir asignar roles superiores.

## 18.5 Sólo consulta datos de sus territoriales

**Parte:** Backoffice + Servidor/API.

**Cambio requerido:**

- Incorporar una relación explícita entre Coordinador regional y Territorial.
- Aplicar el filtro a relevamientos, personas, formularios, avances y reportes.

## Definición aplicada originalmente (posteriormente retirada)

- Es un rol nuevo.
- Una Región agrupa una o más localidades/subsegmentos.
- Ve y modifica solamente las convocatorias que creó y que conserva bajo su responsabilidad.
- Crea convocatorias y relevamientos dentro de las localidades de su Región.
- Crea y administra solamente Territoriales bajo su responsabilidad; no crea roles ni pausa elementos.
- Puede recibir relevamientos propios y operar la APK, además de su gestión en Backoffice.
- El Administrador puede transferir expresamente la responsabilidad a un reemplazante. Se transfieren convocatorias y Territoriales, pero el creador original y los datos históricos no cambian.

## Consultas resueltas para implementar

### Rol y alcance regional

1. ¿Coordinador regional es un rol nuevo o corresponde al Coordinador que ya existe?
2. ¿Qué representa una región en el sistema: un segmento, una localidad/subsegmento, un conjunto de localidades o una entidad nueva?
3. ¿Un Coordinador regional puede administrar más de una región?
4. ¿Quién asigna y reemplaza al Coordinador regional?

### Convocatorias y reemplazos

5. ¿Debe consultar solamente las convocatorias que creó o todas las correspondientes a su región?
6. Si otro Coordinador lo reemplaza, ¿hereda las convocatorias, relevamientos y Territoriales existentes?
7. ¿Puede editar una convocatoria creada por otro Coordinador de la misma región?

### Localidades y Territoriales

8. ¿Un Territorial puede trabajar en una o en varias localidades?
9. ¿La localidad se asigna permanentemente al Territorial o se elige para cada relevamiento?
10. ¿Puede haber varios Territoriales asignados simultáneamente a la misma localidad?
11. ¿El Coordinador puede cambiar la localidad de un relevamiento que ya tiene formularios cargados?
12. Si cambia una asignación, ¿qué ocurre con los relevamientos y datos ya registrados?

### Carga y consulta de datos

13. ¿El Coordinador regional carga personas desde el Backoffice, utiliza la APK como Territorial o puede usar ambos canales?
14. ¿“Sus Territoriales” son los usuarios que creó, los que le asignaron o todos los pertenecientes a su región?
15. ¿Qué información puede consultar de ellos: usuarios, relevamientos, formularios, avances, beneficiarios, cupos y reportes?
16. ¿Puede editar, desactivar y reasignar Territoriales o solamente crearlos y consultarlos?

**Estado final:** implementación retirada. El Punto 18 queda documentado únicamente como pedido original no vigente.

---

# Cambio 19 — Territorial

🟡 **PARCIALMENTE HECHO — CONTROL GPS PENDIENTE**

## 19.1 No debe acceder al portal DataÑach

🟢 **HECHO**

**Parte:** Backoffice + Mobile + Servidor/API.

**Estado actual:** El rol Territorial sembrado sólo tiene capacidad para operar la app de campo. La API comprueba esa capacidad.

**Cambio requerido:**

- Rechazar en el servidor el ingreso del usuario exclusivamente territorial al Backoffice.
- Mantener la APK como su canal operativo.
- Evitar depender solamente de ocultar el menú.

**Implementado:** El formulario de autenticación web rechaza al usuario que tiene exclusivamente la capacidad Territorial y le indica que debe ingresar desde la aplicación móvil. La autenticación por token de la APK continúa habilitada.

## 19.2 No puede tomar datos en otra localidad distinta de la seleccionada por el coordinador

🟡 **ASIGNACIÓN HECHA — CONTROL GPS CONFIRMADO Y PENDIENTE DE COMPLETAR**

**Parte:** Backoffice + Mobile + Servidor/API.

**Cambio requerido en Backoffice:** Asignar formalmente la localidad/subsegmento al territorial o relevamiento.

**Cambio requerido en Mobile:**

- Mostrar la localidad asignada sin permitir reemplazarla por otra.
- Permitir trabajo offline sólo sobre asignaciones previamente descargadas.

**Cambio requerido en Servidor/API:**

- Rechazar formularios enviados para una localidad no autorizada.
- Verificar la asignación nuevamente durante la sincronización.

**Definición confirmada:** Se debe validar por GPS que cada captura fue realizada físicamente dentro de la localidad asignada.

**Implementado:** La localidad proviene del subsegmento de la convocatoria asignada al relevamiento. Mobile la muestra como “Localidad asignada” y no ofrece un selector para reemplazarla. La API sólo permite operar relevamientos del Territorial autenticado y el formulario se crea dentro de ese relevamiento, por lo que Mobile no envía ni puede sustituir la localidad.

**Pendiente técnico:** Mobile ya obtiene y envía latitud/longitud, pero el servidor todavía debe exigirlas y validar que el punto pertenezca a la localidad. Para esta última comprobación se necesita una fuente oficial de límites geográficos de las localidades.

## 19.3 Especificar el cupo de cada relevador

🟢 **HECHO**

El documento aclara: “Creo que está”.

**Parte:** Backoffice + Mobile + Servidor/API.

**Implementado:** Cada relevamiento tiene un cupo propio. En Backoffice se muestra el avance y quienes pueden crear relevamientos pueden establecerlo o aumentarlo. Mobile muestra utilizado/máximo, cuenta también las capturas offline pendientes y bloquea nuevas personas al completarse. El servidor mantiene el conteo definitivo, serializa las cargas concurrentes y rechaza con un error específico las que excedan el límite.

**Cambio requerido en Backoffice:**

- Configurar el cupo individual.
- Mostrar asignado, utilizado y disponible.
- Definir quién puede modificarlo.

**Cambio requerido en Mobile:**

- Mostrar cupo y avance.
- Contabilizar formularios pendientes de sincronización.
- Bloquear nuevas altas al alcanzar el límite.

**Cambio requerido en Servidor/API:**

- Mantener el conteo definitivo.
- Rechazar cargas que superen el cupo.
- Resolver concurrencia y sincronizaciones tardías.

**Definiciones acordadas:**

1. El cupo pertenece a cada relevamiento.
2. Puede establecerlo o modificarlo todo usuario habilitado para crear relevamientos.
3. Cuenta toda persona relevada, independientemente de su aprobación.
4. Al completarse se bloquean nuevas cargas.
5. Las capturas offline pendientes ocupan cupo localmente.
6. El cupo puede aumentarse durante el relevamiento, pero no reducirse por debajo de la cantidad ya utilizada.

## Pendiente para completar el Cambio 19

- Completar en el servidor la validación GPS contra límites geográficos oficiales de localidades.

---

# Matriz consolidada por parte

| Punto original | Backoffice | Mobile | Servidor/API | Infra/ECOM |
|---|:---:|:---:|:---:|:---:|
| Cambio 1 — Recordarme | ✔ | — | ✔ | Configuración |
| Cambio 2 — Limpieza de datos de prueba | Apoyo | — | Procedimiento | ✔ |
| Cambio 3 — Becas → Programas | ✔ | ✔ | Ajustes | — |
| Cambio 4 — Nuevos tipos de usuario | ✔ | Territorial | ✔ | — |
| Cambio 5 — DNI, teléfono, institución y observación | ✔ | — | ✔ | — |
| Cambio 6 — Usuarios y roles dentro de Programas | ✔ | — | Permisos | — |
| Cambio 7 — Categoría Programa | ✔ | — | Migración | Ejecución |
| Cambio 8 — Cuatro programas | ✔ | Posible | ✔ | Carga/configuración |
| Cambio 9 — Localidades como subsegmentos | ✔ | ✔ | ✔ | Limpieza/carga |
| Cambio 10 — Fecha desde/hasta | ✔ | ✔ | ✔ | Migración |
| Cambio 11 — Domicilio actual | ✔ | A confirmar | ✔ | — |
| Cambio 12 — Bug de búsqueda de legajo | ✔ | — | ✔ | — |
| Cambio 13 — Correo de alta | ✔ | — | ✔ | ✔ |
| Cambio 14 — Sesión única | ✔ | — | ✔ | — |
| Cambio 15 — Administrador de programa | ✔ | — | ✔ | — |
| Cambio 16 — Coordinador de segmento | ✔ | — | ✔ | — |
| Cambio 17 — Referente | ✔ | — | ✔ | — |
| Cambio 18 — Coordinador regional | ✔ | ✔ | ✔ | — |
| Cambio 19 — Territorial | ✔ | ✔ | ✔ | — |

---

# Funcionalidad existente que debe reutilizarse

- ABM de segmentos y subsegmentos.
- Convocatorias con fecha de inicio y fin.
- Relevamientos asignados a un territorial y una fecha.
- API que filtra relevamientos por el territorial autenticado.
- Roles Administrador, Coordinador y Territorial con capacidades de programa.
- Alcance del Coordinador por segmento.
- ABM de usuarios y roles con alcance de programa.
- Domicilio, provincia, municipio y localidad del ciudadano.
- Cupo por segmento.
- Revisión de formularios.
- APK con almacenamiento offline y sincronización.

Antecedentes principales en GitHub: #66, #67, #69, #70, #73, #74, #75, #76, #79, #82 y #85.

---

# Impacto crítico

- Eliminar subsegmentos puede afectar convocatorias, requisitos y formularios vinculados.
- Cambiar de una fecha única a un período modifica Backoffice, modelos, API, APK, filtros, estados y sincronización offline.
- El cupo individual puede quedar inconsistente si existen formularios sin sincronizar o credenciales compartidas.
- Una sesión única puede impedir sincronizar trabajo pendiente si no se diseña específicamente para Mobile.
- Renombrar códigos técnicos de Becas puede romper permisos, rutas y migraciones; debe diferenciarse del cambio de textos visibles.
- Los roles Referente y Coordinador regional necesitan nuevas relaciones de alcance. Ocultar botones no resuelve la seguridad.
- La limpieza de datos necesita identificación funcional, respaldo y procedimiento de reversión.

---

# Preguntas necesarias para cerrar el análisis

1. ¿“Programas” es sólo un cambio de nombre o cada programa tendrá un circuito independiente?
2. ¿Administrador del programa, Coordinador general del programa y Coordinador del segmento son roles distintos?
3. ¿Cuál es la jerarquía exacta entre Administrador, Referente, Coordinador regional, Coordinador del segmento y Territorial?
4. ¿Cada subsegmento será obligatoriamente una localidad oficial?
5. ¿Qué subsegmentos y demás registros son datos de prueba?
6. **Resuelta:** La fecha desde/hasta corresponde a cada relevamiento y debe quedar dentro de su convocatoria.
7. **Resuelta:** Al vencer el período se bloquean nuevas cargas y sincronizaciones; el registro conserva su estado para gestión desde Backoffice.
8. **Resuelta:** El cupo es por relevamiento y cuenta toda persona cargada, incluida la captura offline pendiente.
9. ¿Qué usuarios puede crear el Coordinador del segmento y el Referente?
10. ¿El Coordinador regional carga datos desde Backoffice, desde la APK o desde ambos?
11. ¿El Referente ve datos por segmento, región, programa o asignación directa de usuarios?
12. ¿Un territorial puede tener varias localidades o programas simultáneamente?
13. ¿DNI, teléfono, institución, observación y domicilio actual son obligatorios?
14. ¿Ante un segundo inicio se rechaza el acceso nuevo o se cierra la sesión anterior?
15. ¿Cuál es un ejemplo reproducible del bug de búsqueda de legajos?

Hasta resolver estas preguntas, el análisis permanece en estado **En análisis** y no corresponde ejecutar limpiezas ni crear tareas definitivas.
