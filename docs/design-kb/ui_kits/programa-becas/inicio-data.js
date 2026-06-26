// /inicio/ — datos mock del panel de inicio (ficticios). Chaco / NODO backoffice.
window.INICIO = {
  user: { name: 'María González', role: 'Coordinadora — Nivel Superior' },
  saludo: 'Buenas tardes',
  stats: [
    { label: 'Legajos activos', value: '1.284', icon: 'folderOpen', tone: 'brand', gradient: true, change: '8%', dir: 'up', foot: 'vs. mes anterior' },
    { label: 'Relevamientos en curso', value: '37', icon: 'clipboardList', tone: 'warning', change: '5', dir: 'up', foot: '6 sin asignar' },
    { label: 'Formularios por revisar', value: '24', icon: 'clipboardCheck', tone: 'brand', change: '3', dir: 'down', foot: 'pendientes hoy' },
    { label: 'Beneficiarios con cupo', value: '9.512', icon: 'usersGroup', tone: 'success', change: '12%', dir: 'up', foot: 'en el trimestre' },
  ],
  accesos: [
    { label: 'Nuevo legajo', icon: 'identification', tone: 'brand' },
    { label: 'Nueva convocatoria', icon: 'megaphone', tone: 'olive' },
    { label: 'Asignar relevamiento', icon: 'folderOpen', tone: 'pink' },
    { label: 'Revisar formularios', icon: 'clipboardCheck', tone: 'brand' },
  ],
  pendientes: [
    { titulo: 'Formularios en revisión', desc: 'Becas Superior 2026 — Universitario', n: 18, tone: 'brand', icon: 'clipboardCheck' },
    { titulo: 'Relevamientos vencidos', desc: 'Requieren reprogramación', n: 2, tone: 'danger', icon: 'clock' },
    { titulo: 'RENAPER pendiente', desc: 'Validaciones sin resolver', n: 7, tone: 'warning', icon: 'exclamationCircle' },
    { titulo: 'Lista de espera', desc: 'Producción Territorial / Carbón', n: 64, tone: 'olive', icon: 'usersGroup' },
  ],
  actividad: [
    { icon: 'pencilSquare', text: 'Actualizaste la dimensión Vivienda del legajo #1284', time: 'hace 20 min', tone: 'brand' },
    { icon: 'checkCircle', text: 'Aprobaste el formulario de Acosta, Brenda Sofía', time: 'hace 1 h', tone: 'success' },
    { icon: 'folderOpen', text: 'Se creó el Relevamiento 005 — Charata', time: 'hace 3 h', tone: 'olive' },
    { icon: 'xCircle', text: 'Rechazaste el formulario de Maidana, Pedro', time: 'hace 5 h', tone: 'danger' },
    { icon: 'megaphone', text: 'Se abrió la convocatoria Becas 2026 — Carbón', time: 'ayer', tone: 'brand' },
  ],
  agenda: [
    { hora: '09:30', titulo: 'Operativo Resistencia - Zona Norte', sub: 'Territorial: Juan Pérez', estado: 'En curso', tone: 'warning' },
    { hora: '11:00', titulo: 'Revisión de cupo — Nivel Superior', sub: 'Coordinación', estado: 'Hoy', tone: 'brand' },
    { hora: '14:00', titulo: 'Cierre convocatoria Secundario', sub: 'Vence en 3 días', estado: 'Próximo', tone: 'gray' },
  ],
  cobertura: [
    ['Tarjeta Alimentar', 46, 'var(--bg-brand)'],
    ['Producción Territorial', 28, 'var(--color-olive-500)'],
    ['Becas Superior', 18, 'var(--bg-pink)'],
    ['Otros', 8, 'var(--bg-quaternary)'],
  ],
};
