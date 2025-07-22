import logging
from typing import List
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.permission_model import Permission
from app.schemas.permission_schema import PermissionCreate, PermissionUpdate

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)

class PermissionService:
    def __init__(self, factory: "ServiceFactory"):
        self.factory = factory
        self.db: Session = factory.db
        logger.info("[PermissionService] ✅ Initialized")

    def get_current_user(self):
        return self.factory.user  # Solo cuando realmente se necesita

    def create(self, permission_data: PermissionCreate) -> Permission:
        logger.info("[PermissionService] ➕ Creating permission: %s", permission_data.name)
        permission = Permission(**permission_data.dict())
        self.db.add(permission)
        self.db.commit()
        self.db.refresh(permission)
        return permission

    def get_all(self) -> List[Permission]:
        logger.debug("[PermissionService] 📋 Fetching all permissions")
        return self.db.query(Permission).all()

    def get_by_id(self, permission_id: int) -> Permission:
        logger.debug("[PermissionService] 🔍 Fetching permission ID=%s", permission_id)
        permission = self.db.query(Permission).filter(Permission.id == permission_id).first()
        if not permission:
            logger.error("[PermissionService] ❌ Permission ID=%s not found", permission_id)
            raise HTTPException(status_code=404, detail="Permission not found")
        return permission

    def update(self, permission_id: int, updates: PermissionUpdate) -> Permission:
        permission = self.get_by_id(permission_id)
        logger.info("[PermissionService] ✏️ Updating permission ID=%s", permission_id)
        for field, value in updates.dict(exclude_unset=True).items():
            setattr(permission, field, value)
        self.db.commit()
        self.db.refresh(permission)
        return permission

    def delete(self, permission_id: int) -> None:
        permission = self.get_by_id(permission_id)
        logger.warning("[PermissionService] 🗑️ Deleting permission ID=%s", permission_id)
        self.db.delete(permission)
        self.db.commit()

    def get_or_create(self, code: str, description: str = "") -> Permission:
        existing = self.db.query(Permission).filter(Permission.code == code).first()
        if existing:
            logger.debug("[PermissionService] ✅ Found existing permission: %s", code)
            return existing

        logger.info("[PermissionService] ➕ Creating new permission: %s", code)
        new_permission = Permission(code=code, description=description, name=code)
        self.db.add(new_permission)
        self.db.commit()
        self.db.refresh(new_permission)
        return new_permission
