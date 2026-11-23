"""Marca «Emergencia · Caso N» de las estadías que nacieron de un caso de Emergencia (Cambio 575).

Una estadía es «de Emergencia» si cuelga de un ``IntegranteGrupo`` (``estadia``) de un ``CasoEmergencia``. Se resuelve
con **una consulta fija por lista**, partiendo del lado chico (los integrantes con estadía de la página), sin
consultar por fila. El nombre de la familia solo viaja si quien mira puede ver ciudadanos: sin esa capacidad ni
se lee de la base.
"""

from django.db.models import Q

from programas.models import IntegranteGrupo


def q_estadias_de_emergencia():
    """Las estadías que cuelgan de un integrante de un caso de Emergencia (filtro «Origen: Emergencia»).

    Parte del lado chico: los integrantes con estadía; evita un ``Exists`` correlacionado sobre ``Estadia``.
    """

    return Q(pk__in=IntegranteGrupo.objects.filter(estadia__isnull=False).values("estadia_id"))


def marcas_de_emergencia(estadia_ids, *, con_familia):
    """``{estadia_id: {"numero", "caso_pk", "familia"}}`` para las estadías de Emergencia entre las pedidas.

    ``familia`` es ``"Familia <apellido>"`` solo con ``con_familia``; si no, queda vacía y la columna del apellido
    no se pide a la base.
    """

    ids = list(estadia_ids)
    if not ids:
        return {}
    campos = ["estadia_id", "grupo__caso__pk", "grupo__caso__numero"]
    if con_familia:
        campos.append("grupo__responsable__apellido")
    marcas = {}
    for fila in IntegranteGrupo.objects.filter(estadia_id__in=ids).order_by("pk").values(*campos):
        apellido = fila.get("grupo__responsable__apellido") or ""
        marcas.setdefault(
            fila["estadia_id"],
            {
                "numero": fila["grupo__caso__numero"],
                "caso_pk": fila["grupo__caso__pk"],
                "familia": f"Familia {apellido}" if apellido else "",
            },
        )
    return marcas
