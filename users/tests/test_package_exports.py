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
        from users.signals import create_user_profile, save_user_profile

        self.assertTrue(callable(create_user_profile))
        self.assertTrue(callable(save_user_profile))

    def test_api_views_package_exports_viewsets(self):
        from users.api_views import GroupViewSet, ProfileViewSet, UserViewSet

        self.assertIsNotNone(UserViewSet)
        self.assertIsNotNone(GroupViewSet)
        self.assertIsNotNone(ProfileViewSet)
