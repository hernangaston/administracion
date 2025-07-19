# -*- coding: utf-8 -*-
"""
Middleware de seguridad y logging
"""

import time
import uuid
import logging
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

async def security_middleware(request: Request, call_next):
    """Middleware de seguridad y logging"""
    
    # Generar ID único para el request
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    # Extraer información del request
    client_ip = request.client.host if request.client else "unknown"
    method = request.method
    path = request.url.path
    
    try:
        # Logs de entrada
        logger.info(f"Request iniciado: {method} {path} [req:{request_id}]")
        
        # Validaciones de seguridad básicas
        content_length = request.headers.get("content-length")
        if content_length:
            size_mb = int(content_length) / 1024 / 1024
            
            # Límite general de 100MB
            if size_mb > 100:
                logger.warning(f"Request demasiado grande bloqueado: {size_mb}MB [req:{request_id}]")
                raise HTTPException(
                    status_code=413,
                    detail="Request demasiado grande"
                )
        
        # Procesar request
        response = await call_next(request)
        
        # Calcular tiempo y loggear respuesta exitosa
        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"{method} {path} - {response.status_code} ({duration_ms:.2f}ms) [req:{request_id}]")
        
        # Headers de seguridad
        response.headers.update({
            "X-Request-ID": request_id,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        })
        
        return response
        
    except Exception as e:
        # Manejo de errores
        duration_ms = (time.time() - start_time) * 1000
        
        status_code = getattr(e, 'status_code', 500)
        detail = getattr(e, 'detail', str(e))
        
        logger.error(f"{method} {path} - {status_code} ({duration_ms:.2f}ms) ERROR: {detail} [req:{request_id}]")
        
        # Log de seguridad para errores críticos
        if status_code >= 500:
            logger.critical(f"Error crítico: {path} - {detail} [req:{request_id}]")
        
        # Crear respuesta de error
        if isinstance(e, HTTPException):
            response = JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail, "request_id": request_id}
            )
        else:
            response = JSONResponse(
                status_code=500,
                content={"detail": "Error interno del servidor", "request_id": request_id}
            )
        
        response.headers["X-Request-ID"] = request_id
        return response