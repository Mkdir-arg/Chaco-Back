// El nombre del ciudadano y el mensaje de la alerta se escapan antes de entrar a un
// innerHTML: el nombre lo carga el ciudadano en la inscripción pública.
function escaparHtmlAlerta(valor) {
    return String(valor ?? '').replace(/[&<>"']/g, (c) => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));
}

class AlertasWebSocket {
    constructor() {
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectInterval = 3000;
        this.init();
    }

    init() {
        this.connect();
        this.setupNotificationPermission();
    }

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/alertas/`;
        
        this.socket = new WebSocket(wsUrl);
        
        this.socket.onopen = () => {
            console.log('Conectado a alertas WebSocket');
            this.reconnectAttempts = 0;
            this.showConnectionStatus(true);
        };
        
        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
        
        this.socket.onclose = () => {
            console.log('Desconectado de alertas WebSocket');
            this.showConnectionStatus(false);
            this.reconnect();
        };
        
        this.socket.onerror = (error) => {
            console.error('Error WebSocket:', error);
        };
    }

    handleMessage(data) {
        switch(data.type) {
            case 'nueva_alerta':
                this.showAlertaNotification(data.alerta);
                this.updateAlertasCounter();
                break;
            case 'alerta_critica':
                this.showAlertaCritica(data.alerta);
                this.updateAlertasCounter();
                break;
            case 'alerta_cerrada':
                this.removeAlertaFromUI(data.alerta_id);
                this.updateAlertasCounter();
                break;
        }
    }

    showAlertaNotification(alerta) {
        // Notificación toast
        this.showToast(alerta);
        
        // Notificación del navegador
        if (Notification.permission === 'granted') {
            new Notification(`Nueva Alerta - ${alerta.prioridad}`, {
                body: `${alerta.ciudadano}: ${alerta.mensaje}`,
                icon: '/static/custom/img/alert-icon.png',
                tag: `alerta-${alerta.id}`
            });
        }
        
        // Sonido para alertas críticas
        if (alerta.prioridad === 'CRITICA') {
            this.playAlertSound();
        }
    }

    showAlertaCritica(alerta) {
        // Modal para alertas críticas
        this.showCriticalModal(alerta);
        this.playAlertSound();
        
        // Parpadeo en el título
        this.blinkTitle('🚨 ALERTA CRÍTICA');
    }

    // El backoffice tiene un solo sistema de avisos: `window.toast`, que viene del
    // shell. Antes este archivo armaba su propia pila con markup e innerHTML
    // propios, abajo a la derecha igual que la otra, sin rol ARIA ni live region
    // y con clases que el build no genera.
    showToast(alerta) {
        const tipo = alerta.prioridad === 'CRITICA' ? 'error' : 'warning';
        // `window.toast` escribe con textContent: el nombre del ciudadano -que carga
        // el propio ciudadano en la inscripción pública- no necesita escaparse acá.
        window.toast(tipo, `${alerta.ciudadano}: ${alerta.mensaje}`);
    }

    // Destino de «Ver»: el detalle del **ciudadano**. `/legajos/<id>/` no existe como
    // ruta (FE-09) y la plantilla de URL la arma el shell con {% url %}, para no
    // escribir rutas literales en el JS.
    urlDelCiudadano(alerta) {
        const plantilla = (window.alertasConfig || {}).ciudadanoDetalleUrlTemplate;
        if (!plantilla || !alerta.ciudadano_id) return null;
        return plantilla.replace('/0/', `/${alerta.ciudadano_id}/`);
    }

    showCriticalModal(alerta) {
        const url = this.urlDelCiudadano(alerta);
        const opciones = {
            type: 'warning',
            title: 'Alerta crítica',
            message: `${alerta.ciudadano}: ${alerta.mensaje} (${alerta.fecha})`,
        };
        if (url) {
            opciones.confirmText = 'Ver';
            opciones.onConfirm = () => window.location.assign(url);
        }
        window.ModernModal.show(opciones);
    }

    playAlertSound() {
        try {
            const audio = new Audio('/static/custom/sounds/alert.mp3');
            audio.volume = 0.5;
            audio.play().catch(() => {
                // Silenciar error si no se puede reproducir
            });
        } catch (e) {
            // Silenciar error
        }
    }

    blinkTitle(message) {
        const originalTitle = document.title;
        let isBlinking = true;
        
        const blink = setInterval(() => {
            document.title = isBlinking ? message : originalTitle;
            isBlinking = !isBlinking;
        }, 1000);
        
        // Detener después de 10 segundos
        setTimeout(() => {
            clearInterval(blink);
            document.title = originalTitle;
        }, 10000);
    }

    // El dropdown arranca con un spinner: cualquier camino que termine sin datos
    // tiene que reemplazarlo, o la campana queda "Cargando alertas..." para siempre.
    // Pasaba con un rebote por permisos (302 al inicio → 200 de HTML → `json()`
    // revienta y el `catch` solo tocaba el contador).
    mostrarMensajeEnPreview(mensaje, icono = 'fa-exclamation-triangle', color = 'text-gray-500') {
        const preview = document.querySelector('#alertas-preview');
        if (!preview) return;
        preview.innerHTML = `
            <div class="p-4 text-center ${color}">
                <i class="fas ${icono} mb-2"></i>
                <p>${escaparHtmlAlerta(mensaje)}</p>
            </div>
        `;
    }

    // `response.json()` sobre una respuesta que no es JSON —el HTML del inicio, una
    // pantalla de error— tira un `SyntaxError` que no distingue de un fallo de red.
    // Acá se mira antes el status y el content-type.
    leerJson(response) {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const tipo = (response.headers && response.headers.get('content-type')) || '';
        if (tipo && !tipo.includes('application/json')) {
            throw new Error(`Respuesta no JSON (${tipo})`);
        }
        // Sin content-type no se adivina: si no es JSON, `json()` rechaza y el
        // `.catch` de quien llama deja el mensaje en lugar del spinner.
        return response.json();
    }

    updateAlertasCounter() {
        // Actualizar contador de alertas en la UI
        const counter = document.querySelector('#alertas-counter');
        if (counter) {
            fetch('/legajos/alertas/count/')
                .then(response => this.leerJson(response))
                .then(data => {
                    counter.textContent = data.count;
                    counter.classList.toggle('hidden', data.count === 0);

                    // Cargar preview de alertas
                    this.loadAlertasPreview();
                })
                .catch(error => {
                    console.error('Error actualizando contador de alertas:', error);
                    counter.classList.add('hidden');
                    this.mostrarMensajeEnPreview('No se pudieron cargar las alertas');
                });
        }
    }

    loadAlertasPreview() {
        const preview = document.querySelector('#alertas-preview');
        if (!preview) return;

        // Intentar primero el endpoint simple
        fetch('/legajos/alertas/preview/')
            .then(response => this.leerJson(response))
            .then(data => {
                const alertas = data.results || data;
                if (alertas && alertas.length > 0) {
                    preview.innerHTML = alertas.map(alerta => `
                        <div class="p-3 border-b border-light hover:bg-secondary">
                            <div class="flex items-start justify-between">
                                <div class="flex-1">
                                    <p class="text-sm font-medium text-gray-900">${escaparHtmlAlerta(alerta.ciudadano_nombre || 'Sin ciudadano')}</p>
                                    <p class="text-xs text-gray-600 mt-1">${escaparHtmlAlerta(alerta.mensaje)}</p>
                                    <p class="text-xs text-gray-400 mt-1">${new Date(alerta.creado).toLocaleString()}</p>
                                </div>
                                <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                                    alerta.prioridad === 'CRITICA' ? 'bg-red-100 text-red-800' :
                                    alerta.prioridad === 'ALTA' ? 'bg-orange-100 text-orange-800' :
                                    alerta.prioridad === 'MEDIA' ? 'bg-yellow-100 text-yellow-800' :
                                    'bg-blue-100 text-blue-800'
                                }">
                                    ${escaparHtmlAlerta(alerta.prioridad)}
                                </span>
                            </div>
                        </div>
                    `).join('');
                } else {
                    preview.innerHTML = `
                        <div class="p-4 text-center text-gray-500">
                            <i class="fas fa-check-circle text-green-500 text-2xl mb-2"></i>
                            <p>No hay alertas activas</p>
                        </div>
                    `;
                }
            })
            .catch(error => {
                console.error('Error cargando alertas:', error);
                // Fallback: intentar endpoint alternativo
                this.loadAlertasPreviewFallback();
            });
    }
    
    loadAlertasPreviewFallback() {
        const preview = document.querySelector('#alertas-preview');
        if (!preview) return;
        
        // Usar endpoint de views_alertas como fallback
        fetch('/legajos/alertas/count/')
            .then(response => this.leerJson(response))
            .then(data => {
                if (data.count > 0) {
                    preview.innerHTML = `
                        <div class="p-4 text-center text-blue-600">
                            <i class="fas fa-bell text-2xl mb-2"></i>
                            <p class="font-medium">${data.count} alertas activas</p>
                            <p class="text-xs text-gray-500 mt-1">${data.criticas || 0} críticas</p>
                        </div>
                    `;
                } else {
                    preview.innerHTML = `
                        <div class="p-4 text-center text-gray-500">
                            <i class="fas fa-check-circle text-green-500 text-2xl mb-2"></i>
                            <p>No hay alertas activas</p>
                        </div>
                    `;
                }
            })
            .catch(() => {
                preview.innerHTML = `
                    <div class="p-4 text-center text-red-500">
                        <i class="fas fa-exclamation-triangle mb-2"></i>
                        <p>Error cargando alertas</p>
                    </div>
                `;
            });
    }

    removeAlertaFromUI(alertaId) {
        const alertElement = document.querySelector(`[data-alerta-id="${alertaId}"]`);
        if (alertElement) {
            alertElement.remove();
        }
    }

    setupNotificationPermission() {
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }

    showConnectionStatus(connected) {
        const indicator = document.querySelector('#websocket-status');
        if (indicator) {
            indicator.className = connected ? 'text-green-500' : 'text-red-500';
            indicator.title = connected ? 'Conectado' : 'Desconectado';
        }
    }

    reconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            setTimeout(() => {
                console.log(`Reintentando conexión... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
                this.connect();
            }, this.reconnectInterval);
        }
    }
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    // La campana del navbar es la única superficie de este script, y solo se
    // renderiza para quien tiene `ciudadano.ver` (SEC-18): es la misma capacidad
    // que piden `ws/alertas/`, el contador y el preview. Sin campana no hay nada
    // que actualizar, así que no se abre el WebSocket ni se pide un endpoint que
    // va a rebotar. El guard vive en el template, acá solo se lo respeta.
    if (!document.querySelector('#alertas-counter')) {
        return;
    }

    window.alertasWS = new AlertasWebSocket();

    // Cargar contador inicial
    setTimeout(() => {
        if (window.alertasWS) {
            window.alertasWS.updateAlertasCounter();
        }
    }, 1000);
});
