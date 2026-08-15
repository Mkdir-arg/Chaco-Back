"""Cobertura funcional del módulo transversal de reportes de Becas."""

import csv
from datetime import date, timedelta
from io import BytesIO, StringIO

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from core import rbac
from programas.management.commands.seed_becas import ROL_ADMIN, ROL_COORDINADOR_REGIONAL, ROL_TERRITORIAL
from programas.models import (
    Convocatoria,
    Formulario,
    ListaEspera,
    ProgramaSiis,
    Relevamiento,
    Segmento,
    Subsegmento,
    ValidacionSIS,
)
from programas.services.autorizacion import programa_becas
from programas.services.reportes_becas import (
    reporte_avance,
    reporte_beneficiarios,
    reporte_cupos,
    reporte_embudo,
    reporte_produccion,
)
from users.models import Capacidad, RolMeta


class ReportesBecasTests(TestCase):
    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.programa_activo = ProgramaSiis.objects.create(
            nombre="Programa activo", siis_programa_id=901, siis_programa_estado=ProgramaSiis.EstadoSiis.ACTIVO
        )
        self.programa_bloqueado = ProgramaSiis.objects.create(
            nombre="Programa bloqueado", siis_programa_id=902, siis_programa_estado=ProgramaSiis.EstadoSiis.INACTIVO
        )
        self.segmento = Segmento.objects.create(
            programa=self.programa_activo, nombre="Segmento compartido", cupo_maximo=300
        )
        self.segmento_pausado = Segmento.objects.create(
            programa=self.programa_activo, nombre="Segmento pausado", cupo_maximo=50, pausado=True
        )
        self.segmento_bloqueado = Segmento.objects.create(
            programa=self.programa_bloqueado, nombre="Segmento SIIS", cupo_maximo=50
        )
        self.regional = User.objects.create_user("regional-reportes", password="x")
        self.regional.groups.add(Group.objects.get(name=ROL_COORDINADOR_REGIONAL))
        self.otro_regional = User.objects.create_user("regional-ajeno", password="x")
        self.otro_regional.groups.add(Group.objects.get(name=ROL_COORDINADOR_REGIONAL))
        self.territorial = User.objects.create_user("territorial-reportes", password="x")
        self.territorial.groups.add(Group.objects.get(name=ROL_TERRITORIAL))
        self.sub_propio = Subsegmento.objects.create(
            segmento=self.segmento, nombre="Propio", cupo_maximo=100, referente=self.regional
        )
        self.sub_ajeno = Subsegmento.objects.create(
            segmento=self.segmento, nombre="Ajeno", cupo_maximo=150, referente=self.otro_regional
        )
        self.conv_propia = self._convocatoria("Convocatoria propia", self.segmento, self.sub_propio)
        self.conv_ajena = self._convocatoria("Convocatoria ajena", self.segmento, self.sub_ajeno)
        self.rel_propio = self._relevamiento(self.conv_propia, "Zona propia")
        self.rel_ajeno = self._relevamiento(self.conv_ajena, "Zona ajena")
        self.admin = User.objects.create_user("admin-reportes-becas", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))

    def _convocatoria(self, nombre, segmento, subsegmento=None):
        return Convocatoria.objects.create(
            nombre=nombre,
            segmento=segmento,
            subsegmento=subsegmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )

    def _relevamiento(self, convocatoria, zona, estado=Relevamiento.Estado.TERMINADO):
        return Relevamiento.objects.create(
            convocatoria=convocatoria,
            territorial=self.territorial,
            fecha_asignada=date(2026, 6, 1),
            fecha_hasta=date(2026, 6, 30),
            zona=zona,
            estado=estado,
        )

    def _formulario(self, relevamiento, estado=Formulario.Estado.ENVIADO, **extra):
        valores = {
            "relevamiento": relevamiento,
            "celular": "3624000000",
            "email_contacto": "reporte@example.com",
            "estado": estado,
            "datos_identificacion": {
                "dni": str(40000000 + Formulario.objects.count()),
                "nombre": "Persona",
                "apellido": "Prueba",
            },
        }
        valores.update(extra)
        return Formulario.objects.create(**valores)

    def _rol_solo_ver(self):
        grupo = Group.objects.create(name="Becas — Reportes consulta")
        RolMeta.objects.create(grupo=grupo, programa=programa_becas(), activo=True)
        content_type = ContentType.objects.get_for_model(Capacidad)
        permiso = Permission.objects.get(content_type=content_type, codename=rbac.codename_de("becas.reportes.ver"))
        grupo.permissions.add(permiso)
        usuario = User.objects.create_user("reportes-solo-ver", password="x")
        usuario.groups.add(grupo)
        return usuario

    def test_solo_activos_excluye_pausados_y_bloqueados_por_siis(self):
        reporte = reporte_cupos(self.admin, solo_activos=True)
        nombres = {fila[0] for fila in reporte.filas}

        self.assertIn(self.segmento.nombre, nombres)
        self.assertNotIn(self.segmento_pausado.nombre, nombres)
        self.assertNotIn(self.segmento_bloqueado.nombre, nombres)

    def test_regional_no_contabiliza_cupo_ni_personas_del_subsegmento_ajeno(self):
        propios = [
            self._formulario(self.rel_propio, Formulario.Estado.APROBADO, fecha_aprobacion=timezone.now())
            for _ in range(2)
        ]
        for _ in range(3):
            self._formulario(self.rel_ajeno, Formulario.Estado.APROBADO, fecha_aprobacion=timezone.now())
        ListaEspera.objects.create(formulario=self._formulario(self.rel_propio), segmento=self.segmento, posicion=1)
        ListaEspera.objects.create(formulario=self._formulario(self.rel_ajeno), segmento=self.segmento, posicion=2)

        fila = reporte_cupos(self.regional).filas[0]

        self.assertEqual(fila[1], 100)
        self.assertEqual(fila[2], 100)
        self.assertEqual(fila[3], len(propios))
        self.assertEqual(fila[4], 98)
        self.assertEqual(fila[5], 1)
        self.assertNotIn("Ajeno", str(reporte_avance(self.regional).filas))
        self.assertNotIn("Zona ajena", str(reporte_beneficiarios(self.regional).filas))

    def test_embudo_usa_ultima_validacion_siis_y_desglosa_motivos(self):
        formulario = self._formulario(
            self.rel_propio, Formulario.Estado.RECHAZADO, validado_renaper=True, motivo_rechazo="Documentación"
        )
        ValidacionSIS.objects.create(formulario=formulario, estado=ValidacionSIS.Estado.ERROR, documento="40000001")
        ValidacionSIS.objects.create(
            formulario=formulario,
            estado=ValidacionSIS.Estado.RECHAZADO,
            documento="40000001",
            codigo_motivo="BENEFICIO_EXISTENTE",
        )

        reporte = reporte_embudo(self.admin, convocatoria_id=self.conv_propia.pk)
        cantidades = {fila[0]: fila[1] for fila in reporte.filas}

        self.assertEqual(cantidades["Formularios enviados"], 1)
        self.assertEqual(cantidades["Validados RENAPER"], 1)
        self.assertEqual(cantidades["Rechazados"], 1)
        self.assertEqual(cantidades["Rechazo backoffice: Documentación"], 1)
        self.assertEqual(cantidades["Rechazo SIIS: Rechazado. La persona ya posee un beneficio"], 1)

    def test_avance_y_produccion_calculan_conteos_y_periodo_solapado(self):
        self._formulario(self.rel_propio, Formulario.Estado.APROBADO, fecha_aprobacion=timezone.now())
        self._formulario(self.rel_propio, Formulario.Estado.RECHAZADO)

        avance = reporte_avance(self.admin, segmento_id=self.segmento.pk)
        produccion = reporte_produccion(
            self.admin, segmento_id=self.segmento.pk, desde=date(2026, 6, 15), hasta=date(2026, 7, 1)
        )

        fila_avance = next(fila for fila in avance.filas if fila[0] == self.conv_propia.nombre)
        self.assertEqual(fila_avance[14:17], (0, "100.0%", "1/300"))
        fila_produccion = produccion.filas[0]
        self.assertEqual(fila_produccion[5:9], (2, 1, 1, "50.0%"))

    def test_ver_sin_exportar_muestra_pantalla_y_export_devuelve_403(self):
        usuario = self._rol_solo_ver()
        self.client.force_login(usuario)

        self.assertEqual(self.client.get(reverse("becas:reportes")).status_code, 200)
        self.assertEqual(self.client.get(reverse("becas:reporte_exportar", args=["cupos", "csv"])).status_code, 403)

    def test_sin_permiso_no_accede_por_url(self):
        self.client.force_login(self.territorial)
        self.assertEqual(self.client.get(reverse("becas:reportes")).status_code, 403)
        self.assertEqual(self.client.get(reverse("becas:reporte_detalle", args=["cupos"])).status_code, 403)

    def test_padron_pagina_pantalla_pero_exporta_todo(self):
        ahora = timezone.now()
        for indice in range(26):
            self._formulario(
                self.rel_propio,
                Formulario.Estado.APROBADO,
                fecha_aprobacion=ahora - timedelta(minutes=indice),
            )
        self.client.force_login(self.admin)

        primera = self.client.get(reverse("becas:reporte_detalle", args=["beneficiarios"]))
        segunda = self.client.get(reverse("becas:reporte_detalle", args=["beneficiarios"]), {"page": 2})
        exportado = self.client.get(reverse("becas:reporte_exportar", args=["beneficiarios", "csv"]))

        self.assertEqual(len(primera.context["reporte"].filas), 25)
        self.assertEqual(len(segunda.context["reporte"].filas), 1)
        filas_csv = list(csv.reader(StringIO(exportado.content.decode("utf-8-sig"))))
        self.assertEqual(len(filas_csv), 27)

    def test_periodo_invalido_informa_error_y_no_exporta(self):
        self.client.force_login(self.admin)
        filtros = {"desde": "2026-08-01", "hasta": "2026-07-01"}

        pantalla = self.client.get(reverse("becas:reporte_detalle", args=["avance"]), filtros)
        archivo = self.client.get(reverse("becas:reporte_exportar", args=["avance", "csv"]), filtros)

        self.assertContains(pantalla, "La fecha desde no puede ser posterior")
        self.assertEqual(archivo.status_code, 400)

    def test_cinco_reportes_renderizan_y_exportan_csv_xlsx(self):
        self._formulario(self.rel_propio, Formulario.Estado.APROBADO, fecha_aprobacion=timezone.now())
        self.client.force_login(self.admin)

        for codigo in ("cupos", "avance", "produccion", "embudo", "beneficiarios"):
            with self.subTest(reporte=codigo):
                pantalla = self.client.get(reverse("becas:reporte_detalle", args=[codigo]))
                csv_response = self.client.get(reverse("becas:reporte_exportar", args=[codigo, "csv"]))
                xlsx_response = self.client.get(reverse("becas:reporte_exportar", args=[codigo, "xlsx"]))
                self.assertEqual(pantalla.status_code, 200)
                self.assertEqual(csv_response.status_code, 200)
                self.assertEqual(xlsx_response.status_code, 200)
                filas_csv = list(csv.reader(StringIO(csv_response.content.decode("utf-8-sig"))))
                libro = load_workbook(BytesIO(xlsx_response.content), read_only=True)
                try:
                    filas_xlsx = list(libro.active.values)
                finally:
                    libro.close()
                self.assertEqual(len(filas_csv), len(filas_xlsx))

    def test_regional_no_fuerza_convocatoria_ajena_manipulando_url(self):
        self._formulario(self.rel_propio, Formulario.Estado.APROBADO, fecha_aprobacion=timezone.now())
        self._formulario(self.rel_ajeno, Formulario.Estado.APROBADO, fecha_aprobacion=timezone.now())
        self.client.force_login(self.regional)

        response = self.client.get(
            reverse("becas:reporte_exportar", args=["beneficiarios", "csv"]),
            {"convocatoria": self.conv_ajena.pk},
        )

        contenido = response.content.decode("utf-8-sig")
        self.assertNotIn("Zona ajena", contenido)
        self.assertNotIn("Zona propia", contenido)

    def test_formato_no_soportado_devuelve_400(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("becas:reporte_exportar", args=["cupos", "pdf"]))
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Formato de exportación no válido", status_code=400)
