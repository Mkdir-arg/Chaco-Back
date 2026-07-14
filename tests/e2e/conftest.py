"""Configuración compartida del harness E2E (Playwright).

El servidor objetivo y las credenciales se pasan por variables de entorno para
no hardcodear nada en el repo:

    E2E_BASE_URL   URL base del entorno de PRUEBA (ej. https://miserver:8000)
    E2E_USER       correo del usuario de prueba
    E2E_PASS       contraseña del usuario de prueba

Ejemplo (PowerShell), corriendo con navegador VISIBLE y en cámara lenta:

    $env:E2E_BASE_URL="https://miserver:8000"
    $env:E2E_USER="admin@chaco.gob.ar"
    $env:E2E_PASS="********"
    .venv-e2e\\Scripts\\python.exe -m pytest tests/e2e --headed --slowmo 800
"""
import os

import pytest

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8000").rstrip("/")


@pytest.fixture(scope="session")
def base_url():
    """URL base del entorno bajo prueba."""
    return BASE_URL


@pytest.fixture(scope="session")
def credentials():
    """Credenciales del usuario de prueba (skip si no están definidas)."""
    user = os.environ.get("E2E_USER", "")
    password = os.environ.get("E2E_PASS", "")
    if not user or not password:
        pytest.skip(
            "Definí E2E_USER y E2E_PASS con las credenciales del servidor de prueba."
        )
    return {"username": user, "password": password}


@pytest.fixture
def browser_context_args(browser_context_args):
    """Contexto del navegador: viewport de escritorio (para que se vea el sidebar)
    y tolerancia a certificados self-signed típicos de un server de prueba."""
    return {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 900},
        "ignore_https_errors": True,
    }
