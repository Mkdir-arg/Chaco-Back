"""G1c-08 y DAT-03 · El DNI y la procedencia de un legajo.

Los tres escenarios de `poc/test_repro_admin_cron_renaper.py::G1c08AltaRenaperTests`
**invertidos**, más el cabo de DAT-03 que cuelga del tercero.

Lo que la PoC medía y acá ya no pasa:

1. `12.345.678` por la carga manual creaba una **segunda** persona junto a
   `12345678`. Becas normaliza antes de buscar, así que nunca la encontraba: la misma
   persona quedaba partida en dos legajos, uno de ellos invisible para el programa.
2. La confirmación del alta con RENAPER aceptaba un POST con `dni=99999999,
   nombre=Inventado` —la pantalla dice «confirmar» pero el form era editable— y
   guardaba el legajo con `estado_renaper=''`, indistinguible de uno tipeado a mano.
3. La edición cambiaba el DNI de un titular con un caso APROBADO y marcaba
   `estado_renaper=REGISTRADO` a mano, con cualquier `ciudadano.editar`.
4. (DAT-03) Y cuando el DNI cambiaba, `Formulario.dni_titular` se quedaba con el
   viejo: el DNI erróneo seguía ocupando el lugar en la convocatoria y bloqueaba a su
   verdadero titular en el link público.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from core import rbac
from legajos.forms import CiudadanoConfirmarForm, CiudadanoUpdateForm
from legajos.models import Ciudadano
from legajos.services import CiudadanosService
from programas.models import Convocatoria, Formulario, ProgramaSiis, Relevamiento, Segmento
from users.models import Capacidad, RolMeta

DATOS_RENAPER = {
    "dni": "30111222",
    "nombre": "Real",
    "apellido": "Persona",
    "genero": "F",
    "fecha_nacimiento": "1990-01-01",
    "domicilio": "",
    "provincia": None,
}


def _rol(nombre, capacidades):
    grupo = Group.objects.create(name=nombre)
    RolMeta.objects.create(grupo=grupo, categoria=rbac.CATEGORIA_BACKOFFICE, activo=True)
    tipo = ContentType.objects.get_for_model(Capacidad)
    for capacidad in capacidades:
        grupo.permissions.add(Permission.objects.get(content_type=tipo, codename=rbac.codename_de(capacidad)))
    return grupo


class _BaseIdentidadTest(TestCase):
    CAPACIDADES = ("ciudadano.ver", "ciudadano.crear", "ciudadano.editar")

    def setUp(self):
        self.user = User.objects.create_user("gestion_legajos", password="x")
        self.user.groups.add(_rol("Gestión de legajos (test)", self.CAPACIDADES))
        self.client.force_login(self.user)


class DniNormalizadoTests(_BaseIdentidadTest):
    """Escenario 1 de la PoC, invertido."""

    def test_el_dni_con_puntos_no_crea_una_segunda_persona(self):
        Ciudadano.objects.create(dni="12345678", nombre="Ana", apellido="Perez")

        resp = self.client.post(
            reverse("legajos:ciudadano_manual"),
            {"dni": "12.345.678", "nombre": "Ana", "apellido": "Perez"},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Ciudadano.objects.count(), 1)
        self.assertIn("dni", resp.context["form"].errors)

    def test_un_dni_nuevo_con_puntos_se_guarda_en_digitos(self):
        resp = self.client.post(
            reverse("legajos:ciudadano_manual"),
            {"dni": "12.345.678", "nombre": "Ana", "apellido": "Perez"},
        )

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Ciudadano.objects.get().dni, "12345678")

    def test_el_alta_con_renaper_ve_al_gemelo_cargado_con_separadores(self):
        """El `exists()` pelado no encontraba al `87.654.321` ya cargado."""
        Ciudadano.objects.create(dni="87.654.321", nombre="B", apellido="C")

        with patch("legajos.views.ciudadanos.CiudadanosService.consultar_renaper") as consultar:
            consultar.return_value = {"success": True, "data": {"dni": "87654321"}}
            resp = self.client.post(reverse("legajos:ciudadano_nuevo"), {"dni": "87654321", "sexo": "F"})

        self.assertEqual(resp.status_code, 200)
        consultar.assert_not_called()
        self.assertIn("Ya existe un ciudadano con DNI 87654321", [str(m) for m in resp.context["messages"]])

    def test_el_save_del_modelo_normaliza_lo_que_entra_por_el_admin(self):
        """La red para los scripts y el `/admin/`, que no pasan por el form."""
        ciudadano = Ciudadano.objects.create(dni="20.111.222", nombre="X", apellido="Y")

        ciudadano.refresh_from_db()
        self.assertEqual(ciudadano.dni, "20111222")


class ConfirmacionRenaperTests(_BaseIdentidadTest):
    """Escenario 2 de la PoC, invertido."""

    def _consultar(self):
        with patch("legajos.views.ciudadanos.CiudadanosService.consultar_renaper") as consultar:
            consultar.return_value = {"success": True, "data": DATOS_RENAPER, "datos_api": {"apellido": "Persona"}}
            return self.client.post(reverse("legajos:ciudadano_nuevo"), {"dni": "30111222", "sexo": "F"})

    def test_la_confirmacion_no_acepta_datos_alterados_y_deja_la_procedencia(self):
        self.assertEqual(self._consultar().status_code, 302)

        self.client.post(
            reverse("legajos:ciudadano_confirmar"),
            {
                "dni": "99999999",
                "nombre": "Inventado",
                "apellido": "Otro",
                "genero": "M",
                "fecha_nacimiento": "2001-02-03",
            },
        )

        ciudadano = Ciudadano.objects.get()
        self.assertEqual(ciudadano.dni, "30111222")
        self.assertEqual(ciudadano.nombre, "Real")
        self.assertEqual(ciudadano.apellido, "Persona")
        self.assertEqual(ciudadano.fecha_nacimiento, date(1990, 1, 1))
        self.assertEqual(ciudadano.estado_renaper, Ciudadano.EstadoRenaper.REGISTRADO)

    def test_los_cuatro_campos_de_identidad_llegan_bloqueados(self):
        form = CiudadanoConfirmarForm(initial=DATOS_RENAPER)

        for campo in ("dni", "nombre", "apellido", "fecha_nacimiento"):
            with self.subTest(campo=campo):
                self.assertTrue(form.fields[campo].disabled)
        # El domicilio es lo que el operador sí completa.
        self.assertFalse(form.fields["domicilio"].disabled)

    def test_un_campo_que_renaper_no_contesto_queda_editable(self):
        """RED-41 midió respuestas reales con el nombre en `None`: si se bloqueara
        también eso, la pantalla no tendría salida."""
        form = CiudadanoConfirmarForm(initial={**DATOS_RENAPER, "nombre": ""})

        self.assertFalse(form.fields["nombre"].disabled)
        self.assertTrue(form.fields["dni"].disabled)

    def test_tras_un_fallecido_la_carga_manual_guarda_esa_procedencia(self):
        """D-C08, default aplicado."""
        with patch("legajos.views.ciudadanos.CiudadanosService.consultar_renaper") as consultar:
            consultar.return_value = {"success": False, "error": "fallecido", "fallecido": True}
            self.client.post(reverse("legajos:ciudadano_nuevo"), {"dni": "30111222", "sexo": "F"})

        self.client.post(
            reverse("legajos:ciudadano_manual"),
            {"dni": "30111222", "nombre": "Real", "apellido": "Persona"},
        )

        self.assertEqual(Ciudadano.objects.get().estado_renaper, Ciudadano.EstadoRenaper.FALLECIDO)

    def test_la_marca_de_fallecido_no_se_le_pega_al_alta_siguiente(self):
        with patch("legajos.views.ciudadanos.CiudadanosService.consultar_renaper") as consultar:
            consultar.return_value = {"success": False, "error": "fallecido", "fallecido": True}
            self.client.post(reverse("legajos:ciudadano_nuevo"), {"dni": "30111222", "sexo": "F"})

        self.client.post(
            reverse("legajos:ciudadano_manual"),
            {"dni": "30111222", "nombre": "Real", "apellido": "Persona"},
        )
        self.client.post(
            reverse("legajos:ciudadano_manual"),
            {"dni": "30111223", "nombre": "Otra", "apellido": "Persona"},
        )

        self.assertEqual(Ciudadano.objects.get(dni="30111223").estado_renaper, "")


class EdicionDeIdentidadTests(_BaseIdentidadTest):
    """Escenario 3 de la PoC, invertido, y el cabo de DAT-03."""

    def setUp(self):
        super().setUp()
        programa = ProgramaSiis.objects.create(nombre="P", siis_programa_id=79)
        segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=10, programa=programa)
        convocatoria = Convocatoria.objects.create(
            nombre="C", segmento=segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=convocatoria, territorial=self.user, fecha_asignada=date(2026, 6, 1), zona="A"
        )
        self.ciudadano = Ciudadano.objects.create(dni="27888999", nombre="Bene", apellido="Ficiaria")
        self.caso = Formulario.objects.create(
            relevamiento=self.relevamiento, ciudadano=self.ciudadano, estado=Formulario.Estado.APROBADO
        )

    def _editar(self, **datos):
        return self.client.post(
            reverse("legajos:ciudadano_editar", args=[self.ciudadano.pk]),
            {"nombre": "Bene", "apellido": "Ficiaria", **datos},
        )

    def test_con_ciudadano_editar_el_dni_y_la_procedencia_no_se_mueven(self):
        self._editar(dni="11111111", estado_renaper=Ciudadano.EstadoRenaper.REGISTRADO)

        self.ciudadano.refresh_from_db()
        self.assertEqual(self.ciudadano.dni, "27888999")
        self.assertEqual(self.ciudadano.estado_renaper, "")

    def test_quien_administra_la_configuracion_si_puede_corregir_el_dni(self):
        self.user.groups.add(_rol("Config (test)", ("config.administrar",)))

        self._editar(dni="11111111")

        self.ciudadano.refresh_from_db()
        self.assertEqual(self.ciudadano.dni, "11111111")

    def test_la_procedencia_sigue_fuera_de_alcance_para_el_administrador(self):
        """`estado_renaper` no es un dato del legajo: lo pone el alta."""
        self.user.groups.add(_rol("Config renaper (test)", ("config.administrar",)))

        self._editar(dni="27888999", estado_renaper=Ciudadano.EstadoRenaper.REGISTRADO)

        self.ciudadano.refresh_from_db()
        self.assertEqual(self.ciudadano.estado_renaper, "")

    def test_el_form_de_edicion_declara_los_dos_campos_bloqueados(self):
        form = CiudadanoUpdateForm(instance=self.ciudadano)

        self.assertTrue(form.fields["dni"].disabled)
        self.assertTrue(form.fields["estado_renaper"].disabled)
        self.assertFalse(CiudadanoUpdateForm(instance=self.ciudadano, puede_editar_dni=True).fields["dni"].disabled)

    def test_corregir_el_dni_arrastra_el_dni_titular_del_caso(self):
        """DAT-03: si no, el DNI viejo sigue ocupado en la convocatoria."""
        self.assertEqual(self.caso.dni_titular, "27888999")

        self.ciudadano.dni = "11111111"
        self.ciudadano.save()

        self.caso.refresh_from_db()
        self.assertEqual(self.caso.dni_titular, "11111111")

    def test_guardar_sin_tocar_el_dni_no_toca_los_casos(self):
        with self.assertNumQueries(1):
            self.ciudadano.nombre = "Benedicta"
            self.ciudadano.save(update_fields=["nombre"])

        self.caso.refresh_from_db()
        self.assertEqual(self.caso.dni_titular, "27888999")

    def test_un_ciudadano_leido_con_only_no_paga_la_consulta_diferida(self):
        """Con el DNI diferido no hay nada que comparar ni que sincronizar.

        Si el receptor mirara `instance.dni` igual, cada `save()` de una instancia
        cargada con `.only()` sumaría la consulta diferida **y** un `UPDATE` que no
        cambia ninguna fila.
        """
        parcial = Ciudadano.objects.only("pk", "nombre").get(pk=self.ciudadano.pk)
        self.assertIn("dni", parcial.get_deferred_fields())

        with self.assertNumQueries(1):
            parcial.nombre = "Benedicta"
            parcial.save()

        self.caso.refresh_from_db()
        self.assertEqual(self.caso.dni_titular, "27888999")

    def test_si_se_le_asigna_el_dni_a_una_instancia_diferida_igual_sincroniza(self):
        """Asignarlo lo saca de los diferidos: el caso vuelve al camino normal."""
        parcial = Ciudadano.objects.only("pk", "nombre").get(pk=self.ciudadano.pk)

        parcial.dni = "11111111"
        parcial.save()

        self.caso.refresh_from_db()
        self.assertEqual(self.caso.dni_titular, "11111111")

    def test_un_ciudadano_nuevo_no_dispara_la_sincronizacion(self):
        with self.assertNumQueries(1):
            Ciudadano.objects.create(dni="33444555", nombre="Nueva", apellido="Persona")


class DniLegacyEnLaEdicionTests(_BaseIdentidadTest):
    """Una ficha con un DNI que la regla nueva rechaza tiene que seguir editándose.

    La validación del DNI corre **solo si el DNI cambia**: si corriera siempre, un
    legajo con `123456` quedaba inmodificable —el error colgaba de un campo
    `disabled`, no se veía dónde, y no se guardaba nada, ni el teléfono—.
    """

    def setUp(self):
        super().setUp()
        self.ciudadano = Ciudadano.objects.create(dni="30123456", nombre="Legacy", apellido="Persona")
        # Sin pasar por `save()`, que normaliza: es como está cargado en la base.
        Ciudadano.objects.filter(pk=self.ciudadano.pk).update(dni="123456")
        self.ciudadano.refresh_from_db()
        self.url = reverse("legajos:ciudadano_editar", args=[self.ciudadano.pk])

    def _editar(self, **datos):
        return self.client.post(self.url, {"nombre": "Legacy", "apellido": "Persona", **datos})

    def test_se_guarda_el_telefono_sin_tocar_el_dni(self):
        resp = self._editar(telefono="3624000000")

        self.assertEqual(resp.status_code, 302)
        self.ciudadano.refresh_from_db()
        self.assertEqual(self.ciudadano.telefono, "3624000000")
        self.assertEqual(self.ciudadano.dni, "123456")

    def test_la_pantalla_avisa_quien_puede_corregirlo(self):
        resp = self.client.get(self.url)

        avisos = [str(m) for m in resp.context["messages"]]
        self.assertTrue(any("no cumple la regla del sistema" in aviso for aviso in avisos), avisos)
        self.assertTrue(any("quien administra la configuración" in aviso for aviso in avisos), avisos)

    def test_quien_administra_lo_corrige_y_el_aviso_se_lo_dice(self):
        self.user.groups.add(_rol("Config legacy (test)", ("config.administrar",)))

        resp = self.client.get(self.url)
        avisos = [str(m) for m in resp.context["messages"]]
        self.assertTrue(any("Podés corregirlo acá" in aviso for aviso in avisos), avisos)

        self._editar(dni="30123456")

        self.ciudadano.refresh_from_db()
        self.assertEqual(self.ciudadano.dni, "30123456")

    def test_cambiarlo_por_otro_invalido_sigue_sin_poder(self):
        self.user.groups.add(_rol("Config legacy 2 (test)", ("config.administrar",)))

        resp = self._editar(dni="999")

        self.assertEqual(resp.status_code, 200)
        self.assertIn("dni", resp.context["form"].errors)
        self.ciudadano.refresh_from_db()
        self.assertEqual(self.ciudadano.dni, "123456")

    def test_un_alta_con_un_dni_invalido_sigue_rechazada(self):
        """La laxitud es solo para lo que **ya** estaba guardado."""
        resp = self.client.post(
            reverse("legajos:ciudadano_manual"),
            {"dni": "123456", "nombre": "Nueva", "apellido": "Persona"},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertIn("dni", resp.context["form"].errors)


class ExisteConDniTests(TestCase):
    """El chequeo de duplicado que mira las dos formas de escribir el mismo DNI."""

    def test_encuentra_al_gemelo_con_separadores(self):
        Ciudadano.objects.create(dni="12.345.678", nombre="A", apellido="B")

        self.assertTrue(CiudadanosService.existe_con_dni("12345678"))

    def test_no_confunde_un_dni_de_siete_con_el_de_ocho_que_lo_contiene(self):
        """`1234567` está adentro de `12345678`: el cruce es por dígitos, no por texto."""
        Ciudadano.objects.create(dni="12.345.678", nombre="A", apellido="B")

        self.assertFalse(CiudadanosService.existe_con_dni("1234567"))

    def test_sin_dni_no_hay_duplicado(self):
        self.assertFalse(CiudadanosService.existe_con_dni(""))
