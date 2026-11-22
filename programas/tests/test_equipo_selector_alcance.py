"""Selector de alcance del Equipo en el backoffice (Cambio 523, PR 4 de 4; la app queda pendiente).

Todo por la vista, con POST reales:

1. Sumar, crear y editar con alcance «Toda la institución» o «Edificios» (RN2: al menos uno, vinculado).
2. RN6: un responsable con alcance Edificios solo ofrece y acepta sus edificios y solo alcance «Edificios».
3. La tabla del Equipo muestra el alcance sin una consulta por fila.
4. «Agregar persona al edificio» (menú de cada edificio): edificio fijo, suma el edificio a quien ya está con
   Edificios, no toca a quien ya tiene toda la institución, y no se ofrece donde el servidor no lo acepta.
"""

from django.contrib.auth.models import User
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from programas.models import Dispositivo, Edificio, MiembroEquipoDispositivo
from programas.tests.test_dispositivos_equipo_crear_persona_420 import AJAX, DNI_NUEVO, BaseCrear

Alcance = MiembroEquipoDispositivo.Alcance


class BaseSelector(BaseCrear):
    def setUp(self):
        super().setUp()
        self.ed1 = self._edificio("ED-1", self.disp_a)
        self.ed2 = self._edificio("ED-2", self.disp_a)
        self.ed_ajeno = self._edificio("ED-X", self.disp_b)
        self.ana = self._usuario("ana", self.rol_ver, self.rol_admitir)
        User.objects.filter(pk=self.ana.pk).update(first_name="Ana", last_name="Gomez")
        self.url_sumar_post = reverse("dispositivos:equipo_sumar", args=[self.disp_a.pk])
        # Responsable de Edificios {ED-1}: arma el Equipo solo ahí (RN6).
        self.resp_ed = self._usuario("resp_ed", self.rol_ver)
        fila = self._miembro(self.disp_a, self.resp_ed, self.rol_ver, responsable=True)
        fila.alcance = Alcance.EDIFICIOS
        fila.save(update_fields=["alcance"])
        fila.edificios.set([self.ed1])

    def _edificio(self, codigo, dispositivo):
        edificio = Edificio.objects.create(codigo=codigo, nombre=f"Edificio {codigo}")
        edificio.dispositivos.add(dispositivo)
        return edificio

    def _sumar(self, usuario=None, **extra):
        self._entrar(usuario or self.admin_programa)
        datos = {"persona_rol": f"{self.ana.pk}:{self.rol_admitir.pk}", "tipo_contratacion": "BECADO", **extra}
        return self.client.post(self.url_sumar_post, datos, headers=AJAX)

    def _fila_de_ana(self):
        return MiembroEquipoDispositivo.objects.get(usuario=self.ana, dispositivo=self.disp_a)

    def _ids(self, miembro):
        return set(miembro.edificios.values_list("pk", flat=True))


class SumarConAlcanceTests(BaseSelector):
    def test_sin_alcance_en_el_post_es_toda_la_institucion(self):
        self.assertEqual(self._sumar().status_code, 200)
        self.assertIn(self._fila_de_ana().alcance, (None, Alcance.INSTITUCION))

    def test_institucion_no_guarda_edificios(self):
        self.assertEqual(self._sumar(alcance="INSTITUCION", edificios=[self.ed1.pk]).status_code, 200)
        fila = self._fila_de_ana()
        self.assertEqual(fila.alcance, Alcance.INSTITUCION)
        self.assertEqual(self._ids(fila), set())

    def test_edificios_guarda_los_elegidos(self):
        self.assertEqual(self._sumar(alcance="EDIFICIOS", edificios=[self.ed1.pk, self.ed2.pk]).status_code, 200)
        fila = self._fila_de_ana()
        self.assertEqual(fila.alcance, Alcance.EDIFICIOS)
        self.assertEqual(self._ids(fila), {self.ed1.pk, self.ed2.pk})

    def test_edificios_sin_ninguno_es_un_error_en_el_campo_y_no_suma(self):
        respuesta = self._sumar(alcance="EDIFICIOS")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("edificios", respuesta.json()["errors"])
        self.assertFalse(MiembroEquipoDispositivo.objects.filter(usuario=self.ana).exists())

    def test_un_edificio_de_otra_institucion_se_rechaza_en_el_campo(self):
        respuesta = self._sumar(alcance="EDIFICIOS", edificios=[self.ed1.pk, self.ed_ajeno.pk])
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("edificios", respuesta.json()["errors"])
        self.assertFalse(MiembroEquipoDispositivo.objects.filter(usuario=self.ana).exists())

    def test_un_id_que_no_es_numero_no_rompe(self):
        respuesta = self._sumar(alcance="EDIFICIOS", edificios=["abc"])
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("edificios", respuesta.json()["errors"])


class CrearConAlcanceTests(BaseSelector):
    def test_crear_con_edificios(self):
        respuesta = self._crear(alcance="EDIFICIOS", edificios=[self.ed2.pk])
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        fila = MiembroEquipoDispositivo.objects.get(usuario=User.objects.get(email="lucia@example.com"))
        self.assertEqual(fila.alcance, Alcance.EDIFICIOS)
        self.assertEqual(self._ids(fila), {self.ed2.pk})

    def test_crear_con_institucion(self):
        respuesta = self._crear(alcance="INSTITUCION")
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        fila = MiembroEquipoDispositivo.objects.get(usuario=User.objects.get(email="lucia@example.com"))
        self.assertEqual(fila.alcance, Alcance.INSTITUCION)

    def test_crear_con_edificios_sin_edificios_no_deja_ni_el_usuario(self):
        respuesta = self._crear(alcance="EDIFICIOS")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("edificios", respuesta.json()["errors"])
        self._sin_alta()

    def test_crear_con_edificio_ajeno_no_deja_ni_el_usuario(self):
        respuesta = self._crear(alcance="EDIFICIOS", edificios=[self.ed_ajeno.pk])
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("edificios", respuesta.json()["errors"])
        self._sin_alta()


class EditarAlcanceTests(BaseSelector):
    def setUp(self):
        super().setUp()
        self._sumar(alcance="INSTITUCION")
        self.fila = self._fila_de_ana()
        self.url = reverse("dispositivos:equipo_alcance", args=[self.disp_a.pk, self.fila.pk])

    def _editar(self, usuario=None, **datos):
        self._entrar(usuario or self.admin_programa)
        return self.client.post(self.url, datos, headers=AJAX)

    def test_de_institucion_a_edificios_y_de_vuelta(self):
        self.assertEqual(self._editar(alcance="EDIFICIOS", edificios=[self.ed1.pk]).status_code, 200)
        fila = self._fila_de_ana()
        self.assertEqual((fila.alcance, self._ids(fila)), (Alcance.EDIFICIOS, {self.ed1.pk}))
        self.assertEqual(self._editar(alcance="INSTITUCION").status_code, 200)
        fila = self._fila_de_ana()
        self.assertEqual((fila.alcance, self._ids(fila)), (Alcance.INSTITUCION, set()))

    def test_edificios_sin_ninguno_es_error_del_campo_y_no_cambia_nada(self):
        respuesta = self._editar(alcance="EDIFICIOS")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("edificios", respuesta.json()["errors"])
        self.assertEqual(self._fila_de_ana().alcance, Alcance.INSTITUCION)

    def test_edificio_ajeno_se_rechaza(self):
        respuesta = self._editar(alcance="EDIFICIOS", edificios=[self.ed_ajeno.pk])
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("edificios", respuesta.json()["errors"])

    def test_el_modal_abre_con_lo_que_tiene_hoy(self):
        self._editar(alcance="EDIFICIOS", edificios=[self.ed2.pk])
        self._entrar(self.admin_programa)
        respuesta = self.client.get(f"{self.url_detalle}?tab=equipo&equipo=alcance&miembro={self.fila.pk}")
        form = respuesta.context["form_alcance"]
        self.assertEqual(form.initial["alcance"], Alcance.EDIFICIOS)
        self.assertEqual(form.initial["edificios"], [str(self.ed2.pk)])
        self.assertContains(respuesta, "modal-alcance-titulo")

    def test_una_persona_de_baja_no_se_edita(self):
        MiembroEquipoDispositivo.objects.filter(pk=self.fila.pk).update(activo=False)
        respuesta = self._editar(alcance="EDIFICIOS", edificios=[self.ed1.pk])
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(self._fila_de_ana().alcance, Alcance.INSTITUCION)


class ResponsableConAlcanceEdificiosTests(BaseSelector):
    """RN6: la UI no ofrece lo que el servidor rechaza, y el servidor lo rechaza igual."""

    def test_el_modal_ofrece_solo_sus_edificios_y_solo_alcance_edificios(self):
        self._entrar(self.resp_ed)
        respuesta = self.client.get(self.url_sumar)
        form = respuesta.context["form_equipo"]
        self.assertEqual([pk for pk, _ in form.fields["edificios"].choices], [str(self.ed1.pk)])
        self.assertEqual([valor for valor, _ in form.fields["alcance"].widget.choices], ["EDIFICIOS"])
        self.assertNotContains(respuesta, "Edificio ED-2")

    def test_no_puede_dar_alcance_institucion(self):
        self.assertEqual(self._sumar(self.resp_ed, alcance="INSTITUCION").status_code, 403)
        self.assertEqual(self._sumar(self.resp_ed).status_code, 403)
        self.assertFalse(MiembroEquipoDispositivo.objects.filter(usuario=self.ana).exists())

    def test_no_puede_dar_edificios_ajenos(self):
        self.assertEqual(self._sumar(self.resp_ed, alcance="EDIFICIOS", edificios=[self.ed2.pk]).status_code, 403)
        self.assertEqual(
            self._sumar(self.resp_ed, alcance="EDIFICIOS", edificios=[self.ed1.pk, self.ed2.pk]).status_code, 403
        )
        self.assertFalse(MiembroEquipoDispositivo.objects.filter(usuario=self.ana).exists())

    def test_puede_dar_los_suyos(self):
        self.assertEqual(self._sumar(self.resp_ed, alcance="EDIFICIOS", edificios=[self.ed1.pk]).status_code, 200)
        self.assertEqual(self._ids(self._fila_de_ana()), {self.ed1.pk})

    def test_no_puede_cambiar_el_alcance_de_alguien_de_toda_la_institucion(self):
        self._sumar(alcance="INSTITUCION")
        fila = self._fila_de_ana()
        url = reverse("dispositivos:equipo_alcance", args=[self.disp_a.pk, fila.pk])
        self._entrar(self.resp_ed)
        respuesta = self.client.post(url, {"alcance": "EDIFICIOS", "edificios": [self.ed1.pk]}, headers=AJAX)
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self._fila_de_ana().alcance, Alcance.INSTITUCION)
        # Y la tabla no le ofrece la acción.
        pantalla = self.client.get(self.url_detalle + "?tab=equipo")
        por_pk = {m.pk: m for m in pantalla.context["equipo"]}
        self.assertFalse(por_pk[fila.pk].puede_cambiar_alcance)

    def test_puede_cambiar_el_alcance_de_los_suyos_pero_no_a_edificios_ajenos(self):
        self._sumar(alcance="EDIFICIOS", edificios=[self.ed1.pk])
        fila = self._fila_de_ana()
        url = reverse("dispositivos:equipo_alcance", args=[self.disp_a.pk, fila.pk])
        self._entrar(self.resp_ed)
        self.assertEqual(
            self.client.post(url, {"alcance": "EDIFICIOS", "edificios": [self.ed2.pk]}, headers=AJAX).status_code, 403
        )
        self.assertEqual(self._ids(self._fila_de_ana()), {self.ed1.pk})


class TablaDelEquipoTests(BaseSelector):
    def test_la_tabla_muestra_el_alcance_de_cada_persona(self):
        self._sumar(alcance="EDIFICIOS", edificios=[self.ed2.pk, self.ed1.pk])
        self._entrar(self.admin_programa)
        respuesta = self.client.get(self.url_detalle + "?tab=equipo")
        por_persona = {m.usuario.username: m.alcance_texto for m in respuesta.context["equipo"]}
        self.assertEqual(por_persona["ana"], "Edificio ED-1, Edificio ED-2")
        self.assertEqual(por_persona["responsable"], "Toda la institución")
        self.assertContains(respuesta, "Edificio ED-1, Edificio ED-2")

    def test_un_edificio_desvinculado_no_figura_en_el_alcance(self):
        self._sumar(alcance="EDIFICIOS", edificios=[self.ed1.pk, self.ed2.pk])
        # Un edificio huérfano en la tabla intermedia: la tabla muestra solo los vinculados.
        self.ed2.dispositivos.remove(self.disp_a)
        self._entrar(self.admin_programa)
        por_persona = {m.usuario.username: m.alcance_texto for m in self.client.get(self.url_detalle).context["equipo"]}
        self.assertEqual(por_persona["ana"], "Edificio ED-1")

    def test_las_consultas_de_la_tabla_no_crecen_con_los_miembros(self):
        self._sumar(alcance="EDIFICIOS", edificios=[self.ed1.pk])
        self._entrar(self.admin_programa)

        def consultas():
            with CaptureQueriesContext(connection) as captura:
                self.assertEqual(self.client.get(self.url_detalle + "?tab=equipo").status_code, 200)
            return len(captura)

        consultas()  # la primera lectura llena cachés de contenido y permisos
        antes = consultas()
        for n in range(8):
            usuario = self._usuario(f"extra{n}", self.rol_ver)
            fila = self._miembro(self.disp_a, usuario, self.rol_ver)
            fila.alcance = Alcance.EDIFICIOS
            fila.save(update_fields=["alcance"])
            fila.edificios.set([self.ed1, self.ed2])
        self.assertEqual(consultas(), antes)


#: Consultas del detalle visto por un responsable con alcance Edificios, con la caché ya caliente. Si suben, algo
#: del Equipo volvió a leer los permisos más de una vez por request.
CONSULTAS_DETALLE_RESPONSABLE = 33
CONSULTAS_DETALLE_RESPONSABLE_AGREGAR_PERSONA = 34


@tag("performance")
class PresupuestoDelDetalleDelResponsableTests(BaseSelector):
    def _consultas(self, url):
        self.client.get(url)  # la primera lectura llena cachés de contenido y permisos
        with CaptureQueriesContext(connection) as captura:
            self.assertEqual(self.client.get(url).status_code, 200)
        return len(captura)

    def test_el_detalle_comun_cuesta_lo_fijado(self):
        self._entrar(self.resp_ed)
        self.assertEqual(self._consultas(self.url_detalle), CONSULTAS_DETALLE_RESPONSABLE)

    def test_el_detalle_con_agregar_persona_cuesta_lo_fijado(self):
        self._entrar(self.resp_ed)
        url = f"{self.url_detalle}?tab=infraestructura&agregar_persona={self.ed1.pk}"
        self.assertEqual(self._consultas(url), CONSULTAS_DETALLE_RESPONSABLE_AGREGAR_PERSONA)


class AgregarPersonaAlEdificioTests(BaseSelector):
    def setUp(self):
        super().setUp()
        self.url_agregar = f"{self.url_detalle}?tab=infraestructura&agregar_persona={self.ed1.pk}"

    def _agregar(self, usuario=None, edificio=None, **extra):
        self._entrar(usuario or self.admin_programa)
        datos = {
            "persona_rol": f"{self.ana.pk}:{self.rol_admitir.pk}",
            "tipo_contratacion": "BECADO",
            "edificio_fijo": (edificio or self.ed1).pk,
            **extra,
        }
        return self.client.post(self.url_sumar_post, datos, headers=AJAX)

    def test_el_menu_de_cada_edificio_ofrece_la_accion_al_admin(self):
        self._entrar(self.admin_programa)
        respuesta = self.client.get(self.url_detalle + "?tab=infraestructura")
        self.assertContains(respuesta, "Agregar persona al edificio")
        self.assertContains(respuesta, f"agregar_persona={self.ed1.pk}")
        self.assertContains(respuesta, f"agregar_persona={self.ed2.pk}")

    def test_el_responsable_de_edificios_la_ve_solo_en_los_suyos(self):
        self._entrar(self.resp_ed)
        respuesta = self.client.get(self.url_detalle + "?tab=infraestructura")
        self.assertContains(respuesta, f"agregar_persona={self.ed1.pk}")
        self.assertNotContains(respuesta, f"agregar_persona={self.ed2.pk}")

    def test_quien_no_arma_el_equipo_no_la_ve(self):
        rol = self._rol("Solo ve", ("dispositivo.ver",))
        usuario = self._usuario("solo_ve", rol)
        self._miembro(self.disp_a, usuario, rol)
        self._entrar(usuario)
        self.assertNotContains(self.client.get(self.url_detalle + "?tab=infraestructura"), "agregar_persona=")

    def test_un_dispositivo_cerrado_no_la_ofrece_ni_la_acepta(self):
        Dispositivo.objects.filter(pk=self.disp_a.pk).update(estado=Dispositivo.Estado.CERRADO)
        self._entrar(self.admin_programa)
        self.assertNotContains(self.client.get(self.url_detalle + "?tab=infraestructura"), "agregar_persona=")
        self.assertNotIn("form_equipo", self.client.get(self.url_agregar).context)
        self.assertEqual(self._agregar().status_code, 400)
        self.assertFalse(MiembroEquipoDispositivo.objects.filter(usuario=self.ana).exists())

    def test_el_modal_fija_el_edificio_y_no_pregunta_el_alcance(self):
        self._entrar(self.admin_programa)
        respuesta = self.client.get(self.url_agregar)
        self.assertContains(respuesta, "Agregar persona al edificio")
        self.assertContains(respuesta, "Edificio ED-1")
        form = respuesta.context["form_equipo"]
        self.assertNotIn("alcance", form.fields)
        self.assertEqual(form.initial["edificio_fijo"], self.ed1.pk)

    def test_un_edificio_ajeno_o_sin_permiso_no_abre_el_modal(self):
        self._entrar(self.admin_programa)
        self.assertNotIn(
            "form_equipo", self.client.get(f"{self.url_detalle}?agregar_persona={self.ed_ajeno.pk}").context
        )
        self._entrar(self.resp_ed)
        self.assertNotIn("form_equipo", self.client.get(f"{self.url_detalle}?agregar_persona={self.ed2.pk}").context)

    def test_suma_a_la_persona_con_alcance_edificios_en_ese_edificio(self):
        self.assertEqual(self._agregar().status_code, 200)
        fila = self._fila_de_ana()
        self.assertEqual((fila.alcance, self._ids(fila)), (Alcance.EDIFICIOS, {self.ed1.pk}))

    def test_si_ya_estaba_con_edificios_le_suma_el_edificio(self):
        self._agregar()
        self.assertEqual(self._agregar(edificio=self.ed2).status_code, 200)
        self.assertEqual(self._ids(self._fila_de_ana()), {self.ed1.pk, self.ed2.pk})

    def test_si_ya_tiene_toda_la_institucion_no_cambia_nada_y_avisa(self):
        self._sumar(alcance="INSTITUCION")
        respuesta = self._agregar()
        self.assertEqual(respuesta.status_code, 200)
        fila = self._fila_de_ana()
        self.assertEqual((fila.alcance, self._ids(fila)), (Alcance.INSTITUCION, set()))
        mensajes = (
            [str(m) for m in respuesta.wsgi_request._messages] if hasattr(respuesta.wsgi_request, "_messages") else []
        )
        self.assertTrue(any("ya tiene alcance" in m for m in mensajes), mensajes)

    def test_el_buscador_ofrece_a_quien_ya_esta_en_el_equipo_solo_con_incluir(self):
        self._sumar(alcance="INSTITUCION")
        self._entrar(self.admin_programa)
        url = reverse("dispositivos:equipo_personas_buscar", args=[self.disp_a.pk])
        # Ya está con «Admite»; sin `incluir` queda solo el otro rol, con `incluir` los dos.
        self.assertEqual(len(self.client.get(url, {"q": "gomez"}).json()["resultados"]), 1)
        self.assertEqual(len(self.client.get(url, {"q": "gomez", "incluir": "1"}).json()["resultados"]), 2)

    def test_el_responsable_de_edificios_no_agrega_en_edificios_ajenos(self):
        self.assertEqual(self._agregar(self.resp_ed, edificio=self.ed2).status_code, 403)
        self.assertFalse(MiembroEquipoDispositivo.objects.filter(usuario=self.ana).exists())
        self.assertEqual(self._agregar(self.resp_ed, edificio=self.ed1).status_code, 200)

    def test_el_responsable_no_le_suma_un_edificio_ajeno_a_quien_ya_esta_en_los_suyos(self):
        self._agregar(self.resp_ed, edificio=self.ed1)
        self.assertEqual(self._agregar(self.resp_ed, edificio=self.ed2).status_code, 403)
        self.assertEqual(self._ids(self._fila_de_ana()), {self.ed1.pk})

    def test_el_responsable_no_toca_la_fila_de_quien_el_admin_dejo_en_otro_edificio(self):
        # La persona ya está con Edificios {ED-2}: agregarla en ED-1 (que sí es del responsable) la movería de ED-2.
        self._sumar(alcance="EDIFICIOS", edificios=[self.ed2.pk])
        self.assertEqual(self._agregar(self.resp_ed, edificio=self.ed1).status_code, 403)
        self.assertEqual(self._ids(self._fila_de_ana()), {self.ed2.pk})

    def test_un_edificio_de_otra_institucion_se_rechaza(self):
        respuesta = self._agregar(edificio=self.ed_ajeno)
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(MiembroEquipoDispositivo.objects.filter(usuario=self.ana).exists())

    def test_crear_persona_en_el_edificio(self):
        self._entrar(self.admin_programa)
        respuesta = self.client.post(self.url_crear, self._datos(edificio_fijo=self.ed1.pk), headers=AJAX)
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        fila = MiembroEquipoDispositivo.objects.get(usuario=User.objects.get(email="lucia@example.com"))
        self.assertEqual((fila.alcance, self._ids(fila)), (Alcance.EDIFICIOS, {self.ed1.pk}))

    def test_crear_persona_en_un_edificio_ajeno_no_deja_ni_el_usuario(self):
        self._entrar(self.resp_ed)
        self.assertEqual(DNI_NUEVO, self._datos()["dni"])
        # El responsable de Edificios no administra usuarios: 403 antes de mirar nada. Con el admin, el edificio ajeno rechaza.
        self._entrar(self.admin_programa)
        respuesta = self.client.post(self.url_crear, self._datos(edificio_fijo=self.ed_ajeno.pk), headers=AJAX)
        self.assertEqual(respuesta.status_code, 400)
        self._sin_alta()
