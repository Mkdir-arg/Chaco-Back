# Programa Dispositivos — Legajo institucional, admisiones, camas y merenderos

!!! abstract "En una línea"
    Gestionar en el sistema cada **dispositivo** (hogares, residencias y espacios de atención) y cada **merendero**: su legajo institucional, las personas que ingresan y egresan, la disponibilidad de camas en tiempo real y la asistencia alimentaria.

| | |
|---|---|
| **Módulo** | Programas |
| **Estado** | Definición aprobada por el Ministerio — lista para desarrollo |
| **Programas** | Dispositivos y Merenderos (sobre la base de Programas, después de Becas) |
| **Última actualización** | 2026-07-02 |

!!! success "Novedad — Conformidad del Ministerio (01/07/2026)"
    El Ministerio revisó la propuesta y **confirmó su conformidad para avanzar con el desarrollo**, con estas definiciones:

    - **Merenderos es un programa propio** del Ministerio (no un tipo dentro de Dispositivos): consiste en la entrega de mercaderías a merenderos abiertos por vecinos y vecinas, que presentan previamente la documentación respaldatoria.
    - **UPI, ECA y Residencias Universitarias cuentan con camas** (UPI como Centros de Protección Integral; ECA como dispositivos de resguardo para niñas, niños y adolescentes).
    - El **formulario de Abordaje Psicosocial se amplió** con el régimen de comidas y el cierre del relevamiento.
    - Los formularios están **en etapa de relevamiento**: a medida que avance el trabajo con las áreas se incorporarán nuevos campos, sin eliminar lo ya definido. El sistema los soporta por **configuración**, sin cambios de programa.

!!! info "Encuadre dentro de NODO"
    NODO es la plataforma integral de gestión territorial del organismo. Esta etapa pone en el sistema **dos programas**: **Dispositivos** (legajo de cada institución, admisiones y egresos de personas, ocupación de camas) y **Merenderos** (legajo institucional y asistencia alimentaria). Otros frentes de NODO (Línea 102, personal, fondos, infraestructura tecnológica) se abordan en etapas posteriores.

---

## 1. Qué resuelve

Hoy la información de los dispositivos y merenderos vive dispersa (planillas, documentos, registros sueltos). Este módulo la unifica en un **único registro maestro por institución**, conectado al **legajo de cada persona** que pasa por ella. Con eso, el organismo puede saber **en todo momento** cuántas camas hay disponibles, quién está alojado, quién ingresó o egresó, y qué prestación brinda cada merendero, con trazabilidad completa.

Los principios que ordenan el módulo:

- **Dato único:** cada persona y cada dispositivo tienen un solo registro, reutilizado por todo el sistema.
- **Trazabilidad:** toda alta, cambio, validación y egreso queda registrado con usuario, fecha y hora.
- **Historial permanente:** los registros no se borran; se inactivan o cierran conservando la historia.
- **Validación por responsabilidad:** el dispositivo carga la información y el área competente la valida.
- **Ocupación real:** la disponibilidad de camas se calcula a partir de los movimientos, no de una carga manual.

---

## 2. A quién está dirigido

| Actor | Qué hace |
|---|---|
| **Operador del dispositivo** | Carga y actualiza personas, admisiones, egresos y datos operativos de su dispositivo. |
| **Responsable institucional** | Controla la carga de su dispositivo y confirma los cierres. |
| **Supervisor del área** | Valida altas, cambios sensibles, observaciones y correcciones. |
| **Administrador central** | Administra catálogos, perfiles y permisos, y resuelve duplicados. |
| **Equipo territorial** | Releva y propone correcciones de los datos de las instituciones. |
| **Consulta / auditoría** | Accede a reportes y trazabilidad, sin modificar datos. |

---

## 3. Cómo funciona

### 3.1 Legajo del dispositivo

```
Alta del dispositivo → Validación del área → Configuración de camas
   → Admisión de personas → Estadía → Egreso / Traslado
   → Disponibilidad y métricas siempre actualizadas
```

1. **Alta.** Se da de alta el dispositivo buscando primero si ya existe (para no duplicarlo). Se completan su identidad, domicilio y geolocalización, responsable, **tipo**, capacidad de camas, horarios y contacto.
2. **Validación.** El área compara con la fuente oficial y **valida, observa o rechaza**. Validado, el dispositivo queda **activo** y habilitado para recibir personas.
3. **Configuración de camas.** Se cargan las **camas totales** del dispositivo.
4. **Admisión.** Al ingresar una persona, se la **busca por DNI** en el legajo ciudadano (si existe se vincula, si no se crea), se le **asigna una cama**, se registra la fecha de ingreso y se completa la **información específica según el tipo** de dispositivo.
5. **Egreso o traslado.** El egreso registra fecha, motivo y destino, y **libera la cama**. El traslado cierra la estadía y abre una nueva vinculada a la misma persona.
6. **Disponibilidad automática.** En todo momento el sistema muestra **camas libres, camas ocupadas** y **métricas de ingreso, egreso y ocupación**, calculadas solas.

Mientras una persona esté alojada, en su **legajo ciudadano** aparece la **solapa del Programa Dispositivos** con su estado. Si la persona vuelve a ingresar más adelante, el sistema registra la **nueva estadía vinculada al mismo legajo**, conservando el historial completo.

### 3.2 Tipos de dispositivo

Cada tipo define qué información específica se carga de la persona al admitirla:

| Tipo | Camas | Información específica |
|---|---|---|
| **Adulto Mayor** | Sí | Datos personales, situación laboral y económica, permanencia/nutrición y vivienda, red de sostén, datos de la familia, salud, egresos mensuales, intereses y actividades, grado de dependencia. |
| **Abordaje Psicosocial** | Sí | Datos personales, reingreso, situación personal/educativa/laboral, oficio, grupo y dinámica familiar, vivienda, ingresos y egresos, red de sostén, salud, **comidas**, consumos, situaciones de crisis, necesidades básicas, grado de dependencia. |
| **UPI** (Centro de Protección Integral) | Sí | Se configura según el relevamiento del área. |
| **ECA** (resguardo de niñas, niños y adolescentes) | Sí | Se configura según el relevamiento del área. |
| **Residencias Universitarias** | Sí | Se configura según el relevamiento del área. |
| **Fortalecimiento Familiar** | A confirmar | Se configura según el relevamiento del área. |

!!! tip "Formularios configurables"
    La información que se pide en cada tipo de dispositivo es **configurable** desde el sistema: a medida que el Ministerio releve los formularios de cada área, se cargan como configuración, **sin cambiar el programa**. El Ministerio confirmó que los formularios solo se amplían (no se elimina información ya definida).

### 3.3 Programa Merenderos

El Ministerio definió que Merenderos es un **programa propio**, hermano del Programa Dispositivos: la entrega de mercaderías a merenderos abiertos por vecinos y vecinas, que presentan previamente la **documentación respaldatoria** correspondiente.

```
Solicitud del vecino/a (con documentación) → Validación del área
   → Legajo del merendero → Entrega de mercaderías → Prestación alimentaria
```

1. **Alta.** Quien abre el merendero presenta su solicitud con datos institucionales, responsable, domicilio, **zona y barrio**, días y horarios, junto con la documentación respaldatoria.
2. **Validación.** El área controla y aprueba; la aprobación crea el legajo del merendero.
3. **Entrega de mercaderías.** Se registra la cantidad de **kits de mercadería**, la fecha de entrega y el servicio.
4. **Prestación.** Se registran los servicios brindados: **desayuno/colación, almuerzo, merienda/colación, cena** y observaciones.

### 3.4 Los formularios del programa

El programa trabaja con tres formularios. Una idea ordena a los tres: **el operador carga solo lo que el sistema no puede saber por sí mismo**. Los datos de identidad (nombre, DNI, fecha de nacimiento, edad), el responsable, las fechas y los cálculos los **completa el sistema** automáticamente; el operador se concentra en la información propia de cada caso.

=== "F-00 · Admisión de la persona"

    Es el formulario que se completa **al admitir a una persona**, y cambia según el **tipo de dispositivo**. Recupera la identidad de la persona desde su legajo ciudadano (y RENAPER) para no volver a pedirla, y agrupa la información en bloques.

    | Tipo | Bloques de información |
    |---|---|
    | **Adulto Mayor** | Datos personales · Situación laboral y económica · Permanencia, nutrición y vivienda · Red de sostén · Datos de la familia · Salud · Egresos mensuales · Intereses y actividades · Grado de dependencia. |
    | **Abordaje Psicosocial** | Datos personales · Reingreso · Situación personal, educativa y laboral · Grupo familiar · Dinámica familiar · Vivienda · Ingresos y egresos · Red de sostén · Salud · Grado de dependencia · **Comidas** · Consumos · Situaciones de crisis · Necesidades básicas · Cierre del relevamiento. |

    Cuando una persona ya tuvo una estadía anterior, el sistema **detecta el reingreso** solo, sin marcarlo a mano. Los totales económicos (egresos mensuales, saldo) se **calculan** a partir de los conceptos cargados.

    El bloque **Comidas** (incorporado a pedido del Ministerio) registra el régimen alimentario de la persona: normal, dieta blanda, baja en sodio, baja en azúcar, vegetariana/vegana o sin gluten.

=== "F-01 · Registro diario de novedades por turno"

    Es el **parte diario** de cada dispositivo, por **turno** (mañana, tarde, noche). El operador elige el turno y escribe las **observaciones del turno**; el resto lo arma el sistema: camas totales, ingresos y egresos del día, ocupación nocturna y camas disponibles, todo **calculado** a partir de los movimientos registrados.

=== "F-02 · Prestación alimentaria mensual (merenderos)"

    Es la **planilla mensual** del merendero: una fila por día del mes y una columna por servicio (desayuno/colación, almuerzo, merienda/colación, cena). El operador carga la **cantidad de raciones** servidas por día; el sistema calcula el **total diario** y completa mes, año y firma.

!!! tip "Menos carga manual, menos errores"
    Al reutilizar el legajo ciudadano y calcular solo los totales y la ocupación, los formularios piden únicamente lo imprescindible. Eso acelera la carga y evita inconsistencias entre lo declarado y lo que muestra el sistema.

---

## 4. Estados

=== "Dispositivo"

    `Borrador` → `Pendiente de validación` → `Activo` / `Observado` / `Rechazado` → `Inactivo` / `Cerrado`

=== "Admisión de persona"

    `Solicitado` → `En revisión` → `Lista de espera` / `Aprobado` / `Rechazado` → `Alojado` → `Egresado` / `Trasladado`

=== "Cama"

    `Disponible` → `Reservada` → `Ocupada` → `Fuera de servicio`

=== "Merendero"

    Solicitud: `Borrador` → `En revisión` → `Observada` / `Aprobada` / `Rechazada` · Merendero: `Activo` → `Suspendido` / `Cerrado`

---

## 5. Indicadores

El módulo ofrece indicadores con semáforo para la gestión:

| Indicador | Semáforo |
|---|---|
| **Ocupación de camas** | Verde < 50% · Amarillo 50–79% · Rojo ≥ 80% (configurable por tipo). |
| **Disponibilidad** | Verde con disponibilidad · Amarillo limitada · Rojo sin disponibilidad. |
| **Actualización de datos** | Verde ≤ 15 días · Amarillo 16–30 · Rojo > 30 días desde la última carga. |
| **Completitud** | Según campos obligatorios completos sobre los esperados. |
| **Cobertura alimentaria** | Alerta cuando la demanda supera la capacidad o la entrega. |

---

## 6. Alcance de esta etapa

!!! success "Incluye"
    - Legajo institucional del dispositivo (alta, validación, mantenimiento).
    - Tipos de dispositivo con su información específica configurable.
    - Admisión, estadía, egreso y traslado de personas vinculadas al legajo ciudadano.
    - Gestión de camas con disponibilidad y métricas automáticas.
    - **Programa Merenderos**: legajo institucional, entrega de mercaderías y prestación alimentaria.
    - Indicadores básicos de ocupación, disponibilidad y actualización.

!!! warning "Para etapas posteriores"
    - Línea 102, denuncias y derivaciones de casos sensibles.
    - Gestión de personal y dotación por dispositivo.
    - Rendiciones de fondos y recursos.
    - Relevamiento de infraestructura y preparación tecnológica.
    - Cierre mensual formal y tablero de comando completo.

---

## 7. Temas a confirmar

- Detalle de los formularios de **UPI, ECA, Residencias Universitarias y Fortalecimiento Familiar**: en etapa de relevamiento con las áreas del Ministerio; se cargan como configuración a medida que se definan.
- Si el tipo **Fortalecimiento Familiar** trabaja con camas o con cupos/plazas.
- Encuadre de los **albergues y operativos de contención nocturna** (¿tipo de dispositivo propio o variante de Abordaje Psicosocial?).
- Alcance del padrón nominal de niños y tutores, y de la asistencia alimentaria diaria de los merenderos.
- Criterio de carga de la prestación de los merenderos (cantidad de raciones o marca por servicio).
