"""Solapa de Dispositivos del legajo ciudadano, reescrita contra la estadía (MVP v2, #693 · P16).

Esta suite afirmaba el comportamiento viejo: la solapa solo existía con una admisión
alojada, tiraba 403 sin ella, exigía la inscripción activa y se acotaba a los dispositivos
del usuario. Cada candado pasó a afirmar lo contrario (decisión §4.11 de la propuesta v2):

* la trayectoria completa —abiertas y cerradas, de cualquier institución— la ve todo el
  que es del programa; lo que limita es la sensibilidad de cada sección, no el alcance;
* es una vista de lectura;
* «ser del programa» es una capacidad con alcance al programa, nunca un nombre de grupo.
"""

from datetime import timedelta

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core import rbac
from legajos.models import Ciudadano
from programas.models import (
    Dispositivo,
    Estadia,
    InscripcionPrograma,
    MotivoEgreso,
    Plaza,
    Programa,
    Sector,
    TipoDispositivo,
)
from programas.selectors.trayectoria import POR_PAGINA, trayectoria_de
from programas.services.solapas import SolapasService
from users.models import Capacidad, RolMeta


def _permiso(codigo):
    tipo = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=tipo)


def _rol(nombre, capacidades, programa=None):
    grupo = Group.objects.create(name=nombre)
    RolMeta.objects.create(
        grupo=grupo,
        categoria=rbac.CATEGORIA_PROGRAMA if programa else rbac.CATEGORIA_SISTEMA,
        programa=programa,
        activo=True,
    )
    grupo.permissions.add(*[_permiso(c) for c in capacidades])
    return grupo


def _usuario(username, *roles):
    usuario = User.objects.create_user(username, password="Clave-Seg-2026x")
    usuario.groups.add(*roles)
    return usuario


class BaseSolapa(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        self.otro_programa = Programa.objects.create(codigo="BECAS", nombre="Becas")
        tipo = TipoDispositivo.objects.create(codigo="ALBERGUE", nombre="Albergue")
        self.cis = Dispositivo.objects.create(tipo=tipo, codigo="CIS-3", nombre="CIS N.º 3")
        self.parador = Dispositivo.objects.create(tipo=tipo, codigo="PAR-1", nombre="Parador Vedia")
        sector = Sector.objects.create(dispositivo=self.cis, nombre="Pabellón A", capacidad=4)
        self.plaza = Plaza.objects.create(sector=sector, codigo="A-02")
        self.persona = Ciudadano.objects.create(dni="39000100", nombre="Jorge", apellido="Ramírez")
        self.ahora = timezone.now()

    def estadia_cerrada(self, dispositivo, dias_ingreso=30, dias_egreso=10, motivo="", persona=None, observaciones=""):
        """`motivo` es el nombre del catálogo; `observaciones` el texto libre del egreso."""
        catalogo = (
            MotivoEgreso.objects.get_or_create(codigo=motivo.lower().replace(" ", "-"), defaults={"nombre": motivo})[0]
            if motivo
            else None
        )
        return Estadia.objects.create(
            ciudadano=persona or self.persona,
            dispositivo=dispositivo,
            fecha_ingreso=self.ahora - timedelta(days=dias_ingreso),
            fecha_egreso=self.ahora - timedelta(days=dias_egreso),
            estado=Estadia.Estado.EGRESADA,
            motivo=catalogo,
            motivo_egreso=observaciones,
        )

    def estadia_activa(self, dispositivo, plaza=None, persona=None):
        persona = persona or self.persona
        return Estadia.objects.create(
            ciudadano=persona,
            dispositivo=dispositivo,
            plaza=plaza,
            fecha_ingreso=self.ahora - timedelta(days=3),
            estado=Estadia.Estado.ACTIVA,
            clave_alojamiento=Estadia.clave_para(persona),
        )

    def url(self, persona=None):
        return reverse("legajos:dispositivos_ciudadano", args=[(persona or self.persona).pk])

    def del_programa(self, username="operador-programa"):
        """Del programa y con acceso al legajo: `dispositivo.ver` con alcance **y** `ciudadano.ver`, sin asignación."""
        return _usuario(username, _rol(f"Rol {username}", ["dispositivo.ver", "ciudadano.ver"], self.programa))


class SolapaSeOfreceTests(BaseSolapa):
    def test_la_solapa_sigue_ofrecida_despues_de_que_la_persona_egresa(self):
        """Candado 1: antes exigía una admisión **alojada**; la trayectoria existe aunque ya no esté."""
        self.estadia_cerrada(self.cis, motivo="Alta")

        solapas = SolapasService.obtener_solapas_ciudadano(self.persona, user=self.del_programa())

        solapa = next(s for s in solapas if s["id"] == "programa_DISPOSITIVOS")
        self.assertEqual(solapa["url"], self.url())
        self.assertEqual(solapa["badge"]["valor"], 1)

    def test_el_legajo_la_muestra_con_la_inscripcion_cerrada(self):
        """Candado 3: antes exigía la inscripción activa; la historia no se va cuando se cierra."""
        usuario = self.del_programa()
        InscripcionPrograma.objects.create(
            ciudadano=self.persona,
            programa=self.programa,
            responsable=usuario,
            estado=InscripcionPrograma.Estado.CERRADO,
        )
        self.estadia_cerrada(self.cis)

        solapas = SolapasService.obtener_solapas_ciudadano(self.persona, user=usuario)
        self.assertEqual([s["id"] for s in solapas].count("programa_DISPOSITIVOS"), 1)
        self.client.force_login(usuario)
        detalle = self.client.get(reverse("legajos:ciudadano_detalle", args=[self.persona.pk]))
        self.assertContains(detalle, self.url())

    def test_con_inscripcion_vigente_no_se_duplica(self):
        usuario = self.del_programa()
        InscripcionPrograma.objects.create(
            ciudadano=self.persona,
            programa=self.programa,
            responsable=usuario,
            estado=InscripcionPrograma.Estado.ACTIVO,
        )
        self.estadia_activa(self.cis, self.plaza)

        solapas = SolapasService.obtener_solapas_ciudadano(self.persona, user=usuario)

        self.assertEqual([s["id"] for s in solapas].count("programa_DISPOSITIVOS"), 1)

    def test_sin_estadias_no_hay_nada_que_ofrecer(self):
        solapas = SolapasService.obtener_solapas_ciudadano(self.persona, user=self.del_programa())

        self.assertNotIn("programa_DISPOSITIVOS", [s["id"] for s in solapas])

    def test_no_se_ofrece_a_quien_no_es_del_programa(self):
        self.estadia_cerrada(self.cis)
        de_becas = _usuario(
            "operador-becas", _rol("Rol becas", ["dispositivo.ver", "ciudadano.ver"], self.otro_programa)
        )

        for usuario in (de_becas, None):
            solapas = SolapasService.obtener_solapas_ciudadano(self.persona, user=usuario)
            self.assertNotIn("programa_DISPOSITIVOS", [s["id"] for s in solapas])


class PantallaTests(BaseSolapa):
    def test_muestra_la_trayectoria_completa_incluidas_las_cerradas_de_toda_la_red(self):
        """Sin filtro por alcance: el usuario no tiene asignado ni el CIS ni el parador y ve los dos."""
        self.estadia_cerrada(self.parador, 90, 60, motivo="Traslado")
        self.estadia_activa(self.cis, self.plaza)
        self.client.force_login(self.del_programa())

        respuesta = self.client.get(self.url())

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Parador Vedia")
        self.assertContains(respuesta, "Traslado")
        self.assertContains(respuesta, "Pabellón A · A-02")
        self.assertContains(respuesta, "Egresada")
        self.assertContains(respuesta, "Activa")
        self.assertContains(respuesta, "alojada en CIS N.º 3 (Pabellón A · A-02)")
        self.assertEqual(respuesta.context["n_estadias"], 2)

    def test_sin_estadias_es_una_trayectoria_vacia_no_un_403(self):
        """Candado 2: antes tiraba `PermissionDenied` sin admisión alojada."""
        self.client.force_login(self.del_programa())

        respuesta = self.client.get(self.url())

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Todavía no hay estadías registradas")
        self.assertContains(respuesta, "sin estadía activa en la red")

    def test_la_persona_egresada_sin_inscripcion_tambien_se_ve(self):
        self.estadia_cerrada(self.cis, motivo="Abandono")
        self.client.force_login(self.del_programa())

        respuesta = self.client.get(self.url())

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Abandono")

    def test_persona_inexistente_es_404(self):
        self.client.force_login(self.del_programa())

        self.assertEqual(self.client.get(reverse("legajos:dispositivos_ciudadano", args=[999999])).status_code, 404)

    def test_es_de_lectura_y_no_expone_campos_operativos(self):
        """Ni un botón operativo, ni las claves internas ni quién registró cada movimiento."""
        estadia = self.estadia_activa(self.cis, self.plaza)
        estadia.ingresada_por = self.del_programa("registrador-secreto-xyz")
        estadia.save(update_fields=["ingresada_por"])
        self.client.force_login(self.del_programa())

        respuesta = self.client.get(self.url())

        self.assertNotContains(respuesta, "CIU-")
        self.assertNotContains(respuesta, "registrador-secreto-xyz")
        self.assertNotContains(respuesta, "Egresar a la persona")
        # La lectura solo entrega la trayectoria: ni permisos ni URLs de operación
        # (cambiar plaza, trasladar, egresar), ni el modelo de la estadía.
        self.assertEqual(set(trayectoria_de(self.persona)), {"page_obj", "filas", "n_estadias", "hay_activa", "hoy"})
        # Ni dentro del `Page`: iterarlo en el template no puede dar instancias de Estadia.
        for item in trayectoria_de(self.persona)["page_obj"]:
            self.assertIsInstance(item, dict)
            self.assertNotIn("motivo_egreso", item)
            self.assertNotIn("clave_alojamiento", item)
        self.assertEqual(
            set(trayectoria_de(self.persona)["filas"][0]),
            {"dispositivo", "tipo", "ubicacion", "ingreso", "egreso", "estado", "tono", "motivo"},
        )

    def test_las_observaciones_del_egreso_no_van_en_la_trayectoria(self):
        """Son texto libre y pueden traer datos sensibles: se muestra el motivo del catálogo, no ellas."""
        self.estadia_cerrada(self.cis, motivo="Abandono", observaciones="Observacion-reservada-del-egreso-qwz")
        self.client.force_login(self.del_programa())

        respuesta = self.client.get(self.url())

        self.assertContains(respuesta, "Abandono")
        self.assertNotContains(respuesta, "Observacion-reservada-del-egreso-qwz")

    def test_el_enlace_al_legajo_esta_siempre(self):
        self.estadia_cerrada(self.cis)
        self.client.force_login(self.del_programa())

        self.assertEqual(
            self.client.get(self.url()).context["url_legajo"],
            reverse("legajos:ciudadano_detalle", args=[self.persona.pk]),
        )


class LegajoProgramasActivosTests(BaseSolapa):
    """El bloque «Programas activos» del legajo lee `badge.title` de cada solapa de programa."""

    def _solapa(self, usuario=None):
        solapas = SolapasService.obtener_solapas_ciudadano(self.persona, user=usuario or self.del_programa())
        return next(s for s in solapas if s["id"] == "programa_DISPOSITIVOS")

    def test_con_estadia_abierta_dice_alojada(self):
        self.estadia_activa(self.cis, self.plaza)

        self.assertEqual(self._solapa()["badge"]["title"], "Alojada")

    def test_con_solo_estadias_cerradas_no_dice_que_el_programa_sigue_activo(self):
        self.estadia_cerrada(self.cis)
        usuario = self.del_programa()
        self.client.force_login(usuario)

        self.assertEqual(self._solapa(usuario)["badge"]["title"], "Sin estadía activa")
        detalle = self.client.get(reverse("legajos:ciudadano_detalle", args=[self.persona.pk]))
        self.assertContains(detalle, "Sin estadía activa")


class QuienPuedeVerlaTests(BaseSolapa):
    def test_sin_capacidad_del_programa_es_403(self):
        """Pertenecer al programa sigue habilitando: sin `dispositivo.ver` no hay pantalla."""
        self.estadia_cerrada(self.cis)
        self.client.force_login(_usuario("sin-rol", _rol("Rol solo legajo 2", ["ciudadano.ver"])))

        self.assertEqual(self.client.get(self.url()).status_code, 403)

    def test_solo_dispositivo_ver_es_403_y_no_filtra_nombre_ni_dni(self):
        """Sin `ciudadano.ver` no se llega: la URL aparte no puede saltearse el control del legajo."""
        self.estadia_cerrada(self.cis)
        self.client.force_login(
            _usuario("solo-programa", _rol("Rol solo programa", ["dispositivo.ver"], self.programa))
        )

        respuesta = self.client.get(self.url())

        self.assertEqual(respuesta.status_code, 403)
        self.assertNotContains(respuesta, "Ramírez", status_code=403)
        self.assertNotContains(respuesta, "39000100", status_code=403)

    def test_solo_ciudadano_ver_tampoco_alcanza(self):
        self.estadia_cerrada(self.cis)
        self.client.force_login(_usuario("solo-legajo", _rol("Rol solo legajo", ["ciudadano.ver"])))

        self.assertEqual(self.client.get(self.url()).status_code, 403)

    def test_la_solapa_no_se_ofrece_sin_ciudadano_ver(self):
        self.estadia_cerrada(self.cis)
        usuario = _usuario("solapa-sin-legajo", _rol("Rol solapa sin legajo", ["dispositivo.ver"], self.programa))

        solapas = SolapasService.obtener_solapas_ciudadano(self.persona, user=usuario)

        self.assertNotIn("programa_DISPOSITIVOS", [s["id"] for s in solapas])

    def test_la_capacidad_de_otro_programa_no_alcanza(self):
        self.estadia_cerrada(self.cis)
        self.client.force_login(
            _usuario("de-becas", _rol("Rol becas", ["dispositivo.ver", "ciudadano.ver"], self.otro_programa))
        )

        self.assertEqual(self.client.get(self.url()).status_code, 403)

    def test_un_grupo_con_el_nombre_del_programa_no_habilita(self):
        """Se autoriza por capacidad, nunca por el nombre de un grupo."""
        self.estadia_cerrada(self.cis)
        usuario = _usuario("grupo-homonimo", _rol("Rol solo legajo 3", ["ciudadano.ver"]))
        usuario.groups.add(Group.objects.create(name="Dispositivos"))
        self.client.force_login(usuario)

        self.assertEqual(self.client.get(self.url()).status_code, 403)

    def test_un_rol_global_con_las_dos_capacidades_la_ve(self):
        """Decisión: un rol sin programa (`RolMeta.programa=None`) con las capacidades también habilita."""
        self.estadia_cerrada(self.cis)
        self.client.force_login(_usuario("global", _rol("Rol global", ["dispositivo.ver", "ciudadano.ver"])))

        self.assertEqual(self.client.get(self.url()).status_code, 200)

    def test_el_superusuario_la_ve(self):
        self.estadia_cerrada(self.cis)
        self.client.force_login(User.objects.create_superuser("admin-solapa", password="x"))

        self.assertEqual(self.client.get(self.url()).status_code, 200)

    def test_anonimo_va_al_login(self):
        self.assertEqual(self.client.get(self.url()).status_code, 302)


class TopeYConsultasTests(BaseSolapa):
    def _muchas(self, cantidad):
        for i in range(cantidad):
            self.estadia_cerrada(self.cis if i % 2 else self.parador, 400 - i * 10, 395 - i * 10)

    def test_la_trayectoria_se_pagina_y_el_contador_es_el_total(self):
        self._muchas(POR_PAGINA + 2)

        primera = trayectoria_de(self.persona)
        segunda = trayectoria_de(self.persona, 2)

        self.assertEqual(len(primera["filas"]), POR_PAGINA)
        self.assertEqual(len(segunda["filas"]), 2)
        self.assertEqual(primera["n_estadias"], POR_PAGINA + 2)

    def test_las_consultas_no_crecen_con_la_cantidad_de_estadias(self):
        self.estadia_activa(self.cis, self.plaza)
        self._muchas(2)
        with CaptureQueriesContext(connection) as pocas:
            trayectoria_de(self.persona)
        self._muchas(POR_PAGINA)
        with CaptureQueriesContext(connection) as muchas:
            trayectoria_de(self.persona)

        self.assertEqual(len(pocas), len(muchas))
        self.assertLessEqual(len(muchas), 3)

    def test_solo_cuenta_las_de_la_persona(self):
        otra = Ciudadano.objects.create(dni="39000101", nombre="Otra", apellido="Persona")
        self.estadia_cerrada(self.cis, persona=otra)

        self.assertEqual(trayectoria_de(self.persona)["n_estadias"], 0)
