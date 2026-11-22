// DOM mínimo para correr el script de la pantalla de proceso masivo en node, sin dependencias. Los
// relojes son falsos: el test decide cuándo pasa el tiempo. El stub de ModernModal
// imita lo que importa del real (base.html): abre el overlay y enfoca «Sí, …» a los 10 ms.
// Entrada por stdin (JSON): {script, escenario, pendientes, pedido}.
const fs = require('fs');
const entrada = JSON.parse(fs.readFileSync(0, 'utf8'));
let ahora = 1000;
Date.now = () => ahora;
let timers = [];
global.setTimeout = (fn, ms) => { timers.push({ fn, en: ahora + (ms || 0) }); };
function avanzar(ms) {
  const hasta = ahora + ms;
  while (true) {
    timers.sort((a, b) => a.en - b.en);
    if (!timers.length || timers[0].en > hasta) break;
    const t = timers.shift();
    ahora = t.en;
    t.fn();
  }
  ahora = hasta;
}
let overlayOculto = true;
let foco = null;
const oyentes = {};
const boton = { disabled: false };
const form = {
  dataset: {},
  elements: { total_pedido: { value: entrada.pedido } },
  envios: 0,
  submit() { this.envios++; },
  querySelector() { return boton; },
  addEventListener(tipo, fn) { oyentes[tipo] = fn; },
};
if (entrada.pendientes !== undefined) form.dataset.pendientes = entrada.pendientes;
const selector = entrada.escenario === 'frenar' ? 'form[data-confirmar-frenar]' : 'form[data-confirmar-masivo]';
global.window = global;
let relecturas = 0;
global.location = { reload() { relecturas++; } };
global.document = {
  querySelector: (sel) => (sel === selector ? form : null),
  getElementById: (id) => {
    if (id === 'modal-overlay') return { classList: { contains: (c) => c === 'hidden' && overlayOculto } };
    if (id === 'modal-cancel') return { focus() { foco = 'cancelar'; } };
    return null;
  },
};
const mostrados = [];
global.ModernModal = {
  show(op) { mostrados.push(op); overlayOculto = false; setTimeout(() => { foco = 'confirmar'; }, 10); },
};
eval(entrada.script);
const evento = { preventDefault() {} };
const r = {};
oyentes.submit(evento);
r.modales = mostrados.length;
r.titulo = mostrados[0] && mostrados[0].title;
r.mensaje = mostrados[0] && mostrados[0].message;
r.boton = mostrados[0] && mostrados[0].confirmText;
r.danger = mostrados[0] && mostrados[0].danger;
avanzar(60);
r.foco = foco;
oyentes.submit(evento);  // un Enter de más sobre el input con el modal abierto
r.modales_tras_otro_submit = mostrados.length;
mostrados[0].onConfirm();  // segundo Enter a los 60 ms del primero: no confirma
r.envios_rapido = form.envios;
avanzar(500);
mostrados[0].onConfirm();
mostrados[0].onConfirm();  // doble clic durante el cierre de ModernModal
r.envios = form.envios;
r.boton_deshabilitado = boton.disabled;
overlayOculto = true;
oyentes.submit(evento);
r.modales_final = mostrados.length;
avanzar(6000);
r.relecturas = relecturas;
process.stdout.write(JSON.stringify(r));
