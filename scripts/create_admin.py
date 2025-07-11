#!/usr/bin/env python3
"""
Script para crear usuario administrador
"""
import sys
import os
import sqlite3
from passlib.context import CryptContext

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_database_connection

def create_admin_user():
    conn = get_database_connection()
    cursor = conn.cursor()
    
    # Verificar si ya existe admin
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE role = 'admin'")
    if cursor.fetchone()[0] > 0:
        print("❗ Ya existe un usuario administrador")
        return
    
    # Crear admin
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    admin_password = pwd_context.hash("admin123")
    
    cursor.execute("""
        INSERT INTO usuarios (username, email, password_hash, role)
        VALUES (?, ?, ?, ?)
    """, ("admin", "admin@sistema.com", admin_password, "admin"))
    
    conn.commit()
    conn.close()
    print("✅ Usuario admin creado - User: admin, Pass: admin123")

if __name__ == "__main__":
    create_admin_user()