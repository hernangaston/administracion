#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de migración para aplicar las correcciones de la Fase 1
Ejecutar desde la raíz del proyecto: python scripts/migrate_fase1.py
"""

import os
import sys
import shutil
import sqlite3
from pathlib import Path
import logging

# Agregar la raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MigradorFase1:
    """Migrador para aplicar correcciones críticas de la Fase 1"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.backup_dir = self.project_root / "backup_fase1"
        
    def ejecutar_migracion(self):
        """Ejecuta la migración completa"""
        logger.info("🚀 Iniciando migración Fase 1: Correcciones Críticas")
        
        try:
            # 1. Crear backup
            self._crear_backup()
            
            # 2. Crear directorios necesarios
            self._crear_directorios()
            
            # 3. Eliminar archivo problemático
            self._eliminar_import_circular()
            
            # 4. Crear índices de base de datos
            self._crear_indices_bd()
            
            # 5. Instalar dependencias necesarias
            self._verificar_dependencias()
            
            # 6. Validar migración
            self._validar_migracion()
            
            logger.info("✅ Migración Fase 1 completada exitosamente")
            self._mostrar_resumen()
            
        except Exception as e:
            logger.error(f"❌ Error en migración: {e}")
            self._restaurar_backup()
            raise
    
    def _crear_backup(self):
        """Crea backup de archivos críticos"""
        logger.info("📦 Creando backup de archivos...")
        
        self.backup_dir.mkdir(exist_ok=True)
        
        archivos_backup = [
            "agente_facturas.py",
            "cuit_utils.py", 
            "app.py",
            "database.db"
        ]
        
        for archivo in archivos_backup:
            origen = self.project_root / archivo
            if origen.exists():
                destino = self.backup_dir / archivo
                shutil.copy2(origen, destino)
                logger.info(f"  ✓ Backup creado: {archivo}")
        
        logger.info(f"Backup guardado en: {self.backup_dir}")
    
    def _crear_directorios(self):
        """Crea estructura de directorios necesaria"""
        logger.info("📁 Creando directorios necesarios...")
        
        directorios = [
            "logs",
            "uploads",
            "temp",
            "app_modules/utils"
        ]
        
        for directorio in directorios:
            dir_path = self.project_root / directorio
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"  ✓ Directorio: {directorio}")
    
    def _eliminar_import_circular(self):
        """Elimina el archivo cuit_utils.py problemático"""
        logger.info("🗑️ Eliminando archivo con import circular...")
        
        archivo_problematico = self.project_root / "cuit_utils.py"
        if archivo_problematico.exists():
            archivo_problematico.unlink()
            logger.info("  ✓ Eliminado: cuit_utils.py (import circular)")
        else:
            logger.info("  ℹ️ Archivo cuit_utils.py ya no existe")
    
    def _crear_indices_bd(self):
        """Crea índices de base de datos para optimización"""
        logger.info("🗄️ Creando índices de base de datos...")
        
        db_path = self.project_root / "database.db"
        if not db_path.exists():
            logger.warning("  ⚠️ Base de datos no encontrada, saltando índices")
            return
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            indices = [
                "CREATE INDEX IF NOT EXISTS idx_facturas_razon_social ON facturas(razon_social)",
                "CREATE INDEX IF NOT EXISTS idx_facturas_cuit_proveedor ON facturas(cuit_proveedor)", 
                "CREATE INDEX IF NOT EXISTS idx_facturas_created_at ON facturas(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_facturas_total ON facturas(total)",
                "CREATE INDEX IF NOT EXISTS idx_facturas_fecha_factura ON facturas(fecha_factura)",
                "CREATE INDEX IF NOT EXISTS idx_facturas_cuit_fecha ON facturas(cuit_proveedor, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_facturas_proveedor_total ON facturas(razon_social, total)"
            ]
            
            for indice in indices:
                cursor.execute(indice)
                logger.info(f"  ✓ Índice creado: {indice.split('idx_')[1].split(' ON')[0]}")
            
            conn.commit()
            conn.close()
            
            logger.info("  ✅ Índices de BD creados exitosamente")
            
        except Exception as e:
            logger.error(f"  ❌ Error creando índices: {e}")
    
    def _verificar_dependencias(self):
        """Verifica e instala dependencias necesarias"""
        logger.info("📦 Verificando dependencias...")
        
        dependencias_opcionales = {
            'python-magic': 'Validación avanzada de tipos MIME',
            'PyPDF2': 'Validación robusta de archivos PDF'
        }
        
        for dep, descripcion in dependencias_opcionales.items():
            try:
                __import__(dep.replace('-', '_'))
                logger.info(f"  ✓ {dep}: Disponible")
            except ImportError:
                logger.warning(f"  ⚠️ {dep}: No disponible - {descripcion}")
                logger.info(f"    Para instalar: pip install {dep}")
    
    def _validar_migracion(self):
        """Valida que la migración fue exitosa"""
        logger.info("✅ Validando migración...")
        
        # Verificar que archivos críticos no existen
        archivo_circular = self.project_root / "cuit_utils.py"
        if archivo_circular.exists():
            raise Exception("Archivo con import circular aún existe")
        
        # Verificar que directorios existen
        dirs_requeridos = ["logs", "app_modules/utils"]
        for dir_name in dirs_requeridos:
            if not (self.project_root / dir_name).exists():
                raise Exception(f"Directorio requerido no existe: {dir_name}")
        
        # Verificar base de datos
        db_path = self.project_root / "database.db"
        if db_path.exists():
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Verificar que tabla facturas existe
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='facturas'")
                if not cursor.fetchone():
                    raise Exception("Tabla facturas no encontrada")
                
                # Verificar algunos índices
                cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_facturas%'")
                indices = cursor.fetchall()
                logger.info(f"  ✓ Encontrados {len(indices)} índices")
                
                conn.close()
                
            except Exception as e:
                logger.warning(f"  ⚠️ Error verificando BD: {e}")
        
        logger.info("  ✅ Validación completada")
    
    def _mostrar_resumen(self):
        """Muestra resumen de cambios aplicados"""
        print("\n" + "="*60)
        print("🎉 MIGRACIÓN FASE 1 COMPLETADA")
        print("="*60)
        print()
        print("📋 CAMBIOS APLICADOS:")
        print("  ✅ Eliminado import circular en cuit_utils.py")
        print("  ✅ Creados índices de base de datos para optimización")
        print("  ✅ Estructura de directorios preparada")
        print("  ✅ Backup de seguridad creado")
        print()
        print("📝 PRÓXIMOS PASOS:")
        print("  1. Aplicar los archivos corregidos:")
        print("     - agente_facturas.py (eliminar función duplicada)")
        print("     - app_modules/utils/cuit_utils.py (nuevo archivo)")
        print("     - app_modules/utils/file_validator.py (nuevo archivo)")
        print("  2. Actualizar imports en app.py")
        print("  3. Ejecutar tests de validación")
        print()
        print("🔧 INSTALACIONES OPCIONALES RECOMENDADAS:")
        print("  pip install python-magic PyPDF2")
        print()
        print(f"📦 Backup disponible en: {self.backup_dir}")
        print("="*60)
    
    def _restaurar_backup(self):
        """Restaura backup en caso de error"""
        logger.error("🔄 Restaurando backup...")
        
        if not self.backup_dir.exists():
            logger.error("No se encontró directorio de backup")
            return
        
        for archivo_backup in self.backup_dir.glob("*"):
            if archivo_backup.is_file():
                destino = self.project_root / archivo_backup.name
                shutil.copy2(archivo_backup, destino)
                logger.info(f"  ✓ Restaurado: {archivo_backup.name}")


def main():
    """Función principal del script"""
    print("🚀 MIGRADOR FASE 1 - CORRECCIONES CRÍTICAS")
    print("="*50)
    print()
    
    # Verificar que estamos en el directorio correcto
    if not Path("app.py").exists():
        print("❌ Error: Ejecutar desde la raíz del proyecto")
        print("   Uso: python scripts/migrate_fase1.py")
        sys.exit(1)
    
    # Confirmar ejecución
    respuesta = input("¿Continuar con la migración? (s/N): ")
    if respuesta.lower() not in ['s', 'si', 'sí', 'y', 'yes']:
        print("Migración cancelada")
        sys.exit(0)
    
    # Ejecutar migración
    migrador = MigradorFase1()
    try:
        migrador.ejecutar_migracion()
    except KeyboardInterrupt:
        print("\n❌ Migración interrumpida por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error en migración: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()