// Las apps del repo, enumeradas a propósito. Cualquier comodín de primer nivel
// (`./**/…`, `./*/…`) alcanza un virtualenv o un `node_modules` que viven adentro
// del checkout, y entonces el CSS depende de qué tenga instalado el que corre el
// build. La lista se verifica contra el disco en
// `core.tests.test_design_audit_estructura.ContentDeTailwindTests`.
const APPS = '{configuracion,conversaciones,core,dashboard,healthcheck,legajos,notificaciones,portal,programas,users}'

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ['class', '[data-theme="dark"]'],
  // Todo lo que puede nombrar una clase tiene que estar acá: lo que el escáner no
  // ve, no se genera, y la pantalla se ve mal sin que falle nada. Y nada más que
  // eso: lo que entra de más hace que el CSS dependa de la máquina que buildea.
  //
  // Dos reglas, las dos a propósito:
  //
  // 1. **Nada de comodines de primer nivel**: todo sale de `APPS`. El
  //    `./**/templates/**/*.html` anterior alcanzaba los templates de Django admin
  //    adentro de un virtualenv del checkout y `node_modules/<pkg>/templates/`, así
  //    que un build hecho con el entorno presente generaba clases que el runner del
  //    CI no genera: el CSS salía distinto según dónde se buildeara y el gate
  //    obligatorio lo rechazaba. (Con `.venv` no llegaba a pasar porque fast-glob no
  //    entra a directorios que empiezan con punto; con `venv/` o `env/`, sí. Las dos
  //    variantes están medidas en el PR.)
  //
  // 2. **Los `.py` se listan por dónde viven, no con `./**/*.py`.** Entran porque
  //    buena parte de los campos del backoffice traen sus clases desde el widget
  //    del form y no desde el template (`programas/forms.py`, el wizard de
  //    `configuracion`, el input de archivo del legajo); sin ellos el build borraba
  //    `focus:ring-1` y `cursor-not-allowed`, en uso. Barrerlos todos tiene un costo
  //    que no se ve: el extractor de Tailwind es una regex sobre el texto crudo, así
  //    que un slice de Python (`connection.queries[desde:hasta]`) le parece una
  //    utilidad de valor arbitrario y termina como regla basura en el CSS — con el
  //    agravante de que entonces un PR que no toca UI mueve `tailwind.css` y hace
  //    fallar el gate. Medido: barrer todo agregaba `[queries_before:queries_after]`
  //    y `capitalize`, ninguna de las dos usada como clase.
  //
  // Que esta lista quede corta no es silencioso:
  // `core.tests.test_design_audit_estructura.CssCompiladoAlDiaTests` recorre **todos**
  // los `.py` de las apps con `ast` (inmune a la basura de la regex) y se pone rojo si
  // una clase usada desde Python no está en el CSS compilado.
  content: [
    './templates/**/*.html',
    // Las apps del repo tienen sus templates en `<app>/templates/`.
    `./${APPS}/templates/**/*.html`,
    './static/custom/js/**/*.js',
    // Los `.py` que arman clases (ver regla 2).
    `./${APPS}/forms.py`,
    `./${APPS}/{forms,models,templatetags}/**/*.py`,
    // Nunca: los tests, que afirman sobre clases a propósito mal escritas
    // (`bg-gray-200` en los casos negativos de CLASSDEF). Generarlas desarmaría
    // justo la regla que las detecta.
    '!./**/tests/**',
    '!./**/test_*.py',
    // Nunca: migraciones. No tienen markup y son miles de archivos.
    '!./**/migrations/**',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Manrope', 'sans-serif'],
        brand: ['Manrope', 'sans-serif'],
      },
      fontSize: {
        xs: '12px', sm: '14px', base: '16px',
        lg: '18px', xl: '20px', '2xl': '24px', '3xl': '30px',
        '4xl': '36px', '5xl': '48px', '6xl': '60px',
      },
      borderRadius: {
        0: '0px', sm: '2px', DEFAULT: '4px', md: '6px',
        lg: '8px', xl: '12px', '2xl': '16px', '3xl': '24px', full: '9999px',
      },
      maxWidth: {
        xs: '320px', sm: '384px', md: '448px', lg: '512px',
        xl: '576px', '2xl': '672px', '3xl': '768px', '4xl': '896px',
        '5xl': '1024px', '6xl': '1152px', '7xl': '1280px',
      },
      colors: {
        magenta: 'var(--bg-pink)',
        'nodo-purple': 'var(--bg-brand)',
        'nodo-cyan': 'var(--bg-teal)',
        primario: 'var(--color-navy-900)',
        'primario-claro': 'var(--bg-brand)',
        'primario-oscuro': 'var(--color-navy-900)',
        secundario: 'var(--bg-brand)',
        'secundario-claro': 'var(--bg-teal)',
        'secundario-oscuro': 'var(--color-navy-900)',
        acento: 'var(--bg-pink)',
        'acento-claro': 'var(--bg-teal)',
        'acento-oscuro': 'var(--bg-olive)',
        primary: 'var(--color-navy-900)',
        secondary: 'var(--bg-brand)',
      },
      backgroundColor: {
        white: 'var(--bg-white)',
        'primary-soft': 'var(--bg-primary-soft)',
        secondary: 'var(--bg-secondary)',
        'secondary-soft': 'var(--bg-secondary-soft)',
        tertiary: 'var(--bg-tertiary)',
        quaternary: 'var(--bg-quaternary)',
        gray: 'var(--bg-gray)',
        brand: 'var(--bg-brand)',
        'brand-soft': 'var(--bg-brand-soft)',
        'brand-softer': 'var(--bg-brand-softer)',
        'brand-medium': 'var(--bg-brand-medium)',
        'brand-strong': 'var(--bg-brand-strong)',
        success: 'var(--bg-success)',
        'success-soft': 'var(--bg-success-soft)',
        danger: 'var(--bg-danger)',
        'danger-soft': 'var(--bg-danger-soft)',
        'danger-medium': 'var(--bg-danger-medium)',
        warning: 'var(--bg-warning)',
        'warning-soft': 'var(--bg-warning-soft)',
        'info-soft': 'var(--bg-info-soft)',
        dark: 'var(--bg-dark)',
        disabled: 'var(--bg-disabled)',
        pink: 'var(--bg-pink)',
      },
      textColor: {
        white: 'var(--text-white)',
        heading: 'var(--text-heading)',
        body: 'var(--text-body)',
        'body-subtle': 'var(--text-body-subtle)',
        'fg-brand': 'var(--text-fg-brand)',
        'fg-brand-subtle': 'var(--text-fg-brand-subtle)',
        'fg-brand-strong': 'var(--text-fg-brand-strong)',
        'fg-danger': 'var(--text-fg-danger)',
        'fg-danger-strong': 'var(--text-fg-danger-strong)',
        'fg-success': 'var(--text-fg-success)',
        'fg-warning': 'var(--text-fg-warning)',
        'fg-warning-subtle': 'var(--text-fg-warning-subtle)',
        'fg-disabled': 'var(--text-fg-disabled)',
        'fg-info': 'var(--text-fg-info)',
        pink: 'var(--text-fg-pink)',
      },
      borderColor: {
        base: 'var(--border-base)',
        'base-soft': 'var(--border-base-soft)',
        light: 'var(--border-light)',
        brand: 'var(--border-brand)',
        'brand-subtle': 'var(--border-brand-subtle)',
        'brand-light': 'var(--border-brand-light)',
        danger: 'var(--border-danger)',
        'danger-subtle': 'var(--border-danger-subtle)',
        success: 'var(--border-success)',
        'success-subtle': 'var(--border-success-subtle)',
        warning: 'var(--border-warning)',
        'warning-subtle': 'var(--border-warning-subtle)',
      },
    },
  },
  plugins: [],
};
