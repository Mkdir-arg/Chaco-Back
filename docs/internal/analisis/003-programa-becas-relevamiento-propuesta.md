# Propuesta funcional — Programa Becas: Relevamiento territorial y asignación de cupos

**Tipo:** Propuesta de épica (documento de trabajo interno)
**Estado:** En análisis (borrador en construcción)
**Fecha:** 2026-06-04 · **Última actualización:** 2026-06-08
**Responsable (ICORE):** functional-analyst
**Programa:** Becas (primer programa sobre el módulo genérico de Programas)
**Módulos Django candidatos:** `apps/programas`, `apps/legajos`, `apps/ciudadanos`, `users` (roles/permisos)

> ⚠️ **Borrador en construcción.** Backoffice, **RENAPER** y **App de campo** ya están
> relevados; en esta ronda se incorporaron **Segmentos** y **requisitos** (general / de
> segmento) con **cupo por segmento**. Falta cerrar el **contrato técnico de SIS**, algunos
> pendientes finos de segmentos/roles y el **control estricto** antes de generar issues.
> Nada acá es definitivo: todas las **dudas y preguntas** están consolidadas al final, en
> la **Sección 16**.

---

## 1. Objetivo

Construir, en el **backoffice**, un módulo del **Programa Becas** que permita a un
**administrador** configurar convocatorias —cada una asociada a un **segmento** de la beca,
con sus **requisitos** y **cupo** propios— y **asignar relevamientos** a sus
**territoriales**. El territorial, desde una **app de campo** (externa, integrada vía
API), releva ciudadanos en terreno cargando **un formulario por persona**. Al finalizar,
los formularios llegan al backoffice, donde el administrador los **revisa caso por caso**
y los **aprueba o rechaza**. Las personas aprobadas pasan por una **validación contra el
Sistema SIS** y, según disponibilidad de **cupo del segmento**, ocupan una beca o quedan
en **lista de espera**.

---

## 2. Concepto / modelo del dominio

Jerarquía (actualizada con **Segmento** en esta ronda):

```
Programa  (Becas)
   └─ Convocatoria              (1..N; al crearla se selecciona UN Segmento)
        ├─ Segmento             (sub-modalidad de la beca → cupo propio + requisitos vía SIS)
        └─ Relevamiento         (campaña de campo, asignada a UN territorial, con fecha y zona)
             └─ Formulario       (N por relevamiento; cada uno = 1 persona / legajo)
```

| Entidad | Descripción | Notas clave |
|---|---|---|
| **Programa** | Marco genérico. Becas es el primero; Ñachec es otro programa. | El **cupo** vive a nivel **Segmento** (no a nivel Programa). |
| **Convocatoria** | Agrupador dentro del programa. Un programa tiene 1..N convocatorias. Al crearla se **selecciona un Segmento**. | — |
| **Segmento** | Sub-modalidad de la beca (Ladrilleros/Carboneros, Finalización de estudios "Joven", Cultural, Mamá Ñachec, Redes de Fe, Yo Deportista, Mi Casa Ñachec, Solidaria). | Define **cupo propio** y sus **requisitos específicos vienen de SIS**. |
| **Relevamiento** | Campaña de campo asignada a **un solo** territorial. Se **auto-nombra** "Relevamiento XXX". | Tiene territorial, fecha/plazo y zona/localidad. Reasignable. |
| **Formulario** | Una persona relevada. N por relevamiento. | **Campos aún no definidos** (pregunta abierta). |
| **Persona / Legajo** | El ciudadano relevado. Se busca en `legajos`: si existe se relaciona, si no se crea. | El legajo se crea **al enviar** el formulario. Una persona puede estar en **N programas** a la vez. La relación legajo↔programa se visualiza mediante **solapas dinámicas**: si el ciudadano tiene registro en la tabla programas, aparece la solapa correspondiente mostrando el estado (aprobado, rechazado, con cupo, etc.). |
| **Cupo** | Número de becas disponibles **por Segmento** (parametría: cantidad de segmentos + cupo por segmento). *(Antes era por Programa; reabierto por R-5.)* | Se ocupa **después** de validar con SIS, no al aprobar. |
| **Lista de espera** | Personas validadas-OK que no entraron por cupo lleno. | El admin promueve **a mano**. |

📌 *Asunción pendiente:* la jerarquía (Programa → Convocatoria/**Segmento** → Relevamiento →
Formulario) se modela explícita; "Programa" es genérico aunque hoy se arranque solo con
Becas. Ver detalle al final en **Sección 16.6**.

---

## 3. Actores y roles

| Actor | Tipo | Acceso / permisos | Qué hace |
|---|---|---|---|
| **Administrador del programa** | Rol **nuevo** (no existe hoy). Se apoya en el esquema de roles/permisos de `users`. | Acceso al **módulo del programa Becas**; el acceso por módulo depende de los roles asignados. Ve **todo** el programa. | Crea convocatorias y relevamientos, asigna/reasigna territoriales, revisa formularios (aprueba/rechaza con motivo), gestiona cupo y lista de espera, da de baja beneficiarios. |
| **Territorial** | Usuario del sistema con login propio. | Ve **solo sus** relevamientos y formularios. | Inicia el relevamiento del día asignado, carga formularios (1 por persona) en la app de campo, finaliza y envía todo junto. |

Por ahora **solo** estos dos roles. ⚠️ Sin embargo, la respuesta a "quién reprograma un
relevamiento vencido" introdujo la figura de un **"coordinador"** — rol no contemplado
acá. Hay que definir si se agrega como tercer rol o si es el Administrador (ver
**16.2-bis #8.b**).

📌 *Convivencia de perfiles (cerrada — pregunta 7):* un mismo usuario **sí puede tener los
dos roles a la vez** (Admin de un programa + Territorial de otro). El acceso por
módulo/programa depende de los roles asignados. Ver **RN-27**.

📌 *Impacto crítico:* el rol "Administrador de programa" es nuevo y se apoya en el
esquema de permisos existente en `users`. Hay que revisar cómo Chaco maneja roles hoy
para no inventar un esquema paralelo.

---

## 4. Funcionamiento end-to-end

1. **Configuración (admin).** El administrador configura el **Programa Becas**: define los
   **segmentos** y el **cupo por segmento** (parametría) y los **requisitos generales**
   (preguntas compartidas por todas las convocatorias). Crea una o varias **convocatorias**
   y, al crear cada una, **selecciona el segmento** → el sistema **consulta a SIS** los
   **requisitos específicos** de ese segmento, que quedan visibles en la convocatoria.
   Dentro de la convocatoria crea **relevamientos**; al crear un relevamiento define:
   **territorial asignado**, **fecha/plazo** y **zona/localidad**. El relevamiento se
   **auto-nombra** "Relevamiento XXX". Puede **reasignarlo** a otro territorial.
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
6. **Validación SIS (aprobados y rechazados).** Tanto si el admin **aprueba** como si **rechaza**, el sistema **automáticamente** dispara la validación contra SIS (**síncrona**: el admin espera la respuesta). Resultado de SIS: **Validado-Aprobado** o **Validado-Rechazado**.
7. **Asignación de cupo.** Si SIS aprueba y **hay cupo** disponible en el **segmento** → la
   persona **ocupa 1 cupo de ese segmento** en ese momento. Si el cupo del segmento está
   lleno → va a **lista de espera**. El siguiente caso que se apruebe ya ve el cupo
   actualizado.
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

📌 *Reversibilidad (cerrada — pregunta 1):* el paso a **Finalizado es reversible**. El
territorial puede **reabrir el operativo** (volver de `Finalizado` a `En curso`). **Falta
definir** el comportamiento cuando el admin ya empezó la revisión o ya disparó SIS sobre
algunos formularios (ver **16.2-bis #1.b**, 🔴). Ver **RN-26**.

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

📌 *Nota de terminología:* el estado "Enviado" corresponde al "Pendiente de Validación" de RQ-001 (documento del equipo Ministerio). Ambos refieren al mismo momento: el formulario llegó al backoffice y está esperando revisión del admin.

📌 *Nota:* la validación SIS no solo confirma identidad: también **evalúa los requisitos**
(generales + de segmento) al pedir el OKA (ver §6.2 y RN-33).

📌 *Asunción pendiente:* "aprobar" (admin) y "ocupar cupo" (post-SIS) son dos cosas
distintas. El detalle quedó consolidado al final en **Sección 16.6**.

---

## 6. Cupo, validación SIS y lista de espera

- El **cupo es del Segmento** (no del relevamiento ni del programa global; reabierto por
  R-5). El territorial releva **sin límite**.
- El **consumo de cupo NO ocurre al aprobar**, sino tras la validación **SIS**:
  admin confirma (OKA en Nodo) → **se dispara automáticamente** la consulta a SIS
  (**síncrona**: el admin espera la respuesta) → si SIS responde **OKA** y hay cupo →
  ocupa cupo; si SIS responde OKA y no hay cupo → lista de espera.
- **Validación SIS es síncrona y secuencial:** al aprobar un formulario, el sistema
  consulta SIS y **bloquea** hasta recibir respuesta. Esto garantiza que no hay race
  condition: el cupo se consume en ese momento y el siguiente caso ya ve el cupo actualizado.

**Flujo de revisión y validación SIS (secuencial):**

```
Admin abre formulario 1 → revisa → aprueba/rechaza → dispara validación SIS → espera respuesta de SIS
  → (SIS responde: asigna cupo / lista de espera / rechazado)
  → Admin cierra formulario 1
  → Admin abre formulario 2 → revisa → aprueba/rechaza → dispara validación SIS → espera respuesta de SIS
  → (SIS responde: asigna cupo / lista de espera / rechazado)
  → Admin cierra formulario 2
  → ...
```

📌 *El proceso es **estrictamente secuencial**: el admin no puede abrir/revisar otro formulario hasta que SIS responda al actual. Esto garantiza que el consumo de cupo es atómico y sin race conditions.*

📌 **Botón manual de revalidación:** Además del disparo automático, el backoffice ofrece un botón **"Validar contra SIS"** disponible en la pantalla de revisión de formularios para casos de reintento (timeout, error de SIS, o necesidad de revalidación posterior).

- Si el admin **rechaza** un formulario (en lugar de aprobar), **SÍ se envía a SIS** (ambos caminos —aprobar y rechazar— disparan validación SIS para verificar el estado en el sistema central).
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
- **Disparo a SIS:** automático y **síncrono** tanto al aprobar como al rechazar (ambas acciones disparan validación SIS). El admin espera la respuesta antes de continuar.
- Si SIS falla por timeout en Nodo, se muestra alerta en el registro para reintentar.
- Se mantiene el lenguaje propio: **Administrador/Territorial** =
  **Supervisor/Operador** del RQ-002.
- Con **OKA en SIS + OKA en Nodo**, el caso pasa a **liquidacion**.

➡️ El detalle de preguntas derivadas de estas contradicciones está consolidado en
**Sección 16.3 (preguntas 11 a 16)**.

📌 *Pendiente SIS (sigue diferido):* hace falta el **contrato técnico de SIS**.
Detalle de preguntas consolidado al final en **Sección 16.1 (S-1 a S-12)**.

---

## 6.2 Segmentos y requisitos de elegibilidad (✅ relevado en esta ronda)

### Segmento
Un **Segmento** es una **sub-modalidad de la beca**. Se **selecciona al crear la
convocatoria** (la convocatoria apunta a un segmento). Segmentos vigentes hoy:

- Ladrilleros, Carboneros y pequeños productores
- Finalización de estudios "Joven"
- Cultural
- Mamá Ñachec
- Redes de Fe
- Yo Deportista
- Mi Casa Ñachec
- Solidaria

📌 *A confirmar (origen del catálogo, R-1.b):* si el listado de segmentos es **local** (lo
parametrizamos) o lo **provee SIS**.
📌 *Nomenclatura:* varios segmentos nombran "Ñachec"; confirmar si el programa es "Becas" o
"Ñachec" (hoy §2 los trata como programas distintos).

### Dos tipos de requisitos

| Tipo | Origen | Configuración | Visibilidad | Quién evalúa |
|---|---|---|---|---|
| **Requisitos generales** | Definidos por nosotros | **Configurables** desde el panel de **Configuración del programa**. Son **preguntas compartidas por todas las convocatorias**. | — | **SIS**, al pedir el OKA |
| **Requisitos de segmento** | **Provienen de SIS** | Al crear la convocatoria y seleccionar el segmento, el sistema **consulta a SIS** y trae los requisitos específicos de ese segmento. | Se **visualizan una vez configurada la convocatoria**; los **territoriales los ven de forma informativa** al completar el formulario. | **SIS**, al pedir el OKA |

### Flujo de requisitos

1. El admin **crea una convocatoria** y **selecciona el segmento**.
2. El sistema **llama a SIS** y obtiene los **requisitos específicos del segmento**.
3. Esos requisitos **quedan visibles** en la convocatoria configurada.
4. En campo, el territorial los **ve de forma informativa** mientras completa el formulario
   (no los evalúa él).
5. En la revisión, cuando el admin **pide el OKA**, **SIS evalúa** los requisitos
   (generales + de segmento) como parte de la validación.

### Cupo por segmento (reabre pregunta 3)
El **cupo deja de ser único por programa**: ahora se **configura por segmento**. En la
**parametría del sistema** se define la **cantidad de segmentos** y el **cupo por
segmento**.

⚠️ *Impacto:* **reabre y reemplaza** la pregunta 3 (antes "cupo único por programa") y
modifica RN-01/02/03/19 y el modelo (§2). El consumo de cupo (post doble-OKA) descuenta del
**cupo del segmento** correspondiente (RN-34).

➡️ Pendientes finos en **§16.7** (R-1.b, R-6, R-8, R-9) y nuevas preguntas SIS en **§16.1
(S-11, S-12)**.

## 7. Pantallas del backoffice (mapa preliminar)

| Pantalla | Operaciones principales |
|---|---|
| **Convocatorias** | ABM + al crear **seleccionar el segmento** (dispara consulta a SIS de los requisitos del segmento, que quedan visibles en la convocatoria). Listar, editar, ver, (des)activar. |
| **Relevamientos** | ABM + **asignar/reasignar** territorial, fecha/plazo, zona. Ver estado. |
| **Revisión de relevamiento** | Entrar a un relevamiento finalizado → listado de formularios → abrir uno por uno → **aprobar/rechazar** (motivo). Botón **"Validar contra SIS"** disponible para revalidación manual. |
| **Beneficiarios / Cupo** | Ver ocupación de cupo, **lista de espera**, **dar de baja**, **promover** desde lista de espera. |
| **Configuración del programa** | Definir **segmentos** y **cupo por segmento** (parametría). Configurar **requisitos generales** (preguntas compartidas por todas las convocatorias). |
| **Reportes** | Exportar beneficiarios, lista de espera, avance de relevamientos. |

---

## 7.1. Campos del formulario (borrador preliminar según RQ-001)

Los campos del formulario están definidos por RQ-001 (Registro de Beneficiarios). Pendiente confirmación con Guido sobre campos adicionales específicos de Becas (ver pregunta 2 en § 16.2).

### Bloque A — Datos Personales (precargados por escaneo/RENAPER, editables)

| Campo | Características |
|---|---|
| Número de DNI | Texto – Obligatorio – Solo lectura (editable si error de escaneo) |
| Apellido | Texto – Obligatorio – Editable |
| Nombre | Texto – Obligatorio – Editable |
| Sexo | Lista desplegable (M / F / X) – Obligatorio |
| Estado Civil | Lista desplegable – Obligatorio |
| Fecha de Nacimiento | Fecha – Obligatorio – Dispara RN-22 (menor de edad → apoderado) |

### Bloque B — Domicilio (precargado, editable)

| Campo | Características |
|---|---|
| Provincia | Lista desplegable – Opcional |
| Localidad | Texto / Lista – Opcional |
| Calle | Texto – Opcional |
| Número | Número – Opcional |
| Piso | Número – Opcional |
| Departamento / Depto | Texto – Opcional |
| Barrio | Texto – Opcional |

### Bloque C — Contacto (ingreso manual obligatorio)

| Campo | Características |
|---|---|
| Número de celular | Numérico – Obligatorio |
| Correo electrónico (Mail) | Email – Obligatorio – Validar formato |

### Bloque D — Apoderado (visible solo si RN-22 detecta menor de edad)

| Campo | Características |
|---|---|
| Nombre del Apoderado | Texto – Obligatorio si sección visible |
| Apellido del Apoderado | Texto – Obligatorio si sección visible |
| Fecha de Nacimiento del Apoderado | Fecha – Obligatorio si sección visible |

### Adjuntos

| Documento | Obligatoriedad | Método de Carga |
|---|---|---|
| Foto DNI – Frente | Obligatorio | Cámara del dispositivo |
| Foto DNI – Dorso | Obligatorio | Cámara del dispositivo |
| Comprobante de CBU | Opcional | Adjuntar archivo o foto |
| Certificado de Domicilio | Opcional | Adjuntar archivo o foto |

---

## 8. Integraciones (bloque diferido — en relevamiento)

| Integración | Rol en el flujo | Estado del relevamiento |
|---|---|---|
| **Sistema SIS** | **Tres roles:** (1) **provee los requisitos del segmento** al configurar la convocatoria; (2) al pedir el OKA, **valida a la persona** y **evalúa los requisitos** (generales + segmento); (3) su OKA habilita **ocupar cupo**. | 🔻 En análisis (documento del equipo Ministerio pendiente). |
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
➡️ Las preguntas concretas (S-1…S-12) están consolidadas al final, en
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
| RN-01 | El cupo es **por Segmento** (parametría: cantidad de segmentos + cupo por segmento); el territorial releva sin límite. *(Antes por Programa; reabierto por R-5.)* |
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
| RN-24 | La validación SIS se **dispara automáticamente** tanto al aprobar como al rechazar un formulario (ambas acciones envían a SIS para verificación). La consulta a SIS es **síncrona**: el admin espera la respuesta antes de poder continuar con otro caso. Esto garantiza que el consumo de cupo es secuencial y sin race conditions. |
| RN-25 | Tanto la **aprobación** como el **rechazo** del admin envían el caso a SIS; la diferencia está en el contexto (aprobado vs rechazado en Nodo) que se envía junto con los datos. |
| RN-22 | Si la fecha de nacimiento indica que el beneficiario es **menor de edad (< 18 años)**, se habilita obligatoriamente la sección **Apoderado** (Nombre, Apellido, Fecha de Nacimiento). El formulario no puede finalizarse sin esos datos. Si el beneficiario es mayor de edad, la sección permanece oculta. |
| RN-23 | El territorial puede **editar los campos precargados** por escaneo o RENAPER en caso de error de lectura o domicilio desactualizado. |
| RN-26 | **Finalizar un relevamiento es reversible:** el territorial puede **reabrir el operativo** finalizado. *(Condiciones de reapertura cuando ya hubo revisión/SIS del admin: pendiente — ver 16.2-bis #1.b.)* |
| RN-27 | Un usuario **puede tener múltiples roles a la vez** (ej. **Administrador** de un programa y **Territorial** de otro). El acceso por módulo/programa depende de los roles asignados. |
| RN-28 | El relevamiento que **no se inicia el día asignado vence** y debe **reprogramarse** (nueva fecha). *(Quién reprograma: pendiente — ver 16.2-bis #8.b.)* |
| RN-29 | El admin **puede editar los datos del formulario** desde el backoffice **antes de aprobar/rechazar**. *(Traza y campos no editables: pendiente — ver 16.2-bis #9.b.)* |
| RN-30 | Un **Segmento** es una sub-modalidad de la beca. La **convocatoria** apunta a un segmento (se selecciona al crearla). |
| RN-31 | **Requisitos generales:** preguntas **configurables** desde Configuración del programa, **compartidas por todas las convocatorias**. |
| RN-32 | **Requisitos de segmento:** los **provee SIS** al seleccionar el segmento en la convocatoria; se muestran **informativos** al territorial al completar el formulario (no los evalúa él). |
| RN-33 | La **evaluación** de requisitos (generales + de segmento) la hace **SIS** cuando el admin **pide el OKA**. |
| RN-34 | El **cupo se descuenta del segmento** correspondiente, tras doble-OKA (Nodo + SIS). |

---

## 10. Dependencias e impacto crítico

- **`users` / permisos:** rol nuevo "Administrador de programa", acceso por módulo según
  roles. No inventar esquema paralelo.
- **`legajos` / `ciudadanos`:** la persona = legajo. Reusar identificación existente
  (DNI/CUIL) y la relación legajo↔programa. Revisar duplicidad de personas. La relación
  legajo↔programa se visualiza mediante **solapas dinámicas**: si el ciudadano tiene
  registro en la tabla programas, aparece la solapa correspondiente mostrando el estado
  (aprobado, rechazado, con cupo, en lista de espera, etc.).
- **Integraciones externas:** SIS, RENAPER, App de campo (API).
- **Módulo Programas (`apps/programas`):** base genérica donde se apoya Becas.

📌 *Pendiente de investigación de código* (al cerrar el interrogatorio): confirmar qué
ofrecen hoy `apps/programas`, `apps/legajos`, `apps/ciudadanos` y `users` para no duplicar.

---
## Diagrama de Flujo
<iframe width="768" height="640" src="https://miro.com/app/live-embed/uXjVJzk5lbQ=/?focusWidget=3458764674758430959&embedMode=view_only_without_ui&embedId=49042054955" frameborder="0" scrolling="no" allow="fullscreen; clipboard-read; clipboard-write" allowfullscreen></iframe>

## 11. Fuera de alcance (por ahora)

- **Notificaciones** a territoriales o ciudadanos.
- **Reproceso** de personas rechazadas por el admin (rechazo es informativo).
- Diseñador de formularios dinámicos para el **formulario de la persona** (sus **campos son
  fijos**, definidos por nosotros). *(Distinto de los **requisitos generales**, que sí son
  configurables — ver §6.2 / RN-31.)*

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

1. **Sistema SIS** — analizar el documento del equipo Ministerio y cerrar S-1, S-2, S-4,
   S-5 y las nuevas **S-11/S-12** (requisitos por segmento + evaluación en el OKA).
2. **Segmentos / requisitos** — cerrar **R-1.b** (origen del catálogo de segmentos) y la
   cardinalidad convocatoria↔segmento (**R-8**).
3. **Roles y flujo** — resolver **8.b** (¿rol Coordinador o es el Admin?) y **1.b**
   (reapertura de relevamiento cuando ya hay revisión/SIS en curso).
4. **Investigación de código** — completar C-1 (revisar módulos existentes).
5. **Control estricto** — cerrar todas las preguntas 🔴 bloqueantes y verificar consistencia.
6. **Generación en GitHub** — épica → análisis → sub-issues (recién con todo cerrado).

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
| S-11 | **Requisitos por segmento (entrada).** ¿Qué endpoint/contrato expone SIS para **devolver los requisitos** de un segmento al configurar la convocatoria? | Equipo Ministerio/ICORE | 🔴 |
| S-12 | **Evaluación de requisitos (OKA).** Al pedir el OKA, ¿cómo se le envían a SIS las respuestas de los requisitos (generales + segmento) y cómo devuelve el resultado de la evaluación? | Equipo Ministerio/ICORE | 🔴 |

### 16.2 Formulario y reglas de negocio

| # | Pregunta | Para | Estado |
|---|---|---|:--:|
| 2 | **Campos exactos del formulario.** RQ-001 define una base: Bloque A (DNI, Apellido, Nombre, Sexo, Estado Civil, Fecha de Nacimiento), Bloque B (Domicilio: Provincia, Localidad, Calle, Número, Piso, Departamento, Barrio), Bloque C (Celular, Mail — manual obligatorio), Bloque D (Apoderado — condicional menor de edad), Adjuntos (Foto DNI frente/dorso obligatorios; CBU y Cert. domicilio opcionales). **Pendiente confirmar con Guido** si estos son los campos definitivos o si hay campos adicionales para Becas. | Guido (Equipo Ministerio) | 🟡 |

📌 **Preguntas cerradas en esta sección:**
- **Pregunta 3 (Cupo):** ⚠️ **Reabierta y reemplazada por R-5.** El cupo **ya no es único por programa**: ahora es **por segmento** (parametría: cantidad de segmentos + cupo por segmento). Ver §6.2 y RN-01/34.
- **Pregunta 10 (Legajo rechazado):** Cerrada. El legajo usa solapas dinámicas: si el ciudadano tiene registro en la tabla programas, aparece la solapa correspondiente; si está rechazado en Becas, la solapa se habilita y muestra el estado "Rechazado".
- **Pregunta 1 (Reversibilidad del relevamiento):** Cerrada. Finalizar un relevamiento **es reversible**: el territorial puede **reabrir el operativo** (ver RN-26). *Sub-pregunta derivada abierta (1.b):* qué pasa con los formularios ya enviados/en revisión por el admin cuando el territorial reabre — ver §16.2-bis.
- **Pregunta 7 (Doble rol):** Cerrada. Un usuario **sí puede tener los dos roles** simultáneamente (Admin de un programa y Territorial de otro). Ver RN-27.
- **Pregunta 8 (Relevamiento del día no iniciado):** Cerrada en su base. Si no se inicia el día asignado, el relevamiento **vence** y **se reprograma** (ver RN-28). *Sub-pregunta derivada abierta (8.b):* quién reprograma — la respuesta menciona un **"coordinador"**, rol que **hoy el documento declara inexistente** (§3 dice "solo Admin y Territorial"). Ver §16.2-bis.
- **Pregunta 9 (Admin edita formulario):** Cerrada. El admin **sí puede editar los datos del formulario desde el backoffice** antes de aprobar (ver RN-29).

### 16.2-bis Sub-preguntas derivadas de esta ronda (nuevas)

| # | Pregunta | Para | Estado |
|---|---|---|:--:|
| 1.b | Al **reabrir** un relevamiento finalizado: ¿se "recuperan" los formularios ya enviados al backoffice? ¿Qué pasa si el admin ya **aprobó/rechazó** o ya **disparó SIS** sobre algunos? ¿Se permite reabrir solo si la revisión no empezó? | Equipo Ministerio | 🔴 |
| 8.b | El reprogramar lo hace un **"coordinador"**. Hoy §3 dice que **solo existen Admin y Territorial**. ¿Se agrega el rol **Coordinador** o "coordinador" = el Administrador? | Equipo Ministerio | 🔴 |
| 9.b | Cuando el admin **edita** el formulario antes de aprobar: ¿queda **traza** (quién/cuándo/valor anterior)? ¿Hay campos no editables (ej. DNI validado por RENAPER/escaneo)? | Equipo Ministerio | 🟡 |

### 16.3 RQ-002 / cadena de aprobación

| # | Pregunta | Para | Estado |
|---|---|---|:--:|
| 13 | **Sistema de Ayudas Sociales (nivel 3):** ¿dentro del alcance de Becas o es otro requerimiento? | Equipo Ministerio | 🔴 |
| 14 | **Contrato técnico de SIS:** endpoint/API, campos, qué valida, qué devuelve, manejo de rechazo y caída. (= S-1…S-7) | Equipo Ministerio/ICORE | 🔴 |

📌 **Preguntas cerradas en esta sección:**
- **Pregunta 12 (Cadena de control):** Cerrada. El cupo se decide en **Becas (nivel 1)**, no en sistemas posteriores. La cadena completa (Nodo → SIS nivel 2 → Ayudas Sociales nivel 3) se revisará hoy con el equipo Ministerio para definir alcance exacto.
- **Pregunta 15 (Disparo a SIS):** Cerrada. El sistema implementa **ambas opciones**: (1) disparo automático y síncrono al aprobar/rechazar (el admin espera respuesta antes de continuar), y (2) botón manual "Validar contra SIS" disponible en Nodo para reintentos o validaciones posteriores.

### 16.4 Investigación de código pendiente (responsabilidad de ICORE)

| # | Tarea | Estado |
|---|---|:--:|
| C-1 | Revisar duplicidad real en `apps/programas`, `apps/legajos`, `apps/ciudadanos`, `users` (qué existe hoy). | ⏳ |

### 16.5 Resumen del control estricto

- **No se generan issues** mientras haya 🔴 sin cerrar: SIS (S-1/2/4/5/11/12, 13, 14),
  cadena cupo↔RQ-002, segmentos (R-1.b), reapertura de relevamiento (1.b) y rol Coordinador (8.b).
- Las 🟡 se pueden **asumir** y documentar como *Asunción a confirmar* sin frenar.
- Falta cerrar la **investigación de código** (C-1) antes de generar.

### 16.7 Requisitos de elegibilidad (general / segmento)

📌 **Cerradas en esta ronda** (detalle en §6.2):
- **R-1 (qué es segmento):** sub-modalidad de la beca; se selecciona al crear la
  convocatoria. Catálogo actual: 8 segmentos (ver §6.2).
- **R-2 (requisitos generales):** preguntas compartidas por todas las convocatorias.
- **R-3 (requisitos de segmento):** los provee **SIS** al seleccionar el segmento; se ven
  informativos para el territorial al completar el formulario.
- **R-4 (quién/cuándo evalúa):** **SIS** los evalúa cuando el admin **pide el OKA**.
- **R-5 (cupo):** **cupo por segmento** (reabre y reemplaza la pregunta 3). Parametría:
  cantidad de segmentos + cupo por segmento.
- **R-7 (configurabilidad generales):** configurables desde Configuración del programa.

| # | Pregunta abierta | Para | Estado |
|---|---|---|:--:|
| R-1.b | **Origen del catálogo de segmentos:** ¿lo parametrizamos local o lo provee SIS? | Equipo Ministerio | 🔴 |
| R-6 | **Asignación persona↔segmento:** ¿queda determinado por la convocatoria (implícito) o se asigna por persona? ¿Puede una persona estar en más de un segmento? | Equipo Ministerio | 🟡 |
| R-8 | **Cardinalidad convocatoria↔segmento:** ¿una convocatoria apunta a **un solo** segmento o puede tener **varios**? (impacta cómo se configura el cupo por segmento) | Equipo Ministerio | 🟡 |
| R-9 | **Requisitos generales = ¿campos del formulario?** ¿Las "preguntas" generales se responden en el formulario que carga el territorial, o son criterios que evalúa SIS sobre datos ya cargados? | Equipo Ministerio | 🟡 |

### 16.6 Asunciones pendientes de confirmación

| # | Asunción / duda | Estado |
|---|---|:--:|
| A-1 | Jerarquía explícita Programa → Convocatoria/**Segmento** → Relevamiento → Formulario; "Programa" se modela genérico aunque hoy solo se use Becas. | 🟡 |
| A-2 | "Aprobar" en backoffice y "ocupar cupo" son pasos distintos (el cupo se decide después de SIS). | 🟡 |
| A-3 | RENAPER en campo usa la misma API (o equivalente) que backoffice para validar identidad. | 🟡 |
| A-4 | Una persona rechazada por admin conserva legajo creado (sin reproceso en el sistema). | 🟡 |
