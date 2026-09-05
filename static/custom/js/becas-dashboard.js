/*
 * Dashboard del programa Becas (análisis 366, Cambio 64).
 *
 * Pide los datos a `becas:programa_dashboard_datos` recién cuando se abre la solapa
 * (evento `becas-dashboard-abrir`) y los redibuja con cada cambio de filtro. No trae
 * colores propios: los lee de los tokens de chaco-tokens.css en tiempo de ejecución.
 * Chart.js 4 vendorizado, con carga diferida como en templates/inicio.html.
 */
(function () {
  'use strict';

  const raiz = document.getElementById('becas-dashboard');
  if (!raiz) return;

  const form = document.getElementById('becas-dashboard-filtros');
  const urlDatos = raiz.dataset.urlDatos;
  const urlExportar = raiz.dataset.urlExportar || '';
  const urlConvocatoria = raiz.dataset.urlConvocatoria || '';
  const $ = (selector) => raiz.querySelector(selector);
  const $$ = (selector) => Array.from(raiz.querySelectorAll(selector));
  const NF = new Intl.NumberFormat('es-AR');
  const fmt = (n) => NF.format(Math.round(Number(n) || 0));
  const pct = (v) => (typeof v === 'number' ? v.toLocaleString('es-AR', { maximumFractionDigits: 1 }) + ' %' : '—');
  const fecha = (iso) => {
    if (!iso) return '';
    const [a, m, d] = iso.slice(0, 10).split('-');
    return `${d}/${m}/${a}`;
  };
  // Etiqueta larga → hasta dos renglones (Chart.js acepta arrays), así no se recorta en tarjetas angostas.
  const partir = (texto, maximo) => {
    const palabras = String(texto).split(' ');
    if (texto.length <= maximo || palabras.length === 1) return texto;
    const lineas = [''];
    palabras.forEach((p) => {
      const actual = lineas[lineas.length - 1];
      if (actual && (actual + ' ' + p).length > maximo && lineas.length < 2) lineas.push(p);
      else lineas[lineas.length - 1] = actual ? `${actual} ${p}` : p;
    });
    return lineas;
  };

  let abierto = false;
  let controlador = null;
  const charts = {};
  const vistaTabla = {};
  let ultimo = null;

  // ── Tokens ─────────────────────────────────────────────────────────────────
  const token = (nombre, fallback) => {
    const valor = getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
    return valor && !valor.startsWith('var(') ? valor : fallback;
  };
  function paleta() {
    return {
      brand: token('--color-brand-500', 'rebeccapurple'),
      brandSuave: token('--color-brand-400', 'mediumpurple'),
      ok: token('--color-emerald-600', 'seagreen'),
      no: token('--color-rose-600', 'crimson'),
      gris: token('--color-gray-400', 'gray'),
      grilla: token('--border-light', 'gainsboro'),
      texto: token('--text-body-subtle', 'dimgray'),
      titulo: token('--text-heading', 'black'),
      superficie: token('--bg-primary', 'white'),
      fuente: token('--font-family-base', 'Manrope, sans-serif'),
    };
  }
  function conAlfa(color, alfa) {
    const m = /^#([0-9a-f]{6})$/i.exec(color);
    if (!m) return color;
    const n = parseInt(m[1], 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alfa})`;
  }

  // ── Chart.js diferido ──────────────────────────────────────────────────────
  let promesaChart = null;
  function cargarChartJs() {
    if (window.Chart) return Promise.resolve();
    if (promesaChart) return promesaChart;
    promesaChart = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = raiz.dataset.chartjs;
      script.async = true;
      script.onload = resolve;
      script.onerror = () => reject(new Error('No se pudo cargar Chart.js'));
      document.head.appendChild(script);
    });
    return promesaChart;
  }
  function prepararChart() {
    const c = paleta();
    window.Chart.defaults.font.family = c.fuente;
    window.Chart.defaults.font.size = 12;
    window.Chart.defaults.color = c.texto;
    if (!window.Chart.registry.plugins.get('valoresAlFinal')) {
      // Valor al final de cada barra horizontal: los gráficos no comunican solo por color.
      window.Chart.register({
        id: 'valoresAlFinal',
        afterDatasetsDraw(chart, args, opciones) {
          if (!opciones || typeof opciones.formato !== 'function') return;
          const meta = chart.getDatasetMeta(0);
          const { ctx } = chart;
          ctx.save();
          ctx.font = `700 12px ${c.fuente}`;
          ctx.fillStyle = c.titulo;
          ctx.textBaseline = 'middle';
          meta.data.forEach((barra, i) => ctx.fillText(opciones.formato(i), barra.x + 8, barra.y));
          ctx.restore();
        },
      });
    }
  }

  // ── Filtros ────────────────────────────────────────────────────────────────
  const campo = (nombre) => form.elements[nombre];
  function querystring(extra) {
    const params = new URLSearchParams(new FormData(form));
    Object.entries(extra || {}).forEach(([k, v]) => params.set(k, v));
    return params.toString();
  }
  function acotarConvocatorias() {
    const segmento = campo('segmento').value;
    const select = campo('convocatoria');
    Array.from(select.options).forEach((opcion) => {
      if (!opcion.value) return;
      const visible = !segmento || opcion.dataset.segmento === segmento;
      opcion.hidden = !visible;
      if (!visible && opcion.selected) select.value = '';
    });
  }
  function cargarRelevamientos(lista, seleccionado) {
    const select = campo('relevamiento');
    while (select.options.length > 1) select.remove(1);
    lista.forEach((rel) => {
      const opcion = document.createElement('option');
      opcion.value = rel.id;
      opcion.textContent = `${rel.nombre.split(' · ')[0]} · ${rel.tipo === 'Formulario público' ? 'Link público' : rel.territorial || rel.tipo} · ${rel.estado}`;
      select.appendChild(opcion);
    });
    select.disabled = lista.length === 0;
    select.title = select.disabled ? 'Elegí una convocatoria para filtrar por relevamiento' : '';
    select.value = seleccionado ? String(seleccionado) : '';
  }

  // ── Carga ──────────────────────────────────────────────────────────────────
  function ocupado(estado) {
    raiz.setAttribute('aria-busy', String(estado));
    $$('[data-dash-card], [data-dash="kpis"]').forEach((el) => el.classList.toggle('opacity-60', estado));
  }
  function mostrarError(texto) {
    const caja = $('[data-dash="error"]');
    caja.classList.toggle('hidden', !texto);
    $('[data-dash="error-texto"]').textContent = texto || '';
  }
  async function cargar(extra) {
    if (controlador) controlador.abort();
    controlador = new AbortController();
    ocupado(true);
    try {
      const respuesta = await fetch(`${urlDatos}?${querystring(extra)}`, {
        signal: controlador.signal,
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
      });
      const cuerpo = await respuesta.json().catch(() => ({}));
      if (!respuesta.ok) {
        mostrarError((cuerpo.errores || ['No se pudo calcular el tablero.']).join(' '));
        return;
      }
      mostrarError('');
      ultimo = cuerpo;
      sincronizarFiltros(cuerpo);
      pintar(cuerpo);
    } catch (error) {
      if (error.name !== 'AbortError') mostrarError('No se pudo conectar con el servidor. Probá de nuevo.');
    } finally {
      ocupado(false);
    }
  }
  function sincronizarFiltros(cuerpo) {
    const aplicados = cuerpo.filtros_aplicados || {};
    campo('convocatoria').value = aplicados.convocatoria ? String(aplicados.convocatoria) : '';
    cargarRelevamientos((cuerpo.opciones && cuerpo.opciones.relevamientos) || [], aplicados.relevamiento);
    if (aplicados.pregunta && campo('pregunta')) campo('pregunta').value = aplicados.pregunta;
  }

  // ── Pintado ────────────────────────────────────────────────────────────────
  function pintar(cuerpo) {
    const datos = cuerpo.datos;
    const i = datos.indicadores;
    pintarAlcance(datos.alcance);
    const cuando = new Date(datos.calculado_en);
    const calculado = $('[data-dash="calculado-texto"]');
    calculado.textContent = `Datos al ${cuando.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit' })} ${cuando.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit', hour12: false })}`;
    calculado.parentElement.title = cuerpo.desde_cache
      ? 'Servido desde la caché: los totales se recalculan cada 5 minutos o con «Actualizar».'
      : 'Recién calculado. Los totales se guardan 5 minutos.';

    kpi('convocatorias_activas', fmt(i.convocatorias_activas));
    kpi('convocatorias_total', fmt(i.convocatorias_total));
    kpi('convocatorias_nota', i.convocatorias_cerradas_vencimiento ? `${fmt(i.convocatorias_cerradas_vencimiento)} cerrada${i.convocatorias_cerradas_vencimiento === 1 ? '' : 's'} por vencimiento` : 'Ninguna cerrada por vencimiento');
    kpi('relevamientos_en_curso', fmt(i.relevamientos_en_curso));
    kpi('relevamientos_nota', `${fmt(i.relevamientos_total)} en total · ${fmt(i.relevamientos_publicos)} con link público`);
    kpi('formularios_recibidos', fmt(i.formularios_recibidos));
    const variacion = $('[data-kpi="variacion"]');
    variacion.textContent = '';
    variacion.className = 'text-xs font-bold';
    if (typeof i.variacion_periodo_anterior === 'number') {
      const v = i.variacion_periodo_anterior;
      variacion.textContent = `${v > 0 ? '▲' : v < 0 ? '▼' : '='} ${Math.abs(v)} %`;
      variacion.classList.add(v > 0 ? 'text-fg-success' : v < 0 ? 'text-fg-danger' : 'text-body-subtle');
      kpi('formularios_nota', 'vs. el período anterior');
    } else {
      kpi('formularios_nota', 'en el período elegido');
    }
    pintarSparkline(datos.serie_semanal);
    kpi('aprobados', fmt(i.aprobados));
    kpi('aprobados_nota', `${pct(i.tasa_aprobacion)} de lo recibido · ${fmt(i.pendientes)} pendientes de revisión`);
    const ratio = i.cupo_total ? i.cupo_ocupado / i.cupo_total : 0;
    kpi('cupo_pct', fmt(ratio * 100));
    kpi('cupo_nota', i.cupo_total ? `${fmt(i.cupo_ocupado)} de ${fmt(i.cupo_total)} lugares · ${fmt(Math.max(0, i.cupo_total - i.cupo_ocupado))} disponibles` : 'Sin cupo definido');
    const barra = $('[data-kpi="cupo_barra"]');
    barra.style.width = `${Math.min(100, Math.round(ratio * 100))}%`;
    barra.style.background = ratio >= 0.95 ? 'var(--text-fg-danger)' : ratio >= 0.8 ? 'var(--text-fg-warning-subtle)' : 'var(--text-fg-brand)';
    kpi('lista_espera', fmt(i.lista_espera));
    kpi('espera_nota', i.lista_espera ? 'personas aprobadas sin lugar todavía' : 'nadie esperando lugar');

    pintarSemanas(datos);
    pintarEstados(datos);
    pintarConvocatorias(datos);
    pintarBarras('relevamientos', datos.relevamientos_por_estado.map((f) => f.etiqueta), datos.relevamientos_por_estado.map((f) => f.total), {
      subtitulo: `${fmt(i.relevamientos_total)} relevamiento${i.relevamientos_total === 1 ? '' : 's'} en el alcance · no se recortan por fecha`,
      columnas: ['Estado', 'Relevamientos'],
      vacio: i.relevamientos_total === 0,
    });
    pintarBarras('embudo', datos.embudo.map((f) => f.etapa), datos.embudo.map((f) => f.total), {
      subtitulo: `${pct(i.tasa_aprobacion)} de lo recibido llega a aprobado`,
      etiqueta: (k) => `${fmt(datos.embudo[k].total)} · ${pct(datos.embudo[k].pct)}`,
      columnas: ['Etapa', 'Cantidad', '% sobre recibidos'],
      filas: datos.embudo.map((f) => [f.etapa, fmt(f.total), pct(f.pct)]),
      vacio: i.formularios_recibidos === 0,
      maximo: i.formularios_recibidos,
    });
    pintarBarras('territoriales', datos.territoriales.map((f) => f.nombre), datos.territoriales.map((f) => f.formularios), {
      subtitulo: datos.territoriales.length ? 'Formularios cargados en campo · solo canal territorial' : 'Solo aplica al canal territorial',
      columnas: ['Territorial', 'Relevamientos', 'Formularios', 'Aprobados'],
      filas: datos.territoriales.map((f) => [f.nombre, fmt(f.relevamientos), fmt(f.formularios), fmt(f.aprobados)]),
      vacio: datos.territoriales.length === 0,
    });
    pintarBarras('localidades', datos.localidades.top.map((f) => f.localidad), datos.localidades.top.map((f) => f.total), {
      subtitulo: `Según el domicilio del legajo · ${fmt(datos.localidades.detalle.length)} localidad${datos.localidades.detalle.length === 1 ? '' : 'es'}`,
      columnas: ['Localidad', 'Formularios', '%'],
      filas: datos.localidades.detalle.map((f) => [f.localidad, fmt(f.total), pct(f.pct)]),
      vacio: datos.localidades.top.length === 0,
    });
    pintarRespuestas(cuerpo.respuestas);
  }
  function kpi(nombre, texto) {
    const el = $(`[data-kpi="${nombre}"]`);
    if (el) el.textContent = texto;
  }

  // El alcance vigente como chips: se lee de un vistazo y es lo que encabeza las exportaciones.
  function pintarAlcance(alcance) {
    const caja = $('[data-dash="alcance"]');
    caja.textContent = '';
    const rotulo = document.createElement('span');
    rotulo.className = 'font-semibold text-body';
    rotulo.textContent = 'Mostrando';
    caja.appendChild(rotulo);
    String(alcance).split(' · ').forEach((parte) => {
      const chip = document.createElement('span');
      chip.className = 'badge badge-white';
      chip.textContent = parte;
      caja.appendChild(chip);
    });
  }

  // Minigráfico de las últimas doce semanas dentro del indicador de formularios: trazo en
  // gris de apoyo y último punto en color de marca, con currentColor (sin hex en el JS).
  function pintarSparkline(serie) {
    const caja = $('[data-kpi="sparkline"]');
    if (!caja) return;
    caja.textContent = '';
    const puntos = serie.slice(-12).map((f) => f.total);
    if (puntos.length < 2) return;
    const W = 120;
    const H = 28;
    const maximo = Math.max(1, ...puntos);
    const coords = puntos.map((v, k) => [((k / (puntos.length - 1)) * (W - 6) + 3).toFixed(1), (H - 3 - ((H - 8) * v) / maximo).toFixed(1)]);
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.setAttribute('class', 'w-full h-full block');
    const linea = document.createElementNS(ns, 'polyline');
    linea.setAttribute('points', coords.map((c) => c.join(',')).join(' '));
    linea.setAttribute('fill', 'none');
    linea.setAttribute('stroke', 'currentColor');
    linea.setAttribute('stroke-width', '1.5');
    linea.setAttribute('vector-effect', 'non-scaling-stroke');
    linea.setAttribute('class', 'text-body-subtle');
    const punto = document.createElementNS(ns, 'circle');
    const [cx, cy] = coords[coords.length - 1];
    punto.setAttribute('cx', cx);
    punto.setAttribute('cy', cy);
    punto.setAttribute('r', '3');
    punto.setAttribute('fill', 'currentColor');
    punto.setAttribute('class', 'text-fg-brand');
    svg.appendChild(linea);
    svg.appendChild(punto);
    caja.appendChild(svg);
  }

  function dibujar(bloque, config) {
    const contenedor = $(`[data-dash-grafico="${bloque}"]`);
    const canvas = contenedor.querySelector('canvas');
    if (charts[bloque]) charts[bloque].destroy();
    charts[bloque] = new window.Chart(canvas.getContext('2d'), config);
  }
  function estadoVacio(bloque, vacio) {
    const grafico = $(`[data-dash-grafico="${bloque}"]`);
    const tabla = $(`[data-dash-tabla="${bloque}"]`);
    const sinDatos = $(`[data-dash-vacio="${bloque}"]`);
    if (sinDatos) sinDatos.classList.toggle('hidden', !vacio);
    const modoTabla = Boolean(vistaTabla[bloque]);
    if (grafico) grafico.classList.toggle('hidden', vacio || modoTabla);
    if (tabla) tabla.classList.toggle('hidden', vacio || !modoTabla);
  }
  function subtitulo(bloque, texto) {
    const el = $(`[data-dash-sub="${bloque}"]`);
    if (el) el.textContent = texto;
  }

  // Tabla densa canónica, armada con textContent (los rótulos vienen del servidor).
  function tabla(bloque, columnas, filas, alineadas, densa) {
    const contenedor = $(`[data-dash-tabla="${bloque}"]`);
    if (!contenedor) return;
    contenedor.textContent = '';
    const table = document.createElement('table');
    table.className = 'w-full border-collapse';
    const px = densa ? 'px-3' : 'px-4';
    const thead = document.createElement('thead');
    const trh = document.createElement('tr');
    trh.className = 'bg-secondary border-b border-base';
    columnas.forEach((col, idx) => {
      const th = document.createElement('th');
      th.className = `${px} py-[11px] ${idx > 0 && alineadas !== false ? 'text-right' : 'text-left'} font-bold uppercase tracking-[.05em] text-body-subtle`;
      th.style.fontSize = '11px';
      th.textContent = col;
      trh.appendChild(th);
    });
    thead.appendChild(trh);
    const tbody = document.createElement('tbody');
    filas.forEach((fila) => {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-secondary';
      fila.forEach((valor, idx) => {
        const td = document.createElement('td');
        td.className = `${px} py-[13px] text-sm border-t border-light ${idx > 0 && alineadas !== false ? 'text-right text-heading font-semibold whitespace-nowrap tabular-nums' : 'text-body'}`;
        if (valor instanceof Node) td.appendChild(valor);
        else td.textContent = valor;
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(thead);
    table.appendChild(tbody);
    contenedor.appendChild(table);
  }

  function pintarBarras(bloque, etiquetas, valores, opciones) {
    const c = paleta();
    subtitulo(bloque, opciones.subtitulo || '');
    estadoVacio(bloque, Boolean(opciones.vacio));
    tabla(bloque, opciones.columnas, opciones.filas || etiquetas.map((e, k) => [e, fmt(valores[k])]));
    if (opciones.vacio) return;
    // Alto proporcional a las filas: una tarjeta con dos barras no lleva el mismo aire que una con ocho.
    const contenedor = $(`[data-dash-grafico="${bloque}"]`);
    contenedor.style.height = `${Math.max(120, etiquetas.length * 34 + 44)}px`;
    const formato = opciones.etiqueta || ((k) => fmt(valores[k]));
    dibujar(bloque, {
      type: 'bar',
      data: {
        labels: etiquetas.map((e) => partir(e, 16)),
        datasets: [{ data: valores, backgroundColor: opciones.color || c.brand, barThickness: 18, borderRadius: { topRight: 4, bottomRight: 4 }, borderSkipped: false }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { right: 72 } },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { title: (items) => etiquetas[items[0].dataIndex], label: (ctx) => ` ${formato(ctx.dataIndex)}` } },
          valoresAlFinal: { formato },
        },
        scales: {
          x: { beginAtZero: true, suggestedMax: opciones.maximo || undefined, grid: { color: c.grilla, drawTicks: false }, border: { display: false }, ticks: { precision: 0, maxTicksLimit: 5 } },
          y: { grid: { display: false }, border: { display: false }, ticks: { autoSkip: false, font: { weight: '600', size: 11 } } },
        },
      },
    });
  }

  function pintarSemanas(datos) {
    const c = paleta();
    const serie = datos.serie_semanal;
    const total = datos.indicadores.formularios_recibidos;
    subtitulo('semanas', serie.length ? `${fmt(total)} formularios · promedio ${fmt(total / serie.length)} por semana` : '');
    estadoVacio('semanas', serie.length === 0);
    let acumulado = 0;
    tabla('semanas', ['Semana', 'Formularios', 'Acumulado'], serie.map((f) => [`${fecha(f.semana)} – ${fecha(f.hasta)}`, fmt(f.total), fmt((acumulado += f.total))]));
    if (!serie.length) return;
    const ultimoIndice = serie.length - 1;
    dibujar('semanas', {
      type: 'line',
      data: {
        labels: serie.map((f) => fecha(f.hasta).slice(0, 5)),
        datasets: [{
          data: serie.map((f) => f.total),
          borderColor: c.brand,
          backgroundColor: conAlfa(c.brand, 0.1),
          fill: true,
          tension: 0.25,
          borderWidth: 2,
          pointRadius: (ctx) => (ctx.dataIndex === ultimoIndice ? 4 : 0),
          pointHoverRadius: 5,
          pointBackgroundColor: c.brand,
          pointBorderColor: c.superficie,
          pointBorderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { title: (items) => `Semana del ${fecha(serie[items[0].dataIndex].semana)} al ${fecha(serie[items[0].dataIndex].hasta)}`, label: (ctx) => ` ${fmt(ctx.raw)} formularios` } },
        },
        scales: {
          x: { grid: { display: false }, border: { display: false }, ticks: { maxTicksLimit: 8, maxRotation: 0 } },
          y: { beginAtZero: true, grid: { color: c.grilla, drawTicks: false }, border: { display: false }, ticks: { precision: 0, maxTicksLimit: 5 } },
        },
      },
    });
  }

  // Estado de los formularios sin canvas: barra apilada, una fila por estado y el corte por
  // canal, todo con DOM y tokens. Es la tarjeta que más se lee de un vistazo.
  const COLOR_ESTADO = {
    ENVIADO: 'var(--color-brand-400)',
    APROBADO: 'var(--color-emerald-600)',
    RECHAZADO: 'var(--color-rose-600)',
    BAJA: 'var(--color-gray-400)',
  };
  const nombreEstado = (f) => (f.clave === 'ENVIADO' ? 'Pendientes de revisión' : f.etiqueta);
  const nombreCanal = (f) => (f.clave === 'PUBLICO' ? 'Link público' : f.etiqueta);

  function pintarEstados(datos) {
    const total = datos.indicadores.formularios_recibidos;
    const revisados = datos.estados.filter((f) => f.clave !== 'ENVIADO').reduce((a, f) => a + f.total, 0);
    subtitulo('estados', total ? `${fmt(total)} formularios · ${pct((revisados * 100) / total)} ya revisados` : '');
    estadoVacio('estados', total === 0);
    tabla(
      'estados',
      ['Estado', 'Formularios', '%'],
      datos.estados
        .map((f) => [nombreEstado(f), fmt(f.total), pct(total ? (f.total * 100) / total : 0)])
        .concat(datos.canales.map((f) => [`Canal: ${nombreCanal(f)}`, fmt(f.total), pct(total ? (f.total * 100) / total : 0)])),
    );
    const caja = $('[data-dash-grafico="estados"]');
    caja.textContent = '';
    if (!total) return;

    // Barra apilada con separaciones de 2 px en el color de la superficie.
    const barra = document.createElement('div');
    barra.className = 'flex h-3 rounded-full overflow-hidden bg-secondary';
    datos.estados.filter((f) => f.total > 0).forEach((f, k) => {
      const seg = document.createElement('div');
      seg.className = 'h-full';
      seg.style.width = `${(f.total * 100) / total}%`;
      seg.style.background = COLOR_ESTADO[f.clave] || 'var(--color-brand-500)';
      if (k > 0) seg.style.borderLeft = '2px solid var(--bg-primary)';
      seg.title = `${nombreEstado(f)}: ${fmt(f.total)} (${pct((f.total * 100) / total)})`;
      barra.appendChild(seg);
    });
    caja.appendChild(barra);

    // Una fila por estado: punto de color, nombre, cantidad y porcentaje alineados.
    const lista = document.createElement('ul');
    lista.className = 'space-y-2';
    datos.estados.forEach((f) => {
      const li = document.createElement('li');
      li.className = 'flex items-center gap-2 text-sm';
      const punto = document.createElement('span');
      punto.className = 'w-2.5 h-2.5 rounded-sm flex-shrink-0';
      punto.style.background = COLOR_ESTADO[f.clave] || 'var(--color-brand-500)';
      const nombre = document.createElement('span');
      nombre.className = 'text-body flex-1 min-w-0 truncate';
      nombre.textContent = nombreEstado(f);
      const cantidad = document.createElement('span');
      cantidad.className = 'text-heading font-semibold tabular-nums';
      cantidad.textContent = fmt(f.total);
      const porcentaje = document.createElement('span');
      porcentaje.className = 'text-body-subtle text-xs tabular-nums w-14 text-right';
      porcentaje.textContent = pct((f.total * 100) / total);
      li.append(punto, nombre, cantidad, porcentaje);
      lista.appendChild(li);
    });
    caja.appendChild(lista);

    // Corte por canal de carga.
    const titulo = document.createElement('p');
    titulo.className = 'text-xs font-bold uppercase tracking-[.05em] text-body-subtle pt-3 border-t border-light';
    titulo.textContent = 'Por canal de carga';
    caja.appendChild(titulo);
    const canales = document.createElement('div');
    canales.className = 'space-y-2';
    datos.canales.forEach((f) => {
      const fila = document.createElement('div');
      fila.className = 'flex items-center gap-3 text-sm';
      const nombre = document.createElement('span');
      nombre.className = 'text-body w-24 flex-shrink-0';
      nombre.textContent = nombreCanal(f);
      fila.appendChild(nombre);
      fila.appendChild(medidor(total ? f.total / total : 0, 'flex-1'));
      const cantidad = document.createElement('span');
      cantidad.className = 'text-heading font-semibold tabular-nums w-14 text-right';
      cantidad.textContent = fmt(f.total);
      fila.appendChild(cantidad);
      canales.appendChild(fila);
    });
    caja.appendChild(canales);
  }

  function medidor(ratio, ancho, nivel) {
    const pista = document.createElement('div');
    pista.className = `h-2 rounded-full bg-brand-soft overflow-hidden ${ancho || 'w-24'}`;
    const relleno = document.createElement('div');
    relleno.className = 'h-full rounded-full';
    relleno.style.width = `${Math.min(100, Math.round(ratio * 100))}%`;
    relleno.style.background = nivel === 'crit' ? 'var(--text-fg-danger)' : nivel === 'warn' ? 'var(--text-fg-warning-subtle)' : 'var(--text-fg-brand)';
    pista.appendChild(relleno);
    return pista;
  }
  function celdaMedidor(ratio, texto, nivel) {
    const caja = document.createElement('div');
    caja.className = 'flex items-center justify-end gap-2';
    caja.appendChild(medidor(ratio, 'w-20', nivel));
    const span = document.createElement('span');
    span.className = 'text-xs font-semibold text-heading whitespace-nowrap tabular-nums';
    span.style.minWidth = '3.5rem';
    span.textContent = texto;
    caja.appendChild(span);
    return caja;
  }
  function pintarConvocatorias(datos) {
    const filas = datos.convocatorias;
    const vacio = $('[data-dash-vacio="convocatorias"]');
    const contenedor = $('[data-dash-tabla="convocatorias"]');
    vacio.classList.toggle('hidden', filas.length > 0);
    contenedor.classList.toggle('hidden', filas.length === 0);
    subtitulo('convocatorias', `${fmt(filas.length)} convocatoria${filas.length === 1 ? '' : 's'} en el alcance · el cupo se mide sobre el total aprobado del segmento, sin filtro de período`);
    const cuerpo = filas.map((c) => {
      const titulo = document.createElement('div');
      titulo.style.maxWidth = '17rem';
      const nombre = document.createElement('a');
      nombre.className = 'text-fg-brand hover:underline font-semibold';
      nombre.href = urlConvocatoria.replace('/0/', `/${c.id}/`);
      nombre.textContent = c.nombre;
      const sub = document.createElement('div');
      sub.className = 'text-xs text-body-subtle mt-0.5 flex items-center gap-1.5 flex-wrap';
      sub.appendChild(document.createTextNode(`${c.segmento}${c.subsegmento ? ' · ' + c.subsegmento : ''} · ${fecha(c.fecha_inicio)} – ${fecha(c.fecha_fin)}`));
      const badge = document.createElement('span');
      badge.className = `badge badge-dot ${c.activa ? 'badge-success' : 'badge-gray'}`;
      badge.textContent = c.estado;
      sub.appendChild(badge);
      titulo.appendChild(nombre);
      titulo.appendChild(sub);
      const rels = document.createElement('div');
      rels.appendChild(document.createTextNode(fmt(c.relevamientos)));
      const enCurso = document.createElement('div');
      enCurso.className = 'text-xs text-body-subtle font-normal';
      enCurso.textContent = `${fmt(c.en_curso)} en curso`;
      rels.appendChild(enCurso);
      const recibidos = document.createElement('div');
      recibidos.appendChild(document.createTextNode(fmt(c.recibidos)));
      const revisado = document.createElement('div');
      revisado.className = 'text-xs text-body-subtle font-normal';
      revisado.textContent = `${pct(c.revisado_pct)} revisado`;
      recibidos.appendChild(revisado);
      const ratioCupo = c.cupo_segmento ? c.cupo_ocupado / c.cupo_segmento : 0;
      const nivel = ratioCupo >= 0.95 ? 'crit' : ratioCupo >= 0.8 ? 'warn' : '';
      return [
        titulo,
        rels,
        recibidos,
        fmt(c.aprobados),
        fmt(c.rechazados),
        fmt(c.pendientes),
        celdaMedidor(ratioCupo, c.cupo_segmento ? `${fmt(c.cupo_ocupado)}/${fmt(c.cupo_segmento)}` : 'sin cupo', nivel),
      ];
    });
    tabla('convocatorias', ['Convocatoria', 'Relevamientos', 'Recibidos', 'Aprobados', 'Rechazados', 'Pendientes', 'Cupo del segmento'], cuerpo, true, true);
  }

  function pintarRespuestas(respuestas) {
    if (!respuestas) {
      subtitulo('respuestas', 'El programa no tiene preguntas de opciones cerradas.');
      estadoVacio('respuestas', true);
      return;
    }
    const nota = respuestas.multiple ? ' · pueden marcar más de una opción, los porcentajes pueden sumar más de 100 %' : '';
    pintarBarras('respuestas', respuestas.opciones.map((o) => o.opcion), respuestas.opciones.map((o) => o.total), {
      subtitulo: `${respuestas.origen} · ${respuestas.tipo} · ${fmt(respuestas.base)} formularios con respuesta${nota}`,
      etiqueta: (k) => `${fmt(respuestas.opciones[k].total)} · ${pct(respuestas.opciones[k].pct)}`,
      columnas: ['Opción', 'Respuestas', '% de los formularios'],
      filas: respuestas.opciones.map((o) => [o.opcion, fmt(o.total), pct(o.pct)]),
      vacio: respuestas.base === 0,
    });
  }

  // ── Eventos ────────────────────────────────────────────────────────────────
  form.addEventListener('change', (evento) => {
    const nombre = evento.target.name;
    if (nombre === 'segmento') {
      acotarConvocatorias();
      campo('relevamiento').value = '';
    }
    if (nombre === 'convocatoria') campo('relevamiento').value = '';
    if (nombre === 'periodo' && evento.target.value === 'custom' && !(campo('desde').value && campo('hasta').value)) return;
    if (abierto) cargar();
  });
  const preguntaSelect = document.getElementById('dash-pregunta');
  if (preguntaSelect) preguntaSelect.addEventListener('change', () => abierto && cargar());

  const recalcular = $('[data-dash="recalcular"]');
  if (recalcular) recalcular.addEventListener('click', () => cargar({ recalcular: '1' }));

  $$('[data-dash-toggle]').forEach((boton) => {
    boton.addEventListener('click', () => {
      const bloque = boton.dataset.dashToggle;
      vistaTabla[bloque] = !vistaTabla[bloque];
      boton.setAttribute('aria-pressed', String(vistaTabla[bloque]));
      boton.setAttribute('aria-label', vistaTabla[bloque] ? 'Ver como gráfico' : 'Ver como tabla');
      const vacio = $(`[data-dash-vacio="${bloque}"]`);
      estadoVacio(bloque, Boolean(vacio && !vacio.classList.contains('hidden')));
    });
  });

  $$('[data-dash-exportar]').forEach((enlace) => {
    enlace.addEventListener('click', (evento) => {
      evento.preventDefault();
      if (!urlExportar) return;
      const formato = enlace.dataset.dashExportar;
      const extra = enlace.dataset.bloque ? { bloque: enlace.dataset.bloque } : {};
      window.location.href = `${urlExportar.replace('FORMATO', formato)}?${querystring(extra)}`;
    });
  });
  const imprimir = $('[data-dash="imprimir"]');
  if (imprimir) imprimir.addEventListener('click', () => window.print());

  function abrir() {
    if (abierto) return;
    abierto = true;
    cargarChartJs()
      .then(() => {
        prepararChart();
        return cargar();
      })
      .catch((error) => {
        console.error(error);
        mostrarError('No se pudieron cargar los gráficos. Recargá la página.');
      });
  }
  window.addEventListener('becas-dashboard-abrir', abrir);
  if (new URLSearchParams(window.location.search).get('tab') === 'dash') abrir();
})();
