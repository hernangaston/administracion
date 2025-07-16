
let currentChart = null;

function cargarReporte(tipoReporte) {
    // Mostrar container del reporte
    document.getElementById('reporte-container').style.display = 'block';
    
    // Actualizar título
    const titulos = {
        'facturas-mes': 'Facturas por Mes',
        'top-proveedores': 'Top Proveedores (Análisis Inteligente)',
        'distribucion-montos': 'Distribución por Montos',
        'evolucion-temporal': 'Evolución Temporal'
    };
    
    document.getElementById('reporte-titulo').textContent = titulos[tipoReporte] || 'Reporte';
    
    // Cargar datos según el tipo de reporte
    if (tipoReporte === 'facturas-mes') {
        cargarFacturasPorMes();
    } else if (tipoReporte === 'top-proveedores') {
        cargarTopProveedores(); // NUEVA FUNCIÓN
    } else {
        // Otros reportes (placeholder por ahora)
        document.getElementById('reporte-contenido').innerHTML = `
            <div class="alert alert-info">
                <i class="fas fa-info-circle me-2"></i>
                <strong>Reporte "${titulos[tipoReporte]}" en desarrollo</strong>
                <p class="mb-0 mt-2">Este reporte se implementará en los siguientes pasos.</p>
            </div>
        `;
    }
    
    // Scroll al reporte
    document.getElementById('reporte-container').scrollIntoView({ behavior: 'smooth' });
}

async function cargarFacturasPorMes() {
    try {
        // Mostrar loading
        document.getElementById('reporte-contenido').innerHTML = `
            <div class="text-center">
                <i class="fas fa-spinner fa-spin fa-2x"></i>
                <p class="mt-2">Cargando datos...</p>
            </div>
        `;

        // Hacer petición al API
        const response = await fetch('/api/reportes/facturas-mes');
        const resultado = await response.json();

        if (!resultado.success) {
            throw new Error(resultado.error || 'Error cargando datos');
        }

        // Crear el gráfico
        crearGraficoFacturasMes(resultado.data);

    } catch (error) {
        console.error('Error cargando reporte:', error);
        document.getElementById('reporte-contenido').innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                <strong>Error cargando el reporte</strong>
                <p class="mb-0 mt-2">${error.message}</p>
            </div>
        `;
    }
}

function crearGraficoFacturasMes(datos) {
    // Destruir gráfico anterior si existe
    if (currentChart) {
        currentChart.destroy();
    }

    // Preparar datos para Chart.js
    const labels = datos.map(d => d.mes_nombre);
    const cantidades = datos.map(d => d.cantidad);
    const importes = datos.map(d => d.total_importe);

    // Crear contenedor del gráfico
    document.getElementById('reporte-contenido').innerHTML = `
        <div class="row">
            <div class="col-12">
                <div class="mb-3">
                    <p class="text-muted">Últimos ${datos.length} meses con actividad</p>
                </div>
                
                <!-- Gráfico -->
                <div class="chart-container" style="position: relative; height: 400px; margin-bottom: 30px;">
                    <canvas id="grafico-facturas-mes"></canvas>
                </div>
                
                <!-- Tabla resumen -->
                <div class="table-responsive">
                    <table class="table table-striped">
                        <thead>
                            <tr>
                                <th>Mes</th>
                                <th>Cantidad</th>
                                <th>Total Importe</th>
                                <th>Promedio</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${datos.map(d => `
                                <tr>
                                    <td>${d.mes_nombre}</td>
                                    <td>${d.cantidad}</td>
                                    <td>$${d.total_formateado}</td>
                                    <td>$${d.promedio.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;

    // Crear el gráfico
    const ctx = document.getElementById('grafico-facturas-mes').getContext('2d');
    currentChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Cantidad de Facturas',
                data: cantidades,
                backgroundColor: 'rgba(54, 162, 235, 0.8)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1,
                yAxisID: 'y'
            }, {
                label: 'Total Importe ($)',
                data: importes,
                type: 'line',
                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                borderColor: 'rgba(255, 99, 132, 1)',
                borderWidth: 2,
                fill: false,
                yAxisID: 'y1'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Cantidad de Facturas'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Total Importe ($)'
                    },
                    grid: {
                        drawOnChartArea: false,
                    },
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Evolución Mensual de Facturas'
                },
                legend: {
                    display: true,
                    position: 'top'
                }
            }
        }
    });
}

// Función para cargar top proveedores
async function cargarTopProveedores() {
    try {
        console.log('🔍 Cargando top proveedores...');

        // Mostrar loading
        document.getElementById('reporte-contenido').innerHTML = `
            <div class="text-center">
                <i class="fas fa-spinner fa-spin fa-2x"></i>
                <p class="mt-2">Consultando al agente inteligente...</p>
            </div>
        `;

        // Hacer petición al API
        const response = await fetch('/api/reportes/top-proveedores');
        const resultado = await response.json();

        if (!resultado.success) {
            throw new Error(resultado.error || 'Error cargando datos');
        }

        // Crear el gráfico
        crearGraficoTopProveedores(resultado.data, resultado.descripcion);

    } catch (error) {
        console.error('❌ Error cargando top proveedores:', error);
        document.getElementById('reporte-contenido').innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                <strong>Error cargando el reporte</strong>
                <p class="mb-0 mt-2">${error.message}</p>
            </div>
        `;
    }
}

function crearGraficoTopProveedores(datos, descripcion) {
    // Destruir gráfico anterior si existe
    if (currentChart) {
        currentChart.destroy();
    }

    // Preparar datos para Chart.js
    const labels = datos.map(d => d.razon_social);
    const totales = datos.map(d => d.total_proveedor);
    const cantidades = datos.map(d => d.cantidad);

    // Crear contenedor del gráfico
    document.getElementById('reporte-contenido').innerHTML = `
        <div class="row">
            <div class="col-12">
                <div class="mb-3">
                    <p class="text-muted">
                        <i class="fas fa-robot me-2"></i>
                        ${descripcion}
                    </p>
                </div>
                
                <!-- Gráfico -->
                <div class="chart-container" style="position: relative; height: 500px; margin-bottom: 30px;">
                    <canvas id="grafico-top-proveedores"></canvas>
                </div>
                
                <!-- Tabla resumen -->
                <div class="table-responsive">
                    <table class="table table-striped">
                        <thead>
                            <tr>
                                <th>Proveedor</th>
                                <th>Cantidad Facturas</th>
                                <th>Total Facturado</th>
                                <th>Promedio por Factura</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${datos.map(d => `
                                <tr>
                                    <td><strong>${d.razon_social}</strong></td>
                                    <td>${d.cantidad}</td>
                                    <td>$${d.total_formateado}</td>
                                    <td>$${(d.total_proveedor / d.cantidad).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;

    // Crear el gráfico horizontal
    const ctx = document.getElementById('grafico-top-proveedores').getContext('2d');
    currentChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Total Facturado ($)',
                data: totales,
                backgroundColor: [
                    'rgba(255, 99, 132, 0.8)',
                    'rgba(54, 162, 235, 0.8)',
                    'rgba(255, 205, 86, 0.8)',
                    'rgba(75, 192, 192, 0.8)',
                    'rgba(153, 102, 255, 0.8)'
                ],
                borderColor: [
                    'rgba(255, 99, 132, 1)',
                    'rgba(54, 162, 235, 1)',
                    'rgba(255, 205, 86, 1)',
                    'rgba(75, 192, 192, 1)',
                    'rgba(153, 102, 255, 1)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            indexAxis: 'y', // Gráfico horizontal
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Total Facturado ($)'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Proveedores'
                    }
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Top Proveedores por Volumen de Facturación'
                },
                legend: {
                    display: false
                }
            }
        }
    });
}