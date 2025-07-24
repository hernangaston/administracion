# app/infrastructure/database/models.py
from sqlalchemy import Column, Integer, String, Text, DateTime, Numeric, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class FacturaModel(Base):
    """Modelo SQLAlchemy para facturas"""
    __tablename__ = "facturas"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    razon_social = Column(String(255), nullable=True)
    cuit_proveedor = Column(String(13), nullable=True, index=True)  # XX-XXXXXXXX-X
    numero_factura = Column(String(50), nullable=True)
    fecha_factura = Column(DateTime, nullable=True)
    fecha_vencimiento = Column(DateTime, nullable=True)
    tipo_factura = Column(String(50), nullable=True)
    subtotal = Column(Numeric(15, 2), nullable=True)
    iva = Column(Numeric(15, 2), nullable=True)
    total = Column(Numeric(15, 2), nullable=True, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    procesado_por = Column(String(50), nullable=True, index=True)
    
    def __repr__(self):
        return f"<Factura(id={self.id}, filename='{self.filename}', total={self.total})>"


class UsuarioModel(Base):
    """Modelo SQLAlchemy para usuarios (migración del auth actual)"""
    __tablename__ = "usuarios"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="cliente", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    cuit_asociado = Column(String(13), nullable=True, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Usuario(id={self.id}, username='{self.username}', role='{self.role}')>"


class RefreshTokenModel(Base):
    """Modelo SQLAlchemy para refresh tokens"""
    __tablename__ = "refresh_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    token_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<RefreshToken(id={self.id}, user_id={self.user_id})>"