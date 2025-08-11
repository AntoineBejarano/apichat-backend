import logging
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.role_model import Role
from app.models.permission_model import Permission
from app.schemas.role_schema import RoleCreate, RoleUpdate

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)

class RoleService:
    def __init__(self, factory: "ServiceFactory"):
        self.db: Session = factory.db
        self.user = factory.user
        logger.info("[RoleService] ✅ Initialized for user_id=%s", self.user.id)

    def create(self, role_data: RoleCreate) -> Role:
        logger.info("[RoleService] ➕ Creating new role: %s", role_data.name)
        role = Role(**role_data.model_dump())
        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)
        return role

    def get_all(self) -> List[Role]:
        logger.info("[RoleService] 📋 Retrieving all roles")
        return self.db.query(Role).all()

    def get_by_id(self, role_id: int) -> Role:
        logger.debug("[RoleService] 🔍 Fetching role ID=%s", role_id)
        role = self.db.query(Role).filter(Role.id == role_id).first()
        if not role:
            logger.error("[RoleService] ❌ Role ID=%s not found", role_id)
            raise HTTPException(status_code=404, detail="Role not found")
        return role

    def update(self, role_id: int, updates: RoleUpdate) -> Role:
        role = self.get_by_id(role_id)
        logger.info("[RoleService] ✏️ Updating role ID=%s", role_id)
        for field, value in updates.model_dump(exclude_unset=True).items():
            setattr(role, field, value)
        self.db.commit()
        self.db.refresh(role)
        return role

    def delete(self, role_id: int) -> None:
        role = self.get_by_id(role_id)
        logger.warning("[RoleService] 🗑️ Deleting role ID=%s", role_id)
        self.db.delete(role)
        self.db.commit()

    def assign_permission(self, role_id: int, permission_id: int) -> Role:
        role = self.get_by_id(role_id)
        permission = self.db.query(Permission).filter(Permission.id == permission_id).first()
        if not permission:
            raise HTTPException(status_code=404, detail="Permission not found")
        if permission not in role.permissions:
            role.permissions.append(permission)
            self.db.commit()
            logger.info("[RoleService] ✅ Permission %s added to role %s", permission_id, role_id)
        return role

    def remove_permission(self, role_id: int, permission_id: int) -> Role:
        role = self.get_by_id(role_id)
        role.permissions = [p for p in role.permissions if p.id != permission_id]
        self.db.commit()
        logger.info("[RoleService] ❌ Permission %s removed from role %s", permission_id, role_id)
        return role
