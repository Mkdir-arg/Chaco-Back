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

    showToast(alerta) {
        const toast = document.createElement('div');
        toast.className = `alert-toast alert-${alerta.prioridad.toLowerCase()}`;
        toast.innerHTML = `
            <div class="flex items-center p-4 mb-4 text-sm rounded-lg border" role="alert">
                <div class="flex-shrink-0">
                    ${this.getAlertIcon(alerta.prioridad)}
                </div>
                <div class="ml-3 text-sm font-medium">
                    <strong>${escaparHtmlAlerta(alerta.ciudadano)}</strong><br>
                    ${escaparHtmlAlerta(alerta.mensaje)}
                </div>
                <button type="button" class="ml-auto -mx-1.5 -my-1.5 rounded-lg p-1.5" onclick="this.parentElement.parentElement.remove()">
                    <span class="sr-only">Cerrar</span>
                    <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
                    </svg>
                </button>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        // Auto-remove después de 5 segundos
        setTimeout(() => {
            if (toast.parentNode) {
                toast.remove();
            }
        }, 5000);
    }

    showCriticalModal(alerta) {
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50';
        modal.innerHTML = `
            <div class="bg-white rounded-lg p-6 max-w-md mx-4 animate-pulse">
                <div class="flex items-center mb-4">
                    <div class="flex-shrink-0">
                        <svg class="w-8 h-8 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
                        </svg>
                    </div>
                    <h3 class="ml-3 text-lg font-medium text-red-800">ALERTA CRÍTICA</h3>
                </div>
                <div class="mb-4">
                    <p class="text-sm text-gray-600"><strong>Ciudadano:</strong> ${escaparHtmlAlerta(alerta.ciudadano)}</p>
                    <p class="text-sm text-gray-600 mt-2">${escaparHtmlAlerta(alerta.mensaje)}</p>
                    <p class="text-xs text-gray-500 mt-2">${escaparHtmlAlerta(alerta.fecha)}</p>
                </div>
                <div class="flex justify-end space-x-3">
                    <button onclick="this.closest('.fixed').remove()" class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300">
                        Cerrar
                    </button>
                    <a href="/legajos/${escaparHtmlAlerta(alerta.legajo_id)}/" class="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700">
                        Ver Legajo
                    </a>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Auto-remove después de 10 segundos
        setTimeout(() => {
            if (modal.parentNode) {
                modal.remove();
            }
        }, 10000);
    }

    getAlertIcon(prioridad) {
        const icons = {
            'CRITICA': '<svg class="w-4 h-4 text-red-600" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path></svg>',
            'ALTA': '<svg class="w-4 h-4 text-orange-600" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path></svg>',
            'MEDIA': '<svg class="w-4 h-4 text-yellow-600" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path></svg>',
            'BAJA': '<svg class="w-4 h-4 text-blue-600" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path></svg>'
        };
        return icons[prioridad] || icons['BAJA'];
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

    updateAlertasCounter() {
        // Actualizar contador de alertas en la UI
        const counter = document.querySelector('#alertas-counter');
        if (counter) {
            fetch('/legajos/alertas/count/')
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    counter.textContent = data.count;
                    counter.classList.toggle('hidden', data.count === 0);
                    
                    // Cargar preview de alertas
                    this.loadAlertasPreview();
                })
                .catch(error => {
                    console.error('Error actualizando contador de alertas:', error);
                    counter.classList.add('hidden');
                });
        }
    }
    
    loadAlertasPreview() {
        const preview = document.querySelector('#alertas-preview');
        if (!preview) return;
        
        // Intentar primero el endpoint simple
        fetch('/legajos/alertas/preview/')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                const alertas = data.results || data;
                if (alertas && alertas.length > 0) {
                    preview.innerHTML = alertas.map(alerta => `
                        <div class="p-3 border-b border-gray-100 hover:bg-gray-50">
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
            .then(response => response.json())
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
    window.alertasWS = new AlertasWebSocket();
    
    // Cargar contador inicial
    setTimeout(() => {
        if (window.alertasWS) {
            window.alertasWS.updateAlertasCounter();
        }
    }, 1000);
});
