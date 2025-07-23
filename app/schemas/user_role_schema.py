from pydantic import BaseModel
from typing import List

class UserRoleAssign(BaseModel):
    role_id: int

    model_config = {"from_attributes": False}

class UserRoleOut(BaseModel):
    user_id: int
    role_ids: List[int]

    model_config = {"from_attributes": False}

class RoleSummary(BaseModel):
    id: int
    name: str
    description: str | None = None

    model_config = {"from_attributes": True}
