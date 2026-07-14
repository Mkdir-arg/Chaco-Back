# Pruebas E2E (simulación en navegador — Playwright)

Automatización de QA **simulando un usuario real en el navegador** (login, clics,
formularios, confirmaciones SweetAlert2), no tests de backend. Pensado para cubrir
los flujos de UI del backoffice (listados NODO, ABM de Usuarios/Roles, filtros).

## Requisitos (una sola vez)

Se usa un venv **aparte** (`.venv-e2e`) para no tocar el venv de Django (`.venv`):

```powershell
# desde la raíz del repo
py -m venv .venv-e2e
.venv-e2e\Scripts\python.exe -m pip install -r tests/e2e/requirements-e2e.txt
.venv-e2e\Scripts\python.exe -m playwright install chromium
```

## Configurar el entorno objetivo

Nunca correr contra producción (los tests **crean/editan/borran** datos). Usar
Docker local o un **servidor de prueba**. Se pasa todo por variables de entorno:

```powershell
$env:E2E_BASE_URL="https://miserver-de-prueba:8000"
$env:E2E_USER="admin@chaco.gob.ar"
$env:E2E_PASS="********"
```

## Correr — viendo el navegador en tiempo real

```powershell
# navegador VISIBLE + cámara lenta (para mirarlo actuar)
.venv-e2e\Scripts\python.exe -m pytest tests/e2e --headed --slowmo 800
```

```powershell
# modo normal (rápido, sin ventana) — para CI
.venv-e2e\Scripts\python.exe -m pytest tests/e2e
```

### Evidencia para adjuntar al issue de QA

```powershell
.venv-e2e\Scripts\python.exe -m pytest tests/e2e --headed --slowmo 800 `
  --screenshot only-on-failure --video retain-on-failure --tracing retain-on-failure
```

Los artefactos quedan en `tests/e2e/_artifacts/` y en `test-results/`.
Para ver un trace: `.venv-e2e\Scripts\python.exe -m playwright show-trace <archivo.zip>`.

## Grabar un flujo nuevo (codegen)

En vez de escribir a mano, se puede **grabar**: abre un navegador, hacés los clics
y Playwright genera el código.

```powershell
.venv-e2e\Scripts\python.exe -m playwright codegen $env:E2E_BASE_URL
```

## Estructura

```
tests/e2e/
├── conftest.py            # fixtures: base_url, credentials, contexto del navegador
├── pytest.ini             # config de pytest
├── pages/                 # Page Objects (1 por pantalla)
│   ├── login_page.py
│   └── usuarios_page.py
└── test_usuarios_smoke.py # smoke: login + listado de Usuarios (#122/#121/#120)
```

Cada caso nuevo = un `test_*.py` más, reutilizando los Page Objects.
La fuente de cada test son los casos **Dado/Cuando/Entonces** del cuerpo de la task en GitHub.
