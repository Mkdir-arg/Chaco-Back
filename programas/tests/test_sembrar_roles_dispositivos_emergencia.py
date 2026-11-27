"""``sembrar_roles_dispositivos_emergencia``: los roles que el PM crea a mano en el pod de ECOM.

Lo que se fija acá:

1. En base vacía crea los 11 roles con sus capacidades exactas, anclados a su programa.
2. Una segunda corrida no duplica ni cambia nada (se reconoce por clave, aunque se renombre).
3. Si el PM le sacó un permiso a un rol, la corrida no se lo devuelve.
4. ``--dry-run`` no escribe.
5. Sin el programa, el rol de programa se saltea con aviso y el resto sigue.
6. Las capacidades de la definición existen en el catálogo y valen para su programa.
"""

import dataclasses
from io import StringIO
from unittest import mock

from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core import rbac
from programas.management.commands.seed_dispositivos import asegurar_roles_dispositivos
from programas.models import Programa
from programas.services.roles_sembrados import ROL_AGENTE_RELEVAMIENTO, ROLES_DISPOSITIVOS_EMERGENCIA
from users.models import RolMeta

COMANDO = "sembrar_roles_dispositivos_emergencia"


def _correr(*args):
    salida = StringIO()
    call_command(COMANDO, *args, stdout=salida)
    return salida.getvalue()


def _capacidades(clave):
    return set(rbac.capacidades_de_grupo(RolMeta.objects.get(clave=clave).grupo))


def _permisos_por_rol():
    return {m.clave: set(m.grupo.permissions.values_list("pk", flat=True)) for m in RolMeta.objects.all()}


class SembrarRolesTests(TestCase):
    def setUp(self):
        Programa.objects.get_or_create(
            codigo="DISPOSITIVOS", defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS}
        )
        Programa.objects.get_or_create(
            codigo="EMERGENCIA", defaults={"nombre": "Emergencia", "tipo": Programa.TipoPrograma.EMERGENCIA}
        )

    def test_la_definicion_usa_solo_capacidades_del_catalogo_y_de_su_programa(self):
        validos = set(rbac.codigos_de_capacidad())
        self.assertEqual(len(ROLES_DISPOSITIVOS_EMERGENCIA), 10)
        for rol in ROLES_DISPOSITIVOS_EMERGENCIA:
            self.assertLessEqual(set(rol.capacidades), validos, rol.clave)
            fuera = set(rol.capacidades) & rbac.capacidades_fuera_del_programa(rol.programa)
            self.assertFalse(fuera, f"{rol.clave} trae capacidades que no valen en {rol.programa}: {fuera}")

    def test_crea_los_once_roles_con_sus_capacidades_exactas(self):
        salida = _correr()
        for rol in ROLES_DISPOSITIVOS_EMERGENCIA:
            meta = RolMeta.objects.get(clave=rol.clave)
            self.assertEqual(meta.grupo.name, rol.nombre)
            self.assertEqual(meta.categoria, rbac.CATEGORIA_PROGRAMA)
            self.assertEqual(meta.programa.codigo, rol.programa)
            self.assertFalse(meta.protegido)
            self.assertTrue(meta.activo)
            self.assertEqual(_capacidades(rol.clave), set(rol.capacidades), rol.clave)
        admin = RolMeta.objects.get(clave=rbac.CLAVE_ROL_ADMINISTRADOR)
        self.assertEqual(admin.categoria, rbac.CATEGORIA_BACKOFFICE)
        self.assertTrue(admin.protegido)
        self.assertEqual(_capacidades(rbac.CLAVE_ROL_ADMINISTRADOR), set(rbac.codigos_de_capacidad()))
        self.assertEqual(RolMeta.objects.exclude(clave__isnull=True).count(), 11)
        self.assertIn("11 creados", salida)

    def test_las_capacidades_pedidas_por_el_pm(self):
        _correr()
        self.assertEqual(
            _capacidades("dispositivos.supervision_red"),
            {"dispositivo.ver", "dispositivo.ver_todos", "edificio.ver", "stock.ver"},
        )
        self.assertEqual(_capacidades("dispositivos.consulta"), {"dispositivo.ver", "edificio.ver", "stock.ver"})
        self.assertEqual(_capacidades("emergencia.autoridad"), {"emergencia.ver_situacion"})
        self.assertEqual(_capacidades("emergencia.agente_territorial"), {"emergencia.relevar"})
        self.assertEqual(_capacidades("emergencia.supervisor_mesa"), {"emergencia.operar", "emergencia.supervisar"})

    def test_segunda_corrida_no_duplica_ni_cambia_nada(self):
        _correr()
        antes = (Group.objects.count(), RolMeta.objects.count(), Permission.objects.count())
        permisos = _permisos_por_rol()
        salida = _correr()
        self.assertEqual((Group.objects.count(), RolMeta.objects.count(), Permission.objects.count()), antes)
        self.assertEqual(_permisos_por_rol(), permisos)
        self.assertEqual(salida.count("ya existía"), 11)
        self.assertIn("0 creados", salida)

    def test_un_rol_renombrado_no_se_duplica(self):
        _correr()
        grupo = RolMeta.objects.get(clave="dispositivos.consulta").grupo
        grupo.name = "Solo lectura"
        grupo.save()
        _correr()
        self.assertFalse(Group.objects.filter(name="Dispositivos — Consulta").exists())
        self.assertEqual(RolMeta.objects.filter(clave="dispositivos.consulta").count(), 1)

    def test_no_devuelve_el_permiso_que_el_pm_saco(self):
        _correr()
        grupo = RolMeta.objects.get(clave="dispositivos.operador").grupo
        grupo.permissions.remove(Permission.objects.get(codename=rbac.codename_de("ciudadano.ver")))
        _correr()
        self.assertNotIn("ciudadano.ver", _capacidades("dispositivos.operador"))

    def test_no_pisa_el_estado_ni_la_descripcion_editados(self):
        _correr()
        meta = RolMeta.objects.get(clave="emergencia.autoridad")
        meta.activo = False
        meta.descripcion = "Editada por el PM"
        meta.save()
        _correr()
        meta.refresh_from_db()
        self.assertFalse(meta.activo)
        self.assertEqual(meta.descripcion, "Editada por el PM")

    def test_dry_run_no_escribe(self):
        salida = _correr("--dry-run")
        self.assertEqual(Group.objects.count(), 0)
        self.assertEqual(RolMeta.objects.count(), 0)
        self.assertIn("se crearía", salida)
        self.assertIn("11 por crear", salida)
        self.assertIn("no se escribió nada", salida)

    def test_dry_run_con_roles_existentes_informa_ya_existia(self):
        _correr()
        salida = _correr("--dry-run")
        self.assertEqual(salida.count("ya existía"), 11)
        self.assertNotIn("se crearía", salida)

    def test_sin_programa_saltea_ese_rol_y_sigue_con_el_resto(self):
        Programa.objects.filter(codigo="EMERGENCIA").delete()
        salida = _correr()
        self.assertFalse(RolMeta.objects.filter(clave__startswith="emergencia.").exists())
        self.assertTrue(RolMeta.objects.filter(clave="dispositivos.administrador").exists())
        self.assertTrue(RolMeta.objects.filter(clave=rbac.CLAVE_ROL_ADMINISTRADOR).exists())
        self.assertIn("4 salteados", salida)

    def test_el_agente_ya_sembrado_por_seed_dispositivos_no_se_toca(self):
        group, _ = asegurar_roles_dispositivos()
        salida = _correr()
        self.assertEqual(RolMeta.objects.get(clave=ROL_AGENTE_RELEVAMIENTO.clave).grupo, group)
        self.assertEqual(Group.objects.filter(name=ROL_AGENTE_RELEVAMIENTO.nombre).count(), 1)
        self.assertEqual(salida.count("ya existía"), 1)

    def test_el_administrador_existente_no_se_realinea(self):
        _correr()
        admin = RolMeta.objects.get(clave=rbac.CLAVE_ROL_ADMINISTRADOR).grupo
        admin.permissions.remove(Permission.objects.get(codename=rbac.codename_de("ciudadano.ver")))
        _correr()
        self.assertNotIn("ciudadano.ver", rbac.capacidades_de_grupo(admin))


class NombreOcupadoTests(TestCase):
    """Un Group con el nombre del rol pero sin su clave no se adopta (escalada de permisos)."""

    def setUp(self):
        for codigo, tipo in (
            ("DISPOSITIVOS", Programa.TipoPrograma.DISPOSITIVOS),
            ("EMERGENCIA", Programa.TipoPrograma.EMERGENCIA),
        ):
            Programa.objects.get_or_create(codigo=codigo, defaults={"nombre": codigo.title(), "tipo": tipo})
        self.perm = Permission.objects.get(codename=rbac.codename_de("ciudadano.ver"))

    def _rol_ajeno(self, nombre, clave=None):
        grupo = Group.objects.create(name=nombre)
        grupo.permissions.add(self.perm)
        RolMeta.objects.create(grupo=grupo, categoria=rbac.CATEGORIA_BACKOFFICE, clave=clave)
        return grupo

    def _intacto(self, grupo, clave):
        meta = RolMeta.objects.get(grupo=grupo)
        self.assertEqual(meta.clave, clave)
        self.assertEqual(meta.categoria, rbac.CATEGORIA_BACKOFFICE)
        self.assertIsNone(meta.programa_id)
        self.assertEqual(set(grupo.permissions.values_list("pk", flat=True)), {self.perm.pk})

    def test_nombre_igual_y_sin_clave_conserva_permisos_categoria_y_clave_nula(self):
        grupo = self._rol_ajeno("Dispositivos — Consulta")
        salida = _correr()
        self._intacto(grupo, None)
        self.assertIn("ya existe un rol con ese nombre", salida)
        self.assertIn("10 creados, 1 sin crear por nombre ocupado.", salida)

    def test_nombre_igual_con_otra_clave_no_se_toca_ni_en_la_segunda_corrida(self):
        grupo = self._rol_ajeno("Emergencia — Autoridad", clave="otra.clave")
        _correr()
        _correr()
        self._intacto(grupo, "otra.clave")
        self.assertFalse(RolMeta.objects.filter(clave="emergencia.autoridad").exists())

    def test_administrador_con_nombre_ocupado_no_se_adopta(self):
        grupo = self._rol_ajeno(rbac.ROL_ADMINISTRADOR)
        salida = _correr()
        self._intacto(grupo, None)
        self.assertIn("ya existe un rol con ese nombre", salida)

    def test_dry_run_con_nombre_ocupado_dice_ya_existe_y_no_se_crearia(self):
        grupo = self._rol_ajeno("Dispositivos — Administrador")
        salida = _correr("--dry-run")
        linea = next(x for x in salida.splitlines() if "Dispositivos — Administrador" in x)
        self.assertIn("ya existe un rol con ese nombre", linea)
        self.assertNotIn("se crearía", linea)
        self.assertIn("10 por crear", salida)
        self._intacto(grupo, None)


class DefensaDelSavepointTests(TestCase):
    """Si el chequeo de nombre falla (collation de MariaDB), la escritura se deshace."""

    def setUp(self):
        for codigo, tipo in (
            ("DISPOSITIVOS", Programa.TipoPrograma.DISPOSITIVOS),
            ("EMERGENCIA", Programa.TipoPrograma.EMERGENCIA),
        ):
            Programa.objects.get_or_create(codigo=codigo, defaults={"nombre": codigo.title(), "tipo": tipo})

    def test_un_rol_adoptado_por_nombre_no_queda_con_clave_ni_rolmeta(self):
        sin_meta = Group.objects.create(name="Dispositivos — Consulta")
        con_meta = Group.objects.create(name="Emergencia — Autoridad")
        RolMeta.objects.create(grupo=con_meta, categoria=rbac.CATEGORIA_BACKOFFICE)
        original = Group.objects.filter

        class _SinNombre:
            def exists(self):
                return False

        def filtro(*args, **kwargs):
            if "name" in kwargs:
                return _SinNombre()
            return original(*args, **kwargs)

        with mock.patch.object(Group.objects, "filter", side_effect=filtro):
            salida = _correr()
        self.assertFalse(RolMeta.objects.filter(grupo=sin_meta).exists())
        self.assertIsNone(RolMeta.objects.get(grupo=con_meta).clave)
        self.assertEqual(sin_meta.permissions.count(), 0)
        self.assertEqual(salida.count("ya existe un rol con ese nombre"), 2)


class CapacidadFueraDeCatalogoTests(TestCase):
    def setUp(self):
        for codigo, tipo in (
            ("DISPOSITIVOS", Programa.TipoPrograma.DISPOSITIVOS),
            ("EMERGENCIA", Programa.TipoPrograma.EMERGENCIA),
        ):
            Programa.objects.get_or_create(codigo=codigo, defaults={"nombre": codigo.title(), "tipo": tipo})

    def test_corta_con_command_error_y_no_escribe(self):
        primero = ROLES_DISPOSITIVOS_EMERGENCIA[0]
        roto = dataclasses.replace(primero, capacidades=(*primero.capacidades, "no.existe"))
        ruta = "programas.management.commands.sembrar_roles_dispositivos_emergencia.ROLES_DISPOSITIVOS_EMERGENCIA"
        with mock.patch(ruta, (roto,)):
            with self.assertRaisesMessage(CommandError, f"{primero.clave}: capacidades fuera del catálogo"):
                _correr()
        self.assertFalse(RolMeta.objects.filter(clave=primero.clave).exists())
