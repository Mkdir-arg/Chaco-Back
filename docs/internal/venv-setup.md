# Venv local (Windows + PowerShell)

Receta para correr el repo fuera de Docker usando un virtualenv aislado. Útil
para `manage.py check`, tests rápidos, o cuando el Python global de la máquina
tiene paquetes en versiones que rompen `Django 4.2` (p. ej. `django-silk`
viejo importando `get_storage_class` de un Django ya purgado).

## Crear el venv

Desde la raíz del repo, en PowerShell:

```powershell
py -3.12 -m venv .venv
```

Si `py -3.12` no está instalado, se acepta caer a `py -3.10` (ver
"Versión de Python" abajo). Django 4.2 LTS soporta oficialmente Python
3.8 → 3.12.

## Activar / usar el venv

**No** usés `Activate.ps1`. Invocá siempre el intérprete del venv con su path
absoluto para que sea explícito qué Python corre cada comando.

```powershell
$env:PY_VENV = "$PWD\.venv\Scripts\python.exe"
```

A partir de acá, todo se hace contra `$env:PY_VENV`:

```powershell
# Verificar la instalación
$env:DJANGO_SECRET_KEY = "test-key"
& $env:PY_VENV manage.py check

# Levantar servidor local (sin Docker)
& $env:PY_VENV manage.py runserver

# Tests
& $env:PY_VENV manage.py test

# Migraciones / shell
& $env:PY_VENV manage.py migrate
& $env:PY_VENV manage.py shell
```

> El comando `pip` también va por el venv: `& $env:PY_VENV -m pip install <pkg>`.

## Instalar dependencias

```powershell
& $env:PY_VENV -m pip install --upgrade pip
& $env:PY_VENV -m pip install -r requirements.txt
```

Las versiones del `requirements.txt` son la fuente de verdad. No instalar
nada globalmente.

## Versión de Python

- **Ideal:** Python 3.12 (stack documentado en `CLAUDE.md`).
- **Aceptable:** Python 3.10 / 3.11. Django 4.2 LTS los soporta.
- En la máquina de referencia donde se generó este doc solo había Python
  3.10.11, así que el venv se creó con `py -3.10`. El `manage.py check`
  pasa sin errores en esa configuración.

Si necesitás 3.12 explícitamente (por una dependencia futura o para acercarte
al runtime de Docker), instalalo con `py install 3.12` o desde python.org y
recreá el venv borrando `.venv/` primero.

## Version-pin overrides aplicados

**Ninguno por ahora.** El `requirements.txt` actual instala limpio en un venv
3.10 y `manage.py check` pasa con:

- `Django==4.2.20`
- `django-silk==5.0.4`

El error global que motivó este doc:

```
ImportError: cannot import name 'get_storage_class' from
'django.core.files.storage' (silk/models.py)
```

se produce cuando se mezcla `django-silk < 5.1` con `Django >= 5.1` (Django
5.1 eliminó `get_storage_class`). Mientras el venv quede pinneado a Django
4.2.x, `django-silk 5.0.4` sigue siendo compatible y no hace falta tocar el
pin.

**Si en el futuro bumpeamos a Django 5.x**, hay que subir también
`django-silk>=5.1` en el mismo cambio. Documentarlo acá cuando pase.

## Follow-ups conocidos (no bloqueantes)

- Al correr `manage.py check` en el venv aparece:

  ```
  silk.profiling.profiler WARNING: Cannot execute silk_profile as silk is
  not installed correctly.
  ```

  Es un log de silk al import time. No es un fallo del framework de checks
  de Django (`System check identified no issues (0 silenced).` igual aparece).
  Probable causa: falta `silk.middleware.SilkyMiddleware` en `MIDDLEWARE`
  de `config/settings.py`. Queda como tarea separada — no se tocó código de
  la app en este setup.

## Resetear el venv

Si algo queda en un estado raro:

```powershell
Remove-Item -Recurse -Force .venv
py -3.12 -m venv .venv     # o py -3.10
& "$PWD\.venv\Scripts\python.exe" -m pip install --upgrade pip
& "$PWD\.venv\Scripts\python.exe" -m pip install -r requirements.txt
```

`.venv/` ya está en `.gitignore`, así que el reset es local y no ensucia git.
