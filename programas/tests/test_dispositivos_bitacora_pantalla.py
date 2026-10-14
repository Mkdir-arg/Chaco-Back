"""Pantalla «Bitácora del turno» (MVP v2, etapa 3 · #697 · P10).

Lo que se verifica, en el orden de los criterios de la task:

1. **Autorización**: ver (``dispositivo.ver`` con alcance), cargar y corregir
   (``dispositivo.bitacora`` con alcance) y configurar turnos (``dispositivo.editar`` con
   alcance), también desde otra institución. Cada usuario de prueba tiene **todo menos** la
   condición que el test aísla: si no, el 403 podría venir de otra capacidad faltante y la
   guarda probada quedaría vacía (la lección del Cambio 271).
2. **Sin pase de guardia**: no aparece ningún control.
3. **El censo que se muestra es el del servicio**: se parchean `censo_del_dia` y
   `ocupacion_de_plazas` con cifras inventadas y la pantalla tiene que mostrar esas, también
   el tramo que no cuadra, con texto.
4. **Versiones visibles**, **carga fuera de turno** con el error del servicio, **días
   anteriores sin controles de carga**, **privacidad de los nombres** y **las horas en la
   columna tabular de la pieza**.
5. **Presupuesto** de consultas (``--tag performance``).

El reloj está fijo: miércoles 09/09/2026 a las 16:00, en el turno Tarde del CIS.
"""

import json
import re
import shutil
import tempfile
from datetime import date, datetime, time, timedelta
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings, tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core import rbac
from legajos.models import Ciudadano
from programas.models import (
    AsignacionDispositivo,
    Dispositivo,
    EntradaBitacora,
    Estadia,
    Plaza,
    Programa,
    Sector,
    TipoDispositivo,
    Turno,
)
from programas.selectors.estadia_detalle import novedades_de_estadia
from programas.services.bitacora import corregir_entrada, registrar_entrada
from programas.services.bitacora_pantalla import pantalla_bitacora
from programas.services.censo import CERRADO, EN_CURSO, POR_VENIR, CensoDia, TramoCenso
from programas.services.estadias import ingresar_persona
from programas.services.ocupacion import Censo, Conteo, OcupacionDispositivo
from users.models import Capacidad, RolMeta

PRESUPUESTOS = settings.BASE_DIR / "scripts" / "perf_budgets.json"
CLAVE_PRESUPUESTO = "dispositivos_bitacora_turno"

MARTES = date(2026, 9, 8)
MIERCOLES = date(2026, 9, 9)

#: Todo lo que un operador del CIS puede tener. Cada test le saca exactamente una.
TODO = (
    "dispositivo.ver",
    "dispositivo.admitir",
    "dispositivo.egresar",
    "dispositivo.editar",
    "dispositivo.bitacora",
    "ciudadano.ver",
)

PDF = b"%PDF-1.4\n%prueba\n"

#: Las acciones de la tarjeta del turno: enlaces a esta misma pantalla que piden el modal por GET.
ENLACE_NOVEDAD = 'novedad=1"'
ENLACE_CORREGIR = 'corregir="'
AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


def _local(dia, hora, minuto=0):
    return timezone.make_aware(datetime.combine(dia, time(hora, minuto)))


AHORA = _local(MIERCOLES, 16)


def _reloj(momento=AHORA):
    return mock.patch("django.utils.timezone.now", return_value=momento)


def _permiso(codigo):
    tipo = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=tipo)


def _sin(*quitar):
    return tuple(codigo for codigo in TODO if codigo not in quitar)


class BasePantalla(TestCase):
    """Un programa, el CIS con sus tres turnos y dos personas alojadas, y un parador."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        ajuste = override_settings(MEDIA_ROOT=self.media)
        ajuste.enable()
        self.addCleanup(ajuste.disable)

        self.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        self.tipo = TipoDispositivo.objects.create(codigo="ALBERGUE", nombre="Albergue")
        self.cis = self._dispositivo("CIS-3", "CIS N.º 3")
        self.parador = self._dispositivo("PAR-1", "Parador")
        self.manana, self.tarde, self.noche = (
            Turno.objects.create(dispositivo=self.cis, nombre=nombre, hora_desde=time(d), hora_hasta=time(h), orden=o)
            for o, (nombre, d, h) in enumerate((("Mañana", 6, 14), ("Tarde", 14, 22), ("Noche", 22, 6)), 1)
        )
        self.turno_parador = Turno.objects.create(
            dispositivo=self.parador, nombre="Única", hora_desde=time(8), hora_hasta=time(8)
        )
        self.sector = Sector.objects.create(dispositivo=self.cis, nombre="Varones", capacidad=4)
        self.p1 = Plaza.objects.create(sector=self.sector, codigo="A-01")
        self.p2 = Plaza.objects.create(sector=self.sector, codigo="A-02")
        self.ana = Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Gómez")
        self.juan = Ciudadano.objects.create(dni="30333444", nombre="Juan", apellido="Pérez")
        self.operador = self._usuario("Operador CIS", self.cis)
        self.estadia_ana = self._ingresar(self.ana, self.p1, _local(MARTES, 10))
        self.estadia_juan = self._ingresar(self.juan, self.p2, _local(MIERCOLES, 15))
        self.url = reverse("dispositivos:bitacora", args=[self.cis.pk])

    def _dispositivo(self, codigo, nombre):
        return Dispositivo.objects.create(
            tipo=self.tipo, codigo=codigo, nombre=nombre, estado=Dispositivo.Estado.ACTIVO
        )

    def _usuario(self, nombre, dispositivo, capacidades=TODO):
        rol = Group.objects.create(name=nombre)
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        rol.permissions.add(*[_permiso(codigo) for codigo in capacidades])
        AsignacionDispositivo.objects.create(dispositivo=dispositivo, rol=rol, activo=True)
        usuario = User.objects.create_user(
            username=nombre.replace(" ", "_").lower(), password="x", first_name="Lucía", last_name="Méndez"
        )
        usuario.groups.add(rol)
        return User.objects.get(pk=usuario.pk)

    def _ingresar(self, persona, plaza, momento):
        with _reloj():
            return ingresar_persona(
                ciudadano=persona, dispositivo=self.cis, plaza=plaza, usuario=self.operador, fecha_ingreso=momento
            )

    def _cargar(self, momento, texto="Discusión en el comedor, sin lesiones.", **kwargs):
        datos = {
            "dispositivo": self.cis,
            "usuario": self.operador,
            "tipo": EntradaBitacora.Tipo.INCIDENTE,
            "texto": texto,
            "momento": momento,
        }
        datos.update(kwargs)
        with _reloj(momento):
            return registrar_entrada(**datos)

    def _get(self, usuario=None, **params):
        self.client.force_login(usuario or self.operador)
        with _reloj():
            return self.client.get(self.url, params)

    def _post(self, nombre, datos, usuario=None, ajax=True):
        self.client.force_login(usuario or self.operador)
        with _reloj():
            return self.client.post(
                reverse(f"dispositivos:{nombre}", args=[self.cis.pk]), datos, **(AJAX if ajax else {})
            )

    def _html(self, respuesta):
        return respuesta.content.decode()

    def _manuales(self):
        """Las novedades que carga un operador.

        Los dos ingresos del terreno dejan su novedad automática (Cambio NNN): contar
        `EntradaBitacora.objects` entero mezclaría las dos cosas.
        """

        return EntradaBitacora.objects.filter(origen=EntradaBitacora.Origen.MANUAL)


class VerTests(BasePantalla):
    def test_con_ver_y_alcance_se_ve(self):
        respuesta = self._get(self._usuario("Solo lectura", self.cis, ("dispositivo.ver",)))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Bitácora")
        self.assertContains(respuesta, "Turno Tarde · entradas")

    def test_se_llega_desde_el_encabezado_de_p4(self):
        """La bitácora pide lo mismo que P4: quien ve el dispositivo tiene el botón."""

        usuario = self._usuario("Solo lectura", self.cis, ("dispositivo.ver",))
        self.client.force_login(usuario)
        with _reloj():
            respuesta = self.client.get(reverse("dispositivos:detalle", args=[self.cis.pk]))

        self.assertContains(respuesta, f'href="{self.url}"')
        self.assertContains(respuesta, "Bitácora del turno")

    def test_sin_dispositivo_ver_es_403(self):
        respuesta = self._get(self._usuario("Sin ver", self.cis, _sin("dispositivo.ver")))

        self.assertEqual(respuesta.status_code, 403)

    def test_otra_institucion_es_403(self):
        """Con todas las capacidades, pero asignado al parador: el CIS no es suyo."""

        respuesta = self._get(self._usuario("Operador parador", self.parador))

        self.assertEqual(respuesta.status_code, 403)

    def test_anonimo_va_al_login(self):
        with _reloj():
            respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 302)


class CargarTests(BasePantalla):
    def test_con_bitacora_se_ofrece_en_el_turno_en_curso_y_carga(self):
        respuesta = self._get()

        self.assertContains(respuesta, ENLACE_NOVEDAD)
        self.assertContains(respuesta, reverse("dispositivos:bitacora_novedad", args=[self.cis.pk]))

        respuesta = self._post(
            "bitacora_novedad",
            {"tipo": "INCIDENTE", "texto": "Discusión en el comedor.", "personas": [self.estadia_ana.pk]},
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        entrada = self._manuales().get()
        self.assertEqual(entrada.turno, self.tarde)
        self.assertEqual(entrada.fecha_operativa, MIERCOLES)
        self.assertEqual(list(entrada.personas.all()), [self.estadia_ana])

    def test_carga_con_adjunto(self):
        archivo = SimpleUploadedFile("acta.pdf", PDF, content_type="application/pdf")

        respuesta = self._post("bitacora_novedad", {"tipo": "GENERAL", "texto": "Acta.", "adjuntos": [archivo]})

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(self._manuales().get().adjuntos.count(), 1)
        self.assertContains(self._get(), "Adjuntos del turno")

    def test_sin_bitacora_no_se_ofrece_ni_se_carga(self):
        usuario = self._usuario("Sin bitacora", self.cis, _sin("dispositivo.bitacora"))

        respuesta = self._get(usuario)
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, ENLACE_NOVEDAD)
        self.assertNotContains(respuesta, reverse("dispositivos:bitacora_novedad", args=[self.cis.pk]))

        respuesta = self._post("bitacora_novedad", {"tipo": "GENERAL", "texto": "Algo."}, usuario)
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(self._manuales().exists())

    def test_otra_institucion_no_carga(self):
        """Con `dispositivo.bitacora` en el programa, pero asignado al parador: lo frena el servicio."""

        respuesta = self._post(
            "bitacora_novedad", {"tipo": "GENERAL", "texto": "Algo."}, self._usuario("De otro", self.parador)
        )

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(self._manuales().exists())

    def test_fuera_del_turno_en_curso_muestra_el_error_del_servicio(self):
        """La vista no repite la regla: el mensaje es el de `registrar_entrada`."""

        respuesta = self._post(
            "bitacora_novedad", {"tipo": "GENERAL", "texto": "De la mañana.", "momento": "2026-09-09T10:00"}
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn(
            "Solo se cargan y corrigen novedades del turno en curso", " ".join(respuesta.json()["errors"]["momento"])
        )
        self.assertFalse(self._manuales().exists())

    def test_fuera_del_turno_sin_ajax_vuelve_con_el_aviso(self):
        self.client.force_login(self.operador)
        with _reloj():
            respuesta = self.client.post(
                reverse("dispositivos:bitacora_novedad", args=[self.cis.pk]),
                {"tipo": "GENERAL", "texto": "De la mañana.", "momento": "2026-09-09T10:00"},
                follow=True,
            )

        self.assertContains(respuesta, "Solo se cargan y corrigen novedades del turno en curso")

    def test_un_tipo_automatico_no_se_carga_a_mano(self):
        respuesta = self._post("bitacora_novedad", {"tipo": "INGRESO", "texto": "Ingresó alguien."})

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("tipo", respuesta.json()["errors"])


class CorregirTests(BasePantalla):
    def setUp(self):
        super().setUp()
        self.entrada = self._cargar(_local(MIERCOLES, 15, 30), texto="Discusion en comedor.")

    def test_corregir_agrega_una_version_y_la_anterior_sigue_visible(self):
        respuesta = self._get()
        self.assertContains(respuesta, ENLACE_CORREGIR)

        respuesta = self._post(
            "bitacora_corregir",
            {"entrada": self.entrada.pk, "tipo": "INCIDENTE", "texto": "Discusión en el comedor.", "motivo": "Tilde"},
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.content)

        html = self._html(self._get())
        self.assertIn("Discusión en el comedor.", html)
        self.assertIn("Versión 2", html)
        self.assertIn("Versiones anteriores", html)
        self.assertIn("Versión 1, reemplazada.", html)
        self.assertIn("Discusion en comedor.", html)
        self.assertEqual(self._manuales().count(), 2)

    def test_sin_bitacora_no_corrige(self):
        usuario = self._usuario("Sin bitacora", self.cis, _sin("dispositivo.bitacora"))

        self.assertNotContains(self._get(usuario), ENLACE_CORREGIR)
        respuesta = self._post(
            "bitacora_corregir", {"entrada": self.entrada.pk, "tipo": "INCIDENTE", "texto": "Otra cosa."}, usuario
        )

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self._manuales().count(), 1)

    def test_la_entrada_de_otro_dispositivo_no_se_corrige_desde_aca(self):
        operador_parador = self._usuario("Operador parador", self.parador)
        with _reloj():
            ajena = registrar_entrada(
                dispositivo=self.parador, usuario=operador_parador, tipo="GENERAL", texto="Del parador."
            )

        respuesta = self._post("bitacora_corregir", {"entrada": ajena.pk, "tipo": "GENERAL", "texto": "Pisada."})

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("no es de este dispositivo", " ".join(respuesta.json()["errors"]["entrada"]))
        self.assertEqual(self._manuales().filter(dispositivo=self.parador).count(), 1)

    def test_una_entrada_de_un_turno_terminado_no_se_corrige(self):
        """Más tarde, en la Noche: el error es el del servicio."""

        self.client.force_login(self.operador)
        with _reloj(_local(MIERCOLES, 23)):
            respuesta = self.client.post(
                reverse("dispositivos:bitacora_corregir", args=[self.cis.pk]),
                {"entrada": self.entrada.pk, "tipo": "INCIDENTE", "texto": "Tarde."},
                **AJAX,
            )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("Solo se corrigen novedades del turno en curso", " ".join(respuesta.json()["errors"]["entrada"]))


class TurnosTests(BasePantalla):
    def _datos(self, **extra):
        datos = {"nombre": "Guardia", "hora_desde": "08:00", "hora_hasta": "08:00", "orden": "4"}
        datos.update(extra)
        return datos

    def test_con_editar_se_ofrece_y_se_crea(self):
        sin_turnos = self._dispositivo("CIS-4", "CIS N.º 4")
        usuario = self._usuario("Editor CIS 4", sin_turnos)
        self.client.force_login(usuario)
        with _reloj():
            respuesta = self.client.get(reverse("dispositivos:bitacora", args=[sin_turnos.pk]))
            self.assertContains(respuesta, "Configurar turnos")
            self.assertContains(respuesta, "no tiene turnos configurados")
            respuesta = self.client.post(
                reverse("dispositivos:bitacora_turnos", args=[sin_turnos.pk]), self._datos(), **AJAX
            )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertTrue(Turno.objects.filter(dispositivo=sin_turnos, nombre="Guardia").exists())

    def test_editar_un_turno(self):
        respuesta = self._post(
            "bitacora_turnos",
            {"turno": self.noche.pk, "nombre": "Noche", "hora_desde": "22:00", "hora_hasta": "06:00", "orden": "3"},
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.noche.refresh_from_db()
        self.assertFalse(self.noche.activo, "Sin «activo» tildado, la edición lo da de baja")

    def test_la_superposicion_muestra_el_error_del_servicio(self):
        respuesta = self._post("bitacora_turnos", self._datos(hora_desde="12:00", hora_hasta="15:00"))

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("se superpone", " ".join(respuesta.json()["errors"]["hora_desde"]))

    def test_sin_editar_no_se_ofrece_ni_se_configura(self):
        usuario = self._usuario("Sin editar", self.cis, _sin("dispositivo.editar"))

        self.assertNotContains(self._get(usuario), "Configurar turnos")
        respuesta = self._post("bitacora_turnos", self._datos(), usuario)

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Turno.objects.filter(nombre="Guardia").exists())

    def test_otra_institucion_no_configura(self):
        respuesta = self._post("bitacora_turnos", self._datos(), self._usuario("Del parador", self.parador))

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Turno.objects.filter(nombre="Guardia").exists())

    def test_el_turno_de_otro_dispositivo_no_se_edita_desde_aca(self):
        respuesta = self._post("bitacora_turnos", self._datos(turno=self.turno_parador.pk))

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("no es de este dispositivo", " ".join(respuesta.json()["errors"]["turno"]))
        self.turno_parador.refresh_from_db()
        self.assertEqual(self.turno_parador.nombre, "Única")


class SinPaseDeGuardiaTests(BasePantalla):
    def test_no_aparece_ningun_control_de_pase_de_guardia(self):
        self._cargar(_local(MIERCOLES, 15))
        html = self._html(self._get()).lower()

        for texto in ("pase de guardia", "cerrar turno", "recibe", "pendientes para el turno", "pase"):
            self.assertNotIn(texto, html, f"«{texto}» no tiene que aparecer: el pase de guardia no se construye")
        self.assertNotIn("pase", " ".join(name for name in _nombres_de_ruta()))


def _nombres_de_ruta():
    from programas import dispositivos_urls

    return [patron.name or "" for patron in dispositivos_urls.urlpatterns]


def _dd(html, etiqueta):
    """El valor de la fila del censo con esa etiqueta."""

    encontrado = re.search(r"<dt[^>]*>" + re.escape(etiqueta) + r"</dt>\s*<dd[^>]*>([^<]*)</dd>", html)
    return encontrado.group(1).strip() if encontrado else None


class CensoTests(BasePantalla):
    def _censo_inventado(self, *, cuadra_tarde=True):
        tramos = []
        cifras = {
            self.manana.pk: (CERRADO, 30, 4, 1, 33),
            self.tarde.pk: (EN_CURSO, 41, 7, 3, 45 if cuadra_tarde else 47),
            self.noche.pk: (POR_VENIR, 45, 0, 0, 45),
        }
        for turno in (self.manana, self.tarde, self.noche):
            estado, inicial, ingresos, egresos, al_fin = cifras[turno.pk]
            inicio, fin = turno.ventana(MIERCOLES)
            tramos.append(
                TramoCenso(
                    turno=turno,
                    nombre=turno.nombre,
                    inicio=inicio,
                    fin=fin,
                    inicial=inicial,
                    ingresos=ingresos,
                    egresos=egresos,
                    alojadas_al_fin=al_fin,
                    estado=estado,
                )
            )
        return CensoDia(dispositivo_id=self.cis.pk, fecha_operativa=MIERCOLES, tramos=tuple(tramos), con_turnos=True)

    def _plazas_inventadas(self):
        conteo = Conteo(totales=44, fuera_de_servicio=2, ocupadas=37, reservadas=2)
        return Censo(
            por_dispositivo={self.cis.pk: OcupacionDispositivo(dispositivo_id=self.cis.pk, conteo=conteo, sectores=())},
            total=conteo,
        )

    def _pantalla(self, censo):
        with (
            mock.patch("programas.services.bitacora_pantalla.censo_servicio.censo_del_dia", return_value=censo),
            mock.patch(
                "programas.services.bitacora_pantalla.ocupacion_de_plazas", return_value=self._plazas_inventadas()
            ),
        ):
            return self._html(self._get())

    def test_muestra_las_cifras_del_servicio_y_no_un_conteo_propio(self):
        html = self._pantalla(self._censo_inventado())

        self.assertEqual(_dd(html, "Al inicio del turno · 14:00"), "41")
        self.assertEqual(_dd(html, "Ingresos del turno"), "7")
        self.assertEqual(_dd(html, "Egresos del turno"), "3")
        self.assertEqual(_dd(html, "Alojadas ahora"), "45")
        self.assertEqual(_dd(html, "Ingresos del día"), "11")
        self.assertEqual(_dd(html, "Egresos del día"), "4")
        self.assertEqual(_dd(html, "Plazas totales / operativas"), "44 / 42")
        self.assertEqual(_dd(html, "Reservadas o prestadas"), "2")
        self.assertEqual(_dd(html, "Disponibles"), "3")
        self.assertIn("Calculado", html)
        self.assertNotIn("El censo no cuadra", html)
        self.assertIn("30 al inicio · 33 al cierre", html, "la tarjeta del turno cerrado también lee el censo")

    def test_el_orden_es_el_del_mockup_y_solo_disponibles_va_en_negrita(self):
        html = self._pantalla(self._censo_inventado())
        orden = [
            "Plazas totales / operativas",
            "Al inicio del turno · 14:00",
            "Ingresos del día",
            "Alojadas ahora",
            "Reservadas o prestadas",
            "Disponibles",
        ]
        posiciones = [html.index(f">{etiqueta}</dt>") for etiqueta in orden]

        self.assertEqual(posiciones, sorted(posiciones))
        negritas = re.findall(r"<dt[^>]*>([^<]*)</dt>\s*<dd[^>]*font-bold", html)
        self.assertEqual(negritas, ["Disponibles"])

    def test_un_tramo_que_no_cuadra_se_dice_con_texto(self):
        html = self._pantalla(self._censo_inventado(cuadra_tarde=False))

        self.assertEqual(_dd(html, "Alojadas ahora"), "47 según estadías · 45 según movimientos")
        self.assertIn("El censo no cuadra.", html)
        self.assertIn("Tarde: las estadías registran 2 personas más que los ingresos y egresos", html)
        self.assertIn("el censo no cuadra", html, "la tarjeta del turno también lo dice")

    def test_las_plazas_solo_se_muestran_hoy(self):
        """Son la foto de ahora: en un día anterior serían una mentira."""

        html = self._html(self._get(fecha="2026-09-08"))

        self.assertIsNone(_dd(html, "Disponibles"))
        self.assertIsNotNone(_dd(html, "Ingresos del día"))

    def test_sin_parchear_coincide_con_el_censo_real(self):
        """Juan ingresó a las 15:00 del miércoles: un ingreso en la Tarde, y dos alojadas ahora."""

        html = self._html(self._get())

        self.assertEqual(_dd(html, "Al inicio del turno · 14:00"), "1")
        self.assertEqual(_dd(html, "Ingresos del turno"), "1")
        self.assertEqual(_dd(html, "Alojadas ahora"), "2")


class VersionesYDiasAnterioresTests(BasePantalla):
    def test_dia_anterior_sin_controles_de_carga(self):
        with _reloj(_local(MARTES, 10)):
            registrar_entrada(dispositivo=self.cis, usuario=self.operador, tipo="SALUD", texto="Control de presión.")

        html = self._html(self._get(fecha="2026-09-08"))

        self.assertIn("Control de presión.", html)
        self.assertIn("Día anterior, solo lectura.", html)
        for control in (
            ENLACE_NOVEDAD,
            ENLACE_CORREGIR,
            reverse("dispositivos:bitacora_novedad", args=[self.cis.pk]),
            reverse("dispositivos:bitacora_corregir", args=[self.cis.pk]),
        ):
            self.assertNotIn(control, html)

    def test_una_fecha_futura_es_hoy(self):
        html = self._html(self._get(fecha="2030-01-01"))

        self.assertIn(ENLACE_NOVEDAD, html)
        self.assertNotIn("Día anterior, solo lectura.", html)

    def test_las_horas_van_en_la_columna_tabular_de_la_pieza(self):
        for hora, minuto in ((14, 5), (15, 30), (16, 0)):
            self._cargar(_local(MIERCOLES, hora, minuto), texto=f"Novedad {hora}:{minuto:02d}")

        html = self._html(self._get())
        horas = re.findall(r'<span class="w-12 flex-shrink-0 tabular-nums text-body-subtle">([^<]*)</span>', html)

        # 15:00 es la novedad automática del ingreso de Juan, que cae en este mismo turno.
        self.assertEqual(horas, ["16:00", "15:30", "15:00", "14:05"])


class PrivacidadTests(BasePantalla):
    def setUp(self):
        super().setUp()
        self._cargar(_local(MIERCOLES, 15, 30), personas=[self.estadia_ana])

    def test_con_ciudadano_ver_se_nombra(self):
        html = self._html(self._get())

        self.assertIn("Personas: Gómez, Ana", html)

    def test_sin_ciudadano_ver_no_se_nombra_ni_se_ofrece(self):
        usuario = self._usuario("Sin legajo", self.cis, _sin("ciudadano.ver"))

        html = self._html(self._get(usuario))

        self.assertIn("Personas involucradas: 1", html)
        for dato in ("Gómez", "Pérez", "30111222", "30333444"):
            self.assertNotIn(dato, html)

    def test_sin_ciudadano_ver_no_se_vinculan_personas(self):
        usuario = self._usuario("Sin legajo", self.cis, _sin("ciudadano.ver"))

        respuesta = self._post(
            "bitacora_novedad", {"tipo": "GENERAL", "texto": "Algo.", "personas": [self.estadia_juan.pk]}, usuario
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertFalse(EntradaBitacora.objects.get(texto="Algo.").personas.exists())


@tag("performance")
class PresupuestoTests(BasePantalla):
    """La pantalla no hace una consulta por entrada, persona ni adjunto."""

    def _presupuesto(self):
        return json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]

    def _cargar_muchas(self, cuantas):
        for n in range(cuantas):
            archivo = SimpleUploadedFile(f"acta{n}.pdf", PDF, content_type="application/pdf")
            entrada = self._cargar(
                _local(MIERCOLES, 14, n % 60) + timedelta(seconds=n),
                texto=f"Novedad {n}",
                personas=[self.estadia_ana],
                adjuntos=[archivo],
            )
            if n % 3 == 0:
                with _reloj():
                    corregir_entrada(entrada=entrada, usuario=self.operador, texto=f"Novedad {n} corregida")

    def _medir_servicio(self):
        with _reloj(), CaptureQueriesContext(connection) as consultas:
            pantalla_bitacora(
                self.cis, puede_cargar=True, puede_configurar=True, nombrar_personas=True, url_base=self.url
            )
        return len(consultas)

    def test_el_servicio_entra_en_el_presupuesto_y_no_crece(self):
        techo = self._presupuesto()["consultas_fijas"]
        self._cargar_muchas(1)
        con_una = self._medir_servicio()
        self._cargar_muchas(20)
        con_veinte = self._medir_servicio()

        self.assertLessEqual(
            con_veinte,
            techo,
            f"{con_veinte} consultas; el presupuesto de «{CLAVE_PRESUPUESTO}» en scripts/perf_budgets.json es "
            f"{techo}. Subirlo exige justificarlo en el mismo PR.",
        )
        self.assertEqual(con_una, con_veinte, "una consulta por entrada, persona o adjunto")

    def test_la_vista_no_crece_con_las_entradas(self):
        self._cargar_muchas(1)
        self.client.force_login(self.operador)
        with _reloj():
            self.client.get(self.url)  # la primera pide de más por la sesión: no es de la pantalla
        with _reloj(), CaptureQueriesContext(connection) as con_una:
            self.client.get(self.url)
        self._cargar_muchas(20)
        with _reloj(), CaptureQueriesContext(connection) as con_veinte:
            self.client.get(self.url)

        self.assertEqual(len(con_una), len(con_veinte))

    def test_un_turno_dado_de_baja_con_novedades_suma_una_sola_consulta(self):
        """El peor caso del techo: hoy, con todo, y con novedades de un turno que se dio de baja."""

        techo = self._presupuesto()["consultas_fijas"]
        self._cargar_muchas(3)
        with _reloj(_local(MIERCOLES, 10)):
            registrar_entrada(dispositivo=self.cis, usuario=self.operador, tipo="GENERAL", texto="De la mañana.")
        sin_baja = self._medir_servicio()
        self.manana.activo = False
        self.manana.save()
        con_baja = self._medir_servicio()

        self.assertEqual(con_baja, sin_baja + 1)
        self.assertLessEqual(con_baja, techo)


class TurnoDadoDeBajaTests(BasePantalla):
    def test_sus_novedades_de_un_dia_anterior_siguen_visibles(self):
        with _reloj(_local(MARTES, 10)):
            registrar_entrada(dispositivo=self.cis, usuario=self.operador, tipo="SALUD", texto="Control del martes.")
        self.manana.activo = False
        self.manana.save()

        html = self._html(self._get(fecha="2026-09-08"))

        self.assertIn("Control del martes.", html)
        self.assertIn("Dado de baja", html)
        self.assertIn("Turno Mañana · entradas", html)
        self.assertIn("no tiene censo propio", html)

    def test_se_puede_elegir_con_ver(self):
        with _reloj(_local(MIERCOLES, 10)):
            registrar_entrada(dispositivo=self.cis, usuario=self.operador, tipo="SALUD", texto="De la mañana.")
        self.manana.activo = False
        self.manana.save()

        html = self._html(self._get(turno=self.manana.pk))

        self.assertIn("De la mañana.", html)
        self.assertIn("Turno Mañana · entradas · no es el turno en curso (ahora, Tarde)", html)


class FechaYEleccionTests(BasePantalla):
    def test_una_fecha_absurda_no_rompe(self):
        for fecha in ("0001-01-01", "1999-12-31"):
            with self.subTest(fecha=fecha):
                respuesta = self._get(fecha=fecha)

                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(respuesta.context["fecha"], date(2020, 1, 1))
                self.assertIsNone(respuesta.context["dia_anterior"])

    def test_el_turno_elegido_con_ver_lo_dice_el_titulo(self):
        """El en curso no lleva aclaración; cualquier otro dice que no es el de ahora."""

        self.assertIn("Turno Tarde · entradas<", self._html(self._get()))
        self.assertNotIn("no es el turno en curso", self._html(self._get()))
        self.assertIn(
            "Turno Mañana · entradas · no es el turno en curso (ahora, Tarde)",
            self._html(self._get(turno=self.manana.pk)),
        )

    def test_las_acciones_llevan_al_turno_en_curso_aunque_se_mire_otro(self):
        """MINOR de la revisión: llevaban el turno MIRADO, no el en curso.

        Las acciones cuelgan de la tarjeta del turno en curso (`Tarde`) y la lista de
        correcciones sale de ese turno. Si se llegó con «Ver» a la Mañana, abrir el modal
        con `turno=<Mañana>` lo abriría sobre un turno al que no se puede cargar.
        """

        self._cargar(_local(MIERCOLES, 15))
        contexto = self._get(turno=self.manana.pk).context

        self.assertEqual(contexto["turno"], self.manana)
        acciones = {
            accion["texto"]: accion["url"]
            for tarjeta in contexto["tarjetas"]
            for accion in tarjeta["acciones"]
            if accion["texto"] in ("+ Novedad", "Corregir")
        }
        self.assertEqual(sorted(acciones), ["+ Novedad", "Corregir"])
        for texto, url in acciones.items():
            with self.subTest(accion=texto):
                self.assertIn(f"turno={self.tarde.pk}", url)
                self.assertNotIn(f"turno={self.manana.pk}", url)

    def test_abrir_turnos_vuelve_a_la_misma_fecha_y_al_mismo_turno(self):
        """MINOR de la revisión: la URL era `?turnos=1` pelada y perdía dónde se estaba."""

        contexto = self._get(fecha=MARTES.isoformat(), turno=self.manana.pk).context

        url = contexto["url_abrir_turnos"]
        self.assertIn(f"fecha={MARTES.isoformat()}", url)
        self.assertIn(f"turno={self.manana.pk}", url)
        self.assertIn("turnos=1", url)


class ModalPorGetTests(BasePantalla):
    """Los modales se piden por GET, como en Configuración: la vista decide si arrancan abiertos."""

    def test_novedad_abre_solo_a_quien_puede_cargar(self):
        self.assertTrue(self._get(novedad="1").context["abrir_modal_novedad"])
        self.assertFalse(self._get().context["abrir_modal_novedad"])
        sin = self._usuario("Sin bitacora", self.cis, _sin("dispositivo.bitacora"))
        self.assertFalse(self._get(sin, novedad="1").context["abrir_modal_novedad"])

    def test_corregir_preselecciona_la_novedad_pedida(self):
        entrada = self._cargar(_local(MIERCOLES, 15))

        respuesta = self._get(corregir=str(entrada.pk))

        self.assertTrue(respuesta.context["abrir_modal_corregir"])
        self.assertEqual(respuesta.context["correccion_inicial"], str(entrada.pk))
        self.assertEqual(self._get(corregir="999999").context["correccion_inicial"], "")

    def test_turnos_abre_solo_a_quien_configura(self):
        self.assertTrue(self._get(turnos="1").context["abrir_modal_turnos"])
        sin = self._usuario("Sin editar", self.cis, _sin("dispositivo.editar"))
        self.assertFalse(self._get(sin, turnos="1").context["abrir_modal_turnos"])

    def test_no_queda_el_ancla_ni_el_hashchange(self):
        html = self._html(self._get())

        self.assertNotIn("hashchange", html)
        self.assertNotIn("#nueva-novedad", html)

    def test_el_parametro_del_modal_no_viaja_en_los_filtros_ni_en_la_navegacion(self):
        """Si viajara, filtrar o cambiar de día volvería a abrir el modal solo."""

        entrada = self._cargar(_local(MIERCOLES, 15))

        for params in ({"novedad": "1"}, {"corregir": str(entrada.pk)}, {"turnos": "1"}):
            with self.subTest(params=params):
                contexto = self._get(**params).context

                self.assertEqual(sorted(dict(contexto["ocultos"])), ["fecha", "turno"])
                navegacion = [contexto["dia_anterior"]["url"], contexto["url_hoy"]]
                navegacion += [
                    accion["url"]
                    for tarjeta in contexto["tarjetas"]
                    for accion in tarjeta["acciones"]
                    if accion["texto"] == "Ver"
                ]
                for enlace in navegacion:
                    for parametro in ("novedad=", "corregir=", "turnos="):
                        self.assertNotIn(parametro, enlace)


class OraculoDeIdsTests(BasePantalla):
    """Quien no opera el dispositivo recibe 403 igual con un id ajeno que con uno inexistente."""

    def test_corregir_y_turnos_responden_igual(self):
        operador_parador = self._usuario("Operador parador", self.parador)
        with _reloj():
            ajena = registrar_entrada(dispositivo=self.parador, usuario=operador_parador, tipo="GENERAL", texto="X.")
        intruso = self._usuario("Intruso", self.parador)
        horario = {"nombre": "A", "hora_desde": "01:00", "hora_hasta": "02:00"}
        casos = (
            ("bitacora_corregir", {"entrada": ajena.pk, "tipo": "GENERAL", "texto": "Y."}),
            ("bitacora_corregir", {"entrada": 999999, "tipo": "GENERAL", "texto": "Y."}),
            ("bitacora_turnos", {"turno": self.turno_parador.pk, **horario}),
            ("bitacora_turnos", {"turno": 999999, **horario}),
        )
        for nombre, datos in casos:
            with self.subTest(nombre=nombre, datos=datos):
                self.assertEqual(self._post(nombre, datos, intruso).status_code, 403)


class NovedadesDeLaEstadiaTests(BasePantalla):
    """P7: la solapa «Novedades» de la estadía, de lectura."""

    def _p7(self, estadia, **params):
        self.client.force_login(self.operador)
        with _reloj():
            return self.client.get(reverse("dispositivos:estadia_detalle", args=[self.cis.pk, estadia.pk]), params)

    def test_muestra_solo_las_de_esa_estadia_y_la_version_vigente(self):
        propia = self._cargar(_local(MIERCOLES, 15), texto="Discusion de Ana.", personas=[self.estadia_ana])
        with _reloj():
            corregir_entrada(entrada=propia, usuario=self.operador, texto="Discusión de Ana.")
        self._cargar(_local(MIERCOLES, 15, 10), texto="Algo de Juan.", personas=[self.estadia_juan])
        self._cargar(_local(MIERCOLES, 15, 20), texto="Sin personas.")

        html = self._html(self._p7(self.estadia_ana))

        self.assertIn("Discusión de Ana.", html)
        self.assertIn("Versión 2", html)
        self.assertNotIn("Discusion de Ana.", html, "la versión reemplazada no se ve en P7")
        self.assertNotIn("Algo de Juan.", html)
        self.assertNotIn("Sin personas.", html)
        self.assertIn('id="tab-novedades"', html)
        self.assertIn(reverse("dispositivos:bitacora", args=[self.cis.pk]), html)
        self.assertNotIn(reverse("dispositivos:bitacora_novedad", args=[self.cis.pk]), html, "P7 es de lectura")

    def test_pagina_con_su_propio_parametro(self):
        for n in range(21):
            self._cargar(
                _local(MIERCOLES, 14) + timedelta(minutes=n), texto=f"Novedad {n:02d}.", personas=[self.estadia_ana]
            )

        primera = self._html(self._p7(self.estadia_ana))
        segunda = self._html(self._p7(self.estadia_ana, novedades_page="2", tab="novedades"))

        self.assertIn("Novedad 20.", primera)
        self.assertNotIn("Novedad 00.", primera)
        self.assertIn("Novedad 00.", segunda)
        self.assertNotIn("Novedad 20.", segunda)
        self.assertIn("novedades_page=2", primera)

    def test_sin_novedades_muestra_el_estado_vacio(self):
        """Una estadía cargada por fuera de los servicios: sin movimiento, sin novedad automática."""

        sola = Estadia.objects.create(
            ciudadano=Ciudadano.objects.create(dni="30555666", nombre="Sin", apellido="Novedades"),
            dispositivo=self.cis,
            fecha_ingreso=_local(MARTES, 9),
            clave_alojamiento=Estadia.clave_para(Ciudadano.objects.get(dni="30555666")),
        )

        self.assertIn("Sin novedades", self._html(self._p7(sola)))


@tag("performance")
class NovedadesPresupuestoTests(BasePantalla):
    def test_dos_consultas_sin_importar_cuantas(self):
        servicios = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"]
        techo = servicios["dispositivos_estadia_novedades"]["consultas_fijas"]
        self._cargar(_local(MIERCOLES, 14), personas=[self.estadia_ana])
        with CaptureQueriesContext(connection) as una:
            list(novedades_de_estadia(self.estadia_ana))
        for n in range(15):
            self._cargar(_local(MIERCOLES, 14, n + 1), personas=[self.estadia_ana])
        with CaptureQueriesContext(connection) as muchas:
            list(novedades_de_estadia(self.estadia_ana))

        self.assertEqual(len(una), len(muchas))
        self.assertLessEqual(len(muchas), techo)
