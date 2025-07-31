import logging
from typing import List
from uuid import UUID
from fastapi import HTTPException
from app.models.agent_model import Agent
from app.models.agent_app_link import AgentAppLink
from app.models.agent_database_link import AgentDatabaseLink
from app.models.app_model import App
from app.models.database_model import DatabaseConnection
from app.schemas.agent_schema import AgentCreate, AgentUpdate
from app.services.base_service import BaseService

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)

class AgentService(BaseService):
    def __init__(self, factory: 'ServiceFactory'):
        super().__init__(factory)
        self.factory = factory
        self.db = factory.db
        self.user_id = factory.user.id
        logger.info(f"[AgentService] Inicializado para user_id={self.user_id}")

    def create(self, data: AgentCreate) -> Agent:
        # ⚠️ Llamada corregida: usamos el modelo y el nombre del campo del plan
        self.check_limit(Agent, "max_agents", "agentes")
        logger.info(f"[AgentService] Creando nuevo agente para user_id={self.user_id}")

        # Verificar apps
        if data.app_ids:
            apps = self.db.query(App).filter(App.id.in_(data.app_ids), App.user_id == self.user_id).all()
            if len(apps) != len(data.app_ids):
                raise HTTPException(status_code=400, detail="Una o más apps no existen o no pertenecen al usuario")

        # Verificar conexiones DB
        if data.database_connection_ids:
            db_conns = self.db.query(DatabaseConnection).filter(
                DatabaseConnection.id.in_(data.database_connection_ids),
                DatabaseConnection.user_id == self.user_id
            ).all()
            if len(db_conns) != len(data.database_connection_ids):
                raise HTTPException(status_code=400, detail="Una o más conexiones de base de datos no existen o no pertenecen al usuario")

        # Crear agente
        agent = Agent(
            user_id=self.user_id,
            name=data.name,
            description=data.description,
            system_prompt=data.system_prompt,
            language=data.language,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
            memory_enabled=data.memory_enabled
        )

        self.db.add(agent)
        self.db.flush()  # Necesario para obtener el agent.id

        # Crear enlaces a apps
        for app_id in data.app_ids or []:
            self.db.add(AgentAppLink(agent_id=agent.id, app_id=app_id))

        # Crear enlaces a databases
        for db_id in data.database_connection_ids or []:
            self.db.add(AgentDatabaseLink(agent_id=agent.id, database_id=db_id))

        self.db.commit()
        self.db.refresh(agent)
        return agent

    def get_all(self) -> List[Agent]:
        logger.info(f"[AgentService] Listando todos los agentes para user_id={self.user_id}")
        return self.db.query(Agent).filter(Agent.user_id == self.user_id).all()

    def get_by_id(self, agent_id: UUID) -> Agent:
        logger.info(f"[AgentService] Obteniendo agente ID={agent_id} para user_id={self.user_id}")
        agent = self.db.query(Agent).filter_by(user_id=self.user_id, id=agent_id).first()
        if not agent:
            logger.warning(f"[AgentService] Agente ID={agent_id} no encontrado")
            raise HTTPException(status_code=404, detail="Agente no encontrado")
        return agent

    def update(self, agent_id: UUID, updates: AgentUpdate) -> Agent:
        logger.info(f"[AgentService] Actualizando agente ID={agent_id} para user_id={self.user_id}")
        agent = self.get_by_id(agent_id)
        for field, value in updates.dict(exclude_unset=True).items():
            setattr(agent, field, value)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def delete(self, agent_id: UUID) -> bool:
        logger.info(f"[AgentService] Eliminando agente ID={agent_id}")
        agent = self.get_by_id(agent_id)
        self.db.delete(agent)
        self.db.commit()
        return True

    def get_prompt(self, agent_id: UUID) -> str:
        logger.info(f"[AgentService] Obteniendo system_prompt para agente ID={agent_id}")
        agent = self.db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.user_id == self.user_id
        ).first()
        if not agent:
            logger.error(f"[AgentService] Agente ID={agent_id} no encontrado")
            raise HTTPException(status_code=404, detail="Agente no encontrado")
        return agent.system_prompt
