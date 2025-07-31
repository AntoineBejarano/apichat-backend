import logging
from typing import List, Dict, Any
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.models.strategy_model import Strategy, TriggerTypeEnum
from app.schemas.strategy_schema import StrategyCreate, StrategyImportSchema
from app.core.service_factory import ServiceFactory
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)

class StrategyExecutionResult(BaseModel):
    success: bool
    result: Dict
    logs: List[str]


class StrategyService(BaseService):  # 👈 Hereda BaseService
    def __init__(self, factory: ServiceFactory):
        super().__init__(factory)  # 👈 Inicializa BaseService
        self.factory = factory
        self.db: Session = factory.db
        self.user = factory.user

    def create_strategy(self, data: StrategyCreate) -> Strategy:
        self.check_limit("strategies", Strategy)  # 👈 Chequea el límite

        logger.info(f"🚀 Creando nueva estrategia para el usuario {self.user.id}: {data.name}")

        strategy = Strategy(
            user_id=self.user.id,
            name=data.name,
            description=data.description,
            trigger_type=data.trigger_type,
            trigger_config=data.trigger_config,
            steps=[step.dict() for step in data.steps],
            is_active=True,
            status="pending",
        )

        self.db.add(strategy)
        self.db.commit()
        self.db.refresh(strategy)

        logger.info(f"✅ Estrategia creada con ID {strategy.id}")
        return strategy

    def get_user_strategies(self) -> List[Strategy]:
        logger.debug(f"📥 Obteniendo estrategias del usuario {self.user.id}")
        return self.db.query(Strategy).filter_by(user_id=self.user.id).order_by(Strategy.created_at.desc()).all()

    def get_strategy_by_id(self, strategy_id: UUID) -> Strategy:
        logger.debug(f"🔍 Buscando estrategia {strategy_id} para el usuario {self.user.id}")
        strategy = self.db.query(Strategy).filter_by(id=strategy_id, user_id=self.user.id).first()

        if not strategy:
            logger.warning(f"❌ Estrategia {strategy_id} no encontrada o no pertenece al usuario")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Strategy not found"
            )

        return strategy

    def update_strategy(self, strategy_id: UUID, data: StrategyCreate) -> Strategy:
        logger.info(f"✏️ Actualizando estrategia {strategy_id} del usuario {self.user.id}")

        strategy = self.get_strategy_by_id(strategy_id)
        strategy.name = data.name
        strategy.description = data.description
        strategy.trigger_type = data.trigger_type
        strategy.trigger_config = data.trigger_config
        strategy.steps = [step.dict() for step in data.steps]
        strategy.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(strategy)

        logger.info(f"✅ Estrategia {strategy_id} actualizada correctamente")
        return strategy

    def delete_strategy(self, strategy_id: UUID) -> None:
        logger.warning(f"🗑️ Eliminando estrategia {strategy_id} del usuario {self.user.id}")
        strategy = self.get_strategy_by_id(strategy_id)
        self.db.delete(strategy)
        self.db.commit()
        logger.info(f"✅ Estrategia {strategy_id} eliminada")

    def mark_as_run(self, strategy_id: UUID, status: str) -> None:
        logger.info(f"⏱️ Marcando estrategia {strategy_id} como ejecutada con estado '{status}'")
        strategy = self.get_strategy_by_id(strategy_id)
        strategy.last_run_at = datetime.utcnow()
        strategy.status = status
        self.db.commit()

    def get_cron_strategies(self) -> List[Strategy]:
        logger.debug("⏰ Obteniendo todas las estrategias programadas por CRON")
        return self.db.query(Strategy).filter_by(trigger_type="cron", is_active=True).all()

    def get_event_strategies(self, event_name: str) -> List[Strategy]:
        logger.debug(f"📡 Buscando estrategias activadas por evento '{event_name}'")
        return self.db.query(Strategy).filter(
            Strategy.trigger_type == "event",
            Strategy.is_active == True,
            Strategy.trigger_config["event"].astext == event_name
        ).all()

    def execute_strategy(
        self,
        strategy_id: int,
        agent_id: int,
        parameters: Dict[str, Any],
    ) -> StrategyExecutionResult:
        strategy = (
            self.db.query(Strategy)
            .filter_by(id=strategy_id, user_id=self.user.id)
            .first()
        )
        if not strategy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="❌ Estrategia no encontrada",
            )

        if strategy.agent_id != agent_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="❌ Agent no válido para esta estrategia",
            )

        original_steps = strategy.steps or []
        merged_steps: List[Dict[str, Any]] = []
        for step in original_steps:
            step_inputs = step.get("inputs", {}) or {}
            merged = {**parameters, **step_inputs} if parameters else step_inputs
            merged_steps.append({**step, "inputs": merged})

        try:
            strategy.steps = merged_steps
            raw_results = self.executor.run_strategy(strategy)
        finally:
            strategy.steps = original_steps

        logs = [
            f"Paso {r['step']}: function_id={r['function_id']} → {r['status']}"
            for r in raw_results
        ]
        success = all(r["status"] == "success" for r in raw_results)

        strategy.status = "success" if success else "error"
        strategy.last_run_at = datetime.utcnow()
        self.db.commit()

        return StrategyExecutionResult(
            success=success,
            result=raw_results,
            logs=logs,
        )

    def import_from_json(self, data: dict) -> Strategy:
        try:
            logger.info(f"📥 Importando estrategia para el usuario {self.user.id}")
            schema = StrategyImportSchema(**data)

            strategy = Strategy(
                id=uuid4(),
                user_id=self.user.id,
                name=schema.name,
                description=schema.description,
                trigger_type=TriggerTypeEnum(schema.trigger.type),
                trigger_config=schema.trigger.config,
                steps=[step.dict() for step in schema.steps],
                is_active=True,
                status="pending"
            )

            self.db.add(strategy)
            self.db.commit()
            self.db.refresh(strategy)

            logger.info(f"✅ Estrategia importada con ID {strategy.id}")
            return strategy

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.exception("❌ Error de base de datos al importar estrategia")
            raise HTTPException(status_code=500, detail="Database error during import")
        except Exception as e:
            logger.exception("❌ Error al validar estrategia importada")
            raise HTTPException(status_code=400, detail=f"Import error: {str(e)}")

    def export_to_json(self, strategy: Strategy) -> dict:
        logger.info(f"📤 Exportando estrategia {strategy.id}")
        return {
            "name": strategy.name,
            "description": strategy.description,
            "trigger": {
                "type": strategy.trigger_type.value,
                "config": strategy.trigger_config
            },
            "steps": strategy.steps
        }
