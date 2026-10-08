"""Tests del bootstrap de arranque: ``seed_datos_base`` (que corre ``seed_rbac`` y
``seed_becas``) y ``crear_programas`` — Cambio 104 (OPS-06 de la auditoría oct-2026).

El bootstrap corre en **cada** arranque del contenedor (en ECOM, en cada pod nuevo),
así que no puede pisar lo que la pantalla de Roles y la de Programas dejan editar:

- Las capacidades **base** de los roles de Becas se siguen sincronizando con el código
  (regla del Cambio 29): si alguien saca una a mano, vuelve.
- Las capacidades **opt-in** (``becas.relevamiento.publico``, Cambios 41 y 91) se
  encienden tildándolas en Roles y **sobreviven** al seed.
- Un rol existente conserva su descripción y su estado activo/inactivo. Los roles se
  identifican solo por nombre: uno renombrado deja de ser «sembrado» (el arranque crea
  otro con el nombre canónico) y un rol hecho a mano nunca recibe capacidades del seed.
- «Operador de backoffice» solo se siembra al crearlo.
- ``crear_programas`` no pisa el estado ni los demás campos del Programa Becas.

Los catálogos base (``loaddata`` de localidades, 1,5 MB) se omiten: no son parte de lo
que se prueba y harían lento cada caso.
"""

import io
from contextlib import redirect_stdout
from unittest import mock

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import CommandError, call_command
from django.test import TestCase

from core import rbac
from programas.management.commands import seed_becas
from programas.models import Programa
from users.models import Capacidad, RolMeta

PUBLICO = "becas.relevamiento.publico"
OPERADOR = "Operador de backoffice"


def _correr(comando="seed_datos_base"):
    # redirect_stdout también calla a los seeds que seed_datos_base llama por dentro.
    with mock.patch("users.management.commands.seed_datos_base._CATALOGOS", []), redirect_stdout(io.StringIO()):
        call_command(comando)


def _codigos(grupo):
    return set(rbac.capacidades_de_grupo(grupo))


def _perm(codigo):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(content_type=ct, codename=rbac.codename_de(codigo))


def _base(nombre_rol):
    return set(seed_becas.ROLES_BECAS[nombre_rol]["capacidades"])


class SeedRolesBecasTests(TestCase):
    def setUp(self):
        _correr()
        self.referente = Group.objects.get(name=seed_becas.ROL_REFERENTE)

    def test_la_capacidad_opt_in_sobrevive_al_seed(self):
        self.referente.permissions.add(_perm(PUBLICO))

        _correr()

        self.assertIn(PUBLICO, _codigos(self.referente))

    def test_la_capacidad_opt_in_no_se_siembra_sola(self):
        # RN-P13: la capacidad se enciende a mano desde Roles, nunca por seed.
        for nombre in seed_becas.ROLES_BECAS:
            self.assertNotIn(PUBLICO, _codigos(Group.objects.get(name=nombre)))

    def test_una_capacidad_base_quitada_a_mano_vuelve(self):
        # Cambio 29: el seed mantiene los roles alineados con el código.
        self.referente.permissions.remove(_perm("becas.revision.ver"))

        _correr()

        self.assertEqual(_codigos(self.referente), _base(seed_becas.ROL_REFERENTE))

    def test_una_capacidad_ajena_agregada_a_mano_se_quita(self):
        self.referente.permissions.add(_perm("becas.revision.editar"))

        _correr()

        self.assertEqual(_codigos(self.referente), _base(seed_becas.ROL_REFERENTE))

    def test_un_rol_desactivado_sigue_inactivo(self):
        RolMeta.objects.filter(grupo=self.referente).update(activo=False)

        _correr()

        self.assertFalse(RolMeta.objects.get(grupo=self.referente).activo)

    def test_la_descripcion_editada_no_se_pisa(self):
        RolMeta.objects.filter(grupo=self.referente).update(descripcion="Texto propio del cliente")

        _correr()

        self.assertEqual(RolMeta.objects.get(grupo=self.referente).descripcion, "Texto propio del cliente")

    def test_un_rol_renombrado_genera_uno_nuevo_con_el_nombre_canonico(self):
        # Conducta documentada (D-O06): los roles se identifican solo por nombre.
        # Reconocer el renombre exige la clave estable de la fase 2 de OPS-06.
        self.referente.name = "Referente de Becas"
        self.referente.save()
        roles_antes = Group.objects.count()

        _correr()

        self.assertEqual(Group.objects.count(), roles_antes + 1)
        nuevo = Group.objects.get(name=seed_becas.ROL_REFERENTE)
        self.assertNotEqual(nuevo.pk, self.referente.pk)
        self.assertEqual(_codigos(nuevo), _base(seed_becas.ROL_REFERENTE))
        self.referente.refresh_from_db()
        self.assertEqual(self.referente.name, "Referente de Becas")

    def test_un_rol_renombrado_deja_de_sincronizarse(self):
        self.referente.name = "Referente de Becas"
        self.referente.save()
        self.referente.permissions.remove(_perm("becas.revision.ver"))
        self.referente.permissions.add(_perm("becas.revision.editar"))
        RolMeta.objects.filter(grupo=self.referente).update(activo=False)
        antes = _codigos(self.referente)

        _correr()

        self.assertEqual(_codigos(self.referente), antes)
        self.assertFalse(RolMeta.objects.get(grupo=self.referente).activo)

    def test_un_rol_borrado_se_vuelve_a_crear(self):
        self.referente.delete()

        _correr()

        nuevo = Group.objects.get(name=seed_becas.ROL_REFERENTE)
        self.assertEqual(_codigos(nuevo), _base(seed_becas.ROL_REFERENTE))
        self.assertTrue(nuevo.meta.activo)
        self.assertEqual(nuevo.meta.categoria, rbac.CATEGORIA_PROGRAMA)

    def _rol_a_mano(self, nombre, capacidades):
        propio = Group.objects.create(name=nombre)
        RolMeta.objects.create(grupo=propio, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.referente.meta.programa)
        propio.permissions.set([_perm(c) for c in capacidades])
        return propio

    def test_un_rol_hecho_a_mano_parecido_al_oficial_no_recibe_capacidades(self):
        # Revisión del PR #508: «Admin Becas (acotado)», copia del Administrador sin
        # las capacidades de administrar usuarios y roles del programa. Con la
        # heurística por similitud el seed lo adoptaba y le devolvía esas dos
        # capacidades (escalada). Se prueba con el oficial presente y borrado.
        acotadas = _base(seed_becas.ROL_ADMIN) - set(rbac.CAPS_ADMIN_PROGRAMA)
        acotado = self._rol_a_mano("Admin Becas (acotado)", acotadas)

        _correr()
        self.assertEqual(_codigos(acotado), acotadas)

        Group.objects.get(name=seed_becas.ROL_ADMIN).delete()
        _correr()

        self.assertEqual(_codigos(acotado), acotadas)
        acotado.refresh_from_db()
        self.assertEqual(acotado.name, "Admin Becas (acotado)")
        self.assertEqual(_codigos(Group.objects.get(name=seed_becas.ROL_ADMIN)), _base(seed_becas.ROL_ADMIN))

    def test_un_rol_a_mano_identico_al_oficial_borrado_no_lo_reemplaza(self):
        # Territorial tiene una sola capacidad: cualquier rol con solo becas.campo
        # era «idéntico» y la heurística lo capturaba.
        propio = self._rol_a_mano("Territorial zona norte", ["becas.campo"])
        Group.objects.get(name=seed_becas.ROL_TERRITORIAL).delete()

        _correr()

        self.assertTrue(Group.objects.filter(name=seed_becas.ROL_TERRITORIAL).exists())
        propio.refresh_from_db()
        self.assertEqual(propio.name, "Territorial zona norte")
        self.assertEqual(_codigos(propio), {"becas.campo"})

    def test_es_idempotente(self):
        _correr()
        roles = dict(Group.objects.values_list("name", "pk"))
        caps = {g.name: _codigos(g) for g in Group.objects.all()}

        _correr()
        _correr()

        self.assertEqual(dict(Group.objects.values_list("name", "pk")), roles)
        self.assertEqual({g.name: _codigos(g) for g in Group.objects.all()}, caps)
        for nombre in seed_becas.ROLES_BECAS:
            rol = Group.objects.get(name=nombre)
            self.assertEqual(_codigos(rol), _base(nombre))
            self.assertTrue(rol.meta.activo)
            self.assertEqual(rol.meta.programa.codigo, seed_becas.PROGRAMA_BECAS_CODIGO)


class SeedOperadorBackofficeTests(TestCase):
    def test_al_crearlo_lleva_sus_capacidades(self):
        _correr()

        operador = Group.objects.get(name=OPERADOR)
        self.assertEqual(
            _codigos(operador),
            {"ciudadano.ver", "reporte.ver", "config.administrar", "usuario.administrar", "rol.administrar"},
        )
        self.assertTrue(operador.meta.activo)

    def test_desactivado_y_sin_capacidades_sigue_asi(self):
        _correr()
        operador = Group.objects.get(name=OPERADOR)
        operador.permissions.clear()
        RolMeta.objects.filter(grupo=operador).update(activo=False)

        _correr()

        self.assertEqual(_codigos(operador), set())
        self.assertFalse(RolMeta.objects.get(grupo=operador).activo)


class SeedGestionCiudadanosTests(TestCase):
    def test_quien_edita_ciudadanos_nace_exportando(self):
        """SEC-20 / D-20: en una base nueva la 0028 no encuentra roles; el seed cumple la regla."""
        _correr()

        gestion = Group.objects.get(name="Gestión de Ciudadanos")
        self.assertIn("ciudadano.editar", _codigos(gestion))
        self.assertIn("ciudadano.exportar", _codigos(gestion))
        operador = Group.objects.get(name=OPERADOR)
        self.assertNotIn("ciudadano.exportar", _codigos(operador))


class CrearProgramasTests(TestCase):
    def test_no_pisa_el_estado_ni_los_campos_editados(self):
        _correr()
        programa = Programa.objects.get(codigo=seed_becas.PROGRAMA_BECAS_CODIGO)
        Programa.objects.filter(pk=programa.pk).update(
            estado=Programa.Estado.SUSPENDIDO, nombre="Becas Chaco", color="#123456", orden=9
        )

        _correr("crear_programas")
        _correr()

        programa.refresh_from_db()
        self.assertEqual(programa.estado, Programa.Estado.SUSPENDIDO)
        self.assertEqual(programa.nombre, "Becas Chaco")
        self.assertEqual(programa.color, "#123456")
        self.assertEqual(programa.orden, 9)

    def test_crea_el_programa_si_falta(self):
        _correr("crear_programas")

        programa = Programa.objects.get(codigo=seed_becas.PROGRAMA_BECAS_CODIGO)
        self.assertEqual(programa.estado, Programa.Estado.ACTIVO)
        self.assertEqual(programa.tipo, Programa.TipoPrograma.BECAS)

    def test_el_programa_nace_igual_por_cualquiera_de_los_dos_comandos(self):
        # Una sola fuente para icono, color y orden: el arranque corre seed_becas
        # antes que crear_programas, y antes cada uno decía otra cosa.
        _correr("crear_programas")
        becas = Programa.objects.filter(codigo=seed_becas.PROGRAMA_BECAS_CODIGO)
        campos = ("nombre", "tipo", "icono", "color", "orden", "descripcion", "estado", "naturaleza")
        por_crear_programas = becas.values(*campos).get()
        becas.delete()

        _correr("seed_becas")
        por_seed_becas = becas.values(*campos).get()

        self.assertEqual(por_crear_programas, por_seed_becas)

    def test_otro_programa_de_tipo_becas_no_rompe_el_arranque(self):
        # Programa.tipo no es único: un segundo tipo=BECAS daba MultipleObjectsReturned.
        _correr("crear_programas")
        Programa.objects.create(codigo="BECAS_2", nombre="Becas bis", tipo=Programa.TipoPrograma.BECAS)

        _correr("crear_programas")

        self.assertEqual(Programa.objects.filter(codigo=seed_becas.PROGRAMA_BECAS_CODIGO).count(), 1)

    def test_un_programa_becas_con_otro_codigo_frena_en_vez_de_duplicar(self):
        # Sin programa «BECAS» pero con uno de tipo Becas: datos inconsistentes. Crear
        # un segundo programa lo taparía en silencio; el arranque frena y lo explica.
        Programa.objects.create(codigo="BECAS_VIEJO", nombre="Becas", tipo=Programa.TipoPrograma.BECAS)

        for comando in ("crear_programas", "seed_becas"):
            with self.subTest(comando=comando):
                with self.assertRaisesMessage(CommandError, "BECAS_VIEJO"):
                    _correr(comando)
                self.assertFalse(Programa.objects.filter(codigo=seed_becas.PROGRAMA_BECAS_CODIGO).exists())
                self.assertEqual(Programa.objects.filter(tipo=Programa.TipoPrograma.BECAS).count(), 1)
