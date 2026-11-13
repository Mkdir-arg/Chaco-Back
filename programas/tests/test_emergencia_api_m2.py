"""Módulo Emergencia, PR 8: la API M2 (llegada de familias) — acceso, mis dispositivos y presupuestos.

La guardia del dispositivo hace desde la app **lo mismo** que la pantalla E6 del backoffice
(RU-1), llamando a las mismas funciones de ``services.emergencia_alojar`` (RU-2). Cada flujo
tiene su archivo (``…_m2_busqueda``, ``…_m2_integrantes``, ``…_m2_cierre``); la base
(`BaseApiLlegadas`) y las claves exactas están en ``base_emergencia_api``. Este fija:

* **Alcance (C2, RU-9)**: la guardia de la Escuela no abre nada del Centro aunque conozca los
  ids: **404** con el cuerpo de un id inexistente, sin nombrar al Centro. **Mutación vista en
  rojo**: el detalle está en el docstring de ``test_la_guardia_de_otro_dispositivo_recibe_404_en_todo``.
* **403 ``SIN_MODULO``** para un rol de Becas y para quien abre el módulo sin admitir familias;
  **401** sin token.
* **Presupuestos** (``@tag("performance")``) de ``mis-dispositivos``, ``buscar``, ``integrantes`` y
  ``plazas`` con un dispositivo de 300 camas: no crecen con las filas.
"""

import uuid

from django.contrib.auth.models import User
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext

from programas.models import (
    CasoEmergencia,
    Plaza,
    Sector,
)
from programas.selectors import emergencia_alojar as selectores
from programas.services import emergencia as mesa
from programas.services import emergencia_alojar as servicio
from programas.tests.base_emergencia_api import (
    ADMITIR,
    CLAVES_MI_DISPOSITIVO,
    CLAVES_SIN_MODULO,
    NO_ENCONTRADO,
    SIN_ADMITIR,
    SIN_MODULO,
    URL_MIS_DISPOSITIVOS,
    BaseApiLlegadas,
    _url,
)
from programas.tests.test_emergencia_alojar_base import GUARDIA, ficha_minima
from programas.tests.test_emergencia_base import RECIBIR_KIT

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
