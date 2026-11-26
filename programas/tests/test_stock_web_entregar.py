"""«Entregar a persona» en la web (análisis 010, PR 5): permisos en las dos capas, GET que no escribe, saldo insuficiente,
idempotencia por ``uuid_cliente`` y privacidad del historial."""

import re
import uuid
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.urls import reverse

from legajos.models import Ciudadano
from programas.models import MiembroEquipoDispositivo, OperacionStock
from programas.tests.base_stock import BaseEntrega
from programas.views.stock import EntregarAPersonaView

Alcance = MiembroEquipoDispositivo.Alcance


class BaseWebEntregar(BaseEntrega):
    def setUp(self):
        super().setUp()
        self._sembrar(self.colchon, 5)
        self._sembrar(self.frazada, 2)

    def _url(self, dispositivo=None, edificio=None):
        return reverse(
            "dispositivos:stock_entregar", args=[(dispositivo or self.disp).pk, (edificio or self.edificio).pk]
        )

    def _entrar(self, usuario=None):
        self.client.force_login(User.objects.get(pk=(usuario or self.guardia).pk))

    def _datos(self, cantidades, uuid_cliente=None, dni="30111222", **extra):
        datos = {
            "dni": dni,
            "sexo": "",
            "nombre": "",
            "apellido": "",
            "uuid_cliente": str(uuid_cliente or uuid.uuid4()),
            "observacion": "",
        }
        for item, cantidad in cantidades.items():
            datos[f"cantidad_{item.pk}"] = cantidad
        datos.update(extra)
        return datos

    def _mensajes(self, respuesta):
        return [str(m) for m in get_messages(respuesta.wsgi_request)]


class PermisosDeLaVistaTests(BaseWebEntregar):
    def test_sin_sesion_va_al_login(self):
        respuesta = self.client.get(self._url())
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("next=", respuesta.url)

    def test_sin_stock_entregar_en_ningun_lado_es_403(self):
        lector = self._usuario_con("lector", ("stock.ver", "ciudadano.ver"))
        self._entrar(lector)
        self.assertEqual(self.client.get(self._url()).status_code, 403)
        self.assertEqual(self.client.post(self._url(), self._datos({self.colchon: 1})).status_code, 403)

    def test_sin_ciudadano_ver_es_403(self):
        sin_identidad = self._usuario_con("sin_identidad", ("stock.ver", "stock.entregar"))
        self._entrar(sin_identidad)
        self.assertEqual(self.client.get(self._url()).status_code, 403)

    def test_otra_institucion_y_su_edificio_son_404(self):
        self._entrar()
        self.assertEqual(self.client.get(self._url(self.disp_b, self.edificio_b)).status_code, 404)
        # Un edificio que no es de esta institución, aunque exista.
        self.assertEqual(self.client.get(self._url(self.disp, self.edificio_b)).status_code, 404)

    def test_un_edificio_fuera_del_alcance_del_equipo_es_404(self):
        """Con alcance por edificios, entregar en un edificio que no es de los suyos es 404 aunque la institución sea suya."""

        rol = self._rol("De un edificio", ("dispositivo.ver", "stock.ver", "stock.entregar", "ciudadano.ver"))
        usuario = self._usuario("solo_un_edificio", rol)
        miembro = MiembroEquipoDispositivo.objects.create(
            dispositivo=self.disp, usuario=usuario, rol=rol, alcance=Alcance.EDIFICIOS
        )
        miembro.edificios.set([self.otro_edificio])
        usuario = self._fresco(usuario)
        self._entrar(usuario)

        self.assertEqual(self.client.get(self._url(self.disp, self.edificio)).status_code, 404)
        self.assertEqual(self.client.post(self._url(), self._datos({self.colchon: 1})).status_code, 404)
        self.assertEqual(self.client.get(self._url(self.disp, self.otro_edificio)).status_code, 200)
        self.assertEqual(self._cantidad(self.colchon), 5)

    def test_con_lectura_de_toda_la_red_pero_operar_en_otro_edificio_es_404(self):
        """Primera capa, ``puede_operar_edificio``: leer todos los edificios no alcanza para entregar en uno ajeno."""

        rol = self._rol(
            "Lee todo, opera uno",
            ("dispositivo.ver", "dispositivo.ver_todos", "stock.ver", "stock.entregar", "ciudadano.ver"),
        )
        usuario = self._usuario("lee_todo_opera_uno", rol)
        miembro = MiembroEquipoDispositivo.objects.create(
            dispositivo=self.disp, usuario=usuario, rol=rol, alcance=Alcance.EDIFICIOS
        )
        miembro.edificios.set([self.otro_edificio])
        self._entrar(self._fresco(usuario))

        self.assertEqual(self.client.get(self._url(self.disp, self.edificio)).status_code, 404)
        self.assertEqual(self.client.get(self._url(self.disp, self.otro_edificio)).status_code, 200)

    def test_sin_stock_ver_es_403_en_el_get_sin_dni(self):
        """Primera capa, ``stock.ver``: sin ella la pantalla ni abre (el servicio solo cortaría al pedir un DNI)."""

        sin_ver = self._usuario_con("sin_ver", ("stock.entregar", "ciudadano.ver"))
        self._entrar(sin_ver)
        self.assertEqual(self.client.get(self._url()).status_code, 403)

    def test_un_post_sin_identificador_del_envio_muestra_el_error_arriba_y_no_entrega(self):
        """El error de un campo oculto no se vería: sube a los errores generales del formulario."""

        datos = self._datos({self.colchon: 1})
        datos.pop("uuid_cliente")
        self._entrar()
        respuesta = self.client.post(self._url(), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Falta el identificador del envío")
        self.assertEqual(self._cantidad(self.colchon), 5)

    def test_una_institucion_que_no_lleva_stock_es_404(self):
        self.tipo.maneja_stock = False
        self.tipo.save()
        self._entrar()
        self.assertEqual(self.client.get(self._url()).status_code, 404)

    def test_el_servicio_rechaza_aunque_la_vista_deje_pasar(self):
        """Segunda capa: sin el chequeo de la vista, el POST igual muere en el servicio y no escribe nada."""

        lector = self._usuario_con("lector2", ("stock.ver", "ciudadano.ver"))
        self._entrar(lector)

        def dejar_pasar(_vista, _usuario, _dispositivo_pk, _edificio_pk):
            return self.disp, self.edificio

        with patch.object(EntregarAPersonaView, "_lugar", dejar_pasar):
            respuesta = self.client.post(self._url(), self._datos({self.colchon: 1}))
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self._cantidad(self.colchon), 5)
        self.assertFalse(OperacionStock.objects.filter(tipo=OperacionStock.Tipo.ENTREGA_PERSONA).exists())


class ElGetNoEscribeTests(BaseWebEntregar):
    def setUp(self):
        super().setUp()
        self._entrar()

    def _nada_escrito(self, antes):
        self.assertEqual(Ciudadano.objects.count(), antes)
        self.assertFalse(OperacionStock.objects.filter(tipo=OperacionStock.Tipo.ENTREGA_PERSONA).exists())

    def test_sin_dni_muestra_solo_el_buscador(self):
        respuesta = self.client.get(self._url())
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Buscar persona")
        self.assertNotContains(respuesta, "Registrar entrega")

    def test_persona_con_legajo_muestra_historial_y_tabla_sin_escribir(self):
        antes = Ciudadano.objects.count()
        respuesta = self.client.get(self._url(), {"dni": "30111222"})
        self.assertContains(respuesta, "Paz, Ana")
        self.assertContains(respuesta, "Ya tiene legajo")
        self.assertContains(respuesta, "Todavía no recibió insumos")
        # La tabla de cantidades con el rótulo del stock y la columna informativa «En stock» (``rotulo_item``).
        self.assertContains(respuesta, ">Insumo</th>")
        self.assertContains(respuesta, ">En stock</th>")
        self.assertContains(respuesta, "Registrar entrega")
        self.assertContains(respuesta, "Colchón stock")
        self.assertNotContains(respuesta, "Insumo viejo")
        self._nada_escrito(antes)

    def test_un_insumo_sin_saldo_no_se_ofrece(self):
        self._sembrar(self.frazada, 0)
        respuesta = self.client.get(self._url(), {"dni": "30111222"})
        self.assertContains(respuesta, "Colchón stock")
        self.assertNotContains(respuesta, "Frazada stock")

    def test_persona_sin_legajo_ni_sexo_pide_el_sexo_y_no_consulta_el_registro(self):
        antes = Ciudadano.objects.count()
        with patch(self.CONSULTA_RENAPER) as renaper:
            respuesta = self.client.get(self._url(), {"dni": "27555666"})
        renaper.assert_not_called()
        self.assertContains(respuesta, "indicá su sexo")
        self.assertNotContains(respuesta, "Registrar entrega")
        self._nada_escrito(antes)

    def test_persona_del_registro_se_muestra_sin_darla_de_alta(self):
        antes = Ciudadano.objects.count()
        with patch(self.CONSULTA_RENAPER, return_value=self.RENAPER_ENCUENTRA):
            respuesta = self.client.get(self._url(), {"dni": "27555666", "sexo": "F"})
        self.assertContains(respuesta, "Ruiz, Marta")
        self.assertContains(respuesta, "Registro de Personas")
        self.assertContains(respuesta, "Registrar entrega")
        self._nada_escrito(antes)

    def test_persona_que_el_registro_no_tiene_pide_nombre_y_apellido(self):
        antes = Ciudadano.objects.count()
        with patch(self.CONSULTA_RENAPER, return_value=self.RENAPER_NO_ESTA):
            respuesta = self.client.get(self._url(), {"dni": "27555666", "sexo": "F"})
        self.assertContains(respuesta, "cargá su nombre y apellido")
        self.assertContains(respuesta, 'name="nombre"')
        self.assertNotContains(respuesta, "Registrar entrega")
        with patch(self.CONSULTA_RENAPER, return_value=self.RENAPER_NO_ESTA):
            respuesta = self.client.get(
                self._url(), {"dni": "27555666", "sexo": "F", "nombre": "Luz", "apellido": "Gómez"}
            )
        self.assertContains(respuesta, "Gómez, Luz")
        self.assertContains(respuesta, "Registrar entrega")
        self._nada_escrito(antes)

    def test_dni_invalido_y_fallecida_se_rechazan_en_el_campo(self):
        respuesta = self.client.get(self._url(), {"dni": "abc"})
        self.assertNotContains(respuesta, "Registrar entrega")
        self.assertTrue(respuesta.context["persona_form"].errors["dni"])
        with patch(self.CONSULTA_RENAPER, return_value=self.RENAPER_FALLECIDA):
            respuesta = self.client.get(self._url(), {"dni": "27555666", "sexo": "F"})
        self.assertIn("fallecida", respuesta.context["persona_form"].errors["dni"][0])

    def test_el_historial_nombra_solo_la_propia_institucion(self):
        self._sembrar(self.colchon, 3, self.edificio_b, self.disp_b)
        self._entregar(
            self._usuario_con("guardia_b", ("stock.ver", "stock.entregar", "ciudadano.ver"), self.disp_b),
            {self.colchon.pk: 2},
            dispositivo=self.disp_b,
            edificio=self.edificio_b,
        )
        self._entregar(lineas={self.frazada.pk: 1})
        respuesta = self.client.get(self._url(), {"dni": "30111222"})
        self.assertContains(respuesta, "Otra institución")
        self.assertContains(respuesta, self.disp.nombre)
        self.assertNotContains(respuesta, self.disp_b.nombre)
        self.assertNotContains(respuesta, self.edificio_b.nombre)


class ElPostEntregaTests(BaseWebEntregar):
    def setUp(self):
        super().setUp()
        self._entrar()

    def test_entrega_descuenta_asienta_y_vuelve_a_la_solapa(self):
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 3, self.frazada: 1}))
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.url.endswith("?tab=stock"))
        self.assertEqual(self._cantidad(self.colchon), 2)
        self.assertEqual(self._cantidad(self.frazada), 1)
        operacion = OperacionStock.objects.get(tipo=OperacionStock.Tipo.ENTREGA_PERSONA)
        self.assertEqual(operacion.ciudadano, self.persona)
        self.assertEqual(operacion.usuario, self.guardia)
        self.assertLibroCoherente()
        self.assertIn("Entrega registrada", self._mensajes(respuesta)[0])

    def test_cantidades_en_cero_o_vacias_no_se_descuentan(self):
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 2, self.frazada: 0}))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self._cantidad(self.frazada), 2)

    def test_sin_ninguna_cantidad_vuelve_con_el_error(self):
        respuesta = self.client.post(self._url(), self._datos({}))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["form"].non_field_errors())
        self.assertFalse(OperacionStock.objects.exists() and OperacionStock.objects.filter(ciudadano=self.persona))

    def test_saldo_insuficiente_vuelve_al_form_con_el_saldo_de_ahora(self):
        # Entre que se abrió la pantalla y se confirmó, otra entrega dejó 1.
        self._sembrar(self.colchon, 1)
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 4, self.frazada: 1}))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "No alcanza el stock")
        self.assertContains(respuesta, "Hay 1 y pediste 4.")
        # Todo o nada: ni siquiera la frazada que sí alcanzaba.
        self.assertEqual(self._cantidad(self.colchon), 1)
        self.assertEqual(self._cantidad(self.frazada), 2)
        self.assertFalse(OperacionStock.objects.filter(ciudadano=self.persona).exists())
        fila = next(f for f in respuesta.context["filas"] if f["nombre"] == "Colchón stock")
        self.assertEqual(fila["info"][0]["texto"], "1")
        # Lo que cargó la persona se conserva, y el identificador del envío es el mismo.
        self.assertEqual(respuesta.context["form"][f"cantidad_{self.colchon.pk}"].value(), "4")

    def _colchon_llega_a_cero(self):
        """Lo que pasa entre el GET y el POST: otra entrega se llevó todo el colchón."""

        self._sembrar(self.colchon, 0)

    def test_un_insumo_que_llega_a_cero_entre_el_get_y_el_post_no_entrega_el_resto_en_silencio(self):
        """Todo o nada: 3 colchones (ya sin stock) + 1 frazada no sale como «1 frazada» y «Entrega registrada»."""

        self._colchon_llega_a_cero()
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 3, self.frazada: 1}))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Hay 0 y pediste 3.")
        self.assertEqual(self._cantidad(self.frazada), 2)
        self.assertFalse(OperacionStock.objects.filter(tipo=OperacionStock.Tipo.ENTREGA_PERSONA).exists())
        self.assertFalse(self._mensajes(respuesta))
        # La fila del colchón sigue en pantalla, con lo cargado y el saldo de ahora.
        fila = next(f for f in respuesta.context["filas"] if f["nombre"] == "Colchón stock")
        self.assertEqual(fila["info"][0]["texto"], "0")
        self.assertEqual(respuesta.context["form"][f"cantidad_{self.colchon.pk}"].value(), "3")

    def test_un_insumo_en_cero_que_no_se_pidio_sigue_sin_ofrecerse_en_el_post(self):
        self._colchon_llega_a_cero()
        respuesta = self.client.post(self._url(), self._datos({self.frazada: 5}))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("Colchón stock", [f["nombre"] for f in respuesta.context["filas"]])

    def test_el_reintento_por_saldo_insuficiente_tambien_conserva_el_insumo_en_cero(self):
        """El segundo camino: el servicio contesta ``SaldoInsuficiente`` y el formulario se rearma con los saldos de ahora."""

        self._colchon_llega_a_cero()
        datos = self._datos({self.colchon: 3, self.frazada: 5})
        respuesta = self.client.post(self._url(), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Hay 0 y pediste 3.")
        self.assertContains(respuesta, "Hay 2 y pediste 5.")
        self.assertEqual(self._cantidad(self.frazada), 2)
        self.assertFalse(OperacionStock.objects.filter(tipo=OperacionStock.Tipo.ENTREGA_PERSONA).exists())

    def test_una_cantidad_de_un_insumo_sin_fila_alguna_se_rechaza_y_no_se_descarta(self):
        """Un insumo que nunca tuvo saldo en el edificio: la guarda del formulario, no un descarte silencioso."""

        datos = self._datos({self.frazada: 1}, **{"cantidad_999999": "2"})
        respuesta = self.client.post(self._url(), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Algún insumo ya no está en el stock de este edificio")
        self.assertEqual(self._cantidad(self.frazada), 2)

    def test_una_clave_de_cantidad_que_no_es_un_numero_se_rechaza_sin_dar_500(self):
        """``"²".isdigit()`` es verdadero y ``int("²")`` falla: un POST armado a mano no puede romper la vista."""

        for clave in ("cantidad_²", "cantidad_٣", "cantidad_1e3", "cantidad_-4", "cantidad_"):
            with self.subTest(clave=clave):
                datos = self._datos({self.frazada: 1}, **{clave: "2"})
                respuesta = self.client.post(self._url(), datos)
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, "Algún insumo ya no está en el stock de este edificio")
                self.assertEqual(self._cantidad(self.frazada), 2)

    def test_un_error_del_alta_en_un_campo_oculto_se_muestra_arriba(self):
        """Un nombre de 200 caracteres desde el Registro rompe el alta del legajo: el error sube, no se pierde."""

        largo = {"success": True, "data": {**self.RENAPER_ENCUENTRA["data"], "nombre": "N" * 200}}
        datos = self._datos({self.colchon: 1}, dni="27555666", sexo="F")
        with patch(self.CONSULTA_RENAPER, return_value=largo):
            respuesta = self.client.post(self._url(), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["form"].non_field_errors())
        self.assertFalse(Ciudadano.objects.filter(dni="27555666").exists())
        self.assertEqual(self._cantidad(self.colchon), 5)

    def test_el_rechazo_no_consulta_dos_veces_al_registro(self):
        """El servicio ya resolvió a la persona: mostrar el rechazo la reutiliza en vez de volver a la red."""

        datos = self._datos({self.colchon: 9}, dni="27555666", sexo="F")
        with patch(self.CONSULTA_RENAPER, return_value=self.RENAPER_ENCUENTRA) as consulta:
            respuesta = self.client.post(self._url(), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Hay 5 y pediste 9.")
        self.assertEqual(consulta.call_count, 1)

    def test_los_ids_de_la_pantalla_no_se_repiten_y_la_cantidad_anuncia_su_unidad(self):
        """Los ocultos de la entrega repiten ``dni`` y ``sexo`` del buscador: ids propios, y ``aria-describedby`` con la unidad."""

        respuesta = self.client.get(self._url(), {"dni": "30111222"})
        self.assertEqual(respuesta.status_code, 200)
        ids = re.findall(r'\sid="([^"]+)"', respuesta.content.decode())
        repetidos = {i for i in ids if ids.count(i) > 1}
        self.assertFalse(repetidos, repetidos)
        self.assertContains(respuesta, 'id="id_dni"')
        self.assertContains(respuesta, f'id="entrega_cantidad_{self.colchon.pk}"')
        self.assertContains(respuesta, f'aria-describedby="entrega_cantidad_{self.colchon.pk}-ayuda"')

    def test_doble_post_con_el_mismo_uuid_es_una_sola_operacion(self):
        datos = self._datos({self.colchon: 2})
        primera = self.client.post(self._url(), datos)
        segunda = self.client.post(self._url(), datos)
        self.assertEqual((primera.status_code, segunda.status_code), (302, 302))
        self.assertEqual(OperacionStock.objects.filter(tipo=OperacionStock.Tipo.ENTREGA_PERSONA).count(), 1)
        self.assertEqual(self._cantidad(self.colchon), 3)
        self.assertIn("ya estaba registrada", self._mensajes(segunda)[-1])
        self.assertLibroCoherente()

    def test_el_uuid_de_otro_usuario_no_entrega_y_se_regenera(self):
        usado = uuid.uuid4()
        self._entregar(self._otra_guardia(), {self.frazada.pk: 1}, uuid_cliente=usado)
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 1}, uuid_cliente=usado))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self._cantidad(self.colchon), 5)
        self.assertNotEqual(str(respuesta.context["form"]["uuid_cliente"].value()), str(usado))

    def _otra_guardia(self):
        return self._usuario_con("guardia2", ("stock.ver", "stock.entregar", "ciudadano.ver"))

    def test_persona_nueva_se_da_de_alta_al_entregar(self):
        with patch(self.CONSULTA_RENAPER, return_value=self.RENAPER_ENCUENTRA):
            respuesta = self.client.post(self._url(), self._datos({self.colchon: 1}, dni="27555666", sexo="F"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Ciudadano.objects.get(dni="27555666").apellido, "Ruiz")

    def test_la_cantidad_invalida_vuelve_en_su_fila(self):
        respuesta = self.client.post(self._url(), self._datos({self.colchon: "-2"}))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["form"].errors[f"cantidad_{self.colchon.pk}"])
        self.assertEqual(self._cantidad(self.colchon), 5)

    def test_una_institucion_inactiva_vuelve_con_el_motivo(self):
        self.disp.estado = self.disp.Estado.INACTIVO
        self.disp.save()
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 1}))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "no está activa")
        self.assertEqual(self._cantidad(self.colchon), 5)
