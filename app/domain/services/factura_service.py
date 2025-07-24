# app/domain/services/factura_service.py
from typing import List, Optional
from fastapi import UploadFile

from app.domain.entities.factura import (
    Factura, FacturaCreate, FacturaUpdate, FacturaResponse, FacturaFilter
)
from app.domain.repositories.factura_repository import FacturaRepository
from app.domain.services.document_service import DocumentProcessor
from app.shared.exceptions.business import (
    ProcessingError, FacturaNotFoundError, ValidationError, InvalidFileError
)


class FacturaService:
    """Servicio de dominio para gestión de facturas"""
    
    def __init__(
        self,
        factura_repo: FacturaRepository,
        document_processor: DocumentProcessor
    ):
        self._repo = factura_repo
        self._document_processor = document_processor
    
    async def process_files(
        self, 
        files: List[UploadFile], 
        user_id: str
    ) -> List[FacturaResponse]:
        """Procesar múltiples archivos PDF"""
        
        if not files:
            raise ValidationError("No se proporcionaron archivos")
        
        if len(files) > 10:  # TODO: mover a config
            raise ValidationError("Máximo 10 archivos por vez")
        
        results = []
        errors = []
        
        for file in files:
            try:
                result = await self._process_single_file(file, user_id)
                results.append(result)
            except Exception as e:
                errors.append(f"{file.filename}: {str(e)}")
        
        if errors and not results:
            raise ProcessingError(f"Todos los archivos fallaron: {'; '.join(errors)}")
        
        return results
    
    async def _process_single_file(self, file: UploadFile, user_id: str) -> FacturaResponse:
        """Procesar un solo archivo"""
        
        # Validar tipo de archivo
        if not file.filename.lower().endswith('.pdf'):
            raise InvalidFileError(file.filename, "Solo se permiten archivos PDF")
        
        # Procesar con Document AI
        entities = await self._document_processor.process_file(file)
        
        # Crear factura
        factura_data = FacturaCreate(
            filename=file.filename,
            entities=entities,
            procesado_por=user_id
        )
        
        # Guardar en BD
        factura_id = await self._repo.create(factura_data)
        factura = await self._repo.get_by_id(factura_id)
        
        if not factura:
            raise ProcessingError(f"Error guardando factura: {file.filename}")
        
        return FacturaResponse.from_entity(factura)
    
    async def get_facturas(
        self, 
        user_id: str, 
        filters: Optional[FacturaFilter] = None
    ) -> List[FacturaResponse]:
        """Obtener facturas del usuario"""
        
        facturas = await self._repo.get_by_user(user_id, filters)
        return [FacturaResponse.from_entity(f) for f in facturas]
    
    async def get_factura_by_id(self, factura_id: int, user_id: str) -> FacturaResponse:
        """Obtener factura específica con verificación de permisos"""
        
        factura = await self._repo.get_by_id(factura_id)
        
        if not factura:
            raise FacturaNotFoundError(factura_id)
        
        # TODO: Verificar permisos según rol de usuario
        # if not self._can_access_factura(user_id, factura):
        #     raise UnauthorizedAccessError("factura", user_id)
        
        return FacturaResponse.from_entity(factura)
    
    async def update_factura(
        self, 
        factura_id: int, 
        update_data: FacturaUpdate, 
        user_id: str
    ) -> FacturaResponse:
        """Actualizar factura"""
        
        # Verificar que existe
        existing = await self._repo.get_by_id(factura_id)
        if not existing:
            raise FacturaNotFoundError(factura_id)
        
        # TODO: Verificar permisos
        
        # Actualizar
        success = await self._repo.update(factura_id, update_data)
        if not success:
            raise ProcessingError(f"Error actualizando factura {factura_id}")
        
        # Retornar actualizada
        updated_factura = await self._repo.get_by_id(factura_id)
        return FacturaResponse.from_entity(updated_factura)
    
    async def delete_factura(self, factura_id: int, user_id: str) -> bool:
        """Eliminar factura"""
        
        # Verificar que existe
        existing = await self._repo.get_by_id(factura_id)
        if not existing:
            raise FacturaNotFoundError(factura_id)
        
        # TODO: Verificar permisos
        
        return await self._repo.delete(factura_id)