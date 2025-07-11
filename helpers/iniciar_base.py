import sqlite3

from fastapi import logger


def init_db_tables():
    """Inicializa las tablas de la base de datos"""
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        # Tabla para facturas con datos estructurados
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS facturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                razon_social TEXT,
                cuit_proveedor TEXT, -- Mantener como TEXT por los guiones
                numero_factura TEXT,
                fecha_factura DATE, -- Agregar fecha de factura
                fecha_vencimiento DATE, -- Agregar fecha de vencimiento
                tipo_factura TEXT,
                subtotal DECIMAL(15,2), -- Cambiar a DECIMAL para precisión monetaria
                iva DECIMAL(15,2),
                total DECIMAL(15,2),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP -- Cambiar a DATETIME
            );
        """)

        # Tabla para el texto completo extraído del PDF
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pdf_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                extracted_text TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP -- Cambiar a DATETIME
            );
        """)
        
        # Agregar columnas nuevas si no existen (para migración)
        try:
            cursor.execute("ALTER TABLE facturas ADD COLUMN numero_factura TEXT")
        except sqlite3.OperationalError:
            pass  # Columna ya existe
            
        try:
            cursor.execute("ALTER TABLE facturas ADD COLUMN fecha_factura DATE")
        except sqlite3.OperationalError:
            pass
            
        try:
            cursor.execute("ALTER TABLE facturas ADD COLUMN fecha_vencimiento DATE")
        except sqlite3.OperationalError:
            pass
            
        try:
            cursor.execute("ALTER TABLE facturas ADD COLUMN tipo_factura TEXT")
        except sqlite3.OperationalError:
            pass

        conn.commit()
        conn.close()

    except sqlite3.Error as e:
        logger.error(f"Error inicializando base de datos: {e}")