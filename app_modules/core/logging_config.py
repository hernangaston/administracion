# -*- coding: utf-8 -*-
"""
Sistema de logging estructurado para el sistema de facturas
Proporciona logging JSON, rotación de archivos, y contexto enriquecido
"""

import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import traceback
from contextvars import ContextVar

# Variables de contexto para tracking de requests
request_id_var: ContextVar[str] = ContextVar('request_id', default='')
user_id_var: ContextVar[str] = ContextVar('user_id', default='')

class JSONFormatter(logging.Formatter):
    """Formatter para logs estructurados en JSON"""
    
    def format(self, record):
        # Información básica del log
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'process': record.process
        }
        
        # Agregar contexto de request si existe
        request_id = request_id_var.get()
        if request_id:
            log_entry['request_id'] = request_id
        
        user_id = user_id_var.get()
        if user_id:
            log_entry['user_id'] = user_id
        
        # Agregar información adicional del record
        if hasattr(record, 'extra_data'):
            log_entry['extra_data'] = record.extra_data
            
        if hasattr(record, 'user_action'):
            log_entry['user_action'] = record.user_action
            
        if hasattr(record, 'ip_address'):
            log_entry['ip_address'] = record.ip_address
            
        if hasattr(record, 'duration_ms'):
            log_entry['duration_ms'] = record.duration_ms
        
        # Manejo especial para excepciones
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_entry, ensure_ascii=False, default=str)

class ColoredConsoleFormatter(logging.Formatter):
    """Formatter con colores para consola de desarrollo"""
    
    # Códigos de color ANSI
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Verde
        'WARNING': '\033[33m',  # Amarillo
        'ERROR': '\033[31m',    # Rojo
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Formato: [TIMESTAMP] LEVEL - LOGGER - MESSAGE
        formatted = f"{color}[{datetime.now().strftime('%H:%M:%S')}] {record.levelname:8s}{reset} - {record.name:20s} - {record.getMessage()}"
        
        # Agregar contexto si existe
        context_parts = []
        request_id = request_id_var.get()
        if request_id:
            context_parts.append(f"req:{request_id[:8]}")
        
        user_id = user_id_var.get()
        if user_id:
            context_parts.append(f"user:{user_id}")
        
        if context_parts:
            formatted += f" [{', '.join(context_parts)}]"
        
        return formatted

class SystemLogger:
    """Configurador central del sistema de logging"""
    
    def __init__(self, log_dir: str = "logs", app_name: str = "facturas"):
        self.log_dir = Path(log_dir)
        self.app_name = app_name
        self.log_dir.mkdir(exist_ok=True)
        
        # Configurar loggers específicos
        self.setup_root_logger()
        self.setup_application_logger()
        self.setup_security_logger()
        self.setup_audit_logger()
        self.setup_performance_logger()
        
    def setup_root_logger(self):
        """Configurar logger raíz"""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Limpiar handlers existentes
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Handler para consola (desarrollo)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(ColoredConsoleFormatter())
        root_logger.addHandler(console_handler)
        
        # Handler para archivo general
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / f"{self.app_name}.log",
            maxBytes=50*1024*1024,  # 50MB
            backupCount=10
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)
        
    def setup_application_logger(self):
        """Logger para eventos de aplicación"""
        app_logger = logging.getLogger(f"{self.app_name}.app")
        
        handler = logging.handlers.RotatingFileHandler(
            self.log_dir / f"{self.app_name}_app.log",
            maxBytes=20*1024*1024,  # 20MB
            backupCount=5
        )
        handler.setFormatter(JSONFormatter())
        app_logger.addHandler(handler)
        app_logger.setLevel(logging.INFO)
        
    def setup_security_logger(self):
        """Logger para eventos de seguridad"""
        security_logger = logging.getLogger(f"{self.app_name}.security")
        
        # Archivo separado para seguridad (crítico)
        handler = logging.handlers.RotatingFileHandler(
            self.log_dir / f"{self.app_name}_security.log",
            maxBytes=100*1024*1024,  # 100MB para seguridad
            backupCount=20
        )
        handler.setFormatter(JSONFormatter())
        security_logger.addHandler(handler)
        security_logger.setLevel(logging.INFO)
        security_logger.propagate = False  # No propagar al root
        
    def setup_audit_logger(self):
        """Logger para auditoría de acciones de usuario"""
        audit_logger = logging.getLogger(f"{self.app_name}.audit")
        
        handler = logging.handlers.RotatingFileHandler(
            self.log_dir / f"{self.app_name}_audit.log",
            maxBytes=50*1024*1024,  # 50MB
            backupCount=15
        )
        handler.setFormatter(JSONFormatter())
        audit_logger.addHandler(handler)
        audit_logger.setLevel(logging.INFO)
        audit_logger.propagate = False
        
    def setup_performance_logger(self):
        """Logger para métricas de rendimiento"""
        perf_logger = logging.getLogger(f"{self.app_name}.performance")
        
        handler = logging.handlers.RotatingFileHandler(
            self.log_dir / f"{self.app_name}_performance.log",
            maxBytes=30*1024*1024,  # 30MB
            backupCount=10
        )
        handler.setFormatter(JSONFormatter())
        perf_logger.addHandler(handler)
        perf_logger.setLevel(logging.INFO)
        perf_logger.propagate = False

# Instancia global del sistema de logging
_system_logger: Optional[SystemLogger] = None

def setup_logging(log_dir: str = "logs", app_name: str = "facturas") -> SystemLogger:
    """
    Configurar el sistema de logging global
    
    Args:
        log_dir: Directorio para archivos de log
        app_name: Nombre de la aplicación
        
    Returns:
        Instancia del SystemLogger configurado
    """
    global _system_logger
    _system_logger = SystemLogger(log_dir, app_name)
    
    # Configurar loggers de terceros para reducir ruido
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('google').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    return _system_logger

def get_logger(name: str) -> logging.Logger:
    """
    Obtener logger con nombre específico
    
    Args:
        name: Nombre del logger (ej: 'auth', 'db', 'api')
        
    Returns:
        Logger configurado
    """
    return logging.getLogger(f"facturas.{name}")

# Loggers especializados
def get_security_logger() -> logging.Logger:
    """Logger para eventos de seguridad"""
    return logging.getLogger("facturas.security")

def get_audit_logger() -> logging.Logger:
    """Logger para auditoría"""
    return logging.getLogger("facturas.audit")

def get_performance_logger() -> logging.Logger:
    """Logger para métricas de rendimiento"""
    return logging.getLogger("facturas.performance")

# Funciones de contexto para tracking
def set_request_context(request_id: str, user_id: str = ""):
    """Establecer contexto de request para logging"""
    request_id_var.set(request_id)
    if user_id:
        user_id_var.set(user_id)

def clear_request_context():
    """Limpiar contexto de request"""
    request_id_var.set("")
    user_id_var.set("")

# Decoradores para logging automático
def log_function_call(logger_name: str = "app"):
    """Decorador para loggear llamadas a funciones"""
    def decorator(func):
        logger = get_logger(logger_name)
        
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            logger.info(f"Iniciando {func.__name__}", extra={
                'user_action': 'function_call',
                'function': func.__name__,
                'args_count': len(args),
                'kwargs_count': len(kwargs)
            })
            
            try:
                result = func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds() * 1000
                
                logger.info(f"Completado {func.__name__}", extra={
                    'user_action': 'function_completed',
                    'function': func.__name__,
                    'duration_ms': duration,
                    'success': True
                })
                
                return result
                
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds() * 1000
                
                logger.error(f"Error en {func.__name__}: {str(e)}", extra={
                    'user_action': 'function_error',
                    'function': func.__name__,
                    'duration_ms': duration,
                    'success': False,
                    'error_type': type(e).__name__
                }, exc_info=True)
                
                raise
                
        return wrapper
    return decorator

def log_user_action(action: str, logger_name: str = "audit"):
    """Decorador para loggear acciones de usuario"""
    def decorator(func):
        logger = get_logger(logger_name)
        
        def wrapper(*args, **kwargs):
            user_id = user_id_var.get()
            request_id = request_id_var.get()
            
            logger.info(f"Acción de usuario: {action}", extra={
                'user_action': action,
                'function': func.__name__,
                'user_id': user_id,
                'request_id': request_id
            })
            
            return func(*args, **kwargs)
            
        return wrapper
    return decorator

# Funciones de conveniencia para logging específico
def log_security_event(event_type: str, details: Dict[str, Any], 
                      severity: str = "info", user_id: str = "", ip_address: str = ""):
    """Log de evento de seguridad"""
    security_logger = get_security_logger()
    
    extra_data = {
        'event_type': event_type,
        'details': details,
        'severity': severity,
        'user_id': user_id or user_id_var.get(),
        'ip_address': ip_address
    }
    
    if severity == "critical":
        security_logger.critical(f"Evento crítico de seguridad: {event_type}", extra=extra_data)
    elif severity == "error":
        security_logger.error(f"Error de seguridad: {event_type}", extra=extra_data)
    elif severity == "warning":
        security_logger.warning(f"Advertencia de seguridad: {event_type}", extra=extra_data)
    else:
        security_logger.info(f"Evento de seguridad: {event_type}", extra=extra_data)

def log_performance_metric(metric_name: str, value: float, unit: str = "ms", 
                          additional_data: Dict[str, Any] = None):
    """Log de métrica de rendimiento"""
    perf_logger = get_performance_logger()
    
    extra_data = {
        'metric_name': metric_name,
        'metric_value': value,
        'metric_unit': unit,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if additional_data:
        extra_data.update(additional_data)
    
    perf_logger.info(f"Métrica: {metric_name} = {value} {unit}", extra=extra_data)

def log_database_operation(operation: str, table: str, duration_ms: float, 
                          rows_affected: int = 0, success: bool = True):
    """Log de operación de base de datos"""
    db_logger = get_logger("database")
    
    extra_data = {
        'operation': operation,
        'table': table,
        'duration_ms': duration_ms,
        'rows_affected': rows_affected,
        'success': success
    }
    
    if success:
        db_logger.info(f"DB {operation} en {table}: {rows_affected} filas en {duration_ms}ms", extra=extra_data)
    else:
        db_logger.error(f"Error en DB {operation} en {table}", extra=extra_data)

def log_api_request(method: str, path: str, status_code: int, duration_ms: float, 
                   user_id: str = "", ip_address: str = ""):
    """Log de request API"""
    api_logger = get_logger("api")
    
    extra_data = {
        'method': method,
        'path': path,
        'status_code': status_code,
        'duration_ms': duration_ms,
        'user_id': user_id or user_id_var.get(),
        'ip_address': ip_address
    }
    
    if status_code >= 500:
        api_logger.error(f"{method} {path} - {status_code} ({duration_ms}ms)", extra=extra_data)
    elif status_code >= 400:
        api_logger.warning(f"{method} {path} - {status_code} ({duration_ms}ms)", extra=extra_data)
    else:
        api_logger.info(f"{method} {path} - {status_code} ({duration_ms}ms)", extra=extra_data)

# Manejo de errores no capturados
def setup_exception_handling():
    """Configurar manejo global de excepciones no capturadas"""
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # Permitir Ctrl+C
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        logger = get_logger("system")
        logger.critical("Excepción no capturada", exc_info=(exc_type, exc_value, exc_traceback))
    
    sys.excepthook = handle_exception

# Clase de contexto para timing
class TimingContext:
    """Context manager para medir tiempo de ejecución"""
    
    def __init__(self, operation_name: str, logger_name: str = "performance"):
        self.operation_name = operation_name
        self.logger = get_logger(logger_name)
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.debug(f"Iniciando: {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds() * 1000
            
            if exc_type is None:
                self.logger.info(f"Completado: {self.operation_name} ({duration:.2f}ms)")
                log_performance_metric(self.operation_name, duration, "ms")
            else:
                self.logger.error(f"Error en: {self.operation_name} ({duration:.2f}ms)", 
                                exc_info=(exc_type, exc_val, exc_tb))

# Funciones de configuración específicas
def configure_development_logging():
    """Configuración para desarrollo (más verbose, colores)"""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Activar debug para loggers de aplicación
    get_logger("app").setLevel(logging.DEBUG)
    get_logger("database").setLevel(logging.DEBUG)

def configure_production_logging():
    """Configuración para producción (menos verbose, sin colores)"""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remover handler de consola en producción
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
            root_logger.removeHandler(handler)
    
    # Solo logs de WARNING hacia arriba en terceros
    logging.getLogger('uvicorn').setLevel(logging.ERROR)
    logging.getLogger('google').setLevel(logging.ERROR)

def get_log_stats() -> Dict[str, Any]:
    """Obtener estadísticas de logging"""
    log_dir = Path("logs")
    if not log_dir.exists():
        return {"error": "Directorio de logs no existe"}
    
    stats = {
        "total_files": 0,
        "total_size_mb": 0,
        "files": {}
    }
    
    for log_file in log_dir.glob("*.log*"):
        size_bytes = log_file.stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        
        stats["files"][log_file.name] = {
            "size_mb": round(size_mb, 2),
            "modified": log_file.stat().st_mtime
        }
        
        stats["total_files"] += 1
        stats["total_size_mb"] += size_mb
    
    stats["total_size_mb"] = round(stats["total_size_mb"], 2)
    return stats