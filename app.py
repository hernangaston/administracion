# -*- coding: utf-8 -*-

import os
import sqlite3
import logging
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from app_modules.core.config import setup_google_credentials
from app_modules.core.database import init_database
from auth_routes import auth_router
from auth import init_auth_tables

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Configurar credenciales
setup_google_credentials()

# Crear aplicación FastAPI
app = FastAPI(
    title="Sistema de Facturas",
    description="Sistema de procesamiento y gestión de facturas con IA",
    version="2.0.0"
)

# Configurar templates y archivos estáticos
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
def startup():
    """Configuración de inicio simplificada"""
    logger.info("🚀 Iniciando Sistema de Facturas")
    
    # Verificar configuración crítica
    PROJECT_ID = os.getenv("DOCAI_PROJECT_ID")
    LOCATION = os.getenv("DOCAI_LOCATION", "us")
    PROCESSOR_ID = os.getenv("DOCAI_PROCESSOR_ID")
    
    if not all([PROJECT_ID, LOCATION, PROCESSOR_ID]):
        logger.critical("❌ Faltan variables de entorno críticas para Document AI")
        missing = []
        if not PROJECT_ID: missing.append("DOCAI_PROJECT_ID")
        if not LOCATION: missing.append("DOCAI_LOCATION") 
        if not PROCESSOR_ID: missing.append("DOCAI_PROCESSOR_ID")
        logger.critical(f"Variables faltantes: {', '.join(missing)}")
    else:
        logger.info("✅ Configuración de Document AI verificada")
    
    # Inicializar base de datos
    try:
        init_database()
        
        # Inicializar tablas de autenticación
        db = sqlite3.connect("database.db")
        init_auth_tables(db)
        db.close()
        
        logger.info("✅ Base de datos inicializada correctamente")
        
    except Exception as e:
        logger.error(f"❌ Error inicializando base de datos: {e}")
        raise
    
    logger.info("🎉 Sistema iniciado exitosamente")

# Registrar router de autenticación
app.include_router(auth_router)

# Importar y registrar otros routers de forma condicional
try:
    from app_modules.api.facturas_routes import facturas_router
    app.include_router(facturas_router)
    logger.info("✅ Rutas de facturas cargadas")
except ImportError as e:
    logger.warning(f"⚠️ No se pudieron cargar las rutas de facturas: {e}")

try:
    from app_modules.api.dashboard_routes import dashboard_router
    app.include_router(dashboard_router)
    logger.info("✅ Rutas de dashboard cargadas")
except ImportError as e:
    logger.warning(f"⚠️ No se pudieron cargar las rutas de dashboard: {e}")

try:
    from app_modules.api.agente_routes import agente_router
    app.include_router(agente_router, prefix="/agente")
    logger.info("✅ Rutas de agente cargadas")
except ImportError as e:
    logger.warning(f"⚠️ No se pudieron cargar las rutas de agente: {e}")

try:
    from app_modules.api.reportes_routes import reportes_router
    app.include_router(reportes_router)
    logger.info("✅ Rutas de reportes cargadas")
except ImportError as e:
    logger.warning(f"⚠️ No se pudieron cargar las rutas de reportes: {e}")

# Endpoint raíz
@app.get("/")
async def root():
    """Redirigir al dashboard por defecto"""
    from fastapi.responses import RedirectResponse
    try:
        return RedirectResponse(url="/dashboard")
    except:
        # Fallback si dashboard no está disponible
        return RedirectResponse(url="/auth/login")

# FALLBACK: Si no se cargaron los módulos, incluir rutas básicas del original

# Solo incluir estas rutas si no se cargaron los módulos
if not any(route.path.startswith("/dashboard") for route in app.routes):
    logger.warning("⚠️ Cargando rutas de fallback del archivo original...")
    
    # AQUÍ IRÍA EL CÓDIGO DE RUTAS DEL ARCHIVO ORIGINAL
    # Por simplicidad, redirigir a auth por ahora
    @app.get("/dashboard")
    async def dashboard_fallback():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/auth/login")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)