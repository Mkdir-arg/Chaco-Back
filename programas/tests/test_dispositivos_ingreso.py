"""Asistente de ingreso de una persona (MVP v2, etapa 2 · #690 · P6).

El caso que motivó la regla de la ficha del arquetipo Wizard es el primero: la plaza se
elige en el paso 2 y otro operador la puede tomar antes del paso final. El paso final tiene
que volver al paso de la plaza con el error, no reventar.
"""

import re
from datetime import timedelta
from unittest import mock

from django.urls import reverse
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import AsignacionDispositivo, Estadia, Plaza, ReservaPlaza
from programas.services.bitacora import crear_turno
from programas.services.estadias import ingresar_persona, reservar_plaza
from programas.tests.test_dispositivos_estadias import CAPACIDADES_OPERATIVAS, BaseEstadias, _permiso
from programas.views.dispositivos_ingreso import IngresoBaseView

CAPACIDADES_INGRESO = (*CAPACIDADES_OPERATIVAS, "ciudadano.ver", "ciudadano.crear")


class BaseIngreso(BaseEstadias):
    def setUp(self):
        super().setUp()
        self.tipo.plaza_obligatoria_al_ingresar = True
        self.tipo.save()
        self.operador_cis = self._operador("Admisor CIS", self.cis, CAPACIDADES_INGRESO)
        self.client.force_login(self.operador_cis)
        pk = self.cis.pk
        self.url_persona = reverse("dispositivos:ingreso_persona", args=[pk])
        self.url_plaza = reverse("dispositivos:ingreso_plaza", args=[pk])
        self.url_confirmar = reverse("dispositivos:ingreso_confirmar", args=[pk])

    def _campos_ocultos(self, respuesta):
        """Lo que la pantalla mostró y el navegador devuelve al enviar: los ocultos, salvo el CSRF."""

        html = respuesta.content.decode()
        return {
            nombre: valor
            for nombre, valor in re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', html)
            if nombre != "csrfmiddlewaretoken"
        }

    def _elegir_plaza(self, plaza):
        """Como lo hace la persona: toca la plaza en el mapa y, si la pantalla lo pide, «Continuar»."""

        respuesta = self.client.get(f"{self.url_plaza}?elegir={plaza.pk}")
        if respuesta.status_code == 200:
            respuesta = self.client.post(self.url_plaza, self._campos_ocultos(respuesta))
        return respuesta

    def _hasta_la_plaza(self, persona, plaza):
        self.client.post(self.url_persona, {"dni": persona.dni})
        return self._elegir_plaza(plaza)

    def _confirmar(self, datos=None):
        """Abre el paso final y lo envía con lo que esa pantalla mostró."""

        mostrado = self._campos_ocultos(self.client.get(self.url_confirmar))
        return self.client.post(self.url_confirmar, {**mostrado, **(datos or {})})


class CarreraPorLaPlazaTests(BaseIngreso):
    def test_si_otro_operador_toma_la_plaza_se_vuelve_al_paso_de_la_plaza_con_el_error(self):
        respuesta = self._hasta_la_plaza(self.persona, self.plaza)
        self.assertRedirects(respuesta, self.url_confirmar)

        # Entre el paso 2 y el final, otro operador aloja a otra persona en esa plaza.
        ingresar_persona(ciudadano=self.otra_persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)

        respuesta = self._confirmar()
        # No un 500. Sin seguir la redirección: el error se muestra una sola vez.
        self.assertRedirects(respuesta, self.url_plaza, fetch_redirect_response=False)
        self.assertFalse(Estadia.objects.filter(ciudadano=self.persona).exists())

        pagina = self.client.get(self.url_plaza)
        self.assertContains(pagina, "La plaza ya tiene una estadía activa.")
        # La plaza tomada ya no se ofrece; la otra sigue disponible y se puede elegir.
        self.assertNotContains(pagina, f'?elegir={self.plaza.pk}"')
        self.assertContains(pagina, f'?elegir={self.otra_plaza.pk}"')

    def test_la_plaza_sacada_de_servicio_tambien_vuelve_al_paso_de_la_plaza(self):
        self._hasta_la_plaza(self.persona, self.plaza)
        Plaza.objects.filter(pk=self.plaza.pk).update(
            estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="Reparación"
        )

        respuesta = self._confirmar()

        self.assertRedirects(respuesta, self.url_plaza)
        self.assertFalse(Estadia.objects.filter(ciudadano=self.persona).exists())

    def test_elegir_una_plaza_ocupada_no_avanza(self):
        ingresar_persona(ciudadano=self.otra_persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)
        self.client.post(self.url_persona, {"dni": self.persona.dni})

        respuesta = self.client.get(f"{self.url_plaza}?elegir={self.plaza.pk}")

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Esa plaza ya no está disponible")


class FlujoDeIngresoTests(BaseIngreso):
    def test_ingreso_completo_con_plaza(self):
        self._hasta_la_plaza(self.persona, self.plaza)

        respuesta = self._confirmar()

        self.assertRedirects(respuesta, reverse("dispositivos:detalle", args=[self.cis.pk]))
        estadia = Estadia.objects.get(ciudadano=self.persona)
        self.assertEqual(estadia.plaza, self.plaza)
        self.assertEqual(estadia.ingresada_por, self.operador_cis)

    def test_el_paso_de_plaza_sin_persona_vuelve_al_primero(self):
        self.assertRedirects(self.client.get(self.url_plaza), self.url_persona)
        self.assertRedirects(self.client.get(self.url_confirmar), self.url_persona)

    def test_el_paso_final_sin_haber_elegido_plaza_vuelve_al_de_la_plaza(self):
        self.client.post(self.url_persona, {"dni": self.persona.dni})
        self.assertRedirects(self.client.get(self.url_confirmar), self.url_plaza)

    def test_si_el_tipo_exige_plaza_no_se_puede_seguir_sin_ella(self):
        self.client.post(self.url_persona, {"dni": self.persona.dni})
        pagina = self.client.get(self.url_plaza)
        self.assertNotContains(pagina, "Continuar sin plaza")
        # Ni forzando el POST que el botón no ofrece.
        respuesta = self.client.post(self.url_plaza, {**self._campos_ocultos(pagina), "sin_plaza": "1"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "exige asignar una plaza")

    def test_tocar_una_plaza_la_marca_pero_no_avanza_ni_guarda(self):
        self.client.post(self.url_persona, {"dni": self.persona.dni})

        respuesta = self.client.get(f"{self.url_plaza}?elegir={self.plaza.pk}")

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Elegida")
        self.assertEqual(self._campos_ocultos(respuesta)["plaza"], str(self.plaza.pk))
        # Hasta «Continuar» no hay plaza guardada: el paso final todavía no se abre.
        self.assertRedirects(self.client.get(self.url_confirmar), self.url_plaza)

    def test_continuar_sin_marcar_una_plaza_lo_explica(self):
        self.client.post(self.url_persona, {"dni": self.persona.dni})

        respuesta = self.client.post(self.url_plaza, self._campos_ocultos(self.client.get(self.url_plaza)))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Elegí una plaza disponible en el mapa.")

    def test_el_paso_de_la_plaza_muestra_los_datos_de_la_persona_del_legajo(self):
        self.persona.domicilio = "Sin domicilio fijo"
        self.persona.obra_social = "Sin cobertura"
        self.persona.save()
        self.client.post(self.url_persona, {"dni": self.persona.dni})

        respuesta = self.client.get(self.url_plaza)

        for dato in ("Sin domicilio fijo", "Sin cobertura", "Ver legajo completo", "vienen del Legajo Ciudadano"):
            self.assertContains(respuesta, dato)
        self.assertContains(respuesta, reverse("legajos:ciudadano_detalle", args=[self.persona.pk]))
        self.assertContains(respuesta, self.cis.nombre)  # el eyebrow

    def test_un_tipo_que_no_maneja_plazas_se_salta_el_paso_de_la_plaza(self):
        self.tipo.plaza_obligatoria_al_ingresar = False
        self.tipo.save()

        respuesta = self.client.post(self.url_persona, {"dni": self.persona.dni})
        self.assertRedirects(respuesta, self.url_confirmar)
        self._confirmar()

        self.assertIsNone(Estadia.objects.get(ciudadano=self.persona).plaza)

    def test_el_aviso_de_estadia_en_otra_institucion_llega_antes_de_confirmar(self):
        ingresar_persona(
            ciudadano=self.persona, dispositivo=self.parador, usuario=self.operador_parador, plaza=self.plaza_parador
        )

        respuesta = self.client.post(self.url_persona, {"dni": self.persona.dni})

        self.assertEqual(respuesta.status_code, 200)  # no avanza
        self.assertContains(respuesta, "La persona ya está alojada")


class EyebrowConElTurnoTests(BaseIngreso):
    """El eyebrow de P6 es «CIS N.º 3 · turno Tarde · 08/09/2026 16:48» (carril C3).

    El turno sale de `turno_vigente`, el único lugar del sistema que lo calcula, y en hora
    local: el nocturno que empieza el lunes es del lunes aunque sean las 03:00 del martes.
    """

    def _con_turno_de_ahora(self, minutos_de_ventana=60):
        """Un turno que contiene a este momento, y otro activo que no, para que elija uno."""

        local = timezone.localtime()
        desde = (local - timedelta(minutes=minutos_de_ventana)).time().replace(second=0, microsecond=0)
        hasta = (local + timedelta(minutes=minutos_de_ventana)).time().replace(second=0, microsecond=0)
        return crear_turno(
            dispositivo=self.cis, usuario=self.operador_cis, nombre="Tarde", hora_desde=desde, hora_hasta=hasta
        )

    def test_el_eyebrow_de_cada_paso_nombra_el_turno_en_curso(self):
        self._con_turno_de_ahora()
        esperado = f"{self.cis.nombre} · turno Tarde · "

        primero = self.client.get(self.url_persona)
        self.client.post(self.url_persona, {"dni": self.persona.dni})
        segundo = self.client.get(self.url_plaza)
        self._elegir_plaza(self.plaza)
        final = self.client.get(self.url_confirmar)

        for paso, respuesta in (("persona", primero), ("plaza", segundo), ("confirmar", final)):
            with self.subTest(paso=paso):
                self.assertEqual(respuesta.status_code, 200)
                self.assertTrue(respuesta.context["eyebrow"].startswith(esperado), respuesta.context["eyebrow"])
                self.assertContains(respuesta, esperado)

    def test_sin_turno_para_este_momento_el_eyebrow_no_inventa_ninguno(self):
        """El dispositivo no tiene turnos configurados: el eyebrow queda como antes."""

        respuesta = self.client.get(self.url_persona)

        self.assertRegex(
            respuesta.context["eyebrow"], rf"^{self.cis.nombre} · \d{{2}}/\d{{2}}/\d{{4}} \d{{2}}:\d{{2}}$"
        )


class AvisoDeOcupacionCriticaTests(BaseIngreso):
    """Mockup #p6: «Ocupación crítica (88 %). El sistema no bloquea el ingreso.»

    El nivel y el porcentaje salen de `services.ocupacion.tension_de_ocupacion` —la misma
    fuente que P2 y P4— y con los umbrales **del tipo**, no con el corte general: dos tipos
    de dispositivo con la misma ocupación no están igual de exigidos. El aviso no bloquea
    nada: «Continuar» sigue ahí.
    """

    def _paso_dos(self):
        self.client.post(self.url_persona, {"dni": self.persona.dni})
        return self.client.get(self.url_plaza)

    def test_con_la_ocupacion_por_encima_del_umbral_rojo_del_tipo_avisa_y_no_bloquea(self):
        # Una de las dos plazas ocupada: 50 %. El tipo marca rojo desde 40 %.
        self.tipo.umbral_ocupacion_amarillo = 30
        self.tipo.umbral_ocupacion_rojo = 40
        self.tipo.save()
        ingresar_persona(
            ciudadano=self.otra_persona, dispositivo=self.cis, plaza=self.otra_plaza, usuario=self.operador_cis
        )

        respuesta = self._paso_dos()

        self.assertEqual(respuesta.context["aviso_ocupacion"], "Ocupación crítica (50 %).")
        self.assertContains(respuesta, "Ocupación crítica (50 %).")
        self.assertContains(respuesta, "El sistema no bloquea el ingreso.")
        self.assertContains(respuesta, "Continuar")

    def test_con_los_umbrales_de_fabrica_la_misma_ocupacion_no_avisa(self):
        """El mismo 50 % con el corte de fábrica (rojo al 80 %) no es crítico."""

        ingresar_persona(
            ciudadano=self.otra_persona, dispositivo=self.cis, plaza=self.otra_plaza, usuario=self.operador_cis
        )

        respuesta = self._paso_dos()

        self.assertEqual(respuesta.context["aviso_ocupacion"], "")
        self.assertNotContains(respuesta, "El sistema no bloquea el ingreso.")

    def test_un_dispositivo_sin_plazas_no_inventa_un_porcentaje(self):
        Plaza.objects.filter(sector__dispositivo=self.cis).delete()

        respuesta = self._paso_dos()

        self.assertEqual(respuesta.context["aviso_ocupacion"], "")
        self.assertNotContains(respuesta, "Ocupación")


class ResumenDelPasoFinalTests(BaseIngreso):
    def test_la_plaza_se_lee_de_lo_general_a_lo_particular_como_en_p4(self):
        """«Pabellón B · B-03», no «B-03 · Pabellón B»: el orden del mockup y el de P4 y P5."""

        self._hasta_la_plaza(self.persona, self.plaza)

        respuesta = self.client.get(self.url_confirmar)

        self.assertContains(respuesta, f"{self.sector.nombre} · {self.plaza.codigo}")
        self.assertNotContains(respuesta, f"{self.plaza.codigo} · {self.sector.nombre}")


class VerificacionEnLaRedTests(BaseIngreso):
    def test_fuera_del_alcance_solo_se_sabe_que_esta_alojada(self):
        # Un código que el token CSRF, aleatorio, no pueda reproducir por azar.
        Plaza.objects.filter(pk=self.plaza_parador.pk).update(codigo="ZETA-77")
        self.plaza_parador.refresh_from_db()
        ingresar_persona(
            ciudadano=self.persona, dispositivo=self.parador, usuario=self.operador_parador, plaza=self.plaza_parador
        )

        respuesta = self.client.post(self.url_persona, {"dni": self.persona.dni})

        self.assertContains(respuesta, Estadia.clave_para(self.persona))
        for dato in (self.parador.nombre, self.parador.codigo, self.plaza_parador.codigo, "Responsable de Parador"):
            self.assertNotContains(respuesta, dato)

    def test_sin_la_capacidad_de_admitir_en_el_dispositivo_no_hay_asistente_ni_verificacion(self):
        # Alcance sobre el parador, no sobre el CIS.
        self.client.force_login(self.operador_parador)
        for url in (self.url_persona, self.url_plaza, self.url_confirmar):
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(self.url_persona, {"dni": self.persona.dni}).status_code, 403)

    def test_sin_permiso_de_ver_ciudadanos_tampoco(self):
        sin_legajo = self._operador("Sin legajo", self.cis)
        self.client.force_login(sin_legajo)
        self.assertEqual(self.client.get(self.url_persona).status_code, 403)

    def test_anonimo_va_al_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url_persona).status_code, 302)


class AltaDesdeElRegistroDePersonasTests(BaseIngreso):
    DATOS = {
        "success": True,
        "data": {
            "dni": "27555666",
            "nombre": "Marta",
            "apellido": "Ruiz",
            "fecha_nacimiento": "1980-05-02",
            "genero": "F",
            "domicilio": "Mitre 100",
            "provincia": None,
        },
        "datos_api": {},
    }

    def test_la_persona_se_da_de_alta_recien_al_confirmar(self):
        with mock.patch(
            "programas.services.ingreso.CiudadanosService.consultar_renaper", return_value=self.DATOS
        ) as consulta:
            respuesta = self.client.post(self.url_persona, {"dni": "27.555.666", "sexo": "F"})
        consulta.assert_called_once_with("27555666", "F")
        self.assertRedirects(respuesta, self.url_plaza)
        self.assertFalse(Ciudadano.objects.filter(dni="27555666").exists(), "un paso intermedio no escribe")

        self._elegir_plaza(self.plaza)
        self._confirmar()

        ciudadano = Ciudadano.objects.get(dni="27555666")
        self.assertEqual(ciudadano.estado_renaper, Ciudadano.EstadoRenaper.REGISTRADO)
        self.assertEqual(Estadia.objects.get(ciudadano=ciudadano).plaza, self.plaza)

    def test_si_la_plaza_se_ocupa_no_queda_un_legajo_huerfano(self):
        with mock.patch("programas.services.ingreso.CiudadanosService.consultar_renaper", return_value=self.DATOS):
            self.client.post(self.url_persona, {"dni": "27555666", "sexo": "F"})
        self._elegir_plaza(self.plaza)
        ingresar_persona(ciudadano=self.otra_persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)

        respuesta = self._confirmar()

        self.assertRedirects(respuesta, self.url_plaza)
        self.assertFalse(Ciudadano.objects.filter(dni="27555666").exists())

    def test_sin_sexo_no_se_consulta(self):
        with mock.patch("programas.services.ingreso.CiudadanosService.consultar_renaper") as consulta:
            respuesta = self.client.post(self.url_persona, {"dni": "27555666"})
        consulta.assert_not_called()
        self.assertContains(respuesta, "Indicá el sexo")

    def test_si_el_registro_no_la_encuentra_se_explica(self):
        with mock.patch(
            "programas.services.ingreso.CiudadanosService.consultar_renaper",
            return_value={"success": False, "error": "sin resultados"},
        ):
            respuesta = self.client.post(self.url_persona, {"dni": "27555666", "sexo": "F"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "sin resultados")


class UnSoloOrigenDelEstadoDeLaPlazaTests(BaseIngreso):
    """Regla 3 de la etapa 2: «Sectores y plazas» y el ingreso muestran lo mismo."""

    def test_la_misma_plaza_tiene_el_mismo_estado_y_tono_en_las_dos_pantallas(self):
        sector = self.sector
        libre = Plaza.objects.create(sector=sector, codigo="P3")
        prestada = Plaza.objects.create(sector=sector, codigo="P4")
        fuera = Plaza.objects.create(
            sector=sector, codigo="P5", estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="Rota"
        )
        ingresar_persona(
            ciudadano=self.otra_persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza
        )  # P1 ocupada
        reservar_plaza(plaza=self.otra_plaza, ciudadano=self.persona, usuario=self.operador_cis)  # P2 reservada
        reservar_plaza(
            plaza=prestada,
            ciudadano=self.persona,
            usuario=self.operador_cis,
            tipo=ReservaPlaza.Tipo.PRESTAMO,
            hasta=timezone.now() + timedelta(hours=12),
        )

        sectores = self.client.get(reverse("dispositivos:sectores", args=[self.cis.pk])).context["sectores"]
        en_p5 = {p["codigo"]: (p["estado"], p["tono"]) for item in sectores for p in item["plazas"]}
        self.client.post(self.url_persona, {"dni": self.persona.dni})
        sectores = self.client.get(self.url_plaza).context["sectores"]
        en_p6 = {p["codigo"]: (p["estado"], p["tono"]) for item in sectores for p in item["plazas"]}

        self.assertEqual(en_p5, en_p6)
        self.assertEqual(
            en_p5,
            {
                "P1": ("Ocupada", "info"),
                "P2": ("Reservada", "warning"),
                "P3": ("Disponible", "success"),
                "P4": ("Prestada", "brand"),
                "P5": ("Fuera de serv.", "danger"),
            },
        )
        self.assertEqual(libre.codigo, "P3")
        self.assertEqual(fuera.codigo, "P5")

    def test_el_encabezado_de_sectores_cuenta_lo_mismo_que_dibuja_el_mapa(self):
        Plaza.objects.create(sector=self.sector, codigo="P3")
        prestada = Plaza.objects.create(sector=self.sector, codigo="P4")
        Plaza.objects.create(
            sector=self.sector, codigo="P5", estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="Rota"
        )
        ingresar_persona(ciudadano=self.otra_persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)
        reservar_plaza(plaza=self.otra_plaza, ciudadano=self.persona, usuario=self.operador_cis)
        reservar_plaza(
            plaza=prestada,
            ciudadano=self.persona,
            usuario=self.operador_cis,
            tipo=ReservaPlaza.Tipo.PRESTAMO,
            hasta=timezone.now() + timedelta(hours=12),
        )

        contexto = self.client.get(reverse("dispositivos:sectores", args=[self.cis.pk])).context
        celdas = [p["estado"] for item in contexto["sectores"] for p in item["plazas"]]
        totales = contexto["totales"]

        self.assertEqual(totales["ocupadas"], celdas.count("Ocupada"))
        # El resumen de P5 desglosa el agregado del servicio con los mismos estados del mapa.
        self.assertEqual(totales["reservadas"], celdas.count("Reservada"))
        self.assertEqual(totales["prestadas"], celdas.count("Prestada"))
        self.assertEqual(totales["disponibles"], celdas.count("Disponible"))
        self.assertEqual(totales["fuera_servicio"], celdas.count("Fuera de serv."))
        self.assertEqual(totales["total"], len(celdas))
        # Y lo mismo por sector, que es lo que suma el encabezado.
        for item in contexto["sectores"]:
            estados = [p["estado"] for p in item["plazas"]]
            self.assertEqual(item["resumen"]["ocupadas"], estados.count("Ocupada"))
            self.assertEqual(item["resumen"]["reservadas"], estados.count("Reservada"))
            self.assertEqual(item["resumen"]["prestadas"], estados.count("Prestada"))
            self.assertEqual(item["resumen"]["disponibles"], estados.count("Disponible"))
        self.assertEqual(
            (totales["ocupadas"], totales["reservadas"], totales["prestadas"], totales["disponibles"]), (1, 1, 1, 1)
        )

    def test_una_plaza_ocupada_y_reservada_a_la_vez_se_cuenta_una_sola_vez(self):
        """El encabezado cuenta cada plaza **una** vez, con la misma precedencia que el mapa.

        El servicio de estadías no deja reservar una plaza ocupada ni alojar en una fuera de
        servicio, pero el modelo no lo impide: acá se escribe por el ORM, saltando la regla,
        que es justo el caso en que un conteo por cifra sueltas se descuadra.
        """

        tercera = Ciudadano.objects.create(dni="30555666", nombre="Luis", apellido="Sosa")
        fuera = Plaza.objects.create(sector=self.sector, codigo="P3")
        ingresar_persona(ciudadano=self.otra_persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)
        ingresar_persona(ciudadano=tercera, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.otra_plaza)
        hace_una_hora = timezone.now() - timedelta(hours=1)
        for plaza in (self.plaza, self.otra_plaza):  # ocupadas Y reservadas
            ReservaPlaza.objects.create(plaza=plaza, ciudadano=self.persona, desde=hace_una_hora)
        # Y una fuera de servicio con una estadía activa adentro.
        ingresar_persona(ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=fuera)
        Plaza.objects.filter(pk=fuera.pk).update(estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="Rota")

        contexto = self.client.get(reverse("dispositivos:sectores", args=[self.cis.pk])).context
        celdas = [p["estado"] for item in contexto["sectores"] for p in item["plazas"]]
        totales = contexto["totales"]

        self.assertEqual(celdas, ["Ocupada", "Ocupada", "Fuera de serv."])
        self.assertEqual(totales["ocupadas"], celdas.count("Ocupada"))
        self.assertEqual(totales["reservadas"], celdas.count("Reservada"))
        self.assertEqual(totales["prestadas"], celdas.count("Prestada"))
        self.assertEqual(totales["fuera_servicio"], celdas.count("Fuera de serv."))
        self.assertEqual(totales["disponibles"], celdas.count("Disponible"))
        self.assertGreaterEqual(totales["disponibles"], 0)
        self.assertEqual(
            totales["ocupadas"]
            + totales["reservadas"]
            + totales["prestadas"]
            + totales["fuera_servicio"]
            + totales["disponibles"],
            totales["total"],
        )


class DosPestanasTests(BaseIngreso):
    """Lo que se confirma es lo que la pantalla mostró, no lo que quedó en la sesión.

    Las pestañas de un mismo navegador comparten la sesión: si en otra se elige otra
    persona u otra plaza, el «Confirmar» de la primera no puede escribir lo de la segunda.
    """

    def test_confirmar_en_una_pestana_no_ingresa_a_la_persona_elegida_en_otra(self):
        # Pestaña A: Ana en P1, en «Confirmar».
        self._hasta_la_plaza(self.persona, self.plaza)
        pestana_a = self.client.get(self.url_confirmar)
        self.assertContains(pestana_a, "30.111.222")
        mostrado_en_a = self._campos_ocultos(pestana_a)

        # Pestaña B, misma sesión: Juan en P2.
        self._hasta_la_plaza(self.otra_persona, self.otra_plaza)

        # Se confirma en A.
        respuesta = self.client.post(self.url_confirmar, mostrado_en_a)

        self.assertFalse(
            Estadia.objects.filter(ciudadano=self.otra_persona).exists(),
            "se alojó a la persona de la otra pestaña, que esta pantalla nunca mostró",
        )
        self.assertFalse(Estadia.objects.exists())
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "cambió en otra pestaña")
        # El resumen se vuelve a mostrar con lo que hay ahora, y recién eso se puede confirmar.
        self.assertContains(respuesta, "30.333.444")
        self.client.post(self.url_confirmar, self._campos_ocultos(respuesta))
        self.assertEqual(Estadia.objects.get(ciudadano=self.otra_persona).plaza, self.otra_plaza)

    def test_tampoco_se_escribe_la_plaza_elegida_en_otra_pestana(self):
        self._hasta_la_plaza(self.persona, self.plaza)
        mostrado_en_a = self._campos_ocultos(self.client.get(self.url_confirmar))

        self._elegir_plaza(self.otra_plaza)  # en la pestaña B
        respuesta = self.client.post(self.url_confirmar, mostrado_en_a)

        self.assertFalse(Estadia.objects.exists())
        self.assertContains(respuesta, "cambió en otra pestaña")

    def test_sin_lo_que_se_mostro_no_se_confirma(self):
        self._hasta_la_plaza(self.persona, self.plaza)

        respuesta = self.client.post(self.url_confirmar, {})

        self.assertFalse(Estadia.objects.exists())
        self.assertContains(respuesta, "cambió en otra pestaña")

    def test_el_paso_de_la_plaza_no_guarda_la_plaza_si_otra_pestana_cambio_la_persona(self):
        # Pestaña A: Ana, en el paso de la plaza, con P1 marcada.
        self.client.post(self.url_persona, {"dni": self.persona.dni})
        mostrado_en_a = self._campos_ocultos(self.client.get(f"{self.url_plaza}?elegir={self.plaza.pk}"))

        # Pestaña B, misma sesión: Juan.
        self.client.post(self.url_persona, {"dni": self.otra_persona.dni})

        # «Continuar» en A.
        respuesta = self.client.post(self.url_plaza, mostrado_en_a)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "cambió en otra pestaña")
        estado = self.client.session["ingreso_asistente"][str(self.cis.pk)]
        self.assertEqual(estado["ciudadano_id"], self.otra_persona.pk)
        self.assertNotIn("plaza_id", estado, "se guardó para Juan la plaza que A eligió para Ana")
        self.assertRedirects(self.client.get(self.url_confirmar), self.url_plaza)

    def test_mismo_dni_con_otro_sexo_en_otra_pestana_no_da_de_alta_a_esa_persona(self):
        """Sin legajo, la persona es el DNI **y** el sexo con que se consultó el Registro de Personas."""

        marta = AltaDesdeElRegistroDePersonasTests.DATOS
        mario = {
            **marta,
            "data": {**marta["data"], "nombre": "Mario", "genero": "M", "fecha_nacimiento": "1975-01-09"},
        }
        # Pestaña A: Marta (DNI 27555666, F), en «Confirmar» con P1.
        with mock.patch("programas.services.ingreso.CiudadanosService.consultar_renaper", return_value=marta):
            self.client.post(self.url_persona, {"dni": "27555666", "sexo": "F"})
        self._elegir_plaza(self.plaza)
        pestana_a = self.client.get(self.url_confirmar)
        self.assertContains(pestana_a, "Marta")
        mostrado_en_a = self._campos_ocultos(pestana_a)

        # Pestaña B: el mismo DNI con sexo M es otra persona; también con P1.
        with mock.patch("programas.services.ingreso.CiudadanosService.consultar_renaper", return_value=mario):
            self.client.post(self.url_persona, {"dni": "27555666", "sexo": "M"})
        self._elegir_plaza(self.plaza)

        respuesta = self.client.post(self.url_confirmar, mostrado_en_a)

        self.assertFalse(
            Ciudadano.objects.filter(dni="27555666").exists(),
            "se dio de alta a la persona de la otra pestaña, que esta pantalla nunca mostró",
        )
        self.assertFalse(Estadia.objects.exists())
        self.assertContains(respuesta, "cambió en otra pestaña")
        self.assertContains(respuesta, "Mario")

    def test_abrir_el_asistente_de_otro_dispositivo_no_borra_el_progreso(self):
        rol = self.operador_cis.groups.get()
        AsignacionDispositivo.objects.create(dispositivo=self.parador, rol=rol, activo=True)
        self._hasta_la_plaza(self.persona, self.plaza)

        url_persona_parador = reverse("dispositivos:ingreso_persona", args=[self.parador.pk])
        self.client.post(url_persona_parador, {"dni": self.otra_persona.dni})

        respuesta = self.client.get(self.url_confirmar)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "30.111.222")


class EntrePasosTests(BaseIngreso):
    def test_si_borran_el_legajo_entre_pasos_vuelve_al_primero_sin_500(self):
        self._hasta_la_plaza(self.persona, self.plaza)
        mostrado = self._campos_ocultos(self.client.get(self.url_confirmar))
        Ciudadano.objects.filter(pk=self.persona.pk).delete()

        respuesta = self.client.post(self.url_confirmar, mostrado)

        self.assertRedirects(respuesta, self.url_persona, fetch_redirect_response=False)
        self.assertFalse(Estadia.objects.exists())

    def test_la_cache_del_legajo_se_invalida_recien_despues_del_commit(self):
        """Si se invalida adentro de la transacción, otra petición la vuelve a llenar con lo viejo."""

        with mock.patch(
            "programas.services.ingreso.CiudadanosService.consultar_renaper",
            return_value=AltaDesdeElRegistroDePersonasTests.DATOS,
        ):
            self.client.post(self.url_persona, {"dni": "27555666", "sexo": "F"})
        self._elegir_plaza(self.plaza)
        mostrado = self._campos_ocultos(self.client.get(self.url_confirmar))

        with mock.patch("programas.services.ingreso.CiudadanosService.invalidate_ciudadanos_cache") as invalidar:
            with self.captureOnCommitCallbacks(execute=False) as al_commit:
                self.client.post(self.url_confirmar, mostrado)
            invalidar.assert_not_called()
            for callback in al_commit:
                callback()
            invalidar.assert_called_once_with()
        self.assertTrue(Ciudadano.objects.filter(dni="27555666").exists())


class AltaMinimaTests(BaseIngreso):
    """La persona que no está en el legajo ni en el Registro de Personas se carga a mano.

    El Registro se mockea con la falla real de testing («Configuracion RENAPER incompleta»).
    """

    SIN_REGISTRO = {"success": False, "error": "Configuracion RENAPER incompleta (URL)."}
    DNI = "27555666"
    DATOS_FORM = {"nombre": "Marta", "apellido": "Ruiz", "fecha_nacimiento": "1980-05-02", "genero": "F"}

    def _consultar(self, dni=None, sexo="F", resultado=None, cliente=None):
        cliente = cliente or self.client
        with mock.patch(
            "programas.services.ingreso.CiudadanosService.consultar_renaper",
            return_value=resultado or self.SIN_REGISTRO,
        ):
            return cliente.post(self.url_persona, {"dni": dni or self.DNI, "sexo": sexo})

    def _enviar_alta(self, datos=None, ocultos=None):
        """Envía el formulario chico como lo hace el navegador: con sus ocultos."""

        ocultos = self._campos_ocultos(self.client.get(self.url_persona)) if ocultos is None else ocultos
        return self.client.post(self.url_persona, {**ocultos, **(datos or self.DATOS_FORM)})

    def _sesion(self):
        return self.client.session.get("ingreso_asistente", {}).get(str(self.cis.pk), {})

    def test_aparece_el_formulario_chico_y_la_sesion_recuerda_la_consulta(self):
        respuesta = self._consultar()

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "No encontramos a la persona")
        self.assertContains(
            respuesta,
            "No está en el Legajo Ciudadano ni en el Registro de Personas (Configuracion RENAPER incompleta (URL)).",
        )
        self.assertContains(respuesta, "Alta de la persona")
        self.assertEqual(self._sesion(), {"sin_registro": {"dni": self.DNI, "sexo": "F"}})
        self.assertFalse(Ciudadano.objects.filter(dni=self.DNI).exists())
        # Sin persona elegida, los pasos siguientes vuelven al primero.
        self.assertRedirects(self.client.get(self.url_plaza), self.url_persona)
        self.assertRedirects(self.client.get(self.url_confirmar), self.url_persona)

    def test_el_get_del_paso_vuelve_a_mostrar_el_formulario_chico(self):
        self._consultar()

        pagina = self.client.get(self.url_persona)

        self.assertContains(pagina, "No encontramos a la persona")
        self.assertContains(pagina, "Alta de la persona")
        self.assertContains(pagina, self.DNI)
        # Los dos formularios conviven: cada id aparece una sola vez.
        self.assertContains(pagina, 'id="id_dni"', count=1)
        self.assertContains(pagina, 'id="alta_dni"', count=1)

    def test_un_fallecido_despues_de_un_no_encontrada_descarta_el_alta_minima(self):
        self._consultar(sexo="F")
        self.assertEqual(self._sesion(), {"sin_registro": {"dni": self.DNI, "sexo": "F"}})

        respuesta = self._consultar(sexo="M", resultado={"success": False, "fallecido": True})

        self.assertContains(respuesta, "figura como fallecida")
        self.assertNotIn("sin_registro", self._sesion())
        pagina = self.client.get(self.url_persona)
        self.assertNotContains(pagina, "Alta de la persona")

    def test_buscar_otro_dni_descarta_el_alta_minima(self):
        self._consultar()

        self.client.post(self.url_persona, {"dni": self.persona.dni})

        self.assertNotIn("sin_registro", self._sesion())
        self.assertNotContains(self.client.get(self.url_persona), "Alta de la persona")

    def test_el_alta_valida_lleva_a_plaza_y_no_escribe_todavia(self):
        self._consultar()

        respuesta = self._enviar_alta()

        self.assertRedirects(respuesta, self.url_plaza)
        self.assertFalse(Ciudadano.objects.filter(dni=self.DNI).exists(), "un paso intermedio no escribe")
        self.assertEqual(
            self._sesion()["manual"],
            {
                "dni": self.DNI,
                "nombre": "Marta",
                "apellido": "Ruiz",
                "fecha_nacimiento": "1980-05-02",
                "genero": "F",
            },
        )
        self.assertContains(self.client.get(self.url_plaza), "Carga manual")

    def test_el_alta_valida_lleva_a_confirmar_si_el_tipo_no_maneja_plazas(self):
        self.tipo.plaza_obligatoria_al_ingresar = False
        self.tipo.save()
        self._consultar()

        respuesta = self._enviar_alta()

        self.assertRedirects(respuesta, self.url_confirmar)
        pagina = self.client.get(self.url_confirmar)
        self.assertContains(pagina, "cargados a mano, sin validar")

    def test_confirmar_crea_el_ciudadano_sin_estado_renaper_y_la_estadia(self):
        self._consultar()
        self._enviar_alta()
        self._elegir_plaza(self.plaza)

        respuesta = self._confirmar()

        self.assertRedirects(respuesta, reverse("dispositivos:detalle", args=[self.cis.pk]))
        ciudadano = Ciudadano.objects.get(dni=self.DNI)
        self.assertEqual((ciudadano.nombre, ciudadano.apellido, ciudadano.genero), ("Marta", "Ruiz", "F"))
        self.assertEqual(str(ciudadano.fecha_nacimiento), "1980-05-02")
        self.assertEqual(ciudadano.estado_renaper, "")
        self.assertEqual(Estadia.objects.get(ciudadano=ciudadano).plaza, self.plaza)

    def test_si_el_ingreso_falla_no_queda_el_ciudadano(self):
        self._consultar()
        self._enviar_alta()
        self._elegir_plaza(self.plaza)
        ingresar_persona(ciudadano=self.otra_persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)

        respuesta = self._confirmar()

        self.assertRedirects(respuesta, self.url_plaza)
        self.assertFalse(Ciudadano.objects.filter(dni=self.DNI).exists())
        self.assertFalse(Estadia.objects.filter(ciudadano__dni=self.DNI).exists())

    def test_el_dni_del_post_se_ignora_y_se_usa_el_de_la_sesion(self):
        self._consultar()
        ocultos = self._campos_ocultos(self.client.get(self.url_persona))

        self._enviar_alta({**self.DATOS_FORM, "dni": "11222333"}, ocultos)
        self._elegir_plaza(self.plaza)
        self._confirmar()

        self.assertTrue(Ciudadano.objects.filter(dni=self.DNI).exists())
        self.assertFalse(Ciudadano.objects.filter(dni="11222333").exists())

    def test_sin_alta_minima_en_la_sesion_el_envio_no_escribe(self):
        respuesta = self.client.post(
            self.url_persona,
            {"accion": "alta_minima", "persona": f"sin_registro:{self.DNI}:F", "dni": self.DNI, **self.DATOS_FORM},
        )

        self.assertRedirects(respuesta, self.url_persona, fetch_redirect_response=False)
        self.assertFalse(Ciudadano.objects.filter(dni=self.DNI).exists())
        self.assertNotIn("manual", self._sesion())
        self.assertRedirects(self.client.get(self.url_confirmar), self.url_persona)

    def test_sin_ciudadano_crear_no_hay_formulario_chico(self):
        sin_crear = self._operador("Admisor sin alta", self.cis, (*CAPACIDADES_OPERATIVAS, "ciudadano.ver"))
        cliente = self.client_class()
        cliente.force_login(sin_crear)

        respuesta = self._consultar(cliente=cliente)

        self.assertContains(respuesta, "no tenés permiso para darla de alta")
        self.assertNotContains(respuesta, "Alta de la persona")
        envio = cliente.post(
            self.url_persona,
            {"accion": "alta_minima", "persona": f"sin_registro:{self.DNI}:F", **self.DATOS_FORM},
        )
        self.assertEqual(envio.status_code, 403)
        self.assertFalse(Ciudadano.objects.filter(dni=self.DNI).exists())

    def test_el_fallecido_no_ofrece_alta_minima(self):
        respuesta = self._consultar(resultado={"success": False, "fallecido": True})

        self.assertContains(respuesta, "figura como fallecida")
        self.assertNotContains(respuesta, "Alta de la persona")
        self.assertNotIn("sin_registro", self._sesion())

    def test_sin_sexo_sigue_pidiendo_el_sexo(self):
        respuesta = self.client.post(self.url_persona, {"dni": self.DNI})

        self.assertContains(respuesta, "Indicá el sexo")
        self.assertNotContains(respuesta, "Alta de la persona")

    def test_si_aparece_en_el_legajo_entre_pasos_se_usa_la_existente(self):
        self._consultar()
        ocultos = self._campos_ocultos(self.client.get(self.url_persona))
        existente = Ciudadano.objects.create(dni=self.DNI, nombre="Marta", apellido="Ruiz")

        respuesta = self._enviar_alta({**self.DATOS_FORM, "nombre": "Otra"}, ocultos)

        self.assertRedirects(respuesta, self.url_plaza)
        self.assertEqual(self._sesion(), {"ciudadano_id": existente.pk})
        self._elegir_plaza(self.plaza)
        self._confirmar()
        self.assertEqual(Ciudadano.objects.filter(dni=self.DNI).count(), 1)
        self.assertEqual(Estadia.objects.get(ciudadano=existente).plaza, self.plaza)

    def test_si_la_existente_ya_esta_alojada_se_avisa(self):
        self._consultar()
        ocultos = self._campos_ocultos(self.client.get(self.url_persona))
        existente = Ciudadano.objects.create(dni=self.DNI, nombre="Marta", apellido="Ruiz")
        ingresar_persona(
            ciudadano=existente, dispositivo=self.parador, usuario=self.operador_parador, plaza=self.plaza_parador
        )

        respuesta = self._enviar_alta(ocultos=ocultos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "La persona ya está alojada")

    def test_sin_nombre_o_apellido_el_error_queda_en_el_formulario_chico(self):
        self._consultar()

        for faltante in ("nombre", "apellido"):
            with self.subTest(faltante=faltante):
                respuesta = self._enviar_alta({**self.DATOS_FORM, faltante: ""})
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, "Alta de la persona")
                self.assertContains(respuesta, f'data-error="{faltante}">Este campo es requerido.')
                self.assertNotIn("manual", self._sesion())

    def test_la_fecha_de_nacimiento_futura_se_rechaza(self):
        self._consultar()

        futura = (timezone.localdate() + timedelta(days=1)).isoformat()
        respuesta = self._enviar_alta({**self.DATOS_FORM, "fecha_nacimiento": futura})

        self.assertContains(respuesta, "no puede ser futura")
        self.assertNotIn("manual", self._sesion())

    def test_la_fecha_y_el_genero_son_opcionales(self):
        self._consultar()

        respuesta = self._enviar_alta({"nombre": "Marta", "apellido": "Ruiz"})

        self.assertRedirects(respuesta, self.url_plaza)
        self.assertIsNone(self._sesion()["manual"]["fecha_nacimiento"])

    def test_el_formulario_de_otra_pestana_no_guarda_nada(self):
        self._consultar()
        ocultos = self._campos_ocultos(self.client.get(self.url_persona))
        self._consultar(dni="30999888", sexo="M")  # otra pestaña consulta a otra persona

        respuesta = self._enviar_alta(ocultos=ocultos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("manual", self._sesion())
        self.assertFalse(Ciudadano.objects.filter(dni__in=[self.DNI, "30999888"]).exists())

    def test_otra_pestana_rehace_el_alta_del_mismo_dni_y_no_se_da_de_alta_la_que_no_se_mostro(self):
        self._consultar()
        self._enviar_alta()
        self._elegir_plaza(self.plaza)
        mostrado_a = self._campos_ocultos(self.client.get(self.url_confirmar))
        self._consultar()
        self._enviar_alta({**self.DATOS_FORM, "nombre": "Otra"})
        self._elegir_plaza(self.plaza)

        respuesta = self.client.post(self.url_confirmar, mostrado_a)

        self.assertFalse(Ciudadano.objects.filter(dni=self.DNI).exists())
        self.assertContains(respuesta, "cambió en otra pestaña")

    def test_confirmar_una_alta_manual_exige_ciudadano_crear(self):
        self._consultar()
        self._enviar_alta()
        self._elegir_plaza(self.plaza)
        ocultos = self._campos_ocultos(self.client.get(self.url_confirmar))
        self.operador_cis.groups.first().permissions.remove(_permiso("ciudadano.crear"))

        respuesta = self.client.post(self.url_confirmar, ocultos)

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Ciudadano.objects.filter(dni=self.DNI).exists())

    def test_la_huella_de_una_persona_manual_y_una_del_registro_difiere(self):
        manual = {"dni": self.DNI, "nombre": "Marta", "apellido": "Ruiz", "fecha_nacimiento": None, "genero": "F"}
        huella_manual = IngresoBaseView.huella_persona({"manual": manual, "sexo": "F"})
        huella_registro = IngresoBaseView.huella_persona({"renaper": manual, "sexo": "F"})

        self.assertTrue(huella_manual.startswith(f"manual:{self.DNI}:F:"))
        self.assertNotEqual(huella_manual, huella_registro)
