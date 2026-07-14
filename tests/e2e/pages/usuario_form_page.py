"""Page Object del alta/edición de Usuario (users:usuario_crear -> `/usuarios/crear/`).

Campos reales (users/templates/user/user_form.html):
    #id_username #id_email #id_first_name #id_last_name #id_password (password solo en alta)
Roles: el <select id="id_groups"> está OCULTO por CSS; la UI son <button> dentro de
    #group-options con textContent = nombre del rol (ej. "Becas — Coordinador").
    -> se selecciona clickeando el botón por su texto distintivo.
Segmento territorial: #id_segmento_territorial, dentro de #segmento-territorial-field
    (oculto salvo que se tilde un rol territorial). Obligatorio para el rol Territorial.
Submit: botón "Guardar".
"""
from playwright.sync_api import Page


class UsuarioFormPage:
    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def goto_crear(self):
        self.page.goto(f"{self.base_url}/usuarios/crear/")

    def completar_datos(self, username, email, nombre, apellido, password):
        self.page.fill("#id_username", username)
        self.page.fill("#id_email", email)
        self.page.fill("#id_first_name", nombre)
        self.page.fill("#id_last_name", apellido)
        self.page.fill("#id_password", password)

    def elegir_rol(self, texto_distintivo: str):
        """Clickea el botón de rol cuyo texto contiene `texto_distintivo`
        (ej. 'Coordinador', 'Territorial'). Evita depender del em-dash exacto."""
        self.page.locator("#group-options button", has_text=texto_distintivo).click()

    def elegir_segmento_territorial(self, label: str):
        self.page.select_option("#id_segmento_territorial", label=label)

    def guardar(self):
        self.page.get_by_role("button", name="Guardar").click()
