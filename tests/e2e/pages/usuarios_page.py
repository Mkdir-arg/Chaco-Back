"""Page Object del listado de Usuarios (users:usuarios -> `/usuarios/`).

Referencias reales (users/templates/user/user_list.html):
    <h1>Usuarios</h1>                       encabezado de la página
    <a ... aria-label="Nuevo usuario">      botón de alta (patrón NODO btn-brand)
    toolbar de filtros: "Agregar filtro" / "Aplicar"
    <table> dentro del TableCard            listado
"""
from playwright.sync_api import Page


class UsuariosPage:
    PATH = "/usuarios/"

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def goto(self):
        self.page.goto(f"{self.base_url}{self.PATH}")

    def heading(self):
        return self.page.get_by_role("heading", name="Usuarios", level=1)

    def nuevo_usuario_btn(self):
        return self.page.get_by_role("link", name="Nuevo usuario")

    def tabla(self):
        return self.page.locator("table").first

    def aplicar_filtro_btn(self):
        return self.page.get_by_role("button", name="Aplicar")
