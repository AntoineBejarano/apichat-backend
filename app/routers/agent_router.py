from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.schemas.agent_schema import AgentCreate, AgentUpdate, AgentOut
from app.core.servicefactory import ServiceFactory

router = APIRouter(
    prefix="/agents",
    tags=["🤖 Agentes IA"],
    responses={404: {"description": "Agente no encontrado"}},
)

# Inyecta el ServiceFactory en lugar del AgentService y User
def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)

@router.post(
    "/",
    summary="Crear un nuevo agente",
    response_model=AgentOut,
    status_code=status.HTTP_201_CREATED,
    response_description="Agente creado exitosamente"
)
def create_new_agent(
    data: AgentCreate,
    factory: ServiceFactory = Depends(get_factory),
):
    service = factory.get_agent_service()
    return service.create(factory.user.id, data)

@router.get(
    "/",
    summary="Listar agentes del usuario",
    response_model=List[AgentOut],
    response_description="Lista de agentes del usuario actual"
)
def list_user_agents(factory: ServiceFactory = Depends(get_factory)):
    service = factory.get_agent_service()
    return service.get_all(factory.user.id)

@router.get(
    "/{agent_id}",
    summary="Obtener un agente por ID",
    response_model=AgentOut,
    response_description="Detalles del agente"
)
def retrieve_agent(agent_id: int, factory: ServiceFactory = Depends(get_factory)):
    service = factory.get_agent_service()
    return service.get_by_id(factory.user.id, agent_id)

@router.put(
    "/{agent_id}",
    summary="Actualizar un agente",
    response_model=AgentOut,
    response_description="Agente actualizado correctamente"
)
def modify_agent(
    agent_id: int,
    updates: AgentUpdate,
    factory: ServiceFactory = Depends(get_factory),
):
    service = factory.get_agent_service()
    return service.update(factory.user.id, agent_id, updates)

@router.delete(
    "/{agent_id}",
    summary="Eliminar un agente",
    status_code=status.HTTP_204_NO_CONTENT,
    response_description="Agente eliminado exitosamente"
)
def remove_agent(agent_id: int, factory: ServiceFactory = Depends(get_factory)):
    service = factory.get_agent_service()
    service.delete(factory.user.id, agent_id)
