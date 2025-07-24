# app/api/v1/router.py
from fastapi import APIRouter

from app.api.v1.endpoints import facturas

# Router principal de API v1
api_router = APIRouter()

# Incluir endpoints
api_router.include_router(facturas.router)

# Health check endpoint
@api_router.get("/health")
async def health_check():
    """
    ✅ Health check para monitoreo
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "service": "factura-api"
    }