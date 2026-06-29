# ADR 001 — Stack principal del sistema

**Estado:** Aceptado
**Fecha:** 2026

## Contexto

Se necesitaba elegir el stack tecnológico para un sistema de gestión social multi-institución con backoffice, portal ciudadano y app móvil de campo.

## Decisión

- **Backend:** Python 3.12 + Django 4.2
- **Base de datos:** MySQL 8
- **Frontend:** Tailwind CSS + Alpine.js (sin SPA)
- **Tiempo real:** Django Channels + WebSocket
- **Infraestructura:** Docker Compose
- **API móvil:** Django REST Framework sobre MySQL
- **App móvil:** Expo / React Native

## Opciones evaluadas

| Opción | Razón de descarte |
|---|---|
| FastAPI + React | Mayor complejidad de equipo, sin admin nativo |
| Node.js | Menor experiencia del equipo en el dominio |
| PostgreSQL | MySQL ya disponible en infraestructura existente |

## Consecuencias

- Django Admin disponible para gestión rápida de datos
- Curva de entrada baja para devs con experiencia Django
- Tailwind + Alpine permite interactividad sin overhead de SPA
- MySQL limita algunas capacidades de JSON nativo vs PostgreSQL
