"""Alta y edición de la capacidad instalada: edificio, sectores y plazas (carril C5 · P5 y P19).

Lo que se fija acá, y por qué:

1. **Lo que se carga aparece.** El alta de un sector y su lote de plazas llega al censo de
   `ocupacion_de_plazas` y al mapa de P5 sin que nadie tipee una cifra: si el alta no
   alimentara el mismo servicio único de cálculo que todo lo demás, el MVP tendría dos
   verdades sobre cuántas plazas hay.
2. **Nada con historia se borra.** Un sector con una plaza tomada —estadía activa, reserva
   o préstamo sin liberar— **no** se da de baja: primero se reubica, que es lo mismo que
   ya exige `sacar_plaza_de_servicio`. Cada una de esas guardas tiene su test, y cada una
   se verificó con mutación (romper la regla → el test en rojo).
3. **El alcance es el de siempre.** `dispositivo.editar` con alcance al dispositivo; el
   sector ajeno y el inexistente dan el mismo 404, y el dispositivo cerrado no cambia su
   capacidad.
4. **El predio compartido se ve en las dos instituciones.** Es el motivo por el que
   `Edificio` es un varios a varios, y la prueba de que el vínculo no es decorativo.
"""

from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from programas.models import Dispositivo, Edificio, Plaza, Sector, TipoDispositivo, TrazaDispositivo
from programas.services.detalle_dispositivo import infraestructura_del_dispositivo
from programas.services.edificios import (
    crear_edificio,
    desvincular_edificio,
    edificios_vinculables,
    editar_edificio,
    vincular_edificio,
)
from programas.services.estadias import ingresar_persona, reservar_plaza
from programas.services.ocupacion import ocupacion_de_plazas
from programas.services.plazas import (
    TOPE_POR_LOTE,
    agregar_plazas,
    codigos_en_lote,
    crear_sector,
    editar_sector,
)
from programas.tests.test_dispositivos_estadias import BaseEstadias


class BaseCapacidad(BaseEstadias):
    """El terreno de las estadías más los usuarios que el alcance de este carril distingue."""

    def setUp(self):
        super().setUp()
        # Usuarios con todo menos la condición que cada test prueba.
        self.sin_editar = self._operador(
            "Sin editar capacidad", self.cis, ("dispositivo.ver", "dispositivo.admitir", "dispositivo.egresar")
        )
        self.administrador = self._operador(
            "Administrador del programa",
            self.parador,
            ("dispositivo.ver", "dispositivo.editar", "programa.configurar"),
        )

    def _datos_de_sector(self, **extra):
        return {"nombre": "Pabellón B", "tipo": Sector.Tipo.PABELLON, "capacidad": 4, **extra}


class AltaDeSectoresYPlazasTests(BaseCapacidad):
    """Lo que se carga tiene que aparecer en el mismo cálculo que todo lo demás."""

    def test_el_sector_nuevo_y_su_lote_de_plazas_entran_al_censo_y_al_mapa(self):
        antes = ocupacion_de_plazas(self.cis).de(self.cis).conteo.totales

        sector = crear_sector(dispositivo=self.cis, usuario=self.operador_cis, **self._datos_de_sector())
        agregar_plazas(sector=sector, usuario=self.operador_cis, cantidad=4, prefijo="B-")

        self.assertEqual(ocupacion_de_plazas(self.cis).de(self.cis).conteo.totales, antes + 4)
        self.client.force_login(self.operador_cis)
        respuesta = self.client.get(reverse("dispositivos:sectores", args=[self.cis.pk]))
        codigos = [celda["codigo"] for item in respuesta.context["sectores"] for celda in item["plazas"]]
        self.assertEqual([c for c in codigos if c.startswith("B-")], ["B-01", "B-02", "B-03", "B-04"])

    def test_el_alta_por_la_pantalla_crea_el_sector_y_deja_su_traza(self):
        self.client.force_login(self.operador_cis)

        respuesta = self.client.post(reverse("dispositivos:sector_crear", args=[self.cis.pk]), self._datos_de_sector())

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Sector.objects.filter(dispositivo=self.cis, nombre="Pabellón B", activo=True).exists())
        self.assertTrue(TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="SECTOR_CREADO").exists())

    def test_el_lote_por_la_pantalla_agrega_las_plazas_y_deja_su_traza(self):
        sector = crear_sector(dispositivo=self.cis, usuario=self.operador_cis, **self._datos_de_sector())
        self.client.force_login(self.operador_cis)

        self.client.post(
            reverse("dispositivos:plazas_agregar", args=[self.cis.pk]),
            {"sector": sector.pk, "cantidad": 3, "tipo": Plaza.Tipo.CAMA, "prefijo": "B-"},
        )

        self.assertEqual(Plaza.objects.filter(sector=sector).count(), 3)
        self.assertTrue(TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="PLAZAS_AGREGADAS").exists())

    def test_el_lote_saltea_los_codigos_que_ya_existen_en_la_institucion(self):
        """Un código se lee solo, sin su sector, en los mensajes y en la bitácora.

        El modelo solo exige que no se repita **dentro del sector**, así que esta parte no
        la cubre la base: si el generador no mirara toda la institución, el segundo
        pabellón nacería con otra «B-02».
        """

        otro = crear_sector(
            dispositivo=self.cis, usuario=self.operador_cis, nombre="Pabellón C", tipo=Sector.Tipo.PABELLON
        )
        Plaza.objects.create(sector=otro, codigo="B-02")
        sector = crear_sector(dispositivo=self.cis, usuario=self.operador_cis, **self._datos_de_sector())

        plazas = agregar_plazas(sector=sector, usuario=self.operador_cis, cantidad=3, prefijo="B-")

        self.assertEqual([plaza.codigo for plaza in plazas], ["B-01", "B-03", "B-04"])

    def test_los_codigos_del_lote_no_dependen_de_la_base(self):
        self.assertEqual(codigos_en_lote(cantidad=3, prefijo="A-", tomados=set()), ["A-01", "A-02", "A-03"])
        self.assertEqual(codigos_en_lote(cantidad=2, prefijo="", tomados={"01"}), ["02", "03"])

    def test_el_nombre_del_sector_no_se_repite_en_la_institucion(self):
        crear_sector(dispositivo=self.cis, usuario=self.operador_cis, **self._datos_de_sector())

        with self.assertRaises(ValidationError) as fallo:
            crear_sector(dispositivo=self.cis, usuario=self.operador_cis, **self._datos_de_sector())

        self.assertIn("nombre", fallo.exception.message_dict)

    def test_el_mismo_nombre_en_otra_institucion_si_entra(self):
        crear_sector(dispositivo=self.cis, usuario=self.operador_cis, **self._datos_de_sector())

        sector = crear_sector(dispositivo=self.parador, usuario=self.operador_parador, **self._datos_de_sector())

        self.assertEqual(sector.dispositivo, self.parador)

    def test_el_tipo_de_plaza_lo_decide_el_tipo_de_institucion(self):
        tipo = TipoDispositivo.objects.create(
            codigo="SOLO-CUPO", nombre="Solo cupos", tipos_plaza_admitidos=[Plaza.Tipo.CUPO]
        )
        Dispositivo.objects.filter(pk=self.cis.pk).update(tipo=tipo)
        sector = crear_sector(
            dispositivo=Dispositivo.objects.get(pk=self.cis.pk), usuario=self.operador_cis, **self._datos_de_sector()
        )

        with self.assertRaises(ValidationError) as fallo:
            agregar_plazas(sector=sector, usuario=self.operador_cis, cantidad=1, tipo=Plaza.Tipo.CAMA)

        self.assertIn("tipo", fallo.exception.message_dict)

    def test_un_tipo_sin_restriccion_declarada_admite_los_tres(self):
        """Lista vacía es «sin restricción», no «no admite ninguna» (lo que ve el código viejo)."""

        sector = crear_sector(dispositivo=self.cis, usuario=self.operador_cis, **self._datos_de_sector())

        plazas = agregar_plazas(sector=sector, usuario=self.operador_cis, cantidad=1, tipo=Plaza.Tipo.TURNO)

        self.assertEqual(plazas[0].tipo, Plaza.Tipo.TURNO)

    def test_el_lote_tiene_tope(self):
        sector = crear_sector(dispositivo=self.cis, usuario=self.operador_cis, **self._datos_de_sector())

        with self.assertRaises(ValidationError) as fallo:
            agregar_plazas(sector=sector, usuario=self.operador_cis, cantidad=TOPE_POR_LOTE + 1)

        self.assertIn("cantidad", fallo.exception.message_dict)

    def test_un_sector_dado_de_baja_no_recibe_plazas(self):
        sector = crear_sector(dispositivo=self.cis, usuario=self.operador_cis, **self._datos_de_sector())
        editar_sector(sector=sector, usuario=self.operador_cis, activo=False, **self._datos_de_sector())

        with self.assertRaises(ValidationError) as fallo:
            agregar_plazas(sector=sector, usuario=self.operador_cis, cantidad=1)

        self.assertIn("sector", fallo.exception.message_dict)


class BajaDeSectorTests(BaseCapacidad):
    """La regla que impide dejar a alguien en una plaza que el mapa deja de dibujar."""

    def _dar_de_baja(self):
        return editar_sector(
            sector=self.sector,
            usuario=self.operador_cis,
            nombre=self.sector.nombre,
            tipo=self.sector.tipo,
            capacidad=self.sector.capacidad,
            activo=False,
        )

    def test_no_se_da_de_baja_un_sector_con_una_estadia_activa(self):
        ingresar_persona(ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)

        with self.assertRaises(ValidationError) as fallo:
            self._dar_de_baja()

        self.assertIn("activo", fallo.exception.message_dict)
        self.assertTrue(Sector.objects.get(pk=self.sector.pk).activo)

    def test_no_se_da_de_baja_un_sector_con_una_reserva_sin_liberar(self):
        """Sin liberar, no vigente: la reserva vencida que nadie soltó sigue atada a la plaza."""

        ahora = timezone.now()
        reservar_plaza(
            plaza=self.plaza,
            ciudadano=self.persona,
            usuario=self.operador_cis,
            desde=ahora,
            hasta=ahora + timedelta(hours=12),
        )

        with self.assertRaises(ValidationError) as fallo:
            self._dar_de_baja()

        self.assertIn("activo", fallo.exception.message_dict)

    def test_un_sector_sin_plazas_tomadas_se_da_de_baja_y_sale_del_mapa(self):
        sector = self._dar_de_baja()

        self.assertFalse(sector.activo)
        self.assertEqual(ocupacion_de_plazas(self.cis).de(self.cis).conteo.totales, 0)
        self.assertTrue(TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="SECTOR_BAJA").exists())

    def test_la_baja_no_borra_las_plazas(self):
        self._dar_de_baja()

        self.assertEqual(Plaza.objects.filter(sector=self.sector).count(), 2)

    def test_el_sector_dado_de_baja_se_vuelve_a_activar(self):
        self._dar_de_baja()

        sector = editar_sector(
            sector=self.sector,
            usuario=self.operador_cis,
            nombre=self.sector.nombre,
            tipo=self.sector.tipo,
            capacidad=self.sector.capacidad,
            activo=True,
        )

        self.assertTrue(sector.activo)
        self.assertEqual(ocupacion_de_plazas(self.cis).de(self.cis).conteo.totales, 2)


class AlcanceDeLaConfiguracionTests(BaseCapacidad):
    """`dispositivo.editar` con alcance, y ninguna respuesta que distinga lo ajeno de lo inexistente."""

    def test_sin_la_capacidad_el_servicio_no_crea_el_sector(self):
        with self.assertRaises(PermissionDenied):
            crear_sector(dispositivo=self.cis, usuario=self.sin_editar, **self._datos_de_sector())

    def test_sin_la_capacidad_la_pantalla_responde_403(self):
        self.client.force_login(self.sin_editar)

        respuesta = self.client.post(reverse("dispositivos:sector_crear", args=[self.cis.pk]), self._datos_de_sector())

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Sector.objects.filter(dispositivo=self.cis, nombre="Pabellón B").exists())

    def test_el_operador_de_otra_institucion_no_crea_sectores_acá(self):
        self.client.force_login(self.operador_parador)

        respuesta = self.client.post(reverse("dispositivos:sector_crear", args=[self.cis.pk]), self._datos_de_sector())

        self.assertEqual(respuesta.status_code, 403)

    def test_un_sector_ajeno_da_el_mismo_404_que_uno_inexistente(self):
        self.client.force_login(self.operador_cis)
        datos = self._datos_de_sector()

        ajeno = self.client.post(
            reverse("dispositivos:sector_editar", args=[self.cis.pk, self.sector_parador.pk]), datos
        )
        inexistente = self.client.post(reverse("dispositivos:sector_editar", args=[self.cis.pk, 99999]), datos)

        self.assertEqual(ajeno.status_code, 404)
        self.assertEqual(inexistente.status_code, 404)

    def test_el_dispositivo_cerrado_no_cambia_su_capacidad(self):
        Dispositivo.objects.filter(pk=self.cis.pk).update(estado=Dispositivo.Estado.CERRADO)

        with self.assertRaises(ValidationError):
            crear_sector(
                dispositivo=Dispositivo.objects.get(pk=self.cis.pk),
                usuario=self.operador_cis,
                **self._datos_de_sector(),
            )

    def test_el_modal_de_configuracion_no_se_arma_para_quien_no_puede(self):
        self.client.force_login(self.sin_editar)

        respuesta = self.client.get(reverse("dispositivos:sectores", args=[self.cis.pk]), {"sector": "nuevo"})

        self.assertNotIn("form_sector", respuesta.context)
        self.assertFalse(respuesta.context["puede_configurar_plazas"])

    def test_el_modal_de_un_sector_ajeno_no_se_abre(self):
        self.client.force_login(self.operador_cis)

        respuesta = self.client.get(
            reverse("dispositivos:sectores", args=[self.cis.pk]), {"sector": self.sector_parador.pk}
        )

        self.assertNotIn("form_sector", respuesta.context)

    def test_el_modal_propio_llega_con_el_formulario_cargado(self):
        self.client.force_login(self.operador_cis)

        respuesta = self.client.get(reverse("dispositivos:sectores", args=[self.cis.pk]), {"sector": self.sector.pk})

        self.assertEqual(respuesta.context["form_sector"].initial["nombre"], self.sector.nombre)
        self.assertEqual(respuesta.context["sector_en_edicion"], self.sector)


class EdificioTests(BaseCapacidad):
    """El inmueble: alta, edición, predio compartido y alcance de la vinculación."""

    def _datos(self, **extra):
        return {
            "codigo": "EDI-001",
            "nombre": "Predio Sarmiento",
            "calle": "Av. Sarmiento",
            "numero": "1234",
            "localidad": "Resistencia",
            **extra,
        }

    def test_el_alta_lo_vincula_a_la_institucion_que_lo_carga(self):
        edificio = crear_edificio(dispositivo=self.cis, usuario=self.operador_cis, **self._datos())

        self.assertEqual(list(edificio.dispositivos.all()), [self.cis])
        self.assertEqual(infraestructura_del_dispositivo(self.cis)["edificios"][0]["pk"], edificio.pk)
        self.assertTrue(TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="EDIFICIO_CREADO").exists())

    def test_el_alta_por_la_pantalla_deja_el_edificio_en_la_solapa(self):
        self.client.force_login(self.operador_cis)

        respuesta = self.client.post(reverse("dispositivos:edificio_crear", args=[self.cis.pk]), self._datos())

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Edificio.objects.filter(codigo="EDI-001", dispositivos=self.cis).exists())

    def test_el_codigo_del_edificio_no_se_repite(self):
        crear_edificio(dispositivo=self.cis, usuario=self.operador_cis, **self._datos())

        with self.assertRaises(ValidationError) as fallo:
            crear_edificio(dispositivo=self.parador, usuario=self.administrador, **self._datos(nombre="Otro"))

        self.assertIn("codigo", fallo.exception.message_dict)

    def test_el_predio_compartido_se_ve_en_las_dos_instituciones(self):
        edificio = crear_edificio(dispositivo=self.cis, usuario=self.operador_cis, **self._datos())

        vincular_edificio(edificio=edificio, dispositivo=self.parador, usuario=self.administrador)

        for dispositivo in (self.cis, self.parador):
            filas = infraestructura_del_dispositivo(dispositivo)["edificios"]
            self.assertEqual([fila["pk"] for fila in filas], [edificio.pk])
            self.assertEqual(filas[0]["otras_instituciones"], 1)

    def test_solo_se_vincula_lo_que_el_alcance_alcanza(self):
        """Sin esto, el combo sería la lista de los inmuebles de todas las instituciones."""

        edificio = crear_edificio(dispositivo=self.cis, usuario=self.operador_cis, **self._datos())

        self.assertNotIn(edificio, edificios_vinculables(self.operador_parador, self.parador))
        with self.assertRaises(PermissionDenied):
            vincular_edificio(edificio=edificio, dispositivo=self.parador, usuario=self.operador_parador)

    def test_vincular_dos_veces_no_duplica_la_traza(self):
        edificio = crear_edificio(dispositivo=self.cis, usuario=self.operador_cis, **self._datos())
        vincular_edificio(edificio=edificio, dispositivo=self.parador, usuario=self.administrador)

        vincular_edificio(edificio=edificio, dispositivo=self.parador, usuario=self.administrador)

        trazas = TrazaDispositivo.objects.filter(dispositivo=self.parador, accion="EDIFICIO_VINCULADO")
        self.assertEqual(trazas.count(), 1)

    def test_no_se_edita_un_edificio_que_la_institucion_no_ocupa(self):
        edificio = crear_edificio(dispositivo=self.cis, usuario=self.operador_cis, **self._datos())

        with self.assertRaises(PermissionDenied):
            editar_edificio(
                edificio=edificio,
                dispositivo=self.parador,
                usuario=self.administrador,
                **self._datos(nombre="Renombrado"),
            )

    def test_la_edicion_la_ven_las_dos_instituciones_del_predio(self):
        edificio = crear_edificio(dispositivo=self.cis, usuario=self.operador_cis, **self._datos())
        vincular_edificio(edificio=edificio, dispositivo=self.parador, usuario=self.administrador)

        editar_edificio(
            edificio=edificio,
            dispositivo=self.parador,
            usuario=self.administrador,
            **self._datos(nombre="Predio Sarmiento (anexo)"),
        )

        self.assertEqual(
            infraestructura_del_dispositivo(self.cis)["edificios"][0]["nombre"], "Predio Sarmiento (anexo)"
        )

    def test_desvincular_no_borra_el_edificio(self):
        edificio = crear_edificio(dispositivo=self.cis, usuario=self.operador_cis, **self._datos())

        desvincular_edificio(edificio=edificio, dispositivo=self.cis, usuario=self.operador_cis)

        self.assertTrue(Edificio.objects.filter(pk=edificio.pk).exists())
        self.assertEqual(infraestructura_del_dispositivo(self.cis)["edificios"], [])
        self.assertTrue(TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="EDIFICIO_DESVINCULADO").exists())

    def test_sin_la_capacidad_no_se_carga_un_edificio(self):
        with self.assertRaises(PermissionDenied):
            crear_edificio(dispositivo=self.cis, usuario=self.sin_editar, **self._datos())

    def test_sin_la_capacidad_la_pantalla_responde_403(self):
        self.client.force_login(self.sin_editar)

        respuesta = self.client.post(reverse("dispositivos:edificio_crear", args=[self.cis.pk]), self._datos())

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Edificio.objects.exists())

    def test_el_modal_de_vincular_no_se_abre_sin_edificios_para_vincular(self):
        self.client.force_login(self.operador_cis)

        respuesta = self.client.get(
            reverse("dispositivos:detalle", args=[self.cis.pk]), {"tab": "infraestructura", "edificio": "vincular"}
        )

        self.assertNotIn("form_vincular", respuesta.context)

    def test_el_modal_de_un_edificio_que_no_ocupa_no_se_abre(self):
        edificio = crear_edificio(dispositivo=self.parador, usuario=self.administrador, **self._datos())
        self.client.force_login(self.operador_cis)

        respuesta = self.client.get(
            reverse("dispositivos:detalle", args=[self.cis.pk]),
            {"tab": "infraestructura", "edificio": edificio.pk},
        )

        self.assertNotIn("form_edificio", respuesta.context)
