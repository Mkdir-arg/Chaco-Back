"""`/mapa/` y su API de puntos (Cambio 493, fase 3)."""

import json
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core import rbac
from legajos.models import Ciudadano
from mapa import services
from mapa.models import Punto
from programas.models import CasoEmergencia, Dispositivo, Edificio, GrupoFamiliar, TipoDispositivo
from users.models import Capacidad, RolMeta


def usuario_con(*codigos, username="operador"):
    """Un usuario con un rol activo que tiene exactamente ``codigos``."""

    user = User.objects.create_user(username, f"{username}@ejemplo.com", "x", first_name="Ana", last_name="Gómez")
    if codigos:
        grupo = Group.objects.create(name=f"rol {username}")
        RolMeta.objects.create(grupo=grupo, categoria=rbac.CATEGORIA_BACKOFFICE, activo=True)
        ct = ContentType.objects.get_for_model(Capacidad)
        for codigo in codigos:
            permiso, _ = Permission.objects.get_or_create(
                content_type=ct, codename=rbac.codename_de(codigo), defaults={"name": codigo}
            )
            grupo.permissions.add(permiso)
        user.groups.add(grupo)
    return user


def punto(**extra):
    datos = {
        "nombre": "Camioneta 3",
        "categoria": Punto.Categoria.VEHICULO,
        "latitud": "-27.451200",
        "longitud": "-58.986700",
    }
    return Punto.objects.create(**{**datos, **extra})


class PuntoModeloTests(TestCase):
    def test_str_con_categoria(self):
        self.assertEqual(str(punto()), "Camioneta 3 (Vehículo)")

    def test_rango_de_coordenadas(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            Punto(nombre="x", latitud=Decimal("95"), longitud=Decimal("0")).full_clean()


class PantallaTests(TestCase):
    def test_sin_sesion_va_al_login(self):
        respuesta = self.client.get(reverse("mapa:inicio"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("next=/mapa/", respuesta["Location"])

    def test_sin_mapa_ver_no_entra(self):
        self.client.force_login(usuario_con("ciudadano.ver"))
        respuesta = self.client.get(reverse("mapa:inicio"))
        self.assertEqual(respuesta.status_code, 302)

    @override_settings(GOOGLE_MAPS_API_KEY="AIza-prueba")
    def test_con_mapa_ver_ve_los_puntos_sin_editar(self):
        punto()
        self.client.force_login(usuario_con("mapa.ver"))
        respuesta = self.client.get(reverse("mapa:inicio"))
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        self.assertIn('data-mapa-capas="mapa"', html)
        self.assertIn("Camioneta 3", html)
        self.assertNotIn("data-mapa-agregar", html)
        self.assertNotIn("mapa-general.js", html)
        self.assertNotIn('"movible"', html)
        self.assertIn('href="/mapa/"', html)  # ítem del menú

    @override_settings(GOOGLE_MAPS_API_KEY="AIza-prueba")
    def test_con_mapa_editar_agrega_mueve_y_elimina(self):
        punto()
        self.client.force_login(usuario_con("mapa.ver", "mapa.editar"))
        html = self.client.get(reverse("mapa:inicio")).content.decode()
        self.assertIn("data-mapa-agregar", html)
        self.assertIn("mapa-general.js", html)
        self.assertIn('"movible": true', html)
        self.assertIn('"accion": "eliminar"', html)

    @override_settings(GOOGLE_MAPS_API_KEY="")
    def test_sin_key_no_ofrece_agregar_punto(self):
        # Sin Google no hay mapa que tocar: «Agregar punto» dejaba a la persona en «Tocá el mapa…» sin salida.
        punto()
        self.client.force_login(usuario_con("mapa.ver", "mapa.editar"))
        html = self.client.get(reverse("mapa:inicio")).content.decode()
        self.assertIn("El mapa no está disponible en este ambiente", html)
        self.assertIn("Camioneta 3", html)
        self.assertNotIn("data-mapa-agregar", html)
        self.assertNotIn("data-mapa-barra", html)
        self.assertNotIn("mapa-general.js", html)


class CapasTests(TestCase):
    """Cada capa con la regla de su módulo; los selectores de alcance se prueban en sus propios módulos."""

    def setUp(self):
        self.user = usuario_con("mapa.ver")
        tipo = TipoDispositivo.objects.create(codigo="HOGAR", nombre="Hogar")
        reservado = TipoDispositivo.objects.create(codigo="PROTECCION", nombre="Protección", ubicacion_reservada=True)
        self.hogar = Dispositivo.objects.create(
            tipo=tipo, codigo="D-1", nombre="Hogar Santa Rita", latitud="-27.45", longitud="-58.98", camas_totales=24
        )
        Dispositivo.objects.create(tipo=tipo, codigo="D-2", nombre="Sin ubicar")
        self.refugio = Dispositivo.objects.create(
            tipo=reservado, codigo="D-3", nombre="Refugio", latitud="-27.40", longitud="-58.90"
        )
        self.edificio = Edificio.objects.create(
            codigo="ED-1",
            nombre="Sede central",
            latitud="-27.46",
            longitud="-58.99",
            calle="Av. 25 de Mayo",
            numero="925",
        )
        persona = Ciudadano.objects.create(dni="30111222", nombre="Rosa", apellido="Benítez")
        grupo = GrupoFamiliar.objects.create(
            responsable=persona, traslado=GrupoFamiliar.Traslado.BOMBEROS, adultos_f=2, total_declarado=2
        )
        self.caso = CasoEmergencia.objects.create(
            numero="2026-000142",
            grupo=grupo,
            origen=CasoEmergencia.Origen.MESA,
            estado=CasoEmergencia.Estado.NUEVO,
            prioridad=CasoEmergencia.Prioridad.ALTA,
            direccion="Calle Secreta 123",
            latitud="-27.47",
            longitud="-58.97",
            relevado_por=self.user,
            relevado_en=timezone.now() - timedelta(hours=2),
        )
        punto()

    def capas(self, *, dispositivos=True, edificios=True, mesa=True):
        with (
            mock.patch.object(
                services,
                "dispositivos_visibles",
                return_value=Dispositivo.objects.all() if dispositivos else Dispositivo.objects.none(),
            ),
            mock.patch.object(
                services,
                "edificios_visibles",
                return_value=Edificio.objects.all() if edificios else Edificio.objects.none(),
            ),
            mock.patch.object(services, "puede_operar_la_mesa", return_value=mesa),
        ):
            return services.capas_del_mapa(self.user)

    def test_dispositivos_sin_reservados_ni_sin_ubicacion(self):
        datos = self.capas()
        ids = [p["id"] for p in datos["puntos"] if p["capa"] == "dispositivo"]
        self.assertEqual(ids, [f"dispositivo-{self.hogar.pk}"])
        capa = next(c for c in datos["capas"] if c["id"] == "dispositivo")
        self.assertEqual(capa["total"], 1)
        self.assertEqual(capa["fuera"], "1 sin ubicación · 1 de ubicación reservada")
        self.assertNotIn("Refugio", json.dumps(datos))

    def test_punto_de_dispositivo_con_enlace_y_estado(self):
        dispositivo = next(p for p in self.capas()["puntos"] if p["capa"] == "dispositivo")
        self.assertEqual(dispositivo["url"], reverse("dispositivos:detalle", args=[self.hogar.pk]))
        self.assertEqual(dispositivo["estado"]["texto"], "Borrador")
        self.assertIn(["Plazas", "24"], dispositivo["datos"])

    def test_capa_de_edificios(self):
        edificio = next(p for p in self.capas()["puntos"] if p["capa"] == "edificio")
        self.assertEqual(edificio["url"], reverse("dispositivos:edificio_detalle", args=[self.edificio.pk]))
        self.assertIn(["Domicilio", "Av. 25 de Mayo 925"], edificio["datos"])

    def test_edificio_de_un_dispositivo_reservado_no_se_dibuja(self):
        predio = Edificio.objects.create(codigo="ED-R", nombre="Casa Refugio", latitud="-27.40", longitud="-58.90")
        predio.dispositivos.add(self.refugio, self.hogar)
        datos = self.capas()
        self.assertNotIn("Casa Refugio", json.dumps(datos, ensure_ascii=False))
        capa = next(c for c in datos["capas"] if c["id"] == "edificio")
        self.assertEqual(capa["total"], 1)
        self.assertEqual(capa["fuera"], "1 con un dispositivo de ubicación reservada")

    def test_casos_solo_para_la_mesa_y_sin_datos_de_la_persona(self):
        datos = self.capas()
        caso = next(p for p in datos["puntos"] if p["capa"] == "emergencia")
        self.assertEqual(caso["titulo"], "Caso 2026-000142")
        self.assertEqual(caso["tono"], "danger")
        texto = json.dumps(datos, ensure_ascii=False)
        for dato in ("Rosa", "Benítez", "30111222", "Calle Secreta"):
            self.assertNotIn(dato, texto)

        sin_mesa = self.capas(mesa=False)
        self.assertNotIn("emergencia", [c["id"] for c in sin_mesa["capas"]])
        self.assertFalse([p for p in sin_mesa["puntos"] if p["capa"] == "emergencia"])

    def test_estado_y_prioridad_con_la_tabla_de_emergencia(self):
        caso = next(p for p in self.capas()["puntos"] if p["capa"] == "emergencia")
        self.assertEqual(caso["estado"], {"texto": "Nuevo", "tono": "info"})
        self.assertEqual(caso["subtitulo"], "Prioridad alta")

    def test_casos_cerrados_no_se_dibujan(self):
        CasoEmergencia.objects.filter(pk=self.caso.pk).update(
            estado=CasoEmergencia.Estado.CERRADO,
            cerrado_en=timezone.now(),
            motivo_cierre=CasoEmergencia.MotivoCierre.OTRO,
        )
        self.assertFalse([p for p in self.capas()["puntos"] if p["capa"] == "emergencia"])

    def test_sin_alcance_en_un_modulo_no_aparece_su_capa(self):
        capas = [c["id"] for c in self.capas(dispositivos=False, edificios=False, mesa=False)["capas"]]
        self.assertEqual(capas, ["punto"])

    def test_puntos_solo_movibles_con_mapa_editar(self):
        suelto = next(p for p in self.capas()["puntos"] if p["capa"] == "punto")
        self.assertNotIn("movible", suelto)
        self.assertNotIn("acciones", suelto)
        self.assertEqual(suelto["grupo"], Punto.Categoria.VEHICULO)

    def test_consultas_constantes_al_crecer_las_cuatro_capas(self):
        self.capas()  # las capacidades del usuario quedan en caché, como en un request
        with CaptureQueriesContext(connection) as antes:
            self.capas()
        tipo = self.hogar.tipo
        for i in range(4):
            Dispositivo.objects.create(
                tipo=tipo, codigo=f"D-N{i}", nombre=f"Otro {i}", latitud="-27.4", longitud="-58.9"
            )
            Edificio.objects.create(codigo=f"ED-N{i}", nombre=f"Edificio {i}", latitud="-27.4", longitud="-58.9")
            grupo = GrupoFamiliar.objects.create(
                responsable=self.caso.grupo.responsable, traslado=GrupoFamiliar.Traslado.BOMBEROS, total_declarado=1
            )
            CasoEmergencia.objects.create(
                numero=f"2026-00090{i}",
                grupo=grupo,
                origen=CasoEmergencia.Origen.MESA,
                estado=CasoEmergencia.Estado.EN_GESTION,
                prioridad=CasoEmergencia.Prioridad.BAJA,
                direccion="x",
                latitud="-27.4",
                longitud="-58.9",
                relevado_por=self.user,
                relevado_en=timezone.now(),
            )
            punto(nombre=f"Punto {i}", cargado_por=self.user)
        with self.assertNumQueries(len(antes.captured_queries)):
            datos = self.capas()
        self.assertEqual(len(datos["puntos"]), 4 + 4 * 4)


class ApiTests(TestCase):
    def setUp(self):
        self.lector = usuario_con("mapa.ver", username="lector")
        self.editor = usuario_con("mapa.ver", "mapa.editar", username="editor")
        self.punto = punto()
        self.url = reverse("mapa:api_puntos")
        self.url_punto = reverse("mapa:api_punto", args=[self.punto.pk])

    def test_sin_sesion_401_json(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 401)
        self.assertFalse(respuesta.json()["ok"])

    def test_sin_mapa_ver_403(self):
        self.client.force_login(usuario_con("ciudadano.ver", username="otro"))
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_lista_con_mapa_ver(self):
        self.client.force_login(self.lector)
        datos = self.client.get(self.url).json()
        self.assertEqual([p["id"] for p in datos["puntos"]], [f"punto-{self.punto.pk}"])

    def test_crear_exige_mapa_editar(self):
        self.client.force_login(self.lector)
        respuesta = self.client.post(
            self.url, {"nombre": "x", "categoria": "OTRO", "latitud": "-27", "longitud": "-58"}
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(Punto.objects.count(), 1)

    def test_crear(self):
        self.client.force_login(self.editor)
        respuesta = self.client.post(
            self.url,
            {
                "nombre": "  Grupo electrógeno  ",
                "categoria": "EQUIPO",
                "descripcion": "",
                "latitud": "-27.4",
                "longitud": "-58.9",
            },
        )
        self.assertEqual(respuesta.status_code, 201)
        creado = Punto.objects.get(nombre="Grupo electrógeno")
        self.assertEqual(creado.cargado_por, self.editor)
        self.assertEqual(respuesta.json()["punto"]["id"], f"punto-{creado.pk}")
        self.assertTrue(respuesta.json()["punto"]["movible"])
        self.assertIn(f'data-item="punto-{creado.pk}"', respuesta.json()["item"])

    def test_crear_con_errores_400(self):
        self.client.force_login(self.editor)
        respuesta = self.client.post(self.url, {"nombre": "", "categoria": "OTRO", "latitud": "95", "longitud": "-58"})
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(set(respuesta.json()["errors"]), {"nombre", "latitud"})

    def test_mover(self):
        self.client.force_login(self.editor)
        respuesta = self.client.patch(
            self.url_punto, json.dumps({"latitud": "-27.5", "longitud": "-59"}), content_type="application/json"
        )
        self.assertEqual(respuesta.status_code, 200)
        self.punto.refresh_from_db()
        self.assertEqual(self.punto.latitud, Decimal("-27.500000"))
        self.assertEqual(self.punto.nombre, "Camioneta 3")

    def test_mover_fuera_de_rango_400(self):
        self.client.force_login(self.editor)
        respuesta = self.client.patch(
            self.url_punto, json.dumps({"latitud": "-27.5", "longitud": "200"}), content_type="application/json"
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_mover_con_cuerpo_ilegible_400(self):
        self.client.force_login(self.editor)
        respuesta = self.client.patch(self.url_punto, "no es json", content_type="application/json")
        self.assertEqual(respuesta.status_code, 400)

    def test_mover_o_eliminar_sin_mapa_editar_403(self):
        self.client.force_login(self.lector)
        self.assertEqual(self.client.delete(self.url_punto).status_code, 403)
        self.assertEqual(
            self.client.patch(
                self.url_punto, json.dumps({"latitud": "1", "longitud": "1"}), content_type="application/json"
            ).status_code,
            403,
        )
        self.assertTrue(Punto.objects.filter(pk=self.punto.pk).exists())

    def test_eliminar(self):
        self.client.force_login(self.editor)
        self.assertEqual(self.client.delete(self.url_punto).status_code, 200)
        self.assertFalse(Punto.objects.filter(pk=self.punto.pk).exists())
        self.assertEqual(self.client.delete(self.url_punto).status_code, 404)

    def test_metodo_no_permitido(self):
        self.client.force_login(self.editor)
        self.assertEqual(self.client.put(self.url_punto).status_code, 405)

    def test_csrf_obligatorio(self):
        from django.test import Client

        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.editor)
        self.assertEqual(cliente.delete(self.url_punto).status_code, 403)
        self.assertTrue(Punto.objects.filter(pk=self.punto.pk).exists())
