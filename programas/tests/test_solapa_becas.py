from datetime import date
from io import StringIO

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core import rbac
from legajos.models import Ciudadano
from programas.models import Convocatoria, Formulario, ListaEspera, ProgramaSiis, Relevamiento, Segmento
from programas.services.solapas import SolapasService
from users.models import Capacidad, RolMeta


def _permiso(codigo):
    return Permission.objects.get(
        content_type=ContentType.objects.get_for_model(Capacidad),
        codename=rbac.codename_de(codigo),
    )


class SolapaBecasTests(TestCase):
    def test_resumen_sin_formularios_ejecuta_una_sola_query(self):
        ciudadano = Ciudadano.objects.create(dni="39000202", nombre="Cora", apellido="Sin becas")

        with self.assertNumQueries(1):
            resumen = SolapasService.obtener_resumen_becas_ciudadano(ciudadano)

        self.assertEqual(resumen["formularios"], [])

    def test_resumen_opcional_conserva_solapa_y_badge(self):
        territorial = User.objects.create_user(username="territorial-solapa-becas")
        ciudadano = Ciudadano.objects.create(dni="39000201", nombre="Beto", apellido="Becas")
        programa = ProgramaSiis.objects.create(nombre="Programa becas", siis_programa_id=902)
        segmento = Segmento.objects.create(programa=programa, nombre="Segmento becas", cupo_maximo=10)
        convocatoria = Convocatoria.objects.create(
            nombre="Convocatoria becas",
            segmento=segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        relevamiento = Relevamiento.objects.create(
            convocatoria=convocatoria,
            territorial=territorial,
            fecha_asignada=date(2026, 6, 1),
            fecha_hasta=date(2026, 6, 30),
            zona="Zona becas",
        )
        formulario = Formulario.objects.create(
            relevamiento=relevamiento,
            ciudadano=ciudadano,
            celular="3624000000",
            email_contacto="solapa@example.com",
        )
        ListaEspera.objects.create(formulario=formulario, segmento=segmento, posicion=1)

        solapas_sin_resumen = SolapasService.obtener_solapas_ciudadano(ciudadano)
        resumen = SolapasService.obtener_resumen_becas_ciudadano(ciudadano)
        solapas_con_resumen = SolapasService.obtener_solapas_ciudadano(ciudadano, resumen_becas=resumen)

        self.assertEqual(solapas_sin_resumen, solapas_con_resumen)
        solapa_becas = next(solapa for solapa in solapas_con_resumen if solapa["id"] == "becas")
        self.assertEqual(
            solapa_becas["badge"],
            {
                "tipo": "punto",
                "color_hex": "var(--text-fg-warning)",
                "title": "Lista de espera",
            },
        )


class AlcanceTests(TestCase):
    """BEC-23 (D-B23): la solapa es transversal, pero RN-P13 también vale acá.

    La solapa mostraba todos los casos del ciudadano con solo `ciudadano.ver`,
    incluidos los que cargó el link público —que son los que un rol sin
    `becas.relevamiento.publico` no puede ver en ninguna pantalla de Becas—.
    """

    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.ciudadano = Ciudadano.objects.create(dni="41222333", nombre="Nilda", apellido="Solapa")
        programa = ProgramaSiis.objects.create(nombre="Programa solapa", siis_programa_id=9601)
        segmento = Segmento.objects.create(programa=programa, nombre="Segmento solapa", cupo_maximo=10)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Convocatoria solapa",
            segmento=segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        territorial = User.objects.create_user("territorial-solapa-alcance")
        self.caso_territorial = self._caso(
            Relevamiento.objects.create(
                convocatoria=self.convocatoria,
                territorial=territorial,
                fecha_asignada=date(2026, 6, 1),
                fecha_hasta=date(2026, 6, 30),
                zona="Zona S",
            )
        )
        self.caso_publico = self._caso(
            Relevamiento.objects.create(
                convocatoria=self.convocatoria,
                tipo=Relevamiento.Tipo.PUBLICO,
                fecha_asignada=date(2026, 6, 1),
                fecha_hasta=date(2026, 6, 30),
            )
        )
        # Un rol de legajos, no de Becas: la solapa es transversal y la vista solo
        # exige `ciudadano.ver`. Ese es justamente el rol que veía los casos públicos.
        self.grupo = Group.objects.create(name="Solapa — legajos")
        RolMeta.objects.create(grupo=self.grupo, categoria=rbac.CATEGORIA_BACKOFFICE, activo=True)
        self.grupo.permissions.add(_permiso("ciudadano.ver"))
        self.usuario = User.objects.create_user("mira-solapa", password="x")
        self.usuario.groups.add(self.grupo)

    def _caso(self, relevamiento):
        return Formulario.objects.create(
            relevamiento=relevamiento,
            ciudadano=self.ciudadano,
            celular="3624000000",
        )

    def _casos_visibles(self, user):
        resumen = SolapasService.obtener_resumen_becas_ciudadano(self.ciudadano, user=user)
        return [formulario.pk for formulario in resumen["formularios"]]

    def test_no_muestra_casos_publicos_sin_capacidad(self):
        """El rol sembrado no trae `becas.relevamiento.publico`: es opt-in."""
        visibles = self._casos_visibles(self.usuario)

        self.assertIn(self.caso_territorial.pk, visibles)
        self.assertNotIn(self.caso_publico.pk, visibles)

    def test_con_la_capacidad_los_muestra(self):
        self.grupo.permissions.add(_permiso("becas.relevamiento.publico"))
        self.usuario = User.objects.get(pk=self.usuario.pk)  # el caché de capacidades es por objeto

        self.assertIn(self.caso_publico.pk, self._casos_visibles(self.usuario))

    def test_sin_usuario_se_asume_que_no_puede(self):
        """Default seguro: el que no pasa usuario no ve los casos del link público."""
        self.assertNotIn(self.caso_publico.pk, self._casos_visibles(None))

    def test_la_vista_de_la_solapa_tampoco_los_lista(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse("becas:becas_ciudadano_detalle", args=[self.ciudadano.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, reverse("becas:formulario_detalle", args=[self.caso_territorial.pk]))
        self.assertNotContains(respuesta, reverse("becas:formulario_detalle", args=[self.caso_publico.pk]))
