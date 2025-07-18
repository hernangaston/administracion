# -*- coding: utf-8 -*-
"""
Sistema unificado de manejo de fechas para el sistema de facturas
Reemplaza las múltiples funciones dispersas de formateo de fechas
"""

from datetime import datetime, date
from typing import Optional, Union, Dict, Any
import logging
import re

logger = logging.getLogger(__name__)

class DateFormatter:
    """Manejo centralizado y robusto de fechas"""
    
    # Formatos de entrada soportados (orden de prioridad)
    FORMATOS_ENTRADA = [
        '%Y-%m-%d',           # 2024-01-15 (ISO estándar)
        '%Y-%m-%d %H:%M:%S',  # 2024-01-15 10:30:00 (SQLite datetime)
        '%Y-%m-%d %H:%M:%S.%f', # 2024-01-15 10:30:00.123456 (con microsegundos)
        '%d/%m/%Y',           # 15/01/2024 (formato argentino)
        '%d-%m-%Y',           # 15-01-2024
        '%Y/%m/%d',           # 2024/01/15
        '%d/%m/%y',           # 15/01/24
        '%d-%m-%y',           # 15-01-24
    ]
    
    # Patrones regex para extracción flexible
    PATRONES_FECHA = [
        r'(\d{4})-(\d{1,2})-(\d{1,2})',      # YYYY-MM-DD
        r'(\d{1,2})/(\d{1,2})/(\d{4})',      # DD/MM/YYYY
        r'(\d{1,2})-(\d{1,2})-(\d{4})',      # DD-MM-YYYY
        r'(\d{4})/(\d{1,2})/(\d{1,2})',      # YYYY/MM/DD
    ]
    
    # Meses en español para parsing
    MESES_ESPANOL = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
        'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
        'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
        'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4,
        'may': 5, 'jun': 6, 'jul': 7, 'ago': 8,
        'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12
    }

    @staticmethod
    def parsear_fecha(fecha_input: Union[str, datetime, date, None]) -> Optional[datetime]:
        """
        Parsea una fecha de múltiples formatos a datetime
        
        Args:
            fecha_input: Fecha en cualquier formato soportado
            
        Returns:
            datetime object o None si no se puede parsear
        """
        if not fecha_input:
            return None
            
        # Si ya es datetime, devolverlo
        if isinstance(fecha_input, datetime):
            return fecha_input
            
        # Si es date, convertir a datetime
        if isinstance(fecha_input, date):
            return datetime.combine(fecha_input, datetime.min.time())
        
        # Convertir a string y limpiar
        fecha_str = str(fecha_input).strip()
        
        if not fecha_str or fecha_str.lower() in ['none', 'null', '', 'sin fecha']:
            return None
        
        try:
            # 1. Intentar parsing directo con formatos conocidos
            fecha_obj = DateFormatter._parsear_formato_directo(fecha_str)
            if fecha_obj:
                return fecha_obj
            
            # 2. Intentar extracción con regex
            fecha_obj = DateFormatter._parsear_con_regex(fecha_str)
            if fecha_obj:
                return fecha_obj
            
            # 3. Intentar parsing de texto en español
            fecha_obj = DateFormatter._parsear_texto_espanol(fecha_str)
            if fecha_obj:
                return fecha_obj
            
            # 4. Manejo de formatos ISO con T
            fecha_obj = DateFormatter._parsear_iso_formato(fecha_str)
            if fecha_obj:
                return fecha_obj
                
            logger.warning(f"No se pudo parsear fecha: '{fecha_str}'")
            return None
            
        except Exception as e:
            logger.error(f"Error parseando fecha '{fecha_str}': {e}")
            return None
    
    @staticmethod
    def _parsear_formato_directo(fecha_str: str) -> Optional[datetime]:
        """Intenta parsear con formatos predefinidos"""
        for formato in DateFormatter.FORMATOS_ENTRADA:
            try:
                return datetime.strptime(fecha_str, formato)
            except ValueError:
                continue
        return None
    
    @staticmethod
    def _parsear_con_regex(fecha_str: str) -> Optional[datetime]:
        """Intenta extraer fecha usando patrones regex"""
        for patron in DateFormatter.PATRONES_FECHA:
            match = re.search(patron, fecha_str)
            if match:
                grupos = match.groups()
                try:
                    if patron.startswith(r'(\d{4})'):  # YYYY-MM-DD o YYYY/MM/DD
                        año, mes, dia = map(int, grupos)
                    else:  # DD/MM/YYYY o DD-MM-YYYY
                        dia, mes, año = map(int, grupos)
                    
                    return datetime(año, mes, dia)
                except (ValueError, TypeError):
                    continue
        return None
    
    @staticmethod
    def _parsear_texto_espanol(fecha_str: str) -> Optional[datetime]:
        """Parsea fechas en formato texto español: '15 de enero de 2024'"""
        # Patrón para "DD de MES de YYYY"
        patron = r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})'
        match = re.search(patron, fecha_str.lower())
        
        if match:
            dia_str, mes_str, año_str = match.groups()
            mes_num = DateFormatter.MESES_ESPANOL.get(mes_str.lower())
            
            if mes_num:
                try:
                    return datetime(int(año_str), mes_num, int(dia_str))
                except ValueError:
                    pass
        
        return None
    
    @staticmethod
    def _parsear_iso_formato(fecha_str: str) -> Optional[datetime]:
        """Maneja formatos ISO con T y timezone"""
        if 'T' in fecha_str:
            # Extraer solo la parte de fecha
            fecha_parte = fecha_str.split('T')[0]
            try:
                return datetime.strptime(fecha_parte, '%Y-%m-%d')
            except ValueError:
                pass
        
        return None
    
    @staticmethod
    def formatear_para_display(fecha_input: Union[str, datetime, date, None], 
                              formato: str = "dd/mm/yyyy") -> str:
        """
        Formatea una fecha para mostrar en la UI
        
        Args:
            fecha_input: Fecha en cualquier formato
            formato: Formato de salida ('dd/mm/yyyy', 'yyyy-mm-dd', 'texto')
            
        Returns:
            Fecha formateada como string
        """
        fecha_obj = DateFormatter.parsear_fecha(fecha_input)
        
        if not fecha_obj:
            return "Sin fecha"
        
        try:
            if formato == "dd/mm/yyyy":
                return fecha_obj.strftime('%d/%m/%Y')
            elif formato == "yyyy-mm-dd":
                return fecha_obj.strftime('%Y-%m-%d')
            elif formato == "texto":
                meses = [
                    '', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
                ]
                return f"{fecha_obj.day} de {meses[fecha_obj.month]} de {fecha_obj.year}"
            else:
                return fecha_obj.strftime(formato)
                
        except Exception as e:
            logger.warning(f"Error formateando fecha {fecha_obj}: {e}")
            return str(fecha_input) if fecha_input else "Error fecha"
    
    @staticmethod
    def formatear_para_bd(fecha_input: Union[str, datetime, date, None]) -> Optional[str]:
        """
        Formatea una fecha para guardar en base de datos (formato ISO)
        
        Returns:
            Fecha en formato YYYY-MM-DD o None
        """
        fecha_obj = DateFormatter.parsear_fecha(fecha_input)
        
        if not fecha_obj:
            return None
        
        return fecha_obj.strftime('%Y-%m-%d')
    
    @staticmethod
    def es_fecha_valida(fecha_input: Union[str, datetime, date, None]) -> bool:
        """Verifica si una fecha es válida y parseable"""
        return DateFormatter.parsear_fecha(fecha_input) is not None
    
    @staticmethod
    def calcular_diferencia_dias(fecha1: Union[str, datetime, date, None], 
                                fecha2: Union[str, datetime, date, None]) -> Optional[int]:
        """
        Calcula la diferencia en días entre dos fechas
        
        Returns:
            Número de días (positivo si fecha2 > fecha1) o None si hay error
        """
        try:
            dt1 = DateFormatter.parsear_fecha(fecha1)
            dt2 = DateFormatter.parsear_fecha(fecha2)
            
            if not dt1 or not dt2:
                return None
            
            diferencia = dt2.date() - dt1.date()
            return diferencia.days
            
        except Exception as e:
            logger.error(f"Error calculando diferencia entre fechas: {e}")
            return None
    
    @staticmethod
    def obtener_fecha_actual() -> datetime:
        """Obtiene la fecha actual del sistema"""
        return datetime.now()
    
    @staticmethod
    def obtener_fecha_actual_formateada(formato: str = "dd/mm/yyyy") -> str:
        """Obtiene la fecha actual formateada"""
        return DateFormatter.formatear_para_display(datetime.now(), formato)
    
    @staticmethod
    def validar_rango_fechas(fecha_inicio: Union[str, datetime, date, None],
                            fecha_fin: Union[str, datetime, date, None]) -> Dict[str, Any]:
        """
        Valida un rango de fechas
        
        Returns:
            Dict con resultado de validación
        """
        resultado = {
            'es_valido': True,
            'errores': [],
            'fecha_inicio_parseada': None,
            'fecha_fin_parseada': None
        }
        
        # Parsear fechas
        dt_inicio = DateFormatter.parsear_fecha(fecha_inicio)
        dt_fin = DateFormatter.parsear_fecha(fecha_fin)
        
        resultado['fecha_inicio_parseada'] = dt_inicio
        resultado['fecha_fin_parseada'] = dt_fin
        
        # Validaciones
        if not dt_inicio:
            resultado['errores'].append('Fecha de inicio inválida')
            resultado['es_valido'] = False
        
        if not dt_fin:
            resultado['errores'].append('Fecha de fin inválida')
            resultado['es_valido'] = False
        
        if dt_inicio and dt_fin:
            if dt_inicio > dt_fin:
                resultado['errores'].append('Fecha de inicio debe ser anterior a fecha de fin')
                resultado['es_valido'] = False
            
            # Verificar rango razonable (no más de 10 años)
            diferencia = DateFormatter.calcular_diferencia_dias(dt_inicio, dt_fin)
            if diferencia and diferencia > 3650:  # 10 años
                resultado['errores'].append('Rango de fechas demasiado amplio (máximo 10 años)')
                resultado['es_valido'] = False
        
        return resultado


class FechaFactura:
    """Clase específica para manejo de fechas en facturas"""
    
    @staticmethod
    def extraer_fecha_desde_texto(texto: str) -> Optional[datetime]:
        """
        Extrae fecha de factura desde texto OCR
        Busca patrones comunes en facturas argentinas
        """
        if not texto:
            return None
        
        # Patrones específicos de facturas
        patrones_factura = [
            r'fecha[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',  # "Fecha: 15/01/2024"
            r'emisi[óo]n[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',  # "Emisión: 15/01/2024"
            r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',  # Cualquier fecha en el texto
        ]
        
        for patron in patrones_factura:
            matches = re.finditer(patron, texto.lower())
            for match in matches:
                fecha_str = match.group(1) if match.groups() else match.group(0)
                fecha_obj = DateFormatter.parsear_fecha(fecha_str)
                if fecha_obj:
                    # Verificar que sea una fecha razonable (últimos 10 años, próximos 2 años)
                    año_actual = datetime.now().year
                    if (año_actual - 10) <= fecha_obj.year <= (año_actual + 2):
                        return fecha_obj
        
        return None
    
    @staticmethod
    def validar_fecha_factura(fecha: Union[str, datetime, date, None]) -> Dict[str, Any]:
        """
        Valida específicamente una fecha de factura
        
        Returns:
            Dict con resultado de validación específico para facturas
        """
        resultado = {
            'es_valida': True,
            'errores': [],
            'warnings': [],
            'fecha_parseada': None
        }
        
        fecha_obj = DateFormatter.parsear_fecha(fecha)
        resultado['fecha_parseada'] = fecha_obj
        
        if not fecha_obj:
            resultado['errores'].append('Fecha de factura inválida o no reconocida')
            resultado['es_valida'] = False
            return resultado
        
        # Validaciones específicas para facturas
        ahora = datetime.now()
        
        # No puede ser futura (con margen de 1 día)
        if fecha_obj.date() > (ahora.date()):
            resultado['errores'].append('La fecha de factura no puede ser futura')
            resultado['es_valida'] = False
        
        # No puede ser muy antigua (más de 10 años)
        años_diferencia = ahora.year - fecha_obj.year
        if años_diferencia > 10:
            resultado['warnings'].append(f'Fecha de factura muy antigua ({años_diferencia} años)')
        
        # Verificar año razonable
        if fecha_obj.year < 2000:
            resultado['errores'].append('Año de factura demasiado antiguo')
            resultado['es_valida'] = False
        
        return resultado
    
    @staticmethod
    def obtener_periodo_fiscal(fecha: Union[str, datetime, date, None]) -> Optional[str]:
        """
        Obtiene el período fiscal de una fecha (YYYY-MM)
        Útil para agrupaciones y reportes
        """
        fecha_obj = DateFormatter.parsear_fecha(fecha)
        if fecha_obj:
            return fecha_obj.strftime('%Y-%m')
        return None


# Funciones de conveniencia para mantener compatibilidad
def formatear_fecha_display(fecha) -> str:
    """Función de conveniencia para formateo de display"""
    return DateFormatter.formatear_para_display(fecha)

def formatear_fecha_bd(fecha) -> Optional[str]:
    """Función de conveniencia para formateo de BD"""
    return DateFormatter.formatear_para_bd(fecha)

def es_fecha_valida(fecha) -> bool:
    """Función de conveniencia para validación"""
    return DateFormatter.es_fecha_valida(fecha)