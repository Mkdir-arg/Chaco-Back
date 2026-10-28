"""«Crear agente» desde el modal de asignar un relevamiento edilicio (Dispositivos · 28-oct-2026).

Lo que se fija acá, y por qué:

1. **El botón es de quien tiene `inspeccion.agente.crear` en Dispositivos**, en las tres pantallas
   (asignar y reasignar de P21, crear relevamiento de P4). Sin la capacidad no se dibuja.
2. **El endpoint no confía en el template**: 403 sin la capacidad, también si la tiene solo en un
   rol de **otro** programa.
3. **El alta solo da el rol sembrado de agente** (por clave). Un POST armado a mano —otro grupo,
   superusuario, staff— no escala.
4. **Correo obligatorio**, DNI repetido con mensaje propio, rol ausente o inseguro → 409, límite por operador.
5. El agente creado aparece en `agentes_asignables` sin más pasos.
6. El seed del rol es idempotente y respeta renombres; la migración del Administrador va y vuelve.
"""

import importlib
from io import StringIO

from django.apps import apps as apps_registry
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from core import rbac
from programas.management.commands.seed_dispositivos import asegurar_roles_dispositivos
from programas.models import InspeccionEdificio, Programa
from programas.services.inspecciones import (
    CAP_CREAR_AGENTE,
    CLAVE_ROL_AGENTE,
    NOMBRE_ROL_AGENTE,
    agentes_asignables,
)
from programas.tests.test_dispositivos_inspecciones import BaseInspecciones, _permiso
from users.forms import UserCreationForm
from users.models import Profile, RolMeta

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
BOTON = 'data-quick-user="agente"'
URL_ALTA = "users:usuario_alta_rapida"
CAPS_CREADOR = ("inspeccion.asignar", "inspeccion.agente.crear", "dispositivo.ver")


class BaseCrearAgente(BaseInspecciones):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.rol_agente, _ = asegurar_roles_dispositivos()
        self.creador = self._usuario("creador", CAPS_CREADOR, [self.parador])
        self.url = reverse(URL_ALTA)
        self._n = 0
        self._clientes = {}

    def _datos(self, **extra):
        self._n += 1
        datos = {
            "tipo": "agente",
            "username": f"agente{self._n}",
            "email": f"agente{self._n}@example.com",
            "first_name": "Ana",
            "last_name": f"Agente{self._n}",
            "dni": f"3011{self._n:04d}",
            "telefono": "3624000000",
        }
        datos.update(extra)
        return datos

    def _cliente(self, usuario):
        # Uno por usuario: el backoffice admite una sola sesión, y un segundo login invalida el primero.
        if usuario.pk not in self._clientes:
            self._clientes[usuario.pk] = Client()
            self._clientes[usuario.pk].force_login(usuario)
        return self._clientes[usuario.pk]

    def _post(self, datos=None, usuario=None):
        cliente = self._cliente(usuario or self.creador)
        return cliente.post(self.url, datos if datos is not None else self._datos(), **AJAX)

    def _get(self, url, usuario, **parametros):
        return self._cliente(usuario).get(url, parametros)

    def _con_capacidad_en_otro_programa(self, nombre):
        otro = Programa.objects.create(codigo="BECAS", nombre="Becas", tipo=Programa.TipoPrograma.BECAS)
        rol = Group.objects.create(name=f"Rol ajeno {nombre}")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=otro, activo=True)
        rol.permissions.add(_permiso("inspeccion.agente.crear"))
        return rol


class BotonTests(BaseCrearAgente):
    def setUp(self):
        super().setUp()
        self.en_curso = InspeccionEdificio.objects.create(
            edificio=self.predio,
            asignado_a=self.agente,
            creado_por=self.coordinador,
            fecha_vencimiento=self.vence,
        )

    def _pantallas(self, usuario):
        """Las tres pantallas: P21 con el modal pedido por parámetro y P4 con el suyo ya armado."""
        relevamientos = reverse("dispositivos:relevamientos")
        return {
            "asignar P21": self._get(relevamientos, usuario, asignar=self.edificio_cis.pk),
            "reasignar P21": self._get(relevamientos, usuario, reasignar=self.en_curso.pk),
            "crear P4": self._get(reverse("dispositivos:detalle", args=[self.cis.pk]), usuario, tab="infraestructura"),
        }

    def _usuario_total(self, nombre, capacidades):
        return self._usuario(nombre, capacidades, [self.parador, self.cis])

    def test_con_la_capacidad_el_boton_esta_en_las_tres_pantallas(self):
        usuario = self._usuario_total("creador_total", CAPS_CREADOR)
        for nombre, respuesta in self._pantallas(usuario).items():
            with self.subTest(nombre):
                self.assertEqual(respuesta.status_code, 200)
                self.assertTrue(respuesta.context["puede_crear_agente"])
                self.assertContains(respuesta, BOTON)
                self.assertContains(respuesta, 'id="quick-user-modal"')

    def test_el_selector_de_cada_boton_apunta_a_un_select_unico(self):
        usuario = self._usuario_total("creador_sel", CAPS_CREADOR)
        esperados = {
            "asignar P21": "#form-asignar-relevamiento select[name=asignado_a]",
            "reasignar P21": "#form-reasignar-relevamiento select[name=asignado_a]",
            "crear P4": "#form-crear-relevamiento select[name=asignado_a]",
        }
        for nombre, respuesta in self._pantallas(usuario).items():
            with self.subTest(nombre):
                self.assertContains(respuesta, f'data-user-select="{esperados[nombre]}"')

    def test_sin_la_capacidad_el_boton_no_se_dibuja(self):
        usuario = self._usuario_total("sin_cap", ("inspeccion.asignar", "dispositivo.ver"))
        for nombre, respuesta in self._pantallas(usuario).items():
            with self.subTest(nombre):
                self.assertEqual(respuesta.status_code, 200)
                self.assertFalse(respuesta.context["puede_crear_agente"])
                self.assertNotContains(respuesta, BOTON)
                self.assertNotContains(respuesta, 'id="quick-user-modal"')

    def test_la_capacidad_de_otro_programa_no_muestra_el_boton(self):
        usuario = self._usuario_total("cap_ajena", ("inspeccion.asignar", "dispositivo.ver"))
        usuario.groups.add(self._con_capacidad_en_otro_programa("boton"))
        usuario = User.objects.get(pk=usuario.pk)
        for nombre, respuesta in self._pantallas(usuario).items():
            with self.subTest(nombre):
                self.assertNotContains(respuesta, BOTON)


class EndpointTests(BaseCrearAgente):
    def test_sin_la_capacidad_es_403_y_no_crea_nada(self):
        operador = self._usuario("sin_cap_post", ("inspeccion.asignar", "dispositivo.ver"), [self.parador])
        antes = User.objects.count()

        respuesta = self._post(usuario=operador)

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(User.objects.count(), antes)

    def test_con_la_capacidad_en_otro_programa_es_403(self):
        operador = User.objects.create_user(username="ajeno", password="x")
        operador.groups.add(self._con_capacidad_en_otro_programa("post"))

        respuesta = self._post(usuario=User.objects.get(pk=operador.pk))

        self.assertEqual(respuesta.status_code, 403)

    def test_el_alta_crea_un_usuario_solo_con_el_rol_de_agente(self):
        datos = self._datos()

        respuesta = self._post(datos)

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        cuerpo = respuesta.json()
        self.assertTrue(cuerpo["ok"])
        usuario = User.objects.get(pk=cuerpo["user"]["id"])
        self.assertEqual(set(usuario.groups.values_list("pk", flat=True)), {self.rol_agente.pk})
        self.assertFalse(usuario.is_superuser)
        self.assertFalse(usuario.is_staff)
        self.assertEqual(usuario.email, datos["email"])
        self.assertEqual(usuario.profile.dni, datos["dni"])
        self.assertIn("Ana", cuerpo["user"]["label"])

    def test_el_agente_creado_aparece_entre_los_asignables(self):
        cuerpo = self._post().json()

        usuario = User.objects.get(pk=cuerpo["user"]["id"])
        self.assertIn(usuario, set(agentes_asignables(self.predio)))
        self.assertIn(usuario, set(agentes_asignables(self.edificio_cis)))

    def test_el_correo_es_obligatorio(self):
        respuesta = self._post(self._datos(email=""))

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("email", respuesta.json()["errors"])
        self.assertFalse(User.objects.filter(username__regex=r"^agente[0-9]").exists())

    def test_dni_repetido_manda_a_pedirle_el_rol_al_administrador(self):
        primero = self._datos()
        self.assertEqual(self._post(primero).status_code, 200)

        respuesta = self._post(self._datos(dni=primero["dni"]))

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("pedile al administrador del programa que le sume el rol de agente", respuesta.json()["message"])
        self.assertEqual(Profile.objects.filter(dni=primero["dni"]).count(), 1)

    def test_un_post_armado_a_mano_no_escala(self):
        otro_rol = Group.objects.create(name="Rol poderoso")
        RolMeta.objects.create(grupo=otro_rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        datos = self._datos(
            groups=[otro_rol.pk, self.rol_agente.pk],
            is_superuser="on",
            is_staff="on",
            is_active="on",
            password="Clave-Muy-Larga-1234",
            segmentos_territoriales="1",
            coordinador_referente="1",
        )

        respuesta = self._post(datos)

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        usuario = User.objects.get(pk=respuesta.json()["user"]["id"])
        self.assertEqual(set(usuario.groups.values_list("pk", flat=True)), {self.rol_agente.pk})
        self.assertFalse(usuario.is_superuser)
        self.assertFalse(usuario.is_staff)
        # La clave tipeada no entra: la genera el sistema y viaja por correo.
        self.assertFalse(usuario.check_password("Clave-Muy-Larga-1234"))

    def test_el_formulario_acotado_rechaza_cualquier_otro_rol(self):
        """La restricción vive también en el formulario, no solo en cómo la vista arma el POST."""
        otro_rol = Group.objects.create(name="Rol poderoso 2")
        RolMeta.objects.create(grupo=otro_rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        datos = {"username": "x1", "email": "x1@example.com", "groups": [otro_rol.pk], "dni": "30999888"}

        form = UserCreationForm(
            data=datos, operador=self.creador, roles_acotados=Group.objects.filter(pk=self.rol_agente.pk)
        )

        self.assertFalse(form.is_valid())
        self.assertIn("groups", form.errors)

    def test_sin_el_rol_sembrado_es_409(self):
        RolMeta.objects.filter(clave=CLAVE_ROL_AGENTE).update(clave=None)

        respuesta = self._post()

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.json()["message"], "El rol requerido no está configurado.")

    def test_el_rol_se_busca_por_clave_y_no_por_nombre(self):
        Group.objects.filter(pk=self.rol_agente.pk).update(name="Salida a campo")
        impostor = Group.objects.create(name=NOMBRE_ROL_AGENTE)
        RolMeta.objects.create(grupo=impostor, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)

        respuesta = self._post()

        self.assertEqual(respuesta.status_code, 200)
        usuario = User.objects.get(pk=respuesta.json()["user"]["id"])
        self.assertEqual(set(usuario.groups.values_list("pk", flat=True)), {self.rol_agente.pk})

    def test_si_al_rol_le_tildaron_una_capacidad_de_administracion_no_se_usa(self):
        self.rol_agente.permissions.add(_permiso("programa.usuario.administrar"))

        respuesta = self._post()

        self.assertEqual(respuesta.status_code, 409)
        self.assertFalse(User.objects.filter(username__regex=r"^agente[0-9]").exists())

    def test_un_rol_inactivo_es_409(self):
        RolMeta.objects.filter(clave=CLAVE_ROL_AGENTE).update(activo=False)

        self.assertEqual(self._post().status_code, 409)

    def test_limite_de_altas_por_operador(self):
        estados = [self._post().status_code for _ in range(21)]

        self.assertEqual(estados[:20], [200] * 20)
        self.assertEqual(estados[20], 429)

    def test_los_otros_tipos_siguen_pidiendo_su_capacidad(self):
        """El tipo nuevo no abrió los otros: con la capacidad de agente, territorial sigue en 403."""
        for tipo in ("territorial", "coordinador", "referente"):
            with self.subTest(tipo):
                respuesta = self._post(self._datos(tipo=tipo))
                self.assertEqual(respuesta.status_code, 403)


class CatalogoTests(TestCase):
    def test_la_capacidad_esta_en_el_catalogo_y_no_abre_el_abm_de_usuarios(self):
        self.assertIn(CAP_CREAR_AGENTE, rbac.codigos_de_capacidad())
        self.assertNotIn(CAP_CREAR_AGENTE, rbac.CAPS_ENTRADA_ABM_USUARIOS)

    def test_un_admin_de_programa_de_dispositivos_la_puede_delegar(self):
        self.assertIn(CAP_CREAR_AGENTE, rbac.capacidades_delegables("DISPOSITIVOS"))
        self.assertTrue(rbac.puede_asignar_capacidades("DISPOSITIVOS", [CAP_CREAR_AGENTE, "inspeccion.relevar"]))
        # Y no se ofrece fuera de Dispositivos.
        self.assertNotIn(CAP_CREAR_AGENTE, rbac.capacidades_delegables("BECAS"))


class SeedTests(TestCase):
    def test_sin_el_programa_no_falla_ni_siembra(self):
        self.assertIsNone(asegurar_roles_dispositivos())
        call_command("seed_dispositivos", stdout=StringIO())
        self.assertFalse(RolMeta.objects.filter(clave=CLAVE_ROL_AGENTE).exists())

    def test_es_idempotente_y_respeta_el_renombre_y_lo_tildado(self):
        programa = Programa.objects.create(
            codigo="DISPOSITIVOS", nombre="Dispositivos", tipo=Programa.TipoPrograma.DISPOSITIVOS
        )
        grupo, creado = asegurar_roles_dispositivos()
        self.assertTrue(creado)
        meta = grupo.meta
        self.assertEqual(
            (meta.categoria, meta.programa_id, meta.clave), (rbac.CATEGORIA_PROGRAMA, programa.pk, CLAVE_ROL_AGENTE)
        )
        self.assertEqual(
            set(grupo.permissions.values_list("codename", flat=True)), {rbac.codename_de("inspeccion.relevar")}
        )

        # El PM lo renombra, lo describe y le tilda algo más desde el ABM.
        Group.objects.filter(pk=grupo.pk).update(name="Agentes de campo")
        RolMeta.objects.filter(pk=meta.pk).update(descripcion="La mía")
        grupo.permissions.add(_permiso("dispositivo.ver"))

        for _ in range(2):
            call_command("seed_dispositivos", stdout=StringIO())

        self.assertEqual(RolMeta.objects.filter(clave=CLAVE_ROL_AGENTE).count(), 1)
        self.assertFalse(Group.objects.filter(name=NOMBRE_ROL_AGENTE).exists())
        grupo.refresh_from_db()
        grupo.meta.refresh_from_db()
        self.assertEqual(grupo.name, "Agentes de campo")
        self.assertEqual(grupo.meta.descripcion, "La mía")
        self.assertEqual(
            set(grupo.permissions.values_list("codename", flat=True)),
            {rbac.codename_de("inspeccion.relevar"), rbac.codename_de("dispositivo.ver")},
        )


class MigracionAdministradorTests(TestCase):
    def setUp(self):
        self.migracion = importlib.import_module("users.migrations.0043_administrador_inspeccion_agente_crear")
        self.admin = Group.objects.create(name="Administrador")
        RolMeta.objects.create(grupo=self.admin, categoria=rbac.CATEGORIA_BACKOFFICE, clave="sistema.administrador")
        self.otro = Group.objects.create(name="Intermedio")
        self.otro.permissions.add(_permiso("inspeccion.agente.crear"))

    def _tiene(self, grupo):
        return grupo.permissions.filter(codename="inspeccion_agente_crear").exists()

    def test_ida_y_reversa_solo_tocan_al_administrador(self):
        self.migracion.sembrar(apps_registry, None)
        self.migracion.sembrar(apps_registry, None)  # idempotente
        self.assertTrue(self._tiene(self.admin))
        self.assertTrue(self._tiene(self.otro))

        self.migracion.quitar(apps_registry, None)

        self.assertFalse(self._tiene(self.admin))
        self.assertTrue(self._tiene(self.otro))

    def test_sin_administrador_no_falla(self):
        self.admin.delete()
        self.migracion.sembrar(apps_registry, None)
        self.migracion.quitar(apps_registry, None)
