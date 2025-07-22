# app/seeds/seed_permissions.py
from app.core.service_factory import ServiceFactory

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
