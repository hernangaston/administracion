# -*- coding: utf-8 -*-
"""
Validador robusto de archivos PDF para el sistema de facturas
"""
import os
import logging
from typing import Tuple, Optional, Dict, Any
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)

class PDFValidator:
    """Validación exhaustiva de archivos PDF"""
    
    # Configuración
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    MIN_FILE_SIZE = 1024  # 1KB mínimo
    
    ALLOWED_EXTENSIONS = ['.pdf']
    ALLOWED_MIME_TYPES = [
        'application/pdf',
        'application/x-pdf'
    ]
    
    # Firmas de archivos PDF válidas (magic bytes)
    PDF_SIGNATURES = [
        b'%PDF-1.0',
        b'%PDF-1.1', 
        b'%PDF-1.2',
        b'%PDF-1.3',
        b'%PDF-1.4',
        b'%PDF-1.5',
        b'%PDF-1.6',
        b'%PDF-1.7',
        b'%PDF-2.0'
    ]
    
    @staticmethod
    def validar_archivo_completo(file_path: str) -> Dict[str, Any]:
        """
        Validación completa de archivo PDF
        
        Returns:
            Dict con: {
                'es_valido': bool,
                'errores': List[str],
                'warnings': List[str], 
                'metadata': Dict[str, Any]
            }
        """
        resultado = {
            'es_valido': True,
            'errores': [],
            'warnings': [],
            'metadata': {}
        }
        
        try:
            # 1. Verificar que el archivo existe
            if not os.path.exists(file_path):
                resultado['errores'].append("El archivo no existe")
                resultado['es_valido'] = False
                return resultado
            
            # 2. Obtener información básica del archivo
            file_stat = os.stat(file_path)
            file_size = file_stat.st_size
            
            resultado['metadata'].update({
                'ruta': file_path,
                'nombre': os.path.basename(file_path),
                'tamaño_bytes': file_size,
                'tamaño_mb': round(file_size / 1024 / 1024, 2)
            })
            
            # 3. Validar tamaño
            size_validation = PDFValidator._validar_tamaño(file_size)
            if not size_validation[0]:
                resultado['errores'].append(size_validation[1])
                resultado['es_valido'] = False
            
            # 4. Validar extensión
            ext_validation = PDFValidator._validar_extension(file_path)
            if not ext_validation[0]:
                resultado['errores'].append(ext_validation[1])
                resultado['es_valido'] = False
            
            # 5. Validar firma de archivo (magic bytes)
            signature_validation = PDFValidator._validar_firma_pdf(file_path)
            if not signature_validation[0]:
                resultado['errores'].append(signature_validation[1])
                resultado['es_valido'] = False
            else:
                resultado['metadata']['version_pdf'] = signature_validation[1]
            
            # 6. Validar tipo MIME (si python-magic está disponible)
            mime_validation = PDFValidator._validar_tipo_mime(file_path)
            if mime_validation[0]:
                resultado['metadata']['tipo_mime'] = mime_validation[1]
            else:
                resultado['warnings'].append(f"No se pudo determinar tipo MIME: {mime_validation[1]}")
            
            # 7. Validación básica de estructura PDF
            structure_validation = PDFValidator._validar_estructura_basica(file_path)
            if not structure_validation[0]:
                resultado['errores'].append(structure_validation[1])
                resultado['es_valido'] = False
            else:
                resultado['metadata'].update(structure_validation[1])
            
            # 8. Generar hash para detección de duplicados
            try:
                resultado['metadata']['hash_md5'] = PDFValidator._calcular_hash(file_path)
            except Exception as e:
                resultado['warnings'].append(f"No se pudo calcular hash: {str(e)}")
            
            # 9. Verificaciones adicionales de seguridad
            security_validation = PDFValidator._validar_seguridad(file_path)
            if not security_validation[0]:
                resultado['warnings'].extend(security_validation[1])
            
            return resultado
            
        except Exception as e:
            logger.error(f"Error validando archivo {file_path}: {e}")
            resultado['errores'].append(f"Error de validación: {str(e)}")
            resultado['es_valido'] = False
            return resultado
    
    @staticmethod
    def _validar_tamaño(file_size: int) -> Tuple[bool, str]:
        """Valida el tamaño del archivo"""
        if file_size == 0:
            return False, "Archivo vacío"
        
        if file_size < PDFValidator.MIN_FILE_SIZE:
            return False, f"Archivo demasiado pequeño: {file_size} bytes (mínimo {PDFValidator.MIN_FILE_SIZE})"
        
        if file_size > PDFValidator.MAX_FILE_SIZE:
            size_mb = file_size / 1024 / 1024
            max_mb = PDFValidator.MAX_FILE_SIZE / 1024 / 1024
            return False, f"Archivo demasiado grande: {size_mb:.1f}MB (máximo {max_mb}MB)"
        
        return True, "Tamaño válido"
    
    @staticmethod
    def _validar_extension(file_path: str) -> Tuple[bool, str]:
        """Valida la extensión del archivo"""
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext not in PDFValidator.ALLOWED_EXTENSIONS:
            return False, f"Extensión no permitida: {file_ext} (solo se permiten: {', '.join(PDFValidator.ALLOWED_EXTENSIONS)})"
        
        return True, "Extensión válida"
    
    @staticmethod
    def _validar_firma_pdf(file_path: str) -> Tuple[bool, str]:
        """Valida la firma PDF (magic bytes)"""
        try:
            with open(file_path, 'rb') as f:
                # Leer los primeros 8 bytes
                header = f.read(8)
                
                if len(header) < 8:
                    return False, "Archivo demasiado corto para ser un PDF válido"
                
                # Verificar si coincide con alguna firma PDF conocida
                for signature in PDFValidator.PDF_SIGNATURES:
                    if header.startswith(signature):
                        version = signature.decode('ascii').split('-')[1]
                        return True, f"PDF versión {version}"
                
                return False, "No es un archivo PDF válido (firma no reconocida)"
                
        except Exception as e:
            return False, f"Error leyendo firma del archivo: {str(e)}"
    
    @staticmethod
    def _validar_tipo_mime(file_path: str) -> Tuple[bool, str]:
        """Valida el tipo MIME usando python-magic si está disponible"""
        try:
            import magic
            mime_type = magic.from_file(file_path, mime=True)
            
            if mime_type in PDFValidator.ALLOWED_MIME_TYPES:
                return True, mime_type
            else:
                return False, f"Tipo MIME no válido: {mime_type}"
                
        except ImportError:
            # python-magic no está instalado
            return True, "python-magic no disponible"
        except Exception as e:
            return False, f"Error verificando tipo MIME: {str(e)}"
    
    @staticmethod
    def _validar_estructura_basica(file_path: str) -> Tuple[bool, Dict[str, Any]]:
        """Validación básica de estructura PDF"""
        try:
            # Intentar usar PyPDF2 si está disponible
            try:
                import PyPDF2
                return PDFValidator._validar_con_pypdf2(file_path)
            except ImportError:
                pass
            
            # Validación básica sin librerías externas
            return PDFValidator._validar_estructura_manual(file_path)
            
        except Exception as e:
            return False, f"Error validando estructura PDF: {str(e)}"
    
    @staticmethod
    def _validar_con_pypdf2(file_path: str) -> Tuple[bool, Dict[str, Any]]:
        """Validación usando PyPDF2"""
        try:
            import PyPDF2
            
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                
                num_pages = len(pdf_reader.pages)
                if num_pages == 0:
                    return False, "PDF sin páginas"
                
                metadata = {
                    'num_paginas': num_pages,
                    'tiene_metadata': bool(pdf_reader.metadata),
                    'metodo_validacion': 'PyPDF2'
                }
                
                # Intentar obtener metadata si existe
                if pdf_reader.metadata:
                    try:
                        if pdf_reader.metadata.get('/Title'):
                            metadata['titulo'] = str(pdf_reader.metadata['/Title'])
                        if pdf_reader.metadata.get('/Creator'):
                            metadata['creador'] = str(pdf_reader.metadata['/Creator'])
                    except:
                        pass
                
                # Verificar que al menos la primera página se puede leer
                try:
                    first_page = pdf_reader.pages[0]
                    # Intentar extraer texto para verificar que no está corrupto
                    text_sample = first_page.extract_text()
                    metadata['primera_pagina_legible'] = True
                    metadata['tiene_texto'] = len(text_sample.strip()) > 0
                except:
                    metadata['primera_pagina_legible'] = False
                    metadata['tiene_texto'] = False
                
                return True, metadata
                
        except Exception as e:
            return False, f"Error con PyPDF2: {str(e)}"
    
    @staticmethod
    def _validar_estructura_manual(file_path: str) -> Tuple[bool, Dict[str, Any]]:
        """Validación manual básica sin librerías externas"""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                
                # Verificar que tenga elementos básicos de PDF
                if b'%%EOF' not in content:
                    return False, "PDF incompleto (no tiene marca de fin)"
                
                if b'xref' not in content:
                    return False, "PDF sin tabla de referencias cruzadas"
                
                metadata = {
                    'tamaño_contenido': len(content),
                    'tiene_eof': True,
                    'tiene_xref': True,
                    'metodo_validacion': 'manual'
                }
                
                # Contar páginas aproximadamente
                page_count = content.count(b'/Type /Page')
                metadata['num_paginas_aprox'] = page_count
                
                return True, metadata
                
        except Exception as e:
            return False, f"Error en validación manual: {str(e)}"
    
    @staticmethod
    def _calcular_hash(file_path: str) -> str:
        """Calcula hash MD5 del archivo para detección de duplicados"""
        hash_md5 = hashlib.md5()
        
        with open(file_path, 'rb') as f:
            # Leer en chunks para archivos grandes
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        
        return hash_md5.hexdigest()
    
    @staticmethod
    def _validar_seguridad(file_path: str) -> Tuple[bool, list]:
        """Verificaciones básicas de seguridad"""
        warnings = []
        
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                
                # Verificar contenido sospechoso
                suspicious_patterns = [
                    b'javascript:',
                    b'/JS',
                    b'/JavaScript',
                    b'/URI',
                    b'/Launch'
                ]
                
                for pattern in suspicious_patterns:
                    if pattern in content.lower():
                        warnings.append(f"Contenido potencialmente sospechoso detectado: {pattern.decode()}")
                
                return True, warnings
                
        except Exception as e:
            warnings.append(f"No se pudo verificar seguridad: {str(e)}")
            return True, warnings
    
    @staticmethod
    def validar_archivo_simple(file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validación rápida para uso en endpoints
        Returns: (es_valido, mensaje_error)
        """
        resultado = PDFValidator.validar_archivo_completo(file_path)
        
        if resultado['es_valido']:
            return True, None
        else:
            error_msg = '; '.join(resultado['errores'])
            return False, error_msg
    
    @staticmethod
    def obtener_resumen_validacion(resultado_validacion: Dict[str, Any]) -> str:
        """Genera un resumen legible de la validación"""
        if resultado_validacion['es_valido']:
            metadata = resultado_validacion['metadata']
            resumen = f"✅ PDF válido - {metadata.get('tamaño_mb', 0)}MB"
            
            if 'num_paginas' in metadata:
                resumen += f", {metadata['num_paginas']} páginas"
            elif 'num_paginas_aprox' in metadata:
                resumen += f", ~{metadata['num_paginas_aprox']} páginas"
            
            if 'version_pdf' in metadata:
                resumen += f", {metadata['version_pdf']}"
            
            return resumen
        else:
            errores = '; '.join(resultado_validacion['errores'])
            return f"❌ PDF inválido: {errores}"


class FileUploadValidator:
    """Validador para uploads de archivos desde formularios web"""
    
    @staticmethod
    def validar_upload(file_data, filename: str) -> Dict[str, Any]:
        """
        Valida archivo subido desde formulario web
        
        Args:
            file_data: Datos del archivo (FastAPI UploadFile o similar)
            filename: Nombre del archivo
            
        Returns:
            Dict con resultado de validación
        """
        resultado = {
            'es_valido': True,
            'errores': [],
            'warnings': [],
            'metadata': {'nombre_original': filename}
        }
        
        try:
            # Validar nombre de archivo
            if not filename:
                resultado['errores'].append("Nombre de archivo vacío")
                resultado['es_valido'] = False
                return resultado
            
            # Validar caracteres peligrosos en nombre
            dangerous_chars = ['..', '/', '\\', '<', '>', ':', '"', '|', '?', '*']
            for char in dangerous_chars:
                if char in filename:
                    resultado['warnings'].append(f"Carácter potencialmente peligroso en nombre: {char}")
            
            # Validar longitud de nombre
            if len(filename) > 255:
                resultado['errores'].append("Nombre de archivo demasiado largo")
                resultado['es_valido'] = False
            
            # Validar extensión
            if not filename.lower().endswith('.pdf'):
                resultado['errores'].append("Solo se permiten archivos PDF")
                resultado['es_valido'] = False
            
            resultado['metadata']['nombre_seguro'] = FileUploadValidator._generar_nombre_seguro(filename)
            
            return resultado
            
        except Exception as e:
            logger.error(f"Error validando upload: {e}")
            resultado['errores'].append(f"Error de validación: {str(e)}")
            resultado['es_valido'] = False
            return resultado
    
    @staticmethod
    def _generar_nombre_seguro(filename: str) -> str:
        """Genera un nombre de archivo seguro"""
        import re
        from datetime import datetime
        
        # Extraer nombre y extensión
        name, ext = os.path.splitext(filename)
        
        # Limpiar caracteres especiales
        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', name)
        
        # Limitar longitud
        if len(safe_name) > 100:
            safe_name = safe_name[:100]
        
        # Agregar timestamp para evitar duplicados
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        return f"{safe_name}_{timestamp}{ext.lower()}"