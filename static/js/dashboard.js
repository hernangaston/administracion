// JavaScript específico para dashboard
document.addEventListener('DOMContentLoaded', function() {
    
    // Manejar upload de archivos
    const fileInput = document.getElementById('file-input');
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const files = e.target.files;
            if (files.length > 0) {
                const formData = new FormData();
                for (let file of files) {
                    formData.append('files', file);
                }
                
                // Mostrar loading
                const btn = document.querySelector('button[onclick*="file-input"]');
                const originalText = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Procesando...';
                btn.disabled = true;
                
                fetch('/extract-text', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    showNotification(`Procesadas ${data.resultados.length} facturas exitosamente`, 'success');
                    setTimeout(() => location.reload(), 2000);
                })
                .catch(error => {
                    showNotification('Error al procesar facturas: ' + error, 'error');
                })
                .finally(() => {
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                });
            }
        });
    }
    
    // Función para mostrar notificaciones
    function showNotification(message, type) {
        const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
        const notification = document.createElement('div');
        notification.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove después de 5 segundos
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }
    
    // Actualizar contadores en tiempo real (opcional)
    function updateStats() {
        fetch('/api/estadisticas')
            .then(response => response.json())
            .then(data => {
                // Actualizar estadísticas si es necesario
                console.log('Estadísticas actualizadas:', data);
            })
            .catch(error => console.error('Error actualizando stats:', error));
    }
    
    // Actualizar stats cada 30 segundos
    setInterval(updateStats, 30000);
});