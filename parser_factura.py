import sqlite3
from typing import Dict, Optional
import logging
from datetime import datetime
import re
from decimal import Decimal, InvalidOperation
from cuit_utils import validar_cuit_completo

# Configurar logging
logger = logging.getLogger(__name__)

def _convertir_a_decimal(valor: Optional[str]) -> Optional[Decimal]:
    """Convierte un string de número argentino a Decimal para mayor precisión monetaria."""
    if valor is None or valor == "":
        return None
    try:
        # Limpiar el valor: remover espacios, símbolos de moneda
        valor_limpio = str(valor).strip()
        # Remover símbolos de moneda comunes
        valor_limpio = re.sub(r'[\$\s]', '', valor_limpio)
        
        # Formato argentino: 1.234.567,89 -> 1234567.89
        if ',' in valor_limpio and '.' in valor_limpio:
            # Tiene tanto puntos como comas
            valor_limpio = valor_limpio.replace('.', '').replace(',', '.')
        elif ',' in valor_limpio and valor_limpio.count(',') == 1:
            # Solo comas (formato decimal argentino)
            valor_limpio = valor_limpio.replace(',', '.')
        elif '.' in valor_limpio and valor_limpio.count('.') > 1:
            # Múltiples puntos (separadores de miles)
            partes = valor_limpio.split('.')
            valor_limpio = ''.join(partes[:-1]) + '.' + partes[-1]
            
        return Decimal(valor_limpio)
    except (ValueError, TypeError, InvalidOperation):
        logger.warning(f"No se pudo convertir '{valor}' a Decimal.")
        return None

def _convertir_fecha(fecha_str: Optional[str]) -> Optional[str]:
    """Convierte string de fecha a formato ISO (YYYY-MM-DD) para SQLite."""
    if not fecha_str or fecha_str.strip() == "":
        return None
    
    fecha_str = fecha_str.strip()
    
    # Patrones de fecha comunes en facturas argentinas
    patrones = [
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',  # DD/MM/YYYY o DD-MM-YYYY
        r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',  # YYYY/MM/DD o YYYY-MM-DD
        r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})',  # DD de MES de YYYY
    ]
    
    meses = {
        'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
        'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
        'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
    }
    
    for patron in patrones:
        match = re.search(patron, fecha_str, re.IGNORECASE)
        if match:
            if patron == patrones[0]:  # DD/MM/YYYY
                dia, mes, año = match.groups()
                try:
                    fecha = datetime(int(año), int(mes), int(dia))
                    return fecha.strftime('%Y-%m-%d')
                except ValueError:
                    continue
                    
            elif patron == patrones[1]:  # YYYY/MM/DD
                año, mes, dia = match.groups()
                try:
                    fecha = datetime(int(año), int(mes), int(dia))
                    return fecha.strftime('%Y-%m-%d')
                except ValueError:
                    continue
                    
            elif patron == patrones[2]:  # DD de MES de YYYY
                dia, mes_nombre, año = match.groups()
                mes_num = meses.get(mes_nombre.lower())
                if mes_num:
                    try:
                        fecha = datetime(int(año), int(mes_num), int(dia))
                        return fecha.strftime('%Y-%m-%d')
                    except ValueError:
                        continue
    
    logger.warning(f"No se pudo convertir la fecha: '{fecha_str}'")
    return None

def guardar_factura_en_db(db: sqlite3.Connection, filename: str, entities: Dict[str, str]) -> bool:
    """
    Guarda los datos estructurados de una factura en la base de datos SQLite
    utilizando las entidades extraídas por el Invoice Parser.
    """
    logger.info(f"=== INICIANDO GUARDADO DE FACTURA: {filename} ===")
    logger.info(f"Entidades recibidas: {entities}")
    
    if not entities:
        logger.warning(f"No se recibieron entidades para {filename}")
        return False
    
    cursor = db.cursor()

    try:
        # Extraer datos básicos
        razon_social: Optional[str] = entities.get("supplier_name")
        cuit_proveedor: Optional[str] = entities.get("supplier_tax_id")
        numero_factura: Optional[str] = entities.get("invoice_id")
        tipo_factura: Optional[str] = entities.get("invoice_type")

        # Convertir fechas
        fecha_factura: Optional[str] = _convertir_fecha(entities.get("invoice_date"))
        fecha_vencimiento: Optional[str] = _convertir_fecha(entities.get("due_date"))

        # Convertir importes a Decimal para mayor precisión
        subtotal: Optional[Decimal] = _convertir_a_decimal(entities.get("net_amount"))
        iva: Optional[Decimal] = _convertir_a_decimal(entities.get("total_tax_amount"))
        total: Optional[Decimal] = _convertir_a_decimal(entities.get("total_amount"))

        # Validar CUIT
        if cuit_proveedor and not validar_cuit_completo(cuit_proveedor):
            logger.warning(f"CUIT '{cuit_proveedor}' para '{filename}' no es válido según el dígito verificador.")

        # Log de cada campo mapeado
        logger.info(f"Mapeo de campos:")
        logger.info(f"  - supplier_name -> razon_social: {razon_social}")
        logger.info(f"  - supplier_tax_id -> cuit_proveedor: {cuit_proveedor}")
        logger.info(f"  - invoice_id -> numero_factura: {numero_factura}")
        logger.info(f"  - invoice_date -> fecha_factura: {fecha_factura}")
        logger.info(f"  - due_date -> fecha_vencimiento: {fecha_vencimiento}")
        logger.info(f"  - invoice_type -> tipo_factura: {tipo_factura}")
        logger.info(f"  - net_amount -> subtotal (Decimal): {subtotal}")
        logger.info(f"  - total_tax_amount -> iva (Decimal): {iva}")
        logger.info(f"  - total_amount -> total (Decimal): {total}")

        # Ejecutar la inserción con los nuevos campos
        cursor.execute("""
            INSERT INTO facturas (
                filename, razon_social, cuit_proveedor, numero_factura,
                fecha_factura, fecha_vencimiento, tipo_factura,
                subtotal, iva, total
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            filename, razon_social, cuit_proveedor, numero_factura,
            fecha_factura, fecha_vencimiento, tipo_factura,
            float(subtotal) if subtotal else None,
            float(iva) if iva else None,
            float(total) if total else None
        ))

        # Verificar que se insertó correctamente
        cursor.execute(
            "SELECT id, razon_social, total, fecha_factura FROM facturas WHERE filename = ? ORDER BY id DESC LIMIT 1", 
            (filename,)
        )
        factura_guardada = cursor.fetchone()

        if factura_guardada:
            logger.info(f"✅ ÉXITO: Factura '{filename}' guardada correctamente")
            logger.info(f"   ID: {factura_guardada[0]}")
            logger.info(f"   Razón Social: '{factura_guardada[1]}'")
            logger.info(f"   Total: '{factura_guardada[2]}'")
            logger.info(f"   Fecha Factura: '{factura_guardada[3]}'")
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