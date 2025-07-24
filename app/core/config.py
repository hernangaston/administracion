# app/core/config.py
from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    """Configuración centralizada de la aplicación"""
    OPENAI_API_KEY: Optional[str] = None
    
    # App
    APP_NAME: str = "Sistema de Facturas API"
    VERSION: str = "2.0.0"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./database.db"
    DATABASE_ECHO: bool = False
    
    # Document AI
    DOCAI_PROJECT_ID: str
    DOCAI_LOCATION: str = "us"
    DOCAI_PROCESSOR_ID: str
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    
    # Auth
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS para API-First
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",  # React dev
        "http://localhost:8080",  # Vue dev
        "http://localhost:5173",  # Vite dev
    ]
    
    # Redis/Cache
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL: int = 300  # 5 minutos
    
    # File Upload
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_FILE_TYPES: List[str] = [".pdf"]
    MAX_FILES_PER_UPLOAD: int = 10
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    # Microservices (futuro)
    SERVICE_NAME: str = "factura-service"
    SERVICE_VERSION: str = "1.0.0"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Instancia global
settings = Settings()


def setup_google_credentials():
    """Configurar credenciales de Google"""
    if settings.GOOGLE_APPLICATION_CREDENTIALS:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.GOOGLE_APPLICATION_CREDENTIALS