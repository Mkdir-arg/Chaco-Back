"""«Quién ve al agente asignado» de un relevamiento tiene un solo dueño (D-LIM-01, regla R-5).

El dueño es `programas.services.inspecciones` (`ve_la_asignacion`, `ve_la_asignacion_en_lote`,
`q_asignacion_visible`). Antes la vista de P21 reescribía la regla para la columna y las
opciones, y el filtro «Asignado a» y los contadores de las solapas no la aplicaban: quien no
ve la asignación podía deducir, filtrando, a qué agente va un relevamiento que la fila oculta
(Cambio 428). Un dato que la vista oculta por permiso tampoco puede usarse como filtro.

1. Funcional: sin la capacidad, el filtro no devuelve filas ni conteos de lo oculto; con ella
   se ve lo mismo que antes.
2. La vista consulta la regla del servicio (se la reemplaza y se mira el efecto).
3. Un solo dueño: ningún `.py` de vistas o selectores toca `asignado_a`/`agente_asignado`
   fuera de una lista congelada.
"""

import re
from pathlib import Path
from unittest import mock

from programas.models import InspeccionEdificio, MiembroEquipoDispositivo
from programas.services import inspecciones as servicio
from programas.tests.test_dispositivos_inspecciones import TODAS_DE_DISPOSITIVOS
from programas.tests.test_dispositivos_relevamientos_listado import URL_LISTA, BaseListado, _filas, _solapa

RAIZ = Path(__file__).resolve().parents[1]


class FiltroAsignadoANoRevelaTests(BaseListado):
    def setUp(self):
        super().setUp()
        # Mismo armado que `PrivacidadAsignacionTests`: el lector coordina A, y solo lee B (Equipo del CIS).
        capacidades = [c for c in TODAS_DE_DISPOSITIVOS if c != "programa.configurar"]
        self.lector = self._usuario("lector_ag", capacidades, [self.parador])
        rol_b = self._usuario("lector_b_ag", [c for c in capacidades if c != "inspeccion.asignar"], [self.cis])
        self.lector.groups.add(*rol_b.groups.all())
        MiembroEquipoDispositivo.objects.create(dispositivo=self.cis, usuario=self.lector, rol=rol_b.groups.get())
        admin = self._usuario("admin_creador_ag", TODAS_DE_DISPOSITIVOS)
        # Relevamiento de B (el lector no ve la asignación) y de A (sí la ve), ambos del mismo agente.
        self.oculto = servicio.crear_inspeccion(
            admin, edificio=self.edificio_cis, asignado_a=self.agente, fecha_vencimiento=self.vence
        )
        self.visible = self._crear(agente=self.agente)
        self.visible_otro = self._crear(edificio=self._edificio_del_parador("ED-X"), agente=self.otro_agente)

    def test_sin_la_regla_el_filtro_no_trae_filas_ni_conteos_de_lo_oculto(self):
        respuesta = self._cliente(self.lector).get(URL_LISTA, {"asignado_a": self.agente.pk})
        self.assertEqual({r.pk for r in _filas(respuesta)}, {self.visible.pk})
        self.assertEqual(_solapa(respuesta, "en_curso")["total"], 1)

    def test_el_filtro_por_un_agente_cuya_unica_asignacion_esta_oculta_devuelve_vacio(self):
        InspeccionEdificio.objects.filter(pk=self.visible.pk).update(asignado_a=self.otro_agente)
        respuesta = self._cliente(self.lector).get(URL_LISTA, {"asignado_a": self.agente.pk})
        self.assertEqual(_filas(respuesta), [])
        self.assertEqual(_solapa(respuesta, "en_curso")["total"], 0)

    def test_quien_coordina_ve_lo_mismo_que_antes(self):
        # Configurar da alcance global: el filtro devuelve las dos asignaciones del agente.
        coordinador = self._usuario("coord_total", TODAS_DE_DISPOSITIVOS)
        respuesta = self._cliente(coordinador).get(URL_LISTA, {"asignado_a": self.agente.pk})
        self.assertEqual({r.pk for r in _filas(respuesta)}, {self.oculto.pk, self.visible.pk})
        self.assertEqual(_solapa(respuesta, "en_curso")["total"], 2)

    def test_la_vista_consulta_la_regla_del_servicio(self):
        cliente = self._cliente(self.lector)
        # Regla reemplazada por «nadie ve ninguna asignación»: el filtro por el agente no encuentra nada.
        with mock.patch(
            "programas.views.dispositivos_relevamientos.q_asignacion_visible",
            return_value=servicio.Q(pk__in=[]),
        ):
            respuesta = cliente.get(URL_LISTA, {"asignado_a": self.agente.pk})
        self.assertEqual(_filas(respuesta), [])
        self.assertEqual(_solapa(respuesta, "en_curso")["total"], 0)
        # Y la columna sigue el lote del servicio: si nadie ve ninguna, ningún nombre sale.
        with mock.patch("programas.views.dispositivos_relevamientos.ve_la_asignacion_en_lote", return_value=set()):
            respuesta = cliente.get(URL_LISTA)
        filas = _filas(respuesta)
        self.assertTrue(filas)
        self.assertTrue(all(not r.agente_visible for r in filas))

    def test_el_lote_coincide_con_la_regla_por_relevamiento(self):
        for usuario in (self.lector, self.agente, self.otro_agente, self.coord):
            fresco = self._fresco(usuario)
            todos = list(InspeccionEdificio.objects.all())
            esperado = {r.pk for r in todos if servicio.ve_la_asignacion(fresco, r)}
            self.assertEqual(servicio.ve_la_asignacion_en_lote(fresco, todos), esperado, usuario.username)


# Líneas (sin sangría) de vistas y selectores que nombran al agente asignado. Congelada: sumar
# una exige decir por qué no es la regla de visibilidad reescrita. Los templates quedan fuera:
# imprimen lo que la vista ya decidió mostrar (`agente_visible`).
PERMITIDAS = {
    "views/dispositivos_relevamientos.py": {
        # Parámetro GET y píldora: el valor se acota con `q_asignacion_visible`.
        'PARAMETROS_DE_VISTA = ("tab", "estado", "asignado_a")',
        'asignado_id = _entero(params.get("asignado_a"))',
        "asignado_a_id=asignado_id,",
        "base = base.filter(Q(asignado_a_id=asignado_id) & asignacion_visible)",
        'agentes = get_user_model().objects.filter(pk__in=asignaciones_visibles.values("asignado_a"))',
        '"nombre": "asignado_a",',
        # Sin-relevar: el relevamiento en curso del edificio, con el nombre ya pasado por `_nombre`.
        "if edificio.asignado_a:",
        '"valor": edificio.asignado_a,',
        'edificio.asignado_a = _nombre(relevamiento.asignado_a) if relevamiento else ""',
        # Lectura del nombre, decidida por `ve_la_asignacion_en_lote`.
        'relevamiento.agente_visible = _nombre(relevamiento.asignado_a) if ve_asignacion else ""',
        # Carga de la relación (no decide visibilidad).
        'base = visibles.select_related("edificio", "asignado_a", "revisado_por")',
        ').select_related("edificio", "asignado_a")',
        'inspecciones_visibles(user).select_related("edificio", "asignado_a", "realizada_por", "revisado_por"),',
        'inspecciones_visibles(self.request.user).select_related("edificio", "asignado_a"), pk=pk',
        # Escritura: alta y reasignación por el servicio, con el agente que eligió el coordinador.
        'asignado_a=datos["asignado_a"],',
        'return self._creado(edificio, datos["asignado_a"])',
        'agente = form.cleaned_data["asignado_a"]',
    },
    "selectors/edificios.py": {
        # Carga de la relación para la solapa «sin relevar».
        '.select_related("edificio", "asignado_a", "realizada_por", "revisado_por"),',
    },
    "selectors/auditoria_dispositivo.py": {
        # DEUDA CONOCIDA: segunda copia de «coordina el edificio o es el agente» en el Historial.
        # Misma regla, sin filtro ni contador: se unifica con el servicio en su propia ficha.
        "or (usuario_id is not None and traza.inspeccion.asignado_a_id == usuario_id),",
    },
}


class UnSoloDuenoTests(BaseListado):
    def test_solo_el_dueno_y_la_lista_congelada_nombran_al_agente_asignado(self):
        patron = re.compile(r"asignado_a|agente_asignado")
        encontrados = {}
        for carpeta in ("views", "selectors"):
            for archivo in sorted((RAIZ / carpeta).rglob("*.py")):
                clave = f"{carpeta}/{archivo.relative_to(RAIZ / carpeta).as_posix()}"
                for linea in archivo.read_text(encoding="utf-8").splitlines():
                    if patron.search(linea):
                        encontrados.setdefault(clave, set()).add(linea.strip())
        nuevas = {
            archivo: sorted(lineas - PERMITIDAS.get(archivo, set()))
            for archivo, lineas in encontrados.items()
            if lineas - PERMITIDAS.get(archivo, set())
        }
        self.assertEqual(
            nuevas,
            {},
            "«Quién ve al agente asignado» vive en programas/services/inspecciones.py "
            "(ve_la_asignacion, ve_la_asignacion_en_lote, q_asignacion_visible). Usá esa regla.",
        )
        # La lista no acumula líneas que ya no existen.
        sobrantes = {a: sorted(ls - encontrados.get(a, set())) for a, ls in PERMITIDAS.items()}
        self.assertEqual({a: ls for a, ls in sobrantes.items() if ls}, {}, "Líneas de la lista que ya no están")
