#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests de verificación para los sistemas implementados en Fase 2
Ejecutar: python -m pytest tests/test_phase2_systems.py -v
"""

import sys
import os
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta
import pytest

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent))

class TestDateUtils:
    """Tests para el sistema unificado de fechas"""
    
    def test_parsear_fechas_multiples_formatos(self):
        """Test de parsing de múltiples formatos de fecha"""
        try:
            from app_modules.utils.date_utils import DateFormatter
            
            casos_test = [
                ("2024-01-15", "15/01/2024"),
                ("15/01/2024", "15/01/2024"),
                ("15-01-2024", "15/01/2024"),
                ("2024/01/15", "15/01/2024"),
                ("15 de enero de 2024", "15/01/2024"),
                ("2024-01-15 10:30:00", "15/01/2024"),
                ("2024-01-15T10:30:00", "15/01/2024")
            ]
            
            for entrada, esperado in casos_test:
                resultado = DateFormatter.formatear_para_display(entrada)
                assert resultado == esperado, f"Error con {entrada}: esperado {esperado}, obtuvo {resultado}"
            
            print("✅ Test de fechas múltiples formatos: PASÓ")
            
        except ImportError:
            print("⚠️ Sistema de fechas no disponible")
            pytest.skip("Sistema de fechas no implementado")
    
    def test_validacion_fechas_facturas(self):
        """Test de validación específica para fechas de facturas"""
        try:
            from app_modules.utils.date_utils import FechaFactura
            
            # Fecha válida
            resultado = FechaFactura.validar_fecha_factura("15/01/2024")
            assert resultado['es_valida'] == True
            
            # Fecha futura (inválida)
            fecha_futura = (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d')
            resultado = FechaFactura.validar_fecha_factura(fecha_futura)
            assert resultado['es_valida'] == False
            
            # Fecha muy antigua (warning)
            resultado = FechaFactura.validar_fecha_factura("1990-01-01")
            assert len(resultado['warnings']) > 0
            
            print("✅ Test de validación de fechas de facturas: PASÓ")
            
        except ImportError:
            print("⚠️ Sistema de fechas no disponible")
            pytest.skip("Sistema de fechas no implementado")

class TestLoggingSystem:
    """Tests para el sistema de logging estructurado"""
    
    def test_json_formatter(self):
        """Test del formateador JSON"""
        try:
            from app_modules.core.logging_config import JSONFormatter
            import logging
            
            formatter = JSONFormatter()
            
            # Crear record de prueba
            record = logging.LogRecord(
                name="test_logger",
                level=logging.INFO,
                pathname="test.py",
                lineno=10,
                msg="Test message",
                args=(),
                exc_info=None
            )
            
            # Formatear como JSON
            formatted = formatter.format(record)
            
            # Verificar que es JSON válido
            parsed = json.loads(formatted)
            
            # Verificar campos requeridos
            assert 'timestamp' in parsed
            assert 'level' in parsed
            assert 'message' in parsed
            assert parsed['level'] == 'INFO'
            assert parsed['message'] == 'Test message'
            
            print("✅ Test de JSON formatter: PASÓ")
            
        except ImportError:
            print("⚠️ Sistema de logging no disponible")
            pytest.skip("Sistema de logging no implementado")
    
    def test_logging_context(self):
        """Test del contexto de logging"""
        try:
            from app_modules.core.logging_config import set_request_context, clear_request_context
            
            # Establecer contexto
            set_request_context("test_request_123", "test_user")
            
            # Limpiar contexto
            clear_request_context()
            
            print("✅ Test de contexto de logging: PASÓ")
            
        except ImportError:
            print("⚠️ Sistema de logging no disponible")
            pytest.skip("Sistema de logging no implementado")

class TestErrorHandling:
    """Tests para el sistema de manejo de errores"""
    
    def test_facturas_exceptions(self):
        """Test de excepciones personalizadas"""
        try:
            from app_modules.core.error_handling import (
                FacturasException, ErrorCode, ValidationError, 
                ErrorDetail, DataValidator
            )
            
            # Test de excepción básica
            exc = FacturasException(
                ErrorCode.VALIDATION_ERROR,
                "Test error",
                http_status=400
            )
            
            error_dict = exc.to_dict()
            assert error_dict['error']['code'] == ErrorCode.VALIDATION_ERROR.value
            assert error_dict['error']['message'] == "Test error"
            
            print("✅ Test de excepciones básicas: PASÓ")
            
        except ImportError:
            print("⚠️ Sistema de errores no disponible")
            pytest.skip("Sistema de errores no implementado")
    
    def test_data_validators(self):
        """Test de validadores de datos"""
        try:
            from app_modules.core.error_handling import DataValidator, ValidationError
            
            # Test validación de monto válido
            monto = DataValidator.validate_amount("1500.50")
            assert monto == 1500.50
            
            # Test validación de monto inválido
            with pytest.raises(ValidationError):
                DataValidator.validate_amount("abc")
            
            # Test validación de monto negativo
            with pytest.raises(ValidationError):
                DataValidator.validate_amount("-100")
            
            print("✅ Test de validadores de datos: PASÓ")
            
        except ImportError:
            print("⚠️ Sistema de errores no disponible")
            pytest.skip("Sistema de errores no implementado")

class TestCacheSystem:
    """Tests para el sistema de caché inteligente"""
    
    def test_basic_cache_operations(self):
        """Test de operaciones básicas de caché"""
        try:
            from app_modules.core.cache_system import IntelligentCache
            
            cache = IntelligentCache(default_ttl=10, max_memory_mb=10)
            
            # Test set/get básico
            cache.set("test_key", "test_value")
            result = cache.get("test_key")
            assert result == "test_value"
            
            # Test de key inexistente
            result = cache.get("nonexistent_key")
            assert result is None
            
            # Test de delete
            deleted = cache.delete("test_key")
            assert deleted == True
            
            result = cache.get("test_key")
            assert result is None
            
            print("✅ Test de operaciones básicas de caché: PASÓ")
            
        except ImportError:
            print("⚠️ Sistema de caché no disponible")
            pytest.skip("Sistema de caché no implementado")
    
    def test_cache_with_tags(self):
        """Test de caché con tags"""
        try:
            from app_modules.core.cache_system import IntelligentCache
            
            cache = IntelligentCache()
            
            # Guardar con tags
            cache.set("item1", "value1", tags=["tag1", "tag2"])
            cache.set("item2", "value2", tags=["tag1"])
            cache.set("item3", "value3", tags=["tag3"])
            
            # Verificar que están guardados
            assert cache.get("item1") == "value1"
            assert cache.get("item2") == "value2"
            assert cache.get("item3") == "value3"
            
            # Eliminar por tag
            deleted_count = cache.delete_by_tag("tag1")
            assert deleted_count == 2
            
            # Verificar eliminación
            assert cache.get("item1") is None
            assert cache.get("item2") is None
            assert cache.get("item3") == "value3"
            
            print("✅ Test de caché con tags: PASÓ")
            
        except ImportError:
            print("⚠️ Sistema de caché no disponible")
            pytest.skip("Sistema de caché no implementado")
    
    def test_cache_decorators(self):
        """Test de decoradores de caché"""
        try:
            from app_modules.core.cache_system import cached, setup_cache
            
            # Configurar caché
            cache = setup_cache(default_ttl=10)
            
            call_count = 0
            
            @cached(ttl=5)
            def expensive_function(x, y):
                nonlocal call_count
                call_count += 1
                return x + y
            
            # Primera llamada - debería ejecutar función
            result1 = expensive_function(2, 3)
            assert result1 == 5
            assert call_count == 1
            
            # Segunda llamada - debería usar caché
            result2 = expensive_function(2, 3)
            assert result2 == 5
            assert call_count == 1  # No debería incrementar
            
            # Llamada con parámetros diferentes - debería ejecutar función
            result3 = expensive_function(3, 4)
            assert result3 == 7
            assert call_count == 2
            
            print("✅ Test de decoradores de caché: PASÓ")
            
        except ImportError:
            print("⚠️ Sistema de caché no disponible")
            pytest.skip("Sistema de caché no implementado")

class TestIntegration:
    """Tests de integración entre sistemas"""
    
    def test_error_logging_integration(self):
        """Test de integración entre errores y logging"""
        try:
            from app_modules.core.error_handling import FacturasException, ErrorCode
            from app_modules.core.logging_config import get_logger
            
            logger = get_logger("test")
            
            # Crear excepción
            exc = FacturasException(
                ErrorCode.VALIDATION_ERROR,
                "Test integration error",
                context={"test": True}
            )
            
            # Loggear excepción
            logger.error("Test error", exc_info=True)
            
            print("✅ Test de integración error-logging: PASÓ")
            
        except ImportError:
            print("⚠️ Sistemas de integración no disponibles")
            pytest.skip("Sistemas no implementados")
    
    def test_cache_with_date_keys(self):
        """Test de caché usando fechas como parte de las claves"""
        try:
            from app_modules.core.cache_system import IntelligentCache
            from app_modules.utils.date_utils import DateFormatter
            
            cache = IntelligentCache()
            
            # Usar fecha como parte de la clave
            fecha = DateFormatter.formatear_para_bd("2024-01-15")
            cache_key = f"stats:{fecha}"
            
            cache.set(cache_key, {"count": 100}, tags=["stats"])
            result = cache.get(cache_key)
            
            assert result["count"] == 100
            
            print("✅ Test de caché con claves de fecha: PASÓ")
            
        except ImportError:
            print("⚠️ Sistemas de integración no disponibles")
            pytest.skip("Sistemas no implementados")

def run_all_tests():
    """Ejecuta todos los tests y muestra resumen"""
    print("🧪 EJECUTANDO TESTS DE FASE 2")
    print("="*50)
    print()
    
    test_classes = [
        TestDateUtils,
        TestLoggingSystem, 
        TestErrorHandling,
        TestCacheSystem,
        TestIntegration
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    skipped_tests = 0
    
    for test_class in test_classes:
        print(f"\n📋 {test_class.__name__}")
        print("-" * 30)
        
        instance = test_class()
        methods = [m for m in dir(instance) if m.startswith('test_')]
        
        for method_name in methods:
            total_tests += 1
            try:
                method = getattr(instance, method_name)
                method()
                passed_tests += 1
            except pytest.skip.Exception:
                skipped_tests += 1
                print(f"⏭️ {method_name}: OMITIDO")
            except Exception as e:
                failed_tests += 1
                print(f"❌ {method_name}: FALLÓ - {e}")
    
    print("\n" + "="*50)
    print("📊 RESUMEN DE TESTS")
    print("="*50)
    print(f"Total ejecutados: {total_tests}")
    print(f"✅ Pasaron: {passed_tests}")
    print(f"❌ Fallaron: {failed_tests}")
    print(f"⏭️ Omitidos: {skipped_tests}")
    
    if failed_tests == 0:
        print("\n🎉 TODOS LOS TESTS DISPONIBLES PASARON")
        return True
    else:
        print(f"\n⚠️ {failed_tests} TESTS FALLARON")
        return False

def main():
    """Función principal para ejecutar tests"""
    if len(sys.argv) > 1 and sys.argv[1] == "--pytest":
        # Ejecutar con pytest
        pytest.main([__file__, "-v"])
    else:
        # Ejecutar tests personalizados
        success = run_all_tests()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()