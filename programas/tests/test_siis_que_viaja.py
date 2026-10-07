"""Qué viaja a SIIS: la foto manda, gana el más específico y la identidad valida.

Las cuatro fichas del PR 6 de la Ola 1 tocan el mismo punto desde ángulos
distintos: **el payload del alta no puede salir con un dato que nadie decidió
mandar**, porque el alta en SIIS no tiene baja.

* **SIIS-08** — una identidad acreditada por el padrón o por Base de Personas que
  cae sobre un legajo autodeclarado no corregía nada: el caso quedaba validado y
  el alta salía con el nombre del legajo, que es el que nadie verificó.
* **G1-08** — el mapeo «esta pregunta alimenta este campo de SIIS» se leía del
  catálogo de hoy, no de la foto del caso. Desactivar «Calle y altura» para
  reemplazarla mandaba de golpe a todos los aprobados pendientes como «Planta
  urbana sin número», altura 1, sin un solo error.
* **G1-09** — la regla «una sola pregunta activa por destino SIIS» vivía en el
  form y el botón de activar/desactivar no pasa por el form: con dos activas,
  lo informado dependía del orden físico de la tabla.
* **G1-10** — entre dos campos marcados con el mismo destino ganaba el de mayor
  ``orden``, así que un requisito del programa le ganaba al del subsegmento.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from legajos.models import Ciudadano
from programas.models import (
    Formulario,
    PreguntaGlobal,
    RequisitoNativo,
    Subsegmento,
    TipoCampo,
)
from programas.services import siis_envio
from programas.services.becas import resolver_ciudadano_offline
from programas.services.identidad import CLAVE_IDENTIDAD_ACREDITADA
from programas.services.respuestas import foto_definicion
from programas.services.siis_envio import armar_payload, respuestas_por_destino
from programas.tests.test_siis_envio import _catalogo_falso, _ConPayloadCompleto


class _ConFoto(_ConPayloadCompleto):
    """El caso completo de siempre, pero con la foto de su definición guardada.

    Es el estado normal desde el Cambio 58: todo caso nuevo —app de campo o link
    público— guarda la definición que tenía delante. Los tests de
    ``test_siis_envio`` trabajan sobre casos **sin** foto a propósito: son los
    anteriores, los que siguen interpretándose con el catálogo de hoy.
    """

    def setUp(self):
        super().setUp()
        self._sacar_foto()

    def _sacar_foto(self):
        self.formulario.definicion = foto_definicion(self.relevamiento)
        self.formulario.save(update_fields=["definicion"])
        return self.formulario.definicion


class FotoDelDestinoTests(_ConFoto):
    """G1-08: el destino SIIS de cada campo sale de la foto del caso."""

    def test_la_foto_declara_los_destinos_de_los_campos_marcados(self):
        destinos = self.formulario.definicion["destinos_siis"]
        por_clave = {d["clave"]: d["destino"] for d in destinos}
        self.assertEqual(por_clave[f"pg-{self.p_calle.pk}"], "calle_altura")
        self.assertEqual(por_clave[f"pg-{self.p_civil.pk}"], "est_civil")
        # Solo los marcados: una pregunta sin destino no ocupa lugar en la foto.
        self.assertTrue(all(d["destino"] for d in destinos))

    def test_desactivar_la_pregunta_no_cambia_lo_que_ya_se_respondio(self):
        """El escenario de la ficha, con el costo que tenía: sin la foto, los
        casos aprobados y todavía no informados salían con el domicilio
        aproximado del Cambio 89 y nadie se enteraba hasta verlo en SIIS."""
        self.p_calle.activo = False
        self.p_calle.save(update_fields=["activo"])

        payload, faltantes = armar_payload(self.formulario, catalogos=self.cat, hoy=date(2026, 9, 14))

        self.assertEqual(faltantes, {})
        self.assertEqual(payload["calle_actual"], "AV. 9 DE JULIO")
        self.assertEqual(payload["nro_actual"], 450)

    def test_cambiarle_el_destino_a_la_pregunta_no_reinterpreta_el_caso(self):
        """El otro camino del mismo agujero: ``PreguntaGlobalUpdateView`` deja
        cambiar ``destino_siis``, y con el catálogo vivo la respuesta «BARRIO
        CENTRO» de un caso viejo pasaba a viajar como otra cosa."""
        self.p_barrio.destino_siis = PreguntaGlobal.DestinoSiis.LOCALIDAD_NACIMIENTO
        self.p_barrio.save(update_fields=["destino_siis"])

        respuestas = respuestas_por_destino(self.formulario)

        self.assertEqual(respuestas["barrio_actual"], "BARRIO CENTRO")
        self.assertEqual(respuestas["loc_nacim"], "Resistencia")

    def test_desactivar_la_pregunta_si_alcanza_a_un_caso_sin_foto(self):
        """Caracterización del camino viejo, que sigue siendo el único posible
        para los casos anteriores a este cambio: no hay otra fuente que el
        catálogo de hoy."""
        self.formulario.definicion = None
        self.formulario.save(update_fields=["definicion"])
        self.p_calle.activo = False
        self.p_calle.save(update_fields=["activo"])

        payload, _ = armar_payload(self.formulario, catalogos=self.cat, hoy=date(2026, 9, 14))

        self.assertEqual(payload["calle_actual"], siis_envio.CALLE_SIN_NUMERO)
        self.assertEqual(payload["nro_actual"], siis_envio.ALTURA_SIN_NUMERO)

    def test_una_foto_vieja_sin_destinos_cae_al_catalogo(self):
        """Una foto guardada antes de G1-08 no tiene la clave: no es «el caso no
        tenía campos marcados», es «esta foto no sabe»."""
        foto = dict(self.formulario.definicion)
        foto.pop("destinos_siis")
        self.formulario.definicion = foto
        self.formulario.save(update_fields=["definicion"])

        self.assertEqual(respuestas_por_destino(self.formulario)["barrio_actual"], "BARRIO CENTRO")

    def test_el_payload_es_el_mismo_por_los_dos_caminos(self):
        """Contrato: cambiar de dónde sale el mapeo no cambia lo que viaja."""
        con_foto, faltantes_foto = armar_payload(self.formulario, catalogos=self.cat, hoy=date(2026, 9, 14))
        self.formulario.definicion = None
        self.formulario.save(update_fields=["definicion"])
        sin_foto, faltantes_sin = armar_payload(self.formulario, catalogos=self.cat, hoy=date(2026, 9, 14))

        self.assertEqual(faltantes_foto, {})
        self.assertEqual(faltantes_sin, {})
        self.assertEqual(
            con_foto,
            {
                "dni": 20301234,
                "tdoc": 1,
                "cuil_pref": 23,
                "cuil_dig": 9,
                "apellido": "PEREZ",
                "nombre": "JUAN CARLOS",
                "sexo": "M",
                "est_civil": 1,
                "prov_nacim": 22,
                "fecha_nacim": "1995-06-15",
                "loc_nacim": 1,
                "celular": 3624123456,
                "prov_actual": 22,
                "loc_actual": 1,
                "barrio_actual": "BARRIO CENTRO",
                "calle_actual": "AV. 9 DE JULIO",
                "nro_actual": 450,
                "piso_actual": 2,
                "dpto_actual": "B",
                "correo_electron": "juan.perez@email.com",
                "jurid": 28,
                "id_plan_soc": 79,
                "id_fun_x_plan": 4,
            },
        )
        self.assertEqual(con_foto, sin_foto)


class EspecificidadDelDestinoTests(_ConPayloadCompleto):
    """G1-10: entre dos campos con el mismo destino gana el más específico."""

    def setUp(self):
        super().setUp()
        self.subsegmento = Subsegmento.objects.create(segmento=self.segmento, nombre="Sub", cupo_maximo=5)
        self.convocatoria.subsegmento = self.subsegmento
        self.convocatoria.save(update_fields=["subsegmento"])

    def _requisito(self, texto, destino, orden, **ancla):
        return RequisitoNativo.objects.create(
            texto=texto, tipo=TipoCampo.STRING, destino_siis=destino, orden=orden, **ancla
        )

    def _responder(self, por_requisito):
        self.formulario.data["requisitos"] = {str(r.pk): valor for r, valor in por_requisito.items()}
        self.formulario.save(update_fields=["data"])

    def test_el_requisito_del_subsegmento_le_gana_al_del_programa(self):
        """El del programa tiene ``orden`` más alto, que era lo único que se
        miraba: el payload llevaba el dato general habiendo uno particular."""
        del_programa = self._requisito(
            "Barrio (programa)", PreguntaGlobal.DestinoSiis.BARRIO, orden=9, programa=self.programa
        )
        del_sub = self._requisito(
            "Barrio (subsegmento)", PreguntaGlobal.DestinoSiis.BARRIO, orden=1, subsegmento=self.subsegmento
        )
        self._responder({del_programa: "Barrio General", del_sub: "Villa Libertad"})

        self.assertEqual(respuestas_por_destino(self.formulario)["barrio_actual"], "Villa Libertad")

    def test_el_del_segmento_le_gana_al_del_programa_y_pierde_con_el_subsegmento(self):
        del_programa = self._requisito(
            "Barrio (programa)", PreguntaGlobal.DestinoSiis.BARRIO, orden=9, programa=self.programa
        )
        del_segmento = self._requisito(
            "Barrio (segmento)", PreguntaGlobal.DestinoSiis.BARRIO, orden=8, segmento=self.segmento
        )
        self._responder({del_programa: "General", del_segmento: "Del segmento"})
        self.assertEqual(respuestas_por_destino(self.formulario)["barrio_actual"], "Del segmento")

        del_sub = self._requisito(
            "Barrio (subsegmento)", PreguntaGlobal.DestinoSiis.BARRIO, orden=0, subsegmento=self.subsegmento
        )
        self._responder({del_programa: "General", del_segmento: "Del segmento", del_sub: "Del sub"})
        self.assertEqual(respuestas_por_destino(self.formulario)["barrio_actual"], "Del sub")

    def test_dentro_del_mismo_nivel_sigue_desempatando_el_orden(self):
        primero = self._requisito("Barrio A", PreguntaGlobal.DestinoSiis.BARRIO, orden=1, segmento=self.segmento)
        segundo = self._requisito("Barrio B", PreguntaGlobal.DestinoSiis.BARRIO, orden=2, segmento=self.segmento)
        self._responder({primero: "Primero", segundo: "Segundo"})

        self.assertEqual(respuestas_por_destino(self.formulario)["barrio_actual"], "Segundo")

    def test_el_requisito_le_sigue_ganando_a_la_pregunta_general(self):
        """Cambio 80, que esta ficha no cambia: la general es el piso de todos."""
        del_programa = self._requisito(
            "Barrio (programa)", PreguntaGlobal.DestinoSiis.BARRIO, orden=0, programa=self.programa
        )
        self._responder({del_programa: "Del programa"})

        self.assertEqual(respuestas_por_destino(self.formulario)["barrio_actual"], "Del programa")

    def test_la_especificidad_tambien_vale_leyendo_la_foto(self):
        del_programa = self._requisito(
            "Barrio (programa)", PreguntaGlobal.DestinoSiis.BARRIO, orden=9, programa=self.programa
        )
        del_sub = self._requisito(
            "Barrio (subsegmento)", PreguntaGlobal.DestinoSiis.BARRIO, orden=1, subsegmento=self.subsegmento
        )
        self._responder({del_programa: "Barrio General", del_sub: "Villa Libertad"})
        self.formulario.definicion = foto_definicion(self.relevamiento)
        self.formulario.save(update_fields=["definicion"])

        niveles = {d["clave"]: d["alcance"] for d in self.formulario.definicion["destinos_siis"]}
        self.assertEqual(niveles[f"rn-{del_sub.pk}"], "subsegmento")
        self.assertEqual(niveles[f"rn-{del_programa.pk}"], "programa")
        self.assertEqual(respuestas_por_destino(self.formulario)["barrio_actual"], "Villa Libertad")


class ToggleDeDestinoOcupadoTests(TestCase):
    """G1-09: el botón de activar/desactivar respeta «una sola por destino»."""

    def setUp(self):
        self.admin = User.objects.create_superuser("admin", "a@a.com", "x")
        self.client.force_login(self.admin)
        self.vigente = PreguntaGlobal.objects.create(
            texto="Estado civil (vigente)",
            tipo=TipoCampo.STRING,
            destino_siis=PreguntaGlobal.DestinoSiis.ESTADO_CIVIL,
            activo=True,
        )
        self.vieja = PreguntaGlobal.objects.create(
            texto="Estado civil (vieja)",
            tipo=TipoCampo.STRING,
            destino_siis=PreguntaGlobal.DestinoSiis.ESTADO_CIVIL,
            activo=False,
        )

    def _toggle(self, pregunta):
        return self.client.post(reverse("becas:pregunta_toggle", args=[pregunta.pk]), follow=True)

    def test_reactivar_con_el_destino_ocupado_no_activa_y_lo_dice(self):
        respuesta = self._toggle(self.vieja)

        self.vieja.refresh_from_db()
        self.assertFalse(self.vieja.activo)
        avisos = [str(m) for m in respuesta.context["messages"]]
        self.assertTrue(any("Estado civil (vigente)" in a for a in avisos), avisos)
        self.assertTrue(any("ya hay una pregunta activa" in a.lower() for a in avisos), avisos)

    def test_desactivar_la_vigente_libera_el_destino(self):
        self._toggle(self.vigente)
        self.vigente.refresh_from_db()
        self.assertFalse(self.vigente.activo)

        self._toggle(self.vieja)
        self.vieja.refresh_from_db()
        self.assertTrue(self.vieja.activo)

    def test_una_pregunta_sin_destino_se_activa_sin_mirar_a_nadie(self):
        suelta = PreguntaGlobal.objects.create(texto="Comentario", tipo=TipoCampo.STRING, activo=False)

        self._toggle(suelta)

        suelta.refresh_from_db()
        self.assertTrue(suelta.activo)

    def test_un_destino_fuera_del_enum_no_da_500(self):
        """Ronda 2: ``destino_siis`` es un `CharField` con `choices`, así que la
        base acepta cualquier texto. Un valor viejo —de una lista anterior, de un
        `update()` o de un restore— hacía explotar `DestinoSiis(valor)` y el
        botón respondía 500 en vez de decir lo que pasaba."""
        PreguntaGlobal.objects.filter(pk__in=[self.vigente.pk, self.vieja.pk]).update(destino_siis="est_civil_viejo")

        respuesta = self._toggle(self.vieja)

        self.assertEqual(respuesta.status_code, 200)
        self.vieja.refresh_from_db()
        self.assertFalse(self.vieja.activo)
        avisos = [str(m) for m in respuesta.context["messages"]]
        self.assertTrue(any("est_civil_viejo" in a for a in avisos), avisos)

    def test_desactivar_nunca_se_bloquea_por_esta_regla(self):
        """Dos activas con el mismo destino es un estado que ya puede existir en
        la base: la salida tiene que seguir abierta."""
        PreguntaGlobal.objects.filter(pk=self.vieja.pk).update(activo=True)

        self._toggle(self.vieja)

        self.vieja.refresh_from_db()
        self.assertFalse(self.vieja.activo)


class IdentidadAcreditadaTests(_ConPayloadCompleto):
    """SIIS-08: un legajo que contradice la identidad validada no se informa."""

    def setUp(self):
        super().setUp()
        self.legajo = Ciudadano.objects.create(
            dni="27888999", nombre="Juana", apellido="Gomez", fecha_nacimiento=date(1990, 3, 2), genero="F"
        )
        self.caso = Formulario.objects.create(
            relevamiento=self.relevamiento,
            estado=Formulario.Estado.APROBADO,
            data=self.formulario.data,
            datos_identificacion={
                "dni": "27888999",
                "sexo": "F",
                "nombre": "Juana Maria",
                "apellido": "Gomez Fernandez",
                "fecha_nacimiento": "1990-03-02",
                "origen": "padron",
            },
        )

    def _resolver(self):
        resolver_ciudadano_offline(self.caso)
        self.caso.refresh_from_db()

    def test_la_identidad_acreditada_queda_registrada_y_frena_el_envio(self):
        self._resolver()

        acreditada = self.caso.datos_siis[CLAVE_IDENTIDAD_ACREDITADA]
        self.assertEqual(acreditada["apellido"], "Gomez Fernandez")
        self.assertEqual(acreditada["origen"], "padron")
        trazas = list(self.caso.trazas.values_list("campo", "valor_anterior", "valor_nuevo"))
        self.assertIn(("Identidad acreditada (padron) · apellido", "Gomez", "Gomez Fernandez"), trazas)

        _, faltantes = armar_payload(self.caso, catalogos=self.cat, hoy=date(2026, 9, 14))
        self.assertIn("identidad", faltantes)
        self.assertIn("Gomez Fernandez", faltantes["identidad"])

    def test_un_legajo_en_conflicto_no_llega_a_llamar_a_siis(self):
        self._resolver()

        with patch.object(siis_envio, "cargar_beneficiario") as cargar:
            envio = siis_envio.enviar_beneficiario_a_siis(self.caso, self.user, catalogos=self.cat)

        cargar.assert_not_called()
        self.assertEqual(envio.estado, siis_envio.EnvioSIIS.Estado.INCOMPLETO)
        self.assertIn("identidad", envio.detalles)

    def test_corregir_el_legajo_destraba_el_caso_sin_tocar_la_marca(self):
        """Se guarda la identidad acreditada, no «hay conflicto»: la comparación
        se rehace contra el legajo de ahora. Si se guardara la marca, el caso
        quedaría bloqueado para siempre salvo que alguien se acordara de
        borrarla a mano."""
        self._resolver()
        Ciudadano.objects.filter(pk=self.legajo.pk).update(nombre="Juana Maria", apellido="Gomez Fernandez")
        self.caso.refresh_from_db()

        _, faltantes = armar_payload(self.caso, catalogos=self.cat, hoy=date(2026, 9, 14))

        self.assertNotIn("identidad", faltantes)
        self.assertIn(CLAVE_IDENTIDAD_ACREDITADA, self.caso.datos_siis)

    def test_un_legajo_que_coincide_no_deja_marca_ni_traza(self):
        self.caso.datos_identificacion = {**self.caso.datos_identificacion, "nombre": "JUANA", "apellido": "GÓMEZ"}
        self.caso.save(update_fields=["datos_identificacion"])

        self._resolver()

        self.assertEqual(self.caso.datos_siis, {})
        self.assertEqual(self.caso.trazas.count(), 0)

    def test_una_identidad_autodeclarada_nunca_marca_conflicto(self):
        """Lo que la persona dijo de sí misma no acredita nada: no puede frenar
        un envío por «no coincidir» con el legajo."""
        self.caso.datos_identificacion = {**self.caso.datos_identificacion, "origen": "manual"}
        self.caso.save(update_fields=["datos_identificacion"])

        self._resolver()

        self.assertEqual(self.caso.datos_siis, {})

    def test_un_campo_vacio_en_el_legajo_no_es_un_conflicto_de_identidad(self):
        """Que falte la fecha de nacimiento ya lo reclama el payload por su
        cuenta; marcarlo como conflicto mandaría a revisar la identidad de
        alguien por un dato que simplemente no está."""
        Ciudadano.objects.filter(pk=self.legajo.pk).update(
            nombre="Juana Maria", apellido="Gomez Fernandez", fecha_nacimiento=None
        )

        self._resolver()

        self.assertEqual(self.caso.datos_siis, {})

    def test_un_legajo_nuevo_se_crea_con_la_identidad_acreditada(self):
        self.legajo.delete()

        self._resolver()

        self.assertEqual(self.caso.ciudadano.apellido, "Gomez Fernandez")
        self.assertEqual(self.caso.datos_siis, {})


class CatalogosFueraDelRequestTests(TestCase):
    """SIIS-09, ronda 2: dentro de un request no se le pide un catálogo a SIIS.

    La cadena de «Aprobar» ya gasta los 55 s de presupuesto que deja nginx; tres
    GET de catálogo con la caché fría la llevaban a 100 sin que el check de
    ``core.E003`` pudiera verlo, porque la cadena declarada no los nombraba.
    """

    def setUp(self):
        cache.clear()

    def test_las_vistas_que_dan_de_alta_usan_los_catalogos_sin_red(self):
        from programas.views import cupo as vista_cupo
        from programas.views import revision as vista_revision

        for modulo in (vista_revision, vista_cupo):
            with self.subTest(modulo=modulo.__name__):
                codigo = modulo._informar_a_siis.__code__
                self.assertIn("sin_red", codigo.co_names, f"{modulo.__name__} volvió a pedir catálogos a la red")

    def test_sin_copia_local_el_catalogo_falla_sin_tocar_la_red(self):
        from programas.services.siis import SiisCatalogError, catalogo_local

        with self.assertRaisesMessage(SiisCatalogError, "copia local"):
            catalogo_local("estados-civiles")

    def test_la_copia_local_se_lee_sin_cache_y_sin_red(self):
        from programas.models import CatalogoSiisLocal
        from programas.services.siis import catalogo_local

        CatalogoSiisLocal.objects.create(nombre="estados-civiles", items=[{"id": 1, "nombre": "Soltero/a"}])

        self.assertEqual(catalogo_local("estados-civiles"), [{"id": 1, "nombre": "Soltero/a"}])

    def test_cada_lectura_del_catalogo_deja_la_copia_al_dia(self):
        from programas.models import CatalogoSiisLocal
        from programas.services import siis as siis_mod

        with patch.object(
            siis_mod.SiisAPIClient, "_cargar_catalogo", return_value={"items": [{"id": 1, "nombre": "A"}]}
        ):
            siis_mod.catalogo("estados-civiles")

        self.assertEqual(CatalogoSiisLocal.objects.get(nombre="estados-civiles").items, [{"id": 1, "nombre": "A"}])

    def test_un_catalogo_vacio_no_pisa_la_copia_buena(self):
        """Mismo criterio que SIIS-06: una lista vacía resultó ser un error del
        servicio, y pisar la copia dejaría a todos los casos sin localidad."""
        from programas.models import CatalogoSiisLocal
        from programas.services import siis as siis_mod

        CatalogoSiisLocal.objects.create(nombre="provincias", items=[{"id": 22, "nombre": "Chaco"}])

        siis_mod.guardar_catalogo_local("provincias", [])

        self.assertEqual(CatalogoSiisLocal.objects.get(nombre="provincias").items, [{"id": 22, "nombre": "Chaco"}])

    def test_los_catalogos_sin_red_resuelven_el_payload(self):
        """La prueba de que la copia alcanza: el mismo caso completo, armado con
        los catálogos que no salen a la red."""
        from programas.models import CatalogoSiisLocal
        from programas.services.siis_envio import Catalogos

        for nombre in ("provincias", "localidades", "estados-civiles"):
            CatalogoSiisLocal.objects.create(nombre=nombre, items=_catalogo_falso(nombre))

        catalogos = Catalogos.sin_red()

        self.assertEqual(catalogos.provincia_id("Chaco"), 22)
        self.assertEqual(catalogos.localidad_id("Resistencia", 22), 1)
        self.assertEqual(catalogos.estado_civil_id("Soltero/a"), 1)


class SinCopiaDeCatalogosTests(_ConPayloadCompleto):
    """Ronda 2: lo que ve el coordinador el día 1, antes de que la copia exista.

    El toast decía «SIIS no respondió correctamente», que es **lo contrario** de
    lo que pasó: no se consultó a SIIS. Mandaba a revisar un servicio externo
    que nadie tocó, en vez de a bajar la copia a esta base.
    """

    def test_sin_copia_el_envio_queda_error_reintentable_con_su_propio_codigo(self):
        with patch.object(siis_envio, "cargar_beneficiario") as cargar:
            envio = siis_envio.enviar_beneficiario_a_siis(
                self.formulario, self.user, catalogos=siis_envio.Catalogos.sin_red()
            )

        cargar.assert_not_called()
        self.assertEqual(envio.estado, siis_envio.EnvioSIIS.Estado.ERROR)
        self.assertEqual(envio.codigo_error, siis_envio.CODIGO_SIN_COPIA_CATALOGO)
        # Reintentable: no queda vigente, así que el caso vuelve a los candidatos.
        self.assertIsNone(envio.vigente)

    def test_el_toast_dice_que_faltan_los_catalogos_y_no_que_siis_fallo(self):
        envio = siis_envio.EnvioSIIS(
            estado=siis_envio.EnvioSIIS.Estado.ERROR, codigo_error=siis_envio.CODIGO_SIN_COPIA_CATALOGO
        )

        nivel, texto = siis_envio.mensaje_envio(envio)

        self.assertEqual(nivel, "warning")
        self.assertIn("Faltan los catálogos de SIIS", texto)
        self.assertIn("sincronizar_programas_siis", texto)
        self.assertNotIn("SIIS no respondió", texto)

    def test_un_error_tecnico_de_verdad_sigue_diciendo_que_siis_no_respondio(self):
        """El mensaje nuevo es para **este** caso y no para todos los ERROR."""
        envio = siis_envio.EnvioSIIS(estado=siis_envio.EnvioSIIS.Estado.ERROR, codigo_error="ERROR_TECNICO")

        nivel, texto = siis_envio.mensaje_envio(envio)

        self.assertEqual(nivel, "error")
        self.assertIn("SIIS no respondió", texto)

    def test_un_catalogo_que_si_se_consulto_y_fallo_no_usa_el_codigo_nuevo(self):
        """SIIS caído de verdad (el masivo y los comandos, que sí van a la red):
        sigue siendo `ERROR_TECNICO`."""

        def se_cae(nombre):
            raise siis_envio.SiisCatalogError("SIIS tardó demasiado en responder.")

        with patch.object(siis_envio, "cargar_beneficiario"):
            envio = siis_envio.enviar_beneficiario_a_siis(
                self.formulario, self.user, catalogos=siis_envio.Catalogos(cargar=se_cae)
            )

        self.assertEqual(envio.codigo_error, "ERROR_TECNICO")
