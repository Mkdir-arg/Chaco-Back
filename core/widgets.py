"""Widgets de formulario del sistema de diseño NODO.

Cada uno lleva la clase que enciende su CSS en ``static/custom/css/nodo-forms.css``, para
que el template siga siendo ``components/_field.html`` y no escriba markup a mano:

* ``SwitchInput``: un ``BooleanField`` como interruptor de encendido/apagado
  (``.nodo-switch``, pista de 34×18 px). Sigue siendo un ``<input type="checkbox">``, con
  ``role="switch"``: el teclado, el lector de pantalla y el POST son los de siempre.
* ``ChipsSelectMultiple``: un ``MultipleChoiceField`` como chips en píldora
  (``.nodo-chips``, ``role="group"`` nombrado por el label del campo). Sigue siendo un ``CheckboxSelectMultiple``: cada chip es un checkbox
  real, así que la validación, ``cleaned_data`` y el POST no cambian.
"""

from django import forms

SWITCH_CLASS = "nodo-switch"
CHIPS_CLASS = "nodo-chips"


class SwitchInput(forms.CheckboxInput):
    def __init__(self, attrs=None, check_test=None):
        attrs = {"class": SWITCH_CLASS, "role": "switch", **(attrs or {})}
        super().__init__(attrs=attrs, check_test=check_test)


# Atributos que describen al grupo entero: van en el contenedor, no repetidos en cada chip.
ATRIBUTOS_DEL_GRUPO = ("class", "role", "aria-labelledby", "aria-describedby", "aria-invalid")


class ChipsSelectMultiple(forms.CheckboxSelectMultiple):
    """Chips en píldora. El contenedor es ``role="group"`` y se nombra con el label que
    pinta ``components/_field.html`` (``<id>-etiqueta``): un lector de pantalla anuncia
    cada chip con el contexto del campo, y la ayuda y el error cuelgan del grupo, una vez."""

    template_name = "core/widgets/chips.html"

    def __init__(self, attrs=None, choices=()):
        attrs = {"class": CHIPS_CLASS, **(attrs or {})}
        super().__init__(attrs=attrs, choices=choices)

    def get_context(self, name, value, attrs):
        contexto = super().get_context(name, value, attrs)
        atributos = contexto["widget"]["attrs"]
        atributos.setdefault("role", "group")
        if atributos.get("id"):
            atributos.setdefault("aria-labelledby", f"{atributos['id']}-etiqueta")
        return contexto

    def create_option(self, *args, **kwargs):
        opcion = super().create_option(*args, **kwargs)
        for atributo in ATRIBUTOS_DEL_GRUPO:
            opcion["attrs"].pop(atributo, None)
        return opcion
