from django.test import SimpleTestCase


class UsersPackageExportsTests(SimpleTestCase):
    def test_views_package_exports_public_symbols(self):
        from users.views import RolListView, UserCreateView, UserListView, UsuariosLoginView

        self.assertIsNotNone(UsuariosLoginView)
        self.assertIsNotNone(UserListView)
        self.assertIsNotNone(UserCreateView)
        self.assertIsNotNone(RolListView)

    def test_services_and_selectors_packages_export_public_symbols(self):
        from users.forms import CustomUserChangeForm, UserCreationForm
        from users.selectors import get_usuarios_queryset
        from users.services import UsuariosAdminService, UsuariosService

        self.assertIsNotNone(UserCreationForm)
        self.assertIsNotNone(CustomUserChangeForm)
        self.assertIsNotNone(UsuariosService)
        self.assertIsNotNone(UsuariosAdminService)
        self.assertTrue(callable(get_usuarios_queryset))

    def test_signals_package_exports_receivers(self):
        # `save_user_profile` se retiró en la Ola 2 (RED-52): el Profile lo guarda
        # quien lo escribe, no un `post_save(User)` que propaga el objeto entero.
        from users.signals import create_user_profile, revocar_tokens_al_cambiar_la_clave

        self.assertTrue(callable(create_user_profile))
        self.assertTrue(callable(revocar_tokens_al_cambiar_la_clave))

    def test_api_views_package_exports_la_vista_de_me(self):
        # Los ViewSets de usuarios, roles y perfiles se retiraron (D-05 de la
        # auditoría oct-2026): la API solo expone el usuario de la sesión.
        import users.api_views as api_views
        from users.api_views import UsuarioActualView

        self.assertIsNotNone(UsuarioActualView)
        for retirado in ("UserViewSet", "GroupViewSet", "ProfileViewSet"):
            self.assertFalse(hasattr(api_views, retirado), retirado)
