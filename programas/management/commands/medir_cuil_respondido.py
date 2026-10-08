"""Cuántos casos traen un CUIL respondido que no es el que calcula el módulo 11 (G1-11).

La **medición** que pide D-G11, en un comando de **solo lectura**: no hay
``save()``, ``update()`` ni ``delete()`` en este archivo, así que se puede correr
contra una réplica o contra un dump restaurado. El comportamiento del alta no
depende de esta corrida —``siis_envio.cuil_del_caso`` ya prefiere el CUIL real
cuando sus 8 dígitos centrales son el DNI de la persona y es un CUIL válido—; lo
que esto responde es
**a cuántos casos les cambia** lo que viaja a SIIS, que es el dato que el PM
necesita para decidir si hay que revisar los que ya se informaron.

    python manage.py medir_cuil_respondido
    python manage.py medir_cuil_respondido --convocatoria 7 --mostrar 50

Las cinco categorías que informa, por campo (titular y apoderado). Salen de
``siis_envio.evaluar_cuil_respondido``, la misma regla que usa el alta, así que
lo que se cuenta como «difiere» es exactamente lo que viaja distinto:

* **coincide** — el CUIL respondido es exactamente el que da el módulo 11: nada
  cambia para ese caso.
* **difiere** — el respondido es de ese DNI, es un CUIL válido y tiene otro
  prefijo o dígito: son los casos a los que el alta ahora les manda el CUIL
  real. Es el número de D-G11.
* **de otro documento** — 11 dígitos cuyo centro no es el DNI del caso: no se
  usa, se sigue calculando. Vale mirarlo, porque es un dato mal cargado.
* **respondido inválido** — es de ese DNI, pero el prefijo no es uno de los que
  asigna la AFIP o el dígito verificador no cierra: no se usa, se sigue
  calculando. También es un dato mal cargado.
* **sin CUIL** — el campo no está en la foto, está vacío o no tiene 11 dígitos.

Termina siempre en 0: es un informe, no un gate.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from programas.models import Formulario
from programas.services.siis_envio import (
    CUIL_DE_OTRO_DOCUMENTO,
    CUIL_INVALIDO,
    CUIL_SIN_DATO,
    CUIL_USABLE,
    TEXTO_CUIL_APODERADO,
    TEXTO_CUIL_TITULAR,
    _cuil_respondido,
    _digitos,
    calcular_cuil,
    evaluar_cuil_respondido,
)

#: De a cuántos casos se leen las dos columnas JSON pesadas (``definicion`` son
#: ~7 KB por caso). El mismo criterio que el export de G2-01: traer 40.000 fotos
#: en una sola consulta se pasa del ``read_timeout`` de 10 s de ECOM.
LOTE = 500

CATEGORIAS = ("coincide", "difiere", CUIL_DE_OTRO_DOCUMENTO, CUIL_INVALIDO, CUIL_SIN_DATO)


def _clasificar(formulario, texto_campo, dni, sexo):
    """``(categoría, respondido, calculado)`` para un campo de CUIL del caso."""
    respondido = _cuil_respondido(formulario, texto_campo)
    documento = _digitos(dni).zfill(8)[-8:]
    prefijo, digito = calcular_cuil(dni, sexo)
    calculado = f"{prefijo:02d}{documento}{digito}"
    evaluacion = evaluar_cuil_respondido(respondido, dni)
    if evaluacion != CUIL_USABLE:
        return evaluacion, respondido, calculado
    return ("coincide" if respondido == calculado else "difiere"), respondido, calculado


class Command(BaseCommand):
    help = "Mide, sin escribir nada, cuántos casos traen un CUIL respondido distinto del calculado (G1-11 / D-G11)."

    def add_arguments(self, parser):
        parser.add_argument("--convocatoria", type=int, help="Acota la medición a una convocatoria.")
        parser.add_argument(
            "--mostrar",
            type=int,
            default=20,
            help="Cuántos casos de la categoría «difiere» se nombran (0 = ninguno).",
        )

    def handle(self, *args, **opciones):
        alcance = Formulario.objects.all()
        if opciones["convocatoria"]:
            alcance = alcance.filter(relevamiento__convocatoria_id=opciones["convocatoria"])
        pks = list(alcance.values_list("pk", flat=True).order_by("pk"))
        # ``definicion``, ``respuestas`` y ``data`` entran en el ``only`` a
        # propósito: son justo lo que ``_cuil_respondido`` lee, y sin ellas cada
        # caso dispararía su propia consulta para traer el campo diferido.
        casos = Formulario.objects.select_related("ciudadano").only(
            "id",
            "numero",
            "definicion",
            "respuestas",
            "data",
            "apoderado_dni",
            "apoderado_genero",
            "ciudadano__dni",
            "ciudadano__genero",
        )

        cuenta = {campo: dict.fromkeys(CATEGORIAS, 0) for campo in ("titular", "apoderado")}
        ejemplos = {"titular": [], "apoderado": []}
        for inicio in range(0, len(pks), LOTE):
            lote = casos.filter(pk__in=pks[inicio : inicio + LOTE])
            for formulario in lote:
                ciudadano = formulario.ciudadano
                self._medir(
                    formulario,
                    "titular",
                    TEXTO_CUIL_TITULAR,
                    ciudadano.dni if ciudadano else "",
                    ciudadano.genero if ciudadano else "",
                    cuenta,
                    ejemplos,
                )
                self._medir(
                    formulario,
                    "apoderado",
                    TEXTO_CUIL_APODERADO,
                    formulario.apoderado_dni,
                    formulario.apoderado_genero,
                    cuenta,
                    ejemplos,
                )

        self.stdout.write(f"Casos medidos: {len(pks)}")
        for campo in ("titular", "apoderado"):
            self.stdout.write(f"\n{campo.capitalize()}:")
            for categoria in CATEGORIAS:
                self.stdout.write(f"   {categoria:22} {cuenta[campo][categoria]:8}")
            tope = opciones["mostrar"]
            if tope and ejemplos[campo]:
                self.stdout.write(f"   casos que difieren (hasta {tope}): " + ", ".join(ejemplos[campo][:tope]))

    def _medir(self, formulario, campo, texto, dni, sexo, cuenta, ejemplos):
        if not _digitos(dni):
            cuenta[campo][CUIL_SIN_DATO] += 1
            return
        categoria, respondido, calculado = _clasificar(formulario, texto, dni, sexo)
        cuenta[campo][categoria] += 1
        if categoria == "difiere":
            # Sin el CUIL ni el DNI en la salida: son datos personales y esto se
            # corre contra PRD. Alcanza con el número de caso y los dos prefijos,
            # que es lo que hay que mirar.
            ejemplos[campo].append(f"{formulario.numero or formulario.pk} ({calculado[:2]}→{respondido[:2]})")
