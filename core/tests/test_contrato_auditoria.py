"""Toda ficha de la auditoría cerrada deja un test que existe de verdad (RED-34).

El cierre de cada ola estaba definido como «las PoC invertidas pasan»: una
verificación **manual**, sin ningún guard. Y las PoC viven bajo `docs/`, que el runner
no descubre —`unittest.defaultTestLoader.discover('docs')` devuelve **0 tests**— y
además la mayoría *afirma el bug*, así que tampoco se pueden mover al código tal cual.

El agujero concreto: cerrar una ficha invirtiendo su PoC y mergear sin tocar
`<app>/tests/` deja la ficha en ✅ y el bug vuelve el día que alguien toque el módulo,
sin que nada se ponga rojo.

La regla (README §0.3, desde el 04-oct-2026): debajo de cada «Resolución:» va la línea
**«Test permanente: `<app>/tests/<archivo>::<Clase>.<test>`»**. Este módulo la
verifica: toma las fichas resueltas a partir de esa fecha y exige que el módulo, la
clase y el método nombrados **existan** (import + `getattr`). No corre los tests
nombrados —eso lo hace la suite— sino que impide que la línea apunte a un nombre
inventado, renombrado o borrado.

Formato aceptado (los dos están en uso en `hallazgos/`):

* `app/tests/modulo.py::Clase.test_algo`
* `app.tests.modulo.Clase.test_algo` (y las formas cortas: solo módulo, o módulo+clase)

No toca la red ni la base: todo sale de archivos del repo.
"""

import datetime
import importlib
import importlib.util
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

HALLAZGOS = Path(settings.BASE_DIR) / "docs" / "internal" / "auditoria-2026-10" / "hallazgos"

#: Desde cuándo rige la regla. Las fichas cerradas antes (Ola 0, 01 y 03-oct-2026)
#: no la tienen y no se les exige retroactivamente: son 18 y están todas con fecha.
DESDE = datetime.date(2026, 10, 4)

_FICHA = re.compile(r"^### (?P<id>[A-Za-z0-9-]+) · ", re.M)
_RESOLUCION = re.compile(r"\*\*Resolución:\*\*\s*(?P<cuerpo>[^\n]*)")
#: El primer target entre backticks después del rótulo (la línea puede seguir con
#: «(y …)» nombrando los demás; el primero es el que la regla exige).
_TEST_PERMANENTE = re.compile(r"\*\*Test permanente:\*\*\s*\n?\s*`(?P<target>[^`]+)`")
#: Las dos formas que conviven en `hallazgos/`: `06-oct-2026` y `06-10-2026`.
_FECHA = re.compile(r"(?P<dia>\d{1,2})-(?P<mes>[a-z]{3}|\d{1,2})-(?P<anio>\d{4})")

_MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}  # fmt: skip


def _fecha_de(texto):
    m = _FECHA.search(texto)
    if not m:
        return None
    mes = _MESES.get(m.group("mes")) if not m.group("mes").isdigit() else int(m.group("mes"))
    if not mes or not 1 <= mes <= 12:
        return None
    return datetime.date(int(m.group("anio")), mes, int(m.group("dia")))


def fichas_resueltas():
    """`[(archivo, id, cuerpo de la Resolución, target o None)]` de todo `hallazgos/`."""
    salida = []
    for ruta in sorted(HALLAZGOS.glob("*.md")):
        texto = ruta.read_text(encoding="utf-8")
        cortes = [(m.start(), m.group("id")) for m in _FICHA.finditer(texto)]
        cortes.append((len(texto), None))
        for (inicio, ficha_id), (fin, _) in zip(cortes, cortes[1:]):
            cuerpo = texto[inicio:fin]
            resolucion = _RESOLUCION.search(cuerpo)
            if not resolucion:
                continue
            target = _TEST_PERMANENTE.search(cuerpo)
            salida.append(
                (
                    ruta.name,
                    ficha_id,
                    resolucion.group("cuerpo"),
                    target.group("target") if target else None,
                )
            )
    return salida


def _cargar_script_suelto(ruta_relativa):
    """Carga un `.py` que no es parte de ningún paquete, con su carpeta en `sys.path`."""
    import sys

    ruta = Path(settings.BASE_DIR) / ruta_relativa
    if not ruta.is_file():
        return None
    spec = importlib.util.spec_from_file_location(ruta.stem, ruta)
    modulo = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ruta.parent))
    try:
        spec.loader.exec_module(modulo)
    except Exception:  # noqa: BLE001 — el detalle lo da el AssertionError del llamador
        return None
    finally:
        sys.path.remove(str(ruta.parent))
    return modulo


def resolver(target):
    """Resuelve el target a objetos reales. Devuelve `(modulo, clase, metodo)`.

    Levanta `AssertionError` con el detalle de qué parte no existe. La parte difícil
    es la forma punteada: `a.b.c.D.test_x` no dice dónde termina el módulo, así que se
    importa el prefijo más largo que importe y el resto se busca por `getattr`.
    """
    if "::" in target:
        archivo, resto = target.split("::", 1)
        nombre_modulo = archivo.removesuffix(".py").replace("/", ".").replace("\\", ".")
        partes = [nombre_modulo, *resto.split(".")]
    else:
        partes = target.split(".")

    modulo = None
    usadas = 0
    for corte in range(len(partes), 0, -1):
        try:
            modulo = importlib.import_module(".".join(partes[:corte]))
        except ImportError:
            continue
        usadas = corte
        break
    if modulo is None and "::" in target:
        # Tests que **no** descubre el runner de Django y aun así son permanentes
        # porque los corre un job del CI: hoy `scripts/test_design_audit.py`, que
        # ejecuta el job obligatorio `Validate inventory and authority` con
        # `python scripts/test_design_audit.py` y que importa sus vecinos como
        # módulos de primer nivel (`import design_audit`).
        modulo = _cargar_script_suelto(target.split("::", 1)[0])
        usadas = 1
    if modulo is None:
        raise AssertionError(f"no existe ningún módulo importable en `{target}`")

    objeto = modulo
    clase = metodo = None
    recorrido = ".".join(partes[:usadas])
    for parte in partes[usadas:]:
        if not hasattr(objeto, parte):
            raise AssertionError(f"`{recorrido}` no tiene `{parte}` (target: `{target}`)")
        objeto = getattr(objeto, parte)
        recorrido = f"{recorrido}.{parte}"
        if isinstance(objeto, type):
            clase = objeto
        else:
            metodo = objeto
    return modulo, clase, metodo


class FichasCerradasTests(SimpleTestCase):
    """RED-34: la línea «Test permanente» no puede apuntar a algo que no existe."""

    def test_toda_ficha_resuelta_nombra_un_test_que_existe(self):
        rotas = []
        for archivo, ficha_id, _, target in fichas_resueltas():
            if target is None:
                continue
            try:
                resolver(target)
            except AssertionError as error:
                rotas.append(f"{archivo} · {ficha_id}: {error}")

        self.assertEqual(
            rotas,
            [],
            "Estas fichas nombran un «Test permanente» que no existe. Si el test se "
            "renombró o se movió, actualizá la ficha en el mismo diff:\n  " + "\n  ".join(rotas),
        )

    def test_toda_ficha_resuelta_desde_el_04_oct_declara_su_test_permanente(self):
        """La otra mitad de la regla: que la línea **esté**.

        Sin esto, cerrar una ficha sin dejar test sigue siendo gratis: basta con no
        escribir la línea y el test de arriba no tiene qué revisar.
        """
        sin_declarar = []
        for archivo, ficha_id, resolucion, target in fichas_resueltas():
            if target is not None:
                continue
            fecha = _fecha_de(resolucion)
            if fecha is None or fecha < DESDE:
                continue
            sin_declarar.append(f"{archivo} · {ficha_id} ({fecha.isoformat()})")

        self.assertEqual(
            sin_declarar,
            [],
            "Estas fichas se cerraron sin la línea «**Test permanente:** "
            "`<app>/tests/<archivo>::<Clase>.<test>`» que pide el README §0.3 "
            f"(regla vigente desde el {DESDE.isoformat()}):\n  " + "\n  ".join(sin_declarar),
        )

    def test_toda_resolucion_lleva_fecha(self):
        """Sin fecha no se puede saber si le toca la regla: la línea queda exenta para
        siempre. Las ocho fichas anteriores al 04-oct también la tienen."""
        sin_fecha = [
            f"{archivo} · {ficha_id}"
            for archivo, ficha_id, resolucion, _ in fichas_resueltas()
            if _fecha_de(resolucion) is None
        ]

        self.assertEqual(sin_fecha, [])

    def test_las_poc_siguen_sin_ser_descubiertas_por_el_runner(self):
        """La premisa de la ficha, afirmada: `docs/` no aporta ni un test.

        Si algún día `docs/` empezara a descubrirse, esta regla cambiaría de sentido
        (las PoC afirman el bug: correrlas sería tener la suite en rojo a propósito).
        """
        import unittest

        suite = unittest.defaultTestLoader.discover(str(Path(settings.BASE_DIR) / "docs"))

        self.assertEqual(suite.countTestCases(), 0)


class PrechequeoP04Tests(SimpleTestCase):
    """R0b-03: el pre-chequeo P-04 no puede volver a los `JOIN` que lo dejaban ciego.

    P-04 es SQL de solo lectura que corre el PM contra PRD (R0b-12), así que su
    única superficie es el README: la ficha no deja código que testear y sin esto
    se cierra sin nada que la sostenga. Lo que se afirma es justo lo que estaba
    mal: con `JOIN programas_programa` quedaban afuera los roles **sin programa**
    (Backoffice y Sistema) y con `JOIN users_rolmeta` los grupos **sin `RolMeta`**
    —las dos cosas que `puede_gestionar_credenciales` cuenta como fuera de alcance,
    o sea exactamente las cuentas que la consulta tenía que encontrar—.
    """

    @staticmethod
    def _sql_de_p04():
        readme = (Path(settings.BASE_DIR) / "docs" / "internal" / "auditoria-2026-10" / "README.md").read_text(
            encoding="utf-8"
        )
        bloque = re.search(r"\*\*P-04 · .*?```sql\n(?P<sql>.*?)```", readme, re.S)
        assert bloque, "P-04 ya no está en el README §3"
        return bloque.group("sql")

    def test_las_dos_consultas_llegan_a_rolmeta_y_a_programa_con_left_join(self):
        sql = self._sql_de_p04()

        self.assertEqual(sql.count("LEFT JOIN users_rolmeta"), 2)
        self.assertIn("LEFT JOIN programas_programa", sql)
        self.assertNotIn("\n  JOIN users_rolmeta", sql)
        self.assertNotIn("\n  JOIN programas_programa", sql)

    def test_la_segunda_consulta_lista_las_cuentas_que_quedaban_invisibles(self):
        sql = self._sql_de_p04()

        for columna in ("roles_sin_programa", "roles_sin_meta", "roles_desactivados"):
            with self.subTest(columna=columna):
                self.assertIn(columna, sql)


class ParserDelContratoTests(SimpleTestCase):
    """Control del andamio: si el parser dejara de ver las fichas o de resolver los
    targets, los tests de arriba quedarían verdes sin afirmar nada."""

    def test_encuentra_las_fichas_resueltas_de_los_ocho_archivos(self):
        resueltas = fichas_resueltas()

        self.assertGreater(len(resueltas), 100)
        self.assertGreaterEqual(len({archivo for archivo, *_ in resueltas}), 6)

    def test_la_mayoria_declara_su_test_permanente(self):
        con_target = [f for f in fichas_resueltas() if f[3] is not None]

        self.assertGreater(len(con_target), 100)

    def test_resuelve_las_dos_formas_de_escribir_un_target(self):
        por_ruta = resolver(
            "core/tests/test_contrato_auditoria.py::FichasCerradasTests.test_toda_resolucion_lleva_fecha"
        )
        punteado = resolver("core.tests.test_contrato_auditoria.FichasCerradasTests.test_toda_resolucion_lleva_fecha")

        self.assertEqual(por_ruta[1], FichasCerradasTests)
        self.assertEqual(punteado[1], FichasCerradasTests)

    def test_un_target_inventado_se_reporta(self):
        for target, esperado in (
            ("core/tests/test_contrato_auditoria.py::ClaseQueNoExiste.test_x", "no tiene `ClaseQueNoExiste`"),
            ("core.tests.test_contrato_auditoria.FichasCerradasTests.test_que_no_existe", "test_que_no_existe"),
            ("app.inexistente.modulo", "no existe ningún módulo importable"),
        ):
            with self.subTest(target=target):
                with self.assertRaises(AssertionError) as capturado:
                    resolver(target)

                self.assertIn(esperado, str(capturado.exception))
