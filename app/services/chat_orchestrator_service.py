import logging
from typing import List, Optional

from sqlalchemy.orm import Session
from app.core.servicefactory import ServiceFactory  # 👈 Import correcto
from app.schemas.chat_schema import ChatMessage
from app.models.database_model import DatabaseConnection
from app.models.function_model import Function
from app.models.integration_model import Integration

logger = logging.getLogger(__name__)


class OrchestratorService:
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.db: Session = factory.db
        self.user_id: int = factory.user.id

        # Servicios cargados desde el factory
        self.openai = factory.get_openai_service()
        self.agents = factory.get_agent_service()
        self.databases = factory.get_database_service()
        self.functions = factory.get_function_service()
        self.integrations = factory.get_integration_service()

        logger.info(f"[OrchestratorService] Inicializado para user_id={self.user_id}")

    async def handle_user_message(
        self,
        database_id: Optional[int],
        app_id: Optional[int],
        agent_id: Optional[int],
        message: ChatMessage
    ) -> dict:
        steps = []

        try:
            logger.info(f"[{self.user_id}] 📥 Mensaje recibido: '{message.content}'")
            steps.append("Mensaje recibido")

            # Paso 1: Prompt del agente
            system_prompt = ""
            if agent_id:
                logger.info(f"[{self.user_id}] 🔍 Obteniendo prompt del agente ID {agent_id}")
                system_prompt = self.agents.get_prompt(agent_id)
                steps.append(f"Prompt cargado del agente {agent_id}")

            # Paso 2: Conexión a base de datos
            db_conn: Optional[DatabaseConnection] = None
            if database_id:
                logger.info(f"[{self.user_id}] 🧬 Obteniendo conexión DB ID {database_id}")
                db_conn = self.databases.get_sql_instance(database_id)
                steps.append(f"Conexión a DB {database_id} establecida")

            # Paso 3: Funciones del app
            functions: List[Function] = []
            if app_id:
                logger.info(f"[{self.user_id}] ⚙️ Cargando funciones para app ID {app_id}")
                functions = self.functions.get_by_app(app_id)
                steps.append(f"{len(functions)} funciones obtenidas del app {app_id}")

            # Paso 4: Integraciones activas
            logger.info(f"[{self.user_id}] 🔌 Buscando integraciones activas")
            integrations: List[Integration] = self.integrations.get_user_integrations()
            steps.append(f"{len(integrations)} integraciones cargadas")

            # Paso 5: IA
            logger.info(f"[{self.user_id}] 🧠 Ejecutando motor IA...")
            response = await self.openai.detect_intent_and_respond(
                db=self.db,
                user_id=self.user_id,
                db_id=database_id,
                app_id=app_id,
                system_prompt=system_prompt,
                message=message,
                db_conn=db_conn,
                functions=functions,
                integrations=integrations
            )
            steps.append("Respuesta generada por IA")

            logger.info(f"[{self.user_id}] ✅ Respuesta generada exitosamente")
            response["steps"] = steps
            return response

        except Exception as e:
            logger.exception(f"[{self.user_id}] ❌ Error procesando mensaje: {str(e)}")
            return {
                "error": "Ocurrió un error procesando tu mensaje.",
                "details": str(e),
                "steps": steps + ["Error detectado"]
            }
