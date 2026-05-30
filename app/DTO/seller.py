from typing import Optional
from sqlmodel import SQLModel
from uuid import UUID
from datetime import datetime
from pydantic import Field

class SellerCreate(SQLModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    middle_name: Optional[str] = None
    password: str = Field(min_length=8, max_length=128)
    email: str
    company_name: str
    phone: Optional[str] = None
    inn: str = Field(min_length=10, max_length=12)
    
class SellerLogin(SQLModel):
    email: str
    password: str

class SellerResponse(SQLModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    company_name: str
    phone: Optional[str] = None
    inn: str
    created_at: datetime
    updated_at: datetime

class SellerUpdate(SQLModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None

class TokenResponse(SQLModel):
    user_id: UUID
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int

class RefreshRequest(SQLModel):
    refresh_token: str
