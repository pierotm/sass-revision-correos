from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class CredentialBase(BaseModel):
    sol_user: str = Field(..., min_length=2, max_length=50)

class CredentialCreate(CredentialBase):
    sol_password: str = Field(..., min_length=4)

class Credential(CredentialBase):
    id: int
    company_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
