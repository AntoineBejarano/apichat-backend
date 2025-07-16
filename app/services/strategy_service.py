import logging
from typing import List, Optional
from app.models.strategy_model import Strategy
from app.schemas.strategy_schema import StrategyCreate, StrategyUpdate
from app.core.servicefactory import ServiceFactory

logger = logging.getLogger(__name__)


class StrategyService:
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.db = factory.db
        self.user = factory.user

    def create(self, data: StrategyCreate) -> Strategy:
        logger.info(f"[StrategyService] ➕ Creando estrategia para user_id={self.user.id}")
        strategy = Strategy(user_id=self.user.id, **data.model_dump())
        self.db.add(strategy)
        self.db.commit()
        self.db.refresh(strategy)
        logger.debug(f"[StrategyService] ✅ Estrategia creada con ID={strategy.id}")
        return strategy

    def get_all(self) -> List[Strategy]:
        logger.info(f"[StrategyService] 📄 Obteniendo todas las estrategias para user_id={self.user.id}")
        strategies = self.db.query(Strategy).filter(Strategy.user_id == self.user.id).all()
        logger.debug(f"[StrategyService] 🔍 {len(strategies)} estrategias encontradas")
        return strategies

    def get_by_id(self, strategy_id: int) -> Optional[Strategy]:
        logger.info(f"[StrategyService] 🔍 Buscando estrategia ID={strategy_id} para user_id={self.user.id}")
        strategy = (
            self.db.query(Strategy)
            .filter(Strategy.user_id == self.user.id, Strategy.id == strategy_id)
            .first()
        )
        if strategy:
            logger.debug(f"[StrategyService] ✅ Estrategia encontrada")
        else:
            logger.warning(f"[StrategyService] ⚠️ Estrategia ID={strategy_id} no encontrada")
        return strategy

    def update(self, strategy_id: int, updates: StrategyUpdate) -> Optional[Strategy]:
        logger.info(f"[StrategyService] ✏️ Actualizando estrategia ID={strategy_id} para user_id={self.user.id}")
        strategy = self.get_by_id(strategy_id)
        if not strategy:
            logger.warning(f"[StrategyService] ❌ No se encontró estrategia ID={strategy_id} para actualizar")
            return None
        for field, value in updates.model_dump(exclude_unset=True).items():
            setattr(strategy, field, value)
        self.db.commit()
        self.db.refresh(strategy)
        logger.debug(f"[StrategyService] ✅ Estrategia ID={strategy.id} actualizada correctamente")
        return strategy

    def delete(self, strategy_id: int) -> bool:
        logger.info(f"[StrategyService] 🗑️ Eliminando estrategia ID={strategy_id} para user_id={self.user.id}")
        strategy = self.get_by_id(strategy_id)
        if not strategy:
            logger.warning(f"[StrategyService] ❌ No se encontró estrategia ID={strategy_id} para eliminar")
            return False
        self.db.delete(strategy)
        self.db.commit()
        logger.debug(f"[StrategyService] ✅ Estrategia eliminada correctamente")
        return True
