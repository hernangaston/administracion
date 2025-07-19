# -*- coding: utf-8 -*-
"""
Rutas del dashboard - Simplificado
"""

import sqlite3
import logging
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app_modules.utils.formatters import formatear_moneda
from auth_routes import require_auth_cookie

templates = Jinja2Templates(directory="templates")
dashboard_router = APIRouter()
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

@dashboard_router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: sqlite3.Connection = Depends(lambda: sqlite3.connect("database.db", check_same_thread=False)),
    current_user_data = Depends(require_auth_cookie)
):
    """Dashboard con estadísticas del sistema - COPIADO DEL ORIGINAL"""
    current_user, token_data = current_user_data
    
    try:
        cursor = db.cursor()
        
        # Estadísticas según el rol - COPIADO DEL ORIGINAL
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
            "estadisticas": {
                "total_facturas": 0,
                "total_importe": 0,
                "total_proveedores": 0,
                "importe_formateado": "$0,00"
            },
            "permissions": token_data.permissions if 'token_data' in locals() else [],
            "error": str(e)
        })
    finally:
        db.close()