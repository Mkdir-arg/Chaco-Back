"""Simulaciones deterministas de dependencias externas para performance CI."""

import time
from dataclasses import dataclass

from core.performance.query_observability import instrument_external_call

EXTERNAL_DEPENDENCIES = frozenset({"siis", "personas", "renaper"})


@dataclass(frozen=True)
class SimulatedExternalResponse:
    status_code: int


def simulate_external_call(dependency, *, latency_seconds=0, status_code=200):
    """Registra una respuesta sintética sin ejecutar un cliente de red real."""
    if dependency not in EXTERNAL_DEPENDENCIES:
        raise ValueError(f"Dependencia externa no soportada por performance CI: {dependency}")
    if latency_seconds < 0:
        raise ValueError("La latencia simulada no puede ser negativa.")

    def response():
        if latency_seconds:
            time.sleep(latency_seconds)
        return SimulatedExternalResponse(status_code=status_code)

    return instrument_external_call(dependency, response)
