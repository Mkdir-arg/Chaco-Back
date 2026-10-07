"""Revisa la forma de los JSON guardados, **sin escribir nada** (RED-40).

Ocho `JSONField` del dominio de Becas guardan estructuras con contrato
implícito: el modelo acepta cualquier cosa (`validators` = 0) y la forma la
sostiene el código que escribe. Renombrar `presentacion` → `modo_presentacion`
en `ItemDiseno.propio` deja **todos los selectores propios ya guardados**
volviendo a «LISTA» —`propio.get("presentacion", "LISTA")`— sin un solo error.

Este comando es la foto que hay que sacar **antes** de cualquier cambio de forma,
contra un dump de producción restaurado en una base local:

    python manage.py verificar_json_guardado
    python manage.py verificar_json_guardado --json > antes.json

Qué mira:

1. **Condiciones** (`ItemDiseno.condicion`, `GrupoRequisito.condicion_defecto`):
   forma, `modo` válido, reglas con `fuente`/`op`, y operadores que no existen en
   `OPERADORES_POR_TIPO` —ni para ningún tipo de campo—. Un operador desconocido
   cae al `return False` final de `evaluar_regla`: el ítem condicionado **no se
   muestra nunca** y una pregunta obligatoria queda sin responder.
2. **Campos propios** (`ItemDiseno.propio`): sin `tipo` (el constructor no sabe
   qué dibujar), sin `presentacion` (forma anterior al Cambio 56), `opciones` que
   no es lista en un selector.
3. **Fotos de la definición** (`Formulario.definicion`): sin `version`/`items`,
   que es la forma plana anterior al Cambio 58.
4. **Correcciones para SIIS** (`Formulario.datos_siis`): claves que
   `armar_payload` **no consume** —lo cargado ahí nunca llega a SIIS y el
   coordinador cree que sí—.

Es de **solo lectura**: no hay `save()`, `update()` ni `delete()` en este
archivo, y por eso se puede correr contra una réplica. Termina en 0 siempre (es
un informe, no un gate); lo que decide es el conteo.
"""

import json

from django.core.management.base import BaseCommand

from programas.forms import DatosSiisForm
from programas.models import Formulario, GrupoRequisito, ItemDiseno
from programas.services.condiciones import MODOS, OPERADORES_POR_TIPO

#: Todo operador que `evaluar_regla` sabe resolver, sin importar el tipo fuente.
OPERADORES_CONOCIDOS = set().union(*OPERADORES_POR_TIPO.values())

#: Claves del apoderado que `siis_envio._apoderado` lee de `datos_siis`. No salen
#: de `DatosSiisForm` (las escribe `corregir_datos_siis`), así que van a mano;
#: `test_json_compatibilidad` verifica que la lista siga completa.
CLAVES_APODERADO = (
    "dni_apoderado",
    "nombre_apoderado",
    "apellido_apoderado",
    "sexo_apoderado",
    "fecha_nacim_apoderado",
)

#: Lo que `armar_payload` consume de `Formulario.datos_siis`.
CLAVES_SIIS_CONSUMIDAS = frozenset(DatosSiisForm.CAMPOS) | frozenset(CLAVES_APODERADO)

LOTE = 500


def _problemas_de_condicion(condicion, donde):
    """Lista de problemas de una condición guardada. Vacía = sana."""
    if condicion in (None, {}, []):
        return []
    if not isinstance(condicion, dict):
        return [{"donde": donde, "problema": "condicion_no_es_objeto", "detalle": type(condicion).__name__}]

    problemas = []
    modo = condicion.get("modo")
    if modo not in MODOS:
        problemas.append({"donde": donde, "problema": "modo_desconocido", "detalle": repr(modo)})

    reglas = condicion.get("reglas")
    if not isinstance(reglas, list):
        problemas.append({"donde": donde, "problema": "reglas_no_es_lista", "detalle": type(reglas).__name__})
        return problemas

    for indice, regla in enumerate(reglas):
        ubicacion = f"{donde}[{indice}]"
        if not isinstance(regla, dict):
            problemas.append({"donde": ubicacion, "problema": "regla_no_es_objeto", "detalle": type(regla).__name__})
            continue
        if not regla.get("fuente"):
            problemas.append({"donde": ubicacion, "problema": "regla_sin_fuente", "detalle": ""})
        operador = regla.get("op")
        if operador not in OPERADORES_CONOCIDOS:
            # El que más duele: `evaluar_regla` devuelve False y el ítem no
            # aparece nunca.
            problemas.append({"donde": ubicacion, "problema": "operador_desconocido", "detalle": repr(operador)})
    return problemas


def _problemas_de_propio(propio, donde):
    if propio in (None, {}):
        return []
    if not isinstance(propio, dict):
        return [{"donde": donde, "problema": "propio_no_es_objeto", "detalle": type(propio).__name__}]

    problemas = []
    if not propio.get("tipo"):
        problemas.append({"donde": donde, "problema": "propio_sin_tipo", "detalle": ""})
    if "presentacion" not in propio:
        # Forma anterior al Cambio 56: se lee con default "LISTA".
        problemas.append({"donde": donde, "problema": "propio_sin_presentacion", "detalle": ""})
    opciones = propio.get("opciones")
    if opciones is not None and not isinstance(opciones, list):
        problemas.append({"donde": donde, "problema": "opciones_no_es_lista", "detalle": type(opciones).__name__})
    return problemas


def _problemas_de_definicion(definicion, donde):
    if definicion in (None, {}):
        return []
    if not isinstance(definicion, dict):
        return [{"donde": donde, "problema": "definicion_no_es_objeto", "detalle": type(definicion).__name__}]

    problemas = []
    if "items" not in definicion:
        # Forma plana anterior al Cambio 58: solo `globales` y `requisitos`.
        problemas.append({"donde": donde, "problema": "definicion_sin_items", "detalle": ""})
    if "version" not in definicion:
        problemas.append({"donde": donde, "problema": "definicion_sin_version", "detalle": ""})
    return problemas


def _problemas_de_datos_siis(datos, donde):
    if datos in (None, {}):
        return []
    if not isinstance(datos, dict):
        return [{"donde": donde, "problema": "datos_siis_no_es_objeto", "detalle": type(datos).__name__}]

    sobrantes = sorted(set(datos) - CLAVES_SIIS_CONSUMIDAS)
    if sobrantes:
        return [{"donde": donde, "problema": "datos_siis_con_claves_no_consumidas", "detalle": ", ".join(sobrantes)}]
    return []


def revisar():
    """Todos los problemas encontrados. Solo lecturas, en lotes."""
    problemas = []

    for item in ItemDiseno.objects.only("id", "clave", "condicion", "propio").order_by("pk").iterator(chunk_size=LOTE):
        donde = f"ItemDiseno#{item.pk} ({item.clave})"
        problemas += _problemas_de_condicion(item.condicion, f"{donde}.condicion")
        problemas += _problemas_de_propio(item.propio, f"{donde}.propio")

    for grupo in (
        GrupoRequisito.objects.only("id", "clave", "condicion_defecto").order_by("pk").iterator(chunk_size=LOTE)
    ):
        problemas += _problemas_de_condicion(
            grupo.condicion_defecto, f"GrupoRequisito#{grupo.pk} ({grupo.clave}).condicion_defecto"
        )

    for caso in Formulario.objects.only("id", "definicion", "datos_siis").order_by("pk").iterator(chunk_size=LOTE):
        donde = f"Formulario#{caso.pk}"
        problemas += _problemas_de_definicion(caso.definicion, f"{donde}.definicion")
        problemas += _problemas_de_datos_siis(caso.datos_siis, f"{donde}.datos_siis")

    return problemas


def resumen(problemas):
    """`{problema: cantidad}`, que es lo que se compara entre dos corridas."""
    conteo = {}
    for problema in problemas:
        conteo[problema["problema"]] = conteo.get(problema["problema"], 0) + 1
    return dict(sorted(conteo.items()))


class Command(BaseCommand):
    help = (
        "Revisa la forma de los JSON guardados (condiciones, campos propios, definiciones, datos SIIS). Solo lectura."
    )

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Salida JSON para comparar dos corridas.")
        parser.add_argument(
            "--detalle",
            type=int,
            default=20,
            help="Cuántas filas mostrar por tipo de problema en la salida legible (0 = ninguna).",
        )

    def handle(self, *args, **opciones):
        problemas = revisar()
        conteo = resumen(problemas)

        if opciones["json"]:
            self.stdout.write(json.dumps({"total": len(problemas), "resumen": conteo, "problemas": problemas}))
            return

        if not problemas:
            self.stdout.write(self.style.SUCCESS("Sin problemas: todos los JSON guardados tienen la forma esperada."))
            return

        self.stdout.write(self.style.WARNING(f"{len(problemas)} problema(s) en los JSON guardados:"))
        for nombre, cantidad in conteo.items():
            self.stdout.write(f"  {nombre}: {cantidad}")
        tope = opciones["detalle"]
        if tope:
            self.stdout.write("")
            mostrados = {}
            for problema in problemas:
                visto = mostrados.get(problema["problema"], 0)
                if visto >= tope:
                    continue
                mostrados[problema["problema"]] = visto + 1
                detalle = f" — {problema['detalle']}" if problema["detalle"] else ""
                self.stdout.write(f"  [{problema['problema']}] {problema['donde']}{detalle}")
