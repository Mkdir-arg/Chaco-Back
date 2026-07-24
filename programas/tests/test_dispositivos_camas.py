"""Contratos públicos de gestión de camas del Programa Dispositivos (#176)."""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from legajos.models import Ciudadano
from programas.forms import DispositivoForm, TipoDispositivoForm
from programas.models import Admision, Cama, Dispositivo, Programa, TipoDispositivo
from programas.services.camas import cambiar_estado_cama, crear_camas, resumen_ocupacion


class ResumenOcupacionTests(TestCase):
    def test_forma_de_tipo_conserva_umbrales_por_defecto_en_post_existente(self):
        tipo = TipoDispositivo.objects.create(codigo="FORM", nombre="Formulario", maneja_camas=True)

        form = TipoDispositivoForm(
            {"codigo": "FORM", "nombre": "Formulario actualizado", "descripcion": "", "activo": "on"},
            instance=tipo,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_formulario_de_dispositivo_no_permite_editar_capacidad_manual(self):
        self.assertNotIn("camas_totales", DispositivoForm.base_fields)

    def test_deriva_ocupadas_libres_y_semaforo_de_estadias_activas(self):
        tipo = TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor", maneja_camas=True)
        dispositivo = Dispositivo.objects.create(
            codigo="HOGAR-001",
            nombre="Hogar Norte",
            tipo=tipo,
            camas_totales=10,
        )
        camas = [Cama.objects.create(dispositivo=dispositivo, codigo=f"C-{numero:02d}") for numero in range(1, 11)]

        for numero, cama in enumerate(camas[:7], start=1):
            ciudadano = Ciudadano.objects.create(dni=f"300000{numero:02d}", nombre="Persona", apellido=str(numero))
            Admision.objects.create(
                ciudadano=ciudadano,
                dispositivo=dispositivo,
                cama=cama,
                fecha_ingreso=timezone.now(),
                estado=Admision.Estado.ALOJADO,
            )

        resumen = resumen_ocupacion(dispositivo)

        self.assertEqual(
            resumen,
            {
                "totales": 10,
                "ocupadas": 7,
                "fuera_servicio": 0,
                "operativas": 10,
                "libres": 3,
                "porcentaje": 70,
                "semaforo": "AMARILLO",
            },
        )

    def test_aplica_umbrales_del_tipo_y_excluye_camas_fuera_de_servicio(self):
        tipo = TipoDispositivo.objects.create(
            codigo="UPI",
            nombre="Unidad de Primera Infancia",
            maneja_camas=True,
            umbral_ocupacion_amarillo=40,
            umbral_ocupacion_rojo=60,
        )
        dispositivo = Dispositivo.objects.create(
            codigo="UPI-001",
            nombre="UPI Centro",
            tipo=tipo,
            camas_totales=10,
        )
        camas = [Cama.objects.create(dispositivo=dispositivo, codigo=f"C-{numero:02d}") for numero in range(1, 11)]
        camas[-1].estado = Cama.Estado.FUERA_SERVICIO
        camas[-1].save(update_fields=["estado", "modificado"])

        for numero, cama in enumerate(camas[:5], start=1):
            ciudadano = Ciudadano.objects.create(dni=f"310000{numero:02d}", nombre="Persona", apellido=str(numero))
            Admision.objects.create(
                ciudadano=ciudadano,
                dispositivo=dispositivo,
                cama=cama,
                fecha_ingreso=timezone.now(),
                estado=Admision.Estado.ALOJADO,
            )

        resumen = resumen_ocupacion(dispositivo)

        self.assertEqual(resumen["operativas"], 9)
        self.assertEqual(resumen["libres"], 4)
        self.assertEqual(resumen["porcentaje"], 56)
        self.assertEqual(resumen["semaforo"], "AMARILLO")

    def test_semaforo_compara_el_porcentaje_exacto_antes_de_redondear(self):
        tipo = TipoDispositivo.objects.create(codigo="BORDE", nombre="Borde", maneja_camas=True)
        dispositivo = Dispositivo.objects.create(codigo="BORDE-001", nombre="Borde", tipo=tipo)
        camas = [Cama.objects.create(dispositivo=dispositivo, codigo=f"C-{numero:03d}") for numero in range(1, 102)]
        for numero, cama in enumerate(camas[:50], start=1):
            ciudadano = Ciudadano.objects.create(dni=f"3300{numero:04d}", nombre="Persona", apellido=str(numero))
            Admision.objects.create(
                ciudadano=ciudadano,
                dispositivo=dispositivo,
                cama=cama,
                fecha_ingreso=timezone.now(),
                estado=Admision.Estado.ALOJADO,
            )

        resumen = resumen_ocupacion(dispositivo)

        self.assertEqual(resumen["porcentaje"], 50)
        self.assertEqual(resumen["semaforo"], "VERDE")


class IntegridadCamasTests(TestCase):
    def test_crea_camas_disponibles_y_sincroniza_el_total_del_dispositivo(self):
        tipo = TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor", maneja_camas=True)
        dispositivo = Dispositivo.objects.create(codigo="HOGAR-000", nombre="Hogar Oeste", tipo=tipo)

        creadas = crear_camas(dispositivo, 3)

        self.assertEqual([cama.codigo for cama in creadas], ["C-01", "C-02", "C-03"])
        self.assertTrue(all(cama.estado == Cama.Estado.DISPONIBLE for cama in creadas))
        dispositivo.refresh_from_db()
        self.assertEqual(dispositivo.camas_totales, 3)

    def test_no_permite_dos_estadias_alojadas_en_la_misma_cama(self):
        tipo = TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor", maneja_camas=True)
        dispositivo = Dispositivo.objects.create(codigo="HOGAR-002", nombre="Hogar Sur", tipo=tipo)
        cama = Cama.objects.create(dispositivo=dispositivo, codigo="C-01")
        primera = Ciudadano.objects.create(dni="32000001", nombre="Ana", apellido="Uno")
        segunda = Ciudadano.objects.create(dni="32000002", nombre="Beto", apellido="Dos")
        Admision.objects.create(
            ciudadano=primera,
            dispositivo=dispositivo,
            cama=cama,
            fecha_ingreso=timezone.now(),
            estado=Admision.Estado.ALOJADO,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Admision.objects.create(
                ciudadano=segunda,
                dispositivo=dispositivo,
                cama=cama,
                fecha_ingreso=timezone.now(),
                estado=Admision.Estado.ALOJADO,
            )

    def test_no_puede_dejar_fuera_de_servicio_una_cama_con_persona_alojada(self):
        tipo = TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor", maneja_camas=True)
        dispositivo = Dispositivo.objects.create(codigo="HOGAR-003", nombre="Hogar Este", tipo=tipo)
        cama = Cama.objects.create(dispositivo=dispositivo, codigo="C-01", estado=Cama.Estado.OCUPADA)
        ciudadano = Ciudadano.objects.create(dni="32000003", nombre="Cora", apellido="Tres")
        Admision.objects.create(
            ciudadano=ciudadano,
            dispositivo=dispositivo,
            cama=cama,
            fecha_ingreso=timezone.now(),
            estado=Admision.Estado.ALOJADO,
        )

        with self.assertRaisesMessage(ValidationError, "reasignación previa"):
            cambiar_estado_cama(cama, Cama.Estado.FUERA_SERVICIO)

        cama.refresh_from_db()
        self.assertEqual(cama.estado, Cama.Estado.OCUPADA)

    def test_no_permite_marcar_una_cama_ocupada_sin_estadia_activa(self):
        tipo = TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor", maneja_camas=True)
        dispositivo = Dispositivo.objects.create(codigo="HOGAR-005", nombre="Hogar Oeste", tipo=tipo)
        cama = Cama.objects.create(dispositivo=dispositivo, codigo="C-01")

        with self.assertRaisesMessage(ValidationError, "se deriva de una estadía activa"):
            cambiar_estado_cama(cama, Cama.Estado.OCUPADA)

        cama.refresh_from_db()
        self.assertEqual(cama.estado, Cama.Estado.DISPONIBLE)

    def test_admision_rechaza_una_cama_fuera_de_servicio(self):
        tipo = TipoDispositivo.objects.create(codigo="ASIG", nombre="Asignación", maneja_camas=True)
        dispositivo = Dispositivo.objects.create(codigo="HOGAR-006", nombre="Hogar Centro", tipo=tipo)
        fuera_servicio = Cama.objects.create(
            dispositivo=dispositivo,
            codigo="C-01",
            estado=Cama.Estado.FUERA_SERVICIO,
        )
        ciudadano = Ciudadano.objects.create(dni="32000004", nombre="Dani", apellido="Cuatro")
        admision = Admision(
            ciudadano=ciudadano,
            dispositivo=dispositivo,
            cama=fuera_servicio,
            fecha_ingreso=timezone.now(),
            estado=Admision.Estado.ALOJADO,
        )

        with self.assertRaisesMessage(ValidationError, "fuera de servicio"):
            admision.full_clean()

    def test_rechaza_transiciones_de_estado_fuera_de_la_maquina(self):
        tipo = TipoDispositivo.objects.create(codigo="EST", nombre="Estados", maneja_camas=True)
        dispositivo = Dispositivo.objects.create(codigo="HOGAR-007", nombre="Hogar Estado", tipo=tipo)
        cama = Cama.objects.create(dispositivo=dispositivo, codigo="C-01", estado=Cama.Estado.FUERA_SERVICIO)

        with self.assertRaisesMessage(ValidationError, "transición"):
            cambiar_estado_cama(cama, Cama.Estado.RESERVADA)


class CamasViewsTests(TestCase):
    def setUp(self):
        Programa.objects.create(codigo="DISPOSITIVOS", nombre="Dispositivos", tipo=Programa.TipoPrograma.DISPOSITIVOS)
        tipo = TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor", maneja_camas=True)
        self.dispositivo = Dispositivo.objects.create(codigo="HOGAR-004", nombre="Hogar Centro", tipo=tipo)
        self.admin = User.objects.create_superuser("admin-camas", "admin@example.com", "test")
        self.sin_permiso = User.objects.create_user("sin-permiso-camas", password="test")

    def test_agregar_camas_crea_capacidad_y_exige_alcance_por_url_directa(self):
        self.client.force_login(self.sin_permiso)
        prohibido = self.client.get(reverse("dispositivos:camas_agregar", args=[self.dispositivo.pk]))
        self.assertEqual(prohibido.status_code, 403)

        self.client.force_login(self.admin)
        creado = self.client.post(reverse("dispositivos:camas_agregar", args=[self.dispositivo.pk]), {"cantidad": 2})

        self.assertRedirects(creado, reverse("dispositivos:detalle", args=[self.dispositivo.pk]))
        self.assertEqual(Cama.objects.filter(dispositivo=self.dispositivo).count(), 2)
