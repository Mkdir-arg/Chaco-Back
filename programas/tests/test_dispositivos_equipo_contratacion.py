"""Tipo de contratación del Equipo de Dispositivos y datos de alcance por edificio (PR 1 de 4).

Lo que se fija acá:

1. La contratación es obligatoria **solo** en las altas nuevas (Sumar persona y Crear persona).
2. El servicio la guarda al sumar y al crear; reactivar una fila de baja guarda el valor nuevo.
3. Un miembro anterior sin contratación se ve como «Sin dato» y editarlo no la exige.
4. ``alcance`` NULL no cambia nada: el miembro sigue operando su institución (ninguna regla lee
   ``alcance`` ni ``edificios`` todavía).

La obligatoriedad se verificó por mutación: con ``required=False`` en el campo, los tests de
formulario y de vista quedan rojos.
"""

from django.contrib.auth.models import User
from django.urls import reverse

from programas.forms_equipo_dispositivo import CrearPersonaEquipoForm, SumarMiembroEquipoForm
from programas.models import MiembroEquipoDispositivo
from programas.services import equipo_dispositivo as equipo
from programas.services.dispositivos import puede_operar_dispositivo
from programas.tests.test_dispositivos_equipo_crear_persona_420 import AJAX, BaseCrear


class ContratacionBase(BaseCrear):
    def setUp(self):
        super().setUp()
        self.ana = self._usuario("ana", self.rol_ver, self.rol_admitir)
        self.url_sumar_post = reverse("dispositivos:equipo_sumar", args=[self.disp_a.pk])

    def _datos_sumar(self, **extra):
        datos = {"persona_rol": f"{self.ana.pk}:{self.rol_admitir.pk}", "tipo_contratacion": "BECADO"}
        datos.update(extra)
        return datos


class FormulariosTests(ContratacionBase):
    def test_sumar_sin_contratacion_es_invalido(self):
        datos = self._datos_sumar()
        del datos["tipo_contratacion"]
        form = SumarMiembroEquipoForm(datos, dispositivo=self.disp_a)

        self.assertFalse(form.is_valid())
        self.assertIn("tipo_contratacion", form.errors)

    def test_sumar_con_contratacion_es_valido(self):
        form = SumarMiembroEquipoForm(self._datos_sumar(), dispositivo=self.disp_a)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["tipo_contratacion"], "BECADO")

    def test_un_valor_fuera_de_la_lista_se_rechaza(self):
        form = SumarMiembroEquipoForm(self._datos_sumar(tipo_contratacion="OTRO"), dispositivo=self.disp_a)

        self.assertFalse(form.is_valid())
        self.assertIn("tipo_contratacion", form.errors)

    def test_crear_persona_exige_la_contratacion(self):
        datos = self._datos()
        del datos["tipo_contratacion"]
        form = CrearPersonaEquipoForm(datos, roles=equipo.roles_para_crear_persona(self.admin_programa))

        self.assertFalse(form.is_valid())
        self.assertIn("tipo_contratacion", form.errors)

    def test_crear_persona_con_contratacion_es_valido(self):
        form = CrearPersonaEquipoForm(self._datos(), roles=equipo.roles_para_crear_persona(self.admin_programa))

        self.assertTrue(form.is_valid(), form.errors)

    def test_el_desplegable_ofrece_las_cuatro_opciones_y_una_vacia(self):
        form = SumarMiembroEquipoForm(dispositivo=self.disp_a)
        etiquetas = [etiqueta for _, etiqueta in form.fields["tipo_contratacion"].choices]

        self.assertEqual(
            etiquetas,
            [
                "Elegí el tipo de contratación",
                "Becado",
                "Contrato de locación",
                "Contrato de servicio",
                "Planta permanente",
            ],
        )


class VistasTests(ContratacionBase):
    def test_la_vista_de_sumar_rechaza_sin_contratacion_y_no_suma(self):
        self._entrar(self.admin_programa)
        datos = self._datos_sumar()
        del datos["tipo_contratacion"]

        respuesta = self.client.post(self.url_sumar_post, datos, headers=AJAX)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("tipo_contratacion", respuesta.json()["errors"])
        self.assertFalse(MiembroEquipoDispositivo.objects.filter(usuario=self.ana).exists())

    def test_la_vista_de_sumar_guarda_la_contratacion(self):
        self._entrar(self.admin_programa)

        respuesta = self.client.post(self.url_sumar_post, self._datos_sumar(tipo_contratacion="LOCACION"), headers=AJAX)

        self.assertEqual(respuesta.status_code, 200)
        miembro = MiembroEquipoDispositivo.objects.get(usuario=self.ana, dispositivo=self.disp_a)
        self.assertEqual(miembro.tipo_contratacion, "LOCACION")

    def test_la_vista_de_crear_persona_guarda_la_contratacion(self):
        respuesta = self._crear(tipo_contratacion="PLANTA_PERMANENTE")

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        usuario = User.objects.get(email="lucia@example.com")
        miembro = MiembroEquipoDispositivo.objects.get(usuario=usuario, dispositivo=self.disp_a)
        self.assertEqual(miembro.tipo_contratacion, "PLANTA_PERMANENTE")

    def test_la_vista_de_crear_persona_rechaza_sin_contratacion(self):
        self._entrar(self.admin_programa)
        datos = self._datos()
        del datos["tipo_contratacion"]

        respuesta = self.client.post(self.url_crear, datos, headers=AJAX)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("tipo_contratacion", respuesta.json()["errors"])
        self._sin_alta()

    def test_los_modales_muestran_el_desplegable(self):
        self._entrar(self.admin_programa)

        respuesta = self.client.get(self.url_sumar)

        self.assertContains(respuesta, 'name="tipo_contratacion"', count=2)
        self.assertContains(respuesta, "Elegí el tipo de contratación", count=2)


class ServicioTests(ContratacionBase):
    def test_sumar_miembro_guarda_el_valor(self):
        miembro = equipo.sumar_miembro(
            actor=self.admin_programa,
            dispositivo=self.disp_a,
            usuario=self.ana,
            rol=self.rol_admitir,
            tipo_contratacion="SERVICIO",
        )

        miembro.refresh_from_db()
        self.assertEqual(miembro.tipo_contratacion, "SERVICIO")

    def test_sumar_miembro_sin_valor_queda_sin_dato(self):
        miembro = equipo.sumar_miembro(
            actor=self.admin_programa, dispositivo=self.disp_a, usuario=self.ana, rol=self.rol_admitir
        )

        self.assertIsNone(miembro.tipo_contratacion)

    def test_reactivar_actualiza_el_valor(self):
        kwargs = {
            "actor": self.admin_programa,
            "dispositivo": self.disp_a,
            "usuario": self.ana,
            "rol": self.rol_admitir,
        }
        miembro = equipo.sumar_miembro(**kwargs, tipo_contratacion="BECADO")
        MiembroEquipoDispositivo.objects.filter(pk=miembro.pk).update(activo=False)

        reactivado = equipo.sumar_miembro(**kwargs, tipo_contratacion="PLANTA_PERMANENTE")

        reactivado.refresh_from_db()
        self.assertEqual(reactivado.pk, miembro.pk)
        self.assertTrue(reactivado.activo)
        self.assertEqual(reactivado.tipo_contratacion, "PLANTA_PERMANENTE")

    def test_crear_persona_y_sumar_guarda_el_valor(self):
        alta = equipo.datos_de_alta_de_persona(
            actor=self.admin_programa,
            dni="28555111",
            nombre="Lucía",
            apellido="Ferreyra",
            correo="lucia@example.com",
            rol=self.rol_admitir,
        )
        self.assertTrue(alta.is_valid(), alta.errors)

        usuario = equipo.crear_persona_y_sumar(
            actor=self.admin_programa,
            dispositivo=self.disp_a,
            alta=alta,
            rol=self.rol_admitir,
            tipo_contratacion="LOCACION",
        )

        miembro = MiembroEquipoDispositivo.objects.get(usuario=usuario, dispositivo=self.disp_a)
        self.assertEqual(miembro.tipo_contratacion, "LOCACION")


class MiembroExistenteTests(ContratacionBase):
    def setUp(self):
        super().setUp()
        self.viejo = self._miembro(self.disp_a, self.ana, self.rol_admitir)

    def test_se_ve_como_sin_dato(self):
        self._entrar(self.admin_programa)

        respuesta = self.client.get(self.url_detalle + "?tab=equipo")

        self.assertContains(respuesta, "Contratación")
        self.assertContains(respuesta, "Sin dato")

    def test_con_valor_se_ve_la_etiqueta(self):
        MiembroEquipoDispositivo.objects.filter(pk=self.viejo.pk).update(tipo_contratacion="LOCACION")
        self._entrar(self.admin_programa)

        respuesta = self.client.get(self.url_detalle + "?tab=equipo")

        self.assertContains(respuesta, "Contrato de locación")

    def test_editarlo_no_exige_contratacion(self):
        self._entrar(self.admin_programa)

        respuesta = self.client.post(
            reverse("dispositivos:equipo_responsable", args=[self.disp_a.pk, self.viejo.pk]), headers=AJAX
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.viejo.refresh_from_db()
        self.assertTrue(self.viejo.es_responsable)
        self.assertIsNone(self.viejo.tipo_contratacion)


class AlcanceNuloTests(ContratacionBase):
    def test_alcance_nulo_sigue_operando_su_institucion(self):
        self._miembro(self.disp_a, self.ana, self.rol_admitir)
        usuario = self._fresco(self.ana)

        miembro = MiembroEquipoDispositivo.objects.get(usuario=self.ana)
        self.assertIsNone(miembro.alcance)
        self.assertFalse(miembro.edificios.exists())
        self.assertTrue(puede_operar_dispositivo(usuario, self.disp_a, "dispositivo.admitir"))
        self.assertFalse(puede_operar_dispositivo(usuario, self.disp_b, "dispositivo.admitir"))
