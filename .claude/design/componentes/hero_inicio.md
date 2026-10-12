# Componente · Hero de inicio de programa (`{% hero_inicio %}`)

**Clasificación:** Canónico reutilizable, **acotado por regla**. Pieza única, sin variantes.
**Evidencia:** tag `hero_inicio` de `core/templatetags/nodo_ui.py`, `templates/components/_hero_inicio.html`,
`static/custom/css/nodo-hero.css` (el shell la carga desde `templates/includes/base.html`),
`core/tests/test_nodo_ui_piezas.py` (`HeroInicioTest`).
**Consumidores de referencia:** ninguno todavía. Lo estrena el tablero de la red del programa
Dispositivos (P1 del mockup v2). El Inicio (`templates/inicio.html`) lo tuvo hasta que FE-22 lo retiró
y hoy usa `{% page_header %}`: volver a ponerlo es una decisión de producto, no un efecto de esta pieza.

## Regla de uso (taxativa)

El hero es **solo** de dos superficies:

1. la pantalla de inicio (`/inicio/`), y
2. los tableros de programa (la primera pantalla de un programa: Dispositivos, Merenderos, Becas).

En **ninguna otra pantalla**. Un listado, un detalle, un formulario, un modal, una pantalla de
configuración o un reporte abren con `{% page_header %}`: sigue valiendo «no crear landing pages para
backoffice operativo» y «la primera pantalla debe ser la herramienta usable». Un hero en otra pantalla
se rechaza citando esta ficha y la fila del inventario del agente.

- Ocupa el lugar de `{% page_header %}`: su `h1` **es** el título de la página. No se pone un
  `page_header` debajo.
- Es el único contenido del backoffice con gradiente de marca (más la caja de ícono de la stat card
  `variante="tablero"`). No se copia el gradiente a otras piezas ni se arma un hero a mano.
- Uno por pantalla, arriba de todo; no se repite en solapas ni en modales.
- **Se hace cumplir en dos lugares.** `scripts/design_audit.py` tiene la regla P1 `HEROFUERA`: marca
  `{% hero_inicio %}` o clases `nodo-hero*` en cualquier template fuera de `HERO_PANTALLAS` (hoy vacía;
  corta en `--ratchet`, hook y CI). Y `HeroInicioTest.test_solo_las_pantallas_autorizadas_lo_usan` contrasta
  esa misma lista contra los templates reales. Incorporar una pantalla es agregar su ruta a
  `HERO_PANTALLAS`, a la vista de quien revisa.

## Invocación

```django
{% load nodo_ui %}
{% hero_inicio titulo="Red de dispositivos" eyebrow="Programa Dispositivos · Abordaje Psicosocial" accion_url=url_instituciones accion_texto="Ver instituciones" accion_icono="fa-building" %}
  {% bajada %}{{ resumen_red }}{% endbajada %}
{% endhero_inicio %}
```

| Argumento | Efecto |
|---|---|
| `titulo` | Obligatorio. El `h1` (30 px, peso 800), en blanco |
| `eyebrow` | Opcional. Línea de contexto en mayúsculas sobre el título («Programa Dispositivos · …») |
| `bajada` o bloque `{% bajada %}` | Opcional. Un párrafo de hasta 560 px. El bloque admite marcado de la plantilla (`<strong>` con los números) y gana sobre el argumento; los dos se escapan |
| `accion_url` + `accion_texto` | Opcionales y **van juntos**: botón blanco de 44 px con el texto en color de marca. Con uno solo no se dibuja |
| `accion_icono` | Opcional. Nombre Font Awesome sin `fas` (`fa-building`), con `aria-hidden="true"` |

El tag no acepta otros argumentos ni otro contenido en el cuerpo que no sea `{% bajada %}`: falla al
compilar la plantilla. Los números de la bajada se calculan en la vista, no en el template.

## Render

`.nodo-hero` (flex, `gap` 24, `padding` 28 × 32, radio 16, `--gradient-brand`, `--shadow-brand`) con
`.nodo-hero__eyebrow` (13 px, 600, mayúsculas), `.nodo-hero__titulo` (30 px, 800), `.nodo-hero__bajada`
(14,5 px) y `.nodo-hero__accion` (pastilla blanca; foco visible con anillo blanco). Medidas tomadas del
`.hero` de P1 y comparadas con el de `docs/client/mockups/dispositivos-v2.html`.

`nodo-brand.css` fija el color y el tracking de todo `h1` con `!important`; la hoja del hero les gana a
propósito, porque sobre el gradiente el título es blanco.

## Prohibido

- Usar el hero fuera de Inicio y de los tableros de programa.
- Un `<h1>` o un gradiente armados a mano para «parecerse» al hero.
- `style=` o `<style>` para ajustarlo; hex; otras variantes de color.
- Más de una acción: las acciones secundarias van en el contenido de la pantalla, no en la franja.
