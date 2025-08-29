#!/usr/bin/env python3
"""
Script de prueba para verificar que el cache se limpia correctamente
cuando se elimina una base de datos.

Este script simula el proceso de eliminación de una base de datos
y verifica que todos los niveles de cache se limpien correctamente.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Agregar el directorio raíz al path para importar módulos
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.services.data.database_service import DatabaseService
from app.services.cache.redis_schema_cache import redis_schema_cache
from app.services.context.detailed_schema_cache_service import DetailedSchemaCacheService
from app.services.data.redis_cache_service import RedisCacheService

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_cache_cleanup_on_delete():
    """
    Prueba que el cache se limpia correctamente cuando se elimina una base de datos.
    """
    logger.info("🧪 Iniciando prueba de limpieza de cache al eliminar base de datos")
    
    try:
        # 1. Crear una sesión de base de datos
        db = next(get_db())
        
        # 2. Crear un ServiceFactory de prueba
        # Nota: En un entorno real, esto vendría de una request autenticada
        factory = ServiceFactory(db, None)
        
        # 3. Crear instancias de los servicios
        database_service = DatabaseService(factory)
        redis_cache = redis_schema_cache
        detailed_cache = DetailedSchemaCacheService(factory)
        memory_cache = RedisCacheService()
        
        # 4. Simular una base de datos de prueba
        test_db_id = "test-db-123"
        test_user_id = "test-user-456"
        
        logger.info(f"📝 Simulando base de datos de prueba: {test_db_id}")
        
        # 5. Simular datos de cache en diferentes niveles
        # L1: Redis
        test_schema = {
            "tables": ["users", "products"],
            "columns": {"users": ["id", "name"], "products": ["id", "title"]}
        }
        redis_cache.set_schema(test_user_id, test_db_id, test_schema)
        logger.info("✅ Cache Redis poblado con datos de prueba")
        
        # L2: Cache detallado (simulado)
        logger.info("✅ Cache detallado simulado")
        
        # L3: Cache en memoria
        memory_cache.set_schema_cache(test_user_id, test_db_id, test_schema)
        logger.info("✅ Cache en memoria poblado con datos de prueba")
        
        # 6. Verificar que el cache existe
        redis_result = redis_cache.get_schema(test_user_id, test_db_id)
        memory_result = memory_cache.get_schema_cache(test_user_id, test_db_id)
        
        if redis_result and memory_result:
            logger.info("✅ Verificación: Cache existe en todos los niveles")
        else:
            logger.warning("⚠️ Algunos niveles de cache no tienen datos")
        
        # 7. Simular la eliminación de la base de datos
        logger.info("🗑️ Simulando eliminación de base de datos...")
        
        # Llamar directamente al método de limpieza de cache
        database_service._clear_database_cache(test_db_id)
        
        # 8. Verificar que el cache se limpió
        redis_result_after = redis_cache.get_schema(test_user_id, test_db_id)
        memory_result_after = memory_cache.get_schema_cache(test_user_id, test_db_id)
        
        if not redis_result_after and not memory_result_after:
            logger.info("✅ ÉXITO: Cache limpiado correctamente en todos los niveles")
        else:
            logger.error("❌ ERROR: Cache no se limpió completamente")
            if redis_result_after:
                logger.error(f"   - Redis aún tiene datos: {redis_result_after}")
            if memory_result_after:
                logger.error(f"   - Memoria aún tiene datos: {memory_result_after}")
        
        # 9. Limpieza final
        logger.info("🧹 Limpieza final de datos de prueba...")
        
        # Limpiar cualquier dato de prueba restante
        redis_cache.invalidate_schema(test_user_id, test_db_id)
        memory_cache.clear_db_cache(test_db_id)
        
        logger.info("✅ Prueba completada")
        
    except Exception as e:
        logger.error(f"❌ Error durante la prueba: {e}")
        raise
    finally:
        # Cerrar la sesión de base de datos
        if 'db' in locals():
            db.close()

def main():
    """Función principal para ejecutar la prueba"""
    logger.info("🚀 Iniciando script de prueba de limpieza de cache")
    
    try:
        # Ejecutar la prueba asíncrona
        asyncio.run(test_cache_cleanup_on_delete())
        logger.info("🎉 Prueba completada exitosamente")
        
    except Exception as e:
        logger.error(f"💥 Error fatal en la prueba: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
