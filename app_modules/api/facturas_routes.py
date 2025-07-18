# -*- coding: utf-8 -*-
"""
Rutas relacionadas con facturas
"""

import os
import tempfile
import sqlite3
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app_modules.core.database import get_db
from app_modules.services.pdf_processor import process_pdf
from app_modules.utils.formatters import formatear_moneda
from app_modules.utils.cuit_utils import formatear_cuit
from auth_routes import require_auth_cookie
from auth import can_access_factura
from parser_factura import guardar_factura_en_db

templates = Jinja2Templates(directory="templates")
facturas_router = APIRouter()

def _formatear_moneda_safe(valor) -> str:
    """Wrapper seguro para formatear moneda"""
    try:
        return formatear_moneda(valor)
    except Exception:
        return str(valor) if valor else "$0,00"

def _formatear_fecha(fecha_str) -> str:
    """Formatea una fecha para mostrar en la interfaz."""
    if not fecha_str or fecha_str in ['', 'None', None]:
        return "Sin fecha"
    
    try:
        from datetime import datetime
        fecha_str = str(fecha_str).strip()
        
        # Intentar diferentes formatos
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
            # Manejar formatos ISO con T
            if 'T' in fecha_str:
                fecha_parte = fecha_str.split('T')[0]
                fecha_obj = datetime.strptime(fecha_parte, '%Y-%m-%d')
                return fecha_obj.strftime('%d/%m/%Y')
            elif len(fecha_str) >= 10:
                fecha_parte = fecha_str[:10]
                fecha_obj = datetime.strptime(fecha_parte, '%Y-%m-%d')
                return fecha_obj.strftime('%d/%m/%Y')
                
        return str(fecha_str)
        
    except Exception:
        return "Fecha inválida"

def _procesar_factura_para_vista(factura_dict):
    """Procesa una factura para mostrar en la vista con formatos correctos."""
    
    # Formatear monedas
    for campo_moneda in ['subtotal', 'iva', 'total']:
        if campo_moneda in factura_dict:
            factura_dict[f'{campo_moneda}_formateado'] = _formatear_moneda_safe(factura_dict.get(campo_moneda))
    
    # Formatear fechas
    campos_fecha = {
        'fecha_factura': 'fecha_factura_formateada',
        'fecha_vencimiento': 'fecha_vencimiento_formateada', 
        'created_at': 'created_at_formateado'
    }
    
    for campo_orig, campo_format in campos_fecha.items():
        if campo_orig in factura_dict:
            factura_dict[campo_format] = _formatear_fecha(factura_dict.get(campo_orig))
    
    # Formatear número de factura
    if 'numero_factura' in factura_dict:
        numero = factura_dict.get('numero_factura')
        factura_dict['numero_factura_formateado'] = str(numero).strip() if numero else "Sin número"
    
    # Formatear CUIT
    if 'cuit_proveedor' in factura_dict:
        factura_dict['cuit_proveedor_formateado'] = formatear_cuit(factura_dict.get('cuit_proveedor'))
    
    return factura_dict

@facturas_router.get("/facturas", response_class=HTMLResponse)
async def lista_facturas(
    request: Request, 
    db: sqlite3.Connection = Depends(get_db),
    current_user_data = Depends(require_auth_cookie)
):
    """Página principal con listado de facturas (requiere autenticación)"""
    try:
        current_user, token_data = current_user_data
        cursor = db.cursor()
        
        # Consulta según permisos del usuario
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

        # Procesar facturas para la vista
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
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "facturas": [], 
            "error": str(e),
            "current_user": current_user if 'current_user' in locals() else None
        })

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

        # Formatear datos para la vista
        factura_dict = _procesar_factura_para_vista(factura_dict)

        return templates.TemplateResponse("detalle.html", {
            "request": request, 
            "factura": factura_dict,
            "current_user": current_user
        })

    except HTTPException:
        raise
    except Exception as e:
        return templates.TemplateResponse("detalle.html", {
            "request": request, 
            "factura": None, 
            "error": str(e),
            "current_user": current_user if 'current_user' in locals() else None
        })

@facturas_router.post("/extract-text")
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
    
    # Límites de seguridad
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
            # Validar archivo PDF
            if not (file.content_type == 'application/pdf' or file.filename.lower().endswith('.pdf')):
                resultados.append({
                    "filename": file.filename,
                    "error": "Solo se permiten archivos PDF"
                })
                continue
            
            # Guardar temporalmente
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                content = await file.read()
                
                # Límite de tamaño (50MB)
                if len(content) > 50 * 1024 * 1024:
                    raise ValueError(f"Archivo demasiado grande: {len(content)} bytes")
                
                temp_file.write(content)
                temp_path = temp_file.name

            # Procesar con Document AI
            extracted_data = process_pdf(temp_path)
            
            # Verificar si hay datos válidos
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
        return JSONResponse(content={
            "resultados": resultados,
            "total_archivos": len(files),
            "archivos_exitosos": archivos_procesados
        })
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error guardando cambios en base de datos"
        )