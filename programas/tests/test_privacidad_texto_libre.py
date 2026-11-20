"""Texto libre sobre una persona y la guarda de `ciudadano.ver` (D-SEG-02, regla R-4).

El motivo de un cambio o una asignación de plaza lo escribe el operador y puede nombrar
datos sensibles de la persona. El Cambio 271 fija que las personas y sus datos se ven solo
con `ciudadano.ver`, pero el historial y la bitácora se leen con `dispositivo.ver`. Acá se
verifica que el centinela puesto en el motivo no llega a ninguna de las dos pantallas sin esa
capacidad, y que el historial lo sigue mostrando a quien la tiene.

El usuario de prueba tiene todo menos `ciudadano.ver` (la lección del Cambio 271: si le
faltara otra capacidad, el 403 vaciaría la guarda probada).
"""

from django.urls import reverse

from programas.models import EntradaBitacora, MovimientoEstadia
from programas.selectors.auditoria_dispositivo import evento_de_movimiento
from programas.services.estadias import asignar_plaza, cambiar_plaza, ingresar_persona
from programas.tests.test_dispositivos_bitacora_pantalla import MIERCOLES, BasePantalla, _local, _reloj, _sin

CENTINELA = "CENTINELA-motivo-reservado-7731"


class BaseTextoLibre(BasePantalla):
    def setUp(self):
        super().setUp()
        self.lector = self._usuario("Lector sin identidad", self.cis, _sin("ciudadano.ver"))
        self.lector_con_identidad = self._usuario(
            "Lector con identidad", self.cis, ("dispositivo.ver", "ciudadano.ver")
        )
        # La asignación solo existe para tipos que manejan plazas; se prende después de alojar.
        self.tipo.plaza_obligatoria_al_ingresar = True
        self.tipo.save(update_fields=["plaza_obligatoria_al_ingresar"])
        self.cis.refresh_from_db()
        self.p3 = self.p2.__class__.objects.create(sector=self.sector, codigo="A-03")
        self.p4 = self.p2.__class__.objects.create(sector=self.sector, codigo="A-04")

    def _cambiar(self):
        with _reloj():
            cambiar_plaza(estadia=self.estadia_ana, plaza=self.p3, usuario=self.operador, motivo=CENTINELA)

    def _asignar(self):
        with _reloj():
            self.tipo.plaza_obligatoria_al_ingresar = False
            self.tipo.save(update_fields=["plaza_obligatoria_al_ingresar"])
            sin_plaza = ingresar_persona(
                ciudadano=self.ana.__class__.objects.create(dni="30555666", nombre="Eva", apellido="Ruiz"),
                dispositivo=self.cis,
                plaza=None,
                usuario=self.operador,
                fecha_ingreso=_local(MIERCOLES, 15, 45),
            )
            self.tipo.plaza_obligatoria_al_ingresar = True
            self.tipo.save(update_fields=["plaza_obligatoria_al_ingresar"])
            sin_plaza.dispositivo.tipo.refresh_from_db()
            asignar_plaza(estadia=sin_plaza, plaza=self.p4, usuario=self.operador, motivo=CENTINELA)

    def _get(self, usuario, url, **params):
        self.client.force_login(usuario)
        with _reloj():
            return self.client.get(url, params)


class HistorialTests(BaseTextoLibre):
    def _historial(self, usuario):
        url = reverse("dispositivos:detalle", args=[self.cis.pk])
        respuesta = self._get(usuario, url, tab="historial")
        self.assertEqual(respuesta.status_code, 200)
        return respuesta

    def test_sin_ciudadano_ver_el_historial_no_trae_el_motivo_del_cambio(self):
        self._cambiar()
        self.assertTrue(MovimientoEstadia.objects.filter(motivo=CENTINELA).exists())

        self.assertNotContains(self._historial(self.lector), CENTINELA)

    def test_sin_ciudadano_ver_el_historial_no_trae_el_motivo_de_la_asignacion(self):
        self._asignar()
        self.assertTrue(MovimientoEstadia.objects.filter(motivo=CENTINELA).exists())

        self.assertNotContains(self._historial(self.lector), CENTINELA)

    def test_con_ciudadano_ver_el_historial_muestra_el_motivo(self):
        self._cambiar()

        self.assertContains(self._historial(self.lector_con_identidad), CENTINELA)

    def test_el_selector_agrega_el_motivo_solo_con_puede_ver_personas(self):
        self._cambiar()
        movimiento = MovimientoEstadia.objects.select_related("estadia__ciudadano").get(motivo=CENTINELA)

        self.assertNotIn(CENTINELA, evento_de_movimiento(movimiento, puede_ver_personas=False)["detalle"])
        self.assertIn(CENTINELA, evento_de_movimiento(movimiento, puede_ver_personas=True)["detalle"])


class BitacoraTests(BaseTextoLibre):
    def test_la_novedad_automatica_no_lleva_el_motivo_libre(self):
        self._cambiar()
        self._asignar()

        entradas = EntradaBitacora.objects.filter(
            origen=EntradaBitacora.Origen.AUTOMATICA, movimiento__motivo=CENTINELA
        )
        self.assertEqual(entradas.count(), 2)
        for entrada in entradas:
            self.assertNotIn(CENTINELA, entrada.texto)
        # El dato no se pierde: sigue en el movimiento, que se lee con `ciudadano.ver`.
        self.assertEqual(MovimientoEstadia.objects.filter(motivo=CENTINELA).count(), 2)

    def test_sin_ciudadano_ver_la_pantalla_y_el_detalle_no_traen_el_motivo(self):
        self._cambiar()
        self._asignar()

        pantalla = self._get(self.lector, reverse("dispositivos:bitacora", args=[self.cis.pk]))
        self.assertEqual(pantalla.status_code, 200)
        self.assertContains(pantalla, "Cambio de plaza")
        self.assertNotContains(pantalla, CENTINELA)

        for entrada in EntradaBitacora.objects.filter(origen=EntradaBitacora.Origen.AUTOMATICA):
            url = reverse("dispositivos:bitacora_entrada", args=[self.cis.pk, entrada.pk])
            detalle = self._get(self.lector, url)
            self.assertEqual(detalle.status_code, 200)
            self.assertNotContains(detalle, CENTINELA)

    def test_el_texto_automatico_del_cambio_queda_solo_con_las_plazas(self):
        """«Cambio de plaza: A → B», sin motivo; el del egreso (catálogo) lo cubre su propio test."""

        from programas.services.bitacora import _texto_automatico

        self._cambiar()
        movimiento = MovimientoEstadia.objects.get(motivo=CENTINELA)
        self.assertEqual(_texto_automatico(movimiento), "Cambio de plaza · plaza A-01 (Varones) → plaza A-03 (Varones)")
