"""P2 · Listado de instituciones, al arquetipo (MVP v2, carril C4).

Lo que se fija acá, y por qué:

1. **Pagina.** Era la única pantalla del programa que materializaba el padrón entero y
   pagaba el semáforo y las plazas de todas las filas en cada visita. Con 25 por página,
   lo que importa es que la página 2 siga dentro del alcance y siga llevando los filtros:
   una paginación que pierde el filtro muestra registros que el usuario creía descartados.
2. **El alcance no cambia**: el listado es exactamente ``dispositivos_visibles``, también
   en la página 2 y también con filtros puestos.
3. **Las cifras de plazas salen de ``ocupacion_de_plazas``**, fuente única: la fila no
   cuenta por su cuenta y el umbral que decide el color vive en el servicio, no en el
   template.
4. **La acción de alta cuelga de ``dispositivo.crear``**, en el encabezado y en el estado
   vacío: quien solo consulta no ve un botón que el servidor le va a rechazar.
5. **El costo de la página no crece con las filas** (presupuesto en
   ``scripts/perf_budgets.json``, sección ``servicios``).
"""

import json

from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase, tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core import rbac
from legajos.models import Ciudadano
from programas.models import (
    AsignacionDispositivo,
    Dispositivo,
    Edificio,
    Estadia,
    InspeccionEdificio,
    Plaza,
    Programa,
    Sector,
    TipoDispositivo,
)
from programas.services.ocupacion import Conteo, tension_de_ocupacion
from users.models import Capacidad, RolMeta

URL_LISTA = reverse("dispositivos:lista")
PRESUPUESTOS = settings.BASE_DIR / "scripts" / "perf_budgets.json"
CLAVE_PRESUPUESTO = "dispositivos_listado_instituciones"


def _permiso(codigo):
    content_type = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=content_type)


class BaseListado(TestCase):
    """Un programa, dos tipos y los usuarios del caso. El alcance se arma por rol, como en producción."""

    def setUp(self):
        self.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        self.tipo_hogar = TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor")
        self.tipo_parador = TipoDispositivo.objects.create(codigo="PAR", nombre="Parador")
        cache.clear()

    def _dispositivo(self, codigo, nombre, **extra):
        extra.setdefault("tipo", self.tipo_hogar)
        return Dispositivo.objects.create(codigo=codigo, nombre=nombre, **extra)

    def _usuario(self, nombre, capacidades, alcance=None):
        """Un usuario con **todas** las capacidades de la lista y el alcance de los dispositivos dados.

        Sin asignaciones y sin la capacidad de administración el rol no ve nada: el
        alcance fino es la regla, no la excepción (ver `_admin`).
        """

        rol = Group.objects.create(name=f"Rol {nombre}")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        for codigo in capacidades:
            rol.permissions.add(_permiso(codigo))
        for dispositivo in alcance or []:
            AsignacionDispositivo.objects.create(dispositivo=dispositivo, rol=rol)
        usuario = User.objects.create_user(nombre, password="x")
        usuario.groups.add(rol)
        cache.clear()
        return usuario

    def _admin(self, nombre, *extra):
        """Alcance total sobre el programa, que es lo que da `programa.configurar`."""

        return self._usuario(nombre, ("dispositivo.ver", "programa.configurar", *extra))

    def _cliente(self, usuario):
        cliente = Client()
        cliente.force_login(usuario)
        return cliente

    def _filas(self, respuesta):
        return [dispositivo.codigo for dispositivo in respuesta.context["dispositivos"]]


class PaginacionTests(BaseListado):
    def setUp(self):
        super().setUp()
        # 26 instituciones: una más que el tamaño de página, que es el único número que
        # distingue «pagina» de «entra todo en una pantalla».
        self.codigos = [f"INS-{n:03d}" for n in range(1, 27)]
        for codigo in self.codigos:
            self._dispositivo(codigo, f"Institución {codigo}", localidad="Resistencia")
        self.admin = self._admin("admin-paginacion")

    def test_la_primera_pagina_trae_veinticinco_y_la_segunda_el_resto(self):
        cliente = self._cliente(self.admin)

        primera = cliente.get(URL_LISTA)
        segunda = cliente.get(URL_LISTA, {"page": 2})

        self.assertEqual(len(self._filas(primera)), 25)
        self.assertEqual(self._filas(segunda), [self.codigos[-1]])
        self.assertEqual(primera.context["page_obj"].paginator.count, 26)
        self.assertContains(primera, "Página 1 de 2 · 26 instituciones")

    def test_el_orden_es_total_asi_ninguna_institucion_se_repite_ni_se_pierde(self):
        """Dos homónimas: con `nombre` solo —el orden del modelo— el motor puede devolverlas en cualquier orden."""

        self._dispositivo("DUP-B", "Hogar repetido", localidad="Resistencia")
        self._dispositivo("DUP-A", "Hogar repetido", localidad="Resistencia")
        cliente = self._cliente(self.admin)

        vistos = self._filas(cliente.get(URL_LISTA)) + self._filas(cliente.get(URL_LISTA, {"page": 2}))

        self.assertEqual(len(vistos), 28)
        self.assertEqual(len(set(vistos)), 28, "una institución apareció en las dos páginas")
        # El desempate es por código: «Hogar repetido» sale dos veces seguidas y en ese orden.
        self.assertEqual(vistos[vistos.index("DUP-A") : vistos.index("DUP-A") + 2], ["DUP-A", "DUP-B"])

    def test_la_segunda_pagina_conserva_los_filtros(self):
        for n in range(27, 60):
            self._dispositivo(f"PAR-{n:03d}", f"Parador {n}", tipo=self.tipo_parador, localidad="Fontana")
        cliente = self._cliente(self.admin)

        respuesta = cliente.get(URL_LISTA, {"tipo": self.tipo_parador.pk})
        segunda = cliente.get(URL_LISTA, {"tipo": self.tipo_parador.pk, "page": 2})

        # El pie de la página 1 lleva el filtro al enlace de «Siguiente»…
        self.assertContains(respuesta, f"page=2&amp;tipo={self.tipo_parador.pk}")
        # …y la página 2 sigue mostrando solo paradores, no las 26 del otro tipo.
        self.assertEqual(len(self._filas(segunda)), 8)
        self.assertTrue(all(codigo.startswith("PAR-") for codigo in self._filas(segunda)))

    def test_el_pie_no_aparece_cuando_entra_todo_en_una_pagina(self):
        Dispositivo.objects.exclude(codigo=self.codigos[0]).delete()

        respuesta = self._cliente(self.admin).get(URL_LISTA)

        self.assertNotContains(respuesta, "Página 1 de")


class FiltrosTests(BaseListado):
    def setUp(self):
        super().setUp()
        self.hogar = self._dispositivo("HOG-1", "Hogar San José", localidad="Barranqueras")
        self.parador = self._dispositivo(
            "PAR-1",
            "Parador Nocturno",
            tipo=self.tipo_parador,
            localidad="Resistencia",
            estado=Dispositivo.Estado.ACTIVO,
        )
        self.admin = self._admin("admin-filtros", "dispositivo.crear")
        self.cliente = self._cliente(self.admin)

    def test_filtra_por_tipo(self):
        respuesta = self.cliente.get(URL_LISTA, {"tipo": self.tipo_parador.pk})

        self.assertEqual(self._filas(respuesta), ["PAR-1"])
        self.assertEqual(respuesta.context["tipo_actual"], str(self.tipo_parador.pk))

    def test_filtra_por_estado(self):
        respuesta = self.cliente.get(URL_LISTA, {"estado": Dispositivo.Estado.ACTIVO})

        self.assertEqual(self._filas(respuesta), ["PAR-1"])
        self.assertEqual(respuesta.context["estado_actual"], Dispositivo.Estado.ACTIVO)

    def test_filtra_por_localidad_sin_distinguir_mayusculas(self):
        respuesta = self.cliente.get(URL_LISTA, {"localidad": " resistencia "})

        self.assertEqual(self._filas(respuesta), ["PAR-1"])
        self.assertEqual(respuesta.context["localidad_actual"], "resistencia")

    def test_sin_coincidencias_el_vacio_ofrece_limpiar_y_no_habla_del_alcance(self):
        """El usuario filtró: decirle que no tiene alcance sería mentirle sobre por qué no ve nada."""

        respuesta = self.cliente.get(URL_LISTA, {"localidad": "Inexistente"})

        self.assertEqual(self._filas(respuesta), [])
        self.assertContains(respuesta, "Ningún dispositivo coincide con los filtros")
        self.assertContains(respuesta, "Limpiar filtros")
        self.assertContains(respuesta, URL_LISTA)  # la acción vuelve al listado sin filtros
        self.assertNotContains(respuesta, "No hay dispositivos en tu alcance")

    def test_sin_datos_y_sin_filtros_el_vacio_habla_del_alcance(self):
        Dispositivo.objects.all().delete()

        respuesta = self.cliente.get(URL_LISTA)

        self.assertContains(respuesta, "No hay dispositivos en tu alcance")
        # «Limpiar filtros» no sirve acá, y además lo trae el <template> del shell: lo que
        # se verifica es que la rama del vacío con filtros no se dibujó.
        self.assertNotContains(respuesta, "Ningún dispositivo coincide con los filtros")

    def test_la_exportacion_lleva_los_filtros_y_no_la_pagina(self):
        respuesta = self.cliente.get(URL_LISTA, {"localidad": "Resistencia", "page": 1})

        self.assertEqual(respuesta.context["exportar_qs"], "localidad=Resistencia")
        self.assertNotIn("page", respuesta.context["exportar_qs"])


class AlcanceTests(BaseListado):
    """La regla de visibilidad no la cambia ni la paginación ni los filtros."""

    def setUp(self):
        super().setUp()
        self.mio = self._dispositivo("MIO-1", "Hogar propio", localidad="Resistencia")
        self.ajenos = [self._dispositivo(f"AJE-{n:03d}", f"Ajeno {n}", localidad="Resistencia") for n in range(1, 30)]
        # Todo salvo la condición probada: el consultor tiene la capacidad de ver, lo
        # único que le falta es el alcance sobre los ajenos.
        self.consultor = self._usuario("consultor", ("dispositivo.ver",), [self.mio])

    def test_el_listado_es_exactamente_lo_visible(self):
        respuesta = self._cliente(self.consultor).get(URL_LISTA)

        self.assertEqual(self._filas(respuesta), ["MIO-1"])
        self.assertContains(respuesta, "Hogar propio")
        self.assertNotContains(respuesta, "Ajeno 1")

    def test_la_segunda_pagina_no_se_escapa_del_alcance(self):
        """Un alcance que se aplicara antes de paginar dejaría filas ajenas en la página 2."""

        for n in range(30, 60):
            AsignacionDispositivo.objects.create(
                dispositivo=self._dispositivo(f"MIO-{n:03d}", f"Propio {n}", localidad="Resistencia"),
                rol=self.consultor.groups.first(),
            )
        cache.clear()
        cliente = self._cliente(self.consultor)

        primera = self._filas(cliente.get(URL_LISTA))
        segunda = self._filas(cliente.get(URL_LISTA, {"page": 2}))

        self.assertEqual(len(primera) + len(segunda), 31)
        self.assertFalse([codigo for codigo in primera + segunda if codigo.startswith("AJE-")])

    def test_el_filtro_no_abre_una_puerta_al_alcance_ajeno(self):
        respuesta = self._cliente(self.consultor).get(URL_LISTA, {"localidad": "Resistencia"})

        self.assertEqual(self._filas(respuesta), ["MIO-1"])


class EncabezadoTests(BaseListado):
    """El encabezado de P2 sale del mockup: eyebrow «Programa Dispositivos» sobre el H1.

    P6 y P7 ya tenían su aserción; P2 no, y el eyebrow se podía borrar sin que nada
    fallara. Va contra el HTML que rinde `{% page_header %}`, no contra el contexto:
    lo que el mockup fija es lo que se ve arriba del título.
    """

    def test_el_encabezado_lleva_el_eyebrow_del_programa_sobre_el_titulo(self):
        respuesta = self._cliente(self._admin("encabezado")).get(URL_LISTA)

        self.assertContains(
            respuesta,
            '<p class="text-xs font-semibold uppercase tracking-wide text-fg-brand mb-1">Programa Dispositivos</p>',
            html=True,
        )


class AccionDeAltaTests(BaseListado):
    def setUp(self):
        super().setUp()
        self._dispositivo("INS-1", "Institución única", localidad="Resistencia")

    def test_con_la_capacidad_de_crear_y_alcance_de_admin_el_encabezado_ofrece_el_alta(self):
        usuario = self._admin("alta-si", "dispositivo.crear")

        respuesta = self._cliente(usuario).get(URL_LISTA)

        self.assertTrue(respuesta.context["puede_crear"])
        self.assertContains(respuesta, reverse("dispositivos:crear"))
        self.assertContains(respuesta, "Nueva institución")

    def test_con_la_capacidad_de_crear_pero_sin_alcance_de_admin_no_se_dibuja_el_alta(self):
        """El perfil que rompía: `dispositivo.crear` asignado a una institución concreta.

        Guardaba el borrador y el redirect a su propio legajo le daba 403, porque la
        institución nueva no tiene asignaciones. El botón no se ofrece y la vista tampoco.
        """

        institucion = self._dispositivo("INS-2", "Institución asignada", localidad="Resistencia")
        usuario = self._usuario(
            "alta-sin-alcance",
            ("dispositivo.ver", "dispositivo.crear", "dispositivo.editar"),
            alcance=[institucion],
        )
        cliente = self._cliente(usuario)

        respuesta = cliente.get(URL_LISTA)

        self.assertFalse(respuesta.context["puede_crear"])
        self.assertNotContains(respuesta, reverse("dispositivos:crear"))
        self.assertNotContains(respuesta, "Nueva institución")
        # Y el servidor cierra las dos puertas del alta, sin crear nada.
        self.assertEqual(cliente.get(reverse("dispositivos:crear")).status_code, 403)
        self.assertEqual(
            cliente.post(
                reverse("dispositivos:crear"), {"tipo": self.tipo_hogar.pk, "codigo": "X-1", "nombre": "X"}
            ).status_code,
            403,
        )
        self.assertFalse(Dispositivo.objects.filter(codigo="X-1").exists())
        self.assertEqual(cliente.get(reverse("dispositivos:buscar_duplicados"), {"codigo": "INS-1"}).status_code, 403)

    def test_sin_la_capacidad_de_crear_no_se_dibuja_el_alta(self):
        """Todo lo demás de Dispositivos —alcance de admin incluido— menos `dispositivo.crear`."""

        cliente = self._cliente(self._admin("alta-no", "dispositivo.editar", "dispositivo.validar"))

        respuesta = cliente.get(URL_LISTA)

        self.assertFalse(respuesta.context["puede_crear"])
        self.assertNotContains(respuesta, reverse("dispositivos:crear"))
        self.assertNotContains(respuesta, "Nueva institución")
        self.assertEqual(cliente.get(reverse("dispositivos:crear")).status_code, 403)

    def test_sin_la_capacidad_de_crear_el_estado_vacio_tampoco_la_ofrece(self):
        Dispositivo.objects.all().delete()
        usuario = self._usuario("alta-no-vacio", ("dispositivo.ver",))

        respuesta = self._cliente(usuario).get(URL_LISTA)

        self.assertContains(respuesta, "No hay dispositivos en tu alcance")
        self.assertEqual(respuesta.context["url_crear"], "")
        self.assertNotContains(respuesta, "Nueva institución")


class TensionDeOcupacionTests(TestCase):
    """El umbral que decide el color vive en el servicio, no en el template."""

    def test_sin_plazas_operativas_no_hay_porcentaje(self):
        tension = tension_de_ocupacion(Conteo(totales=0, ocupadas=0, reservadas=0))

        self.assertIsNone(tension.porcentaje)
        self.assertFalse(tension.hay_cifra)
        self.assertEqual(tension.texto, "sin plazas")
        self.assertEqual(tension.tono, "gray")

    def test_todas_fuera_de_servicio_tampoco_es_cero_por_ciento(self):
        tension = tension_de_ocupacion(Conteo(totales=8, fuera_de_servicio=8, ocupadas=0, reservadas=0))

        self.assertIsNone(tension.porcentaje)
        self.assertEqual(tension.texto, "sin plazas")

    def test_un_conteo_sin_la_cifra_de_ocupadas_no_inventa_un_cero(self):
        """`None` es «no se sabe»; dibujarlo como 0 % mandaría a alojar sobre plazas tomadas."""

        tension = tension_de_ocupacion(Conteo(totales=10))

        self.assertIsNone(tension.porcentaje)
        self.assertFalse(tension.hay_cifra)

    def test_los_tres_niveles_salen_de_los_umbrales(self):
        casos = {
            42: ("normal", "success"),
            59: ("normal", "success"),
            60: ("exigida", "warning"),
            79: ("exigida", "warning"),
            80: ("critica", "danger"),
            96: ("critica", "danger"),
        }
        for ocupadas, (nivel, tono) in casos.items():
            with self.subTest(ocupadas=ocupadas):
                tension = tension_de_ocupacion(Conteo(totales=100, ocupadas=ocupadas, reservadas=0))

                self.assertEqual(tension.porcentaje, ocupadas)
                self.assertEqual((tension.nivel, tension.tono), (nivel, tono))

    def test_el_texto_son_las_ocupadas_sobre_las_operativas_y_no_sobre_las_cargadas(self):
        tension = tension_de_ocupacion(Conteo(totales=50, fuera_de_servicio=8, ocupadas=37, reservadas=0))

        self.assertEqual(tension.texto, "37 / 42")
        self.assertEqual(tension.porcentaje, 88)


class PlazasEnLaFilaTests(BaseListado):
    def setUp(self):
        super().setUp()
        self.cis = self._dispositivo("CIS-003", "CIS N.º 3", localidad="Resistencia")
        self.vacio = self._dispositivo("ECA-SUR", "ECA Sur", localidad="Fontana")
        sector = Sector.objects.create(dispositivo=self.cis, nombre="Único")
        self.plazas = Plaza.objects.bulk_create(Plaza(sector=sector, codigo=f"P{n}") for n in range(1, 11))
        self.plazas = list(Plaza.objects.filter(sector=sector).order_by("codigo"))
        for n, plaza in enumerate(self.plazas[:9]):
            persona = Ciudadano.objects.create(nombre=f"Persona {n}", apellido="Prueba", dni=f"3000000{n}")
            Estadia.objects.create(
                ciudadano=persona,
                dispositivo=self.cis,
                plaza=plaza,
                fecha_ingreso=timezone.now(),
                clave_alojamiento=Estadia.clave_para(persona),
            )
        self.admin = self._admin("admin-plazas")

    def _por_codigo(self, respuesta):
        return {d.codigo: d.plazas for d in respuesta.context["dispositivos"]}

    def test_las_cifras_de_la_fila_salen_del_censo(self):
        respuesta = self._cliente(self.admin).get(URL_LISTA)

        plazas = self._por_codigo(respuesta)
        self.assertEqual(plazas["CIS-003"].texto, "9 / 10")
        self.assertEqual((plazas["CIS-003"].porcentaje, plazas["CIS-003"].tono), (90, "danger"))
        self.assertContains(respuesta, "9 / 10")
        self.assertContains(respuesta, '<span class="badge badge-dot badge-danger ml-1">90 %')

    def test_la_institucion_sin_plazas_lo_dice_y_no_muestra_cero_por_ciento(self):
        respuesta = self._cliente(self.admin).get(URL_LISTA)

        self.assertFalse(self._por_codigo(respuesta)["ECA-SUR"].hay_cifra)
        self.assertContains(respuesta, '<span class="text-body-subtle">sin plazas</span>')


@tag("performance")
class PresupuestoTests(BaseListado):
    """La página no puede hacer una consulta por fila: semáforo y plazas van en lote."""

    def setUp(self):
        super().setUp()
        self.admin = self._admin("admin-presupuesto", "dispositivo.crear")

    def _presupuesto(self):
        return json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]

    def _sembrar(self, desde, hasta):
        """Cada institución con su sector, sus plazas y su edificio relevado: el peor caso de la fila."""

        for n in range(desde, hasta):
            dispositivo = self._dispositivo(f"INS-{n:03d}", f"Institución {n}", localidad="Resistencia")
            sector = Sector.objects.create(dispositivo=dispositivo, nombre="Único")
            Plaza.objects.bulk_create(Plaza(sector=sector, codigo=f"P{i}") for i in range(1, 4))
            edificio = Edificio.objects.create(codigo=f"ED-{n:03d}", nombre=f"Edificio {n}")
            edificio.dispositivos.add(dispositivo)
            InspeccionEdificio.objects.create(
                edificio=edificio,
                asignado_a=self.admin,
                creado_por=self.admin,
                realizada_por=self.admin,
                realizada_en=timezone.now(),
                estado=InspeccionEdificio.Estado.REALIZADA,
                criticidad=InspeccionEdificio.Criticidad.ALTA,
                fecha_vencimiento=timezone.localdate(),
            )

    def _medir(self, cliente):
        with CaptureQueriesContext(connection) as medida:
            respuesta = cliente.get(URL_LISTA)
        self.assertEqual(respuesta.status_code, 200)
        return len(medida), len(respuesta.context["dispositivos"])

    def test_el_listado_cuesta_lo_mismo_con_dos_que_con_veinte(self):
        techo = self._presupuesto()["consultas_fijas"]
        cliente = self._cliente(self.admin)
        cliente.get(URL_LISTA)  # calienta la sesión y el cache del programa

        self._sembrar(0, 2)
        pocas, filas_pocas = self._medir(cliente)
        self._sembrar(2, 20)
        muchas, filas_muchas = self._medir(cliente)

        self.assertEqual((filas_pocas, filas_muchas), (2, 20))
        self.assertEqual(pocas, muchas, "El listado hace consultas por fila.")
        self.assertLessEqual(
            muchas,
            techo,
            f"{muchas} consultas; el presupuesto de «{CLAVE_PRESUPUESTO}» en scripts/perf_budgets.json es "
            f"{techo}. Subirlo exige justificarlo en el mismo PR.",
        )

    def test_la_pagina_no_paga_el_padron_entero(self):
        """Con 60 instituciones la página 1 sigue costando lo mismo que con 20: pagina."""

        self._sembrar(0, 20)
        cliente = self._cliente(self.admin)
        cliente.get(URL_LISTA)
        veinte, _ = self._medir(cliente)

        self._sembrar(20, 60)
        sesenta, filas = self._medir(cliente)

        self.assertEqual(filas, 25, "la página tiene que seguir siendo de 25")
        self.assertEqual(veinte, sesenta)
