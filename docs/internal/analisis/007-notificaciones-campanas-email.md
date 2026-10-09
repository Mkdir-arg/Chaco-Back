# Análisis funcional 007 — Notificaciones: campañas de email masivo

**Estado:** Definido
**Fecha de análisis:** 2026-10-08
**Analista:** functional-analyst (sesión con el PM)
**Sprint asociado:** Sin asignar
**Módulo/App:** app nueva `notificaciones` (backoffice)
**Mock-ups:** lienzo de Claude Design «Notificaciones · Campañas de email» (https://claude.ai/artifact/PXnf1gJJScWQvpww6ALWVz)

---

## 1. Contexto y motivación

Hoy DATAÑACH manda correos uno a uno y siempre como efecto de una acción del dominio: las
credenciales al dar de alta un usuario (Cambio 37), el comprobante de inscripción por link
(Cambio 41) y el aviso de resolución del caso (Cambio 44). No hay forma de que el equipo
del programa le escriba a un grupo de personas por fuera de esos disparadores, por ejemplo
para avisar la apertura de una convocatoria, recordar un vencimiento o comunicar una
novedad a una lista armada en otra herramienta.

El pedido es un módulo nuevo, **Notificaciones**, donde un operador arma una **campaña**:
le pone un nombre, sube un Excel con la lista de correos, escribe el asunto y sube el
cuerpo del correo como un archivo HTML ya diseñado. Antes de enviar, el sistema muestra una
previsualización con todos los destinatarios, el total y el correo tal como le va a llegar
a la persona. La campaña queda en estado **A enviar** hasta que alguien aprieta **Enviar**.

El nombre «notificaciones» está libre en el código, pero convive con dos cosas que se
llaman parecido y no son esto: las alertas en tiempo real de la campana del navbar
(`legajos/services/alertas.py`) y `NotificacionService` de conversaciones (WebSocket). El
módulo nuevo es solo correo saliente.

---

## 2. Actores involucrados

| Actor | Rol en el sistema | Qué puede hacer en esta funcionalidad |
|---|---|---|
| Operador de comunicaciones | Rol nuevo **Comunicaciones** (categoría global, sembrado con las tres capacidades) | Ver el listado, crear, editar, eliminar y duplicar campañas, mandar pruebas, enviar y detener |
| Responsable de envío | Cualquier rol al que se le tilde `notificacion.enviar` | Disparar el envío de una campaña en «A enviar» y cancelarla mientras se envía |
| Consulta | Usuario con solo `notificacion.ver` | Ver campañas, su previsualización y el resultado por destinatario |
| Destinatario | Persona externa, sin usuario | Recibe el correo |
| Administrador | Rol Administrador (`seed_rbac`) | Todo lo anterior, por asignación automática de capacidades |

Se separa **enviar** de **gestionar** a propósito: el envío es irreversible y conviene poder
dárselo a menos gente que el armado.

---

## 3. Descripción funcional

### Flujo principal

1. El usuario entra a **Notificaciones › Campañas** desde el sidebar (grupo nuevo, ícono de
   sobre). Ve el listado de campañas con nombre, asunto, destinatarios, estado, fecha y
   quién la creó, más métricas arriba (campañas a enviar, enviadas en el mes, correos
   enviados en el mes) y filtros por estado y texto.
2. Aprieta **Nueva campaña** y completa el formulario:
   - **Nombre** (interno, no lo ve el destinatario).
   - **Asunto** (lo ve el destinatario).
   - **Lista de destinatarios**: archivo `.xlsx`.
   - **Cuerpo del correo**: archivo `.html`.
   El formulario muestra el formato esperado del Excel y permite bajar una plantilla.
3. Al guardar, el sistema valida los dos archivos, lee el Excel, normaliza y deduplica los
   correos, descarta los inválidos, sanitiza el HTML y crea la campaña en estado
   **A enviar**. Redirige a la previsualización.
4. En la **previsualización** (detalle de la campaña) el usuario ve:
   - Métricas: **total de destinatarios** a enviar, filas leídas, inválidos descartados y
     duplicados descartados.
   - Solapa **Vista previa**: el correo renderizado tal como llega (remitente, asunto con
     el prefijo del ambiente, cuerpo HTML), en un marco aislado del backoffice, con
     conmutador escritorio / móvil.
   - Solapa **Destinatarios**: tabla paginada y con búsqueda de todos los correos que se
     van a enviar.
   - Solapa **Descartados**: fila del Excel, valor leído y motivo (formato inválido,
     duplicado, vacío).
   - Acciones: **Editar**, **Eliminar**, **Duplicar**, **Enviar prueba** y **Enviar**.
5. El usuario aprieta **Enviar**. Un modal de confirmación repite el asunto y el total
   («Se van a enviar 4.812 correos. Esta acción no se puede deshacer.») y pide confirmar.
6. Al confirmar, la campaña pasa a **Enviando**, se registra quién y cuándo la envió y el
   envío corre en segundo plano. La pantalla muestra el avance (enviados / fallidos /
   pendientes) y se refresca sola.
7. Al terminar, la campaña queda **Enviada** (todos salieron) o **Enviada con errores**
   (alguno falló). La solapa Destinatarios muestra el resultado por correo y se puede
   descargar el resultado en Excel.

### Flujos alternativos

**Archivo con errores al crear**
- Condición: el Excel no es `.xlsx`, supera el tamaño, no tiene la columna de correo, o no
  queda ningún correo válido; o el HTML no es `.html`, supera el tamaño o no es UTF-8.
- Comportamiento: no se crea la campaña; el formulario vuelve con el error en el campo.

**Editar antes de enviar**
- Condición: campaña en «A enviar».
- Comportamiento: se puede cambiar nombre y asunto y reemplazar cualquiera de los dos
  archivos; al reemplazar el Excel se recalcula la lista completa.

**Eliminar**
- Condición: campaña en «A enviar».
- Comportamiento: confirmación sí/no; se borra la campaña, sus destinatarios y sus archivos.
  Una campaña enviada o enviándose no se puede eliminar.

**Cancelar un envío en curso**
- Condición: campaña en «Enviando».
- Comportamiento: botón **Detener envío** con confirmación; los correos ya enviados quedan
  enviados, los pendientes quedan sin enviar y la campaña pasa a **Cancelada**.

**Envío interrumpido** (redeploy o caída del proceso)
- Condición: la campaña está en «Enviando» pero el proceso dejó de dar señales de vida.
- Comportamiento: la pantalla lo muestra como interrumpido y ofrece **Reanudar**, que
  sigue solo con los pendientes. Nunca se reenvía a quien ya recibió.

**Enviar una prueba**
- Condición: campaña en «A enviar», usuario con `notificacion.gestionar`.
- Comportamiento: el botón **Enviar prueba** abre un popup que pide **un correo** (precargado
  con el del usuario logueado, editable; cualquier dominio, no solo Gmail). Al confirmar se
  manda el correo de la campaña **solo a esa dirección**, con el asunto precedido de
  «[PRUEBA] ». No cambia el estado de la campaña ni cuenta como envío; queda registrada
  (quién, a qué correo, cuándo) y se avisa con un toast si salió o falló.

**Duplicar**
- Condición: cualquier campaña, en cualquier estado.
- Comportamiento: **Duplicar** crea una campaña nueva en «A enviar» con nombre «Copia de
  <nombre>», el mismo asunto, el mismo HTML y la misma lista (se copian los dos archivos y
  se vuelve a leer el Excel). Lleva a la pantalla de edición de la copia. La original no
  cambia.

---

## 4. Requerimientos

### Requerimientos funcionales

| ID | Requerimiento | Prioridad | Notas |
|---|---|---|---|
| RF-007-01 | Existe el grupo **Notificaciones** en el sidebar con el ítem **Campañas**, visible con `notificacion.ver` | Alta | Grupo nuevo, después de Reportes |
| RF-007-02 | Listado de campañas paginado (25), con filtros por estado y búsqueda por nombre/asunto | Alta | Arquetipo Listado |
| RF-007-03 | Alta de campaña con nombre, asunto, Excel `.xlsx` y HTML `.html`, todos obligatorios | Alta | Arquetipo Formulario |
| RF-007-04 | Al guardar, se lee el Excel, se normalizan, validan y deduplican los correos y se persiste un destinatario por correo válido | Alta | Ver RN-02 a RN-05 |
| RF-007-05 | Se persisten los descartados con fila, valor y motivo | Media | Para la solapa Descartados |
| RF-007-06 | La campaña creada queda en estado **A enviar** | Alta | |
| RF-007-07 | Previsualización con total, métricas de lectura, vista previa del correo y lista completa de destinatarios | Alta | Arquetipo Detalle con solapas |
| RF-007-08 | La vista previa muestra remitente, asunto (con prefijo de ambiente) y cuerpo HTML en un marco aislado, con vista escritorio y móvil | Alta | `iframe sandbox` + `srcdoc` |
| RF-007-09 | Botón **Enviar** con confirmación que muestra total y asunto; solo con `notificacion.enviar` y estado «A enviar» | Alta | Arquetipo Confirmación |
| RF-007-10 | El envío corre en segundo plano y la campaña pasa a «Enviando» con avance visible | Alta | |
| RF-007-11 | Se registra el resultado por destinatario: enviado (fecha) o fallido (error) | Alta | |
| RF-007-12 | Estado final «Enviada» o «Enviada con errores» según haya fallidos | Alta | |
| RF-007-13 | Editar y eliminar solo en «A enviar» | Alta | |
| RF-007-14 | Detener un envío en curso → «Cancelada» | Media | |
| RF-007-15 | Reanudar un envío interrumpido, solo con los pendientes | Media | |
| RF-007-16 | Descargar el resultado por destinatario en Excel | Baja | |
| RF-007-17 | Plantilla Excel descargable desde el formulario | Baja | |
| RF-007-18 | **Enviar prueba**: popup que pide un correo y manda la campaña solo a esa dirección con «[PRUEBA] » en el asunto | Alta | Decidido 08/10 |
| RF-007-19 | **Duplicar** una campaña en cualquier estado → copia en «A enviar» con «Copia de …» | Media | Decidido 08/10 |

### Requerimientos no funcionales

| ID | Requerimiento | Categoría |
|---|---|---|
| RNF-007-01 | Capacidades nuevas en el `CATALOGO` de `core/rbac.py`, módulo global `notificaciones`: `notificacion.ver`, `notificacion.gestionar`, `notificacion.enviar`; migración `AlterModelOptions` en `users`, rol nuevo **Comunicaciones** con las tres, y `seed_rbac` | Seguridad |
| RNF-007-02 | Los archivos subidos se guardan en `media/notificaciones/` con nombre UUID y se sirven solo detrás de login | Seguridad |
| RNF-007-03 | El HTML se sanitiza al subirlo (sin `<script>`, manejadores `on*`, `<iframe>`, `<form>`, `javascript:`); se agrega `nh3` a requirements | Seguridad |
| RNF-007-04 | La vista previa nunca inyecta el HTML en la página del backoffice: va en `iframe` con `sandbox` vacío y `srcdoc` | Seguridad |
| RNF-007-05 | El envío reutiliza una sola conexión SMTP por lote (`get_connection()`), en lotes con pausa configurables por entorno (`NOTIF_LOTE`, `NOTIF_PAUSA_SEG`). La cuota del SMTP de ECOM no se conoce y el PM decidió no esperarla: se arranca con valores conservadores (50 correos cada 10 s) y se ajustan por variable de entorno sin release | Performance |
| RNF-007-06 | El envío no corre en el request: hilo de fondo con latido, sobre el patrón de `programas/services/proceso_masivo.py` + `CorridaSiis` | Performance / Robustez |
| RNF-007-07 | Un candado impide dos envíos simultáneos de la misma campaña | Robustez |
| RNF-007-08 | Cada correo sale **individual** (un destinatario en `To`), nunca en CC/BCC masivo | Privacidad |
| RNF-007-09 | Se respeta `EMAIL_ASUNTO_PREFIJO`: en QA el asunto lleva `[QA] ` | Operación |
| RNF-007-10 | Lectura del Excel con `openpyxl` en `read_only`, sobre el patrón de `parsear_padron` | Performance |
| RNF-007-11 | Funciona igual en MySQL 8 y MariaDB (sin `Trunc*` sobre `DateTimeField`, sin `UUIDField` en `char(32)`) | Compatibilidad |

---

## 5. Reglas de negocio

| ID | Regla | Consecuencia si no se cumple |
|---|---|---|
| RN-007-01 | Estados: **A enviar → Enviando → Enviada / Enviada con errores / Cancelada**. No hay vuelta atrás desde «Enviando» | Transición rechazada |
| RN-007-02 | El Excel es `.xlsx`, hasta 2 MB, primera hoja; el correo se toma de la columna con encabezado `email` (sin distinguir mayúsculas ni acentos: `email`, `correo`, `mail`); si no hay encabezado reconocible, de la columna A | Error en el campo |
| RN-007-03 | Cada correo se recorta, se pasa a minúsculas y se valida con `EmailValidator` de Django | Va a Descartados con motivo «formato inválido» |
| RN-007-04 | Correos repetidos cuentan una sola vez (comparación en minúsculas) | Va a Descartados con motivo «duplicado» |
| RN-007-05 | Tope de destinatarios por campaña: **5.000** correos válidos | Error en el campo del Excel |
| RN-007-06 | Si no queda ningún correo válido, no se crea la campaña | Error en el campo |
| RN-007-07 | El HTML es `.html`/`.htm`, hasta 1 MB, UTF-8 | Error en el campo |
| RN-007-08 | Las imágenes del HTML tienen que ser URLs absolutas `https://`; no se adjuntan archivos | Aviso en la previsualización si detecta rutas relativas |
| RN-007-09 | Asunto: obligatorio, hasta 150 caracteres. Nombre: obligatorio, hasta 120 | Error en el campo |
| RN-007-10 | Solo «A enviar» se edita o elimina; solo «Enviando» se detiene; solo «Enviando» interrumpida se reanuda | Botón no visible y la vista responde error |
| RN-007-11 | Un destinatario ya marcado como enviado nunca se vuelve a enviar (ni al reanudar) | — |
| RN-007-12 | El envío se dispara solo con `notificacion.enviar`; editar/eliminar/crear con `notificacion.gestionar` | Redirección con aviso o 403 |
| RN-007-13 | El correo se arma con `EmailMultiAlternatives`: cuerpo HTML + alternativa en texto plano derivada del HTML; remitente `DEFAULT_FROM_EMAIL` | — |
| RN-007-14 | Un fallo de un destinatario no frena la campaña: se registra el error y se sigue | — |
| RN-007-15 | El Excel trae **solo correos**: cualquier otra columna se ignora | — |
| RN-007-16 | La prueba va a **una sola** dirección válida, lleva «[PRUEBA] » en el asunto, no cambia el estado y tiene un límite de 10 pruebas por usuario por hora | Error en el popup / aviso de límite |
| RN-007-17 | Remitente único: `DEFAULT_FROM_EMAIL` (el `no-responder` actual), sin remitente propio por campaña | — |

---

## 6. Criterios de aceptación

- [ ] Dado un usuario sin `notificacion.ver`, cuando entra al backoffice, entonces no ve el grupo Notificaciones y la URL lo redirige.
- [ ] Dado un Excel con 10 filas (7 válidas, 2 inválidas, 1 duplicada), cuando creo la campaña, entonces queda en «A enviar» con 7 destinatarios, y la previsualización muestra total 7, 2 inválidos y 1 duplicado.
- [ ] Dado un Excel sin ningún correo válido, cuando guardo, entonces no se crea la campaña y veo el error en el campo.
- [ ] Dado un HTML con `<script>`, cuando creo la campaña, entonces la vista previa y el correo enviado no contienen el script.
- [ ] Dada una campaña en «A enviar», cuando abro la previsualización, entonces veo el correo con el asunto (con `[QA] ` en testing) y la lista completa de destinatarios.
- [ ] Dada una campaña en «A enviar» y un usuario con `notificacion.enviar`, cuando aprieto Enviar y confirmo, entonces pasa a «Enviando» y cada destinatario recibe un correo individual.
- [ ] Dado un usuario sin `notificacion.enviar`, cuando ve una campaña en «A enviar», entonces no ve el botón Enviar y el POST directo responde 403.
- [ ] Dado un envío donde falla un correo, cuando termina, entonces la campaña queda «Enviada con errores» y ese destinatario muestra el error.
- [ ] Dada una campaña enviada, cuando intento editarla o eliminarla, entonces no hay acción disponible y la URL lo rechaza.
- [ ] Dado un envío interrumpido, cuando aprieto Reanudar, entonces solo se envía a los pendientes.
- [ ] Dada una campaña en «A enviar», cuando aprieto Enviar prueba, cargo `prueba@gmail.com` y confirmo, entonces llega un único correo a esa dirección con «[PRUEBA] » en el asunto y la campaña sigue en «A enviar» sin destinatarios enviados.
- [ ] Dada una campaña enviada, cuando aprieto Duplicar, entonces se crea «Copia de <nombre>» en «A enviar» con el mismo asunto, HTML y lista, y la original no cambia.
- [ ] Dado un Excel con 5.001 correos válidos, cuando guardo, entonces no se crea la campaña y el error dice que el tope es 5.000.

---

## 7. Casos límite y excepciones

| Caso | Comportamiento esperado |
|---|---|
| Celda con varios correos («a@x.com; b@y.com») | Descartada con motivo «formato inválido» (decidido: no se separan) |
| Correo de prueba inválido | El popup no se cierra y muestra el error en el campo |
| Duplicar una campaña cuyo Excel quedó con correos inválidos | La copia vuelve a leer el archivo y recalcula descartados igual que en el alta |
| Excel con fórmulas | Se lee el valor calculado (`data_only=True`) |
| Excel `.xls` o `.csv` | Rechazado; se pide `.xlsx` |
| HTML con CSS en `<style>` del `<head>` | Se conserva (los clientes de correo lo admiten parcialmente); la vista previa lo muestra |
| HTML con imágenes relativas o `cid:` | Aviso en la previsualización: «Hay N imágenes que no se van a ver» |
| SMTP caído al empezar | La campaña queda «Enviando» interrumpida con el error; se puede Reanudar |
| Redeploy durante el envío | El latido vence (5 min) → interrumpida → Reanudar |
| Dos usuarios aprietan Enviar a la vez | El candado deja pasar uno; el otro recibe aviso |
| Rechazo del SMTP por cuota | Se registra como fallido; si es masivo, se pausa (pregunta 3) |

---

## 8. Dependencias

- SMTP de ECOM operativo (Cambio 50) y su política de cuota/ritmo (pregunta 3).
- `openpyxl` (ya está). `nh3` (nuevo) para sanitizar y para derivar el texto plano.
- `core/rbac.py` + migración de `users` + `seed_rbac`.
- Patrón de proceso en segundo plano de `programas/services/proceso_masivo.py`.
- Servido de `media/` detrás de login (`config/urls.py`).

### Diseño técnico propuesto (para las tasks)

```
notificaciones/
  models.py      Campana(TimeStamped): nombre, asunto, archivo_excel, archivo_html,
                 html_sanitizado, estado, creada_por, enviada_por, enviada_en, finalizada_en,
                 latido, cancelacion_pedida, total, enviados, fallidos, leidas, invalidos,
                 duplicados
                 Destinatario(TimeStamped): campana FK, email, fila_excel, estado
                 (PENDIENTE|ENVIADO|FALLIDO), enviado_en, error  · unique(campana, email)
                 Descartado: campana FK, fila_excel, valor, motivo
  selectors/     campanas_listado, metricas, destinatarios_de
  services/      lectura_excel.py (parsear_destinatarios), html.py (sanitizar, a_texto),
                 envio.py (lanzar, enviar_lote, detener, reanudar)
  views/         listado, alta, edición, detalle/previsualización, html_preview (srcdoc),
                 enviar (POST), detener (POST), reanudar (POST), progreso (JSON), exportar
  forms/         CampanaForm (ModelForm, validación de archivos)
```

---

## 9. Fuera de alcance

- Personalizar el correo con columnas del Excel (`{{nombre}}`).
- Programar el envío para una fecha y hora.
- Plantillas reutilizables o editor visual de HTML.
- Adjuntos.
- Métricas de apertura, clics y rebotes.
- Enlace de desuscripción y lista de bajas (decidido 08/10: no hace falta).
- Remitente propio por campaña.
- Columnas extra en el Excel (nombre u otros datos).
- Elegir destinatarios desde ciudadanos/legajos del sistema en lugar de un Excel.
- Envío por otros canales (SMS, WhatsApp, push).

---

## 10. Preguntas abiertas

| # | Pregunta | Responsable de responder | Estado |
|---|---|---|---|
| 1 | ¿Quién usa el módulo? | PM | Cerrada: rol nuevo **Comunicaciones** |
| 2 | Tope de destinatarios por campaña | PM | Cerrada: **5.000** |
| 3 | ¿El SMTP de ECOM tiene cuota? | PM | Cerrada: no se sabe y no bloquea; lotes configurables (RNF-007-05) |
| 4 | ¿Envío de prueba? | PM | Cerrada: sí, popup que pide un correo (RF-007-18) |
| 5 | ¿Enlace de desuscripción? | PM | Cerrada: no |
| 6 | Celdas con varios correos | PM | Cerrada: se descartan |
| 7 | Remitente | PM | Cerrada: el `no-responder` actual |
| 8 | ¿Qué trae el Excel? | PM | Cerrada: solo correos |
| 9 | ¿Se puede duplicar? | PM | Cerrada: sí (RF-007-19) |

---

## 11. Historial de cambios del análisis

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-08 | Versión inicial + mock-ups | Pedido del PM |
| 2026-10-08 | Cierre de las 9 preguntas: rol Comunicaciones, tope 5.000, prueba por popup, duplicar, sin desuscripción, solo correos, remitente no-responder | Respuestas del PM |
