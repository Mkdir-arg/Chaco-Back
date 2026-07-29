import csv
from datetime import date, datetime
from io import BytesIO, StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from core import rbac
from legajos.models import Ciudadano
from programas.models import (
    Admision,
    AsignacionDispositivo,
    Cama,
    Dispositivo,
    EntregaMercaderia,
    Merendero,
    Programa,
    TipoDispositivo,
)
from users.models import Capacidad, RolMeta


def permiso(codigo):
    content_type = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=content_type)


class ReportesExportablesTests(TestCase):
    def setUp(self):
        self.dispositivos_programa = Programa.objects.create(
            codigo=Programa.TipoPrograma.DISPOSITIVOS,
            nombre="Dispositivos",
            tipo=Programa.TipoPrograma.DISPOSITIVOS,
        )
        self.merenderos_programa = Programa.objects.create(
            codigo=Programa.TipoPrograma.MERENDEROS,
            nombre="Merenderos",
            tipo=Programa.TipoPrograma.MERENDEROS,
        )
        self.tipo_hogar = TipoDispositivo.objects.create(codigo="HOG", nombre="Hogar", maneja_camas=True)
        self.tipo_refugio = TipoDispositivo.objects.create(codigo="REF", nombre="Refugio", maneja_camas=True)
        self.dispositivo = Dispositivo.objects.create(
            codigo="DIS-001",
            nombre="Hogar Norte",
            tipo=self.tipo_hogar,
            localidad="Resistencia",
            estado=Dispositivo.Estado.ACTIVO,
        )
        self.otro_dispositivo = Dispositivo.objects.create(
            codigo="DIS-002",
            nombre="Refugio Sur",
            tipo=self.tipo_refugio,
            localidad="Barranqueras",
            estado=Dispositivo.Estado.INACTIVO,
        )
        Dispositivo.objects.create(
            codigo="DIS-003",
            nombre="Hogar Este",
            tipo=self.tipo_hogar,
            localidad="Sáenz Peña",
            estado=Dispositivo.Estado.ACTIVO,
        )
        self.merendero = Merendero.objects.create(
            codigo="MER-001",
            nombre="Merendero Norte",
            domicilio="Calle 1",
            responsable_nombre="Ana",
            estado=Merendero.Estado.ACTIVO,
        )
        Merendero.objects.create(
            codigo="MER-002",
            nombre="Merendero Sur",
            domicilio="Calle 2",
            responsable_nombre="Beto",
            estado=Merendero.Estado.ACTIVO,
        )
        self.admin = get_user_model().objects.create_superuser(username="admin-reportes", password="test")
        self.client.force_login(self.admin)

    @staticmethod
    def _csv(response):
        return list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))

    @staticmethod
    def _xlsx(response):
        workbook = load_workbook(BytesIO(response.content), read_only=True)
        try:
            return list(workbook.active.values)
        finally:
            workbook.close()

    def test_padron_dispositivos_csv_y_excel_respetan_tipo_y_estado(self):
        filtros = {"tipo": self.tipo_hogar.pk, "estado": Dispositivo.Estado.ACTIVO, "localidad": "Resistencia"}

        csv_response = self.client.get(reverse("dispositivos:exportar", args=["padron", "csv"]), filtros)
        xlsx_response = self.client.get(reverse("dispositivos:exportar", args=["padron", "xlsx"]), filtros)

        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(xlsx_response.status_code, 200)
        self.assertEqual(csv_response["Content-Type"], "text/csv; charset=utf-8")
        self.assertEqual(
            xlsx_response["Content-Type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        self.assertEqual(self._csv(csv_response)[0], ["Código", "Nombre", "Tipo", "Localidad", "Estado"])
        self.assertEqual(self._csv(csv_response)[1:], [["DIS-001", "Hogar Norte", "Hogar", "Resistencia", "Activo"]])
        self.assertEqual(
            self._xlsx(xlsx_response), [tuple(self._csv(csv_response)[0]), tuple(self._csv(csv_response)[1])]
        )

    def test_ocupacion_y_movimientos_incluyen_los_limites_del_periodo(self):
        cama_ocupada = Cama.objects.create(dispositivo=self.dispositivo, codigo="C-01", estado=Cama.Estado.OCUPADA)
        Cama.objects.create(dispositivo=self.dispositivo, codigo="C-02")
        ciudadano = Ciudadano.objects.create(dni="38000001", nombre="Ana", apellido="Reporte")
        inicio = timezone.make_aware(datetime(2026, 7, 1, 9, 0))
        fin = timezone.make_aware(datetime(2026, 7, 31, 18, 0))
        Admision.objects.create(
            ciudadano=ciudadano,
            dispositivo=self.dispositivo,
            fecha_ingreso=inicio,
            fecha_egreso=fin,
            estado=Admision.Estado.EGRESADO,
        )
        ciudadano_alojado = Ciudadano.objects.create(dni="38000002", nombre="Beto", apellido="Ocupación")
        Admision.objects.create(
            ciudadano=ciudadano_alojado,
            dispositivo=self.dispositivo,
            cama=cama_ocupada,
            fecha_ingreso=timezone.now(),
            estado=Admision.Estado.ALOJADO,
        )

        ocupacion = self.client.get(reverse("dispositivos:exportar", args=["ocupacion", "xlsx"]))
        movimientos = self.client.get(
            reverse("dispositivos:exportar", args=["movimientos", "csv"]),
            {"desde": "2026-07-01", "hasta": "2026-07-31"},
        )

        fila_ocupacion = next(fila for fila in self._xlsx(ocupacion)[1:] if fila[0] == "DIS-001")
        self.assertEqual(fila_ocupacion[3:7], (2, 1, 1, 50))
        filas_movimientos = self._csv(movimientos)
        self.assertEqual(filas_movimientos[1][0:2], ["Ingreso", "01/07/2026"])
        self.assertIn(["Egreso", "31/07/2026"], [fila[0:2] for fila in filas_movimientos[1:]])

    def test_padron_merenderos_con_entregas_csv_y_excel_respeta_periodo_y_estado(self):
        EntregaMercaderia.objects.create(
            merendero=self.merendero,
            fecha=date(2026, 7, 15),
            cantidad_kits=5,
            servicio="Merienda",
        )
        EntregaMercaderia.objects.create(
            merendero=self.merendero,
            fecha=date(2026, 8, 1),
            cantidad_kits=9,
            servicio="Merienda",
        )
        filtros = {
            "estado": Merendero.Estado.ACTIVO,
            "q": "Norte",
            "desde": "2026-07-01",
            "hasta": "2026-07-31",
        }

        csv_response = self.client.get(reverse("merenderos:exportar", args=["csv"]), filtros)
        xlsx_response = self.client.get(reverse("merenderos:exportar", args=["xlsx"]), filtros)

        self.assertEqual(self._csv(csv_response)[1][-3:], ["15/07/2026", "5", "Merienda"])
        self.assertEqual(self._xlsx(xlsx_response)[1][-3:], ("15/07/2026", 5, "Merienda"))

    def test_periodo_dispositivos_muestra_y_exporta_el_mismo_conjunto_inclusivo(self):
        inicio = timezone.make_aware(datetime(2026, 7, 1, 9, 0))
        fin = timezone.make_aware(datetime(2026, 7, 31, 18, 0))
        ciudadano = Ciudadano.objects.create(dni="38000003", nombre="Cora", apellido="Período")
        Admision.objects.create(
            ciudadano=ciudadano,
            dispositivo=self.dispositivo,
            fecha_ingreso=inicio,
            estado=Admision.Estado.ALOJADO,
        )
        Admision.objects.create(
            ciudadano=Ciudadano.objects.create(dni="38000004", nombre="Dino", apellido="Egreso"),
            dispositivo=self.otro_dispositivo,
            fecha_ingreso=timezone.make_aware(datetime(2026, 6, 30, 9, 0)),
            fecha_egreso=fin,
            estado=Admision.Estado.EGRESADO,
        )
        filtros = {"desde": "2026-07-01", "hasta": "2026-07-31"}

        listado = self.client.get(reverse("dispositivos:lista"), filtros)
        padron_csv = self.client.get(reverse("dispositivos:exportar", args=["padron", "csv"]), filtros)
        padron_xlsx = self.client.get(reverse("dispositivos:exportar", args=["padron", "xlsx"]), filtros)
        movimientos_csv = self.client.get(reverse("dispositivos:exportar", args=["movimientos", "csv"]), filtros)
        movimientos_xlsx = self.client.get(reverse("dispositivos:exportar", args=["movimientos", "xlsx"]), filtros)

        visibles = {dispositivo.codigo for dispositivo in listado.context["dispositivos"]}
        self.assertEqual(visibles, {"DIS-001", "DIS-002"})
        self.assertEqual({fila[0] for fila in self._csv(padron_csv)[1:]}, visibles)
        self.assertEqual({fila[0] for fila in self._xlsx(padron_xlsx)[1:]}, visibles)
        self.assertEqual({fila[2] for fila in self._csv(movimientos_csv)[1:]}, visibles)
        self.assertEqual({fila[2] for fila in self._xlsx(movimientos_xlsx)[1:]}, visibles)

    def test_periodo_merenderos_muestra_y_exporta_el_mismo_conjunto_no_anulado(self):
        EntregaMercaderia.objects.create(
            merendero=self.merendero,
            fecha=date(2026, 7, 1),
            cantidad_kits=5,
            servicio="Merienda",
        )
        merendero_anulado = Merendero.objects.create(
            codigo="MER-003",
            nombre="Merendero Anulado",
            domicilio="Calle 3",
            responsable_nombre="Cora",
        )
        EntregaMercaderia.objects.create(
            merendero=merendero_anulado,
            fecha=date(2026, 7, 31),
            cantidad_kits=5,
            servicio="Merienda",
            anulada=True,
        )
        filtros = {"desde": "2026-07-01", "hasta": "2026-07-31"}

        listado = self.client.get(reverse("merenderos:lista"), filtros)
        csv_response = self.client.get(reverse("merenderos:exportar", args=["csv"]), filtros)
        xlsx_response = self.client.get(reverse("merenderos:exportar", args=["xlsx"]), filtros)

        visibles = {merendero.codigo for merendero in listado.context["merenderos"]}
        self.assertEqual(visibles, {"MER-001"})
        self.assertEqual({fila[0] for fila in self._csv(csv_response)[1:]}, visibles)
        self.assertEqual({fila[0] for fila in self._xlsx(xlsx_response)[1:]}, visibles)

    def test_exportaciones_neutralizan_formulas_en_csv_y_excel(self):
        for espacio in ("", "\t"):
            for prefijo in ("=", "+", "-", "@"):
                valor = f"{espacio}{prefijo}2+2"
                self.dispositivo.nombre = valor
                self.dispositivo.save(update_fields=["nombre", "modificado"])

                csv_response = self.client.get(reverse("dispositivos:exportar", args=["padron", "csv"]))
                xlsx_response = self.client.get(reverse("dispositivos:exportar", args=["padron", "xlsx"]))

                self.assertEqual(self._csv(csv_response)[1][1], f"'{valor}")
                self.assertEqual(self._xlsx(xlsx_response)[1][1], f"'{valor}")

    def test_periodo_invalido_devuelve_error_controlado_y_archivo_vacio_es_valido(self):
        invalido = self.client.get(
            reverse("dispositivos:exportar", args=["movimientos", "csv"]),
            {"desde": "2026-08-01", "hasta": "2026-07-01"},
        )
        vacio = self.client.get(
            reverse("dispositivos:exportar", args=["movimientos", "csv"]),
            {"desde": "2025-01-01", "hasta": "2025-01-31"},
        )

        self.assertEqual(invalido.status_code, 400)
        self.assertEqual(len(self._csv(vacio)), 1)

    def test_consulta_solo_exporta_su_alcance_y_no_puede_acceder_a_merenderos(self):
        consulta = get_user_model().objects.create_user(username="consulta-reportes", password="test")
        rol = Group.objects.create(name="Consulta Dispositivos Reportes")
        RolMeta.objects.create(
            grupo=rol,
            categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.dispositivos_programa,
            activo=True,
        )
        rol.permissions.add(permiso("dispositivo.ver"))
        consulta.groups.add(rol)
        AsignacionDispositivo.objects.create(dispositivo=self.dispositivo, rol=rol)
        cache.clear()
        self.client.force_login(consulta)

        dispositivos = self.client.get(reverse("dispositivos:exportar", args=["padron", "csv"]))
        merenderos = self.client.get(reverse("merenderos:exportar", args=["csv"]))

        self.assertEqual(self._csv(dispositivos)[1:], [["DIS-001", "Hogar Norte", "Hogar", "Resistencia", "Activo"]])
        self.assertEqual(merenderos.status_code, 403)

    def test_exportacion_bloquea_usuario_inactivo_y_rol_desactivado(self):
        usuario_inactivo = get_user_model().objects.create_user(
            username="consulta-inactiva",
            password="test",
            is_active=False,
        )
        self.client.force_login(usuario_inactivo)
        self.assertEqual(self.client.get(reverse("dispositivos:exportar", args=["padron", "csv"])).status_code, 302)

        usuario = get_user_model().objects.create_user(username="consulta-rol-inactivo", password="test")
        rol = Group.objects.create(name="Consulta inactiva Reportes")
        RolMeta.objects.create(
            grupo=rol,
            categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.dispositivos_programa,
            activo=False,
        )
        rol.permissions.add(permiso("dispositivo.ver"))
        usuario.groups.add(rol)
        AsignacionDispositivo.objects.create(dispositivo=self.dispositivo, rol=rol)
        cache.clear()
        self.client.force_login(usuario)

        self.assertEqual(self.client.get(reverse("dispositivos:exportar", args=["padron", "csv"])).status_code, 403)
