"""Precondición de la excepción temporal CVE-2026-83813 (PR #988)."""

import json
import subprocess
import sys

from django.test import SimpleTestCase


class ResolverDaphneTests(SimpleTestCase):
    def test_daphne_usa_dns_del_sistema_sin_twisted_names(self):
        # Un proceso limpio evita que el reactor o imports de otros tests
        # oculten un cambio en el arranque real de Daphne.
        codigo = """
import json
import socket
import sys
import daphne.server
import daphne.http_protocol
import daphne.ws_protocol
import channels.layers
from twisted.internet import reactor
print(json.dumps({
    "resolver": type(reactor.nameResolver).__name__,
    "modulo": type(reactor.nameResolver).__module__,
    "getaddrinfo_del_sistema": reactor.nameResolver._getaddrinfo is socket.getaddrinfo,
    "names_cargado": any(n == "twisted.names" or n.startswith("twisted.names.") for n in sys.modules),
}))
"""
        resultado = subprocess.run(
            [sys.executable, "-c", codigo], capture_output=True, text=True, timeout=30, check=True
        )
        datos = json.loads(resultado.stdout)
        self.assertEqual(datos["resolver"], "GAIResolver")
        self.assertEqual(datos["modulo"], "twisted.internet._resolver")
        self.assertTrue(datos["getaddrinfo_del_sistema"])
        self.assertFalse(datos["names_cargado"])
