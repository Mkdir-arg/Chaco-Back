from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from legajos.models import Ciudadano
from programas.forms import F00DinamicoForm
from programas.models import (
    Admision,
    ArchivoAdmision,
    Cama,
    CampoTipoDispositivo,
    Dispositivo,
    EsperaAdmision,
    Programa,
    TipoCampo,
    TipoDispositivo,
)
from programas.services.admisiones import (
    admitir_ciudadano,
    egresar_admision,
    poner_en_espera,
    promover_espera,
    trasladar_admision,
)


class AdmisionesServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(username="operador")
        cls.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        tipo = TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor", maneja_camas=True)
        cls.dispositivo = Dispositivo.objects.create(
            codigo="HOGAR-01", nombre="Hogar Norte", tipo=tipo, estado=Dispositivo.Estado.ACTIVO
        )
        cls.cama = Cama.objects.create(dispositivo=cls.dispositivo, codigo="C-01")
        cls.ciudadano = Ciudadano.objects.create(dni="30000001", nombre="Ana", apellido="Prueba")

    def test_admitir_ocupa_cama_y_activa_membresia(self):
        admision = admitir_ciudadano(
            ciudadano=self.ciudadano, dispositivo=self.dispositivo, cama=self.cama, usuario=self.usuario
        )

        self.cama.refresh_from_db()
        self.assertEqual(admision.estado, admision.Estado.ALOJADO)
        self.assertEqual(self.cama.estado, Cama.Estado.OCUPADA)
        self.assertEqual(admision.inscripcion_programa.estado, "ACTIVO")

    def test_egreso_libera_cama_y_cierra_membresia_sin_otra_estadia_activa(self):
        admision = admitir_ciudadano(
            ciudadano=self.ciudadano, dispositivo=self.dispositivo, cama=self.cama, usuario=self.usuario
        )

        egresar_admision(
            admision=admision,
            usuario=self.usuario,
            fecha_egreso=timezone.now(),
            motivo="Alta",
            destino="Domicilio",
        )

        self.cama.refresh_from_db()
        admision.refresh_from_db()
        self.assertEqual(admision.estado, admision.Estado.EGRESADO)
        self.assertEqual(self.cama.estado, Cama.Estado.DISPONIBLE)
        self.assertEqual(admision.inscripcion_programa.estado, "CERRADO")

    def test_no_admite_sobre_cama_no_disponible(self):
        self.cama.estado = Cama.Estado.FUERA_SERVICIO
        self.cama.save(update_fields=["estado", "modificado"])

        with self.assertRaisesMessage(ValidationError, "disponible"):
            admitir_ciudadano(
                ciudadano=self.ciudadano, dispositivo=self.dispositivo, cama=self.cama, usuario=self.usuario
            )

    def test_traslado_sin_cama_conserva_origen_y_promocion_manual_lo_cierra(self):
        origen = admitir_ciudadano(
            ciudadano=self.ciudadano, dispositivo=self.dispositivo, cama=self.cama, usuario=self.usuario
        )
        destino = Dispositivo.objects.create(
            codigo="HOGAR-02", nombre="Hogar Sur", tipo=self.dispositivo.tipo, estado=Dispositivo.Estado.ACTIVO
        )

        espera = trasladar_admision(admision=origen, destino=destino, cama=None, usuario=self.usuario)

        origen.refresh_from_db()
        self.cama.refresh_from_db()
        self.assertEqual(espera.estado, Admision.Estado.LISTA_ESPERA)
        self.assertEqual(espera.origen_traslado_id, origen.pk)
        self.assertEqual(origen.estado, Admision.Estado.ALOJADO)
        self.assertEqual(self.cama.estado, Cama.Estado.OCUPADA)

        cama_destino = Cama.objects.create(dispositivo=destino, codigo="C-01")
        promover_espera(espera=EsperaAdmision.objects.get(admision=espera), cama=cama_destino, usuario=self.usuario)

        origen.refresh_from_db()
        self.cama.refresh_from_db()
        cama_destino.refresh_from_db()
        self.assertEqual(origen.estado, Admision.Estado.TRASLADADO)
        self.assertEqual(self.cama.estado, Cama.Estado.DISPONIBLE)
        self.assertEqual(cama_destino.estado, Cama.Estado.OCUPADA)

    def test_espera_no_se_promueve_automaticamente_al_egresar(self):
        alojada = admitir_ciudadano(
            ciudadano=self.ciudadano, dispositivo=self.dispositivo, cama=self.cama, usuario=self.usuario
        )
        otra = Ciudadano.objects.create(dni="30000002", nombre="Beto", apellido="Prueba")
        espera = poner_en_espera(ciudadano=otra, dispositivo=self.dispositivo, usuario=self.usuario)

        egresar_admision(
            admision=alojada, usuario=self.usuario, fecha_egreso=timezone.now(), motivo="Alta", destino="Domicilio"
        )

        espera.refresh_from_db()
        self.assertEqual(espera.estado, Admision.Estado.LISTA_ESPERA)


class F00DinamicoFormTests(TestCase):
    def setUp(self):
        self.tipo = TipoDispositivo.objects.create(codigo="F00", nombre="Formulario")
        self.ingreso = CampoTipoDispositivo.objects.create(
            tipo_dispositivo=self.tipo,
            seccion="Ingresos y egresos",
            nombre="Ingreso total mensual",
            tipo_campo=TipoCampo.INT,
            rol_calculo=CampoTipoDispositivo.RolCalculo.INGRESO,
            orden=1,
        )
        self.alquiler = CampoTipoDispositivo.objects.create(
            tipo_dispositivo=self.tipo,
            seccion="Ingresos y egresos",
            nombre="Alquiler",
            tipo_campo=TipoCampo.INT,
            rol_calculo=CampoTipoDispositivo.RolCalculo.EGRESO,
            orden=2,
        )
        self.texto = CampoTipoDispositivo.objects.create(
            tipo_dispositivo=self.tipo,
            seccion="Datos",
            nombre="Observación",
            tipo_campo=TipoCampo.STRING,
            obligatorio=True,
            orden=3,
        )
        self.archivo = CampoTipoDispositivo.objects.create(
            tipo_dispositivo=self.tipo,
            seccion="Datos",
            nombre="Constancia",
            tipo_campo=TipoCampo.ARCHIVO,
            obligatorio=True,
            orden=4,
        )

    def test_valida_campos_configurados_y_calcula_totales_sin_persistir_archivo_en_json(self):
        data = {
            F00DinamicoForm.nombre_campo(self.ingreso): "1000",
            F00DinamicoForm.nombre_campo(self.alquiler): "1250",
            F00DinamicoForm.nombre_campo(self.texto): "Completo",
        }
        files = {F00DinamicoForm.nombre_campo(self.archivo): SimpleUploadedFile("constancia.txt", b"ok")}
        form = F00DinamicoForm(data, files, tipo_dispositivo=self.tipo)

        self.assertTrue(form.is_valid(), form.errors)
        respuestas, archivos = form.respuestas_y_archivos()
        self.assertEqual(respuestas["_totales"], {"egresos": 1250, "ingresos": 1000, "saldo_estimado": -250})
        self.assertNotIn(str(self.archivo.pk), respuestas)
        self.assertIn(self.archivo, archivos)

    def test_rechaza_un_campo_obligatorio_configurado_vacio(self):
        form = F00DinamicoForm(tipo_dispositivo=self.tipo, data={})

        self.assertFalse(form.is_valid())
        self.assertIn(F00DinamicoForm.nombre_campo(self.texto), form.errors)
        self.assertIn(F00DinamicoForm.nombre_campo(self.archivo), form.errors)

    def test_archivo_f00_se_persiste_fuera_del_json_de_respuestas(self):
        Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        usuario = User.objects.create_user("operador-archivo")
        dispositivo = Dispositivo.objects.create(
            codigo="ARCH", nombre="Archivos", tipo=self.tipo, estado=Dispositivo.Estado.ACTIVO
        )
        cama = Cama.objects.create(dispositivo=dispositivo, codigo="C-01")
        ciudadano = Ciudadano.objects.create(dni="30000004", nombre="Dora", apellido="Archivo")
        form = F00DinamicoForm(
            {
                F00DinamicoForm.nombre_campo(self.ingreso): "100",
                F00DinamicoForm.nombre_campo(self.alquiler): "10",
                F00DinamicoForm.nombre_campo(self.texto): "Completo",
            },
            {F00DinamicoForm.nombre_campo(self.archivo): SimpleUploadedFile("constancia.txt", b"ok")},
            tipo_dispositivo=self.tipo,
        )
        self.assertTrue(form.is_valid(), form.errors)
        respuestas, archivos = form.respuestas_y_archivos()

        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            admision = admitir_ciudadano(
                ciudadano=ciudadano,
                dispositivo=dispositivo,
                cama=cama,
                usuario=usuario,
                respuestas_f00=respuestas,
                archivos_f00=archivos,
            )

            self.assertFalse(any(str(self.archivo.pk) == key for key in admision.respuestas_f00))
            self.assertTrue(ArchivoAdmision.objects.filter(admision=admision, campo=self.archivo).exists())


class AdmisionesViewsTests(TestCase):
    def setUp(self):
        Programa.objects.get_or_create(
            codigo="DISPOSITIVOS", defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS}
        )
        tipo = TipoDispositivo.objects.create(codigo="VISTAS", nombre="Vistas", maneja_camas=True)
        self.dispositivo = Dispositivo.objects.create(
            codigo="HOGAR-V", nombre="Hogar Vistas", tipo=tipo, estado=Dispositivo.Estado.ACTIVO
        )
        self.cama = Cama.objects.create(dispositivo=self.dispositivo, codigo="C-01")
        self.ciudadano = Ciudadano.objects.create(
            dni="30000003", nombre="Cora", apellido="Prueba", obra_social="OS test"
        )
        self.admin = User.objects.create_superuser("admin-admisiones", "admin@example.com", "x")
        self.sin_permiso = User.objects.create_user("sin-permiso-admisiones", password="x")

    def test_admision_por_dni_reutiliza_ciudadano_y_obrasocial_y_exige_permiso_en_url(self):
        self.client.force_login(self.sin_permiso)
        prohibido = self.client.get(reverse("dispositivos:admitir", args=[self.dispositivo.pk]))
        self.assertEqual(prohibido.status_code, 403)

        self.client.force_login(self.admin)
        consulta = self.client.get(
            reverse("dispositivos:admitir", args=[self.dispositivo.pk]), {"dni": self.ciudadano.dni}
        )
        self.assertContains(consulta, "OS test")
        self.assertNotContains(consulta, 'name="nombre"')
        creado = self.client.post(
            reverse("dispositivos:admitir", args=[self.dispositivo.pk]),
            {"dni": self.ciudadano.dni, "cama": self.cama.pk, "accion": "alojar"},
        )
        self.assertRedirects(creado, reverse("dispositivos:detalle", args=[self.dispositivo.pk]))
        self.assertTrue(Admision.objects.filter(ciudadano=self.ciudadano, estado=Admision.Estado.ALOJADO).exists())

    def test_egreso_directo_sin_permiso_no_modifica_estadia(self):
        admision = admitir_ciudadano(
            ciudadano=self.ciudadano, dispositivo=self.dispositivo, cama=self.cama, usuario=self.admin
        )
        self.client.force_login(self.sin_permiso)

        response = self.client.post(
            reverse("dispositivos:egresar", args=[self.dispositivo.pk, admision.pk]),
            {"fecha_egreso": timezone.localtime().strftime("%Y-%m-%dT%H:%M"), "motivo": "Alta", "destino": "Domicilio"},
        )

        admision.refresh_from_db()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(admision.estado, Admision.Estado.ALOJADO)

    def test_dni_nuevo_precarga_los_datos_que_devuelve_renaper(self):
        self.client.force_login(self.admin)
        with patch(
            "programas.views.admisiones.CiudadanosService.consultar_renaper",
            return_value={
                "success": True,
                "data": {"nombre": "Nueva", "apellido": "Persona", "fecha_nacimiento": "2000-01-02", "genero": "F"},
            },
        ) as consultar:
            response = self.client.get(
                reverse("dispositivos:admitir", args=[self.dispositivo.pk]), {"dni": "30000005", "sexo": "F"}
            )

        consultar.assert_called_once_with("30000005", "F")
        self.assertContains(response, 'value="Nueva"')
        self.assertContains(response, 'value="Persona"')
