"""
Authentication schemas
"""
from pydantic import BaseModel, EmailStr
from app.models.user import UserRole


class LoginRequest(BaseModel):
    """Login request schema"""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response schema"""
    access_token: str
    user: "UserResponse"


class UserResponse(BaseModel):
    """User response schema"""
    id: str
    email: str
    role: UserRole
    account_id: str
    
    class Config:
        from_attributes = True

