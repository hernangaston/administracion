# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings, setup_google_credentials
from app.infrastructure.database.connection import init_database, close_database
from app.core.dependencies import setup_dependencies
from app.api.v1.router import api_router

# Configurar logging básico
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación"""
    
    # === STARTUP ===
    logger.info("🚀 Iniciando Sistema de Facturas API v2.0")
    
    try:
        # 1. Configurar credenciales Google
        setup_google_credentials()
        logger.info("✅ Google credentials configuradas")
        
        # 2. Inicializar base de datos
        await init_database()
        logger.info("✅ Base de datos inicializada")
        
        # 3. Setup dependencias
        await setup_dependencies()
        logger.info("✅ Dependencias configuradas")
        
        logger.info("🎉 Aplicación iniciada exitosamente")
        
    except Exception as e:
        logger.error(f"❌ Error durante startup: {e}")
        raise
    
    yield
    
    # === SHUTDOWN ===
    logger.info("🔄 Cerrando aplicación...")
    
    try:
        await close_database()
        logger.info("✅ Base de datos cerrada")
    except Exception as e:
        logger.error(f"❌ Error durante shutdown: {e}")
    
    logger.info("👋 Aplicación cerrada correctamente")


def create_app() -> FastAPI:
    """Factory para crear la aplicación FastAPI"""
    
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.VERSION,
        description="""
        ## 🚀 Sistema de Facturas API v2.0
        
        **API-First** para procesamiento inteligente de facturas con Document AI.
        
        ### Características:
        - 📄 Procesamiento automático de PDFs
        - 🤖 Extracción de datos con Google Document AI  
        - 📊 Consultas y reportes avanzados
        - 🔐 Autenticación JWT + RBAC
        - ⚡ Arquitectura async para máximo rendimiento
        
        ### Endpoints principales:
        - `POST /api/v1/facturas/upload` - Subir y procesar facturas
        - `GET /api/v1/facturas/` - Listar facturas con filtros
        - `GET /api/v1/facturas/{id}` - Obtener factura específica
        - `GET /api/v1/health` - Health check
        """,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan
    )
    
    # === MIDDLEWARE ===
    
    # CORS para API-First
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # === ROUTERS ===
    
    # API v1 (prioritario)
    app.include_router(api_router, prefix="/api/v1")
    
    # TODO: Web routes (temporal, hasta migrar frontend)
    # app.include_router(web_router)
    
    return app


# Crear instancia de la aplicación
app = create_app()


# === ROOT ENDPOINTS ===

@app.get("/")
async def root():
    """Endpoint raíz con información de la API"""
    return {
        "message": "Sistema de Facturas API v2.0",
        "version": settings.VERSION,
        "docs": "/docs",
        "api": "/api/v1",
        "health": "/api/v1/health"
    }