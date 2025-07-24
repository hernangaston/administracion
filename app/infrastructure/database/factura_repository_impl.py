# app/infrastructure/database/factura_repository_impl.py
from typing import List, Optional
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal
import logging

from app.domain.repositories.factura_repository import FacturaRepository
from app.domain.entities.factura import Factura, FacturaCreate, FacturaUpdate, FacturaFilter
from app.infrastructure.database.models import FacturaModel
from app.shared.exceptions.business import ValidationError

logger = logging.getLogger(__name__)


class SQLiteFacturaRepository(FacturaRepository):
    """Implementación SQLite async del repositorio de facturas"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, factura_data: FacturaCreate) -> int:
        """Crear nueva factura desde entidades extraídas"""
        
        # Mapear entidades a campos de factura
        mapped_data = self._map_entities_to_factura(factura_data.entities)
        
        # Crear modelo
        factura_model = FacturaModel(
            filename=factura_data.filename,
            procesado_por=factura_data.procesado_por,
            **mapped_data
        )
        
        self.session.add(factura_model)
        await self.session.flush()  # Para obtener el ID
        
        logger.info(f"Factura creada: ID={factura_model.id}, filename={factura_data.filename}")
        return factura_model.id
    
    async def get_by_id(self, factura_id: int) -> Optional[Factura]:
        """Obtener factura por ID"""
        
        stmt = select(FacturaModel).where(FacturaModel.id == factura_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        return self._model_to_entity(model) if model else None
    
    async def get_by_user(self, user_id: str, filters: Optional[FacturaFilter] = None) -> List[Factura]:
        """Obtener facturas del usuario con filtros"""
        
        # Base query
        stmt = select(FacturaModel).where(FacturaModel.procesado_por == user_id)
        
        # Aplicar filtros
        if filters:
            stmt = self._apply_filters(stmt, filters)
        
        # Ordenar por fecha más reciente
        stmt = stmt.order_by(FacturaModel.created_at.desc())
        
        # Aplicar limit y offset
        if filters:
            stmt = stmt.offset(filters.offset).limit(filters.limit)
        else:
            stmt = stmt.limit(50)  # Default limit
        
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        
        return [self._model_to_entity(model) for model in models]
    
    async def update(self, factura_id: int, factura_data: FacturaUpdate) -> bool:
        """Actualizar factura"""
        
        # Preparar datos para actualizar (solo campos no None)
        update_data = {
            k: v for k, v in factura_data.dict(exclude_unset=True).items() 
            if v is not None
        }
        
        if not update_data:
            return True  # Nada que actualizar
        
        stmt = (
            update(FacturaModel)
            .where(FacturaModel.id == factura_id)
            .values(**update_data)
        )
        
        result = await self.session.execute(stmt)
        return result.rowcount > 0
    
    async def delete(self, factura_id: int) -> bool:
        """Eliminar factura"""
        
        stmt = delete(FacturaModel).where(FacturaModel.id == factura_id)
        result = await self.session.execute(stmt)
        return result.rowcount > 0
    
    async def get_all(self, filters: Optional[FacturaFilter] = None) -> List[Factura]:
        """Obtener todas las facturas (admin)"""
        
        stmt = select(FacturaModel)
        
        if filters:
            stmt = self._apply_filters(stmt, filters)
        
        stmt = stmt.order_by(FacturaModel.created_at.desc())
        
        if filters:
            stmt = stmt.offset(filters.offset).limit(filters.limit)
        else:
            stmt = stmt.limit(100)  # Default limit para admin
        
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        
        return [self._model_to_entity(model) for model in models]
    
    async def get_by_cuit(self, cuit: str) -> List[Factura]:
        """Obtener facturas por CUIT"""
        
        stmt = (
            select(FacturaModel)
            .where(FacturaModel.cuit_proveedor == cuit)
            .order_by(FacturaModel.created_at.desc())
        )
        
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        
        return [self._model_to_entity(model) for model in models]
    
    async def count_by_user(self, user_id: str) -> int:
        """Contar facturas del usuario"""
        
        stmt = select(func.count(FacturaModel.id)).where(FacturaModel.procesado_por == user_id)
        result = await self.session.execute(stmt)
        return result.scalar() or 0
    
    def _apply_filters(self, stmt, filters: FacturaFilter):
        """Aplicar filtros a la query"""
        
        if filters.razon_social:
            stmt = stmt.where(FacturaModel.razon_social.ilike(f"%{filters.razon_social}%"))
        
        if filters.cuit_proveedor:
            stmt = stmt.where(FacturaModel.cuit_proveedor == filters.cuit_proveedor)
        
        if filters.fecha_desde:
            stmt = stmt.where(FacturaModel.fecha_factura >= filters.fecha_desde)
        
        if filters.fecha_hasta:
            stmt = stmt.where(FacturaModel.fecha_factura <= filters.fecha_hasta)
        
        if filters.total_min:
            stmt = stmt.where(FacturaModel.total >= filters.total_min)
        
        if filters.total_max:
            stmt = stmt.where(FacturaModel.total <= filters.total_max)
        
        return stmt
    
    def _model_to_entity(self, model: FacturaModel) -> Factura:
        """Convertir modelo SQLAlchemy a entidad de dominio"""
        
        return Factura(
            id=model.id,
            filename=model.filename,
            razon_social=model.razon_social,
            cuit_proveedor=model.cuit_proveedor,
            numero_factura=model.numero_factura,
            fecha_factura=model.fecha_factura,
            fecha_vencimiento=model.fecha_vencimiento,
            tipo_factura=model.tipo_factura,
            subtotal=model.subtotal,
            iva=model.iva,
            total=model.total,
            created_at=model.created_at,
            updated_at=model.updated_at,
            procesado_por=model.procesado_por
        )
    
    def _map_entities_to_factura(self, entities: dict) -> dict:
        """Mapear entidades de Document AI a campos de factura"""
        
        return {
            "razon_social": entities.get("supplier_name"),
            "cuit_proveedor": self._clean_cuit(entities.get("supplier_tax_id")),
            "numero_factura": entities.get("invoice_id"),
            "fecha_factura": self._parse_date(entities.get("invoice_date")),
            "fecha_vencimiento": self._parse_date(entities.get("due_date")),
            "tipo_factura": entities.get("invoice_type"),
            "subtotal": self._parse_decimal(entities.get("net_amount")),
            "iva": self._parse_decimal(entities.get("total_tax_amount")),
            "total": self._parse_decimal(entities.get("total_amount")),
        }
    
    def _clean_cuit(self, cuit_raw: str) -> Optional[str]:
        """Limpiar CUIT extraído"""
        if not cuit_raw:
            return None
        
        # Extraer solo dígitos
        digits = ''.join(filter(str.isdigit, str(cuit_raw)))
        
        # Validar longitud
        if len(digits) == 11:
            return digits
        elif len(digits) > 11:
            logger.warning(f"CUIT con más de 11 dígitos: {cuit_raw}")
            return digits[:11]
        else:
            logger.warning(f"CUIT incompleto: {cuit_raw}")
            return digits if digits else None
    
    def _parse_decimal(self, value) -> Optional[Decimal]:
        """Parsear valor monetario"""
        if not value:
            return None
        
        try:
            # Limpiar formato argentino
            clean_value = str(value).replace('$', '').replace(' ', '')
            if ',' in clean_value and '.' in clean_value:
                clean_value = clean_value.replace('.', '').replace(',', '.')
            elif ',' in clean_value:
                clean_value = clean_value.replace(',', '.')
            
            return Decimal(clean_value)
        except Exception as e:
            logger.warning(f"Error parseando decimal '{value}': {e}")
            return None
    
    def _parse_date(self, date_str) -> Optional:
        """Parsear fecha - placeholder por ahora"""
        # TODO: Implementar parsing robusto de fechas
        # Por ahora retornar None, se implementará en siguiente iteración
        return None