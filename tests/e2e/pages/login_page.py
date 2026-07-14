"""Page Object del login del backoffice (users:login, montado en la raíz `/`).

Campos reales del form (users/templates/user/login.html):
    input[name="username"]  -> el correo electrónico
    input[name="password"]  -> la contraseña
    button "Iniciar Sesión" -> submit
Tras un login OK la app redirige a `/inicio/` (LOGIN_REDIRECT_URL = core:inicio).
"""
from playwright.sync_api import Page, expect


class LoginPage:
    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def goto(self):
        self.page.goto(f"{self.base_url}/")

    def login(self, username: str, password: str):
        self.goto()
        self.page.fill("input[name='username']", username)
        self.page.fill("input[name='password']", password)
        self.page.get_by_role("button", name="Iniciar Sesión").click()
        # Login OK => sale del login y cae en /inicio/.
        self.page.wait_for_url("**/inicio/**", timeout=15000)

    def error_banner(self):
        """Cartel 'Credenciales inválidas' que aparece cuando el login falla."""
        return self.page.get_by_text("Credenciales inválidas")
