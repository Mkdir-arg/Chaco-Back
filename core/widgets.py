"""Widgets de formulario del sistema de diseño NODO.

Cada uno lleva la clase que enciende su CSS en ``static/custom/css/nodo-forms.css``, para
que el template siga siendo ``components/_field.html`` y no escriba markup a mano:

* ``SwitchInput``: un ``BooleanField`` como interruptor de encendido/apagado
  (``.nodo-switch``, pista de 34×18 px). Sigue siendo un ``<input type="checkbox">``, con
  ``role="switch"``: el teclado, el lector de pantalla y el POST son los de siempre.
* ``ChipsSelectMultiple``: un ``MultipleChoiceField`` como chips en píldora
  (``.nodo-chips``). Sigue siendo un ``CheckboxSelectMultiple``: cada chip es un checkbox
  real, así que la validación, ``cleaned_data`` y el POST no cambian.
"""

from django import forms

SWITCH_CLASS = "nodo-switch"
CHIPS_CLASS = "nodo-chips"


class SwitchInput(forms.CheckboxInput):
    def __init__(self, attrs=None, check_test=None):
        attrs = {"class": SWITCH_CLASS, "role": "switch", **(attrs or {})}
        super().__init__(attrs=attrs, check_test=check_test)


class ChipsSelectMultiple(forms.CheckboxSelectMultiple):
    def __init__(self, attrs=None, choices=()):
        attrs = {"class": CHIPS_CLASS, **(attrs or {})}
        super().__init__(attrs=attrs, choices=choices)
