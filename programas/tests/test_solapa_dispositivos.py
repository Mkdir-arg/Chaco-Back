from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import Admision, Cama, Dispositivo, InscripcionPrograma, Programa, TipoDispositivo
from programas.services.solapas import SolapasService


class SolapaDispositivosTests(TestCase):
    def test_la_membresia_activa_de_dispositivos_agrega_una_solapa_dedicada(self):
        usuario = User.objects.create_user(username="operador-solapa")
        programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        ciudadano = Ciudadano.objects.create(dni="39000100", nombre="Ana", apellido="Solapa")
        membresia = InscripcionPrograma.objects.create(
            ciudadano=ciudadano,
            programa=programa,
            responsable=usuario,
            estado=InscripcionPrograma.Estado.ACTIVO,
        )
        tipo = TipoDispositivo.objects.create(codigo="SOLAPA", nombre="Solapa", maneja_camas=True)
        dispositivo = Dispositivo.objects.create(codigo="SOL-01", nombre="Hogar Solapa", tipo=tipo)
        cama = Cama.objects.create(dispositivo=dispositivo, codigo="C-01")
        Admision.objects.create(
            ciudadano=ciudadano,
            dispositivo=dispositivo,
            inscripcion_programa=membresia,
            cama=cama,
            fecha_ingreso=timezone.now(),
            estado=Admision.Estado.ALOJADO,
        )
        Admision.objects.create(
            ciudadano=ciudadano,
            dispositivo=dispositivo,
            inscripcion_programa=membresia,
            fecha_ingreso=timezone.now() - timezone.timedelta(days=3),
            fecha_egreso=timezone.now() - timezone.timedelta(days=1),
            estado=Admision.Estado.EGRESADO,
            es_reingreso=True,
        )

        solapas = SolapasService.obtener_solapas_ciudadano(ciudadano)

        self.assertEqual([solapa["id"] for solapa in solapas].count("programa_DISPOSITIVOS"), 1)
        solapa = next(solapa for solapa in solapas if solapa["id"] == "programa_DISPOSITIVOS")
        self.assertEqual(solapa["url_name"], "legajos:dispositivos_ciudadano")
        self.assertEqual(solapa["url"], reverse("legajos:dispositivos_ciudadano", args=[ciudadano.pk, membresia.pk]))

        administrador = User.objects.create_superuser(username="admin-solapa", password="clave")
        self.client.force_login(administrador)
        response = self.client.get(reverse("legajos:dispositivos_ciudadano", args=[ciudadano.pk, membresia.pk]))

        self.assertContains(response, "Hogar Solapa")
        self.assertContains(response, "C-01")
        self.assertContains(response, "Alojado")
        self.assertContains(response, "Egresado")
        self.assertContains(response, "Sí")
        self.assertContains(response, "—")
        detalle = self.client.get(reverse("legajos:ciudadano_detalle", args=[ciudadano.pk]))
        self.assertContains(detalle, reverse("legajos:dispositivos_ciudadano", args=[ciudadano.pk, membresia.pk]))

    def test_membresia_sin_admision_alojada_no_agrega_la_solapa(self):
        usuario = User.objects.create_user(username="operador-sin-admision")
        programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        ciudadano = Ciudadano.objects.create(dni="39000101", nombre="Beto", apellido="Sin admisión")
        membresia = InscripcionPrograma.objects.create(
            ciudadano=ciudadano,
            programa=programa,
            responsable=usuario,
            estado=InscripcionPrograma.Estado.ACTIVO,
        )

        solapas = SolapasService.obtener_solapas_ciudadano(ciudadano)

        self.assertNotIn("programa_DISPOSITIVOS", [solapa["id"] for solapa in solapas])
        administrador = User.objects.create_superuser(username="admin-sin-admision", password="clave")
        self.client.force_login(administrador)
        response = self.client.get(reverse("legajos:dispositivos_ciudadano", args=[ciudadano.pk, membresia.pk]))

        self.assertEqual(response.status_code, 403)

    def test_endpoint_directo_exige_permiso_del_programa(self):
        usuario = User.objects.create_user(username="operador-scope")
        programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        ciudadano = Ciudadano.objects.create(dni="39000102", nombre="Carla", apellido="Scope")
        membresia = InscripcionPrograma.objects.create(
            ciudadano=ciudadano,
            programa=programa,
            responsable=usuario,
            estado=InscripcionPrograma.Estado.ACTIVO,
        )
        self.client.force_login(usuario)

        response = self.client.get(reverse("legajos:dispositivos_ciudadano", args=[ciudadano.pk, membresia.pk]))

        self.assertEqual(response.status_code, 403)
