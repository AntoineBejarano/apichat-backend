# app/routers/agent_router.py

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.agent_schema import AgentCreate, AgentUpdate, AgentOut

router = APIRouter(
    prefix="/agents",
    tags=["🤖 Agentes IA"],
    responses={404: {"description": "Agente no encontrado"}},
)

# Factory dependency injection
def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)

@router.post(
    "/",
    summary="Crear un nuevo agente",
    response_model=AgentOut,
    status_code=status.HTTP_201_CREATED,
    response_description="Agente creado exitosamente"
)
def create_agent(
    data: AgentCreate,
    factory: ServiceFactory = Depends(get_factory),
):
    agent_service = factory.get_agent_service()
    return agent_service.create(factory.user.id, data)

@router.get(
    "/",
    summary="Listar todos los agentes del usuario",
    response_model=List[AgentOut],
    response_description="Lista de agentes del usuario actual"
)
def list_agents(factory: ServiceFactory = Depends(get_factory)):
    agent_service = factory.get_agent_service()
    return agent_service.get_all(factory.user.id)

@router.get(
    "/{agent_id}",
    summary="Obtener un agente por ID",
    response_model=AgentOut,
    response_description="Detalles del agente"
)
def get_agent(agent_id: int, factory: ServiceFactory = Depends(get_factory)):
    agent_service = factory.get_agent_service()
    return agent_service.get_by_id(factory.user.id, agent_id)

@router.put(
    "/{agent_id}",
    summary="Actualizar un agente",
    response_model=AgentOut,
    response_description="Agente actualizado correctamente"
)
def update_agent(
    agent_id: int,
    updates: AgentUpdate,
    factory: ServiceFactory = Depends(get_factory),
):
    agent_service = factory.get_agent_service()
    return agent_service.update(factory.user.id, agent_id, updates)

@router.delete(
    "/{agent_id}",
    summary="Eliminar un agente",
    status_code=status.HTTP_204_NO_CONTENT,
    response_description="Agente eliminado exitosamente"
)
def delete_agent(agent_id: int, factory: ServiceFactory = Depends(get_factory)):
    agent_service = factory.get_agent_service()
    agent_service.delete(factory.user.id, agent_id)
