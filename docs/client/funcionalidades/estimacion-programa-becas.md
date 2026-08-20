# Estimación de esfuerzo — Programa Becas
## Relevamiento territorial y asignación de cupos

**Fecha:** 2026-06-17
**Versión:** 1.2
**Alcance cubierto:** Análisis A — funcionalidades sin dependencia de integración SIS

> **Nota de consumo (cierre de junio 2026):** en junio se consumieron 499 horas del sprint en análisis funcional (Becas, legajos, programa Dispositivos), desarrollo del motor RBAC y del backend de Becas, Design System, app de campo y mockups del equipo UX, cerrando el mes dentro del presupuesto de 500 horas (100%). Las 654 horas estimadas en este documento corresponden a trabajo comprometido que se ejecuta en los meses siguientes.

---

## 1. Resumen ejecutivo

| Concepto | Horas |
|---|---:|
| Desarrollo Backend | 168 |
| Desarrollo Frontend | 52 |
| Desarrollo App (React Native) | 158 |
| Diseño UX/UI | 126 |
| Pruebas funcionales y QA | 105 |
| Despliegue a ambiente QA | 30 |
| Capacitación | 15 |
| **Total** | **654** |

> Las horas corresponden a esfuerzo técnico neto. No incluyen reuniones de seguimiento, gestión de proyecto ni la integración con el Sistema SIS (Análisis B, pendiente de contrato técnico — ver §6).

---

## 2. Desarrollo

### 2.1 Detalle por módulo

| Ref | Módulo | Descripción | Horas | Perfil |
|---|---|---|---:|---|
| T-01 | Modelo de datos | Modelos del dominio Becas: Segmento, Subsegmento, Convocatoria, Relevamiento, PreguntaGlobal, RequisitoNativo, AsignacionCoordinador, Formulario, TracaFormulario, ListaEspera. Migraciones y admin básico. | 21 | Backend |
| T-02 | Configuración del programa | ABM de segmentos, subsegmentos con validación de cupo, asignación de coordinadores por segmento, ABM de requisitos nativos con tipo de campo (texto / número / selector / fecha / archivo) y ABM del cuestionario social (13 preguntas globales con toggle activo). | 32 | Backend + Frontend |
| T-03 | Convocatorias | ABM de convocatorias con selección dinámica de segmento y subsegmento (Alpine.js). Visualización de requisitos configurados. | 13 | Backend + Frontend |
| T-04 | Relevamientos | ABM de relevamientos, asignación y reasignación de territorial, reprogramación por Coordinador. | 16 | Backend + Frontend |
| T-05 | Revisión de formularios | Pantalla de revisión caso a caso: aprobación, rechazo con motivo, edición de datos con trazabilidad completa (quién / cuándo / valor anterior). | 21 | Backend + Frontend |
| T-06 | Gestión de cupo | Vista de cupo por segmento, lista de beneficiarios activos, lista de espera, baja manual y promoción manual. | 19 | Backend + Frontend |
| T-07 | Roles y autorización | Creación de roles Admin, Territorial y Coordinador integrados al motor RBAC existente. Control de acceso por segmento asignado para el rol Coordinador. | 13 | Backend |
| T-08 | Solapa Becas en legajo | Pestaña dinámica "Becas" en el legajo del ciudadano: estado, datos del formulario, vínculo con la pantalla de revisión. | 16 | Backend + Frontend |
| T-09 | Reportes | Exportación CSV/Excel de beneficiarios activos, lista de espera y avance de relevamientos, con filtros por segmento y convocatoria. | 13 | Backend + Frontend |
| T-10 | API para app de campo | Endpoints REST para la app territorial: autenticación, listado de relevamientos con definición dinámica del formulario (tipos de campo y opciones), carga de formularios, sincronización offline y finalización en lote. | 29 | Backend |
| T-11 | Validación RENAPER | Integración de los 3 caminos de validación de identidad (escaneo de DNI / RENAPER online / carga manual). Revalidación diferida desde el backoffice. | 19 | Backend |
| T-12 | App de campo (React Native) | App Expo/React Native para el agente territorial: autenticación JWT con persistencia de sesión, listado de relevamientos asignados, motor de formulario dinámico (6 tipos de campo: STRING / INT / SELECTOR / SELECTOR_MULTIPLE / DATE / ARCHIVO), captura GPS automática, escaneo y validación de DNI (3 caminos RENAPER), carga de adjuntos con cámara, almacenamiento offline con sync automático al reconectar, finalización de relevamiento. EAS Build para Android e iOS. | 158 | App React Native |
| | **Subtotal desarrollo** | | **378** | |

### 2.2 Detalle de la app de campo (T-12)

| Componente | Horas |
|---|---:|
| Setup: proyecto Expo, navegación, estado global, auth JWT | 21 |
| Pantalla de relevamientos (lista, detalle, badges de estado) | 16 |
| Motor de formulario dinámico (6 tipos de campo, bloques fijos, GPS) | 37 |
| Escaneo de DNI y flujo de validación RENAPER (3 caminos) | 21 |
| Carga y almacenamiento de adjuntos (cámara + archivos) | 16 |
| Sincronización offline (cola local, retry, indicador de estado) | 26 |
| Envío, actualización y finalización de relevamiento | 11 |
| EAS Build, signing, configuración de entornos y distribución de prueba | 10 |
| **Total T-12** | **158** |

### 2.3 Distribución por perfil

| Perfil | Módulos | Horas |
|---|---|---:|
| Desarrollador Backend | T-01, T-07, T-10, T-11 + parte de T-02 a T-09 | 168 |
| Desarrollador Frontend | Parte de T-02 a T-09 | 52 |
| Desarrollador React Native | T-12 | 158 |
| **Total** | | **378** |

---

## 3. Pruebas funcionales y QA

### 3.1 Alcance — backoffice

| Concepto | Horas |
|---|---:|
| Escritura de casos de prueba documentados (módulos T-01 a T-11) | 19 |
| Ejecución de pruebas por módulo | 25 |
| Pruebas de flujo end-to-end (relevamiento completo: desde configuración hasta cupo asignado) | 15 |
| Pruebas de la API (Postman o herramienta equivalente) | 8 |
| Registro de defectos, re-test y cierre | 6 |
| **Subtotal QA backoffice** | **73** |

### 3.2 Alcance — app de campo (React Native)

| Concepto | Horas |
|---|---:|
| Escritura de casos de prueba (formulario dinámico, offline, RENAPER) | 8 |
| Ejecución en dispositivo Android (flujo completo) | 11 |
| Pruebas de escenarios offline: guardar borrador → reconectar → sync | 7 |
| Pruebas de los 3 caminos de validación RENAPER desde el dispositivo | 4 |
| Registro de defectos, re-test y cierre | 2 |
| **Subtotal QA app** | **32** |

| **Total QA** | **105** |
|---|---:|

### 3.3 Escenarios críticos cubiertos

- Flujo completo: segmento con subsegmentos → convocatoria → relevamiento → formulario → aprobación → cupo asignado.
- Validación de cupo: subsegmento cuyo cupo suma más que el del segmento.
- Autorización: Coordinador sin asignación, Coordinador de segmento A intentando acceder a segmento B.
- RENAPER: los 3 caminos (escaneo, RENAPER online, manual offline) desde backoffice y desde la app.
- Formulario dinámico: los 6 tipos de campo (STRING, INT, SELECTOR, SELECTOR_MULTIPLE, DATE, ARCHIVO) en la app de campo.
- Offline: formulario guardado sin conexión → sincronización correcta al reconectar.
- Lista de espera: baja de beneficiario → liberación de cupo → alerta → promoción manual.

---

## 4. Despliegue a ambiente QA

| Concepto | Horas |
|---|---:|
| Configuración del ambiente (Docker, variables de entorno, base de datos) | 8 |
| Despliegue del código y ejecución de migraciones | 5 |
| Carga de datos iniciales de prueba (segmentos, preguntas del cuestionario social, usuarios y roles de prueba) | 6 |
| Verificación post-despliegue y smoke tests del backoffice | 5 |
| EAS Build del apk de prueba y distribución interna (Firebase App Distribution o similar) | 6 |
| **Subtotal despliegue** | **30** |

---

## 5. Capacitación

| Sesión | Destinatarios | Horas |
|---|---|---:|
| Elaboración de materiales (guía de usuario por rol, manual de la app) | — | 4 |
| Administradores del programa: configuración de segmentos, convocatorias, revisión de formularios, cupo y reportes | Equipo ministerio | 5 |
| Coordinadores: revisión de formularios y reprogramación de relevamientos | Coordinadores territoriales | 2 |
| Territoriales: instalación de la app y uso en campo (relevamientos y carga de formularios) | Agentes de campo | 4 |
| **Subtotal capacitación** | | **15** |

---

## 6. Fuera del alcance de esta estimación

| Ítem | Motivo |
|---|---|
| Integración con el Sistema SIS (validación de incompatibilidades y asignación definitiva de cupo) | Pendiente de contrato técnico de API con el equipo SIS/ICORE — corresponde a Análisis B |
| Sistema de Ayudas Sociales / liquidación (Nivel 3) | Pendiente de definición de alcance con el Ministerio |
| Notificaciones push a territoriales o ciudadanos | Diferido a una versión posterior |
| Módulo de seguimiento / permanencia por segmento | Diferido a Versión 2 por acuerdo con el Ministerio |
| Publicación en Google Play Store / App Store | La distribución de prueba (EAS) está incluida; la publicación pública es un paso posterior |

---

## 7. Supuestos y condiciones

1. El motor RBAC (épica #46, tasks #64–#68) está disponible antes del inicio del T-07. Si no estuviera listo, T-07 requiere estimación separada.
2. La integración con RENAPER reusa el servicio existente en `legajos/services/consulta_renaper.py` sin modificaciones al contrato.
3. El ambiente de QA cuenta con Docker Compose operativo, acceso a la base de datos MySQL y conectividad a la API de RENAPER (ambiente de pruebas).
4. Los datos del catálogo inicial (segmentos y preguntas del cuestionario social según el documento del Ministerio) son provistos por el cliente antes del despliegue.
5. La capacitación se realiza en modalidad presencial o videoconferencia con grupos de hasta 10 personas por sesión. Sesiones adicionales se cotizan por separado.
6. Los dispositivos Android de los territoriales son provistos por el Ministerio. La estimación no incluye gestión MDM ni configuración de dispositivos.

---

## 8. Cronograma — Gantt

**Inicio:** Lunes 23 de junio de 2026  
**Equipo:** 1 Backend, 1 Frontend, 1 React Native, 1 Diseñador, 1 QA  
**Supuesto:** 8 horas/día por persona

[:material-chart-gantt: Ver cronograma interactivo en ClickUp](https://sharing.clickup.com/90171120919/g/h/2kz9w78q-597/87b99d07c0b05ee){ .md-button target="_blank" }

**Duración estimada:** ~7 semanas (35 días hábiles)  
**Fecha tentativa de finalización:** 7 de agosto de 2026

### Notas del cronograma

- El diseño arranca en paralelo con desarrollo y cubre mockups, flujos y componentes.
- El backend avanza secuencialmente por dependencias (modelo → config → roles → API).
- La app React Native arranca en paralelo apenas el diseño entrega primeros assets.
- El frontend arranca cuando el backend tiene endpoints listos (T-02 en adelante).
- QA arranca cuando cada módulo está completo (backend/app).
- El despliegue a QA requiere que QA backoffice esté completo.
- La capacitación se realiza sobre el ambiente de QA desplegado.

---

## 9. Resumen por fase

```
Desarrollo Backend ············ 168 h  ████████████████████████████░░░░░░░░
Desarrollo Frontend ········· 52 h  ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░
Desarrollo App ·············· 158 h  ████████████████████████░░░░░░░░░░░░
Diseño UX/UI ················ 126 h  ███████████████████░░░░░░░░░░░░░░░░░
Pruebas y QA ················ 105 h  ████████████████░░░░░░░░░░░░░░░░░░░░
Despliegue a QA ············· 30 h  █████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
Capacitación ················ 15 h  ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

Total                       654 h
```

| | Horas | % |
|---|---:|---:|
| Desarrollo Backend | 168 | 26 % |
| Desarrollo Frontend | 52 | 8 % |
| Desarrollo App | 158 | 24 % |
| Diseño UX/UI | 126 | 19 % |
| Pruebas y QA | 105 | 16 % |
| Despliegue | 30 | 5 % |
| Capacitación | 15 | 2 % |
| **Total** | **654** | **100 %** |
