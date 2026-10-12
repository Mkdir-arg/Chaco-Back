"""Consultas de lectura de `programas`, sin lógica de negocio.

El corte de capas del repo (ver `CLAUDE.md`) es
`models → selectors → services → views`: acá vive lo que **arma el contexto de
una pantalla** leyendo la base, y en `services/` lo que decide y escribe.
`programas` era la única app de dominio sin este paquete; lo abre RED-54 (Ola 7),
sacando de `views/revision.py` los tres bloques que arman el detalle del caso.

Los submódulos no se re-exportan acá a propósito: `from programas.selectors
import revision` deja a la vista el módulo del que sale cada cosa.
"""
