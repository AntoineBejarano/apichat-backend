# app/services/agent_service.py
"""
AgentService
────────────
Gestión de agentes (LLM personas) y sus vínculos con apps y bases de datos.
Incluye helpers para:
  • CRUD completo
  • límite de agentes por plan
  • obtención del `system_prompt` definido en el agente
  • recuperación opcional del último prompt de sistema almacenado en historial
"""
from __future__ import annotations

import logging
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.agent_model import Agent
from app.models.agent_app_link import AgentAppLink
from app.models.agent_database_link import AgentDatabaseLink
from app.models.app_model import App
from app.models.database_model import DatabaseConnection
from app.schemas.agent_schema import AgentCreate, AgentUpdate
from app.services.base_service import BaseService

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class AgentService(BaseService):
    # ─────────────────────────────────────────────
    #   Init
    # ─────────────────────────────────────────────
    def __init__(self, factory: "ServiceFactory") -> None:
        super().__init__(factory)
        self.factory = factory
        self.db: Session = factory.db
        self.user_id: UUID = factory.user.id
        logger.info("[AgentService] Inicializado para user_id=%s", self.user_id)

    # ─────────────────────────────────────────────
    #   CRUD
    # ─────────────────────────────────────────────
    def create(self, data: AgentCreate) -> Agent:
        self.check_limit(Agent, "max_agents", "agentes")
        logger.info("[AgentService] Creando nuevo agente para user_id=%s", self.user_id)

        # Validar apps
        if data.app_ids:
            apps = (
                self.db.query(App)
                .filter(App.id.in_(data.app_ids), App.user_id == self.user_id)
                .all()
            )
            if len(apps) != len(data.app_ids):
                raise HTTPException(400, "Una o más apps no existen o no pertenecen al usuario")

        # Validar conexiones BD
        if data.database_connection_ids:
            db_conns = (
                self.db.query(DatabaseConnection)
                .filter(DatabaseConnection.id.in_(data.database_connection_ids),
                        DatabaseConnection.user_id == self.user_id)
                .all()
            )
            if len(db_conns) != len(data.database_connection_ids):
                raise HTTPException(400, "Una o más conexiones de BD no existen o no pertenecen al usuario")

        agent = Agent(
            user_id=self.user_id,
            name=data.name,
            description=data.description,
            system_prompt=data.system_prompt,
            language=data.language,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
            memory_enabled=data.memory_enabled,
        )
        self.db.add(agent)
        self.db.flush()  # obtener agent.id antes de enlaces

        # Enlaces apps
        for app_id in data.app_ids or []:
            self.db.add(AgentAppLink(agent_id=agent.id, app_id=app_id))

        # Enlaces BD
        for db_id in data.database_connection_ids or []:
            self.db.add(AgentDatabaseLink(agent_id=agent.id, database_id=db_id))

        self.db.commit()
        self.db.refresh(agent)
        return agent

    def get_all(self) -> List[Agent]:
        logger.info("[AgentService] Listando agentes para user_id=%s", self.user_id)
        return self.db.query(Agent).filter(Agent.user_id == self.user_id).all()

    def get_by_id(self, agent_id: UUID) -> Agent:
        agent = (
            self.db.query(Agent)
            .filter(Agent.id == agent_id, Agent.user_id == self.user_id)
            .first()
        )
        if not agent:
            logger.warning("[AgentService] Agente ID=%s no encontrado", agent_id)
            raise HTTPException(404, "Agente no encontrado")
        return agent

    def update(self, agent_id: UUID, updates: AgentUpdate) -> Agent:
        agent = self.get_by_id(agent_id)
        for field, value in updates.dict(exclude_unset=True).items():
            setattr(agent, field, value)
        self.db.commit()
        self.db.refresh(agent)
        logger.info("[AgentService] Agente ID=%s actualizado", agent_id)
        return agent

    def delete(self, agent_id: UUID) -> bool:
        agent = self.get_by_id(agent_id)
        self.db.delete(agent)
        self.db.commit()
        logger.info("[AgentService] Agente ID=%s eliminado", agent_id)
        return True

    # ─────────────────────────────────────────────
    #   Prompts
    # ─────────────────────────────────────────────
    def get_prompt(self, agent_id: UUID) -> str:
        """
        Devuelve el `system_prompt` almacenado en la tabla Agent.
        """
        agent = self.get_by_id(agent_id)
        logger.info("[AgentService] Obtenido prompt de agente ID=%s", agent_id)
        return agent.system_prompt

    def get_prompt_from_history(self, chat_id: Optional[UUID] = None) -> str:
        """
        Devuelve el contenido del último mensaje `role='system'` guardado
        en el historial (opcionalmente para un chat concreto).
        Retorna cadena vacía si no existe.
        """
        try:
            last_msg = (
                self.factory.get_chat_history_service()
                .get_last_system_prompt(chat_id)
            )
            return last_msg.content if last_msg else ""
        except Exception as e:
            logger.warning("[AgentService] No se pudo obtener prompt de historial: %s", e)
            return ""
