# -*- coding: utf-8 -*-
"""
Sistema unificado de manejo de errores para el sistema de facturas
Proporciona excepciones personalizadas, manejo centralizado y respuestas consistentes
"""

import traceback
from typing import Dict, Any, Optional, List, Union
from enum import Enum
from dataclasses import dataclass
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

class ErrorCode(Enum):
    """Códigos de error estandarizados del sistema"""
    
    # Errores generales (1000-1999)
    UNKNOWN_ERROR = "E1000"
    VALIDATION_ERROR = "E1001"
    CONFIGURATION_ERROR = "E1002"
    
    # Errores de autenticación y autorización (2000-2999)
    AUTHENTICATION_FAILED = "E2000"
    INVALID_TOKEN = "E2001"
    TOKEN_EXPIRED = "E2002"
    INSUFFICIENT_PERMISSIONS = "E2003"
    ACCOUNT_LOCKED = "E2004"
    INVALID_CREDENTIALS = "E2005"
    
    # Errores de base de datos (3000-3999)
    DATABASE_CONNECTION_ERROR = "E3000"
    DATABASE_QUERY_ERROR = "E3001"
    RECORD_NOT_FOUND = "E3002"
    DUPLICATE_RECORD = "E3003"
    CONSTRAINT_VIOLATION = "E3004"
    
    # Errores de archivos (4000-4999)
    FILE_NOT_FOUND = "E4000"
    FILE_TOO_LARGE = "E4001"
    INVALID_FILE_TYPE = "E4002"
    CORRUPTED_FILE = "E4003"
    FILE_PROCESSING_ERROR = "E4004"
    UPLOAD_ERROR = "E4005"
    
    # Errores de procesamiento de documentos (5000-5999)
    DOCUMENT_AI_ERROR = "E5000"
    PDF_PARSING_ERROR = "E5001"
    TEXT_EXTRACTION_ERROR = "E5002"
    ENTITY_EXTRACTION_ERROR = "E5003"
    
    # Errores de validación de datos (6000-6999)
    INVALID_CUIT = "E6000"
    INVALID_DATE = "E6001"
    INVALID_AMOUNT = "E6002"
    MISSING_REQUIRED_FIELD = "E6003"
    DATA_FORMAT_ERROR = "E6004"
    
    # Errores de API externa (7000-7999)
    EXTERNAL_API_ERROR = "E7000"
    NETWORK_ERROR = "E7001"
    TIMEOUT_ERROR = "E7002"
    RATE_LIMIT_EXCEEDED = "E7003"
    
    # Errores de negocio (8000-8999)
    BUSINESS_RULE_VIOLATION = "E8000"
    DUPLICATE_INVOICE = "E8001"
    INVALID_OPERATION = "E8002"

@dataclass
class ErrorDetail:
    """Detalle de error estructurado"""
    code: ErrorCode
    message: str
    field: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class FacturasException(Exception):
    """Excepción base del sistema de facturas"""
    
    def __init__(self, 
                 error_code: ErrorCode,
                 message: str,
                 details: Optional[List[ErrorDetail]] = None,
                 http_status: int = 500,
                 context: Optional[Dict[str, Any]] = None):
        
        self.error_code = error_code
        self.message = message
        self.details = details or []
        self.http_status = http_status
        self.context = context or {}
        
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte la excepción a diccionario para respuesta API"""
        return {
            "error": {
                "code": self.error_code.value,
                "message": self.message,
                "details": [
                    {
                        "code": detail.code.value,
                        "message": detail.message,
                        "field": detail.field,
                        "context": detail.context
                    } for detail in self.details
                ],
                "context": self.context
            }
        }

# Excepciones específicas del dominio

class AuthenticationError(FacturasException):
    """Error de autenticación"""
    
    def __init__(self, message: str = "Error de autenticación", 
                 error_code: ErrorCode = ErrorCode.AUTHENTICATION_FAILED,
                 context: Optional[Dict[str, Any]] = None):
        super().__init__(error_code, message, http_status=401, context=context)

class AuthorizationError(FacturasException):
    """Error de autorización"""
    
    def __init__(self, message: str = "Permisos insuficientes",
                 error_code: ErrorCode = ErrorCode.INSUFFICIENT_PERMISSIONS,
                 context: Optional[Dict[str, Any]] = None):
        super().__init__(error_code, message, http_status=403, context=context)

class ValidationError(FacturasException):
    """Error de validación"""
    
    def __init__(self, message: str = "Error de validación",
                 details: Optional[List[ErrorDetail]] = None,
                 context: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorCode.VALIDATION_ERROR, message, details, 400, context)

class DatabaseError(FacturasException):
    """Error de base de datos"""
    
    def __init__(self, message: str = "Error de base de datos",
                 error_code: ErrorCode = ErrorCode.DATABASE_QUERY_ERROR,
                 context: Optional[Dict[str, Any]] = None):
        super().__init__(error_code, message, http_status=500, context=context)

class FileProcessingError(FacturasException):
    """Error de procesamiento de archivos"""
    
    def __init__(self, message: str = "Error procesando archivo",
                 error_code: ErrorCode = ErrorCode.FILE_PROCESSING_ERROR,
                 context: Optional[Dict[str, Any]] = None):
        super().__init__(error_code, message, http_status=422, context=context)

class DocumentAIError(FacturasException):
    """Error de Document AI"""
    
    def __init__(self, message: str = "Error en procesamiento de documento",
                 error_code: ErrorCode = ErrorCode.DOCUMENT_AI_ERROR,
                 context: Optional[Dict[str, Any]] = None):
        super().__init__(error_code, message, http_status=502, context=context)

class BusinessRuleError(FacturasException):
    """Error de regla de negocio"""
    
    def __init__(self, message: str = "Violación de regla de negocio",
                 error_code: ErrorCode = ErrorCode.BUSINESS_RULE_VIOLATION,
                 context: Optional[Dict[str, Any]] = None):
        super().__init__(error_code, message, http_status=422, context=context)

# Manejador centralizado de errores

class ErrorHandler:
    """Manejador centralizado de errores"""
    
    @staticmethod
    def handle_exception(exc: Exception, request: Optional[Request] = None) -> Dict[str, Any]:
        """
        Maneja cualquier excepción y devuelve respuesta estructurada
        
        Args:
            exc: Excepción a manejar
            request: Request de FastAPI (opcional)
            
        Returns:
            Diccionario con información del error
        """
        
        # Si es una excepción del sistema, usar su información
        if isinstance(exc, FacturasException):
            error_info = exc.to_dict()
            error_info["http_status"] = exc.http_status
            
            # Log según severidad
            if exc.http_status >= 500:
                logger.error(f"Error del sistema: {exc.message}", 
                           extra={"error_code": exc.error_code.value, "context": exc.context})
            else:
                logger.warning(f"Error de usuario: {exc.message}",
                             extra={"error_code": exc.error_code.value, "context": exc.context})
            
            return error_info
        
        # Si es HTTPException de FastAPI
        elif isinstance(exc, HTTPException):
            error_info = {
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": exc.detail,
                    "details": [],
                    "context": {}
                },
                "http_status": exc.status_code
            }
            
            logger.warning(f"HTTP Error: {exc.detail}", extra={"status_code": exc.status_code})
            return error_info
        
        # Cualquier otra excepción - error interno del servidor
        else:
            error_info = {
                "error": {
                    "code": ErrorCode.UNKNOWN_ERROR.value,
                    "message": "Error interno del servidor",
                    "details": [],
                    "context": {
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc)
                    }
                },
                "http_status": 500
            }
            
            # Log completo para errores inesperados
            logger.error(f"Error inesperado: {str(exc)}", 
                        exc_info=True,
                        extra={
                            "exception_type": type(exc).__name__,
                            "request_path": request.url.path if request else None
                        })
            
            return error_info
    
    @staticmethod
    def create_http_response(error_info: Dict[str, Any]) -> JSONResponse:
        """Crea respuesta HTTP desde información de error"""
        status_code = error_info.pop("http_status", 500)
        
        return JSONResponse(
            status_code=status_code,
            content=error_info,
            headers={
                "X-Error-Code": error_info["error"]["code"],
                "X-Content-Type-Options": "nosniff"
            }
        )

# Validadores específicos

class DataValidator:
    """Validadores de datos con errores estructurados"""
    
    @staticmethod
    def validate_cuit(cuit: str, field_name: str = "cuit") -> None:
        """Valida CUIT y lanza excepción estructurada si es inválido"""
        from app_modules.utils.cuit_utils import validar_cuit_completo
        
        if not cuit:
            raise ValidationError(
                "CUIT es requerido",
                details=[ErrorDetail(
                    ErrorCode.MISSING_REQUIRED_FIELD,
                    "CUIT no puede estar vacío",
                    field=field_name
                )]
            )
        
        if not validar_cuit_completo(cuit):
            raise ValidationError(
                "CUIT inválido",
                details=[ErrorDetail(
                    ErrorCode.INVALID_CUIT,
                    f"El CUIT '{cuit}' no es válido",
                    field=field_name,
                    context={"cuit_provided": cuit}
                )]
            )
    
    @staticmethod
    def validate_amount(amount: Union[str, float, int], field_name: str = "amount") -> float:
        """Valida y convierte monto monetario"""
        if amount is None:
            raise ValidationError(
                "Monto es requerido",
                details=[ErrorDetail(
                    ErrorCode.MISSING_REQUIRED_FIELD,
                    "Monto no puede estar vacío",
                    field=field_name
                )]
            )
        
        try:
            # Convertir a float
            if isinstance(amount, str):
                # Limpiar formato argentino
                cleaned = amount.replace('$', '').replace(' ', '').replace('.', '').replace(',', '.')
                amount_float = float(cleaned)
            else:
                amount_float = float(amount)
            
            # Validar rango razonable
            if amount_float < 0:
                raise ValidationError(
                    "Monto no puede ser negativo",
                    details=[ErrorDetail(
                        ErrorCode.INVALID_AMOUNT,
                        f"El monto {amount_float} no puede ser negativo",
                        field=field_name
                    )]
                )
            
            if amount_float > 999999999.99:  # 999 millones máximo
                raise ValidationError(
                    "Monto demasiado grande",
                    details=[ErrorDetail(
                        ErrorCode.INVALID_AMOUNT,
                        f"El monto {amount_float} excede el límite máximo",
                        field=field_name
                    )]
                )
            
            return amount_float
            
        except (ValueError, TypeError) as e:
            raise ValidationError(
                "Formato de monto inválido",
                details=[ErrorDetail(
                    ErrorCode.DATA_FORMAT_ERROR,
                    f"No se pudo convertir '{amount}' a número",
                    field=field_name,
                    context={"original_value": str(amount), "error": str(e)}
                )]
            )
    
    @staticmethod
    def validate_date(date_value: str, field_name: str = "date") -> str:
        """Valida fecha usando el sistema unificado de fechas"""
        from app_modules.utils.date_utils import DateFormatter
        
        if not date_value:
            raise ValidationError(
                "Fecha es requerida",
                details=[ErrorDetail(
                    ErrorCode.MISSING_REQUIRED_FIELD,
                    "Fecha no puede estar vacía",
                    field=field_name
                )]
            )
        
        parsed_date = DateFormatter.parsear_fecha(date_value)
        if not parsed_date:
            raise ValidationError(
                "Fecha inválida",
                details=[ErrorDetail(
                    ErrorCode.INVALID_DATE,
                    f"No se pudo parsear la fecha '{date_value}'",
                    field=field_name,
                    context={"original_value": date_value}
                )]
            )
        
        return DateFormatter.formatear_para_bd(parsed_date)

# Decoradores para manejo de errores

def handle_errors(convert_to_http: bool = True):
    """
    Decorador para manejo automático de errores en funciones
    
    Args:
        convert_to_http: Si True, convierte excepciones a HTTPException
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except FacturasException:
                # Re-lanzar excepciones del sistema sin modificar
                raise
            except Exception as e:
                # Convertir a excepción del sistema
                logger.error(f"Error inesperado en {func.__name__}: {str(e)}", exc_info=True)
                
                if convert_to_http:
                    error_info = ErrorHandler.handle_exception(e)
                    raise HTTPException(
                        status_code=error_info["http_status"],
                        detail=error_info["error"]["message"]
                    )
                else:
                    raise FacturasException(
                        ErrorCode.UNKNOWN_ERROR,
                        f"Error inesperado en {func.__name__}: {str(e)}",
                        context={"function": func.__name__, "original_error": str(e)}
                    )
        
        return wrapper
    return decorator

def validate_input(**validators):
    """
    Decorador para validación automática de inputs
    
    Usage:
        @validate_input(cuit=DataValidator.validate_cuit, amount=DataValidator.validate_amount)
        def process_invoice(cuit: str, amount: str):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Validar argumentos con nombre
            for param_name, validator in validators.items():
                if param_name in kwargs:
                    try:
                        if callable(validator):
                            kwargs[param_name] = validator(kwargs[param_name], param_name)
                    except FacturasException:
                        raise
                    except Exception as e:
                        raise ValidationError(
                            f"Error validando {param_name}",
                            details=[ErrorDetail(
                                ErrorCode.VALIDATION_ERROR,
                                str(e),
                                field=param_name
                            )]
                        )
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

# Funciones de utilidad

def create_validation_error(field: str, message: str, 
                          error_code: ErrorCode = ErrorCode.VALIDATION_ERROR) -> ValidationError:
    """Función de conveniencia para crear errores de validación"""
    return ValidationError(
        f"Error en campo {field}",
        details=[ErrorDetail(error_code, message, field=field)]
    )

def log_and_raise_error(error_code: ErrorCode, message: str, 
                       exc_class: type = FacturasException,
                       context: Optional[Dict[str, Any]] = None,
                       original_exception: Optional[Exception] = None):
    """Log y lanza error de manera consistente"""
    
    # Log del error
    extra = {"error_code": error_code.value, "context": context}
    if original_exception:
        logger.error(f"{message}: {str(original_exception)}", extra=extra, exc_info=True)
    else:
        logger.error(message, extra=extra)
    
    # Lanzar excepción
    raise exc_class(error_code, message, context=context)