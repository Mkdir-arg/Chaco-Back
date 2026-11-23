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
  Y el bloque del alta de relevamiento: si la convocatoria no admite altas (pausada o cerrada), el botón
  y el modal se reemplazan por `_alerta.html` (`tono="danger"`) con el motivo que calcula la vista
  (`motivo_sin_alta`); no se oculta sin explicar.

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
              <th class="nodo-th nodo-col-acciones text-right w-28"><span class="sr-only">Acciones</span></th>
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
              <td class="nodo-td nodo-col-acciones text-right whitespace-nowrap">
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

- Encabezado con más de una acción secundaria: el menú `texto="Más acciones"` (ver la «Variante de encabezado» de `componentes/tabla.md`).
- Sin métricas: se omite la grilla de stat cards.
- Secciones apiladas en vez de solapas cuando hay un área sola.
- Apilado con panel lateral (`{# arquetipo: detalle + apilado #}`): las secciones van en la columna
  `lg:col-span-2 min-w-0 space-y-5` de la grilla de «Formulario con asistencia lateral»
  (`grid grid-cols-1 lg:grid-cols-3 gap-5`) y el panel que acompaña al registro en un `aside space-y-5 min-w-0`
  con `aria-label`; se apila en móvil. Evidencia: `programas/templates/programas/emergencia/casos/detail.html`
  (la ficha del caso a la izquierda; a la derecha, «Derivar» o la derivación vigente). Arriba de la ficha, los avisos de la mesa (`avisos_de_la_mesa` de
  `programas/selectors/emergencia_mesa.py`: «Rechazado por X: motivo», «Derivación vencida», «Derivación vencida
  sin marcar», «Dispositivo inactivo», «Llegaron N sobre M declaradas») van uno por `_alerta.html` con `tono`, `titulo` y `texto`, sin
  variantes nuevas; los mismos textos son las marcas de la fila en la bandeja. La tabla «Personas que ingresan
  juntas» agrega una fila «Responsable» (sexo en «—», total 1) antes de la de totales cuando el grupo tiene
  `responsable_aparte`; misma `nodo-td`, sin clases nuevas. Los rótulos `<dt>` de la ficha (Responsable, DNI, Fuerza que traslada…) van
  `text-xs font-semibold uppercase text-body-subtle`, igual que en el resto de las fichas, para que el valor sea lo destacado. Las filas las arma `franjas_del_grupo` (selector de la
  mesa), la misma fuente que la tarjeta de «Llegadas» del dispositivo. Sin panel lateral,
  las secciones van apiladas a todo el ancho: `programas/templates/programas/emergencia/kits/detail.html`
  (la entrega, ítems con la tabla de conciliación, observaciones, remito con `_galeria_fotos.html`, reposiciones y traza). El reloj del SLA
  (`_semaforo_sla.html` `variante="reloj"`) va en el cuerpo del `page_header`, uno solo por pantalla.
- Tablero de programa como Detalle apilado (`{# arquetipo: detalle + apilado #}`): `{% hero_inicio %}` ocupa el
  lugar del `page_header` (solo en las pantallas de `HERO_PANTALLAS`, ficha `componentes/hero_inicio.md`), una franja
  de `_stat_card` `variante="tablero"`, los avisos como lista de `_alerta.html` (ficha `componentes/alerta.md`) y
  tablas canónicas en secciones con `h2`. Sin gráficos. Evidencia: `programas/templates/programas/emergencia/tablero.html` (E1).
- Solapa con carga diferida: `@click="tab='x'; $dispatch('<evento>')"` y el JS escucha ese
  evento en `window` (molde: `config/programa_detail.html`, que dispara `becas-dashboard-abrir`).
- Solapa que navega (variante de la carga diferida, sin JS de pantalla): cuando el contenido pesa y la vista solo lo
  arma con `?tab=<x>`, el panel va vacío hasta entonces y el `@click` del botón, mientras no esté cargado, es
  `window.location.href='<url con ?tab=<x>>'`. Ese botón lleva `data-solapa-navega` (solo mientras no está cargado): con
  ← → recibe el foco pero no se activa (recorrer la barra no recarga la página); se abre con Enter, Espacio o clic. Lo
  lee `static/custom/js/nodo-tabs.js` (`componentes/tabs.md`). Molde: la solapa «Sectores y plazas» de la
  página del edificio (`dispositivos/edificios/operativo.html`), cuyo cuerpo es `dispositivos/sectores/_cuerpo.html`, el
  mismo que dibuja la pantalla suelta de siempre, con el edificio fijo y sin el filtro «Edificio» (Cambio 565).
- Solapa condicionada por permiso: el `{% if %}` envuelve **el botón y el panel**.
- Solapa inicial validada por el servidor: en P4
  (`programas/templates/programas/dispositivos/legajo/detail.html`),
  `programas/services/detalle_dispositivo.py` normaliza `?tab=` según las solapas disponibles
  y la vista pasa `tab` al `x-data`; una inexistente cae en la predeterminada.
- **Marca «Emergencia · Caso N» (Cambio 575):** la persona alojada por un caso de Emergencia lleva `badge badge-brand`
  «Emergencia» y el número de caso, dibujados por el parcial `_marca_emergencia.html` (de `dispositivos/`) (no es pieza del
  inventario) en la solapa Personas alojadas de P4 (`legajo/detail.html`), en la solapa Estadías de la página del edificio
  y en el encabezado de P7. La vista deja `estadia.marca_emergencia` (una consulta por lista, `selectors/estadia_origen_emergencia.py`):
  el número enlaza al caso solo con `emergencia.operar` o `supervisar`, y «· Familia <apellido>» (también en el `title`)
  solo con `ciudadano.ver`; sin esa capacidad el apellido no llega al HTML. Los filtros de esas solapas salen de
  `pildoras_de_estadias` (`services/detalle_dispositivo.py`): «Origen: Emergencia / Todas» es opt-in (`origen`) y solo lo
  pide la página del edificio.
  El menú «Más acciones» de P4 suma «Emergencia · Kits» (ítem con `url`) solo si la vista manda `url_kits_emergencia`: quien tiene `emergencia.recibir_kit` en el Equipo de ese dispositivo.
  Las acciones del encabezado de P4 salen de banderas que arma la vista, no de un `{% if %}` sobre el estado: «Editar» (`puede_editar`) y «Enviar a validación» (`puede_enviar_validacion`, desde borrador, observado o rechazado con `dispositivo.editar`).
  El menú «Más acciones» de P4 lleva además el ítem de navegación «Emergencia · Llegadas»: la vista manda `url_llegadas_emergencia` solo a quien tiene `dispositivo.admitir` con alcance —lo que exige esa pantalla— y sin la URL el ítem no se dibuja.
  La `dl` de datos de la solapa Datos rotula las franjas de P3 como «Horario de atención» (solo informativo; no son los turnos de la Bitácora).
  Solapa «Equipo» de P4 (Cambio 411): la ve quien ve el dispositivo; tabla canónica (`nodo-th`, `menu_fila` con `confirm_url`; baja y quitar responsable en `peligro`) y «Sumar persona» `btn-brand btn-sm btn-fit` que abre un modal de `data-ajax`. Botón, columna de acciones y modal van bajo `puede_gestionar_equipo` (la vista re-verifica en cada POST); la marca de responsable es `badge badge-dot badge-success` y una fila cuyo rol ya no vale lleva `badge badge-warning badge-sm` «Rol no vigente». Bajo `lg`, Rol y Responsable van apilados bajo el nombre (`lg:hidden`) y sus columnas son `hidden lg:table-cell` (Cambio 447: la columna fija de acciones tapaba el resto de la fila). La tabla suma la columna «Contratación» (`nodo-th hidden lg:table-cell`, «Sin dato» en `text-body-subtle` si es NULL; bajo `lg` va bajo el nombre junto al rol), y los dos modales de alta llevan el desplegable `tipo_contratacion` (Cambio 523).
- Respuestas de un formulario del constructor en la solapa Datos de P4: una `section`
  `border-t border-light mt-6 pt-5` por formulario respondido, con `h2` y `badge badge-gray`
  «Versión N» (más «Tipo anterior: …» si es de otro tipo), `h3` por sección y la misma `dl`
  `grid gap-5 sm:grid-cols-2` de los datos; el archivo es un enlace con `fa-paperclip`. Solo
  lo visible según las condiciones de la foto respondida.
- Edificios de P4 (Cambio 570): sección «Edificios · N» en el cuerpo, **fuera de las solapas** y entre los indicadores y
  las solapas: `section` con `aria-labelledby`, encabezado «Edificios · N» con «Vincular edificio» (`btn-tertiary`) y
  «Agregar edificio» (`btn-secondary`) bajo `puede_editar`, y una grilla `lg:grid-cols-3` de
  `components/_tarjeta_edificio.html` (hasta 60, las más graves primero; `n_sin_mostrar` avisa el resto). Cada tarjeta
  abre la página del edificio (`dispositivos:edificio_operativo`). Sin edificio, el estado vacío; los sectores sin
  edificio van en `_infra_sin_edificio.html` (una `_alerta` warning; «Asignar edificio» solo con
  `puede_asignar_edificio`). Un edificio sin plazas disponibles sale en una `_alerta` warning sobre los indicadores
  (`ficha_edificios.aviso_sin_plazas`: uno se nombra con su enlace; varios, un solo resumen). Alta, edición y vínculo del
  edificio siguen en los modales canónicos, abiertos por `?edificio=nuevo|vincular|<pk>`. Las solapas son Datos, Personas
  alojadas (clave `estadias`), Equipo e Historial: los enlaces viejos a `?tab=sectores|infraestructura` los resuelve
  `ficha_edificios.redireccion_de_solapa_vieja`. La ficha no ingresa personas ni lleva la bitácora: son del edificio.
- Ficha propia del edificio (`programas/templates/programas/dispositivos/edificios/detail.html`, `{# arquetipo: detalle + apilado #}`):
  sin métricas, solo lectura salvo «Editar edificio», desde la sección Edificios (`EdificioDetailView`, `ficha_de_edificio` de
  `programas/selectors/edificios.py`). `page_header` con volver a «Edificios», estado, aviso, «Inactivo», «Crear relevamiento» solo con `url_asignar` y «Editar edificio» (`btn-secondary btn-sm`) solo con `url_editar`, que lleva al modal de edición de la ficha (`?edificio=<pk>`) de la primera institución del predio (por nombre) que el usuario abre, que no está cerrada y sobre la que alcanza toda la institución (`dispositivo.editar`; con alcance Edificios no se ofrece); los títulos de sección son `h2 text-heading font-bold`;
  secciones Datos (`_ubicacion.html` compacto), Instituciones del predio, Sectores por institución, Último relevamiento y Registro
  fotográfico (`_linea_tiempo` plegable + `_paginacion`). Quién relevó, observaciones y el registro solo con `ve_detalle` (Cambio 428). La fila
  del listado abre la ficha con el nombre enlazado y un `nodo-icon-btn` «Ver», junto al de «Crear relevamiento».
  Inactivar y reactivar (Cambio 583): solo con `programa.configurar` (`ve_situaciones`); «Inactivar edificio» (`btn-secondary btn-sm`; confirmación roja) y «Activar edificio» (`btn-brand`) confirman con `data-confirm-url` (`ModernModal`) y hacen POST a `edificios/<pk>/inactivar|reactivar/`. Con el edificio inactivo no hay `url_editar`. La página operativa (`edificios/operativo.html`) suma el ítem de peligro «Inactivar edificio» en «Más acciones»; inactivo, muestra la insignia «Inactivo» (`estado_texto` de `page_header`), un aviso informativo y «Activar edificio» como botón primario en lugar de ingresar persona y bitácora (`programas/services/edificio_operativo.py`). En Infraestructura la tarjeta lleva el `aviso` «Inactivo» y sin editar ni desvincular (`programas/services/detalle_dispositivo.py`).
- En P4, la columna Persona muestra «Apellido, Nombre» y DNI sin avatar solo con `ciudadano.ver`.
  Sin esa capacidad, fila, etiqueta del menú y modales de cambio/egreso muestran «Persona alojada»
  sin identidad en texto ni atributos; tampoco los movimientos del Historial precargado nombran
  a la persona. El nombre visible de celda, menú y modales se prepara en la vista con el mismo
  formato; sin identidad, el menú distingue la fila por sector y plaza o, sin plaza, por la
  fecha de ingreso visible y «estadía N.º <pk>», también si dos ingresos coinciden en el minuto.
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
  acción secundaria existente, condicionada por capacidad y estado activo; «Reactivar» (confirmación
  no destructiva, mismo menú) aparece solo con el dispositivo inactivo y la misma capacidad.
- Estado vacío dentro de la tabla: `{% empty %}` con `<td colspan="n" class="p-0">`.
- Acción de la fila que muta: `<button type="button">` con `data-*` + `<form method="post" class="hidden">`
  con `{% csrf_token %}`, y la confirmación por `data-confirm-url` (arquetipo Confirmación).

La ficha de la institución pide las tarjetas con `infraestructura_del_dispositivo(..., solo_tarjetas=True)`: no abre la ficha de un edificio, no lee las instituciones del predio ni los totales de relevamientos, y su comentario de cabecera nombra la sección «Edificios», no una solapa.

En P4, `programas/services/detalle_dispositivo.py` prepara la sección Edificios, el registro del edificio y el Historial según
quien mira: la institución no recibe el nombre del agente de un relevamiento sin realizar,
incluidos los cancelados. La asignación la ven el coordinador del edificio y el propio agente
(`programas.services.inspecciones.ve_la_asignacion`). El Historial rearma esas trazas sin
nombres; una vez realizado, el resultado muestra quién relevó. el registro fotográfico del edificio enlaza cada
evento con su informe de solo lectura y conserva el dispositivo de origen para volver.
Con alcance por edificios (Cambio 523) el Historial trae solo los movimientos de las plazas de sus edificios, las
correcciones de sus novedades y los relevamientos de sus edificios; las trazas del dispositivo (legajo, plazas, sectores, turnos y edificios) no llevan edificio y quedan para
quien tiene toda la institución (`eventos_de_historial`, `edificios_en_alcance`).
El badge del registro es siempre la criticidad; la revisión agrega «Revisado» en el panel, más revisor y fecha/hora, con el
contrato de `componentes/ficha_timeline.md`. Las fotos en curso conservan su fecha de carga.
Quien ve el dispositivo sin alcance de inspección sobre el edificio (`inspecciones_visibles`) ve en la tarjeta y en la ficha del
edificio solo el estado y la fecha del último relevamiento: sin criticidad, observaciones ni quién relevó.
El estado edilicio de cada edificio (clave del filtro, rótulo y tono del semáforo, y el aviso «Vencido» / «Vence en
N días») sale de `clave_estado_edilicio` y `aviso_de_vencimiento` de `programas/services/detalle_dispositivo.py`, las
mismas que usa el listado de la sección Edificios (`programas/selectors/edificios.py`): una sola definición para la
tarjeta, la ficha y la fila.
El registro fotográfico (página de relevamientos, fotos y quién ve la asignación) sale de
`registro_de_relevamientos` del mismo servicio: la tarjeta del edificio en la ficha de la institución y la ficha propia del edificio
muestran el mismo registro del mismo edificio.
El enlace «Ver informe» lleva el origen para volver: `?dispositivo=<pk>` desde la institución y
`?edificio=<pk>` desde la ficha del edificio; el informe solo arma ese «Volver» si el usuario puede abrir esa pantalla.

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
