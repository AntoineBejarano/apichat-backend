import logging
from fastapi import HTTPException
from sqlalchemy.orm import Session
from typing import List, TYPE_CHECKING

from app.models.user_model import User
from app.models.role_model import Role

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)

class UserRoleService:
    def __init__(self, factory: "ServiceFactory"):
        self.db: Session = factory.db
        self.user = factory.user  # usuario autenticado

    def assign_role(self, user_id: int, role_id: int) -> dict:
        user = self.db.query(User).filter(User.id == user_id).first()
        role = self.db.query(Role).filter(Role.id == role_id).first()

        if not user or not role:
            raise HTTPException(status_code=404, detail="User or role not found")

        if role in user.roles:
            raise HTTPException(status_code=400, detail="Role already assigned")

        user.roles.append(role)
        self.db.commit()

        logger.info(f"[UserRoleService] ✅ Role {role_id} assigned to user {user_id}")
        return {"detail": "Role assigned successfully"}

    def remove_role(self, user_id: int, role_id: int) -> dict:
        user = self.db.query(User).filter(User.id == user_id).first()
        role = self.db.query(Role).filter(Role.id == role_id).first()

        if not user or not role:
            raise HTTPException(status_code=404, detail="User or role not found")

        if role not in user.roles:
            raise HTTPException(status_code=400, detail="Role not assigned")

        user.roles.remove(role)
        self.db.commit()

        logger.info(f"[UserRoleService] ❌ Role {role_id} removed from user {user_id}")
        return {"detail": "Role removed successfully"}

    def list_roles(self, user_id: int) -> List[Role]:
        user = self.db.query(User).filter(User.id == user_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        logger.info(f"[UserRoleService] 📄 Listing roles for user {user_id}")
        return user.roles
