"""Módulo Emergencia, PR 8: la API M2 (llegada de familias) y su contrato.

La guardia del dispositivo hace desde la app **lo mismo** que la pantalla E6 del backoffice
(RU-1), llamando a las mismas funciones de ``services.emergencia_alojar`` (RU-2). Lo que fija
este archivo:

* **Claves exactas** de cada respuesta: las constantes ``CLAVES_*`` viven en
  ``test_emergencia_api_contrato`` (el contrato de toda la app) y se importan.
* **409 cuando la web y la API compiten** sobre el mismo caso: la guardia acepta (o confirma)
  desde el backoffice y después la app hace lo mismo → ``{detail, estado_actual}``.
* **RU-16**: el mismo ``uuid_cliente`` dos veces en confirmar, agregar, ingreso directo y aviso a
  la mesa escribe **una** vez.
* **Alcance (C2, RU-9)**: la guardia de la Escuela no abre nada del Centro aunque conozca los
  ids: **404** con el cuerpo de un id inexistente, sin nombrar al Centro. **Mutación vista en
  rojo**: el detalle está en el docstring de ``test_la_guardia_de_otro_dispositivo_recibe_404_en_todo``.
* **403 ``SIN_MODULO``** para un rol de Becas y para quien abre el módulo sin admitir familias;
  **401** sin token.
* **Presupuestos** (``@tag("performance")``) de ``mis-dispositivos``, ``buscar``, ``integrantes`` y
  ``plazas`` con un dispositivo de 300 camas: no crecen con las filas.
"""

import uuid
from unittest import mock

from django.contrib.auth.models import User
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from programas.api.views_emergencia import MENSAJE_SIN_ADMITIR
from programas.models import (
    CasoEmergencia,
    Derivacion,
    Estadia,
    IntegranteGrupo,
    Plaza,
    ReservaPlaza,
    Sector,
    TrazaCaso,
)
from programas.selectors import emergencia_alojar as selectores
from programas.services import emergencia as mesa
from programas.services import emergencia_alojar as servicio
from programas.services import emergencia_alta
from programas.tests.test_emergencia_alojar import GUARDIA, ficha_minima
from programas.tests.test_emergencia_api_contrato import (
    ADMITIR,
    CLAVES_ACEPTACION,
    CLAVES_AVISO_A_LA_MESA,
    CLAVES_BUSQUEDA,
    CLAVES_CASO_RESUMEN,
    CLAVES_CIERRE_DE_INGRESO,
    CLAVES_CONFIRMACION,
    CLAVES_DERIVACION_LLEGADA,
    CLAVES_ESTADO_CAMBIO,
    CLAVES_FICHA_COMPLETADA,
    CLAVES_FIJAS_DEL_400,
    CLAVES_GRUPO_DE_LA_DERIVACION,
    CLAVES_INGRESO_DIRECTO,
    CLAVES_INTEGRANTE,
    CLAVES_INTEGRANTE_AGREGADO,
    CLAVES_INTEGRANTE_DETALLE,
    CLAVES_INTEGRANTES,
    CLAVES_MAPA,
    CLAVES_MI_DISPOSITIVO,
    CLAVES_PERSONA_DEL_INTEGRANTE,
    CLAVES_PLAZA_DEL_INTEGRANTE,
    CLAVES_PLAZA_DEL_MAPA,
    CLAVES_RECHAZO,
    CLAVES_RESPONSABLE,
    CLAVES_SECTOR_CON_PLAZAS,
    CLAVES_SECTOR_DEL_MAPA,
    CLAVES_SIN_MODULO,
    RECIBIR_KIT,
    SIN_MODULO,
    URL_MIS_DISPOSITIVOS,
    BaseApiEmergencia,
)

Estado = CasoEmergencia.Estado

SIN_ADMITIR = {"detail": MENSAJE_SIN_ADMITIR, "code": "SIN_MODULO"}
NO_ENCONTRADO = {"detail": "No encontrado."}


def _url(nombre, *args):
    return reverse(f"emergencia_api:{nombre}", args=args)


class BaseApiLlegadas(BaseApiEmergencia):
    """Lo de ``BaseApiEmergencia`` más dos dispositivos con su guardia y una familia de 7 por derivar."""

    def setUp(self):
        super().setUp()
        self.centro = self._dispositivo("Centro Norte", camas=9, localidad="Resistencia")
        self.escuela = self._dispositivo("Escuela 12", camas=5)
        self.guardia_centro = self._guardia("guardia_centro", list(GUARDIA), [self.centro])
        self.guardia_escuela = self._guardia("guardia_escuela", list(GUARDIA), [self.escuela])

    def _derivado(self, dispositivo=None, plazas=None, **datos):
        """Un caso de 7 personas tomado y derivado. Devuelve ``(caso, derivacion)``."""
        datos = {"menores_f": 2, "menores_m": 3, "dni": "30111222", "nombre": "Rosa", "apellido": "Benítez", **datos}
        caso = self._caso_tomado(**datos)
        derivacion = mesa.derivar_caso(
            caso, self.operador, dispositivo or self.centro, plazas or caso.grupo.total_declarado, True
        )
        return CasoEmergencia.objects.get(pk=caso.pk), derivacion

    def _aceptado(self, **kwargs):
        caso, derivacion = self._derivado(**kwargs)
        guardia = self.guardia_escuela if kwargs.get("dispositivo") == self.escuela else self.guardia_centro
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=guardia)
        return CasoEmergencia.objects.get(pk=caso.pk), Derivacion.objects.get(pk=derivacion.pk)

    def _reservas(self, derivacion):
        return list(
            ReservaPlaza.objects.filter(derivacion=derivacion, estado=ReservaPlaza.Estado.VIGENTE).order_by("plaza_id")
        )

    def _confirmar(self, caso, n, dni, plaza=None, uuid_cliente=None, usuario=None, **cambios):
        """La confirmación de la persona ``n`` por la API."""
        if plaza is None:
            plaza = self._reservas(Derivacion.objects.get(clave_vigente=caso.pk))[0].plaza
        cuerpo = {
            "uuid_cliente": str(uuid_cliente or uuid.uuid4()),
            "plaza_id": getattr(plaza, "pk", plaza),
            "ficha": ficha_minima(dni, **cambios),
        }
        return self._como(usuario or self.guardia_centro).post(
            _url("caso-integrante-confirmar", caso.pk, n), cuerpo, format="json"
        )

    def _confirmar_con_el_servicio(self, caso, n, dni):
        plaza = self._reservas(Derivacion.objects.get(clave_vigente=caso.pk))[0].plaza
        return servicio.confirmar_integrante(
            caso=caso, orden=n, usuario=self.guardia_centro, ficha=ficha_minima(dni), plaza=plaza
        )

    def _foto_del_caso(self, caso):
        """Todo lo que una acción podría escribir sobre el caso: para afirmar que no se escribió nada."""
        return (
            CasoEmergencia.objects.filter(pk=caso.pk).values().get(),
            list(Derivacion.objects.filter(caso=caso).order_by("id").values()),
            list(IntegranteGrupo.objects.filter(grupo_id=caso.grupo_id).order_by("orden").values()),
            TrazaCaso.objects.filter(caso=caso).count(),
            ReservaPlaza.objects.count(),
            Estadia.objects.count(),
        )


# ---------------------------------------------------------------------------
# Acceso
# ---------------------------------------------------------------------------


class AccesoALlegadasTests(BaseApiLlegadas):
    def setUp(self):
        super().setUp()
        self.caso, self.derivacion = self._aceptado()
        self.pendiente_caso, self.pendiente = self._derivado(dni="30222333")

    def _rutas(self):
        """Toda ruta nueva de M2 con ids **reales** del Centro, y los métodos que tiene."""
        caso, centro = self.caso.pk, self.centro.pk
        return [
            ("get", _url("dispositivo-buscar", centro) + "?dni=30111222"),
            ("get", _url("dispositivo-plazas", centro) + f"?caso={caso}"),
            ("post", _url("derivacion-aceptar", self.pendiente.pk)),
            ("post", _url("derivacion-rechazar", self.pendiente.pk)),
            ("get", _url("caso-integrantes", caso)),
            ("post", _url("caso-integrantes", caso)),
            ("get", _url("caso-integrante", caso, 1)),
            ("patch", _url("caso-integrante", caso, 1)),
            ("post", _url("caso-integrante-confirmar", caso, 1)),
            ("post", _url("caso-alojar", caso)),
            ("post", _url("caso-cerrar-diferencia", caso)),
            ("post", _url("caso-cancelar-ingreso", caso)),
            ("post", _url("dispositivo-ingreso-directo", centro)),
            ("post", _url("dispositivo-avisar-mesa", centro)),
        ]

    def _cuerpo_valido(self, url):
        """Un cuerpo que pasaría si el usuario pudiera: así lo que frena es el permiso, no la forma."""
        if "ingreso-directo" in url or "avisar-mesa" in url:
            return self._cuerpo(), "multipart"
        return (
            {
                "uuid_cliente": str(uuid.uuid4()),
                "motivo": "SIN_PLAZAS",
                "ficha": ficha_minima("40111222"),
                "plaza_id": self._reservas(self.derivacion)[0].plaza_id,
            },
            "json",
        )

    def _pedir(self, cliente, metodo, url):
        """Un GET va sin cuerpo: con datos, el cliente de pruebas pisa la consulta de la URL."""
        if metodo == "get":
            return cliente.get(url)
        cuerpo, formato = self._cuerpo_valido(url)
        return getattr(cliente, metodo)(url, cuerpo, format=formato)

    def test_sin_token_todo_es_401(self):
        for metodo, url in self._rutas():
            with self.subTest(metodo=metodo, url=url):
                self.assertEqual(getattr(self._anonimo(), metodo)(url, {}, format="json").status_code, 401)

    def test_un_rol_de_becas_recibe_403_sin_modulo_en_todo_y_no_escribe_nada(self):
        antes = (self._foto_del_caso(self.caso), self._foto_del_caso(self.pendiente_caso))
        casos = CasoEmergencia.objects.count()
        cliente = self._como(self.territorial_becas)

        for metodo, url in self._rutas():
            with self.subTest(metodo=metodo, url=url):
                respuesta = self._pedir(cliente, metodo, url)
                self.assertEqual(respuesta.status_code, 403)
                self.assertEqual(sorted(respuesta.json()), CLAVES_SIN_MODULO)
                self.assertEqual(respuesta.json(), SIN_MODULO)

        self.assertEqual((self._foto_del_caso(self.caso), self._foto_del_caso(self.pendiente_caso)), antes)
        self.assertEqual(CasoEmergencia.objects.count(), casos)

    def test_quien_abre_el_modulo_sin_admitir_recibe_403(self):
        """El agente territorial y el depósito que solo recibe kits abren el módulo, no la llegada de familias."""
        deposito = self._guardia("deposito", [RECIBIR_KIT], [self.centro])
        antes = self._foto_del_caso(self.caso)

        for usuario in (self.agente, deposito):
            cliente = self._como(usuario)
            for metodo, url in self._rutas():
                with self.subTest(usuario=usuario.username, metodo=metodo, url=url):
                    respuesta = self._pedir(cliente, metodo, url)
                    self.assertEqual((respuesta.status_code, respuesta.json()), (403, SIN_ADMITIR))
        self.assertEqual(self._foto_del_caso(self.caso), antes)

    def test_el_admin_de_dispositivos_sin_admitir_no_opera_y_el_perfil_lo_dice(self):
        admin = self._guardia("admin_disp", ["programa.configurar"])
        cliente = self._como(admin)

        self.assertEqual(cliente.get("/api/emergencia/perfil/").json(), {"relevar": False, "dispositivo": False})
        respuesta = cliente.get(_url("dispositivo-buscar", self.centro.pk), {"dni": "30111222"})
        self.assertEqual((respuesta.status_code, respuesta.json()), (403, SIN_ADMITIR))

    def test_el_admin_de_dispositivos_con_admitir_opera_cualquiera_sin_equipo(self):
        admin = self._guardia("admin_disp", ["programa.configurar", *GUARDIA])
        cliente = self._como(admin)

        self.assertEqual(cliente.get("/api/emergencia/perfil/").json(), {"relevar": False, "dispositivo": True})
        respuesta = cliente.get(_url("caso-integrantes", self.caso.pk))
        self.assertEqual(respuesta.status_code, 200)

    def test_la_guardia_de_otro_dispositivo_recibe_404_en_todo(self):
        """**Mutación de RU §6 n.° 2 / C2 por la API.** La guardia de la Escuela pide todo lo del Centro.

        Visto en rojo: con ``_VistaDeLlegadas._ingreso`` sin el filtro del alcance (la última
        derivación del caso, sin preguntar si su dispositivo está en ``dispositivos_en_alcance``),
        ``GET casos/{id}/integrantes/`` y ``GET …/integrantes/1/`` contestan **200 con la familia
        del Centro** (nombre, DNI, cama) —«200 != 404»—, ``cerrar-diferencia`` contesta el 400 del
        motivo en vez del 404, y ``test_un_caso_que_la_mesa_derivo_a_otro_lado…`` da 409 en vez de
        404. El resto de las escrituras las sigue frenando el servicio (``PermissionDenied`` →
        404): para las lecturas, la guarda de la vista es la única. Restaurada, verde. El cuerpo
        es el de un id inexistente y no nombra al Centro.
        """
        cliente = self._como(self.guardia_escuela)
        antes = (self._foto_del_caso(self.caso), self._foto_del_caso(self.pendiente_caso))
        casos = CasoEmergencia.objects.count()
        inexistente = cliente.get(_url("caso-integrantes", 999_999))
        self.assertEqual((inexistente.status_code, inexistente.json()), (404, NO_ENCONTRADO))

        rutas = [*self._rutas(), ("get", _url("dispositivo-plazas", self.escuela.pk) + f"?caso={self.caso.pk}")]
        for metodo, url in rutas:
            with self.subTest(metodo=metodo, url=url):
                respuesta = self._pedir(cliente, metodo, url)
                self.assertEqual(respuesta.status_code, 404)
                self.assertEqual(respuesta.json(), NO_ENCONTRADO)
                self.assertNotIn("Centro", respuesta.content.decode())
                self.assertNotIn("Benítez", respuesta.content.decode())

        self.assertEqual((self._foto_del_caso(self.caso), self._foto_del_caso(self.pendiente_caso)), antes)
        self.assertEqual(CasoEmergencia.objects.count(), casos)

    def test_un_caso_que_la_mesa_derivo_a_otro_lado_deja_de_ser_de_la_guardia(self):
        """Rechazado por el Centro y derivado a la Escuela: para el Centro ya no existe (RU-9)."""
        servicio.rechazar_derivacion(derivacion=self.pendiente, usuario=self.guardia_centro, motivo="SIN_PLAZAS")
        caso = CasoEmergencia.objects.get(pk=self.pendiente_caso.pk)
        mesa.derivar_caso(caso, self.operador, self.escuela, 2, True)

        respuesta = self._como(self.guardia_centro).get(_url("caso-integrantes", caso.pk))

        self.assertEqual((respuesta.status_code, respuesta.json()), (404, NO_ENCONTRADO))


# ---------------------------------------------------------------------------
# mis-dispositivos (lo que suma el PR 8)
# ---------------------------------------------------------------------------


class MisDispositivosConLlegadasTests(BaseApiLlegadas):
    def test_suma_camas_libres_y_derivaciones_pendientes(self):
        self._ocupar(self.centro, 1)
        self._derivado()
        self._derivado(dni="30222333", plazas=2)
        self._aceptado(dni="30333444", menores_f=0, menores_m=0)  # 2 personas: 2 camas reservadas, ya no pendiente

        respuesta = self._como(self.guardia_centro).get(URL_MIS_DISPOSITIVOS)

        self.assertEqual(respuesta.status_code, 200)
        (fila,) = respuesta.json()
        self.assertEqual(sorted(fila), CLAVES_MI_DISPOSITIVO)
        self.assertEqual(fila["derivaciones_pendientes"], 2)
        self.assertEqual(fila["plazas_libres"], 6)
        self.assertEqual(fila["plazas_libres"], len(selectores.camas_libres(self.centro)))

    def test_la_cama_fuera_de_servicio_y_la_de_un_sector_inactivo_no_cuentan(self):
        Plaza.objects.filter(pk=Plaza.objects.filter(sector__dispositivo=self.centro).first().pk).update(
            estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="Rota"
        )
        inactivo = Sector.objects.create(dispositivo=self.centro, nombre="Viejo", capacidad=3, activo=False)
        Plaza.objects.bulk_create([Plaza(sector=inactivo, codigo=f"V{n}") for n in range(3)])

        (fila,) = self._como(self.guardia_centro).get(URL_MIS_DISPOSITIVOS).json()

        self.assertEqual(fila["plazas_libres"], 8)
        self.assertEqual(fila["plazas_libres"], len(selectores.camas_libres(self.centro)))

    def test_no_cuenta_lo_de_otro_dispositivo(self):
        self._derivado(dispositivo=self.escuela)

        (fila,) = self._como(self.guardia_centro).get(URL_MIS_DISPOSITIVOS).json()

        self.assertEqual((fila["id"], fila["derivaciones_pendientes"]), (self.centro.pk, 0))


@tag("performance")
class PresupuestoDeMisDispositivosTests(BaseApiLlegadas):
    def _consultas(self, usuario, url):
        cliente = self._como(usuario)
        cliente.get(url)
        with CaptureQueriesContext(connection) as capturadas:
            self.assertEqual(cliente.get(url).status_code, 200)
        return len(capturadas)

    def test_no_crece_con_los_dispositivos_ni_con_las_derivaciones(self):
        self._derivado()
        con_uno = self._consultas(self.guardia_centro, URL_MIS_DISPOSITIVOS)
        muchos = [self._dispositivo(f"Sede {n:02d}", camas=3) for n in range(30)]
        de_todos = self._guardia("guardia_de_todos", [ADMITIR], muchos)
        for n, dispositivo in enumerate(muchos):
            self._derivado(dispositivo=dispositivo, dni=str(31_000_000 + n), menores_f=0, menores_m=0)

        self.assertEqual(self._consultas(de_todos, URL_MIS_DISPOSITIVOS), con_uno)
        filas = self._como(de_todos).get(URL_MIS_DISPOSITIVOS).json()
        self.assertEqual({(fila["plazas_libres"], fila["derivaciones_pendientes"]) for fila in filas}, {(3, 1)})

    def test_el_selector_cuesta_tres_consultas(self):
        muchos = [self._dispositivo(f"Sede {n:02d}", camas=3) for n in range(30)]
        for n, dispositivo in enumerate(muchos):
            self._derivado(dispositivo=dispositivo, dni=str(31_000_000 + n), menores_f=0, menores_m=0)
        ids = [dispositivo.pk for dispositivo in muchos]

        with self.assertNumQueries(3):
            resumen = selectores.resumen_de_llegadas(
                type(self.centro).objects.filter(pk__in=ids)  # el queryset va como subconsulta
            )
        self.assertEqual(len(resumen), 30)


# ---------------------------------------------------------------------------
# Buscar (M2-1)
# ---------------------------------------------------------------------------


class BuscarFamiliaApiTests(BaseApiLlegadas):
    def _buscar(self, dni, usuario=None, dispositivo=None):
        return self._como(usuario or self.guardia_centro).get(
            _url("dispositivo-buscar", (dispositivo or self.centro).pk), {"dni": dni}
        )

    def test_con_derivacion_trae_la_tarjeta_con_claves_exactas(self):
        caso, derivacion = self._derivado(embarazo=True, telefono="3624000000")

        respuesta = self._buscar("30.111.222")

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(sorted(cuerpo), CLAVES_BUSQUEDA)
        self.assertEqual((cuerpo["resultado"], cuerpo["dni"], cuerpo["plazas_libres"]), ("DERIVACION", "30111222", 9))
        tarjeta = cuerpo["derivacion"]
        self.assertEqual(sorted(tarjeta), CLAVES_DERIVACION_LLEGADA)
        self.assertEqual(sorted(tarjeta["caso"]), CLAVES_CASO_RESUMEN)
        self.assertEqual(sorted(tarjeta["responsable"]), CLAVES_RESPONSABLE)
        self.assertEqual(sorted(tarjeta["grupo"]), CLAVES_GRUPO_DE_LA_DERIVACION)
        self.assertEqual((tarjeta["id"], tarjeta["estado"], tarjeta["plazas_pedidas"]), (derivacion.pk, "PENDIENTE", 7))
        self.assertEqual(tarjeta["caso"]["id"], caso.pk)
        self.assertEqual(tarjeta["responsable"], {"nombre": "Rosa", "apellido": "Benítez", "dni": "30111222"})
        self.assertEqual(tarjeta["necesidades"], ["embarazo"])
        self.assertEqual(tarjeta["derivada_por"], "Ana López")
        self.assertIs(tarjeta["vencida"], False)
        self.assertEqual((cuerpo["alojada_aca"], cuerpo["alojada_en"], cuerpo["alojada_desde"]), (None, "", None))

    def test_la_derivacion_a_otro_dispositivo_es_sin_derivacion_y_no_lo_nombra(self):
        self._derivado(dispositivo=self.escuela)

        respuesta = self._buscar("30111222")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["resultado"], "SIN_DERIVACION")
        self.assertIsNone(respuesta.json()["derivacion"])
        self.assertNotIn("Escuela", respuesta.content.decode())

    def test_alojada_aca(self):
        caso, _derivacion = self._aceptado()
        self._confirmar_con_el_servicio(caso, 1, "30111222")
        servicio.cerrar_con_diferencia(caso=caso, usuario=self.guardia_centro, motivo="NO_LLEGO")

        cuerpo = self._buscar("30111222").json()

        self.assertEqual(
            (cuerpo["resultado"], cuerpo["alojada_aca"], cuerpo["alojada_en"]), ("ALOJADA", True, "Centro Norte")
        )

    def test_un_dni_invalido_es_400(self):
        respuesta = self._buscar("12")

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["code"], "VALIDACION")
        self.assertIn("dni", respuesta.json())


# ---------------------------------------------------------------------------
# Aceptar y rechazar (M2-2)
# ---------------------------------------------------------------------------


class AceptarYRechazarApiTests(BaseApiLlegadas):
    def test_aceptar_reserva_y_devuelve_las_filas(self):
        caso, derivacion = self._derivado(plazas=7)
        self._ocupar(self.centro, 4)  # quedan 5 libres de 9

        respuesta = self._como(self.guardia_centro).post(
            _url("derivacion-aceptar", derivacion.pk), {"uuid_cliente": str(uuid.uuid4())}, format="json"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        cuerpo = respuesta.json()
        self.assertEqual(sorted(cuerpo), CLAVES_ACEPTACION)
        self.assertEqual(sorted(cuerpo["caso"]), CLAVES_CASO_RESUMEN)
        self.assertEqual((cuerpo["reservadas"], cuerpo["faltantes"]), (5, 2))
        self.assertEqual(cuerpo["mensaje"], "Reservé 5 de 7 · faltan 2 camas")
        self.assertEqual(cuerpo["caso"]["estado"], Estado.INGRESO_EN_CURSO)
        self.assertEqual([fila["n"] for fila in cuerpo["integrantes"]], [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual([sorted(fila) for fila in cuerpo["integrantes"]], [CLAVES_INTEGRANTE] * 7)
        self.assertEqual(len(self._reservas(derivacion)), 5)

    def test_la_web_acepta_y_despues_la_app_recibe_409(self):
        """§10 de 03: dos guardias, una en el backoffice y otra en la app, sobre el mismo caso."""
        caso, derivacion = self._derivado()
        self.client.force_login(self.guardia_centro)
        web = self.client.post(reverse("dispositivos:emergencia_aceptar", args=[self.centro.pk, derivacion.pk]))
        self.assertEqual(web.status_code, 302)
        reservas = ReservaPlaza.objects.count()

        respuesta = self._como(self.guardia_centro).post(_url("derivacion-aceptar", derivacion.pk), {}, format="json")

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(sorted(respuesta.json()), CLAVES_ESTADO_CAMBIO)
        self.assertEqual(respuesta.json()["estado_actual"], Estado.INGRESO_EN_CURSO)
        self.assertIn("ya la aceptó", respuesta.json()["detail"])
        self.assertEqual(ReservaPlaza.objects.count(), reservas)

    def test_sin_camas_libres_es_400_en_plazas(self):
        _caso, derivacion = self._derivado()
        self._ocupar(self.centro, 9)

        respuesta = self._como(self.guardia_centro).post(_url("derivacion-aceptar", derivacion.pk), {}, format="json")

        self.assertEqual(respuesta.status_code, 400)
        self.assertTrue(CLAVES_FIJAS_DEL_400 <= set(respuesta.json()))
        self.assertIn("plazas", respuesta.json())
        self.assertEqual(Derivacion.objects.get(pk=derivacion.pk).estado, Derivacion.Estado.PENDIENTE)

    def test_rechazar_devuelve_el_caso_a_la_mesa(self):
        caso, derivacion = self._derivado()

        respuesta = self._como(self.guardia_centro).post(
            _url("derivacion-rechazar", derivacion.pk), {"motivo": "NO_CUMPLE_PERFIL"}, format="json"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(sorted(respuesta.json()), CLAVES_RECHAZO)
        self.assertEqual(respuesta.json(), {"caso_estado": Estado.EN_GESTION})
        self.assertEqual(Derivacion.objects.get(pk=derivacion.pk).estado, Derivacion.Estado.RECHAZADA)

    def test_rechazar_sin_motivo_o_con_otro_sin_observacion_es_400(self):
        _caso, derivacion = self._derivado()
        cliente = self._como(self.guardia_centro)

        for cuerpo, campo in (({}, "motivo"), ({"motivo": "INVENTADO"}, "motivo"), ({"motivo": "OTRO"}, "observacion")):
            with self.subTest(cuerpo=cuerpo):
                respuesta = cliente.post(_url("derivacion-rechazar", derivacion.pk), cuerpo, format="json")
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn(campo, respuesta.json())
        self.assertEqual(Derivacion.objects.get(pk=derivacion.pk).estado, Derivacion.Estado.PENDIENTE)

    def test_rechazar_una_ya_aceptada_es_409(self):
        _caso, derivacion = self._aceptado()

        respuesta = self._como(self.guardia_centro).post(
            _url("derivacion-rechazar", derivacion.pk), {"motivo": "SIN_PLAZAS"}, format="json"
        )

        self.assertEqual((respuesta.status_code, respuesta.json()["estado_actual"]), (409, Estado.INGRESO_EN_CURSO))


# ---------------------------------------------------------------------------
# Integrantes (M2-3, M2-4)
# ---------------------------------------------------------------------------


class IntegrantesApiTests(BaseApiLlegadas):
    def setUp(self):
        super().setUp()
        self.caso, self.derivacion = self._aceptado()

    def test_la_lista_tiene_claves_exactas_y_el_contador(self):
        self._confirmar_con_el_servicio(self.caso, 1, "30111222")

        respuesta = self._como(self.guardia_centro).get(_url("caso-integrantes", self.caso.pk))

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(sorted(cuerpo), CLAVES_INTEGRANTES)
        self.assertEqual(sorted(cuerpo["caso"]), CLAVES_CASO_RESUMEN)
        self.assertEqual((cuerpo["confirmadas"], cuerpo["total_declarado"], cuerpo["declaradas_al_relevar"]), (1, 7, 7))
        primera, segunda = cuerpo["integrantes"][:2]
        self.assertEqual(sorted(primera), CLAVES_INTEGRANTE)
        self.assertEqual(sorted(primera["persona"]), CLAVES_PERSONA_DEL_INTEGRANTE)
        self.assertEqual(sorted(primera["plaza"]), CLAVES_PLAZA_DEL_INTEGRANTE)
        self.assertEqual((primera["n"], primera["estado"], primera["persona"]["dni"]), (1, "CONFIRMADA", "30111222"))
        self.assertEqual((segunda["estado"], segunda["persona"], segunda["plaza"]), ("SIN_CONFIRMAR", None, None))

    def test_antes_de_aceptar_es_409(self):
        caso, _derivacion = self._derivado(dni="30222333")

        respuesta = self._como(self.guardia_centro).get(_url("caso-integrantes", caso.pk))

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.json()["estado_actual"], Estado.DERIVADO)

    def test_confirmar_crea_la_estadia_y_devuelve_la_fila(self):
        respuesta = self._confirmar(self.caso, 2, "45111222")

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        cuerpo = respuesta.json()
        self.assertEqual(sorted(cuerpo), CLAVES_CONFIRMACION)
        self.assertEqual(sorted(cuerpo["integrante"]), CLAVES_INTEGRANTE)
        self.assertEqual((cuerpo["confirmadas"], cuerpo["total_declarado"], cuerpo["reserva_liberada"]), (1, 7, False))
        self.assertEqual((cuerpo["integrante"]["n"], cuerpo["integrante"]["estado"]), (2, "CONFIRMADA"))
        self.assertTrue(Estadia.objects.activas().filter(ciudadano__dni="45111222").exists())

    def test_confirmar_dos_veces_con_el_mismo_uuid_escribe_una_vez(self):
        """RU-16: el reintento de la app tras perder la respuesta."""
        identificador = uuid.uuid4()
        primera = self._confirmar(self.caso, 2, "45111222", uuid_cliente=identificador)
        estadias, trazas = Estadia.objects.count(), TrazaCaso.objects.count()

        segunda = self._confirmar(self.caso, 2, "45111222", uuid_cliente=identificador)

        self.assertEqual((primera.status_code, segunda.status_code), (201, 200))
        self.assertEqual(segunda.json(), primera.json())
        self.assertEqual((Estadia.objects.count(), TrazaCaso.objects.count()), (estadias, trazas))

    def test_la_web_confirma_y_despues_la_app_recibe_409(self):
        self._confirmar_con_el_servicio(self.caso, 2, "45111222")
        estadias = Estadia.objects.count()

        respuesta = self._confirmar(self.caso, 2, "45111222")

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.json()["estado_actual"], Estado.INGRESO_EN_CURSO)
        self.assertEqual(Estadia.objects.count(), estadias)

    def test_la_ficha_sin_el_minimo_es_400_por_campo_y_no_escribe(self):
        antes = self._foto_del_caso(self.caso)
        cuerpo = {
            "uuid_cliente": str(uuid.uuid4()),
            "plaza_id": self._reservas(self.derivacion)[0].plaza_id,
            "ficha": {"parentesco": {"parentesco": "HIJO"}, "datos_personales": {"dni": "45111222", "nombre": "Juan"}},
        }

        respuesta = self._como(self.guardia_centro).post(
            _url("caso-integrante-confirmar", self.caso.pk, 2), cuerpo, format="json"
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["code"], "VALIDACION")
        for campo in ("apellido", "sexo", "embarazo", "alergias_graves"):
            self.assertIn(campo, respuesta.json())
        self.assertEqual(self._foto_del_caso(self.caso), antes)

    def test_confirmar_sin_uuid_o_en_una_cama_ocupada_es_400(self):
        ocupada = (
            Plaza.objects.filter(sector__dispositivo=self.centro)
            .exclude(pk__in=[reserva.plaza_id for reserva in self._reservas(self.derivacion)])
            .first()
        )
        self._ocupar_esa(ocupada)
        cliente = self._como(self.guardia_centro)

        sin_uuid = cliente.post(
            _url("caso-integrante-confirmar", self.caso.pk, 2),
            {"ficha": ficha_minima("45111222"), "plaza_id": self._reservas(self.derivacion)[0].plaza_id},
            format="json",
        )
        en_ocupada = self._confirmar(self.caso, 2, "45111222", plaza=ocupada)

        self.assertEqual(sin_uuid.status_code, 400)
        self.assertIn("uuid_cliente", sin_uuid.json())
        self.assertEqual(en_ocupada.status_code, 400)
        self.assertIn("plaza", en_ocupada.json())

    def _ocupar_esa(self, plaza):
        from legajos.models import Ciudadano

        persona = Ciudadano.objects.create(dni="29000111", nombre="Otra", apellido="Persona")
        Estadia.objects.create(
            ciudadano=persona,
            dispositivo=self.centro,
            plaza=plaza,
            fecha_ingreso=self.reloj(),
            clave_alojamiento=Estadia.clave_para(persona),
        )

    def test_agregar_con_el_mismo_uuid_suma_una_sola_fila(self):
        identificador = str(uuid.uuid4())
        cliente = self._como(self.guardia_centro)

        primera = cliente.post(_url("caso-integrantes", self.caso.pk), {"uuid_cliente": identificador}, format="json")
        segunda = cliente.post(_url("caso-integrantes", self.caso.pk), {"uuid_cliente": identificador}, format="json")

        self.assertEqual((primera.status_code, segunda.status_code), (201, 200))
        self.assertEqual(sorted(primera.json()), CLAVES_INTEGRANTE_AGREGADO)
        self.assertEqual(primera.json(), segunda.json())
        self.assertEqual((primera.json()["integrante"]["n"], primera.json()["total_declarado"]), (8, 8))
        self.assertEqual(IntegranteGrupo.objects.filter(grupo_id=self.caso.grupo_id).count(), 8)

    def test_agregar_sin_uuid_es_400(self):
        respuesta = self._como(self.guardia_centro).post(_url("caso-integrantes", self.caso.pk), {}, format="json")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("uuid_cliente", respuesta.json())
        self.assertEqual(IntegranteGrupo.objects.filter(grupo_id=self.caso.grupo_id).count(), 7)

    def test_el_detalle_trae_la_ficha_sin_los_identificadores_de_envio(self):
        self._confirmar(self.caso, 2, "45111222")

        respuesta = self._como(self.guardia_centro).get(_url("caso-integrante", self.caso.pk, 2))

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(sorted(cuerpo), CLAVES_INTEGRANTE_DETALLE)
        self.assertEqual(cuerpo["ficha"]["datos_personales"]["dni"], "45111222")
        self.assertNotIn("uuid_cliente", cuerpo["ficha"])
        self.assertEqual(len(cuerpo["secciones_incompletas"]), 5)

    def test_el_detalle_de_una_persona_que_no_es_de_la_familia_es_404(self):
        respuesta = self._como(self.guardia_centro).get(_url("caso-integrante", self.caso.pk, 99))

        self.assertEqual((respuesta.status_code, respuesta.json()), (404, NO_ENCONTRADO))

    def test_completar_la_ficha_con_patch(self):
        self._confirmar(self.caso, 2, "45111222")
        secciones = {seccion: {"sin_datos": True} for seccion in servicio.SECCIONES_OPCIONALES}
        secciones["educacion"] = {"nivel_educativo": "PRIMARIO", "asiste_escuela": True}

        respuesta = self._como(self.guardia_centro).patch(
            _url("caso-integrante", self.caso.pk, 2), {"ficha": secciones}, format="json"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(sorted(respuesta.json()), CLAVES_FICHA_COMPLETADA)
        self.assertEqual(respuesta.json(), {"ficha_completa": True, "secciones_incompletas": []})
        fila = IntegranteGrupo.objects.get(grupo_id=self.caso.grupo_id, orden=2)
        self.assertTrue(fila.ficha_completa)
        self.assertEqual(fila.ficha["educacion"]["nivel_educativo"], "PRIMARIO")

    def test_completar_la_ficha_de_alguien_sin_confirmar_es_400(self):
        respuesta = self._como(self.guardia_centro).patch(
            _url("caso-integrante", self.caso.pk, 3), {"ficha": {"educacion": {"sin_datos": True}}}, format="json"
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("orden", respuesta.json())


# ---------------------------------------------------------------------------
# Mapa de plazas
# ---------------------------------------------------------------------------


class PlazasApiTests(BaseApiLlegadas):
    def test_el_mapa_marca_las_de_la_familia_y_tiene_claves_exactas(self):
        caso, derivacion = self._aceptado(plazas=3)
        Plaza.objects.filter(
            pk=Plaza.objects.filter(sector__dispositivo=self.centro).order_by("-codigo").first().pk
        ).update(estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="Rota")

        respuesta = self._como(self.guardia_centro).get(_url("dispositivo-plazas", self.centro.pk), {"caso": caso.pk})

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(sorted(cuerpo), CLAVES_MAPA)
        self.assertEqual(cuerpo["caso"], caso.pk)
        (sector,) = cuerpo["sectores"]
        self.assertEqual(sorted(sector), CLAVES_SECTOR_CON_PLAZAS)
        self.assertEqual(sorted(sector["sector"]), CLAVES_SECTOR_DEL_MAPA)
        self.assertEqual({sorted(plaza).__repr__() for plaza in sector["plazas"]}, {repr(CLAVES_PLAZA_DEL_MAPA)})
        estados = [plaza["estado"] for plaza in sector["plazas"]]
        self.assertEqual(estados.count("RESERVADA_FAMILIA"), 3)
        self.assertEqual(estados.count("FUERA_SERVICIO"), 1)
        self.assertEqual(estados.count("LIBRE"), 5)
        self.assertEqual((sector["total"], sector["libres"], sector["reservadas_familia"]), (9, 5, 3))
        reservadas = {reserva.plaza_id for reserva in self._reservas(derivacion)}
        self.assertEqual({p["id"] for p in sector["plazas"] if p["estado"] == "RESERVADA_FAMILIA"}, reservadas)

    def test_las_de_otra_familia_salen_reservadas_sin_decir_de_quien(self):
        self._aceptado(plazas=3)
        otro, _derivacion = self._aceptado(dni="30222333", menores_f=0, menores_m=0)

        cuerpo = (
            self._como(self.guardia_centro).get(_url("dispositivo-plazas", self.centro.pk), {"caso": otro.pk}).json()
        )

        plazas = cuerpo["sectores"][0]["plazas"]
        self.assertEqual(sum(plaza["estado"] == "RESERVADA" for plaza in plazas), 3)
        self.assertEqual(sum(plaza["estado"] == "RESERVADA_FAMILIA" for plaza in plazas), 2)
        self.assertNotIn("Benítez", str([plaza for plaza in plazas if plaza["estado"] == "RESERVADA"]))

    def test_sin_caso_ninguna_es_de_la_familia_y_un_caso_ilegible_es_404(self):
        self._aceptado(plazas=3)
        cliente = self._como(self.guardia_centro)

        sin_caso = cliente.get(_url("dispositivo-plazas", self.centro.pk)).json()
        ilegible = cliente.get(_url("dispositivo-plazas", self.centro.pk), {"caso": "abc"})

        self.assertIsNone(sin_caso["caso"])
        self.assertNotIn("RESERVADA_FAMILIA", [plaza["estado"] for plaza in sin_caso["sectores"][0]["plazas"]])
        self.assertEqual(ilegible.status_code, 404)


# ---------------------------------------------------------------------------
# Cerrar el ingreso (M2-5, RN-3.9)
# ---------------------------------------------------------------------------


class CerrarIngresoApiTests(BaseApiLlegadas):
    def test_alojar_con_todas_confirmadas(self):
        caso, derivacion = self._aceptado(dni="30111222", menores_f=0, menores_m=0, plazas=3)  # 2 personas, 3 camas
        self._confirmar(caso, 1, "30111222")
        self._confirmar(caso, 2, "45111222")
        sector = Sector.objects.filter(dispositivo=self.centro).first()

        respuesta = self._como(self.guardia_centro).post(
            _url("caso-alojar", caso.pk),
            {"sector": sector.pk, "aula": "Aula 3", "tarjeta_entregada": True, "tarjeta_numero": "0042"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(sorted(respuesta.json()), CLAVES_CIERRE_DE_INGRESO)
        self.assertEqual(respuesta.json(), {"estado": Estado.ALOJADO, "total_alojado": 2, "liberadas": 1})
        self.assertEqual(CasoEmergencia.objects.get(pk=caso.pk).situacion["alojamiento"]["aula"], "Aula 3")

        otra_vez = self._como(self.guardia_centro).post(_url("caso-alojar", caso.pk), {}, format="json")
        self.assertEqual((otra_vez.status_code, otra_vez.json()["estado_actual"]), (409, Estado.ALOJADO))

    def test_alojar_con_alguien_sin_confirmar_es_400(self):
        caso, _derivacion = self._aceptado()
        self._confirmar(caso, 1, "30111222")

        respuesta = self._como(self.guardia_centro).post(_url("caso-alojar", caso.pk), {}, format="json")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("Falta confirmar", respuesta.json()["detail"])
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)

    def test_cerrar_con_diferencia(self):
        caso, _derivacion = self._aceptado()
        self._confirmar(caso, 1, "30111222")

        respuesta = self._como(self.guardia_centro).post(
            _url("caso-cerrar-diferencia", caso.pk), {"motivo": "QUEDO_CON_FAMILIARES"}, format="json"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json(), {"estado": Estado.ALOJADO, "total_alojado": 1, "liberadas": 6})

    def test_cerrar_con_diferencia_sin_motivo_es_400(self):
        caso, _derivacion = self._aceptado()
        self._confirmar(caso, 1, "30111222")

        respuesta = self._como(self.guardia_centro).post(_url("caso-cerrar-diferencia", caso.pk), {}, format="json")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("motivo", respuesta.json())

    def test_cancelar_el_ingreso_sin_nadie_confirmado(self):
        caso, derivacion = self._aceptado()

        respuesta = self._como(self.guardia_centro).post(
            _url("caso-cancelar-ingreso", caso.pk), {"motivo": "La familia se fue con parientes."}, format="json"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json()["estado"], Estado.EN_GESTION)
        self.assertEqual(respuesta.json()["liberadas"], 7)
        self.assertEqual(self._reservas(derivacion), [])

    def test_la_web_cancela_y_la_app_quiere_alojar_409(self):
        caso, _derivacion = self._aceptado()
        servicio.cancelar_ingreso(caso=caso, usuario=self.guardia_centro, motivo="Se fueron.")

        respuesta = self._como(self.guardia_centro).post(_url("caso-alojar", caso.pk), {}, format="json")

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.json()["estado_actual"], Estado.EN_GESTION)

    def _estado(self, caso):
        return CasoEmergencia.objects.values_list("estado", flat=True).get(pk=caso.pk)


# ---------------------------------------------------------------------------
# Sin derivación (M2-6)
# ---------------------------------------------------------------------------


class SinDerivacionApiTests(BaseApiLlegadas):
    def _cuerpo_puerta(self, uuid_cliente=None, **cambios):
        cuerpo = self._cuerpo(uuid_cliente=uuid_cliente, **cambios)
        cuerpo.pop("direccion", None)  # en la puerta, la dirección es opcional
        return cuerpo

    def test_ingreso_directo_crea_el_caso_y_es_idempotente(self):
        identificador = uuid.uuid4()
        cliente = self._como(self.guardia_centro)
        url = _url("dispositivo-ingreso-directo", self.centro.pk)

        primera = cliente.post(url, self._cuerpo_puerta(identificador, adultos_m=2), format="multipart")
        casos, reservas = CasoEmergencia.objects.count(), ReservaPlaza.objects.count()
        segunda = cliente.post(url, self._cuerpo_puerta(identificador, adultos_m=5), format="multipart")

        self.assertEqual((primera.status_code, segunda.status_code), (201, 200), primera.content)
        cuerpo = primera.json()
        self.assertEqual(sorted(cuerpo), CLAVES_INGRESO_DIRECTO)
        self.assertEqual(sorted(cuerpo["caso"]), CLAVES_CASO_RESUMEN)
        self.assertEqual(cuerpo["caso"]["estado"], Estado.INGRESO_EN_CURSO)
        self.assertEqual((cuerpo["reservadas"], cuerpo["faltantes"]), (3, 0))
        self.assertEqual(len(cuerpo["integrantes"]), 3)
        self.assertEqual(segunda.json(), cuerpo)
        self.assertEqual((CasoEmergencia.objects.count(), ReservaPlaza.objects.count()), (casos, reservas))
        caso = CasoEmergencia.objects.get(pk=cuerpo["caso"]["id"])
        self.assertEqual(caso.origen, CasoEmergencia.Origen.DISPOSITIVO)

    def test_ingreso_directo_sin_camas_es_400_y_sin_uuid_tambien(self):
        self._ocupar(self.centro, 9)
        cliente = self._como(self.guardia_centro)
        url = _url("dispositivo-ingreso-directo", self.centro.pk)

        sin_camas = cliente.post(url, self._cuerpo_puerta(), format="multipart")
        cuerpo = self._cuerpo_puerta()
        cuerpo.pop("uuid_cliente")
        sin_uuid = cliente.post(url, cuerpo, format="multipart")

        self.assertEqual(sin_camas.status_code, 400)
        self.assertIn("plazas", sin_camas.json())
        self.assertEqual(sin_uuid.status_code, 400)
        self.assertIn("uuid_cliente", sin_uuid.json())
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    def test_el_uuid_de_otro_usuario_es_409(self):
        identificador = uuid.uuid4()
        self._como(self.guardia_escuela).post(
            _url("dispositivo-ingreso-directo", self.escuela.pk), self._cuerpo_puerta(identificador), format="multipart"
        )

        respuesta = self._como(self.guardia_centro).post(
            _url("dispositivo-ingreso-directo", self.centro.pk), self._cuerpo_puerta(identificador), format="multipart"
        )

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.json()["code"], "UUID_EN_USO")
        self.assertEqual(CasoEmergencia.objects.count(), 1)

    def test_el_409_sale_por_tipo_aunque_cambie_el_texto_del_mensaje(self):
        """``_ejecutar`` atrapa ``UuidEnUso`` por tipo, no compara el texto (PR #1130).

        **Mutación vista en rojo:** con la comparación de ``errores["uuid_cliente"]`` contra
        ``[UUID_EN_USO]`` de vuelta, el mensaje cambiado sale como 400. Restaurada, verde.
        """
        identificador = uuid.uuid4()
        self._como(self.guardia_escuela).post(
            _url("dispositivo-ingreso-directo", self.escuela.pk), self._cuerpo_puerta(identificador), format="multipart"
        )

        with mock.patch.object(emergencia_alta, "UUID_EN_USO", "Ese identificador ya lo usó otra persona."):
            respuesta = self._como(self.guardia_centro).post(
                _url("dispositivo-avisar-mesa", self.centro.pk), self._cuerpo_puerta(identificador), format="multipart"
            )

        self.assertEqual(respuesta.status_code, 409, respuesta.content)
        self.assertEqual(
            respuesta.json(), {"detail": "Ese identificador ya lo usó otra persona.", "code": "UUID_EN_USO"}
        )
        self.assertEqual(CasoEmergencia.objects.count(), 1)

    def test_las_reglas_del_formulario_1_en_la_puerta_son_las_del_servicio(self):
        """Mismo serializer que M1: ni tope propio de ``traslado_otro`` ni mínimo propio en las cantidades."""
        cliente = self._como(self.guardia_centro)
        url = _url("dispositivo-ingreso-directo", self.centro.pk)

        negativa = cliente.post(url, self._cuerpo_puerta(adultos_f=-1, traslado=""), format="multipart")
        largo = cliente.post(url, self._cuerpo_puerta(traslado="OTRA", traslado_otro="G" * 80), format="multipart")

        self.assertEqual(negativa.status_code, 400, negativa.content)
        self.assertEqual(negativa.json()["adultos_f"], ["No puede ser negativo."])
        self.assertIn("traslado", negativa.json())
        self.assertEqual(largo.status_code, 201, largo.content)
        self.assertEqual(CasoEmergencia.objects.get().grupo.traslado_otro, "G" * 80)

    def test_avisar_a_la_mesa_crea_un_caso_nuevo_e_idempotente(self):
        identificador = uuid.uuid4()
        cliente = self._como(self.guardia_centro)
        url = _url("dispositivo-avisar-mesa", self.centro.pk)

        primera = cliente.post(url, self._cuerpo_puerta(identificador), format="multipart")
        segunda = cliente.post(url, self._cuerpo_puerta(identificador), format="multipart")

        self.assertEqual((primera.status_code, segunda.status_code), (201, 200), primera.content)
        self.assertEqual(sorted(primera.json()), CLAVES_AVISO_A_LA_MESA)
        self.assertEqual(primera.json(), segunda.json())
        self.assertEqual(primera.json()["caso"]["estado"], Estado.NUEVO)
        self.assertEqual(CasoEmergencia.objects.count(), 1)


# ---------------------------------------------------------------------------
# Presupuestos de consultas
# ---------------------------------------------------------------------------


@tag("performance")
class PresupuestoDeLlegadasTests(BaseApiLlegadas):
    """``buscar``, ``integrantes`` y ``plazas`` cuestan lo mismo con 9 camas que con 300: sin N+1."""

    def setUp(self):
        super().setUp()
        self.grande = self._dispositivo("Polideportivo", camas=0)
        for letra in "ABC":
            sector = Sector.objects.create(dispositivo=self.grande, nombre=f"Pabellón {letra}", capacidad=100)
            Plaza.objects.bulk_create([Plaza(sector=sector, codigo=f"{letra}-{n}") for n in range(1, 101)])
        self.guardia_grande = self._guardia("guardia_grande", list(GUARDIA), [self.grande])

    def _consultas(self, usuario, url, datos=None):
        cliente = self._como(User.objects.get(pk=usuario.pk))
        self.assertEqual(cliente.get(url, datos).status_code, 200)
        with CaptureQueriesContext(connection) as capturadas:
            self.assertEqual(cliente.get(url, datos).status_code, 200)
        return len(capturadas)

    def _familia_aceptada(self, dispositivo, guardia, dni, confirmadas):
        caso, derivacion = self._derivado(dispositivo=dispositivo, dni=dni, menores_f=4, menores_m=1)
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=guardia)
        for n, reserva in enumerate(self._reservas(derivacion)[:confirmadas], start=1):
            servicio.confirmar_integrante(
                caso=caso,
                orden=n,
                usuario=guardia,
                ficha=ficha_minima(dni if n == 1 else str(int(dni) + 1_000_000 + n)),
                plaza=reserva.plaza,
            )
        return caso

    def test_plazas_con_300_camas_cuesta_lo_mismo_que_con_9(self):
        chico = self._familia_aceptada(self.centro, self.guardia_centro, "30111222", 2)
        grande = self._familia_aceptada(self.grande, self.guardia_grande, "30222333", 2)
        self._ocupar(self.grande, 120)

        con_9 = self._consultas(self.guardia_centro, _url("dispositivo-plazas", self.centro.pk), {"caso": chico.pk})
        con_300 = self._consultas(self.guardia_grande, _url("dispositivo-plazas", self.grande.pk), {"caso": grande.pk})

        self.assertEqual(con_300, con_9)
        self.assertLessEqual(con_300, 14)

    def test_integrantes_no_crece_con_la_familia(self):
        chica = self._familia_aceptada(self.centro, self.guardia_centro, "30111222", 1)
        grande, derivacion = self._derivado(dispositivo=self.grande, dni="30222333", menores_f=20, menores_m=18)
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia_grande)
        for n, reserva in enumerate(self._reservas(derivacion)[:30], start=1):
            servicio.confirmar_integrante(
                caso=grande,
                orden=n,
                usuario=self.guardia_grande,
                ficha=ficha_minima(str(46_000_000 + n)),
                plaza=reserva.plaza,
            )

        con_1 = self._consultas(self.guardia_centro, _url("caso-integrantes", chica.pk))
        con_30 = self._consultas(self.guardia_grande, _url("caso-integrantes", grande.pk))

        self.assertEqual(con_30, con_1)
        self.assertLessEqual(con_30, 12)

    def test_buscar_cuesta_lo_mismo_en_un_dispositivo_de_300_camas(self):
        self._derivado(dispositivo=self.centro, dni="30111222")
        self._derivado(dispositivo=self.grande, dni="30222333")
        self._ocupar(self.grande, 120)

        con_9 = self._consultas(self.guardia_centro, _url("dispositivo-buscar", self.centro.pk), {"dni": "30111222"})
        con_300 = self._consultas(self.guardia_grande, _url("dispositivo-buscar", self.grande.pk), {"dni": "30222333"})

        self.assertEqual(con_300, con_9)
        self.assertLessEqual(con_300, 14)
