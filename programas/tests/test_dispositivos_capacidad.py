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

import json
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import override_settings, tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from programas.forms_dispositivos import AgregarPlazasForm
from programas.models import Dispositivo, Edificio, Plaza, ReservaPlaza, Sector, TipoDispositivo, TrazaDispositivo
from programas.selectors.capacidad_dispositivo import edificios_vinculables, plazas_tomadas_del_sector
from programas.services.detalle_dispositivo import infraestructura_del_dispositivo
from programas.services.edificios import (
    crear_edificio,
    desvincular_edificio,
    editar_edificio,
    vincular_edificio,
)
from programas.services.estadias import ingresar_persona, reservar_plaza, sacar_plaza_de_servicio
from programas.services.ocupacion import ocupacion_de_plazas
from programas.services.plazas import (
    TOPE_POR_LOTE,
    agregar_plazas,
    codigos_en_lote,
    crear_sector,
    editar_plaza,
    editar_sector,
)
from programas.tests.test_dispositivos_estadias import BaseEstadias


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class BaseCapacidad(BaseEstadias):
    """El terreno de las estadías más los usuarios que el alcance de este carril distingue."""

    def setUp(self):
        self.ahora = datetime(2026, 10, 14, 10, tzinfo=UTC)
        reloj = patch("django.utils.timezone.now", return_value=self.ahora)
        reloj.start()
        self.addCleanup(reloj.stop)
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
        self.assertEqual(codigos_en_lote(cantidad=2, prefijo="A-", tomados={"a-01"}), ["A-02", "A-03"])

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

    def test_no_se_da_de_baja_un_sector_con_un_prestamo_vigente(self):
        reservar_plaza(
            plaza=self.plaza,
            ciudadano=self.persona,
            usuario=self.operador_cis,
            desde=self.ahora,
            hasta=self.ahora + timedelta(hours=12),
            tipo=ReservaPlaza.Tipo.PRESTAMO,
        )
        with self.assertRaises(ValidationError):
            self._dar_de_baja()

    def test_la_reserva_vencida_sin_liberar_tambien_impide_la_baja(self):
        reserva = reservar_plaza(
            plaza=self.plaza,
            ciudadano=self.persona,
            usuario=self.operador_cis,
            desde=self.ahora,
            hasta=self.ahora + timedelta(hours=12),
        )
        ReservaPlaza.objects.filter(pk=reserva.pk).update(
            desde=self.ahora - timedelta(days=2), hasta=self.ahora - timedelta(days=1)
        )
        with self.assertRaises(ValidationError):
            self._dar_de_baja()

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

    def test_editar_sector_sin_nombre_no_guarda(self):
        with self.assertRaises(ValidationError):
            editar_sector(sector=self.sector, usuario=self.operador_cis, nombre=" ", tipo=Sector.Tipo.OTRO)


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

        self.assertEqual(respuesta.status_code, 404)

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

        respuesta = self.client.get(reverse("dispositivos:sectores", args=[self.cis.pk]), {"sector": self.sector.pk})

        self.assertNotIn("form_sector", respuesta.context)
        self.assertNotIn("form_sector_nuevo", respuesta.context)
        self.assertNotIn("form_plazas", respuesta.context)
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

    def test_el_detalle_renderiza_el_estado_de_la_otra_institucion_del_predio(self):
        edificio = crear_edificio(dispositivo=self.cis, usuario=self.operador_cis, **self._datos())
        vincular_edificio(edificio=edificio, dispositivo=self.parador, usuario=self.administrador)
        self.client.force_login(self.administrador)

        for estado, texto, tono in (
            (Dispositivo.Estado.BORRADOR, "Borrador", "white"),
            (Dispositivo.Estado.PENDIENTE_VALIDACION, "Pendiente de validación", "info"),
            (Dispositivo.Estado.ACTIVO, "Activo", "success"),
            (Dispositivo.Estado.OBSERVADO, "Observado", "warning"),
            (Dispositivo.Estado.RECHAZADO, "Rechazado", "danger"),
            (Dispositivo.Estado.INACTIVO, "Inactivo", "gray"),
            (Dispositivo.Estado.CERRADO, "Cerrado", "gray"),
        ):
            with self.subTest(estado=estado):
                Dispositivo.objects.filter(pk=self.parador.pk).update(estado=estado)

                respuesta = self.client.get(reverse("dispositivos:detalle", args=[self.cis.pk]))

                self.assertEqual(respuesta.status_code, 200)
                fila = next(
                    fila
                    for fila in respuesta.content.decode().split("</tr>")
                    if f'href="{reverse("dispositivos:detalle", args=[self.parador.pk])}"' in fila
                )
                self.assertInHTML(f'<span class="badge badge-dot badge-{tono}">{texto}</span>', fila)

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
        self.assertTrue(TrazaDispositivo.objects.filter(dispositivo=self.parador, accion="EDIFICIO_EDITADO").exists())
        self.assertTrue(TrazaDispositivo.objects.filter(dispositivo=self.parador, accion="EDIFICIO_VINCULADO").exists())

    def test_editar_edificio_rechaza_codigo_y_nombre_vacios(self):
        edificio = crear_edificio(dispositivo=self.cis, usuario=self.operador_cis, **self._datos())
        for extra in ({"codigo": " "}, {"nombre": " "}):
            with self.subTest(extra=extra), self.assertRaises(ValidationError):
                editar_edificio(
                    edificio=edificio, dispositivo=self.cis, usuario=self.operador_cis, **self._datos(**extra)
                )

    def test_desvincular_exige_que_la_institucion_ocupe_el_edificio(self):
        edificio = crear_edificio(dispositivo=self.cis, usuario=self.operador_cis, **self._datos())
        with self.assertRaises(PermissionDenied):
            desvincular_edificio(edificio=edificio, dispositivo=self.parador, usuario=self.administrador)

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


class EdicionDePlazaTests(BaseCapacidad):
    def test_la_edicion_por_pantalla_guarda_y_traza_sin_tocar_estado_ni_sector(self):
        sacar_plaza_de_servicio(plaza=self.plaza, usuario=self.operador_cis, motivo="Arreglo")
        self.client.force_login(self.operador_cis)
        respuesta = self.client.post(
            reverse("dispositivos:plaza_editar", args=[self.cis.pk, self.plaza.pk]),
            {"codigo": "A-01", "tipo": Plaza.Tipo.CUPO},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.plaza.refresh_from_db()
        self.assertEqual((self.plaza.codigo, self.plaza.tipo), ("A-01", Plaza.Tipo.CUPO))
        self.assertEqual(
            (self.plaza.estado, self.plaza.motivo_fuera_servicio), (Plaza.Estado.FUERA_SERVICIO, "Arreglo")
        )
        self.assertEqual(self.plaza.sector, self.sector)
        self.assertTrue(TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="PLAZA_EDITADA").exists())

    def test_el_codigo_es_unico_entre_sectores_del_dispositivo(self):
        otro = crear_sector(dispositivo=self.cis, usuario=self.operador_cis, **self._datos_de_sector())
        Plaza.objects.create(sector=otro, codigo="b-01")
        with self.assertRaises(ValidationError) as fallo:
            editar_plaza(plaza=self.plaza, usuario=self.operador_cis, codigo="B-01", tipo=Plaza.Tipo.CAMA)
        self.assertIn("codigo", fallo.exception.message_dict)

    def test_otro_dispositivo_puede_usar_el_mismo_codigo(self):
        plaza = editar_plaza(plaza=self.plaza, usuario=self.operador_cis, codigo="G1", tipo=Plaza.Tipo.CAMA)
        self.assertEqual(plaza.codigo, self.plaza_parador.codigo)

    def test_el_tipo_admitido_tambien_se_exige_en_edicion(self):
        self.tipo.tipos_plaza_admitidos = [Plaza.Tipo.CAMA]
        self.tipo.save()
        with self.assertRaises(ValidationError) as fallo:
            editar_plaza(plaza=self.plaza, usuario=self.operador_cis, codigo=self.plaza.codigo, tipo=Plaza.Tipo.CUPO)
        self.assertIn("tipo", fallo.exception.message_dict)

    def test_editar_no_acepta_codigo_vacio_ni_tipo_inventado(self):
        for codigo, tipo in (("   ", Plaza.Tipo.CAMA), ("P1", "INVENTADO")):
            with self.subTest(codigo=codigo, tipo=tipo), self.assertRaises(ValidationError):
                editar_plaza(plaza=self.plaza, usuario=self.operador_cis, codigo=codigo, tipo=tipo)

    def test_el_modal_propio_esta_cargado_y_el_ajeno_no_se_abre(self):
        self.client.force_login(self.operador_cis)
        url = reverse("dispositivos:sectores", args=[self.cis.pk])
        respuesta = self.client.get(url, {"editar_plaza": self.plaza.pk})
        self.assertEqual(respuesta.context["form_editar_plaza"].initial["codigo"], self.plaza.codigo)
        self.assertContains(respuesta, "Guardar plaza")
        for pk in (self.plaza_parador.pk, 99999, "١", "１"):
            with self.subTest(pk=pk):
                self.assertNotIn("form_editar_plaza", self.client.get(url, {"editar_plaza": pk}).context)

    def test_quien_edita_sin_admitir_llega_a_la_edicion_de_una_plaza_reservada(self):
        editor = self._operador("Solo editor", self.cis, ("dispositivo.ver", "dispositivo.editar"))
        reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)
        self.client.force_login(editor)
        url = reverse("dispositivos:sectores", args=[self.cis.pk])
        respuesta = self.client.get(url)
        celda = next(c for fila in respuesta.context["sectores"] for c in fila["plazas"] if c["codigo"] == "P1")
        modal = self.client.get(url + celda["url"])
        self.assertEqual(modal.context["plaza_en_edicion"], self.plaza)
        self.assertNotIn("plaza_accion", modal.context)


class GuardasDeCapacidadTests(BaseCapacidad):
    def test_los_estados_vacios_enlazan_al_alta_y_al_lote(self):
        Sector.objects.filter(dispositivo=self.cis).update(activo=False)
        self.client.force_login(self.operador_cis)
        url = reverse("dispositivos:sectores", args=[self.cis.pk])
        respuesta = self.client.get(url)
        self.assertContains(respuesta, "Este dispositivo no tiene sectores")
        self.assertContains(respuesta, '<button type="button" @click="modalSectorNuevo=true"', count=2)
        sector = crear_sector(dispositivo=self.cis, usuario=self.operador_cis, **self._datos_de_sector())
        self.assertContains(self.client.get(url), f"sectorPlazas='{sector.pk}'; modalPlazas=true")
        respuesta = self.client.get(reverse("dispositivos:detalle", args=[self.cis.pk]), {"tab": "infraestructura"})
        self.assertContains(respuesta, "Este dispositivo no tiene edificio cargado")
        self.assertContains(respuesta, "edificio=nuevo")

    def test_los_errores_ajax_del_servicio_llegan_al_campo_o_al_error_general(self):
        self.client.force_login(self.operador_cis)
        url = reverse("dispositivos:sector_crear", args=[self.cis.pk])
        headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        respuesta = self.client.post(url, self._datos_de_sector(nombre=self.sector.nombre), **headers)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("nombre", respuesta.json()["errors"])
        Dispositivo.objects.filter(pk=self.cis.pk).update(estado=Dispositivo.Estado.CERRADO)
        respuesta = self.client.post(url, self._datos_de_sector(), **headers)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("__all__", respuesta.json()["errors"])

    def test_plaza_con_estadia_activa_no_sale_de_servicio(self):
        ingresar_persona(ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)
        with self.assertRaises(ValidationError):
            sacar_plaza_de_servicio(plaza=self.plaza, usuario=self.operador_cis, motivo="Arreglo")

    def test_plaza_con_reserva_vigente_no_sale_de_servicio(self):
        reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)
        with self.assertRaises(ValidationError):
            sacar_plaza_de_servicio(plaza=self.plaza, usuario=self.operador_cis, motivo="Arreglo")

    def test_plaza_con_prestamo_vigente_no_sale_de_servicio(self):
        reservar_plaza(
            plaza=self.plaza,
            ciudadano=self.persona,
            usuario=self.operador_cis,
            tipo=ReservaPlaza.Tipo.PRESTAMO,
            desde=self.ahora,
            hasta=self.ahora + timedelta(hours=12),
        )
        with self.assertRaises(ValidationError):
            sacar_plaza_de_servicio(plaza=self.plaza, usuario=self.operador_cis, motivo="Arreglo")

    def test_compuerta_de_alcance_antes_de_consultar_objetos_o_validar_forms(self):
        self.client.force_login(self.operador_parador)
        with patch("programas.views.dispositivos_capacidad.SectorForm") as form:
            for pk in (self.sector.pk, 99999):
                respuesta = self.client.post(reverse("dispositivos:sector_editar", args=[self.cis.pk, pk]), {})
                self.assertEqual(respuesta.status_code, 404)
            form.assert_not_called()

    def test_edificios_y_plazas_ajenos_e_inexistentes_devuelven_el_mismo_404_antes_de_validar(self):
        edificio = crear_edificio(
            dispositivo=self.parador, usuario=self.operador_parador, codigo="AJENO", nombre="Ajeno"
        )
        self.client.force_login(self.operador_cis)
        for accion, ajeno in (
            ("edificio_editar", edificio.pk),
            ("edificio_desvincular", edificio.pk),
            ("plaza_editar", self.plaza_parador.pk),
        ):
            for pk in (ajeno, 99999):
                with self.subTest(accion=accion, pk=pk):
                    self.assertEqual(
                        self.client.post(reverse(f"dispositivos:{accion}", args=[self.cis.pk, pk]), {}).status_code, 404
                    )

    def test_vincular_ajeno_e_inexistente_no_revela_si_existe(self):
        edificio = crear_edificio(
            dispositivo=self.parador, usuario=self.operador_parador, codigo="AJENO", nombre="Ajeno"
        )
        self.client.force_login(self.operador_cis)
        url = reverse("dispositivos:edificio_vincular", args=[self.cis.pk])
        headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        ajeno = self.client.post(url, {"edificio": edificio.pk}, **headers)
        inexistente = self.client.post(url, {"edificio": 99999}, **headers)
        self.assertEqual(ajeno.status_code, 404)
        self.assertEqual(inexistente.status_code, 404)

    def test_lote_a_sector_ajeno_inexistente_o_id_no_ascii_da_404(self):
        self.client.force_login(self.operador_cis)
        url = reverse("dispositivos:plazas_agregar", args=[self.cis.pk])
        for pk in (self.sector_parador.pk, 99999, "١", "１"):
            with self.subTest(pk=pk):
                self.assertEqual(self.client.post(url, {"sector": pk}).status_code, 404)

    def test_los_servicios_exigen_capacidad_y_asignacion(self):
        edificio = crear_edificio(dispositivo=self.cis, usuario=self.operador_cis, codigo="EDI", nombre="Predio")
        for usuario in (self.sin_editar, self.operador_parador):
            for accion in (
                lambda: editar_sector(sector=self.sector, usuario=usuario, **self._datos_de_sector()),
                lambda: agregar_plazas(sector=self.sector, usuario=usuario, cantidad=1),
                lambda: editar_plaza(plaza=self.plaza, usuario=usuario, codigo="P1", tipo=Plaza.Tipo.CAMA),
                lambda: editar_edificio(
                    edificio=edificio, dispositivo=self.cis, usuario=usuario, codigo="EDI", nombre="Predio"
                ),
                lambda: desvincular_edificio(edificio=edificio, dispositivo=self.cis, usuario=usuario),
            ):
                with self.subTest(usuario=usuario.username), self.assertRaises(PermissionDenied):
                    accion()

    def test_edificio_cerrado_no_se_modifica(self):
        Dispositivo.objects.filter(pk=self.cis.pk).update(estado=Dispositivo.Estado.CERRADO)
        self.cis.refresh_from_db()
        with self.assertRaises(ValidationError):
            crear_edificio(dispositivo=self.cis, usuario=self.operador_cis, codigo="EDI", nombre="Predio")

    def test_lote_rechaza_cero_y_prefijo_que_desborda_el_codigo(self):
        for cantidad, prefijo, campo in ((0, "", "cantidad"), (1, "A" * 50, "prefijo")):
            with self.subTest(campo=campo), self.assertRaises(ValidationError) as fallo:
                agregar_plazas(sector=self.sector, usuario=self.operador_cis, cantidad=cantidad, prefijo=prefijo)
            self.assertIn(campo, fallo.exception.message_dict)

    def test_altas_sin_nombre_o_codigo_no_guardan_nada(self):
        with self.assertRaises(ValidationError):
            crear_sector(dispositivo=self.cis, usuario=self.operador_cis, nombre=" ", tipo=Sector.Tipo.OTRO)
        for datos in ({"codigo": "", "nombre": "Predio"}, {"codigo": "EDI", "nombre": " "}):
            with self.assertRaises(ValidationError):
                crear_edificio(dispositivo=self.cis, usuario=self.operador_cis, **datos)
        self.assertFalse(Edificio.objects.exists())

    def test_las_acciones_son_post_y_exigen_csrf(self):
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        client.force_login(self.operador_cis)
        for nombre in ("sector_crear", "plazas_agregar", "edificio_crear", "edificio_vincular"):
            url = reverse(f"dispositivos:{nombre}", args=[self.cis.pk])
            self.assertEqual(client.get(url).status_code, 405)
            self.assertEqual(client.post(url, {}).status_code, 403)

    def test_el_admin_no_borra_ni_mueve_historia_ni_da_de_baja_sin_guarda(self):
        from django.contrib import admin
        from django.contrib.auth.models import User
        from django.test import RequestFactory

        request = RequestFactory().get("/admin/")
        request.user = User.objects.create_superuser(username="soporte", password="x")
        for modelo in (Edificio, Sector, Plaza):
            self.assertFalse(admin.site._registry[modelo].has_delete_permission(request))
        self.assertIn("activo", admin.site._registry[Sector].get_readonly_fields(request, self.sector))
        self.assertIn("dispositivo", admin.site._registry[Sector].get_readonly_fields(request, self.sector))
        self.assertIn("sector", admin.site._registry[Plaza].get_readonly_fields(request, self.plaza))


class AltasSinRecargaTests(BaseCapacidad):
    """«Agregar plazas» y «Nuevo sector» abren su modal en el navegador, como el de la golden.

    Eran enlaces a `?plazas=1` y `?sector=nuevo`: el clic recargaba la pantalla entera para que
    el servidor la devolviera con el modal abierto, y en QA se veía como un F5 antes del modal.
    Ninguna de las dos altas depende de un registro, así que los formularios llegan con la
    página y el botón solo los muestra. «Editar sector» sí depende del suyo y sigue por GET.
    """

    def setUp(self):
        super().setUp()
        self.url = reverse("dispositivos:sectores", args=[self.cis.pk])

    def test_el_boton_del_encabezado_abre_el_lote_sin_navegar(self):
        self.client.force_login(self.operador_cis)

        respuesta = self.client.get(self.url)

        self.assertIn("form_plazas", respuesta.context)
        self.assertNotContains(respuesta, 'href="?plazas=')
        self.assertContains(respuesta, "sectorPlazas=''; modalPlazas=true")

    def test_nuevo_sector_abre_su_modal_sin_navegar(self):
        self.client.force_login(self.operador_cis)

        respuesta = self.client.get(self.url)

        self.assertFalse(respuesta.context["form_sector_nuevo"].is_bound)
        self.assertNotIn("form_sector", respuesta.context)
        self.assertNotContains(respuesta, 'href="?sector=nuevo"')
        self.assertContains(respuesta, '<button type="button" @click="modalSectorNuevo=true"')

    def test_la_edicion_de_un_sector_no_pisa_el_alta(self):
        """Con `?sector=<id>` están los dos modales: cada uno con su formulario y su título."""

        self.client.force_login(self.operador_cis)

        respuesta = self.client.get(self.url, {"sector": self.sector.pk})

        self.assertEqual(respuesta.context["form_sector"].initial["nombre"], self.sector.nombre)
        self.assertNotIn("nombre", respuesta.context["form_sector_nuevo"].initial)
        self.assertContains(respuesta, 'aria-labelledby="modal-sector-titulo"')
        self.assertContains(respuesta, 'aria-labelledby="modal-sector-nuevo-titulo"')

    def test_un_enlace_viejo_al_alta_no_avisa_que_el_sector_no_se_edita(self):
        self.client.force_login(self.operador_cis)

        respuesta = self.client.get(self.url, {"sector": "nuevo"})

        self.assertEqual(list(respuesta.context["messages"]), [])
        self.assertNotIn("form_sector", respuesta.context)

    def test_las_altas_no_se_arman_para_quien_no_puede_ni_el_lote_sin_sectores(self):
        self.client.force_login(self.sin_editar)
        contexto = self.client.get(self.url).context
        self.assertNotIn("form_plazas", contexto)
        self.assertNotIn("form_sector_nuevo", contexto)

        Sector.objects.filter(dispositivo=self.cis).update(activo=False)
        self.client.force_login(self.operador_cis)
        contexto = self.client.get(self.url).context
        self.assertNotIn("form_plazas", contexto)
        self.assertIn("form_sector_nuevo", contexto)

    def test_la_pantalla_no_repite_ids_con_otro_modal_abierto(self):
        """El lote, el sector y la plaza tienen un campo `tipo`, y el alta y la edición del sector
        son el mismo formulario: ahora conviven en el HTML."""

        self.client.force_login(self.operador_cis)
        for parametros in ({}, {"sector": "nuevo"}, {"sector": self.sector.pk}, {"editar_plaza": self.plaza.pk}):
            with self.subTest(parametros=parametros):
                html = self.client.get(self.url, parametros).content.decode()
                repetidos = [i for i, n in Counter(re.findall(r'\sid="([^"]+)"', html)).items() if n > 1]
                self.assertEqual(repetidos, [])


@tag("performance")
class CapacidadPresupuestoTests(BaseCapacidad):
    def test_el_selector_del_lote_no_consulta_por_sector(self):
        presupuesto = json.loads(
            (Path(__file__).resolve().parents[2] / "scripts/perf_budgets.json").read_text(encoding="utf-8")
        )
        techo = presupuesto["servicios"]["dispositivos_selector_lote_plazas"]["consultas_fijas"]
        for cantidad in (1, 8):
            if cantidad == 8:
                Sector.objects.bulk_create(Sector(dispositivo=self.cis, nombre=f"Pabellón {n}") for n in range(7))
            form = AgregarPlazasForm(dispositivo=self.cis, sectores=Sector.objects.filter(dispositivo=self.cis))
            with CaptureQueriesContext(connection) as consultas:
                html = str(form["sector"])
            self.assertIn(self.sector.nombre, html)
            self.assertLessEqual(len(consultas), techo)

    def test_la_guarda_de_baja_cuesta_dos_consultas_con_dos_o_doscientas_plazas(self):
        presupuesto = json.loads(
            (Path(__file__).resolve().parents[2] / "scripts/perf_budgets.json").read_text(encoding="utf-8")
        )
        techo = presupuesto["servicios"]["dispositivos_baja_sector"]["consultas_fijas"]
        for cantidad in (2, 200):
            if cantidad == 200:
                Plaza.objects.bulk_create(Plaza(sector=self.sector, codigo=f"X-{n}") for n in range(198))
            with CaptureQueriesContext(connection) as consultas:
                self.assertEqual(plazas_tomadas_del_sector(self.sector), 0)
            self.assertLessEqual(len(consultas), techo)
