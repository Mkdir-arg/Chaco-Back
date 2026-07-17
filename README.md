# Chaco

Chaco es un sistema de gestión compuesto por un backoffice para equipos
administrativos y un portal ciudadano para realizar trámites y consultas.

Está construido con Django 4.2, MySQL 8 y Docker Compose.

## Requisitos

- Docker Engine con el plugin Docker Compose (`docker compose`).
- Git.
- Acceso al repositorio y a las credenciales de producción.

## Configuración inicial

1. Clone el repositorio y ubíquese en su directorio raíz.
2. Cree `.env.production` a partir de `.env.local.example`.
3. Complete los valores de producción, especialmente las claves, credenciales
   de base de datos y dominios permitidos.
4. No versionar nunca `.env.production` ni compartir sus secretos.

## Despliegue

Para crear o actualizar los servicios manualmente:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

También puede usar el script de despliegue:

```bash
scripts/deploy_prod.sh
```

El script realiza backup de archivos relevantes, valida la configuración,
espera el health check y revierte al commit anterior si el despliegue falla.

## Verificación

Una vez iniciados los servicios, verifique que el endpoint responda HTTP 200:

```bash
curl -i http://localhost/health/
```

## Actualización

1. Confirme que el árbol de trabajo del servidor esté limpio.
2. Actualice exclusivamente desde la rama de release:

   ```bash
   git pull --ff-only origin main
   ```

3. Recree los servicios de aplicación y websocket:

   ```bash
   docker compose -f docker-compose.prod.yml up -d --build --force-recreate web websocket
   ```

4. Reinicie Nginx:

   ```bash
   docker compose -f docker-compose.prod.yml restart nginx
   ```

`main` es una rama de release generada automáticamente. No haga commits sobre
ella ni la actualice manualmente.
