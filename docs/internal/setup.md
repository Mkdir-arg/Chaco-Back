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

# 7. Crear el superusuario (elegís usuario, correo y contraseña)
docker compose exec django python manage.py createsuperuser
```

!!! note
    No hay ningún comando que cree un superusuario con credenciales fijas: existía
    uno (`crear_superadmin`, con `admin`/`mkdir123` escritos en el código) y se
    retiró porque corría igual en los ambientes servidos. Si necesitás crearlo sin
    interacción —por ejemplo para el harness de E2E—, pasá las credenciales por
    entorno:

    ```bash
    docker compose exec \
      -e DJANGO_SUPERUSER_USERNAME=admin \
      -e DJANGO_SUPERUSER_EMAIL=admin@localhost \
      -e DJANGO_SUPERUSER_PASSWORD=<local> \
      django python manage.py createsuperuser --noinput
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
