from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.agent_schema import AgentCreate, AgentUpdate, AgentOut

router = APIRouter(
    prefix="/agents",
    tags=["🤖 Agentes IA"],
    responses={
        404: {"description": "❌ Agente no encontrado"},
        401: {"description": "🔒 No autorizado"},
    },
)

def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)

@router.post(
    "/",
    summary="🧠 Crear nuevo agente IA",
    description="Crea un agente inteligente con nombre, prompt, idioma, temperatura, etc.",
    response_model=AgentOut,
    status_code=status.HTTP_201_CREATED,
    response_description="✅ Agente creado exitosamente"
)
def create_agent(
    data: AgentCreate,
    factory: ServiceFactory = Depends(get_factory),
):
    return factory.get_agent_service().create(data)

@router.get(
    "/",
    summary="📋 Listar agentes",
    description="Devuelve todos los agentes del usuario autenticado.",
    response_model=List[AgentOut],
    response_description="✅ Lista de agentes obtenida correctamente"
)
def list_agents(factory: ServiceFactory = Depends(get_factory)):
    return factory.get_agent_service().get_all()

@router.get(
    "/{agent_id}",
    summary="🔍 Obtener agente por ID",
    description="Devuelve un agente específico si pertenece al usuario autenticado.",
    response_model=AgentOut,
    response_description="✅ Agente encontrado"
)
def get_agent(agent_id: UUID, factory: ServiceFactory = Depends(get_factory)):
    return factory.get_agent_service().get_by_id(agent_id)

@router.put(
    "/{agent_id}",
    summary="✏️ Actualizar agente",
    description="Permite modificar cualquier atributo del agente.",
    response_model=AgentOut,
    response_description="✅ Agente actualizado correctamente"
)
def update_agent(
    agent_id: UUID,
    updates: AgentUpdate,
    factory: ServiceFactory = Depends(get_factory),
):
    return factory.get_agent_service().update(agent_id, updates)

@router.delete(
    "/{agent_id}",
    summary="🗑️ Eliminar agente",
    description="Elimina un agente del usuario.",
    status_code=status.HTTP_204_NO_CONTENT,
    response_description="✅ Agente eliminado exitosamente"
)
def delete_agent(agent_id: UUID, factory: ServiceFactory = Depends(get_factory)):
    factory.get_agent_service().delete(agent_id)
