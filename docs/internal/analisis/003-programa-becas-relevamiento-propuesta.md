# Propuesta funcional — Programa Becas: Relevamiento territorial y asignación de cupos

**Tipo:** Propuesta de épica (documento de trabajo interno)
**Estado:** En análisis (borrador en construcción)
**Fecha:** 2026-06-04 · **Última actualización:** 2026-06-16
**Responsable (ICORE):** functional-analyst
**Programa:** Becas (primer programa sobre el módulo genérico de Programas)
**Módulos Django candidatos:** `apps/programas`, `apps/legajos`, `apps/ciudadanos`, `users` (roles/permisos)

> **Borrador en construcción.** Última ronda: **requisitos nativos** (ya no vienen de SIS),
> **subsegmento**, **Coordinador** (= validador territorial), **control de incompatibilidades**,
> regla **RENAPER/escaneo** y **catálogo oficial** de segmentos. **Permanencia/seguimiento y
> estados extendidos → Versión 2.** Falta cerrar el **contrato técnico de SIS** y varios
> pendientes. Todas las **dudas y preguntas** están al final, en la **Sección 16**.

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

Jerarquía (actualizada: se agrega **Subsegmento**; los requisitos de segmento pasan a ser nativos):

```
Programa  (Becas)
   └─ Convocatoria              (1..N; al crearla se selecciona UN Segmento)
        ├─ Segmento             (sub-modalidad de la beca → cupo propio + requisitos NATIVOS configurables)
        │     └─ Subsegmento    (nivel opcional configurable, ej. Ladrillo / Carbón en Producción Territorial)
        └─ Relevamiento         (campaña de campo, asignada a UN territorial, con fecha y zona)
             └─ Formulario       (N por relevamiento; cada uno = 1 persona / legajo)
```

| Entidad | Descripción | Notas clave |
|---|---|---|
| **Programa** | Marco genérico. Becas es el primero; Ñachec es otro programa. | El **cupo** vive a nivel **Segmento** (no a nivel Programa). |
| **Convocatoria** | Agrupador dentro del programa. Un programa tiene 1..N convocatorias. Al crearla se **selecciona un Segmento**. | — |
| **Segmento** | Sub-modalidad de la beca (Producción Territorial/Fuego y Barro, Cultura/Mi Pequeño Artista, Futuro Joven, Comunidades Originarias/Mamá Ñachec, Redes de Fe, Deportes/Talento Deportivo, Vivienda/Casa Ñachec — ver §6.2). | Define **cupo propio** y sus **requisitos específicos NATIVOS** (configurables; **ya no vienen de SIS**). |
| **Subsegmento** | Nivel **opcional configurable** dentro de un segmento (ej. **Ladrillo / Carbón** en Producción Territorial). | Tiene **`cupo_maximo` propio** y puede tener requisitos propios. La suma de cupos de los subsegmentos de un segmento no puede superar el cupo del segmento (RN-40). |
| **Relevamiento** | Campaña de campo asignada a **un solo** territorial. Se **auto-nombra** "Relevamiento XXX". | Tiene territorial, fecha/plazo y zona/localidad. Reasignable. |
| **Formulario** | Una persona relevada. N por relevamiento. | Campos: ver **§7.1** + requisitos generales (13 preguntas) y de segmento. |
| **Persona / Legajo** | El ciudadano relevado. Se busca en `legajos`: si existe se relaciona, si no se crea. | El legajo se crea **al enviar** el formulario. Una persona puede estar en **N programas** a la vez. La relación legajo↔programa se visualiza mediante **solapas dinámicas**: si el ciudadano tiene registro en la tabla programas, aparece la solapa correspondiente mostrando el estado (aprobado, rechazado, con cupo, etc.). |
| **Cupo** | Número de becas disponibles **por Segmento**. Si el segmento **no tiene subsegmentos**, el cupo del segmento es el total. Si **tiene subsegmentos**, el cupo se distribuye: cada uno tiene su propio `cupo_maximo` y `sum(subsegmentos.cupo_maximo) <= segmento.cupo_maximo` (RN-40). | Se ocupa **después** de validar con SIS, no al aprobar. |
| **Lista de espera** | Personas validadas-OK que no entraron por cupo lleno. | El admin promueve **a mano**. |

---

## 3. Actores y roles

| Actor | Tipo | Acceso / permisos | Qué hace |
|---|---|---|---|
| **Administrador del programa** | Rol **nuevo** (no existe hoy). Se apoya en el esquema de roles/permisos de `users`. | Acceso al **módulo del programa Becas**; el acceso por módulo depende de los roles asignados. Ve **todo** el programa. | Crea convocatorias y relevamientos, asigna/reasigna territoriales, revisa formularios (aprueba/rechaza con motivo), gestiona cupo y lista de espera, da de baja beneficiarios. |
| **Territorial** | Usuario del sistema con login propio. | Ve **solo sus** relevamientos y formularios. | Inicia el relevamiento del día asignado, carga formularios (1 por persona) en la app de campo, finaliza y envía todo junto. |
| **Coordinador** (= validador territorial) | Rol **nuevo** (tercero). | Habilitado para validar a nivel territorial. | **Valida las postulaciones** (referentes/municipios/consorcios/autoridades operan bajo este rol) y **reprograma** relevamientos vencidos (RN-28). |

Hay **tres roles**: Administrador, Territorial y **Coordinador** (= validador territorial).

**Convivencia de perfiles:** un mismo usuario **sí puede tener los dos roles a la vez**
(Admin de un programa + Territorial de otro). El acceso por módulo/programa depende de los
roles asignados. Ver **RN-27**.

**Nota de diseño:** el rol "Administrador de programa" es nuevo y se apoya en el esquema de
permisos existente en `users`. Hay que revisar cómo Chaco maneja roles hoy para no inventar
un esquema paralelo.

---

## 4. Funcionamiento end-to-end

1. **Configuración (admin).** El administrador configura el **Programa Becas**: define los
   **segmentos** (y **subsegmentos** si corresponde), el **cupo por segmento** (parametría),
   los **requisitos generales** (compartidos por todas las convocatorias) y los **requisitos
   de cada segmento** (**nativos, configurables**; ya no vienen de SIS). Crea una o varias
   **convocatorias** y, al crear cada una, **selecciona el segmento**; sus requisitos quedan
   visibles en la convocatoria. Dentro de la convocatoria crea **relevamientos**; al crear un
   relevamiento define: **territorial asignado**, **fecha/plazo** y **zona/localidad**. El
   relevamiento se **auto-nombra** "Relevamiento XXX". Puede **reasignarlo** a otro territorial.
2. **Inicio en campo (territorial).** El territorial entra a la app, ve el **listado de
   sus relevamientos** asignados y **solo puede iniciar el relevamiento del día**.
3. **Carga (territorial).** Dentro del relevamiento carga **un formulario tras otro**
   (1 por persona). Al iniciar cada formulario, el sistema determina la **forma de
   validar identidad** según conectividad (ver §8.2 para detalle completo): puede
   **escanear el DNI** (lectura directa del chip/código del documento), **validar con
   RENAPER** (ingreso manual de DNI + sexo), o **cargar manual** si no hay conexión. Luego
   completa lo que no autocompleta RENAPER/escaneo: **contacto, estudios, situación laboral,
   los requisitos generales (13 preguntas), los del segmento, GPS y adjuntos**; si es **menor**,
   los datos del **apoderado**. **No** puede dejar un formulario a medias.
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

**Reversibilidad:** el paso a **Finalizado es reversible**. El territorial puede **reabrir el
operativo** (vuelve de `Finalizado` a `En curso`) **para sumar más personas**. Los
**formularios ya enviados no se tocan**: conservan su estado (en revisión, aprobado,
rechazado, validado). Al re-finalizar se **envían solo los nuevos**. Ver **RN-26**.

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

**Nota de terminología:** el estado "Enviado" corresponde al "Pendiente de Validación" de
RQ-001 (documento del equipo Ministerio). Ambos refieren al mismo momento: el formulario
llegó al backoffice y está esperando revisión del admin.

**Nota:** la validación SIS confirma identidad y hace el **control de incompatibilidades**
(OKA/negativa). Los **requisitos de elegibilidad** son **nativos** (configurables, §6.2): los
valida **Nodo** (admin/coordinador); SIS solo hace las **incompatibilidades** (RN-33).

---

## 6. Cupo, validación SIS y lista de espera

- El **cupo es del Segmento** (no del relevamiento ni del programa global). Si el segmento **no tiene subsegmentos**, el cupo del segmento es el total. Si **tiene subsegmentos**, cada uno tiene su propio `cupo_maximo`; la suma no puede superar el del segmento (RN-40). El territorial releva **sin límite**.
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

El proceso es **estrictamente secuencial**: el admin no puede abrir/revisar otro formulario
hasta que SIS responda al actual. Esto garantiza que el consumo de cupo es atómico y sin
race conditions.

**Botón manual de revalidación:** además del disparo automático, el backoffice ofrece un
botón **"Validar contra SIS"** disponible en la pantalla de revisión de formularios para
casos de reintento (timeout, error de SIS, o necesidad de revalidación posterior).

- Si el admin **rechaza** un formulario (en lugar de aprobar), **SÍ se envía a SIS** (ambos caminos —aprobar y rechazar— disparan validación SIS para verificar el estado en el sistema central).
- **Lista de espera:** el admin **promueve a mano**. Al dar de baja a un beneficiario, el
  sistema dispara una **alerta proactiva** para mover a alguien de la lista.
- Si existe **OKA en Nodo + OKA en SIS**, el caso queda habilitado para pasar al
  **sistema de liquidacion**.

### 6.1 Hallazgos del documento del equipo Ministerio (URD RQ-002 — "Tablero de Aprobación N1")

El equipo Ministerio entregó el documento **RQ-002** (Tablero de Aprobación de Primer Nivel e
Integración SIS). **No resuelve el contrato técnico de SIS**, pero aporta encuadre:

**Aporta:**
- **SIS = Sistema de Inclusión Social**, **segundo nivel de control**, recibe los datos
  aprobados vía **API REST** y hace su propio control intermedio.
- Aparece un **tercer sistema: "Sistema de Ayudas Sociales"** (sistema madre de
  **liquidación**, nivel 3) que graba definitivamente para pagar el beneficio.
- Cadena real de control: **Aprobación Nivel 1 (nuestro backoffice) → SIS (Nivel 2) →
  Ayudas Sociales (Nivel 3, liquidación)**.

**NO responde (sigue pendiente):** qué se manda exactamente (sin contrato de campos/API)
y qué devuelve SIS en detalle (estructura/campos).

**Definiciones acordadas en esta ronda:**
- SIS responde **OKA** = válido. Se espera confirmación o rechazo con motivo.
- Para ocupar cupo debe existir **OKA del administrador en Nodo + OKA de SIS**.
- **Disparo a SIS:** automático y **síncrono** tanto al aprobar como al rechazar (ambas acciones disparan validación SIS). El admin espera la respuesta antes de continuar.
- Si SIS falla por timeout en Nodo, se muestra alerta en el registro para reintentar.
- Se mantiene el lenguaje propio: **Administrador/Territorial** =
  **Supervisor/Operador** del RQ-002.
- Con **OKA en SIS + OKA en Nodo**, el caso pasa a **liquidacion**.

---

## 6.2 Segmentos, subsegmentos y requisitos de elegibilidad

### Segmento y subsegmento
Un **Segmento** es una **sub-modalidad de la beca**; se **selecciona al crear la
convocatoria**. Un **Subsegmento** es un nivel **opcional** dentro del segmento. Ambos son
**configurables** (ABM en Configuración del programa). Catálogo oficial (doc Ministerio):

| Segmento | Subsegmentos |
|---|---|
| Producción Territorial / Fuego y Barro | **Ladrillo**, **Carbón** |
| Cultura / Mi Pequeño Artista | — |
| Futuro Joven | — |
| Comunidades Originarias / Mamá Ñachec | — |
| Redes de Fe | — |
| Deportes / Talento Deportivo | — |
| Vivienda / Casa Ñachec | — |

### Requisitos: ahora NATIVOS (cambio de definición)
Los **requisitos de segmento ya NO vienen de SIS.** Son **nativos** del sistema: se
**agregan/configuran al configurar el segmento** (y subsegmento). Los requisitos nativos los
valida **Nodo** (admin/coordinador); SIS solo hace el **control de incompatibilidades**
(OKA/negativa).

| Tipo | Configuración | Visibilidad |
|---|---|---|
| **Requisitos generales** | Configurables en **Configuración del programa**; aplican a **todos los segmentos**. Son el **Cuestionario social de 13 preguntas** (§6.3). | **Se responden en el formulario** por todo beneficiario. |
| **Requisitos de segmento / subsegmento** | **Nativos, configurables** al configurar el segmento/subsegmento. | Quedan visibles en la convocatoria; informativos para el territorial. |

### Requisitos generales del sistema (doc Ministerio — todos los segmentos)
- **Registro único** del beneficiario: datos personales, domicilio, CUIL, **estudios**,
  **situación laboral**, localidad, **segmento asignado** y **estado del trámite**.
- **Documentación obligatoria** (ver §7.1): DNI, certificado de domicilio, CUIL, constancia
  de estudios, **convenio de confidencialidad / uso de imagen**, + doc específica por segmento.
- **Validación territorial** por el **Coordinador** (referentes/municipios/consorcios/autoridades).
- **Geolocalización GPS** cuando el segmento lo requiera (ej. Producción, Vivienda).
- **Control de incompatibilidades = lo hace SIS** (es el **OKA / negativa** que devuelve la
  integración): residencia fuera del Chaco, planta/contrato estatal, otros programas
  incompatibles, relación de dependencia, ingresos > 3 SMVM y otras que defina la autoridad.
  Una **negativa de SIS = incompatibilidad detectada** (con motivo); sin OKA no ocupa cupo.
- **Asignación** por segmento/subsegmento, localidad, referente y estado administrativo.
- *(Seguimiento administrativo y estados extendidos → Versión 2, ver §11.1.)*

**Regla de carga (RENAPER/escaneo) — RN-37:** los datos que provee **RENAPER o el escaneo de
DNI** (apellido, nombre, fecha de nacimiento, CUIL, sexo, domicilio) **no se preguntan** —
vienen autocompletados. **Solo se cargan a mano si no hay conexión.**

### Cupo por segmento y subsegmento
El **cupo se configura por segmento** (parametría; RN-01/34/40). Regla:
- **Sin subsegmentos:** el `cupo_maximo` del segmento es el cupo total.
- **Con subsegmentos:** cada subsegmento tiene su propio `cupo_maximo`; la suma no puede superar el del segmento (`sum(subsegmentos.cupo_maximo) <= segmento.cupo_maximo`). El sistema valida esta restricción al crear o editar el cupo de un subsegmento (RN-40).

El consumo (post doble-OKA) descuenta del **cupo del subsegmento** (si aplica) o del **segmento**.

Detalle de **requisitos por segmento** y el **Cuestionario social (13 preguntas)** en el
**Anexo §6.3**.

## 6.3 Anexo — Requisitos por segmento y Cuestionario social (doc Ministerio)

- **Producción Territorial / Fuego y Barro** (subsegmentos **Ladrillo / Carbón**): actividad
  productiva actual/reciente, lugar de trabajo/producción, **fotos del lugar**, **GPS**,
  validación territorial/institucional/sectorial, sublínea. *Permanencia (V2): mantener actividad.*
- **Cultura / Mi Pequeño Artista:** edad 7–16, disciplina artística, aval (docente/escuela/espacio
  cultural), evidencias (fotos/videos/muestras), validación, **adulto responsable**. *Permanencia (V2).*
- **Futuro Joven:** alumno regular del último año secundario, promedio, asistencia, materias
  aprobadas, validación del establecimiento, adulto responsable si corresponde. *Permanencia (V2).*
- **Comunidades Originarias / Mamá Ñachec:** vínculo con comunidad originaria, embarazo desde
  6.º mes o maternidad de niño ≤ 2 años, constancia médica/carnet sanitario, validación. *Permanencia (V2).*
- **Redes de Fe:** datos del espacio religioso/comunitario, **registro de culto provincial**,
  informe de actividades barriales, estado edilicio/necesidades, acciones con comunidad,
  validación. Destino: mejoras edilicias/mantenimiento. *Permanencia (V2).*
- **Deportes / Talento Deportivo:** disciplina, participación activa, aval (club/profesor/escuela),
  reconocimiento por desempeño, validación, adulto responsable si corresponde. *Permanencia (V2).*
- **Vivienda / Casa Ñachec:** residencia efectiva, necesidad de mejora/reparación, tipo de
  intervención, **fotos del estado actual**, validación, acreditación del destino. Destino:
  reparaciones/mejoras habitacionales. *Permanencia (V2).*

**Menores de edad:** los segmentos con menores exigen **adulto responsable, autorización y
documentación respaldatoria** (alinea con RN-22 / Bloque D del formulario).

### Cuestionario de Relevamiento Social (13 preguntas) = REQUISITOS GENERALES (todos los segmentos)
Estas 13 preguntas **son los requisitos generales** — las **preguntas que responde todo
beneficiario** en el formulario (sección general, compartida por todas las convocatorias y
segmentos).

1. Tenencia de la vivienda (propia + acreditación: Escritura/RUBH/RENABAP/Boleto).
2. Servicios básicos (luz; agua: red/pozo).
3. Saneamiento (baño: interno/externo/no posee).
4. Composición del hogar (total + por rangos: menores de 18, 18–59, 60+).
5. Documentación del grupo familiar (DNI + partida; cuántos faltan).
6. Embarazo en el hogar.
7. Discapacidad (tipo, CUD, pensión).
8. Educación del hogar (secundario adultos; asistencia de menores 4–17).
9. Asistencia médica y vacunas (efector: CAPS/Hospital; carnet completo).
10. Situación laboral (formal/informal/ninguno + cantidad).
11. Programas sociales (AUH, Tarjeta Alimentar, pensiones/jubilaciones, ninguno).
12. Cobertura Caja Ñachec / Operativo Impenetrable.
13. Capital social y asistencia comunitaria (club/iglesia/centro; comedor/merendero).

## 7. Pantallas del backoffice (mapa preliminar)

| Pantalla | Operaciones principales |
|---|---|
| **Convocatorias** | ABM + al crear **seleccionar el segmento**; sus requisitos (nativos del segmento) quedan visibles en la convocatoria. Listar, editar, ver, (des)activar. |
| **Relevamientos** | ABM + **asignar/reasignar** territorial, fecha/plazo, zona. Ver estado. |
| **Revisión de relevamiento** | Entrar a un relevamiento finalizado → listado de formularios → abrir uno por uno → **aprobar/rechazar** (motivo). Botón **"Validar contra SIS"** disponible para revalidación manual. |
| **Validación territorial (Coordinador)** | El coordinador **valida las postulaciones** del territorio y **reprograma** relevamientos vencidos. |
| **Beneficiarios / Cupo** | Ver ocupación de cupo, **lista de espera**, **dar de baja**, **promover** desde lista de espera. |
| **Configuración del programa** | ABM de **segmentos y subsegmentos**, **cupo por segmento** (parametría), **requisitos generales** y **requisitos por segmento/subsegmento** (nativos). |
| **Reportes** | Exportar beneficiarios, lista de espera, avance de relevamientos. |

---

## 7.1. Campos del formulario (borrador preliminar según RQ-001)

Los campos del formulario están definidos por RQ-001 (Registro de Beneficiarios).

**Regla de carga (RN-37):** los campos del **Bloque A** (salvo Estado Civil) y el **Bloque B**
los **autocompleta RENAPER/escaneo** → **no se preguntan**; solo se cargan a mano **sin
conexión**. Del **Registro único** se suman: **estudios**, **situación laboral** y
**geolocalización GPS** (según segmento).

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
| Certificado de Domicilio | Obligatorio | Adjuntar archivo o **imagen en el formulario** |
| CUIL | Obligatorio | Autocompletado por RENAPER (no se sube si valida) |
| Constancia de estudios | Obligatorio | Adjuntar archivo o foto |
| Convenio de confidencialidad / uso de imagen | Obligatorio | Adjuntar archivo o foto |
| Comprobante de CBU | Opcional | Adjuntar archivo o foto |
| Documentación específica del segmento (fotos del lugar, evidencias, etc.) | Según segmento | **Imágenes capturadas en el formulario** / adjuntar |

Algunos adjuntos por segmento son **imágenes que se capturan dentro del formulario** (fotos
del lugar de producción, estado de la vivienda, evidencias artísticas/deportivas).

---

## 8. Integraciones (bloque diferido — en relevamiento)

| Integración | Rol en el flujo | Estado del relevamiento |
|---|---|---|
| **Sistema SIS** | **Dos roles:** (1) al pedir el OKA, **valida a la persona** y hace el **control de incompatibilidades** → devuelve **OKA / negativa**; (2) su **OKA habilita ocupar cupo**. *(Los requisitos de elegibilidad son **nativos**, NO los provee SIS.)* | En análisis (contrato técnico pendiente). |
| **RENAPER** | Valida la identidad (DNI + sexo) **al cargar** cada persona en campo. | **Relevada y probada** (reusa integración existente). |
| **App de campo** | App **propia** (la desarrollamos nosotros). Funciona **online/offline**, sincroniza al recuperar señal; al finalizar offline confirma tras sync. | **Relevada** (alcance propio). |

**Impacto crítico:** offline + envío en lote + validación RENAPER en campo es alcance grande
y depende de las 3 integraciones.

### 8.0 RENAPER — integración relevada (cerrada)

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

**Regla:** sin respuesta de RENAPER, el formulario se carga manual y queda **"No validado
RENAPER"** → el backoffice debe ofrecer **validar a posteriori**.

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

**Estado SIS:** Parcialmente definido (con pendientes técnicos). Las preguntas concretas
(S-1…S-12) están consolidadas al final, en la **Sección 16**.

---

### 8.2 App de campo — integración relevada (cerrada)

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

**Regla crítica:** el **escaneo DNI NO consulta RENAPER** porque lee los datos directamente
del chip/código del documento físico que tiene el territorial en la mano. Esto le da el mismo
nivel de confianza (o mayor) que la validación remota con RENAPER.

**Regla:** "No validado RENAPER" tiene **dos orígenes posibles**: sin conexión (offline) o
RENAPER caído con conexión. En ambos casos el tratamiento posterior es idéntico: el backoffice
debe permitir revalidar (RN-16).

**Regla (RN-15):** "Finalizado" del relevamiento es un estado **diferido a la sincronización**:
si se finaliza offline, el relevamiento muestra **"Sincronizando..."** en la app (estado local)
y solo aparece en el backoffice con estado `Finalizado` cuando **todo** se sincronizó. El admin
no ve el relevamiento antes de la sincronización completa.

**Impacto crítico:** hay **dos momentos de validación RENAPER** — (1) en campo si hay señal;
(2) en backoffice (revalidación) para los marcados "No validado RENAPER". El backoffice debe
exponer esa acción de revalidar.

---

## 9. Reglas de negocio (consolidadas, preliminares)

| ID | Regla |
|---|---|
| RN-01 | El cupo es **por Segmento** (parametría). Si el segmento **no tiene subsegmentos**, su `cupo_maximo` es el cupo total. Si **tiene subsegmentos**, el cupo se distribuye por subsegmento (ver RN-40). El territorial releva sin límite. |
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
| RN-26 | **Finalizar un relevamiento es reversible:** el territorial puede **reabrir el operativo** finalizado **para sumar más personas**. Los **formularios ya enviados no se modifican** (conservan estado/revisión/SIS); al re-finalizar se **envían solo los nuevos**. |
| RN-27 | Un usuario **puede tener múltiples roles a la vez** (ej. **Administrador** de un programa y **Territorial** de otro). El acceso por módulo/programa depende de los roles asignados. |
| RN-28 | El relevamiento que **no se inicia el día asignado vence** y el **Coordinador lo reprograma** (nueva fecha). |
| RN-29 | El admin **puede editar los datos del formulario** desde el backoffice **antes de aprobar/rechazar**. |
| RN-30 | Un **Segmento** es una sub-modalidad de la beca. La **convocatoria** apunta a un segmento (se selecciona al crearla). |
| RN-31 | **Requisitos generales:** preguntas **configurables** desde Configuración del programa, **compartidas por todas las convocatorias**; son el **Cuestionario social de 13 preguntas** (§6.3) y **se responden en el formulario**. |
| RN-32 | **Requisitos de segmento/subsegmento:** son **nativos** del sistema, **configurables** al configurar el segmento (ya **no vienen de SIS**); se muestran **informativos** al territorial al completar el formulario. |
| RN-33 | La **evaluación** se reparte: **Nodo** valida los **requisitos nativos** (admin/coordinador en la revisión) y **SIS** hace el **control de incompatibilidades** (devuelve **OKA / negativa**). |
| RN-34 | El **cupo se descuenta del segmento** correspondiente, tras doble-OKA (Nodo + SIS). |
| RN-35 | Existe el nivel **Subsegmento** (opcional, configurable) dentro de un segmento (ej. Ladrillo/Carbón en Producción Territorial). |
| RN-36 | El **Coordinador** (= validador territorial) es un **rol nuevo**: **valida postulaciones** del territorio y **reprograma** relevamientos vencidos. |
| RN-37 | Los datos que provee **RENAPER o escaneo de DNI** (personales, CUIL, domicilio) **no se preguntan** en el formulario; **solo se cargan a mano sin conexión**. |
| RN-38 | El **control de incompatibilidades lo realiza SIS** (es el **OKA / negativa** de la integración): fuera de Chaco, planta/contrato estatal, otros programas, relación de dependencia, ingresos > 3 SMVM, etc. **Negativa de SIS = incompatibilidad** (con motivo); sin OKA no ocupa cupo. |
| RN-39 | **Documentación obligatoria** general: DNI, certificado de domicilio, CUIL, constancia de estudios y convenio de confidencialidad/uso de imagen; más la **documentación específica por segmento**. |
| RN-40 | Al crear o editar el `cupo_maximo` de un subsegmento, el sistema valida que `sum(hermanos.cupo_maximo) + nuevo_cupo <= segmento.cupo_maximo`. Si la validación falla, la operación es rechazada con mensaje de error indicando el máximo disponible. |

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

---
## Diagrama de Flujo
<iframe width="768" height="640" src="https://miro.com/app/live-embed/uXjVJzk5lbQ=/?focusWidget=3458764674758430959&embedMode=view_only_without_ui&embedId=49042054955" frameborder="0" scrolling="no" allow="fullscreen; clipboard-read; clipboard-write" allowfullscreen></iframe>

## 11. Fuera de alcance (por ahora)

- **Notificaciones** a territoriales o ciudadanos.
- **Reproceso** de personas rechazadas por el admin (rechazo es informativo).
- Diseñador de formularios dinámicos para el **formulario de la persona** (sus **campos son
  fijos**, definidos por nosotros). *(Distinto de los **requisitos generales/segmento**, que
  sí son configurables — ver §6.2 / RN-31/32.)*

### 11.1 Diferido a Versión 2 (acordado)
- **Condición de permanencia / seguimiento** de cada segmento (recertificación, mantener
  actividad/regularidad/controles, instancias de seguimiento).
- **Estados administrativos extendidos:** suspensión, documentación faltante, validación
  pendiente, baja con motivo.
- **Seguimiento administrativo** (observaciones y cambios de estado a lo largo del tiempo).

---

## 12. Preguntas abiertas

Todas las preguntas pendientes están consolidadas al final del documento, en la
**Sección 16** (equipo Ministerio, técnicas y de equipo, con su estado).

---

## 13. Asunciones a confirmar

Asunciones y dudas pendientes consolidadas al final en la **Sección 16.6**.

---

## 14. Próximos pasos

1. **Sistema SIS** — cerrar S-1, S-2, S-4, S-5 y S-12 (contrato técnico del control de incompatibilidades).
2. **Segmentos / requisitos** — confirmar "Solidaria" (R-1.c) y si los requisitos/documentación son campos del formulario o informativos (R-13). *(R-8.b cerrada: ver RN-40)*
3. **Flujo funcional** — cerrado (reapertura 1.b resuelta). No quedan pendientes funcionales nuestros; el resto depende del **contrato de SIS** (paso 1).
4. **Investigación de código** — completar C-1 (revisar módulos existentes).
5. **Control estricto** — cerrar todas las preguntas bloqueantes y verificar consistencia.
6. **Generación en GitHub** — épica → análisis → sub-issues (recién con todo cerrado).

---

## 16. Preguntas pendientes (consolidado)

> **Todas las preguntas abiertas del análisis, juntas y al final.** Mientras existan
> pendientes **bloqueantes**, NO se generan issues (control estricto de `AGENTS.md`).
> Estado de cada una: Bloqueante · No bloq. · Diferida · Cerrada · Pendiente.

### 16.1 Sistema SIS (pendientes y diferida)

| # | Pregunta | Para | Estado |
|---|---|---|:--:|
| S-1 | **Contrato de API.** ¿SIS expone una API REST? ¿Endpoint, autenticación, ambiente de prueba? ¿Es síncrono o asíncrono? | Equipo Ministerio/ICORE | Bloqueante |
| S-2 | **Datos de entrada.** ¿Qué campos se le envían por persona? (DNI/CUIL, datos del beneficio, id de programa, adjuntos) | Equipo Ministerio/ICORE | Bloqueante |
| S-4 | **Datos de salida.** ¿Qué devuelve exactamente? (OK/NO, código, motivo de rechazo, datos) | Equipo Ministerio/ICORE | Bloqueante |
| S-5 | **Rechazo de SIS.** Si responde NO, ¿la persona queda fuera o el admin corrige y reenvía? | Equipo Ministerio | Bloqueante |
| S-8 | **Cadena de 3 niveles.** ¿Becas llega hasta "ocupa cupo" o también hasta Ayudas Sociales / Liquidado (nivel 3)? | Equipo Ministerio | Diferida |
| S-11 | ~~Requisitos por segmento desde SIS~~ — **ANULADA:** los requisitos son **nativos**, no vienen de SIS (cambio de definición). | — | Cerrada |
| S-12 | **Contrato SIS (incompatibilidades).** Ya está claro que SIS = **control de incompatibilidades** (OKA/negativa). Falta el **detalle técnico**: qué campos se le envían y qué devuelve exactamente (se solapa con S-2/S-4). | Equipo Ministerio/ICORE | Bloqueante |

### 16.2 Formulario y reglas de negocio

| # | Pregunta | Para | Estado |
|---|---|---|:--:|
| 2 | **Campos exactos del formulario.** RQ-001 define una base: Bloque A (DNI, Apellido, Nombre, Sexo, Estado Civil, Fecha de Nacimiento), Bloque B (Domicilio: Provincia, Localidad, Calle, Número, Piso, Departamento, Barrio), Bloque C (Celular, Mail — manual obligatorio), Bloque D (Apoderado — condicional menor de edad), Adjuntos ampliados (ver §7.1: DNI, cert. domicilio, CUIL, constancia de estudios y convenio **obligatorios**; CBU opcional; + docs por segmento). **Pendiente confirmar con Guido** si hay campos adicionales para Becas. | Guido (Equipo Ministerio) | No bloq. |

**Preguntas cerradas en esta sección:**
- **Pregunta 3 (Cupo):** Reabierta y reemplazada por R-5. El cupo **ya no es único por programa**: ahora es **por segmento** (parametría: cantidad de segmentos + cupo por segmento). Ver §6.2 y RN-01/34.
- **Pregunta 10 (Legajo rechazado):** Cerrada. El legajo usa solapas dinámicas: si el ciudadano tiene registro en la tabla programas, aparece la solapa correspondiente; si está rechazado en Becas, la solapa se habilita y muestra el estado "Rechazado".
- **Pregunta 1 (Reversibilidad del relevamiento):** Cerrada. Finalizar **es reversible**: el territorial **reabre el operativo para sumar más personas**; los formularios ya enviados no se tocan (1.b también cerrada). Ver RN-26.
- **Pregunta 7 (Doble rol):** Cerrada. Un usuario **sí puede tener los dos roles** simultáneamente (Admin de un programa y Territorial de otro). Ver RN-27.
- **Pregunta 8 (Relevamiento del día no iniciado):** Cerrada. Si no se inicia el día asignado, **vence** y el **Coordinador lo reprograma** (RN-28). El coordinador = validador territorial, tercer rol (8.b cerrada).
- **Pregunta 9 (Admin edita formulario):** Cerrada. El admin **sí puede editar los datos del formulario desde el backoffice** antes de aprobar (ver RN-29).

### 16.2-bis Sub-preguntas derivadas

| # | Pregunta | Para | Estado |
|---|---|---|:--:|
| 1.b | Cerrada: reabrir el relevamiento es **para sumar más personas**. Los formularios **ya enviados no se tocan** (conservan estado/revisión/SIS); al re-finalizar se envían **solo los nuevos** (RN-26). | — | Cerrada |
| 8.b | Cerrada: el **"coordinador" = validador territorial**, rol **nuevo (tercero)**; valida postulaciones y reprograma relevamientos vencidos (RN-36, §3). | — | Cerrada |
| 9.b | Cuando el admin **edita** el formulario antes de aprobar: ¿queda **traza** (quién/cuándo/valor anterior)? ¿Hay campos no editables (ej. DNI validado por RENAPER/escaneo)? | Equipo Ministerio | No bloq. |

### 16.3 RQ-002 / cadena de aprobación

| # | Pregunta | Para | Estado |
|---|---|---|:--:|
| 13 | **Sistema de Ayudas Sociales (nivel 3):** ¿dentro del alcance de Becas o es otro requerimiento? | Equipo Ministerio | Bloqueante |
| 14 | **Contrato técnico de SIS:** endpoint/API, campos, qué valida, qué devuelve, manejo de rechazo y caída. (= S-1, S-2, S-4, S-5, S-12) | Equipo Ministerio/ICORE | Bloqueante |

**Preguntas cerradas en esta sección:**
- **Pregunta 12 (Cadena de control):** Cerrada. El cupo se decide en **Becas (nivel 1)**, no en sistemas posteriores.
- **Pregunta 15 (Disparo a SIS):** Cerrada. El sistema implementa **ambas opciones**: (1) disparo automático y síncrono al aprobar/rechazar (el admin espera respuesta antes de continuar), y (2) botón manual "Validar contra SIS" disponible en Nodo para reintentos o validaciones posteriores.

### 16.4 Investigación de código pendiente (responsabilidad de ICORE)

| # | Tarea | Estado |
|---|---|:--:|
| C-1 | Revisar duplicidad real en `apps/programas`, `apps/legajos`, `apps/ciudadanos`, `users` (qué existe hoy). | Pendiente |

### 16.5 Resumen del control estricto

- **No se generan issues** mientras haya bloqueantes sin cerrar: **SIS** (S-1, S-2, S-4, S-5, S-12, 13, 14). Único bloque pendiente: el **contrato técnico de SIS**, depende del equipo Ministerio/ICORE.
- Las **No bloq.** se pueden asumir y documentar como *Asunción a confirmar* sin frenar.
- Falta cerrar la **investigación de código** (C-1) antes de generar.

### 16.7 Requisitos de elegibilidad (general / segmento)

**Cerradas en esta ronda** (detalle en §6.2):
- **R-1 (qué es segmento):** sub-modalidad de la beca; se selecciona al crear la
  convocatoria. Catálogo oficial: **7 segmentos + subsegmentos** (ver §6.2).
- **R-2 (requisitos generales):** preguntas compartidas por todas las convocatorias.
- **R-3 (requisitos de segmento):** CAMBIADA — ya **no vienen de SIS**; son **nativos**
  y **configurables** al configurar el segmento/subsegmento (RN-32).
- **R-4 (quién/cuándo evalúa):** Cerrada — **Nodo valida los requisitos nativos**
  (admin/coordinador en la revisión) y **SIS hace el control de incompatibilidades**
  (OKA/negativa).
- **R-10 (control de incompatibilidades):** Cerrada — **lo hace SIS**: su **OKA/negativa** es
  el resultado (negativa = incompatibilidad, con motivo). Es la misma validación SIS (RN-18/38).
- **R-5 (cupo):** **cupo por segmento** (reabre y reemplaza la pregunta 3). Parametría:
  cantidad de segmentos + cupo por segmento.
- **R-7 (configurabilidad generales):** configurables desde Configuración del programa.
- **R-1.b (origen del catálogo):** Cerrada — el catálogo de **segmentos/subsegmentos es local
  y configurable** (ABM en Configuración del programa).
- **R-9 (requisitos generales en el formulario):** Cerrada — **sí**, son las **13 preguntas**
  del Cuestionario social, respondidas en el formulario.
- **R-12 (cuestionario social):** Cerrada — **= requisitos generales**, para **todos** los
  segmentos, dentro del formulario (§6.3).

| # | Pregunta abierta | Para | Estado |
|---|---|---|:--:|
| R-1.c | El segmento **"Solidaria"** no figura en el doc del Ministerio. ¿Sigue existiendo? | Equipo Ministerio | No bloq. |
| R-6 | **Asignación persona↔segmento:** ¿queda determinado por la convocatoria (implícito) o se asigna por persona? ¿Puede una persona estar en más de un segmento? | Equipo Ministerio | No bloq. |
| R-8 | **Cardinalidad convocatoria↔segmento:** ¿una convocatoria apunta a **un solo** segmento o puede tener **varios**? | Equipo Ministerio | No bloq. |
| ~~R-8.b~~ | ~~¿Cupo por segmento o por subsegmento?~~ **Cerrada:** los subsegmentos tienen su propio `cupo_maximo`; la suma no puede superar el del segmento. Sin subsegmentos, el cupo del segmento es el total (ver RN-40). | — | **Cerrada** |
| R-11 | **Documentación/adjuntos:** confirmar obligatoriedades por segmento y cuáles son **imágenes cargadas en el formulario**. | Equipo Ministerio | No bloq. |
| R-13 | **Requisitos y documentación como campos vs informativo:** los requisitos configurables y la documentación (certificado de domicilio, CUIL, constancia de estudios, convenio de confidencialidad) ¿aparecen como **campos del formulario** o son solo **a modo informativo**? | Equipo Ministerio | Por definir |

### 16.6 Asunciones pendientes de confirmación

| # | Asunción / duda | Estado |
|---|---|:--:|
| A-1 | Jerarquía explícita Programa → Convocatoria/**Segmento** → **Subsegmento** → Relevamiento → Formulario; "Programa" se modela genérico aunque hoy solo se use Becas. | No bloq. |
| A-2 | "Aprobar" en backoffice y "ocupar cupo" son pasos distintos (el cupo se decide después de SIS). | No bloq. |
| A-3 | RENAPER en campo usa la misma API (o equivalente) que backoffice para validar identidad. | No bloq. |
| A-4 | Una persona rechazada por admin conserva legajo creado (sin reproceso en el sistema). | No bloq. |
