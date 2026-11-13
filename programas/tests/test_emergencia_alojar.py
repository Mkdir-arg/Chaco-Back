"""Emergencia, etapa 3 (alojar): lo que cruza los módulos del servicio y los selectores.

Los tests de cada paso están junto a su módulo: ``test_emergencia_ficha``,
``test_emergencia_recepcion``, ``test_emergencia_confirmacion``, ``test_emergencia_cierre`` y
``test_emergencia_sin_derivacion``; la base común, en ``test_emergencia_alojar_base``. Acá:

* **El orden de los candados**, por la secuencia de llamadas (en SQLite ``select_for_update``
  es un no-op). Las carreras de verdad están en ``test_emergencia_alojar_concurrencia``.
* **Selectores** de la guardia (mapa, integrantes, llegadas) y su alcance.
* **Presupuestos** de ``integrantes_de`` y ``plazas_para_caso`` con 300 camas, y de las
  llegadas con 2 y con 20 derivaciones.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from core.tests.candados import orden_de_candados
from legajos.models import Ciudadano
from programas.models import (
    CasoEmergencia,
    Derivacion,
    Estadia,
    NumeradorEmergencia,
    Plaza,
    ReservaPlaza,
    Sector,
    TrazaCaso,
)
from programas.selectors import emergencia_alojar as selectores
from programas.selectors import emergencia_llegadas as pantalla
from programas.services import emergencia_alojar as servicio
from programas.services.estadias import egresar_persona, reservar_plaza
from programas.tests.test_emergencia_alojar_base import BaseAlojar, ficha_minima
from programas.tests.test_emergencia_casos import T0

Estado = CasoEmergencia.Estado
Accion = TrazaCaso.Accion


# ---------------------------------------------------------------------------
# El orden de los candados
# ---------------------------------------------------------------------------


class OrdenDeLosCandadosDeAlojarTests(BaseAlojar):
    """**caso → derivación → plazas (por pk) → reservas → persona**, en cada camino de la etapa.

    Por la secuencia de llamadas y no por su efecto: en SQLite ``select_for_update()`` es un
    no-op y no hay deadlock que reproducir. La carrera de verdad es
    ``test_emergencia_alojar_concurrencia``, con ``@tag("mysql")``.
    """

    def _orden(self):
        return orden_de_candados(
            caso=CasoEmergencia.objects,
            derivacion=Derivacion.objects,
            plaza=Plaza.objects,
            reserva=ReservaPlaza.objects,
            persona=Ciudadano.objects,
            estadia=Estadia.objects,
            numerador=NumeradorEmergencia.objects,
        )

    def _sin_repetir(self, orden):
        """El orden en que cada tipo de fila se pide **por primera vez**."""

        return list(dict.fromkeys(orden))

    def test_aceptar(self):
        _caso, derivacion = self._derivado(plazas=2)
        with self._orden() as orden:
            servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)
        self.assertEqual(orden, ["caso", "derivacion", "plaza"])

    def test_rechazar(self):
        _caso, derivacion = self._derivado()
        with self._orden() as orden:
            servicio.rechazar_derivacion(derivacion=derivacion, usuario=self.guardia, motivo="SIN_PLAZAS")
        self.assertEqual(orden, ["caso", "derivacion"])

    def test_confirmar_consumiendo_una_reserva(self):
        caso, _derivacion = self._aceptado(plazas=2)
        with self._orden() as orden:
            self._confirmar(caso, 2, "45000111")
        self.assertEqual(orden[:2], ["caso", "derivacion"])
        self.assertEqual(self._sin_repetir(orden), ["caso", "derivacion", "plaza", "reserva", "persona"])

    def test_confirmar_en_una_cama_libre_devolviendo_la_sobrante(self):
        """Las dos plazas de una vez, después la reserva que se libera y la persona al final."""

        caso, _derivacion = self._aceptado()
        libre = self._cama_libre()
        with self._orden() as orden:
            integrante = self._confirmar(caso, 2, "45000111", plaza=libre)
        self.assertTrue(integrante.reserva_liberada)
        self.assertEqual(self._sin_repetir(orden), ["caso", "derivacion", "plaza", "reserva", "persona"])
        self._nada_nuevo_despues_de_la_persona(orden)

    def _nada_nuevo_despues_de_la_persona(self, orden):
        """Después de la persona solo se vuelve a pedir lo que ya estaba tomado (``ingresar_persona`` relee)."""

        persona = orden.index("persona")
        nuevas = [tipo for tipo in orden[persona + 1 :] if tipo not in orden[: persona + 1]]
        self.assertEqual(nuevas, [], "pidió algo nuevo después de bloquear a la persona")

    def test_confirmar_en_una_cama_libre_cerrando_su_reserva_comun_de_otro_dispositivo(self):
        """D2 del Cambio 409: la plaza de la reserva común entra en el mismo bloqueo único por pk."""

        caso, _derivacion = self._aceptado()
        persona = Ciudadano.objects.create(dni="45000111", nombre="Juan", apellido="Pérez")
        escuela = Plaza.objects.filter(sector__dispositivo=self.escuela).order_by("pk").first()
        reservar_plaza(plaza=escuela, ciudadano=persona, usuario=self.guardia_escuela)
        libre = self._cama_libre()
        with self._orden() as orden:
            self._confirmar(caso, 2, "45000111", plaza=libre)
        self.assertEqual(self._sin_repetir(orden), ["caso", "derivacion", "plaza", "reserva", "persona"])
        self._nada_nuevo_despues_de_la_persona(orden)

    def test_confirmar_en_una_cama_libre_sin_nada_que_liberar(self):
        """La cama se bloquea antes que la persona aunque no haya sobrante ni reservas comunes.

        Si no, el orden quedaba persona → plaza, el revés de ``ingresar_persona`` y
        ``reservar_plaza`` de Dispositivos: con una guardia de Dispositivos sobre la misma cama
        y la misma persona, deadlock en vez del rechazo prolijo.
        """

        caso, _derivacion = self._aceptado(plazas=2)  # retiene 2 de 7: no hay sobrante
        libre = self._cama_libre()
        with self._orden() as orden:
            integrante = self._confirmar(caso, 2, "45000111", plaza=libre)
        self.assertFalse(integrante.reserva_liberada)
        self.assertEqual(self._sin_repetir(orden), ["caso", "derivacion", "plaza", "persona"])
        self._nada_nuevo_despues_de_la_persona(orden)

    def test_cerrar_con_diferencia_cancelar_y_alojar(self):
        acciones = {
            "diferencia": lambda caso: servicio.cerrar_con_diferencia(
                caso=caso, usuario=self.guardia, motivo="NO_LLEGO"
            ),
            "alojar": None,
            "cancelar": lambda caso: servicio.cancelar_ingreso(caso=caso, usuario=self.guardia, motivo="No llegaron"),
        }
        for nombre, accion in acciones.items():
            with self.subTest(accion=nombre):
                caso, derivacion = self._aceptado(
                    dni=str(next(self._dnis)), menores_f=0, menores_m=0, plazas=3 if nombre == "alojar" else 2
                )
                if nombre == "alojar":
                    for orden_fila, reserva in enumerate(self._reservas(derivacion)[:2], start=1):
                        self._confirmar(caso, orden_fila, str(next(self._dnis)), plaza=reserva.plaza)
                    accion = lambda caso: servicio.alojar_familia(caso=caso, usuario=self.guardia)  # noqa: E731
                elif nombre == "diferencia":
                    self._confirmar(caso, 1, str(next(self._dnis)))
                with self._orden() as orden:
                    accion(caso)
                self.assertEqual(self._sin_repetir(orden), ["caso", "derivacion", "plaza", "reserva"])

    def test_completar_ficha_y_agregar_no_pasan_de_la_derivacion(self):
        caso, _derivacion = self._aceptado()
        self._confirmar(caso, 2, "45000111")
        with self._orden() as orden:
            servicio.completar_ficha(caso=caso, orden=2, usuario=self.guardia, ficha={"trabajo": {"sin_datos": True}})
            servicio.agregar_integrante(caso=caso, usuario=self.guardia)
        self.assertEqual(orden, ["caso", "derivacion", "caso", "derivacion"])

    def test_ingreso_directo(self):
        datos = self._datos(dni="33444555", nombre="Marta", apellido="Ríos")
        with self._orden() as orden:
            servicio.ingreso_directo(dispositivo=self.club, usuario=self.guardia, datos_formulario1=datos)
        self.assertEqual(orden, ["numerador", "caso", "plaza"])

    def test_el_egreso_bloquea_la_estadia_y_despues_el_caso(self):
        """El orden propio del egreso (ver el docstring del servicio): estadía → caso, y nada más."""

        caso, derivacion = self._aceptado(menores_f=0, menores_m=0)
        self._confirmar(caso, 1, "45000101")
        estadia = Estadia.objects.get()
        self.reloj.avanzar(hours=1)

        with self._orden() as orden:
            egresar_persona(estadia=estadia, usuario=self.guardia, motivo_egreso=self.motivo_alta, destino="Casa")

        self.assertEqual(orden, ["estadia", "caso"])


# ---------------------------------------------------------------------------
# Selectores
# ---------------------------------------------------------------------------


class SelectoresTests(BaseAlojar):
    def test_el_mapa_distingue_las_camas_de_esta_familia_de_las_de_otra(self):
        caso, derivacion = self._aceptado(plazas=3)
        _otro, otra = self._derivado(dni="30222333", plazas=2)
        servicio.aceptar_derivacion(derivacion=otra, usuario=self.guardia)
        self._ocupar_una_libre()
        rota = self._cama_libre()
        Plaza.objects.filter(pk=rota.pk).update(estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="Rota")

        (sector,) = selectores.plazas_para_caso(self.club, caso, self.guardia)

        estados = [plaza["estado"] for plaza in sector["plazas"]]
        self.assertEqual(estados.count(selectores.PLAZA_RESERVADA_FAMILIA), 3)
        self.assertEqual(estados.count(selectores.PLAZA_RESERVADA), 2)
        self.assertEqual(estados.count(selectores.PLAZA_OCUPADA), 1)
        self.assertEqual(estados.count(selectores.PLAZA_FUERA_SERVICIO), 1)
        self.assertEqual(estados.count(selectores.PLAZA_LIBRE), 2)
        self.assertEqual((sector["total"], sector["libres"], sector["reservadas_familia"]), (9, 2, 3))
        de_la_familia = {reserva.plaza_id for reserva in self._reservas(derivacion)}
        for plaza in sector["plazas"]:
            self.assertEqual(plaza["elegible"], plaza["estado"] in ("LIBRE", "RESERVADA_FAMILIA"))
            if plaza["estado"] == selectores.PLAZA_RESERVADA_FAMILIA:
                self.assertIn(plaza["id"], de_la_familia)
                self.assertEqual((plaza["texto"], plaza["tono"]), ("Reservada para esta familia", "warning"))
            if plaza["estado"] == selectores.PLAZA_RESERVADA:
                self.assertEqual((plaza["texto"], plaza["detalle"]), ("Reservada", ""))

    def _ocupar_una_libre(self):
        plaza = self._cama_libre()
        persona = Ciudadano.objects.create(dni=str(next(self._dnis)), nombre="Persona", apellido="Alojada")
        Estadia.objects.create(
            ciudadano=persona,
            dispositivo=self.club,
            plaza=plaza,
            fecha_ingreso=T0 - timedelta(days=1),
            clave_alojamiento=Estadia.clave_para(persona),
        )

    def test_el_mapa_no_nombra_al_responsable_de_otra_familia_ni_con_permiso_de_ver_personas(self):
        """RU-9: la cama guardada para otro caso es «Reservada» y nada más."""

        caso, _derivacion = self._aceptado(plazas=1)
        _otro, otra = self._derivado(dni="30222333", apellido="Zalazar", plazas=1)
        servicio.aceptar_derivacion(derivacion=otra, usuario=self.guardia)

        (sector,) = selectores.plazas_para_caso(self.club, caso, self.guardia, puede_ver_personas=True)

        self.assertNotIn("Zalazar", repr(sector))

    def test_sin_caso_ninguna_cama_es_de_la_familia(self):
        self._aceptado(plazas=2)
        (sector,) = selectores.plazas_para_caso(self.club, None, self.guardia)
        self.assertEqual(sector["reservadas_familia"], 0)

    def test_el_mapa_y_las_llegadas_exigen_alcance(self):
        caso, _derivacion = self._aceptado()
        for usuario in (self.guardia_escuela, self.operador):
            with self.subTest(usuario=usuario.username):
                with self.assertRaises(PermissionDenied):
                    selectores.plazas_para_caso(self.club, caso, usuario)
                with self.assertRaises(PermissionDenied):
                    selectores.llegadas_del_dispositivo(self.club, usuario)

    def test_integrantes_de_cuenta_y_describe_cada_fila(self):
        caso, derivacion = self._aceptado(menores_f=0, menores_m=0)
        plaza = self._reservas(derivacion)[0].plaza
        self._confirmar(caso, 2, "45000111", plaza=plaza)
        servicio.agregar_integrante(caso=caso, usuario=self.guardia)
        caso = CasoEmergencia.objects.select_related("grupo").get(pk=caso.pk)

        datos = selectores.integrantes_de(caso)

        self.assertEqual((datos["confirmadas"], datos["total_declarado"], datos["declaradas_al_relevar"]), (1, 3, 2))
        self.assertEqual(datos["con_ficha_incompleta"], 1)
        sin_confirmar, confirmada, agregada = datos["integrantes"]
        self.assertEqual(
            (sin_confirmar["n"], sin_confirmar["estado"], sin_confirmar["persona"]), (1, "SIN_CONFIRMAR", None)
        )
        self.assertEqual(confirmada["estado"], "CONFIRMADA")
        self.assertEqual(confirmada["persona"]["nombre"], "Pérez, Juan")
        self.assertEqual(
            confirmada["plaza"],
            {
                "id": plaza.pk,
                "codigo": plaza.codigo,
                "nombre": f"{plaza.codigo} (General)",
                "sector_id": plaza.sector_id,
            },
        )
        self.assertEqual(confirmada["parentesco"], "Hijo/a")
        self.assertFalse(confirmada["ficha_completa"])
        self.assertEqual(agregada["n"], 3)

    def test_las_llegadas_son_solo_las_de_ese_dispositivo(self):
        """RU-9."""

        pendiente_caso, pendiente = self._derivado()
        en_curso_caso, en_curso = self._aceptado(dni="30222333", plazas=2)
        self._confirmar(en_curso_caso, 2, "45000111")
        self._derivado(dispositivo=self.escuela, dni="30333444")
        _alojado_caso, alojada = self._aceptado(dni="30444555", menores_f=0, menores_m=0, adultos_m=0)
        self._confirmar(CasoEmergencia.objects.get(pk=alojada.caso_id), 1, "45000222")
        servicio.alojar_familia(caso=alojada.caso_id, usuario=self.guardia)

        llegadas = selectores.llegadas_del_dispositivo(self.club, self.guardia)

        self.assertEqual([d.pk for d in llegadas["pendientes"]], [pendiente.pk])
        self.assertEqual([d.pk for d in llegadas["en_curso"]], [en_curso.pk])
        self.assertEqual(llegadas["en_curso"][0].confirmadas, 1)
        self.assertEqual(llegadas["pendientes"][0].confirmadas, 0)


class PresupuestoDeConsultasDeAlojarTests(BaseAlojar):
    """Las dos lecturas de M2-3 / M2-4 cuestan lo mismo con 9 camas que con 300: sin N+1."""

    #: Las dos del alcance con un usuario recién leído (sus capacidades, que `rbac` memoiza en
    #: el objeto, y si integra el Equipo con un rol que admite), las camas con su sector, las
    #: dos de `estado_de_plazas` y la derivación vigente del caso.
    CONSULTAS_PLAZAS = 6
    #: Los integrantes con persona, estadía, plaza y sector.
    CONSULTAS_INTEGRANTES = 1

    def setUp(self):
        super().setUp()
        self.grande = self._dispositivo("Polideportivo", camas=0)
        for letra in "ABC":
            sector = Sector.objects.create(dispositivo=self.grande, nombre=f"Pabellón {letra}", capacidad=100)
            Plaza.objects.bulk_create([Plaza(sector=sector, codigo=f"{letra}-{n}") for n in range(1, 101)])
        self.guardia_grande = self._guardia("guardia_grande", self.grande)

    def test_plazas_para_caso_con_300_camas(self):
        caso, derivacion = self._derivado(dispositivo=self.grande)
        self._ocupar(self.grande, 120)
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia_grande)
        usuario = User.objects.get(pk=self.guardia_grande.pk)

        with self.assertNumQueries(self.CONSULTAS_PLAZAS):
            sectores = selectores.plazas_para_caso(self.grande, caso, usuario)

        self.assertEqual(sum(sector["total"] for sector in sectores), 300)
        self.assertEqual(sum(sector["reservadas_familia"] for sector in sectores), 7)
        self.assertEqual(sum(len(sector["plazas"]) for sector in sectores), 300)

    def test_integrantes_de_una_familia_grande(self):
        caso, derivacion = self._derivado(dispositivo=self.grande, menores_f=20, menores_m=18)
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia_grande)
        for orden, reserva in enumerate(self._reservas(derivacion)[:30], start=1):
            servicio.confirmar_integrante(
                caso=caso,
                orden=orden,
                usuario=self.guardia_grande,
                ficha=ficha_minima(str(46_000_000 + orden)),
                plaza=reserva.plaza,
            )
        caso = CasoEmergencia.objects.select_related("grupo").get(pk=caso.pk)

        with self.assertNumQueries(self.CONSULTAS_INTEGRANTES):
            datos = selectores.integrantes_de(caso)

        self.assertEqual((datos["confirmadas"], datos["total_declarado"]), (30, 40))

    def _llegadas_cuestan(self):
        """Cuántas consultas cuesta la lista de llegadas, con el usuario recién leído.

        Cuenta también el armado de las filas y de las tarjetas (familia, responsable, quién
        derivó): es lo que lee la pantalla, y donde aparecería un N+1 si el selector dejara de
        traer algo.
        """

        usuario = User.objects.get(pk=self.guardia_grande.pk)
        ahora = timezone.now()
        with CaptureQueriesContext(connection) as consultas:
            llegadas = selectores.llegadas_del_dispositivo(self.grande, usuario)
            for derivaciones in llegadas.values():
                pantalla.filas_de_llegadas(derivaciones, ahora, lambda derivacion: "")
                for derivacion in derivaciones:
                    pantalla.tarjeta_de_derivacion(derivacion, ahora)
        return len(consultas), llegadas

    def _familias_derivadas(self, desde, cuantas):
        """``cuantas`` familias de 2 derivadas al Polideportivo: la mitad aceptadas, la otra pendientes."""

        for n in range(desde, desde + cuantas):
            _caso, derivacion = self._derivado(
                dispositivo=self.grande, dni=str(31_000_000 + n), menores_f=0, menores_m=1, plazas=2
            )
            if n % 2:
                servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia_grande)

    def test_llegadas_cuestan_lo_mismo_con_2_que_con_20_derivaciones(self):
        """Sin N+1: la lista de llegadas trae caso, grupo, responsable y quién derivó en la misma consulta."""

        self._familias_derivadas(0, 2)
        con_2, llegadas = self._llegadas_cuestan()
        self.assertEqual((len(llegadas["pendientes"]), len(llegadas["en_curso"])), (1, 1))

        self._familias_derivadas(2, 18)
        con_20, llegadas = self._llegadas_cuestan()
        self.assertEqual((len(llegadas["pendientes"]), len(llegadas["en_curso"])), (10, 10))

        self.assertEqual(con_20, con_2, "las consultas de llegadas crecen con las derivaciones")
