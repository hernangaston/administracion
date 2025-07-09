// Agente Inteligente de Facturas - JavaScript
// Archivo: agente-facturas.js

// Variables globales
let consultaEnProceso = false;

// Función para mostrar tabs
function mostrarTab(tabName) {
    // Ocultar todos los contenidos
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Desactivar todos los tabs
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Mostrar contenido seleccionado
    document.getElementById(tabName).classList.add('active');
    
    // Activar tab seleccionado
    event.target.classList.add('active');
}

// Función para usar ejemplo
function usarEjemplo(consulta) {
    document.getElementById('consulta-input').value = consulta;
    // Simular submit del formulario
    document.getElementById('consulta-form').dispatchEvent(new Event('submit'));
}

// Función para agregar mensaje al chat
function agregarMensajeChat(tipo, mensaje) {
    const chatContainer = document.getElementById('chat-container');
    const tipoTexto = tipo === 'usuario' ? 'Tú' : 'Agente';
    
    chatContainer.innerHTML += `
        <div class="mensaje ${tipo}">
            <strong>${tipoTexto}:</strong> ${mensaje}
        </div>
    `;
    
    // Hacer scroll hacia abajo
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Función para mostrar loading
function mostrarLoading() {
    const chatContainer = document.getElementById('chat-container');
    chatContainer.innerHTML += `
        <div class="mensaje agente loading" id="loading-msg">
            <strong>Agente:</strong> 
            <span class="loading-text">Analizando tu consulta...</span>
            <span class="loading-dots">
                <span>.</span><span>.</span><span>.</span>
            </span>
        </div>
    `;
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Función para remover loading
function removerLoading() {
    const loadingMsg = document.getElementById('loading-msg');
    if (loadingMsg) {
        loadingMsg.remove();
    }
}

// Función para crear tabla de resultados
function crearTablaResultados(resultados) {
    if (!resultados || resultados.length === 0) {
        return '<p>No se encontraron resultados.</p>';
    }
    
    // Obtener las columnas del primer resultado
    const columnas = Object.keys(resultados[0]);
    
    let tablaHTML = `
        <div class="resultados-tabla">
            <table>
                <thead>
                    <tr>
    `;
    
    // Agregar headers
    columnas.forEach(col => {
        tablaHTML += `<th>${col.charAt(0).toUpperCase() + col.slice(1)}</th>`;
    });
    
    tablaHTML += `
                    </tr>
                </thead>
                <tbody>
    `;
    
    // Agregar filas
    resultados.forEach(fila => {
        tablaHTML += '<tr>';
        columnas.forEach(col => {
            let valor = fila[col];
            // Formatear valores especiales
            if (col.includes('monto') || col.includes('total')) {
                valor = formatearMonto(valor);
            } else if (col.includes('fecha')) {
                valor = formatearFecha(valor);
            }
            tablaHTML += `<td>${valor || '-'}</td>`;
        });
        tablaHTML += '</tr>';
    });
    
    tablaHTML += `
                </tbody>
            </table>
        </div>
    `;
    
    return tablaHTML;
}

// Función para formatear montos
function formatearMonto(monto) {
    if (!monto) return '-';
    return new Intl.NumberFormat('es-AR', {
        style: 'currency',
        currency: 'ARS'
    }).format(monto);
}

// Función para formatear fechas
function formatearFecha(fecha) {
    if (!fecha) return '-';
    try {
        return new Date(fecha).toLocaleDateString('es-AR');
    } catch (e) {
        return fecha;
    }
}

// Función para cambiar estado del botón
function cambiarEstadoBoton(boton, procesando = false) {
    if (procesando) {
        boton.disabled = true;
        boton.textContent = 'Procesando...';
        boton.classList.add('procesando');
    } else {
        boton.disabled = false;
        boton.textContent = 'Consultar';
        boton.classList.remove('procesando');
    }
}

// Función principal para manejar consultas
async function manejarConsulta(consulta) {
    const consultaBtn = document.getElementById('consulta-btn');
    
    try {
        // Mostrar mensaje del usuario
        agregarMensajeChat('usuario', consulta);
        
        // Mostrar loading
        mostrarLoading();
        
        // Cambiar estado del botón
        cambiarEstadoBoton(consultaBtn, true);
        
        // Preparar datos para enviar
        const formData = new FormData();
        formData.append('consulta', consulta);
        
        // Enviar consulta al servidor
        const response = await fetch('/agente/consulta', {
            method: 'POST',
            body: formData
        });
        
        const resultado = await response.json();
        
        // Remover loading
        removerLoading();
        
        if (resultado.exito) {
            // Construir respuesta
            let respuestaHTML = resultado.respuesta;
            
            // Mostrar SQL generado (para depuración)
            if (resultado.sql_generado) {
                respuestaHTML += `
                    <div class="sql-debug">
                        <small><strong>SQL generado:</strong> ${resultado.sql_generado}</small>
                    </div>
                `;
            }
            
            // Agregar tabla de resultados
            if (resultado.resultados && resultado.resultados.length > 0) {
                respuestaHTML += crearTablaResultados(resultado.resultados);
                
                // Agregar resumen
                respuestaHTML += `
                    <div class="resumen-resultados">
                        <small>Se encontraron ${resultado.resultados.length} resultado(s)</small>
                    </div>
                `;
            }
            
            // Mostrar respuesta del agente
            agregarMensajeChat('agente', respuestaHTML);
            
        } else {
            // Mostrar error
            agregarMensajeChat('agente', 
                `❌ Error: ${resultado.mensaje || 'No se pudo procesar la consulta'}`);
        }
        
    } catch (error) {
        console.error('Error en consulta:', error);
        removerLoading();
        agregarMensajeChat('agente', 
            '❌ Error de conexión. Por favor, intenta nuevamente.');
    } finally {
        // Restaurar estado del botón
        cambiarEstadoBoton(consultaBtn, false);
        consultaEnProceso = false;
    }
}

// Función para detectar duplicados
async function detectarDuplicados() {
    const resultadoDiv = document.getElementById('duplicados-resultado');
    
    try {
        // Mostrar loading
        resultadoDiv.innerHTML = `
            <div class="loading-container">
                <p>🔍 Buscando facturas duplicadas...</p>
            </div>
        `;
        
        // Enviar petición al servidor
        const response = await fetch('/agente/duplicados', {
            method: 'GET'
        });
        
        const resultado = await response.json();
        
        if (resultado.exito) {
            if (resultado.duplicados && resultado.duplicados.length > 0) {
                let duplicadosHTML = `
                    <div class="duplicados-encontrados">
                        <h3>⚠️ Facturas duplicadas encontradas:</h3>
                `;
                
                resultado.duplicados.forEach((grupo, index) => {
                    duplicadosHTML += `
                        <div class="grupo-duplicado">
                            <h4>Grupo ${index + 1}:</h4>
                            ${crearTablaResultados(grupo)}
                        </div>
                    `;
                });
                
                duplicadosHTML += `
                    </div>
                    <div class="resumen-duplicados">
                        <p><strong>Total de grupos duplicados:</strong> ${resultado.duplicados.length}</p>
                    </div>
                `;
                
                resultadoDiv.innerHTML = duplicadosHTML;
            } else {
                resultadoDiv.innerHTML = `
                    <div class="no-duplicados">
                        <p>✅ No se encontraron facturas duplicadas</p>
                    </div>
                `;
            }
        } else {
            resultadoDiv.innerHTML = `
                <div class="error-duplicados">
                    <p>❌ Error: ${resultado.mensaje}</p>
                </div>
            `;
        }
        
    } catch (error) {
        console.error('Error detectando duplicados:', error);
        resultadoDiv.innerHTML = `
            <div class="error-duplicados">
                <p>❌ Error de conexión al buscar duplicados</p>
            </div>
        `;
    }
}

// Función para cargar estadísticas
async function cargarEstadisticas() {
    const resultadoDiv = document.getElementById('estadisticas-resultado');
    
    try {
        // Mostrar loading
        resultadoDiv.innerHTML = `
            <div class="loading-container">
                <p>📊 Calculando estadísticas...</p>
            </div>
        `;
        
        // Enviar petición al servidor
        const response = await fetch('/agente/estadisticas', {
            method: 'GET'
        });
        
        const resultado = await response.json();
        
        if (resultado.exito) {
            const stats = resultado.estadisticas;
            
            let estadisticasHTML = `
                <div class="estadisticas-grid">
                    <div class="stat-card">
                        <h3>📄 Total de Facturas</h3>
                        <p class="stat-numero">${stats.total_facturas || 0}</p>
                    </div>
                    
                    <div class="stat-card">
                        <h3>💰 Monto Total</h3>
                        <p class="stat-numero">${formatearMonto(stats.monto_total || 0)}</p>
                    </div>
                    
                    <div class="stat-card">
                        <h3>🏢 Proveedores Únicos</h3>
                        <p class="stat-numero">${stats.proveedores_unicos || 0}</p>
                    </div>
                    
                    <div class="stat-card">
                        <h3>📅 Período</h3>
                        <p class="stat-texto">${stats.periodo || 'N/A'}</p>
                    </div>
                </div>
            `;
            
            // Agregar top proveedores si existen
            if (stats.top_proveedores && stats.top_proveedores.length > 0) {
                estadisticasHTML += `
                    <div class="top-proveedores">
                        <h3>🔝 Top Proveedores</h3>
                        ${crearTablaResultados(stats.top_proveedores)}
                    </div>
                `;
            }
            
            // Agregar facturas por mes si existen
            if (stats.facturas_por_mes && stats.facturas_por_mes.length > 0) {
                estadisticasHTML += `
                    <div class="facturas-mes">
                        <h3>📊 Facturas por Mes</h3>
                        ${crearTablaResultados(stats.facturas_por_mes)}
                    </div>
                `;
            }
            
            resultadoDiv.innerHTML = estadisticasHTML;
            
        } else {
            resultadoDiv.innerHTML = `
                <div class="error-estadisticas">
                    <p>❌ Error: ${resultado.mensaje}</p>
                </div>
            `;
        }
        
    } catch (error) {
        console.error('Error cargando estadísticas:', error);
        resultadoDiv.innerHTML = `
            <div class="error-estadisticas">
                <p>❌ Error de conexión al cargar estadísticas</p>
            </div>
        `;
    }
}

// Función para limpiar chat
function limpiarChat() {
    const chatContainer = document.getElementById('chat-container');
    chatContainer.innerHTML = `
        <div class="mensaje agente">
            <strong>Agente:</strong> ¡Hola! Soy tu asistente inteligente para consultas sobre facturas. 
            Puedes preguntarme cosas como "busca facturas de enero" o "muéstrame facturas mayores a $100,000".
        </div>
    `;
}

// Event listeners cuando se carga el DOM
document.addEventListener('DOMContentLoaded', function() {
    // Manejar formulario de consulta
    const consultaForm = document.getElementById('consulta-form');
    if (consultaForm) {
        consultaForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            // Prevenir múltiples consultas simultáneas
            if (consultaEnProceso) {
                return;
            }
            
            const consulta = document.getElementById('consulta-input').value.trim();
            if (!consulta) {
                return;
            }
            
            consultaEnProceso = true;
            
            // Ejecutar consulta
            await manejarConsulta(consulta);
            
            // Limpiar input
            document.getElementById('consulta-input').value = '';
        });
    }
    
    // Manejar Enter en el input
    const consultaInput = document.getElementById('consulta-input');
    if (consultaInput) {
        consultaInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                consultaForm.dispatchEvent(new Event('submit'));
            }
        });
    }
    
    // Agregar botón para limpiar chat
    const chatContainer = document.getElementById('chat-container');
    if (chatContainer) {
        // Crear botón limpiar si no existe
        let limpiarBtn = document.getElementById('limpiar-chat-btn');
        if (!limpiarBtn) {
            limpiarBtn = document.createElement('button');
            limpiarBtn.id = 'limpiar-chat-btn';
            limpiarBtn.textContent = '🗑️ Limpiar Chat';
            limpiarBtn.className = 'limpiar-btn';
            limpiarBtn.onclick = limpiarChat;
            
            // Insertar antes del formulario
            consultaForm.parentNode.insertBefore(limpiarBtn, consultaForm);
        }
    }
    
    console.log('Agente Inteligente de Facturas inicializado correctamente');
});

// Función de utilidad para mostrar notificaciones
function mostrarNotificacion(mensaje, tipo = 'info') {
    const notificacion = document.createElement('div');
    notificacion.className = `notificacion ${tipo}`;
    notificacion.textContent = mensaje;
    
    document.body.appendChild(notificacion);
    
    // Remover después de 3 segundos
    setTimeout(() => {
        notificacion.remove();
    }, 3000);
}

// Función para exportar resultados (opcional)
function exportarResultados(resultados, nombre = 'facturas') {
    if (!resultados || resultados.length === 0) {
        mostrarNotificacion('No hay resultados para exportar', 'warning');
        return;
    }
    
    // Convertir a CSV
    const headers = Object.keys(resultados[0]);
    const csvContent = [
        headers.join(','),
        ...resultados.map(fila => 
            headers.map(header => `"${fila[header] || ''}"`).join(',')
        )
    ].join('\n');
    
    // Crear y descargar archivo
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${nombre}_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    
    mostrarNotificacion('Resultados exportados correctamente', 'success');
}