"""Candados: dos requests simultáneos no se pisan.

Las dos carreras que cubre este módulo se reprodujeron a mano con dos pestañas:

- lanzar el proceso masivo dos veces deja dos corridas EN_CURSO, y los dos hilos
  aprueban e informan a SIIS los mismos casos;
- rechazar un caso (o descartar una carga duplicada) mientras otro request lo
  aprueba pisa la aprobación, le libera el cupo y le manda el correo de «no fue
  aprobado».

La carrera se simula, no se corre: la suite usa SQLite en memoria, donde
``select_for_update()`` es un no-op y dos hilos de verdad no probarían nada. Lo
que se comprueba es lo que sí depende del código: que la decisión se tome con lo
que hay adentro del candado y no con lo que se leyó antes.

De ahí sale también ``ContratoDeCandadosTests`` (RED-67): como en SQLite el
candado no hace nada, borrar la línea del ``select_for_update()`` al optimizar
no rompe ni un test, y en MariaDB se pierde la serialización. Ese contrato no se
puede probar por su efecto, así que se prueba por su presencia, con
``core.tests.candados.candados_tomados``.
"""

import threading
import time
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.db import connections, transaction
from django.test import TransactionTestCase, tag
from django.urls import reverse
from django.utils import timezone

from core.tests.candados import candados_tomados
from core.tests.test_motor_real import MotorRealMixin
from programas.models import (
    CorridaSiis,
    Formulario,
    ListaEspera,
    ProgramaSiis,
    Relevamiento,
    Segmento,
    TracaFormulario,
)
from programas.services import proceso_masivo
from programas.services.cupo import (
    agregar_a_lista_espera,
    aprobar_o_poner_en_espera,
    dar_baja_beneficiario,
    promover_lista_espera,
)
from programas.tests.test_becas_api import _BaseApiTest
from programas.tests.test_becas_revision import _BaseAprobacionTest
from programas.tests.test_cupo_espera_reglas import _BaseEsperaTest
from programas.tests.test_proceso_masivo import _BaseProcesoTest

# A propósito escrito acá y no importado de la vista: lo que se comprueba es el
# texto que ve la persona, no que dos módulos compartan una constante.
MENSAJE_EN_CURSO = "Ya hay una corrida en curso. Esperá a que termine o frenala."


class CandadoCorridaMasivaTests(_BaseProcesoTest):
    """Entre ``en_curso()`` y el ``create()`` no puede entrar nadie."""

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser("admin_candado", password="x")
        self.client.force_login(self.admin)

    def _url(self, nombre="proceso_masivo_lanzar"):
        return reverse(f"becas:{nombre}", args=[self.programa.pk])

    def test_una_corrida_que_entro_mientras_esperabamos_el_candado_frena_la_nuestra(self):
        """La pantalla vio el camino libre; con el candado tomado, ya no lo está."""
        rastro = {"consultas": 0, "rival": None}

        def en_curso_falsa():
            rastro["consultas"] += 1
            if rastro["consultas"] == 1:
                # Chequeo de la vista, antes del candado: no hay nada corriendo.
                return None
            # Re-chequeo del servicio, ya con el candado: el otro request
            # commiteó su corrida mientras esperábamos.
            if rastro["rival"] is None:
                rastro["rival"] = CorridaSiis.objects.create(
                    programa=self.programa, total_pedido=7, latido=timezone.now()
                )
            return rastro["rival"]

        with (
            patch.object(CorridaSiis, "en_curso", side_effect=en_curso_falsa),
            patch("programas.views.proceso_masivo.servicio.lanzar") as lanzar,
        ):
            resp = self.client.post(self._url(), {"total_pedido": "25"})

        self.assertEqual(resp.status_code, 302)
        lanzar.assert_not_called()
        # Solo sobrevive la del rival: la nuestra no llegó a escribirse.
        self.assertEqual([c.total_pedido for c in CorridaSiis.objects.all()], [7])
        self.assertIn(MENSAJE_EN_CURSO, [str(m) for m in get_messages(resp.wsgi_request)])

    def test_con_el_camino_libre_la_corrida_se_crea_igual(self):
        with patch("programas.views.proceso_masivo.servicio.lanzar") as lanzar:
            self.client.post(self._url(), {"total_pedido": "25"})

        corrida = CorridaSiis.objects.get()
        self.assertEqual(corrida.total_pedido, 25)
        self.assertEqual(corrida.solicitada_por, self.admin)
        self.assertEqual(corrida.estado, CorridaSiis.Estado.EN_CURSO)
        lanzar.assert_called_once()

    def test_el_servicio_no_crea_nada_si_ya_hay_una_viva(self):
        CorridaSiis.objects.create(programa=self.programa, total_pedido=3, latido=timezone.now())

        creada = proceso_masivo.crear_corrida(programa=self.programa, solicitada_por=self.user, total_pedido=5)

        self.assertIsNone(creada)
        self.assertEqual(CorridaSiis.objects.count(), 1)

    def test_una_interrumpida_no_bloquea_al_servicio(self):
        """El candado no cambia la regla del latido: un pod muerto no traba nada."""
        CorridaSiis.objects.create(
            programa=self.programa,
            total_pedido=3,
            latido=timezone.now() - CorridaSiis.LATIDO_VENCIDO * 2,
        )

        creada = proceso_masivo.crear_corrida(programa=self.programa, solicitada_por=self.user, total_pedido=5)

        self.assertIsNotNone(creada)
        self.assertEqual(CorridaSiis.objects.count(), 2)


@tag("mysql")
class CarreraDeCorridaMasivaTests(MotorRealMixin, TransactionTestCase):
    """SIIS-03 · capa 2: el candado de la corrida, con el motor de verdad.

    Las clases de arriba simulan la carrera porque en SQLite
    ``select_for_update()`` es un no-op: lo que afirman es que la decisión se toma
    con lo que hay adentro del candado. Acá se corre de verdad, con dos hilos y
    dos conexiones, que es lo único que puede mostrar que el candado serializa.

    Las dos carreras que importan son distintas:

    * dos lanzamientos a la vez (dos pestañas) → **una** corrida;
    * un comando a mano justo cuando alguien lanza desde la pantalla → el comando
      espera el candado y después ve la corrida commiteada, en vez de colarse
      entre el ``en_curso()`` y el ``create()`` y procesar los mismos casos.
    """

    def setUp(self):
        super().setUp()
        self.programa = ProgramaSiis.objects.create(nombre="Programa corrida", siis_programa_id=943)
        self.user = User.objects.create_superuser("admin-corrida", "c@d.com", "x")

    def _en_paralelo(self, *operaciones):
        barrera = threading.Barrier(len(operaciones), timeout=30)
        resultados, errores = [], []

        def correr(operacion):
            try:
                barrera.wait()
                resultados.append(operacion())
            except Exception as exc:
                # A ``errores``, no a ``resultados``: una excepción guardada entre
                # los resultados deja el test en verde mientras el hilo se murió.
                errores.append(exc)
            finally:
                connections.close_all()

        hilos = [threading.Thread(target=correr, args=(operacion,)) for operacion in operaciones]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=60)
        self.assertEqual([repr(e) for e in errores], [])
        return resultados

    def _crear(self):
        return proceso_masivo.crear_corrida(programa=self.programa, solicitada_por=self.user, total_pedido=5)

    def test_dos_lanzamientos_simultaneos_crean_una_sola_corrida(self):
        resultados = self._en_paralelo(self._crear, self._crear)

        creadas = [r for r in resultados if isinstance(r, CorridaSiis)]
        self.assertEqual(len(creadas), 1, f"se crearon {len(creadas)} corridas: el candado no serializó")
        self.assertEqual(CorridaSiis.objects.filter(estado=CorridaSiis.Estado.EN_CURSO).count(), 1)

    def test_un_comando_no_se_cuela_entre_el_candado_y_la_corrida(self):
        """El comando espera el candado; no lee la tabla antes del commit del otro.

        Sin el candado, con READ COMMITTED el comando no ve la corrida que la
        pantalla todavía no commiteó, arranca igual y los dos procesan los mismos
        casos. Acá el lanzamiento retiene el candado un segundo y el comando
        **tiene** que tardar eso y después encontrarla.
        """
        creada, veredicto = threading.Event(), {}

        def lanzar_despacio():
            with transaction.atomic():
                proceso_masivo._tomar_candado()
                CorridaSiis.objects.create(
                    programa=self.programa, solicitada_por=self.user, total_pedido=5, latido=timezone.now()
                )
                creada.set()
                time.sleep(1)

        def comando():
            creada.wait(timeout=10)
            arranque = time.monotonic()
            try:
                proceso_masivo.exigir_sin_corrida_viva()
                veredicto["resultado"] = "arrancó"
            except proceso_masivo.CorridaEnCurso:
                veredicto["resultado"] = "abortó"
            veredicto["espera"] = time.monotonic() - arranque

        self._en_paralelo(lanzar_despacio, comando)

        self.assertEqual(veredicto["resultado"], "abortó")
        self.assertGreater(veredicto["espera"], 0.5, "el comando no esperó el candado: leyó antes del commit")
        self.assertEqual(CorridaSiis.objects.count(), 1)


class ContratoDeCandadosTests(_BaseEsperaTest):
    """RED-67 · capa 1: los tres caminos que tocan el cupo bloquean el segmento.

    Lo que protege el candado es el cupo máximo: sin él, en MariaDB dos
    aprobaciones simultáneas leen el mismo ``cupo_disponible`` y aprueban las
    dos —cupo excedido y **dos altas en SIIS, que no tiene baja**—, y dos altas
    a la lista leen el mismo ``Max("posicion")`` y se reparten la misma posición.

    Es un contrato de forma, no de efecto: afirma que el candado se pide, y que
    lo pide la función que tiene que pedirlo. La carrera de verdad —dos hilos
    sobre un segmento con un lugar— es la capa 2, un ``TransactionTestCase`` con
    ``@tag("mysql")`` que entra con el motor real del CI (TST-01, PR R-11).
    """

    def test_aprobar_toma_el_candado_del_segmento(self):
        self.entrada.delete()

        with candados_tomados(Segmento.objects) as candados:
            self.assertEqual(aprobar_o_poner_en_espera(self.form_a, self.coord_a), "aprobado")

        self.assertIn("cupo.py:aprobar_o_poner_en_espera", candados)

    def test_mandar_a_la_lista_de_espera_toma_el_candado_del_segmento(self):
        """Sin cupo, aprobar deriva a la lista: las dos ramas quedan cubiertas."""
        self.entrada.delete()
        self.seg_a.cupo_maximo = 0
        self.seg_a.save(update_fields=["cupo_maximo"])

        with candados_tomados(Segmento.objects) as candados:
            self.assertEqual(aprobar_o_poner_en_espera(self.form_a, self.coord_a), "lista_espera")

        self.assertEqual(candados, ["cupo.py:aprobar_o_poner_en_espera", "cupo.py:agregar_a_lista_espera"])

    def test_promover_toma_el_candado_del_segmento(self):
        with candados_tomados(Segmento.objects) as candados:
            promover_lista_espera(self._entrada_fresca(), self.admin)

        self.assertIn("cupo.py:promover_lista_espera", candados)
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)

    def test_agregar_a_la_lista_toma_el_candado_del_segmento(self):
        self.entrada.delete()

        with candados_tomados(Segmento.objects) as candados:
            agregar_a_lista_espera(self.form_a, self.seg_a, self.admin)

        self.assertIn("cupo.py:agregar_a_lista_espera", candados)
        self.assertEqual(self.form_a.lista_espera.get().posicion, 1)


class ContratoDeCandadosApiTests(_BaseApiTest):
    """RED-67 · capa 1: el alta de la app de campo bloquea el relevamiento.

    Sin el lock, dos dispositivos que sincronizan a la vez pasan el cupo del
    relevamiento y el chequeo de duplicado por DNI.
    """

    def setUp(self):
        super().setUp()
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])
        self.autenticar(self.terri)

    def test_el_alta_de_campo_toma_el_candado_del_relevamiento(self):
        with candados_tomados(Relevamiento.objects) as candados:
            resp = self.client.post(
                reverse("becas_api:relevamiento-formularios", args=[self.rel.id]),
                {
                    "client_uuid": "44444444-4444-4444-8444-444444444444",
                    "celular": "3624111222",
                    "email_contacto": "x@y.com",
                    "datos_identificacion": {"dni": "40444444", "nombre": "Cuatro", "apellido": "Candado"},
                },
                format="json",
            )

        self.assertEqual(resp.status_code, 201)
        # El de la vista, antes de decidir estado, cupo y duplicado. El otro
        # —``__init__.py:save``— lo toma ``Formulario.save()`` para numerar el
        # caso: por eso acá se mira quién pidió el candado y no solo que
        # alguien lo haya pedido.
        self.assertIn("views.py:formularios", candados)


class CandadoDelCasoAlAprobarTests(_BaseEsperaTest):
    """BEC-01 · aprobar, promover y dar de baja deciden con el caso bajo candado.

    Rechazar ya tomaba el candado de la fila del caso (``revision.py``) y relee
    su estado adentro; aprobar no, así que las dos operaciones no se serializaban
    entre sí: la aprobación leía ENVIADO, se iba a contar el cupo y escribía
    APROBADO encima de un rechazo que había commiteado mientras tanto —cupo
    consumido, correo de «no fue aprobado» ya mandado y, con cupo libre, un alta
    en SIIS que no tiene baja—.

    El candado nuevo serializa la carrera en MariaDB; la escritura condicional
    —``filter(estado=ENVIADO).update(...)``— es lo que hace que la decisión se
    pueda afirmar también acá, donde ``select_for_update()`` es un no-op.

    Qué se afirma en cada capa: acá, que la operación **lanza en vez de pisar**.
    Que el rechazo del otro sobreviva no se puede ver desde este lado: el
    servicio es atómico y, al lanzar, su transacción se deshace llevándose lo que
    el rival escribió adentro de la ventana. Eso lo prueba la carrera de verdad,
    con dos conexiones (``core.tests.test_motor_real.CarreraDelMismoCasoTests``).
    """

    def setUp(self):
        super().setUp()
        self.entrada.delete()

    def _rechazo_al_contar_el_cupo(self, segmento):
        """``get_cupo_stats`` falso: el otro request resuelve el caso en la ventana."""
        Formulario.objects.filter(pk=self.form_a.pk).update(estado=Formulario.Estado.RECHAZADO)
        return {"cupo_maximo": 10, "cupo_ocupado": 0, "cupo_disponible": 10}

    def _sin_traza_de_estado(self):
        self.assertFalse(
            TracaFormulario.objects.filter(formulario=self.form_a, campo="estado").exists(),
            "se registró un cambio de estado: la operación escribió igual",
        )

    def test_un_rechazo_que_entro_mientras_contabamos_el_cupo_no_se_pisa(self):
        """La ventana real: entre releer el estado y escribir la aprobación."""
        with patch("programas.services.cupo.get_cupo_stats", side_effect=self._rechazo_al_contar_el_cupo):
            with self.assertRaisesMessage(ValidationError, "ya fue resuelto"):
                aprobar_o_poner_en_espera(self.form_a, self.coord_a)

        self.form_a.refresh_from_db()
        self.assertNotEqual(self.form_a.estado, Formulario.Estado.APROBADO)
        self._sin_traza_de_estado()

    def test_aprobar_toma_el_candado_de_la_fila_del_caso(self):
        with candados_tomados(Formulario.objects) as candados:
            self.assertEqual(aprobar_o_poner_en_espera(self.form_a, self.coord_a), "aprobado")

        self.assertIn("cupo.py:aprobar_o_poner_en_espera", candados)

    def test_sin_carrera_la_aprobacion_sigue_funcionando(self):
        self.assertEqual(aprobar_o_poner_en_espera(self.form_a, self.coord_a), "aprobado")

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)
        self.assertEqual(self.form_a.motivo_rechazo, "")
        self.assertTrue(TracaFormulario.objects.filter(formulario=self.form_a, campo="estado").exists())

    def test_promover_no_pisa_un_rechazo_que_entro_mientras_contabamos_el_cupo(self):
        entrada = ListaEspera.objects.create(formulario=self.form_a, segmento=self.seg_a, posicion=1)

        with patch("programas.services.cupo.get_cupo_stats", side_effect=self._rechazo_al_contar_el_cupo):
            with self.assertRaisesMessage(ValidationError, "ya fue resuelto"):
                promover_lista_espera(self._entrada_fresca(entrada), self.admin)

        self.form_a.refresh_from_db()
        self.assertNotEqual(self.form_a.estado, Formulario.Estado.APROBADO)
        self._sin_traza_de_estado()

    def test_promover_toma_el_candado_de_la_fila_del_caso(self):
        entrada = ListaEspera.objects.create(formulario=self.form_a, segmento=self.seg_a, posicion=1)

        with candados_tomados(Formulario.objects) as candados:
            promover_lista_espera(self._entrada_fresca(entrada), self.admin)

        self.assertIn("cupo.py:promover_lista_espera", candados)
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)

    def test_dar_de_baja_no_pisa_una_baja_que_ya_entro(self):
        """Dos clics en «Dar de baja»: la segunda tiene que avisar, no repetir."""
        Formulario.objects.filter(pk=self.form_a.pk).update(estado=Formulario.Estado.APROBADO)
        self.form_a.refresh_from_db()
        viejo = Formulario.objects.get(pk=self.form_a.pk)
        dar_baja_beneficiario(self.form_a, self.admin)

        with self.assertRaises(ValidationError):
            dar_baja_beneficiario(viejo, self.admin)

        self.assertEqual(
            TracaFormulario.objects.filter(formulario=self.form_a, campo="estado").count(),
            1,
            "la segunda baja dejó una traza: se escribió dos veces",
        )

    def test_dar_de_baja_toma_el_candado_de_la_fila_del_caso(self):
        Formulario.objects.filter(pk=self.form_a.pk).update(estado=Formulario.Estado.APROBADO)
        self.form_a.refresh_from_db()

        with candados_tomados(Formulario.objects) as candados:
            dar_baja_beneficiario(self.form_a, self.admin)

        self.assertIn("cupo.py:dar_baja_beneficiario", candados)
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.BAJA)


class CandadoListaEsperaTests(_BaseEsperaTest):
    """BEC-02 · el alta a la lista de espera chequeaba antes de tomar el candado.

    Doble clic en «Agregar a lista de espera» y el caso entra dos veces: dos
    filas activas, dos posiciones consecutivas para la misma persona y dos
    correos. El chequeo de «ya está en la lista» miraba la base antes del
    ``select_for_update`` del segmento, así que las dos pasaban.

    Como en ``CandadoDelCasoAlAprobarTests``, acá se afirma la decisión —lanzar
    en vez de crear la segunda fila—: el ``raise`` deshace la transacción del
    servicio y con ella lo que el rival escribió adentro, así que el conteo final
    no distingue nada. Las dos filas de verdad las cuenta
    ``core.tests.test_motor_real.CarreraDelMismoCasoTests``.
    """

    def setUp(self):
        super().setUp()
        self.entrada.delete()

    def _con_un_rival_al_dar_el_candado(self, rival):
        """``Segmento`` falso cuyo ``select_for_update().get()`` deja entrar al otro.

        Es la forma de meterse en la ventana sin dos hilos: en SQLite el candado
        no serializa nada, así que lo que se afirma es *cuándo* se lee, no que el
        motor espere.
        """
        falso = MagicMock()
        falso.objects.select_for_update.return_value.get.side_effect = lambda pk: rival() or self.seg_a
        return patch("programas.services.cupo.Segmento", falso)

    def test_un_alta_que_entro_mientras_esperabamos_el_candado_frena_la_nuestra(self):
        """El rival commitea su fila justo cuando nos dan el candado."""

        def otro_lo_agrega():
            ListaEspera.objects.create(formulario=self.form_a, segmento=self.seg_a, posicion=1)

        with self._con_un_rival_al_dar_el_candado(otro_lo_agrega):
            with self.assertRaisesMessage(ValidationError, "ya está en la lista de espera"):
                agregar_a_lista_espera(self.form_a, self.seg_a, self.admin)

    def test_un_caso_que_cambio_de_estado_bajo_el_candado_no_entra_a_la_lista(self):
        def otro_lo_aprueba():
            Formulario.objects.filter(pk=self.form_a.pk).update(estado=Formulario.Estado.APROBADO)

        with self._con_un_rival_al_dar_el_candado(otro_lo_aprueba):
            with self.assertRaises(ValidationError):
                agregar_a_lista_espera(self.form_a, self.seg_a, self.admin)

        self.assertFalse(ListaEspera.objects.filter(formulario=self.form_a).exists())

    def test_sin_carrera_el_alta_a_la_lista_sigue_funcionando(self):
        agregar_a_lista_espera(self.form_a, self.seg_a, self.admin)

        entrada = ListaEspera.objects.get(formulario=self.form_a, promovido=False)
        self.assertEqual(entrada.posicion, 1)


class CandadoRechazoTests(_BaseAprobacionTest):
    """Rechazar decide con el estado que hay bajo el candado."""

    def _rechazar(self, motivo="No cumple los requisitos"):
        return self.client.post(reverse("becas:formulario_rechazar", args=[self.form_a.pk]), {"motivo": motivo})

    @patch("programas.views.revision.enviar_aviso_resolucion")
    def test_no_pisa_una_aprobacion_que_entro_mientras_consultabamos_siis(self, aviso):
        """La consulta a SIIS es la ventana larga del request: ahí entra el otro."""

        def validar_y_que_otro_apruebe(formulario, usuario):
            Formulario.objects.filter(pk=formulario.pk).update(estado=Formulario.Estado.APROBADO)
            return self.validacion

        with patch("programas.views.revision.validar_formulario_en_siis", side_effect=validar_y_que_otro_apruebe):
            resp = self._rechazar()

        self.assertEqual(resp.status_code, 302)
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)
        self.assertEqual(self.form_a.motivo_rechazo, "")
        self.assertFalse(TracaFormulario.objects.filter(formulario=self.form_a, campo="estado").exists())
        aviso.assert_not_called()

    @patch("programas.views.revision.enviar_aviso_resolucion")
    def test_sin_carrera_el_rechazo_sigue_funcionando(self, aviso):
        resp = self._rechazar(motivo="Documentación incompleta")

        self.assertEqual(resp.status_code, 302)
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.RECHAZADO)
        self.assertEqual(self.form_a.motivo_rechazo, "Documentación incompleta")
        aviso.assert_called_once()


class CandadoDuplicadoTests(_BaseAprobacionTest):
    """Resolver un duplicado tampoco decide con datos de hace un rato."""

    def setUp(self):
        super().setUp()
        self.previo = Formulario.objects.create(relevamiento=self.rel_a, celular="3624300300")
        Formulario.objects.filter(pk=self.form_a.pk).update(conflicto_duplicado=True, duplicado_de=self.previo)
        self.form_a.refresh_from_db()

    def _resolver(self, decision="conservar_previo", pk=None):
        return self.client.post(
            reverse("becas:formulario_resolver_duplicado", args=[pk or self.form_a.pk]), {"decision": decision}
        )

    def test_conservar_previo_no_descarta_una_carga_que_ya_aprobaron(self):
        Formulario.objects.filter(pk=self.form_a.pk).update(estado=Formulario.Estado.APROBADO)

        self._resolver()

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)
        self.assertFalse(self.form_a.conflicto_resuelto)
        self.assertEqual(self.form_a.motivo_rechazo, "")

    def test_el_conflicto_resuelto_se_relee_bajo_el_candado(self):
        """Otra pestaña resolvió el conflicto entre la lectura y el candado."""

        def resuelve_el_otro(request, formulario):
            Formulario.objects.filter(pk=formulario.pk).update(conflicto_resuelto=True)

        with patch("programas.views.revision._assert_scope_formulario", side_effect=resuelve_el_otro):
            self._resolver()

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.ENVIADO)

    def test_conservar_actual_no_reemplaza_una_carga_anterior_ya_resuelta(self):
        Formulario.objects.filter(pk=self.previo.pk).update(estado=Formulario.Estado.APROBADO)

        self._resolver(decision="conservar_actual")

        self.previo.refresh_from_db()
        self.form_a.refresh_from_db()
        self.assertEqual(self.previo.estado, Formulario.Estado.APROBADO)
        self.assertFalse(self.form_a.conflicto_resuelto)

    def test_sin_carrera_el_duplicado_se_resuelve_igual(self):
        self._resolver()

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.RECHAZADO)
        self.assertTrue(self.form_a.conflicto_resuelto)
