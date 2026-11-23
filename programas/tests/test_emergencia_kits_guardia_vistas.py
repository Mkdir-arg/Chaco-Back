"""Módulo Emergencia: la recepción de kits en el dispositivo, vista por la guardia (HU-4.3).

Mismo contrato que test_emergencia_kits_vistas (de donde salió la clase al pasar de 1000 líneas): la base
BaseVistasKits es la de allá.
"""

from unittest.mock import patch

from django.urls import reverse

from programas.models import EntradaBitacora, EntregaKit, MiembroEquipoDispositivo
from programas.services import kits as servicio
from programas.tests.test_emergencia_kits import ADMITIR, PNG, RECIBIR_KIT
from programas.tests.test_emergencia_kits_vistas import BaseVistasKits

Estado = EntregaKit.Estado


class RecepcionEnElDispositivoTests(BaseVistasKits):
    def setUp(self):
        super().setUp()
        self.entrega = self._en_camino(dispositivo=self.club, observacion="Entregar a la directora.")
        self.url_kits = self._url("dispositivo_kits", self.club.pk)
        self.url_recibir = self._url("dispositivo_kit_recibir", self.club.pk, self.entrega.pk)

    def _cuerpo(self, colchones=10, kits=3, remito="jpeg", **extra):
        cuerpo = {f"cantidad_{self.colchon.pk}": colchones, f"cantidad_{self.alimentos.pk}": kits, **extra}
        if remito == "jpeg":
            cuerpo["remito"] = self._remito_http()
        elif remito is not None:
            cuerpo["remito"] = remito
        return cuerpo

    def test_sin_login_redirige_al_login(self):
        for url in (self.url_kits, self.url_recibir):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).url, f"{reverse('users:login')}?next={url}")
                self.assertEqual(self.client.post(url, {}).status_code, 302)

    def test_sin_la_capacidad_en_ningun_dispositivo_es_un_403(self):
        """Lo mismo que la API contesta con ``SIN_MODULO``: no abre esta parte del módulo."""
        sin_equipo = self._guardia("sin_equipo", [RECIBIR_KIT])
        admisor = self._guardia("admisor", [ADMITIR, "dispositivo.ver"], [self.club])
        de_becas = self._usuario("de_becas", ["becas.campo"], programa=self.becas)
        antes = self._foto(self.entrega)

        for usuario in (sin_equipo, admisor, de_becas, self.operador, self.supervisor, self.agente):
            self.client.force_login(usuario)
            for url in (self.url_kits, self.url_recibir):
                with self.subTest(usuario=usuario.username, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)
                    self.assertEqual(self.client.post(url, self._cuerpo()).status_code, 403)
        self.assertEqual(self._foto(self.entrega), antes)

    def test_la_guardia_de_otro_dispositivo_recibe_404(self):
        """**Mutación de RN-4.8 por HTTP.** ``recibir_kit`` en la Escuela no abre nada del Club.

        Visto en rojo: con ``RecepcionKitsMixin`` aceptando a quien tiene la capacidad en
        **algún** dispositivo (sin filtrar por el de la URL), los dos GET del Club contestan
        200 («200 != 404») y la guardia de la Escuela ve la entrega ajena. El 404 es el de un
        id inexistente: el cuerpo no nombra al Club.
        """
        self.client.force_login(self.guardia_escuela)
        antes = self._foto(self.entrega)
        # La entrega del Club pedida por el Club, y pedida por su propio dispositivo.
        por_la_escuela = self._url("dispositivo_kit_recibir", self.escuela.pk, self.entrega.pk)

        for url in (self.url_kits, self.url_recibir, por_la_escuela):
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 404)
                self.assertNotIn("Club Sarmiento", respuesta.content.decode())
                self.assertEqual(self.client.post(url, self._cuerpo()).status_code, 404)

        self.assertEqual(self._foto(self.entrega), antes)
        self.assertFalse(EntregaKit.objects.get(pk=self.entrega.pk).remito)
        self.assertFalse(EntradaBitacora.objects.exists())
        # …y un dispositivo que no existe contesta lo mismo.
        self.assertEqual(self.client.get(self._url("dispositivo_kits", 999_999)).status_code, 404)

    def test_la_guardia_ve_las_pendientes_de_su_dispositivo(self):
        preparada = self._entrega(dispositivo=self.club)
        self._en_camino(dispositivo=self.escuela)
        self.client.force_login(self.guardia)

        respuesta = self.client.get(self.url_kits)

        self.assertTemplateUsed(respuesta, "programas/emergencia/kits/pendientes.html")
        self.assertEqual([fila["entrega"] for fila in respuesta.context["filas"]], [self.entrega, preparada])
        self.assertContains(respuesta, f'href="{self.url_recibir}"')
        self.assertContains(respuesta, "Sin marca de salida")
        self.assertEqual(respuesta.context["url_dispositivo"], "")

    def test_las_pendientes_se_paginan(self):
        self._entrega(dispositivo=self.club)
        self.client.force_login(self.guardia)

        with patch("programas.views.emergencia_kits.PENDIENTES_POR_PAGINA", 1):
            primera = self.client.get(self.url_kits)
            segunda = self.client.get(self.url_kits, {"page": 2})

        self.assertEqual(len(primera.context["filas"]), 1)
        self.assertContains(primera, "page=2")
        self.assertEqual(len(segunda.context["filas"]), 1)
        self.assertNotEqual(primera.context["filas"][0]["entrega"], segunda.context["filas"][0]["entrega"])

    def test_el_titulo_del_listado_no_repite_el_modulo(self):
        self.client.force_login(self.guardia)

        respuesta = self.client.get(self.url_kits)

        self.assertRegex(respuesta.content.decode(), r"<h1[^>]*>\s*Kits\s*</h1>")
        self.assertNotContains(respuesta, "Emergencia · Kits</h1>")

    def test_confirmar_la_recepcion_pide_confirmacion_en_un_modal_que_envia_el_formulario(self):
        self.client.force_login(self.guardia)

        respuesta = self.client.get(self.url_recibir)

        self.assertContains(respuesta, 'id="form-recibir-entrega"')
        self.assertContains(respuesta, 'aria-labelledby="modal-confirmar-recepcion-titulo"')
        self.assertContains(respuesta, 'form="form-recibir-entrega"')
        # Enter en una cantidad no envía: el submit del formulario abre el modal, y el botón es un submit.
        self.assertContains(respuesta, "if (!modalConfirmar) { $event.preventDefault();")
        self.assertRegex(
            respuesta.content.decode(),
            r'<button type="submit" class="btn-nodo btn-brand btn-base"><i class="fas fa-check"[^>]*></i> Confirmar recepción',
        )
        self.assertContains(respuesta, "La recepción no se corrige")

    def test_el_enlace_al_dispositivo_solo_si_lo_puede_ver(self):
        con_ver = self._guardia("guardia_con_ver", [RECIBIR_KIT, "dispositivo.ver"], [self.club])
        self.client.force_login(con_ver)

        self.assertEqual(
            self.client.get(self.url_kits).context["url_dispositivo"],
            reverse("dispositivos:detalle", args=[self.club.pk]),
        )

    def test_el_formulario_llega_con_las_cantidades_vacias(self):
        """Cambio 586: quien recibe cuenta lo que llegó; el formulario no le sopla lo que se envió."""
        self.client.force_login(self.guardia)

        respuesta = self.client.get(self.url_recibir)

        self.assertTemplateUsed(respuesta, "programas/emergencia/kits/recibir.html")
        self.assertNotContains(respuesta, f'name="cantidad_{self.colchon.pk}" value=')
        self.assertNotContains(respuesta, f'name="cantidad_{self.alimentos.pk}" value=')
        self.assertContains(respuesta, 'enctype="multipart/form-data"')
        self.assertContains(respuesta, "Entregar a la directora.")
        self.assertContains(respuesta, "Se enviaron 10 · en unidad.")

    def _con_edificio(self):
        from programas.models import Edificio

        edificio = Edificio.objects.create(codigo="EG-1", nombre="Edificio guardia")
        edificio.dispositivos.add(self.club)
        EntregaKit.objects.filter(pk=self.entrega.pk).update(edificio=edificio)
        return edificio

    def test_con_dispositivo_ver_una_entrega_con_edificio_se_recibe_en_la_solapa_kits(self):
        edificio = self._con_edificio()
        con_ver = self._guardia("guardia_con_ver", [RECIBIR_KIT, "dispositivo.ver"], [self.club])
        self.client.force_login(con_ver)
        pagina = reverse("dispositivos:edificio_operativo", args=[self.club.pk, edificio.pk])
        destino = f"{pagina}?tab=kits&entrega={self.entrega.pk}"

        self.assertRedirects(self.client.get(self.url_recibir), destino, fetch_redirect_response=False)
        self.assertEqual(self.client.get(self.url_kits).context["filas"][0]["url"], destino)

    def test_sin_dispositivo_ver_la_recepcion_sigue_en_el_formulario_y_no_en_un_403(self):
        """La guardia con solo ``emergencia.recibir_kit`` no puede abrir la página del edificio (403): su fila y su GET
        van al formulario de recibir. Mutación: redirigir siempre a la solapa deja este test en rojo (403)."""
        self._con_edificio()
        self.client.force_login(self.guardia)

        respuesta = self.client.get(self.url_recibir, follow=True)

        self.assertEqual((respuesta.redirect_chain, respuesta.status_code), ([], 200))
        self.assertTemplateUsed(respuesta, "programas/emergencia/kits/recibir.html")
        self.assertContains(respuesta, 'enctype="multipart/form-data"')
        self.assertEqual(self.client.get(self.url_kits).context["filas"][0]["url"], self.url_recibir)

    def test_con_dispositivo_ver_acotado_a_otro_edificio_la_recepcion_sigue_en_el_formulario_y_no_en_un_404(self):
        """Dos filas del Equipo: una con ``dispositivo.ver`` + ``emergencia.recibir_kit`` acotada al edificio A y otra
        con solo ``recibir_kit`` para toda la institución. La entrega es del edificio B: la página del edificio le
        contesta 404, así que se recibe en el formulario. Mutación: decidir solo por ``dispositivo.ver`` (sin el alcance
        por edificio) deja este test en rojo (404).
        """
        from django.contrib.auth.models import User

        from programas.models import Edificio

        edificio_a = Edificio.objects.create(codigo="EG-A", nombre="Edificio A")
        edificio_b = self._con_edificio()
        edificio_a.dispositivos.add(self.club)
        usuario = User.objects.create_user(username="guardia_dos_filas", password="x")
        rol_con_ver = self._sumar_rol(usuario, [RECIBIR_KIT, "dispositivo.ver"], self.dispositivos).groups.get()
        fila_a = MiembroEquipoDispositivo.objects.create(
            dispositivo=self.club,
            usuario=usuario,
            rol=rol_con_ver,
            alcance=MiembroEquipoDispositivo.Alcance.EDIFICIOS,
        )
        fila_a.edificios.set([edificio_a])
        usuario = self._sumar_rol(usuario, [RECIBIR_KIT], self.dispositivos)
        solo_recibir = usuario.groups.exclude(pk=rol_con_ver.pk).get()
        MiembroEquipoDispositivo.objects.create(
            dispositivo=self.club,
            usuario=usuario,
            rol=solo_recibir,
            alcance=MiembroEquipoDispositivo.Alcance.INSTITUCION,
        )
        self.assertEqual(self.entrega.pk, EntregaKit.objects.get(edificio=edificio_b).pk)
        self.client.force_login(usuario)

        respuesta = self.client.get(self.url_recibir, follow=True)

        self.assertEqual((respuesta.redirect_chain, respuesta.status_code), ([], 200))
        self.assertTemplateUsed(respuesta, "programas/emergencia/kits/recibir.html")
        self.assertEqual(self.client.get(self.url_kits).context["filas"][0]["url"], self.url_recibir)

    def test_hu_4_3_confirmar_sin_tocar_nada_la_deja_recibida(self):
        self.client.force_login(self.guardia)

        respuesta = self.client.post(self.url_recibir, self._cuerpo(observacion="Todo en orden."))

        self.assertRedirects(respuesta, self.url_kits)
        recibida = EntregaKit.objects.get(pk=self.entrega.pk)
        self.assertEqual((recibida.estado, recibida.recibida_por), (Estado.RECIBIDA, self.guardia))
        self.assertEqual(recibida.observacion_dispositivo, "Todo en orden.")
        self.assertTrue(recibida.remito.name.startswith(f"emergencia/entregas/{recibida.carpeta_media}/"))
        self.assertEqual(self._avisos(respuesta), [f"Entrega {recibida.numero}: recibida completa."])
        self.assertEqual(self.client.get(self.url_kits).context["filas"], [])

    def test_hu_4_3_cambiar_una_cantidad_la_deja_con_diferencias(self):
        self.client.force_login(self.guardia)

        respuesta = self.client.post(self.url_recibir, self._cuerpo(colchones=8))

        recibida = EntregaKit.objects.get(pk=self.entrega.pk)
        self.assertEqual(recibida.estado, Estado.RECIBIDA_CON_DIFERENCIAS)
        self.assertEqual(recibida.lineas.get(item=self.colchon).diferencia, -2)
        self.assertEqual(self._avisos(respuesta), [f"Entrega {recibida.numero}: recibida · 1 ítem con diferencia."])

    def test_hu_4_3_sin_la_foto_dice_que_falta_el_remito(self):
        self.client.force_login(self.guardia)

        respuesta = self.client.post(self.url_recibir, self._cuerpo(remito=None))

        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, "Falta la foto del remito.", status_code=400)
        self.assertEqual(EntregaKit.objects.get(pk=self.entrega.pk).estado, Estado.EN_CAMINO)

    def test_un_remito_que_no_es_jpeg_vuelve_a_su_campo(self):
        self.client.force_login(self.guardia)
        png = self._remito_http("remito.png", PNG, "image/png")

        respuesta = self.client.post(self.url_recibir, self._cuerpo(colchones=7, remito=png))

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.context["form"].errors["remito"], ["La foto del remito tiene que llegar en JPEG."])
        # Lo que ya había cargado no se pierde.
        self.assertContains(respuesta, f'name="cantidad_{self.colchon.pk}" value="7"', status_code=400)
        self.assertEqual(EntregaKit.objects.get(pk=self.entrega.pk).estado, Estado.EN_CAMINO)

    def test_una_cantidad_vacia_o_negativa_no_se_acepta(self):
        self.client.force_login(self.guardia)

        for cantidad, aviso in (("", "Indicá cuánto llegó, aunque sea cero."), ("-1", "cero o más")):
            with self.subTest(cantidad=cantidad):
                respuesta = self.client.post(self.url_recibir, self._cuerpo(colchones=cantidad))
                self.assertContains(respuesta, aviso, status_code=400)
        self.assertEqual(EntregaKit.objects.get(pk=self.entrega.pk).estado, Estado.EN_CAMINO)

    def test_si_la_mesa_la_cancelo_mientras_cargaba_avisa_y_vuelve_a_las_pendientes(self):
        self.client.force_login(self.guardia)
        self.reloj.avanzar(hours=5, minutes=2)
        servicio.cancelar_entrega(self.entrega, self.operador, "El camión volvió")

        respuesta = self.client.post(self.url_recibir, self._cuerpo())

        self.assertRedirects(respuesta, self.url_kits)
        self.assertEqual(
            self._avisos(respuesta),
            [f"Entrega {self.entrega.numero} cancelada por la mesa a las 15:02. Ya no se puede recibir."],
        )
        self.assertFalse(EntregaKit.objects.get(pk=self.entrega.pk).remito)

    def test_abrir_una_ya_recibida_avisa_y_vuelve_a_las_pendientes(self):
        self._recibir(self.entrega)
        self.client.force_login(self.guardia)

        respuesta = self.client.get(self.url_recibir)

        self.assertRedirects(respuesta, self.url_kits)
        self.assertIn("ya la recibió", self._avisos(respuesta)[0])

    def test_una_fila_del_equipo_dada_de_baja_ya_no_entra(self):
        MiembroEquipoDispositivo.objects.filter(usuario=self.guardia).update(activo=False)
        self.client.force_login(self.guardia)

        self.assertEqual(self.client.get(self.url_kits).status_code, 403)
