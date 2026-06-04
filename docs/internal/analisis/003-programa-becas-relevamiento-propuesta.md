# Propuesta funcional — Programa Becas: Relevamiento territorial y asignación de cupos

**Tipo:** Propuesta de épica (documento de trabajo interno)
**Estado:** En análisis (borrador en construcción)
**Fecha:** 2026-06-04
**Analista:** functional-analyst
**Programa:** Becas (primer programa sobre el módulo genérico de Programas)
**Módulos Django candidatos:** `apps/programas`, `apps/legajos`, `apps/ciudadanos`, `users` (roles/permisos)

> ⚠️ **Borrador en construcción.** Este documento consolida todo lo relevado hasta el
> cierre del backoffice (Secciones 1–7). Falta cerrar el **bloque de integraciones**
> (SIS → RENAPER → App de campo) y el **control estricto** antes de generar issues.
> Nada acá es definitivo: las **Preguntas abiertas** (sección 12) deben cerrarse primero.

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

📌 *Asunción a confirmar:* la jerarquía de 4 niveles se modela explícita; "Programa" es
genérico aunque hoy se arranque solo con Becas.

---

## 3. Actores y roles

| Actor | Tipo | Acceso / permisos | Qué hace |
|---|---|---|---|
| **Administrador del programa** | Rol **nuevo** (no existe hoy). Se apoya en el esquema de roles/permisos de `users`. | Acceso al **módulo del programa Becas**; el acceso por módulo depende de los roles asignados. Ve **todo** el programa. | Crea convocatorias y relevamientos, asigna/reasigna territoriales, revisa formularios (aprueba/rechaza con motivo), gestiona cupo y lista de espera, da de baja beneficiarios. |
| **Territorial** | Usuario del sistema con login propio. | Ve **solo sus** relevamientos y formularios. | Inicia el relevamiento del día asignado, carga formularios (1 por persona) en la app de campo, finaliza y envía todo junto. |

Por ahora **solo** estos dos roles (sin supervisor/coordinador).

📌 *Asunción a confirmar:* ¿un mismo usuario puede ser Administrador de un programa y
Territorial de otro a la vez, o son excluyentes? → pregunta abierta.

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
   (1 por persona). Al iniciar cada formulario pide **2 datos de identidad** que se
   validan contra **RENAPER**. **No** puede dejar un formulario a medias.
4. **Finalización y envío (territorial).** Cuando termina, **finaliza el relevamiento** y
   **todos los formularios se envían juntos** al backoffice. El territorial **termina su
   tarea** acá (no participa más). Al enviarse, cada persona se **crea/relaciona como
   legajo**, se apruebe o no después.
5. **Revisión caso por caso (admin).** El admin entra al relevamiento finalizado, ve el
   **listado de formularios enviados**, abre **uno por uno**, ve la información recabada y
   **aprueba** o **rechaza** (el rechazo requiere **motivo** y es **informativo**: no
   vuelve al territorial).
6. **Validación SIS (aprobados).** Cada persona aprobada se **valida contra el Sistema
   SIS**. Resultado: **Validado-Aprobado** o **Validado-Rechazado**.
7. **Asignación de cupo.** Si SIS aprueba y **hay cupo** disponible en el programa → la
   persona **ocupa 1 cupo**. Si el cupo está lleno → va a **lista de espera**.
8. **Gestión de cupo (admin).** Cuando el admin **da de baja** a un beneficiario, se
   libera un cupo y el sistema muestra una **alerta**: "se liberó un cupo, ¿querés mover a
   alguien de la lista de espera?". El admin **promueve a mano**.
9. **Reportes.** El admin **exporta** beneficiarios, lista de espera y avance de
   relevamientos (requerimiento **clave**).

---

## 5. Estados

### Estado del Relevamiento

```
Asignado → En curso → Finalizado → En revisión → Terminado
```

| Estado | Significado |
|---|---|
| **Asignado** | El admin lo creó y se lo asignó a un territorial. |
| **En curso** | El territorial lo inició en campo (el día asignado). |
| **Finalizado** | El territorial lo cerró y envió todos los formularios. |
| **En revisión** | El admin está revisando los formularios caso por caso. |
| **Terminado** | Revisión completa cerrada. |

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

📌 *Asunción a confirmar:* "aprobar" (admin) y "ocupar cupo" (post-SIS) son dos cosas
distintas. La aprobación es el caso por caso; el cupo se decide después con SIS +
disponibilidad.

---

## 6. Cupo, validación SIS y lista de espera

- El **cupo es del Programa** (no del relevamiento). El territorial releva **sin límite**.
- El **consumo de cupo NO ocurre al aprobar**, sino tras la validación **SIS**:
  admin confirma → consulta SIS → si OK y hay cupo → ocupa cupo; si OK y sin cupo → lista
  de espera.
- **Lista de espera:** el admin **promueve a mano**. Al dar de baja a un beneficiario, el
  sistema dispara una **alerta proactiva** para mover a alguien de la lista.

### 6.1 Hallazgos del documento del cliente (URD RQ-002 — "Tablero de Aprobación N1")

El cliente entregó el documento **RQ-002** (Tablero de Aprobación de Primer Nivel e
Integración SIS). **No resuelve el contrato técnico de SIS**, pero aporta encuadre y
**revela contradicciones** que hay que reconciliar:

**Aporta:**
- **SIS = Sistema de Inclusión Social**, **segundo nivel de control**, recibe los datos
  aprobados vía **API REST** y hace su propio control intermedio.
- Aparece un **tercer sistema nuevo: "Sistema de Ayudas Sociales"** (sistema madre de
  **liquidación**, nivel 3) que graba definitivamente para pagar el beneficio.
- Cadena real de control: **Aprobación Nivel 1 (nuestro backoffice) → SIS (Nivel 2) →
  Ayudas Sociales (Nivel 3, liquidación)**.

**NO responde (sigue pendiente):** qué se manda exactamente (sin contrato de campos/API),
qué valida SIS, qué devuelve, qué pasa si SIS **rechaza** (su matriz de estados **no tiene
estado de rechazo SIS**), ni qué pasa si SIS está caído.

**🔴 Contradicciones / huecos a reconciliar con el cliente:**
- **Roles:** el doc usa **Supervisor/Operador**; nuestra propuesta usa
  **Administrador/Territorial**. ¿Son los mismos con otro nombre?
- **Cupo y lista de espera:** el doc **no los menciona**. En el doc, post-SIS se va directo
  a **Liquidado**; en nuestro modelo, post-SIS recién se decide **cupo / lista de espera**.
  ¿Cómo conviven el cupo y la cadena SIS → Ayudas Sociales?
- **Disparo a SIS:** el doc dice "automático al aprobar" PERO su Pantalla 4 tiene botón
  **"Enviar al SIS / Confirmar transferencia"** (manual). **Se contradice solo** (afecta
  nuestra pregunta 6: auto vs manual).
- **Alcance:** RQ-002 es **genérico** ("beneficios sociales", "Asignación Social X", login
  con Google/OAuth), parece de una **plataforma más amplia**, no específico de Becas.

📌 *Pendiente SIS (sigue diferido):* hace falta el **contrato técnico de SIS** (endpoint,
campos, qué valida, qué devuelve, manejo de NO y de caída). El RQ-002 **no** lo tiene.

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
| **Sistema SIS** | Valida a la persona **aprobada**; su OK habilita ocupar cupo. | 🔻 En análisis (documento del cliente pendiente). |
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

**Ejemplo de respuesta real (DNI de prueba 40732138, sexo M) — para mostrar al cliente:**

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

El relevamiento de SIS queda **frenado del lado nuestro**: el documento RQ-002 no trae el
contrato técnico. Hasta tener respuestas del cliente, SIS queda como **caja negra** en la
propuesta ("se valida contra SIS y devuelve OK/NO").

**Estado SIS:** 🔴 **Bloqueado** a la espera de respuestas del cliente.
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

📌 *Regla nueva (RN):* "Finalizado" del relevamiento es un estado **diferido a la
sincronización**: si se finaliza offline, el relevamiento queda pendiente de sync y solo
pasa a `Finalizado` (con los formularios en backoffice) cuando **todo** se sincronizó.

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
| RN-13 | Identidad de la persona validada con **RENAPER** (DNI + sexo) al cargar. Si RENAPER no responde, se carga **manual** y queda **"No validado RENAPER"**, para validar luego en backoffice. |
| RN-14 | Trazabilidad obligatoria: quién cargó, cuándo, historial de estados (admin/SIS). |
| RN-15 | La app funciona **offline**; si se finaliza sin conexión, el relevamiento pasa a `Finalizado` **recién cuando se sincronizó todo**. |
| RN-16 | El backoffice debe permitir **revalidar contra RENAPER** los registros marcados "No validado RENAPER". |
| RN-17 | La app de campo **la desarrollamos nosotros** (entra en el alcance). |

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
**[16. Preguntas pendientes](#16-preguntas-pendientes-consolidado)** (cliente, técnicas y
de equipo, con su estado).

---

## 13. Asunciones a confirmar

- Jerarquía de 4 niveles explícita; "Programa" genérico aunque hoy solo Becas.
- "Aprobar" (admin) y "ocupar cupo" (post-SIS) son pasos distintos.
- RENAPER se valida en campo al cargar; la detección de duplicados se apoya en los 2 datos.
- Una persona rechazada por el admin queda con legajo creado igual.
- Rechazo informativo ⇒ persona rechazada **sin reproceso** en el sistema.

---

## 14. Próximos pasos

1. **Sistema SIS** — analizar el documento del cliente y cerrar preguntas 5 y 6.
2. **RENAPER** — relevar validación de identidad en campo.
3. **App de campo** — online/offline, sincronización, envío en lote.
4. **Control estricto** — cerrar todas las preguntas abiertas y verificar consistencia.
5. **Generación en GitHub** — épica → análisis → sub-issues (recién con todo cerrado).

---

## 15. Historial

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-06-04 | Versión inicial: consolidación backoffice (Secciones 1–7). | Pedido del usuario antes de abrir el bloque SIS. |

---

## 16. Preguntas pendientes (consolidado)

> **Todas las preguntas abiertas del análisis, juntas y al final.** Mientras existan
> pendientes **bloqueantes**, NO se generan issues (control estricto de `AGENTS.md`).
> Estado de cada una: 🔴 bloqueante · 🟡 no bloqueante (se asume y se confirma luego).

### 16.1 Sistema SIS (🔴 bloqueante — caja negra hasta respuesta del cliente)

| # | Pregunta | Para | Estado |
|---|---|---|:--:|
| S-1 | **Contrato de API.** ¿SIS expone una API REST? ¿Endpoint, autenticación, ambiente de prueba? ¿Es síncrono o asíncrono? | Cliente/Técnico | 🔴 |
| S-2 | **Datos de entrada.** ¿Qué campos se le envían por persona? (DNI/CUIL, datos del beneficio, id de programa, adjuntos) | Cliente/Técnico | 🔴 |
| S-3 | **Qué valida SIS.** ¿Qué significa su "OK"? (elegibilidad, no estar en beneficio incompatible, cruce de datos) | Cliente | 🔴 |
| S-4 | **Datos de salida.** ¿Qué devuelve exactamente? (OK/NO, código, motivo de rechazo, datos) | Cliente/Técnico | 🔴 |
| S-5 | **Rechazo de SIS.** Si responde NO, ¿la persona queda fuera o el admin corrige y reenvía? | Cliente | 🔴 |
| S-6 | **Asignación de cupo.** Con SIS OK: ¿ocupa cupo automáticamente (y manda a lista de espera si no hay) o el admin confirma a mano? | Cliente | 🔴 |
| S-7 | **Caída / error de SIS.** Si no responde o falla, ¿queda pendiente y se reintenta? ¿Timeout / aviso? | Cliente/Técnico | 🔴 |
| S-8 | **Cadena de 3 niveles.** ¿Becas llega hasta "ocupa cupo" o también hasta Ayudas Sociales / Liquidado (nivel 3)? | Cliente | 🔴 |
| S-9 | **Roles.** ¿"Supervisor/Operador" del RQ-002 son los mismos "Administrador/Territorial" de Becas? | Cliente | 🔴 |
| S-10 | **Convivencia cupo ↔ cadena SIS.** En el RQ-002 post-SIS va directo a Liquidado (sin cupo). ¿Dónde encaja el cupo/lista de espera? | Cliente | 🔴 |

### 16.2 Formulario y reglas de negocio

| # | Pregunta | Para | Estado |
|---|---|---|:--:|
| 2 | **Campos exactos del formulario** (aún sin definir). | Cliente | 🔴 |
| 1 | ¿Finalizar un relevamiento es **reversible** para el territorial? | Cliente | 🟡 |
| 3 | Cupo: ¿único por programa o puede haber **por zona/localidad/convocatoria**? | Cliente | 🟡 |
| 4 | Lista de espera: ¿**orden/prioridad** (FIFO) o elección libre del admin? | Cliente | 🟡 |
| 7 | ¿Un usuario puede ser **Admin de un programa y Territorial de otro** a la vez? | Cliente | 🟡 |
| 8 | "Relevamiento del día": ¿qué pasa si **no se inicia** ese día (vence/reprograma)? | Cliente | 🟡 |
| 9 | ¿El admin puede **editar datos** del formulario antes de aprobar? | Cliente | 🟡 |
| 10 | Legajo creado al enviar: ¿cómo se **marca** un legajo "relevado pero rechazado en Becas"? | Equipo/Cliente | 🟡 |

### 16.3 RQ-002 / cadena de aprobación (🔴 bloqueante — contradicciones a reconciliar)

| # | Pregunta | Para | Estado |
|---|---|---|:--:|
| 11 | **Roles:** ¿"Supervisor/Operador" del RQ-002 = "Administrador/Territorial" de Becas, o distintos? | Cliente | 🔴 |
| 12 | **Cadena de control:** ¿cómo conviven cupo/lista de espera con post-SIS → Ayudas Sociales/Liquidado? ¿El cupo se decide antes o después de SIS? | Cliente | 🔴 |
| 13 | **Sistema de Ayudas Sociales (nivel 3):** ¿dentro del alcance de Becas o es otro requerimiento? | Cliente | 🔴 |
| 14 | **Contrato técnico de SIS:** endpoint/API, campos, qué valida, qué devuelve, manejo de rechazo y caída. (= S-1…S-7) | Cliente/Técnico | 🔴 |
| 15 | **Disparo a SIS:** el RQ-002 se contradice (auto al aprobar vs botón manual "Enviar al SIS"). ¿Cuál es? | Cliente | 🔴 |
| 16 | **Alcance RQ-002:** ¿es parte de Becas o de una plataforma más amplia (login Google/OAuth, beneficios genéricos)? | Cliente | 🔴 |

### 16.4 Investigación de código pendiente (la hace el analista, no el cliente)

| # | Tarea | Estado |
|---|---|:--:|
| C-1 | Revisar duplicidad real en `apps/programas`, `apps/legajos`, `apps/ciudadanos`, `users` (qué existe hoy). | ⏳ |
| C-2 | Revisar épicas/análisis/tasks ya creados y el backlog del Project #1 (no duplicar trabajo encolado). | ⏳ |

### 16.5 Resumen del control estricto

- **No se generan issues** mientras haya 🔴 sin cerrar (SIS, campos del formulario, roles,
  cadena cupo↔RQ-002).
- Las 🟡 se pueden **asumir** y documentar como *Asunción a confirmar* sin frenar.
- Falta cerrar la **investigación de código** (C-1, C-2) antes de generar.
