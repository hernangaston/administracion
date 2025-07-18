# -*- coding: utf-8 -*-
"""
Sistema de caché inteligente para el sistema de facturas
Implementa múltiples niveles de caché con invalidación automática
"""

import json
import time
import hashlib
import threading
from typing import Any, Optional, Dict, List, Callable, Union
from functools import wraps
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Entrada de caché con metadata"""
    key: str
    value: Any
    created_at: float
    last_accessed: float
    access_count: int
    ttl: float
    size_bytes: int
    tags: List[str]
    dependency_keys: List[str]

class LRUCache:
    """Implementación de LRU Cache thread-safe"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache = OrderedDict()
        self.lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            if key in self.cache:
                # Mover al final (más reciente)
                value = self.cache.pop(key)
                self.cache[key] = value
                return value
            return None
    
    def set(self, key: str, value: Any) -> None:
        with self.lock:
            if key in self.cache:
                # Actualizar existente
                self.cache.pop(key)
            elif len(self.cache) >= self.max_size:
                # Remover el más antiguo
                self.cache.popitem(last=False)
            
            self.cache[key] = value
    
    def delete(self, key: str) -> bool:
        with self.lock:
            return self.cache.pop(key, None) is not None
    
    def clear(self) -> None:
        with self.lock:
            self.cache.clear()
    
    def keys(self) -> List[str]:
        with self.lock:
            return list(self.cache.keys())
    
    def size(self) -> int:
        with self.lock:
            return len(self.cache)

class IntelligentCache:
    """Sistema de caché inteligente con múltiples funcionalidades"""
    
    def __init__(self, 
                 default_ttl: int = 300,  # 5 minutos
                 max_memory_mb: int = 100,
                 cleanup_interval: int = 60):  # 1 minuto
        
        self.default_ttl = default_ttl
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.cleanup_interval = cleanup_interval
        
        # Almacenamiento principal
        self.entries: Dict[str, CacheEntry] = {}
        self.lru = LRUCache(10000)  # Para tracking de acceso
        
        # Índices para búsqueda eficiente
        self.tag_index: Dict[str, set] = {}
        self.dependency_index: Dict[str, set] = {}
        
        # Control de memoria y limpieza
        self.current_memory_bytes = 0
        self.lock = threading.RLock()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'evictions': 0,
            'memory_usage_bytes': 0
        }
        
        # Iniciar thread de limpieza
        self._start_cleanup_thread()
    
    def get(self, key: str) -> Optional[Any]:
        """Obtiene valor del caché"""
        with self.lock:
            entry = self.entries.get(key)
            
            if not entry:
                self.stats['misses'] += 1
                return None
            
            # Verificar TTL
            if self._is_expired(entry):
                self._delete_entry(key)
                self.stats['misses'] += 1
                return None
            
            # Actualizar estadísticas de acceso
            entry.last_accessed = time.time()
            entry.access_count += 1
            self.lru.set(key, True)  # Marcar como accedido
            
            self.stats['hits'] += 1
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None, 
            tags: Optional[List[str]] = None, 
            dependencies: Optional[List[str]] = None) -> bool:
        """Guarda valor en caché"""
        
        ttl = ttl or self.default_ttl
        tags = tags or []
        dependencies = dependencies or []
        
        # Calcular tamaño
        size_bytes = self._calculate_size(value)
        
        with self.lock:
            # Verificar límite de memoria
            if not self._ensure_memory_available(size_bytes):
                logger.warning(f"No se pudo cachear {key}: límite de memoria")
                return False
            
            # Crear entrada
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                last_accessed=time.time(),
                access_count=0,
                ttl=ttl,
                size_bytes=size_bytes,
                tags=tags,
                dependency_keys=dependencies
            )
            
            # Remover entrada anterior si existe
            if key in self.entries:
                self._delete_entry(key)
            
            # Guardar nueva entrada
            self.entries[key] = entry
            self.current_memory_bytes += size_bytes
            self.lru.set(key, True)
            
            # Actualizar índices
            self._update_indexes(key, tags, dependencies)
            
            self.stats['sets'] += 1
            self.stats['memory_usage_bytes'] = self.current_memory_bytes
            
            return True
    
    def delete(self, key: str) -> bool:
        """Elimina entrada específica del caché"""
        with self.lock:
            if key in self.entries:
                self._delete_entry(key)
                self.stats['deletes'] += 1
                return True
            return False
    
    def delete_by_tag(self, tag: str) -> int:
        """Elimina todas las entradas con un tag específico"""
        deleted_count = 0
        
        with self.lock:
            keys_to_delete = self.tag_index.get(tag, set()).copy()
            
            for key in keys_to_delete:
                if self.delete(key):
                    deleted_count += 1
        
        logger.info(f"Eliminadas {deleted_count} entradas con tag '{tag}'")
        return deleted_count
    
    def delete_by_pattern(self, pattern: str) -> int:
        """Elimina entradas cuyas claves coincidan con un patrón"""
        import fnmatch
        deleted_count = 0
        
        with self.lock:
            keys_to_delete = [
                key for key in self.entries.keys() 
                if fnmatch.fnmatch(key, pattern)
            ]
            
            for key in keys_to_delete:
                if self.delete(key):
                    deleted_count += 1
        
        logger.info(f"Eliminadas {deleted_count} entradas con patrón '{pattern}'")
        return deleted_count
    
    def invalidate_dependencies(self, dependency_key: str) -> int:
        """Invalida todas las entradas que dependen de una clave"""
        invalidated_count = 0
        
        with self.lock:
            dependent_keys = self.dependency_index.get(dependency_key, set()).copy()
            
            for key in dependent_keys:
                if self.delete(key):
                    invalidated_count += 1
        
        logger.info(f"Invalidadas {invalidated_count} entradas dependientes de '{dependency_key}'")
        return invalidated_count
    
    def clear(self) -> None:
        """Limpia todo el caché"""
        with self.lock:
            self.entries.clear()
            self.tag_index.clear()
            self.dependency_index.clear()
            self.lru.clear()
            self.current_memory_bytes = 0
            self.stats['memory_usage_bytes'] = 0
        
        logger.info("Caché completamente limpiado")
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del caché"""
        with self.lock:
            total_requests = self.stats['hits'] + self.stats['misses']
            hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                **self.stats.copy(),
                'total_entries': len(self.entries),
                'hit_rate_percent': round(hit_rate, 2),
                'memory_usage_mb': round(self.current_memory_bytes / 1024 / 1024, 2),
                'memory_limit_mb': round(self.max_memory_bytes / 1024 / 1024, 2),
                'memory_usage_percent': round(
                    (self.current_memory_bytes / self.max_memory_bytes * 100), 2
                ) if self.max_memory_bytes > 0 else 0
            }
    
    def get_entry_info(self, key: str) -> Optional[Dict[str, Any]]:
        """Obtiene información detallada de una entrada"""
        with self.lock:
            entry = self.entries.get(key)
            if not entry:
                return None
            
            return {
                'key': entry.key,
                'created_at': datetime.fromtimestamp(entry.created_at).isoformat(),
                'last_accessed': datetime.fromtimestamp(entry.last_accessed).isoformat(),
                'access_count': entry.access_count,
                'ttl_seconds': entry.ttl,
                'size_bytes': entry.size_bytes,
                'tags': entry.tags,
                'dependencies': entry.dependency_keys,
                'expires_at': datetime.fromtimestamp(entry.created_at + entry.ttl).isoformat(),
                'is_expired': self._is_expired(entry)
            }
    
    def _delete_entry(self, key: str) -> None:
        """Elimina una entrada y actualiza índices"""
        entry = self.entries.get(key)
        if not entry:
            return
        
        # Actualizar memoria
        self.current_memory_bytes -= entry.size_bytes
        
        # Remover de índices
        for tag in entry.tags:
            if tag in self.tag_index:
                self.tag_index[tag].discard(key)
                if not self.tag_index[tag]:
                    del self.tag_index[tag]
        
        for dep in entry.dependency_keys:
            if dep in self.dependency_index:
                self.dependency_index[dep].discard(key)
                if not self.dependency_index[dep]:
                    del self.dependency_index[dep]
        
        # Remover entrada principal
        del self.entries[key]
        self.lru.delete(key)
    
    def _is_expired(self, entry: CacheEntry) -> bool:
        """Verifica si una entrada ha expirado"""
        return time.time() > (entry.created_at + entry.ttl)
    
    def _calculate_size(self, value: Any) -> int:
        """Calcula el tamaño aproximado en bytes de un valor"""
        try:
            if isinstance(value, str):
                return len(value.encode('utf-8'))
            elif isinstance(value, (int, float)):
                return 8
            elif isinstance(value, (list, tuple)):
                return sum(self._calculate_size(item) for item in value) + 24
            elif isinstance(value, dict):
                return sum(
                    self._calculate_size(k) + self._calculate_size(v) 
                    for k, v in value.items()
                ) + 24
            else:
                # Serializar para calcular tamaño
                return len(json.dumps(value, default=str).encode('utf-8'))
        except:
            return 1024  # 1KB por defecto si no se puede calcular
    
    def _ensure_memory_available(self, needed_bytes: int) -> bool:
        """Asegura que haya memoria disponible, evictando entradas si es necesario"""
        if self.current_memory_bytes + needed_bytes <= self.max_memory_bytes:
            return True
        
        # Necesitamos liberar memoria
        bytes_to_free = (self.current_memory_bytes + needed_bytes) - self.max_memory_bytes
        freed_bytes = 0
        
        # Obtener entradas ordenadas por LRU (menos accedidas primero)
        entries_by_access = sorted(
            self.entries.items(),
            key=lambda x: (x[1].last_accessed, x[1].access_count)
        )
        
        for key, entry in entries_by_access:
            if freed_bytes >= bytes_to_free:
                break
            
            freed_bytes += entry.size_bytes
            self._delete_entry(key)
            self.stats['evictions'] += 1
        
        return freed_bytes >= bytes_to_free
    
    def _update_indexes(self, key: str, tags: List[str], dependencies: List[str]) -> None:
        """Actualiza índices de tags y dependencias"""
        # Índice de tags
        for tag in tags:
            if tag not in self.tag_index:
                self.tag_index[tag] = set()
            self.tag_index[tag].add(key)
        
        # Índice de dependencias
        for dep in dependencies:
            if dep not in self.dependency_index:
                self.dependency_index[dep] = set()
            self.dependency_index[dep].add(key)
    
    def _cleanup_expired(self) -> int:
        """Limpia entradas expiradas"""
        expired_keys = []
        
        with self.lock:
            for key, entry in self.entries.items():
                if self._is_expired(entry):
                    expired_keys.append(key)
        
        # Eliminar fuera del lock para evitar deadlock
        for key in expired_keys:
            self.delete(key)
        
        if expired_keys:
            logger.debug(f"Limpiadas {len(expired_keys)} entradas expiradas")
        
        return len(expired_keys)
    
    def _start_cleanup_thread(self) -> None:
        """Inicia thread de limpieza automática"""
        def cleanup_worker():
            while True:
                try:
                    time.sleep(self.cleanup_interval)
                    self._cleanup_expired()
                except Exception as e:
                    logger.error(f"Error en limpieza de caché: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        logger.info("Thread de limpieza de caché iniciado")

# Instancia global del caché
_global_cache: Optional[IntelligentCache] = None

def get_cache() -> IntelligentCache:
    """Obtiene la instancia global del caché"""
    global _global_cache
    if _global_cache is None:
        _global_cache = IntelligentCache()
    return _global_cache

def setup_cache(default_ttl: int = 300, max_memory_mb: int = 100) -> IntelligentCache:
    """Configura el caché global"""
    global _global_cache
    _global_cache = IntelligentCache(default_ttl=default_ttl, max_memory_mb=max_memory_mb)
    return _global_cache

# Decoradores para caché automático

def cached(ttl: int = 300, 
          tags: Optional[List[str]] = None,
          dependencies: Optional[List[str]] = None,
          key_func: Optional[Callable] = None):
    """
    Decorador para cachear resultados de funciones automáticamente
    
    Args:
        ttl: Tiempo de vida en segundos
        tags: Tags para invalidación por grupo
        dependencies: Claves de dependencia para invalidación en cascada
        key_func: Función personalizada para generar clave de caché
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()
            
            # Generar clave de caché
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = _generate_cache_key(func.__name__, args, kwargs)
            
            # Intentar obtener del caché
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit para {func.__name__}")
                return cached_result
            
            # Ejecutar función y cachear resultado
            logger.debug(f"Cache miss para {func.__name__}, ejecutando...")
            result = func(*args, **kwargs)
            
            cache.set(
                cache_key, 
                result, 
                ttl=ttl, 
                tags=tags or [], 
                dependencies=dependencies or []
            )
            
            return result
        
        # Agregar función para invalidar caché específico
        wrapper.invalidate_cache = lambda *args, **kwargs: get_cache().delete(
            _generate_cache_key(func.__name__, args, kwargs)
        )
        
        return wrapper
    return decorator

def cache_result(key: str, ttl: int = 300, 
                tags: Optional[List[str]] = None,
                dependencies: Optional[List[str]] = None):
    """
    Decorador simple para cachear con clave específica
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()
            
            cached_result = cache.get(key)
            if cached_result is not None:
                return cached_result
            
            result = func(*args, **kwargs)
            cache.set(key, result, ttl=ttl, tags=tags, dependencies=dependencies)
            
            return result
        
        wrapper.cache_key = key
        wrapper.invalidate = lambda: get_cache().delete(key)
        
        return wrapper
    return decorator

def invalidate_cache_on_change(tags: Optional[List[str]] = None,
                              dependencies: Optional[List[str]] = None,
                              patterns: Optional[List[str]] = None):
    """
    Decorador para invalidar caché automáticamente después de operaciones que modifican datos
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Invalidar después de ejecutar la función
            cache = get_cache()
            
            if tags:
                for tag in tags:
                    cache.delete_by_tag(tag)
            
            if dependencies:
                for dep in dependencies:
                    cache.invalidate_dependencies(dep)
            
            if patterns:
                for pattern in patterns:
                    cache.delete_by_pattern(pattern)
            
            logger.debug(f"Cache invalidado después de {func.__name__}")
            return result
            
        return wrapper
    return decorator

# Funciones de utilidad

def _generate_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Genera clave de caché determinística"""
    # Crear representación serializable
    key_data = {
        'function': func_name,
        'args': args,
        'kwargs': sorted(kwargs.items())
    }
    
    # Generar hash
    key_str = json.dumps(key_data, sort_keys=True, default=str)
    hash_obj = hashlib.md5(key_str.encode('utf-8'))
    
    return f"func:{func_name}:{hash_obj.hexdigest()[:16]}"

def warm_cache(func: Callable, args_list: List[tuple], kwargs_list: List[dict] = None):
    """
    Precarga el caché ejecutando una función con múltiples parámetros
    """
    kwargs_list = kwargs_list or [{}] * len(args_list)
    
    for args, kwargs in zip(args_list, kwargs_list):
        try:
            func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Error precargando caché para {func.__name__}: {e}")

# Funciones específicas para el sistema de facturas

class FacturasCacheManager:
    """Administrador de caché específico para el sistema de facturas"""
    
    @staticmethod
    def invalidate_user_data(user_id: str):
        """Invalida todos los datos de caché de un usuario específico"""
        cache = get_cache()
        cache.delete_by_tag(f"user:{user_id}")
        cache.delete_by_pattern(f"user:{user_id}:*")
    
    @staticmethod
    def invalidate_facturas():
        """Invalida caché relacionado con facturas"""
        cache = get_cache()
        cache.delete_by_tag("facturas")
        cache.delete_by_tag("estadisticas")
        cache.delete_by_pattern("factura:*")
        cache.delete_by_pattern("stats:*")
    
    @staticmethod
    def invalidate_reports():
        """Invalida caché de reportes"""
        cache = get_cache()
        cache.delete_by_tag("reportes")
        cache.delete_by_pattern("report:*")
    
    @staticmethod
    def get_cache_health() -> Dict[str, Any]:
        """Obtiene información de salud del caché"""
        cache = get_cache()
        stats = cache.get_stats()
        
        health_status = "healthy"
        issues = []
        
        # Verificar hit rate
        if stats['hit_rate_percent'] < 50:
            health_status = "warning"
            issues.append("Hit rate bajo (< 50%)")
        
        # Verificar uso de memoria
        if stats['memory_usage_percent'] > 90:
            health_status = "critical"
            issues.append("Uso de memoria crítico (> 90%)")
        elif stats['memory_usage_percent'] > 75:
            if health_status != "critical":
                health_status = "warning"
            issues.append("Uso de memoria alto (> 75%)")
        
        # Verificar evictions frecuentes
        total_ops = stats['sets'] + stats['deletes']
        if total_ops > 0 and (stats['evictions'] / total_ops) > 0.1:
            if health_status != "critical":
                health_status = "warning"
            issues.append("Evictions frecuentes (> 10% de operaciones)")
        
        return {
            "status": health_status,
            "issues": issues,
            "stats": stats,
            "recommendations": FacturasCacheManager._get_recommendations(stats)
        }
    
    @staticmethod
    def _get_recommendations(stats: Dict[str, Any]) -> List[str]:
        """Genera recomendaciones basadas en estadísticas"""
        recommendations = []
        
        if stats['hit_rate_percent'] < 50:
            recommendations.append("Considerar aumentar TTL o revisar patrones de acceso")
        
        if stats['memory_usage_percent'] > 75:
            recommendations.append("Considerar aumentar límite de memoria o reducir TTL")
        
        if stats['total_entries'] > 5000:
            recommendations.append("Considerar implementar particionado de caché")
        
        return recommendations

# Configuración específica para facturas
def setup_facturas_cache():
    """Configura caché optimizado para el sistema de facturas"""
    cache = setup_cache(
        default_ttl=300,  # 5 minutos por defecto
        max_memory_mb=200  # 200MB para facturas
    )
    
    logger.info("Sistema de caché configurado para facturas")
    return cache