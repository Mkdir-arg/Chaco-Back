"""Validadores de modelo de ``programas`` (RED-40).

Los `JSONField` del dominio tienen una estructura implícita que nadie valida:
la forma la conoce el motor que la lee y nada impide guardar otra cosa. El caso
que más duele está medido en la ficha RED-40: una condición con un operador
fuera de ``OPERADORES_POR_TIPO`` cae al ``return False`` final de
``evaluar_regla`` y el ítem condicionado **no se muestra nunca** —sin error, sin
log y sin forma de notarlo desde la pantalla—.

Vive en su propio módulo, y no en ``services/condiciones.py``, porque
``programas.models`` lo importa para declararlo en ``validators=[…]`` y
``condiciones`` importa ``programas.models``: el import diferido de adentro de
la función es lo que corta el ciclo. El nombre del módulo es el que queda
escrito en las migraciones, así que mover la función de archivo es un cambio de
contrato.

Lo que valida es la **forma**, no la coherencia: si la fuente existe, si está
antes y si el operador aplica al tipo de ese campo lo decide
``condiciones.validar_condicion``, que necesita el diseño entero alrededor.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError


def validar_condicion_json(valor):
    """Valida la forma de una condición (``{modo, reglas}``) de ``ItemDiseno``
    o ``GrupoRequisito``. ``None`` y el vacío son válidos: no hay condición."""
    if valor in (None, "", {}, []):
        return

    from programas.services import condiciones

    if not isinstance(valor, dict):
        raise ValidationError("La condición tiene que ser un objeto con «modo» y «reglas».")

    errores = []
    modo = valor.get("modo") or condiciones.MODO_TODAS
    if modo not in condiciones.MODOS:
        errores.append(f"Modo desconocido: {modo!r}.")

    reglas = valor.get("reglas")
    if reglas is None:
        reglas = []
    if not isinstance(reglas, list):
        raise ValidationError("Las reglas de la condición tienen que ser una lista.")

    operadores = operadores_conocidos()
    for numero, regla in enumerate(reglas, start=1):
        if not isinstance(regla, dict):
            errores.append(f"Regla {numero}: tiene un formato inválido.")
            continue
        if not isinstance(regla.get("fuente"), str) or not regla.get("fuente"):
            errores.append(f"Regla {numero}: la fuente tiene que ser la clave de otro ítem.")
        op = regla.get("op")
        if not isinstance(op, str) or op not in operadores:
            # Es el hallazgo de RED-40: un operador que el motor no conoce no
            # falla, devuelve False, y el ítem queda escondido para siempre.
            errores.append(f"Regla {numero}: el operador «{op}» no existe.")
            continue
        if op not in condiciones.SIN_VALOR and condiciones.esta_vacio(regla.get("valor")):
            etiqueta = condiciones.ETIQUETAS_OPERADOR.get(op, op)
            errores.append(f"Regla {numero}: el operador «{etiqueta}» necesita un valor.")
        if op in condiciones.CON_LISTA and not isinstance(regla.get("valor"), (list, tuple)):
            etiqueta = condiciones.ETIQUETAS_OPERADOR.get(op, op)
            errores.append(f"Regla {numero}: «{etiqueta}» espera una lista de valores.")

    if errores:
        raise ValidationError(errores)


def operadores_conocidos():
    """Todos los operadores que el motor sabe evaluar, sin mirar el tipo del
    campo fuente (eso es coherencia, no forma)."""
    from programas.services import condiciones

    conocidos = set()
    for permitidos in condiciones.OPERADORES_POR_TIPO.values():
        conocidos |= set(permitidos)
    return conocidos
