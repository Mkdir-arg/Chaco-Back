"""E2E del proceso de negocio del Programa Becas (multi-actor, encadenado).

Orden real del flujo (con dependencias reales del código):
  1. Admin crea Coordinador           <- ESTE ARCHIVO (primer eslabón)
  2. Admin crea Segmento (elige coord)
  3. Admin crea Territorial (rol + segmento)
  4. Admin asigna Coordinador al Segmento (alcance)
  5. Coordinador/Admin crea Convocatoria
  6. Coordinador/Admin crea Relevamiento (asigna Territorial)
  7. [Trabajo de campo del Territorial = mobile/API, NO web]
  8. Coordinador revisa formularios + gestiona cupo

Login inicial: superuser `admin` / `mkdir123` (el que tiene el ABM de Usuarios).
"""
import os
import uuid

from playwright.sync_api import expect

from pages.login_page import LoginPage
from pages.usuario_form_page import UsuarioFormPage
from pages.usuarios_page import UsuariosPage

ARTIFACTS = os.path.join(os.path.dirname(__file__), "_artifacts")


def test_admin_crea_coordinador(page, base_url, credentials):
    """Paso 1: el Admin da de alta un usuario con rol Becas — Coordinador
    y lo encuentra en el listado de Usuarios."""
    LoginPage(page, base_url).login(**credentials)

    sufijo = uuid.uuid4().hex[:6]
    username = f"coord_{sufijo}"

    form = UsuarioFormPage(page, base_url)
    form.goto_crear()
    form.completar_datos(
        username=username,
        email=f"{username}@test.local",
        nombre="Coordi",
        apellido="Prueba",
        password="BecasCoord2026!",
    )
    form.elegir_rol("Coordinador")
    form.guardar()

    # Éxito => redirige al listado de Usuarios (h1 "Usuarios", distinto del alta "Nuevo Usuario").
    usuarios = UsuariosPage(page, base_url)
    expect(usuarios.heading()).to_be_visible(timeout=15000)
    expect(page.get_by_text(username, exact=True)).to_be_visible()

    os.makedirs(ARTIFACTS, exist_ok=True)
    page.screenshot(path=os.path.join(ARTIFACTS, "01_coordinador_creado.png"), full_page=True)
