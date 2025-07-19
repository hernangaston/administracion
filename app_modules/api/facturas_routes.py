# -*- coding: utf-8 -*-

import os
import tempfile
import sqlite3
import logging
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from google.cloud import documentai_v1 as documentai
from app_modules.utils.formatters import formatear_moneda
from app_modules.utils.cuit_utils import formatear_cuit
from auth_routes import require_auth_cookie
from auth import can_access_factura
from parser_factura import guardar_factura_en_db

# Configuración de Document AI - Copiado del original
PROJECT_ID = os.getenv("DOCAI_PROJECT_ID")
LOCATION_RAW = os.getenv("DOCAI_LOCATION", "us")
PROCESSOR_ID = os.getenv("DOCAI_PROCESSOR_ID")
LOCATION = LOCATION_RAW.split('#')[0].strip().strip('\'"') if LOCATION_RAW else "us"

# Cliente Document AI - lazy loading
client = None

def get_document_ai_client():
    global client
    if client is None:
        client = documentai.DocumentProcessorServiceClient()
    return client

templates = Jinja2Templates(directory="templates")
facturas_router = APIRouter()
logger = logging.getLogger(__name__)

def get_db():
    db = sqlite3.connect("database.db", check_same_thread=False)
    db.row_factory = sqlite3.Row
    return db


def limpiar_cuit(cuit_raw):
    """Limpia y normaliza un CUIT extraído del PDF"""
    if not cuit_raw:
        return ""
    
    cuit_str = str(cuit_raw).strip()
    cuit_limpio = ''.join(filter(str.isdigit, cuit_str))
    
    if len(cuit_limpio) == 11:
        return cuit_limpio
    elif len(cuit_limpio) > 11:
        logger.warning(f"CUIT con más de 11 dígitos: '{cuit_raw}', tomando primeros 11")
        return cuit_limpio[:11]
    else:
        logger.warning(f"CUIT con formato incompleto: '{cuit_raw}' ({len(cuit_limpio)} dígitos)")
        return cuit_limpio

def mapear_entidades_flexibles(entities_raw):
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
    line_items_data = {k: v for k, v in entities_raw.items() if 'linea_item' in k.lower() or 'line_item' in k.lower()}
    if line_items_data:
        li = reconstruir_line_items(line_items_data)
        if li:
            entities_mapeadas.update(li)
    return entities_mapeadas

def reconstruir_line_items(data):
    descripcion = data.get('linea_item', data.get('line_item', ''))
    producto = data.get('linea_item_producto', data.get('line_item_product', ''))
    cantidad = data.get('linea_item_cantidad', data.get('line_item_quantity', ''))
    precio_unitario = data.get('linea_item_precio_unitario', data.get('line_item_unit_price', ''))
    importe = data.get('linea_item_importe', data.get('line_item_amount', ''))
    item = []
    if producto: item.append(f"Producto: {producto}")
    if descripcion and descripcion != producto: item.append(f"Descripción: {descripcion}")
    if cantidad: item.append(f"Cantidad: {cantidad}")
    if precio_unitario: item.append(f"Precio Unitario: {precio_unitario}")
    if importe: item.append(f"Importe: {importe}")
    return {'line_item_1': " | ".join(item)} if item else {}

def _formatear_moneda(valor) -> str:
    """Helper para formatear moneda"""
    if valor is None:
        return "$0,00"    
    try:
        return formatear_moneda(valor)
    except Exception as e:
        logger.warning(f"Error formateando moneda '{valor}': {e}")
        return str(valor) if valor else "$0,00"

def _formatear_fecha(fecha_str) -> str:
    """Formatea una fecha para mostrar en la interfaz."""
    if not fecha_str or fecha_str in ['', 'None', None]:
        return "Sin fecha"
    
    try:
        from datetime import datetime
        fecha_str = str(fecha_str).strip()
        
        formatos_entrada = [
            '%Y-%m-%d',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M:%S.%f',
            '%d/%m/%Y',
            '%d-%m-%Y',
        ]
        
        fecha_obj = None
        for formato in formatos_entrada:
            try:
                fecha_obj = datetime.strptime(fecha_str, formato)
                break
            except ValueError:
                continue
        
        if fecha_obj:
            return fecha_obj.strftime('%d/%m/%Y')
        else:
            if 'T' in fecha_str:
                fecha_parte = fecha_str.split('T')[0]
                fecha_obj = datetime.strptime(fecha_parte, '%Y-%m-%d')
                return fecha_obj.strftime('%d/%m/%Y')
            elif len(fecha_str) >= 10:
                fecha_parte = fecha_str[:10]
                fecha_obj = datetime.strptime(fecha_parte, '%Y-%m-%d')
                return fecha_obj.strftime('%d/%m/%Y')
                
        return str(fecha_str)
        
    except Exception as e:
        logger.warning(f"Error formateando fecha '{fecha_str}': {e}")
        return "Fecha inválida"

def _formatear_numero_factura(numero) -> str:
    """Formatea el número de factura."""
    if not numero:
        return "Sin número"
    return str(numero).strip()

def _procesar_factura_para_vista(factura_dict):
    """Procesa una factura para mostrar en la vista con formatos correctos."""
    
    # Formatear monedas
    for campo_moneda in ['subtotal', 'iva', 'total']:
        if campo_moneda in factura_dict:
            factura_dict[f'{campo_moneda}_formateado'] = _formatear_moneda(factura_dict.get(campo_moneda))
    
    # Formatear fechas
    try:
        if 'fecha_factura' in factura_dict:
            factura_dict['fecha_factura_formateada'] = _formatear_fecha(factura_dict.get('fecha_factura'))
    except Exception:
        factura_dict['fecha_factura_formateada'] = "Error fecha"
    
    try:
        if 'fecha_vencimiento' in factura_dict:
            factura_dict['fecha_vencimiento_formateada'] = _formatear_fecha(factura_dict.get('fecha_vencimiento'))
    except Exception:
        factura_dict['fecha_vencimiento_formateada'] = "Error fecha"
    
    try:
        if 'created_at' in factura_dict:
            factura_dict['created_at_formateado'] = _formatear_fecha(factura_dict.get('created_at'))
    except Exception:
        factura_dict['created_at_formateado'] = "Error fecha"
    
    # Formatear número de factura
    if 'numero_factura' in factura_dict:
        factura_dict['numero_factura_formateado'] = _formatear_numero_factura(factura_dict.get('numero_factura'))
    
    # Formatear CUIT
    if 'cuit_proveedor' in factura_dict:
        factura_dict['cuit_proveedor_formateado'] = formatear_cuit(factura_dict.get('cuit_proveedor'))
    
    return factura_dict

def process_pdf(file_path: str) -> Dict:
    """Procesamiento de PDF - COPIADO DEL ORIGINAL"""
    logger.info(f"Iniciando procesamiento de PDF: {file_path}")
    
    try:
        # Validación básica del archivo (sin Fase 2)
        logger.info("Validador de archivos no disponible, continuando...")

        # Procesamiento con Document AI
        with open(file_path, "rb") as f:
            file_content = f.read()
            
            selector = documentai.ProcessOptions.IndividualPageSelector(pages=[1])
            options = documentai.ProcessOptions(individual_page_selector=selector)
            
            request = documentai.ProcessRequest(
                name=get_document_ai_client().processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID),
                raw_document=documentai.RawDocument(
                    content=file_content, 
                    mime_type="application/pdf"
                ),
                field_mask="text,entities,pages.layout",
                process_options=options
            )
            
            result = get_document_ai_client().process_document(request=request)
            doc = result.document
            
            if not doc:
                raise Exception("Document AI no devolvió resultados")
            
            logger.info(f"Document AI procesó {len(doc.pages)} páginas exitosamente")

        # Extracción de entidades
        entities_raw = {e.type_: e.mention_text for e in doc.entities}
        entities_mapped = mapear_entidades_flexibles(entities_raw)
        
        # Validaciones básicas
        warnings = []
        
        if entities_mapped.get('supplier_tax_id'):
            cuit = entities_mapped['supplier_tax_id']
            cuit_limpio = ''.join(filter(str.isdigit, cuit))
            if len(cuit_limpio) != 11:
                warnings.append(f"CUIT '{cuit}' no tiene 11 dígitos")
        
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
            "processing_error": str(e)
        }

# === RUTAS - COPIADAS DEL ORIGINAL ===

@facturas_router.get("/", response_class=HTMLResponse)
async def home(
    request: Request, 
    db: sqlite3.Connection = Depends(get_db),
    current_user_data = Depends(require_auth_cookie)
):
    """Página principal con listado de facturas (requiere autenticación)"""
    try:
        current_user, token_data = current_user_data
        cursor = db.cursor()
        
        # Consultas según rol - COPIADO DEL ORIGINAL
        if current_user.role in ["admin", "contador", "vendedor", "auditor"]:
            cursor.execute("""
                SELECT id, filename, razon_social, cuit_proveedor, numero_factura,
                       fecha_factura, fecha_vencimiento, tipo_factura,
                       subtotal, iva, total, created_at 
                FROM facturas ORDER BY created_at DESC
            """)
        elif current_user.role == "cliente":
            if current_user.cuit_asociado:
                cursor.execute("""
                    SELECT id, filename, razon_social, cuit_proveedor, numero_factura,
                           fecha_factura, fecha_vencimiento, tipo_factura,
                           subtotal, iva, total, created_at 
                    FROM facturas 
                    WHERE cuit_proveedor = ? OR razon_social LIKE ?
                    ORDER BY created_at DESC
                """, (current_user.cuit_asociado, f"%{current_user.cuit_asociado}%"))
            else:
                cursor.execute("SELECT * FROM facturas WHERE 1=0")
        else:
            cursor.execute("SELECT * FROM facturas WHERE 1=0")

        facturas_raw = cursor.fetchall()

        facturas = []
        for factura in facturas_raw:
            factura_dict = dict(factura)
            factura_dict = _procesar_factura_para_vista(factura_dict)
            facturas.append(factura_dict)

        return templates.TemplateResponse("index.html", {
            "request": request, 
            "facturas": facturas,
            "current_user": current_user,
            "permissions": token_data.permissions
        })

    except Exception as e:
        logger.error(f"Error en ruta home: {e}")
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "facturas": [], 
            "error": str(e),
            "current_user": current_user if 'current_user' in locals() else None
        })
    finally:
        db.close()

@facturas_router.get("/factura/{factura_id}", response_class=HTMLResponse)
async def ver_factura(
    request: Request, 
    factura_id: int, 
    db: sqlite3.Connection = Depends(get_db),
    current_user_data = Depends(require_auth_cookie)
):
    """Ver detalle de una factura específica (con control de acceso)"""
    try:
        current_user, token_data = current_user_data
        cursor = db.cursor()
        cursor.execute("SELECT * FROM facturas WHERE id = ?", (factura_id,))
        factura = cursor.fetchone()

        if not factura:
            logger.warning(f"Factura con ID {factura_id} no encontrada")
            return templates.TemplateResponse("detalle.html", {
                "request": request, 
                "factura": None,
                "current_user": current_user
            })

        factura_dict = dict(factura)
        
        # Verificar permisos de acceso
        if not can_access_factura(current_user, token_data, factura_dict.get('cuit_proveedor')):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para ver esta factura"
            )

        factura_dict['cuit_proveedor_formateado'] = formatear_cuit(factura_dict.get('cuit_proveedor'))
        for key in ['subtotal', 'iva', 'total']:
            factura_dict[f'{key}_formateado'] = _formatear_moneda(factura_dict.get(key))

        return templates.TemplateResponse("detalle.html", {
            "request": request, 
            "factura": factura_dict,
            "current_user": current_user
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo factura {factura_id}: {e}")
        return templates.TemplateResponse("detalle.html", {
            "request": request, 
            "factura": None, 
            "error": str(e),
            "current_user": current_user if 'current_user' in locals() else None
        })
    finally:
        db.close()

@facturas_router.post("/extract-text")
async def extract_text_from_pdfs_secure(
    files: List[UploadFile] = File(...), 
    db: sqlite3.Connection = Depends(get_db),
    current_user_data = Depends(require_auth_cookie)
):
    """Procesamiento seguro de PDFs - SIMPLIFICADO"""
    current_user, token_data = current_user_data
    
    # Verificar permisos
    if "facturas:create" not in token_data.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para crear facturas"
        )
    
    # Límites de seguridad básicos
    MAX_FILES = 10
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Máximo {MAX_FILES} archivos por vez"
        )
    
    resultados = []
    archivos_procesados = 0
    
    for file in files:
        temp_path = None
        try:
            # Validación básica de archivo
            if not (file.content_type == 'application/pdf' or file.filename.lower().endswith('.pdf')):
                resultados.append({
                    "filename": file.filename,
                    "error": "Solo se permiten archivos PDF"
                })
                continue
            
            # Guardar temporalmente
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", prefix="factura_") as temp_file:
                content = await file.read()
                
                # Límite de tamaño básico
                if len(content) > 50 * 1024 * 1024:  # 50MB
                    raise ValueError(f"Archivo demasiado grande: {len(content)} bytes")
                
                temp_file.write(content)
                temp_path = temp_file.name
            
            # Procesamiento
            extracted_data = process_pdf(temp_path)
            
            # Guardar en BD si hay entidades
            entities = extracted_data.get("entities", {})
            if entities:
                try:
                    guardar_factura_en_db(db, file.filename, entities)
                    
                    resultados.append({
                        "filename": file.filename,
                        "message": f"Factura procesada exitosamente (página 1 de {extracted_data.get('pages_processed', 'N/A')}).",
                        "summary_text": (extracted_data.get("text", "")[:200] + "...") if extracted_data.get("text") else "No se pudo extraer texto.",
                        "extracted_entities": entities,
                        "pages_processed": extracted_data.get("pages_processed", 0),
                        "processed_by": current_user.username
                    })
                    archivos_procesados += 1
                    
                except Exception as db_error:
                    logger.error(f"Error guardando en BD para {file.filename}: {db_error}")
                    resultados.append({
                        "filename": file.filename,
                        "error": f"Error guardando en base de datos: {str(db_error)}"
                    })
            else:
                resultados.append({
                    "filename": file.filename,
                    "message": "Archivo procesado pero no se extrajeron datos válidos",
                    "summary_text": extracted_data.get("text", "")[:200] if extracted_data.get("text") else "Sin texto"
                })
                
        except Exception as e:
            logger.error(f"Error procesando {file.filename}: {e}")
            resultados.append({
                "filename": file.filename,
                "error": str(e)
            })
            
        finally:
            # Limpiar archivo temporal
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    # Confirmar cambios
    try:
        db.commit()
        logger.info(f"Usuario {current_user.username} procesó {archivos_procesados}/{len(files)} archivos exitosamente")
        
        return JSONResponse(content={
            "resultados": resultados,
            "total_archivos": len(files),
            "archivos_exitosos": archivos_procesados
        })
        
    except Exception as e:
        logger.error(f"Error en commit final: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error guardando cambios en base de datos"
        )
    finally:
        db.close()