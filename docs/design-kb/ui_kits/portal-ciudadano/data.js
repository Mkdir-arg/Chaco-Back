// Mock data for the Portal Ciudadano UI kit (all fictional).
window.PORTAL = {
  contact: { phone: '0800-222-1133', email: 'ayuda@chaco.gob.ar' },
  ciudadano: { name: 'Juan Carlos Romero', dni: '30.118.902' },
  programas: [
    { id: 'alimentar', nombre: 'Tarjeta Alimentar', icon: 'fas fa-cart-shopping', desc: 'Asistencia para la compra de alimentos de la canasta básica familiar.', tone: 'brand' },
    { id: 'progresar', nombre: 'Becas Progresar', icon: 'fas fa-graduation-cap', desc: 'Apoyo económico para estudiantes que continúan sus estudios.', tone: 'olive' },
    { id: 'potenciar', nombre: 'Potenciar Trabajo', icon: 'fas fa-briefcase', desc: 'Acompañamiento para la inclusión socioproductiva y el empleo.', tone: 'pink' },
    { id: 'salud', nombre: 'Salud Comunitaria', icon: 'fas fa-heart-pulse', desc: 'Turnos, libreta sanitaria y campañas de salud en tu localidad.', tone: 'brand' },
  ],
  misProgramas: [
    { nombre: 'Tarjeta Alimentar', estado: 'activo', detalle: 'Cobro mensual al día · próximo: 10/07' },
    { nombre: 'Becas Progresar', estado: 'revision', detalle: 'Documentación en evaluación' },
  ],
  misConsultas: [
    { id: 4821, asunto: 'Solicitud de turno — Tarjeta Alimentar', estado: 'pendiente', fecha: 'Hoy, 10:24' },
    { id: 4720, asunto: 'Actualización de domicilio', estado: 'activo', fecha: '02/06/2026' },
    { id: 4610, asunto: 'Consulta por estado de beca', estado: 'cerrado', fecha: '21/05/2026' },
  ],
  estados: {
    activo:    { label: 'Activo', variant: 'success', dot: true },
    revision:  { label: 'En revisión', variant: 'info' },
    pendiente: { label: 'Pendiente', variant: 'warning' },
    cerrado:   { label: 'Resuelto', variant: 'neutral' },
  },
};
