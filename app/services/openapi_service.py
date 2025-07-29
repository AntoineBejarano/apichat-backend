from typing import List, Dict
from sqlalchemy.exc import SQLAlchemyError
from app.integrations.openapi_parser import parse_openapi_to_functions
from app.models.openapi_model import OpenAPIIntegration
from app.schemas.function_schema import FunctionCreate
from app.schemas.app_schema import AppCreate
from app.core.service_factory import ServiceFactory


class OpenAPIProcessor:
    def __init__(self, factory: ServiceFactory):
        self.db = factory.db
        self.user = factory.user
        self.function_service = factory.get_function_service()
        self.app_service = factory.get_apps_service()

    def process(self, openapi_dict: Dict, app_id: str | None = None) -> List:
        title = openapi_dict.get("info", {}).get("title", "Untitled")
        version = openapi_dict.get("info", {}).get("version", "")
        base_url = openapi_dict.get("servers", [{}])[0].get("url", "")

        parsed_functions = parse_openapi_to_functions(openapi_dict)
        if not parsed_functions:
            raise ValueError("❌ No se encontraron funciones válidas en el archivo OpenAPI.")

        try:
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

            if app_id is None:
                app = self.app_service.create(
                    AppCreate(
                        name=title,
                        description=f"App generada automáticamente desde OpenAPI {title}"
                    )
                )
                app_id = str(app.id)

            saved_functions = []

            for func_def in parsed_functions:
                function_create = FunctionCreate(
                    name=func_def["name"],
                    description=func_def.get("description"),
                    parameters=func_def["parameters"],
                    execution_type="http",
                    method=func_def["method"],
                    url=func_def["url"],
                    headers={},
                    body={},
                    code=None,
                    app_id=app_id,
                    integration_id=str(integration.id),
                    active=True
                )
                new_func = self.function_service.create(function_create)
                saved_functions.append(new_func)

            return saved_functions

        except SQLAlchemyError as e:
            self.db.rollback()
            raise RuntimeError(f"❌ Error al guardar integración o funciones: {str(e)}")
