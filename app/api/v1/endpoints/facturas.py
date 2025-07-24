# app/api/v1/endpoints/facturas.py
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query, status

from app.domain.services.factura_service import FacturaService
from app.domain.entities.factura import FacturaResponse, FacturaFilter
from app.core.dependencies import get_factura_service, get_current_user, CurrentUser
from app.shared.exceptions.business import (
    ProcessingError, FacturaNotFoundError, ValidationError, InvalidFileError
)

router = APIRouter(prefix="/facturas", tags=["facturas"])


@router.post("/upload", response_model=List[FacturaResponse])
async def upload_facturas(
    files: List[UploadFile] = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    factura_service: FacturaService = Depends(get_factura_service)
):
    """
    📄 Subir y procesar facturas PDF
    
    - Procesa múltiples archivos PDF con Google Document AI
    - Extrae datos estructurados automáticamente
    - Guarda en base de datos para consulta posterior
    """
    
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se proporcionaron archivos"
        )
    
    try:
        results = await factura_service.process_files(files, current_user.id)
        return results
        
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except InvalidFileError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except ProcessingError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno procesando archivos: {str(e)}"
        )


@router.get("/", response_model=List[FacturaResponse])
async def get_facturas(
    razon_social: Optional[str] = Query(None, description="Filtrar por razón social"),
    cuit_proveedor: Optional[str] = Query(None, description="Filtrar por CUIT"),
    limit: int = Query(50, le=100, description="Límite de resultados"),
    offset: int = Query(0, ge=0, description="Offset para paginación"),
    current_user: CurrentUser = Depends(get_current_user),
    factura_service: FacturaService = Depends(get_factura_service)
):
    """
    📋 Listar facturas del usuario
    
    - Filtros disponibles por razón social y CUIT
    - Paginación con limit/offset
    - Solo facturas del usuario autenticado
    """
    
    try:
        # Crear filtros
        filters = FacturaFilter(
            razon_social=razon_social,
            cuit_proveedor=cuit_proveedor,
            limit=limit,
            offset=offset
        )
        
        facturas = await factura_service.get_facturas(current_user.id, filters)
        return facturas
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo facturas: {str(e)}"
        )


@router.get("/{factura_id}", response_model=FacturaResponse)
async def get_factura(
    factura_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    factura_service: FacturaService = Depends(get_factura_service)
):
    """
    🔍 Obtener factura específica por ID
    
    - Verificación automática de permisos
    - Datos completos de la factura
    """
    
    try:
        factura = await factura_service.get_factura_by_id(factura_id, current_user.id)
        return factura
        
    except FacturaNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factura con ID {factura_id} no encontrada"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo factura: {str(e)}"
        )


@router.delete("/{factura_id}")
async def delete_factura(
    factura_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    factura_service: FacturaService = Depends(get_factura_service)
):
    """
    🗑️ Eliminar factura
    
    - Solo propietario puede eliminar
    - Eliminación permanente
    """
    
    try:
        success = await factura_service.delete_factura(factura_id, current_user.id)
        
        if success:
            return {"message": f"Factura {factura_id} eliminada correctamente"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error eliminando factura"
            )
            
    except FacturaNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factura con ID {factura_id} no encontrada"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error eliminando factura: {str(e)}"
        )


@router.get("/stats/summary")
async def get_stats_summary(
    current_user: CurrentUser = Depends(get_current_user),
    factura_service: FacturaService = Depends(get_factura_service)
):
    """
    📊 Estadísticas rápidas del usuario
    
    - Total facturas
    - Suma total importes
    - Facturas último mes
    """
    
    try:
        # Obtener todas las facturas del usuario
        facturas = await factura_service.get_facturas(current_user.id)
        
        # Calcular estadísticas
        total_facturas = len(facturas)
        suma_total = sum(f.total or 0 for f in facturas)
        
        # TODO: Implementar filtro por último mes
        facturas_ultimo_mes = 0  # Placeholder
        
        return {
            "total_facturas": total_facturas,
            "suma_total": float(suma_total),
            "suma_total_formateada": f"${suma_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            "facturas_ultimo_mes": facturas_ultimo_mes,
            "promedio_por_factura": float(suma_total / total_facturas) if total_facturas > 0 else 0
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estadísticas: {str(e)}"
        )
    