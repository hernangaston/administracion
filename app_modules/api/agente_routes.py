# -*- coding: utf-8 -*-
"""
Rutas del agente inteligente
"""

import sqlite3
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app_modules.core.database import get_db
from agente_facturas import AgenteFacturas

templates = Jinja2Templates(directory="templates")
agente_router = APIRouter()

@agente_router.get("/", response_class=HTMLResponse)
async def pagina_agente(request: Request):
    """Página del agente inteligente"""
    return templates.TemplateResponse("agente.html", {"request": request})

@agente_router.post("/consulta")
async def consulta_agente(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """Endpoint para consultas en lenguaje natural"""
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
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )

@agente_router.get("/similares/{factura_id}")
async def facturas_similares(factura_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Buscar facturas similares a una específica"""
    try:
        agente = AgenteFacturas(db)
        similares = agente.buscar_facturas_similares(factura_id)
        
        return JSONResponse(content={
            "factura_id": factura_id,
            "similares": similares,
            "total_encontradas": len(similares)
        })
        
    except Exception as e:
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )

@agente_router.get("/duplicados")
async def detectar_duplicados(db: sqlite3.Connection = Depends(get_db)):
    """Detectar facturas duplicadas"""
    try:
        agente = AgenteFacturas(db)
        duplicados = agente.detectar_duplicados()
        
        return JSONResponse(content={
            "duplicados": duplicados,
            "total_duplicados": len(duplicados)
        })
        
    except Exception as e:
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )

@agente_router.get("/estadisticas")
async def estadisticas_inteligentes(db: sqlite3.Connection = Depends(get_db)):
    """Estadísticas inteligentes sobre las facturas"""
    try:
        agente = AgenteFacturas(db)
        estadisticas = agente.obtener_estadisticas_inteligentes()
        
        return JSONResponse(content=estadisticas)
        
    except Exception as e:
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )