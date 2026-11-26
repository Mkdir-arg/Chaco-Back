"""Stock, PR 2b (análisis 010, RN-010-09 y RN-010-10): la entrega a una persona por DNI y su historial.

Todo llama al servicio directo, no a una vista. Mutaciones verificadas a mano (se rompe la regla, se mira el test
rojo, se restaura):

* sacar ``rbac.puede(user, CAP_VER_CIUDADANO)`` de ``puede_entregar`` pone rojo
  ``test_sin_ciudadano_ver_no_entrega_ni_consulta_el_registro`` y ``test_consultar_persona_exige_lo_mismo_que_entregar``;
* sacar ``_exigir_saldo`` de ``entregar_a_persona`` y de ``_asentar`` pone rojo ``test_saldo_insuficiente_es_todo_o_nada``
  (llega el ``IntegrityError`` del ``CHECK``, no la excepción del dominio);
* sacar el ``atomic`` de ``entregar_a_persona`` pone rojo ``test_sin_saldo_no_queda_un_legajo_huerfano`` (es lo que
  deshace el alta); mover ``dar_de_alta`` antes de ``_exigir_saldo`` lo detecta ``test_stock_ronda2``, no este archivo;
* nombrar siempre la institución en ``historial_de_persona`` pone rojo ``test_otra_institucion_figura_sin_nombre``.
"""

from datetime import timedelta
from unittest import mock

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import Dispositivo, MovimientoStock, OperacionStock, SaldoStock, TipoDispositivo
from programas.selectors import stock as selectores
from programas.services import stock as servicio
from programas.services.stock_personas import PersonaSinDatos, resolver_persona
from programas.tests.base_stock import BaseEntrega


class EntregaALaPersonaTests(BaseEntrega):
    def test_una_entrega_descuenta_asienta_a_la_persona_y_deja_el_libro_coherente(self):
        self._sembrar(self.colchon, 5)
        self._sembrar(self.frazada, 2)

        operacion = self._entregar(lineas={self.colchon.pk: 3, self.frazada.pk: 1}, observacion="  para la familia ")

        self.assertFalse(operacion.ya_existia)
        self.assertEqual(operacion.tipo, OperacionStock.Tipo.ENTREGA_PERSONA)
        self.assertEqual(operacion.ciudadano, self.persona)
        self.assertEqual(operacion.usuario, self.guardia)
        self.assertEqual(operacion.observacion, "para la familia")
        self.assertEqual((self._cantidad(self.colchon), self._cantidad(self.frazada)), (2, 1))
        movimientos = {m.item_id: m for m in operacion.movimientos.all()}
        self.assertEqual(movimientos[self.colchon.pk].cantidad, -3)
        self.assertEqual(movimientos[self.colchon.pk].saldo_posterior, 2)
        self.assertEqual(movimientos[self.frazada.pk].tipo, MovimientoStock.Tipo.ENTREGA_PERSONA)
        self.assertLibroCoherente()

    def test_con_el_saldo_justo_queda_en_cero(self):
        self._sembrar(self.colchon, 3)

        self._entregar(lineas={self.colchon.pk: 3})

        self.assertEqual(self._cantidad(self.colchon), 0)
        self.assertLibroCoherente()

    def test_saldo_insuficiente_es_todo_o_nada(self):
        self._sembrar(self.colchon, 5)
        self._sembrar(self.frazada, 1)
        antes = (OperacionStock.objects.count(), MovimientoStock.objects.count())

        with self.assertRaises(servicio.SaldoInsuficiente) as contexto:
            self._entregar(lineas={self.colchon.pk: 2, self.frazada.pk: 2})

        error = contexto.exception
        self.assertEqual(error.faltantes, {self.frazada.pk: (2, 1)})
        self.assertEqual(error.saldos_actuales, {self.colchon.pk: 5, self.frazada.pk: 1})
        self.assertEqual((self._cantidad(self.colchon), self._cantidad(self.frazada)), (5, 1))
        self.assertEqual((OperacionStock.objects.count(), MovimientoStock.objects.count()), antes)
        self.assertLibroCoherente()

    def test_sin_ningun_saldo_no_se_entrega(self):
        with self.assertRaises(servicio.SaldoInsuficiente):
            self._entregar()

        self.assertFalse(OperacionStock.objects.exists())

    def test_un_insumo_desactivado_con_saldo_se_entrega(self):
        """RN-010-17: mientras tenga saldo se entrega, esté o no activo."""

        self._sembrar(self.viejo, 2)

        self._entregar(lineas={self.viejo.pk: 2})

        self.assertEqual(self._cantidad(self.viejo), 0)

    def test_las_lineas_se_validan_como_en_el_resto_del_modulo(self):
        self._sembrar(self.colchon, 5)

        for lineas in ({}, {self.colchon.pk: 0}, {self.colchon.pk: "x"}, {999999: 1}):
            with self.subTest(lineas), self.assertRaises(ValidationError) as contexto:
                self._entregar(lineas=lineas)
            self.assertIn("lineas", contexto.exception.message_dict)
        with self.assertRaises(ValidationError) as contexto:
            self._entregar(observacion="x" * 201)
        self.assertIn("observacion", contexto.exception.message_dict)
        self.assertEqual(self._cantidad(self.colchon), 5)


class LaPersonaDeLaEntregaTests(BaseEntrega):
    def setUp(self):
        super().setUp()
        self._sembrar(self.colchon, 10)

    def test_la_persona_del_legajo_no_consulta_el_registro(self):
        with mock.patch(self.CONSULTA_RENAPER) as consulta:
            operacion = self._entregar(dni="30.111.222", sexo="F")

        consulta.assert_not_called()
        self.assertEqual(operacion.ciudadano, self.persona)

    def test_un_legajo_cargado_con_separadores_se_encuentra(self):
        con_puntos = Ciudadano.objects.create(dni="31.222.333", nombre="Luis", apellido="Gil")

        with mock.patch(self.CONSULTA_RENAPER) as consulta:
            operacion = self._entregar(dni="31222333")

        consulta.assert_not_called()
        self.assertEqual(operacion.ciudadano, con_puntos)

    def test_la_persona_del_registro_se_da_de_alta_con_sus_datos(self):
        with mock.patch(self.CONSULTA_RENAPER, return_value=self.RENAPER_ENCUENTRA) as consulta:
            operacion = self._entregar(dni="27.555.666", sexo="F")

        consulta.assert_called_once_with("27555666", "F")
        ciudadano = Ciudadano.objects.get(dni="27555666")
        self.assertEqual(operacion.ciudadano, ciudadano)
        self.assertEqual((ciudadano.nombre, ciudadano.apellido), ("Marta", "Ruiz"))
        self.assertEqual(ciudadano.estado_renaper, Ciudadano.EstadoRenaper.REGISTRADO)

    def test_sin_registro_se_da_el_alta_minima_con_nombre_y_apellido(self):
        with mock.patch(self.CONSULTA_RENAPER, return_value=self.RENAPER_NO_ESTA):
            operacion = self._entregar(dni="28444555", sexo="M", nombre=" Juan ", apellido="Pérez")

        ciudadano = Ciudadano.objects.get(dni="28444555")
        self.assertEqual(operacion.ciudadano, ciudadano)
        self.assertEqual((ciudadano.nombre, ciudadano.apellido), ("Juan", "Pérez"))
        self.assertEqual(ciudadano.estado_renaper, "")
        self.assertEqual(ciudadano.genero, "M")

    def test_sin_sexo_el_alta_minima_no_consulta_el_registro(self):
        with mock.patch(self.CONSULTA_RENAPER) as consulta:
            self._entregar(dni="28444555", nombre="Juan", apellido="Pérez")

        consulta.assert_not_called()
        self.assertTrue(Ciudadano.objects.filter(dni="28444555").exists())

    def test_sin_registro_y_sin_nombre_pide_los_datos(self):
        with mock.patch(self.CONSULTA_RENAPER, return_value=self.RENAPER_NO_ESTA):
            with self.assertRaises(PersonaSinDatos) as contexto:
                self._entregar(dni="28444555", sexo="M")

        self.assertEqual(contexto.exception.code, "PERSONA_SIN_DATOS")
        self.assertFalse(contexto.exception.pide_sexo)
        self.assertEqual(contexto.exception.motivo, "No está en el Registro de Personas.")
        self.assertFalse(Ciudadano.objects.filter(dni="28444555").exists())
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_sin_sexo_ni_nombre_pide_el_sexo_y_no_consulta(self):
        with mock.patch(self.CONSULTA_RENAPER) as consulta, self.assertRaises(PersonaSinDatos) as contexto:
            self._entregar(dni="28444555")

        consulta.assert_not_called()
        self.assertTrue(contexto.exception.pide_sexo)

    def test_el_registro_caido_tambien_cae_al_alta_minima(self):
        with mock.patch(self.CONSULTA_RENAPER, return_value={"success": False, "status_code": 503}):
            with self.assertRaises(PersonaSinDatos) as contexto:
                self._entregar(dni="28444555", sexo="M")

        self.assertEqual(contexto.exception.motivo, "No se pudo consultar el Registro de Personas.")

    def test_la_persona_fallecida_no_recibe_nada(self):
        with mock.patch(self.CONSULTA_RENAPER, return_value=self.RENAPER_FALLECIDA):
            with self.assertRaises(ValidationError) as contexto:
                self._entregar(dni="28444555", sexo="M", nombre="Juan", apellido="Pérez")

        self.assertIn("fallecida", contexto.exception.message_dict["dni"][0])
        self.assertFalse(Ciudadano.objects.filter(dni="28444555").exists())
        self.assertFalse(OperacionStock.objects.exclude(tipo=OperacionStock.Tipo.INGRESO_MANUAL).exists())
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_un_dni_o_un_sexo_invalidos_se_rechazan_antes_de_consultar(self):
        with mock.patch(self.CONSULTA_RENAPER) as consulta:
            with self.assertRaises(ValidationError) as dni:
                self._entregar(dni="123")
            with self.assertRaises(ValidationError) as sexo:
                self._entregar(dni="28444555", sexo="Z")

        consulta.assert_not_called()
        self.assertIn("dni", dni.exception.message_dict)
        self.assertIn("sexo", sexo.exception.message_dict)

    def test_sin_saldo_no_queda_un_legajo_huerfano(self):
        with mock.patch(self.CONSULTA_RENAPER, return_value=self.RENAPER_ENCUENTRA):
            with self.assertRaises(servicio.SaldoInsuficiente):
                self._entregar(dni="27555666", sexo="F", lineas={self.colchon.pk: 11})

        self.assertFalse(Ciudadano.objects.filter(dni="27555666").exists())

    def test_si_falla_al_asentar_tampoco_queda_el_legajo(self):
        """El alta va **dentro** de la transacción de la entrega: lo que falle después la deshace."""

        with (
            mock.patch(self.CONSULTA_RENAPER, return_value=self.RENAPER_ENCUENTRA),
            mock.patch.object(servicio, "_asentar", side_effect=RuntimeError("se cayó")),
            self.assertRaises(RuntimeError),
        ):
            self._entregar(dni="27555666", sexo="F")

        self.assertFalse(Ciudadano.objects.filter(dni="27555666").exists())

    def test_un_dato_que_el_legajo_no_acepta_se_devuelve_como_error_del_nombre(self):
        with mock.patch(self.CONSULTA_RENAPER, return_value=self.RENAPER_NO_ESTA):
            with self.assertRaises(ValidationError) as contexto:
                self._entregar(dni="28444555", sexo="M", nombre="N" * 200, apellido="Pérez")

        self.assertIn("nombre", contexto.exception.message_dict)
        self.assertFalse(Ciudadano.objects.filter(dni="28444555").exists())

    def test_resolver_persona_solo_lee(self):
        with mock.patch(self.CONSULTA_RENAPER, return_value=self.RENAPER_ENCUENTRA):
            persona = resolver_persona("27555666", "F")

        self.assertEqual(persona.origen, "registro")
        self.assertEqual((persona.nombre, persona.apellido), ("Marta", "Ruiz"))
        self.assertFalse(Ciudadano.objects.filter(dni="27555666").exists())
        self.assertEqual(resolver_persona("30111222").origen, "legajo")


class PermisosYEstadoDeLaEntregaTests(BaseEntrega):
    def setUp(self):
        super().setUp()
        self._sembrar(self.colchon, 10)

    def test_sin_ciudadano_ver_no_entrega_ni_consulta_el_registro(self):
        sin_ciudadano = self._usuario_con("sin_ciudadano", ("stock.ver", "stock.entregar"))

        with mock.patch(self.CONSULTA_RENAPER) as consulta, self.assertRaises(PermissionDenied):
            self._entregar(sin_ciudadano, dni="27555666", sexo="F")

        consulta.assert_not_called()
        self.assertEqual(self._cantidad(self.colchon), 10)
        self.assertFalse(Ciudadano.objects.filter(dni="27555666").exists())

    def test_sin_stock_entregar_o_sin_stock_ver_no_entrega(self):
        for nombre, capacidades in (
            ("sin_entregar", ("stock.ver", "stock.ingresar", "ciudadano.ver")),
            ("sin_ver", ("stock.entregar", "ciudadano.ver")),
        ):
            usuario = self._usuario_con(nombre, capacidades)
            with self.subTest(nombre), self.assertRaises(PermissionDenied):
                self._entregar(usuario)
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_un_usuario_sin_rol_o_anonimo_no_entrega(self):
        from django.contrib.auth.models import AnonymousUser

        sin_rol = self._fresco(self._otro_usuario("sin_rol"))
        for usuario in (sin_rol, AnonymousUser()):
            with self.subTest(usuario), self.assertRaises(PermissionDenied):
                self._entregar(usuario)

    def test_quien_alcanza_otro_edificio_no_entrega_en_este(self):
        from programas.models import MiembroEquipoDispositivo

        rol = self._rol("De un edificio", ("dispositivo.ver", "stock.ver", "stock.entregar", "ciudadano.ver"))
        usuario = self._usuario("de_un_edificio", rol)
        miembro = MiembroEquipoDispositivo.objects.create(
            dispositivo=self.disp, usuario=usuario, rol=rol, alcance=MiembroEquipoDispositivo.Alcance.EDIFICIOS
        )
        miembro.edificios.set([self.otro_edificio])
        usuario = self._fresco(usuario)

        with self.assertRaises(PermissionDenied):
            self._entregar(usuario, edificio=self.edificio)

    def test_ver_todos_lee_pero_no_entrega(self):
        rol = self._rol(
            "Supervisión", ("dispositivo.ver", "dispositivo.ver_todos", "stock.ver", "stock.entregar", "ciudadano.ver")
        )
        supervisor = self._fresco(self._usuario("supervisor", rol))

        with self.assertRaises(PermissionDenied):
            self._entregar(supervisor)

    def test_una_institucion_que_no_lleva_stock_no_entrega(self):
        self.tipo.maneja_stock = False
        self.tipo.save()

        with mock.patch(self.CONSULTA_RENAPER) as consulta, self.assertRaises(servicio.StockNoHabilitado):
            self._entregar(dni="27555666", sexo="F")

        consulta.assert_not_called()

    def test_una_institucion_que_no_esta_activa_ni_un_edificio_inactivo_entregan(self):
        self.disp.estado = Dispositivo.Estado.INACTIVO
        self.disp.save()
        with self.assertRaises(servicio.StockNoHabilitado):
            self._entregar()

        self.disp.estado = Dispositivo.Estado.ACTIVO
        self.disp.save()
        self.edificio.activo = False
        self.edificio.save()
        with self.assertRaises(servicio.StockNoHabilitado):
            self._entregar()
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_un_edificio_de_otra_institucion_se_rechaza(self):
        with self.assertRaises(ValidationError) as contexto:
            self._entregar(edificio=self.edificio_b)

        self.assertIn("edificio", contexto.exception.message_dict)


class IdempotenciaDeLaEntregaTests(BaseEntrega):
    def setUp(self):
        super().setUp()
        self._sembrar(self.colchon, 10)
        self.envio = "6f1c7c8e-3a4b-4c5d-9e0f-1a2b3c4d5e6f"

    def test_el_mismo_envio_del_mismo_usuario_no_descuenta_dos_veces(self):
        primera = self._entregar(uuid_cliente=self.envio)

        with mock.patch(self.CONSULTA_RENAPER) as consulta:
            segunda = self._entregar(uuid_cliente=self.envio, dni="27555666", sexo="F")

        consulta.assert_not_called()
        self.assertFalse(primera.ya_existia)
        self.assertTrue(segunda.ya_existia)
        self.assertEqual(segunda.pk, primera.pk)
        self.assertEqual(self._cantidad(self.colchon), 9)
        self.assertEqual(OperacionStock.objects.filter(tipo=OperacionStock.Tipo.ENTREGA_PERSONA).count(), 1)
        self.assertLibroCoherente()

    def test_el_envio_de_otro_usuario_o_de_otra_accion_es_uuid_en_uso(self):
        self._entregar(uuid_cliente=self.envio)
        otra = self._usuario_con("otra_guardia", ("stock.ver", "stock.entregar", "stock.ingresar", "ciudadano.ver"))

        with self.assertRaises(servicio.UuidEnUso):
            self._entregar(otra, uuid_cliente=self.envio)
        with self.assertRaises(servicio.UuidEnUso):
            servicio.ingresar_manual(
                otra, self.disp, self.edificio, {self.colchon.pk: 1}, origen="DONACION", uuid_cliente=self.envio
            )
        self.assertEqual(self._cantidad(self.colchon), 9)


class ConsultarPersonaTests(BaseEntrega):
    def test_consultar_persona_exige_lo_mismo_que_entregar(self):
        for nombre, capacidades in (
            ("solo_ciudadano", ("stock.ver", "ciudadano.ver")),
            ("solo_entregar", ("stock.ver", "stock.entregar")),
        ):
            usuario = self._usuario_con(nombre, capacidades)
            with self.subTest(nombre), mock.patch(self.CONSULTA_RENAPER) as consulta:
                with self.assertRaises(PermissionDenied):
                    servicio.consultar_persona(usuario, self.disp, self.edificio, "30111222", "F")
                consulta.assert_not_called()

    def test_devuelve_la_persona_y_su_historial_sin_escribir(self):
        self._sembrar(self.colchon, 5)
        self._entregar(lineas={self.colchon.pk: 2})
        operaciones = OperacionStock.objects.count()

        persona, historial = servicio.consultar_persona(self.guardia, self.disp, self.edificio, "30.111.222")

        self.assertEqual(persona.ciudadano, self.persona)
        self.assertEqual(
            [h["lineas"] for h in historial], [[{"nombre": "Colchón stock", "unidad": "unidad", "cantidad": 2}]]
        )
        self.assertEqual(OperacionStock.objects.count(), operaciones)

    def test_una_persona_del_registro_se_muestra_pero_no_se_da_de_alta(self):
        with mock.patch(self.CONSULTA_RENAPER, return_value=self.RENAPER_ENCUENTRA):
            persona, historial = servicio.consultar_persona(self.guardia, self.disp, self.edificio, "27555666", "F")

        self.assertEqual((persona.origen, persona.nombre), ("registro", "Marta"))
        self.assertEqual(historial, [])
        self.assertFalse(Ciudadano.objects.filter(dni="27555666").exists())


class HistorialDeLaPersonaTests(BaseEntrega):
    def setUp(self):
        super().setUp()
        self._sembrar(self.colchon, 500)
        self._sembrar(self.frazada, 500)

    def _entregas(self, cantidad):
        for numero in range(cantidad):
            self._entregar(lineas={self.colchon.pk: 1, self.frazada.pk: numero + 1})

    def test_son_las_ultimas_veinte_de_la_mas_nueva_a_la_mas_vieja(self):
        self._entregas(22)

        historial = selectores.historial_de_persona(self.persona, self.disp)

        self.assertEqual(len(historial), 20)
        frazadas = [
            next(linea["cantidad"] for linea in entrega["lineas"] if linea["nombre"] == "Frazada stock")
            for entrega in historial
        ]
        self.assertEqual(frazadas, list(range(22, 2, -1)))

    def test_cuesta_dos_consultas_sin_importar_cuantas_entregas_ni_insumos(self):
        self._entregas(20)

        with CaptureQueriesContext(connection) as consultas:
            historial = selectores.historial_de_persona(self.persona, self.disp)

        self.assertEqual(len(historial), 20)
        self.assertEqual(len(consultas), 2)

    def test_otra_institucion_figura_sin_nombre(self):
        self._entregas(1)
        guardia_b = self._usuario_con(
            "guardia_b", ("stock.ver", "stock.entregar", "ciudadano.ver"), dispositivo=self.disp_b
        )
        self._sembrar(self.colchon, 5, edificio=self.edificio_b, dispositivo=self.disp_b)
        self._entregar(guardia_b, dispositivo=self.disp_b, edificio=self.edificio_b)

        desde_a = selectores.historial_de_persona(self.persona, self.disp)
        desde_b = selectores.historial_de_persona(self.persona, self.disp_b)

        self.assertEqual(
            {h["institucion"]: h["propia"] for h in desde_a}, {self.disp.nombre: True, "Otra institución": False}
        )
        self.assertEqual(
            {h["institucion"]: h["propia"] for h in desde_b}, {self.disp_b.nombre: True, "Otra institución": False}
        )
        self.assertNotIn(self.disp_b.nombre, repr(desde_a))
        self.assertNotIn(self.disp.nombre, repr(desde_b))

    def test_una_institucion_de_ubicacion_reservada_no_deja_nombre_ni_localidad(self):
        tipo = TipoDispositivo.objects.create(
            codigo="RESERVADO", nombre="Refugio", maneja_stock=True, ubicacion_reservada=True
        )
        reservada = Dispositivo.objects.create(
            tipo=tipo,
            codigo="R-1",
            nombre="Refugio Secreto",
            localidad="Barrio Escondido",
            estado=Dispositivo.Estado.ACTIVO,
        )
        edificio = self.edificio_b
        edificio.dispositivos.add(reservada)
        self._sembrar(self.colchon, 5, edificio=edificio, dispositivo=reservada)
        guardia = self._usuario_con(
            "guardia_reservada", ("stock.ver", "stock.entregar", "ciudadano.ver"), dispositivo=reservada
        )
        self._entregar(guardia, dispositivo=reservada, edificio=edificio)

        historial = selectores.historial_de_persona(self.persona, self.disp)

        self.assertEqual([h["institucion"] for h in historial], ["Otra institución"])
        texto = repr(historial)
        for dato in ("Refugio", "Escondido", "R-1", "Edificio de la otra"):
            self.assertNotIn(dato, texto)

    def test_no_trae_quien_entrego_ni_la_observacion(self):
        self._entregar(observacion="dato libre de la persona")

        (entrada,) = selectores.historial_de_persona(self.persona, self.disp)

        self.assertEqual(set(entrada), {"creado_en", "institucion", "propia", "lineas"})
        self.assertNotIn("dato libre", repr(entrada))
        self.assertNotIn(self.guardia.username, repr(entrada))

    def test_solo_cuentan_las_entregas_de_esa_persona(self):
        otra = Ciudadano.objects.create(dni="32000111", nombre="Otra", apellido="Persona")
        self._entregar(dni="32000111")
        servicio.ingresar_manual(self.carga, self.disp, self.edificio, {self.colchon.pk: 1}, origen="DONACION")

        self.assertEqual(selectores.historial_de_persona(self.persona, self.disp), [])
        self.assertEqual(len(selectores.historial_de_persona(otra, self.disp)), 1)
        self.assertEqual(selectores.historial_de_persona(None, self.disp), [])

    def test_conserva_la_entrega_aunque_el_tipo_ya_no_lleve_stock(self):
        """El libro queda y el historial lo sigue mostrando (análisis §11)."""

        self._entregas(1)
        SaldoStock.objects.update(cantidad=0)
        self.tipo.maneja_stock = False
        self.tipo.save()

        self.assertEqual(len(selectores.historial_de_persona(self.persona, self.disp)), 1)

    def test_los_momentos_son_los_de_cada_operacion(self):
        self._entregas(2)
        ahora = timezone.now()

        historial = selectores.historial_de_persona(self.persona, self.disp)

        self.assertTrue(all(abs(h["creado_en"] - ahora) < timedelta(minutes=1) for h in historial))
