# -*- coding: utf-8 -*-
"""
Rutas de autenticación para integrar con FastAPI
"""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import sqlite3

from auth import (
    UserCreate, UserLogin, Token, User,
    authenticate_user, create_access_token, create_refresh_token,
    store_refresh_token, get_current_user, init_auth_tables,
    create_user, ACCESS_TOKEN_EXPIRE_MINUTES, require_permission, require_role
)

# Router para las rutas de autenticación
auth_router = APIRouter(prefix="/auth", tags=["autenticación"])
templates = Jinja2Templates(directory="templates")

# Dependencia de base de datos (debe ser la misma que uses en app.py)
def get_db():
    db = sqlite3.connect("database.db", check_same_thread=False)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()

@auth_router.on_event("startup")
def startup_auth():
    """Inicializa las tablas de autenticación al arrancar"""
    db = sqlite3.connect("database.db")
    init_auth_tables(db)
    db.close()

# === RUTAS HTML (para interfaz web) ===

@auth_router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Página de login"""
    return templates.TemplateResponse("login.html", {"request": request})

@auth_router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Página de registro"""
    return templates.TemplateResponse("register.html", {"request": request})

@auth_router.post("/login")
async def login_form(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: sqlite3.Connection = Depends(get_db)
):
    """Procesa el formulario de login"""
    
    # Obtener información de la request
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    print(f"🔍 DEBUG: Intentando login para usuario: {username}")
    print(f"🔍 DEBUG: IP: {ip_address}, User-Agent: {user_agent[:50]}...")
    
    try:
        user = authenticate_user(db, username, password, ip_address, user_agent)
        print(f"🔍 DEBUG: Resultado authenticate_user: {user}")
        
        if not user:
            print("❌ DEBUG: Usuario no autenticado")
            return templates.TemplateResponse(
                "login.html", 
                {"request": request, "error": "Usuario o contraseña incorrectos"}
            )
        
        print("✅ DEBUG: Usuario autenticado exitosamente")
        
        # Crear tokens
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["username"], "user_id": user["id"], "role": user["role"]},
            expires_delta=access_token_expires
        )
        refresh_token = create_refresh_token(
            data={"sub": user["username"], "user_id": user["id"]}
        )
        
        print(f"🔍 DEBUG: Tokens creados, redirigiendo a /")
        
        # Guardar refresh token
        store_refresh_token(db, user["id"], refresh_token)
        
        # Crear respuesta con redirección AL DASHBOARD
        response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

        # Establecer cookies seguras
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            secure=False,
            samesite="lax")
        
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            max_age=7 * 24 * 60 * 60,  # 7 días
            secure=False,
            samesite="lax")
        
        print("🔍 DEBUG: Respuesta de redirección creada")
        return response
        
    except HTTPException as e:
        print(f"❌ DEBUG: HTTPException: {e.status_code} - {e.detail}")
        # Manejar cuenta bloqueada
        if e.status_code == 423:  # HTTP_423_LOCKED
            return templates.TemplateResponse(
                "login.html", 
                {"request": request, "error": e.detail, "account_locked": True}
            )
        raise e
    except Exception as e:
        print(f"❌ DEBUG: Error inesperado: {e}")
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "Error interno del servidor"}
        )
@auth_router.post("/register")
async def register_form(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(default="cliente"),
    cuit_asociado: str = Form(default=""),
    db: sqlite3.Connection = Depends(get_db)
):
    """Procesa el formulario de registro"""
    try:
        user_data = UserCreate(
            username=username,
            email=email,
            password=password,
            role=role,
            cuit_asociado=cuit_asociado if cuit_asociado else None
        )
        
        user = create_user(db, user_data)
        
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "success": "Usuario creado exitosamente. Puedes iniciar sesión."}
        )
        
    except HTTPException as e:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": e.detail}
        )

@auth_router.get("/logout")
async def logout():
    """Cierra sesión del usuario"""
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    return response

# === RUTAS API (para uso programático) ===

@auth_router.post("/api/login", response_model=Token)
async def api_login(
    user_credentials: UserLogin,
    db: sqlite3.Connection = Depends(get_db)
):
    """API de login que devuelve tokens JWT"""
    user = authenticate_user(db, user_credentials.username, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"], "user_id": user["id"], "role": user["role"]},
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(
        data={"sub": user["username"], "user_id": user["id"]}
    )
    
    store_refresh_token(db, user["id"], refresh_token)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

@auth_router.post("/api/register", response_model=User)
async def api_register(
    user_data: UserCreate,
    db: sqlite3.Connection = Depends(get_db)
):
    """API de registro de usuarios"""
    return create_user(db, user_data)

@auth_router.get("/api/profile", response_model=User)
async def get_profile(
    current_user_data = Depends(get_current_user)
):
    """Obtiene el perfil del usuario actual"""
    current_user, _ = current_user_data
    return current_user

@auth_router.get("/api/users")
@require_permission("usuarios:read")
async def list_users(
    current_user_data = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db)
):
    """Lista todos los usuarios (solo admins)"""
    cursor = db.cursor()
    cursor.execute("""
        SELECT id, username, email, role, is_active, cuit_asociado, created_at
        FROM usuarios WHERE is_active = TRUE
        ORDER BY created_at DESC
    """)
    
    users = []
    for row in cursor.fetchall():
        users.append({
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "role": row[3],
            "is_active": bool(row[4]),
            "cuit_asociado": row[5],
            "created_at": row[6]
        })
    
    return {"users": users}

# === MIDDLEWARES PARA VERIFICAR AUTENTICACIÓN ===

def get_current_user_from_cookie(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """
    Función helper para obtener usuario desde cookies
    Útil para rutas HTML que no usan Authorization header
    """
    token = request.cookies.get("access_token")
    if not token:
        return None
    
    if token.startswith("Bearer "):
        token = token[7:]
    
    try:
        from auth import verify_token, get_user_by_id
        token_data = verify_token(token)
        user = get_user_by_id(db, token_data.user_id)
        return user, token_data
    except:
        return None

def require_auth_cookie(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """
    Dependencia que requiere autenticación vía cookie
    Para usar en rutas HTML
    """
    user_data = get_current_user_from_cookie(request, db)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            detail="Autenticación requerida",
            headers={"Location": "/auth/login"}
        )
    return user_data