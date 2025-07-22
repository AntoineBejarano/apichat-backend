# app/routers/strategy_router.py

from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.strategy_schema import (
    StrategyCreate,
    StrategyOut,
    StrategyUpdate,
)
from pydantic import BaseModel

router = APIRouter(
    prefix="/strategies",
    tags=["📈 Strategies"],
    responses={
        404: {"description": "Estrategia no encontrada"},
        500: {"description": "Error interno del servidor"},
    },
)

# 🧩 Inyector del ServiceFactory
def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)


# ——————————————————————————————
# CRUD Básico de Estrategias (ya existente)
# ——————————————————————————————

@router.post(
    "/",
    response_model=StrategyOut,
    status_code=status.HTTP_201_CREATED,
    summary="➕ Crear nueva estrategia",
    description="Crea una nueva estrategia basada en una secuencia de funciones definida por el usuario.",
)
def create_strategy_route(
    user_data: StrategyCreate,
    factory: ServiceFactory = Depends(get_factory),
):
    try:
        return factory.get_strategy_service().create_strategy(
            factory.user.id, user_data
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"💥 Error al crear estrategia: {str(e)}"
        )


@router.get(
    "/",
    response_model=List[StrategyOut],
    summary="📋 Listar estrategias",
    description="Devuelve todas las estrategias creadas por el usuario autenticado.",
)
def list_strategies(factory: ServiceFactory = Depends(get_factory)):
    return factory.get_strategy_service().get_user_strategies(factory.user.id)


@router.get(
    "/{strategy_id}",
    response_model=StrategyOut,
    summary="🔍 Obtener estrategia por ID",
    description="Devuelve los detalles de una estrategia específica del usuario.",
)
def get_strategy_route(
    strategy_id: int, factory: ServiceFactory = Depends(get_factory)
):
    strategy = factory.get_strategy_service().get_strategy_by_id(
        factory.user.id, strategy_id
    )
    if not strategy:
        raise HTTPException(
            status_code=404, detail="❌ Estrategia no encontrada"
        )
    return strategy


@router.put(
    "/{strategy_id}",
    response_model=StrategyOut,
    summary="✏️ Actualizar estrategia",
    description="Actualiza los datos de una estrategia específica.",
)
def update_strategy_route(
    strategy_id: int,
    updates: StrategyUpdate,
    factory: ServiceFactory = Depends(get_factory),
):
    updated = factory.get_strategy_service().update_strategy(
        factory.user.id, strategy_id, updates
    )
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="❌ Estrategia no encontrada o sin cambios",
        )
    return updated


@router.delete(
    "/{strategy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="🗑️ Eliminar estrategia",
    description="Elimina una estrategia específica del usuario.",
)
def delete_strategy_route(
    strategy_id: int, factory: ServiceFactory = Depends(get_factory)
):
    success = factory.get_strategy_service().delete_strategy(
        factory.user.id, strategy_id
    )
    if not success:
        raise HTTPException(
            status_code=404, detail="❌ Estrategia no encontrada"
        )


# ——————————————————————————————
# Endpoint de Ejecución de Estrategia
# ——————————————————————————————

class StrategyExecuteRequest(BaseModel):
    agent_id: int
    parameters: Dict  # define aquí tu schema concreto si quieres más validación


class StrategyExecuteResponse(BaseModel):
    success: bool
    result: List[dict]
    logs: List[str]

@router.post(
    "/{strategy_id}/execute",
    response_model=StrategyExecuteResponse,
    summary="🏃 Ejecutar estrategia",
)
def execute_strategy_route(
    strategy_id: int,
    body: StrategyExecuteRequest,
    factory: ServiceFactory = Depends(get_factory),
):
    try:
        outcome = factory.get_strategy_service().execute_strategy(
            strategy_id,         # ya sin user_id
            body.agent_id,
            body.parameters,
        )
        return StrategyExecuteResponse(**outcome.dict())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"❌ Error al ejecutar: {e}",
        )