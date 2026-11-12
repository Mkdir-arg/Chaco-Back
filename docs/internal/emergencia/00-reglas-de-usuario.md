# Emergencia · 00 — Reglas de usuario (roles, superficies y permisos)

Fecha: 2026-11-06. Vale para todas las etapas (`01` a `05`). Si una etapa contradice este
archivo, gana este archivo y hay que corregir la etapa.

Cómo leer las reglas: cada una tiene código (`RU-n`), es verificable con un test, y dice
quién, dónde y qué. «PWA» es la app de campo `Chaco-mobile` (Expo, instalada como PWA);
«backoffice» es el sitio Django detrás de `includes/base.html`.

---

## 1. Los cuatro roles

| Rol | Quién es en la vida real | Superficie principal | Superficie secundaria |
|---|---|---|---|
| **Agente territorial** | Persona del Ministerio o del municipio que recorre el barrio inundado | PWA | — (no entra al backoffice) |
| **Operador de mesa** | Persona sentada en la mesa de operaciones del Ministerio | Backoffice | — |
| **Supervisor de mesa** | Coordinador de la mesa; responde por los tiempos | Backoffice | — |
| **Operador del dispositivo** | Persona de guardia en el centro de evacuados (escuela, club, parroquia) | **PWA y backoffice, con paridad** | — |

Un usuario puede tener más de un rol (un supervisor suele tener también operador). El rol
no es un grupo con nombre: es el conjunto de capacidades tildadas en su Rol
(`Group` + `users.RolMeta`), siempre dentro del programa **Emergencia**, salvo las del
dispositivo, que son del programa **Dispositivos** (ver §3).

---

## 2. El operador del dispositivo trabaja desde la PWA

Esto faltaba en el diseño del 04-nov y es regla desde hoy:

- **RU-1.** Todo lo que el operador del dispositivo puede hacer en el backoffice (E6) lo
  puede hacer en la PWA (M2 y M3): buscar la familia por DNI, aceptar o rechazar la
  derivación, cargar las fichas individuales, elegir la cama en el mapa de plazas, agregar
  una persona, cerrar el ingreso con diferencia, alojar, ingresar sin derivación, recibir
  un kit. **La PWA es la vía principal** del dispositivo: la guardia no tiene PC, tiene
  teléfono.
- **RU-2.** Las dos superficies usan **los mismos servicios** (`programas/services/`): la
  vista web y el endpoint de la API llaman a la misma función, con la misma validación y
  la misma traza. Nada se implementa dos veces, nada se valida solo en el cliente.
- **RU-3.** La PWA del dispositivo **requiere conexión** para aceptar, confirmar fichas y
  alojar: son operaciones sobre plazas compartidas con toda la red y no pueden quedar en
  una cola. Lo único que trabaja sin señal es el Formulario 1 del agente (etapa 1) y, en
  el dispositivo, el **ingreso directo** (sin derivación) que se encola como un caso de
  origen `DISPOSITIVO` y recién al sincronizar reserva y aloja (ver `03-alojar.md`, §7).
- **RU-4.** Al iniciar sesión, la PWA recibe la lista de módulos que abre ese usuario
  (`modulos` del login, `programas/api/views.py`). Se agrega `"emergencia"` cuando el
  usuario tiene `emergencia.relevar` (agente) **o** `dispositivo.admitir` en al menos un
  dispositivo de su equipo (operador de dispositivo). El selector de módulos de la app
  (`src/services/modulos.js`, `ModuloSelectorScreen.js`) suma «Emergencia».
- **RU-5.** Dentro del módulo Emergencia de la PWA, la pantalla inicial depende del rol:
  el agente ve «Ingreso de familias» (M1); el operador de dispositivo ve «Llegada de
  familias» (M2) y «Recepción de kits» (M3) de **su** dispositivo. Si tiene los dos roles,
  ve los tres accesos. Si integra el equipo de más de un dispositivo, elige el dispositivo
  primero (mismo patrón que `DispositivosListaScreen`).

---

## 3. Capacidades

Catálogo (`core/rbac.py`, `CATALOGO`). Módulo nuevo `emergencia`, `"alcance": "programa"`:

| Capacidad | Rol que la tiene | Qué habilita |
|---|---|---|
| `emergencia.relevar` | Agente territorial | Crear casos desde la PWA (Formulario 1). Entra en `CAPACIDADES_DE_CAMPO` (`core/rbac.py:893`), que hoy es `{"becas.campo", "inspeccion.relevar"}`: por eso el login la cuenta como acceso a la app. |
| `emergencia.operar` | Operador de mesa | Bandeja, tomar, soltar lo propio, derivar, registrar contactos, cerrar sin alojamiento, crear caso desde la mesa; crear entregas de kits y marcarlas en camino. |
| `emergencia.supervisar` | Supervisor de mesa | Todo lo de operar **más**: tablero E1, reasignar y soltar casos de otros, cambiar prioridad de un caso tomado por otro, configuración E7 (SLA, vigencia, catálogo). |
| `emergencia.recibir_kit` | Operador del dispositivo | Confirmar la recepción de una entrega destinada a su dispositivo (M3 / E6-kits). |

Del programa **Dispositivos**, ya existentes, sin cambios:

| Capacidad | Para qué la usa Emergencia |
|---|---|
| `dispositivo.admitir` | Aceptar/rechazar derivación, confirmar fichas con cama, alojar, ingreso directo. Es la misma que hoy habilita el asistente de ingreso. |
| `dispositivo.egresar` | Egresar a un integrante alojado (cierra el caso cuando no queda nadie). |
| `dispositivo.ver` / `dispositivo.ver_todos` | Ver plazas libres y el mapa de plazas. La mesa necesita `ver_todos` o ser admin del programa Dispositivos para armar el selector de derivación: se resuelve con un selector de solo lectura propio de Emergencia (ver RU-14). |
| `dispositivo.bitacora` | No hace falta: las entradas de bitácora que deja Emergencia son `AUTOMATICA`. |

Reglas:

- **RU-6.** Se autoriza **solo por capacidad**, nunca por nombre de grupo ni por
  `RolMeta.categoria`. `is_superuser` tiene bypass total.
- **RU-7.** Las capacidades `emergencia.*` se evalúan con `puede(user, cap,
  programa=EMERGENCIA)`. El programa `EMERGENCIA` se crea en el seed (`crear_programas`) con
  un `RolMeta.programa` posible para sus roles.
- **RU-8.** Las acciones del dispositivo se evalúan con `puede_operar_dispositivo(user,
  dispositivo, "dispositivo.admitir")` (`programas/services/dispositivos.py:150`): la
  capacidad en el programa Dispositivos **y** pertenecer al equipo de ese dispositivo
  (`MiembroEquipoDispositivo` activo con un rol que la tenga), salvo admin del programa.
  `emergencia.recibir_kit` se evalúa igual, con la misma función, pasando esa capacidad.
- **RU-9.** Un operador de dispositivo **nunca** ve casos, derivaciones ni entregas de otro
  dispositivo. La API filtra por `dispositivos_en_alcance(user, cap)`; una búsqueda por
  DNI devuelve «sin derivación vigente» si la derivación es para otro dispositivo, **sin
  decir cuál** (dato personal de la familia).
- **RU-10.** La mesa (operar/supervisar) ve todos los casos del programa, sin alcance
  territorial. No hay recorte por localidad en esta etapa.
- **RU-11.** Un usuario ciudadano del portal (`es_ciudadano_portal`) no llega a ninguna
  URL de Emergencia: lo frena `PortalCiudadanoMiddleware` antes de la vista.

---

## 4. Qué puede hacer cada rol, acción por acción

Leyenda: ✔ puede · ✖ no puede · ◐ con condición. «Disp» = operador del dispositivo.

| Acción | Agente | Operador mesa | Supervisor | Disp |
|---|---|---|---|---|
| Crear caso desde territorio (M1) | ✔ | ✖ | ✖ | ✖ |
| Crear caso desde la mesa (E2 «Nuevo caso») | ✖ | ✔ | ✔ | ✖ |
| Ver bandeja y ficha del caso (E2, E3) | ✖ | ✔ | ✔ | ◐ solo los derivados o alojados en su dispositivo, en M2/E6 |
| Tomar un caso `NUEVO` | ✖ | ✔ | ✔ | ✖ |
| Soltar un caso | ✖ | ◐ solo el propio | ✔ cualquiera | ✖ |
| Reasignar un caso a otro operador | ✖ | ✖ | ✔ | ✖ |
| Cambiar prioridad | ✖ | ◐ si lo tiene tomado | ✔ | ✖ |
| Registrar contacto con la familia | ✖ | ◐ si lo tiene tomado | ✔ | ✖ |
| Derivar | ✖ | ◐ si lo tiene tomado | ✔ | ✖ |
| Cancelar una derivación `PENDIENTE` | ✖ | ◐ si lo tiene tomado | ✔ | ✖ |
| Cerrar sin alojamiento | ✖ | ◐ si lo tiene tomado | ✔ | ✖ |
| Aceptar / rechazar derivación | ✖ | ✖ | ✖ | ✔ (`admitir`, su dispositivo) |
| Confirmar ficha + cama, agregar persona, cerrar con diferencia, alojar | ✖ | ✖ | ✖ | ✔ (`admitir`) |
| Ingreso directo sin derivación | ✖ | ✖ | ✖ | ◐ si hay plazas libres |
| Egresar a un integrante | ✖ | ✖ | ✖ | ✔ (`egresar`) |
| Crear entrega de kit, marcar en camino, cancelar | ✖ | ✔ | ✔ | ✖ |
| Recibir kit | ✖ | ✖ | ✖ | ✔ (`recibir_kit`) |
| Ver tablero E1 | ✖ | ✖ | ✔ | ✖ |
| Configurar SLA, vigencia, catálogo (E7) | ✖ | ✖ | ✔ | ✖ |

- **RU-12.** «Si lo tiene tomado» = `caso.tomado_por == user`. El operador que no lo tiene
  tomado ve la ficha en solo lectura con el botón «Tomar» (si está `NUEVO`) o el aviso
  «Tomado por Nombre Apellido hace 12 min».
- **RU-13.** El supervisor puede actuar sobre cualquier caso sin tomarlo, y la traza
  registra «por supervisor».
- **RU-14.** El selector de dispositivos para derivar (E3) es una consulta de solo lectura
  de Emergencia (`selectors/emergencia.py`, `dispositivos_para_derivar(caso)`), autorizada
  por `emergencia.operar`, **no** por `dispositivo.ver`. Devuelve solo: nombre, localidad,
  plazas libres, reservadas, distancia. Nada de la operación interna del dispositivo.

---

## 5. Reglas transversales de datos y comportamiento

- **RU-15.** Toda transición de estado de un caso, derivación o entrega deja una fila en
  `TrazaCaso` / `TrazaEntrega` (inmutable, como `TrazaDispositivo`) con usuario, momento,
  estado anterior, estado nuevo y detalle. Aceptar, alojar, cerrar con diferencia y recibir
  kit dejan además `EntradaBitacora` `AUTOMATICA` en el dispositivo (tipo `INGRESO` o
  `GENERAL`).
- **RU-16.** Toda escritura desde la PWA lleva `uuid_cliente` y es **idempotente**: el
  mismo `uuid_cliente` dos veces devuelve el mismo resultado, sin duplicar (patrón de las
  inspecciones, `docs/internal/contrato-app-dispositivos.md`).
- **RU-17.** Las fotos (vivienda, acceso, remito) y las fichas individuales son datos
  personales: se sirven detrás de login desde `media/`, nunca en `docs/client/`, nunca en
  una URL sin sesión o token.
- **RU-18.** Los tiempos del SLA se calculan con las marcas de tiempo del caso
  (`tomado_en`, `derivado_en`, `aceptado_en`, `alojado_en`), en el servidor, **nunca** con
  la hora del teléfono. La única hora del cliente que se guarda es `relevado_en` del
  Formulario 1 (cuándo estuvo el agente en el lugar), y se muestra como «relevado a las
  14:20, enviado a las 16:05» cuando difieren.
- **RU-19.** El semáforo de SLA siempre es **texto + color** («Fuera de SLA · 42 min»),
  nunca solo color. Umbral «por vencer» = 80 % del objetivo.
- **RU-20.** Los mensajes de error al usuario dicen qué pasó y qué hacer («La derivación
  venció a las 02:20. Pedile a la mesa que vuelva a derivar o ingresala igual si tenés
  plazas»). Los errores de alcance en la API devuelven cuerpo explicativo, como el contrato
  de inspecciones (§ accesos).
- **RU-21.** Ningún aviso automático a la familia en esta etapa (sin SMS, sin WhatsApp, sin
  correo). El contacto es un registro manual (`ContactoCaso`).
- **RU-22.** Confirmaciones destructivas (rechazar, cancelar, cerrar sin alojamiento,
  cerrar con diferencia) piden motivo y usan modal (SweetAlert2 en backoffice, modal nativo
  de la app), nunca `confirm()`.

---

## 6. Qué tiene que probar cada regla (tests de mutación)

Para cada RU con «✖» o «◐» en §4 hay un test que **rompe la regla y ve el rojo**:

1. Usuario con `emergencia.operar` pero sin `supervisar` intenta reasignar → 403 y la
   fila no cambia.
2. Operador de dispositivo A busca el DNI de una familia derivada al dispositivo B →
   «sin derivación vigente», y la respuesta no contiene el nombre del dispositivo B.
3. Un rol de **Becas** (p. ej. `becas.campo`) no abre `"emergencia"` en el login ni ve
   ninguna URL del módulo (el caso que ya cobró en Dispositivos: «un rol de Becas
   habilita»).
4. Dos operadores toman el mismo caso en la misma transacción → uno gana, el otro recibe
   «Tomado por otro operador».
5. El mismo `uuid_cliente` enviado dos veces crea **un** caso.

Cada test se escribe primero contra la regla invertida, se ve fallar, y recién después se
implementa (`feedback-tests-que-pasan-por-el-motivo-equivocado`).
