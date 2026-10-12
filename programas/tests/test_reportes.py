import csv
from datetime import date
from io import BytesIO, StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from openpyxl import load_workbook

from core import rbac
from legajos.models import Ciudadano
from programas.models import (
    AsignacionDispositivo,
    Convocatoria,
    Dispositivo,
    EntregaMercaderia,
    Formulario,
    ListaEspera,
    Merendero,
    Programa,
    Relevamiento,
    Segmento,
    TipoDispositivo,
)
from programas.services.exportacion_reportes import celda_segura, respuesta_libro, respuesta_reporte
from programas.services.reportes import Reporte
from users.models import Capacidad, RolMeta


def permiso(codigo):
    content_type = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=content_type)


class CeldaSeguraTests(SimpleTestCase):
    """RED-70: `celda_segura` limpia caracteres de control **antes** de prefijar.

    La línea `ILLEGAL_CHARACTERS_RE.sub("", valor)` parece redundante al lado
    del prefijo anti-fórmula y sobrevivió a la prueba de mutación (M49): ningún
    test la ejercía. Hace dos cosas, y las dos importan:

    1. **Sin la limpieza, `libro.save()` lanza `IllegalCharacterError`** y la
       descarga entera da 500 por una sola fila entre miles —un texto pegado
       desde Word o un PDF alcanza—.
    2. **El orden no es intercambiable:** limpiar después de prefijar deja que
       un `\\x0b` adelante del `=` esconda la fórmula del chequeo, que es un
       bypass real de la inyección CSV/XLSX que SEC-20 va a extender a cinco
       exports más.
    """

    #: Un verticaltab y un bell en el medio de un nombre, como los deja un copy&paste.
    CON_CONTROLES = "Mart\x0bin\x07"
    REPORTE = Reporte(encabezados=("Nombre",), filas=((CON_CONTROLES,),))

    def _primera_celda(self, respuesta, hoja=0):
        libro = load_workbook(BytesIO(respuesta.content))
        return libro[libro.sheetnames[hoja]].cell(row=1, column=1).value

    def test_celda_segura_limpia_y_prefija_a_la_vez(self):
        self.assertEqual(celda_segura(self.CON_CONTROLES), "Martin")
        self.assertEqual(
            celda_segura("\x0b=1+1"),
            "'=1+1",
            "Se invirtió el orden: el carácter de control impide detectar la fórmula (bypass de SEC-20).",
        )
        # Los cuatro arranques de fórmula se siguen prefijando sin controles de por medio.
        for inicio in ("=", "+", "-", "@"):
            with self.subTest(inicio=inicio):
                self.assertEqual(celda_segura(f"{inicio}cmd"), f"'{inicio}cmd")

    def test_un_caracter_de_control_no_rompe_el_xlsx(self):
        respuesta = respuesta_reporte(self.REPORTE, "xlsx", "reporte")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self._primera_celda(respuesta), "Nombre")
        libro = load_workbook(BytesIO(respuesta.content))
        self.assertEqual(libro["Reporte"].cell(row=2, column=1).value, "Martin")

    def test_un_caracter_de_control_no_rompe_el_libro_de_varias_hojas(self):
        respuesta = respuesta_libro([("Personas", self.REPORTE)], "libro")

        self.assertEqual(respuesta.status_code, 200)
        libro = load_workbook(BytesIO(respuesta.content))
        self.assertEqual(libro["Personas"].cell(row=2, column=1).value, "Martin")

    def test_el_alcance_del_libro_tambien_pasa_por_celda_segura(self):
        """El alcance sale de los filtros que eligió quien descarga: es texto de
        usuario y también se limpia. La fórmula no necesita prefijo acá porque
        la celda arranca con el literal «Alcance: », no con el `=`."""
        respuesta = respuesta_libro(
            [("Personas", self.REPORTE)],
            "libro",
            alcance="Conv\x0b2026 =cmd|'/C calc'!A0",
        )

        libro = load_workbook(BytesIO(respuesta.content))
        self.assertEqual(libro["Personas"].cell(row=1, column=1).value, "Alcance: Conv2026 =cmd|'/C calc'!A0")

    def test_el_csv_tambien_sale_limpio(self):
        respuesta = respuesta_reporte(self.REPORTE, "csv", "reporte")

        self.assertEqual(respuesta.status_code, 200)
        filas = list(csv.reader(respuesta.content.decode("utf-8-sig").splitlines()))
        self.assertEqual(filas[1], ["Martin"])


class ReportesExportablesTests(TestCase):
    def setUp(self):
        self.dispositivos_programa, _ = Programa.objects.get_or_create(
            codigo=Programa.TipoPrograma.DISPOSITIVOS,
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        self.merenderos_programa, _ = Programa.objects.get_or_create(
            codigo=Programa.TipoPrograma.MERENDEROS,
            defaults={"nombre": "Merenderos", "tipo": Programa.TipoPrograma.MERENDEROS},
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
        """El período quedó solo en Merenderos: el de Dispositivos acotaba por estadía."""
        invalido = self.client.get(
            reverse("merenderos:exportar", args=["csv"]),
            {"desde": "2026-08-01", "hasta": "2026-07-01"},
        )
        vacio = self.client.get(
            reverse("merenderos:exportar", args=["csv"]),
            {"desde": "2025-01-01", "hasta": "2025-01-31"},
        )

        self.assertEqual(invalido.status_code, 400)
        self.assertEqual(len(self._csv(vacio)), 1)

    def test_el_reporte_de_ocupacion_dejo_de_existir(self):
        """Lo repone el MVP v2 sobre `Plaza` y `Estadia`; hasta entonces no es un reporte."""
        for reporte in ("ocupacion", "movimientos"):
            with self.subTest(reporte=reporte):
                respuesta = self.client.get(reverse("dispositivos:exportar", args=[reporte, "csv"]))
                self.assertEqual(respuesta.status_code, 400)

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


class ExportsDeConvocatoriaTests(TestCase):
    """SEC-20: los tres CSV legacy de la convocatoria escribían el valor crudo.

    `celda_segura` existía y la usaban los reportes nuevos; estos tres —beneficiarios,
    relevamientos y lista de espera— se arman a mano con `csv.writer` y quedaron
    afuera. El dato peligroso es el que carga la persona desde el link público o la
    app de campo: nombre y apellido.
    """

    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(username="admin-exports", password="test")
        self.client.force_login(self.admin)
        self.segmento = Segmento.objects.create(nombre="Segmento export", cupo_maximo=10)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Convocatoria export",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        territorial = get_user_model().objects.create_user(username="terri-export", password="test")
        territorial.first_name = "=1+1"
        territorial.save(update_fields=["first_name"])
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=territorial,
            fecha_asignada=date(2026, 6, 1),
            fecha_hasta=date(2026, 6, 30),
            zona="=Zona(1)",
        )
        ciudadano = Ciudadano.objects.create(dni="31999888", nombre="=1+1", apellido="Padrón")
        self.aprobado = Formulario.objects.create(
            relevamiento=self.relevamiento,
            ciudadano=ciudadano,
            estado=Formulario.Estado.APROBADO,
            celular="3624000000",
        )
        en_espera = Formulario.objects.create(
            relevamiento=self.relevamiento,
            ciudadano=ciudadano,
            estado=Formulario.Estado.ENVIADO,
            celular="3624000000",
        )
        ListaEspera.objects.create(formulario=en_espera, segmento=self.segmento, posicion=1)

    @staticmethod
    def _csv(response):
        return list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))

    def test_el_export_de_beneficiarios_neutraliza_la_formula(self):
        respuesta = self.client.get(reverse("becas:convocatoria_export_beneficiarios", args=[self.convocatoria.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self._csv(respuesta)[1][0], "'=1+1 Padrón")

    def test_el_export_de_relevamientos_neutraliza_la_formula(self):
        respuesta = self.client.get(reverse("becas:convocatoria_export_relevamientos", args=[self.convocatoria.pk]))

        self.assertEqual(respuesta.status_code, 200)
        fila = self._csv(respuesta)[1]
        self.assertEqual(fila[1], "'=1+1")
        self.assertEqual(fila[4], "'=Zona(1)")

    def test_el_export_de_lista_de_espera_neutraliza_la_formula(self):
        respuesta = self.client.get(reverse("becas:convocatoria_export_lista_espera", args=[self.convocatoria.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self._csv(respuesta)[1][1], "'=1+1 Padrón")
