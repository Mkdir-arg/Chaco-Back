"""G2-05 · `import_users_from_csv` no puede pisar cuentas que ya existen.

El comando creaba o **actualizaba** usuarios desde un CSV y a todos les hacía
`groups.set(...)` con los grupos de un usuario de referencia **cuyo id estaba
escrito en el código** (368, que en otra base es cualquiera). En los que ya
existían cambiaba además el email y **la contraseña**, sin ensayo, sin
`validate_password`, sin `transaction.atomic` y sin `debe_cambiar_contrasena`:
una fila repetida en el CSV le cambiaba la clave y los roles a una persona que
ya estaba trabajando, y una fila rota a mitad del archivo dejaba la mitad hecha.

Lo que fija este módulo es el contrato nuevo, el mismo que el resto de los
comandos que escriben (`ComandoSiisBase`): **ensayo por defecto**, escritura con
`--aplicar`, y lo destructivo —tocar una cuenta que ya existe— detrás de
`--actualizar --motivo`, que deja rastro en el log.
"""

import csv
import io
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core import rbac
from users.models import Capacidad, RolMeta

COLUMNAS = ["Usuario", "Email", "Nombre completo", "Apellido", "Contraseña"]
CLAVE_BUENA = "Resistencia-2026-Chaco"
CLAVE_DE_LA_PERSONA = "la-que-ya-tenia-2026"


def _perm(codigo):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct)


class ImportUsersFromCsvTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.User = get_user_model()
        cls.grupo_referencia = Group.objects.create(name="Mesa de entrada")
        cls.referencia = cls.User.objects.create_user(username="referente")
        cls.referencia.groups.add(cls.grupo_referencia)

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def csv_con(self, filas, columnas=COLUMNAS):
        ruta = Path(self.tmp.name) / "usuarios.csv"
        with ruta.open("w", newline="", encoding="utf-8") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=columnas)
            escritor.writeheader()
            for fila in filas:
                escritor.writerow(fila)
        return str(ruta)

    def fila(self, usuario="nuevo", clave=CLAVE_BUENA, email="nuevo@chaco.gob.ar"):
        return {
            "Usuario": usuario,
            "Email": email,
            "Nombre completo": "Nombre",
            "Apellido": "Apellido",
            "Contraseña": clave,
        }

    def correr(self, ruta, **opciones):
        salida = io.StringIO()
        opciones.setdefault("reference_user_id", self.referencia.pk)
        call_command("import_users_from_csv", ruta, stdout=salida, stderr=salida, **opciones)
        return salida.getvalue()

    # ── El id de referencia escrito en el código ────────────────────────────

    def test_reference_user_id_es_obligatorio(self):
        """Sin default: el 368 de otra base reparte los grupos de un desconocido."""
        ruta = self.csv_con([self.fila()])
        with self.assertRaises(CommandError) as capturado:
            call_command("import_users_from_csv", ruta, stdout=io.StringIO())
        self.assertIn("reference-user-id", str(capturado.exception))

    # ── Ensayo por defecto ─────────────────────────────────────────────────

    def test_sin_aplicar_no_escribe_nada(self):
        salida = self.correr(self.csv_con([self.fila()]))
        self.assertFalse(self.User.objects.filter(username="nuevo").exists())
        self.assertIn("ENSAYO", salida)

    def test_con_aplicar_crea_al_usuario_con_los_grupos_de_la_referencia(self):
        self.correr(self.csv_con([self.fila()]), aplicar=True)
        creado = self.User.objects.get(username="nuevo")
        self.assertEqual(list(creado.groups.all()), [self.grupo_referencia])
        self.assertTrue(creado.check_password(CLAVE_BUENA))

    def test_el_creado_tiene_que_cambiar_la_clave(self):
        """La clave viaja en texto plano en el CSV: es provisoria por definición."""
        self.correr(self.csv_con([self.fila()]), aplicar=True)
        self.assertTrue(self.User.objects.get(username="nuevo").profile.debe_cambiar_contrasena)

    # ── No tocar lo que ya existe ──────────────────────────────────────────

    def test_un_usuario_existente_conserva_grupos_clave_y_email_sin_actualizar(self):
        propio = Group.objects.create(name="Legajos — Operador")
        persona = self.User.objects.create_user(
            username="ocupado", email="ocupado@chaco.gob.ar", password=CLAVE_DE_LA_PERSONA
        )
        persona.groups.add(propio)

        salida = self.correr(
            self.csv_con([self.fila(usuario="ocupado", email="otro@chaco.gob.ar")]),
            aplicar=True,
        )

        persona.refresh_from_db()
        self.assertEqual(list(persona.groups.all()), [propio])
        self.assertTrue(persona.check_password(CLAVE_DE_LA_PERSONA))
        self.assertEqual(persona.email, "ocupado@chaco.gob.ar")
        self.assertIn("--actualizar", salida)

    def test_actualizar_exige_motivo(self):
        self.User.objects.create_user(username="ocupado", password=CLAVE_DE_LA_PERSONA)
        with self.assertRaises(CommandError) as capturado:
            self.correr(self.csv_con([self.fila(usuario="ocupado")]), aplicar=True, actualizar=True)
        self.assertIn("--motivo", str(capturado.exception))

    def test_con_actualizar_y_motivo_se_le_replican_los_grupos_y_queda_en_el_log(self):
        self.User.objects.create_superuser(username="jefa", password=CLAVE_BUENA)
        persona = self.User.objects.create_user(username="ocupado", password=CLAVE_DE_LA_PERSONA)
        persona.groups.add(Group.objects.create(name="Legajos — Operador"))

        with self.assertLogs("users.management.commands.import_users_from_csv", level=logging.WARNING) as registro:
            self.correr(
                self.csv_con([self.fila(usuario="ocupado")]),
                aplicar=True,
                actualizar=True,
                motivo="alta masiva pedida por el área",
            )

        persona.refresh_from_db()
        self.assertEqual(list(persona.groups.all()), [self.grupo_referencia])
        self.assertIn("alta masiva pedida por el área", "\n".join(registro.output))

    def test_actualizar_no_puede_dejar_al_sistema_sin_administrador(self):
        """`groups.set` de la referencia le quita el rol al único que administra."""
        rol_admin = Group.objects.create(name="Administración")
        RolMeta.objects.create(grupo=rol_admin, categoria="Sistema", activo=True)
        rol_admin.permissions.add(_perm("usuario.administrar"))
        unico = self.User.objects.create_user(username="ocupado", password=CLAVE_DE_LA_PERSONA)
        unico.groups.add(rol_admin)

        with self.assertLogs("users.management.commands.import_users_from_csv", level=logging.WARNING):
            with self.assertRaises(CommandError) as capturado:
                self.correr(
                    self.csv_con([self.fila(usuario="ocupado")]),
                    aplicar=True,
                    actualizar=True,
                    motivo="alta masiva",
                )

        self.assertIn("sin ningún usuario con permisos de administración", str(capturado.exception))
        unico.refresh_from_db()
        self.assertEqual(list(unico.groups.all()), [rol_admin])

    # ── Claves ─────────────────────────────────────────────────────────────

    def test_una_clave_debil_corta_y_no_deja_nada_escrito(self):
        ruta = self.csv_con([self.fila(usuario="primero"), self.fila(usuario="segundo", clave="123")])
        with self.assertRaises(CommandError) as capturado:
            self.correr(ruta, aplicar=True)
        self.assertIn("segundo", str(capturado.exception))
        self.assertFalse(self.User.objects.filter(username="primero").exists())

    def test_la_salida_no_imprime_la_clave_ni_el_email(self):
        salida = self.correr(self.csv_con([self.fila()]), aplicar=True)
        self.assertNotIn(CLAVE_BUENA, salida)
        self.assertNotIn("nuevo@chaco.gob.ar", salida)
        self.assertIn("nuevo", salida)

    def test_la_columna_rol_no_se_exige_y_se_avisa_que_se_ignora(self):
        """Los grupos salen de `--reference-user-id`; la columna «Rol» no los movía."""
        ruta = self.csv_con([{**self.fila(), "Rol": "Coordinador"}], columnas=[*COLUMNAS, "Rol"])
        salida = self.correr(ruta, aplicar=True)
        self.assertIn("Rol", salida)
        self.assertEqual(list(self.User.objects.get(username="nuevo").groups.all()), [self.grupo_referencia])
