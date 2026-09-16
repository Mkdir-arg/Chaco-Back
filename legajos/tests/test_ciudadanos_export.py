from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from legajos.models import Ciudadano
from legajos.selectors.ciudadanos import get_ciudadanos_queryset


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
