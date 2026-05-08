from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class CompanyBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    ruc: str = Field(..., min_length=11, max_length=11, pattern=r"^\d{11}$")

class CompanyCreate(CompanyBase):
    pass

class Company(CompanyBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
