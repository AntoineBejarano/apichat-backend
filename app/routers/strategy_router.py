from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict
from uuid import UUID

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.strategy_schema import (
    StrategyCreate,
    StrategyOut,
    StrategyUpdate,
    StrategyImportSchema,
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
        return factory.get_strategy_service().create_strategy(user_data)
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
    return factory.get_strategy_service().get_user_strategies()


@router.get(
    "/{strategy_id}",
    response_model=StrategyOut,
    summary="🔍 Obtener estrategia por ID",
    description="Devuelve los detalles de una estrategia específica del usuario.",
)
def get_strategy_route(
    strategy_id: UUID, factory: ServiceFactory = Depends(get_factory)
):
    return factory.get_strategy_service().get_strategy_by_id(strategy_id)


@router.put(
    "/{strategy_id}",
    response_model=StrategyOut,
    summary="✏️ Actualizar estrategia",
    description="Actualiza los datos de una estrategia específica.",
)
def update_strategy_route(
    strategy_id: UUID,
    updates: StrategyUpdate,
    factory: ServiceFactory = Depends(get_factory),
):
    return factory.get_strategy_service().update_strategy(strategy_id, updates)


@router.delete(
    "/{strategy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="🗑️ Eliminar estrategia",
    description="Elimina una estrategia específica del usuario.",
)
def delete_strategy_route(
    strategy_id: UUID, factory: ServiceFactory = Depends(get_factory)
):
    factory.get_strategy_service().delete_strategy(strategy_id)


# ——————————————————————————————
# Endpoint de Ejecución de Estrategia
# ——————————————————————————————

class StrategyExecuteRequest(BaseModel):
    agent_id: int
    parameters: Dict  # puedes usar un schema específico si lo prefieres

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
    strategy_id: UUID,
    body: StrategyExecuteRequest,
    factory: ServiceFactory = Depends(get_factory),
):
    try:
        outcome = factory.get_strategy_service().execute_strategy(
            strategy_id,
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


# ——————————————————————————————
# 🆕 Importar y Exportar Estrategias en JSON
# ——————————————————————————————

@router.post(
    "/import",
    response_model=StrategyOut,
    summary="📥 Importar estrategia desde JSON",
    description="Importa una estrategia en formato JSON como las de Make o n8n.",
)
def import_strategy_route(
    payload: StrategyImportSchema,
    factory: ServiceFactory = Depends(get_factory),
):
    return factory.get_strategy_service().import_from_json(payload.dict())


@router.get(
    "/{strategy_id}/export",
    summary="📤 Exportar estrategia como JSON",
    description="Exporta una estrategia a formato JSON universal.",
)
def export_strategy_route(
    strategy_id: UUID,
    factory: ServiceFactory = Depends(get_factory),
):
    strategy = factory.get_strategy_service().get_strategy_by_id(strategy_id)
    return factory.get_strategy_service().export_to_json(strategy)
