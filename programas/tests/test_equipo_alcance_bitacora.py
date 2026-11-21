"""Bitácora por edificio (Cambio 523, PR 3): la novedad lleva edificio y se ve solo en su alcance.

1. Automáticas: el edificio sale de la plaza → sector → edificio; un sector sin edificio, vacío.
2. Manuales: con más de un edificio en alcance se elige (obligatorio); con uno queda fijo; Institución, opcional.
3. Visibilidad: la pantalla, el detalle y los adjuntos (404 por URL directa) siguen al edificio de la novedad.
4. Filtro «Edificio» de la bitácora para quien ve toda la institución.
"""

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from core.views.media import _autorizar
from legajos.models import Ciudadano
from programas.models import EntradaBitacora, Plaza, Sector
from programas.selectors.estadia_detalle import novedades_de_estadia
from programas.services.bitacora import corregir_entrada
from programas.services.bitacora_pantalla import pantalla_bitacora
from programas.services.dispositivos import q_edificios_en_alcance
from programas.tests.test_dispositivos_bitacora_pantalla import MIERCOLES, PDF, _local, _reloj
from programas.tests.test_equipo_alcance_edificio import Alcance, BaseAlcance

TEXTOS = ("Novedad de A", "Novedad de B", "Novedad sin edificio")


def _fresco(usuario):
    return User.objects.get(pk=usuario.pk)


class BaseBitacoraAlcance(BaseAlcance):
    def setUp(self):
        super().setUp()
        self.de_ab = self._miembro("De A y B", Alcance.EDIFICIOS, [self.edif_a, self.edif_b])
        self.entrada_a = self._cargar(_local(MIERCOLES, 15), texto=TEXTOS[0], edificio=self.edif_a)
        self.entrada_b = self._cargar(_local(MIERCOLES, 15), texto=TEXTOS[1], edificio=self.edif_b)
        self.entrada_sin = self._cargar(_local(MIERCOLES, 15), texto=TEXTOS[2])

    def _textos(self, usuario, **params):
        respuesta = self._get(usuario, **params)
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        return {t for t in TEXTOS if t in html}

    def _ruta_de_adjunto(self, **kwargs):
        acta = SimpleUploadedFile("acta.pdf", PDF, content_type="application/pdf")
        entrada = self._cargar(_local(MIERCOLES, 15), adjuntos=[acta], **kwargs)
        return entrada.adjuntos.get().archivo.name


class AutomaticasTests(BaseBitacoraAlcance):
    def _ultima_automatica(self):
        return EntradaBitacora.objects.filter(origen=EntradaBitacora.Origen.AUTOMATICA).latest("id")

    def test_el_ingreso_a_una_plaza_de_un_edificio_lo_anota_con_ese_edificio(self):
        libre = Plaza.objects.create(sector=self.sector_b, codigo="B-02")
        persona = Ciudadano.objects.create(dni="30555666", nombre="Eva", apellido="Soto")
        self._ingresar(persona, libre, _local(MIERCOLES, 15, 30))
        self.assertEqual(self._ultima_automatica().edificio_id, self.edif_b.pk)

    def test_un_sector_sin_edificio_deja_la_automatica_sin_edificio(self):
        sector = Sector.objects.create(dispositivo=self.cis, nombre="Sin edificio", capacidad=2)
        libre = Plaza.objects.create(sector=sector, codigo="S-01")
        persona = Ciudadano.objects.create(dni="30777888", nombre="Rosa", apellido="Paz")
        self._ingresar(persona, libre, _local(MIERCOLES, 15, 30))
        self.assertIsNone(self._ultima_automatica().edificio_id)


class CargaManualTests(BaseBitacoraAlcance):
    def test_con_dos_edificios_en_alcance_sin_elegir_se_rechaza(self):
        with self.assertRaisesMessage(ValidationError, "Elegí el edificio"):
            self._cargar(_local(MIERCOLES, 15), usuario=self.de_ab)

    def test_con_dos_edificios_eligiendo_uno_se_guarda_con_ese(self):
        entrada = self._cargar(_local(MIERCOLES, 15), usuario=self.de_ab, edificio=self.edif_b)
        self.assertEqual(entrada.edificio_id, self.edif_b.pk)

    def test_con_un_solo_edificio_queda_fijo_sin_preguntar(self):
        entrada = self._cargar(_local(MIERCOLES, 15), usuario=self.de_a)
        self.assertEqual(entrada.edificio_id, self.edif_a.pk)

    def test_no_se_puede_cargar_en_un_edificio_ajeno(self):
        with self.assertRaises(PermissionDenied):
            self._cargar(_local(MIERCOLES, 15), usuario=self.de_a, edificio=self.edif_b)

    def test_institucion_puede_dejarlo_vacio_o_elegir(self):
        self.assertIsNone(self._cargar(_local(MIERCOLES, 15), usuario=self.de_inst).edificio_id)
        elegida = self._cargar(_local(MIERCOLES, 15), usuario=self.de_inst, edificio=self.edif_b)
        self.assertEqual(elegida.edificio_id, self.edif_b.pk)

    def test_el_modal_ofrece_el_select_solo_con_mas_de_un_edificio(self):
        self.assertIn('name="edificio"', self._get(self.de_ab, novedad=1).content.decode())
        fijo = self._get(self.de_a, novedad=1).content.decode()
        self.assertNotIn('name="edificio"', fijo)
        self.assertIn("Edificio ED-A", fijo)

    def test_por_la_vista_sin_edificio_con_dos_en_alcance_responde_400(self):
        respuesta = self._post("bitacora_novedad", {"tipo": "INCIDENTE", "texto": "x"}, usuario=self.de_ab)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("edificio", respuesta.json()["errors"])

    def test_corregir_una_novedad_ajena_no_se_puede_y_la_version_hereda_el_edificio(self):
        with _reloj(), self.assertRaises(PermissionDenied):
            corregir_entrada(entrada=self.entrada_b, usuario=self.de_a, texto="cambio")
        with _reloj():
            nueva = corregir_entrada(entrada=self.entrada_b, usuario=self.de_inst, texto="cambio")
        self.assertEqual(nueva.edificio_id, self.edif_b.pk)


class VisibilidadTests(BaseBitacoraAlcance):
    def test_alcance_edificios_ve_solo_las_de_sus_edificios(self):
        self.assertEqual(self._textos(self.de_a), {TEXTOS[0]})
        self.assertEqual(self._textos(self.de_ab), {TEXTOS[0], TEXTOS[1]})

    def test_institucion_ve_todas_incluida_la_sin_edificio(self):
        self.assertEqual(self._textos(self.de_inst), set(TEXTOS))

    def test_el_detalle_de_una_novedad_ajena_es_404(self):
        def detalle(usuario, entrada):
            self.client.force_login(usuario)
            with _reloj():
                return self.client.get(reverse("dispositivos:bitacora_entrada", args=[self.cis.pk, entrada.pk]))

        self.assertEqual(detalle(self.de_a, self.entrada_a).status_code, 200)
        self.assertEqual(detalle(self.de_a, self.entrada_b).status_code, 404)
        self.assertEqual(detalle(self.de_a, self.entrada_sin).status_code, 404)
        self.assertEqual(detalle(self.de_inst, self.entrada_sin).status_code, 200)

    def test_el_adjunto_sigue_la_visibilidad_de_su_novedad(self):
        ruta = self._ruta_de_adjunto(edificio=self.edif_b)
        self.assertIsNone(_autorizar(_fresco(self.de_a), ruta))
        self.assertIs(_autorizar(_fresco(self.de_ab), ruta), True)
        self.assertIs(_autorizar(_fresco(self.de_inst), ruta), True)

    def test_el_adjunto_de_una_novedad_sin_edificio_es_solo_de_institucion(self):
        ruta = self._ruta_de_adjunto()
        self.assertIsNone(_autorizar(_fresco(self.de_a), ruta))
        self.assertIs(_autorizar(_fresco(self.de_inst), ruta), True)

    def test_la_solapa_de_novedades_de_la_estadia_tambien_se_acota(self):
        self._cargar(_local(MIERCOLES, 15, 5), texto="Del legajo B", edificio=self.edif_b, personas=[self.estadia_ana])

        def textos(usuario):
            q = q_edificios_en_alcance(_fresco(usuario), "dispositivo.ver", "dispositivo_id", "edificio_id")
            return [f["texto"] for f in novedades_de_estadia(self.estadia_ana, q_entradas=q).object_list]

        self.assertIn("Del legajo B", textos(self.de_inst))
        self.assertNotIn("Del legajo B", textos(self.de_a))

    def test_la_vista_de_la_estadia_acota_las_novedades_por_edificio(self):
        self._cargar(_local(MIERCOLES, 15, 6), texto="Del legajo B", edificio=self.edif_b, personas=[self.estadia_ana])
        self._cargar(_local(MIERCOLES, 15, 7), texto="Del legajo sin edificio", personas=[self.estadia_ana])
        self._cargar(_local(MIERCOLES, 15, 8), texto="Del legajo A", edificio=self.edif_a, personas=[self.estadia_ana])
        url = reverse("dispositivos:estadia_detalle", args=[self.cis.pk, self.estadia_ana.pk])

        def textos(usuario):
            self.client.force_login(_fresco(usuario))
            with _reloj():
                respuesta = self.client.get(url, {"tab": "novedades"})
            self.assertEqual(respuesta.status_code, 200)
            return {
                f["texto"]
                for f in respuesta.context["novedades_page"].object_list
                if f["texto"].startswith("Del legajo")
            }

        self.assertEqual(textos(self.de_a), {"Del legajo A"})
        self.assertEqual(textos(self.de_inst), {"Del legajo A", "Del legajo B", "Del legajo sin edificio"})


class FiltroEdificioTests(BaseBitacoraAlcance):
    def test_institucion_filtra_por_edificio_y_por_sin_edificio(self):
        self.assertEqual(self._textos(self.de_inst, edificio=str(self.edif_a.pk)), {TEXTOS[0]})
        self.assertEqual(self._textos(self.de_inst, edificio="sin"), {TEXTOS[2]})
        self.assertEqual(self._textos(self.de_inst, edificio=""), set(TEXTOS))

    def test_el_filtro_solo_lo_ve_quien_tiene_toda_la_institucion(self):
        self.assertIn("Sin edificio", self._get(self.de_inst).content.decode())
        self.assertNotIn("Sin edificio", self._get(self.de_ab).content.decode())

    def test_edificios_no_se_salta_su_alcance_con_el_filtro(self):
        self.assertEqual(self._textos(self.de_a, edificio=str(self.edif_b.pk)), {TEXTOS[0]})
        self.assertEqual(self._textos(self.de_a, edificio="sin"), {TEXTOS[0]})


class CensoPorEdificioTests(BaseBitacoraAlcance):
    """El censo del día y las cifras de plazas son de los edificios de quien mira (decisión del PM, 21-nov-2026)."""

    def _fila(self, usuario, etiqueta):
        with _reloj():
            datos = pantalla_bitacora(self.cis, usuario=_fresco(usuario), fecha=MIERCOLES.isoformat())
        return {f["etiqueta"]: f["valor"] for f in datos["censo_filas"]}[etiqueta]

    def test_los_ingresos_del_dia_son_de_sus_edificios(self):
        persona = Ciudadano.objects.create(dni="30444555", nombre="Lía", apellido="Gil")
        antes_a = self._fila(self.de_a, "Ingresos del día")
        antes_inst = self._fila(self.de_inst, "Ingresos del día")
        self._ingresar(persona, self.plaza_b, _local(MIERCOLES, 15, 40))
        self.assertEqual(self._fila(self.de_a, "Ingresos del día"), antes_a)
        self.assertEqual(self._fila(self.de_inst, "Ingresos del día"), antes_inst + 1)
        self.assertEqual(self._fila(self.de_ab, "Ingresos del día"), antes_a + 1)

    def test_las_plazas_son_las_de_sus_edificios(self):
        self.assertEqual(self._fila(self.de_a, "Plazas totales / operativas").split(" / ")[0], "2")
        total_inst = int(self._fila(self.de_inst, "Plazas totales / operativas").split(" / ")[0])
        self.assertGreater(total_inst, 2)
