# Prompt para Claude Design — módulo Emergencia (mockups + video de 2 minutos)

Fecha: 2026-11-04. Acompaña a `2026-11-04-emergencia-design.md`.

**Antes de pegar:** adjuntar en Claude Design el archivo
`docs/client/mockups/dispositivos-v2.html` (también publicado en
https://Mkdir-arg.github.io/Chaco-Back/mockups/dispositivos-v2.html). Es la referencia
visual obligatoria. Si Claude Design no genera audio, pedirle solo el prototipo y el guion
con tiempos, y grabar la voz con el pipeline del video de Becas (`edge-tts`,
`es-AR-ElenaNeural`).

---

```text
Sos el diseñador de producto de DATAÑACH, el sistema de gestión social del Ministerio de Desarrollo Humano de la Provincia del Chaco. Tu trabajo tiene dos entregables, en este orden: (A) los mockups de un módulo nuevo llamado Emergencia y (B) un video narrado de máximo 2 minutos que explique el proceso completo usando esos mockups.

<referencia_visual>
Adjunto el mockup del programa Dispositivos (dispositivos-v2.html). Es el sistema de diseño real del producto, no una inspiración: reutilizá exactamente su chrome y sus piezas.
- Sidebar de 288 px con marca DATAÑACH, usuario con avatar y rol, grupo de menú «Programas» (el nombre del grupo no cambia). Emergencia se agrega como un programa más dentro de ese grupo.
- Barra superior, encabezado de página (.ph) con eyebrow, h1, bajada y acciones a la derecha.
- Tokens: Manrope; marca #5059bc; grises g050–g900; éxito #007a55; peligro #c70036; advertencia #b43403; gradiente de marca solo en el hero de inicio del programa.
- Piezas: stat cards (variante tablero), badges, campos .nf, tabla densa con thead fijo, stepper de 4 pasos, layout .split (ficha a la izquierda, acción a la derecha), surfaces por sector con el mapa de plazas de P5 (cuadraditos Disponible / Ocupada / Reservada / Prestada / Fuera de servicio), modal de confirmación con motivo obligatorio.
- Íconos Font Awesome, nunca emoji. Todo estado se comunica con texto además de color.
- Vocabulario del producto: «caso», «familia», «integrante», «derivación», «dispositivo», «plaza» o «cama», «estadía», «kit», «entrega», «mesa de operaciones». Castellano rioplatense, voseo en los textos de interfaz.
- Datos de ejemplo ficticios (familias «Pérez», «Gómez»; dispositivos «CIS N.º 3», «Escuela 412 · Centro de evacuados»). Ningún nombre, DNI ni dirección real.
</referencia_visual>

<proceso_a_diseñar>
Emergencia es la mesa de operaciones para las crecidas del río. Dos carriles.

Carril 1, casos:
1. Territorio. Un agente carga desde la app de campo (PWA, 390×844) el Formulario 1 «Ingreso de familias» (ver <formularios_fuente>): fuerza o institución que traslada, responsable de la familia (escanea el DNI o lo escribe; el sistema trae nombre y apellido de la Base de Personas), y la tabla de cantidades «Personas que ingresan juntas» (menores de 16, adultos, personas mayores × femenino / masculino, con totales calculados), más las personas que necesitan asistencia (dependientes, adultos mayores dependientes, lactantes). La app agrega ubicación por GPS y fotos. Sin señal, la carga queda en cola y se envía sola al reconectar. **El total de personas de esa tabla define el tamaño del grupo familiar**: si dice 7, el caso pide 7 plazas y el dispositivo deberá confirmar 7 fichas individuales.
2. Mesa de operaciones (backoffice). El caso aparece en la bandeja en estado NUEVO. Un operador lo «toma» (queda bloqueado para los demás, con su nombre visible). Ve la ficha de la familia y, al lado, los dispositivos de la red ordenados por plazas libres y distancia. Elige uno y deriva: el caso pasa a DERIVADO y se reservan plazas. Desde la creación corre un SLA por tramo (tomar, derivar, aceptar, alojar) y la bandeja muestra un semáforo con texto («Fuera de SLA · 1 h 20 min»). Registra el contacto con la familia (llamada / WhatsApp / presencial).
3. Dispositivo. Cuando la familia llega, el operador del dispositivo (app o backoffice) busca por el DNI del responsable (o de cualquier integrante ya confirmado), ve la tarjeta «Derivación vigente: familia Pérez · 7 personas declaradas · derivada 14:20 por Mesa» y acepta. Aceptar abre **una instancia del Formulario 2 «Registro individual» por cada persona declarada**: el grupo dijo 7, hay 7 fichas por confirmar, con un contador «3 de 7 confirmadas». Cada ficha se confirma con su cama elegida en el mapa de plazas y genera la estadía de esa persona; la primera ficha es la del responsable, precargada con sus datos. La familia queda «Alojada» cuando las 7 están confirmadas; mientras tanto el caso está «Ingreso en curso». Si llegan menos personas que las declaradas, el operador cierra el ingreso con la diferencia y el motivo («llegaron 6 de 7 · uno quedó con familiares»), y las plazas sobrantes se liberan; si llegan más, agrega una ficha y el contador pasa a 8. Al completar, se registra la sección 4 del Formulario 1 (sector / ala, aula / dormitorio, tarjeta familiar entregada) y la bitácora. Si no hay derivación y hay plazas, puede «Ingresar igual»: carga el Formulario 1 ahí mismo y sigue con las fichas; la mesa lo ve como «ingreso directo».
4. Rechazo y vencimiento: el dispositivo puede rechazar con motivo (sin plazas, no llegó); la derivación vence sola a las 12 h. En ambos casos el caso vuelve a la mesa.

Carril 2, kits:
5. La mesa arma una entrega para un dispositivo: ítems del catálogo (kit alimentario, kit de higiene, colchón, agua 6 l…) con cantidades. Estados: Preparada → En camino → Recibida / Recibida con diferencias.
6. El dispositivo recibe la entrega, corrige la cantidad recibida por ítem si difiere, adjunta foto del remito y confirma. Las diferencias quedan resaltadas para la mesa.

Tablero: casos nuevos, en gestión, fuera de SLA, familias alojadas hoy, plazas libres en la red, entregas en camino; lista por localidad.
</proceso_a_diseñar>

<formularios_fuente>
Los dos formularios en papel del Ministerio son la fuente de los campos. Respetá sus secciones y su vocabulario.

Formulario 1 · Ingreso de familias (una ficha por familia; lo carga el territorial en la app; la sección 4 la completa el dispositivo al alojar):
1. Ingreso y responsable: albergue / centro (lo asigna la mesa, no se pide en territorio), fecha de ingreso, N° de ingreso (lo da el sistema), fuerza o institución que realiza el traslado (Bomberos / Ejército / Defensa Civil / Policía / Municipio / Autoevacuado / Otra), DNI, apellido y nombre del responsable.
2. Personas que ingresan juntas: tabla de cantidades enteras, filas Menores de 16 años / Adultos / Personas mayores, columnas Femenino / Masculino / Total, con fila TOTAL DE PERSONAS calculada. Cada persona se cuenta una sola vez.
3. Personas que necesitan asistencia (cantidades, incluidas en el total): personas dependientes, adultos mayores dependientes, niños lactantes.
4. Ubicación y acreditación familiar: sector / ala / módulo, aula / dormitorio, pase o tarjeta familiar entregada (Sí / No), encargado.

Formulario 2 · Registro individual (una ficha por persona; lo completa quien hace el ingreso en el centro, una instancia por cada persona declarada en el Formulario 1):
Encabezado: N° de ficha familiar (el caso), albergue / centro, sector / ala, aula / dormitorio (la cama elegida), parentesco con el responsable (Jefe/a de hogar / Cónyuge o pareja / Hijo/a / Otro), fecha, hora, operador.
1. Datos personales: apellido, nombre, teléfono, DNI, ¿documento en mano? (Sí / No, extraviado en inundación), fecha de nacimiento, edad, género (F / M / Otro), etnia o pueblo (No aplica / Qom / Moqoit / Wichí / Otra).
2. Educación: nivel alcanzado (Ninguno / Primario / Secundario / Terciario-Universitario), estado (Completo / Incompleto / En curso), escolaridad actual y establecimiento.
3. Vacunación · emergencia hídrica: antitetánica y hepatitis A (Al día / Faltante o desconoce / Aplicada en operativo); leptospirosis o quimioprofilaxis (Indicada / No indicada / En tratamiento).
4. Salud y medicación: embarazo (semanas, controles al día), lactante o menor de 5, adulto mayor dependiente, discapacidad (motriz / visual / auditiva / intelectual-psicosocial), CUD, apoyos, electrodependiente y equipo, enfermedades crónicas (hipertensión / diabetes / asma / otra), medicamentos diarios, ¿tiene dosis para los próximos días? (No = reposición urgente), centro de salud habitual.
5. Trabajo y situación general: ocupación, condición laboral (Asalariado formal / Informal / Cuenta propia / Desocupado / Jubilado-pensionado), ¿sale del albergue por trabajo?, turno; adultos responsables (si es menor o tiene discapacidad) con nombre y vínculo; mascotas (Sí / No) y destino del animal (canil del albergue / quedó en domicilio / con terceros).
6. Observaciones y contención.

Regla de diseño para la ficha individual: es larga, así que la pantalla la organiza en solapas o acordeones por sección, con un **mínimo obligatorio para confirmar** (parentesco, datos personales y los avisos de salud críticos: embarazo, discapacidad, electrodependiente, medicación sin dosis) y el resto completable después, con badge «Ficha incompleta» en la lista de integrantes. Los avisos críticos de salud se muestran como badges en la ficha de la familia (E3) y en la lista de integrantes del dispositivo.
</formularios_fuente>

<entregable_A_mockups>
Diseñá estas 10 pantallas, numeradas y con este nombre exacto. Escritorio a 1440 px; app a 390×844.
E1 Tablero de Emergencia (escritorio): hero del programa + stat cards + tabla por localidad + entregas en camino.
E2 Bandeja de casos (escritorio): filtros Estado / Prioridad / Localidad / Operador / SLA; columnas Familia (titular y N integrantes), Localidad, Prioridad, Estado, Tomado por, Tiempo en estado con semáforo; botón «Tomar» en las filas NUEVO.
E3 Detalle del caso y derivación (escritorio, layout split): izquierda ficha de la familia, integrantes, necesidades, fotos, contactos, traza; derecha selector de dispositivos con plazas libres y distancia, botón «Derivar», acciones «Registrar contacto» y «Cerrar caso» (modal con motivo).
E4 Entregas de kits (escritorio): listado con estados y asistente de 3 pasos (Dispositivo → Ítems → Confirmar).
E5 Detalle de entrega (escritorio): líneas enviadas vs recibidas, diferencias resaltadas, remito, quién recibió y cuándo.
E6 Recepción en el dispositivo (escritorio): buscar por DNI → tarjeta de derivación vigente («7 personas declaradas») → aceptar → lista de integrantes con contador «3 de 7 confirmadas» y, por cada una, la ficha individual (Formulario 2 en solapas por sección, mínimo obligatorio marcado) con la cama elegida en el mapa de plazas de P5; acciones «Agregar persona» y «Cerrar ingreso con diferencia» (modal con motivo).
E7 Configuración (escritorio): SLA en minutos por tramo, vigencia de la derivación, catálogo de kits.
M1 App · Ingreso de familias (Formulario 1): stepper de 4 pasos (Traslado y responsable → Personas que ingresan juntas, la tabla de cantidades con totales calculados → Personas que necesitan asistencia → Ubicación y fotos) y pantalla de «Enviado · 7 personas» con el aviso de cola sin conexión.
M2 App · Llegada de una familia al dispositivo: buscar DNI → derivación vigente «7 personas declaradas» → lista de integrantes con contador «3 de 7 confirmadas» → ficha individual (Formulario 2, secciones colapsables, mínimo obligatorio) con elección de cama → «Familia alojada · 7 de 7».
M3 App · Recepción de kit: ítems con cantidad esperada y recibida, foto del remito, confirmar.

Reglas: cada pantalla se construye con las piezas del mockup adjunto; si necesitás una pieza que no existe ahí, usá la más parecida y anotala en una lista «Piezas nuevas» al final, con una línea por pieza. No inventes un lenguaje visual nuevo, ni modo oscuro, ni mapa geográfico. Los estados vacíos y los errores («DNI sin derivación vigente», «Faltan 2 plazas») se muestran en la pantalla que corresponde.
</entregable_A_mockups>

<entregable_B_video>
Un recorrido narrado de máximo 120 segundos, en castellano rioplatense, con voz femenina neutra, que muestre los mockups en el orden del proceso. Formato: video 1920×1080; la app se muestra en un marco de 390×844 centrado. Sin música sobre la voz. Subtítulos.

Usá este guion tal cual (275 palabras, ritmo de 140 palabras por minuto). Cada bloque indica el segundo de inicio y la pantalla que se ve:

[0:00 · portada con el nombre del módulo] «Cuando el río crece, las familias necesitan un lugar seguro y el Ministerio necesita saber dónde están. Emergencia es el módulo de DATAÑACH que une las dos cosas.»
[0:12 · M1, paso a paso] «En territorio, un agente abre la app y carga el Ingreso de familias: escanea el DNI del responsable, anota cuántas personas son, cuántas necesitan asistencia, y toma la ubicación. Si no hay señal, la carga queda guardada y se envía sola cuando vuelve.»
[0:34 · E2 y después E3] «El caso llega a la mesa de operaciones. Cualquier operador lo toma, y nadie más puede tomarlo a la vez. Ve a la familia, cuántas personas son y qué dispositivos de la red tienen camas libres cerca. Elige uno y deriva. Desde ese momento corre el reloj: cada paso tiene un tiempo objetivo y la bandeja avisa cuando se pasa.»
[1:00 · M2 y E6] «La familia llega al dispositivo. El operador busca el documento del responsable, ve la derivación y la acepta. El grupo declaró siete personas: se completa una ficha por cada una, con su cama en el mapa de plazas. Cuando las siete están confirmadas, la familia queda alojada y la bitácora lo registra.»
[1:24 · E4 y M3] «Del otro lado, la mesa arma las entregas de kits: alimentos, higiene, colchones. El dispositivo recibe el paquete, confirma las cantidades que llegaron y, si falta algo, la diferencia queda a la vista de la mesa.»
[1:40 · E1] «En el tablero, el Ministerio ve cuántas familias esperan, cuántas están alojadas, qué dispositivos tienen lugar y qué casos se pasaron del tiempo. Relevar, derivar, alojar y abastecer: todo en el mismo sistema que ya usan.»
[1:58 · cierre] Logo DATAÑACH · Emergencia.

Si no podés generar el audio, entregá el prototipo navegable con las transiciones en ese orden y el guion con los tiempos: la voz se graba aparte.
</entregable_B_video>

<verificacion>
Antes de entregar, confirmá en una lista corta: (1) las 10 pantallas existen con el nombre pedido; (2) ninguna usa colores, tipografía o íconos ajenos al mockup adjunto; (3) todo estado tiene texto además de color; (4) no hay datos reales; (5) el video dura 120 segundos o menos y cada frase del guion coincide con la pantalla indicada; (6) la lista «Piezas nuevas» está completa.
</verificacion>
```

🎯 Target: Claude Design. 💡 Se optimizó anclando cada pantalla a una pieza concreta del mockup adjunto y fijando el guion con tiempos, para que no invente ni el lenguaje visual ni el proceso.
