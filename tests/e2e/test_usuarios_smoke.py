"""Smoke E2E: login del backoffice + carga del listado de Usuarios (patrón NODO).

Es el primer caso del harness: valida de punta a punta que se puede entrar al
sistema y que la pantalla de Usuarios renderiza (encabezado, botón de alta y
tabla). Cubre el flujo base de los issues #122 / #121 / #120.

Correr con navegador visible y en cámara lenta:
    .venv-e2e\\Scripts\\python.exe -m pytest tests/e2e/test_usuarios_smoke.py --headed --slowmo 800
"""
import os

from playwright.sync_api import expect

from pages.login_page import LoginPage
from pages.usuarios_page import UsuariosPage

ARTIFACTS = os.path.join(os.path.dirname(__file__), "_artifacts")


def test_login_y_listado_usuarios(page, base_url, credentials):
    # 1) Entrar al sistema
    login = LoginPage(page, base_url)
    login.login(**credentials)

    # 2) Ir al listado de Usuarios
    usuarios = UsuariosPage(page, base_url)
    usuarios.goto()

    # 3) La pantalla NODO renderiza: encabezado, botón de alta y tabla
    expect(usuarios.heading()).to_be_visible()
    expect(usuarios.nuevo_usuario_btn()).to_be_visible()
    expect(usuarios.tabla()).to_be_visible(timeout=10000)

    # 4) Evidencia para QA
    os.makedirs(ARTIFACTS, exist_ok=True)
    page.screenshot(
        path=os.path.join(ARTIFACTS, "usuarios_listado.png"), full_page=True
    )
