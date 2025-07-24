# app/infrastructure/database/connection.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.infrastructure.database.models import Base

logger = logging.getLogger(__name__)

# Engine async global
engine = None
async_session_maker = None


async def init_database():
    """Inicializar base de datos async"""
    global engine, async_session_maker
    
    logger.info(f"Inicializando base de datos: {settings.DATABASE_URL}")
    
    # Crear engine async
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        poolclass=StaticPool,  # Para SQLite
        connect_args={
            "check_same_thread": False,  # Para SQLite async
        },
        future=True
    )
    
    # Crear session maker
    async_session_maker = async_sessionmaker(
        engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    # Crear tablas
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("✅ Base de datos inicializada correctamente")


async def get_async_session() -> AsyncSession:
    """Dependency para obtener sesión async"""
    if not async_session_maker:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    async with async_session_maker() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_session():
    """Context manager para sesiones manuales"""
    if not async_session_maker:
        raise RuntimeError("Database not initialized")
    
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_database():
    """Cerrar conexiones de base de datos"""
    global engine
    if engine:
        await engine.dispose()
        logger.info("✅ Base de datos cerrada correctamente")