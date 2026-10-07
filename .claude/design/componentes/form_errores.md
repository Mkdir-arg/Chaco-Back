# Componente · Errores no de campo

**Pieza única:** `templates/components/_form_errores.html`
**Test del contrato:** `core/tests/test_nodo_ui_piezas.py` (`FormErroresTest`)
**Marcadores:** es marcador obligatorio del arquetipo Formulario
(`scripts/design_audit.py --arquetipo formulario`).

## Cuándo

Siempre que la pantalla renderice un Django Form: página de formulario, modal de alta o
edición, y cada paso de un flujo. Los errores que la validación pone en el **conjunto** y
no en un control (`unique_together`, un `clean()` de form, `validate_unique` de un
ModelForm) viven en `form.non_field_errors` y **ningún campo los muestra**: sin esta
pieza el formulario vuelve idéntico, con todos los `field.errors` vacíos, y el usuario
reenvía lo mismo.

No reemplaza los errores de campo: esos los rinde `templates/components/_field.html` debajo de
su control.

## Contrato

```django
{% include "components/_form_errores.html" %}
{% include "components/_form_errores.html" with form=form_domicilio titulo="Revisá el domicilio" %}
```

| Parámetro | Obligatorio | Qué es |
|---|---|---|
| `form` | sí (por contexto) | El Django Form. Si no se pasa, toma el `form` del contexto. |
| `titulo` | no | Encabezado del bloque. Por defecto «Revisá el formulario». |

- Solo se renderiza si hay errores no de campo: con un form sin errores, sin bindear o
  ausente devuelve vacío.
- Va **arriba del primer campo**, inmediatamente después de `{% csrf_token %}`.
- Caja `mb-4 rounded-lg bg-danger-soft border border-danger-subtle p-4 text-sm` con
  `role="alert"`, título en `strong.text-heading` y un `<p class="text-body mt-1">` por
  error. No usa el `<ul class="errorlist">` de Django, que en el backoffice sale sin
  estilo.
- En un modal que se repite por fila (las listas de Geografía y Secretarías), el include
  va dentro del `{% if abrir_modal_pk == objeto.pk %}`: el `form` del contexto es uno
  solo y es el de la fila que falló.

## Prohibido

- `{{ form.non_field_errors }}` escrito a mano, o una caja propia con paleta cruda
  (`text-red-600`, `bg-red-50`).
- Volcar `form.errors.items` entero en el resumen: duplica los errores de campo, que ya
  se muestran junto a su control.
- Usar esta pieza para avisos que no vengan de la validación del form: eso es
  `components/_alerta.html` o `window.toast`.

## Checklist (la usa el revisor)

- [ ] El include está después de `{% csrf_token %}` y antes del primer campo.
- [ ] Hay un test que hace el POST inválido real y ve el texto del error.
- [ ] En modales por fila, el include está acotado a la fila que falló.
- [ ] No quedó ninguna caja de errores generales propia en la misma pantalla.
