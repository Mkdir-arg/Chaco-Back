from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from core import rbac
from legajos.models import Ciudadano
from legajos.selectors.ciudadanos import get_ciudadanos_queryset
from users.models import Capacidad, RolMeta


def _usuario_con(*codigos, username):
    """Usuario de backoffice con exactamente esas capacidades."""
    usuario = User.objects.create_user(username, password="Clave-Seg-2026x")
    grupo = Group.objects.create(name=f"Rol {username}")
    RolMeta.objects.create(grupo=grupo, categoria=rbac.CATEGORIA_BACKOFFICE, activo=True)
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(content_type=ct, codename=rbac.codename_de(codigo)))
    usuario.groups.add(grupo)
    return usuario


class CiudadanosExportarCsvTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("root", "root@example.com", "x")
        self.client.force_login(self.user)

    def _filas(self, response):
        contenido = response.content.decode("utf-8-sig")
        return [linea.split(",") for linea in contenido.splitlines() if linea]

    def test_exporta_la_columna_sexo_con_la_etiqueta_del_ciudadano(self):
        Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Alvarez", genero=Ciudadano.Genero.FEMENINO)
        Ciudadano.objects.create(dni="30111223", nombre="Beto", apellido="Benitez", genero="")

        response = self.client.get(reverse("legajos:ciudadanos_exportar_csv"))

        self.assertEqual(response.status_code, 200)
        filas = self._filas(response)
        self.assertEqual(filas[0][:4], ["DNI", "Apellido", "Nombre", "Sexo"])
        self.assertEqual(filas[1][:4], ["30111222", "Alvarez", "Ana", "Femenino"])
        self.assertEqual(filas[2][:4], ["30111223", "Benitez", "Beto", ""])

    def test_una_formula_en_el_apellido_sale_neutralizada(self):
        """SEC-20: el apellido lo carga la persona en el link público o la app.

        Sin el prefijo, abrir el CSV en Excel ejecuta la fórmula: `=HYPERLINK` arma un
        pedido a un servidor ajeno con el DNI de la fila de al lado.
        """
        Ciudadano.objects.create(dni="30111999", nombre="Eva", apellido="=1+1")

        response = self.client.get(reverse("legajos:ciudadanos_exportar_csv"))

        filas = self._filas(response)
        self.assertEqual(filas[1][:3], ["30111999", "'=1+1", "Eva"])

    def test_el_sexo_viaja_en_la_misma_consulta_que_el_listado(self):
        """``genero`` está en el ``only()``: leerlo no dispara una consulta por fila."""
        for indice in range(3):
            Ciudadano.objects.create(
                dni=f"3122200{indice}",
                nombre=f"Ciudadano {indice}",
                apellido="Consultas",
                genero=Ciudadano.Genero.MASCULINO,
            )

        with self.assertNumQueries(1):
            [ciudadano.get_genero_display() for ciudadano in get_ciudadanos_queryset("")]


class ExportarCiudadanosCapacidadTests(TestCase):
    """SEC-20 / D-20: bajarse el padrón completo es su propia capacidad.

    Hasta este PR, cualquier cuenta con `ciudadano.ver` se descargaba las ~100.000
    personas del padrón —DNI incluido— sin límite y sin dejar rastro, y no había forma
    de impedírselo a un rol sin impedirle también ver un legajo.

    D-20 (PM, 08-oct-2026): la capacidad se siembra a quien ya tiene `ciudadano.ver`,
    así que el día del deploy nadie pierde la exportación. Lo que cambia es que ahora
    es **destildable** rol por rol desde el ABM, que es lo que estos tests fijan: con
    `ciudadano.ver` y sin `ciudadano.exportar` no hay descarga ni botón.
    """

    @classmethod
    def setUpTestData(cls):
        Ciudadano.objects.create(dni="33444555", nombre="Juana", apellido="Padrón")

    def test_con_ver_pero_sin_exportar_no_descarga(self):
        self.client.force_login(_usuario_con("ciudadano.ver", username="solo-ve"))

        response = self.client.get(reverse("legajos:ciudadanos_exportar_csv"))

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("text/csv", response.get("Content-Type", ""))

    def test_con_la_capacidad_descarga(self):
        self.client.force_login(_usuario_con("ciudadano.ver", "ciudadano.exportar", username="exporta"))

        response = self.client.get(reverse("legajos:ciudadanos_exportar_csv"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("33444555", response.content.decode("utf-8-sig"))

    def test_un_anonimo_va_al_login(self):
        response = self.client.get(reverse("legajos:ciudadanos_exportar_csv"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("next=", response["Location"])

    def test_el_boton_no_se_dibuja_sin_la_capacidad(self):
        """La UI sigue a la capacidad (R-19): un botón que da 302 es peor que no estar."""
        url = reverse("legajos:ciudadanos_exportar_csv")
        self.client.force_login(_usuario_con("ciudadano.ver", username="ve-listado"))

        sin_capacidad = self.client.get(reverse("legajos:ciudadanos"))

        self.client.force_login(_usuario_con("ciudadano.ver", "ciudadano.exportar", username="exporta-listado"))
        con_capacidad = self.client.get(reverse("legajos:ciudadanos"))

        self.assertNotContains(sin_capacidad, url)
        self.assertContains(con_capacidad, url)

    def test_el_superusuario_sigue_pudiendo(self):
        self.client.force_login(User.objects.create_superuser("root-exp", "root@example.com", "x"))

        self.assertEqual(self.client.get(reverse("legajos:ciudadanos_exportar_csv")).status_code, 200)
