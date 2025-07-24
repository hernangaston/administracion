# app/shared/exceptions/business.py
from typing import Optional, Dict, Any


class BusinessException(Exception):
    """Excepción base para errores de negocio"""
    def __init__(self, message: str, code: str = "BUSINESS_ERROR", details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)


class ValidationError(BusinessException):
    """Error de validación de datos"""
    def __init__(self, message: str, field: str = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "VALIDATION_ERROR", details)
        self.field = field


class ProcessingError(BusinessException):
    """Error durante procesamiento de documentos"""
    def __init__(self, message: str, filename: str = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "PROCESSING_ERROR", details)
        self.filename = filename


class DocumentAIError(BusinessException):
    """Error en Google Document AI"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "DOCUMENT_AI_ERROR", details)


class FacturaNotFoundError(BusinessException):
    """Factura no encontrada"""
    def __init__(self, factura_id: int):
        super().__init__(f"Factura con ID {factura_id} no encontrada", "FACTURA_NOT_FOUND")
        self.factura_id = factura_id


class UnauthorizedAccessError(BusinessException):
    """Acceso no autorizado a recurso"""
    def __init__(self, resource: str, user_id: str = None):
        super().__init__(f"Acceso no autorizado a {resource}", "UNAUTHORIZED_ACCESS")
        self.resource = resource
        self.user_id = user_id


class InvalidFileError(BusinessException):
    """Archivo inválido"""
    def __init__(self, filename: str, reason: str):
        super().__init__(f"Archivo inválido {filename}: {reason}", "INVALID_FILE")
        self.filename = filename
        self.reason = reason