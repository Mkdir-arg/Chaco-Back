---
name: chaco-design-system
description: Fuente operativa única para decisiones de UI del backoffice y portal ciudadano de Chaco. Se usa obligatoriamente antes de crear o modificar templates, includes, CSS o JavaScript de interfaz.
tools: Read, Grep, Glob, Edit, Bash
model: sonnet
---

# Agente canónico de diseño — Chaco

## Autoridad y alcance

Este archivo es la única fuente de verdad **operativa** de diseño. No reemplaza al
producto: ante cualquier diferencia, el orden de precedencia es:

1. Código productivo vigente y su comportamiento comprobable.
2. Este agente y su inventario, actualizados con evidencia del código.
3. `docs/design-kb/`, prototipos, prompts y assets, únicamente como referencia.

Aplica al backoffice y al portal ciudadano. La documentación no autoriza a cambiar
el producto para hacerla coincidir; si discrepa, se corrige esta clasificación con
evidencia. No migres ni rediseñes pantallas fuera del alcance de la tarea.

## Procedimiento obligatorio antes de editar UI

1. Leé `AGENTS.md` y este archivo.
2. Ubicá la ruta, el template final, su `{% extends %}` y los includes compartidos.
3. Identificá CSS y JavaScript que el shell realmente carga, además de los usos de
   las clases o APIs involucradas.
4. Consultá el inventario. La UI nueva reutiliza exclusivamente piezas clasificadas
   como **Canónico reutilizable**.
5. Si no existe una pieza canónica, demostralo con rutas y búsqueda, creá el patrón
   reutilizable más pequeño necesario dentro del alcance y agregalo al inventario
   en el mismo PR.

### Reconciliación obligatoria

Si el inventario, otro agente o un material histórico contradice el código:

- detené el cambio visual;
- citá las rutas que prueban el comportamiento cargado o usado;
- actualizá aquí la clasificación, contrato y reemplazo recomendado;
- retomá solamente la tarea afectada.

Esa reconciliación no habilita migraciones laterales, limpieza masiva ni cambios de
pantallas ajenas.

## Clasificación

- **Canónico reutilizable:** tiene evidencia de carga y contrato reutilizable en el
  producto. La UI nueva puede usarlo.
- **Legacy solo mantenimiento:** sigue vivo por una pantalla o compatibilidad. Solo
  se conserva o corrige al mantener esa superficie; no se propaga.
- **Duplicado o conflictivo:** compite con otro contrato, tiene cascada global o es
  documentación/prototipo no verificado. No se reutiliza; se indica el reemplazo.

## Inventario operativo inicial

| Pieza | Clasificación | Evidencia y contrato de uso |
|---|---|---|
| Tokens semánticos y tipografía | Canónico reutilizable | `static/custom/css/chaco-tokens.css`; usar `--bg-*`, `--text-*`, `--border-*` y `--font-*`, no valores visuales ad hoc. |
| Shell backoffice | Canónico reutilizable | `templates/includes/base.html`, `templates/includes/navbar.html`, `templates/includes/sidebar/base.html`; heredar/incluir, no recrear sidebar ni offsets. El cierre de sesión del menú de usuario es un `<form method="post">` con `{% csrf_token %}`, no un enlace: `LogoutView` no acepta GET desde Django 5.0. |
| Shell de autenticación pública | Canónico reutilizable | `users/templates/user/base_public_auth.html`; lo extienden `establecer_contrasena.html`, `recuperar_contrasena.html`, `recuperar_contrasena_enviada.html` y `cambiar_contrasena_obligatorio.html`. Contrato: clases `public-auth__title`, `__help`, `__field`, `__error`, `__button` y `__link`, con `button.public-auth__link` para la misma apariencia cuando la acción tiene que ir por formulario. Es el shell de las pantallas de credenciales fuera de sesión; no reutiliza el shell del backoffice. |
| Shell portal ciudadano | Canónico reutilizable | `portal/templates/portal/base.html`, `portal/templates/portal/ciudadano/base_ciudadano.html`; superficie separada del backoffice. |
| Shell público de autenticación | Canónico reutilizable | `users/templates/user/base_public_auth.html`; superficie sin sesión, menú ni alertas internas para recuperación y establecimiento de contraseña. Consumido por `users/templates/user/recuperar_contrasena.html`, `users/templates/user/recuperar_contrasena_enviada.html` y `users/templates/user/establecer_contrasena.html`. |
| Botones NODO | Canónico reutilizable | `static/custom/css/nodo-buttons.css`; reutilizar `btn-nodo` con las variantes y tamaños existentes. |
| Badges NODO | Canónico reutilizable | `static/custom/css/nodo-badges.css`; reutilizar `badge` y sus variantes, siempre con texto además del color. |
| Campos NODO | Canónico reutilizable | `static/custom/css/nodo-forms.css`; usar `nodo-field` en controles que correspondan. |
| Toasts NODO | Canónico reutilizable | `templates/includes/base.html`, `static/custom/css/nodo-toast.css`, `static/custom/js/nodo-toast.js`; preservar roles, live regions, persistencia de errores y cierre accesible. |
| Confirmación SweetAlert2 | Canónico reutilizable, condicionado | `static/custom/css/nodo-swal.css` y `static/custom/js/nodo-swal-theme.js`; antes de `Swal.fire`, verificar que la pantalla cargue SweetAlert2. |
| Modal global `ModernModal` | Legacy solo mantenimiento | Implementaciones activas en `templates/includes/base.html` y `portal/templates/portal/base.html`; preservar su contrato en pantallas existentes. No hay reemplazo canónico probado: si una tarea exige un modal nuevo, crear el patrón mínimo y registrarlo. |
| Bootstrap/AdminLTE y estilos de pantalla heredados | Legacy solo mantenimiento | `static/custom/css/main.css`, `custom.css`, `override.css`; mantener solamente en la superficie que los consume. Reemplazo para UI nueva: piezas canónicas inventariadas. |
| Puente `paleta-unificada.css` | Legacy solo mantenimiento | Alias de compatibilidad cargados desde `templates/includes/base.html`; no usar sus utilidades en UI nueva. Reemplazo: tokens semánticos y componente canónico aplicable. |
| `nodo-brand.css` | Duplicado o conflictivo | Selectores globales de links, submits y focus en `static/custom/css/nodo-brand.css`; el base los neutraliza parcialmente. Reemplazo: tokens, botones, badges y campos canónicos. |
| CSS responsive/mobile global | Duplicado o conflictivo | `static/custom/css/responsive.css`, `mobile-forms.css`, `mobile-modals.css`, `mobile-tables.css`; sus reglas generales compiten con contratos específicos. Reemplazo: responsive del shell y del componente canónico afectado. |
| Kits, JSX, tokens y documentos previos | Duplicado o conflictivo como autoridad | `docs/design-kb/`; pueden aportar assets o antecedentes, nunca decidir contra el runtime. Reemplazo: este inventario contrastado con código. |

No hay evidencia de componentes compartidos canónicos para page headers, stat cards,
tablas o modales nuevos. No los inventes desde el kit: si una tarea los necesita,
seguí el procedimiento de ausencia de pieza canónica.

## Estados transversales comprobados

- **Accesibilidad:** los toasts tienen roles/live regions y foco visible; el modal
  global del backoffice tiene `role=dialog`, focus trap, Escape y devolución de
  foco. Todo cambio debe conservar o mejorar ese soporte.
- **Responsividad:** el shell provee sidebar móvil/colapsable; las piezas con reglas
  responsive propias deben verificarse en el CSS que se carga para esa superficie.
- **Dark mode:** `chaco-tokens.css` define variables para `[data-theme="dark"]` y
  `.dark`, pero no hay evidencia actual de activación compartida en el shell. Usá
  tokens semánticos para no bloquearlo, sin declarar soporte funcional hasta que se
  compruebe la activación en código.
- **Portal:** no hay activación dark comprobada; tratarlo como light-only mientras
  no exista evidencia productiva distinta.

## Sincronización y validación

Cada PR que cree, altere o reclasifique una pieza reutilizable actualiza esta tabla
en el mismo PR, con ruta, contrato, estados y clasificación. En la descripción del
PR, informar el delta de inventario y cualquier reconciliación.

Si se modifican templates, CSS o JavaScript de UI, ejecutar:

```powershell
& .\.venv\Scripts\python.exe scripts\check_design_agent.py --changed
& .\.venv\Scripts\python.exe scripts\design_audit.py <rutas-tocadas>
& .\.venv\Scripts\python.exe scripts\compile_templates.py  # si hubo templates
```

`check_design_agent.py` valida rutas de evidencia, consumidores, autoridad residual y
que una pieza canónica modificada actualice este inventario. La auditoría mecánica es
un control parcial; ninguna de las dos sustituye la verificación de carga,
accesibilidad, responsividad y comportamiento de la superficie afectada.
