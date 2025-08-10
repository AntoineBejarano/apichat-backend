import logging
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.executed_strategy_model import ExecutedStrategy
from app.schemas.executed_strategy_schema import (
    ExecutedStrategyCreate,
    ExecutedStrategyUpdate,
    ExecutedStrategyOut
)

logger = logging.getLogger(__name__)


class ExecutedStrategyService:
    def __init__(self, db: Session, user_id: UUID):
        self.db = db
        self.user_id = user_id

    def create(self, data: ExecutedStrategyCreate) -> ExecutedStrategyOut:
        """
        Crea una estrategia ejecutada (generada por IA o definida por usuario).
        Compatible con exportación a n8n/Make.
        """
        try:
            new_strategy = ExecutedStrategy(
                user_id=self.user_id,
                chat_id=data.chat_id,
                plan=data.plan,  # JSON del plan de la IA
                graph=data.graph,  # Estructura de grafo/flow
                is_public=data.is_public,
                is_user_defined=data.is_user_defined,
                source=data.source or "ai"  # "ai" o "user"
            )
            self.db.add(new_strategy)
            self.db.commit()
            self.db.refresh(new_strategy)
            logger.info(
                "[ExecutedStrategyService] ✅ Estrategia creada (id=%s, user_defined=%s)",
                new_strategy.id,
                new_strategy.is_user_defined
            )
            return ExecutedStrategyOut.model_validate(new_strategy)
        except Exception as e:
            logger.exception("[ExecutedStrategyService] ❌ Error creando estrategia: %s", e)
            raise HTTPException(status_code=500, detail="Error creando estrategia ejecutada.")

    def get_by_id(self, strategy_id: UUID) -> ExecutedStrategyOut:
        """Obtiene una estrategia por su ID (solo si pertenece al usuario)."""
        strategy = (
            self.db.query(ExecutedStrategy)
            .filter(ExecutedStrategy.id == strategy_id, ExecutedStrategy.user_id == self.user_id)
            .first()
        )
        if not strategy:
            raise HTTPException(status_code=404, detail="Estrategia no encontrada.")
        return ExecutedStrategyOut.model_validate(strategy)

    def list_for_chat(self, chat_id: UUID) -> List[ExecutedStrategyOut]:
        """Lista todas las estrategias ejecutadas en un chat específico."""
        strategies = (
            self.db.query(ExecutedStrategy)
            .filter(ExecutedStrategy.chat_id == chat_id, ExecutedStrategy.user_id == self.user_id)
            .order_by(ExecutedStrategy.created_at.desc())
            .all()
        )
        return [ExecutedStrategyOut.model_validate(s) for s in strategies]

    def list_all(self) -> List[ExecutedStrategyOut]:
        """Lista todas las estrategias ejecutadas por el usuario."""
        strategies = (
            self.db.query(ExecutedStrategy)
            .filter(ExecutedStrategy.user_id == self.user_id)
            .order_by(ExecutedStrategy.created_at.desc())
            .all()
        )
        return [ExecutedStrategyOut.model_validate(s) for s in strategies]

    def update(self, strategy_id: UUID, data: ExecutedStrategyUpdate) -> ExecutedStrategyOut:
        """
        Actualiza una estrategia existente (por ejemplo, convertir IA → usuario o editar grafo).
        """
        strategy = (
            self.db.query(ExecutedStrategy)
            .filter(ExecutedStrategy.id == strategy_id, ExecutedStrategy.user_id == self.user_id)
            .first()
        )
        if not strategy:
            raise HTTPException(status_code=404, detail="Estrategia no encontrada.")

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(strategy, field, value)

        self.db.commit()
        self.db.refresh(strategy)
        logger.info("[ExecutedStrategyService] ✏️ Estrategia actualizada (id=%s)", strategy_id)
        return ExecutedStrategyOut.model_validate(strategy)

    def delete(self, strategy_id: UUID) -> None:
        """Elimina una estrategia ejecutada (solo si pertenece al usuario)."""
        strategy = (
            self.db.query(ExecutedStrategy)
            .filter(ExecutedStrategy.id == strategy_id, ExecutedStrategy.user_id == self.user_id)
            .first()
        )
        if not strategy:
            raise HTTPException(status_code=404, detail="Estrategia no encontrada.")
        self.db.delete(strategy)
        self.db.commit()
        logger.info("[ExecutedStrategyService] 🗑️ Estrategia eliminada (id=%s)", strategy_id)
