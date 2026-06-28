# Referencia — repo `Mkdir-arg/Chaco`

Material traído del repositorio real para usar como **referencia** al diseñar.
El repo es la fuente de verdad de *cómo funciona* el sistema; el diseño de este
proyecto es lo que se va a implementar. Esta carpeta NO es parte del entregable.

## Qué hay acá
- `branding.py` — fuente de verdad del branding en el código (perfil activo: `chaco`).
  Genera las CSS variables `--color-*`, `--nodo-*`, gradientes y estados de botón.
- `design-kb/` — base de conocimiento de diseño (principios, anti-patrones, specs
  de componentes en `.yaml`, patrones de pantalla en `patterns/`, foundations).

## El repo en una mirada (Django 4.2 · MySQL · Tailwind + Alpine)
Apps de dominio y sus pantallas (templates) reales:

| App | Pantallas clave (templates) |
|---|---|
| `legajos` | listado de ciudadanos/legajos, alta (stepper RENAPER), detalle (dimensiones, grupo familiar, alertas, archivos) |
| `programas` + `configuracion` | ABM de programas, **wizard de alta en 4 pasos**, detalle NACHEC (becas) |
| `dashboard` | `dashboard.html` — greeting card, métricas, gráfico de estados de legajo, tendencia, timeline |
| `portal` | Portal Ñandé (ciudadano): home, login, registro 2 pasos, mi perfil, mis programas, consultas |
| `conversaciones` | bandeja de chat, detalle, métricas, configurar cola, chat ciudadano |
| `users` | login, ABM de usuarios y roles (RBAC) |

Templates base: backoffice extiende `templates/includes/base.html`; portal extiende
`portal/templates/portal/base.html`. Componentes compartidos en `templates/components/`.

## Marca real (perfil `chaco` en branding.py)
- Jacarandá (primario claro / gradiente inicio): `#5059BC`
- Rosa / magenta (acento, gradiente fin): **`#F26DF9`**
- Azul principal (texto/oscuro): `#00203A`
- Olivo: `#8A9A46` · olivo claro `#C8D29C`
- Nav activo: `#A54FA9`
- Gradiente de marca: `linear-gradient(45deg, #5059BC 0%, #F26DF9 100%)`

## ⚠ Divergencia a resolver (diseño ↔ código)
El **rosa** difiere entre el sistema de diseño y el código desplegado:
- Sistema de diseño (`tokens/colors.css`, Figma v1.0): `--bg-pink: #f98dff`, gradiente termina en `#f98dff`.
- Código (`branding.py`, perfil chaco): `nodo_magenta = #F26DF9`, gradiente termina en `#F26DF9`.

Antes de implementar conviene unificar a un único valor de rosa. Es decisión del
equipo de diseño; no lo cambié unilateralmente.
