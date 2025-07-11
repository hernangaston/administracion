from dotenv import load_dotenv
import os

# Cargar variables de entorno
load_dotenv()

class Settings:
    # Google Document AI
    DOCAI_PROJECT_ID = os.getenv("DOCAI_PROJECT_ID")
    DOCAI_LOCATION = os.getenv("DOCAI_LOCATION", "us")
    DOCAI_PROCESSOR_ID = os.getenv("DOCAI_PROCESSOR_ID")
    
    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # Google Credentials
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    # Database
    DATABASE_URL = "database.db"
    
    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "tu-secret-key-aqui")
    ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Instancia global
settings = Settings()

# Función helper para configurar credenciales de Google
def setup_google_credentials():
    if settings.GOOGLE_APPLICATION_CREDENTIALS:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.GOOGLE_APPLICATION_CREDENTIALS