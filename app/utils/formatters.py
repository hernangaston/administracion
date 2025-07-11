def formatear_moneda(valor) -> str:
    """Formatea un número a string con formato de moneda argentina."""
    if valor is None:
        return ""
    try:
        # Formato: 1.234,56
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(valor)

def formatear_fecha(fecha_str: str) -> str:
    """Formatea una fecha para mostrar"""
    if not fecha_str:
        return "N/A"
    return fecha_str[:10]  # Solo la parte de fecha YYYY-MM-DD