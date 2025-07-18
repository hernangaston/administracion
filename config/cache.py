# Configuración de caché
CACHE_DEFAULT_TTL = 300  # 5 minutos
CACHE_MAX_MEMORY_MB = 200  # 200MB
CACHE_CLEANUP_INTERVAL = 60  # 1 minuto

# Configuraciones específicas por tipo
CACHE_CONFIG = {
    'facturas': {
        'ttl': 600,  # 10 minutos para listados
        'tags': ['facturas', 'data']
    },
    'estadisticas': {
        'ttl': 1800,  # 30 minutos para estadísticas
        'tags': ['stats', 'reports']
    },
    'reportes': {
        'ttl': 3600,  # 1 hora para reportes
        'tags': ['reports']
    },
    'usuarios': {
        'ttl': 900,  # 15 minutos para datos de usuario
        'tags': ['auth', 'users']
    }
}
