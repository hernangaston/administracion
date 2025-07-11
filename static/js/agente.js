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
    document.getElementById('consulta-form').dispatchEvent(new Event('submit'));
}

// Manejar formulario de consulta
document.addEventListener('DOMContentLoaded', function () {
    const consultaForm = document.getElementById('consulta-form');
    if (consultaForm) {
        consultaForm.addEventListener('submit', async function (e) {
            e.preventDefault();

            const consulta = document.getElementById('consulta-input').value.trim();
            if (!consulta) return;

            const chatContainer = document.getElementById('chat-container');
            const consultaBtn = document.getElementById('consulta-btn');

            // Mostrar mensaje del usuario
            chatContainer.innerHTML += `
                <div class="mensaje usuario">
                    <strong>Tú:</strong> ${consulta}
                </div>
            `;

            // Mostrar loading
            const loadingId = 'loading-msg-' + Date.now();
            chatContainer.innerHTML += `
                <div class="mensaje agente loading" id="${loadingId}">
                    <strong>Agente:</strong> Analizando tu consulta...
                </div>
            `;

            // Desactivar botón
            consultaBtn.disabled = true;
            consultaBtn.textContent = 'Procesando...';

            try {
                // Enviar consulta
                const formData = new FormData();
                formData.append('consulta', consulta);

                const response = await fetch('/agente/consulta', {
                    method: 'POST',
                    body: formData
                });

                const resultado = await response.json();

                // Remover loading
                const loadingElement = document.getElementById(loadingId);
                if (loadingElement) {
                    loadingElement.remove();
                }

                if (resultado.exito) {
                    // Mostrar respuesta
                    let respuestaHTML = `
                        <div class="mensaje agente">
                            <strong>Agente:</strong> ${resultado.respuesta}
                    `;

                    // Mostrar SQL generado (para depuración)
                    if (resultado.sql_generado) {
                        respuestaHTML += `
                            <div class="sql-debug">
                                <small>SQL generado: ${resultado.sql_generado}</small>
                            </div>
                        `;
                    }

                    // Mostrar tabla de resultados si hay datos
                    if (resultado.resultados && resultado.resultados.length > 0) {
                        respuestaHTML += `
                            <div class="resultados-tabla">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Archivo</th>
                                            <th>Proveedor</th>
                                            <th>CUIT</th>
                                            <th>Total</th>
                                            <th>Fecha</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                        `;

                        resultado.resultados.forEach(factura => {
                            respuestaHTML += `
                                <tr>
                                    <td>${factura.filename || 'N/A'}</td>
                                    <td>${factura.razon_social || 'N/A'}</td>
                                    <td>${factura.cuit_formateado || factura.cuit_proveedor || 'N/A'}</td>
                                    <td>${factura.total_formateado || (factura.total ? '$' + factura.total : 'N/A')}</td>
                                    <td>${factura.fecha_formateada || (factura.created_at ? factura.created_at.substring(0, 10) : 'N/A')}</td>
                                </tr>
                            `;
                        });

                        respuestaHTML += `
                                    </tbody>
                                </table>
                            </div>
                        `;
                    }

                    respuestaHTML += '</div>';
                    chatContainer.innerHTML += respuestaHTML;

                } else {
                    // Mostrar error
                    chatContainer.innerHTML += `
                        <div class="mensaje agente error">
                            <strong>Error:</strong> ${resultado.error || 'No se pudo procesar la consulta'}
                        </div>
                    `;
                }

            } catch (error) {
                // Remover loading si existe
                const loadingElement = document.getElementById(loadingId);
                if (loadingElement) {
                    loadingElement.remove();
                }

                // Mostrar error
                chatContainer.innerHTML += `
                    <div class="mensaje agente error">
                        <strong>Error:</strong> No se pudo conectar con el servidor
                    </div>
                `;
            }

            // Reactivar botón
            consultaBtn.disabled = false;
            consultaBtn.textContent = 'Consultar';

            // Limpiar input
            document.getElementById('consulta-input').value = '';

            // Scroll al final
            chatContainer.scrollTop = chatContainer.scrollHeight;
        });
    }

    // Permitir envío con Enter
    const consultaInput = document.getElementById('consulta-input');
    if (consultaInput) {
        consultaInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                document.getElementById('consulta-form').dispatchEvent(new Event('submit'));
            }
        });
    }
});

// Función para detectar duplicados
async function detectarDuplicados() {
    const resultadoDiv = document.getElementById('duplicados-resultado');

    resultadoDiv.innerHTML = '<div class="loading">Buscando duplicados...</div>';

    try {
        const response = await fetch('/agente/duplicados');
        const resultado = await response.json();

        if (resultado.total_duplicados === 0) {
            resultadoDiv.innerHTML = `
                <div class="mensaje agente">
                    ✅ ¡Excelente! No se encontraron facturas duplicadas en tu sistema.
                </div>
            `;
        } else {
            let html = `
                <div class="mensaje agente">
                    ⚠️ Se encontraron ${resultado.total_duplicados} posibles duplicados:
                </div>
                <div class="resultados-tabla">
                    <table>
                        <thead>
                            <tr>
                                <th>Factura 1</th>
                                <th>Factura 2</th>
                                <th>Proveedor</th>
                                <th>Total</th>
                                <th>Motivo</th>
                            </tr>
                        </thead>
                        <tbody>
            `;

            resultado.duplicados.forEach(dup => {
                html += `
                    <tr>
                        <td>${dup.filename1}</td>
                        <td>${dup.filename2}</td>
                        <td>${dup.razon_social1 || 'N/A'}</td>
                        <td>${dup.total_formateado}</td>
                        <td>${dup.motivo}</td>
                    </tr>
                `;
            });

            html += `
                        </tbody>
                    </table>
                </div>
            `;

            resultadoDiv.innerHTML = html;
        }

    } catch (error) {
        resultadoDiv.innerHTML = `
            <div class="error">
                Error al buscar duplicados: ${error.message}
            </div>
        `;
    }
}

// Función para cargar estadísticas
async function cargarEstadisticas() {
    const resultadoDiv = document.getElementById('estadisticas-resultado');

    resultadoDiv.innerHTML = '<div class="loading">Cargando estadísticas...</div>';

    try {
        const response = await fetch('/agente/estadisticas');
        const stats = await response.json();

        let html = `
            <div class="estadisticas-grid">
                <div class="stat-card">
                    <div class="stat-number">${stats.total_facturas || 0}</div>
                    <div class="stat-label">Total de Facturas</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${stats.suma_total_formateada || '$0'}</div>
                    <div class="stat-label">Suma Total</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${stats.top_proveedores?.length || 0}</div>
                    <div class="stat-label">Proveedores Únicos</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${stats.facturas_por_mes?.length || 0}</div>
                    <div class="stat-label">Meses con Actividad</div>
                </div>
            </div>
        `;

        // Top proveedores
        if (stats.top_proveedores && stats.top_proveedores.length > 0) {
            html += `
                <h3>Top 5 Proveedores</h3>
                <div class="resultados-tabla">
                    <table>
                        <thead>
                            <tr>
                                <th>Proveedor</th>
                                <th>Cantidad</th>
                                <th>Total</th>
                            </tr>
                        </thead>
                        <tbody>
            `;

            stats.top_proveedores.forEach(proveedor => {
                const totalFormateado = proveedor.total_proveedor
                    ? `$${proveedor.total_proveedor.toLocaleString('es-AR', { minimumFractionDigits: 2 })}`
                    : 'N/A';

                html += `
                    <tr>
                        <td>${proveedor.razon_social}</td>
                        <td>${proveedor.cantidad}</td>
                        <td>${totalFormateado}</td>
                    </tr>
                `;
            });

            html += `
                        </tbody>
                    </table>
                </div>
            `;
        }

        // Facturas por mes
        if (stats.facturas_por_mes && stats.facturas_por_mes.length > 0) {
            html += `
                <h3>Actividad por Mes</h3>
                <div class="resultados-tabla">
                    <table>
                        <thead>
                            <tr>
                                <th>Mes</th>
                                <th>Cantidad de Facturas</th>
                            </tr>
                        </thead>
                        <tbody>
            `;

            stats.facturas_por_mes.forEach(mes => {
                html += `
                    <tr>
                        <td>${mes.mes}</td>
                        <td>${mes.cantidad}</td>
                    </tr>
                `;
            });

            html += `
                        </tbody>
                    </table>
                </div>
            `;
        }

        resultadoDiv.innerHTML = html;

    } catch (error) {
        resultadoDiv.innerHTML = `
            <div class="error">
                Error al cargar estadísticas: ${error.message}
            </div>
        `;
    }
}

// Auto-cargar estadísticas cuando se haga clic en esa tab
document.addEventListener('click', function (e) {
    if (e.target.classList.contains('tab') && e.target.textContent.trim() === 'Estadísticas') {
        setTimeout(() => {
            const resultadoDiv = document.getElementById('estadisticas-resultado');
            if (resultadoDiv && resultadoDiv.innerHTML.trim() === '') {
                cargarEstadisticas();
            }
        }, 100);
    }
});