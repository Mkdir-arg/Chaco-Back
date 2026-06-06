# Propuesta funcional — Programa Becas: Relevamiento territorial y asignación de cupos

**Tipo:** Propuesta de épica (documento de trabajo interno)
**Estado:** En análisis (borrador en construcción)
**Fecha:** 2026-06-04
**Responsable (ICORE):** functional-analyst
**Programa:** Becas (primer programa sobre el módulo genérico de Programas)
**Módulos Django candidatos:** `apps/programas`, `apps/legajos`, `apps/ciudadanos`, `users` (roles/permisos)

> ⚠️ **Borrador en construcción.** Este documento consolida todo lo relevado hasta el
> cierre del backoffice (Secciones 1–7). Falta cerrar el **bloque de integraciones**
> (SIS → RENAPER → App de campo) y el **control estricto** antes de generar issues.
> Nada acá es definitivo: todas las **dudas y preguntas** están consolidadas al final,
> en la **Sección 16**.

---

## 1. Objetivo

Construir, en el **backoffice**, un módulo del **Programa Becas** que permita a un
**administrador** configurar convocatorias y **asignar relevamientos** a sus
**territoriales**. El territorial, desde una **app de campo** (externa, integrada vía
API), releva ciudadanos en terreno cargando **un formulario por persona**. Al finalizar,
los formularios llegan al backoffice, donde el administrador los **revisa caso por caso**
y los **aprueba o rechaza**. Las personas aprobadas pasan por una **validación contra el
Sistema SIS** y, según disponibilidad de **cupo del programa**, ocupan una beca o quedan
en **lista de espera**.

---

## 2. Concepto / modelo del dominio

Jerarquía de 4 niveles (confirmada):

```
Programa  (módulo con funcionamiento propio — Becas es uno, Ñachec es otro)
   └─ Convocatoria        (una o varias dentro del programa)
        └─ Relevamiento   (campaña de campo, asignada a UN territorial, con fecha y zona)
             └─ Formulario (N por relevamiento; cada uno = 1 persona / legajo)
```

| Entidad | Descripción | Notas clave |
|---|---|---|
| **Programa** | Marco genérico. Becas es el primero; Ñachec es otro programa. | El **cupo** vive a nivel Programa. |
| **Convocatoria** | Agrupador dentro del programa. Un programa tiene 1..N convocatorias. | — |
| **Relevamiento** | Campaña de campo asignada a **un solo** territorial. Se **auto-nombra** "Relevamiento XXX". | Tiene territorial, fecha/plazo y zona/localidad. Reasignable. |
| **Formulario** | Una persona relevada. N por relevamiento. | **Campos aún no definidos** (pregunta abierta). |
| **Persona / Legajo** | El ciudadano relevado. Se busca en `legajos`: si existe se relaciona, si no se crea. | El legajo se crea **al enviar** el formulario. Una persona puede estar en **N programas** a la vez. |
| **Cupo** | Número de becas disponibles **por Programa**. | Se ocupa **después** de validar con SIS, no al aprobar. |
| **Lista de espera** | Personas validadas-OK que no entraron por cupo lleno. | El admin promueve **a mano**. |

📌 *Asunción pendiente:* la jerarquía de 4 niveles se modela explícita; "Programa" es
genérico aunque hoy se arranque solo con Becas. Ver detalle al final en **Sección 16.6**.

---

## 3. Actores y roles

| Actor | Tipo | Acceso / permisos | Qué hace |
|---|---|---|---|
| **Administrador del programa** | Rol **nuevo** (no existe hoy). Se apoya en el esquema de roles/permisos de `users`. | Acceso al **módulo del programa Becas**; el acceso por módulo depende de los roles asignados. Ve **todo** el programa. | Crea convocatorias y relevamientos, asigna/reasigna territoriales, revisa formularios (aprueba/rechaza con motivo), gestiona cupo y lista de espera, da de baja beneficiarios. |
| **Territorial** | Usuario del sistema con login propio. | Ve **solo sus** relevamientos y formularios. | Inicia el relevamiento del día asignado, carga formularios (1 por persona) en la app de campo, finaliza y envía todo junto. |

Por ahora **solo** estos dos roles (sin supervisor/coordinador).

📌 *Duda pendiente:* convivencia de perfiles en un mismo usuario (admin/territorial).
Detalle consolidado al final en **Sección 16.2 (pregunta 7)**.

📌 *Impacto crítico:* el rol "Administrador de programa" es nuevo y se apoya en el
esquema de permisos existente en `users`. Hay que revisar cómo Chaco maneja roles hoy
para no inventar un esquema paralelo.

---

## 4. Funcionamiento end-to-end

1. **Configuración (admin).** El administrador define el **Programa Becas** con su
   **cupo**, crea una o varias **convocatorias** y, dentro de ellas, **relevamientos**.
   Al crear un relevamiento define: **territorial asignado**, **fecha/plazo** y
   **zona/localidad**. El relevamiento se **auto-nombra** "Relevamiento XXX". Puede
   **reasignarlo** a otro territorial.
2. **Inicio en campo (territorial).** El territorial entra a la app, ve el **listado de
   sus relevamientos** asignados y **solo puede iniciar el relevamiento del día**.
3. **Carga (territorial).** Dentro del relevamiento carga **un formulario tras otro**
   (1 por persona). Al iniciar cada formulario, el sistema determina la **forma de
   validar identidad** según conectividad (ver § 8.2 para detalle completo): puede
   **escanear el DNI** (lectura directa del chip/código del documento), **validar con
   RENAPER** (ingreso manual de DNI + sexo), o **cargar manual** si no hay conexión.
   **No** puede dejar un formulario a medias.
4. **Finalización y envío (territorial).** Cuando termina, **finaliza el relevamiento** y
   **todos los formularios se envían juntos** al backoffice. El territorial **termina su
   tarea** acá (no participa más). Al enviarse, cada persona se **crea/relaciona como
   legajo**, se apruebe o no después.
5. **Revisión caso por caso (admin).** El admin entra al relevamiento finalizado, ve el
   **listado de formularios enviados**, abre **uno por uno**, ve la información recabada y
   **aprueba** o **rechaza** (el rechazo requiere **motivo** y es **informativo**: no
   vuelve al territorial).
6. **Validación SIS (aprobados).** Si el admin **aprueba**, el sistema **automáticamente**
   dispara la validación contra SIS (**síncrona**: el admin espera la respuesta). Si el
   admin **rechaza**, no se envía a SIS. Resultado de SIS: **Validado-Aprobado** o
   **Validado-Rechazado**.
7. **Asignación de cupo.** Si SIS aprueba y **hay cupo** disponible en el programa → la
   persona **ocupa 1 cupo** en ese momento. Si el cupo está lleno → va a **lista de
   espera**. El siguiente caso que se apruebe ya ve el cupo actualizado.
8. **Gestión de cupo (admin).** Cuando el admin **da de baja** a un beneficiario, se
  libera un cupo y el sistema muestra una **alerta**: "se liberó un cupo, mover a
  alguien de la lista de espera". El admin **promueve a mano**.
9. **Reportes.** El admin **exporta** beneficiarios, lista de espera y avance de
   relevamientos (requerimiento **clave**).

---

## 5. Estados

### Estado del Relevamiento

```
Asignado → En curso → Finalizado → En revisión → Terminado
```

| Estado | Significado | Dónde se ve |
|---|---|---|
| **Asignado** | El admin lo creó y se lo asignó a un territorial. | Backoffice y app de campo |
| **En curso** | El territorial lo inició en campo (el día asignado). | Backoffice y app de campo |
| **Sincronizando...** | El territorial presionó "Finalizar" sin conexión; los formularios están pendientes de sincronización. | **Solo app de campo** (el backoffice no lo ve hasta que sincronice) |
| **Finalizado** | El territorial lo cerró y envió todos los formularios (ya sincronizados con el backoffice). | Backoffice y app de campo |
| **En revisión** | El admin está revisando los formularios caso por caso. | Backoffice (el territorial ya no lo ve activo) |
| **Terminado** | Revisión completa cerrada. | Backoffice |

### Estado del Formulario / Persona

```
Enviado → Aprobado / Rechazado            (revisión del admin)
   Aprobado → Validando (SIS)
       → Validado-Aprobado → Con cupo / En lista de espera
       → Validado-Rechazado
```

| Estado | Significado |
|---|---|
| **Enviado** | El territorial lo mandó al finalizar el relevamiento. |
| **Aprobado** | El admin lo aprobó en la revisión. |
| **Rechazado** | El admin lo rechazó (con motivo, informativo). |
| **Validando** | Consultando al Sistema SIS. |
| **Validado-Aprobado** | SIS respondió OK. |
| **Validado-Rechazado** | SIS respondió NO. |
| **Con cupo** | Ocupa una beca (había cupo disponible). |
| **En lista de espera** | Validado-OK pero sin cupo disponible. |

📌 *Asunción pendiente:* "aprobar" (admin) y "ocupar cupo" (post-SIS) son dos cosas
distintas. El detalle quedó consolidado al final en **Sección 16.6**.

---

## 6. Cupo, validación SIS y lista de espera

- El **cupo es del Programa** (no del relevamiento). El territorial releva **sin límite**.
- El **consumo de cupo NO ocurre al aprobar**, sino tras la validación **SIS**:
  admin confirma (OKA en Nodo) → **se dispara automáticamente** la consulta a SIS
  (**síncrona**: el admin espera la respuesta) → si SIS responde **OKA** y hay cupo →
  ocupa cupo; si SIS responde OKA y no hay cupo → lista de espera.
- **Validación SIS es síncrona y secuencial:** al aprobar un formulario, el sistema
  consulta SIS y **bloquea** hasta recibir respuesta. Esto garantiza que no hay race
  condition: el cupo se consume en ese momento y el siguiente caso ya ve el cupo actualizado.
- Si el admin **rechaza** un formulario (en lugar de aprobar), **no se envía a SIS**;
  queda directamente en estado "Rechazado" con motivo.
- **Lista de espera:** el admin **promueve a mano**. Al dar de baja a un beneficiario, el
  sistema dispara una **alerta proactiva** para mover a alguien de la lista.
- Si existe **OKA en Nodo + OKA en SIS**, el caso queda habilitado para pasar al
  **sistema de liquidacion**.

### 6.1 Hallazgos del documento del equipo Ministerio (URD RQ-002 — "Tablero de Aprobación N1")

El equipo Ministerio entregó el documento **RQ-002** (Tablero de Aprobación de Primer Nivel e
Integración SIS). **No resuelve el contrato técnico de SIS**, pero aporta encuadre y
**revela contradicciones** que hay que reconciliar:

**Aporta:**
- **SIS = Sistema de Inclusión Social**, **segundo nivel de control**, recibe los datos
  aprobados vía **API REST** y hace su propio control intermedio.
- Aparece un **tercer sistema nuevo: "Sistema de Ayudas Sociales"** (sistema madre de
  **liquidación**, nivel 3) que graba definitivamente para pagar el beneficio.
- Cadena real de control: **Aprobación Nivel 1 (nuestro backoffice) → SIS (Nivel 2) →
  Ayudas Sociales (Nivel 3, liquidación)**.

**NO responde (sigue pendiente):** qué se manda exactamente (sin contrato de campos/API)
y qué devuelve SIS en detalle (estructura/campos). También queda pendiente definir la
pregunta de cadena de 3 niveles para esta fase.

**🔴 Contradicciones / huecos a reconciliar con el equipo Ministerio:**
- **Disparo a SIS:** el doc dice "automático al aprobar" PERO su Pantalla 4 tiene botón
  **"Enviar al SIS / Confirmar transferencia"** (manual), lo que contradice el flujo.
- **Alcance:** RQ-002 es **genérico** ("beneficios sociales", "Asignación Social X", login
  con Google/OAuth), parece de una **plataforma más amplia**, no específico de Becas.

**Definiciones acordadas en esta ronda:**
- SIS responde **OKA** = válido. Se espera confirmación o rechazo con motivo.
- Para ocupar cupo debe existir **OKA del administrador en Nodo + OKA de SIS**.
- **Disparo a SIS:** automático y **síncrono** al aprobar (el admin espera la respuesta
  antes de continuar). Si el admin rechaza, **no se envía a SIS**.
- Si SIS falla por timeout en Nodo, se muestra alerta en el registro para reintentar.
- Se mantiene el lenguaje propio: **Administrador/Territorial** =
  **Supervisor/Operador** del RQ-002.
- Con **OKA en SIS + OKA en Nodo**, el caso pasa a **liquidacion**.

➡️ El detalle de preguntas derivadas de estas contradicciones está consolidado en
**Sección 16.3 (preguntas 11 a 16)**.

📌 *Pendiente SIS (sigue diferido):* hace falta el **contrato técnico de SIS**.
Detalle de preguntas consolidado al final en **Sección 16.1 (S-1 a S-10)**.

---

## 7. Pantallas del backoffice (mapa preliminar)

| Pantalla | Operaciones principales |
|---|---|
| **Convocatorias** | ABM: listar, crear, editar, ver, (des)activar convocatorias del programa. |
| **Relevamientos** | ABM + **asignar/reasignar** territorial, fecha/plazo, zona. Ver estado. |
| **Revisión de relevamiento** | Entrar a un relevamiento finalizado → listado de formularios → abrir uno por uno → **aprobar/rechazar** (motivo). |
| **Beneficiarios / Cupo** | Ver ocupación de cupo, **lista de espera**, **dar de baja**, **promover** desde lista de espera. |
| **Configuración del programa** | Definir **cupo total** del programa y parámetros. |
| **Reportes** | Exportar beneficiarios, lista de espera, avance de relevamientos. |

---

## 8. Integraciones (bloque diferido — en relevamiento)

| Integración | Rol en el flujo | Estado del relevamiento |
|---|---|---|
| **Sistema SIS** | Valida a la persona **aprobada**; su OK habilita ocupar cupo. | 🔻 En análisis (documento del equipo Ministerio pendiente). |
| **RENAPER** | Valida la identidad (DNI + sexo) **al cargar** cada persona en campo. | ✅ **Relevada y probada** (reusa integración existente). |
| **App de campo** | App **propia** (la desarrollamos nosotros). Funciona **online/offline**, sincroniza al recuperar señal; al finalizar offline confirma tras sync. | ✅ **Relevada** (alcance propio). |

📌 *Impacto crítico:* offline + envío en lote + validación RENAPER en campo es alcance
grande y depende de las 3 integraciones.

### 8.0 RENAPER — integración relevada (✅ cerrada)

**Reusa la integración existente** de Chaco (no es nueva). Vive en
`legajos/services/consulta_renaper.py` (`consultar_datos_renaper(dni, sexo)` y el cliente
de bajo nivel `APIClient.consultar_ciudadano`). Hoy se usa al crear el legajo de un
ciudadano. Endpoint configurado: `RENAPER_API_URL` →
`https://sisoc.secretarianaf.gob.ar/api/renaper/consultar/` (POST, con API key /
credenciales por variables de entorno).

| Punto | Definición |
|---|---|
| **Datos de entrada (2)** | **DNI + sexo**. |
| **Qué devuelve** | Confirma identidad **y autocompleta** datos: apellido, nombres, fecha de nacimiento, CUIL, domicilio (calle/número/piso/ciudad/municipio/provincia), número de trámite, **aviso de fallecimiento** (`mensaf`), vencimiento del DNI. |
| **Si NO valida** | Si los datos no coinciden, RENAPER responde "No se encontró coincidencia" (success=false). |
| **Si RENAPER no responde / falla** | El sistema **permite cargar el formulario de forma manual** y marca el registro como **"No validado RENAPER"**. Ese registro queda visible en el backoffice para que el admin **lo valide en ese momento** (posteriormente). |
| **Quién la consume** | **Ya existe** en Chaco; se **reusa** el servicio. No se desarrolla de cero. |

📌 *Regla nueva (RN):* sin respuesta de RENAPER, el formulario se carga manual y queda
**"No validado RENAPER"** → el backoffice debe ofrecer **validar a posteriori**.

📌 *Asunción a confirmar:* la app de campo (externa) consume **la misma API** que el
backoffice o un endpoint equivalente; la validación posterior en backoffice usa el mismo
`consultar_datos_renaper`.

**Ejemplo de respuesta real (DNI de prueba 40732138, sexo M) — para mostrar al equipo Ministerio:**

```json
{
  "success": true,
  "data": {
    "iD_TRAMITE_PRINCIPAL": 456510149,
    "ejemplar": "C",
    "vencimiento": "16/09/2031",
    "emision": "16/09/2016",
    "apellido": "FARIÑA",
    "nombres": "Matias",
    "fechaNacimiento": "1997-10-25",
    "cuil": "20407321384",
    "calle": "MONTIEL",
    "numero": "2951",
    "piso": "TIMB",
    "ciudad": "MATADEROS",
    "municipio": "CIUDAD_DE_BUENOS_AIRES",
    "provincia": "CIUDAD_DE_BUENOS_AIRES",
    "pais": "ARGENTINA",
    "mensaf": "Sin Aviso de Fallecimiento",
    "idciudadano": "101445173",
    "nroError": 0,
    "descripcionError": "DNI/PAS Firmado"
  }
}
```

> Nota: el servicio de alto nivel también mapea `provincia` contra la tabla `Provincia` y
> detecta fallecimiento (`mensaf == "FALLECIDO"` ⇒ no continúa).

### 8.1 Sistema SIS — estado

El relevamiento de SIS sigue parcialmente abierto: ya se acordaron reglas de decisión
(OKA/RECHAZO, doble OKA para cupo, manejo de timeout), pero falta cerrar contrato
técnico y alcance completo de cadena.

**Estado SIS:** 🟠 **Parcialmente definido** (con pendientes técnicos).
➡️ Las preguntas concretas (S-1…S-10) están consolidadas al final, en
**[16. Preguntas pendientes](#16-preguntas-pendientes-consolidado)**.

---

### 8.2 App de campo — integración relevada (✅ cerrada)

| Punto | Definición |
|---|---|
| **Quién la hace** | **La desarrollamos nosotros** (ya la tenemos). Entra en el alcance. |
| **Online/offline** | Funciona **online y offline**. Guarda local y **sincroniza** al recuperar señal. |
| **Finalizar offline** | El territorial puede presionar **Finalizar sin conexión**; el sistema **finaliza recién cuando se sincronizó todo** (el envío en lote se encola y la finalización se confirma post-sincronización). |
| **RENAPER offline** | Si no hay señal, se aplica la regla **"cargar manual + No validado RENAPER"**; el registro se envía al backoffice y el **administrador puede revalidar** ahí. |

#### Flujo de carga de identidad en campo

Al iniciar un formulario, el sistema determina el camino según conectividad y elección del territorial:

```
¿Hay conexión?
    SÍ → el territorial elige:
           Opción A: Escaneo DNI (cámara — barcode / QR / MRZ)
                     → lee datos DIRECTOS del chip/código del documento físico
                     → autocompleta todos los campos disponibles
                     → NO consulta RENAPER (los datos vienen del DNI real)
                     → marca: "Validado por escaneo DNI"
           Opción B: Validación RENAPER (ingresa DNI + sexo a mano)
                     → consulta API RENAPER
                     → RENAPER confirma identidad y autocompleta datos
                     → marca: "Validado RENAPER"
                     → si RENAPER no responde → carga manual + "No validado RENAPER"
    NO → carga manual directamente → "No validado RENAPER"
```

| Camino | Origen | Marca de validación | ¿Requiere revalidación? |
|---|---|---|---|
| Escaneo DNI (con conexión) | Territorial elige opción A | **Validado por escaneo DNI** | No — datos leídos directamente del documento físico |
| RENAPER responde OK (con conexión) | Territorial elige opción B | **Validado RENAPER** | No — confirmado por API RENAPER |
| RENAPER no responde (con conexión) | Opción B fallida → carga manual | **No validado RENAPER** | Sí — backoffice debe revalidar (RN-16) |
| Sin conexión | Automático → carga manual | **No validado RENAPER** | Sí — backoffice debe revalidar (RN-16) |

📌 *Regla crítica:* el **escaneo DNI NO consulta RENAPER** porque lee los datos directamente del chip/código del documento físico que tiene el territorial en la mano. Esto le da el mismo nivel de confianza (o mayor) que la validación remota con RENAPER.

📌 *Regla:* "No validado RENAPER" tiene **dos orígenes posibles**: sin conexión (offline) o RENAPER caído con conexión. En ambos casos el tratamiento posterior es idéntico: el backoffice debe permitir revalidar (RN-16).

📌 *Regla nueva (RN-15):* "Finalizado" del relevamiento es un estado **diferido a la
sincronización**: si se finaliza offline, el relevamiento muestra **"Sincronizando..."** en
la app (estado local) y solo aparece en el backoffice con estado `Finalizado` cuando
**todo** se sincronizó. El admin no ve el relevamiento antes de la sincronización completa.

📌 *Impacto crítico:* hay **dos momentos de validación RENAPER** — (1) en campo si hay
señal; (2) en backoffice (revalidación) para los marcados "No validado RENAPER". El
backoffice debe exponer esa acción de revalidar.

---

## 9. Reglas de negocio (consolidadas, preliminares)

| ID | Regla |
|---|---|
| RN-01 | El cupo es **por Programa**; el territorial releva sin límite. |
| RN-02 | El cupo se consume **solo** tras SIS = OK y si hay disponibilidad. |
| RN-03 | Sin cupo disponible, la persona validada-OK va a **lista de espera**. |
| RN-04 | La salida de lista de espera es **manual** (admin promueve). |
| RN-05 | Al dar de baja un beneficiario, se libera cupo y el sistema **alerta** para promover. |
| RN-06 | El territorial **solo** puede iniciar el relevamiento **del día asignado**. |
| RN-07 | Un formulario **no** se puede dejar a medias; se completa entero. |
| RN-08 | Los formularios se envían **todos juntos** al finalizar el relevamiento. |
| RN-09 | El legajo se crea/relaciona **al enviar** el formulario, se apruebe o no. |
| RN-10 | Una persona puede pertenecer a **N programas** a la vez. |
| RN-11 | El **rechazo** del admin requiere **motivo** y es **informativo** (no vuelve al territorial). |
| RN-12 | El territorial **ve solo lo suyo**; el admin **ve todo** el programa. |
| RN-13 | Identidad de la persona se valida al cargar mediante **3 caminos posibles**: (A) escaneo DNI (lectura directa del chip/código del documento → marca "Validado por escaneo DNI"), (B) RENAPER (ingreso manual DNI + sexo → consulta API → marca "Validado RENAPER"), (C) carga manual si no hay conexión o RENAPER falla (marca "No validado RENAPER" → requiere revalidación posterior en backoffice). |
| RN-14 | Trazabilidad obligatoria: quién cargó, cuándo, historial de estados (admin/SIS). |
| RN-15 | La app funciona **offline**; si el territorial presiona "Finalizar" sin conexión, el relevamiento muestra estado **"Sincronizando..."** en la app (solo visible localmente) hasta recuperar señal y sincronizar. El backoffice **no ve el relevamiento** hasta que se sincronicen todos los formularios; recién ahí aparece con estado `Finalizado`. |
| RN-16 | El backoffice debe permitir **revalidar contra RENAPER** los registros marcados "No validado RENAPER". |
| RN-17 | La app de campo **la desarrollamos nosotros** (entra en el alcance). |
| RN-18 | SIS responde **OKA** = válido; si SIS rechaza, debe existir motivo de rechazo. |
| RN-19 | El cupo se ocupa **solo** con doble confirmación: **OKA en Nodo + OKA en SIS**. Sin alguno de los dos, no ocupa cupo. |
| RN-20 | Si SIS falla por **timeout en Nodo**, el sistema marca alerta en el registro para reintento posterior. |
| RN-21 | Con **OKA en Nodo + OKA en SIS**, el caso queda habilitado para pasar al **sistema de liquidacion**. |
| RN-24 | La validación SIS se **dispara automáticamente** al aprobar un formulario (tanto aprobación como rechazo disparan en ese momento: aprobación → envía a SIS; rechazo → no envía). La consulta a SIS es **síncrona**: el admin espera la respuesta antes de poder continuar con otro caso. Esto garantiza que el consumo de cupo es secuencial y sin race conditions. |
| RN-25 | Si el admin **rechaza** un formulario, **no se envía a SIS**; queda directamente en estado "Rechazado" con motivo informativo. |
| RN-22 | Si la fecha de nacimiento indica que el beneficiario es **menor de edad (< 18 años)**, se habilita obligatoriamente la sección **Apoderado** (Nombre, Apellido, Fecha de Nacimiento). El formulario no puede finalizarse sin esos datos. Si el beneficiario es mayor de edad, la sección permanece oculta. |
| RN-23 | El territorial puede **editar los campos precargados** por escaneo o RENAPER en caso de error de lectura o domicilio desactualizado. |

---

## 10. Dependencias e impacto crítico

- **`users` / permisos:** rol nuevo "Administrador de programa", acceso por módulo según
  roles. No inventar esquema paralelo.
- **`legajos` / `ciudadanos`:** la persona = legajo. Reusar identificación existente
  (DNI/CUIL) y la relación legajo↔programa. Revisar duplicidad de personas.
- **Integraciones externas:** SIS, RENAPER, App de campo (API).
- **Módulo Programas (`apps/programas`):** base genérica donde se apoya Becas.

📌 *Pendiente de investigación de código* (al cerrar el interrogatorio): confirmar qué
ofrecen hoy `apps/programas`, `apps/legajos`, `apps/ciudadanos` y `users` para no duplicar.

---

## 11. Fuera de alcance (por ahora)

- **Notificaciones** a territoriales o ciudadanos.
- **Reproceso** de personas rechazadas por el admin (rechazo es informativo).
- Diseñador de formularios dinámicos (los **campos son fijos**, definidos por nosotros).

---

## 12. Preguntas abiertas

➡️ **Todas las preguntas pendientes están consolidadas al final del documento**, en
**[16. Preguntas pendientes](#16-preguntas-pendientes-consolidado)** (equipo Ministerio, técnicas y
de equipo, con su estado).

---

## 13. Asunciones a confirmar

➡️ **Asunciones y dudas pendientes** consolidadas al final en
**[16.6 Asunciones pendientes de confirmación](#166-asunciones-pendientes-de-confirmacion)**.

---

## 14. Próximos pasos

1. **Sistema SIS** — analizar el documento del equipo Ministerio y cerrar preguntas 5 y 6.
2. **RENAPER** — relevar validación de identidad en campo.
3. **App de campo** — online/offline, sincronización, envío en lote.
4. **Control estricto** — cerrar todas las preguntas abiertas y verificar consistencia.
5. **Generación en GitHub** — épica → análisis → sub-issues (recién con todo cerrado).

---

## 15. Historial

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-06-04 | Versión inicial: consolidación backoffice (Secciones 1–7). | Pedido del usuario antes de abrir el bloque SIS. |
| 2026-06-04 | Incorporación RQ-001: flujo de carga de identidad en campo (escaneo / RENAPER / manual), RN-22 y RN-23, pregunta 2 rebajada a 🟡 con base de campos definida. | Análisis URD RQ-001 (Registro de Beneficiarios). |
| 2026-06-04 | Reconciliación § 4 paso 3 vs § 8.2: aclarado que escaneo DNI NO consulta RENAPER (lee datos directos del chip/código del documento) y se marca "Validado por escaneo DNI". Actualizada RN-13. | Corrección de tensión lógica detectada en análisis. |
| 2026-06-04 | Documentado estado "Sincronizando..." (solo app de campo) en § 5 y RN-15: el backoffice no ve el relevamiento hasta que sincronice completamente. | Corrección de estado implícito detectado en análisis. |
| 2026-06-04 | Documentado flujo síncrono de validación SIS (§ 4 pasos 6-7, § 6, RN-24, RN-25): el disparo es automático al aprobar y bloquea hasta recibir respuesta, garantizando consumo secuencial de cupo sin race conditions. | Cierre de potencial race condition detectado en análisis. |

---

## 16. Preguntas pendientes (consolidado)

> **Todas las preguntas abiertas del análisis, juntas y al final.** Mientras existan
> pendientes **bloqueantes**, NO se generan issues (control estricto de `AGENTS.md`).
> Estado de cada una: 🔴 bloqueante · 🟡 no bloqueante · ⏸️ diferida.

### 16.1 Sistema SIS (pendientes y diferida)

| # | Pregunta | Para | Estado |
|---|---|---|:--:|
| S-1 | **Contrato de API.** ¿SIS expone una API REST? ¿Endpoint, autenticación, ambiente de prueba? ¿Es síncrono o asíncrono? | Equipo Ministerio/ICORE | 🔴 |
| S-2 | **Datos de entrada.** ¿Qué campos se le envían por persona? (DNI/CUIL, datos del beneficio, id de programa, adjuntos) | Equipo Ministerio/ICORE | 🔴 |
| S-4 | **Datos de salida.** ¿Qué devuelve exactamente? (OK/NO, código, motivo de rechazo, datos) | Equipo Ministerio/ICORE | 🔴 |
| S-5 | **Rechazo de SIS.** Si responde NO, ¿la persona queda fuera o el admin corrige y reenvía? | Equipo Ministerio | 🔴 |
| S-8 | **Cadena de 3 niveles.** ¿Becas llega hasta "ocupa cupo" o también hasta Ayudas Sociales / Liquidado (nivel 3)? | Equipo Ministerio | ⏸️ |

### 16.2 Formulario y reglas de negocio

| # | Pregunta | Para | Estado |
|---|---|---|:--:|
| 2 | **Campos exactos del formulario.** RQ-001 define una base: Bloque A (DNI, Apellido, Nombre, Sexo, Estado Civil, Fecha de Nacimiento), Bloque B (Domicilio: Provincia, Localidad, Calle, Número, Piso, Departamento, Barrio), Bloque C (Celular, Mail — manual obligatorio), Bloque D (Apoderado — condicional menor de edad), Adjuntos (Foto DNI frente/dorso obligatorios; CBU y Cert. domicilio opcionales). **Pendiente confirmar con Guido** si estos son los campos definitivos o si hay campos adicionales para Becas. | Guido (Equipo Ministerio) | 🟡 |
| 1 | ¿Finalizar un relevamiento es **reversible** para el territorial? | Equipo Ministerio | 🟡 |
| 3 | Cupo: ¿único por programa o puede haber **por zona/localidad/convocatoria**? | Equipo Ministerio | 🟡 |
| 4 | Lista de espera: ¿**orden/prioridad** (FIFO) o elección libre del admin? | Equipo Ministerio | 🟡 |
| 7 | ¿Un usuario puede ser **Admin de un programa y Territorial de otro** a la vez? | Equipo Ministerio | 🟡 |
| 8 | "Relevamiento del día": ¿qué pasa si **no se inicia** ese día (vence/reprograma)? | Equipo Ministerio | 🟡 |
| 9 | ¿El admin puede **editar datos** del formulario antes de aprobar? | Equipo Ministerio | 🟡 |
| 10 | Legajo creado al enviar: ¿cómo se **marca** un legajo "relevado pero rechazado en Becas"? | ICORE/Equipo Ministerio | 🟡 |

### 16.3 RQ-002 / cadena de aprobación (🔴 bloqueante — contradicciones a reconciliar)

| # | Pregunta | Para | Estado |
|---|---|---|:--:|
| 12 | **Cadena de control:** ¿cómo conviven cupo/lista de espera con post-SIS → Ayudas Sociales/Liquidado? ¿El cupo se decide antes o después de SIS? | Equipo Ministerio | 🔴 |
| 13 | **Sistema de Ayudas Sociales (nivel 3):** ¿dentro del alcance de Becas o es otro requerimiento? | Equipo Ministerio | 🔴 |
| 14 | **Contrato técnico de SIS:** endpoint/API, campos, qué valida, qué devuelve, manejo de rechazo y caída. (= S-1…S-7) | Equipo Ministerio/ICORE | 🔴 |
| 15 | **Disparo a SIS:** el RQ-002 se contradice (auto al aprobar vs botón manual "Enviar al SIS"). ¿Cuál es? | Equipo Ministerio | 🔴 |
| 16 | **Alcance RQ-002:** ¿es parte de Becas o de una plataforma más amplia (login Google/OAuth, beneficios genéricos)? | Equipo Ministerio | 🔴 |

### 16.4 Investigación de código pendiente (responsabilidad de ICORE)

| # | Tarea | Estado |
|---|---|:--:|
| C-1 | Revisar duplicidad real en `apps/programas`, `apps/legajos`, `apps/ciudadanos`, `users` (qué existe hoy). | ⏳ |
| C-2 | Revisar épicas/análisis/tasks ya creados y el backlog del Project #1 (no duplicar trabajo encolado). | ⏳ |

### 16.5 Resumen del control estricto

- **No se generan issues** mientras haya 🔴 sin cerrar (SIS, campos del formulario, roles,
  cadena cupo↔RQ-002).
- Las 🟡 se pueden **asumir** y documentar como *Asunción a confirmar* sin frenar.
- Falta cerrar la **investigación de código** (C-1, C-2) antes de generar.

### 16.6 Asunciones pendientes de confirmación

| # | Asunción / duda | Estado |
|---|---|:--:|
| A-1 | Jerarquía de 4 niveles explícita; "Programa" se modela genérico aunque hoy solo se use Becas. | 🟡 |
| A-2 | "Aprobar" en backoffice y "ocupar cupo" son pasos distintos (el cupo se decide después de SIS). | 🟡 |
| A-3 | RENAPER en campo usa la misma API (o equivalente) que backoffice para validar identidad. | 🟡 |
| A-4 | Una persona rechazada por admin conserva legajo creado (sin reproceso en el sistema). | 🟡 |
