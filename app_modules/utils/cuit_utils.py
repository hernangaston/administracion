# -*- coding: utf-8 -*-
"""
Utilidades para manejo de CUIT argentino
NOTA: Este archivo reemplaza el cuit_utils.py de la raíz que tenía imports circulares
"""
import re
import logging

logger = logging.getLogger(__name__)

def limpiar_cuit(cuit):
    """
    Limpia el CUIT removiendo todos los caracteres no numéricos
    
    Args:
        cuit (str): CUIT a limpiar
        
    Returns:
        str: CUIT solo con números
    """
    if not cuit:
        return ""
    return re.sub(r'[^0-9]', '', str(cuit))

def formatear_cuit(cuit):
    """
    Formatea el CUIT agregando guiones (XX-XXXXXXXX-X)
    
    Args:
        cuit (str): CUIT a formatear
        
    Returns:
        str: CUIT formateado o el original si no es válido
    """
    if not cuit:
        return ""
        
    cuit_limpio = limpiar_cuit(cuit)
    if len(cuit_limpio) == 11:
        return f"{cuit_limpio[:2]}-{cuit_limpio[2:10]}-{cuit_limpio[10]}"
    
    # Si no tiene 11 dígitos, devolver el original
    return str(cuit)

def validar_cuit(cuit):
    """
    Valida que el CUIT tenga exactamente 11 dígitos
    
    Args:
        cuit (str): CUIT a validar
        
    Returns:
        bool: True si tiene 11 dígitos numéricos
    """
    if not cuit:
        return False
        
    cuit_limpio = limpiar_cuit(cuit)
    return len(cuit_limpio) == 11 and cuit_limpio.isdigit()

def calcular_digito_verificador(cuit):
    """
    Calcula el dígito verificador del CUIT argentino
    
    Args:
        cuit (str): CUIT sin dígito verificador (10 dígitos)
        
    Returns:
        int or None: Dígito verificador o None si es inválido
    """
    if not cuit:
        return None
        
    cuit_limpio = limpiar_cuit(cuit)
    
    if len(cuit_limpio) < 10:
        return None
        
    base = cuit_limpio[:10]
    multiplicadores = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    
    try:
        suma = sum(int(base[i]) * multiplicadores[i] for i in range(10))
        resto = suma % 11
        
        if resto == 0:
            return 0
        elif resto == 1:
            # Un resto de 1 indica un CUIT base inválido en la mayoría de los casos
            logger.warning(f"CUIT base '{base}' produce resto 1, generalmente inválido")
            return None
        else:
            return 11 - resto
            
    except (ValueError, IndexError) as e:
        logger.error(f"Error calculando dígito verificador para '{cuit}': {e}")
        return None

def validar_cuit_completo(cuit):
    """
    Valida completamente el CUIT incluyendo el dígito verificador
    
    Args:
        cuit (str): CUIT completo (11 dígitos)
        
    Returns:
        bool: True si el CUIT es válido con dígito verificador correcto
    """
    if not validar_cuit(cuit):
        return False
        
    cuit_limpio = limpiar_cuit(cuit)
    
    try:
        digito_calculado = calcular_digito_verificador(cuit_limpio)
        digito_ingresado = int(cuit_limpio[10])
        
        if digito_calculado is None:
            return False
            
        es_valido = digito_calculado == digito_ingresado
        
        if not es_valido:
            logger.debug(f"CUIT '{cuit}' inválido: esperado {digito_calculado}, recibido {digito_ingresado}")
            
        return es_valido
        
    except (ValueError, IndexError) as e:
        logger.error(f"Error validando CUIT completo '{cuit}': {e}")
        return False

def normalizar_cuit(cuit):
    """
    Normaliza un CUIT: limpia, valida y formatea
    
    Args:
        cuit (str): CUIT en cualquier formato
        
    Returns:
        dict: {
            'original': str,
            'limpio': str,
            'formateado': str,
            'es_valido': bool,
            'mensaje': str
        }
    """
    resultado = {
        'original': str(cuit) if cuit else '',
        'limpio': '',
        'formateado': '',
        'es_valido': False,
        'mensaje': ''
    }
    
    if not cuit:
        resultado['mensaje'] = 'CUIT vacío'
        return resultado
    
    # Limpiar
    cuit_limpio = limpiar_cuit(cuit)
    resultado['limpio'] = cuit_limpio
    
    # Validar longitud
    if len(cuit_limpio) != 11:
        resultado['mensaje'] = f'CUIT debe tener 11 dígitos, encontrados {len(cuit_limpio)}'
        return resultado
    
    # Formatear
    resultado['formateado'] = formatear_cuit(cuit_limpio)
    
    # Validar dígito verificador
    if validar_cuit_completo(cuit_limpio):
        resultado['es_valido'] = True
        resultado['mensaje'] = 'CUIT válido'
    else:
        resultado['mensaje'] = 'Dígito verificador incorrecto'
    
    return resultado

# Función de conveniencia para uso en templates
def obtener_cuit_formateado_o_original(cuit):
    """
    Devuelve el CUIT formateado si es válido, o el original si no
    Útil para mostrar en templates
    """
    if not cuit:
        return ""
    
    resultado = normalizar_cuit(cuit)
    return resultado['formateado'] if resultado['es_valido'] else resultado['original']