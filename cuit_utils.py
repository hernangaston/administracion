import re

def limpiar_cuit(cuit):
    """
    Limpia el CUIT removiendo todos los caracteres no numéricos
    """
    if not cuit:
        return ""
    return re.sub(r'[^0-9]', '', str(cuit))

def formatear_cuit(cuit):
    """
    Formatea el CUIT agregando guiones (XX-XXXXXXXX-X)
    """
    cuit_limpio = limpiar_cuit(cuit)
    if len(cuit_limpio) == 11:
        return f"{cuit_limpio[:2]}-{cuit_limpio[2:10]}-{cuit_limpio[10]}"
    return cuit

def validar_cuit(cuit):
    """
    Valida que el CUIT tenga exactamente 11 dígitos
    """
    cuit_limpio = limpiar_cuit(cuit)
    return len(cuit_limpio) == 11 and cuit_limpio.isdigit()

def calcular_digito_verificador(cuit):
    """
    Calcula el dígito verificador del CUIT argentino
    """
    cuit_limpio = limpiar_cuit(cuit)
    
    if not cuit_limpio or len(cuit_limpio) < 10:
        return None
        
    base = cuit_limpio[:10]
    multiplicadores = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(int(base[i]) * multiplicadores[i] for i in range(10))
    
    resto = suma % 11
    
    if resto == 0:
        return 0
    elif resto == 1:
        # Un resto de 1 indica un CUIT base inválido en la mayoría de los casos.
        return None
    else:
        return 11 - resto

def validar_cuit_completo(cuit):
    """
    Valida completamente el CUIT incluyendo el dígito verificador
    """
    if not validar_cuit(cuit):
        return False
        
    cuit_limpio = limpiar_cuit(cuit)
    digito_calculado = calcular_digito_verificador(cuit_limpio)
    digito_ingresado = int(cuit_limpio[10])
    
    if digito_calculado is None:
        return False
        
    return digito_calculado == digito_ingresado