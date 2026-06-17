# Estimación de esfuerzo — Programa Becas
## Relevamiento territorial y asignación de cupos

**Fecha:** 2026-06-17
**Versión:** 1.1
**Alcance cubierto:** Análisis A — funcionalidades sin dependencia de integración SIS

---

## 1. Resumen ejecutivo

| Concepto | Horas |
|---|---:|
| Desarrollo | 130 |
| Diseño UX/UI | 25 |
| Pruebas funcionales y QA | 67 |
| Despliegue a ambiente QA | 14 |
| Capacitación | 14 |
| **Total** | **250** |

> Las horas corresponden a esfuerzo técnico neto. No incluyen reuniones de seguimiento, gestión de proyecto ni la integración con el Sistema SIS (Análisis B, pendiente de contrato técnico — ver §6).

---

## 2. Desarrollo

### 2.1 Detalle por módulo

| Ref | Módulo | Descripción | Horas |
|---|---|---|---:|
| T-01 | Modelo de datos | Modelos del dominio Becas: Segmento, Subsegmento, Convocatoria, Relevamiento, PreguntaGlobal, RequisitoNativo, AsignacionCoordinador, Formulario, TracaFormulario, ListaEspera. Migraciones y admin básico. | 12 |
| T-02 | Configuración del programa | ABM de segmentos, subsegmentos con validación de cupo, asignación de coordinadores por segmento, ABM de requisitos nativos con tipo de campo (texto / número / selector / fecha / archivo) y ABM del cuestionario social (13 preguntas globales con toggle activo). | 10 |
| T-03 | Convocatorias | ABM de convocatorias con selección dinámica de segmento y subsegmento (Alpine.js). Visualización de requisitos configurados. | 4 |
| T-04 | Relevamientos | ABM de relevamientos, asignación y reasignación de territorial, reprogramación por Coordinador. | 5 |
| T-05 | Revisión de formularios | Pantalla de revisión caso a caso: aprobación, rechazo con motivo, edición de datos con trazabilidad completa (quién / cuándo / valor anterior). | 6 |
| T-06 | Gestión de cupo | Vista de cupo por segmento, lista de beneficiarios activos, lista de espera, baja manual y promoción manual. | 5 |
| T-07 | Roles y autorización | Creación de roles Admin, Territorial y Coordinador integrados al motor RBAC existente. Control de acceso por segmento asignado para el rol Coordinador. | 5 |
| T-08 | Solapa Becas en legajo | Pestaña dinámica "Becas" en el legajo del ciudadano: estado, datos del formulario, vínculo con la pantalla de revisión. | 3 |
| T-09 | Reportes | Exportación CSV/Excel de beneficiarios activos, lista de espera y avance de relevamientos, con filtros por segmento y convocatoria. | 4 |
| T-10 | API para app de campo | Endpoints REST para la app territorial: autenticación, listado de relevamientos con definición dinámica del formulario (tipos de campo y opciones), carga de formularios, sincronización offline y finalización en lote. | 8 |
| T-11 | Validación RENAPER | Integración de los 3 caminos de validación de identidad (escaneo de DNI / RENAPER online / carga manual). Revalidación diferida desde el backoffice. | 4 |
| T-12 | App de campo (React Native) | App Expo/React Native para el agente territorial: autenticación JWT con persistencia de sesión, listado de relevamientos asignados, motor de formulario dinámico (6 tipos de campo: STRING / INT / SELECTOR / SELECTOR_MULTIPLE / DATE / ARCHIVO), captura GPS automática, escaneo y validación de DNI (3 caminos RENAPER), carga de adjuntos con cámara, almacenamiento offline con sync automático al reconectar, finalización de relevamiento. EAS Build para Android e iOS. | 64 |
| | **Subtotal desarrollo** | | **130** |

### 2.2 Detalle de la app de campo (T-12)

| Componente | Horas |
|---|---:|
| Setup: proyecto Expo, navegación, estado global, auth JWT | 8 |
| Pantalla de relevamientos (lista, detalle, badges de estado) | 6 |
| Motor de formulario dinámico (6 tipos de campo, bloques fijos, GPS) | 14 |
| Escaneo de DNI y flujo de validación RENAPER (3 caminos) | 8 |
| Carga y almacenamiento de adjuntos (cámara + archivos) | 6 |
| Sincronización offline (cola local, retry, indicador de estado) | 10 |
| Envío, actualización y finalización de relevamiento | 5 |
| EAS Build, signing, configuración de entornos y distribución de prueba | 7 |
| **Total T-12** | **64** |

### 2.3 Distribución por perfil

| Perfil | Módulos | Horas |
|---|---|---:|
| Desarrollador fullstack | T-01 a T-09 | 50 |
| Desarrollador backend / API | T-10, T-11 | 12 |
| Desarrollador React Native | T-12 | 64 |
| Revisión técnica / code review | Todos | 4 |
| **Total** | | **130** |

---

## 3. Pruebas funcionales y QA

### 3.1 Alcance — backoffice

| Concepto | Horas |
|---|---:|
| Escritura de casos de prueba documentados (módulos T-01 a T-11) | 10 |
| Ejecución de pruebas por módulo | 14 |
| Pruebas de flujo end-to-end (relevamiento completo: desde configuración hasta cupo asignado) | 8 |
| Pruebas de la API (Postman o herramienta equivalente) | 4 |
| Registro de defectos, re-test y cierre | 4 |
| **Subtotal QA backoffice** | **40** |

### 3.2 Alcance — app de campo (React Native)

| Concepto | Horas |
|---|---:|
| Escritura de casos de prueba (formulario dinámico, offline, RENAPER) | 6 |
| Ejecución en dispositivo Android (flujo completo) | 8 |
| Pruebas de escenarios offline: guardar borrador → reconectar → sync | 6 |
| Pruebas de los 3 caminos de validación RENAPER desde el dispositivo | 4 |
| Registro de defectos, re-test y cierre | 3 |
| **Subtotal QA app** | **27** |

| **Total QA** | **67** |
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
| Configuración del ambiente (Docker, variables de entorno, base de datos) | 3 |
| Despliegue del código y ejecución de migraciones | 2 |
| Carga de datos iniciales de prueba (segmentos, preguntas del cuestionario social, usuarios y roles de prueba) | 3 |
| Verificación post-despliegue y smoke tests del backoffice | 2 |
| EAS Build del apk de prueba y distribución interna (Firebase App Distribution o similar) | 4 |
| **Subtotal despliegue** | **14** |

---

## 5. Capacitación

| Sesión | Destinatarios | Horas |
|---|---|---:|
| Elaboración de materiales (guía de usuario por rol, manual de la app) | — | 4 |
| Administradores del programa: configuración de segmentos, convocatorias, revisión de formularios, cupo y reportes | Equipo ministerio | 4 |
| Coordinadores: revisión de formularios y reprogramación de relevamientos | Coordinadores territoriales | 2 |
| Territoriales: instalación de la app y uso en campo (relevamientos y carga de formularios) | Agentes de campo | 4 |
| **Subtotal capacitación** | | **14** |

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

## 8. Resumen por fase

```
Desarrollo ················· 130 h  ████████████████████████████████░░░░░░░░
Diseño UX/UI ················ 25 h  ██████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
Pruebas y QA ················ 67 h  █████████████████░░░░░░░░░░░░░░░░░░░░░░
Despliegue a QA ·············· 14 h  ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
Capacitación ················ 14 h  ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

Total                       250 h
```

| | Horas | % |
|---|---:|---:|
| Desarrollo | 130 | 52 % |
| Diseño UX/UI | 25 | 10 % |
| Pruebas y QA | 67 | 27 % |
| Despliegue | 14 | 6 % |
| Capacitación | 14 | 6 % |
| **Total** | **250** | **100 %** |
