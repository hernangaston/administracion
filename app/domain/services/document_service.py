# app/domain/services/document_service.py
from abc import ABC, abstractmethod
from typing import Dict, Any
from fastapi import UploadFile

from app.shared.exceptions.business import ProcessingError, DocumentAIError


class DocumentService(ABC):
    """Interface para procesamiento de documentos"""
    
    @abstractmethod
    async def extract_entities(self, file: UploadFile) -> Dict[str, Any]:
        """Extraer entidades de un archivo PDF"""
        pass
    
    @abstractmethod
    async def validate_file(self, file: UploadFile) -> bool:
        """Validar que el archivo sea procesable"""
        pass


class DocumentProcessor:
    """Procesador concreto de documentos (será implementado en infrastructure)"""
    
    def __init__(self, document_service: DocumentService):
        self._document_service = document_service
    
    async def process_file(self, file: UploadFile) -> Dict[str, Any]:
        """Procesar archivo completo con validaciones"""
        
        # Validar archivo
        if not await self._document_service.validate_file(file):
            raise ProcessingError(f"Archivo inválido: {file.filename}")
        
        try:
            # Extraer entidades
            entities = await self._document_service.extract_entities(file)
            
            if not entities:
                raise ProcessingError(f"No se pudieron extraer datos de: {file.filename}")
            
            return entities
            
        except DocumentAIError as e:
            raise ProcessingError(f"Error procesando {file.filename}: {e.message}")
        except Exception as e:
            raise ProcessingError(f"Error inesperado procesando {file.filename}: {str(e)}")