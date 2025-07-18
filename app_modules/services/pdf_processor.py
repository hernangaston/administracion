# -*- coding: utf-8 -*-
"""
Servicio de procesamiento de PDFs con Google Document AI
"""

import os
import logging
from typing import Dict
from google.cloud import documentai_v1 as documentai

from app_modules.utils.cuit_utils import limpiar_cuit

logger = logging.getLogger(__name__)

# Configuración de Document AI
PROJECT_ID = os.getenv("DOCAI_PROJECT_ID")
LOCATION_RAW = os.getenv("DOCAI_LOCATION", "us")
PROCESSOR_ID = os.getenv("DOCAI_PROCESSOR_ID")

# Limpiar la variable de ubicación
LOCATION = LOCATION_RAW.split('#')[0].strip().strip('\'"')

# ❌ NO inicializar aquí
# client = documentai.DocumentProcessorServiceClient()

# ✅ Inicializar cuando se necesite
_client = None

def get_document_ai_client():
    """Obtiene el cliente de Document AI, inicializándolo si es necesario"""
    global _client
    if _client is None:
        _client = documentai.DocumentProcessorServiceClient()
    return _client


def mapear_entidades_flexibles(entities_raw):
    """Mapea entidades extraídas por Document AI a campos estándar"""
    mapeo_entidades = {
        'supplier_name': ['proveedor_nombre', 'supplier_name', 'vendor_name', 'company_name'],
        'supplier_tax_id': ['proveedor_cuit', 'supplier_tax_id', 'tax_id', 'cuit_proveedor'],
        'supplier_address': ['proveedor_direccion', 'supplier_address', 'vendor_address'],
        'supplier_phone': ['proveedor_telefono', 'supplier_phone', 'phone'],
        'supplier_email': ['proveedor_email', 'supplier_email', 'email'],
        'receiver_tax_id': ['cliente_cuit', 'receiver_tax_id', 'customer_tax_id'],
        'receiver_name': ['cliente_nombre', 'receiver_name', 'customer_name'],
        'receiver_address': ['cliente_direccion', 'receiver_address', 'customer_address'],
        'invoice_id': ['factura_numero', 'invoice_id', 'invoice_number', 'numero_factura'],
        'invoice_date': ['factura_fecha', 'invoice_date', 'fecha_factura'],
        'due_date': ['factura_vencimiento', 'due_date', 'vencimiento'],
        'invoice_type': ['factura_tipo', 'invoice_type', 'tipo_factura'],
        'net_amount': ['factura_subtotal', 'net_amount', 'subtotal_amount', 'subtotal'],
        'total_tax_amount': ['factura_importe_iva_uno', 'total_tax_amount', 'tax_amount', 'iva_total'],
        'total_amount': ['factura_importe_total', 'total_amount', 'invoice_total', 'grand_total', 'total'],
        'vat': ['factura_iva_uno', 'vat', 'iva_alicuota'],
        'line_item': ['linea_item', 'line_item', 'item_description'],
        'line_item_product': ['linea_item_producto', 'line_item_product', 'product_description'],
        'line_item_quantity': ['linea_item_cantidad', 'line_item_quantity', 'quantity'],
        'line_item_unit_price': ['linea_item_precio_unitario', 'line_item_unit_price', 'unit_price'],
        'line_item_amount': ['linea_item_importe', 'line_item_amount', 'line_total']
    }
    
    entities_mapeadas = {}
    for campo_esperado, posibles_nombres in mapeo_entidades.items():
        for nombre_posible in posibles_nombres:
            if nombre_posible in entities_raw:
                valor = entities_raw[nombre_posible]
                if 'tax_id' in campo_esperado or 'cuit' in campo_esperado.lower():
                    valor = limpiar_cuit(valor)
                entities_mapeadas[campo_esperado] = valor
                break
    
    return procesar_line_items_inteligente(entities_raw, entities_mapeadas)

def procesar_line_items_inteligente(entities_raw, entities_mapeadas):
    """Procesa los ítems de línea de la factura"""
    line_items_data = {k: v for k, v in entities_raw.items() 
                      if 'linea_item' in k.lower() or 'line_item' in k.lower()}
    
    if line_items_data:
        li = reconstruir_line_items(line_items_data)
        if li:
            entities_mapeadas.update(li)
    
    return entities_mapeadas

def reconstruir_line_items(data):
    """Reconstruye la información de los ítems de línea"""
    descripcion = data.get('linea_item', data.get('line_item', ''))
    producto = data.get('linea_item_producto', data.get('line_item_product', ''))
    cantidad = data.get('linea_item_cantidad', data.get('line_item_quantity', ''))
    precio_unitario = data.get('linea_item_precio_unitario', data.get('line_item_unit_price', ''))
    importe = data.get('linea_item_importe', data.get('line_item_amount', ''))
    
    item = []
    if producto: 
        item.append(f"Producto: {producto}")
    if descripcion and descripcion != producto: 
        item.append(f"Descripción: {descripcion}")
    if cantidad: 
        item.append(f"Cantidad: {cantidad}")
    if precio_unitario: 
        item.append(f"Precio Unitario: {precio_unitario}")
    if importe: 
        item.append(f"Importe: {importe}")
    
    return {'line_item_1': " | ".join(item)} if item else {}

def process_pdf(file_path: str) -> Dict:
    """
    Procesa un archivo PDF usando Google Document AI
    
    Args:
        file_path (str): Ruta al archivo PDF a procesar
        
    Returns:
        Dict: Resultado del procesamiento con texto, entidades y metadatos
    """
    logger.info(f"Iniciando procesamiento de PDF: {file_path}")
    
    try:
        # Validación básica del archivo
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")
        
        if not file_path.lower().endswith('.pdf'):
            raise ValueError("Solo se aceptan archivos PDF")
        
        # Leer archivo
        with open(file_path, "rb") as f:
            file_content = f.read()
            
            # Validar tamaño
            if len(file_content) == 0:
                raise ValueError("El archivo PDF está vacío")
            
            if len(file_content) > 50 * 1024 * 1024:  # 50MB
                raise ValueError("El archivo PDF es demasiado grande")
            
            # Configurar procesamiento
            selector = documentai.ProcessOptions.IndividualPageSelector(pages=[1])
            options = documentai.ProcessOptions(
                individual_page_selector=selector
            )
            
            request = documentai.ProcessRequest(
                name=client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID),
                raw_document=documentai.RawDocument(
                    content=file_content, 
                    mime_type="application/pdf"
                ),
                field_mask="text,entities,pages.layout",
                process_options=options
            )
            
            # Ejecutar procesamiento
            result = client.process_document(request=request)
            doc = result.document
            
            if not doc:
                raise Exception("Document AI no devolvió resultados")
            
            logger.info(f"Document AI procesó {len(doc.pages)} páginas exitosamente")

        # Extraer entidades
        entities_raw = {e.type_: e.mention_text for e in doc.entities}
        entities_mapped = mapear_entidades_flexibles(entities_raw)
        
        # Validaciones básicas
        warnings = []
        
        # Validar CUIT si fue extraído
        if entities_mapped.get('supplier_tax_id'):
            cuit = entities_mapped['supplier_tax_id']
            cuit_limpio = ''.join(filter(str.isdigit, cuit))
            if len(cuit_limpio) != 11:
                warnings.append(f"CUIT '{cuit}' no tiene 11 dígitos")
        
        # Validar montos básicos
        for field in ['total_amount', 'net_amount']:
            if entities_mapped.get(field):
                try:
                    float(str(entities_mapped[field]).replace(',', '.').replace('$', ''))
                except ValueError:
                    warnings.append(f"Monto {field} con formato inválido")
        
        return {
            "text": doc.text,
            "entities": entities_mapped,
            "entities_raw": entities_raw,
            "pages_processed": len(doc.pages) if doc.pages else 0,
            "validation_warnings": warnings,
            "processing_success": True
        }
        
    except Exception as e:
        logger.error(f"Error procesando PDF {file_path}: {e}")
        return {
            "text": "",
            "entities": {},
            "entities_raw": {},
            "pages_processed": 0,
            "processing_error": str(e),
            "processing_success": False
        }