"""RED-60 · El runbook de rollback de ``docs/internal/processes.md``.

Lo que había antes mandaba al operador a un comando que ni arranca
(``docker compose exec django``: el servicio se llama ``web``), a revertir
migraciones que traban MariaDB (RED-15) y autorizaba ``--fake``. El runbook
(Anexo D de la auditoría oct-2026) es documentación, así que lo que lo protege es
este test: si alguien lo borra, lo parte o vuelve a autorizar ``--fake``, se pone
rojo.
"""

import re
from pathlib import Path

from django.test import SimpleTestCase

from core.tests.test_barreras_de_reversa import BARRERAS, MARCA

RAIZ = Path(__file__).resolve().parents[2]
PROCESOS = RAIZ / "docs" / "internal" / "processes.md"

PASOS = ("D.0", "D.1", "D.2", "D.2.0", "D.3", "D.4", "D.5")


class RunbookRollbackTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.texto = PROCESOS.read_text(encoding="utf-8")

    def test_estan_los_pasos_del_runbook(self):
        for paso in PASOS:
            with self.subTest(paso=paso):
                self.assertTrue(f"**{paso} " in self.texto, f"falta el paso {paso} del runbook")

    def test_hay_un_comando_de_dump_concreto(self):
        """«Siempre hacer backup» sin comando no es un procedimiento (RED-60)."""
        self.assertTrue("mysqldump" in self.texto, "el runbook no trae el comando de dump")
        self.assertTrue("~/backups/" in self.texto, "el dump no dice dónde se guarda")

    def test_ningun_comando_del_runbook_opera_sobre_development(self):
        """icore-srv y el espejo de ECOM corren `main`; `development` no se despliega."""
        # El `[^\n`]*` corta en la comilla invertida: así un `git pull … main` seguido de
        # una frase sobre `development` no cuenta como comando.
        comandos = re.findall(r"git (?:-C \S+ )?(?:switch|checkout|reset|pull|fetch)[^\n`]*\bdevelopment\b", self.texto)
        self.assertEqual(comandos, [], "el runbook manda a operar sobre la rama de trabajo")

    def test_ningun_comando_apunta_a_un_servicio_inexistente(self):
        """Los servicios del compose son mysql, redis, web, websocket y nginx; `django` no."""
        apuntan_a_django = re.findall(r"docker compose (?:\S+ )*?[a-z]+ (?:-\S+ )*django\b", self.texto)
        self.assertEqual(apuntan_a_django, [], "hay comandos contra un servicio que no existe")

    def test_ninguna_mencion_autoriza_fake(self):
        """Lo que había antes era «usar `--fake` solo si…»; ahora solo puede prohibirse."""
        prohibicion = re.compile(r"\b(nunca|no se usa|ni usar|no usar)\b", re.IGNORECASE)
        plano = " ".join(self.texto.split())
        posiciones = [m.start() for m in re.finditer(r"--fake", plano)]
        self.assertTrue(posiciones, "el runbook tiene que nombrar `--fake` para prohibirlo")
        for posicion in posiciones:
            contexto = plano[max(0, posicion - 140) : posicion + 140]
            with self.subTest(contexto=contexto):
                self.assertRegex(contexto, prohibicion)

    def test_el_paso_d4_lista_todas_las_migraciones_marcadas_barrera(self):
        """Una barrera que el runbook no nombra es una barrera que el operador no ve."""
        self.assertTrue("**D.4 " in self.texto and "**D.5 " in self.texto, "falta el paso D.4")
        d4 = self.texto.split("**D.4 ")[1].split("**D.5 ")[0]
        marcadas = [etiqueta for _, ruta, etiqueta in BARRERAS if MARCA in (RAIZ / ruta).read_text(encoding="utf-8")]
        self.assertEqual(len(marcadas), len(BARRERAS))
        for etiqueta in marcadas:
            with self.subTest(migracion=etiqueta):
                self.assertIn(etiqueta, d4)
