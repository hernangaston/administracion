# app/domain/repositories/factura_repository.py
from abc import ABC, abstractmethod
from typing import List, Optional

from app.domain.entities.factura import Factura, FacturaCreate, FacturaUpdate, FacturaFilter


class FacturaRepository(ABC):
    """Interface para persistencia de facturas"""
    
    @abstractmethod
    async def create(self, factura_data: FacturaCreate) -> int:
        """Crear nueva factura"""
        pass
    
    @abstractmethod
    async def get_by_id(self, factura_id: int) -> Optional[Factura]:
        """Obtener factura por ID"""
        pass
    
    @abstractmethod
    async def get_by_user(self, user_id: str, filters: Optional[FacturaFilter] = None) -> List[Factura]:
        """Obtener facturas del usuario con filtros"""
        pass
    
    @abstractmethod
    async def update(self, factura_id: int, factura_data: FacturaUpdate) -> bool:
        """Actualizar factura"""
        pass
    
    @abstractmethod
    async def delete(self, factura_id: int) -> bool:
        """Eliminar factura"""
        pass
    
    @abstractmethod
    async def get_all(self, filters: Optional[FacturaFilter] = None) -> List[Factura]:
        """Obtener todas las facturas (admin)"""
        pass
    
    @abstractmethod
    async def get_by_cuit(self, cuit: str) -> List[Factura]:
        """Obtener facturas por CUIT"""
        pass
    
    @abstractmethod
    async def count_by_user(self, user_id: str) -> int:
        """Contar facturas del usuario"""
        pass