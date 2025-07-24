# app/seeds/seed_all.py

from app.core.service_factory import ServiceFactory
from app.schemas.event_definition_schema import EventDefinitionCreate


def seed_permissions(factory: ServiceFactory):
    perm_matrix = {
        "apps": ["create", "read", "update", "delete"],
        "functions": ["create", "read", "update", "delete"],
        "strategies": ["create", "read", "update", "delete"],
        "proxies": ["create", "read", "update", "delete"],
        "mcp": ["create", "read", "update", "delete"],
    }

    permission_service = factory.get_permission_service()

    for res, acts in perm_matrix.items():
        for act in acts:
            code = f"{res}:{act}"
            permission_service.get_or_create(code, description=f"{act.capitalize()} {res.capitalize()}")


def seed_event_definitions(factory: ServiceFactory):
    event_service = factory.get_event_definition_service()

    default_events = [
        {
            "code": "new_db_row",
            "name": "Nuevo registro en tabla",
            "description": "Detecta un nuevo registro en una tabla específica de una base de datos conectada",
            "required_config": {
                "database_connection_id": "UUID",
                "table_name": "str",
                "time_field": "str"
            }
        },
        {
            "code": "new_user_signup",
            "name": "Nuevo registro de usuario",
            "description": "Un nuevo usuario se ha registrado en tu sistema",
            "required_config": {
                "email_field": "str",
                "timestamp_field": "str"
            }
        },
        {
            "code": "webhook_received",
            "name": "Webhook recibido",
            "description": "Se ha recibido un webhook en un endpoint determinado",
            "required_config": {
                "path": "str",
                "method": "str"
            }
        },
        {
            "code": "api_event_triggered",
            "name": "Llamada API externa",
            "description": "Una API externa ha hecho una llamada que debe generar un evento",
            "required_config": {
                "auth_token": "str",
                "endpoint": "str"
            }
        },
        {
            "code": "cron_trigger",
            "name": "Trigger por horario (cron)",
            "description": "El evento se ejecuta basado en un patrón de tiempo definido",
            "required_config": {
                "cron_expression": "str"
            }
        }
    ]

    for event_data in default_events:
        exists = event_service.get_by_code(event_data["code"])
        if not exists:
            event_service.create(EventDefinitionCreate(**event_data))
