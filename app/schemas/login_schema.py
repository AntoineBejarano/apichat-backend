from pydantic import BaseModel, EmailStr, Field

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6)