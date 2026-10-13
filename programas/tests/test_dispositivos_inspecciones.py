"""Relevamiento edilicio: `InspeccionEdificio` y su circuito (MVP v2, etapa 4 · #700).

Lo que se fija acá, y por qué:

1. **Un predio compartido se releva una vez y lo ven todas las instituciones que lo
   ocupan**: es la decisión del PM del 08/10/2026 que hizo colgar el modelo del edificio.
2. **El agente solo ve y carga lo que tiene asignado.** El usuario que lo intenta tiene
   todo lo demás —todas las capacidades, alcance de admin del programa— menos ser el
   asignado: si la guarda fuera la capacidad, pasaría.
3. **El coordinador asigna dentro de su alcance, y el agente es externo** a las
   instituciones del edificio (default a confirmar con el Ministerio).
4. **La consulta del semáforo distingue «sin relevar» de «relevado y sano»** y no crece
   con la cantidad de edificios.
5. **Las fotos se agregan, no se pisan**, se validan y se sirven con la regla de la
   inspección.
"""

import tempfile
from datetime import timedelta

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from core import rbac
from programas.models import (
    AsignacionDispositivo,
    Dispositivo,
    Edificio,
    FotoInspeccion,
    InspeccionEdificio,
    Programa,
    TipoDispositivo,
)
from programas.services import inspecciones as servicio
from programas.services.inspecciones import (
    agentes_asignables,
    agregar_foto,
    cancelar_inspeccion,
    crear_inspeccion,
    edificios_en_alcance,
    inspecciones_asignadas,
    inspecciones_de_dispositivo,
    inspecciones_visibles,
    reasignar_inspeccion,
    registrar_resultado,
    ultima_inspeccion,
    ultimas_inspecciones_de_dispositivos,
    ultimas_inspecciones_por_edificio,
)
from users.models import Capacidad, RolMeta

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64
TODAS_DE_DISPOSITIVOS = (
    "dispositivo.ver",
    "dispositivo.crear",
    "dispositivo.editar",
    "dispositivo.validar",
    "dispositivo.admitir",
    "dispositivo.egresar",
    "programa.configurar",
    "inspeccion.asignar",
    "inspeccion.relevar",
)
Criticidad = InspeccionEdificio.Criticidad
Estado = InspeccionEdificio.Estado


def _permiso(codigo):
    tipo = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=tipo)


def _foto(nombre="fachada.jpg", contenido=JPEG):
    return SimpleUploadedFile(nombre, contenido, content_type="image/jpeg")


class BaseInspecciones(TestCase):
    """Un predio con dos instituciones, otro edificio propio y un dispositivo sin edificio."""

    def setUp(self):
        super().setUp()
        cache.clear()
        media = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(media.cleanup)
        contexto = override_settings(MEDIA_ROOT=media.name)
        contexto.enable()
        self.addCleanup(contexto.disable)

        self.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        self.tipo = TipoDispositivo.objects.create(codigo="ALBERGUE", nombre="Albergue")
        self.parador = self._dispositivo("PAR-1", "Parador")
        self.geriatrico = self._dispositivo("GER-1", "Geriátrico")
        self.cis = self._dispositivo("CIS-3", "CIS")
        self.sin_edificio = self._dispositivo("SIN-1", "Sin edificio")

        self.predio = Edificio.objects.create(codigo="ED-PREDIO", nombre="Predio Resistencia")
        self.predio.dispositivos.add(self.parador, self.geriatrico)
        self.edificio_cis = Edificio.objects.create(codigo="ED-CIS", nombre="Edificio CIS")
        self.edificio_cis.dispositivos.add(self.cis)

        # Coordina el parador: su alcance es el predio, no el edificio del CIS.
        self.coordinador = self._usuario("coordinador", ("inspeccion.asignar", "dispositivo.ver"), [self.parador])
        self.agente = self._usuario("agente", ("inspeccion.relevar",))
        self.otro_agente = self._usuario("otro_agente", ("inspeccion.relevar",))
        self.personal_parador = self._usuario(
            "personal_parador", ("inspeccion.relevar", "dispositivo.ver"), [self.parador]
        )
        self.operador_geriatrico = self._usuario("operador_geriatrico", ("dispositivo.ver",), [self.geriatrico])
        self.vence = timezone.localdate() + timedelta(days=30)

    def _dispositivo(self, codigo, nombre):
        return Dispositivo.objects.create(
            tipo=self.tipo, codigo=codigo, nombre=nombre, estado=Dispositivo.Estado.ACTIVO
        )

    def _usuario(self, nombre, capacidades, dispositivos=()):
        rol = Group.objects.create(name=f"Rol {nombre}")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        rol.permissions.add(*[_permiso(codigo) for codigo in capacidades])
        for dispositivo in dispositivos:
            AsignacionDispositivo.objects.create(dispositivo=dispositivo, rol=rol, activo=True)
        usuario = User.objects.create_user(username=nombre, password="x")
        usuario.groups.add(rol)
        return User.objects.get(pk=usuario.pk)

    def _fresco(self, usuario):
        """`rbac` memoiza las capacidades en el objeto: se recarga entre operaciones."""

        return User.objects.get(pk=usuario.pk)

    def _crear(self, edificio=None, agente=None):
        return crear_inspeccion(
            self._fresco(self.coordinador),
            edificio=edificio or self.predio,
            asignado_a=self._fresco(agente or self.agente),
            fecha_vencimiento=self.vence,
        )


class PredioCompartidoTests(BaseInspecciones):
    def test_un_predio_compartido_se_releva_una_vez_y_lo_ven_todas_sus_instituciones(self):
        inspeccion = self._crear()
        registrar_resultado(self._fresco(self.agente), inspeccion, criticidad=Criticidad.MEDIA, observaciones="Techo")

        self.assertEqual(InspeccionEdificio.objects.count(), 1)
        for dispositivo in (self.parador, self.geriatrico):
            self.assertEqual(list(inspecciones_de_dispositivo(dispositivo)), [inspeccion])
        self.assertEqual(list(inspecciones_de_dispositivo(self.cis)), [])

        ultimas = ultimas_inspecciones_de_dispositivos([self.parador.pk, self.geriatrico.pk])
        self.assertEqual(ultimas[self.parador.pk], {self.predio.pk: inspeccion})
        self.assertEqual(ultimas[self.geriatrico.pk], {self.predio.pk: inspeccion})

    def test_el_operador_de_otra_institucion_del_predio_ve_el_relevamiento(self):
        inspeccion = self._crear()

        self.assertIn(inspeccion, inspecciones_visibles(self._fresco(self.operador_geriatrico)))

    def test_el_operador_de_otro_edificio_no_lo_ve(self):
        inspeccion = self._crear()
        operador_cis = self._usuario("operador_cis", ("dispositivo.ver",), [self.cis])

        self.assertNotIn(inspeccion, inspecciones_visibles(operador_cis))


class UltimaInspeccionTests(BaseInspecciones):
    def test_sin_relevar_no_es_lo_mismo_que_relevado_y_sano(self):
        inspeccion = self._crear()

        # En curso todavía no cuenta: el edificio sigue sin relevar.
        self.assertIsNone(ultima_inspeccion(self.predio))
        self.assertEqual(ultimas_inspecciones_por_edificio([self.predio.pk]), {self.predio.pk: None})

        registrar_resultado(self._fresco(self.agente), inspeccion, criticidad=Criticidad.BAJA)

        ultima = ultimas_inspecciones_por_edificio([self.predio.pk, self.edificio_cis.pk])
        self.assertEqual(ultima[self.predio.pk].criticidad, Criticidad.BAJA)
        self.assertIn(self.edificio_cis.pk, ultima)
        self.assertIsNone(ultima[self.edificio_cis.pk])

    def test_el_dispositivo_sin_edificio_trae_un_diccionario_vacio(self):
        resultado = ultimas_inspecciones_de_dispositivos([self.sin_edificio.pk, self.cis.pk])

        self.assertEqual(resultado[self.sin_edificio.pk], {})
        self.assertEqual(resultado[self.cis.pk], {self.edificio_cis.pk: None})

    def test_gana_la_ultima_realizada(self):
        agente = self._fresco(self.agente)
        primera = self._crear()
        registrar_resultado(agente, primera, criticidad=Criticidad.ALTA)
        InspeccionEdificio.objects.filter(pk=primera.pk).update(realizada_en=timezone.now() - timedelta(days=90))
        segunda = self._crear()
        registrar_resultado(self._fresco(self.agente), segunda, criticidad=Criticidad.BAJA)

        self.assertEqual(ultima_inspeccion(self.predio), segunda)
        self.assertEqual(ultimas_inspecciones_por_edificio([self.predio.pk])[self.predio.pk], segunda)

    def test_la_consulta_no_crece_con_los_edificios(self):
        edificios = [Edificio.objects.create(codigo=f"ED-{i}", nombre=f"Edificio {i}") for i in range(6)]
        for edificio in edificios[:3]:
            InspeccionEdificio.objects.create(
                edificio=edificio,
                asignado_a=self.agente,
                creado_por=self.coordinador,
                fecha_vencimiento=self.vence,
                estado=Estado.REALIZADA,
                criticidad=Criticidad.MEDIA,
                realizada_en=timezone.now(),
                realizada_por=self.agente,
            )
            edificio.dispositivos.add(self.cis)

        with self.assertNumQueries(2):
            ultimas_inspecciones_por_edificio([edificios[0].pk])
        with self.assertNumQueries(2):
            resultado = ultimas_inspecciones_por_edificio([e.pk for e in edificios])
        self.assertEqual(sum(1 for valor in resultado.values() if valor is not None), 3)
        with self.assertNumQueries(3):
            ultimas_inspecciones_de_dispositivos([self.cis.pk, self.parador.pk, self.sin_edificio.pk])


class AsignacionTests(BaseInspecciones):
    def test_el_coordinador_crea_y_asigna(self):
        inspeccion = self._crear()

        self.assertEqual(inspeccion.estado, Estado.ASIGNADA)
        self.assertEqual(inspeccion.asignado_a, self.agente)
        self.assertEqual(inspeccion.creado_por, self.coordinador)
        self.assertEqual(inspeccion.criticidad, "")

    def test_sin_inspeccion_asignar_no_se_crea_aunque_tenga_todo_lo_demas(self):
        casi_admin = self._usuario(
            "casi_admin",
            [c for c in TODAS_DE_DISPOSITIVOS if c != "inspeccion.asignar"],
            [self.parador, self.geriatrico, self.cis],
        )

        with self.assertRaises(PermissionDenied):
            crear_inspeccion(casi_admin, edificio=self.predio, asignado_a=self.agente, fecha_vencimiento=self.vence)

    def test_fuera_de_su_alcance_el_coordinador_no_asigna(self):
        with self.assertRaises(PermissionDenied):
            self._crear(edificio=self.edificio_cis)

    def test_el_admin_del_programa_asigna_en_cualquier_edificio(self):
        admin = self._usuario("admin", ("programa.configurar", "inspeccion.asignar"))

        inspeccion = crear_inspeccion(
            admin, edificio=self.edificio_cis, asignado_a=self.agente, fecha_vencimiento=self.vence
        )

        self.assertEqual(inspeccion.edificio, self.edificio_cis)

    def test_el_agente_tiene_que_poder_relevar(self):
        sin_relevar = self._usuario("sin_relevar", [c for c in TODAS_DE_DISPOSITIVOS if c != "inspeccion.relevar"])

        with self.assertRaises(ValidationError):
            self._crear(agente=sin_relevar)

    def test_el_personal_del_edificio_no_puede_ser_el_agente(self):
        with self.assertRaises(ValidationError):
            self._crear(agente=self.personal_parador)

        candidatos = set(agentes_asignables(self.predio))
        self.assertNotIn(self.personal_parador, candidatos)
        self.assertIn(self.agente, candidatos)
        self.assertIn(self.otro_agente, candidatos)
        # En otro edificio no es personal: ahí sí se lo puede asignar.
        self.assertIn(self.personal_parador, set(agentes_asignables(self.edificio_cis)))

    def test_el_agente_externo_es_un_default_que_se_apaga(self):
        servicio.AGENTE_DEBE_SER_EXTERNO = False
        self.addCleanup(setattr, servicio, "AGENTE_DEBE_SER_EXTERNO", True)

        inspeccion = self._crear(agente=self.personal_parador)

        self.assertEqual(inspeccion.asignado_a, self.personal_parador)

    def test_un_solo_relevamiento_en_curso_por_edificio(self):
        self._crear()

        with self.assertRaises(ValidationError):
            self._crear(agente=self.otro_agente)

    def test_el_vencimiento_no_puede_estar_en_el_pasado(self):
        with self.assertRaises(ValidationError):
            crear_inspeccion(
                self._fresco(self.coordinador),
                edificio=self.predio,
                asignado_a=self.agente,
                fecha_vencimiento=timezone.localdate() - timedelta(days=1),
            )

    def test_reasignar_le_saca_la_tarea_al_agente_anterior(self):
        inspeccion = self._crear()

        reasignar_inspeccion(self._fresco(self.coordinador), inspeccion, self._fresco(self.otro_agente))

        self.assertNotIn(inspeccion, inspecciones_visibles(self._fresco(self.agente)))
        self.assertIn(inspeccion, inspecciones_asignadas(self._fresco(self.otro_agente)))
        with self.assertRaises(PermissionDenied):
            registrar_resultado(self._fresco(self.agente), inspeccion, criticidad=Criticidad.BAJA)

    def test_cancelar_exige_motivo_y_libera_el_edificio(self):
        inspeccion = self._crear()
        with self.assertRaises(ValidationError):
            cancelar_inspeccion(self._fresco(self.coordinador), inspeccion, "  ")

        cancelar_inspeccion(self._fresco(self.coordinador), inspeccion, "Edificio cerrado")

        inspeccion.refresh_from_db()
        self.assertEqual(inspeccion.estado, Estado.CANCELADA)
        self.assertEqual(list(inspecciones_de_dispositivo(self.parador)), [])
        self._crear(agente=self.otro_agente)  # ya no hay uno en curso


class SoloLoAsignadoTests(BaseInspecciones):
    """La guarda es `asignado_a`: ni la capacidad ni el alcance de admin la reemplazan."""

    def setUp(self):
        super().setUp()
        self.inspeccion = self._crear()
        # Todo menos ser el asignado: todas las capacidades y alcance de admin del programa.
        self.intruso = self._usuario("intruso", TODAS_DE_DISPOSITIVOS, [self.parador, self.geriatrico])

    def test_otro_agente_no_ve_la_tarea(self):
        otro = self._fresco(self.otro_agente)

        self.assertNotIn(self.inspeccion, inspecciones_visibles(otro))
        self.assertEqual(list(inspecciones_asignadas(otro)), [])
        self.assertEqual(list(inspecciones_asignadas(self._fresco(self.agente))), [self.inspeccion])

    def test_quien_no_es_el_asignado_no_carga_el_resultado(self):
        for usuario in (self.otro_agente, self.intruso):
            with self.subTest(usuario=usuario.username), self.assertRaises(PermissionDenied):
                registrar_resultado(self._fresco(usuario), self.inspeccion, criticidad=Criticidad.BAJA)

        self.inspeccion.refresh_from_db()
        self.assertEqual(self.inspeccion.estado, Estado.ASIGNADA)

    def test_quien_no_es_el_asignado_no_sube_fotos(self):
        for usuario in (self.otro_agente, self.intruso):
            with self.subTest(usuario=usuario.username), self.assertRaises(PermissionDenied):
                agregar_foto(self._fresco(usuario), self.inspeccion, _foto())

        self.assertFalse(FotoInspeccion.objects.exists())

    def test_el_asignado_sin_la_capacidad_no_carga(self):
        """El otro lado de la guarda: ser el asignado tampoco alcanza solo."""

        Group.objects.get(name="Rol agente").permissions.clear()

        with self.assertRaises(PermissionDenied):
            registrar_resultado(self._fresco(self.agente), self.inspeccion, criticidad=Criticidad.BAJA)


class ResultadoYFotosTests(BaseInspecciones):
    def setUp(self):
        super().setUp()
        self.inspeccion = self._crear()

    def test_el_agente_registra_criticidad_observaciones_y_fotos(self):
        registrar_resultado(
            self._fresco(self.agente),
            self.inspeccion,
            criticidad=Criticidad.ALTA,
            observaciones="Filtración en el pabellón C",
            fotos=[_foto(), (_foto("techo.png", b"\x89PNG\r\n\x1a\n" + b"0" * 32), "Techo")],
        )

        self.inspeccion.refresh_from_db()
        self.assertEqual(self.inspeccion.estado, Estado.REALIZADA)
        self.assertEqual(self.inspeccion.criticidad, Criticidad.ALTA)
        self.assertEqual(self.inspeccion.realizada_por, self.agente)
        self.assertIsNotNone(self.inspeccion.realizada_en)
        fotos = list(self.inspeccion.fotos.all())
        self.assertEqual([f.descripcion for f in fotos], ["", "Techo"])
        self.assertTrue(all(f.archivo.name.startswith("dispositivos/inspecciones/") for f in fotos))

    def test_no_se_registra_dos_veces_ni_con_criticidad_inventada(self):
        agente = self._fresco(self.agente)
        with self.assertRaises(ValidationError):
            registrar_resultado(agente, self.inspeccion, criticidad="VERDE")

        registrar_resultado(agente, self.inspeccion, criticidad=Criticidad.BAJA)
        with self.assertRaises(ValidationError):
            registrar_resultado(self._fresco(self.agente), self.inspeccion, criticidad=Criticidad.ALTA)

    def test_las_fotos_se_agregan_y_no_se_pisan(self):
        agente = self._fresco(self.agente)
        primera = agregar_foto(agente, self.inspeccion, _foto(), "Fachada")
        registrar_resultado(self._fresco(self.agente), self.inspeccion, criticidad=Criticidad.MEDIA)
        # La app sin conexión puede mandar fotos después de cerrar el resultado.
        segunda = agregar_foto(self._fresco(self.agente), self.inspeccion, _foto(), "Fachada")

        self.assertNotEqual(primera.archivo.name, segunda.archivo.name)
        self.assertEqual(self.inspeccion.fotos.count(), 2)
        primera.descripcion = "Otra"
        with self.assertRaises(ValidationError):
            primera.save()
        with self.assertRaises(ValidationError):
            primera.delete()

    def test_la_foto_se_valida_y_si_falla_no_queda_nada(self):
        agente = self._fresco(self.agente)
        for nombre, contenido in (("informe.pdf", b"%PDF-1.4"), ("falsa.jpg", b"<html>no</html>")):
            with self.subTest(nombre=nombre), self.assertRaises(ValidationError):
                registrar_resultado(
                    agente,
                    self.inspeccion,
                    criticidad=Criticidad.BAJA,
                    fotos=[_foto(), _foto(nombre, contenido)],
                )

        self.inspeccion.refresh_from_db()
        self.assertEqual(self.inspeccion.estado, Estado.ASIGNADA)
        self.assertFalse(FotoInspeccion.objects.exists())

    def test_webp_y_heic_se_miran_por_su_firma(self):
        """`FIRMAS` deja pasar sin mirar las extensiones que no conoce: la foto no."""

        agente = self._fresco(self.agente)
        for nombre in ("x.webp", "x.heic", "x.heif"):
            with self.subTest(nombre=nombre), self.assertRaises(ValidationError):
                agregar_foto(agente, self.inspeccion, _foto(nombre, b"<html><script>no</script></html>"))
        self.assertFalse(FotoInspeccion.objects.exists())

        agregar_foto(agente, self.inspeccion, _foto("ok.webp", b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"0" * 16))
        agregar_foto(agente, self.inspeccion, _foto("ok.heic", b"\x00\x00\x00\x18ftypheic" + b"0" * 16))
        self.assertEqual(FotoInspeccion.objects.count(), 2)

    def test_las_fotos_tampoco_se_tocan_por_queryset(self):
        foto = agregar_foto(self._fresco(self.agente), self.inspeccion, _foto())
        foto.descripcion = "Otra"

        for operacion in (
            lambda: FotoInspeccion.objects.filter(pk=foto.pk).update(descripcion="Otra"),
            lambda: FotoInspeccion.objects.filter(pk=foto.pk).delete(),
            lambda: self.inspeccion.fotos.all().delete(),
            lambda: FotoInspeccion.objects.bulk_update([foto], ["descripcion"]),
            lambda: FotoInspeccion.objects.all().bulk_update([foto], ["descripcion"]),
        ):
            with self.assertRaises(ValidationError):
                operacion()

        foto.refresh_from_db()
        self.assertEqual(foto.descripcion, "")

    def test_un_cancelado_no_recibe_fotos(self):
        cancelar_inspeccion(self._fresco(self.coordinador), self.inspeccion, "Duplicado")

        with self.assertRaises(ValidationError):
            agregar_foto(self._fresco(self.agente), self.inspeccion, _foto())

    def test_la_base_no_acepta_un_realizado_sin_criticidad(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            InspeccionEdificio.objects.filter(pk=self.inspeccion.pk).update(
                estado=Estado.REALIZADA, realizada_en=timezone.now(), realizada_por=self.agente
            )

    def test_vencida_se_deriva_de_la_fecha(self):
        self.assertFalse(self.inspeccion.vencida())
        self.assertTrue(self.inspeccion.vencida(hoy=self.vence + timedelta(days=1)))


class MediaDeFotosTests(BaseInspecciones):
    """`/media/` sirve la foto con la misma regla que la inspección."""

    def setUp(self):
        super().setUp()
        self.inspeccion = self._crear()
        foto = agregar_foto(self._fresco(self.agente), self.inspeccion, _foto())
        self.url = f"/media/{foto.archivo.name}"

    def _get(self, usuario):
        cliente = Client()
        cliente.force_login(usuario)
        respuesta = cliente.get(self.url)
        if respuesta.streaming:
            b"".join(respuesta.streaming_content)
        return respuesta.status_code

    def test_la_ven_el_agente_el_coordinador_y_las_instituciones_del_predio(self):
        for usuario in (self.agente, self.coordinador, self.operador_geriatrico):
            with self.subTest(usuario=usuario.username):
                self.assertEqual(self._get(usuario), 200)

    def test_no_la_ve_otro_agente(self):
        self.assertEqual(self._get(self.otro_agente), 403)


class AlcanceDelCoordinadorTests(MediaDeFotosTests):
    """El coordinador ve por **su propio** camino, y solo en su alcance.

    Los coordinadores de acá tienen únicamente `inspeccion.asignar`: sin `dispositivo.ver`
    no hay un segundo camino que tape el del coordinador si se rompe.
    """

    def test_el_coordinador_de_otro_edificio_no_ve_la_inspeccion_ni_su_foto(self):
        coordinador_cis = self._usuario("coordinador_cis", ("inspeccion.asignar",), [self.cis])

        self.assertNotIn(self.inspeccion, inspecciones_visibles(coordinador_cis))
        self.assertEqual(self._get(coordinador_cis), 403)

    def test_el_coordinador_del_predio_la_ve_solo_por_asignar(self):
        coordinador_parador = self._usuario("coordinador_parador", ("inspeccion.asignar",), [self.parador])

        self.assertIn(self.inspeccion, inspecciones_visibles(coordinador_parador))
        self.assertEqual(self._get(coordinador_parador), 200)

    def test_el_alcance_lo_da_el_rol_que_tiene_la_capacidad(self):
        """`asignar` en un rol sin asignación más `ver` en otro rol asignado no suman alcance."""

        mixto = self._usuario("mixto", ("inspeccion.asignar",))
        rol_ver = Group.objects.create(name="Rol mixto ver")
        RolMeta.objects.create(grupo=rol_ver, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        rol_ver.permissions.add(_permiso("dispositivo.ver"))
        AsignacionDispositivo.objects.create(dispositivo=self.cis, rol=rol_ver, activo=True)
        mixto.groups.add(rol_ver)
        mixto = self._fresco(mixto)

        self.assertFalse(edificios_en_alcance(mixto).exists())
        with self.assertRaises(PermissionDenied):
            crear_inspeccion(
                mixto, edificio=self.edificio_cis, asignado_a=self._fresco(self.agente), fecha_vencimiento=self.vence
            )


class CatalogoTests(TestCase):
    def test_las_capacidades_son_de_programa_y_solo_de_dispositivos(self):
        modulo = next(m for m in rbac.CATALOGO if m["modulo"] == "inspecciones")

        self.assertEqual(modulo["alcance"], "programa")
        self.assertEqual(modulo["programas"], ("DISPOSITIVOS",))
        self.assertTrue(rbac.es_codigo_de_programa("inspeccion.asignar"))
        self.assertTrue(rbac.es_codigo_de_programa("inspeccion.relevar"))
        self.assertTrue(Permission.objects.filter(codename="inspeccion_relevar").exists())
        modulos_becas = {m["modulo"] for m in rbac.arbol_capacidades(solo_programa=True, programa="BECAS")}
        self.assertNotIn("inspecciones", modulos_becas)
