from django.test import SimpleTestCase

from users.services import UsuariosService


class UsuariosServiceUrlsTests(SimpleTestCase):
    def test_contexto_lista_expone_namespaces_estables(self):
        context = UsuariosService.get_usuarios_list_context()

        self.assertEqual(context['breadcrumb_items'][0]['url'], '/usuarios/')
        self.assertEqual(context['reset_url'], '/usuarios/')
        self.assertEqual(context['add_url'], '/usuarios/crear/')
        self.assertEqual(context['filters_action'], '/usuarios/')
        self.assertEqual(context['table_actions'][0]['url_name'], 'users:usuario_editar')
        self.assertEqual(context['table_actions'][1]['url_name'], 'users:usuario_toggle')
