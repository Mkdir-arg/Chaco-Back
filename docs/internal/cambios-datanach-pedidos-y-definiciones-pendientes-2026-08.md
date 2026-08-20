# Cambios DataÑach — pedidos y definiciones pendientes

**Documento de origen:** `Cambios en DataÑach (1).docx`  
**Fecha de revisión:** 7 de agosto de 2026  
**Objetivo:** relacionar cada punto del DOCX con el cambio solicitado y registrar las respuestas que todavía se necesitan.

> El DOCX no contiene números impresos. La numeración 1 a 19 es la normalización que usamos, respetando estrictamente el orden de aparición de los pedidos. Los puntos 7 y 8 separan dos pedidos que aparecen juntos en un mismo párrafo del DOCX: categoría de rol y alta de programas. Este archivo no reemplaza el análisis funcional ni el registro de implementación.

**Verificación de fuente:** contenido textual del DOCX revisado nuevamente luego de cerrar el archivo; se confirmaron los 19 temas y los subpuntos de los roles Administrador, Coordinador, Referente, Coordinador regional y Territorial.

## Referencias relacionadas

- Análisis funcional completo: `docs/internal/analisis-funcional-cambios-datanach-2026-08.md`
- Registro de cambios realizados: `docs/internal/requerimientos.md` (archivo vivo de requerimientos)

## Resumen de pedidos y definiciones

| Referencia en el DOCX | Cambio solicitado | Definición o confirmación pendiente |
|---|---|---|
| **Punto 1 — Revisar “Recordarme” porque no funciona** | Hacer que el Backoffice recuerde la sesión cuando el usuario marque la opción. | **Resuelto:** se definió una duración de 24 horas. Sin marcarlo, la sesión termina al cerrar el navegador. |
| **Punto 2 — Quitar usuarios y datos de prueba** | Limpiar la información utilizada durante las pruebas. | **Fuera del listado de definiciones pendientes por decisión actual.** Se conserva únicamente la trazabilidad del pedido original. |
| **Punto 3 — Reemplazar “Becas” por “Programas”** | Cambiar la denominación visible del módulo. | **Resuelto:** se acordó cambiar solamente el texto del menú lateral. No implica cambiar rutas, permisos, API ni APK. |
| **Punto 4 — Revisar los tipos de usuarios de esta etapa** | Adecuar los perfiles a Administrador/Coordinador general, Coordinador del segmento, Referente, Coordinador regional y Territorial. | **Definición actualizada:** quedan Administrador, Coordinador del segmento, Referente y Territorial. Se decidió retirar el Coordinador regional. Coordinador general y Administrador son el mismo rol. |
| **Punto 5 — Agregar datos al crear usuarios** | Incorporar DNI, teléfono, institución y observación. | Confirmar cuáles deben ser obligatorios y si los usuarios existentes deben completarlos. Actualmente son opcionales. |
| **Punto 6 — Poner Usuarios y Roles dentro de Programas** | Ubicar la gestión de usuarios y roles dentro del sector Programas. | **Resuelto:** se incorporó el alta contextual de usuarios mediante modales, con selección/asignación directa y roles limitados por permisos. No se duplicaron los ABM por programa. |
| **Punto 7 — Quitar la categoría “Becas” y dejar “Programa”** | Utilizar Programa como categoría de los roles. | **Sin definiciones pendientes.** La categoría Becas fue retirada del selector. |
| **Punto 8 — Incorporar programas** | Incorporar **MAMÁ ÑACHEC, FUTURO JÓVEN, SEGMENTO FE y MI CASA ÑACHEC** al selector integrado con SIIS. En el DOCX sigue la aclaración “Ya se le escribió el email a ECOM”. | **Fuera del listado de definiciones pendientes por decisión actual.** Se conserva únicamente la trazabilidad del pedido original. |
| **Punto 9 — Reemplazar subsegmentos por localidades de Chaco** | Permitir trabajar con localidades en lugar de los subsegmentos actuales. | **Decisión provisoria:** identificar la localidad en el título de la convocatoria. Si se retoma el cambio estructural, definir fuente oficial del catálogo, relación con segmentos/programas y cupos por localidad. |
| **Punto 10 — Fecha del relevamiento desde/hasta** | Permitir relevamientos de uno o varios días dentro de la convocatoria. | **Sin definiciones pendientes.** Las fechas deben permanecer dentro del período de la convocatoria. |
| **Punto 11 — Domicilio actual del ciudadano** | Identificar expresamente el domicilio cargado como domicilio actual. | **Sin definiciones pendientes.** Se conserva la estructura existente de domicilio. |
| **Punto 12 — Bug al buscar un legajo** | Evitar que los resultados del buscador se extiendan fuera de la pantalla, especialmente en Mac. | **Sin definiciones funcionales pendientes.** Conviene validar visualmente en el navegador utilizado por el usuario de Mac. |
| **Punto 13 — Notificar por correo al crear un usuario** | Enviar al nuevo usuario un correo para establecer su contraseña. | **Fuera del listado de definiciones pendientes por decisión actual.** La implementación realizada permanece registrada. |
| **Punto 14 — Impedir sesiones simultáneas** | Evitar que un mismo usuario mantenga dos sesiones web activas. | **Sin definiciones pendientes.** El ingreso web más reciente reemplaza la sesión web anterior; la sesión de la APK no se incluye. |
| **Punto 15 — Administrador del programa** | Permitir crear usuarios y roles y pausar cualquier sector, segmento, subsegmento y relevamiento. El DOCX agrega “Creo que ya lo hace, pero chequeo”. | **Sin definiciones pendientes para lo implementado.** Se interpretó “sector” como convocatoria y se agregó auditoría. |
| **Punto 16 — Coordinador del segmento** | Permitir crear Territoriales, impedir crear roles o pausar y limitar la consulta a sus segmentos. | **Sin definiciones pendientes para lo implementado.** |
| **Punto 17 — Referente** | Crear un perfil que ayude al Coordinador, cree usuarios sin crear roles, no pause y consulte solamente información bajo su responsabilidad. | **Resuelto:** depende de un Coordinador del segmento y administra Territoriales dentro del alcance heredado. |
| **Punto 18 — Coordinador regional** | Gestionar convocatorias, localidades y Territoriales de una región; crear solamente Territoriales y consultar sus datos. | **Retirado por decisión funcional del 10/08/2026:** no se conservarán el rol Coordinador regional ni el módulo Regiones. |
| **Punto 19 — Territorial** | Restringirlo a la APK y a la localidad/subsegmento seleccionado por el Coordinador, y especificar el cupo de cada relevador. El DOCX aclara sobre el cupo: “Creo que está”. | El acceso, la localidad y el cupo por relevamiento están resueltos. El cupo cuenta toda persona, bloquea nuevas cargas al completarse, incluye pendientes offline, puede aumentarse y no puede reducirse por debajo de lo utilizado. **Se confirmó el control GPS**; falta completar únicamente la validación geográfica en servidor. |

## Punto 17 del DOCX — Referente

### Pedido original relacionado

- **17.1:** no puede detener ni pausar el segmento.
- **17.2:** crea usuarios, pero no roles.
- **17.3:** solamente consulta datos de sus coordinadores generales y territoriales.

### Preguntas respondidas para la implementación

1. ¿El Referente pertenece a un programa completo, a un segmento o a un Coordinador específico?
2. ¿Puede estar relacionado con más de un Coordinador o segmento?
3. ¿Quién lo asigna y desasigna?
4. ¿Qué rol real representa la expresión “coordinador general”?
5. ¿Puede crear solamente Territoriales o también Coordinadores y Referentes?
6. ¿Puede editar, desactivar, reasignar o restablecer el acceso de los usuarios que administra?
7. ¿Puede consultar datos personales de los Coordinadores o solamente información operativa de los Territoriales?
8. ¿Qué pantallas puede consultar: usuarios, convocatorias, relevamientos, formularios, revisión, cupos, beneficiarios y reportes?
9. ¿Puede crear o modificar convocatorias y relevamientos?
10. Si un Territorial cambia de segmento o Coordinador, ¿deja de estar visible para el Referente anterior?

## Punto 18 del DOCX — Coordinador regional

> **Decisión posterior (10/08/2026):** este punto quedó fuera del alcance. Se retiraron el rol, la entidad Región, su pantalla, asignaciones, transferencias y filtros asociados.

### Pedido original relacionado

- **18.1:** solamente ve datos de la convocatoria que creó.
- **18.2:** selecciona las localidades donde el Territorial tomará datos.
- **18.3:** puede cargar datos.
- **18.4:** crea solamente usuarios Territoriales y no crea roles.
- **18.5:** solamente consulta datos de sus Territoriales.

### Preguntas respondidas para la implementación

1. ¿Es un rol nuevo o corresponde al Coordinador actual?
2. ¿Región significa segmento, localidad/subsegmento, conjunto de localidades o una entidad nueva?
3. ¿Puede administrar más de una región?
4. ¿Quién lo asigna, desasigna y reemplaza?
5. ¿Ve solamente las convocatorias que creó o todas las de su región?
6. Ante un reemplazo, ¿se transfieren convocatorias, relevamientos y Territoriales?
7. ¿Puede editar convocatorias creadas por otro Coordinador de la misma región?
8. ¿Un Territorial puede trabajar en varias localidades?
9. ¿La localidad se asigna permanentemente al Territorial o en cada relevamiento?
10. ¿Puede haber varios Territoriales trabajando en la misma localidad?
11. ¿Puede cambiarse la localidad de un relevamiento que ya contiene formularios?
12. Si cambia una asignación, ¿qué ocurre con los datos anteriores?
13. ¿Carga personas desde el Backoffice, desde la APK o desde ambos?
14. ¿“Sus Territoriales” son los que creó, los que le asignaron o todos los de su región?
15. ¿Qué datos puede consultar de esos Territoriales?
16. ¿Puede editarlos, desactivarlos y reasignarlos o solamente crearlos y consultarlos?

## Punto 19 del DOCX — Territorial

### Pedido original relacionado

- **19.1:** no debe acceder al portal DataÑach.
- **19.2:** no puede tomar datos en una localidad distinta de la seleccionada por el Coordinador.
- **19.3:** especificar el cupo de cada relevador.

### Preguntas que deben responderse

**Definición confirmada:** Cada captura debe controlarse mediante GPS para verificar que fue realizada físicamente dentro de la localidad asignada.

Preguntas que permanecen abiertas solamente sobre el cupo:

1. ¿El cupo individual es diario, por relevamiento, por convocatoria o por programa?
2. ¿Quién establece y modifica el cupo?
3. ¿Se cuentan personas cargadas, formularios finalizados o solamente formularios aprobados?
4. ¿Las capturas pendientes de sincronización reservan cupo inmediatamente en la tablet?
5. Si varias tablets sincronizan y superan el cupo, ¿se rechazan las últimas cargas o pasan a una lista pendiente?
6. Al alcanzar el cupo, ¿se bloquea la captura o se permite continuar con una advertencia?
7. ¿Puede aumentarse el cupo cuando el relevamiento ya está en curso?

## Puntos retirados de definiciones pendientes

Por decisión actual se retiraron de este listado los puntos **2, 6, 8 y 13**. Sus pedidos originales y cualquier implementación realizada se conservan en la tabla y en el registro para mantener trazabilidad.

## Criterio para continuar

- Los puntos sin definiciones pendientes pueden pasar a verificación integral.
- Los puntos 17 y 18 quedaron definidos e implementados; cualquier cambio posterior de jerarquía requiere revisar migración, permisos y filtros.
- El punto 19 puede conservar lo ya implementado; el cupo individual debe esperar una definición funcional completa.
- Las tareas de ECOM/Infraestructura deben validarse en el entorno de test antes de habilitar producción.
