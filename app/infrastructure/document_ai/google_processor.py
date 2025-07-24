# app/infrastructure/document_ai/google_processor.py
from typing import Dict, Any
from fastapi import UploadFile
import logging

from google.cloud import documentai_v1 as documentai
from app.domain.services.document_service import DocumentService
from app.shared.exceptions.business import DocumentAIError, InvalidFileError
from app.core.config import settings

logger = logging.getLogger(__name__)


class GoogleDocumentProcessor(DocumentService):
    """Implementación de Google Document AI"""
    
    def __init__(self):
        self._client = None
        self._processor_name = None
        self._setup_client()
    
    def _setup_client(self):
        """Configurar cliente de Document AI"""
        try:
            self._client = documentai.DocumentProcessorServiceClient()
            self._processor_name = self._client.processor_path(
                settings.DOCAI_PROJECT_ID,
                settings.DOCAI_LOCATION,
                settings.DOCAI_PROCESSOR_ID
            )
            logger.info(f"✅ Document AI configurado: {self._processor_name}")
        except Exception as e:
            logger.error(f"❌ Error configurando Document AI: {e}")
            raise DocumentAIError(f"Error configurando Document AI: {str(e)}")
    
    async def validate_file(self, file: UploadFile) -> bool:
        """Validar archivo PDF"""
        
        # Validar nombre
        if not file.filename:
            raise InvalidFileError("", "Nombre de archivo vacío")
        
        # Validar extensión
        if not file.filename.lower().endswith('.pdf'):
            raise InvalidFileError(file.filename, "Solo se permiten archivos PDF")
        
        # Validar tamaño
        await file.seek(0)
        content = await file.read()
        await file.seek(0)  # Reset para posterior lectura
        
        if len(content) == 0:
            raise InvalidFileError(file.filename, "Archivo vacío")
        
        if len(content) > settings.MAX_FILE_SIZE:
            size_mb = len(content) / 1024 / 1024
            raise InvalidFileError(
                file.filename, 
                f"Archivo demasiado grande: {size_mb:.1f}MB (máximo {settings.MAX_FILE_SIZE/1024/1024}MB)"
            )
        
        # Validar firma PDF
        if not content.startswith(b'%PDF'):
            raise InvalidFileError(file.filename, "No es un archivo PDF válido")
        
        return True
    
    async def extract_entities(self, file: UploadFile) -> Dict[str, Any]:
        """Extraer entidades usando Google Document AI"""
        
        try:
            # Leer contenido del archivo
            await file.seek(0)
            file_content = await file.read()
            
            # Configurar request
            selector = documentai.ProcessOptions.IndividualPageSelector(pages=[1])
            options = documentai.ProcessOptions(individual_page_selector=selector)
            
            request = documentai.ProcessRequest(
                name=self._processor_name,
                raw_document=documentai.RawDocument(
                    content=file_content,
                    mime_type="application/pdf"
                ),
                field_mask="text,entities,pages.layout",
                process_options=options
            )
            
            # Ejecutar procesamiento
            logger.info(f"Procesando archivo: {file.filename}")
            result = self._client.process_document(request=request)
            doc = result.document
            
            if not doc:
                raise DocumentAIError("Document AI no devolvió resultados")
            
            # Extraer entidades
            entities_raw = {e.type_: e.mention_text for e in doc.entities}
            
            # Mapear entidades a formato estándar
            entities_mapped = self._map_entities(entities_raw)
            
            logger.info(f"✅ Extraídas {len(entities_mapped)} entidades de {file.filename}")
            logger.debug(f"Entidades: {list(entities_mapped.keys())}")
            
            return entities_mapped
            
        except DocumentAIError:
            raise
        except Exception as e:
            logger.error(f"Error procesando {file.filename}: {e}")
            raise DocumentAIError(f"Error procesando documento: {str(e)}")
    
    def _map_entities(self, entities_raw: Dict[str, str]) -> Dict[str, Any]:
        """Mapear entidades de Document AI a formato estándar"""
        
        # Mapeo flexible de nombres de entidades
        entity_mapping = {
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
        }
        
        entities_mapped = {}
        
        for expected_field, possible_names in entity_mapping.items():
            for possible_name in possible_names:
                if possible_name in entities_raw:
                    value = entities_raw[possible_name]
                    
                    # Limpiar CUIT si es campo de tax_id
                    if 'tax_id' in expected_field or 'cuit' in expected_field.lower():
                        value = self._clean_cuit(value)
                    
                    entities_mapped[expected_field] = value
                    break
        
        # Procesar line items si existen
        line_items = self._process_line_items(entities_raw)
        if line_items:
            entities_mapped.update(line_items)
        
        return entities_mapped
    
    def _clean_cuit(self, cuit_raw: str) -> str:
        """Limpiar CUIT extraído"""
        if not cuit_raw:
            return ""
        
        # Extraer solo dígitos
        cuit_clean = ''.join(filter(str.isdigit, str(cuit_raw)))
        
        if len(cuit_clean) == 11:
            return cuit_clean
        elif len(cuit_clean) > 11:
            logger.warning(f"CUIT con más de 11 dígitos: '{cuit_raw}', tomando primeros 11")
            return cuit_clean[:11]
        else:
            logger.warning(f"CUIT con formato incompleto: '{cuit_raw}' ({len(cuit_clean)} dígitos)")
            return cuit_clean
    
    def _process_line_items(self, entities_raw: Dict[str, str]) -> Dict[str, str]:
        """Procesar line items de la factura"""
        
        line_items_data = {
            k: v for k, v in entities_raw.items() 
            if 'linea_item' in k.lower() or 'line_item' in k.lower()
        }
        
        if not line_items_data:
            return {}
        
        # Reconstruir line items
        descripcion = line_items_data.get('linea_item', line_items_data.get('line_item', ''))
        producto = line_items_data.get('linea_item_producto', line_items_data.get('line_item_product', ''))
        cantidad = line_items_data.get('linea_item_cantidad', line_items_data.get('line_item_quantity', ''))
        precio_unitario = line_items_data.get('linea_item_precio_unitario', line_items_data.get('line_item_unit_price', ''))
        importe = line_items_data.get('linea_item_importe', line_items_data.get('line_item_amount', ''))
        
        item_parts = []
        if producto:
            item_parts.append(f"Producto: {producto}")
        if descripcion and descripcion != producto:
            item_parts.append(f"Descripción: {descripcion}")
        if cantidad:
            item_parts.append(f"Cantidad: {cantidad}")
        if precio_unitario:
            item_parts.append(f"Precio Unitario: {precio_unitario}")
        if importe:
            item_parts.append(f"Importe: {importe}")
        
        if item_parts:
            return {'line_item_1': " | ".join(item_parts)}
        
        return {}