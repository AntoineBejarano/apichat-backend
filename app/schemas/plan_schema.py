from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class ActionModel(BaseModel):
    type: Literal["db_query", "api_function", "mcp_tool"] = Field(..., description="Tipo de acción a ejecutar")
    sql: Optional[str] = Field(None, description="Consulta SQL si aplica")
    question: Optional[str] = Field(None, description="Pregunta a base de datos si aplica")
    function_id: Optional[int] = Field(None, description="ID de función API si aplica")
    tool_name: Optional[str] = Field(None, description="Nombre de la herramienta MCP si aplica")
    params: Optional[dict] = Field(default_factory=dict, description="Parámetros para la función o herramienta")
    store_as: Optional[str] = Field(None, description="Nombre para almacenar el resultado en contexto")

class PlanModel(BaseModel):
    actions: List[ActionModel] = Field(..., description="Secuencia de acciones a ejecutar")
    assistant_response: str = Field(..., description="Respuesta final al usuario")
