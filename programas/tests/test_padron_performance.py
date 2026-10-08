"""El cruce del padrón escribe en lotes y el resultado no cambia (PERF-04, PERF-16).

`validar_casos_pendientes` corría dentro del request que sube el Excel y pagaba un
`UPDATE legajos_ciudadano` y un `INSERT programas_tracaformulario` **por caso**: con el
relevamiento público de 20.000 casos del banco eran 13.942 sentencias y 26.668
`cache.delete`, contra los 60 s de nginx y el `read_timeout` de 10 s de ECOM.

Dos cosas se fijan acá:

1. **Consultas constantes** (PERF-04): cruzar 25 casos cuesta las mismas consultas que
   cruzar 5. Antes crecía de a dos por caso.
2. **Mismo resultado** que la versión por caso: `_cruce_por_caso_referencia` es la copia
   congelada del algoritmo anterior al cambio y los dos corren sobre datasets gemelos.
   Si alguna optimización futura mueve un dato, el diff sale acá y no en producción.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import Convocatoria, Formulario, PadronHabilitado, Relevamiento, Segmento
from programas.services.becas import registrar_traza
from programas.services.padron import (
    _es_relevamiento,
    _identidad_del_caso,
    cargar_padron,
    normalizar_dni,
    normalizar_sexo,
    padron_de,
    validar_casos_pendientes,
)


def _cruce_por_caso_referencia(objetivo, usuario=None):
    """Copia **congelada** de `validar_casos_pendientes` anterior a PERF-04.

    No se mantiene ni se mejora: su único trabajo es producir el resultado contra el
    que se compara la versión en lotes. Un `ciudadano.save()` y un `registrar_traza`
    por caso, más un `bulk_update` de los formularios al final.
    """
    filas = {(fila.dni, fila.sexo): fila for fila in padron_de(objetivo).con_identidad().select_related("localidad")}
    if not filas:
        return 0
    pendientes = (
        Formulario.objects.filter(validado_renaper=False, identidad_forzada=False)
        .defer("data", "respuestas", "definicion", "datos_siis")
        .select_related("ciudadano")
    )
    if _es_relevamiento(objetivo):
        pendientes = pendientes.filter(relevamiento=objetivo)
    else:
        pendientes = pendientes.filter(relevamiento__convocatoria=objetivo).exclude(
            relevamiento__in=PadronHabilitado.objects.filter(relevamiento__convocatoria=objetivo).values(
                "relevamiento_id"
            )
        )

    validados = []
    for formulario in pendientes:
        dni, sexo = _identidad_del_caso(formulario)
        fila = filas.get((normalizar_dni(dni), normalizar_sexo(sexo)))
        if fila is None:
            continue
        cambios = [("Validación de identidad", "Pendiente", "Validada por padrón")]
        ciudadano = formulario.ciudadano
        if ciudadano is not None:
            actualizados = []
            for campo, valor in (
                ("nombre", fila.nombre),
                ("apellido", fila.apellido),
                ("fecha_nacimiento", fila.fecha_nacimiento),
                ("localidad", fila.localidad),
            ):
                if valor and not getattr(ciudadano, campo):
                    setattr(ciudadano, campo, valor)
                    actualizados.append(campo)
                    cambios.append((f"Ciudadano · {campo}", "", str(valor)))
            if actualizados:
                ciudadano.save(update_fields=[*actualizados, "modificado"])
        elif isinstance(formulario.datos_identificacion, dict):
            datos = dict(formulario.datos_identificacion)
            for campo, valor in (
                ("nombre", fila.nombre),
                ("apellido", fila.apellido),
                ("fecha_nacimiento", fila.fecha_nacimiento.isoformat() if fila.fecha_nacimiento else ""),
            ):
                if valor and not datos.get(campo):
                    datos[campo] = valor
            if fila.localidad_id and not datos.get("localidad_id"):
                datos["localidad_id"] = fila.localidad_id
            datos["origen"] = "padron"
            formulario.datos_identificacion = datos
        formulario.validado_renaper = True
        formulario.origen_validacion = Formulario.OrigenValidacion.PADRON
        formulario.modificado = timezone.now()
        formulario.dni_titular = formulario._dni_titular_actual()
        validados.append(formulario)
        registrar_traza(formulario, usuario, cambios)
    if validados:
        Formulario.objects.bulk_update(
            validados,
            ["validado_renaper", "origen_validacion", "datos_identificacion", "modificado", "dni_titular"],
            batch_size=200,
        )
    return len(validados)


class _BaseCruce(TestCase):
    """Una convocatoria con un relevamiento y casos pendientes a pedido."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.territorial = User.objects.create_user("terri_perf04", password="x")

    def _convocatoria(self, sufijo):
        segmento = Segmento.objects.create(nombre=f"Seg perf {sufijo}", cupo_maximo=10_000)
        convocatoria = Convocatoria.objects.create(
            nombre=f"Conv perf {sufijo}",
            segmento=segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        relevamiento = Relevamiento.objects.create(
            convocatoria=convocatoria,
            territorial=self.territorial,
            fecha_asignada=timezone.now() - timedelta(days=1),
            fecha_hasta=timezone.now() + timedelta(days=10),
            zona=f"Zona {sufijo}",
        )
        return convocatoria, relevamiento

    def _poblar(self, relevamiento, cantidad, base_dni):
        """`cantidad` casos pendientes con el legajo vacío y `cantidad` filas de padrón.

        Uno de cada cinco va sin ciudadano (caso offline, el que mueve
        `datos_identificacion`) para que las dos ramas del cruce entren al test.
        """
        entradas = []
        for indice in range(cantidad):
            dni = str(base_dni + indice)
            sexo = "F" if indice % 2 else "M"
            if indice % 5 == 4:
                Formulario.objects.create(
                    relevamiento=relevamiento,
                    celular="3624000000",
                    email_contacto="a@b.com",
                    datos_identificacion={"dni": dni, "sexo": sexo, "origen": "manual"},
                )
            else:
                ciudadano = Ciudadano.objects.create(dni=dni, nombre="", apellido="", genero=sexo)
                Formulario.objects.create(
                    relevamiento=relevamiento,
                    ciudadano=ciudadano,
                    celular="3624000000",
                    email_contacto="a@b.com",
                )
            entradas.append(
                {
                    "dni": dni,
                    "sexo": sexo,
                    "nombre": f"Nombre {indice}",
                    "apellido": f"Apellido {indice}",
                    "fecha_nacimiento": date(1990, 1, 1) + timedelta(days=indice),
                    "localidad_texto": "",
                }
            )
        return entradas

    def _sembrar_padron(self, convocatoria, entradas):
        """Las filas del padrón **sin** pasar por `cargar_padron`: lo que se mide es
        el cruce, no la carga."""
        PadronHabilitado.objects.bulk_create(
            PadronHabilitado(
                convocatoria=convocatoria,
                dni=e["dni"],
                sexo=e["sexo"],
                nombre=e["nombre"],
                apellido=e["apellido"],
                fecha_nacimiento=e["fecha_nacimiento"],
            )
            for e in entradas
        )


class ConsultasConstantesTests(_BaseCruce):
    """PERF-04: el cruce no puede costar más consultas por traer más casos."""

    def _consultas_del_cruce(self, cantidad, base_dni):
        convocatoria, relevamiento = self._convocatoria(f"{cantidad}")
        self._sembrar_padron(convocatoria, self._poblar(relevamiento, cantidad, base_dni))
        with CaptureQueriesContext(connection) as capturadas:
            validados = validar_casos_pendientes(convocatoria)
        self.assertEqual(validados, cantidad, "el cruce tiene que validar todos los casos sembrados")
        return len(capturadas.captured_queries)

    def test_el_cruce_no_crece_con_la_cantidad_de_casos(self):
        con_5 = self._consultas_del_cruce(5, 30_100_000)
        con_25 = self._consultas_del_cruce(25, 30_200_000)

        self.assertEqual(
            con_5,
            con_25,
            f"el cruce pasó de {con_5} consultas con 5 casos a {con_25} con 25: volvió a escribir por caso",
        )

    def test_la_version_por_caso_si_crecia(self):
        """Control del test de arriba: sin esto, un empate pasaría aunque el cruce no
        escribiera nada. La referencia congelada **sí** crece con los casos."""
        convocatoria_5, rel_5 = self._convocatoria("ref5")
        self._sembrar_padron(convocatoria_5, self._poblar(rel_5, 5, 30_300_000))
        convocatoria_25, rel_25 = self._convocatoria("ref25")
        self._sembrar_padron(convocatoria_25, self._poblar(rel_25, 25, 30_400_000))

        with CaptureQueriesContext(connection) as con_5:
            _cruce_por_caso_referencia(convocatoria_5)
        with CaptureQueriesContext(connection) as con_25:
            _cruce_por_caso_referencia(convocatoria_25)

        self.assertGreater(len(con_25.captured_queries), len(con_5.captured_queries))


class MismoResultadoQueLaVersionPorCasoTests(_BaseCruce):
    """La reescritura de PERF-04 no puede cambiar ni un dato escrito."""

    def _foto(self, convocatoria):
        """Todo lo que el cruce escribe, sin las marcas de tiempo."""
        casos = (
            Formulario.objects.filter(relevamiento__convocatoria=convocatoria)
            .select_related("ciudadano")
            .order_by("numero")
        )
        foto = []
        for caso in casos:
            ciudadano = caso.ciudadano
            foto.append(
                {
                    "numero": caso.numero,
                    "validado_renaper": caso.validado_renaper,
                    "origen_validacion": caso.origen_validacion,
                    "dni_titular": caso.dni_titular,
                    "datos_identificacion": caso.datos_identificacion,
                    "ciudadano": (
                        None
                        if ciudadano is None
                        else (
                            ciudadano.nombre,
                            ciudadano.apellido,
                            ciudadano.fecha_nacimiento,
                            ciudadano.localidad_id,
                        )
                    ),
                    "trazas": list(caso.trazas.order_by("id").values_list("campo", "valor_anterior", "valor_nuevo")),
                }
            )
        return foto

    def test_escribe_exactamente_lo_mismo_que_el_cruce_por_caso(self):
        viejo_conv, viejo_rel = self._convocatoria("viejo")
        nuevo_conv, nuevo_rel = self._convocatoria("nuevo")
        # Mismo dataset en los dos: mismos DNI, mismos sexos, mismas filas de padrón.
        self._sembrar_padron(viejo_conv, self._poblar(viejo_rel, 12, 31_000_000))
        self._sembrar_padron(nuevo_conv, self._poblar(nuevo_rel, 12, 31_001_000))

        validados_viejo = _cruce_por_caso_referencia(viejo_conv)
        validados_nuevo = validar_casos_pendientes(nuevo_conv)

        self.assertEqual(validados_viejo, 12)
        self.assertEqual(validados_nuevo, validados_viejo)
        foto_viejo = self._foto(viejo_conv)
        foto_nuevo = self._foto(nuevo_conv)
        # Los DNI del dataset gemelo están corridos en 1.000: se normalizan para comparar.
        for fila in foto_viejo:
            if fila["dni_titular"]:
                fila["dni_titular"] = str(int(fila["dni_titular"]) + 1_000)
            if isinstance(fila["datos_identificacion"], dict) and fila["datos_identificacion"].get("dni"):
                fila["datos_identificacion"] = {
                    **fila["datos_identificacion"],
                    "dni": str(int(fila["datos_identificacion"]["dni"]) + 1_000),
                }
        self.assertEqual(foto_nuevo, foto_viejo)

    def test_no_pisa_lo_cargado_ni_desvalida_lo_ya_validado(self):
        """Los dos bordes que el cruce nunca puede romper, sobre la versión nueva."""
        convocatoria, relevamiento = self._convocatoria("bordes")
        con_datos = Ciudadano.objects.create(dni="32000001", nombre="Ana", apellido="Ya", genero="F")
        caso_con_datos = Formulario.objects.create(relevamiento=relevamiento, ciudadano=con_datos, celular="3624000000")
        validado = Formulario.objects.create(
            relevamiento=relevamiento,
            ciudadano=Ciudadano.objects.create(dni="32000002", nombre="Beto", apellido="Paz", genero="M"),
            celular="3624000000",
            validado_renaper=True,
            origen_validacion="personas",
        )
        forzado = Formulario.objects.create(
            relevamiento=relevamiento,
            ciudadano=Ciudadano.objects.create(dni="32000003", genero="F"),
            celular="3624000000",
            identidad_forzada=True,
            validado_renaper=True,
            origen_validacion="forzada",
        )

        cargar_padron(
            convocatoria,
            None,
            [
                {"dni": "32000001", "sexo": "F", "nombre": "Otra", "apellido": "Cosa"},
                {"dni": "32000002", "sexo": "M", "nombre": "Otra", "apellido": "Cosa"},
                {"dni": "32000003", "sexo": "F", "nombre": "Otra", "apellido": "Cosa"},
            ],
        )

        caso_con_datos.refresh_from_db()
        caso_con_datos.ciudadano.refresh_from_db()
        self.assertTrue(caso_con_datos.validado_renaper)
        self.assertEqual(caso_con_datos.ciudadano.nombre, "Ana")
        validado.refresh_from_db()
        self.assertEqual(validado.origen_validacion, "personas")
        forzado.refresh_from_db()
        self.assertEqual(forzado.origen_validacion, "forzada")


class InvalidacionDeCacheTests(_BaseCruce):
    """PERF-16: el cruce avisa a la caché del legajo **una vez**, no por ciudadano."""

    def test_el_cruce_invalida_el_legajo_de_cada_ciudadano_una_sola_vez(self):
        convocatoria, relevamiento = self._convocatoria("cache")
        entradas = self._poblar(relevamiento, 5, 33_000_000)
        pks = list(Ciudadano.objects.filter(formularios_becas__relevamiento=relevamiento).values_list("pk", flat=True))
        for pk in pks:
            cache.set(f"ciudadano_{pk}", "viejo", 300)
        cache.set("contar_ciudadanos", 99, 300)

        with self.captureOnCommitCallbacks(execute=True):
            cargar_padron(convocatoria, None, entradas)

        for pk in pks:
            self.assertIsNone(cache.get(f"ciudadano_{pk}"), "el legajo de un ciudadano tocado quedó cacheado viejo")
        # El cruce no crea ni borra ciudadanos: el total de la home no cambió.
        self.assertEqual(cache.get("contar_ciudadanos"), 99)
