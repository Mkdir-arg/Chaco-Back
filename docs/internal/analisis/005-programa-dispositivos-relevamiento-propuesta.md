# Propuesta funcional — Programa Dispositivos (NODO): legajo institucional, admisiones, camas y merenderos

**Tipo:** Propuesta de épica (documento de trabajo interno)
**Estado:** Aprobada por el cliente — técnicos C-1…C-7 resueltos code-first; lista para generar épica/issues (solo C-8 abierto, con cliente, no bloqueante)
**Fecha:** 2026-06-25 · **Última actualización:** 2026-07-02
**Responsable (ICORE):** functional-analyst
**Programas:** **Dispositivos** y **Merenderos** — dos `Programa` propios sobre el módulo genérico de Programas (después de Becas)
**Módulos Django candidatos:** `apps/programas`, `apps/legajos`, `apps/ciudadanos` (core), `users`/`core.rbac` (roles/permisos), `dashboard`

> **Conformidad del cliente (mail de Guido, 2026-07-01).** El cliente **aprobó avanzar con el
> desarrollo** y aportó observaciones + los formularios relevados hasta el momento. Se
> resolvieron los bloqueantes: **Q-2** (Merenderos = **programa propio**, no un tipo de
> Dispositivos), **Q-5** (UPI, ECA y Residencias Universitarias **tienen camas**) y se
> reencuadró **Q-1** (los formularios están "en etapa de relevamiento": crecen pero no se
> elimina lo ya definido → confirma el enfoque **configurable por tipo**). Se recibieron además
> formularios nuevos (F-00 Línea 102, ficha de albergue "Calcuta", Relevamiento de PC) y una
> versión ampliada del F-00 Abordaje Psicosocial. Detalle del impacto en §19.

> **Origen.** Esta propuesta nace de: (1) el **Miro** del Programa Dispositivos (legajo del
> dispositivo con tipos + cálculos de camas, y legajo de merenderos), (2) la **Especificación
> funcional de procesos para NODO** (13 procesos macro, reglas transversales e indicadores) y
> (3) los **formularios reales del cliente** (F-00 Adultos Mayores, F-00 Abordaje Psicosocial,
> F-01 Registro Diario, F-02 Prestación, + referencias). El Miro es el **alcance concreto** que
> arrancamos; NODO es la **visión macro**. Este documento reconcilia todo y lo **ancla al
> código real**. Todas las **dudas y preguntas** están al final, en la **Sección 17**.

---

## 1. Objetivo

Construir, en el **backoffice**, el **Programa Dispositivos** de NODO: un módulo que permita dar
de alta y mantener un **legajo institucional único por dispositivo** (establecimiento físico:
hogar de adultos mayores, dispositivo de abordaje psicosocial, residencia universitaria, etc.),
gestionar la **admisión, ocupación de camas y egreso** de las personas que ingresan a cada
dispositivo, y registrar la **información específica de cada persona según el tipo de
dispositivo** mediante formularios configurables. En un **programa hermano y propio** (Programa
Merenderos, confirmado por el cliente como programa aparte del Ministerio) se gestiona el
**legajo de merenderos/comedores**: alta institucional con documentación respaldatoria, entrega
de mercaderías y registro de la prestación alimentaria.

Cada persona admitida se **vincula al Legajo Ciudadano** existente (dato único, sin duplicar
identidad), y el dispositivo mantiene en tiempo real su **disponibilidad de camas** y sus
**métricas de ingreso/egreso/ocupación** a partir de los movimientos registrados, no de una
carga manual paralela.

---

## 2. Encuadre: NODO (macro) vs Programa Dispositivos (alcance de esta épica)

**NODO** es la plataforma integral de gestión territorial del organismo. La especificación del
cliente describe **13 procesos** (P01–P13) que cubren toda la operación (dispositivos, personas,
admisiones, asistencia, merenderos, albergues, denuncias/Línea 102, fondos, personal,
infraestructura tecnológica, migración y cierre mensual).

El **Programa Dispositivos** (lo que muestra el Miro) es la **primera tajada concreta** de NODO,
y junto a él entra el **Programa Merenderos** (que el cliente confirmó como **programa propio**
del Ministerio, no un tipo de Dispositivos — ver Q-2). Ambos se apoyan en el **módulo genérico
de Programas** ya construido para Becas. El mapeo completo NODO → alcance está en la **§16**; el
resumen:

| Proceso NODO | ¿En esta épica? | Comentario |
|---|---|---|
| **P01** Alta y mantenimiento del dispositivo | ✅ Núcleo | Es el "Legajo Dispo" del Miro (Información Base + tipo). |
| **P03** Alta/actualización de persona y legajo | ✅ Reuso | Reusa `Ciudadano` existente; no se reinventa. |
| **P04** Inscripción, admisión, egreso y traslado | ✅ Núcleo | "Ingreso/Egreso persona" del Miro. |
| **P07** Albergues, residencias y camas | ✅ Núcleo | "Camas totales / libres / ocupadas / métricas". |
| **P06** Merenderos y comedores | ✅ Núcleo (**programa propio**) | "Legajo Merenderos" + F-02. Es un `Programa` separado: entrega de mercaderías a merenderos abiertos por vecinos/as previa documentación respaldatoria (Q-2 cerrada). |
| **P05** Asistencia y prestación diaria | 🟡 Parcial | El Miro solo muestra prestación en merenderos; asistencia diaria general → confirmar alcance. |
| **P02** Usuarios, perfiles y permisos | 🟡 Reuso | Reusa `core.rbac`; agrega roles del programa. |
| **P11** Infraestructura y preparación tecnológica | 🟡 Diferible | Semáforo edilicio/tecnológico de PCs → fase posterior. |
| **P08** Denuncias, riesgo y derivaciones (Línea 102) | ⛔ Fuera (V2+) | Casos sensibles NNA; otra épica. |
| **P09** Fondos, raciones, kits y rendiciones | 🟡 Parcial | Solo "kits de mercadería" del merendero entra; rendiciones financieras → diferido. |
| **P10** Personal y asignaciones | ⛔ Fuera (V2+) | Dotación por dispositivo; no está en el Miro. |
| **P12** Migración, corrección y duplicados | 🟡 Transversal | Aplica al alta inicial de dispositivos; tratar como tarea de migración. |
| **P13** Cierre mensual y tablero | 🟡 Diferible | Indicadores básicos sí; cierre mensual formal → fase posterior. |

> **Decisión de alcance (aprobada por el cliente, 2026-07-01):** esta épica = **P01 + P03(reuso)
> + P04 + P06 + P07**, más lo transversal mínimo (roles, indicadores básicos, solapa en el
> legajo). **P06 (Merenderos) se modela como `Programa` propio** hermano de Dispositivos, no como
> un tipo. El resto se documenta para encuadre pero queda **fuera** o **diferido** (§13).

---

## 3. Concepto / modelo del dominio

La entidad central nueva es el **Dispositivo** (establecimiento/institución). De él cuelgan su
**tipo**, su **configuración operativa** (camas) y las **admisiones** de personas. El
**Merendero** es una segunda clase de legajo institucional, hermana, que vive en su **propio
programa** (`Programa` separado, confirmado por el cliente) con un circuito distinto.

```
NODO (plataforma)
 ├─ Programa Dispositivos                         (Programa codigo="DISPOSITIVOS")
 │    └─ Dispositivo                              (institución: 1..N; "Legajo Dispo")
 │         ├─ Información base                     (nombre, domicilio, contacto, responsable)
 │         ├─ Tipo de dispositivo                  (define el formulario de admisión F-00)
 │         ├─ Configuración operativa              (camas totales; reglas de ingreso/egreso)
 │         ├─ Admisión / Estadía / Egreso          (N por dispositivo; 1 = 1 persona/legajo)
 │         │      └─ vínculo a Legajo Ciudadano + F-00 según tipo
 │         ├─ Registro diario F-01                 (novedades por turno; cantidades calculadas)
 │         └─ Cálculos automáticos                 (camas libres/ocupadas, métricas)
 │
 └─ Programa Merenderos                            (Programa codigo="MERENDEROS" — programa propio)
      └─ Merendero                                 (institución: 1..N; "Legajo Merenderos")
           ├─ Información base                      (nombre, dom., zona, barrio, responsable)
           ├─ Documentación respaldatoria           (la presenta el/la vecino/a que abre el merendero)
           ├─ Entrega de mercaderías               (kits de mercadería, fecha de entrega, servicio)
           └─ Prestación mensual F-02              (raciones por día y servicio + observaciones)
```

| Entidad | Descripción | Notas clave / anclaje en código |
|---|---|---|
| **Programa Dispositivos** | Marco genérico. Es **otro `Programa`** además de Becas/Ñachec. | `Programa` ya existe (`programas/models/__init__.py:9`). Se crea con `codigo="DISPOSITIVOS"` (el `codigo` es el identificador único; el enum `TipoPrograma` de `:12` no lo incluye aún — sumar la choice). |
| **Programa Merenderos** *(NUEVO — programa propio)* | Programa hermano y separado de Dispositivos (confirmado por el cliente). Entrega de mercaderías a merenderos abiertos por vecinos/as previa documentación respaldatoria. | Segunda instancia de `Programa` con `codigo="MERENDEROS"`. Comparte el patrón de legajo institucional pero **no maneja camas**. |
| **Dispositivo** *(NUEVO)* | Establecimiento físico con identidad institucional, domicilio, responsable, capacidad y tipo. | **No existe modelo hoy.** Hay que crearlo. ⚠️ Colisión de nombre: en código `dispositivo` ya es un *alias* de `LegajoAtencion` (`legajos/models/base.py`); usar un nombre distinto (ej. `DispositivoInstitucional`). |
| **Tipo de dispositivo** | Clasifica el dispositivo y **determina el formulario de admisión** (F-00). Tipos del Miro: Adulto Mayor, Abordaje Psicosocial, UPI/ECA, UPI, Residencias Universitarias, Fortalecimiento Familiar. | Conceptualmente equivale al **Segmento** de Becas (cada tipo → su set de campos). Ver §4 y §9. |
| **Persona / Legajo Ciudadano** | La persona que ingresa al dispositivo. Dato único. | **Reusa** `Ciudadano` (`legajos/models/base.py:13`). Se busca por DNI; si existe se relaciona, si no se crea. |
| **Admisión / Estadía** *(NUEVO)* | Relación temporal persona↔dispositivo: ingreso, ocupación de cama, egreso/traslado. | **No existe.** Conceptualmente cercano a `InscripcionPrograma` (`programas/models/__init__.py:93`) pero con cama/fecha de ingreso-egreso. Evaluar reuso vs modelo nuevo (§8). |
| **Cama / Plaza** *(NUEVO)* | Unidad de capacidad del dispositivo. Estado: Disponible/Reservada/Ocupada/Fuera de servicio. | **No existe.** El Miro pide camas totales + libres + ocupadas (cálculo). Ver §10. |
| **Formulario de admisión (F-00)** | Información específica de la persona según el **tipo** de dispositivo. | Configurable por tipo. Reusa el patrón `PreguntaGlobal`/`RequisitoNativo` (§9). |
| **Configuración del dispositivo (F-01)** | Parametría operativa: camas totales, reglas de ingreso/egreso. | "Solapa de configuración" del Miro. |
| **Merendero** *(NUEVO)* | Organización comunitaria (abierta por vecinos/as) que recibe mercaderías y brinda asistencia alimentaria. Legajo institucional propio del **Programa Merenderos**. | **No existe.** Vive en su propio programa; circuito distinto (no maneja camas). Documentación respaldatoria + entrega de kits + prestación F-02. |
| **Prestación de merendero (F-02)** | Servicios alimentarios brindados (desayuno/almuerzo/merienda/cena) + observaciones. | Configurable. |

### 3.1 Hallazgo crítico (anclaje code-first)

El módulo **Programa** modela hoy la **inscripción de un ciudadano a un programa**
(`InscripcionPrograma`), no un **establecimiento**. El "Dispositivo" del Miro/NODO es una
**entidad institucional nueva** (como un legajo de la institución), que **no tiene equivalente**
en el código. Es el principal trabajo de modelado de esta épica. Lo demás (identidad de la
persona, solapas, RBAC, formularios configurables) **se reusa**.

> **Colisión de terminología a resolver (RN-DI-19):** el término `dispositivo` ya existe en el
> código como propiedad/alias de `LegajoAtencion` (el legajo de atención de un ciudadano dentro
> de un programa). El **Dispositivo institucional** de esta épica es algo distinto. Hay que elegir
> un nombre de modelo que no choque (propuesta: `DispositivoInstitucional` / app o submódulo
> propio) y aclararlo en el código para evitar ambigüedad.

---

## 4. Tipos de dispositivo

Cada **tipo** define qué información específica se carga al admitir a una persona (el formulario
F-00). Los tipos del Miro:

| Tipo | Form. de admisión | ¿Maneja camas? | ¿Detalle en el Miro? |
|---|---|---|:--:|
| **Adulto Mayor** | F-00 – Ingreso Adultos Mayores | Sí | ✅ Detallado |
| **Abordaje Psicosocial** | F-00 – Abordaje Psicosocial | Sí | ✅ Detallado (ampliado 2026-07: Comidas + Cierre) |
| **ECA** | Información específica | **Sí** (dispositivo de resguardo NNA) | 🟡 A configurar |
| **UPI** | Información específica | **Sí** (Centro de Protección Integral) | 🟡 A configurar |
| **Residencias Universitarias** | Información específica | **Sí** (camas/plazas) | 🟡 A configurar |
| **Fortalecimiento Familiar** | Información específica | A confirmar | 🟡 A configurar |

> **Actualización 2026-07 (cliente):** UPI, ECA y Residencias Universitarias **manejan camas**
> (Q-5 cerrada). Solo queda por confirmar Fortalecimiento Familiar. El detalle de sus F-00 sigue
> "en etapa de relevamiento": se cargan como **configuración** a medida que el Ministerio los
> releve, sin tocar código (Q-1 reencuadrada). Los tipos "UPI" y "ECA" figuraban juntos en el
> Miro; el cliente los trata como dispositivos distintos.

**F-00 – Adultos Mayores** (bloques del Miro): Datos personales · Situación laboral y económica ·
Permanencia, nutrición y vivienda · Red de sostén · Datos generales de la familia · Salud ·
Ingresos mensuales · Egresos del dispositivo · Intereses y actividades · Grado de dependencia.

**F-00 – Abordaje Psicosocial** (bloques del Miro): Datos personales · Reingreso · Situación
personal, educativa y laboral · Oficio laboral · Grupo familiar · Dinámica familiar · Vivienda ·
Ingresos y egresos económicos · Red de sostén · Salud · Consumos · Situaciones de crisis ·
Necesidades básicas · Grado de dependencia.

> **Decisión de modelado (validada por el cliente):** los **bloques** se modelan como
> **secciones** y los campos de cada bloque como **preguntas configurables por tipo** (patrón
> `RequisitoNativo`), de modo que "Adulto Mayor" y "Abordaje Psicosocial" tengan cada uno su
> propio set sin tocar código. El cliente confirmó que los formularios **crecen por
> configuración** ("no se prevé eliminar información ya definida, sino únicamente ampliar"), lo
> que valida este enfoque. Los tipos aún sin detalle (ECA, UPI, Residencias Univ.,
> Fortalecimiento Familiar) se **dan de alta como configuración** cuando el Ministerio los
> releve — no bloquean el desarrollo del mecanismo.

---

### 4.1 F-00 Adultos Mayores — campo a campo

*Área: Sistema Integral Gerontológico.*

**Convención:** `FORMULARIO` = campo que carga el operador. `FUNCIONALIDAD` = lo provee el sistema (cálculo, Legajo Ciudadano, usuario logueado). `CONFIRMAR` = requiere verificación antes de implementar.

**Resumen:** 31 al formulario · 17 funcionalidades · 2 a confirmar (C-6, C-7)

| Sección | Campo | Tipo | Clasificación | Nota |
|---|---|---|---|---|
| Encabezado | Institución / sede | — | `FUNCIONALIDAD` | Contexto del dispositivo activo |
| Encabezado | Fecha y hora | — | `FUNCIONALIDAD` | Timestamp de la admisión |
| Encabezado | Reingreso (Sí/No) | — | `FUNCIONALIDAD` | Sistema detecta estadía anterior cerrada del ciudadano |
| Encabezado | Responsable | — | `FUNCIONALIDAD` | Usuario logueado |
| A. Datos personales | Nombre y apellido | — | `FUNCIONALIDAD` | Legajo Ciudadano / RENAPER (RN-DI-12) |
| A. Datos personales | DNI / CUIL | — | `FUNCIONALIDAD` | Clave de búsqueda del Legajo Ciudadano |
| A. Datos personales | Edad | — | `FUNCIONALIDAD` | Calculada de fecha de nacimiento del legajo |
| A. Datos personales | Fecha de nacimiento | — | `FUNCIONALIDAD` | Legajo Ciudadano / RENAPER (RN-DI-12) |
| A. Datos personales | Género | — | `FUNCIONALIDAD` | Legajo Ciudadano / RENAPER (RN-DI-12) |
| A. Datos personales | Obra social / N° | texto | `CONFIRMAR` | Ver C-6: verificar si ya en solapa Salud del Legajo Ciudadano |
| A. Datos personales | Nivel instrucción | selector | `FORMULARIO` | Pre-completar desde legajo educativo si existe |
| A. Datos personales | Oficio | texto | `FORMULARIO` | Pre-completar desde legajo laboral si existe |
| A. Datos personales | Capacitaciones (Sí/No + cuáles) | bool + texto | `FORMULARIO` | |
| A. Datos personales | Interés en formación (Sí/No + cuál) | bool + texto | `FORMULARIO` | |
| B. Sit. laboral y econ. | Empleo | selector | `FORMULARIO` | Formal / Informal / Sin empleo |
| B. Sit. laboral y econ. | Lugar de trabajo | texto | `FORMULARIO` | |
| B. Sit. laboral y econ. | Ocupación | texto | `FORMULARIO` | Pre-completar desde legajo laboral si existe |
| B. Sit. laboral y econ. | Ingreso mensual | número | `FORMULARIO` | |
| B. Sit. laboral y econ. | Plan social / beca (Sí/No + cuál) | bool + texto | `FORMULARIO` | |
| B. Sit. laboral y econ. | Jubilación / pensión (Sí/No + cuál) | bool + texto | `FORMULARIO` | |
| C. Permanencia, nutrición y vivienda | Perfil permanencia | selector | `FORMULARIO` | Larga estadía / Mediana estadía / Tránsito-crítico |
| C. Permanencia, nutrición y vivienda | Requerimiento nutricional | selector | `FORMULARIO` | General / Adulto mayor / Especial |
| C. Permanencia, nutrición y vivienda | Relación familiar (Sí/No) | bool | `FORMULARIO` | |
| C. Permanencia, nutrición y vivienda | Último domicilio | texto | `FORMULARIO` | Domicilio previo al ingreso; ≠ domicilio del Legajo Ciudadano |
| C. Permanencia, nutrición y vivienda | Motivo egreso hogar | texto | `FORMULARIO` | Por qué dejó su vivienda anterior. ≠ egreso del dispositivo (Sección H) |
| C. Permanencia, nutrición y vivienda | Posee vivienda (Sí/No) | bool | `FORMULARIO` | |
| C. Permanencia, nutrición y vivienda | Dónde duerme actualmente | texto | `FORMULARIO` | Situación habitacional justo antes del ingreso |
| C. Permanencia, nutrición y vivienda | Observaciones | texto libre | `FORMULARIO` | |
| D. Red de sostén | Tipos de red | multi-selector | `FORMULARIO` | Parientes / Institucional / Vecinos / ONG / Iglesia / CC / Gubernamental / Otros |
| D. Red de sostén | Detalle red de sostén | texto libre | `FORMULARIO` | |
| E. Datos familia | Tabla familiar | tabla N filas | `FORMULARIO` | Nombre / Parentesco / Edad / Nivel / Ingreso / Teléfono |
| F. Salud | Grupo sanguíneo | texto | `CONFIRMAR` | Ver C-7: verificar si ya en solapa Salud del Legajo Ciudadano |
| F. Salud | Tratamiento médico (Sí/No + dónde) | bool + texto | `FORMULARIO` | |
| F. Salud | Antecedentes / condiciones de salud | multi-selector | `FORMULARIO` | Tuberculosis / Diabetes / Cardíacos / Respiratorios / Salud mental / Discapacidad / ETS / Otros |
| F. Salud | Observaciones de salud | texto libre | `FORMULARIO` | |
| G. Egresos mensuales | Alquiler | número | `FORMULARIO` | |
| G. Egresos mensuales | Créditos | número | `FORMULARIO` | |
| G. Egresos mensuales | Cuotas | número | `FORMULARIO` | |
| G. Egresos mensuales | Medicamentos | número | `FORMULARIO` | |
| G. Egresos mensuales | Transporte / otros | número | `FORMULARIO` | |
| G. Egresos mensuales | Total egresos | — | `FUNCIONALIDAD` | Calculado: suma de los conceptos anteriores |
| H. Egreso del dispositivo | Sección completa (Fecha / Motivo / Destino / Derivación) | — | `FUNCIONALIDAD` | Es el flujo de egreso, no el formulario de admisión. En papel están juntos; en el sistema es una acción separada al momento del retiro. |
| I. Intereses y actividades | Intereses | texto libre | `FORMULARIO` | |
| J. Dependencia y cierre | Grado de dependencia | selector | `FORMULARIO` | Autoválido / Semi-válido / Postrado |
| J. Dependencia y cierre | Fecha de revisión | — | `FUNCIONALIDAD` | Timestamp del sistema |
| J. Dependencia y cierre | Firma y aclaración | — | `FUNCIONALIDAD` | Usuario logueado |
| J. Dependencia y cierre | DNI / cargo | — | `FUNCIONALIDAD` | Del usuario logueado |

---

### 4.2 F-00 Abordaje Psicosocial — campo a campo

*Área: Dirección de Inclusión y Abordaje Integral (Psicosocial).*

**Resumen:** 45 al formulario · 20 funcionalidades · **versión ampliada 2026-07** (se agregó §11 Comidas y el bloque Cierre/egreso, a pedido del cliente).

| Sección | Campo | Tipo | Clasificación | Nota |
|---|---|---|---|---|
| Encabezado | Institución / sede | — | `FUNCIONALIDAD` | Contexto del dispositivo activo |
| Encabezado | Fecha | — | `FUNCIONALIDAD` | Timestamp de la admisión |
| Encabezado | Tipo de ingreso (1ª vez / Reingreso) | — | `FUNCIONALIDAD` | Sistema detecta estadía anterior; no es checkbox manual |
| Encabezado | Responsable | — | `FUNCIONALIDAD` | Usuario logueado |
| 1. Datos personales | Fecha de ingreso | — | `FUNCIONALIDAD` | Timestamp de la admisión |
| 1. Datos personales | DNI / CUIL | — | `FUNCIONALIDAD` | Clave de búsqueda del Legajo Ciudadano |
| 1. Datos personales | Nombre y apellido | — | `FUNCIONALIDAD` | Legajo Ciudadano / RENAPER (RN-DI-12) |
| 1. Datos personales | Edad | — | `FUNCIONALIDAD` | Calculada de fecha de nacimiento |
| 1. Datos personales | Lugar y fecha de nacimiento | — | `FUNCIONALIDAD` | Legajo Ciudadano / RENAPER (RN-DI-12) |
| 1. Datos personales | Tel. / Cel. | — | `FUNCIONALIDAD` | Pre-completar del Legajo Ciudadano |
| 2. Reingreso | Fecha de reingreso | — | `FUNCIONALIDAD` | Nueva fecha de admisión; auto-capturada |
| 2. Reingreso | Observaciones | texto | `FORMULARIO` | Contexto del reingreso |
| 2. Reingreso | Observaciones ampliadas | texto libre | `FORMULARIO` | |
| 3. Sit. personal, educativa y laboral | Nivel educativo | selector | `FORMULARIO` | Pre-completar desde legajo educativo si existe |
| 3. Sit. personal, educativa y laboral | Capacitaciones | texto | `FORMULARIO` | |
| 3. Sit. personal, educativa y laboral | Interés en formación | texto | `FORMULARIO` | |
| 3. Sit. personal, educativa y laboral | Ocupación | texto | `FORMULARIO` | Pre-completar desde legajo laboral si existe |
| 3. Sit. personal, educativa y laboral | Lugar de trabajo | texto | `FORMULARIO` | |
| 3. Sit. personal, educativa y laboral | Ingreso mensual | número | `FORMULARIO` | |
| 3. Sit. personal, educativa y laboral | Empleo (Formal / Informal) | selector | `FORMULARIO` | |
| 3. Sit. personal, educativa y laboral | Oficio / saber laboral | multi-selector | `FORMULARIO` | Carpintería / Electricista / Albañilería / Soldador/a / Mecánica / Peluquería / Jardinería / Panadería / Artesanía / Otro |
| 3. Sit. personal, educativa y laboral | Ayuda económica externa (Sí/No + monto) | bool + número | `FORMULARIO` | |
| 3. Sit. personal, educativa y laboral | Plan social / beca (Sí/No + cuál) | bool + texto | `FORMULARIO` | |
| 3. Sit. personal, educativa y laboral | Jubilación / pensión (Sí/No + cuál) | bool + texto | `FORMULARIO` | |
| 4. Grupo familiar | Tabla grupo familiar | tabla N filas | `FORMULARIO` | Nombre / Parentesco / Edad / Educación / Ocupación / Ingreso |
| 5. Dinámica familiar | Relación con su familia | texto | `FORMULARIO` | |
| 5. Dinámica familiar | Último domicilio | texto | `FORMULARIO` | Domicilio previo al ingreso al dispositivo |
| 5. Dinámica familiar | Motivo de egreso | texto | `FORMULARIO` | ⚠ "Egreso" aquí = razón por la que dejó su hogar anterior. No es el egreso del dispositivo. |
| 5. Dinámica familiar | Derivación / referencia | texto | `FORMULARIO` | Quién o qué institución derivó al ciudadano |
| 5. Dinámica familiar | Historia familiar | texto libre | `FORMULARIO` | |
| 6. Vivienda | Posee vivienda (Sí/No) | bool | `FORMULARIO` | |
| 6. Vivienda | Condición | selector | `FORMULARIO` | Propia / Alquilada / Prestada |
| 6. Vivienda | Observaciones | texto | `FORMULARIO` | |
| 6. Vivienda | Localidad / barrio | texto | `FORMULARIO` | |
| 7. Ingresos y egresos econ. | Ingreso total mensual | número | `FORMULARIO` | |
| 7. Ingresos y egresos econ. | Ayuda alimentaria | multi-selector | `FORMULARIO` | Comedor / Bolsa / Trueque / Otro |
| 7. Ingresos y egresos econ. | Alquiler / Medicamentos / Transporte / Créditos / Otros | número (x5) | `FORMULARIO` | Cinco campos de gasto mensual declarado |
| 7. Ingresos y egresos econ. | Total egresos | — | `FUNCIONALIDAD` | Calculado: suma de los conceptos anteriores |
| 7. Ingresos y egresos econ. | Saldo estimado | — | `FUNCIONALIDAD` | Calculado: ingreso total − total egresos |
| 8. Red de sostén | Tipos de red | multi-selector | `FORMULARIO` | Familiares / Vecinos / Iglesia / Centro comunitario / Estado / Otros |
| 8. Red de sostén | Detalle / referentes | texto libre | `FORMULARIO` | |
| 9. Salud | Cobertura de salud (Sí/No) | bool | `FORMULARIO` | |
| 9. Salud | Nro. afiliado | texto | `FORMULARIO` | |
| 9. Salud | Tabla Problema / Enfermedad / Tratamiento / Medicación | tabla N filas | `FORMULARIO` | |
| 9. Salud | Problemas de salud declarados | multi-selector | `FORMULARIO` | Diabetes / Cardíacos / Respiratorios / Salud mental / Discapacidad / Otros |
| 10. Grado de dependencia | Condición funcional | selector | `FORMULARIO` | Autoválido / Semi-válido / Postrado |
| 11. Comidas *(nuevo 2026-07)* | Régimen alimentario | multi-selector | `FORMULARIO` | Normal / Dieta blanda / Baja en sodio / Baja en azúcar / Vegetariana-Vegana / Sin gluten |
| 12. Consumos | Consume sustancias (Sí/No) | bool | `FORMULARIO` | |
| 12. Consumos | Cuáles | texto | `FORMULARIO` | |
| 12. Consumos | Tratamiento | selector | `FORMULARIO` | Ambulatorio / Internación / Otro |
| 12. Consumos | Derivación | texto | `FORMULARIO` | |
| 13. Situaciones de crisis | Situaciones registradas | multi-selector | `FORMULARIO` | Violencia / Adicciones / Abandono / Migración / Enfermedad grave / Muerte familiar / Otros |
| 13. Situaciones de crisis | Descripción breve | texto libre | `FORMULARIO` | |
| 14. Necesidades básicas | Necesidades observadas | multi-selector | `FORMULARIO` | Hacinamiento / Vivienda precaria / Falta de agua / Niños sin escuela / Problemas de salud |
| Cierre del relevamiento *(nuevo 2026-07)* | Fecha de egreso | — | `FUNCIONALIDAD` | Flujo de egreso del dispositivo, no del formulario de admisión. Igual que la Sección H del F-00 AM: acción separada al momento del retiro. |
| Cierre del relevamiento *(nuevo 2026-07)* | Motivo de egreso | — | `FUNCIONALIDAD` | Parte del flujo de egreso |
| Cierre del relevamiento *(nuevo 2026-07)* | Lugar de egreso / destino | — | `FUNCIONALIDAD` | Parte del flujo de egreso |
| Cierre | Responsable del relevamiento | — | `FUNCIONALIDAD` | Usuario logueado |
| Cierre | Firma | — | `FUNCIONALIDAD` | Usuario logueado |
| Cierre | Fecha de carga / revisión | — | `FUNCIONALIDAD` | Timestamp del sistema |
| Cierre | Estado (Completo / Pendiente) | — | `FUNCIONALIDAD` | Borrador / completado según flujo del sistema |

---

## 5. Actores y roles

Anclado en `core/rbac.py` (categorías de rol; la categoría **PROGRAMA** ya exige FK a un
`Programa`). Los roles que aplican a Dispositivos:

| Actor (NODO) | Rol propuesto | Acceso / alcance | Qué hace |
|---|---|---|---|
| **Operador del dispositivo** | Categoría PROGRAMA, alcance al dispositivo. | Ve y opera **su** dispositivo. | Carga/actualiza personas, admisiones, egresos, prestaciones y datos operativos. |
| **Responsable institucional** | Categoría PROGRAMA/INSTITUCION. | Su dispositivo. | Controla la carga y confirma cierres (diarios/mensuales en fases posteriores). |
| **Supervisor del área** | Categoría PROGRAMA. | Su área/varios dispositivos. | **Valida** altas de dispositivo, cambios sensibles, observaciones y correcciones. |
| **Administrador central** | Categoría SISTEMA/PROGRAMA. | Todo el programa. | Catálogos, perfiles/permisos, reaperturas, fusión de duplicados, configuración. |
| **Equipo territorial / relevamiento** | Categoría PROGRAMA/INSTITUCION. | Relevamiento. | Releva y propone correcciones de datos maestros e infraestructura. |
| **Consulta / auditoría** | Rol de solo lectura. | Reportes/trazabilidad. | Accede a reportes y trazabilidad **sin modificar**. |

**Anclaje:** el catálogo RBAC ya tiene módulos `programas` (`programa.ver/operar/configurar`,
alcance=programa) y `relevamientos`. Se agregarían codenames para Dispositivos (ej.
`dispositivo.ver/operar/configurar`, `dispositivo.admitir`, `merendero.operar`). **No inventar
esquema paralelo** — reusar `RolMeta` (`users/models/__init__.py:25`) con `categoria=PROGRAMA`
y `programa = Programa(codigo="DISPOSITIVOS")`.

---

## 6. Funcionamiento end-to-end

### 6.1 Legajo Dispositivo

1. **Alta del dispositivo (P01).** Un usuario autorizado **busca primero** por código/nombre/
   localidad (evita duplicados). Si no existe, crea un **borrador**, completa identidad
   institucional, ubicación + geolocalización, responsable, **tipo**, capacidad (camas),
   horarios y contacto, y referencia el instrumento de creación.
2. **Validación (supervisor).** El supervisor compara con la fuente oficial y **valida, observa
   o rechaza**. Al validar, el dispositivo queda **Activo** y habilitado para recibir personas.
3. **Configuración operativa (F-01).** Se cargan **camas totales** y reglas de ingreso/egreso.
4. **Admisión de persona (P04).** El operador **busca la persona por DNI** en el Legajo
   Ciudadano (si existe se relaciona, si no se crea). Verifica disponibilidad de cama, **asigna
   cama**, registra **fecha/hora de ingreso** y completa el **formulario F-00 según el tipo** del
   dispositivo (info específica de la persona).
5. **Estadía.** Durante la permanencia se registran cambios de cama, sala, modalidad o referente,
   conservando historial.
6. **Egreso / traslado.** El egreso registra **fecha, motivo, destino y responsable** y **libera
   la cama**. El traslado cierra la estadía anterior y abre una nueva vinculada al mismo legajo.
7. **Cálculos automáticos.** En todo momento el sistema deriva **camas libres**, **camas
   ocupadas** y **métricas de ingreso/egreso/ocupación** desde las admisiones activas (RN-DI-08).
8. **Solapa en el Legajo Ciudadano.** Mientras la persona esté admitida (activa), aparece la
   **solapa "Dispositivos"** en su legajo, mostrando el estado.

### 6.2 Legajo Merenderos

1. **Alta del merendero (P06).** Un/a **vecino/a** que abre un merendero presenta la solicitud
   (datos institucionales, responsable, domicilio + geolocalización, zona, barrio, días/horarios,
   capacidad) junto con la **documentación respaldatoria** requerida.
2. **Validación.** El área controla domicilio, capacidad y documentación → aprueba/observa/
   rechaza. La aprobación crea el **legajo del merendero** (Activo).
3. **Entrega de mercaderías.** Se registra **cantidad de kits de mercadería**, **fecha de
   entrega** y **servicio** (núcleo del programa: la entrega de mercadería al merendero).
4. **Prestación (F-02).** Planilla **mensual** de raciones servidas por día y servicio
   (**desayuno/colación, almuerzo, merienda/colación, cena**), total por día y **observaciones**.
5. *(Padrón nominal de niños/tutores y asistencia alimentaria diaria — según P06 de NODO — ver
   §17 Q-7: confirmar si entra en esta épica o es fase posterior.)*

---

## 7. Estados

### 7.1 Dispositivo (P01)

```
Borrador → Pendiente de validación → Activo / Observado / Rechazado → Inactivo / Cerrado
```

| Estado | Significado |
|---|---|
| **Borrador** | Creado, admite datos incompletos (RN-DI-04). |
| **Pendiente de validación** | Esperando control del supervisor. |
| **Activo** | Validado; puede recibir personas, camas, admisiones. |
| **Observado** | Tiene observaciones; no puede iniciar nuevos períodos operativos hasta resolver las críticas. |
| **Rechazado** | El alta no procede. |
| **Inactivo / Cerrado** | No admite nuevas cargas; **conserva** personas, admisiones e historial. |

### 7.2 Admisión / Estadía (P04/P07)

```
Solicitado → En revisión → (Lista de espera / Aprobado / Rechazado) → Alojado → Egresado / Trasladado
```

### 7.3 Cama (P07)

```
Disponible → Reservada → Ocupada → Fuera de servicio
```

### 7.4 Merendero (P06)

```
Solicitud: Borrador → En revisión → Observada / Aprobada / Rechazada
Merendero: Activo → Suspendido / Cerrado
```

---

## 8. Entidades funcionales y mapeo al código existente

> **Anclaje code-first.** Qué se **reusa** y qué se **crea**. Rutas con `file_path:line`.

| Entidad NODO | ¿Existe? | Anclaje / decisión |
|---|---|---|
| **Programa** | ✅ Reuso | `programas/models/__init__.py:9` — crear **dos** instancias: `codigo="DISPOSITIVOS"` y `codigo="MERENDEROS"` (el `codigo`, `:32`, es la clave única obligatoria; conviene sumar ambas al enum `TipoPrograma`, `:12`). |
| **Persona** | ✅ Reuso | `Ciudadano` (`legajos/models/base.py:13`): DNI único e indexado, vivienda/laboral/educativo/salud/migración ya modelados. |
| **Identidad / RENAPER** | ✅ Reuso | `legajos/services/consulta_renaper.py` (DNI+sexo → autocompleta). |
| **Solapa en legajo** | ✅ Reuso | `programas/services/solapas.py` — `SolapasService.obtener_solapas_ciudadano()` genera solapa dinámica si hay inscripción activa. Hay que enganchar Dispositivos al mismo mecanismo. |
| **Roles/permisos** | ✅ Reuso | `core/rbac.py` + `RolMeta` (`users/models/__init__.py:25`), categoría PROGRAMA con FK a Programa. |
| **Formulario configurable** | ✅ Reuso (patrón) | `PreguntaGlobal` (`programas/models/__init__.py:569`) + `RequisitoNativo` (`:599`) con tipos STRING/INT/SELECTOR/SELECTOR_MULTIPLE/DATE/ARCHIVO (`TipoCampo`, `:330`). Adaptar: la clave de agrupación pasa de "Segmento" a "Tipo de dispositivo". |
| **Auditoría/traza** | ✅ Reuso (patrón) | `TracaFormulario` (`programas/models/__init__.py:760`) — patrón antes/después/usuario para RN-DI-06. |
| **Lista de espera** | ✅ Reuso (patrón) | `ListaEspera` (`programas/models/__init__.py:791`). |
| **Dispositivo (institución)** | ⛔ NUEVO | No existe. Crear `DispositivoInstitucional` (evitar colisión con alias `dispositivo` de `LegajoAtencion`). Campos mínimos: código único, nombre, tipo, estado, domicilio, geolocalización, contacto, responsable, capacidad (camas), horarios. |
| **Cama / Plaza** | ⛔ NUEVO | No existe. Estados Disponible/Reservada/Ocupada/Fuera de servicio; ocupación calculada (RN-DI-08). |
| **Admisión / Estadía** | ⛔ NUEVO (¿reuso parcial?) | No existe con semántica de cama/ingreso-egreso. Evaluar extender `InscripcionPrograma` (`:93`, ya tiene estados y vía de ingreso) vs modelo dedicado. |
| **Merendero** | ⛔ NUEVO | No existe. Legajo institucional propio en un **`Programa` separado** (`codigo="MERENDEROS"`): documentación respaldatoria + entrega de mercaderías + prestación F-02. Sin camas. |
| **Asistencia/prestación diaria** | ⛔ NUEVO | No existe modelo. (`legajos_registroasistencia` aparece referenciada en particionado pero **sin modelo definido** — confirmar.) |
| **Indicadores/tablero** | 🟡 Mínimo | `dashboard` solo tiene un contador primitivo (`dashboard/models/__init__.py`). Tablero real = trabajo nuevo. |

**Conclusión de modelado:** la épica crea **4 entidades nuevas** (Dispositivo institucional,
Cama, Admisión/Estadía, Merendero) + el set de **formularios configurables por tipo**, y
**reusa** toda la base de identidad, solapas, RBAC y patrón de preguntas/traza.

---

## 9. Formularios configurables (F-00 / F-01 / F-02)

El Miro distingue tres "formularios". Se modelan con el mecanismo dinámico ya probado en Becas:

| Form. | Qué es | Mecanismo propuesto |
|---|---|---|
| **F-00** | Información específica de **la persona** según el **tipo** de dispositivo (Adulto Mayor, Abordaje Psicosocial, …). | Preguntas configurables **agrupadas por tipo de dispositivo** (patrón `RequisitoNativo`), con secciones por bloque. Respuestas en JSON tipo `data` del `Formulario`. |
| **F-01** | **Registro diario de novedades por turno** del dispositivo. Contiene turno (Mañana/Tarde/Noche), cantidades calculadas de camas y movimientos, y observaciones libres. *Actualización: no es solo configuración — es un registro operativo diario. Resuelve Q-9.* | Modelo de registro diario propio del dispositivo. Las cantidades (camas totales/ingresos/egresos/ocupación/disponibles) son **calculadas**; el operador solo aporta el turno y las observaciones. Ver §9.1. |
| **F-02** | Prestación del **merendero** (servicios alimentarios + observaciones). | Campos fijos del modelo `Merendero`/prestación; los "servicios" pueden ser SELECTOR_MULTIPLE configurable. |

**Paralelo con Becas (importante para reuso):**

```
Becas:        Segmento            → RequisitoNativo (campos configurables del formulario)
Dispositivos: Tipo de dispositivo → (mismo patrón) campos configurables del F-00 por tipo
```

Esto permite que agregar/editar el formulario de un tipo (o sumar el detalle de UPI/ECA, UPI,
etc.) sea **configuración, no código**. Los datos que provee **RENAPER/escaneo** (personales,
CUIL, domicilio) **no se vuelven a preguntar** (RN-DI-12, alinea con RN-37 de Becas).

---

### 9.1 F-01 — Registro Diario de Novedades — campo a campo

**Resumen:** 2 al formulario · 9 funcionalidades · 1 a confirmar

| Sección | Campo | Tipo | Clasificación | Nota |
|---|---|---|---|---|
| Datos del registro | Institución / sede | — | `FUNCIONALIDAD` | Contexto del dispositivo activo |
| Datos del registro | Fecha | — | `FUNCIONALIDAD` | Fecha del sistema al crear el registro |
| Datos del registro | Responsable del turno | — | `FUNCIONALIDAD` | Usuario logueado |
| Datos del registro | Turno | selector | `FORMULARIO` | Mañana / Tarde / Noche — único dato que aporta el operador en el encabezado |
| Novedades | A. Camas totales — Cantidad | — | `FUNCIONALIDAD` | Viene de la configuración del dispositivo |
| Novedades | A. Camas totales — Observaciones | texto | `CONFIRMAR` | ¿Un cambio de capacidad se anota aquí o dispara una reconfiguración formal? |
| Novedades | B. Ingresos del día — Cantidad | — | `FUNCIONALIDAD` | Calculado: count de admisiones con fecha = hoy |
| Novedades | C. Egresos del día — Cantidad | — | `FUNCIONALIDAD` | Calculado: count de egresos con fecha = hoy |
| Novedades | D. Ocupación nocturna — Cantidad | — | `FUNCIONALIDAD` | Calculado: estadías activas al cierre del día |
| Novedades | E. Camas disponibles — Cantidad | — | `FUNCIONALIDAD` | Calculado: totales − ocupadas − fuera de servicio (RN-DI-08) |
| Novedades | Observaciones filas B–E | — | `FUNCIONALIDAD` | Sin campo propio: cada admisión/egreso ya tiene observaciones propias |
| Novedades | Observaciones generales del turno | texto libre | `FORMULARIO` | Narrativa libre del turno; campo principal que aporta el operador |
| Cierre | Firma y Aclaración | — | `FUNCIONALIDAD` | Usuario logueado |

---

## 10. Gestión de camas, ingreso/egreso y cálculos automáticos (P07)

Esto es el corazón del "Legajo Dispo" del Miro ("Camas totales", "Cama Libres", "Camas
ocupadas", "Métrica de ingreso/egreso/ocupación").

**Reglas (de NODO P07, ancladas en RN-DI-08):**

- **Camas totales** = capacidad configurada del dispositivo (F-01).
- **Camas ocupadas** = `count(estadías activas con cama asignada)` — **calculado**, nunca carga manual.
- **Camas libres** = camas totales − ocupadas − fuera de servicio.
- **Una cama no puede asignarse a dos personas a la vez** (RN-DI-09).
- **Censo diario** (si entra en alcance): `existencia inicial + ingresos − egresos = existencia final`.
- **Métricas**: ingresos, egresos, permanencia promedio, % de ocupación — derivadas de las estadías.

**Indicador de ocupación (semáforo, de NODO §8):** Verde <50% · Amarillo 50–79% · Rojo ≥80%.
Configurable por tipo.

> **F-01 y el censo diario (Q-9 cerrada):** el formulario F-01 del cliente es un "Registro Diario
> de Novedades por Turno". Confirma que el **censo diario sí existe** en el circuito operativo.
> En el sistema las cantidades son calculadas (no cargadas manualmente); el operador solo
> selecciona el turno y escribe observaciones libres. Ver clasificación campo a campo en §9.1.

> **Q-5 (cerrada, cliente 2026-07-01):** **UPI, ECA y Residencias Universitarias manejan camas**,
> además de Adultos Mayores y Abordaje Psicosocial. Merenderos, al ser programa aparte, **no**
> maneja camas. Queda por confirmar solo **Fortalecimiento Familiar**. Para tipos sin internación,
> "camas" se generaliza a "plazas/cupos" (misma mecánica de ocupación calculada, RN-DI-08).

---

## 11. Merenderos (P06)

**Programa propio** del Ministerio (confirmado por el cliente), hermano de Dispositivos y **sin
camas**. El núcleo del negocio: **vecinos/as abren un merendero y presentan la documentación
respaldatoria**; el Ministerio **valida y entrega mercaderías**; el merendero registra la
prestación alimentaria. Campos del Miro + formularios:

- **Información base:** Nombre, Dirección, **Zona**, **Barrio**, Teléfono + **Responsable**
  (Nombre, CUIT/DNI, Email).
- **Documentación respaldatoria:** la que presenta quien abre el merendero (requisito de alta;
  ver circuito de validación en §6.2).
- **Entrega de mercaderías:** cantidad de **kits de mercadería**, **Fecha de entrega**, **Servicio**.
- **Prestación (F-02):** planilla **mensual** — una fila por día del mes, columnas por servicio
  (Desayuno/colación, Almuerzo, Merienda/colación, Cena), total por día y observaciones. Ver
  detalle campo a campo abajo.

NODO P06 amplía con **padrón nominal de niños y tutores**, **días/horarios de apertura** y
**asistencia/entrega de kits con responsable receptor**. Confirmar cuánto de eso entra en V1
(Q-7).

> **Q-2 (cerrada, cliente 2026-07-01):** Merenderos es un **programa propio** del Ministerio, no
> un tipo dentro de Dispositivos. Se modela como un **segundo `Programa`** (`codigo="MERENDEROS"`)
> que reusa el patrón de legajo institucional pero con su propio circuito (documentación →
> validación → entrega de mercaderías → prestación F-02), sin camas.

---

### F-02 — Prestación Alimentaria Mensual — campo a campo

*Formulario mensual: una fila por día del mes, columnas por servicio alimentario.*

**Resumen:** 5 al formulario · 6 funcionalidades · 1 a confirmar (C-8)

| Sección | Campo | Tipo | Clasificación | Nota |
|---|---|---|---|---|
| Cabecera | Institución / sede | — | `FUNCIONALIDAD` | Contexto del merendero activo |
| Cabecera | Mes | — | `FUNCIONALIDAD` | Pre-completado con el mes actual al crear el registro |
| Cabecera | Año | — | `FUNCIONALIDAD` | Pre-completado |
| Cabecera | Servicio (☐ Desayuno ☐ Almuerzo ☐ Merienda ☐ Cena) | multi-selector | `CONFIRMAR` | C-8: el PDF lo pone en la **cabecera del registro mensual** (checkboxes) → sugiere selección por mes; probablemente sea configuración del legajo del merendero pre-marcada cada mes. Determina qué columnas se cargan en la tabla. |
| Tabla diaria | Día (1–31) | — | `FUNCIONALIDAD` | El sistema genera una fila por cada día del mes |
| Tabla diaria | Desayuno / colación | número o S/N | `FORMULARIO` | Raciones servidas **o** S/N según el "criterio de carga acordado" (nota del PDF) |
| Tabla diaria | Almuerzo | número o S/N | `FORMULARIO` | Raciones servidas o S/N según criterio acordado |
| Tabla diaria | Merienda / colación | número o S/N | `FORMULARIO` | Raciones servidas o S/N según criterio acordado |
| Tabla diaria | Cena | número o S/N | `FORMULARIO` | Raciones servidas o S/N según criterio acordado |
| Tabla diaria | Total por día | — | `FUNCIONALIDAD` | Calculado: suma de los servicios del día (solo si la carga es numérica) |
| Tabla diaria | Observaciones por día | texto | `FORMULARIO` | Texto libre opcional por fila |
| Tabla diaria | Firma por día | — | `FUNCIONALIDAD` | Usuario logueado al cargar la fila |

> **Criterio de carga (nuevo, PDF F-02):** la nota del formulario aclara que las celdas de
> prestación pueden llevar **cantidad de raciones** o **marcarse S/N** "según el criterio de carga
> acordado". Definir con el cliente cuál criterio rige (impacta el tipo de campo y si el "Total
> por día" tiene sentido). Se suma como parte de C-8.

---

## 12. Reglas de negocio (consolidadas, preliminares)

Combina las **reglas transversales de NODO (RN-01…RN-10)** con reglas propias de Dispositivos.

| ID | Regla |
|---|---|
| RN-DI-01 | **No eliminación física.** Los registros operativos se **anulan/inactivan**, nunca se eliminan; se conserva historial (NODO RN-01). |
| RN-DI-02 | **Identidad única.** La persona se busca por **DNI** (y reglas de coincidencia) antes de crear; una persona puede estar vinculada a varios dispositivos sin duplicar identidad (NODO RN-02). |
| RN-DI-03 | **Dato único de dispositivo.** Antes de crear un dispositivo, se busca por código/nombre/localidad para evitar duplicados. El **código institucional es único**. |
| RN-DI-04 | **Campos por estado.** Un **borrador** admite datos incompletos; **validar/cerrar** exige los campos obligatorios del proceso (NODO RN-04). |
| RN-DI-05 | **Control de acceso por alcance.** El permiso depende de rol, área, dispositivo y sensibilidad (NODO RN-05); se implementa con `core.rbac` categoría PROGRAMA. |
| RN-DI-06 | **Auditoría.** Altas, cambios, validaciones, egresos, reaperturas y fusiones registran **usuario, fecha, hora y valor anterior** (NODO RN-06). |
| RN-DI-07 | **Fechas coherentes.** La fecha de egreso no puede ser anterior a la de ingreso; asignaciones y períodos respetan orden cronológico (NODO RN-07). |
| RN-DI-08 | **Ocupación calculada.** Camas ocupadas/libres y métricas se **derivan** de las estadías activas, **no** de una carga manual paralela (NODO RN-08). |
| RN-DI-09 | **Una cama, una persona.** Una cama no puede asignarse simultáneamente a dos personas. |
| RN-DI-10 | **Dispositivo cerrado.** No admite nuevas admisiones; conserva personas, estadías e historial. |
| RN-DI-11 | **Dispositivo observado.** No puede iniciar nuevos períodos operativos hasta resolver observaciones críticas. |
| RN-DI-12 | **RENAPER/escaneo.** Los datos que provee RENAPER o el escaneo de DNI no se vuelven a preguntar; solo se cargan a mano sin conexión. |
| RN-DI-13 | **Validación por responsabilidad.** El dispositivo **carga**; el área competente **observa/valida/rechaza** (NODO §1). |
| RN-DI-14 | **No cupo sin disponibilidad.** No se aprueba una admisión si el dispositivo está cerrado o sin cama, salvo autorización registrada. |
| RN-DI-15 | **Lista de espera.** Si no hay cama, la admisión validada va a lista de espera; la promoción es manual (reusa patrón `ListaEspera`). |
| RN-DI-16 | **Traslado.** Cierra la estadía anterior y abre una nueva vinculada al mismo legajo, conservando historia. |
| RN-DI-17 | **Solapa dinámica.** Si el ciudadano tiene una admisión activa en un dispositivo, aparece la solapa "Dispositivos" en su legajo con el estado (reusa `SolapasService`). |
| RN-DI-18 | **Contingencia territorial.** Debe contemplarse carga diferida/sin conectividad evitando duplicados en la sincronización (NODO RN-09). |
| RN-DI-19 | **Nomenclatura.** El "Dispositivo institucional" (esta épica) es distinto del alias `dispositivo` de `LegajoAtencion`. Resolver con un nombre de modelo no ambiguo. |
| RN-DI-20 | **Fuente del dato.** Todo dato migrado o corregido conserva fuente, fecha y responsable (NODO RN-03); no se publica como oficial una dirección pendiente de verificación. |
| RN-DI-21 | **Merenderos = programa propio.** El Programa Merenderos es un `Programa` separado (`codigo="MERENDEROS"`), no un tipo de Dispositivos. El alta la inicia un/a **vecino/a con documentación respaldatoria**; el Ministerio valida y **entrega mercaderías**. No maneja camas (cliente 2026-07-01). |
| RN-DI-22 | **Camas por tipo.** Manejan camas: Adulto Mayor, Abordaje Psicosocial, UPI, ECA y Residencias Universitarias. En tipos sin internación, "camas" se generaliza a "plazas/cupos" con la misma ocupación calculada (RN-DI-08). Fortalecimiento Familiar a confirmar. |

---

## 13. Fuera de alcance / diferido

### Fuera de alcance (esta épica)
- **P08 — Línea 102 / denuncias / riesgo / derivaciones NNA** (casos sensibles; épica propia).
  ℹ️ El cliente ya envió el **F-00 Línea 102 – Registro Inicial de Denuncia** (3 pág.); se archiva
  como insumo de esa futura épica. Su §14 ya prevé el enganche con NODO (`ID legajo dispositivo/área`).
- **P10 — Personal y asignaciones por dispositivo** (no está en el Miro).
- **P09 — Fondos, rendiciones financieras** (solo entran los *kits de mercadería* del merendero).

### Diferido a fase/versión posterior
- **P11 — Infraestructura y preparación tecnológica** (semáforo edilicio y de PCs).
  ℹ️ El cliente envió el formulario **Relevamiento de PC** (prueba de funcionamiento + requisitos
  mínimos NODO + semáforo Verde/Amarillo/Rojo); base lista para cuando se aborde P11.
- **P13 — Cierre mensual formal** y tablero de comando completo (sí indicadores básicos).
- **P05 — Asistencia/prestación diaria general** más allá de merenderos.
- **Padrón nominal de niños/tutores y asistencia alimentaria diaria** del merendero (P06 ampliado).

### Insumos de referencia recibidos (no son alcance en sí, orientan el modelado)
- **Ficha socio-económica "Albergue Familiar Madre Teresa de Calcuta"** — la usa hoy el equipo
  de Abordaje Psicosocial en los **operativos de contención nocturna**. Confirma que ese proceso
  maneja **préstamos de cama** (camas), grado de dependencia, grupo familiar y datos de
  procedencia, y agrega el concepto de **"Comensal"** y **servicio médico** (PERR/PED/NEFRO/…).
  Sirve de referencia para el F-00 de Abordaje / albergues y abre Q-11 (§17): ¿"Albergue" es otro
  tipo de dispositivo o una variante del tipo Abordaje Psicosocial?

---

## 14. Dependencias e impacto crítico

- **`programas`:** se apoya en el `Programa` genérico; se agregan modelos institucionales nuevos.
- **`legajos` / `ciudadanos`:** la persona = `Ciudadano`. Reusar identidad (DNI/CUIL) y RENAPER;
  vigilar deduplicación. La relación con el programa se visualiza con **solapas dinámicas**.
- **`users` / `core.rbac`:** roles del programa con alcance por dispositivo. **No inventar
  esquema paralelo.**
- **`solapas.py`:** enganchar la solapa de Dispositivos al `SolapasService`.
- **Migración inicial (P12):** alta de dispositivos existentes desde matriz/Excel con fuente y
  nivel de confianza; reconciliar antes de definir el padrón oficial.
- **Colisión de nombres (`dispositivo`)** — RN-DI-19.

---

## 15. Pantallas del backoffice (mapa preliminar)

| Pantalla | Operaciones principales |
|---|---|
| **Dispositivos** | ABM con búsqueda anti-duplicado; alta en borrador; validar/observar/rechazar; ver estado y ocupación. |
| **Detalle de dispositivo** | Información base, tipo, configuración de camas (F-01), listado de admisiones, cálculos automáticos. |
| **Admisión / Egreso** | Buscar persona (DNI) → asignar cama → completar F-00 según tipo → registrar egreso/traslado. |
| **Camas** | Estado de cada cama (disponible/reservada/ocupada/fuera de servicio); censo. |
| **Merenderos** | ABM institucional; información extra (kits); prestación F-02. |
| **Configuración del programa** | ABM de **tipos de dispositivo** y de los **campos del F-00 por tipo** (preguntas configurables); catálogo de servicios de merendero. |
| **Indicadores** | Ocupación, disponibilidad, actualización de datos, completitud (semáforos §8 de NODO). |
| **Reportes** | Exportar dispositivos, ocupación, admisiones/egresos, padrón de merenderos. |

---

## 16. Mapeo NODO (P01–P13) → alcance de la épica

| Proc. | Nombre | Alcance | Anclaje / nota |
|---|---|---|---|
| P01 | Alta y mantenimiento del dispositivo | ✅ Núcleo | Modelo `DispositivoInstitucional` nuevo; estados §7.1. |
| P02 | Usuarios, perfiles y permisos | 🟡 Reuso | `core.rbac` + roles del programa. |
| P03 | Alta/actualización de persona y legajo | ✅ Reuso | `Ciudadano` + RENAPER. |
| P04 | Inscripción, admisión, egreso y traslado | ✅ Núcleo | `Admisión/Estadía` nuevo; estados §7.2. |
| P05 | Asistencia y prestación diaria | 🟡 Parcial | Solo merenderos en V1. |
| P06 | Merenderos y comedores | ✅ Núcleo (**programa propio**) | `Merendero` + F-02 en `Programa codigo="MERENDEROS"`. |
| P07 | Albergues, residencias y camas | ✅ Núcleo | `Cama` + cálculos §10. UPI/ECA/Residencias con camas confirmadas. |
| P08 | Denuncias, riesgo y derivaciones | ⛔ Fuera | Línea 102, NNA. Form F-00 recibido y archivado. |
| P09 | Fondos, raciones, kits y rendiciones | 🟡 Parcial | Solo kits/mercadería del merendero. |
| P10 | Personal y asignaciones | ⛔ Fuera | No está en el Miro. |
| P11 | Infraestructura y preparación tecnológica | 🟡 Diferible | Semáforo de PCs. Form "Relevamiento de PC" recibido. |
| P12 | Migración, corrección y duplicados | 🟡 Transversal | Alta inicial de dispositivos. |
| P13 | Cierre mensual y tablero | 🟡 Diferible | Indicadores básicos sí. |

---

## 17. Preguntas abiertas (consolidado)

> Mientras existan pendientes **bloqueantes**, NO se generan issues (control estricto de
> `AGENTS.md`). Estado: Bloqueante · No bloq. · Diferida · Cerrada.
>
> **Al 2026-07-02 no quedan preguntas bloqueantes** (Q-2 y Q-5 cerradas, Q-1 reencuadrada como
> configuración). El único paso previo real a bajar issues son los **pendientes técnicos
> C-1…C-8** de ICORE (§17.3), que se resuelven code-first sobre el repo.

### 17.1 Alcance y dominio

| # | Pregunta | Para | Estado |
|---|---|---|:--:|
| Q-1 | **Tipos sin detalle.** Falta el detalle de los F-00 de **ECA, UPI, Residencias Universitarias y Fortalecimiento Familiar**. | Cliente | **Reencuadrada / No bloq.** — El cliente confirmó que los formularios se **amplían por configuración** ("no se elimina lo ya definido"). Se cargan como config cuando el Ministerio los releve; no bloquean el mecanismo. |
| Q-2 | **Merenderos: ¿tipo o programa aparte?** | Cliente | **Cerrada** — Es un **programa propio** (`codigo="MERENDEROS"`): entrega de mercaderías previa documentación respaldatoria. |
| Q-3 | **Qué es un "dispositivo".** Confirmar que = establecimiento físico (hogar/residencia) con capacidad de camas y responsable. | Cliente | No bloq. |
| Q-4 | **Tipos: ¿lista fija o configurable?** ¿Los tipos son fijos o un catálogo ABM que crece? | Cliente | **Encaminada** — El cliente confirmó crecimiento por configuración → catálogo ABM de tipos + F-00 configurables. Falta confirmar quién administra el catálogo. |
| Q-5 | **¿Todos los tipos manejan camas?** | Cliente | **Cerrada** — UPI, ECA y Residencias **sí** (+ AM y Abordaje). Solo Fortalecimiento Familiar pendiente. Se generaliza a "plazas/cupos" donde no hay internación. |

### 17.2 Procesos y operación

| # | Pregunta | Para | Estado |
|---|---|---|:--:|
| Q-6 | **Validación del alta.** ¿Quién valida el alta de un dispositivo (supervisor del área) y con qué criterio? ¿Aplica el circuito borrador→validación a todos los tipos? | Cliente | No bloq. |
| Q-7 | **Merenderos en V1.** ¿Entra el **padrón nominal de niños/tutores** y la **asistencia/entrega de kits diaria** (P06 ampliado), o V1 es solo legajo + prestación F-02? | Cliente | No bloq. |
| Q-8 | **Asistencia diaria (P05).** ¿Hay registro de asistencia diaria para dispositivos con internación, o el alcance es solo admisión/egreso? | Cliente | No bloq. |
| Q-9 | **Censo de camas.** ¿Se requiere censo diario formal (existencia inicial + ingresos − egresos)? | Cliente | **Cerrada** — El F-01 es un Registro Diario de Novedades por Turno; el censo diario existe. Las cantidades son calculadas en el sistema. Ver §9.1 y §10. |
| Q-10 | **Reingreso (Abordaje Ps).** El F-00 psicosocial tiene "Reingreso". ¿Cómo se modela una persona que vuelve a ingresar (nueva estadía vinculada al mismo legajo)? | Cliente | No bloq. |
| Q-11 | **Albergues / contención nocturna.** La ficha "Calcuta" y los operativos de contención nocturna de Abordaje Psicosocial: ¿"Albergue" es otro tipo de dispositivo, una variante del tipo Abordaje Psicosocial, o un proceso (P05) aparte? ¿Entra en V1? | Cliente | No bloq. |

### 17.3 Técnicas (ICORE) — resueltas code-first (2026-07-02)

| # | Tarea | Estado |
|---|---|:--:|
| C-1 | **Nombre del modelo.** | **✅ Resuelta** — `dispositivo` es solo una `@property` de solo lectura del modelo Acompañamiento (`legajos/models/base.py:291`, alias de `programa`): **no colisiona a nivel ORM**, es ambigüedad semántica. Decisión: modelo **`DispositivoInstitucional`** como **submódulo de `programas`** siguiendo el precedente de Becas (`programas/models/dispositivos.py` re-exportado en `__init__`; templates en `programas/templates/programas/dispositivos/`). No crear app nueva. |
| C-2 | **Admisión: reuso vs nuevo.** | **✅ Resuelta: modelo dedicado `Admision`** + membresía sincronizada. Razones duras: (1) `InscripcionPrograma` tiene `unique_together [ciudadano, programa]` (`programas/models/__init__.py:153`) → **imposible** modelar reingresos/estadías múltiples (Q-10); (2) sin FK a dispositivo, sin cama, `DateField` sin hora, estados incompatibles. **Patrón:** `Admision` (N estadías por ciudadano, FK a dispositivo+cama) y **una** `InscripcionPrograma(ciudadano, programa=DISPOSITIVOS)` como membresía cuyo estado se deriva de las admisiones activas → la solapa funciona gratis (ver C-4). |
| C-3 | **Formularios por tipo.** | **✅ Resuelta: replicar el patrón, no re-clavarlo.** `RequisitoNativo` tiene FK **dura** a `Segmento`/`Subsegmento` (`:612-626`); re-anclarlo arriesga el RN-32 de Becas. Decisión: modelo hermano **`CampoTipoDispositivo`** (mismo shape: texto/tipo/opciones/orden/obligatorio, reusando el enum `TipoCampo` `:330`) + FK a `TipoDispositivo` + campo **`seccion`** (los bloques A–J del F-00, que RequisitoNativo no tiene). Se reusa el mecanismo de render/validación, no la tabla. |
| C-4 | **Solapa.** | **✅ Resuelta** — `SolapasService.obtener_solapas_ciudadano` (`programas/services/solapas.py:29-61`) genera la solapa desde `InscripcionPrograma` activa. Con la membresía de C-2 la solapa "Dispositivos" **aparece sola**; solo falta (a) sumar `"DISPOSITIVOS"` al `url_map` de `_obtener_url_programa` (`:187`) o aceptar el fallback `legajos:programa_detalle`, y (b) si se quiere tab embebida con contenido propio, replicar el patrón `_obtener_solapa_becas` (`:206`). |
| C-5 | **`legajos_registroasistencia`.** | **✅ Resuelta: es un fantasma.** Solo aparece como config de particionado en `core/performance/advanced_partitioning.py:15` y `database_partitioning.py:17,29` — **no existe modelo ni tabla**. Si la asistencia diaria entra en alcance, es modelo nuevo. Sub-tarea técnica: limpiar esas referencias muertas del particionado. |
| C-6 | **Obra social (F-00 AM).** | **✅ Resuelta: ya existe.** `Ciudadano.obra_social` (`legajos/models/base.py:123`, CharField 200 "Obra social / prepaga", editable en `legajos/forms/ciudadanos.py:179`). El F-00 AM lo **pre-completa** (FUNCIONALIDAD), no lo re-pregunta. El papel pide "Obra social / N°": el texto libre de 200 chars admite nombre + número; si se quiere N° como campo aparte es decisión de producto en la task. |
| C-7 | **Grupo sanguíneo (F-00 AM).** | **✅ Resuelta: no existe** en ningún módulo del repo. Queda como campo del **F-00 AM** (FORMULARIO configurable). Recomendación para la task: evaluarlo como campo de `Ciudadano` (solapa Salud) porque es dato de la persona —no de la estadía— y así queda como dato único reutilizable. |
| C-8 | **F-02 Merenderos: "Servicio" + criterio de carga.** (a) ¿Los servicios (Desayuno/Almuerzo/Merienda/Cena) son configuración del legajo del merendero o un selector por cada registro mensual? El PDF los pone en la **cabecera del registro mensual**. (b) La nota del PDF permite cargar **raciones (número) o marcar S/N** "según el criterio de carga acordado" → definir cuál rige (impacta el tipo de campo y si el "Total por día" aplica). | **Pendiente (con cliente)** — único técnico abierto; no bloquea el modelado (el campo admite arrancar numérico). |

---

## 18. Próximos pasos

1. ✅ **Bloqueantes de alcance cerrados** (Q-1 reencuadrada, Q-2 y Q-5 cerradas) con la
   conformidad del cliente del 2026-07-01.
2. ✅ **Pendientes técnicos resueltos code-first** (2026-07-02): C-1…C-7 cerrados con anclajes
   en §17.3. Decisiones de modelado firmes: `DispositivoInstitucional` como submódulo de
   `programas` (precedente Becas) · `Admision` dedicada + membresía `InscripcionPrograma`
   sincronizada (la solapa sale gratis) · `CampoTipoDispositivo` replicando el patrón
   `RequisitoNativo` con `seccion` · `obra_social` se pre-completa · `grupo_sanguineo` va al
   F-00 (evaluar subirlo a Ciudadano en la task).
3. **Cerrar con el cliente los no-bloqueantes que tocan modelado:** C-8 (criterio de carga F-02),
   Q-11 (albergues / contención nocturna), Q-7/Q-8 (alcance V1 de merenderos y asistencia).
   Ninguno bloquea la generación de issues.
4. **Cargar como configuración** los F-00 de AM y Abordaje (detallados) y dejar ECA/UPI/
   Residencias/Fortalecimiento como tipos "a configurar" cuando el Ministerio los releve.
5. ✅ **Estimación de esfuerzo armada** (2026-07-02): **436 h**, backoffice-only — ver
   `docs/client/funcionalidades/estimacion-programa-dispositivos.md`. Reusa RBAC/RENAPER/DS;
   formularios de tipos pendientes = configuración sin desarrollo. **Pendiente de aprobación del
   Ministerio** antes de comprometerla en el financiero.
6. **Generación en GitHub** — épica(s) → análisis → sub-issues (receta de `AGENTS.md`). Definir si
   va **una épica por programa** (Dispositivos y Merenderos) o una épica con dos análisis, dado
   que son `Programa` distintos. → **ESTE ES EL PRÓXIMO PASO.**

---

## 19. Historial de cambios del análisis

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-06-25 | Versión inicial | Primer borrador a partir del Miro del Programa Dispositivos + Especificación NODO + mapeo del código real. |
| 2026-06-26 | Integración de formularios F-00/F-01/F-02 campo a campo | Se incorporaron los 4 formularios del cliente y se clasificó cada campo como FORMULARIO, FUNCIONALIDAD o CONFIRMAR. Se cerró Q-9 y se agregaron C-6, C-7, C-8. |
| 2026-07-02 | **Pendientes técnicos C-1…C-7 resueltos code-first** | `dispositivo` = property inofensiva → `DispositivoInstitucional` en submódulo de `programas`; `InscripcionPrograma` inviable como Admisión (`unique_together`) → modelo `Admision` + membresía sincronizada; `RequisitoNativo` no se re-clava → `CampoTipoDispositivo` con `seccion`; solapa vía membresía + url_map; `legajos_registroasistencia` = fantasma del particionado; `obra_social` existe (pre-completar); `grupo_sanguineo` no existe (F-00). Solo queda C-8 con el cliente. Próximo paso: generación de épica/issues. |
| 2026-07-02 | **Conformidad del cliente + observaciones (mail de Guido, 2026-07-01)** | Se cerró **Q-2** (Merenderos = **programa propio** → `codigo="MERENDEROS"`) y **Q-5** (UPI/ECA/Residencias manejan camas); se reencuadró **Q-1** (formularios crecen por configuración, no bloquean). Se amplió el **F-00 Abordaje Psicosocial** (§11 Comidas + Cierre/egreso → 45·20). Se redefinió **Merenderos** como entrega de mercaderías con documentación respaldatoria (§3, §6.2, §8, §11, RN-DI-21). Se registró detalle nuevo del **F-02** (Servicio en cabecera mensual + criterio raciones/SN → C-8). Se archivaron formularios recibidos: **F-00 Línea 102** (P08), **Relevamiento de PC** (P11) y **ficha "Calcuta"** (referencia albergues → nueva Q-11). Estado del doc: **aprobado, listo para issues** salvo pendientes técnicos ICORE (C-1…C-8). |
