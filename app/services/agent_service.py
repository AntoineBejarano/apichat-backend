import logging
from typing import List
from fastapi import HTTPException

from app.models.agent_model import Agent
from app.schemas.agent_schema import AgentCreate, AgentUpdate
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory
    
logger = logging.getLogger(__name__)

class AgentService:
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.db = factory.db
        self.user_id = factory.user.id
        logger.info(f"[AgentService] Inicializado para user_id={self.user_id}")

    def create(self, data: AgentCreate) -> Agent:
        logger.info(f"[AgentService] Creando nuevo agente para user_id={self.user_id}")
        agent = Agent(user_id=self.user_id, **data.dict())
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def get_all(self) -> List[Agent]:
        logger.info(f"[AgentService] Recuperando todos los agentes para user_id={self.user_id}")
        return self.db.query(Agent).filter(Agent.user_id == self.user_id).all()

    def get_by_id(self, agent_id: int) -> Agent:
        logger.info(f"[AgentService] Buscando agente ID={agent_id} para user_id={self.user_id}")
        agent = self.db.query(Agent).filter_by(user_id=self.user_id, id=agent_id).first()
        if not agent:
            logger.warning(f"[AgentService] Agente ID={agent_id} no encontrado")
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent

    def update(self, agent_id: int, updates: AgentUpdate) -> Agent:
        logger.info(f"[AgentService] Actualizando agente ID={agent_id} para user_id={self.user_id}")
        agent = self.get_by_id(agent_id)
        for field, value in updates.dict(exclude_unset=True).items():
            setattr(agent, field, value)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def delete(self, agent_id: int) -> bool:
        logger.info(f"[AgentService] Eliminando agente ID={agent_id}")
        agent = self.get_by_id(agent_id)
        self.db.delete(agent)
        self.db.commit()
        return True

    def get_prompt(self, agent_id: int) -> str:
        logger.info(f"[AgentService] Obteniendo prompt para agente ID={agent_id}")
        agent = self.db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.user_id == self.user_id
        ).first()

        if not agent:
            logger.error(f"[AgentService] Agente ID={agent_id} no encontrado")
            raise HTTPException(status_code=404, detail="Agent not found")

        return agent.prompt
