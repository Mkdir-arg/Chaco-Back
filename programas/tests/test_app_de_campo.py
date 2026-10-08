"""La app de campo contra el servidor: gracia de sincronización, validación de
la carga, fecha de nacimiento, adjuntos y versión del diseño (G1-04 + BEC-22,
G1-05, G1-06, G1-07 y G1-16).

La app (`Chaco-mobile`) es **otro repo** y la versión instalada en producción es
`origin/main @ a66c2d3` (21/08/2026). Nada de lo que hay acá le pide un release:
lo que cambia del lado del servidor es que **acepta más** —capturas que antes
rechazaba— y que marca lo que antes no contaba. Lo que la app ya mandaba sigue
significando lo mismo. G1-16 **habilita** un dato nuevo y opcional: mandarlo es
lo que necesita una release de la app, no seguir sin mandarlo.

Las fichas comparten un criterio: una captura la hizo un territorial parado
delante de una persona. Tirarla sin dejar rastro es perder trabajo de campo, así
que se acepta y se marca; solo se rechaza lo que no se puede arreglar después.
"""

import shutil
import tempfile
from datetime import timedelta
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import (
    AdjuntoFormulario,
    CanalFormulario,
    Formulario,
    GrupoRequisito,
    ItemDiseno,
    PreguntaGlobal,
    Relevamiento,
    TipoCampo,
)
from programas.services import campo
from programas.services.vencimientos import pasar_relevamientos_a_revision, relevamientos_de_convocatoria_vencida
from programas.tests.test_becas_api import _BaseApiTest


class _CampoBase(_BaseApiTest):
    def setUp(self):
        super().setUp()
        self.autenticar(self.terri)
        self.url = reverse("becas_api:relevamiento-formularios", args=[self.rel.pk])

    def _payload(self, **extra):
        cuerpo = {
            "client_uuid": str(uuid4()),
            "celular": "3624111222",
            "email_contacto": "x@y.com",
            "gps_lat": "-27.451000",
            "gps_lng": "-58.986000",
            "datos_identificacion": {
                "dni": "40400400",
                "nombre": "Juan",
                "apellido": "Perez",
                "sexo": "M",
                "fecha_nacimiento": "1990-01-02",
            },
            "data": {"globales": {}, "requisitos": {}},
        }
        cuerpo.update(extra)
        return cuerpo

    def _cerrar(self, estado, *, hace=timedelta(hours=2)):
        """Deja el relevamiento con el período vencido `hace` y en `estado`,
        que es lo que deja el cron de las 03:10."""
        fin = timezone.now() - hace
        Relevamiento.objects.filter(pk=self.rel.pk).update(
            estado=estado,
            fecha_asignada=fin - timedelta(days=1),
            fecha_hasta=fin,
        )
        self.rel.refresh_from_db()
        return fin


class GraciaDeSincronizacionTests(_CampoBase):
    """G1-04 · lo que el teléfono subió tarde.

    El escenario medido: último día del relevamiento, zona sin señal, quince
    personas cargadas. Al día siguiente el cron ya pasó el relevamiento a
    `EN_REVISION` y la cola offline empieza a subir. El alta respondía 409 y la
    app clasifica un 409 que no sea de pausa como `FAILED_PERMANENT`
    (`relevamientoService.js`): las quince capturas quedaban en el teléfono y el
    backoffice nunca se enteraba de que existían.
    """

    def test_una_captura_en_fecha_entra_con_el_relevamiento_ya_en_revision(self):
        fin = self._cerrar(Relevamiento.Estado.EN_REVISION)

        resp = self.client.post(
            self.url,
            self._payload(capturado_en=(fin - timedelta(hours=1)).isoformat()),
            format="json",
        )

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(Formulario.objects.get(pk=resp.data["id"]).sincronizado_tarde)

    def test_el_caso_que_llega_tarde_se_marca_y_la_app_lo_ve(self):
        fin = self._cerrar(Relevamiento.Estado.FINALIZADO)

        resp = self.client.post(
            self.url,
            self._payload(capturado_en=(fin - timedelta(hours=1)).isoformat()),
            format="json",
        )

        self.assertTrue(resp.data["sincronizado_tarde"])

    def test_una_carga_dentro_del_periodo_no_se_marca(self):
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])

        resp = self.client.post(
            self.url,
            self._payload(capturado_en=timezone.now().isoformat()),
            format="json",
        )

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(resp.data["sincronizado_tarde"])

    def test_una_captura_posterior_al_periodo_se_rechaza(self):
        """Lo que la gracia **no** habilita: cargar a alguien después del
        cierre. El permiso es para subir lo ya capturado, no para seguir
        capturando."""
        fin = self._cerrar(Relevamiento.Estado.EN_REVISION)

        resp = self.client.post(
            self.url,
            self._payload(capturado_en=(fin + timedelta(minutes=30)).isoformat()),
            format="json",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["detail"], campo.FUERA_DE_PERIODO)
        self.assertEqual(self.rel.formularios.count(), 0)

    def test_pasada_la_gracia_el_alta_vuelve_a_rechazarse(self):
        fin = self._cerrar(Relevamiento.Estado.EN_REVISION, hace=timedelta(hours=25))

        resp = self.client.post(
            self.url,
            self._payload(capturado_en=(fin - timedelta(hours=1)).isoformat()),
            format="json",
        )

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data["detail"], campo.GRACIA_VENCIDA)
        self.assertEqual(self.rel.formularios.count(), 0)

    def test_un_relevamiento_terminado_no_acepta_nada(self):
        """TERMINADO es el único cerrado sin gracia: los reportes ya salieron y
        sumar un caso cambiaría números ya informados."""
        fin = self._cerrar(Relevamiento.Estado.TERMINADO)

        resp = self.client.post(
            self.url,
            self._payload(capturado_en=(fin - timedelta(hours=1)).isoformat()),
            format="json",
        )

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data["detail"], campo.NO_EN_CURSO)

    def test_un_relevamiento_asignado_tampoco(self):
        """La otra punta: todavía no arrancó. La gracia es por el final, no por
        el principio."""
        fin = self._cerrar(Relevamiento.Estado.ASIGNADO)

        resp = self.client.post(
            self.url,
            self._payload(capturado_en=(fin - timedelta(hours=1)).isoformat()),
            format="json",
        )

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data["detail"], campo.NO_EN_CURSO)

    def test_sin_capturado_en_la_regla_es_la_de_siempre(self):
        """La app vieja y la carga en línea no mandan `capturado_en`: ahí no hay
        nada que datar y el relevamiento tiene que estar en curso **ahora**."""
        self._cerrar(Relevamiento.Estado.EN_REVISION)
        cuerpo = self._payload()
        cuerpo.pop("capturado_en", None)

        resp = self.client.post(self.url, cuerpo, format="json")

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data["detail"], campo.NO_EN_CURSO)

    def test_un_relevamiento_pausado_no_habilita_la_gracia(self):
        """La pausa gana: `habilitado_en` la mira y el alta no entra ni con la
        fecha correcta. Es lo que la app ya sabe reintentar."""
        fin = self._cerrar(Relevamiento.Estado.EN_REVISION)
        Relevamiento.objects.filter(pk=self.rel.pk).update(pausado=True, pausa_motivo="Operativo suspendido")
        self.rel.refresh_from_db()

        resp = self.client.post(
            self.url,
            self._payload(capturado_en=(fin - timedelta(hours=1)).isoformat()),
            format="json",
        )

        self.assertEqual(resp.status_code, 409)
        self.assertTrue(resp.data["pausado"])


class CronDeVencimientosTests(TestCase):
    """BEC-22 + la traza de G1-04 sobre `procesar_vencimientos`."""

    def setUp(self):
        from datetime import date

        from programas.models import Convocatoria, Segmento

        self.seg = Segmento.objects.create(nombre="Seg", cupo_maximo=10)
        self.conv = Convocatoria.objects.create(
            nombre="Conv", segmento=self.seg, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )

    def _relevamiento(self, estado, **extra):
        rel = Relevamiento.objects.create(
            convocatoria=self.conv,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now() - timedelta(days=3),
            fecha_hasta=timezone.now() - timedelta(days=2),
            **extra,
        )
        Relevamiento.objects.filter(pk=rel.pk).update(estado=estado)
        rel.refresh_from_db()
        return rel

    def test_el_update_vuelve_a_filtrar_el_estado(self):
        """BEC-22: entre leer los ids y escribirlos, alguien puede haber cerrado
        el relevamiento desde la pantalla. El `UPDATE` por pk solo no lo mira y
        reabría un `TERMINADO` mandándolo a `EN_REVISION`."""
        rel = self._relevamiento(Relevamiento.Estado.EN_CURSO)
        qs = relevamientos_de_convocatoria_vencida()
        list(qs.values_list("pk", flat=True))  # la lectura del cron
        # Lo que pasa en el medio.
        Relevamiento.objects.filter(pk=rel.pk).update(estado=Relevamiento.Estado.TERMINADO)

        cerrados = pasar_relevamientos_a_revision(qs)

        rel.refresh_from_db()
        self.assertEqual(cerrados, 0)
        self.assertEqual(rel.estado, Relevamiento.Estado.TERMINADO)

    def test_devuelve_las_filas_afectadas_y_no_los_ids_leidos(self):
        self._relevamiento(Relevamiento.Estado.EN_CURSO)
        self._relevamiento(Relevamiento.Estado.ASIGNADO)

        self.assertEqual(pasar_relevamientos_a_revision(relevamientos_de_convocatoria_vencida()), 2)
        # Segunda corrida: ya no queda nada abierto.
        self.assertEqual(pasar_relevamientos_a_revision(relevamientos_de_convocatoria_vencida()), 0)

    def test_la_transicion_automatica_queda_en_el_log(self):
        """G1-04: el relevamiento no tiene traza propia (Cambio 54). Sin esta
        línea, un territorial encuentra su relevamiento cerrado y no hay registro
        de qué lo cerró — que es la mitad invisible de la sincronización tardía."""
        rel = self._relevamiento(Relevamiento.Estado.EN_CURSO)

        with self.assertLogs("programas.services.vencimientos", level="INFO") as registro:
            pasar_relevamientos_a_revision(relevamientos_de_convocatoria_vencida())

        self.assertIn(str(rel.pk), registro.output[0])
        self.assertIn("EN_REVISION", registro.output[0])

    def test_el_log_nombra_los_que_se_cerraron_y_no_los_que_se_leyeron(self):
        """La línea decía «N relevamiento(s) … (ids=…)» con N = filas afectadas
        (BEC-22) y la lista = ids **leídos**. Justo cuando las dos cosas
        difieren —que es el escenario que BEC-22 arregla— el rastro nombraba un
        relevamiento que nadie cerró.

        La carrera se reproduce pasándole la lista tal como quedó leída: es el
        estado exacto en el que la deja un coordinador que termina su
        relevamiento desde la pantalla entre el `SELECT` y el `UPDATE`.
        """
        cerrado = self._relevamiento(Relevamiento.Estado.EN_CURSO)
        escapado = self._relevamiento(Relevamiento.Estado.TERMINADO)

        with self.assertLogs("programas.services.vencimientos", level="INFO") as registro:
            afectadas = pasar_relevamientos_a_revision(Relevamiento.objects.filter(pk__in=[cerrado.pk, escapado.pk]))

        self.assertEqual(afectadas, 1)
        self.assertIn(f"ids=[{cerrado.pk}]", registro.output[0])
        self.assertIn("EN_REVISION", registro.output[0])
        self.assertIn(f"ids=[{escapado.pk}]", registro.output[1])
        self.assertIn("cambiaron de estado", registro.output[1])

    def test_un_finalizando_fuera_de_fecha_con_la_convocatoria_viva_no_se_cierra(self):
        """Caracterización que G1-04 **no** cambia (Cambio 120): la segunda rama
        de la regla solo alcanza `ASIGNADO` y `EN_CURSO`. La gracia es una
        ventana de la API, no una del cron."""
        rel = self._relevamiento(Relevamiento.Estado.FINALIZANDO)

        pasar_relevamientos_a_revision(relevamientos_de_convocatoria_vencida())

        rel.refresh_from_db()
        self.assertEqual(rel.estado, Relevamiento.Estado.FINALIZANDO)


class ValidacionDeLaCargaTests(_CampoBase):
    """G1-05 · el servidor deja de creerle todo a lo que sube el teléfono.

    El link público pasa cada respuesta por el motor de condiciones y por la
    validación de su campo; la API de campo no validaba nada. Un cliente con
    token —o una app vieja— creaba el caso igual, y las respuestas a ítems que
    el formulario escondía quedaban guardadas y **viajaban a SIIS**.
    """

    def setUp(self):
        super().setUp()
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])

    def _pregunta(self, texto, tipo=TipoCampo.STRING, **extra):
        return PreguntaGlobal.objects.create(texto=texto, tipo=tipo, activo=True, **extra)

    def _caso(self, **extra):
        resp = self.client.post(self.url, self._payload(**extra), format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        return Formulario.objects.get(pk=resp.data["id"])

    def test_una_obligatoria_sin_responder_no_frena_la_carga_pero_queda_anotada(self):
        self._pregunta("Tenencia de la vivienda", orden=1, obligatorio=True)

        formulario = self._caso()

        self.assertIn("Tenencia de la vivienda", formulario.observaciones_carga)
        self.assertIn("Falta la respuesta obligatoria", formulario.observaciones_carga)

    def test_la_respuesta_a_un_item_oculto_no_se_guarda(self):
        """RN-6 / D11: la condición no se cumple ⇒ el ítem no se pidió ⇒ lo que
        haya llegado no es una respuesta. Si se guarda igual,
        `respuestas_por_destino` lo manda a SIIS."""
        disparador = self._pregunta("¿Tenés hijos?", tipo=TipoCampo.SELECTOR, orden=1)
        disparador.opciones = ["Sí", "No"]
        disparador.save(update_fields=["opciones", "modificado"])
        condicionada = self._pregunta("¿Cuántos?", tipo=TipoCampo.INT, orden=2)
        self._condicionar(condicionada, fuente=f"pg-{disparador.pk}", op="es", valor="Sí")

        formulario = self._caso(
            data={"globales": {str(disparador.pk): "No", str(condicionada.pk): "3"}, "requisitos": {}}
        )

        self.assertNotIn(f"pg-{condicionada.pk}", formulario.respuestas)
        self.assertNotIn(str(condicionada.pk), formulario.data["globales"])
        self.assertIn("Se descartó la respuesta", formulario.observaciones_carga)

    def test_una_opcion_que_no_esta_en_el_formulario_queda_anotada(self):
        pregunta = self._pregunta("Nivel educativo", tipo=TipoCampo.SELECTOR, orden=1)
        pregunta.opciones = ["Primario", "Secundario"]
        pregunta.save(update_fields=["opciones", "modificado"])

        formulario = self._caso(data={"globales": {str(pregunta.pk): "Doctorado"}, "requisitos": {}})

        self.assertIn("Doctorado", formulario.observaciones_carga)
        self.assertIn("no está en el formulario", formulario.observaciones_carga)

    def test_un_numero_que_no_es_numero_queda_anotado(self):
        pregunta = self._pregunta("Personas en el hogar", tipo=TipoCampo.INT, orden=1)

        formulario = self._caso(data={"globales": {str(pregunta.pk): "muchas"}, "requisitos": {}})

        self.assertIn("esperaba un número", formulario.observaciones_carga)

    def test_sin_gps_cuando_el_segmento_lo_pide(self):
        """`requiere_gps` vivía en la definición y nadie lo exigía del lado del
        servidor: la app podía no mandarlo y el caso entraba igual."""
        formulario = self._caso(gps_lat=None, gps_lng=None)

        self.assertIn("ubicación GPS", formulario.observaciones_carga)

    def test_con_gps_y_todo_respondido_no_queda_ninguna_observacion(self):
        """El caso normal no paga nada: sin observaciones no se escribe la
        columna (es lo que sostiene el presupuesto de consultas del alta)."""
        formulario = self._caso()

        self.assertIsNone(formulario.observaciones_carga)

    def test_un_sexo_desconocido_queda_anotado(self):
        """`resolver_ciudadano_offline` lo descarta en silencio al crear el
        legajo: la persona quedaba sin sexo y nadie sabía por qué."""
        formulario = self._caso(
            datos_identificacion={
                "dni": "40400401",
                "nombre": "Ana",
                "apellido": "Gomez",
                "sexo": "Z",
                "fecha_nacimiento": "1990-01-02",
            }
        )

        self.assertIn("no es un valor conocido", formulario.observaciones_carga)
        self.assertEqual(Ciudadano.objects.get(dni="40400401").genero, "")

    def test_el_no_binario_se_observa_pero_se_guarda(self):
        """Desvío de la ficha, code-first. Pedía «sexo F/M» a secas, y los dos
        lados dicen cosas distintas: el **legajo** acepta tres valores
        (`Ciudadano.Genero`, con `X` = no binario) y el **formulario** ofrece
        dos (`VINCULOS_LEGAJO["genero"]`, opciones `["F", "M"]`). La carga se
        guarda con su X —no se pierde un dato que el sistema sabe representar— y
        queda la observación de que el formulario no ofrecía esa opción, que es
        lo que el revisor tiene que saber."""
        formulario = self._caso(
            datos_identificacion={
                "dni": "40400403",
                "nombre": "Alex",
                "apellido": "Gomez",
                "sexo": "X",
                "fecha_nacimiento": "1990-01-02",
            }
        )

        self.assertIn("no está en el formulario", formulario.observaciones_carga)
        self.assertEqual(Ciudadano.objects.get(dni="40400403").genero, "X")

    def test_los_adjuntos_obligatorios_no_se_reportan_como_faltantes(self):
        """Code-first: un campo `ARCHIVO` se responde con el `POST …/adjuntos/`
        que la app manda **después** del alta. Exigirlo acá marcaría «falta» en
        el 100 % de las cargas y haría inútil la columna. Lo que falte de verdad
        lo mira G1-07."""
        self._pregunta("Foto del recibo", tipo=TipoCampo.ARCHIVO, orden=1, obligatorio=True)

        formulario = self._caso()

        self.assertIsNone(formulario.observaciones_carga)

    def test_el_apoderado_de_un_adulto_no_se_reporta_como_faltante(self):
        """Cambio 67: el catálogo pide el apoderado a toda persona **en el
        link**; ahí mismo está escrito que «la app de campo mantiene, por ahora,
        la regla de menores». En el canal app la obligatoriedad la decide RN-22
        en el serializer, no el catálogo."""
        self.assertTrue(
            PreguntaGlobal.objects.filter(grupo__clave="apoderado", obligatorio=True).exists(),
            "el catálogo sembrado tiene que traer el apoderado obligatorio, si no el test no prueba nada",
        )

        formulario = self._caso()

        self.assertIsNone(formulario.observaciones_carga)

    def test_un_dni_imposible_se_rechaza(self):
        """Lo único que se rechaza: un caso con un DNI que no es un DNI no se
        puede cruzar con el padrón, ni consultar en SIIS, ni unir a un legajo.
        No hay forma de arreglarlo después."""
        resp = self.client.post(
            self.url,
            self._payload(datos_identificacion={"dni": "123", "nombre": "Juan", "apellido": "Perez"}),
            format="json",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.rel.formularios.count(), 0)
        # El motivo tiene que llegar donde la app lo lee (`becasApi.js`,
        # `buildResponseError`): con el dict anidado por campo el territorial
        # veía «Error HTTP 400» y no sabía qué corregir.
        self.assertIn("non_field_errors", resp.data)
        self.assertIn("dni", str(resp.data["datos_identificacion"]).lower())

    def _condicionar(self, pregunta, *, fuente, op, valor):
        """Cuelga una condición del ítem del diseño que corresponde a `pregunta`."""
        from programas.services.diseno import obtener_o_crear_diseno

        diseno, _ = obtener_o_crear_diseno(self.conv)
        item = diseno.items.get(clave=f"pg-{pregunta.pk}")
        item.condicion = {"modo": "todas", "reglas": [{"fuente": fuente, "op": op, "valor": valor}]}
        item.save(update_fields=["condicion", "modificado"])
        return item


class FechaDeNacimientoTests(_CampoBase):
    """G1-06 · una fecha ilegible dejaba el caso sin legajo y en bucle de 500.

    `parse_date` devuelve `None` para `15/03/2010` y traga el `ValueError` de
    `31/02/2000`, así que el texto crudo seguía viaje hasta el ORM. El caso se
    insertaba, `_completar_alta` explotaba **después** del commit —500— y la app
    reintenta ocho veces por ser 5xx; el caso quedaba sin legajo y RN-22 sin
    evaluar.
    """

    def setUp(self):
        super().setUp()
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])

    def test_una_fecha_imposible_se_rechaza_con_400(self):
        resp = self.client.post(
            self.url,
            self._payload(
                datos_identificacion={
                    "dni": "40400400",
                    "nombre": "Juan",
                    "apellido": "Perez",
                    "fecha_nacimiento": "31/02/2000",
                }
            ),
            format="json",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.rel.formularios.count(), 0)
        # Igual que el DNI: el motivo viaja también donde la app lo lee.
        self.assertIn("fecha", " ".join(resp.data["non_field_errors"]).lower())
        self.assertIn("fecha_nacimiento", str(resp.data["datos_identificacion"]))

    def test_una_fecha_en_formato_argentino_se_normaliza_y_entra(self):
        """El caso de la ficha: `15/03/2010` → 201 y el legajo con
        `2010-03-15`. Lleva apoderado porque con esa fecha ya evaluada la
        persona **es menor**, que es justamente lo que antes no se notaba."""
        resp = self.client.post(
            self.url,
            self._payload(
                datos_identificacion={
                    "dni": "40400400",
                    "nombre": "Juan",
                    "apellido": "Perez",
                    "fecha_nacimiento": "15/03/2010",
                },
                apoderado_nombre="Marta",
                apoderado_apellido="Perez",
                apoderado_dni="20200200",
                apoderado_genero="F",
                apoderado_fecha_nacimiento="1980-01-01",
            ),
            format="json",
        )

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(str(Ciudadano.objects.get(dni="40400400").fecha_nacimiento), "2010-03-15")

    def test_la_edad_se_evalua_con_la_fecha_normalizada(self):
        """La consecuencia de fondo: con la fecha ilegible, `es_menor` recibía
        `None` y RN-22 no exigía apoderado a un menor."""
        menor = (timezone.localdate() - timedelta(days=365 * 10)).strftime("%d/%m/%Y")

        resp = self.client.post(
            self.url,
            self._payload(
                datos_identificacion={
                    "dni": "40400402",
                    "nombre": "Nina",
                    "apellido": "Perez",
                    "fecha_nacimiento": menor,
                }
            ),
            format="json",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("apoderado_nombre", resp.data)


class ObservacionesEnLaRevisionTests(_CampoBase):
    """Las dos marcas llegan a la pantalla del revisor. Sin esto, G1-04 y G1-05
    guardan información que nadie ve."""

    def setUp(self):
        super().setUp()
        from django.contrib.auth.models import Group

        from programas.management.commands.seed_becas import ROL_COORDINADOR

        self.coord = self._crear_coordinador(Group.objects.get(name=ROL_COORDINADOR))

    def _crear_coordinador(self, rol):
        from django.contrib.auth.models import User

        from programas.models import AsignacionCoordinador

        coord = User.objects.create_user("coord-campo", password="secret123")
        coord.groups.add(rol)
        AsignacionCoordinador.objects.create(segmento=self.seg, coordinador=coord)
        return coord

    def test_el_detalle_muestra_el_badge_y_las_observaciones(self):
        formulario = Formulario.objects.create(
            relevamiento=self.rel,
            ciudadano=Ciudadano.objects.create(dni="40400400", nombre="Juan", apellido="Perez"),
            celular="1",
            email_contacto="a@b.com",
            sincronizado_tarde=True,
            observaciones_carga="El segmento pide ubicación GPS y la carga llegó sin coordenadas.",
        )
        self.client.credentials()
        self.client.force_login(self.coord)

        resp = self.client.get(reverse("becas:formulario_detalle", args=[formulario.pk]))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Sincronizado tarde")
        self.assertContains(resp, "Observaciones de la carga")
        self.assertContains(resp, "sin coordenadas")

    def test_un_caso_sin_marcas_no_muestra_nada(self):
        formulario = Formulario.objects.create(
            relevamiento=self.rel,
            ciudadano=Ciudadano.objects.create(dni="40400401", nombre="Ana", apellido="Gomez"),
            celular="1",
            email_contacto="a@b.com",
        )
        self.client.credentials()
        self.client.force_login(self.coord)

        resp = self.client.get(reverse("becas:formulario_detalle", args=[formulario.pk]))

        self.assertNotContains(resp, "Sincronizado tarde")
        self.assertNotContains(resp, "Observaciones de la carga")


class AdjuntosDeLaAppTests(_CampoBase):
    """G1-07 · el archivo de un campo ARCHIVO, que llega después del alta.

    Dos agujeros del mismo endpoint: no había idempotencia —el reintento de la
    cola offline creaba una fila más y la revisión se quedaba con la **más
    vieja**, así que la foto corregida no se veía nunca— y no había control de
    pertenencia: la referencia podía ser de un campo que el formulario de ese
    relevamiento no pide, y entonces el documento quedaba guardado donde la
    pantalla del revisor no lo busca.
    """

    @classmethod
    def setUpClass(cls):
        # Los adjuntos van a un `media/` descartable: el almacenamiento no se
        # revierte con la transacción del test (mismo patrón que RED-05, en
        # `test_adjunto_punta_a_punta`).
        cls._media = tempfile.mkdtemp(prefix="adjuntos-g107-")
        cls.addClassCleanup(shutil.rmtree, cls._media, ignore_errors=True)
        cls._media_override = override_settings(MEDIA_ROOT=cls._media)
        cls._media_override.enable()
        cls.addClassCleanup(cls._media_override.disable)
        super().setUpClass()

    def setUp(self):
        super().setUp()
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])
        self.pregunta = PreguntaGlobal.objects.create(
            texto="Foto del DNI", tipo=TipoCampo.ARCHIVO, activo=True, obligatorio=False, orden=900
        )
        # Está en el formulario, pero su respuesta es texto: sirve para separar
        # «no es un campo de este formulario» de «no es un campo de archivo».
        self.pregunta_texto = PreguntaGlobal.objects.create(
            texto="Tenencia", tipo=TipoCampo.STRING, activo=True, obligatorio=False, orden=902
        )
        self.formulario = self._caso()

    def _caso(self):
        resp = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        return Formulario.objects.get(pk=resp.data["id"])

    def _url_adjuntos(self, formulario=None):
        return reverse("becas_api:formulario-adjuntos", args=[(formulario or self.formulario).pk])

    def _subir(self, contenido=b"primera", nombre="dni.jpg", **referencia):
        referencia = referencia or {"pregunta_global": self.pregunta.pk}
        return self.client.post(
            self._url_adjuntos(),
            {**referencia, "archivo": SimpleUploadedFile(nombre, contenido)},
            format="multipart",
        )

    def test_un_reintento_de_la_app_no_duplica_el_adjunto(self):
        """El escenario de la ficha: la cola offline sube la foto, pierde la
        respuesta y reintenta. Antes quedaban dos filas del mismo campo."""
        primera = self._subir(b"una foto")

        segunda = self._subir(b"una foto")

        self.assertEqual(primera.status_code, 201, primera.data)
        self.assertEqual(segunda.status_code, 201, segunda.data)
        self.assertEqual(self.formulario.adjuntos.count(), 1)
        self.assertEqual(segunda.json()["id"], primera.json()["id"])

    def test_la_foto_que_vale_es_la_ultima_que_subio_el_territorial(self):
        """La primera salió movida y el territorial la vuelve a sacar: lo que el
        revisor abre tiene que ser la segunda."""
        self._subir(b"movida")

        self._subir(b"nitida")

        adjunto = self.formulario.adjuntos.get()
        with adjunto.archivo.open("rb") as guardado:
            self.assertEqual(guardado.read(), b"nitida")

    def test_el_archivo_viejo_no_queda_en_media(self):
        """El reemplazo borra el anterior del almacenamiento, y recién después
        de que la transacción confirma: si se cae, el que vale sigue estando."""
        self._subir(b"movida")
        archivo = self.formulario.adjuntos.get().archivo
        almacenamiento, anterior = archivo.storage, archivo.name
        self.assertTrue(almacenamiento.exists(anterior))

        with self.captureOnCommitCallbacks(execute=True):
            self._subir(b"nitida")

        self.assertFalse(almacenamiento.exists(anterior))
        self.assertTrue(almacenamiento.exists(self.formulario.adjuntos.get().archivo.name))

    def test_la_revision_resuelve_el_adjunto_mas_nuevo(self):
        """Producción ya tiene filas duplicadas de antes de esta ficha: el índice
        que lee la revisión se quedaba con la más vieja porque el `ordering` del
        modelo es `-creado` y el bucle pisaba."""
        from programas.services.respuestas import _adjuntos_por_clave

        vieja = AdjuntoFormulario.objects.create(
            formulario=self.formulario,
            pregunta_global=self.pregunta,
            archivo=SimpleUploadedFile("vieja.jpg", b"vieja"),
        )
        nueva = AdjuntoFormulario.objects.create(
            formulario=self.formulario,
            pregunta_global=self.pregunta,
            archivo=SimpleUploadedFile("nueva.jpg", b"nueva"),
        )

        indice = _adjuntos_por_clave(self.formulario)

        self.assertEqual(indice[f"pg-{self.pregunta.pk}"].pk, nueva.pk)
        self.assertNotEqual(nueva.pk, vieja.pk)

    def test_un_campo_que_el_formulario_no_pide_se_rechaza(self):
        """Una pregunta desactivada no está en la foto del caso: el adjunto se
        guardaba igual y después no lo encontraba nadie."""
        ajena = PreguntaGlobal.objects.create(
            texto="Foto que ya no se pide", tipo=TipoCampo.ARCHIVO, activo=False, orden=901
        )

        resp = self._subir(pregunta_global=ajena.pk)

        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(self.formulario.adjuntos.count(), 0)

    def test_un_requisito_de_otro_segmento_se_rechaza(self):
        from programas.models import RequisitoNativo, Segmento

        otro = Segmento.objects.create(nombre="Otro seg", cupo_maximo=10)
        requisito = RequisitoNativo.objects.create(
            texto="Certificado de otro programa", tipo=TipoCampo.ARCHIVO, segmento=otro, orden=1
        )

        resp = self._subir(requisito_nativo=requisito.pk)

        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(self.formulario.adjuntos.count(), 0)

    def test_un_campo_que_no_es_de_archivo_se_rechaza(self):
        """Está en la foto del caso, pero su respuesta es texto: un archivo
        colgado de ahí no se muestra en ningún lado."""
        resp = self._subir(pregunta_global=self.pregunta_texto.pk)

        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(self.formulario.adjuntos.count(), 0)

    def test_el_caso_de_otro_territorial_no_recibe_adjuntos(self):
        """`get_queryset` acota a los relevamientos propios: el caso del otro
        territorial no existe para esta sesión."""
        ajeno = Formulario.objects.create(
            relevamiento=self.rel_ajeno, celular="1", email_contacto="a@b.com", datos_identificacion={"dni": "40400401"}
        )

        resp = self.client.post(
            self._url_adjuntos(ajeno),
            {"pregunta_global": self.pregunta.pk, "archivo": SimpleUploadedFile("dni.jpg", b"x")},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 404)
        self.assertEqual(AdjuntoFormulario.objects.count(), 0)

    def test_el_rechazo_dice_el_motivo_donde_la_app_lo_lee(self):
        """`becasApi.js` arma el mensaje con `detail` / `non_field_errors`: un
        diccionario por campo le deja al territorial un «Error HTTP 400»."""
        resp = self._subir(b"0" * (5 * 1024 * 1024 + 1))

        self.assertEqual(resp.status_code, 400)
        self.assertIn("5 MB", " ".join(resp.json()["non_field_errors"]))
        # La clave de siempre no se va: quien lea por campo la sigue teniendo.
        self.assertIn("archivo", resp.json())

    def test_la_foto_de_una_captura_en_fecha_sube_con_el_relevamiento_cerrado(self):
        """D-G04 aplicada a los adjuntos: la cola offline sube primero el caso y
        después las fotos. Si el cierre las frenara, el caso quedaría sin sus
        documentos y el revisor lo rechazaría por faltantes."""
        capturado = timezone.now() - timedelta(hours=1)
        Formulario.objects.filter(pk=self.formulario.pk).update(capturado_en=capturado)
        self.formulario.refresh_from_db()
        self._cerrar(Relevamiento.Estado.EN_REVISION, hace=timedelta(minutes=30))

        resp = self._subir(b"una foto")

        self.assertEqual(resp.status_code, 201, resp.data)

    def test_con_el_relevamiento_pausado_no_se_sube_nada(self):
        self.conv.pausado = True
        self.conv.pausa_motivo = "Operativo suspendido"
        self.conv.save(update_fields=["pausado", "pausa_motivo"])

        resp = self._subir(b"una foto")

        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(self.formulario.adjuntos.count(), 0)


class VersionDelFormularioTests(_CampoBase):
    """G1-16 · con qué versión del diseño capturó el teléfono.

    La foto de la definición se guarda al **sincronizar**, no al capturar: entre
    una cosa y la otra puede haber días y una edición del formulario en el medio.
    El servidor acepta la versión como dato **opcional** —la app instalada no la
    manda y el alta funciona igual— y, cuando viene y no coincide, lo deja
    observado para el revisor.
    """

    def setUp(self):
        super().setUp()
        from programas.services.diseno import obtener_o_crear_diseno

        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])
        # Sin diseño guardado la definición se sirve con `version = 0` y no hay
        # dos versiones que comparar: el constructor es el que las numera.
        self.diseno, _ = obtener_o_crear_diseno(self.conv)

    def _alta(self, **extra):
        return self.client.post(self.url, self._payload(**extra), format="json")

    def _version_vigente(self):
        """La versión que la app bajó en el detalle del relevamiento. Se relee el
        relevamiento de la base: la instancia del test se armó antes del diseño."""
        from programas.services.becas import definicion_formulario

        return definicion_formulario(Relevamiento.objects.get(pk=self.rel.pk))["version"]

    def test_la_app_instalada_no_manda_la_version_y_entra_igual(self):
        """El contrato que no se puede romper: `Chaco-mobile@a66c2d3` no manda
        esta clave."""
        resp = self._alta()

        self.assertEqual(resp.status_code, 201, resp.data)
        formulario = Formulario.objects.get(pk=resp.data["id"])
        self.assertIsNone(formulario.version_capturada)
        self.assertNotIn("versión", formulario.observaciones_carga or "")

    def test_la_version_que_manda_la_app_se_guarda_y_vuelve_en_la_respuesta(self):
        vigente = self._version_vigente()

        resp = self._alta(version_capturada=vigente)

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.json()["version_capturada"], vigente)
        formulario = Formulario.objects.get(pk=resp.data["id"])
        self.assertEqual(formulario.version_capturada, vigente)
        self.assertEqual(formulario.definicion["version"], vigente)
        self.assertNotIn("versión", formulario.observaciones_carga or "")

    def test_capturar_con_una_version_anterior_queda_observado(self):
        """El caso de la ficha: el teléfono capturó con la v1, alguien editó el
        formulario y la sincronización guarda la foto de la v2."""
        vigente = self._version_vigente()
        self.assertGreater(vigente, 0, "El diseño tiene que estar numerado para que haya algo que comparar.")

        resp = self._alta(version_capturada=vigente - 1)

        self.assertEqual(resp.status_code, 201, resp.data)
        formulario = Formulario.objects.get(pk=resp.data["id"])
        self.assertIn("versión", formulario.observaciones_carga)
        self.assertIn(str(vigente), formulario.observaciones_carga)

    def test_la_version_no_rechaza_la_carga(self):
        """La captura ya existe: una versión distinta es una advertencia, nunca
        un motivo para tirar trabajo de campo."""
        resp = self._alta(version_capturada=99999)

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Formulario.objects.get(pk=resp.data["id"]).version_capturada, 99999)

    def test_una_version_que_no_es_una_version_se_rechaza(self):
        """La columna es `PositiveIntegerField`: un negativo reventaría contra la
        base y un texto, contra el ORM. El 400 sale antes."""
        self.assertEqual(self._alta(version_capturada=-1).status_code, 400)
        self.assertEqual(self._alta(version_capturada="hola").status_code, 400)
        self.assertEqual(self.rel.formularios.count(), 0)


class GrupoCondicionadoTests(TestCase):
    """El caso de borde del motor que la revisión de la carga tiene que respetar:
    un hijo de un grupo oculto está oculto, aunque su propia condición se cumpla."""

    def test_un_hijo_de_grupo_oculto_cuenta_como_oculto(self):
        from programas.services.respuestas import aplicar

        definicion = {
            "items": [
                {
                    "tipo": "grupo",
                    "clave": "g1",
                    "condicion": None,
                    "items": [{"tipo_item": "campo", "clave": "pg-1", "tipo": TipoCampo.SELECTOR, "opciones": ["a"]}],
                },
                {
                    "tipo": "grupo",
                    "clave": "g2",
                    "condicion": {"modo": "todas", "reglas": [{"fuente": "pg-1", "op": "es", "valor": "b"}]},
                    "items": [{"tipo_item": "campo", "clave": "pg-2", "tipo": TipoCampo.STRING}],
                },
            ]
        }

        _visibles, ocultos, _efectivas = aplicar(definicion, {"pg-1": "a", "pg-2": "x"})

        self.assertIn("pg-2", ocultos)


class ContratoDelCatalogoTests(TestCase):
    """Los dos modelos que RED-40 toca siguen aceptando lo que ya tienen
    guardado: agregar un validador no puede dejar inmodificable un catálogo."""

    def test_un_grupo_sin_condicion_se_valida_sin_ruido(self):
        grupo = GrupoRequisito(clave="g-x", nombre="Grupo", canal=CanalFormulario.AMBOS)
        grupo.full_clean(exclude=["clave"])

    def test_un_item_con_condicion_valida_se_valida(self):
        item = ItemDiseno(
            clave="pg-1",
            tipo=ItemDiseno.Tipo.CAMPO,
            condicion={"modo": "todas", "reglas": [{"fuente": "pg-2", "op": "es", "valor": "Sí"}]},
        )
        item.clean_fields(exclude=["diseno", "padre", "pregunta", "requisito"])
