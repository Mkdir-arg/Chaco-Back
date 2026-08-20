// Notificación global de conversaciones. En la lista, el WebSocket ya entrega
// esas novedades; el polling HTTP queda activo solo mientras ese socket no esté abierto.
(function () {
    const config = window.conversacionesConfig || {};

    class NotificadorGlobalConversaciones {
        constructor() {
            this.ultimoConteo = null;
            this.polling = null;
        }

        estaEnLista() {
            return Boolean(document.getElementById('conversaciones-lista-app'));
        }

        websocketListaAbierto() {
            return window.conversacionesListaWS && window.conversacionesListaWS.readyState === 1;
        }

        debeUsarPolling() {
            return !this.estaEnLista() || !this.websocketListaAbierto();
        }

        iniciar() {
            if (!config.statsUrl) return;
            window.addEventListener('conversaciones:lista-ws-estado', () => this.actualizarPolling());
            this.actualizarPolling();
        }

        actualizarPolling() {
            if (this.debeUsarPolling()) {
                this.iniciarPolling();
                return;
            }
            this.detenerPolling();
        }

        iniciarPolling() {
            if (this.polling) return;
            this.verificar(true);
            this.polling = setInterval(() => this.verificar(false), 5000);
        }

        detenerPolling() {
            if (!this.polling) return;
            clearInterval(this.polling);
            this.polling = null;
        }

        async verificar(soloBaseline) {
            if (!this.debeUsarPolling()) {
                this.detenerPolling();
                return;
            }
            try {
                const response = await fetch(config.statsUrl, {
                    method: 'GET',
                    headers: {'X-Requested-With': 'XMLHttpRequest'},
                });
                const data = await response.json();
                if (!data.success) return;

                const chatsNoAtendidos = data.estadisticas.chats_no_atendidos;
                if (soloBaseline || this.ultimoConteo === null) {
                    this.ultimoConteo = chatsNoAtendidos;
                    return;
                }
                if (chatsNoAtendidos > this.ultimoConteo) {
                    this.mostrarNotificacion(`${chatsNoAtendidos - this.ultimoConteo} nueva(s) conversación(es) sin atender`);
                }
                this.ultimoConteo = chatsNoAtendidos;
            } catch (_) {
                // El siguiente intervalo o una reconexión del WebSocket reintentará.
            }
        }

        mostrarNotificacion(mensaje) {
            document.querySelectorAll('.notificacion-global-conversaciones').forEach(n => n.remove());
            const notificacion = document.createElement('div');
            notificacion.className = 'notificacion-global-conversaciones fixed top-4 right-4 z-50 p-4 rounded-lg shadow-lg text-white bg-blue-500';
            notificacion.innerHTML = `
                <div class="flex items-center">
                    <span>🆕 ${mensaje}</span>
                    <a href="${config.listUrl || '#'}" class="ml-3 bg-white text-blue-600 px-3 py-1 rounded text-sm hover:bg-gray-100">Ver</a>
                    <button type="button" class="ml-2 text-white hover:text-gray-200" aria-label="Cerrar">✕</button>
                </div>
            `;
            notificacion.querySelector('button').addEventListener('click', () => notificacion.remove());
            document.body.appendChild(notificacion);
            setTimeout(() => notificacion.remove(), 8000);
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        const notificador = new NotificadorGlobalConversaciones();
        notificador.iniciar();
        window.notificadorGlobalConversaciones = notificador;
    });
})();
