import sqlite3
from typing import Generator
import logging

logger = logging.getLogger(__name__)

def get_database_connection() -> sqlite3.Connection:
    """Crea una nueva conexión a la base de datos"""
    conn = sqlite3.connect("database.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Dependencia de FastAPI para obtener conexión a DB"""
    db = get_database_connection()
    try:
        yield db
    finally:
        db.close()

def init_database():
    """Inicializa todas las tablas de la base de datos"""
    conn = get_database_connection()
    cursor = conn.cursor()
    
    try:
        # Tabla de facturas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS facturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                razon_social TEXT,
                cuit_proveedor TEXT,
                subtotal REAL,
                iva REAL,
                total REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Tabla de texto extraído
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pdf_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                extracted_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP 
            );
        """)
        
        # Tabla de usuarios
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'cliente',
                is_active BOOLEAN DEFAULT TRUE,
                cuit_asociado TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Tabla de refresh tokens
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES usuarios (id) ON DELETE CASCADE
            );
        """)
        
        conn.commit()
        logger.info("Base de datos inicializada correctamente")
        
    except Exception as e:
        logger.error(f"Error inicializando base de datos: {e}")
        conn.rollback()
    finally:
        conn.close()