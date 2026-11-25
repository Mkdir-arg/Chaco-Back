"""«Plazas y estadías» en la API de la app (Cambio 596): perfil, edificios, mapa de camas y estadías.

Fija el contrato de claves, el alcance (un edificio ajeno es 404 igual que uno inexistente; sin ``ciudadano.ver`` no
se ve a la persona; sin ``dispositivo.ver`` el perfil dice ``plazas: false``) y el presupuesto de consultas del mapa
(constante respecto de la cantidad de camas).
"""

from datetime import timedelta

from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import (
    Edificio,
    Estadia,
    IntegranteGrupo,
    MiembroEquipoDispositivo,
    Plaza,
    ReservaPlaza,
    Sector,
)
from programas.tests.base_emergencia_api import (
    CLAVES_PERFIL,
    URL_PERFIL,
    BaseApiEmergencia,
    _url,
)

VER = "dispositivo.ver"
ADMITIR = "dispositivo.admitir"
EGRESAR = "dispositivo.egresar"
EDITAR = "dispositivo.editar"
VER_CIUDADANO = "ciudadano.ver"

CLAVES_ITEM_EDIFICIO = ["dispositivo", "edificio", "resumen"]
CLAVES_RESUMEN = ["fuera_servicio", "libres", "ocupadas", "prestadas", "reservadas", "total"]
CLAVES_MAPA = ["dispositivo", "edificio", "puede", "resumen", "sectores"]
CLAVES_PUEDE = ["admitir", "editar", "egresar", "ver_personas"]
CLAVES_SECTOR = ["id", "nombre", "plazas", "resumen", "tipo"]
CLAVES_PLAZA = [
    "acciones",
    "bloqueo",
    "codigo",
    "desde",
    "estadia_id",
    "estado",
    "hasta",
    "id",
    "persona",
    "reserva_id",
    "tipo",
]
CLAVES_PAGINA = ["count", "next", "previous", "results"]
CLAVES_ESTADIA = [
    "acciones",
    "emergencia",
    "estado",
    "fecha_egreso",
    "fecha_ingreso",
    "id",
    "origen",
    "persona",
    "plaza",
    "sector",
]


class BasePlazasApp(BaseApiEmergencia):
    """Una institución con dos edificios (A: 6 camas en 2 sectores; B: 2 camas) y su guardia."""

    def setUp(self):
        super().setUp()
        self.sede = self._dispositivo("Sede Central")
        self.edificio_a = self._edificio(
            "EDI-A", "Edificio Alfa", calle="Calle 1", numero="100", localidad="Resistencia"
        )
        self.edificio_b = self._edificio("EDI-B", "Edificio Beta")
        self.sector_a1 = self._sector(self.edificio_a, "Pabellón 1", 4)
        self.sector_a2 = self._sector(self.edificio_a, "Pabellón 2", 2)
        self.sector_b = self._sector(self.edificio_b, "Único", 2)
        self.ajena = self._dispositivo("Otra institución")
        self.edificio_ajeno = self._edificio("EDI-X", "Edificio Ajeno")
        self._sector(self.edificio_ajeno, "General", 2, dispositivo=self.ajena)
        self.jefa = self._guardia("jefa", [VER, ADMITIR, EGRESAR, EDITAR, VER_CIUDADANO], [self.sede])
        self._n = 0

    def _edificio(self, codigo, nombre, dispositivo=None, **datos):
        edificio = Edificio.objects.create(codigo=codigo, nombre=nombre, **datos)
        edificio.dispositivos.add(dispositivo or (self.ajena if codigo == "EDI-X" else self.sede))
        return edificio

    def _sector(self, edificio, nombre, camas, dispositivo=None):
        sector = Sector.objects.create(
            dispositivo=dispositivo or self.sede, edificio=edificio, nombre=nombre, capacidad=camas
        )
        Plaza.objects.bulk_create([Plaza(sector=sector, codigo=f"S{sector.pk}-{n:03d}") for n in range(1, camas + 1)])
        return sector

    def _plaza(self, sector, indice=0):
        return Plaza.objects.filter(sector=sector).order_by("codigo")[indice]

    def _persona(self, apellido="Benítez", nombre="Rosa"):
        self._n += 1
        return Ciudadano.objects.create(dni=str(30000000 + self._n), apellido=apellido, nombre=nombre)

    def _alojar(self, plaza, persona=None, dispositivo=None, **datos):
        persona = persona or self._persona()
        return Estadia.objects.create(
            ciudadano=persona,
            dispositivo=dispositivo or self.sede,
            plaza=plaza,
            fecha_ingreso=datos.pop("fecha_ingreso", timezone.now() - timedelta(days=1)),
            clave_alojamiento=Estadia.clave_para(persona),
            **datos,
        )

    def _egresada(self, plaza, persona=None):
        persona = persona or self._persona("Gómez", "Ana")
        ingreso = timezone.now() - timedelta(days=5)
        return Estadia.objects.create(
            ciudadano=persona,
            dispositivo=self.sede,
            plaza=plaza,
            fecha_ingreso=ingreso,
            fecha_egreso=ingreso + timedelta(days=2),
            estado=Estadia.Estado.EGRESADA,
        )

    def _reservar(self, plaza, tipo=ReservaPlaza.Tipo.RESERVA, persona=None):
        return ReservaPlaza.objects.create(
            plaza=plaza,
            ciudadano=persona or self._persona("Reyes", "Luz"),
            tipo=tipo,
            desde=timezone.now() - timedelta(hours=1),
            hasta=timezone.now() + timedelta(days=1),
        )

    def _get(self, usuario, ruta, *args, **consulta):
        return self._como(usuario).get(_url(ruta, *args), consulta)

    def _mapa(self, usuario, dispositivo=None, edificio=None):
        return self._get(
            usuario,
            "edificio-mapa",
            (dispositivo or self.sede).pk,
            (edificio or self.edificio_a).pk,
        )

    def _plazas_del_mapa(self, cuerpo):
        return {plaza["codigo"]: plaza for sector in cuerpo["sectores"] for plaza in sector["plazas"]}


class PerfilConPlazasTests(BasePlazasApp):
    def test_el_perfil_suma_plazas_y_conserva_las_demas_claves(self):
        respuesta = self._como(self.jefa).get(URL_PERFIL)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(sorted(respuesta.json()), CLAVES_PERFIL)
        self.assertTrue(respuesta.json()["plazas"])
        self.assertTrue(respuesta.json()["llegadas"])

    def test_sin_dispositivo_ver_en_ningun_edificio_plazas_es_false(self):
        """La guardia de ``setUp`` admite pero no ve (``dispositivo.ver``): abre el módulo y no abre «Plazas»."""

        respuesta = self._como(self.guardia).get(URL_PERFIL)

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.json()["plazas"])

    def test_el_agente_territorial_no_ve_plazas(self):
        self.assertFalse(self._como(self.agente).get(URL_PERFIL).json()["plazas"])

    def test_con_alcance_edificios_vacio_plazas_es_false(self):
        """Del Equipo con alcance «Edificios» pero sin ninguno cargado: no ve nada, jamás cae a toda la institución."""

        limitada = self._guardia("limitada", [VER, ADMITIR], [self.sede])
        MiembroEquipoDispositivo.objects.filter(usuario=limitada).update(
            alcance=MiembroEquipoDispositivo.Alcance.EDIFICIOS
        )

        self.assertFalse(self._como(limitada).get(URL_PERFIL).json()["plazas"])


class EdificiosDeLaAppTests(BasePlazasApp):
    def test_lista_un_item_por_par_en_alcance_con_el_contrato(self):
        self._alojar(self._plaza(self.sector_a1, 0))
        self._reservar(self._plaza(self.sector_a1, 1))
        self._reservar(self._plaza(self.sector_a1, 2), ReservaPlaza.Tipo.PRESTAMO)

        respuesta = self._get(self.jefa, "edificios")

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual([item["edificio"]["nombre"] for item in cuerpo], ["Edificio Alfa", "Edificio Beta"])
        alfa = cuerpo[0]
        self.assertEqual(sorted(alfa), CLAVES_ITEM_EDIFICIO)
        self.assertEqual(alfa["dispositivo"], {"id": self.sede.pk, "nombre": "Sede Central"})
        self.assertEqual(
            alfa["edificio"],
            {"id": self.edificio_a.pk, "nombre": "Edificio Alfa", "direccion": "Calle 1 100, Resistencia, Chaco"},
        )
        self.assertEqual(sorted(alfa["resumen"]), CLAVES_RESUMEN)
        self.assertEqual(
            alfa["resumen"],
            {"total": 6, "libres": 3, "ocupadas": 1, "reservadas": 1, "prestadas": 1, "fuera_servicio": 0},
        )
        self.assertEqual(cuerpo[1]["resumen"]["total"], 2)

    def test_no_lista_lo_de_otra_institucion_fuera_del_alcance(self):
        respuesta = self._get(self.jefa, "edificios")

        self.assertNotIn(self.edificio_ajeno.pk, [item["edificio"]["id"] for item in respuesta.json()])

    def test_con_alcance_edificios_solo_lista_los_suyos(self):
        limitada = self._guardia("limitada", [VER, ADMITIR], [self.sede])
        fila = MiembroEquipoDispositivo.objects.get(usuario=limitada)
        fila.alcance = MiembroEquipoDispositivo.Alcance.EDIFICIOS
        fila.save()
        fila.edificios.add(self.edificio_b)

        cuerpo = self._get(limitada, "edificios").json()

        self.assertEqual([item["edificio"]["id"] for item in cuerpo], [self.edificio_b.pk])
        self.assertEqual(cuerpo[0]["resumen"]["total"], 2)

    def test_sin_edificios_en_alcance_es_lista_vacia(self):
        self.assertEqual(self._get(self.guardia, "edificios").json(), [])


class MapaDelEdificioTests(BasePlazasApp):
    def test_el_mapa_tiene_el_contrato_de_claves(self):
        ocupada = self._alojar(self._plaza(self.sector_a1, 0))
        reserva = self._reservar(self._plaza(self.sector_a1, 1))

        respuesta = self._mapa(self.jefa)

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        cuerpo = respuesta.json()
        self.assertEqual(sorted(cuerpo), CLAVES_MAPA)
        self.assertEqual(cuerpo["dispositivo"], {"id": self.sede.pk, "nombre": "Sede Central", "estado": "ACTIVO"})
        self.assertEqual(cuerpo["edificio"], {"id": self.edificio_a.pk, "nombre": "Edificio Alfa"})
        self.assertEqual(sorted(cuerpo["resumen"]), CLAVES_RESUMEN)
        self.assertEqual(cuerpo["puede"], {"egresar": True, "admitir": True, "editar": True, "ver_personas": True})
        self.assertEqual(sorted(cuerpo["puede"]), CLAVES_PUEDE)
        self.assertEqual([sector["nombre"] for sector in cuerpo["sectores"]], ["Pabellón 1", "Pabellón 2"])
        sector = cuerpo["sectores"][0]
        self.assertEqual(sorted(sector), CLAVES_SECTOR)
        self.assertEqual(sorted(sector["resumen"]), CLAVES_RESUMEN)
        self.assertEqual(len(sector["plazas"]), 4)
        for plaza in sector["plazas"]:
            self.assertEqual(sorted(plaza), CLAVES_PLAZA)
        plazas = self._plazas_del_mapa(cuerpo)
        self.assertEqual(plazas[self._plaza(self.sector_a1, 0).codigo]["estadia_id"], ocupada.pk)
        self.assertEqual(plazas[self._plaza(self.sector_a1, 1).codigo]["reserva_id"], reserva.pk)

    def test_cada_estado_con_su_persona_fechas_y_acciones(self):
        p = [self._plaza(self.sector_a1, i) for i in range(4)]
        estadia = self._alojar(p[0], self._persona("Benítez", "Rosa"))
        self._reservar(p[1], persona=self._persona("Reyes", "Luz"))
        self._reservar(p[2], ReservaPlaza.Tipo.PRESTAMO, persona=self._persona("Paz", "Juan"))
        Plaza.objects.filter(pk=p[3].pk).update(estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="Goteras")

        plazas = self._plazas_del_mapa(self._mapa(self.jefa).json())

        ocupada, reservada, prestada, fuera, libre = (
            plazas[p[0].codigo],
            plazas[p[1].codigo],
            plazas[p[2].codigo],
            plazas[p[3].codigo],
            plazas[self._plaza(self.sector_a2, 0).codigo],
        )
        self.assertEqual(ocupada["estado"], "ocupada")
        self.assertEqual(ocupada["persona"], {"nombre": "Benítez, Rosa", "dni": estadia.ciudadano.dni})
        self.assertIsNotNone(ocupada["desde"])
        self.assertIsNone(ocupada["hasta"])
        self.assertEqual(ocupada["acciones"], ["egresar", "reubicar", "fuera_servicio"])
        self.assertTrue(ocupada["bloqueo"])
        self.assertEqual(reservada["estado"], "reservada")
        self.assertEqual(reservada["persona"]["nombre"], "Reyes, Luz")
        self.assertIsNotNone(reservada["hasta"])
        self.assertEqual(reservada["acciones"], ["liberar"])
        self.assertEqual(prestada["estado"], "prestada")
        self.assertEqual(fuera["estado"], "fuera_servicio")
        self.assertIsNone(fuera["persona"])
        self.assertEqual(fuera["acciones"], ["volver"])
        self.assertEqual(libre["estado"], "disponible")
        self.assertIsNone(libre["persona"])
        self.assertEqual(libre["acciones"], ["reservar", "prestar", "fuera_servicio"])
        self.assertEqual(libre["bloqueo"], "")
        for plaza in plazas.values():
            self.assertNotIn("ingresar", plaza["acciones"])
            self.assertNotIn("baja", plaza["acciones"])

    def test_sin_ciudadano_ver_no_se_ve_a_la_persona_ni_el_dni(self):
        self._alojar(self._plaza(self.sector_a1, 0))
        self._reservar(self._plaza(self.sector_a1, 1))
        operador = self._guardia("sin_ciudadano", [VER, ADMITIR, EGRESAR], [self.sede])

        cuerpo = self._mapa(operador).json()

        self.assertFalse(cuerpo["puede"]["ver_personas"])
        plazas = self._plazas_del_mapa(cuerpo)
        self.assertIsNone(plazas[self._plaza(self.sector_a1, 0).codigo]["persona"])
        self.assertIsNone(plazas[self._plaza(self.sector_a1, 1).codigo]["persona"])
        self.assertNotIn("30000001", str(cuerpo))
        # Sin `ciudadano.ver` quedan egresar y reubicar; no se puede reservar ni prestar (buscan por DNI).
        self.assertEqual(plazas[self._plaza(self.sector_a1, 0).codigo]["acciones"], ["egresar", "reubicar"])
        self.assertEqual(plazas[self._plaza(self.sector_a2, 0).codigo]["acciones"], [])

    def test_sin_egresar_ni_editar_el_mapa_lo_dice_y_no_ofrece_esas_acciones(self):
        self._alojar(self._plaza(self.sector_a1, 0))
        admite = self._guardia("solo_admite", [VER, ADMITIR, VER_CIUDADANO], [self.sede])

        cuerpo = self._mapa(admite).json()

        self.assertEqual(cuerpo["puede"], {"egresar": False, "admitir": True, "editar": False, "ver_personas": True})
        plazas = self._plazas_del_mapa(cuerpo)
        self.assertEqual(plazas[self._plaza(self.sector_a1, 0).codigo]["acciones"], ["reubicar"])
        self.assertEqual(plazas[self._plaza(self.sector_a2, 0).codigo]["acciones"], ["reservar", "prestar"])

    def test_edificio_de_otro_dispositivo_o_inexistente_es_404(self):
        for dispositivo, edificio in (
            (self.sede, self.edificio_ajeno),  # no está vinculado a la sede
            (self.ajena, self.edificio_ajeno),  # la institución es de otro Equipo
            (self.ajena, self.edificio_a),
        ):
            with self.subTest(dispositivo=dispositivo.nombre, edificio=edificio.nombre):
                self.assertEqual(self._mapa(self.jefa, dispositivo, edificio).status_code, 404)
        inexistente = self._como(self.jefa).get(_url("edificio-mapa", self.sede.pk, 999999))
        self.assertEqual(inexistente.status_code, 404)
        self.assertEqual(inexistente.json(), self._mapa(self.jefa, self.ajena, self.edificio_ajeno).json())

    def test_con_alcance_edificios_el_otro_edificio_es_404(self):
        limitada = self._guardia("limitada", [VER, ADMITIR], [self.sede])
        fila = MiembroEquipoDispositivo.objects.get(usuario=limitada)
        fila.alcance = MiembroEquipoDispositivo.Alcance.EDIFICIOS
        fila.save()
        fila.edificios.add(self.edificio_a)

        self.assertEqual(self._mapa(limitada, edificio=self.edificio_a).status_code, 200)
        self.assertEqual(self._mapa(limitada, edificio=self.edificio_b).status_code, 404)
        self.assertEqual(self._get(limitada, "edificio-estadias", self.sede.pk, self.edificio_b.pk).status_code, 404)

    def test_el_mapa_no_trae_camas_de_otro_edificio(self):
        cuerpo = self._mapa(self.jefa, edificio=self.edificio_b).json()

        self.assertEqual([s["nombre"] for s in cuerpo["sectores"]], ["Único"])
        self.assertEqual(cuerpo["resumen"]["total"], 2)

    def test_sin_el_modulo_es_403_y_sin_token_401(self):
        sin_modulo = self._usuario("nadie", [VER], programa=self.dispositivos)

        self.assertEqual(self._mapa(sin_modulo).status_code, 403)
        self.assertEqual(self._anonimo().get(_url("edificios")).status_code, 401)

    @tag("performance")
    def test_las_consultas_no_crecen_con_las_camas(self):
        def consultas():
            with CaptureQueriesContext(connection) as capturadas:
                self.assertEqual(self._mapa(self.jefa).status_code, 200)
            return len(capturadas)

        self._alojar(self._plaza(self.sector_a1, 0))
        self._reservar(self._plaza(self.sector_a1, 1))
        consultas()  # la primera calienta cachés (permisos, tipos de contenido) que no son del mapa
        base = consultas()
        grande = self._sector(self.edificio_a, "Salón grande", 90)
        for indice in range(0, 90, 3):
            self._alojar(self._plaza(grande, indice))
        for indice in range(1, 90, 9):
            self._reservar(self._plaza(grande, indice))

        self.assertEqual(consultas(), base)
        self.assertLessEqual(base, 40)


class EstadiasDelEdificioTests(BasePlazasApp):
    def _estadias(self, usuario, edificio=None, **consulta):
        return self._get(usuario, "edificio-estadias", self.sede.pk, (edificio or self.edificio_a).pk, **consulta)

    def test_pagina_con_el_contrato_y_solo_las_activas_por_defecto(self):
        activa = self._alojar(self._plaza(self.sector_a1, 0))
        self._egresada(self._plaza(self.sector_a1, 1))
        self._alojar(self._plaza(self.sector_b, 0))  # otro edificio

        respuesta = self._estadias(self.jefa)

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        cuerpo = respuesta.json()
        self.assertEqual(sorted(cuerpo), CLAVES_PAGINA)
        self.assertEqual(cuerpo["count"], 1)
        self.assertIsNone(cuerpo["next"])
        self.assertIsNone(cuerpo["previous"])
        fila = cuerpo["results"][0]
        self.assertEqual(sorted(fila), CLAVES_ESTADIA)
        self.assertEqual(fila["id"], activa.pk)
        self.assertEqual(fila["persona"], {"nombre": "Benítez, Rosa", "dni": activa.ciudadano.dni})
        self.assertEqual(fila["sector"], {"id": self.sector_a1.pk, "nombre": "Pabellón 1"})
        self.assertEqual(fila["plaza"], {"id": activa.plaza_id, "codigo": activa.plaza.codigo})
        self.assertEqual(fila["estado"], "activa")
        self.assertIsNone(fila["fecha_egreso"])
        self.assertEqual(fila["origen"], "dispositivo")
        self.assertIsNone(fila["emergencia"])
        self.assertEqual(fila["acciones"], ["egresar", "reubicar"])

    def test_filtra_por_estado_y_por_sector(self):
        self._alojar(self._plaza(self.sector_a1, 0))
        self._alojar(self._plaza(self.sector_a2, 0))
        egresada = self._egresada(self._plaza(self.sector_a1, 1))

        egresadas = self._estadias(self.jefa, estado="egresada").json()
        del_sector = self._estadias(self.jefa, sector=self.sector_a2.pk).json()

        self.assertEqual([f["id"] for f in egresadas["results"]], [egresada.pk])
        self.assertEqual(egresadas["results"][0]["estado"], "egresada")
        self.assertIsNotNone(egresadas["results"][0]["fecha_egreso"])
        self.assertEqual(egresadas["results"][0]["acciones"], [])
        self.assertEqual(del_sector["count"], 1)
        self.assertEqual(del_sector["results"][0]["sector"]["nombre"], "Pabellón 2")

    def test_pagina_de_a_25_con_next_y_previous(self):
        grande = self._sector(self.edificio_a, "Salón grande", 30)
        for indice in range(30):
            self._alojar(self._plaza(grande, indice))

        primera = self._estadias(self.jefa).json()
        segunda = self._estadias(self.jefa, page=2).json()

        self.assertEqual(primera["count"], 30)
        self.assertEqual(len(primera["results"]), 25)
        self.assertIn("page=2", primera["next"])
        self.assertEqual(len(segunda["results"]), 5)
        self.assertIsNone(segunda["next"])
        self.assertIn("page=1", segunda["previous"])

    def test_sin_ciudadano_ver_no_hay_persona_y_sin_capacidades_no_hay_acciones(self):
        self._alojar(self._plaza(self.sector_a1, 0))
        lector = self._guardia("lector", [VER, ADMITIR], [self.sede])

        fila = self._estadias(lector).json()["results"][0]

        self.assertIsNone(fila["persona"])
        self.assertEqual(fila["acciones"], ["reubicar"])

    def test_marca_las_de_emergencia_con_el_numero_del_caso(self):
        caso = self._caso_tomado(menores_f=1, dni="30111222", nombre="Rosa", apellido="Benítez")
        estadia = self._alojar(self._plaza(self.sector_a1, 0))
        IntegranteGrupo.objects.create(grupo=caso.grupo, orden=1, ciudadano=estadia.ciudadano, estadia=estadia)

        fila = self._estadias(self.jefa).json()["results"][0]

        self.assertEqual(fila["origen"], "emergencia")
        self.assertEqual(fila["emergencia"], {"caso_numero": caso.numero})

    def test_edificio_de_otra_institucion_es_404(self):
        self.assertEqual(self._estadias(self.jefa, edificio=self.edificio_ajeno).status_code, 404)

    @tag("performance")
    def test_las_consultas_no_crecen_con_las_estadias(self):
        def consultas():
            with CaptureQueriesContext(connection) as capturadas:
                self.assertEqual(self._estadias(self.jefa).status_code, 200)
            return len(capturadas)

        self._alojar(self._plaza(self.sector_a1, 0))
        consultas()  # la primera calienta cachés que no son de la lista
        base = consultas()
        for indice in range(1, 4):
            self._alojar(self._plaza(self.sector_a1, indice))
        self._alojar(self._plaza(self.sector_a2, 0))

        self.assertEqual(consultas(), base)
