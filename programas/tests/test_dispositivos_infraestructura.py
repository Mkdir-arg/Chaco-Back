"""Solapa Infraestructura del detalle (P19 recortada · #702) y semáforo edilicio (#705).

Lo que se fija acá, y por qué:

1. **La solapa la ve quien ve el dispositivo**, y nadie más: la guarda es la del detalle
   (``dispositivo.ver`` con alcance). Cada usuario que se rechaza tiene todo lo demás.
2. **El registro fotográfico es histórico**: cada relevamiento y cada carga de fotos es una
   entrada nueva; ninguna pisa a la anterior.
3. **Lo que no es del MVP no se dibuja**: tenencia, servicios, habitaciones, plano y
   vigencia no aparecen en el panel, ni siquiera vacíos.
4. **Las fotos se sirven detrás de login a quien ve el dispositivo** (200) y no a otra
   institución (403).
5. **El semáforo** sale de la última realizada, se entiende sin el color y distingue
   «sin relevar» de «relevado y sano»; un predio compartido muestra el mismo en todas sus
   instituciones, y el listado lo calcula sin una consulta por fila.
"""

import json
import re
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import Group
from django.db import connection
from django.test import Client, tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core import rbac
from programas.models import AsignacionDispositivo, Edificio, FotoInspeccion, InspeccionEdificio
from programas.services.detalle_dispositivo import infraestructura_del_dispositivo
from programas.services.inspecciones import (
    SEMAFOROS,
    SIN_EDIFICIO,
    SIN_RELEVAR,
    agregar_foto,
    crear_inspeccion,
    registrar_resultado,
    semaforos_de_dispositivos,
)
from programas.tests.test_dispositivos_inspecciones import TODAS_DE_DISPOSITIVOS, BaseInspecciones, _foto, _permiso
from users.models import RolMeta

PRESUPUESTOS = settings.BASE_DIR / "scripts" / "perf_budgets.json"
Criticidad = InspeccionEdificio.Criticidad

#: Lo que P19 tiene y el MVP no: ningún rastro en el panel (criterio de la task 37).
FUERA_DEL_MVP = (
    "Tenencia",
    "Servicios",
    "Habitaciones",
    "Plano",
    "Vigencia",
    "vencid",
    "Próximo vencimiento",
    "Relevar ya",
    "Comparar dos fechas",
)


def _panel(html):
    """El HTML del panel Infraestructura: del `id` del panel al del panel siguiente."""

    inicio = html.index('id="panel-infraestructura"')
    return html[inicio : html.index('id="panel-historial"', inicio)]


class BaseInfraestructura(BaseInspecciones):
    def setUp(self):
        super().setUp()
        self.admin = self._usuario("admin_programa", TODAS_DE_DISPOSITIVOS)

    def _relevar(self, edificio, criticidad, *, fotos=(), observaciones="", dias_atras=0):
        """Un relevamiento realizado de ``edificio``, con fecha ``dias_atras`` en el pasado."""

        inspeccion = crear_inspeccion(
            self._fresco(self.admin),
            edificio=edificio,
            asignado_a=self._fresco(self.agente),
            fecha_vencimiento=self.vence,
        )
        registrar_resultado(
            self._fresco(self.agente),
            inspeccion,
            criticidad=criticidad,
            observaciones=observaciones,
            fotos=[(_foto(f"{rotulo}.jpg"), rotulo) for rotulo in fotos],
        )
        if dias_atras:
            InspeccionEdificio.objects.filter(pk=inspeccion.pk).update(
                realizada_en=timezone.now() - timedelta(days=dias_atras)
            )
        inspeccion.refresh_from_db()
        return inspeccion

    def _cliente(self, usuario):
        """Un cliente por usuario: la sesión única del backoffice cierra la segunda que se abre."""

        clientes = self.__dict__.setdefault("_clientes", {})
        if usuario.pk not in clientes:
            cliente = Client()
            cliente.force_login(self._fresco(usuario))
            clientes[usuario.pk] = cliente
        return clientes[usuario.pk]

    def _detalle(self, usuario, dispositivo, **params):
        return self._cliente(usuario).get(reverse("dispositivos:detalle", args=[dispositivo.pk]), params)


class SolapaVisibleTests(BaseInfraestructura):
    def test_quien_ve_el_dispositivo_con_alcance_ve_la_solapa(self):
        respuesta = self._detalle(self.operador_geriatrico, self.geriatrico)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'id="tab-infraestructura"')
        self.assertContains(respuesta, 'id="panel-infraestructura"')

    def test_sin_dispositivo_ver_no_hay_solapa_aunque_tenga_todo_lo_demas(self):
        sin_ver = tuple(c for c in TODAS_DE_DISPOSITIVOS if c != "dispositivo.ver")
        usuario = self._usuario("todo_menos_ver", sin_ver, [self.geriatrico])

        self.assertEqual(self._detalle(usuario, self.geriatrico).status_code, 403)

    def test_sin_alcance_sobre_el_dispositivo_no_hay_solapa(self):
        """Todas las capacidades salvo la de admin del programa, asignado a otra institución."""

        sin_admin = tuple(c for c in TODAS_DE_DISPOSITIVOS if c != "programa.configurar")
        usuario = self._usuario("todo_menos_alcance", sin_admin, [self.cis])

        self.assertEqual(self._detalle(usuario, self.geriatrico).status_code, 403)

    def test_la_solapa_se_abre_por_la_url(self):
        respuesta = self._detalle(self.operador_geriatrico, self.geriatrico, tab="infraestructura")

        self.assertContains(respuesta, "tab: 'infraestructura'")
        self.assertContains(respuesta, 'aria-controls="panel-infraestructura"')


class HistorialFotograficoTests(BaseInfraestructura):
    def test_cada_relevamiento_es_una_entrada_y_ninguno_pisa_al_anterior(self):
        viejo = self._relevar(self.predio, Criticidad.BAJA, fotos=("fachada", "patio"), dias_atras=180)
        nuevo = self._relevar(self.predio, Criticidad.MEDIA, fotos=("fachada", "cocina", "techo"))

        infra = self._detalle(self.operador_geriatrico, self.geriatrico).context["infraestructura"]

        self.assertEqual([tanda["pk"] for tanda in infra["eventos"]], [nuevo.pk, viejo.pk])
        self.assertEqual([len(tanda["fotos"]) for tanda in infra["eventos"]], [3, 2])
        self.assertEqual([tanda["titulo"] for tanda in infra["eventos"]], ["3 fotos", "2 fotos"])
        self.assertEqual(infra["indicadores"][1]["valor"], 2)
        self.assertEqual(infra["indicadores"][2]["valor"], 5)

    def test_una_foto_cargada_despues_se_suma_a_su_tanda(self):
        inspeccion = self._relevar(self.predio, Criticidad.BAJA, fotos=("fachada",))
        agregar_foto(self._fresco(self.agente), inspeccion, _foto("tarde.jpg"), "patio")

        tanda = self._detalle(self.operador_geriatrico, self.geriatrico).context["infraestructura"]["eventos"][0]

        self.assertEqual([foto["rotulo"] for foto in tanda["fotos"]], ["fachada", "patio"])
        self.assertEqual(tanda["total_fotos"], 2)

    def test_el_html_dibuja_las_fotos_de_todas_las_tandas(self):
        self._relevar(self.predio, Criticidad.BAJA, fotos=("fachada",), dias_atras=90)
        self._relevar(self.predio, Criticidad.ALTA, fotos=("techo",), observaciones="Filtración en el techo")

        respuesta = self._detalle(self.operador_geriatrico, self.geriatrico)
        panel = _panel(respuesta.content.decode())

        for tanda in respuesta.context["infraestructura"]["eventos"]:
            for foto in tanda["fotos"]:
                self.assertIn(f'src="{foto["url"]}"', panel)
                self.assertIn('loading="lazy"', panel)
        self.assertIn("Filtración en el techo", panel)
        self.assertIn("Registro fotográfico", panel)

    def test_una_sola_linea_de_tiempo_con_las_fotos_dentro_de_cada_evento(self):
        """El riel es continuo (una `<ol>`) y cada galería vive dentro de su `<li>`, como en P19."""

        self._relevar(self.predio, Criticidad.BAJA, fotos=("fachada",), dias_atras=90)
        self._relevar(self.predio, Criticidad.ALTA, fotos=("techo", "cocina"))

        panel = _panel(self._detalle(self.operador_geriatrico, self.geriatrico).content.decode())
        riel = panel[panel.index('<h3 id="registro-fotografico-titulo"') :]

        self.assertEqual(riel.count("<ol "), 1)
        eventos = re.findall(
            r'<li class="relative pl-5 text-sm">(.*?)</li>\s*(?=<li class="relative|</ol>)', riel, re.S
        )
        self.assertEqual(len(eventos), 2)
        self.assertEqual([evento.count("<figure") for evento in eventos], [2, 1])

    def test_una_foto_heic_vieja_no_se_dibuja_rota(self):
        """El navegador no muestra HEIC en un `<img>`: va la celda gris con cámara, sin URL.

        Desde el rechazo de HEIC/HEIF (`core.validators.FOTO_EXTENSIONES`) ninguna nueva puede
        serlo, así que la fila se arma **sin pasar por el servicio**: es el caso de una foto que
        ya hubiera entrado antes. El manejo queda justamente por ellas.
        """

        inspeccion = self._relevar(self.predio, Criticidad.BAJA, fotos=("fachada",))
        heic = FotoInspeccion.objects.create(
            inspeccion=inspeccion,
            archivo=_foto("celular.heic", b"\x00\x00\x00\x18ftypheic" + b"0" * 16),
            descripcion="celular",
            cargada_por=self._fresco(self.agente),
        )
        self.assertTrue(heic.archivo.name.endswith(".heic"))

        respuesta = self._detalle(self.operador_geriatrico, self.geriatrico)
        fotos = respuesta.context["infraestructura"]["eventos"][0]["fotos"]
        panel = _panel(respuesta.content.decode())

        self.assertEqual(
            [(foto["rotulo"], bool(foto["url"])) for foto in fotos], [("fachada", True), ("celular", False)]
        )
        self.assertNotIn(heic.archivo.name, panel)
        self.assertIn("celular · Predio Resistencia", panel)
        self.assertIn("sin imagen", panel)

    def test_un_predio_compartido_muestra_el_mismo_relevamiento_en_sus_instituciones(self):
        inspeccion = self._relevar(self.predio, Criticidad.MEDIA, fotos=("fachada",))

        for usuario, dispositivo in ((self.operador_geriatrico, self.geriatrico), (self.admin, self.parador)):
            with self.subTest(dispositivo=dispositivo.nombre):
                respuesta = self._detalle(usuario, dispositivo)
                infra = respuesta.context["infraestructura"]
                self.assertEqual([tanda["pk"] for tanda in infra["eventos"]], [inspeccion.pk])
                self.assertIn("Predio compartido", _panel(respuesta.content.decode()))

    def test_sin_edificio_cargado_hay_un_estado_vacio_claro(self):
        respuesta = self._detalle(self.admin, self.sin_edificio)
        panel = _panel(respuesta.content.decode())

        self.assertIn("Este dispositivo no tiene edificio cargado", panel)
        self.assertNotIn("Registro fotográfico", panel)


class FueraDelMvpTests(BaseInfraestructura):
    def test_no_se_dibuja_ningun_bloque_de_lo_que_no_entra(self):
        self._relevar(self.predio, Criticidad.ALTA, fotos=("fachada",), observaciones="Techo con daños")

        panel = _panel(self._detalle(self.operador_geriatrico, self.geriatrico).content.decode())

        for texto in FUERA_DEL_MVP:
            with self.subTest(texto=texto):
                self.assertNotIn(texto.lower(), panel.lower())

    def test_tampoco_en_el_estado_sin_relevar_ni_sin_edificio(self):
        for dispositivo in (self.cis, self.sin_edificio):
            panel = _panel(self._detalle(self.admin, dispositivo).content.decode()).lower()
            for texto in FUERA_DEL_MVP:
                with self.subTest(dispositivo=dispositivo.nombre, texto=texto):
                    self.assertNotIn(texto.lower(), panel)


class FotosDetrasDeLoginTests(BaseInfraestructura):
    def setUp(self):
        super().setUp()
        self._relevar(self.predio, Criticidad.MEDIA, fotos=("fachada", "cocina"))

    def _urls(self, usuario, dispositivo):
        infra = self._detalle(usuario, dispositivo).context["infraestructura"]
        return [foto["url"] for tanda in infra["eventos"] for foto in tanda["fotos"]]

    def _estado(self, usuario, url):
        respuesta = self._cliente(usuario).get(url)
        if respuesta.streaming:
            b"".join(respuesta.streaming_content)
        return respuesta.status_code

    def test_quien_ve_el_dispositivo_ve_sus_fotos(self):
        """Solo `dispositivo.ver` asignado: ninguna capacidad de relevamientos."""

        urls = self._urls(self.operador_geriatrico, self.geriatrico)

        self.assertEqual(len(urls), 2)
        for url in urls:
            with self.subTest(url=url):
                self.assertTrue(url.startswith(settings.MEDIA_URL))
                self.assertEqual(self._estado(self.operador_geriatrico, url), 200)

    def test_el_admin_del_programa_tambien(self):
        for url in self._urls(self.admin, self.parador):
            self.assertEqual(self._estado(self.admin, url), 200)

    def test_otra_institucion_recibe_403(self):
        """Ve su propio dispositivo con todas las capacidades, salvo el alcance de admin."""

        sin_admin = tuple(c for c in TODAS_DE_DISPOSITIVOS if c not in ("programa.configurar", "inspeccion.asignar"))
        operador_cis = self._usuario("operador_cis", sin_admin, [self.cis])
        urls = self._urls(self.operador_geriatrico, self.geriatrico)

        self.assertEqual(self._detalle(operador_cis, self.cis).status_code, 200)
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self._estado(operador_cis, url), 403)

    def test_sin_sesion_no_se_sirve(self):
        url = self._urls(self.operador_geriatrico, self.geriatrico)[0]

        self.assertEqual(Client().get(url).status_code, 302)


class SemaforoTests(BaseInfraestructura):
    def test_cada_nivel_tiene_su_texto_y_su_tono(self):
        esperado = {
            Criticidad.ALTA: ("Crítico", "danger"),
            Criticidad.MEDIA: ("Regular", "warning"),
            Criticidad.BAJA: ("Bueno", "success"),
        }
        for criticidad, (texto, tono) in esperado.items():
            with self.subTest(criticidad=criticidad):
                edificio = Edificio.objects.create(codigo=f"ED-{criticidad}", nombre=f"Edificio {criticidad}")
                dispositivo = self._dispositivo(f"D-{criticidad}", f"Dispositivo {criticidad}")
                edificio.dispositivos.add(dispositivo)
                self._relevar(edificio, criticidad)

                semaforo = semaforos_de_dispositivos([dispositivo.pk])[dispositivo.pk]
                self.assertEqual((semaforo.nivel, semaforo.texto, semaforo.tono), (criticidad, texto, tono))

    def test_sin_relevar_no_es_lo_mismo_que_relevado_y_sano(self):
        self._relevar(self.predio, Criticidad.BAJA)
        # El edificio del CIS tiene un relevamiento EN CURSO: todavía no cuenta.
        crear_inspeccion(
            self._fresco(self.admin),
            edificio=self.edificio_cis,
            asignado_a=self._fresco(self.agente),
            fecha_vencimiento=self.vence,
        )

        semaforos = semaforos_de_dispositivos([self.parador.pk, self.cis.pk, self.sin_edificio.pk])

        self.assertEqual(semaforos[self.parador.pk].texto, "Bueno")
        self.assertEqual(semaforos[self.cis.pk].nivel, SIN_RELEVAR)
        self.assertEqual(semaforos[self.cis.pk].texto, "Sin relevar")
        self.assertEqual(semaforos[self.sin_edificio.pk].nivel, SIN_EDIFICIO)
        self.assertEqual(len({s.texto for s in semaforos.values()}), 3)

    def test_gana_la_ultima_realizada_no_la_peor_de_la_historia(self):
        self._relevar(self.predio, Criticidad.ALTA, dias_atras=200)
        self._relevar(self.predio, Criticidad.BAJA)

        self.assertEqual(semaforos_de_dispositivos([self.parador.pk])[self.parador.pk].texto, "Bueno")

    def test_un_predio_compartido_muestra_el_mismo_semaforo_en_sus_instituciones(self):
        self._relevar(self.predio, Criticidad.ALTA)

        semaforos = semaforos_de_dispositivos([self.parador.pk, self.geriatrico.pk])

        self.assertEqual(semaforos[self.parador.pk], semaforos[self.geriatrico.pk])
        self.assertEqual(semaforos[self.parador.pk].texto, "Crítico")

    def test_con_varios_edificios_gana_el_mas_grave_y_sin_relevar_le_gana_al_sano(self):
        self.edificio_cis.dispositivos.add(self.parador)  # el parador ocupa el predio y el edificio del CIS
        self._relevar(self.predio, Criticidad.BAJA)

        self.assertEqual(semaforos_de_dispositivos([self.parador.pk])[self.parador.pk].nivel, SIN_RELEVAR)

        self._relevar(self.edificio_cis, Criticidad.ALTA)
        self.assertEqual(semaforos_de_dispositivos([self.parador.pk])[self.parador.pk].texto, "Crítico")

    def test_el_estado_se_entiende_sin_el_color(self):
        """Cinco estados, cinco textos distintos: el tono solo refuerza (dos comparten el gris)."""

        textos = [semaforo.texto for semaforo in SEMAFOROS.values()]

        self.assertEqual(len(set(textos)), len(textos))
        self.assertTrue(all(texto.strip() for texto in textos))

    def test_el_detalle_lo_muestra_en_la_franja_y_por_edificio(self):
        self._relevar(self.predio, Criticidad.MEDIA, observaciones="Faltan dos duchas")

        respuesta = self._detalle(self.operador_geriatrico, self.geriatrico)
        infra = respuesta.context["infraestructura"]
        panel = _panel(respuesta.content.decode())

        self.assertEqual(infra["indicadores"][0]["etiqueta"], "Estado edilicio")
        self.assertEqual(infra["indicadores"][0]["valor"], "Regular")
        self.assertIn('<span class="badge badge-dot badge-warning">Regular</span>', panel)
        self.assertIn("Faltan dos duchas", panel)

    def test_se_ve_en_el_boton_de_la_solapa_sin_abrirla(self):
        """Con la solapa cerrada (abre en Estadías) el semáforo ya está en su botón, con texto."""

        self._relevar(self.predio, Criticidad.ALTA)

        html = self._detalle(self.operador_geriatrico, self.geriatrico).content.decode()
        inicio = html.index('id="tab-infraestructura"')
        boton = html[inicio : html.index("</button>", inicio)]

        self.assertIn("tab: 'estadias'", html, "la pantalla abre en Estadías")
        self.assertIn('<span class="badge badge-dot badge-danger">Crítico</span>', boton)

    def test_el_boton_de_la_solapa_distingue_sin_relevar_de_sin_edificio(self):
        for dispositivo, texto in ((self.cis, "Sin relevar"), (self.sin_edificio, "Sin edificio cargado")):
            with self.subTest(texto=texto):
                html = self._detalle(self.admin, dispositivo).content.decode()
                inicio = html.index('id="tab-infraestructura"')
                self.assertIn(f">{texto}</span>", html[inicio : html.index("</button>", inicio)])

    def test_la_bajada_del_edificio_sin_relevar_no_promete_observaciones(self):
        panel = _panel(self._detalle(self.admin, self.cis).content.decode())

        self.assertNotIn("criticidad y observaciones del último relevamiento", panel)
        self.assertIn("Todavía no se relevó este edificio", panel)

    def test_el_listado_lo_muestra_con_texto(self):
        self._relevar(self.predio, Criticidad.ALTA)

        respuesta = self._cliente(self.admin).get(reverse("dispositivos:lista"))
        por_pk = {d.pk: d.semaforo.texto for d in respuesta.context["dispositivos"]}

        self.assertEqual(por_pk[self.parador.pk], "Crítico")
        self.assertEqual(por_pk[self.cis.pk], "Sin relevar")
        self.assertEqual(por_pk[self.sin_edificio.pk], "Sin edificio cargado")
        self.assertContains(respuesta, '<span class="badge badge-dot badge-danger">Crítico</span>', count=2)
        self.assertContains(respuesta, '<span class="badge badge-dot badge-gray">Sin relevar</span>', count=1)


class ListadoSinNMasUnoTests(BaseInfraestructura):
    def _consultas(self):
        cliente = self._cliente(self.admin)
        cliente.get(reverse("dispositivos:lista"))  # calienta caches de permisos
        with CaptureQueriesContext(connection) as medida:
            self.assertEqual(cliente.get(reverse("dispositivos:lista")).status_code, 200)
        return len(medida)

    def test_las_consultas_no_crecen_con_los_dispositivos(self):
        self._relevar(self.predio, Criticidad.MEDIA)
        pocas = self._consultas()

        for n in range(6):
            edificio = Edificio.objects.create(codigo=f"ED-N{n}", nombre=f"Edificio {n}")
            edificio.dispositivos.add(self._dispositivo(f"N-{n}", f"Nuevo {n}"))
            self._relevar(edificio, Criticidad.ALTA)
        muchas = self._consultas()

        self.assertEqual(muchas, pocas, "una consulta por fila sería un N+1 en el listado")


@tag("performance")
class PresupuestosTests(BaseInfraestructura):
    def _techo(self, clave):
        return json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][clave]["consultas_fijas"]

    def test_el_semaforo_del_listado_cuesta_lo_mismo_con_uno_que_con_muchos(self):
        self._relevar(self.predio, Criticidad.MEDIA)
        with CaptureQueriesContext(connection) as uno:
            semaforos_de_dispositivos([self.parador.pk])

        ids = [self.parador.pk, self.geriatrico.pk, self.cis.pk, self.sin_edificio.pk]
        for n in range(8):
            edificio = Edificio.objects.create(codigo=f"ED-P{n}", nombre=f"Edificio P{n}")
            dispositivo = self._dispositivo(f"P-{n}", f"Perf {n}")
            edificio.dispositivos.add(dispositivo)
            self._relevar(edificio, Criticidad.BAJA)
            ids.append(dispositivo.pk)
        with CaptureQueriesContext(connection) as muchos:
            semaforos_de_dispositivos(ids)

        self.assertEqual(len(muchos), len(uno))
        self.assertLessEqual(len(muchos), self._techo("dispositivos_semaforo_edilicio"))

    def test_la_solapa_cuesta_lo_mismo_con_uno_que_con_muchos_relevamientos(self):
        self._relevar(self.predio, Criticidad.MEDIA, fotos=("fachada",))
        usuario = self._fresco(self.admin)
        rbac.puede(usuario, "dispositivo.ver", programa=self.programa)
        with CaptureQueriesContext(connection) as uno:
            infraestructura_del_dispositivo(self.parador, usuario=usuario)

        self.edificio_cis.dispositivos.add(self.parador)
        for dias in range(1, 7):
            self._relevar(self.predio, Criticidad.BAJA, fotos=("fachada", "patio", "techo"), dias_atras=dias)
        self._relevar(self.edificio_cis, Criticidad.ALTA, fotos=("cocina",))
        usuario = self._fresco(self.admin)
        rbac.puede(usuario, "dispositivo.ver", programa=self.programa)
        with CaptureQueriesContext(connection) as muchos:
            infra = infraestructura_del_dispositivo(self.parador, usuario=usuario)

        self.assertEqual(len(infra["eventos"]), 8)
        self.assertTrue(all(edificio["instituciones"] for edificio in infra["edificios"]))
        self.assertEqual(len(muchos), len(uno))
        self.assertLessEqual(len(muchos), self._techo("dispositivos_infraestructura"))


class RolSinAsignacionTests(BaseInfraestructura):
    """`dispositivo.ver` en un rol sin asignación más otro rol asignado sin `ver` no suman alcance."""

    def test_capacidad_y_asignacion_tienen_que_venir_del_mismo_rol(self):
        usuario = self._usuario("mixto", ("dispositivo.ver",))
        rol = Group.objects.create(name="Rol mixto asignado")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        rol.permissions.add(_permiso("dispositivo.admitir"))
        AsignacionDispositivo.objects.create(dispositivo=self.geriatrico, rol=rol, activo=True)
        usuario.groups.add(rol)

        self.assertEqual(self._detalle(usuario, self.geriatrico).status_code, 403)
