# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from google.cloud import documentai_v1 as documentai
from dotenv import load_dotenv
import os
import tempfile
import sqlite3
from typing import List, Dict
import traceback
import logging

# Asegúrate que la importación coincida con la ubicación de tu archivo
from parser_factura import guardar_factura_en_db, verificar_entidades_disponibles, obtener_estadisticas_facturas

from cuit_utils import limpiar_cuit, formatear_cuit, validar_cuit

from auth_routes import auth_router, require_auth_cookie, get_current_user_from_cookie
from auth import init_auth_tables, can_access_factura

# Configurar logging con nivel WARNING para reducir ruido
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Cargar variables de entorno desde .env
load_dotenv()

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
                cuit_proveedor TEXT, -- Se mantiene como TEXT por los guiones, pero se valida que sean 11 dígitos
                subtotal REAL,
                iva REAL,
                total REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Tabla para el texto completo extraído del PDF
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pdf_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                extracted_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP 
            );
        """)
        conn.commit()
        conn.close()

    except sqlite3.Error as e:
        logger.error(f"Error inicializando base de datos: {e}")

# Helper para formatear moneda
def _formatear_moneda(valor) -> str:
    """Formatea un número a string con formato de moneda argentina."""
    if valor is None:
        return ""
    try:
        # Formato: 1.234,56
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(valor) # Dejar como está si no es un número

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
        
        # Filtrar facturas según el rol del usuario
        if current_user.role in ["admin", "contador", "vendedor", "auditor"]:
            # Pueden ver todas las facturas
            cursor.execute("""
                SELECT id, filename, razon_social, cuit_proveedor, subtotal, iva, total, created_at 
                FROM facturas ORDER BY created_at DESC
            """)
        elif current_user.role == "cliente":
            # Solo pueden ver facturas de su CUIT
            if current_user.cuit_asociado:
                cursor.execute("""
                    SELECT id, filename, razon_social, cuit_proveedor, subtotal, iva, total, created_at 
                    FROM facturas 
                    WHERE cuit_proveedor = ? OR razon_social LIKE ?
                    ORDER BY created_at DESC
                """, (current_user.cuit_asociado, f"%{current_user.cuit_asociado}%"))
            else:
                cursor.execute("SELECT * FROM facturas WHERE 1=0")  # No mostrar nada
        else:
            cursor.execute("SELECT * FROM facturas WHERE 1=0")  # No mostrar nada

        facturas_raw = cursor.fetchall()
        facturas = []
        for factura in facturas_raw:
            factura_dict = dict(factura)
            factura_dict['cuit_proveedor_formateado'] = formatear_cuit(factura_dict.get('cuit_proveedor'))
            for key in ['subtotal', 'iva', 'total']:
                factura_dict[f'{key}_formateado'] = _formatear_moneda(factura_dict.get(key))
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