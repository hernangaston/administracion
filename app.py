# -*- coding: utf-8 -*-
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from google.cloud import documentai_v1 as documentai
from dotenv import load_dotenv
import os
import sqlite3
from typing import List, Dict
import traceback
import logging

# Asegúrate que la importación coincida con la ubicación de tu archivo
from parser_factura import guardar_factura_en_db, verificar_entidades_disponibles, obtener_estadisticas_facturas

from cuit_utils import limpiar_cuit, formatear_cuit, validar_cuit

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
LOCATION = os.getenv("DOCAI_LOCATION", "us") # Default a 'us' si no se especifica
PROCESSOR_ID = os.getenv("DOCAI_PROCESSOR_ID")

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

def limpiar_datos_factura(entities):
    campos_cuit = ['supplier_tax_id', 'receiver_tax_id', 'cuit_proveedor', 'cliente_cuit']
    for campo in campos_cuit:
        if campo in entities and entities[campo]:
            entities[campo] = limpiar_cuit(entities[campo])
    return entities

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

@app.on_event("startup")
def startup():
    if not all([PROJECT_ID, LOCATION, PROCESSOR_ID]):
        logger.critical("Faltan variables de entorno críticas para Document AI (DOCAI_PROJECT_ID, DOCAI_LOCATION, DOCAI_PROCESSOR_ID).")
        # En un entorno de producción, podrías querer que la aplicación no inicie.
        # import sys
        # sys.exit(1)
    init_db_tables()

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



# Modificar la ruta home para formatear CUITs en el listado
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Página principal con listado de facturas"""
    try:
        conn = sqlite3.connect("database.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, filename, razon_social, cuit_proveedor, subtotal, iva, total, created_at FROM facturas ORDER BY created_at DESC")
        facturas_raw = cursor.fetchall()
        conn.close()

        # NUEVO: Formatear CUITs y números para visualización
        facturas = []
        for factura in facturas_raw:
            factura_dict = dict(factura)
            if factura_dict.get('cuit_proveedor'):
                factura_dict['cuit_proveedor_formateado'] = formatear_cuit(factura_dict['cuit_proveedor'])
            # Formatear números a dos decimales con coma
            for key in ['subtotal', 'iva', 'total']:
                if factura_dict.get(key) is not None:
                    try:
                        factura_dict[f'{key}_formateado'] = f"{float(factura_dict[key]):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    except (ValueError, TypeError):
                        factura_dict[f'{key}_formateado'] = factura_dict[key] # Dejar como está si no es un número
            facturas.append(factura_dict)

        return templates.TemplateResponse("index.html", {"request": request, "facturas": facturas})

    except Exception as e:
        logger.error(f"Error en ruta home: {e}")
        return templates.TemplateResponse("index.html", {"request": request, "facturas": [], "error": str(e)})
    
# Agregar nueva ruta para formatear CUIT para visualización
@app.get("/factura/{factura_id}", response_class=HTMLResponse)
async def ver_factura(request: Request, factura_id: int):
    """Ver detalle de una factura específica"""
    try:
        conn = sqlite3.connect("database.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM facturas WHERE id = ?", (factura_id,))
        factura = cursor.fetchone()
        conn.close()

        if not factura:
            logger.warning(f"Factura con ID {factura_id} no encontrada")
            return templates.TemplateResponse("detalle.html", {"request": request, "factura": None})

        # NUEVO: Convertir Row a dict y formatear CUITs para visualización
        factura_dict = dict(factura)
        if factura_dict.get('cuit_proveedor'):
            factura_dict['cuit_proveedor_formateado'] = formatear_cuit(factura_dict['cuit_proveedor'])
        # Formatear números a dos decimales con coma
        for key in ['subtotal', 'iva', 'total']:
            if factura_dict.get(key) is not None:
                try:
                    factura_dict[f'{key}_formateado'] = f"{float(factura_dict[key]):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                except (ValueError, TypeError):
                    factura_dict[f'{key}_formateado'] = factura_dict[key]
        return templates.TemplateResponse("detalle.html", {"request": request, "factura": factura_dict})

    except Exception as e:
        logger.error(f"Error obteniendo factura {factura_id}: {e}")
        return templates.TemplateResponse("detalle.html", {"request": request, "factura": None, "error": str(e)})

@app.post("/extract-text")
async def extract_text_from_pdfs(files: List[UploadFile] = File(...)):
    resultados = []
    for file in files:
        try:
            temp_path = f"/tmp/{file.filename}"
            with open(temp_path, "wb") as f:
                f.write(await file.read())
            extracted_data = process_pdf(temp_path)
            if extracted_data.get("entities"):
                entities_limpias = limpiar_datos_factura(extracted_data["entities"])
                guardar_factura_en_db(file.filename, entities_limpias)
            resultados.append({
                "filename": file.filename,
                "message": f"Factura procesada (página 1 de {extracted_data.get('pages_processed', 'N/A')}).",
                "summary_text": extracted_data.get("text", "")[:200] + "...",
                "extracted_entities": entities_limpias if 'entities_limpias' in locals() else extracted_data.get("entities", {}),
                "pages_processed": extracted_data.get("pages_processed", 0)
            })
        except Exception as e:
            logger.error(f"Error con {file.filename}: {e}")
            resultados.append({"filename": file.filename, "error": str(e)})
    return JSONResponse(content={"resultados": resultados})
