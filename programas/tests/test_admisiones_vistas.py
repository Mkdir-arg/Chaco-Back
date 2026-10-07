"""Las pantallas que operan sobre una admisión, por HTTP (RED-33).

`programas/views/admisiones.py` estaba al 59 % de cobertura: `EgresoAdmisionView`,
`EsperaAdmisionListView`, `PromoverEsperaView` y `TrasladoAdmisionView` no tenían
un solo test que las tocara por la URL. Los tests de servicio de
`test_admisiones.py` pasan igual porque reciben el `usuario`, la cama y la
admisión ya armados: lo que no estaba probado es justamente el pegamento de la
vista —quién autoriza, qué objeto se opera y qué se le pasa al servicio—.

Esto es **caracterización**: fija lo que el código hace hoy, no lo que debería
hacer. Tres conductas que la ficha nombra como «se rompería sin que nadie se
entere» quedan medidas acá: que la vista le pase el `usuario` al servicio, que
`PromoverEsperaView` revalide la cama antes de ocuparla, y que la admisión que
se opera sea la del dispositivo de la URL y no cualquiera por id.

Si D-V1 = no (la v2 no se implementa), estos tests son el criterio heredable de
la v2 (README §7 de la auditoría).
"""

from datetime import timedelta
from unittest.mock import patch
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core import rbac
from legajos.models import Ciudadano
from programas.models import (
    Admision,
    AsignacionDispositivo,
    Cama,
    Dispositivo,
    EsperaAdmision,
    Programa,
    TipoDispositivo,
)
from programas.services.admisiones import admitir_ciudadano, poner_en_espera, promover_espera
from users.models import Capacidad, RolMeta


def permiso(codigo):
    content_type = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=content_type)


class AdmisionesPorHttpTests(TestCase):
    """Egreso, espera, promoción y traslado entrando por la URL."""

    def setUp(self):
        cache.clear()
        self.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        tipo = TipoDispositivo.objects.create(codigo="HTTP", nombre="Hogar", maneja_camas=True)
        self.origen = Dispositivo.objects.create(
            codigo="HOGAR-ORIGEN", nombre="Hogar Origen", tipo=tipo, estado=Dispositivo.Estado.ACTIVO
        )
        self.destino = Dispositivo.objects.create(
            codigo="HOGAR-DESTINO", nombre="Hogar Destino", tipo=tipo, estado=Dispositivo.Estado.ACTIVO
        )
        self.ajeno = Dispositivo.objects.create(
            codigo="HOGAR-AJENO", nombre="Hogar Ajeno", tipo=tipo, estado=Dispositivo.Estado.ACTIVO
        )
        self.cama_origen = Cama.objects.create(dispositivo=self.origen, codigo="O-01")
        self.cama_espera = Cama.objects.create(dispositivo=self.origen, codigo="O-02")
        self.cama_destino = Cama.objects.create(dispositivo=self.destino, codigo="D-01")
        self.cama_ajena = Cama.objects.create(dispositivo=self.ajeno, codigo="A-01")
        self.ciudadano = Ciudadano.objects.create(dni="30100001", nombre="Ana", apellido="Operada")
        self.otro_ciudadano = Ciudadano.objects.create(dni="30100002", nombre="Beto", apellido="Esperando")

        self.admin = User.objects.create_superuser("admin-red33", "admin-red33@example.com", "x")
        self.sin_rol = User.objects.create_user("sin-rol-red33", password="x")
        self.operador = self._usuario_con(
            "operador-red33",
            ["dispositivo.ver", "dispositivo.egresar", "dispositivo.admitir"],
            [self.origen, self.destino],
        )
        self.miron = self._usuario_con("miron-red33", ["dispositivo.ver"], [self.origen])
        cache.clear()

    def _usuario_con(self, username, capacidades, dispositivos):
        """Usuario con un rol de Programa acotado a Dispositivos y nada más.

        Sin `programa.configurar`: el alcance fino lo dan las asignaciones, que
        es el camino que recorre un operador real (`puede_operar_dispositivo`).
        """
        rol = Group.objects.create(name=f"Rol {username}")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        rol.permissions.add(*[permiso(codigo) for codigo in capacidades])
        usuario = User.objects.create_user(username, password="x")
        usuario.groups.add(rol)
        for dispositivo in dispositivos:
            AsignacionDispositivo.objects.create(dispositivo=dispositivo, rol=rol)
        return usuario

    def _alojar(self, ciudadano=None, cama=None, usuario=None):
        return admitir_ciudadano(
            ciudadano=ciudadano or self.ciudadano,
            dispositivo=self.origen,
            cama=cama or self.cama_origen,
            usuario=usuario or self.admin,
        )

    def _encolar(self, usuario=None):
        admision = poner_en_espera(
            ciudadano=self.otro_ciudadano, dispositivo=self.origen, usuario=usuario or self.admin
        )
        return EsperaAdmision.objects.get(admision=admision, promovida=False)

    def _urls(self, admision, espera):
        return {
            "egresar": reverse("dispositivos:egresar", args=[self.origen.pk, admision.pk]),
            "espera": reverse("dispositivos:espera", args=[self.origen.pk]),
            "promover": reverse("dispositivos:espera_promover", args=[self.origen.pk, espera.pk]),
            "trasladar": reverse("dispositivos:trasladar", args=[self.origen.pk, admision.pk]),
        }

    # ------------------------------------------------------------------ permisos

    def test_un_anonimo_va_al_login_en_las_cuatro(self):
        urls = self._urls(self._alojar(), self._encolar())

        for nombre, url in urls.items():
            with self.subTest(pantalla=nombre):
                respuesta = self.client.get(url)

                self.assertEqual(respuesta.status_code, 302)
                self.assertEqual(urlparse(respuesta["Location"]).path, reverse(settings.LOGIN_URL))

    def test_sin_capacidad_las_cuatro_dan_403(self):
        """Una cuenta de backoffice sin rol de Dispositivos no entra a ninguna."""
        urls = self._urls(self._alojar(), self._encolar())
        self.client.force_login(self.sin_rol)

        for nombre, url in urls.items():
            with self.subTest(pantalla=nombre):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_con_dispositivo_ver_solo_se_abre_la_lista_de_espera(self):
        """El alcance es por capacidad, no por módulo: `ver` no habilita operar."""
        urls = self._urls(self._alojar(), self._encolar())
        self.client.force_login(self.miron)

        self.assertEqual(self.client.get(urls["espera"]).status_code, 200)
        for nombre in ("egresar", "promover", "trasladar"):
            with self.subTest(pantalla=nombre):
                self.assertEqual(self.client.get(urls[nombre]).status_code, 403)

    def test_sin_asignacion_al_dispositivo_no_se_opera_aunque_sobre_la_capacidad(self):
        """`puede_operar_dispositivo` exige la asignación activa, no solo el rol."""
        admision = admitir_ciudadano(
            ciudadano=self.ciudadano, dispositivo=self.ajeno, cama=self.cama_ajena, usuario=self.admin
        )
        self.client.force_login(self.operador)

        url = reverse("dispositivos:egresar", args=[self.ajeno.pk, admision.pk])

        self.assertEqual(self.client.get(url).status_code, 403)

    def test_el_superusuario_opera_sin_asignacion(self):
        """Bypass de `is_superuser`: entra a las cuatro sin rol ni asignación."""
        urls = self._urls(self._alojar(), self._encolar())
        self.client.force_login(self.admin)

        for nombre, url in urls.items():
            with self.subTest(pantalla=nombre):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_la_admision_de_otro_dispositivo_no_se_opera_desde_esta_url(self):
        """El `pk` del dispositivo manda: una admisión ajena por id da 403."""
        ajena = admitir_ciudadano(
            ciudadano=self.ciudadano, dispositivo=self.destino, cama=self.cama_destino, usuario=self.admin
        )
        self.client.force_login(self.admin)

        for nombre in ("egresar", "trasladar"):
            with self.subTest(pantalla=nombre):
                url = reverse(f"dispositivos:{nombre}", args=[self.origen.pk, ajena.pk])

                self.assertEqual(self.client.get(url).status_code, 403)

        ajena.refresh_from_db()
        self.assertEqual(ajena.estado, Admision.Estado.ALOJADO)

    def test_las_cuatro_exigen_post_para_cambiar_algo(self):
        """El GET dibuja el formulario y no mueve nada; la espera no acepta POST."""
        admision = self._alojar()
        espera = self._encolar()
        urls = self._urls(admision, espera)
        self.client.force_login(self.operador)

        for nombre in ("egresar", "promover", "trasladar"):
            with self.subTest(pantalla=nombre):
                self.assertEqual(self.client.get(urls[nombre]).status_code, 200)

        self.assertEqual(self.client.post(urls["espera"], {}).status_code, 405)

        admision.refresh_from_db()
        espera.refresh_from_db()
        self.cama_origen.refresh_from_db()
        self.assertEqual(admision.estado, Admision.Estado.ALOJADO)
        self.assertFalse(espera.promovida)
        self.assertEqual(self.cama_origen.estado, Cama.Estado.OCUPADA)

    # ------------------------------------------------------------------ egreso

    def test_egresar_desde_la_pantalla_libera_la_cama_y_registra_quien(self):
        admision = self._alojar()
        self.client.force_login(self.operador)

        # El widget es `datetime-local`: manda minutos, sin segundos. Egresar en el
        # mismo minuto del ingreso queda **antes** del ingreso y el servicio lo
        # rechaza, así que la pantalla real siempre egresa más tarde.
        egreso = timezone.localtime(admision.fecha_ingreso) + timedelta(hours=2)
        respuesta = self.client.post(
            reverse("dispositivos:egresar", args=[self.origen.pk, admision.pk]),
            {
                "fecha_egreso": egreso.strftime("%Y-%m-%dT%H:%M"),
                "motivo": "Alta médica",
                "destino": "Domicilio",
            },
        )

        self.assertRedirects(respuesta, reverse("dispositivos:detalle", args=[self.origen.pk]))
        admision.refresh_from_db()
        self.cama_origen.refresh_from_db()
        self.assertEqual(admision.estado, Admision.Estado.EGRESADO)
        self.assertEqual(self.cama_origen.estado, Cama.Estado.DISPONIBLE)
        # El autor sale de `request.user`: si la vista dejara de pasarlo, el egreso
        # quedaría sin responsable y nadie se enteraría (RED-33).
        self.assertEqual(admision.responsable_egreso, self.operador)
        self.assertEqual(admision.motivo_egreso, "Alta médica")

    def test_un_egreso_anterior_al_ingreso_no_cierra_la_estadia(self):
        """El error del servicio vuelve al formulario, no a un 500."""
        admision = self._alojar()
        anterior = (admision.fecha_ingreso - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        self.client.force_login(self.operador)

        respuesta = self.client.post(
            reverse("dispositivos:egresar", args=[self.origen.pk, admision.pk]),
            {"fecha_egreso": anterior, "motivo": "Error de carga", "destino": "Domicilio"},
        )

        self.assertEqual(respuesta.status_code, 200)
        admision.refresh_from_db()
        self.cama_origen.refresh_from_db()
        self.assertEqual(admision.estado, Admision.Estado.ALOJADO)
        self.assertEqual(self.cama_origen.estado, Cama.Estado.OCUPADA)

    # ------------------------------------------------------------------ espera

    def test_la_lista_de_espera_muestra_solo_la_fila_de_este_dispositivo(self):
        propia = self._encolar()
        ajena = poner_en_espera(ciudadano=self.ciudadano, dispositivo=self.destino, usuario=self.admin)
        self.client.force_login(self.operador)

        respuesta = self.client.get(reverse("dispositivos:espera", args=[self.origen.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(list(respuesta.context["esperas"]), [propia])
        self.assertNotIn(ajena.pk, [espera.admision_id for espera in respuesta.context["esperas"]])

    # ------------------------------------------------------------------ promoción

    def test_promover_de_la_espera_ocupa_la_cama_y_cierra_la_fila(self):
        espera = self._encolar()
        self.client.force_login(self.operador)

        with patch("programas.views.admisiones.promover_espera", side_effect=promover_espera) as espia:
            respuesta = self.client.post(
                reverse("dispositivos:espera_promover", args=[self.origen.pk, espera.pk]),
                {"cama": self.cama_espera.pk},
            )

        self.assertRedirects(respuesta, reverse("dispositivos:espera", args=[self.origen.pk]))
        espera.refresh_from_db()
        self.cama_espera.refresh_from_db()
        self.assertTrue(espera.promovida)
        self.assertEqual(self.cama_espera.estado, Cama.Estado.OCUPADA)
        self.assertEqual(espera.admision.estado, Admision.Estado.ALOJADO)
        self.assertEqual(espera.admision.cama_id, self.cama_espera.pk)
        # La promoción no persiste un «promovida por»: lo único que ata la acción
        # a su autor es el `usuario` que la vista le pasa al servicio.
        self.assertEqual(espia.call_args.kwargs["usuario"], self.operador)

    def test_promover_revalida_la_cama_y_no_pisa_a_quien_la_ocupo(self):
        """La cama se ocupó entre el GET y el POST: no se promueve ni se rompe."""
        espera = self._encolar()
        ocupante = self._alojar(ciudadano=self.ciudadano, cama=self.cama_espera)
        self.client.force_login(self.operador)

        respuesta = self.client.post(
            reverse("dispositivos:espera_promover", args=[self.origen.pk, espera.pk]),
            {"cama": self.cama_espera.pk},
        )

        self.assertEqual(respuesta.status_code, 200)
        espera.refresh_from_db()
        ocupante.refresh_from_db()
        self.cama_espera.refresh_from_db()
        self.assertFalse(espera.promovida)
        self.assertEqual(self.cama_espera.estado, Cama.Estado.OCUPADA)
        self.assertEqual(ocupante.cama_id, self.cama_espera.pk)

    def test_una_espera_de_otro_dispositivo_no_se_promueve_desde_esta_url(self):
        admision = poner_en_espera(ciudadano=self.ciudadano, dispositivo=self.destino, usuario=self.admin)
        ajena = EsperaAdmision.objects.get(admision=admision, promovida=False)
        self.client.force_login(self.admin)

        url = reverse("dispositivos:espera_promover", args=[self.origen.pk, ajena.pk])

        self.assertEqual(self.client.get(url).status_code, 403)
        ajena.refresh_from_db()
        self.assertFalse(ajena.promovida)

    # ------------------------------------------------------------------ traslado

    def test_trasladar_cierra_el_origen_y_abre_el_destino(self):
        admision = self._alojar()
        self.client.force_login(self.operador)

        respuesta = self.client.post(
            reverse("dispositivos:trasladar", args=[self.origen.pk, admision.pk]),
            {"destino": self.destino.pk, "cama": self.cama_destino.pk},
        )

        self.assertRedirects(respuesta, reverse("dispositivos:detalle", args=[self.origen.pk]))
        admision.refresh_from_db()
        self.cama_origen.refresh_from_db()
        self.cama_destino.refresh_from_db()
        nueva = Admision.objects.get(origen_traslado=admision)
        self.assertEqual(admision.estado, Admision.Estado.TRASLADADO)
        self.assertEqual(admision.responsable_egreso, self.operador)
        self.assertEqual(self.cama_origen.estado, Cama.Estado.DISPONIBLE)
        self.assertEqual(nueva.dispositivo_id, self.destino.pk)
        self.assertEqual(nueva.estado, Admision.Estado.ALOJADO)
        self.assertEqual(self.cama_destino.estado, Cama.Estado.OCUPADA)

    def test_trasladar_a_un_dispositivo_donde_no_puede_admitir_no_mueve_nada(self):
        """La capacidad del destino se evalúa aparte: `egresar` no alcanza."""
        solo_egreso = self._usuario_con(
            "solo-egreso-red33", ["dispositivo.ver", "dispositivo.egresar"], [self.origen, self.destino]
        )
        admision = self._alojar()
        cache.clear()
        self.client.force_login(solo_egreso)

        respuesta = self.client.post(
            reverse("dispositivos:trasladar", args=[self.origen.pk, admision.pk]),
            {"destino": self.destino.pk, "cama": self.cama_destino.pk},
        )

        self.assertEqual(respuesta.status_code, 403)
        admision.refresh_from_db()
        self.cama_destino.refresh_from_db()
        self.assertEqual(admision.estado, Admision.Estado.ALOJADO)
        self.assertEqual(self.cama_destino.estado, Cama.Estado.DISPONIBLE)
        self.assertFalse(Admision.objects.filter(origen_traslado=admision).exists())

    def test_trasladar_a_un_destino_fuera_del_alcance_no_lo_ofrece(self):
        """El combo sale de `dispositivos_visibles`: un ajeno ni figura."""
        admision = self._alojar()
        self.client.force_login(self.operador)

        respuesta = self.client.post(
            reverse("dispositivos:trasladar", args=[self.origen.pk, admision.pk]),
            {"destino": self.ajeno.pk, "cama": self.cama_ajena.pk},
        )

        self.assertEqual(respuesta.status_code, 200)
        admision.refresh_from_db()
        self.assertEqual(admision.estado, Admision.Estado.ALOJADO)
        self.assertFalse(Admision.objects.filter(origen_traslado=admision).exists())
