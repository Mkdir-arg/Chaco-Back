"""Deuda de E1 que E8 reusa (Cambio 504 · E-1 #1180), separada de ``test_emergencia_tablero``.

Camas libres solo ``CAMA`` en E1 y en el panel «Derivar» de E3, casos por ``localidad_id``
(homónimas), el estado vacío con red cargada y la definición única de ingreso directo.
"""

from django.core.exceptions import ValidationError

from core.models import Localidad, Municipio
from programas.models import CasoEmergencia, Plaza, Sector
from programas.selectors import emergencia_tablero as tablero
from programas.selectors.emergencia import dispositivos_para_derivar
from programas.services import emergencia as servicio
from programas.tests.test_emergencia_casos import T0
from programas.tests.test_emergencia_tablero import URL_TABLERO, BaseTablero, _hora

Estado = CasoEmergencia.Estado
Origen = CasoEmergencia.Origen


class BaseDeudaE1(BaseTablero):
    """Los casos y personas de estos tests usan DNIs de prueba (90000001–90000099)."""

    def setUp(self):
        super().setUp()
        self._dnis = iter(range(90_000_001, 90_000_100))

    def _cupos(self, dispositivo, cuantos):
        sector = Sector.objects.create(dispositivo=dispositivo, nombre="Cupos", capacidad=cuantos)
        Plaza.objects.bulk_create(
            [Plaza(sector=sector, codigo=f"U{n:03d}", tipo=Plaza.Tipo.CUPO) for n in range(1, cuantos + 1)]
        )
        Plaza.objects.create(sector=sector, codigo="T001", tipo=Plaza.Tipo.TURNO)


class CamasLibresTests(BaseDeudaE1):
    """Pendiente 1 del Cambio 472: E1 y el panel «Derivar» de E3 cuentan solo camas (RN-2.3)."""

    def setUp(self):
        super().setUp()
        self.solo_cupos = self._dispositivo("Comedor Norte", localidad="Resistencia")
        self._cupos(self.solo_cupos, 20)
        self.mixto = self._dispositivo("Club Mixto", camas=10, localidad="Resistencia")
        self._ocupar(self.mixto, 7)
        self._cupos(self.mixto, 20)
        self.caso = self._sembrar(Estado.EN_GESTION, tomado_en=T0)

    def _derivar_panel(self):
        filas = dispositivos_para_derivar(self.caso, self.supervisor, momento=T0)
        return {fila["id"]: fila["libres"] for fila in filas}

    def test_e1_los_cupos_no_suman_a_camas_libres(self):
        foto = tablero.foto_del_tablero(self.sla, T0)
        self.assertEqual(foto.red.libres_de(self.solo_cupos.pk), 0)
        self.assertEqual(foto.red.libres_de(self.mixto.pk), 3)
        self.assertEqual(tablero.resumen(self.sla, T0, foto=foto)["hero"]["libres"], 3)

    def test_e3_el_panel_derivar_cuenta_solo_camas_y_coincide_con_e1(self):
        foto = tablero.foto_del_tablero(self.sla, T0)
        panel = self._derivar_panel()
        self.assertEqual(panel, {self.solo_cupos.pk: 0, self.mixto.pk: 3})
        self.assertEqual(panel, {pk: foto.red.libres_de(pk) for pk in panel})

    def test_no_se_deriva_a_un_dispositivo_que_solo_tiene_cupos(self):
        with self.assertRaises(ValidationError) as error:
            servicio.derivar_caso(self.caso, self.supervisor, self.solo_cupos, 2)
        self.assertEqual(error.exception.message_dict["dispositivo"], [servicio.SIN_PLAZAS])


class LocalidadesHomonimasTests(BaseDeudaE1):
    """Pendiente 3 del Cambio 472 (RN-009-04): los casos se agrupan por ``localidad_id``."""

    def setUp(self):
        super().setUp()
        self.norte = Localidad.objects.create(nombre="La Esperanza", municipio=Municipio.objects.create(nombre="Norte"))
        self.sur = Localidad.objects.create(nombre="La Esperanza", municipio=Municipio.objects.create(nombre="Sur"))
        self.fontana = Localidad.objects.create(nombre="Fontana", municipio=None)
        for localidad in (self.norte, self.norte, self.sur, self.fontana):
            self._sembrar(Estado.NUEVO, localidad=localidad, creado=_hora(9, 55))

    def _filas(self):
        return tablero.por_localidad(self.sla, T0)

    def test_dos_localidades_homonimas_no_se_mezclan(self):
        filas = {fila["localidad_id"]: fila for fila in self._filas() if fila["localidad_id"]}
        self.assertEqual((filas[self.norte.pk]["nuevos"], filas[self.sur.pk]["nuevos"]), (2, 1))
        self.assertEqual(filas[self.norte.pk]["url"], f"/emergencia/casos/?solapa=abiertos&localidad={self.norte.pk}")
        self.assertEqual(filas[self.sur.pk]["url"], f"/emergencia/casos/?solapa=abiertos&localidad={self.sur.pk}")
        self.assertEqual(sum(fila["nuevos"] for fila in self._filas()), 4)

    def test_las_camas_de_un_nombre_ambiguo_van_aparte_y_sin_enlace(self):
        self._dispositivo("Escuela 5", camas=4, localidad="La Esperanza")
        self._dispositivo("Club Fontana", camas=3, localidad=" fontana ")
        filas = self._filas()
        por_id = {fila["localidad_id"]: fila for fila in filas if fila["localidad_id"]}
        aparte = [fila for fila in filas if not fila["localidad_id"]]
        self.assertEqual((por_id[self.norte.pk]["plazas_libres"], por_id[self.sur.pk]["plazas_libres"]), (0, 0))
        self.assertEqual(por_id[self.fontana.pk]["plazas_libres"], 3)
        self.assertEqual(
            [(fila["localidad"], fila["plazas_libres"], fila["nuevos"], fila["url"]) for fila in aparte],
            [("La Esperanza", 4, 0, "")],
        )


class EstadoVacioConRedTests(BaseDeudaE1):
    """Pendiente 4 del Cambio 472: con red cargada y sin casos, la tabla dice «Todavía no hay casos»."""

    def setUp(self):
        super().setUp()
        for n, localidad in enumerate(("Resistencia", "Barranqueras", "Fontana")):
            self._dispositivo(f"Dispositivo {n}", camas=5, localidad=localidad)
        self.client.force_login(self.supervisor)

    def test_sin_casos_aparece_el_estado_vacio(self):
        self.assertContains(self.client.get(URL_TABLERO), "Todavía no hay casos")

    def test_con_un_caso_no_aparece(self):
        localidad = self._localidad("Resistencia")
        self._sembrar(Estado.NUEVO, localidad=localidad, creado=_hora(9, 55))
        respuesta = self.client.get(URL_TABLERO)
        self.assertNotContains(respuesta, "Todavía no hay casos")
        self.assertContains(respuesta, f'href="/emergencia/casos/?solapa=abiertos&amp;localidad={localidad.pk}"')


class IngresoDirectoUnicoTests(BaseDeudaE1):
    """Pendiente 7 del Cambio 472: E1 usa ``CasoEmergencia.es_ingreso_directo`` (en SQL, su ``Q``)."""

    def test_la_foto_dice_lo_mismo_que_el_modelo(self):
        en_la_puerta = {CasoEmergencia.SITUACION_EN_LA_PUERTA: {"dispositivo": "Escuela 12"}}
        casos = [
            # «Ingresar igual» con el tomado corrido: la regla vieja (tomado == creado) no lo veía.
            self._sembrar(
                Estado.ALOJADO, origen=Origen.DISPOSITIVO, creado=_hora(8), tomado_en=_hora(8, 1), alojado_en=_hora(9)
            ),
            # Aviso a la mesa tomado en el mismo instante: la regla vieja lo contaba como directo.
            self._sembrar(Estado.EN_GESTION, origen=Origen.DISPOSITIVO, tomado_en=T0, situacion=en_la_puerta),
            self._sembrar(Estado.NUEVO, creado=_hora(9, 30)),
        ]
        CasoEmergencia.objects.filter(pk=casos[1].pk).update(creado=T0)
        filas = {fila.id: fila.ingreso_directo for fila in tablero.foto_del_tablero(self.sla, T0).casos}
        esperado = {caso.pk: CasoEmergencia.objects.get(pk=caso.pk).es_ingreso_directo for caso in casos}
        self.assertEqual(filas, esperado)
        self.assertEqual(list(esperado.values()), [True, False, False])
