"""SEC-29 / D-29 — comando que desactiva las cuentas de ciudadano del portal.

Decisión D-29: las cuentas existentes se desactivan, pero **no** en una migración
de datos: queda un comando explícito para que lo corra quien opere la base,
después de contar con P-08 (cuántas cuentas activas hay en PRD). Por eso el
default es ``--dry-run``: sin ``--aplicar`` no toca nada.
"""

from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase


class DesactivarUsuariosPortalTests(TestCase):
    def setUp(self):
        self.ciudadanos = Group.objects.create(name="Ciudadanos")
        self.backoffice = Group.objects.create(name="Operador")

        self.ciudadano_activo = User.objects.create_user(username="30111222", password="x")  # nosec B106
        self.ciudadano_activo.groups.add(self.ciudadanos)

        self.ciudadano_ya_inactivo = User.objects.create_user(
            username="30111333",
            password="x",  # nosec B106
            is_active=False,
        )
        self.ciudadano_ya_inactivo.groups.add(self.ciudadanos)

        self.operador = User.objects.create_user(username="operador", password="x")  # nosec B106
        self.operador.groups.add(self.backoffice)

        self.sin_grupo = User.objects.create_user(username="suelto", password="x")  # nosec B106
        self.admin = User.objects.create_superuser(username="root", email="r@x.test", password="x")  # nosec B106

    def _run(self, *args):
        salida = StringIO()
        call_command("desactivar_usuarios_portal", *args, stdout=salida)
        return salida.getvalue()

    def test_dry_run_es_el_default_y_no_cambia_nada(self):
        salida = self._run()

        self.assertIn("1", salida)
        self.assertIn("--aplicar", salida)
        for usuario in (self.ciudadano_activo, self.operador, self.sin_grupo, self.admin):
            usuario.refresh_from_db()
            self.assertTrue(usuario.is_active, usuario.username)

    def test_dry_run_explicito_tampoco_cambia_nada(self):
        self._run("--dry-run")

        self.ciudadano_activo.refresh_from_db()
        self.assertTrue(self.ciudadano_activo.is_active)

    def test_aplicar_desactiva_solo_a_los_del_grupo_ciudadanos(self):
        self._run("--aplicar")

        self.ciudadano_activo.refresh_from_db()
        self.assertFalse(self.ciudadano_activo.is_active)

        for usuario in (self.operador, self.sin_grupo, self.admin):
            usuario.refresh_from_db()
            self.assertTrue(usuario.is_active, usuario.username)

    def test_aplicar_es_idempotente(self):
        self._run("--aplicar")
        salida = self._run("--aplicar")

        self.assertEqual(User.objects.filter(groups=self.ciudadanos, is_active=True).count(), 0)
        self.assertIn("0", salida)

    def test_no_toca_a_un_usuario_que_es_ciudadano_y_backoffice_a_la_vez(self):
        """Un usuario con los dos grupos sigue siendo alguien que opera el backoffice."""
        mixto = User.objects.create_user(username="mixto", password="x")  # nosec B106
        mixto.groups.add(self.ciudadanos, self.backoffice)

        self._run("--aplicar")

        mixto.refresh_from_db()
        self.assertTrue(mixto.is_active)

    def test_sin_grupo_ciudadanos_no_falla(self):
        self.ciudadanos.delete()

        salida = self._run("--aplicar")

        self.assertIn("0", salida)
