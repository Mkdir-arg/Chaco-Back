"""Tests de los roles RBAC de Becas y el scoping por segmento (#79)."""

from datetime import date
from io import StringIO

from django.contrib.auth.models import Group, Permission, User
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import RequestFactory, TestCase

from core import rbac
from programas.management.commands.seed_becas import (
    ROL_ADMIN,
    ROL_COORDINADOR,
    ROL_TERRITORIAL,
)
from programas.models import (
    AsignacionCoordinador,
    Convocatoria,
    Formulario,
    Programa,
    Relevamiento,
    Segmento,
)
from programas.services.autorizacion import (
    es_admin_becas,
    es_coordinador_becas,
    programa_becas,
    puede_gestionar_segmento,
    segmentos_visibles,
)
from programas.views.configuracion import _assert_scope as config_assert_scope
from programas.views.revision import _assert_scope_formulario, _assert_scope_relevamiento
from users.models import RolMeta


class RbacBecasTests(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.becas = Programa.objects.get(codigo="BECAS")
        self.seg_a = Segmento.objects.create(nombre="Segmento A", cupo_maximo=100)
        self.seg_b = Segmento.objects.create(nombre="Segmento B", cupo_maximo=100)

        self.g_admin = Group.objects.get(name=ROL_ADMIN)
        self.g_coord = Group.objects.get(name=ROL_COORDINADOR)
        self.g_terri = Group.objects.get(name=ROL_TERRITORIAL)

        self.admin = User.objects.create_user("admin_becas")
        self.admin.groups.add(self.g_admin)

        self.coord = User.objects.create_user("coord_becas")
        self.coord.groups.add(self.g_coord)
        AsignacionCoordinador.objects.create(segmento=self.seg_a, coordinador=self.coord)

        self.coord_sin = User.objects.create_user("coord_sin_asignacion")
        self.coord_sin.groups.add(self.g_coord)

        self.territorial = User.objects.create_user("terri")
        self.territorial.groups.add(self.g_terri)

    # --- existencia y configuración de roles ---
    def test_tres_roles_existen_categoria_programa(self):
        for nombre in (ROL_ADMIN, ROL_COORDINADOR, ROL_TERRITORIAL):
            meta = Group.objects.get(name=nombre).meta
            self.assertEqual(meta.categoria, rbac.CATEGORIA_PROGRAMA)
            self.assertEqual(meta.programa_id, self.becas.id)
            self.assertTrue(meta.activo)

    def test_capacidades_de_cada_rol(self):
        self.assertTrue(rbac.puede(self.admin, "becas.programa.administrar", programa=self.becas))
        self.assertTrue(rbac.puede(self.admin, "becas.revision.editar", programa=self.becas))
        self.assertFalse(rbac.puede(self.coord, "becas.programa.administrar", programa=self.becas))
        self.assertTrue(rbac.puede(self.coord, "becas.revision.editar", programa=self.becas))
        self.assertTrue(rbac.puede(self.coord, "becas.reportes.ver", programa=self.becas))
        self.assertTrue(rbac.puede(self.coord, "becas.reportes.exportar", programa=self.becas))
        self.assertTrue(rbac.puede(self.territorial, "becas.campo", programa=self.becas))
        self.assertFalse(rbac.puede(self.territorial, "becas.revision.editar", programa=self.becas))
        self.assertFalse(rbac.puede(self.territorial, "becas.reportes.ver", programa=self.becas))

    def test_admin_recibe_el_alcance_de_los_abm_del_programa(self):
        """El seed le da las dos capacidades transversales explícitamente.

        La paraguas ``becas.programa.administrar`` ya no las confiere, y como
        ``asegurar_roles_becas`` usa ``permissions.set()``, si el seed no las incluyera
        una corrida revertiría el traspaso de ``users.0020`` y el Administrador se
        quedaría sin los ABM de Usuarios y Roles.
        """
        from users.selectors.roles import programas_administrables_roles, programas_administrables_usuarios

        for capacidad in rbac.CAPS_ADMIN_PROGRAMA:
            self.assertTrue(rbac.puede(self.admin, capacidad, programa=self.becas), capacidad)
        self.assertEqual(list(programas_administrables_usuarios(self.admin)), [self.becas])
        self.assertEqual(list(programas_administrables_roles(self.admin)), [self.becas])
        # El Coordinador no administra el programa: su alcance son sus territoriales.
        self.assertEqual(list(programas_administrables_usuarios(self.coord)), [])

    # --- admin: acceso total ---
    def test_admin_gestiona_cualquier_segmento(self):
        self.assertTrue(es_admin_becas(self.admin, programa=self.becas))
        self.assertTrue(puede_gestionar_segmento(self.admin, self.seg_a, programa=self.becas))
        self.assertTrue(puede_gestionar_segmento(self.admin, self.seg_b, programa=self.becas))
        self.assertEqual(set(segmentos_visibles(self.admin, programa=self.becas)), {self.seg_a, self.seg_b})

    # --- coordinador: scoping por segmento ---
    def test_coordinador_asignado_accede_solo_a_su_segmento(self):
        self.assertTrue(es_coordinador_becas(self.coord, programa=self.becas))
        self.assertTrue(puede_gestionar_segmento(self.coord, self.seg_a, programa=self.becas))
        self.assertFalse(puede_gestionar_segmento(self.coord, self.seg_b, programa=self.becas))
        self.assertEqual(set(segmentos_visibles(self.coord, programa=self.becas)), {self.seg_a})

    def test_coordinador_sin_asignacion_no_accede(self):
        self.assertFalse(puede_gestionar_segmento(self.coord_sin, self.seg_a, programa=self.becas))
        self.assertFalse(puede_gestionar_segmento(self.coord_sin, self.seg_b, programa=self.becas))
        self.assertEqual(list(segmentos_visibles(self.coord_sin, programa=self.becas)), [])

    # --- territorial: sin acceso de gestión/revisión ---
    def test_territorial_no_gestiona_segmentos(self):
        self.assertFalse(es_admin_becas(self.territorial, programa=self.becas))
        self.assertFalse(es_coordinador_becas(self.territorial, programa=self.becas))
        self.assertFalse(puede_gestionar_segmento(self.territorial, self.seg_a, programa=self.becas))
        self.assertEqual(list(segmentos_visibles(self.territorial, programa=self.becas)), [])

    # --- RN-27: múltiples roles a la vez ---
    def test_usuario_con_multiples_roles(self):
        otro_grupo = Group.objects.create(name="Operador genérico")
        rbac_ct_user = User.objects.create_user("multi")
        rbac_ct_user.groups.add(self.g_admin, otro_grupo)
        # Sigue siendo admin de Becas con varios roles asignados.
        self.assertTrue(es_admin_becas(rbac_ct_user, programa=self.becas))
        self.assertTrue(puede_gestionar_segmento(rbac_ct_user, self.seg_b, programa=self.becas))

    def test_anonimo_no_accede(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(puede_gestionar_segmento(AnonymousUser(), self.seg_a, programa=self.becas))
        self.assertEqual(list(segmentos_visibles(AnonymousUser(), programa=self.becas)), [])


class GuardsFallanCerradoTests(TestCase):
    """RED-56: sin el Programa Becas sembrado, los guards tienen que denegar.

    ``programa_becas()`` devuelve ``None`` si la fila ``BECAS`` no está (un
    restore, un ``crear_programas`` que la recrea con otro pk, un pod que
    arranca antes del bootstrap, o la clave ``programas:becas`` envenenada en el
    Redis compartido con TTL 300). Con ``programa=None`` el RBAC cae al chequeo
    **global**, así que un rol de **otro** programa con una capacidad ``becas.*``
    tildada atravesaba los tres guards durante 300 s y se curaba solo, sin rastro.
    """

    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.becas = Programa.objects.get(codigo="BECAS")

        self.segmento = Segmento.objects.create(nombre="Seg A", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv A", segmento=self.segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.territorial = User.objects.create_user("terri_red56")
        self.territorial.groups.add(Group.objects.get(name=ROL_TERRITORIAL))
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=self.territorial,
            fecha_asignada=date(2026, 6, 1),
            zona="A",
        )
        self.formulario = Formulario.objects.create(relevamiento=self.relevamiento)

        # Un rol de OTRO programa con capacidades de Becas tildadas: el caso que el
        # RBAC acotado por programa rechaza y el chequeo global deja pasar. El árbol
        # del ABM de Roles muestra el catálogo entero, así que tildarlas es un clic.
        self.otro_programa = Programa.objects.create(codigo="OTRO", nombre="Otro programa")
        self.grupo_ajeno = Group.objects.create(name="Otro — Administrador")
        RolMeta.objects.create(
            grupo=self.grupo_ajeno,
            categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.otro_programa,
            activo=True,
        )
        self.grupo_ajeno.permissions.set(
            Permission.objects.filter(
                content_type__app_label=rbac.APP_LABEL,
                codename__in=[
                    rbac.codename_de(c)
                    for c in ("becas.programa.administrar", "becas.revision.ver", "becas.revision.editar")
                ],
            )
        )
        self.ajeno = User.objects.create_user("admin_de_otro_programa")
        self.ajeno.groups.add(self.grupo_ajeno)

        self.factory = RequestFactory()

    def _request(self):
        request = self.factory.get("/becas/revision/")
        # Usuario recién leído: ``programa_becas`` memoiza en el objeto durante
        # la request, y cada request real trae el suyo.
        request.user = User.objects.get(pk=self.ajeno.pk)
        return request

    def _sin_programa_becas(self):
        """Lo que pasa en producción: la fila queda con otro código, o no está."""
        Programa.objects.filter(codigo="BECAS").update(codigo="BECAS_RENOMBRADO")
        cache.clear()
        self.assertIsNone(programa_becas())

    def test_los_tres_guards_dan_el_mismo_veredicto(self):
        """Ratchet barato: con Becas sembrado, un usuario de otro programa no entra."""
        request = self._request()
        for nombre, guard, objeto in (
            ("configuracion._assert_scope", config_assert_scope, self.segmento),
            ("revision._assert_scope_relevamiento", _assert_scope_relevamiento, self.relevamiento),
            ("revision._assert_scope_formulario", _assert_scope_formulario, self.formulario),
        ):
            with self.subTest(guard=nombre):
                with self.assertRaises(PermissionDenied):
                    guard(request, objeto)

    def test_sin_programa_becas_el_guard_deniega(self):
        self._sin_programa_becas()
        with self.assertRaises(PermissionDenied):
            _assert_scope_formulario(self._request(), self.formulario)

    def test_sin_programa_becas_los_tres_guards_deniegan(self):
        self._sin_programa_becas()
        request = self._request()
        for nombre, guard, objeto in (
            ("configuracion._assert_scope", config_assert_scope, self.segmento),
            ("revision._assert_scope_relevamiento", _assert_scope_relevamiento, self.relevamiento),
            ("revision._assert_scope_formulario", _assert_scope_formulario, self.formulario),
        ):
            with self.subTest(guard=nombre):
                with self.assertRaises(PermissionDenied):
                    guard(request, objeto)

    def test_sin_programa_becas_los_predicados_tampoco_abren(self):
        """Las seis puertas de ``autorizacion.py``, no solo las tres de las vistas."""
        self._sin_programa_becas()
        usuario = User.objects.get(pk=self.ajeno.pk)  # sin memo de una llamada previa
        for nombre, funcion in (
            ("es_admin_becas", es_admin_becas),
            ("es_coordinador_becas", es_coordinador_becas),
        ):
            with self.subTest(funcion=nombre):
                with self.assertRaises(PermissionDenied):
                    funcion(usuario)
        with self.assertRaises(PermissionDenied):
            puede_gestionar_segmento(usuario, self.segmento)
        with self.assertRaises(PermissionDenied):
            list(segmentos_visibles(usuario))

    def test_con_el_programa_sembrado_el_admin_de_becas_sigue_entrando(self):
        """La guarda nueva no puede cerrarle la puerta a quien sí corresponde."""
        admin = User.objects.create_user("admin_becas_ok")
        admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        request = self.factory.get("/becas/revision/")
        request.user = admin
        config_assert_scope(request, self.segmento)
        _assert_scope_relevamiento(request, self.relevamiento)
        _assert_scope_formulario(request, self.formulario)
