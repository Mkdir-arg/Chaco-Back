# Programa Dispositivos — Legajo institucional, admisiones, camas y merenderos

!!! abstract "En una línea"
    Gestionar en el sistema cada **dispositivo** (hogares, residencias y espacios de atención) y cada **merendero**: su legajo institucional, las personas que ingresan y egresan, la disponibilidad de camas en tiempo real y la asistencia alimentaria.

| | |
|---|---|
| **Módulo** | Programas |
| **Estado** | Definición aprobada por el Ministerio — lista para desarrollo |
| **Programas** | Dispositivos y Merenderos (sobre la base de Programas, después de Becas) |
| **Última actualización** | 2026-07-03 |

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

=== "F-00 · Adultos Mayores"

    Formulario de admisión del tipo **Adulto Mayor** (Sistema Integral Gerontológico), construido a partir del formulario en papel relevado con el área. **De los ~50 datos del papel, el operador carga 32 y el sistema completa 17 automáticamente.**

    | Sección | Campos | ¿Quién lo completa? |
    |---|---|---|
    | Encabezado | Institución/sede · Fecha y hora · Reingreso · Responsable | **El sistema** (contexto, reloj, detección de estadía anterior, usuario) |
    | A. Datos personales | Nombre y apellido · DNI/CUIL · Edad · Fecha de nacimiento · Género | **El sistema** (legajo ciudadano / RENAPER) |
    | A. Datos personales | Obra social | **El sistema** (desde el legajo ciudadano; editable) |
    | A. Datos personales | Nivel de instrucción · Oficio · Capacitaciones · Interés en formación | El operador (con pre-completado desde el legajo cuando existe) |
    | B. Situación laboral y económica | Empleo (formal/informal/sin empleo) · Lugar de trabajo · Ocupación · Ingreso mensual · Plan social/beca · Jubilación/pensión | El operador |
    | C. Permanencia, nutrición y vivienda | Perfil de permanencia (larga/mediana estadía/tránsito) · Requerimiento nutricional · Relación familiar · Último domicilio · Motivo de egreso del hogar · Posee vivienda · Dónde duerme actualmente · Observaciones | El operador |
    | D. Red de sostén | Tipos de red (parientes/institucional/vecinos/ONG/iglesia/CC/gubernamental) · Detalle | El operador |
    | E. Datos de la familia | Tabla familiar (nombre, parentesco, edad, nivel, ingreso, teléfono) | El operador |
    | F. Salud | Grupo sanguíneo · Tratamiento médico · Antecedentes de salud · Observaciones | El operador |
    | G. Egresos mensuales | Alquiler · Créditos · Cuotas · Medicamentos · Transporte/otros | El operador |
    | G. Egresos mensuales | **Total de egresos** | **El sistema** (calculado) |
    | H. Egreso del dispositivo | Fecha · Motivo · Destino · Derivación | **El sistema** — en papel está en el mismo formulario; en el sistema es la **acción de egreso**, al momento del retiro |
    | I. Intereses y actividades | Intereses | El operador |
    | J. Dependencia y cierre | Grado de dependencia (autoválido/semi-válido/postrado) | El operador |
    | J. Dependencia y cierre | Fecha de revisión · Firma y aclaración · DNI/cargo | **El sistema** (reloj + usuario que carga) |

=== "F-00 · Abordaje Psicosocial"

    Formulario de admisión del tipo **Abordaje Psicosocial** (Dirección de Inclusión y Abordaje Integral), en su **versión ampliada por el Ministerio** (bloques Comidas y Cierre del relevamiento). **El operador carga 45 datos y el sistema completa 20.**

    | Sección | Campos | ¿Quién lo completa? |
    |---|---|---|
    | Encabezado | Institución/sede · Fecha · Tipo de ingreso (1ª vez / reingreso) · Responsable | **El sistema** (el reingreso se detecta solo, no es un casillero manual) |
    | 1. Datos personales | Fecha de ingreso · DNI/CUIL · Nombre y apellido · Edad · Lugar y fecha de nacimiento · Teléfono | **El sistema** (legajo ciudadano / RENAPER) |
    | 2. Reingreso | Fecha de reingreso | **El sistema** |
    | 2. Reingreso | Observaciones del reingreso | El operador |
    | 3. Situación personal, educativa y laboral | Nivel educativo · Capacitaciones · Interés en formación · Ocupación · Lugar de trabajo · Ingreso mensual · Empleo · Oficio/saber laboral · Ayuda económica externa · Plan social/beca · Jubilación/pensión | El operador (nivel educativo y ocupación con pre-completado del legajo) |
    | 4. Grupo familiar | Tabla del grupo (nombre, parentesco, edad, educación, ocupación, ingreso) | El operador |
    | 5. Dinámica familiar | Relación con la familia · Último domicilio · Motivo de egreso del hogar anterior · Derivación/referencia · Historia familiar | El operador |
    | 6. Vivienda | Posee vivienda · Condición (propia/alquilada/prestada) · Localidad/barrio · Observaciones | El operador |
    | 7. Ingresos y egresos | Ingreso total mensual · Ayuda alimentaria · Alquiler/medicamentos/transporte/créditos/otros | El operador |
    | 7. Ingresos y egresos | **Total de egresos** · **Saldo estimado** | **El sistema** (calculados) |
    | 8. Red de sostén | Tipos de red · Detalle/referentes | El operador |
    | 9. Salud | Cobertura de salud · N° de afiliado · Tabla problema/enfermedad/tratamiento/medicación · Problemas de salud declarados | El operador |
    | 10. Grado de dependencia | Condición funcional (autoválido/semi-válido/postrado) | El operador |
    | 11. **Comidas** *(nuevo)* | Régimen alimentario: normal · dieta blanda · baja en sodio · baja en azúcar · vegetariana/vegana · sin gluten | El operador |
    | 12. Consumos | Consume sustancias · Cuáles · Tratamiento (ambulatorio/internación) · Derivación | El operador |
    | 13. Situaciones de crisis | Situaciones registradas (violencia/adicciones/abandono/migración/enfermedad grave/muerte familiar) · Descripción | El operador |
    | 14. Necesidades básicas | Necesidades observadas (hacinamiento/vivienda precaria/falta de agua/niños sin escuela/salud) | El operador |
    | Cierre del relevamiento *(nuevo)* | Fecha de egreso · Motivo · Lugar de egreso | **El sistema** — es la **acción de egreso** del dispositivo, no parte de la admisión |
    | Cierre | Responsable del relevamiento · Firma · Fecha de carga · Estado (completo/pendiente) | **El sistema** |

=== "F-01 · Registro diario por turno"

    El **parte diario** de cada dispositivo. En papel el responsable de turno anota a mano las cantidades; en el sistema **todas se calculan solas** a partir de los movimientos registrados — el operador solo aporta dos datos.

    | Campo | ¿Quién lo completa? |
    |---|---|
    | Institución/sede · Fecha · Responsable del turno | **El sistema** |
    | **Turno** (mañana / tarde / noche) | El operador |
    | A. Camas totales | **El sistema** (de la configuración del dispositivo) |
    | B. Ingresos del día | **El sistema** (admisiones registradas hoy) |
    | C. Egresos del día | **El sistema** (egresos registrados hoy) |
    | D. Ocupación nocturna | **El sistema** (estadías activas al cierre del día) |
    | E. Camas disponibles | **El sistema** (totales − ocupadas − fuera de servicio) |
    | **Observaciones generales del turno** | El operador |
    | Firma y aclaración | **El sistema** (usuario que carga) |

=== "F-02 · Prestación mensual (merenderos)"

    La **planilla mensual** del merendero: una fila por cada día del mes y una columna por servicio alimentario.

    | Campo | ¿Quién lo completa? |
    |---|---|
    | Institución/sede · Mes · Año | **El sistema** |
    | Servicios del merendero (desayuno / almuerzo / merienda / cena) | A confirmar con el Ministerio (¿configuración del legajo o selección por mes?) |
    | Filas por día (1 al 31) | **El sistema** (genera la grilla del mes) |
    | Raciones por día y servicio | El operador |
    | **Total por día** | **El sistema** (calculado) |
    | Observaciones por día | El operador (opcional) |
    | Firma por fila | **El sistema** (usuario que carga) |

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

---

## Documentos relacionados

- [Estimación de horas — Programa Dispositivos y Merenderos](estimacion-programa-dispositivos.md)
