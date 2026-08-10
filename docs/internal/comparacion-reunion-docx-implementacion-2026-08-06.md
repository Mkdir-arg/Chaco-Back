# Comparación entre reunión, DOCX e implementación — DataÑach

**Reunión analizada:** 6 de agosto de 2026, 13:51 (transcripción y resumen de Gemini)  
**Pedido formal:** `Cambios en DataÑach (1).docx`  
**Implementación contrastada:** rama `fixes-31-07` y registro interno al 7 de agosto de 2026

## Criterio de lectura

La transcripción contiene ideas exploratorias, correcciones durante la conversación y algunas contradicciones. El DOCX fue enviado después como punteo formal y mantiene la numeración de los 19 cambios. Cuando el DOCX y la reunión difieren, este documento no inventa una decisión: marca el punto para confirmar.

## Resultado ejecutivo

- La mayoría de las correcciones visuales y operativas implementadas coinciden con la reunión y el DOCX.
- Los puntos **6 y 8** fueron retirados de las definiciones pendientes por decisión posterior. Los puntos **17 y 18** conservan las observaciones de alcance surgidas del cruce documental.
- El punto **9** coincide con la decisión final de la reunión: la subdivisión interna se identifica en el nombre de la convocatoria, manteniendo el subsegmento como localidad.
- La reunión agrega temas que no forman parte de los 19 puntos: conectividad/certificado, pasaje `test` → `main`, prebeneficiarios SIIS y futura publicación en Play Store.

## Comparación punto por punto

| Punto | Lo tratado en la reunión | Lo solicitado en el DOCX | Lo realizado | Evaluación |
|---:|---|---|---|---|
| 1 | “Recordarme” no persistía. | Corregir Recordarme. | Sesión recordada por 24 horas cuando se marca. | **Coincide.** |
| 2 | Limpiar segmentos, relevamientos y revisiones de prueba; conservar requisitos generales. | Quitar usuarios y datos de prueba. | No se ejecutó una eliminación; quedó señalado para base de test con respaldo. | **Pendiente operativo.** La reunión acota mejor qué borrar. |
| 3 | Cambiar la denominación Becas por Programas. | Reemplazar Becas por Programas. | Se cambió el texto del menú lateral. | **Parcial respecto del texto literal**, pero coincide con la decisión posterior tomada durante el trabajo. |
| 4 | Jerarquía Administrador, Coordinador de programa, su mano derecha, Coordinador regional/director y Territorial. | Revisar tipos de usuario. | Se formalizaron Administrador, Coordinador de segmento, Referente, Coordinador regional y Territorial. | **Coincide en perfiles**, con diferencias de nombres que deben validarse. |
| 5 | No surge como definición central de la reunión. | Agregar DNI, teléfono, institución y observación. | Campos agregados como opcionales; asteriscos en los actualmente obligatorios. | **Coincide con DOCX.** |
| 6 | Llevar Usuarios y Roles dentro de Programas y dividir permisos: administrar usuarios no debe implicar administrar roles. | Poner Usuarios y Roles dentro de Programas. | Alta contextual mediante modales, asignación directa y permisos separados; se conservaron los ABM generales. | **Parcial.** Los modales resuelven el alta contextual, pero no reproducen literalmente una sección completa de Usuarios y Roles dentro de Programas. |
| 7 | Los roles deben quedar limitados al programa correspondiente y no exponer otros módulos. | Quitar categoría Becas y dejar Programa. | Se retiró Becas del selector y se aplicaron alcances/permisos. | **Coincide.** |
| 8 | Se eligió filtrar localmente los cuatro programas recibidos desde SIIS para no depender del cambio de ECOM. | Incorporar Mamá Ñachec, Futuro Joven, Segmento FE y Mi Casa Ñachec; consta que se escribió a ECOM. | El selector continúa consumiendo el catálogo activo de SIIS y el punto quedó atribuido a ECOM. | **No coincide con la decisión de la reunión.** Falta el filtro local de los cuatro nombres/IDs, salvo que ECOM ya entregue exclusivamente esos cuatro. |
| 9 | Subsegmento = localidad. Para barrios, escuelas o divisiones internas se acordó usar el nombre de la convocatoria. | Reemplazar subsegmentos por localidades. | Se decidió identificar la subdivisión en el título de la convocatoria; además Región usa localidades/subsegmentos. | **Coincide con la decisión final de la reunión.** Falta disponer del catálogo real de localidades si SIIS no lo provee. |
| 10 | Relevamiento con fecha desde/hasta, incluso para un solo día, dentro del período de convocatoria. | Incorporar rango de fechas. | Implementado en Backoffice, API y Mobile con validación contra la convocatoria. | **Coincide.** |
| 11 | No aparece como definición relevante en las notas. | Aclarar domicilio actual. | Etiqueta y visualización ajustadas. | **Coincide con DOCX.** |
| 12 | El buscador de DNI quedaba cortado debajo del layout. | Corregir desplegable de búsqueda, especialmente en Mac. | Contenedor, scroll y paginación/listado amplio corregidos. | **Coincide.** Conviene validar en la Mac/navegador original. |
| 13 | No aparece como acuerdo central. | Enviar correo al crear usuario. | Flujo implementado; pendiente configuración SMTP de ECOM. | **Coincide con DOCX, pendiente Infraestructura.** |
| 14 | No aparece como acuerdo central. | Impedir sesiones simultáneas. | Implementado para Backoffice; Mobile no se invalida. | **Coincide con la definición posterior.** |
| 15 | Administrador de Programas con control total; los niveles inferiores no deben pausar. | Administrador crea usuarios/roles y puede pausar. | Capacidades y pausas auditadas implementadas. | **Coincide.** |
| 16 | Coordinador de programa limitado a su segmento: crea usuarios, no roles, no pausa y consulta lo designado. | Coordinador del segmento con esas restricciones. | Implementado por segmentos asignados. | **Coincide en lo principal.** La reunión dice por momentos “territoriales que crea/designa”; el sistema aplica alcance por segmento, que puede incluir Territoriales creados por otro operador. |
| 17 | Referente como mano derecha del Coordinador de programa; no pausa, crea usuarios pero no roles y consulta información limitada. | Perfil Referente con esas restricciones. | Depende de un Coordinador y hereda todos sus segmentos; administra Territoriales del alcance heredado. | **Parcialmente alineado.** Falta confirmar si debe ver todos los Territoriales del segmento o solamente los creados/designados por su jerarquía. |
| 18 | Coordinador regional = director de escuela; asociado a un subsegmento/localidad, crea profesores/Territoriales, recibe y acepta/rechaza encuestas y sólo ve su localidad. En otro tramo se dice que puede cargar datos y luego que no debería cargar nada. | Ve su convocatoria, selecciona localidades, puede cargar, crea sólo Territoriales y consulta sus datos. | **Retirado el 10/08/2026:** se eliminaron el rol Coordinador regional y el módulo Regiones. | **Fuera del alcance vigente por decisión funcional posterior.** |
| 19 | Territorial/profesor usa solamente la APK y toma encuestas en su aula/localidad. | Sin Backoffice, sin operar fuera de localidad y con cupo individual. | Acceso web bloqueado; Mobile y localidad/relevamiento validados; cupo por relevamiento implementado en Backoffice, Mobile y API; Mobile captura coordenadas. | **Parcial:** el cupo quedó resuelto; el control GPS fue confirmado, pero falta exigirlo y comprobar pertenencia a la localidad. |

## Diferencias que necesitan una decisión

### Puntos 17 y 18 — jerarquía y propiedad

Hay que confirmar tres reglas antes de considerar definitivamente aceptados ambos perfiles:

1. Si Referente/Coordinador visualizan todos los Territoriales del segmento o solamente los que crearon o les asignaron.

## Temas de la reunión fuera de los 19 puntos

| Tema | Definición de la reunión | Estado observado |
|---|---|---|
| Conectividad y certificado | Infraestructura debe resolver el acceso de la APK sin VPN. | Se hicieron pruebas y se usó una solución temporal en la app; la corrección definitiva corresponde a Infraestructura/cadena de certificados. |
| Producción | Tras estabilizar test, fusionar `test` a `main` y realizar estrés/seguridad. | No forma parte de estos cambios locales ni debe ejecutarse sin coordinación con DevOps. |
| Validación SIIS | Enviar DNI + ID de programa; conservar resultado y motivos de rechazo. | Dependiente del endpoint/documentación final de ECOM. |
| Prebeneficiarios | DataÑach envía validados a una tabla intermedia; un operador SIIS realiza la aprobación final. | Endpoint externo pendiente de ECOM; no debe pasarse directamente a beneficiario. |
| Distribución Android | Evaluar publicación en Play Store ante futuras restricciones a APK instaladas por URL. | Riesgo futuro separado de la funcionalidad actual. Requiere cuenta, firma y plan de publicación. |

## Conclusión

Por decisión posterior, los puntos 2, 6, 8 y 13 se retiraron del listado de definiciones pendientes. No conviene dar por aceptados sin consulta los alcances observados en 17 y 18. En el punto 19 el cupo ya está implementado y el control GPS está definido; queda completar su validación geográfica técnica.
