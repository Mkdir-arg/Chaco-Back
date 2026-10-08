# Plan de implementación del MVP de Dispositivos — tabla rasa

**Decisión del PM (08/10/2026):** borrar lo construido del Programa Dispositivos e implementarlo de
cero, con el alcance del [MVP de 700 h](../../client/funcionalidades/mvp-dispositivos-v2.md).
**Merenderos queda fuera: no se toca.**

**Condiciones que lo habilitan**, confirmadas por el PM: **no hay datos reales cargados** y **nadie
usa el programa hoy**. Sin eso, la tabla rasa no sería viable y habría que convivir y migrar.

**Dos ejes, no uno.** Este plan separa deliberadamente **la lógica** —modelos, servicios, reglas— de
**el diseño** —piezas del sistema, goldens, apariencia—, porque el requisito del PM es que la v2
**se vea igual al mockup**, y eso no sale solo de implementar bien el backend. Cada etapa declara las
dos mitades.

**Fuentes.** El inventario visual y de datos pantalla por pantalla está en
[`mapeo-mockup.md`](mapeo-mockup.md), con los 15 conflictos decididos el 06/10 (Cambio 134). Este
plan **no los reabre**: los aplica, recortados al MVP.

---

## 1. Qué se borra y qué se conserva

Verificado contra el código: los modelos que se dan de baja **solo se referencian entre sí**, y
Merenderos no depende de ninguno de ellos. El acoplamiento hacia afuera del programa es una sola
vista de 38 líneas.

### Se conserva, sin tocar

| Modelo | Por qué |
|---|---|
| `TipoDispositivo` | El catálogo de tipos. El MVP no rehace la configuración por tipo |
| `Dispositivo` | El legajo institucional. El MVP dice textual «el dispositivo tal como está hoy» |
| `AsignacionDispositivo` | El alcance por institución, que el MVP usa tal cual |
| `TrazaDispositivo` | La auditoría aditiva; es el patrón que hereda la trazabilidad del MVP |
| `Merendero`, `SolicitudMerendero`, `EntregaMercaderia`, `PrestacionMensual`, `PrestacionDiaria` | **Merenderos queda fuera del alcance** |

### Se borra y se reemplaza

| Se va | Entra en su lugar | Etapa |
|---|---|---|
| `Cama` | `Sector` + `Plaza`, con tipo de plaza y estados | E1 |
| `Admision` + `ArchivoAdmision` | `Estadia` + `MovimientoEstadia` | E2 |
| `RegistroDiario` | `Turno` + `EntradaBitacora` | E3 |

### Se borra sin reemplazo en el MVP

| Se va | Por qué |
|---|---|
| `EsperaAdmision` | La lista de espera **no entra** en el MVP. Se rehace cuando entre |
| `CampoTipoDispositivo` | El MVP no tiene formularios configurables, y el F-00 muere con la admisión. Se rehace en la v2 completa, sobre el motor de formularios |

### Lo que hay que reescribir fuera del programa

- `legajos/views/dispositivos.py` y su ruta — la solapa del legajo ciudadano. Se reescribe contra
  `Estadia` en la E2; es trabajo que el MVP ya contempla.
- `programas/services/solapas.py`, tres ramas que hoy consultan `Admision`.
- `templates/includes/sidebar/opciones.html`, tres entradas de menú.

### Cómo se borra, sin pelearse con el CI

`scripts/check_migraciones.py` es un gate: todo `DeleteModel` lleva su marca
`# CONTRACT: <dejó de leerse en la release X>` y **va una release después** de que el código deje de
leerlo. Con la base vacía y sin usuarios eso es trámite, no riesgo, pero hay que respetarlo:

1. **Release A** — el código nuevo deja de leer los modelos viejos; las tablas siguen ahí, vacías.
2. **Release B** — migración de borrado con su `# CONTRACT`.

No se usa `--fake` ni se tocan las migraciones ya aplicadas.

---

## 2. Etapa 0 · El terreno y las piezas

**Bloquea la primera pantalla.** Es la etapa que hace que el resultado se vea igual al mockup; sin
ella cada pantalla improvisa su propia versión de cada componente y el parecido se pierde.

### Lógica

- Dar de baja del código las lecturas de `Cama`, `Admision`, `RegistroDiario`, `EsperaAdmision`,
  `ArchivoAdmision` y `CampoTipoDispositivo`, dejando el legajo institucional en pie.
- Las migraciones de borrado con su marca de contrato.
- Decidir el **nombre del modelo del relevamiento edilicio**. `Relevamiento` ya existe y es de Becas,
  con sus capacidades y una entrada de memoria sobre el vocabulario (Q4 del mapeo). Propuesta:
  el modelo se llama **`InspeccionDispositivo`** y la etiqueta visible sigue diciendo
  **«Relevamientos»**, que es el vocabulario del cliente.

### Diseño

Las seis piezas **ya aprobadas** el 06/10, que son tasks del análisis M0 en GitHub:

| Pieza | Para qué, en el MVP | Esfuerzo |
|---|---|---|
| Variante «tablero» de `_stat_card` | La franja de indicadores de P4 y P19 | ~1 día |
| Ampliación de `_alerta.html` con ícono y acción | Quince pantallas del mockup; cinco del MVP | ~½ día |
| Variante `btn-fit` sin ancho mínimo | Sin ella ninguna barra de acciones se parece al mockup | ~½ día |
| Menú de fila accesible (`.kebab`) | P4 y P21 | ~1 día |
| Hero de inicio de programa | La portada del programa | ~½ día |
| Bloque de ubicación sin mapa | P19. El mapa embebido quedó **descartado**: la CSP bloquea los CDN | ~2 h |

Las piezas **nuevas que el MVP necesita** y todavía no tienen decisión. Cada una se propone al abrir
la primera pantalla que la usa, y el mismo diff actualiza su ficha en `.claude/design/`:

| Pieza | Dónde |
|---|---|
| `eyebrow` en `page_header` | Casi todas |
| Filtro rápido en píldora (`.nf.pill`) | P4, P10, P21 |
| Chips de selección múltiple | P10, P21 |
| Switch (`.toggle`) | P9 |
| Mapa de plazas (`.plazas`) con su leyenda | P5, P6 |
| Línea de tiempo (`.tl`) | P7, P19 |
| Sección de ficha (`.sec`) con progreso y bloqueo | P7 |
| Tarjeta de turno (`.turno`) | P10 |
| Entrada de bitácora (`.entry`) | P10 |
| Galería fotográfica histórica (`.fotos`) | P19 |
| Stepper de backoffice | P6 |

!!! danger "Dos pantallas del MVP están frenadas por el agente de diseño"
    **P6 (asistente de ingreso)** es un *wizard* y **P7 (detalle de la estadía)** es un *caso
    complejo*. Ninguno de los dos arquetipos tiene golden, y el agente canónico **manda frenar y
    devolver** cuando una pantalla no tiene molde. No se saltea con una excepción escrita.

    Construir esas dos goldens es **precondición de la etapa 2 y de la 3**, y son las dos pantallas
    más importantes del MVP. Se arrancan en la etapa 0, en paralelo con lo demás.

**Costo de esta etapa: unas 100 h**, de las cuales ~28 son las piezas aprobadas, ~24 las dos goldens,
~40 las piezas nuevas y ~8 el borrado con sus migraciones.

!!! warning "Esto no está en las 700 h"
    El presupuesto del Ministerio cotiza funcionalidad, no el trabajo de sistema de diseño que la
    hace verse como el mockup. Y la reserva de 100 h **ya está comprometida** con las cinco
    funcionalidades que se sumaron después (el funcionamiento sin conexión, sobre todo).

    A favor: **esta etapa no se paga dos veces**. Las piezas y las goldens sirven para toda la
    Versión 2 y para el resto del sistema, no solo para el MVP.

---

## 3. Los dos carriles

A partir de la etapa 0 el trabajo se abre en dos carriles que **avanzan en paralelo**, porque el
relevamiento lo ejecuta el equipo móvil junto con backend, y el circuito de las personas es trabajo
de backoffice.

```
E0 · terreno y piezas
      ├── carril A (backoffice) ──  E1 sectores → E2 ingreso y egreso → E3 circuito interno
      └── carril B (campo)      ──────────────── E4 relevamiento (necesita E1)
```

El carril B depende de la E1 porque el relevamiento se carga **por edificio**, así que no puede
arrancar antes de que esa entidad exista.

---

## 4. Etapa 1 · El edificio, los sectores y las plazas

La base de los dos carriles. Sin esto no hay dónde alojar a nadie ni qué relevar.

### Lógica

- **`Edificio`**: el inmueble, con relación de **varios a varios** con `Dispositivo`. Un predio puede
  alojar más de una institución —parador, geriátrico y Sotai en el mismo predio de Resistencia— y una
  institución podría ocupar más de un inmueble. **Decisión del PM del 08/10/2026**: el relevamiento es
  del edificio, no del sector, así que esta entidad entra al MVP y deja de ser parte de la etapa 5 de
  la Versión 2.
- `Sector`: nombre, tipo, capacidad y condiciones de uso. Cuelga del dispositivo, no del edificio:
  el edificio es el inmueble y el sector es la organización operativa de la institución.
- `Plaza` dentro del sector, con su tipo —cama, cupo o turno— y su estado.
- El **servicio único de cálculo**: operativas, ocupadas, disponibles. Todo derivado de los
  movimientos; nada se tipea. Es la pieza de la que después dependen el censo y la vista de situación.
- Migración del esquema. Sin datos que mover.

### Diseño

**P5 · Sectores y plazas.** Arquetipo *detalle*, con golden. Usa el **mapa de plazas** (`.plazas`)
con sus cinco estados tonales y la leyenda, que es la pieza visual más característica de la pantalla
y hay que construirla acá.

---

## 5. Etapa 2 · Ingreso y egreso

### Lógica

- `Estadia` reemplazando a `Admision`: persona, dispositivo, plaza, fechas, estado.
- **Clave de alojamiento**: el mecanismo que permite preguntar si una persona ya está alojada
  **en cualquier dispositivo de la red**. Es lo que sostiene la verificación que el PM sumó al
  alcance, y es un dato nuevo, no una consulta más.
- Validaciones: plaza libre, egreso nunca anterior al ingreso.
- Egreso con catálogo de motivos, destino y derivación, más la liberación del cupo.
- Reescritura de la **solapa del legajo ciudadano** contra `Estadia`, con el historial completo
  —incluidas las estadías cerradas— y sin los tres candados que hoy la hacen desaparecer al egresar.
- Trazabilidad sobre el patrón de `TrazaDispositivo`.

### Diseño

| Pantalla | Arquetipo | Estado |
|---|---|---|
| **P6** · Asistente de ingreso | Wizard | **Necesita su golden** (E0). Usa el stepper de backoffice y el selector de plaza |
| **P9** · Egreso | Modal de confirmación con motivo | Golden existente. Usa el switch |
| **P4** · Detalle del dispositivo | Detalle con solapas | Golden existente. Usa la franja de indicadores, el filtro en píldora y el menú de fila |
| **P16** · Solapa del legajo | Detalle con solapas | Golden existente. Barata una vez que `Estadia` existe |

---

## 6. Etapa 3 · Circuito interno

### Lógica

- `MovimientoEstadia`: cambios de sector, con su registro.
- Permanencia y cambios de estado.
- `Turno` y `EntradaBitacora`, con responsable. Las entradas **se agregan**, no se pisan.
- **Censo automático por turno**: existencia inicial, ingresos, egresos y existencia final,
  calculados desde los movimientos. Ojo con una trampa conocida del proyecto: **nada de `Trunc*`
  sobre un `DateTimeField`**, porque la base de ECOM no tiene tablas de zona horaria y devuelve nulo
  solo en producción.
- Alertas por criticidad, sobre el registro de reglas de `core/services/vencimientos.py`, que ya
  existe y está pensado para extenderse.
- Auditoría básica.

### Diseño

| Pantalla | Arquetipo | Estado |
|---|---|---|
| **P7** · Detalle de la estadía | Caso complejo | **Necesita su golden** (E0). Usa la sección de ficha y la línea de tiempo |
| **P10** · Bitácora del turno | Detalle degradado | Golden existente. Usa la tarjeta de turno, la entrada de bitácora, los chips y el filtro en píldora |

!!! note "Qué no entra, aunque la pantalla lo insinúe"
    El **pase de guardia** queda fuera del MVP. El censo se calcula solo, pero no existe el acto
    formal de que un turno le entregue al siguiente con constancia. Al implementar P10 hay que
    construir la pantalla **sin** ese bloque, no dejarlo deshabilitado.

---

## 7. Etapa 4 · Relevamiento en campo

Carril paralelo. Arranca cuando la E1 deja el sector disponible.

### Lógica

- `InspeccionEdificio` —nombre a confirmar—: **edificio**, criticidad, observaciones, responsable,
  fecha y estado. **No cuelga del sector ni del dispositivo**: un predio compartido se releva una vez
  y el resultado lo ven todas las instituciones que lo ocupan.
- **Creación y asignación por el coordinador**: elige el dispositivo y el agente, y la tarea le llega
  a la aplicación. El agente no elige libremente qué relevar.
- Fotos como evidencia, con almacenamiento protegido detrás de login, sobre el patrón que ya usa
  el adjunto de admisión.
- **Los servicios que consume la aplicación**: autenticación del agente, sus tareas asignadas, y el
  envío de datos y fotos. El patrón ya existe para la app de campo de Becas.
- **Funcionamiento sin conexión.** Es la pieza de mayor peso técnico de todo el MVP: almacenamiento
  local en el celular, cola de sincronización, reintentos, resolución de conflictos y fotos pesadas.
  Estaba **explícitamente fuera de alcance** en la propuesta de la Versión 2 y entró por decisión del
  PM. La mayor parte del trabajo es del lado de la aplicación.
- Semáforo de criticidad sobre el dispositivo.

### Diseño

| Pantalla | Arquetipo | Estado |
|---|---|---|
| **P21** · Relevamientos: listado y asignación | Listado + modal | Golden existente. Usa el menú de fila y los chips |
| **P19** · Solapa Infraestructura | Detalle con solapas | Golden existente. **Solo la parte del MVP**: criticidad, observaciones y galería fotográfica con su línea de tiempo. Sin tenencia, sin servicios, sin ubicación y sin la regla de vigencia |

---

## 8. Resumen

| Etapa | Qué deja | Carril |
|---|---|---|
| **E0** | El terreno limpio y las piezas de diseño que hacen que se vea igual al mockup, más las dos goldens que faltan | Bloquea todo |
| **E1** | El edificio, los sectores y las plazas, con el cálculo único de ocupación | A y B |
| **E2** | Ingreso y egreso con verificación en toda la red, y la solapa del legajo ciudadano | A |
| **E3** | Movimientos, bitácora por turno con censo automático y la vista de situación | A |
| **E4** | El relevamiento en campo, con la app y el funcionamiento sin conexión | B |

**Orden de ataque.** Primero la E0 completa, porque bloquea. Después, en paralelo: el carril A
arranca por la E1 y sigue de corrido; el carril B se suma apenas la E1 libera el sector.

**Lo que hay que decidir para arrancar:**

1. **El nombre del modelo del relevamiento.** Propuesta: `InspeccionDispositivo` como modelo,
   «Relevamientos» como etiqueta visible.
2. ~~Si la etapa 0 se absorbe o se cotiza.~~ **Resuelto el 08/10/2026: se absorbe.** El PM lo dio por
   cerrado («no importa que lleve esas 100 horas»).
3. **Las definiciones del cliente** que están en el correo a Guido: escala de criticidad, si el
   agente debe ser externo, estados del relevamiento y catálogo de motivos de egreso. La de
   «sector o edificio» **ya la cerró el PM el 08/10/2026: por edificio**, y el plan está escrito con
   esa decisión aplicada.
