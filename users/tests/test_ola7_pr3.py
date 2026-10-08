"""Ola 7 · PR 3 — G1b-09, G1b-10 y el seguimiento MINOR de #646 sobre la ficha del rol.

* ``CandadoDeUltimoAdminTests`` / ``CarreraDeUltimoAdminTests`` (G1b-09) — el check de
  «último administrador» leía sin candado, así que dos operaciones simultáneas lo
  salteaban y el sistema quedaba sin nadie que pudiera tocar usuarios ni roles.
* ``AltaRapidaEnCarreraTests`` (G1b-10) — la colisión de unicidad en la carrera salía
  como 500 y el modal mostraba «respuesta inesperada del servidor».
* ``BotonEditarDeLaFichaTests`` (seguimiento de #646) — la ficha del rol propio
  dibujaba «Editar» y la vista rebotaba.
"""

import threading

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, connections, transaction
from django.test import TestCase, TransactionTestCase, tag
from django.urls import reverse
from unittest.mock import patch

from core import rbac
from core.tests.candados import candados_tomados
from core.tests.test_motor_real import MotorRealMixin
from programas.management.commands.seed_becas import ROL_COORDINADOR
from programas.models import Programa
from users.models import Capacidad, RolMeta


def _perm(codigo):
    content_type = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=content_type)


def _rol_admin(nombre, programa=None):
    """Rol que confiere administración: global o acotado a un programa."""
    grupo = Group.objects.create(name=nombre)
    RolMeta.objects.create(
        grupo=grupo,
        categoria=rbac.CATEGORIA_PROGRAMA if programa else rbac.CATEGORIA_SISTEMA,
        programa=programa,
        activo=True,
    )
    capacidades = rbac.CAPS_ADMIN_PROGRAMA if programa else rbac.CAPS_ADMINISTRACION
    for codigo in capacidades:
        grupo.permissions.add(_perm(codigo))
    return grupo


class CandadoDeUltimoAdminTests(TestCase):
    """G1b-09 · el check toma su candado, y lo toma **antes** de contar.

    En SQLite —la suite— `select_for_update()` es un no-op, así que la carrera no se
    puede reproducir acá y lo que se prueba es la presencia del candado, con el mismo
    criterio que `programas.tests.test_candados_concurrencia.ContratoDeCandadosTests`
    (RED-67). La carrera de verdad está abajo, con `@tag("mysql")`.
    """

    def setUp(self):
        self.admin = User.objects.create_user("admin-g1b09", password="x")
        self.admin.groups.add(_rol_admin("Administración"))

    def test_el_check_global_bloquea_las_capacidades_de_administracion(self):
        with candados_tomados(Permission.objects) as candados:
            rbac.asegurar_admin_restante()

        self.assertIn("rbac.py:tomar_candado_de_administracion", candados)

    def test_el_check_global_lee_los_usuarios_con_candado(self):
        """El ancla sola no alcanza: la lectura tiene que ver lo último commiteado.

        Con una lectura consistente, la segunda transacción sigue viendo activo al
        administrador que la primera acaba de desactivar y pasa el check igual.
        """
        with candados_tomados(User.objects) as candados:
            rbac.asegurar_admin_restante()

        self.assertIn("rbac.py:usuarios_que_administran", candados)

    def test_el_check_por_programa_toma_los_mismos_dos_candados(self):
        programa = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.admin.groups.add(_rol_admin("Admin Becas", programa=programa))

        with candados_tomados(Permission.objects) as anclas, candados_tomados(User.objects) as usuarios:
            rbac.asegurar_admin_restante(programa=programa.pk)

        self.assertIn("rbac.py:tomar_candado_de_administracion", anclas)
        self.assertIn("rbac.py:usuarios_que_administran_programa", usuarios)

    def test_el_check_sigue_decidiendo_lo_mismo(self):
        """El candado no cambia la respuesta: con admin pasa, sin admin lanza."""
        rbac.asegurar_admin_restante()  # no lanza

        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])

        with self.assertRaises(rbac.SinAdministradorError):
            rbac.asegurar_admin_restante()


@tag("mysql")
class CarreraDeUltimoAdminTests(MotorRealMixin, TransactionTestCase):
    """G1b-09 · capa 2: dos desactivaciones simultáneas, con el motor de verdad.

    Es la única capa que puede mostrar el bug. Con los dos últimos administradores
    activos, dos requests que desactivan uno cada una leen la foto de su propia
    transacción —en REPEATABLE READ, el otro sigue activo—, pasan el check y
    commitean: el sistema queda en cero administradores y no hay forma de volver
    desde la UI. Con el candado, la segunda espera al COMMIT de la primera, su
    lectura con candado ya la ve desactivada y revierte.
    """

    def setUp(self):
        super().setUp()
        self.rol = _rol_admin("Administración carrera")
        self.uno = User.objects.create_user("admin-carrera-1", password="x")
        self.dos = User.objects.create_user("admin-carrera-2", password="x")
        for usuario in (self.uno, self.dos):
            usuario.groups.add(self.rol)

    def _desactivar(self, usuario):
        def correr():
            try:
                with transaction.atomic():
                    usuario.is_active = False
                    usuario.save(update_fields=["is_active"])
                    rbac.asegurar_admin_restante()
                return "desactivado"
            except rbac.SinAdministradorError:
                return "frenado"

        return correr

    def _en_paralelo(self, *operaciones):
        barrera = threading.Barrier(len(operaciones), timeout=30)
        resultados, errores = [], []

        def correr(operacion):
            try:
                barrera.wait()
                resultados.append(operacion())
            except Exception as exc:
                errores.append(exc)
            finally:
                connections.close_all()

        hilos = [threading.Thread(target=correr, args=(op,)) for op in operaciones]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=60)
        self.assertEqual([repr(e) for e in errores], [])
        return resultados

    def test_dos_desactivaciones_simultaneas_no_dejan_el_sistema_sin_admin(self):
        resultados = self._en_paralelo(self._desactivar(self.uno), self._desactivar(self.dos))

        self.assertEqual(sorted(resultados), ["desactivado", "frenado"], "el candado no serializó")
        self.assertEqual(rbac.usuarios_que_administran().count(), 1)


class AltaRapidaEnCarreraTests(TestCase):
    """G1b-10 · la colisión de unicidad contesta 409 con el campo, no un 500.

    El `ModelForm` ya valida que el usuario y el DNI estén libres, así que a la
    `IntegrityError` solo se llega en una **carrera**: dos altas con el mismo valor
    pasan las dos validaciones y la segunda choca contra el índice único. El modal
    espera JSON (`data.errors`, `data.message`); con el 500 recibía HTML y le decía al
    operador «respuesta inesperada del servidor».
    """

    def setUp(self):
        # `es_admin_becas` falla cerrado sin la fila del programa (RED-56).
        becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.admin = User.objects.create_superuser("admin-g1b10", "a@b.com", "x")
        self.client.force_login(self.admin)
        coordinador = Group.objects.create(name=ROL_COORDINADOR)
        RolMeta.objects.create(
            grupo=coordinador, categoria=rbac.CATEGORIA_PROGRAMA, programa=becas, activo=True
        )

    def _post(self, **extra):
        datos = {
            "tipo": "coordinador",
            "username": "coord.nuevo",
            "first_name": "Coord",
            "last_name": "Nuevo",
            "email": "",
            "dni": "30111222",
            "password": "Clave-Seg-2026x",
            "password_confirm": "Clave-Seg-2026x",
        }
        datos.update(extra)
        return self.client.post(reverse("users:usuario_alta_rapida"), datos)

    def _con_colision(self, mensaje):
        return patch(
            "users.views.quick_create.UsuariosAdminService.create_user_from_form",
            side_effect=IntegrityError(mensaje),
        )

    def test_la_colision_de_username_contesta_409_con_el_campo(self):
        with self._con_colision("Duplicate entry 'coord.nuevo' for key 'auth_user.username'"):
            respuesta = self._post()

        self.assertEqual(respuesta.status_code, 409)
        cuerpo = respuesta.json()
        self.assertFalse(cuerpo["ok"])
        self.assertIn("username", cuerpo["errors"])
        self.assertTrue(cuerpo["message"])

    def test_la_colision_de_dni_apunta_al_dni(self):
        with self._con_colision("Duplicate entry '30111222' for key 'users_profile.dni'"):
            respuesta = self._post()

        self.assertEqual(respuesta.status_code, 409)
        self.assertIn("dni", respuesta.json()["errors"])

    def test_una_colision_que_no_se_puede_atribuir_no_culpa_a_ningun_campo(self):
        with self._con_colision("FOREIGN KEY constraint failed"):
            respuesta = self._post()

        self.assertEqual(respuesta.status_code, 409)
        self.assertIn("__all__", respuesta.json()["errors"])

    def test_la_respuesta_sigue_siendo_json(self):
        """Lo que el modal necesita para decir algo útil: un cuerpo que parsee."""
        with self._con_colision("Duplicate entry 'coord.nuevo' for key 'auth_user.username'"):
            respuesta = self._post()

        self.assertEqual(respuesta["Content-Type"], "application/json")

    def test_el_alta_feliz_sigue_creando_el_usuario(self):
        respuesta = self._post()

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()["ok"])
        self.assertTrue(User.objects.filter(username="coord.nuevo").exists())

    def test_el_duplicado_que_el_form_ya_atrapa_sigue_dando_400(self):
        """Sin carrera, el `ModelForm` lo frena antes: eso no cambia."""
        self._post()

        respuesta = self._post(dni="30111999")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("username", respuesta.json()["errors"])


class BotonEditarDeLaFichaTests(TestCase):
    """Seguimiento de #646 · la ficha no dibuja «Editar» sobre el rol propio.

    `RolDetailView` gatea con `puede_gestionar_rol` (ver) y el guardado con
    `puede_editar_rol` (editar), que para un admin de programa excluye sus propios
    roles (G1b-02). El listado ya lo escondía con `item.puede_editar`; la ficha no, y
    el link llevaba a un 302 con «no tenés permisos».
    """

    def setUp(self):
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        # Admin global presente para que la auto-protección del RBAC no salte.
        User.objects.create_user("root-ola7pr3", password="x").groups.add(_rol_admin("Administración"))
        self.rol_propio = _rol_admin("Becas — Admin de roles", programa=self.becas)
        self.otro_rol = Group.objects.create(name="Becas — Operador")
        RolMeta.objects.create(
            grupo=self.otro_rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.becas, activo=True
        )
        self.operador = User.objects.create_user("admin-roles-becas", password="x")
        self.operador.groups.add(self.rol_propio)
        self.client.force_login(self.operador)

    def _ficha(self, group):
        return self.client.get(reverse("users:rol_detalle", args=[group.pk]))

    def test_la_ficha_del_rol_propio_no_ofrece_editar(self):
        respuesta = self._ficha(self.rol_propio)

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.context["puede_editar"])
        self.assertNotContains(respuesta, reverse("users:rol_editar", args=[self.rol_propio.pk]))

    def test_y_la_vista_de_edicion_la_sigue_rechazando(self):
        """La contracara: el servidor manda, el botón solo deja de mentir."""
        respuesta = self.client.get(reverse("users:rol_editar", args=[self.rol_propio.pk]))

        self.assertEqual(respuesta.status_code, 302)

    def test_sobre_otro_rol_del_programa_el_boton_sigue_estando(self):
        respuesta = self._ficha(self.otro_rol)

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["puede_editar"])
        self.assertContains(respuesta, reverse("users:rol_editar", args=[self.otro_rol.pk]))

    def test_el_admin_global_sigue_editando_su_propio_rol(self):
        """Él sí es el que tiene que poder arreglarlo (G1b-02)."""
        root = User.objects.create_superuser("root-global-ola7pr3", "r@o.com", "x")
        self.client.force_login(root)

        respuesta = self._ficha(self.rol_propio)

        self.assertTrue(respuesta.context["puede_editar"])
        self.assertContains(respuesta, reverse("users:rol_editar", args=[self.rol_propio.pk]))
