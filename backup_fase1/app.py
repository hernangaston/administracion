# -*- coding: utf-8 -*-
import datetime
from decimal import Decimal
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from google.cloud import documentai_v1 as documentai
import os
import tempfile
import sqlite3
from typing import List, Dict
import traceback
import logging
from datetime import datetime, timedelta

from app_modules.core.config import settings, setup_google_credentials
from app_modules.core.database import get_db, init_database
from app_modules.utils.formatters import formatear_moneda

# Asegúrate que la importación coincida con la ubicación de tu archivo
from parser_factura import guardar_factura_en_db

from app_modules.utils.cuit_utils import limpiar_cuit, formatear_cuit, validar_cuit

from auth_routes import auth_router, require_auth_cookie, get_current_user_from_cookie
from auth import init_auth_tables, can_access_factura


from helpers.iniciar_base import init_db_tables

from agente_facturas import AgenteFacturas

# Configurar logging con nivel WARNING para reducir ruido
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)



# Configurar credenciales
setup_google_credentials()

app = FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configura Google Document AI
PROJECT_ID = os.getenv("DOCAI_PROJECT_ID")
LOCATION_RAW = os.getenv("DOCAI_LOCATION", "us") # Leer valor crudo
PROCESSOR_ID = os.getenv("DOCAI_PROCESSOR_ID")

# Limpiar la variable de ubicación para evitar errores con comentarios o comillas en el .env
LOCATION = LOCATION_RAW.split('#')[0].strip().strip('\'"')

# Autenticación
google_creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if google_creds_path:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = google_creds_path

# Inicializar cliente de Document AI
client = documentai.DocumentProcessorServiceClient()

def init_db_tables():
    """Usar la nueva función centralizada"""
    init_database()

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

# Helper para formatear moneda
# DESPUÉS:
def _formatear_moneda(valor) -> str:
    """Usar el nuevo formateador"""
    return formatear_moneda(valor)

def _formatear_fecha(fecha_str) -> str:
    """Formatea una fecha para mostrar en la interfaz."""
    if not fecha_str or fecha_str in ['', 'None', None]:
        return "Sin fecha"
    
    try:
        fecha_str = str(fecha_str).strip()
        
        # Intentar diferentes formatos que pueden venir de SQLite
        formatos_entrada = [
            '%Y-%m-%d',           # 2024-01-15
            '%Y-%m-%d %H:%M:%S',  # 2024-01-15 10:30:00
            '%Y-%m-%d %H:%M:%S.%f', # 2024-01-15 10:30:00.123456
            '%d/%m/%Y',           # 15/01/2024
            '%d-%m-%Y',           # 15-01-2024
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
            # Si no pudo parsear, intentar extraer solo la parte de fecha
            # En caso de que venga algo como "2024-01-15T10:30:00"
            if 'T' in fecha_str:
                fecha_parte = fecha_str.split('T')[0]
                fecha_obj = datetime.strptime(fecha_parte, '%Y-%m-%d')
                return fecha_obj.strftime('%d/%m/%Y')
            elif len(fecha_str) >= 10:
                # Tomar los primeros 10 caracteres (YYYY-MM-DD)
                fecha_parte = fecha_str[:10]
                fecha_obj = datetime.strptime(fecha_parte, '%Y-%m-%d')
                return fecha_obj.strftime('%d/%m/%Y')
                
        return str(fecha_str)  # Mostrar como viene si no se puede formatear
        
    except Exception as e:
        # Para debugging - puedes comentar esta línea en producción
        logger.warning(f"Error formateando fecha '{fecha_str}': {e}")
        return "Fecha inválida"
    
def _formatear_numero_factura(numero) -> str:
    """Formatea el número de factura."""
    if not numero:
        return "Sin número"
    return str(numero).strip()

def _procesar_factura_para_vista(factura_dict):
    """Procesa una factura para mostrar en la vista con formatos correctos."""
    
    # Debug: mostrar qué datos llegan
    logger.debug(f"Procesando factura ID {factura_dict.get('id')}")
    logger.debug(f"  fecha_factura raw: '{factura_dict.get('fecha_factura')}' tipo: {type(factura_dict.get('fecha_factura'))}")
    logger.debug(f"  created_at raw: '{factura_dict.get('created_at')}' tipo: {type(factura_dict.get('created_at'))}")
    
    # Formatear monedas
    for campo_moneda in ['subtotal', 'iva', 'total']:
        if campo_moneda in factura_dict:
            factura_dict[f'{campo_moneda}_formateado'] = _formatear_moneda(factura_dict.get(campo_moneda))
    
    # Formatear fechas - con manejo de errores individual
    try:
        if 'fecha_factura' in factura_dict:
            fecha_formateada = _formatear_fecha(factura_dict.get('fecha_factura'))
            factura_dict['fecha_factura_formateada'] = fecha_formateada
            logger.debug(f"  fecha_factura formateada: '{fecha_formateada}'")
    except Exception as e:
        logger.error(f"Error formateando fecha_factura: {e}")
        factura_dict['fecha_factura_formateada'] = "Error fecha"
    
    try:
        if 'fecha_vencimiento' in factura_dict:
            factura_dict['fecha_vencimiento_formateada'] = _formatear_fecha(factura_dict.get('fecha_vencimiento'))
    except Exception as e:
        logger.error(f"Error formateando fecha_vencimiento: {e}")
        factura_dict['fecha_vencimiento_formateada'] = "Error fecha"
    
    try:
        if 'created_at' in factura_dict:
            fecha_creacion = _formatear_fecha(factura_dict.get('created_at'))
            factura_dict['created_at_formateado'] = fecha_creacion
            logger.debug(f"  created_at formateado: '{fecha_creacion}'")
    except Exception as e:
        logger.error(f"Error formateando created_at: {e}")
        factura_dict['created_at_formateado'] = "Error fecha"
    
    # Formatear número de factura
    if 'numero_factura' in factura_dict:
        factura_dict['numero_factura_formateado'] = _formatear_numero_factura(factura_dict.get('numero_factura'))
    
    # Formatear CUIT (ya existe la función)
    if 'cuit_proveedor' in factura_dict:
        factura_dict['cuit_proveedor_formateado'] = formatear_cuit(factura_dict.get('cuit_proveedor'))
    
    return factura_dict

# Dependencia de FastAPI para gestionar la conexión a la BD
def get_db():
    db = sqlite3.connect("database.db", check_same_thread=False)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def startup():
    if not all([PROJECT_ID, LOCATION, PROCESSOR_ID]):
        logger.critical("Faltan variables de entorno críticas para Document AI.")
    
    # Inicializar tablas existentes
    init_db_tables()
    
    # Inicializar tablas de autenticación
    db = sqlite3.connect("database.db")
    init_auth_tables(db)
    db.close()

# === INCLUIR EL ROUTER DE AUTENTICACIÓN ===
app.include_router(auth_router)

def process_pdf(file_path: str) -> Dict:
    try:
        with open(file_path, "rb") as f:
            file_content = f.read()
            selector = documentai.ProcessOptions.IndividualPageSelector(pages=[1])
            options = documentai.ProcessOptions(individual_page_selector=selector)
            request = documentai.ProcessRequest(
                name=client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID), # type: ignore
                raw_document=documentai.RawDocument(content=file_content, mime_type="application/pdf"),
                field_mask="text,entities,pages.layout",
                process_options=options
            )
            result = client.process_document(request=request)
            doc = result.document
            entities_raw = {e.type_: e.mention_text for e in doc.entities}
            return {
                "text": doc.text,
                "entities": mapear_entidades_flexibles(entities_raw),
                "entities_raw": entities_raw,
                "pages_processed": len(doc.pages) if doc.pages else 0
            }
    except Exception as e:
        logger.error(f"Error procesando PDF: {e}")
        return {"text": "", "entities": {}, "entities_raw": {}, "pages_processed": 0}

# En app.py, reemplazar la función home:
@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request, 
    db: sqlite3.Connection = Depends(get_db),
    current_user_data = Depends(require_auth_cookie)
):
    """Página principal con listado de facturas (requiere autenticación)"""
    try:
        current_user, token_data = current_user_data
        cursor = db.cursor()
        
        # Actualizar consulta para incluir nuevos campos
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

        for factura in facturas_raw[:1]:  # Solo la primera para no llenar logs
            factura_dict = dict(factura)
            logger.info(f"DEBUG - Datos de factura desde DB:")
            logger.info(f"  fecha_factura: '{factura_dict.get('fecha_factura')}' (tipo: {type(factura_dict.get('fecha_factura'))})")
            logger.info(f"  created_at: '{factura_dict.get('created_at')}' (tipo: {type(factura_dict.get('created_at'))})")

        facturas = []
        for factura in facturas_raw:
            factura_dict = dict(factura)
            # Usar la nueva función de procesamiento
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
    
@app.get("/factura/{factura_id}", response_class=HTMLResponse)
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
    
@app.post("/extract-text")
async def extract_text_from_pdfs(
    files: List[UploadFile] = File(...), 
    db: sqlite3.Connection = Depends(get_db),
    current_user_data = Depends(require_auth_cookie)
):
    """Procesar PDFs (requiere permisos de creación)"""
    current_user, token_data = current_user_data
    
    # Verificar permisos
    if "facturas:create" not in token_data.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para crear facturas"
        )
    
    resultados = []
    for file in files:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_file.write(await file.read())
                temp_path = temp_file.name

            extracted_data = process_pdf(temp_path)
            entities = extracted_data.get("entities", {})
            if entities:
                guardar_factura_en_db(db, file.filename, entities)

            resultados.append({
                "filename": file.filename,
                "message": f"Factura procesada (página 1 de {extracted_data.get('pages_processed', 'N/A')}).",
                "summary_text": (extracted_data.get("text", "")[:200] + "...") if extracted_data.get("text") else "No se pudo extraer texto.",
                "extracted_entities": entities,
                "pages_processed": extracted_data.get("pages_processed", 0),
                "processed_by": current_user.username
            })
        except Exception as e:
            logger.error(f"Error con {file.filename}: {e}")
            resultados.append({"filename": file.filename, "error": str(e)})
        finally:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)

    db.commit()
    return JSONResponse(content={"resultados": resultados})

# === NUEVA RUTA PARA DASHBOARD/ESTADÍSTICAS ===
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    current_user_data = Depends(require_auth_cookie)
):
    """Dashboard con estadísticas del sistema"""
    current_user, token_data = current_user_data
    
    try:
        cursor = db.cursor()
        
        # Estadísticas básicas
        if current_user.role in ["admin", "contador", "auditor"]:
            cursor.execute("SELECT COUNT(*) FROM facturas")
            total_facturas = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(total) FROM facturas WHERE total IS NOT NULL")
            total_importe = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT COUNT(DISTINCT cuit_proveedor) FROM facturas WHERE cuit_proveedor IS NOT NULL")
            total_proveedores = cursor.fetchone()[0]
            
        elif current_user.role == "cliente":
            cursor.execute("SELECT COUNT(*) FROM facturas WHERE cuit_proveedor = ?", (current_user.cuit_asociado,))
            total_facturas = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(total) FROM facturas WHERE cuit_proveedor = ? AND total IS NOT NULL", (current_user.cuit_asociado,))
            total_importe = cursor.fetchone()[0] or 0
            
            total_proveedores = 1  # Solo su propio CUIT
        
        else:
            total_facturas = total_importe = total_proveedores = 0

        estadisticas = {
            "total_facturas": total_facturas,
            "total_importe": total_importe,
            "total_proveedores": total_proveedores,
            "importe_formateado": _formatear_moneda(total_importe)
        }

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "current_user": current_user,
            "estadisticas": estadisticas,
            "permissions": token_data.permissions
        })

    except Exception as e:
        logger.error(f"Error en dashboard: {e}")
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "current_user": current_user,
            "error": str(e)
        })

# === RUTA DE API PARA OBTENER ESTADÍSTICAS ===
@app.get("/api/estadisticas")
async def api_estadisticas(
    current_user_data = Depends(get_current_user_from_cookie),
    db: sqlite3.Connection = Depends(get_db)
):
    """API para obtener estadísticas (requiere autenticación)"""
    current_user, token_data = current_user_data
    
    if "reportes:read" not in token_data.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para ver reportes"
        )
    
    return obtener_estadisticas_facturas(db)

#----------------AGENTE------------------------------------------------------------------
@app.post("/agente/consulta")
async def consulta_agente(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """
    Endpoint para consultas en lenguaje natural
    """
    try:
        # Obtener datos del formulario
        form_data = await request.form()
        consulta = form_data.get("consulta", "").strip()
        
        if not consulta:
            return JSONResponse(
                content={"error": "Debes escribir una consulta"},
                status_code=400
            )
        
        # Procesar con el agente
        agente = AgenteFacturas(db)
        resultado = agente.procesar_consulta(consulta)
        
        return JSONResponse(content=resultado)
        
    except Exception as e:
        logger.error(f"Error en consulta agente: {e}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )

@app.get("/agente", response_class=HTMLResponse)
async def pagina_agente(request: Request):
    """
    Página del agente inteligente
    """
    return templates.TemplateResponse("agente.html", {"request": request})

@app.get("/agente/similares/{factura_id}")
async def facturas_similares(factura_id: int, db: sqlite3.Connection = Depends(get_db)):
    """
    Buscar facturas similares a una específica
    """
    try:
        agente = AgenteFacturas(db)
        similares = agente.buscar_facturas_similares(factura_id)
        
        return JSONResponse(content={
            "factura_id": factura_id,
            "similares": similares,
            "total_encontradas": len(similares)
        })
        
    except Exception as e:
        logger.error(f"Error buscando similares: {e}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )

@app.get("/agente/duplicados")
async def detectar_duplicados(db: sqlite3.Connection = Depends(get_db)):
    """
    Detectar facturas duplicadas
    """
    try:
        agente = AgenteFacturas(db)
        duplicados = agente.detectar_duplicados()
        
        return JSONResponse(content={
            "duplicados": duplicados,
            "total_duplicados": len(duplicados)
        })
        
    except Exception as e:
        logger.error(f"Error detectando duplicados: {e}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )

@app.get("/agente/estadisticas")
async def estadisticas_inteligentes(db: sqlite3.Connection = Depends(get_db)):

    """
    Estadísticas inteligentes sobre las facturas
    """
    try:
        agente = AgenteFacturas(db)
        estadisticas = agente.obtener_estadisticas_inteligentes()
        
        return JSONResponse(content=estadisticas)
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )
    

@app.get("/reportes", response_class=HTMLResponse)
async def reportes_page(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    current_user_data = Depends(require_auth_cookie)
):
    """Página de reportes (solo admin y contador)"""
    current_user, token_data = current_user_data
    
    # Verificar permisos
    if "reportes:read" not in token_data.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para ver reportes"
        )
    
    try:
        # Estadísticas básicas para mostrar en la página
        cursor = db.cursor()
        
        # Construir WHERE clause correctamente
        where_conditions = []
        params = []
        
        if current_user.role == "cliente" and current_user.cuit_asociado:
            where_conditions.append("cuit_proveedor = ?")
            params.append(current_user.cuit_asociado)
        
        # Construir WHERE clause final
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)
        
        # Métricas generales
        cursor.execute(f"SELECT COUNT(*) FROM facturas {where_clause}", params)
        total_facturas = cursor.fetchone()[0]
        
        # Para el total, necesitamos agregar condición de total IS NOT NULL
        total_where_conditions = where_conditions.copy()
        total_where_conditions.append("total IS NOT NULL")
        total_where_clause = "WHERE " + " AND ".join(total_where_conditions)
        total_params = params + []  # Copia de params, no se agrega nada nuevo
        
        cursor.execute(f"SELECT SUM(total) FROM facturas {total_where_clause}", total_params)
        total_importe = cursor.fetchone()[0] or 0
        
        # Para proveedores únicos
        prov_where_conditions = where_conditions.copy()
        prov_where_conditions.append("cuit_proveedor IS NOT NULL")
        prov_where_clause = "WHERE " + " AND ".join(prov_where_conditions) if prov_where_conditions else ""
        prov_params = params + []
        
        cursor.execute(f"SELECT COUNT(DISTINCT cuit_proveedor) FROM facturas {prov_where_clause}", prov_params)
        total_proveedores = cursor.fetchone()[0]
        
        estadisticas = {
            "total_facturas": total_facturas,
            "total_importe": total_importe,
            "total_proveedores": total_proveedores,
            "importe_formateado": _formatear_moneda(total_importe)
        }
        
        return templates.TemplateResponse("reportes.html", {
            "request": request,
            "current_user": current_user,
            "estadisticas": estadisticas,
            "permissions": token_data.permissions
        })
        
    except Exception as e:
        logger.error(f"Error en página de reportes: {e}")
        # En caso de error, devolver estadísticas vacías
        estadisticas = {
            "total_facturas": 0,
            "total_importe": 0,
            "total_proveedores": 0,
            "importe_formateado": "0,00"
        }
        
        return templates.TemplateResponse("reportes.html", {
            "request": request,
            "current_user": current_user,
            "estadisticas": estadisticas,
            "permissions": token_data.permissions,
            "error": f"Error cargando estadísticas: {str(e)}"
        })
    
@app.get("/api/reportes/facturas-mes")
async def reporte_facturas_mes(
    db: sqlite3.Connection = Depends(get_db),
    current_user_data = Depends(require_auth_cookie)
):
    """Datos para reporte de facturas por mes"""
    current_user, token_data = current_user_data
    
    # Verificar permisos
    if "reportes:read" not in token_data.permissions:
        raise HTTPException(status_code=403, detail="Sin permisos")
    
    try:
        cursor = db.cursor()
        
        # Construir WHERE clause según permisos
        where_conditions = []
        params = []
        
        if current_user.role == "cliente" and current_user.cuit_asociado:
            where_conditions.append("cuit_proveedor = ?")
            params.append(current_user.cuit_asociado)
        
        # Agregar condición para fechas válidas
        where_conditions.append("created_at IS NOT NULL")
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        # Consulta para obtener facturas por mes
        cursor.execute(f"""
            SELECT 
                strftime('%Y-%m', created_at) as mes,
                COUNT(*) as cantidad,
                SUM(CASE WHEN total IS NOT NULL THEN total ELSE 0 END) as total_importe,
                AVG(CASE WHEN total IS NOT NULL THEN total ELSE 0 END) as promedio
            FROM facturas 
            {where_clause}
            GROUP BY strftime('%Y-%m', created_at)
            ORDER BY mes DESC
            LIMIT 12
        """, params)
        
        resultados = cursor.fetchall()
        
        # Formatear datos para el gráfico
        datos = []
        for row in resultados:
            mes, cantidad, total, promedio = row
            
            # Formatear el nombre del mes
            try:
                from datetime import datetime
                fecha_obj = datetime.strptime(mes, '%Y-%m')
                mes_nombre = fecha_obj.strftime('%b %Y')  # Ej: "Jan 2024"
            except:
                mes_nombre = mes
            
            datos.append({
                "mes": mes,
                "mes_nombre": mes_nombre,
                "cantidad": cantidad,
                "total_importe": float(total or 0),
                "promedio": float(promedio or 0),
                "total_formateado": _formatear_moneda(total or 0)
            })
        
        return JSONResponse(content={
            "success": True,
            "data": datos,
            "total_meses": len(datos)
        })
        
    except Exception as e:
        logger.error(f"Error en reporte facturas por mes: {e}")
        return JSONResponse(content={
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/reportes/top-proveedores")
async def reporte_top_proveedores(
    db: sqlite3.Connection = Depends(get_db),
    current_user_data = Depends(require_auth_cookie)
):
    """Top proveedores usando el agente inteligente"""
    current_user, token_data = current_user_data
    
    # Verificar permisos
    if "reportes:read" not in token_data.permissions:
        raise HTTPException(status_code=403, detail="Sin permisos")
    
    try:
        # Usar el agente para obtener estadísticas
        agente = AgenteFacturas(db)
        estadisticas = agente.obtener_estadisticas_inteligentes()
        
        # Extraer top proveedores de las estadísticas del agente
        top_proveedores = estadisticas.get('top_proveedores', [])
        
        # Formatear datos para el gráfico
        datos_formateados = []
        for proveedor in top_proveedores:
            datos_formateados.append({
                "razon_social": proveedor['razon_social'],
                "cantidad": proveedor['cantidad'],
                "total_proveedor": float(proveedor['total_proveedor'] or 0),
                "total_formateado": _formatear_moneda(proveedor['total_proveedor'] or 0)
            })
        
        return JSONResponse(content={
            "success": True,
            "data": datos_formateados,
            "total_proveedores": len(datos_formateados),
            "descripcion": f"Top {len(datos_formateados)} proveedores por volumen de facturación"
        })
        
    except Exception as e:
        logger.error(f"Error en reporte top proveedores: {e}")
        return JSONResponse(content={
            "success": False,
            "error": str(e)
        }, status_code=500)

def obtener_estadisticas_facturas(db: sqlite3.Connection) -> Dict:
    """
    Obtiene estadísticas usando el agente inteligente
    """
    try:
        # Usar el agente inteligente existente
        agente = AgenteFacturas(db)
        estadisticas = agente.obtener_estadisticas_inteligentes()
        
        # El agente ya devuelve las estadísticas en el formato correcto
        return estadisticas
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas con agente: {e}")
        # Fallback simple si falla el agente
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM facturas")
        total_facturas = cursor.fetchone()[0]
        
        return {
            "total_facturas": total_facturas,
            "suma_total": 0,
            "total_proveedores": 0,
            "suma_total_formateada": "$0,00",
            "top_proveedores": [],
            "facturas_por_mes": []
        }
    
