# scripts/init_db.py

import os
import sys
import logging
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Cargar .env desde la raíz del proyecto
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=env_path)

# Añadir path del proyecto
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Importa todos los modelos (esto registra las tablas)
from app.models import Base, init_model_relationships
import app.models  # ← Forza todos los imports y relaciones

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("❌ DATABASE_URL no está definida en el archivo .env")
        return

    logger.info(f"🔌 Conectando a la base de datos en {db_url}")
    engine = create_engine(db_url)

    logger.info("🧱 Inicializando relaciones entre modelos...")
    init_model_relationships()

    logger.info("🛠️ Creando todas las tablas...")
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Base de datos creada con éxito.")

if __name__ == "__main__":
    init_db()
