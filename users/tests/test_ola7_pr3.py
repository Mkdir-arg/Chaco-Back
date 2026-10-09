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
import time
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, connections, transaction
from django.test import TestCase, TransactionTestCase, tag
from django.urls import reverse

from core import rbac
from core.tests.candados import candados_tomados
from core.tests.test_motor_real import MotorRealMixin
from programas.management.commands.seed_becas import ROL_COORDINADOR
from programas.models import Programa
from users.models import Capacidad, RolMeta
from users.services.roles import RolesAdminService


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
    """G1b-09 · el candado existe y se toma **antes** de escribir.

    En SQLite —la suite— `select_for_update()` es un no-op, así que la carrera no se
    puede reproducir acá y lo que se prueba es el contrato: que el candado se pida, y
    que se pida antes de tocar la fila. Mismo criterio que
    `programas.tests.test_candados_concurrencia.ContratoDeCandadosTests` (RED-67). La
    carrera de verdad está abajo, con `@tag("mysql")`.

    El **orden** no es un detalle de estilo. Tomarlo después del `UPDATE` serializa
    igual, pero la segunda transacción sigue leyendo su propia foto —en REPEATABLE READ
    una lectura con candado no la refresca— y pasa el check; y encima deadlockea contra
    MariaDB, porque cada una tendría tomada la fila del usuario que desactivó.
    """

    def setUp(self):
        self.admin = User.objects.create_user("admin-g1b09", password="x")
        self.admin.groups.add(_rol_admin("Administración"))
        self.operador = User.objects.create_superuser("root-g1b09", "r@o.com", "x")
        self.client.force_login(self.operador)

    def test_el_check_toma_el_candado_sobre_las_capacidades_de_administracion(self):
        with candados_tomados(Permission.objects) as candados:
            rbac.asegurar_admin_restante()

        self.assertIn("rbac.py:tomar_candado_de_administracion", candados)

    def test_el_check_por_programa_toma_el_mismo_candado(self):
        programa = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.admin.groups.add(_rol_admin("Admin Becas", programa=programa))

        with candados_tomados(Permission.objects) as candados:
            rbac.asegurar_admin_restante(programa=programa.pk)

        self.assertIn("rbac.py:tomar_candado_de_administracion", candados)

    def test_el_toggle_toma_el_candado_antes_de_desactivar(self):
        """El orden, probado por lo que la base todavía dice cuando se pide el candado.

        El espía lee la fila **desde la base** en el momento del candado: si el `UPDATE`
        ya hubiera pasado, vería `is_active=False`.
        """
        visto = []
        original = rbac.tomar_candado_de_administracion

        def espiar():
            # Solo la primera vez: `asegurar_admin_restante` lo vuelve a tomar al final.
            if not visto:
                visto.append(User.objects.filter(pk=self.admin.pk).values_list("is_active", flat=True).first())
            return original()

        with patch("core.rbac.tomar_candado_de_administracion", espiar):
            self.client.post(reverse("users:usuario_toggle", args=[self.admin.pk]))

        self.assertEqual(visto, [True], "el candado se tomó después del UPDATE")
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_active)

    def test_desactivar_un_rol_toma_el_candado_antes_de_guardarlo(self):
        rol = _rol_admin("Rol que se desactiva")
        User.objects.create_user("otro-admin-g1b09", password="x").groups.add(_rol_admin("Otra administración"))
        visto = []
        original = rbac.tomar_candado_de_administracion

        def espiar():
            if not visto:
                visto.append(RolMeta.objects.filter(grupo=rol).values_list("activo", flat=True).first())
            return original()

        with patch("core.rbac.tomar_candado_de_administracion", espiar):
            RolesAdminService.toggle_activo(rol)

        self.assertEqual(visto, [True], "el candado se tomó después de guardar la RolMeta")
        self.assertFalse(RolMeta.objects.get(grupo=rol).activo)

    def test_el_check_sigue_decidiendo_lo_mismo(self):
        """El candado no cambia la respuesta: con admin pasa, sin admin lanza."""
        rbac.asegurar_admin_restante()  # no lanza

        for usuario in (self.admin, self.operador):
            usuario.is_active = False
            usuario.save(update_fields=["is_active"])

        with self.assertRaises(rbac.SinAdministradorError):
            rbac.asegurar_admin_restante()


@tag("mysql")
class CarreraDeUltimoAdminTests(MotorRealMixin, TransactionTestCase):
    """G1b-09 · capa 2: dos desactivaciones a la vez, con el motor de verdad.

    Es la única capa que puede mostrar el bug. Dos requests que desactivan cada una a
    uno de los dos últimos administradores leen la foto de **su** transacción, ven al
    otro todavía activo, pasan el check y commitean: el sistema queda en cero
    administradores y no hay forma de volver desde la UI. Medido contra
    `mariadb:10.11` con las dos transacciones sincronizadas entre el `UPDATE` y el
    check: sin candado, las dos dicen «desactivado» y quedan **0** administradores.

    Ese escenario no se puede escribir como test del código arreglado —con el candado
    el segundo hilo nunca llega al punto de sincronización, porque está esperando—, así
    que lo que se afirma acá es el mecanismo, que es igual de discriminante: **gana el
    que arrancó primero, y el segundo espera**. Medido en los dos árboles:

    ==================  ==============================  ==============================
    hilo                sin candado (`development`)     con candado (este PR)
    ==================  ==============================  ==============================
    A (arranca a t=0)   frenado, 1,03 s                 **desactivado**, 1,01 s
    B (arranca a t=0,2) **desactivado**, 0,01 s         frenado, **0,81 s** (esperó)
    ==================  ==============================  ==============================

    Sin el candado B no espera nada y se cuela mientras A tiene la transacción abierta;
    A termina revertido aunque fue el primero. Las dos afirmaciones de abajo —quién gana
    y cuánto esperó el segundo— se ponen rojas con cualquiera de las dos mitades fuera.

    `_desactivar` reproduce la forma exacta de `UserToggleActivoView.post`: candado,
    lectura, escritura, check.
    """

    #: Cuánto retiene la primera transacción antes de chequear y commitear.
    RETENCION = 1.0
    #: Cuánto tarda en arrancar la segunda. Bastante menos que `RETENCION`, para que
    #: la espera que se mide sea la del candado y no la del arranque.
    DEMORA = 0.2

    def setUp(self):
        super().setUp()
        self.rol = _rol_admin("Administración carrera")
        self.uno = User.objects.create_user("admin-carrera-1", password="x")
        self.dos = User.objects.create_user("admin-carrera-2", password="x")
        for usuario in (self.uno, self.dos):
            usuario.groups.add(self.rol)
        self.resultados = {}

    def _desactivar(self, etiqueta, usuario, antes=0.0, retener=0.0):
        """Un hilo con la forma de `UserToggleActivoView.post`, instrumentado."""

        def hilo():
            try:
                time.sleep(antes)
                arranque = time.monotonic()
                with transaction.atomic():
                    rbac.tomar_candado_de_administracion()
                    usuario.is_active = False
                    usuario.save(update_fields=["is_active"])
                    time.sleep(retener)
                    rbac.asegurar_admin_restante()
                self.resultados[etiqueta] = ("desactivado", time.monotonic() - arranque)
            except rbac.SinAdministradorError:
                self.resultados[etiqueta] = ("frenado", time.monotonic() - arranque)
            except Exception as exc:  # noqa: BLE001 — se reporta como fallo del test
                self.resultados[etiqueta] = (f"{type(exc).__name__}: {exc}", 0.0)
            finally:
                connections.close_all()

        return threading.Thread(target=hilo)

    def test_la_segunda_desactivacion_espera_y_la_primera_gana(self):
        hilos = [
            self._desactivar("primera", self.uno, retener=self.RETENCION),
            self._desactivar("segunda", self.dos, antes=self.DEMORA),
        ]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=60)

        desenlace = {etiqueta: valor[0] for etiqueta, valor in self.resultados.items()}
        self.assertEqual(
            desenlace,
            {"primera": "desactivado", "segunda": "frenado"},
            "sin el candado la segunda se cuela mientras la primera tiene la transacción abierta",
        )
        espera = self.resultados["segunda"][1]
        self.assertGreater(
            espera,
            (self.RETENCION - self.DEMORA) / 2,
            f"la segunda tardó {espera:.2f} s: no esperó el candado de la primera",
        )

    def test_queda_un_administrador(self):
        """La consecuencia: el sistema nunca se queda sin nadie que pueda entrar."""
        hilos = [
            self._desactivar("primera", self.uno, retener=self.RETENCION),
            self._desactivar("segunda", self.dos, antes=self.DEMORA),
        ]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=60)

        self.assertEqual(rbac.usuarios_que_administran().count(), 1)
        self.dos.refresh_from_db()
        self.assertTrue(self.dos.is_active, "la transacción frenada tiene que revertir su UPDATE")


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
        RolMeta.objects.create(grupo=coordinador, categoria=rbac.CATEGORIA_PROGRAMA, programa=becas, activo=True)

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
        RolMeta.objects.create(grupo=self.otro_rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.becas, activo=True)
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
