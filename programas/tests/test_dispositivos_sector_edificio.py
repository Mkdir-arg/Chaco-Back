"""El sector se ubica en un edificio del dispositivo (Cambio 429, caso de QA 6).

Cubre: el alta exige edificio y solo uno vinculado al dispositivo, el cambio de edificio en la
edición y su traza, el bloqueo de desvincular un edificio con sectores activos, la migración de
datos de los sectores existentes (1 edificio → asignado; 2 o más → sin edificio) y la vista
jerárquica de la solapa Infraestructura con el bloque «Sin edificio».
"""

import importlib

from django.apps import apps
from django.core.exceptions import ValidationError
from django.urls import reverse

from programas.models import Edificio, Plaza, Sector, TrazaDispositivo
from programas.services.edificios import desvincular_edificio
from programas.services.plazas import crear_sector, editar_sector, reactivar_sector
from programas.tests.test_dispositivos_capacidad import BaseCapacidad

migracion_datos = importlib.import_module("programas.migrations.0114_sector_edificio_datos")


class BaseSectorEdificio(BaseCapacidad):
    def setUp(self):
        super().setUp()
        self.edificio_a = self._nuevo_edificio("EDI-A", "Predio A", self.cis)
        self.edificio_b = self._nuevo_edificio("EDI-B", "Predio B", self.cis)
        self.ajeno = self._nuevo_edificio("EDI-X", "Predio ajeno", self.parador)

    def _nuevo_edificio(self, codigo, nombre, *dispositivos):
        edificio = Edificio.objects.create(codigo=codigo, nombre=nombre)
        edificio.dispositivos.add(*dispositivos)
        return edificio

    def _sector(self, edificio, nombre="Pabellón Z", **extra):
        return Sector.objects.create(dispositivo=self.cis, edificio=edificio, nombre=nombre, **extra)

    def _datos(self, **extra):
        return {
            "nombre": "Pabellón N",
            "tipo": Sector.Tipo.PABELLON,
            "capacidad": 3,
            "edificio": self.edificio_a,
            **extra,
        }


class AltaConEdificioTests(BaseSectorEdificio):
    def test_el_alta_sin_edificio_se_rechaza_en_el_servicio(self):
        with self.assertRaises(ValidationError) as fallo:
            crear_sector(dispositivo=self.cis, usuario=self.operador_cis, **self._datos(edificio=None))

        self.assertIn("edificio", fallo.exception.message_dict)
        self.assertFalse(Sector.objects.filter(nombre="Pabellón N").exists())

    def test_el_alta_guarda_el_edificio_y_lo_deja_en_la_traza(self):
        sector = crear_sector(dispositivo=self.cis, usuario=self.operador_cis, **self._datos())

        self.assertEqual(sector.edificio, self.edificio_a)
        traza = TrazaDispositivo.objects.get(dispositivo=self.cis, accion="SECTOR_CREADO")
        self.assertIn("EDI-A", traza.detalle)

    def test_un_edificio_no_vinculado_al_dispositivo_se_rechaza_en_el_servicio(self):
        with self.assertRaises(ValidationError) as fallo:
            crear_sector(dispositivo=self.cis, usuario=self.operador_cis, **self._datos(edificio=self.ajeno))

        self.assertIn("edificio", fallo.exception.message_dict)
        self.assertFalse(Sector.objects.filter(nombre="Pabellón N").exists())

    def test_la_pantalla_exige_el_edificio_y_no_acepta_uno_ajeno(self):
        self.client.force_login(self.operador_cis)
        url = reverse("dispositivos:sector_crear", args=[self.cis.pk])
        ajax = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        base = {"nombre": "Pabellón N", "tipo": Sector.Tipo.PABELLON, "capacidad": 3}

        sin = self.client.post(url, base, **ajax)
        ajeno = self.client.post(url, {**base, "edificio": self.ajeno.pk}, **ajax)

        self.assertEqual(sin.status_code, 400)
        self.assertEqual(list(sin.json()["errors"]), ["edificio"])
        self.assertEqual(ajeno.status_code, 400)
        self.assertIn("edificio", ajeno.json()["errors"])
        self.assertFalse(Sector.objects.filter(nombre="Pabellón N").exists())

    def test_el_alta_por_la_pantalla_con_un_edificio_vinculado_crea_el_sector(self):
        self.client.force_login(self.operador_cis)
        url = reverse("dispositivos:sector_crear", args=[self.cis.pk])

        respuesta = self.client.post(
            url, {"nombre": "Pabellón N", "tipo": Sector.Tipo.PABELLON, "capacidad": 3, "edificio": self.edificio_b.pk}
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Sector.objects.get(nombre="Pabellón N").edificio, self.edificio_b)

    def test_el_selector_ofrece_solo_los_edificios_del_dispositivo(self):
        from programas.forms_dispositivos import SectorForm

        form = SectorForm(dispositivo=self.cis)

        self.assertEqual(set(form.fields["edificio"].queryset), {self.edificio_a, self.edificio_b})
        self.assertTrue(form.fields["edificio"].required)


class EdicionConEdificioTests(BaseSectorEdificio):
    def _editar(self, sector, **extra):
        datos = {
            "nombre": sector.nombre,
            "tipo": sector.tipo,
            "capacidad": sector.capacidad,
            "perfil": sector.perfil,
            **extra,
        }
        return editar_sector(sector=sector, usuario=self.operador_cis, **datos)

    def test_cambiar_el_edificio_queda_en_la_traza_con_el_de_antes_y_el_de_ahora(self):
        sector = self._sector(self.edificio_a)

        self._editar(sector, edificio=self.edificio_b)

        sector.refresh_from_db()
        self.assertEqual(sector.edificio, self.edificio_b)
        traza = TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="SECTOR_EDITADO").latest("pk")
        self.assertIn("edificio EDI-B", traza.detalle)
        self.assertIn("antes: EDI-A", traza.detalle)

    def test_editar_sin_cambiar_el_edificio_no_dice_de_donde_venia(self):
        sector = self._sector(self.edificio_a)

        self._editar(sector, edificio=self.edificio_a, capacidad=9)

        traza = TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="SECTOR_EDITADO").latest("pk")
        self.assertNotIn("antes:", traza.detalle)

    def test_el_edificio_nuevo_tiene_que_estar_vinculado(self):
        sector = self._sector(self.edificio_a)

        with self.assertRaises(ValidationError) as fallo:
            self._editar(sector, edificio=self.ajeno)

        self.assertIn("edificio", fallo.exception.message_dict)
        sector.refresh_from_db()
        self.assertEqual(sector.edificio, self.edificio_a)

    def test_un_sector_sin_edificio_lo_pide_al_guardar(self):
        sector = self._sector(None)

        with self.assertRaises(ValidationError) as fallo:
            self._editar(sector)

        self.assertIn("edificio", fallo.exception.message_dict)

    def test_un_sector_sin_edificio_se_puede_dar_de_baja_sin_elegir_uno(self):
        sector = self._sector(None)

        self._editar(sector, activo=False)

        sector.refresh_from_db()
        self.assertFalse(sector.activo)
        self.assertIsNone(sector.edificio)

    def test_la_pantalla_de_edicion_pide_el_edificio_a_un_sector_sin_el(self):
        sector = self._sector(None)
        self.client.force_login(self.operador_cis)
        url = reverse("dispositivos:sector_editar", args=[self.cis.pk, sector.pk])

        sin = self.client.post(
            url,
            {"nombre": sector.nombre, "tipo": sector.tipo, "capacidad": 0, "activo": "on"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        con = self.client.post(
            url,
            {
                "nombre": sector.nombre,
                "tipo": sector.tipo,
                "capacidad": 0,
                "activo": "on",
                "edificio": self.edificio_b.pk,
            },
        )

        self.assertEqual(sin.status_code, 400)
        self.assertIn("edificio", sin.json()["errors"])
        self.assertEqual(con.status_code, 302)
        sector.refresh_from_db()
        self.assertEqual(sector.edificio, self.edificio_b)

    def test_no_se_reactiva_un_sector_cuyo_edificio_ya_no_esta_vinculado(self):
        sector = self._sector(self.edificio_a, activo=False)
        self.edificio_a.dispositivos.remove(self.cis)

        with self.assertRaises(ValidationError):
            reactivar_sector(sector=sector, usuario=self.operador_cis)

        sector.refresh_from_db()
        self.assertFalse(sector.activo)


class DesvincularConSectoresTests(BaseSectorEdificio):
    def test_se_bloquea_con_sectores_activos_del_dispositivo_en_el_edificio(self):
        self._sector(self.edificio_a)

        with self.assertRaises(ValidationError) as fallo:
            desvincular_edificio(edificio=self.edificio_a, dispositivo=self.cis, usuario=self.operador_cis)

        self.assertIn("1 sector activo", fallo.exception.message_dict["__all__"][0])
        self.assertTrue(self.edificio_a.dispositivos.filter(pk=self.cis.pk).exists())

    def test_la_pantalla_dice_el_motivo(self):
        self._sector(self.edificio_a)
        self.client.force_login(self.operador_cis)

        respuesta = self.client.post(
            reverse("dispositivos:edificio_desvincular", args=[self.cis.pk, self.edificio_a.pk]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("sector", respuesta.json()["errors"]["__all__"][0])
        self.assertTrue(self.edificio_a.dispositivos.filter(pk=self.cis.pk).exists())

    def test_los_sectores_dados_de_baja_no_lo_bloquean(self):
        self._sector(self.edificio_a, activo=False)

        desvincular_edificio(edificio=self.edificio_a, dispositivo=self.cis, usuario=self.operador_cis)

        self.assertFalse(self.edificio_a.dispositivos.filter(pk=self.cis.pk).exists())

    def test_los_sectores_de_otro_edificio_no_lo_bloquean(self):
        self._sector(self.edificio_b)

        desvincular_edificio(edificio=self.edificio_a, dispositivo=self.cis, usuario=self.operador_cis)

        self.assertFalse(self.edificio_a.dispositivos.filter(pk=self.cis.pk).exists())

    def test_los_sectores_de_otra_institucion_en_el_predio_compartido_no_lo_bloquean(self):
        self.edificio_a.dispositivos.add(self.parador)
        Sector.objects.create(dispositivo=self.parador, edificio=self.edificio_a, nombre="Del parador")

        desvincular_edificio(edificio=self.edificio_a, dispositivo=self.cis, usuario=self.operador_cis)

        self.assertFalse(self.edificio_a.dispositivos.filter(pk=self.cis.pk).exists())

    def test_con_el_sector_movido_se_puede_desvincular(self):
        sector = self._sector(self.edificio_a)
        editar_sector(
            sector=sector,
            usuario=self.operador_cis,
            nombre=sector.nombre,
            tipo=sector.tipo,
            capacidad=0,
            edificio=self.edificio_b,
        )

        desvincular_edificio(edificio=self.edificio_a, dispositivo=self.cis, usuario=self.operador_cis)

        self.assertFalse(self.edificio_a.dispositivos.filter(pk=self.cis.pk).exists())


class MigracionDeDatosTests(BaseSectorEdificio):
    """La función de la migración 0114, con los modelos históricos (`apps.get_model`)."""

    def setUp(self):
        super().setUp()
        # Un dispositivo con un solo edificio (el parador: `ajeno`) y otro con dos (el CIS).
        self.sector_parador = Sector.objects.create(dispositivo=self.parador, nombre="Del parador")
        self.sector_cis = self._sector(None, "Del CIS")
        self.sector_cis_2 = self._sector(None, "Otro del CIS")

    def test_con_un_edificio_se_asigna_y_con_dos_queda_sin_edificio(self):
        migracion_datos.asignar_edificio_unico(apps)

        self.sector_parador.refresh_from_db()
        self.sector_cis.refresh_from_db()
        self.sector_cis_2.refresh_from_db()
        self.assertEqual(self.sector_parador.edificio, self.ajeno)
        self.assertIsNone(self.sector_cis.edificio)
        self.assertIsNone(self.sector_cis_2.edificio)

    def test_es_idempotente_y_no_pisa_una_asignacion_hecha_a_mano(self):
        migracion_datos.asignar_edificio_unico(apps)
        otro = self._nuevo_edificio("EDI-Y", "Otro", self.parador)
        # Con un segundo edificio vinculado, una corrida nueva ya no tiene «el único»; y de todos
        # modos el sector que ya tiene edificio no se toca.
        nuevo = Sector.objects.create(dispositivo=self.parador, edificio=otro, nombre="A mano")

        migracion_datos.asignar_edificio_unico(apps)
        migracion_datos.asignar_edificio_unico(apps)

        self.sector_parador.refresh_from_db()
        nuevo.refresh_from_db()
        self.assertEqual(self.sector_parador.edificio, self.ajeno)
        self.assertEqual(nuevo.edificio, otro)

    def test_un_sector_que_ya_tiene_edificio_no_se_pisa_aunque_el_dispositivo_tenga_uno_solo(self):
        asignado = Sector.objects.create(dispositivo=self.parador, edificio=self.edificio_a, nombre="Ya asignado")

        migracion_datos.asignar_edificio_unico(apps)

        asignado.refresh_from_db()
        self.assertEqual(asignado.edificio, self.edificio_a)

    def test_no_pierde_sectores_ni_plazas(self):
        Plaza.objects.create(sector=self.sector_parador, codigo="P-1")
        sectores = Sector.objects.count()
        plazas = Plaza.objects.count()

        migracion_datos.asignar_edificio_unico(apps)

        self.assertEqual(Sector.objects.count(), sectores)
        self.assertEqual(Plaza.objects.count(), plazas)

    def test_la_reversa_deja_todos_los_sectores_sin_edificio(self):
        sectores = Sector.objects.count()
        migracion_datos.asignar_edificio_unico(apps)
        self.assertTrue(Sector.objects.filter(edificio__isnull=False).exists())

        migracion_datos.desasignar_edificios(apps)

        self.assertFalse(Sector.objects.filter(edificio__isnull=False).exists())
        self.assertEqual(Sector.objects.count(), sectores)


class VistaJerarquicaTests(BaseSectorEdificio):
    def setUp(self):
        super().setUp()
        # El sector del terreno compartido no tiene edificio: aparte, para contar solo los de cada test.
        Sector.objects.filter(pk=self.sector.pk).update(activo=False)

    def _infraestructura(self):
        self.client.force_login(self.operador_cis)
        return self.client.get(reverse("dispositivos:detalle", args=[self.cis.pk]), {"tab": "infraestructura"})

    def test_cada_edificio_trae_sus_sectores_y_el_bloque_sin_edificio(self):
        sector = self._sector(self.edificio_a, "Pabellón 1")
        Plaza.objects.create(sector=sector, codigo="A-01")
        Plaza.objects.create(sector=sector, codigo="A-02")
        self._sector(self.edificio_a, "Pabellón 2")
        huerfano = self._sector(None, "Sin ubicar")
        Plaza.objects.create(sector=huerfano, codigo="S-01")
        self._sector(self.edificio_b, "Dado de baja", activo=False)

        respuesta = self._infraestructura()

        infra = respuesta.context["infraestructura"]
        por_codigo = {fila["codigo"]: fila for fila in infra["edificios"]}
        self.assertEqual([s["nombre"] for s in por_codigo["EDI-A"]["sectores"]], ["Pabellón 1", "Pabellón 2"])
        self.assertEqual(por_codigo["EDI-A"]["n_plazas"], 2)
        self.assertEqual(por_codigo["EDI-B"]["sectores"], [])
        self.assertEqual([s["nombre"] for s in infra["sin_edificio"]["sectores"]], ["Sin ubicar"])
        self.assertEqual(infra["sin_edificio"]["n_plazas"], 1)
        self.assertContains(respuesta, "Sectores por edificio")
        self.assertContains(respuesta, "Sin edificio")
        self.assertContains(respuesta, "2 sectores")
        self.assertContains(respuesta, "Sin sectores en este edificio.")

    def test_sin_sectores_huerfanos_no_hay_bloque_sin_edificio(self):
        self._sector(self.edificio_a)

        respuesta = self._infraestructura()

        self.assertIsNone(respuesta.context["infraestructura"]["sin_edificio"])
        self.assertNotContains(respuesta, "Quedan acá hasta que un administrador")

    def test_con_un_solo_edificio_tambien_se_ven_los_sectores(self):
        self.edificio_b.dispositivos.remove(self.cis)
        self._sector(self.edificio_a, "Único")

        respuesta = self._infraestructura()

        fila = respuesta.context["infraestructura"]["edificios"][0]
        self.assertEqual([s["nombre"] for s in fila["sectores"]], ["Único"])
        self.assertContains(respuesta, "1 sector ")

    def test_al_abrir_un_edificio_solo_se_ve_su_jerarquia(self):
        self._sector(self.edificio_a, "En A")
        self._sector(self.edificio_b, "En B")
        self._sector(None, "Huérfano")
        self.client.force_login(self.operador_cis)

        respuesta = self.client.get(
            reverse("dispositivos:detalle", args=[self.cis.pk]),
            {"tab": "infraestructura", "ver_edificio": self.edificio_b.pk},
        )

        infra = respuesta.context["infraestructura"]
        self.assertEqual([f["codigo"] for f in infra["edificios"]], ["EDI-B"])
        self.assertIsNone(infra["sin_edificio"])
