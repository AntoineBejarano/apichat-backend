from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
from dotenv import load_dotenv

# Carga las variables de entorno desde .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set in environment variables")

# Crea el engine con la conexión a la base de datos
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Crea la sesión y el Base para los modelos
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependencia para inyectar la sesión en los endpoints
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
