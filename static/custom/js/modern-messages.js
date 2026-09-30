/**
 * Sistema para convertir mensajes de Django en modales modernos
 */

document.addEventListener('DOMContentLoaded', function() {
    // Interceptar mensajes de Django y convertirlos en modales modernos
    const djangoMessages = document.querySelectorAll('.alert, [class*="alert-"], .messages .alert, .message');
    
    djangoMessages.forEach(function(messageElement) {
        const messageText = messageElement.textContent.trim();
        
        if (!messageText || messageText.length === 0) return;
        
        // Determinar el tipo de mensaje basado en las clases CSS
        let messageType = 'info';
        const classList = messageElement.className.toLowerCase();
        
        if (classList.includes('success') || classList.includes('alert-success')) {
            messageType = 'success';
        } else if (classList.includes('error') || classList.includes('alert-error') || classList.includes('alert-danger')) {
            messageType = 'error';
        } else if (classList.includes('warning') || classList.includes('alert-warning')) {
            messageType = 'warning';
        }
        
        // Ocultar el mensaje original
        messageElement.style.display = 'none';
        
        // Mostrar modal moderno después de un pequeño delay
        setTimeout(function() {
            if (window.ModernModal) {
                window.ModernModal.show({
                    type: messageType,
                    title: getMessageTitle(messageType),
                    message: messageText
                });
            }
        }, 100);
    });
    
    // Interceptar mensajes específicos que sabemos que aparecen
    interceptSpecificMessages();
});

function getMessageTitle(type) {
    const titles = {
        success: 'Operación Exitosa',
        error: 'Error',
        warning: 'Advertencia',
        info: 'Información'
    };
    return titles[type] || 'Información';
}

function interceptSpecificMessages() {
    // Interceptar el mensaje "Vínculo agregado exitosamente"
    const originalAlert = window.alert;
    
    window.alert = function(message) {
        if (window.ModernModal) {
            let messageType = 'info';
            let title = 'Información';
            
            // Detectar tipos específicos de mensajes
            const lowerMessage = message.toLowerCase();
            
            if (lowerMessage.includes('exitosamente') || 
                lowerMessage.includes('éxito') || 
                lowerMessage.includes('agregado') ||
                lowerMessage.includes('creado') ||
                lowerMessage.includes('guardado') ||
                lowerMessage.includes('actualizado')) {
                messageType = 'success';
                title = 'Operación Exitosa';
            } else if (lowerMessage.includes('error') || 
                      lowerMessage.includes('falló') ||
                      lowerMessage.includes('no se pudo')) {
                messageType = 'error';
                title = 'Error';
            } else if (lowerMessage.includes('advertencia') || 
                      lowerMessage.includes('cuidado') ||
                      lowerMessage.includes('atención')) {
                messageType = 'warning';
                title = 'Advertencia';
            }
            
            window.ModernModal.show({
                type: messageType,
                title: title,
                message: message
            });
        } else {
            // Fallback al alert original si ModernModal no está disponible
            originalAlert.call(window, message);
        }
    };
}

// Función para mostrar mensajes de éxito específicos
window.showSuccessAlert = function(message) {
    if (window.ModernModal) {
        window.ModernModal.show({
            type: 'success',
            title: 'Operación Exitosa',
            message: message
        });
    } else {
        if (window.toast) window.toast('success', message);
    }
};

// Función para mostrar errores específicos
window.showErrorAlert = function(message) {
    if (window.ModernModal) {
        window.ModernModal.show({
            type: 'error',
            title: 'Error',
            message: message
        });
    } else {
        if (window.toast) window.toast('error', message);
    }
};

// Función para mostrar advertencias específicas
window.showWarningAlert = function(message) {
    if (window.ModernModal) {
        window.ModernModal.show({
            type: 'warning',
            title: 'Advertencia',
            message: message
        });
    } else {
        if (window.toast) window.toast('warning', message);
    }
};
