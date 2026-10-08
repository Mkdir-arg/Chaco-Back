"""SEC-06 — las capacidades ``becas.*`` solo valen dentro del Programa Becas.

PoC invertida (`poc/test_repro_seguridad.py::SEC06BecasCrossProgramTests`): el admin de
roles de **Dispositivos** veía los trece módulos ``becas_*`` en el árbol del ABM, se
tildaba ``becas.programa.administrar`` en un rol de su programa, y con eso bajaba el CSV
con DNI de cualquier convocatoria de Becas y entraba al proceso masivo. Los gates
evaluaban la capacidad **sin alcance**.

Tres candados, y los tres tienen test acá:

1. el catálogo ya no la **ofrece** (``core/rbac.py``: ``"programas": ("BECAS",)``);
2. los gates la evalúan **con alcance** (exports, proceso masivo, pendientes de RENAPER);
3. ``users.0031`` quita lo que haya quedado tildado, con reversa real.
"""

from datetime import date

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from core import rbac
from legajos.models import Ciudadano
from programas.models import (
    Convocatoria,
    Formulario,
    Programa,
    ProgramaSiis,
    Relevamiento,
    Segmento,
)
from users.models import Capacidad, RolMeta

EXPORTS = (
    "becas:convocatoria_export_beneficiarios",
    "becas:convocatoria_export_relevamientos",
    "becas:convocatoria_export_lista_espera",
)


def _perm(codigo):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct)


def _rol(nombre, capacidades, programa=None):
    grupo = Group.objects.create(name=nombre)
    RolMeta.objects.create(
        grupo=grupo,
        categoria=rbac.CATEGORIA_PROGRAMA if programa else rbac.CATEGORIA_SISTEMA,
        programa=programa,
        activo=True,
    )
    for codigo in capacidades:
        grupo.permissions.add(_perm(codigo))
    return grupo


def _usuario(username, *roles):
    usuario = User.objects.create_user(username, password="Clave-Seg-2026x")
    for rol in roles:
        usuario.groups.add(rol)
    return usuario


class Base(TestCase):
    def setUp(self):
        # El alcance de Becas se resuelve desde una clave cacheada (RED-80): sin
        # limpiarla, un test ve el ``Programa`` que sembró el anterior.
        cache.clear()
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.dispositivos = Programa.objects.create(codigo="DISPOSITIVOS", nombre="Dispositivos")
        self.programa_siis = ProgramaSiis.objects.create(nombre="Ñachec", siis_programa_id=79)
        segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=10, programa=self.programa_siis)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv",
            segmento=segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        territorial = _usuario("terri-sec06")
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=territorial,
            fecha_asignada=date(2026, 6, 1),
            zona="A",
        )
        ciudadano = Ciudadano.objects.create(dni="27888999", nombre="Beneficiaria", apellido="Secreta")
        self.caso = Formulario.objects.create(
            relevamiento=self.relevamiento,
            ciudadano=ciudadano,
            estado=Formulario.Estado.APROBADO,
        )
        # Admin global presente: la auto-protección del RBAC no tiene que saltar.
        User.objects.create_superuser("root-sec06", "root@x.test", "x")

    def _rol_de_dispositivos_con_becas(self):
        """El rol que la PoC conseguía armar desde el ABM. Acá se inyecta a mano: el
        catálogo ya no lo deja crear (lo prueba ``CatalogoNoOfreceBecasTests``), y lo que
        se mide es que los **gates** tampoco lo acepten."""
        return _rol(
            "Escalada Dispositivos",
            ["becas.programa.administrar", "becas.programa.proceso_masivo"],
            programa=self.dispositivos,
        )


class CatalogoNoOfreceBecasTests(Base):
    """Candado 1: el ABM de Roles ya no ofrece ``becas.*`` fuera de Becas."""

    def test_admin_dispositivos_no_ve_ni_asigna_capacidades_becas(self):
        rol_admin = _rol("Admin Dispositivos", ["programa.rol.administrar"], programa=self.dispositivos)
        operador = _usuario("adm-disp-sec06", rol_admin)
        self.client.force_login(operador)

        respuesta = self.client.get(reverse("users:rol_crear"))
        self.assertNotIn("becas.programa.administrar", respuesta.content.decode())

        guardado = self.client.post(
            reverse("users:rol_crear"),
            {
                "name": "Escalada",
                "descripcion": "",
                "categoria": rbac.CATEGORIA_PROGRAMA,
                "programa": str(self.dispositivos.pk),
                "capacidades": ["becas.programa.administrar", "becas.programa.proceso_masivo"],
            },
        )

        # El POST ni siquiera llega al `clean`: los códigos dejaron de estar en las
        # `choices` del campo, así que el formulario los rechaza con un error de campo
        # y el rol **no se crea**. Antes se creaba con las dos capacidades tildadas.
        self.assertEqual(guardado.status_code, 200)
        self.assertIn("capacidades", guardado.context["form"].errors)
        self.assertFalse(Group.objects.filter(name="Escalada").exists())

    def test_el_admin_de_becas_si_las_sigue_viendo(self):
        rol_admin = _rol("Admin Becas Roles", ["programa.rol.administrar"], programa=self.becas)
        self.client.force_login(_usuario("adm-becas-sec06", rol_admin))

        respuesta = self.client.get(reverse("users:rol_crear"))

        self.assertIn("becas.programa.administrar", respuesta.content.decode())

    def test_el_arbol_del_catalogo_lo_dice_sin_pasar_por_http(self):
        ofrecidas_disp = rbac.capacidades_de_programa_asignables(self.dispositivos)
        ofrecidas_becas = rbac.capacidades_de_programa_asignables(self.becas)

        self.assertNotIn("becas.programa.administrar", ofrecidas_disp)
        self.assertIn("dispositivo.ver", ofrecidas_disp)
        self.assertIn("becas.programa.administrar", ofrecidas_becas)
        self.assertNotIn("dispositivo.ver", ofrecidas_becas)


class ExportsDeConvocatoriaTests(Base):
    """Candado 2a: los tres CSV con DNI."""

    def test_un_rol_de_otro_programa_con_la_paraguas_no_exporta(self):
        operador = _usuario("escalada-export", self._rol_de_dispositivos_con_becas())
        self.assertTrue(rbac.puede(operador, "becas.programa.administrar"))  # sin alcance la tiene
        self.client.force_login(operador)

        for nombre in EXPORTS:
            with self.subTest(export=nombre):
                respuesta = self.client.get(reverse(nombre, args=[self.convocatoria.pk]))
                self.assertEqual(respuesta.status_code, 403)

    def test_el_admin_de_becas_sigue_exportando(self):
        rol = _rol("Admin Becas Export", ["becas.programa.administrar"], programa=self.becas)
        self.client.force_login(_usuario("adm-becas-export", rol))

        respuesta = self.client.get(reverse(EXPORTS[0], args=[self.convocatoria.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("27888999", respuesta.content.decode("utf-8", "ignore"))

    def test_un_coordinador_sin_la_paraguas_no_exporta(self):
        """Contraste que ya traía la PoC: el agujero no era «cualquier coordinador»."""
        rol = _rol("Coord Becas", ["becas.segmento.ver", "becas.relevamiento.ver"], programa=self.becas)
        self.client.force_login(_usuario("coord-export", rol))

        respuesta = self.client.get(reverse(EXPORTS[0], args=[self.convocatoria.pk]))

        self.assertEqual(respuesta.status_code, 403)

    def test_una_cuenta_sin_rol_no_exporta(self):
        self.client.force_login(_usuario("sin-rol-export"))

        self.assertEqual(self.client.get(reverse(EXPORTS[0], args=[self.convocatoria.pk])).status_code, 403)

    def test_el_anonimo_va_al_login(self):
        respuesta = self.client.get(reverse(EXPORTS[0], args=[self.convocatoria.pk]))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("users:login"), respuesta["Location"])

    def test_el_superusuario_exporta(self):
        self.client.force_login(User.objects.get(username="root-sec06"))

        self.assertEqual(self.client.get(reverse(EXPORTS[0], args=[self.convocatoria.pk])).status_code, 200)


class ProcesoMasivoTests(Base):
    """Candado 2b: las altas en lote a SIIS, que **no tienen baja**."""

    def test_rechaza_capacidad_de_rol_de_otro_programa(self):
        operador = _usuario("escalada-masivo", self._rol_de_dispositivos_con_becas())
        self.client.force_login(operador)

        pantalla = self.client.get(reverse("becas:proceso_masivo", args=[self.programa_siis.pk]))
        self.assertEqual(pantalla.status_code, 403)

        lanzar = self.client.post(
            reverse("becas:proceso_masivo_lanzar", args=[self.programa_siis.pk]),
            {"total_pedido": "1"},
        )
        self.assertEqual(lanzar.status_code, 403)

        frenar = self.client.post(reverse("becas:proceso_masivo_frenar", args=[self.programa_siis.pk]))
        self.assertEqual(frenar.status_code, 403)

    def test_el_de_becas_entra_a_la_pantalla(self):
        rol = _rol("Masivo Becas", ["becas.programa.proceso_masivo"], programa=self.becas)
        self.client.force_login(_usuario("masivo-becas", rol))

        respuesta = self.client.get(reverse("becas:proceso_masivo", args=[self.programa_siis.pk]))

        self.assertEqual(respuesta.status_code, 200)

    def test_una_cuenta_sin_rol_no_entra(self):
        self.client.force_login(_usuario("sin-rol-masivo"))

        respuesta = self.client.get(reverse("becas:proceso_masivo", args=[self.programa_siis.pk]))

        self.assertEqual(respuesta.status_code, 302)


class RenaperPendientesTests(Base):
    """Candado 2c: la bandeja de pendientes de RENAPER listaba **toda** la tabla."""

    def setUp(self):
        super().setUp()
        self.caso.validado_renaper = False
        self.caso.save(update_fields=["validado_renaper"])
        self.url = reverse("becas:renaper_pendientes")

    def test_un_rol_de_otro_programa_no_ve_ningun_caso(self):
        operador = _usuario("escalada-renaper", self._rol_de_dispositivos_con_becas())
        self.client.force_login(operador)

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(list(respuesta.context["formularios"]), [])

    def test_el_admin_de_becas_los_ve(self):
        rol = _rol("Admin Becas Renaper", ["becas.programa.administrar"], programa=self.becas)
        self.client.force_login(_usuario("adm-becas-renaper", rol))

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([f.pk for f in respuesta.context["formularios"]], [self.caso.pk])

    def test_una_cuenta_sin_rol_no_entra(self):
        self.client.force_login(_usuario("sin-rol-renaper"))

        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_el_anonimo_va_al_login(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("users:login"), respuesta["Location"])

    def test_el_superusuario_los_ve(self):
        self.client.force_login(User.objects.get(username="root-sec06"))

        self.assertEqual([f.pk for f in self.client.get(self.url).context["formularios"]], [self.caso.pk])


class BotonesDeExportEnLaPantallaTests(Base):
    """Ronda 2: lo que la pantalla ofrece tiene que ser lo que el gate acepta.

    El flag ``puede_reportes`` se calculaba con ``puede(...)`` **sin alcance**, o sea la
    regla vieja: para un Coordinador la solapa Reportes quedaba visible y sus tres CSV
    daban 403. Y el botón «Exportar beneficiarios (CSV)» de la solapa Beneficiarios no
    estaba bajo el flag, así que se lo veía hasta sin la solapa.
    """

    def setUp(self):
        super().setUp()
        from programas.models import AsignacionCoordinador

        self.url = reverse("becas:convocatoria_detalle", args=[self.convocatoria.pk])
        self.coordinador = _usuario(
            "coord-botones",
            _rol(
                "Coord Becas botones",
                ["becas.convocatoria.ver", "becas.segmento.ver", "becas.relevamiento.ver"],
                programa=self.becas,
            ),
        )
        AsignacionCoordinador.objects.create(segmento=self.convocatoria.segmento, coordinador=self.coordinador)

    def test_el_coordinador_no_ve_ningun_boton_de_export(self):
        self.client.force_login(self.coordinador)

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.context["puede_reportes"])
        self.assertNotIn("Exportar beneficiarios (CSV)", respuesta.content.decode())
        self.assertNotIn(
            reverse("becas:convocatoria_export_beneficiarios", args=[self.convocatoria.pk]),
            respuesta.content.decode(),
        )

    def test_y_el_export_le_sigue_contestando_403(self):
        """La contracara: el botón no está porque el gate no lo deja, no al revés."""
        self.client.force_login(self.coordinador)

        for nombre in EXPORTS:
            with self.subTest(export=nombre):
                self.assertEqual(
                    self.client.get(reverse(nombre, args=[self.convocatoria.pk])).status_code,
                    403,
                )

    def test_el_admin_de_becas_sigue_viendo_los_cuatro(self):
        rol = _rol(
            "Admin Becas botones",
            ["becas.programa.administrar", "becas.convocatoria.ver"],
            programa=self.becas,
        )
        self.client.force_login(_usuario("adm-becas-botones", rol))

        respuesta = self.client.get(self.url)
        cuerpo = respuesta.content.decode()

        self.assertTrue(respuesta.context["puede_reportes"])
        self.assertIn("Exportar beneficiarios (CSV)", cuerpo)
        for nombre in EXPORTS:
            self.assertIn(reverse(nombre, args=[self.convocatoria.pk]), cuerpo)
