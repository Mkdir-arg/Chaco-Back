// WebSocket global para lista de conversaciones (sin recargar la página)
(function() {
    const listaApp = document.getElementById('conversaciones-lista-app');
    if (!listaApp) {
        return;
    }

    if (window.__conversacionesListaWsInitialized) {
        return;
    }
    window.__conversacionesListaWsInitialized = true;

    function notificarEstadoWebSocket() {
        window.dispatchEvent(new Event('conversaciones:lista-ws-estado'));
    }

    function buildConversationUrl(template, conversacionId) {
        if (!template) return '';
        return template.replace('/0/', `/${conversacionId}/`);
    }

    function getListaConfig() {
        return {
            detailApiTemplate: listaApp ? listaApp.dataset.detailApiUrlTemplate : '',
            detailTemplate: listaApp ? listaApp.dataset.detailUrlTemplate : '',
            closeTemplate: listaApp ? listaApp.dataset.closeUrlTemplate : '',
            wsPath: listaApp ? listaApp.dataset.listWsPath : '/ws/conversaciones/',
        };
    }

    function incChatsNoAtendidos(delta) {
        const el = document.querySelector('[data-stat="chats-no-atendidos"]');
        if (!el) return;
        const actual = parseInt(el.textContent) || 0;
        const nuevo = actual + delta;
        el.textContent = nuevo;
        el.style.backgroundColor = '#fef3c7';
        setTimeout(() => el.style.backgroundColor = '', 1200);
    }

    function notificar(mensaje) {
        const prev = document.querySelectorAll('.notif-conv-lista');
        prev.forEach(n => n.remove());
        const n = document.createElement('div');
        n.className = 'notif-conv-lista fixed top-4 right-4 z-50 p-4 rounded-lg shadow-lg text-white bg-green-600';
        n.innerHTML = `<div class="flex items-center"><span>${mensaje}</span><button class="ml-3" aria-label="Cerrar">✕</button></div>`;
        n.querySelector('button').addEventListener('click', () => n.remove());
        document.body.appendChild(n);
        setTimeout(() => { if (n.parentElement) n.remove(); }, 4000);
    }

    function agregarFilaDesktop(conv) {
        const config = getListaConfig();
        const tbody = document.querySelector('table tbody');
        if (!tbody) return;
        // Evitar duplicados
        if (document.querySelector(`tr[data-conversacion-id="${conv.id}"]`)) return;
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-gray-50';
        tr.setAttribute('data-conversacion-id', conv.id);
        const tipoBadge = (conv.tipo && String(conv.tipo).toLowerCase() === 'personal') ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800';
        const estadoBadge = (conv.estado === 'activa') ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800';
        tr.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">#${conv.id}</td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${tipoBadge}">${conv.tipo || ''}</span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${conv.dni || '-'} ${conv.sexo ? `<span class="text-xs text-gray-500">(${conv.sexo})</span>` : ''}</td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${estadoBadge}">${conv.estado_display || conv.estado || ''}</span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${(conv.operador && conv.operador !== null) ? conv.operador : 'Sin asignar'}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${conv.fecha || ''}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">${conv.mensajes || 0}</span>
                ${conv.no_leidos && conv.no_leidos > 0 ? `<span class="contador-mensajes ml-1 inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">${conv.no_leidos} sin leer</span>` : ''}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                <div class="flex space-x-2">
                    <a href="${buildConversationUrl(config.detailTemplate, conv.id)}" class="text-blue-600 hover:text-blue-900"><i class="fas fa-eye"></i> Ver</a>
                    ${(!conv.operador || conv.operador === 'Sin asignar' || conv.operador === null) ? `<button onclick="asignarConversacion(${conv.id})" class="text-green-600 hover:text-green-900"><i class="fas fa-user-plus"></i> Asignar</button>` : ''}
                    ${conv.estado === 'activa' ? `<a href="${buildConversationUrl(config.closeTemplate, conv.id)}" class="text-red-600 hover:text-red-900" onclick="return confirm('¿Estás seguro de cerrar esta conversación?')"><i class="fas fa-times"></i> Cerrar</a>` : ''}
                </div>
            </td>
        `;
        tbody.prepend(tr);
    }

    async function cargarYAgregarConversacion(conversacionId) {
        const config = getListaConfig();
        const url = buildConversationUrl(config.detailApiTemplate, conversacionId);
        if (!url) return;
        try {
            const r = await fetch(url);
            if (!r.ok) return;
            const data = await r.json();
            if (data && data.conversacion) {
                agregarFilaDesktop(data.conversacion);
            }
        } catch (_) {}
    }

    async function actualizarFilaConversacion(conversacionId) {
        const config = getListaConfig();
        const url = buildConversationUrl(config.detailApiTemplate, conversacionId);
        if (!url) return;
        try {
            const r = await fetch(url);
            if (!r.ok) return;
            const data = await r.json();
            if (data && data.conversacion) {
                const conv = data.conversacion;
                const fila = document.querySelector(`tr[data-conversacion-id="${conversacionId}"]`);
                if (fila) {
                    // Actualizar contador de mensajes
                    const mensajesCell = fila.querySelector('td:nth-child(7)');
                    if (mensajesCell) {
                        mensajesCell.innerHTML = `
                            <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">${conv.mensajes || 0}</span>
                            ${conv.no_leidos && conv.no_leidos > 0 ? `<span class="contador-mensajes ml-1 inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800 animate-pulse">${conv.no_leidos} sin leer</span>` : ''}
                        `;
                        setTimeout(() => {
                            const badge = mensajesCell.querySelector('.animate-pulse');
                            if (badge) badge.classList.remove('animate-pulse');
                        }, 1000);
                    }
                }
            }
        } catch (_) {}
    }

    function conectarWS() {
        if (window.conversacionesListaWS && [0, 1].includes(window.conversacionesListaWS.readyState)) return;
        const config = getListaConfig();
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}${config.wsPath}`;
        const ws = new WebSocket(wsUrl);
        window.conversacionesListaWS = ws;
        notificarEstadoWebSocket();

        ws.onopen = () => {
            // console.log('[Conversaciones Lista] WS conectado');
            notificarEstadoWebSocket();
        };
        ws.onmessage = (ev) => {
            try {
                const data = JSON.parse(ev.data);
                if (data.type === 'nueva_conversacion') {
                    incChatsNoAtendidos(1);
                    const msg = data.mensaje || 'Nueva conversación disponible';
                    notificar(msg);
                    let convId = data.conversacion_id;
                    if (!convId && typeof data.mensaje === 'string') {
                        const m = data.mensaje.match(/#(\d+)/);
                        if (m) convId = parseInt(m[1], 10);
                    }
                    if (convId && document.querySelector('table tbody')) {
                        cargarYAgregarConversacion(convId);
                    }
                } else if (data.type === 'nuevo_mensaje') {
                    // Recargar la fila completa para actualizar contadores
                    if (data.conversacion_id) {
                        actualizarFilaConversacion(data.conversacion_id);
                    }
                } else if (data.type === 'actualizar_lista') {
                    // Recargar página cuando se asigna/reasigna
                    setTimeout(() => window.location.reload(), 500);
                }
            } catch (_) {}
        };
        ws.onclose = () => {
            notificarEstadoWebSocket();
            setTimeout(conectarWS, 3000);
        };
        ws.onerror = () => {};
    }

    document.addEventListener('DOMContentLoaded', () => {
        conectarWS();
    });
})();
