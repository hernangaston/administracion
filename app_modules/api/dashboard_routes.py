# -*- coding: utf-8 -*-
"""
Rutas del dashboard
"""

import sqlite3
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app_modules.core.database import get_db
from app_modules.utils.formatters import formatear_moneda
from auth_routes import require_auth_cookie

templates = Jinja2Templates(directory="templates")
dashboard_router = APIRouter()

@dashboard_router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    current_user_data = Depends(require_auth_cookie)
):
    """Dashboard con estadísticas del sistema"""
    current_user, token_data = current_user_data
    
    try:
        cursor = db.cursor()
        
        # Estadísticas según el rol del usuario
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
            "importe_formateado": formatear_moneda(total_importe)
        }

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "current_user": current_user,
            "estadisticas": estadisticas,
            "permissions": token_data.permissions
        })

    except Exception as e:
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