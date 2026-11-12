"""Señales de dominio de `programas`: hechos del negocio, no eventos del ORM.

Viven en un módulo sin imports del proyecto a propósito: las emite un servicio
(`programas.services.estadias`) y las recibe otro (Emergencia), y `programas.signals`
—que registra receptores sobre modelos e importa servicios— no puede ser importado por
un servicio sin arriesgar un ciclo. Acá solo se **definen**; quién las recibe se conecta
en su propio módulo.
"""

from django.dispatch import Signal

#: Una persona egresó de un dispositivo. La envía `estadias.egresar_persona` **dentro de
#: su transacción**, al final —con la estadía ya cerrada, su movimiento, su novedad de
#: bitácora y su traza escritos—, con ``send`` y no ``send_robust``: un receptor que lanza
#: una excepción **deshace el egreso**. Es intencional: lo que el receptor escribe (en
#: Emergencia, `IntegranteGrupo.egresado_en` y el cierre del caso) y el egreso son un solo
#: hecho, y es preferible un egreso que no se registra y avisa a uno que queda a medias.
#:
#: Argumentos: ``sender`` es el modelo `Estadia`; ``estadia``, la estadía ya egresada
#: (releída con bloqueo por el servicio); ``usuario``, quien registró el egreso.
#:
#: Un receptor corre con la fila de la estadía bloqueada: lo que bloquee tiene que venir
#: **después** de la estadía en el orden de candados, y no puede hacer E/S lenta.
estadia_egresada = Signal()
