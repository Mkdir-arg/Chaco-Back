"""«Insumos» de Emergencia (Cambio 578): el catálogo de lo que la mesa envía, con su alta y edición en un modal.

Qué fija este archivo, regla por regla:

* **Regla 1** — un insumo ya usado en alguna entrega no cambia de nombre ni de unidad: lo rechaza
  el servicio (la vista no es la única puerta) y el formulario lo muestra de solo lectura. Se puede
  desactivar y se puede ajustar su consumo estimado.
* **RN-4.7** — un insumo no se borra: se desactiva y se vuelve a activar, con su traza.
* **`LineaEntrega.nombre`** — la línea copia el nombre al crearse y las pantallas la leen con
  respaldo en el ítem; la migración de datos rellena lo viejo sin pisar lo que ya tiene nombre.
* **Sin formset ni fila vacía** — cada guardado es un insumo; «Guardar y cargar otro» reabre el alta.
"""

import importlib
from decimal import Decimal

from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from programas.models import LineaEntrega, TipoKit, TrazaConfiguracion
from programas.selectors import emergencia_insumos as selector
from programas.services import configuracion_emergencia as servicio
from programas.services import pantalla_abastecimiento_emergencia as pantalla
from programas.tests.test_emergencia_kits import BaseKits

URL_INSUMOS = "/emergencia/config/insumos/"


class BaseInsumos(BaseKits):
    """El catálogo de ``BaseKits`` (colchón, kit alimentario, agua) y un supervisor ya logueado."""

    def setUp(self):
        super().setUp()
        self.url = reverse("emergencia:insumos")
        self.client.force_login(self.supervisor)

    def _form_de(self, tipo, **cambios):
        """Lo que mandaría el modal al editar ``tipo``: sus valores de hoy más ``cambios``."""
        datos = {
            "insumo": tipo.pk,
            "nombre": tipo.nombre,
            "unidad": tipo.unidad,
            "regla_modo": tipo.regla_modo,
            "regla_cantidad": "" if tipo.regla_cantidad is None else str(tipo.regla_cantidad),
            "regla_por": tipo.regla_por,
            "regla_cada_dias": "" if tipo.regla_cada_dias is None else str(tipo.regla_cada_dias),
        }
        datos.update(cambios)
        return datos

    def _trazas(self):
        return {t.campo: (t.valor_anterior, t.valor_nuevo) for t in TrazaConfiguracion.objects.all()}


class AccesoInsumosTests(BaseInsumos):
    def test_sin_login_redirige_al_login(self):
        self.client.logout()
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, f"{reverse('users:login')}?next={self.url}")
        self.assertEqual(self.client.post(self.url, {}).status_code, 302)

    def test_la_url_es_la_del_namespace_emergencia(self):
        self.assertEqual(self.url, URL_INSUMOS)

    def test_sin_supervisar_rechaza_todo(self):
        for usuario in (self._usuario("sin_rol"), self.operador):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                self.assertEqual(self.client.get(self.url).status_code, 403)
                self.assertEqual(
                    self.client.post(self.url, {"nombre": "Pañales", "unidad": "paquete"}).status_code, 403
                )
                self.assertEqual(
                    self.client.post(reverse("emergencia:insumo_desactivar", args=[self.agua.pk])).status_code, 403
                )
                self.assertEqual(
                    self.client.post(reverse("emergencia:insumo_activar", args=[self.agua.pk])).status_code, 403
                )
        self.assertEqual(TipoKit.objects.count(), 3)
        self.assertTrue(TipoKit.objects.get(pk=self.agua.pk).activo)

    def test_con_supervisar_abre_el_listado(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "programas/emergencia/insumos.html")
        self.assertContains(respuesta, "Nuevo insumo")

    def test_la_url_vieja_lleva_a_insumos(self):
        respuesta = self.client.get("/emergencia/config/")
        self.assertRedirects(respuesta, self.url, fetch_redirect_response=False)
        self.assertEqual(reverse("emergencia:configuracion"), "/emergencia/config/")

    def test_la_url_vieja_exige_sesion_y_supervisar(self):
        self.client.logout()
        anonimo = self.client.get("/emergencia/config/")
        self.assertEqual(anonimo.status_code, 302)
        self.assertIn("next=/emergencia/config/", anonimo.url)
        self.client.force_login(self.operador)
        self.assertEqual(self.client.get("/emergencia/config/").status_code, 403)

    def test_el_menu_tiene_las_dos_entradas_y_marca_la_actual(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn('href="/emergencia/config/insumos/"', html)
        self.assertIn('href="/emergencia/config/plazos/"', html)
        self.assertNotIn('href="/emergencia/config/"', html)


class ListadoDeInsumosTests(BaseInsumos):
    def test_muestra_nombre_unidad_estado_y_en_cuantas_entregas_se_uso(self):
        self._entrega(lineas=[(self.colchon, 2)])
        self._entrega(lineas=[(self.colchon, 1), (self.agua, 1)])
        insumos = {i.nombre: i for i in self.client.get(self.url).context["insumos"]}
        self.assertEqual(
            {n: i.entregas for n, i in insumos.items()}, {"Colchón": 2, "Kit alimentario": 0, "Agua 6 l": 1}
        )
        html = self.client.get(self.url).content.decode()
        self.assertIn("2 entregas", html)
        self.assertRegex(html, r"1 entrega(?!s)")
        self.assertIn("Sin entregas", html)

    def test_los_chips_filtran_y_cuentan(self):
        TipoKit.objects.filter(pk=self.agua.pk).update(activo=False)
        for estado, esperado in (
            ("activos", {"Colchón", "Kit alimentario"}),
            ("inactivos", {"Agua 6 l"}),
            ("todos", {"Colchón", "Kit alimentario", "Agua 6 l"}),
            ("cualquier-cosa", {"Colchón", "Kit alimentario"}),
        ):
            with self.subTest(estado=estado):
                respuesta = self.client.get(self.url, {"estado": estado})
                self.assertEqual({i.nombre for i in respuesta.context["insumos"]}, esperado)
        chips = {c["texto"]: c["n"] for c in self.client.get(self.url).context["chips"]}
        self.assertEqual(chips, {"Activos": 2, "Inactivos": 1, "Todos": 3})

    def test_con_inactivos_pero_ningun_activo_dice_que_no_hay_en_esta_vista(self):
        TipoKit.objects.update(activo=False)
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, "No hay insumos en esta vista")
        self.assertNotContains(respuesta, "Todavía no hay insumos")

    def test_sin_insumos_ofrece_cargar_el_primero(self):
        TipoKit.objects.all().delete()
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, "Todavía no hay insumos")
        self.assertContains(respuesta, f'href="{self.url}?estado=activos&amp;nuevo=1"')

    def test_el_consumo_se_dice_en_palabras(self):
        casos = (
            (dict(), pantalla.TEXTO_SIN_ESTIMAR),
            (dict(regla_modo="DOTACION", regla_cantidad=1, regla_por="PERSONA"), "1 por persona, una sola vez"),
            (
                dict(regla_modo="REPOSICION", regla_cantidad="0.5", regla_por="FAMILIA", regla_cada_dias=1),
                "0,5 por familia por día",
            ),
            (
                dict(regla_modo="REPOSICION", regla_cantidad=1, regla_por="FAMILIA", regla_cada_dias=7),
                "1 por familia cada 7 días",
            ),
        )
        for i, (campos, texto) in enumerate(casos):
            with self.subTest(texto=texto):
                if "regla_cantidad" in campos:
                    campos["regla_cantidad"] = Decimal(str(campos["regla_cantidad"]))
                tipo = TipoKit(nombre=f"X{i}", unidad="u", **campos)
                self.assertEqual(pantalla.texto_de_consumo(tipo), texto)

    def test_el_listado_no_hace_una_consulta_por_fila(self):
        for i in range(10):
            TipoKit.objects.create(nombre=f"Extra {i}", unidad="u")
        with self.assertNumQueries(2):  # los insumos con su conteo de entregas, y las cuentas de los chips
            list(selector.insumos_del_catalogo("todos"))
            selector.conteos_de_insumos()


class AltaDeInsumosTests(BaseInsumos):
    def test_un_insumo_nuevo_queda_ultimo_en_el_catalogo_de_las_entregas(self):
        """Va al final aunque su nombre ordene antes: el orden es ``orden`` y después el nombre."""
        mayor = max(TipoKit.objects.values_list("orden", flat=True))
        self.assertEqual(
            self.client.post(self.url, {"regla_modo": "", "nombre": "Almohada", "unidad": "u"}).status_code, 302
        )
        self.assertEqual(
            self.client.post(self.url, {"regla_modo": "", "nombre": "Abrigo", "unidad": "u"}).status_code, 302
        )
        catalogo = list(TipoKit.objects.filter(activo=True).values_list("nombre", flat=True))
        self.assertEqual(catalogo[-2:], ["Almohada", "Abrigo"])
        self.assertEqual(TipoKit.objects.get(nombre="Abrigo").orden, mayor + 2)

    def test_nuevo_abre_el_modal_vacio(self):
        respuesta = self.client.get(self.url, {"nuevo": 1})
        self.assertTrue(respuesta.context["abre_modal"])
        self.assertIsNone(respuesta.context["editando"])
        self.assertContains(respuesta, 'aria-labelledby="modal-insumo-titulo"')
        self.assertNotContains(respuesta, 'name="insumo"')

    def test_sin_parametros_no_dibuja_el_modal(self):
        respuesta = self.client.get(self.url)
        self.assertFalse(respuesta.context["abre_modal"])
        self.assertNotContains(respuesta, "modal-insumo-titulo")

    def test_se_crea_un_insumo_y_deja_la_traza_del_alta(self):
        respuesta = self.client.post(self.url, {"nombre": "Pañales", "unidad": "paquete", "regla_modo": ""})
        self.assertRedirects(respuesta, f"{self.url}?estado=activos", fetch_redirect_response=False)
        tipo = TipoKit.objects.get(nombre="Pañales")
        self.assertEqual((tipo.unidad, tipo.activo, tipo.regla_modo), ("paquete", True, ""))
        traza = TrazaConfiguracion.objects.get()
        self.assertEqual(
            (traza.campo, traza.valor_nuevo, traza.usuario_id),
            (servicio.CAMPO_ALTA, "Pañales (paquete)", self.supervisor.pk),
        )

    def test_guardar_y_cargar_otro_reabre_el_alta(self):
        respuesta = self.client.post(
            self.url, {"nombre": "Pañales", "unidad": "paquete", "regla_modo": "", "continuar": "1", "estado": "todos"}
        )
        self.assertRedirects(respuesta, f"{self.url}?estado=todos&nuevo=1", fetch_redirect_response=False)
        self.assertTrue(TipoKit.objects.filter(nombre="Pañales").exists())

    def test_el_estado_viaja_y_uno_inventado_no(self):
        respuesta = self.client.post(self.url, {"nombre": "A", "unidad": "u", "regla_modo": "", "estado": "inventado"})
        self.assertEqual(respuesta.url, f"{self.url}?estado=activos")

    def test_los_errores_vuelven_con_el_modal_abierto_y_no_guardan(self):
        casos = {
            "nombre duplicado": ({"nombre": " colchón ", "unidad": "u"}, servicio.MENSAJE_NOMBRE_DUPLICADO),
            "sin unidad": ({"nombre": "Pañales", "unidad": ""}, "requerido"),
            "sin nombre": ({"nombre": "", "unidad": "u"}, "requerido"),
        }
        for caso, (datos, texto) in casos.items():
            with self.subTest(caso=caso):
                respuesta = self.client.post(self.url, {"regla_modo": "", **datos})
                self.assertEqual(respuesta.status_code, 400)
                self.assertTrue(respuesta.context["abre_modal"])
                self.assertContains(respuesta, texto, status_code=400)
                self.assertEqual(TipoKit.objects.count(), 3)
        self.assertFalse(TrazaConfiguracion.objects.exists())

    def test_el_alta_lleva_la_regla_de_consumo_y_la_traza(self):
        datos = {"nombre": "Pañales", "unidad": "paquete", "regla_modo": "REPOSICION"}
        datos |= {"regla_cantidad": "1", "regla_por": "LACTANTE", "regla_cada_dias": "3"}
        self.assertEqual(self.client.post(self.url, datos).status_code, 302)
        tipo = TipoKit.objects.get(nombre="Pañales")
        self.assertEqual((tipo.regla_modo, tipo.regla_por, tipo.regla_cada_dias), ("REPOSICION", "LACTANTE", 3))
        self.assertEqual(
            set(self._trazas()), {servicio.CAMPO_ALTA, "regla_modo", "regla_cantidad", "regla_por", "regla_cada_dias"}
        )

    def test_el_modal_explica_que_la_regla_no_es_stock(self):
        """#1365: «Cantidad» se leyó como raciones disponibles; el campo es el consumo de cada persona, familia o lactante."""
        respuesta = self.client.get(self.url, {"nuevo": 1})
        self.assertContains(respuesta, "Consumo por unidad")
        self.assertNotContains(respuesta, ">Cantidad<")
        self.assertContains(respuesta, "No es stock")
        self.assertContains(respuesta, "Ej.: 3 raciones por persona cada 1 día")


class EdicionDeInsumosTests(BaseInsumos):
    def test_editar_abre_el_modal_con_ese_insumo(self):
        respuesta = self.client.get(self.url, {"editar": self.agua.pk})
        self.assertTrue(respuesta.context["abre_modal"])
        self.assertEqual(respuesta.context["editando"], self.agua)
        self.assertContains(respuesta, f'name="insumo" value="{self.agua.pk}"')

    def test_un_id_que_no_existe_o_armado_a_mano_no_abre_nada(self):
        for valor in ("999999", "abc", "-1", "9" * 30):
            with self.subTest(editar=valor):
                respuesta = self.client.get(self.url, {"editar": valor})
                self.assertEqual(respuesta.status_code, 200)
                self.assertFalse(respuesta.context["abre_modal"])
        self.assertEqual(self.client.post(self.url, self._form_de(self.agua, insumo=999999)).status_code, 404)
        self.assertEqual(self.client.post(self.url, self._form_de(self.agua, insumo="abc")).status_code, 404)

    def test_sin_entregas_se_renombra_y_cambia_de_unidad(self):
        respuesta = self.client.post(self.url, self._form_de(self.agua, nombre="Agua 10 l", unidad="botellón"))
        self.assertEqual(respuesta.status_code, 302)
        self.agua.refresh_from_db()
        self.assertEqual((self.agua.nombre, self.agua.unidad), ("Agua 10 l", "botellón"))
        self.assertEqual(self._trazas(), {"nombre": ("Agua 6 l", "Agua 10 l"), "unidad": ("bidón", "botellón")})

    def test_se_puede_renombrar_a_si_mismo_sin_que_cuente_como_duplicado(self):
        self.assertEqual(self.client.post(self.url, self._form_de(self.agua, unidad="pack")).status_code, 302)

    def test_renombrar_al_nombre_de_otro_se_rechaza(self):
        respuesta = self.client.post(self.url, self._form_de(self.agua, nombre="colchón"))
        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, servicio.MENSAJE_NOMBRE_DUPLICADO, status_code=400)
        self.agua.refresh_from_db()
        self.assertEqual(self.agua.nombre, "Agua 6 l")

    def test_regla_1_un_insumo_usado_muestra_nombre_y_unidad_de_solo_lectura_y_dice_por_que(self):
        self._entrega(lineas=[(self.agua, 3)])
        respuesta = self.client.get(self.url, {"editar": self.agua.pk})
        form = respuesta.context["form"]
        self.assertTrue(form.en_uso)
        self.assertTrue(form.fields["nombre"].disabled and form.fields["unidad"].disabled)
        self.assertFalse(form.fields["regla_modo"].disabled)
        self.assertContains(respuesta, "no se pueden cambiar")
        self.assertContains(respuesta, "desactivalo y cargá uno nuevo")

    def test_regla_1_sin_entregas_el_formulario_no_lo_bloquea(self):
        form = self.client.get(self.url, {"editar": self.agua.pk}).context["form"]
        self.assertFalse(form.en_uso)
        self.assertFalse(form.fields["nombre"].disabled)

    def test_regla_1_un_post_armado_a_mano_no_cambia_nombre_ni_unidad_de_un_insumo_usado(self):
        self._entrega(lineas=[(self.agua, 3)])
        datos = self._form_de(self.agua, nombre="Otro nombre", unidad="otra", regla_modo="DOTACION")
        datos |= {"regla_cantidad": "1", "regla_por": "PERSONA"}
        self.assertEqual(self.client.post(self.url, datos).status_code, 302)
        self.agua.refresh_from_db()
        self.assertEqual((self.agua.nombre, self.agua.unidad), ("Agua 6 l", "bidón"))
        self.assertEqual(self.agua.regla_modo, "DOTACION")  # el consumo sí se ajusta
        self.assertEqual(set(self._trazas()), {"regla_modo", "regla_cantidad", "regla_por"})


class ReglaUnoDelServicioTests(BaseInsumos):
    """El servicio lo exige por su cuenta: el formulario deshabilitado no es la única puerta."""

    def test_un_insumo_usado_no_cambia_de_nombre(self):
        self._entrega(lineas=[(self.agua, 3)])
        with self.assertRaises(ValidationError) as error:
            servicio.editar_tipo_kit(self.supervisor, self.agua, nombre="Agua 10 l")
        self.assertIn("nombre", error.exception.message_dict)
        self.agua.refresh_from_db()
        self.assertEqual(self.agua.nombre, "Agua 6 l")
        self.assertFalse(TrazaConfiguracion.objects.exists())

    def test_un_insumo_usado_no_cambia_de_unidad(self):
        self._entrega(lineas=[(self.agua, 3)])
        with self.assertRaises(ValidationError) as error:
            servicio.editar_tipo_kit(self.supervisor, self.agua, unidad="pack")
        self.assertIn("unidad", error.exception.message_dict)
        self.agua.refresh_from_db()
        self.assertEqual(self.agua.unidad, "bidón")

    def test_cambiar_los_dos_a_la_vez_rechaza_los_dos_y_no_guarda_ni_la_regla(self):
        self._entrega(lineas=[(self.agua, 3)])
        with self.assertRaises(ValidationError) as error:
            servicio.editar_tipo_kit(
                self.supervisor,
                self.agua,
                nombre="X",
                unidad="y",
                regla_modo="DOTACION",
                regla_cantidad=1,
                regla_por="PERSONA",
            )
        self.assertEqual(set(error.exception.message_dict), {"nombre", "unidad"})
        self.agua.refresh_from_db()
        self.assertEqual(self.agua.regla_modo, "")

    def test_un_insumo_usado_si_se_desactiva_y_ajusta_su_consumo(self):
        self._entrega(lineas=[(self.agua, 3)])
        servicio.cambiar_estado_tipo_kit(self.supervisor, self.agua, False)
        servicio.editar_tipo_kit(
            self.supervisor, self.agua, regla_modo="DOTACION", regla_cantidad=1, regla_por="PERSONA"
        )
        self.agua.refresh_from_db()
        self.assertEqual((self.agua.activo, self.agua.regla_modo), (False, "DOTACION"))

    def test_mandar_el_mismo_nombre_y_unidad_de_un_insumo_usado_no_es_un_cambio(self):
        self._entrega(lineas=[(self.agua, 3)])
        servicio.editar_tipo_kit(self.supervisor, self.agua, nombre=" Agua  6 l ", unidad="bidón")
        self.assertFalse(TrazaConfiguracion.objects.exists())

    def test_un_insumo_que_no_se_uso_se_corrige(self):
        servicio.editar_tipo_kit(self.supervisor, self.agua, nombre="Agua 10 l", unidad="botellón")
        self.agua.refresh_from_db()
        self.assertEqual((self.agua.nombre, self.agua.unidad), ("Agua 10 l", "botellón"))

    def test_una_entrega_cancelada_tambien_cuenta_como_uso(self):
        entrega = self._entrega(lineas=[(self.agua, 3)])
        servicio_kits = importlib.import_module("programas.services.kits")
        servicio_kits.cancelar_entrega(entrega, self.operador, "Error de carga")
        with self.assertRaises(ValidationError):
            servicio.editar_tipo_kit(self.supervisor, self.agua, nombre="Agua 10 l")

    def test_el_servicio_exige_supervisar(self):
        with self.assertRaises(PermissionDenied):
            servicio.editar_tipo_kit(self.operador, self.agua, unidad="pack")


class ActivarYDesactivarTests(BaseInsumos):
    def test_se_desactiva_con_post_y_no_se_borra(self):
        respuesta = self.client.post(reverse("emergencia:insumo_desactivar", args=[self.agua.pk]) + "?estado=todos")
        self.assertRedirects(respuesta, f"{self.url}?estado=todos", fetch_redirect_response=False)
        self.agua.refresh_from_db()
        self.assertFalse(self.agua.activo)
        self.assertEqual(TipoKit.objects.count(), 3)
        self.assertEqual(self._trazas(), {"activo": ("Sí", "No")})
        self.assertNotIn(self.agua, servicio.catalogo_kits(solo_activos=True))

    def test_se_vuelve_a_activar(self):
        TipoKit.objects.filter(pk=self.agua.pk).update(activo=False)
        self.client.post(reverse("emergencia:insumo_activar", args=[self.agua.pk]))
        self.agua.refresh_from_db()
        self.assertTrue(self.agua.activo)

    def test_solo_por_post(self):
        for nombre in ("insumo_desactivar", "insumo_activar"):
            self.assertEqual(self.client.get(reverse(f"emergencia:{nombre}", args=[self.agua.pk])).status_code, 405)
        self.assertTrue(TipoKit.objects.get(pk=self.agua.pk).activo)

    def test_un_insumo_que_no_existe_es_404(self):
        self.assertEqual(self.client.post(reverse("emergencia:insumo_desactivar", args=[999999])).status_code, 404)

    def test_la_lista_confirma_antes_de_desactivar_y_no_ofrece_borrar(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn("data-confirm-url", html)
        self.assertIn("¿Desactivar el insumo?", html)
        self.assertNotIn("eliminar", html.lower())
        self.assertNotIn("-DELETE", html)

    def test_desactivar_dos_veces_no_deja_una_segunda_traza(self):
        url = reverse("emergencia:insumo_desactivar", args=[self.agua.pk])
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(TrazaConfiguracion.objects.filter(campo="activo").count(), 1)


class NombreDeLaLineaTests(BaseInsumos):
    def test_la_linea_copia_el_nombre_al_crearse(self):
        entrega = self._entrega(lineas=[(self.agua, 6)])
        linea = entrega.lineas.select_related("item").get()
        self.assertEqual((linea.nombre, linea.unidad), ("Agua 6 l", "bidón"))

    def test_la_entrega_vieja_sigue_diciendo_lo_que_se_mando(self):
        entrega = self._entrega(lineas=[(self.agua, 6)])
        TipoKit.objects.filter(pk=self.agua.pk).update(nombre="Agua 10 l")  # lo que el servicio ya impide
        linea = entrega.lineas.select_related("item").get()
        self.assertEqual(linea.nombre_visible, "Agua 6 l")
        self.assertEqual(linea.item.nombre, "Agua 10 l")

    def test_sin_copia_vale_el_nombre_del_item(self):
        entrega = self._entrega(lineas=[(self.agua, 6)])
        LineaEntrega.objects.filter(entrega=entrega).update(nombre=None)
        linea = entrega.lineas.select_related("item").get()
        self.assertEqual(linea.nombre_visible, "Agua 6 l")
        self.assertIn("Agua 6 l", str(linea))

    def test_las_pantallas_de_entregas_leen_el_nombre_de_la_linea(self):
        entrega = self._entrega(lineas=[(self.agua, 6)])
        LineaEntrega.objects.filter(entrega=entrega).update(nombre="Agua de antes")
        respuesta = self.client.get(reverse("emergencia:entrega_detalle", args=[entrega.pk]))
        self.assertContains(respuesta, "Agua de antes")
        self.assertNotContains(respuesta, "Agua 6 l")

    def test_la_api_de_la_guardia_conserva_la_clave_nombre(self):
        from programas.api.serializers_emergencia_kits import LineaEntregaKitSerializer

        entrega = self._entrega(lineas=[(self.agua, 6)])
        LineaEntrega.objects.filter(entrega=entrega).update(nombre="Agua de antes")
        linea = entrega.lineas.select_related("item").get()
        dato = LineaEntregaKitSerializer(linea).data
        self.assertEqual(list(dato), ["item", "nombre", "unidad", "enviada", "recibida"])
        self.assertEqual(dato["nombre"], "Agua de antes")


class MigracionDelNombreTests(BaseInsumos):
    """0141: rellena lo viejo, sin pisar lo que ya tiene nombre, y se puede correr de nuevo."""

    def _correr(self):
        modulo = importlib.import_module("programas.migrations.0141_linea_entrega_nombre_datos")
        modulo.rellenar_nombre(apps, None)

    def test_rellena_solo_las_que_no_tienen_nombre_y_es_idempotente(self):
        vieja = self._entrega(lineas=[(self.colchon, 1)]).lineas.get()
        con_nombre = self._entrega(lineas=[(self.agua, 1)]).lineas.get()
        LineaEntrega.objects.filter(pk=vieja.pk).update(nombre=None)
        LineaEntrega.objects.filter(pk=con_nombre.pk).update(nombre="Agua de antes")

        self._correr()
        self._correr()

        vieja.refresh_from_db()
        con_nombre.refresh_from_db()
        self.assertEqual(vieja.nombre, "Colchón")
        self.assertEqual(con_nombre.nombre, "Agua de antes")
        self.assertFalse(LineaEntrega.objects.filter(nombre__isnull=True).exists())

    def test_la_reversa_esta_declarada(self):
        modulo = importlib.import_module("programas.migrations.0141_linea_entrega_nombre_datos")
        operacion = modulo.Migration.operations[0]
        self.assertIsNotNone(operacion.reverse_code)
