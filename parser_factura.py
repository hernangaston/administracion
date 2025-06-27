import sqlite3
from typing import Dict, Optional
import logging
from cuit_utils import validar_cuit_completo

# Configurar logging
logger = logging.getLogger(__name__)

def _convertir_a_float(valor: Optional[str]) -> Optional[float]:
    """Convierte un string de número argentino a float."""
    if valor is None:
        return None
    try:
        # Reemplaza el punto de miles y la coma decimal por un punto decimal
        valor_limpio = valor.replace('.', '').replace(',', '.')
        return float(valor_limpio)
    except (ValueError, TypeError):
        logger.warning(f"No se pudo convertir '{valor}' a float.")
        return None

def guardar_factura_en_db(db: sqlite3.Connection, filename: str, entities: Dict[str, str]) -> bool:
    """
    Guarda los datos estructurados de una factura en la base de datos SQLite
    utilizando las entidades extraídas por el Invoice Parser.

    Args:
        db (sqlite3.Connection): La conexión a la base de datos.
        filename (str): El nombre del archivo de la factura.        
        entities (Dict[str, str]): Un diccionario con las entidades extraídas.
        
    Returns:
        bool: True si se guardó exitosamente, False en caso contrario.
    """
    logger.info(f"=== INICIANDO GUARDADO DE FACTURA: {filename} ===")
    logger.info(f"Entidades recibidas: {entities}")
    
    # Verificar si hay entidades para procesar
    if not entities:
        logger.warning(f"No se recibieron entidades para {filename}")
        return False
    
    # Mostrar todas las claves disponibles para depuración
    logger.info(f"Claves disponibles en entities: {list(entities.keys())}")
    
    cursor = db.cursor()

    try:
        # El mapeo ya se hizo en app.py, aquí solo obtenemos los valores.
        razon_social: Optional[str] = entities.get("supplier_name")
        cuit_proveedor: Optional[str] = entities.get("supplier_tax_id")

        # Convertir importes a números
        subtotal: Optional[float] = _convertir_a_float(entities.get("net_amount"))
        iva: Optional[float] = _convertir_a_float(entities.get("total_tax_amount"))
        total: Optional[float] = _convertir_a_float(entities.get("total_amount"))

        # Validar CUIT
        if cuit_proveedor and not validar_cuit_completo(cuit_proveedor):
            logger.warning(f"CUIT '{cuit_proveedor}' para '{filename}' no es válido según el dígito verificador.")

        # Log de cada campo mapeado
        logger.info(f"Mapeo de campos:")
        logger.info(f"  - supplier_name -> razon_social: {razon_social}")
        logger.info(f"  - supplier_tax_id -> cuit_proveedor: {cuit_proveedor}")
        logger.info(f"  - net_amount -> subtotal (float): {subtotal}")
        logger.info(f"  - total_tax_amount -> iva (float): {iva}")
        logger.info(f"  - total_amount -> total (float): {total}")

        # Ejecutar la inserción
        cursor.execute("""
            INSERT INTO facturas (filename, razon_social, cuit_proveedor, subtotal, iva, total)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (filename, razon_social, cuit_proveedor, subtotal, iva, total))

        # Verificar que se insertó correctamente
        cursor.execute("SELECT id, razon_social, total FROM facturas WHERE filename = ? ORDER BY id DESC LIMIT 1", (filename,))
        factura_guardada = cursor.fetchone()

        if factura_guardada:
            logger.info(f"✅ ÉXITO: Factura '{filename}' guardada correctamente")
            logger.info(f"   ID: {factura_guardada[0]}")
            logger.info(f"   Razón Social: '{factura_guardada[1]}'")
            logger.info(f"   Total: '{factura_guardada[2]}'")
            return True
        else:
            logger.error(f"❌ ERROR: No se pudo verificar el guardado de {filename}")
            return False

    except sqlite3.Error as e:
        logger.error(f"❌ ERROR SQL al guardar datos de '{filename}': {e}")
        return False
    except Exception as e:
        logger.error(f"❌ ERROR GENERAL al guardar datos de '{filename}': {e}")
        return False

def verificar_entidades_disponibles(entities: Dict[str, str]) -> None:
    """
    Función auxiliar para mostrar todas las entidades disponibles
    y ayudar en la depuración.
    """
    logger.info("=== TODAS LAS ENTIDADES DISPONIBLES ===")
    if not entities:
        logger.info("No hay entidades disponibles")
        return
        
    for key, value in entities.items():
        logger.info(f"  {key}: {value}")
    logger.info("=====================================")

def obtener_estadisticas_facturas() -> Dict:
    """
    Función auxiliar para obtener estadísticas de las facturas guardadas.
    """
    conn = sqlite3.connect("database.db", check_same_thread=False)
    cursor = conn.cursor()
    
    try:
        # Total de facturas
        cursor.execute("SELECT COUNT(*) FROM facturas")
        total_facturas = cursor.fetchone()[0]
        
        # Facturas con datos completos
        cursor.execute("""
            SELECT COUNT(*) FROM facturas 
            WHERE razon_social IS NOT NULL 
            AND total IS NOT NULL
        """)
        facturas_completas = cursor.fetchone()[0]
        
        # Facturas recientes
        cursor.execute("""
            SELECT filename, razon_social, total, created_at 
            FROM facturas 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        facturas_recientes = cursor.fetchall()
        
        estadisticas = {
            'total_facturas': total_facturas,
            'facturas_completas': facturas_completas,
            'facturas_incompletas': total_facturas - facturas_completas,
            'facturas_recientes': facturas_recientes
        }
        
        logger.info(f"=== ESTADÍSTICAS DE BASE DE DATOS ===")
        logger.info(f"Total facturas: {estadisticas['total_facturas']}")
        logger.info(f"Facturas completas: {estadisticas['facturas_completas']}")
        logger.info(f"Facturas incompletas: {estadisticas['facturas_incompletas']}")
        logger.info("=====================================")
        
        return estadisticas
        
    except sqlite3.Error as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        return {}
    finally:
        conn.close()