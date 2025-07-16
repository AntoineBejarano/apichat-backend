import asyncio
from app.database.database import engine
from app.database.models.base import Base  # Asegúrate que todos tus modelos hereden de esta Base
from dotenv import load_dotenv
import os

# Carga variables de entorno desde .env
load_dotenv()

async def create_tables():
    async with engine.begin() as conn:
        print("🔧 Creando tablas en la base de datos...")
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Tablas creadas correctamente.")

if __name__ == "__main__":
    asyncio.run(create_tables())
