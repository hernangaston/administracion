# app/domain/entities/factura.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class Factura(BaseModel):
    """Entidad de dominio para Factura"""
    id: Optional[int] = None
    filename: str
    razon_social: Optional[str] = None
    cuit_proveedor: Optional[str] = None
    numero_factura: Optional[str] = None
    fecha_factura: Optional[datetime] = None
    fecha_vencimiento: Optional[datetime] = None
    tipo_factura: Optional[str] = None
    subtotal: Optional[Decimal] = None
    iva: Optional[Decimal] = None
    total: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    procesado_por: Optional[str] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            Decimal: lambda v: float(v) if v else None
        }


class FacturaCreate(BaseModel):
    """DTO para crear factura"""
    filename: str
    entities: dict
    procesado_por: str


class FacturaUpdate(BaseModel):
    """DTO para actualizar factura"""
    razon_social: Optional[str] = None
    cuit_proveedor: Optional[str] = None
    numero_factura: Optional[str] = None
    fecha_factura: Optional[datetime] = None
    fecha_vencimiento: Optional[datetime] = None
    tipo_factura: Optional[str] = None
    subtotal: Optional[Decimal] = None
    iva: Optional[Decimal] = None
    total: Optional[Decimal] = None


class FacturaResponse(BaseModel):
    """DTO para respuesta API"""
    id: int
    filename: str
    razon_social: Optional[str]
    cuit_proveedor: Optional[str]
    numero_factura: Optional[str]
    total: Optional[Decimal]
    total_formateado: str
    estado: str
    created_at: datetime
    
    @classmethod
    def from_entity(cls, factura: Factura) -> "FacturaResponse":
        """Crear response desde entidad"""
        total_fmt = f"${factura.total or 0:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        estado = "completo" if factura.razon_social and factura.total else "parcial"
        
        return cls(
            id=factura.id,
            filename=factura.filename,
            razon_social=factura.razon_social,
            cuit_proveedor=factura.cuit_proveedor,
            numero_factura=factura.numero_factura,
            total=factura.total,
            total_formateado=total_fmt,
            estado=estado,
            created_at=factura.created_at
        )


class FacturaFilter(BaseModel):
    """Filtros para búsqueda de facturas"""
    razon_social: Optional[str] = None
    cuit_proveedor: Optional[str] = None
    fecha_desde: Optional[datetime] = None
    fecha_hasta: Optional[datetime] = None
    total_min: Optional[Decimal] = None
    total_max: Optional[Decimal] = None
    limit: int = Field(default=50, le=100)
    offset: int = Field(default=0, ge=0)