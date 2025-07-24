# app/core/dependencies.py
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.infrastructure.database.connection import get_async_session
from app.infrastructure.database.factura_repository_impl import SQLiteFacturaRepository
from app.infrastructure.document_ai.google_processor import GoogleDocumentProcessor
from app.domain.services.document_service import DocumentProcessor
from app.domain.services.factura_service import FacturaService

logger = logging.getLogger(__name__)

# Singleton instances
_document_processor_instance = None
_google_processor_instance = None


async def setup_dependencies():
    """Setup de dependencias al iniciar la aplicación"""
    global _google_processor_instance, _document_processor_instance
    
    logger.info("🔧 Configurando dependencias...")
    
    # Inicializar Google Document AI
    _google_processor_instance = GoogleDocumentProcessor()
    _document_processor_instance = DocumentProcessor(_google_processor_instance)
    
    logger.info("✅ Dependencias configuradas correctamente")


# === DEPENDENCY PROVIDERS ===

async def get_factura_repository(
    session: AsyncSession = Depends(get_async_session)
) -> SQLiteFacturaRepository:
    """Dependency para obtener repositorio de facturas"""
    return SQLiteFacturaRepository(session)


async def get_document_processor() -> DocumentProcessor:
    """Dependency para obtener procesador de documentos"""
    if not _document_processor_instance:
        raise RuntimeError("Document processor not initialized. Call setup_dependencies() first.")
    return _document_processor_instance


async def get_factura_service(
    factura_repo: SQLiteFacturaRepository = Depends(get_factura_repository),
    document_processor: DocumentProcessor = Depends(get_document_processor)
) -> FacturaService:
    """Dependency para obtener servicio de facturas"""
    return FacturaService(factura_repo, document_processor)


# === AUTH DEPENDENCIES (temporal, hasta migrar auth completo) ===

class CurrentUser:
    """Modelo temporal para usuario actual"""
    def __init__(self, id: str, username: str, role: str):
        self.id = id
        self.username = username
        self.role = role


async def get_current_user() -> CurrentUser:
    """
    Dependency temporal para obtener usuario actual
    TODO: Integrar con sistema de auth existente
    """
    # Por ahora retornar usuario mock para testing
    # En la siguiente fase se integrará con el auth actual
    return CurrentUser(id="admin", username="admin", role="admin")


# === UTILITY DEPENDENCIES ===

async def common_parameters(limit: int = 50, offset: int = 0):
    """Parámetros comunes para paginación"""
    return {"limit": min(limit, 100), "offset": max(offset, 0)}