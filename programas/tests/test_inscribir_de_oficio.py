"""Alta de oficio de beneficiarias vigentes (comando ``inscribir_de_oficio``).

Personas que ya son beneficiarias y ya figuran en SIIS: el caso se crea y queda
APROBADO sin pasar por SIIS ni mandar correos. Personas (Gran Base) va mockeada.
"""

import csv
import io
import os
import tempfile
from datetime import date, timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import (
    Convocatoria,
    EnvioSIIS,
    Formulario,
    Relevamiento,
    Segmento,
    TracaFormulario,
    ValidacionSIS,
)

PERSONAS = "programas.services.identidad.consultar_persona"
GRAN_BASE = "programas.services.identidad.gran_base_activa"


def _ok(nombre="Ana", apellido="Paz"):
    return {"success": True, "data": {"nombre": nombre, "apellido": apellido, "fecha_nacimiento": "1980-05-01"}}


class AltaDeOficioBase(TestCase):
    cupo_segmento = 100
    cupo_relevamiento = 100

    def setUp(self):
        self.usuario = User.objects.create_user("pm_oficio", password="x")
        self.segmento = Segmento.objects.create(nombre="Seg oficio", cupo_maximo=self.cupo_segmento)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas oficio",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now() - timedelta(days=1),
            fecha_hasta=timezone.now() + timedelta(days=10),
            cupo_maximo=self.cupo_relevamiento,
        )
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.informe = os.path.join(self._tmp.name, "informe.csv")
        gran_base = mock.patch(GRAN_BASE, return_value=True)
        gran_base.start()
        self.addCleanup(gran_base.stop)

    def csv(self, filas, encabezado="dni,sexo,apellido,nombres"):
        ruta = os.path.join(self._tmp.name, "personas.csv")
        with open(ruta, "w", encoding="utf-8-sig", newline="") as archivo:
            archivo.write(encabezado + "\n")
            for fila in filas:
                archivo.write(",".join(fila) + "\n")
        return ruta

    def correr(self, filas, *, aplicar=True, **extra):
        salida = io.StringIO()
        argumentos = {
            "token": str(self.relevamiento.token_publico),
            "archivo": self.csv(filas),
            "usuario": "pm_oficio",
            "pausa": 0,
            "stdout": salida,
            "stderr": io.StringIO(),
            **extra,
        }
        if aplicar:
            argumentos.update(aplicar=True, informe=self.informe)
        call_command("inscribir_de_oficio", **argumentos)
        return salida.getvalue()

    def informe_filas(self):
        with open(self.informe, encoding="utf-8-sig", newline="") as archivo:
            return list(csv.DictReader(archivo))


class EnSecoTests(AltaDeOficioBase):
    def test_en_seco_no_escribe_nada(self):
        with mock.patch(PERSONAS, return_value=_ok()) as personas:
            salida = self.correr([["30111222", "F", "Paz", "Ana"]], aplicar=False)
        self.assertEqual(Formulario.objects.count(), 0)
        self.assertEqual(Ciudadano.objects.count(), 0)
        self.assertEqual(TracaFormulario.objects.count(), 0)
        personas.assert_not_called()
        self.assertIn("EN SECO", salida)

    def test_en_seco_con_consultar_personas_informa_pero_no_escribe(self):
        with mock.patch(PERSONAS, return_value=_ok()):
            salida = self.correr(
                [["30111222", "F", "Paz", "Ana"], ["30111223", "M", "Gomez", "Luis"]],
                aplicar=False,
                consultar_personas=True,
            )
        self.assertEqual(Formulario.objects.count(), 0)
        self.assertIn("Validarían en Personas: 2", salida)

    def test_aplicar_exige_informe(self):
        with self.assertRaises(CommandError):
            call_command(
                "inscribir_de_oficio",
                token=str(self.relevamiento.token_publico),
                archivo=self.csv([["30111222", "F", "Paz", "Ana"]]),
                usuario="pm_oficio",
                aplicar=True,
                stdout=io.StringIO(),
            )

    def test_la_salida_no_lleva_nombres(self):
        with mock.patch(PERSONAS, return_value=_ok("Zulema", "Quispe")):
            salida = self.correr([["30111222", "F", "Quispe", "Zulema"]])
        self.assertNotIn("Zulema", salida)
        self.assertNotIn("Quispe", salida)


class AplicarTests(AltaDeOficioBase):
    def test_alta_validada_queda_aprobada_con_ciudadano_y_traza(self):
        with mock.patch(PERSONAS, return_value=_ok()):
            self.correr([["30111222", "F", "Paz", "Ana"]])
        formulario = Formulario.objects.get()
        self.assertEqual(formulario.estado, Formulario.Estado.APROBADO)
        self.assertTrue(formulario.validado_renaper)
        self.assertEqual(formulario.origen_validacion, "personas")
        self.assertEqual(formulario.created_by, self.usuario)
        self.assertEqual(formulario.ciudadano.dni, "30111222")
        self.assertEqual(formulario.ciudadano.apellido, "Paz")
        campos = set(formulario.trazas.values_list("campo", flat=True))
        self.assertEqual(campos, {"estado", "alta_de_oficio"})
        marca = formulario.trazas.get(campo="alta_de_oficio")
        self.assertIn("ya figura en SIIS", marca.valor_nuevo)
        self.assertEqual(marca.editado_por, self.usuario)
        fila = self.informe_filas()[0]
        self.assertEqual(fila["resultado"], "aprobado")
        self.assertEqual(fila["numero_formulario"], str(formulario.numero))
        self.assertEqual(fila["ciudadano_id"], str(formulario.ciudadano_id))
        self.assertEqual(fila["origen"], "personas")

    def test_no_validada_queda_enviada_con_datos_del_csv(self):
        sin_datos = {"success": False, "error": "No encontrada", "not_found": True}
        with mock.patch(PERSONAS, return_value=sin_datos):
            self.correr([["30111222", "F", "Perez", "Juan"]])
        formulario = Formulario.objects.get()
        self.assertEqual(formulario.estado, Formulario.Estado.ENVIADO)
        self.assertFalse(formulario.validado_renaper)
        self.assertEqual(formulario.ciudadano.apellido, "Perez")
        self.assertEqual(self.informe_filas()[0]["resultado"], "creado_sin_validar")
        self.assertEqual(self.informe_filas()[0]["origen"], "manual")

    def test_ya_inscripto_se_saltea(self):
        Formulario.objects.create(
            relevamiento=self.relevamiento, datos_identificacion={"dni": "30111222"}, validado_renaper=True
        )
        with mock.patch(PERSONAS, return_value=_ok()) as personas:
            self.correr([["30111222", "F", "Paz", "Ana"]])
        self.assertEqual(Formulario.objects.count(), 1)
        personas.assert_not_called()
        self.assertEqual(self.informe_filas()[0]["resultado"], "ya_inscripto")

    def test_dni_repetido_en_el_archivo(self):
        with mock.patch(PERSONAS, return_value=_ok()):
            self.correr([["30111222", "F", "Paz", "Ana"], ["30.111.222", "F", "Paz", "Ana"]])
        self.assertEqual(Formulario.objects.count(), 1)
        self.assertEqual([f["resultado"] for f in self.informe_filas()], ["aprobado", "duplicado_archivo"])

    def test_dni_o_sexo_invalidos(self):
        with mock.patch(PERSONAS, return_value=_ok()):
            self.correr([["123", "F", "A", "B"], ["30111222", "X", "A", "B"]])
        self.assertEqual(Formulario.objects.count(), 0)
        self.assertEqual([f["resultado"] for f in self.informe_filas()], ["invalido", "invalido"])

    def test_fallecido_no_se_crea(self):
        with mock.patch(PERSONAS, return_value={"success": False, "fallecido": True}):
            self.correr([["30111222", "F", "Paz", "Ana"]])
        self.assertEqual(Formulario.objects.count(), 0)
        self.assertEqual(self.informe_filas()[0]["resultado"], "fallecido")

    def test_error_tecnico_no_crea_y_frena_tras_el_maximo(self):
        caida = {"success": False, "error": "timeout"}
        filas = [[str(30111000 + n), "F", "A", "B"] for n in range(6)]
        with mock.patch(PERSONAS, return_value=caida) as personas:
            self.correr(filas, max_errores=3)
        self.assertEqual(Formulario.objects.count(), 0)
        self.assertEqual(personas.call_count, 3)
        self.assertEqual(len(self.informe_filas()), 3)

    def test_una_fila_que_falla_no_corta_el_resto(self):
        respuestas = [{"success": False, "error": "boom"}, _ok()]
        with mock.patch(PERSONAS, side_effect=respuestas):
            self.correr([["30111222", "F", "Paz", "Ana"], ["30111223", "F", "Paz", "Eva"]])
        self.assertEqual([f["resultado"] for f in self.informe_filas()], ["error", "aprobado"])

    def test_no_manda_correos_ni_toca_siis(self):
        with (
            mock.patch(PERSONAS, return_value=_ok()),
            mock.patch("programas.services.validacion_siis.validar_formulario_en_siis") as validar,
            mock.patch("programas.services.siis_envio.enviar_beneficiario_a_siis") as enviar,
        ):
            self.correr([["30111222", "F", "Paz", "Ana"]])
        self.assertEqual(Formulario.objects.get().estado, Formulario.Estado.APROBADO)
        self.assertEqual(mail.outbox, [])
        validar.assert_not_called()
        enviar.assert_not_called()
        self.assertEqual(ValidacionSIS.objects.count(), 0)
        self.assertEqual(EnvioSIIS.objects.count(), 0)


class IdempotenciaTests(AltaDeOficioBase):
    def test_rerrida_no_duplica(self):
        filas = [["30111222", "F", "Paz", "Ana"]]
        with mock.patch(PERSONAS, return_value=_ok()):
            self.correr(filas)
            self.correr(filas)
        self.assertEqual(Formulario.objects.count(), 1)
        self.assertEqual(Ciudadano.objects.count(), 1)
        self.assertEqual(self.informe_filas()[0]["resultado"], "ya_aprobado")
        self.assertEqual(TracaFormulario.objects.filter(campo="alta_de_oficio").count(), 1)

    def test_rerrida_aprueba_el_caso_que_antes_no_validaba(self):
        filas = [["30111222", "F", "Perez", "Juan"]]
        with mock.patch(PERSONAS, return_value={"success": False, "error": "no", "not_found": True}):
            self.correr(filas)
        self.assertEqual(Formulario.objects.get().estado, Formulario.Estado.ENVIADO)
        with mock.patch(PERSONAS, return_value=_ok("Juan", "Perez")):
            self.correr(filas)
        formulario = Formulario.objects.get()
        self.assertEqual(Formulario.objects.count(), 1)
        self.assertEqual(formulario.estado, Formulario.Estado.APROBADO)
        self.assertTrue(formulario.validado_renaper)
        self.assertEqual(self.informe_filas()[0]["resultado"], "aprobado")

    def test_corte_en_la_aprobacion_no_deja_nada_a_medias_y_se_retoma(self):
        """Corte entre el alta y la aprobación: la fila revierte entera y la re-corrida la completa."""
        with mock.patch("programas.services.alta_de_oficio.aprobar_de_oficio", side_effect=RuntimeError("corte")):
            with mock.patch(PERSONAS, return_value=_ok()):
                self.correr([["30111222", "F", "Paz", "Ana"]])
        self.assertEqual(Formulario.objects.count(), 0, "la fila falló entera: nada a medias")
        with mock.patch(PERSONAS, return_value=_ok()):
            self.correr([["30111222", "F", "Paz", "Ana"]])
        self.assertEqual(Formulario.objects.get().estado, Formulario.Estado.APROBADO)


class CupoTests(AltaDeOficioBase):
    cupo_segmento = 1

    def test_cupo_insuficiente_aborta_antes_de_escribir(self):
        with mock.patch(PERSONAS, return_value=_ok()) as personas:
            with self.assertRaisesMessage(CommandError, "cupo"):
                self.correr([["30111222", "F", "Paz", "Ana"], ["30111223", "F", "Paz", "Eva"]])
        self.assertEqual(Formulario.objects.count(), 0)
        personas.assert_not_called()

    def test_cupo_insuficiente_tambien_aborta_en_seco(self):
        with self.assertRaisesMessage(CommandError, "cupo"):
            self.correr([["30111222", "F", "Paz", "Ana"], ["30111223", "F", "Paz", "Eva"]], aplicar=False)

    def test_aprobar_de_oficio_sin_cupo_no_manda_a_lista_de_espera(self):
        from django.core.exceptions import ValidationError

        from programas.models import ListaEspera
        from programas.services.cupo import aprobar_de_oficio

        ocupante = Formulario.objects.create(relevamiento=self.relevamiento, estado=Formulario.Estado.APROBADO)
        self.assertEqual(ocupante.estado, Formulario.Estado.APROBADO)
        ciudadano = Ciudadano.objects.create(dni="30111999", nombre="X", apellido="Y")
        caso = Formulario.objects.create(relevamiento=self.relevamiento, ciudadano=ciudadano, validado_renaper=True)
        with self.assertRaises(ValidationError):
            aprobar_de_oficio(caso, self.usuario)
        caso.refresh_from_db()
        self.assertEqual(caso.estado, Formulario.Estado.ENVIADO)
        self.assertEqual(ListaEspera.objects.count(), 0)


class AprobarDeOficioReglasTests(AltaDeOficioBase):
    def test_no_aprueba_sin_identidad_validada(self):
        from django.core.exceptions import ValidationError

        from programas.services.cupo import aprobar_de_oficio

        ciudadano = Ciudadano.objects.create(dni="30111999", nombre="X", apellido="Y")
        caso = Formulario.objects.create(relevamiento=self.relevamiento, ciudadano=ciudadano, validado_renaper=False)
        with self.assertRaises(ValidationError):
            aprobar_de_oficio(caso, self.usuario)
        caso.refresh_from_db()
        self.assertEqual(caso.estado, Formulario.Estado.ENVIADO)

    def test_no_aprueba_sin_ciudadano(self):
        from django.core.exceptions import ValidationError

        from programas.services.cupo import aprobar_de_oficio

        caso = Formulario.objects.create(relevamiento=self.relevamiento, validado_renaper=True)
        with self.assertRaises(ValidationError):
            aprobar_de_oficio(caso, self.usuario)


class MarcaDeOficioTests(AltaDeOficioBase):
    def test_la_marca_nace_con_el_caso_tambien_sin_validar(self):
        sin_datos = {"success": False, "error": "No encontrada", "not_found": True}
        with mock.patch(PERSONAS, return_value=sin_datos):
            self.correr([["30111222", "F", "Perez", "Juan"]])
        formulario = Formulario.objects.get()
        self.assertEqual(formulario.estado, Formulario.Estado.ENVIADO)
        self.assertEqual(formulario.trazas.filter(campo="alta_de_oficio").count(), 1)

    def test_ya_inscripto_informa_estado_y_numero(self):
        previo = Formulario.objects.create(
            relevamiento=self.relevamiento, datos_identificacion={"dni": "30111222"}, validado_renaper=True
        )
        with mock.patch(PERSONAS, return_value=_ok()):
            self.correr([["30111222", "F", "Paz", "Ana"]])
        detalle = self.informe_filas()[0]["detalle"]
        self.assertIn(f"caso {previo.numero}", detalle)
        self.assertIn("ENVIADO", detalle)

    def test_error_de_conexion_cuenta_como_tecnico_y_frena(self):
        from django.db import OperationalError

        filas = [[str(30111000 + n), "F", "A", "B"] for n in range(6)]
        with (
            mock.patch(PERSONAS, side_effect=OperationalError("server has gone away")) as personas,
            mock.patch("programas.management.commands.inscribir_de_oficio.close_old_connections") as cerrar,
        ):
            self.correr(filas, max_errores=3)
        self.assertEqual(personas.call_count, 3)
        self.assertEqual(cerrar.call_count, 3)
        self.assertEqual(Formulario.objects.count(), 0)

    def test_acreditar_deja_constancia_y_completa_nacimiento(self):
        filas = [["30111222", "F", "Perez", "Juan"]]
        with mock.patch(PERSONAS, return_value={"success": False, "error": "no", "not_found": True}):
            self.correr(filas)
        with mock.patch(PERSONAS, return_value=_ok("Juana", "Perez Oficial")):
            self.correr(filas)
        formulario = Formulario.objects.get()
        formulario.ciudadano.refresh_from_db()
        self.assertEqual(str(formulario.ciudadano.fecha_nacimiento), "1980-05-01")
        self.assertEqual(formulario.ciudadano.nombre, "Juan", "el legajo no se corrige: solo se deja constancia")
        self.assertTrue(formulario.trazas.filter(campo__startswith="Identidad acreditada").exists())
        self.assertIn("_identidad_acreditada", formulario.datos_siis)

    def test_aprobar_de_oficio_respeta_la_lista_de_espera(self):
        from django.core.exceptions import ValidationError

        from programas.models import ListaEspera
        from programas.services.cupo import CasoEnListaEspera, aprobar_de_oficio

        ciudadano = Ciudadano.objects.create(dni="30111999", nombre="X", apellido="Y")
        caso = Formulario.objects.create(relevamiento=self.relevamiento, ciudadano=ciudadano, validado_renaper=True)
        ListaEspera.objects.create(formulario=caso, segmento=self.segmento, posicion=1)
        with self.assertRaises(CasoEnListaEspera):
            aprobar_de_oficio(caso, self.usuario)
        caso.refresh_from_db()
        self.assertEqual(caso.estado, Formulario.Estado.ENVIADO)
        self.assertTrue(issubclass(CasoEnListaEspera, ValidationError))


class NingunCaminoInformaASiisTests(AltaDeOficioBase):
    """Los casos de oficio ya figuran en SIIS y la API no deduplica."""

    def setUp(self):
        super().setUp()
        from programas.models import ProgramaSiis

        self.programa = ProgramaSiis.objects.create(nombre="Becas oficio", siis_programa_id=7)
        self.segmento.programa = self.programa
        self.segmento.save()

    def _de_oficio(self, dni="30111222", nombre="Ana"):
        with mock.patch(PERSONAS, return_value=_ok(nombre, "Paz")):
            self.correr([[dni, "F", "Paz", nombre]])
        return Formulario.objects.get(dni_titular=dni)

    def _comun(self, dni="30999888"):
        ciudadano = Ciudadano.objects.create(dni=dni, nombre="Otra", apellido="Persona")
        return Formulario.objects.create(
            relevamiento=self.relevamiento,
            ciudadano=ciudadano,
            estado=Formulario.Estado.APROBADO,
            validado_renaper=True,
        )

    def test_reservar_cierra_sin_llamar_a_siis(self):
        from programas.services import siis_envio

        formulario = self._de_oficio()
        with (
            mock.patch("programas.services.siis_envio.cargar_beneficiario") as api,
            mock.patch("programas.services.siis_envio.armar_payload", return_value=({"id_plan_soc": 7}, {})),
        ):
            envio = siis_envio.enviar_beneficiario_a_siis(formulario, self.usuario, catalogos=mock.MagicMock())
        api.assert_not_called()
        self.assertEqual(envio.estado, EnvioSIIS.Estado.RECHAZADO)
        self.assertEqual(envio.codigo_error, "ALTA_DE_OFICIO")
        self.assertFalse(envio.vigente)
        self.assertFalse(EnvioSIIS.objects.filter(formulario=formulario, vigente=True).exists())

    def test_enviar_no_arma_el_payload_de_un_caso_de_oficio(self):
        """Sin catálogos, armar el payload dejaba al caso en ERROR SIN_COPIA_CATALOGO."""
        from programas.services import siis_envio

        formulario = self._de_oficio()
        with mock.patch("programas.services.siis_envio.armar_payload") as armar:
            envio = siis_envio.enviar_beneficiario_a_siis(formulario, self.usuario, catalogos=mock.MagicMock())
        armar.assert_not_called()
        self.assertEqual(envio.codigo_error, "ALTA_DE_OFICIO")

    def test_reenviar_siis_pendientes_no_lista_al_de_oficio_pero_si_al_comun(self):
        from programas.management.commands.reenviar_siis_pendientes import Command

        oficio = self._de_oficio()
        comun = self._comun()
        for formulario in (oficio, comun):
            EnvioSIIS.objects.create(
                formulario=formulario,
                solicitado_por=self.usuario,
                estado=EnvioSIIS.Estado.ERROR,
                codigo_error="SIN_COPIA_CATALOGO",
            )
        casos, _agotados = Command()._casos(None)
        pks = {caso.pk for caso in casos}
        self.assertIn(comun.pk, pks)
        self.assertNotIn(oficio.pk, pks)

    def test_guardar_en_tabla_intermedia_no_guarda(self):
        from programas.models import AltaIntermediaSIIS
        from programas.services.siis_envio import guardar_en_tabla_intermedia

        formulario = self._de_oficio()
        alta, envio = guardar_en_tabla_intermedia(formulario, self.usuario, catalogos=mock.MagicMock())
        self.assertIsNone(alta)
        self.assertEqual(envio.codigo_error, "ALTA_DE_OFICIO")
        self.assertFalse(AltaIntermediaSIIS.objects.exists())

    def test_candidatos_no_toma_al_de_oficio_pero_si_al_comun(self):
        from programas.services import proceso_masivo

        oficio_aprobado = self._de_oficio()
        sin_validar = self._de_oficio(dni="30111223", nombre="Eva")
        Formulario.objects.filter(pk=sin_validar.pk).update(estado=Formulario.Estado.ENVIADO)
        comun = self._comun()
        for destino in (proceso_masivo.DESTINO_SIIS, proceso_masivo.DESTINO_TABLA):
            pks = set(proceso_masivo.candidatos(filtrar_materias=False, destino=destino).values_list("pk", flat=True))
            self.assertIn(comun.pk, pks)
            self.assertNotIn(oficio_aprobado.pk, pks)
            self.assertNotIn(sin_validar.pk, pks)

    def test_enviar_casos_siis_no_toma_al_de_oficio_pero_si_al_comun(self):
        from programas.management.commands.enviar_casos_siis import Command

        oficio = self._de_oficio()
        comun = self._comun()
        opciones = {
            "convocatoria": None,
            "relevamiento": None,
            "segmento": None,
            "programa": None,
            "limite": None,
            "reintentar_rechazados": False,
            "sin_filtro_materias": True,
        }
        pks = {fila[0] for fila in Command()._casos(opciones, [Formulario.Estado.APROBADO])}
        self.assertIn(comun.pk, pks)
        self.assertNotIn(oficio.pk, pks)
