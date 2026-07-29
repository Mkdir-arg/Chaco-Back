from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import (
    Admision,
    Cama,
    CampoTipoDispositivo,
    Dispositivo,
    Programa,
    RegistroDiario,
    TipoDispositivo,
)
from programas.services.indicadores import indicadores_dispositivo


class IndicadoresDispositivoTests(TestCase):
    def crear_programa_dispositivos(self, **umbrales):
        return Programa.objects.create(
            codigo=Programa.TipoPrograma.DISPOSITIVOS,
            nombre="Dispositivos",
            **umbrales,
        )

    def test_calcula_indicadores_desde_camas_registro_diario_y_f00_activo(self):
        self.crear_programa_dispositivos()
        tipo = TipoDispositivo.objects.create(codigo="IND", nombre="Indicadores", maneja_camas=True)
        dispositivo = Dispositivo.objects.create(codigo="IND-001", nombre="Hogar Indicadores", tipo=tipo)
        cama = Cama.objects.create(dispositivo=dispositivo, codigo="C-01", estado=Cama.Estado.OCUPADA)
        Cama.objects.create(dispositivo=dispositivo, codigo="C-02")
        campo_completo = CampoTipoDispositivo.objects.create(
            tipo_dispositivo=tipo,
            seccion="Datos",
            nombre="Documento",
            tipo_campo="STRING",
            obligatorio=True,
        )
        CampoTipoDispositivo.objects.create(
            tipo_dispositivo=tipo,
            seccion="Datos",
            nombre="Contacto",
            tipo_campo="STRING",
            obligatorio=True,
        )
        ciudadano = Ciudadano.objects.create(dni="39000001", nombre="Ana", apellido="Indicador")
        Admision.objects.create(
            ciudadano=ciudadano,
            dispositivo=dispositivo,
            cama=cama,
            fecha_ingreso=timezone.now(),
            estado=Admision.Estado.ALOJADO,
            respuestas_f00={str(campo_completo.pk): "ok"},
        )
        usuario = get_user_model().objects.create_user("indicadores")
        registro = RegistroDiario.objects.create(
            dispositivo=dispositivo,
            fecha=timezone.localdate(),
            turno=RegistroDiario.Turno.MANIANA,
            firmado_por=usuario,
        )
        RegistroDiario.objects.filter(pk=registro.pk).update(modificado=timezone.now() - timedelta(days=16))

        indicadores = indicadores_dispositivo(dispositivo)

        self.assertEqual(indicadores["ocupacion"]["semaforo"], "AMARILLO")
        self.assertEqual(indicadores["disponibilidad"]["semaforo"], "VERDE")
        self.assertEqual(indicadores["actualizacion"]["semaforo"], "AMARILLO")
        self.assertEqual(indicadores["completitud"]["porcentaje"], 50)
        self.assertEqual(indicadores["completitud"]["semaforo"], "ROJO")

    def test_informa_sin_datos_cuando_no_hay_admisiones_ni_registro_diario(self):
        self.crear_programa_dispositivos()
        tipo = TipoDispositivo.objects.create(codigo="SIN", nombre="Sin datos")
        dispositivo = Dispositivo.objects.create(codigo="SIN-001", nombre="Sin datos", tipo=tipo)

        indicadores = indicadores_dispositivo(dispositivo)

        self.assertEqual(indicadores["actualizacion"]["semaforo"], "SIN_DATOS")
        self.assertEqual(indicadores["completitud"]["semaforo"], "SIN_DATOS")

    def test_aplica_umbrales_centralizados_del_programa(self):
        self.crear_programa_dispositivos(
            umbral_disponibilidad_verde=60,
            dias_actualizacion_verde=10,
            dias_actualizacion_amarillo=20,
        )
        tipo = TipoDispositivo.objects.create(
            codigo="CONF",
            nombre="Configurado",
            maneja_camas=True,
        )
        dispositivo = Dispositivo.objects.create(codigo="CONF-001", nombre="Configurado", tipo=tipo)
        cama = Cama.objects.create(dispositivo=dispositivo, codigo="C-01", estado=Cama.Estado.OCUPADA)
        Cama.objects.create(dispositivo=dispositivo, codigo="C-02")
        ciudadano = Ciudadano.objects.create(dni="39000002", nombre="Beto", apellido="Config")
        Admision.objects.create(
            ciudadano=ciudadano,
            dispositivo=dispositivo,
            cama=cama,
            fecha_ingreso=timezone.now(),
            estado=Admision.Estado.ALOJADO,
        )

        indicadores = indicadores_dispositivo(dispositivo)

        self.assertEqual(indicadores["disponibilidad"]["semaforo"], "AMARILLO")
