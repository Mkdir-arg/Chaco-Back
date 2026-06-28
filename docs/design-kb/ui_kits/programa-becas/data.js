// Programa Becas — mock domain data (fictional). Chaco / NODO backoffice.
// Domain: Segmento → Subsegmento → Convocatoria → Relevamiento → Formulario.
window.BECAS = {
  user: { name: 'María González', role: 'Coordinadora — Nivel Superior' },

  // Relevamiento workflow states (canonical)
  relevEstados: {
    ASIGNADO:    { label: 'Asignado',     variant: 'gray' },
    EN_CURSO:    { label: 'En curso',     variant: 'warning' },
    FINALIZANDO: { label: 'Finalizando',  variant: 'warning' },
    FINALIZADO:  { label: 'Finalizado',   variant: 'brand' },
    EN_REVISION: { label: 'En revisión',  variant: 'brand' },
    TERMINADO:   { label: 'Terminado',    variant: 'success' },
    VENCIDO:     { label: 'Vencido',      variant: 'danger' },
  },

  // Tipos de campo de un requisito (parametría)
  tiposRequisito: ['STRING', 'INT', 'SELECTOR', 'SELECTOR_MULTIPLE', 'DATE', 'ARCHIVO', 'GPS'],

  // Modelo: Segmento { cupoTotal, coordinador, requisitos[], subsegmentos[ { cupoMax, ocupado, requisitos[] } ] }
  // cupoOcupado del segmento = Σ subsegmentos.ocupado · disponible del subsegmento = cupoMax − ocupado
  segmentos: [
    { id: 1, nombre: 'Producción Territorial / Fuego y Barro', desc: 'Productores de ladrillo y carbón vegetal del territorio provincial.',
      cupoTotal: 500, coordinador: 'Laura Méndez', estado: 'activo',
      requisitos: [
        { id: 11, pregunta: '¿Lugar de trabajo / producción?', tipo: 'STRING', obligatorio: true, orden: 1 },
        { id: 12, pregunta: 'Fotos del lugar', tipo: 'ARCHIVO', obligatorio: true, orden: 2 },
        { id: 13, pregunta: 'Ubicación GPS del predio', tipo: 'GPS', obligatorio: true, orden: 3 },
      ],
      subsegmentos: [
        { id: 101, nombre: 'Ladrillo', desc: 'Producción de ladrillos artesanales.', cupoMax: 200, ocupado: 50,
          requisitos: [
            { id: 1101, pregunta: 'Cantidad de hornos', tipo: 'INT', obligatorio: true, orden: 1 },
            { id: 1102, pregunta: 'Tipo de horno', tipo: 'SELECTOR', obligatorio: false, orden: 2 },
          ] },
        { id: 102, nombre: 'Carbón', desc: 'Producción de carbón vegetal.', cupoMax: 300, ocupado: 100,
          requisitos: [
            { id: 1201, pregunta: 'Método de producción', tipo: 'SELECTOR', obligatorio: true, orden: 1 },
          ] },
      ] },
    { id: 2, nombre: 'Nivel Superior', desc: 'Terciario y universitario, instituciones públicas y privadas.',
      cupoTotal: 1500, coordinador: 'María González', estado: 'activo',
      requisitos: [
        { id: 21, pregunta: 'Certificado de alumno regular', tipo: 'ARCHIVO', obligatorio: true, orden: 1 },
        { id: 22, pregunta: 'Promedio del último período', tipo: 'INT', obligatorio: true, orden: 2 },
        { id: 23, pregunta: 'Institución educativa', tipo: 'STRING', obligatorio: true, orden: 3 },
      ],
      subsegmentos: [
        { id: 201, nombre: 'Terciario', desc: 'Institutos de formación terciaria.', cupoMax: 700, ocupado: 512, requisitos: [] },
        { id: 202, nombre: 'Universitario', desc: 'Carreras de grado universitarias.', cupoMax: 800, ocupado: 700,
          requisitos: [{ id: 2201, pregunta: 'Carrera / Especialidad', tipo: 'STRING', obligatorio: true, orden: 1 }] },
      ] },
    { id: 3, nombre: 'Nivel Secundario', desc: 'Estudiantes de escuelas secundarias de la provincia.',
      cupoTotal: 2000, coordinador: 'Laura Méndez', estado: 'activo',
      requisitos: [{ id: 31, pregunta: 'Constancia de inscripción', tipo: 'ARCHIVO', obligatorio: true, orden: 1 }],
      subsegmentos: [
        { id: 301, nombre: 'Ciclo Básico', desc: '1º a 3º año.', cupoMax: 1000, ocupado: 820, requisitos: [] },
        { id: 302, nombre: 'Ciclo Orientado', desc: '4º a 6º año.', cupoMax: 1000, ocupado: 980, requisitos: [] },
      ] },
    { id: 4, nombre: 'Posgrado e Investigación', desc: 'Maestrías, doctorados y proyectos de investigación.',
      cupoTotal: 120, coordinador: 'Diego Ferreyra', estado: 'inactivo',
      requisitos: [], subsegmentos: [] },
  ],

  coordinadores: [
    { nombre: 'María González', segmentos: ['Nivel Superior'], legajos: 1212 },
    { nombre: 'Laura Méndez', segmentos: ['Nivel Secundario'], legajos: 1840 },
    { nombre: 'Diego Ferreyra', segmentos: ['Nivel Superior', 'Posgrado e Investigación'], legajos: 1308 },
    { nombre: 'Sofía Aguirre', segmentos: ['Formación Profesional'], legajos: 530 },
  ],

  // Requisitos nativos (per segmento/subsegmento) — build the territorial's dynamic form
  requisitos: [
    { id: 1, nombre: 'Certificado de alumno regular', tipo: 'Archivo', segmento: 'Nivel Superior', obligatorio: true },
    { id: 2, nombre: 'Promedio del último período', tipo: 'Número', segmento: 'Nivel Superior', obligatorio: true },
    { id: 3, nombre: 'Institución educativa', tipo: 'Texto', segmento: 'Nivel Superior', obligatorio: true },
    { id: 4, nombre: 'Carrera / Especialidad', tipo: 'Texto', segmento: 'Nivel Superior', obligatorio: true },
    { id: 5, nombre: 'Año que cursa', tipo: 'Selección', segmento: 'Nivel Superior', obligatorio: true },
    { id: 6, nombre: '¿Percibe otra beca?', tipo: 'Sí / No', segmento: 'Nivel Superior', obligatorio: false },
    { id: 7, nombre: 'Constancia de CBU', tipo: 'Archivo', segmento: 'Nivel Superior', obligatorio: true },
  ],

  // 13 preguntas globales del programa (se muestran informativas en la convocatoria)
  requisitosGenerales: [
    'Apellido y nombre', 'DNI', 'Fecha de nacimiento', 'Sexo', 'Domicilio',
    'Localidad', 'Teléfono de contacto', 'Correo electrónico', 'Estado civil',
    'Composición del grupo familiar', 'Situación habitacional', 'Ingreso mensual del hogar', 'Cobertura de salud',
  ],

  // Usuarios con rol Territorial
  territoriales: ['Juan Pérez', 'María López', 'Carlos Gómez', 'Paula Vega', 'Marta Ojeda'],

  // Convocatorias — segmento/subsegmento por id; cupo se toma del subsegmento si tiene, si no del segmento.
  convocatorias: [
    { id: 1, nombre: 'Convocatoria Becas 2026 — Carbón', desc: 'Relevamiento de productores de carbón vegetal del territorio.',
      segmentoId: 1, subsegmentoId: 102, desde: '01/03/2026', hasta: '30/04/2026',
      estado: 'activa', creada: '12/02/2026', creadoPor: 'Admin — D. Ferreyra',
      relevamientos: [
        { id: 1, nombre: 'Relevamiento 001', territorial: 'Juan Pérez', zona: 'Resistencia - Zona Norte', plazo: '15/03/2026', estado: 'ASIGNADO', formularios: 0 },
        { id: 2, nombre: 'Relevamiento 002', territorial: 'María López', zona: 'Pcia. Roque Sáenz Peña', plazo: '20/03/2026', estado: 'EN_CURSO', formularios: 12 },
        { id: 3, nombre: 'Relevamiento 003', territorial: 'Carlos Gómez', zona: 'Villa Ángela', plazo: '18/03/2026', estado: 'FINALIZADO', formularios: 25 },
        { id: 4, nombre: 'Relevamiento 004', territorial: 'Paula Vega', zona: 'Charata', plazo: '22/03/2026', estado: 'EN_REVISION', formularios: 18 },
      ],
      beneficiarios: [
        { dni: '12.345.678', nombre: 'Juan Pérez', estado: 'cupo', fecha: '20/03/2026' },
        { dni: '87.654.321', nombre: 'María López', estado: 'espera', fecha: '22/03/2026' },
        { dni: '33.221.998', nombre: 'Ramón Acosta', estado: 'cupo', fecha: '21/03/2026' },
        { dni: '40.552.117', nombre: 'Lucía Sosa', estado: 'rechazado', fecha: '23/03/2026' },
      ] },
    { id: 2, nombre: 'Becas Superior 2026 — Universitario', desc: 'Becas para estudiantes universitarios de grado.',
      segmentoId: 2, subsegmentoId: 202, desde: '01/03/2026', hasta: '15/05/2026',
      estado: 'activa', creada: '10/02/2026', creadoPor: 'Admin — M. González',
      relevamientos: [
        { id: 1, nombre: 'Relevamiento 001', territorial: 'Paula Vega', zona: 'Resistencia - Centro', plazo: '12/03/2026', estado: 'EN_CURSO', formularios: 30 },
        { id: 2, nombre: 'Relevamiento 002', territorial: 'Marta Ojeda', zona: 'Barranqueras', plazo: '14/03/2026', estado: 'TERMINADO', formularios: 41 },
      ],
      beneficiarios: [
        { dni: '45.880.214', nombre: 'Acosta, Brenda Sofía', estado: 'cupo', fecha: '15/03/2026' },
        { dni: '46.112.907', nombre: 'Benítez, Tomás', estado: 'espera', fecha: '16/03/2026' },
      ] },
    { id: 3, nombre: 'Convocatoria Becas 2026 — Ladrillo', desc: 'Relevamiento de productores de ladrillo artesanal.',
      segmentoId: 1, subsegmentoId: 101, desde: '01/04/2026', hasta: '20/05/2026',
      estado: 'inactiva', creada: '05/03/2026', creadoPor: 'Admin — D. Ferreyra',
      relevamientos: [], beneficiarios: [] },
    { id: 4, nombre: 'Becas Secundario 2025', desc: 'Convocatoria del ciclo lectivo anterior.',
      segmentoId: 3, subsegmentoId: 302, desde: '15/02/2025', hasta: '15/03/2025',
      estado: 'finalizada', creada: '20/01/2025', creadoPor: 'Admin — L. Méndez',
      relevamientos: [
        { id: 1, nombre: 'Relevamiento 001', territorial: 'Carlos Gómez', zona: 'Sáenz Peña', plazo: '01/03/2025', estado: 'TERMINADO', formularios: 60 },
      ],
      beneficiarios: [] },
  ],
  convEstados: {
    activa:     { label: 'Activa',     variant: 'success', dot: true },
    inactiva:   { label: 'Inactiva',   variant: 'gray' },
    finalizada: { label: 'Finalizada', variant: 'brand' },
  },
  benefEstados: {
    cupo:      { label: 'Con cupo',           variant: 'success', dot: true },
    espera:    { label: 'En lista de espera', variant: 'warning' },
    rechazado: { label: 'Validado-Rechazado', variant: 'danger' },
  },

  // Estado del formulario / persona relevada (dentro de un operativo)
  personaEstados: {
    PENDIENTE:     { label: 'Pendiente',      variant: 'warning' },
    APROBADO:      { label: 'Aprobado',       variant: 'success', dot: true },
    RECHAZADO:     { label: 'Rechazado',      variant: 'danger' },
    VALIDADO_SIS:  { label: 'Validado SIS',   variant: 'success', dot: true },
    RECHAZADO_SIS: { label: 'Rechazado SIS',  variant: 'danger' },
  },
  renaperRes: {
    validado:     { label: 'Validado',     variant: 'success', icon: 'checkCircle' },
    no_validado:  { label: 'No validado',  variant: 'danger',  icon: 'xCircle' },
    pendiente:    { label: 'Pendiente',    variant: 'warning', icon: 'clock' },
  },
  sisRes: {
    oka:        { label: 'OKA',        variant: 'success', icon: 'checkCircle' },
    rechazado:  { label: 'Rechazado',  variant: 'danger',  icon: 'xCircle' },
    pendiente:  { label: 'Pendiente',  variant: 'warning', icon: 'clock' },
  },

  // OPERATIVOS de relevamiento. Las personas relevadas viven DENTRO de cada operativo.
  relevamientos: [
    { id: 1, nombre: 'Relevamiento 001', convocatoria: 'Convocatoria Becas 2026 — Carbón', segmento: 'Producción Territorial', subsegmento: 'Carbón',
      territorial: 'Juan Pérez', zona: 'Resistencia - Zona Norte', fecha: '15/03/2026', estado: 'EN_CURSO', observaciones: 'Acceso por camino vecinal; coordinar con referente local.',
      personas: [
        { dni: '12.345.678', nombre: 'Juan Pérez', fechaCarga: '12/03/2026', estado: 'APROBADO', renaper: 'validado', sis: 'oka' },
        { dni: '23.456.789', nombre: 'Marta Giménez', fechaCarga: '12/03/2026', estado: 'PENDIENTE', renaper: 'validado', sis: 'pendiente' },
        { dni: '34.567.890', nombre: 'Ramón Acosta', fechaCarga: '13/03/2026', estado: 'VALIDADO_SIS', renaper: 'validado', sis: 'oka' },
        { dni: '45.678.901', nombre: 'Lucía Sosa', fechaCarga: '13/03/2026', estado: 'RECHAZADO_SIS', renaper: 'validado', sis: 'rechazado' },
        { dni: '56.789.012', nombre: 'Pedro Maidana', fechaCarga: '14/03/2026', estado: 'RECHAZADO', renaper: 'no_validado', sis: 'pendiente' },
      ] },
    { id: 2, nombre: 'Relevamiento 002', convocatoria: 'Convocatoria Becas 2026 — Carbón', segmento: 'Producción Territorial', subsegmento: 'Carbón',
      territorial: 'María López', zona: 'Pcia. Roque Sáenz Peña', fecha: '20/03/2026', estado: 'ASIGNADO', observaciones: '',
      personas: [] },
    { id: 3, nombre: 'Relevamiento 003', convocatoria: 'Convocatoria Becas 2026 — Carbón', segmento: 'Producción Territorial', subsegmento: 'Carbón',
      territorial: 'Carlos Gómez', zona: 'Villa Ángela', fecha: '18/03/2026', estado: 'EN_REVISION', observaciones: 'Operativo conjunto con Desarrollo Social.',
      personas: [
        { dni: '67.890.123', nombre: 'Ana Benítez', fechaCarga: '16/03/2026', estado: 'PENDIENTE', renaper: 'validado', sis: 'pendiente' },
        { dni: '78.901.234', nombre: 'Diego Cabrera', fechaCarga: '16/03/2026', estado: 'APROBADO', renaper: 'validado', sis: 'oka' },
        { dni: '89.012.345', nombre: 'Sofía Ledesma', fechaCarga: '17/03/2026', estado: 'PENDIENTE', renaper: 'pendiente', sis: 'pendiente' },
      ] },
    { id: 4, nombre: 'Relevamiento 004', convocatoria: 'Becas Superior 2026 — Universitario', segmento: 'Nivel Superior', subsegmento: 'Universitario',
      territorial: 'Paula Vega', zona: 'Resistencia - Centro', fecha: '12/03/2026', estado: 'TERMINADO', observaciones: '',
      personas: [
        { dni: '45.880.214', nombre: 'Acosta, Brenda Sofía', fechaCarga: '10/03/2026', estado: 'APROBADO', renaper: 'validado', sis: 'oka' },
        { dni: '46.112.907', nombre: 'Benítez, Tomás', fechaCarga: '10/03/2026', estado: 'VALIDADO_SIS', renaper: 'validado', sis: 'oka' },
      ] },
    { id: 5, nombre: 'Relevamiento 005', convocatoria: 'Convocatoria Becas 2026 — Ladrillo', segmento: 'Producción Territorial', subsegmento: 'Ladrillo',
      territorial: 'Marta Ojeda', zona: 'Charata', fecha: '08/03/2026', estado: 'VENCIDO', observaciones: 'Sin avances; reprogramar.',
      personas: [] },
  ],

  // Form under review (caso a caso)
  formulario: {
    ciudadano: 'Acosta, Brenda Sofía', dni: '45.880.214', edad: 19,
    convocatoria: 'Becas Superior 2026 — 1er cuatrimestre', segmento: 'Nivel Superior · Universitario',
    territorial: 'Carlos Ruiz', presentado: '18/06/2026',
    social: [
      { p: 'Composición del grupo familiar', r: '4 integrantes (madre, 2 hermanos menores)' },
      { p: 'Ingreso mensual del hogar', r: '$ 410.000' },
      { p: 'Situación habitacional', r: 'Vivienda alquilada' },
      { p: 'Cobertura de salud', r: 'Hospital público' },
      { p: '¿Trabaja actualmente?', r: 'No' },
    ],
    requisitos: [
      { nombre: 'Certificado de alumno regular', tipo: 'Archivo', valor: 'cert-regular.pdf', ok: true },
      { nombre: 'Promedio del último período', tipo: 'Número', valor: '8,40', ok: true },
      { nombre: 'Institución educativa', tipo: 'Texto', valor: 'UNNE — Facultad de Medicina', ok: true },
      { nombre: 'Carrera / Especialidad', tipo: 'Texto', valor: 'Medicina', ok: true },
      { nombre: 'Año que cursa', tipo: 'Selección', valor: '2º año', ok: true },
      { nombre: 'Constancia de CBU', tipo: 'Archivo', valor: '— sin adjuntar —', ok: false },
    ],
    historial: [
      { quien: 'Carlos Ruiz (Territorial)', accion: 'Presentó el formulario', cuando: '18/06 · 09:12' },
      { quien: 'Sistema', accion: 'Validación RENAPER correcta', cuando: '18/06 · 09:12' },
      { quien: 'María González (Coordinadora)', accion: 'Tomó el caso para revisión', cuando: '18/06 · 11:40' },
    ],
  },

  // Cupo y lista de espera
  espera: [
    { id: 7701, ciudadano: 'Gómez, Valentina', dni: '47.553.901', convocatoria: 'Becas Superior 2026 — 1er cuatr.', desde: '12/06/2026', prioridad: 'Alta' },
    { id: 7702, ciudadano: 'Herrera, Nicolás', dni: '46.220.114', convocatoria: 'Becas Superior 2026 — 1er cuatr.', desde: '12/06/2026', prioridad: 'Media' },
    { id: 7703, ciudadano: 'Ibáñez, Camila', dni: '48.001.226', convocatoria: 'Becas Superior 2026 — 1er cuatr.', desde: '13/06/2026', prioridad: 'Media' },
    { id: 7704, ciudadano: 'Juárez, Lautaro', dni: '47.889.330', convocatoria: 'Becas Superior 2026 — 1er cuatr.', desde: '14/06/2026', prioridad: 'Baja' },
  ],
  prioridades: { Alta: 'danger', Media: 'warning', Baja: 'gray' },

  // Formularios cargados dentro de un relevamiento (lista caso a caso)
  formEstados: {
    BORRADOR:    { label: 'Borrador',     variant: 'gray' },
    PRESENTADO:  { label: 'Presentado',   variant: 'warning' },
    EN_REVISION: { label: 'En revisión',  variant: 'brand' },
    APROBADO:    { label: 'Aprobado',     variant: 'success', dot: true },
    RECHAZADO:   { label: 'Rechazado',    variant: 'danger' },
  },
  formularios: [
    { id: 9001, ciudadano: 'Acosta, Brenda Sofía', dni: '45.880.214', renaper: 'ok', estado: 'EN_REVISION', completo: 92, presentado: '18/06/2026' },
    { id: 9002, ciudadano: 'Benítez, Tomás', dni: '46.112.907', renaper: 'ok', estado: 'PRESENTADO', completo: 100, presentado: '18/06/2026' },
    { id: 9003, ciudadano: 'Coronel, Ailén', dni: '44.503.118', renaper: 'pendiente', estado: 'BORRADOR', completo: 60, presentado: '—' },
    { id: 9004, ciudadano: 'Duarte, Mateo', dni: '47.220.661', renaper: 'ok', estado: 'APROBADO', completo: 100, presentado: '15/06/2026' },
    { id: 9005, ciudadano: 'Escobar, Lucía', dni: '45.009.473', renaper: 'observado', estado: 'RECHAZADO', completo: 80, presentado: '14/06/2026' },
  ],
  renaperEstados: {
    ok:        { label: 'RENAPER validado', variant: 'success', icon: 'checkCircle' },
    pendiente: { label: 'RENAPER pendiente', variant: 'warning', icon: 'clock' },
    observado: { label: 'RENAPER observado', variant: 'danger', icon: 'exclamationCircle' },
  },
};
