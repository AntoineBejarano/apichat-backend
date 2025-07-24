from pydantic import BaseModel
from typing import List
from uuid import UUID

class UserRoleAssign(BaseModel):
    role_id: int

    model_config = {"from_attributes": False}

class UserRoleOut(BaseModel):
    user_id: UUID
    role_ids: List[int]

    model_config = {"from_attributes": False}

class RoleSummary(BaseModel):
    id: UUID
    name: str
    description: str | None = None

    model_config = {"from_attributes": True}

