// ============================================================
// CHACO NODO — Tailwind CSS Config
// Extiende los defaults de Tailwind con los tokens del sistema
// Versión 1.0 — Generado desde Figma Variables
// ============================================================
// IMPORTANTE: Este archivo extiende Tailwind — no reemplaza.
// Las clases utilitarias del sistema de diseño usan el prefijo
// de los tokens (ej: bg-brand, text-fg-danger, border-base).
// ============================================================

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {

      // --------------------------------------------------------
      // FONT FAMILY
      // --------------------------------------------------------
      fontFamily: {
        sans: ['Manrope', 'sans-serif'],
        brand: ['Gellat', 'sans-serif'], // Solo para hero headings
      },

      // --------------------------------------------------------
      // FONT SIZE — valores exactos del sistema
      // --------------------------------------------------------
      fontSize: {
        'xxs': '8px',
        'xs':  '12px',
        'sm':  '14px',
        'base':'16px',
        'lg':  '18px',
        'xl':  '20px',
        '2xl': '24px',
        '3xl': '30px',
        '4xl': '36px',
        '5xl': '48px',
        '6xl': '60px',
        '7xl': '72px',
        '8xl': '96px',
        '9xl': '128px',
      },

      // --------------------------------------------------------
      // LETTER SPACING
      // --------------------------------------------------------
      letterSpacing: {
        tighter: '-0.8px',
        tight:   '-0.4px',
        normal:  '0px',
        wide:    '0.4px',
        wider:   '0.8px',
        widest:  '1.6px',
      },

      // --------------------------------------------------------
      // BORDER RADIUS
      // --------------------------------------------------------
      borderRadius: {
        '0':    '0px',
        'sm':   '2px',
        DEFAULT:'4px',
        'md':   '6px',
        'lg':   '8px',
        'xl':   '12px',
        '2xl':  '16px',
        '3xl':  '24px',
        'full': '9999px',
      },

      // --------------------------------------------------------
      // MAX WIDTH
      // --------------------------------------------------------
      maxWidth: {
        'xs':  '320px',
        'sm':  '384px',
        'md':  '448px',
        'lg':  '512px',
        'xl':  '576px',
        '2xl': '672px',
        '3xl': '768px',
        '4xl': '896px',
        '5xl': '1024px',
        '6xl': '1152px',
        '7xl': '1280px',
      },

      // --------------------------------------------------------
      // COLORS — paleta primitiva + tokens semánticos
      // Uso: bg-brand, text-fg-danger, border-base, etc.
      // ⚠️ No usar las escalas numéricas directamente en componentes.
      //    Usar siempre los tokens semánticos.
      // --------------------------------------------------------
      colors: {

        // --- Semantic tokens (light mode defaults via CSS vars) ---
        // Background
        'bg-white':             'var(--bg-white)',
        'bg-primary':           'var(--bg-primary)',
        'bg-primary-soft':      'var(--bg-primary-soft)',
        'bg-primary-medium':    'var(--bg-primary-medium)',
        'bg-primary-strong':    'var(--bg-primary-strong)',
        'bg-secondary':         'var(--bg-secondary)',
        'bg-secondary-soft':    'var(--bg-secondary-soft)',
        'bg-secondary-medium':  'var(--bg-secondary-medium)',
        'bg-secondary-strong':  'var(--bg-secondary-strong)',
        'bg-tertiary':          'var(--bg-tertiary)',
        'bg-tertiary-soft':     'var(--bg-tertiary-soft)',
        'bg-tertiary-medium':   'var(--bg-tertiary-medium)',
        'bg-quaternary':        'var(--bg-quaternary)',
        'bg-quaternary-medium': 'var(--bg-quaternary-medium)',
        'bg-gray':              'var(--bg-gray)',
        'bg-brand-softer':      'var(--bg-brand-softer)',
        'bg-brand-soft':        'var(--bg-brand-soft)',
        'bg-brand-medium':      'var(--bg-brand-medium)',
        'bg-brand':             'var(--bg-brand)',
        'bg-brand-strong':      'var(--bg-brand-strong)',
        'bg-success-soft':      'var(--bg-success-soft)',
        'bg-success-medium':    'var(--bg-success-medium)',
        'bg-success':           'var(--bg-success)',
        'bg-success-strong':    'var(--bg-success-strong)',
        'bg-danger-soft':       'var(--bg-danger-soft)',
        'bg-danger-medium':     'var(--bg-danger-medium)',
        'bg-danger':            'var(--bg-danger)',
        'bg-danger-strong':     'var(--bg-danger-strong)',
        'bg-warning-soft':      'var(--bg-warning-soft)',
        'bg-warning-medium':    'var(--bg-warning-medium)',
        'bg-warning':           'var(--bg-warning)',
        'bg-warning-strong':    'var(--bg-warning-strong)',
        'bg-dark':              'var(--bg-dark)',
        'bg-dark-strong':       'var(--bg-dark-strong)',
        'bg-disabled':          'var(--bg-disabled)',
        'bg-purple':            'var(--bg-purple)',
        'bg-sky':               'var(--bg-sky)',
        'bg-teal':              'var(--bg-teal)',
        'bg-pink':              'var(--bg-pink)',
        'bg-cyan':              'var(--bg-cyan)',
        'bg-fuchsia':           'var(--bg-fuchsia)',
        'bg-indigo':            'var(--bg-indigo)',
        'bg-orange':            'var(--bg-orange)',

        // Border
        'border-dark':           'var(--border-dark)',
        'border-buffer':         'var(--border-buffer)',
        'border-buffer-medium':  'var(--border-buffer-medium)',
        'border-buffer-strong':  'var(--border-buffer-strong)',
        'border-muted':          'var(--border-muted)',
        'border-light-subtle':   'var(--border-light-subtle)',
        'border-light':          'var(--border-light)',
        'border-light-medium':   'var(--border-light-medium)',
        'border-base-soft':      'var(--border-base-soft)',
        'border-base':           'var(--border-base)',
        'border-base-medium':    'var(--border-base-medium)',
        'border-base-strong':    'var(--border-base-strong)',
        'border-success-subtle': 'var(--border-success-subtle)',
        'border-success':        'var(--border-success)',
        'border-danger-subtle':  'var(--border-danger-subtle)',
        'border-danger':         'var(--border-danger)',
        'border-warning-subtle': 'var(--border-warning-subtle)',
        'border-warning':        'var(--border-warning)',
        'border-brand-subtle':   'var(--border-brand-subtle)',
        'border-brand-light':    'var(--border-brand-light)',
        'border-brand':          'var(--border-brand)',
        'border-dark-subtle':    'var(--border-dark-subtle)',
        'border-purple':         'var(--border-purple)',
        'border-orange':         'var(--border-orange)',

        // Text / Foreground
        'text-white':             'var(--text-white)',
        'text-black':             'var(--text-black)',
        'text-heading':           'var(--text-heading)',
        'text-body':              'var(--text-body)',
        'text-body-subtle':       'var(--text-body-subtle)',
        'text-fg-brand-subtle':   'var(--text-fg-brand-subtle)',
        'text-fg-brand':          'var(--text-fg-brand)',
        'text-fg-brand-strong':   'var(--text-fg-brand-strong)',
        'text-fg-success':        'var(--text-fg-success)',
        'text-fg-success-strong': 'var(--text-fg-success-strong)',
        'text-fg-danger':         'var(--text-fg-danger)',
        'text-fg-danger-strong':  'var(--text-fg-danger-strong)',
        'text-fg-warning-subtle': 'var(--text-fg-warning-subtle)',
        'text-fg-warning':        'var(--text-fg-warning)',
        'text-fg-yellow':         'var(--text-fg-yellow)',
        'text-fg-info':           'var(--text-fg-info)',
        'text-fg-disabled':       'var(--text-fg-disabled)',
        'text-fg-purple':         'var(--text-fg-purple)',
        'text-fg-cyan':           'var(--text-fg-cyan)',
        'text-fg-indigo':         'var(--text-fg-indigo)',
        'text-fg-pink':           'var(--text-fg-pink)',
        'text-fg-lime':           'var(--text-fg-lime)',
      },
    },
  },
  plugins: [],
}
