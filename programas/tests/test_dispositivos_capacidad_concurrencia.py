"""Dos POST simultáneos de las pantallas de C5 contra MySQL/MariaDB de verdad."""

import threading

from django.contrib.auth.models import User
from django.db import connections
from django.test import Client, TransactionTestCase, override_settings, tag
from django.urls import reverse

from core.tests.test_motor_real import MotorRealMixin
from programas.models import Dispositivo, Plaza, Programa, Sector, TipoDispositivo


@tag("mysql")
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class CapacidadConcurrenteTests(MotorRealMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        # Un usuario por hilo: BackofficeSingleSessionMiddleware deja una sola sesión por usuario y
        # desloguea (302) a la que llega segunda; con un único usuario el 302 dependía de la carrera.
        self.usuarios = [
            User.objects.create_superuser(username=f"capacidad_concurrente_{i}", password="x") for i in (1, 2)
        ]
        tipo = TipoDispositivo.objects.create(codigo="C5", nombre="Albergue C5", plaza_obligatoria_al_ingresar=True)
        self.dispositivo = Dispositivo.objects.create(
            tipo=tipo,
            codigo="C5",
            nombre="Institución C5",
            estado=Dispositivo.Estado.ACTIVO,
        )
        self.sectores = [Sector.objects.create(dispositivo=self.dispositivo, nombre=f"Pabellón {i}") for i in (1, 2)]
        self.plazas = [Plaza.objects.create(sector=s, codigo=f"P{i}") for i, s in enumerate(self.sectores)]

    def _post_simultaneos(self, pedidos):
        barrera = threading.Barrier(2, timeout=15)
        respuestas, errores = [], []

        def post(usuario, url, datos):
            try:
                client = Client()
                client.force_login(User.objects.get(pk=usuario.pk))
                barrera.wait()
                respuestas.append(client.post(url, datos, HTTP_X_REQUESTED_WITH="XMLHttpRequest"))
            except Exception as error:
                errores.append(error)
                barrera.abort()
            finally:
                connections.close_all()

        hilos = [
            threading.Thread(target=post, args=(usuario, *pedido)) for usuario, pedido in zip(self.usuarios, pedidos)
        ]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=30)
        self.assertFalse(any(hilo.is_alive() for hilo in hilos), "Un POST quedó bloqueado")
        self.assertEqual([repr(error) for error in errores], [])
        return sorted(r.status_code for r in respuestas)

    def _lote(self, sector, cantidad):
        return (
            reverse("dispositivos:plazas_agregar", args=[self.dispositivo.pk]),
            {"sector": sector.pk, "cantidad": cantidad, "tipo": Plaza.Tipo.CAMA, "prefijo": "B-"},
        )

    def _editar(self, plaza, codigo):
        return (
            reverse("dispositivos:plaza_editar", args=[self.dispositivo.pk, plaza.pk]),
            {"codigo": codigo, "tipo": Plaza.Tipo.CAMA},
        )

    def _codigos_de(self, sector):
        return sorted(Plaza.objects.filter(sector=sector, codigo__startswith="B-").values_list("codigo", flat=True))

    def test_dos_lotes_simultaneos_en_sectores_distintos_numeran_cada_uno_desde_1(self):
        """Cambio 430: la numeración es por sector, así que no compiten por el mismo número."""

        estados = self._post_simultaneos([self._lote(sector, 2) for sector in self.sectores])

        self.assertEqual(estados, [200, 200])
        for sector in self.sectores:
            self.assertEqual(self._codigos_de(sector), ["B-01", "B-02"])

    def test_dos_lotes_simultaneos_en_el_mismo_sector_no_duplican_numeros(self):
        estados = self._post_simultaneos([self._lote(self.sectores[0], 2) for _ in self.usuarios])

        self.assertEqual(estados, [200, 200])
        self.assertEqual(self._codigos_de(self.sectores[0]), ["B-01", "B-02", "B-03", "B-04"])
        self.assertEqual(self._codigos_de(self.sectores[1]), [])

    def test_dos_ediciones_simultaneas_al_mismo_codigo_en_sectores_distintos_guardan_las_dos(self):
        """El código ya no es único en el dispositivo: dos sectores pueden tener «B-01»."""

        estados = self._post_simultaneos([self._editar(plaza, "B-01") for plaza in self.plazas])

        self.assertEqual(estados, [200, 200])
        for sector in self.sectores:
            self.assertEqual(self._codigos_de(sector), ["B-01"])

    def test_dos_ediciones_simultaneas_al_mismo_codigo_en_el_mismo_sector_guardan_una_sola(self):
        otra = Plaza.objects.create(sector=self.sectores[0], codigo="P9")

        estados = self._post_simultaneos([self._editar(self.plazas[0], "B-01"), self._editar(otra, "B-01")])

        self.assertEqual(estados, [200, 400])
        self.assertEqual(self._codigos_de(self.sectores[0]), ["B-01"])

    def test_un_lote_y_una_edicion_simultaneos_en_el_mismo_sector_comparten_el_candado(self):
        estados = self._post_simultaneos([self._lote(self.sectores[0], 1), self._editar(self.plazas[0], "B-01")])

        # Gana el lote (B-01) y la edición choca, o gana la edición y el lote sigue en B-02.
        self.assertIn(estados, ([200, 200], [200, 400]))
        codigos = list(Plaza.objects.filter(sector=self.sectores[0]).values_list("codigo", flat=True))
        self.assertEqual(len(codigos), len(set(codigos)))
        self.assertEqual(Plaza.objects.count(), 3)
