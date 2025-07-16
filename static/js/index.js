// JavaScript para index.html - Guardar como /static/js/index.js

document.addEventListener('DOMContentLoaded', function() {
    console.log('Sistema de Facturas - Lista cargada');
    
    // Manejar formulario de subida
    const uploadForm = document.querySelector('form[action="/extract-text"]');
    if (uploadForm) {
        uploadForm.addEventListener('submit', handleFormSubmit);
    }
    
    // Manejar notificaciones de URL
    handleUrlNotifications();
    
    // Inicializar tooltips y interactividad
    initializeInteractivity();
});

/**
 * Maneja el envío del formulario con feedback visual
 */
function handleFormSubmit(event) {
    const form = event.target;
    const submitBtn = form.querySelector('.submit-btn');
    const fileInput = form.querySelector('input[type="file"]');
    
    // Validar que se hayan seleccionado archivos
    if (!fileInput.files.length) {
        event.preventDefault();
        showNotification('Por favor selecciona al menos un archivo PDF', 'error');
        return false;
    }
    
    // Validar que sean archivos PDF
    const validFiles = Array.from(fileInput.files).every(file => 
        file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
    );
    
    if (!validFiles) {
        event.preventDefault();
        showNotification('Solo se permiten archivos PDF', 'error');
        return false;
    }
    
    // Cambiar estado del botón durante la carga
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Procesando...';
    submitBtn.disabled = true;
    
    // Mostrar feedback visual
    showNotification('Subiendo archivos...', 'info');
    
    // En caso de error, restaurar botón después de un timeout
    setTimeout(() => {
        if (submitBtn.disabled) {
            submitBtn.textContent = originalText;
            submitBtn.disabled = false;
        }
    }, 30000); // 30 segundos timeout
    
    return true;
}

/**
 * Maneja notificaciones basadas en parámetros URL
 */
function handleUrlNotifications() {
    const urlParams = new URLSearchParams(window.location.search);
    
    if (urlParams.get('uploaded') === 'success') {
        showNotification('Facturas procesadas exitosamente', 'success');
        // Limpiar URL sin recargar página
        window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    if (urlParams.get('error')) {
        const errorMsg = urlParams.get('error');
        showNotification(`Error: ${errorMsg}`, 'error');
        window.history.replaceState({}, document.title, window.location.pathname);
    }
}

/**
 * Inicializa interactividad adicional
 */
function initializeInteractivity() {
    // Hover effects para filas de tabla
    const tableRows = document.querySelectorAll('tbody tr');
    tableRows.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#fafafa';
        });
        
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
    });
    
    // Click en fila para ir al detalle
    tableRows.forEach(row => {
        row.addEventListener('click', function(e) {
            // Solo si no se clickeó en un enlace
            if (!e.target.closest('a')) {
                const link = this.querySelector('a[href*="/factura/"]');
                if (link) {
                    window.location.href = link.href;
                }
            }
        });
        
        // Cambiar cursor para indicar que es clickeable
        row.style.cursor = 'pointer';
    });
    
    // Mejorar accesibilidad del input file
    const fileInput = document.querySelector('#file-input');
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            const fileCount = this.files.length;
            if (fileCount > 0) {
                const label = document.querySelector('label[for="file-input"]');
                if (label) {
                    label.textContent = `${fileCount} archivo${fileCount > 1 ? 's' : ''} seleccionado${fileCount > 1 ? 's' : ''}`;
                }
            }
        });
    }
    
    // Atajos de teclado
    document.addEventListener('keydown', function(e) {
        // Ctrl+U para subir archivos
        if (e.ctrlKey && e.key === 'u') {
            e.preventDefault();
            const fileInput = document.querySelector('#file-input');
            if (fileInput) {
                fileInput.click();
            }
        }
        
        // Escape para limpiar selección de archivos
        if (e.key === 'Escape') {
            const fileInput = document.querySelector('#file-input');
            if (fileInput && fileInput.files.length > 0) {
                fileInput.value = '';
                const label = document.querySelector('label[for="file-input"]');
                if (label) {
                    label.textContent = 'Subir nuevas facturas';
                }
            }
        }
    });
}

/**
 * Sistema de notificaciones minimalista
 */
function showNotification(message, type = 'info') {
    // Remover notificación existente
    const existing = document.querySelector('.notification');
    if (existing) {
        existing.remove();
    }
    
    // Crear nueva notificación
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    
    // Estilos inline para asegurar que se vea correctamente
    const baseStyles = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        padding: 16px 24px;
        border: 1px solid;
        font-size: 14px;
        font-weight: 500;
        max-width: 400px;
        animation: slideIn 0.3s ease;
    `;
    
    let typeStyles = '';
    switch (type) {
        case 'success':
            typeStyles = `
                background-color: #f8f8f8;
                border-color: #e6e6e6;
                color: #2a2a2a;
            `;
            break;
        case 'error':
            typeStyles = `
                background-color: #f5f5f5;
                border-color: #e6e6e6;
                color: #666666;
            `;
            break;
        case 'info':
        default:
            typeStyles = `
                background-color: #fafafa;
                border-color: #e6e6e6;
                color: #2a2a2a;
            `;
            break;
    }
    
    notification.style.cssText = baseStyles + typeStyles;
    notification.textContent = message;
    
    // Agregar botón de cerrar
    const closeBtn = document.createElement('button');
    closeBtn.innerHTML = '×';
    closeBtn.style.cssText = `
        background: none;
        border: none;
        font-size: 20px;
        cursor: pointer;
        float: right;
        margin-left: 12px;
        padding: 0;
        color: inherit;
        opacity: 0.7;
    `;
    closeBtn.addEventListener('click', () => notification.remove());
    
    notification.appendChild(closeBtn);
    document.body.appendChild(notification);
    
    // Auto-remover después de 5 segundos
    setTimeout(() => {
        if (notification.parentNode) {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }
    }, 5000);
}

/**
 * Función para actualizar estadísticas dinámicamente
 */
function updateStats() {
    const rows = document.querySelectorAll('tbody tr');
    const totalFacturas = rows.length;
    
    // Actualizar contador si existe el elemento
    const totalElement = document.querySelector('.stat-number');
    if (totalElement && totalFacturas > 0) {
        totalElement.textContent = totalFacturas;
    }
}

/**
 * Función para filtrar tabla (para uso futuro)
 */
function filterTable(searchTerm) {
    const rows = document.querySelectorAll('tbody tr');
    const term = searchTerm.toLowerCase();
    
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        const shouldShow = text.includes(term);
        row.style.display = shouldShow ? '' : 'none';
    });
}

// Agregar estilos de animación
const styleSheet = document.createElement('style');
styleSheet.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(styleSheet);

// Exportar funciones para uso global si es necesario
window.FacturasApp = {
    showNotification,
    updateStats,
    filterTable
};