# app/services/openapi_processor.py

from typing import List, Dict
from app.integrations.openapi_parser import parse_openapi_to_functions
from app.models.openapi_model import OpenAPIIntegration
from app.schemas.function_schema import FunctionCreate
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory
    
class OpenAPIProcessor:
    def __init__(self, factory: ServiceFactory):
        self.db = factory.db
        self.user = factory.user
        self.function_service = factory.get_function_service()

    def process(self, openapi_dict: Dict) -> List[Dict]:
        title = openapi_dict.get("info", {}).get("title", "Untitled")
        version = openapi_dict.get("info", {}).get("version", "")
        base_url = openapi_dict.get("servers", [{}])[0].get("url", "")

        # 1. Guardar integración
        integration = OpenAPIIntegration(
            user_id=self.user.id,
            title=title,
            version=version,
            base_url=base_url,
            raw_json=str(openapi_dict)
        )
        self.db.add(integration)
        self.db.commit()
        self.db.refresh(integration)

        # 2. Parsear y guardar funciones
        parsed_functions = parse_openapi_to_functions(openapi_dict)
        saved_functions = []

        for func_def in parsed_functions:
            function_create = FunctionCreate(
                name=func_def["name"],
                description=func_def.get("description"),
                definition=func_def["parameters"],
                code=None
            )
            new_func = self.function_service.create_function(
                user_id=self.user.id,
                data=function_create
            )
            saved_functions.append(new_func)

        return saved_functions
