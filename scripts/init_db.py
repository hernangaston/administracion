#!/usr/bin/env python3
"""
Script para inicializar la base de datos
Reemplaza al init_db.py actual
"""
import sys
import os

# Agregar el directorio padre al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import init_database
from app.core.config import setup_google_credentials

def main():
    print("Inicializando base de datos...")
    setup_google_credentials()
    init_database()
    print("✅ Base de datos inicializada correctamente")

if __name__ == "__main__":
    main()