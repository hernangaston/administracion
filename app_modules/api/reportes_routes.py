# -*- coding: utf-8 -*-
"""
Rutas de reportes - Simplificado
"""

import sqlite3
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app_modules.utils.formatters import formatear_moneda
from auth_routes import require_auth_cookie, get_current_user_from_cookie
from agente_facturas import AgenteFacturas


templates = Jinja2Templates(directory="templates")
reportes_router = APIRouter()
logger = logging.getLogger(__name__)

def _formatear_moneda(valor) -> str:
    """Helper para formatear moneda"""
    if valor is None:
        return "$0,00"    
    try:
        return formatear_moneda(valor)
    except Exception as e:
        logger.warning(f"Error formateando moneda '{valor}': {e}")
        return str(valor) if valor else "$0,00"

def obtener_estadisticas_facturas(db: sqlite3.Connection):
    """Obtiene estadísticas usando el agente inteligente - COPIADO DEL ORIGINAL"""
    try:
        agente = AgenteFacturas(db)
        estadisticas = agente.obtener_estadisticas_inteligentes()
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

@reportes_router.get("/reportes", response_class=HTMLResponse)
async def reportes_page(
    request: Request,
    db: sqlite3.Connection = Depends(lambda: sqlite3.connect("database.db", check_same_thread=False)),
    current_user_data = Depends(require_auth_cookie)
):
    """Página de reportes (solo admin y contador) - COPIADO DEL ORIGINAL"""
    current_user, token_data = current_user_data
    
    # Verificar permisos
    if "reportes:read" not in token_data.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para ver reportes"
        )
    
    try:
        cursor = db.cursor()
        
        # Construir WHERE clause según permisos - COPIADO DEL ORIGINAL
        where_conditions = []
        params = []
        
        if current_user.role == "cliente" and current_user.cuit_asociado:
            where_conditions.append("cuit_proveedor = ?")
            params.append(current_user.cuit_asociado)
        
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)
        
        # Métricas generales
        cursor.execute(f"SELECT COUNT(*) FROM facturas {where_clause}", params)
        total_facturas = cursor.fetchone()[0]
        
        # Para el total, agregar condición de total IS NOT NULL
        total_where_conditions = where_conditions.copy()
        total_where_conditions.append("total IS NOT NULL")
        total_where_clause = "WHERE " + " AND ".join(total_where_conditions)
        total_params = params + []
        
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
    finally:
        db.close()

@reportes_router.get("/api/estadisticas")
async def api_estadisticas(
    current_user_data = Depends(get_current_user_from_cookie),
    db: sqlite3.Connection = Depends(lambda: sqlite3.connect("database.db", check_same_thread=False))
):
    """API para obtener estadísticas (requiere autenticación) - COPIADO DEL ORIGINAL"""
    current_user, token_data = current_user_data
    
    if "reportes:read" not in token_data.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para ver reportes"
        )
    
    try:
        return obtener_estadisticas_facturas(db)
    finally:
        db.close()

@reportes_router.get("/api/reportes/facturas-mes")
async def reporte_facturas_mes(
    db: sqlite3.Connection = Depends(lambda: sqlite3.connect("database.db", check_same_thread=False)),
    current_user_data = Depends(require_auth_cookie)
):
    """Datos para reporte de facturas por mes - COPIADO DEL ORIGINAL"""
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
    finally:
        db.close()

@reportes_router.get("/api/reportes/top-proveedores")
async def reporte_top_proveedores(
    db: sqlite3.Connection = Depends(lambda: sqlite3.connect("database.db", check_same_thread=False)),
    current_user_data = Depends(require_auth_cookie)
):
    """Top proveedores usando el agente inteligente - COPIADO DEL ORIGINAL"""
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
    finally:
        db.close()