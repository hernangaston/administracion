# -*- coding: utf-8 -*-
"""
Módulo de autenticación y autorización para el sistema de facturas
Implementa JWT + RBAC (Role-Based Access Control)
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import sqlite3
import hashlib
import secrets
from functools import wraps

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import logging
import re

logger = logging.getLogger(__name__)

# Configuración
SECRET_KEY = secrets.token_urlsafe(32)  # En producción, usar variable de entorno
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Configuración de hash de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Roles y permisos del sistema
ROLES_PERMISOS = {
    "admin": [
        "facturas:create", "facturas:read", "facturas:update", "facturas:delete",
        "usuarios:create", "usuarios:read", "usuarios:update", "usuarios:delete",
        "reportes:read", "sistema:config"
    ],
    "contador": [
        "facturas:create", "facturas:read", "facturas:update",
        "reportes:read"
    ],
    "vendedor": [
        "facturas:create", "facturas:read"
    ],
    "cliente": [
        "facturas:read_own"  # Solo sus propias facturas
    ],
    "auditor": [
        "facturas:read", "reportes:read"
    ]
}

# Modelos Pydantic
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "cliente"
    cuit_asociado: Optional[str] = None  # Para clientes, asociar con CUIT

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[str] = None
    permissions: List[str] = []

class User(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    cuit_asociado: Optional[str] = None
    created_at: datetime

# Funciones de utilidad para contraseñas
def hash_password(password: str) -> str:
    """Hashea una contraseña"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contraseña contra su hash"""
    return pwd_context.verify(plain_password, hashed_password)

# Funciones JWT
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Crea un token de acceso JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    """Crea un token de refresco JWT"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> TokenData:
    """Verifica y decodifica un token JWT"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        role: str = payload.get("role")
        
        if username is None or user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Obtener permisos del rol
        permissions = ROLES_PERMISOS.get(role, [])
        
        return TokenData(
            username=username, 
            user_id=user_id, 
            role=role, 
            permissions=permissions
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Funciones de base de datos
def init_auth_tables(db: sqlite3.Connection):
    """Inicializa las tablas de autenticación"""
    cursor = db.cursor()
    
    # Tabla de usuarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'cliente',
            is_active BOOLEAN DEFAULT TRUE,
            cuit_asociado TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Tabla de tokens de refresco
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES usuarios (id) ON DELETE CASCADE
        );
    """)
    
    # Crear usuario admin por defecto si no existe
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE role = 'admin'")
    admin_count = cursor.fetchone()[0]
    
    if admin_count == 0:
        admin_password = hash_password("admin123")  # Cambiar en producción
        cursor.execute("""
            INSERT INTO usuarios (username, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        """, ("admin", "admin@sistema.com", admin_password, "admin"))
        logger.info("Usuario admin creado con contraseña 'admin123'")
    
     # NUEVA TABLA: Historial de intentos de login
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            success BOOLEAN NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            failure_reason TEXT
        );
    """)
    
    # NUEVA TABLA: Cuentas bloqueadas temporalmente
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS account_lockouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            locked_until TIMESTAMP NOT NULL,
            attempts_count INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    db.commit()

def create_user(db: sqlite3.Connection, user_data: UserCreate) -> User:
    """Crea un nuevo usuario"""
    cursor = db.cursor()
    
    # NUEVA VALIDACIÓN DE CONTRASEÑA
    password_check = AuthEnhancer.validate_password_strength(user_data.password)
    if not password_check['is_strong']:
        feedback = AuthEnhancer.get_password_feedback(password_check)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contraseña no cumple requisitos: {', '.join(feedback)}"
        )
    
    # Verificar que el rol existe
    if user_data.role not in ROLES_PERMISOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rol '{user_data.role}' no válido"
        )
    
    # Hash de la contraseña
    hashed_password = hash_password(user_data.password)
    
    try:
        cursor.execute("""
            INSERT INTO usuarios (username, email, password_hash, role, cuit_asociado)
            VALUES (?, ?, ?, ?, ?)
        """, (user_data.username, user_data.email, hashed_password, 
              user_data.role, user_data.cuit_asociado))
        
        user_id = cursor.lastrowid
        db.commit()
        
        # Obtener el usuario creado
        return get_user_by_id(db, user_id)
        
    except sqlite3.IntegrityError as e:
        if "username" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El nombre de usuario ya existe"
            )
        elif "email" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está registrado"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error al crear usuario"
            )

def get_user_by_username(db: sqlite3.Connection, username: str) -> Optional[Dict]:
    """Obtiene un usuario por nombre de usuario"""
    cursor = db.cursor()
    cursor.execute("""
        SELECT id, username, email, password_hash, role, is_active, cuit_asociado, created_at
        FROM usuarios WHERE username = ? AND is_active = TRUE
    """, (username,))
    
    row = cursor.fetchone()
    if row:
        return {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "password_hash": row[3],
            "role": row[4],
            "is_active": bool(row[5]),
            "cuit_asociado": row[6],
            "created_at": row[7]
        }
    return None

def get_user_by_id(db: sqlite3.Connection, user_id: int) -> User:
    """Obtiene un usuario por ID"""
    cursor = db.cursor()
    cursor.execute("""
        SELECT id, username, email, role, is_active, cuit_asociado, created_at
        FROM usuarios WHERE id = ? AND is_active = TRUE
    """, (user_id,))
    
    row = cursor.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    return User(
        id=row[0],
        username=row[1],
        email=row[2],
        role=row[3],
        is_active=bool(row[4]),
        cuit_asociado=row[5],
        created_at=datetime.fromisoformat(row[6]) if row[6] else datetime.now()
    )

def authenticate_user(db: sqlite3.Connection, username: str, password: str, 
                     ip_address: str = None, user_agent: str = None) -> Optional[Dict]:
    """Autentica un usuario con protección contra ataques"""
    
    print(f"🔍 AUTH DEBUG: Iniciando autenticación para {username}")
    
    # 1. Verificar si la cuenta está bloqueada
    lockout_info = AuthEnhancer.is_account_locked(db, username)
    if lockout_info["is_locked"]:
        print(f"🔒 AUTH DEBUG: Cuenta bloqueada hasta {lockout_info['locked_until']}")
        AuthEnhancer.log_login_attempt(
            db, username, False, ip_address, user_agent, 
            f"account_locked_until_{lockout_info['locked_until']}"
        )
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Cuenta bloqueada por seguridad. Intenta en {lockout_info['minutes_remaining']} minutos."
        )
    
    # 2. Buscar usuario
    user = get_user_by_username(db, username)
    if not user:
        print(f"❌ AUTH DEBUG: Usuario {username} no encontrado")
        AuthEnhancer.log_login_attempt(
            db, username, False, ip_address, user_agent, "user_not_found"
        )
        return None
    
    print(f"👤 AUTH DEBUG: Usuario encontrado: {user['username']}")
    
    # 3. Verificar contraseña
    if not verify_password(password, user["password_hash"]):
        print(f"❌ AUTH DEBUG: Contraseña incorrecta para {username}")
        AuthEnhancer.log_login_attempt(
            db, username, False, ip_address, user_agent, "invalid_password"
        )
        
        # Verificar si se debe bloquear la cuenta
        if AuthEnhancer.should_lock_account(db, username):
            print(f"🔒 AUTH DEBUG: Bloqueando cuenta {username}")
            AuthEnhancer.lock_account(db, username, 5)
        
        return None
    
    print(f"✅ AUTH DEBUG: Contraseña correcta para {username}")
    
    # 4. Login exitoso
    AuthEnhancer.log_login_attempt(
        db, username, True, ip_address, user_agent, None
    )
    
    # Limpiar intentos fallidos anteriores
    AuthEnhancer.clear_failed_attempts(db, username)
    
    print(f"🎉 AUTH DEBUG: Login exitoso para {username}")
    return user

def store_refresh_token(db: sqlite3.Connection, user_id: int, refresh_token: str):
    """Almacena un token de refresco en la base de datos"""
    cursor = db.cursor()
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    cursor.execute("""
        INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
        VALUES (?, ?, ?)
    """, (user_id, token_hash, expires_at))
    
    db.commit()

# Dependencias de FastAPI
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: sqlite3.Connection = Depends(lambda: None)  # Se debe proveer la dependencia de DB
):
    """Dependencia para obtener el usuario actual del token"""
    token_data = verify_token(credentials.credentials)
    user = get_user_by_id(db, token_data.user_id)
    return user, token_data

def require_permission(required_permission: str):
    """Decorador que requiere un permiso específico"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Buscar user_data en kwargs (viene de get_current_user)
            user_data = None
            token_data = None
            
            for key, value in kwargs.items():
                if isinstance(value, tuple) and len(value) == 2:
                    if hasattr(value[0], 'role') and hasattr(value[1], 'permissions'):
                        user_data, token_data = value
                        break
            
            if not user_data or not token_data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Autenticación requerida"
                )
            
            if required_permission not in token_data.permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permiso '{required_permission}' requerido"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def require_role(required_roles: List[str]):
    """Decorador que requiere uno de los roles especificados"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user_data = None
            
            for key, value in kwargs.items():
                if isinstance(value, tuple) and len(value) == 2:
                    if hasattr(value[0], 'role'):
                        user_data = value[0]
                        break
            
            if not user_data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Autenticación requerida"
                )
            
            if user_data.role not in required_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Se requiere uno de estos roles: {', '.join(required_roles)}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Función para verificar acceso a facturas específicas
def can_access_factura(user: User, token_data: TokenData, factura_cuit: str) -> bool:

    """Verifica si un usuario puede acceder a una factura específica"""
    # Admin y auditor pueden ver todo
    if user.role in ["admin", "auditor"]:
        return True
    
    # Contador y vendedor pueden ver todas las facturas
    if user.role in ["contador", "vendedor"]:
        return True
    
    # Cliente solo puede ver facturas de su CUIT
    if user.role == "cliente":
        if user.cuit_asociado and user.cuit_asociado == factura_cuit:
            return True
        return False
    
    return False

class AuthEnhancer:
    """Mejoras de seguridad para el sistema de autenticación"""
    
    @staticmethod
    def validate_password_strength(password: str) -> Dict[str, bool]:
        """Valida la fortaleza de la contraseña"""
        checks = {
            'length': len(password) >= 8,
            'uppercase': bool(re.search(r'[A-Z]', password)),
            'lowercase': bool(re.search(r'[a-z]', password)),
            'numbers': bool(re.search(r'\d', password)),
            'special': bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password))
        }
        
        checks['score'] = sum(checks.values())
        checks['is_strong'] = checks['score'] >= 4
        
        return checks
    
    @staticmethod
    def generate_password_requirements_message() -> str:
        """Genera mensaje de requisitos de contraseña"""
        return """
        La contraseña debe tener:
        • Al menos 8 caracteres
        • Al menos una mayúscula
        • Al menos una minúscula  
        • Al menos un número
        • Al menos un carácter especial (!@#$%^&*(),.?":{}|<>)
        """
    
    @staticmethod
    def check_password_history(db, user_id: int, new_password_hash: str, limit: int = 5) -> bool:
        """Evita reutilización de contraseñas recientes"""
        cursor = db.cursor()
        cursor.execute("""
            SELECT password_hash FROM password_history 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (user_id, limit))
        
        recent_passwords = [row[0] for row in cursor.fetchall()]
        return new_password_hash not in recent_passwords
    
    @staticmethod
    def log_failed_attempt(db, username: str, ip_address: str):
        """Registra intento fallido de login"""
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO login_attempts (username, ip_address, success, timestamp)
            VALUES (?, ?, FALSE, ?)
        """, (username, ip_address, datetime.utcnow()))
        db.commit()
    
    @staticmethod
    def is_account_locked(db, username: str, lockout_minutes: int = 15, max_attempts: int = 5) -> bool:
        """Verifica si la cuenta está bloqueada por múltiples intentos fallidos"""
        cursor = db.cursor()
        since = datetime.utcnow() - timedelta(minutes=lockout_minutes)
        
        cursor.execute("""
            SELECT COUNT(*) FROM login_attempts 
            WHERE username = ? AND success = FALSE AND timestamp > ?
        """, (username, since))
        
        failed_attempts = cursor.fetchone()[0]
        return failed_attempts >= max_attempts
    
    @staticmethod
    def get_password_feedback(checks: Dict[str, bool]) -> List[str]:
        """Genera lista de mejoras para la contraseña"""
        feedback = []
        
        if not checks['length']:
            feedback.append("Debe tener al menos 8 caracteres")
        if not checks['uppercase']:
            feedback.append("Debe incluir al menos una mayúscula")
        if not checks['lowercase']:
            feedback.append("Debe incluir al menos una minúscula")
        if not checks['numbers']:
            feedback.append("Debe incluir al menos un número")
        if not checks['special']:
            feedback.append("Debe incluir al menos un carácter especial (!@#$%^&*)")
            
        return feedback
    
    @staticmethod
    def log_login_attempt(db, username: str, success: bool, ip_address: str = None, 
                         user_agent: str = None, failure_reason: str = None):
        """Registra intento de login"""
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO login_attempts (username, ip_address, user_agent, success, failure_reason)
            VALUES (?, ?, ?, ?, ?)
        """, (username, ip_address, user_agent, success, failure_reason))
        db.commit()
    
    @staticmethod
    def get_recent_failed_attempts(db, username: str, minutes: int = 15) -> int:
        """Cuenta intentos fallidos recientes"""
        cursor = db.cursor()
        since = datetime.utcnow() - timedelta(minutes=minutes)
        
        cursor.execute("""
            SELECT COUNT(*) FROM login_attempts 
            WHERE username = ? AND success = FALSE AND timestamp > ?
        """, (username, since))
        
        return cursor.fetchone()[0]
    
    @staticmethod
    def is_account_locked(db, username: str) -> Dict:
        """Verifica si la cuenta está bloqueada"""
        cursor = db.cursor()
        
        # Verificar bloqueo activo
        cursor.execute("""
            SELECT locked_until, attempts_count FROM account_lockouts 
            WHERE username = ? AND locked_until > datetime('now')
            ORDER BY created_at DESC LIMIT 1
        """, (username,))
        
        result = cursor.fetchone()
        if result:
            locked_until, attempts = result
            return {
                "is_locked": True,
                "locked_until": locked_until,
                "attempts_count": attempts,
                "minutes_remaining": int((datetime.fromisoformat(locked_until) - datetime.utcnow()).total_seconds() / 60)
            }
        
        return {"is_locked": False}
    
    @staticmethod
    def lock_account(db, username: str, attempts_count: int, lockout_minutes: int = 15):
        """Bloquea una cuenta temporalmente"""
        cursor = db.cursor()
        locked_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)
        
        cursor.execute("""
            INSERT INTO account_lockouts (username, locked_until, attempts_count)
            VALUES (?, ?, ?)
        """, (username, locked_until, attempts_count))
        db.commit()
        
        logger.warning(f"Cuenta bloqueada: {username} por {lockout_minutes} minutos ({attempts_count} intentos)")
    
    @staticmethod
    def should_lock_account(db, username: str, max_attempts: int = 5, window_minutes: int = 15) -> bool:
        """Determina si se debe bloquear la cuenta"""
        failed_attempts = AuthEnhancer.get_recent_failed_attempts(db, username, window_minutes)
        return failed_attempts >= max_attempts
    
    @staticmethod
    def clear_failed_attempts(db, username: str):
        """Limpia intentos fallidos después de login exitoso"""
        cursor = db.cursor()
        # Marcar como resueltos (no eliminar para auditoría)
        cursor.execute("""
            UPDATE login_attempts 
            SET failure_reason = 'resolved_by_successful_login'
            WHERE username = ? AND success = FALSE AND failure_reason IS NULL
        """, (username,))
        db.commit()


class TwoFactorAuth:
    """Implementación de autenticación de dos factores"""
    
    @staticmethod
    def generate_totp_secret() -> str:
        """Genera secreto para TOTP (Google Authenticator)"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def generate_backup_codes(count: int = 10) -> List[str]:
        """Genera códigos de respaldo"""
        return [secrets.token_hex(4).upper() for _ in range(count)]
    
    @staticmethod
    def send_sms_code(phone_number: str) -> str:
        """Envía código por SMS (implementar con Twilio/etc)"""
        code = str(secrets.randbelow(900000) + 100000)  # 6 dígitos
        # TODO: Integrar con servicio SMS
        print(f"Código SMS para {phone_number}: {code}")
        return code