from datetime import datetime, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import Admision, Cama, Dispositivo, Programa, RegistroDiario, TipoDispositivo
from programas.services.registro_diario import registrar_parte_diario


class RegistroDiarioServiceTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="operador-f01")
        Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        tipo = TipoDispositivo.objects.create(codigo="F01", nombre="Parte diario", maneja_camas=True)
        self.dispositivo = Dispositivo.objects.create(
            codigo="F01-01", nombre="Dispositivo F-01", tipo=tipo, estado=Dispositivo.Estado.ACTIVO
        )
        self.camas = [Cama.objects.create(dispositivo=self.dispositivo, codigo=f"C-{indice}") for indice in range(1, 4)]
        self.camas[2].estado = Cama.Estado.FUERA_SERVICIO
        self.camas[2].save(update_fields=["estado", "modificado"])
        self.fecha = timezone.localdate()

    def _admision(self, indice, *, ingreso, egreso=None, cama=None, estado=Admision.Estado.ALOJADO):
        ciudadano = Ciudadano.objects.create(dni=f"390000{indice:02d}", nombre="Persona", apellido=str(indice))
        return Admision.objects.create(
            ciudadano=ciudadano,
            dispositivo=self.dispositivo,
            cama=cama,
            fecha_ingreso=ingreso,
            fecha_egreso=egreso,
            estado=estado,
        )

    def test_calcula_el_parte_desde_los_movimientos_del_dia_y_no_desde_el_formulario(self):
        inicio = timezone.make_aware(datetime.combine(self.fecha, time(8)))
        ayer = inicio - timedelta(days=1)
        self._admision(1, ingreso=inicio, cama=self.camas[0])
        self._admision(2, ingreso=inicio, cama=self.camas[1])
        self._admision(3, ingreso=ayer, egreso=inicio, estado=Admision.Estado.EGRESADO)
        self._admision(4, ingreso=ayer, egreso=ayer, estado=Admision.Estado.EGRESADO)

        parte = registrar_parte_diario(
            dispositivo=self.dispositivo,
            fecha=self.fecha,
            turno=RegistroDiario.Turno.MANIANA,
            usuario=self.usuario,
            observaciones_generales="Sin novedades",
        )

        self.assertEqual(parte.camas_totales, 3)
        self.assertEqual(parte.ingresos, 2)
        self.assertEqual(parte.egresos, 1)
        self.assertEqual(parte.ocupacion_nocturna, 2)
        self.assertEqual(parte.camas_disponibles, 0)
        self.assertEqual(parte.firmado_por, self.usuario)

    def test_reabrir_el_mismo_turno_actualiza_el_unico_parte_existente(self):
        parte = registrar_parte_diario(
            dispositivo=self.dispositivo,
            fecha=self.fecha,
            turno=RegistroDiario.Turno.TARDE,
            usuario=self.usuario,
        )
        self._admision(
            5,
            ingreso=timezone.make_aware(datetime.combine(self.fecha, time(14))),
            cama=self.camas[0],
        )

        actualizado = registrar_parte_diario(
            dispositivo=self.dispositivo,
            fecha=self.fecha,
            turno=RegistroDiario.Turno.TARDE,
            usuario=self.usuario,
            observaciones_generales="Actualizado",
            observaciones={"ingresos": "Ingreso nocturno confirmado"},
        )

        self.assertEqual(actualizado.pk, parte.pk)
        self.assertEqual(RegistroDiario.objects.count(), 1)
        self.assertEqual(actualizado.ingresos, 1)
        self.assertEqual(actualizado.observaciones_generales, "Actualizado")
        self.assertEqual(actualizado.observaciones, {"ingresos": "Ingreso nocturno confirmado"})

    def test_los_tres_turnos_del_dia_generan_partes_independientes(self):
        for turno in RegistroDiario.Turno.values:
            registrar_parte_diario(
                dispositivo=self.dispositivo,
                fecha=self.fecha,
                turno=turno,
                usuario=self.usuario,
            )

        self.assertEqual(RegistroDiario.objects.count(), 3)

    def test_espera_sin_cama_no_cuenta_como_ingreso_ni_ocupacion(self):
        inicio = timezone.make_aware(datetime.combine(self.fecha, time(10)))
        self._admision(6, ingreso=inicio, estado=Admision.Estado.LISTA_ESPERA)

        parte = registrar_parte_diario(
            dispositivo=self.dispositivo,
            fecha=self.fecha,
            turno=RegistroDiario.Turno.MANIANA,
            usuario=self.usuario,
        )

        self.assertEqual(parte.ingresos, 0)
        self.assertEqual(parte.ocupacion_nocturna, 0)

    def test_post_del_parte_ignora_valores_calculados_manipulados(self):
        superusuario = User.objects.create_superuser(username="admin-f01", password="clave")
        self.client.force_login(superusuario)

        response = self.client.post(
            reverse("dispositivos:parte_diario", args=[self.dispositivo.pk]),
            {
                "turno": RegistroDiario.Turno.NOCHE,
                "observaciones_generales": "Controlado",
                "observacion_ingresos": "Verificado con guardia",
                "camas_totales": 999,
                "ingresos": 999,
                "egresos": 999,
            },
        )

        url = reverse("dispositivos:parte_diario", args=[self.dispositivo.pk])
        self.assertRedirects(response, f"{url}?turno={RegistroDiario.Turno.NOCHE}")
        parte = RegistroDiario.objects.get(dispositivo=self.dispositivo, turno=RegistroDiario.Turno.NOCHE)
        self.assertEqual(parte.camas_totales, 3)
        self.assertEqual(parte.ingresos, 0)
        self.assertEqual(parte.egresos, 0)
        self.assertEqual(parte.observaciones, {"ingresos": "Verificado con guardia"})

    def test_formulario_muestra_las_cantidades_calculadas_antes_de_guardar(self):
        administrador = User.objects.create_superuser(username="admin-snapshot", password="clave")
        self.client.force_login(administrador)

        response = self.client.get(reverse("dispositivos:parte_diario", args=[self.dispositivo.pk]))

        self.assertContains(response, "Camas totales")
        self.assertContains(response, "Firma al guardar")

    def test_reabrir_por_get_precarga_el_parte_existente_del_turno(self):
        registrar_parte_diario(
            dispositivo=self.dispositivo,
            fecha=self.fecha,
            turno=RegistroDiario.Turno.MANIANA,
            usuario=self.usuario,
            observaciones_generales="Observación previa",
            observaciones={"camas_disponibles": "Una cama fuera de servicio"},
        )
        administrador = User.objects.create_superuser(username="admin-reabrir", password="clave")
        self.client.force_login(administrador)

        response = self.client.get(
            reverse("dispositivos:parte_diario", args=[self.dispositivo.pk]),
            {"turno": RegistroDiario.Turno.MANIANA},
        )

        self.assertContains(response, "Observación previa")
        self.assertContains(response, "Una cama fuera de servicio")
        self.assertContains(response, "Camas totales")

    def test_dispositivo_inactivo_no_permite_registrar_el_parte(self):
        self.dispositivo.estado = Dispositivo.Estado.CERRADO
        self.dispositivo.save(update_fields=["estado", "modificado"])

        with self.assertRaisesMessage(ValueError, "debe estar activo"):
            registrar_parte_diario(
                dispositivo=self.dispositivo,
                fecha=self.fecha,
                turno=RegistroDiario.Turno.NOCHE,
                usuario=self.usuario,
            )

    def test_servicio_rechaza_un_turno_fuera_del_dominio(self):
        with self.assertRaisesMessage(ValueError, "mañana, tarde o noche"):
            registrar_parte_diario(
                dispositivo=self.dispositivo,
                fecha=self.fecha,
                turno="MADRUGADA",
                usuario=self.usuario,
            )

    def test_endpoint_del_parte_exige_permiso_de_admision(self):
        self.client.force_login(User.objects.create_user(username="sin-permiso-f01"))

        response = self.client.get(reverse("dispositivos:parte_diario", args=[self.dispositivo.pk]))

        self.assertEqual(response.status_code, 403)
