"""«Buscar agente» en el modal de asignar un relevamiento edilicio (Dispositivos · 29-oct-2026, Cambio 397).

Lo que se fija acá, y por qué:

1. **Solo se busca entre quienes tienen el rol sembrado de agente**: un territorial de Becas o un
   usuario sin el rol no aparecen, aunque coincidan por nombre, DNI o correo.
2. **La búsqueda no da nada**: elegir un resultado no crea ni modifica grupos ni permisos.
3. **La asignabilidad sale de la fuente del selector** (`agentes_asignables`): el personal del edificio,
   el inactivo y quien perdió la capacidad de relevar salen marcados con su motivo, con DNI y correo
   enmascarados.
4. **El endpoint no confía en el template**: 403 sin la capacidad (también la de otro programa) o sin
   alcance sobre el edificio, 400 sin edificio o con pocos caracteres, 429 por operador.
5. El modal lleva el edificio del botón y los textos del paso de búsqueda por tipo.
"""

from django.contrib.auth.models import Group, User
from django.test import Client
from django.urls import reverse

from core import rbac
from programas.models import AsignacionDispositivo, InspeccionEdificio
from programas.services.buscador_agentes import (
    MOTIVO_AGENTE_ES_PERSONAL,
    MOTIVO_AGENTE_INACTIVO,
    MOTIVO_AGENTE_NO_RELEVA,
)
from programas.services.inspecciones import agentes_asignables
from programas.tests.test_dispositivos_crear_agente import BaseCrearAgente
from users.models import Profile, RolMeta

URL = "users:usuario_buscar_agente"


class BaseBuscarAgente(BaseCrearAgente):
    def setUp(self):
        super().setUp()
        self.carla = self._con_rol_de_agente("carla", "Carla", "Quiroga", "30111222", "carla@example.com")
        self.url_buscar = reverse(URL)

    def _persona(self, username, nombre, apellido, dni, email):
        usuario = User.objects.create_user(
            username=username, password="x", first_name=nombre, last_name=apellido, email=email
        )
        Profile.objects.update_or_create(user=usuario, defaults={"dni": dni})
        return User.objects.get(pk=usuario.pk)

    def _con_rol_de_agente(self, *args):
        usuario = self._persona(*args)
        usuario.groups.add(self.rol_agente)
        return User.objects.get(pk=usuario.pk)

    def _buscar(self, q, edificio=None, usuario=None, **extra):
        parametros = {"q": q}
        if edificio is not False:
            parametros["edificio_id"] = (edificio or self.predio).pk
        parametros.update(extra)
        return self._cliente(usuario or self.creador).get(self.url_buscar, parametros)

    def _ids(self, respuesta):
        return {fila["id"] for fila in respuesta.json()["resultados"]}


class UniversoTests(BaseBuscarAgente):
    def test_encuentra_al_agente_por_nombre_apellido_dni_y_correo(self):
        for texto in ("Quiroga", "carl qui", "30.111.222", "CARLA@example.com"):
            with self.subTest(texto):
                respuesta = self._buscar(texto)
                self.assertEqual(respuesta.status_code, 200, respuesta.content)
                self.assertEqual(self._ids(respuesta), {self.carla.pk})

    def test_solo_devuelve_a_quien_tiene_el_rol_de_agente(self):
        territorial = self._persona("terri", "Carla", "Quiroga Territorial", "30111333", "terri@example.com")
        territorial.groups.add(Group.objects.create(name="Becas — Territorial de prueba"))
        sin_rol = self._persona("sinrol", "Carla", "Quiroga Sinrol", "30111444", "sinrol@example.com")
        # Puede relevar por otro rol del programa, pero no es el agente sembrado: no entra.
        con_otro_rol = self._usuario("relevador", ("inspeccion.relevar",))
        con_otro_rol.first_name, con_otro_rol.last_name = "Carla", "Quiroga Relevador"
        con_otro_rol.save()

        ids = self._ids(self._buscar("Quiroga"))

        self.assertEqual(ids, {self.carla.pk})
        for ajeno in (territorial, sin_rol, con_otro_rol):
            self.assertNotIn(ajeno.pk, ids)

    def test_un_superusuario_con_el_rol_no_aparece(self):
        self.carla.is_superuser = True
        self.carla.save()
        self.assertEqual(self._ids(self._buscar("Quiroga")), set())

    def test_dni_y_correo_son_exactos_no_parciales(self):
        self.assertEqual(self._ids(self._buscar("3011")), set())
        self.assertEqual(self._ids(self._buscar("carla@exam")), set())

    def test_el_tope_de_resultados_avisa_que_hay_mas(self):
        for n in range(12):
            self._con_rol_de_agente(f"mas{n}", "Mara", f"Lopez{n:02d}", f"3022{n:04d}", f"mas{n}@example.com")
        cuerpo = self._buscar("Lopez").json()
        self.assertEqual(len(cuerpo["resultados"]), 10)
        self.assertTrue(cuerpo["hay_mas"])

    def _foto(self):
        return (
            set(Group.objects.values_list("pk", "name")),
            {(g.pk, frozenset(g.permissions.values_list("pk", flat=True))) for g in Group.objects.all()},
            {(u.pk, frozenset(u.groups.values_list("pk", flat=True))) for u in User.objects.all()},
        )

    def test_buscar_no_crea_ni_modifica_grupos_ni_permisos(self):
        antes = self._foto()
        self._buscar("Quiroga")
        self._buscar("carla@example.com")
        self.assertEqual(antes, self._foto())


class AsignabilidadTests(BaseBuscarAgente):
    def _fila(self, usuario, q="Quiroga", edificio=None):
        filas = self._buscar(q, edificio).json()["resultados"]
        return next(f for f in filas if f["id"] == usuario.pk)

    def test_un_agente_externo_es_asignable_y_esta_en_el_selector(self):
        fila = self._fila(self.carla)
        self.assertTrue(fila["asignable"])
        self.assertEqual(fila["motivo"], "")
        self.assertEqual(fila["dni"], "30.111.222")
        self.assertEqual(fila["email"], "carla@example.com")
        self.assertIn(self.carla, set(agentes_asignables(self.predio)))

    def test_el_personal_del_edificio_sale_no_asignable_con_motivo_y_enmascarado(self):
        propio = self._con_rol_de_agente("propia", "Paula", "Quiroga Propia", "30111555", "propia@example.com")
        rol_institucion = Group.objects.create(name="Rol institucion propia")
        RolMeta.objects.create(
            grupo=rol_institucion, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True
        )
        propio.groups.add(rol_institucion)
        AsignacionDispositivo.objects.create(dispositivo=self.parador, rol=rol_institucion, activo=True)

        fila = self._fila(propio)

        self.assertFalse(fila["asignable"])
        self.assertEqual(fila["motivo"], MOTIVO_AGENTE_ES_PERSONAL)
        self.assertEqual(fila["dni"], "30.***.555")
        self.assertEqual(fila["email"], "p***@example.com")
        self.assertNotIn(propio, set(agentes_asignables(self.predio)))

    def test_el_personal_de_un_edificio_si_es_asignable_a_otro(self):
        propio = self._con_rol_de_agente("propia", "Paula", "Quiroga Propia", "30111555", "propia@example.com")
        rol_institucion = Group.objects.create(name="Rol institucion propia")
        RolMeta.objects.create(
            grupo=rol_institucion, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True
        )
        propio.groups.add(rol_institucion)
        AsignacionDispositivo.objects.create(dispositivo=self.cis, rol=rol_institucion, activo=True)
        usuario = self._usuario(
            "creador_total",
            ("inspeccion.asignar", "inspeccion.agente.crear", "dispositivo.ver"),
            [self.parador, self.cis],
        )

        en_su_edificio = self._buscar("Paula", edificio=self.edificio_cis, usuario=usuario).json()["resultados"][0]
        en_otro = self._buscar("Paula", edificio=self.predio, usuario=usuario).json()["resultados"][0]

        self.assertFalse(en_su_edificio["asignable"])
        self.assertTrue(en_otro["asignable"])

    def test_un_agente_inactivo_sale_no_asignable(self):
        self.carla.is_active = False
        self.carla.save()
        fila = self._fila(self.carla)
        self.assertFalse(fila["asignable"])
        self.assertFalse(fila["activo"])
        self.assertEqual(fila["motivo"], MOTIVO_AGENTE_INACTIVO)
        self.assertEqual(fila["dni"], "30.***.222")

    def test_si_el_rol_de_agente_esta_inactivo_no_releva(self):
        meta = self.rol_agente.meta
        meta.activo = False
        meta.save()
        fila = self._fila(self.carla)
        self.assertFalse(fila["asignable"])
        self.assertEqual(fila["motivo"], MOTIVO_AGENTE_NO_RELEVA)


class EndpointTests(BaseBuscarAgente):
    def test_sin_la_capacidad_es_403(self):
        usuario = self._usuario("sin_cap", ("inspeccion.asignar", "dispositivo.ver"), [self.parador])
        self.assertEqual(self._buscar("Quiroga", usuario=usuario).status_code, 403)

    def test_la_capacidad_en_otro_programa_es_403(self):
        usuario = self._usuario("cap_ajena", ("inspeccion.asignar", "dispositivo.ver"), [self.parador])
        usuario.groups.add(self._con_capacidad_en_otro_programa("buscar"))
        usuario = User.objects.get(pk=usuario.pk)
        self.assertEqual(self._buscar("Quiroga", usuario=usuario).status_code, 403)

    def test_un_edificio_fuera_de_alcance_es_403(self):
        self.assertEqual(self._buscar("Quiroga", edificio=self.edificio_cis).status_code, 403)
        self.assertEqual(self._buscar("Quiroga", edificio=False, edificio_id="99999").status_code, 403)

    def test_sin_edificio_o_con_edificio_invalido_es_400(self):
        self.assertEqual(self._buscar("Quiroga", edificio=False).status_code, 400)
        self.assertEqual(self._buscar("Quiroga", edificio=False, edificio_id="abc").status_code, 400)

    def test_pide_al_menos_tres_caracteres(self):
        respuesta = self._buscar("ca")
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(respuesta.json()["ok"])

    def test_anonimo_no_entra(self):
        self.assertIn(Client().get(self.url_buscar, {"q": "Quiroga"}).status_code, (302, 401, 403))

    def test_solo_get(self):
        self.assertEqual(self._cliente(self.creador).post(self.url_buscar, {"q": "Quiroga"}).status_code, 405)

    def test_limite_de_busquedas_por_operador(self):
        estados = [self._buscar("Quiroga").status_code for _ in range(31)]
        self.assertEqual(estados[:30], [200] * 30)
        self.assertEqual(estados[30], 429)

    def test_la_cubeta_es_por_operador(self):
        for _ in range(31):
            self._buscar("Quiroga")
        otro = self._usuario(
            "creador2", ("inspeccion.asignar", "inspeccion.agente.crear", "dispositivo.ver"), [self.parador]
        )
        self.assertEqual(self._buscar("Quiroga", usuario=otro).status_code, 200)


class ModalTests(BaseBuscarAgente):
    def test_el_boton_lleva_el_edificio_en_las_tres_pantallas(self):
        en_curso = InspeccionEdificio.objects.create(
            edificio=self.predio, asignado_a=self.agente, creado_por=self.coordinador, fecha_vencimiento=self.vence
        )
        usuario = self._usuario(
            "creador_total",
            ("inspeccion.asignar", "inspeccion.agente.crear", "dispositivo.ver"),
            [self.parador, self.cis],
        )
        relevamientos = reverse("dispositivos:relevamientos")
        cliente = self._cliente(usuario)
        asignar = cliente.get(relevamientos, {"asignar": self.edificio_cis.pk})
        reasignar = cliente.get(relevamientos, {"reasignar": en_curso.pk})
        crear = cliente.get(reverse("dispositivos:detalle", args=[self.cis.pk]), {"tab": "infraestructura"})

        self.assertContains(asignar, f'data-edificio-id="{self.edificio_cis.pk}"')
        self.assertContains(reasignar, f'data-edificio-id="{self.predio.pk}"')
        self.assertContains(crear, 'data-edificio-source="#form-crear-relevamiento [name=edificio]"')
        for respuesta in (asignar, reasignar, crear):
            self.assertContains(respuesta, reverse(URL))
            self.assertContains(respuesta, "No encontramos agentes con esos datos")
            self.assertContains(respuesta, "Crear agente nuevo")
