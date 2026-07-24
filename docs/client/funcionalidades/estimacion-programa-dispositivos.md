# Estimación de esfuerzo — Programa Dispositivos y Programa Merenderos
## Legajo institucional, admisiones, camas y asistencia alimentaria

**Fecha:** 2026-07-02
**Versión:** 1.0
**Alcance cubierto:** definición aprobada por el Ministerio el 01/07/2026 (legajo del dispositivo, admisiones y camas, registro diario, legajo de merenderos con entrega de mercaderías y prestación mensual)
**Estado:** Aprobada por el Ministerio (24/07/2026)

> **Base de la estimación:** la definición funcional publicada en [Programa Dispositivos](programa-dispositivos.md), con la conformidad del Ministerio del 01/07/2026. A diferencia del Programa Becas, esta etapa es **100% backoffice** (no incluye app móvil), y reutiliza componentes ya construidos: motor de roles, validación RENAPER, formularios configurables y solapas del legajo ciudadano — eso reduce el esfuerzo respecto de construirlos de cero.

---

## 1. Resumen ejecutivo

| Concepto | Horas |
|---|---:|
| Desarrollo Backend | 154 |
| Desarrollo Frontend | 103 |
| Diseño UX/UI | 60 |
| Pruebas funcionales y QA | 80 |
| Despliegue a ambiente QA | 25 |
| Capacitación | 14 |
| **Total** | **436** |

> Las horas corresponden a esfuerzo técnico neto. No incluyen reuniones de seguimiento ni gestión de proyecto. Los formularios de los tipos aún en relevamiento (UPI, ECA, Residencias Universitarias, Fortalecimiento Familiar) **no requieren desarrollo adicional**: se cargan como configuración cuando el Ministerio los entregue (ver §7).

---

## 2. Desarrollo

### 2.1 Detalle por módulo

| Ref | Módulo | Descripción | Horas | Perfil |
|---|---|---|---:|---|
| D-01 | Modelo de datos | Modelos del dominio: Dispositivo institucional, Tipo de dispositivo, Cama, Admisión/Estadía, campos configurables del formulario de admisión, Registro diario, Merendero, Entrega de mercaderías y Prestación mensual. Vínculo con el legajo ciudadano y membresía al programa (habilita la solapa). Migraciones y admin básico. | 24 | Backend |
| D-02 | Configuración del programa | ABM del catálogo de **tipos de dispositivo** y de los **campos del formulario de admisión por tipo** (secciones + tipos de campo: texto / número / selector / selector múltiple / fecha / archivo). Carga de la configuración inicial de **Adulto Mayor** (31 campos) y **Abordaje Psicosocial** (45 campos) según los formularios relevados. Catálogo de servicios del merendero. | 34 | Backend + Frontend |
| D-03 | Legajo del dispositivo | ABM con búsqueda anti-duplicado, alta en borrador, circuito de validación del área (validar / observar / rechazar), estados del dispositivo, domicilio con geolocalización, responsable y contacto. Pantalla de detalle con información base y configuración de camas. | 26 | Backend + Frontend |
| D-04 | Gestión de camas | Estado por cama (disponible / reservada / ocupada / fuera de servicio), regla "una cama, una persona", **ocupación y disponibilidad calculadas** a partir de las estadías (nunca carga manual), semáforo de ocupación configurable por tipo. | 16 | Backend + Frontend |
| D-05 | Admisiones, estadía y egreso | Búsqueda de la persona por DNI en el legajo ciudadano (con pre-completado de identidad vía RENAPER), asignación de cama, **formulario de admisión dinámico según el tipo** (secciones, campos configurables, totales calculados), **detección automática de reingreso**, estados de la admisión, lista de espera, egreso con liberación de cama y traslado con nueva estadía vinculada al mismo legajo. | 40 | Backend + Frontend |
| D-06 | Registro diario de novedades (F-01) | Parte diario por turno (mañana / tarde / noche): el operador elige turno y escribe observaciones; camas totales, ingresos, egresos, ocupación nocturna y disponibles se calculan solos. | 11 | Backend + Frontend |
| D-07 | Solapa Dispositivos en legajo | Pestaña dinámica en el legajo del ciudadano mientras tiene una admisión activa: estado de la estadía, dispositivo y acceso al detalle. | 10 | Backend + Frontend |
| D-08 | Roles y autorización | Roles Operador de dispositivo, Responsable institucional, Supervisor de área, Administrador central y Consulta/auditoría, integrados al motor de roles existente, con alcance por dispositivo/área. | 14 | Backend |
| D-09 | Legajo de merenderos | ABM institucional del **Programa Merenderos**: solicitud del vecino/a con **documentación respaldatoria** (adjuntos), circuito de validación del área, estados del merendero y registro de **entregas de mercaderías** (kits, fecha, servicio). | 24 | Backend + Frontend |
| D-10 | Prestación alimentaria mensual (F-02) | Planilla mensual del merendero: una fila por día y una columna por servicio, carga de raciones, total diario calculado, firma automática por fila. | 13 | Backend + Frontend |
| D-11 | Indicadores | Semáforos de ocupación, disponibilidad, actualización de datos y completitud; panel básico del programa. | 16 | Backend + Frontend |
| D-12 | Reportes | Exportación CSV/Excel: padrón de dispositivos, ocupación, admisiones/egresos por período y padrón de merenderos con entregas. | 13 | Backend + Frontend |
| D-13 | Carga inicial de dispositivos | Importador del padrón existente desde planilla normalizada provista por el Ministerio, conservando fuente y fecha del dato, con validación anti-duplicados previa al alta masiva. | 16 | Backend |
| | **Subtotal desarrollo** | | **257** | |

### 2.2 Distribución por perfil

| Perfil | Módulos | Horas |
|---|---|---:|
| Desarrollador Backend | D-01, D-08, D-13 + parte de D-02 a D-12 | 154 |
| Desarrollador Frontend | Parte de D-02 a D-12 (pantallas sobre el design system existente) | 103 |
| **Total** | | **257** |

---

## 3. Diseño UX/UI

| Concepto | Horas |
|---|---:|
| Flujos y wireframes de las 8 pantallas del programa (dispositivos, detalle, admisión/egreso, camas, merenderos, configuración, indicadores, reportes) | 24 |
| Diseño del formulario de admisión dinámico (secciones largas, estados de error, pre-completado) | 14 |
| Diseño de camas, semáforos e indicadores (estados visuales) | 10 |
| Ajustes sobre componentes del design system y revisión con el equipo | 12 |
| **Subtotal diseño** | **60** |

> El design system del proyecto ya está construido y aplicado (tokens, componentes, patrones de pantalla); el diseño de esta etapa compone sobre esa base en lugar de crear lenguaje visual nuevo.

---

## 4. Pruebas funcionales y QA

| Concepto | Horas |
|---|---:|
| Escritura de casos de prueba documentados (módulos D-01 a D-13) | 20 |
| Ejecución de pruebas por módulo | 28 |
| Pruebas de flujo end-to-end (alta del dispositivo → validación → admisión → estadía → egreso → censo) y del circuito completo de merenderos (solicitud → validación → entrega → prestación) | 16 |
| Verificación de cálculos: ocupación, disponibilidad, reingresos, totales del formulario y del registro diario | 8 |
| Registro de defectos, re-test y cierre | 8 |
| **Subtotal QA** | **80** |

### Escenarios críticos cubiertos

- Flujo completo del dispositivo: alta anti-duplicado → validación del área → configuración de camas → admisión con formulario por tipo → egreso con liberación de cama.
- Reingreso: persona con estadía anterior cerrada → el sistema lo detecta solo y vincula la nueva estadía al mismo legajo.
- Regla de camas: intento de asignar una cama ocupada; cama fuera de servicio no cuenta como disponible.
- Sin cupo: admisión validada sin cama disponible → lista de espera → promoción manual.
- Traslado: cierre de estadía en el dispositivo A y apertura en el B conservando historial.
- Autorización: operador del dispositivo A intentando operar el dispositivo B; rol de consulta intentando modificar.
- Pre-completado: datos de identidad y obra social desde el legajo ciudadano / RENAPER, sin re-preguntar.
- Merenderos: solicitud sin documentación respaldatoria → observada; prestación mensual con totales diarios calculados.

---

## 5. Despliegue a ambiente QA

| Concepto | Horas |
|---|---:|
| Configuración del ambiente (Docker, variables de entorno, base de datos) | 8 |
| Despliegue del código y ejecución de migraciones | 5 |
| Carga de datos iniciales (tipos de dispositivo, configuración de los formularios de Adulto Mayor y Abordaje Psicosocial, roles y usuarios de prueba, merenderos de ejemplo) | 8 |
| Verificación post-despliegue y smoke tests | 4 |
| **Subtotal despliegue** | **25** |

---

## 6. Capacitación

| Sesión | Destinatarios | Horas |
|---|---|---:|
| Elaboración de materiales (guía de usuario por rol) | — | 4 |
| Administradores: configuración de tipos y formularios, validación de altas, indicadores y reportes | Equipo ministerio | 5 |
| Operadores de dispositivos: admisiones, egresos, camas y registro diario | Operadores / responsables | 3 |
| Área de merenderos: legajo, entregas de mercaderías y prestación mensual | Equipo del área | 2 |
| **Subtotal capacitación** | | **14** |

---

## 7. Fuera del alcance de esta estimación

| Ítem | Motivo |
|---|---|
| Formularios de UPI, ECA, Residencias Universitarias y Fortalecimiento Familiar | En relevamiento por el Ministerio; **se cargan como configuración sin desarrollo adicional** cuando estén definidos (el mecanismo configurable está incluido en D-02) |
| Línea 102, denuncias y derivaciones de casos sensibles | Etapa posterior acordada con el Ministerio |
| Gestión de personal y dotación por dispositivo | Etapa posterior |
| Rendiciones de fondos y recursos (más allá del registro de kits) | Etapa posterior |
| Relevamiento de infraestructura y preparación tecnológica | Etapa posterior |
| Cierre mensual formal y tablero de comando completo | Etapa posterior (los indicadores básicos sí están incluidos en D-11) |
| Padrón nominal de niños y tutores y asistencia alimentaria diaria de merenderos | Alcance a confirmar con el Ministerio; se estimará por separado si se incorpora |
| App móvil | Esta etapa es de backoffice; no se requiere aplicación de campo |

---

## 8. Supuestos y condiciones

1. El motor de roles (RBAC) y el design system del proyecto están operativos; los módulos los reutilizan sin modificaciones estructurales.
2. La validación RENAPER reusa el servicio existente sin cambios en su contrato.
3. El padrón inicial de dispositivos y merenderos es provisto por el Ministerio en planilla normalizada (una fila por institución, columnas acordadas) antes de la carga inicial (D-13).
4. Los formularios de Adulto Mayor y Abordaje Psicosocial se cargan según los documentos relevados y aprobados el 01/07/2026; ampliaciones posteriores se incorporan por configuración.
5. La prestación de merenderos se carga como **cantidad de raciones** (numérica); si el Ministerio define el criterio "marca por servicio (S/N)", el ajuste es de configuración menor y no altera esta estimación.
6. El ambiente de QA cuenta con Docker Compose operativo y acceso a la base de datos.
7. La capacitación se realiza presencial o por videoconferencia con grupos de hasta 10 personas por sesión; sesiones adicionales se cotizan por separado.

---

## 9. Cronograma

**Inicio:** a definir con el Ministerio (sujeto a aprobación de esta estimación)
**Equipo:** 1 Backend, 1 Frontend, 1 Diseñador, 1 QA
**Supuesto:** 8 horas/día por persona

**Duración estimada:** ~6 semanas (30 días hábiles)

### Notas del cronograma

- El diseño arranca en paralelo con el modelo de datos y entrega primero las pantallas del legajo del dispositivo.
- El backend avanza por dependencias: modelo → configuración → dispositivos/camas → admisiones → merenderos.
- El frontend arranca cuando D-02/D-03 tienen endpoints listos.
- QA escribe casos desde el inicio y ejecuta a medida que cada módulo se completa.
- La carga inicial (D-13) requiere la planilla del Ministerio; puede correr en paralelo al final del desarrollo.
- La capacitación se realiza sobre el ambiente de QA desplegado.

---

## 10. Resumen por fase

```
Desarrollo Backend ·········· 154 h  ████████████████████████████░░░░░░░░
Desarrollo Frontend ········· 103 h  ███████████████████░░░░░░░░░░░░░░░░░
Diseño UX/UI ················  60 h  ███████████░░░░░░░░░░░░░░░░░░░░░░░░░
Pruebas y QA ················  80 h  ███████████████░░░░░░░░░░░░░░░░░░░░░
Despliegue a QA ·············  25 h  █████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
Capacitación ················  14 h  ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

Total                        436 h
```

| | Horas | % |
|---|---:|---:|
| Desarrollo Backend | 154 | 35 % |
| Desarrollo Frontend | 103 | 24 % |
| Diseño UX/UI | 60 | 14 % |
| Pruebas y QA | 80 | 18 % |
| Despliegue | 25 | 6 % |
| Capacitación | 14 | 3 % |
| **Total** | **436** | **100 %** |
