"""Módulo Emergencia, PR 7: E6 · «Emergencia · Llegadas» en el backoffice (la guardia del dispositivo).

Qué fija este archivo:

* **Acceso (plan C2, Cambio 432)** — sin sesión, al login; sin ``dispositivo.admitir`` en
  ningún lado, 403; con la capacidad pero sin alcance sobre el dispositivo, 404, el mismo de
  un id inexistente. Y un caso o una derivación **de otro dispositivo** pedidos por id dentro
  de uno propio, 404. La mutación está en ``AlcancePorHttpTests``.
* **RU-2** — las vistas no tienen reglas: el recorrido entero por HTTP (buscar → aceptar →
  confirmar 3 → cerrar con diferencia, y el ingreso directo) termina en el mismo estado que
  dejan los servicios.
* **RU-9 por pantalla** — buscar el DNI de una familia derivada a otro dispositivo no lo nombra.
* **RU-22 / C4** — las confirmaciones con motivo son un POST con CSRF; nada de SweetAlert2.
* **E3 y la bandeja** — la mesa ve a los integrantes y las marcas con el dato real.
* **``/media/``** — las fotos del caso las ve la guardia del dispositivo de la derivación
  vigente, y nadie más fuera de la mesa.
"""

import shutil
import tempfile
from pathlib import Path

from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse

from core.models import Localidad
from legajos.models import Ciudadano
from programas.forms_emergencia_dispositivo import CONTROLES_DE_LA_FICHA, FichaIntegranteForm
from programas.models import (
    AdjuntoCaso,
    CasoEmergencia,
    Derivacion,
    Estadia,
    IntegranteGrupo,
    Plaza,
    ReservaPlaza,
    TrazaCaso,
)
from programas.selectors import emergencia_mesa
from programas.services import emergencia as mesa
from programas.services import emergencia_alojar as servicio
from programas.tests.test_emergencia_alojar_base import BaseAlojar
from programas.tests.test_emergencia_casos import JPEG

Estado = CasoEmergencia.Estado

TEMPLATES = Path(__file__).resolve().parents[1] / "templates/programas/emergencia/dispositivo"


def ficha_post(dni, **cambios):
    """El POST de la ficha con el mínimo, como lo manda el formulario (plano, sí/no en texto)."""

    datos = {
        "parentesco": "HIJO",
        "dni": dni,
        "nombre": "Juan",
        "apellido": "Pérez",
        "sexo": "M",
        "fecha_nacimiento": "2006-03-10",
        "embarazo": "no",
        "discapacidad": "no",
        "electrodependiente": "no",
        "medicacion_critica": "no",
        "alergias_graves": "no",
    }
    datos.update(cambios)
    return datos


class BaseLlegadas(BaseAlojar):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.guardia)

    def _url(self, nombre, *args, dispositivo=None):
        return reverse(f"dispositivos:emergencia_{nombre}", args=[(dispositivo or self.club).pk, *args])

    def _avisos(self, respuesta):
        dejados = [str(mensaje) for mensaje in get_messages(respuesta.wsgi_request)._queued_messages]
        list(get_messages(respuesta.wsgi_request))
        return dejados

    def _formulario1(self, **cambios):
        datos = {
            "traslado": "BOMBEROS",
            "dni": "33444555",
            "nombre": "Marta",
            "apellido": "Ríos",
            "adultos_f": "1",
            "adultos_m": "1",
            "menores_f": "1",
        }
        datos.update(cambios)
        return datos


# ---------------------------------------------------------------------------
# Acceso
# ---------------------------------------------------------------------------


class AccesoTests(BaseLlegadas):
    def setUp(self):
        super().setUp()
        self.caso, self.derivacion = self._aceptado()
        _otro, self.pendiente = self._derivado(dni="30222333", plazas=2)
        self.gets = [
            self._url("llegadas"),
            self._url("integrantes", self.caso.pk),
            self._url("ficha", self.caso.pk, 1),
            self._url("cama", self.caso.pk, 1),
            self._url("avisar"),
            self._url("ingreso_directo"),
        ]
        self.posts = [
            self._url("aceptar", self.pendiente.pk),
            self._url("rechazar", self.pendiente.pk),
            self._url("agregar", self.caso.pk),
            self._url("diferencia", self.caso.pk),
            self._url("cancelar", self.caso.pk),
            self._url("alojar", self.caso.pk),
        ]

    def test_las_urls_cuelgan_del_dispositivo(self):
        self.assertEqual(self._url("llegadas"), f"/dispositivos/{self.club.pk}/emergencia/llegadas/")

    def test_sin_sesion_todo_va_al_login(self):
        self.client.logout()
        for url in self.gets:
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), f"/?next={url}", fetch_redirect_response=False)
        for url in self.posts:
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, {}).status_code, 302)
        self.assertEqual(Derivacion.objects.get(pk=self.pendiente.pk).estado, Derivacion.Estado.PENDIENTE)

    def test_la_guardia_del_dispositivo_abre_todas_las_pantallas(self):
        for url in self.gets:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_sin_la_capacidad_en_ningun_lado_es_403(self):
        """La mesa no opera dispositivos, y un rol de Becas tampoco."""

        for usuario in (self.operador, self.supervisor, self._usuario("becario", ["becas.campo"], programa=self.becas)):
            self.client.force_login(usuario)
            for url in self.gets:
                with self.subTest(usuario=usuario.username, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)
            for url in self.posts:
                with self.subTest(usuario=usuario.username, url=url):
                    self.assertEqual(self.client.post(url, {}).status_code, 403)

    def test_con_la_capacidad_pero_sin_alcance_sobre_el_dispositivo_es_404(self):
        """Plan C2: el mismo 404 que un dispositivo que no existe."""

        self.client.force_login(self.guardia_escuela)
        for url in self.gets:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
        for url in self.posts:
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, {"motivo": "SIN_PLAZAS"}).status_code, 404)
        self.assertEqual(self.client.get("/dispositivos/999999/emergencia/llegadas/").status_code, 404)
        self.assertEqual(Derivacion.objects.get(pk=self.pendiente.pk).estado, Derivacion.Estado.PENDIENTE)

    def test_el_detalle_del_dispositivo_ofrece_llegadas_solo_a_quien_puede_admitir(self):
        url = reverse("dispositivos:detalle", args=[self.club.pk])
        self.assertContains(self.client.get(url), self._url("llegadas"))

        solo_lectura = self._guardia("portero", self.club, capacidades=("dispositivo.ver",))
        self.client.force_login(solo_lectura)
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "Emergencia · Llegadas")

    def test_ninguna_pantalla_nueva_usa_sweetalert_ni_confirm_nativo(self):
        """Plan C4, RU-22: Modal y ModernModal."""

        for template in TEMPLATES.glob("*.html"):
            with self.subTest(template=template.name):
                texto = template.read_text(encoding="utf-8")
                self.assertNotIn("Swal", texto)
                self.assertNotIn("confirm(", texto)
                self.assertNotIn("data-confirm=", texto)


class AlcancePorHttpTests(BaseLlegadas):
    """Lo de **otro** dispositivo, pedido por id dentro del propio, no existe (RU-9, C2)."""

    def test_admitir_en_a_no_acepta_ni_rechaza_una_derivacion_de_b_aunque_conozca_el_id(self):
        """**Mutación nueva del PR 7, por HTTP.**

        Visto en rojo sacando ``dispositivo=self.dispositivo`` del ``get_object_or_404`` de
        ``_AccionDeDerivacionView.preparar``: la vista le pasa al servicio la derivación de la
        Escuela, el servicio la frena con ``PermissionDenied`` y la respuesta es **403** —que
        confirma que ese id existe— en vez de 404.
        """

        caso, de_la_escuela = self._derivado(dispositivo=self.escuela)

        for accion, cuerpo in (("aceptar", {}), ("rechazar", {"motivo": "SIN_PLAZAS"})):
            with self.subTest(accion=accion):
                respuesta = self.client.post(self._url(accion, de_la_escuela.pk), cuerpo)
                self.assertEqual(respuesta.status_code, 404)

        de_la_escuela.refresh_from_db()
        self.assertEqual(de_la_escuela.estado, Derivacion.Estado.PENDIENTE)
        self.assertEqual(self._estado(caso), Estado.DERIVADO)
        self.assertFalse(ReservaPlaza.objects.exists())
        self.assertEqual(TrazaCaso.objects.filter(caso=caso).count(), 3)

    def test_el_caso_de_otro_dispositivo_no_existe_en_el_mio(self):
        caso, de_la_escuela = self._derivado(dispositivo=self.escuela)
        servicio.aceptar_derivacion(derivacion=de_la_escuela, usuario=self.guardia_escuela)

        for nombre, args in (("integrantes", ()), ("ficha", (1,)), ("cama", (1,)), ("alojar", ())):
            with self.subTest(pantalla=nombre):
                self.assertEqual(self.client.get(self._url(nombre, caso.pk, *args)).status_code, 404)
        for nombre in ("agregar", "diferencia", "cancelar"):
            with self.subTest(accion=nombre):
                respuesta = self.client.post(self._url(nombre, caso.pk), {"motivo": "NO_LLEGO"})
                self.assertEqual(respuesta.status_code, 404)
        respuesta = self.client.post(self._url("ficha", caso.pk, 1), ficha_post("45000111"))
        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)
        self.assertFalse(Estadia.objects.exists())

    def test_buscar_una_familia_derivada_a_otro_dispositivo_no_lo_nombra(self):
        """RU §6 n.° 2, por pantalla."""

        self._derivado(dispositivo=self.escuela)

        respuesta = self.client.get(self._url("llegadas"), {"dni": "30111222"})

        self.assertContains(respuesta, "No hay una derivación para este DNI en tu dispositivo.")
        self.assertNotContains(respuesta, "Escuela")
        self.assertNotContains(respuesta, "Aceptar y reservar camas")
        self.assertContains(respuesta, "Ingresar igual")
        self.assertContains(respuesta, "Avisar a la mesa")

    def test_la_lista_pide_ver_una_derivacion_de_otro_dispositivo_y_no_la_muestra(self):
        _caso, de_la_escuela = self._derivado(dispositivo=self.escuela)

        respuesta = self.client.get(self._url("llegadas"), {"derivacion": de_la_escuela.pk})

        self.assertRedirects(respuesta, self._url("llegadas"), fetch_redirect_response=False)
        self.assertIn("ya no está para recibir", self._avisos(respuesta)[0])


# ---------------------------------------------------------------------------
# Paso 1 · Buscar, aceptar, rechazar
# ---------------------------------------------------------------------------


class LlegadasTests(BaseLlegadas):
    def test_la_pantalla_lista_lo_que_el_dispositivo_tiene_por_recibir(self):
        self._derivado()
        en_curso, _derivacion = self._aceptado(dni="30222333", apellido="Zalazar", plazas=2)
        self._derivado(dispositivo=self.escuela, dni="30333444", apellido="Quiroga")

        respuesta = self.client.get(self._url("llegadas"))

        self.assertTemplateUsed(respuesta, "programas/emergencia/dispositivo/llegadas.html")
        self.assertContains(respuesta, "Familia Benítez")
        self.assertContains(respuesta, "Familia Zalazar")
        self.assertContains(respuesta, "0 de 7 confirmadas")
        self.assertNotContains(respuesta, "Quiroga")
        self.assertContains(respuesta, self._url("integrantes", en_curso.pk))

    def test_buscar_el_dni_del_responsable_muestra_la_derivacion_con_sus_acciones(self):
        _caso, derivacion = self._derivado(embarazo=True)

        respuesta = self.client.get(self._url("llegadas"), {"dni": "30.111.222"})

        self.assertContains(respuesta, "Familia Benítez · 7 personas declaradas")
        self.assertContains(respuesta, "Embarazo")
        self.assertContains(respuesta, f'action="{self._url("aceptar", derivacion.pk)}"')
        self.assertContains(respuesta, f'action="{self._url("rechazar", derivacion.pk)}"')
        self.assertContains(respuesta, 'role="dialog"')
        self.assertContains(respuesta, "csrfmiddlewaretoken")

    def test_un_dni_mal_escrito_vuelve_con_el_error_en_el_campo(self):
        respuesta = self.client.get(self._url("llegadas"), {"dni": "abc"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "DNI válido")

    def test_una_persona_alojada_en_otro_dispositivo_se_informa_sin_decir_donde(self):
        self._ocupar(self.escuela, 1)
        alojada = Estadia.objects.get().ciudadano

        respuesta = self.client.get(self._url("llegadas"), {"dni": alojada.dni})

        self.assertContains(respuesta, "Alojada en otro dispositivo de la red.")
        self.assertNotContains(respuesta, "Escuela")
        self.assertNotContains(respuesta, "Ingresar igual")

    def test_sin_camas_libres_no_se_ofrece_ingresar_igual(self):
        self._ocupar(self.club, 9)
        respuesta = self.client.get(self._url("llegadas"), {"dni": "39999999"})
        self.assertContains(respuesta, "No hay camas libres")
        self.assertNotContains(respuesta, "Ingresar igual")
        self.assertContains(respuesta, "Avisar a la mesa")

    def test_aceptar_lleva_a_los_integrantes_con_las_camas_reservadas(self):
        caso, derivacion = self._derivado()

        respuesta = self.client.post(self._url("aceptar", derivacion.pk))

        self.assertRedirects(respuesta, self._url("integrantes", caso.pk), fetch_redirect_response=False)
        self.assertEqual(self._avisos(respuesta), ["Derivación aceptada. Reservé 7 de 7 camas."])
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)
        self.assertEqual(ReservaPlaza.objects.filter(derivacion=derivacion).count(), 7)

    def test_aceptar_con_menos_camas_avisa_cuantas_faltan(self):
        _caso, derivacion = self._derivado()
        self._ocupar(self.club, 4)
        respuesta = self.client.post(self._url("aceptar", derivacion.pk))
        self.assertIn("Reservé 5 de 7 · faltan 2 camas", self._avisos(respuesta)[0])

    def test_aceptar_sin_camas_vuelve_a_la_derivacion_con_el_motivo(self):
        caso, derivacion = self._derivado()
        self._ocupar(self.club, 9)

        respuesta = self.client.post(self._url("aceptar", derivacion.pk))

        self.assertRedirects(
            respuesta, f"{self._url('llegadas')}?derivacion={derivacion.pk}", fetch_redirect_response=False
        )
        self.assertEqual(self._avisos(respuesta), [servicio.SIN_PLAZAS_PARA_ACEPTAR])
        self.assertEqual(self._estado(caso), Estado.DERIVADO)

    def test_la_segunda_pestana_que_acepta_recibe_el_aviso_y_sigue_con_el_ingreso(self):
        """03 §7: es el 409 de la API. Acá, el aviso de recargar; nunca un 500."""

        caso, derivacion = self._derivado()
        self.client.post(self._url("aceptar", derivacion.pk))

        respuesta = self.client.post(self._url("aceptar", derivacion.pk))

        self.assertRedirects(respuesta, self._url("integrantes", caso.pk), fetch_redirect_response=False)
        self.assertIn("ya la aceptó", self._avisos(respuesta)[-1])
        self.assertEqual(ReservaPlaza.objects.filter(derivacion=derivacion).count(), 7)

    def test_rechazar_pide_motivo_y_devuelve_el_caso_a_la_mesa(self):
        caso, derivacion = self._derivado()

        sin_motivo = self.client.post(self._url("rechazar", derivacion.pk), {"motivo": ""})
        self.assertIn("Elegí el motivo", self._avisos(sin_motivo)[0])
        self.assertEqual(self._estado(caso), Estado.DERIVADO)
        otro_sin_texto = self.client.post(self._url("rechazar", derivacion.pk), {"motivo": "OTRO"})
        self.assertIn("contá qué pasó", self._avisos(otro_sin_texto)[0])

        respuesta = self.client.post(self._url("rechazar", derivacion.pk), {"motivo": "NO_CUMPLE_PERFIL"})

        self.assertRedirects(respuesta, self._url("llegadas"), fetch_redirect_response=False)
        self.assertEqual(self._estado(caso), Estado.EN_GESTION)
        derivacion.refresh_from_db()
        self.assertEqual((derivacion.estado, derivacion.motivo), (Derivacion.Estado.RECHAZADA, "No cumple perfil"))

    def test_los_post_exigen_csrf(self):
        caso, derivacion = self._derivado()
        estricto = Client(enforce_csrf_checks=True)
        estricto.force_login(self.guardia)

        self.assertEqual(estricto.post(self._url("aceptar", derivacion.pk)).status_code, 403)
        self.assertEqual(estricto.post(self._url("rechazar", derivacion.pk), {"motivo": "NO_LLEGO"}).status_code, 403)
        self.assertEqual(self._estado(caso), Estado.DERIVADO)


# ---------------------------------------------------------------------------
# Paso 2 · Integrantes, ficha y cama
# ---------------------------------------------------------------------------


class IntegrantesTests(BaseLlegadas):
    def setUp(self):
        super().setUp()
        self.caso, self.derivacion = self._aceptado()
        self.reservas = self._reservas(self.derivacion)

    def test_la_lista_muestra_las_filas_el_contador_y_las_acciones_del_estado(self):
        respuesta = self.client.get(self._url("integrantes", self.caso.pk))

        self.assertTemplateUsed(respuesta, "programas/emergencia/dispositivo/integrantes.html")
        self.assertContains(respuesta, "Persona 7")
        self.assertContains(respuesta, "0 de 7 confirmadas")
        self.assertContains(respuesta, 'aria-valuemax="7"')
        self.assertContains(respuesta, "Agregar persona")
        # Sin nadie confirmado se puede cancelar, y todavía no hay diferencia que cerrar.
        self.assertContains(respuesta, f'action="{self._url("cancelar", self.caso.pk)}"')
        self.assertNotContains(respuesta, f'action="{self._url("diferencia", self.caso.pk)}"')
        self.assertNotContains(respuesta, "Familia alojada</a>")

    def test_el_formulario_de_la_ficha_tiene_un_control_por_cada_campo_del_esquema(self):
        """El backoffice no puede quedar atrás del esquema que comparte con la app."""

        del_esquema = {campo for seccion in servicio.ESQUEMA_FICHA.values() for campo in seccion}
        self.assertEqual(set(CONTROLES_DE_LA_FICHA), del_esquema)
        form = FichaIntegranteForm()
        self.assertEqual([seccion["numero"] for seccion in form.secciones()], [1, 2, 3, 4, 5, 6, 7, 8])
        self.assertEqual([s["codigo"] for s in form.secciones() if s["minimo"]], list(servicio.SECCIONES_MINIMAS))
        self.assertTrue(del_esquema <= set(form.fields))

    def test_la_ficha_ofrece_primero_una_cama_reservada_para_la_familia(self):
        respuesta = self.client.get(self._url("ficha", self.caso.pk, 2))

        self.assertTemplateUsed(respuesta, "programas/emergencia/dispositivo/ficha.html")
        self.assertContains(respuesta, "Reservada para esta familia")
        self.assertContains(respuesta, f'name="plaza" value="{self.reservas[0].plaza_id}"')
        self.assertContains(respuesta, "Mínimo para confirmar")
        self.assertContains(respuesta, "csrfmiddlewaretoken")

    def test_la_persona_1_arranca_con_los_datos_del_responsable(self):
        respuesta = self.client.get(self._url("ficha", self.caso.pk, 1))
        self.assertContains(respuesta, 'value="30111222"')
        self.assertContains(respuesta, 'value="Benítez"')

    def test_el_mapa_marca_las_camas_de_la_familia_y_solo_enlaza_las_elegibles(self):
        """Modo emergencia de la pieza, sin tocarla: texto propio, tono de reserva y selección única."""

        _otro, otra = self._derivado(dni="30222333", plazas=1)
        servicio.aceptar_derivacion(derivacion=otra, usuario=self.guardia)
        ajena = ReservaPlaza.objects.get(derivacion=otra).plaza
        elegida = self.reservas[1].plaza_id

        respuesta = self.client.get(self._url("cama", self.caso.pk, 2), {"cama": elegida})

        self.assertTemplateUsed(respuesta, "components/_mapa_plazas.html")
        self.assertTemplateUsed(respuesta, "components/_leyenda_plazas.html")
        html = respuesta.content.decode()
        self.assertEqual(html.count("Reservada para esta familia"), 7 + 1, "siete camas y la leyenda")
        self.assertEqual(html.count("Elegida"), 1, "la selección es única")
        ficha = self._url("ficha", self.caso.pk, 2)
        for reserva in self.reservas:
            self.assertIn(f'href="{ficha}?cama={reserva.plaza_id}"', html)
        self.assertNotIn(f"?cama={ajena.pk}", html, "se puede elegir la cama de otra familia")
        # Siete de la familia, la única libre y el «volver» del encabezado, que conserva la elegida.
        self.assertEqual(html.count(f'href="{ficha}?cama='), 7 + 1 + 1)

    def test_elegir_otra_cama_en_el_mapa_vuelve_a_la_ficha_con_esa_cama(self):
        libre = self._cama_libre()
        respuesta = self.client.get(self._url("ficha", self.caso.pk, 2), {"cama": libre.pk})
        self.assertContains(respuesta, f'name="plaza" value="{libre.pk}"')
        self.assertContains(respuesta, "Disponible")

    def test_una_cama_que_no_se_puede_elegir_cae_en_la_sugerida(self):
        ajena = Plaza.objects.filter(sector__dispositivo=self.escuela).first()
        respuesta = self.client.get(self._url("ficha", self.caso.pk, 2), {"cama": ajena.pk})
        self.assertContains(respuesta, f'name="plaza" value="{self.reservas[0].plaza_id}"')

    def test_confirmar_por_http_aloja_a_la_persona_en_la_cama_que_mostro_la_pantalla(self):
        plaza = self.reservas[2].plaza

        respuesta = self.client.post(
            self._url("ficha", self.caso.pk, 2), ficha_post("45000111", plaza=str(plaza.pk), telefono="3624 111111")
        )

        self.assertRedirects(respuesta, self._url("integrantes", self.caso.pk), fetch_redirect_response=False)
        self.assertEqual(
            self._avisos(respuesta), [f"Juan Pérez quedó en la cama {plaza.codigo} (General) · 1 de 7 confirmadas."]
        )
        estadia = Estadia.objects.get()
        self.assertEqual((estadia.plaza, estadia.ciudadano.dni), (plaza, "45000111"))
        integrante = IntegranteGrupo.objects.get(grupo=self.caso.grupo, orden=2)
        self.assertEqual(integrante.ficha["avisos_salud"]["embarazo"], False)
        self.assertEqual(integrante.ficha["datos_personales"]["telefono"], "3624 111111")
        lista = self.client.get(self._url("integrantes", self.caso.pk))
        self.assertContains(lista, "Pérez, Juan")
        self.assertContains(lista, "1 de 7 confirmadas")
        self.assertContains(lista, "Ficha incompleta")
        self.assertContains(lista, f'action="{self._url("diferencia", self.caso.pk)}"')

    def test_sin_el_minimo_vuelve_la_ficha_con_cada_error_en_su_campo_y_no_crea_nada(self):
        datos = ficha_post("45000111", plaza=str(self.reservas[0].plaza_id), embarazo="", sexo="")

        respuesta = self.client.post(self._url("ficha", self.caso.pk, 2), datos)

        self.assertEqual(respuesta.status_code, 400)
        form = respuesta.context["form"]
        self.assertIn("Falta: avisos de salud", form.errors["embarazo"][0])
        self.assertIn("sexo", form.errors)
        self.assertContains(respuesta, 'value="Pérez"', status_code=400)
        self.assertFalse(Ciudadano.objects.filter(dni="45000111").exists())
        self.assertFalse(Estadia.objects.exists())

    def test_el_rechazo_de_la_cama_va_arriba_del_formulario(self):
        ajena = Plaza.objects.filter(sector__dispositivo=self.escuela).first()

        respuesta = self.client.post(self._url("ficha", self.caso.pk, 2), ficha_post("45000111", plaza=str(ajena.pk)))

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.context["form"].non_field_errors(), [servicio.ELEGI_UNA_CAMA])
        self.assertFalse(Estadia.objects.exists())

    def test_confirmar_dos_veces_la_misma_fila_avisa_y_no_duplica(self):
        url = self._url("ficha", self.caso.pk, 2)
        self.client.post(url, ficha_post("45000111", plaza=str(self.reservas[0].plaza_id)))

        respuesta = self.client.post(url, ficha_post("45000999", plaza=str(self.reservas[1].plaza_id)))

        # La fila ya está confirmada: ese POST es la ficha complementaria, no otra confirmación.
        self.assertEqual(Estadia.objects.count(), 1)
        self.assertFalse(Ciudadano.objects.filter(dni="45000999").exists())
        self.assertEqual(respuesta.status_code, 302)

    def test_la_ficha_de_una_persona_confirmada_deja_completar_las_secciones_que_faltan(self):
        url = self._url("ficha", self.caso.pk, 2)
        self.client.post(url, ficha_post("45000111", plaza=str(self.reservas[0].plaza_id)))

        pantalla = self.client.get(url)
        self.assertContains(pantalla, "Pérez, Juan")
        self.assertContains(pantalla, "Falta: Educación")
        self.assertNotContains(pantalla, 'name="dni"')
        self.assertNotContains(pantalla, 'name="plaza"')

        respuesta = self.client.post(
            url,
            {
                "nivel_educativo": "SECUNDARIO",
                "asiste_escuela": "si",
                "vacunacion_sin_datos": "on",
                "obra_social": "No tiene",
                "trabajo_sin_datos": "on",
                "mascotas": "no",
            },
        )

        self.assertRedirects(respuesta, self._url("integrantes", self.caso.pk), fetch_redirect_response=False)
        self.assertEqual(self._avisos(respuesta)[-1], "La ficha de la persona 2 quedó completa.")
        integrante = IntegranteGrupo.objects.get(grupo=self.caso.grupo, orden=2)
        self.assertTrue(integrante.ficha_completa)
        self.assertEqual(integrante.ficha["educacion"], {"nivel_educativo": "SECUNDARIO", "asiste_escuela": True})
        self.assertEqual(integrante.ficha["vacunacion"], {"sin_datos": True})
        # Y al volver, el formulario trae lo guardado.
        de_nuevo = self.client.get(url)
        self.assertEqual(de_nuevo.context["form"].initial["asiste_escuela"], "si")
        self.assertIs(de_nuevo.context["form"].initial["trabajo_sin_datos"], True)

    def test_agregar_persona_suma_la_fila_y_abre_su_ficha_sin_cama_reservada(self):
        for orden, reserva in enumerate(self.reservas, start=1):
            self._confirmar(self.caso, orden, str(45_000_100 + orden), plaza=reserva.plaza)

        respuesta = self.client.post(self._url("agregar", self.caso.pk))

        self.assertRedirects(respuesta, self._url("ficha", self.caso.pk, 8), fetch_redirect_response=False)
        ficha = self.client.get(self._url("ficha", self.caso.pk, 8))
        # Quedan dos camas libres en el Club: no hay reservada, así que no se sugiere ninguna.
        self.assertContains(ficha, "Sin cama elegida")
        self.assertContains(ficha, "Elegir cama")
        lista = self.client.get(self._url("integrantes", self.caso.pk))
        self.assertContains(lista, "7 de 8 confirmadas")
        self.assertContains(lista, "(7 declaradas al relevar)")

    def test_confirmar_sin_cama_cuando_no_queda_ninguna_lo_dice(self):
        """HU-3.5."""

        for orden, reserva in enumerate(self.reservas, start=1):
            self._confirmar(self.caso, orden, str(45_000_100 + orden), plaza=reserva.plaza)
        self._ocupar(self.club, 9)
        self.client.post(self._url("agregar", self.caso.pk))

        respuesta = self.client.post(self._url("ficha", self.caso.pk, 8), ficha_post("45000999"))

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.context["form"].non_field_errors(), [servicio.SIN_CAMA_LIBRE])


# ---------------------------------------------------------------------------
# Paso 3 · Cerrar el ingreso
# ---------------------------------------------------------------------------


class CerrarElIngresoPorHttpTests(BaseLlegadas):
    def _familia_confirmada(self, personas=2):
        caso, derivacion = self._aceptado(menores_f=0, menores_m=0, adultos_f=1, adultos_m=personas - 1)
        for orden, reserva in enumerate(self._reservas(derivacion), start=1):
            self._confirmar(caso, orden, str(45_000_100 + orden), plaza=reserva.plaza)
        return caso

    def test_familia_alojada_muestra_el_resumen_y_cierra_el_ingreso(self):
        caso = self._familia_confirmada(2)
        url = self._url("alojar", caso.pk)

        pantalla = self.client.get(url)
        self.assertTemplateUsed(pantalla, "programas/emergencia/dispositivo/alojar.html")
        self.assertContains(pantalla, "2 de 2 confirmadas")
        sector = pantalla.context["form"].initial["sector"]
        self.assertIsNotNone(sector, "el sector no vino preseleccionado con el de las camas")

        respuesta = self.client.post(
            url, {"sector": str(sector), "aula": "Aula 3", "tarjeta_entregada": "on", "tarjeta_numero": "0042"}
        )

        self.assertRedirects(respuesta, self._url("llegadas"), fetch_redirect_response=False)
        self.assertEqual(
            self._avisos(respuesta)[-1],
            "Familia Benítez alojada · 2 de 2 · General · Aula 3. Podés buscar otra familia.",
        )
        fila = self._fila(caso)
        self.assertEqual((fila["estado"], fila["total_alojado"]), (Estado.ALOJADO, 2))
        self.assertEqual(fila["situacion"]["alojamiento"]["tarjeta_numero"], "0042")
        # La familia alojada sigue abriendo su lista, para terminar las fichas.
        lista = self.client.get(self._url("integrantes", caso.pk))
        self.assertContains(lista, "Dónde quedó la familia")
        self.assertNotContains(lista, "Agregar persona")

    def test_la_tarjeta_sin_numero_vuelve_el_formulario_con_el_error(self):
        caso = self._familia_confirmada(1)
        respuesta = self.client.post(self._url("alojar", caso.pk), {"tarjeta_entregada": "on"})
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("tarjeta_numero", respuesta.context["form"].errors)
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)

    def test_sin_todas_confirmadas_no_se_llega_al_paso_final(self):
        caso, _derivacion = self._aceptado()
        self._confirmar(caso, 1, "45000101")

        respuesta = self.client.get(self._url("alojar", caso.pk))

        self.assertRedirects(respuesta, self._url("integrantes", caso.pk), fetch_redirect_response=False)
        self.assertIn("Falta confirmar a 6 personas", self._avisos(respuesta)[-1])

    def test_cerrar_con_diferencia_pide_motivo_y_deja_el_ingreso_parcial(self):
        caso, derivacion = self._aceptado()
        self._confirmar(caso, 1, "45000101")
        url = self._url("diferencia", caso.pk)

        sin_motivo = self.client.post(url, {"motivo": ""})
        self.assertIn("Elegí el motivo", self._avisos(sin_motivo)[-1])
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)

        respuesta = self.client.post(url, {"motivo": "NO_LLEGO", "observacion": "Quedaron en lo de la abuela"})

        self.assertRedirects(respuesta, self._url("llegadas"), fetch_redirect_response=False)
        self.assertIn("1 de 7 personas alojadas", self._avisos(respuesta)[-1])
        fila = self._fila(caso)
        self.assertEqual((fila["estado"], fila["total_alojado"]), (Estado.ALOJADO, 1))
        self.assertFalse(ReservaPlaza.objects.filter(derivacion=derivacion, estado="VIGENTE").exists())

    def test_cancelar_el_ingreso_devuelve_el_caso_a_la_mesa(self):
        caso, derivacion = self._aceptado()

        respuesta = self.client.post(self._url("cancelar", caso.pk), {"motivo": "La familia no llegó"})

        self.assertRedirects(respuesta, self._url("llegadas"), fetch_redirect_response=False)
        self.assertEqual(self._estado(caso), Estado.EN_GESTION)
        # La pantalla del ingreso ya no existe para ese caso: vuelve a llegadas con el aviso.
        despues = self.client.get(self._url("integrantes", caso.pk))
        self.assertRedirects(despues, self._url("llegadas"), fetch_redirect_response=False)

    def test_cancelar_con_alguien_confirmado_dice_que_se_cierra_con_diferencia(self):
        caso, _derivacion = self._aceptado()
        self._confirmar(caso, 1, "45000101")
        respuesta = self.client.post(self._url("cancelar", caso.pk), {"motivo": "Me equivoqué"})
        self.assertRedirects(respuesta, self._url("integrantes", caso.pk), fetch_redirect_response=False)
        self.assertIn("cerrá el ingreso con diferencia", self._avisos(respuesta)[-1])
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)


# ---------------------------------------------------------------------------
# De punta a punta
# ---------------------------------------------------------------------------


class RecorridoCompletoTests(BaseLlegadas):
    def test_buscar_aceptar_confirmar_tres_y_cerrar_con_diferencia(self):
        """El guion de 03 §3 entero, por HTTP, con una familia de 7 de la que llegan 3."""

        caso, derivacion = self._derivado()

        buscada = self.client.get(self._url("llegadas"), {"dni": "30111222"})
        self.assertContains(buscada, "Aceptar y reservar camas")
        aceptada = self.client.post(self._url("aceptar", derivacion.pk))
        self.assertRedirects(aceptada, self._url("integrantes", caso.pk), fetch_redirect_response=False)

        for orden, dni in ((1, "30111222"), (2, "45000111"), (3, "45000222")):
            ficha = self.client.get(self._url("ficha", caso.pk, orden))
            plaza = ficha.context["form"].initial["plaza"]
            datos = ficha_post(dni, plaza=str(plaza), parentesco="JEFE" if orden == 1 else "HIJO")
            confirmada = self.client.post(self._url("ficha", caso.pk, orden), datos)
            self.assertRedirects(confirmada, self._url("integrantes", caso.pk), fetch_redirect_response=False)

        lista = self.client.get(self._url("integrantes", caso.pk))
        self.assertContains(lista, "3 de 7 confirmadas")
        cerrada = self.client.post(self._url("diferencia", caso.pk), {"motivo": "QUEDO_CON_FAMILIARES"})
        self.assertRedirects(cerrada, self._url("llegadas"), fetch_redirect_response=False)

        fila = self._fila(caso)
        self.assertEqual((fila["estado"], fila["total_alojado"]), (Estado.ALOJADO, 3))
        self.assertEqual(Estadia.objects.activas().filter(dispositivo=self.club).count(), 3)
        self.assertEqual(ReservaPlaza.objects.filter(derivacion=derivacion, estado="CONSUMIDA").count(), 3)
        self.assertEqual(ReservaPlaza.objects.filter(derivacion=derivacion, estado="LIBERADA").count(), 4)
        self.assertEqual(
            list(TrazaCaso.objects.filter(caso=caso).values_list("accion", flat=True))[-5:],
            [
                "DERIVACION_ACEPTADA",
                "INTEGRANTE_CONFIRMADO",
                "INTEGRANTE_CONFIRMADO",
                "INTEGRANTE_CONFIRMADO",
                "ALOJADO_CON_DIFERENCIA",
            ],
        )
        # Y la llegada ya no figura entre los ingresos en curso.
        self.assertNotContains(self.client.get(self._url("llegadas")), "Familia Benítez")

    def test_ingreso_directo_de_punta_a_punta(self):
        """HU-3.6: sin derivación → «Ingresar igual» → fichas → «Familia alojada»."""

        Localidad.objects.create(nombre="Resistencia")
        buscada = self.client.get(self._url("llegadas"), {"dni": "33444555"})
        self.assertContains(buscada, f"{self._url('ingreso_directo')}?dni=33444555")

        formulario = self.client.get(self._url("ingreso_directo"), {"dni": "33444555"})
        self.assertTemplateUsed(formulario, "programas/emergencia/dispositivo/formulario1.html")
        self.assertContains(formulario, 'value="33444555"')
        creado = self.client.post(self._url("ingreso_directo"), self._formulario1(menores_f="0"))

        caso = CasoEmergencia.objects.get()
        self.assertRedirects(creado, self._url("integrantes", caso.pk), fetch_redirect_response=False)
        self.assertEqual((caso.estado, caso.origen), (Estado.INGRESO_EN_CURSO, CasoEmergencia.Origen.DISPOSITIVO))
        self.assertEqual(caso.localidad.nombre, "Resistencia")

        for orden, dni in ((1, "33444555"), (2, "45000111")):
            ficha = self.client.get(self._url("ficha", caso.pk, orden))
            plaza = ficha.context["form"].initial["plaza"]
            datos = ficha_post(dni, plaza=str(plaza), parentesco="JEFE" if orden == 1 else "CONYUGE")
            self.client.post(self._url("ficha", caso.pk, orden), datos)
        alojada = self.client.post(self._url("alojar", caso.pk), {"aula": "Salón"})

        self.assertRedirects(alojada, self._url("llegadas"), fetch_redirect_response=False)
        self.assertEqual(self._estado(caso), Estado.ALOJADO)
        self.assertEqual(Estadia.objects.activas().filter(dispositivo=self.club).count(), 2)

    def test_el_ingreso_directo_sin_camas_vuelve_el_formulario_con_el_motivo(self):
        self._ocupar(self.club, 9)
        respuesta = self.client.post(self._url("ingreso_directo"), self._formulario1())
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.context["form"].non_field_errors(), [servicio.SIN_CAMAS_PARA_INGRESO_DIRECTO])
        self.assertFalse(CasoEmergencia.objects.exists())

    def test_avisar_a_la_mesa_crea_el_caso_en_la_puerta(self):
        respuesta = self.client.post(self._url("avisar"), self._formulario1())

        caso = CasoEmergencia.objects.get()
        self.assertRedirects(respuesta, self._url("llegadas"), fetch_redirect_response=False)
        self.assertEqual(caso.estado, Estado.NUEVO)
        self.assertEqual(caso.situacion["en_la_puerta_de"]["dispositivo"], "Club Sarmiento")
        self.assertIn("enviado a la mesa", self._avisos(respuesta)[-1])

    def test_el_formulario_1_del_dispositivo_no_exige_direccion_ni_localidad(self):
        respuesta = self.client.post(self._url("avisar"), self._formulario1(dni="", traslado=""))
        self.assertEqual(respuesta.status_code, 400)
        errores = respuesta.context["form"].errors
        self.assertEqual(set(errores), {"dni", "traslado"})


# ---------------------------------------------------------------------------
# La mesa lo ve (E2, E3) y las fotos
# ---------------------------------------------------------------------------


class LaMesaLoVeTests(BaseLlegadas):
    def test_la_situacion_de_la_etapa_3_se_lee_del_modelo(self):
        """Una sola definición de las claves y del «ingreso directo»: el modelo. La mesa no las repite."""

        self.assertFalse(hasattr(emergencia_mesa, "SITUACION_EN_LA_PUERTA"))
        directo = CasoEmergencia(origen=CasoEmergencia.Origen.DISPOSITIVO, situacion={})
        aviso = CasoEmergencia(
            origen=CasoEmergencia.Origen.DISPOSITIVO,
            situacion={CasoEmergencia.SITUACION_EN_LA_PUERTA: {"dispositivo_id": 1, "dispositivo": "Club"}},
        )
        de_la_mesa = CasoEmergencia(origen=CasoEmergencia.Origen.MESA, situacion={})
        self.assertTrue(directo.es_ingreso_directo)
        self.assertTrue(servicio.es_ingreso_directo(directo))
        self.assertFalse(aviso.es_ingreso_directo)
        self.assertFalse(de_la_mesa.es_ingreso_directo)
        self.assertEqual(aviso.en_la_puerta["dispositivo"], "Club")
        self.assertIsNone(directo.en_la_puerta)

    def test_la_ficha_de_la_mesa_muestra_los_integrantes_y_el_ingreso_parcial(self):
        caso, derivacion = self._aceptado()
        reservas = self._reservas(derivacion)
        self._confirmar(caso, 2, "45000111", plaza=reservas[0].plaza)
        servicio.cerrar_con_diferencia(
            caso=caso, usuario=self.guardia, motivo="DERIVADO_A_SALUD", observacion="Dos fueron al hospital"
        )
        self.client.force_login(self.operador)

        respuesta = self.client.get(reverse("emergencia:caso_detalle", args=[caso.pk]))

        self.assertContains(respuesta, "Pérez, Juan")
        self.assertContains(respuesta, f"{reservas[0].plaza.codigo} (General)")
        self.assertContains(respuesta, "1 de 7 confirmadas")
        self.assertContains(respuesta, "Ingreso parcial · 1 de 7 personas alojadas · Derivado a salud")
        self.assertContains(respuesta, "Dos fueron al hospital")
        self.assertNotContains(respuesta, "Todavía no hay fichas confirmadas")
        # Solo lectura: la mesa no confirma ni completa fichas.
        self.assertNotContains(respuesta, "/emergencia/llegadas/")

    def test_antes_de_que_el_dispositivo_acepte_la_ficha_sigue_con_el_estado_vacio(self):
        caso, _derivacion = self._derivado()
        self.client.force_login(self.operador)
        respuesta = self.client.get(reverse("emergencia:caso_detalle", args=[caso.pk]))
        self.assertContains(respuesta, "Todavía no hay fichas confirmadas")

    def test_la_ficha_muestra_donde_quedo_la_familia_y_las_personas_agregadas(self):
        caso, derivacion = self._aceptado(menores_f=0, menores_m=0, adultos_m=0)
        self._confirmar(caso, 1, "30111222", parentesco={"parentesco": "JEFE"})
        servicio.agregar_integrante(caso=caso, usuario=self.guardia)
        self._confirmar(caso, 2, "45000111", plaza=self._cama_libre())
        servicio.alojar_familia(
            caso=caso, usuario=self.guardia, aula="Aula 3", tarjeta_entregada=True, tarjeta_numero="7"
        )
        self.client.force_login(self.operador)

        respuesta = self.client.get(reverse("emergencia:caso_detalle", args=[caso.pk]))

        self.assertContains(respuesta, "Llegaron 2 sobre 1 declaradas")
        self.assertContains(respuesta, "Aula 3")
        self.assertContains(respuesta, "Entregada · N.° 7")

    def test_la_bandeja_y_la_ficha_marcan_el_aviso_en_la_puerta_y_el_ingreso_directo(self):
        en_la_puerta = servicio.avisar_a_la_mesa(
            dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._datos(dni="33444555")
        )
        directo = servicio.ingreso_directo(
            dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._datos(dni="33444666")
        )
        self.client.force_login(self.operador)

        bandeja = self.client.get(reverse("emergencia:bandeja"))
        self.assertContains(bandeja, "En la puerta de Club Sarmiento")
        self.assertContains(bandeja, "Ingreso directo")

        ficha = self.client.get(reverse("emergencia:caso_detalle", args=[en_la_puerta.pk]))
        self.assertContains(ficha, "En la puerta de Club Sarmiento")
        self.assertNotContains(ficha, "sin pasar por la mesa")
        ficha = self.client.get(reverse("emergencia:caso_detalle", args=[directo.pk]))
        self.assertContains(ficha, "sin pasar por la mesa")

    def test_la_bandeja_marca_el_ingreso_parcial(self):
        caso, _derivacion = self._aceptado()
        self._confirmar(caso, 2, "45000111")
        servicio.cerrar_con_diferencia(caso=caso, usuario=self.guardia, motivo="NO_LLEGO")
        self.client.force_login(self.operador)

        bandeja = self.client.get(reverse("emergencia:bandeja"), {"estado": "ALOJADO", "solapa": "abiertos"})

        self.assertContains(bandeja, "Ingreso parcial · 1 de 7")


class FotosDelCasoTests(BaseLlegadas):
    """``/media/``: las fotos del caso son de la mesa y de la guardia que recibe a la familia (RU-17)."""

    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        ajuste = override_settings(MEDIA_ROOT=self.media)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.caso = mesa.tomar_caso(
            self._caso(
                dni="30111222",
                menores_f=1,
                fotos={AdjuntoCaso.Tipo.VIVIENDA: SimpleUploadedFile("casa.jpg", JPEG, content_type="image/jpeg")},
            ),
            self.operador,
        )
        self.url = AdjuntoCaso.objects.get(caso=self.caso).archivo.url

    def _pide(self, usuario):
        # Un cliente por usuario para todo el test: el backoffice admite una sola sesión por
        # persona, y entrar de nuevo con otro cliente cierra la anterior.
        clientes = self.__dict__.setdefault("_clientes", {})
        if usuario.pk not in clientes:
            clientes[usuario.pk] = Client()
            clientes[usuario.pk].force_login(usuario)
        return clientes[usuario.pk].get(self.url).status_code

    def test_sin_derivacion_la_guardia_no_ve_las_fotos(self):
        self.assertEqual(self._pide(self.operador), 200)
        self.assertEqual(self._pide(self.guardia), 403)

    def test_la_guardia_del_dispositivo_de_la_derivacion_vigente_las_ve_y_la_de_otro_no(self):
        derivacion = mesa.derivar_caso(self.caso, self.operador, self.club, 3)

        self.assertEqual(self._pide(self.guardia), 200, "derivación pendiente: es quien la va a recibir")
        self.assertEqual(self._pide(self.guardia_escuela), 403)

        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)
        self.assertEqual(self._pide(self.guardia), 200, "ingreso en curso")
        self.assertEqual(self._pide(self.guardia_escuela), 403)
        # La pantalla del ingreso las muestra con esa misma URL.
        lista = self._clientes[self.guardia.pk].get(self._url("integrantes", self.caso.pk))
        self.assertContains(lista, f'src="{self.url}"')

    def test_una_derivacion_que_ya_no_esta_vigente_deja_de_dar_acceso(self):
        derivacion = mesa.derivar_caso(self.caso, self.operador, self.club, 3)
        servicio.rechazar_derivacion(derivacion=derivacion, usuario=self.guardia, motivo="SIN_PLAZAS")

        self.assertEqual(self._pide(self.guardia), 403)

        # Vuelta a derivar a la Escuela: ahora las ve su guardia, y la del Club no.
        mesa.derivar_caso(CasoEmergencia.objects.get(pk=self.caso.pk), self.operador, self.escuela, 3)
        self.assertEqual(self._pide(self.guardia_escuela), 200)
        self.assertEqual(self._pide(self.guardia), 403)

    def test_quien_solo_mira_el_dispositivo_no_las_ve(self):
        """Hace falta `dispositivo.admitir`: es quien recibe a la familia."""

        mesa.derivar_caso(self.caso, self.operador, self.club, 3)
        portero = self._guardia("portero", self.club, capacidades=("dispositivo.ver",))
        self.assertEqual(self._pide(portero), 403)
