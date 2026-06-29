# Setup del proyecto

## Requisitos previos

- Docker Desktop instalado y corriendo
- Git configurado con acceso al repositorio
- Python 3.12 (solo para herramientas locales fuera de Docker)

## Levantar el entorno local

```bash
# 1. Clonar el repositorio
git clone <url-del-repo>
cd Chaco

# 2. Copiar variables de entorno
cp .env.local.example .env

# 3. Editar .env con los valores locales (pedir al equipo)

# 4. Levantar los servicios
docker compose up -d

# 5. Aplicar migraciones
docker compose exec django python manage.py migrate

# 6. Cargar datos iniciales
docker compose exec django python manage.py load_initial_data

# 7. Crear superusuario
docker compose exec django python manage.py crear_superadmin
```

## Verificar que todo funciona

```bash
docker compose exec django python manage.py check
```

Acceder a `http://localhost:8000` para el backoffice.

## Servicios del docker-compose

| Servicio | Puerto | Descripción |
|---|---|---|
| django | 8000 | Aplicación principal |
| mysql | 3306 | Base de datos |

## Variables de entorno críticas

Ver `.env.local.example` para la lista completa. Las variables que necesitás pedir al equipo:

- `SECRET_KEY`
- `DATABASE_URL`

## Comandos útiles del día a día

```bash
# Ver logs en tiempo real
docker compose logs -f django

# Ejecutar tests
docker compose exec django python manage.py test

# Shell de Django
docker compose exec django python manage.py shell

# Crear migración después de cambiar un modelo
docker compose exec django python manage.py makemigrations <app>
docker compose exec django python manage.py migrate
```
