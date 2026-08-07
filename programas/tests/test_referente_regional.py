from datetime import date
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core import rbac
from programas.management.commands.seed_becas import (
    ROL_ADMIN,
    ROL_COORDINADOR,
    ROL_COORDINADOR_REGIONAL,
    ROL_REFERENTE,
    ROL_TERRITORIAL,
)
from programas.models import (
    AsignacionCoordinador,
    AsignacionCoordinadorRegional,
    AsignacionReferente,
    AsignacionTerritorial,
    Convocatoria,
    Region,
    Segmento,
    Subsegmento,
    TransferenciaRegional,
)
from programas.services.autorizacion import convocatorias_visibles, segmentos_visibles
from programas.services.regiones import transferir_responsabilidad_regional
from users.selectors.usuarios import usuarios_visibles_para


class ReferenteRegionalTests(TestCase):
    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.segmento = Segmento.objects.create(nombre="Norte", cupo_maximo=100)
        self.otro_segmento = Segmento.objects.create(nombre="Sur", cupo_maximo=100)
        self.localidad = Subsegmento.objects.create(
            segmento=self.segmento, nombre="Resistencia", cupo_maximo=50, siis_segmento_id=8001
        )
        self.otra_localidad = Subsegmento.objects.create(
            segmento=self.otro_segmento, nombre="Villa Ángela", cupo_maximo=50, siis_segmento_id=8002
        )
        self.region = Region.objects.create(nombre="Región Norte")
        self.region.localidades.add(self.localidad)

        self.admin = self._usuario("admin-r", ROL_ADMIN)
        self.coordinador = self._usuario("coord-r", ROL_COORDINADOR)
        AsignacionCoordinador.objects.create(segmento=self.segmento, coordinador=self.coordinador)
        self.referente = self._usuario("referente-r", ROL_REFERENTE)
        AsignacionReferente.objects.create(referente=self.referente, coordinador=self.coordinador)
        self.regional = self._usuario("regional-r", ROL_COORDINADOR_REGIONAL)
        AsignacionCoordinadorRegional.objects.create(coordinador=self.regional, region=self.region)
        self.territorial = self._usuario("territorial-r", ROL_TERRITORIAL)
        AsignacionTerritorial.objects.create(territorial=self.territorial, segmento=self.segmento)
        self.territorial_ajeno = self._usuario("territorial-ajeno-r", ROL_TERRITORIAL)
        AsignacionTerritorial.objects.create(territorial=self.territorial_ajeno, segmento=self.otro_segmento)

    @staticmethod
    def _usuario(username, rol):
        user = User.objects.create_user(username, password="x")
        user.groups.add(Group.objects.get(name=rol))
        return user

    def test_referente_hereda_segmentos_y_solo_administra_territoriales_del_coordinador(self):
        self.assertEqual(list(segmentos_visibles(self.referente)), [self.segmento])
        self.assertEqual(list(usuarios_visibles_para(self.referente)), [self.territorial])
        self.assertFalse(rbac.puede(self.referente, "rol.administrar"))
        self.assertFalse(rbac.puede(self.referente, "becas.convocatoria.crear"))

    def test_referente_y_regional_no_pueden_pausar(self):
        convocatoria = Convocatoria.objects.create(
            nombre="Operativo",
            segmento=self.segmento,
            subsegmento=self.localidad,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
            creada_por=self.regional,
            responsable_regional=self.regional,
        )
        for user in (self.referente, self.regional):
            self.client.force_login(user)
            response = self.client.post(
                reverse("becas:gestionar_pausa", args=["convocatoria", convocatoria.pk]),
                {"accion": "pausar", "motivo": "No permitido"},
            )
            self.assertEqual(response.status_code, 403)
        convocatoria.refresh_from_db()
        self.assertFalse(convocatoria.pausado)

    def test_regional_solo_ve_convocatorias_propias_de_su_region(self):
        propia = Convocatoria.objects.create(
            nombre="Propia",
            segmento=self.segmento,
            subsegmento=self.localidad,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
            creada_por=self.regional,
            responsable_regional=self.regional,
        )
        otra = Convocatoria.objects.create(
            nombre="De otro",
            segmento=self.segmento,
            subsegmento=self.localidad,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
            creada_por=self.admin,
        )
        self.assertEqual(list(convocatorias_visibles(self.regional)), [propia])
        self.assertNotIn(otra, convocatorias_visibles(self.regional))

    def test_transferencia_cambia_responsabilidad_sin_perder_creador_ni_datos(self):
        reemplazo = self._usuario("regional-reemplazo", ROL_COORDINADOR_REGIONAL)
        convocatoria = Convocatoria.objects.create(
            nombre="Transferible",
            segmento=self.segmento,
            subsegmento=self.localidad,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
            creada_por=self.regional,
            responsable_regional=self.regional,
        )
        asignacion = self.territorial.asignacion_territorial
        asignacion.coordinador_regional = self.regional
        asignacion.save(update_fields=["coordinador_regional", "modificado"])

        resultado = transferir_responsabilidad_regional(
            origen=self.regional, destino=reemplazo, ejecutado_por=self.admin
        )

        convocatoria.refresh_from_db()
        asignacion.refresh_from_db()
        self.assertEqual(resultado["convocatorias"], 1)
        self.assertEqual(convocatoria.creada_por, self.regional)
        self.assertEqual(convocatoria.responsable_regional, reemplazo)
        self.assertEqual(asignacion.coordinador_regional, reemplazo)
        self.assertEqual(reemplazo.asignacion_coordinador_regional.region, self.region)
        self.assertFalse(AsignacionCoordinadorRegional.objects.filter(coordinador=self.regional).exists())
        transferencia = TransferenciaRegional.objects.get()
        self.assertEqual(transferencia.coordinador_origen, self.regional)
        self.assertEqual(transferencia.coordinador_destino, reemplazo)
        self.assertEqual(transferencia.ejecutado_por, self.admin)
        self.assertEqual(transferencia.convocatorias_transferidas, 1)
        self.assertEqual(transferencia.territoriales_transferidos, 1)

    def test_solo_admin_accede_a_configuracion_de_regiones(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("becas:regiones")).status_code, 200)
        self.client.force_login(self.regional)
        self.assertEqual(self.client.get(reverse("becas:regiones")).status_code, 302)
