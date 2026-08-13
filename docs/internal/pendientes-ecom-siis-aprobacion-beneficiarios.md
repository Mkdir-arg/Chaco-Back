# Pendientes de ECOM/SIIS para completar la aprobación de beneficiarios

**Fecha:** 12/08/2026  
**Sistema consumidor:** DataÑach  
**Responsable externo:** ECOM / SIIS  
**Estado:** Bloqueado por contrato y endpoint externo pendientes

## Objetivo

Definir lo que ECOM debe entregar para que DataÑach pueda completar el circuito
real de aprobación de una persona. La prevalidación de compatibilidad ya funciona,
pero no equivale a la aprobación final como beneficiario.

## Qué está disponible y verificado

DataÑach ya consume correctamente el contrato vigente del manual técnico de SIIS:

| Operación | Endpoint | Estado |
|---|---|---|
| Obtener token M2M | `POST /api/v1/auth/token` | Implementado y probado contra SIIS |
| Consultar programas | `GET /api/v1/programas` | Implementado |
| Prevalidar compatibilidad | `POST /api/v1/validaciones/compatibilidad` | Implementado y probado contra SIIS |

La prevalidación envía:

```json
{
  "dni": "24459123",
  "id_programa": 41,
  "fecha_nacimiento": "1975-02-20"
}
```

DataÑach conserva un registro inmutable por cada intento, incluyendo `resultado`,
`apto`, `validaciones`, `id_consulta`, `fecha_hora`, programa, usuario solicitante
y la respuesta JSON completa.

## Qué falta

Falta el contrato para enviar una persona compatible desde DataÑach a la instancia
intermedia de **prebeneficiarios** de SIIS y conocer posteriormente su aprobación o
rechazo final por parte del operador de SIIS.

Sin ese contrato, DataÑach solamente puede afirmar:

> SIIS no encontró incompatibilidades para que la persona se postule.

No puede afirmar:

> La persona fue aprobada por SIIS como beneficiaria.

Como resguardo local, DataÑach exige desde el 12/08/2026 identidad validada y una
última prevalidación SIIS compatible, correspondiente al mismo DNI y programa,
antes de permitir la aprobación o la promoción desde lista de espera. Este gate
evita aprobar personas incompatibles, pero no reemplaza la aprobación final de SIIS.

## Información que debe proporcionar ECOM

### 1. Alta de prebeneficiario

ECOM debe confirmar:

- método y ruta del endpoint;
- si utiliza el mismo token M2M ya implementado;
- esquema completo del cuerpo JSON;
- campos obligatorios y opcionales;
- reglas de formato y validación;
- respuesta exitosa y respuestas de error;
- identificador estable de la postulación o prebeneficiario;
- comportamiento ante reintentos y duplicados.

Contrato mínimo esperado, sujeto a confirmación de ECOM:

```json
{
  "dni": "24459123",
  "id_programa": 41,
  "id_consulta_compatibilidad": "8ef13bfb-529a-4438-a8b4-dca8b238039a",
  "sistema_origen": "DATANACH",
  "id_formulario_origen": "25"
}
```

Preguntas concretas:

1. ¿Debe enviarse información personal adicional además del DNI?
2. ¿Debe enviarse la fecha de nacimiento?
3. ¿La prevalidación debe repetirse en SIIS o alcanza con referenciar `id_consulta`?
4. ¿SIIS rechazará una prevalidación vencida? En ese caso, ¿cuál es su vigencia?
5. ¿Cómo se evita duplicar una postulación si DataÑach reintenta por timeout?
6. ¿El identificador de DataÑach puede utilizarse como clave de idempotencia?

### 2. Consulta del estado final

ECOM debe definir cómo DataÑach conoce la resolución tomada por el operador SIIS:

- endpoint de consulta por ID de postulación; o
- webhook enviado desde SIIS hacia DataÑach; o
- ambos mecanismos.

Estados mínimos que DataÑach necesita distinguir:

| Estado externo | Significado esperado |
|---|---|
| `PENDIENTE` | Recibido por SIIS, todavía sin resolución humana |
| `APROBADO` | Aprobación final como beneficiario |
| `RECHAZADO` | Rechazo final con motivo |
| `OBSERVADO` | Requiere corrección o documentación adicional, si SIIS contempla este caso |
| `BAJA` | Beneficio posteriormente dado de baja, si corresponde al alcance |

Preguntas concretas:

1. ¿Cuáles son los nombres y transiciones reales de los estados de SIIS?
2. ¿Qué usuario, fecha y motivo se informan con la resolución?
3. ¿Un rechazo puede corregirse y reenviarse o es definitivo?
4. ¿SIIS notificará cambios posteriores, como suspensión o baja?
5. Si se utiliza webhook, ¿cómo se firma y valida cada notificación?

### 3. Reglas de cupo

ECOM debe confirmar quién tiene autoridad sobre el cupo final:

1. ¿DataÑach reserva cupo al crear el prebeneficiario?
2. ¿SIIS vuelve a controlar el cupo al aprobarlo?
3. ¿Qué sucede si había cupo en DataÑach pero ya no existe cuando SIIS resuelve?
4. ¿Las personas en lista de espera deben enviarse a SIIS o solamente al ser promovidas?
5. ¿Una prevalidación compatible consume algún cupo en SIIS?

### 4. Errores, reintentos e idempotencia

ECOM debe documentar:

- códigos HTTP y cuerpos para errores de negocio y técnicos;
- timeouts recomendados;
- política de reintentos;
- clave de idempotencia;
- tratamiento de respuestas perdidas después de un alta exitosa;
- límites de frecuencia;
- vigencia del token y eventual rotación de credenciales;
- mecanismo para consultar una operación cuyo resultado quedó incierto.

### 5. Ambiente y datos de prueba

Para validar el circuito antes de producción, ECOM debe suministrar:

- URL del ambiente de prueba;
- credenciales M2M específicas del ambiente;
- IDs de programas habilitados;
- DNI o casos controlados para obtener cada resultado;
- un caso aprobable de punta a punta;
- un caso rechazado con motivo;
- un caso observado, si existe ese estado;
- un caso duplicado/idempotente;
- forma de identificar o limpiar datos de prueba.

No deben compartirse secretos dentro de este documento ni incorporarse al repositorio.

## Flujo esperado cuando ECOM entregue el contrato

```text
Formulario ENVIADO
        ↓
Identidad validada y duplicados resueltos
        ↓
Prevalidación SIIS = OK / apto=true
        ↓
Revisión manual y control de cupo en DataÑach
        ↓
PREBENEFICIARIO
        ↓
Alta en tabla intermedia de SIIS
        ↓
Resolución del operador SIIS
        ↓
APROBADO o RECHAZADO en DataÑach
```

Hasta que el endpoint exista, `APROBADO` no debería interpretarse como una
confirmación emitida por SIIS.

## Decisiones internas posteriores al contrato

Una vez recibida la documentación de ECOM, DataÑach deberá cerrar estas decisiones:

1. Incorporar el estado local `PREBENEFICIARIO`.
2. Reservar `APROBADO` exclusivamente para la confirmación final de SIIS.
3. Definir la vigencia temporal de la prevalidación. La exigencia de compatibilidad
   y correspondencia con el mismo DNI y programa ya está implementada localmente.
4. Definir qué ocurre con los aprobados históricos existentes.
5. Determinar en qué estado se consume el cupo local.
6. Incorporar trazabilidad del alta, reintentos y resolución externa.
7. Adecuar listados, reportes, exportaciones, bajas y promoción desde lista de espera.

## Criterios para considerar desbloqueada la integración

- [ ] ECOM entregó el contrato de alta de prebeneficiarios.
- [ ] ECOM entregó el mecanismo de consulta o notificación de la resolución final.
- [ ] Están definidos estados, motivos y transiciones.
- [ ] Está definida la idempotencia.
- [ ] Está definida la autoridad y reserva de cupo.
- [ ] Existe un ambiente de prueba con casos controlados.
- [ ] Se completó una prueba de punta a punta: DataÑach → SIIS → resolución → DataÑach.
- [ ] La evidencia incluye los identificadores de auditoría de ambos sistemas.

## Texto breve para enviar a ECOM

> DataÑach ya consume autenticación, catálogo de programas y prevalidación de
> compatibilidad del contrato SIIS vigente. Para completar la aprobación real
> necesitamos el contrato del endpoint de alta de prebeneficiarios y el mecanismo
> para recibir o consultar la resolución final del operador SIIS. Solicitamos ruta,
> método, autenticación, payload, respuestas, estados, motivos, idempotencia,
> reglas de cupo, política de reintentos y casos de prueba controlados. También
> necesitamos confirmar si el `id_consulta` de compatibilidad debe enviarse y cuál
> es su vigencia.
