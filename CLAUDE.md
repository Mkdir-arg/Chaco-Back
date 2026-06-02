# Chaco

## Identidad del repo

`Chaco` es un monorepo Django orientado a backoffice y portal ciudadano.

- Stack principal: Python 3.12, Django 4.2, MySQL 8, Tailwind CSS, Alpine.js, Docker Compose
- Apps que suelen concentrar trabajo: `core`, `legajos`, `configuracion`, `conversaciones`, `dashboard`, `portal`, `users`, `tramites`, `healthcheck`
- Superficies principales: backoffice y portal ciudadano
- La fuente de verdad es el código actual del repo, no documentación histórica

## Regla principal

Trabajar code-first.

1. Leer este archivo.
2. Entender el pedido actual del usuario.
3. Inspeccionar el código real afectado.
4. Diseñar o implementar con cambios mínimos y verificables.
5. Validar con `manage.py check`, tests o revisión de templates según corresponda.

## Convenciones de implementación

- Priorizar lectura de código antes de asumir comportamiento.
- No depender de `docs/`, `documentos/` ni `memory/` como prerequisito de trabajo.
- Si falta contexto funcional, derivarlo del código, rutas, templates y nombres del dominio.
- Usar Django Forms/ModelForms para formularios del backoffice.
- Crear migraciones inmediatamente después de cambiar modelos.
- Templates del backoffice: extender `includes/base.html`.
- Templates del portal: extender `portal/base.html`.
- Confirmaciones destructivas: SweetAlert2 o modal equivalente, nunca `confirm()` nativo.
- Mantener cambios pequeños, consistentes y fáciles de validar.
