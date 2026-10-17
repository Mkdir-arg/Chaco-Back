# Arquetipo · Detalle con solapas

**Golden (la única que se clona):** `programas/templates/programas/becas/cupo/segmento_detail.html`.
**Marcadores:** `scripts/design_audit.py --arquetipo detalle <archivo>`.
**Componentes:** page_header · stat_card · tabs · tabla · estado_vacio · paginacion · botones_badges.

**Secundarias, solo para lo indicado:**

- `programas/templates/programas/becas/config/programa_detail.html`: **solo** la solapa con
  carga diferida (`$dispatch` en el `@click` y el JS escuchando ese evento en `window`) y la
  solapa condicionada por permiso (botón y panel envueltos en el mismo `{% if %}`).
- `programas/templates/programas/becas/relevamientos/convocatoria_detail.html`: **solo** las
  migas y las acciones del encabezado (con `aria-hidden` en sus íconos). **Nunca sus solapas**:
  no tienen ARIA.

## Cuándo

Un registro que se mira y se opera, con métricas de cabecera y **2 o más áreas equivalentes**.
Con un área sola no hay solapas: van secciones apiladas en surfaces. **Esa variante se
declara**, con un comentario en la primera línea del template:

```django
{# arquetipo: detalle + apilado #}
```

Declarada, el auditor deja de pedir los siete marcadores de solapas y en su lugar exige que
**cada sección sea un `<section>` con `aria-labelledby` y su `<h2>`**: sin solapas, la sección
es la unidad navegable, y el nombre accesible es lo que la solapa daba gratis.

Se **declara** y no se infiere de que falten las solapas: si se infiriera, una pantalla que
se las olvidó pasaría como «apilada» y el gate no serviría para nada.

## Esqueleto (copiar literal; cambiar solo lo que está entre <>)

```django
{% extends "includes/base.html" %}
{% load nodo_ui %}
{% block title %}<Módulo> · <Entidad> · {{ <objeto>.nombre }}{% endblock %}

{% block main-content %}
<div class="space-y-5"
     x-data="{ tab: new URLSearchParams(window.location.search).get('tab') || '<tab_default>' }">

  {% url '<app>:<lista>' as url_volver %}
  {% page_header titulo="<Título>" volver_url=url_volver volver_label="<pantalla de origen>" migas=migas %}
    {% bajada %}<una línea con el contexto del registro>{% endbajada %}
    <span class="badge badge-success badge-dot">{{ <objeto>.estado }}</span>
    <a href="{% url '<app>:<entidad>_editar' <objeto>.pk %}" class="btn-nodo btn-secondary btn-sm">
      <i class="fas fa-pen" aria-hidden="true"></i> Editar
    </a>
  {% endpage_header %}

  <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
    {% include "components/_stat_card.html" with etiqueta="<Métrica>" valor=stats.<x> icono="fa-users" tono="brand" %}
  </div>

  <div class="bg-white rounded-xl border border-base shadow-sm overflow-hidden">

    <div class="border-b border-base flex gap-1 px-2 flex-wrap" role="tablist" aria-label="Secciones de <la entidad>">
      <button @click="tab='<a>'" type="button" role="tab" id="tab-<a>" aria-controls="panel-<a>"
              :aria-selected="tab==='<a>'"
              class="px-4 py-3 text-sm border-b-2 -mb-px transition flex items-center gap-1.5 whitespace-nowrap"
              :class="tab==='<a>' ? 'text-fg-brand border-brand font-bold' : 'text-body-subtle border-transparent hover:text-body font-medium'">
        <i class="fas fa-<icono>" aria-hidden="true"></i> <Solapa>
        <span class="badge" :class="tab==='<a>' ? 'badge-info' : 'badge-gray'">{{ n_<a> }}</span>
      </button>
    </div>

    <div x-show="tab==='<a>'" x-cloak role="tabpanel" id="panel-<a>" aria-labelledby="tab-<a>">
      <div class="overflow-x-auto">
        <table class="w-full border-collapse">
          <thead>
            <tr class="nodo-thead-row">
              <th class="nodo-th"><Columna></th>
              <th class="nodo-th text-right w-28"><span class="sr-only">Acciones</span></th>
            </tr>
          </thead>
          <tbody>
            {% for obj in <objetos> %}
            <tr class="hover:bg-secondary transition">
              <td class="nodo-td">
                <div class="flex items-center gap-2.5">
                  <div class="w-8 h-8 rounded-full bg-brand-soft text-fg-brand flex items-center justify-center text-xs font-bold flex-shrink-0" aria-hidden="true">{{ obj.<nombre>|slice:":1"|upper }}{{ obj.<apellido>|slice:":1"|upper }}</div>
                  <span class="font-medium text-heading">{{ obj.<apellido> }}, {{ obj.<nombre> }}</span>
                </div>
              </td>
              <td class="nodo-td text-right whitespace-nowrap">
                <a href="{% url '<app>:<detalle>' obj.pk %}?next={{ request.get_full_path|urlencode }}"
                   class="nodo-icon-btn" aria-label="Ver <entidad> de {{ obj.<nombre> }} {{ obj.<apellido> }}">
                  <i class="fas fa-eye" aria-hidden="true"></i>
                </a>
              </td>
            </tr>
            {% empty %}
            <tr>
              <td colspan="<n>" class="p-0">
                {% include "components/_estado_vacio.html" with icono="fa-<x>" titulo="<Nada todavía>" texto="<cuándo aparece algo acá>" %}
              </td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

Vista: el objeto, `stats` (dict con los números ya calculados), los contadores de cada
solapa, las capacidades resueltas con `puede()` y las relaciones con `select_related` /
`prefetch_related`. Las migas, cuando hay 3 o más niveles; en Becas las arma
`{% becas_migas objeto actual="…" %}`, en otros módulos se arman en la vista.

## Variantes permitidas

- Estado junto al H1: P4/P19 y P7 pasan `estado_texto` y `estado_variante` a `page_header`;
  el estado se omite del cuerpo de acciones. El resto de los detalles conserva su header.

- Sin métricas: se omite la grilla de stat cards.
- Secciones apiladas en vez de solapas cuando hay un área sola.
- Solapa con carga diferida: `@click="tab='x'; $dispatch('<evento>')"` y el JS escucha ese
  evento en `window` (molde: `config/programa_detail.html`, que dispara `becas-dashboard-abrir`).
- Solapa condicionada por permiso: el `{% if %}` envuelve **el botón y el panel**.
- Solapa inicial validada por el servidor: en P4
  (`programas/templates/programas/dispositivos/legajo/detail.html`),
  `programas/services/detalle_dispositivo.py` normaliza `?tab=` según las solapas disponibles
  y la vista pasa `tab` al `x-data`; una inexistente cae en la predeterminada.
- Infraestructura de P4/P19: cada edificio muestra su domicilio normalizado junto a su
  identidad y `_ubicacion.html` con las coordenadas del inmueble. El predio compartido
  lista solo instituciones visibles, con tipo, estado y enlace al legajo; omite sector
  porque `Sector` no se relaciona con `Edificio`. `infraestructura_del_dispositivo`
  entrega domicilio y coordenadas sin consultas por fila. Alta, edición y vínculo se abren en los modales
  canónicos de esa solapa y exigen alcance de edición al dispositivo.
  El semáforo de la solapa y de cada edificio conserva «Crítico» (`danger`) si la última
  realizada fue Alta, incluso con relevamientos vencidos en ese edificio u otro del dispositivo.
  En los demás casos muestra «Vencido» (`warning`) si hay un relevamiento en curso vencido,
  con el selector que usa la alerta. Sin vencidos
  conserva la criticidad de la última realizada o «Sin relevar»; sin inmuebles,
  «Sin edificio cargado». P2 usa el mismo servicio, con lecturas por lote.
- En P4, la columna Persona muestra nombre y DNI sin avatar solo con `ciudadano.ver`.
  Sin esa capacidad, fila, etiqueta del menú y modales de cambio/egreso muestran «Persona alojada»
  sin identidad en texto ni atributos; tampoco los movimientos del Historial precargado nombran
  a la persona. El nombre visible se prepara una sola vez en la vista; sin identidad, el menú
  distingue la fila por sector y plaza o, sin plaza, por la fecha de ingreso visible.
  El modal de egreso cuenta días de calendario con
  `Estadia.dias_de_permanencia()`, como P7.
- En P4, las acciones de estadía usan `menu_fila` y cada capacidad: ver (`ciudadano.ver`),
  cambiar (`dispositivo.admitir`) y egresar (`dispositivo.egresar`). Cambio y egreso abren
  un único modal por GET, como P21, y guardan por POST AJAX. Sin plazas libres, cambiar
  muestra el motivo; las acciones sin capacidad o sobre estadías cerradas se omiten.
  La elegibilidad se lee de forma perezosa una sola vez por petición: una fila activa con
  plaza o el modal válido de cambio la necesitan; menú y modal comparten el mismo mapa.
  Un detalle sin esas filas ni modal no consulta las plazas elegibles para ingreso.
- En el encabezado de P4, Cerrar usa `btn-nodo btn-tertiary btn-sm btn-fit` y conserva
  su confirmación destructiva (`data-confirm-danger="true"`). Inactivar permanece como
  acción secundaria existente, condicionada por capacidad y estado activo.
- Estado vacío dentro de la tabla: `{% empty %}` con `<td colspan="n" class="p-0">`.
- Acción de la fila que muta: `<button type="button">` con `data-*` + `<form method="post" class="hidden">`
  con `{% csrf_token %}`, y la confirmación por `data-confirm-url` (arquetipo Confirmación).

En P4, `programas/services/detalle_dispositivo.py` prepara Infraestructura e Historial según
quien mira: la institución no recibe el nombre del agente de un relevamiento sin realizar,
incluidos los cancelados. La asignación la ven el coordinador del edificio y el propio agente
(`programas.services.inspecciones.ve_la_asignacion`). El Historial rearma esas trazas sin
nombres; una vez realizado, el resultado muestra quién relevó. Infraestructura enlaza cada
evento con su informe de solo lectura y conserva el dispositivo de origen para volver.
La revisión agrega badge verde, revisor y fecha/hora sin perder la criticidad, con el
contrato de `componentes/ficha_timeline.md`. Las fotos en curso conservan su fecha de carga.

## Prohibido

- `<h1>` propio, «← Volver» como link de texto, header dentro de una card.
- `<style>` local (incluido `[x-cloak]`: ya está global en `static/custom/css/override.css`),
  `style=`, paleta cruda, SVG inline.
- Solapas sin `role="tablist"`/`role="tab"`/`aria-controls`/`role="tabpanel"`/`aria-labelledby`.
- Un manejo de teclado propio para las solapas: lo da `static/custom/js/nodo-tabs.js` desde
  el shell (ficha `componentes/tabs.md`).
- Una solapa que abre **otra pantalla**: eso es una acción del encabezado
  (`btn-nodo btn-secondary btn-sm`), no una solapa con `ml-auto`.
- Avatares con `var(--gradient-brand)`: las iniciales van `bg-brand-soft text-fg-brand`.
- Contadores de solapa con utilidades de color sueltas: `badge badge-info` en la activa y
  `badge badge-gray` en las demás.

## Paginación dentro de una solapa

`templates/components/_paginacion.html` acepta `param` (nombre del parámetro de página) y `extra_qs`
(el `tab` al que vuelve el enlace), así que **cada solapa pagina con su propio parámetro** sin mover
a las otras. La golden lo hace en sus tres solapas; la vista prepara el `Page` y el querystring sin
ese parámetro ni `tab`:

```django
{% include "components/_paginacion.html" with page_obj=beneficiarios entidad="beneficiario" param="beneficiarios_page" extra_qs="tab=beneficiarios" filtros_qs=beneficiarios_querystring %}
```

Ficha del componente: `.claude/design/componentes/paginacion.md`.

## Checklist (la usa el revisor)

- [ ] `--arquetipo detalle` OK y `--ratchet` con 0 nuevos.
- [ ] Molde declarado = golden; de la hermana solo salió dominio.
- [ ] `tablist` con `aria-label`; cada `tab` con `id`, `aria-controls` y `:aria-selected`;
      cada panel con `role="tabpanel"` y `aria-labelledby`.
- [ ] La solapa inicial sale de la querystring `tab`.
- [ ] Acciones del encabezado en `btn-sm`; badges de estado antes de las acciones.
- [ ] `volver_url` apunta a la pantalla de origen y `volver_label` la nombra.
- [ ] Métricas calculadas en la vista, no en el template.
- [ ] Cada tabla tiene su estado vacío y su columna de acciones nombrada.
