"""Buscar y asignar a un territorial que ya tiene cuenta (Cambio 355, PR 2).

Cubre los dos endpoints del modal de alta rápida (``usuario_buscar_territorial`` y
``usuario_asignar_territorial``), el selector múltiple del ABM y el contrato del alta
rápida. Las guardas críticas (capacidad, enmascarado, DNI exacto) se verificaron por
mutación: romper la regla pone el test en rojo (ver el registro del Cambio 355).
"""

from io import StringIO
from unittest import mock

from django.contrib.auth.models import Group, Permission, User
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core import rbac
from programas.forms import ReasignarTerritorialForm
from programas.management.commands.seed_becas import ROL_COORDINADOR, ROL_TERRITORIAL
from programas.models import AsignacionCoordinador, AsignacionTerritorial, Segmento
from programas.services.autorizacion import usuarios_territoriales_becas
from users.forms import CustomUserChangeForm
from users.models import Profile
from users.services.territoriales import enmascarar_correo, enmascarar_dni

BUSCAR = "users:usuario_buscar_territorial"
ASIGNAR = "users:usuario_asignar_territorial"


class _Base(TestCase):
    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.seg_a = Segmento.objects.create(nombre="Seg A", cupo_maximo=10)
        self.seg_b = Segmento.objects.create(nombre="Seg B", cupo_maximo=10)
        self.seg_c = Segmento.objects.create(nombre="Seg C", cupo_maximo=10)
        self.rol_territorial = Group.objects.get(name=ROL_TERRITORIAL)
        self.rol_coordinador = Group.objects.get(name=ROL_COORDINADOR)
        self.coord_a = self._coordinador("coord_a", self.seg_a)
        self.coord_b = self._coordinador("coord_b", self.seg_b)
        self.admin = User.objects.create_superuser("admin_bus", "admin@example.com", "x")

        self.ajeno = self._territorial(
            "t_ajeno", "Marta", "Quiroga", "20111222", "marta@example.com", [self.seg_c, self.seg_b]
        )
        self.propio = self._territorial("t_propio", "Pedro", "Paz", "30111222", "pedro@example.com", [self.seg_a])
        self.inactivo = self._territorial(
            "t_inactivo", "Ines", "Inactiva", "31111222", "ines@example.com", [self.seg_c], activo=False
        )
        self.sin_nombre = self._territorial("sinnombre", "", "", "40111222", "sn@example.com", [self.seg_c])
        # Territorial que además coordina: no es «puro», un gestor acotado no lo ve.
        self.mixto = self._territorial("t_mixto", "Mixto", "Rolero", "41111222", "mixto@example.com", [self.seg_c])
        self.mixto.groups.add(self.rol_coordinador)
        # Un superusuario con el rol territorial: nunca sale en la búsqueda.
        self.super_terr = self._territorial("t_super", "Super", "Visor", "42111222", "su@example.com", [self.seg_c])
        User.objects.filter(pk=self.super_terr.pk).update(is_superuser=True)

    def _quitar_la_capacidad_territorial(self):
        """Deja a los coordinadores gestionando su segmento pero SIN ``becas.usuario.territorial``.

        Sin esto un usuario cualquiera ya rebota por el chequeo del segmento destino, y el
        test de la capacidad pasaría aunque el chequeo explícito no existiera.
        """
        permiso = Permission.objects.get(codename=rbac.codename_de("becas.usuario.territorial"))
        self.rol_coordinador.permissions.remove(permiso)
        self.assertFalse(rbac.puede(self.coord_a, "becas.usuario.territorial"))

    def _coordinador(self, username, segmento):
        usuario = User.objects.create_user(username, password="x")
        usuario.groups.add(self.rol_coordinador)
        AsignacionCoordinador.objects.create(segmento=segmento, coordinador=usuario)
        return usuario

    def _territorial(self, username, nombre, apellido, dni, email, segmentos, activo=True):
        usuario = User.objects.create_user(
            username, email=email, password="x", first_name=nombre, last_name=apellido, is_active=activo
        )
        usuario.groups.add(self.rol_territorial)
        Profile.objects.update_or_create(user=usuario, defaults={"dni": dni})
        for segmento in segmentos:
            AsignacionTerritorial.objects.create(territorial=usuario, segmento=segmento)
        return usuario

    def _buscar(self, operador, q, segmento=None):
        self.client.force_login(operador)
        return self.client.get(reverse(BUSCAR), {"q": q, "segmento_id": (segmento or self.seg_a).pk})

    def _ids(self, respuesta):
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        return {fila["id"] for fila in respuesta.json()["resultados"]}


class BuscarTerritorialTests(_Base):
    def test_dni_exacto_encuentra_con_o_sin_puntos(self):
        self.assertEqual(self._ids(self._buscar(self.coord_a, "20111222")), {self.ajeno.pk})
        self.assertEqual(self._ids(self._buscar(self.coord_a, "20.111.222")), {self.ajeno.pk})

    def test_dni_parcial_no_encuentra(self):
        # Mutación (c): permitir DNI parcial (``profile__dni__startswith``) pone esto en rojo.
        for parcial in ("2011122", "20111", "111222", "201"):
            self.assertEqual(self._ids(self._buscar(self.coord_a, parcial)), set(), parcial)

    def test_correo_exacto_encuentra_y_parcial_no(self):
        self.assertEqual(self._ids(self._buscar(self.coord_a, "marta@example.com")), {self.ajeno.pk})
        self.assertEqual(self._ids(self._buscar(self.coord_a, "MARTA@Example.com")), {self.ajeno.pk})
        self.assertEqual(self._ids(self._buscar(self.coord_a, "marta@exam")), set())
        self.assertEqual(self._ids(self._buscar(self.coord_a, "arta@example.com")), set())

    def test_nombre_y_apellido_con_coincidencia_parcial(self):
        self.assertEqual(self._ids(self._buscar(self.coord_a, "quir")), {self.ajeno.pk})
        self.assertEqual(self._ids(self._buscar(self.coord_a, "marta quir")), {self.ajeno.pk})
        self.assertEqual(self._ids(self._buscar(self.coord_a, "quiroga MARTA")), {self.ajeno.pk})
        self.assertEqual(self._ids(self._buscar(self.coord_a, "marta paz")), set())

    def test_el_username_no_sirve_para_buscar_ni_se_devuelve(self):
        self.assertEqual(self._ids(self._buscar(self.coord_a, "sinnombre")), set())
        respuesta = self._buscar(self.coord_a, "40111222")
        self.assertEqual(self._ids(respuesta), {self.sin_nombre.pk})
        self.assertEqual(respuesta.json()["resultados"][0]["nombre"], "(sin nombre)")
        self.assertNotIn("sinnombre", respuesta.content.decode())
        for fila in self._buscar(self.admin, "quir").json()["resultados"]:
            self.assertNotIn("username", fila)

    def test_enmascara_a_los_ajenos_y_no_a_los_del_alcance(self):
        # Mutación (b): dejar de enmascarar pone esto en rojo.
        fila = self._buscar(self.coord_a, "20111222").json()["resultados"][0]
        self.assertFalse(fila["en_alcance"])
        self.assertEqual(fila["dni"], "20.***.222")
        self.assertEqual(fila["email"], "m***@example.com")
        propio = self._buscar(self.coord_a, "30111222").json()["resultados"][0]
        self.assertTrue(propio["en_alcance"])
        self.assertEqual(propio["dni"], "30.111.222")
        self.assertEqual(propio["email"], "pedro@example.com")

    def test_alguno_de_sus_segmentos_en_el_alcance_alcanza_para_no_enmascarar(self):
        # El ajeno trabaja en C y en B: para coord_b (dueño de B) no se enmascara.
        fila = self._buscar(self.coord_b, "20111222", segmento=self.seg_b).json()["resultados"][0]
        self.assertTrue(fila["en_alcance"])
        self.assertEqual(fila["dni"], "20.111.222")
        self.assertEqual(fila["email"], "marta@example.com")

    def test_el_admin_nunca_enmascara(self):
        fila = self._buscar(self.admin, "20111222").json()["resultados"][0]
        self.assertTrue(fila["en_alcance"])
        self.assertEqual(fila["dni"], "20.111.222")
        self.assertEqual(fila["email"], "marta@example.com")

    def test_el_gestor_no_encuentra_no_puros_ni_superusuarios(self):
        self.assertEqual(self._ids(self._buscar(self.coord_a, "41111222")), set())
        self.assertEqual(self._ids(self._buscar(self.coord_a, "rolero")), set())
        self.assertEqual(self._ids(self._buscar(self.coord_a, "visor")), set())

    def test_el_admin_encuentra_al_no_puro_pero_no_al_superusuario(self):
        self.assertEqual(self._ids(self._buscar(self.admin, "rolero")), {self.mixto.pk})
        self.assertEqual(self._ids(self._buscar(self.admin, "visor")), set())

    def test_los_inactivos_aparecen_marcados(self):
        filas = self._buscar(self.coord_a, "inactiva").json()["resultados"]
        self.assertEqual([f["id"] for f in filas], [self.inactivo.pk])
        self.assertFalse(filas[0]["activo"])
        self.assertTrue(self._buscar(self.coord_a, "quiroga").json()["resultados"][0]["activo"])

    def test_ya_asignado_y_segmentos_ordenados(self):
        fila = self._buscar(self.coord_a, "pedro").json()["resultados"][0]
        self.assertTrue(fila["ya_asignado"])
        self.assertEqual(fila["segmentos"], ["Seg A"])
        ajeno = self._buscar(self.coord_a, "quiroga").json()["resultados"][0]
        self.assertFalse(ajeno["ya_asignado"])
        self.assertEqual(ajeno["segmentos"], ["Seg B", "Seg C"])

    def test_sin_la_capacidad_es_403(self):
        # Mutación (a): sacar el chequeo de ``becas.usuario.territorial`` pone esto en rojo.
        # Es el coordinador del segmento destino (el chequeo del segmento pasaría): lo único
        # que lo frena es la capacidad.
        self._quitar_la_capacidad_territorial()
        respuesta = self._buscar(self.coord_a, "quiroga")
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(respuesta.json()["ok"])
        self.assertIn("permiso", respuesta.json()["message"])
        # Un usuario cualquiera y un territorial (rol de campo) tampoco.
        for otro in (User.objects.create_user("sin_rol", password="x"), self.propio):
            self.assertEqual(self._buscar(otro, "quiroga").status_code, 403, otro.username)

    def test_el_anonimo_va_al_login(self):
        respuesta = self.client.get(reverse(BUSCAR), {"q": "quiroga", "segmento_id": self.seg_a.pk})
        self.assertEqual(respuesta.status_code, 302)

    def test_segmento_destino_ajeno_o_invalido_es_403(self):
        self.assertEqual(self._buscar(self.coord_a, "quiroga", segmento=self.seg_b).status_code, 403)
        self.client.force_login(self.coord_a)
        for valor in ("", "abc", "99999"):
            respuesta = self.client.get(reverse(BUSCAR), {"q": "quiroga", "segmento_id": valor})
            self.assertEqual(respuesta.status_code, 403, valor)

    def test_menos_de_tres_caracteres_es_400(self):
        for q in ("", "ab", "  ab  ", "1."):
            respuesta = self._buscar(self.coord_a, q)
            self.assertEqual(respuesta.status_code, 400, q)
            self.assertFalse(respuesta.json()["ok"])

    def test_solo_acepta_get(self):
        self.client.force_login(self.coord_a)
        self.assertEqual(self.client.post(reverse(BUSCAR), {"q": "quiroga"}).status_code, 405)

    def test_tope_de_diez_con_aviso_de_hay_mas(self):
        for i in range(11):
            self._territorial(f"mx{i}", f"Persona{i:02d}", "Masiva", f"5{i:07d}", f"m{i}@example.com", [self.seg_a])
        respuesta = self._buscar(self.coord_a, "masiva")
        self.assertEqual(len(respuesta.json()["resultados"]), 10)
        self.assertTrue(respuesta.json()["hay_mas"])
        self.assertFalse(self._buscar(self.coord_a, "persona00 masiva").json()["hay_mas"])

    def test_las_consultas_no_crecen_con_los_resultados(self):
        def consultas(q):
            self._buscar(self.coord_a, "pedro")  # calienta cachés de capacidades
            with CaptureQueriesContext(connection) as capturadas:
                self._buscar(self.coord_a, q)
            return len(capturadas)

        for i in range(8):
            self._territorial(f"nn{i}", f"Nene{i}", "Plus", f"6{i:07d}", f"n{i}@example.com", [self.seg_c, self.seg_a])
        self.assertEqual(consultas("nene0"), consultas("plus"))

    def test_limita_las_busquedas_por_operador(self):
        with mock.patch("users.views.quick_create.BUSQUEDAS_POR_MINUTO", 2):
            self.assertEqual(self._buscar(self.coord_a, "quiroga").status_code, 200)
            self.assertEqual(self._buscar(self.coord_a, "quiroga").status_code, 200)
            self.assertEqual(self._buscar(self.coord_a, "quiroga").status_code, 429)
            # Otro operador, otra cubeta.
            self.assertEqual(self._buscar(self.coord_b, "quiroga", segmento=self.seg_b).status_code, 200)

    def test_mascaras(self):
        self.assertEqual(enmascarar_dni("12345678"), "12.***.678")
        self.assertEqual(enmascarar_dni("1234567"), "12.***.567")
        self.assertEqual(enmascarar_dni(""), "")
        self.assertEqual(enmascarar_correo("carla@dominio.gob.ar"), "c***@dominio.gob.ar")
        self.assertEqual(enmascarar_correo(""), "")


class AsignarTerritorialTests(_Base):
    def _asignar(self, operador, usuario, segmento=None):
        self.client.force_login(operador)
        return self.client.post(reverse(ASIGNAR), {"user_id": usuario.pk, "segmento_id": (segmento or self.seg_a).pk})

    def test_crea_la_fila_con_quien_asigno_y_responde_con_el_contrato_del_alta(self):
        antes = AsignacionTerritorial.objects.filter(territorial=self.ajeno).count()
        respuesta = self._asignar(self.coord_a, self.ajeno)
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        cuerpo = respuesta.json()
        self.assertTrue(cuerpo["ok"])
        self.assertIn("message", cuerpo)
        self.assertEqual(cuerpo["user"]["id"], self.ajeno.pk)
        self.assertEqual(cuerpo["user"]["label"], "Marta Quiroga")
        self.assertEqual(cuerpo["user"]["segmento_id"], self.seg_a.pk)
        self.assertEqual(set(cuerpo["user"]["segmentos"]), {self.seg_a.pk, self.seg_b.pk, self.seg_c.pk})
        self.assertEqual(AsignacionTerritorial.objects.filter(territorial=self.ajeno).count(), antes + 1)
        fila = AsignacionTerritorial.objects.get(territorial=self.ajeno, segmento=self.seg_a)
        self.assertEqual(fila.asignado_por, self.coord_a)

    def test_es_idempotente(self):
        self._asignar(self.coord_a, self.ajeno)
        respuesta = self._asignar(self.coord_a, self.ajeno)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(AsignacionTerritorial.objects.filter(territorial=self.ajeno, segmento=self.seg_a).count(), 1)
        # Y no cambia al dueño ni quién lo asignó.
        self._asignar(self.admin, self.ajeno)
        self.assertEqual(
            AsignacionTerritorial.objects.get(territorial=self.ajeno, segmento=self.seg_a).asignado_por, self.coord_a
        )

    def test_despues_de_asignar_aparece_en_el_alta_de_relevamiento_de_esa_convocatoria(self):
        self.assertNotIn(self.ajeno, usuarios_territoriales_becas(segmento=self.seg_a))
        self._asignar(self.coord_a, self.ajeno)
        self.assertIn(self.ajeno, usuarios_territoriales_becas(segmento=self.seg_a))
        form = ReasignarTerritorialForm(segmento=self.seg_a)
        self.assertIn(self.ajeno, form.fields["territorial"].queryset)

    def test_sin_la_capacidad_es_403_y_no_escribe(self):
        self._quitar_la_capacidad_territorial()
        respuesta = self._asignar(self.coord_a, self.ajeno)
        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("permiso", respuesta.json()["message"])
        self.assertFalse(AsignacionTerritorial.objects.filter(territorial=self.ajeno, segmento=self.seg_a).exists())
        sin_rol = User.objects.create_user("sin_rol2", password="x")
        self.assertEqual(self._asignar(sin_rol, self.ajeno).status_code, 403)

    def test_segmento_destino_ajeno_es_403_y_no_escribe(self):
        respuesta = self._asignar(self.coord_a, self.ajeno, segmento=self.seg_b)
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(AsignacionTerritorial.objects.filter(territorial=self.ajeno).count(), 2)

    def test_un_target_fuera_del_universo_es_403(self):
        for fuera in (self.mixto, self.super_terr, self.coord_b):
            respuesta = self._asignar(self.coord_a, fuera)
            self.assertEqual(respuesta.status_code, 403, fuera.username)
            self.assertFalse(AsignacionTerritorial.objects.filter(territorial=fuera, segmento=self.seg_a).exists())
        # El admin tampoco asigna a un superusuario ni a quien no es territorial.
        self.assertEqual(self._asignar(self.admin, self.super_terr).status_code, 403)
        self.assertEqual(self._asignar(self.admin, self.coord_b).status_code, 403)

    def test_un_id_invalido_es_403(self):
        self.client.force_login(self.coord_a)
        for valor in ("", "abc", "999999"):
            respuesta = self.client.post(reverse(ASIGNAR), {"user_id": valor, "segmento_id": self.seg_a.pk})
            self.assertEqual(respuesta.status_code, 403, valor)

    def test_un_inactivo_es_409_y_no_escribe(self):
        respuesta = self._asignar(self.coord_a, self.inactivo)
        self.assertEqual(respuesta.status_code, 409)
        self.assertIn("administrador del programa", respuesta.json()["message"])
        self.assertFalse(AsignacionTerritorial.objects.filter(territorial=self.inactivo, segmento=self.seg_a).exists())

    def test_solo_acepta_post(self):
        self.client.force_login(self.coord_a)
        self.assertEqual(self.client.get(reverse(ASIGNAR)).status_code, 405)

    def test_limita_las_asignaciones_por_operador(self):
        with mock.patch("users.views.quick_create.ASIGNACIONES_POR_MINUTO", 1):
            self.assertEqual(self._asignar(self.coord_a, self.ajeno).status_code, 200)
            self.assertEqual(self._asignar(self.coord_a, self.ajeno).status_code, 429)


class AltaRapidaTerritorialTests(_Base):
    def _alta(self, operador, **extra):
        self.client.force_login(operador)
        datos = {
            "tipo": "territorial",
            "segmento_id": str(self.seg_a.pk),
            "username": "nuevo_terr",
            "email": "nuevo@example.com",
            "first_name": "Nuevo",
            "last_name": "Territorial",
            "dni": "33444555",
        }
        datos.update(extra)
        return self.client.post(reverse("users:usuario_alta_rapida"), datos)

    def test_devuelve_segmento_y_la_lista_de_segmentos(self):
        respuesta = self._alta(self.coord_a)
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        usuario = respuesta.json()["user"]
        self.assertEqual(usuario["segmento_id"], self.seg_a.pk)
        self.assertEqual(usuario["segmentos"], [self.seg_a.pk])
        nuevo = User.objects.get(username="nuevo_terr")
        self.assertEqual(
            list(nuevo.segmentos_territoriales.values_list("segmento_id", "asignado_por")),
            [(self.seg_a.pk, self.coord_a.pk)],
        )

    def test_coordinador_y_referente_devuelven_lista_vacia(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("users:usuario_alta_rapida"),
            {"tipo": "coordinador", "username": "coord_nuevo", "email": "cn@example.com", "dni": "34444555"},
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json()["user"]["segmentos"], [])

    def test_pide_la_capacidad_explicita_para_el_territorial(self):
        self._quitar_la_capacidad_territorial()
        respuesta = self._alta(self.coord_a)
        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("permiso", respuesta.json()["message"])
        self.assertFalse(User.objects.filter(username="nuevo_terr").exists())

    def test_un_dni_que_ya_existe_manda_a_buscarlo(self):
        respuesta = self._alta(self.coord_a, dni="20111222")
        self.assertEqual(respuesta.status_code, 400)
        cuerpo = respuesta.json()
        self.assertIn("buscalo en el paso anterior", cuerpo["message"])
        self.assertIn("Territorial", cuerpo["errors"]["dni"][0])
        self.assertFalse(User.objects.filter(username="nuevo_terr").exists())

    def test_el_error_generico_del_abm_no_cambia(self):
        form = CustomUserChangeForm(
            {"username": "x", "email": "x@example.com", "dni": "20111222", "groups": [str(self.rol_territorial.pk)]},
            instance=self.propio,
            operador=self.admin,
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["dni"], ["Ya existe un usuario registrado con este DNI."])

    def test_un_segmento_no_numerico_es_403_y_no_un_500(self):
        respuesta = self._alta(self.coord_a, segmento_id="abc")
        self.assertEqual(respuesta.status_code, 403)


class SelectorMultipleDelAbmTests(_Base):
    """Un territorial con A y B: el ABM ofrece los segmentos del operador y conserva los ajenos."""

    def setUp(self):
        super().setUp()
        self.comp = self._territorial(
            "t_comp", "Compartida", "Doble", "50111222", "comp@example.com", [self.seg_a, self.seg_b]
        )

    def _editar(self, operador, **extra):
        self.client.force_login(operador)
        datos = {
            "username": "t_comp",
            "email": "comp@example.com",
            "password": "",
            "first_name": "Compartida",
            "last_name": "Doble",
            "dni": "50111222",
            "groups": [str(self.rol_territorial.pk)],
        }
        datos.update(extra)
        return self.client.post(reverse("users:usuario_editar", args=[self.comp.pk]), datos)

    def _segmentos(self):
        return set(AsignacionTerritorial.objects.filter(territorial=self.comp).values_list("segmento_id", flat=True))

    def test_el_campo_es_un_multiple_con_los_segmentos_del_alcance(self):
        form = CustomUserChangeForm(instance=self.comp, operador=self.coord_b)
        campo = form.fields["segmentos_territoriales"]
        self.assertEqual(list(campo.queryset), [self.seg_b])
        self.assertEqual(campo.initial, [self.seg_b.pk])
        self.assertEqual([s.pk for s in form.segmentos_ajenos], [self.seg_a.pk])

    def test_el_admin_ve_todos_y_los_inactivos_quedan_como_ajenos(self):
        Segmento.objects.filter(pk=self.seg_b.pk).update(activo=False)
        form = CustomUserChangeForm(instance=self.comp, operador=self.admin)
        self.assertEqual(form.fields["segmentos_territoriales"].initial, [self.seg_a.pk])
        self.assertEqual([s.pk for s in form.segmentos_ajenos], [self.seg_b.pk])

    def test_el_gestor_agrega_y_quita_sus_segmentos_y_los_ajenos_se_conservan(self):
        coord_bc = self._coordinador("coord_bc", self.seg_b)
        AsignacionCoordinador.objects.create(segmento=self.seg_c, coordinador=coord_bc)
        # Suma C a lo que ya tiene (B): los dos propios quedan, A (ajeno) se conserva.
        resp = self._editar(coord_bc, segmentos_territoriales=[str(self.seg_b.pk), str(self.seg_c.pk)])
        self.assertEqual(resp.status_code, 302, resp.context["form"].errors if resp.context else None)
        self.assertEqual(self._segmentos(), {self.seg_a.pk, self.seg_b.pk, self.seg_c.pk})
        # Quita B: solo sale B.
        resp = self._editar(coord_bc, segmentos_territoriales=[str(self.seg_c.pk)])
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self._segmentos(), {self.seg_a.pk, self.seg_c.pk})

    def test_un_post_no_puede_agregar_un_segmento_fuera_del_alcance(self):
        resp = self._editar(self.coord_b, segmentos_territoriales=[str(self.seg_b.pk), str(self.seg_c.pk)])
        self.assertEqual(resp.status_code, 200)
        self.assertIn("segmentos_territoriales", resp.context["form"].errors)
        self.assertEqual(self._segmentos(), {self.seg_a.pk, self.seg_b.pk})

    def test_el_admin_elige_varios_y_solo_toca_lo_que_cambia(self):
        resp = self._editar(
            self.admin, segmentos_territoriales=[str(self.seg_a.pk), str(self.seg_b.pk), str(self.seg_c.pk)]
        )
        self.assertEqual(resp.status_code, 302, resp.context["form"].errors if resp.context else None)
        self.assertEqual(self._segmentos(), {self.seg_a.pk, self.seg_b.pk, self.seg_c.pk})
        # Las filas que ya estaban no se tocan (el dueño sigue siendo A).
        self.assertEqual(
            AsignacionTerritorial.objects.filter(territorial=self.comp).order_by("pk").first().segmento_id,
            self.seg_a.pk,
        )

    def test_el_admin_que_desmarca_solo_b_deja_a(self):
        # Antes (select simple) guardar borraba lo que el operador no veía.
        resp = self._editar(self.admin, segmentos_territoriales=[str(self.seg_a.pk)])
        self.assertEqual(resp.status_code, 302, resp.context["form"].errors if resp.context else None)
        self.assertEqual(self._segmentos(), {self.seg_a.pk})

    def test_el_admin_no_borra_segmentos_que_no_ve(self):
        Segmento.objects.filter(pk=self.seg_b.pk).update(activo=False)
        resp = self._editar(self.admin, segmentos_territoriales=[str(self.seg_a.pk)])
        self.assertEqual(resp.status_code, 302, resp.context["form"].errors if resp.context else None)
        self.assertEqual(self._segmentos(), {self.seg_a.pk, self.seg_b.pk})

    def test_el_set_final_exige_al_menos_un_segmento(self):
        resp = self._editar(self.admin, segmentos_territoriales=[])
        self.assertEqual(resp.status_code, 200)
        self.assertIn("segmentos_territoriales", resp.context["form"].errors)
        self.assertEqual(self._segmentos(), {self.seg_a.pk, self.seg_b.pk})

    def test_la_pantalla_muestra_el_selector_los_ajenos_y_el_aviso_del_no_dueno(self):
        self.client.force_login(self.coord_b)
        html = self.client.get(reverse("users:usuario_editar", args=[self.comp.pk])).content.decode()
        self.assertIn('class="nodo-checks', html)
        self.assertIn('name="segmentos_territoriales"', html)
        self.assertIn("Otros segmentos del territorial", html)
        self.assertIn("Seg A", html)
        self.assertIn("Datos de la cuenta bloqueados", html)
        self.assertIn("los administra el coordinador de Seg A o el administrador del programa", html)
        self.assertNotIn("Solo lo administra quien gestiona el segmento dueño", html)
        # «Limpiar» queda deshabilitado: no destilda los roles bloqueados.
        self.assertRegex(html, r'id="roles-limpiar"[^>]*\sdisabled')

    def test_el_dueno_no_ve_el_aviso_y_puede_limpiar(self):
        self.client.force_login(self.coord_a)
        html = self.client.get(reverse("users:usuario_editar", args=[self.comp.pk])).content.decode()
        self.assertNotIn("Datos de la cuenta bloqueados", html)
        self.assertNotRegex(html, r'id="roles-limpiar"[^>]*\sdisabled')
