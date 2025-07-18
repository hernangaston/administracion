# -*- coding: utf-8 -*-
import os
import sqlite3
import logging
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles


from app_modules.api.facturas_routes import facturas_router
from app_modules.api.agente_routes import agente_router
from app_modules.api.reportes_routes import reportes_router
from app_modules.api.dashboard_routes import dashboard_router

from app_modules.core.config import setup_google_credentials
from app_modules.core.database import init_database
from auth_routes import auth_router
from auth import init_auth_tables

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

setup_google_credentials()

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
def startup():
    init_database()
    db = sqlite3.connect("database.db")
    init_auth_tables(db)
    db.close()
    logger.info("Sistema iniciado")

app.include_router(auth_router)

@app.get("/")
async def root():
    """Redirigir al login"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/auth/login")

app.include_router(facturas_router)
app.include_router(agente_router, prefix="/agente")
app.include_router(reportes_router, prefix="/reportes")
app.include_router(dashboard_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)    