# Arquitectura del sistema

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12, Django 4.2 |
| Base de datos | MySQL 8 |
| Frontend | Tailwind CSS, Alpine.js |
| Infraestructura | Docker Compose |
| Tiempo real | Django Channels (WebSocket) |

## Aplicaciones principales

```
config/          → configuración central de Django (settings, urls, wsgi)
core/            → modelos base, utilidades, cache, performance
legajos/         → gestión de ciudadanos, programas, derivaciones, NACHEC
configuracion/   → instituciones, programas, clases, geografía
conversaciones/  → chat en tiempo real, colas de atención
portal/          → portal ciudadano (autenticación, perfil, consultas)
users/           → usuarios del backoffice, grupos y permisos
dashboard/       → métricas y vistas de inicio
tramites/        → gestión de trámites
healthcheck/     → endpoint de salud del sistema
security/        → autenticación, autorización, auditoría
```

## Diagrama de capas

```
┌─────────────────────────────────────────┐
│           Clientes                      │
│   Backoffice (staff) │ Portal ciudadano │
└──────────────┬───────────────┬──────────┘
               │               │
┌──────────────▼───────────────▼──────────┐
│              Django (config/urls.py)    │
│  Middlewares: auth, institución, perf   │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Apps de dominio                        │
│  legajos │ configuracion │ portal │ ... │
│  Patrón: selectors → services → views  │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Persistencia                           │
│  MySQL 8 (principal)                    │
└─────────────────────────────────────────┘
```

## Patrón de capas por app

Cada app sigue este patrón interno:

- `models.py` — definición de datos
- `selectors/` — consultas de lectura (sin lógica de negocio)
- `services/` — lógica de negocio y escritura
- `views/` — orquestación HTTP, sin lógica de dominio
- `forms/` — validación de entrada
- `templates/` — presentación HTML

## Decisiones de diseño relevantes

Ver [decisions/](decisions/README.md) para el registro completo de ADRs.
