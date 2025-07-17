from pydantic import BaseModel
from typing import List

class UserRoleAssign(BaseModel):
    role_id: int

class UserRoleOut(BaseModel):
    user_id: int
    role_ids: List[int]

class RoleSummary(BaseModel):
    id: int
    name: str
    description: str | None = None

    class Config:
        orm_mode = True
