# Proyecto de Administración de Facturas

Este proyecto es una aplicación web desarrollada con FastAPI para la gestión de facturas argentinas. Permite subir archivos PDF de facturas, extraer información relevante utilizando Google Document AI, y almacenar los datos en una base de datos SQLite para su posterior consulta.

## Características principales

*   **Extracción de datos:** Utiliza Google Document AI (Invoice Parser) para extraer datos clave de facturas en formato PDF, como:
    *   Razón social y CUIT del proveedor
    *   Subtotal, IVA y total
    *   Otros campos relevantes (fecha, número de factura, etc.)
*   **Almacenamiento:** Guarda los datos extraídos en una base de datos SQLite para su gestión.
*   **Interfaz web:** Proporciona una interfaz web para:
    *   Subir facturas en formato PDF
    *   Listar las facturas procesadas
    *   Visualizar los detalles de cada factura
*   **Validación:** Incluye validación del CUIT del proveedor, incluyendo el dígito verificador.

## Requisitos

*   Python 3.9+
*   pip (gestor de paquetes de Python)
*   Google Cloud SDK (si deseas ejecutarlo localmente)

## Configuración

1.  **Clonar el repositorio:**
    ```bash
    git clone <URL_DEL_REPOSITORIO>
    cd administracion
    ```
2.  **Crear un entorno virtual:**
    ```bash
    python3 -m venv admin
    source admin/bin/activate  # o admin\Scripts\activate en Windows
    ```
3.  **Instalar dependencias:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configurar variables de entorno:**
    *   Copia el archivo `.env.example` a `.env` y completa los valores con tu configuración de Google Cloud y Document AI.

## Uso